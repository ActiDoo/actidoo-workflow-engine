# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""Guards for the SQL shape of the BFF instance lists.

The count runs on every page request. MySQL cannot merge a derived table whose
select list contains a subselect, so a count subquery carrying the entity's
full select list (blob columns, correlated column_properties like
``has_task_in_error_state``) materializes the whole filtered set into an
on-disk temp table on every request. These tests pin both halves of the
guarantee: the count subquery stays reduced to the primary key, and the
payload blobs stay deferred out of every list page.
"""

import uuid

from sqlalchemy import event, literal, select
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import aliased

import actidoo_wfe.helpers.bff_table as bff_table_module
from actidoo_wfe.helpers.bff_table import BFFTable
from actidoo_wfe.wf.bff.bff_admin import AdminWorkflowInstancesBffTableQuerySchema, AdminWorkflowUsersBffTableQuerySchema
from actidoo_wfe.wf.models import WorkflowInstance, WorkflowInstanceTask, WorkflowRole, WorkflowUser, WorkflowUserRole
from actidoo_wfe.wf.views import _bff_admin_all_workflow_instances_table, _instance_list_loader_options

# Schema without filter/sort fields, for count-fallback tests whose queries do
# not export the admin columns.
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


def test_count_query_reduces_entity_select_list_to_the_primary_key():
    bff_table = _admin_instances_table()

    # PK only: no blob columns, no correlated has_task_in_error_state subselect
    # — a subselect in the select list would force MySQL to materialize.
    assert _count_subquery_columns(bff_table) == ["id"]
    # The scoping filter must survive the reduction.
    assert "workflow_instances.name IN" in _compile(bff_table._count_query())


def test_count_query_keeps_distinct_deduplication():
    Role = aliased(WorkflowRole)
    q = (
        select(WorkflowUser)
        .distinct()
        .join(WorkflowUserRole, WorkflowUserRole.user_id == WorkflowUser.id, isouter=True)
        .join(Role, WorkflowUserRole.role_id == Role.id, isouter=True)
    )

    bff_table = BFFTable(
        db=None,
        request_params=AdminWorkflowUsersBffTableQuerySchema(),
        query=q,
        field_to_dbfield_map={"full_name": WorkflowUser.full_name, "roles": Role.name},
        default_order_by=WorkflowUser.created_at.desc(),
    )

    # A user with several roles multiplies the joined rows; DISTINCT over the
    # primary key inside the subquery keeps the count at one per user.
    assert "SELECT DISTINCT workflow_users.id" in _compile(bff_table._count_query())


def test_count_query_falls_back_for_an_aliased_entity_select():
    bff_table = BFFTable(
        db=None,
        request_params=MinimalQuerySchema(),
        query=select(aliased(WorkflowInstance)),
        field_to_dbfield_map={},
        default_order_by=[],
    )

    # An aliased entity has no reducible mapper primary key; the count must
    # keep the full select list instead of crashing.
    assert "data" in _count_subquery_columns(bff_table)


def test_count_query_falls_back_for_a_non_entity_select():
    bff_table = BFFTable(
        db=None,
        request_params=MinimalQuerySchema(),
        query=select(literal(1).label("one")),
        field_to_dbfield_map={},
        default_order_by=[],
    )

    assert _count_subquery_columns(bff_table) == ["one"]


def test_page_query_defers_instance_blobs_but_keeps_the_error_flag():
    bff_table = _admin_instances_table()

    sql = _compile(bff_table._paginate(bff_table.query))

    assert "workflow_instances.data" not in sql
    assert "workflow_instances.lane_mapping" not in sql
    # has_task_in_error_state is shown in the list, so its subselect stays in
    # the page query (bounded by the page size, unlike the count).
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
