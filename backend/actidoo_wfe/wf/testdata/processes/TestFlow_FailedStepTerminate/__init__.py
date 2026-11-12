# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 ActiDoo GmbH

"""Two parallel branches: one has a step that always fails, the other ends in a
terminate end event, which ends the whole instance."""

from actidoo_wfe.wf.service_task_helper import ServiceTaskHelper


def service_failing_step(sth: ServiceTaskHelper):
    raise RuntimeError("intentional failure")
