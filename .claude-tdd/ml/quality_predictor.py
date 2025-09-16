"""
Predictive Quality Analytics for FXML4 Claude TDD Framework
ML-powered quality forecasting, defect prediction, and release readiness scoring
"""

import json
import logging
import pickle
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor, RandomForestClassifier
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.preprocessing import MinMaxScaler, StandardScaler

logger = logging.getLogger(__name__)


class QualityLevel(Enum):
    """Quality level classifications"""
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    CRITICAL = "critical"


class ReleaseReadiness(Enum):
    """Release readiness classifications"""
    READY = "ready"
    READY_WITH_CAUTION = "ready_with_caution"
    NOT_READY = "not_ready"
    BLOCKED = "blocked"


@dataclass
class QualityMetrics:
    """Comprehensive quality metrics for a codebase"""
    timestamp: datetime
    test_coverage: float
    mutation_score: float
    code_complexity: float
    technical_debt_ratio: float
    defect_density: float
    performance_score: float
    security_score: float
    maintainability_index: float
    financial_risk_score: float
    compliance_score: float


@dataclass
class DefectPrediction:
    """Defect prediction for a file or component"""
    file_path: str
    defect_probability: float
    severity_prediction: str  # low, medium, high, critical
    confidence: float
    risk_factors: List[str]
    recommendation: str


@dataclass
class QualityForecast:
    """Quality forecast for upcoming periods"""
    target_date: datetime
    predicted_coverage: float
    predicted_defect_count: int
    predicted_quality_level: QualityLevel
    confidence_interval: Tuple[float, float]
    improvement_actions: List[str]


@dataclass
class ReleaseAssessment:
    """Comprehensive release readiness assessment"""
    version: str
    assessment_date: datetime
    readiness: ReleaseReadiness
    overall_score: float
    quality_gates_passed: int
    quality_gates_total: int
    risk_factors: List[Dict[str, Any]]
    recommendations: List[str]
    estimated_defect_count: int
    financial_impact_score: float


