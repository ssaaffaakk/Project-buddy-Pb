"""add users avatar_url column

Revision ID: b8e4f2a91c3d
Revises: 3f60331bcca5
Create Date: 2026-06-24 16:45:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b8e4f2a91c3d'
down_revision = '3f60331bcca5'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if 'users' not in insp.get_table_names():
        return
    cols = [c['name'] for c in insp.get_columns('users')]
    if 'avatar_url' not in cols:
        op.add_column('users', sa.Column('avatar_url', sa.String(length=500), nullable=True))


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if 'users' not in insp.get_table_names():
        return
    cols = [c['name'] for c in insp.get_columns('users')]
    if 'avatar_url' in cols:
        op.drop_column('users', 'avatar_url')
