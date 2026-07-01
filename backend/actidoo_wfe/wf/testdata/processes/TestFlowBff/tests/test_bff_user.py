# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

import base64
import datetime
import logging
import uuid
from pathlib import Path

from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from sqlalchemy import update as sa_update

from actidoo_wfe.database import SessionLocal, setup_db
from actidoo_wfe.helpers.bff_table import CursorPosition, decode_cursor, encode_cursor
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
    GetWorkflowInstancesWithTasksResponse,
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
        # BFF: the instance block rides along so the task page has the title.
        assert parsed.workflow_instance is not None
        assert parsed.workflow_instance.id == workflow.workflow_instance_id
        assert parsed.workflow_instance.title


def test_get_my_usertasks_instance_block_visibility(db_engine_ctx):
    """The instance block is shipped only to users who may see the instance —
    outsiders and unknown ids get the same empty shape (no title oracle)."""
    with db_engine_ctx():
        db = SessionLocal()
        workflow = _start_bff_workflow(db, extra_users={"outsider": ["wf-user"]})

        client = Client()
        url_for = lambda c: c.root_client.app.url_path_for("get_usertasks", state="ready")  # noqa: E731

        with override_get_user(client=client, user=workflow.user("outsider").user), disable_role_check(client):
            foreign = client.root_client.get(
                url_for(client), params={"workflow_instance_id": str(workflow.workflow_instance_id)},
            )
            unknown = client.root_client.get(
                url_for(client), params={"workflow_instance_id": str(uuid.uuid4())},
            )

        # identical shape for "not involved" and "does not exist"
        for response in (foreign, unknown):
            assert response.status_code == 200
            parsed = GetUserTasksResponse.model_validate(response.json())
            assert parsed.usertasks == []
            assert parsed.workflow_instance is None


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
        # The submit response carries the instance block too — the task page must
        # not lose the title when this replaces its store data.
        assert parsed.workflow_instance is not None
        assert parsed.workflow_instance.id == workflow.workflow_instance_id


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
        parsed = GetWorkflowInstancesWithTasksResponse.model_validate(response.json())
        assert any(i.id == workflow.workflow_instance_id for i in parsed.ITEMS)
        # cursor responses carry no total count
        assert "COUNT" not in response.json()


def test_cursor_encode_decode_roundtrip():
    ident = uuid.uuid4()
    position = CursorPosition(
        sort_value=datetime.datetime(2026, 6, 1, 12, 30, 45, tzinfo=datetime.timezone.utc),
        id=ident,
    )
    assert decode_cursor(encode_cursor(position.sort_value, position.id)) == position

    # sub-second precision is truncated (TIMESTAMP fsp=0) and naive datetimes
    # are treated as UTC — both decode to the same position
    with_micros = position.sort_value.replace(microsecond=999999)
    assert decode_cursor(encode_cursor(with_micros, ident)) == position
    naive = position.sort_value.replace(tzinfo=None)
    assert decode_cursor(encode_cursor(naive, ident)) == position

    # missing / malformed tokens degrade to None instead of raising
    assert decode_cursor(None) is None
    assert decode_cursor("") is None
    assert decode_cursor("garbage") is None
    assert decode_cursor(ident.hex) is None  # former id-only token format
    assert decode_cursor(base64.urlsafe_b64encode(b"no-separator").decode()) is None
    assert decode_cursor(base64.urlsafe_b64encode(b"-5|" + ident.hex.encode()).decode()) is None
    assert decode_cursor(base64.urlsafe_b64encode(b"123|nothex").decode()) is None
    assert decode_cursor(base64.urlsafe_b64encode(f"1|2|{ident.hex}".encode()).decode()) is None


def _walk_cursor_pages(client, url, limit, params_extra=None, max_pages=20):
    """Walk the cursor pagination until exhausted; returns (ids per page, pages)."""
    pages: list[list] = []
    cursor = None
    while True:
        params = {"limit": str(limit), **(params_extra or {})}
        if cursor:
            params["cursor"] = cursor
        response = client.root_client.post(url, params=params, json={})
        assert response.status_code == 200
        parsed = GetWorkflowInstancesWithTasksResponse.model_validate(response.json())
        pages.append([i.id for i in parsed.ITEMS])
        cursor = parsed.NEXT_CURSOR
        if cursor is None:
            break
        assert len(pages) <= max_pages  # guard against an unterminated cursor walk
    return pages


