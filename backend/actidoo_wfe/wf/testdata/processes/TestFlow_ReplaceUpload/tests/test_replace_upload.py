# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""A new file where an earlier step removed one.

The three steps share an optional single upload, ``file_a``, and the same kind of
upload inside the rows of ``my_list``. Step 1 uploads a file. Step 2 removes it: the
browser sends null, and null is stored. Step 3 uploads another file onto that null,
and the submit must store it.
"""

from actidoo_wfe.database import SessionLocal
from actidoo_wfe.wf import repository, service_workflow
from actidoo_wfe.wf.constants import ROW_ID_KEY
from actidoo_wfe.wf.tests.helpers.workflow_dummy import WorkflowDummy

WF_NAME = "TestFlow_ReplaceUpload"

STEP_1 = "Form010_Upload"
STEP_2 = "Form020_Remove"
STEP_3 = "Form030_UploadAgain"

FIRST_FILE = {"datauri": "data:text/plain;name=first.txt;base64,dGhlIGZpcnN0IGZpbGU="}
SECOND_FILE = {"datauri": "data:text/plain;name=second.txt;base64,dGhlIHNlY29uZCBmaWxl"}


def _start_workflow():
    return WorkflowDummy(
        db_session=SessionLocal(),
        users_with_roles={"initiator": ["wf-user"]},
        workflow_name=WF_NAME,
        start_user="initiator",
    )


def _submit(workflow, task_name, task_data):
    workflow.user("initiator").submit(
        task_data=task_data,
        workflow_instance_id=workflow.workflow_instance_id,
        task_name=task_name,
    )


def _ready_task_data(workflow):
    return workflow.user("initiator").get_usertasks(workflow.workflow_instance_id, 1)[0].data


def _completed_task_data(workflow, name):
    stored = repository.load_workflow_instance(db=workflow.db, workflow_id=workflow.workflow_instance_id)
    task = next(t for t in service_workflow.get_completed_usertasks(workflow=stored) if t.task_spec.name == name)
    return task.data


def test_a_new_file_replaces_a_removed_one(db_engine_ctx, mock_send_text_mail):
    with db_engine_ctx():
        workflow = _start_workflow()
        _submit(workflow, STEP_1, {"file_a": FIRST_FILE})
        _submit(workflow, STEP_2, {"file_a": None})
        assert _ready_task_data(workflow)["file_a"] is None

        _submit(workflow, STEP_3, {"file_a": SECOND_FILE})

        workflow.assert_completed()
        assert _completed_task_data(workflow, STEP_3)["file_a"]["filename"] == "second.txt"


def test_a_new_file_replaces_a_removed_one_in_a_list_row(db_engine_ctx, mock_send_text_mail):
    with db_engine_ctx():
        workflow = _start_workflow()
        _submit(workflow, STEP_1, {"my_list": [{ROW_ID_KEY: "row-1", "file_b": FIRST_FILE}]})
        _submit(workflow, STEP_2, {"my_list": [{"file_b": None}]})
        assert _ready_task_data(workflow)["my_list"][0]["file_b"] is None

        _submit(workflow, STEP_3, {"my_list": [{"file_b": SECOND_FILE}]})

        workflow.assert_completed()
        row = _completed_task_data(workflow, STEP_3)["my_list"][0]
        assert row[ROW_ID_KEY] == "row-1"
        assert row["file_b"]["filename"] == "second.txt"
