#!/usr/bin/env python
"""
Test script for Supabase connection for FXML3.
Run this script to verify that the Supabase connection works.
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client, Client

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))


def main():
    """Run the test script."""
    print("Testing Supabase connection for FXML3...")
    
    # Load environment variables
    load_dotenv()
    
    # Get Supabase credentials
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_ANON_KEY")
    supabase_service_key = os.getenv("SUPABASE_SERVICE_KEY")
    
    if not all([supabase_url, supabase_key, supabase_service_key]):
        print("Error: Missing required Supabase environment variables")
        sys.exit(1)
    
    try:
        # Create Supabase client
        print("Creating Supabase client...")
        print(f"Using URL: {supabase_url}")
        client = create_client(supabase_url, supabase_key)
        
        # Test connection by fetching user roles
        print("Testing connection...")
        # Just test if we can authenticate - don't try to query a table yet
        auth_response = client.auth.get_user()
        print("Authentication successful.")
        
        # If we get here, connection is successful
        print(f"Success! Connected to Supabase.")
        
    except Exception as e:
        print(f"Error connecting to Supabase: {str(e)}")
        # Print detailed connection information for debugging
        print(f"\nConnection details:")
        print(f"  URL: {supabase_url}")
        print(f"  Anon Key: {supabase_key[:5]}...{supabase_key[-5:] if len(supabase_key) > 10 else ''}")
        
        # Check if PostgreSQL connection variables exist
        print(f"\nPostgreSQL connection variables:")
        print(f"  Host: {os.getenv('POSTGRES_HOST')}")
        print(f"  Port: {os.getenv('POSTGRES_PORT')}")
        print(f"  Username: {os.getenv('POSTGRES_USERNAME')}")
        print(f"  DB Name: {os.getenv('POSTGRES_DB_NAME')}")
        print(f"  Password: {'Exists' if os.getenv('POSTGRES_PASSWORD') else 'Missing'}")
        
        sys.exit(1)
    
    print("Connection test completed successfully")


if __name__ == "__main__":
    main()