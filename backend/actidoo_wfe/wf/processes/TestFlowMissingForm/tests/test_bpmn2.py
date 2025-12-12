import pytest

from actidoo_wfe.database import SessionLocal
from actidoo_wfe.wf.exceptions import InvalidWorkflowSpecException
from actidoo_wfe.wf.tests.helpers.workflow_dummy import WorkflowDummy

WF_NAME = "TestFlowMissingForm" # must match the "Process ID" inside bpmn and the folder name in actidoo_wfe/wf/processes (but not the bpmn file name itself)

FILL_FORM_DATA = {

}

def test_startWorkflow_fails_missingForm(db_engine_ctx):
    """ the bpmn contains a user task 'SimpleFormID' for which we have no proper form file 'SimpleFormID.form'"""
    with db_engine_ctx():
        db_session = SessionLocal()

        # we raise a FormNotFoundException inside spiff_customized.py, which gets re-raised as ValidationException by the Spiffworkflow parser
        with pytest.raises(InvalidWorkflowSpecException):
            WorkflowDummy(
                db_session=db_session,
                users_with_roles={
                    "initiator": ["wf-user"]
                },            
                workflow_name=WF_NAME,
                start_user="initiator",
            )
