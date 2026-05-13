# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""Tests for the behaviour when a workflow definition is removed from any registered provider
but instances of that workflow are still present in the database.

Setup pattern: start a workflow normally (provider present), then clear the registry to
simulate the definition being dropped. The instance rows and their tasks remain in the DB,
so we can verify that the BFF and engine-side paths handle the orphan state gracefully.
"""

from __future__ import annotations

import pytest

from actidoo_wfe.database import SessionLocal
from actidoo_wfe.wf import providers as workflow_providers
from actidoo_wfe.wf import repository, service_application, service_i18n
from actidoo_wfe.wf.bff.bff_user import WorkflowInstancesBffTableQuerySchema
from actidoo_wfe.wf.mail import send_personal_status_mail
from actidoo_wfe.wf.tests.helpers.workflow_dummy import WorkflowDummy
from actidoo_wfe.wf.types import ReactJsonSchemaFormData

WF_NAME = "TestFlowMailNotifications"


@pytest.fixture
def restore_registry():
    """Ensure the registry is restored to its initial state after the test."""
    try:
        yield
    finally:
        workflow_providers.registry.reload()


def _start_workflow_with_ready_task():
    db_session = SessionLocal()
    wf = WorkflowDummy(
        db_session=db_session,
        users_with_roles={
            "initiator": ["wf-user"],
            "other@example.com": ["wf-user"],
        },
        workflow_name=WF_NAME,
        start_user="initiator",
    )
    return wf, db_session


# ---------------------------------------------------------------------------
# i18n hardening (Test H)
# ---------------------------------------------------------------------------


def test_translate_string_returns_msgid_when_workflow_definition_is_missing(restore_registry):
    workflow_providers.registry.clear()

    result = service_i18n.translate_string(
        msgid="A title that should not be translated",
        workflow_name="NonExistentWorkflow",
        locale="en-US",
    )

    assert result == "A title that should not be translated"


def test_translate_form_data_returns_unchanged_when_workflow_definition_is_missing(restore_registry):
    workflow_providers.registry.clear()

    form = ReactJsonSchemaFormData(
        jsonschema={"title": "My title", "properties": {"a": {"title": "A"}}},
        uischema={"ui:label": "Label"},
    )

    result = service_i18n.translate_form_data(
        form_data=form,
        workflow_name="NonExistentWorkflow",
        locale="en-US",
    )

    assert result.jsonschema == form.jsonschema
    assert result.uischema == form.uischema


def test_workflow_definition_available_reflects_registry_state(restore_registry):
    assert workflow_providers.workflow_definition_available(WF_NAME) is True

    workflow_providers.registry.clear()
    assert workflow_providers.workflow_definition_available(WF_NAME) is False

    workflow_providers.registry.reload()
    assert workflow_providers.workflow_definition_available(WF_NAME) is True


# ---------------------------------------------------------------------------
# BFF read-only behaviour (Test A, G)
# ---------------------------------------------------------------------------


def test_bff_get_workflows_with_usertasks_marks_orphans_readonly(db_engine_ctx, restore_registry):
    with db_engine_ctx():
        workflow, db = _start_workflow_with_ready_task()
        user_id = workflow.user("initiator").user.id

        workflow_providers.registry.clear()

        table_params = WorkflowInstancesBffTableQuerySchema.parse_obj({})
        result = service_application.bff_get_workflows_with_usertasks(
            db=db,
            bff_table_request_params=table_params,
            user_id=user_id,
            state="ready",
        )

        assert len(result.ITEMS) >= 1
        orphan_items = [i for i in result.ITEMS if i.id == workflow.workflow_instance_id]
        assert len(orphan_items) == 1
        orphan = orphan_items[0]
        assert orphan.is_readonly is True
        for task in orphan.active_tasks:
            assert task.is_readonly is True
            assert task.can_be_assigned_as_delegate is False


def test_get_usertasks_for_user_id_marks_tasks_readonly(db_engine_ctx, restore_registry):
    with db_engine_ctx():
        workflow, db = _start_workflow_with_ready_task()
        user_id = workflow.user("initiator").user.id

        workflow_providers.registry.clear()

        tasks = service_application.get_usertasks_for_user_id(
            db=db,
            user_id=user_id,
            workflow_instance_id=workflow.workflow_instance_id,
            state="ready",
        )

        assert len(tasks) >= 1
        for t in tasks:
            assert t.is_readonly is True
            assert t.can_be_unassigned is False
            assert t.can_cancel_workflow is False
            assert t.can_delete_workflow is False
            assert t.can_be_assigned_as_delegate is False


def test_bff_admin_get_all_tasks_marks_orphan_tasks_readonly(db_engine_ctx, restore_registry):
    from actidoo_wfe.wf import service_user
    from actidoo_wfe.wf.bff.bff_admin import AdminWorkflowInstanceTasksBffTableQuerySchema

    with db_engine_ctx():
        workflow, db = _start_workflow_with_ready_task()
        admin_id = workflow.user("initiator").user.id
        service_user.assign_roles(db=db, user_id=admin_id, role_names=["wf-admin", f"{WF_NAME}-admin"])
        db.commit()

        workflow_providers.registry.clear()

        params = AdminWorkflowInstanceTasksBffTableQuerySchema.parse_obj({})
        tasks = service_application.bff_admin_get_all_tasks(
            db=db,
            user_id=admin_id,
            bff_table_request_params=params,
        )

        orphan_tasks = [t for t in tasks.ITEMS if t.workflow_instance.id == workflow.workflow_instance_id]
        assert len(orphan_tasks) >= 1
        for t in orphan_tasks:
            assert t.is_readonly is True
            assert t.workflow_instance.is_readonly is True
            assert t.can_be_unassigned is False


def test_bff_admin_get_all_workflow_instances_marks_orphans_readonly(db_engine_ctx, restore_registry):
    with db_engine_ctx():
        workflow, db = _start_workflow_with_ready_task()
        admin_id = workflow.user("initiator").user.id
        # Make the initiator a workflow admin so they see all instances.
        from actidoo_wfe.wf import service_user

        service_user.assign_roles(db=db, user_id=admin_id, role_names=["wf-admin", f"{WF_NAME}-admin"])
        db.commit()

        workflow_providers.registry.clear()

        table_params = WorkflowInstancesBffTableQuerySchema.parse_obj({})
        result = service_application.bff_admin_get_all_workflow_instances(
            db=db,
            bff_table_request_params=table_params,
            user_id=admin_id,
        )

        orphan_items = [i for i in result.ITEMS if i.id == workflow.workflow_instance_id]
        assert len(orphan_items) == 1
        assert orphan_items[0].is_readonly is True


def test_bff_marks_readonly_only_for_missing_definitions(db_engine_ctx, restore_registry):
    """Live workflows next to orphan ones must not be marked read-only."""
    with db_engine_ctx():
        workflow, db = _start_workflow_with_ready_task()
        user_id = workflow.user("initiator").user.id

        # Registry intact: nothing should be marked read-only.
        table_params = WorkflowInstancesBffTableQuerySchema.parse_obj({})
        result = service_application.bff_get_workflows_with_usertasks(
            db=db,
            bff_table_request_params=table_params,
            user_id=user_id,
            state="ready",
        )

        for item in result.ITEMS:
            assert item.is_readonly is False
            for task in item.active_tasks:
                assert task.is_readonly is False


# ---------------------------------------------------------------------------
# Engine-side stilllegung (Test B, C, D)
# ---------------------------------------------------------------------------


def test_send_personal_status_mail_skips_orphan_instances(db_engine_ctx, restore_registry, mock_send_text_mail):
    with db_engine_ctx():
        workflow, db = _start_workflow_with_ready_task()

        workflow_providers.registry.clear()

        send_personal_status_mail(db=db)

        # No mail should be sent because the orphan instance is filtered out.
        assert len(mock_send_text_mail) == 0


def test_handle_timeevents_does_not_crash_on_orphan_instance(db_engine_ctx, restore_registry):
    """handle_timeevents must not crash if a workflow definition is missing.
    Timer events for orphan instances are simply skipped.
    """
    with db_engine_ctx():
        workflow, db = _start_workflow_with_ready_task()

        workflow_providers.registry.clear()

        # Should not raise — there may or may not be timer events, but the cron path must be stable.
        service_application.handle_timeevents(db=db)


def test_handle_timeevents_does_not_loop_forever_on_orphan_events(db_engine_ctx, restore_registry):
    """Regression test: when an orphan workflow has due timer events that we skip without
    advancing their status, the outer batching loop in handle_timeevents must still terminate.
    """
    import datetime as _dt
    import uuid as _uuid

    from actidoo_wfe.helpers.time import dt_now_naive
    from actidoo_wfe.wf.models import WorkflowTimeEvent

    with db_engine_ctx():
        workflow, db = _start_workflow_with_ready_task()

        # Seed a due timer event for the (about-to-be-orphan) instance.
        wte = WorkflowTimeEvent(
            id=_uuid.uuid4(),
            workflow_instance_id=workflow.workflow_instance_id,
            timer_task_id=_uuid.uuid4(),
            timer_kind="time_date",
            due_at=dt_now_naive() - _dt.timedelta(minutes=1),
            interrupting=True,
            status="scheduled",
        )
        db.add(wte)
        db.commit()

        workflow_providers.registry.clear()

        # If the skip path leaves the timer "scheduled", list_due_time_events would return
        # the same batch forever. Use a very small batch_size so a bug would manifest immediately.
        service_application.handle_timeevents(db=db, batch_size=1)

        # Timer must still be "scheduled" (we don't destructively cancel it).
        db.refresh(wte)
        assert wte.status == "scheduled"


def test_handle_messages_does_not_crash_on_orphan_instance(db_engine_ctx, restore_registry):
    """handle_messages must not crash if a workflow definition is missing."""
    with db_engine_ctx():
        workflow, db = _start_workflow_with_ready_task()

        workflow_providers.registry.clear()

        # Should not raise.
        service_application.handle_messages(db=db)


# ---------------------------------------------------------------------------
# Recovery (Test E)
# ---------------------------------------------------------------------------


def test_orphan_instance_recovers_when_provider_returns(db_engine_ctx, restore_registry):
    """When the registry is restored, the instance becomes non-readonly again automatically."""
    with db_engine_ctx():
        workflow, db = _start_workflow_with_ready_task()
        user_id = workflow.user("initiator").user.id

        # Orphan phase
        workflow_providers.registry.clear()
        table_params = WorkflowInstancesBffTableQuerySchema.parse_obj({})
        result = service_application.bff_get_workflows_with_usertasks(
            db=db,
            bff_table_request_params=table_params,
            user_id=user_id,
            state="ready",
        )
        orphan = [i for i in result.ITEMS if i.id == workflow.workflow_instance_id][0]
        assert orphan.is_readonly is True

        # Recovery phase
        workflow_providers.registry.reload()
        result = service_application.bff_get_workflows_with_usertasks(
            db=db,
            bff_table_request_params=table_params,
            user_id=user_id,
            state="ready",
        )
        recovered = [i for i in result.ITEMS if i.id == workflow.workflow_instance_id][0]
        assert recovered.is_readonly is False


# ---------------------------------------------------------------------------
# Repository-level helpers
# ---------------------------------------------------------------------------


def test_submit_task_data_raises_workflow_definition_missing(db_engine_ctx, restore_registry):
    """Write paths on an orphan must raise WorkflowDefinitionMissingError so the FastAPI
    handler can return HTTP 410.
    """
    import pytest as _pytest

    from actidoo_wfe.wf.exceptions import WorkflowDefinitionMissingError

    with db_engine_ctx():
        workflow, db = _start_workflow_with_ready_task()
        user_id = workflow.user("initiator").user.id
        tasks = service_application.get_usertasks_for_user_id(
            db=db,
            user_id=user_id,
            workflow_instance_id=workflow.workflow_instance_id,
            state="ready",
        )
        task_id = tasks[0].id

        workflow_providers.registry.clear()

        with _pytest.raises(WorkflowDefinitionMissingError) as exc_info:
            service_application.submit_task_data(
                db=db,
                user_id=user_id,
                task_id=task_id,
                task_data={},
            )
        assert exc_info.value.workflow_name == WF_NAME


def test_orphan_submit_returns_410_via_http(db_engine_ctx, restore_registry):
    """End-to-end: HTTP POST against submit_task_data on an orphan task → 410."""
    from actidoo_wfe.fastapi import app as root_app
    from actidoo_wfe.wf.tests.helpers.client import Client
    from actidoo_wfe.wf.tests.helpers.overrides import disable_role_check, override_get_user

    with db_engine_ctx():
        workflow, db = _start_workflow_with_ready_task()
        user = workflow.user("initiator").user
        tasks = service_application.get_usertasks_for_user_id(
            db=db,
            user_id=user.id,
            workflow_instance_id=workflow.workflow_instance_id,
            state="ready",
        )
        task_id = tasks[0].id

        workflow_providers.registry.clear()

        client = Client()
        with override_get_user(client=client, user=user), disable_role_check(client):
            response = client.root_client.post(
                root_app.url_path_for("submit_task_data"),
                params={"task_id": str(task_id)},
                json={},
            )

        assert response.status_code == 410
        body = response.json()
        assert body["code"] == "workflow_definition_missing"
        assert body["workflow_name"] == WF_NAME


def test_search_property_options_does_not_crash_on_orphan(db_engine_ctx, restore_registry):
    """When the workflow definition is gone we can't reach the workflow's options/ folder.
    The endpoint must echo back already-selected values instead of crashing.
    """
    with db_engine_ctx():
        workflow, db = _start_workflow_with_ready_task()
        user_id = workflow.user("initiator").user.id
        tasks = service_application.get_usertasks_for_user_id(
            db=db,
            user_id=user_id,
            workflow_instance_id=workflow.workflow_instance_id,
            state="ready",
        )
        assert len(tasks) >= 1
        task_id = tasks[0].id

        workflow_providers.registry.clear()

        # Should not raise; should echo back include_value as the only option.
        opts = service_application.search_property_options(
            db=db,
            user_id=user_id,
            task_id=task_id,
            property_path=["someField"],
            search="",
            include_value="already-selected-value",
            form_data=None,
        )
        assert opts == [("already-selected-value", "already-selected-value")]


def test_get_workflow_instance_name_returns_name(db_engine_ctx, restore_registry):
    with db_engine_ctx():
        workflow, db = _start_workflow_with_ready_task()
        name = repository.get_workflow_instance_name(db=db, workflow_instance_id=workflow.workflow_instance_id)
        assert name == WF_NAME


def test_get_workflow_instance_name_by_task_id_returns_name(db_engine_ctx, restore_registry):
    with db_engine_ctx():
        workflow, db = _start_workflow_with_ready_task()
        user_id = workflow.user("initiator").user.id
        tasks = service_application.get_usertasks_for_user_id(
            db=db,
            user_id=user_id,
            workflow_instance_id=workflow.workflow_instance_id,
            state="ready",
        )
        assert len(tasks) >= 1
        name = repository.get_workflow_instance_name_by_task_id(db=db, task_id=tasks[0].id)
        assert name == WF_NAME
