# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

import logging

from actidoo_wfe.database import SessionLocal, setup_db
from actidoo_wfe.settings import settings
from actidoo_wfe.wf.tests.helpers.client import Client

log: logging.Logger = logging.getLogger(__name__)

setup_db(settings=settings)

def mock_service_user():
    from actidoo_wfe.wf.service_user import upsert_user
    svc_user = upsert_user(
        db=SessionLocal(),
        idp_user_id="123",
        username="test_user",
        email="",
        first_name="Service",
        last_name="User",
        is_service_user=True
    )
    return svc_user

def test_send_message(db_engine_ctx,):
    from actidoo_wfe.wf.api.api_schema import SendMessageResponse
    from actidoo_wfe.wf.api.deps import dep_require_service_user

    with db_engine_ctx():
        client = Client()
        client.root_client.app.dependency_overrides[dep_require_service_user] = mock_service_user

        status, json_resp = client.post(
            name="api_v1_send_message",
            json={"message_name": "WorkflowTest", "correlation_key": "", "data": {}},
            cls=SendMessageResponse,
        )

        assert status == 200
