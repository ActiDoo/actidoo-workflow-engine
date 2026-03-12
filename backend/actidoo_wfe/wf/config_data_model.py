# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Literal

from sqlalchemy import select


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
