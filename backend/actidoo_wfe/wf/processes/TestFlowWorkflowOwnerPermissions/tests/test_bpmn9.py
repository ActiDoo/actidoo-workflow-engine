# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

import pytest

from actidoo_wfe.database import SessionLocal
from actidoo_wfe.testing.utils import wait_for_results
from actidoo_wfe.wf import repository, service_application, service_workflow
from actidoo_wfe.wf.bff import bff_admin
from actidoo_wfe.wf.exceptions import UserMayNotAdministrateThisWorkflowException
from actidoo_wfe.wf.tests.helpers.workflow_dummy import WorkflowDummy

WF_NAME = "TestFlowWorkflowOwnerPermissions" # must match the "Process ID" inside bpmn and the folder name in actidoo_wfe/wf/processes (but not the bpmn file name itself)

FILL_FORM_DATA = {

}

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


def test_getAllTasks_MustRespectWFOwner(db_engine_ctx, mock_send_text_mail):
    with db_engine_ctx():
        workflow, db_session = start_my_workflow()

        tasks = workflow.user("initiator").get_usertasks(workflow.workflow_instance_id, 1)
        service_application.admin_assign_task_to_user_without_checks(db=db_session, admin_user_id=workflow.user("wfowner").user.id, task_id=tasks[0].id, assign_to_user_id=workflow.user("other@example.com").user.id, remove_roles=True)

        for name, should_be_allowed in (
            ("initiator", False),
            ("other@example.com", False),
            ("wfowner", True),
            ("otherwfowner", False),
            ("admin", True),
        ):
            # normal user: not allowed
            tasks = service_application.bff_admin_get_all_tasks(
                db=db_session, user_id=workflow.user(name).user.id, bff_table_request_params=bff_admin.AdminWorkflowInstanceTasksBffTableQuerySchema()
            )
            if should_be_allowed:
                assert tasks.COUNT > 0
            else:
                assert tasks.COUNT == 0
        

def test_getAllWorkflowInstances_MustRespectWFOwner(db_engine_ctx, mock_send_text_mail):
    with db_engine_ctx():
        workflow, db_session = start_my_workflow()

        tasks = workflow.user("initiator").get_usertasks(workflow.workflow_instance_id, 1)
        service_application.admin_assign_task_to_user_without_checks(db=db_session, admin_user_id=workflow.user("wfowner").user.id, task_id=tasks[0].id, assign_to_user_id=workflow.user("other@example.com").user.id, remove_roles=True)

        for name, should_be_allowed in (
            ("initiator", False),
            ("other@example.com", False),
            ("wfowner", True),
            ("otherwfowner", False),
            ("admin", True),
        ):

            # normal user: not allowed
            tasks = service_application.bff_admin_get_all_workflow_instances(
                db=db_session, user_id=workflow.user(name).user.id, bff_table_request_params=bff_admin.AdminWorkflowInstancesBffTableQuerySchema()
            )

            if should_be_allowed:
                assert tasks.COUNT == 1
            else:
                assert tasks.COUNT == 0


def test_assignTaskToUserWithoutChecks_MustRespectWFOwner(db_engine_ctx, mock_send_text_mail):
    with db_engine_ctx():
        for name, should_be_allowed in (
            ("initiator", False),
            ("other@example.com", False),
            ("wfowner", True),
            ("otherwfowner", False),
            ("admin", True),
        ):
            workflow, db_session = start_my_workflow()

            tasks = workflow.user("initiator").get_usertasks(workflow.workflow_instance_id, 1)

            if should_be_allowed:
                service_application.admin_assign_task_to_user_without_checks(db=db_session, admin_user_id=workflow.user(name).user.id, task_id=tasks[0].id, assign_to_user_id=workflow.user("other@example.com").user.id, remove_roles=True)
            else:
                with pytest.raises(UserMayNotAdministrateThisWorkflowException):
                    service_application.admin_assign_task_to_user_without_checks(db=db_session, admin_user_id=workflow.user(name).user.id, task_id=tasks[0].id, assign_to_user_id=workflow.user("other@example.com").user.id, remove_roles=True)
            

def test_replaceTaskData_MustRespectWFOwner(db_engine_ctx, mock_send_text_mail):
    with db_engine_ctx():       
        workflow, db_session = start_my_workflow()

        tasks = workflow.user("initiator").get_usertasks(workflow.workflow_instance_id, 1)
        
        for name, should_be_allowed in (
            ("initiator", False),
            ("other@example.com", False),
            ("wfowner", True),
            ("otherwfowner", False),
            ("admin", True),
        ):    
            
            if should_be_allowed:
                service_application.admin_replace_task_data(db=db_session, 
                                                    user_id=workflow.user(name).user.id, 
                                                    task_id=tasks[0].id,
                                                    task_data={
                                                        "test": "123"
                                                    })
            else:
                with pytest.raises(UserMayNotAdministrateThisWorkflowException):
                    service_application.admin_replace_task_data(db=db_session, 
                                                    user_id=workflow.user(name).user.id, 
                                                    task_id=tasks[0].id,
                                                    task_data={
                                                        "test": "123"
                                                    })
        

