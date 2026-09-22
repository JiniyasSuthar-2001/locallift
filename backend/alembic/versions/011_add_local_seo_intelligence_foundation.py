"""add local seo intelligence foundation: business_profiles, local_audit_runs, local_audit_findings, citation and competitor provenance

Revision ID: 011_add_local_seo_intelligence_foundation
Revises: 010_add_geo_grid_point_results
Create Date: 2026-09-22 17:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = '011_add_local_seo_intelligence_foundation'
down_revision = '010_add_geo_grid_point_results'
branch_labels = None
depends_on = None

def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    tables = inspector.get_table_names()

    # 1. Create business_profiles table if not exists
    if 'business_profiles' not in tables:
        op.create_table(
            'business_profiles',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False, unique=True, index=True),
            sa.Column('business_name', sa.String(length=255), nullable=False),
            sa.Column('website', sa.String(length=500), nullable=True),
            sa.Column('primary_phone', sa.String(length=50), nullable=True),
            sa.Column('primary_address', sa.String(length=500), nullable=True),
            sa.Column('city', sa.String(length=100), nullable=True),
            sa.Column('state', sa.String(length=100), nullable=True),
            sa.Column('postal_code', sa.String(length=20), nullable=True),
            sa.Column('country', sa.String(length=100), nullable=True),
            sa.Column('latitude', sa.Float(), nullable=True),
            sa.Column('longitude', sa.Float(), nullable=True),
            sa.Column('primary_category', sa.String(length=255), nullable=True),
            sa.Column('additional_categories', sa.JSON(), nullable=True),
            sa.Column('service_area', sa.JSON(), nullable=True),
            sa.Column('place_id', sa.String(length=255), nullable=True),
            sa.Column('maps_url', sa.String(length=1000), nullable=True),
            sa.Column('source', sa.String(length=50), server_default='USER_PROVIDED', nullable=True),
            sa.Column('verification_status', sa.String(length=50), server_default='NOT_VERIFIED', nullable=True),
            sa.Column('last_verified_at', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True)
        )

    # 2. Create local_audit_runs table if not exists
    if 'local_audit_runs' not in tables:
        op.create_table(
            'local_audit_runs',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('framework_version', sa.String(length=50), server_default='local_seo_v1', nullable=True),
            sa.Column('status', sa.String(length=50), server_default='completed', nullable=True),
            sa.Column('overall_score', sa.Integer(), nullable=True),
            sa.Column('category_scores', sa.JSON(), nullable=True),
            sa.Column('findings_summary', sa.JSON(), nullable=True),
            sa.Column('started_at', sa.DateTime(), nullable=True),
            sa.Column('completed_at', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True)
        )

    # 3. Create local_audit_findings table if not exists
    if 'local_audit_findings' not in tables:
        op.create_table(
            'local_audit_findings',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('audit_run_id', sa.Integer(), sa.ForeignKey('local_audit_runs.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('category', sa.String(length=100), nullable=False, index=True),
            sa.Column('check_key', sa.String(length=100), nullable=False, index=True),
            sa.Column('title', sa.String(length=255), nullable=False),
            sa.Column('status', sa.String(length=50), server_default='NOT_VERIFIED', nullable=True),
            sa.Column('severity', sa.String(length=50), server_default='warning', nullable=True),
            sa.Column('score_impact', sa.Float(), server_default='0.0', nullable=True),
            sa.Column('evidence', sa.Text(), nullable=True),
            sa.Column('source', sa.String(length=100), nullable=True),
            sa.Column('source_url', sa.String(length=1000), nullable=True),
            sa.Column('verification_status', sa.String(length=50), server_default='NOT_VERIFIED', nullable=True),
            sa.Column('confidence', sa.String(length=50), server_default='HIGH', nullable=True),
            sa.Column('recommendation', sa.Text(), nullable=True),
            sa.Column('action_type', sa.String(length=100), server_default='manual_action', nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True)
        )

    # 4. Add provenance columns to citations table if missing
    if 'citations' in tables:
        cit_cols = [c['name'] for c in inspector.get_columns('citations')]
        cit_new_cols = {
            'citation_type': sa.Column('citation_type', sa.String(length=50), server_default='USER_PROVIDED', nullable=True),
            'verification_status': sa.Column('verification_status', sa.String(length=50), server_default='NOT_VERIFIED', nullable=True),
            'confidence': sa.Column('confidence', sa.Float(), nullable=True),
            'evidence': sa.Column('evidence', sa.JSON(), nullable=True),
            'source_type': sa.Column('source_type', sa.String(length=50), server_default='manual', nullable=True)
        }
        for col_name, col_def in cit_new_cols.items():
            if col_name not in cit_cols:
                op.add_column('citations', col_def)

    # 5. Add intelligence columns to competitors table if missing
    if 'competitors' in tables:
        comp_cols = [c['name'] for c in inspector.get_columns('competitors')]
        comp_new_cols = {
            'place_id': sa.Column('place_id', sa.String(length=255), nullable=True),
            'categories': sa.Column('categories', sa.JSON(), nullable=True),
            'gbp_status': sa.Column('gbp_status', sa.String(length=50), nullable=True),
            'citations_count': sa.Column('citations_count', sa.Integer(), server_default='0', nullable=True),
            'backlinks_count': sa.Column('backlinks_count', sa.Integer(), server_default='0', nullable=True),
            'geo_grid_share_pct': sa.Column('geo_grid_share_pct', sa.Float(), nullable=True),
            'tracked_keywords_overlap': sa.Column('tracked_keywords_overlap', sa.JSON(), nullable=True)
        }
        for col_name, col_def in comp_new_cols.items():
            if col_name not in comp_cols:
                op.add_column('competitors', col_def)

def downgrade():
    op.drop_table('local_audit_findings')
    op.drop_table('local_audit_runs')
    op.drop_table('business_profiles')
