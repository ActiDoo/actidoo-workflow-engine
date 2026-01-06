# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

import logging
import os
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Response
from sqlalchemy.orm import Session

import actidoo_wfe.helpers.bff_table as bff_table
import actidoo_wfe.wf.service_application as service_application
from actidoo_wfe.database import get_db
from actidoo_wfe.helpers.http import streaming_response_with_filecontent
from actidoo_wfe.helpers.schema import PaginatedDataSchema
from actidoo_wfe.wf import views
from actidoo_wfe.wf.bff.bff_admin_schema import (
    AssignUserRequest,
    CancelWorkflowInstanceRequest,
    CancelWorkflowInstanceResponse,
    DownloadAttachmentRequest,
    ExecuteErroneousTaskRequest,
    GetAllTasksResponse,
    GetAllWorkflowInstancesResponse,
    GetSingleTaskResponse,
    GetSystemInformationResponse,
    ReplaceTaskDataRequest,
    SearchUsersRequest,
    SearchUsersResponse,
    SearchUsersResponseItem,
    UnassignUserRequest,
)
from actidoo_wfe.wf.bff.deps import get_user
from actidoo_wfe.wf.cross_context.imports import require_realm_role
from actidoo_wfe.wf.exceptions import UserMayNotAdministrateThisWorkflowException
from actidoo_wfe.wf.models import WorkflowUser
from actidoo_wfe.wf.service_user import search_users
from actidoo_wfe.wf.types import Attachment, ReducedWorkflowInstanceResponse, WorkflowInstanceRepresentation, WorkflowInstanceTaskAdminRepresentation, WorkflowStateResponse

log = logging.getLogger(__name__)

router = APIRouter(
     # fine-grained authorization in functions
    dependencies=[Depends(require_realm_role("wf-user"))],
    tags=["wfe-bff-admin"]
)


AdminWorkflowInstanceTasksBffTableQuerySchema = bff_table.get_bff_table_query_schema(
    schema_name="AdminWorkflowInstanceTasksBffTableQuerySchema",
    sorting_fields=[
        "id",
        "name",
        "title",
        "created_at",
        "completed_at",
        "state_ready",
        "state_completed",
        "state_error",
        "state_cancelled",
        "workflow_instance___id",
        "workflow_instance___title",
        "workflow_instance___subtitle",
        "lane",
        "sort"
    ],
    filter_fields=[
        bff_table.UUidSearchFilterField(name="id"),
        bff_table.TextSearchFilterField(name="name"),
        bff_table.TextSearchFilterField(name="title"),
        bff_table.DatetimeSearchFilterField(name="created_at"),
        bff_table.DatetimeSearchFilterField(name="completed_at"),
        bff_table.BooleanFilterField(name="state_ready"),
        bff_table.BooleanFilterField(name="state_completed"),
        bff_table.BooleanFilterField(name="state_error"),
        bff_table.BooleanFilterField(name="state_cancelled"),
        bff_table.UUidSearchFilterField(name="workflow_instance___id"),
        bff_table.TextSearchFilterField(name="workflow_instance___title"),
        bff_table.TextSearchFilterField(name="workflow_instance___subtitle"),
        bff_table.TextSearchFilterField(name="lane"),
        bff_table.TextSearchFilterField(name="assigned_user___full_name"),
        # bff_table.BooleanFilterField(name="is_completed")
    ],
    add_global_search_filter=True,
)


@router.post("/all_tasks", name="bff_admin_get_all_tasks")
def get_all_tasks(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[WorkflowUser, Depends(get_user)],
    bff_table_request_params: Annotated[
        bff_table.BffTableQuerySchemaBase,
        Depends(AdminWorkflowInstanceTasksBffTableQuerySchema),
    ],  # type: ignore
) -> GetAllTasksResponse:
    """
    Retrieve all tasks with pagination for the given user.

    This endpoint allows users to fetch a paginated list of tasks based on the
    provided request parameters. All users can access this endpoint, but for
    'non-admin and non-wf-owner' users, the task list will be empty.
    The request should contain valid filtering and sorting criteria.

    Args:
        db (Session): The database session dependency for querying the database.
        user (WorkflowUser): The authenticated user requesting the task data.
        bff_table_request_params (BffTableQuerySchemaBase): Parameters for
            pagination and filtering of tasks.

    Returns:
        GetAllTasksResponse: A response containing the paginated list of tasks.
    """

    tasks: PaginatedDataSchema[
        WorkflowInstanceTaskAdminRepresentation
    ] = service_application.bff_admin_get_all_tasks(
        db=db, user_id=user.id, bff_table_request_params=bff_table_request_params
    )

    return GetAllTasksResponse.model_validate(tasks)


