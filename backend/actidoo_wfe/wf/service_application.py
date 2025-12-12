"""
    This module implements the application services (services which must be used by the APIs).
"""

import hashlib
import logging
import uuid
from typing import Any, Literal

from sqlalchemy.orm import Session
from actidoo_wfe.helpers.bff_table import BffTableQuerySchemaBase
from actidoo_wfe.helpers.datauri import DataURI
from actidoo_wfe.helpers.modules import env_from_module
from actidoo_wfe.helpers.schema import PaginatedDataSchema
from actidoo_wfe.helpers.time import dt_now_naive
from actidoo_wfe.storage import get_file_content
from actidoo_wfe.wf import providers as workflow_providers
from actidoo_wfe.wf import repository, service_form, service_i18n, service_workflow, views
from actidoo_wfe.wf.exceptions import (
    AttachmentNotFoundException,
    InvalidWorkflowSpecException,
    TaskIsNotInReadyUsertasksException,
    UserMayNotAdministrateThisWorkflowException,
    UserMayNotCopyWorkflowException,
    UserMayNotStartWorkflowException,
    ValidationResultContainsErrors,
    WorkflowSpecNotFoundException,
)
from actidoo_wfe.wf.models import (
    WorkflowInstanceTaskAttachment,
    WorkflowMessage,
)
from actidoo_wfe.wf.repository import (
    store_attachment,
    store_attachment_for_task,
    store_attachment_for_workflow_instance,
)
from actidoo_wfe.wf.service_form import (
    get_attachments,
    iterate_and_replace_datauri,
    make_uischema_read_only,
)
from actidoo_wfe.wf.types import (
    Attachment,
    ReactJsonSchemaFormData,
    ReducedWorkflowInstanceResponse,
    UploadedAttachmentRepresentation,
    UserRepresentation,
    UserTaskRepresentation,
    UserTaskWithoutNestedAssignedUserRepresentation,
    WorkflowCopyInstruction,
    WorkflowInstanceRepresentation,
    WorkflowPreviewRepresentation,
    WorkflowRepresentation,
    WorkflowSpecRepresentation,
    WorkflowStatisticsRepresentation,
    WorkflowStateResponse
)

log = logging.getLogger(__name__)


def start_workflow(db: Session, name: str, user_id: uuid.UUID, initial_task_data: dict | None = None) -> uuid.UUID:
    """Starts a workflow with the given name, and the given user as creator. Returns the workflow ID."""
    user_rep = repository.load_user(db=db, user_id=user_id)
    repository.persist_workflow_spec(db=db, name=name)
    
    if not service_workflow.can_load_workflow(name=name):
        raise InvalidWorkflowSpecException()

    if not service_workflow.user_may_start_workflow(name=name, user=user_rep):
        raise UserMayNotStartWorkflowException()
    
    workflow = service_workflow.start_process(name=name, created_by=user_rep)
    service_workflow.run_workflow(workflow=workflow)

    copied_task_attachments: list[tuple[uuid.UUID, list[UploadedAttachmentRepresentation]]] = []

    if initial_task_data is not None:
        ready_tasks_in_new_workflow = service_workflow.get_usertasks_for_user(
            workflow=workflow, user=user_rep, state="ready"
        )

        if not ready_tasks_in_new_workflow:
            log.warning("No ready user tasks available to apply initial data for workflow %s", name)
        else:
            first_task = ready_tasks_in_new_workflow[0]
            cleaned_task_data = _clean_submitted_task_data(
                workflow=workflow,
                task=first_task,
                submitted_data=initial_task_data,
            )
            service_workflow.update_task_data(
                workflow=workflow,
                task_id=first_task.id,
                cleaned_task_data=cleaned_task_data,
            )
            attachments = get_attachments(cleaned_task_data)
            if attachments:
                copied_task_attachments.append((first_task.id, attachments))

    repository.store_workflow_instance(db=db, workflow=workflow, triggered_by=user_id)
    _persist_copied_attachments(
        db=db,
        workflow_instance_id=workflow.task_tree.id,
        task_attachments=copied_task_attachments,
    )

    return workflow.task_tree.id


