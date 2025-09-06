#!/usr/bin/env python
"""
Setup script for Supabase database for FXML3.
Run this script to initialize the database schema.
"""
import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Import migration runner
from fxml3.api.db.migrations.run_migrations import run_migrations


def main():
    """Run the setup script."""
    print("Setting up Supabase database for FXML3...")
    print("Running migrations...")
    
    # Run migrations
    asyncio.run(run_migrations())
    
    print("Setup completed successfully")


if __name__ == "__main__":
    main()