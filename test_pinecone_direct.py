#!/usr/bin/env python3
"""Direct test script for Pinecone with explicit API key."""

import os
import sys
import pinecone

def main():
    """Test Pinecone connection with explicit API key."""
    # Get API key directly from .env file
    try:
        with open('.env', 'r') as f:
            for line in f:
                if line.startswith('PINECONE_API_TOKEN='):
                    api_key = line.strip().split('=', 1)[1]
                    break
    except Exception as e:
        print(f"Error reading .env file: {str(e)}")
        return
    
    print(f"API key: {api_key[:5]}...{api_key[-5:]}")
    
    # Try connecting to Pinecone
    print("Connecting to Pinecone...")
    try:
        pc = pinecone.Pinecone(api_key=api_key)
        
        # List indexes
        indexes = pc.list_indexes()
        
        print(f"Connection successful! Found {len(indexes)} indexes.")
        for idx in indexes:
            print(f"- {idx.name}")
            
    except Exception as e:
        print(f"Error connecting to Pinecone: {str(e)}")
        
        # Check if we need to use the legacy API
        print("\nTrying with legacy Pinecone API...")
        try:
            from pinecone import Pinecone as PineconeNew
            pc = PineconeNew(api_key=api_key)
            indexes = pc.list_indexes()
            print(f"Legacy connection successful! Found {len(indexes)} indexes.")
        except Exception as e2:
            print(f"Legacy API also failed: {str(e2)}")
            
            # Print API key format information
            print("\nAPI key format check:")
            if not api_key.startswith("pcsk_"):
                print("- Warning: API key doesn't start with 'pcsk_' (typical Pinecone prefix)")
            if len(api_key) < 40:
                print(f"- Warning: API key is only {len(api_key)} characters (typical keys are 70+ characters)")
            print("- Make sure there are no quotes or extra spaces in the API key")
            print("- Verify the API key was generated recently and hasn't expired")
            print("- Ensure you're using the API key from your active Pinecone project")

if __name__ == "__main__":
    main()