# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

import base64
import hashlib

import pytest

from actidoo_wfe.database import SessionLocal
from actidoo_wfe.wf import repository, service_workflow
from actidoo_wfe.wf.exceptions import UserMayNotCopyWorkflowException
from actidoo_wfe.wf.service_application import (
    get_usertasks_for_user_id,
    get_workflow_copy_data,
    get_workflow_preview,
    start_workflow,
)
from actidoo_wfe.wf.service_form import get_attachments
from actidoo_wfe.wf.tests.helpers.workflow_dummy import WorkflowDummy

WF_NAME = "TestFlow_Copy" # must match the "Process ID" inside bpmn and the folder name in actidoo_wfe/wf/processes (but not the bpmn file name itself)

ATTACHMENT_CONTENT = b"copy me"
ATTACHMENT_FILENAME = "copy.txt"
ATTACHMENT_MIMETYPE = "text/plain"
ATTACHMENT_DATAURI = (
    f"data:{ATTACHMENT_MIMETYPE};name={ATTACHMENT_FILENAME};base64,"
    f"{base64.b64encode(ATTACHMENT_CONTENT).decode()}"
)
ATTACHMENT_HASH = hashlib.sha256(ATTACHMENT_CONTENT).hexdigest()

def start_my_workflow():
    db_session=SessionLocal()
    wf = WorkflowDummy(
            
            db_session=db_session,
            users_with_roles={
                "initiator": ["wf-user"],
                "other@example.com": ["wf-user"],
                "admin": ["wf-user", "wf-admin"],
                "wfowner": ["wf-user", "wf-owner-testflowworkflowownerpermissions"],
                "otherwfowner": ["wf-user", "wf-owner-testflowworkflowownerpermissionsb"],
            },            
            workflow_name=WF_NAME,
            start_user="initiator",
        )
    
    return wf, db_session


def test_copyWorkflowInstance(db_engine_ctx, mock_send_text_mail):
    with db_engine_ctx():
        workflow, db_session = start_my_workflow()

        workflow.user("initiator").assign_submit(
            workflow_instance_id=workflow.workflow_instance_id,
            task_data={
                "text1": "hallo",
                "attachments": [
                    {
                        "datauri": ATTACHMENT_DATAURI,
                    }
                ],
            }
        )

        copy_instruction = get_workflow_copy_data(
            db=db_session,
            user_id=workflow.user("initiator").user.id,
            workflow_instance_id=workflow.workflow_instance_id,
        )

        assert copy_instruction.workflow_name == "TestFlow_Copy"

        preview = get_workflow_preview(
            db=db_session,
            name=copy_instruction.workflow_name,
            user_id=workflow.user("initiator").user.id,
            task_data=copy_instruction.data,
        )
        assert preview.name == copy_instruction.workflow_name
        assert preview.title

        preview_task = preview.task
        assert preview_task is not None

        def _all_fields_read_only(schema: dict) -> bool:
            def _check(node):
                if isinstance(node, dict):
                    disabled = True
                    if "ui:path" in node:
                        disabled = node.get("ui:disabled", False)
                    return disabled and all(_check(v) for v in node.values())
                if isinstance(node, list):
                    return all(_check(item) for item in node)
                return True

            return _check(schema)

        assert _all_fields_read_only(preview_task.uischema)
        assert preview_task.data.get("text1") == "hallo"

        newwfid = start_workflow(
            db=db_session,
            name=copy_instruction.workflow_name,
            user_id=workflow.user("initiator").user.id,
            initial_task_data=copy_instruction.data,
        )
        newtask = get_usertasks_for_user_id(
            db=db_session,
            user_id=workflow.user("initiator").user.id,
            workflow_instance_id=newwfid, # type: ignore
            state="ready",
        )[0]
        
        assert newtask.data.get("text1") == "hallo"
        copied_attachments = get_attachments(newtask.data)
        assert len(copied_attachments) == 1
        copied_attachment = copied_attachments[0]
        assert copied_attachment.hash == ATTACHMENT_HASH
        assert copied_attachment.filename == ATTACHMENT_FILENAME

        db_task_attachments = repository.find_task_attachments_by_task_id(
            db=db_session,
            task_id=newtask.id,
        )
        assert len(db_task_attachments) == 1
        db_attachment = db_task_attachments[0]
        assert db_attachment.attachment.hash == ATTACHMENT_HASH
        assert db_attachment.attachment.file
        from actidoo_wfe.storage import get_file_content
        assert get_file_content(db_attachment.attachment.file.file_id) == ATTACHMENT_CONTENT
        assert db_attachment.filename == ATTACHMENT_FILENAME

        db_workflow_attachments = repository.find_workflow_instance_attachments_by_worfklow_instance_id(
            db=db_session,
            workflow_instance_id=newwfid,
        )
        assert any(
            att.attachment.hash == ATTACHMENT_HASH for att in db_workflow_attachments
        )
        with pytest.raises(UserMayNotCopyWorkflowException):
            get_workflow_copy_data(
                db=db_session,
                user_id=workflow.user("other@example.com").user.id,
                workflow_instance_id=workflow.workflow_instance_id,
            )

        with pytest.raises(UserMayNotCopyWorkflowException):
            get_workflow_copy_data(
                db=db_session,
                user_id=workflow.user("admin").user.id,
                workflow_instance_id=workflow.workflow_instance_id,
            )

