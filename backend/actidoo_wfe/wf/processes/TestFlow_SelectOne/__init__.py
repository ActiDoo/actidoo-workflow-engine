# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""
This test flow is for unit testing the transformation of Camunda forms.

It is not intendended to test any service tasks or other functionality.
"""
import logging
from pprint import pprint

from actidoo_wfe.wf.service_task_helper import ServiceTaskHelper

log = logging.getLogger(__name__)

def service_evaluate_form(sth: ServiceTaskHelper):
    log.debug("service_evaluate_form")
    log.debug(sth.task_data)
    log.debug(pprint.pformat(sth.task_data))
    pass