@router.post("/statistics_information", name="bff_admin_get_statistics_information")
def get_statistic_information(
    db: Annotated[Session, Depends(get_db)],
) -> ReducedWorkflowInstanceResponse:
    """
    Used by the Frontend Graph and similar to "all_workflow_instances",
    but without the function get_paginated_data() in `views.py`,
    because this caused high loading times, which were unacceptable for the Graph.
    """
    result = service_application.admin_get_statistics_graph_timestamps(db=db)
    return result


AdminWorkflowInstancesBffTableQuerySchema = bff_table.get_bff_table_query_schema(
    schema_name="AdminWorkflowInstancesBffTableQuerySchema",
    sorting_fields=[
        "id",
        "name",
        "title",
        "subtitle",
        "created_at",
        "is_completed",
        "has_task_in_error_state",
        "created_by___full_name",
    ],
    filter_fields=[
        bff_table.UUidSearchFilterField(name="id"),
        bff_table.TextSearchFilterField(name="name"),
        bff_table.TextSearchFilterField(name="title"),
        bff_table.TextSearchFilterField(name="subtitle"),
        bff_table.TextSearchFilterField(name="created_by___full_name"),
        bff_table.DatetimeSearchFilterField(name="created_at"),
        bff_table.BooleanFilterField(name="is_completed"),
        bff_table.BooleanFilterField(name="has_task_in_error_state"),
    ],
    add_global_search_filter=True,
)


@router.post("/all_workflow_instances", name="bff_admin_get_all_workflow_instances")
def get_all_workflow_instances(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[WorkflowUser, Depends(get_user)],
    bff_table_request_params: Annotated[
        bff_table.BffTableQuerySchemaBase,
        Depends(AdminWorkflowInstancesBffTableQuerySchema),
    ],  # type: ignore
) -> GetAllWorkflowInstancesResponse:
    """
    Retrieve all workflow instances with pagination for the given user.

    This endpoint allows users to fetch a paginated list of workflow instances
    based on the provided request parameters. All users can access this endpoint,
    but for 'non-admin and non-wf-owner' users, the list of workflow instances will be empty.
    The request should contain valid filtering and sorting criteria.

    Args:
        db (Session): The database session dependency for querying the database.
        user (WorkflowUser): The authenticated user requesting the workflow instance data.
        bff_table_request_params (BffTableQuerySchemaBase): Parameters for pagination
            and filtering of workflow instances.

    Returns:
        GetAllWorkflowInstancesResponse: A response containing the paginated list of
            workflow instances.
    """
    tasks: PaginatedDataSchema[WorkflowInstanceRepresentation] = service_application.bff_admin_get_all_workflow_instances(
        db=db, user_id=user.id, bff_table_request_params=bff_table_request_params
    )

    return GetAllWorkflowInstancesResponse.model_validate(tasks)


@router.post("/replace_task_data", name="bff_admin_replace_task_data")
def replace_task_data(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[WorkflowUser, Depends(get_user)],
    req_data: Annotated[ReplaceTaskDataRequest, Body()],
) -> GetSingleTaskResponse:
    
    try:
        service_application.admin_replace_task_data(
            db=db, user_id=user.id, task_id=req_data.task_id, task_data=req_data.data
        )
        task = service_application.admin_get_single_task(db=db, user_id=user.id, task_id=req_data.task_id)
        return GetSingleTaskResponse.model_validate(dict(task=task))
    except UserMayNotAdministrateThisWorkflowException as ex:
        log.exception(f"User {user.username} is not allowed to call replace_task_data for task_id {req_data.task_id}")
        raise HTTPException(status_code=403)
        

@router.post("/execute_erroneous_task", name="bff_admin_execute_erroneous_task")
def execute_erroneous_task(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[WorkflowUser, Depends(get_user)],
    req_data: Annotated[ExecuteErroneousTaskRequest, Body()],
) -> GetAllTasksResponse:
    
    try:
        workflow_instance_id = service_application.admin_execute_erroneous_task(
            db=db, user_id=user.id, task_id=req_data.task_id
        )

        tasks = service_application.bff_admin_get_all_tasks(
            db=db,
            user_id=user.id,
            bff_table_request_params=AdminWorkflowInstanceTasksBffTableQuerySchema.validate(
                {"f_workflow_instance_id": str(workflow_instance_id)}
            )
        )

        return GetAllTasksResponse.model_validate(tasks)
    except UserMayNotAdministrateThisWorkflowException as ex:
        log.exception(f"User {user.username} is not allowed to call execute_erroneous_task for task_id {req_data.task_id}")
        raise HTTPException(status_code=403)

