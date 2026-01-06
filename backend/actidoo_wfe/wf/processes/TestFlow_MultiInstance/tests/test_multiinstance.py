# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH


from actidoo_wfe.database import SessionLocal
from actidoo_wfe.wf import service_application
from actidoo_wfe.wf.models import WorkflowInstanceTask
from sqlalchemy import select, true
from actidoo_wfe.wf.tests.helpers.workflow_dummy import WorkflowDummy

WF_NAME = "TestFlow_MultiInstance"

def start_my_workflow():
    db_session=SessionLocal()
    wf = WorkflowDummy(
            
            db_session=db_session,
            users_with_roles={
                "initiator": ["wf-user"],
            },            
            workflow_name=WF_NAME,
            start_user="initiator",
        )
    
    return wf, db_session


def test_multiinstance_happy(db_engine_ctx, mock_send_text_mail):
    with db_engine_ctx():
        workflow, db_session = start_my_workflow()

        # First Parallel MI with 3 instances of the same user task

        tasks = workflow.user("initiator").get_usertasks(workflow.workflow_instance_id, 3)

        for task in tasks:
            workflow.user("initiator").assign_task(task_id=task.id)
            workflow.user("initiator").submit(
                task_id=task.id,
                task_data={
                    "myTestField": "testvalue",
                },
                workflow_instance_id = workflow.workflow_instance_id
            )

        # Second Sequential MI with 3 instances of the same user task

        tasks = workflow.user("initiator").get_usertasks(workflow.workflow_instance_id, 1)

        for i in range(3):
            workflow.user("initiator").assign_submit(workflow_instance_id=workflow.workflow_instance_id, task_data={
                "myTestField": "testvalue",
            })

        # End

        workflow.assert_completed()


def test_completed_tasks_can_be_loaded_via_my_usertasks_endpoint(db_engine_ctx, mock_send_text_mail):
    with db_engine_ctx():
        workflow, db_session = start_my_workflow()

        tasks = workflow.user("initiator").get_usertasks(workflow.workflow_instance_id, 3)
        task = tasks[0]

        workflow.user("initiator").assign_task(task_id=task.id)
        workflow.user("initiator").submit(
            task_id=task.id,
            task_data={
                "myTestField": "testvalue",
            },
            workflow_instance_id=workflow.workflow_instance_id,
        )

        completed_db_task = db_session.execute(
            select(WorkflowInstanceTask).where(
                WorkflowInstanceTask.id == task.id,
                WorkflowInstanceTask.workflow_instance_id == workflow.workflow_instance_id,
                WorkflowInstanceTask.state_completed == true(),
            )
        ).scalar_one_or_none()
        assert completed_db_task is not None, "Expected submitted task to be stored as completed in DB"

        completed_api_tasks = service_application.get_usertasks_for_user_id(
            db=db_session,
            user_id=workflow.user("initiator").user.id,
            workflow_instance_id=workflow.workflow_instance_id,
            state="completed",
        )

        returned_ids = {t.id for t in completed_api_tasks}
        assert task.id in returned_ids, (
            "Expected completed task to be returned by get_usertasks_for_user_id(state='completed'). "
            f"Submitted task id: {task.id}, API returned ids: {sorted(returned_ids)}"
        )
