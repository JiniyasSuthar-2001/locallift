import os
import tempfile
from sqlalchemy import create_engine, inspect, text
from alembic.config import Config
from alembic import command
from app.database import Base
import app.models  # noqa: F401

def test_alembic_new_database_migration():
    """Test Case A: A new empty database is initialized via Alembic upgrade head."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "new_test.db")
        sync_url = f"sqlite:///{db_path}"

        backend_dir = os.path.dirname(os.path.abspath(__file__))
        alembic_ini = os.path.join(backend_dir, "alembic.ini")
        alembic_dir = os.path.join(backend_dir, "alembic")

        alembic_cfg = Config(alembic_ini)
        alembic_cfg.set_main_option("sqlalchemy.url", sync_url)
        alembic_cfg.set_main_option("script_location", alembic_dir)

        # Upgrade to head on clean DB
        command.upgrade(alembic_cfg, "head")

        engine = create_engine(sync_url)
        try:
            with engine.connect() as conn:
                inspector = inspect(conn)
                tables = inspector.get_table_names()
                assert "alembic_version" in tables, "alembic_version table missing"
                assert "users" in tables, "users table missing"
                assert "projects" in tables, "projects table missing"

                # Check revision ID
                res = conn.execute(text("SELECT version_num FROM alembic_version")).fetchone()
                assert res is not None and res[0] == "001_initial_schema"
        finally:
            engine.dispose()

def test_alembic_existing_database_bootstrapping():
    """Test Case B: Existing DB created via create_all() is safely stamped and upgraded."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "existing_test.db")
        sync_url = f"sqlite:///{db_path}"

        # 1. Simulate unversioned database created via create_all()
        engine = create_engine(sync_url)
        try:
            Base.metadata.create_all(bind=engine)
            with engine.connect() as conn:
                inspector = inspect(conn)
                tables = inspector.get_table_names()
                assert "users" in tables
                assert "alembic_version" not in tables
        finally:
            engine.dispose()

        # 2. Run migration runner logic
        backend_dir = os.path.dirname(os.path.abspath(__file__))
        alembic_ini = os.path.join(backend_dir, "alembic.ini")
        alembic_dir = os.path.join(backend_dir, "alembic")

        alembic_cfg = Config(alembic_ini)
        alembic_cfg.set_main_option("sqlalchemy.url", sync_url)
        alembic_cfg.set_main_option("script_location", alembic_dir)

        # Inspect and stamp
        engine2 = create_engine(sync_url)
        try:
            with engine2.connect() as conn:
                inspector = inspect(conn)
                tables = inspector.get_table_names()
                has_alembic = "alembic_version" in tables
                has_app_tables = "users" in tables or "projects" in tables

                if has_app_tables and not has_alembic:
                    command.stamp(alembic_cfg, "001_initial_schema")
        finally:
            engine2.dispose()

        # Upgrade head
        command.upgrade(alembic_cfg, "head")

        engine3 = create_engine(sync_url)
        try:
            with engine3.connect() as conn:
                inspector = inspect(conn)
                tables = inspector.get_table_names()
                assert "alembic_version" in tables
                res = conn.execute(text("SELECT version_num FROM alembic_version")).fetchone()
                assert res[0] == "001_initial_schema"
        finally:
            engine3.dispose()

def test_future_migration_simulation():
    """Test Case C: Simulate future revision 002_test_migration on top of 001."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "future_test.db")
        sync_url = f"sqlite:///{db_path}"

        backend_dir = os.path.dirname(os.path.abspath(__file__))
        alembic_ini = os.path.join(backend_dir, "alembic.ini")
        alembic_dir = os.path.join(backend_dir, "alembic")
        versions_dir = os.path.join(alembic_dir, "versions")

        alembic_cfg = Config(alembic_ini)
        alembic_cfg.set_main_option("sqlalchemy.url", sync_url)
        alembic_cfg.set_main_option("script_location", alembic_dir)

        # Initialize at 001
        command.upgrade(alembic_cfg, "head")

        # Create temporary 002 revision file
        temp_rev_path = os.path.join(versions_dir, "002_test_migration.py")
        rev_code = """\"\"\"Future test migration

Revision ID: 002_test_migration
Revises: 001_initial_schema
Create Date: 2026-09-12 12:00:00.000000

\"\"\"
from alembic import op
import sqlalchemy as sa

revision = '002_test_migration'
down_revision = '001_initial_schema'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        'test_future_feature',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(), nullable=True)
    )

def downgrade() -> None:
    op.drop_table('test_future_feature')
"""
        try:
            with open(temp_rev_path, "w", encoding="utf-8") as f:
                f.write(rev_code)

            # Re-read config & upgrade to head (002)
            alembic_cfg2 = Config(alembic_ini)
            alembic_cfg2.set_main_option("sqlalchemy.url", sync_url)
            alembic_cfg2.set_main_option("script_location", alembic_dir)

            command.upgrade(alembic_cfg2, "head")

            engine = create_engine(sync_url)
            try:
                with engine.connect() as conn:
                    inspector = inspect(conn)
                    tables = inspector.get_table_names()
                    assert "test_future_feature" in tables, "Future table missing after 002 migration"
                    res = conn.execute(text("SELECT version_num FROM alembic_version")).fetchone()
                    assert res[0] == "002_test_migration"
            finally:
                engine.dispose()
        finally:
            if os.path.exists(temp_rev_path):
                os.remove(temp_rev_path)

if __name__ == "__main__":
    test_alembic_new_database_migration()
    test_alembic_existing_database_bootstrapping()
    test_future_migration_simulation()
    print("[PASS] All Alembic migration architecture tests passed successfully!")
