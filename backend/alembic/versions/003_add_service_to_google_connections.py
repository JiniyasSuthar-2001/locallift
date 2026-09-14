"""Add service column and unique constraint to google_connections

Revision ID: 003_add_service_to_google_connections
Revises: 002_add_serp_config
Create Date: 2026-09-12 18:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '003_add_service_to_google_connections'
down_revision: Union[str, None] = '002_add_serp_config'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    
    if 'google_connections' in tables:
        columns = [c['name'] for c in inspector.get_columns('google_connections')]
        if 'service' not in columns:
            op.add_column(
                'google_connections',
                sa.Column('service', sa.String(length=50), nullable=False, server_default='business_profile')
            )
            op.create_index(
                op.f('ix_google_connections_service'),
                'google_connections',
                ['service'],
                unique=False
            )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    
    if 'google_connections' in tables:
        columns = [c['name'] for c in inspector.get_columns('google_connections')]
        if 'service' in columns:
            op.drop_index(op.f('ix_google_connections_service'), table_name='google_connections')
            op.drop_column('google_connections', 'service')
