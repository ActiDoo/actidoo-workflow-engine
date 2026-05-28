# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

import base64
import logging
from pathlib import Path

from actidoo_wfe.database import SessionLocal, setup_db
from actidoo_wfe.settings import settings
from actidoo_wfe.wf import service_application
from actidoo_wfe.wf.bff.bff_user_schema import (
    AssignTaskToMeResponse,
    CancelWorkflowResponse,
    DeleteWorkflowResponse,
    GetMyWfeUserResponse,
    GetPinnedWorkflowsResponse,
    GetUserTasksResponse,
    GetWorkflowCopyDataResponse,
    GetWorkflowInstancesResponse,
    GetWorkflowsResponse,
    GetWorkflowStatisticsResponse,
    SearchPropertyOptionsResponse,
    StartWorkflowResponse,
    StartWorkflowWithDataResponse,
    UserSettingsResponse,
    WorkflowSpecResponse,
)
from actidoo_wfe.wf.tests.helpers.client import Client
from actidoo_wfe.wf.tests.helpers.overrides import disable_role_check, override_get_user
from actidoo_wfe.wf.tests.helpers.workflow_dummy import WorkflowDummy

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


def _start_bff_workflow(db, *, extra_users=None):
    users_with_roles = {"initiator": ["wf-user"]}
    if extra_users:
        users_with_roles.update(extra_users)
    return WorkflowDummy(
        db_session=db,
        users_with_roles=users_with_roles,
        workflow_name=WF_NAME,
        start_user="initiator",
    )


# ---------------------------------------------------------------------------
# user info / workflow listing
# ---------------------------------------------------------------------------


def test_refresh_get_workflow_spec(db_engine_ctx):
    with db_engine_ctx():
        db = SessionLocal()
        workflow = WorkflowDummy(db_session=db, users_with_roles={"u": ["wf-user"]})

        client = Client()
        with override_get_user(client=client, user=workflow.user("u").user), disable_role_check(client):
            status, json_resp = client.post(
                name="refresh_get_workflow_spec",
                json={"name": WF_NAME},
                cls=WorkflowSpecResponse,
            )

        assert status == 200
        assert len(json_resp.files) > 0


def test_get_my_wfe_user(db_engine_ctx):
    with db_engine_ctx():
        db = SessionLocal()
        workflow = WorkflowDummy(db_session=db, users_with_roles={"initiator": ["wf-user"]})
        client = Client()

        with override_get_user(client=client, user=workflow.user("initiator").user), disable_role_check(client):
            status, json_resp = client.post(name="get_my_wfe_user", json={}, cls=GetMyWfeUserResponse)

        assert status == 200
        assert json_resp.id == workflow.user("initiator").user.id
        assert json_resp.email == workflow.user("initiator").user.email


def test_get_workflows(db_engine_ctx):
    with db_engine_ctx():
        db = SessionLocal()
        workflow = WorkflowDummy(db_session=db, users_with_roles={"initiator": ["wf-user"]})
        client = Client()

        with override_get_user(client=client, user=workflow.user("initiator").user), disable_role_check(client):
            status, json_resp = client.get(name="get_workflows", cls=GetWorkflowsResponse)

        assert status == 200
        assert any(w.name == WF_NAME for w in json_resp.workflows)


def test_pinned_workflows_toggle(db_engine_ctx):
    with db_engine_ctx():
        db = SessionLocal()
        workflow = WorkflowDummy(db_session=db, users_with_roles={"initiator": ["wf-user"]})
        client = Client()

        with override_get_user(client=client, user=workflow.user("initiator").user), disable_role_check(client):
            status, json_resp = client.get(name="get_pinned_workflows", cls=GetPinnedWorkflowsResponse)
            assert status == 200
            assert json_resp.pinned_workflow_names == []

            status, json_resp = client.post(
                name="toggle_pinned_workflow",
                json={"name": WF_NAME},
                cls=GetPinnedWorkflowsResponse,
            )
            assert status == 200
            assert json_resp.pinned_workflow_names == [WF_NAME]

            # persists across a fresh GET
            status, json_resp = client.get(name="get_pinned_workflows", cls=GetPinnedWorkflowsResponse)
            assert status == 200
            assert json_resp.pinned_workflow_names == [WF_NAME]

            # toggling again removes it
            status, json_resp = client.post(
                name="toggle_pinned_workflow",
                json={"name": WF_NAME},
                cls=GetPinnedWorkflowsResponse,
            )
            assert status == 200
            assert json_resp.pinned_workflow_names == []


