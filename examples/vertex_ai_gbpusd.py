#!/usr/bin/env python3
"""
Test the integration of GBP/USD ML model with Google Vertex AI.

This script demonstrates:
1. Training a GBP/USD model locally
2. Preparing the model for Vertex AI
3. Uploading the model to Google Cloud Storage
4. Registering the model with Vertex AI Model Registry
"""

import argparse
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from sklearn.model_selection import train_test_split

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables
load_dotenv()

# Import FXML4 modules
from fxml4.ml.gbpusd_model import GBPUSDModel, train_gbpusd_model
from fxml4.strategy.gbpusd_signal_generator import GBPUSDSignalGenerator

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def train_and_save_model(data_path):
    """Train and save a GBP/USD model locally."""
    logger.info(f"Loading data from {data_path}")
    data = pd.read_parquet(data_path)

    # Create and train model
    logger.info("Training GBP/USD model")
    model = GBPUSDModel(model_type="random_forest")

    # Prepare features
    features = model.prepare_features(
        data, target_horizon=12, add_lag_features=True, create_target=True
    )

    # Train model
    target_col = "target_12"
    X = features.drop(columns=[target_col])
    y = features[target_col]

    # Split into train and test sets
    test_size = 0.2
    split_idx = int(len(X) * (1 - test_size))
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]

    logger.info(f"Training set: {len(X_train)} samples")
    logger.info(f"Test set: {len(X_test)} samples")

    # Scale features
    X_train_scaled = model.scale_features(X_train, refit=True)

    # Train model
    model.model.fit(X_train_scaled, y_train)

    # Evaluate model
    X_test_scaled = model.scale_features(X_test, refit=False)
    y_pred = model.model.predict(X_test_scaled)

    from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score

    accuracy = accuracy_score(y_test, y_pred)
    precision = precision_score(y_test, y_pred, average="weighted")
    recall = recall_score(y_test, y_pred, average="weighted")
    f1 = f1_score(y_test, y_pred, average="weighted")

    logger.info(f"Accuracy: {accuracy:.4f}")
    logger.info(f"Precision: {precision:.4f}")
    logger.info(f"Recall: {recall:.4f}")
    logger.info(f"F1 Score: {f1:.4f}")

    # Save model
    model_dir = "models"
    model.save(directory=model_dir)

    return model


def setup_gcp_environment():
    """Set up Google Cloud environment for Vertex AI."""
    logger.info("Setting up GCP environment")

    # Check if GCP project is set
    gcp_project = os.environ.get("GCP_PROJECT")
    if not gcp_project:
        logger.error("GCP_PROJECT environment variable not set")
        return False

    # Hardcode the application credentials path
    credentials_path = os.path.expanduser(
        "~/.config/gcloud/application_default_credentials.json"
    )
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path

    # Check if the credentials file exists
    if not os.path.exists(credentials_path):
        logger.error(f"Credentials file not found: {credentials_path}")
        return False

    logger.info(f"Using GCP project: {gcp_project}")
    logger.info(f"Using credentials: {credentials_path}")

    # Set up Google Cloud storage bucket
    # Check if bucket exists and create if needed
    try:
        from google.cloud import storage

        # Initialize client
        storage_client = storage.Client(project=gcp_project)

        # Check if bucket exists
        bucket_name = f"{gcp_project}-fxml4-models"
        bucket = storage_client.bucket(bucket_name)

        if not bucket.exists():
            logger.info(f"Creating bucket: {bucket_name}")
            bucket = storage_client.create_bucket(bucket_name, location="us-central1")
        else:
            logger.info(f"Using existing bucket: {bucket_name}")

        return True
    except Exception as e:
        logger.error(f"Error setting up GCP environment: {e}")
        return False


