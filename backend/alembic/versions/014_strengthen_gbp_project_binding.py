"""strengthen gbp project binding and complete location fields

Revision ID: 014_strengthen_gbp_project_binding
Revises: 013_add_geogrid_cancellation_fields
Create Date: 2026-09-23 16:15:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = '014_strengthen_gbp_project_binding'
down_revision: Union[str, None] = '013_add_geogrid_cancellation_fields'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    tables = inspector.get_table_names()

    if 'google_business_profiles' in tables:
        columns = [c['name'] for c in inspector.get_columns('google_business_profiles')]
        with op.batch_alter_table('google_business_profiles') as batch_op:
            if 'project_id' not in columns:
                batch_op.add_column(
                    sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='CASCADE', name='fk_gbp_project_id'), nullable=True)
                )
            if 'google_connection_id' not in columns:
                batch_op.add_column(
                    sa.Column('google_connection_id', sa.Integer(), sa.ForeignKey('google_connections.id', ondelete='SET NULL', name='fk_gbp_google_connection_id'), nullable=True)
                )
            if 'account_resource_name' not in columns:
                batch_op.add_column(sa.Column('account_resource_name', sa.String(length=255), nullable=True))
            if 'location_resource_name' not in columns:
                batch_op.add_column(sa.Column('location_resource_name', sa.String(length=255), nullable=True))
            if 'place_id' not in columns:
                batch_op.add_column(sa.Column('place_id', sa.String(length=255), nullable=True))
            if 'maps_uri' not in columns:
                batch_op.add_column(sa.Column('maps_uri', sa.String(length=1000), nullable=True))
            if 'storefront_address' not in columns:
                batch_op.add_column(sa.Column('storefront_address', sa.JSON(), nullable=True))
            if 'address_lines' not in columns:
                batch_op.add_column(sa.Column('address_lines', sa.JSON(), nullable=True))
            if 'city' not in columns:
                batch_op.add_column(sa.Column('city', sa.String(length=100), nullable=True))
            if 'state' not in columns:
                batch_op.add_column(sa.Column('state', sa.String(length=100), nullable=True))
            if 'postal_code' not in columns:
                batch_op.add_column(sa.Column('postal_code', sa.String(length=50), nullable=True))
            if 'country' not in columns:
                batch_op.add_column(sa.Column('country', sa.String(length=100), nullable=True))
            if 'latitude' not in columns:
                batch_op.add_column(sa.Column('latitude', sa.Float(), nullable=True))
            if 'longitude' not in columns:
                batch_op.add_column(sa.Column('longitude', sa.Float(), nullable=True))
            if 'regular_hours' not in columns:
                batch_op.add_column(sa.Column('regular_hours', sa.JSON(), nullable=True))
            if 'service_areas' not in columns:
                batch_op.add_column(sa.Column('service_areas', sa.JSON(), nullable=True))
            if 'status' not in columns:
                batch_op.add_column(sa.Column('status', sa.String(length=50), nullable=True, server_default='CONNECTED'))
            if 'sync_status' not in columns:
                batch_op.add_column(sa.Column('sync_status', sa.String(length=50), nullable=True, server_default='idle'))
            if 'sync_error' not in columns:
                batch_op.add_column(sa.Column('sync_error', sa.Text(), nullable=True))

        indexes = [idx['name'] for idx in inspector.get_indexes('google_business_profiles')]
        if 'ix_gbp_project_id' not in indexes:
            try:
                op.create_index('ix_gbp_project_id', 'google_business_profiles', ['project_id'], unique=False)
            except Exception:
                pass
        if 'ix_gbp_location_resource_name' not in indexes:
            try:
                op.create_index('ix_gbp_location_resource_name', 'google_business_profiles', ['location_resource_name'], unique=False)
            except Exception:
                pass


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    tables = inspector.get_table_names()

    if 'google_business_profiles' in tables:
        columns = [c['name'] for c in inspector.get_columns('google_business_profiles')]
        with op.batch_alter_table('google_business_profiles') as batch_op:
            for col in [
                'sync_error', 'sync_status', 'status', 'service_areas', 'regular_hours',
                'longitude', 'latitude', 'country', 'postal_code', 'state', 'city',
                'address_lines', 'storefront_address', 'maps_uri', 'place_id',
                'location_resource_name', 'account_resource_name',
                'google_connection_id', 'project_id'
            ]:
                if col in columns:
                    batch_op.drop_column(col)
