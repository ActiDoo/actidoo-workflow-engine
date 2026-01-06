# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

import sys
import time
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from authlib.jose import JsonWebKey, jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.testclient import TestClient
from sqlalchemy import select

from actidoo_wfe.auth.authlib_starlette import OAuthError, StarletteOAuth2App
from actidoo_wfe.auth.constants import SESSION_TOKEN_KEY
from actidoo_wfe.auth.core import FrameworkOAuth2Token
from actidoo_wfe.auth.fastapi import router as auth_router
from actidoo_wfe.database import get_db_contextmanager
from actidoo_wfe.session import SessionMiddleware, SessionModel
from actidoo_wfe.settings import settings


def _build_test_idp():
    """Create a minimal in-memory OIDC IdP for happy-path testing."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    kid = "test-key"
    base_url = "http://idp.test"
    default_code = "test-code"
    default_refresh_token = "refresh-token"
    issuer = base_url
    state_store: dict[str, dict[str, Any]] = {}
    last_state: dict[str, str | None] = {"value": None}

    user_profile = {
        "sub": "user-123",
        "preferred_username": "workflow.user",
        "email": "workflow@example.com",
        "given_name": "Workflow",
        "family_name": "User",
        "realm_access": {"roles": ["wf-user"]},
    }

    app = FastAPI()

    @app.get("/.well-known/openid-configuration")
    def configuration():
        return {
            "issuer": issuer,
            "authorization_endpoint": f"{base_url}/authorize",
            "token_endpoint": f"{base_url}/token",
            "userinfo_endpoint": f"{base_url}/userinfo",
            "jwks_uri": f"{base_url}/jwks",
            "end_session_endpoint": f"{base_url}/logout",
        }

    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    public_jwk = JsonWebKey.import_key(public_pem).as_dict(is_private=False)
    public_jwk["kid"] = kid

    @app.get("/jwks")
    def jwks():
        return {"keys": [public_jwk]}

    @app.get("/authorize")
    def authorize(redirect_uri: str, state: str, **_: str):
        """Simulate user consent by redirecting back with a static code."""
        redirect = httpx.URL(redirect_uri).include_query_params(code=default_code, state=state)
        last_state["value"] = state
        return RedirectResponse(str(redirect))

    def _encode(claims: dict) -> str:
        header = {"alg": "RS256", "kid": kid}
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        token = jwt.encode(header, claims, private_pem)
        return token.decode("utf-8") if isinstance(token, bytes) else token

    @app.post("/token")
    def token(
        grant_type: str = Form(...),
        code: str = Form(None),
        refresh_token: str = Form(None),
        client_id: str | None = Form(None),
        redirect_uri: str | None = Form(None),
        code_verifier: str | None = Form(None),
    ):
        del client_id, redirect_uri, code_verifier  # unused for the happy-path
        now = int(time.time())

        nonce: str | None = None

        if grant_type == "authorization_code":
            if code != default_code:
                raise HTTPException(status_code=400, detail="invalid_code")
        elif grant_type == "refresh_token":
            if refresh_token != default_refresh_token:
                raise HTTPException(status_code=400, detail="invalid_refresh_token")
        else:
            raise HTTPException(status_code=400, detail="unsupported_grant")

        nonce = state_store.get(last_state["value"], {}).get("nonce")

        access_claims = {
            "iss": issuer,
            "aud": [],
            "azp": "test-client",
            "sub": user_profile["sub"],
            "preferred_username": user_profile["preferred_username"],
            "email": user_profile["email"],
            "realm_access": user_profile["realm_access"],
            "scope": "wf-user",
            "exp": now + 3600,
            "iat": now,
        }

        id_claims = {
            "iss": issuer,
            "aud": "test-client",
            "sub": user_profile["sub"],
            "email": user_profile["email"],
            "preferred_username": user_profile["preferred_username"],
            "given_name": user_profile["given_name"],
            "family_name": user_profile["family_name"],
            "realm_access": user_profile["realm_access"],
            "scope": "wf-user",
            "exp": now + 3600,
            "iat": now,
        }
        if nonce:
            id_claims["nonce"] = nonce

        payload = {
            "access_token": _encode(access_claims),
            "id_token": _encode(id_claims),
            "token_type": "Bearer",
            "expires_in": 3600,
            "expires_at": now + 3600,
            "refresh_token": default_refresh_token,
            "scope": "openid profile email",
        }
        payload["userinfo"] = dict(user_profile)
        return payload

    @app.get("/userinfo")
    def userinfo():
        return user_profile

    @app.get("/logout")
    def logout(post_logout_redirect_uri: str):
        return RedirectResponse(url=post_logout_redirect_uri)

    transport = httpx.ASGITransport(app=app)

    return {
        "app": app,
        "transport": transport,
        "base_url": base_url,
        "code": default_code,
        "refresh_token": default_refresh_token,
        "jwks": {"keys": [public_jwk]},
        "state_store": state_store,
        "last_state": last_state,
        "user_profile": dict(user_profile),
    }


@pytest.fixture
def oidc_environment(monkeypatch):
    """Configure the application to use the in-memory OIDC provider."""
    provider = _build_test_idp()

    metadata = {
        "issuer": provider["base_url"],
        "authorization_endpoint": f"{provider['base_url']}/authorize",
        "token_endpoint": f"{provider['base_url']}/token",
        "userinfo_endpoint": f"{provider['base_url']}/userinfo",
        "jwks_uri": f"{provider['base_url']}/jwks",
        "end_session_endpoint": f"{provider['base_url']}/logout",
    }

    remote_app = StarletteOAuth2App(
        framework=FrameworkOAuth2Token(),
        name="idp",
        client_id="test-client",
        client_secret="test-secret",
        server_metadata=metadata,
        client_kwargs={
            "scope": "openid profile email",
            "code_challenge_method": "S256",
            "transport": provider["transport"],
        },
        timeout=5,
        verify=False,
    )

    def _load_metadata(self):
        self._server_metadata = metadata  # type: ignore[attr-defined]
        return metadata

    remote_app.load_server_metadata = _load_metadata.__get__(remote_app, type(remote_app))  # type: ignore[assignment]

    idp_client = TestClient(provider["app"], base_url=provider["base_url"])

    def _fetch_access_token(self, request_token_url=None, **request_kwargs):
        if request_kwargs.get("refresh_token"):
            data = {
                "grant_type": "refresh_token",
                "refresh_token": request_kwargs["refresh_token"],
            }
        else:
            code = request_kwargs.get("code")
            if not code and request_kwargs.get("authorization_response"):
                parsed = urlparse(request_kwargs["authorization_response"])
                code = parse_qs(parsed.query).get("code", [None])[0]
            data = {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": request_kwargs.get("redirect_uri"),
                "code_verifier": request_kwargs.get("code_verifier"),
            }
        response = idp_client.post("/token", data={k: v for k, v in data.items() if v is not None})
        if response.status_code >= 400:
            detail = response.json().get("detail") if response.headers.get("content-type", "").startswith("application/json") else response.text
            raise OAuthError(error=detail or "token_request_failed")
        return response.json()

    def _fetch_jwk_set(self):
        return provider["jwks"]

    remote_app.fetch_access_token = _fetch_access_token.__get__(remote_app, type(remote_app))  # type: ignore[assignment]
    remote_app.fetch_jwk_set = _fetch_jwk_set.__get__(remote_app, type(remote_app))  # type: ignore[assignment]

    original_authorize_access_token = remote_app.authorize_access_token

    def _authorize_access_token(self, request, redirect_uri, **kwargs):
        state_data = self._get_session(request).get(f"{self.name}:state") or {}
        state_value = state_data.get("state")
        if state_value:
            provider["last_state"]["value"] = state_value
            provider["state_store"][state_value] = {
                "nonce": state_data.get("nonce"),
            }
        return original_authorize_access_token(request=request, redirect_uri=redirect_uri, **kwargs)

    remote_app.authorize_access_token = _authorize_access_token.__get__(remote_app, type(remote_app))  # type: ignore[assignment]

    import actidoo_wfe.auth.core as auth_core
    import actidoo_wfe.auth.fastapi as auth_fastapi

    monkeypatch.setattr(auth_core, "client", remote_app)
    monkeypatch.setattr(auth_fastapi, "client", remote_app)

    monkeypatch.setattr(settings, "disable_login_check", False)
    monkeypatch.setattr(
        settings,
        "oidc_discovery_url",
        f"{provider['base_url']}/.well-known/openid-configuration",
    )
    monkeypatch.setattr(settings, "oidc_client_id", "test-client")
    monkeypatch.setattr(settings, "oidc_client_secret", "test-secret")
    monkeypatch.setattr(settings, "oidc_scopes", "openid profile email")
    monkeypatch.setattr(settings, "oidc_verify_ssl", "false")

    monkeypatch.setattr(sys, "_called_from_test", False, raising=False)

    try:
        yield provider
    finally:
        idp_client.close()


@pytest.fixture
def auth_test_client(monkeypatch, oidc_environment, db_engine_ctx):
    with db_engine_ctx():
        app = FastAPI()
        app.include_router(auth_router)
        app.add_middleware(
            SessionMiddleware,
            session_cookie="wfesess",
            same_site=settings.session_same_site,
            https_only=settings.session_https_only,
        )

        import actidoo_wfe.auth.hooks as hooks_module
        import actidoo_wfe.auth.fastapi as auth_fastapi_module

        monkeypatch.setattr(hooks_module, "call_login_hooks", lambda request, db: None)
        monkeypatch.setattr(auth_fastapi_module, "call_login_hooks", lambda request, db: None)

        client = TestClient(app, base_url="https://testserver")
        try:
            yield client
        finally:
            client.close()


def _initiate_login(client: TestClient, redirect_url: str = "/welcome") -> tuple[str, str]:
    login_url = client.app.url_path_for("auth_do_login")
    response = client.get(
        login_url,
        params={"redirect_url": redirect_url},
        follow_redirects=False,
    )
    assert response.status_code in (302, 303, 307)

    parsed = urlparse(response.headers["location"])
    state = parse_qs(parsed.query)["state"][0]
    return state, redirect_url


def _fetch_session_data(client: TestClient) -> dict[str, Any]:
    token = client.cookies.get("wfesess")
    assert token, "session cookie missing"
    with get_db_contextmanager() as db:
        record = db.execute(
            select(SessionModel).where(SessionModel.token == token)
        ).scalar_one_or_none()
        if record is None or record.data is None:
            return {}
        return dict(record.data)


def test_login_redirect_respects_configured_scope(
    oidc_environment, auth_test_client, monkeypatch
):
    client = auth_test_client
    custom_scope = "openid email offline_access"
    monkeypatch.setattr(settings, "oidc_scopes", custom_scope)

    login_url = client.app.url_path_for("auth_do_login")
    response = client.get(
        login_url,
        params={"redirect_url": "/after-login"},
        follow_redirects=False,
    )

    assert response.status_code in (302, 303, 307)
    parsed = urlparse(response.headers["location"])
    assert parse_qs(parsed.query)["scope"] == [custom_scope]


def test_full_login_flow_happy_path(oidc_environment, auth_test_client):
    client = auth_test_client
    state, redirect_target = _initiate_login(client)

    callback_url = client.app.url_path_for("auth_login_callback")
    callback_response = client.get(
        callback_url,
        params={"code": oidc_environment["code"], "state": state},
        follow_redirects=False,
    )
    assert callback_response.status_code in (302, 303, 307)
    assert callback_response.headers["location"] == redirect_target

    login_state_url = client.app.url_path_for("auth_get_login_state")
    login_state_response = client.get(login_state_url, follow_redirects=False)
    assert login_state_response.status_code == 200
    payload = login_state_response.json()

    assert payload["is_logged_in"] is True
    assert payload["username"] == oidc_environment["user_profile"]["preferred_username"]
    assert payload["email"] == oidc_environment["user_profile"]["email"]
    assert payload["can_access_wf"] is True
    assert payload["can_access_wf_admin"] is False


def test_login_callback_with_invalid_code_redirects_to_original_target(
    oidc_environment, auth_test_client
):
    client = auth_test_client
    state, redirect_target = _initiate_login(client, redirect_url="/desired")

    callback_url = client.app.url_path_for("auth_login_callback")
    callback_response = client.get(
        callback_url,
        params={"code": "bad-code", "state": state},
        follow_redirects=False,
    )
    assert callback_response.status_code in (302, 303, 307)
    assert callback_response.headers["location"].endswith(redirect_target)

    session_data = _fetch_session_data(client)
    assert session_data.get("login_fails") == 1
    assert SESSION_TOKEN_KEY not in session_data


def test_login_callback_redirects_to_fallback_after_many_failures(
    oidc_environment, auth_test_client, monkeypatch
):
    import actidoo_wfe.auth.fastapi as auth_fastapi
    import actidoo_wfe.auth.core as auth_core

    def auth_error(self, request: Request, redirect_uri: str, **_: Any):
        raise OAuthError(error="invalid_grant")

    monkeypatch.setattr(
        auth_fastapi.client,
        "authorize_access_token",
        auth_error.__get__(auth_fastapi.client, type(auth_fastapi.client)),
    )
    monkeypatch.setattr(
        auth_core.client,
        "authorize_access_token",
        auth_error.__get__(auth_core.client, type(auth_core.client)),
    )

    client = auth_test_client
    callback_url = client.app.url_path_for("auth_login_callback")
    fallback_url = client.app.url_path_for("auth_fallback")

    for attempt in range(1, 11):
        state, redirect_target = _initiate_login(client, redirect_url="/retry")
        response = client.get(
            callback_url,
            params={"code": oidc_environment["code"], "state": state},
            follow_redirects=False,
        )
        assert response.status_code in (302, 303, 307)

        session_data = _fetch_session_data(client)
        if attempt < 10:
            assert response.headers["location"].endswith(redirect_target)
            assert session_data.get("login_fails") == attempt
        else:
            assert response.headers["location"].endswith(fallback_url)
            assert session_data.get("login_fails") == 0


def test_login_callback_invalid_claims_redirects_to_original_target(
    oidc_environment, auth_test_client, monkeypatch
):
    import actidoo_wfe.auth.fastapi as auth_fastapi
    import actidoo_wfe.auth.core as auth_core

    def boom(self, token: dict):
        raise OAuthError(error="invalid_token")

    monkeypatch.setattr(
        auth_fastapi.client,
        "access_token_claims_via_jwks",
        boom.__get__(auth_fastapi.client, type(auth_fastapi.client)),
    )
    monkeypatch.setattr(
        auth_core.client,
        "access_token_claims_via_jwks",
        boom.__get__(auth_core.client, type(auth_core.client)),
    )

    client = auth_test_client
    state, redirect_target = _initiate_login(client)

    callback_url = client.app.url_path_for("auth_login_callback")
    response = client.get(
        callback_url,
        params={"code": oidc_environment["code"], "state": state},
        follow_redirects=False,
    )
    assert response.status_code in (302, 303, 307)
    assert response.headers["location"].endswith(redirect_target)
    session_data = _fetch_session_data(client)
    assert session_data.get("login_fails") == 1


def test_login_callback_value_error_redirects_to_original_target(
    oidc_environment, auth_test_client, monkeypatch
):
    import actidoo_wfe.auth.fastapi as auth_fastapi
    import actidoo_wfe.auth.core as auth_core

    def boom(self, token: dict):
        raise ValueError("invalid aud")

    monkeypatch.setattr(
        auth_fastapi.client,
        "access_token_claims_via_jwks",
        boom.__get__(auth_fastapi.client, type(auth_fastapi.client)),
    )
    monkeypatch.setattr(
        auth_core.client,
        "access_token_claims_via_jwks",
        boom.__get__(auth_core.client, type(auth_core.client)),
    )

    client = auth_test_client
    state, redirect_target = _initiate_login(client)

    callback_url = client.app.url_path_for("auth_login_callback")
    response = client.get(
        callback_url,
        params={"code": oidc_environment["code"], "state": state},
        follow_redirects=False,
    )
    assert response.status_code in (302, 303, 307)
    assert response.headers["location"].endswith(redirect_target)
    session_data = _fetch_session_data(client)
    assert session_data.get("login_fails") == 1


def test_login_callback_provider_error_redirects_to_original_target(
    auth_test_client,
):
    client = auth_test_client
    state, redirect_target = _initiate_login(client, redirect_url="/after-deny")

    callback_url = client.app.url_path_for("auth_login_callback")
    response = client.get(
        callback_url,
        params={"error": "access_denied", "state": state},
        follow_redirects=False,
    )
    assert response.status_code in (302, 303, 307)
    assert response.headers["location"].endswith(redirect_target)
    session_data = _fetch_session_data(client)
    assert session_data.get("login_fails") == 1


def test_login_callback_can_skip_access_token_validation(
    oidc_environment, auth_test_client, monkeypatch
):
    import actidoo_wfe.auth.fastapi as auth_fastapi
    import actidoo_wfe.auth.core as auth_core

    monkeypatch.setattr(settings, "validate_and_parse_access_token", False)

    def unexpected_parse(self, token: dict):
        raise AssertionError("access token parsing should be skipped")

    monkeypatch.setattr(
        auth_fastapi.client,
        "access_token_claims_via_jwks",
        unexpected_parse.__get__(auth_fastapi.client, type(auth_fastapi.client)),
    )
    monkeypatch.setattr(
        auth_core.client,
        "access_token_claims_via_jwks",
        unexpected_parse.__get__(auth_core.client, type(auth_core.client)),
    )

    client = auth_test_client
    state, redirect_target = _initiate_login(client)

    callback_url = client.app.url_path_for("auth_login_callback")
    response = client.get(
        callback_url,
        params={"code": oidc_environment["code"], "state": state},
        follow_redirects=False,
    )
    assert response.status_code in (302, 303, 307)
    assert response.headers["location"] == redirect_target

    login_state_url = client.app.url_path_for("auth_get_login_state")
    login_state_response = client.get(login_state_url, follow_redirects=False)
    assert login_state_response.status_code == 200
    payload = login_state_response.json()
    assert payload["is_logged_in"] is True
    assert payload["username"] == oidc_environment["user_profile"]["preferred_username"]


def test_access_token_validation_accepts_matching_audience(monkeypatch, oidc_environment):
    import actidoo_wfe.auth.core as auth_core

    # Generate a fresh RSA key for this test to sign the access token.
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    public_jwk = JsonWebKey.import_key(public_pem).as_dict(is_private=False)
    public_jwk["kid"] = "aud-test"

    def _fetch_jwk_set(self):
        return {"keys": [public_jwk]}

    monkeypatch.setattr(
        auth_core.client,
        "fetch_jwk_set",
        _fetch_jwk_set.__get__(auth_core.client, type(auth_core.client)),
    )

    metadata = auth_core.client.load_server_metadata()
    now = int(time.time())
    claims = {
        "iss": metadata["issuer"],
        "aud": [settings.oidc_client_id],
        "azp": settings.oidc_client_id,
        "sub": "user-audience",
        "exp": now + 300,
        "iat": now,
    }
    header = {"alg": "RS256", "kid": public_jwk["kid"]}
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    token = jwt.encode(header, claims, private_pem)
    access_token = token.decode("utf-8") if isinstance(token, bytes) else token

    parsed_claims = auth_core.client.access_token_claims_via_jwks(token={"access_token": access_token})
    audience_claim = parsed_claims.get("aud")
    if isinstance(audience_claim, list):
        assert settings.oidc_client_id in audience_claim
    else:
        assert audience_claim == settings.oidc_client_id


def test_auth_fallback_redirects_to_frontend(auth_test_client):
    client = auth_test_client
    fallback_url = client.app.url_path_for("auth_fallback")
    response = client.get(fallback_url, follow_redirects=False)
    assert response.status_code in (302, 303, 307)
    assert response.headers["location"] == settings.frontend_base_url


def test_auth_fallback_can_render_debug_view(auth_test_client, monkeypatch):
    client = auth_test_client
    fallback_url = client.app.url_path_for("auth_fallback")
    monkeypatch.setattr(settings, "auth_debug_token_introspection", False)
    response = client.get(f"{fallback_url}?debug=1")
    assert response.status_code == 200
    assert "Please visit target application" in response.text


def test_initial_login(oidc_environment, auth_test_client):
    client = auth_test_client
    state, redirect_target = _initiate_login(client)

    callback_url = client.app.url_path_for("auth_login_callback")
    response = client.get(
        callback_url,
        params={"code": oidc_environment["code"], "state": state},
        follow_redirects=False,
    )
    assert response.status_code in (302, 303, 307)
    assert response.headers["location"] == redirect_target

    initial_session = _fetch_session_data(client)
    original_token = dict(initial_session.get(SESSION_TOKEN_KEY, {}))
    assert original_token, "expected OIDC token in session"


def test_expired_session_reports_logged_out(oidc_environment, auth_test_client):
    client = auth_test_client
    state, _ = _initiate_login(client)

    callback_url = client.app.url_path_for("auth_login_callback")
    client.get(
        callback_url,
        params={"code": oidc_environment["code"], "state": state},
        follow_redirects=False,
    )

    initial_session = _fetch_session_data(client)
    original_token = dict(initial_session.get(SESSION_TOKEN_KEY, {}))
    original_received_at = original_token.get("received_at")

    session_cookie = client.cookies.get("wfesess")
    assert session_cookie, "missing session cookie"

    with get_db_contextmanager() as db:
        record = db.execute(
            select(SessionModel).where(SessionModel.token == session_cookie)
        ).scalar_one()
        mutated_data = dict(record.data or {})
        mutated_token = dict(mutated_data.get(SESSION_TOKEN_KEY, {}))
        mutated_token["expires_at"] = int(time.time()) - 20
        mutated_data[SESSION_TOKEN_KEY] = mutated_token
        record.data = mutated_data

    login_state_url = client.app.url_path_for("auth_get_login_state")
    login_state_response = client.get(
        login_state_url,
        follow_redirects=False,
    )
    assert login_state_response.status_code == 200
    payload = login_state_response.json()
    assert payload["is_logged_in"] is False

    refreshed_session = _fetch_session_data(client)
    refreshed_token = dict(refreshed_session.get(SESSION_TOKEN_KEY, {}))
    assert refreshed_token["expires_at"] == mutated_token["expires_at"]
    assert refreshed_token.get("received_at") == original_received_at
