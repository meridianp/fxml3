#!/usr/bin/env python3
"""Direct test of Pinecone and OpenAI embeddings for RAG."""

import os
import time
import openai
import pinecone
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get API keys
def get_env_var(var_name):
    """Get environment variable from .env file."""
    try:
        with open('.env', 'r') as f:
            for line in f:
                if line.startswith(f"{var_name}="):
                    return line.strip().split('=', 1)[1]
    except Exception as e:
        print(f"Error reading .env file: {str(e)}")
    return None

pinecone_api_key = get_env_var("PINECONE_API_TOKEN")
openai_api_key = get_env_var("OPENAI_API_KEY")

# Set up OpenAI client
print(f"OpenAI API key: {openai_api_key[:5]}...{openai_api_key[-5:]}")
# Set a valid OpenAI API key manually (you need to replace this with a valid key)
openai_api_key = "sk-[ENTER_VALID_OPENAI_API_KEY_HERE]"
openai_client = openai.OpenAI(api_key=openai_api_key)

# Set up Pinecone client
pc = pinecone.Pinecone(api_key=pinecone_api_key)

# Constants
INDEX_NAME = "fxml3-wave"
NAMESPACE = "elliott-wave-theory"
EMBEDDING_MODEL = "text-embedding-3-small"

# Elliott Wave document
elliott_wave_document = """
Elliott Wave Theory: Core Principles and Patterns

Elliott Wave Theory is a form of technical analysis used to analyze financial market cycles
and forecast market trends by identifying extremes in investor psychology, highs and lows 
in prices, and other collective factors. Ralph Nelson Elliott (1871–1948) discovered that 
price movements in financial markets follow a pattern of five waves in the direction of the 
main trend followed by three corrective waves (a 5-3 move).

The Basic Pattern

The Elliott Wave Theory identifies a 5-3 wave pattern. The five-wave pattern (known as an 
impulse wave) moves in the direction of the trend, while the three-wave pattern (known as 
a corrective wave) moves against the trend.

Five-Wave Impulse Pattern

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

Three-Wave Corrective Pattern

After the five-wave impulse pattern completes, a three-wave corrective pattern typically follows:

1. Wave A: Initial corrective move against the trend of the 5-wave sequence.

2. Wave B: Countertrend move, retracing a portion of Wave A. Often traps traders who incorrectly 
   believe the original trend has resumed.

3. Wave C: Final corrective wave that generally moves beyond the end of Wave A and completes 
   the correction.

Wave Degrees

Elliott identified nine degrees of waves, from the smallest Grand Supercycle:

1. Grand Supercycle (multi-century)
2. Supercycle (40-70 years)
3. Cycle (1-several years)
4. Primary (months to years)
5. Intermediate (weeks to months)
6. Minor (weeks)
7. Minute (days)
8. Minuette (hours)
9. Subminuette (minutes)

Each wave at any degree consists of waves of a smaller degree, creating a fractal pattern.

Fibonacci Relationships

Elliott Wave Theory is closely associated with Fibonacci numbers and ratios. Key Fibonacci 
relationships observed in waves include:

- Wave 2 often retraces 50% or 61.8% of Wave 1
- Wave 3 is typically 1.618 or 2.618 times the length of Wave 1
- Wave 4 often retraces 38.2% of Waves 1-3
- Wave 5 is often 0.618 or 1.618 times the length of Waves 1-3

Rules of Elliott Wave Theory

There are three unbreakable rules in Elliott Wave Theory:

1. Wave 2 never retraces more than 100% of Wave 1
2. Wave 3 is never the shortest of the three impulse waves (1, 3, 5)
3. Wave 4 never overlaps with the price territory of Wave 1

Guidelines (Not Rules)

In addition to the unbreakable rules, there are guidelines that are often observed:

- Wave 3 is typically the longest and strongest
- Wave 5 often displays divergence with technical indicators
- Corrective waves often retrace to Fibonacci levels of the preceding impulse wave
- Waves 2 and 4 often alternate in form (if Wave 2 is sharp, Wave 4 is typically flat)
- Wave 5 of an impulsive sequence often contains a 5-wave sequence of a lower degree

Complex Corrections

Corrective patterns can become quite complex. The basic corrective patterns include:

- Zigzag (5-3-5 structure)
- Flat (3-3-5 structure)
- Triangle (3-3-3-3-3 structure)

These can combine to form compound corrections such as:

- Double zigzag
- Double three
- Triple three

Trading Applications

Elliott Wave Theory is used by traders to:

1. Identify the overall market direction (trend analysis)
2. Determine potential reversal points
3. Set price targets for waves
4. Identify stop-loss levels based on wave rules
5. Gauge market sentiment and psychology

Practitioners believe that by identifying the current wave position, traders can anticipate 
future price movements and make more informed trading decisions.
"""

# Get OpenAI embedding for a text
def get_embedding(text, model=EMBEDDING_MODEL):
    """Get embedding from OpenAI API."""
    try:
        response = openai_client.embeddings.create(
            model=model,
            input=text
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"Error getting embedding: {str(e)}")
        return None

# Delete all vectors in a namespace
def delete_all_vectors():
    """Delete all vectors in the Pinecone index."""
    try:
        # Get the index
        index = pc.Index(INDEX_NAME)
        
        # Delete all vectors in the namespace
        print(f"Deleting all vectors in namespace '{NAMESPACE}'...")
        index.delete(delete_all=True, namespace=NAMESPACE)
        
        # Verify deletion
        verify = False
        attempt = 0
        max_attempts = 5
        
        while not verify and attempt < max_attempts:
            attempt += 1
            # Query with a dummy vector to see if anything remains
            dummy_vector = [0.0] * 1536
            results = index.query(
                vector=dummy_vector,
                top_k=10,
                include_metadata=True,
                namespace=NAMESPACE
            )
            
            if not results.get("matches", []):
                verify = True
                print("Successfully deleted all vectors!")
                break
            else:
                print(f"Deletion verification attempt {attempt}: {len(results.get('matches', []))} vectors still exist")
                time.sleep(2)
        
        if not verify:
            print("Warning: Could not verify deletion of all vectors.")
        
        return verify
        
    except Exception as e:
        print(f"Error deleting vectors: {str(e)}")
        return False

