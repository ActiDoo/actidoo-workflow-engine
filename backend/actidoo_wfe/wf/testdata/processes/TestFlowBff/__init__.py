# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""TestFlowBff — synthetic workflow exclusively for BFF endpoint tests.

Form1 collects a text, a dynamic select, an upload, an optional note, and a
`trigger_error` boolean. The gateway routes a `trigger_error == true` submission
to a service task that stands for a call to an external system. That system is
down by default (``probe.external_down``), so the task ends in state_error and
gives `bff_admin_execute_erroneous_task` something real to operate on. A second
service task sits behind it, so a test can also let the retried task succeed and
the step after it fail. A script task closes the chain: unlike a service task it
does not catch its own errors, so a retry of it can raise.

A test steers the run the way an administrator experiences it:

* the outside world: ``probe.external_down = False`` means the external system
  is back, and a retry with unchanged data succeeds;
* the task data, corrected through ``bff_admin_replace_task_data`` before a
  retry: ``crash_follow_up`` makes the step behind the crash task raise,
  ``crash_script`` makes the script step raise (checked in the BPMN script itself).

``probe`` also counts the crash task's runs and can hold a successful run open.
"""

import threading
from dataclasses import dataclass, field

from actidoo_wfe.wf.service_task_helper import ServiceTaskHelper


@dataclass
class Probe:
    #: The external system the crash task calls is unreachable. Every test
    #: starts with it down; "the system is back" is what makes a retry succeed.
    external_down: bool = True
    #: How often the crash task ran.
    runs: int = 0
    #: Set when the crash task starts, so a test can wait for that moment.
    started: threading.Event = field(default_factory=threading.Event)
    #: When set, a successful run of the crash task blocks until the event fires.
    #: That keeps the retry inside its request, holding the instance row lock,
    #: so a second retry can overlap with it.
    hold_until: threading.Event | None = None

    def reset(self) -> None:
        self.external_down = True
        self.runs = 0
        self.started.clear()
        self.hold_until = None


probe = Probe()


def service_bff_crash_task(sth: ServiceTaskHelper):
    probe.runs += 1
    probe.started.set()
    if probe.external_down:
        raise RuntimeError("intentional crash for BFF endpoint tests")
    if probe.hold_until is not None:
        probe.hold_until.wait(timeout=30)


def service_bff_follow_up_task(sth: ServiceTaskHelper):
    if sth.task_data.get("crash_follow_up"):
        raise RuntimeError("intentional crash of the step after the crash task")


# ``probe`` stays out: what is exported here becomes a reserved name in the
# workflow's script namespace.
__all__ = ["service_bff_crash_task", "service_bff_follow_up_task"]
