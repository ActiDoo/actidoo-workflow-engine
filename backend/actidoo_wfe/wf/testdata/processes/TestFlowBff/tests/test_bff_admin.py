# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

import base64
import logging
from datetime import timedelta
from pathlib import Path

from actidoo_wfe.database import SessionLocal, setup_db
from actidoo_wfe.helpers.time import dt_now_naive
from actidoo_wfe.settings import settings
from actidoo_wfe.wf import service_application
from actidoo_wfe.wf.bff import bff_admin
from actidoo_wfe.wf.bff.bff_admin_schema import (
    CancelWorkflowInstanceResponse,
    GetAllTasksResponse,
    GetAllUsersResponse,
    GetAllWorkflowInstancesResponse,
    GetSingleTaskResponse,
    GetSystemInformationResponse,
    GetUserDetailResponse,
    SearchUsersResponse,
)
from actidoo_wfe.wf.tests.helpers.client import Client
from actidoo_wfe.wf.tests.helpers.overrides import disable_role_check, override_get_user
from actidoo_wfe.wf.tests.helpers.workflow_dummy import WorkflowDummy
from actidoo_wfe.wf.types import ReducedWorkflowInstanceResponse, WorkflowStateResponse

log: logging.Logger = logging.getLogger(__name__)

setup_db(settings=settings)

WF_NAME = "TestFlowBff"
FORM1_DATA_MIN = {"required_text": "ok", "short_code": "abc", "trigger_error": False}
FORM1_DATA_TRIGGER_ERROR = {"required_text": "ok", "short_code": "abc", "trigger_error": True}
FORM2_DATA = {"confirmation": "done"}


def _png_attachment():
    png_path = Path(__file__).parent.parent.parent / "TestFlowFormUploads" / "tests" / "test.png"
    encoded = base64.b64encode(png_path.read_bytes()).decode("utf-8")
    return {"datauri": f"data:image/png;name=test.png;base64,{encoded}"}


def _create_completed_workflow(db):
    """Start TestFlowBff and submit both forms so the instance ends in the normal end state."""
    workflow = WorkflowDummy(
        db_session=db,
        users_with_roles={"admin": ["wf-admin"], "initiator": ["wf-user"]},
        workflow_name=WF_NAME,
        start_user="initiator",
    )
    workflow.user("initiator").submit(
        task_data=FORM1_DATA_MIN,
        workflow_instance_id=workflow.workflow_instance_id,
    )
    workflow.user("initiator").submit(
        task_data=FORM2_DATA,
        workflow_instance_id=workflow.workflow_instance_id,
    )
    return workflow


# ---------------------------------------------------------------------------
# task / workflow listings
# ---------------------------------------------------------------------------


def test_admin_get_all_tasks(db_engine_ctx):
    with db_engine_ctx():
        db = SessionLocal()
        workflow = _create_completed_workflow(db=db)
        client = Client()

        with override_get_user(client=client, user=workflow.user("admin").user), disable_role_check(client):
            status, json_resp = client.post(
                name="bff_admin_get_all_tasks",
                json={},
                cls=GetAllTasksResponse,
            )

        assert len(json_resp.ITEMS) > 0
        assert any(t.completed_at is not None for t in json_resp.ITEMS)


def test_admin_get_all_workflow_instances(db_engine_ctx):
    with db_engine_ctx():
        db = SessionLocal()
        workflow = _create_completed_workflow(db=db)
        client = Client()

        with override_get_user(client=client, user=workflow.user("admin").user), disable_role_check(client):
            status, json_resp = client.post(
                name="bff_admin_get_all_workflow_instances",
                json={},
                cls=GetAllWorkflowInstancesResponse,
            )

        assert len(json_resp.ITEMS) > 0


