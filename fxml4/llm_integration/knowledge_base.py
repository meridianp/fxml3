"""Knowledge base for Elliott Wave theory and technical analysis.

This module provides a structured knowledge base for Elliott Wave theory that
can be used for retrieval-augmented generation in market analysis.
"""

import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from fxml4.llm_integration.rag import RAG

logger = logging.getLogger(__name__)


class ElliottWaveKnowledgeBase:
    """Knowledge base for Elliott Wave theory and technical analysis.

    This class manages a structured knowledge base of Elliott Wave
    concepts, patterns, and trading strategies that can be used for
    retrieval-augmented generation.
    """

    # Categories for organizing knowledge
    CATEGORIES = {
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

    def __init__(
        self,
        rag_instance: Optional[RAG] = None,
        namespace: str = "elliott-wave-theory",
        embedding_model: str = "text-embedding-3-small",
    ):
        """Initialize the knowledge base.

        Args:
            rag_instance: RAG system for knowledge retrieval
            namespace: Namespace within the vector store
            embedding_model: Model to use for embeddings
        """
        self.rag = rag_instance or RAG(
            {
                "namespace": namespace,
                "embedding_model": embedding_model,
            }
        )
        self.namespace = namespace
        self.embedding_model = embedding_model

    def seed_basic_knowledge(self) -> Dict[str, bool]:
        """Seed the knowledge base with basic Elliott Wave theory knowledge.

        Returns:
            Dictionary with status information
        """
        # Basic Elliott Wave knowledge chunks
        basics = [
            {
                "text": """
                Elliott Wave Theory Basics:

                The Elliott Wave Theory is a form of technical analysis that traders use to analyze financial market cycles
                and forecast market trends by identifying extremes in investor psychology, high and low prices, and other
                collective activities. Ralph Nelson Elliott developed this theory in the 1930s after observing that financial
                markets tend to move in repetitive patterns.

                The theory identifies impulse waves that establish a pattern and corrective waves that oppose the larger trend.
                Each set of waves is nested within a larger set of waves that adhere to the same impulse/corrective pattern.
                """,
                "metadata": {"category": "basics", "source": "theory_foundation"},
            },
            {
                "text": """
                Five Wave Pattern (Impulse):

                In Elliott Wave theory, the basic pattern consists of 5 waves moving in the direction of the main trend
                (impulse waves numbered 1-2-3-4-5), followed by 3 waves moving against the trend (corrective waves labeled A-B-C).

                Characteristics of impulse waves:
                - Wave 1: Initial move up, often overlooked by most participants
                - Wave 2: Partial retracement of wave 1, cannot go below the start of wave 1
                - Wave 3: Usually the longest and strongest wave, confirming the trend
                - Wave 4: Another retracement, cannot overlap with wave 1
                - Wave 5: Final move up, often displays weaker momentum than wave 3
                """,
                "metadata": {"category": "impulse", "source": "wave_patterns"},
            },
            {
                "text": """
                Three Wave Pattern (Corrective):

                Corrective waves move against the trend of the next larger degree and are labeled with letters A-B-C.
                There are several corrective patterns:

                1. Zigzag (5-3-5): Sharp, clear correction with wave B typically retracing less than 75% of wave A
                2. Flat (3-3-5): Sideways correction where wave B retraces 100% or more of wave A
                3. Triangle (3-3-3-3-3): Five waves in a sideways contracting or expanding pattern
                4. Double and Triple Three: Combination of simpler corrective patterns

                Corrections are typically more complex and take longer to unfold than impulse waves.
                """,
                "metadata": {"category": "corrective", "source": "wave_patterns"},
            },
            {
                "text": """
                Fibonacci Relationships in Elliott Wave:

                Fibonacci ratios are crucial for validating Elliott Wave patterns and projecting price targets:

                - The most common retracement levels are 38.2%, 50%, and 61.8%
                - Wave 3 is often 1.618 or 2.618 times the length of wave 1
                - Wave 5 is often 0.618 or 1.0 times the length of wave 1
                - Wave 4 typically retraces 38.2% or 50% of wave 3
                - In an ABC correction, wave C is often 1.618 times the length of wave A

                These relationships help confirm pattern validity and predict future price movements.
                """,
                "metadata": {
                    "category": "fibonacci",
                    "source": "measurement_techniques",
                },
            },
            {
                "text": """
                Wave Counting Rules:

                1. Wave 2 cannot retrace more than 100% of wave 1
                2. Wave 3 cannot be the shortest of waves 1, 3, and 5
                3. Wave 4 cannot overlap with the price territory of wave 1
                4. Wave 3 must travel beyond the end of wave 1
                5. Wave B cannot travel beyond the start of wave A

                These rules help validate or invalidate potential Elliott Wave patterns.
                """,
                "metadata": {"category": "validation", "source": "wave_counting"},
            },
            {
                "text": """
                Principle of Alternation:

                The principle of alternation states that corrective waves tend to alternate in form. If wave 2 is a sharp
                correction, wave 4 is likely to be a flat or complex correction, and vice versa.

                Alternation may also apply to:
                - Depth of retracements (one shallow, one deep)
                - Time duration (one short, one long)
                - Complexity (one simple, one complex)

                This principle helps anticipate the form of future waves based on prior waves.
                """,
                "metadata": {"category": "alternation", "source": "wave_patterns"},
            },
            {
                "text": """
                Trading Strategies with Elliott Wave:

                1. Wave 3 Entry Strategy: Enter trades in the direction of the main trend at the end of wave 2 correction
                2. Wave 5 Completion Strategy: Take profits or prepare for reversal at the completion of wave 5
                3. Breakout Strategy: Enter during wave 3 when price breaks above the high of wave 1
                4. ABC Correction Strategy: Enter in the direction of the main trend after an ABC correction completes
                5. Triangle Completion Strategy: Enter in the direction of the prior trend when a triangle pattern completes

                These strategies combine Elliott Wave pattern recognition with risk management for optimal trade execution.
                """,
                "metadata": {"category": "trading", "source": "trading_strategies"},
            },
            {
                "text": """
                Wave Fractal Nature:

                Elliott Wave patterns exhibit fractal properties, meaning they appear at all scales (timeframes). Each wave
                of larger degree contains multiple waves of smaller degrees.

                Wave Degrees from largest to smallest:
                1. Grand Supercycle
                2. Supercycle
                3. Cycle
                4. Primary
                5. Intermediate
                6. Minor
                7. Minute
                8. Minuette
                9. Subminuette

                Understanding the current position within waves of different degrees helps traders anticipate larger trends.
                """,
                "metadata": {
                    "category": "multi_timeframe",
                    "source": "fractal_structure",
                },
            },
            {
                "text": """
                Market Psychology and Wave Patterns:

                Elliott Wave Theory correlates wave patterns with investor psychology:

                - Wave 1: Initial optimism, typically after a bear market
                - Wave 2: Renewed pessimism, doubt about the new trend
                - Wave 3: Widespread recognition of the trend, increased participation
                - Wave 4: Complacency and mild profit-taking
                - Wave 5: Euphoria and maximum optimism
                - Wave A: Initial panic or profit-taking
                - Wave B: Relief rally, belief the correction is over
                - Wave C: Capitulation and despair

                This psychological framework explains why patterns repeat across various markets and timeframes.
                """,
                "metadata": {"category": "psychology", "source": "investor_sentiment"},
            },
        ]

        success_count = 0
        results = {"success": False, "documents_added": 0, "message": ""}

        try:
            for item in basics:
                text = item["text"]
                metadata = item["metadata"]

                # Add knowledge to RAG system
                response = self.rag.add_document(text, metadata)

                if response.get("success", False):
                    success_count += 1

            # Set results
            if success_count == len(basics):
                results = {
                    "success": True,
                    "documents_added": success_count,
                    "message": "Successfully seeded basic knowledge",
                }
            else:
                results = {
                    "success": False,
                    "documents_added": success_count,
                    "message": f"Added {success_count} out of {len(basics)} documents",
                }
        except Exception as e:
            results = {
                "success": False,
                "documents_added": success_count,
                "message": f"Error seeding knowledge: {str(e)}",
            }

        return results

    def add_category_knowledge(
        self,
        category: str,
        texts: List[str],
        source: str,
        additional_metadata: Optional[Dict] = None,
    ) -> Dict[str, any]:
        """Add knowledge to a specific category.

        Args:
            category: The category to add knowledge to
            texts: List of text documents to add
            source: Source of the knowledge
            additional_metadata: Optional additional metadata

        Returns:
            Dictionary with status information

        Raises:
            ValueError: If the category is not recognized
        """
        if category not in self.CATEGORIES:
            raise ValueError(
                f"Unrecognized category: {category}. Valid categories: {list(self.CATEGORIES.keys())}"
            )

        success_count = 0
        results = {"success": False, "documents_added": 0, "message": ""}

        try:
            for text in texts:
                # Prepare metadata
                metadata = {"category": category, "source": source}
                if additional_metadata:
                    metadata.update(additional_metadata)

                # Add to RAG system
                response = self.rag.add_document(text, metadata)

                if response.get("success", False):
                    success_count += 1

            # Set results
            if success_count == len(texts):
                results = {
                    "success": True,
                    "documents_added": success_count,
                    "message": f"Successfully added {success_count} documents to category '{category}'",
                }
            else:
                results = {
                    "success": False,
                    "documents_added": success_count,
                    "message": f"Added {success_count} out of {len(texts)} documents to category '{category}'",
                }
        except Exception as e:
            results = {
                "success": False,
                "documents_added": success_count,
                "message": f"Error adding knowledge: {str(e)}",
            }

        return results

    def load_from_directory(self, directory_path: str) -> Dict[str, any]:
        """Load knowledge from a directory of text files.

        The directory should have subdirectories named after the categories,
        each containing text files with knowledge documents.

        Args:
            directory_path: Path to the directory

        Returns:
            Dictionary with status information
        """
        result = {
            "success": False,
            "documents_added": 0,
            "categories": {},
            "message": "",
        }

        # Create Path object
        dir_path = Path(directory_path)

        if not dir_path.exists() or not dir_path.is_dir():
            result["message"] = f"Directory not found: {directory_path}"
            return result

        total_documents = 0

        # Look for category subdirectories
        for category in self.CATEGORIES:
            category_path = dir_path / category

            # Skip if not a directory
            if not category_path.is_dir():
                continue

            # Process files in this category
            category_docs = 0
            for file_path in category_path.glob("*.txt"):
                # Extract source from filename
                source = file_path.stem

                # Read file
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        text = f.read()

                    # Add to knowledge base
                    response = self.add_category_knowledge(category, [text], source)

                    if response.get("success", False):
                        category_docs += 1
                        total_documents += 1
                except Exception as e:
                    logger.error(f"Error processing {file_path}: {str(e)}")

            # Store counts for this category
            if category_docs > 0:
                result["categories"][category] = category_docs

        # Update result
        result["documents_added"] = total_documents
        if total_documents > 0:
            result["success"] = True
            result["message"] = (
                f"Successfully loaded {total_documents} documents from {len(result['categories'])} categories"
            )
        else:
            result["message"] = "No documents were found or loaded"

        return result

    def query_knowledge_base(
        self,
        query: str,
        category: Optional[str] = None,
        k: int = 5,
    ) -> Dict[str, any]:
        """Query the knowledge base for relevant information.

        Args:
            query: The query text
            category: Optional category to filter by
            k: Number of results to return

        Returns:
            Dictionary with query results
        """
        # Prepare filter if category is specified
        filter_dict = None
        if category:
            if category not in self.CATEGORIES:
                raise ValueError(
                    f"Unrecognized category: {category}. Valid categories: {list(self.CATEGORIES.keys())}"
                )
            filter_dict = {"category": category}

        # Perform search using RAG system
        return self.rag.query(query, filter=filter_dict, top_k=k)

    def get_all_categories(self) -> Dict[str, str]:
        """Get all available knowledge categories and their descriptions.

        Returns:
            Dictionary mapping category IDs to descriptions
        """
        return self.CATEGORIES.copy()

    def validate_wave_pattern(
        self,
        pattern_description: str,
        price_data: Optional[str] = None,
        use_categories: List[str] = None,
    ) -> Dict[str, any]:
        """Validate an Elliott Wave pattern using the knowledge base.

        Args:
            pattern_description: Description of the pattern to validate
            price_data: Optional price data context
            use_categories: Optional list of categories to search in

        Returns:
            Dictionary with validation results
        """
        # Default categories to search
        if use_categories is None:
            use_categories = ["validation", "impulse", "corrective"]

        # Construct validation question
        question = f"Is this a valid Elliott Wave pattern: {pattern_description}"

        # Add price data context if provided
        additional_context = f"Price data:\n{price_data}" if price_data else None

        # Iterate through categories and find relevant knowledge
        results = {}
        for category in use_categories:
            try:
                # Query the RAG system with category filter
                response = self.rag.query(
                    question,
                    filter={"category": category},
                    additional_context=additional_context,
                )

                # Store result if successful
                if response.get("success", False):
                    results[category] = response
            except Exception as e:
                logger.error(f"Error querying category {category}: {str(e)}")

        # If no results were found in any category
        if not results:
            return self.rag.validate_wave_pattern(pattern_description, price_data)

        # Combine results and analyze validity
        combined_answer = ""
        is_valid = False
        confidence = 0.0
        sources = []

        for category, result in results.items():
            answer = result.get("answer", "")
            combined_answer += f"\n--- {category.upper()} ---\n{answer}\n"

            # Extract validity information
            if "valid" in answer.lower() or "correct" in answer.lower():
                is_valid = True
                confidence += 0.33  # Each category confirmation adds confidence

            # Collect sources
            sources.extend(result.get("sources", []))

        # Cap confidence at 1.0
        confidence = min(1.0, confidence)

        return {
            "success": True,
            "is_valid": is_valid,
            "confidence": confidence,
            "explanation": combined_answer.strip(),
            "sources": sources[:5],  # Limit to top 5 sources
        }
