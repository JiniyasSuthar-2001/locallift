"""add public business listing fields

Revision ID: 009_add_public_business_listing_fields
Revises: 008_add_audit_job_hardening_fields
Create Date: 2026-09-17 11:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = '009_add_public_business_listing_fields'
down_revision = '008_add_audit_job_hardening_fields'
branch_labels = None
depends_on = None

def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [c['name'] for c in inspector.get_columns('public_business_listings')]

    if 'address_components' not in columns:
        op.add_column('public_business_listings', sa.Column('address_components', sa.JSON(), nullable=True))
    if 'category' not in columns:
        op.add_column('public_business_listings', sa.Column('category', sa.String(length=255), nullable=True))
    if 'business_status' not in columns:
        op.add_column('public_business_listings', sa.Column('business_status', sa.String(length=100), nullable=True))
    if 'opening_hours' not in columns:
        op.add_column('public_business_listings', sa.Column('opening_hours', sa.JSON(), nullable=True))
    if 'source' not in columns:
        op.add_column('public_business_listings', sa.Column('source', sa.String(length=50), server_default='google_places_api', nullable=True))
    if 'source_checked_at' not in columns:
        op.add_column('public_business_listings', sa.Column('source_checked_at', sa.DateTime(), nullable=True))
    if 'lookup_status' not in columns:
        op.add_column('public_business_listings', sa.Column('lookup_status', sa.String(length=50), server_default='idle', nullable=True))
    if 'lookup_error' not in columns:
        op.add_column('public_business_listings', sa.Column('lookup_error', sa.Text(), nullable=True))

def downgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [c['name'] for c in inspector.get_columns('public_business_listings')]

    if 'lookup_error' in columns:
        op.drop_column('public_business_listings', 'lookup_error')
    if 'lookup_status' in columns:
        op.drop_column('public_business_listings', 'lookup_status')
    if 'source_checked_at' in columns:
        op.drop_column('public_business_listings', 'source_checked_at')
    if 'source' in columns:
        op.drop_column('public_business_listings', 'source')
    if 'opening_hours' in columns:
        op.drop_column('public_business_listings', 'opening_hours')
    if 'business_status' in columns:
        op.drop_column('public_business_listings', 'business_status')
    if 'category' in columns:
        op.drop_column('public_business_listings', 'category')
    if 'address_components' in columns:
        op.drop_column('public_business_listings', 'address_components')
