# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""add workflow user form templates

Revision ID: 7f2e1a9c4b30
Revises: e8b3d5c7a9f1
Create Date: 2026-06-17 09:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
import actidoo_wfe.database

# revision identifiers, used by Alembic.
revision = "7f2e1a9c4b30"
down_revision = "e8b3d5c7a9f1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workflow_user_form_templates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("workflow_name", sa.String(length=255), nullable=False),
        sa.Column("task_name", sa.String(length=255), nullable=False),
        sa.Column("template_name", sa.String(length=255), nullable=False),
        sa.Column("template_data", actidoo_wfe.database.JSONBlob(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["workflow_users.id"],
            name=op.f("fk_workflow_user_form_templates_user_id_workflow_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workflow_user_form_templates")),
    )
    op.create_index(op.f("ix_workflow_user_form_templates_user_id"), "workflow_user_form_templates", ["user_id"], unique=False)
    op.create_index(op.f("ix_workflow_user_form_templates_workflow_name"), "workflow_user_form_templates", ["workflow_name"], unique=False)
    op.create_index(op.f("ix_workflow_user_form_templates_task_name"), "workflow_user_form_templates", ["task_name"], unique=False)
    op.create_index(op.f("ix_workflow_user_form_templates_created_at"), "workflow_user_form_templates", ["created_at"], unique=False)
    op.create_index(
        "uq_workflow_user_form_templates_scope",
        "workflow_user_form_templates",
        ["user_id", "workflow_name", "task_name", "template_name"],
        unique=True,
        mysql_length={"workflow_name": 191, "task_name": 191, "template_name": 191},
    )


def downgrade() -> None:
    op.drop_index("uq_workflow_user_form_templates_scope", table_name="workflow_user_form_templates")
    op.drop_index(op.f("ix_workflow_user_form_templates_created_at"), table_name="workflow_user_form_templates")
    op.drop_index(op.f("ix_workflow_user_form_templates_task_name"), table_name="workflow_user_form_templates")
    op.drop_index(op.f("ix_workflow_user_form_templates_workflow_name"), table_name="workflow_user_form_templates")
    op.drop_index(op.f("ix_workflow_user_form_templates_user_id"), table_name="workflow_user_form_templates")
    op.drop_table("workflow_user_form_templates")
