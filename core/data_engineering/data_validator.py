"""
Real-Time Data Validation Framework

Validates incoming market data for quality, completeness, and anomalies
with configurable rules and automatic alerting.

Following TDD Green phase - implementation to pass validation tests.
"""

import asyncio
import logging
from collections import defaultdict, deque
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class ValidationSeverity(Enum):
    """Validation issue severity levels."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ValidationRule:
    """Base class for validation rules."""

    def __init__(
        self, name: str, severity: ValidationSeverity = ValidationSeverity.WARNING
    ):
        """Initialize validation rule."""
        self.name = name
        self.severity = severity
        self.violations = 0
        self.last_violation = None

    async def validate(self, data: Any) -> Tuple[bool, Optional[str]]:
        """
        Validate data against rule.

        Returns:
            Tuple of (is_valid, error_message)
        """
        raise NotImplementedError


class RangeValidationRule(ValidationRule):
    """Validates numeric values are within expected range."""

    def __init__(
        self,
        name: str,
        field: str,
        min_value: float,
        max_value: float,
        severity: ValidationSeverity = ValidationSeverity.WARNING,
    ):
        super().__init__(name, severity)
        self.field = field
        self.min_value = min_value
        self.max_value = max_value

    async def validate(self, data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Check if field value is within range."""
        if self.field not in data:
            return False, f"Missing field: {self.field}"

        value = data[self.field]
        if value < self.min_value or value > self.max_value:
            self.violations += 1
            self.last_violation = datetime.now()
            return (
                False,
                f"{self.field}={value} outside range [{self.min_value}, {self.max_value}]",
            )

        return True, None


