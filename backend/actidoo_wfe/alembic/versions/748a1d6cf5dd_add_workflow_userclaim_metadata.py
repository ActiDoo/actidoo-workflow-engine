# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""add workflow userclaim metadata

Revision ID: 748a1d6cf5dd
Revises: 4bb6f2f6f4c2
Create Date: 2025-12-09 16:40:19.447702

"""
from alembic import op
import sqlalchemy as sa
import actidoo_wfe.database

# revision identifiers, used by Alembic.
revision = '748a1d6cf5dd'
down_revision = '4bb6f2f6f4c2'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column('workflow_user_claims', sa.Column('source_name', sa.String(length=255), nullable=True))
    op.add_column('workflow_user_claims', sa.Column('fetched_at', actidoo_wfe.database.UTCDateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('workflow_user_claims', 'fetched_at')
    op.drop_column('workflow_user_claims', 'source_name')
