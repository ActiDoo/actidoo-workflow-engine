# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""Two submissions that overlap in time on one workflow instance.

A workflow instance is persisted as one serialized blob holding every task of
the run. Task data itself is isolated per task - SpiffWorkflow hands each task a
``deepcopy`` of its parent's data - but that isolation exists only in the object
graph, not in the database: storing any task writes the whole instance back. A
caller that reads the instance, changes one task and writes it back would
therefore discard whatever another caller committed on a *different* task in
the meantime.

The guard against that is the instance row lock: every read-modify-write path
loads through ``repository.load_workflow_instance(_by_task_id)`` with
``for_update=True``, which serializes overlapping writers on the row for the
rest of the transaction. This test overlaps two submissions and asserts that
the second one waits instead of overwriting - remove the lock from
``submit_task_data`` and it goes red with two ready tasks instead of one.

``TestFlow_MultiInstance`` opens three parallel instances of one user task,
which is the cheapest way to get two independently submittable ready tasks on
one instance.
"""

import threading
import uuid

from actidoo_wfe.database import SessionLocal, get_db_contextmanager
from actidoo_wfe.wf import service_application, service_workflow
from actidoo_wfe.wf.tests.helpers.workflow_dummy import WorkflowDummy

WF_NAME = "TestFlow_MultiInstance"

# How long the first submission holds the instance between reading and writing
# it. The second submission blocks on the row lock for the whole window, so it
# can never commit inside it - the wait below always runs out. (Without the
# lock the second submission would commit within milliseconds instead.)
HOLD_TIMEOUT_SECONDS = 2.0


def test_overlapping_submits_on_one_instance_do_not_discard_each_other(db_engine_ctx, mock_send_text_mail, monkeypatch):
    with db_engine_ctx():
        setup_session = SessionLocal()
        workflow = WorkflowDummy(
            db_session=setup_session,
            users_with_roles={"initiator": ["wf-user"]},
            workflow_name=WF_NAME,
            start_user="initiator",
        )
        initiator = workflow.user("initiator")
        instance_id = workflow.workflow_instance_id
        user_id = initiator.user.id

        ready = initiator.get_usertasks(instance_id, 3)
        slow_task_id, fast_task_id = ready[0].id, ready[1].id

        # Assigning writes the blob as well - keep it out of the timed window.
        initiator.assign_task(task_id=slow_task_id)
        initiator.assign_task(task_id=fast_task_id)
        setup_session.commit()

        slow_holds_the_instance = threading.Event()
        fast_has_committed = threading.Event()
        failures: dict[uuid.UUID, Exception] = {}

        original_execute_user_task = service_workflow.execute_user_task

        def execute_user_task_holding_the_instance(workflow_obj, user, task_id, *args, **kwargs):
            """Widen the gap between reading and writing the instance, but only
            for the slow submission."""
            result = original_execute_user_task(workflow_obj, user, task_id, *args, **kwargs)
            if task_id == slow_task_id:
                slow_holds_the_instance.set()
                fast_has_committed.wait(timeout=HOLD_TIMEOUT_SECONDS)
            return result

        def submit(task_id: uuid.UUID, *, announce_commit: bool) -> None:
            try:
                with get_db_contextmanager() as db:
                    service_application.submit_task_data(
                        db=db,
                        user_id=user_id,
                        task_id=task_id,
                        task_data={"myTestField": "testvalue"},
                    )
            except Exception as error:  # surfaced in the main thread below
                failures[task_id] = error
            finally:
                # Fires after the context manager exits, i.e. after the real
                # commit - the slow thread must not wake up any earlier.
                if announce_commit:
                    fast_has_committed.set()

        monkeypatch.setattr(service_workflow, "execute_user_task", execute_user_task_holding_the_instance)

        slow = threading.Thread(target=submit, args=(slow_task_id,), kwargs={"announce_commit": False})
        slow.start()
        # The fast submission must try to read the instance while the slow one
        # is still holding it, so wait until the slow one is past its own read.
        assert slow_holds_the_instance.wait(timeout=10), "the slow submission never reached execute_user_task"

        fast = threading.Thread(target=submit, args=(fast_task_id,), kwargs={"announce_commit": True})
        fast.start()

        fast.join(timeout=30)
        slow.join(timeout=30)
        assert not slow.is_alive() and not fast.is_alive(), "a submission did not finish"

        for task_id, error in failures.items():
            raise AssertionError(f"submission of task {task_id} failed") from error

        # Three parallel tasks, two of them submitted: exactly one may remain.
        # Two would mean the later blob write reverted the other submission's
        # task to ready - the lost update the instance row lock exists to
        # prevent.
        remaining = service_application.get_usertasks_for_user_id(
            db=SessionLocal(),
            user_id=user_id,
            workflow_instance_id=instance_id,
            state="ready",
        )
        assert len(remaining) == 1, (
            f"expected one ready task after two overlapping submissions, found {len(remaining)} - "
            "a submission was overwritten; is the for_update lock still taken on every "
            "read-modify-write path?"
        )