def upload_model_to_gcs(model, gcs_bucket=None):
    """Upload model to Google Cloud Storage."""
    logger.info("Uploading model to Google Cloud Storage")

    # Get GCP project
    gcp_project = os.environ.get("GCP_PROJECT")
    if not gcp_project:
        logger.error("GCP_PROJECT environment variable not set")
        return None

    # Set bucket name
    if gcs_bucket is None:
        gcs_bucket = f"{gcp_project}-models"

    try:
        from google.cloud import storage

        # Initialize client
        storage_client = storage.Client(project=gcp_project)

        # Get model files
        model_dir = "models"
        model_files = [
            f"{model.name}.joblib",
            f"{model.name}_scaler.joblib",
            f"{model.name}_metadata.json",
        ]

        # Upload files
        for file_name in model_files:
            local_path = os.path.join(model_dir, file_name)

            if not os.path.exists(local_path):
                logger.warning(f"Model file not found: {local_path}")
                continue

            # Set destination path in GCS
            timestamp = datetime.now().strftime("%Y%m%d")
            gcs_path = f"models/gbpusd/{timestamp}/{file_name}"

            # Upload file
            bucket = storage_client.bucket(gcs_bucket)
            blob = bucket.blob(gcs_path)
            blob.upload_from_filename(local_path)

            logger.info(f"Uploaded {local_path} to gs://{gcs_bucket}/{gcs_path}")

        # Return GCS URI
        gcs_dir = f"gs://{gcs_bucket}/models/gbpusd/{timestamp}"
        logger.info(f"Model uploaded to: {gcs_dir}")

        return gcs_dir
    except Exception as e:
        logger.error(f"Error uploading model to GCS: {e}")
        return None


def register_model_with_vertex_ai(model, gcs_uri):
    """Register model with Vertex AI Model Registry."""
    logger.info("Registering model with Vertex AI Model Registry")

    # Get GCP project
    gcp_project = os.environ.get("GCP_PROJECT")
    if not gcp_project:
        logger.error("GCP_PROJECT environment variable not set")
        return None

    try:
        from google.cloud import aiplatform

        # Initialize Vertex AI client
        aiplatform.init(project=gcp_project, location="us-central1")

        # Register model
        model_display_name = f"gbpusd-{model.model_type}-model"
        registered_model = aiplatform.Model.upload(
            display_name=model_display_name,
            artifact_uri=gcs_uri,
            serving_container_image_uri="us-docker.pkg.dev/vertex-ai/prediction/sklearn-cpu.1-0:latest",
            sync=True,
        )

        logger.info(
            f"Model registered with Vertex AI: {registered_model.resource_name}"
        )
        logger.info(f"Model URI: {registered_model.uri}")

        return registered_model
    except Exception as e:
        logger.error(f"Error registering model with Vertex AI: {e}")
        return None


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Test GBP/USD ML model with Vertex AI")
    parser.add_argument(
        "--data-path", default="output/C_GBPUSD_4h.parquet", help="Path to data file"
    )
    parser.add_argument(
        "--skip-training",
        action="store_true",
        help="Skip training and use existing model",
    )
    parser.add_argument("--model-name", help="Name of existing model to use")
    parser.add_argument("--gcs-bucket", help="Google Cloud Storage bucket name")
    args = parser.parse_args()

    logger.info("Testing GBP/USD ML model with Vertex AI")

    # Set up GCP environment
    if not setup_gcp_environment():
        logger.error("Failed to set up GCP environment. Exiting.")
        return 1

    # Train or load model
    if not args.skip_training:
        # Train model
        model = train_and_save_model(args.data_path)
    else:
        # Load existing model
        model_name = args.model_name
        if not model_name:
            logger.error("Model name must be provided when using --skip-training")
            return 1

        try:
            logger.info(f"Loading model: {model_name}")
            model = GBPUSDModel.load(model_name, directory="models")
        except Exception as e:
            logger.error(f"Error loading model: {e}")
            return 1

    # Upload model to GCS
    gcs_uri = upload_model_to_gcs(model, args.gcs_bucket)
    if not gcs_uri:
        logger.error("Failed to upload model to GCS. Exiting.")
        return 1

    # Register model with Vertex AI
    registered_model = register_model_with_vertex_ai(model, gcs_uri)
    if not registered_model:
        logger.error("Failed to register model with Vertex AI. Exiting.")
        return 1

    logger.info("Test completed successfully")
    return 0


if __name__ == "__main__":
    sys.exit(main())
