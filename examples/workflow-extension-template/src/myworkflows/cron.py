# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""Example cron tasks for the Workflow Engine.

Tasks are registered via venusian scan; ensure the package is listed in the
`actidoo_wfe.venusian_scan` entry point (see pyproject.toml).
"""

from __future__ import annotations

from actidoo_wfe.async_scheduling import cron_task
from actidoo_wfe.database import get_db_contextmanager
from actidoo_wfe.wf.service_application import handle_messages


@cron_task(task_name="ext_handle_messages", cron="*/10 * * * *")
def cron_handle_messages(db=None):
    """Forward messages every 10 minutes (demo)."""
    # use a fresh DB session if none was injected
    if db is None:
        with get_db_contextmanager() as ctx_db:
            handle_messages(db=ctx_db)
    else:
        handle_messages(db=db)
