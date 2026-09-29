"""add completed_at to geo_grid_scans and external_review_id to reviews

Revision ID: 016_add_completed_at_and_review_identity
Revises: 015_add_forensic_audit_and_ranking_fields
Create Date: 2026-09-26 12:20:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = '016_add_completed_at_and_review_identity'
down_revision: Union[str, None] = '015_add_forensic_audit_and_ranking_fields'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    tables = inspector.get_table_names()

    # 1. geo_grid_scans -> completed_at
    if 'geo_grid_scans' in tables:
        columns = [c['name'] for c in inspector.get_columns('geo_grid_scans')]
        with op.batch_alter_table('geo_grid_scans') as batch_op:
            if 'completed_at' not in columns:
                batch_op.add_column(sa.Column('completed_at', sa.DateTime(), nullable=True))

    # 2. reviews -> external_review_id
    if 'reviews' in tables:
        columns = [c['name'] for c in inspector.get_columns('reviews')]
        with op.batch_alter_table('reviews') as batch_op:
            if 'external_review_id' not in columns:
                batch_op.add_column(sa.Column('external_review_id', sa.String(length=255), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    tables = inspector.get_table_names()

    if 'reviews' in tables:
        columns = [c['name'] for c in inspector.get_columns('reviews')]
        with op.batch_alter_table('reviews') as batch_op:
            if 'external_review_id' in columns:
                batch_op.drop_column('external_review_id')

    if 'geo_grid_scans' in tables:
        columns = [c['name'] for c in inspector.get_columns('geo_grid_scans')]
        with op.batch_alter_table('geo_grid_scans') as batch_op:
            if 'completed_at' in columns:
                batch_op.drop_column('completed_at')
