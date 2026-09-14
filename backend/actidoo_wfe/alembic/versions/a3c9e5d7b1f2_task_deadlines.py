# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 ActiDoo GmbH

"""task deadlines

Revision ID: a3c9e5d7b1f2
Revises: 7f2e1a9c4b30
Create Date: 2026-09-14 12:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
import actidoo_wfe.database

# revision identifiers, used by Alembic.
revision = "a3c9e5d7b1f2"
down_revision = "7f2e1a9c4b30"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "workflow_instance_tasks",
        sa.Column("urgency_at", actidoo_wfe.database.UTCDateTime(), nullable=True),
    )
    op.add_column(
        "workflow_instance_tasks",
        sa.Column("critical_at", actidoo_wfe.database.UTCDateTime(), nullable=True),
    )
    op.create_index("ix_workflow_instance_tasks_urgency_at", "workflow_instance_tasks", ["urgency_at"])
    op.create_index("ix_workflow_instance_tasks_critical_at", "workflow_instance_tasks", ["critical_at"])


def downgrade() -> None:
    op.drop_index("ix_workflow_instance_tasks_critical_at", table_name="workflow_instance_tasks")
    op.drop_index("ix_workflow_instance_tasks_urgency_at", table_name="workflow_instance_tasks")
    op.drop_column("workflow_instance_tasks", "critical_at")
    op.drop_column("workflow_instance_tasks", "urgency_at")
