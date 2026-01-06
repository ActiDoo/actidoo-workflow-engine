# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

import logging

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse

from actidoo_wfe.auth.authlib_starlette import OAuthError
from actidoo_wfe.auth.claims import get_claims, set_claims
from actidoo_wfe.auth.core import get_login_state, get_token_from_session, set_token_in_session, client
from actidoo_wfe.auth.hooks import call_login_hooks
from actidoo_wfe.auth.schema import LoginStateResponseSchema
from actidoo_wfe.database import get_db
from actidoo_wfe.settings import settings

router = APIRouter(tags=["auth"])
log = logging.getLogger(__name__)

@router.get("/do_login", name="auth_do_login", include_in_schema=False)
def do_login(request: Request, redirect_url: str) -> Response:
    fastapi_redirect_uri = str(request.url_for("auth_login_callback"))
    request.session["login_redirect_url"] = redirect_url
    client.client_kwargs["scope"] = settings.oidc_scopes
    return client.authorize_redirect(request, fastapi_redirect_uri)

@router.get("/get_login_state", name="auth_get_login_state")
def get_login_state_endpoint(request: Request) -> LoginStateResponseSchema:
    loginstate = get_login_state(request=request)
    return LoginStateResponseSchema.model_validate(loginstate.model_dump())

@router.get("/login_callback", name="auth_login_callback", include_in_schema=False)
def login_callback(request: Request, db=Depends(get_db)):
    try:
        if "login_fails" not in request.session:
            request.session["login_fails"] = 0
        request.session["login_fails"] += 1

        # If the IdP redirected back with an error (e.g. user denied consent), surface it as an OAuthError
        # so we follow the regular redirect/backoff flow instead of crashing with a 500.
        provider_error = request.query_params.get("error")
        if provider_error:
            raise OAuthError(error=provider_error)
        
        access_token = client.authorize_access_token(request=request, redirect_uri=str(request.url_for("auth_login_callback")))
        set_token_in_session(request, access_token)

        claims = client.get_combined_userdata(token=access_token)
        set_claims(request, claims)

        call_login_hooks(request, db)
    except (OAuthError,) as e:
        log.exception("Login callback failed: %s", e)
        if (
            request.session["login_fails"] >= 10
        ):  # prevent endless redirect if frontend auto-initiates login
            request.session["login_fails"] = 0
            return RedirectResponse(url=request.url_for("auth_fallback"))
        
        return RedirectResponse(
            url=request.session.get(
                "login_redirect_url", request.url_for("auth_fallback")
            )
        )
    
    try:
        return RedirectResponse(
            url=request.session.get(
                "login_redirect_url", request.url_for("auth_fallback")
            )
        )
    except KeyError:
        return RedirectResponse(url=request.url_for("auth_fallback"))


@router.get("/do_logout", name="auth_do_logout", include_in_schema=False)
def do_logout(request: Request, redirect_url: str, db=Depends(get_db)) -> Response:
    fastapi_redirect_uri = str(request.url_for("auth_logout_callback"))
    token = get_token_from_session(request)
    logout_target = client.make_logout_url(redirect_uri=fastapi_redirect_uri, id_token=token.get("id_token") if token else None)

    request.session.clear()

    response = RedirectResponse(url=logout_target or fastapi_redirect_uri)
    response.set_cookie(key="logout_redirect_url", value=redirect_url, secure=True, httponly=True)
    return response


@router.get("/logout_callback", name="auth_logout_callback", include_in_schema=False)
def logout_callback(request: Request, db=Depends(get_db)):
    redirect_url = request.cookies.get(
        "logout_redirect_url", str(request.url_for("auth_fallback"))
    )
    response = RedirectResponse(url=redirect_url)
    response.delete_cookie(key="logout_redirect_url", secure=True, httponly=True)
    return response


@router.get("/", name="auth_fallback", include_in_schema=False)
def auth_fallback(request: Request) -> Response:

    login_state = get_login_state(request=request)

    debug_requested = settings.auth_debug_token_introspection or request.query_params.get(
        "debug", ""
    ).lower() in {"1", "true", "yes", "on"}

    if debug_requested:
        token_debug = ""
        if settings.auth_debug_token_introspection and login_state.is_logged_in:
            token_debug = f"<br><br><pre>{get_claims(request)}</pre>"

        content = (
            "<html><body>Please visit target application. "
            f"<br> LoggedIn: {login_state.is_logged_in}{token_debug}</body></html>"
        )
        return HTMLResponse(content=content, status_code=200)

    # Prefer the configured frontend entrypoint; fall back to explicit override only if frontend_base_url is empty.
    fallback_target = settings.frontend_base_url or settings.auth_fallback_redirect or "/"
    return RedirectResponse(url=fallback_target)