def test_cancel_workflow(db_engine_ctx):
    with db_engine_ctx():
        db = SessionLocal()
        workflow = WorkflowDummy(
            db_session=db,
            users_with_roles={"initiator": ["wf-user"], "admin": ["wf-admin"]},
            workflow_name=WF_NAME,
            start_user="initiator",
        )

        assert workflow.workflow_instance_id is not None

        client = Client()
        with override_get_user(client=client, user=workflow.user("admin").user), disable_role_check(client):
            status, json_resp = client.post(
                name="bff_admin_cancel_workflow_instance",
                json={"workflow_instance_id": str(workflow.workflow_instance_id)},
                cls=CancelWorkflowInstanceResponse,
            )

        assert status == 200

        with override_get_user(client=client, user=workflow.user("admin").user), disable_role_check(client):
            status, json_resp = client.post(
                name="bff_admin_get_all_tasks",
                json={},
                cls=GetAllTasksResponse,
            )

        assert len(json_resp.ITEMS) > 0
        assert any(x.state_cancelled for x in json_resp.ITEMS)


def test_admin_assign(db_engine_ctx):
    with db_engine_ctx():
        db = SessionLocal()
        workflow = WorkflowDummy(
            db_session=db,
            users_with_roles={
                "admin": ["wf-admin"],
                "initiator": ["wf-user"],
                "reviewer": ["wf-user"],
            },
            workflow_name=WF_NAME,
            start_user="initiator",
        )

        task = workflow.user("initiator").get_usertasks(workflow.workflow_instance_id, 1)
        workflow.user("initiator").assign_task(task_id=task[0].id)

        client = Client()
        with override_get_user(client=client, user=workflow.user("admin").user), disable_role_check(client):
            status, json_resp = client.post(
                name="bff_admin_unassign_task",
                json={"task_id": str(task[0].id)},
                cls=GetSingleTaskResponse,
            )

        assert json_resp.task.assigned_user is None

        with override_get_user(client=client, user=workflow.user("admin").user), disable_role_check(client):
            status, json_resp = client.post(
                name="bff_admin_assign_task",
                json={
                    "task_id": str(task[0].id),
                    "user_id": str(workflow.user("initiator").user.id),
                },
                cls=GetSingleTaskResponse,
            )

        assert json_resp.task.assigned_user is not None
        assert str(json_resp.task.assigned_user.id) == str(workflow.user("initiator").user.id)


def test_admin_user_listing_and_delegations(db_engine_ctx):
    with db_engine_ctx():
        db = SessionLocal()
        dummy = WorkflowDummy(
            db_session=db,
            users_with_roles={
                "admin": ["wf-admin"],
                "principal": ["wf-user"],
                "delegate": ["wf-user"],
            },
        )

        admin = dummy.user("admin").user
        principal = dummy.user("principal").user
        delegate = dummy.user("delegate").user

        table_params = bff_admin.AdminWorkflowUsersBffTableQuerySchema.parse_obj({})
        users = service_application.bff_admin_get_all_users(
            db=db,
            user_id=admin.id,
            bff_table_request_params=table_params,
        )
        assert any(u["id"] == principal.id for u in users.ITEMS)

        detail = service_application.admin_get_user_detail(
            db=db,
            admin_user_id=admin.id,
            target_user_id=principal.id,
        )
        assert detail["user"]["id"] == principal.id

        updated_detail = service_application.admin_set_user_delegations(
            db=db,
            admin_user_id=admin.id,
            principal_user_id=principal.id,
            delegations=[(delegate.id, dt_now_naive() + timedelta(days=1))],
        )

        assert any(d["delegate"]["id"] == delegate.id for d in updated_detail["delegations"])

        filtered_params = bff_admin.AdminWorkflowUsersBffTableQuerySchema.parse_obj(
            {"f_roles": "wf-admin"},
        )
        filtered_users = service_application.bff_admin_get_all_users(
            db=db,
            user_id=admin.id,
            bff_table_request_params=filtered_params,
        )
        assert any(u["id"] == admin.id for u in filtered_users.ITEMS)
        assert all("wf-admin" in u["roles"] for u in filtered_users.ITEMS)


# ---------------------------------------------------------------------------
# new endpoint-level tests
# ---------------------------------------------------------------------------


def test_admin_get_statistic_information(db_engine_ctx):
    with db_engine_ctx():
        db = SessionLocal()
        workflow = _create_completed_workflow(db=db)
        client = Client()

        with override_get_user(client=client, user=workflow.user("admin").user), disable_role_check(client):
            status, _ = client.post(
                name="bff_admin_get_statistics_information",
                json={},
                cls=ReducedWorkflowInstanceResponse,
            )

        assert status == 200


