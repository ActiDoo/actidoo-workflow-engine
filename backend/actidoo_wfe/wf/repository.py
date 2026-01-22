# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

import datetime
import hashlib
import pathlib
import re
import uuid
from typing import Literal, Union

from SpiffWorkflow.bpmn.specs.bpmn_task_spec import BpmnTaskSpec
from SpiffWorkflow.bpmn.specs.event_definitions.timer import TimerEventDefinition
from SpiffWorkflow.bpmn.specs.mixins.events.event_types import CatchingEvent
from SpiffWorkflow.bpmn.workflow import BpmnWorkflow
from SpiffWorkflow.task import Task, TaskState
from sqlalchemy import and_, delete, func, null, select
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy_file import File

from actidoo_wfe.helpers.time import dt_now_naive
from actidoo_wfe.wf import events, providers as workflow_providers
from actidoo_wfe.wf.exceptions import InvalidWorkflowSpecException
from actidoo_wfe.wf.models import (
    WorkflowAttachment,
    WorkflowInstance,
    WorkflowInstanceAttachment,
    WorkflowInstanceTask,
    WorkflowInstanceTaskAttachment,
    WorkflowInstanceTaskRole,
    WorkflowMessage,
    WorkflowMessageSubscription,
    WorkflowMessageWorkflowInstance,
    WorkflowSpec,
    WorkflowSpecFile,
    WorkflowTimeEvent,
    WorkflowUser,
    WorkflowUserClaim,
    WorkflowUserRole,
)
from actidoo_wfe.wf.service_workflow import (
    _get_custom_props,
    can_be_unassigned,
    dump,
    get_assigned_delegate_user,
    get_assigned_user,
    get_completed_by_delegate_user,
    get_completed_by_user,
    get_created_by_id,
    get_delegate_submit_comment,
    get_lane_mapping,
    get_react_json_schema_form_data,
    get_stacktrace,
    get_subtitle,
    get_task_data,
    get_task_roles,
    restore,
)
from actidoo_wfe.wf.spiff_customized import MyIntermediateCatchEvent
from actidoo_wfe.wf.types import TimeEvent, UserRepresentation
from actidoo_wfe.helpers.datauri import sanitize_metadata_value


