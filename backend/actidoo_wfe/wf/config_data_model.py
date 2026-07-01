# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Literal

from sqlalchemy import false, select

DisplayType = Literal["string", "number", "decimal", "boolean", "datetime", "date", "file"]

# Wildcard entry for ``WorkflowDataApiConfig.read_roles``: every workflow user may
# read the model. Read access is deny-by-default; opening a model to everyone is
# an explicit, greppable decision instead of a forgotten field.
READ_ALL_WORKFLOW_USERS = "*"


@dataclass
class FieldDef:
    """Declarative description of a data-model field for the data API.

    ``type``/``label``/``format`` are authoritative; whatever is not declared is
    inferred from the SQLAlchemy column. A field with ``compute`` set is a
    computed field with no database column — ``type`` should then be given, since
    it cannot be inferred.

    ``label`` is a gettext msgid: it is resolved to the requesting user's locale
    against the model's catalog (``i18n/locales/<locale>/LC_MESSAGES/<Model>.mo``
    next to the model module — same toolchain as the workflow catalogs) and falls
    back to the msgid itself when no catalog/translation exists.

    ``include_in_table``/``include_in_detail``/``include_in_csv`` gate the field per
    presentation context (all default on). They are orthogonal: a verbose field can be
    shown only on the detail page (``include_in_table=False``) so it never bloats the
    table list payload, while a noisy field can be kept out of the export, etc. Filtered
    server-side in ``field_metadata``/``serialize_row``, so they stay authoring-only and
    are never part of the wire schema.
    """

    name: str
    label: str | None = None
    type: DisplayType | None = None
    # presentation hint the DB type can't express, e.g. "currency:EUR"
    format: str | None = None
    # (row) -> Any; if set, this is a computed/virtual field with no DB column
    compute: Callable | None = None
    # Per-context visibility (all default on); see class docstring.
    include_in_table: bool = True
    include_in_detail: bool = True
    include_in_csv: bool = True

    @property
    def is_computed(self) -> bool:
        return self.compute is not None


@dataclass
class ActionDef:
    """A follow-up workflow that can be started from a data-model row.

    ``row_filter`` decides on which rows the action is available — the same
    ``(query, db, user) -> query`` shape (and helper library) as
    ``WorkflowDataApiConfig.row_filter`` for reads, evaluated at the DB level.
    ``payload`` optionally maps a row to the initial task data of the workflow.
    """

    key: str
    label: str  # gettext msgid, resolved like FieldDef.label
    target: str  # name of the workflow to start
    row_filter: Callable | None = None  # (query, db, user) -> query
    payload: Callable | None = None  # (row) -> dict


@dataclass(kw_only=True)
class WorkflowDataApiConfig:
    """API configuration for a workflow-managed data model.

    ``read_roles`` is mandatory and must not be empty: either name the roles that
    may read the model, or open it to every workflow user explicitly with
    ``read_roles=[READ_ALL_WORKFLOW_USERS]``. Forgetting it fails at import time,
    an empty list fails at registration — a model can never become readable to
    everyone by accident.
    """

    # Human-readable model label for the catalog / table title (falls back to the
    # registered model name when not set). A gettext msgid, resolved like
    # ``FieldDef.label``.
    label: str | None = None
    read_roles: list[str]
    row_filter: Callable | None = None
    fields: list[FieldDef] | None = None
    actions: list[ActionDef] = field(default_factory=list)


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
    from sqlalchemy import or_

    from actidoo_wfe.wf.models import (
        WorkflowInstance,
        WorkflowInstanceTask,
        WorkflowInstanceTaskRole,
        WorkflowRole,
        WorkflowUserRole,
    )

    user_role_names = select(WorkflowRole.name).join(WorkflowUserRole, WorkflowRole.id == WorkflowUserRole.role_id).where(WorkflowUserRole.user_id == user.id)

    participant_wf_ids = (
        select(WorkflowInstance.id)
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
            ),
        )
    )

    return query.where(wf_id_column.in_(participant_wf_ids))


# ---------------------------------------------------------------------------
# Row-filter helper
#
# A row filter has the shape ``(query, db, user) -> query`` and is used both for
# read visibility (``WorkflowDataApiConfig.row_filter``) and action eligibility
# (``ActionDef.row_filter``). Column/value conditions are plain SQLAlchemy
# ``.where(...)`` clauses written inline. ``requires_role`` covers the one case
# SQLAlchemy can't express on its own: gating the whole result set on a
# Python-side user role.
# ---------------------------------------------------------------------------


def requires_role(*roles: str) -> Callable:
    """Keep all rows if the user has any of *roles*, otherwise none.

    A user/global condition expressed as a row filter: the query is returned
    unchanged (role present) or restricted to nothing (``where(false())``).
    Chain a normal ``.where(...)`` after it for a "role AND row condition" filter.
    """

    def _filter(query, db, user):
        if {r.role.name for r in user.roles} & set(roles):
            return query
        return query.where(false())

    return _filter
