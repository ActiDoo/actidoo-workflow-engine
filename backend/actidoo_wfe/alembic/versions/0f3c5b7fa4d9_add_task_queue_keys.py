# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""add key_concurrent and key_dedup to task tables

Revision ID: 0f3c5b7fa4d9
Revises: 748a1d6cf5dd
Create Date: 2025-12-10 06:40:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0f3c5b7fa4d9"
down_revision = "748a1d6cf5dd"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ts_queue", sa.Column("key_concurrent", sa.String(length=255), nullable=True))
    op.add_column("ts_queue", sa.Column("key_dedup", sa.String(length=255), nullable=True))
    op.create_index("ix_ts_queue_key_concurrent", "ts_queue", ["key_concurrent"])
    op.create_index("ix_ts_queue_key_dedup", "ts_queue", ["key_dedup"])

    op.add_column("ts_results", sa.Column("key_concurrent", sa.String(length=255), nullable=True))
    op.add_column("ts_results", sa.Column("key_dedup", sa.String(length=255), nullable=True))
    op.create_index("ix_ts_results_key_concurrent", "ts_results", ["key_concurrent"])
    op.create_index("ix_ts_results_key_dedup", "ts_results", ["key_dedup"])


def downgrade() -> None:
    op.drop_index("ix_ts_results_key_dedup", table_name="ts_results")
    op.drop_index("ix_ts_results_key_concurrent", table_name="ts_results")
    op.drop_column("ts_results", "key_dedup")
    op.drop_column("ts_results", "key_concurrent")

    op.drop_index("ix_ts_queue_key_dedup", table_name="ts_queue")
    op.drop_index("ix_ts_queue_key_concurrent", table_name="ts_queue")
    op.drop_column("ts_queue", "key_dedup")
    op.drop_column("ts_queue", "key_concurrent")
