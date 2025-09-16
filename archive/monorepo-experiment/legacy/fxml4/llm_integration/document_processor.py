"""Document processor for knowledge assets.

This module provides utilities for processing documents (PDFs, text files)
into text chunks suitable for embedding and storage in vector databases.
"""

import json
import os
import re
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import logging

logger = logging.getLogger(__name__)

try:
    import PyPDF2
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    DOCUMENT_PROCESSING_AVAILABLE = True
except ImportError:
    logger.warning("PyPDF2 or langchain not available. Document processing will be limited.")
    DOCUMENT_PROCESSING_AVAILABLE = False


def process_pdf(
    file_path: str,
    chunk_size: int = 1000,
    overlap: int = 200,
    filter_empty: bool = True,
) -> List[str]:
    """Process a PDF file into text chunks.
    
    Args:
        file_path: Path to the PDF file
        chunk_size: Maximum size of each text chunk (in characters)
        overlap: Number of overlapping characters between chunks
        filter_empty: Whether to filter out empty chunks
        
    Returns:
        List of text chunks
        
    Raises:
        ImportError: If PyPDF2 is not installed
        FileNotFoundError: If the file doesn't exist
        ValueError: If the file is not a valid PDF
    """
    if not DOCUMENT_PROCESSING_AVAILABLE:
        raise ImportError(
            "PyPDF2 package not installed. Install it with: pip install PyPDF2"
        )
    
    # Check if file exists
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
        
    try:
        # Open the PDF file
        with open(file_path, "rb") as f:
            # Create PDF reader object
            pdf_reader = PyPDF2.PdfReader(f)
            
            # Get number of pages
            num_pages = len(pdf_reader.pages)
            
            # Extract text from each page
            text = ""
            for page_num in range(num_pages):
                page = pdf_reader.pages[page_num]
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n\n"
        
        # Create chunks with overlap
        return create_chunks(text, chunk_size, overlap, filter_empty)
    except PyPDF2.errors.PdfReadError:
        raise ValueError(f"Invalid PDF file: {file_path}")
    except Exception as e:
        logger.exception(f"Error processing PDF {file_path}: {str(e)}")
        raise


def process_text_file(
    file_path: str,
    chunk_size: int = 1000,
    overlap: int = 200,
    filter_empty: bool = True,
) -> List[str]:
    """Process a text file into chunks.
    
    Args:
        file_path: Path to the text file
        chunk_size: Maximum size of each text chunk (in characters)
        overlap: Number of overlapping characters between chunks
        filter_empty: Whether to filter out empty chunks
        
    Returns:
        List of text chunks
        
    Raises:
        FileNotFoundError: If the file doesn't exist
    """
    # Check if file exists
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
        
    try:
        # Read the text file
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()
        
        # Create chunks with overlap
        return create_chunks(text, chunk_size, overlap, filter_empty)
    except UnicodeDecodeError:
        # Try with a different encoding
        with open(file_path, "r", encoding="latin-1") as f:
            text = f.read()
        return create_chunks(text, chunk_size, overlap, filter_empty)
    except Exception as e:
        logger.exception(f"Error processing text file {file_path}: {str(e)}")
        raise


def create_chunks(
    text: str,
    chunk_size: int = 1000,
    overlap: int = 200,
    filter_empty: bool = True,
) -> List[str]:
    """Split text into chunks with overlap.
    
    Args:
        text: The text to split
        chunk_size: Maximum size of each chunk (in characters)
        overlap: Number of overlapping characters between chunks
        filter_empty: Whether to filter out empty chunks
        
    Returns:
        List of text chunks
    """
    if not DOCUMENT_PROCESSING_AVAILABLE:
        # Fallback to simple chunking if langchain is not available
        return _simple_text_chunks(text, chunk_size, overlap, filter_empty)
    
    try:
        # Clean the text
        text = clean_text(text)
        
        # Create text splitter
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=overlap,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
        
        # Split text into chunks
        chunks = text_splitter.split_text(text)
        
        # Filter empty chunks if requested
        if filter_empty:
            chunks = [chunk for chunk in chunks if chunk.strip()]
            
        return chunks
    except Exception as e:
        logger.warning(f"Error using langchain text splitter: {str(e)}. Falling back to simple chunking.")
        return _simple_text_chunks(text, chunk_size, overlap, filter_empty)


