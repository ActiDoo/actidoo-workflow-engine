import dataclasses
import datetime
import uuid
from typing import Any, List, NamedTuple, Optional, Dict, Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_serializer
from SpiffWorkflow.task import Task
from actidoo_wfe.settings import settings

class UserRepresentation(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    email: str | None
    first_name: str | None
    last_name: str | None
    roles: set[str]
    is_service_user: bool
    locale: str = Field(default=settings.default_locale)
    
    def is_same(self, other: Optional["UserRepresentation"]) -> bool:
        return other is not None and other.id == self.id

    @computed_field
    @property
    def full_name(self) -> str:
        if self.first_name is not None and self.last_name is not None:
            return self.first_name + " " + self.last_name
        elif self.email:
            return self.email
        else:
            return self.username

    # For storing the user inside the workflow, we need to convert uuids to str when calling dict()
    @field_serializer("id")
    def serialize_id(self, id: uuid.UUID, _info):
        return str(id)

    @field_serializer("roles")
    def serialize_roles(self, roles: set[str], _info):
        return list(roles)

class InlineUserRepresentation(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    first_name: str | None = Field(default_factory=lambda: None)
    last_name: str | None = Field(default_factory=lambda: None)
    email: str|None
    is_service_user: bool = Field(default_factory=lambda: False)

    @property
    def full_name(self):
        if self.first_name is not None and self.last_name is not None:
            return self.first_name + " " + self.last_name
        else:
            return self.email


class UserTaskWithoutNestedAssignedUserRepresentation(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    title: str
    id: uuid.UUID
    lane: str | None
    lane_initiator: bool
    jsonschema: dict | None
    uischema: dict | None
    assigned_user_id: uuid.UUID | None
    assigned_to_me: bool
    can_be_unassigned: bool
    can_cancel_workflow: bool
    can_delete_workflow: bool
    state_completed: bool
    data: dict | list | None

class UserTaskRepresentation(UserTaskWithoutNestedAssignedUserRepresentation):
    model_config = ConfigDict(from_attributes=True)
    assigned_user: UserRepresentation | None
    

class ReactJsonSchemaFormData(NamedTuple):
    jsonschema: dict
    uischema: dict


class WorkflowInstanceTaskInlineRepresentation(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    title: str
    assigned_user: InlineUserRepresentation | None


class WorkflowInstanceRepresentation(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    title: str
    subtitle: str | None = Field(default_factory=lambda: None)
    is_completed: bool
    active_tasks: list[WorkflowInstanceTaskInlineRepresentation] = Field(
        default_factory=lambda: []
    )
    completed_tasks: list[WorkflowInstanceTaskInlineRepresentation] = Field(
        default_factory=lambda: []
    )
    completed_at: datetime.datetime | None = Field(default=None)
    created_at: datetime.datetime
    created_by: InlineUserRepresentation
    has_task_in_error_state: bool


class WorkflowInstanceWithoutTasksRepresentation(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    title: str
    subtitle: str | None = Field(default_factory=lambda: None)
    is_completed: bool
    completed_at: datetime.datetime | None = Field(default=None)
    created_at: datetime.datetime
    created_by: InlineUserRepresentation
    has_task_in_error_state: bool


class WorkflowRepresentation(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    title: str


class WorkflowPreviewRepresentation(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    title: str
    subtitle: str | None = Field(default=None)

    task: UserTaskRepresentation | None
    

class WorkflowCopyInstruction(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    workflow_name: str
    task_name: str
    data: dict

class WorkflowStatisticsRepresentation(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    title: str
    
    active_instances: int | None = Field(default=None)
    completed_instances: int | None = Field(default=None)
    estimated_saved_mins_per_instance: int | None = Field(default=None)
    estimated_instances_per_year: int | None = Field(default=None)
    estimated_savings_per_year: float | None = Field(default=None)

class UploadedAttachmentRepresentation(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    hash: str
    filename: str
    mimetype: str | None

    @field_serializer("id")
    def serialize_id(self, id: uuid.UUID, _info):
        return str(id)


@dataclasses.dataclass
class Attachment:
    id: uuid.UUID
    hash: str
    filename: str
    mimetype: str | None
    data: bytes


class WorkflowInstanceTaskAdminRepresentation(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    title: str
    id: uuid.UUID
    lane: str | None
    lane_roles: list[str] | None  # new
    lane_initiator: bool
    jsonschema: dict | None
    uischema: dict | None
    assigned_user: InlineUserRepresentation | None
    triggered_by: InlineUserRepresentation | None
    can_be_unassigned: bool
    data: dict | list | None
    state_ready: bool
    state_completed: bool
    state_error: bool
    state_cancelled: bool
    created_at: datetime.datetime = Field(default=None)
    completed_at: datetime.datetime | None = Field(default=None)
    workflow_instance: WorkflowInstanceWithoutTasksRepresentation  # new
    error_stacktrace: str | None = Field(default=None)


TaskToUserMapping = dict[Task, uuid.UUID]

class WorkflowSpecFileRepresentation(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime.datetime
    file_name: str
    file_type: str
    file_hash: str
    file_content: str|None
    file_bpmn_process_id: str

class WorkflowSpecRepresentation(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: uuid.UUID
    created_at: datetime.datetime
    name: str
    version: int
    files: list[WorkflowSpecFileRepresentation]


class MessageEventDefinitionRepresentation(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    name: str
    event_type: str
    value: Any

class MessageSubscriptionRepresentation(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    correlation_key: str
    workflow_instance_task_id: uuid.UUID

class TaskState(BaseModel):
    title: str
    ready_counter: int
    error_counter: int

class WorkflowStateResponse(BaseModel):
    workflow_name: str
    tasks: Dict[str, TaskState]

class TimeEvent(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    workflow_instance_id: uuid.UUID
    timer_task_id: uuid.UUID
    timer_kind: Literal["time_date", "time_duration", "time_cycle"]
    due_at: datetime.datetime
    interrupting: bool
    remaining_cycles: int | None = Field(default=None)
    expression: str | None = Field(default=None)

class ReducedWorkflowState(BaseModel):
    id: uuid.UUID
    created_at: datetime.datetime
    title: str
    name: str


class ReducedWorkflowInstanceResponse(BaseModel):
    ITEMS: List[ReducedWorkflowState]