# Repository
def store_workflow_instance(db: Session, workflow: BpmnWorkflow, triggered_by: uuid.UUID|None=None):
    """Stores the workflow and all tasks"""
    id = workflow.task_tree.id  # the id is the id of the top task
    name = workflow.spec.name
    title = workflow.spec.description

    db_workflow = db.execute(
        select(WorkflowInstance).where(WorkflowInstance.id == id)
    ).scalar()

    created_by_id = get_created_by_id(workflow=workflow)
    subtitle = get_subtitle(workflow=workflow)
    instance_was_completed = (
        db_workflow.is_completed if db_workflow is not None else False
    )

    if db_workflow is None:
        db_workflow = WorkflowInstance()
        db_workflow.id = id
        db_workflow.created_by_id = created_by_id
        db_workflow.lane_mapping = get_lane_mapping(workflow)
        db_workflow.name = name
        db_workflow.title = title

    db_workflow.subtitle = subtitle
    db_workflow.data = dump(workflow=workflow)
    db_workflow.is_completed = workflow.is_completed()
    if db_workflow.is_completed and not instance_was_completed:
        # instance has just been set completed
        db_workflow.completed_at = dt_now_naive()

    db.add(db_workflow)

    # TASKS
 
    all_tasks: list[Task] = workflow.get_tasks()
    lane_mapping = db_workflow.lane_mapping

    engine_index=0
    for task in all_tasks:
        engine_index+=1
        
        db_task = db.execute(
            select(WorkflowInstanceTask)
            .join(
                WorkflowInstance,
                WorkflowInstanceTask.workflow_instance_id == WorkflowInstance.id,
            )
            .where(and_(WorkflowInstance.id == id, WorkflowInstanceTask.id == task.id))
        ).scalar()

        task_spec: BpmnTaskSpec = task.task_spec

        task_was_completed = db_task.state_completed if db_task is not None else False
        task_was_ready = db_task.state_ready if db_task is not None else False
        task_was_erroneous = db_task.state_error if db_task is not None else False
        task_was_assigned_to = db_task.assigned_user_id if db_task is not None else None

        if db_task is None:
            db_task = WorkflowInstanceTask()
            is_new = True
            db.add(db_task)

            db_task.id = task.id
            db_task.workflow_instance_id = db_workflow.id
            db_task.bpmn_id = task_spec.bpmn_id
            db_task.lane = task_spec.lane
            if task_spec.lane is not None:
                initiator= lane_mapping.get(task_spec.lane, {}).get(
                    "initiator", False
                )
                # For now, we will just store, whether the lane is the initiator lane; not the defined initiator roles (as they are only relevent for start)
                db_task.lane_initiator = initiator is not None and initiator is not False

            db_task.manual = task_spec.manual
            db_task.name = task_spec.name
            db_task.title = task_spec.bpmn_name or task_spec.name

            db_task.state = task.state
            db_task.state_ready = task.has_state(TaskState.READY)
            db_task.state_completed = task.has_state(TaskState.COMPLETED)
            db_task.state_error = task.has_state(TaskState.ERROR)
            db_task.state_cancelled = task.has_state(TaskState.CANCELLED)

            db_task.data = get_task_data(task)

            formdata = get_react_json_schema_form_data(task)
            if formdata is not None:
                db_task.jsonschema = formdata.jsonschema
                db_task.uischema = formdata.uischema

            db.flush()
        else:
            is_new=False

        existing_roles = set(
            [
                x
                for x in db.execute(
                    select(WorkflowInstanceTaskRole.name).where(                        
                            WorkflowInstanceTaskRole.workflow_instance_task_id == task.id
                    )
                ).scalars()
            ]
        )

        role_set = get_task_roles(workflow=workflow, task_id=task.id)
        to_add_roles = role_set - existing_roles
        to_remove_roles = existing_roles - role_set

        for role in to_add_roles:
            db_task_role = WorkflowInstanceTaskRole()
            db.add(db_task_role)
            db_task_role.workflow_instance_task = db_task
            db_task_role.name = role
            db.flush()

        db.execute(
            delete(WorkflowInstanceTaskRole).where(
                and_(WorkflowInstanceTaskRole.name.in_(to_remove_roles),
                     WorkflowInstanceTaskRole.workflow_instance_task_id == task.id)
            )
        )

        db_task.sort = engine_index
        db_task.can_be_unassigned = can_be_unassigned(
            workflow=workflow, task_id=task.id
        )

        if is_new or db_task.state != task.state:
            db_task.triggered_by_id = triggered_by

        db_task.state = task.state
        db_task.state_ready = task.has_state(TaskState.READY)
        db_task.state_completed = task.has_state(TaskState.COMPLETED)
        db_task.state_error = task.has_state(TaskState.ERROR)
        db_task.state_cancelled = task.has_state(TaskState.CANCELLED)
        db_task.error_stacktrace = get_stacktrace(workflow=workflow, task_id=task.id)

        if db_task.state_completed and not task_was_completed:
            # task has just been set completed
            db_task.completed_at = dt_now_naive()

        db_task.data = get_task_data(task)

        assigned_user_id = get_assigned_user(workflow=workflow, task_id=task.id)
        db_task.assigned_user_id = assigned_user_id
        db_task.assigned_delegate_user_id = get_assigned_delegate_user(
            workflow=workflow, task_id=task.id
        )
        db_task.completed_by_user_id = get_completed_by_user(
            workflow=workflow, task_id=task.id
        )
        db_task.completed_by_delegate_user_id = get_completed_by_delegate_user(
            workflow=workflow, task_id=task.id
        )
        db_task.delegate_submit_comment = get_delegate_submit_comment(
            workflow=workflow, task_id=task.id
        )

        ### Conditionally fire UserAssignedToReadyTaskEvent
        # Define conditions for readability
        is_manual_task = db_task.manual
        is_ready_state = db_task.state_ready
        has_assigned_user = db_task.assigned_user_id is not None
        is_newly_assigned_or_newly_ready = task_was_assigned_to != db_task.assigned_user_id or not task_was_ready
        is_not_triggered_by_current_user = triggered_by is None or triggered_by != db_task.assigned_user_id
        is_excluded_by_property = _get_custom_props(task).get("send_assignment_email", None) == "no"

        # Check if all conditions are met
        if (
            is_manual_task and 
            is_ready_state and 
            has_assigned_user and 
            is_newly_assigned_or_newly_ready and 
            is_not_triggered_by_current_user and
            not is_excluded_by_property
        ):
            events.publish_event(events.UserAssignedToReadyTaskEvent(
                user_id=db_task.assigned_user_id, # type: ignore
                task_id=db_task.id
            ))

        ### Conditionally fire TaskBecameErroneousEvent
        if not task_was_erroneous and db_task.state_error:
            events.publish_event(events.TaskBecameErroneousEvent(task_id=db_task.id))

    all_task_ids = {x.id for x in all_tasks}

    db.execute(
        delete(WorkflowInstanceTask).where(
            and_(
                WorkflowInstanceTask.workflow_instance_id == db_workflow.id,
                WorkflowInstanceTask.id.notin_(all_task_ids)
            )
        )
    )

    db.flush()
    db.expire(db_workflow)

    queue_waiting_receive_messages(db=db, workflow=workflow)
    sync_timer_events(db=db, workflow=workflow)



