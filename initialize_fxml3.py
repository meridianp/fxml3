#!/usr/bin/env python
"""
Initialize FXML3 with Supabase integration.
"""
import os
import sys
import subprocess
from pathlib import Path
from dotenv import load_dotenv

def run_command(command, description):
    """Run a command with description."""
    print(f"\n=== {description} ===")
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    
    if result.returncode == 0:
        print("Success!")
        if result.stdout:
            print(result.stdout)
    else:
        print("Error!")
        if result.stderr:
            print(result.stderr)
        sys.exit(1)

def main():
    """Run the initialization script."""
    print("Initializing FXML3 with Supabase integration...")
    
    # Step 1: Check for .env file
    env_path = Path('.env')
    if not env_path.exists():
        print("Error: .env file not found!")
        print("Please create a .env file with your Supabase credentials.")
        sys.exit(1)
    
    # Step 2: Update .env file
    run_command("python update_env.py", "Updating .env file")
    
    # Step 3: Install dependencies
    print("\n=== Installing dependencies ===")
    try:
        subprocess.run("pip install -r requirements.txt", shell=True, check=False)
        print("Dependencies installed (some may have been skipped)")
    except Exception as e:
        print(f"Warning: Some dependencies may not have been installed: {str(e)}")
    
    # Step 4: Test Supabase connection
    print("\n=== Testing Supabase connection ===")
    try:
        subprocess.run("python test_supabase_connection.py", shell=True, check=False)
        print("Supabase connection test completed")
    except Exception as e:
        print(f"Warning: Supabase connection test failed: {str(e)}")
        print("You may need to update your Supabase credentials in the .env file")
        print("Continuing with initialization...")
    
    # Step 5: Setup database schema
    print("\n=== Setting up database schema ===")
    try:
        subprocess.run("python setup_supabase.py", shell=True, check=False)
        print("Database schema setup completed")
    except Exception as e:
        print(f"Warning: Database schema setup failed: {str(e)}")
        print("You may need to run this step manually after updating your credentials")
    
    print("\n=== FXML3 Initialization Complete ===")
    print("\nYou can now run the API server with:")
    print("  python run_api.py")
    print("\nAccess the API documentation at:")
    print("  http://localhost:8000/docs")

if __name__ == "__main__":
    main()