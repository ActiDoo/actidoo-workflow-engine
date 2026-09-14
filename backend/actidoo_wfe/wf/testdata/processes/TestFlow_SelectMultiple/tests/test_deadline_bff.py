# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 ActiDoo GmbH

"""The task deadline comes from the BPMN user-task properties (``urgency`` /
``critical`` in days) and reaches the sidebar list per task and per instance."""

from sqlalchemy import select
from sqlalchemy import update as sa_update

from actidoo_wfe.database import SessionLocal
from actidoo_wfe.helpers.time import dt_ago_naive
from actidoo_wfe.wf.bff.bff_user_schema import GetWorkflowInstancesWithTasksResponse
from actidoo_wfe.wf.models import WorkflowInstanceTask
from actidoo_wfe.wf.tests.helpers.client import Client
from actidoo_wfe.wf.tests.helpers.overrides import disable_role_check, override_get_user
from actidoo_wfe.wf.tests.helpers.workflow_dummy import WorkflowDummy


def test_sidebar_list_carries_the_user_task_deadline(db_engine_ctx):
    with db_engine_ctx():
        db = SessionLocal()
        workflow = WorkflowDummy(
            db_session=db,
            users_with_roles={"initiator": ["wf-user"]},
            workflow_name="TestFlow_SelectMultiple",
            start_user="initiator",
        )

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
