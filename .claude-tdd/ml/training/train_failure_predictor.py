"""
Training script for test failure prediction model
Trains ML models to predict test failure likelihood for intelligent test prioritization
"""

import argparse
import json
import logging
import pickle
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    roc_auc_score,
    roc_curve,
)
from sklearn.model_selection import (
    GridSearchCV,
    cross_val_score,
    train_test_split,
)
from sklearn.preprocessing import StandardScaler

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class FailurePredictorTrainer:
    """Trainer for test failure prediction models"""

    def __init__(self, data_dir: str, models_dir: str):
        """Initialize the trainer

        Args:
            data_dir: Directory containing training data
            models_dir: Directory to save trained models
        """
        self.data_dir = Path(data_dir)
        self.models_dir = Path(models_dir)

        # Ensure directories exist
        self.models_dir.mkdir(parents=True, exist_ok=True)

        self.scaler = StandardScaler()
        self.best_model = None
        self.best_score = 0.0

        # Financial domain weights for training
        self.domain_weights = {
            "order_execution": 2.0,  # Critical failures get higher weight
            "risk_management": 1.8,
            "pnl_calculation": 1.6,
            "position_management": 1.4,
            "compliance": 1.2,
            "market_data": 1.0,
            "elliott_wave": 0.8,
            "forex": 0.8,
            "analytics": 0.6,
            "reporting": 0.4,
            "ui": 0.2,
            "general": 0.5
        }

    def load_training_data(self) -> pd.DataFrame:
        """Load and preprocess training data"""
        logger.info("Loading training data...")

        data_file = self.data_dir / "execution_history.json"
        if not data_file.exists():
            raise FileNotFoundError(f"Training data not found: {data_file}")

        with open(data_file, 'r') as f:
            data = json.load(f)

        df = pd.DataFrame(data)

        if df.empty:
            raise ValueError("No training data available")

        # Convert timestamp
        df['timestamp'] = pd.to_datetime(df['timestamp'])

        # Create failure target variable
        df['failed'] = (df['status'] == 'failed').astype(int)

        logger.info(f"Loaded {len(df)} training records")
        logger.info(f"Failure rate: {df['failed'].mean():.3f}")

        return df

    def create_features(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
        """Create feature matrix and target variable"""
        logger.info("Creating features...")

        features = pd.DataFrame()

        # Basic test features
        features['test_name_length'] = df['test_name'].str.len()
        features['test_name_underscores'] = df['test_name'].str.count('_')
        features['test_name_numbers'] = df['test_name'].str.count(r'\d')

        # Test type features
        features['is_integration'] = df['test_name'].str.contains('integration', case=False).astype(int)
        features['is_unit'] = df['test_name'].str.contains('unit', case=False).astype(int)
        features['is_performance'] = df['test_name'].str.contains('performance', case=False).astype(int)
        features['is_edge_case'] = df['test_name'].str.contains('edge', case=False).astype(int)

        # Execution features
        features['execution_time_log'] = np.log1p(df['execution_time'])
        features['complexity_score'] = df['complexity_score']

        # Domain features (one-hot encoding)
        domain_dummies = pd.get_dummies(df['financial_domain'], prefix='domain')
        features = pd.concat([features, domain_dummies], axis=1)

        # Risk level features
        risk_mapping = {'low': 1, 'medium': 2, 'high': 3, 'critical': 4}
        features['risk_level_numeric'] = df['risk_level'].map(risk_mapping).fillna(2)

        # Temporal features
        features['hour'] = df['timestamp'].dt.hour
        features['day_of_week'] = df['timestamp'].dt.dayofweek
        features['is_weekend'] = (df['timestamp'].dt.dayofweek >= 5).astype(int)

        # Historical features (lookback)
        df_sorted = df.sort_values('timestamp')
        features['failures_last_week'] = self._calculate_recent_failures(df_sorted, 7)
        features['failures_last_month'] = self._calculate_recent_failures(df_sorted, 30)

        # Change features
        features['changed_files_count'] = df['changed_files'].apply(
            lambda x: len(x) if isinstance(x, list) else 0
        )
        features['coverage_delta'] = df['coverage_delta'].fillna(0)

        # Financial keywords in test name
        financial_keywords = [
            'order', 'trade', 'position', 'risk', 'pnl', 'price',
            'execute', 'market', 'forex', 'currency', 'elliott', 'wave',
            'fibonacci', 'compliance', 'regulation', 'audit'
        ]

        for keyword in financial_keywords:
            features[f'has_{keyword}'] = df['test_name'].str.contains(
                keyword, case=False
            ).astype(int)

        # Fill missing values
        features = features.fillna(0)

        # Target variable with sample weights
        target = df['failed']
        sample_weights = df['financial_domain'].map(self.domain_weights).fillna(1.0)

        logger.info(f"Created {features.shape[1]} features")
        return features, target, sample_weights

    def _calculate_recent_failures(self, df_sorted: pd.DataFrame, days: int) -> pd.Series:
        """Calculate number of failures in recent days for each test"""
        failures = []

        for i, row in df_sorted.iterrows():
            test_name = row['test_name']
            current_time = row['timestamp']
            cutoff_time = current_time - timedelta(days=days)

            # Count failures for this test in the lookback period
            mask = (
                (df_sorted['test_name'] == test_name) &
                (df_sorted['timestamp'] >= cutoff_time) &
                (df_sorted['timestamp'] < current_time) &
                (df_sorted['status'] == 'failed')
            )

            failure_count = df_sorted[mask].shape[0]
            failures.append(failure_count)

        return pd.Series(failures, index=df_sorted.index)

    def train_models(self, X: pd.DataFrame, y: pd.Series, sample_weights: pd.Series) -> Dict[str, Any]:
        """Train multiple models and select the best one"""
        logger.info("Training failure prediction models...")

        # Split data
        X_train, X_test, y_train, y_test, weights_train, weights_test = train_test_split(
            X, y, sample_weights, test_size=0.2, random_state=42, stratify=y
        )

        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)

        models = {
            'gradient_boosting': {
                'model': GradientBoostingClassifier(random_state=42),
                'params': {
                    'n_estimators': [50, 100, 200],
                    'max_depth': [3, 6, 9],
                    'learning_rate': [0.01, 0.1, 0.2]
                }
            },
            'random_forest': {
                'model': RandomForestClassifier(random_state=42, class_weight='balanced'),
                'params': {
                    'n_estimators': [50, 100, 200],
                    'max_depth': [5, 10, 15],
                    'min_samples_split': [2, 5, 10]
                }
            },
            'logistic_regression': {
                'model': LogisticRegression(random_state=42, class_weight='balanced'),
                'params': {
                    'C': [0.1, 1.0, 10.0],
                    'penalty': ['l1', 'l2'],
                    'solver': ['liblinear']
                }
            }
        }

        results = {}

        for model_name, model_config in models.items():
            logger.info(f"Training {model_name}...")

            # Grid search with cross-validation
            grid_search = GridSearchCV(
                model_config['model'],
                model_config['params'],
                cv=5,
                scoring='roc_auc',
                n_jobs=-1,
                verbose=1
            )

            # Use scaled features for logistic regression, original for tree-based models
            if model_name == 'logistic_regression':
                grid_search.fit(X_train_scaled, y_train, sample_weight=weights_train)
                best_model = grid_search.best_estimator_
                predictions = best_model.predict_proba(X_test_scaled)[:, 1]
            else:
                grid_search.fit(X_train, y_train, sample_weight=weights_train)
                best_model = grid_search.best_estimator_
                predictions = best_model.predict_proba(X_test)[:, 1]

            # Evaluate model
            auc_score = roc_auc_score(y_test, predictions)

            # Cross-validation score
            if model_name == 'logistic_regression':
                cv_scores = cross_val_score(best_model, X_train_scaled, y_train, cv=5, scoring='roc_auc')
            else:
                cv_scores = cross_val_score(best_model, X_train, y_train, cv=5, scoring='roc_auc')

            results[model_name] = {
                'model': best_model,
                'best_params': grid_search.best_params_,
                'auc_score': auc_score,
                'cv_mean': cv_scores.mean(),
                'cv_std': cv_scores.std(),
                'predictions': predictions
            }

            logger.info(f"{model_name} - AUC: {auc_score:.3f}, CV: {cv_scores.mean():.3f} ± {cv_scores.std():.3f}")

            # Track best model
            if auc_score > self.best_score:
                self.best_score = auc_score
                self.best_model = best_model

        # Generate detailed evaluation for best model
        best_model_name = max(results.keys(), key=lambda k: results[k]['auc_score'])
        logger.info(f"Best model: {best_model_name} (AUC: {results[best_model_name]['auc_score']:.3f})")

        # Detailed evaluation
        best_predictions = results[best_model_name]['predictions']
        classification_rep = classification_report(
            y_test,
            (best_predictions > 0.5).astype(int),
            target_names=['Pass', 'Fail']
        )

        results['evaluation'] = {
            'best_model': best_model_name,
            'classification_report': classification_rep,
            'confusion_matrix': confusion_matrix(y_test, (best_predictions > 0.5).astype(int)).tolist(),
            'feature_importance': self._get_feature_importance(results[best_model_name]['model'], X.columns)
        }

        return results

    def _get_feature_importance(self, model, feature_names: List[str]) -> Dict[str, float]:
        """Get feature importance from trained model"""
        if hasattr(model, 'feature_importances_'):
            # Tree-based models
            importance = model.feature_importances_
        elif hasattr(model, 'coef_'):
            # Linear models
            importance = np.abs(model.coef_[0])
        else:
            return {}

        # Create feature importance dictionary
        feature_importance = dict(zip(feature_names, importance))

        # Sort by importance
        sorted_features = sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)

        return dict(sorted_features[:20])  # Top 20 features

    def save_model(self, model_name: str = "failure_predictor") -> None:
        """Save the best trained model"""
        if self.best_model is None:
            raise ValueError("No model has been trained yet")

        model_path = self.models_dir / f"{model_name}.pkl"
        scaler_path = self.models_dir / "feature_scaler.pkl"

        # Save model
        with open(model_path, 'wb') as f:
            pickle.dump(self.best_model, f)

        # Save scaler
        with open(scaler_path, 'wb') as f:
            pickle.dump(self.scaler, f)

        logger.info(f"Saved model to {model_path}")
        logger.info(f"Saved scaler to {scaler_path}")

    def generate_training_report(self, results: Dict[str, Any]) -> str:
        """Generate comprehensive training report"""
        report = f"""
# Test Failure Predictor Training Report

**Training Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Best Model:** {results['evaluation']['best_model']}
**Best AUC Score:** {self.best_score:.3f}

## Model Performance Summary

"""

        for model_name, result in results.items():
            if model_name == 'evaluation':
                continue

            report += f"""
### {model_name.title().replace('_', ' ')}
- **AUC Score:** {result['auc_score']:.3f}
- **Cross-Validation:** {result['cv_mean']:.3f} ± {result['cv_std']:.3f}
- **Best Parameters:** {result['best_params']}
"""

        report += f"""

## Best Model Evaluation

### Classification Report
```
{results['evaluation']['classification_report']}
```

### Confusion Matrix
```
{np.array(results['evaluation']['confusion_matrix'])}
```

### Top Feature Importance
"""

        for feature, importance in list(results['evaluation']['feature_importance'].items())[:10]:
            report += f"- **{feature}:** {importance:.4f}\n"

        report += f"""

## Model Usage

The trained model can predict test failure probability based on:
1. Test characteristics (name, type, complexity)
2. Historical failure patterns
3. Financial domain and risk level
4. Recent changes and coverage impact
5. Temporal patterns

## Financial Domain Considerations

The model gives higher weight to failures in critical financial domains:
- Order execution and trading operations
- Risk management systems
- PnL calculations and position management
- Compliance and regulatory functions

## Recommendations

1. Use this model for intelligent test prioritization
2. Focus testing efforts on high-risk financial components
3. Monitor model performance and retrain monthly
4. Consider additional features from code analysis tools
5. Implement A/B testing to validate prioritization effectiveness
"""

        return report

    def evaluate_model_on_recent_data(self, days_back: int = 30) -> Dict[str, float]:
        """Evaluate model performance on recent data"""
        if self.best_model is None:
            raise ValueError("No model has been trained yet")

        logger.info(f"Evaluating model on data from last {days_back} days...")

        # Load recent data
        df = self.load_training_data()
        cutoff_date = datetime.now() - timedelta(days=days_back)
        recent_df = df[df['timestamp'] >= cutoff_date]

        if recent_df.empty:
            logger.warning("No recent data available for evaluation")
            return {}

        # Create features
        X_recent, y_recent, _ = self.create_features(recent_df)

        # Scale features if needed
        if isinstance(self.best_model, LogisticRegression):
            X_recent_scaled = self.scaler.transform(X_recent)
            predictions = self.best_model.predict_proba(X_recent_scaled)[:, 1]
        else:
            predictions = self.best_model.predict_proba(X_recent)[:, 1]

        # Calculate metrics
        auc_score = roc_auc_score(y_recent, predictions)

        # Precision at different thresholds
        thresholds = [0.1, 0.3, 0.5, 0.7, 0.9]
        precision_at_k = {}

        for threshold in thresholds:
            predicted_failures = predictions >= threshold
            if predicted_failures.sum() > 0:
                precision = y_recent[predicted_failures].mean()
                precision_at_k[f"precision_at_{threshold}"] = precision

        metrics = {
            "recent_auc": auc_score,
            "recent_data_points": len(recent_df),
            "recent_failure_rate": y_recent.mean(),
            **precision_at_k
        }

        logger.info(f"Recent performance - AUC: {auc_score:.3f}, Failure rate: {y_recent.mean():.3f}")
        return metrics


