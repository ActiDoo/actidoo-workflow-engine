# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 ActiDoo GmbH

"""Tests for the daily erroneous-tasks reminder digest.

Erroneous tasks are seeded by flipping ``state_error`` directly on the stored task
rows — driving a real workflow into an error state is not needed to test the digest
logic (recipient resolution, new/known marking, opt-out).
"""

from __future__ import annotations

from unittest.mock import patch

from sqlalchemy import select

from actidoo_wfe.database import SessionLocal
from actidoo_wfe.helpers.concurrency import wait_for_background_tasks
from actidoo_wfe.helpers.time import dt_now_naive
from actidoo_wfe.settings import settings
from actidoo_wfe.wf import mail as wf_mail
from actidoo_wfe.wf import repository, service_application
from actidoo_wfe.wf.mail import send_erroneous_tasks_reminder_mail
from actidoo_wfe.wf.models import WorkflowInstance, WorkflowInstanceTask
from actidoo_wfe.wf.tests.helpers.workflow_dummy import WorkflowDummy

# Has the BPMN custom property wf-owner="wf-owner-testflowworkflowownerpermissions"
WF_OWNED = "TestFlowWorkflowOwnerPermissions"
OWNER_ROLE = "wf-owner-testflowworkflowownerpermissions"

# Has no wf-owner property
WF_PLAIN = "TestFlowMailNotifications"

ADMIN = "admin@example.com"
OWNER = "owner@example.com"
ADMIN_OWNER = "adminowner@example.com"
PLAIN_USER = "plainuser@example.com"


def _start_workflow(db, wf: WorkflowDummy, workflow_name: str, start_user: str):
    instance_id = service_application.start_workflow(
        db=db,
        name=workflow_name,
        user_id=wf.users[start_user].user.id,
    )
    db.commit()
    return instance_id


def _make_task_erroneous(db, workflow_instance_id) -> WorkflowInstanceTask:
    task = db.execute(
        select(WorkflowInstanceTask).where(
            WorkflowInstanceTask.workflow_instance_id == workflow_instance_id,
        ),
    ).scalars().first()
    assert task is not None
    task.state_error = True
    task.error_at = dt_now_naive()
    db.commit()
    return task


def _mails_to(emails, recipient):
    return [m for m in emails if m["recipients"] == recipient]


def _reset_mailbox(emails):
    """Drop mails triggered by workflow start events so tests only see the digest."""
    wait_for_background_tasks()
    emails.clear()


def test_first_run_marks_new_second_run_known(db_engine_ctx, mock_send_text_mail):
    with db_engine_ctx():
        db = SessionLocal()
        wf = WorkflowDummy(db_session=db, users_with_roles={ADMIN: ["wf-user", "wf-admin"]})
        instance_id = _start_workflow(db, wf, WF_PLAIN, ADMIN)
        task = _make_task_erroneous(db, instance_id)

        _reset_mailbox(mock_send_text_mail)
        num_sent = send_erroneous_tasks_reminder_mail(db=db)
        db.commit()

        assert num_sent == 1
        (mail,) = _mails_to(mock_send_text_mail, ADMIN)
        assert "* NEW *" in mail["content"]
        assert "1 total, 1 new" in mail["subject"]
        assert "erroneous since" in mail["content"]

        db.refresh(task)
        assert task.error_reported_at is not None

        # Second run: same task is now a known failure
        _reset_mailbox(mock_send_text_mail)
        num_sent = send_erroneous_tasks_reminder_mail(db=db)
        db.commit()

        assert num_sent == 1
        (mail,) = _mails_to(mock_send_text_mail, ADMIN)
        assert "NEW" not in mail["content"]
        assert "1 total, 0 new" in mail["subject"]


def test_recovery_resets_reported_marker(db_engine_ctx, mock_send_text_mail):
    with db_engine_ctx():
        db = SessionLocal()
        wf = WorkflowDummy(db_session=db, users_with_roles={ADMIN: ["wf-user", "wf-admin"]})
        instance_id = _start_workflow(db, wf, WF_PLAIN, ADMIN)
        task = _make_task_erroneous(db, instance_id)
        task.error_reported_at = dt_now_naive()
        db.commit()

        # Re-store the instance: the engine-side task is not in an error state, so the
        # sync clears state_error and must reset the reported marker as well.
        workflow = repository.load_workflow_instance(db=db, workflow_id=instance_id)
        repository.store_workflow_instance(db=db, workflow=workflow)
        db.commit()

        db.refresh(task)
        assert task.state_error is False
        assert task.error_at is None
        assert task.error_reported_at is None


