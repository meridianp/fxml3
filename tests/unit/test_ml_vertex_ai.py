"""
Comprehensive retrospective test coverage for ML Vertex AI Integration.

This module provides comprehensive test coverage for the FXML4 Vertex AI integration,
which enables cloud-based model training, deployment, and inference through
Google Cloud Platform's Vertex AI service.

Following TDD principles with retrospective testing approach:
- Testing existing production Vertex AI functionality
- Ensuring comprehensive coverage of cloud ML workflows
- Validating model deployment, batch prediction, and monitoring
"""

import json
import os
import tempfile
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from unittest.mock import ANY, AsyncMock, MagicMock, call, patch

import numpy as np
import pandas as pd
import pytest

from fxml4.ml.vertex_ai import (
    ModelMetadata,
    VertexAIConfig,
    VertexAIModel,
    VertexAIModelRegistry,
    VertexAIPredictionService,
    VertexAITrainingJob,
    batch_predict,
    check_vertex_availability,
    create_vertex_client,
    deploy_model_to_endpoint,
)


class TestVertexAIAvailability:
    """Test Vertex AI availability and configuration."""

    def test_check_vertex_availability_success(self):
        """Test successful Vertex AI availability check."""
        with patch("fxml4.ml.vertex_ai.VERTEX_AVAILABLE", True):
            result = check_vertex_availability()
            assert result is True

    def test_check_vertex_availability_failure(self):
        """Test Vertex AI availability check when dependencies missing."""
        with patch("fxml4.ml.vertex_ai.VERTEX_AVAILABLE", False):
            result = check_vertex_availability()
            assert result is False

    @patch("fxml4.ml.vertex_ai.aiplatform.init")
    def test_create_vertex_client_success(self, mock_init):
        """Test successful Vertex AI client creation."""
        config = VertexAIConfig(
            project_id="test-project",
            location="us-central1",
            staging_bucket="gs://test-bucket",
        )

        client = create_vertex_client(config)

        mock_init.assert_called_once_with(
            project=config.project_id,
            location=config.location,
            staging_bucket=config.staging_bucket,
        )
        assert client is not None

    @patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": "env-project"})
    def test_create_vertex_client_from_env(self):
        """Test Vertex AI client creation from environment variables."""
        with patch("fxml4.ml.vertex_ai.aiplatform.init") as mock_init:
            config = VertexAIConfig()  # Should use env vars

            client = create_vertex_client(config)

            mock_init.assert_called()
            call_args = mock_init.call_args[1]
            assert call_args["project"] == "env-project"

    def test_vertex_config_validation(self):
        """Test Vertex AI configuration validation."""
        # Valid config
        config = VertexAIConfig(project_id="valid-project", location="us-central1")
        assert config.project_id == "valid-project"

        # Invalid project ID
        with pytest.raises(ValueError, match="Invalid project_id"):
            VertexAIConfig(project_id="", location="us-central1")

    def test_vertex_config_defaults(self):
        """Test Vertex AI configuration defaults."""
        config = VertexAIConfig(project_id="test-project")

        assert config.location == "us-central1"  # Default
        assert config.machine_type == "n1-standard-4"  # Default
        assert config.accelerator_type is None  # No GPU by default