def load_workflow_instance(db: Session, workflow_id: uuid.UUID) -> BpmnWorkflow:
    """Restores a workflow"""

    db_wf: WorkflowInstance = db.execute(
        select(WorkflowInstance).where(WorkflowInstance.id == workflow_id)
    ).scalar_one()
    db.refresh(db_wf)

    workflow = restore(serialized_data=db_wf.data)

    return workflow


def load_workflow_instance_by_task_id(db: Session, task_id: uuid.UUID)-> BpmnWorkflow:
    """Restores a workflow by task_id"""

    db_task: WorkflowInstanceTask = db.execute(
        select(WorkflowInstanceTask).where(WorkflowInstanceTask.id == task_id)
    ).scalar_one()

    return restore(serialized_data=db_task.workflow_instance.data)

def persist_workflow_spec(db: Session, name: str):
    try:
        folder = workflow_providers.get_workflow_directory(name)
    except FileNotFoundError as error:
        raise InvalidWorkflowSpecException(str(error)) from error
    all_files = [x for x in folder.glob("*") if x.is_file()]

    BUF_SIZE = 65536
    fs_hashes: dict[pathlib.Path, str] = dict()
    for f in all_files:
        with open(f, "rb") as fd:
            hasher = hashlib.sha256()
            while True:
                data = fd.read(BUF_SIZE)
                if not data:
                    break                
                hasher.update(data)
            hash = hasher.hexdigest()
        fs_hashes[f] = hash
        

    #workflow: WorkflowSpec|None = db.execute(
    #    select(WorkflowSpec).where(WorkflowSpec.name == name).order_by(WorkflowSpec.version.desc()).limit(1)
    #).scalar()

    workflow: WorkflowSpec|None = db.execute(
        select(WorkflowSpec).where(WorkflowSpec.name == name).limit(1)
    ).scalar()

    workflow_files_changed = False

    if workflow is None:
        workflow = WorkflowSpec()
        workflow.name = name
        workflow.version = 1 #TODO: implement versioning
        db.add(workflow)
        workflow_files_changed = True
    else:
        existing_db_files: list[WorkflowSpecFile] = list(db.execute(
            select(WorkflowSpecFile).where(WorkflowSpecFile.workflow_spec_id == workflow.id)
        ).scalars())

        for f, hash in fs_hashes.items():
            fs_file_exists_in_db = any(x.file_name == f.name and x.file_hash == hash for x in existing_db_files)
            if not fs_file_exists_in_db:
                workflow_files_changed = True

        for x in existing_db_files:
            db_file_exists_in_fs = any(x.file_name == f.name and x.file_hash == hash for f, hash in fs_hashes.items())
            if not db_file_exists_in_fs:
                workflow_files_changed = True
            
        if workflow_files_changed:
            for f in workflow.files:
                db.delete(f)

    db.flush()

    if workflow_files_changed:
        for f, hash in fs_hashes.items():
            name = f.name
            try:
                content = f.read_text()
            except UnicodeDecodeError:
                # We do not store content for binary file
                content = None
            db_file = WorkflowSpecFile()
            db_file.workflow_spec_id = workflow.id
            db_file.file_hash = hash
            db_file.file_content = content
            db_file.file_name = name
            
            spl = f.name.rsplit(".", 1)

            db_file.file_type = spl[1].lower() if len(spl)==2 else ""
            
            if content is not None:
                pattern = r'<bpmn:process id="(.*?)"'
                match = re.search(pattern, content)
                if match:
                    process_id = match.group(1)
                    db_file.file_bpmn_process_id = process_id
                
            db.add(db_file)


