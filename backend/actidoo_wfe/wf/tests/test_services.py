# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

import logging
from datetime import timedelta

import pytest
from sqlalchemy import select

import actidoo_wfe.wf.bff.bff_user_schema as bff_user_schema
from actidoo_wfe.database import SessionLocal, setup_db
from actidoo_wfe.helpers.time import dt_now_naive
from actidoo_wfe.settings import settings
from actidoo_wfe.wf import repository, service_application, service_form, service_i18n, service_user
from actidoo_wfe.wf.bff.bff_user import WorkflowInstancesBffTableQuerySchema
from actidoo_wfe.wf.exceptions import (
    TaskAlreadyAssignedToDifferentUserException,
    TaskCannotBeUnassignedException,
    TaskIsNotInReadyUsertasksException,
)
from actidoo_wfe.wf.models import WorkflowInstanceTask
from actidoo_wfe.wf.tests.helpers.client import Client
from actidoo_wfe.wf.tests.helpers.workflow_dummy import WorkflowDummy

log: logging.Logger = logging.getLogger(__name__)

setup_db(settings=settings)


# TODO out-commented for now, because get_workflow now expects a user-authorization
# def test_get_workflows(db_engine_ctx):
#     with db_engine_ctx():
#         client = Client()
#         status, json_resp = client.get("get_workflows", bff_user_schema.GetWorkflowsResponse)
#         assert len(json_resp.workflows) > 0


def test_user_roles(db_engine_ctx):
    with db_engine_ctx():
        db = SessionLocal()
        workflow = WorkflowDummy(
            db_session=db,
            users_with_roles={"user1": ["role1", "role2"], "user2": ["role2"]},
        )

        user1 = service_user.get_user(db=db, user_id=workflow.user("user1").user.id)
        assert user1 is not None
        assert "role1" in [r.role.name for r in user1.roles]
        assert "role2" in [r.role.name for r in user1.roles]

        user2 = service_user.get_user(db=db, user_id=workflow.user("user2").user.id)
        assert user2 is not None
        assert "role1" not in [r.role.name for r in user2.roles]
        assert "role2" in [r.role.name for r in user2.roles]

        service_user.assign_roles(db=db, user_id=user1.id, role_names=["role2", "role3"])

        user1 = service_user.get_user(db=db, user_id=workflow.user("user1").user.id)
        assert user1 is not None
        assert "role1" not in [r.role.name for r in user1.roles]
        assert "role2" in [r.role.name for r in user1.roles]
        assert "role3" in [r.role.name for r in user1.roles]

        user2 = service_user.get_user(db=db, user_id=workflow.user("user2").user.id)
        assert user2 is not None
        assert "role1" not in [r.role.name for r in user2.roles]
        assert "role2" in [r.role.name for r in user2.roles]


def test_search_users(db_engine_ctx):
    with db_engine_ctx():
        db = SessionLocal()
        workflow = WorkflowDummy(
            db_session=db,
            users_with_roles={
                "userA1": [],
                "userA2": [],
                "userA3": [],
                "userB4": [],
                "userB5": [],
                "userB6": [],
                "user kurt": [],
            },
        )

        results = service_user.search_users(db=db, search="user", include_value=None)

        # alle finden
        assert any(r.id == workflow.user("userA1").user.id for r in results)
        assert len(results) == 7

        # kein ergebnis
        results = service_user.search_users(db=db, search="abcdef", include_value=None)
        assert len(results) == 0

        # prefix suche
        results = service_user.search_users(db=db, search="userA", include_value=None)
        assert len(results) == 3

        # contains
        results = service_user.search_users(db=db, search="A3", include_value=None)
        assert len(results) == 1

        # multi word suche
        results = service_user.search_users(db=db, search="user kur", include_value=None)
        assert len(results) == 1

        # ID prefix suche
        results = service_user.search_users(
            db=db,
            search=str(workflow.user("userA1").user.id)[:5],
            include_value=None,
        )
        assert len(results) == 1

        # kein suchergebnis, aber include_value
        results = service_user.search_users(
            db=db,
            search="mööööh",
            include_value=str(workflow.user("userA1").user.id),
        )
        assert len(results) == 1

        # suchergebnis + include_value, aber nur ein result darf gefunden werden
        results = service_user.search_users(
            db=db,
            search=str(workflow.user("userA1").user.id)[:5],
            include_value=str(workflow.user("userA1").user.id),
        )
        assert len(results) == 1


