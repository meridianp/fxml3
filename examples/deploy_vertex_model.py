#!/usr/bin/env python3
"""
Deploy a registered model to a Vertex AI endpoint.

This script creates an endpoint and deploys a registered model for online predictions.
"""

import argparse
import logging
import os

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
    except Exception as e:
        logger.error(f"Error deploying model: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(
        description="Deploy a model to a Vertex AI endpoint"
    )
    parser.add_argument("--model-id", required=True, help="Vertex AI model ID")
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

    # Deploy model to endpoint
    endpoint = deploy_model_to_endpoint(
        model_id=args.model_id,
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
