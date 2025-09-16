"""Vector store implementation using Pinecone with the latest v3.0.0+ API."""

import os
import uuid
from typing import Dict, List, Optional, Tuple, Union

import pinecone
from dotenv import load_dotenv

from fxml3.llm_integration.llm_client import LLMClient


def check_pinecone_connection() -> Dict:
    """Check Pinecone connection and return index stats.

    Returns:
        Dictionary with connection status and statistics about the index.
    """
    # Load environment variables
    load_dotenv()

    # Set API credentials
    api_key = os.environ.get("PINECONE_API_TOKEN")

    if not api_key:
        return {
            "status": "error",
            "message": "Pinecone API key not found in environment",
            "connected": False,
        }

    try:
        # Initialize Pinecone client (using v3.0.0+ API)
        pc = pinecone.Pinecone(api_key=api_key)

        # Get list of indexes
        indexes = pc.list_indexes()
        index_names = [idx.name for idx in indexes]

        if not indexes:
            return {
                "status": "warning",
                "message": "Connected to Pinecone but no indexes found",
                "connected": True,
                "indexes": [],
            }

        # Get stats for each index
        index_stats = {}
        for idx_info in indexes:
            index_name = idx_info.name
            try:
                index = pc.Index(index_name)
                stats = index.describe_index_stats()
                index_stats[index_name] = {
                    "namespaces": stats.get("namespaces", {}),
                    "dimension": stats.get("dimension"),
                    "total_vector_count": stats.get("total_vector_count", 0),
                }
            except Exception as e:
                index_stats[index_name] = {"error": str(e)}

        return {
            "status": "success",
            "message": f"Connected to Pinecone. Found {len(indexes)} indexes.",
            "connected": True,
            "indexes": index_names,
            "index_stats": index_stats,
        }

    except Exception as e:
        return {
            "status": "error",
            "message": f"Error connecting to Pinecone: {str(e)}",
            "connected": False,
        }


