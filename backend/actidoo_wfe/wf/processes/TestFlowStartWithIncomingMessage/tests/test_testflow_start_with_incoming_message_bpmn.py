from actidoo_wfe.database import SessionLocal
from actidoo_wfe.wf.tests.helpers.workflow_dummy import WorkflowDummy

FILL_FORM_DATA = {
    "request_title": "Example Service Request",
    "reference_number": 5,
    "effort_hours": 10,
    "reviewer_email": "reviewer@example.com",
}

NOT_APPROVE_FORM_DATA = {
    "approve": "no"
}

APPROVE_FORM_DATA = {
    "approve": "yes"
}


def test_incoming_message_workflow_happy_path(db_engine_ctx):
    with db_engine_ctx():
        db = SessionLocal()

        workflow = WorkflowDummy(
            db_session=db,
            users_with_roles={
                "reviewer@example.com": ["wf-user"],
            },
            service_users_with_roles={
                "initiator": ["wf-api"],
            }
        )

        workflow.service_user("initiator").send_message(
            message_name="testflow_start_with_incoming_message_start",
            data=dict(FILL_FORM_DATA),
            correlation_key=""
        )
        workflow.auto_set_workflow_instance_id()

        workflow.user("reviewer@example.com").get_usertasks(workflow.workflow_instance_id, 1)
        workflow.user("reviewer@example.com").assign_submit(workflow.workflow_instance_id, NOT_APPROVE_FORM_DATA)
        workflow.user("reviewer@example.com").get_usertasks(workflow.workflow_instance_id, 0)

        subscriptions = workflow.get_message_subscriptions()
        assert len(subscriptions) == 1

        workflow.service_user("initiator").send_message(
            message_name="testflow_start_with_incoming_message_resubmit",
            data=dict(FILL_FORM_DATA),
            correlation_key=subscriptions[0].correlation_key
        )

        workflow.user("reviewer@example.com").get_usertasks(workflow.workflow_instance_id, 1)
        workflow.user("reviewer@example.com").assign_submit(workflow.workflow_instance_id, APPROVE_FORM_DATA)
        workflow.user("reviewer@example.com").get_usertasks(workflow.workflow_instance_id, 0)