def get_workflow_preview(
    db: Session,
    name: str,
    user_id: uuid.UUID,
    task_data: dict | None = None,
) -> WorkflowPreviewRepresentation:
    user_rep = repository.load_user(db=db, user_id=user_id)
    repository.persist_workflow_spec(db=db, name=name)

    if not service_workflow.can_load_workflow(name=name):
        raise InvalidWorkflowSpecException()

    if not service_workflow.user_may_start_workflow(name=name, user=user_rep):
        raise UserMayNotStartWorkflowException()

    workflow = service_workflow.start_process(name=name, created_by=user_rep)
    service_workflow.run_workflow(workflow=workflow)

    subtitle = service_workflow.get_subtitle(workflow=workflow)

    workflow_rep = WorkflowPreviewRepresentation(
        name=workflow.spec.name,
        title=service_workflow.get_workflow_title_cached(workflow.spec.name),
        subtitle=subtitle, 
        task=None
    )

    usertasks = service_workflow.get_usertasks_for_user(
        workflow=workflow,
        user=user_rep,
        state="ready",
    )
    if not usertasks:
        return workflow_rep

    first_task = usertasks[0]

    if task_data is not None:
        cleaned_task_data = _clean_submitted_task_data(
            workflow=workflow,
            task=first_task,
            submitted_data=task_data,
        )
        service_workflow.update_task_data(
            workflow=workflow,
            task_id=first_task.id,
            cleaned_task_data=cleaned_task_data,
        )
        first_task.data = cleaned_task_data

    enriched_task = _enrich_UserTaskRepresentationWithNestedAssignedUser(
        db=db,
        usertask=first_task,
    )
    enriched_task = _translate_UserTaskRepresentationForms(
        db=db,
        workflow_name=workflow.spec.name,
        usertask=enriched_task,
        locale=user_rep.locale,
    )

    if enriched_task.uischema and enriched_task.jsonschema:
        (
            enriched_task.uischema,
            enriched_task.jsonschema,
        ) = make_uischema_read_only(
            enriched_task.uischema,
            jsonschema=enriched_task.jsonschema,
            workflow=workflow,
            task_id=first_task.id,
            form_data=enriched_task.data if isinstance(enriched_task.data, dict) else None,
        )

    workflow_rep.task = enriched_task

    return workflow_rep


def get_workflow_copy_data(
    db: Session,
    user_id: uuid.UUID,
    workflow_instance_id: uuid.UUID,
) -> WorkflowCopyInstruction:
    original_instance = repository.load_workflow_instance(
        db=db,
        workflow_id=workflow_instance_id,
    )
    original_created_by = service_workflow.get_created_by_id(original_instance)

    if original_created_by != user_id:
        raise UserMayNotCopyWorkflowException()

    user_rep = repository.load_user(db=db, user_id=user_id)

    workflow_name = original_instance.spec.name

    if not service_workflow.can_load_workflow(name=workflow_name):
        raise InvalidWorkflowSpecException()

    if not service_workflow.user_may_start_workflow(name=workflow_name, user=user_rep):
        raise UserMayNotStartWorkflowException()

    repository.persist_workflow_spec(db=db, name=workflow_name)

    workflow_preview = service_workflow.start_process(
        name=workflow_name,
        created_by=user_rep,
    )
    service_workflow.run_workflow(workflow=workflow_preview)

    ready_tasks_in_new_workflow = service_workflow.get_usertasks_for_user(
        workflow=workflow_preview,
        user=user_rep,
        state="ready",
    )
    tasks_in_original_workflow = service_workflow.get_usertasks_for_user(
        workflow=original_instance,
        user=user_rep,
        state="completed",
    )

    cleaned_data_for_first_task: dict | None = None
    first_task_name = ""

    for idx, t_new in enumerate(ready_tasks_in_new_workflow):
        matching_original_task = next(
            (t_original for t_original in tasks_in_original_workflow if t_original.name == t_new.name),
            None,
        )

        if matching_original_task is None or matching_original_task.assigned_user_id != user_id:
            raise UserMayNotCopyWorkflowException()

        cleaned_task_data = _clean_submitted_task_data(
            workflow=workflow_preview,
            task=t_new,
            submitted_data=matching_original_task.data,
        )

        if idx == 0:
            cleaned_data_for_first_task = cleaned_task_data
            first_task_name = t_new.name

    if cleaned_data_for_first_task is None:
        cleaned_data_for_first_task = {}
        if ready_tasks_in_new_workflow:
            first_task_name = ready_tasks_in_new_workflow[0].name

    return WorkflowCopyInstruction(
        workflow_name=workflow_name,
        task_name=first_task_name,
        data=cleaned_data_for_first_task,
    )


def start_workflow_with_message(db: Session, name: str, message: WorkflowMessage) -> uuid.UUID:
    """Starts a workflow with the given name, and the given user as creator. Returns the workflow ID."""
    user_rep = repository.load_user(db=db, user_id=message.sent_by_user_id)
    repository.persist_workflow_spec(db=db, name=name)

    if not service_workflow.user_may_start_workflow(name=name, user=user_rep):
        raise UserMayNotStartWorkflowException()

    workflow = service_workflow.start_process(name=name, created_by=user_rep)
    service_workflow.run_workflow(workflow=workflow)
    repository.store_workflow_instance(db=db, workflow=workflow, triggered_by=user_rep.id)

    service_workflow.send_event(
        workflow=workflow,
        name=message.name,
        payload=message.data
    )

    service_workflow.run_workflow(workflow=workflow)
    repository.store_workflow_instance(db=db, workflow=workflow, triggered_by=user_rep.id)

    return workflow.task_tree.id


def receive_message(db: Session, message_name: str, correlation_key: str, data: dict, user_id: uuid.UUID|None):
    repository.store_message(
        db=db,
        message_name=message_name,
        correlation_key=correlation_key,
        data=data,
        sent_by_user_id=user_id,
        sent_by_workflow_instance_id=None
    )
    


