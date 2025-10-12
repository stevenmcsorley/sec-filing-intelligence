# ruff: noqa: I001,E402
#!/usr/bin/env python3
"""Clear all existing filing and company data from the database."""

import asyncio
import os
import sys
from pathlib import Path

from app.config import get_settings
from app.db import init_db, get_session_factory
from sqlalchemy import text

# Add the backend directory to the path FIRST
backend_dir = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_dir))

# Load environment variables from backend.env

# Load settings from environment
settings = get_settings()

async def clear_data():
    """Clear all filing and company data."""
    print("Initializing database connection...")
    init_db(settings)
    session_factory = get_session_factory()

    async with session_factory() as session:
        print("Clearing data in order...")

        # Clear diffs first (they reference filings)
        print("Clearing filing diffs...")
        await session.execute(text("DELETE FROM filing_section_diffs"))
        await session.execute(text("DELETE FROM filing_diffs"))

        # Clear analyses
        print("Clearing filing analyses...")
        await session.execute(text("DELETE FROM filing_analyses"))

        # Clear entities
        print("Clearing filing entities...")
        await session.execute(text("DELETE FROM filing_entities"))

        # Clear blobs
        print("Clearing filing blobs...")
        await session.execute(text("DELETE FROM filing_blobs"))

        # Clear sections
        print("Clearing filing sections...")
        await session.execute(text("DELETE FROM filing_sections"))

        # Clear filings
        print("Clearing filings...")
        await session.execute(text("DELETE FROM filings"))

        # Clear companies
        print("Clearing companies...")
        await session.execute(text("DELETE FROM companies"))

        # Commit all changes
        await session.commit()

        print("All data cleared successfully!")

if __name__ == "__main__":
    asyncio.run(clear_data())