class TestVertexAIModel:
    """Test Vertex AI model management functionality."""

    @pytest.fixture
    def vertex_config(self):
        """Create Vertex AI configuration for testing."""
        return VertexAIConfig(
            project_id="test-project",
            location="us-central1",
            staging_bucket="gs://test-bucket",
        )

    @pytest.fixture
    def sample_model_data(self):
        """Create sample model training data."""
        X = pd.DataFrame(
            {
                "feature_1": np.random.randn(1000),
                "feature_2": np.random.randn(1000),
                "feature_3": np.random.uniform(0, 1, 1000),
            }
        )
        y = pd.Series(np.random.randint(0, 3, 1000))
        return X, y

    def test_vertex_ai_model_initialization(self, vertex_config):
        """Test VertexAIModel initialization."""
        model = VertexAIModel(
            model_name="test-forex-model", config=vertex_config, model_type="sklearn"
        )

        assert model.model_name == "test-forex-model"
        assert model.config == vertex_config
        assert model.model_type == "sklearn"
        assert model.model_resource is None
        assert model.endpoint is None

    @patch("fxml4.ml.vertex_ai.aiplatform.Model")
    def test_upload_model_to_vertex(self, mock_model_class, vertex_config):
        """Test uploading model to Vertex AI."""
        mock_model = MagicMock()
        mock_model.resource_name = "projects/test/locations/us-central1/models/12345"
        mock_model_class.upload.return_value = mock_model

        vertex_model = VertexAIModel("test-model", vertex_config)

        with tempfile.TemporaryDirectory() as temp_dir:
            model_path = os.path.join(temp_dir, "model.pkl")

            # Create dummy model file
            with open(model_path, "w") as f:
                f.write("dummy model")

            result = vertex_model.upload_model(
                model_path=model_path,
                display_name="Test Forex Model",
                description="Test model for forex prediction",
            )

            assert result is True
            assert vertex_model.model_resource == mock_model
            mock_model_class.upload.assert_called_once()

    @patch("fxml4.ml.vertex_ai.aiplatform.Model")
    def test_upload_model_failure(self, mock_model_class, vertex_config):
        """Test model upload failure handling."""
        mock_model_class.upload.side_effect = Exception("Upload failed")

        vertex_model = VertexAIModel("test-model", vertex_config)

        result = vertex_model.upload_model(
            model_path="nonexistent/path", display_name="Test Model"
        )

        assert result is False
        assert vertex_model.model_resource is None

    @patch("fxml4.ml.vertex_ai.aiplatform.Endpoint")
    def test_deploy_model_to_endpoint(self, mock_endpoint_class, vertex_config):
        """Test deploying model to Vertex AI endpoint."""
        # Mock model
        mock_model = MagicMock()
        mock_model.resource_name = "projects/test/locations/us-central1/models/12345"

        # Mock endpoint
        mock_endpoint = MagicMock()
        mock_endpoint.resource_name = (
            "projects/test/locations/us-central1/endpoints/67890"
        )
        mock_endpoint_class.create.return_value = mock_endpoint
        mock_endpoint.deploy.return_value = mock_endpoint

        vertex_model = VertexAIModel("test-model", vertex_config)
        vertex_model.model_resource = mock_model

        result = vertex_model.deploy_to_endpoint(
            endpoint_display_name="Test Endpoint",
            machine_type="n1-standard-2",
            min_replica_count=1,
            max_replica_count=3,
        )

        assert result is True
        assert vertex_model.endpoint == mock_endpoint
        mock_endpoint_class.create.assert_called_once()
        mock_endpoint.deploy.assert_called_once()

    def test_predict_with_endpoint(self, vertex_config):
        """Test prediction using deployed endpoint."""
        # Mock endpoint
        mock_endpoint = MagicMock()
        mock_predictions = [
            {"predictions": [0.1, 0.7, 0.2]},
            {"predictions": [0.8, 0.1, 0.1]},
        ]
        mock_endpoint.predict.return_value = mock_predictions

        vertex_model = VertexAIModel("test-model", vertex_config)
        vertex_model.endpoint = mock_endpoint

        # Sample prediction data
        X = pd.DataFrame(
            {"feature_1": [1.5, -0.5], "feature_2": [2.0, 1.0], "feature_3": [0.3, 0.8]}
        )

        predictions = vertex_model.predict(X)

        assert len(predictions) == 2
        assert len(predictions[0]) == 3  # 3 classes
        mock_endpoint.predict.assert_called_once()

    def test_predict_without_endpoint(self, vertex_config):
        """Test prediction failure when no endpoint deployed."""
        vertex_model = VertexAIModel("test-model", vertex_config)

        X = pd.DataFrame({"feature_1": [1.0], "feature_2": [2.0]})

        with pytest.raises(ValueError, match="No endpoint deployed"):
            vertex_model.predict(X)

    @patch("fxml4.ml.vertex_ai.aiplatform.BatchPredictionJob")
    def test_batch_predict(self, mock_batch_job_class, vertex_config):
        """Test batch prediction functionality."""
        mock_job = MagicMock()
        mock_job.resource_name = (
            "projects/test/locations/us-central1/batchPredictionJobs/12345"
        )
        mock_job.state = "JOB_STATE_SUCCEEDED"
        mock_batch_job_class.create.return_value = mock_job

        mock_model = MagicMock()
        mock_model.resource_name = "projects/test/locations/us-central1/models/12345"

        vertex_model = VertexAIModel("test-model", vertex_config)
        vertex_model.model_resource = mock_model

        result = vertex_model.batch_predict(
            input_uri="gs://bucket/input.csv",
            output_uri="gs://bucket/output/",
            instances_format="csv",
            predictions_format="jsonl",
        )

        assert result == mock_job
        mock_batch_job_class.create.assert_called_once()

    def test_get_model_metadata(self, vertex_config):
        """Test retrieving model metadata."""
        mock_model = MagicMock()
        mock_model.display_name = "Test Forex Model"
        mock_model.description = "Forex prediction model"
        mock_model.create_time = datetime.now()
        mock_model.update_time = datetime.now()
        mock_model.labels = {"environment": "test", "version": "1.0"}

        vertex_model = VertexAIModel("test-model", vertex_config)
        vertex_model.model_resource = mock_model

        metadata = vertex_model.get_metadata()

        assert metadata["display_name"] == "Test Forex Model"
        assert metadata["description"] == "Forex prediction model"
        assert "create_time" in metadata
        assert "labels" in metadata


