from actidoo_wfe.wf.service_task_helper import ServiceTaskHelper


def service_set_wf_name(sth: ServiceTaskHelper):
    request_data = sth.task_data["IncomingRequest_Response"]
    title = request_data.get("request_title", "")
    reference = request_data.get("reference_number", "")
    sth.set_workflow_instance_subtitle(f"{title} - Ref #{reference}")


def service_assign_user(sth: ServiceTaskHelper):
    # see /site-packages/SpiffWorkflow/camunda/specs/event_definitions.py:
    # The data of an event is copied to f'{my_task.task_spec.name}_Response'
    reviewer_email = sth.task_data["IncomingRequest_Response"].get("reviewer_email", "")
    bpmn_task_id = "ReviewRequest"

    sth.assign_user_without_role(
        bpmn_task_id=bpmn_task_id,
        email=reviewer_email,
        create_user=True
    )


def service_msg_notapproved(sth: ServiceTaskHelper):
    # TODO: send message.....
    print("HALLO!!!!")


def service_generate_doc(sth: ServiceTaskHelper):
    print("WELT!!!!")


def service_msg_approved(sth: ServiceTaskHelper):
    # TODO: send message.....
    print("APPROVED!!!!")
