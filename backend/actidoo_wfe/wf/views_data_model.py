# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""Read-models for the workflow-data API.

This module is the projection layer: it turns SQLAlchemy data models and their
``WorkflowDataApiConfig`` into the typed wire schemas, runs the paginated/filtered
queries via the shared ``BFFTable`` engine, and walks version chains. It contains
no HTTP or authorization logic — that lives in ``service_data_model``.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import json
import logging
import uuid
from decimal import Decimal
from typing import Any, Literal

import sqlalchemy as sa
from sqlalchemy import func, select
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import Session

import actidoo_wfe.wf.service_i18n as service_i18n
from actidoo_wfe.database import FlexibleUuid, JSONBlob, UTCDateTime, ZlibJSONBlob
from actidoo_wfe.helpers.bff_table import (
    BFFTable,
    BffTableQuerySchemaBase,
    BooleanFilterField,
    DatetimeSearchFilterField,
    FilterField,
    IntegerSearchFilterField,
    TextSearchFilterField,
    UUidSearchFilterField,
)
from actidoo_wfe.settings import settings
from actidoo_wfe.wf.config_data_model import DisplayType, FieldDef
from actidoo_wfe.wf.models import _MIXIN_SYSTEM_COLUMNS, WorkflowUser
from actidoo_wfe.wf.registry_data_model import DataModelDescriptor
from actidoo_wfe.wf.types_data_model import (
    ActionSchema,
    DataModelSchema,
    FieldSchema,
    ListRowsResponse,
    RowResponse,
    VersionChainResponse,
    VersionEntry,
)

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Display-type inference (default; FieldDef.type/format are authoritative)
# ---------------------------------------------------------------------------


def display_type(col_type) -> DisplayType:
    """Map a SQLAlchemy column type to a frontend display type.

    Order matters: the JSON blobs report ``python_type == str`` and must be
    caught before the generic ``python_type`` fallback. ``file`` is never
    inferred — it must be declared explicitly via ``FieldDef(type="file")``.
    """
    if isinstance(col_type, (JSONBlob, ZlibJSONBlob)):
        return "string"
    if isinstance(col_type, FlexibleUuid):
        return "string"
    if isinstance(col_type, (UTCDateTime, sa.DateTime, sa.TIMESTAMP)):
        return "datetime"
    if isinstance(col_type, sa.Date):
        return "date"
    if isinstance(col_type, sa.Boolean):
        return "boolean"
    if isinstance(col_type, sa.Float):
        return "number"
    if isinstance(col_type, sa.Numeric):
        return "decimal"
    if isinstance(col_type, sa.Integer):
        return "number"
    try:
        python_type = col_type.python_type
    except NotImplementedError:
        return "string"
    if python_type is uuid.UUID:
        return "string"
    if python_type is bool:
        return "boolean"
    if python_type is Decimal:
        return "decimal"
    if python_type in (int, float):
        return "number"
    if python_type is dt.datetime:
        return "datetime"
    if python_type is dt.date:
        return "date"
    if python_type is str:
        return "string"
    log.warning("No display-type mapping for column type %r; defaulting to 'string'", col_type)
    return "string"


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


