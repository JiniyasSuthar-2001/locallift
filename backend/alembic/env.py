import asyncio
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Import app Base and Settings
from app.config import settings
from app.database import Base
import app.models  # Ensure all models are registered

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    try:
        fileConfig(config.config_file_name, disable_existing_loggers=False)
    except Exception:
        pass

# Set database URL dynamically from app settings unless explicitly overridden in config
custom_url = config.get_main_option("sqlalchemy.url")
if custom_url:
    sync_db_url = custom_url
    if sync_db_url.startswith("sqlite:") and not sync_db_url.startswith("sqlite+aiosqlite:"):
        db_url = sync_db_url.replace("sqlite:", "sqlite+aiosqlite:", 1)
    elif sync_db_url.startswith("postgresql:") and not sync_db_url.startswith("postgresql+asyncpg:"):
        db_url = sync_db_url.replace("postgresql:", "postgresql+asyncpg:", 1)
    else:
        db_url = sync_db_url
else:
    db_url = settings.DATABASE_URL
    if db_url.startswith("sqlite+aiosqlite:"):
        sync_db_url = db_url.replace("sqlite+aiosqlite:", "sqlite:", 1)
    else:
        sync_db_url = db_url.replace("postgresql+asyncpg:", "postgresql:", 1)
    config.set_main_option("sqlalchemy.url", sync_db_url)

target_metadata = Base.metadata

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True if "sqlite" in sync_db_url else False
    )

    with context.begin_transaction():
        context.run_migrations()

def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True if "sqlite" in sync_db_url else False
    )

    with context.begin_transaction():
        context.run_migrations()

async def run_async_migrations() -> None:
    """In this scenario we need to create an Engine and associate a connection with the context."""
    from sqlalchemy.ext.asyncio import create_async_engine
    connectable = create_async_engine(
        db_url,
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
        await connection.commit()

    await connectable.dispose()

def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
