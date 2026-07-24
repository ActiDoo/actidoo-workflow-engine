# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

import pytest
from sqlalchemy import select

from actidoo_wfe.database import SessionLocal
from actidoo_wfe.testing.utils import wait_for_results
from actidoo_wfe.wf import repository, service_application, service_workflow
from actidoo_wfe.wf.bff import bff_admin
from actidoo_wfe.wf.exceptions import UserMayNotAdministrateThisWorkflowException
from actidoo_wfe.wf.models import WorkflowInstanceTask
from actidoo_wfe.wf.tests.helpers.workflow_dummy import WorkflowDummy

WF_NAME = "TestFlowWorkflowOwnerPermissions"  # must match the "Process ID" inside bpmn and the folder name in actidoo_wfe/wf/processes (but not the bpmn file name itself)
FOREIGN_WF_NAME = "TestFlowBff"  # a workflow the wf-owner neither owns nor administrates

FILL_FORM_DATA = {}


def start_my_workflow():
    db_session = SessionLocal()
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


def _first_task(db, instance_id):
    return db.execute(
        select(WorkflowInstanceTask).where(WorkflowInstanceTask.workflow_instance_id == instance_id),
    ).scalars().first()


def test_erroneous_running_tasks_are_scoped_to_workflow_owner(db_engine_ctx, mock_send_text_mail):
    """The admin "erroneous running tasks" view (f_state_error + f_workflow_instance___is_completed=False)
    must only show a workflow owner the erroneous tasks of workflows they own, not those of other owners."""
    with db_engine_ctx():
        db = SessionLocal()
        wf = WorkflowDummy(
            db_session=db,
            users_with_roles={
                "initiator": ["wf-user"],
                "wfowner": ["wf-user", "wf-owner-testflowworkflowownerpermissions"],
                "otherwfowner": ["wf-user", "wf-owner-testflowworkflowownerpermissionsb"],
            },
            workflow_name=WF_NAME,
            start_user="initiator",
        )
        owned_instance = wf.workflow_instance_id
        foreign_instance = service_application.start_workflow(
            db=db, name=FOREIGN_WF_NAME, user_id=wf.user("initiator").user.id
        )
        db.commit()

        # both instances stay running; put one task of each into the error state
        for instance_id in (owned_instance, foreign_instance):
            task = _first_task(db, instance_id)
            assert task is not None
            task.state_error = True
        db.commit()

        params = bff_admin.AdminWorkflowInstanceTasksBffTableQuerySchema(
            f_state_error=True,
            f_workflow_instance___is_completed=False,
        )
        result = service_application.bff_admin_get_all_tasks(
            db=db,
            user_id=wf.user("wfowner").user.id,
            bff_table_request_params=params,
        )

        returned_instances = {t.workflow_instance.id for t in result.ITEMS}
        assert owned_instance in returned_instances, "owner must see erroneous tasks of their own workflow"
        assert foreign_instance not in returned_instances, "owner must NOT see erroneous tasks of a workflow they do not own"
        assert all(t.state_error for t in result.ITEMS)
        assert all(not t.workflow_instance.is_completed for t in result.ITEMS)


def test_getAllTasks_MustRespectWFOwner(db_engine_ctx, mock_send_text_mail):
    with db_engine_ctx():
        workflow, db_session = start_my_workflow()

        tasks = workflow.user("initiator").get_usertasks(workflow.workflow_instance_id, 1)
        service_application.admin_assign_task_to_user_without_checks(
            db=db_session, admin_user_id=workflow.user("wfowner").user.id, task_id=tasks[0].id, assign_to_user_id=workflow.user("other@example.com").user.id, remove_roles=True
        )

        for name, should_be_allowed in (
            ("initiator", False),
            ("other@example.com", False),
            ("wfowner", True),
            ("otherwfowner", False),
            ("admin", True),
        ):
            # normal user: not allowed
            tasks = service_application.bff_admin_get_all_tasks(
                db=db_session,
                user_id=workflow.user(name).user.id,
                bff_table_request_params=bff_admin.AdminWorkflowInstanceTasksBffTableQuerySchema(),
            )
            if should_be_allowed:
                assert tasks.COUNT > 0
            else:
                assert tasks.COUNT == 0