def test_hidden_fields_removed_for_ready_tasks(db_engine_ctx, mock_send_text_mail):
    with db_engine_ctx():
        workflow, db_session = start_my_workflow()

        try:
            workflow_instance = repository.load_workflow_instance(
                db=db_session,
                workflow_id=workflow.workflow_instance_id,
            )

            ready_tasks = service_workflow.get_ready_and_waiting_usertasks(workflow_instance)
            assert ready_tasks, "Expected at least one ready task"

            task = ready_tasks[0]
            task.data["toggle"] = False
            task.data["should_not_survive"] = "secret"
            task.data["technical_field"] = "keep-me"

            service_workflow.run_workflow(workflow_instance)

            assert "should_not_survive" not in task.data
            assert task.data["technical_field"] == "keep-me"
        finally:
            db_session.close()


def test_copyWorkflowInstance_strips_unknown_fields(db_engine_ctx, mock_send_text_mail):
    with db_engine_ctx():
        workflow, db_session = start_my_workflow()

        workflow.user("initiator").assign_submit(
            workflow_instance_id=workflow.workflow_instance_id,
            task_data={
                "text1": "hallo",
                "toggle": True,
                "should_not_survive": "value"
            },
        )

        original_workflow = repository.load_workflow_instance(
            db=db_session,
            workflow_id=workflow.workflow_instance_id,
        )
        for task in service_workflow.get_completed_usertasks(original_workflow):
            task.data["toggle"] = False
            assert task.data["should_not_survive"] == "value"

        repository.store_workflow_instance(
            db=db_session,
            workflow=original_workflow,
            triggered_by=workflow.user("initiator").user.id,
        )
        db_session.commit()

        copy_instruction = get_workflow_copy_data(
            db=db_session,
            user_id=workflow.user("initiator").user.id,
            workflow_instance_id=workflow.workflow_instance_id,
        )
        newwfid = start_workflow(
            db=db_session,
            name=copy_instruction.workflow_name,
            user_id=workflow.user("initiator").user.id,
            initial_task_data=copy_instruction.data,
        )
        newtask = get_usertasks_for_user_id(
            db=db_session,
            user_id=workflow.user("initiator").user.id,
            workflow_instance_id=newwfid,  # type: ignore[arg-type]
            state="ready",
        )[0]

        assert "should_not_survive" not in newtask.data.keys()



def test_hidden_fields_removed_for_ready_tasks_after_copy(db_engine_ctx, mock_send_text_mail):
    with db_engine_ctx():
        workflow, db_session = start_my_workflow()

        try:
            workflow.user("initiator").assign_submit(
                workflow_instance_id=workflow.workflow_instance_id,
                task_data={
                    "text1": "hallo",
                    "toggle": True,
                    "should_not_survive": "value",
                },
            )

            original_workflow = repository.load_workflow_instance(
                db=db_session,
                workflow_id=workflow.workflow_instance_id,
            )
            for task in service_workflow.get_completed_usertasks(original_workflow):
                task.data["toggle"] = False
                task.data["should_not_survive"] = "legacy"

            repository.store_workflow_instance(
                db=db_session,
                workflow=original_workflow,
                triggered_by=workflow.user("initiator").user.id,
            )
            db_session.commit()

            copy_instruction = get_workflow_copy_data(
                db=db_session,
                user_id=workflow.user("initiator").user.id,
                workflow_instance_id=workflow.workflow_instance_id,
            )

            newwfid = start_workflow(
                db=db_session,
                name=copy_instruction.workflow_name,
                user_id=workflow.user("initiator").user.id,
                initial_task_data=copy_instruction.data,
            )

            copied_task = get_usertasks_for_user_id(
                db=db_session,
                user_id=workflow.user("initiator").user.id,
                workflow_instance_id=newwfid,  # type: ignore[arg-type]
                state="ready",
            )[0]

            assert "should_not_survive" not in copied_task.data
            assert copied_task.data.get("toggle") is False
        finally:
            db_session.close()