@router.post("/download_attachment", name="bff_admin_download_attachment")
def download_attachment(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[WorkflowUser, Depends(get_user)],
    reqdata: DownloadAttachmentRequest
) -> Response:
    
    attachment: Attachment = service_application.download_attachment(
        db=db, task_id=reqdata.task_id, hash=reqdata.hash
    )

    return streaming_response_with_filecontent(
        binary=attachment.data,
        filename=attachment.filename,
        mimetype=attachment.mimetype,
    )


@router.post("/search_wf_users", name="bff_admin_search_wf_users")
def search_wf_users(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[WorkflowUser, Depends(get_user)],
    search_options: SearchUsersRequest
) -> SearchUsersResponse:

    options = search_users(
        db=db, search=search_options.search, include_value=search_options.include_value
    )

    return SearchUsersResponse(
        options=[
            SearchUsersResponseItem(
                value=option.id,
                label=f"{option.first_name} {option.last_name} ({option.username})",
            )
            for option in options
        ]
    )


# assign user


@router.post("/assign_task", name="bff_admin_assign_task")
def assign_user(
    db: Annotated[Session, Depends(get_db)], 
    user: Annotated[WorkflowUser, Depends(get_user)],
    reqdata: AssignUserRequest
) -> GetSingleTaskResponse:
    try:
        service_application.admin_assign_task_to_user_without_checks(
            db=db, admin_user_id=user.id, assign_to_user_id=reqdata.user_id, task_id=reqdata.task_id, remove_roles=False
        )
        task = views.admin_get_single_task(db=db, task_id=reqdata.task_id)
        return GetSingleTaskResponse.model_validate(dict(task=task))
    except UserMayNotAdministrateThisWorkflowException as ex:
        log.exception(f"User {user.username} is not allowed to call assign_user for task_id {reqdata.task_id}")
        raise HTTPException(status_code=403)
    

@router.post("/unassign_task", name="bff_admin_unassign_task")
def unassign_task(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[WorkflowUser, Depends(get_user)],
    reqdata: UnassignUserRequest,
) -> GetSingleTaskResponse:
    
    try:
        service_application.admin_unassign_task_without_checks(db=db, admin_user_id=user.id, task_id=reqdata.task_id)
        task = views.admin_get_single_task(db=db, task_id=reqdata.task_id)
        return GetSingleTaskResponse.model_validate(dict(task=task))
    except UserMayNotAdministrateThisWorkflowException as ex:
        log.exception(f"User {user.username} is not allowed to call unassign_task for task_id {reqdata.task_id}")
        raise HTTPException(status_code=403)
    

# cancel workflow


@router.post("/cancel_workflow_instance", name="bff_admin_cancel_workflow_instance")
def cancel_workflow_instance(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[WorkflowUser, Depends(get_user)],
    reqdata: CancelWorkflowInstanceRequest,
) -> CancelWorkflowInstanceResponse:
    
    try:
        service_application.admin_cancel_workflow(
            db=db, user_id=user.id, workflow_instance_id=reqdata.workflow_instance_id
        )
        return CancelWorkflowInstanceResponse()
    
    except UserMayNotAdministrateThisWorkflowException as ex:
        log.exception(f"User {user.username} is not allowed to call cancel_workflow_instance for task_id {reqdata.task_id}")
        raise HTTPException(status_code=403)



@router.get("/system_information", name="bff_admin_system_information")
def get_system_information() -> GetSystemInformationResponse:
    
    resp = GetSystemInformationResponse()
    resp.build_number = os.environ.get("CI_COMMIT_SHA", "dev")

    return resp

@router.get("/get_task_states_per_workflow", name="bff_admin_get_task_states_per_workflow")
def get_task_states_per_workflow(
    db: Annotated[Session, Depends(get_db)], 
    user: Annotated[WorkflowUser, Depends(get_user)],
    wf_name: str
) -> WorkflowStateResponse:
    result = service_application.admin_get_task_states_per_workflow(db=db, wf_name=wf_name, admin_user_id=user.id)
    return result
