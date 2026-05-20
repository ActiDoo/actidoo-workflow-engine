# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""TestFlowBff — synthetic workflow exclusively for BFF endpoint tests.

Form1 collects a text, a dynamic select, an upload, an optional note, and a
trigger_error boolean. The gateway routes a `trigger_error == true` submission
to a service task that intentionally raises, putting the task into state_error
and giving `bff_admin_execute_erroneous_task` something real to operate on.
"""

from actidoo_wfe.wf.service_task_helper import ServiceTaskHelper


def service_bff_crash_task(sth: ServiceTaskHelper):
    raise RuntimeError("intentional crash for BFF endpoint tests")


__all__ = ["service_bff_crash_task"]
