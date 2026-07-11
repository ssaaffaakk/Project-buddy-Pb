"""add activity_events (product analytics event stream)

Revision ID: a1c9e7d24b31
Revises: 4f4eee5c0502
Create Date: 2026-07-11

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1c9e7d24b31'
down_revision = '4f4eee5c0502'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'activity_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('event', sa.String(length=40), nullable=False),
        sa.Column('object_type', sa.String(length=30), nullable=True),
        sa.Column('object_id', sa.Integer(), nullable=True),
        sa.Column('variant', sa.String(length=10), nullable=True),
        sa.Column('value', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_activity_events_user_id'), 'activity_events', ['user_id'])
    op.create_index(op.f('ix_activity_events_event'), 'activity_events', ['event'])
    op.create_index(op.f('ix_activity_events_created_at'), 'activity_events', ['created_at'])
    op.create_index('ix_activity_events_event_created', 'activity_events', ['event', 'created_at'])


def downgrade():
    op.drop_index('ix_activity_events_event_created', table_name='activity_events')
    op.drop_index(op.f('ix_activity_events_created_at'), table_name='activity_events')
    op.drop_index(op.f('ix_activity_events_event'), table_name='activity_events')
    op.drop_index(op.f('ix_activity_events_user_id'), table_name='activity_events')
    op.drop_table('activity_events')