def handle_messages(db: Session):
    messages = repository.load_unprocessed_messages(db=db)
    for message in messages:
        wf_instance_ids = []

        sent_by_user = repository.load_user(db=db, user_id=message.sent_by_user_id)

        # Handle Starts
        workflow_names = service_workflow.get_workflows_to_trigger_by_start_message(
            message_name = message.name, user=sent_by_user
        )
        for workflow in workflow_names:
            wf_id = start_workflow_with_message(db=db, name=workflow, message=message)
            wf_instance_ids.append(wf_id)

        # Handle Correlations
        subscriptions = repository.get_subscriptions_by_message_name_and_correlation_key(
            db=db,
            message_name = message.name,
            correlation_key = message.correlation_key
        )
        for sub in subscriptions:
            workflow = repository.load_workflow_instance_by_task_id(db=db, task_id=sub.workflow_instance_task_id)
            service_workflow.send_event(
                workflow=workflow,
                name=message.name,
                payload=message.data,
            )
            service_workflow.run_workflow(workflow=workflow)
            repository.store_workflow_instance(db=db, workflow=workflow, triggered_by=message.sent_by_user_id)

            wf_instance_ids.append(workflow.task_tree.id)

        repository.store_message_processed(db=db, message_id=message.id, processed_by_workflow_instance_ids=wf_instance_ids)


def handle_timeevents(db: Session, *, batch_size: int = 200):
    now = dt_now_naive()

    while True:
        due = repository.list_due_time_events(db=db, now=now, limit=batch_size)
        if not due:
            break

        for wte in due:
            try:
                # Load aggregate
                wf = repository.load_workflow_instance(db=db, workflow_id=wte.workflow_instance_id)

                # Domain call
                result: service_workflow.TimeEventResult = service_workflow.process_single_time_event(workflow=wf, wte_record=wte)

                # Persist domain state
                repository.store_workflow_instance(db=db, workflow=wf)

                # Persist timer record according to outcome
                if result.outcome == "completed":
                    repository.mark_timer_completed(db, wte)
                elif result.outcome == "reschedule":
                    repository.reschedule_cycle(
                        db,
                        wte,
                        next_due=result.next_due,
                        remaining_cycles=(result.remaining_cycles if result.remaining_cycles is not None else -1),
                    )
                elif result.outcome == "cancelled":
                    repository.cancel_timer_for_task(db, wte)
                elif result.outcome == "noop":
                    # Do not change the timer status; it will be re-planned by store_workflow if needed.
                    pass
                else:
                    # Defensive default
                    repository.mark_timer_completed(db, wte)

            except Exception as ex:
                repository.fail_and_release(db, wte, err=str(ex))


def bff_user_get_initiated_workflows(
    db: Session, bff_table_request_params: BffTableQuerySchemaBase, user_id: uuid.UUID
):
    user = get_user(db=db, user_id=user_id)
    instances: PaginatedDataSchema[WorkflowInstanceRepresentation] = views.bff_user_get_initiated_workflows(db=db, bff_table_request_params=bff_table_request_params, user_id=user_id)

    for instance in instances.ITEMS:
        instance.title = service_i18n.translate_string(msgid=instance.title, workflow_name=instance.name, locale=user.locale)
        for task in instance.active_tasks:
            task.title = service_i18n.translate_string(msgid=task.title, workflow_name=instance.name, locale=user.locale)

    return instances


def bff_get_workflows_with_usertasks(
    db: Session,
    bff_table_request_params: BffTableQuerySchemaBase,
    user_id: uuid.UUID,
    state: Literal["ready", "completed"],
):
    user = get_user(db=db, user_id=user_id)
    instances: PaginatedDataSchema[WorkflowInstanceRepresentation] = views.bff_get_workflows_with_usertasks(db=db, bff_table_request_params=bff_table_request_params, user_id=user_id, state=state)

    for instance in instances.ITEMS:
        instance.title = service_i18n.translate_string(msgid=instance.title, workflow_name=instance.name, locale=user.locale)
        for task in instance.active_tasks:
            task.title = service_i18n.translate_string(msgid=task.title, workflow_name=instance.name, locale=user.locale)

    return instances

def _enrich_UserTaskRepresentationWithNestedAssignedUser(db: Session, usertask: UserTaskWithoutNestedAssignedUserRepresentation)->UserTaskRepresentation:
    if usertask.assigned_user_id:
        user = get_user(db=db, user_id=usertask.assigned_user_id)
        new_usertask = UserTaskRepresentation(**usertask.model_dump(), assigned_user=user)
    else:
        new_usertask = UserTaskRepresentation(**usertask.model_dump(), assigned_user=None)

    return new_usertask

def _translate_UserTaskRepresentationForms(db: Session, workflow_name: str, usertask: UserTaskRepresentation, locale) -> UserTaskRepresentation:
    if usertask.jsonschema and usertask.uischema:
        translated = service_i18n.translate_form_data(form_data=ReactJsonSchemaFormData(
            jsonschema=usertask.jsonschema, uischema=usertask.uischema
        ), workflow_name=workflow_name, locale=locale)
        usertask.jsonschema = translated.jsonschema
        usertask.uischema = translated.uischema
        if usertask.lane:
            usertask.lane = service_i18n.translate_string(msgid=usertask.lane, workflow_name=workflow_name, locale=locale)
        usertask.title = service_i18n.translate_string(msgid=usertask.title, workflow_name=workflow_name, locale=locale)
    return usertask


