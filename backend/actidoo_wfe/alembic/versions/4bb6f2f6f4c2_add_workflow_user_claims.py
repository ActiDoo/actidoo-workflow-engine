# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""add workflow user claims

Revision ID: 4bb6f2f6f4c2
Revises: fb45a9433d17
Create Date: 2025-12-03 15:41:00.000000

"""
from alembic import op
import sqlalchemy as sa
import actidoo_wfe.database

# revision identifiers, used by Alembic.
revision = '4bb6f2f6f4c2'
down_revision = 'fb45a9433d17'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'workflow_user_claims',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('claim_key', sa.String(length=255), nullable=False),
        sa.Column('claim_value', actidoo_wfe.database.JSONBlob(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['workflow_users.id'], name=op.f('fk_workflow_user_claims_user_id_workflow_users'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_workflow_user_claims')),
        sa.UniqueConstraint('user_id', 'claim_key', name=op.f('uq_workflow_user_claims_user_id_claim_key'))
    )
    op.create_index(op.f('ix_workflow_user_claims_user_id'), 'workflow_user_claims', ['user_id'], unique=False)
    op.create_index(op.f('ix_workflow_user_claims_claim_key'), 'workflow_user_claims', ['claim_key'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_workflow_user_claims_claim_key'), table_name='workflow_user_claims')
    op.drop_index(op.f('ix_workflow_user_claims_user_id'), table_name='workflow_user_claims')
    op.drop_table('workflow_user_claims')
