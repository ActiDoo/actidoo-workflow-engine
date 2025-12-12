"""
    This module contains most of our work around workflow instances:
    Loading, Execution, User Assignment, Delegations to Form-Service,....

    This module works on domain objects. There must not be any database involved here.
"""

import collections
from dataclasses import dataclass
import datetime
import logging
import traceback
import uuid
from copy import deepcopy
from functools import cache
from typing import Any, Generator, List, Literal

from pydantic import BaseModel, Field
from SpiffWorkflow.bpmn import BpmnEvent, BpmnWorkflow
from SpiffWorkflow.bpmn.parser.ProcessParser import ProcessParser
from SpiffWorkflow.bpmn.parser.ValidationException import ValidationException
from SpiffWorkflow.bpmn.specs.bpmn_task_spec import BpmnTaskSpec
from SpiffWorkflow.bpmn.util.event import PendingBpmnEvent
from SpiffWorkflow.camunda.specs.event_definitions import MessageEventDefinition
from SpiffWorkflow.exceptions import TaskNotFoundException, WorkflowException
from SpiffWorkflow.task import Task, TaskFilter, TaskState
from SpiffWorkflow.bpmn.specs.event_definitions.timer import TimerEventDefinition, TimeDateEventDefinition, CycleTimerEventDefinition, DurationTimerEventDefinition

from actidoo_wfe.helpers.modules import env_from_module
from actidoo_wfe.helpers.string import boolean_or_string_list
from actidoo_wfe.helpers.tests import in_test
from actidoo_wfe.settings import settings
from actidoo_wfe.wf.constants import (
    DATA_KEY_CREATED_BY,
    DATA_KEY_WORKFLOW_INSTANCE_SUBTITLE,
    INTERNAL_DATA_KEY_ALLOW_UNASSIGN,
    INTERNAL_DATA_KEY_ASSIGNED_ROLES,
    INTERNAL_DATA_KEY_ASSIGNED_USER,
    INTERNAL_DATA_KEY_STACKTRACE,
)
from actidoo_wfe.wf import providers as workflow_providers
from actidoo_wfe.wf.exceptions import (
    FormNotFoundException,
    TaskAlreadyAssignedToDifferentUserException,
    TaskCannotBeUnassignedException,
    TaskIsNotErroneousException,
    UserMayNotCopyWorkflowException,
)
from actidoo_wfe.wf.service_form import (
    get_options,
    get_options_detailed,
    validate_task_data,
)
from actidoo_wfe.wf.spiff_customized import (
    get_parser,
    get_script_engine,
    get_serializer,
)
from actidoo_wfe.wf.types import (
    MessageEventDefinitionRepresentation,
    ReactJsonSchemaFormData,
    UserRepresentation,
    UserTaskWithoutNestedAssignedUserRepresentation,
    TimeEvent,
)

log = logging.getLogger(__name__)

def load_process_from_file(name: str):
    """Loads a process from files parses it and returns a BpmnWorkflow object"""
    try:

        parser = get_parser()
        folder = workflow_providers.get_workflow_directory(name)
        bpmn_files = [str(x.absolute()) for x in folder.glob("*.bpmn") if x.is_file()]
        dmn_files = [str(x.absolute()) for x in folder.glob("*.dmn") if x.is_file()]
        parser.add_bpmn_files(bpmn_files)
        if dmn_files:
            parser.add_dmn_files(dmn_files)

        top_level = parser.get_spec(name) # This is where the real parsing is called in MyProcessParser._parse() of spiff_customized.py
        subprocesses = parser.get_subprocess_specs(name)
        workflow = BpmnWorkflow(
            top_level, subprocesses, script_engine=get_script_engine(workflow_name=name)
        )

        return workflow
    except ValidationException as error:
        log.error(f"load_process_from_file({name}): {type(error).__name__}: {error.args}, id={error.id}, name={error.name}, file = {error.file_name}")
        raise error

def start_process(name: str, created_by: UserRepresentation):
    """Loads a process from files, sets the creator and returns a BpmnWorkflow object"""

    workflow = load_process_from_file(name)

    workflow.set_data(**{DATA_KEY_CREATED_BY: str(created_by.id)})
    return workflow

