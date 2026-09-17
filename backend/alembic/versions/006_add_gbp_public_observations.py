"""Add google_post_observations and google_observed_changes tables

Revision ID: 006_add_gbp_public_observations
Revises: 005_add_ai_control_tables
Create Date: 2026-09-16 13:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '006_add_gbp_public_observations'
down_revision: Union[str, None] = '005_add_ai_control_tables'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if 'google_post_observations' not in tables:
        op.create_table(
            'google_post_observations',
            sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
            sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
            sa.Column('business_identifier', sa.String(length=255), nullable=True),
            sa.Column('post_type', sa.String(length=50), nullable=True, server_default='UPDATE'),
            sa.Column('content_summary', sa.Text(), nullable=False),
            sa.Column('action_url', sa.String(length=500), nullable=True),
            sa.Column('published_at', sa.DateTime(), nullable=True),
            sa.Column('observed_at', sa.DateTime(), nullable=True),
            sa.Column('source', sa.String(length=100), nullable=True, server_default='Public Business Observation')
        )
        op.create_index('ix_google_post_observations_project_id', 'google_post_observations', ['project_id'])
        op.create_index('ix_google_post_observations_observed_at', 'google_post_observations', ['observed_at'])

    if 'google_observed_changes' not in tables:
        op.create_table(
            'google_observed_changes',
            sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
            sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
            sa.Column('field_name', sa.String(length=100), nullable=False),
            sa.Column('old_value', sa.Text(), nullable=True),
            sa.Column('new_value', sa.Text(), nullable=True),
            sa.Column('observed_at', sa.DateTime(), nullable=True),
            sa.Column('source', sa.String(length=100), nullable=True, server_default='Public Search Observation'),
            sa.Column('confidence', sa.String(length=50), nullable=True, server_default='Observed')
        )
        op.create_index('ix_google_observed_changes_project_id', 'google_observed_changes', ['project_id'])
        op.create_index('ix_google_observed_changes_observed_at', 'google_observed_changes', ['observed_at'])

def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if 'google_observed_changes' in tables:
        op.drop_table('google_observed_changes')
    if 'google_post_observations' in tables:
        op.drop_table('google_post_observations')
