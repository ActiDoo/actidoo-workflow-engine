
from actidoo_wfe.database import SessionLocal
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