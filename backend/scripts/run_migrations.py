import sys
import os

# Add backend directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.migrations import run_db_migrations
from sqlalchemy import create_engine, inspect
from app.config import settings

def main():
    print("Running DB migrations...")
    run_db_migrations()
    
    db_url = settings.DATABASE_URL.replace("sqlite+aiosqlite:", "sqlite:")
    engine = create_engine(db_url)
    inspector = inspect(engine)
    
    for table in ["google_search_console_properties", "google_analytics_properties"]:
        if table in inspector.get_table_names():
            cols = [c["name"] for c in inspector.get_columns(table)]
            print(f"Table '{table}' columns: {cols}")
            assert "project_id" in cols, f"project_id missing from {table}"
        else:
            print(f"Table '{table}' does not exist yet (will be created on first use).")
    print("Migration verification successful!")

if __name__ == "__main__":
    main()
