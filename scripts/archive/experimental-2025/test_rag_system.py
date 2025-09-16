#!/usr/bin/env python
"""Test script for RAG system with Elliott Wave knowledge.

This script tests the enhanced RAG system with Elliott Wave knowledge.
It initializes the system, seeds it with basic knowledge, and performs queries.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

# Add parent directory to path to import fxml4
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fxml4.llm_integration.document_processor import process_directory
from fxml4.llm_integration.knowledge_base import ElliottWaveKnowledgeBase
from fxml4.llm_integration.rag import RAG


def initialize_rag(config: Dict) -> RAG:
    """Initialize the RAG system with the given configuration.

    Args:
        config: Configuration for RAG system

    Returns:
        Initialized RAG instance
    """
    # Print init progress
    print(f"Initializing RAG system with config: {json.dumps(config, indent=2)}")

    # Initialize RAG system
    rag = RAG(config)

    # Check if initialized
    if not rag.initialized:
        print("Failed to initialize RAG system. Check logs for details.")
        sys.exit(1)

    print("RAG system initialized successfully")
    return rag


def test_simple_query(rag: RAG):
    """Test a simple query to the RAG system.

    Args:
        rag: RAG instance to test
    """
    print("\n--- Testing Simple Query ---")

    question = (
        "What are the key rules for identifying an impulse wave in Elliott Wave theory?"
    )
    result = rag.query(question)

    if result.get("success", False):
        print(f"Question: {question}")
        print(f"Answer: {result.get('answer')}")
        print(f"Sources: {len(result.get('sources', []))}")
    else:
        print(f"Query failed: {result.get('error')}")


def test_validate_patterns(rag: RAG):
    """Test pattern validation with the RAG system.

    Args:
        rag: RAG instance to test
    """
    print("\n--- Testing Pattern Validation ---")

    # Test patterns
    patterns = [
        "An impulse wave showing a clear 5-wave structure with wave 3 extending beyond wave 1 by 1.618 times, and wave 4 not overlapping with wave 1.",
        "A zigzag correction with wave A moving down sharply, wave B retracing 38.2% of wave A, and wave C extending to 1.618 times the length of wave A.",
        "An impulse wave where wave 4 overlaps with wave 1 territory, and wave 3 is shorter than both waves 1 and 5.",
    ]

    for pattern in patterns:
        result = rag.validate_wave_pattern(pattern)

        if result.get("success", False):
            print(f"Pattern: {pattern[:50]}...")
            print(f"Valid: {result.get('is_valid')}")
            print(f"Explanation: {result.get('explanation')[:200]}...\n")
        else:
            print(f"Validation failed: {result.get('error')}")


def test_market_context(rag: RAG):
    """Test market context retrieval with the RAG system.

    Args:
        rag: RAG instance to test
    """
    print("\n--- Testing Market Context ---")

    symbol = "GBPUSD"
    timeframe = "4h"
    result = rag.get_market_context(symbol, timeframe)

    if result.get("success", False):
        print(f"Symbol: {symbol}, Timeframe: {timeframe}")
        print(f"Context: {result.get('context')[:300]}...")
    else:
        print(f"Context retrieval failed: {result.get('error')}")


def test_wave_characteristics(rag: RAG):
    """Test wave characteristics retrieval with the RAG system.

    Args:
        rag: RAG instance to test
    """
    print("\n--- Testing Wave Characteristics ---")

    wave_types = ["impulse", "zigzag", "flat", "triangle"]

    for wave_type in wave_types:
        result = rag.get_wave_characteristics(wave_type)

        if result.get("success", False):
            print(f"Wave Type: {wave_type}")
            print(f"Characteristics: {result.get('characteristics')[:200]}...\n")
        else:
            print(f"Characteristic retrieval failed: {result.get('error')}")


def process_knowledge_assets(kb: ElliottWaveKnowledgeBase, assets_dir: str):
    """Process knowledge assets and add them to the knowledge base.

    Args:
        kb: Elliott Wave knowledge base
        assets_dir: Directory containing knowledge assets
    """
    print("\n--- Processing Knowledge Assets ---")

    # Check if directory exists
    if not os.path.exists(assets_dir):
        print(f"Knowledge assets directory does not exist: {assets_dir}")
        return

    # Look for raw directory
    raw_dir = os.path.join(assets_dir, "raw")
    if os.path.exists(raw_dir):
        print(f"Processing raw documents from {raw_dir}")

        # Process each file in the raw directory
        for filename in os.listdir(raw_dir):
            file_path = os.path.join(raw_dir, filename)
            if os.path.isfile(file_path):
                print(f"Processing {filename}...")

                # Process the file into the processed directory
                processed_dir = os.path.join(assets_dir, "processed")
                os.makedirs(processed_dir, exist_ok=True)

                # Determine file type and category from filename
                _, ext = os.path.splitext(filename)
                if ext.lower() == ".pdf":
                    # Process PDF in chunks
                    from fxml4.llm_integration.document_processor import (
                        process_document,
                    )

                    # Try to determine category from filename
                    if "elliott" in filename.lower():
                        category = "basics"
                    elif "mastering" in filename.lower():
                        category = "trading"
                    else:
                        category = None

                    # Process the document
                    try:
                        result = process_document(
                            file_path,
                            processed_dir,
                            chunk_size=1000,
                            overlap=200,
                            category=category,
                            metadata={"source": filename},
                        )
                        print(f"Processed {len(result)} chunks from {filename}")
                    except Exception as e:
                        print(f"Error processing {filename}: {str(e)}")

    # Load from processed directory
    processed_dir = os.path.join(assets_dir, "processed")
    if os.path.exists(processed_dir):
        print(f"Loading knowledge from {processed_dir}")

        # Load knowledge from processed directory
        result = kb.load_from_directory(processed_dir)

        if result.get("success", False):
            print(
                f"Loaded {result.get('documents_added')} documents from {len(result.get('categories', {}))} categories"
            )
        else:
            print(f"Failed to load knowledge: {result.get('message')}")


def main():
    """Main function for testing RAG system."""
    parser = argparse.ArgumentParser(
        description="Test RAG system with Elliott Wave knowledge"
    )
    parser.add_argument(
        "--seed-knowledge",
        action="store_true",
        help="Seed knowledge base with basic Elliott Wave knowledge",
    )
    parser.add_argument(
        "--process-assets", action="store_true", help="Process knowledge assets"
    )
    parser.add_argument(
        "--assets-dir",
        type=str,
        default="fxml3/knowledge_assets",
        help="Directory containing knowledge assets",
    )
    parser.add_argument(
        "--pinecone-api-key",
        type=str,
        default=None,
        help="Pinecone API key (or set PINECONE_API_KEY env var)",
    )
    parser.add_argument(
        "--pinecone-environment",
        type=str,
        default=None,
        help="Pinecone environment (or set PINECONE_ENVIRONMENT env var)",
    )
    parser.add_argument(
        "--index-name", type=str, default="fxml4-knowledge", help="Pinecone index name"
    )
    parser.add_argument(
        "--namespace",
        type=str,
        default="elliott-wave-theory",
        help="Namespace within the index",
    )
    args = parser.parse_args()

    # Set up configuration
    config = {
        "vector_store": "pinecone",
        "pinecone_api_key": args.pinecone_api_key or os.environ.get("PINECONE_API_KEY"),
        "pinecone_environment": args.pinecone_environment
        or os.environ.get("PINECONE_ENVIRONMENT"),
        "index_name": args.index_name,
        "namespace": args.namespace,
    }

    # Initialize RAG system
    rag = initialize_rag(config)

    # Print RAG status
    status = rag.get_status()
    print("\nRAG Status:")
    print(json.dumps(status, indent=2))

    # Initialize knowledge base
    kb = ElliottWaveKnowledgeBase(rag_instance=rag)

    # Seed knowledge base if requested
    if args.seed_knowledge:
        print("\nSeeding knowledge base...")
        result = kb.seed_basic_knowledge()
        if result.get("success", False):
            print(f"Successfully added {result.get('documents_added')} documents")
        else:
            print(f"Failed to seed knowledge base: {result.get('message')}")

    # Process knowledge assets if requested
    if args.process_assets:
        process_knowledge_assets(kb, args.assets_dir)

    # Run tests
    test_simple_query(rag)
    test_validate_patterns(rag)
    test_market_context(rag)
    test_wave_characteristics(rag)

    print("\nAll tests completed")


if __name__ == "__main__":
    main()
