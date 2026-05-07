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


def test_taskInRoleLane_skipsMail_whenRoleExceedsCap(db_engine_ctx, mock_send_text_mail):
    """When the role's member count exceeds the lane's notify_role_members_max, no mail is sent."""
    with db_engine_ctx():
        db_session = SessionLocal()

        workflow = WorkflowDummy(
            db_session=db_session,
            users_with_roles={
                "initiator": ["wf-user"],
                # 3 members exceeds the lane's cap of 2 -> broadcast suppressed
                "member1@example.com": ["wf-user", "wf-test-role"],
                "member2@example.com": ["wf-user", "wf-test-role"],
                "member3@example.com": ["wf-user", "wf-test-role"],
            },
            workflow_name=WF_NAME,
            start_user="initiator",
        )

        workflow.user("initiator").submit({}, workflow.workflow_instance_id)

        # Give the background handler time to run, then assert no mail was sent.
        # We can't easily wait_for_results for "0 results", so sleep a short fixed window.
        import time

        time.sleep(1.0)

        assert len(mock_send_text_mail) == 0
