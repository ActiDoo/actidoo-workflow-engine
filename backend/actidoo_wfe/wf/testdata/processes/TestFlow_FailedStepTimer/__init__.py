# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 ActiDoo GmbH

"""A step that always fails carries an interrupting timer boundary event. When
the timer fires, the timeout path leads to an end event."""

from actidoo_wfe.wf.service_task_helper import ServiceTaskHelper


def service_failing_step(sth: ServiceTaskHelper):
    raise RuntimeError("intentional failure")
