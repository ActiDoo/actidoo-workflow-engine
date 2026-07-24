# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

import logging

import croniter
from sqlalchemy.orm import Session

from actidoo_wfe.async_scheduling import CronRetryPolicy, cron_task
from actidoo_wfe.settings import settings
from actidoo_wfe.wf.mail import send_erroneous_tasks_reminder_mail, send_personal_status_mail
from actidoo_wfe.wf.service_application import handle_messages, handle_timeevents

log = logging.getLogger(__name__)


@cron_task(task_name="personal_status_mail", cron="0 10 * * tue", retry_policy=CronRetryPolicy(retry_delay_seconds=600, max_retries=1))
def cron_personal_status_mail(db: Session):
    send_personal_status_mail(db=db)


_reminder_cron = settings.email_erroneous_tasks_reminder_cron

if _reminder_cron and not croniter.croniter.is_valid(_reminder_cron):
    log.error(f"Invalid cron expression in email_erroneous_tasks_reminder_cron: '{_reminder_cron}' - the erroneous-tasks reminder is disabled")
    _reminder_cron = ""


# An empty cron registers the task without scheduling it (CronTask handles falsy crons).
@cron_task(
    task_name="erroneous_tasks_reminder",
    cron=_reminder_cron,
    retry_policy=CronRetryPolicy(retry_delay_seconds=600, max_retries=1),
)
def cron_erroneous_tasks_reminder(db: Session):
    send_erroneous_tasks_reminder_mail(db=db)
    db.commit()


@cron_task(
    task_name="handle_messages",
    cron="* * * * * */30",
)
def cron_handle_messages(db: Session):
    handle_messages(db=db)
    db.commit()


@cron_task(
    task_name="handle_timeevents",
    cron="* * * * * */30",
)
def cron_handle_timeevents(db: Session):
    handle_timeevents(db=db)
    db.commit()
