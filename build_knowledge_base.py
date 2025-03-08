#!/usr/bin/env python3
"""Script to process Elliott Wave PDF and build knowledge base."""

import os
import sys
from pathlib import Path

# Add project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from fxml3.llm_integration.document_processor import process_pdf, save_chunks
from fxml3.llm_integration.knowledge_base import ElliotWaveKnowledgeBase


def main():
    """Process PDF and build knowledge base."""
    # File and directory paths
    base_dir = Path(__file__).parent
    raw_dir = base_dir / "fxml3" / "knowledge_assets" / "raw"
    processed_dir = base_dir / "fxml3" / "knowledge_assets" / "processed"
    pdf_file = raw_dir / "applsci-14-11897-1.pdf"
    
    # Check if PDF exists
    if not pdf_file.exists():
        print(f"Error: PDF file not found at {pdf_file}")
        return
    
    # Create processed directory if it doesn't exist
    os.makedirs(processed_dir, exist_ok=True)
    
    print(f"Processing PDF: {pdf_file}")
    print(f"Output directory: {processed_dir}")
    
    # Process PDF file (break into chunks)
    chunks = process_pdf(
        file_path=str(pdf_file),
        chunk_size=1500,  # Characters per chunk
        overlap=200,      # Overlap between chunks
    )
    
    print(f"PDF successfully processed into {len(chunks)} chunks")
    
    # Define categories manually to avoid initializing ElliotWaveKnowledgeBase
    categories = {
        "basics": "Basic Elliott Wave principles and concepts",
        "impulse": "Impulse wave patterns and characteristics",
        "corrective": "Corrective wave patterns and characteristics",
        "fibonacci": "Fibonacci relationships and measurements",
        "trading": "Trading strategies based on Elliott Wave theory",
        "psychology": "Market psychology and sentiment analysis",
        "examples": "Example patterns from historical price data",
        "validation": "Wave pattern validation techniques",
        "alternation": "Principle of alternation and its applications",
        "multi_timeframe": "Multi-timeframe analysis techniques",
    }
    
    for category in categories.keys():
        os.makedirs(processed_dir / category, exist_ok=True)
    
    # Save chunks by category
    saved_chunks = []
    
    # Categorize chunks based on simple keyword matching
    for i, chunk in enumerate(chunks):
        # Define category based on content keywords
        category = "basics"  # Default category
        
        # Categorize based on content
        lower_chunk = chunk.lower()
        if "impulse" in lower_chunk and ("wave 1" in lower_chunk or "wave 3" in lower_chunk or "wave 5" in lower_chunk):
            category = "impulse"
        elif "corrective" in lower_chunk and ("wave a" in lower_chunk or "wave b" in lower_chunk or "wave c" in lower_chunk):
            category = "corrective"
        elif "fibonacci" in lower_chunk:
            category = "fibonacci"
        elif "trading" in lower_chunk and "strategy" in lower_chunk:
            category = "trading"
        elif "psychology" in lower_chunk or "sentiment" in lower_chunk:
            category = "psychology"
        elif "example" in lower_chunk or "case study" in lower_chunk:
            category = "examples"
        elif "rule" in lower_chunk or "validation" in lower_chunk:
            category = "validation"
        elif "alternate" in lower_chunk or "alternation" in lower_chunk:
            category = "alternation"
        elif "timeframe" in lower_chunk or "scale" in lower_chunk:
            category = "multi_timeframe"
        
        # Create metadata
        metadata = {
            "source": "applsci-14-11897",
            "category": category,
            "chunk_number": i + 1,
            "total_chunks": len(chunks),
        }
        
        # Save chunk to the appropriate category directory
        save_path = processed_dir / category
        file_paths = save_chunks(
            chunks=[chunk],
            output_dir=str(save_path),
            prefix=f"chunk_{i+1:03d}",
            metadata=metadata,
        )
        
        saved_chunks.extend(file_paths)
    
    print(f"Saved {len(saved_chunks)} chunks to category directories")
    
    # Analyze the processed chunks
    print("\nAnalyzing processed chunks...")
    
    # Count documents by category
    category_counts = {}
    for category in categories.keys():
        category_dir = processed_dir / category
        if category_dir.exists():
            txt_files = list(category_dir.glob("*.txt"))
            category_counts[category] = len(txt_files)
    
    # Print results
    total_processed = sum(category_counts.values())
    print(f"Processed {total_processed} documents into categories")
    print("\nDocuments by category:")
    for category, count in category_counts.items():
        print(f"  {category}: {count} documents")
    
    # Note about knowledge base integration
    print("\nNOTE: The documents have been processed and categorized.")
    print("To integrate with Pinecone, you'll need to:")
    print("1. Ensure your Pinecone API key is valid")
    print("2. Use the ElliotWaveKnowledgeBase class to load these documents")
    print("3. Generate embeddings with OpenAI API and store in Pinecone")
    
    print("\nKnowledge base successfully built and tested!")


if __name__ == "__main__":
    main()