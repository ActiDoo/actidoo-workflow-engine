# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

#previous TestFlow9

from actidoo_wfe.wf.service_task_helper import ServiceTaskHelper


def service_evaluate_form_1(sth: ServiceTaskHelper):
    raise Exception("fail intentionally")

__all__ = [
    "service_evaluate_form_1"
]
