# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""Core utilities for interactive OIDC authentication."""

from __future__ import annotations

from typing import Any, Dict, Optional

from authlib.oauth2.rfc6749 import OAuth2Token
from fastapi import Request

from actidoo_wfe.auth.claims import get_email, get_first_name, get_idp_user_id, get_last_name, get_username, get_roles
from actidoo_wfe.auth.schema import LoginStateSchema
from actidoo_wfe.auth.authlib_starlette import StarletteOAuth2App
from actidoo_wfe.auth.constants import ROLE_TO_LOGIN_STATE_MAP, SESSION_TOKEN_KEY
from actidoo_wfe.settings import settings

class FrameworkOAuth2Token():
    def update_token(token, refresh_token=None, access_token=None):
        pass
    
client: StarletteOAuth2App = StarletteOAuth2App(
    framework=FrameworkOAuth2Token(),
    name="idp",
    client_id=settings.oidc_client_id,
    client_secret=settings.oidc_client_secret,
    server_metadata_url=settings.oidc_discovery_url,
    client_kwargs={
        "scope": settings.oidc_scopes
    },
    code_challenge_method="S256",
)

def set_token_in_session(request: Request, token: Dict[str, Any]) -> None:
    request.session[SESSION_TOKEN_KEY] = token

def get_token_from_session(request: Request) -> Dict[str, Any]|None:
    token = request.session.get(SESSION_TOKEN_KEY)
    return token

def token_needs_refresh(token: Dict[str, Any]) -> Optional[int]:
    return OAuth2Token(token).is_expired(leeway=settings.oidc_token_refresh_skew_seconds)

def token_is_expired(token: Dict[str, Any]) -> Optional[int]:
    return OAuth2Token(token).is_expired(leeway=0)

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