def test_remove_datauri(db_engine_ctx):
    # This is an adjusted source from real data.
    # I kept it deeply nested and kept a lot more than the 'datauri' field,
    # with lists/objects/strings/bools as values, to thoroughly test the correct parsing.
    schema = {
        "definitions": {},
        "type": "object",
        "properties": {
            "travel_approver": True,
            "attachments": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "datauri": {"type": "string", "format": "data-url"},  # this must be removed
                        "filename": {"type": "string"},
                        "hash": {"type": "string"},
                        "id": {"type": "string"},
                        "mimetype": {"type": "string"},
                    },
                },
            },
            "department_approver": {
                "type": "string",
                "title": "Select your department.",
            },
        },
        "required": [
            "mail_header",
            "travel_region",
        ],
        "allOf": [
            {
                "if": {
                    "not": {
                        "not": {
                            "type": "object",
                            "properties": {"travel_region": {"const": "sonstiges", "default": ""}},
                        }
                    }
                },
                "else": {
                    "properties": {"travel_approver": {"type": "null"}},
                    "type": "object",
                },
            }
        ],
    }

    expected_transformation = {
        "definitions": {},
        "type": "object",
        "properties": {
            "travel_approver": True,
            "attachments": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        # "datauri": {"type": "string", "format": "data-url"},
                        "filename": {"type": "string"},
                        "hash": {"type": "string"},
                        "id": {"type": "string"},
                        "mimetype": {"type": "string"},
                    },
                },
            },
            "department_approver": {
                "type": "string",
                "title": "Select your department.",
            },
        },
        "required": [
            "mail_header",
            "travel_region",
        ],
        "allOf": [
            {
                "if": {
                    "not": {
                        "not": {
                            "type": "object",
                            "properties": {"travel_region": {"const": "sonstiges", "default": ""}},
                        }
                    }
                },
                "else": {
                    "properties": {"travel_approver": {"type": "null"}},
                    "type": "object",
                },
            }
        ],
    }

    service_form.remove_data_uri_fields(schema)

    assert expected_transformation == schema


def test_update_user_settings_success(db_engine_ctx):
    with db_engine_ctx():
        db = SessionLocal()
        # set up two users with roles (roles not used here, but WorkflowDummy creates users)
        workflow = WorkflowDummy(
            db_session=db,
            users_with_roles={"user1": ["role1", "role2"], "user2": ["role2"]},
        )
        user = workflow.user("user1").user  # get the WorkflowUser model
        # perform the update
        updated = service_user.update_user_settings(
            db=db,
            user_id=user.id,
            locale="fr-FR",
        )
        # assertions
        assert updated.id == user.id
        assert updated.locale == "fr-FR"

        # verify persisted
        reloaded = service_user.get_user_settings(db=db, user_id=user.id)
        assert reloaded.locale == "fr-FR"


def test_update_user_settings_invalid_locale(db_engine_ctx):
    with db_engine_ctx():
        db = SessionLocal()
        workflow = WorkflowDummy(
            db_session=db,
            users_with_roles={"userA": []},
        )
        user = workflow.user("userA").user

        with pytest.raises(ValueError):
            service_user.update_user_settings(
                db=db,
                user_id=user.id,
                locale="xx-XX",  # invalid # type: ignore
            )


def test_update_user_settings_with_delegations(db_engine_ctx):
    with db_engine_ctx():
        db = SessionLocal()
        workflow = WorkflowDummy(
            db_session=db,
            users_with_roles={"principal": ["wf-user"], "delegate": ["wf-user"]},
        )
        principal = workflow.user("principal").user
        delegate = workflow.user("delegate").user

        service_user.update_user_settings(
            db=db,
            user_id=principal.id,
            locale="en-US",
            delegations=[(delegate.id, dt_now_naive() + timedelta(days=5))],
        )

        delegations = service_user.list_user_delegations(db=db, principal_user_id=principal.id)
        assert len(delegations) == 1
        assert delegations[0].delegate_user_id == delegate.id

        service_user.update_user_settings(
            db=db,
            user_id=principal.id,
            locale="en-US",
            delegations=[],
        )

        delegations = service_user.list_user_delegations(db=db, principal_user_id=principal.id)
        assert delegations == []


