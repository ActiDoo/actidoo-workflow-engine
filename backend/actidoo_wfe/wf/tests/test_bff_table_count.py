# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""Performance and query-shape regressions for BFF table lists."""

import uuid

from sqlalchemy import event

from actidoo_wfe.wf.bff.bff_admin import (
    AdminWorkflowInstancesBffTableQuerySchema,
    AdminWorkflowInstanceTasksBffTableQuerySchema,
    AdminWorkflowUsersBffTableQuerySchema,
)
from actidoo_wfe.wf.models import (
    WorkflowInstance,
    WorkflowInstanceTask,
    WorkflowRole,
    WorkflowUser,
    WorkflowUserRole,
)


def test_all_users_dedups_the_distinct_role_fanout(db_engine_ctx):
    """The users list outer-joins roles and relies on DISTINCT to collapse the
    fan-out: a user with two roles must appear once with count 1, not twice —
    while both roles still arrive through the selectin load."""
    with db_engine_ctx():
        from actidoo_wfe.database import SessionLocal
        from actidoo_wfe.wf import views

        db = SessionLocal()
        user = WorkflowUser(username="two-roles", email="two-roles@example.com")
        first_role = WorkflowRole(name="first-role")
        second_role = WorkflowRole(name="second-role")
        db.add_all(
            [
                user,
                first_role,
                second_role,
                WorkflowUserRole(user=user, role=first_role),
                WorkflowUserRole(user=user, role=second_role),
            ],
        )
        db.commit()

        result = views.bff_admin_get_all_users(
            db=db,
            bff_table_request_params=AdminWorkflowUsersBffTableQuerySchema(),
        )

        assert result.COUNT == 1
        assert [item["id"] for item in result.ITEMS] == [user.id]
        assert sorted(result.ITEMS[0]["roles"]) == ["first-role", "second-role"]


def _seed_tasks_with_assigned_users(db, count: int):
    """One instance with *count* tasks, each assigned to a user whose computed
    full_name sorts in task index order."""
    users = [
        WorkflowUser(id=uuid.uuid4(), username=f"user{i}", email=f"user{i}@example.com", first_name=chr(ord("a") + i), last_name="sorter")
        for i in range(count)
    ]
    instance = WorkflowInstance(id=uuid.uuid4(), name="wf", title="t", lane_mapping={}, data={}, is_completed=False, created_by=users[0])
    tasks = [
        WorkflowInstanceTask(
            id=uuid.uuid4(),
            workflow_instance=instance,
            name=f"t{i}",
            title=f"t{i}",
            state=1,
            state_ready=True,
            sort=i,
            assigned_user=users[i],
            completed_by_user=users[0],
            data={"index": i},
            jsonschema={"index": i},
            uischema={"index": i},
            error_stacktrace=f"error {i}",
        )
        for i in range(count)
    ]
    db.add_all(users + [instance] + tasks)
    db.commit()
    return instance, tasks


def test_all_tasks_page_loads_the_slice_without_unbounded_related_data(db_engine_ctx):
    """Cover the admin task page's result and SQL shape in one request."""
    with db_engine_ctx():
        from actidoo_wfe.database import SessionLocal
        from actidoo_wfe.wf import views

        db = SessionLocal()
        _, tasks = _seed_tasks_with_assigned_users(db, count=4)

        statements = []

        def capture(conn, cursor, statement, parameters, context, executemany):
            statements.append(statement)

        engine = db.get_bind()
        event.listen(engine, "before_cursor_execute", capture)
        try:
            result = views.bff_admin_get_all_tasks(
                db=db,
                bff_table_request_params=AdminWorkflowInstanceTasksBffTableQuerySchema(
                    sort=["assigned_user___full_name.asc"],
                    limit=2,
                    offset=1,
                ),
                allowed_workflow_names={"wf"},
            )
        finally:
            event.remove(engine, "before_cursor_execute", capture)

        assert result.COUNT == 4
        assert len(result.ITEMS) == 2
        assert [item.id for item in result.ITEMS] == [task.id for task in tasks[1:3]]
        assert [item.data for item in result.ITEMS] == [{"index": 1}, {"index": 2}]
        assert [item.title for item in result.ITEMS] == ["t1", "t2"]

        page_selects = [s for s in statements if "ORDER BY" in s and "LIMIT" in s and "FROM workflow_instance_tasks" in s]
        assert len(page_selects) == 1
        for column in ("data", "jsonschema", "uischema", "error_stacktrace"):
            assert f"workflow_instance_tasks.{column}" not in page_selects[0]

        count_selects = [s for s in statements if s.startswith("SELECT count(*)")]
        assert len(count_selects) == 1
        assert "SELECT workflow_instance_tasks.id AS id" in count_selects[0]
        assert "workflow_instance_tasks.jsonschema" not in count_selects[0]

        payload_selects = [s for s in statements if "workflow_instance_tasks.id IN" in s and "workflow_instance_tasks.jsonschema" in s]
        assert len(payload_selects) == 1
        for column in ("data", "jsonschema", "uischema", "error_stacktrace"):
            assert f"workflow_instance_tasks.{column}" in payload_selects[0]
        # The instances' payload blobs are deferred everywhere.
        assert all("workflow_instances.data" not in s and "lane_mapping" not in s for s in statements)
        # Users arrive as batched selectin loads, never as per-row lazy loads.
        user_selects = [s for s in statements if "FROM workflow_users" in s]
        assert user_selects
        assert all("workflow_users.id IN" in s for s in user_selects)


def test_all_workflow_instances_loads_the_error_flag_after_pagination(db_engine_ctx):
    with db_engine_ctx():
        from actidoo_wfe.database import SessionLocal
        from actidoo_wfe.wf import views

        db = SessionLocal()
        instance, tasks = _seed_tasks_with_assigned_users(db, count=2)
        tasks[0].state_error = True
        db.commit()
        statements = []

        def capture(conn, cursor, statement, parameters, context, executemany):
            statements.append(statement)

        engine = db.get_bind()
        event.listen(engine, "before_cursor_execute", capture)
        try:
            result = views.bff_admin_get_all_workflow_instances(
                db=db,
                bff_table_request_params=AdminWorkflowInstancesBffTableQuerySchema(limit=1),
                allowed_workflow_names={"wf"},
            )
        finally:
            event.remove(engine, "before_cursor_execute", capture)

        assert result.COUNT == 1
        assert [item.id for item in result.ITEMS] == [instance.id]
        assert result.ITEMS[0].has_task_in_error_state is True
        assert result.ITEMS[0].title == "t"

        page_selects = [s for s in statements if "ORDER BY" in s and "LIMIT" in s and "FROM workflow_instances" in s]
        assert len(page_selects) == 1
        assert "workflow_instance_tasks.state_error" not in page_selects[0]
        assert "workflow_instances.data" not in page_selects[0]
        assert "workflow_instances.lane_mapping" not in page_selects[0]

        error_flag_selects = [s for s in statements if "workflow_instances.id IN" in s and "workflow_instance_tasks.state_error" in s]
        assert len(error_flag_selects) == 1