class SpreadValidationRule(ValidationRule):
    """Validates bid-ask spread is reasonable."""

    def __init__(
        self,
        name: str,
        max_spread_pips: float = 10,
        severity: ValidationSeverity = ValidationSeverity.WARNING,
    ):
        super().__init__(name, severity)
        self.max_spread_pips = max_spread_pips

    async def validate(self, data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Check if spread is reasonable."""
        if "bid" not in data or "ask" not in data:
            return False, "Missing bid or ask price"

        spread_pips = (data["ask"] - data["bid"]) * 10000  # For forex
        if spread_pips > self.max_spread_pips or spread_pips < 0:
            self.violations += 1
            self.last_violation = datetime.now()
            return False, f"Invalid spread: {spread_pips:.2f} pips"

        return True, None


class DataValidator:
    """
    Real-time data validation engine.

    Features:
    - Configurable validation rules
    - Anomaly detection
    - Data quality scoring
    - Alert generation
    - Historical validation tracking
    """

    def __init__(self):
        """Initialize data validator."""
        self._rules: Dict[str, List[ValidationRule]] = defaultdict(list)
        self._validation_history = deque(maxlen=10000)
        self._anomaly_detector = AnomalyDetector()
        self._quality_scores = defaultdict(lambda: deque(maxlen=100))
        self._alerts = deque(maxlen=1000)

    def add_rule(self, data_type: str, rule: ValidationRule):
        """Add validation rule for a data type."""
        self._rules[data_type].append(rule)
        logger.info(f"Added {rule.name} rule for {data_type}")

    async def validate_tick(self, tick_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate single tick data.

        Args:
            tick_data: Tick data to validate

        Returns:
            Validation result with quality score
        """
        symbol = tick_data.get("symbol", "UNKNOWN")
        timestamp = tick_data.get("timestamp", datetime.now())

        # Run all rules for tick data
        violations = []
        for rule in self._rules.get("tick", []):
            is_valid, error_msg = await rule.validate(tick_data)
            if not is_valid:
                violations.append(
                    {
                        "rule": rule.name,
                        "severity": rule.severity.value,
                        "message": error_msg,
                    }
                )

        # Check for anomalies
        is_anomaly, anomaly_score = await self._anomaly_detector.detect_tick_anomaly(
            tick_data
        )
        if is_anomaly:
            violations.append(
                {
                    "rule": "anomaly_detection",
                    "severity": ValidationSeverity.WARNING.value,
                    "message": f"Anomaly detected (score: {anomaly_score:.2f})",
                }
            )

        # Calculate quality score
        quality_score = self._calculate_quality_score(violations)
        self._quality_scores[symbol].append(quality_score)

        # Generate alerts for critical issues
        critical_violations = [
            v for v in violations if v["severity"] == ValidationSeverity.CRITICAL.value
        ]
        if critical_violations:
            await self._generate_alert(symbol, critical_violations)

        # Store validation result
        result = {
            "symbol": symbol,
            "timestamp": timestamp,
            "is_valid": len(violations) == 0,
            "quality_score": quality_score,
            "violations": violations,
        }

        self._validation_history.append(result)
        return result

    async def validate_candle(self, candle_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate OHLCV candle data.

        Args:
            candle_data: Candle data to validate

        Returns:
            Validation result
        """
        symbol = candle_data.get("symbol", "UNKNOWN")

        # Basic OHLCV validation
        violations = []

        # Check required fields
        required_fields = ["open", "high", "low", "close", "volume"]
        for field in required_fields:
            if field not in candle_data:
                violations.append(
                    {
                        "rule": "required_field",
                        "severity": ValidationSeverity.ERROR.value,
                        "message": f"Missing required field: {field}",
                    }
                )

        if not violations:  # Only validate relationships if all fields present
            # High should be highest
            if candle_data["high"] < max(candle_data["open"], candle_data["close"]):
                violations.append(
                    {
                        "rule": "high_low_consistency",
                        "severity": ValidationSeverity.ERROR.value,
                        "message": "High is not the highest price",
                    }
                )

            # Low should be lowest
            if candle_data["low"] > min(candle_data["open"], candle_data["close"]):
                violations.append(
                    {
                        "rule": "high_low_consistency",
                        "severity": ValidationSeverity.ERROR.value,
                        "message": "Low is not the lowest price",
                    }
                )

            # Volume should be positive
            if candle_data["volume"] < 0:
                violations.append(
                    {
                        "rule": "volume_validation",
                        "severity": ValidationSeverity.ERROR.value,
                        "message": "Negative volume",
                    }
                )

        # Run custom rules
        for rule in self._rules.get("candle", []):
            is_valid, error_msg = await rule.validate(candle_data)
            if not is_valid:
                violations.append(
                    {
                        "rule": rule.name,
                        "severity": rule.severity.value,
                        "message": error_msg,
                    }
                )

        quality_score = self._calculate_quality_score(violations)

        return {
            "symbol": symbol,
            "timestamp": candle_data.get("timestamp", datetime.now()),
            "is_valid": len(violations) == 0,
            "quality_score": quality_score,
            "violations": violations,
        }

    async def validate_batch(
        self, data_batch: List[Dict[str, Any]], data_type: str = "tick"
    ) -> Dict[str, Any]:
        """
        Validate batch of data.

        Args:
            data_batch: List of data records
            data_type: Type of data (tick, candle)

        Returns:
            Batch validation summary
        """
        validation_tasks = []

        for data in data_batch:
            if data_type == "tick":
                task = self.validate_tick(data)
            elif data_type == "candle":
                task = self.validate_candle(data)
            else:
                continue
            validation_tasks.append(task)

        results = await asyncio.gather(*validation_tasks)

        # Calculate batch statistics
        valid_count = sum(1 for r in results if r["is_valid"])
        avg_quality = (
            sum(r["quality_score"] for r in results) / len(results) if results else 0
        )

        return {
            "total_records": len(data_batch),
            "valid_records": valid_count,
            "invalid_records": len(data_batch) - valid_count,
            "validation_rate": valid_count / len(data_batch) if data_batch else 0,
            "avg_quality_score": avg_quality,
            "results": results,
        }

    def _calculate_quality_score(self, violations: List[Dict[str, Any]]) -> float:
        """Calculate data quality score based on violations."""
        if not violations:
            return 100.0

        # Weighted scoring based on severity
        severity_weights = {
            ValidationSeverity.INFO.value: 0.95,
            ValidationSeverity.WARNING.value: 0.85,
            ValidationSeverity.ERROR.value: 0.5,
            ValidationSeverity.CRITICAL.value: 0.0,
        }

        score = 100.0
        for violation in violations:
            weight = severity_weights.get(violation["severity"], 0.9)
            score *= weight

        return max(0, score)

    async def _generate_alert(self, symbol: str, violations: List[Dict[str, Any]]):
        """Generate alert for critical violations."""
        alert = {
            "timestamp": datetime.now(),
            "symbol": symbol,
            "type": "data_quality",
            "severity": ValidationSeverity.CRITICAL.value,
            "violations": violations,
        }
        self._alerts.append(alert)
        logger.error(f"Data quality alert for {symbol}: {violations}")

    def get_quality_metrics(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """
        Get data quality metrics.

        Args:
            symbol: Optional symbol to filter by

        Returns:
            Quality metrics summary
        """
        if symbol:
            scores = list(self._quality_scores[symbol])
        else:
            scores = [
                s for scores_list in self._quality_scores.values() for s in scores_list
            ]

        if not scores:
            return {
                "avg_quality": 0,
                "min_quality": 0,
                "max_quality": 0,
                "recent_alerts": [],
            }

        recent_alerts = [
            a for a in self._alerts if not symbol or a.get("symbol") == symbol
        ][-10:]

        return {
            "avg_quality": np.mean(scores),
            "min_quality": np.min(scores),
            "max_quality": np.max(scores),
            "quality_trend": self._calculate_trend(scores),
            "recent_alerts": recent_alerts,
            "total_validations": len(self._validation_history),
        }

    def _calculate_trend(self, scores: List[float]) -> str:
        """Calculate quality trend."""
        if len(scores) < 10:
            return "insufficient_data"

        recent = np.mean(scores[-10:])
        previous = (
            np.mean(scores[-20:-10]) if len(scores) >= 20 else np.mean(scores[:-10])
        )

        if recent > previous * 1.05:
            return "improving"
        elif recent < previous * 0.95:
            return "degrading"
        else:
            return "stable"


class AnomalyDetector:
    """Detect anomalies in market data using statistical methods."""

    def __init__(self, lookback_window: int = 100):
        """Initialize anomaly detector."""
        self._lookback_window = lookback_window
        self._price_history = defaultdict(lambda: deque(maxlen=lookback_window))
        self._volume_history = defaultdict(lambda: deque(maxlen=lookback_window))

    async def detect_tick_anomaly(
        self, tick_data: Dict[str, Any]
    ) -> Tuple[bool, float]:
        """
        Detect anomalies in tick data.

        Returns:
            Tuple of (is_anomaly, anomaly_score)
        """
        symbol = tick_data.get("symbol", "UNKNOWN")
        price = tick_data.get(
            "mid", (tick_data.get("bid", 0) + tick_data.get("ask", 0)) / 2
        )

        # Store price history
        self._price_history[symbol].append(price)

        if len(self._price_history[symbol]) < 20:
            return False, 0.0  # Not enough data

        # Calculate z-score
        prices = np.array(self._price_history[symbol])
        mean = np.mean(prices)
        std = np.std(prices)

        if std == 0:
            return False, 0.0

        z_score = abs((price - mean) / std)

        # Anomaly if z-score > 3
        is_anomaly = z_score > 3
        anomaly_score = min(z_score / 3, 1.0) * 100  # Normalize to 0-100

        return is_anomaly, anomaly_score

    async def detect_volume_anomaly(
        self, volume: float, symbol: str
    ) -> Tuple[bool, float]:
        """Detect volume anomalies."""
        self._volume_history[symbol].append(volume)

        if len(self._volume_history[symbol]) < 20:
            return False, 0.0

        volumes = np.array(self._volume_history[symbol])
        mean = np.mean(volumes)
        std = np.std(volumes)

        if std == 0:
            return False, 0.0

        z_score = abs((volume - mean) / std)
        is_anomaly = z_score > 3
        anomaly_score = min(z_score / 3, 1.0) * 100

        return is_anomaly, anomaly_score
