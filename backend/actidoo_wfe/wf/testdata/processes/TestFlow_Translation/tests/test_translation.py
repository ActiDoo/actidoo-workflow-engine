# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

from actidoo_wfe.database import SessionLocal
from actidoo_wfe.wf import service_application, service_i18n
from actidoo_wfe.wf.bff.bff_user import WorkflowInstancesBffTableQuerySchema
from actidoo_wfe.wf.tests.helpers.workflow_dummy import WorkflowDummy

WF_NAME = "TestFlow_Translation"  # must match the "Process ID" inside bpmn and the folder name in actidoo_wfe/wf/processes (but not the bpmn file name itself)

FILL_FORM_DATA = {}


def test_translation(db_engine_ctx):
    with db_engine_ctx():
        db_session = SessionLocal()

        workflow = WorkflowDummy(
            db_session=db_session,
            users_with_roles={
                "initiator": ["wf-user"],
            },
            workflow_name=WF_NAME,
            start_user="initiator",
        )

        workflow.user("initiator").user.locale = "en-US"

        service_i18n.compile_all()
        tasks = workflow.user("initiator").get_usertasks(workflow.workflow_instance_id, 1)
        task = tasks[0]

        assert task.uischema
        assert task.jsonschema

        assert task.uischema["Field_1pi0zgp"]["ui:description"] == "Translation test, this should be English"
        assert task.jsonschema["properties"]["textfield1"]["title"] == "First entry"
        assert task.jsonschema["properties"]["select1"]["title"] == "My translated selection field"
        assert task.jsonschema["properties"]["select1"]["oneOf"][0]["title"] == "First value (English translated)"
        assert task.jsonschema["properties"]["select1"]["oneOf"][1]["title"] == "Second value (English translated)"
        assert task.uischema["dynamiclist1"]["ui:label"] == "My translated dynamic list"
        assert task.jsonschema["properties"]["dynamiclist1"]["items"]["properties"]["textfield1"]["title"] == "The inner field (translated)"
        assert task.lane == "en9"
        assert task.title == "The first task"

        items = service_application.bff_get_workflows_with_usertasks(
            db=db_session,
            bff_table_request_params=WorkflowInstancesBffTableQuerySchema(),
            user_id=workflow.user("initiator").user.id,
            state="ready",
        )
        assert items.ITEMS[0].title == "English name of the process"


def test_getAllowedWorkflowsToStart_translatesTitlePerUserLocale(db_engine_ctx):
    with db_engine_ctx():
        db_session = SessionLocal()

        workflow = WorkflowDummy(
            db_session=db_session,
            users_with_roles={"initiator": ["wf-user"]},
            workflow_name=WF_NAME,
            start_user="initiator",
        )

        service_i18n.compile_all()
        # Caching: get_workflow_title_cached is @cache'd on (name, locale).
        # Tests run in isolated workers, but make sure prior calls don't bleed.
        from actidoo_wfe.wf import service_workflow
        service_workflow.get_workflow_title_cached.cache_clear()

        user = workflow.user("initiator").user
        user.locale = "en-US"
        db_session.commit()

        results = service_application.get_allowed_workflows_to_start(db=db_session, user_id=user.id)
        translated = next((w for w in results if w.name == WF_NAME), None)
        assert translated is not None
        assert translated.title == "English name of the process"

        # Different locale: German .po has its own translation for the process title.
        service_workflow.get_workflow_title_cached.cache_clear()
        user.locale = "de-DE"
        db_session.commit()

        results = service_application.get_allowed_workflows_to_start(db=db_session, user_id=user.id)
        translated_de = next((w for w in results if w.name == WF_NAME), None)
        assert translated_de is not None
        assert translated_de.title == "Der deutsche Name des Prozesses"


def test_getWorkflowStatistics_translatesTitlePerUserLocale(db_engine_ctx):
    with db_engine_ctx():
        db_session = SessionLocal()

        workflow = WorkflowDummy(
            db_session=db_session,
            users_with_roles={"initiator": ["wf-user"]},
            workflow_name=WF_NAME,
            start_user="initiator",
        )

        service_i18n.compile_all()
        from actidoo_wfe.wf import service_workflow
        service_workflow.get_workflow_title_cached.cache_clear()

        user = workflow.user("initiator").user
        user.locale = "en-US"
        db_session.commit()

        stats = service_application.get_workflow_statistics(db=db_session, user_id=user.id)
        entry = next((s for s in stats if s.name == WF_NAME), None)
        assert entry is not None
        assert entry.title == "English name of the process"

        service_workflow.get_workflow_title_cached.cache_clear()
        user.locale = "de-DE"
        db_session.commit()

        stats = service_application.get_workflow_statistics(db=db_session, user_id=user.id)
        entry_de = next((s for s in stats if s.name == WF_NAME), None)
        assert entry_de is not None
        assert entry_de.title == "Der deutsche Name des Prozesses"


def test_bffAdminGetAllWorkflowInstances_translatesTitlePerUserLocale(db_engine_ctx):
    from actidoo_wfe.wf.bff.bff_admin import AdminWorkflowInstancesBffTableQuerySchema

    with db_engine_ctx():
        db_session = SessionLocal()

        workflow = WorkflowDummy(
            db_session=db_session,
            users_with_roles={"admin": ["wf-user", "wf-admin"]},
            workflow_name=WF_NAME,
            start_user="admin",
        )

        service_i18n.compile_all()

        admin = workflow.user("admin").user
        admin.locale = "en-US"
        db_session.commit()

        result = service_application.bff_admin_get_all_workflow_instances(
            db=db_session,
            user_id=admin.id,
            bff_table_request_params=AdminWorkflowInstancesBffTableQuerySchema(),
        )
        instance = next((i for i in result.ITEMS if i.name == WF_NAME), None)
        assert instance is not None
        assert instance.title == "English name of the process"

        admin.locale = "de-DE"
        db_session.commit()

        result_de = service_application.bff_admin_get_all_workflow_instances(
            db=db_session,
            user_id=admin.id,
            bff_table_request_params=AdminWorkflowInstancesBffTableQuerySchema(),
        )
        instance_de = next((i for i in result_de.ITEMS if i.name == WF_NAME), None)
        assert instance_de is not None
        assert instance_de.title == "Der deutsche Name des Prozesses"


def test_adminGetTaskStatesPerWorkflow_translatesTaskTitlePerAdminLocale(db_engine_ctx):
    with db_engine_ctx():
        db_session = SessionLocal()

        workflow = WorkflowDummy(
            db_session=db_session,
            users_with_roles={"admin": ["wf-user", "wf-admin"]},
            workflow_name=WF_NAME,
            start_user="admin",
        )

        service_i18n.compile_all()

        admin = workflow.user("admin").user
        admin.locale = "en-US"
        db_session.commit()

        result = service_application.admin_get_task_states_per_workflow(db=db_session, wf_name=WF_NAME, admin_user_id=admin.id)
        # The active user task in the BPMN is "SimpleForm.userTask" with msgid "Un formulaire simple avec des sélections"
        assert any("The first task" == ts.title for ts in result.tasks.values()), f"Got titles: {[ts.title for ts in result.tasks.values()]}"

        admin.locale = "de-DE"
        db_session.commit()

        result_de = service_application.admin_get_task_states_per_workflow(db=db_session, wf_name=WF_NAME, admin_user_id=admin.id)
        assert any("Die erste Aufgabe" == ts.title for ts in result_de.tasks.values()), f"Got titles: {[ts.title for ts in result_de.tasks.values()]}"