def test_delegate_can_assign_and_submit_task(db_engine_ctx, mock_send_text_mail):
    with db_engine_ctx():
        db = SessionLocal()
        workflow = WorkflowDummy(
            db_session=db,
            users_with_roles={"initiator": ["wf-user"], "deputy": ["wf-user"]},
            workflow_name="TestFlow_Copy",
            start_user="initiator",
        )

        principal = workflow.user("initiator").user
        delegate = workflow.user("deputy").user

        service_user.set_user_delegations(
            db=db,
            principal_user_id=principal.id,
            delegations=[(delegate.id, dt_now_naive() + timedelta(days=1))],
        )

        delegate_tasks = service_application.get_usertasks_for_user_id(
            db=db,
            user_id=delegate.id,
            workflow_instance_id=workflow.workflow_instance_id,  # type: ignore[arg-type]
            state="ready",
        )

        assert len(delegate_tasks) == 1
        assert delegate_tasks[0].assigned_user is not None
        assert delegate_tasks[0].assigned_user.id == principal.id
        assert delegate_tasks[0].can_be_assigned_as_delegate is True

        table_params = WorkflowInstancesBffTableQuerySchema.parse_obj({})
        ready_workflows = service_application.bff_get_workflows_with_usertasks(
            db=db,
            bff_table_request_params=table_params,
            user_id=delegate.id,
            state="ready",
        )
        assert any(
            any(
                t.id == delegate_tasks[0].id
                and t.can_be_assigned_as_delegate is True
                for t in wf.active_tasks
            )
            for wf in ready_workflows.ITEMS
        )

        task_id = delegate_tasks[0].id
        service_application.assign_task_to_me(db=db, user_id=delegate.id, task_id=task_id)

        db_task = db.execute(
            select(WorkflowInstanceTask).where(WorkflowInstanceTask.id == task_id)
        ).scalar_one()
        assert db_task.assigned_user_id == principal.id
        assert db_task.assigned_delegate_user_id == delegate.id

        service_application.unassign_task_from_me(db=db, user_id=delegate.id, task_id=task_id)
        db_task = db.execute(
            select(WorkflowInstanceTask).where(WorkflowInstanceTask.id == task_id)
        ).scalar_one()
        assert db_task.assigned_user_id == principal.id
        assert db_task.assigned_delegate_user_id is None

        service_application.assign_task_to_me(db=db, user_id=delegate.id, task_id=task_id)
        db_task = db.execute(
            select(WorkflowInstanceTask).where(WorkflowInstanceTask.id == task_id)
        ).scalar_one()
        assert db_task.assigned_delegate_user_id == delegate.id

        service_application.submit_task_data(
            db=db,
            user_id=delegate.id,
            task_id=task_id,
            task_data={"text1": "handled"},
            delegate_comment="handled while away",
        )

        db_task = db.execute(
            select(WorkflowInstanceTask).where(WorkflowInstanceTask.id == task_id)
        ).scalar_one()
        assert db_task.completed_by_user_id == principal.id
        assert db_task.completed_by_delegate_user_id == delegate.id
        assert db_task.delegate_submit_comment == "handled while away"

        delegate_completed = service_application.get_usertasks_for_user_id(
            db=db,
            user_id=delegate.id,
            workflow_instance_id=workflow.workflow_instance_id,  # type: ignore[arg-type]
            state="completed",
        )
        assert len(delegate_completed) == 1
        assert delegate_completed[0].completed_by_delegate_user is not None
        assert delegate_completed[0].completed_by_delegate_user.id == delegate.id
        assert delegate_completed[0].can_be_assigned_as_delegate is False

        principal_completed = service_application.get_usertasks_for_user_id(
            db=db,
            user_id=principal.id,
            workflow_instance_id=workflow.workflow_instance_id,  # type: ignore[arg-type]
            state="completed",
        )
        assert len(principal_completed) == 1
        assert principal_completed[0].completed_by_user is not None
        assert principal_completed[0].completed_by_user.id == principal.id
        assert principal_completed[0].can_be_assigned_as_delegate is False

        delegate_workflows = service_application.bff_get_workflows_with_usertasks(
            db=db,
            bff_table_request_params=table_params,
            user_id=delegate.id,
            state="completed",
        )
        principal_workflows = service_application.bff_get_workflows_with_usertasks(
            db=db,
            bff_table_request_params=table_params,
            user_id=principal.id,
            state="completed",
        )

        assert any(
            any(t.id == task_id for t in wf.completed_tasks)
            for wf in delegate_workflows.ITEMS
        )
        assert any(
            any(t.id == task_id for t in wf.completed_tasks)
            for wf in principal_workflows.ITEMS
        )


