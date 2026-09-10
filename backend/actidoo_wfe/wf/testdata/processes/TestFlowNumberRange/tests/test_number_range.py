# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""Number ranges end to end through a workflow (ADR 012).

``NumberRangeMixin.allocate`` itself is covered by ``wf/tests/test_numbering.py``.
What is tested here is the wiring: ``sth.next_number``, the ``DATA_MODELS`` gate,
the draw counter that lets one step issue several numbers - and the case the whole
idempotency design exists for, an administrator re-running a step that failed
*after* it had issued its numbers.
"""

import types
import uuid

import pytest

from actidoo_wfe.database import SessionLocal, SessionMaker
from actidoo_wfe.wf import repository
from actidoo_wfe.wf.bff.bff_admin_schema import GetAllTasksResponse
from actidoo_wfe.wf.constants import DATA_KEY_WORKFLOW_INSTANCE_SUBTITLE
from actidoo_wfe.wf.exceptions import DataModelAccessDeniedError
from actidoo_wfe.wf.service_task_helper import ServiceTaskHelper
from actidoo_wfe.wf.testdata.datamodels.demo_case_number_model import DemoCaseNumber
from actidoo_wfe.wf.testdata.processes import TestFlowNumberRange as workflow_module
from actidoo_wfe.wf.tests.helpers.client import Client
from actidoo_wfe.wf.tests.helpers.overrides import disable_role_check, override_get_user
from actidoo_wfe.wf.tests.helpers.workflow_dummy import WorkflowDummy

WF_NAME = "TestFlowNumberRange"


@pytest.fixture(autouse=True)
def _reset_module_state():
    workflow_module.CRASH_AFTER_ALLOCATION = False
    workflow_module.ISSUED.clear()
    yield
    workflow_module.CRASH_AFTER_ALLOCATION = False
    workflow_module.ISSUED.clear()


def _start(db):
    return WorkflowDummy(
        db_session=db,
        users_with_roles={"admin": ["wf-admin"], "initiator": ["wf-user"]},
        workflow_name=WF_NAME,
        start_user="initiator",
    )


def _rows():
    with SessionMaker() as db:
        return db.query(DemoCaseNumber).order_by(DemoCaseNumber.value).all()


def _helper(*, allowed):
    """A ServiceTaskHelper without a real run - enough for the access gates."""
    stub_workflow = types.SimpleNamespace(task_tree=types.SimpleNamespace(id=uuid.uuid4()))
    return ServiceTaskHelper(
        workflow=stub_workflow,
        task_data={},
        task_to_user_mapping={},
        task_uuid=uuid.uuid4(),
        allowed_data_models=allowed,
    )


class TestIssuing:
    def test_one_step_issues_two_distinct_numbers_and_the_run_completes(self, db_engine_ctx):
        with db_engine_ctx():
            dummy = _start(SessionLocal())
            dummy.assert_completed()

            # Two draws without an explicit key are counted (#0, #1), so they are
            # two numbers rather than the same one handed back twice.
            assert workflow_module.ISSUED == [("CASE-01000", "CASE-01001")]
            assert [(row.value, row.formatted) for row in _rows()] == [
                (1000, "CASE-01000"),
                (1001, "CASE-01001"),
            ]

            with SessionMaker() as db:
                instance = repository.load_workflow_instance(db=db, workflow_id=dummy.workflow_instance_id)
            assert instance.get_data(DATA_KEY_WORKFLOW_INSTANCE_SUBTITLE) == "CASE-01000"

    def test_a_second_run_continues_the_sequence(self, db_engine_ctx):
        with db_engine_ctx():
            _start(SessionLocal()).assert_completed()
            _start(SessionLocal()).assert_completed()
            assert [row.formatted for row in _rows()] == [
                "CASE-01000",
                "CASE-01001",
                "CASE-01002",
                "CASE-01003",
            ]

    def test_every_row_records_its_instance_and_step(self, db_engine_ctx):
        """The range is its own allocation log - that is the point of the shape.

        Nothing exposes it through the data API; the record is the table.
        """
        with db_engine_ctx():
            dummy = _start(SessionLocal())
            dummy.assert_completed()

            rows = _rows()
            assert {row.workflow_instance_id for row in rows} == {dummy.workflow_instance_id}
            # Both numbers came from the same step, told apart by the draw counter.
            assert len({row.workflow_instance_task_id for row in rows}) == 1
            assert sorted(row.alloc_key for row in rows) == ["#0", "#1"]
            assert all(row.created_at is not None for row in rows)


class TestAdminRetry:
    def test_a_retry_hands_back_the_numbers_instead_of_issuing_new_ones(self, db_engine_ctx):
        """The step fails *after* it issued its numbers - the case idempotency exists for.

        The failure does not roll back (the engine catches it and commits the
        request anyway), so the numbers are already in the table when the
        administrator re-runs the step. Without the claim on the task occurrence
        the retry would issue a second pair and leave the first orphaned.
        """
        with db_engine_ctx():
            workflow_module.CRASH_AFTER_ALLOCATION = True
            dummy = _start(SessionLocal())

            issued_first = list(workflow_module.ISSUED)
            assert issued_first == [("CASE-01000", "CASE-01001")]
            assert len(_rows()) == 2

            client = Client()
            with override_get_user(client=client, user=dummy.user("admin").user), disable_role_check(client):
                status, all_tasks = client.post(
                    name="bff_admin_get_all_tasks",
                    json={"f_state_error": True},
                    cls=GetAllTasksResponse,
                )
                assert status == 200
                erroneous = [task for task in all_tasks.ITEMS if task.state_error]
                assert erroneous, "the issuing step should be in state_error"

                workflow_module.CRASH_AFTER_ALLOCATION = False
                status, _ = client.post(
                    name="bff_admin_execute_erroneous_task",
                    json={"task_id": str(erroneous[0].id)},
                    cls=GetAllTasksResponse,
                )
                assert status == 200

            # The function ran a second time from the start ...
            assert len(workflow_module.ISSUED) == 2
            # ... and got exactly the same numbers back ...
            assert workflow_module.ISSUED[1] == workflow_module.ISSUED[0]
            # ... without a second pair of rows.
            assert [row.formatted for row in _rows()] == ["CASE-01000", "CASE-01001"]


class TestAccessGates:
    def test_a_workflow_may_only_use_ranges_it_declared(self, db_engine_ctx):
        with db_engine_ctx():
            helper = _helper(allowed=set())
            with pytest.raises(DataModelAccessDeniedError):
                helper.next_number("DemoCaseNumber")

    def test_a_data_model_that_is_not_a_range_is_rejected(self, db_engine_ctx):
        with db_engine_ctx():
            helper = _helper(allowed={"DemoExpense"})
            with pytest.raises(TypeError) as excinfo:
                helper.next_number("DemoExpense")
            assert "not a number range" in str(excinfo.value)
