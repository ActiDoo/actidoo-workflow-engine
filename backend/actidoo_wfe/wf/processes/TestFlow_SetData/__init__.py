from actidoo_wfe.wf.service_task_helper import ServiceTaskHelper
import logging

log = logging.getLogger(__name__)


def service_extend_data(sth: ServiceTaskHelper):
    sth.set_data({"extended": "Hier ist was neues!"}) # das landet unter sth.workflow.data und ist NICHT im Formular abrufbar
    sth.task_data["extended"] = "HALLO!" # Das...
    sth.update_task_data({"extended": "Hallo2!"}) # ...bzw das hier landet unter sth.task_data und ist im nächsten Formular als key 'extended' darstellbar.
    pass


def service_check_immediately(sth: ServiceTaskHelper):
    log.debug(sth.task_data)
    log.debug(sth.workflow.data)
    pass

def service_check_data(sth: ServiceTaskHelper):
    log.debug(sth.task_data)
    log.debug(sth.workflow.data)
    pass