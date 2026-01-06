# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

from actidoo_wfe.database import SessionLocal
from actidoo_wfe.wf.tests.helpers.workflow_dummy import WorkflowDummy

WF_NAME = "TestFlowSthUserRoles" # must match the "Process ID" inside bpmn and the folder name in actidoo_wfe/wf/processes (but not the bpmn file name itself)

def test_startWorkflow_succeeds_basicSetupWithoutImplementation(db_engine_ctx):
    with db_engine_ctx():
        db_session = SessionLocal()

        workflow = WorkflowDummy(
            db_session=db_session,
            users_with_roles={
                "initiator": ["wf-user"],
                "someOne": ["wf-lane2", "wf-user"],
                "someOne2": ["wf-user", "wf-lane2"],
                "someOne3": ["wf-lane2"],
            },            
            workflow_name=WF_NAME,
            start_user="initiator",
        )

        workflow.user("initiator").submit({}, workflow.workflow_instance_id)

        pass


        