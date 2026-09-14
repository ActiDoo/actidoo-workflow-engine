# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""TestFlowBff — synthetic workflow exclusively for BFF endpoint tests.

Form1 collects a text, a dynamic select, an upload, an optional note, and a
trigger_error boolean. The gateway routes a `trigger_error == true` submission
to a service task that intentionally raises, putting the task into state_error
and giving `bff_admin_execute_erroneous_task` something real to operate on. A
second service task sits behind it, so a test can also let the retried task
succeed and the step after it fail.

The module-level switches below let a test decide what the two tasks do. They
are read at call time; tests set them through ``monkeypatch``.
"""

import threading

from actidoo_wfe.wf.service_task_helper import ServiceTaskHelper

#: ``True`` (the default) makes every run of the crash task raise. A test sets
#: it to ``False`` before an admin retry to let the step succeed.
CRASH = True

#: When set, a successful run blocks here until the event fires. That keeps the
#: retry inside its request, holding the instance row lock, so a second retry
#: can overlap with it.
HOLD_UNTIL: threading.Event | None = None

#: One entry per run of the crash task, so a test can count how often the step
#: actually ran.
RUNS: list = []

#: Makes the step *behind* the crash task raise. Off by default, so the crash
#: task is the only thing that can fail.
FOLLOW_UP_CRASH = False


def service_bff_crash_task(sth: ServiceTaskHelper):
    RUNS.append(sth.task_uuid)
    if CRASH:
        raise RuntimeError("intentional crash for BFF endpoint tests")
    if HOLD_UNTIL is not None:
        HOLD_UNTIL.wait(timeout=30)


def service_bff_follow_up_task(sth: ServiceTaskHelper):
    if FOLLOW_UP_CRASH:
        raise RuntimeError("intentional crash of the step after the crash task")


__all__ = ["service_bff_crash_task", "service_bff_follow_up_task"]
