"""Add system_settings, organization_ai_configs, and ai_usage_logs tables

Revision ID: 005_add_ai_control_tables
Revises: 004_add_project_id_to_gsc_ga4_properties
Create Date: 2026-09-16 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '005_add_ai_control_tables'
down_revision: Union[str, None] = '004_add_project_id_to_gsc_ga4_properties'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if 'system_settings' not in tables:
        op.create_table(
            'system_settings',
            sa.Column('key', sa.String(length=100), primary_key=True, nullable=False),
            sa.Column('value', sa.Text(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=True)
        )

    if 'organization_ai_configs' not in tables:
        op.create_table(
            'organization_ai_configs',
            sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
            sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False, unique=True),
            sa.Column('ai_enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('ai_daily_limit', sa.Integer(), nullable=False, server_default='100'),
            sa.Column('ai_monthly_limit', sa.Integer(), nullable=False, server_default='3000'),
            sa.Column('ai_per_request_limit', sa.Integer(), nullable=False, server_default='5'),
            sa.Column('ai_credits_balance', sa.Float(), nullable=False, server_default='1000.0'),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True)
        )

    if 'ai_usage_logs' not in tables:
        op.create_table(
            'ai_usage_logs',
            sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
            sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='SET NULL'), nullable=True),
            sa.Column('task_type', sa.String(length=100), nullable=False),
            sa.Column('provider', sa.String(length=50), nullable=False),
            sa.Column('model', sa.String(length=100), nullable=True),
            sa.Column('input_tokens', sa.Integer(), nullable=True),
            sa.Column('output_tokens', sa.Integer(), nullable=True),
            sa.Column('total_tokens', sa.Integer(), nullable=True),
            sa.Column('estimated_cost', sa.Float(), nullable=True),
            sa.Column('actual_cost', sa.Float(), nullable=True),
            sa.Column('credits_charged', sa.Float(), nullable=False, server_default='0.0'),
            sa.Column('status', sa.String(length=50), nullable=False),
            sa.Column('error_message', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True)
        )
        op.create_index('ix_ai_usage_logs_organization_id', 'ai_usage_logs', ['organization_id'])
        op.create_index('ix_ai_usage_logs_project_id', 'ai_usage_logs', ['project_id'])
        op.create_index('ix_ai_usage_logs_created_at', 'ai_usage_logs', ['created_at'])

def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if 'ai_usage_logs' in tables:
        op.drop_table('ai_usage_logs')
    if 'organization_ai_configs' in tables:
        op.drop_table('organization_ai_configs')
    if 'system_settings' in tables:
        op.drop_table('system_settings')