def user_may_start_workflow(name: str, user: UserRepresentation):
    workflow_initiator_roles= get_initiator_property_cached(name=name)

    if workflow_initiator_roles is None:
        return True
    else:
        return workflow_initiator_roles is True or  \
            (isinstance(workflow_initiator_roles, list) and len(set(workflow_initiator_roles) & user.roles)>0 )

def restore(serialized_data: dict):
    """Restores a workflow from serialized data"""
    serializer = get_serializer()
    serializer.migrate(serialized_data)
    workflow = serializer.from_dict(serialized_data)
    workflow.script_engine = get_script_engine(workflow_name=workflow.spec.name)
    return workflow


def dump(workflow: BpmnWorkflow):
    """Serializes a workflow"""
    serializer = get_serializer()
    dct = serializer.to_dict(workflow)
    dct[serializer.VERSION_KEY] = serializer.VERSION # type: ignore
    return dct
    #return json.dumps(dct, indent=2, separators=(", ", ": "))

def get_unfinished_tasks(workflow: BpmnWorkflow):
    return workflow.get_tasks(task_filter=TaskFilter(state = TaskState.NOT_FINISHED_MASK))

def get_faulty_tasks(workflow: BpmnWorkflow):
    return workflow.get_tasks(task_filter=TaskFilter(state = TaskState.ERROR))

def run_workflow(workflow: BpmnWorkflow):
    """Runs all possible tasks and finally auto-assigns if possible"""

    # TODO: This logic could be moved to application service, as we might want to persist after each step?!?

    if not workflow.is_completed():
        engine_tasks = [
            t for t in workflow.get_tasks(task_filter=TaskFilter(state = TaskState.READY, manual=False))
        ]
        result = True
        while len(engine_tasks) > 0:
            for task in engine_tasks:
                set_stacktrace(
                    workflow=workflow, task_id=task.id, stacktrace=None
                )  # reset stacktrace
                try:
                    success = task.run()
                    if not success:
                        result = False
                        task.error()
                        log.exception("task failed") # TODO no error code is returned
                except Exception as error: # WorkflowTaskException("Error evaluating expression '=optional_approver1 != null'")
                    log.exception(f'{type(error).__name__}: {error.args}') # TODO the exception/args is often very descriptive, but the information is not re-raised, only a bool gets return and the Exception info is lost....
                    result = False
                    task.error()
                    s_traceback = traceback.format_exc()
                    set_stacktrace(
                        workflow=workflow, task_id=task.id, stacktrace=s_traceback
                    )
                    log.exception("task failed") # TODO no error code is returned

            workflow.refresh_waiting_tasks()
            engine_tasks = [
                t for t in workflow.get_tasks(task_filter=TaskFilter(state = TaskState.READY, manual=False))
            ]

    auto_assign_all_tasks_in_initiator_lane(workflow=workflow)
    cleanup_hidden_fields_for_ready_tasks(workflow=workflow)
    return result

def update(dest, upd):
    ''' A deep update function, which merges the contents of two dictionaries.'''
    # we assume that d and u are dicts (or more general 'Mappings')
    try:
        for k, v in upd.items():
            if isinstance(v, collections.abc.Mapping):
                # if the new value is a Mapping too, let's do a simple recursion
                dest[k] = update(dest.get(k, {}), v)
            elif isinstance(v, list):
                # consider an empty list [] first:
                if len(v) == 0:
                    dest[k] = []
                    continue
                # if it's a list, it can be a list of dicts [{...}, {...}] or a list of strings ["..", ".."]
                # we only support lists of same types and therfore only check the first entry for its type
                if isinstance(v[0], collections.abc.Mapping): # [{...}, {...}]
                    if k not in dest or not isinstance(dest[k], list): #in dest we may not have a list or some other type (see new_list or some_other_list_type_dict)
                        dest[k] = [{}] * len(v)  # create an empty list with as many elements as v
                    elif len(dest[k]) < len(v):
                        dest[k].extend([{}] * (len(v)-len(dest[k]) )) # if dest[k] is smaller extend it with a list of empty dicts to get the same size as v
                    elif len(dest[k]) > len(v):
                        del dest[k][-(len(dest[k]) - len(v)):] # if dest[k] is bigger then delete the last items
                        # TODO actually we do not know that the user intended to remove the last item!
                        # This works only if all the items contain ALL the properties, otherwise we might mix different items together
                        # But to solve this a list is not sufficient, we would need a data structure, which stores the information if an item got deleted

                    # now we have equally sized lists of the same type on both sides and can safely update each element of dest:
                    assert len(v) == len(dest[k])

                    for idx, new_value in enumerate(v):
                        # We can't write
                        #    update(dest[k][idx], new_value)
                        #    or dest[k][idx] = update(dest[k][idx], new_value)
                        # but we need a deepcopy, because otherwise update() insert 'new_value' into every index of 'dest[k]'
                        # and not only at position 'idx'
                        # This happens only if dest[k] was initialized with empty dicts: [{}]*len(v)
                        tmp = deepcopy(dest[k][idx])
                        dest[k][idx] = update(tmp, new_value)
                        # update((dest[k])[idx], new_value)

                else: # ["", ""] or any other list
                    # the list of strings in dest mus be overwritten with the exact list of v.
                    dest[k] = []
                    for new_value in v:
                        dest[k].append(new_value)
            else:
                dest[k] = v
        return dest
    except Exception as error:
        log.exception(f'{type(error).__name__}: {error.args}.')
        log.error(f'Error in update:\n{dest} \n\n {upd}')
        raise error