def test_pinned_workflows_are_user_specific(db_engine_ctx):
    with db_engine_ctx():
        db = SessionLocal()
        workflow = WorkflowDummy(db_session=db, users_with_roles={"alice": ["wf-user"], "bob": ["wf-user"]})
        client = Client()

        with override_get_user(client=client, user=workflow.user("alice").user), disable_role_check(client):
            status, json_resp = client.post(
                name="toggle_pinned_workflow",
                json={"name": WF_NAME},
                cls=GetPinnedWorkflowsResponse,
            )
            assert status == 200
            assert json_resp.pinned_workflow_names == [WF_NAME]

        with override_get_user(client=client, user=workflow.user("bob").user), disable_role_check(client):
            status, json_resp = client.get(name="get_pinned_workflows", cls=GetPinnedWorkflowsResponse)
            assert status == 200
            assert json_resp.pinned_workflow_names == []


def test_get_workflow_statistics(db_engine_ctx):
    with db_engine_ctx():
        db = SessionLocal()
        workflow = WorkflowDummy(db_session=db, users_with_roles={"initiator": ["wf-user"]})
        client = Client()

        with override_get_user(client=client, user=workflow.user("initiator").user), disable_role_check(client):
            status, json_resp = client.get(name="get_workflow_statistics", cls=GetWorkflowStatisticsResponse)

        assert status == 200
        assert isinstance(json_resp.workflows, list)


# ---------------------------------------------------------------------------
# start_workflow / preview / copy
# ---------------------------------------------------------------------------


def test_start_workflow(db_engine_ctx):
    with db_engine_ctx():
        db = SessionLocal()
        workflow = WorkflowDummy(db_session=db, users_with_roles={"initiator": ["wf-user"]})
        client = Client()

        with override_get_user(client=client, user=workflow.user("initiator").user), disable_role_check(client):
            status, json_resp = client.post(
                name="start_workflow",
                json={"name": WF_NAME},
                cls=StartWorkflowResponse,
            )

        assert status == 200
        assert json_resp.workflow_instance_id is not None


def test_start_workflow_preview_with_data(db_engine_ctx):
    with db_engine_ctx():
        db = SessionLocal()
        workflow = WorkflowDummy(db_session=db, users_with_roles={"initiator": ["wf-user"]})
        client = Client()

        with override_get_user(client=client, user=workflow.user("initiator").user), disable_role_check(client):
            status, json_resp = client.post(
                name="start_workflow_preview_with_data",
                json={"name": WF_NAME, "data": FORM1_DATA_MIN},
                cls=StartWorkflowWithDataResponse,
            )

        assert status == 200
        assert json_resp.name == WF_NAME
        assert json_resp.task is not None


def test_get_workflow_copy_data(db_engine_ctx):
    with db_engine_ctx():
        db = SessionLocal()
        workflow = _start_bff_workflow(db)
        workflow.user("initiator").submit(
            task_data=FORM1_DATA_MIN,
            workflow_instance_id=workflow.workflow_instance_id,
        )
        workflow.user("initiator").submit(
            task_data=FORM2_DATA,
            workflow_instance_id=workflow.workflow_instance_id,
        )

        client = Client()
        with override_get_user(client=client, user=workflow.user("initiator").user), disable_role_check(client):
            url = client.root_client.app.url_path_for(
                "get_workflow_copy_data",
                workflow_instance_id=str(workflow.workflow_instance_id),
            )
            response = client.root_client.post(url, json={})

        assert response.status_code == 200
        parsed = GetWorkflowCopyDataResponse.model_validate(response.json())
        assert parsed.workflow_name == WF_NAME


# ---------------------------------------------------------------------------
# tasks
# ---------------------------------------------------------------------------


def test_get_my_usertasks_ready(db_engine_ctx):
    with db_engine_ctx():
        db = SessionLocal()
        workflow = _start_bff_workflow(db)

        client = Client()
        with override_get_user(client=client, user=workflow.user("initiator").user), disable_role_check(client):
            url = client.root_client.app.url_path_for("get_usertasks", state="ready")
            response = client.root_client.get(
                url,
                params={"workflow_instance_id": str(workflow.workflow_instance_id)},
            )

        assert response.status_code == 200
        parsed = GetUserTasksResponse.model_validate(response.json())
        assert len(parsed.usertasks) == 1
        assert parsed.usertasks[0].name == "Form1"


def test_submit_task_data_happy(db_engine_ctx):
    with db_engine_ctx():
        db = SessionLocal()
        workflow = _start_bff_workflow(db)
        task = workflow.user("initiator").get_usertasks(workflow.workflow_instance_id, 1)[0]

        client = Client()
        with override_get_user(client=client, user=workflow.user("initiator").user), disable_role_check(client):
            url = client.root_client.app.url_path_for("submit_task_data")
            response = client.root_client.post(
                url,
                params={"task_id": str(task.id)},
                json=FORM1_DATA_MIN,
            )

        assert response.status_code == 200
        parsed = GetUserTasksResponse.model_validate(response.json())
        # After submit Form1 (with trigger_error=false), next task should be Form2
        assert len(parsed.usertasks) == 1
        assert parsed.usertasks[0].name == "Form2"


