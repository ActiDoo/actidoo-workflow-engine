# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

from typing import Annotated

from fastapi import Depends

import actidoo_wfe.wf.service_user as service_user
from actidoo_wfe.database import get_db_contextmanager
from actidoo_wfe.helpers.oauth_bearer import TokenInformation, oauth_bearer_require_client_role
from actidoo_wfe.settings import settings


def get_service_user(require_additional_client_roles=[]):
    require_client_role = "wf-api"

    def dep_get_user(token_information: Annotated[TokenInformation, Depends(oauth_bearer_require_client_role(require_client_role))]):
        idp_user_id = token_information.sub
        username = token_information.preferred_username or token_information.sub

        if require_additional_client_roles:
            for role in require_additional_client_roles:
                oauth_bearer_require_client_role(role=role)(token_information=token_information)

        assert idp_user_id is not None
        assert username is not None

        with get_db_contextmanager() as db:
            primary = settings.default_locale
            user = service_user.upsert_user(
                db=db,
                idp_user_id=idp_user_id,
                username=username,
                email=None,
                first_name=None,
                last_name=None,
                is_service_user=True,
                initial_locale=primary,
            )

        return user

    return dep_get_user


dep_require_service_user = get_service_user()
