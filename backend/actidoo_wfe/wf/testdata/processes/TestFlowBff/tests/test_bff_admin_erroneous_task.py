# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""Admin retry of an erroneous task.

``bff_admin_execute_erroneous_task`` re-runs a step that ended in error. Three
things can go wrong around that, and the tests below pin the answer for each:

* the step fails again, which must not be reported as success,
* the step was already completed by an earlier request, which must be a clean
  rejection and not a traceback,
* two retries overlap on one instance, which must not surface the database's
  lock wait timeout.

The last two use ``TestFlowBff``'s crash task with the switches in its module:
``CRASH`` decides whether a run raises, ``HOLD_UNTIL`` keeps a successful run
inside its request so a second request can overlap with it.
"""

import threading
import time
import uuid

import pytest

from actidoo_wfe.database import SessionLocal, setup_db
from actidoo_wfe.settings import settings
from actidoo_wfe.wf.bff.bff_admin_schema import GetAllTasksResponse
from actidoo_wfe.wf.testdata.processes import TestFlowBff as workflow_module
from actidoo_wfe.wf.tests.helpers.client import Client
from actidoo_wfe.wf.tests.helpers.overrides import disable_role_check, override_get_user
from actidoo_wfe.wf.tests.helpers.workflow_dummy import WorkflowDummy

setup_db(settings=settings)

WF_NAME = "TestFlowBff"
FORM1_DATA_TRIGGER_ERROR = {"required_text": "ok", "short_code": "abc", "trigger_error": True}

# The engine sets ``innodb_lock_wait_timeout`` to 3 s per connection. A second
# retry that waits on the instance row for longer than that fails with a lock
# wait timeout, so the first retry has to hold the row for longer.
LOCK_WAIT_TIMEOUT_SECONDS = 3


@pytest.fixture
def crash_task(monkeypatch):
    """Fresh switches for every test; the defaults make the task crash."""
    monkeypatch.setattr(workflow_module, "CRASH", True)
    monkeypatch.setattr(workflow_module, "HOLD_UNTIL", None)
    monkeypatch.setattr(workflow_module, "RUNS", [])
    return workflow_module


def _start_with_erroneous_task(db) -> tuple[WorkflowDummy, uuid.UUID]:
    workflow = WorkflowDummy(
        db_session=db,
        users_with_roles={"admin": ["wf-admin"], "initiator": ["wf-user"]},
        workflow_name=WF_NAME,
        start_user="initiator",
    )
    workflow.user("initiator").submit(
        task_data=FORM1_DATA_TRIGGER_ERROR,
        workflow_instance_id=workflow.workflow_instance_id,
    )
    client = Client()
    with override_get_user(client=client, user=workflow.user("admin").user), disable_role_check(client):
        tasks = _all_tasks(client, f_workflow_instance___id=str(workflow.workflow_instance_id), f_state_error=True)
    erroneous = [task for task in tasks if task.state_error]
    assert len(erroneous) == 1, "the crash task should be the one erroneous task"
    # Count only the runs the retries cause, not the crash that set the task up.
    workflow_module.RUNS.clear()
    return workflow, erroneous[0].id


def _all_tasks(client: Client, **filters):
    """The table filters travel as query parameters, not in the body."""
    response = client.root_client.post(
        url=client.root_client.app.url_path_for("bff_admin_get_all_tasks"),
        params=filters,
        json={},
    )
    assert response.status_code == 200
    return GetAllTasksResponse.model_validate(response.json()).ITEMS


def _retry(client: Client, task_id: uuid.UUID) -> tuple[int, dict]:
    return client.post(name="bff_admin_execute_erroneous_task", json={"task_id": str(task_id)})


def _get_task(client: Client, task_id: uuid.UUID):
    tasks = [task for task in _all_tasks(client, f_id=str(task_id)) if task.id == task_id]
    assert len(tasks) == 1
    return tasks[0]


class TestRetryOutcome:
    def test_a_retry_that_fails_again_is_not_answered_with_200(self, db_engine_ctx, crash_task):
        """The frontend maps 200 to the "task executed" toast. A step that raised
        again must therefore not get a 200, and the failure has to stay on record."""
        with db_engine_ctx():
            workflow, task_id = _start_with_erroneous_task(SessionLocal())

            client = Client()
            with override_get_user(client=client, user=workflow.user("admin").user), disable_role_check(client):
                status, _ = _retry(client, task_id)
                task = _get_task(client, task_id)

            assert len(crash_task.RUNS) == 1, "the retry should have run the step once"
            assert status == 409, f"a retry that failed again was answered with {status}"
            assert task.state_error, "the step is still erroneous"
            assert task.error_stacktrace is not None and "intentional crash" in task.error_stacktrace

    def test_a_retry_that_succeeds_completes_the_step(self, db_engine_ctx, crash_task):
        with db_engine_ctx():
            workflow, task_id = _start_with_erroneous_task(SessionLocal())
            crash_task.CRASH = False

            client = Client()
            with override_get_user(client=client, user=workflow.user("admin").user), disable_role_check(client):
                status, _ = _retry(client, task_id)
                task = _get_task(client, task_id)

            assert status == 200
            assert not task.state_error
            assert task.state_completed
            assert task.error_stacktrace is None
            # Read through the endpoint: the dummy's own session still sees its
            # pre-retry snapshot.
            assert task.workflow_instance.is_completed

    def test_retrying_a_step_that_already_succeeded_is_rejected_without_a_500(self, db_engine_ctx, crash_task):
        """A second click while the first request already completed the step:
        the second finds nothing to retry. That is a 409, not a traceback."""
        with db_engine_ctx():
            workflow, task_id = _start_with_erroneous_task(SessionLocal())
            crash_task.CRASH = False

            client = Client()
            with override_get_user(client=client, user=workflow.user("admin").user), disable_role_check(client):
                status, _ = _retry(client, task_id)
                assert status == 200

                try:
                    status, _ = _retry(client, task_id)
                except Exception as error:  # noqa: BLE001 - any leak is the failure under test
                    pytest.fail(f"the second retry crashed the request instead of answering: {error!r}")

            assert status == 409, f"a retry of a completed step was answered with {status}"
            assert len(crash_task.RUNS) == 1, "the step must not run a second time"


class TestOverlappingRetries:
    def test_two_overlapping_retries_run_the_step_once_and_both_get_an_answer(self, db_engine_ctx, crash_task):
        """The first retry is slow (a long external call) and holds the instance
        row for longer than the lock wait timeout. The second retry must not
        surface the database's ``Lock wait timeout exceeded`` as a 500, and the
        step must run exactly once."""
        with db_engine_ctx():
            workflow, task_id = _start_with_erroneous_task(SessionLocal())
            crash_task.CRASH = False
            release = threading.Event()
            crash_task.HOLD_UNTIL = release

            results: dict[str, tuple[int, object]] = {}
            failures: dict[str, BaseException] = {}

            def retry(label: str) -> None:
                try:
                    results[label] = _retry(Client(), task_id)
                except BaseException as error:  # noqa: BLE001 - surfaced in the main thread below
                    failures[label] = error

            client = Client()
            with override_get_user(client=client, user=workflow.user("admin").user), disable_role_check(client):
                first = threading.Thread(target=retry, args=("first",))
                first.start()
                deadline = time.monotonic() + 10
                while not crash_task.RUNS and time.monotonic() < deadline:
                    time.sleep(0.05)
                assert crash_task.RUNS, "the first retry never reached the step"

                second = threading.Thread(target=retry, args=("second",))
                second.start()
                # Long enough for the second request to run into the lock wait timeout.
                time.sleep(LOCK_WAIT_TIMEOUT_SECONDS + 1)
                release.set()

                first.join(timeout=30)
                second.join(timeout=30)
                assert not first.is_alive() and not second.is_alive(), "a retry did not finish"

                task = _get_task(client, task_id)

            for label, error in failures.items():
                raise AssertionError(f"the {label} retry crashed the request instead of answering") from error

            assert results["first"][0] == 200, f"the first retry answered {results['first']}"
            assert results["second"][0] in (200, 409), f"the second retry answered {results['second']}"
            assert len(crash_task.RUNS) == 1, f"the step ran {len(crash_task.RUNS)} times instead of once"
            assert task.state_completed and not task.state_error