def test_delegate_cannot_assign_without_permission(db_engine_ctx):
    with db_engine_ctx():
        db = SessionLocal()
        workflow = WorkflowDummy(
            db_session=db,
            users_with_roles={"initiator": ["wf-user"], "colleague": ["wf-user"]},
            workflow_name="TestFlow_Copy",
            start_user="initiator",
        )

        principal = workflow.user("initiator").user
        colleague = workflow.user("colleague").user

        ready_tasks = service_application.get_usertasks_for_user_id(
            db=db,
            user_id=principal.id,
            workflow_instance_id=workflow.workflow_instance_id,  # type: ignore[arg-type]
            state="ready",
        )
        task_id = ready_tasks[0].id

        with pytest.raises(TaskAlreadyAssignedToDifferentUserException):
            service_application.assign_task_to_me(db=db, user_id=colleague.id, task_id=task_id)

        service_user.set_user_delegations(
            db=db,
            principal_user_id=principal.id,
            delegations=[(colleague.id, dt_now_naive() - timedelta(days=1))],
        )

        with pytest.raises(TaskAlreadyAssignedToDifferentUserException):
            service_application.assign_task_to_me(db=db, user_id=colleague.id, task_id=task_id)


def test_delegate_unassign_active_assignment(db_engine_ctx):
    with db_engine_ctx():
        db = SessionLocal()
        workflow = WorkflowDummy(
            db_session=db,
            users_with_roles={"initiator": ["wf-user"], "helper": ["wf-user"]},
            workflow_name="TestFlow_Copy",
            start_user="initiator",
        )

        principal = workflow.user("initiator").user
        helper = workflow.user("helper").user

        service_user.set_user_delegations(
            db=db,
            principal_user_id=principal.id,
            delegations=[(helper.id, dt_now_naive() + timedelta(days=1))],
        )

        ready_tasks = service_application.get_usertasks_for_user_id(
            db=db,
            user_id=helper.id,
            workflow_instance_id=workflow.workflow_instance_id,  # type: ignore[arg-type]
            state="ready",
        )
        task_id = ready_tasks[0].id

        service_application.unassign_task_from_me(db=db, user_id=helper.id, task_id=task_id)
        db_task = db.execute(
            select(WorkflowInstanceTask).where(WorkflowInstanceTask.id == task_id)
        ).scalar_one()
        assert db_task.assigned_user_id == principal.id
        assert db_task.assigned_delegate_user_id is None


def test_principal_must_unassign_delegate_before_submit(db_engine_ctx):
    with db_engine_ctx():
        db = SessionLocal()
        workflow = WorkflowDummy(
            db_session=db,
            users_with_roles={"initiator": ["wf-user"], "helper": ["wf-user"]},
            workflow_name="TestFlow_Copy",
            start_user="initiator",
        )

        principal = workflow.user("initiator").user
        helper = workflow.user("helper").user

        service_user.set_user_delegations(
            db=db,
            principal_user_id=principal.id,
            delegations=[(helper.id, dt_now_naive() + timedelta(days=1))],
        )

        delegate_tasks = service_application.get_usertasks_for_user_id(
            db=db,
            user_id=helper.id,
            workflow_instance_id=workflow.workflow_instance_id,  # type: ignore[arg-type]
            state="ready",
        )
        task_id = delegate_tasks[0].id

        service_application.assign_task_to_me(db=db, user_id=helper.id, task_id=task_id)

        with pytest.raises(TaskIsNotInReadyUsertasksException):
            service_application.submit_task_data(
                db=db,
                user_id=principal.id,
                task_id=task_id,
                task_data={"text1": "handled"},
            )

        service_application.unassign_task_from_me(db=db, user_id=helper.id, task_id=task_id)
        service_application.submit_task_data(
            db=db,
            user_id=principal.id,
            task_id=task_id,
            task_data={"text1": "handled"},
        )


