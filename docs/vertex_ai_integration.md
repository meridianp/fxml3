# Google Vertex AI Integration for FXML4

This document outlines how the FXML4 platform integrates with Google Cloud Vertex AI for machine learning model training, deployment, and management.

## Overview

FXML4 leverages Google Vertex AI for the following capabilities:

1. **Scalable Training Infrastructure**: Train ML models on powerful cloud infrastructure
2. **Model Versioning and Registry**: Store, version, and manage trained models
3. **Online Prediction Endpoints**: Deploy models for real-time trading signals
4. **AutoML**: Automatically optimize model hyperparameters
5. **Model Monitoring**: Monitor model performance in production

## Implementation Details

The integration is built in multiple layers:

### 1. ML Model Pipeline

The core ML pipeline in FXML4 is designed to work both locally and with Vertex AI:

- **Data Preparation**: Feature engineering and preprocessing pipeline
- **Model Training**: Framework-agnostic training with scikit-learn, XGBoost, etc.
- **Model Evaluation**: Consistent evaluation metrics across environments
- **Model Serialization**: Standard format for model saving/loading

### 2. Vertex AI Integration Layer

The `vertex_ai.py` module provides a bridge between FXML4 models and Vertex AI:

- **VertexAIModel**: Class for managing models in Vertex AI
- **VertexAITrainer**: Class for training models in Vertex AI
- **AutoMLModel**: Class for AutoML model training

### 3. GBP/USD Model Implementation

The GBP/USD model is fully integrated with Vertex AI:

- **Feature Engineering**: Currency-specific technical indicators
- **Training Pipeline**: 4-hour timeframe optimized model
- **Signal Generation**: ML-based trading signal generation
- **Cloud Deployment**: Automatic deployment to Vertex AI

## Usage Instructions

### Setting up Google Cloud

1. Create a Google Cloud project:
   ```bash
   gcloud projects create fxml4 --name="FXML4 Trading Platform"
   ```

2. Enable required APIs:
   ```bash
   gcloud services enable aiplatform.googleapis.com \
       artifactregistry.googleapis.com \
       compute.googleapis.com \
       storage.googleapis.com
   ```

3. Create GCS buckets for model storage:
   ```bash
   gsutil mb -l us-central1 gs://fxml4-models
   gsutil mb -l us-central1 gs://fxml4-training
   ```

4. Set up authentication:
   ```bash
   gcloud auth application-default login
   ```

### Environment Configuration

Add the following to your `.env` file:

```
GCP_PROJECT=fxml4
GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json
```

### Training a Model Locally and Registering with Vertex AI

```python
from fxml4.ml.gbpusd_model import GBPUSDModel
from ml.vertex_ai import VertexAIModel

# Train model locally
model = GBPUSDModel(model_type="random_forest")
features = model.prepare_features(data)
model.train(features, target_col="target_12")

# Register with Vertex AI
vertex_model = VertexAIModel(
    project_id="fxml4",
    location="us-central1"
)
result = vertex_model.register_model(
    model=model,
    version="v1",
    description="GBP/USD prediction model"
)
```

### Training a Model on Vertex AI

```python
from ml.vertex_ai import VertexAITrainer

# Initialize trainer
trainer = VertexAITrainer(
    project_id="fxml4",
    location="us-central1"
)

# Submit training job
job = trainer.submit_training_job(
    model_type="xgboost",
    model_params={"n_estimators": 100, "max_depth": 6},
    training_data_uri="gs://fxml4-training/gbpusd.csv",
    target_column="target",
    job_name="gbpusd_training"
)
```

### Using AutoML for Automated Model Optimization

```python
from ml.vertex_ai import AutoMLModel

# Initialize AutoML
automl = AutoMLModel(
    name="gbpusd_automl",
    project_id="fxml4",
    location="us-central1"
)

# Train model
automl.train(
    training_data_uri="gs://fxml4-training/gbpusd.csv",
    target_column="target",
    training_budget_hours=4
)
```

## Command-Line Utilities

FXML4 includes command-line utilities for managing Vertex AI models:

```bash
# Train and register a model
python examples/vertex_ai_gbpusd.py --data-path output/C_GBPUSD_4h.parquet

# Use an existing model
python examples/vertex_ai_gbpusd.py --skip-training --model-name gbpusd_random_forest_20250313

# Train with AutoML
python examples/vertex_ai_gbpusd.py --automl --data-path output/C_GBPUSD_4h.parquet
```

## Directory Structure

The Vertex AI integration code is organized as follows:

```
fxml4/
├── ml/
│   └── vertex_ai.py           # Core Vertex AI integration
├── examples/
│   ├── vertex_ai_example.py   # Basic example script
│   ├── vertex_ai_gbpusd.py    # GBP/USD specific integration
│   └── train_with_vertex.py   # Advanced training script
└── docs/
    └── vertex_ai_integration.md # This documentation
```

## Best Practices

1. **Local Testing First**: Always test models locally before training in the cloud
2. **Version Management**: Use clear versioning for model iterations
3. **Pipeline Automation**: Automate the pipeline from training to deployment
4. **Cost Management**: Monitor resource usage to control cloud costs
5. **Model Monitoring**: Implement drift detection and monitoring

## Troubleshooting

### Authentication Issues

If you encounter authentication errors:

```bash
gcloud auth application-default login
gcloud config set project fxml4
```

### API Enablement

Ensure all required APIs are enabled:

```bash
gcloud services enable aiplatform.googleapis.com
```

### Storage Access

Verify your GCS buckets and permissions:

```bash
gsutil ls gs://fxml4-models
```

## Future Enhancements

1. **Feature Store Integration**: Implement Vertex AI Feature Store
2. **Continuous Training**: Set up automated retraining pipelines
3. **Multi-Model Ensemble**: Deploy ensemble models with Vertex AI
4. **A/B Testing**: Implement model A/B testing framework
5. **TensorFlow Models**: Support for TensorFlow models

---

For more information, refer to the [Google Vertex AI documentation](https://cloud.google.com/vertex-ai/docs).
