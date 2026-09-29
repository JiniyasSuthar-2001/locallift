import os
import sys
from pathlib import Path

# Ensure backend root is on sys.path
BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Force testing environment flags
os.environ["TESTING"] = "true"
os.environ["ENVIRONMENT"] = "testing"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_isolated.db"

import pytest
from app.config import settings
import app.database
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

test_db_file = BACKEND_DIR / "test_isolated.db"
settings.DATABASE_URL = "sqlite+aiosqlite:///./test_isolated.db"

app.database.engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False}
)
app.database.AsyncSessionLocal = async_sessionmaker(
    bind=app.database.engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Session fixture ensuring tests run isolated from production database."""
    yield
    try:
        if test_db_file.exists():
            test_db_file.unlink(missing_ok=True)
    except Exception:
        pass
