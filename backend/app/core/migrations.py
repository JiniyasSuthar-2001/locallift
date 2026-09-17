import os
import logging
from sqlalchemy import create_engine, inspect, text
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
            if "audit_jobs" in tables:
                columns = [c["name"] for c in inspector.get_columns("audit_jobs")]
                new_cols = {
                    "crawler_status": "VARCHAR(100) DEFAULT 'queued'",
                    "pages_crawled": "INTEGER DEFAULT 0",
                    "pages_failed": "INTEGER DEFAULT 0",
                    "pages_blocked": "INTEGER DEFAULT 0",
                    "links_discovered": "INTEGER DEFAULT 0",
                    "links_checked": "INTEGER DEFAULT 0",
                    "broken_links_found": "INTEGER DEFAULT 0",
                    "js_pages_rendered": "INTEGER DEFAULT 0",
                    "sitemap_urls_discovered": "INTEGER DEFAULT 0",
                    "robots_blocked_count": "INTEGER DEFAULT 0",
                    "ssrf_blocked_count": "INTEGER DEFAULT 0",
                    "options_snapshot": "JSON DEFAULT '{}'"
                }
                with engine.begin() as alter_conn:
                    for col_name, col_type in new_cols.items():
                        if col_name not in columns:
                            logger.info(f"Adding missing column '{col_name}' to audit_jobs table")
                            alter_conn.execute(text(f"ALTER TABLE audit_jobs ADD COLUMN {col_name} {col_type}"))

            if "organization_serp_configs" in tables:
                columns = [c["name"] for c in inspector.get_columns("organization_serp_configs")]
                serp_cols = {
                    "base_url": "VARCHAR(500) NULL",
                    "auth_mode": "VARCHAR(50) DEFAULT 'api_key'",
                    "capabilities": "JSON DEFAULT '{}'"
                }
                with engine.begin() as alter_conn:
                    for col_name, col_type in serp_cols.items():
                        if col_name not in columns:
                            logger.info(f"Adding missing column '{col_name}' to organization_serp_configs table")
                            alter_conn.execute(text(f"ALTER TABLE organization_serp_configs ADD COLUMN {col_name} {col_type}"))

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
    try:
        command.upgrade(alembic_cfg, "head")
    except Exception as exc:
        logger.warning(f"Alembic upgrade warning: {exc}")
    logger.info("Alembic database migration completed successfully.")