def load_user(db: Session, user_id: uuid.UUID) -> UserRepresentation:
    user = db.execute(
        select(WorkflowUser).where(WorkflowUser.id == user_id)
    ).scalar_one()
    roles = {r.role.name for r in user.roles}
    claims = {claim.claim_key: claim.claim_value for claim in user.claims}

    return UserRepresentation(
        id=user.id,
        username=user.username,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        roles=roles,
        is_service_user=user.is_service_user,
        locale=user.locale,
        claims=claims,
    )


def load_user_by_email(db: Session, email: str) -> UserRepresentation:
    user = db.execute(
        select(WorkflowUser).where(WorkflowUser.email == email)
    ).scalar_one()
    roles = {r.role.name for r in user.roles}
    claims = {claim.claim_key: claim.claim_value for claim in user.claims}

    return UserRepresentation(
        id=user.id,
        username=user.username,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        roles=roles,
        is_service_user=user.is_service_user,
        locale=user.locale,
        claims=claims,
    )


def load_user_by_username(db: Session, username: str) -> UserRepresentation:
    user = db.execute(
        select(WorkflowUser).where(WorkflowUser.username == username)
    ).scalar_one()
    roles = {r.role.name for r in user.roles}
    claims = {claim.claim_key: claim.claim_value for claim in user.claims}

    return UserRepresentation(
        id=user.id,
        username=user.username,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        roles=roles,
        is_service_user=user.is_service_user,
        locale=user.locale,
        claims=claims,
    )


def load_users_by_ids(
    db: Session, user_ids: set[uuid.UUID]
) -> dict[uuid.UUID, UserRepresentation]:
    if not user_ids:
        return {}

    users = db.execute(
        select(WorkflowUser)
        .options(selectinload(WorkflowUser.roles).selectinload(WorkflowUserRole.role))
        .where(WorkflowUser.id.in_(user_ids))
    ).scalars().all()

    result: dict[uuid.UUID, UserRepresentation] = {}
    for user in users:
        roles = {r.role.name for r in user.roles}
        result[user.id] = UserRepresentation(
            id=user.id,
            username=user.username,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            roles=roles,
            is_service_user=user.is_service_user,
            locale=user.locale,
        )
    return result


def upsert_user(
    db: Session,
    idp_user_id: str | None,
    username: str,
    email: str | None,
    first_name: str | None,
    last_name: str | None,
    is_service_user: bool
):
    # The idp_user_id (i.e. the keycloak id) can be None when inserting a new user which has never logged in yet.
    # The can also be existing users in the database, where idp_user_id is still None.
    # So, if idp_user_id is None, we can not take idp_user_id as select option to check if the user exists,
    # but then we take the username.
    if idp_user_id is not None:
        user = db.execute(
            select(WorkflowUser).where(WorkflowUser.idp_id == idp_user_id)
        ).scalar()
    else:
        user = db.execute(
            select(WorkflowUser).where(WorkflowUser.username == username)
        ).scalar()

    if user is None:
        user = WorkflowUser()
        if idp_user_id is not None:
            user.idp_id = idp_user_id
        db.add(user)

    user.username = username
    user.email = email
    user.first_name = first_name
    user.last_name = last_name
    user.is_service_user = is_service_user

    db.flush()
    db.expire(user)

    return load_user_by_username(db=db, username=username)