def test_owner_scoping_and_admin_dedup(db_engine_ctx, mock_send_text_mail):
    with db_engine_ctx():
        db = SessionLocal()
        wf = WorkflowDummy(
            db_session=db,
            users_with_roles={
                ADMIN: ["wf-user", "wf-admin"],
                OWNER: ["wf-user", OWNER_ROLE],
                ADMIN_OWNER: ["wf-user", "wf-admin", OWNER_ROLE],
                PLAIN_USER: ["wf-user"],
            },
        )
        owned_instance_id = _start_workflow(db, wf, WF_OWNED, ADMIN)
        plain_instance_id = _start_workflow(db, wf, WF_PLAIN, ADMIN)
        _make_task_erroneous(db, owned_instance_id)
        _make_task_erroneous(db, plain_instance_id)

        _reset_mailbox(mock_send_text_mail)
        num_sent = send_erroneous_tasks_reminder_mail(db=db)
        db.commit()

        assert num_sent == 3

        # Admins get the global digest with both workflows
        for admin_email in (ADMIN, ADMIN_OWNER):
            (mail,) = _mails_to(mock_send_text_mail, admin_email)
            assert "2 total" in mail["subject"]

        # The owner only gets the tasks of the owned workflow
        (mail,) = _mails_to(mock_send_text_mail, OWNER)
        assert "1 total" in mail["subject"]
        assert str(owned_instance_id) in mail["content"]
        assert str(plain_instance_id) not in mail["content"]

        assert _mails_to(mock_send_text_mail, PLAIN_USER) == []


def test_opt_out_and_settings_receivers(db_engine_ctx, mock_send_text_mail, monkeypatch):
    with db_engine_ctx():
        db = SessionLocal()
        wf = WorkflowDummy(
            db_session=db,
            users_with_roles={
                ADMIN: ["wf-user", "wf-admin"],
                ADMIN_OWNER: ["wf-user", "wf-admin"],
            },
        )
        instance_id = _start_workflow(db, wf, WF_PLAIN, ADMIN)
        _make_task_erroneous(db, instance_id)

        wf.users[ADMIN].user.receive_error_task_reminder = False
        db.commit()

        monkeypatch.setattr(settings, "email_receivers_erroneous_tasks", ["static@example.com"])

        _reset_mailbox(mock_send_text_mail)
        num_sent = send_erroneous_tasks_reminder_mail(db=db)
        db.commit()

        # Opted-out admin gets nothing; the other admin and the static receiver do.
        assert num_sent == 2
        assert _mails_to(mock_send_text_mail, ADMIN) == []
        assert len(_mails_to(mock_send_text_mail, ADMIN_OWNER)) == 1
        assert len(_mails_to(mock_send_text_mail, "static@example.com")) == 1


def test_opted_out_admin_still_receives_via_settings_list(db_engine_ctx, mock_send_text_mail, monkeypatch):
    with db_engine_ctx():
        db = SessionLocal()
        wf = WorkflowDummy(db_session=db, users_with_roles={ADMIN: ["wf-user", "wf-admin"]})
        instance_id = _start_workflow(db, wf, WF_PLAIN, ADMIN)
        _make_task_erroneous(db, instance_id)

        wf.users[ADMIN].user.receive_error_task_reminder = False
        db.commit()

        monkeypatch.setattr(settings, "email_receivers_erroneous_tasks", [ADMIN])

        _reset_mailbox(mock_send_text_mail)
        num_sent = send_erroneous_tasks_reminder_mail(db=db)
        db.commit()

        # The settings list is exempt from the opt-out.
        assert num_sent == 1
        assert len(_mails_to(mock_send_text_mail, ADMIN)) == 1


def test_completed_instance_tasks_are_not_digested(db_engine_ctx, mock_send_text_mail):
    with db_engine_ctx():
        db = SessionLocal()
        wf = WorkflowDummy(db_session=db, users_with_roles={ADMIN: ["wf-user", "wf-admin"]})
        instance_id = _start_workflow(db, wf, WF_PLAIN, ADMIN)
        _make_task_erroneous(db, instance_id)

        instance = db.get(WorkflowInstance, instance_id)
        instance.is_completed = True
        db.commit()

        _reset_mailbox(mock_send_text_mail)
        num_sent = send_erroneous_tasks_reminder_mail(db=db)

        assert num_sent == 0
        assert len(mock_send_text_mail) == 0