def test_executeErroneousTask_MustRespectWFOwner(db_engine_ctx, mock_send_text_mail):
    with db_engine_ctx():
        for name, should_be_allowed in (
            ("initiator", False),
            ("other@example.com", False),
            ("wfowner", True),
            ("otherwfowner", False),
            ("admin", True),
        ):
            
            workflow, db_session = start_my_workflow()
            workflow.user("initiator").assign_submit(workflow_instance_id=workflow.workflow_instance_id, task_data={
                "text1": "Hallo"
            })

            engineworkflow = repository.load_workflow_instance(db=db_session, workflow_id=workflow.workflow_instance_id)
            faulty_tasks = service_workflow.get_faulty_tasks(engineworkflow)

            assert len(faulty_tasks) == 1
        
            if should_be_allowed:
                service_application.admin_execute_erroneous_task(db=db_session, 
                                                    user_id=workflow.user(name).user.id, 
                                                    task_id=faulty_tasks[0].id)
            else:
                with pytest.raises(UserMayNotAdministrateThisWorkflowException):
                    service_application.admin_execute_erroneous_task(db=db_session, 
                                                    user_id=workflow.user(name).user.id, 
                                                    task_id=faulty_tasks[0].id)
        

def test_erroneousTask_MustSendMail(db_engine_ctx, mock_send_text_mail):
    with db_engine_ctx():            
        workflow, db_session = start_my_workflow()
        workflow.user("initiator").assign_submit(workflow_instance_id=workflow.workflow_instance_id, task_data={
            "text1": "Hallo"
        })

        engineworkflow = repository.load_workflow_instance(db=db_session, workflow_id=workflow.workflow_instance_id)
        faulty_tasks = service_workflow.get_faulty_tasks(engineworkflow)

        wait_for_results(mock_send_text_mail, 1, 3)

        assert len(faulty_tasks) == 1
        assert len(mock_send_text_mail)>0
                    
def test_assignUser_MustRespectWFOwner(db_engine_ctx, mock_send_text_mail):
    with db_engine_ctx():
        workflow, db_session = start_my_workflow()

        tasks = workflow.user("initiator").get_usertasks(workflow.workflow_instance_id, 1)
               
        for name, should_be_allowed in (
            ("initiator", False),
            ("other@example.com", False),
            ("wfowner", True),
            ("otherwfowner", False),
            ("admin", True),
        ):
            if should_be_allowed:
                service_application.admin_assign_task_to_user_without_checks(db=db_session, 
                                                    admin_user_id=workflow.user(name).user.id, 
                                                    assign_to_user_id=workflow.user("other@example.com").user.id, 
                                                    task_id=tasks[0].id,
                                                    remove_roles=False)
            else:
                with pytest.raises(UserMayNotAdministrateThisWorkflowException):
                    service_application.admin_assign_task_to_user_without_checks(db=db_session, 
                                    admin_user_id=workflow.user(name).user.id, 
                                    assign_to_user_id=workflow.user("other@example.com").user.id, 
                                    task_id=tasks[0].id,
                                    remove_roles=False)
            

def test_unassignUser_MustRespectWFOwner(db_engine_ctx, mock_send_text_mail):
    with db_engine_ctx():
        workflow, db_session = start_my_workflow()

        tasks = workflow.user("initiator").get_usertasks(workflow.workflow_instance_id, 1)

        for name, should_be_allowed in (
            ("initiator", False),
            ("other@example.com", False),
            ("wfowner", True),
            ("otherwfowner", False),
            ("admin", True),
        ):
            if should_be_allowed:
                service_application.admin_unassign_task_without_checks(db=db_session, 
                                                    admin_user_id=workflow.user(name).user.id, 
                                                    task_id=tasks[0].id)
            else:
                with pytest.raises(UserMayNotAdministrateThisWorkflowException):
                    service_application.admin_unassign_task_without_checks(db=db_session, 
                                                    admin_user_id=workflow.user(name).user.id, 
                                                    task_id=tasks[0].id)
     

def test_cancelWorkflowInstance_MustRespectWFOwner(db_engine_ctx, mock_send_text_mail):
    with db_engine_ctx():
        for name, should_be_allowed in (
            ("initiator", False),
            ("other@example.com", False),
            ("wfowner", True),
            ("otherwfowner", False),
            ("admin", True),
        ):
            workflow, db_session = start_my_workflow()
            assert workflow.workflow_instance_id is not None
            if should_be_allowed:
                service_application.admin_cancel_workflow(db=db_session, 
                                                    user_id=workflow.user(name).user.id, 
                                                    workflow_instance_id=workflow.workflow_instance_id)
            else:
                with pytest.raises(UserMayNotAdministrateThisWorkflowException):
                    service_application.admin_cancel_workflow(db=db_session, 
                                        user_id=workflow.user(name).user.id, 
                                        workflow_instance_id=workflow.workflow_instance_id)
        
        
    