def find_attachment_by_hash(db: Session, hash: str) -> WorkflowAttachment | None:
    return db.execute(
        select(WorkflowAttachment).where(WorkflowAttachment.hash == hash)
    ).scalar()


def find_attachment_by_id(
    db: Session, attachment_id: uuid.UUID
) -> WorkflowAttachment | None:
    return db.execute(
        select(WorkflowAttachment).where(WorkflowAttachment.id == attachment_id)
    ).scalar()


def store_attachment(
    db: Session, filename: str, mimetype: str | None, data: bytes, hash: str
) -> WorkflowAttachment:
    obj = find_attachment_by_hash(db=db, hash=hash)

    if not obj:
        obj = WorkflowAttachment()
        obj.hash = hash
        obj.first_filename = filename
        obj.file = File(content=data, filename=sanitize_metadata_value(filename), content_type=mimetype)
        db.add(obj)

    if mimetype is not None and obj.mimetype is None:
        obj.mimetype = mimetype
        db.add(obj)

    db.flush()
    db.expire(obj)

    return obj


def store_attachment_for_task(
    db: Session, task_id: uuid.UUID, attachment_id: uuid.UUID, filename: str
) -> WorkflowInstanceTaskAttachment:
    obj = db.execute(
        select(WorkflowInstanceTaskAttachment).where(
            WorkflowInstanceTaskAttachment.workflow_attachment_id == attachment_id,
            WorkflowInstanceTaskAttachment.workflow_instance_task_id == task_id,
        )
    ).scalar()

    if not obj:
        obj = WorkflowInstanceTaskAttachment()
        obj.workflow_attachment_id = attachment_id
        obj.filename = filename
        obj.workflow_instance_task_id = task_id
        db.add(obj)

    db.flush()
    db.expire(obj)

    return obj


def store_attachment_for_workflow_instance(
    db: Session,
    workflow_instance_id: uuid.UUID,
    attachment_id: uuid.UUID,
    filename: str,
) -> WorkflowInstanceAttachment:
    obj = db.execute(
        select(WorkflowInstanceAttachment).where(
            WorkflowInstanceAttachment.workflow_attachment_id == workflow_instance_id,
            WorkflowInstanceAttachment.workflow_instance_id == workflow_instance_id,
        )
    ).scalar()

    if not obj:
        obj = WorkflowInstanceAttachment()
        obj.workflow_attachment_id = attachment_id
        obj.filename = filename
        obj.workflow_instance_id = workflow_instance_id
        db.add(obj)

    db.flush()
    db.expire(obj)

    return obj


def find_task_attachments_by_task_id(db: Session, task_id: uuid.UUID):
    return list(
        db.execute(
            select(WorkflowInstanceTaskAttachment)
            .options(joinedload(WorkflowInstanceTaskAttachment.attachment))
            .where(
                and_(
                    WorkflowInstanceTaskAttachment.workflow_instance_task_id == task_id
                )
            )
        ).scalars()
    )


def find_task_attachments_by_worfklow_instance_id(
    db: Session, workflow_instance_id: uuid.UUID
):
    return list(
        db.execute(
            select(WorkflowInstanceTaskAttachment)
            .options(joinedload(WorkflowInstanceTaskAttachment.attachment))
            .join(
                WorkflowInstanceTask,
                WorkflowInstanceTask.id
                == WorkflowInstanceTaskAttachment.workflow_instance_task_id,
            )
            .where(
                and_(WorkflowInstanceTask.workflow_instance_id == workflow_instance_id)
            )
        ).scalars()
    )


