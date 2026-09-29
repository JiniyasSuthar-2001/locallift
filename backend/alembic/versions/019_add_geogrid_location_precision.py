"""add location_precision, center_source, center_address to geo_grid_scans

Revision ID: 019_add_geogrid_location_precision
Revises: 018_add_scan_allowance_and_review_provenance
Create Date: 2026-09-26 18:25:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = '019_add_geogrid_location_precision'
down_revision: Union[str, None] = '018_add_scan_allowance_and_review_provenance'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    tables = inspector.get_table_names()

    if 'geo_grid_scans' in tables:
        columns = [c['name'] for c in inspector.get_columns('geo_grid_scans')]
        with op.batch_alter_table('geo_grid_scans') as batch_op:
            if 'location_precision' not in columns:
                batch_op.add_column(sa.Column('location_precision', sa.String(length=50), nullable=True, server_default='EXACT'))
            if 'center_source' not in columns:
                batch_op.add_column(sa.Column('center_source', sa.String(length=50), nullable=True))
            if 'center_address' not in columns:
                batch_op.add_column(sa.Column('center_address', sa.String(length=500), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    tables = inspector.get_table_names()

    if 'geo_grid_scans' in tables:
        columns = [c['name'] for c in inspector.get_columns('geo_grid_scans')]
        with op.batch_alter_table('geo_grid_scans') as batch_op:
            if 'center_address' in columns:
                batch_op.drop_column('center_address')
            if 'center_source' in columns:
                batch_op.drop_column('center_source')
            if 'location_precision' in columns:
                batch_op.drop_column('location_precision')