def test_get_workflow_instances_with_tasks_cursor_pagination(db_engine_ctx):
    with db_engine_ctx():
        db = SessionLocal()
        workflow = _start_bff_workflow(db)
        user = workflow.user("initiator").user

        # Start two more ready instances for the same user so we paginate across 3.
        for _ in range(2):
            service_application.start_workflow(db=db, name=WF_NAME, user_id=user.id)
        db.commit()

        client = Client()
        with override_get_user(client=client, user=user), disable_role_check(client):
            url = client.root_client.app.url_path_for("get_workflow_instances_with_tasks", state="ready")
            pages = _walk_cursor_pages(client, url, limit=1)

    seen_ids = [i for page in pages for i in page]
    # no overlap across pages, all three instances retrieved
    assert len(seen_ids) == len(set(seen_ids))
    assert len(set(seen_ids)) >= 3


def _set_created_at(db, instance_ids, created_at):
    """Force deterministic created_at values (TIMESTAMP has second granularity —
    ties are the production norm and must be deterministic in tests)."""
    from actidoo_wfe.wf.models import WorkflowInstance

    for instance_id in instance_ids:
        db.execute(
            sa_update(WorkflowInstance).where(WorkflowInstance.id == instance_id).values(created_at=created_at),
        )
    db.commit()


def test_cursor_walk_is_deterministic_for_created_at_ties(db_engine_ctx):
    """Instances sharing one created_at second are ordered strictly by id DESC."""
    with db_engine_ctx():
        db = SessionLocal()
        workflow = _start_bff_workflow(db)
        user = workflow.user("initiator").user
        ids = [workflow.workflow_instance_id]
        for _ in range(3):
            ids.append(service_application.start_workflow(db=db, name=WF_NAME, user_id=user.id))
        db.commit()
        _set_created_at(db, ids, datetime.datetime(2026, 6, 1, 12, 0, 0))

        client = Client()
        with override_get_user(client=client, user=user), disable_role_check(client):
            url = client.root_client.app.url_path_for("get_workflow_instances_with_tasks", state="ready")
            pages = _walk_cursor_pages(client, url, limit=1)

    seen_ids = [i for page in pages for i in page]
    assert len(seen_ids) == len(set(seen_ids)) == 4
    # within the tie, the order is the id DESC tiebreaker — deterministic
    assert seen_ids == sorted(seen_ids, key=lambda i: str(i), reverse=True)


def test_cursor_continues_after_cursor_row_deleted(db_engine_ctx):
    """The token is a position, not a row reference: deleting the cursor row
    must not restart paging from the beginning."""
    with db_engine_ctx():
        db = SessionLocal()
        workflow = _start_bff_workflow(db)
        user = workflow.user("initiator").user
        for _ in range(2):
            service_application.start_workflow(db=db, name=WF_NAME, user_id=user.id)
        db.commit()

        client = Client()
        with override_get_user(client=client, user=user), disable_role_check(client):
            url = client.root_client.app.url_path_for("get_workflow_instances_with_tasks", state="ready")

            first = client.root_client.post(url, params={"limit": "1"}, json={})
            assert first.status_code == 200
            page1 = GetWorkflowInstancesWithTasksResponse.model_validate(first.json())
            assert len(page1.ITEMS) == 1 and page1.NEXT_CURSOR

            # delete the row the cursor points at (children cascade at DB level,
            # same as repository.delete_workflow_instance)
            from actidoo_wfe.wf.models import WorkflowInstance

            deleted_id = page1.ITEMS[0].id
            db.execute(sa_delete(WorkflowInstance).where(WorkflowInstance.id == deleted_id))
            db.commit()

            second = client.root_client.post(
                url, params={"limit": "10", "cursor": page1.NEXT_CURSOR}, json={},
            )
            assert second.status_code == 200
            page2 = GetWorkflowInstancesWithTasksResponse.model_validate(second.json())

    # continuation, not a restart: the deleted row is gone, the remaining two follow
    ids2 = [i.id for i in page2.ITEMS]
    assert deleted_id not in ids2
    assert len(ids2) == 2


