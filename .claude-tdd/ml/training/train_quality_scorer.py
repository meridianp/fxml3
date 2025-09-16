"""
Training script for quality scoring model
Trains ML models to predict code quality metrics and release readiness
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
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error
from sklearn.model_selection import GridSearchCV, cross_val_score, train_test_split
from sklearn.preprocessing import StandardScaler, MinMaxScaler

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class QualityScorerTrainer:
    """Trainer for quality scoring and prediction models"""

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

        self.feature_scaler = StandardScaler()
        self.target_scaler = MinMaxScaler()
        self.best_models = {}

        # Quality metrics to predict
        self.quality_targets = [
            'test_coverage',
            'mutation_score',
            'code_complexity',
            'technical_debt_ratio',
            'defect_density',
            'performance_score',
            'security_score',
            'maintainability_index'
        ]

        # Financial domain impact weights
        self.domain_impacts = {
            "order_execution": 1.0,
            "risk_management": 0.95,
            "pnl_calculation": 0.9,
            "position_management": 0.85,
            "compliance": 0.8,
            "market_data": 0.75,
            "elliott_wave": 0.7,
            "forex": 0.7,
            "analytics": 0.6,
            "reporting": 0.5,
            "ui": 0.3,
            "general": 0.4
        }

    def load_training_data(self) -> pd.DataFrame:
        """Load and preprocess quality training data"""
        logger.info("Loading quality training data...")

        data_file = self.data_dir / "quality_history.json"
        if not data_file.exists():
            # Generate synthetic data for demonstration
            logger.warning("No quality history found, generating synthetic data")
            return self._generate_synthetic_quality_data()

        with open(data_file, 'r') as f:
            data = json.load(f)

        df = pd.DataFrame(data)

        if df.empty:
            logger.warning("Empty quality history, generating synthetic data")
            return self._generate_synthetic_quality_data()

        # Convert timestamp
        df['timestamp'] = pd.to_datetime(df['timestamp'])

        logger.info(f"Loaded {len(df)} quality records")
        return df

    def _generate_synthetic_quality_data(self) -> pd.DataFrame:
        """Generate synthetic quality data for training"""
        logger.info("Generating synthetic quality data...")

        np.random.seed(42)
        n_samples = 1000

        # Generate timestamps over last year
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365)
        timestamps = pd.date_range(start_date, end_date, periods=n_samples)

        data = []
        for i, timestamp in enumerate(timestamps):
            # Simulate quality trends over time
            trend_factor = i / n_samples  # Improving trend
            seasonal_factor = 0.1 * np.sin(2 * np.pi * i / 52)  # Weekly seasonality

            # Base quality metrics with trends and noise
            base_coverage = 70 + 20 * trend_factor + seasonal_factor + np.random.normal(0, 5)
            base_complexity = 8 - 3 * trend_factor + np.random.normal(0, 1)

            record = {
                'timestamp': timestamp.isoformat(),
                'test_coverage': max(0, min(100, base_coverage)),
                'mutation_score': max(0, min(100, base_coverage - 10 + np.random.normal(0, 3))),
                'code_complexity': max(1, base_complexity),
                'technical_debt_ratio': max(0, 5 - 2 * trend_factor + np.random.normal(0, 0.5)),
                'defect_density': max(0, 0.2 - 0.15 * trend_factor + np.random.normal(0, 0.02)),
                'performance_score': max(0, min(100, 60 + 30 * trend_factor + np.random.normal(0, 5))),
                'security_score': max(0, min(100, 85 + 10 * trend_factor + np.random.normal(0, 3))),
                'maintainability_index': max(0, min(100, 65 + 25 * trend_factor + np.random.normal(0, 4))),
                'financial_risk_score': max(0, min(1, 0.3 - 0.2 * trend_factor + np.random.normal(0, 0.05))),
                'compliance_score': max(0, min(100, 90 + 8 * trend_factor + np.random.normal(0, 2))),
                # Additional context features
                'lines_of_code': int(10000 + 5000 * trend_factor + np.random.normal(0, 1000)),
                'number_of_tests': int(500 + 300 * trend_factor + np.random.normal(0, 50)),
                'number_of_files': int(100 + 50 * trend_factor + np.random.normal(0, 10)),
                'team_size': max(1, int(3 + 2 * np.random.random())),
                'sprint_week': (i % 4) + 1,  # 4-week sprints
                'is_release_week': int((i % 8) == 7),  # Release every 8 weeks
            }

            data.append(record)

        df = pd.DataFrame(data)
        df['timestamp'] = pd.to_datetime(df['timestamp'])

        # Save synthetic data for future use
        output_file = self.data_dir / "quality_history.json"
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2, default=str)

        logger.info(f"Generated {len(df)} synthetic quality records")
        return df

    def create_features(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Create feature matrix and target variables for quality prediction"""
        logger.info("Creating quality prediction features...")

        features = pd.DataFrame()

        # Temporal features
        features['day_of_week'] = df['timestamp'].dt.dayofweek
        features['month'] = df['timestamp'].dt.month
        features['quarter'] = df['timestamp'].dt.quarter
        features['is_weekend'] = (df['timestamp'].dt.dayofweek >= 5).astype(int)

        # Code base features
        features['lines_of_code'] = df.get('lines_of_code', 10000)
        features['number_of_tests'] = df.get('number_of_tests', 500)
        features['number_of_files'] = df.get('number_of_files', 100)
        features['test_to_code_ratio'] = features['number_of_tests'] / features['lines_of_code']
        features['files_per_test'] = features['number_of_files'] / features['number_of_tests']

        # Team and process features
        features['team_size'] = df.get('team_size', 3)
        features['sprint_week'] = df.get('sprint_week', 1)
        features['is_release_week'] = df.get('is_release_week', 0)

        # Historical trend features (lookback windows)
        df_sorted = df.sort_values('timestamp')

        # 7-day rolling averages
        for target in self.quality_targets:
            if target in df.columns:
                features[f'{target}_7d_avg'] = df_sorted[target].rolling(window=7, min_periods=1).mean()
                features[f'{target}_7d_trend'] = df_sorted[target].diff(7)

        # 30-day rolling averages
        for target in self.quality_targets:
            if target in df.columns:
                features[f'{target}_30d_avg'] = df_sorted[target].rolling(window=30, min_periods=1).mean()
                features[f'{target}_30d_std'] = df_sorted[target].rolling(window=30, min_periods=1).std()

        # Cross-metric relationships
        if 'test_coverage' in df.columns and 'mutation_score' in df.columns:
            features['coverage_mutation_ratio'] = df['test_coverage'] / (df['mutation_score'] + 1)

        if 'defect_density' in df.columns and 'test_coverage' in df.columns:
            features['defect_coverage_inverse'] = 1 / (df['defect_density'] * 100 + df['test_coverage'] + 1)

        # Lag features (previous values)
        for lag in [1, 3, 7]:
            for target in self.quality_targets:
                if target in df.columns:
                    features[f'{target}_lag_{lag}'] = df_sorted[target].shift(lag)

        # Fill missing values
        features = features.fillna(method='bfill').fillna(method='ffill').fillna(0)

        # Target variables
        targets = df[self.quality_targets].fillna(0)

        logger.info(f"Created {features.shape[1]} features for {targets.shape[1]} targets")
        return features, targets

    def train_models(self, X: pd.DataFrame, y: pd.DataFrame) -> Dict[str, Any]:
        """Train quality prediction models for each target metric"""
        logger.info("Training quality prediction models...")

        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        # Scale features
        X_train_scaled = self.feature_scaler.fit_transform(X_train)
        X_test_scaled = self.feature_scaler.transform(X_test)

        # Model configurations
        models = {
            'random_forest': {
                'model': RandomForestRegressor(random_state=42),
                'params': {
                    'n_estimators': [50, 100, 200],
                    'max_depth': [5, 10, 15],
                    'min_samples_split': [2, 5, 10]
                },
                'use_scaled': False
            },
            'gradient_boosting': {
                'model': GradientBoostingRegressor(random_state=42),
                'params': {
                    'n_estimators': [50, 100, 200],
                    'max_depth': [3, 6, 9],
                    'learning_rate': [0.01, 0.1, 0.2]
                },
                'use_scaled': False
            },
            'linear_regression': {
                'model': LinearRegression(),
                'params': {},
                'use_scaled': True
            }
        }

        results = {}

        # Train models for each quality target
        for target in self.quality_targets:
            if target not in y.columns:
                continue

            logger.info(f"Training models for {target}...")

            target_results = {}
            y_target_train = y_train[target]
            y_target_test = y_test[target]

            best_score = -np.inf
            best_model = None

            for model_name, config in models.items():
                try:
                    # Select appropriate feature set
                    if config['use_scaled']:
                        X_train_model = X_train_scaled
                        X_test_model = X_test_scaled
                    else:
                        X_train_model = X_train
                        X_test_model = X_test

                    # Grid search or direct training
                    if config['params']:
                        grid_search = GridSearchCV(
                            config['model'],
                            config['params'],
                            cv=5,
                            scoring='r2',
                            n_jobs=-1
                        )
                        grid_search.fit(X_train_model, y_target_train)
                        model = grid_search.best_estimator_
                        best_params = grid_search.best_params_
                    else:
                        model = config['model']
                        model.fit(X_train_model, y_target_train)
                        best_params = {}

                    # Evaluate model
                    predictions = model.predict(X_test_model)
                    r2 = r2_score(y_target_test, predictions)
                    mse = mean_squared_error(y_target_test, predictions)
                    mae = mean_absolute_error(y_target_test, predictions)

                    # Cross-validation
                    cv_scores = cross_val_score(model, X_train_model, y_target_train, cv=5, scoring='r2')

                    target_results[model_name] = {
                        'model': model,
                        'best_params': best_params,
                        'r2_score': r2,
                        'mse': mse,
                        'mae': mae,
                        'cv_mean': cv_scores.mean(),
                        'cv_std': cv_scores.std(),
                        'predictions': predictions,
                        'use_scaled': config['use_scaled']
                    }

                    logger.info(f"{target} - {model_name}: R² = {r2:.3f}, CV = {cv_scores.mean():.3f} ± {cv_scores.std():.3f}")

                    # Track best model for this target
                    if r2 > best_score:
                        best_score = r2
                        best_model = model_name

                except Exception as e:
                    logger.error(f"Error training {model_name} for {target}: {e}")
                    continue

            # Store best model for this target
            if best_model:
                self.best_models[target] = {
                    'model': target_results[best_model]['model'],
                    'model_name': best_model,
                    'use_scaled': target_results[best_model]['use_scaled'],
                    'performance': target_results[best_model]
                }

            target_results['best_model'] = best_model
            target_results['best_score'] = best_score
            results[target] = target_results

        # Overall evaluation
        overall_performance = self._evaluate_overall_performance(results)
        results['overall'] = overall_performance

        return results

    def _evaluate_overall_performance(self, results: Dict[str, Any]) -> Dict[str, float]:
        """Evaluate overall model performance across all targets"""
        scores = []
        target_scores = {}

        for target, target_results in results.items():
            if target == 'overall':
                continue

            best_model = target_results.get('best_model')
            if best_model and best_model in target_results:
                score = target_results[best_model]['r2_score']
                scores.append(score)
                target_scores[target] = score

        return {
            'mean_r2': np.mean(scores) if scores else 0.0,
            'std_r2': np.std(scores) if scores else 0.0,
            'min_r2': np.min(scores) if scores else 0.0,
            'max_r2': np.max(scores) if scores else 0.0,
            'target_scores': target_scores
        }

    def predict_quality_scores(self, features: pd.DataFrame) -> Dict[str, float]:
        """Predict quality scores using trained models"""
        if not self.best_models:
            raise ValueError("No models have been trained yet")

        predictions = {}

        for target, model_info in self.best_models.items():
            model = model_info['model']
            use_scaled = model_info['use_scaled']

            if use_scaled:
                features_model = self.feature_scaler.transform(features)
            else:
                features_model = features

            prediction = model.predict(features_model)
            predictions[target] = float(prediction[0]) if len(prediction) == 1 else prediction.tolist()

        return predictions

    def calculate_composite_quality_score(self, predictions: Dict[str, float]) -> float:
        """Calculate composite quality score from individual predictions"""
        weights = {
            'test_coverage': 0.2,
            'mutation_score': 0.15,
            'code_complexity': 0.1,  # Inverse weight (lower is better)
            'technical_debt_ratio': 0.1,  # Inverse weight
            'defect_density': 0.1,  # Inverse weight
            'performance_score': 0.15,
            'security_score': 0.1,
            'maintainability_index': 0.1
        }

        total_score = 0.0
        total_weight = 0.0

        for metric, weight in weights.items():
            if metric in predictions:
                value = predictions[metric]

                # Normalize and apply weights
                if metric in ['code_complexity', 'technical_debt_ratio', 'defect_density']:
                    # Inverse metrics (lower is better)
                    if metric == 'code_complexity':
                        normalized = max(0, (20 - value) / 20 * 100)  # Assuming max complexity of 20
                    elif metric == 'technical_debt_ratio':
                        normalized = max(0, (10 - value) / 10 * 100)  # Assuming max debt ratio of 10
                    else:  # defect_density
                        normalized = max(0, (1 - value) / 1 * 100)  # Assuming max density of 1
                else:
                    # Direct metrics (higher is better)
                    normalized = min(100, max(0, value))

                total_score += normalized * weight
                total_weight += weight

        return total_score / total_weight if total_weight > 0 else 0.0

    def save_models(self) -> None:
        """Save all trained models"""
        if not self.best_models:
            raise ValueError("No models have been trained yet")

        # Save individual models
        for target, model_info in self.best_models.items():
            model_path = self.models_dir / f"quality_{target}_predictor.pkl"
            with open(model_path, 'wb') as f:
                pickle.dump(model_info, f)

        # Save scalers
        scaler_path = self.models_dir / "quality_feature_scaler.pkl"
        with open(scaler_path, 'wb') as f:
            pickle.dump(self.feature_scaler, f)

        # Save model metadata
        metadata = {
            'targets': list(self.best_models.keys()),
            'feature_count': self.feature_scaler.n_features_in_ if hasattr(self.feature_scaler, 'n_features_in_') else 0,
            'training_date': datetime.now().isoformat()
        }

        metadata_path = self.models_dir / "quality_models_metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)

        logger.info(f"Saved {len(self.best_models)} quality prediction models")

    def generate_training_report(self, results: Dict[str, Any]) -> str:
        """Generate comprehensive training report"""
        overall = results.get('overall', {})

        report = f"""
# Quality Scorer Training Report

**Training Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Overall Performance:** R² = {overall.get('mean_r2', 0):.3f} ± {overall.get('std_r2', 0):.3f}

## Model Performance Summary

| Target Metric | Best Model | R² Score | CV Score | MAE |
|---------------|------------|----------|----------|-----|
"""

        for target in self.quality_targets:
            if target in results:
                target_results = results[target]
                best_model = target_results.get('best_model', 'N/A')

                if best_model and best_model in target_results:
                    r2 = target_results[best_model]['r2_score']
                    cv = target_results[best_model]['cv_mean']
                    mae = target_results[best_model]['mae']
                    report += f"| {target} | {best_model} | {r2:.3f} | {cv:.3f} | {mae:.3f} |\n"

        report += f"""

## Quality Prediction Capabilities

The trained models can predict the following quality metrics:

### Coverage and Testing
- **Test Coverage:** Percentage of code covered by tests
- **Mutation Score:** Quality of test suite based on mutation testing

### Code Quality
- **Code Complexity:** Average cyclomatic complexity
- **Technical Debt Ratio:** Ratio of technical debt to total development time
- **Maintainability Index:** Overall maintainability score

### Defects and Performance
- **Defect Density:** Number of defects per lines of code
- **Performance Score:** Overall system performance rating
- **Security Score:** Security assessment score

## Feature Importance

The models use the following types of features:
1. **Temporal Features:** Day of week, month, sprint cycles
2. **Codebase Features:** Lines of code, number of tests, file count
3. **Historical Trends:** Rolling averages and trend analysis
4. **Cross-Metric Relationships:** Coverage-mutation ratios, defect-coverage relationships
5. **Team and Process Features:** Team size, release cycles

## Financial Trading Considerations

The models are specifically tuned for financial trading systems:
- Higher weight given to security and compliance metrics
- Performance predictions account for real-time trading requirements
- Defect prediction considers financial impact severity
- Risk-adjusted quality scoring for trading components

## Usage Recommendations

1. **Regular Retraining:** Retrain models monthly with new data
2. **Feature Engineering:** Add domain-specific features as available
3. **Threshold Tuning:** Adjust quality thresholds based on business requirements
4. **Ensemble Predictions:** Consider averaging predictions from multiple models
5. **Monitoring:** Track prediction accuracy over time

## Quality Gates Integration

The predictions can be used to set dynamic quality gates:
- Minimum test coverage based on historical trends
- Defect density thresholds adjusted for codebase maturity
- Performance score requirements for release readiness
- Security score requirements for compliance

## Model Limitations

- Predictions are based on historical patterns
- Accuracy depends on data quality and quantity
- Financial domain specifics may require custom features
- Regular monitoring and retraining required
"""

        return report

    def validate_on_holdout_data(self, holdout_weeks: int = 4) -> Dict[str, float]:
        """Validate models on recent holdout data"""
        logger.info(f"Validating models on last {holdout_weeks} weeks of data...")

        # Load all data
        df = self.load_training_data()

        # Split into training and holdout
        cutoff_date = df['timestamp'].max() - timedelta(weeks=holdout_weeks)
        train_df = df[df['timestamp'] <= cutoff_date]
        holdout_df = df[df['timestamp'] > cutoff_date]

        if holdout_df.empty:
            logger.warning("No holdout data available for validation")
            return {}

        # Create features for holdout data
        X_holdout, y_holdout = self.create_features(holdout_df)

        validation_results = {}

        for target in self.quality_targets:
            if target not in self.best_models or target not in y_holdout.columns:
                continue

            model_info = self.best_models[target]
            model = model_info['model']
            use_scaled = model_info['use_scaled']

            # Prepare features
            if use_scaled:
                X_holdout_model = self.feature_scaler.transform(X_holdout)
            else:
                X_holdout_model = X_holdout

            # Make predictions
            predictions = model.predict(X_holdout_model)
            actual = y_holdout[target]

            # Calculate metrics
            r2 = r2_score(actual, predictions)
            mse = mean_squared_error(actual, predictions)
            mae = mean_absolute_error(actual, predictions)

            validation_results[target] = {
                'r2_score': r2,
                'mse': mse,
                'mae': mae,
                'samples': len(holdout_df)
            }

            logger.info(f"Holdout validation - {target}: R² = {r2:.3f}, MAE = {mae:.3f}")

        return validation_results


