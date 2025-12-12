from actidoo_wfe.database import SessionLocal
from actidoo_wfe.wf import service_application, service_i18n
from actidoo_wfe.wf.bff.bff_user import WorkflowInstancesBffTableQuerySchema
from actidoo_wfe.wf.tests.helpers.workflow_dummy import WorkflowDummy

WF_NAME = "TestFlow_Translation" # must match the "Process ID" inside bpmn and the folder name in actidoo_wfe/wf/processes (but not the bpmn file name itself)

FILL_FORM_DATA = {

}

def test_translation(db_engine_ctx):
    with db_engine_ctx():
        db_session = SessionLocal()

        workflow = WorkflowDummy(
            db_session=db_session,
            users_with_roles={
                "initiator": ["wf-user"]
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
            state='ready'
        )
        assert items.ITEMS[0].title == "English name of the process"
        