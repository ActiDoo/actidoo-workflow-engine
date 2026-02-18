# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""
Data Model Persistence — extension point for structured business data.

Projects register data models — SQLAlchemy models for business data that
lives alongside workflows.  Workflows declare which models they use, and
the task helpers provide access with dependency enforcement.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Callable, Dict, List, Literal, Type

import venusian
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import DateTime, String, inspect as sa_inspect, select, func
from sqlalchemy.orm import Mapped, Session, declared_attr, mapped_column

from actidoo_wfe.database import Base, get_db

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class DataModelNotFoundError(KeyError):
    """Raised when a data model name is not in the registry."""


class DataModelAccessDeniedError(Exception):
    """Raised when a workflow accesses a data model it did not declare."""

    def __init__(self, model_name: str, allowed: set[str]):
        self.model_name = model_name
        self.allowed = allowed
        super().__init__(
            f"Access denied to data model '{model_name}'. "
            f"Allowed models for this workflow: {sorted(allowed)}"
        )


# ---------------------------------------------------------------------------
# extension_model_base — factory for prefixed SQLAlchemy models
# ---------------------------------------------------------------------------


def extension_model_base(namespace: str) -> type:
    """Create an abstract base class whose subclasses get auto-prefixed table names.

    Usage in an extension project::

        AcmeModel = extension_model_base("acme")

        class OrderApproval(AcmeModel):
            _ext_table = "order_approval"
            # -> __tablename__ = "ext_acme_order_approval"
    """

    class _ExtBase(Base):
        __abstract__ = True
        _ext_namespace: str = namespace
        _ext_table: str  # must be defined by subclass

        @declared_attr.directive
        def __tablename__(cls) -> str:
            table = getattr(cls, "_ext_table", None)
            if not table:
                raise ValueError(
                    f"{cls.__name__} must define '_ext_table' as a stable DB identifier"
                )
            return f"ext_{namespace}_{table}"

    return _ExtBase


# ---------------------------------------------------------------------------
# WorkflowManagedMixin — version-chain columns for workflow-managed data
# ---------------------------------------------------------------------------

_MIXIN_SYSTEM_COLUMNS = frozenset({
    "parent_workflow_instance_id",
    "child_workflow_instance_id",
    "action",
})


class WorkflowManagedMixin:
    """Mixin for data managed exclusively by workflows.

    Each modification creates a new row linked to the previous one,
    forming a version chain via parent/child workflow instance IDs.
    """

    workflow_instance_id: Mapped[str] = mapped_column(
        String(100), primary_key=True,
    )
    parent_workflow_instance_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True,
    )
    child_workflow_instance_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True,
    )
    action: Mapped[str | None] = mapped_column(
        String(100), nullable=True,
    )
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True,
    )


# ---------------------------------------------------------------------------
# VirtualField + WorkflowDataApiConfig
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VirtualField:
    """A computed field that doesn't exist in the database."""

    name: str
    type: Literal["string", "integer", "number", "boolean", "datetime", "array"]
    value: Callable  # (row) -> Any


@dataclass
class WorkflowDataApiConfig:
    """API configuration for a workflow-managed data model."""

    read_roles: list[str] = field(default_factory=list)
    row_filter: Callable | None = None
    fields: list[str | VirtualField] | None = None


def add_workflow_participant_filter(query, wf_id_column, user: Any):
    """Filter *query* to rows whose *wf_id_column* belongs to a workflow the user participates in.

    Participation is determined by four paths:

    * **Creator** — ``WorkflowInstance.created_by_id``
    * **Assignee / delegate** — ``WorkflowInstanceTask.assigned_user_id`` /
      ``assigned_delegate_user_id``
    * **Lane role** — the user owns a role that is listed in
      ``WorkflowInstanceTaskRole``

    Returns the filtered query.
    """
    from sqlalchemy import cast, or_
    from sqlalchemy import types as sa_types
    from actidoo_wfe.wf.models import (
        WorkflowInstance,
        WorkflowInstanceTask,
        WorkflowInstanceTaskRole,
        WorkflowRole,
        WorkflowUserRole,
    )

    user_role_names = (
        select(WorkflowRole.name)
        .join(WorkflowUserRole, WorkflowRole.id == WorkflowUserRole.role_id)
        .where(WorkflowUserRole.user_id == user.id)
    )

    participant_wf_ids = (
        select(cast(WorkflowInstance.id, sa_types.String(100)))
        .distinct()
        .outerjoin(
            WorkflowInstanceTask,
            WorkflowInstanceTask.workflow_instance_id == WorkflowInstance.id,
        )
        .outerjoin(
            WorkflowInstanceTaskRole,
            WorkflowInstanceTaskRole.workflow_instance_task_id == WorkflowInstanceTask.id,
        )
        .where(
            or_(
                WorkflowInstance.created_by_id == user.id,
                WorkflowInstanceTask.assigned_user_id == user.id,
                WorkflowInstanceTask.assigned_delegate_user_id == user.id,
                WorkflowInstanceTaskRole.name.in_(user_role_names),
            )
        )
    )

    return query.where(wf_id_column.in_(participant_wf_ids))


# ---------------------------------------------------------------------------
# DataModelDescriptor + Registry
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DataModelDescriptor:
    name: str
    model_class: type
    namespace: str
    api: WorkflowDataApiConfig | None = None


