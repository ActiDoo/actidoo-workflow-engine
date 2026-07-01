# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

import logging

from sqlalchemy import select

from actidoo_wfe.database import SessionLocal, setup_db
from actidoo_wfe.settings import settings
from actidoo_wfe.wf import service_form_templates
from actidoo_wfe.wf.bff.bff_user_schema import (
    ListFormTemplatesResponse,
    ResolveFormTemplateResponse,
    SaveFormTemplateResponse,
)
from actidoo_wfe.wf.exceptions import FormTemplatesDisabledException, TemplateNotFoundException
from actidoo_wfe.wf.models import WorkflowUserFormTemplate
from actidoo_wfe.wf.tests.helpers.client import Client
from actidoo_wfe.wf.tests.helpers.overrides import disable_role_check, override_get_user
from actidoo_wfe.wf.tests.helpers.workflow_dummy import WorkflowDummy

log: logging.Logger = logging.getLogger(__name__)

setup_db(settings=settings)

WF_NAME = "TestFlowBff"
FORM1_MIN = {"required_text": "ok", "short_code": "abc", "trigger_error": False}


def _start(db, extra_users=None):
    users = {"initiator": ["wf-user"]}
    if extra_users:
        users.update(extra_users)
    return WorkflowDummy(db_session=db, users_with_roles=users, workflow_name=WF_NAME, start_user="initiator")


def _form1_task(workflow):
    return workflow.user("initiator").get_usertasks(workflow.workflow_instance_id, 1)[0]


# --- service layer -----------------------------------------------------------


def test_save_filters_ineligible_fields_and_empty_values(db_engine_ctx):
    with db_engine_ctx():
        db = SessionLocal()
        workflow = _start(db)
        task = _form1_task(workflow)
        user_id = workflow.user("initiator").user.id

        row = service_form_templates.save_template(
            db=db,
            user_id=user_id,
            task_id=task.id,
            template_name="A",
            template_data={
                "required_text": "keep",
                "short_code": "no",  # template_field: false -> excluded
                "optional_note": "",  # empty -> dropped
                "trigger_error": False,  # boolean -> kept
                "attachment": {"filename": "x.pdf"},  # attachment -> excluded
            },
        )

        assert row.template_data == {"required_text": "keep", "trigger_error": False}


def test_preview_returns_eligible_fields(db_engine_ctx):
    with db_engine_ctx():
        db = SessionLocal()
        workflow = _start(db)
        task = _form1_task(workflow)
        user_id = workflow.user("initiator").user.id

        result = service_form_templates.preview_template(
            db=db,
            user_id=user_id,
            task_id=task.id,
            template_data={"required_text": "keep", "short_code": "no", "optional_note": "", "trigger_error": False},
        )

        assert result.applicable_data == {"required_text": "keep", "trigger_error": False}
        assert "short_code" in {item["key"] for item in result.skipped_fields}


def test_save_and_list_scoped(db_engine_ctx):
    with db_engine_ctx():
        db = SessionLocal()
        workflow = _start(db)
        task = _form1_task(workflow)
        user_id = workflow.user("initiator").user.id

        service_form_templates.save_template(db=db, user_id=user_id, task_id=task.id, template_name="A", template_data=FORM1_MIN)
        rows, mode = service_form_templates.list_templates(db=db, user_id=user_id, task_id=task.id)

        assert mode == "blacklist"
        assert [r.template_name for r in rows] == ["A"]
        assert rows[0].task_name == "Form1"
        assert rows[0].workflow_name == WF_NAME


def test_save_overwrites_same_name(db_engine_ctx):
    with db_engine_ctx():
        db = SessionLocal()
        workflow = _start(db)
        task = _form1_task(workflow)
        user_id = workflow.user("initiator").user.id

        service_form_templates.save_template(db=db, user_id=user_id, task_id=task.id, template_name="A", template_data={"required_text": "first"})
        service_form_templates.save_template(db=db, user_id=user_id, task_id=task.id, template_name="A", template_data={"required_text": "second"})

        rows = db.execute(select(WorkflowUserFormTemplate).where(WorkflowUserFormTemplate.user_id == user_id)).scalars().all()
        assert len(rows) == 1
        assert rows[0].template_data == {"required_text": "second"}


