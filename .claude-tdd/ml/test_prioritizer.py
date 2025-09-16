"""
Intelligent Test Prioritizer for FXML4 Claude TDD Framework
ML-powered test prioritization based on failure prediction and risk analysis
"""

import json
import logging
import pickle
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)


@dataclass
class TestExecutionRecord:
    """Record of test execution for training ML models"""
    test_name: str
    file_path: str
    execution_time: float
    status: str  # passed, failed, skipped, error
    timestamp: datetime
    changed_files: List[str]
    commit_hash: str
    branch: str
    coverage_delta: float
    complexity_score: int
    financial_domain: str
    risk_level: str


@dataclass
class TestPriority:
    """Test with calculated priority score"""
    test_name: str
    file_path: str
    priority_score: float
    failure_probability: float
    risk_impact: float
    execution_time_prediction: float
    change_impact_score: float
    domain_criticality: float
    last_failure: Optional[datetime]
    reason: str


class IntelligentTestPrioritizer:
    """ML-powered test prioritization for financial trading systems"""

    def __init__(self, data_dir: str = None, models_dir: str = None):
        """Initialize the test prioritizer

        Args:
            data_dir: Directory containing historical test execution data
            models_dir: Directory containing trained ML models
        """
        self.data_dir = Path(data_dir) if data_dir else Path.cwd() / ".claude-tdd" / "ml" / "data"
        self.models_dir = Path(models_dir) if models_dir else Path.cwd() / ".claude-tdd" / "ml" / "models"

        # Ensure directories exist
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.models_dir.mkdir(parents=True, exist_ok=True)

        # ML models for different predictions
        self.failure_predictor = None
        self.execution_time_predictor = None
        self.change_impact_predictor = None

        # Feature preprocessing
        self.scaler = StandardScaler()
        self.text_vectorizer = TfidfVectorizer(max_features=1000, stop_words='english')

        # Financial domain weights
        self.domain_criticality = {
            "order_execution": 1.0,  # Most critical
            "risk_management": 0.95,
            "pnl_calculation": 0.9,
            "position_management": 0.85,
            "compliance": 0.8,
            "market_data": 0.75,
            "elliott_wave": 0.7,
            "forex": 0.7,
            "analytics": 0.6,
            "reporting": 0.5,
            "ui": 0.3,  # Least critical for trading
            "general": 0.4
        }

        # Load existing models if available
        self._load_models()

    def collect_execution_data(self, execution_results: List[Dict[str, Any]]) -> None:
        """Collect test execution data for ML training

        Args:
            execution_results: List of test execution results from pytest
        """
        records = []

        for result in execution_results:
            record = TestExecutionRecord(
                test_name=result.get("nodeid", ""),
                file_path=result.get("file_path", ""),
                execution_time=result.get("duration", 0.0),
                status=result.get("outcome", "unknown"),
                timestamp=datetime.now(),
                changed_files=result.get("changed_files", []),
                commit_hash=result.get("commit_hash", ""),
                branch=result.get("branch", "main"),
                coverage_delta=result.get("coverage_delta", 0.0),
                complexity_score=result.get("complexity_score", 1),
                financial_domain=result.get("financial_domain", "general"),
                risk_level=result.get("risk_level", "low")
            )
            records.append(record)

        # Save to persistent storage
        self._save_execution_records(records)

    def prioritize_tests(
        self,
        test_list: List[str],
        changed_files: List[str] = None,
        target_count: int = None,
        strategy: str = "ml_hybrid"
    ) -> List[TestPriority]:
        """Prioritize tests based on ML predictions and heuristics

        Args:
            test_list: List of test identifiers to prioritize
            changed_files: Files that have changed in current commit
            target_count: Maximum number of tests to return (None for all)
            strategy: Prioritization strategy (ml_hybrid, risk_based, time_optimal)

        Returns:
            List of prioritized tests with scores
        """
        changed_files = changed_files or []

        if strategy == "ml_hybrid":
            return self._prioritize_ml_hybrid(test_list, changed_files, target_count)
        elif strategy == "risk_based":
            return self._prioritize_risk_based(test_list, changed_files, target_count)
        elif strategy == "time_optimal":
            return self._prioritize_time_optimal(test_list, changed_files, target_count)
        else:
            raise ValueError(f"Unknown prioritization strategy: {strategy}")

    def _prioritize_ml_hybrid(
        self,
        test_list: List[str],
        changed_files: List[str],
        target_count: int = None
    ) -> List[TestPriority]:
        """ML-powered hybrid prioritization strategy"""
        priorities = []

        for test_name in test_list:
            # Extract features for ML prediction
            features = self._extract_test_features(test_name, changed_files)

            # Predict failure probability
            failure_prob = self._predict_failure_probability(features)

            # Predict execution time
            exec_time_pred = self._predict_execution_time(features)

            # Calculate change impact score
            change_impact = self._calculate_change_impact(test_name, changed_files)

            # Get domain criticality
            domain = self._infer_financial_domain(test_name)
            domain_crit = self.domain_criticality.get(domain, 0.5)

            # Calculate risk impact
            risk_impact = self._calculate_risk_impact(test_name, features)

            # Get last failure date
            last_failure = self._get_last_failure_date(test_name)

            # Calculate composite priority score
            priority_score = self._calculate_priority_score(
                failure_prob, risk_impact, domain_crit, change_impact, exec_time_pred
            )

            # Generate reasoning
            reason = self._generate_priority_reason(
                failure_prob, risk_impact, domain_crit, change_impact
            )

            priorities.append(TestPriority(
                test_name=test_name,
                file_path=self._get_test_file_path(test_name),
                priority_score=priority_score,
                failure_probability=failure_prob,
                risk_impact=risk_impact,
                execution_time_prediction=exec_time_pred,
                change_impact_score=change_impact,
                domain_criticality=domain_crit,
                last_failure=last_failure,
                reason=reason
            ))

        # Sort by priority score (descending)
        priorities.sort(key=lambda x: x.priority_score, reverse=True)

        # Return requested count
        if target_count:
            return priorities[:target_count]
        return priorities

    def _prioritize_risk_based(
        self,
        test_list: List[str],
        changed_files: List[str],
        target_count: int = None
    ) -> List[TestPriority]:
        """Risk-based prioritization for financial systems"""
        priorities = []

        for test_name in test_list:
            # Focus on financial risk impact
            domain = self._infer_financial_domain(test_name)
            domain_crit = self.domain_criticality.get(domain, 0.5)

            # High priority for:
            # 1. Order execution tests
            # 2. Risk management tests
            # 3. PnL calculation tests
            # 4. Recently failed tests

            features = self._extract_test_features(test_name, changed_files)
            risk_impact = self._calculate_risk_impact(test_name, features)
            change_impact = self._calculate_change_impact(test_name, changed_files)
            last_failure = self._get_last_failure_date(test_name)

            # Risk-weighted priority
            priority_score = (domain_crit * 0.5) + (risk_impact * 0.3) + (change_impact * 0.2)

            # Boost for recent failures
            if last_failure and (datetime.now() - last_failure).days < 7:
                priority_score *= 1.5

            priorities.append(TestPriority(
                test_name=test_name,
                file_path=self._get_test_file_path(test_name),
                priority_score=priority_score,
                failure_probability=0.0,  # Not calculated in risk-based
                risk_impact=risk_impact,
                execution_time_prediction=0.0,
                change_impact_score=change_impact,
                domain_criticality=domain_crit,
                last_failure=last_failure,
                reason=f"Risk-based priority: {domain} domain (criticality: {domain_crit:.2f})"
            ))

        priorities.sort(key=lambda x: x.priority_score, reverse=True)

        if target_count:
            return priorities[:target_count]
        return priorities

    def _prioritize_time_optimal(
        self,
        test_list: List[str],
        changed_files: List[str],
        target_count: int = None
    ) -> List[TestPriority]:
        """Time-optimal prioritization for fast feedback"""
        priorities = []

        for test_name in test_list:
            features = self._extract_test_features(test_name, changed_files)

            # Predict execution time
            exec_time_pred = self._predict_execution_time(features)

            # Calculate change impact
            change_impact = self._calculate_change_impact(test_name, changed_files)

            # Get domain criticality
            domain = self._infer_financial_domain(test_name)
            domain_crit = self.domain_criticality.get(domain, 0.5)

            # Priority = (impact + criticality) / time
            # This favors high-impact, low-time tests
            priority_score = (change_impact + domain_crit) / max(exec_time_pred, 0.1)

            priorities.append(TestPriority(
                test_name=test_name,
                file_path=self._get_test_file_path(test_name),
                priority_score=priority_score,
                failure_probability=0.0,
                risk_impact=0.0,
                execution_time_prediction=exec_time_pred,
                change_impact_score=change_impact,
                domain_criticality=domain_crit,
                last_failure=None,
                reason=f"Time-optimal: High impact ({change_impact:.2f}) / Low time ({exec_time_pred:.2f}s)"
            ))

        priorities.sort(key=lambda x: x.priority_score, reverse=True)

        if target_count:
            return priorities[:target_count]
        return priorities

    def train_models(self, retrain: bool = False) -> Dict[str, float]:
        """Train ML models for test prioritization

        Args:
            retrain: Whether to retrain existing models

        Returns:
            Dictionary of model performance metrics
        """
        # Load historical execution data
        df = self._load_execution_data()

        if df.empty:
            logger.warning("No execution data available for training")
            return {}

        metrics = {}

        # Train failure predictor
        if self.failure_predictor is None or retrain:
            metrics["failure_predictor"] = self._train_failure_predictor(df)

        # Train execution time predictor
        if self.execution_time_predictor is None or retrain:
            metrics["execution_time_predictor"] = self._train_execution_time_predictor(df)

        # Train change impact predictor
        if self.change_impact_predictor is None or retrain:
            metrics["change_impact_predictor"] = self._train_change_impact_predictor(df)

        # Save models
        self._save_models()

        return metrics

    def _train_failure_predictor(self, df: pd.DataFrame) -> float:
        """Train failure prediction model"""
        logger.info("Training failure prediction model...")

        # Prepare features
        features = self._prepare_features_for_training(df)
        target = (df['status'] == 'failed').astype(int)

        if features.empty or len(features.columns) == 0:
            logger.warning("No features available for failure predictor training")
            return 0.0

        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            features, target, test_size=0.2, random_state=42, stratify=target
        )

        # Train model
        self.failure_predictor = GradientBoostingClassifier(
            n_estimators=100,
            max_depth=6,
            learning_rate=0.1,
            random_state=42
        )

        self.failure_predictor.fit(X_train, y_train)

        # Evaluate
        predictions = self.failure_predictor.predict_proba(X_test)[:, 1]
        auc_score = roc_auc_score(y_test, predictions)

        logger.info(f"Failure predictor AUC: {auc_score:.3f}")
        return auc_score

    def _train_execution_time_predictor(self, df: pd.DataFrame) -> float:
        """Train execution time prediction model"""
        logger.info("Training execution time prediction model...")

        # Prepare features
        features = self._prepare_features_for_training(df)
        target = np.log1p(df['execution_time'])  # Log transform for better distribution

        if features.empty:
            logger.warning("No features available for execution time predictor training")
            return 0.0

        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            features, target, test_size=0.2, random_state=42
        )

        # Train model
        self.execution_time_predictor = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            random_state=42
        )

        self.execution_time_predictor.fit(X_train, y_train)

        # Evaluate (R² score)
        score = self.execution_time_predictor.score(X_test, y_test)

        logger.info(f"Execution time predictor R²: {score:.3f}")
        return score

    def _train_change_impact_predictor(self, df: pd.DataFrame) -> float:
        """Train change impact prediction model"""
        logger.info("Training change impact prediction model...")

        # Prepare features including changed files information
        features = self._prepare_features_with_changes(df)
        target = df['coverage_delta'].fillna(0)

        if features.empty:
            logger.warning("No features available for change impact predictor training")
            return 0.0

        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            features, target, test_size=0.2, random_state=42
        )

        # Train model
        self.change_impact_predictor = LogisticRegression(
            max_iter=1000,
            random_state=42
        )

        self.change_impact_predictor.fit(X_train, y_train)

        # Evaluate
        score = self.change_impact_predictor.score(X_test, y_test)

        logger.info(f"Change impact predictor R²: {score:.3f}")
        return score

    def _extract_test_features(self, test_name: str, changed_files: List[str]) -> np.ndarray:
        """Extract features for a single test for ML prediction"""
        features = []

        # Test name features
        features.extend([
            len(test_name),
            test_name.count('_'),
            test_name.count('test'),
            int('integration' in test_name.lower()),
            int('unit' in test_name.lower()),
            int('edge' in test_name.lower()),
            int('scenario' in test_name.lower())
        ])

        # Financial domain features
        domain = self._infer_financial_domain(test_name)
        domain_features = [0] * len(self.domain_criticality)
        if domain in self.domain_criticality:
            domain_idx = list(self.domain_criticality.keys()).index(domain)
            domain_features[domain_idx] = 1
        features.extend(domain_features)

        # Change impact features
        features.extend([
            len(changed_files),
            int(any(cf in self._get_test_file_path(test_name) for cf in changed_files)),
            sum(1 for cf in changed_files if cf.endswith('.py')),
            sum(1 for cf in changed_files if 'test' in cf)
        ])

        # Historical features (simplified - would be replaced with actual data)
        features.extend([
            0,  # days_since_last_failure
            0,  # failure_count_last_week
            0,  # avg_execution_time
            1   # complexity_score
        ])

        return np.array(features).reshape(1, -1)

    def _predict_failure_probability(self, features: np.ndarray) -> float:
        """Predict probability of test failure"""
        if self.failure_predictor is None:
            # Fallback heuristic
            return 0.1  # Default low probability

        try:
            # Scale features if scaler is fitted
            if hasattr(self.scaler, 'mean_'):
                features_scaled = self.scaler.transform(features)
            else:
                features_scaled = features

            proba = self.failure_predictor.predict_proba(features_scaled)[:, 1]
            return float(proba[0])
        except Exception as e:
            logger.warning(f"Error predicting failure probability: {e}")
            return 0.1

    def _predict_execution_time(self, features: np.ndarray) -> float:
        """Predict test execution time"""
        if self.execution_time_predictor is None:
            # Fallback heuristic based on test name
            test_name = str(features[0]) if len(features) > 0 else ""
            if 'integration' in test_name.lower():
                return 5.0
            elif 'performance' in test_name.lower():
                return 10.0
            else:
                return 1.0

        try:
            prediction = self.execution_time_predictor.predict(features)
            return max(np.expm1(float(prediction[0])), 0.1)  # Inverse log transform
        except Exception as e:
            logger.warning(f"Error predicting execution time: {e}")
            return 1.0

    def _calculate_change_impact(self, test_name: str, changed_files: List[str]) -> float:
        """Calculate impact score based on changed files"""
        if not changed_files:
            return 0.1

        test_file = self._get_test_file_path(test_name)
        impact = 0.0

        # Direct impact: test file itself changed
        if test_file in changed_files:
            impact += 1.0

        # Indirect impact: related files changed
        for changed_file in changed_files:
            if self._files_are_related(test_file, changed_file):
                impact += 0.5

        # Boost for financial domain files
        for changed_file in changed_files:
            if any(keyword in changed_file.lower() for keyword in
                   ['trading', 'order', 'risk', 'pnl', 'position', 'market']):
                impact += 0.3

        return min(impact, 1.0)

    def _calculate_risk_impact(self, test_name: str, features: np.ndarray) -> float:
        """Calculate financial risk impact score"""
        # Base risk from domain
        domain = self._infer_financial_domain(test_name)
        base_risk = self.domain_criticality.get(domain, 0.5)

        # Additional risk factors
        risk_keywords = ['order', 'trade', 'execute', 'money', 'fund', 'position', 'risk']
        keyword_risk = sum(0.1 for keyword in risk_keywords if keyword in test_name.lower())

        # Integration tests have higher risk
        integration_risk = 0.2 if 'integration' in test_name.lower() else 0.0

        return min(base_risk + keyword_risk + integration_risk, 1.0)

    def _calculate_priority_score(
        self,
        failure_prob: float,
        risk_impact: float,
        domain_crit: float,
        change_impact: float,
        exec_time: float
    ) -> float:
        """Calculate composite priority score"""
        # Weighted combination of factors
        score = (
            failure_prob * 0.3 +
            risk_impact * 0.25 +
            domain_crit * 0.25 +
            change_impact * 0.2
        )

        # Time penalty (prefer faster tests when scores are similar)
        time_penalty = min(exec_time / 60.0, 0.1)  # Max 10% penalty for long tests
        score = max(score - time_penalty, 0.0)

        return score

    def _generate_priority_reason(
        self,
        failure_prob: float,
        risk_impact: float,
        domain_crit: float,
        change_impact: float
    ) -> str:
        """Generate human-readable reason for priority"""
        reasons = []

        if failure_prob > 0.7:
            reasons.append("high failure probability")
        elif failure_prob > 0.4:
            reasons.append("moderate failure risk")

        if risk_impact > 0.8:
            reasons.append("critical financial impact")
        elif risk_impact > 0.6:
            reasons.append("significant financial risk")

        if domain_crit > 0.8:
            reasons.append("critical trading domain")
        elif domain_crit > 0.6:
            reasons.append("important financial domain")

        if change_impact > 0.7:
            reasons.append("high change impact")
        elif change_impact > 0.4:
            reasons.append("moderate change impact")

        if not reasons:
            reasons.append("baseline priority")

        return f"Priority: {', '.join(reasons)}"

    # Helper methods

    def _infer_financial_domain(self, test_name: str) -> str:
        """Infer financial domain from test name"""
        test_lower = test_name.lower()

        if any(keyword in test_lower for keyword in ['order', 'execute', 'trade']):
            return "order_execution"
        elif any(keyword in test_lower for keyword in ['risk', 'var', 'exposure']):
            return "risk_management"
        elif any(keyword in test_lower for keyword in ['pnl', 'profit', 'loss']):
            return "pnl_calculation"
        elif any(keyword in test_lower for keyword in ['position', 'portfolio']):
            return "position_management"
        elif any(keyword in test_lower for keyword in ['compliance', 'regulation']):
            return "compliance"
        elif any(keyword in test_lower for keyword in ['market', 'price', 'data']):
            return "market_data"
        elif any(keyword in test_lower for keyword in ['elliott', 'wave', 'fibonacci']):
            return "elliott_wave"
        elif any(keyword in test_lower for keyword in ['forex', 'currency', 'fx']):
            return "forex"
        elif any(keyword in test_lower for keyword in ['ui', 'frontend', 'component']):
            return "ui"
        elif any(keyword in test_lower for keyword in ['analytics', 'chart', 'report']):
            return "analytics"
        else:
            return "general"

    def _get_test_file_path(self, test_name: str) -> str:
        """Get file path for test"""
        # Simplified - in real implementation, would parse test node ID
        if "::" in test_name:
            return test_name.split("::")[0]
        return test_name

    def _files_are_related(self, test_file: str, changed_file: str) -> bool:
        """Check if test file and changed file are related"""
        # Simple heuristic - same directory or similar names
        test_dir = Path(test_file).parent
        changed_dir = Path(changed_file).parent

        return (
            test_dir == changed_dir or
            Path(test_file).stem in Path(changed_file).stem or
            Path(changed_file).stem in Path(test_file).stem
        )

    def _get_last_failure_date(self, test_name: str) -> Optional[datetime]:
        """Get date of last failure for test"""
        # In real implementation, would query historical data
        return None

    def _prepare_features_for_training(self, df: pd.DataFrame) -> pd.DataFrame:
        """Prepare features from execution data for ML training"""
        if df.empty:
            return pd.DataFrame()

        features = pd.DataFrame()

        # Basic features
        features['test_name_length'] = df['test_name'].str.len()
        features['test_name_underscores'] = df['test_name'].str.count('_')
        features['execution_time_log'] = np.log1p(df['execution_time'])
        features['complexity_score'] = df['complexity_score']

        # Domain features (one-hot encoding)
        domain_dummies = pd.get_dummies(df['financial_domain'], prefix='domain')
        features = pd.concat([features, domain_dummies], axis=1)

        # Risk level features
        risk_dummies = pd.get_dummies(df['risk_level'], prefix='risk')
        features = pd.concat([features, risk_dummies], axis=1)

        # Temporal features
        features['hour'] = df['timestamp'].dt.hour
        features['day_of_week'] = df['timestamp'].dt.dayofweek

        return features.fillna(0)

    def _prepare_features_with_changes(self, df: pd.DataFrame) -> pd.DataFrame:
        """Prepare features including change information"""
        features = self._prepare_features_for_training(df)

        if df.empty:
            return features

        # Change-related features
        features['changed_files_count'] = df['changed_files'].apply(len)
        features['coverage_delta'] = df['coverage_delta']

        return features

    def _load_execution_data(self) -> pd.DataFrame:
        """Load historical execution data"""
        data_file = self.data_dir / "execution_history.json"

        if not data_file.exists():
            return pd.DataFrame()

        try:
            with open(data_file, 'r') as f:
                data = json.load(f)

            df = pd.DataFrame(data)
            if not df.empty:
                df['timestamp'] = pd.to_datetime(df['timestamp'])

            return df

        except Exception as e:
            logger.error(f"Error loading execution data: {e}")
            return pd.DataFrame()

    def _save_execution_records(self, records: List[TestExecutionRecord]) -> None:
        """Save execution records to persistent storage"""
        data_file = self.data_dir / "execution_history.json"

        # Load existing data
        existing_data = []
        if data_file.exists():
            try:
                with open(data_file, 'r') as f:
                    existing_data = json.load(f)
            except Exception as e:
                logger.warning(f"Error loading existing data: {e}")

        # Convert records to dictionaries
        new_data = []
        for record in records:
            new_data.append({
                "test_name": record.test_name,
                "file_path": record.file_path,
                "execution_time": record.execution_time,
                "status": record.status,
                "timestamp": record.timestamp.isoformat(),
                "changed_files": record.changed_files,
                "commit_hash": record.commit_hash,
                "branch": record.branch,
                "coverage_delta": record.coverage_delta,
                "complexity_score": record.complexity_score,
                "financial_domain": record.financial_domain,
                "risk_level": record.risk_level
            })

        # Combine and save
        all_data = existing_data + new_data

        # Keep only last 10000 records to manage size
        if len(all_data) > 10000:
            all_data = all_data[-10000:]

        try:
            with open(data_file, 'w') as f:
                json.dump(all_data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving execution data: {e}")

    def _load_models(self) -> None:
        """Load pre-trained models"""
        models = {
            "failure_predictor": "failure_predictor.pkl",
            "execution_time_predictor": "execution_time_predictor.pkl",
            "change_impact_predictor": "change_impact_predictor.pkl",
            "scaler": "feature_scaler.pkl",
            "text_vectorizer": "text_vectorizer.pkl"
        }

        for attr_name, filename in models.items():
            model_path = self.models_dir / filename
            if model_path.exists():
                try:
                    with open(model_path, 'rb') as f:
                        setattr(self, attr_name, pickle.load(f))
                    logger.info(f"Loaded {attr_name} from {filename}")
                except Exception as e:
                    logger.warning(f"Error loading {attr_name}: {e}")

    def _save_models(self) -> None:
        """Save trained models"""
        models = {
            "failure_predictor": self.failure_predictor,
            "execution_time_predictor": self.execution_time_predictor,
            "change_impact_predictor": self.change_impact_predictor,
            "scaler": self.scaler,
            "text_vectorizer": self.text_vectorizer
        }

        for attr_name, model in models.items():
            if model is not None:
                model_path = self.models_dir / f"{attr_name}.pkl"
                try:
                    with open(model_path, 'wb') as f:
                        pickle.dump(model, f)
                    logger.info(f"Saved {attr_name} to {model_path.name}")
                except Exception as e:
                    logger.error(f"Error saving {attr_name}: {e}")

    def get_prioritization_analytics(self) -> Dict[str, Any]:
        """Get analytics about test prioritization performance"""
        df = self._load_execution_data()

        if df.empty:
            return {"message": "No historical data available"}

        analytics = {
            "total_test_executions": len(df),
            "unique_tests": df['test_name'].nunique(),
            "failure_rate_by_domain": df.groupby('financial_domain')['status'].apply(
                lambda x: (x == 'failed').mean()
            ).to_dict(),
            "avg_execution_time_by_domain": df.groupby('financial_domain')['execution_time'].mean().to_dict(),
            "recent_failure_trends": df[df['timestamp'] > datetime.now() - timedelta(days=7)].groupby(
                df['timestamp'].dt.date
            )['status'].apply(lambda x: (x == 'failed').sum()).to_dict()
        }

        # Model performance metrics
        if self.failure_predictor is not None:
            analytics["model_performance"] = {
                "failure_predictor_available": True,
                "execution_time_predictor_available": self.execution_time_predictor is not None,
                "change_impact_predictor_available": self.change_impact_predictor is not None
            }

        return analytics