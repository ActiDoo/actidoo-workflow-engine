import dataclasses
import logging
import re
import time
from typing import Annotated, Any, Optional, Sequence

import httpx
from fastapi import Depends, HTTPException, Request, Security
from fastapi.openapi.models import OAuthFlowClientCredentials, OAuthFlows
from fastapi.security import OAuth2
from fastapi.security.utils import get_authorization_scheme_param

from actidoo_wfe.settings import settings

logger = logging.getLogger(__name__)




def _resolve_path(payload: Any, path: str) -> Any:
    """Resolve a dotted path inside a nested mapping structure."""

    current = payload
    for part in path.split("."):
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def coerce_to_list(value: Any) -> list[str]:
    """Convert common claim value shapes to a list of strings."""

    if value is None:
        return []
    if isinstance(value, str):
        items = [item for item in re.split(r"[,\s]+", value) if item]
        return items
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value if item not in (None, "")]
    return [str(value)]

def extract_first_list(payload: dict[str, Any], paths: Sequence[str]) -> list[str]:
    """Return the first non-empty list resolved via the given claim paths."""

    for path in paths:
        value = _resolve_path(payload, path)
        values = coerce_to_list(value)
        if values:
            return values
    return []

def get_token_endpoint():
    token_endpoint = settings.oauth_bearer_token_endpoint

    if token_endpoint.endswith(".well-known/openid-configuration"):
        # an OIDC configuration url is given, lets fetch the introspection endpoint
        try:
            token_endpoint = httpx.get(url=token_endpoint).json().get("token_endpoint")
        except Exception:
            logger.exception("OAUTH_BEARER_TOKEN_ENDPOINT has been set to an openid-configuration endpoint, but the token_endpoint could not be retrieved from it")
        
        if not token_endpoint:
            logger.exception("OAUTH_BEARER_TOKEN_ENDPOINT has been set to an openid-configuration endpoint, but the token_endpoint could not be retrieved from it")

    #TODO: Cache result for x minutes

    return token_endpoint


def get_introspection_endpoint():
    introspection_endpoint = settings.oauth_bearer_introspection_endpoint

    if introspection_endpoint.endswith(".well-known/openid-configuration"):
        # an OIDC configuration url is given, lets fetch the introspection endpoint
        try:
            introspection_endpoint = httpx.get(url=introspection_endpoint).json().get("introspection_endpoint")
        except Exception:
            logger.exception("OAUTH_BEARER_INTROSPECTION_ENDPOINT has been set to an openid-configuration endpoint, but the introspection_endpoint could not be retrieved from it")
        
        if not introspection_endpoint:
            logger.exception("OAUTH_BEARER_INTROSPECTION_ENDPOINT has been set to an openid-configuration endpoint, but the introspection_endpoint could not be retrieved from it")

    #TODO: Cache result for x minutes

    return introspection_endpoint


class OAuth2ClientCredentialsBearer(OAuth2):
    def __init__(
        self,
        tokenUrl: str,
        scheme_name: Optional[str] = None,
        description: Optional[str] = None,
        auto_error: bool = True,
    ):
        flows = OAuthFlows(clientCredentials=OAuthFlowClientCredentials(tokenUrl=tokenUrl))
        super().__init__(
            flows=flows,
            scheme_name=scheme_name,
            description=description,
            auto_error=auto_error,
        )

    async def __call__(self, request: Request) -> Optional[str]:
        authorization = request.headers.get("Authorization")
        scheme, param = get_authorization_scheme_param(authorization)
        if not authorization or scheme.lower() != "bearer":
            if self.auto_error:
                raise HTTPException(
                    status_code=401,
                    detail="Not authenticated",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            else:
                return None
        return param


@dataclasses.dataclass
class TokenInformation:
    sub: str
    preferred_username: Optional[str]
    aud: str|list[str]
    roles: list[str]
    resource_roles: dict[str, list[str]]
    raw: dict[str, Any]


# Function to validate the token using the introspection endpoint
async def oauth_bearer_validate_token(token: Annotated[str, Security(OAuth2ClientCredentialsBearer(tokenUrl=get_token_endpoint()))]):
    async with httpx.AsyncClient() as client:
        # TODO: Cache this for the given token for x minutes / seconds (but then always check exp)
        url = get_introspection_endpoint()
        introspection_response = await client.post(
            url,
            data={"token": token},
            auth=(settings.oauth_bearer_client_id, settings.oauth_bearer_client_secret)  # Replace with your client credentials
        )

        introspection_data = introspection_response.json()

        if not introspection_data.get("active"):
            raise HTTPException(status_code=401, detail="Token is not valid")

        # Validate token audience
        token_audience = introspection_data.get("aud")
        if not (
                token_audience == settings.oauth_bearer_client_id
            or (isinstance(token_audience, list) and settings.oauth_bearer_client_id in token_audience)
        ):
            raise HTTPException(status_code=401, detail="Token audience is invalid")
        
        # Validate token expiration time (exp claim)
        token_expiration = introspection_data.get("exp")
        current_time = int(time.time())
        if token_expiration is not None and token_expiration < current_time:
            raise HTTPException(status_code=401, detail="Token has expired")
        
        preferred_username = introspection_data.get("preferred_username") or introspection_data.get("username")
        role_claim_paths = [
            path.replace("{client_id}", settings.oauth_bearer_client_id)
            for path in settings.oauth_bearer_role_claim_paths
        ]
        roles = extract_first_list(introspection_data, role_claim_paths)
        resource_roles: dict[str, list[str]] = {}
        for client, meta in (introspection_data.get("resource_access") or {}).items():
            roles_for_client = coerce_to_list(meta.get("roles"))
            if roles_for_client:
                resource_roles[client] = roles_for_client

        return TokenInformation(
            sub=introspection_data["sub"],
            preferred_username=preferred_username,
            aud=introspection_data["aud"],
            roles=roles,
            resource_roles=resource_roles,
            raw=introspection_data,
        )
    

def oauth_bearer_require_client_role(role: str, client_id: str=settings.oauth_bearer_client_id):

    def oauth_bearer_require_client_role_dependency(token_information: Annotated[TokenInformation, Depends(oauth_bearer_validate_token)]) -> TokenInformation:
        client_roles = token_information.resource_roles.get(client_id)
        if client_roles is not None:
            has_role = role in client_roles
        else:
            has_role = role in token_information.roles

        if not has_role:
            logger.info(f'"{token_information.sub}" does not have required role "{role}" for client_id "{client_id}"')
            raise HTTPException(status_code=403, detail="Token does not have the required role")
        
        return token_information
        
    return oauth_bearer_require_client_role_dependency


def oauth_bearer_require_realm_role(role: str):

    def oauth_bearer_require_realm_role_dependency(token_information: Annotated[TokenInformation, Depends(oauth_bearer_validate_token)]) -> TokenInformation:
        if role not in token_information.roles:
            logger.info(f'"{token_information.sub}" does not have required realm role "{role}"')
            raise HTTPException(status_code=403, detail="Token does not have the required role")
        return token_information
        
    return oauth_bearer_require_realm_role_dependency