def _simple_text_chunks(
    text: str,
    chunk_size: int = 1000,
    overlap: int = 200,
    filter_empty: bool = True,
) -> List[str]:
    """Simple implementation of text chunking without langchain dependency."""
    # Clean the text
    text = clean_text(text)
    
    # Split the text into chunks
    chunks = []
    start = 0
    while start < len(text):
        # Define chunk end with overlap
        end = min(start + chunk_size, len(text))
        
        # Try to find a good breaking point (end of sentence, paragraph, etc.)
        if end < len(text):
            # Look for end of paragraph
            paragraph_end = text.rfind("\n\n", start, end)
            if paragraph_end != -1 and paragraph_end > start + chunk_size // 2:
                end = paragraph_end + 2
            else:
                # Look for end of sentence
                sentence_end = find_sentence_end(text, start, end)
                if sentence_end != -1:
                    end = sentence_end
        
        # Get the chunk
        chunk = text[start:end].strip()
        
        # Add to list if not empty or if we're not filtering
        if chunk or not filter_empty:
            chunks.append(chunk)
        
        # Move to next chunk with overlap
        start = end - overlap if end - overlap > start else end
    
    return chunks


def clean_text(text: str) -> str:
    """Clean text of common issues.
    
    Args:
        text: Text to clean
        
    Returns:
        Cleaned text
    """
    # Replace multiple newlines with double newlines
    text = re.sub(r"\n{3,}", "\n\n", text)
    
    # Replace multiple spaces with single space
    text = re.sub(r" {2,}", " ", text)
    
    # Replace tabs with spaces
    text = text.replace("\t", " ")
    
    # Fix Unicode issues
    text = text.replace("\uf0b7", "•")  # Replace Unicode bullet
    text = text.replace("\uf0a7", "→")  # Replace Unicode arrow
    
    # Replace smart quotes with regular quotes
    text = text.replace(""", "\"").replace(""", "\"")
    text = text.replace("'", "'").replace("'", "'")
    
    # Fix common PDF extraction issues
    text = text.replace("-\n", "")  # Remove hyphenation
    
    return text


def find_sentence_end(text: str, start: int, end: int) -> int:
    """Find the end of a sentence within a range.
    
    Args:
        text: The text to search
        start: Start position
        end: End position
        
    Returns:
        Position of the end of the sentence, or -1 if not found
    """
    # Look for sentence-ending punctuation followed by space or newline
    for punctuation in [".", "!", "?"]:
        pos = text.rfind(punctuation, start, end)
        if pos != -1 and pos + 1 < len(text):
            # Check for a space or newline after the punctuation
            if pos + 1 >= len(text) or text[pos + 1] in [" ", "\n"]:
                return pos + 1
    
    # If no sentence end found, look for line end
    pos = text.rfind("\n", start, end)
    if pos != -1:
        return pos + 1
    
    # If nothing found, just return -1
    return -1


def save_chunks(
    chunks: List[str],
    output_dir: str,
    prefix: str,
    metadata: Optional[Dict] = None,
) -> List[str]:
    """Save text chunks to files.
    
    Args:
        chunks: List of text chunks
        output_dir: Directory to save the chunks
        prefix: Prefix for the chunk filenames
        metadata: Optional metadata to include with each chunk
        
    Returns:
        List of file paths
    """
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Save chunks to files
    file_paths = []
    for i, chunk in enumerate(chunks):
        # Create filename
        filename = f"{prefix}_{i+1:03d}.txt"
        file_path = os.path.join(output_dir, filename)
        
        # Create metadata file if metadata is provided
        if metadata:
            metadata_filename = f"{prefix}_{i+1:03d}.json"
            metadata_path = os.path.join(output_dir, metadata_filename)
            
            # Add chunk number and timestamp to metadata
            chunk_metadata = metadata.copy()
            chunk_metadata["chunk_num"] = i + 1
            chunk_metadata["timestamp"] = time.time()
            
            # Save metadata
            with open(metadata_path, "w", encoding="utf-8") as f:
                json.dump(chunk_metadata, f, indent=2)
        
        # Save chunk
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(chunk)
            
        file_paths.append(file_path)
    
    return file_paths


