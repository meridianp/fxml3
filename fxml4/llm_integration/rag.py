"""Retrieval-Augmented Generation (RAG) for market analysis.

This module provides RAG capabilities for enhancing market analysis with
domain-specific knowledge about Elliott Wave theory and forex trading.
"""

import json
import logging
import os
import tempfile
from typing import Any, Dict, Optional

from fxml4.config import get_config
from fxml4.llm_integration.llm_client import LLMClient

logger = logging.getLogger(__name__)

try:
    import pinecone
    from langchain.chains import RetrievalQA
    from langchain.chat_models import ChatOpenAI
    from langchain.document_loaders import PyPDFLoader, TextLoader
    from langchain.embeddings import OpenAIEmbeddings
    from langchain.prompts import ChatPromptTemplate
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    from langchain.vectorstores import FAISS, Pinecone

    LANGCHAIN_AVAILABLE = True
except ImportError:
    logger.warning("LangChain not available. RAG functionality will be limited.")
    LANGCHAIN_AVAILABLE = False


def is_rag_available() -> bool:
    """Check if full RAG functionality is available.

    Returns:
        bool: True if all required dependencies are available and RAG can function fully.
    """
    return LANGCHAIN_AVAILABLE


class RAG:
    """Retrieval-Augmented Generation for market analysis."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the RAG system.

        Args:
            config: Configuration dictionary.
        """
        self.config = config or {}

        # Check if RAG is enabled
        self.enabled = self.config.get(
            "enabled", get_config().get("llm_integration.enabled", True)
        )

        if not self.enabled or not LANGCHAIN_AVAILABLE:
            logger.info("RAG system is disabled or langchain is not available")
            self.initialized = False
            return

        # Get configuration parameters
        self.vector_store_type = self.config.get(
            "vector_store",
            get_config().get("llm_integration.vector_store.provider", "pinecone"),
        )
        self.similarity_threshold = self.config.get(
            "similarity_threshold",
            get_config().get("llm_integration.similarity_threshold", 0.75),
        )
        self.top_k = self.config.get(
            "top_k", get_config().get("llm_integration.top_k", 5)
        )
        self.namespace = self.config.get(
            "namespace",
            get_config().get("llm_integration.namespace", "elliott-wave-theory"),
        )

        # Initialize LLM client
        self.llm_client = LLMClient(
            provider=self.config.get(
                "provider", get_config().get("llm_integration.provider", "openai")
            ),
            model=self.config.get(
                "model", get_config().get("llm_integration.openai.model", "gpt-4o")
            ),
        )

        # Initialize embedding model
        self.embedding_model = self._initialize_embedding_model()

        # Initialize vector store
        self.vector_store = self._initialize_vector_store()

        # Initialize LLM
        self.llm = self._initialize_llm()

        self.initialized = (
            self.embedding_model is not None
            and self.vector_store is not None
            and self.llm is not None
        )

        if self.initialized:
            logger.info("RAG system initialized successfully")
        else:
            logger.warning("RAG system initialization failed")

    def _initialize_embedding_model(self) -> Any:
        """Initialize the embedding model.

        Returns:
            Embedding model instance or None if initialization failed.
        """
        try:
            # Get API key from config or environment
            api_key = self.config.get(
                "openai_api_key", os.environ.get("OPENAI_API_KEY")
            )

            if not api_key:
                logger.error("OpenAI API key not found in config or environment")
                return None

            embedding_model = self.config.get(
                "embedding_model",
                get_config().get(
                    "llm_integration.openai.embedding_model", "text-embedding-3-small"
                ),
            )

            return OpenAIEmbeddings(openai_api_key=api_key, model=embedding_model)
        except Exception as e:
            logger.exception("Error initializing embedding model: %s", e)
            return None

    def _initialize_vector_store(self) -> Any:
        """Initialize the vector store.

        Returns:
            Vector store instance or None if initialization failed.
        """
        if not self.embedding_model:
            logger.error("Cannot initialize vector store without embedding model")
            return None

        try:
            if self.vector_store_type.lower() == "pinecone":
                return self._initialize_pinecone()
            elif self.vector_store_type.lower() == "faiss":
                # Use in-memory FAISS for testing or when Pinecone is not available
                logger.warning("Using in-memory FAISS vector store (no persistence)")
                return FAISS(
                    embedding_function=self.embedding_model, texts=[], metadatas=[]
                )
            else:
                logger.error(
                    "Unsupported vector store type: %s", self.vector_store_type
                )
                return None
        except Exception as e:
            logger.exception("Error initializing vector store: %s", e)
            return None

    def _initialize_pinecone(self) -> Any:
        """Initialize Pinecone vector store.

        Returns:
            Pinecone vector store instance or None if initialization failed.
        """
        # Get API key and environment
        pinecone_api_key = self.config.get(
            "pinecone_api_key",
            os.environ.get(
                "PINECONE_API_KEY",
                get_config().get("llm_integration.vector_store.pinecone.api_key", None),
            ),
        )

        pinecone_environment = self.config.get(
            "pinecone_environment",
            os.environ.get(
                "PINECONE_ENVIRONMENT",
                get_config().get(
                    "llm_integration.vector_store.pinecone.environment", None
                ),
            ),
        )

        index_name = self.config.get(
            "index_name",
            get_config().get(
                "llm_integration.vector_store.pinecone.index_name", "fxml4-knowledge"
            ),
        )

        if not pinecone_api_key or not pinecone_environment:
            logger.error("Pinecone API key or environment not found")
            return None

        try:
            # Initialize Pinecone
            pinecone.init(api_key=pinecone_api_key, environment=pinecone_environment)

            # Check if index exists
            if index_name not in pinecone.list_indexes():
                # Index doesn't exist, create it
                logger.info(f"Creating Pinecone index: {index_name}")

                # Get dimensions from config or use default
                dimensions = self.config.get(
                    "dimensions", 1536
                )  # OpenAI embeddings are 1536 dimensions

                # Create the index
                pinecone.create_index(
                    name=index_name, dimension=dimensions, metric="cosine"
                )

                # Wait for the index to be ready
                import time

                while not index_name in pinecone.list_indexes():
                    logger.info(
                        f"Waiting for Pinecone index {index_name} to be ready..."
                    )
                    time.sleep(5)

            # Connect to the index
            return Pinecone.from_existing_index(
                index_name=index_name,
                embedding=self.embedding_model,
                text_key="text",
                namespace=self.namespace,
            )
        except Exception as e:
            logger.exception(f"Error initializing Pinecone: {e}")
            return None

    def _initialize_llm(self) -> Any:
        """Initialize the language model.

        Returns:
            Language model instance or None if initialization failed.
        """
        try:
            # Get API key from config or environment
            api_key = self.config.get(
                "openai_api_key", os.environ.get("OPENAI_API_KEY")
            )

            if not api_key:
                logger.error("OpenAI API key not found in config or environment")
                return None

            model_name = self.config.get(
                "model", get_config().get("llm_integration.openai.model", "gpt-4o")
            )

            temperature = self.config.get(
                "temperature",
                get_config().get("llm_integration.openai.temperature", 0.2),
            )

            return ChatOpenAI(
                openai_api_key=api_key, model=model_name, temperature=temperature
            )
        except Exception as e:
            logger.exception("Error initializing language model: %s", e)
            return None

    def query(
        self,
        question: str,
        additional_context: Optional[str] = None,
        filter: Optional[Dict] = None,
        top_k: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Query the RAG system with a question.

        Args:
            question: Question to ask.
            additional_context: Additional context for the question.
            filter: Optional filter for metadata in document retrieval
            top_k: Number of documents to retrieve (overrides default)

        Returns:
            Dictionary with query response and metadata.
        """
        if not self.initialized:
            return {
                "success": False,
                "error": "RAG system not initialized",
                "answer": None,
                "sources": [],
            }

        try:
            # Set number of documents to retrieve
            k = top_k if top_k is not None else self.top_k

            # Create retriever with similarity search
            retriever = self.vector_store.as_retriever(
                search_type="similarity",
                search_kwargs={
                    "k": k,
                    "score_threshold": self.similarity_threshold,
                    "filter": filter,
                },
            )

            # Get relevant documents
            docs = retriever.get_relevant_documents(question)

            if not docs:
                return {
                    "success": True,
                    "answer": "No relevant information found in the knowledge base.",
                    "sources": [],
                }

            # Prepare context from retrieved documents
            context_texts = [doc.page_content for doc in docs]
            combined_context = "\n\n".join(context_texts)

            # Prepare prompt
            prompt_template = ChatPromptTemplate.from_template(
                """You are an expert in Elliott Wave analysis and forex trading.
                Answer the question based on the following context:

                Context:
                {context}

                Additional context:
                {additional_context}

                Question: {question}

                Provide a concise, accurate answer based on the information provided.
                Be specific and cite information from the context where possible.
                """
            )

            # Format prompt with context
            prompt = prompt_template.format(
                context=combined_context,
                additional_context=additional_context or "",
                question=question,
            )

            # Get answer from LLM
            response = self.llm.invoke(prompt)

            # Extract source metadata
            sources = []
            for doc in docs:
                if hasattr(doc, "metadata"):
                    sources.append(doc.metadata)
                else:
                    sources.append({"content": doc.page_content[:100] + "..."})

            return {
                "success": True,
                "answer": response.content,
                "sources": sources,
            }
        except Exception as e:
            logger.exception("Error querying RAG system: %s", e)
            return {
                "success": False,
                "error": str(e),
                "answer": None,
                "sources": [],
            }

    def add_document(
        self, text: str, metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Add a document to the vector store.

        Args:
            text: The text content to add
            metadata: Optional metadata for the document

        Returns:
            Dictionary with status information
        """
        if not self.initialized:
            return {"success": False, "error": "RAG system not initialized", "id": None}

        try:
            # Create document
            document_id = self.vector_store.add_texts(
                texts=[text],
                metadatas=[metadata or {}],
            )[0]

            return {
                "success": True,
                "id": document_id,
                "message": "Document added successfully",
            }
        except Exception as e:
            logger.exception("Error adding document: %s", e)
            return {"success": False, "error": str(e), "id": None}

    def add_documents_from_file(
        self,
        file_path: str,
        metadata: Optional[Dict[str, Any]] = None,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
    ) -> Dict[str, Any]:
        """Add documents from a file to the vector store.

        Args:
            file_path: Path to the file (PDF or text)
            metadata: Optional metadata for all documents from this file
            chunk_size: Size of text chunks to create
            chunk_overlap: Overlap between chunks

        Returns:
            Dictionary with status information
        """
        if not self.initialized:
            return {
                "success": False,
                "error": "RAG system not initialized",
                "documents_added": 0,
            }

        try:
            from fxml4.llm_integration.document_processor import process_document

            # Create temporary directory for processed chunks
            with tempfile.TemporaryDirectory() as temp_dir:
                # Process the document into chunks
                file_name = os.path.basename(file_path)
                base_name, _ = os.path.splitext(file_name)

                # Process the document
                chunk_files = process_document(
                    file_path,
                    temp_dir,
                    chunk_size=chunk_size,
                    overlap=chunk_overlap,
                    metadata=metadata,
                )

                # Read chunks and add to vector store
                documents_added = 0
                for chunk_file in chunk_files:
                    # Read chunk file
                    with open(chunk_file, "r", encoding="utf-8") as f:
                        text = f.read()

                    # Check for corresponding metadata file
                    metadata_file = chunk_file.replace(".txt", ".json")
                    if os.path.exists(metadata_file):
                        with open(metadata_file, "r", encoding="utf-8") as f:
                            chunk_metadata = json.load(f)
                    else:
                        chunk_metadata = metadata or {}

                    # Add chunk metadata
                    chunk_metadata["source_file"] = file_name
                    chunk_metadata["chunk_file"] = os.path.basename(chunk_file)

                    # Add to vector store
                    result = self.add_document(text, chunk_metadata)
                    if result.get("success", False):
                        documents_added += 1

                # Return result
                if documents_added > 0:
                    return {
                        "success": True,
                        "documents_added": documents_added,
                        "message": f"Added {documents_added} documents from {file_path}",
                    }
                else:
                    return {
                        "success": False,
                        "error": "No documents were added",
                        "documents_added": 0,
                    }

        except ImportError:
            return {
                "success": False,
                "error": "Document processing not available. Install PyPDF2 and langchain.",
                "documents_added": 0,
            }
        except Exception as e:
            logger.exception("Error adding documents from file: %s", e)
            return {"success": False, "error": str(e), "documents_added": 0}

    def validate_wave_pattern(
        self,
        pattern_description: str,
        price_data: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Validate an Elliott Wave pattern using the RAG system.

        Args:
            pattern_description: Description of the pattern to validate.
            price_data: String representation of price data.

        Returns:
            Dictionary with validation results.
        """
        if not self.initialized:
            return {
                "success": False,
                "error": "RAG system not initialized",
                "is_valid": False,
                "explanation": None,
                "sources": [],
            }

        # Construct validation question
        question = f"""Is this a valid Elliott Wave pattern: {pattern_description}

        Please analyze this pattern according to Elliott Wave theory rules and principles.
        Explain your reasoning for why it is valid or invalid. If invalid, explain what would make it valid.
        """

        # Add price data context if provided
        additional_context = f"Price data:\n{price_data}" if price_data else None

        # Apply filters to focus on validation-related documents
        filters = {"category": "validation"}

        # Query the RAG system
        result = self.query(question, additional_context, filters)

        if not result.get("success", False):
            return {
                "success": False,
                "error": result.get("error", "Unknown error"),
                "is_valid": False,
                "explanation": None,
                "sources": [],
            }

        # Parse answer to determine validity
        answer = result["answer"].lower()
        is_valid = False

        if "valid" in answer:
            # Check if it says it's valid or invalid
            invalid_indicators = ["not valid", "invalid", "isn't valid", "is not valid"]
            is_valid = not any(indicator in answer for indicator in invalid_indicators)

        return {
            "success": True,
            "is_valid": is_valid,
            "explanation": result["answer"],
            "sources": result["sources"],
        }

    def get_market_context(self, symbol: str, timeframe: str) -> Dict[str, Any]:
        """Get market context for a symbol and timeframe.

        Args:
            symbol: Trading symbol.
            timeframe: Timeframe.

        Returns:
            Dictionary with market context.
        """
        if not self.initialized:
            return {
                "success": False,
                "error": "RAG system not initialized",
                "context": None,
                "sources": [],
            }

        # Construct market context question
        question = f"""Provide Elliott Wave analysis context for {symbol} on the {timeframe} timeframe.

        Include information about:
        1. Common Elliott Wave patterns for this currency pair
        2. Important considerations for this timeframe
        3. Typical Fibonacci relationships to watch for
        4. Any special characteristics of this currency pair
        """

        # Query the RAG system
        result = self.query(question)

        if not result["success"]:
            return {
                "success": False,
                "error": result.get("error", "Unknown error"),
                "context": None,
                "sources": [],
            }

        return {
            "success": True,
            "context": result["answer"],
            "sources": result["sources"],
        }

    def get_wave_characteristics(self, wave_type: str) -> Dict[str, Any]:
        """Get characteristics of a specific Elliott Wave pattern.

        Args:
            wave_type: Type of Elliott Wave pattern (e.g., "impulse", "zigzag", "flat")

        Returns:
            Dictionary with wave characteristics
        """
        if not self.initialized:
            return {
                "success": False,
                "error": "RAG system not initialized",
                "characteristics": None,
            }

        # Construct query
        question = f"""Describe the key characteristics of {wave_type} Elliott Wave patterns.

        Include information about:
        1. Wave structure and components
        2. Common Fibonacci relationships
        3. Key validation rules
        4. Common trading strategies for this pattern
        5. Examples of when this pattern typically appears
        """

        # Query the RAG system
        result = self.query(question)

        if not result["success"]:
            return {
                "success": False,
                "error": result.get("error", "Unknown error"),
                "characteristics": None,
            }

        return {
            "success": True,
            "characteristics": result["answer"],
            "sources": result["sources"],
        }

    def get_status(self) -> Dict[str, Any]:
        """Get status information about the RAG system.

        Returns:
            Dictionary with status information
        """
        if not LANGCHAIN_AVAILABLE:
            return {
                "status": "disabled",
                "initialized": False,
                "vector_store_type": None,
                "embedding_model": None,
                "llm_model": None,
                "error": "LangChain packages not available",
            }

        if not self.initialized:
            return {
                "status": "error",
                "initialized": False,
                "vector_store_type": self.vector_store_type,
                "embedding_model": None,
                "llm_model": None,
                "error": "RAG system initialization failed",
            }

        # Get vector store details
        vector_store_info = {}
        if self.vector_store_type.lower() == "pinecone":
            try:
                # Get namespace statistics from Pinecone index
                pinecone_api_key = self.config.get(
                    "pinecone_api_key", os.environ.get("PINECONE_API_KEY")
                )
                pinecone_environment = self.config.get(
                    "pinecone_environment", os.environ.get("PINECONE_ENVIRONMENT")
                )
                index_name = self.config.get(
                    "index_name",
                    get_config().get(
                        "llm_integration.vector_store.pinecone.index_name",
                        "fxml4-knowledge",
                    ),
                )

                if pinecone_api_key and pinecone_environment:
                    pinecone.init(
                        api_key=pinecone_api_key, environment=pinecone_environment
                    )

                    # Get index stats
                    index = pinecone.Index(index_name)
                    stats = index.describe_index_stats()

                    vector_store_info = {
                        "index_name": index_name,
                        "namespace": self.namespace,
                        "total_vectors": stats.get("total_vector_count", 0),
                        "dimension": stats.get("dimension", 0),
                        "namespaces": stats.get("namespaces", {}),
                    }
            except Exception as e:
                vector_store_info = {"error": str(e)}

        # Get LLM model details
        llm_info = {}
        try:
            llm_info = {
                "provider": self.config.get("provider", "openai"),
                "model": self.config.get("model", "gpt-4o"),
                "temperature": self.config.get("temperature", 0.2),
            }
        except Exception as e:
            llm_info = {"error": str(e)}

        return {
            "status": "ready",
            "initialized": self.initialized,
            "vector_store": {
                "type": self.vector_store_type,
                "details": vector_store_info,
            },
            "embedding_model": self.config.get(
                "embedding_model", "text-embedding-3-small"
            ),
            "llm": llm_info,
            "namespace": self.namespace,
        }
