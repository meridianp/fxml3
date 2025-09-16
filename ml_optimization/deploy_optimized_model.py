#!/usr/bin/env python3
"""
Deploy Optimized GBP/USD Model to Google Vertex AI

This script uploads and deploys the optimized model to Vertex AI:
1. Loads the optimized model from local storage
2. Uploads the model to Google Cloud Storage
3. Registers the model with Vertex AI
4. Deploys the model to a prediction endpoint
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Add project root to path to import from fxml4
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

# Import necessary modules
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file


def setup_gcp_environment():
    """Set up Google Cloud environment for Vertex AI."""
    # Check if GCP project is set
    gcp_project = os.environ.get("GCP_PROJECT")
    if not gcp_project:
        logger.error("GCP_PROJECT environment variable not set")
        return None

    # Set application credentials path
    credentials_path = os.path.expanduser(
        "~/.config/gcloud/application_default_credentials.json"
    )
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path

    # Check if credentials file exists
    if not os.path.exists(credentials_path):
        logger.error(f"Credentials file not found: {credentials_path}")
        return None

    logger.info(f"Using GCP project: {gcp_project}")
    logger.info(f"Using credentials: {credentials_path}")

    return gcp_project


def upload_model_to_gcs(model_path, metadata_path, bucket_name=None):
    """
    Upload model and metadata to Google Cloud Storage

    Args:
        model_path: Path to model file
        metadata_path: Path to metadata file
        bucket_name: GCS bucket name

    Returns:
        GCS URI for the uploaded model directory
    """
    try:
        from google.cloud import storage

        # Get project ID
        project_id = os.environ.get("GCP_PROJECT")

        # Use default bucket if not specified
        if bucket_name is None:
            bucket_name = f"{project_id}-models"

        # Create a unique directory name using timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        gcs_dir = f"gbpusd_model_{timestamp}"

        # Connect to GCS
        client = storage.Client(project=project_id)

        # Check if bucket exists, create if not
        try:
            bucket = client.get_bucket(bucket_name)
        except Exception:
            logger.info(f"Creating bucket: {bucket_name}")
            bucket = client.create_bucket(bucket_name, location="us-central1")

        # Upload model file as model.joblib (required name for sklearn serving container)
        model_blob = bucket.blob(f"{gcs_dir}/model.joblib")
        model_blob.upload_from_filename(model_path)
        logger.info(f"Uploaded model to gs://{bucket_name}/{gcs_dir}/model.joblib")

        # Upload metadata file as model_metadata.json
        metadata_blob = bucket.blob(f"{gcs_dir}/model_metadata.json")
        metadata_blob.upload_from_filename(metadata_path)
        logger.info(
            f"Uploaded metadata to gs://{bucket_name}/{gcs_dir}/model_metadata.json"
        )

        # Return the GCS URI
        return f"gs://{bucket_name}/{gcs_dir}"

    except ImportError:
        logger.error(
            "Google Cloud Storage client not installed. Run: pip install google-cloud-storage"
        )
        return None
    except Exception as e:
        logger.error(f"Error uploading model to GCS: {str(e)}")
        return None


def register_model_with_vertex(gcs_uri, display_name, description=None):
    """Register a model from GCS with Vertex AI Model Registry."""
    try:
        from google.cloud import aiplatform

        # Initialize Vertex AI client
        project_id = os.environ.get("GCP_PROJECT")
        location = "us-central1"

        logger.info(
            f"Initializing Vertex AI in project {project_id}, location {location}"
        )
        aiplatform.init(project=project_id, location=location)

        # Get description if not provided
        if description is None:
            description = f"GBP/USD prediction model uploaded on {datetime.now().strftime('%Y-%m-%d')}"

        # Register model
        logger.info(f"Registering model {display_name} from {gcs_uri}")
        model = aiplatform.Model.upload(
            display_name=display_name,
            artifact_uri=gcs_uri,
            serving_container_image_uri="us-docker.pkg.dev/vertex-ai/prediction/sklearn-cpu.1-0:latest",
            description=description,
            sync=True,
        )

        logger.info(f"Model registered with Vertex AI: {model.resource_name}")
        logger.info(f"Model URI: {model.uri}")

        return model
    except ImportError:
        logger.error(
            "Google Cloud AI Platform package not installed. Run: pip install google-cloud-aiplatform"
        )
        return None
    except Exception as e:
        logger.error(f"Error registering model with Vertex AI: {e}")
        return None


def deploy_model_to_endpoint(model_id, endpoint_name, machine_type="n1-standard-2"):
    """Deploy a model to a Vertex AI endpoint."""
    try:
        from google.cloud import aiplatform

        # Initialize Vertex AI client
        project_id = os.environ.get("GCP_PROJECT")
        location = "us-central1"

        logger.info(
            f"Initializing Vertex AI in project {project_id}, location {location}"
        )
        aiplatform.init(project=project_id, location=location)

        # Get the model
        logger.info(f"Loading model {model_id}")
        model = aiplatform.Model(model_id)

        # Create or get endpoint
        try:
            logger.info(f"Looking for existing endpoint: {endpoint_name}")
            endpoint = aiplatform.Endpoint.list(filter=f"display_name={endpoint_name}")
            if endpoint:
                endpoint = endpoint[0]
                logger.info(f"Using existing endpoint: {endpoint.resource_name}")
            else:
                logger.info(f"Creating new endpoint: {endpoint_name}")
                endpoint = aiplatform.Endpoint.create(display_name=endpoint_name)
        except Exception as e:
            logger.info(f"Creating new endpoint: {endpoint_name}")
            endpoint = aiplatform.Endpoint.create(display_name=endpoint_name)

        # Deploy model to endpoint
        logger.info(f"Deploying model {model_id} to endpoint {endpoint.resource_name}")
        deployment = endpoint.deploy(
            model=model,
            machine_type=machine_type,
            min_replica_count=1,
            max_replica_count=1,
            deploy_request_timeout=1800,  # 30 minutes
        )

        logger.info(f"Model deployed successfully to {endpoint.resource_name}")
        logger.info(f"Endpoint URL: {endpoint.service_endpoint}")

        return endpoint
    except ImportError:
        logger.error(
            "Google Cloud AI Platform package not installed. Run: pip install google-cloud-aiplatform"
        )
        return None
    except Exception as e:
        logger.error(f"Error deploying model: {e}")
        return None


def main():
    # Parse arguments
    parser = argparse.ArgumentParser(
        description="Deploy optimized GBP/USD model to Vertex AI"
    )
    parser.add_argument(
        "--model-path",
        default="ml_optimization/results/",
        help="Path to directory containing the optimized model",
    )
    parser.add_argument(
        "--bucket-name",
        default=None,
        help="GCS bucket name for model storage (defaults to PROJECT_ID-models)",
    )
    parser.add_argument(
        "--endpoint-name",
        default="gbpusd-prediction-endpoint",
        help="Name for the endpoint",
    )
    parser.add_argument(
        "--machine-type", default="n1-standard-2", help="Machine type for deployment"
    )
    args = parser.parse_args()

    # Set up Google Cloud environment
    project_id = setup_gcp_environment()
    if project_id is None:
        logger.error("Failed to set up GCP environment")
        return 1

    # Find the latest model file in the specified directory
    model_dir = Path(args.model_path)
    model_files = list(model_dir.glob("*.joblib"))
    metadata_files = list(model_dir.glob("*metadata.json"))

    if not model_files or not metadata_files:
        logger.error(f"No model or metadata files found in {model_dir}")
        return 1

    # Use the most recent model file
    model_path = str(
        sorted(model_files, key=lambda p: p.stat().st_mtime, reverse=True)[0]
    )
    metadata_path = str(
        sorted(metadata_files, key=lambda p: p.stat().st_mtime, reverse=True)[0]
    )

    logger.info(f"Using model file: {model_path}")
    logger.info(f"Using metadata file: {metadata_path}")

    # Upload model to GCS
    gcs_uri = upload_model_to_gcs(model_path, metadata_path, args.bucket_name)
    if gcs_uri is None:
        logger.error("Failed to upload model to GCS")
        return 1

    # Register model with Vertex AI
    model_display_name = f"gbpusd-model-{datetime.now().strftime('%Y%m%d')}"
    model = register_model_with_vertex(
        gcs_uri=gcs_uri,
        display_name=model_display_name,
        description=f"GBP/USD prediction model with optimized hyperparameters",
    )

    if model is None:
        logger.error("Failed to register model with Vertex AI")
        return 1

    # Deploy model to endpoint
    endpoint = deploy_model_to_endpoint(
        model_id=model.resource_name,
        endpoint_name=args.endpoint_name,
        machine_type=args.machine_type,
    )

    if endpoint is None:
        logger.error("Failed to deploy model")
        return 1

    logger.info("Model deployment completed successfully")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
