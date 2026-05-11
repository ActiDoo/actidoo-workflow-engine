# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

from actidoo_wfe.database import SessionLocal
from actidoo_wfe.testing.utils import wait_for_results
from actidoo_wfe.wf.tests.helpers.workflow_dummy import WorkflowDummy

# Must match the "Process ID" in the bpmn file and the folder name in actidoo_wfe/wf/processes
WF_NAME = "TestFlowRoleNotifications"


def test_taskInRoleLane_sendsMailToAllRoleMembers_underCap(db_engine_ctx, mock_send_text_mail):
    """Lane with notify_role_members='true' broadcasts to all role members when count is at/below cap.

    BPMN sets notify_role_members_max='2'; we set up exactly 2 role members.
    """
    with db_engine_ctx():
        db_session = SessionLocal()

        workflow = WorkflowDummy(
            db_session=db_session,
            users_with_roles={
                "initiator": ["wf-user"],
                "member1@example.com": ["wf-user", "wf-test-role"],
                "member2@example.com": ["wf-user", "wf-test-role"],
            },
            workflow_name=WF_NAME,
            start_user="initiator",
        )

        # Initiator advances past the init-lane task; the role-lane task then becomes ready.
        workflow.user("initiator").submit({}, workflow.workflow_instance_id)

        # Two role members, each gets a personalised mail.
        wait_for_results(mock_send_text_mail, 2, 3)

        assert len(mock_send_text_mail) == 2
        for email in mock_send_text_mail:
            assert "A task is waiting in your role" in email["subject"]
        recipients = {e["recipients"] for e in mock_send_text_mail}
        assert recipients == {"member1@example.com", "member2@example.com"}


def test_taskInRoleLane_capsRecipientsToFirstN_whenRoleExceedsCap(db_engine_ctx, mock_send_text_mail):
    """When role members exceed cap, send to the first N (deterministically sorted by email)."""
    with db_engine_ctx():
        db_session = SessionLocal()

        workflow = WorkflowDummy(
            db_session=db_session,
            users_with_roles={
                "initiator": ["wf-user"],
                # 3 members exceeds the lane's cap of 2 -> broadcast capped to first 2 by email.
                "member1@example.com": ["wf-user", "wf-test-role"],
                "member2@example.com": ["wf-user", "wf-test-role"],
                "member3@example.com": ["wf-user", "wf-test-role"],
            },
            workflow_name=WF_NAME,
            start_user="initiator",
        )

        workflow.user("initiator").submit({}, workflow.workflow_instance_id)

        # Two task-ready mails (cap=2). No admin/owner configured -> no limit-warning mail.
        wait_for_results(mock_send_text_mail, 2, 3)

        task_mails = [e for e in mock_send_text_mail if "A task is waiting in your role" in e["subject"]]
        assert len(task_mails) == 2
        recipients = {e["recipients"] for e in task_mails}
        assert recipients == {"member1@example.com", "member2@example.com"}

        limit_mails = [e for e in mock_send_text_mail if "Role notification limit exceeded" in e["subject"]]
        assert len(limit_mails) == 0


def test_taskInRoleLane_sendsLimitWarningMail_whenRoleExceedsCap(db_engine_ctx, mock_send_text_mail, monkeypatch):
    """When the cap is exceeded, an additional warning mail is sent to configured admins."""
    from actidoo_wfe.settings import settings

    monkeypatch.setattr(settings, "email_receivers_erroneous_tasks", ["admin@example.com"])

    with db_engine_ctx():
        db_session = SessionLocal()

        workflow = WorkflowDummy(
            db_session=db_session,
            users_with_roles={
                "initiator": ["wf-user"],
                "member1@example.com": ["wf-user", "wf-test-role"],
                "member2@example.com": ["wf-user", "wf-test-role"],
                "member3@example.com": ["wf-user", "wf-test-role"],
            },
            workflow_name=WF_NAME,
            start_user="initiator",
        )

        workflow.user("initiator").submit({}, workflow.workflow_instance_id)

        # 2 capped task mails + 1 admin warning mail
        wait_for_results(mock_send_text_mail, 3, 3)

        limit_mails = [e for e in mock_send_text_mail if "Role notification limit exceeded" in e["subject"]]
        assert len(limit_mails) == 1
        assert limit_mails[0]["recipients"] == ["admin@example.com"]
        assert "3 members" in limit_mails[0]["content"]
        assert "cap of 2" in limit_mails[0]["content"]
