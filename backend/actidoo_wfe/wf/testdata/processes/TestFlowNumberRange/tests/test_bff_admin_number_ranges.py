# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""The read-only administrative view of number ranges (ADR 012).

Visibility follows workflow ownership: a global admin sees every range, the owner
of a workflow that declares a range sees that range, and everybody else sees
nothing - including the owner of some *other* workflow.
"""

import pytest

from actidoo_wfe.database import SessionLocal
from actidoo_wfe.wf.bff.bff_admin_schema import GetNumberRangeAllocationsResponse, GetNumberRangesResponse
from actidoo_wfe.wf.testdata.processes import TestFlowNumberRange as workflow_module
from actidoo_wfe.wf.tests.helpers.client import Client
from actidoo_wfe.wf.tests.helpers.overrides import disable_role_check, override_get_user
from actidoo_wfe.wf.tests.helpers.workflow_dummy import WorkflowDummy

WF_NAME = "TestFlowNumberRange"
RANGE = "DemoCaseNumber"


@pytest.fixture(autouse=True)
def _reset_module_state():
    workflow_module.CRASH_AFTER_ALLOCATION = False
    workflow_module.ISSUED.clear()
    yield
    workflow_module.CRASH_AFTER_ALLOCATION = False
    workflow_module.ISSUED.clear()


def _start():
    dummy = WorkflowDummy(
        db_session=SessionLocal(),
        users_with_roles={
            "admin": ["wf-admin"],
            "owner": ["wf-user", "wf-owner-testflownumberrange"],
            "other_owner": ["wf-user", "wf-owner-testflowworkflowownerpermissions"],
            "initiator": ["wf-user"],
        },
        workflow_name=WF_NAME,
        start_user="initiator",
    )
    dummy.assert_completed()  # two numbers issued: CASE-01000, CASE-01001
    return dummy


def _ranges(client):
    return client.get(name="bff_admin_get_number_ranges", cls=GetNumberRangesResponse)


def _allocations(client, name=RANGE, **params):
    path = client.root_client.app.url_path_for("bff_admin_get_number_range_allocations")
    response = client.root_client.post(path, params={"range_name": name, **params})
    parsed = GetNumberRangeAllocationsResponse.model_validate(response.json()) if response.status_code == 200 else None
    return response.status_code, parsed


class TestVisibility:
    def test_a_global_admin_sees_the_range_with_its_workflows_and_scope(self, db_engine_ctx):
        with db_engine_ctx():
            dummy = _start()
            client = Client()
            with override_get_user(client=client, user=dummy.user("admin").user), disable_role_check(client):
                status, listed = _ranges(client)
            assert status == 200
            ranges = {r.name: r for r in listed.ranges}
            assert ranges[RANGE].workflows == [WF_NAME]
            assert ranges[RANGE].table == "ext_demo_case_number"
            (scope,) = ranges[RANGE].scopes
            assert (scope.scope_key, scope.count, scope.highest_value, scope.last_formatted) == ("", 2, 1001, "CASE-01001")
            assert scope.last_issued_at is not None

    def test_the_owner_of_a_declaring_workflow_sees_it(self, db_engine_ctx):
        with db_engine_ctx():
            dummy = _start()
            client = Client()
            with override_get_user(client=client, user=dummy.user("owner").user), disable_role_check(client):
                _, listed = _ranges(client)
                status, page = _allocations(client)
            assert [r.name for r in listed.ranges] == [RANGE]
            assert status == 200 and page.COUNT == 2

    def test_the_owner_of_another_workflow_sees_nothing(self, db_engine_ctx):
        with db_engine_ctx():
            dummy = _start()
            client = Client()
            with override_get_user(client=client, user=dummy.user("other_owner").user), disable_role_check(client):
                _, listed = _ranges(client)
                status, _ = _allocations(client)
            assert listed.ranges == []
            assert status == 403

    def test_a_plain_user_sees_nothing(self, db_engine_ctx):
        with db_engine_ctx():
            dummy = _start()
            client = Client()
            with override_get_user(client=client, user=dummy.user("initiator").user), disable_role_check(client):
                _, listed = _ranges(client)
                status, _ = _allocations(client)
            assert listed.ranges == []
            assert status == 403


class TestAllocationLog:
    def test_lists_newest_first_and_links_each_number_to_its_instance_and_step(self, db_engine_ctx):
        with db_engine_ctx():
            dummy = _start()
            client = Client()
            with override_get_user(client=client, user=dummy.user("admin").user), disable_role_check(client):
                status, page = _allocations(client)
            assert status == 200
            assert page.COUNT == 2
            assert [i.formatted for i in page.ITEMS] == ["CASE-01001", "CASE-01000"]
            assert {i.workflow_instance_id for i in page.ITEMS} == {dummy.workflow_instance_id}
            # Both came from the same step, told apart by the draw counter.
            assert len({i.workflow_instance_task_id for i in page.ITEMS}) == 1
            assert sorted(i.alloc_key for i in page.ITEMS) == ["#0", "#1"]

    def test_table_filter_paging_and_unknown_range(self, db_engine_ctx):
        with db_engine_ctx():
            dummy = _start()
            client = Client()
            with override_get_user(client=client, user=dummy.user("admin").user), disable_role_check(client):
                _, filtered = _allocations(client, f_formatted="CASE-01000")
                _, paged = _allocations(client, limit=1, offset=1)
                unknown, _ = _allocations(client, name="NoSuchRange")
                not_a_range, _ = _allocations(client, name="DemoExpense")
            assert [i.formatted for i in filtered.ITEMS] == ["CASE-01000"] and filtered.COUNT == 1
            assert paged.COUNT == 2 and [i.formatted for i in paged.ITEMS] == ["CASE-01000"]
            assert unknown == 404
            assert not_a_range == 404