def execute_user_task(
    workflow: BpmnWorkflow,
    user: UserRepresentation,
    task_id: uuid.UUID,
    cleaned_task_data: dict,
):
    """Runs a user task, afterwards proceeds with run_workflow"""
    task: Task = workflow.get_task_from_id(task_id)

    assert is_assigned_to_task(workflow=workflow, task_id=task.id, user_id=user.id)

    update(task.data, cleaned_task_data)
    
    set_stacktrace(
        workflow=workflow, task_id=task_id, stacktrace=None
    )  # reset stacktrace

    result = task.run()
    logging.debug(result)

    # TODO: This logic could be moved to application service, as we might want to persist after each step?!?
    return run_workflow(workflow=workflow)


def get_completed_usertasks(workflow: BpmnWorkflow) -> list[Task]:
    """Returns the usertasks which are completed (and manual)"""
    tasks = workflow.get_tasks(task_filter=TaskFilter(state = TaskState.COMPLETED))
    return [t for t in tasks if t.task_spec.manual]


def get_ready_and_waiting_usertasks(workflow: BpmnWorkflow) -> list[Task]:
    """Returns the usertasks which are ready or waiting (and manual)"""
    tasks = workflow.get_tasks(task_filter=TaskFilter(state = TaskState.READY | TaskState.WAITING))
    return [t for t in tasks if t.task_spec.manual]


def get_usertasks_for_user(
    workflow: BpmnWorkflow,
    user: UserRepresentation,
    state: Literal["ready", "completed"] | list[Literal["ready", "completed"]],
):
    tasks = []
    if "ready" in state :
        tasks = get_ready_and_waiting_usertasks(workflow=workflow)

    if "completed" in state:
        tasks.extend(get_completed_usertasks(workflow=workflow))

    available_tasks: list[UserTaskWithoutNestedAssignedUserRepresentation] = []
    for task in tasks:
        assigned_user_id = get_assigned_user(workflow=workflow, task_id=task.id)
        assigned = user.id == assigned_user_id
        task_roles = get_task_roles(workflow=workflow, task_id=task.id)
        lane_is_initiator = is_initiator_lane(
            workflow=workflow, lane_name=task.task_spec.lane
        )
        created_by_id = get_created_by_id(workflow=workflow)

        task_is_available_for_this_user = (
            assigned
            or len(task_roles & user.roles) > 0
            or (lane_is_initiator and user.id == created_by_id)
        )

        assigned_user_id = get_assigned_user(workflow=workflow, task_id=task.id)

        if task_is_available_for_this_user:
            formspec = get_react_json_schema_form_data(task=task)
            if formspec is None:
                pass
            else:
                available_tasks.append(
                    UserTaskWithoutNestedAssignedUserRepresentation(
                        name=task.task_spec.name,
                        title=task.task_spec.bpmn_name or task.task_spec.bpmn_id,
                        id=task.id,
                        lane=task.task_spec.lane,
                        lane_initiator=lane_is_initiator,
                        assigned_user_id=assigned_user_id,
                        assigned_to_me=assigned,
                        can_be_unassigned=can_be_unassigned(
                            workflow=workflow, task_id=task.id
                        ),
                        can_cancel_workflow=can_user_cancel_workflow(
                            workflow=workflow, task_id=task.id, user_id=user.id
                        ),
                        can_delete_workflow=can_user_delete_workflow(
                            workflow=workflow, task_id=task.id, user_id=user.id
                        ),
                        state_completed=task.has_state(TaskState.COMPLETED),
                        **formspec._asdict(),
                        data=get_task_data(task),
                    )
                )
    available_tasks.reverse()
    return available_tasks


