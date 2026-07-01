# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""add data model files

Revision ID: c4e1a7b9d6f2
Revises: a1c7e9f2b4d3
Create Date: 2026-06-13 12:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
import actidoo_wfe.database

# revision identifiers, used by Alembic.
revision = "c4e1a7b9d6f2"
down_revision = "a1c7e9f2b4d3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "data_model_files",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("model_name", sa.String(length=255), nullable=False),
        sa.Column("row_id", actidoo_wfe.database.FlexibleUuid(), nullable=False),
        sa.Column("row_version", sa.Integer(), nullable=False),
        sa.Column("field_name", sa.String(length=255), nullable=False),
        sa.Column("workflow_attachment_id", sa.Uuid(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("mimetype", sa.String(length=255), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("created_at", actidoo_wfe.database.UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(["workflow_attachment_id"], ["workflow_attachments.id"], name=op.f("fk_dmf_attachment"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_data_model_files")),
        sa.UniqueConstraint("model_name", "row_id", "row_version", "field_name", "workflow_attachment_id", name="uq_dmf_ref"),
    )
    op.create_index(op.f("ix_data_model_files_workflow_attachment_id"), "data_model_files", ["workflow_attachment_id"], unique=False)
    op.create_index("ix_dmf_lookup", "data_model_files", ["model_name", "row_id", "row_version"], unique=False)

    # The demo model's former JSON file column. The demo table only exists where
    # test workflows are enabled (created via create_registered_data_model_tables,
    # not Alembic), so guard the drop for environments where it is absent.
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "ext_demo_expense" in inspector.get_table_names():
        columns = {col["name"] for col in inspector.get_columns("ext_demo_expense")}
        if "receipt" in columns:
            op.drop_column("ext_demo_expense", "receipt")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "ext_demo_expense" in inspector.get_table_names():
        columns = {col["name"] for col in inspector.get_columns("ext_demo_expense")}
        if "receipt" not in columns:
            op.add_column("ext_demo_expense", sa.Column("receipt", sa.String(length=1000), nullable=True))

    # drop_table removes the table's indexes and FK in one statement; dropping the
    # FK-backing index separately first would fail on MySQL (1553).
    op.drop_table("data_model_files")