def test_getAllWorkflowInstances_MustRespectWFOwner(db_engine_ctx, mock_send_text_mail):
    with db_engine_ctx():
        workflow, db_session = start_my_workflow()

        tasks = workflow.user("initiator").get_usertasks(workflow.workflow_instance_id, 1)
        service_application.admin_assign_task_to_user_without_checks(
            db=db_session, admin_user_id=workflow.user("wfowner").user.id, task_id=tasks[0].id, assign_to_user_id=workflow.user("other@example.com").user.id, remove_roles=True
        )

        for name, should_be_allowed in (
            ("initiator", False),
            ("other@example.com", False),
            ("wfowner", True),
            ("otherwfowner", False),
            ("admin", True),
        ):
            # normal user: not allowed
            tasks = service_application.bff_admin_get_all_workflow_instances(
                db=db_session,
                user_id=workflow.user(name).user.id,
                bff_table_request_params=bff_admin.AdminWorkflowInstancesBffTableQuerySchema(),
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
                service_application.admin_assign_task_to_user_without_checks(
                    db=db_session, admin_user_id=workflow.user(name).user.id, task_id=tasks[0].id, assign_to_user_id=workflow.user("other@example.com").user.id, remove_roles=True
                )
            else:
                with pytest.raises(UserMayNotAdministrateThisWorkflowException):
                    service_application.admin_assign_task_to_user_without_checks(
                        db=db_session, admin_user_id=workflow.user(name).user.id, task_id=tasks[0].id, assign_to_user_id=workflow.user("other@example.com").user.id, remove_roles=True
                    )


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
                service_application.admin_replace_task_data(
                    db=db_session,
                    user_id=workflow.user(name).user.id,
                    task_id=tasks[0].id,
                    task_data={
                        "test": "123",
                    },
                )
            else:
                with pytest.raises(UserMayNotAdministrateThisWorkflowException):
                    service_application.admin_replace_task_data(
                        db=db_session,
                        user_id=workflow.user(name).user.id,
                        task_id=tasks[0].id,
                        task_data={
                            "test": "123",
                        },
                    )


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
            workflow.user("initiator").assign_submit(
                workflow_instance_id=workflow.workflow_instance_id,
                task_data={
                    "text1": "Hallo",
                },
            )

            engineworkflow = repository.load_workflow_instance(db=db_session, workflow_id=workflow.workflow_instance_id)
            faulty_tasks = service_workflow.get_faulty_tasks(engineworkflow)

            assert len(faulty_tasks) == 1

            if should_be_allowed:
                service_application.admin_execute_erroneous_task(db=db_session, user_id=workflow.user(name).user.id, task_id=faulty_tasks[0].id)
            else:
                with pytest.raises(UserMayNotAdministrateThisWorkflowException):
                    service_application.admin_execute_erroneous_task(db=db_session, user_id=workflow.user(name).user.id, task_id=faulty_tasks[0].id)


def test_erroneousTask_MustSendMail(db_engine_ctx, mock_send_text_mail):
    with db_engine_ctx():
        workflow, db_session = start_my_workflow()
        workflow.user("initiator").assign_submit(
            workflow_instance_id=workflow.workflow_instance_id,
            task_data={
                "text1": "Hallo",
            },
        )

        engineworkflow = repository.load_workflow_instance(db=db_session, workflow_id=workflow.workflow_instance_id)
        faulty_tasks = service_workflow.get_faulty_tasks(engineworkflow)

        wait_for_results(mock_send_text_mail, 1, 3)

        assert len(faulty_tasks) == 1
        assert len(mock_send_text_mail) > 0


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
                service_application.admin_assign_task_to_user_without_checks(
                    db=db_session, admin_user_id=workflow.user(name).user.id, assign_to_user_id=workflow.user("other@example.com").user.id, task_id=tasks[0].id, remove_roles=False
                )
            else:
                with pytest.raises(UserMayNotAdministrateThisWorkflowException):
                    service_application.admin_assign_task_to_user_without_checks(
                        db=db_session, admin_user_id=workflow.user(name).user.id, assign_to_user_id=workflow.user("other@example.com").user.id, task_id=tasks[0].id, remove_roles=False
                    )


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
                service_application.admin_unassign_task_without_checks(db=db_session, admin_user_id=workflow.user(name).user.id, task_id=tasks[0].id)
            else:
                with pytest.raises(UserMayNotAdministrateThisWorkflowException):
                    service_application.admin_unassign_task_without_checks(db=db_session, admin_user_id=workflow.user(name).user.id, task_id=tasks[0].id)


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
                service_application.admin_cancel_workflow(db=db_session, user_id=workflow.user(name).user.id, workflow_instance_id=workflow.workflow_instance_id)
            else:
                with pytest.raises(UserMayNotAdministrateThisWorkflowException):
                    service_application.admin_cancel_workflow(db=db_session, user_id=workflow.user(name).user.id, workflow_instance_id=workflow.workflow_instance_id)
