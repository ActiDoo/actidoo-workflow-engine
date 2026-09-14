# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""Admin retry of an erroneous task.

``bff_admin_execute_erroneous_task`` re-runs a step that ended in error. Five
things can go wrong around that, and the tests below pin the answer for each:

* the step fails again, which must not be reported as success,
* the step runs but a later step fails, which must not be reported as the step
  failing again,
* the step was already completed by an earlier request, which must be a clean
  rejection and not a traceback,
* two retries overlap on one instance, which must not surface the database's
  lock wait timeout,
* the retried step raises instead of returning ``False``, which only service
  tasks do for themselves; a script task hands the exception up.

They steer ``TestFlowBff`` the way an administrator experiences it: the
external system the crash task calls comes back (``probe.external_down``), or
the task data gets corrected before the retry (``crash_follow_up``,
``crash_script``). ``probe`` also counts the crash task's runs and can hold a
successful run inside its request so a second request can overlap with it.
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


@pytest.fixture(autouse=True)
def probe():
    """The workflow's outside world and run counter; every test starts with the
    external system down and leaves nothing behind for the next."""
    yield workflow_module.probe
    workflow_module.probe.reset()


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
    workflow_module.probe.reset()
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


def _edit_task_data(client: Client, task_id: uuid.UUID, **flags) -> None:
    """What an administrator does in the task's data editor before a retry:
    take the data as it is and set ``flags`` for what should fail next."""
    data = {**(_get_task(client, task_id).data or {}), **flags}
    status, _ = client.post(name="bff_admin_replace_task_data", json={"task_id": str(task_id), "data": data})
    assert status == 200, f"replacing the task data was answered with {status}"