def test_one_failing_recipient_does_not_block_others(db_engine_ctx):
    with db_engine_ctx():
        db = SessionLocal()
        wf = WorkflowDummy(
            db_session=db,
            users_with_roles={
                ADMIN: ["wf-user", "wf-admin"],
                ADMIN_OWNER: ["wf-user", "wf-admin"],
            },
        )
        instance_id = _start_workflow(db, wf, WF_PLAIN, ADMIN)
        task = _make_task_erroneous(db, instance_id)
        wait_for_background_tasks()

        delivered = []

        def fake_send(subject, content, recipient_or_recipients_list, attachments):
            if recipient_or_recipients_list == ADMIN:
                raise RuntimeError("mailbox unavailable")
            delivered.append(recipient_or_recipients_list)
            return True

        with patch("actidoo_wfe.helpers.mail.send_text_mail", new=fake_send):
            num_sent = send_erroneous_tasks_reminder_mail(db=db)
        db.commit()

        assert num_sent == 1
        assert delivered == [ADMIN_OWNER]
        db.refresh(task)
        assert task.error_reported_at is not None


def test_rendering_error_for_one_recipient_does_not_block_others(db_engine_ctx, mock_send_text_mail):
    """A failure while building one recipient's digest (title/template rendering, not a
    transport error) must not abort the run and starve later recipients. The successfully
    sent recipient's tasks are still marked; nothing rolls back."""
    with db_engine_ctx():
        db = SessionLocal()
        wf = WorkflowDummy(
            db_session=db,
            users_with_roles={
                ADMIN: ["wf-user", "wf-admin"],
                ADMIN_OWNER: ["wf-user", "wf-admin"],
            },
        )
        instance_id = _start_workflow(db, wf, WF_PLAIN, ADMIN)
        task = _make_task_erroneous(db, instance_id)
        wait_for_background_tasks()

        real_compile = wf_mail.compile_email_template
        calls = {"n": 0}

        def flaky_compile(*args, **kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("template rendering boom")
            return real_compile(*args, **kwargs)

        _reset_mailbox(mock_send_text_mail)
        with patch("actidoo_wfe.wf.mail.compile_email_template", side_effect=flaky_compile):
            num_sent = send_erroneous_tasks_reminder_mail(db=db)
        db.commit()

        # First recipient's render raised and was skipped; the second still received the digest.
        assert num_sent == 1
        assert len(mock_send_text_mail) == 1
        # The successfully sent recipient's task is marked reported (no rollback).
        db.refresh(task)
        assert task.error_reported_at is not None


def test_skipped_send_does_not_mark_reported(db_engine_ctx):
    with db_engine_ctx():
        db = SessionLocal()
        wf = WorkflowDummy(db_session=db, users_with_roles={ADMIN: ["wf-user", "wf-admin"]})
        instance_id = _start_workflow(db, wf, WF_PLAIN, ADMIN)
        task = _make_task_erroneous(db, instance_id)
        wait_for_background_tasks()

        def fake_send(subject, content, recipient_or_recipients_list, attachments):
            return False

        with patch("actidoo_wfe.helpers.mail.send_text_mail", new=fake_send):
            num_sent = send_erroneous_tasks_reminder_mail(db=db)
        db.commit()

        assert num_sent == 0
        db.refresh(task)
        assert task.error_reported_at is None


def test_no_erroneous_tasks_sends_nothing(db_engine_ctx, mock_send_text_mail):
    with db_engine_ctx():
        db = SessionLocal()
        wf = WorkflowDummy(db_session=db, users_with_roles={ADMIN: ["wf-user", "wf-admin"]})
        _start_workflow(db, wf, WF_PLAIN, ADMIN)

        _reset_mailbox(mock_send_text_mail)
        num_sent = send_erroneous_tasks_reminder_mail(db=db)

        assert num_sent == 0
        assert len(mock_send_text_mail) == 0


def test_no_recipients_leaves_markers_unset(db_engine_ctx, mock_send_text_mail, monkeypatch):
    with db_engine_ctx():
        db = SessionLocal()
        wf = WorkflowDummy(db_session=db, users_with_roles={PLAIN_USER: ["wf-user"]})
        instance_id = _start_workflow(db, wf, WF_PLAIN, PLAIN_USER)
        task = _make_task_erroneous(db, instance_id)

        monkeypatch.setattr(settings, "email_receivers_erroneous_tasks", [])

        _reset_mailbox(mock_send_text_mail)
        num_sent = send_erroneous_tasks_reminder_mail(db=db)
        db.commit()

        assert num_sent == 0
        assert len(mock_send_text_mail) == 0
        db.refresh(task)
        assert task.error_reported_at is None