def test_resolve_surfaces_skipped_fields(db_engine_ctx):
    with db_engine_ctx():
        db = SessionLocal()
        workflow = _start(db)
        task = _form1_task(workflow)
        user_id = workflow.user("initiator").user.id

        # Stored data with a now-removed field and an ineligible field simulates schema drift.
        db.add(
            WorkflowUserFormTemplate(
                user_id=user_id,
                workflow_name=WF_NAME,
                task_name="Form1",
                template_name="drift",
                template_data={"required_text": "x", "short_code": "y", "ghost": "z"},
            )
        )
        db.flush()
        template_id = db.execute(select(WorkflowUserFormTemplate.id).where(WorkflowUserFormTemplate.template_name == "drift")).scalar_one()

        result = service_form_templates.resolve_template_for_apply(db=db, user_id=user_id, task_id=task.id, template_id=template_id)

        assert result.applicable_data == {"required_text": "x"}
        skipped_keys = {item["key"] for item in result.skipped_fields}
        assert "short_code" in skipped_keys
        assert "ghost" in skipped_keys


def test_delete_other_users_template_raises_not_found(db_engine_ctx):
    with db_engine_ctx():
        db = SessionLocal()
        workflow = _start(db, extra_users={"other": ["wf-user"]})
        task = _form1_task(workflow)
        owner_id = workflow.user("initiator").user.id
        other_id = workflow.user("other").user.id

        row = service_form_templates.save_template(db=db, user_id=owner_id, task_id=task.id, template_name="A", template_data=FORM1_MIN)

        try:
            service_form_templates.delete_template(db=db, user_id=other_id, template_id=row.id)
            assert False, "expected TemplateNotFoundException"
        except TemplateNotFoundException:
            pass


def test_save_on_off_form_raises(db_engine_ctx):
    with db_engine_ctx():
        db = SessionLocal()
        workflow = _start(db)
        # advance to Form2, whose template_mode is off
        workflow.user("initiator").submit(FORM1_MIN, workflow.workflow_instance_id, task_name="Form1")
        form2 = workflow.user("initiator").get_usertasks(workflow.workflow_instance_id, 1)[0]
        user_id = workflow.user("initiator").user.id

        rows, mode = service_form_templates.list_templates(db=db, user_id=user_id, task_id=form2.id)
        assert mode == "off"
        assert rows == []

        try:
            service_form_templates.save_template(db=db, user_id=user_id, task_id=form2.id, template_name="A", template_data={"confirmation": "x"})
            assert False, "expected FormTemplatesDisabledException"
        except FormTemplatesDisabledException:
            pass


# --- bff endpoints -----------------------------------------------------------


def test_bff_save_list_resolve_delete(db_engine_ctx):
    with db_engine_ctx():
        db = SessionLocal()
        workflow = _start(db)
        task = _form1_task(workflow)
        client = Client()

        with override_get_user(client=client, user=workflow.user("initiator").user), disable_role_check(client):
            status, saved = client.post(
                name="save_form_template",
                json={"task_id": str(task.id), "template_name": "Standard", "template_data": FORM1_MIN},
                cls=SaveFormTemplateResponse,
            )
            assert status == 200
            template_id = saved.id

            status, listing = client.post(name="list_form_templates", json={"task_id": str(task.id)}, cls=ListFormTemplatesResponse)
            assert status == 200
            assert listing.template_mode == "blacklist"
            assert [t.name for t in listing.templates] == ["Standard"]

            status, resolved = client.post(
                name="resolve_form_template",
                json={"task_id": str(task.id), "template_id": str(template_id)},
                cls=ResolveFormTemplateResponse,
            )
            assert status == 200
            assert resolved.applicable_data.get("required_text") == "ok"
            assert "short_code" not in resolved.applicable_data

            status, _ = client.post(name="delete_form_template", json={"template_id": str(template_id)})
            assert status == 200

            status, _ = client.post(name="resolve_form_template", json={"task_id": str(task.id), "template_id": str(template_id)})
            assert status == 404


def test_bff_save_on_off_form_returns_409(db_engine_ctx):
    with db_engine_ctx():
        db = SessionLocal()
        workflow = _start(db)
        workflow.user("initiator").submit(FORM1_MIN, workflow.workflow_instance_id, task_name="Form1")
        form2 = workflow.user("initiator").get_usertasks(workflow.workflow_instance_id, 1)[0]
        client = Client()

        with override_get_user(client=client, user=workflow.user("initiator").user), disable_role_check(client):
            status, _ = client.post(
                name="save_form_template",
                json={"task_id": str(form2.id), "template_name": "X", "template_data": {"confirmation": "x"}},
            )
            assert status == 409