def test_admin_get_all_users_endpoint(db_engine_ctx):
    with db_engine_ctx():
        db = SessionLocal()
        dummy = WorkflowDummy(
            db_session=db,
            users_with_roles={
                "admin": ["wf-admin"],
                "alice": ["wf-user"],
                "bob": ["wf-user"],
            },
        )
        client = Client()

        with override_get_user(client=client, user=dummy.user("admin").user), disable_role_check(client):
            status, json_resp = client.post(
                name="bff_admin_get_all_users",
                json={},
                cls=GetAllUsersResponse,
            )

        assert status == 200
        ids = {u.id for u in json_resp.ITEMS}
        assert dummy.user("alice").user.id in ids
        assert dummy.user("bob").user.id in ids


def test_admin_get_user_detail(db_engine_ctx):
    with db_engine_ctx():
        db = SessionLocal()
        dummy = WorkflowDummy(
            db_session=db,
            users_with_roles={
                "admin": ["wf-admin"],
                "principal": ["wf-user"],
            },
        )
        client = Client()

        with override_get_user(client=client, user=dummy.user("admin").user), disable_role_check(client):
            status, json_resp = client.post(
                name="bff_admin_get_user_detail",
                json={"user_id": str(dummy.user("principal").user.id)},
                cls=GetUserDetailResponse,
            )

        assert status == 200
        assert json_resp.user.id == dummy.user("principal").user.id


def test_admin_set_user_delegations_endpoint(db_engine_ctx):
    with db_engine_ctx():
        db = SessionLocal()
        dummy = WorkflowDummy(
            db_session=db,
            users_with_roles={
                "admin": ["wf-admin"],
                "principal": ["wf-user"],
                "delegate": ["wf-user"],
            },
        )
        client = Client()

        valid_until = (dt_now_naive() + timedelta(days=1)).isoformat()
        with override_get_user(client=client, user=dummy.user("admin").user), disable_role_check(client):
            status, json_resp = client.post(
                name="bff_admin_set_user_delegations",
                json={
                    "user_id": str(dummy.user("principal").user.id),
                    "delegations": [
                        {
                            "delegate_user_id": str(dummy.user("delegate").user.id),
                            "valid_until": valid_until,
                        },
                    ],
                },
                cls=GetUserDetailResponse,
            )

        assert status == 200
        assert any(d.delegate.id == dummy.user("delegate").user.id for d in json_resp.delegations)


def test_admin_replace_task_data(db_engine_ctx):
    with db_engine_ctx():
        db = SessionLocal()
        workflow = WorkflowDummy(
            db_session=db,
            users_with_roles={"admin": ["wf-admin"], "initiator": ["wf-user"]},
            workflow_name=WF_NAME,
            start_user="initiator",
        )
        task = workflow.user("initiator").get_usertasks(workflow.workflow_instance_id, 1)[0]

        client = Client()
        with override_get_user(client=client, user=workflow.user("admin").user), disable_role_check(client):
            status, json_resp = client.post(
                name="bff_admin_replace_task_data",
                json={"task_id": str(task.id), "data": {"required_text": "replaced", "short_code": "xy"}},
                cls=GetSingleTaskResponse,
            )

        assert status == 200
        assert json_resp.task.data == {"required_text": "replaced", "short_code": "xy"}


def test_admin_execute_erroneous_task(db_engine_ctx):
    with db_engine_ctx():
        db = SessionLocal()
        workflow = WorkflowDummy(
            db_session=db,
            users_with_roles={"admin": ["wf-admin"], "initiator": ["wf-user"]},
            workflow_name=WF_NAME,
            start_user="initiator",
        )
        workflow.user("initiator").submit(
            task_data=FORM1_DATA_TRIGGER_ERROR,
            workflow_instance_id=workflow.workflow_instance_id,
        )

        client = Client()
        with override_get_user(client=client, user=workflow.user("admin").user), disable_role_check(client):
            status, all_tasks = client.post(
                name="bff_admin_get_all_tasks",
                json={"f_state_error": True},
                cls=GetAllTasksResponse,
            )
            assert status == 200
            erroneous = [t for t in all_tasks.ITEMS if t.state_error]
            assert erroneous, "expected a task in state_error"

            status, _ = client.post(
                name="bff_admin_execute_erroneous_task",
                json={"task_id": str(erroneous[0].id)},
                cls=GetAllTasksResponse,
            )

        assert status == 200


