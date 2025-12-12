import logging

from fastapi import Request
from sqlalchemy.orm import Session

import actidoo_wfe.wf.bff.deps as deps
import actidoo_wfe.wf.service_user as service_user
from actidoo_wfe.database import get_db_contextmanager
from actidoo_wfe.wf import events
from actidoo_wfe.wf.cross_context.imports import (
    LoginStateSchema,
    login_hook,
)
from actidoo_wfe.wf.mail import send_task_became_erroneous_mail, send_user_assigned_to_task_mail

log = logging.getLogger(__name__)


@login_hook
def wf_on_login(request: Request, db: Session, login_state: LoginStateSchema):
    """This is called on every successful login. We UPSERT the WFEUser according to the user login information."""
    if login_state.can_access_wf and login_state.roles is not None: 
        user = deps.get_user(request=request)
        service_user.assign_roles(
            db=db, user_id=user.id, role_names=login_state.roles
        )

@events.event_handler(events.UserAssignedToReadyTaskEvent)
def handle_user_assigned_to_task(event: events.UserAssignedToReadyTaskEvent):
    with get_db_contextmanager() as db:
        send_user_assigned_to_task_mail(task_id=event.task_id, user_id=event.user_id, db=db)

@events.event_handler(events.TaskBecameErroneousEvent)
def handle_erroneous_task(event: events.TaskBecameErroneousEvent):
    with get_db_contextmanager() as db:
        send_task_became_erroneous_mail(task_id=event.task_id, db=db)
    