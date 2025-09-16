#!/usr/bin/env python3
"""
Deploy Enhanced Forex ML Model to Google Vertex AI

This script deploys a trained ML model with exogenous data features to Google Vertex AI.
It handles:
1. Loading the trained model and feature information
2. Creating an adapter class for Vertex AI compatibility
3. Uploading the model to Vertex AI Model Registry
4. Deploying the model to an endpoint for online predictions

Usage:
    python deploy_enhanced_model.py --model-path MODEL_PATH [--deploy]
"""

import argparse
import json
import logging
import os
import pickle
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import joblib
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Add project root to path to import from fxml4
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))


class ModelAdapter:
    """
    Adapter class to make our ML model compatible with Vertex AI serving.

    This creates a wrapper around our trained model that handles:
    1. Preprocessing input data with proper feature extraction
    2. Ensuring the right features are used in the right order
    3. Transforming outputs into standardized format for API responses
    """

    def __init__(
        self,
        model_path: str,
        feature_info_path: Optional[str] = None,
        vertex_compatible: bool = True,
    ):
        """
        Initialize the model adapter.

        Args:
            model_path: Path to saved model file (.joblib or .pkl)
            feature_info_path: Path to feature info JSON (if None, infers from model_path)
            vertex_compatible: Whether to make this adapter compatible with Vertex AI
        """
        # Load the model
        self.model_path = model_path
        self.model = self.load_model(model_path)

        # Load feature info
        if feature_info_path is None:
            # Try to infer feature info path from model path
            if model_path.endswith(".joblib") or model_path.endswith(".pkl"):
                base_path = (
                    model_path[: -len(".joblib")]
                    if model_path.endswith(".joblib")
                    else model_path[: -len(".pkl")]
                )
                feature_info_path = f"{base_path}_features.json"

            if not os.path.exists(feature_info_path):
                # Try to find any _features.json file in the same directory
                directory = os.path.dirname(model_path)
                json_files = [
                    f for f in os.listdir(directory) if f.endswith("_features.json")
                ]
                if json_files:
                    feature_info_path = os.path.join(directory, json_files[0])
                else:
                    raise ValueError(
                        f"Could not find feature info file for {model_path}"
                    )

        # Load feature info
        with open(feature_info_path, "r") as f:
            self.feature_info = json.load(f)

        # Extract feature lists
        self.all_features = self.feature_info.get("all_features", [])
        self.selected_features = self.feature_info.get(
            "selected_features", self.all_features
        )

        # Set up for Vertex AI compatibility if needed
        self.vertex_compatible = vertex_compatible

        # Load metadata
        self.metadata = {}
        try:
            # Try to get metadata from model if available
            if hasattr(self.model, "metadata"):
                self.metadata = self.model.metadata
            else:
                # Check if there's a separate metadata file
                metadata_path = model_path.replace(".joblib", "_metadata.json").replace(
                    ".pkl", "_metadata.json"
                )
                if os.path.exists(metadata_path):
                    with open(metadata_path, "r") as f:
                        self.metadata = json.load(f)
        except Exception as e:
            logger.warning(f"Could not load model metadata: {e}")

        logger.info(
            f"Model adapter initialized with {len(self.selected_features)} features"
        )

    def load_model(self, model_path: str) -> Any:
        """
        Load model from disk.

        Args:
            model_path: Path to saved model

        Returns:
            Loaded model
        """
        try:
            if model_path.endswith(".joblib"):
                model = joblib.load(model_path)
            elif model_path.endswith(".pkl"):
                with open(model_path, "rb") as f:
                    model = pickle.load(f)
            else:
                # Try joblib as default
                model = joblib.load(model_path)

            logger.info(f"Successfully loaded model from {model_path}")
            return model
        except Exception as e:
            raise ValueError(f"Failed to load model from {model_path}: {e}")

    def preprocess(self, inputs: Dict[str, Any]) -> np.ndarray:
        """
        Preprocess input data for prediction.

        Args:
            inputs: Dictionary of input data

        Returns:
            Numpy array ready for model prediction
        """
        # If already a DataFrame, use it
        if isinstance(inputs, pd.DataFrame):
            df = inputs
        else:
            # Convert dictionary to DataFrame
            df = pd.DataFrame([inputs])

        # Ensure all required features are present
        missing_features = [f for f in self.selected_features if f not in df.columns]
        if missing_features:
            raise ValueError(f"Missing required features: {missing_features}")

        # Select and order features according to model requirements
        X = df[self.selected_features].values

        return X

    def postprocess(self, outputs: np.ndarray) -> List[Dict[str, Any]]:
        """
        Postprocess model outputs into API-friendly format.

        Args:
            outputs: Raw model output array

        Returns:
            List of dictionaries with prediction results
        """
        # Get the prediction class probabilities if available
        if hasattr(self.model, "predict_proba"):
            probabilities = self.model.predict_proba(outputs)
        elif hasattr(self.model, "model") and hasattr(
            self.model.model, "predict_proba"
        ):
            probabilities = self.model.model.predict_proba(outputs)
        else:
            # Create dummy probabilities if not available
            n_samples = outputs.shape[0]
            classes = [-1, 0, 1]  # Default for our forex model
            n_classes = len(classes)
            probabilities = np.zeros((n_samples, n_classes))
            for i, pred in enumerate(outputs):
                class_idx = classes.index(pred) if pred in classes else 0
                probabilities[i, class_idx] = 1.0

        # Transform predictions to structured output
        results = []
        predictions = outputs if isinstance(outputs, np.ndarray) else np.array(outputs)

        for i, pred in enumerate(predictions):
            result = {
                "prediction": int(pred),  # -1, 0, or 1
                "prediction_label": {
                    "-1": "Bearish",
                    "0": "Neutral",
                    "1": "Bullish",
                }.get(str(int(pred)), "Unknown"),
            }

            # Add probabilities if available
            if probabilities is not None and i < len(probabilities):
                probs = probabilities[i]
                result["probabilities"] = {
                    "bearish": float(probs[0]) if len(probs) > 0 else 0.0,
                    "neutral": float(probs[1]) if len(probs) > 1 else 0.0,
                    "bullish": float(probs[2]) if len(probs) > 2 else 0.0,
                }

                # Add confidence (highest probability)
                result["confidence"] = float(np.max(probs))

            results.append(result)

        return results

    def predict(
        self, inputs: Union[Dict[str, Any], List[Dict[str, Any]], pd.DataFrame]
    ) -> List[Dict[str, Any]]:
        """
        Make predictions with the model.

        Args:
            inputs: Input data (dict, list of dicts, or DataFrame)

        Returns:
            List of dictionaries with prediction results
        """
        # Handle different input formats
        if isinstance(inputs, dict):
            inputs = [inputs]

        if isinstance(inputs, list):
            # Convert list of dicts to DataFrame
            df = pd.DataFrame(inputs)
        else:
            # Already a DataFrame
            df = inputs

        # Preprocess
        X = self.preprocess(df)

        # Make prediction
        try:
            if hasattr(self.model, "predict"):
                predictions = self.model.predict(X)
            elif hasattr(self.model, "model") and hasattr(self.model.model, "predict"):
                # For wrapper class like MLModelWrapper
                predictions = self.model.model.predict(X)
            else:
                raise ValueError("Model does not have a predict method")
        except Exception as e:
            logger.error(f"Error during prediction: {e}")
            raise

        # Postprocess
        results = self.postprocess(predictions)

        return results

    def vertex_predict(self, instances):
        """
        Prediction method signature for Vertex AI online serving.

        Args:
            instances: List of instances as dictionaries

        Returns:
            Dictionary with predictions
        """
        if not self.vertex_compatible:
            raise ValueError("Model adapter not configured for Vertex AI compatibility")

        try:
            # Convert instances to DataFrame
            df = pd.DataFrame(instances)

            # Make prediction
            results = self.predict(df)

            # Return in Vertex expected format
            return {"predictions": results}

        except Exception as e:
            logger.error(f"Error in Vertex prediction: {e}")
            return {"error": str(e)}


