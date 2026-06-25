# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""TestFlowDemoExpenseChange — edits an existing DemoExpense record.

Started as the "edit" follow-up action from a DemoExpense row (via
``start_workflow_for_existing_data_model``). The action's ``payload`` seeds the
edit form with the current values plus ``source_id`` (the stable record id to
update). After the user edits, a service task appends a new version of that
record (``action="UPDATE"``); the ``before_flush`` versioning hook bumps
``version`` and demotes the previous head.
"""

from actidoo_wfe.wf.service_task_helper import ServiceTaskHelper

DATA_MODELS = ["DemoExpense"]


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


__all__ = ["DATA_MODELS", "service_demo_persist_update"]