def main():
    """Main training script"""
    parser = argparse.ArgumentParser(description="Train test failure prediction model")
    parser.add_argument(
        "--data-dir",
        default=".claude-tdd/ml/data",
        help="Directory containing training data"
    )
    parser.add_argument(
        "--models-dir",
        default=".claude-tdd/ml/models",
        help="Directory to save trained models"
    )
    parser.add_argument(
        "--output-report",
        default=".claude-tdd/ml/training_report.md",
        help="Path to save training report"
    )
    parser.add_argument(
        "--evaluate-recent",
        action="store_true",
        help="Evaluate model on recent data"
    )

    args = parser.parse_args()

    try:
        # Initialize trainer
        trainer = FailurePredictorTrainer(args.data_dir, args.models_dir)

        # Load data
        df = trainer.load_training_data()

        # Create features
        X, y, sample_weights = trainer.create_features(df)

        # Train models
        results = trainer.train_models(X, y, sample_weights)

        # Save best model
        trainer.save_model()

        # Generate report
        report = trainer.generate_training_report(results)

        # Save report
        report_path = Path(args.output_report)
        report_path.parent.mkdir(parents=True, exist_ok=True)

        with open(report_path, 'w') as f:
            f.write(report)

        logger.info(f"Training report saved to {report_path}")

        # Evaluate on recent data if requested
        if args.evaluate_recent:
            recent_metrics = trainer.evaluate_model_on_recent_data()
            logger.info(f"Recent performance metrics: {recent_metrics}")

        logger.info("Training completed successfully!")

    except Exception as e:
        logger.error(f"Training failed: {e}")
        raise


if __name__ == "__main__":
    main()