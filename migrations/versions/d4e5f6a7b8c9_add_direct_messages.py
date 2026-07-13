"""add conversations + direct_messages (1:1 DM)

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-07-13

Idempotent: guarded on introspection (create_all may already have created the
tables on a fresh DB).
"""
from alembic import op
import sqlalchemy as sa


revision = 'd4e5f6a7b8c9'
down_revision = 'c3d4e5f6a7b8'
branch_labels = None
depends_on = None


def _has_table(insp, name):
    return name in set(insp.get_table_names())


def upgrade():
    insp = sa.inspect(op.get_bind())
    if not _has_table(insp, 'conversations'):
        op.create_table(
            'conversations',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_a_id', sa.Integer(), nullable=False),
            sa.Column('user_b_id', sa.Integer(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('last_message_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['user_a_id'], ['users.id']),
            sa.ForeignKeyConstraint(['user_b_id'], ['users.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('user_a_id', 'user_b_id', name='uq_conversation_pair'),
        )
        op.create_index(op.f('ix_conversations_user_a_id'), 'conversations', ['user_a_id'])
        op.create_index(op.f('ix_conversations_user_b_id'), 'conversations', ['user_b_id'])
        op.create_index(op.f('ix_conversations_last_message_at'), 'conversations', ['last_message_at'])

    if not _has_table(insp, 'direct_messages'):
        op.create_table(
            'direct_messages',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('conversation_id', sa.Integer(), nullable=False),
            sa.Column('sender_id', sa.Integer(), nullable=False),
            sa.Column('body', sa.Text(), nullable=False),
            sa.Column('is_read', sa.Boolean(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id']),
            sa.ForeignKeyConstraint(['sender_id'], ['users.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_direct_messages_conversation_id'), 'direct_messages', ['conversation_id'])


def downgrade():
    insp = sa.inspect(op.get_bind())
    if _has_table(insp, 'direct_messages'):
        op.drop_index(op.f('ix_direct_messages_conversation_id'), table_name='direct_messages')
        op.drop_table('direct_messages')
    if _has_table(insp, 'conversations'):
        op.drop_index(op.f('ix_conversations_last_message_at'), table_name='conversations')
        op.drop_index(op.f('ix_conversations_user_b_id'), table_name='conversations')
        op.drop_index(op.f('ix_conversations_user_a_id'), table_name='conversations')
        op.drop_table('conversations')