def get_usertasks_for_user_id(
    db: Session,
    user_id: uuid.UUID,
    workflow_instance_id: uuid.UUID,
    state: Literal["ready", "completed"],
) -> list[UserTaskRepresentation]:
    user = repository.load_user(db=db, user_id=user_id)
    workflow = repository.load_workflow_instance(db=db, workflow_id=workflow_instance_id)
    usertasks = service_workflow.get_usertasks_for_user(
        workflow=workflow, user=user, state=state
    )
    usertasks = [_enrich_UserTaskRepresentationWithNestedAssignedUser(db=db, usertask=ut) for ut in usertasks]
    usertasks = [_translate_UserTaskRepresentationForms(db=db, workflow_name=workflow.spec.name, usertask=ut, locale=user.locale) for ut in usertasks]

    return usertasks


def _clean_submitted_task_data(workflow, task, submitted_data):
    """Validate and clean a payload from a user form submission.

    The payload typically only contains the fields the frontend knows about.
    Unknown / technical properties are removed deliberately and hidden fields
    are stripped."""

    assert task.uischema and task.jsonschema
    form = ReactJsonSchemaFormData(jsonschema=task.jsonschema, uischema=task.uischema)
    options_folder = workflow_providers.get_workflow_directory(workflow.spec.name) / "options"

    module_path = workflow_providers.get_workflow_module_path(workflow.spec.name)
    if module_path:
        try:
            functions_env = env_from_module(module_path)
        except ImportError:
            functions_env = {}
    else:
        functions_env = {}

    validation_result = service_form.validate_task_data(
        form=form,
        task_data=submitted_data,
        options_folder=options_folder,
        functions_env=functions_env,
        preserve_unknown_fields=False,
        preserve_disabled_fields=False,
    )

    if validation_result.error_schema:
        log.error("Errors during validation of submitted task data" + str(validation_result.error_schema))
        raise ValidationResultContainsErrors(message="Errors during validation of submitted task data", error_schema=validation_result.error_schema)

    return validation_result.task_data


# def _clean_full_task_data(workflow, task, task_data):
#     """Validate and clean an existing task payload (e.g. when copying).

#     In this mode we keep technical fields that are not represented in the
#     schema, but we still apply the hide-if cleanup so the new task only exposes
#     allowed user-facing data."""

#     assert task.uischema and task.jsonschema
#     form = ReactJsonSchemaFormData(jsonschema=task.jsonschema, uischema=task.uischema)
#     options_folder = workflow_providers.get_workflow_directory(workflow.spec.name) / "options"

#     module_path = workflow_providers.get_workflow_module_path(workflow.spec.name)
#     functions_env = env_from_module(module_path) if module_path else {}

#     validation_result = service_form.validate_task_data(
#         form=form,
#         task_data=task_data,
#         options_folder=options_folder,
#         functions_env=functions_env,
#         preserve_unknown_fields=True,
#         preserve_disabled_fields=True,
#     )

#     if validation_result.error_schema:
#         log.error("Errors during validation of submitted task data" + str(validation_result.error_schema))
#         raise ValidationResultContainsErrors(message="Errors during validation of submitted task data", error_schema=validation_result.error_schema)

#     return validation_result.task_data


def _persist_copied_attachments(
    db: Session,
    workflow_instance_id: uuid.UUID,
    task_attachments: list[tuple[uuid.UUID, list[UploadedAttachmentRepresentation]]],
) -> None:
    if not task_attachments:
        return

    seen_workflow_attachment_ids: set[uuid.UUID] = set()

    for task_id, attachments in task_attachments:
        for attachment in attachments:
            attachment_obj = repository.find_attachment_by_id(
                db=db, attachment_id=attachment.id
            )
            if attachment_obj is None:
                raise AttachmentNotFoundException()

            if attachment_obj.id not in seen_workflow_attachment_ids:
                store_attachment_for_workflow_instance(
                    db=db,
                    workflow_instance_id=workflow_instance_id,
                    attachment_id=attachment_obj.id,
                    filename=attachment.filename,
                )
                seen_workflow_attachment_ids.add(attachment_obj.id)

            store_attachment_for_task(
                db=db,
                task_id=task_id,
                attachment_id=attachment_obj.id,
                filename=attachment.filename,
            )