def test_submit_400_required_missing(db_engine_ctx):
    with db_engine_ctx():
        db = SessionLocal()
        workflow = _start_bff_workflow(db)
        task = workflow.user("initiator").get_usertasks(workflow.workflow_instance_id, 1)[0]

        client = Client()
        with override_get_user(client=client, user=workflow.user("initiator").user), disable_role_check(client):
            url = client.root_client.app.url_path_for("submit_task_data")
            response = client.root_client.post(
                url, params={"task_id": str(task.id)}, json={"trigger_error": False},
            )

        assert response.status_code == 400
        assert "error_schema" in response.json()


def test_submit_400_required_too_short(db_engine_ctx):
    with db_engine_ctx():
        db = SessionLocal()
        workflow = _start_bff_workflow(db)
        task = workflow.user("initiator").get_usertasks(workflow.workflow_instance_id, 1)[0]

        client = Client()
        with override_get_user(client=client, user=workflow.user("initiator").user), disable_role_check(client):
            url = client.root_client.app.url_path_for("submit_task_data")
            response = client.root_client.post(
                url, params={"task_id": str(task.id)},
                json={"required_text": "a", "trigger_error": False},
            )

        assert response.status_code == 400
        assert "error_schema" in response.json()


def test_submit_400_short_code_too_long(db_engine_ctx):
    with db_engine_ctx():
        db = SessionLocal()
        workflow = _start_bff_workflow(db)
        task = workflow.user("initiator").get_usertasks(workflow.workflow_instance_id, 1)[0]

        client = Client()
        with override_get_user(client=client, user=workflow.user("initiator").user), disable_role_check(client):
            url = client.root_client.app.url_path_for("submit_task_data")
            response = client.root_client.post(
                url, params={"task_id": str(task.id)},
                json={"required_text": "ok", "short_code": "ABCD", "trigger_error": False},
            )

        assert response.status_code == 400
        assert "error_schema" in response.json()


def test_assign_task_to_me(db_engine_ctx):
    with db_engine_ctx():
        db = SessionLocal()
        workflow = _start_bff_workflow(db)
        task = workflow.user("initiator").get_usertasks(workflow.workflow_instance_id, 1)[0]

        client = Client()
        with override_get_user(client=client, user=workflow.user("initiator").user), disable_role_check(client):
            status, _json = client.post(
                name="assign_task",
                json={"task_id": str(task.id)},
                cls=AssignTaskToMeResponse,
            )

            assert status == 200
            url = client.root_client.app.url_path_for("get_usertasks", state="ready")
            response = client.root_client.get(
                url, params={"workflow_instance_id": str(workflow.workflow_instance_id)},
            )
            parsed = GetUserTasksResponse.model_validate(response.json())
            assert parsed.usertasks[0].assigned_user is not None


def test_unassign_task_from_me(db_engine_ctx):
    # The endpoint silently no-ops when can_be_unassigned is False, which is the
    # default for this synthetic flow's user task (set_allow_unassign is internal
    # to a single assign->unassign roundtrip and does not survive a reload).
    # We assert only that the endpoint stays reachable and returns 200.
    with db_engine_ctx():
        db = SessionLocal()
        workflow = _start_bff_workflow(db)
        task = workflow.user("initiator").get_usertasks(workflow.workflow_instance_id, 1)[0]
        workflow.user("initiator").assign_task(task_id=task.id)

        client = Client()
        with override_get_user(client=client, user=workflow.user("initiator").user), disable_role_check(client):
            status, _ = client.post(
                name="unassign_task",
                json={"task_id": str(task.id)},
                cls=AssignTaskToMeResponse,
            )

        assert status == 200


# ---------------------------------------------------------------------------
# pagination
# ---------------------------------------------------------------------------


def test_get_my_initiated_workflow_instances(db_engine_ctx):
    with db_engine_ctx():
        db = SessionLocal()
        workflow = _start_bff_workflow(db)

        client = Client()
        with override_get_user(client=client, user=workflow.user("initiator").user), disable_role_check(client):
            status, json_resp = client.post(
                name="get_my_initiated_workflow_instances",
                json={},
                cls=GetWorkflowInstancesResponse,
            )

        assert status == 200
        assert any(i.id == workflow.workflow_instance_id for i in json_resp.ITEMS)


