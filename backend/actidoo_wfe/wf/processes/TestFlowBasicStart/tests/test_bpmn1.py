import pytest

from actidoo_wfe.database import SessionLocal
from actidoo_wfe.wf.exceptions import InvalidWorkflowSpecException
from actidoo_wfe.wf.tests.helpers.workflow_dummy import WorkflowDummy

WF_NAME = "TestFlowBasicStart" # must match the "Process ID" inside bpmn and the folder name in actidoo_wfe/wf/processes (but not the bpmn file name itself)

FILL_FORM_DATA = {

}

def test_startWorkflow_throwsException_wrongWfNname(db_engine_ctx):
    with db_engine_ctx():
        db_session = SessionLocal()
        
        with pytest.raises(InvalidWorkflowSpecException):
            WorkflowDummy(
                db_session=db_session,
                users_with_roles={
                    "initiator": ["wf-user"]
                },            
                workflow_name="GibtEsNicht", # --> Name does not exist!
                start_user="initiator",
            )

def test_startWorkflow_throwsException_unknownUser(db_engine_ctx):
    with db_engine_ctx():
        db_session = SessionLocal()

        with pytest.raises(KeyError):
            WorkflowDummy(
                db_session=db_session,
                users_with_roles={
                    "initiator": ["wf-user"]
                },            
                workflow_name=WF_NAME,
                start_user="non_existing_user", # --> does not exist
            )

def test_startWorkflow_succeeds_basicSetupWithoutImplementation(db_engine_ctx):
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

        # expect 0 user tasks, because workflow has already ended
        workflow.user("initiator").get_usertasks(workflow.workflow_instance_id, 0)

        # TODO
        # The workflow has ended successfully, although we have a service task 'evaluate_form_1'
        # inside the bpmn, without any implementation.
        # See also call_service() in spiff_customized.py for this.
        
