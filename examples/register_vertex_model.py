#!/usr/bin/env python3
"""
Register an existing model in Google Cloud Storage with Vertex AI.

This script registers models that have already been uploaded to GCS with the Vertex AI
Model Registry, without needing to train or upload a new model.
"""

import argparse
import logging
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


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
    except Exception as e:
        logger.error(f"Error registering model with Vertex AI: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Register a model with Vertex AI")
    parser.add_argument(
        "--gcs-uri",
        required=True,
        help="GCS URI to the directory containing model files",
    )
    parser.add_argument(
        "--display-name",
        default=f"gbpusd-model-{datetime.now().strftime('%Y%m%d')}",
        help="Display name for the model in Vertex AI",
    )
    parser.add_argument("--description", help="Description for the model")
    args = parser.parse_args()

    # Set up Google Cloud environment
    project_id = setup_gcp_environment()
    if project_id is None:
        logger.error("Failed to set up GCP environment")
        return 1

    # Register model with Vertex AI
    model = register_model_with_vertex(
        gcs_uri=args.gcs_uri,
        display_name=args.display_name,
        description=args.description,
    )

    if model is None:
        logger.error("Failed to register model with Vertex AI")
        return 1

    logger.info("Model registration completed successfully")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
