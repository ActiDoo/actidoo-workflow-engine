import logging

from actidoo_wfe.database import SessionLocal
from actidoo_wfe.wf.tests.helpers.workflow_dummy import WorkflowDummy

WF_NAME = "FeelWorkflowThisOnly"

log = logging.getLogger(__name__)

FORM_DATA = {}


def _start_workflow():
    db_session = SessionLocal()

    workflow = WorkflowDummy(
        db_session=db_session,
        users_with_roles={  # keycloak-realm dummy
            "initiator": ["wf-user"],
        },
        workflow_name=WF_NAME,
        start_user="initiator",
    )

    return workflow


def test_feel_this(db_engine_ctx, mock_send_text_mail):
    """for 'db_engine_ctx' see conftest.py"""
    with db_engine_ctx():
        workflow = _start_workflow()

        workflow.user("initiator").submit(
            task_data=FORM_DATA,
            workflow_instance_id=workflow.workflow_instance_id,
        )
