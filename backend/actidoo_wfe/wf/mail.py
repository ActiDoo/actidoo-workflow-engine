# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

import logging
import uuid

from mako.lookup import TemplateLookup
from markupsafe import Markup
from sqlalchemy import select
from sqlalchemy.orm import Session

from actidoo_wfe.helpers import mail
from actidoo_wfe.settings import settings
from actidoo_wfe.wf import service_i18n
from actidoo_wfe.wf.constants import MAIL_TEMPLATE_DIR
from actidoo_wfe.wf.models import WorkflowInstanceTask, WorkflowUser
from actidoo_wfe.wf.service_user import get_all_users, get_users_of_role
from actidoo_wfe.wf.service_workflow import get_workflow_owner
from actidoo_wfe.wf.views import get_single_task, get_workflows_with_usertasks

log = logging.getLogger(__name__)

DEFAULT_NOTIFY_ROLE_MEMBERS_MAX = 20


def _generate_instance_url(workflow_instance_id):
    return Markup(settings.frontend_base_url.rstrip("/") + "/tasks/open/" + str(workflow_instance_id))


def _generate_workflow_instance_admin_url(workflow_instance_id):
    return Markup(settings.frontend_base_url.rstrip("/") + "/admin/all-workflows/" + str(workflow_instance_id))


def _translated_instance_title(task: WorkflowInstanceTask, locale: str) -> str:
    raw = task.workflow_instance.title or task.workflow_instance.name
    if not task.workflow_instance.title:
        return raw
    return service_i18n.translate_string(
        msgid=task.workflow_instance.title,
        workflow_name=task.workflow_instance.name,
        locale=locale,
    )


def _translated_task_title(task: WorkflowInstanceTask, locale: str) -> str:
    if not task.title:
        return task.title
    return service_i18n.translate_string(
        msgid=task.title,
        workflow_name=task.workflow_instance.name,
        locale=locale,
    )


def _build_signature_block() -> str:
    """Return the signature block (with a "--" separator) or empty string if none is configured.

    The signature is plain text from settings.email_signature; deployments can put a
    multi-line, multi-language farewell there and it is rendered as-is — no translation.
    """
    sig = (settings.email_signature or "").strip()
    if not sig:
        return ""
    return f"\n\n-- \n{sig}\n"


def compile_email_template(template: str, params: dict, locale: str, template_dir=MAIL_TEMPLATE_DIR) -> str:
    mylookup = TemplateLookup(directories=[template_dir], strict_undefined=True)
    mytemplate = mylookup.get_template(template)
    try:
        return mytemplate.render_unicode(
            **dict(
                params,
                generate_instance_url=_generate_instance_url,
                generate_workflow_instance_admin_url=_generate_workflow_instance_admin_url,
                signature_block=_build_signature_block(),
                _=lambda s: service_i18n.translate_mail_string(s, locale),
            )
        )  # type: ignore
    except NameError as e:
        log.exception(f"{str(e)}, {template}")
        raise e