class PineconeVectorStore:
    """Pinecone vector store for storing and retrieving embeddings.

    This class provides an interface to Pinecone for storing and
    retrieving document embeddings, and supports semantic search
    with similarity metrics.

    Updated to work with Pinecone v3.0.0+ API.
    """

    def __init__(
        self,
        index_name: str = "fxml3-wave",
        namespace: str = "elliott-wave-theory",
        embedding_model: str = "text-embedding-3-small",
        dimensions: int = 1536,
        metric: str = "cosine",
        api_key: Optional[str] = None,
    ):
        """Initialize the Pinecone vector store.

        Args:
            index_name: Name of the Pinecone index
            namespace: Namespace within the index
            embedding_model: Model used for generating embeddings
            dimensions: Dimensionality of the embeddings
            metric: Similarity metric to use (cosine, dotproduct, euclidean)
            api_key: Pinecone API key (if None, read from environment)
        """
        # Load environment variables
        load_dotenv()

        # Set configuration
        self.index_name = index_name
        self.namespace = namespace
        self.embedding_model = embedding_model
        self.dimensions = dimensions
        self.metric = metric

        # Set API credentials
        self.api_key = api_key or os.environ.get("PINECONE_API_TOKEN")

        if not self.api_key:
            raise ValueError("Pinecone API key not provided or found in environment")

        # Initialize Pinecone
        self._init_pinecone()

        # Initialize LLM client for embeddings
        self.llm_client = LLMClient(provider="openai")

    def _init_pinecone(self) -> None:
        """Initialize connection to Pinecone and ensure index exists."""
        # Initialize Pinecone client (v3.0.0+ API)
        self.pc = pinecone.Pinecone(api_key=self.api_key)

        # Check if index exists, create if not
        existing_indexes = self.pc.list_indexes()
        existing_index_names = [idx.name for idx in existing_indexes]

        if self.index_name not in existing_index_names:
            self.pc.create_index(
                name=self.index_name,
                dimension=self.dimensions,
                metric=self.metric,
                spec=pinecone.ServerlessSpec(cloud="aws", region="us-east-1"),
            )

            # Wait for index to be ready
            import time

            while not self.pc.describe_index(self.index_name).status.ready:
                time.sleep(5)

        # Connect to the index
        self.index = self.pc.Index(self.index_name)

    def add_texts(
        self,
        texts: List[str],
        metadatas: Optional[List[Dict]] = None,
        ids: Optional[List[str]] = None,
        batch_size: int = 100,
    ) -> List[str]:
        """Add texts to the vector store.

        Args:
            texts: List of text documents to add
            metadatas: Optional list of metadata dictionaries for each text
            ids: Optional list of IDs for each text
            batch_size: Number of texts to process in each batch

        Returns:
            List of IDs for the added texts

        Raises:
            Exception: If there's an error with Pinecone or embeddings
        """
        if not texts:
            return []

        # Generate IDs if not provided
        if ids is None:
            ids = [str(uuid.uuid4()) for _ in range(len(texts))]

        # Initialize empty metadata if not provided
        if metadatas is None:
            metadatas = [{} for _ in range(len(texts))]

        # Process in batches
        result_ids = []
        for i in range(0, len(texts), batch_size):
            # Get batch
            batch_texts = texts[i : i + batch_size]
            batch_metadatas = metadatas[i : i + batch_size]
            batch_ids = ids[i : i + batch_size]

            # Generate embeddings
            batch_embeddings = [
                self.llm_client.get_embedding(text, self.embedding_model)
                for text in batch_texts
            ]

            # Create upsert data
            vectors = [
                {
                    "id": id_,
                    "values": embedding,
                    "metadata": {
                        "text": text,
                        **metadata,
                    },
                }
                for id_, text, embedding, metadata in zip(
                    batch_ids, batch_texts, batch_embeddings, batch_metadatas
                )
            ]

            # Upsert to Pinecone (v3.0.0+ API)
            try:
                self.index.upsert(
                    vectors=vectors,
                    namespace=self.namespace,
                )
                result_ids.extend(batch_ids)
            except Exception as e:
                raise Exception(f"Pinecone upsert error: {str(e)}")

        return result_ids

    def similarity_search(
        self,
        query: str,
        k: int = 5,
        filter: Optional[Dict] = None,
    ) -> List[Dict]:
        """Search for similar documents.

        Args:
            query: Query text
            k: Number of results to return
            filter: Optional filter for metadata

        Returns:
            List of dictionaries containing document and similarity score
        """
        # Generate query embedding
        query_embedding = self.llm_client.get_embedding(query, self.embedding_model)

        # Perform similarity search (v3.0.0+ API)
        try:
            results = self.index.query(
                vector=query_embedding,
                top_k=k,
                include_metadata=True,
                namespace=self.namespace,
                filter=filter,
            )
        except Exception as e:
            raise Exception(f"Pinecone query error: {str(e)}")

        # Format results (v3.0.0+ API)
        documents = []
        for match in results.get("matches", []):
            documents.append(
                {
                    "id": match.get("id", ""),
                    "text": match.get("metadata", {}).get("text", ""),
                    "metadata": {
                        k: v
                        for k, v in match.get("metadata", {}).items()
                        if k != "text"
                    },
                    "score": match.get("score", 0.0),
                }
            )

        return documents

    def delete(
        self,
        ids: Optional[List[str]] = None,
        filter: Optional[Dict] = None,
        delete_all: bool = False,
    ) -> None:
        """Delete vectors from the index.

        Args:
            ids: List of IDs to delete
            filter: Filter to select vectors to delete
            delete_all: Whether to delete all vectors in the namespace

        Raises:
            ValueError: If no deletion method is specified
            Exception: If there's an error with Pinecone
        """
        if delete_all:
            try:
                # v3.0.0+ API for delete_all
                self.index.delete(
                    delete_all=True,
                    namespace=self.namespace,
                )
            except Exception as e:
                raise Exception(f"Pinecone delete_all error: {str(e)}")
        elif ids:
            try:
                self.index.delete(
                    ids=ids,
                    namespace=self.namespace,
                )
            except Exception as e:
                raise Exception(f"Pinecone delete by ids error: {str(e)}")
        elif filter:
            try:
                # v3.0.0+ API doesn't directly support delete by filter
                # We need to first query to get ids matching the filter
                results = self.index.query(
                    vector=[0.0] * self.dimensions,  # Dummy vector
                    top_k=10000,  # Get all matches
                    filter=filter,
                    namespace=self.namespace,
                )
                ids_to_delete = [
                    match.get("id") for match in results.get("matches", [])
                ]

                if ids_to_delete:
                    self.index.delete(
                        ids=ids_to_delete,
                        namespace=self.namespace,
                    )
            except Exception as e:
                raise Exception(f"Pinecone delete by filter error: {str(e)}")
        else:
            raise ValueError("Specify ids, filter, or delete_all for deletion")

    def get_by_id(self, id: str) -> Optional[Dict]:
        """Retrieve a vector by ID.

        Args:
            id: The ID of the vector to retrieve

        Returns:
            Dictionary containing the document and metadata, or None if not found
        """
        try:
            # v3.0.0+ API for fetch
            result = self.index.fetch(
                ids=[id],
                namespace=self.namespace,
            )
        except Exception as e:
            raise Exception(f"Pinecone fetch error: {str(e)}")

        # Check if vector was found (v3.0.0+ API)
        vectors = result.get("vectors", {})
        if id in vectors:
            vector = vectors[id]
            return {
                "id": id,
                "text": vector.get("metadata", {}).get("text", ""),
                "metadata": {
                    k: v for k, v in vector.get("metadata", {}).items() if k != "text"
                },
                "values": vector.get("values", []),
            }
        else:
            return None
