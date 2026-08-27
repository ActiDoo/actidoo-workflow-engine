# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

from fastapi import Request

import actidoo_wfe.wf.service_user as service_user
from actidoo_wfe.database import get_db_contextmanager
from actidoo_wfe.helpers.http import HTTPException
from actidoo_wfe.i18n import extract_primary_locale
from actidoo_wfe.settings import settings
from actidoo_wfe.wf.constants import BFF_CLIENT_VERSION_HEADER, BFF_CONTRACT_VERSION
from actidoo_wfe.wf.cross_context.imports import get_login_state
from actidoo_wfe.wf.exceptions import ClientVersionMismatchError, DataModelNotFoundError
from actidoo_wfe.wf.registry_data_model import DataModelDescriptor, data_model_registry


def require_matching_client_version(request: Request):
    """Refuse a bundle whose BFF contract version is not exactly ours (ADR 011).

    A stale tab that survived a deploy would otherwise keep submitting against a
    contract it does not speak - for dynamic lists that means silently
    index-merged rows (ADR 010). Listed FIRST in the BFF routers' dependencies so
    it answers before the role check: a stale tab whose session also expired must
    see the version error, not a 401 that sends it into a login redirect.
    """
    raw = request.headers.get(BFF_CLIENT_VERSION_HEADER)
    try:
        client_version = int(raw)
    except (TypeError, ValueError):
        raise ClientVersionMismatchError(client_version=None)

    if client_version != BFF_CONTRACT_VERSION:
        raise ClientVersionMismatchError(client_version=client_version)


def get_user(request: Request):
    login_state = get_login_state(request=request)
    idp_user_id = login_state.idp_user_id
    email = login_state.email
    username = login_state.email
    first_name = login_state.first_name
    last_name = login_state.last_name

    assert idp_user_id is not None
    assert email is not None
    assert username is not None

    first_name = first_name or ""
    last_name = last_name or ""

    with get_db_contextmanager() as db:
        header = request.headers.get("accept-language", "")
        primary = extract_primary_locale(header) or settings.default_locale
        user = service_user.upsert_user(
            db=db,
            idp_user_id=idp_user_id,
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            is_service_user=False,
            initial_locale=primary,
        )

    return user


def get_data_model(model_name: str) -> DataModelDescriptor:
    """Resolve a registered data model or raise 404.

    Doubles as a FastAPI dependency: on the ``/{model_name}/...`` routes it binds
    the path parameter, so the routes receive the resolved data model directly.
    Routes whose model name arrives in the request body call it explicitly.
    """
    try:
        return data_model_registry.get(model_name)
    except DataModelNotFoundError:
        raise HTTPException(status_code=404, detail=f"Data model '{model_name}' not found")
