# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

import logging
import uuid

import pytz
from babel import Locale
from babel.dates import format_date
from mako.lookup import TemplateLookup
from markupsafe import Markup
from sqlalchemy import false, select
from sqlalchemy.orm import Session

from actidoo_wfe.constants import CRON_TIMEZONE
from actidoo_wfe.helpers import mail
from actidoo_wfe.helpers.time import dt_now_naive
from actidoo_wfe.i18n import make_translator
from actidoo_wfe.settings import settings
from actidoo_wfe.wf import providers as workflow_providers
from actidoo_wfe.wf import service_i18n
from actidoo_wfe.wf.constants import MAIL_TEMPLATE_DIR
from actidoo_wfe.wf.models import WorkflowInstanceTask, WorkflowUser
from actidoo_wfe.wf.service_user import get_all_users, get_users_of_role
from actidoo_wfe.wf.service_workflow import get_wf_owner_role_to_workflow_mapping, get_workflow_owner
from actidoo_wfe.wf.views import get_erroneous_tasks, get_single_task, get_workflows_with_usertasks

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
    # "-- " (dash-dash-space) is the RFC 3676 signature delimiter mail clients detect.
    return f"\n\n-- \n{sig}\n"


def _format_error_date(error_at, locale: str) -> str:
    aware = error_at if error_at.tzinfo else pytz.utc.localize(error_at)
    local_dt = aware.astimezone(pytz.timezone(CRON_TIMEZONE))
    try:
        return format_date(local_dt.date(), format="medium", locale=Locale.parse(locale, sep="-"))
    except Exception:
        return local_dt.date().isoformat()


