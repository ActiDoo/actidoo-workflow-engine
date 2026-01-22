# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

import logging
from datetime import timedelta

import pytest

from actidoo_wfe.helpers.time import dt_now_naive
from actidoo_wfe.database import SessionLocal, setup_db
from actidoo_wfe.settings import settings
from actidoo_wfe.wf import service_application
from actidoo_wfe.wf.bff import bff_admin
from actidoo_wfe.wf.bff.bff_admin_schema import (
    CancelWorkflowInstanceResponse,
    GetAllTasksResponse,
    GetAllWorkflowInstancesResponse,
    GetSingleTaskResponse,
)
from actidoo_wfe.wf.tests.helpers.overrides import override_get_user, disable_role_check
from actidoo_wfe.wf.tests.helpers.client import Client
from actidoo_wfe.wf.tests.helpers.workflow_dummy import WorkflowDummy

log: logging.Logger = logging.getLogger(__name__)

setup_db(settings=settings)

WF_NAME = "TestFlowFormValidation"
FORM_DATA = {"text1": "Value of text1"}


def _create_workflow_instance_and_complete_it(db):
    workflow = WorkflowDummy(
        db_session=db,
        users_with_roles={
            "admin": ["wf-admin"],
            "initiator": ["wf-user"],
        },
        workflow_name=WF_NAME,
        start_user="initiator",
    )

    workflow.user("initiator").submit(
        task_data=FORM_DATA,
        workflow_instance_id=workflow.workflow_instance_id,
    )

    return workflow

def test_admin_get_all_tasks(db_engine_ctx):
    with db_engine_ctx():
        db = SessionLocal()
        workflow = _create_workflow_instance_and_complete_it(db=db)
        client = Client()

        with override_get_user(client=client, user=workflow.user("admin").user), disable_role_check(client):
            status, json_resp = client.post(
                name="bff_admin_get_all_tasks", json={}, cls=GetAllTasksResponse
            )

        assert len(json_resp.ITEMS) > 0
        assert json_resp.ITEMS[0].completed_at is not None


def test_admin_get_all_workflow_instances(db_engine_ctx):
    with db_engine_ctx():
        db = SessionLocal()
        workflow = _create_workflow_instance_and_complete_it(db=db)
        client = Client()

        with override_get_user(client=client, user=workflow.user("admin").user), disable_role_check(client):
            status, json_resp = client.post(
                name="bff_admin_get_all_workflow_instances",
                json={},
                cls=GetAllWorkflowInstancesResponse,
            )

        assert len(json_resp.ITEMS) > 0


def test_cancel_workflow(db_engine_ctx):
    with db_engine_ctx():
        db = SessionLocal()

        workflow = WorkflowDummy(
            db_session=db,
            users_with_roles={
                "initiator": ["wf-user"],
                "admin": ["wf-admin"],
            },
            workflow_name=WF_NAME,
            start_user="initiator",
        )

        assert workflow.workflow_instance_id is not None

        client = Client()
        with override_get_user(client=client, user=workflow.user("admin").user), disable_role_check(client):
            status, json_resp = client.post(
                name="bff_admin_cancel_workflow_instance",
                json={
                    "workflow_instance_id": str(workflow.workflow_instance_id)
                },
                cls=CancelWorkflowInstanceResponse,
            )

        assert status == 200

        with override_get_user(client=client, user=workflow.user("admin").user), disable_role_check(client):
            status, json_resp = client.post(
                name="bff_admin_get_all_tasks", json={}, cls=GetAllTasksResponse
            )

        assert len(json_resp.ITEMS) > 0
        assert any(x.state_cancelled for x in json_resp.ITEMS)

def test_admin_assign(db_engine_ctx):
    with db_engine_ctx():
        db = SessionLocal()
        workflow = WorkflowDummy(
            db_session=db,
            users_with_roles={
                "admin": ["wf-admin"],
                "initiator": ["wf-user"],
                "reviewer": ["wf-user"],
            },
            workflow_name=WF_NAME,
            start_user="initiator",
        )

        task = workflow.user("initiator").get_usertasks(workflow.workflow_instance_id, 1)

        workflow.user("initiator").assign_task(
            task_id=task[0].id
        )

        client = Client()
        with override_get_user(client=client, user=workflow.user("admin").user), disable_role_check(client):
            status, json_resp = client.post(
                name="bff_admin_unassign_task", json={
                    "task_id": str(task[0].id)
                }, cls=GetSingleTaskResponse
            )

        assert json_resp.task.assigned_user is None

        with override_get_user(client=client, user=workflow.user("admin").user), disable_role_check(client):
            status, json_resp = client.post(
                name="bff_admin_assign_task", json={
                    "task_id": str(task[0].id),
                    "user_id": str(workflow.user("initiator").user.id)
                }, cls=GetSingleTaskResponse
            )

        assert json_resp.task.assigned_user is not None and str(json_resp.task.assigned_user.id) == str(workflow.user("initiator").user.id)


def test_admin_user_listing_and_delegations(db_engine_ctx):
    with db_engine_ctx():
        db = SessionLocal()
        dummy = WorkflowDummy(
            db_session=db,
            users_with_roles={
                "admin": ["wf-admin"],
                "principal": ["wf-user"],
                "delegate": ["wf-user"],
            },
        )

        admin = dummy.user("admin").user
        principal = dummy.user("principal").user
        delegate = dummy.user("delegate").user

        table_params = bff_admin.AdminWorkflowUsersBffTableQuerySchema.parse_obj({})
        users = service_application.bff_admin_get_all_users(
            db=db,
            user_id=admin.id,
            bff_table_request_params=table_params,
        )
        assert any(u.id == principal.id for u in users.ITEMS)

        detail = service_application.admin_get_user_detail(
            db=db, admin_user_id=admin.id, target_user_id=principal.id
        )
        assert detail.user.id == principal.id

        updated_detail = service_application.admin_set_user_delegations(
            db=db,
            admin_user_id=admin.id,
            principal_user_id=principal.id,
            delegations=[(delegate.id, dt_now_naive() + timedelta(days=1))],
        )

        assert any(d.delegate.id == delegate.id for d in updated_detail.delegations)

        filtered_params = bff_admin.AdminWorkflowUsersBffTableQuerySchema.parse_obj(
            {"f_roles": "wf-admin"}
        )
        filtered_users = service_application.bff_admin_get_all_users(
            db=db,
            user_id=admin.id,
            bff_table_request_params=filtered_params,
        )
        assert any(u.id == admin.id for u in filtered_users.ITEMS)
        assert all("wf-admin" in u.roles for u in filtered_users.ITEMS)
