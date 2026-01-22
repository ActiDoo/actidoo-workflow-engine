# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

import datetime
import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from actidoo_wfe.helpers.schema import PaginatedDataSchema


class InlineUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str | None = Field(default_factory=lambda: None)
    username: str | None = Field(default_factory=lambda: None)
    email: str | None = Field(default_factory=lambda: None)


class InlineUserAdminResponse(InlineUserResponse):
    first_name: str | None = Field(default_factory=lambda: None)
    last_name: str | None = Field(default_factory=lambda: None)
    is_service_user: bool | None = Field(default_factory=lambda: None)
    created_at: datetime.datetime | None = Field(default=None)
    roles: list[str] = Field(default_factory=list)


class InlineWorkflowInstance(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    title: str
    subtitle: str | None
    is_completed: bool
    created_at: datetime.datetime
    completed_at: datetime.datetime | None
    created_by: InlineUserResponse


class GetAllTasksResponseItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    title: str
    id: uuid.UUID
    lane: str | None
    lane_roles: list[str] | None
    lane_initiator: bool
    jsonschema: dict | None
    uischema: dict | None
    assigned_user: Optional["InlineUserResponse"]
    assigned_delegate_user: Optional["InlineUserResponse"]
    triggered_by: Optional["InlineUserResponse"]
    completed_by_user: Optional["InlineUserResponse"]
    completed_by_delegate_user: Optional["InlineUserResponse"]
    delegate_submit_comment: str | None = Field(default=None)
    can_be_unassigned: bool
    data: dict | list | None
    state_ready: bool
    state_completed: bool
    state_error: bool
    state_cancelled: bool
    created_at: datetime.datetime
    completed_at: datetime.datetime | None
    workflow_instance: InlineWorkflowInstance
    error_stacktrace: str | None


GetAllTasksResponse = PaginatedDataSchema[GetAllTasksResponseItem]

class GetSingleTaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    task: GetAllTasksResponseItem

class GetAllWorkflowInstancesResponseItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    title: str
    subtitle: str | None = Field(default_factory=lambda: None)
    is_completed: bool
    has_task_in_error_state: bool
    created_by: InlineUserResponse
    created_at: datetime.datetime


GetAllWorkflowInstancesResponse = PaginatedDataSchema[
    GetAllWorkflowInstancesResponseItem
]


class ReplaceTaskDataRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    task_id: uuid.UUID
    data: dict


#class ReplaceTaskDataResponse(BaseModel):
#    model_config = ConfigDict(from_attributes=True)


class ExecuteErroneousTaskRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    task_id: uuid.UUID


class DownloadAttachmentRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    task_id: uuid.UUID
    hash: str


class SearchUsersRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    search: str = Field(default_factory=lambda: "")
    include_value: str | None = Field(default_factory=lambda: None)


class SearchUsersResponseItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    value: uuid.UUID
    label: str


class SearchUsersResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    options: list["SearchUsersResponseItem"]


class AssignUserRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    task_id: uuid.UUID
    user_id: uuid.UUID


#class AssignUserResponse(BaseModel):
#    model_config = ConfigDict(from_attributes=True)


class UnassignUserRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    task_id: uuid.UUID


#class UnassignUserResponse(BaseModel):
#    model_config = ConfigDict(from_attributes=True)


class CancelWorkflowInstanceRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    workflow_instance_id: uuid.UUID


class CancelWorkflowInstanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class GetSystemInformationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    build_number: str = Field(default_factory=lambda: "dev")


class GetAllUsersResponseItem(InlineUserAdminResponse):
    pass


GetAllUsersResponse = PaginatedDataSchema[GetAllUsersResponseItem]


class GetUserDetailRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID


class DelegationInput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    delegate_user_id: uuid.UUID
    valid_until: datetime.datetime | None


class SetUserDelegationsRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    delegations: list["DelegationInput"] = Field(default_factory=list)


class UserDelegationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    delegate: InlineUserResponse
    valid_until: datetime.datetime | None


class GetUserDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user: InlineUserAdminResponse
    delegations: list["UserDelegationResponse"] = Field(default_factory=list)
