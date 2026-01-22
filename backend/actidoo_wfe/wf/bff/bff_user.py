# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

import logging
import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Path, Response, status
from sqlalchemy.orm import Session

import actidoo_wfe.helpers.bff_table as bff_table
import actidoo_wfe.wf.service_application as service_application
import actidoo_wfe.wf.service_i18n as service_i18n
import actidoo_wfe.wf.service_user as service_user
from actidoo_wfe.database import get_db
from actidoo_wfe.helpers.http import HTTPException, streaming_response_with_filecontent
from actidoo_wfe.wf.bff.bff_user_schema import (
    AssignTaskToMeRequest,
    AssignTaskToMeResponse,
    CancelWorkflowRequest,
    CancelWorkflowResponse,
    DeleteWorkflowRequest,
    DeleteWorkflowResponse,
    DownloadAttachmentRequest,
    GetMyWfeUserResponse,
    GetUserTasksResponse,
    GetUserTasksResponseUserTasks,
    GetWorkflowInstancesResponse,
    GetWorkflowsResponse,
    GetWorkflowsResponseItem,
    GetWorkflowStatisticsResponse,
    GetWorkflowStatisticsResponseItem,
    InlineUserResponse,
    GetWorkflowCopyDataResponse,
    LocaleItem,
    RefreshGetWorkflowSpecRequest,
    SaveUserSettingsRequest,
    SearchPropertyOptionsRequest,
    SearchPropertyOptionsResponse,
    SearchPropertyOptionsResponseItem,
    StartWorkflowRequest,
    StartWorkflowResponse,
    StartWorkflowWithDataRequest,
    StartWorkflowWithDataResponse,
    SubmitTaskDataErrorResponse,
    UserDelegationResponse,
    UserSettingsResponse,
    WorkflowSpecResponse,
)
from actidoo_wfe.wf.bff.deps import get_user
from actidoo_wfe.wf.cross_context.imports import require_realm_role
from actidoo_wfe.wf.exceptions import InvalidWorkflowSpecException, UserMayNotCopyWorkflowException, UserMayNotStartWorkflowException, ValidationResultContainsErrors
from actidoo_wfe.wf.models import WorkflowUser
from actidoo_wfe.wf.types import (
    Attachment,
    UserTaskRepresentation,
    WorkflowRepresentation,
)

log = logging.getLogger(__name__)

router = APIRouter(
    dependencies=[Depends(require_realm_role("wf-user"))],
    tags=["wfe-bff-user"]
)


@router.post("/my_wfe_user", name="get_my_wfe_user")
def get_my_wfe_user(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[WorkflowUser, Depends(get_user)],
) -> GetMyWfeUserResponse:
    wfe_user = service_application.get_user(db=db, user_id=user.id)
    workflows_the_user_is_admin_for = service_application.get_workflow_names_the_user_is_admin_for(db=db, user_id=user.id)
    return GetMyWfeUserResponse.model_validate(dict(**wfe_user.model_dump(),workflows_the_user_is_admin_for=workflows_the_user_is_admin_for))


@router.post("/start_workflow", name="start_workflow")
def start_workflow(
    reqdata: StartWorkflowRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[WorkflowUser, Depends(get_user)],
) -> StartWorkflowResponse:
    try:
        workflow_id = service_application.start_workflow(
            db=db,
            name=reqdata.name,
            user_id=user.id,
            initial_task_data=reqdata.data,
        )
    except UserMayNotStartWorkflowException:
        log.exception(f"Starting workflow {reqdata.name} failed")
        raise HTTPException(
            status_code=403, detail=f"Starting workflow {reqdata.name} not allowed"
        )
    except Exception:
        log.exception(f"Starting workflow {reqdata.name} failed")
        raise HTTPException(
            status_code=500, detail=f"Starting workflow {reqdata.name} failed"
        )
    return StartWorkflowResponse(workflow_instance_id=workflow_id)


