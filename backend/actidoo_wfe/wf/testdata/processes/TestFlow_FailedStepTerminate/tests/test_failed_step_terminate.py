# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 ActiDoo GmbH

from actidoo_wfe.database import SessionLocal
from actidoo_wfe.wf import repository, service_workflow
from actidoo_wfe.wf.tests.helpers.workflow_dummy import WorkflowDummy

WF_NAME = "TestFlow_FailedStepTerminate"


def test_a_terminate_end_event_completes_the_instance_despite_a_failed_step(db_engine_ctx):
    with db_engine_ctx():
        db_session = SessionLocal()
        workflow = WorkflowDummy(
            db_session=db_session,
            users_with_roles={"initiator": ["wf-user"]},
            workflow_name=WF_NAME,
            start_user="initiator",
        )

        engine_workflow = repository.load_workflow_instance(db=db_session, workflow_id=workflow.workflow_instance_id)
        assert [t.task_spec.bpmn_id for t in service_workflow.get_faulty_tasks(engine_workflow)] == ["FailingStep"]
        workflow.assert_completed()
