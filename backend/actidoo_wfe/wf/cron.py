# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

from sqlalchemy.orm import Session

from actidoo_wfe.async_scheduling import CronRetryPolicy, cron_task
from actidoo_wfe.wf.mail import send_personal_status_mail
from actidoo_wfe.wf.service_application import handle_messages, handle_timeevents


@cron_task(task_name="personal_status_mail", cron="0 10 * * tue",
    retry_policy=CronRetryPolicy(retry_delay_seconds=600, max_retries=1))
def cron_personal_status_mail(db: Session):
    send_personal_status_mail(db=db)


@cron_task(
    task_name="handle_messages",
    cron="* * * * * */30"
)
def cron_handle_messages(db: Session):
    handle_messages(db=db)
    db.commit()

@cron_task(
    task_name="handle_timeevents",
    cron="* * * * * */30"
)
def cron_handle_timeevents(db: Session):
    handle_timeevents(db=db)
    db.commit()
