# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""TestFlowDemoExpenseCreate — creates a DemoExpense record from a user form.

Reference example for the workflow-data feature: a user enters expense data
(including a receipt upload); a service task persists it as the first version of
a DemoExpense row (``action="CREATE"``).
"""

from actidoo_wfe.wf.service_task_helper import ServiceTaskHelper

DATA_MODELS = ["DemoExpense"]


def service_demo_persist_create(sth: ServiceTaskHelper):
    """Persist the entered data as a new DemoExpense record (first version).

    Plain ORM: ``id``/``created_at`` come from column defaults and the
    ``before_flush`` versioning hook assigns ``version=1`` / ``is_current=True``.
    Only the provenance (``workflow_instance_id``) and ``action`` are set here.
    The ``receipt`` is a framework-managed file field: ``attach_files`` records the
    upload and the framework writes it to the data_model_files side table at flush.
    """
    DemoExpense = sth.get_model("DemoExpense")
    row = DemoExpense(
        workflow_instance_id=sth.workflow_instance_id,
        action="CREATE",
        title=sth.task_data.get("title"),
        amount=sth.task_data.get("amount"),
        category=sth.task_data.get("category"),
        description=sth.task_data.get("description"),
        status="open",
    )
    sth.db.add(row)
    receipt = sth.task_data.get("receipt")
    if receipt:
        sth.attach_files(row, "receipt", receipt)
    sth.db.flush()


__all__ = ["DATA_MODELS", "service_demo_persist_create"]
