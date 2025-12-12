import logging

from actidoo_wfe.wf.mail import _generate_instance_url
from actidoo_wfe.wf.service_task_helper import ServiceTaskHelper

log = logging.getLogger(__name__)


def service_create_multi_instance(sth: ServiceTaskHelper):
    users = sth.get_users_of_role("wf-multi-instance-reviewer")
    sth.set_task_data({
        "key_users": [u.email for u in users]
    })

def service_assign_multi_instance_task(sth: ServiceTaskHelper):
    sth.set_task_data({
        "count": 0,
        "vote": 0
    })
    sth.assign_user_without_role(
        bpmn_task_id="GroupReview",
        email=sth.task_data.get("key_user")
    )

def service_send_info_mail(sth: ServiceTaskHelper):
    key_user_email = sth.task_data.get("key_user")
    if not key_user_email:
        log.warning("service_send_info_mail: no key_user email found; skipping mail")
        return
    
    sth.assign_user_without_role(
        bpmn_task_id="GroupReview",
        email=sth.task_data.get("key_user")
    )

    attempt = int(sth.task_data.get("count", 0)) + 1
    sth.set_task_data({"count": attempt})

    request_summary = sth.task_data.get("request_summary") or "Sample request"

    workflow_link = _generate_instance_url(sth.workflow_instance_id)
    reminder_suffix = f" (reminder {attempt - 1})" if attempt > 1 else ""

    details_lines = [
        f"Request details: {request_summary}",
    ]

    details_lines.append("")
    details_lines.append(f"Open task: {workflow_link}")

    content = "\n".join([
        "Hello,",
        "",
        "please review the sample multi-instance request.",
        "",
        *details_lines,
    ])

    subject = f"Group review required{reminder_suffix}"

    sth.send_text_mail(
        subject=subject,
        content=content,
        recipient_or_recipients_list=[key_user_email],
        attachments={},
    )

def service_evaluate_votes(sth: ServiceTaskHelper):
    raw_votes = sth.task_data.get("votes")

    sth.set_task_data({
        "success": sum([int(v) for v in raw_votes]) > 3,
    })
