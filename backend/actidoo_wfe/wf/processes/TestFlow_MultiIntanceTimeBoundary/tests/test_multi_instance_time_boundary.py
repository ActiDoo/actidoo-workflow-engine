# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

from actidoo_wfe.database import SessionLocal
from actidoo_wfe.wf.tests.helpers.workflow_dummy import WorkflowDummy

WF_NAME = "TestFlow_MultiIntanceTimeBoundary"
REVIEWER_IDS = [f"reviewer{i}" for i in range(1, 6)]
BOUNDARY_EVENT_BPMN_ID = "Event_0yclcrn"

def start_workflow():
    db_session = SessionLocal()
    workflow = WorkflowDummy(
        db_session=db_session,
        users_with_roles={
            "initiator": ["wf-user"],
            **{
                user_id: ["wf-user", "wf-multi-instance-reviewer"]
                for user_id in REVIEWER_IDS
            },
        },
        workflow_name=WF_NAME,
        start_user="initiator",
    )
    return workflow, db_session

def test_multi_instance_time_boundary_happy(db_engine_ctx, mock_send_text_mail):
    with db_engine_ctx():
        workflow, db_session = start_workflow()

        workflow.user("initiator").assign_submit(
            workflow_instance_id=workflow.workflow_instance_id,
            task_data={"request_summary": "Sample description"},
        )

        for user_id in REVIEWER_IDS[:-1]:
            workflow.user(user_id).assign_submit(
                workflow_instance_id=workflow.workflow_instance_id,
                task_data={"vote": "1"},
            )

        timer_user_id = REVIEWER_IDS[-1]
        timer_user_email = workflow.user(REVIEWER_IDS[-1]).user.email

        workflow.trigger_timer_events(timer_bpmn_id=BOUNDARY_EVENT_BPMN_ID)
        workflow.user(timer_user_id).get_usertasks(workflow.workflow_instance_id, 1)
        
        assert timer_user_email in mock_send_text_mail[-1]["recipients"]

        #2. mail
        workflow.trigger_timer_events(timer_bpmn_id=BOUNDARY_EVENT_BPMN_ID)
        workflow.user(timer_user_id).get_usertasks(workflow.workflow_instance_id, 1)

        #3. mail
        workflow.trigger_timer_events(timer_bpmn_id=BOUNDARY_EVENT_BPMN_ID)
        workflow.user(timer_user_id).get_usertasks(workflow.workflow_instance_id, 1)

        #4. subprocess canceled
        workflow.trigger_timer_events(timer_bpmn_id=BOUNDARY_EVENT_BPMN_ID)
        workflow.user(timer_user_id).get_usertasks(workflow.workflow_instance_id, 0)

        workflow.assert_completed()