def submit_task_data(db: Session, user_id: uuid.UUID, task_id: uuid.UUID, task_data: dict):
    workflow = repository.load_workflow_instance_by_task_id(db=db, task_id=task_id)
    user = repository.load_user(db=db, user_id=user_id)

    # prohibit misuse of the API, by checking that the task_id is really a ready task of the user who submitted data for it:
    usertasks: list[UserTaskWithoutNestedAssignedUserRepresentation] = service_workflow.get_usertasks_for_user(
        workflow=workflow,
        user=user,
        state="ready",
    )
    if task_id not in [t.id for t in usertasks]:
        raise TaskIsNotInReadyUsertasksException()

    #process attachments START
    def process_uploads(datauri):
        obj = _upload_attachment(db=db, task_id=task_id, datauri=datauri) # datauri = e.g. 'data:image/png;name=example1.png;base64,B64_ENCODED_CONTENTS'
        return obj.model_dump() # model_dump creates a dict from the obj (which is a 'UplaodedAttachmentRepresentation)

    # We will process all uploads, also those that should not be accepted according to the json schema
    # Validating the JSON schema including the datauri fields would be just too slow...
    task_data: Any = iterate_and_replace_datauri(task_data, process_uploads)  # type: ignore

    task = next(t for t in usertasks if t.id == task_id)
    assert task.uischema and task.jsonschema
    # Now the JSON is much smaller. We validate the new JSON which just contains the references to the uploaded files.
    # Afterwards, only allowed uploads will be referenced in the json
    cleaned_task_data = _clean_submitted_task_data(
        workflow=workflow,
        task=task,
        submitted_data=task_data,
    )  # may raise ValidationResultContainsErrors

    # Now, we are going to extract all attachments, and cleanup the remaining
    # If illegal attachments had been attached before, they will be cleaned up here.
    attachements = get_attachments(cleaned_task_data)
    _delete_unused_attachments(db, workflow.task_tree.id, task.id, attachements)
    # process attachments END

    result = service_workflow.execute_user_task(workflow, user, task_id, cleaned_task_data)
    repository.store_workflow_instance(db, workflow, user.id)
    return result, workflow.task_tree.id


def get_allowed_workflows_to_start(db: Session, user_id: uuid.UUID):
    user = repository.load_user(db=db, user_id=user_id)

    workflows = [
        WorkflowRepresentation(
            name=name, title=service_workflow.get_workflow_title_cached(name)
        )
        for name in service_workflow.get_allowed_workflow_names_to_start(user=user)
    ]
    
    workflows.sort(key=lambda x: x.title) # sort by title
    return workflows


def assign_task_to_me(db: Session, user_id: uuid.UUID, task_id: uuid.UUID):
    workflow = repository.load_workflow_instance_by_task_id(db=db, task_id=task_id)
    user = repository.load_user(db=db, user_id=user_id)
    service_workflow.assign_task(workflow=workflow, task_id=task_id, user=user)
    service_workflow.set_allow_unassign(workflow=workflow, task_id=task_id)
    repository.store_workflow_instance(db=db, workflow=workflow, triggered_by=user_id)


def unassign_task_from_me(db: Session, user_id: uuid.UUID, task_id: uuid.UUID):
    workflow = repository.load_workflow_instance_by_task_id(db=db, task_id=task_id)
    assigned_user_id = service_workflow.get_assigned_user(
        workflow=workflow, task_id=task_id
    )
    can_unassign = service_workflow.can_be_unassigned(
        workflow=workflow, task_id=task_id
    )
    if can_unassign and assigned_user_id == user_id:
        service_workflow.unassign_task(workflow=workflow, task_id=task_id)
    repository.store_workflow_instance(db=db, workflow=workflow, triggered_by=user_id)


def search_property_options(
    db: Session,
    user_id: uuid.UUID,
    task_id: uuid.UUID,
    property_path: list[str],
    search: str,
    include_value: str | list[str] | None,
    form_data: dict|None
) -> list[tuple[str, str]]:
    workflow = repository.load_workflow_instance_by_task_id(db=db, task_id=task_id)
    user = repository.load_user(db=db, user_id=user_id)

    usertasks: list[UserTaskWithoutNestedAssignedUserRepresentation] = service_workflow.get_usertasks_for_user(
        workflow=workflow, user=user, state=["ready", "completed"]
    )
    if task_id not in [t.id for t in usertasks]:
        raise TaskIsNotInReadyUsertasksException()

    options = service_workflow.get_options_for_property(
        workflow=workflow, task_id=task_id, property_path=property_path, form_data=form_data
    )

    options_by_value = []

    # add the current selected element(s)
    if include_value and isinstance(include_value, list):
        for val in include_value:
            for o in options:
                if o[0] == val:
                    options_by_value.append(o)
                    
    elif include_value:
        for o in options:
            if o[0] == include_value:
                options_by_value.append(o)

    options.sort(key=lambda x: x[1]) # sort according to the label
    if (('new', '- New -')) in options:
        index_to_move = options.index(('new', '- New -'))
        element = options.pop(index_to_move)
        options.insert(0, element)

    for word in search.split():
        options = [
            x
            for x in options
            if word.lower() in x[1].lower() or word.lower() in x[0].lower()
        ]

    options_limit = 15
    try:
        task = workflow.get_task_from_id(task_id)
        formdata = service_workflow.get_react_json_schema_form_data(task=task)
        options_limit = service_form.get_options_limit(
            jsonschema=formdata.jsonschema, path=property_path, default_limit=15
        )
    except Exception:
        options_limit = 15

    if options_limit is not None:
        options = options[:options_limit]
    
    for val in options_by_value:
        if val[0] not in {o[0] for o in options}:
            options.append(val)

    return options


