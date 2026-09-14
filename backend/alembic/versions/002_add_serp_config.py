"""Add OrganizationSERPConfig model for organization-specific SERP settings

Revision ID: 002_add_serp_config
Revises: 001_initial_schema
Create Date: 2026-09-12 16:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '002_add_serp_config'
down_revision: Union[str, None] = '001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create organization_serp_configs table if it doesn't exist
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    if 'organization_serp_configs' not in tables:
        op.create_table(
            'organization_serp_configs',
            sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
            sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False, unique=True),
            sa.Column('provider', sa.String(length=50), nullable=False, server_default='serpapi'),
            sa.Column('api_key', sa.Text(), nullable=True),
            sa.Column('enabled', sa.Boolean(), server_default='1'),
            sa.Column('connection_status', sa.String(length=50), server_default='not_configured'),
            sa.Column('status_message', sa.Text(), nullable=True),
            sa.Column('last_tested_at', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
        )
        op.create_index(op.f('ix_organization_serp_configs_id'), 'organization_serp_configs', ['id'], unique=False)
        op.create_index(op.f('ix_organization_serp_configs_organization_id'), 'organization_serp_configs', ['organization_id'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_organization_serp_configs_organization_id'), table_name='organization_serp_configs')
    op.drop_index(op.f('ix_organization_serp_configs_id'), table_name='organization_serp_configs')
    op.drop_table('organization_serp_configs')
