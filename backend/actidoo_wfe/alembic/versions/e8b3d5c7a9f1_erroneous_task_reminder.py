# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 ActiDoo GmbH

"""erroneous task reminder

Revision ID: e8b3d5c7a9f1
Revises: d4f7a1e9c2b6
Create Date: 2026-07-03 12:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
import actidoo_wfe.database

# revision identifiers, used by Alembic.
revision = "e8b3d5c7a9f1"
down_revision = "d4f7a1e9c2b6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "workflow_users",
        sa.Column("receive_error_task_reminder", sa.Boolean(), nullable=False, server_default="1"),
    )
    op.add_column(
        "workflow_instance_tasks",
        sa.Column("error_at", actidoo_wfe.database.UTCDateTime(), nullable=True),
    )
    op.add_column(
        "workflow_instance_tasks",
        sa.Column("error_reported_at", actidoo_wfe.database.UTCDateTime(), nullable=True),
    )

    # Mark the pre-existing error backlog as an already-reported baseline so the first
    # digest after deploy does not flag every long-standing failure as "* NEW *".
    # error_reported_at is only ever checked for NULL (never displayed or compared by
    # time), so any non-NULL sentinel is enough; CURRENT_TIMESTAMP keeps the intent clear.
    # error_at is deliberately left NULL: the real error time of the backlog is unknown.
    wit = sa.table(
        "workflow_instance_tasks",
        sa.column("state_error"),
        sa.column("error_reported_at"),
    )
    op.execute(
        wit.update().where(wit.c.state_error == sa.true()).values(error_reported_at=sa.func.now())
    )


def downgrade() -> None:
    op.drop_column("workflow_instance_tasks", "error_reported_at")
    op.drop_column("workflow_instance_tasks", "error_at")
    op.drop_column("workflow_users", "receive_error_task_reminder")