@router.post("/start_workflow_preview_with_data", name="start_workflow_preview_with_data")
def start_workflow_preview_with_data(
    reqdata: StartWorkflowWithDataRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[WorkflowUser, Depends(get_user)],
) -> StartWorkflowWithDataResponse:
    try:
        preview = service_application.get_workflow_preview(
            db=db,
            name=reqdata.name,
            user_id=user.id,
            task_data=reqdata.data,
        )
    except UserMayNotStartWorkflowException:
        log.exception(f"Previewing workflow {reqdata.name} failed (not allowed)")
        raise HTTPException(
            status_code=403, detail=f"Previewing workflow {reqdata.name} not allowed"
        )
    except InvalidWorkflowSpecException:
        raise HTTPException(
            status_code=404, detail=f"Workflow spec {reqdata.name} not found"
        )
    except ValidationResultContainsErrors as ex:
        raise HTTPException(status_code=400, detail=ex.error_schema)
    except Exception:
        log.exception(f"Previewing workflow {reqdata.name} failed")
        raise HTTPException(
            status_code=500, detail=f"Previewing workflow {reqdata.name} failed"
        )

    return StartWorkflowWithDataResponse.model_validate(preview.model_dump())


@router.post("/workflow_instances/{workflow_instance_id}/copy_data", name="get_workflow_copy_data")
def get_workflow_copy_data(
    workflow_instance_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[WorkflowUser, Depends(get_user)],
) -> GetWorkflowCopyDataResponse:
    try:
        instruction = service_application.get_workflow_copy_data(
            db=db,
            user_id=user.id,
            workflow_instance_id=workflow_instance_id,
        )
    except UserMayNotCopyWorkflowException:
        log.exception(f"Creating workflow copy data for instance {workflow_instance_id} failed (copy not allowed)")
        raise HTTPException(
            status_code=403,
            detail="Starting workflow not allowed because the user may not copy the given workflow instance",
        )
    except UserMayNotStartWorkflowException:
        log.exception(f"Creating workflow copy data for instance {workflow_instance_id} failed (start not allowed)")
        raise HTTPException(
            status_code=403,
            detail="Starting workflow not allowed",
        )
    except InvalidWorkflowSpecException:
        raise HTTPException(
            status_code=404, detail="Workflow specification not found"
        )
    except Exception:
        log.exception(f"Creating workflow copy data for instance {workflow_instance_id} failed")
        raise HTTPException(
            status_code=500,
            detail="Creating workflow copy data failed",
        )

    return GetWorkflowCopyDataResponse.model_validate(instruction)


@router.get("/my_usertasks/{state}", name="get_usertasks")
def get_my_usertasks(
    workflow_instance_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[WorkflowUser, Depends(get_user)],
    state: Annotated[Literal["ready", "completed"], Path()],
) -> GetUserTasksResponse:
    tasks: list[UserTaskRepresentation] = service_application.get_usertasks_for_user_id(
        db=db, user_id=user.id, workflow_instance_id=workflow_instance_id, state=state
    )

    return GetUserTasksResponse(
        usertasks=[GetUserTasksResponseUserTasks.model_validate(t) for t in tasks]
    )


@router.post("/submit_task_data", name="submit_task_data")
def submit_task_data(
    task_id: uuid.UUID,
    task_data: dict,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[WorkflowUser, Depends(get_user)],
    response: Response,
    delegate_comment: str | None = None,
) -> GetUserTasksResponse|SubmitTaskDataErrorResponse:
    try:
        success, workflow_instance_id = service_application.submit_task_data(
            db=db, user_id=user.id, task_id=task_id, task_data=task_data, delegate_comment=delegate_comment
        )
        
        tasks: list[UserTaskRepresentation] = service_application.get_usertasks_for_user_id(
            db=db, user_id=user.id, workflow_instance_id=workflow_instance_id, state="ready"
        )

        return GetUserTasksResponse(
            usertasks=[GetUserTasksResponseUserTasks.model_validate(t) for t in tasks]
        )
    except ValidationResultContainsErrors as ex:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return SubmitTaskDataErrorResponse(
            error_schema=ex.error_schema
        )


