from actidoo_wfe.wf.service_task_helper import ServiceTaskHelper
import logging


logger = logging.getLogger()

def service_job_test(sth:ServiceTaskHelper):
    data = sth.task_data
    print(data,"lachs")