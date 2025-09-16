#!/usr/bin/env python
"""
Example of using Google Vertex AI integration with FXML4.

This script demonstrates how to:
1. Train a model locally
2. Register it with the model registry
3. Upload it to Vertex AI
4. Deploy it as an endpoint for predictions

Requirements:
- Google Cloud SDK installed (gcloud)
- Authenticated with `gcloud auth login`
- Vertex AI API enabled in your project
- google-cloud-aiplatform package installed
"""

import argparse
import logging
import os
import sys
from datetime import datetime

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from sklearn.ensemble import RandomForestClassifier

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables
load_dotenv()

from ml.model_registry import ModelRegistry
from ml.vertex_ai import (
    VertexAIModel,
    VertexAITrainer,
    check_vertex_availability,
    get_default_project_id,
)

# FXML4 imports
from fxml4.ml.models import ClassicMLModel

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def train_local_model(data_path: str, target_column: str):
    """Train a simple model locally."""
    # Load data
    logger.info(f"Loading data from {data_path}")
    data = pd.read_csv(data_path)

    # Prepare features and target
    X = data.drop(columns=[target_column])
    y = data[target_column]

    # Create model
    model_params = {
        "n_estimators": 100,
        "max_depth": 5,
        "min_samples_split": 10,
        "random_state": 42,
    }

    # Create and train model
    model = ClassicMLModel(
        model_type="rf",
        model_params=model_params,
        name="forex_direction_predictor",
        n_classes=len(np.unique(y)),
        random_state=42,
    )

    logger.info("Training model locally")
    model.train(X, y)

    # Evaluate model
    evaluation = model.evaluate(X, y)
    logger.info(f"Model accuracy: {evaluation['accuracy']:.4f}")
    logger.info(f"Model F1 score: {evaluation['f1']:.4f}")

    return model


def register_and_upload_model(
    model, gcp_project_id: Optional[str] = None, upload_to_cloud: bool = True
):
    """Register model and optionally upload to Vertex AI."""
    # Initialize model registry
    cloud_config = {
        "project_id": gcp_project_id or get_default_project_id(),
        "location": "us-central1",
    }

    cloud_provider = "vertex_ai" if upload_to_cloud else None
    registry = ModelRegistry(
        base_dir="models",
        cloud_provider=cloud_provider,
        cloud_config=cloud_config if upload_to_cloud else None,
    )

    # Register model
    logger.info(f"Registering model {model.name}")
    registration = registry.register_model(
        model=model,
        description="Forex direction prediction model",
        tags=["forex", "direction", "classification"],
        upload_to_cloud=upload_to_cloud,
    )

    logger.info(f"Model registered with version {registration['version']}")
    if upload_to_cloud and registration.get("cloud_info"):
        logger.info(
            f"Model uploaded to Vertex AI: {registration['cloud_info'].get('vertex_model_id')}"
        )

    return registration


def deploy_model_to_vertex(
    model_name: str, version: str, gcp_project_id: Optional[str] = None
):
    """Deploy model to Vertex AI endpoint."""
    # Initialize model registry with cloud connection
    cloud_config = {
        "project_id": gcp_project_id or get_default_project_id(),
        "location": "us-central1",
    }

    registry = ModelRegistry(
        base_dir="models", cloud_provider="vertex_ai", cloud_config=cloud_config
    )

    # Deploy model
    logger.info(f"Deploying model {model_name} version {version} to Vertex AI")
    deployment = registry.deploy_model(
        model_name=model_name,
        version=version,
        deployment_config={
            "machine_type": "n1-standard-2",
            "min_replicas": 1,
            "max_replicas": 2,
        },
    )

    logger.info(f"Model deployed to endpoint: {deployment.get('endpoint_id')}")
    return deployment


def submit_training_job(data_gcs_uri: str, gcp_project_id: Optional[str] = None):
    """Submit a training job to Vertex AI."""
    # Check Vertex AI availability
    if not check_vertex_availability():
        logger.error("Vertex AI not available")
        return None

    # Initialize Vertex AI trainer
    trainer = VertexAITrainer(project_id=gcp_project_id, location="us-central1")

    # Model parameters
    model_params = {
        "n_estimators": 100,
        "max_depth": 5,
        "min_samples_split": 10,
        "random_state": 42,
    }

    # Submit training job
    logger.info(f"Submitting training job to Vertex AI")
    job = trainer.submit_training_job(
        model_type="rf",
        model_params=model_params,
        training_data_uri=data_gcs_uri,
        target_column="target",
        job_name=f"forex_model_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        machine_type="n1-standard-4",
    )

    logger.info(f"Training job submitted: {job.get('job_name')}")
    logger.info(f"Model will be saved to: {job.get('output_dir')}")

    return job


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="FXML4 Vertex AI Example")
    parser.add_argument("--data", type=str, required=True, help="Path to CSV data file")
    parser.add_argument(
        "--gcp-project",
        type=str,
        default=None,
        help="GCP project ID (defaults to environment value)",
    )
    parser.add_argument(
        "--target", type=str, default="target", help="Target column name"
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["local", "cloud"],
        default="local",
        help="Training mode: local or cloud",
    )
    parser.add_argument(
        "--deploy", action="store_true", help="Deploy model to endpoint"
    )

    args = parser.parse_args()

    # Check Vertex AI availability
    if not check_vertex_availability():
        logger.warning(
            "Vertex AI not available. Make sure you have the required packages installed."
        )
        logger.warning("Running in local-only mode")
        args.mode = "local"
        args.deploy = False

    # Train model locally or in the cloud
    if args.mode == "local":
        # Train model locally
        model = train_local_model(args.data, args.target)

        # Register model and optionally upload to cloud
        registration = register_and_upload_model(
            model, args.gcp_project, upload_to_cloud=True
        )

        # Deploy model if requested
        if args.deploy and registration.get("cloud_info"):
            deploy_model_to_vertex(
                model.name, registration["version"], args.gcp_project
            )
    else:
        # Convert data path to GCS URI if it's not already
        data_uri = args.data
        if not data_uri.startswith("gs://"):
            logger.error("For cloud training, data_path must be a GCS URI (gs://...)")
            return

        # Submit training job to Vertex AI
        job = submit_training_job(data_uri, args.gcp_project)

        # Note: Vertex AI training job is asynchronous
        # You need to check the job status in the GCP console
        logger.info("Training job submitted. Check GCP console for status.")


if __name__ == "__main__":
    main()
