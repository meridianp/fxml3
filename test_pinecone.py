#!/usr/bin/env python3
"""Test script to check Pinecone connectivity and verify searchable embeddings."""

import os
import sys
import json
from dotenv import load_dotenv

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Direct Pinecone test (not using our wrapper)
import pinecone


def main():
    """Test Pinecone connectivity and search for embeddings using direct Pinecone API."""
    # Load environment variables
    load_dotenv()
    
    # Get API credentials
    api_key = os.environ.get("PINECONE_API_TOKEN")
    environment = os.environ.get("PINECONE_ENVIRONMENT", "us-east-1")
    
    if not api_key:
        print("Error: Pinecone API key not found in environment")
        return
    
    # Create a Pinecone client
    print("Connecting to Pinecone...")
    try:
        pc = pinecone.Pinecone(api_key=api_key)
        
        # List indexes
        indexes = pc.list_indexes()
        
        print(f"Connected to Pinecone successfully. Found {len(indexes)} indexes.")
        
        # Show available indexes
        print("\nAvailable indexes:")
        for idx in indexes:
            print(f"- {idx.name}")
        
        if not indexes:
            print("\nNo indexes found. You need to create an index first.")
            return
        
        # Get stats for each index
        print("\nIndex statistics:")
        vector_exists = False
        test_index = None
        
        for idx_info in indexes:
            index_name = idx_info.name
            index = pc.Index(index_name)
            
            try:
                stats = index.describe_index_stats()
                total_vector_count = stats.get('total_vector_count', 0)
                dimension = stats.get('dimension')
                
                print(f"\n{index_name}:")
                print(f"  Total vectors: {total_vector_count}")
                print(f"  Dimension: {dimension}")
                
                namespaces = stats.get('namespaces', {})
                if namespaces:
                    print("  Namespaces:")
                    for ns_name, ns_stats in namespaces.items():
                        vector_count = ns_stats.get('vector_count', 0)
                        print(f"    - {ns_name}: {vector_count} vectors")
                        
                        # Keep track of a namespace with vectors for testing
                        if vector_count > 0:
                            vector_exists = True
                            test_index = index_name
                            test_namespace = ns_name
                else:
                    print("  No namespaces found")
                    
            except Exception as e:
                print(f"  Error getting stats for {index_name}: {str(e)}")
        
        # Test search if vectors exist
        if vector_exists and test_index:
            print(f"\nTesting search on index '{test_index}' in namespace '{test_namespace}'...")
            
            try:
                # We'd need an OpenAI API key to generate embeddings for search
                # For now, just report the status
                print("Vectors exist, but can't perform search without embedding generation.")
                print("To perform a proper search, use the API with embeddings from OpenAI.")
                
            except Exception as e:
                print(f"Error during search preparation: {str(e)}")
        else:
            print("\nNo vectors found in any index. You need to add embeddings first.")
            
    except Exception as e:
        print(f"Error connecting to Pinecone: {str(e)}")


if __name__ == "__main__":
    load_dotenv()
    main()