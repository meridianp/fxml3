#!/usr/bin/env python3
"""Script to load processed chunks into Pinecone vector store."""

import os
import sys
from pathlib import Path

# Add project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from fxml3.llm_integration.knowledge_base import ElliotWaveKnowledgeBase


def main():
    """Load processed documents into Pinecone vector store."""
    # Directory paths
    base_dir = Path(__file__).parent
    processed_dir = base_dir / "fxml3" / "knowledge_assets" / "processed"
    
    # Check if processed directory exists
    if not processed_dir.exists():
        print(f"Error: Processed directory not found at {processed_dir}")
        print("Run build_knowledge_base.py first to process the PDF files")
        return
    
    # Check for processed files
    has_files = False
    for category_dir in processed_dir.iterdir():
        if category_dir.is_dir():
            if list(category_dir.glob("*.txt")):
                has_files = True
                break
    
    if not has_files:
        print("Error: No processed files found in category directories")
        print("Run build_knowledge_base.py first to process the PDF files")
        return
    
    print("Loading processed documents into Pinecone vector store")
    print(f"Source directory: {processed_dir}")
    
    try:
        # Create knowledge base
        kb = ElliotWaveKnowledgeBase(namespace="elliott-wave-theory")
        
        # First, seed with basic knowledge
        print("Seeding knowledge base with basic Elliott Wave theory...")
        basic_ids = kb.seed_basic_knowledge()
        print(f"Added {len(basic_ids)} basic knowledge entries")
        
        # Then load from processed directory
        print(f"Loading knowledge from processed directory: {processed_dir}")
        category_ids = kb.load_from_directory(str(processed_dir))
        
        # Print results
        total_loaded = sum(len(ids) for ids in category_ids.values())
        print(f"Loaded {total_loaded} additional documents into knowledge base")
        print("\nDocuments by category:")
        for category, ids in category_ids.items():
            print(f"  {category}: {len(ids)} documents")
        
        # Test the knowledge base
        print("\nTesting knowledge base with sample queries...")
        test_queries = [
            {"query": "What is Elliott Wave Theory?", "category": "basics"},
            {"query": "Explain impulse wave patterns", "category": "impulse"},
            {"query": "What are corrective waves?", "category": "corrective"},
            {"query": "How are Fibonacci ratios used in Elliott Wave analysis?", "category": "fibonacci"},
            {"query": "What are the rules for wave counting?", "category": "validation"},
        ]
        
        for test in test_queries:
            query = test["query"]
            category = test["category"]
            
            print(f"\nQuery: {query}")
            results = kb.query_knowledge_base(query, category=category, k=1)
            
            if results:
                result = results[0]
                print(f"Top result (score: {result['score']:.4f}):")
                print(f"Source: {result['metadata'].get('source', 'unknown')}")
                
                # Show a snippet
                text = result['text']
                if len(text) > 300:
                    print(f"Snippet: {text[:300]}...")
                else:
                    print(f"Content: {text}")
            else:
                print("No results found")
        
        print("\nKnowledge base successfully loaded and tested!")
        
    except Exception as e:
        print(f"Error loading knowledge base: {str(e)}")
        print("\nPlease check that:")
        print("1. Your Pinecone API key is valid in .env file")
        print("2. You have access to the OpenAI API for embedding generation")
        print("3. The Pinecone index 'fxml3-wave' exists with the correct dimension (1536)")


if __name__ == "__main__":
    main()