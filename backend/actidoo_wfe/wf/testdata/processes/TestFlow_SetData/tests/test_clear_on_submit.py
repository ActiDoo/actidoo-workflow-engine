# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""Clearing a field in a later task clears its stored value.

Two user tasks share the optional text field ``textfield_1``. The second task is
handed out with the value the first one stored. The browser sends null for a field
the user cleared, and null must overwrite the stored value in the merge - a field
the submission leaves out keeps it.
"""

from actidoo_wfe.database import SessionLocal
from actidoo_wfe.wf import repository, service_workflow
from actidoo_wfe.wf.tests.helpers.workflow_dummy import WorkflowDummy

WF_NAME = "TestFlow_SetData"

STEP_1 = "Form010_EnterData"
STEP_2 = "Form020_ExtendData"


def _start_workflow():
    return WorkflowDummy(
        db_session=SessionLocal(),
        users_with_roles={"initiator": ["wf-user"]},
        workflow_name=WF_NAME,
        start_user="initiator",
    )


def _completed_task_data(workflow, name):
    stored = repository.load_workflow_instance(db=workflow.db, workflow_id=workflow.workflow_instance_id)
    task = next(t for t in service_workflow.get_completed_usertasks(workflow=stored) if t.task_spec.name == name)
    return task.data


def _submit(workflow, task_name, task_data):
    workflow.user("initiator").submit(
        task_data=task_data,
        workflow_instance_id=workflow.workflow_instance_id,
        task_name=task_name,
    )


def test_an_emptied_field_clears_its_stored_value(db_engine_ctx, mock_send_text_mail):
    with db_engine_ctx():
        workflow = _start_workflow()
        _submit(workflow, STEP_1, {"textfield_1": "old"})
        assert workflow.user("initiator").get_usertasks(workflow.workflow_instance_id, 1)[0].data["textfield_1"] == "old"

        _submit(workflow, STEP_2, {"textfield_1": None, "extended": "kept"})
        workflow.assert_completed()

        data = _completed_task_data(workflow, STEP_2)
        assert data["extended"] == "kept"
        assert data["textfield_1"] is None


def test_a_field_left_out_of_the_submission_keeps_its_stored_value(db_engine_ctx, mock_send_text_mail):
    with db_engine_ctx():
        workflow = _start_workflow()
        _submit(workflow, STEP_1, {"textfield_1": "old"})
        _submit(workflow, STEP_2, {"extended": "kept"})
        workflow.assert_completed()

        assert _completed_task_data(workflow, STEP_2)["textfield_1"] == "old"
