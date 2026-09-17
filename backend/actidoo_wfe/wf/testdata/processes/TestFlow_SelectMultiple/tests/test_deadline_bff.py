# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 ActiDoo GmbH

"""The task deadline comes from the BPMN user-task properties (``urgency`` /
``critical`` in days) and reaches the sidebar list per task and per instance."""

import datetime

from sqlalchemy import select
from sqlalchemy import update as sa_update

from actidoo_wfe.database import SessionLocal
from actidoo_wfe.helpers.time import dt_ago_naive
from actidoo_wfe.wf import service_workflow
from actidoo_wfe.wf.bff.bff_admin_schema import GetAllTasksResponse
from actidoo_wfe.wf.bff.bff_user_schema import GetWorkflowInstancesWithTasksResponse
from actidoo_wfe.wf.models import WorkflowInstanceTask
from actidoo_wfe.wf.tests.helpers.client import Client
from actidoo_wfe.wf.tests.helpers.overrides import disable_role_check, override_get_user
from actidoo_wfe.wf.tests.helpers.workflow_dummy import WorkflowDummy
from actidoo_wfe.wf.types import TaskDeadlineRepresentation

UTC = datetime.timezone.utc
T0 = datetime.datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
DAY = datetime.timedelta(days=1)


def _start(db):
    return WorkflowDummy(
        db_session=db,
        users_with_roles={"admin": ["wf-admin"], "initiator": ["wf-user"]},
        workflow_name="TestFlow_SelectMultiple",
        start_user="initiator",
    )


# ---------------------------------------------------------------------------
# level from the stored timestamps
# ---------------------------------------------------------------------------


def test_level_follows_the_stored_timestamps():
    urgency_at, critical_at = T0 + 2 * DAY, T0 + 5 * DAY

    assert service_workflow.build_task_deadline(urgency_at=None, critical_at=None) is None

    before = service_workflow.build_task_deadline(urgency_at, critical_at, now=T0 + DAY)
    assert before.level == "normal"
    assert (before.urgency_at, before.critical_at) == (urgency_at, critical_at)

    assert service_workflow.build_task_deadline(urgency_at, critical_at, now=T0 + 2 * DAY).level == "urgency"
    assert service_workflow.build_task_deadline(urgency_at, critical_at, now=T0 + 3 * DAY).level == "urgency"
    assert service_workflow.build_task_deadline(urgency_at, critical_at, now=T0 + 5 * DAY).level == "critical"

    # One threshold alone is enough.
    assert service_workflow.build_task_deadline(None, critical_at, now=T0 + 6 * DAY).level == "critical"
    assert service_workflow.build_task_deadline(urgency_at, None, now=T0 + 6 * DAY).level == "urgency"


def test_level_compares_naive_rows_as_utc():
    # Before a flush the row holds naive UTC; read back through UTCDateTime it is aware.
    naive = service_workflow.build_task_deadline(urgency_at=T0.replace(tzinfo=None), critical_at=None, now=T0 + DAY)
    aware = service_workflow.build_task_deadline(urgency_at=T0, critical_at=None, now=T0 + DAY)
    assert naive == aware
    assert naive.level == "urgency"
    assert naive.urgency_at.tzinfo is not None


# ---------------------------------------------------------------------------
# the most pressing deadline of an instance
# ---------------------------------------------------------------------------


def _deadline(level, at):
    return TaskDeadlineRepresentation(urgency_at=at, critical_at=at, level=level)


def test_highest_task_deadline_prefers_level_then_the_earliest_time():
    assert service_workflow.highest_task_deadline([]) is None
    assert service_workflow.highest_task_deadline([None, None]) is None

    normal, urgency, critical = _deadline("normal", T0 + 9 * DAY), _deadline("urgency", T0 + 3 * DAY), _deadline("critical", T0 + 7 * DAY)
    # The level wins even when a lower level is due earlier.
    assert service_workflow.highest_task_deadline([normal, urgency, None, critical]) is critical
    assert service_workflow.highest_task_deadline([normal, urgency]) is urgency

    # Same level: the one reached first.
    later, sooner = _deadline("urgency", T0 + 4 * DAY), _deadline("urgency", T0 + 2 * DAY)
    assert service_workflow.highest_task_deadline([later, sooner]) is sooner


# ---------------------------------------------------------------------------
# through the endpoints
# ---------------------------------------------------------------------------


def test_sidebar_list_carries_the_user_task_deadline(db_engine_ctx):
    with db_engine_ctx():
        db = SessionLocal()
        workflow = _start(db)

        # critical=0 on SimpleForm: critical_at was fixed to created_at when the
        # task row was stored (the definition is not consulted on read).
        task_row = db.execute(
            select(WorkflowInstanceTask).where(
                WorkflowInstanceTask.workflow_instance_id == workflow.workflow_instance_id,
                WorkflowInstanceTask.name == "SimpleForm",
            ),
        ).scalar_one()
        assert task_row.urgency_at is None
        assert task_row.critical_at == task_row.created_at

        # MySQL rounds the TIMESTAMP to whole seconds, so a moment-old task may
        # still be due "in the future"; age it so the level is settled.
        db.execute(
            sa_update(WorkflowInstanceTask)
            .where(WorkflowInstanceTask.id == task_row.id)
            .values(created_at=dt_ago_naive(days=1), critical_at=dt_ago_naive(days=1)),
        )
        db.commit()

        client = Client()
        with override_get_user(client=client, user=workflow.user("initiator").user), disable_role_check(client):
            url = client.root_client.app.url_path_for("get_workflow_instances_with_tasks", state="ready")
            response = client.root_client.post(url, json={})

        assert response.status_code == 200
        parsed = GetWorkflowInstancesWithTasksResponse.model_validate(response.json())
        instance = next(i for i in parsed.ITEMS if i.id == workflow.workflow_instance_id)

        task = next(t for t in instance.active_tasks if t.name == "SimpleForm")
        assert task.deadline is not None
        assert task.deadline.urgency_at is None
        assert task.deadline.critical_at is not None
        assert task.deadline.level == "critical"
        assert instance.deadline == task.deadline


def test_admin_task_list_carries_the_task_deadline(db_engine_ctx):
    with db_engine_ctx():
        db = SessionLocal()
        workflow = _start(db)

        db.execute(
            sa_update(WorkflowInstanceTask)
            .where(
                WorkflowInstanceTask.workflow_instance_id == workflow.workflow_instance_id,
                WorkflowInstanceTask.name == "SimpleForm",
            )
            .values(created_at=dt_ago_naive(days=1), critical_at=dt_ago_naive(days=1)),
        )
        db.commit()

        client = Client()
        with override_get_user(client=client, user=workflow.user("admin").user), disable_role_check(client):
            status, parsed = client.post(name="bff_admin_get_all_tasks", json={}, cls=GetAllTasksResponse)

        assert status == 200
        by_name = {t.name: t for t in parsed.ITEMS if t.workflow_instance.id == workflow.workflow_instance_id}
        assert by_name["SimpleForm"].deadline is not None
        assert by_name["SimpleForm"].deadline.level == "critical"
        # Only user tasks carry a deadline; the start event and gateways do not.
        assert all(t.deadline is None for name, t in by_name.items() if name != "SimpleForm")