def _upload_attachment(
    db: Session, task_id: uuid.UUID, datauri: str
) -> UploadedAttachmentRepresentation:
    workflow = repository.load_workflow_instance_by_task_id(db=db, task_id=task_id)

    datauri = DataURI(datauri)

    data = datauri.data
    mimetype = datauri.mimetype
    filename = datauri.name

    assert filename is not None

    hasher = hashlib.sha256()
    hasher.update(data)
    hash = hasher.hexdigest()

    attachment = store_attachment(
        db=db, filename=filename, mimetype=mimetype, data=data, hash=hash
    )
    store_attachment_for_workflow_instance(
        db=db,
        workflow_instance_id=workflow.task_tree.id,
        attachment_id=attachment.id,
        filename=filename,
    )
    store_attachment_for_task(
        db=db, task_id=task_id, attachment_id=attachment.id, filename=filename
    )

    return UploadedAttachmentRepresentation(
        hash=hash, filename=filename, id=attachment.id, mimetype=mimetype
    )


def _delete_unused_attachments(
    db: Session,
    workflow_instance_id: uuid.UUID,
    task_id: uuid.UUID,
    attachments: list[UploadedAttachmentRepresentation],
):
    delete_ids = []

    current_task_attachments_by_task = repository.find_task_attachments_by_task_id(
        db=db, task_id=task_id
    )

    for ca in current_task_attachments_by_task:
        if not any([ga.hash == ca.attachment.hash for ga in attachments]):
            delete_ids.append(ca.attachment.id)
            db.delete(ca)

    current_task_attachments_by_workflow = (
        repository.find_task_attachments_by_worfklow_instance_id(
            db=db, workflow_instance_id=workflow_instance_id
        )
    )

    current_workflow_attachments = (
        repository.find_workflow_instance_attachments_by_worfklow_instance_id(
            db=db, workflow_instance_id=workflow_instance_id
        )
    )

    for ca in current_workflow_attachments:
        if not any([ga.hash == ca.attachment.hash for ga in attachments]):
            if not any(
                [
                    ga.attachment.hash == ca.attachment.hash
                    for ga in current_task_attachments_by_workflow
                ]
            ):
                delete_ids.append(ca.attachment.id)
                db.delete(ca)

    db.flush()

    delete_ids = list(set(delete_ids)) # remove duplicate entries
    for deleteid in delete_ids:
        repository.delete_dangling_attachment(db=db, attachment_id=deleteid)

    db.flush()


def find_attachment_by_hash(db: Session, workflow_instance_id: uuid.UUID, hash: str):
    attachments = repository.find_task_attachments_by_worfklow_instance_id(
        db=db, workflow_instance_id=workflow_instance_id
    )
    att: WorkflowInstanceTaskAttachment | None = next(
        (a for a in attachments if a.attachment.hash == hash), None
    )
    if att is None:
        raise AttachmentNotFoundException()
    return Attachment(
        id=att.id,
        hash=att.attachment.hash,
        filename=att.attachment.first_filename,
        mimetype=att.attachment.mimetype,
        data=get_file_content(att.attachment.file.file_id) if att.attachment.file else att.attachment.data,
    )


def find_all_workflow_attachments(db: Session, workflow_instance_id: uuid.UUID):
    attachments = repository.find_task_attachments_by_worfklow_instance_id(
        db=db, workflow_instance_id=workflow_instance_id
    )
    return [
        Attachment(
            id=att.id,
            hash=att.attachment.hash,
            filename=att.attachment.first_filename,
            mimetype=att.attachment.mimetype,
            data=get_file_content(att.attachment.file.file_id) if att.attachment.file else att.attachment.data,
        )
        for att in attachments
    ]


def verify_assigned_user_and_download_attachment(
    db: Session, user_id: uuid.UUID, task_id: uuid.UUID, hash: str
) -> Attachment:
    workflow = repository.load_workflow_instance_by_task_id(db=db, task_id=task_id)
    assert (
        service_workflow.is_assigned_to_task(
            workflow=workflow, task_id=task_id, user_id=user_id
        )
    )

    return download_attachment(db=db, task_id=task_id, hash=hash)


def download_attachment(
    db: Session, task_id: uuid.UUID, hash: str
) -> Attachment:
    workflow = repository.load_workflow_instance_by_task_id(db=db, task_id=task_id)

    attachments = repository.find_task_attachments_by_worfklow_instance_id(
        db=db, workflow_instance_id=workflow.task_tree.id
    )
    att: WorkflowInstanceTaskAttachment | None = next(
        (a for a in attachments if a.attachment.hash == hash), None
    )
    if att is None:
        raise AttachmentNotFoundException()

    return Attachment(
        id=att.id,
        hash=att.attachment.hash,
        filename=att.attachment.first_filename,
        mimetype=att.attachment.mimetype,
        data=get_file_content(att.attachment.file.file_id) if att.attachment.file else att.attachment.data,
    )


