# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""sort tasks

Revision ID: ce6f4adda3a1
Revises: 9f1c3fee8890
Create Date: 2024-08-01 11:12:21.936233

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = 'ce6f4adda3a1'
down_revision = '9f1c3fee8890'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('workflow_instance_tasks', sa.Column('sort', sa.Integer(), server_default='0', nullable=False))


def downgrade() -> None:
    op.drop_index(op.f('ix_workflow_instance_tasks_sort'), table_name='workflow_instance_tasks')
  