class DataModelRegistry:
    def __init__(self) -> None:
        self._models: Dict[str, DataModelDescriptor] = {}

    def register(self, descriptor: DataModelDescriptor) -> None:
        existing = self._models.get(descriptor.name)
        if existing is not None:
            if existing.model_class is descriptor.model_class:
                return  # dedup
            raise ValueError(
                f"Data model '{descriptor.name}' already registered with a different model class "
                f"(existing: {existing.model_class.__name__}, new: {descriptor.model_class.__name__})"
            )
        self._models[descriptor.name] = descriptor
        log.debug("Registered data model %r (namespace=%s, table=%s)",
                  descriptor.name, descriptor.namespace,
                  getattr(descriptor.model_class, "__tablename__", "?"))

    def get(self, name: str) -> DataModelDescriptor:
        try:
            return self._models[name]
        except KeyError:
            raise DataModelNotFoundError(
                f"Data model '{name}' is not registered. "
                f"Available: {sorted(self._models)}"
            ) from None

    def list_names(self) -> List[str]:
        return sorted(self._models)

    def list_models(self) -> List[DataModelDescriptor]:
        return list(self._models.values())

    def clear(self) -> None:
        self._models.clear()


data_model_registry = DataModelRegistry()


# ---------------------------------------------------------------------------
# @register_data_model — venusian decorator (dual registration)
# ---------------------------------------------------------------------------


def register_data_model(
    *,
    name: str,
    api: WorkflowDataApiConfig | None = None,
):
    """Decorator to register a data model class.

    Usage::

        @register_data_model(name="OrderApproval")
        class OrderApproval(AcmeModel):
            _ext_table = "order_approval"
            ...

    If *api* is provided, the model must use ``WorkflowManagedMixin``.
    """

    def decorator(model_class: type) -> type:
        if api is not None and not issubclass(model_class, WorkflowManagedMixin):
            raise TypeError(
                f"Data model '{name}' provides an api config but does not use "
                f"WorkflowManagedMixin. Only workflow-managed models can be "
                f"exposed via the API."
            )

        namespace = getattr(model_class, "_ext_namespace", "")
        descriptor = DataModelDescriptor(
            name=name,
            model_class=model_class,
            namespace=namespace,
            api=api,
        )

        def callback(scanner, _name, _ob):
            data_model_registry.register(descriptor)

        venusian.attach(model_class, callback)
        data_model_registry.register(descriptor)
        return model_class

    return decorator


# ---------------------------------------------------------------------------
# REST API Router — Workflow Data
# ---------------------------------------------------------------------------


def _columns_from_model(model_class: type) -> list[dict]:
    """Derive column metadata from a SQLAlchemy model via inspection.

    Mixin system columns (parent_workflow_instance_id,
    child_workflow_instance_id, action) are excluded.
    """
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
            result.append({
                "name": f.name,
                "type": f.type,
                "nullable": True,
                "primary_key": False,
                "virtual": True,
            })
        elif isinstance(f, str):
            col = col_map.get(f)
            if col is not None:
                result.append({
                    "name": col.key,
                    "type": str(col.type),
                    "nullable": col.nullable,
                    "primary_key": col.primary_key,
                })
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
    """Serialize a SQLAlchemy model instance to a dict.

    If *fields* is given, only include those fields in order.
    VirtualField entries are computed from the row.
    Otherwise all columns minus mixin system columns are returned.
    """
    if fields is None:
        mapper = sa_inspect(type(row))
        return {
            col.key: _serialize_value(getattr(row, col.key))
            for col in mapper.columns
            if col.key not in _MIXIN_SYSTEM_COLUMNS
        }

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
        return True  # no restriction = all authenticated users
    user_roles = {r.role.name for r in user.roles}
    return bool(user_roles & set(descriptor.api.read_roles))


def _require_read_access(user, descriptor: DataModelDescriptor, db: Session) -> None:
    """Raise 404/403 if user lacks read access."""
    if not _user_has_read_access(user, descriptor, db):
        if not descriptor.api:
            raise HTTPException(status_code=404, detail="Model not found or not exposed via API")
        raise HTTPException(status_code=403, detail="Insufficient permissions")


def _require_wf_user(request: Request):
    """FastAPI dependency: require wf-user role (lazy import to avoid circular deps)."""
    from actidoo_wfe.wf.cross_context.imports import require_realm_role
    require_realm_role("wf-user")(request)


def _current_user(request: Request):
    """FastAPI dependency: get current authenticated user (lazy import)."""
    from actidoo_wfe.wf.bff.deps import get_user
    return get_user(request)


workflow_data_router = APIRouter(
    prefix="/workflow-data",
    tags=["workflow-data"],
    dependencies=[Depends(_require_wf_user)],
)


@workflow_data_router.get("")
def list_models(
    user=Depends(_current_user),
    db: Session = Depends(get_db),
):
    """List workflow-data models the current user can access, including column metadata."""
    return [
        {"name": d.name, "columns": _fields_metadata(d)}
        for d in data_model_registry.list_models()
        if d.api and _user_has_read_access(user, d, db)
    ]


@workflow_data_router.get("/{model_name}")
def list_rows(
    model_name: str,
    user=Depends(_current_user),
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
        query.offset((page - 1) * effective_page_size).limit(effective_page_size)
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
    user=Depends(_current_user),
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
            model_class.workflow_instance_id == head.workflow_instance_id
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
