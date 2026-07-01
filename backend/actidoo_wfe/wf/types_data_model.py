# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""Typed response schemas for the workflow-data API.

The data-model counterpart of ``wf/types.py``: neutral types shared by the
views/service/BFF layers, so the lower layers never import from the ``bff``
package. They are projected from the declarative ``WorkflowDataApiConfig``
(``FieldDef``/``ActionDef``) in ``views_data_model`` — never authored in
parallel — and never contain the Python callables of the definition layer.
"""

from __future__ import annotations

import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from actidoo_wfe.helpers.schema import PaginatedDataSchema
from actidoo_wfe.wf.config_data_model import DisplayType


class FileRef(BaseModel):
    """A single file reference stored in a ``file`` field's JSON metadata."""

    model_config = ConfigDict(from_attributes=True)

    id: str | None = None
    hash: str | None = None
    filename: str | None = None
    mimetype: str | None = None


class FieldSchema(BaseModel):
    """Presentation metadata for a single data-model field."""

    model_config = ConfigDict(from_attributes=True)

    name: str
    label: str
    type: DisplayType
    format: str | None = None
    nullable: bool
    primary_key: bool
    virtual: bool = False
    sortable: bool = False
    filterable: bool = False


class ActionSchema(BaseModel):
    """A follow-up workflow that can be started from a row (client-relevant bits only)."""

    model_config = ConfigDict(from_attributes=True)

    key: str
    label: str
    target: str


class DataModelSchema(BaseModel):
    """The schema of a workflow-data model: its name, label and fields."""

    model_config = ConfigDict(from_attributes=True)

    name: str
    # Human-readable label (falls back to ``name`` server-side when not declared).
    label: str
    fields: list[FieldSchema]
    # Number of rows the current user may see. Only populated in the catalog
    # (``list_models``); ``None`` in the row/version responses.
    row_count: int | None = None
    # Whether the model declares follow-up actions — stable per model, so clients
    # can size/show the actions column independently of the currently loaded page.
    has_actions: bool = False


class ProcessRefSchema(BaseModel):
    """A workflow that uses a data model and that the user may start (for the
    "involved processes" picker on the data-model detail page)."""

    model_config = ConfigDict(from_attributes=True)

    name: str
    title: str


class RowResponse(BaseModel):
    """A single row plus the follow-up workflows available on it."""

    model_config = ConfigDict(from_attributes=True)

    data: dict[str, Any]
    actions: list[ActionSchema] = []


class ListRowsResponse(PaginatedDataSchema[RowResponse]):
    """Paginated rows (``ITEMS``/``COUNT``) plus the model schema."""

    model: DataModelSchema


class VersionEntry(BaseModel):
    """One version of a record: its serialized fields plus metadata guaranteed
    regardless of the declared display fields (the version detail page needs a
    date and an action label per version)."""

    model_config = ConfigDict(from_attributes=True)

    data: dict[str, Any]
    created_at: datetime.datetime | None = None
    action: str | None = None  # what the producing workflow did (CREATE/UPDATE)


class VersionChainResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    versions: list[VersionEntry]
    model: DataModelSchema
    # Follow-up workflows available on the current (head) version for this user —
    # the detail page offers them just like the table does per row.
    actions: list[ActionSchema] = []
