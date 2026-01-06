# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

from actidoo_wfe.database import SessionLocal
from actidoo_wfe.wf.tests.helpers.workflow_dummy import WorkflowDummy

WF_NAME = "TestFlow_TimerEvent"
BOUNDARY_EVENT_BPMN_ID = "Event_0ud0839"

def start_workflow():
    db_session = SessionLocal()
    workflow = WorkflowDummy(
        db_session=db_session,
        users_with_roles={
            "initiator": ["wf-user"]
        },
        workflow_name=WF_NAME,
        start_user="initiator",
    )
    return workflow, db_session

def test_timer_event(db_engine_ctx, mock_send_text_mail):
    with db_engine_ctx():
        workflow, db_session = start_workflow()

        workflow.user("initiator").get_usertasks(workflow.workflow_instance_id, 1)
        
        workflow.trigger_timer_events(timer_bpmn_id=BOUNDARY_EVENT_BPMN_ID)

        workflow.user("initiator").get_usertasks(workflow.workflow_instance_id, 0)

        workflow.assert_completed()
