"""
Google Vertex AI Integration for FXML4 ML Pipeline

This module enables seamless integration with Google Vertex AI for:
1. Model training on scalable cloud infrastructure
2. Model registry with versioning
3. Online prediction endpoints
4. Batch prediction jobs
5. Cloud model performance monitoring

The module wraps the google-cloud-aiplatform SDK to provide a consistent
interface that aligns with the existing FXML4 ML training pipeline.
"""

import json
import logging
import os
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Google Cloud imports
try:
    from google.cloud import aiplatform, storage
    from google.cloud.aiplatform import model_registry as gcp_model_registry
    from google.cloud.aiplatform.training_jobs import CustomTrainingJob

    VERTEX_AVAILABLE = True
except ImportError:
    VERTEX_AVAILABLE = False
    gcp_model_registry = None

# FXML4 imports
from ml.models import ClassicMLModel, EnsembleModel

logger = logging.getLogger(__name__)


def check_vertex_availability():
    """Check if Vertex AI dependencies are available and configured."""
    if not VERTEX_AVAILABLE:
        logger.error(
            "Google Cloud AI Platform package not installed. Run: pip install google-cloud-aiplatform"
        )
        return False

    # Check for GCP credentials
    if not any(
        env_var in os.environ
        for env_var in [
            "GOOGLE_APPLICATION_CREDENTIALS",
            "GCP_PROJECT",
            "GOOGLE_CLOUD_PROJECT",
        ]
    ):
        logger.error("Google Cloud credentials not found in environment variables")
        return False

    return True


def get_default_project_id():
    """Get the default GCP project ID from environment variables."""
    # Check environment variables in order of preference
    for env_var in ["GCP_PROJECT", "GOOGLE_CLOUD_PROJECT", "GCLOUD_PROJECT"]:
        if env_var in os.environ:
            return os.environ[env_var]

    # If we're running on GCP, use the metadata server
    try:
        import requests

        metadata_url = (
            "http://metadata.google.internal/computeMetadata/v1/project/project-id"
        )
        project_id = requests.get(
            metadata_url, headers={"Metadata-Flavor": "Google"}, timeout=2
        ).text
        return project_id
    except:
        pass

    # Default fallback
    return "fxml4"