def get_user_by_email(db: Session, email: str):
    return repository.load_user_by_email(db=db, email=email)


def get_user(db: Session, user_id: uuid.UUID) -> UserRepresentation:
    return repository.load_user(db=db, user_id=user_id)


def list_users(db: Session, user_id: uuid.UUID) -> UserRepresentation:
    return repository.load_user(db=db, user_id=user_id)


def refresh_get_workflow_spec(db: Session, name: str, version: int|None, file_type: str) -> WorkflowSpecRepresentation:
    repository.persist_workflow_spec(db=db, name=name)
    spec = views.get_workflow_spec(db=db, name=name, version=version)
    if spec is None:
        raise WorkflowSpecNotFoundException()

    return WorkflowSpecRepresentation.model_validate(
        dict(spec.__dict__, files=[x for x in spec.files if x.file_type == file_type])
    )

def is_completed(
    db: Session,
    workflow_instance_id: uuid.UUID,
) -> bool:
    workflow = repository.load_workflow_instance(db=db, workflow_id=workflow_instance_id)
    unfinished_tasks = service_workflow.get_unfinished_tasks(workflow)
    return len(unfinished_tasks) == 0

def is_faulty(
    db: Session,
    workflow_instance_id: uuid.UUID,
) -> bool:
    workflow = repository.load_workflow_instance(db=db, workflow_id=workflow_instance_id)
    faulty_tasks = service_workflow.get_faulty_tasks(workflow)
    return len(faulty_tasks) > 0


def user_cancel_workflow(db: Session, user_id: uuid.UUID, task_id: uuid.UUID):
    workflow = repository.load_workflow_instance_by_task_id(db=db, task_id=task_id)
    can_cancel = service_workflow.can_user_cancel_workflow(
        workflow=workflow, task_id=task_id, user_id=user_id
    )
    if can_cancel:
        service_workflow.cancel_workflow(workflow=workflow)
        repository.store_workflow_instance(db=db, workflow=workflow, triggered_by=user_id)


def user_delete_workflow(db: Session, user_id: uuid.UUID, task_id: uuid.UUID):
    workflow = repository.load_workflow_instance_by_task_id(db=db, task_id=task_id)
    can_delete = service_workflow.can_user_delete_workflow(
        workflow=workflow, task_id=task_id, user_id=user_id
    )
    if can_delete:
        repository.delete_workflow_instance(db=db, workflow=workflow)

#### Statistics ####


def get_workflow_statistics(db: Session, user_id: uuid.UUID):
    workflows = [
        WorkflowStatisticsRepresentation(
            name=wf_name,
            title=service_workflow.get_workflow_title_cached(wf_name),
            estimated_saved_mins_per_instance=service_workflow.get_workflow_saved_minutes_per_instance_cached(wf_name)
        )
        for wf_name in service_workflow.get_all_activated_workflow_names()
    ]

    for wfstats in workflows:
        stats = views.get_workflow_statistics(db=db, workflow_name=wfstats.name)
        wfstats.active_instances = stats["active_instances"]
        wfstats.completed_instances = stats["completed_instances"]
        wfstats.estimated_instances_per_year = stats["estimated_instances_per_year"]
        wfstats.estimated_savings_per_year =  (wfstats.estimated_instances_per_year * wfstats.estimated_saved_mins_per_instance) / 60.0
    
    workflows.sort(key=lambda x: x.title) # sort by title
    
    return workflows


#### Admin ####

def is_global_admin(db: Session, user_id):
    user = get_user(db=db, user_id=user_id)
    return "wf-admin" in user.roles


def get_workflow_names_the_user_is_admin_for(db: Session, user_id):
    """
    Retrieves the names of workflows for which the specified user has administrative rights.

    This function checks if the user is a global administrator. If so, it returns all
    workflow names.
    If not, it only returns workflows for which the user belongs to a wf-owner role.

    Args:
        db (Session): The database session.
        user_id (uuid.UUID): The identifier of the user for whom to retrieve admin workflow names.

    Returns:
        set: A set containing the names of workflows the user can administrate.
    """
    wfnames = set()
    if is_global_admin(db=db, user_id=user_id):
        workflow_names_from_files = set(service_workflow.get_all_activated_workflow_names())
        workflow_names_from_db = set(views.get_distinct_workflow_names_from_db(db=db))
        wfnames = workflow_names_from_files | workflow_names_from_db
    else:
        role_to_workflow_names_map = service_workflow.get_wf_owner_role_to_workflow_mapping()
        user = get_user(db=db, user_id=user_id)
        wfnames = {wfname for role in user.roles for wfname in role_to_workflow_names_map.get(role, [])}

    return wfnames


def require_workflow_admin_by_task_id(db, user_id, task_id):
    is_global_workflow_admin  = is_global_admin(db=db, user_id=user_id)
    if not is_global_workflow_admin:
        allowed_workflow_names = get_workflow_names_the_user_is_admin_for(db=db, user_id=user_id)
        task = views.get_single_task(db=db, task_id=task_id)
        if task.workflow_instance.name not in allowed_workflow_names:
            raise UserMayNotAdministrateThisWorkflowException(f"User is not admin for workflow {task.workflow_instance.name}")
        