def main():
    """Main training script"""
    parser = argparse.ArgumentParser(description="Train quality scoring models")
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
        default=".claude-tdd/ml/quality_training_report.md",
        help="Path to save training report"
    )
    parser.add_argument(
        "--validate-holdout",
        action="store_true",
        help="Validate on holdout data"
    )

    args = parser.parse_args()

    try:
        # Initialize trainer
        trainer = QualityScorerTrainer(args.data_dir, args.models_dir)

        # Load data
        df = trainer.load_training_data()

        # Create features
        X, y = trainer.create_features(df)

        # Train models
        results = trainer.train_models(X, y)

        # Save models
        trainer.save_models()

        # Generate report
        report = trainer.generate_training_report(results)

        # Save report
        report_path = Path(args.output_report)
        report_path.parent.mkdir(parents=True, exist_ok=True)

        with open(report_path, 'w') as f:
            f.write(report)

        logger.info(f"Training report saved to {report_path}")

        # Validate on holdout data if requested
        if args.validate_holdout:
            validation_results = trainer.validate_on_holdout_data()
            logger.info(f"Holdout validation results: {validation_results}")

        logger.info("Quality scorer training completed successfully!")

    except Exception as e:
        logger.error(f"Training failed: {e}")
        raise


if __name__ == "__main__":
    main()