# Add document to Pinecone
def add_document(text, metadata=None):
    """Add a document to the Pinecone index."""
    try:
        # Get the index
        index = pc.Index(INDEX_NAME)
        
        # Get embedding for the document
        embedding = get_embedding(text)
        
        if not embedding:
            print("Failed to get embedding for document.")
            return None
        
        # Prepare metadata
        if metadata is None:
            metadata = {}
        
        # Include the text in metadata
        metadata["text"] = text
        
        # Upsert the vector
        vector_id = f"ew-doc-{int(time.time())}"
        
        upsert_response = index.upsert(
            vectors=[
                {
                    "id": vector_id,
                    "values": embedding,
                    "metadata": metadata
                }
            ],
            namespace=NAMESPACE
        )
        
        print(f"Document added with ID {vector_id}: {upsert_response}")
        return vector_id
        
    except Exception as e:
        print(f"Error adding document: {str(e)}")
        return None

# Search for documents similar to a query
def search_documents(query_text, top_k=3):
    """Search for documents similar to the query."""
    try:
        # Get the index
        index = pc.Index(INDEX_NAME)
        
        # Get embedding for the query
        query_embedding = get_embedding(query_text)
        
        if not query_embedding:
            print("Failed to get embedding for query.")
            return []
        
        # Query the index
        results = index.query(
            vector=query_embedding,
            top_k=top_k,
            include_metadata=True,
            namespace=NAMESPACE
        )
        
        # Format results
        formatted_results = []
        for match in results.get("matches", []):
            formatted_results.append({
                "id": match.get("id", ""),
                "score": match.get("score", 0),
                "text": match.get("metadata", {}).get("text", ""),
                "metadata": {k: v for k, v in match.get("metadata", {}).items() if k != "text"}
            })
            
        return formatted_results
        
    except Exception as e:
        print(f"Error searching documents: {str(e)}")
        return []

# Main function
def main():
    """Run the direct test."""
    print("Testing direct Pinecone + OpenAI RAG implementation")
    print(f"Using Pinecone API key: {pinecone_api_key[:5]}...{pinecone_api_key[-5:]}")
    print(f"Using OpenAI API key: {openai_api_key[:5]}...{openai_api_key[-5:]}")
    
    # Check if index exists
    try:
        indexes = pc.list_indexes()
        index_names = [idx.name for idx in indexes]
        
        if INDEX_NAME not in index_names:
            print(f"Creating index '{INDEX_NAME}'...")
            pc.create_index(
                name=INDEX_NAME,
                dimension=1536,  # text-embedding-3-small dimension
                metric="cosine",
                spec=pinecone.ServerlessSpec(
                    cloud="aws",
                    region="us-east-1"
                )
            )
            
            # Wait for index to be ready
            while not pc.describe_index(INDEX_NAME).status.ready:
                time.sleep(2)
                
            print(f"Index '{INDEX_NAME}' created!")
        else:
            print(f"Using existing index '{INDEX_NAME}'")
            
        # Delete all vectors
        delete_all_vectors()
        
        # Add the Elliott Wave document
        print("\nAdding Elliott Wave document...")
        doc_id = add_document(
            elliott_wave_document,
            metadata={
                "source": "elliott_wave_theory_guide",
                "author": "System",
                "category": "Trading Theory",
                "topic": "Elliott Wave",
                "difficulty": "intermediate"
            }
        )
        
        if doc_id:
            print(f"Successfully added document with ID: {doc_id}")
            
            # Wait for indexing
            time.sleep(3)
            
            # Test queries
            test_queries = [
                "What are the five waves in Elliott Wave Theory?",
                "Explain the Fibonacci relationships in Elliott Wave",
                "What are the unbreakable rules of Elliott Wave?",
                "How can Elliott Wave be used for trading?",
                "What are complex corrections in Elliott Wave Theory?"
            ]
            
            print("\nTesting queries...")
            for query in test_queries:
                print(f"\nQuery: '{query}'")
                results = search_documents(query, top_k=1)
                
                if results:
                    result = results[0]
                    print(f"Found document with score: {result['score']}")
                    print(f"Document ID: {result['id']}")
                    
                    # Extract relevant snippet
                    text = result['text']
                    query_terms = query.lower().split()
                    
                    # Find position of first query term in text
                    positions = []
                    for term in query_terms:
                        if term in ["in", "the", "are", "what", "how", "can", "be", "to", "and", "of", "for"]:
                            continue
                        pos = text.lower().find(term)
                        if pos != -1:
                            positions.append(pos)
                    
                    # Get snippet around the first match
                    if positions:
                        start_pos = max(0, min(positions) - 100)
                        end_pos = min(len(text), start_pos + 400)
                        snippet = text[start_pos:end_pos]
                        print(f"Relevant snippet: '{snippet}...'")
                    else:
                        print(f"No specific match found. First 200 chars: '{text[:200]}...'")
                else:
                    print("No matching documents found")
                    
        else:
            print("Failed to add document, cannot proceed with testing")
            
    except Exception as e:
        print(f"Error during testing: {str(e)}")

if __name__ == "__main__":
    main()