def upload_model_to_gcs(
    model_path: str,
    gcs_bucket: str,
    gcs_prefix: Optional[str] = None,
    feature_info_path: Optional[str] = None,
) -> str:
    """
    Upload model and its metadata to Google Cloud Storage.

    Args:
        model_path: Path to model file
        gcs_bucket: GCS bucket name
        gcs_prefix: Prefix for GCS path
        feature_info_path: Path to feature info file

    Returns:
        GCS path where model was uploaded
    """
    try:
        from google.cloud import storage
    except ImportError:
        logger.error("Google Cloud Storage package not installed")
        logger.error("Install with: pip install google-cloud-storage")
        return None

    logger.info(f"Uploading model {model_path} to GCS bucket {gcs_bucket}")

    # Create Storage client
    client = storage.Client()

    # Get bucket
    bucket = client.bucket(gcs_bucket)

    # Create timestamp for unique path
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Set GCS prefix with timestamp
    if gcs_prefix:
        gcs_path = (
            f"{gcs_prefix}/models/enhanced/{os.path.basename(model_path)}_{timestamp}"
        )
    else:
        gcs_path = f"models/enhanced/{os.path.basename(model_path)}_{timestamp}"

    # Upload model file
    blob = bucket.blob(gcs_path)
    blob.upload_from_filename(model_path)

    logger.info(f"Uploaded model to gs://{gcs_bucket}/{gcs_path}")

    # Upload feature info if available
    if feature_info_path is None:
        # Try to infer feature info path
        if model_path.endswith(".joblib"):
            feature_info_path = model_path.replace(".joblib", "_features.json")
        elif model_path.endswith(".pkl"):
            feature_info_path = model_path.replace(".pkl", "_features.json")

    if feature_info_path and os.path.exists(feature_info_path):
        feature_gcs_path = gcs_path.replace(".joblib", "_features.json").replace(
            ".pkl", "_features.json"
        )
        feature_blob = bucket.blob(feature_gcs_path)
        feature_blob.upload_from_filename(feature_info_path)
        logger.info(f"Uploaded feature info to gs://{gcs_bucket}/{feature_gcs_path}")

    # Return the full GCS URI
    gcs_uri = f"gs://{gcs_bucket}/{gcs_path}"
    return gcs_uri