def require_workflow_admin_by_instance_id(db, user_id, instance_id):
    is_global_workflow_admin  = is_global_admin(db=db, user_id=user_id)
    if not is_global_workflow_admin:
        allowed_workflow_names = get_workflow_names_the_user_is_admin_for(db=db, user_id=user_id)
        instance = views.get_workflow_by_instance_id(db=db, workflow_instance_id=instance_id)
        if instance.name not in allowed_workflow_names:
            raise UserMayNotAdministrateThisWorkflowException(f"User is not admin for workflow {instance.name}")

def bff_admin_get_all_tasks(db: Session, user_id: uuid.UUID, bff_table_request_params: BffTableQuerySchemaBase):
    allowed_workflow_names = get_workflow_names_the_user_is_admin_for(db=db, user_id=user_id)
    return views.bff_admin_get_all_tasks(
        db=db, bff_table_request_params=bff_table_request_params, allowed_workflow_names = allowed_workflow_names
    )

def bff_admin_get_all_workflow_instances(db: Session, user_id: uuid.UUID, bff_table_request_params: BffTableQuerySchemaBase):
    allowed_workflow_names = get_workflow_names_the_user_is_admin_for(db=db, user_id=user_id)
    return views.bff_admin_get_all_workflow_instances(
        db=db, bff_table_request_params=bff_table_request_params, allowed_workflow_names = allowed_workflow_names
    )

def admin_get_single_task(db: Session, user_id: uuid.UUID, task_id: uuid.UUID):
    require_workflow_admin_by_task_id(db=db, user_id=user_id, task_id=task_id)
    return views.admin_get_single_task(db=db, task_id=task_id)

def admin_replace_task_data(db: Session, user_id: uuid.UUID, task_id: uuid.UUID, task_data: dict):

    require_workflow_admin_by_task_id(db=db, user_id=user_id, task_id=task_id)

    workflow = repository.load_workflow_instance_by_task_id(db=db, task_id=task_id)

    service_workflow.replace_task_data(
        workflow=workflow, task_id=task_id, task_data=task_data
    )

    repository.store_workflow_instance(db=db, workflow=workflow)


def admin_execute_erroneous_task(db: Session, user_id: uuid.UUID, task_id: uuid.UUID):
    require_workflow_admin_by_task_id(db=db, user_id=user_id, task_id=task_id)

    workflow = repository.load_workflow_instance_by_task_id(db=db, task_id=task_id)
    service_workflow.execute_erroneous_task(workflow=workflow, task_id=task_id)
    repository.store_workflow_instance(db=db, workflow=workflow)
    return workflow.task_tree.id


def admin_cancel_workflow(db: Session, user_id:uuid.UUID, workflow_instance_id: uuid.UUID):
    
    require_workflow_admin_by_instance_id(db=db, user_id=user_id, instance_id=workflow_instance_id)

    workflow = repository.load_workflow_instance(db=db, workflow_id=workflow_instance_id)
    service_workflow.cancel_workflow(workflow=workflow)
    repository.store_workflow_instance(db=db, workflow=workflow)


def admin_assign_task_to_user_without_checks(
    db: Session, task_id: uuid.UUID, admin_user_id: uuid.UUID, assign_to_user_id: uuid.UUID, remove_roles: bool
):
    
    require_workflow_admin_by_task_id(db=db, user_id=admin_user_id, task_id=task_id)

    workflow = repository.load_workflow_instance_by_task_id(db=db, task_id=task_id)
    user = repository.load_user(db=db, user_id=assign_to_user_id)
    if remove_roles:
        service_workflow.set_manually_assigned_roles(
            workflow=workflow, task_id=task_id, roles=set()
        )
    service_workflow.assign_task_without_checks(
        workflow=workflow, task_id=task_id, user_id=user.id
    )
    repository.store_workflow_instance(db=db, workflow=workflow)

def admin_unassign_task_without_checks(db: Session, admin_user_id: uuid.UUID, task_id: uuid.UUID):
    require_workflow_admin_by_task_id(db=db, user_id=admin_user_id, task_id=task_id)

    workflow = repository.load_workflow_instance_by_task_id(db=db, task_id=task_id)
    service_workflow.unassign_task_without_checks(workflow=workflow, task_id=task_id)
    repository.store_workflow_instance(db=db, workflow=workflow)

def admin_get_task_states_per_workflow(db: Session, wf_name: str, admin_user_id: uuid.UUID) -> WorkflowStateResponse:
    allowed_workflow_names = get_workflow_names_the_user_is_admin_for(db=db, user_id=admin_user_id)
    return views.admin_get_task_states_per_workflow(db=db, wf_name=wf_name, allowed_workflow_names=allowed_workflow_names)


def admin_get_statistics_graph_timestamps(db: Session) -> ReducedWorkflowInstanceResponse:
    return views.bff_admin_get_graph_workflow_instances(db=db)