def test_cannot_unassign_completed_task(db_engine_ctx):
    with db_engine_ctx():
        db = SessionLocal()
        workflow = WorkflowDummy(
            db_session=db,
            users_with_roles={"initiator": ["wf-user"]},
            workflow_name="TestFlow_Copy",
            start_user="initiator",
        )

        principal = workflow.user("initiator").user
        ready_tasks = service_application.get_usertasks_for_user_id(
            db=db,
            user_id=principal.id,
            workflow_instance_id=workflow.workflow_instance_id,  # type: ignore[arg-type]
            state="ready",
        )
        task_id = ready_tasks[0].id

        service_application.assign_task_to_me(db=db, user_id=principal.id, task_id=task_id)
        service_application.submit_task_data(
            db=db,
            user_id=principal.id,
            task_id=task_id,
            task_data={"text1": "handled"},
        )

        with pytest.raises(TaskCannotBeUnassignedException):
            service_application.unassign_task_from_me(db=db, user_id=principal.id, task_id=task_id)
        db_task = db.execute(
            select(WorkflowInstanceTask).where(WorkflowInstanceTask.id == task_id)
        ).scalar_one()
        assert db_task.assigned_user_id == principal.id
        assert db_task.assigned_delegate_user_id is None

def test_supported_locales_fit_db_column():
    service_i18n.get_supported_locales.cache_clear()
    locales = service_i18n.get_supported_locales()
    assert locales  # ensure at least one locale is available
    assert all(len(loc["key"]) <= service_i18n.MAX_LOCALE_KEY_LENGTH for loc in locales)

@pytest.mark.parametrize(
    "header,expected",
    [
        # exact primary extraction
        ("en-US,en;q=0.9", "en-US"),
        ("de-DE;q=0.9,en;q=0.8", "de-DE"),
        # without country will not match any
        ("fr;q=0.9,en;q=0.8", None),
        # no valid entries
        ("es,pt;q=0.9", None),
        ("", None),
        ("not-a-header", None),
        # without country will not match any
        ("en;q=0.5,en;q=0.9", None), 
        # case preserved
        ("EN-US,en;q=0.9", "en-US"),
        ("DE-DE,de;q=0.9", "de-DE"),
        # malformed segments ignored
        (" , ;q=,de-DE;q=not,aabb;;q=0.5,en-US", "en-US"),
    ],
)
def test_extract_primary_locale(header, expected):
    assert service_i18n.extract_primary_locale(header) == expected


@pytest.mark.parametrize(
    "user_locale,available,default,expected",
    [
        # 1. exact match
        ("en-US", ["en", "de"], "de", "en"),
        # 2. fallback region→base
        ("de-DE", ["de", "en"], "en", "de"),
        # 3. language-only match
        ("fr", ["en", "fr"], "en", "fr"),
        # 4. no match→default
        ("es", ["en", "de"], "en", "en"),
        # 5. direct base match
        ("de", ["de", "en"], "en", "de"),
        # 6. single available
        ("en", ["en"], "de", "en"),
        # 7. region-specific supported
        ("en-GB", ["en-GB", "en"], "en", "en-GB"),
        # 8. case-insensitive fallback
        ("EN-us", ["en-US", "en"], "en", "en-US"),
    ],
)
def test_match_translation(user_locale, available, default, expected, monkeypatch):
    # configure default fallback
    monkeypatch.setattr(settings, "default_locale", default)

    result = service_i18n.match_translation(user_locale=user_locale, available=available)
    assert result == expected, (
        f"match_translation({user_locale!r}, {available}, default={default!r}) -> {result!r}, "
        f"expected {expected!r}"
    )
