# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

from typing import Any, Dict, Iterable, List, Optional

from fastapi import Request

from actidoo_wfe.settings import settings
from actidoo_wfe.auth.constants import SESSION_IDP_CLAIMS_KEY

def set_claims(request: Request, claims: Dict[str, Any]):
    request.session[SESSION_IDP_CLAIMS_KEY] = claims
    
def get_claims(request: Request) -> Dict[str, Any]:
    claims = request.session.get(SESSION_IDP_CLAIMS_KEY)
    if isinstance(claims, dict):
        return dict(claims)
    return {}

def _get_from_claims(claims: Dict[str, Any], csv_keys: str) -> Optional[str]:
    for key in [entry.strip() for entry in csv_keys.split(",") if entry.strip()]:
        value = claims.get(key)
        if isinstance(value, str) and value:
            return value
    return None

def _split_full_name(full_name: str) -> tuple[Optional[str], Optional[str]]:
    parts = [part for part in full_name.split(" ") if part]
    if not parts:
        return None, None
    if len(parts) == 1:
        return parts[0], None
    return parts[0], " ".join(parts[1:])

def get_username(request: Request) -> Optional[str]:
    claims = get_claims(request)
    value = _get_from_claims(claims, settings.oidc_username_claims)
    if value is None:
        value = _get_from_claims(claims, settings.oidc_email_claims)
    return value

def get_email(request: Request) -> Optional[str]:
    return _get_from_claims(get_claims(request), settings.oidc_email_claims)

def get_first_name(request: Request) -> Optional[str]:
    claims = get_claims(request)
    value = _get_from_claims(claims, settings.oidc_first_name_claims)
    if value:
        return value
    full_name = _get_from_claims(claims, settings.oidc_full_name_claims)
    if full_name:
        first, _ = _split_full_name(full_name)
        return first
    return None

def get_last_name(request: Request) -> Optional[str]:
    claims = get_claims(request)
    value = _get_from_claims(claims, settings.oidc_last_name_claims)
    if value:
        return value
    full_name = _get_from_claims(claims, settings.oidc_full_name_claims)
    if full_name:
        _, last = _split_full_name(full_name)
        return last
    return None

def get_idp_user_id(request: Request) -> Optional[str]:
    return _get_from_claims(get_claims(request), settings.oidc_user_id_claims)

def _iter_dict_paths(obj: Any, parts: List[str]) -> Iterable[Any]:
    if not parts:
        yield obj
        return
    head, *tail = parts
    if isinstance(obj, dict):
        if head == "*":
            for value in obj.values():
                yield from _iter_dict_paths(value, tail)
        elif head in obj:
            yield from _iter_dict_paths(obj[head], tail)
    elif isinstance(obj, list):
        try:
            index = int(head)
        except ValueError:
            for value in obj:
                yield from _iter_dict_paths(value, [head] + tail)
        else:
            if 0 <= index < len(obj):
                yield from _iter_dict_paths(obj[index], tail)

def extract_roles(claims: Dict[str, Any]) -> List[str]:
    roles: List[str] = []
    formatted_paths = settings.oidc_roles_claim_paths.replace("{client_id}", settings.oidc_client_id)
    for raw in [p.strip() for p in formatted_paths.split(",") if p.strip()]:
        parts = raw.split(".")
        for value in _iter_dict_paths(claims, parts):
            if isinstance(value, str) and value:
                roles.append(value)
            elif isinstance(value, list):
                roles.extend(str(item) for item in value if item)
    return sorted(set(roles))

def get_roles(request: Request) -> List[str]:
    return extract_roles(get_claims(request))
