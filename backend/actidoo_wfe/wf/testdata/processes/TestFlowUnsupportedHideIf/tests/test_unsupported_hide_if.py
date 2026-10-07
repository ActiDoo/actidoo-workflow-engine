# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""A workflow definition whose form holds a hide-if the server cannot evaluate.

The form hides ``detail`` while ``due > "2024-01-01"``, an ordering comparison
against text. The browser would evaluate it, the server cannot. The definition
fails when it is loaded, like one with a missing form: it cannot be started and is
not offered for start, and the message names the workflow, the form and the field.
"""

import pytest
from SpiffWorkflow.bpmn.parser.ValidationException import ValidationException

from actidoo_wfe.database import SessionLocal
from actidoo_wfe.wf import service_application, service_workflow
from actidoo_wfe.wf.exceptions import InvalidWorkflowSpecException
from actidoo_wfe.wf.tests.helpers.workflow_dummy import WorkflowDummy

WF_NAME = "TestFlowUnsupportedHideIf"


def test_loading_the_definition_fails_and_names_workflow_form_and_field():
    with pytest.raises(ValidationException, match=r"workflow TestFlowUnsupportedHideIf, form Form010_EnterData\.form, field detail"):
        service_workflow.load_process_from_file(WF_NAME)


def test_the_workflow_is_not_offered_and_cannot_be_started(db_engine_ctx):
    with db_engine_ctx():
        db_session = SessionLocal()
        user_id = WorkflowDummy(db_session=db_session, users_with_roles={"initiator": ["wf-user"]}).user("initiator").user.id

        offered = service_application.get_allowed_workflows_to_start(db=db_session, user_id=user_id)

        assert WF_NAME not in [workflow.name for workflow in offered]
        with pytest.raises(InvalidWorkflowSpecException):
            service_application.start_workflow(db=db_session, name=WF_NAME, user_id=user_id)
