# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""add workflow user pinned workflows

Revision ID: a1c7e9f2b4d3
Revises: 4d8c4d89b100
Create Date: 2026-05-27 12:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
import actidoo_wfe.database

# revision identifiers, used by Alembic.
revision = "a1c7e9f2b4d3"
down_revision = "4d8c4d89b100"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workflow_user_pinned_workflows",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("workflow_name", sa.String(length=255), nullable=False),
        sa.Column("created_at", actidoo_wfe.database.UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["workflow_users.id"], name=op.f("fk_workflow_user_pinned_workflows_user_id_workflow_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workflow_user_pinned_workflows")),
        sa.UniqueConstraint("user_id", "workflow_name", name=op.f("uq_workflow_user_pinned_workflows_user_id_workflow_name")),
    )
    op.create_index(op.f("ix_workflow_user_pinned_workflows_user_id"), "workflow_user_pinned_workflows", ["user_id"], unique=False)
    op.create_index(op.f("ix_workflow_user_pinned_workflows_workflow_name"), "workflow_user_pinned_workflows", ["workflow_name"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_workflow_user_pinned_workflows_workflow_name"), table_name="workflow_user_pinned_workflows")
    op.drop_index(op.f("ix_workflow_user_pinned_workflows_user_id"), table_name="workflow_user_pinned_workflows")
    op.drop_table("workflow_user_pinned_workflows")