class TestVertexAITrainingJob:
    """Test Vertex AI custom training job functionality."""

    @pytest.fixture
    def training_config(self):
        """Create training configuration for testing."""
        return {
            "model_type": "random_forest",
            "hyperparameters": {"n_estimators": 100, "max_depth": 10},
            "training_data_uri": "gs://bucket/training_data.csv",
            "validation_data_uri": "gs://bucket/validation_data.csv",
        }

    @patch("fxml4.ml.vertex_ai.CustomTrainingJob")
    def test_create_training_job(self, mock_training_job_class, training_config):
        """Test creating custom training job on Vertex AI."""
        mock_job = MagicMock()
        mock_job.resource_name = (
            "projects/test/locations/us-central1/trainingPipelines/12345"
        )
        mock_training_job_class.return_value = mock_job

        training_job = VertexAITrainingJob(
            display_name="Test Training Job",
            script_path="train.py",
            container_uri="gcr.io/cloud-aiplatform/training/sklearn-cpu.0-23:latest",
            requirements=["scikit-learn==1.0.2", "pandas==1.3.3"],
        )

        job = training_job.create(
            args=[
                f"--model-type={training_config['model_type']}",
                f"--training-data={training_config['training_data_uri']}",
            ],
            replica_count=1,
            machine_type="n1-standard-4",
            accelerator_type="NVIDIA_TESLA_T4",
            accelerator_count=1,
        )

        assert job == mock_job
        mock_training_job_class.assert_called_once()

    @patch("fxml4.ml.vertex_ai.CustomTrainingJob")
    def test_submit_training_job(self, mock_training_job_class, training_config):
        """Test submitting and monitoring training job."""
        mock_job = MagicMock()
        mock_job.run.return_value = mock_job
        mock_job.state = "PIPELINE_STATE_SUCCEEDED"
        mock_job.resource_name = (
            "projects/test/locations/us-central1/trainingPipelines/12345"
        )
        mock_training_job_class.return_value = mock_job

        training_job = VertexAITrainingJob(
            display_name="Test Training Job", script_path="train.py"
        )

        result = training_job.submit_and_wait(args=["--epochs=10"], timeout=3600)

        assert result == mock_job
        mock_job.run.assert_called_once()

    @patch("fxml4.ml.vertex_ai.storage.Client")
    def test_upload_training_script(self, mock_storage_client):
        """Test uploading training script to Google Cloud Storage."""
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_blob = MagicMock()

        mock_storage_client.return_value = mock_client
        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob

        training_job = VertexAITrainingJob(
            display_name="Test Training Job", script_path="local/train.py"
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("# Training script")
            script_path = f.name

        try:
            gcs_path = training_job.upload_script(
                script_path, "gs://test-bucket/scripts/"
            )

            assert gcs_path.startswith("gs://test-bucket/scripts/")
            mock_blob.upload_from_filename.assert_called_once()
        finally:
            os.unlink(script_path)

    def test_training_job_status_monitoring(self):
        """Test monitoring training job status."""
        mock_job = MagicMock()
        mock_job.state = "PIPELINE_STATE_RUNNING"

        training_job = VertexAITrainingJob(display_name="Test Job")
        training_job.job = mock_job

        status = training_job.get_status()

        assert status == "PIPELINE_STATE_RUNNING"

        # Test completion check
        assert training_job.is_complete() is False

        mock_job.state = "PIPELINE_STATE_SUCCEEDED"
        assert training_job.is_complete() is True

    def test_training_job_logs_retrieval(self):
        """Test retrieving training job logs."""
        mock_job = MagicMock()
        mock_job.resource_name = (
            "projects/test/locations/us-central1/trainingPipelines/12345"
        )

        training_job = VertexAITrainingJob(display_name="Test Job")
        training_job.job = mock_job

        with patch("fxml4.ml.vertex_ai.logging.Client") as mock_logging_client:
            mock_client = MagicMock()
            mock_entries = [
                MagicMock(payload="Training started"),
                MagicMock(payload="Epoch 1/10 completed"),
                MagicMock(payload="Training completed"),
            ]
            mock_client.list_entries.return_value = mock_entries
            mock_logging_client.return_value = mock_client

            logs = training_job.get_logs()

            assert len(logs) == 3
            assert "Training started" in logs[0]


class TestVertexAIPredictionService:
    """Test Vertex AI prediction service functionality."""

    @pytest.fixture
    def prediction_service(self):
        """Create prediction service for testing."""
        config = VertexAIConfig(project_id="test-project", location="us-central1")
        return VertexAIPredictionService(config)

    def test_prediction_service_initialization(self, prediction_service):
        """Test prediction service initialization."""
        assert prediction_service.config.project_id == "test-project"
        assert prediction_service.endpoints == {}
        assert prediction_service.models == {}

    @patch("fxml4.ml.vertex_ai.aiplatform.Endpoint")
    def test_load_endpoint(self, mock_endpoint_class, prediction_service):
        """Test loading existing endpoint."""
        mock_endpoint = MagicMock()
        mock_endpoint.resource_name = (
            "projects/test/locations/us-central1/endpoints/12345"
        )
        mock_endpoint.display_name = "forex-model-endpoint"
        mock_endpoint_class.return_value = mock_endpoint

        endpoint_id = "12345"
        endpoint = prediction_service.load_endpoint(endpoint_id)

        assert endpoint == mock_endpoint
        assert prediction_service.endpoints[endpoint_id] == mock_endpoint

    def test_predict_with_loaded_endpoint(self, prediction_service):
        """Test making predictions with loaded endpoint."""
        # Mock endpoint
        mock_endpoint = MagicMock()
        mock_predictions = [
            {"predictions": [0.2, 0.6, 0.2]},
            {"predictions": [0.7, 0.2, 0.1]},
        ]
        mock_endpoint.predict.return_value = mock_predictions

        prediction_service.endpoints["test-endpoint"] = mock_endpoint

        instances = [
            {"feature_1": 1.5, "feature_2": 2.0},
            {"feature_1": -0.5, "feature_2": 1.0},
        ]

        predictions = prediction_service.predict("test-endpoint", instances)

        assert len(predictions) == 2
        mock_endpoint.predict.assert_called_once_with(instances=instances)

    def test_batch_predict_with_service(self, prediction_service):
        """Test batch prediction through service."""
        mock_model = MagicMock()
        mock_job = MagicMock()
        mock_job.resource_name = "projects/test/batchPredictionJobs/12345"

        prediction_service.models["test-model"] = mock_model

        with patch(
            "fxml4.ml.vertex_ai.aiplatform.BatchPredictionJob"
        ) as mock_batch_job:
            mock_batch_job.create.return_value = mock_job

            job = prediction_service.batch_predict(
                model_name="test-model",
                input_uri="gs://bucket/input.csv",
                output_uri="gs://bucket/output/",
            )

            assert job == mock_job
            mock_batch_job.create.assert_called_once()

    def test_prediction_monitoring(self, prediction_service):
        """Test prediction request monitoring."""
        mock_endpoint = MagicMock()
        prediction_service.endpoints["monitored-endpoint"] = mock_endpoint

        # Enable monitoring
        prediction_service.enable_monitoring("monitored-endpoint")

        # Mock prediction with monitoring
        mock_endpoint.predict.return_value = [{"predictions": [0.8, 0.1, 0.1]}]

        instances = [{"feature_1": 1.0, "feature_2": 2.0}]
        predictions = prediction_service.predict("monitored-endpoint", instances)

        # Should track prediction metrics
        assert "monitored-endpoint" in prediction_service.prediction_metrics
        metrics = prediction_service.prediction_metrics["monitored-endpoint"]
        assert metrics["request_count"] == 1
        assert "latency" in metrics


class TestVertexAIModelRegistry:
    """Test Vertex AI model registry functionality."""

    @pytest.fixture
    def model_registry(self):
        """Create model registry for testing."""
        config = VertexAIConfig(project_id="test-project", location="us-central1")
        return VertexAIModelRegistry(config)

    @patch("fxml4.ml.vertex_ai.aiplatform.Model")
    def test_register_model(self, mock_model_class, model_registry):
        """Test registering model in Vertex AI registry."""
        mock_model = MagicMock()
        mock_model.resource_name = "projects/test/locations/us-central1/models/12345"
        mock_model.display_name = "forex-model-v1"
        mock_model_class.upload.return_value = mock_model

        metadata = ModelMetadata(
            name="forex-model",
            version="1.0",
            description="Forex prediction model",
            metrics={"accuracy": 0.85, "precision": 0.82},
            features=["rsi", "macd", "bollinger"],
            training_data_version="v2024.1",
        )

        model_id = model_registry.register_model(
            model_path="models/forex_model.pkl", metadata=metadata
        )

        assert model_id is not None
        assert model_registry.models[model_id] == mock_model
        mock_model_class.upload.assert_called_once()

    def test_list_models(self, model_registry):
        """Test listing models in registry."""
        # Mock models
        mock_model1 = MagicMock()
        mock_model1.display_name = "forex-model-v1"
        mock_model1.create_time = datetime.now()

        mock_model2 = MagicMock()
        mock_model2.display_name = "forex-model-v2"
        mock_model2.create_time = datetime.now()

        model_registry.models = {"model-1": mock_model1, "model-2": mock_model2}

        models = model_registry.list_models()

        assert len(models) == 2
        assert "forex-model-v1" in [m.display_name for m in models]
        assert "forex-model-v2" in [m.display_name for m in models]

    def test_get_model_by_name(self, model_registry):
        """Test retrieving model by name."""
        mock_model = MagicMock()
        mock_model.display_name = "forex-model-v1"

        model_registry.models = {"model-1": mock_model}

        retrieved_model = model_registry.get_model("forex-model-v1")

        assert retrieved_model == mock_model

    def test_delete_model(self, model_registry):
        """Test deleting model from registry."""
        mock_model = MagicMock()
        mock_model.display_name = "forex-model-v1"

        model_registry.models = {"model-1": mock_model}

        success = model_registry.delete_model("model-1")

        assert success is True
        assert "model-1" not in model_registry.models
        mock_model.delete.assert_called_once()

    def test_model_versioning(self, model_registry):
        """Test model versioning functionality."""
        # Register multiple versions
        versions = ["1.0", "1.1", "2.0"]

        for version in versions:
            mock_model = MagicMock()
            mock_model.display_name = f"forex-model-v{version}"
            mock_model.labels = {"version": version}

            model_id = f"model-v{version.replace('.', '-')}"
            model_registry.models[model_id] = mock_model

        # Get latest version
        latest = model_registry.get_latest_version("forex-model")

        assert latest is not None
        assert latest.labels["version"] == "2.0"

    def test_model_metadata_tracking(self, model_registry):
        """Test tracking of model metadata."""
        metadata = ModelMetadata(
            name="test-model",
            version="1.0",
            metrics={"accuracy": 0.88, "f1_score": 0.85},
            hyperparameters={"n_estimators": 100, "max_depth": 10},
            training_duration_minutes=45,
            data_version="2024.1",
        )

        model_registry.track_metadata("model-1", metadata)

        retrieved_metadata = model_registry.get_metadata("model-1")

        assert retrieved_metadata.name == "test-model"
        assert retrieved_metadata.metrics["accuracy"] == 0.88
        assert retrieved_metadata.training_duration_minutes == 45


class TestVertexAIIntegration:
    """Test complete Vertex AI integration workflows."""

    @pytest.fixture
    def integration_config(self):
        """Create configuration for integration testing."""
        return VertexAIConfig(
            project_id="test-project",
            location="us-central1",
            staging_bucket="gs://test-staging-bucket",
        )

    def test_complete_model_deployment_workflow(self, integration_config):
        """Test complete model deployment workflow."""
        with (
            patch("fxml4.ml.vertex_ai.aiplatform.Model") as mock_model,
            patch("fxml4.ml.vertex_ai.aiplatform.Endpoint") as mock_endpoint,
        ):

            # Mock model upload
            mock_model_instance = MagicMock()
            mock_model_instance.resource_name = "projects/test/models/12345"
            mock_model.upload.return_value = mock_model_instance

            # Mock endpoint deployment
            mock_endpoint_instance = MagicMock()
            mock_endpoint_instance.resource_name = "projects/test/endpoints/67890"
            mock_endpoint.create.return_value = mock_endpoint_instance

            # Create and deploy model
            vertex_model = VertexAIModel("forex-model", integration_config)

            # Upload model
            upload_success = vertex_model.upload_model(
                model_path="models/forex_model.pkl", display_name="Forex Trading Model"
            )

            assert upload_success is True

            # Deploy to endpoint
            deploy_success = vertex_model.deploy_to_endpoint(
                endpoint_display_name="Forex Prediction Endpoint",
                machine_type="n1-standard-2",
            )

            assert deploy_success is True
            assert vertex_model.endpoint is not None

    def test_model_training_and_deployment_pipeline(self, integration_config):
        """Test complete training and deployment pipeline."""
        with (
            patch("fxml4.ml.vertex_ai.CustomTrainingJob") as mock_training,
            patch("fxml4.ml.vertex_ai.aiplatform.Model") as mock_model,
        ):

            # Mock training job
            mock_job = MagicMock()
            mock_job.state = "PIPELINE_STATE_SUCCEEDED"
            mock_job.resource_name = "projects/test/trainingPipelines/12345"
            mock_training.return_value = mock_job
            mock_job.run.return_value = mock_job

            # Mock model registration
            mock_model_instance = MagicMock()
            mock_model_instance.resource_name = "projects/test/models/67890"
            mock_model.upload.return_value = mock_model_instance

            # Create training job
            training_job = VertexAITrainingJob(
                display_name="Forex Model Training", script_path="training/train.py"
            )

            # Submit training
            job_result = training_job.submit_and_wait(
                args=["--epochs=10", "--model-type=random_forest"]
            )

            assert job_result.state == "PIPELINE_STATE_SUCCEEDED"

            # Register trained model
            vertex_model = VertexAIModel("trained-forex-model", integration_config)

            upload_success = vertex_model.upload_model(
                model_path="gs://bucket/trained_model/",
                display_name="Trained Forex Model",
            )

            assert upload_success is True

    def test_batch_prediction_workflow(self, integration_config):
        """Test batch prediction workflow."""
        with patch(
            "fxml4.ml.vertex_ai.aiplatform.BatchPredictionJob"
        ) as mock_batch_job:

            mock_job = MagicMock()
            mock_job.state = "JOB_STATE_SUCCEEDED"
            mock_job.resource_name = "projects/test/batchPredictionJobs/12345"
            mock_batch_job.create.return_value = mock_job

            # Create model and submit batch prediction
            vertex_model = VertexAIModel("forex-model", integration_config)

            # Mock model resource
            mock_model_resource = MagicMock()
            mock_model_resource.resource_name = "projects/test/models/67890"
            vertex_model.model_resource = mock_model_resource

            batch_job = vertex_model.batch_predict(
                input_uri="gs://bucket/prediction_data.csv",
                output_uri="gs://bucket/predictions/",
                instances_format="csv",
                predictions_format="jsonl",
            )

            assert batch_job.state == "JOB_STATE_SUCCEEDED"
            mock_batch_job.create.assert_called_once()

    def test_model_monitoring_and_maintenance(self, integration_config):
        """Test model monitoring and maintenance workflows."""
        # Mock model with performance degradation
        mock_model = MagicMock()
        mock_model.resource_name = "projects/test/models/12345"

        vertex_model = VertexAIModel("monitored-model", integration_config)
        vertex_model.model_resource = mock_model

        # Simulate performance monitoring
        performance_metrics = {
            "accuracy": 0.75,  # Degraded from initial 0.85
            "precision": 0.72,
            "recall": 0.78,
            "prediction_latency_ms": 150,
        }

        # Check if retraining is needed
        needs_retraining = vertex_model.check_performance_degradation(
            current_metrics=performance_metrics, threshold_accuracy=0.80
        )

        assert needs_retraining is True

        # Test model lifecycle management
        lifecycle_status = vertex_model.get_lifecycle_status()

        assert lifecycle_status["needs_attention"] is True
        assert "performance_degradation" in lifecycle_status["issues"]

    def test_error_handling_and_recovery(self, integration_config):
        """Test error handling and recovery mechanisms."""
        vertex_model = VertexAIModel("error-test-model", integration_config)

        # Test upload failure recovery
        with patch("fxml4.ml.vertex_ai.aiplatform.Model") as mock_model:
            mock_model.upload.side_effect = Exception("Network error")

            # Should handle error gracefully
            result = vertex_model.upload_model("model.pkl", "Test Model")
            assert result is False

            # Test retry mechanism
            mock_model.upload.side_effect = None
            mock_model.upload.return_value = MagicMock()

            result = vertex_model.upload_model("model.pkl", "Test Model", max_retries=3)
            assert result is True

    def test_cost_optimization_features(self, integration_config):
        """Test cost optimization features."""
        vertex_model = VertexAIModel("cost-optimized-model", integration_config)

        # Test auto-scaling configuration
        scaling_config = vertex_model.configure_auto_scaling(
            min_replicas=1, max_replicas=10, target_cpu_utilization=70
        )

        assert scaling_config["min_replicas"] == 1
        assert scaling_config["max_replicas"] == 10
        assert scaling_config["target_cpu_utilization"] == 70

        # Test spot instance usage for training
        training_job = VertexAITrainingJob(
            display_name="Cost Optimized Training", use_spot_instances=True
        )

        cost_savings = training_job.estimate_cost_savings()
        assert cost_savings["spot_discount_percent"] > 0