def get_waiting_events(workflow: BpmnWorkflow) -> List[MessageEventDefinitionRepresentation]:
    waiting_events: list[PendingBpmnEvent] = workflow.waiting_events()
    return [MessageEventDefinitionRepresentation(
        name=e.name,
        value=e.value,
        event_type=e.event_type
    ) for e in waiting_events
    ]

def send_event(workflow: BpmnWorkflow, name: str, payload: dict):
    # We need to construct the MessageEventDefinition class from the "camunda" package.
    # The "catches" check compares the classes (this event definition == event definition in bpmn file)

    bpmn_message = MessageEventDefinition(
        name=name,
        correlation_properties=[],
    )
    bpmn_event = BpmnEvent(
        event_definition=bpmn_message,
        payload={
            'payload': payload
        }
    )

    # This overrides SpiffWorkflow.bpmn.workflow::send_event to check the message payload
    tasks = workflow.get_tasks(catches_event=bpmn_event, task_filter=TaskFilter(state = TaskState.WAITING))
    if len(tasks) == 0:
        raise WorkflowException(f"This process is not waiting for {bpmn_event.event_definition.name}")
    for task in tasks:
        task.task_spec.catch(task, bpmn_event)
        task.run()

    workflow.refresh_waiting_tasks()


def get_react_json_schema_form_data(task: Task):
    form_spec = getattr(task.task_spec, "form", None)
    return ReactJsonSchemaFormData(*form_spec) if form_spec else None


def get_task_data(task: Task) -> dict:
    return task.data


def _get_workflow_functions_env(workflow_name: str) -> dict[str, Any]:
    module_path = workflow_providers.get_workflow_module_path(workflow_name)
    if not module_path:
        return {}
    try:
        return env_from_module(module_path)
    except ImportError:
        log.debug("Workflow module '%s' could not be imported for workflow '%s'", module_path, workflow_name)
        return {}

def get_allowed_workflow_names_to_start(user: UserRepresentation) -> Generator[str, Any, None]:
    """Returns a list of all possible workflow names, the user may start"""
    for folder in workflow_providers.iter_workflow_directories():
        name = folder.name
        if name in settings.workflows or in_test() or "__ALL__" in settings.workflows:
            if user_may_start_workflow(name=name, user=user):
                yield name


def get_all_activated_workflow_names() -> Generator[str, Any, None]:
    """Returns a list of all activated workflow names"""
    for folder in workflow_providers.iter_workflow_directories():
        name = folder.name
        if name in settings.workflows or in_test() or "__ALL__" in settings.workflows:
            yield name
                
@cache
def get_workflow_title_cached(name: str):
    assert name is not None and name != ""

    try:
        process = load_process_from_file(name=name)
        return process.spec.description
    except Exception:
        log.exception(f"Cannot get workflow title (description) for workflow {name}")
        return name
    
@cache
def get_workflow_saved_minutes_per_instance_cached(name: str) -> int:
    assert name is not None and name != ""

    try:
        process = load_process_from_file(name=name)
        return process.spec.custom_props.get("statistics_saved_minutes", 10)
    except Exception:
        log.exception(f"Cannot get workflow custom property statistics_saved_minutes (statistics_saved_minutes) for workflow {name}")
        return 10
    
@cache
def get_workflow_owner(name: str):
    """Fetches the value of the custom property 'wf-owner'.

    Args:
        name (str): The name of the workflow to load.

    Returns:
        str | None: The owner role of the workflow if defined, otherwise None.

    Raises:
        Exception: Logs an error if there is an issue loading the workflow.
    """
    assert name is not None and name != ""

    try:
        process = load_process_from_file(name=name)
        return process.spec.custom_props.get("wf-owner", None)
    except Exception:
        log.error(f"Cannot get workflow custom property wf-owner for workflow {name}")
        return None

