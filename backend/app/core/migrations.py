import os
import logging
from sqlalchemy import create_engine, inspect
from alembic.config import Config
from alembic import command
from app.config import settings

logger = logging.getLogger("locallift.migrations")

def run_db_migrations() -> None:
    """
    Single authoritative database migration & bootstrap entrypoint.
    Executes Alembic migrations safely for both new and existing databases.
    """
    db_url = settings.DATABASE_URL
    if db_url.startswith("sqlite+aiosqlite:"):
        sync_db_url = db_url.replace("sqlite+aiosqlite:", "sqlite:")
    elif db_url.startswith("postgresql+asyncpg:"):
        sync_db_url = db_url.replace("postgresql+asyncpg:", "postgresql:")
    else:
        sync_db_url = db_url

    current_dir = os.path.dirname(os.path.abspath(__file__))
    app_dir = os.path.dirname(current_dir)
    backend_dir = os.path.dirname(app_dir)

    alembic_ini_path = os.path.join(backend_dir, "alembic.ini")
    alembic_dir = os.path.join(backend_dir, "alembic")

    if not os.path.exists(alembic_ini_path):
        alembic_ini_path = "alembic.ini"
        alembic_dir = "alembic"

    alembic_cfg = Config(alembic_ini_path)
    alembic_cfg.set_main_option("sqlalchemy.url", sync_db_url)
    alembic_cfg.set_main_option("script_location", alembic_dir)

    engine = create_engine(sync_db_url)
    try:
        with engine.connect() as conn:
            inspector = inspect(conn)
            tables = inspector.get_table_names()
            has_alembic = "alembic_version" in tables
            has_app_tables = "users" in tables or "projects" in tables

            if has_app_tables and not has_alembic:
                logger.info("Existing unversioned database detected. Stamping schema at 001_initial_schema.")
                command.stamp(alembic_cfg, "001_initial_schema")
            elif not has_app_tables and not has_alembic:
                logger.info("New empty database detected. Initializing schema via Alembic.")
    except Exception as e:
        logger.error(f"Error inspecting database before migration: {e}")
    finally:
        engine.dispose()

    logger.info("Executing Alembic database migrations (upgrade head)...")
    command.upgrade(alembic_cfg, "head")
    logger.info("Alembic database migration completed successfully.")
