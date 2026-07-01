# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""TestFlowDemoExpenseChange — edits an existing DemoExpense record.

Started as the "edit" follow-up action from a DemoExpense row (via
``start_workflow_for_existing_data_model``). The action's ``payload`` seeds the
edit form with the current values plus ``source_id`` (the stable record id to
update). A service task runs *before* the first user task and uses ``source_id``
to prefill a field the payload does not carry — see
``service_demo_prefill_from_source``. After the user edits, a service task appends
a new version of that record (``action="UPDATE"``); the ``before_flush``
versioning hook bumps ``version`` and demotes the previous head.
"""

from actidoo_wfe.wf.service_task_helper import ServiceTaskHelper

DATA_MODELS = ["DemoExpense"]


def service_demo_prefill_from_source(sth: ServiceTaskHelper):
    """Prefill the edit form from the source record — runs BEFORE the first user task.

    Reference example for a server-set seed being available early: ``source_id`` is
    seeded into the engine task data by the originating action, so a service task
    that runs before any user task already sees it in ``task_data``. Here we load the
    current source version by ``source_id`` and prefill ``category`` — a field the
    action ``payload`` deliberately does not carry — so the edit form shows the
    record's current category without the payload having to seed it. Defensive
    (``one_or_none`` + guards) so the flow never breaks if the row is not visible.
    """
    DemoExpense = sth.get_model("DemoExpense")
    source_id = sth.task_data.get("source_id")
    if not source_id:
        return
    source = DemoExpense.get_current_by_id(sth.db, source_id)
    if source is not None and source.category is not None:
        sth.set_task_data_key("category", source.category)


def service_demo_persist_update(sth: ServiceTaskHelper):
    """Append a new version of the source record (action="UPDATE").

    ``source_id`` is the stable record id, a server-set technical variable carried
    by the engine (not a form field), so it is trusted here — the client picks the
    row at action start, never re-supplies it. Adding a row with the existing ``id``
    lets the versioning hook do the rest. The ``receipt`` file field is not
    re-entered in the edit form, so the framework auto-copies it forward from the
    previous version (call ``sth.clear_files(row, "receipt")`` to drop it instead).
    """
    DemoExpense = sth.get_model("DemoExpense")
    source_id = sth.task_data.get("source_id")
    sth.db.add(
        DemoExpense(
            id=source_id,
            workflow_instance_id=sth.workflow_instance_id,
            action="UPDATE",
            title=sth.task_data.get("title"),
            amount=sth.task_data.get("amount"),
            category=sth.task_data.get("category"),
            description=sth.task_data.get("description"),
            status="open",
        )
    )
    sth.db.flush()


__all__ = ["DATA_MODELS", "service_demo_prefill_from_source", "service_demo_persist_update"]
