"""
Comprehensive retrospective test coverage for ML Model Registry.

This module provides comprehensive test coverage for the FXML4 ML Model Registry,
which handles model versioning, metadata tracking, search/retrieval, and
integration with cloud model registries for production ML workflows.

Following TDD principles with retrospective testing approach:
- Testing existing production model registry functionality
- Ensuring comprehensive coverage of model lifecycle management
- Validating metadata tracking and model versioning systems
"""

import json
import os
import shutil
import tempfile
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from unittest.mock import ANY, AsyncMock, MagicMock, call, patch

import numpy as np
import pandas as pd
import pytest

from fxml4.ml.model_registry import (
    CloudModelRegistry,
    LocalModelRegistry,
    ModelMetadata,
    ModelNotFoundError,
    ModelRegistry,
    ModelVersion,
    RegistryConfig,
    RegistryError,
    VersionConflictError,
)
from fxml4.ml.models import ClassicMLModel, EnsembleModel


class TestModelRegistry:
    """Test core model registry functionality."""

    @pytest.fixture
    def temp_registry_dir(self):
        """Create temporary directory for registry testing."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def registry_config(self, temp_registry_dir):
        """Create registry configuration for testing."""
        return RegistryConfig(
            registry_path=temp_registry_dir,
            enable_cloud_sync=False,
            max_versions_per_model=10,
            metadata_format="json",
        )

    @pytest.fixture
    def sample_model_metadata(self):
        """Create sample model metadata for testing."""
        return ModelMetadata(
            name="forex_predictor",
            version="1.0.0",
            model_type="random_forest",
            description="Forex trading signal prediction model",
            author="ML Team",
            created_at=datetime.now(),
            metrics={
                "accuracy": 0.85,
                "precision": 0.82,
                "recall": 0.88,
                "f1_score": 0.85,
                "sharpe_ratio": 1.45,
            },
            hyperparameters={
                "n_estimators": 100,
                "max_depth": 10,
                "min_samples_split": 5,
                "random_state": 42,
            },
            features=["rsi", "macd", "bollinger_ratio", "volume", "returns"],
            training_data_version="2024.1",
            training_duration_minutes=45,
            model_size_mb=2.5,
            tags=["production", "forex", "signals"],
            dependencies=["scikit-learn==1.0.2", "pandas==1.3.3"],
        )

    def test_model_registry_initialization(self, registry_config):
        """Test model registry initialization."""
        registry = ModelRegistry(registry_config)

        assert registry.config == registry_config
        assert registry.models == {}
        assert registry.metadata == {}
        assert os.path.exists(registry_config.registry_path)

    def test_register_model_success(self, registry_config, sample_model_metadata):
        """Test successful model registration."""
        registry = ModelRegistry(registry_config)

        # Create mock model file
        with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as f:
            f.write(b"mock model data")
            model_path = f.name

        try:
            model_id = registry.register_model(
                model_path=model_path, metadata=sample_model_metadata
            )

            assert model_id is not None
            assert model_id in registry.models
            assert model_id in registry.metadata

            # Verify metadata storage
            stored_metadata = registry.metadata[model_id]
            assert stored_metadata.name == "forex_predictor"
            assert stored_metadata.version == "1.0.0"
            assert stored_metadata.metrics["accuracy"] == 0.85

        finally:
            os.unlink(model_path)

    def test_register_model_duplicate_version(
        self, registry_config, sample_model_metadata
    ):
        """Test registration failure for duplicate model version."""
        registry = ModelRegistry(registry_config)

        with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as f:
            f.write(b"mock model data")
            model_path = f.name

        try:
            # Register first version
            registry.register_model(model_path, sample_model_metadata)

            # Try to register same version again
            with pytest.raises(
                VersionConflictError, match="Version 1.0.0 already exists"
            ):
                registry.register_model(model_path, sample_model_metadata)

        finally:
            os.unlink(model_path)

    def test_get_model_by_name_and_version(
        self, registry_config, sample_model_metadata
    ):
        """Test retrieving model by name and version."""
        registry = ModelRegistry(registry_config)

        with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as f:
            f.write(b"mock model data")
            model_path = f.name

        try:
            model_id = registry.register_model(model_path, sample_model_metadata)

            # Retrieve by name and version
            retrieved_model = registry.get_model(
                name="forex_predictor", version="1.0.0"
            )

            assert retrieved_model is not None
            assert retrieved_model == registry.models[model_id]

        finally:
            os.unlink(model_path)

    def test_get_latest_model_version(self, registry_config):
        """Test retrieving latest model version."""
        registry = ModelRegistry(registry_config)

        # Register multiple versions
        versions = ["1.0.0", "1.1.0", "2.0.0"]
        model_ids = []

        for version in versions:
            metadata = ModelMetadata(
                name="forex_predictor",
                version=version,
                model_type="random_forest",
                created_at=datetime.now(),
                metrics={"accuracy": 0.85 + float(version.split(".")[0]) * 0.05},
            )

            with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as f:
                f.write(f"mock model data v{version}".encode())
                model_path = f.name

            try:
                model_id = registry.register_model(model_path, metadata)
                model_ids.append(model_id)
            finally:
                os.unlink(model_path)

        # Get latest version
        latest_model = registry.get_latest_model("forex_predictor")

        assert latest_model is not None
        latest_metadata = registry.get_model_metadata(latest_model)
        assert latest_metadata.version == "2.0.0"

    def test_list_models(self, registry_config):
        """Test listing all models in registry."""
        registry = ModelRegistry(registry_config)

        # Register multiple models
        model_names = ["forex_predictor", "crypto_predictor", "equity_predictor"]

        for name in model_names:
            metadata = ModelMetadata(
                name=name,
                version="1.0.0",
                model_type="random_forest",
                created_at=datetime.now(),
            )

            with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as f:
                f.write(f"mock {name} data".encode())
                model_path = f.name

            try:
                registry.register_model(model_path, metadata)
            finally:
                os.unlink(model_path)

        # List all models
        models = registry.list_models()

        assert len(models) == 3
        model_names_in_registry = [
            registry.get_model_metadata(model).name for model in models
        ]

        for name in model_names:
            assert name in model_names_in_registry

    def test_search_models_by_metrics(self, registry_config):
        """Test searching models by performance metrics."""
        registry = ModelRegistry(registry_config)

        # Register models with different metrics
        models_data = [
            ("model_a", {"accuracy": 0.85, "f1_score": 0.82}),
            ("model_b", {"accuracy": 0.90, "f1_score": 0.88}),
            ("model_c", {"accuracy": 0.75, "f1_score": 0.78}),
        ]

        for name, metrics in models_data:
            metadata = ModelMetadata(
                name=name,
                version="1.0.0",
                model_type="random_forest",
                metrics=metrics,
                created_at=datetime.now(),
            )

            with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as f:
                f.write(f"mock {name} data".encode())
                model_path = f.name

            try:
                registry.register_model(model_path, metadata)
            finally:
                os.unlink(model_path)

        # Search for models with accuracy > 0.80
        high_accuracy_models = registry.search_models(
            criteria={"metrics.accuracy": {"$gt": 0.80}}
        )

        assert len(high_accuracy_models) == 2

        # Verify search results
        for model in high_accuracy_models:
            metadata = registry.get_model_metadata(model)
            assert metadata.metrics["accuracy"] > 0.80

    def test_search_models_by_tags(self, registry_config):
        """Test searching models by tags."""
        registry = ModelRegistry(registry_config)

        models_data = [
            ("model_a", ["production", "forex"]),
            ("model_b", ["development", "forex"]),
            ("model_c", ["production", "crypto"]),
        ]

        for name, tags in models_data:
            metadata = ModelMetadata(
                name=name,
                version="1.0.0",
                model_type="random_forest",
                tags=tags,
                created_at=datetime.now(),
            )

            with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as f:
                f.write(f"mock {name} data".encode())
                model_path = f.name

            try:
                registry.register_model(model_path, metadata)
            finally:
                os.unlink(model_path)

        # Search for production models
        production_models = registry.search_models(
            criteria={"tags": {"$in": ["production"]}}
        )

        assert len(production_models) == 2

    def test_delete_model(self, registry_config, sample_model_metadata):
        """Test model deletion from registry."""
        registry = ModelRegistry(registry_config)

        with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as f:
            f.write(b"mock model data")
            model_path = f.name

        try:
            model_id = registry.register_model(model_path, sample_model_metadata)

            # Verify model exists
            assert model_id in registry.models

            # Delete model
            success = registry.delete_model(model_id)

            assert success is True
            assert model_id not in registry.models
            assert model_id not in registry.metadata

        finally:
            if os.path.exists(model_path):
                os.unlink(model_path)

    def test_update_model_metadata(self, registry_config, sample_model_metadata):
        """Test updating model metadata."""
        registry = ModelRegistry(registry_config)

        with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as f:
            f.write(b"mock model data")
            model_path = f.name

        try:
            model_id = registry.register_model(model_path, sample_model_metadata)

            # Update metadata
            updated_metadata = {
                "description": "Updated forex prediction model",
                "metrics": {"accuracy": 0.90, "f1_score": 0.88},
                "tags": ["production", "updated"],
            }

            success = registry.update_model_metadata(model_id, updated_metadata)

            assert success is True

            # Verify updates
            stored_metadata = registry.metadata[model_id]
            assert stored_metadata.description == "Updated forex prediction model"
            assert stored_metadata.metrics["accuracy"] == 0.90
            assert "updated" in stored_metadata.tags

        finally:
            os.unlink(model_path)


class TestModelVersioning:
    """Test model versioning functionality."""

    @pytest.fixture
    def registry(self, registry_config):
        """Create registry for versioning tests."""
        return ModelRegistry(registry_config)

    def test_automatic_version_increment(self, registry):
        """Test automatic version incrementation."""
        base_metadata = ModelMetadata(
            name="test_model", version="1.0.0", model_type="random_forest"
        )

        with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as f:
            f.write(b"mock model data v1")
            model_path_v1 = f.name

        with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as f:
            f.write(b"mock model data v2")
            model_path_v2 = f.name

        try:
            # Register v1.0.0
            model_id_v1 = registry.register_model(model_path_v1, base_metadata)

            # Register next version (should auto-increment to v1.0.1)
            next_metadata = base_metadata.copy()
            next_metadata.version = None  # Let registry auto-assign

            model_id_v2 = registry.register_model_with_auto_version(
                model_path_v2, next_metadata
            )

            v2_metadata = registry.metadata[model_id_v2]
            assert v2_metadata.version == "1.0.1"

        finally:
            os.unlink(model_path_v1)
            os.unlink(model_path_v2)

    def test_semantic_versioning(self, registry):
        """Test semantic versioning rules."""
        versions = ["1.0.0", "1.0.1", "1.1.0", "2.0.0"]

        for i, version in enumerate(versions):
            metadata = ModelMetadata(
                name="versioned_model", version=version, model_type="random_forest"
            )

            with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as f:
                f.write(f"mock model data v{version}".encode())
                model_path = f.name

            try:
                registry.register_model(model_path, metadata)
            finally:
                os.unlink(model_path)

        # Get versions in order
        versions_list = registry.get_model_versions("versioned_model")

        assert len(versions_list) == 4
        # Should be sorted by version
        version_numbers = [v.version for v in versions_list]
        assert version_numbers == ["1.0.0", "1.0.1", "1.1.0", "2.0.0"]

    def test_version_comparison(self, registry):
        """Test version comparison functionality."""
        # Register multiple versions with different metrics
        versions_data = [
            ("1.0.0", {"accuracy": 0.80}),
            ("1.1.0", {"accuracy": 0.85}),
            ("2.0.0", {"accuracy": 0.82}),
        ]

        for version, metrics in versions_data:
            metadata = ModelMetadata(
                name="comparison_model",
                version=version,
                metrics=metrics,
                model_type="random_forest",
            )

            with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as f:
                f.write(f"mock model v{version}".encode())
                model_path = f.name

            try:
                registry.register_model(model_path, metadata)
            finally:
                os.unlink(model_path)

        # Compare versions
        comparison = registry.compare_model_versions(
            model_name="comparison_model",
            version1="1.0.0",
            version2="1.1.0",
            metric="accuracy",
        )

        assert comparison["version1_metric"] == 0.80
        assert comparison["version2_metric"] == 0.85
        assert comparison["improvement"] == 0.05
        assert comparison["improvement_percent"] == 6.25

    def test_version_rollback(self, registry):
        """Test rolling back to previous model version."""
        # Register versions
        versions = ["1.0.0", "1.1.0", "1.2.0"]

        for version in versions:
            metadata = ModelMetadata(
                name="rollback_model", version=version, model_type="random_forest"
            )

            with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as f:
                f.write(f"mock model v{version}".encode())
                model_path = f.name

            try:
                registry.register_model(model_path, metadata)
            finally:
                os.unlink(model_path)

        # Set current version to latest
        registry.set_current_version("rollback_model", "1.2.0")

        # Rollback to v1.0.0
        success = registry.rollback_version("rollback_model", "1.0.0")

        assert success is True

        current_version = registry.get_current_version("rollback_model")
        assert current_version == "1.0.0"


class TestCloudModelRegistry:
    """Test cloud model registry integration."""

    @pytest.fixture
    def cloud_config(self):
        """Create cloud registry configuration."""
        return RegistryConfig(
            enable_cloud_sync=True,
            cloud_provider="vertex_ai",
            project_id="test-project",
            location="us-central1",
        )

    @patch("fxml4.ml.vertex_ai.VertexAIModelRegistry")
    def test_cloud_registry_initialization(self, mock_vertex_registry, cloud_config):
        """Test cloud registry initialization."""
        mock_vertex_instance = MagicMock()
        mock_vertex_registry.return_value = mock_vertex_instance

        cloud_registry = CloudModelRegistry(cloud_config)

        assert cloud_registry.config == cloud_config
        assert cloud_registry.cloud_client == mock_vertex_instance
        mock_vertex_registry.assert_called_once()

    @patch("fxml4.ml.vertex_ai.VertexAIModelRegistry")
    def test_sync_model_to_cloud(self, mock_vertex_registry, cloud_config):
        """Test syncing local model to cloud registry."""
        mock_vertex_instance = MagicMock()
        mock_vertex_instance.register_model.return_value = "cloud-model-id-123"
        mock_vertex_registry.return_value = mock_vertex_instance

        cloud_registry = CloudModelRegistry(cloud_config)

        metadata = ModelMetadata(
            name="cloud_test_model",
            version="1.0.0",
            model_type="random_forest",
            metrics={"accuracy": 0.87},
        )

        with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as f:
            f.write(b"mock model for cloud")
            model_path = f.name

        try:
            cloud_model_id = cloud_registry.sync_to_cloud(model_path, metadata)

            assert cloud_model_id == "cloud-model-id-123"
            mock_vertex_instance.register_model.assert_called_once()

        finally:
            os.unlink(model_path)

    @patch("fxml4.ml.vertex_ai.VertexAIModelRegistry")
    def test_pull_model_from_cloud(self, mock_vertex_registry, cloud_config):
        """Test pulling model from cloud registry."""
        mock_vertex_instance = MagicMock()
        mock_model = MagicMock()
        mock_model.download.return_value = "local/path/model.pkl"
        mock_vertex_instance.get_model.return_value = mock_model
        mock_vertex_registry.return_value = mock_vertex_instance

        cloud_registry = CloudModelRegistry(cloud_config)

        local_path = cloud_registry.pull_from_cloud(
            cloud_model_id="cloud-model-123", local_path="models/"
        )

        assert local_path == "local/path/model.pkl"
        mock_vertex_instance.get_model.assert_called_once_with("cloud-model-123")

    @patch("ftml4.ml.vertex_ai.VertexAIModelRegistry")
    def test_bidirectional_sync(self, mock_vertex_registry, cloud_config):
        """Test bidirectional sync between local and cloud registries."""
        mock_vertex_instance = MagicMock()
        mock_vertex_instance.list_models.return_value = [
            MagicMock(display_name="cloud-model-1", version="1.0.0"),
            MagicMock(display_name="cloud-model-2", version="1.1.0"),
        ]
        mock_vertex_registry.return_value = mock_vertex_instance

        # Local registry with some models
        local_registry = ModelRegistry(
            RegistryConfig(registry_path=tempfile.mkdtemp(), enable_cloud_sync=False)
        )

        # Add local model
        local_metadata = ModelMetadata(
            name="local_model", version="1.0.0", model_type="random_forest"
        )

        with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as f:
            f.write(b"local model data")
            local_model_path = f.name

        try:
            local_registry.register_model(local_model_path, local_metadata)

            # Create cloud registry and sync
            cloud_registry = CloudModelRegistry(cloud_config)
            cloud_registry.local_registry = local_registry

            sync_result = cloud_registry.bidirectional_sync()

            assert sync_result["local_to_cloud_count"] >= 1
            assert sync_result["cloud_to_local_count"] >= 0

        finally:
            os.unlink(local_model_path)
            shutil.rmtree(local_registry.config.registry_path)


class TestModelRegistryPerformance:
    """Test model registry performance characteristics."""

    @pytest.fixture
    def registry(self, registry_config):
        """Create registry for performance tests."""
        return ModelRegistry(registry_config)

    def test_large_scale_model_registration(self, registry):
        """Test registering large number of models."""
        num_models = 100
        model_ids = []

        start_time = datetime.now()

        for i in range(num_models):
            metadata = ModelMetadata(
                name=f"model_{i}",
                version="1.0.0",
                model_type="random_forest",
                metrics={"accuracy": 0.8 + (i % 20) * 0.01},
            )

            with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as f:
                f.write(f"mock model {i}".encode())
                model_path = f.name

            try:
                model_id = registry.register_model(model_path, metadata)
                model_ids.append(model_id)
            finally:
                os.unlink(model_path)

        registration_time = (datetime.now() - start_time).total_seconds()

        # Should register 100 models in reasonable time
        assert len(model_ids) == num_models
        assert registration_time < 10.0  # Less than 10 seconds

        # Test search performance
        search_start = datetime.now()
        search_results = registry.search_models(
            criteria={"metrics.accuracy": {"$gt": 0.90}}
        )
        search_time = (datetime.now() - search_start).total_seconds()

        assert len(search_results) > 0
        assert search_time < 1.0  # Search should be fast

    def test_concurrent_model_operations(self, registry):
        """Test concurrent model operations."""
        import concurrent.futures
        import threading

        def register_model(model_index):
            metadata = ModelMetadata(
                name=f"concurrent_model_{model_index}",
                version="1.0.0",
                model_type="random_forest",
            )

            with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as f:
                f.write(f"concurrent model {model_index}".encode())
                model_path = f.name

            try:
                return registry.register_model(model_path, metadata)
            finally:
                os.unlink(model_path)

        # Register models concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(register_model, i) for i in range(20)]
            model_ids = [f.result() for f in concurrent.futures.as_completed(futures)]

        assert len(model_ids) == 20
        assert len(set(model_ids)) == 20  # All unique IDs

    def test_memory_usage_with_large_metadata(self, registry):
        """Test memory usage with large metadata objects."""
        # Create model with large metadata
        large_features = [f"feature_{i}" for i in range(1000)]
        large_hyperparameters = {f"param_{i}": i for i in range(500)}

        metadata = ModelMetadata(
            name="large_metadata_model",
            version="1.0.0",
            model_type="random_forest",
            features=large_features,
            hyperparameters=large_hyperparameters,
            description="x" * 10000,  # Large description
        )

        with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as f:
            f.write(b"model with large metadata")
            model_path = f.name

        try:
            model_id = registry.register_model(model_path, metadata)

            # Verify large metadata is stored correctly
            stored_metadata = registry.metadata[model_id]
            assert len(stored_metadata.features) == 1000
            assert len(stored_metadata.hyperparameters) == 500
            assert len(stored_metadata.description) == 10000

        finally:
            os.unlink(model_path)


class TestModelRegistryIntegration:
    """Test model registry integration scenarios."""

    @pytest.fixture
    def integrated_registry(self, registry_config):
        """Create registry with integration features enabled."""
        registry_config.enable_cloud_sync = True
        registry_config.enable_model_validation = True
        registry_config.auto_backup = True
        return ModelRegistry(registry_config)

    def test_complete_ml_lifecycle_workflow(self, integrated_registry):
        """Test complete ML model lifecycle through registry."""
        # Stage 1: Register initial model
        initial_metadata = ModelMetadata(
            name="lifecycle_model",
            version="1.0.0",
            model_type="random_forest",
            metrics={"accuracy": 0.80},
            tags=["development"],
        )

        with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as f:
            f.write(b"initial model")
            initial_path = f.name

        try:
            model_id_v1 = integrated_registry.register_model(
                initial_path, initial_metadata
            )

            # Stage 2: Deploy to production (update tags)
            integrated_registry.update_model_metadata(
                model_id_v1,
                {"tags": ["production"], "deployment_date": datetime.now().isoformat()},
            )

            # Stage 3: Register improved version
            improved_metadata = ModelMetadata(
                name="lifecycle_model",
                version="1.1.0",
                model_type="random_forest",
                metrics={"accuracy": 0.85},
                tags=["development"],
            )

            with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as f:
                f.write(b"improved model")
                improved_path = f.name

            try:
                model_id_v2 = integrated_registry.register_model(
                    improved_path, improved_metadata
                )

                # Stage 4: A/B test comparison
                comparison = integrated_registry.compare_model_versions(
                    "lifecycle_model", "1.0.0", "1.1.0", "accuracy"
                )

                assert comparison["improvement"] == 0.05

                # Stage 5: Promote new version to production
                if comparison["improvement"] > 0.03:  # 3% improvement threshold
                    integrated_registry.update_model_metadata(
                        model_id_v2,
                        {
                            "tags": ["production"],
                            "promotion_date": datetime.now().isoformat(),
                        },
                    )

                    # Retire old version
                    integrated_registry.update_model_metadata(
                        model_id_v1,
                        {
                            "tags": ["retired"],
                            "retirement_date": datetime.now().isoformat(),
                        },
                    )

                # Verify lifecycle state
                v1_metadata = integrated_registry.metadata[model_id_v1]
                v2_metadata = integrated_registry.metadata[model_id_v2]

                assert "retired" in v1_metadata.tags
                assert "production" in v2_metadata.tags

            finally:
                os.unlink(improved_path)

        finally:
            os.unlink(initial_path)

    def test_model_validation_pipeline(self, integrated_registry):
        """Test model validation during registration."""
        # Valid model
        valid_metadata = ModelMetadata(
            name="validated_model",
            version="1.0.0",
            model_type="random_forest",
            metrics={"accuracy": 0.85},
            features=["rsi", "macd"],
            hyperparameters={"n_estimators": 100},
        )

        with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as f:
            f.write(b"valid model data")
            valid_path = f.name

        try:
            # Should succeed with validation
            model_id = integrated_registry.register_model(valid_path, valid_metadata)
            assert model_id is not None

        finally:
            os.unlink(valid_path)

        # Invalid model (missing required metrics)
        invalid_metadata = ModelMetadata(
            name="invalid_model",
            version="1.0.0",
            model_type="random_forest",
            # Missing required metrics
        )

        with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as f:
            f.write(b"invalid model data")
            invalid_path = f.name

        try:
            # Should fail validation
            with pytest.raises(RegistryError, match="Model validation failed"):
                integrated_registry.register_model(invalid_path, invalid_metadata)

        finally:
            os.unlink(invalid_path)

    def test_automated_backup_and_recovery(self, integrated_registry):
        """Test automated backup and recovery functionality."""
        # Register model
        metadata = ModelMetadata(
            name="backup_test_model",
            version="1.0.0",
            model_type="random_forest",
            metrics={"accuracy": 0.87},
        )

        with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as f:
            f.write(b"model for backup test")
            model_path = f.name

        try:
            model_id = integrated_registry.register_model(model_path, metadata)

            # Trigger backup
            backup_path = integrated_registry.create_backup()

            assert os.path.exists(backup_path)

            # Simulate registry corruption
            integrated_registry.models.clear()
            integrated_registry.metadata.clear()

            # Restore from backup
            restored = integrated_registry.restore_from_backup(backup_path)

            assert restored is True
            assert model_id in integrated_registry.models
            assert integrated_registry.metadata[model_id].name == "backup_test_model"

        finally:
            os.unlink(model_path)

    def test_audit_trail_and_compliance(self, integrated_registry):
        """Test audit trail and compliance features."""
        # Register model with compliance metadata
        metadata = ModelMetadata(
            name="compliant_model",
            version="1.0.0",
            model_type="random_forest",
            metrics={"accuracy": 0.85},
            compliance_info={
                "data_governance": "GDPR_compliant",
                "model_explainability": "SHAP_enabled",
                "bias_testing": "completed",
                "security_scan": "passed",
            },
            audit_info={
                "reviewer": "ML_Team_Lead",
                "review_date": datetime.now().isoformat(),
                "approval_status": "approved",
            },
        )

        with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as f:
            f.write(b"compliant model")
            model_path = f.name

        try:
            model_id = integrated_registry.register_model(model_path, metadata)

            # Generate audit trail
            audit_trail = integrated_registry.get_audit_trail(model_id)

            assert len(audit_trail) > 0
            assert audit_trail[0]["action"] == "model_registered"
            assert "timestamp" in audit_trail[0]

            # Update model (should add to audit trail)
            integrated_registry.update_model_metadata(
                model_id, {"tags": ["production"]}
            )

            updated_audit_trail = integrated_registry.get_audit_trail(model_id)
            assert len(updated_audit_trail) > len(audit_trail)

        finally:
            os.unlink(model_path)
