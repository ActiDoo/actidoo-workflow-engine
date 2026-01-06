# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

# We are passing roles as permission flags to the frontends
ROLE_TO_LOGIN_STATE_MAP: dict[str, str] = {
    "can_access_wf": "wf-user",
    "can_access_wf_admin": "wf-admin",
} # please also update in .schema

SESSION_IDP_CLAIMS_KEY = "idp_user_claims"
SESSION_TOKEN_KEY = "idp_token"