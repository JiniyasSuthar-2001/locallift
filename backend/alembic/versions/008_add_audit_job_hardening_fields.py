"""add audit job hardening fields

Revision ID: 008_add_audit_job_hardening_fields
Revises: 007_add_audit_jobs_table
Create Date: 2026-09-17 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = '008_add_audit_job_hardening_fields'
down_revision = '007_add_audit_jobs_table'
branch_labels = None
depends_on = None

def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [c['name'] for c in inspector.get_columns('audit_jobs')]

    if 'broken_link_check_status' not in columns:
        op.add_column('audit_jobs', sa.Column('broken_link_check_status', sa.String(length=50), server_default='not_started', nullable=True))
    if 'broken_link_check_error' not in columns:
        op.add_column('audit_jobs', sa.Column('broken_link_check_error', sa.Text(), nullable=True))
    if 'links_skipped' not in columns:
        op.add_column('audit_jobs', sa.Column('links_skipped', sa.Integer(), server_default='0', nullable=True))
    if 'runtime_limit_reached' not in columns:
        op.add_column('audit_jobs', sa.Column('runtime_limit_reached', sa.Boolean(), server_default='0', nullable=True))
    if 'redirect_limit_reached' not in columns:
        op.add_column('audit_jobs', sa.Column('redirect_limit_reached', sa.Boolean(), server_default='0', nullable=True))
    if 'browser_rendering_unavailable' not in columns:
        op.add_column('audit_jobs', sa.Column('browser_rendering_unavailable', sa.Boolean(), server_default='0', nullable=True))

def downgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [c['name'] for c in inspector.get_columns('audit_jobs')]

    if 'browser_rendering_unavailable' in columns:
        op.drop_column('audit_jobs', 'browser_rendering_unavailable')
    if 'redirect_limit_reached' in columns:
        op.drop_column('audit_jobs', 'redirect_limit_reached')
    if 'runtime_limit_reached' in columns:
        op.drop_column('audit_jobs', 'runtime_limit_reached')
    if 'links_skipped' in columns:
        op.drop_column('audit_jobs', 'links_skipped')
    if 'broken_link_check_error' in columns:
        op.drop_column('audit_jobs', 'broken_link_check_error')
    if 'broken_link_check_status' in columns:
        op.drop_column('audit_jobs', 'broken_link_check_status')
