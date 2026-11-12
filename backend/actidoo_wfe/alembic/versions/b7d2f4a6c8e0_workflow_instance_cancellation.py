# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 ActiDoo GmbH

"""workflow instance cancellation

Revision ID: b7d2f4a6c8e0
Revises: a3c9e5d7b1f2
Create Date: 2026-10-23 12:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "b7d2f4a6c8e0"
down_revision = "a3c9e5d7b1f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("workflow_instances", sa.Column("cancelled_by_id", sa.Uuid(), nullable=True))
    op.add_column("workflow_instances", sa.Column("cancel_reason", sa.Text(), nullable=True))
    op.create_foreign_key(
        "fk_workflow_instances_cancelled_by_id_workflow_users",
        "workflow_instances",
        "workflow_users",
        ["cancelled_by_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_workflow_instances_cancelled_by_id_workflow_users", "workflow_instances", type_="foreignkey")
    op.drop_column("workflow_instances", "cancel_reason")
    op.drop_column("workflow_instances", "cancelled_by_id")
