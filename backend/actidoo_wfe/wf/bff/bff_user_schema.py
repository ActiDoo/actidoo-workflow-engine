# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

import datetime
import uuid
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from actidoo_wfe.helpers.schema import PaginatedDataSchema

# class OperationStatus(enum.Enum):
#    SUCCESS = "success"
#    ERROR = "error"


class ErrorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    message: str


class StartWorkflowRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    data: dict | None = Field(default=None)


class StartWorkflowResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    workflow_instance_id: uuid.UUID


class StartWorkflowWithDataRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    data: dict | None = Field(default=None)

class GetWorkflowCopyDataResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    workflow_name: str
    task_name: str
    data: dict

class SubmitTaskDataErrorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    error_schema: dict

class GetUserTasksResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    usertasks: List["GetUserTasksResponseUserTasks"]


class GetUserTasksResponseUserTasks(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    title: str
    id: uuid.UUID
    jsonschema: dict
    uischema: dict
    lane: Optional[str]
    assigned_user: Optional["InlineUserResponse"]
    assigned_to_me: bool
    assigned_delegate_user: Optional["InlineUserResponse"]
    assigned_to_me_as_delegate: bool
    can_be_assigned_as_delegate: bool
    can_be_unassigned: bool
    can_cancel_workflow: bool
    can_delete_workflow: bool
    state_completed: bool
    data: dict | list | None
    completed_by_user: Optional["InlineUserResponse"]
    completed_by_delegate_user: Optional["InlineUserResponse"]
    delegate_submit_comment: str | None = Field(default=None)


class StartWorkflowWithDataResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    title: str
    subtitle: str | None = Field(default_factory=lambda: None)
    task: Optional[GetUserTasksResponseUserTasks]


class GetWorkflowInstancesResponseItemTask(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    title: str
    assigned_user: Optional["InlineUserResponse"]
    assigned_delegate_user: Optional["InlineUserResponse"]
    completed_by_user: Optional["InlineUserResponse"]
    completed_by_delegate_user: Optional["InlineUserResponse"]
    delegate_submit_comment: str | None = Field(default=None)
    can_be_assigned_as_delegate: bool


class GetWorkflowInstancesResponseItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    title: str
    subtitle: str | None = Field(default_factory=lambda: None)
    is_completed: bool
    created_at: datetime.datetime
    completed_at: datetime.datetime | None
    active_tasks: list[GetWorkflowInstancesResponseItemTask] = Field(
        default_factory=lambda: []
    )
    completed_tasks: list[GetWorkflowInstancesResponseItemTask] = Field(
        default_factory=lambda: []
    )


GetWorkflowInstancesResponse = PaginatedDataSchema[GetWorkflowInstancesResponseItem]


class GetWorkflowsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    workflows: list["GetWorkflowsResponseItem"]


class GetWorkflowsResponseItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    title: str

class GetWorkflowStatisticsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    workflows: list["GetWorkflowStatisticsResponseItem"]


class GetWorkflowStatisticsResponseItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    title: str

    active_instances: int
    completed_instances: int
    estimated_saved_mins_per_instance: int
    estimated_instances_per_year: int
    estimated_savings_per_year: float

    @field_validator("estimated_savings_per_year", mode="before")
    def round_estimated_savings(cls, value):
        return round(float(value), 2)


class AssignTaskToMeRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    task_id: uuid.UUID


class AssignTaskToMeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class InlineUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str | None = Field(default_factory=lambda: None)
    username: str | None = Field(default_factory=lambda: None)
    email: str | None = Field(default_factory=lambda: None)


class SearchPropertyOptionsRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    task_id: uuid.UUID
    property_path: list[str]
    search: str = Field(default_factory=lambda: "")
    include_value: str | list[str] | None = Field(default_factory=lambda: None)
    form_data: dict | None = Field(default_factory=lambda: None)


class SearchPropertyOptionsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    options: list["SearchPropertyOptionsResponseItem"]


class SearchPropertyOptionsResponseItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    value: str
    label: str


class DownloadAttachmentRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    task_id: uuid.UUID
    hash: str


class GetMyWfeUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str | None = Field(default_factory=lambda: None)
    email: str
    workflows_the_user_is_admin_for: list[str] = Field(default_factory=lambda: [])


class RefreshGetWorkflowSpecRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    name: str
    #version: int|None = Field(default=None)


class WorkflowSpecResponseFile(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime.datetime
    file_name: str
    file_type: str
    file_hash: str
    file_content: str|None
    file_bpmn_process_id: str


class WorkflowSpecResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: uuid.UUID
    created_at: datetime.datetime
    name: str
    version: int
    files: list[WorkflowSpecResponseFile]


class CancelWorkflowRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    task_id: uuid.UUID


class CancelWorkflowResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class DeleteWorkflowRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    task_id: uuid.UUID


class DeleteWorkflowResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

class SaveUserSettingsRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    locale: str
    delegations: List["UserDelegationRequest"] | None = Field(default=None)

class LocaleItem(BaseModel):
    key: str
    label: str

class UserSettingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    locale: str
    supported_locales: List[LocaleItem]
    delegations: List["UserDelegationResponse"]


class UserDelegationRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    delegate_user_id: uuid.UUID
    valid_until: datetime.datetime | None = Field(default=None)


class UserDelegationResponse(UserDelegationRequest):
    delegate: "InlineUserResponse"


for x in list(globals().values()):
    try:
        x.model_rebuild()
    except Exception:
        pass