def get_wf_owner_role_to_workflow_mapping():
    """
    Generates a mapping of workflow owner roles to their corresponding workflow names.

    This function iterates through all activated workflow names and retrieves the owner role
    for each workflow. It constructs a dictionary where the keys are the workflow owner roles
    and the values are lists of workflow names associated with those roles.

    Returns:
        dict: A dictionary which maps workflow owner roles to lists of workflow names.
    """
    role_to_workflow_map = {}
    for wfname in get_all_activated_workflow_names():
        wf_owner_role = get_workflow_owner(wfname)
        if wf_owner_role is not None:
            role_to_workflow_map.setdefault(wf_owner_role, []).append(wfname)
    return role_to_workflow_map

@cache
def can_load_workflow(name):
    try:
        load_process_from_file(name=name)
    except Exception as error:
        log.error(f'load_process_from_file({name}): {type(error).__name__}: {error.args}. Raised in load_process_from_file({name})')
        return False
    else:
        return True

@cache
def get_initiator_property_cached(name: str) -> list[str] | bool | None:

    assert name is not None and name != ""

    try:
        workflow = load_process_from_file(name=name)
        lane_mapping = get_lane_mapping(workflow=workflow)
        return next((v.get("initiator") for k,v in lane_mapping.items() if v.get("initiator", None) is not None), None)
    except Exception as error:
        log.error(f"get_initiator_property_cached({name}): {type(error).__name__}: {error.args}")
        return False


def get_created_by_id(workflow: BpmnWorkflow) -> uuid.UUID | None:
    created_by = workflow.get_data(DATA_KEY_CREATED_BY)
    created_by = uuid.UUID(created_by) if created_by is not None else None
    return created_by


def get_subtitle(workflow: BpmnWorkflow) -> str | None:
    subtitle = workflow.get_data(DATA_KEY_WORKFLOW_INSTANCE_SUBTITLE)
    return subtitle


def get_assigned_user(
    workflow: BpmnWorkflow, task_id: uuid.UUID
) -> uuid.UUID | None:
    task: Task = workflow.get_task_from_id(task_id)
    assigned_user_id: str | None = task._get_internal_data(
        name=INTERNAL_DATA_KEY_ASSIGNED_USER, default=None
    )
    assigned_user_uuid = uuid.UUID(assigned_user_id) if assigned_user_id is not None else None
    return assigned_user_uuid


def is_assigned_to_task(workflow: BpmnWorkflow, task_id: uuid.UUID, user_id: uuid.UUID):
    """Returns whether a user is assigned to the task"""
    assigned_user_id = get_assigned_user(
        workflow=workflow, task_id=task_id
    )
    return assigned_user_id == user_id


def assign_task(workflow: BpmnWorkflow, task_id: uuid.UUID, user: UserRepresentation):
    """Assign a user to the task"""

    usertasks = get_usertasks_for_user(workflow=workflow, user=user, state="ready")

    task: UserTaskWithoutNestedAssignedUserRepresentation | None = next(
        (t for t in usertasks if t.id == task_id), None
    )

    if task is None:
        raise TaskNotFoundException(
            message="A ready user task with the given id has not been found"
        )

    assigned_user_id = get_assigned_user(workflow=workflow, task_id=task.id)

    if assigned_user_id is not None and assigned_user_id != user.id:
        raise TaskAlreadyAssignedToDifferentUserException()

    workflow.get_task_from_id(task_id=task.id)._set_internal_data(
        **{INTERNAL_DATA_KEY_ASSIGNED_USER: str(user.id)}
    )


def assign_task_without_checks(
    workflow: BpmnWorkflow, task_id: uuid.UUID, user_id: uuid.UUID
):
    """We want to assign a (future) task from a script and do not want to perform additional checks"""

    task: Task | None = next((t for t in workflow.get_tasks() if t.id == task_id), None)

    if task is None:
        raise TaskNotFoundException(
            message="A task with the given id has not been found"
        )

    workflow.get_task_from_id(task_id=task.id)._set_internal_data(
        **{INTERNAL_DATA_KEY_ASSIGNED_USER: str(user_id)}
    )
    

def set_allow_unassign(workflow: BpmnWorkflow, task_id: uuid.UUID):
    workflow.get_task_from_id(task_id=task_id)._set_internal_data(
        **{INTERNAL_DATA_KEY_ALLOW_UNASSIGN: True}
    )


