# Elliott Wave Knowledge Assets

This directory contains knowledge assets for Elliott Wave theory, used by the RAG system for pattern validation and trading recommendations.

## Directory Structure

- `raw/`: Raw source documents (PDFs, text files)
- `processed/`: Processed text chunks organized by category
  - `basics/`: Basic Elliott Wave principles and concepts
  - `impulse/`: Impulse wave patterns and characteristics
  - `corrective/`: Corrective wave patterns and characteristics
  - `fibonacci/`: Fibonacci relationships and measurements
  - `trading/`: Trading strategies based on Elliott Wave theory
  - `psychology/`: Market psychology and sentiment analysis
  - `examples/`: Example patterns from historical price data
  - `validation/`: Wave pattern validation techniques
  - `alternation/`: Principle of alternation and its applications
  - `multi_timeframe/`: Multi-timeframe analysis techniques

## Processing Documents

To process a new document and add it to the knowledge base:

1. Place the document in the `raw/` directory
2. Run the document processor script:

```bash
python -m scripts.test_rag_system --process-assets --assets-dir fxml4/llm_integration/knowledge_assets
```

This will:
1. Process the document into chunks
2. Store the chunks in the appropriate category directories
3. Add metadata for each chunk
4. Add the chunks to the vector database

## Adding to Knowledge Base

After processing documents, you can load them into the knowledge base using:

```python
from fxml4.llm_integration.knowledge_base import ElliottWaveKnowledgeBase

kb = ElliottWaveKnowledgeBase()
result = kb.load_from_directory("fxml4/llm_integration/knowledge_assets/processed")
```

## Knowledge Sources

The knowledge base is built from the following sources:

1. Elliott Wave Principle by Frost & Prechter
2. Mastering Elliott Wave Principle by Constance Brown
3. Research papers on Elliott Wave theory
4. Examples from historical price data

## Usage

This knowledge is used by the RAG system to:

1. Validate Elliott Wave patterns detected in price data
2. Provide explanations for pattern validity
3. Generate trading recommendations based on wave patterns
4. Offer contextual information about wave characteristics