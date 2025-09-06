#!/usr/bin/env python3
"""Script to check Pinecone index contents and clean up if needed."""

import os
import sys
import time
from dotenv import load_dotenv

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import our vector store
from fxml3.llm_integration.vector_store import PineconeVectorStore


def main():
    """Check Pinecone index contents and clean up."""
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
    
    # Initialize the vector store
    try:
        print("Initializing Pinecone vector store...")
        vector_store = PineconeVectorStore(
            index_name="fxml3-wave",
            namespace="elliott-wave-theory",
            api_key=api_key
        )
        
        # Directly use Pinecone API to check index contents
        print("\nChecking index contents...")
        
        # First try a direct query to see what's in the index
        dummy_vector = [0.0] * 1536  # Create a dummy vector to query with
        results = vector_store.index.query(
            vector=dummy_vector,
            top_k=100,  # Get all the vectors we have (assuming < 100)
            include_metadata=True,
            namespace="elliott-wave-theory"
        )
        
        # Print the results
        vectors = results.get("matches", [])
        print(f"Found {len(vectors)} vectors in the index:")
        
        for i, vector in enumerate(vectors):
            vector_id = vector.get("id", "")
            metadata = vector.get("metadata", {})
            score = vector.get("score", 0)
            text_preview = metadata.get("text", "")[:100] + "..." if metadata.get("text") else "No text"
            
            print(f"\nVector {i+1}:")
            print(f"  ID: {vector_id}")
            print(f"  Score: {score}")
            print(f"  Text preview: {text_preview}")
            print(f"  Metadata: {metadata}")
        
        # Automatically clean up the index
        print("\nDeleting all vectors and rebuilding the index...")
        print("Deleting all vectors...")
        vector_store.delete(delete_all=True)
        print("All vectors deleted successfully.")
        
        # Verify deletion
        verify_results = vector_store.index.query(
            vector=dummy_vector,
            top_k=10,
            include_metadata=True,
            namespace="elliott-wave-theory"
        )
        
        if len(verify_results.get("matches", [])) == 0:
            print("Verification successful: No vectors remain in the index.")
        else:
            print(f"Warning: Still found {len(verify_results.get('matches', []))} vectors in the index.")
        
        # Automatically add the Elliott Wave document
        print("\nAdding Elliott Wave document...")
        
        # Read the document from the file we created earlier
        with open("test_rag_embedding.py", "r") as f:
            content = f.read()
            start_marker = 'elliott_wave_document = """'
            end_marker = '    """'
            
            if start_marker in content and end_marker in content:
                start_index = content.find(start_marker) + len(start_marker)
                end_index = content.find(end_marker, start_index)
                
                if start_index > -1 and end_index > -1:
                    elliott_wave_document = content[start_index:end_index].strip()
                    
                    # Add the document
                    document_id = vector_store.add_texts(
                        texts=[elliott_wave_document],
                        metadatas=[{
                            "source": "elliott_wave_theory_guide",
                            "author": "System",
                            "category": "Trading Theory",
                            "topic": "Elliott Wave",
                            "difficulty": "intermediate"
                        }]
                    )
                    
                    print(f"Document added with ID: {document_id[0]}")
                    
                    # Wait for indexing
                    time.sleep(2)
                    
                    # Test a query
                    print("\nTesting a query...")
                    test_query = "What are the five waves in Elliott Wave Theory?"
                    results = vector_store.similarity_search(test_query, k=1)
                    
                    if results:
                        print(f"Found matching document with score: {results[0]['score']}")
                        print(f"Document ID: {results[0]['id']}")
                        text = results[0]['text']
                        start_pos = max(0, text.lower().find("five waves") - 100)
                        snippet = text[start_pos:start_pos + 300]
                        print(f"Relevant snippet: '{snippet}...'")
                    else:
                        print("No results found")
                else:
                    print("Couldn't parse the Elliott Wave document from the file.")
            else:
                print("Couldn't find the Elliott Wave document in the file.")
        
    except Exception as e:
        print(f"Error: {str(e)}")


if __name__ == "__main__":
    main()