def can_be_unassigned(workflow: BpmnWorkflow, task_id: uuid.UUID):
    return workflow.get_task_from_id(task_id=task_id)._get_internal_data(
        INTERNAL_DATA_KEY_ALLOW_UNASSIGN, False
    )

def _get_custom_props(task):
    custom_props = getattr(task.task_spec, "custom_props", {})
    return custom_props

def can_user_cancel_workflow(workflow: BpmnWorkflow, task_id: uuid.UUID, user_id: uuid.UUID):
    task = workflow.get_task_from_id(task_id=task_id)
    return task is not None and task.has_state(TaskState.READY) and _get_custom_props(task).get("can_user_cancel_workflow", None) == "1" and is_assigned_to_task(workflow=workflow, task_id=task_id, user_id=user_id)

def can_user_delete_workflow(workflow: BpmnWorkflow, task_id: uuid.UUID, user_id: uuid.UUID):
    task = workflow.get_task_from_id(task_id=task_id)
    return task is not None and task.has_state(TaskState.READY) and _get_custom_props(task).get("can_user_delete_workflow", None) == "1" and is_assigned_to_task(workflow=workflow, task_id=task_id, user_id=user_id)

def unassign_task(workflow: BpmnWorkflow, task_id: uuid.UUID):
    """Unassign a user from a task"""
    if can_be_unassigned(workflow=workflow, task_id=task_id):
        task: Task = workflow.get_task_from_id(task_id)
        task._set_internal_data(**{INTERNAL_DATA_KEY_ASSIGNED_USER: None})
    else:
        raise TaskCannotBeUnassignedException()


def unassign_task_without_checks(workflow: BpmnWorkflow, task_id: uuid.UUID):
    """Unassign a user from a task"""
    task: Task = workflow.get_task_from_id(task_id)
    task._set_internal_data(**{INTERNAL_DATA_KEY_ASSIGNED_USER: None})


def is_initiator_lane(workflow: BpmnWorkflow, lane_name: str | None) -> bool:
    is_initiator_lane = False
    if lane_name is not None:
        lane_mapping = get_lane_mapping(workflow=workflow)
        initiator_property= lane_mapping.get(lane_name, {}).get("initiator", False) 
        is_initiator_lane = (
            initiator_property is not False and initiator_property is not None
        )
    return is_initiator_lane


def get_manually_assigned_roles(task: Task) -> set[str] | None:
    roles = task._get_internal_data(INTERNAL_DATA_KEY_ASSIGNED_ROLES)
    if roles is not None:
        roles = set(roles)
    return roles


def set_manually_assigned_roles(
    workflow: BpmnWorkflow, task_id: uuid.UUID, roles: set[str]
) -> str | None:
    task = workflow.get_task_from_id(task_id)
    task._set_internal_data(**{INTERNAL_DATA_KEY_ASSIGNED_ROLES: list(roles)})


def get_task_roles(workflow: BpmnWorkflow, task_id: uuid.UUID) -> set[str]:
    task: Task = workflow.get_task_from_id(task_id=task_id)
    task_spec: BpmnTaskSpec = task.task_spec
    roles = set()
    manually_assigned_roles = get_manually_assigned_roles(task)
    if manually_assigned_roles is not None:
        roles: set[str] = set(manually_assigned_roles)
    elif task_spec.lane is not None:
        lane_mapping = get_lane_mapping(workflow=workflow)
        roles: set[str] = set(lane_mapping.get(task_spec.lane, {}).get("roles", set()))
    return roles


def auto_assign_all_tasks_in_initiator_lane(workflow: BpmnWorkflow):
    """Automatically assigns all possible open usertasks to the initiator"""
    tasks = get_ready_and_waiting_usertasks(workflow=workflow)
    for task in tasks:
        task_spec: BpmnTaskSpec = task.task_spec
        if is_initiator_lane(workflow=workflow, lane_name=task_spec.lane):
            created_by_id: uuid.UUID | None = get_created_by_id(workflow=workflow)
            if created_by_id:
                assign_task_without_checks(workflow=workflow, task_id=task.id, user_id=created_by_id)


