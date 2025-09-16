"""
Model Registry for FXML4

This module provides a centralized registry for ML models with:
1. Model versioning
2. Metadata tracking
3. Model search and retrieval
4. Cloud integration with Google Vertex AI

The registry serves as a single source of truth for all trained models
and provides a consistent interface for working with models across
development and production environments.
"""

import datetime
import json
import logging
import os
import shutil
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from .models import ClassicMLModel, EnsembleModel

# Conditional import for Vertex AI
try:
    from .vertex_ai import VertexAIModel, check_vertex_availability

    VERTEX_AVAILABLE = True
except ImportError:
    VERTEX_AVAILABLE = False

logger = logging.getLogger(__name__)


class ModelRegistry:
    """Centralized registry for ML models."""

    def __init__(
        self,
        base_dir: str = "models",
        cloud_provider: Optional[str] = None,
        cloud_config: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize the model registry.

        Args:
            base_dir: Base directory for storing models locally
            cloud_provider: Cloud provider for model storage (None, 'vertex_ai')
            cloud_config: Configuration for cloud provider
        """
        self.base_dir = base_dir
        self.cloud_provider = cloud_provider
        self.cloud_client = None

        # Create base directory if it doesn't exist
        os.makedirs(base_dir, exist_ok=True)

        # Set up registry index
        self.index_path = os.path.join(base_dir, "registry_index.json")
        self.index = self._load_index()

        # Initialize cloud client if requested
        if cloud_provider:
            self._initialize_cloud_client(cloud_provider, cloud_config)

    def _initialize_cloud_client(
        self, provider: str, config: Optional[Dict[str, Any]] = None
    ):
        """Initialize cloud client based on provider."""
        if provider == "vertex_ai":
            if not VERTEX_AVAILABLE or not check_vertex_availability():
                logger.warning("Vertex AI not available. Using local storage only.")
                return

            if config is None:
                config = {}

            project_id = config.get("project_id")
            if not project_id:
                logger.warning(
                    "No project_id specified for Vertex AI. Using local storage only."
                )
                return

            # Initialize Vertex AI client
            self.cloud_client = VertexAIModel(
                project_id=project_id,
                location=config.get("location", "us-central1"),
                staging_bucket=config.get("staging_bucket"),
                model_registry_name=config.get(
                    "model_registry_name", "fxml4-model-registry"
                ),
            )
            logger.info(f"Initialized Vertex AI client for project {project_id}")
        else:
            logger.warning(f"Unsupported cloud provider: {provider}")

    def _load_index(self) -> Dict[str, Any]:
        """Load registry index from disk."""
        if os.path.exists(self.index_path):
            try:
                with open(self.index_path, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load registry index: {str(e)}")
                return {"models": {}, "last_updated": None}
        else:
            return {"models": {}, "last_updated": None}

    def _save_index(self):
        """Save registry index to disk."""
        try:
            self.index["last_updated"] = datetime.datetime.now().isoformat()
            with open(self.index_path, "w") as f:
                json.dump(self.index, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save registry index: {str(e)}")

    def register_model(
        self,
        model: Union[ClassicMLModel, EnsembleModel],
        version: Optional[str] = None,
        description: str = "",
        tags: Optional[List[str]] = None,
        upload_to_cloud: bool = False,
    ) -> Dict[str, Any]:
        """
        Register a model in the registry.

        Args:
            model: Model to register
            version: Model version (if None, generated from timestamp)
            description: Model description
            tags: Tags for categorizing the model
            upload_to_cloud: Whether to upload model to cloud

        Returns:
            Dictionary with registration information
        """
        # Generate version if not provided
        if version is None:
            version = datetime.datetime.now().strftime("v%Y%m%d_%H%M%S")

        # Create model directory
        model_dir = os.path.join(self.base_dir, model.name, version)
        os.makedirs(model_dir, exist_ok=True)

        # Save model locally
        model.save(model_dir)

        # Add model to index
        if model.name not in self.index["models"]:
            self.index["models"][model.name] = {
                "versions": {},
                "created_at": datetime.datetime.now().isoformat(),
                "model_type": model.model_type,
                "latest_version": version,
            }

        # Add version to model
        self.index["models"][model.name]["versions"][version] = {
            "path": model_dir,
            "created_at": datetime.datetime.now().isoformat(),
            "description": description,
            "tags": tags or [],
            "model_type": model.model_type,
            "cloud_info": None,
        }

        # Update latest version
        self.index["models"][model.name]["latest_version"] = version

        # Save index
        self._save_index()

        # Upload to cloud if requested
        cloud_info = None
        if upload_to_cloud and self.cloud_client:
            try:
                if self.cloud_provider == "vertex_ai":
                    # Convert tags to labels
                    labels = {}
                    if tags:
                        for tag in tags:
                            # Sanitize tag for GCP labels (lowercase, only letters, numbers, and dashes)
                            key = "".join(
                                c.lower() if c.isalnum() else "_" for c in tag
                            )
                            labels[key] = "true"

                    # Register in Vertex AI
                    cloud_info = self.cloud_client.register_model(
                        model=model,
                        version=version,
                        description=description,
                        labels=labels,
                    )

                    # Update cloud info in index
                    self.index["models"][model.name]["versions"][version][
                        "cloud_info"
                    ] = cloud_info
                    self._save_index()

                    logger.info(
                        f"Uploaded model {model.name} version {version} to {self.cloud_provider}"
                    )
            except Exception as e:
                logger.error(f"Failed to upload model to cloud: {str(e)}")

        logger.info(f"Registered model {model.name} version {version}")

        return {
            "model_name": model.name,
            "version": version,
            "path": model_dir,
            "cloud_info": cloud_info,
        }

    def load_model(
        self, model_name: str, version: Optional[str] = None, prefer_cloud: bool = False
    ) -> Union[ClassicMLModel, EnsembleModel]:
        """
        Load model from registry.

        Args:
            model_name: Name of the model to load
            version: Model version (if None, uses latest)
            prefer_cloud: Whether to prefer loading from cloud if available

        Returns:
            Loaded model
        """
        # Check if model exists
        if model_name not in self.index["models"]:
            raise ValueError(f"Model {model_name} not found in registry")

        # Determine version
        if version is None:
            version = self.index["models"][model_name]["latest_version"]

        # Check if version exists
        if version not in self.index["models"][model_name]["versions"]:
            raise ValueError(f"Version {version} of model {model_name} not found")

        # Get version info
        version_info = self.index["models"][model_name]["versions"][version]

        # Try loading from cloud if preferred and available
        if prefer_cloud and self.cloud_client and version_info.get("cloud_info"):
            try:
                logger.info(f"Loading model {model_name} version {version} from cloud")
                return self.cloud_client.load_model(model_name, version)
            except Exception as e:
                logger.warning(
                    f"Failed to load model from cloud, falling back to local: {str(e)}"
                )

        # Load model from local path
        local_path = version_info["path"]
        if not os.path.exists(local_path):
            raise FileNotFoundError(f"Model path {local_path} does not exist")

        # Determine model type and load accordingly
        model_type = version_info.get("model_type")
        if model_type == "ensemble":
            # Ensemble loading requires special handling
            # This is a simplification
            raise NotImplementedError("Loading ensemble models not yet implemented")
        else:
            model = ClassicMLModel.load(model_name, local_path)

        logger.info(f"Loaded model {model_name} version {version}")
        return model

    def list_models(
        self, tags: Optional[List[str]] = None, model_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        List models in the registry.

        Args:
            tags: Filter by tags
            model_type: Filter by model type

        Returns:
            List of models matching criteria
        """
        models = []

        for name, model_info in self.index["models"].items():
            # Apply filters
            if model_type and model_info.get("model_type") != model_type:
                continue

            # Extract latest version info
            latest_version = model_info["latest_version"]
            version_info = model_info["versions"][latest_version]

            # Filter by tags
            if tags and not all(tag in version_info.get("tags", []) for tag in tags):
                continue

            # Build model info
            model_entry = {
                "name": name,
                "model_type": model_info.get("model_type"),
                "created_at": model_info.get("created_at"),
                "latest_version": latest_version,
                "latest_version_created_at": version_info.get("created_at"),
                "description": version_info.get("description", ""),
                "tags": version_info.get("tags", []),
                "has_cloud_version": version_info.get("cloud_info") is not None,
            }

            models.append(model_entry)

        return models

    def list_versions(self, model_name: str) -> List[Dict[str, Any]]:
        """
        List versions of a model.

        Args:
            model_name: Name of the model

        Returns:
            List of versions
        """
        if model_name not in self.index["models"]:
            raise ValueError(f"Model {model_name} not found in registry")

        versions = []
        for version, version_info in self.index["models"][model_name][
            "versions"
        ].items():
            version_entry = {
                "version": version,
                "created_at": version_info.get("created_at"),
                "description": version_info.get("description", ""),
                "tags": version_info.get("tags", []),
                "has_cloud_version": version_info.get("cloud_info") is not None,
            }
            versions.append(version_entry)

        # Sort by creation time (newest first)
        versions.sort(key=lambda x: x["created_at"], reverse=True)

        return versions

    def get_model_info(
        self, model_name: str, version: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get information about a model version.

        Args:
            model_name: Name of the model
            version: Model version (if None, uses latest)

        Returns:
            Dictionary with model information
        """
        if model_name not in self.index["models"]:
            raise ValueError(f"Model {model_name} not found in registry")

        # Determine version
        if version is None:
            version = self.index["models"][model_name]["latest_version"]

        if version not in self.index["models"][model_name]["versions"]:
            raise ValueError(f"Version {version} of model {model_name} not found")

        # Get model info
        model_info = self.index["models"][model_name]
        version_info = model_info["versions"][version]

        # Load metadata if available
        metadata = {}
        metadata_path = os.path.join(
            version_info["path"], f"{model_name}_metadata.json"
        )
        if os.path.exists(metadata_path):
            try:
                with open(metadata_path, "r") as f:
                    metadata = json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load model metadata: {str(e)}")

        # Build detailed info
        detailed_info = {
            "name": model_name,
            "version": version,
            "model_type": model_info.get("model_type"),
            "created_at": version_info.get("created_at"),
            "description": version_info.get("description", ""),
            "tags": version_info.get("tags", []),
            "is_latest": version == model_info["latest_version"],
            "cloud_info": version_info.get("cloud_info"),
            "metadata": metadata,
        }

        return detailed_info

    def delete_model(
        self,
        model_name: str,
        version: Optional[str] = None,
        delete_all_versions: bool = False,
        delete_from_cloud: bool = False,
    ) -> bool:
        """
        Delete a model from the registry.

        Args:
            model_name: Name of the model
            version: Specific version to delete (if None and delete_all_versions is True, deletes all versions)
            delete_all_versions: Whether to delete all versions
            delete_from_cloud: Whether to delete from cloud

        Returns:
            True if successful
        """
        if model_name not in self.index["models"]:
            raise ValueError(f"Model {model_name} not found in registry")

        if delete_all_versions:
            # Delete all versions
            for version in list(self.index["models"][model_name]["versions"].keys()):
                self._delete_model_version(model_name, version, delete_from_cloud)

            # Remove model from index
            del self.index["models"][model_name]
            self._save_index()

            # Delete model directory
            model_dir = os.path.join(self.base_dir, model_name)
            if os.path.exists(model_dir):
                shutil.rmtree(model_dir)

            logger.info(f"Deleted all versions of model {model_name}")
            return True
        elif version:
            # Delete specific version
            if version not in self.index["models"][model_name]["versions"]:
                raise ValueError(f"Version {version} of model {model_name} not found")

            self._delete_model_version(model_name, version, delete_from_cloud)

            # Update latest version if necessary
            if self.index["models"][model_name]["latest_version"] == version:
                # Find new latest version
                versions = self.list_versions(model_name)
                if versions:
                    self.index["models"][model_name]["latest_version"] = versions[0][
                        "version"
                    ]
                else:
                    # No versions left, delete the model
                    del self.index["models"][model_name]

            self._save_index()
            return True
        else:
            raise ValueError("Either version or delete_all_versions must be specified")

    def _delete_model_version(
        self, model_name: str, version: str, delete_from_cloud: bool = False
    ):
        """Delete a specific model version."""
        version_info = self.index["models"][model_name]["versions"][version]

        # Delete from cloud if requested
        if delete_from_cloud and self.cloud_client and version_info.get("cloud_info"):
            try:
                # This depends on the cloud provider's API
                logger.warning("Cloud deletion not implemented yet")
            except Exception as e:
                logger.error(f"Failed to delete model from cloud: {str(e)}")

        # Delete local files
        path = version_info["path"]
        if os.path.exists(path):
            try:
                shutil.rmtree(path)
            except Exception as e:
                logger.error(f"Failed to delete model files: {str(e)}")

        # Remove from index
        del self.index["models"][model_name]["versions"][version]

        logger.info(f"Deleted model {model_name} version {version}")

    def deploy_model(
        self,
        model_name: str,
        version: Optional[str] = None,
        deployment_config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Deploy a model to a cloud endpoint.

        Args:
            model_name: Name of the model
            version: Model version (if None, uses latest)
            deployment_config: Configuration for deployment

        Returns:
            Dictionary with deployment information
        """
        if not self.cloud_client:
            raise ValueError("No cloud provider configured")

        # Determine version
        if version is None:
            if model_name not in self.index["models"]:
                raise ValueError(f"Model {model_name} not found in registry")
            version = self.index["models"][model_name]["latest_version"]

        # Default configuration
        if deployment_config is None:
            deployment_config = {}

        # Deploy based on cloud provider
        if self.cloud_provider == "vertex_ai":
            result = self.cloud_client.deploy_model(
                model_id=model_name,
                version=version,
                machine_type=deployment_config.get("machine_type", "n1-standard-2"),
                min_replicas=deployment_config.get("min_replicas", 1),
                max_replicas=deployment_config.get("max_replicas", 1),
            )

            # Update deployment info in registry
            if (
                model_name in self.index["models"]
                and version in self.index["models"][model_name]["versions"]
            ):
                self.index["models"][model_name]["versions"][version][
                    "deployment_info"
                ] = result
                self._save_index()

            logger.info(
                f"Deployed model {model_name} version {version} to {self.cloud_provider}"
            )
            return result
        else:
            raise ValueError(
                f"Deployment not supported for provider {self.cloud_provider}"
            )

    def sync_with_cloud(self) -> Dict[str, Any]:
        """
        Sync registry with cloud provider.

        Returns:
            Dictionary with sync information
        """
        if not self.cloud_client:
            raise ValueError("No cloud provider configured")

        if self.cloud_provider == "vertex_ai":
            try:
                # Get models from cloud
                cloud_models = self.cloud_client.list_models()

                # Track sync results
                sync_results = {"added": [], "updated": [], "errors": []}

                # Process each cloud model
                for cloud_model in cloud_models:
                    model_name = cloud_model.get("name").split("/")[-1]
                    if not model_name.startswith("fxml4_"):
                        continue

                    # Extract model name from display name
                    model_name = model_name.replace("fxml4_", "")
                    version = cloud_model.get("version")

                    if model_name not in self.index["models"]:
                        # New model
                        self.index["models"][model_name] = {
                            "versions": {},
                            "created_at": cloud_model.get("create_time"),
                            "model_type": cloud_model.get("metadata", {}).get(
                                "algorithm", "unknown"
                            ),
                            "latest_version": version,
                        }
                        sync_results["added"].append(f"{model_name}:{version}")

                    # Add or update version
                    if version not in self.index["models"][model_name]["versions"]:
                        # New version
                        self.index["models"][model_name]["versions"][version] = {
                            "path": None,  # No local path
                            "created_at": cloud_model.get("create_time"),
                            "description": cloud_model.get("description", ""),
                            "tags": [],  # No tags from cloud
                            "model_type": cloud_model.get("metadata", {}).get(
                                "algorithm", "unknown"
                            ),
                            "cloud_info": cloud_model,
                        }
                        sync_results["added"].append(f"{model_name}:{version}")
                    else:
                        # Update existing version
                        self.index["models"][model_name]["versions"][version][
                            "cloud_info"
                        ] = cloud_model
                        sync_results["updated"].append(f"{model_name}:{version}")

                # Save index
                self._save_index()

                logger.info(
                    f"Synced with {self.cloud_provider}: {len(sync_results['added'])} added, {len(sync_results['updated'])} updated"
                )
                return sync_results
            except Exception as e:
                logger.error(f"Failed to sync with cloud: {str(e)}")
                raise
        else:
            raise ValueError(f"Sync not supported for provider {self.cloud_provider}")