class PredictiveQualityAnalytics:
    """ML-powered quality prediction and analytics for financial trading systems"""

    def __init__(self, data_dir: str = None, models_dir: str = None):
        """Initialize the quality analytics system

        Args:
            data_dir: Directory containing historical quality data
            models_dir: Directory containing trained ML models
        """
        self.data_dir = Path(data_dir) if data_dir else Path.cwd() / ".claude-tdd" / "ml" / "data"
        self.models_dir = Path(models_dir) if models_dir else Path.cwd() / ".claude-tdd" / "ml" / "models"

        # Ensure directories exist
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.models_dir.mkdir(parents=True, exist_ok=True)

        # ML models for different predictions
        self.defect_predictor = None
        self.quality_forecaster = None
        self.coverage_predictor = None
        self.technical_debt_predictor = None

        # Feature preprocessing
        self.quality_scaler = StandardScaler()
        self.metrics_scaler = MinMaxScaler()

        # Financial domain-specific weights
        self.domain_risk_weights = {
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

        # Quality gates for financial trading systems
        self.quality_gates = {
            "minimum_test_coverage": 85.0,
            "minimum_mutation_score": 75.0,
            "maximum_complexity": 10.0,
            "maximum_technical_debt": 5.0,
            "minimum_performance_score": 80.0,
            "minimum_security_score": 90.0,
            "maximum_defect_density": 0.1,
            "minimum_maintainability": 70.0,
            "minimum_compliance_score": 95.0
        }

        # Load existing models
        self._load_models()

    def collect_quality_metrics(self, metrics: Dict[str, Any]) -> None:
        """Collect quality metrics for ML training and analysis

        Args:
            metrics: Dictionary containing quality metrics
        """
        quality_metrics = QualityMetrics(
            timestamp=datetime.now(),
            test_coverage=metrics.get("test_coverage", 0.0),
            mutation_score=metrics.get("mutation_score", 0.0),
            code_complexity=metrics.get("code_complexity", 0.0),
            technical_debt_ratio=metrics.get("technical_debt_ratio", 0.0),
            defect_density=metrics.get("defect_density", 0.0),
            performance_score=metrics.get("performance_score", 0.0),
            security_score=metrics.get("security_score", 0.0),
            maintainability_index=metrics.get("maintainability_index", 0.0),
            financial_risk_score=metrics.get("financial_risk_score", 0.0),
            compliance_score=metrics.get("compliance_score", 0.0)
        )

        self._save_quality_metrics(quality_metrics)

    def predict_defects(self, file_paths: List[str] = None) -> List[DefectPrediction]:
        """Predict potential defects in code files

        Args:
            file_paths: List of file paths to analyze (None for all)

        Returns:
            List of defect predictions
        """
        if file_paths is None:
            file_paths = self._get_all_source_files()

        predictions = []

        for file_path in file_paths:
            # Extract features for the file
            features = self._extract_file_features(file_path)

            # Predict defect probability
            defect_prob = self._predict_defect_probability(features)

            # Predict severity
            severity = self._predict_defect_severity(features, defect_prob)

            # Calculate confidence
            confidence = self._calculate_prediction_confidence(features)

            # Identify risk factors
            risk_factors = self._identify_risk_factors(features, file_path)

            # Generate recommendation
            recommendation = self._generate_defect_recommendation(
                defect_prob, severity, risk_factors
            )

            predictions.append(DefectPrediction(
                file_path=file_path,
                defect_probability=defect_prob,
                severity_prediction=severity,
                confidence=confidence,
                risk_factors=risk_factors,
                recommendation=recommendation
            ))

        # Sort by defect probability (descending)
        predictions.sort(key=lambda x: x.defect_probability, reverse=True)

        return predictions

    def forecast_quality(self, forecast_days: int = 30) -> List[QualityForecast]:
        """Forecast quality metrics for upcoming periods

        Args:
            forecast_days: Number of days to forecast

        Returns:
            List of quality forecasts
        """
        forecasts = []
        current_date = datetime.now()

        # Load historical quality data
        df = self._load_quality_history()

        if df.empty:
            logger.warning("No historical data available for forecasting")
            return []

        # Generate forecasts for weekly intervals
        for week in range(0, forecast_days, 7):
            target_date = current_date + timedelta(days=week)

            # Predict coverage
            predicted_coverage = self._forecast_coverage(df, target_date)

            # Predict defect count
            predicted_defects = self._forecast_defect_count(df, target_date)

            # Predict quality level
            quality_level = self._predict_quality_level(predicted_coverage, predicted_defects)

            # Calculate confidence interval
            confidence_interval = self._calculate_forecast_confidence(df, week)

            # Generate improvement actions
            improvement_actions = self._generate_improvement_actions(
                predicted_coverage, predicted_defects, quality_level
            )

            forecasts.append(QualityForecast(
                target_date=target_date,
                predicted_coverage=predicted_coverage,
                predicted_defect_count=predicted_defects,
                predicted_quality_level=quality_level,
                confidence_interval=confidence_interval,
                improvement_actions=improvement_actions
            ))

        return forecasts

    def assess_release_readiness(self, version: str, target_date: datetime = None) -> ReleaseAssessment:
        """Assess readiness for release based on current quality metrics

        Args:
            version: Version identifier for the release
            target_date: Target release date (None for immediate)

        Returns:
            Comprehensive release assessment
        """
        target_date = target_date or datetime.now()

        # Get current quality metrics
        current_metrics = self._get_current_quality_metrics()

        # Evaluate quality gates
        gates_passed, gates_total = self._evaluate_quality_gates(current_metrics)

        # Calculate overall score
        overall_score = self._calculate_release_score(current_metrics, gates_passed, gates_total)

        # Determine readiness level
        readiness = self._determine_readiness_level(overall_score, gates_passed, gates_total)

        # Identify risk factors
        risk_factors = self._identify_release_risks(current_metrics, target_date)

        # Generate recommendations
        recommendations = self._generate_release_recommendations(
            current_metrics, risk_factors, readiness
        )

        # Estimate defect count for release
        estimated_defects = self._estimate_release_defects(current_metrics)

        # Calculate financial impact score
        financial_impact = self._calculate_financial_impact_score(
            current_metrics, estimated_defects, readiness
        )

        return ReleaseAssessment(
            version=version,
            assessment_date=datetime.now(),
            readiness=readiness,
            overall_score=overall_score,
            quality_gates_passed=gates_passed,
            quality_gates_total=gates_total,
            risk_factors=risk_factors,
            recommendations=recommendations,
            estimated_defect_count=estimated_defects,
            financial_impact_score=financial_impact
        )

    def train_quality_models(self, retrain: bool = False) -> Dict[str, float]:
        """Train ML models for quality prediction

        Args:
            retrain: Whether to retrain existing models

        Returns:
            Dictionary of model performance metrics
        """
        # Load historical data
        df = self._load_quality_history()

        if df.empty:
            logger.warning("No historical data available for training")
            return {}

        metrics = {}

        # Train defect predictor
        if self.defect_predictor is None or retrain:
            metrics["defect_predictor"] = self._train_defect_predictor(df)

        # Train quality forecaster
        if self.quality_forecaster is None or retrain:
            metrics["quality_forecaster"] = self._train_quality_forecaster(df)

        # Train coverage predictor
        if self.coverage_predictor is None or retrain:
            metrics["coverage_predictor"] = self._train_coverage_predictor(df)

        # Train technical debt predictor
        if self.technical_debt_predictor is None or retrain:
            metrics["technical_debt_predictor"] = self._train_technical_debt_predictor(df)

        # Save models
        self._save_models()

        return metrics

    def _train_defect_predictor(self, df: pd.DataFrame) -> float:
        """Train defect prediction model"""
        logger.info("Training defect prediction model...")

        # Prepare features
        features = self._prepare_quality_features(df)
        target = df['defect_density']

        if features.empty:
            logger.warning("No features available for defect predictor training")
            return 0.0

        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            features, target, test_size=0.2, random_state=42
        )

        # Train model
        self.defect_predictor = GradientBoostingRegressor(
            n_estimators=100,
            max_depth=6,
            learning_rate=0.1,
            random_state=42
        )

        self.defect_predictor.fit(X_train, y_train)

        # Evaluate
        predictions = self.defect_predictor.predict(X_test)
        r2 = r2_score(y_test, predictions)

        logger.info(f"Defect predictor R²: {r2:.3f}")
        return r2

    def _train_quality_forecaster(self, df: pd.DataFrame) -> float:
        """Train quality forecasting model"""
        logger.info("Training quality forecasting model...")

        # Prepare time series features
        features = self._prepare_time_series_features(df)
        target = df['test_coverage']

        if features.empty:
            logger.warning("No features available for quality forecaster training")
            return 0.0

        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            features, target, test_size=0.2, random_state=42
        )

        # Train model
        self.quality_forecaster = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            random_state=42
        )

        self.quality_forecaster.fit(X_train, y_train)

        # Evaluate
        score = self.quality_forecaster.score(X_test, y_test)

        logger.info(f"Quality forecaster R²: {score:.3f}")
        return score

    def _train_coverage_predictor(self, df: pd.DataFrame) -> float:
        """Train test coverage prediction model"""
        logger.info("Training coverage prediction model...")

        # Prepare features
        features = self._prepare_coverage_features(df)
        target = df['test_coverage']

        if features.empty:
            logger.warning("No features available for coverage predictor training")
            return 0.0

        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            features, target, test_size=0.2, random_state=42
        )

        # Train model
        self.coverage_predictor = LinearRegression()
        self.coverage_predictor.fit(X_train, y_train)

        # Evaluate
        score = self.coverage_predictor.score(X_test, y_test)

        logger.info(f"Coverage predictor R²: {score:.3f}")
        return score

    def _train_technical_debt_predictor(self, df: pd.DataFrame) -> float:
        """Train technical debt prediction model"""
        logger.info("Training technical debt prediction model...")

        # Prepare features
        features = self._prepare_debt_features(df)
        target = df['technical_debt_ratio']

        if features.empty:
            logger.warning("No features available for technical debt predictor training")
            return 0.0

        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            features, target, test_size=0.2, random_state=42
        )

        # Train model
        self.technical_debt_predictor = GradientBoostingRegressor(
            n_estimators=50,
            max_depth=4,
            learning_rate=0.1,
            random_state=42
        )

        self.technical_debt_predictor.fit(X_train, y_train)

        # Evaluate
        score = self.technical_debt_predictor.score(X_test, y_test)

        logger.info(f"Technical debt predictor R²: {score:.3f}")
        return score

    # Feature extraction and prediction methods

    def _extract_file_features(self, file_path: str) -> np.ndarray:
        """Extract features for defect prediction from a file"""
        features = []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Basic file metrics
            features.extend([
                len(content),  # File size
                content.count('\n'),  # Line count
                content.count('def '),  # Function count
                content.count('class '),  # Class count
                content.count('if '),  # Conditional complexity
                content.count('for ') + content.count('while '),  # Loop complexity
                content.count('try'),  # Exception handling
                content.count('import'),  # Import count
            ])

            # Financial domain features
            financial_keywords = [
                'order', 'trade', 'position', 'risk', 'pnl', 'price',
                'execute', 'market', 'forex', 'currency', 'elliott', 'wave'
            ]

            for keyword in financial_keywords:
                features.append(content.lower().count(keyword))

            # Code quality indicators
            features.extend([
                content.count('TODO'),  # Technical debt markers
                content.count('FIXME'),
                content.count('XXX'),
                content.count('# pylint: disable'),  # Lint suppressions
                content.count('# type: ignore'),  # Type check suppressions
            ])

        except Exception as e:
            logger.warning(f"Error extracting features from {file_path}: {e}")
            # Return zeros for all features
            features = [0] * 20

        return np.array(features).reshape(1, -1)

    def _predict_defect_probability(self, features: np.ndarray) -> float:
        """Predict probability of defects in a file"""
        if self.defect_predictor is None:
            # Fallback heuristic based on complexity
            complexity_score = features[0, 4] + features[0, 5]  # if + loops
            return min(complexity_score / 100.0, 1.0)

        try:
            prediction = self.defect_predictor.predict(features)
            return max(min(float(prediction[0]), 1.0), 0.0)
        except Exception as e:
            logger.warning(f"Error predicting defect probability: {e}")
            return 0.1

    def _predict_defect_severity(self, features: np.ndarray, defect_prob: float) -> str:
        """Predict severity of potential defects"""
        # Heuristic based on financial domain presence and complexity
        financial_score = sum(features[0, 8:20])  # Financial keyword counts
        complexity_score = features[0, 4] + features[0, 5]

        if financial_score > 10 and defect_prob > 0.7:
            return "critical"
        elif financial_score > 5 and defect_prob > 0.5:
            return "high"
        elif complexity_score > 10 or defect_prob > 0.3:
            return "medium"
        else:
            return "low"

    def _calculate_prediction_confidence(self, features: np.ndarray) -> float:
        """Calculate confidence in the prediction"""
        # Simple heuristic - more features available = higher confidence
        feature_completeness = np.count_nonzero(features) / features.size
        return min(feature_completeness + 0.3, 1.0)

    def _identify_risk_factors(self, features: np.ndarray, file_path: str) -> List[str]:
        """Identify risk factors for a file"""
        risk_factors = []

        # High complexity
        if features[0, 4] + features[0, 5] > 15:
            risk_factors.append("High cyclomatic complexity")

        # Large file size
        if features[0, 0] > 10000:  # File size
            risk_factors.append("Large file size")

        # Many functions/classes
        if features[0, 2] + features[0, 3] > 20:
            risk_factors.append("High number of functions/classes")

        # Technical debt markers
        if features[0, -5] + features[0, -4] + features[0, -3] > 5:
            risk_factors.append("Technical debt markers present")

        # Financial domain
        financial_score = sum(features[0, 8:20])
        if financial_score > 5:
            risk_factors.append("Financial domain complexity")

        # File type specific risks
        if 'order' in file_path.lower() or 'trade' in file_path.lower():
            risk_factors.append("Critical trading functionality")

        return risk_factors

    def _generate_defect_recommendation(
        self,
        defect_prob: float,
        severity: str,
        risk_factors: List[str]
    ) -> str:
        """Generate recommendation based on defect prediction"""
        if defect_prob > 0.8:
            return "URGENT: Immediate code review and refactoring required"
        elif defect_prob > 0.6:
            return "HIGH: Schedule detailed code review and increase test coverage"
        elif defect_prob > 0.4:
            return "MEDIUM: Add more unit tests and consider refactoring"
        elif defect_prob > 0.2:
            return "LOW: Monitor and maintain current quality practices"
        else:
            return "MINIMAL: Continue current quality practices"

    # Quality forecasting methods

    def _forecast_coverage(self, df: pd.DataFrame, target_date: datetime) -> float:
        """Forecast test coverage for target date"""
        if self.coverage_predictor is None or df.empty:
            return 80.0  # Conservative default

        try:
            # Simple trend-based prediction
            recent_data = df.tail(10)
            if len(recent_data) < 2:
                return recent_data['test_coverage'].iloc[-1] if not recent_data.empty else 80.0

            # Linear trend
            days_ahead = (target_date - df['timestamp'].iloc[-1]).days
            trend = (recent_data['test_coverage'].iloc[-1] - recent_data['test_coverage'].iloc[0]) / len(recent_data)
            prediction = recent_data['test_coverage'].iloc[-1] + (trend * days_ahead)

            return max(min(prediction, 100.0), 0.0)

        except Exception as e:
            logger.warning(f"Error forecasting coverage: {e}")
            return 80.0

    def _forecast_defect_count(self, df: pd.DataFrame, target_date: datetime) -> int:
        """Forecast defect count for target date"""
        if df.empty:
            return 0

        try:
            # Base on recent defect density and code growth
            recent_density = df['defect_density'].tail(5).mean()
            # Assume moderate code growth
            estimated_loc = 10000  # Lines of code (would be calculated from actual data)
            estimated_defects = int(recent_density * estimated_loc)

            return max(estimated_defects, 0)

        except Exception as e:
            logger.warning(f"Error forecasting defect count: {e}")
            return 0

    def _predict_quality_level(self, coverage: float, defect_count: int) -> QualityLevel:
        """Predict overall quality level"""
        if coverage >= 90 and defect_count <= 2:
            return QualityLevel.EXCELLENT
        elif coverage >= 80 and defect_count <= 5:
            return QualityLevel.GOOD
        elif coverage >= 70 and defect_count <= 10:
            return QualityLevel.FAIR
        elif coverage >= 60 and defect_count <= 20:
            return QualityLevel.POOR
        else:
            return QualityLevel.CRITICAL

    def _calculate_forecast_confidence(self, df: pd.DataFrame, weeks_ahead: int) -> Tuple[float, float]:
        """Calculate confidence interval for forecast"""
        # Simple heuristic - confidence decreases with time
        base_confidence = 0.95 - (weeks_ahead * 0.1)
        margin = max(0.1, weeks_ahead * 0.05)

        return (max(base_confidence - margin, 0.0), min(base_confidence + margin, 1.0))

    def _generate_improvement_actions(
        self,
        coverage: float,
        defect_count: int,
        quality_level: QualityLevel
    ) -> List[str]:
        """Generate improvement actions based on forecast"""
        actions = []

        if coverage < 80:
            actions.append("Increase test coverage by adding unit and integration tests")

        if defect_count > 5:
            actions.append("Implement more rigorous code review process")
            actions.append("Add mutation testing to improve test quality")

        if quality_level in [QualityLevel.POOR, QualityLevel.CRITICAL]:
            actions.append("Conduct immediate technical debt reduction sprint")
            actions.append("Implement daily quality monitoring")

        # Financial domain specific actions
        actions.append("Review financial calculation precision")
        actions.append("Validate risk management test scenarios")

        return actions

    # Release assessment methods

    def _get_current_quality_metrics(self) -> Dict[str, float]:
        """Get current quality metrics"""
        # In real implementation, would fetch from actual quality tools
        return {
            "test_coverage": 85.0,
            "mutation_score": 75.0,
            "code_complexity": 8.0,
            "technical_debt_ratio": 3.0,
            "defect_density": 0.05,
            "performance_score": 82.0,
            "security_score": 95.0,
            "maintainability_index": 78.0,
            "financial_risk_score": 0.2,
            "compliance_score": 98.0
        }

    def _evaluate_quality_gates(self, metrics: Dict[str, float]) -> Tuple[int, int]:
        """Evaluate quality gates against current metrics"""
        passed = 0
        total = len(self.quality_gates)

        for gate, threshold in self.quality_gates.items():
            metric_name = gate.replace("minimum_", "").replace("maximum_", "")
            current_value = metrics.get(metric_name, 0.0)

            if gate.startswith("minimum_"):
                if current_value >= threshold:
                    passed += 1
            else:  # maximum_
                if current_value <= threshold:
                    passed += 1

        return passed, total

    def _calculate_release_score(self, metrics: Dict[str, float], gates_passed: int, gates_total: int) -> float:
        """Calculate overall release score"""
        # Weighted combination of metrics
        score = (
            metrics.get("test_coverage", 0) * 0.2 +
            metrics.get("mutation_score", 0) * 0.15 +
            (100 - metrics.get("code_complexity", 0) * 10) * 0.1 +
            (100 - metrics.get("technical_debt_ratio", 0) * 20) * 0.1 +
            metrics.get("performance_score", 0) * 0.15 +
            metrics.get("security_score", 0) * 0.2 +
            metrics.get("compliance_score", 0) * 0.1
        )

        # Quality gates bonus
        gates_bonus = (gates_passed / gates_total) * 10

        return min(score + gates_bonus, 100.0)

    def _determine_readiness_level(self, score: float, gates_passed: int, gates_total: int) -> ReleaseReadiness:
        """Determine release readiness level"""
        gate_ratio = gates_passed / gates_total

        if score >= 90 and gate_ratio >= 0.9:
            return ReleaseReadiness.READY
        elif score >= 75 and gate_ratio >= 0.8:
            return ReleaseReadiness.READY_WITH_CAUTION
        elif score >= 60 and gate_ratio >= 0.6:
            return ReleaseReadiness.NOT_READY
        else:
            return ReleaseReadiness.BLOCKED

    def _identify_release_risks(self, metrics: Dict[str, float], target_date: datetime) -> List[Dict[str, Any]]:
        """Identify risks for the release"""
        risks = []

        # Quality gate failures
        for gate, threshold in self.quality_gates.items():
            metric_name = gate.replace("minimum_", "").replace("maximum_", "")
            current_value = metrics.get(metric_name, 0.0)

            failed = False
            if gate.startswith("minimum_") and current_value < threshold:
                failed = True
            elif gate.startswith("maximum_") and current_value > threshold:
                failed = True

            if failed:
                risks.append({
                    "type": "quality_gate_failure",
                    "description": f"{gate} failed: {current_value:.2f} vs {threshold:.2f}",
                    "severity": "high" if "security" in gate or "compliance" in gate else "medium",
                    "impact": "May block release or cause production issues"
                })

        # Financial domain specific risks
        if metrics.get("financial_risk_score", 0) > 0.5:
            risks.append({
                "type": "financial_risk",
                "description": "High financial risk score detected",
                "severity": "critical",
                "impact": "Potential financial losses in production"
            })

        # Time-based risks
        days_to_release = (target_date - datetime.now()).days
        if days_to_release < 7 and len(risks) > 0:
            risks.append({
                "type": "time_pressure",
                "description": f"Only {days_to_release} days to release with quality issues",
                "severity": "high",
                "impact": "Insufficient time to address quality issues"
            })

        return risks

    def _generate_release_recommendations(
        self,
        metrics: Dict[str, float],
        risks: List[Dict[str, Any]],
        readiness: ReleaseReadiness
    ) -> List[str]:
        """Generate release recommendations"""
        recommendations = []

        if readiness == ReleaseReadiness.BLOCKED:
            recommendations.append("DO NOT RELEASE - Critical quality issues must be resolved")
            recommendations.append("Conduct emergency quality improvement sprint")

        elif readiness == ReleaseReadiness.NOT_READY:
            recommendations.append("Delay release until quality gates are met")
            recommendations.append("Focus on failing quality metrics")

        elif readiness == ReleaseReadiness.READY_WITH_CAUTION:
            recommendations.append("Release with enhanced monitoring")
            recommendations.append("Prepare rollback plan")

        # Specific recommendations based on metrics
        if metrics.get("test_coverage", 0) < 85:
            recommendations.append("Increase test coverage before release")

        if metrics.get("security_score", 0) < 90:
            recommendations.append("Conduct security review")

        # Financial domain recommendations
        recommendations.append("Validate all financial calculations")
        recommendations.append("Review risk management scenarios")

        return recommendations

    def _estimate_release_defects(self, metrics: Dict[str, float]) -> int:
        """Estimate number of defects likely in release"""
        # Heuristic based on defect density and code quality
        base_defects = metrics.get("defect_density", 0.1) * 10000  # Assume 10k LOC

        # Adjust based on other quality metrics
        quality_factor = (
            (100 - metrics.get("test_coverage", 80)) +
            (100 - metrics.get("mutation_score", 70)) +
            metrics.get("code_complexity", 5) * 5
        ) / 100

        estimated_defects = int(base_defects * (1 + quality_factor))

        return max(estimated_defects, 0)

    def _calculate_financial_impact_score(
        self,
        metrics: Dict[str, float],
        estimated_defects: int,
        readiness: ReleaseReadiness
    ) -> float:
        """Calculate potential financial impact score"""
        # Base impact from defects (assuming $10k per defect in financial systems)
        defect_impact = estimated_defects * 10000

        # Multiply by risk factors
        risk_multiplier = 1.0

        if readiness == ReleaseReadiness.BLOCKED:
            risk_multiplier = 5.0
        elif readiness == ReleaseReadiness.NOT_READY:
            risk_multiplier = 3.0
        elif readiness == ReleaseReadiness.READY_WITH_CAUTION:
            risk_multiplier = 1.5

        # Add compliance and security impact
        compliance_impact = (100 - metrics.get("compliance_score", 95)) * 1000
        security_impact = (100 - metrics.get("security_score", 90)) * 2000

        total_impact = (defect_impact + compliance_impact + security_impact) * risk_multiplier

        # Normalize to 0-100 scale
        return min(total_impact / 100000, 100.0)

    # Data management methods

    def _get_all_source_files(self) -> List[str]:
        """Get all source files for analysis"""
        # In real implementation, would scan the project directory
        return [
            "fxml4/trading/order_execution.py",
            "fxml4/risk/position_manager.py",
            "fxml4/analytics/elliott_wave.py",
            # ... more files
        ]

    def _prepare_quality_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Prepare features for quality prediction"""
        if df.empty:
            return pd.DataFrame()

        features = pd.DataFrame()

        # Quality metrics as features
        features['test_coverage'] = df['test_coverage']
        features['mutation_score'] = df['mutation_score']
        features['code_complexity'] = df['code_complexity']
        features['performance_score'] = df['performance_score']
        features['security_score'] = df['security_score']

        # Derived features
        features['quality_trend'] = df['test_coverage'].rolling(window=3).mean()
        features['complexity_growth'] = df['code_complexity'].diff()

        return features.fillna(0)

    def _prepare_time_series_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Prepare time series features for forecasting"""
        if df.empty:
            return pd.DataFrame()

        features = pd.DataFrame()

        # Time-based features
        features['day_of_week'] = df['timestamp'].dt.dayofweek
        features['month'] = df['timestamp'].dt.month
        features['days_since_start'] = (df['timestamp'] - df['timestamp'].min()).dt.days

        # Lagged features
        for lag in [1, 3, 7]:
            features[f'coverage_lag_{lag}'] = df['test_coverage'].shift(lag)
            features[f'defect_lag_{lag}'] = df['defect_density'].shift(lag)

        return features.fillna(0)

    def _prepare_coverage_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Prepare features for coverage prediction"""
        return self._prepare_quality_features(df)

    def _prepare_debt_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Prepare features for technical debt prediction"""
        return self._prepare_quality_features(df)

    def _load_quality_history(self) -> pd.DataFrame:
        """Load historical quality data"""
        data_file = self.data_dir / "quality_history.json"

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
            logger.error(f"Error loading quality history: {e}")
            return pd.DataFrame()

    def _save_quality_metrics(self, metrics: QualityMetrics) -> None:
        """Save quality metrics to persistent storage"""
        data_file = self.data_dir / "quality_history.json"

        # Load existing data
        existing_data = []
        if data_file.exists():
            try:
                with open(data_file, 'r') as f:
                    existing_data = json.load(f)
            except Exception as e:
                logger.warning(f"Error loading existing quality data: {e}")

        # Add new metrics
        new_record = {
            "timestamp": metrics.timestamp.isoformat(),
            "test_coverage": metrics.test_coverage,
            "mutation_score": metrics.mutation_score,
            "code_complexity": metrics.code_complexity,
            "technical_debt_ratio": metrics.technical_debt_ratio,
            "defect_density": metrics.defect_density,
            "performance_score": metrics.performance_score,
            "security_score": metrics.security_score,
            "maintainability_index": metrics.maintainability_index,
            "financial_risk_score": metrics.financial_risk_score,
            "compliance_score": metrics.compliance_score
        }

        existing_data.append(new_record)

        # Keep only last 1000 records
        if len(existing_data) > 1000:
            existing_data = existing_data[-1000:]

        try:
            with open(data_file, 'w') as f:
                json.dump(existing_data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving quality metrics: {e}")

    def _load_models(self) -> None:
        """Load pre-trained models"""
        models = {
            "defect_predictor": "defect_predictor.pkl",
            "quality_forecaster": "quality_forecaster.pkl",
            "coverage_predictor": "coverage_predictor.pkl",
            "technical_debt_predictor": "technical_debt_predictor.pkl",
            "quality_scaler": "quality_scaler.pkl",
            "metrics_scaler": "metrics_scaler.pkl"
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
            "defect_predictor": self.defect_predictor,
            "quality_forecaster": self.quality_forecaster,
            "coverage_predictor": self.coverage_predictor,
            "technical_debt_predictor": self.technical_debt_predictor,
            "quality_scaler": self.quality_scaler,
            "metrics_scaler": self.metrics_scaler
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

    def get_quality_dashboard_data(self) -> Dict[str, Any]:
        """Get data for quality dashboard"""
        df = self._load_quality_history()
        current_metrics = self._get_current_quality_metrics()

        dashboard_data = {
            "current_metrics": current_metrics,
            "quality_trends": {},
            "recent_forecasts": [],
            "quality_gates_status": {}
        }

        if not df.empty:
            # Quality trends
            dashboard_data["quality_trends"] = {
                "coverage_trend": df['test_coverage'].tail(30).tolist(),
                "defect_trend": df['defect_density'].tail(30).tolist(),
                "complexity_trend": df['code_complexity'].tail(30).tolist()
            }

            # Recent forecasts
            forecasts = self.forecast_quality(14)
            dashboard_data["recent_forecasts"] = [
                {
                    "date": f.target_date.isoformat(),
                    "coverage": f.predicted_coverage,
                    "defects": f.predicted_defect_count,
                    "quality_level": f.predicted_quality_level.value
                }
                for f in forecasts[:5]
            ]

        # Quality gates status
        gates_passed, gates_total = self._evaluate_quality_gates(current_metrics)
        dashboard_data["quality_gates_status"] = {
            "passed": gates_passed,
            "total": gates_total,
            "percentage": (gates_passed / gates_total) * 100 if gates_total > 0 else 0
        }

        return dashboard_data