def find_workflow_instance_attachments_by_worfklow_instance_id(
    db: Session, workflow_instance_id: uuid.UUID
):
    return list(
        db.execute(
            select(WorkflowInstanceAttachment)
            .options(joinedload(WorkflowInstanceAttachment.attachment))
            .where(
                and_(
                    WorkflowInstanceAttachment.workflow_instance_id
                    == workflow_instance_id
                )
            )
        ).scalars()
    )


def delete_attachment_for_task(
    db: Session, task_id: uuid.UUID, attachment_id: uuid.UUID
):
    db.execute(
        delete(WorkflowInstanceTaskAttachment).where(
            and_(
                WorkflowInstanceTaskAttachment.workflow_instance_task_id == task_id,
                WorkflowInstanceTaskAttachment.workflow_attachment_id == attachment_id,
            )
        )
    )
    db.flush()


def delete_attachment_for_workflow_instance(
    db: Session, workflow_instance_id: uuid.UUID, attachment_id: uuid.UUID
):
    db.execute(
        delete(WorkflowInstanceAttachment).where(
            and_(
                WorkflowInstanceAttachment.workflow_instance_id == workflow_instance_id,
                WorkflowInstanceAttachment.workflow_attachment_id == attachment_id,
            )
        )
    )
    db.flush()


def delete_dangling_attachment(db: Session, attachment_id: uuid.UUID):
    attachment = find_attachment_by_id(db=db, attachment_id=attachment_id)

    n_tasks = db.execute(
        select(func.count())
        .select_from(WorkflowInstanceTaskAttachment)
        .where(WorkflowInstanceTaskAttachment.workflow_attachment_id == attachment_id)
    ).scalar_one()

    n_workflow_instances = db.execute(
        select(func.count())
        .select_from(WorkflowInstanceAttachment)
        .where(WorkflowInstanceAttachment.workflow_attachment_id == attachment_id)
    ).scalar_one()

    if n_tasks == 0 and n_workflow_instances == 0:
        db.delete(attachment)

    db.flush()

def store_message(
        db: Session,
        message_name: str,
        correlation_key: str, 
        data: dict,
        sent_by_user_id: uuid.UUID|None,
        sent_by_workflow_instance_id: uuid.UUID|None
    ):
    
    msg = WorkflowMessage()
    msg.name = message_name
    msg.correlation_key = correlation_key
    msg.data = data
    msg.sent_by_user_id = sent_by_user_id
    msg.sent_by_workflow_instance_id = sent_by_workflow_instance_id
    db.add(msg)
    db.flush()
    
def store_message_processed(
        db: Session,
        message_id: uuid.UUID,
        processed_by_workflow_instance_ids: set[uuid.UUID]
    ):
    
    msg_ex = db.execute(select(WorkflowMessage).filter(WorkflowMessage.id == message_id)).scalar_one()
    
    msg_ex.processed_at = dt_now_naive()

    db.flush()

    for wfid in processed_by_workflow_instance_ids:
        msg_wf_instance = WorkflowMessageWorkflowInstance()
        msg_wf_instance.message_id = msg_ex.id
        msg_wf_instance.workflow_instance_id = wfid
        db.add(msg_wf_instance)

    db.flush()


def load_unprocessed_messages(
    db: Session
):
    return list(
        db.execute(
            select(WorkflowMessage).filter(WorkflowMessage.processed_at == null())
        ).scalars()
    )

def queue_waiting_receive_messages(
    db: Session,
    workflow: BpmnWorkflow
):
    iter = [t for t in workflow.get_tasks_iterator(state=TaskState.WAITING, spec_class=CatchingEvent)]
    waiting_event_tasks:list[Task] = [t for t in iter if t.task_spec.event_definition.details(t).event_type == "MessageEventDefinition"]

    existing_subscriptions = db.execute(
        select(WorkflowMessageSubscription)
        .join(WorkflowInstanceTask, WorkflowMessageSubscription.workflow_instance_task_id == WorkflowInstanceTask.id)
        .where(
            WorkflowInstanceTask.workflow_instance_id == workflow.task_tree.id
        )
    ).scalars()

    for sub in existing_subscriptions:
        db.delete(sub)

    for task in waiting_event_tasks:
        if isinstance(task.task_spec, MyIntermediateCatchEvent):
            event_details = task.task_spec.event_definition.details(task)

            evaluated_correlation_key = task.task_spec.evaluate_correlation_key(task=task)

            # Create a new Message Instance
            subscription = WorkflowMessageSubscription()
            subscription.workflow_instance_task_id = task.id
            subscription.name = event_details.name
            subscription.correlation_key = evaluated_correlation_key

            db.add(subscription)

    db.flush()