def _serialize_value(value: Any, display: DisplayType | None = None) -> Any:
    """Convert a value to a JSON-safe representation for the given display type."""
    if value is None:
        return None
    if isinstance(value, dt.datetime):
        return value.isoformat()
    if isinstance(value, dt.date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _column_map(model_class: type) -> dict:
    return {col.key: col for col in sa_inspect(model_class).columns}


def _project_identity(row: Any, data_model: DataModelDescriptor, result: dict) -> None:
    """Always carry the stable ``id``, the record ``title`` (and ``version`` for
    versioned models) in a serialized row, so the client can build action/download/
    version-chain URLs and show the record's name even when the model does not list
    them among its display fields."""
    if "id" not in result:
        result["id"] = _serialize_value(getattr(row, "id", None), "string")
    if "title" not in result:
        result["title"] = _serialize_value(getattr(row, "title", None), "string")
    if data_model.is_versioned and "version" not in result:
        result["version"] = getattr(row, "version", None)


def _safe_compute(field: FieldDef, row: Any) -> Any:
    """Evaluate a computed field defensively.

    Computed fields run author-provided callables; a failure on one row/field must
    not 500 the whole page. On error we log and yield ``None``.
    """
    try:
        return field.compute(row)
    except Exception:
        log.warning("compute for field %r failed; serializing as None", field.name, exc_info=True)
        return None


def serialize_row(
    row: Any,
    data_model: DataModelDescriptor,
    file_refs_by_field: dict[str, list[dict]] | None = None,
    *,
    context: FieldContext | None = None,
) -> dict:
    """Serialize a model instance to a JSON-safe dict, respecting the field config.

    ``file`` fields have no backing column — their references live in the
    ``data_model_files`` side table. Callers pass the row's already-batch-loaded
    refs as ``file_refs_by_field`` (see ``files_by_row``); without it, file fields
    serialize as empty (used only off the hot path, e.g. callers with no files).

    With *context* set, fields hidden in that presentation context are dropped, so
    the row data matches the schema ``field_metadata`` builds for the same context
    (and verbose detail-only fields never ride along in the table list payload).
    """
    file_refs_by_field = file_refs_by_field or {}
    fields = data_model.api.fields if data_model.api else None
    if fields is None:
        result: dict[str, Any] = {
            col.key: _serialize_value(getattr(row, col.key), display_type(col.type))
            for col in sa_inspect(type(row)).columns
            if col.key not in _MIXIN_SYSTEM_COLUMNS
        }
        _project_identity(row, data_model, result)
        return result

    col_map = _column_map(type(row))
    result = {}
    for field in fields:
        if context is not None and not _field_visible(field, context):
            continue
        if field.type == "file":
            result[field.name] = file_refs_by_field.get(field.name, [])
            continue
        if field.is_computed:
            result[field.name] = _serialize_value(_safe_compute(field, row), field.type or "string")
            continue
        col = col_map.get(field.name)
        if col is None:
            # Unknown column: skip, mirroring ``field_metadata`` so the row data and
            # the schema agree (no ``None`` ghost for a mistyped field name).
            continue
        result[field.name] = _serialize_value(getattr(row, field.name), field.type or display_type(col.type))
    _project_identity(row, data_model, result)
    return result


def _model_has_file_fields(data_model: DataModelDescriptor) -> bool:
    fields = data_model.api.fields if data_model.api else None
    return any(f.type == "file" for f in (fields or []))


def files_by_row(
    data_model: DataModelDescriptor,
    rows: list,
    db: Session,
) -> dict[tuple[uuid.UUID, int], dict[str, list[dict]]]:
    """Batch-load the file references of a page of rows, keyed by
    ``(row_id, row_version)`` then field name (ordered by ``position``).

    One query for the whole page — mirrors the ``actions_by_row`` secondary-query
    pattern so file fields stay free of an N+1.
    """
    from actidoo_wfe.wf import repository

    if not _model_has_file_fields(data_model) or not rows:
        return {}
    keys = [(row.id, getattr(row, "version", 0) or 0) for row in rows]
    result: dict[tuple[uuid.UUID, int], dict[str, list[dict]]] = {}
    for file in repository.find_data_model_files_for_rows(db, data_model.name, keys):
        by_field = result.setdefault((file.row_id, file.row_version), {})
        by_field.setdefault(file.field_name, []).append(
            {
                "id": str(file.workflow_attachment_id),
                "hash": file.attachment.hash,
                "filename": file.filename,
                "mimetype": file.mimetype,
            }
        )
    return result


def _file_refs_for(files_map: dict, row: Any) -> dict[str, list[dict]]:
    """The per-field file refs for one row from a ``files_by_row`` map."""
    return files_map.get((row.id, getattr(row, "version", 0) or 0), {})


# ---------------------------------------------------------------------------
# Field-schema projection
# ---------------------------------------------------------------------------


def resolve_label(data_model: DataModelDescriptor, label: str | None, locale: str | None, fallback: str) -> str:
    """Resolve a declared label (gettext msgid) to the requesting user's locale.

    Uses the model's catalog (``i18n/locales/<locale>/LC_MESSAGES/<name>.mo`` next
    to the model module — the same Babel toolchain as the per-workflow catalogs).
    Missing catalog or translation yields the msgid itself; ``None``/empty labels
    fall back to *fallback* (usually the field or model name) — the wire schema
    always carries a plain string.
    """
    if not label:
        return fallback
    if data_model.i18n_dir is None:
        return label
    return service_i18n.translate_string(
        msgid=label,
        workflow_name=data_model.name,
        locale=locale or settings.default_locale,
        base_i18n_dir=data_model.i18n_dir,
    )


def _field_schema_from_column(
    col, override: FieldDef | None = None, *, data_model: DataModelDescriptor, locale: str | None = None
) -> FieldSchema:
    override_type = override.type if override and override.type else None
    return FieldSchema(
        name=col.key,
        label=resolve_label(data_model, override.label if override else None, locale, col.key),
        type=(override_type or display_type(col.type)),
        format=(override.format if override else None),
        nullable=bool(col.nullable),
        primary_key=bool(col.primary_key),
        virtual=False,
        sortable=True,  # DB-backed columns are sortable
        filterable=_filter_field_for(col.key, col, override_type) is not None,
    )


# Presentation context a field list is projected for. ``None`` means "no filtering"
# (every declared field), preserving the behaviour of callers that don't pass one.
FieldContext = Literal["table", "detail", "csv"]


def _field_visible(field: FieldDef, context: FieldContext) -> bool:
    """Whether *field* is shown in *context*, per its include_in_* flags."""
    if context == "table":
        return field.include_in_table
    if context == "detail":
        return field.include_in_detail
    return field.include_in_csv  # csv


def field_metadata(
    data_model: DataModelDescriptor, *, context: FieldContext | None = None, locale: str | None = None
) -> list[FieldSchema]:
    """Build the field schema for a model, merging FieldDef bits with inspection.

    With *context* set, fields hidden in that presentation context are dropped, so
    the schema matches what ``serialize_row`` emits for the same context.
    """
    model_class = data_model.model_class
    fields = data_model.api.fields if data_model.api else None
    if fields is None:
        return [
            _field_schema_from_column(col, data_model=data_model, locale=locale)
            for col in sa_inspect(model_class).columns
            if col.key not in _MIXIN_SYSTEM_COLUMNS
        ]

    col_map = _column_map(model_class)
    result: list[FieldSchema] = []
    for field in fields:
        if context is not None and not _field_visible(field, context):
            continue
        if field.is_computed or field.type == "file":
            # Computed and file fields are framework-managed virtual fields with no
            # backing column (file refs live in the data_model_files side table).
            result.append(
                FieldSchema(
                    name=field.name,
                    label=resolve_label(data_model, field.label, locale, field.name),
                    type=field.type or "string",
                    format=field.format,
                    nullable=True,
                    primary_key=False,
                    virtual=True,
                    sortable=False,  # no DB column to sort by
                    filterable=False,
                )
            )
        else:
            col = col_map.get(field.name)
            if col is not None:
                result.append(_field_schema_from_column(col, field, data_model=data_model, locale=locale))
    return result


def data_model_schema(
    data_model: DataModelDescriptor,
    row_count: int | None = None,
    *,
    context: FieldContext | None = None,
    locale: str | None = None,
) -> DataModelSchema:
    return DataModelSchema(
        name=data_model.name,
        label=resolve_label(data_model, data_model.api.label if data_model.api else None, locale, data_model.name),
        fields=field_metadata(data_model, context=context, locale=locale),
        row_count=row_count,
        has_actions=bool(data_model.api.actions) if data_model.api else False,
    )


# ---------------------------------------------------------------------------
# BFFTable wiring (filter / sort fields derived from the schema)
# ---------------------------------------------------------------------------


def _filter_field_for(name: str, col, override_type: DisplayType | None) -> FilterField | None:
    """Pick a BFFTable filter field from the SQLAlchemy column type.

    Derived from the column type (not the display type), since uuid collapses to
    ``string`` there. ``decimal``/float/json columns get no filter for now.
    """
    if override_type == "file":
        return None
    col_type = col.type
    if isinstance(col_type, FlexibleUuid):
        return UUidSearchFilterField(name=name)
    if isinstance(col_type, (UTCDateTime, sa.DateTime, sa.TIMESTAMP, sa.Date)):
        return DatetimeSearchFilterField(name=name)
    if isinstance(col_type, sa.Boolean):
        return BooleanFilterField(name=name)
    if isinstance(col_type, sa.Integer):
        return IntegerSearchFilterField(name=name)
    if isinstance(col_type, sa.String):
        return TextSearchFilterField(name=name)
    try:
        python_type = col_type.python_type
    except NotImplementedError:
        python_type = None
    if python_type is uuid.UUID:
        return UUidSearchFilterField(name=name)
    if python_type is str:
        return TextSearchFilterField(name=name)
    if python_type is bool:
        return BooleanFilterField(name=name)
    if python_type is int:
        return IntegerSearchFilterField(name=name)
    return None


def _db_backed_entries(data_model: DataModelDescriptor) -> list[tuple[str, Any, FieldDef | None]]:
    """Return ``(name, column, field_def|None)`` for every DB-backed field."""
    model_class = data_model.model_class
    col_map = _column_map(model_class)
    fields = data_model.api.fields if data_model.api else None
    entries: list[tuple[str, Any, FieldDef | None]] = []
    if fields is None:
        for col in sa_inspect(model_class).columns:
            if col.key not in _MIXIN_SYSTEM_COLUMNS:
                entries.append((col.key, col, None))
    else:
        for field in fields:
            col = col_map.get(field.name)
            if col is not None:  # skip computed / unknown
                entries.append((field.name, col, field))
    return entries


def table_spec(data_model: DataModelDescriptor) -> tuple[list[str], list[FilterField], dict]:
    """Derive ``(sorting_fields, filter_fields, field_to_dbfield_map)`` from the schema."""
    model_class = data_model.model_class
    sorting_fields: list[str] = []
    filter_fields: list[FilterField] = []
    field_to_dbfield_map: dict = {}
    for name, col, field in _db_backed_entries(data_model):
        sorting_fields.append(name)
        field_to_dbfield_map[name] = getattr(model_class, name)
        ff = _filter_field_for(name, col, field.type if field else None)
        if ff is not None:
            filter_fields.append(ff)
    # The reserved record title is always searchable/sortable/filterable, even when
    # the model does not declare it as a display field — every record stays findable
    # by its human-readable name via the global search.
    if "title" not in field_to_dbfield_map and hasattr(model_class, "title"):
        sorting_fields.append("title")
        field_to_dbfield_map["title"] = model_class.title
        title_ff = _filter_field_for("title", sa_inspect(model_class).columns["title"], None)
        if title_ff is not None:
            filter_fields.append(title_ff)
    return sorting_fields, filter_fields, field_to_dbfield_map


# ---------------------------------------------------------------------------
# Read operations
# ---------------------------------------------------------------------------


def current_rows_query(data_model: DataModelDescriptor):
    """``select(model)`` over the current rows: the head version for versioned
    models (``is_current``), or every row for non-versioned models."""
    model_class = data_model.model_class
    query = select(model_class)
    if data_model.is_versioned:
        query = query.where(model_class.is_current.is_(True))
    return query


def actions_by_row(data_model: DataModelDescriptor, rows: list, db: Session, user: WorkflowUser) -> dict:
    """Map each row's stable id to the actions available on it (via each ``row_filter``).

    Each action's ``row_filter`` is run once over the page's ids (a DB query),
    scoped to the head version, so eligibility is decided at the DB level.
    """
    actions = data_model.api.actions if data_model.api else []
    if not actions or not rows:
        return {}
    model_class = data_model.model_class
    page_ids = [row.id for row in rows]
    result: dict = {pk: [] for pk in page_ids}
    for action in actions:
        query = select(model_class.id).where(model_class.id.in_(page_ids))
        if data_model.is_versioned:
            query = query.where(model_class.is_current.is_(True))
        if action.row_filter is not None:
            query = action.row_filter(query, db, user)
        schema = ActionSchema(
            key=action.key,
            label=resolve_label(data_model, action.label, user.locale, action.key),
            target=action.target,
        )
        for pk in db.scalars(query).all():
            result[pk].append(schema)
    return result


def _visible_rows_query(data_model: DataModelDescriptor, db: Session, user: WorkflowUser):
    """Base query for everything the user may see: current rows narrowed by the
    model's ``row_filter``. Shared by listing, export and the catalog count, so
    the three can never drift apart."""
    query = current_rows_query(data_model)
    if data_model.api and data_model.api.row_filter:
        query = data_model.api.row_filter(query, db, user)
    return query


def list_rows(
    data_model: DataModelDescriptor,
    request_params: BffTableQuerySchemaBase,
    db: Session,
    user: WorkflowUser,
) -> ListRowsResponse:
    """List the current rows (head version for versioned models), paginated/filtered/sorted."""
    model_class = data_model.model_class
    query = _visible_rows_query(data_model, db, user)

    _, _, field_to_dbfield_map = table_spec(data_model)
    bff_table = BFFTable(
        db=db,
        request_params=request_params,
        query=query,
        field_to_dbfield_map=field_to_dbfield_map,
        default_order_by=model_class.id.asc(),
    )
    paginated = bff_table.get_paginated_data()

    actions_map = actions_by_row(data_model, paginated.items, db, user)
    files_map = files_by_row(data_model, paginated.items, db)
    items = [
        RowResponse(
            data=serialize_row(row, data_model, _file_refs_for(files_map, row), context="table"),
            actions=actions_map.get(row.id, []),
        )
        for row in paginated.items
    ]
    return ListRowsResponse(
        ITEMS=items,
        COUNT=paginated.count,
        model=data_model_schema(data_model, context="table", locale=user.locale),
    )


def walk_version_chain(data_model: DataModelDescriptor, db: Session, record_id: uuid.UUID) -> list | None:
    """The full version chain for one record id (oldest first).

    Versioned models return every version ordered by ``version``; non-versioned
    models return the single row (``[row]``). ``None`` if the id does not exist.
    """
    model_class = data_model.model_class
    if data_model.is_versioned:
        rows = list(db.scalars(select(model_class).where(model_class.id == record_id).order_by(model_class.version.asc())).all())
        return rows or None
    row = db.get(model_class, record_id)
    return [row] if row is not None else None


def version_chain_response(
    data_model: DataModelDescriptor,
    chain: list,
    actions: list[ActionSchema] | None = None,
    *,
    db: Session,
    locale: str | None = None,
) -> VersionChainResponse:
    files_map = files_by_row(data_model, chain, db)
    return VersionChainResponse(
        versions=[
            VersionEntry(
                data=serialize_row(row, data_model, _file_refs_for(files_map, row), context="detail"),
                created_at=getattr(row, "created_at", None),
                action=getattr(row, "action", None),
            )
            for row in chain
        ],
        model=data_model_schema(data_model, context="detail", locale=locale),
        actions=actions or [],
    )


# ---------------------------------------------------------------------------
# CSV export
# ---------------------------------------------------------------------------


def all_rows(
    data_model: DataModelDescriptor,
    db: Session,
    user: WorkflowUser,
    request_params: BffTableQuerySchemaBase | None = None,
) -> list:
    """All current rows of a model (read-scoped via ``row_filter``), unpaginated.

    With ``request_params`` the rows are narrowed and ordered by the same
    filter/search/sort machinery as ``list_rows`` — but never paginated, so an
    export always contains the complete filtered view.
    """
    query = _visible_rows_query(data_model, db, user)
    if request_params is None:
        return list(db.scalars(query.order_by(data_model.model_class.id.asc())).all())

    _, _, field_to_dbfield_map = table_spec(data_model)
    bff_table = BFFTable(
        db=db,
        request_params=request_params,
        query=query,
        field_to_dbfield_map=field_to_dbfield_map,
        default_order_by=data_model.model_class.id.asc(),
    )
    return bff_table.get_all_data()


def count_visible_rows(data_model: DataModelDescriptor, db: Session, user: WorkflowUser) -> int:
    """Number of current rows the user may see (head version + ``row_filter``).

    Mirrors ``list_rows``' base query so the catalog count matches the table.
    """
    query = _visible_rows_query(data_model, db, user)
    return db.scalar(select(func.count()).select_from(query.subquery())) or 0


def _neutralize_formula(text: str) -> str:
    """Defang CSV/formula injection: a cell that a spreadsheet would evaluate as a
    formula (leading ``=``, ``+``, ``-``, ``@`` after optional whitespace) is
    prefixed with an apostrophe so Excel/Sheets treat it as literal text.

    Applied to every exported cell, so it is model-agnostic — exported values come
    from workflow forms and are attacker-controllable.
    """
    if text and text.lstrip()[:1] in ("=", "+", "-", "@"):
        return "'" + text
    return text


def _csv_cell(value: Any) -> str:
    """Flatten a serialized value to a single, formula-safe CSV cell."""
    if value is None:
        return ""
    if isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, dict):  # file refs
                parts.append(str(item.get("filename") or item.get("hash") or ""))
            else:
                parts.append(str(item))
        return _neutralize_formula(", ".join(parts))
    if isinstance(value, dict):
        return _neutralize_formula(json.dumps(value, ensure_ascii=False))
    return _neutralize_formula(str(value))


def rows_to_csv(data_model: DataModelDescriptor, rows: list, *, db: Session, locale: str | None = None) -> str:
    """Serialize rows to CSV (header = field labels, columns = field order).

    The header carries the labels resolved to *locale* — consumers parsing the
    header must match by position or request a fixed locale.
    """
    fields = field_metadata(data_model, context="csv", locale=locale)
    files_map = files_by_row(data_model, rows, db)
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow([field.label for field in fields])
    for row in rows:
        data = serialize_row(row, data_model, _file_refs_for(files_map, row), context="csv")
        writer.writerow([_csv_cell(data.get(field.name)) for field in fields])
    return output.getvalue()
