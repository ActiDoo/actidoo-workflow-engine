# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""Demo data model for the workflow-data feature reference example.

``DemoExpense`` is a workflow-managed data model: rows are created and versioned
exclusively through the ``TestFlowDemoExpenseCreate`` / ``TestFlowDemoExpenseChange``
workflows. It is registered (and thus exposed via the data API) only when test
workflows are enabled, so it never appears in production.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from actidoo_wfe.settings import settings
from actidoo_wfe.wf.config_data_model import (
    ActionDef,
    FieldDef,
    WorkflowDataApiConfig,
    requires_role,
)
from actidoo_wfe.wf.models import WorkflowManagedMixin, extension_model_base
from actidoo_wfe.wf.registry_data_model import register_data_model

DemoBase = extension_model_base("demo")


class DemoExpense(DemoBase, WorkflowManagedMixin):
    _ext_table = "expense"  # -> __tablename__ = "ext_demo_expense"

    # ``title`` comes from WorkflowManagedMixin (reserved record title) — declaring
    # an own column here would shadow it and fail at registration. The mixin also
    # gives the mandatory ``workflow_instance_id`` provenance, set by the service tasks.
    amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # ``description`` is a verbose free-text field: it would crowd the table list, so
    # it is declared detail-only (FieldDef include_in_table=False below).
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # ``receipt`` is a framework-managed file field (FieldDef type="file" below):
    # its references live in the data_model_files side table, not in a column.


def _editable_rows(query, db, user):
    """Row-level "who may edit": only ``demo-editor`` users, only rows still ``open``."""
    query = requires_role("demo-editor")(query, db, user)
    return query.where(DemoExpense.status == "open")


def register_demo_expense() -> None:
    """Register the demo model. Idempotent (the registry dedups by model class)."""
    register_data_model(
        name="DemoExpense",
        api=WorkflowDataApiConfig(
            # Labels are gettext msgids — the German translations live in
            # ``datamodels/i18n/locales/de/LC_MESSAGES/DemoExpense.po`` (reference
            # example for data-model label i18n, same toolchain as workflows).
            label="Demo Expenses",
            # Read: viewers and editors. Modify: only editors can start the change
            # workflow (its initiator role), see TestFlowDemoExpenseChange.
            read_roles=["demo-viewer", "demo-editor"],
            fields=[
                # The stable id is always projected into the row data for action/
                # download/version URLs; declaring it here also shows it as a column.
                FieldDef("id", label="ID"),
                FieldDef("version", type="number", label="Version"),
                FieldDef("title", label="Title"),
                # ``amount`` renders as a localized currency via the ``format`` hint
                # (frontend buildDataColumns), so no separate label field is needed.
                FieldDef("amount", type="decimal", format="currency:EUR", label="Amount"),
                FieldDef("category", label="Category"),
                FieldDef("status", label="Status"),
                # Per-context field visibility (all three flags default on):
                # - ``description`` is verbose, so it is shown only on the detail page
                #   (``include_in_table=False``) and never bloats the table list payload.
                # - ``receipt`` is a file field with no meaningful CSV cell, so it is
                #   left out of the export (``include_in_csv=False``).
                # The third flag, ``include_in_detail=False``, is the inverse (table-only).
                FieldDef("description", label="Description", include_in_table=False),
                FieldDef("created_at", label="Created"),
                FieldDef("receipt", type="file", label="Receipt", include_in_csv=False),
            ],
            actions=[
                ActionDef(
                    key="edit",
                    label="Edit",
                    target="TestFlowDemoExpenseChange",
                    row_filter=_editable_rows,
                    # Seed the change workflow with the source record id (to append a
                    # new version) plus the current values (to prefill the edit form).
                    payload=lambda row: {
                        "source_id": str(row.id),
                        "title": row.title,
                        "amount": float(row.amount) if row.amount is not None else None,
                        # Seed a string (never None): the edit form's textarea schema
                        # rejects a null prefill.
                        "description": row.description or "",
                    },
                ),
            ],
        ),
    )(DemoExpense)


# Registered only with test workflows enabled — the venusian scan imports this
# module in production too, and we must not expose a demo model there.
if settings.show_test_workflows:
    register_demo_expense()
