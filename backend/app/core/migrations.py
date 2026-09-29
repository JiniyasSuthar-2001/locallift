import os
import re
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
            has_app_tables = "users" in tables or "projects" in tables
            has_alembic = "alembic_version" in tables
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
        logger.info("Alembic database migration completed successfully.")
    except Exception as exc:
        logger.warning(f"Alembic migration notice: {exc}")

    # Ensure all newly registered models (ScanJob, ProviderUsageRecord, etc.) exist
    try:
        from app.database import Base
        import app.models  # noqa: F401
        sync_engine = create_engine(sync_db_url)
        with sync_engine.connect() as conn:
            inspector = inspect(conn)
            if "users" in inspector.get_table_names():
                user_cols = [c["name"] for c in inspector.get_columns("users")]
                if "platform_role" not in user_cols:
                    conn.execute(text("ALTER TABLE users ADD COLUMN platform_role VARCHAR(50);"))
                    conn.commit()
            if "organizations" in inspector.get_table_names():
                org_cols = [c["name"] for c in inspector.get_columns("organizations")]
                if "status" not in org_cols:
                    conn.execute(text("ALTER TABLE organizations ADD COLUMN status VARCHAR(50) DEFAULT 'active';"))
                    conn.commit()
            if "geo_grid_scans" in inspector.get_table_names():
                geo_cols = [c["name"] for c in inspector.get_columns("geo_grid_scans")]
                geo_missing = [
                    ("location_precision", "VARCHAR(50) DEFAULT 'EXACT'"),
                    ("center_source", "VARCHAR(50)"),
                    ("center_address", "VARCHAR(500)"),
                    ("successful_points", "INTEGER DEFAULT 0"),
                    ("failed_points", "INTEGER DEFAULT 0"),
                    ("cancel_requested", "BOOLEAN DEFAULT 0"),
                    ("cancelled_at", "DATETIME"),
                    ("started_at", "DATETIME"),
                    ("cancellation_reason", "VARCHAR(255)"),
                    ("completed_at", "DATETIME")
                ]
                for col_name, col_type in geo_missing:
                    if col_name not in geo_cols:
                        conn.execute(text(f"ALTER TABLE geo_grid_scans ADD COLUMN {col_name} {col_type};"))
                conn.commit()
            if "reviews" in inspector.get_table_names():
                rev_cols = [c["name"] for c in inspector.get_columns("reviews")]
                rev_missing = [
                    ("access_mode", "VARCHAR(50) DEFAULT 'PUBLIC'"),
                    ("verification_status", "VARCHAR(50) DEFAULT 'OBSERVED'"),
                    ("collection_status", "VARCHAR(50) DEFAULT 'active'"),
                    ("raw_provider_reference", "VARCHAR(500)")
                ]
                for col_name, col_type in rev_missing:
                    if col_name not in rev_cols:
                        conn.execute(text(f"ALTER TABLE reviews ADD COLUMN {col_name} {col_type};"))
                conn.commit()
            if "citations" in inspector.get_table_names():
                cit_cols = [c["name"] for c in inspector.get_columns("citations")]
                cit_missing = [
                    ("verification_status", "VARCHAR(50) DEFAULT 'NOT_VERIFIED'"),
                    ("citation_type", "VARCHAR(50) DEFAULT 'USER_PROVIDED'"),
                    ("source", "VARCHAR(50)"),
                    ("platform_domain", "VARCHAR(255)")
                ]
                for col_name, col_type in cit_missing:
                    if col_name not in cit_cols:
                        conn.execute(text(f"ALTER TABLE citations ADD COLUMN {col_name} {col_type};"))
                conn.commit()
            if "organization_serp_configs" in inspector.get_table_names():
                serp_cols = [c["name"] for c in inspector.get_columns("organization_serp_configs")]
                serp_missing = [
                    ("credentials_extra", "TEXT"),
                    ("account_info", "JSON"),
                    ("usage_info", "JSON"),
                    ("last_synced_at", "DATETIME"),
                    ("last_sync_error", "TEXT")
                ]
                for col_name, col_type in serp_missing:
                    if col_name not in serp_cols:
                        conn.execute(text(f"ALTER TABLE organization_serp_configs ADD COLUMN {col_name} {col_type};"))
                conn.commit()
        Base.metadata.create_all(bind=sync_engine)
        sync_engine.dispose()
    except Exception as e:
        logger.warning(f"Table auto-creation notice: {e}")
        err_msg = str(exc)
        safe_err = re.sub(r"://([^:]+):([^@]+)@", "://***:***@", err_msg)
        logger.error(
            f"Alembic migration failed: command='upgrade head', revision='head', "
            f"exception_class='{exc.__class__.__name__}', error='{safe_err}'"
        )
        raise RuntimeError(f"Database migration failed ({exc.__class__.__name__}): {safe_err}") from exc
