# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""Application service (facade) for the workflow-data API.

Coordinates authorization (read access, per-row action permission) and
orchestration, delegating the actual read-model work to ``views_data_model`` and
the workflow start to ``service_application``. Raises only domain exceptions from
``wf.exceptions``; the HTTP mapping lives in the BFF, as does resolving a model
name to a ``DataModelDescriptor``.

Like the workflow services, the entry points take a ``user_id`` and load the user
fresh from the request-scoped session — here as the ORM ``WorkflowUser`` rather
than a ``UserRepresentation``, because the ``row_filter`` callbacks
``(query, db, user)`` are public extension API and rely on the ORM relationships
(e.g. ``user.roles[].role.name``).
"""

from __future__ import annotations

import importlib
import logging
import uuid
from functools import lru_cache

from sqlalchemy import select
from sqlalchemy.orm import Session

import actidoo_wfe.wf.providers as workflow_providers
import actidoo_wfe.wf.repository as repository
import actidoo_wfe.wf.service_application as service_application
import actidoo_wfe.wf.service_workflow as service_workflow
import actidoo_wfe.wf.views_data_model as views_data_model
from actidoo_wfe.helpers.bff_table import BffTableQuerySchemaBase
from actidoo_wfe.storage import get_file_content
from actidoo_wfe.wf.config_data_model import READ_ALL_WORKFLOW_USERS
from actidoo_wfe.wf.exceptions import (
    DataModelForbiddenError,
    DataModelNotFoundError,
    DataModelRowNotFoundError,
)
from actidoo_wfe.wf.models import WorkflowUser
from actidoo_wfe.wf.registry_data_model import DataModelDescriptor, data_model_registry
from actidoo_wfe.wf.types import Attachment
from actidoo_wfe.wf.types_data_model import (
    DataModelSchema,
    ListRowsResponse,
    ProcessRefSchema,
    VersionChainResponse,
)

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Authorization
# ---------------------------------------------------------------------------


def _user_has_read_access(user: WorkflowUser, data_model: DataModelDescriptor) -> bool:
    """Check read access (deny by default; ``READ_ALL_WORKFLOW_USERS`` opens the model)."""
    if not data_model.api:
        return False
    if READ_ALL_WORKFLOW_USERS in data_model.api.read_roles:
        return True
    user_roles = {r.role.name for r in user.roles}
    return bool(user_roles & set(data_model.api.read_roles))


def _require_read_access(db: Session, user_id: uuid.UUID, data_model: DataModelDescriptor) -> WorkflowUser:
    """Load the user; raise not-found/forbidden if they lack read access."""
    user = repository.load_workflow_user(db, user_id)
    if not _user_has_read_access(user, data_model):
        if not data_model.api:
            raise DataModelNotFoundError("Model not found or not exposed via API")
        raise DataModelForbiddenError("Insufficient permissions")
    return user


def _passes_row_filter(db: Session, user: WorkflowUser, row_filter, data_model: DataModelDescriptor, row) -> bool:
    """Whether the exact ``row`` passes ``row_filter`` for ``user`` (DB-level probe)."""
    if row_filter is None:
        return True
    model_class = data_model.model_class
    check = select(model_class.id).where(model_class.id == row.id)
    if data_model.is_versioned:
        check = check.where(model_class.version == row.version)
    check = row_filter(check, db, user)
    return db.scalars(check).first() is not None


def _row_visible(db: Session, user: WorkflowUser, data_model: DataModelDescriptor, row) -> bool:
    """Whether ``row`` passes the model's ``row_filter`` for ``user``."""
    row_filter = data_model.api.row_filter if data_model.api else None
    return _passes_row_filter(db, user, row_filter, data_model, row)


def _action_allows(db: Session, user: WorkflowUser, data_model: DataModelDescriptor, action, row) -> bool:
    """Whether ``action``'s ``row_filter`` admits ``row`` for ``user``."""
    return _passes_row_filter(db, user, action.row_filter, data_model, row)


def _load_head_row(db: Session, user: WorkflowUser, data_model: DataModelDescriptor, row_id: uuid.UUID):
    """Load the current (head) row for ``row_id`` if visible, else raise.

    Actions act on the current version: a stale/superseded id must not start a
    follow-up workflow. Versioned models select ``is_current``; non-versioned
    models have a single row per id.
    """
    model_class = data_model.model_class
    row = db.scalars(views_data_model.current_rows_query(data_model).where(model_class.id == row_id)).first()
    if row is None or not _row_visible(db, user, data_model, row):
        raise DataModelRowNotFoundError("Row not found")
    return row


