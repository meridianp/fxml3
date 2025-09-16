# Knowledge Assets for FXML3

This directory contains the knowledge assets used by the FXML3 system for the Elliott Wave RAG (Retrieval Augmented Generation) system.

## Directory Structure

- `raw/`: Raw documents before processing (PDFs, text files, etc.)
- `processed/`: Processed text chunks organized by category

## Categories

The processed documents are organized into the following categories:

- `basics`: Basic Elliott Wave principles and concepts
- `impulse`: Impulse wave patterns and characteristics
- `corrective`: Corrective wave patterns and characteristics
- `fibonacci`: Fibonacci relationships and measurements
- `trading`: Trading strategies based on Elliott Wave theory
- `psychology`: Market psychology and sentiment analysis
- `examples`: Example patterns from historical price data
- `validation`: Wave pattern validation techniques
- `alternation`: Principle of alternation and its applications
- `multi_timeframe`: Multi-timeframe analysis techniques

## Processing Workflow

1. Raw PDFs and documents are placed in the `raw/` directory
2. Documents are processed using the `document_processor.py` into text chunks
3. Chunks are categorized and saved to category subdirectories in `processed/`
4. The processed chunks are indexed into the Pinecone vector database
5. The Elliott Wave Knowledge Base uses the vector store for RAG

## Building the Knowledge Base

To process the raw documents and build the knowledge base:

1. Place your Elliott Wave PDF documents in the `raw/` directory
2. Run the processing script from the project root:
   ```
   python build_knowledge_base.py
   ```
3. Once the documents are processed, load them into Pinecone:
   ```
   python load_knowledge_to_pinecone.py
   ```

## Using the Knowledge Base

The knowledge base can be used by the multi-agent system to:

1. Validate detected wave patterns
2. Provide explanations of Elliott Wave principles
3. Guide trading decisions based on pattern recognition
4. Offer context-aware information about market psychology
5. Enhance the system's ability to generate accurate wave counts

## API Usage

```python
from fxml3.llm_integration.knowledge_base import ElliotWaveKnowledgeBase

# Create knowledge base instance
kb = ElliotWaveKnowledgeBase(namespace="elliott-wave-theory")

# Query the knowledge base
results = kb.query_knowledge_base(
    query="How do I identify a wave 3?",
    category="impulse",  # Optional: filter by category
    k=3  # Return top 3 results
)

# Process results
for result in results:
    print(f"Score: {result['score']}")
    print(f"Content: {result['text']}")
```