def test_admin_download_attachment(db_engine_ctx):
    with db_engine_ctx():
        db = SessionLocal()
        workflow = WorkflowDummy(
            db_session=db,
            users_with_roles={"admin": ["wf-admin"], "initiator": ["wf-user"]},
            workflow_name=WF_NAME,
            start_user="initiator",
        )
        workflow.user("initiator").submit(
            task_data={**FORM1_DATA_MIN, "attachment": _png_attachment()},
            workflow_instance_id=workflow.workflow_instance_id,
        )

        attachments = service_application.find_all_workflow_attachments(
            db=db, workflow_instance_id=workflow.workflow_instance_id,
        )
        assert attachments, "expected at least one attachment after upload"
        tasks = service_application.get_usertasks_for_user_id(
            db=db, user_id=workflow.user("initiator").user.id,
            workflow_instance_id=workflow.workflow_instance_id, state="completed",
        )
        task_id = tasks[0].id

        client = Client()
        with override_get_user(client=client, user=workflow.user("admin").user), disable_role_check(client):
            url = client.root_client.app.url_path_for("bff_admin_download_attachment")
            response = client.root_client.post(
                url, json={"task_id": str(task_id), "hash": attachments[0].hash},
            )

        assert response.status_code == 200
        assert "content-disposition" in {k.lower() for k in response.headers}


def test_admin_search_wf_users(db_engine_ctx):
    with db_engine_ctx():
        db = SessionLocal()
        dummy = WorkflowDummy(
            db_session=db,
            users_with_roles={"admin": ["wf-admin"], "searched": ["wf-user"]},
        )
        client = Client()

        with override_get_user(client=client, user=dummy.user("admin").user), disable_role_check(client):
            status, json_resp = client.post(
                name="bff_admin_search_wf_users",
                json={"search": "searched"},
                cls=SearchUsersResponse,
            )

        assert status == 200
        assert any(o.value == dummy.user("searched").user.id for o in json_resp.options)


def test_admin_unassign_task(db_engine_ctx):
    with db_engine_ctx():
        db = SessionLocal()
        workflow = WorkflowDummy(
            db_session=db,
            users_with_roles={"admin": ["wf-admin"], "initiator": ["wf-user"]},
            workflow_name=WF_NAME,
            start_user="initiator",
        )
        task = workflow.user("initiator").get_usertasks(workflow.workflow_instance_id, 1)[0]
        workflow.user("initiator").assign_task(task_id=task.id)

        client = Client()
        with override_get_user(client=client, user=workflow.user("admin").user), disable_role_check(client):
            status, json_resp = client.post(
                name="bff_admin_unassign_task",
                json={"task_id": str(task.id)},
                cls=GetSingleTaskResponse,
            )

        assert status == 200
        assert json_resp.task.assigned_user is None


def test_admin_system_information(db_engine_ctx):
    with db_engine_ctx():
        db = SessionLocal()
        dummy = WorkflowDummy(db_session=db, users_with_roles={"admin": ["wf-admin"]})

        client = Client()
        with override_get_user(client=client, user=dummy.user("admin").user), disable_role_check(client):
            status, json_resp = client.get(name="bff_admin_system_information", cls=GetSystemInformationResponse)

        assert status == 200
        assert json_resp.build_number  # default "dev" in tests


def test_admin_get_task_states_per_workflow(db_engine_ctx):
    with db_engine_ctx():
        db = SessionLocal()
        workflow = _create_completed_workflow(db=db)
        client = Client()

        with override_get_user(client=client, user=workflow.user("admin").user), disable_role_check(client):
            status, _ = client.get(
                name="bff_admin_get_task_states_per_workflow",
                params={"wf_name": WF_NAME},
                cls=WorkflowStateResponse,
            )

        assert status == 200
