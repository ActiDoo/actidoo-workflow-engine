# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""Core utilities for interactive OIDC authentication."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from authlib.oauth2.rfc6749 import OAuth2Token
from fastapi import Request
from sqlalchemy.exc import OperationalError

from actidoo_wfe.auth.claims import get_email, get_first_name, get_idp_user_id, get_last_name, get_username, get_roles, set_claims
from actidoo_wfe.auth.schema import LoginStateSchema
from actidoo_wfe.auth.authlib_starlette import StarletteOAuth2App
from actidoo_wfe.auth.constants import ROLE_TO_LOGIN_STATE_MAP, SESSION_IDP_CLAIMS_KEY, SESSION_TOKEN_KEY
from actidoo_wfe.settings import settings

log = logging.getLogger(__name__)

# Bound every identity-provider call (login, JWKS, token refresh) so a slow or hanging
# provider can never hold the session row lock (or a request) open indefinitely.
_OIDC_HTTP_TIMEOUT_SECONDS = 15


class FrameworkOAuth2Token:
    def update_token(token, refresh_token=None, access_token=None):
        pass


client: StarletteOAuth2App = StarletteOAuth2App(
    framework=FrameworkOAuth2Token(),
    name="idp",
    client_id=settings.oidc_client_id,
    client_secret=settings.oidc_client_secret,
    server_metadata_url=settings.oidc_discovery_url,
    client_kwargs={
        "scope": settings.oidc_scopes,
    },
    code_challenge_method="S256",
    timeout=_OIDC_HTTP_TIMEOUT_SECONDS,
)


def set_token_in_session(request: Request, token: Dict[str, Any]) -> None:
    request.session[SESSION_TOKEN_KEY] = token


def get_token_from_session(request: Request) -> Dict[str, Any] | None:
    token = request.session.get(SESSION_TOKEN_KEY)
    return token


def token_needs_refresh(token: Dict[str, Any]) -> Optional[int]:
    return OAuth2Token(token).is_expired(leeway=settings.oidc_token_refresh_skew_seconds)


def token_is_expired(token: Dict[str, Any]) -> Optional[int]:
    return OAuth2Token(token).is_expired(leeway=0)


def refresh_token_if_needed(request: Request) -> None:
    """Silently renew the OIDC access token before it expires.

    The access token is short-lived (minutes) but the server-side session lasts days, so
    an idle user would otherwise be logged out the moment the token lapses even though the
    session is still valid.

    A refresh token may be single-use, so it must be presented to the provider exactly
    once. We get that by running the read-refresh-write in one transaction that locks the
    session row: a second request for the same session finds the row locked. If its own
    token is still valid it backs off and lets that refresh rotate the token, so nobody
    waits on the lock; if its own token has already expired, backing off would mean a
    certain 401, so it waits for the in-flight refresh and adopts the rotated token
    instead. Because the lock is the row, single-use also holds across processes. A slow
    or failing provider falls through to the normal expiry check.
    """
    token = get_token_from_session(request)
    if not token or not token.get("refresh_token") or not token_needs_refresh(token):
        return

    scope = getattr(request, "scope", {}) or {}
    session_token = scope.get("session_token")
    if not session_token:
        # No persisted session row to coordinate on (e.g. outside the SessionMiddleware);
        # skip rather than refresh without the single-use guarantee.
        return

    from actidoo_wfe.database import get_db_contextmanager
    from actidoo_wfe.session import load_session_for_update

    # Only back off from a busy row while our own token is still usable; if it has already
    # expired, backing off would just 401, so wait for the in-flight refresh instead.
    may_skip = not token_is_expired(token)

    new_token: Optional[Dict[str, Any]] = None
    new_claims: Optional[Dict[str, Any]] = None

    with get_db_contextmanager() as db:
        try:
            row = load_session_for_update(db=db, token=session_token, skip_locked=may_skip)
        except OperationalError:
            # Waited for a concurrent refresh but it did not release the row in time; fall
            # through to the expiry check rather than erroring the request.
            return
        if row is None or not isinstance(row.data, dict):
            return

        stored = row.data.get(SESSION_TOKEN_KEY)
        if not isinstance(stored, dict):
            return
        if not stored.get("refresh_token") or not token_needs_refresh(stored):
            # Another request already rotated the token; adopt it instead of spending an
            # already-consumed refresh token.
            new_token = stored
            claims = row.data.get(SESSION_IDP_CLAIMS_KEY)
            new_claims = claims if isinstance(claims, dict) else None
        else:
            try:
                fetched = client.fetch_access_token(
                    grant_type="refresh_token", refresh_token=stored["refresh_token"]
                )
            except Exception:  # noqa: BLE001 - fall through to the expiry check on any failure
                log.warning("OIDC access token refresh failed", exc_info=True)
                return

            # A refresh response may omit id_token/id_info; keep the originals so logout and
            # cached user data stay intact.
            for carry_over in ("id_token", "id_info"):
                if carry_over not in fetched and carry_over in stored:
                    fetched[carry_over] = stored[carry_over]

            # Re-derive roles/claims from the fresh token, as login does, so a role change
            # or revocation takes effect instead of staying frozen at login.
            try:
                new_claims = client.get_combined_userdata(token=fetched)
            except Exception:  # noqa: BLE001 - keep the old claims rather than fail the refresh
                log.warning("Could not refresh user claims after token refresh", exc_info=True)
                existing = row.data.get(SESSION_IDP_CLAIMS_KEY)
                new_claims = existing if isinstance(existing, dict) else None

            new_token = fetched

            # Authoritative write inside the locked transaction.
            new_data = dict(row.data)
            new_data[SESSION_TOKEN_KEY] = new_token
            if isinstance(new_claims, dict):
                new_data[SESSION_IDP_CLAIMS_KEY] = new_claims
            row.data = new_data

    # Make the fresh token/claims visible to the rest of this request.
    if isinstance(new_token, dict):
        set_token_in_session(request, new_token)
    if isinstance(new_claims, dict):
        set_claims(request, new_claims)


def is_logged_in(request: Request) -> bool:
    token = get_token_from_session(request)
    if not token:
        return False
    if token_is_expired(token):
        return False
    return True


def has_role(request: Request, role: str) -> bool:
    return role in set(get_roles(request))


def get_login_state(request: Request) -> LoginStateSchema:
    logged_in = is_logged_in(request)
    roles = get_roles(request) if logged_in else []

    permissions: Dict[str, bool] = {}

    for key, required_role in ROLE_TO_LOGIN_STATE_MAP.items():
        permissions[key] = logged_in and has_role(request=request, role=required_role)

    return LoginStateSchema(
        is_logged_in=logged_in,
        username=get_username(request=request),
        email=get_email(request=request),
        first_name=get_first_name(request=request),
        last_name=get_last_name(request=request),
        idp_user_id=get_idp_user_id(request=request),
        roles=roles,
        **permissions,
    )
