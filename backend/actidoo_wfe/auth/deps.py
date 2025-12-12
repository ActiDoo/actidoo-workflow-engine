from functools import lru_cache
from fastapi import HTTPException, Request

from actidoo_wfe.auth.core import (
    get_login_state,
    has_role,
)


def require_authenticated(request: Request):
    """Ensure the current session is authenticated, otherwise raise 401."""
    
    loginstate = get_login_state(request=request)

    if not loginstate.is_logged_in:
        raise HTTPException(status_code=401, detail="Not logged in")
    

@lru_cache(maxsize=None)
def require_realm_role(role: str):
    """Ensure the user is authenticated and holds the given role."""

    def require_realm_role_dependency(request: Request):
        require_authenticated(request=request)

        if not has_role(request=request, role=role):
            raise HTTPException(status_code=403, detail="Forbidden")

    return require_realm_role_dependency
