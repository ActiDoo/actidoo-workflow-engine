
import pytest

from fastapi import Request
from contextlib import contextmanager
from fastapi import Request

from actidoo_wfe.wf.cross_context.imports import require_realm_role
from actidoo_wfe.wf.bff.deps import get_user as bff_get_user

@contextmanager
def override_get_user(client, user):
    def override_get_user(_: Request):
        return user

    app = client.root_client.app
    app.dependency_overrides[bff_get_user] = override_get_user

    try:
        yield
    finally:
        client.root_client.app.dependency_overrides.pop(bff_get_user, None)

    app.dependency_overrides.pop(bff_get_user, None)

@contextmanager
def disable_role_check(client):
    def override_realm_role(_: Request):
        return True

    app = client.root_client.app
    
    app.dependency_overrides[require_realm_role("wf-user")] = override_realm_role
    app.dependency_overrides[require_realm_role("wf-admin")] = override_realm_role

    try:
        yield
    finally:
        app.dependency_overrides.pop(require_realm_role("wf-user"), None)
        app.dependency_overrides.pop(require_realm_role("wf-admin"), None)
