# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

import logging

from actidoo_wfe.wf.service_task_helper import ServiceTaskHelper

log = logging.getLogger(__name__)

def service_interrupt(sth: ServiceTaskHelper):
    log.debug("service_interrupt")
    