def _load_version_row(db: Session, user: WorkflowUser, data_model: DataModelDescriptor, row_id: uuid.UUID, version: int | None):
    """Load a specific version of ``row_id`` if visible, else raise (for attachment downloads,
    which deliberately serve historical versions). Non-versioned models ignore ``version``."""
    model_class = data_model.model_class
    if data_model.is_versioned:
        row = db.get(model_class, (row_id, version))
    else:
        row = db.get(model_class, row_id)
    if row is None or not _row_visible(db, user, data_model, row):
        raise DataModelRowNotFoundError("Row not found")
    return row


# ---------------------------------------------------------------------------
# Read operations
# ---------------------------------------------------------------------------


def list_models(*, db: Session, user_id: uuid.UUID) -> list[DataModelSchema]:
    """List the workflow-data models the user may read, with field schema + row count.

    Models the user may read but currently sees zero rows in (read role present,
    but ``row_filter`` filters everything out, or the model is simply empty) are
    omitted from the overview.
    """
    user = repository.load_workflow_user(db, user_id)
    result: list[DataModelSchema] = []
    for data_model in data_model_registry.list_models():
        if not (data_model.api and _user_has_read_access(user, data_model)):
            continue
        count = views_data_model.count_visible_rows(data_model, db, user)
        if count == 0:
            continue
        result.append(views_data_model.data_model_schema(data_model, row_count=count, locale=user.locale))
    return result


def list_rows(
    *,
    db: Session,
    user_id: uuid.UUID,
    data_model: DataModelDescriptor,
    request_params: BffTableQuerySchemaBase,
) -> ListRowsResponse:
    """List the latest version of each row the user may read (paginated/filtered/sorted)."""
    user = _require_read_access(db, user_id, data_model)
    return views_data_model.list_rows(data_model, request_params, db, user)


def get_version_chain(
    *,
    db: Session,
    user_id: uuid.UUID,
    data_model: DataModelDescriptor,
    row_id: uuid.UUID,
) -> VersionChainResponse:
    """Return the full version chain for one record id (oldest first).

    Visibility is decided on the head (latest version): if the user may see the
    current row, they may see its full history. This suits role-based row_filters.
    Participation-based filters (add_workflow_participant_filter) are a poorer fit
    here — a user who only participates in the newest version still sees older
    ones; apply a per-version filter instead if that matters for a model.
    """
    user = _require_read_access(db, user_id, data_model)
    chain = views_data_model.walk_version_chain(data_model, db, row_id)
    if chain is None:
        raise DataModelRowNotFoundError("Row not found")
    head = chain[-1]
    if not _row_visible(db, user, data_model, head):
        raise DataModelRowNotFoundError("Row not found")
    # The follow-up workflows startable on the current (head) version — the detail
    # page offers them like the table does per row.
    head_actions = views_data_model.actions_by_row(data_model, [head], db, user).get(head.id, [])
    return views_data_model.version_chain_response(data_model, chain, head_actions, db=db, locale=user.locale)


def export_rows_csv(
    *,
    db: Session,
    user_id: uuid.UUID,
    data_model: DataModelDescriptor,
    request_params: BffTableQuerySchemaBase | None = None,
) -> tuple[str, str]:
    """Return ``(csv_content, filename)`` of the rows of a model the user may read.

    Exports the active table view: with ``request_params`` the same filter/search/
    sort machinery as the listing applies (never paginated — the export always
    holds the complete filtered set); without params the full model. Read scope
    (``row_filter``) applies in both cases.
    """
    user = _require_read_access(db, user_id, data_model)
    rows = views_data_model.all_rows(data_model, db, user, request_params=request_params)
    return views_data_model.rows_to_csv(data_model, rows, db=db, locale=user.locale), f"{data_model.name}.csv"


# ---------------------------------------------------------------------------
# Involved processes (reverse scan of each workflow's DATA_MODELS allow-list)
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _model_to_workflows(workflow_names: tuple[str, ...]) -> dict[str, list[str]]:
    """Import every workflow module and group workflows by the models they declare.

    The sorted workflow-name set is the cache key: the scan imports every workflow
    module (to read its ``DATA_MODELS``), so it reruns only when the set of
    workflows changes (e.g. provider reload); ``maxsize=1`` keeps just the current
    set. Note the scope: a change to a workflow's ``DATA_MODELS`` *without* a
    change to the workflow-name set does not invalidate — irrelevant in production
    (static modules), only a concern under dev hot-reload of an existing workflow.
    """
    mapping: dict[str, list[str]] = {}
    for name in workflow_names:
        module_path = workflow_providers.get_workflow_module_path(name)
        if not module_path:
            continue
        try:
            module = importlib.import_module(module_path)
        except Exception:
            log.warning("Could not import workflow module %s for data-model reverse scan", module_path, exc_info=True)
            continue
        for model_name in getattr(module, "DATA_MODELS", None) or []:
            mapping.setdefault(model_name, []).append(name)
    return mapping


