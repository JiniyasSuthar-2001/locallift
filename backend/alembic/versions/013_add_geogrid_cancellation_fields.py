"""add geogrid cancellation fields

Revision ID: 013_add_geogrid_cancellation_fields
Revises: 012_add_public_maps_url
Create Date: 2026-09-23 15:10:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = '013_add_geogrid_cancellation_fields'
down_revision = '012_add_public_maps_url'
branch_labels = None
depends_on = None

def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('geo_grid_scans')]

    if 'cancel_requested' not in columns:
        op.add_column('geo_grid_scans', sa.Column('cancel_requested', sa.Boolean(), nullable=False, server_default=sa.false()))
    if 'cancelled_at' not in columns:
        op.add_column('geo_grid_scans', sa.Column('cancelled_at', sa.DateTime(), nullable=True))
    if 'started_at' not in columns:
        op.add_column('geo_grid_scans', sa.Column('started_at', sa.DateTime(), nullable=True))
    if 'cancellation_reason' not in columns:
        op.add_column('geo_grid_scans', sa.Column('cancellation_reason', sa.String(length=255), nullable=True))

def downgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('geo_grid_scans')]

    if 'cancellation_reason' in columns:
        op.drop_column('geo_grid_scans', 'cancellation_reason')
    if 'started_at' in columns:
        op.drop_column('geo_grid_scans', 'started_at')
    if 'cancelled_at' in columns:
        op.drop_column('geo_grid_scans', 'cancelled_at')
    if 'cancel_requested' in columns:
        op.drop_column('geo_grid_scans', 'cancel_requested')