def test_cursor_from_foreign_instance_yields_only_own_rows(db_engine_ctx):
    """A token built from another user's instance is just a position: the
    response stays scoped to the caller — no oracle, nothing foreign."""
    with db_engine_ctx():
        db = SessionLocal()
        workflow = _start_bff_workflow(db, extra_users={"outsider": ["wf-user"]})
        initiator = workflow.user("initiator").user
        outsider = workflow.user("outsider").user

        # the outsider has one own instance
        own_id = service_application.start_workflow(db=db, name=WF_NAME, user_id=outsider.id)
        db.commit()

        # craft a token from the initiator's instance, positioned in the future
        # so the outsider's own row lies behind it
        from actidoo_wfe.wf.models import WorkflowInstance

        foreign_created_at = db.execute(
            select(WorkflowInstance.created_at).where(WorkflowInstance.id == workflow.workflow_instance_id),
        ).scalar_one() + datetime.timedelta(hours=1)
        token = encode_cursor(foreign_created_at, workflow.workflow_instance_id)

        client = Client()
        with override_get_user(client=client, user=outsider), disable_role_check(client):
            url = client.root_client.app.url_path_for("get_workflow_instances_with_tasks", state="ready")
            response = client.root_client.post(url, params={"limit": "10", "cursor": token}, json={})

        assert response.status_code == 200
        parsed = GetWorkflowInstancesWithTasksResponse.model_validate(response.json())
        ids = [i.id for i in parsed.ITEMS]
        assert ids == [own_id]
        assert workflow.workflow_instance_id not in ids


def test_cursor_walk_with_search(db_engine_ctx):
    """search and cursor combine: the walk pages only through matches."""
    with db_engine_ctx():
        db = SessionLocal()
        workflow = _start_bff_workflow(db)
        user = workflow.user("initiator").user
        ids = [workflow.workflow_instance_id]
        for _ in range(3):
            ids.append(service_application.start_workflow(db=db, name=WF_NAME, user_id=user.id))
        db.commit()

        # give two instances a distinguishable title (deterministic via DB update)
        from actidoo_wfe.wf.models import WorkflowInstance

        needle_ids = set(ids[:2])
        for instance_id in needle_ids:
            db.execute(
                sa_update(WorkflowInstance).where(WorkflowInstance.id == instance_id).values(title="Needle"),
            )
        db.commit()

        client = Client()
        with override_get_user(client=client, user=user), disable_role_check(client):
            url = client.root_client.app.url_path_for("get_workflow_instances_with_tasks", state="ready")
            pages = _walk_cursor_pages(client, url, limit=1, params_extra={"search": "Needle"})

    seen_ids = [i for page in pages for i in page]
    assert set(seen_ids) == needle_ids
    assert len(seen_ids) == len(set(seen_ids))


def test_cursor_malformed_token_yields_first_page(db_engine_ctx):
    with db_engine_ctx():
        db = SessionLocal()
        workflow = _start_bff_workflow(db)
        user = workflow.user("initiator").user

        client = Client()
        with override_get_user(client=client, user=user), disable_role_check(client):
            url = client.root_client.app.url_path_for("get_workflow_instances_with_tasks", state="ready")
            response = client.root_client.post(url, params={"limit": "10", "cursor": "garbage"}, json={})

        assert response.status_code == 200
        parsed = GetWorkflowInstancesWithTasksResponse.model_validate(response.json())
        assert any(i.id == workflow.workflow_instance_id for i in parsed.ITEMS)


def test_cursor_exactly_full_last_page_has_no_token(db_engine_ctx):
    """limit+1 look-ahead: an exactly full last page must not advertise more."""
    with db_engine_ctx():
        db = SessionLocal()
        workflow = _start_bff_workflow(db)
        user = workflow.user("initiator").user
        for _ in range(2):
            service_application.start_workflow(db=db, name=WF_NAME, user_id=user.id)
        db.commit()  # exactly 3 ready instances

        client = Client()
        with override_get_user(client=client, user=user), disable_role_check(client):
            url = client.root_client.app.url_path_for("get_workflow_instances_with_tasks", state="ready")
            exact = client.root_client.post(url, params={"limit": "3"}, json={})
            short = client.root_client.post(url, params={"limit": "2"}, json={})

        exact_page = GetWorkflowInstancesWithTasksResponse.model_validate(exact.json())
        assert len(exact_page.ITEMS) == 3
        assert exact_page.NEXT_CURSOR is None  # full but final → no empty extra request

        short_page = GetWorkflowInstancesWithTasksResponse.model_validate(short.json())
        assert len(short_page.ITEMS) == 2
        assert short_page.NEXT_CURSOR is not None


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