WorkflowInstancesBffTableQuerySchema = bff_table.get_bff_table_query_schema(
    schema_name="WorkflowInstancesBffTableQuerySchema",
    sorting_fields=["id", "name", "title", "subtitle", "created_at", "completed_at"],
    filter_fields=[
        bff_table.UUidSearchFilterField(name="id"),
        bff_table.TextSearchFilterField(name="name"),
        bff_table.TextSearchFilterField(name="title"),
        bff_table.TextSearchFilterField(name="subtitle"),
        bff_table.DatetimeSearchFilterField(name="created_at"),
        bff_table.DatetimeSearchFilterField(name="completed_at"),
        bff_table.BooleanFilterField(name="is_completed"),
    ],
    add_global_search_filter=True,
)


@router.post(
    "/my_initiated_workflow_instances", name="get_my_initiated_workflow_instances"
)
def get_my_initiated_workflow_instances(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[WorkflowUser, Depends(get_user)],
    bff_table_request_params: Annotated[
        bff_table.BffTableQuerySchemaBase, Depends(WorkflowInstancesBffTableQuerySchema)
    ],  # type: ignore
) -> GetWorkflowInstancesResponse:
    ppp = WorkflowInstancesBffTableQuerySchema.parse_obj(bff_table_request_params)

    workflows: GetWorkflowInstancesResponse = (
        GetWorkflowInstancesResponse.model_validate(
            service_application.bff_user_get_initiated_workflows(
                db=db, bff_table_request_params=ppp, user_id=user.id
            )
        )
    )

    return workflows


@router.post(
    "/workflow_instances_with_tasks/{state}", name="get_workflow_instances_with_tasks"
)
def get_workflow_instances_with_tasks(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[WorkflowUser, Depends(get_user)],
    bff_table_request_params: Annotated[
        bff_table.BffTableQuerySchemaBase, Depends(WorkflowInstancesBffTableQuerySchema)
    ],  # type: ignore
    state: Annotated[Literal["ready", "completed"], Path()],
) -> GetWorkflowInstancesResponse:
    ppp = WorkflowInstancesBffTableQuerySchema.parse_obj(bff_table_request_params)

    workflows: GetWorkflowInstancesResponse = (
        GetWorkflowInstancesResponse.model_validate(
            service_application.bff_get_workflows_with_usertasks(
                db=db, bff_table_request_params=ppp, user_id=user.id, state=state
            )
        )
    )

    return workflows


@router.get("/workflows", name="get_workflows")
def get_workflows(db: Annotated[Session, Depends(get_db)], user: Annotated[WorkflowUser, Depends(get_user)]):
    
    workflows: list[WorkflowRepresentation] = service_application.get_allowed_workflows_to_start(db=db, user_id=user.id)

    return GetWorkflowsResponse(
        workflows=[
            GetWorkflowsResponseItem(name=x.name, title=x.title) for x in workflows
        ]
    )


@router.post("/assign_task_to_me", name="assign_task")
def assign_task_to_me(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[WorkflowUser, Depends(get_user)],
    reqdata: AssignTaskToMeRequest,
) -> AssignTaskToMeResponse:
    service_application.assign_task_to_me(
        db=db, user_id=user.id, task_id=reqdata.task_id
    )

    return AssignTaskToMeResponse()


@router.post("/unassign_task_from_me", name="unassign_task")
def unassign_task_from_me(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[WorkflowUser, Depends(get_user)],
    reqdata: AssignTaskToMeRequest,
) -> AssignTaskToMeResponse:
    service_application.unassign_task_from_me(
        db=db, user_id=user.id, task_id=reqdata.task_id
    )

    return AssignTaskToMeResponse()


@router.post("/search_property_options", name="get_property_options")
def search_property_options(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[WorkflowUser, Depends(get_user)],
    search_options: SearchPropertyOptionsRequest,
) -> SearchPropertyOptionsResponse:
    options = service_application.search_property_options(
        db=db,
        user_id=user.id,
        task_id=search_options.task_id,
        property_path=search_options.property_path,
        search=search_options.search,
        include_value=search_options.include_value,
        form_data=search_options.form_data
    )

    return SearchPropertyOptionsResponse(
        options=[
            SearchPropertyOptionsResponseItem(value=option[0], label=option[1])
            for option in options
        ]
    )


