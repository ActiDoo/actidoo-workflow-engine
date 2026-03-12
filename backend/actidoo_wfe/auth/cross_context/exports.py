# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

from actidoo_wfe.auth.claims import get_claims
from actidoo_wfe.auth.core import get_token_from_session
from actidoo_wfe.auth.deps import require_authenticated, require_realm_role
from actidoo_wfe.auth.hooks import get_login_state, login_hook
from actidoo_wfe.auth.schema import LoginStateSchema

__all__ = [
    "LoginStateSchema",
    "get_claims",
    "get_login_state",
    "get_token_from_session",
    "login_hook",
    "require_authenticated",
    "require_realm_role",
]
