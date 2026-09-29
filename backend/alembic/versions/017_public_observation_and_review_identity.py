"""add public_observation_snapshots and review identity hardening

Revision ID: 017_public_observation_and_review_identity
Revises: 016_add_completed_at_and_review_identity
Create Date: 2026-09-26 16:15:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = '017_public_observation_and_review_identity'
down_revision: Union[str, None] = '016_add_completed_at_and_review_identity'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    tables = inspector.get_table_names()

    # 1. Create public_observation_snapshots table
    if 'public_observation_snapshots' not in tables:
        op.create_table(
            'public_observation_snapshots',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=True, index=True),
            sa.Column('provider', sa.String(length=100), nullable=False, server_default='Google Places API'),
            sa.Column('place_id', sa.String(length=255), nullable=True, index=True),
            sa.Column('fetched_at', sa.DateTime(), nullable=False),
            sa.Column('status', sa.String(length=50), nullable=False, server_default='FOUND'),
            sa.Column('completeness', sa.String(length=50), nullable=False, server_default='COMPLETE'),
            sa.Column('fields_returned', sa.JSON(), nullable=True),
            sa.Column('reviews_returned', sa.Integer(), nullable=True),
            sa.Column('errors', sa.Text(), nullable=True),
            sa.Column('provider_metadata', sa.JSON(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
        )

    # 2. Add columns to reviews
    if 'reviews' in tables:
        columns = [c['name'] for c in inspector.get_columns('reviews')]
        with op.batch_alter_table('reviews') as batch_op:
            if 'update_time' not in columns:
                batch_op.add_column(sa.Column('update_time', sa.DateTime(), nullable=True))
            if 'provider_url' not in columns:
                batch_op.add_column(sa.Column('provider_url', sa.String(length=1000), nullable=True))
            if 'provider_metadata' not in columns:
                batch_op.add_column(sa.Column('provider_metadata', sa.JSON(), nullable=True))
            if 'collected_at' not in columns:
                batch_op.add_column(sa.Column('collected_at', sa.DateTime(), nullable=True))
            if 'raw_provider_reference' not in columns:
                batch_op.add_column(sa.Column('raw_provider_reference', sa.String(length=500), nullable=True))
            if 'collection_status' not in columns:
                batch_op.add_column(sa.Column('collection_status', sa.String(length=50), nullable=True, server_default='active'))
            
            # Add unique index/constraint on (project_id, source, external_review_id)
            # Check existing unique constraints / indices
            existing_indexes = [idx['name'] for idx in inspector.get_indexes('reviews')]
            if 'uq_reviews_proj_src_ext_id' not in existing_indexes:
                batch_op.create_index(
                    'uq_reviews_proj_src_ext_id',
                    ['project_id', 'source', 'external_review_id'],
                    unique=False
                )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    tables = inspector.get_table_names()

    if 'reviews' in tables:
        columns = [c['name'] for c in inspector.get_columns('reviews')]
        existing_indexes = [idx['name'] for idx in inspector.get_indexes('reviews')]
        with op.batch_alter_table('reviews') as batch_op:
            if 'uq_reviews_proj_src_ext_id' in existing_indexes:
                batch_op.drop_index('uq_reviews_proj_src_ext_id')
            if 'collection_status' in columns:
                batch_op.drop_column('collection_status')
            if 'raw_provider_reference' in columns:
                batch_op.drop_column('raw_provider_reference')
            if 'collected_at' in columns:
                batch_op.drop_column('collected_at')
            if 'provider_metadata' in columns:
                batch_op.drop_column('provider_metadata')
            if 'provider_url' in columns:
                batch_op.drop_column('provider_url')
            if 'update_time' in columns:
                batch_op.drop_column('update_time')

    if 'public_observation_snapshots' in tables:
        op.drop_table('public_observation_snapshots')
