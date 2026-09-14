# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

import logging

from actidoo_wfe.wf.service_task_helper import ServiceTaskHelper

log = logging.getLogger(__name__)


def service_extend_data(sth: ServiceTaskHelper):
    sth.set_data({"extended": "Hier ist was neues!"})  # das landet unter sth.workflow.data und ist NICHT im Formular abrufbar
    sth.task_data["extended"] = "HALLO!"  # Das...
    sth.update_task_data({"extended": "Hallo2!"})  # ...bzw das hier landet unter sth.task_data und ist im nächsten Formular als key 'extended' darstellbar.
    entered = str(sth.task_data.get("textfield_1") or "").strip()
    sth.set_workflow_instance_subtitle(
        f"{entered} – Beispiel-Untertitel zum Testen langer Werte: Position 7, "
        "Kostenstelle 4711, Referenz A-2026-000123, Bearbeitung dringend",
    )
    pass


def service_check_immediately(sth: ServiceTaskHelper):
    log.debug(sth.task_data)
    log.debug(sth.workflow.data)
    pass


def service_check_data(sth: ServiceTaskHelper):
    log.debug(sth.task_data)
    log.debug(sth.workflow.data)
    pass