class VertexAIModel:
    """Wrapper for Vertex AI Model Registry integration with FXML4 models."""

    def __init__(
        self,
        project_id: Optional[str] = None,
        location: str = "us-central1",
        staging_bucket: Optional[str] = None,
        model_registry_name: str = "fxml4-model-registry",
        initialize: bool = True,
    ):
        """
        Initialize Vertex AI integration.

        Args:
            project_id: Google Cloud project ID (default: from environment)
            location: Google Cloud region
            staging_bucket: GCS bucket for staging model artifacts
            model_registry_name: Name of the model registry
            initialize: Whether to initialize Vertex AI client
        """
        # Get project ID from environment if not provided
        self.project_id = project_id or get_default_project_id()
        self.location = location
        self.model_registry_name = model_registry_name

        # Set up staging bucket
        if staging_bucket:
            self.staging_bucket = staging_bucket
        else:
            self.staging_bucket = f"gs://fxml4-models"

        # Initialize Vertex AI client
        if initialize and check_vertex_availability():
            aiplatform.init(
                project=self.project_id,
                location=location,
                staging_bucket=self.staging_bucket,
            )

            # Check if model registry exists, if not create it
            try:
                self._get_or_create_registry()
            except Exception as e:
                logger.error(f"Failed to initialize model registry: {str(e)}")

    def _get_or_create_registry(self):
        """Get or create the model registry."""
        if not VERTEX_AVAILABLE or gcp_model_registry is None:
            raise ImportError("Google Cloud AI Platform not available")

        try:
            registry = gcp_model_registry.ModelRegistry.get_model_registry(
                model_registry_name=self.model_registry_name,
                project=self.project_id,
                location=self.location,
            )
            logger.info(f"Using existing model registry: {self.model_registry_name}")
            return registry
        except Exception:
            # Registry doesn't exist, create it
            logger.info(f"Creating new model registry: {self.model_registry_name}")
            return model_registry.ModelRegistry.create(
                model_registry_name=self.model_registry_name,
                project=self.project_id,
                location=self.location,
            )

    def _upload_model_artifacts(
        self, model: Union[ClassicMLModel, EnsembleModel], prefix: str = "models"
    ) -> str:
        """
        Upload model artifacts to GCS.

        Args:
            model: FXML4 model to upload
            prefix: GCS path prefix

        Returns:
            GCS URI to the model directory
        """
        # Create temporary directory for model artifacts
        with tempfile.TemporaryDirectory() as temp_dir:
            # Save model locally
            model.save(temp_dir)

            # Generate GCS path
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            model_name = model.name.replace(" ", "_").lower()
            model_id = str(uuid.uuid4())[:8]
            gcs_dir = f"{prefix}/{model_name}/{timestamp}_{model_id}"
            gcs_uri = f"{self.staging_bucket}/{gcs_dir}"

            # Upload files to GCS
            storage_client = storage.Client(project=self.project_id)
            bucket_name = self.staging_bucket.replace("gs://", "").split("/")[0]
            bucket = storage_client.bucket(bucket_name)

            # Upload all files in the temp directory
            local_dir = Path(temp_dir)
            for local_file in local_dir.glob("*"):
                if local_file.is_file():
                    blob_path = f"{gcs_dir}/{local_file.name}"
                    blob = bucket.blob(blob_path)
                    blob.upload_from_filename(str(local_file))
                    logger.info(f"Uploaded {local_file.name} to {blob_path}")

            return gcs_uri

    def register_model(
        self,
        model: Union[ClassicMLModel, EnsembleModel],
        version: Optional[str] = None,
        labels: Optional[Dict[str, str]] = None,
        description: str = "",
    ) -> Dict[str, Any]:
        """
        Register a FXML4 model in Vertex AI Model Registry.

        Args:
            model: FXML4 model to register
            version: Model version (if None, generated from timestamp)
            labels: Labels to apply to the model
            description: Model description

        Returns:
            Dictionary with model registration information
        """
        if not check_vertex_availability():
            raise ImportError(
                "Vertex AI not available. Please install required packages."
            )

        # Generate version if not provided
        if version is None:
            version = datetime.now().strftime("v%Y%m%d_%H%M%S")

        # Upload model artifacts to GCS
        artifact_uri = self._upload_model_artifacts(model)

        # Create model metadata
        metadata = {
            "framework": "sklearn" if model.model_type != "ensemble" else "custom",
            "framework_version": "1.0.0",  # Can be dynamically determined
            "algorithm": model.model_type,
            "metrics": model.metadata.get("evaluation_metrics", {}),
            "parameters": model.model_params if hasattr(model, "model_params") else {},
            "created_at": datetime.now().isoformat(),
            "fxml4_version": "0.1.0",  # Should come from package version
        }

        # Create display name
        display_name = f"fxml4_{model.name}"

        # Set up default labels if none provided
        if labels is None:
            labels = {"model_type": model.model_type, "environment": "development"}

        # Register model in Vertex AI
        try:
            registry = self._get_or_create_registry()
            registered_model = registry.register_model(
                model_id=model.name,
                version_id=version,
                artifact_uri=artifact_uri,
                serving_container_image_uri="us-docker.pkg.dev/vertex-ai/prediction/sklearn-cpu.1-0:latest",
                display_name=display_name,
                description=description or f"FXML4 {model.model_type} model",
                metadata=metadata,
                labels=labels,
            )

            # Return registration info
            result = {
                "model_id": model.name,
                "version": version,
                "vertex_model_id": registered_model.name,
                "artifact_uri": artifact_uri,
                "registration_time": datetime.now().isoformat(),
                "status": "registered",
            }

            logger.info(
                f"Successfully registered model {model.name} as {version} in Vertex AI"
            )
            return result

        except Exception as e:
            logger.error(f"Failed to register model in Vertex AI: {str(e)}")
            raise

    def list_models(self, filter_str: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List models in the Vertex AI Model Registry.

        Args:
            filter_str: Filter string for models

        Returns:
            List of models with metadata
        """
        if not check_vertex_availability():
            raise ImportError(
                "Vertex AI not available. Please install required packages."
            )

        try:
            registry = self._get_or_create_registry()
            models = registry.list_model_versions(filter=filter_str)

            result = []
            for model in models:
                model_dict = {
                    "id": model.resource_name,
                    "name": model.display_name,
                    "version": model.version_id,
                    "create_time": model.create_time.isoformat(),
                    "update_time": model.update_time.isoformat(),
                    "metadata": model.metadata,
                    "artifact_uri": model.artifact_uri,
                }
                result.append(model_dict)

            return result
        except Exception as e:
            logger.error(f"Failed to list models: {str(e)}")
            raise

    def load_model(
        self, model_id: str, version: Optional[str] = None
    ) -> Union[ClassicMLModel, EnsembleModel]:
        """
        Load a model from Vertex AI Model Registry.

        Args:
            model_id: Model ID
            version: Model version (if None, uses latest)

        Returns:
            Loaded FXML4 model
        """
        if not check_vertex_availability():
            raise ImportError(
                "Vertex AI not available. Please install required packages."
            )

        try:
            registry = self._get_or_create_registry()

            # Get model version
            if version:
                model_version = registry.get_model_version(
                    model_id=model_id, version_id=version
                )
            else:
                # Get the latest version
                versions = registry.list_model_versions(
                    model_id=model_id, order_by="update_time desc", limit=1
                )
                if not versions:
                    raise ValueError(f"No versions found for model {model_id}")
                model_version = versions[0]

            # Download model from GCS
            with tempfile.TemporaryDirectory() as temp_dir:
                artifact_uri = model_version.artifact_uri
                if artifact_uri.startswith("gs://"):
                    # Parse GCS URI
                    bucket_name = artifact_uri.replace("gs://", "").split("/")[0]
                    prefix = "/".join(artifact_uri.replace("gs://", "").split("/")[1:])

                    # Download files
                    storage_client = storage.Client(project=self.project_id)
                    bucket = storage_client.bucket(bucket_name)
                    blobs = bucket.list_blobs(prefix=prefix)

                    for blob in blobs:
                        # Get the filename only
                        filename = os.path.basename(blob.name)
                        if filename:  # Skip directories
                            local_path = os.path.join(temp_dir, filename)
                            blob.download_to_filename(local_path)

                    # Determine model type from metadata
                    metadata_files = [
                        f for f in os.listdir(temp_dir) if f.endswith("_metadata.json")
                    ]
                    if not metadata_files:
                        raise ValueError("No metadata file found in model artifacts")

                    # Load model
                    model_name = metadata_files[0].replace("_metadata.json", "")

                    # Check if it's an ensemble model
                    with open(os.path.join(temp_dir, metadata_files[0]), "r") as f:
                        metadata = json.load(f)

                    if metadata.get("model_type") == "ensemble":
                        # For ensemble models, we need a special loading process
                        # This is simplified here - would need expansion for full functionality
                        raise NotImplementedError(
                            "Loading ensemble models not yet implemented"
                        )
                    else:
                        model = ClassicMLModel.load(model_name, temp_dir)

                    logger.info(
                        f"Successfully loaded model {model_id} version {version or 'latest'}"
                    )
                    return model
                else:
                    raise ValueError(f"Unsupported artifact URI: {artifact_uri}")

        except Exception as e:
            logger.error(f"Failed to load model: {str(e)}")
            raise

    def deploy_model(
        self,
        model_id: str,
        version: Optional[str] = None,
        machine_type: str = "n1-standard-2",
        min_replicas: int = 1,
        max_replicas: int = 1,
    ) -> Dict[str, Any]:
        """
        Deploy a model to a Vertex AI endpoint.

        Args:
            model_id: Model ID
            version: Model version (if None, uses latest)
            machine_type: Machine type for deployment
            min_replicas: Minimum number of replicas
            max_replicas: Maximum number of replicas

        Returns:
            Dictionary with deployment information
        """
        if not check_vertex_availability():
            raise ImportError(
                "Vertex AI not available. Please install required packages."
            )

        try:
            registry = self._get_or_create_registry()

            # Get model version
            if version:
                model_version = registry.get_model_version(
                    model_id=model_id, version_id=version
                )
            else:
                # Get the latest version
                versions = registry.list_model_versions(
                    model_id=model_id, order_by="update_time desc", limit=1
                )
                if not versions:
                    raise ValueError(f"No versions found for model {model_id}")
                model_version = versions[0]

            # Create endpoint
            endpoint_name = f"fxml4-{model_id}-endpoint"
            endpoint = aiplatform.Endpoint.create(display_name=endpoint_name)

            # Deploy model to endpoint
            deployed_model = endpoint.deploy(
                model=model_version.resource_name,
                machine_type=machine_type,
                min_replica_count=min_replicas,
                max_replica_count=max_replicas,
                deploy_request_timeout=1800,
            )

            # Return deployment info
            result = {
                "model_id": model_id,
                "version": version or model_version.version_id,
                "endpoint_id": endpoint.resource_name,
                "endpoint_url": endpoint.resource_name,
                "deployment_time": datetime.now().isoformat(),
                "status": "deployed",
            }

            logger.info(
                f"Successfully deployed model {model_id} to endpoint {endpoint_name}"
            )
            return result

        except Exception as e:
            logger.error(f"Failed to deploy model: {str(e)}")
            raise


class VertexAITrainer:
    """
    Trainer for running FXML4 model training jobs on Vertex AI.
    """

    def __init__(
        self,
        project_id: Optional[str] = None,
        location: str = "us-central1",
        staging_bucket: Optional[str] = None,
        container_uri: Optional[str] = None,
    ):
        """
        Initialize Vertex AI training job client.

        Args:
            project_id: Google Cloud project ID (default: from environment)
            location: Google Cloud region
            staging_bucket: GCS bucket for staging
            container_uri: Custom container URI for training
        """
        # Get project ID from environment if not provided
        self.project_id = project_id or get_default_project_id()
        self.location = location

        # Set up staging bucket
        if staging_bucket:
            self.staging_bucket = staging_bucket
        else:
            self.staging_bucket = f"gs://fxml4-training"

        # Set container URI
        self.container_uri = (
            container_uri
            or "us-docker.pkg.dev/vertex-ai/training/sklearn-cpu.1-0:latest"
        )

        # Initialize Vertex AI client
        if check_vertex_availability():
            aiplatform.init(
                project=self.project_id,
                location=location,
                staging_bucket=self.staging_bucket,
            )

    def prepare_training_script(
        self,
        model_type: str,
        model_params: Dict[str, Any],
        hyperparam_tuning: bool = False,
        task_type: str = "classification",
        output_dir: str = "/tmp/fxml4-training",
    ) -> str:
        """
        Prepare a training script for Vertex AI.

        Args:
            model_type: Type of model to train
            model_params: Model parameters
            hyperparam_tuning: Whether to perform hyperparameter tuning
            task_type: Task type (classification or regression)
            output_dir: Directory for output script

        Returns:
            Path to the generated training script
        """
        # Generate training script
        script_content = f"""#!/usr/bin/env python
# FXML4 Training Script for Vertex AI
# Generated at {datetime.now().isoformat()}

import os
import argparse
import logging
import json
import pandas as pd
import numpy as np
from google.cloud import storage
from sklearn.model_selection import TimeSeriesSplit

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Parse arguments
parser = argparse.ArgumentParser()
parser.add_argument('--model-dir', type=str, required=True, help='Directory for model output')
parser.add_argument('--training-data', type=str, required=True, help='GCS path to training data')
parser.add_argument('--validation-data', type=str, default='', help='GCS path to validation data')
parser.add_argument('--model-name', type=str, default='fxml4_model', help='Name for the trained model')
parser.add_argument('--task-type', type=str, default='{task_type}', help='Task type (classification or regression)')
parser.add_argument('--n-splits', type=int, default=5, help='Number of CV splits')
parser.add_argument('--target-column', type=str, required=True, help='Name of target column')
args = parser.parse_args()

# Download data from GCS
def download_blob_to_file(bucket_name, source_blob_name, destination_file_name):
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(source_blob_name)
    os.makedirs(os.path.dirname(destination_file_name), exist_ok=True)
    blob.download_to_filename(destination_file_name)
    logger.info(f"Downloaded {{source_blob_name}} to {{destination_file_name}}")

# Parse GCS path
def parse_gcs_path(gcs_path):
    path_parts = gcs_path.replace('gs://', '').split('/')
    bucket = path_parts[0]
    blob_path = '/'.join(path_parts[1:])
    return bucket, blob_path

# Download training data
train_bucket, train_blob = parse_gcs_path(args.training_data)
train_local_path = '/tmp/train_data.csv'
download_blob_to_file(train_bucket, train_blob, train_local_path)

# Load data
train_data = pd.read_csv(train_local_path)
X_train = train_data.drop(columns=[args.target_column])
y_train = train_data[args.target_column]

# Load validation data if provided
if args.validation_data:
    val_bucket, val_blob = parse_gcs_path(args.validation_data)
    val_local_path = '/tmp/val_data.csv'
    download_blob_to_file(val_bucket, val_blob, val_local_path)
    val_data = pd.read_csv(val_local_path)
    X_val = val_data.drop(columns=[args.target_column])
    y_val = val_data[args.target_column]
else:
    # Use part of training data for validation
    time_series_split = TimeSeriesSplit(n_splits=args.n_splits)
    splits = list(time_series_split.split(X_train))
    train_idx, val_idx = splits[-1]  # Use last split
    X_val, y_val = X_train.iloc[val_idx], y_train.iloc[val_idx]
    X_train, y_train = X_train.iloc[train_idx], y_train.iloc[train_idx]

# Initialize and train model
logger.info(f"Training {{args.model_name}} with model_type={model_type}")

# Model parameters
model_params = {json.dumps(model_params, indent=2)}

# Import necessary libraries based on model type
if '{model_type}' == 'rf':
    from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
    if args.task_type == 'classification':
        model = RandomForestClassifier(**model_params)
    else:
        model = RandomForestRegressor(**model_params)
elif '{model_type}' == 'xgb':
    import xgboost as xgb
    if args.task_type == 'classification':
        model = xgb.XGBClassifier(**model_params)
    else:
        model = xgb.XGBRegressor(**model_params)
elif '{model_type}' == 'lr':
    from sklearn.linear_model import LogisticRegression, LinearRegression
    if args.task_type == 'classification':
        model = LogisticRegression(**model_params)
    else:
        model = LinearRegression(**model_params)
else:
    raise ValueError(f"Unsupported model type: {model_type}")

# Train model
model.fit(X_train, y_train)

# Evaluate model
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, mean_squared_error, r2_score

metrics = {{}}
if args.task_type == 'classification':
    y_pred = model.predict(X_val)
    metrics['accuracy'] = float(accuracy_score(y_val, y_pred))
    metrics['precision'] = float(precision_score(y_val, y_pred, average='weighted', zero_division=0))
    metrics['recall'] = float(recall_score(y_val, y_pred, average='weighted', zero_division=0))
    metrics['f1'] = float(f1_score(y_val, y_pred, average='weighted', zero_division=0))
else:
    y_pred = model.predict(X_val)
    metrics['mse'] = float(mean_squared_error(y_val, y_pred))
    metrics['rmse'] = float(np.sqrt(mean_squared_error(y_val, y_pred)))
    metrics['r2'] = float(r2_score(y_val, y_pred))

# Save model and metadata
import joblib
import json
import os

os.makedirs(args.model_dir, exist_ok=True)
model_path = os.path.join(args.model_dir, f"{{args.model_name}}.joblib")
joblib.dump(model, model_path)

# Create metadata
metadata = {{
    "created_at": "{{datetime.now().isoformat()}}",
    "model_type": "{model_type}",
    "task_type": args.task_type,
    "params": model_params,
    "metrics": metrics,
    "features": list(X_train.columns),
    "n_features": len(X_train.columns),
    "n_train_samples": len(X_train),
    "n_val_samples": len(X_val)
}}

# Save metadata
metadata_path = os.path.join(args.model_dir, f"{{args.model_name}}_metadata.json")
with open(metadata_path, 'w') as f:
    json.dump(metadata, f, indent=2)

logger.info(f"Training complete. Model saved to {{model_path}}")
logger.info(f"Metrics: {{metrics}}")
"""

        # Write script to file
        os.makedirs(output_dir, exist_ok=True)
        script_path = os.path.join(output_dir, "train.py")
        with open(script_path, "w") as f:
            f.write(script_content)

        # Make script executable
        os.chmod(script_path, 0o755)

        return script_path

    def submit_training_job(
        self,
        model_type: str,
        model_params: Dict[str, Any],
        training_data_uri: str,
        validation_data_uri: Optional[str] = None,
        job_name: Optional[str] = None,
        machine_type: str = "n1-standard-4",
        target_column: str = "target",
        task_type: str = "classification",
        timeout: int = 3600,
    ) -> Dict[str, Any]:
        """
        Submit a training job to Vertex AI.

        Args:
            model_type: Type of model to train
            model_params: Model parameters
            training_data_uri: GCS URI to training data
            validation_data_uri: GCS URI to validation data
            job_name: Name for the training job
            machine_type: Machine type for training
            target_column: Name of target column
            task_type: Task type (classification or regression)
            timeout: Timeout in seconds

        Returns:
            Dictionary with job information
        """
        if not check_vertex_availability():
            raise ImportError(
                "Vertex AI not available. Please install required packages."
            )

        try:
            # Generate job name if not provided
            if job_name is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                job_name = f"fxml4_{model_type}_{timestamp}"

            # Prepare training script
            script_dir = tempfile.mkdtemp()
            script_path = self.prepare_training_script(
                model_type=model_type,
                model_params=model_params,
                task_type=task_type,
                output_dir=script_dir,
            )

            # Generate output directory in GCS
            output_dir = f"{self.staging_bucket}/models/{job_name}"

            # Set up command arguments
            command = [
                "python",
                "/train.py",
                f"--model-dir={output_dir}",
                f"--training-data={training_data_uri}",
                f"--target-column={target_column}",
                f"--task-type={task_type}",
                f"--model-name={job_name}",
            ]

            if validation_data_uri:
                command.append(f"--validation-data={validation_data_uri}")

            # Create and run custom training job
            job = CustomTrainingJob(
                display_name=job_name,
                script_path=script_path,
                container_uri=self.container_uri,
                requirements=[
                    "scikit-learn",
                    "pandas",
                    "numpy",
                    "xgboost",
                    "google-cloud-storage",
                ],
                model_serving_container_image_uri="us-docker.pkg.dev/vertex-ai/prediction/sklearn-cpu.1-0:latest",
            )

            # Start job
            model = job.run(
                machine_type=machine_type,
                replica_count=1,
                args=command,
                service_account=None,  # Use default
                timeout=timeout,
            )

            # Return job information
            result = {
                "job_name": job_name,
                "output_dir": output_dir,
                "model_id": model.resource_name if model else None,
                "status": "submitted",
                "submission_time": datetime.now().isoformat(),
            }

            logger.info(f"Successfully submitted training job {job_name}")
            return result

        except Exception as e:
            logger.error(f"Failed to submit training job: {str(e)}")
            raise
