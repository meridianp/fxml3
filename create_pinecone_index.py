#!/usr/bin/env python3
"""Script to create a Pinecone index for the FXML3 project."""

import os
import sys
from dotenv import load_dotenv
import time

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import Pinecone
import pinecone


def main():
    """Create a new Pinecone index for the FXML3 project."""
    # Load environment variables
    load_dotenv()
    
    # Get API key directly from .env file
    api_key = None
    try:
        with open('.env', 'r') as f:
            for line in f:
                if line.startswith('PINECONE_API_TOKEN='):
                    api_key = line.strip().split('=', 1)[1]
                    break
    except Exception as e:
        print(f"Error reading .env file: {str(e)}")
        return
        
    print(f"Using API key: {api_key[:5]}...{api_key[-5:]}")
    
    if not api_key:
        print("Error: Pinecone API key not found in environment")
        return
    
    # Configuration
    index_name = "fxml3-wave"  # Using a new name to avoid conflicts
    dimensions = 1536  # OpenAI text-embedding-3-small dimensions
    metric = "cosine"
    
    # Create a Pinecone client
    print("Connecting to Pinecone...")
    try:
        pc = pinecone.Pinecone(api_key=api_key)
        
        # Check if index already exists
        existing_indexes = pc.list_indexes()
        existing_index_names = [idx.name for idx in existing_indexes]
        
        if index_name in existing_index_names:
            print(f"Index '{index_name}' already exists. Using existing index.")
            index = pc.Index(index_name)
        else:
            # Create a new index
            print(f"Creating new index '{index_name}'...")
            pc.create_index(
                name=index_name,
                dimension=dimensions,
                metric=metric,
                spec=pinecone.ServerlessSpec(
                    cloud="aws",
                    region="us-east-1"
                )
            )
            
            # Wait for index to be ready
            print("Waiting for index to be ready...")
            while not pc.describe_index(index_name).status.ready:
                time.sleep(5)
                
            print(f"Index '{index_name}' created successfully!")
            index = pc.Index(index_name)
        
        # Add a test vector to confirm it works
        print("\nAdding a test vector...")
        
        # Create a random vector of the right dimension
        import random
        test_vector = [random.uniform(-1, 1) for _ in range(dimensions)]
        
        # Upsert the vector
        upsert_response = index.upsert(
            vectors=[
                {
                    "id": "test-vector-1",
                    "values": test_vector,
                    "metadata": {
                        "text": "This is a test vector for the Elliott Wave Theory project.",
                        "source": "test",
                        "category": "elliott-wave"
                    }
                }
            ],
            namespace="elliott-wave-theory"
        )
        
        print(f"Vector upserted successfully: {upsert_response}")
        
        # Query to make sure it worked
        print("\nQuerying for the test vector...")
        query_response = index.query(
            vector=test_vector,
            top_k=1,
            include_metadata=True,
            namespace="elliott-wave-theory"
        )
        
        print("Query results:")
        for match in query_response.get("matches", []):
            print(f"  ID: {match.get('id')}")
            print(f"  Score: {match.get('score')}")
            print(f"  Metadata: {match.get('metadata')}")
            
        print("\nPinecone index is working correctly!")
        
        # Print connection details for future use
        print("\nConnection details for your .env file:")
        print(f"PINECONE_API_TOKEN={api_key}")
        print(f"PINECONE_INDEX_NAME={index_name}")
        
    except Exception as e:
        print(f"Error: {str(e)}")


if __name__ == "__main__":
    main()