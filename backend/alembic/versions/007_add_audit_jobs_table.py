"""add audit_jobs table

Revision ID: 007_add_audit_jobs_table
Revises: 006_add_gbp_public_observations
Create Date: 2026-09-16 19:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = '007_add_audit_jobs_table'
down_revision = '006_add_gbp_public_observations'
branch_labels = None
depends_on = None

def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    tables = inspector.get_table_names()

    if 'audit_jobs' not in tables:
        op.create_table(
            'audit_jobs',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
            sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id', ondelete='SET NULL'), nullable=True),
            sa.Column('job_type', sa.String(length=50), nullable=True, server_default='website_audit'),
            sa.Column('status', sa.String(length=50), nullable=False, server_default='queued'),
            sa.Column('progress', sa.Float(), nullable=True, server_default='0.0'),
            sa.Column('current_stage', sa.String(length=100), nullable=True, server_default='Queued for execution'),
            sa.Column('pages_discovered', sa.Integer(), nullable=True, server_default='0'),
            sa.Column('pages_processed', sa.Integer(), nullable=True, server_default='0'),
            sa.Column('start_url', sa.String(length=1000), nullable=True),
            sa.Column('started_at', sa.DateTime(), nullable=True),
            sa.Column('completed_at', sa.DateTime(), nullable=True),
            sa.Column('failed_at', sa.DateTime(), nullable=True),
            sa.Column('error_message', sa.Text(), nullable=True),
            sa.Column('error_code', sa.String(length=50), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_audit_jobs_id'), 'audit_jobs', ['id'], unique=False)
        op.create_index(op.f('ix_audit_jobs_project_id'), 'audit_jobs', ['project_id'], unique=False)

def downgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    tables = inspector.get_table_names()

    if 'audit_jobs' in tables:
        op.drop_index(op.f('ix_audit_jobs_project_id'), table_name='audit_jobs')
        op.drop_index(op.f('ix_audit_jobs_id'), table_name='audit_jobs')
        op.drop_table('audit_jobs')
