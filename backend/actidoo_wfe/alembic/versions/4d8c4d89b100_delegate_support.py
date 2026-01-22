# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""delegate support

Revision ID: 4d8c4d89b100
Revises: b2cbdf43f36f
Create Date: 2025-11-13 10:02:43.312832

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '4d8c4d89b100'
down_revision = 'b2cbdf43f36f'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'workflow_user_delegates',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('principal_user_id', sa.Uuid(), nullable=False),
        sa.Column('delegate_user_id', sa.Uuid(), nullable=False),
        sa.Column('valid_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['delegate_user_id'], ['workflow_users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['principal_user_id'], ['workflow_users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('principal_user_id', 'delegate_user_id')
    )
    op.create_index('ix_workflow_user_delegates_principal_user_id', 'workflow_user_delegates', ['principal_user_id'])
    op.create_index('ix_workflow_user_delegates_delegate_user_id', 'workflow_user_delegates', ['delegate_user_id'])
    op.create_index('ix_workflow_user_delegates_valid_until', 'workflow_user_delegates', ['valid_until'])

    op.add_column('workflow_instance_tasks', sa.Column('assigned_delegate_user_id', sa.Uuid(), nullable=True))
    op.add_column('workflow_instance_tasks', sa.Column('completed_by_user_id', sa.Uuid(), nullable=True))
    op.add_column('workflow_instance_tasks', sa.Column('completed_by_delegate_user_id', sa.Uuid(), nullable=True))
    op.add_column('workflow_instance_tasks', sa.Column('delegate_submit_comment', sa.Text(), nullable=True))

    op.create_index('ix_workflow_instance_tasks_assigned_delegate_user_id', 'workflow_instance_tasks', ['assigned_delegate_user_id'])
    op.create_index('ix_workflow_instance_tasks_completed_by_user_id', 'workflow_instance_tasks', ['completed_by_user_id'])
    op.create_index('ix_workflow_instance_tasks_completed_by_delegate_user_id', 'workflow_instance_tasks', ['completed_by_delegate_user_id'])

    op.create_foreign_key(
        'fk_wit_assigned_delegate_user_id',
        'workflow_instance_tasks',
        'workflow_users',
        ['assigned_delegate_user_id'],
        ['id']
    )
    op.create_foreign_key(
        'fk_wit_completed_by_user_id',
        'workflow_instance_tasks',
        'workflow_users',
        ['completed_by_user_id'],
        ['id']
    )
    op.create_foreign_key(
        'fk_wit_completed_by_delegate_user_id',
        'workflow_instance_tasks',
        'workflow_users',
        ['completed_by_delegate_user_id'],
        ['id']
    )


def downgrade() -> None:
    op.drop_constraint('fk_wit_completed_by_delegate_user_id', 'workflow_instance_tasks', type_='foreignkey')
    op.drop_constraint('fk_wit_completed_by_user_id', 'workflow_instance_tasks', type_='foreignkey')
    op.drop_constraint('fk_wit_assigned_delegate_user_id', 'workflow_instance_tasks', type_='foreignkey')
    op.drop_index('ix_workflow_instance_tasks_completed_by_delegate_user_id', table_name='workflow_instance_tasks')
    op.drop_index('ix_workflow_instance_tasks_completed_by_user_id', table_name='workflow_instance_tasks')
    op.drop_index('ix_workflow_instance_tasks_assigned_delegate_user_id', table_name='workflow_instance_tasks')
    op.drop_column('workflow_instance_tasks', 'delegate_submit_comment')
    op.drop_column('workflow_instance_tasks', 'completed_by_delegate_user_id')
    op.drop_column('workflow_instance_tasks', 'completed_by_user_id')
    op.drop_column('workflow_instance_tasks', 'assigned_delegate_user_id')

    op.drop_index('ix_workflow_user_delegates_valid_until', table_name='workflow_user_delegates')
    op.drop_index('ix_workflow_user_delegates_delegate_user_id', table_name='workflow_user_delegates')
    op.drop_index('ix_workflow_user_delegates_principal_user_id', table_name='workflow_user_delegates')
    op.drop_table('workflow_user_delegates')