def send_personal_status_mail(db: Session):
    users = get_all_users(db)
    num_mails_sent = 0

    for user in users:
        wf_instances = get_workflows_with_usertasks(db=db, user=user)

        assigned_to_me = [x for x in wf_instances if any(t.assigned_user_id == user.id for t in x.active_tasks)]
        assigned_by_role = [x for x in wf_instances if not all(t.assigned_user_id is not None for t in x.active_tasks)]

        if (len(assigned_to_me) > 0 or len(assigned_by_role) > 0) and user.email:
            locale = user.locale
            def _(s):
                return service_i18n.translate_mail_string(s, locale)


            # Pre-translate instance + task titles per workflow so the template renders them already localized.
            def _translate_instance(instance):
                instance.title = service_i18n.translate_string(
                    msgid=instance.title or instance.name,
                    workflow_name=instance.name,
                    locale=locale,
                )
                for t in instance.active_tasks + instance.completed_tasks:
                    if t.title:
                        t.title = service_i18n.translate_string(
                            msgid=t.title,
                            workflow_name=instance.name,
                            locale=locale,
                        )
                return instance

            assigned_to_me_t = [_translate_instance(x) for x in assigned_to_me]
            assigned_by_role_t = [_translate_instance(x) for x in assigned_by_role]

            text = compile_email_template(
                template="personal_status_mail.mako",
                params={
                    "user": user,
                    "assigned_to_me": assigned_to_me_t,
                    "not_assigned": assigned_by_role_t,
                },
                locale=locale,
            )

            subject = _("{n_assigned} assigned tasks / {n_available} available tasks").format(
                n_assigned=len(assigned_to_me),
                n_available=len(assigned_by_role),
            )

            mail.send_text_mail(
                subject=subject,
                content=text,
                recipient_or_recipients_list=user.email,
                attachments=dict(),
            )
            num_mails_sent += 1

    log.info(f"Sent personal_status_mail to {num_mails_sent} users")

    return num_mails_sent


def send_user_assigned_to_task_mail(db: Session, user_id: uuid.UUID, task_id: uuid.UUID):
    user = db.execute(
        select(WorkflowUser).where(WorkflowUser.id == user_id),
    ).scalar_one()

    task: WorkflowInstanceTask = get_single_task(db=db, task_id=task_id)
    num_sent = 0

    if task.assigned_user_id != user_id:
        log.warning("trying to send user_assigned_to_task mail, but the provided user does not match the assigned user in the database")
    else:
        if user.email is not None:
            locale = user.locale
            def _(s):
                return service_i18n.translate_mail_string(s, locale)

            workflow_title = _translated_instance_title(task, locale)
            task_title = _translated_task_title(task, locale)

            text = compile_email_template(
                template="user_assigned_to_task.mako",
                params={
                    "user": user,
                    "task": task,
                    "workflow_title": workflow_title,
                    "task_title": task_title,
                },
                locale=locale,
            )

            subject = _('A task is assigned to you in "{workflow_title}"').format(workflow_title=workflow_title)

            mail.send_text_mail(
                subject=subject,
                content=text,
                recipient_or_recipients_list=user.email,
                attachments=dict(),
            )

            log.info(f"Sent user_assigned_to_task to {user.id}")

            num_sent += 1

    return num_sent


def send_task_ready_to_role_members_mail(db: Session, task_id: uuid.UUID):
    task: WorkflowInstanceTask = get_single_task(db=db, task_id=task_id)
    if not task.state_ready:
        return 0

    instance = task.workflow_instance
    lane_cfg = (instance.lane_mapping or {}).get(task.lane, {}) if task.lane else {}
    cap = lane_cfg.get("notify_role_members_max") or DEFAULT_NOTIFY_ROLE_MEMBERS_MAX

    role_names = [r.name for r in task.lane_roles]

    recipients_by_id: dict = {}
    for role_name in role_names:
        for u in get_users_of_role(db=db, role_name=role_name):
            if u.email:
                recipients_by_id[u.id] = u

    if not recipients_by_id:
        return 0

    # Stable, deterministic order so the same first `cap` users are picked across calls.
    ordered_recipients = sorted(
        recipients_by_id.values(),
        key=lambda u: ((u.email or "").lower(), str(u.id)),
    )
    total = len(ordered_recipients)

    capped = total > cap
    if capped:
        log.warning(
            "Capping role-broadcast for task %s: %d recipients > cap %d (lane=%s)",
            task_id,
            total,
            cap,
            task.lane,
        )
        ordered_recipients = ordered_recipients[:cap]

    num_sent = 0
    for user in ordered_recipients:
        locale = user.locale
        def _(s):
            return service_i18n.translate_mail_string(s, locale)

        workflow_title = _translated_instance_title(task, locale)
        task_title = _translated_task_title(task, locale)

        text = compile_email_template(
            template="task_ready_for_role_members.mako",
            params={
                "user": user,
                "task": task,
                "role_names": role_names,
                "workflow_title": workflow_title,
                "task_title": task_title,
            },
            locale=locale,
        )

        subject = _('A task is waiting in your role for "{workflow_title}"').format(workflow_title=workflow_title)

        mail.send_text_mail(
            subject=subject,
            content=text,
            recipient_or_recipients_list=user.email,
            attachments=dict(),
        )
        num_sent += 1

    log.info(f"Sent task_ready_for_role_members for task {task_id} to {num_sent} recipients")

    if capped:
        send_role_notification_limit_exceeded_mail(
            db=db,
            task_id=task_id,
            total_role_members=total,
            cap=cap,
            role_names=role_names,
        )

    return num_sent


