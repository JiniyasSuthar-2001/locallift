"""add organization_scan_allowances table and review provenance columns

Revision ID: 018_add_scan_allowance_and_review_provenance
Revises: 017_public_observation_and_review_identity
Create Date: 2026-09-26 17:50:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = '018_add_scan_allowance_and_review_provenance'
down_revision: Union[str, None] = '017_public_observation_and_review_identity'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    tables = inspector.get_table_names()

    # 1. Create organization_scan_allowances table
    if 'organization_scan_allowances' not in tables:
        op.create_table(
            'organization_scan_allowances',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('year_month', sa.String(length=7), nullable=False, index=True),
            sa.Column('used_scans', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('allowed_scans', sa.Integer(), nullable=False, server_default='3'),
            sa.Column('last_scan_at', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.UniqueConstraint('organization_id', 'year_month', name='uq_org_scan_allowance_month')
        )

    # 2. Add access_mode and verification_status columns to reviews
    if 'reviews' in tables:
        columns = [c['name'] for c in inspector.get_columns('reviews')]
        with op.batch_alter_table('reviews') as batch_op:
            if 'access_mode' not in columns:
                batch_op.add_column(sa.Column('access_mode', sa.String(length=50), nullable=True, server_default='PUBLIC'))
            if 'verification_status' not in columns:
                batch_op.add_column(sa.Column('verification_status', sa.String(length=50), nullable=True, server_default='OBSERVED'))


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    tables = inspector.get_table_names()

    if 'reviews' in tables:
        columns = [c['name'] for c in inspector.get_columns('reviews')]
        with op.batch_alter_table('reviews') as batch_op:
            if 'verification_status' in columns:
                batch_op.drop_column('verification_status')
            if 'access_mode' in columns:
                batch_op.drop_column('access_mode')

    if 'organization_scan_allowances' not in tables:
        op.drop_table('organization_scan_allowances')