def register_model_to_vertex(
    model_uri: str, model_name: str, project_id: str, region: str = "us-central1"
) -> str:
    """
    Register model to Vertex AI Model Registry.

    Args:
        model_uri: GCS URI where model is stored
        model_name: Name for the Vertex AI model
        project_id: GCP project ID
        region: GCP region

    Returns:
        Vertex AI model resource name
    """
    try:
        from google.cloud import aiplatform
    except ImportError:
        logger.error("Google Cloud AI Platform package not installed")
        logger.error("Install with: pip install google-cloud-aiplatform")
        return None

    logger.info(f"Registering model {model_name} to Vertex AI Model Registry")

    # Initialize Vertex AI client
    aiplatform.init(
        project=project_id,
        location=region,
    )

    # Upload the model to Model Registry
    model = aiplatform.Model.upload(
        display_name=model_name,
        artifact_uri=model_uri,
        serving_container_image_uri="us-docker.pkg.dev/vertex-ai/prediction/sklearn-cpu.1-0:latest",
        description="Enhanced forex ML model with exogenous data features",
        serving_container_predict_route="/predict",
        serving_container_health_route="/health",
    )

    logger.info(f"Registered model {model.resource_name}")
    return model.resource_name


def deploy_model_to_endpoint(
    model_resource_name: str,
    endpoint_name: str,
    project_id: str,
    region: str = "us-central1",
    machine_type: str = "n1-standard-2",
    min_nodes: int = 1,
) -> str:
    """
    Deploy model to a Vertex AI endpoint.

    Args:
        model_resource_name: Vertex AI model resource name
        endpoint_name: Name for the endpoint
        project_id: GCP project ID
        region: GCP region
        machine_type: Compute type for the endpoint
        min_nodes: Minimum number of nodes

    Returns:
        Endpoint resource name
    """
    try:
        from google.cloud import aiplatform
    except ImportError:
        logger.error("Google Cloud AI Platform package not installed")
        logger.error("Install with: pip install google-cloud-aiplatform")
        return None

    logger.info(f"Deploying model to endpoint {endpoint_name}")

    # Initialize Vertex AI client
    aiplatform.init(
        project=project_id,
        location=region,
    )

    # Get the model
    model = aiplatform.Model(model_resource_name)

    # Create or get endpoint
    try:
        # Try to get existing endpoint
        endpoints = aiplatform.Endpoint.list(
            filter=f'display_name="{endpoint_name}"', order_by="create_time desc"
        )

        if endpoints:
            endpoint = endpoints[0]
            logger.info(f"Using existing endpoint {endpoint.resource_name}")
        else:
            # Create new endpoint
            endpoint = aiplatform.Endpoint.create(
                display_name=endpoint_name,
                project=project_id,
                location=region,
            )
            logger.info(f"Created new endpoint {endpoint.resource_name}")
    except Exception as e:
        logger.error(f"Error creating endpoint: {e}")
        return None

    # Deploy the model to the endpoint
    try:
        # Create deployment config
        traffic_split = {"0": 100}  # Send 100% traffic to this model
        machine_spec = {"machine_type": machine_type}
        autoscaling_metric_specs = [
            {
                "metric_name": "aiplatform.googleapis.com/prediction/online/accelerator/duty_cycle",
                "target": 60,
            }
        ]
        min_replica_count = min_nodes
        max_replica_count = 2

        # Deploy model
        deployment = model.deploy(
            endpoint=endpoint,
            deployed_model_display_name=f"{endpoint_name}-{datetime.now().strftime('%Y%m%d')}",
            traffic_split=traffic_split,
            machine_type=machine_type,
            min_replica_count=min_replica_count,
            max_replica_count=max_replica_count,
            autoscaling_metric_specs=autoscaling_metric_specs,
        )

        logger.info(f"Deployed model to endpoint {endpoint.resource_name}")
        return endpoint.resource_name

    except Exception as e:
        logger.error(f"Error deploying model to endpoint: {e}")
        return None


