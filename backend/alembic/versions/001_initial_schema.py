"""Initial comprehensive schema migration for LocalLift

Revision ID: 001_initial_schema
Revises: None
Create Date: 2026-09-11 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. users
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('email', sa.String(length=255), unique=True, index=True, nullable=False),
        sa.Column('full_name', sa.String(length=255), nullable=True),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='1', nullable=True),
        sa.Column('is_superuser', sa.Boolean(), server_default='0', nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )

    # 2. organizations
    op.create_table(
        'organizations',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=255), unique=True, index=True, nullable=False),
        sa.Column('plan', sa.String(length=50), server_default='agency_pro', nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )

    # 3. organization_members
    op.create_table(
        'organization_members',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('role', sa.String(length=50), server_default='manager', nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )

    # 4. clients
    op.create_table(
        'clients',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('phone', sa.String(length=50), nullable=True),
        sa.Column('company_name', sa.String(length=255), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=50), server_default='active', nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )

    # 5. projects
    op.create_table(
        'projects',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('client_id', sa.Integer(), sa.ForeignKey('clients.id', ondelete='SET NULL'), nullable=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('domain', sa.String(length=255), nullable=False),
        sa.Column('primary_category', sa.String(length=255), server_default='Local Business', nullable=True),
        sa.Column('additional_categories', sa.JSON(), nullable=True),
        sa.Column('country', sa.String(length=50), nullable=True),
        sa.Column('health_score', sa.Integer(), nullable=True),
        sa.Column('technical_score', sa.Integer(), nullable=True),
        sa.Column('onpage_score', sa.Integer(), nullable=True),
        sa.Column('local_score', sa.Integer(), nullable=True),
        sa.Column('gbp_score', sa.Integer(), nullable=True),
        sa.Column('reviews_score', sa.Integer(), nullable=True),
        sa.Column('citations_score', sa.Integer(), nullable=True),
        sa.Column('keywords_score', sa.Integer(), nullable=True),
        sa.Column('maps_score', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=50), server_default='active', nullable=True),
        sa.Column('is_archived', sa.Boolean(), server_default='0', nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )

    # 6. locations
    op.create_table(
        'locations',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('address', sa.String(length=255), nullable=True),
        sa.Column('city', sa.String(length=100), nullable=True),
        sa.Column('state', sa.String(length=100), nullable=True),
        sa.Column('postal_code', sa.String(length=20), nullable=True),
        sa.Column('country', sa.String(length=100), nullable=True),
        sa.Column('phone', sa.String(length=50), nullable=True),
        sa.Column('latitude', sa.Float(), nullable=True),
        sa.Column('longitude', sa.Float(), nullable=True),
        sa.Column('place_id', sa.String(length=255), nullable=True),
        sa.Column('service_areas', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )

    # 7. websites
    op.create_table(
        'websites',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('url', sa.String(length=500), nullable=False),
        sa.Column('sitemap_url', sa.String(length=500), nullable=True),
        sa.Column('robots_url', sa.String(length=500), nullable=True),
        sa.Column('status', sa.String(length=50), server_default='ready', nullable=True),
        sa.Column('pages_crawled', sa.Integer(), server_default='0', nullable=True),
        sa.Column('last_crawled_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )

    # 8. website_pages
    op.create_table(
        'website_pages',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('website_id', sa.Integer(), sa.ForeignKey('websites.id', ondelete='CASCADE'), nullable=False),
        sa.Column('url', sa.String(length=1000), nullable=False, index=True),
        sa.Column('status_code', sa.Integer(), server_default='200', nullable=True),
        sa.Column('title', sa.String(length=500), nullable=True),
        sa.Column('meta_description', sa.Text(), nullable=True),
        sa.Column('h1', sa.String(length=500), nullable=True),
        sa.Column('h2_list', sa.JSON(), nullable=True),
        sa.Column('word_count', sa.Integer(), server_default='0', nullable=True),
        sa.Column('canonical_url', sa.String(length=1000), nullable=True),
        sa.Column('is_indexable', sa.Boolean(), server_default='1', nullable=True),
        sa.Column('load_time_ms', sa.Integer(), server_default='0', nullable=True),
        sa.Column('schema_types', sa.JSON(), nullable=True),
        sa.Column('schema_data', sa.JSON(), nullable=True),
        sa.Column('phones_found', sa.JSON(), nullable=True),
        sa.Column('emails_found', sa.JSON(), nullable=True),
        sa.Column('images_count', sa.Integer(), server_default='0', nullable=True),
        sa.Column('missing_alt_count', sa.Integer(), server_default='0', nullable=True),
        sa.Column('internal_links_count', sa.Integer(), server_default='0', nullable=True),
        sa.Column('external_links_count', sa.Integer(), server_default='0', nullable=True),
        sa.Column('issues_detected', sa.JSON(), nullable=True),
        sa.Column('broken_links', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )

    # 9. seo_audits
    op.create_table(
        'seo_audits',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('website_id', sa.Integer(), sa.ForeignKey('websites.id', ondelete='SET NULL'), nullable=True),
        sa.Column('overall_score', sa.Integer(), server_default='0', nullable=True),
        sa.Column('crawl_score', sa.Integer(), server_default='0', nullable=True),
        sa.Column('onpage_score', sa.Integer(), server_default='0', nullable=True),
        sa.Column('local_score', sa.Integer(), server_default='0', nullable=True),
        sa.Column('gbp_score', sa.Integer(), server_default='0', nullable=True),
        sa.Column('citations_score', sa.Integer(), server_default='0', nullable=True),
        sa.Column('reviews_score', sa.Integer(), server_default='0', nullable=True),
        sa.Column('audit_data', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )

    # 10. seo_issues
    op.create_table(
        'seo_issues',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('audit_id', sa.Integer(), sa.ForeignKey('seo_audits.id', ondelete='SET NULL'), nullable=True),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('category', sa.String(length=50), nullable=False),
        sa.Column('severity', sa.String(length=20), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('evidence', sa.JSON(), nullable=True),
        sa.Column('why_it_matters', sa.Text(), nullable=True),
        sa.Column('recommended_solution', sa.Text(), nullable=True),
        sa.Column('action_type', sa.String(length=50), server_default='manual', nullable=True),
        sa.Column('affected_url', sa.String(length=1000), nullable=True),
        sa.Column('status', sa.String(length=20), server_default='open', nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
    )

    # 11. seo_tasks
    op.create_table(
        'seo_tasks',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('issue_id', sa.Integer(), sa.ForeignKey('seo_issues.id', ondelete='SET NULL'), nullable=True),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('priority', sa.String(length=20), server_default='medium', nullable=True),
        sa.Column('status', sa.String(length=20), server_default='open', nullable=True),
        sa.Column('category', sa.String(length=50), server_default='general', nullable=True),
        sa.Column('impact_score', sa.Integer(), server_default='0', nullable=True),
        sa.Column('assigned_to_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('due_date', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
    )

    # 12. google_accounts
    op.create_table(
        'google_accounts',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('access_token', sa.Text(), nullable=True),
        sa.Column('refresh_token', sa.Text(), nullable=True),
        sa.Column('token_expiry', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='1', nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )

    # 13. google_connections
    op.create_table(
        'google_connections',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('google_user_id', sa.String(length=255), nullable=True),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('access_token', sa.Text(), nullable=False),
        sa.Column('refresh_token', sa.Text(), nullable=True),
        sa.Column('token_expiry', sa.DateTime(), nullable=True),
        sa.Column('scopes', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='1', nullable=True),
        sa.Column('connection_status', sa.String(length=50), server_default='connected', nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )

    # 14. google_business_profiles
    op.create_table(
        'google_business_profiles',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('google_account_id', sa.Integer(), sa.ForeignKey('google_accounts.id', ondelete='CASCADE'), nullable=True),
        sa.Column('location_id', sa.Integer(), sa.ForeignKey('locations.id', ondelete='SET NULL'), nullable=True),
        sa.Column('business_name', sa.String(length=255), nullable=False),
        sa.Column('address', sa.String(length=500), nullable=True),
        sa.Column('phone', sa.String(length=50), nullable=True),
        sa.Column('website_url', sa.String(length=500), nullable=True),
        sa.Column('primary_category', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )

    # 15. gbp_changes
    op.create_table(
        'gbp_changes',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('profile_id', sa.Integer(), sa.ForeignKey('google_business_profiles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('field_name', sa.String(length=100), nullable=False),
        sa.Column('old_value', sa.Text(), nullable=True),
        sa.Column('new_value', sa.Text(), nullable=True),
        sa.Column('changed_by_google', sa.Boolean(), server_default='1', nullable=True),
        sa.Column('status', sa.String(length=50), server_default='pending', nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )

    # 16. google_ads_accounts
    op.create_table(
        'google_ads_accounts',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('google_connection_id', sa.Integer(), sa.ForeignKey('google_connections.id', ondelete='CASCADE'), nullable=False),
        sa.Column('customer_id', sa.String(length=50), nullable=False),
        sa.Column('descriptive_name', sa.String(length=255), nullable=True),
        sa.Column('currency_code', sa.String(length=10), nullable=True),
        sa.Column('time_zone', sa.String(length=50), nullable=True),
        sa.Column('is_manager', sa.Boolean(), server_default='0', nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )

    # 17. google_search_console_properties
    op.create_table(
        'google_search_console_properties',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('google_connection_id', sa.Integer(), sa.ForeignKey('google_connections.id', ondelete='CASCADE'), nullable=False),
        sa.Column('site_url', sa.String(length=500), nullable=False),
        sa.Column('permission_level', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )

    # 18. google_analytics_properties
    op.create_table(
        'google_analytics_properties',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('google_connection_id', sa.Integer(), sa.ForeignKey('google_connections.id', ondelete='CASCADE'), nullable=False),
        sa.Column('property_id', sa.String(length=50), nullable=False),
        sa.Column('display_name', sa.String(length=255), nullable=True),
        sa.Column('default_data_stream_id', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )

    # 19. keywords
    op.create_table(
        'keywords',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('keyword', sa.String(length=255), nullable=False),
        sa.Column('target_location', sa.String(length=255), nullable=True),
        sa.Column('search_volume', sa.Integer(), server_default='0', nullable=True),
        sa.Column('current_rank', sa.Integer(), nullable=True),
        sa.Column('previous_rank', sa.Integer(), nullable=True),
        sa.Column('best_rank', sa.Integer(), nullable=True),
        sa.Column('search_intent', sa.String(length=50), server_default='commercial', nullable=True),
        sa.Column('difficulty', sa.Integer(), server_default='0', nullable=True),
        sa.Column('is_tracked', sa.Boolean(), server_default='1', nullable=True),
        sa.Column('last_checked_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )

    # 20. keyword_rankings
    op.create_table(
        'keyword_rankings',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('keyword_id', sa.Integer(), sa.ForeignKey('keywords.id', ondelete='CASCADE'), nullable=False),
        sa.Column('rank', sa.Integer(), nullable=True),
        sa.Column('url', sa.String(length=1000), nullable=True),
        sa.Column('serp_features', sa.JSON(), nullable=True),
        sa.Column('checked_at', sa.DateTime(), nullable=True),
    )

    # 21. geo_grid_scans
    op.create_table(
        'geo_grid_scans',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('keyword_id', sa.Integer(), sa.ForeignKey('keywords.id', ondelete='CASCADE'), nullable=False),
        sa.Column('center_lat', sa.Float(), nullable=False),
        sa.Column('center_lng', sa.Float(), nullable=False),
        sa.Column('radius_km', sa.Float(), server_default='5.0', nullable=True),
        sa.Column('grid_size', sa.Integer(), server_default='3', nullable=True),
        sa.Column('avg_rank', sa.Float(), nullable=True),
        sa.Column('points_data', sa.JSON(), nullable=True),
        sa.Column('scan_status', sa.String(length=50), server_default='completed', nullable=True),
        sa.Column('scanned_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )

    # 22. ranking_snapshots
    op.create_table(
        'ranking_snapshots',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('snapshot_date', sa.DateTime(), nullable=True),
        sa.Column('total_keywords', sa.Integer(), server_default='0', nullable=True),
        sa.Column('top_3_count', sa.Integer(), server_default='0', nullable=True),
        sa.Column('top_10_count', sa.Integer(), server_default='0', nullable=True),
        sa.Column('top_100_count', sa.Integer(), server_default='0', nullable=True),
        sa.Column('avg_rank', sa.Float(), server_default='0.0', nullable=True),
    )

    # 23. reviews
    op.create_table(
        'reviews',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('gbp_review_id', sa.String(length=255), unique=True, nullable=True),
        sa.Column('author_name', sa.String(length=255), nullable=False),
        sa.Column('author_photo_url', sa.String(length=500), nullable=True),
        sa.Column('rating', sa.Integer(), nullable=False),
        sa.Column('text', sa.Text(), nullable=True),
        sa.Column('review_time', sa.DateTime(), nullable=False),
        sa.Column('response_text', sa.Text(), nullable=True),
        sa.Column('response_time', sa.DateTime(), nullable=True),
        sa.Column('response_status', sa.String(length=50), server_default='unanswered', nullable=True),
        sa.Column('sentiment', sa.String(length=20), server_default='neutral', nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )

    # 24. citations
    op.create_table(
        'citations',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('source_name', sa.String(length=100), nullable=False),
        sa.Column('source_domain', sa.String(length=255), nullable=True),
        sa.Column('url', sa.String(length=500), nullable=True),
        sa.Column('status', sa.String(length=50), server_default='active', nullable=True),
        sa.Column('nap_status', sa.String(length=50), server_default='consistent', nullable=True),
        sa.Column('listed_name', sa.String(length=255), nullable=True),
        sa.Column('listed_address', sa.String(length=500), nullable=True),
        sa.Column('listed_phone', sa.String(length=50), nullable=True),
        sa.Column('domain_authority', sa.Integer(), server_default='0', nullable=True),
        sa.Column('is_verified', sa.Boolean(), server_default='0', nullable=True),
        sa.Column('last_checked_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )

    # 25. nap_records
    op.create_table(
        'nap_records',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('source_name', sa.String(length=100), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=True),
        sa.Column('address', sa.String(length=500), nullable=True),
        sa.Column('phone', sa.String(length=50), nullable=True),
        sa.Column('website', sa.String(length=500), nullable=True),
        sa.Column('name_match', sa.Boolean(), server_default='0', nullable=True),
        sa.Column('address_match', sa.Boolean(), server_default='0', nullable=True),
        sa.Column('phone_match', sa.Boolean(), server_default='0', nullable=True),
        sa.Column('website_match', sa.Boolean(), server_default='0', nullable=True),
        sa.Column('overall_status', sa.String(length=50), server_default='needs_audit', nullable=True),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
    )

    # 26. competitors
    op.create_table(
        'competitors',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('domain', sa.String(length=255), nullable=True),
        sa.Column('website', sa.String(length=500), nullable=True),
        sa.Column('address', sa.String(length=500), nullable=True),
        sa.Column('phone', sa.String(length=50), nullable=True),
        sa.Column('rating', sa.Float(), server_default='0.0', nullable=True),
        sa.Column('reviews_count', sa.Integer(), server_default='0', nullable=True),
        sa.Column('avg_rank', sa.Float(), server_default='0.0', nullable=True),
        sa.Column('visibility_score', sa.Float(), server_default='0.0', nullable=True),
        sa.Column('shared_keywords_count', sa.Integer(), server_default='0', nullable=True),
        sa.Column('last_scanned_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )

    # 27. schema_records
    op.create_table(
        'schema_records',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('page_url', sa.String(length=500), nullable=False),
        sa.Column('schema_type', sa.String(length=100), nullable=False),
        sa.Column('raw_json_ld', sa.JSON(), nullable=True),
        sa.Column('validation_status', sa.String(length=50), server_default='valid', nullable=True),
        sa.Column('validation_errors', sa.JSON(), nullable=True),
        sa.Column('last_extracted_at', sa.DateTime(), nullable=True),
    )

    # 28. gsc_metrics
    op.create_table(
        'gsc_metrics',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('date', sa.DateTime(), nullable=False),
        sa.Column('clicks', sa.Integer(), server_default='0', nullable=True),
        sa.Column('impressions', sa.Integer(), server_default='0', nullable=True),
        sa.Column('ctr', sa.Float(), server_default='0.0', nullable=True),
        sa.Column('average_position', sa.Float(), server_default='0.0', nullable=True),
        sa.Column('query', sa.String(length=255), nullable=True),
        sa.Column('page', sa.String(length=500), nullable=True),
        sa.Column('device', sa.String(length=50), nullable=True),
        sa.Column('country', sa.String(length=10), nullable=True),
    )

    # 29. ga4_metrics
    op.create_table(
        'ga4_metrics',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('date', sa.DateTime(), nullable=False),
        sa.Column('sessions', sa.Integer(), server_default='0', nullable=True),
        sa.Column('total_users', sa.Integer(), server_default='0', nullable=True),
        sa.Column('new_users', sa.Integer(), server_default='0', nullable=True),
        sa.Column('engagement_rate', sa.Float(), server_default='0.0', nullable=True),
        sa.Column('conversions', sa.Integer(), server_default='0', nullable=True),
        sa.Column('event_name', sa.String(length=100), nullable=True),
        sa.Column('channel_grouping', sa.String(length=100), nullable=True),
    )

    # 30. reports
    op.create_table(
        'reports',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('report_type', sa.String(length=50), server_default='monthly_seo', nullable=True),
        sa.Column('format', sa.String(length=20), server_default='pdf', nullable=True),
        sa.Column('status', sa.String(length=50), server_default='generated', nullable=True),
        sa.Column('file_path', sa.String(length=500), nullable=True),
        sa.Column('parameters', sa.JSON(), nullable=True),
        sa.Column('data_snapshot', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )

    # 31. scheduled_jobs
    op.create_table(
        'scheduled_jobs',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=True),
        sa.Column('job_type', sa.String(length=50), nullable=False),
        sa.Column('schedule_cron', sa.String(length=50), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='1', nullable=True),
        sa.Column('last_run_at', sa.DateTime(), nullable=True),
        sa.Column('next_run_at', sa.DateTime(), nullable=True),
        sa.Column('last_status', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )

    # 32. templates
    op.create_table(
        'templates',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('category', sa.String(length=50), nullable=False),
        sa.Column('prompt_template', sa.Text(), nullable=False),
        sa.Column('system_instructions', sa.Text(), nullable=True),
        sa.Column('is_system', sa.Boolean(), server_default='0', nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )

    # 33. template_usages
    op.create_table(
        'template_usages',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('template_id', sa.Integer(), sa.ForeignKey('templates.id', ondelete='CASCADE'), nullable=False),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('inputs', sa.JSON(), nullable=True),
        sa.Column('output', sa.Text(), nullable=True),
        sa.Column('tokens_used', sa.Integer(), server_default='0', nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )

    # 34. project_memberships
    op.create_table(
        'project_memberships',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('role', sa.String(length=50), server_default='editor', nullable=True),
        sa.Column('permissions', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )

    # 35. project_invitations
    op.create_table(
        'project_invitations',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=50), server_default='editor', nullable=True),
        sa.Column('token', sa.String(length=255), unique=True, nullable=False),
        sa.Column('status', sa.String(length=50), server_default='pending', nullable=True),
        sa.Column('invited_by', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )

    # 36. public_business_listings
    op.create_table(
        'public_business_listings',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('business_name', sa.String(length=255), nullable=False),
        sa.Column('address', sa.String(length=500), nullable=True),
        sa.Column('phone', sa.String(length=50), nullable=True),
        sa.Column('website', sa.String(length=500), nullable=True),
        sa.Column('place_id', sa.String(length=255), nullable=True),
        sa.Column('latitude', sa.Float(), nullable=True),
        sa.Column('longitude', sa.Float(), nullable=True),
        sa.Column('rating', sa.Float(), nullable=True),
        sa.Column('user_ratings_total', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )

    # 37. project_intelligence_scans
    op.create_table(
        'project_intelligence_scans',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('overall_status', sa.String(length=50), server_default='PENDING', nullable=True),
        sa.Column('progress_pct', sa.Integer(), server_default='0', nullable=True),
        sa.Column('current_stage', sa.String(length=100), nullable=True),
        sa.Column('stages_status', sa.JSON(), nullable=True),
        sa.Column('stage_durations_ms', sa.JSON(), nullable=True),
        sa.Column('failure_reason', sa.Text(), nullable=True),
        sa.Column('total_duration_ms', sa.Integer(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    for table_name in [
        'project_intelligence_scans',
        'public_business_listings',
        'project_invitations',
        'project_memberships',
        'template_usages',
        'templates',
        'scheduled_jobs',
        'reports',
        'ga4_metrics',
        'gsc_metrics',
        'schema_records',
        'competitors',
        'nap_records',
        'citations',
        'reviews',
        'ranking_snapshots',
        'geo_grid_scans',
        'keyword_rankings',
        'keywords',
        'google_analytics_properties',
        'google_search_console_properties',
        'google_ads_accounts',
        'gbp_changes',
        'google_business_profiles',
        'google_connections',
        'google_accounts',
        'seo_tasks',
        'seo_issues',
        'seo_audits',
        'website_pages',
        'websites',
        'locations',
        'projects',
        'clients',
        'organization_members',
        'organizations',
        'users'
    ]:
        op.drop_table(table_name)

