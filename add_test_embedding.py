#!/usr/bin/env python3
"""Script to add a test embedding to Pinecone for verification purposes."""

import os
import sys
from dotenv import load_dotenv

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from fxml3.llm_integration.vector_store import PineconeVectorStore, check_pinecone_connection


def main():
    """Add a test embedding to Pinecone."""
    # Check connection first
    print("Checking Pinecone connection...")
    connection_info = check_pinecone_connection()
    
    if not connection_info['connected']:
        print(f"Failed to connect to Pinecone: {connection_info['message']}")
        return
    
    print(f"Connected to Pinecone successfully: {connection_info['message']}")
    
    # Define the index and namespace to use
    index_name = "wave"  # Default index name in PineconeVectorStore
    namespace = "elliott-wave-theory"  # Default namespace in PineconeVectorStore
    
    # Create the vector store
    print(f"\nInitializing vector store with index '{index_name}' and namespace '{namespace}'...")
    try:
        vector_store = PineconeVectorStore(
            index_name=index_name,
            namespace=namespace
        )
        
        # Add a test document
        print("\nAdding test document...")
        test_document = """
        Elliott Wave Theory is a form of technical analysis that attempts to identify market cycles and forecast market trends 
        by identifying extremes in investor psychology, highs and lows in prices, and other collective factors. 
        Ralph Nelson Elliott developed the theory in the 1930s after studying 75 years of stock market data.
        
        The theory identifies a regular pattern of five impulsive waves and three corrective waves in market price movements. 
        The five impulsive waves move in the direction of the main trend, while the three corrective waves move against it.
        
        Key principles of Elliott Wave Theory:
        1. Wave 1: Initial move upward, usually caused by a small group of investors who feel the stock is undervalued
        2. Wave 2: The stock is considered overvalued, and a downward move begins
        3. Wave 3: The longest and strongest wave, when the trend is recognized by the public
        4. Wave 4: A corrective wave against the main trend
        5. Wave 5: The final leg of the trend, often displaying market euphoria
        
        The corrective waves, labeled A, B, and C, move against the trend and typically form more complex patterns.
        """
        
        metadata = {
            "source": "test_document",
            "author": "System",
            "category": "Elliott Wave Theory",
            "importance": "high"
        }
        
        # Add the document to the vector store
        ids = vector_store.add_texts(
            texts=[test_document],
            metadatas=[metadata]
        )
        
        print(f"Successfully added test document with ID: {ids[0]}")
        
        # Verify by searching
        print("\nVerifying by searching for the document...")
        results = vector_store.similarity_search("Elliott Wave Theory principles", k=1)
        
        if results:
            print("Test document found in search results:")
            print(f"  Score: {results[0]['score']}")
            print(f"  ID: {results[0]['id']}")
            print(f"  Text (snippet): {results[0]['text'][:100]}...")
        else:
            print("Test document not found in search results.")
            
    except Exception as e:
        print(f"Error: {str(e)}")


if __name__ == "__main__":
    load_dotenv()
    main()