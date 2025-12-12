import logging
import uuid

from mako.lookup import TemplateLookup
from markupsafe import Markup
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from actidoo_wfe.helpers import mail
from actidoo_wfe.settings import settings
from actidoo_wfe.wf.constants import MAIL_TEMPLATE_DIR
from actidoo_wfe.wf.models import WorkflowInstanceTask, WorkflowUser
from actidoo_wfe.wf.service_user import get_all_users, get_users_of_role
from actidoo_wfe.wf.service_workflow import get_workflow_owner
from actidoo_wfe.wf.views import get_single_task, get_workflows_with_usertasks

log = logging.getLogger(__name__)

def _generate_instance_url(workflow_instance_id):
    return Markup(settings.frontend_base_url.rstrip("/") + "/tasks/open/" + str(workflow_instance_id ))

def _generate_workflow_instance_admin_url(workflow_instance_id):
    return Markup(settings.frontend_base_url.rstrip("/") + "/admin/all-workflows/" + str(workflow_instance_id ))
    
def compile_email_template(template: str, params: dict, template_dir = MAIL_TEMPLATE_DIR) -> str:
    mylookup = TemplateLookup(directories=[template_dir])
    mytemplate = mylookup.get_template(template)
    return mytemplate.render_unicode(**dict(params,
        generate_instance_url=_generate_instance_url,
        generate_workflow_instance_admin_url=_generate_workflow_instance_admin_url,
        email_signature=settings.email_signature
    )) # type: ignore

def send_personal_status_mail(db: Session):
    users = get_all_users(db)
    num_mails_sent = 0
    
    for user in users:
        wf_instances = get_workflows_with_usertasks(db=db, user=user)

        assigned_to_me = [x for x in wf_instances if any(t.assigned_user_id==user.id for t in x.active_tasks)]
        assigned_by_role = [x for x in wf_instances if not all(t.assigned_user_id is not None for t in x.active_tasks)]

        if (len(assigned_to_me)>0 or len(assigned_by_role)>0) and user.email:

            text = compile_email_template(template="personal_status_mail.mako", params={
                "user": user,
                "assigned_to_me": assigned_to_me,
                "not_assigned": assigned_by_role
            })

            subject = f"{len(assigned_to_me)} assigned tasks / {len(assigned_by_role)} available tasks"
            
            mail.send_text_mail(
                subject=subject,
                content=text,
                recipient_or_recipients_list=user.email,
                attachments=dict()
            )
            num_mails_sent+=1

    log.info(f"Sent personal_status_mail to {num_mails_sent} users")

    return num_mails_sent

def send_user_assigned_to_task_mail(db: Session, user_id: uuid.UUID, task_id: uuid.UUID):
    user = db.execute(
        select(WorkflowUser).where(WorkflowUser.id == user_id)
    ).scalar_one()

    task: WorkflowInstanceTask = get_single_task(db=db, task_id=task_id)
    num_sent = 0

    if task.assigned_user_id != user_id:
        log.warning("trying to send user_assigned_to_task mail, but the provided user does not match the assigned user in the database")
    else:
        if user.email is not None:

            text = compile_email_template(template="user_assigned_to_task.mako", params={
                "user": user,
                "task": task
            })

            subject = f"A task is assigned to you in \"{task.workflow_instance.title or task.workflow_instance.name}\""
                    
            mail.send_text_mail(
                subject=subject,
                content=text,
                recipient_or_recipients_list=user.email,
                attachments=dict()
            )

            log.info(f"Sent user_assigned_to_task to {user.id}")

            num_sent += 1

    return num_sent

def send_task_became_erroneous_mail(db: Session, task_id: uuid.UUID):
    task: WorkflowInstanceTask = get_single_task(db=db, task_id=task_id)
    
    recipients = set(settings.email_receivers_erroneous_tasks)

    owner = get_workflow_owner(task.workflow_instance.name)
    if owner is not None:
        owner_users = get_users_of_role(db=db, role_name=owner)
        recipients |= {u.email for u in owner_users if u.email}

    text = compile_email_template(template="task_became_erroneous.mako", params={
        "task": task
    })

    subject = f"A task became erroneous \"{task.workflow_instance.title or task.workflow_instance.name}\""
            
    mail.send_text_mail(
        subject=subject,
        content=text,
        recipient_or_recipients_list=list(recipients),
        attachments=dict()
    )

    log.info(f"Sent task_became_erroneous to {','.join(recipients)}")

    return len(recipients)