class TestRetryOutcome:
    def test_a_retry_that_fails_again_is_not_answered_with_200(self, db_engine_ctx, probe):
        """The frontend maps 200 to the "task executed" toast. A step that raised
        again must therefore not get a 200, and the failure has to stay on record."""
        with db_engine_ctx():
            workflow, task_id = _start_with_erroneous_task(SessionLocal())

            client = Client()
            with override_get_user(client=client, user=workflow.user("admin").user), disable_role_check(client):
                status, body = _retry(client, task_id)
                task = _get_task(client, task_id)

            assert probe.runs == 1, "the retry should have run the step once"
            assert status == 409, f"a retry that failed again was answered with {status}"
            assert body["code"] == "task_failed_again"
            assert task.state_error, "the step is still erroneous"
            assert task.error_stacktrace is not None and "intentional crash" in task.error_stacktrace

    def test_a_failing_later_step_is_not_reported_as_the_retried_task_failing(self, db_engine_ctx, probe):
        """The retried step runs to completion, the step behind it raises.

        Telling the administrator that *their* task failed again would be
        wrong twice over: the task is done, and its error message is gone.
        """
        with db_engine_ctx():
            workflow, task_id = _start_with_erroneous_task(SessionLocal())

            client = Client()
            with override_get_user(client=client, user=workflow.user("admin").user), disable_role_check(client):
                probe.external_down = False
                _edit_task_data(client, task_id, crash_follow_up=True)
                status, body = _retry(client, task_id)
                task = _get_task(client, task_id)
                all_tasks = _all_tasks(client, f_workflow_instance___id=str(workflow.workflow_instance_id))

            assert task.state_completed and not task.state_error, "the retried step itself succeeded"
            assert status == 409, f"a failing later step was answered with {status}"
            assert body["code"] == "follow_up_task_failed", f"reported as {body['code']}"

            erroneous = [item.name for item in all_tasks if item.state_error]
            assert erroneous == ["FollowUpTask"], f"the error belongs to the later step, found {erroneous}"

    def test_a_retried_task_that_raises_is_reported_as_failed_again(self, db_engine_ctx, probe):
        """A service task catches its own exception and returns ``False``. A
        script task does not: its exception leaves ``task.run()``. The retry has
        to treat both the same - error state, fresh stack trace, 409 - and must
        not roll the request back, or the new stack trace is lost."""
        with db_engine_ctx():
            workflow, crash_task_id = _start_with_erroneous_task(SessionLocal())

            client = Client()
            with override_get_user(client=client, user=workflow.user("admin").user), disable_role_check(client):
                # Gets the crash task done and leaves the script step in error.
                probe.external_down = False
                _edit_task_data(client, crash_task_id, crash_script=True)
                status, body = _retry(client, crash_task_id)
                assert (status, body["code"]) == (409, "follow_up_task_failed")
                instance_tasks = _all_tasks(client, f_workflow_instance___id=str(workflow.workflow_instance_id))
                script_step = next(item for item in instance_tasks if item.name == "ScriptStep")
                assert script_step.state_error

                try:
                    status, body = _retry(client, script_step.id)
                except Exception as error:  # noqa: BLE001 - any leak is the failure under test
                    pytest.fail(f"the retry of a raising task crashed the request instead of answering: {error!r}")
                task = _get_task(client, script_step.id)

                assert status == 409, f"a retry that raised again was answered with {status}"
                assert body["code"] == "task_failed_again"
                assert task.state_error
                assert task.error_stacktrace is not None and "intentional crash of the script step" in task.error_stacktrace

                _edit_task_data(client, script_step.id, crash_script=False)
                status, _ = _retry(client, script_step.id)
                task = _get_task(client, script_step.id)

            assert status == 200
            assert task.state_completed and task.error_stacktrace is None
            assert task.workflow_instance.is_completed

    def test_a_retry_that_succeeds_completes_the_step(self, db_engine_ctx, probe):
        with db_engine_ctx():
            workflow, task_id = _start_with_erroneous_task(SessionLocal())

            client = Client()
            with override_get_user(client=client, user=workflow.user("admin").user), disable_role_check(client):
                probe.external_down = False
                status, _ = _retry(client, task_id)
                task = _get_task(client, task_id)

            assert status == 200
            assert not task.state_error
            assert task.state_completed
            assert task.error_stacktrace is None
            # Read through the endpoint: the dummy's own session still sees its
            # pre-retry snapshot.
            assert task.workflow_instance.is_completed

    def test_retrying_a_step_that_already_succeeded_is_rejected_without_a_500(self, db_engine_ctx, probe):
        """A second click while the first request already completed the step:
        the second finds nothing to retry. That is a 409, not a traceback."""
        with db_engine_ctx():
            workflow, task_id = _start_with_erroneous_task(SessionLocal())

            client = Client()
            with override_get_user(client=client, user=workflow.user("admin").user), disable_role_check(client):
                probe.external_down = False
                status, _ = _retry(client, task_id)
                assert status == 200

                try:
                    status, _ = _retry(client, task_id)
                except Exception as error:  # noqa: BLE001 - any leak is the failure under test
                    pytest.fail(f"the second retry crashed the request instead of answering: {error!r}")

            assert status == 409, f"a retry of a completed step was answered with {status}"
            assert probe.runs == 1, "the step must not run a second time"


class TestOverlappingRetries:
    def test_two_overlapping_retries_run_the_step_once_and_both_get_an_answer(self, db_engine_ctx, probe):
        """The first retry is slow (a long external call) and holds the instance
        row for longer than the lock wait timeout. The second retry must not
        surface the database's ``Lock wait timeout exceeded`` as a 500, and the
        step must run exactly once."""
        with db_engine_ctx():
            workflow, task_id = _start_with_erroneous_task(SessionLocal())
            probe.external_down = False
            release = threading.Event()
            probe.hold_until = release

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
                second = threading.Thread(target=retry, args=("second",))
                try:
                    first.start()
                    assert probe.started.wait(timeout=10), "the first retry never reached the step"

                    second.start()
                    # Long enough for the second request to run into the lock wait timeout.
                    time.sleep(LOCK_WAIT_TIMEOUT_SECONDS + 1)
                finally:
                    # Also on a failed assertion: the first retry must not keep
                    # holding the instance row for the next test.
                    release.set()

                first.join(timeout=30)
                second.join(timeout=30)
                assert not first.is_alive() and not second.is_alive(), "a retry did not finish"

                task = _get_task(client, task_id)

            for label, error in failures.items():
                raise AssertionError(f"the {label} retry crashed the request instead of answering") from error

            assert results["first"][0] == 200, f"the first retry answered {results['first']}"
            assert results["second"][0] in (200, 409), f"the second retry answered {results['second']}"
            assert probe.runs == 1, f"the step ran {probe.runs} times instead of once"
            assert task.state_completed and not task.state_error
