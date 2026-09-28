# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

import base64

import pytest

from actidoo_wfe.database import SessionLocal
from actidoo_wfe.wf.exceptions import ValidationResultContainsErrors
from actidoo_wfe.wf.tests.helpers.workflow_dummy import WorkflowDummy

WF_NAME = "TestFlowDemoFormUpload"


def _file(name: str, mimetype: str) -> dict:
    content = base64.b64encode(f"content of {name}".encode()).decode()
    return {"datauri": f"data:{mimetype};name={name};base64,{content}"}


PDF = _file("report.pdf", "application/pdf")
CSV = _file("table.csv", "text/csv")
XML = _file("data.xml", "application/xml")
PNG = _file("image.png", "image/png")
TXT = _file("note.txt", "text/plain")

FORM_DATA = {
    "file_single": TXT,
    "file_multi": [TXT, PNG],
    "file_accept": CSV,
    "file_multi_accept_required": [PDF, XML],
    "legacy_multi_images": [PNG],
}


def _start_workflow():
    return WorkflowDummy(
        db_session=SessionLocal(),
        users_with_roles={"initiator": ["wf-user"]},
        workflow_name=WF_NAME,
        start_user="initiator",
    )


def test__demo_workflow_completes(db_engine_ctx, mock_send_text_mail):
    with db_engine_ctx():
        workflow = _start_workflow()
        workflow.user("initiator").submit(task_data=FORM_DATA, workflow_instance_id=workflow.workflow_instance_id)
        workflow.user("initiator").submit(task_data={}, workflow_instance_id=workflow.workflow_instance_id)
        workflow.assert_completed()


@pytest.mark.parametrize(
    "field, value",
    [
        ("file_accept", TXT),
        ("file_multi_accept_required", [PDF, TXT]),
        ("legacy_multi_images", [PDF]),
    ],
)
def test__a_file_type_outside_accept_is_rejected(db_engine_ctx, mock_send_text_mail, field, value):
    with db_engine_ctx():
        workflow = _start_workflow()

        with pytest.raises(ValidationResultContainsErrors) as exc_info:
            workflow.user("initiator").submit(
                task_data={**FORM_DATA, field: value},
                workflow_instance_id=workflow.workflow_instance_id,
            )
        assert field in exc_info.value.error_schema