def _collect_admin_owner_recipients(db: Session, task: WorkflowInstanceTask) -> list[tuple[str, str]]:
    """Return list of (email, locale) for admin + workflow-owner recipients.

    settings.email_receivers_erroneous_tasks contains plain emails (no User row) — those
    get the default_locale. Owner-role members have their own user.locale.
    """
    out: dict[str, str] = {}

    for email in settings.email_receivers_erroneous_tasks:
        if email:
            out.setdefault(email, settings.default_locale)

    owner = get_workflow_owner(task.workflow_instance.name)
    if owner is not None:
        for u in get_users_of_role(db=db, role_name=owner):
            if u.email:
                # Owner user.locale wins over the default-locale entry from settings.
                out[u.email] = u.locale

    return [(email, locale) for email, locale in out.items()]


def send_role_notification_limit_exceeded_mail(
    db: Session,
    task_id: uuid.UUID,
    total_role_members: int,
    cap: int,
    role_names: list[str],
):
    task: WorkflowInstanceTask = get_single_task(db=db, task_id=task_id)

    recipients = _collect_admin_owner_recipients(db=db, task=task)

    if not recipients:
        log.warning(
            "Role notification limit exceeded for task %s, but no admin/owner recipients configured",
            task_id,
        )
        return 0

    num_sent = 0
    for email, locale in recipients:
        def _(s):
            return service_i18n.translate_mail_string(s, locale)

        workflow_title = _translated_instance_title(task, locale)
        task_title = _translated_task_title(task, locale)

        text = compile_email_template(
            template="role_notification_limit_exceeded.mako",
            params={
                "task": task,
                "role_names": role_names,
                "total_role_members": total_role_members,
                "cap": cap,
                "workflow_title": workflow_title,
                "task_title": task_title,
            },
            locale=locale,
        )

        subject = _('Role notification limit exceeded for "{workflow_title}"').format(workflow_title=workflow_title)

        mail.send_text_mail(
            subject=subject,
            content=text,
            recipient_or_recipients_list=email,
            attachments=dict(),
        )
        num_sent += 1

    log.info(f"Sent role_notification_limit_exceeded for task {task_id} to {num_sent} recipients")

    return num_sent


def send_task_became_erroneous_mail(db: Session, task_id: uuid.UUID):
    task: WorkflowInstanceTask = get_single_task(db=db, task_id=task_id)

    recipients = _collect_admin_owner_recipients(db=db, task=task)

    num_sent = 0
    for email, locale in recipients:
        def _(s):
            return service_i18n.translate_mail_string(s, locale)

        workflow_title = _translated_instance_title(task, locale)
        task_title = _translated_task_title(task, locale)

        text = compile_email_template(
            template="task_became_erroneous.mako",
            params={
                "task": task,
                "workflow_title": workflow_title,
                "task_title": task_title,
            },
            locale=locale,
        )

        subject = _('A task became erroneous "{workflow_title}"').format(workflow_title=workflow_title)

        mail.send_text_mail(
            subject=subject,
            content=text,
            recipient_or_recipients_list=email,
            attachments=dict(),
        )
        num_sent += 1

    log.info(f"Sent task_became_erroneous to {num_sent} recipients")

    return num_sent
