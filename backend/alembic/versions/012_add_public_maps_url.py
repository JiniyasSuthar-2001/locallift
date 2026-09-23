"""add public_maps_url to projects table

Revision ID: 012_add_public_maps_url
Revises: 011_add_local_seo_intelligence_foundation
Create Date: 2026-09-22 22:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = '012_add_public_maps_url'
down_revision = '011_add_local_seo_intelligence_foundation'
branch_labels = None
depends_on = None

def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('projects')]

    if 'public_maps_url' not in columns:
        op.add_column('projects', sa.Column('public_maps_url', sa.String(length=1000), nullable=True))

def downgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('projects')]

    if 'public_maps_url' in columns:
        op.drop_column('projects', 'public_maps_url')
