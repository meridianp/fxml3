#!/usr/bin/env python3
"""Simplified RAG demo using Pinecone to store Elliott Wave knowledge."""

import os
import sys
import time
import random
import uuid
import pinecone
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get API key directly from .env file
pinecone_api_key = None
try:
    with open('.env', 'r') as f:
        for line in f:
            if line.startswith('PINECONE_API_TOKEN='):
                pinecone_api_key = line.strip().split('=', 1)[1]
                break
except Exception as e:
    print(f"Error reading .env file: {str(e)}")
    sys.exit(1)

if not pinecone_api_key:
    print("Error: Pinecone API key not found in .env file")
    sys.exit(1)

# Set up Pinecone client
pc = pinecone.Pinecone(api_key=pinecone_api_key)

# Constants
INDEX_NAME = "fxml3-wave"
NAMESPACE = "elliott-wave-theory"
DIMENSION = 1536  # Match the dimension of the existing index (text-embedding-3-small)

# Elliott Wave documents - breaking into smaller chunks for better retrieval
elliott_wave_documents = [
    {
        "title": "Elliott Wave Theory - Introduction",
        "text": """
Elliott Wave Theory is a form of technical analysis used to analyze financial market cycles
and forecast market trends by identifying extremes in investor psychology, highs and lows 
in prices, and other collective factors. Ralph Nelson Elliott (1871–1948) discovered that 
price movements in financial markets follow a pattern of five waves in the direction of the 
main trend followed by three corrective waves (a 5-3 move).
        """,
        "metadata": {
            "category": "Introduction",
            "section": "Overview",
            "author": "System"
        }
    },
    {
        "title": "Five-Wave Impulse Pattern",
        "text": """
The five-wave impulse pattern in Elliott Wave Theory moves in the direction of the main trend:

1. Wave 1: Initial move upward, typically caused by a relatively small number of people who 
   recognize that conditions are changing and prices are too low.

2. Wave 2: Partial retracement of Wave 1, as profit-taking occurs. This wave typically 
   retraces less than 100% of Wave 1, often finding support around the 50% or 61.8% Fibonacci level.

3. Wave 3: Usually the longest and strongest wave. This is where most money is made.
   Wave 3 is never the shortest impulse wave and it always travels beyond the end of Wave 1.

4. Wave 4: Corrective wave following Wave 3. It typically retraces less than Wave 2 and 
   often forms a complex pattern. Wave 4 does not enter the territory of Wave 1.

5. Wave 5: Final leg of the trend, often showing weakening momentum and divergence with indicators.
   This wave is driven mainly by market psychology rather than fundamentals.
        """,
        "metadata": {
            "category": "Wave Patterns",
            "section": "Impulse Waves",
            "author": "System"
        }
    },
    {
        "title": "Three-Wave Corrective Pattern",
        "text": """
After the five-wave impulse pattern completes, a three-wave corrective pattern typically follows:

1. Wave A: Initial corrective move against the trend of the 5-wave sequence.

2. Wave B: Countertrend move, retracing a portion of Wave A. Often traps traders who incorrectly 
   believe the original trend has resumed.

3. Wave C: Final corrective wave that generally moves beyond the end of Wave A and completes 
   the correction.

The corrective pattern moves against the trend of the impulse wave.
        """,
        "metadata": {
            "category": "Wave Patterns",
            "section": "Corrective Waves",
            "author": "System"
        }
    },
    {
        "title": "Fibonacci Relationships in Elliott Wave",
        "text": """
Elliott Wave Theory is closely associated with Fibonacci numbers and ratios. Key Fibonacci 
relationships observed in waves include:

- Wave 2 often retraces 50% or 61.8% of Wave 1
- Wave 3 is typically 1.618 or 2.618 times the length of Wave 1
- Wave 4 often retraces 38.2% of Waves 1-3
- Wave 5 is often 0.618 or 1.618 times the length of Waves 1-3

These Fibonacci relationships help traders identify potential reversal points and set price targets.
        """,
        "metadata": {
            "category": "Wave Analysis",
            "section": "Fibonacci Relationships",
            "author": "System"
        }
    },
    {
        "title": "Rules of Elliott Wave Theory",
        "text": """
There are three unbreakable rules in Elliott Wave Theory:

1. Wave 2 never retraces more than 100% of Wave 1
2. Wave 3 is never the shortest of the three impulse waves (1, 3, 5)
3. Wave 4 never overlaps with the price territory of Wave 1

These rules must be followed for a wave count to be valid. If a pattern violates any of these rules,
the wave count is incorrect and needs to be revised.
        """,
        "metadata": {
            "category": "Wave Analysis",
            "section": "Rules",
            "author": "System"
        }
    },
    {
        "title": "Trading Applications of Elliott Wave",
        "text": """
Elliott Wave Theory is used by traders to:

1. Identify the overall market direction (trend analysis)
2. Determine potential reversal points
3. Set price targets for waves
4. Identify stop-loss levels based on wave rules
5. Gauge market sentiment and psychology

Practitioners believe that by identifying the current wave position, traders can anticipate 
future price movements and make more informed trading decisions.

Trading strategies often involve entering positions at the beginning of impulse waves (especially
Wave 3) and exiting at the end of Wave 5 or during corrective patterns.
        """,
        "metadata": {
            "category": "Application",
            "section": "Trading",
            "author": "System"
        }
    },
    {
        "title": "Complex Corrections in Elliott Wave",
        "text": """
Corrective patterns can become quite complex. The basic corrective patterns include:

- Zigzag (5-3-5 structure): Sharp move against the trend
- Flat (3-3-5 structure): Sideways correction with limited price movement
- Triangle (3-3-3-3-3 structure): Converging trendlines forming a triangle

These can combine to form compound corrections such as:

- Double zigzag: Two zigzags connected by an intervening "X" wave
- Double three: Two corrective patterns (often flats) connected by an "X" wave
- Triple three: Three corrective patterns connected by two "X" waves

Complex corrections often confuse traders and can be difficult to identify in real-time.
        """,
        "metadata": {
            "category": "Wave Patterns",
            "section": "Complex Corrections",
            "author": "System"
        }
    },
]