def cleanup_hidden_fields_for_ready_tasks(workflow: BpmnWorkflow):
    """Ensure ready tasks do not expose values of currently hidden form fields."""

    tasks = get_ready_and_waiting_usertasks(workflow=workflow)
    options_folder = workflow_providers.get_workflow_directory(workflow.spec.name) / "options"
    functions_env = _get_workflow_functions_env(workflow.spec.name)
    for task in tasks:
        form_spec = get_react_json_schema_form_data(task=task)
        if form_spec is None:
            continue

        task_data = task.data
        if not isinstance(task_data, dict) or not task_data:
            continue

        cleaned = validate_task_data(
            form=form_spec,
            task_data=task_data,
            options_folder=options_folder,
            functions_env=functions_env,
            preserve_unknown_fields=True,
            preserve_disabled_fields=True,
            log_validation_errors=False
        ).task_data

        task.data.clear()
        task.data.update(cleaned)


class LaneMappingSchema(BaseModel):
    initiator: bool | list[str] | None = Field(default=None)
    roles: List[str] = Field(default_factory=list)


def get_lane_mapping(workflow: BpmnWorkflow) -> dict[str, dict]:
    wflanes = workflow.spec.wflanes
    mapping = {}
    for lane in wflanes.values():
        # get "roles" extension property. If "roles" is missing we use "" as default value,
        # if user configured "roles", but left the entry empty we get None. We will treat this as error
        lane_config = lane.get("custom_properties",{}).get("roles","")
        if lane_config is None:
            raise Exception((f"'roles' configured, but left empty in lane {lane['id']}"))

        role_list = [r.strip() for r in lane_config.split(",")] # create list of strings and strip all spaces
        role_list = [r for r in role_list if r != ""] # remove empty-string entries, so it's either an empty list [] or list of non-empty strings
        mapping[lane["name"]] = LaneMappingSchema(
            roles=role_list,
            initiator=boolean_or_string_list(lane.get("custom_properties",{}).get("initiator",None))
        ).model_dump()
    return mapping


def get_options_for_property(
    workflow: BpmnWorkflow, task_id: uuid.UUID, property_path: list[str], form_data: dict|None,
) -> list[tuple[str, str]]:
    options_folder = workflow_providers.get_workflow_directory(workflow.spec.name) / "options"
    functions_env = _get_workflow_functions_env(workflow.spec.name)
    task: Task = workflow.get_task_from_id(task_id)
    formdata = get_react_json_schema_form_data(task=task)
    if formdata is None:
        raise FormNotFoundException()
    jsonschema = formdata.jsonschema

    data = get_options(
        jsonschema=jsonschema, property_path=property_path, options_folder=options_folder, form_data=form_data, functions_env=functions_env
    )

    return data


def get_options_detailed_for_property(
    workflow: BpmnWorkflow, task_id: uuid.UUID, property_path: list[str], form_data: dict|None
) -> dict[str, dict[str, Any]]:
    options_folder = workflow_providers.get_workflow_directory(workflow.spec.name) / "options"
    functions_env = _get_workflow_functions_env(workflow.spec.name)
    task: Task = workflow.get_task_from_id(task_id)
    formdata = get_react_json_schema_form_data(task=task)
    if formdata is None:
        raise FormNotFoundException()

    data = get_options_detailed(
        jsonschema=formdata.jsonschema,
        property_path=property_path,
        options_folder=options_folder,
        form_data=form_data,
        functions_env=functions_env
    )

    return data


def replace_task_data(workflow: BpmnWorkflow, task_id: uuid.UUID, task_data: dict):
    task: Task = workflow.get_task_from_id(task_id)
    task.data = task_data


def execute_erroneous_task(workflow: BpmnWorkflow, task_id: uuid.UUID):
    """Runs a task, afterwards proceeds with run_workflow"""
    task: Task = workflow.get_task_from_id(task_id)
    if not task.has_state(TaskState.ERROR):
        raise TaskIsNotErroneousException()
    set_stacktrace(
        workflow=workflow, task_id=task_id, stacktrace=None
    )  # reset stacktrace
    success = task.run()
    if not success:
        return False
    return run_workflow(workflow=workflow)


def get_stacktrace(workflow: BpmnWorkflow, task_id: uuid.UUID) -> str | None:
    task: Task = workflow.get_task_from_id(task_id)
    return task._get_internal_data(INTERNAL_DATA_KEY_STACKTRACE, None)


