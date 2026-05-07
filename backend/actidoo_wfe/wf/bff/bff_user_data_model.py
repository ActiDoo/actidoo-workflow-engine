# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import inspect as sa_inspect, select, func
from sqlalchemy.orm import Session

from actidoo_wfe.database import get_db
from actidoo_wfe.wf.bff.deps import get_user
from actidoo_wfe.wf.config_data_model import VirtualField
from actidoo_wfe.wf.cross_context.imports import require_realm_role
from actidoo_wfe.wf.exceptions import DataModelNotFoundError
from actidoo_wfe.wf.models import _MIXIN_SYSTEM_COLUMNS
from actidoo_wfe.wf.registry_data_model import DataModelDescriptor, data_model_registry


def _columns_from_model(model_class: type) -> list[dict]:
    """Derive column metadata from a SQLAlchemy model via inspection."""
    mapper = sa_inspect(model_class)
    return [
        {
            "name": col.key,
            "type": str(col.type),
            "nullable": col.nullable,
            "primary_key": col.primary_key,
        }
        for col in mapper.columns
        if col.key not in _MIXIN_SYSTEM_COLUMNS
    ]


def _fields_metadata(descriptor: DataModelDescriptor) -> list[dict]:
    """Build field metadata for the API response, respecting the fields config."""
    if not descriptor.api or descriptor.api.fields is None:
        return _columns_from_model(descriptor.model_class)

    mapper = sa_inspect(descriptor.model_class)
    col_map = {col.key: col for col in mapper.columns}
    result = []
    for f in descriptor.api.fields:
        if isinstance(f, VirtualField):
            result.append(
                {
                    "name": f.name,
                    "type": f.type,
                    "nullable": True,
                    "primary_key": False,
                    "virtual": True,
                }
            )
        elif isinstance(f, str):
            col = col_map.get(f)
            if col is not None:
                result.append(
                    {
                        "name": col.key,
                        "type": str(col.type),
                        "nullable": col.nullable,
                        "primary_key": col.primary_key,
                    }
                )
    return result


def _serialize_value(value: Any) -> Any:
    """Convert non-JSON-serializable types to JSON-safe representations."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _serialize_row(row: Any, fields: list[str | VirtualField] | None = None) -> dict:
    """Serialize a SQLAlchemy model instance to a dict."""
    if fields is None:
        mapper = sa_inspect(type(row))
        return {col.key: _serialize_value(getattr(row, col.key)) for col in mapper.columns if col.key not in _MIXIN_SYSTEM_COLUMNS}

    result = {}
    for f in fields:
        if isinstance(f, VirtualField):
            result[f.name] = _serialize_value(f.value(row))
        elif isinstance(f, str):
            result[f] = _serialize_value(getattr(row, f, None))
    return result


def _user_has_read_access(user, descriptor: DataModelDescriptor, db: Session) -> bool:
    """Check if the user has read access to this workflow-data model."""
    if not descriptor.api:
        return False
    if not descriptor.api.read_roles:
        return True
    user_roles = {r.role.name for r in user.roles}
    return bool(user_roles & set(descriptor.api.read_roles))


def _require_read_access(user, descriptor: DataModelDescriptor, db: Session) -> None:
    """Raise 404/403 if user lacks read access."""
    if not _user_has_read_access(user, descriptor, db):
        if not descriptor.api:
            raise HTTPException(status_code=404, detail="Model not found or not exposed via API")
        raise HTTPException(status_code=403, detail="Insufficient permissions")


def _require_wf_user(request: Request):
    """FastAPI dependency: require wf-user role."""
    require_realm_role("wf-user")(request)


workflow_data_router = APIRouter(
    prefix="/workflow-data",
    tags=["workflow-data"],
    dependencies=[Depends(_require_wf_user)],
)


@workflow_data_router.get("")
def list_models(
    user=Depends(get_user),
    db: Session = Depends(get_db),
):
    """List workflow-data models the current user can access, including column metadata."""
    return [{"name": d.name, "columns": _fields_metadata(d)} for d in data_model_registry.list_models() if d.api and _user_has_read_access(user, d, db)]


@workflow_data_router.get("/{model_name}")
def list_rows(
    model_name: str,
    user=Depends(get_user),
    db: Session = Depends(get_db),
    page: int = 1,
    page_size: int | None = Query(default=None),
):
    """List rows of a workflow-managed model (paginated, latest versions only)."""
    from actidoo_wfe.settings import settings

    try:
        descriptor = data_model_registry.get(model_name)
    except DataModelNotFoundError:
        raise HTTPException(status_code=404, detail=f"Data model '{model_name}' not found")

    _require_read_access(user, descriptor, db)

    page = max(1, page)
    effective_page_size = min(
        page_size or settings.data_model_api_page_size,
        settings.data_model_api_max_page_size,
    )

    model_class = descriptor.model_class
    query = select(model_class)

    # Only latest versions (no child = head of chain)
    query = query.where(model_class.child_workflow_instance_id.is_(None))

    # Apply row filter if defined
    if descriptor.api.row_filter:
        query = descriptor.api.row_filter(query, db, user)

    # Deterministic ordering for pagination
    query = query.order_by(model_class.workflow_instance_id)

    total = db.scalar(select(func.count()).select_from(query.subquery()))
    items = db.scalars(
        query.offset((page - 1) * effective_page_size).limit(effective_page_size),
    ).all()

    fields = descriptor.api.fields
    return {
        "items": [_serialize_row(item, fields) for item in items],
        "total": total,
        "page": page,
        "page_size": effective_page_size,
        "model": {
            "name": model_name,
            "columns": _fields_metadata(descriptor),
        },
    }


@workflow_data_router.get("/{model_name}/{workflow_instance_id}")
def get_version_chain(
    model_name: str,
    workflow_instance_id: str,
    user=Depends(get_user),
    db: Session = Depends(get_db),
):
    """Get the full version chain for a single entity."""
    try:
        descriptor = data_model_registry.get(model_name)
    except DataModelNotFoundError:
        raise HTTPException(status_code=404, detail=f"Data model '{model_name}' not found")

    _require_read_access(user, descriptor, db)

    model_class = descriptor.model_class

    # Load the requested row
    row = db.get(model_class, workflow_instance_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Row not found")

    # Walk up to the root of the chain
    current = row
    while current.parent_workflow_instance_id:
        parent = db.get(model_class, current.parent_workflow_instance_id)
        if parent is None:
            break
        current = parent

    # Walk down from root, collecting the full chain
    chain = []
    cursor = current
    while cursor is not None:
        chain.append(cursor)
        if cursor.child_workflow_instance_id:
            cursor = db.get(model_class, cursor.child_workflow_instance_id)
        else:
            cursor = None

    # Apply row filter on the head (latest version) for authorization
    if descriptor.api and descriptor.api.row_filter:
        head = chain[-1]
        check_query = select(model_class).where(
            model_class.workflow_instance_id == head.workflow_instance_id,
        )
        check_query = descriptor.api.row_filter(check_query, db, user)
        if db.scalars(check_query).first() is None:
            raise HTTPException(status_code=404, detail="Row not found")

    fields = descriptor.api.fields if descriptor.api else None
    return {
        "versions": [_serialize_row(r, fields) for r in chain],
        "model": {
            "name": model_name,
            "columns": _fields_metadata(descriptor),
        },
    }