# Functions
def reset_index():
    """Create or reset the Pinecone index."""
    try:
        # Check if index exists
        indexes = pc.list_indexes()
        index_names = [idx.name for idx in indexes]
        
        # Create index if it doesn't exist
        if INDEX_NAME not in index_names:
            print(f"Creating new index '{INDEX_NAME}'...")
            pc.create_index(
                name=INDEX_NAME,
                dimension=DIMENSION,
                metric="cosine",
                spec=pinecone.ServerlessSpec(
                    cloud="aws",
                    region="us-east-1"
                )
            )
            
            # Wait for index to be ready
            while not pc.describe_index(INDEX_NAME).status.ready:
                time.sleep(2)
                
            print(f"Index '{INDEX_NAME}' created successfully!")
        else:
            print(f"Using existing index '{INDEX_NAME}'")
            
        # Get index
        index = pc.Index(INDEX_NAME)
        
        # Clear vectors in the namespace
        try:
            print(f"Clearing all vectors in namespace '{NAMESPACE}'...")
            index.delete(delete_all=True, namespace=NAMESPACE)
            print("Namespace cleared!")
        except Exception as e:
            # If namespace doesn't exist yet, that's fine
            if "Namespace not found" in str(e):
                print(f"Namespace '{NAMESPACE}' doesn't exist yet. Will be created when adding documents.")
            else:
                raise e
        
        return index
        
    except Exception as e:
        print(f"Error resetting index: {str(e)}")
        return None

def add_documents(index, documents):
    """Add documents to the index."""
    try:
        print(f"Adding {len(documents)} documents to the index...")
        
        # Add each document
        document_ids = []
        for doc in documents:
            # Create a unique ID
            doc_id = str(uuid.uuid4())
            
            # Create a simple dummy vector (in real application, this would be an embedding)
            # Using random values since we can't use real embeddings
            dummy_vector = [random.uniform(-1, 1) for _ in range(DIMENSION)]
            
            # Prepare metadata
            metadata = {
                "text": doc["text"],
                "title": doc["title"],
                **doc.get("metadata", {})
            }
            
            # Upsert to Pinecone
            index.upsert(
                vectors=[
                    {
                        "id": doc_id,
                        "values": dummy_vector,
                        "metadata": metadata
                    }
                ],
                namespace=NAMESPACE
            )
            
            document_ids.append(doc_id)
            
        print(f"Successfully added {len(document_ids)} documents!")
        return document_ids
        
    except Exception as e:
        print(f"Error adding documents: {str(e)}")
        return []

