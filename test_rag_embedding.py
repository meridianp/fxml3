#!/usr/bin/env python3
"""Test script to add an Elliott Wave document to Pinecone and test retrieval."""

import os
import sys
import time
from dotenv import load_dotenv

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import our vector store
from fxml3.llm_integration.vector_store import PineconeVectorStore


def main():
    """Add Elliott Wave document to Pinecone and test retrieval."""
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
    
    # Create Elliott Wave document
    elliott_wave_document = """
    # Elliott Wave Theory: Core Principles and Patterns
    
    Elliott Wave Theory is a form of technical analysis used to analyze financial market cycles
    and forecast market trends by identifying extremes in investor psychology, highs and lows 
    in prices, and other collective factors. Ralph Nelson Elliott (1871–1948) discovered that 
    price movements in financial markets follow a pattern of five waves in the direction of the 
    main trend followed by three corrective waves (a 5-3 move).
    
    ## The Basic Pattern
    
    The Elliott Wave Theory identifies a 5-3 wave pattern. The five-wave pattern (known as an 
    impulse wave) moves in the direction of the trend, while the three-wave pattern (known as 
    a corrective wave) moves against the trend.
    
    ### Five-Wave Impulse Pattern
    
    1. **Wave 1**: Initial move upward, typically caused by a relatively small number of people who 
       recognize that conditions are changing and prices are too low.
    
    2. **Wave 2**: Partial retracement of Wave 1, as profit-taking occurs. This wave typically 
       retraces less than 100% of Wave 1, often finding support around the 50% or 61.8% Fibonacci level.
    
    3. **Wave 3**: Usually the longest and strongest wave. This is where most money is made.
       Wave 3 is never the shortest impulse wave and it always travels beyond the end of Wave 1.
    
    4. **Wave 4**: Corrective wave following Wave 3. It typically retraces less than Wave 2 and 
       often forms a complex pattern. Wave 4 does not enter the territory of Wave 1.
    
    5. **Wave 5**: Final leg of the trend, often showing weakening momentum and divergence with indicators.
       This wave is driven mainly by market psychology rather than fundamentals.
    
    ### Three-Wave Corrective Pattern
    
    After the five-wave impulse pattern completes, a three-wave corrective pattern typically follows:
    
    1. **Wave A**: Initial corrective move against the trend of the 5-wave sequence.
    
    2. **Wave B**: Countertrend move, retracing a portion of Wave A. Often traps traders who incorrectly 
       believe the original trend has resumed.
    
    3. **Wave C**: Final corrective wave that generally moves beyond the end of Wave A and completes 
       the correction.
    
    ## Wave Degrees
    
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
    
    ## Fibonacci Relationships
    
    Elliott Wave Theory is closely associated with Fibonacci numbers and ratios. Key Fibonacci 
    relationships observed in waves include:
    
    - Wave 2 often retraces 50% or 61.8% of Wave 1
    - Wave 3 is typically 1.618 or 2.618 times the length of Wave 1
    - Wave 4 often retraces 38.2% of Waves 1-3
    - Wave 5 is often 0.618 or 1.618 times the length of Waves 1-3
    
    ## Rules of Elliott Wave Theory
    
    There are three unbreakable rules in Elliott Wave Theory:
    
    1. Wave 2 never retraces more than 100% of Wave 1
    2. Wave 3 is never the shortest of the three impulse waves (1, 3, 5)
    3. Wave 4 never overlaps with the price territory of Wave 1
    
    ## Guidelines (Not Rules)
    
    In addition to the unbreakable rules, there are guidelines that are often observed:
    
    - Wave 3 is typically the longest and strongest
    - Wave 5 often displays divergence with technical indicators
    - Corrective waves often retrace to Fibonacci levels of the preceding impulse wave
    - Waves 2 and 4 often alternate in form (if Wave 2 is sharp, Wave 4 is typically flat)
    - Wave 5 of an impulsive sequence often contains a 5-wave sequence of a lower degree
    
    ## Complex Corrections
    
    Corrective patterns can become quite complex. The basic corrective patterns include:
    
    - Zigzag (5-3-5 structure)
    - Flat (3-3-5 structure)
    - Triangle (3-3-3-3-3 structure)
    
    These can combine to form compound corrections such as:
    
    - Double zigzag
    - Double three
    - Triple three
    
    ## Trading Applications
    
    Elliott Wave Theory is used by traders to:
    
    1. Identify the overall market direction (trend analysis)
    2. Determine potential reversal points
    3. Set price targets for waves
    4. Identify stop-loss levels based on wave rules
    5. Gauge market sentiment and psychology
    
    Practitioners believe that by identifying the current wave position, traders can anticipate 
    future price movements and make more informed trading decisions.
    """
    
    # Initialize the vector store with explicit API key
    try:
        print("Initializing Pinecone vector store...")
        vector_store = PineconeVectorStore(
            index_name="fxml3-wave",
            namespace="elliott-wave-theory",
            embedding_model="text-embedding-3-small",
            api_key=api_key
        )
        
        # Add the Elliott Wave document with metadata
        print("\nAdding Elliott Wave document to Pinecone...")
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
        
        # Wait a moment for Pinecone to process
        time.sleep(2)
        
        # Test retrieval with relevant queries
        print("\nTesting document retrieval with various queries:")
        
        queries = [
            "What are the five waves in Elliott Wave Theory?",
            "Explain the Fibonacci relationships in Elliott Wave",
            "What are the unbreakable rules of Elliott Wave?",
            "How can Elliott Wave be used for trading?",
            "What are complex corrections in Elliott Wave Theory?"
        ]
        
        for query in queries:
            print(f"\nQuery: '{query}'")
            results = vector_store.similarity_search(query, k=1)
            
            if results:
                print(f"Found matching document with score: {results[0]['score']}")
                print(f"Document ID: {results[0]['id']}")
                # Show a snippet of the result
                text = results[0]['text']
                start_pos = max(0, text.lower().find(query.lower().split()[0]) - 100)
                snippet = text[start_pos:start_pos + 500]
                print(f"Relevant snippet: '{snippet}...'")
            else:
                print("No results found")
        
        print("\nRAG testing complete!")
        
    except Exception as e:
        print(f"Error: {str(e)}")


if __name__ == "__main__":
    main()