def workflows_using_model(model_name: str) -> list[str]:
    """Names of workflows that declare *model_name* in their module-level ``DATA_MODELS``.

    The reverse of the per-workflow ``DATA_MODELS`` allow-list: every process that
    reads or writes a given data model.
    """
    workflow_names = tuple(sorted(workflow_providers.iter_workflow_names()))
    return list(_model_to_workflows(workflow_names).get(model_name, []))


def list_processes_for_model(*, db: Session, user_id: uuid.UUID, data_model: DataModelDescriptor) -> list[ProcessRefSchema]:
    """Workflows that use the model and that the current user may start.

    Backs the "involved processes" picker on the data-model detail page: a model
    can be touched by several workflows, and only those the user may execute are
    offered (their own initiator roles apply, via ``user_may_start_workflow``).
    """
    _require_read_access(db, user_id, data_model)

    user_rep = repository.load_user(db=db, user_id=user_id)
    return [
        ProcessRefSchema(name=name, title=service_workflow.get_workflow_title_cached(name, locale=user_rep.locale))
        for name in workflows_using_model(data_model.name)
        if service_workflow.user_may_start_workflow(name, user_rep)
    ]


# ---------------------------------------------------------------------------
# Attachment download (authorized by data-model read access, not task assignment)
# ---------------------------------------------------------------------------


def load_row_attachment(
    *,
    db: Session,
    user_id: uuid.UUID,
    data_model: DataModelDescriptor,
    row_id: uuid.UUID,
    version: int | None,
    file_hash: str,
) -> Attachment:
    """Load an attachment referenced by a specific version of a row, authorized via
    data-model read access.

    The ``file_hash`` must be referenced by a ``file`` field of *this* version, so a
    user with read access cannot pull arbitrary global attachments by hash. A
    specific ``version`` is addressed so historical versions' files stay reachable.
    """
    user = _require_read_access(db, user_id, data_model)

    row = _load_version_row(db, user, data_model, row_id, version)
    row_version = getattr(row, "version", 0) or 0

    # Ownership + filename come from the side table: a file row for this exact
    # version must reference the hash. The per-row filename names the download in
    # this record's context (the deduped attachment's first_filename may differ).
    side = repository.find_data_model_file_by_hash(db, data_model.name, row.id, row_version, file_hash)
    if side is None or side.attachment.file is None:
        raise DataModelRowNotFoundError("Attachment not found")

    return Attachment(
        id=side.attachment.id,
        hash=side.attachment.hash,
        filename=side.filename,
        mimetype=side.mimetype or side.attachment.mimetype,
        data=get_file_content(side.attachment.file.file_id),
    )


# ---------------------------------------------------------------------------
# Action execution (start a follow-up workflow from a row)
# ---------------------------------------------------------------------------


def start_workflow_for_existing_data_model(
    *,
    db: Session,
    user_id: uuid.UUID,
    data_model: DataModelDescriptor,
    row_id: uuid.UUID,
    action_key: str,
) -> uuid.UUID:
    """Start the follow-up workflow declared as action ``action_key`` on a row.

    ``UserMayNotStartWorkflowException`` from the workflow start propagates to the
    BFF, which maps it like the plain start_workflow route.
    """
    user = _require_read_access(db, user_id, data_model)

    row = _load_head_row(db, user, data_model, row_id)

    actions = data_model.api.actions if data_model.api else []
    action = next((a for a in actions if a.key == action_key), None)
    if action is None:
        raise DataModelRowNotFoundError(f"Action '{action_key}' not found")

    if not _action_allows(db, user, data_model, action, row):
        raise DataModelForbiddenError("Action not allowed on this row")

    payload = action.payload(row) if action.payload else {"source_id": str(row.id)}

    return service_application.start_workflow(
        db=db,
        name=action.target,
        user_id=user_id,
        initial_task_data=payload,
        # The payload is server-built and trusted, so it is applied to the target's
        # first form as-is: its technical fields (e.g. a source row id) survive even
        # though the form has no field for them, and it is not subjected to form
        # validation. The client supplies no free-form data.
        trusted_seed=True,
    )