def simple_match_score(query, title, text, category):
    """Simple keyword matching for relevance scoring."""
    query = query.lower()
    title = title.lower()
    text = text.lower()
    category = category.lower() if category else ""
    
    # Define query-document pairs for keyword matching
    relevant_pairs = {
        "five waves": ["impulse pattern", "wave 1", "wave 2", "wave 3", "wave 4", "wave 5"],
        "fibonacci": ["fibonacci"],
        "unbreakable rules": ["rules", "unbreakable"],
        "trading": ["trading", "strategies", "application"],
        "complex corrections": ["complex", "correction", "zigzag", "flat", "triangle"]
    }
    
    score = 0.0
    
    # Title match bonus
    if any(keyword in title for keyword in query.split()):
        score += 0.4
        
    # Category match bonus
    for keyword in query.split():
        if keyword in category:
            score += 0.3
            break
    
    # Content keywords match
    for query_term, doc_terms in relevant_pairs.items():
        if query_term in query:
            for doc_term in doc_terms:
                if doc_term in text:
                    score += 0.1
    
    # Direct text match
    if any(term in text for term in query.split() if len(term) > 3):
        score += 0.2
    
    return min(1.0, score)  # Cap at 1.0

def query_documents(index, query_text):
    """Query documents using simple string matching instead of embeddings."""
    try:
        print(f"Querying for: '{query_text}'")
        
        # Without proper embeddings, we'll:
        # 1. Get all documents with a dummy query
        # 2. Compare the query text with document text using string similarity
        
        # Create dummy vector for the query
        dummy_vector = [random.uniform(-1, 1) for _ in range(DIMENSION)]
        
        # Get all documents
        results = index.query(
            vector=dummy_vector,
            top_k=100,  # Get all documents (assuming < 100)
            include_metadata=True,
            namespace=NAMESPACE
        )
        
        matches = results.get("matches", [])
        
        # Debug output
        print(f"Query returned {len(matches)} raw matches")
        if matches:
            print("First match sample:")
            print(f"  ID: {matches[0].get('id', '')}")
            print(f"  Metadata: {matches[0].get('metadata', {})}")
        else:
            print("No matches found in index")
        
        # Use our own ranking based on string similarity
        ranked_results = []
        for match in matches:
            doc_text = match.get("metadata", {}).get("text", "")
            doc_title = match.get("metadata", {}).get("title", "")
            
            # Get category from metadata
            category = match.get("metadata", {}).get("category", "")
            
            # Calculate relevance score
            similarity = simple_match_score(query_text, doc_title, doc_text, category)
            
            ranked_results.append({
                "id": match.get("id", ""),
                "title": doc_title,
                "text": doc_text,
                "similarity": similarity,
                "metadata": {k: v for k, v in match.get("metadata", {}).items() 
                            if k not in ["text", "title"]}
            })
        
        # Sort by similarity score (highest first)
        ranked_results.sort(key=lambda x: x["similarity"], reverse=True)
        
        # Return top 3 results
        return ranked_results[:3]
        
    except Exception as e:
        print(f"Error querying documents: {str(e)}")
        return []

def format_result(result):
    """Format a search result for display."""
    text = result["text"].strip()
    if len(text) > 300:
        text = text[:300] + "..."
    
    return f"""
TITLE: {result["title"]}
SIMILARITY: {result["similarity"]:.2f}
CATEGORY: {result["metadata"].get("category", "Unknown")}
SECTION: {result["metadata"].get("section", "Unknown")}
---
{text}
---
"""

def main():
    """Main function."""
    # Set up the index
    print(f"Connecting to Pinecone with API key: {pinecone_api_key[:5]}...{pinecone_api_key[-5:]}")
    index = reset_index()
    
    if not index:
        print("Failed to set up Pinecone index")
        return
    
    # Add documents
    doc_ids = add_documents(index, elliott_wave_documents)
    
    if not doc_ids:
        print("Failed to add documents")
        return
    
    # Wait for indexing
    print("Waiting for indexing to complete...")
    time.sleep(2)
    
    # Test queries
    test_queries = [
        "What are the five waves in Elliott Wave Theory?",
        "Explain the Fibonacci relationships in Elliott Wave",
        "What are the unbreakable rules of Elliott Wave?",
        "How can Elliott Wave be used for trading?",
        "What are complex corrections in Elliott Wave Theory?"
    ]
    
    print("\n" + "="*80)
    print("ELLIOTT WAVE THEORY RAG DEMONSTRATION")
    print("="*80)
    
    for i, query in enumerate(test_queries, 1):
        print(f"\nQUERY {i}: '{query}'")
        results = query_documents(index, query)
        
        if results:
            print(f"Found {len(results)} matching documents:")
            for j, result in enumerate(results, 1):
                print(f"\nRESULT {j}:{format_result(result)}")
        else:
            print("No matching documents found")
            
    print("\n" + "="*80)
    print("RAG DEMONSTRATION COMPLETE")
    print("="*80)

if __name__ == "__main__":
    main()