def test_get_workflow_instances_with_tasks_ready(db_engine_ctx):
    with db_engine_ctx():
        db = SessionLocal()
        workflow = _start_bff_workflow(db)

        client = Client()
        with override_get_user(client=client, user=workflow.user("initiator").user), disable_role_check(client):
            url = client.root_client.app.url_path_for("get_workflow_instances_with_tasks", state="ready")
            response = client.root_client.post(url, json={})

        assert response.status_code == 200
        parsed = GetWorkflowInstancesResponse.model_validate(response.json())
        assert any(i.id == workflow.workflow_instance_id for i in parsed.ITEMS)


# ---------------------------------------------------------------------------
# property options + download
# ---------------------------------------------------------------------------


def test_search_property_options(db_engine_ctx):
    with db_engine_ctx():
        db = SessionLocal()
        workflow = _start_bff_workflow(db)
        task = workflow.user("initiator").get_usertasks(workflow.workflow_instance_id, 1)[0]

        client = Client()
        with override_get_user(client=client, user=workflow.user("initiator").user), disable_role_check(client):
            status, json_resp = client.post(
                name="get_property_options",
                json={
                    "task_id": str(task.id),
                    "property_path": ["category"],
                    "search": "",
                },
                cls=SearchPropertyOptionsResponse,
            )

        assert status == 200
        values = {o.value for o in json_resp.options}
        assert {"cat_alpha", "cat_beta", "cat_gamma"} <= values


def test_download_attachment(db_engine_ctx):
    with db_engine_ctx():
        db = SessionLocal()
        workflow = _start_bff_workflow(db)
        task = workflow.user("initiator").get_usertasks(workflow.workflow_instance_id, 1)[0]
        workflow.user("initiator").assign_task(task_id=task.id)
        attachment = _png_attachment()
        workflow.user("initiator").submit(
            task_data={**FORM1_DATA_MIN, "attachment": attachment},
            workflow_instance_id=workflow.workflow_instance_id,
            task_id=task.id,
        )

        attachments = service_application.find_all_workflow_attachments(
            db=db, workflow_instance_id=workflow.workflow_instance_id,
        )
        assert attachments, "expected at least one attachment after upload"
        hash_value = attachments[0].hash

        client = Client()
        with override_get_user(client=client, user=workflow.user("initiator").user), disable_role_check(client):
            url = client.root_client.app.url_path_for("download_attachment")
            response = client.root_client.post(
                url, json={"task_id": str(task.id), "hash": hash_value},
            )

        assert response.status_code == 200
        assert "content-disposition" in {k.lower() for k in response.headers}


# ---------------------------------------------------------------------------
# cancel / delete
# ---------------------------------------------------------------------------


def test_cancel_workflow(db_engine_ctx):
    with db_engine_ctx():
        db = SessionLocal()
        workflow = _start_bff_workflow(db)
        task = workflow.user("initiator").get_usertasks(workflow.workflow_instance_id, 1)[0]

        client = Client()
        with override_get_user(client=client, user=workflow.user("initiator").user), disable_role_check(client):
            status, _json = client.post(
                name="cancel_workflow",
                json={"task_id": str(task.id)},
                cls=CancelWorkflowResponse,
            )

        assert status == 200


def test_delete_workflow(db_engine_ctx):
    with db_engine_ctx():
        db = SessionLocal()
        workflow = _start_bff_workflow(db)
        task = workflow.user("initiator").get_usertasks(workflow.workflow_instance_id, 1)[0]

        client = Client()
        with override_get_user(client=client, user=workflow.user("initiator").user), disable_role_check(client):
            status, _json = client.post(
                name="delete_workflow",
                json={"task_id": str(task.id)},
                cls=DeleteWorkflowResponse,
            )

        assert status == 200


# ---------------------------------------------------------------------------
# user settings
# ---------------------------------------------------------------------------


def test_save_user_settings(db_engine_ctx):
    with db_engine_ctx():
        db = SessionLocal()
        workflow = WorkflowDummy(db_session=db, users_with_roles={"initiator": ["wf-user"]})

        client = Client()
        with override_get_user(client=client, user=workflow.user("initiator").user), disable_role_check(client):
            status, json_resp = client.post(
                name="save_user_settings",
                json={"locale": "de-DE", "delegations": []},
                cls=UserSettingsResponse,
            )

        assert status == 200
        assert json_resp.locale == "de-DE"


def test_get_user_settings(db_engine_ctx):
    with db_engine_ctx():
        db = SessionLocal()
        workflow = WorkflowDummy(db_session=db, users_with_roles={"initiator": ["wf-user"]})

        client = Client()
        with override_get_user(client=client, user=workflow.user("initiator").user), disable_role_check(client):
            status, json_resp = client.get(name="get_user_settings", cls=UserSettingsResponse)

        assert status == 200
        assert json_resp.locale  # default locale is set
        assert len(json_resp.supported_locales) > 0
