"""
Model Loader for FXML4

This module provides functionality for loading trained ML models from various sources:
1. Local filesystem
2. Model registry
3. Google Cloud Storage (GCS)
4. Vertex AI Model Registry

The loader supports automatic format detection, version management, and
caching for improved performance.
"""

import hashlib
import json
import logging
import os
import pickle
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import joblib
import numpy as np
import pandas as pd

from fxml4.ml.model_registry import ModelRegistry

# FXML4 imports
from fxml4.ml.models import ClassicMLModel, EnsembleModel

# Conditional imports
try:
    from google.cloud import storage

    GCS_AVAILABLE = True
except ImportError:
    GCS_AVAILABLE = False

try:
    from fxml4.ml.vertex_ai import VertexAIModel, check_vertex_availability

    VERTEX_AVAILABLE = True
except ImportError:
    VERTEX_AVAILABLE = False

logger = logging.getLogger(__name__)


class ModelCache:
    """Simple in-memory cache for loaded models."""

    def __init__(self, max_size: int = 10, ttl_minutes: int = 60):
        """
        Initialize model cache.

        Args:
            max_size: Maximum number of models to cache
            ttl_minutes: Time-to-live for cached models in minutes
        """
        self.max_size = max_size
        self.ttl_minutes = ttl_minutes
        self.cache = {}
        self.access_times = {}

    def get(self, key: str) -> Optional[Any]:
        """Get model from cache if available and not expired."""
        if key not in self.cache:
            return None

        # Check if expired
        if datetime.now() - self.access_times[key] > timedelta(
            minutes=self.ttl_minutes
        ):
            del self.cache[key]
            del self.access_times[key]
            return None

        # Update access time
        self.access_times[key] = datetime.now()
        return self.cache[key]

    def put(self, key: str, model: Any) -> None:
        """Put model in cache."""
        # Remove oldest if cache is full
        if len(self.cache) >= self.max_size:
            oldest_key = min(self.access_times, key=self.access_times.get)
            del self.cache[oldest_key]
            del self.access_times[oldest_key]

        self.cache[key] = model
        self.access_times[key] = datetime.now()

    def clear(self) -> None:
        """Clear the cache."""
        self.cache.clear()
        self.access_times.clear()


