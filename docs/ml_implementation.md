# ML Implementation Design for FXML4

This document outlines the design decisions, architecture, and implementation details for the machine learning components of FXML4.

## Design Goals

1. **Developer Experience**
   - Support efficient local development on macOS/Apple Silicon
   - Provide intuitive APIs that follow scikit-learn patterns
   - Include comprehensive documentation and examples

2. **Scalability**
   - Support scaling from local development to cloud training
   - Handle large forex datasets spanning multiple years
   - Enable training of complex models beyond local hardware capabilities

3. **Trading-Specific Features**
   - Include metrics relevant to forex trading (profit factor, drawdown)
   - Support time series cross-validation and walk-forward testing
   - Handle multiple trading regimes and market conditions

4. **Integration**
   - Seamlessly integrate with other FXML4 components
   - Support both research workflows and production deployment
   - Maintain compatibility with both FXML2 and FXML3 patterns

## Architecture

The ML implementation follows a modular architecture with the following components:

### Core Model Classes

1. **ClassicMLModel**
   - Base class for traditional ML models (Random Forest, XGBoost, Logistic Regression)
   - Handles training, evaluation, and persistence
   - Includes hardware acceleration detection for Apple Silicon, CUDA, and ROCm
   - Provides trading-specific metrics and evaluation methods

2. **EnsembleModel**
   - Combines multiple base models
   - Supports various ensemble methods (voting, averaging, weighted)
   - Maintains compatibility with base model evaluation metrics

3. **Future: VertexAIModel**
   - Interface to Google Vertex AI for cloud-scale training
   - Supports both custom training and AutoML workflows
   - Handles data transfer to/from Google Cloud Storage
   - Maintains API compatibility with local models

### Supporting Components

1. **Feature Engineering**
   - Technical indicator extraction
   - Market regime classification
   - Economic data integration
   - Pivot point analysis (weekly, daily, and session-specific)
   - Advanced feature selection and dimensionality reduction:
     - Random Forest importance
     - Mutual Information
     - Recursive Feature Elimination (RFE)
     - Sequential Feature Selection
     - SHAP values
     - Correlation-aware selection
     - Cross-validated selection with stability analysis
     - Ensemble feature selection methods

2. **Evaluation Framework**
   - Trading-specific metrics (profit factor, win rate, drawdown)
   - Time series cross-validation utilities
   - Performance visualization methods

3. **Persistence Layer**
   - Model saving/loading with metadata
   - Version tracking for model evolution
   - Feature mapping preservation

## Key Design Decisions

1. **Selecting Base ML Algorithms**
   - Random Forest: Robust to noise, handles feature interactions, low risk of overfitting
   - XGBoost: High performance, good with imbalanced data, hardware acceleration
   - Logistic Regression: Interpretable baseline, useful in ensembles

2. **Hardware Acceleration**
   - Apple Silicon: Use Metal Performance Shaders via XGBoost's tree methods
   - NVIDIA GPUs: Use CUDA via XGBoost's GPU acceleration
   - CPU Fallback: Ensure all models work on standard hardware

3. **Cloud Integration Approach**
   - Google Vertex AI selected for:
     - Strong support for time series modeling
     - Both AutoML and custom training options
     - Reasonable pricing model
     - Seamless integration with GCP ecosystem
   - Hybrid approach: local development + cloud training

4. **Class Structure**
   - Traditional inheritance vs. composition decision
   - Favored composition for flexibility and future extensibility
   - Used strategy pattern for model selection and ensemble methods

5. **Persistence Format**
   - Model binary stored using joblib for efficiency and size
   - Metadata stored as JSON for human readability and editing
   - Compatibility maintained with FXML2 model formats

6. **Extension Points**
   - Plugin architecture for custom models
   - Hooks for custom metrics
   - Support for reinforcement learning integration in future

## Implementation Plan

### Phase 1: Local Models (Completed)
- Implement ClassicMLModel base class
- Add Random Forest, XGBoost, and Logistic Regression support
- Include Apple Silicon optimizations
- Implement EnsembleModel
- Create testing framework

### Phase 2: Cloud Integration (Next)
- Design VertexAIModel interface
- Implement data export/import utilities
- Add AutoML support
- Create cloud-local interoperability layer
- Develop deployment pipeline

### Phase 3: Advanced Features (In Progress)
- ✅ Implement sophisticated feature selection with cross-validation
   - Feature importance stability analysis
   - Correlation-aware selection
   - Cross-validation integration
   - Ensemble selection techniques
- ✅ Establish Google Vertex AI integration for cloud-scale training
   - Cloud model training and storage
   - Scalable infrastructure utilization
   - Model registry with versioning
- ✅ Integrate pivot point analysis from FXML2
   - Weekly pivot calculation
   - Session-specific pivot levels
   - Distance-to-pivot features
   - Pivot breakout detection
- 🔄 Add reinforcement learning models
- 🔄 Implement online learning capabilities
- 🔄 Create adaptive market regime detection
- 🔄 Develop explainable AI components

## Trade-offs and Considerations

### Local vs. Cloud Training
- **Local Advantages**: Faster iteration, lower cost, data privacy
- **Cloud Advantages**: Larger scale, more computational power, managed infrastructure
- **Our Approach**: Hybrid model with seamless transition between environments

### Model Complexity vs. Interpretability
- **Simple Models**: More interpretable, easier to debug, faster to train
- **Complex Models**: Potentially higher performance, capture more patterns
- **Our Approach**: Ensemble of models with varying complexity, emphasis on feature importance

### Training Time vs. Prediction Speed
- **Training Optimization**: Can be slower but more thorough on cloud
- **Inference Optimization**: Must be fast for real-time trading
- **Our Approach**: Separate optimization strategies for training vs. inference

### Data Volume vs. Quality
- **Large Datasets**: More comprehensive but slower to process
- **Curated Datasets**: Higher quality signals but potential selection bias
- **Our Approach**: Tiered data approach with preprocessing pipelines

## Conclusion

The ML implementation for FXML4 balances local development efficiency with cloud scalability, providing a flexible framework that grows with the project's needs. By supporting both traditional ML models and cloud-based training, we enable a smooth transition path from research to production deployment.

The design emphasizes trading-specific features while maintaining compatibility with standard ML workflows, allowing researchers to leverage familiar tools while adding domain-specific capabilities needed for forex trading.