def compile_email_template(template: str, params: dict, locale: str | None = None, template_dir=MAIL_TEMPLATE_DIR) -> str:
    mylookup = TemplateLookup(directories=[template_dir], strict_undefined=True)
    mytemplate = mylookup.get_template(template)
    try:
        return mytemplate.render_unicode(
            **dict(
                params,
                generate_instance_url=_generate_instance_url,
                generate_workflow_instance_admin_url=_generate_workflow_instance_admin_url,
                signature_block=_build_signature_block(),
                _=make_translator(locale),
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
        # Skip instances whose workflow definition has been removed from any provider —
        # they should not be advertised in reminder mails (treated like cancelled).
        wf_instances = [w for w in wf_instances if workflow_providers.workflow_definition_available(w.name)]

        assigned_to_me = [x for x in wf_instances if any(t.assigned_user_id == user.id for t in x.active_tasks)]
        assigned_by_role = [x for x in wf_instances if not all(t.assigned_user_id is not None for t in x.active_tasks)]

        if (len(assigned_to_me) > 0 or len(assigned_by_role) > 0) and user.email:
            locale = user.locale
            _ = make_translator(locale)


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
    if not workflow_providers.workflow_definition_available(task.workflow_instance.name):
        return 0
    num_sent = 0

    if task.assigned_user_id != user_id:
        log.warning("trying to send user_assigned_to_task mail, but the provided user does not match the assigned user in the database")
    else:
        if user.email is not None:
            locale = user.locale
            _ = make_translator(locale)

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
    if not workflow_providers.workflow_definition_available(task.workflow_instance.name):
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
        _ = make_translator(locale)

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
        _ = make_translator(locale)

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
    if not workflow_providers.workflow_definition_available(task.workflow_instance.name):
        return 0

    recipients = _collect_admin_owner_recipients(db=db, task=task)

    num_sent = 0
    for email, locale in recipients:
        _ = make_translator(locale)

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


def send_erroneous_tasks_reminder_mail(db: Session) -> int:
    """Send the daily digest of erroneous tasks.

    wf-admin members and settings.email_receivers_erroneous_tasks get a global digest
    over all workflows; wf-owner role members get a digest limited to their own
    workflows (unless they already receive the global one). Tasks not yet included in
    any sent digest (error_reported_at is NULL) are marked as new.
    """
    tasks = [t for t in get_erroneous_tasks(db) if workflow_providers.workflow_definition_available(t.workflow_instance.name)]
    if not tasks:
        return 0

    # email -> locale
    admin_recipients: dict[str, str] = {}
    locale_by_email: dict[str, str] = {}
    for u in get_users_of_role(db=db, role_name="wf-admin"):
        if u.email:
            admin_recipients[u.email] = u.locale
            locale_by_email[u.email] = u.locale

    # email -> (locale, owned workflow names); admins are skipped (global digest wins)
    owner_recipients: dict[str, tuple[str, set[str]]] = {}
    for owner_role, wf_names in get_wf_owner_role_to_workflow_mapping().items():
        for u in get_users_of_role(db=db, role_name=owner_role):
            if not u.email or u.email in admin_recipients:
                continue
            locale_by_email[u.email] = u.locale
            _locale, owned = owner_recipients.setdefault(u.email, (u.locale, set()))
            owned.update(wf_names)

    role_emails = set(admin_recipients) | set(owner_recipients)
    if role_emails:
        opted_out = set(
            db.execute(
                select(WorkflowUser.email).where(
                    WorkflowUser.email.in_(role_emails),
                    WorkflowUser.receive_error_task_reminder == false(),
                ),
            ).scalars(),
        )
        for email in opted_out:
            admin_recipients.pop(email, None)
            owner_recipients.pop(email, None)

    # The statically configured receivers always get the global digest (no opt-out).
    for email in settings.email_receivers_erroneous_tasks:
        if email:
            admin_recipients.setdefault(email, locale_by_email.get(email, settings.default_locale))
            owner_recipients.pop(email, None)

    num_sent = 0
    reported_tasks: set[WorkflowInstanceTask] = set()

    def _send_digest(email: str, locale: str, recipient_tasks: list[WorkflowInstanceTask]):
        nonlocal num_sent
        _ = make_translator(locale)

        def _item(t: WorkflowInstanceTask) -> dict:
            workflow_title = _translated_instance_title(t, locale)
            if t.workflow_instance.subtitle:
                workflow_title += " / " + t.workflow_instance.subtitle
            title = f"{workflow_title} - {_translated_task_title(t, locale)}"
            if t.error_at:
                title += " (" + _("erroneous since {date}").format(date=_format_error_date(t.error_at, locale)) + ")"
            return {
                "title": title,
                "is_new": t.error_reported_at is None,
                "admin_url": _generate_workflow_instance_admin_url(t.workflow_instance.id),
            }

        # Guard the whole per-recipient body, not just the send: a failure while rendering
        # one recipient's titles/template must not abort the run and starve the recipients
        # after it. Nothing here writes to the DB (reads + mail I/O only), so skipping a
        # recipient leaves the transaction intact for the rest and the final marker flush.
        try:
            items = [_item(t) for t in recipient_tasks]
            params = {
                "items": items,
                "n_total": len(items),
                "n_new": sum(1 for i in items if i["is_new"]),
            }

            text = compile_email_template(template="erroneous_tasks_reminder.mako", params=params, locale=locale)

            subject = _("Erroneous workflow tasks: {n_total} total, {n_new} new").format(
                n_total=params["n_total"],
                n_new=params["n_new"],
            )

            sent = mail.send_text_mail(
                subject=subject,
                content=text,
                recipient_or_recipients_list=email,
                attachments=dict(),
            )
        except Exception:
            log.exception(f"Failed to build/send erroneous_tasks_reminder to '{email}', continuing with remaining recipients")
            return

        if sent:
            reported_tasks.update(recipient_tasks)
            num_sent += 1

    for email, locale in admin_recipients.items():
        _send_digest(email, locale, tasks)

    for email, (locale, owned_wfs) in owner_recipients.items():
        recipient_tasks = [t for t in tasks if t.workflow_instance.name in owned_wfs]
        if recipient_tasks:
            _send_digest(email, locale, recipient_tasks)

    # Only tasks that were part of at least one sent mail count as reported.
    if reported_tasks:
        now = dt_now_naive()
        for t in reported_tasks:
            if t.error_reported_at is None:
                t.error_reported_at = now
        db.flush()

    log.info(f"Sent erroneous_tasks_reminder to {num_sent} recipients ({len(tasks)} erroneous tasks)")

    return num_sent
