# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

import logging

from actidoo_wfe.database import SessionLocal, setup_db
from actidoo_wfe.settings import settings
from actidoo_wfe.wf.bff.bff_user_schema import WorkflowSpecResponse
from actidoo_wfe.wf.tests.helpers.client import Client
from actidoo_wfe.wf.tests.helpers.overrides import disable_role_check, override_get_user

log: logging.Logger = logging.getLogger(__name__)

setup_db(settings=settings)

def mock_user():
    from actidoo_wfe.wf.service_user import upsert_user
    mockuser = upsert_user(
        db=SessionLocal(),
        idp_user_id="321",
        username="test_user_mock",
        email="",
        first_name="Mock",
        last_name="User",
        is_service_user=False
    )
    return mockuser


def test_refresh_get_workflow_spec(db_engine_ctx):
    with db_engine_ctx():
        client = Client()
        user = mock_user()
        
        with override_get_user(client=client, user=user), disable_role_check(client):
            status, json_resp = client.post(
                name="refresh_get_workflow_spec",
                json={"name": "TestFlowBasicStart"},
                cls=WorkflowSpecResponse,
            )

        assert status == 200
        assert len(json_resp.files) > 0
