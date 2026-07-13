# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""Guards for the SQL shape of the BFF list queries.

Both pagination statements run on every page request and must never drag wide
entity rows through MySQL temp tables:

- The count wraps a subquery; a subselect or blob column in its select list
  prevents MySQL from merging the derived table, materializing the whole
  filtered set per request. The count therefore wraps the primary key only.
- The page load sorts before it limits; sorting full entity rows materializes
  the whole filtered join (blobs included) before LIMIT can apply. The page
  therefore loads in two phases: primary keys first, then the rows for
  exactly those keys.

These tests pin both reductions, the entity contract that makes them
well-defined, and the deferral of payload blobs out of the list queries.
"""

import uuid

import pytest
from sqlalchemy import event, literal, select
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import aliased

import actidoo_wfe.helpers.bff_table as bff_table_module
from actidoo_wfe.helpers.bff_table import BFFTable
from actidoo_wfe.wf.bff.bff_admin import (
    AdminWorkflowInstancesBffTableQuerySchema,
    AdminWorkflowInstanceTasksBffTableQuerySchema,
    AdminWorkflowUsersBffTableQuerySchema,
)
from actidoo_wfe.wf.models import WorkflowInstance, WorkflowInstanceTask, WorkflowRole, WorkflowUser, WorkflowUserRole
from actidoo_wfe.wf.testdata.datamodels.demo_expense_model import DemoExpense
from actidoo_wfe.wf.views import _bff_admin_all_tasks_table, _bff_admin_all_workflow_instances_table, _instance_list_loader_options

# Schema without filter/sort fields, for contract tests whose queries do not
# export the admin columns.
MinimalQuerySchema = bff_table_module.get_bff_table_query_schema(
    schema_name="MinimalCountQuerySchema",
    sorting_fields=[],
    filter_fields=[],
    add_global_search_filter=False,
)


def _compile(query) -> str:
    return str(query.compile(dialect=mysql.dialect()))


def _count_subquery_columns(bff_table: BFFTable) -> list[str]:
    """The select list of the derived table the count wraps."""
    return list(bff_table._count_query().get_final_froms()[0].c.keys())


def _admin_instances_table() -> BFFTable:
    return _bff_admin_all_workflow_instances_table(
        db=None,
        bff_table_request_params=AdminWorkflowInstancesBffTableQuerySchema(),
        allowed_workflow_names={"some_workflow"},
    )


def _admin_users_table() -> BFFTable:
    Role = aliased(WorkflowRole)
    q = (
        select(WorkflowUser)
        .distinct()
        .join(WorkflowUserRole, WorkflowUserRole.user_id == WorkflowUser.id, isouter=True)
        .join(Role, WorkflowUserRole.role_id == Role.id, isouter=True)
    )
    return BFFTable(
        db=None,
        request_params=AdminWorkflowUsersBffTableQuerySchema(),
        query=q,
        field_to_dbfield_map={"full_name": WorkflowUser.full_name, "roles": Role.name},
        default_order_by=WorkflowUser.created_at.desc(),
    )


def test_bff_table_rejects_non_entity_and_aliased_selects():
    """The reductions are only well-defined for a select of exactly one plain
    mapped class — anything else must fail at construction, not as a slow or
    wrong statement later."""
    for query in (select(literal(1).label("one")), select(aliased(WorkflowInstance))):
        with pytest.raises(ValueError):
            BFFTable(
                db=None,
                request_params=MinimalQuerySchema(),
                query=query,
                field_to_dbfield_map={},
                default_order_by=[],
            )


def test_count_query_reduces_entity_select_list_to_the_primary_key():
    bff_table = _admin_instances_table()

    # PK only: no blob columns, no correlated has_task_in_error_state subselect
    # — a subselect in the select list would force MySQL to materialize.
    assert _count_subquery_columns(bff_table) == ["id"]
    # The scoping filter must survive the reduction.
    assert "workflow_instances.name IN" in _compile(bff_table._count_query())


def test_count_query_keeps_distinct_deduplication():
    # A user with several roles multiplies the joined rows; DISTINCT over the
    # primary key inside the subquery keeps the count at one per user.
    assert "SELECT DISTINCT workflow_users.id" in _compile(_admin_users_table()._count_query())


def test_page_ids_query_selects_only_the_primary_key():
    bff_table = _admin_instances_table()

    page_ids_query = bff_table._page_ids_query()

    assert list(page_ids_query.selected_columns.keys()) == ["id"]
    sql = _compile(page_ids_query)
    assert "ORDER BY" in sql
    assert "LIMIT" in sql
    # The user scoping must survive the reduction.
    assert "workflow_instances.name IN" in sql


def test_composite_pk_and_distinct_selects_stay_on_the_direct_page_path():
    """DISTINCT must not be reduced (MySQL rejects DISTINCT with an ORDER BY on
    columns outside the select list); composite primary keys have no single
    IN-able key column. Both also pin the query attributes the routing reads."""
    assert not _admin_users_table()._uses_late_lookup()

    expense_table = BFFTable(
        db=None,
        request_params=MinimalQuerySchema(),
        query=select(DemoExpense),
        field_to_dbfield_map={},
        default_order_by=[],
    )
    assert not expense_table._uses_late_lookup()

    # The blob-heavy lists must page over primary keys.
    assert _admin_instances_table()._uses_late_lookup()
    assert _bff_admin_all_tasks_table(
        db=None,
        bff_table_request_params=AdminWorkflowInstanceTasksBffTableQuerySchema(),
        allowed_workflow_names={"wf"},
    )._uses_late_lookup()


def test_page_query_defers_instance_blobs_but_keeps_the_error_flag():
    bff_table = _admin_instances_table()

    sql = _compile(bff_table.query)

    assert "workflow_instances.data" not in sql
    assert "workflow_instances.lane_mapping" not in sql
    # has_task_in_error_state is shown in the list, so its subselect stays in
    # the row query (bounded by the page size, unlike the count).
    assert "EXISTS" in sql.upper()


def test_instance_list_load_does_not_select_task_payload_blobs(db_engine_ctx):
    """The task lists are selectin-loaded in separate statements, so the main
    page-query compile cannot see them — capture the SQL a real list load
    emits and check the blob columns stayed deferred there too."""
    with db_engine_ctx():
        from actidoo_wfe.database import SessionLocal

        db = SessionLocal()
        instance = WorkflowInstance(id=uuid.uuid4(), name="wf", title="t", lane_mapping={}, data={}, is_completed=False)
        task = WorkflowInstanceTask(
            id=uuid.uuid4(),
            workflow_instance=instance,
            name="t1",
            title="t1",
            state=1,
            state_ready=True,
            data={"k": "v"},
            jsonschema={},
            uischema={},
        )
        db.add_all([instance, task])
        db.commit()

        statements = []

        def capture(conn, cursor, statement, parameters, context, executemany):
            statements.append(statement)

        engine = db.get_bind()
        event.listen(engine, "before_cursor_execute", capture)
        try:
            rows = db.execute(select(WorkflowInstance).options(*_instance_list_loader_options())).scalars().all()
        finally:
            event.remove(engine, "before_cursor_execute", capture)

        assert rows
        task_selects = [s for s in statements if "FROM workflow_instance_tasks" in s]
        assert task_selects
        for sql in task_selects:
            assert "workflow_instance_tasks.data" not in sql
            assert "workflow_instance_tasks.jsonschema" not in sql
            assert "workflow_instance_tasks.uischema" not in sql
            assert "workflow_instance_tasks.error_stacktrace" not in sql


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
        )
        for i in range(count)
    ]
    db.add_all(users + [instance] + tasks)
    db.commit()
    return instance, tasks


def test_page_load_delivers_the_requested_slice_in_sort_order(db_engine_ctx):
    """Sorting over a joined alias column, offset and count — asserted against
    the seeded ground truth."""
    with db_engine_ctx():
        from actidoo_wfe.database import SessionLocal

        db = SessionLocal()
        _, tasks = _seed_tasks_with_assigned_users(db, count=4)

        bff_table = _bff_admin_all_tasks_table(
            db=db,
            bff_table_request_params=AdminWorkflowInstanceTasksBffTableQuerySchema(
                sort=["assigned_user___full_name.asc"],
                limit=2,
                offset=1,
            ),
            allowed_workflow_names={"wf"},
        )

        page = bff_table.get_paginated_data()

        # The assignees' full names sort in task index order, so the page
        # behind offset 1 with limit 2 is exactly tasks[1:3].
        assert [item.id for item in page.items] == [task.id for task in tasks[1:3]]
        assert page.count == 4


def test_all_tasks_page_load_avoids_instance_blobs_and_lazy_user_loads(db_engine_ctx):
    """The admin task list ships the task payloads (list API), but must not
    drag the instances' workflow-state blobs along, must batch created_by
    instead of lazy-loading it per instance, and must page over primary keys
    first."""
    with db_engine_ctx():
        from actidoo_wfe.database import SessionLocal
        from actidoo_wfe.wf import views

        db = SessionLocal()
        _seed_tasks_with_assigned_users(db, count=2)

        statements = []

        def capture(conn, cursor, statement, parameters, context, executemany):
            statements.append(statement)

        engine = db.get_bind()
        event.listen(engine, "before_cursor_execute", capture)
        try:
            result = views.bff_admin_get_all_tasks(
                db=db,
                bff_table_request_params=AdminWorkflowInstanceTasksBffTableQuerySchema(),
                allowed_workflow_names={"wf"},
            )
        finally:
            event.remove(engine, "before_cursor_execute", capture)

        assert result.COUNT == 2
        assert len(result.ITEMS) == 2

        # The page is looked up over bare primary keys.
        pk_page_selects = [s for s in statements if s.startswith("SELECT workflow_instance_tasks.id")]
        assert pk_page_selects
        assert all("jsonschema" not in s for s in pk_page_selects)
        # The task payloads stay part of the row load (list API contract).
        assert any("workflow_instance_tasks.jsonschema" in s for s in statements)
        # The instances' payload blobs are deferred everywhere.
        assert all("workflow_instances.data" not in s and "lane_mapping" not in s for s in statements)
        # Users arrive as batched selectin loads, never as per-row lazy loads.
        user_selects = [s for s in statements if "FROM workflow_users" in s]
        assert user_selects
        assert all("workflow_users.id IN" in s for s in user_selects)