@router.post("/download_attachment", name="download_attachment")
def download_attachment(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[WorkflowUser, Depends(get_user)],
    search_options: DownloadAttachmentRequest,
) -> Response:
    attachment: Attachment = (
        service_application.verify_assigned_user_and_download_attachment(
            db=db,
            user_id=user.id,
            task_id=search_options.task_id,
            hash=search_options.hash,
        )
    )

    return streaming_response_with_filecontent(
        binary=attachment.data,
        filename=attachment.filename,
        mimetype=attachment.mimetype,
    )


@router.post("/refresh_get_workflow_spec", name="refresh_get_workflow_spec")
def refresh_get_workflow_spec(
    db: Annotated[Session, Depends(get_db)],
    req_data: RefreshGetWorkflowSpecRequest,
) -> WorkflowSpecResponse:
    spec = service_application.refresh_get_workflow_spec(db=db, name=req_data.name, file_type="bpmn", version=None)
    
    return WorkflowSpecResponse.model_validate(spec)


@router.post("/cancel_workflow", name="cancel_workflow")
def cancel_workflow(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[WorkflowUser, Depends(get_user)],
    reqdata: CancelWorkflowRequest,
) -> CancelWorkflowResponse:
    service_application.user_cancel_workflow(
        db=db, user_id=user.id, task_id=reqdata.task_id
    )

    return CancelWorkflowResponse()

@router.post("/delete_workflow", name="delete_workflow")
def delete_workflow(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[WorkflowUser, Depends(get_user)],
    reqdata: DeleteWorkflowRequest,
) -> DeleteWorkflowResponse:
    service_application.user_delete_workflow(
        db=db, user_id=user.id, task_id=reqdata.task_id
    )

    return DeleteWorkflowResponse()


@router.get("/statistics", name="get_workflow_statistics")
def get_workflow_statistics(db: Annotated[Session, Depends(get_db)], user: Annotated[WorkflowUser, Depends(get_user)]):
    
    workflows = service_application.get_workflow_statistics(db=db, user_id=user.id)

    return GetWorkflowStatisticsResponse(
        workflows=[
            GetWorkflowStatisticsResponseItem.model_validate(x) for x in workflows
        ]
    )




def _serialize_user_delegations(db: Session, user_id: uuid.UUID) -> list[UserDelegationResponse]:
    delegations = service_user.list_user_delegations(db=db, principal_user_id=user_id)
    responses: list[UserDelegationResponse] = []
    for delegation in delegations:
        delegate = delegation.delegate
        responses.append(
            UserDelegationResponse(
                delegate_user_id=delegation.delegate_user_id,
                valid_until=delegation.valid_until,
                delegate=InlineUserResponse(
                    id=delegate.id,
                    full_name=delegate.full_name,
                    username=delegate.username,
                    email=delegate.email,
                ),
            )
        )
    return responses

@router.post("/user_settings", name="save_user_settings")
def save_user_settings(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[WorkflowUser, Depends(get_user)],
    reqdata: SaveUserSettingsRequest,
) -> UserSettingsResponse:

    delegations = (
        [(d.delegate_user_id, d.valid_until) for d in reqdata.delegations]
        if reqdata.delegations is not None
        else None
    )

    updated_user = service_user.update_user_settings(
        db=db,
        user_id=user.id,
        locale=reqdata.locale,
        delegations=delegations,
    )

    locales = service_i18n.get_supported_locales()
    delegation_responses = _serialize_user_delegations(db=db, user_id=user.id)

    return UserSettingsResponse(
        locale=updated_user.locale,
        supported_locales=[LocaleItem(**l) for l in locales],
        delegations=delegation_responses,
    )

@router.get("/user_settings", name="get_user_settings")
def get_user_settings(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[WorkflowUser, Depends(get_user)],
) -> UserSettingsResponse:
    user = service_user.get_user_settings(
        db=db,
        user_id=user.id,
    )

    locales = service_i18n.get_supported_locales()
    delegation_responses = _serialize_user_delegations(db=db, user_id=user.id)

    return UserSettingsResponse(
        locale=user.locale,
        supported_locales=[LocaleItem(**l) for l in locales],
        delegations=delegation_responses,
    )