def process_document(
    input_path: str,
    output_dir: str,
    chunk_size: int = 1000,
    overlap: int = 200,
    metadata: Optional[Dict] = None,
    category: Optional[str] = None,
) -> List[str]:
    """Process a document into chunks and save them.
    
    Args:
        input_path: Path to the input document
        output_dir: Directory to save the chunks
        chunk_size: Maximum size of each chunk (in characters)
        overlap: Number of overlapping characters between chunks
        metadata: Optional metadata to include with each chunk
        category: Optional category for organizing chunks
        
    Returns:
        List of file paths
    """
    # Get file type
    _, ext = os.path.splitext(input_path)
    ext = ext.lower()
    
    # Create file prefix from input filename
    prefix = os.path.splitext(os.path.basename(input_path))[0]
    
    # Process based on file type
    if ext == ".pdf":
        chunks = process_pdf(input_path, chunk_size, overlap)
    elif ext in [".txt", ".md"]:
        chunks = process_text_file(input_path, chunk_size, overlap)
    else:
        raise ValueError(f"Unsupported file type: {ext}")
    
    # Update output directory with category if provided
    if category:
        output_dir = os.path.join(output_dir, category)
    
    # Update metadata with source and category
    if metadata is None:
        metadata = {}
    metadata["source"] = prefix
    if category:
        metadata["category"] = category
    
    # Save chunks
    return save_chunks(chunks, output_dir, prefix, metadata)


def process_directory(
    input_dir: str,
    output_dir: str,
    chunk_size: int = 1000,
    overlap: int = 200,
    recursive: bool = False,
    category: Optional[str] = None,
) -> Dict[str, int]:
    """Process all documents in a directory.
    
    Args:
        input_dir: Directory containing documents
        output_dir: Directory to save the chunks
        chunk_size: Maximum size of each chunk (in characters)
        overlap: Number of overlapping characters between chunks
        recursive: Whether to process subdirectories
        category: Optional category for organizing chunks
        
    Returns:
        Dictionary with statistics about processed files
    """
    results = {"files_processed": 0, "chunks_created": 0, "errors": 0}
    
    # Get list of files to process
    if recursive:
        file_paths = []
        for root, _, files in os.walk(input_dir):
            for file in files:
                if file.lower().endswith((".pdf", ".txt", ".md")):
                    file_paths.append(os.path.join(root, file))
    else:
        file_paths = [
            os.path.join(input_dir, f) for f in os.listdir(input_dir)
            if os.path.isfile(os.path.join(input_dir, f)) and
            f.lower().endswith((".pdf", ".txt", ".md"))
        ]
    
    # Process each file
    for file_path in file_paths:
        try:
            # Use path within input_dir to determine category if not provided
            file_category = category
            if not file_category and recursive:
                rel_path = os.path.relpath(os.path.dirname(file_path), input_dir)
                if rel_path != ".":
                    file_category = rel_path.replace(os.path.sep, "_")
            
            # Process the document
            files = process_document(
                file_path, 
                output_dir, 
                chunk_size, 
                overlap,
                category=file_category,
            )
            results["files_processed"] += 1
            results["chunks_created"] += len(files)
            
            logger.info(f"Processed {file_path} into {len(files)} chunks")
        except Exception as e:
            logger.error(f"Error processing {file_path}: {str(e)}")
            results["errors"] += 1
    
    return results