def get_subscriptions_by_message_name_and_correlation_key(db: Session, message_name: str, correlation_key: str):
    subscriptions = db.execute(
        select(WorkflowMessageSubscription)
        .where(and_(
            WorkflowMessageSubscription.name == message_name,
            WorkflowMessageSubscription.correlation_key == correlation_key
        ))
    ).scalars()

    return subscriptions


def delete_workflow_instance(db: Session, workflow: BpmnWorkflow):
    """Deletes a workflow instance comletely"""
    id = workflow.task_tree.id  # the id is the id of the top task
    
    db.execute(
        delete(WorkflowInstance).where(
            WorkflowInstance.id == id
        )
    )
    
    db.flush()


def list_due_time_events(db: Session, *, now: datetime.datetime, limit: int = 200) -> list[TimeEvent]:
    """Return scheduled time events due at or before 'now' as domain objects."""
    rows: list[WorkflowTimeEvent] = list(
        db.execute(
            select(WorkflowTimeEvent)
            .where(and_(WorkflowTimeEvent.status == "scheduled", WorkflowTimeEvent.due_at <= now))
            .order_by(WorkflowTimeEvent.due_at.asc())
            .limit(limit)
        )
        .scalars()
        .all()
    )
    return [
        TimeEvent(
            workflow_instance_id=r.workflow_instance_id,
            timer_task_id=r.timer_task_id,
            timer_kind=r.timer_kind,
            due_at=r.due_at,
            interrupting=r.interrupting,
            remaining_cycles=r.remaining_cycles,
            expression=r.expression,
        )
        for r in rows
    ]

def _get_wte_by_id(db: Session, wte_id: uuid.UUID) -> WorkflowTimeEvent:
    return db.execute(
        select(WorkflowTimeEvent).where(WorkflowTimeEvent.id == wte_id)
    ).scalar_one()

def _get_wte_from_any(db: Session, wte: Union[WorkflowTimeEvent, TimeEvent, uuid.UUID]) -> WorkflowTimeEvent:
    if isinstance(wte, WorkflowTimeEvent):
        return wte
    if isinstance(wte, uuid.UUID):
        return _get_wte_by_id(db, wte)

    return db.execute(
        select(WorkflowTimeEvent).where(
            and_(
                WorkflowTimeEvent.workflow_instance_id == wte.workflow_instance_id,
                WorkflowTimeEvent.timer_task_id == wte.timer_task_id,
            )
        )
    ).scalar_one()

def mark_timer_completed(db: Session, wte: Union[WorkflowTimeEvent, TimeEvent, uuid.UUID]):
    """Mark a timer as completed; accepts ORM, domain, or id."""
    rec = _get_wte_from_any(db, wte)
    rec.status = "completed"
    db.flush()

def cancel_timer_for_task(db: Session, wte: Union[WorkflowTimeEvent, TimeEvent, uuid.UUID]):
    rec = _get_wte_from_any(db, wte)
    if rec.status not in ("completed", "cancelled"):
        rec.status = "cancelled"
        db.flush()

def reschedule_cycle(db: Session, wte: Union[WorkflowTimeEvent, TimeEvent, uuid.UUID], next_due: datetime.datetime, remaining_cycles: int):
    rec = _get_wte_from_any(db, wte)
    rec.status = "scheduled"
    rec.due_at = next_due.astimezone(datetime.timezone.utc)
    rec.remaining_cycles = remaining_cycles
    rec.fire_count += 1
    db.flush()

def fail_and_release(db: Session, wte: Union[WorkflowTimeEvent, TimeEvent, uuid.UUID], err: str):
    rec = _get_wte_from_any(db, wte)
    rec.status = "error"
    rec.last_error = (err or "")[:4000]
    db.flush()

