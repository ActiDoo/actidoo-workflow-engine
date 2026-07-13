# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""Guards for the SQL shape of the BFF instance lists.

The count runs on every page request. MySQL cannot merge a derived table whose
select list contains a subselect, so if the count subquery dragged the entity's
full select list along (blob columns, correlated column_properties like
``has_task_in_error_state``), the whole filtered set would be materialized into
an on-disk temp table per request — the prod regression these tests pin down.
The page-query tests pin the other half of the same fix: the payload blobs stay
deferred out of every list page.
"""

from sqlalchemy import literal, select
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import aliased

import actidoo_wfe.helpers.bff_table as bff_table_module
from actidoo_wfe.helpers.bff_table import BFFTable
from actidoo_wfe.wf.bff.bff_admin import AdminWorkflowInstancesBffTableQuerySchema, AdminWorkflowUsersBffTableQuerySchema
from actidoo_wfe.wf.models import WorkflowInstance, WorkflowInstanceTask, WorkflowRole, WorkflowUser, WorkflowUserRole
from actidoo_wfe.wf.views import _bff_admin_all_workflow_instances_table, _inline_task_loader_options

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


def test_inline_task_loader_defers_task_payload_blobs():
    sql = _compile(select(WorkflowInstanceTask).options(*_inline_task_loader_options()))

    assert "workflow_instance_tasks.id" in sql
    assert "workflow_instance_tasks.data" not in sql
    assert "workflow_instance_tasks.jsonschema" not in sql
    assert "workflow_instance_tasks.uischema" not in sql
    assert "workflow_instance_tasks.error_stacktrace" not in sql
