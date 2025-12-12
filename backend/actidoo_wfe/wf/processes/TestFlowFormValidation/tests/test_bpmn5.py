import pytest
from jsonschema.exceptions import ValidationError

from actidoo_wfe.database import SessionLocal
from actidoo_wfe.wf.exceptions import ValidationResultContainsErrors
from actidoo_wfe.wf.tests.helpers.workflow_dummy import WorkflowDummy

WF_NAME = "TestFlowFormValidation" # must match the "Process ID" inside bpmn and the folder name in actidoo_wfe/wf/processes (but not the bpmn file name itself)

def start_my_workflow():
    db_session=SessionLocal()
    wf = WorkflowDummy(
            
            db_session=db_session,
            users_with_roles={
                "initiator": ["wf-user"]
            },            
            workflow_name=WF_NAME,
            start_user="initiator",
        )
    
    return wf, db_session

def test_startWorkflow_hasTasksForInitiator_whenThereIsALaneMapping(db_engine_ctx):
    with db_engine_ctx():
        workflow, db_session = start_my_workflow()

        # expect 1 user tasks, there is a lane mapping which will add the initiator to the user task
        workflow.user("initiator").get_usertasks(workflow.workflow_instance_id, 1)

def test_submit_fails_forEmptyTaskDataWhenRequired(db_engine_ctx):
    with db_engine_ctx():
        workflow, db_session = start_my_workflow()

        # 'initiator' initiates and submits a workflow with EMPTY task data, which will fail
        with pytest.raises(ValidationResultContainsErrors):
            workflow.user("initiator").submit(
                task_data={}, # --> empty task data!
                workflow_instance_id = workflow.workflow_instance_id,
            )

        # 'initiator' initiates and submits a workflow with wrong task data, which will fail
        with pytest.raises(ValidationResultContainsErrors):
            workflow.user("initiator").submit(
                task_data={
                    "junk": "yard"
                }, # --> wrong task data!
                workflow_instance_id = workflow.workflow_instance_id,
            )

        # afterwards the user still has this task:
        workflow.user("initiator").get_usertasks(workflow.workflow_instance_id, 1)

def test_submit_fails_forWrongTaskDataWhenRequired(db_engine_ctx):
    with db_engine_ctx():
        workflow, db_session = start_my_workflow()

        # 'initiator' initiates and submits a workflow with WRONG task data, which will fail
        with pytest.raises(ValidationResultContainsErrors):
            workflow.user("initiator").submit(
                task_data={
                    "junk": "yard"
                }, # --> wrong task data!
                workflow_instance_id = workflow.workflow_instance_id,
            )

        # afterwards the user still has this task:
        workflow.user("initiator").get_usertasks(workflow.workflow_instance_id, 1)

def test_submit_succeeds_forRequiredTaskData(db_engine_ctx):
    with db_engine_ctx():
        workflow, db_session = start_my_workflow()

        # 'initiator' initiates and submits a workflow
        workflow.user("initiator").submit(
            task_data={
                "text1": "Value of text1"
            },
            workflow_instance_id = workflow.workflow_instance_id,
        )

        # afterwards the initiator has no more tasks:
        workflow.user("initiator").get_usertasks(workflow.workflow_instance_id, 0)

# TODO für neuen Test:
# eigentlich dürfte user.submit() keine Exception raisen, weil das der richtige Code auch nicht macht.

# Problem: User submitted seine Task, das ist noch in Ordnung, Task wird als READY (64) auch eingetragen.
# Der Workflow wird allerdings weiter ausgeführt und wenn es dann bei einer Service Task zu einem Fehler kommt...
# ....tja, was dann machen? Dann müsste man irgendwie im UI bekanntgeben, dass die User Task okay gelaufen ist,
# es danach aber zu einem Fehler gekommen ist und man es weiter probieren muss.


# id                                  |created_at                   |completed_at                 |workflow_instance_id                |assigned_user_id                    |can_be_unassigned|state|state_ready|state_completed|state_error|state_cancelled|name             |title            |manual|bpmn_id         |lane     |lane_initiator|data                       |jsonschema                                                                                                                        |uischema                                                                                                                                                                         |error_stacktrace|
# ------------------------------------+-----------------------------+-----------------------------+------------------------------------+------------------------------------+-----------------+-----+-----------+---------------+-----------+---------------+-----------------+-----------------+------+----------------+---------+--------------+---------------------------+----------------------------------------------------------------------------------------------------------------------------------+---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+----------------+
# ...
# a70daf08-c752-4d5d-adcf-26d463cd920a|2024-04-25 16:56:05.394 +0200|2024-04-25 16:56:05.506 +0200|32bdd1b7-934b-4662-92f6-30d88f3043e1|20d2fb70-1107-4d47-9c58-b783c6cb754c|false            |   64|false      |true           |false      |false          |SimpleFormID     |A Simple Form    |true  |SimpleFormID    |Init Lane|true          |{"text1": "Value of text1"}|{"type": "object", "required": ["text1"], "properties": {"text1": {"type": "string", "title": "Text Label 1"}}, "definitions": {}}|{"text1": {"ui:path": ["text1"], "ui:description": "Field Description 1", "ui:enableMarkdownInDescription": true}, "ui:field": "layout", "ui:layout": {"Row_09eujo2": ["text1"]}}|                |
# bb9d493c-aac6-4116-bbfe-b5ebb96897d4|2024-04-25 16:56:05.402 +0200|                             |32bdd1b7-934b-4662-92f6-30d88f3043e1|                                    |false            |  128|false      |false          |true       |false          |Activity_06zk4v0 |EvaluateForm1    |false |Activity_06zk4v0|Init Lane|true          |{"text1": "Value of text1"}|                                                                                                                                  |                                                                                                                                                                                 |NoneType: None¶ |


# assert service_application.is_faulty(db_session, workflow.workflow_instance_id) # type: ignore
        
