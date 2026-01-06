# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

import pytest

from actidoo_wfe.database import SessionLocal
from actidoo_wfe.wf import service_application
from actidoo_wfe.wf.exceptions import UserMayNotStartWorkflowException
from actidoo_wfe.wf.tests.helpers.workflow_dummy import WorkflowDummy

WF_NAME = "TestFlowInitiatorRoleCheck"

def start_my_workflow(starter):
    db_session=SessionLocal()
    wf = WorkflowDummy(
            
            db_session=db_session,
            users_with_roles={
                "initiator_false": ["wf-user"],
                "initiator_true": ["wf-user", "wf-initiator-test"]
            },            
            workflow_name=WF_NAME,
            start_user=starter,
        )
    
    return wf, db_session

def test_startWorkflow_raisesException_whenUserHasNotCorrectRole(db_engine_ctx):
    with db_engine_ctx():
        with pytest.raises(UserMayNotStartWorkflowException):
            workflow, db_session = start_my_workflow(starter="initiator_false")


def test_startWorkflow_doesNotRaiseException_whenUserHasCorrectRole(db_engine_ctx):
    with db_engine_ctx():
        workflow, db_session = start_my_workflow(starter="initiator_true")


def test_getAllowedWorkflowsToStart_containsWorkflow_whenUserHasCorrectRole(db_engine_ctx):
    with db_engine_ctx():
        workflow, db_session = start_my_workflow(starter=None)
        assert WF_NAME in [x.name for x in service_application.get_allowed_workflows_to_start(db=db_session, user_id=workflow.users.get("initiator_true").user.id)]

def test_getAllowedWorkflowsToStart_doesNotContainWorkflow_whenUserHasNotCorrectRole(db_engine_ctx):
    with db_engine_ctx():
        workflow, db_session = start_my_workflow(starter=None)
        assert WF_NAME not in [x.name for x in service_application.get_allowed_workflows_to_start(db=db_session, user_id=workflow.users.get("initiator_false").user.id)]
