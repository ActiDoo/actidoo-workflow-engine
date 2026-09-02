# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""Reference workflow for number ranges (ADR 012).

Shows the two-task shape the docs prescribe: ``AssignNumber`` issues the number
and does nothing else, ``UseNumber`` is where the number would be posted onward.
Keeping the issuing step short keeps the window in which a concurrent issue has
to wait short, and keeps an administrator's retry of the *using* step from
re-issuing anything.

``CRASH_AFTER_ALLOCATION`` lets the test drive the case that matters: the step
fails *after* it has issued its numbers, and the admin retry must hand back the
same ones rather than burn a second pair.
"""

from actidoo_wfe.wf.service_task_helper import ServiceTaskHelper

DATA_MODELS = ["DemoCaseNumber"]

#: Flipped by the tests to make the issuing step fail after allocation.
CRASH_AFTER_ALLOCATION = False

#: Every (first, second) pair the issuing step handed out, in call order — the
#: tests read this to tell "issued again" from "handed back".
ISSUED = []


def service_assign_number(sth: ServiceTaskHelper):
    # Two draws from one range in one step: without a key the helper counts them
    # (#0, #1), so these are two different numbers — and a retry replays the same
    # sequence and gets both back unchanged.
    case_number = sth.next_number("DemoCaseNumber")
    sub_number = sth.next_number("DemoCaseNumber")
    ISSUED.append((case_number, sub_number))

    sth.set_task_data_key("case_number", case_number)
    sth.set_task_data_key("sub_number", sub_number)
    sth.set_workflow_instance_subtitle(case_number)

    if CRASH_AFTER_ALLOCATION:
        raise RuntimeError("intentional crash after the numbers were issued")


def service_use_number(sth: ServiceTaskHelper):
    # Stands in for the step that posts the number onward. It reads the number
    # from task data and never issues one, so retrying it is safe by shape.
    sth.set_task_data_key("posted", sth.task_data.get("case_number"))


__all__ = [
    "CRASH_AFTER_ALLOCATION",
    "DATA_MODELS",
    "ISSUED",
    "service_assign_number",
    "service_use_number",
]
