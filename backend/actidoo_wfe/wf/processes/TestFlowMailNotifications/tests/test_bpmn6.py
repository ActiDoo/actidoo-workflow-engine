
from actidoo_wfe.database import SessionLocal
from actidoo_wfe.helpers.tests import wait_for_results
from actidoo_wfe.wf import service_application
from actidoo_wfe.wf.mail import send_personal_status_mail
from actidoo_wfe.wf.tests.helpers.workflow_dummy import WorkflowDummy

WF_NAME = "TestFlowMailNotifications" # must match the "Process ID" inside bpmn and the folder name in actidoo_wfe/wf/processes (but not the bpmn file name itself)

def start_my_workflow():
    db_session=SessionLocal()
    wf = WorkflowDummy(
            
            db_session=db_session,
            users_with_roles={
                "initiator": ["wf-user"],
                "other@example.com": ["wf-user"],
                "admin": ["wf-user", "wf-admin"],
            },            
            workflow_name=WF_NAME,
            start_user="initiator",
        )
    
    return wf, db_session

def test_assignTaskToUserWithoutChecks_InvokesEmail(db_engine_ctx, mock_send_text_mail):
    with db_engine_ctx():
        workflow, db_session = start_my_workflow()

        # expect 1 user tasks, there is a lane mapping which will add the initiator to the user task
        tasks = workflow.user("initiator").get_usertasks(workflow.workflow_instance_id, 1)
        service_application.admin_assign_task_to_user_without_checks(db=db_session, admin_user_id=workflow.user("admin").user.id, task_id=tasks[0].id, assign_to_user_id=workflow.user("other@example.com").user.id, remove_roles=True)

        db_session.commit()

        wait_for_results(mock_send_text_mail, 1, 3)

        assert len(mock_send_text_mail) == 1
        assert "A task is assigned to you" in mock_send_text_mail[0]['subject']

def test_sendPersonalStatusMail_shouldSentOnlyOneMailPerUser(db_engine_ctx, mock_send_text_mail):
    with db_engine_ctx():
        # start two workflows

        workflow1, db_session = start_my_workflow()

        # start more
        service_application.start_workflow(db=db_session, name=WF_NAME, user_id=workflow1.users["initiator"].user.id)
        service_application.start_workflow(db=db_session, name=WF_NAME, user_id=workflow1.users["initiator"].user.id)
        service_application.start_workflow(db=db_session, name=WF_NAME, user_id=workflow1.users["initiator"].user.id)
        service_application.start_workflow(db=db_session, name=WF_NAME, user_id=workflow1.users["initiator"].user.id)
        
        assert workflow1.workflow_instance_id is not None
        
        workflow1.user("initiator").get_usertasks(workflow_instance_id = workflow1.workflow_instance_id, expected_task_count=1)
        
        send_personal_status_mail(db=db_session)
        
        assert len(mock_send_text_mail) == 1
        
        
