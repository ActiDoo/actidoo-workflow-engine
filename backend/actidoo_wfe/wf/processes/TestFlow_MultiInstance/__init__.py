import logging

from actidoo_wfe.wf.service_task_helper import ServiceTaskHelper

log = logging.getLogger(__name__)


def service_createLoop(sth: ServiceTaskHelper):
    sth.task_data["myInputCollection"] = [1,2,3]
    pass

def service_checkResult1(sth: ServiceTaskHelper):
    pass

def service_checkResult2(sth: ServiceTaskHelper):
    pass

def service_writeOutput(sth: ServiceTaskHelper):
    sth.task_data["myOutputElement"] = sth.task_data.get("textfield_q2b29g", "fallback")
