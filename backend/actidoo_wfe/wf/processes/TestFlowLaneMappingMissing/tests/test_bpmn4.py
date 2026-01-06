# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

from actidoo_wfe.database import SessionLocal
from actidoo_wfe.wf.tests.helpers.workflow_dummy import WorkflowDummy

WF_NAME = "TestFlowLaneMappingMissing" # must match the "Process ID" inside bpmn and the folder name in actidoo_wfe/wf/processes (but not the bpmn file name itself)

FILL_FORM_DATA = {

}

def test_startWorkflow_hasNoTasksForInitiator_whenThereIsALaneButNoLaneMappingFile(db_engine_ctx):
    with db_engine_ctx():
        db_session = SessionLocal()

        workflow = WorkflowDummy(
            db_session=db_session,
            users_with_roles={
                "initiator": ["wf-user"]
            },            
            workflow_name=WF_NAME,
            start_user="initiator",
        )

        # expect 0 user tasks, there is no lane inside the bpmn, which would add the task automatically to the user.
        workflow.user("initiator").get_usertasks(workflow.workflow_instance_id, 0)