def main():
    """Main deployment function"""
    parser = argparse.ArgumentParser(
        description="Deploy enhanced ML model to Vertex AI"
    )
    parser.add_argument(
        "--model-path",
        type=str,
        required=True,
        help="Path to trained model file (.joblib or .pkl)",
    )
    parser.add_argument(
        "--feature-info",
        type=str,
        help="Path to feature info JSON (if not specified, will try to infer)",
    )
    parser.add_argument(
        "--deploy",
        action="store_true",
        help="Whether to deploy the model to an endpoint",
    )
    parser.add_argument(
        "--project-id",
        type=str,
        default=os.environ.get("GCP_PROJECT", "fxml4"),
        help="GCP project ID",
    )
    parser.add_argument("--region", type=str, default="us-central1", help="GCP region")
    parser.add_argument(
        "--gcs-bucket",
        type=str,
        help="GCS bucket name (if not specified, will use {project-id}-models)",
    )
    parser.add_argument(
        "--endpoint-name",
        type=str,
        default="enhanced-forex-ml",
        help="Name for the Vertex AI endpoint",
    )
    args = parser.parse_args()

    # Get model name from path
    model_path = args.model_path
    model_name = os.path.basename(model_path).split(".")[0]

    # Set default GCS bucket if not specified
    if not args.gcs_bucket:
        args.gcs_bucket = f"{args.project_id}-models"

    # 1. Create and test the model adapter
    try:
        adapter = ModelAdapter(
            model_path=model_path,
            feature_info_path=args.feature_info,
            vertex_compatible=True,
        )

        # Test prediction with dummy data
        dummy_features = {}
        for feature in adapter.selected_features:
            dummy_features[feature] = 0.0

        test_prediction = adapter.predict(dummy_features)
        logger.info(f"Test prediction successful: {test_prediction}")

    except Exception as e:
        logger.error(f"Error creating or testing model adapter: {e}")
        return

    # 2. Upload model to GCS
    gcs_uri = upload_model_to_gcs(
        model_path=model_path,
        gcs_bucket=args.gcs_bucket,
        feature_info_path=args.feature_info,
    )

    if not gcs_uri:
        logger.error("Failed to upload model to GCS")
        return

    # If deployment not requested, exit here
    if not args.deploy:
        logger.info(
            f"Model uploaded to {gcs_uri}, use this URI to manually deploy to Vertex AI."
        )
        return

    # 3. Register model to Vertex AI Model Registry
    model_resource = register_model_to_vertex(
        model_uri=gcs_uri,
        model_name=model_name,
        project_id=args.project_id,
        region=args.region,
    )

    if not model_resource:
        logger.error("Failed to register model to Vertex AI")
        return

    # 4. Deploy model to endpoint
    endpoint_resource = deploy_model_to_endpoint(
        model_resource_name=model_resource,
        endpoint_name=args.endpoint_name,
        project_id=args.project_id,
        region=args.region,
    )

    if not endpoint_resource:
        logger.error("Failed to deploy model to endpoint")
        return

    logger.info("Model deployment completed successfully")
    logger.info(f"Endpoint resource: {endpoint_resource}")


if __name__ == "__main__":
    main()
