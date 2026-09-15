"""Add project_id column to google_search_console_properties and google_analytics_properties

Revision ID: 004_add_project_id_to_gsc_ga4_properties
Revises: 003_add_service_to_google_connections
Create Date: 2026-09-15 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '004_add_project_id_to_gsc_ga4_properties'
down_revision: Union[str, None] = '003_add_service_to_google_connections'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    
    if 'google_search_console_properties' in tables:
        columns = [c['name'] for c in inspector.get_columns('google_search_console_properties')]
        if 'project_id' not in columns:
            with op.batch_alter_table('google_search_console_properties') as batch_op:
                batch_op.add_column(
                    sa.Column(
                        'project_id',
                        sa.Integer(),
                        sa.ForeignKey('projects.id', ondelete='SET NULL', name='fk_gsc_project_id'),
                        nullable=True
                    )
                )

    if 'google_analytics_properties' in tables:
        columns = [c['name'] for c in inspector.get_columns('google_analytics_properties')]
        if 'project_id' not in columns:
            with op.batch_alter_table('google_analytics_properties') as batch_op:
                batch_op.add_column(
                    sa.Column(
                        'project_id',
                        sa.Integer(),
                        sa.ForeignKey('projects.id', ondelete='SET NULL', name='fk_ga4_project_id'),
                        nullable=True
                    )
                )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    
    if 'google_search_console_properties' in tables:
        columns = [c['name'] for c in inspector.get_columns('google_search_console_properties')]
        if 'project_id' in columns:
            with op.batch_alter_table('google_search_console_properties') as batch_op:
                batch_op.drop_column('project_id')

    if 'google_analytics_properties' in tables:
        columns = [c['name'] for c in inspector.get_columns('google_analytics_properties')]
        if 'project_id' in columns:
            with op.batch_alter_table('google_analytics_properties') as batch_op:
                batch_op.drop_column('project_id')
