"""add geo grid point results table and scan metrics

Revision ID: 010_add_geo_grid_point_results
Revises: 009_add_public_business_listing_fields
Create Date: 2026-09-22 15:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = '010_add_geo_grid_point_results'
down_revision = '009_add_public_business_listing_fields'
branch_labels = None
depends_on = None

def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    tables = inspector.get_table_names()

    # 1. Add metric columns to geo_grid_scans if missing
    if 'geo_grid_scans' in tables:
        columns = [c['name'] for c in inspector.get_columns('geo_grid_scans')]
        new_cols = {
            'completed_points': sa.Column('completed_points', sa.Integer(), server_default='0', nullable=True),
            'ranking_found_points': sa.Column('ranking_found_points', sa.Integer(), server_default='0', nullable=True),
            'not_found_points': sa.Column('not_found_points', sa.Integer(), server_default='0', nullable=True),
            'provider_error_points': sa.Column('provider_error_points', sa.Integer(), server_default='0', nullable=True),
            'timeout_points': sa.Column('timeout_points', sa.Integer(), server_default='0', nullable=True),
        }
        for col_name, col_def in new_cols.items():
            if col_name not in columns:
                op.add_column('geo_grid_scans', col_def)

    # 2. Create geo_grid_point_results table if not exists
    if 'geo_grid_point_results' not in tables:
        op.create_table(
            'geo_grid_point_results',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('scan_id', sa.Integer(), sa.ForeignKey('geo_grid_scans.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('keyword_id', sa.Integer(), sa.ForeignKey('keywords.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('point_number', sa.Integer(), nullable=False),
            sa.Column('row', sa.Integer(), nullable=True),
            sa.Column('col', sa.Integer(), nullable=True),
            sa.Column('latitude', sa.Float(), nullable=False),
            sa.Column('longitude', sa.Float(), nullable=False),
            sa.Column('keyword', sa.String(length=255), nullable=False),
            sa.Column('provider', sa.String(length=50), nullable=False),
            sa.Column('status', sa.String(length=50), nullable=False),
            sa.Column('rank', sa.Integer(), nullable=True),
            sa.Column('matched_business', sa.String(length=255), nullable=True),
            sa.Column('matched_place_id', sa.String(length=255), nullable=True),
            sa.Column('matched_domain', sa.String(length=255), nullable=True),
            sa.Column('ranking_url', sa.String(length=1000), nullable=True),
            sa.Column('searched_at', sa.DateTime(), nullable=True),
            sa.Column('error', sa.Text(), nullable=True),
            sa.UniqueConstraint('scan_id', 'point_number', name='uq_geo_grid_scan_point')
        )

def downgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    tables = inspector.get_table_names()

    if 'geo_grid_point_results' in tables:
        op.drop_table('geo_grid_point_results')

    if 'geo_grid_scans' in tables:
        columns = [c['name'] for c in inspector.get_columns('geo_grid_scans')]
        for col_name in ['timeout_points', 'provider_error_points', 'not_found_points', 'ranking_found_points', 'completed_points']:
            if col_name in columns:
                op.drop_column('geo_grid_scans', col_name)
