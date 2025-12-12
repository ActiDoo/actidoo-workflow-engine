import logging

from actidoo_wfe.wf.service_task_helper import ServiceTaskHelper
from actidoo_wfe.wf.service_user import get_users_of_role

log = logging.getLogger(__name__)

def service_testrunner(sth: ServiceTaskHelper):
    
    spiff_task = sth.get_last_completed_task()
    assert spiff_task.task_spec.name == "test1"
    
    
    next_spiff_task = sth.get_next_task()
    log.debug(next_spiff_task.task_spec.name)
    assert next_spiff_task.task_spec.name == "test3"


    #users = get_potential_users_of_task(sth.db, next_spiff_task.id)
    users = get_users_of_role(sth.db, "wf-lane2")

    assert len(users) == 3
    
    for user in users:
        assert user.email in ["someOne@example.com", "someOne2@example.com", "someOne3@example.com"]
        log.debug(user.email)

    
