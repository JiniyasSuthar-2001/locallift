"""add forensic audit and ranking fields

Revision ID: 015_add_forensic_audit_and_ranking_fields
Revises: 014_strengthen_gbp_project_binding
Create Date: 2026-09-26 11:45:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = '015_add_forensic_audit_and_ranking_fields'
down_revision: Union[str, None] = '014_strengthen_gbp_project_binding'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    tables = inspector.get_table_names()

    # 1. local_audit_runs -> crawl_id
    if 'local_audit_runs' in tables:
        columns = [c['name'] for c in inspector.get_columns('local_audit_runs')]
        with op.batch_alter_table('local_audit_runs') as batch_op:
            if 'crawl_id' not in columns:
                batch_op.add_column(sa.Column('crawl_id', sa.Integer(), nullable=True))

    # 2. local_audit_findings -> forensic detail fields
    if 'local_audit_findings' in tables:
        columns = [c['name'] for c in inspector.get_columns('local_audit_findings')]
        with op.batch_alter_table('local_audit_findings') as batch_op:
            if 'rule_definition' not in columns:
                batch_op.add_column(sa.Column('rule_definition', sa.Text(), nullable=True))
            if 'what_was_checked' not in columns:
                batch_op.add_column(sa.Column('what_was_checked', sa.Text(), nullable=True))
            if 'observed_value' not in columns:
                batch_op.add_column(sa.Column('observed_value', sa.Text(), nullable=True))
            if 'expected_value' not in columns:
                batch_op.add_column(sa.Column('expected_value', sa.Text(), nullable=True))
            if 'why_it_matters' not in columns:
                batch_op.add_column(sa.Column('why_it_matters', sa.Text(), nullable=True))
            if 'affected_urls' not in columns:
                batch_op.add_column(sa.Column('affected_urls', sa.JSON(), nullable=True))
            if 'technical_evidence' not in columns:
                batch_op.add_column(sa.Column('technical_evidence', sa.JSON(), nullable=True))
            if 'remediation_steps' not in columns:
                batch_op.add_column(sa.Column('remediation_steps', sa.JSON(), nullable=True))
            if 'verification_steps' not in columns:
                batch_op.add_column(sa.Column('verification_steps', sa.JSON(), nullable=True))
            if 'crawl_id' not in columns:
                batch_op.add_column(sa.Column('crawl_id', sa.Integer(), nullable=True))
            if 'source_timestamp' not in columns:
                batch_op.add_column(sa.Column('source_timestamp', sa.DateTime(), nullable=True))

    # 3. keywords -> separate surfaces & timestamps
    if 'keywords' in tables:
        columns = [c['name'] for c in inspector.get_columns('keywords')]
        with op.batch_alter_table('keywords') as batch_op:
            if 'organic_rank' not in columns:
                batch_op.add_column(sa.Column('organic_rank', sa.Integer(), nullable=True))
            if 'local_pack_rank' not in columns:
                batch_op.add_column(sa.Column('local_pack_rank', sa.Integer(), nullable=True))
            if 'maps_rank' not in columns:
                batch_op.add_column(sa.Column('maps_rank', sa.Integer(), nullable=True))
            if 'rank_status' not in columns:
                batch_op.add_column(sa.Column('rank_status', sa.String(length=50), nullable=True, server_default='NOT_CHECKED'))
            if 'ranking_title' not in columns:
                batch_op.add_column(sa.Column('ranking_title', sa.String(length=500), nullable=True))
            if 'last_attempted_at' not in columns:
                batch_op.add_column(sa.Column('last_attempted_at', sa.DateTime(), nullable=True))
            if 'last_successful_check_at' not in columns:
                batch_op.add_column(sa.Column('last_successful_check_at', sa.DateTime(), nullable=True))
            if 'last_failed_at' not in columns:
                batch_op.add_column(sa.Column('last_failed_at', sa.DateTime(), nullable=True))

    # 4. keyword_rankings -> surfaces & metadata
    if 'keyword_rankings' in tables:
        columns = [c['name'] for c in inspector.get_columns('keyword_rankings')]
        with op.batch_alter_table('keyword_rankings') as batch_op:
            if 'organic_rank' not in columns:
                batch_op.add_column(sa.Column('organic_rank', sa.Integer(), nullable=True))
            if 'local_pack_rank' not in columns:
                batch_op.add_column(sa.Column('local_pack_rank', sa.Integer(), nullable=True))
            if 'maps_rank' not in columns:
                batch_op.add_column(sa.Column('maps_rank', sa.Integer(), nullable=True))
            if 'rank_status' not in columns:
                batch_op.add_column(sa.Column('rank_status', sa.String(length=50), nullable=True, server_default='RANKED'))
            if 'ranking_url' not in columns:
                batch_op.add_column(sa.Column('ranking_url', sa.String(length=1000), nullable=True))
            if 'country' not in columns:
                batch_op.add_column(sa.Column('country', sa.String(length=10), nullable=True, server_default='us'))
            if 'device' not in columns:
                batch_op.add_column(sa.Column('device', sa.String(length=20), nullable=True, server_default='desktop'))


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    tables = inspector.get_table_names()

    if 'keyword_rankings' in tables:
        columns = [c['name'] for c in inspector.get_columns('keyword_rankings')]
        with op.batch_alter_table('keyword_rankings') as batch_op:
            for col in ['device', 'country', 'ranking_url', 'rank_status', 'maps_rank', 'local_pack_rank', 'organic_rank']:
                if col in columns:
                    batch_op.drop_column(col)

    if 'keywords' in tables:
        columns = [c['name'] for c in inspector.get_columns('keywords')]
        with op.batch_alter_table('keywords') as batch_op:
            for col in ['last_failed_at', 'last_successful_check_at', 'last_attempted_at', 'ranking_title', 'rank_status', 'maps_rank', 'local_pack_rank', 'organic_rank']:
                if col in columns:
                    batch_op.drop_column(col)

    if 'local_audit_findings' in tables:
        columns = [c['name'] for c in inspector.get_columns('local_audit_findings')]
        with op.batch_alter_table('local_audit_findings') as batch_op:
            for col in ['source_timestamp', 'crawl_id', 'verification_steps', 'remediation_steps', 'technical_evidence', 'affected_urls', 'why_it_matters', 'expected_value', 'observed_value', 'what_was_checked', 'rule_definition']:
                if col in columns:
                    batch_op.drop_column(col)

    if 'local_audit_runs' in tables:
        columns = [c['name'] for c in inspector.get_columns('local_audit_runs')]
        with op.batch_alter_table('local_audit_runs') as batch_op:
            if 'crawl_id' in columns:
                batch_op.drop_column('crawl_id')