def set_stacktrace(workflow: BpmnWorkflow, task_id: uuid.UUID, stacktrace: str | None):
    task: Task = workflow.get_task_from_id(task_id)
    task._set_internal_data(**{INTERNAL_DATA_KEY_STACKTRACE: stacktrace})


def cancel_workflow(workflow: BpmnWorkflow):
    workflow.cancel()


def get_message_triggers(name: str) -> list[str]:
    """Load a process from files, parse it and return message names which can start this process"""
    parser = get_parser()
    folder = workflow_providers.get_workflow_directory(name)
    bpmn_files = [str(x.absolute()) for x in folder.glob("*.bpmn") if x.is_file()]
    dmn_files = [str(x.absolute()) for x in folder.glob("*.dmn") if x.is_file()]
    parser.add_bpmn_files(bpmn_files)
    if dmn_files:
        parser.add_dmn_files(dmn_files)

    process_parser: ProcessParser|None = parser.get_process_parser(name)
    message_names: list[str] = []

    if process_parser is not None and isinstance(process_parser, ProcessParser):
        message_names = process_parser.start_messages()

    return message_names


def get_workflows_to_trigger_by_start_message(message_name: str, user: UserRepresentation):
    workflow_names = []
    for workflow_name in get_allowed_workflow_names_to_start(user=user):
        messages = get_message_triggers(workflow_name)
        if message_name in messages:
            workflow_names.append(workflow_name)

    return workflow_names


def update_task_data(workflow: BpmnWorkflow, task_id: uuid.UUID, cleaned_task_data: dict):
    """Copies provided task_data directly to the task. This is used e.g. in the copy-workflow use-case."""
    update(workflow.tasks[task_id].data, cleaned_task_data)


# Domain outcome for a single processed time event
@dataclass(frozen=True)
class TimeEventResult:
    outcome: Literal["completed", "reschedule", "cancelled", "noop"]
    next_due: datetime.datetime | None = None
    remaining_cycles: int | None = None
    note: str | None = None

def _first_timer_def(task) -> TimerEventDefinition | None:
    ed = getattr(task.task_spec, "event_definition", None)
    if isinstance(ed, TimerEventDefinition):
        return ed
    return None

def process_single_time_event(workflow: BpmnWorkflow, wte_record: TimeEvent) -> TimeEventResult:
    """
    execute a single due time event inside 'workflow'.
    No database I/O here; caller persists workflow and timer record.
    """
    # Locate task
    task = next((t for t in workflow.get_tasks() if t.id == wte_record.timer_task_id), None)
    if task is None or task.state != TaskState.WAITING:
        return TimeEventResult(outcome="cancelled", note="Task not waiting or not found")

    ed = _first_timer_def(task)
    if ed is None:
        return TimeEventResult(outcome="cancelled", note="No timer definition")

    # One-shot timers (date/duration)
    if isinstance(ed, (TimeDateEventDefinition, DurationTimerEventDefinition)):
        fired = ed.has_fired(task)
        if not fired:
            # Not due anymore; scheduling will be recomputed by repository sync after store.
            return TimeEventResult(outcome="noop", note="Not due anymore")
        task.task_spec._update(task)
        run_workflow(workflow=workflow)
        return TimeEventResult(outcome="completed")

    # Cycle (non-interrupting)
    if isinstance(ed, CycleTimerEventDefinition):
        fired_any = False
        while ed.cycle_complete(task):
            ed.update_task(task)
            fired_any = True

        if fired_any:
            run_workflow(workflow=workflow)

        # Determine next occurrence (or completion) directly from internal data
        ev = task._get_internal_data("event_value")
        if not ev or (isinstance(ev.get("cycles"), int) and ev["cycles"] == 0):
            return TimeEventResult(outcome="completed")

        # Parse next ISO instant to UTC
        next_iso = ev.get("next")
        if not next_iso:
            return TimeEventResult(outcome="completed")
        next_due = datetime.datetime.fromisoformat(next_iso).astimezone(datetime.timezone.utc)
        remaining = int(ev.get("cycles", -1))
        return TimeEventResult(outcome="reschedule", next_due=next_due, remaining_cycles=remaining)

    # Fallback: avoid stuck records on unexpected types
    return TimeEventResult(outcome="completed", note="Unexpected timer type")
