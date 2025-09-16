#!/usr/bin/env python3
"""
Supabase setup script for FXML4.

This script initializes the Supabase project for FXML4,
sets up authentication, and creates necessary tables and functions.
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def run_command(command):
    """Run a shell command and return the output."""
    print(f"Running: {command}")
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        return None
    return result.stdout.strip()


def check_supabase_cli():
    """Check if Supabase CLI is installed."""
    result = run_command("supabase --version")
    if not result:
        print("Supabase CLI not found. Please install it first.")
        print("npm install -g supabase")
        return False
    return True


def login_to_supabase():
    """Log in to Supabase if not already logged in."""
    # Check if already logged in
    result = run_command("supabase projects list")
    if result:
        print("Already logged in to Supabase")
        return True

    # Get access token
    token = os.getenv("SUPABASE_ACCESS_TOKEN")
    if not token:
        print("SUPABASE_ACCESS_TOKEN not found in environment variables.")
        print("Please login manually: supabase login")
        return False

    # Login with token
    result = run_command(f"supabase login {token}")
    if not result:
        return False

    print("Logged in to Supabase successfully")
    return True


def link_project():
    """Link to existing Supabase project."""
    project_ref = os.getenv("SUPABASE_PROJECT_REF")
    if not project_ref:
        print("SUPABASE_PROJECT_REF not found in environment variables.")
        return False

    # Check if already linked
    if Path(".supabase").exists():
        print("Project already linked to Supabase")
        return True

    # Link project
    result = run_command(f"supabase link --project-ref {project_ref}")
    if not result:
        return False

    print("Project linked to Supabase successfully")
    return True


def generate_types():
    """Generate TypeScript types from Supabase schema."""
    output_dir = Path("fxml4") / "api" / "types"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "supabase.ts"

    result = run_command(f"supabase gen types typescript > {output_file}")
    if not result:
        return False

    print(f"TypeScript types generated at {output_file}")
    return True


def apply_migrations():
    """Apply migrations to Supabase project."""
    result = run_command("supabase db push")
    if not result:
        return False

    print("Migrations applied successfully")
    return True


def setup_auth():
    """Configure Supabase Auth settings."""
    # Get auth settings
    site_url = os.getenv("SUPABASE_SITE_URL", "http://localhost:3000")

    # Update auth settings
    config = {
        "site_url": site_url,
        "additional_redirect_urls": [
            "http://localhost:3000",
            "http://localhost:8000",
            "http://localhost:8501",
        ],
        "autoconfirm": False,
        "enable_signup": True,
    }

    # Write config to temporary file
    temp_file = "temp_auth_config.json"
    with open(temp_file, "w") as f:
        json.dump(config, f)

    # Apply config
    result = run_command(f"supabase auth config --config {temp_file}")

    # Remove temporary file
    os.remove(temp_file)

    if not result:
        return False

    print("Auth configuration updated successfully")
    return True


def setup_storage():
    """Configure Supabase Storage buckets."""
    buckets = ["models", "backtest-results", "data-exports"]

    for bucket in buckets:
        # Check if bucket exists
        result = run_command(f"supabase storage list-buckets")
        if result and bucket in result:
            print(f"Bucket {bucket} already exists")
            continue

        # Create bucket
        result = run_command(f"supabase storage create-bucket {bucket} --public")
        if not result:
            return False

        print(f"Bucket {bucket} created successfully")

    return True


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Set up Supabase for FXML4")
    parser.add_argument("--skip-login", action="store_true", help="Skip Supabase login")
    parser.add_argument("--skip-link", action="store_true", help="Skip project linking")
    parser.add_argument(
        "--skip-types", action="store_true", help="Skip type generation"
    )
    parser.add_argument(
        "--skip-migrations", action="store_true", help="Skip migrations"
    )
    parser.add_argument(
        "--skip-auth", action="store_true", help="Skip auth configuration"
    )
    parser.add_argument(
        "--skip-storage", action="store_true", help="Skip storage configuration"
    )
    args = parser.parse_args()

    # Check Supabase CLI
    if not check_supabase_cli():
        return 1

    # Steps to run
    steps = []

    if not args.skip_login:
        steps.append(("Login to Supabase", login_to_supabase))

    if not args.skip_link:
        steps.append(("Link Supabase project", link_project))

    if not args.skip_migrations:
        steps.append(("Apply migrations", apply_migrations))

    if not args.skip_types:
        steps.append(("Generate TypeScript types", generate_types))

    if not args.skip_auth:
        steps.append(("Configure Auth settings", setup_auth))

    if not args.skip_storage:
        steps.append(("Configure Storage buckets", setup_storage))

    # Run steps
    for description, func in steps:
        print(f"\n=== {description} ===")
        if not func():
            print(f"Error during {description}. Exiting.")
            return 1

    print("\n=== Supabase setup completed successfully ===")
    print("\nNext steps:")
    print("1. Configure your application to use Supabase")
    print("2. Set up authentication in your frontend")
    print("3. Use generated types for type-safe database access")
    return 0


if __name__ == "__main__":
    sys.exit(main())
