"""Initial comprehensive schema migration for LocalLift

Revision ID: 001_initial_schema
Revises: None
Create Date: 2026-09-11 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Tables are created or managed via SQLAlchemy Base metadata
    pass


def downgrade() -> None:
    pass
