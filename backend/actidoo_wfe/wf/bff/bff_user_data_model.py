# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""Workflow-data BFF: thin HTTP routes for the data API.

Every route resolves the requested model from the data-model registry at request
time (``get_data_model``, a dependency on the ``{model_name}`` path parameter)
and delegates to ``service_data_model``, which raises domain exceptions only;
``_map_domain_errors``, a router-level yield-dependency, turns them into HTTP
responses. The list and version-chain routes build their typed table-query schema
(sorting/filter fields) per request from the model's schema — a single dynamic
route per endpoint, no per-model route generation or startup wiring.

Route order matters: the literal sub-paths (``export.csv``, ``processes``) are
declared before the ``/{model_name}/{row_id}`` version-chain route so a path like
``/DemoExpense/export.csv`` is never captured by the version-chain parameter.
"""

from __future__ import annotations

import logging
import uuid
from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

import actidoo_wfe.wf.service_data_model as service_data_model
import actidoo_wfe.wf.views_data_model as views_data_model
from actidoo_wfe.database import get_db
from actidoo_wfe.helpers.bff_table import (
    BffTableQuerySchemaBase,
    get_bff_table_query_schema,
    parse_bff_table_query_params,
)
from actidoo_wfe.helpers.http import HTTPException, streaming_response_with_filecontent
from actidoo_wfe.wf.bff.bff_user_data_model_schema import StartWorkflowForExistingDataModelRequest
from actidoo_wfe.wf.bff.bff_user_schema import StartWorkflowResponse
from actidoo_wfe.wf.bff.deps import get_data_model, get_user
from actidoo_wfe.wf.cross_context.imports import require_realm_role
from actidoo_wfe.wf.exceptions import (
    DataModelForbiddenError,
    DataModelNotFoundError,
    DataModelRowNotFoundError,
    UserMayNotStartWorkflowException,
)
from actidoo_wfe.wf.models import WorkflowUser
from actidoo_wfe.wf.registry_data_model import DataModelDescriptor
from actidoo_wfe.wf.types_data_model import (
    DataModelSchema,
    ListRowsResponse,
    ProcessRefSchema,
    VersionChainResponse,
)

log = logging.getLogger(__name__)


def _map_domain_errors():
    """Router-level yield-dependency mapping the data-model domain exceptions to HTTP.

    Exceptions raised by the routes propagate into the ``yield`` and are re-raised
    as HTTPException here, so the routes stay free of mapping boilerplate.
    ``DataModelNotFoundError`` gets a static detail on purpose: the registry's
    message enumerates all registered model names, which must not leak to clients.
    """
    try:
        yield
    except DataModelRowNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except DataModelForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except DataModelNotFoundError:
        raise HTTPException(status_code=404, detail="Model not found or not exposed via API")


workflow_data_router = APIRouter(
    prefix="/workflow-data",
    tags=["workflow-data"],
    dependencies=[Depends(require_realm_role("wf-user")), Depends(_map_domain_errors)],
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@lru_cache(maxsize=128)
def _get_bff_table_query_schema_for(data_model: DataModelDescriptor) -> type[BffTableQuerySchemaBase]:
    """Build the model's table-query schema class, once per data model.

    The schema (sortable/filterable fields) is derived from the model's field
    schema and is deterministic per data model, so the class is built lazily on
    first use and cached. Descriptors hash by identity (``eq=False``), so a
    re-registration (dev reload, tests) naturally misses the cache.
    """
    sorting_fields, filter_fields, _ = views_data_model.table_spec(data_model)
    return get_bff_table_query_schema(
        schema_name=f"WorkflowData{data_model.name}Query",
        sorting_fields=sorting_fields,
        filter_fields=filter_fields,
        add_global_search_filter=True,
    )


def _parse_bff_table_query_params_for(data_model: DataModelDescriptor, request: Request) -> BffTableQuerySchemaBase:
    """Populate the model's table-query schema from the request params.

    Only declared, typed fields can be sorted/filtered on. Unknown sort values
    are rejected with 422; unknown query params are ignored.
    """
    return parse_bff_table_query_params(_get_bff_table_query_schema_for(data_model), request)


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------


@workflow_data_router.get("", name="list_models")
def list_models(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[WorkflowUser, Depends(get_user)],
) -> list[DataModelSchema]:
    """List the workflow-data models the current user can access, with field schema."""
    return service_data_model.list_models(db=db, user_id=user.id)


# ---------------------------------------------------------------------------
# Single-purpose sub-paths (declared before the version-chain catch-all)
# ---------------------------------------------------------------------------


@workflow_data_router.get("/{model_name}/export.csv", name="export_data_model_csv")
def export_data_model_csv(
    data_model: Annotated[DataModelDescriptor, Depends(get_data_model)],
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[WorkflowUser, Depends(get_user)],
) -> Response:
    """Export the rows of a model the user may read as CSV.

    Honors the same filter/search/sort query params as the list route, so the
    export matches the visible table view — but never paginated: pagination
    params are ignored, the export always holds the complete filtered set.
    """
    request_params = _parse_bff_table_query_params_for(data_model, request)
    content, filename = service_data_model.export_rows_csv(
        db=db, user_id=user.id, data_model=data_model, request_params=request_params
    )
    return streaming_response_with_filecontent(
        # utf-8-sig: a BOM so Excel (esp. de-DE, ``;`` delimiter) reads it as UTF-8.
        binary=content.encode("utf-8-sig"),
        filename=filename,
        mimetype="text/csv",
    )


@workflow_data_router.get("/{model_name}/processes", name="list_data_model_processes")
def list_data_model_processes(
    data_model: Annotated[DataModelDescriptor, Depends(get_data_model)],
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[WorkflowUser, Depends(get_user)],
) -> list[ProcessRefSchema]:
    """List the workflows using this model that the current user may start."""
    return service_data_model.list_processes_for_model(db=db, user_id=user.id, data_model=data_model)


@workflow_data_router.get(
    "/{model_name}/{row_id}/versions/{version}/attachments/{file_hash}",
    name="download_data_model_attachment",
)
def download_data_model_attachment(
    data_model: Annotated[DataModelDescriptor, Depends(get_data_model)],
    row_id: uuid.UUID,
    version: int,
    file_hash: str,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[WorkflowUser, Depends(get_user)],
) -> Response:
    """Stream an attachment referenced by a specific version of a row, authorized via data-model read access."""
    attachment = service_data_model.load_row_attachment(
        db=db,
        user_id=user.id,
        data_model=data_model,
        row_id=row_id,
        version=version,
        file_hash=file_hash,
    )
    return streaming_response_with_filecontent(
        binary=attachment.data,
        filename=attachment.filename,
        mimetype=attachment.mimetype,
    )


# ---------------------------------------------------------------------------
# Per-model read endpoints (dynamic: model resolved + query schema built per request)
# ---------------------------------------------------------------------------


@workflow_data_router.get("/{model_name}", name="list_data_model_rows")
def list_data_model_rows(
    data_model: Annotated[DataModelDescriptor, Depends(get_data_model)],
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[WorkflowUser, Depends(get_user)],
) -> ListRowsResponse:
    """List the latest version of each row (paginated/filtered/sorted)."""
    request_params = _parse_bff_table_query_params_for(data_model, request)
    return service_data_model.list_rows(db=db, user_id=user.id, data_model=data_model, request_params=request_params)


@workflow_data_router.get("/{model_name}/{row_id}", name="get_data_model_version_chain")
def get_data_model_version_chain(
    data_model: Annotated[DataModelDescriptor, Depends(get_data_model)],
    row_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[WorkflowUser, Depends(get_user)],
) -> VersionChainResponse:
    """Return the full version chain for a single record (oldest first)."""
    return service_data_model.get_version_chain(
        db=db,
        user_id=user.id,
        data_model=data_model,
        row_id=row_id,
    )


# ---------------------------------------------------------------------------
# Action execution (start a follow-up workflow from a row)
# ---------------------------------------------------------------------------


@workflow_data_router.post("/start_workflow", name="start_workflow_for_existing_data_model")
def start_workflow_for_existing_data_model(
    reqdata: StartWorkflowForExistingDataModelRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[WorkflowUser, Depends(get_user)],
) -> StartWorkflowResponse:
    """Start a follow-up workflow (declared as an action on a data model) from an existing row."""
    data_model = get_data_model(reqdata.model_name)
    try:
        workflow_id = service_data_model.start_workflow_for_existing_data_model(
            db=db,
            user_id=user.id,
            data_model=data_model,
            row_id=reqdata.id,
            action_key=reqdata.action,
        )
    except UserMayNotStartWorkflowException:
        log.warning("Starting workflow for data-model action %s failed (not allowed)", reqdata.action)
        raise HTTPException(
            status_code=403,
            detail=f"Starting workflow for action '{reqdata.action}' not allowed",
        )
    return StartWorkflowResponse(workflow_instance_id=workflow_id)