class ModelLoader:
    """Unified model loader for FXML4."""

    def __init__(
        self,
        registry: Optional[ModelRegistry] = None,
        cache_enabled: bool = True,
        cache_size: int = 10,
        cache_ttl_minutes: int = 60,
    ):
        """
        Initialize model loader.

        Args:
            registry: Model registry instance (creates default if None)
            cache_enabled: Whether to enable model caching
            cache_size: Maximum number of models to cache
            cache_ttl_minutes: Cache TTL in minutes
        """
        self.registry = registry or ModelRegistry()
        self.cache_enabled = cache_enabled

        if cache_enabled:
            self.cache = ModelCache(max_size=cache_size, ttl_minutes=cache_ttl_minutes)
        else:
            self.cache = None

    def load(
        self,
        model_identifier: str,
        source: str = "auto",
        version: Optional[str] = None,
        force_reload: bool = False,
    ) -> Union[ClassicMLModel, EnsembleModel]:
        """
        Load a model from the specified source.

        Args:
            model_identifier: Model name, path, or URI
            source: Source type ("auto", "local", "registry", "gcs", "vertex_ai")
            version: Model version (for registry/cloud sources)
            force_reload: Force reload even if cached

        Returns:
            Loaded model instance
        """
        # Generate cache key
        cache_key = self._generate_cache_key(model_identifier, source, version)

        # Check cache unless force reload
        if not force_reload and self.cache_enabled:
            cached_model = self.cache.get(cache_key)
            if cached_model is not None:
                logger.info(f"Loaded model from cache: {model_identifier}")
                return cached_model

        # Determine source if auto
        if source == "auto":
            source = self._detect_source(model_identifier)

        # Load model based on source
        if source == "local":
            model = self._load_local(model_identifier)
        elif source == "registry":
            model = self._load_from_registry(model_identifier, version)
        elif source == "gcs":
            model = self._load_from_gcs(model_identifier)
        elif source == "vertex_ai":
            model = self._load_from_vertex_ai(model_identifier, version)
        else:
            raise ValueError(f"Unknown source: {source}")

        # Cache the loaded model
        if self.cache_enabled:
            self.cache.put(cache_key, model)

        logger.info(f"Successfully loaded model: {model_identifier} from {source}")
        return model

    def _generate_cache_key(
        self, identifier: str, source: str, version: Optional[str]
    ) -> str:
        """Generate a cache key for the model."""
        key_parts = [identifier, source]
        if version:
            key_parts.append(version)
        key_string = "|".join(key_parts)
        return hashlib.md5(key_string.encode()).hexdigest()

    def _detect_source(self, identifier: str) -> str:
        """Detect the source type from the identifier."""
        # Check if it's a GCS URI
        if identifier.startswith("gs://"):
            return "gcs"

        # Check if it's a local path
        if os.path.exists(identifier) or "/" in identifier or "\\" in identifier:
            return "local"

        # Check if it exists in registry
        try:
            models = self.registry.list_models()
            if any(m["name"] == identifier for m in models):
                return "registry"
        except:
            pass

        # Default to registry
        return "registry"

    def _load_local(self, path: str) -> Union[ClassicMLModel, EnsembleModel]:
        """Load model from local filesystem."""
        path = Path(path)

        if path.is_dir():
            # Directory containing model files
            return self._load_from_directory(path)
        elif path.is_file():
            # Single model file
            return self._load_from_file(path)
        else:
            raise FileNotFoundError(f"Model path not found: {path}")

    def _load_from_directory(
        self, directory: Path
    ) -> Union[ClassicMLModel, EnsembleModel]:
        """Load model from a directory containing model files."""
        # Look for metadata file to determine model name
        metadata_files = list(directory.glob("*_metadata.json"))
        if not metadata_files:
            raise ValueError(f"No metadata file found in {directory}")

        # Load metadata to determine model type
        with open(metadata_files[0], "r") as f:
            metadata = json.load(f)

        model_name = metadata.get(
            "name", metadata_files[0].stem.replace("_metadata", "")
        )
        model_type = metadata.get("model_type", "unknown")

        # Load based on model type
        if model_type == "ensemble":
            # For ensemble models, we need special handling
            # This is a simplified version - full implementation would load base models
            raise NotImplementedError(
                "Loading ensemble models from directory not yet implemented"
            )
        else:
            # Load classic ML model
            model = ClassicMLModel.load(model_name, str(directory))

        return model

    def _load_from_file(self, file_path: Path) -> Union[ClassicMLModel, EnsembleModel]:
        """Load model from a single file."""
        # Determine format from extension
        extension = file_path.suffix.lower()

        if extension == ".joblib":
            # Load joblib model
            model_object = joblib.load(file_path)

            # Wrap in ClassicMLModel if it's a sklearn model
            if hasattr(model_object, "predict") and hasattr(model_object, "fit"):
                # Create a wrapper ClassicMLModel
                wrapped_model = ClassicMLModel(model_type="custom", name=file_path.stem)
                wrapped_model.model = model_object
                return wrapped_model
            else:
                return model_object

        elif extension in [".pkl", ".pickle"]:
            # Load pickle model
            with open(file_path, "rb") as f:
                model_object = pickle.load(f)

            # Wrap if needed
            if hasattr(model_object, "predict") and hasattr(model_object, "fit"):
                wrapped_model = ClassicMLModel(model_type="custom", name=file_path.stem)
                wrapped_model.model = model_object
                return wrapped_model
            else:
                return model_object

        else:
            raise ValueError(f"Unsupported file format: {extension}")

    def _load_from_registry(
        self, model_name: str, version: Optional[str] = None
    ) -> Union[ClassicMLModel, EnsembleModel]:
        """Load model from the model registry."""
        return self.registry.load_model(model_name, version)

    def _load_from_gcs(self, gcs_uri: str) -> Union[ClassicMLModel, EnsembleModel]:
        """Load model from Google Cloud Storage."""
        if not GCS_AVAILABLE:
            raise ImportError(
                "Google Cloud Storage not available. Install google-cloud-storage."
            )

        # Parse GCS URI
        if not gcs_uri.startswith("gs://"):
            raise ValueError(f"Invalid GCS URI: {gcs_uri}")

        # Extract bucket and blob path
        path_parts = gcs_uri.replace("gs://", "").split("/", 1)
        bucket_name = path_parts[0]
        blob_prefix = path_parts[1] if len(path_parts) > 1 else ""

        # Download to temporary directory
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Download files from GCS
            storage_client = storage.Client()
            bucket = storage_client.bucket(bucket_name)

            # List all blobs with the prefix
            blobs = bucket.list_blobs(prefix=blob_prefix)
            downloaded_files = []

            for blob in blobs:
                # Get relative path from prefix
                relative_path = blob.name[len(blob_prefix) :].lstrip("/")
                if relative_path:  # Skip directories
                    local_path = temp_path / relative_path
                    local_path.parent.mkdir(parents=True, exist_ok=True)
                    blob.download_to_filename(str(local_path))
                    downloaded_files.append(local_path)

            if not downloaded_files:
                raise ValueError(f"No files found at {gcs_uri}")

            # Load from temporary directory
            return self._load_from_directory(temp_path)

    def _load_from_vertex_ai(
        self, model_id: str, version: Optional[str] = None
    ) -> Union[ClassicMLModel, EnsembleModel]:
        """Load model from Vertex AI Model Registry."""
        if not VERTEX_AVAILABLE or not check_vertex_availability():
            raise ImportError(
                "Vertex AI not available. Install google-cloud-aiplatform."
            )

        # Initialize Vertex AI client
        vertex_client = VertexAIModel()

        # Load model
        return vertex_client.load_model(model_id, version)

    def load_ensemble(
        self,
        base_model_identifiers: List[Tuple[str, str]],
        ensemble_method: str = "weighted",
        weights: Optional[List[float]] = None,
    ) -> EnsembleModel:
        """
        Load and create an ensemble from multiple models.

        Args:
            base_model_identifiers: List of (identifier, source) tuples
            ensemble_method: Ensemble method ("vote", "average", "weighted")
            weights: Weights for ensemble (if weighted method)

        Returns:
            Ensemble model instance
        """
        # Load base models
        base_models = []
        for identifier, source in base_model_identifiers:
            model = self.load(identifier, source)
            base_models.append(model)

        # Create ensemble
        ensemble = EnsembleModel(
            models=base_models, ensemble_method=ensemble_method, weights=weights
        )

        return ensemble

    def preload_models(
        self, model_list: List[Dict[str, Any]]
    ) -> Dict[str, Union[ClassicMLModel, EnsembleModel]]:
        """
        Preload multiple models into cache.

        Args:
            model_list: List of model specifications
                Each item should have: identifier, source (optional), version (optional)

        Returns:
            Dictionary of loaded models
        """
        loaded_models = {}

        for model_spec in model_list:
            identifier = model_spec.get("identifier")
            if not identifier:
                logger.warning("Skipping model without identifier")
                continue

            try:
                model = self.load(
                    model_identifier=identifier,
                    source=model_spec.get("source", "auto"),
                    version=model_spec.get("version"),
                    force_reload=False,
                )
                loaded_models[identifier] = model
                logger.info(f"Preloaded model: {identifier}")
            except Exception as e:
                logger.error(f"Failed to preload model {identifier}: {str(e)}")

        return loaded_models

    def clear_cache(self) -> None:
        """Clear the model cache."""
        if self.cache_enabled:
            self.cache.clear()
            logger.info("Model cache cleared")

    def load_latest_model(
        self, model_name: str
    ) -> Union[ClassicMLModel, EnsembleModel]:
        """
        Load the latest version of a model from the registry.

        Args:
            model_name: Name of the model

        Returns:
            Latest model version
        """
        return self.load(model_name, source="registry", version=None)


# Convenience functions
def load_model(
    model_identifier: str,
    source: str = "auto",
    version: Optional[str] = None,
    registry: Optional[ModelRegistry] = None,
) -> Union[ClassicMLModel, EnsembleModel]:
    """
    Convenience function to load a model.

    Args:
        model_identifier: Model name, path, or URI
        source: Source type ("auto", "local", "registry", "gcs", "vertex_ai")
        version: Model version (for registry/cloud sources)
        registry: Model registry instance

    Returns:
        Loaded model instance
    """
    loader = ModelLoader(registry=registry)
    return loader.load(model_identifier, source, version)


def load_latest_model(
    model_name: str, registry: Optional[ModelRegistry] = None
) -> Union[ClassicMLModel, EnsembleModel]:
    """
    Load the latest version of a model from the registry.

    Args:
        model_name: Name of the model
        registry: Model registry instance

    Returns:
        Latest model version
    """
    loader = ModelLoader(registry=registry)
    return loader.load(model_name, source="registry", version=None)
