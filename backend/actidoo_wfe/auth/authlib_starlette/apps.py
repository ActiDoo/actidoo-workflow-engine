# starlette_fastapi/apps.py
import time
from typing import Any, Dict, Optional

import urllib.parse
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response

from authlib.integrations.base_client import BaseApp
from authlib.integrations.base_client import OAuth2Mixin
from authlib.integrations.base_client import OAuthError
from authlib.integrations.base_client import OpenIDMixin
from authlib.integrations.requests_client import OAuth2Session
from authlib.jose import JsonWebToken

class StarletteOAuth2App(OAuth2Mixin, OpenIDMixin, BaseApp):
    client_cls = OAuth2Session

    # ---- Redirect helpers
    def redirect(self, url: str, status_code: int = 302) -> Response:
        return RedirectResponse(url, status_code=status_code)

    # ---- State helpers to mirror flask.g
    def get_state(self, request: Request) -> Any:
        return request.state

    def _get_session(self, request: Request) -> Dict[str, Any]:  # starlette session dict
        try:
            return request.session  # type: ignore[attr-defined]
        except Exception as e:  # pragma: no cover
            raise RuntimeError(
                "SessionMiddleware not configured. Add it to your Starlette/FastAPI app."
            ) from e


    # Public API mirrors Flask version. `request` must be passed explicitly.

    def authorize_redirect(self, request: Request, redirect_uri: str, **kwargs):
        session = self._get_session(request)
        rv = self.create_authorization_url(redirect_uri=redirect_uri, **kwargs)
        url = rv.get("url")
        #state = rv.get("state")
        #nonce = rv.get("nonce")
        #code_verifier = rv.get("code_verifier")
        session[self.name + ":state"] = rv
        return self.redirect(url)

    def authorize_access_token(
        self,
        request: Request,
        redirect_uri: str,
        claims_options: Optional[Dict[str, Any]] = None,
        claims_cls: Optional[Any] = None,
        **kwargs,
    ):
        session = self._get_session(request)
        state_data = session.pop(self.name + ":state", None)
        if not state_data:
            raise OAuthError("Missing state in session")

        # Validate state
        state = request.query_params.get("state")
        if not state or state != state_data.get("state"):
            raise OAuthError("State mismatch")

        # Exchange code
        params: Dict[str, Any] = {"redirect_uri": redirect_uri, "authorization_response": str(request.url)}
        params = {k: v for k, v in params.items() if v is not None}
        leeway = kwargs.pop("leeway", 120)
        token = self.fetch_access_token(**params, **kwargs, code_verifier = state_data.get("code_verifier"))
        self.token = token

        # OIDC userinfo if present
        if "id_token" in token and "nonce" in state_data:
            userinfo = self.parse_id_token(
                token,
                nonce=state_data["nonce"],
                claims_options=claims_options,
                claims_cls=claims_cls,
                leeway=leeway,
            )
            token["userinfo"] = userinfo
        return token

    def make_logout_url(self, redirect_uri: str, id_token: str | None = None) -> str:
        meta = self.load_server_metadata()
        end_session = meta.get("end_session_endpoint")
        if not end_session:
            raise RuntimeError("Provider has no end_session_endpoint")

        params = {"post_logout_redirect_uri": redirect_uri}

        if id_token:
            params["id_token_hint"] = id_token

        params["client_id"] = self.client_id

        return f"{end_session}?{urllib.parse.urlencode(params)}"
    
    def access_token_claims_via_jwks(self, token: dict) -> Dict[str, Any]:
        at = token.get("access_token")
        if not at or at.count(".") != 2:
            return {}
        
        jwks = self.fetch_jwk_set() 
        jwt = JsonWebToken(["RS256","RS384","RS512","ES256","ES384","ES512","PS256","PS384","PS512"])
        claims = jwt.decode(at, jwks)  # verify signature
        claims.validate()

        meta = self.load_server_metadata()

        issuer =meta["issuer"]
        if claims.get("iss") != issuer:
            raise ValueError("invalid issuer")
        
        aud = claims.get("aud")
        if isinstance(aud, str):
            aud = [aud]

        if isinstance(aud, list) and len(aud)>0:
            raise ValueError("invalid aud")

        if aud is None or (isinstance(aud, list) and len(aud)==0):
            # this is an exception for keycloak. if only realm roles are assigned, the aud claim is missing.
            if claims["azp"] != self.client_id:
                raise ValueError("invalid authorized party")

        if claims.get("azp") and claims["azp"] != self.client_id:
            raise ValueError("invalid authorized party")
        
        if time.time() > claims["exp"]:
            raise ValueError("token expired")

        return dict(claims)