def _first_timer_def(task: Task) -> TimerEventDefinition | None:
    ed = getattr(task.task_spec, "event_definition", None)
    if ed and isinstance(ed, TimerEventDefinition):
        return ed
    return None

def _prepare_timer_events(workflow: BpmnWorkflow) -> list[TimeEvent]:
    """
    Build scheduling plans by reading pre-populated 'event_value' from each WAITING timer task.
    We use 'ed.details(task)' to obtain the same PendingBpmnEvent you see in workflow.waiting_events,
    but with a stable mapping to the task (for timer_task_id).
    """
    plans: list[TimeEvent] = []
    wf_id = workflow.task_tree.id

    for t in workflow.get_tasks(state=TaskState.WAITING):
        ed = _first_timer_def(t)
        if ed is None:
            continue

        details = ed.details(t) # Read the PendingBpmnEvent for this task
        ev_type = details.event_type     # e.g., "TimeDateEventDefinition", "DurationTimerEventDefinition", "CycleTimerEventDefinition"
        ev_value = details.value  # already populated by update_hook

        interrupting = bool(getattr(t.task_spec, "cancel_activity", True))

        if ev_type in ("TimeDateEventDefinition", "DurationTimerEventDefinition"):
            # ev_value is ISO datetime string
            if not isinstance(ev_value, str): # Defensive Fallback
                continue
            due = TimerEventDefinition.get_datetime(ev_value)  # UTC
            kind: Literal["time_date","time_duration"] = "time_date" if ev_type == "TimeDateEventDefinition" else "time_duration"
            plans.append(TimeEvent(
                workflow_instance_id=wf_id,
                timer_task_id=t.id,
                timer_kind=kind,
                due_at=due.astimezone(datetime.timezone.utc),
                interrupting=interrupting,
                expression=ev_value,
                remaining_cycles=None,
            ))
        elif ev_type == "CycleTimerEventDefinition":
            # ev_value is dict {'cycles': int, 'next': iso, 'duration': seconds}
            if not isinstance(ev_value, dict):
                continue
            next_iso = ev_value.get("next")
            cycles = ev_value.get("cycles", -1)
            if not next_iso:
                continue
            due = TimerEventDefinition.get_datetime(next_iso)

            plans.append(TimeEvent(
                workflow_instance_id=wf_id,
                timer_task_id=t.id,
                timer_kind="time_cycle",
                due_at=due.astimezone(datetime.timezone.utc),
                interrupting=interrupting,
                expression=None,
                remaining_cycles=int(cycles) if cycles is not None else -1,
            ))
        else:
            # Not a timer event we schedule
            continue

    return plans


def sync_timer_events(
    db: Session,
    *,
    workflow: BpmnWorkflow
) -> None:
    workflow_instance_id = workflow.task_tree.id
    plans = _prepare_timer_events(workflow)

    existing: list[WorkflowTimeEvent] = list(
        db.execute(select(WorkflowTimeEvent).where(WorkflowTimeEvent.workflow_instance_id == workflow_instance_id))
        .scalars()
        .all()
    )
    existing_by_task = {e.timer_task_id: e for e in existing}
    planned_task_ids = {str(p.timer_task_id) for p in plans}

    now = dt_now_naive()

    # Cancel those no longer planned
    for e in existing:
        if str(e.timer_task_id) not in planned_task_ids and e.status not in ("completed", "cancelled"):
            e.status = "cancelled"

    # Upsert plans
    for p in plans:
        e = existing_by_task.get(p.timer_task_id)
        if e is None:
            e = WorkflowTimeEvent()
            db.add(e)
            e.workflow_instance_id=workflow_instance_id
            e.timer_task_id=p.timer_task_id


        e.timer_kind=p.timer_kind
        e.expression=p.expression
        e.interrupting=p.interrupting
        e.due_at=p.due_at
        e.remaining_cycles=p.remaining_cycles
        e.status="scheduled"
        e.created_at=now

    db.flush()
