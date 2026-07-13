"""add user_availability + users.timezone

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-07-13

Idempotent: guarded on introspection (create_all may already have created the
table / column on a fresh DB).
"""
from alembic import op
import sqlalchemy as sa


revision = 'c3d4e5f6a7b8'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None


def _has_table(insp, name):
    return name in set(insp.get_table_names())


def _has_column(insp, table, column):
    if not _has_table(insp, table):
        return False
    return column in {c['name'] for c in insp.get_columns(table)}


def upgrade():
    insp = sa.inspect(op.get_bind())
    if _has_table(insp, 'users') and not _has_column(insp, 'users', 'timezone'):
        with op.batch_alter_table('users', schema=None) as batch_op:
            batch_op.add_column(sa.Column('timezone', sa.String(length=64), nullable=True))

    if not _has_table(insp, 'user_availability'):
        op.create_table(
            'user_availability',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('weekday', sa.Integer(), nullable=False),
            sa.Column('block', sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(['user_id'], ['users.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('user_id', 'weekday', 'block', name='uq_availability_cell'),
        )
        op.create_index(op.f('ix_user_availability_user_id'), 'user_availability', ['user_id'])


def downgrade():
    insp = sa.inspect(op.get_bind())
    if _has_table(insp, 'user_availability'):
        op.drop_index(op.f('ix_user_availability_user_id'), table_name='user_availability')
        op.drop_table('user_availability')
    if _has_column(insp, 'users', 'timezone'):
        with op.batch_alter_table('users', schema=None) as batch_op:
            batch_op.drop_column('timezone')
