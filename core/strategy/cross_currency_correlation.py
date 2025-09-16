"""
Cross-Currency Correlation Analysis and Monitoring for FXML4.

This module provides comprehensive correlation analysis and monitoring capabilities
for multi-currency forex trading, including real-time correlation tracking,
regime change detection, and risk management insights.

Key Features:
- Real-time correlation matrix calculation and monitoring
- Correlation regime change detection with statistical significance testing
- Multi-timeframe correlation analysis (5m, 15m, 1h, 4h, 1d)
- Rolling correlation stability analysis
- Cross-asset correlation integration (Gold, VIX, Equity indices)
- Correlation-based risk warnings and alerts
- Portfolio diversification metrics and recommendations
"""

import asyncio
import logging
import threading
import warnings
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
from scipy import stats
from scipy.stats import pearsonr, spearmanr

warnings.filterwarnings("ignore")

logger = logging.getLogger(__name__)


@dataclass
class CorrelationMetrics:
    """Container for correlation analysis metrics."""

    pearson_corr: float
    spearman_corr: float
    rolling_corr_mean: float
    rolling_corr_std: float
    correlation_regime: str  # 'low', 'normal', 'high', 'extreme'
    stability_score: float  # 0-1, higher = more stable
    significance_level: float
    last_regime_change: Optional[datetime] = None
    correlation_trend: str = "stable"  # 'increasing', 'decreasing', 'stable'


@dataclass
class CorrelationAlert:
    """Correlation-based alert structure."""

    alert_type: str  # 'regime_change', 'extreme_correlation', 'instability', 'diversification_loss'
    severity: str  # 'low', 'medium', 'high', 'critical'
    pair1: str
    pair2: str
    current_correlation: float
    threshold_breached: float
    message: str
    timestamp: datetime
    recommended_action: str = ""


class CrossCurrencyCorrelationMonitor:
    """
    Comprehensive cross-currency correlation analysis and monitoring system.

    Tracks correlations between multiple currency pairs, detects regime changes,
    provides risk management insights, and supports portfolio optimization.
    """

    def __init__(
        self, currency_pairs: List[str] = None, config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize cross-currency correlation monitor.

        Args:
            currency_pairs: List of currency pairs to monitor
            config: Configuration parameters
        """
        self.currency_pairs = currency_pairs or [
            "GBPUSD",
            "EURUSD",
            "USDJPY",
            "USDCHF",
            "AUDUSD",
            "NZDUSD",
            "USDCAD",  # Extended coverage
        ]

        self.config = self._get_default_config()
        if config:
            self.config.update(config)

        # Data storage
        self.price_data: Dict[str, pd.DataFrame] = {}
        self.return_data: Dict[str, pd.Series] = {}

        # Correlation matrices for different timeframes
        self.correlation_matrices: Dict[str, pd.DataFrame] = {}
        self.correlation_history: Dict[str, List[pd.DataFrame]] = defaultdict(list)

        # Metrics and monitoring
        self.correlation_metrics: Dict[Tuple[str, str], CorrelationMetrics] = {}
        self.alerts: List[CorrelationAlert] = []
        self.regime_states: Dict[Tuple[str, str], str] = {}

        # Monitoring control
        self.is_monitoring = False
        self.monitor_thread = None
        self.last_update = None

        # Cross-asset data integration
        self.cross_asset_data: Dict[str, pd.DataFrame] = {}

        logger.info(
            f"Initialized CrossCurrencyCorrelationMonitor for {len(self.currency_pairs)} pairs"
        )

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration parameters."""
        return {
            "correlation_windows": {
                "5M": 144,  # 5-minute, 12 hours of data
                "15M": 96,  # 15-minute, 24 hours of data
                "1H": 168,  # 1-hour, 7 days of data
                "4H": 180,  # 4-hour, 30 days of data
                "1D": 252,  # Daily, 1 year of data
            },
            "regime_thresholds": {
                "low_correlation": 0.3,
                "normal_correlation": 0.6,
                "high_correlation": 0.8,
                "extreme_correlation": 0.95,
            },
            "stability_thresholds": {"unstable": 0.3, "moderate": 0.6, "stable": 0.8},
            "alert_thresholds": {
                "correlation_change": 0.2,  # Alert if correlation changes by this much
                "regime_persistence": 5,  # Periods before confirming regime change
                "significance_level": 0.05,  # Statistical significance threshold
                "extreme_duration": 24,  # Hours of extreme correlation before alert
            },
            "update_frequency": 300,  # Update every 5 minutes
            "cross_asset_pairs": {
                "XAUUSD": "gold",  # Gold
                "VIX": "volatility",  # VIX
                "SPX": "equity",  # S&P 500
                "DXY": "dollar_index",  # Dollar Index
            },
            "portfolio_analysis": {
                "max_correlation_exposure": 0.7,  # Maximum average correlation for portfolio
                "diversification_threshold": 0.5,  # Minimum diversification score
                "concentration_limit": 0.4,  # Maximum weight in correlated pairs
            },
        }

    async def add_price_data(
        self, pair: str, data: pd.DataFrame, timeframe: str = "1H"
    ) -> bool:
        """
        Add price data for a currency pair.

        Args:
            pair: Currency pair (e.g., 'EURUSD')
            data: Price data with OHLCV columns
            timeframe: Data timeframe

        Returns:
            Success status
        """
        try:
            if pair not in self.currency_pairs:
                self.currency_pairs.append(pair)

            # Store price data
            self.price_data[pair] = data.copy()

            # Calculate returns
            if "close" in data.columns:
                returns = data["close"].pct_change().dropna()
                self.return_data[pair] = returns

                logger.debug(f"Added {len(data)} data points for {pair}")
                return True
            else:
                logger.error(f"Missing 'close' column in data for {pair}")
                return False

        except Exception as e:
            logger.error(f"Error adding price data for {pair}: {e}")
            return False

    async def add_cross_asset_data(self, asset: str, data: pd.DataFrame) -> bool:
        """Add cross-asset data for correlation analysis."""
        try:
            if asset in self.config["cross_asset_pairs"]:
                self.cross_asset_data[asset] = data.copy()

                if "close" in data.columns:
                    returns = data["close"].pct_change().dropna()
                    self.return_data[asset] = returns

                logger.debug(f"Added cross-asset data for {asset}")
                return True
            return False

        except Exception as e:
            logger.error(f"Error adding cross-asset data for {asset}: {e}")
            return False

    def calculate_correlation_matrix(
        self, timeframe: str = "1H", method: str = "pearson"
    ) -> pd.DataFrame:
        """
        Calculate correlation matrix for all currency pairs.

        Args:
            timeframe: Timeframe for correlation calculation
            method: Correlation method ('pearson', 'spearman')

        Returns:
            Correlation matrix DataFrame
        """
        try:
            if not self.return_data:
                logger.warning("No return data available for correlation calculation")
                return pd.DataFrame()

            # Get correlation window size
            window = self.config["correlation_windows"].get(timeframe, 168)

            # Align return data
            aligned_returns = pd.DataFrame()
            for pair, returns in self.return_data.items():
                if len(returns) >= window:
                    aligned_returns[pair] = returns.tail(window)

            if aligned_returns.empty:
                return pd.DataFrame()

            # Calculate correlation matrix
            if method == "pearson":
                corr_matrix = aligned_returns.corr(method="pearson")
            elif method == "spearman":
                corr_matrix = aligned_returns.corr(method="spearman")
            else:
                corr_matrix = aligned_returns.corr()

            # Store correlation matrix
            self.correlation_matrices[timeframe] = corr_matrix
            self.correlation_history[timeframe].append(corr_matrix.copy())

            # Keep only recent history (last 100 matrices)
            if len(self.correlation_history[timeframe]) > 100:
                self.correlation_history[timeframe] = self.correlation_history[
                    timeframe
                ][-100:]

            logger.debug(f"Calculated correlation matrix for {timeframe} timeframe")
            return corr_matrix

        except Exception as e:
            logger.error(f"Error calculating correlation matrix: {e}")
            return pd.DataFrame()

    def analyze_correlation_stability(
        self, pair1: str, pair2: str, timeframe: str = "1H", lookback_periods: int = 20
    ) -> Dict[str, float]:
        """
        Analyze correlation stability between two pairs.

        Args:
            pair1: First currency pair
            pair2: Second currency pair
            timeframe: Analysis timeframe
            lookback_periods: Number of periods to analyze

        Returns:
            Stability metrics dictionary
        """
        try:
            if timeframe not in self.correlation_history:
                return {}

            history = self.correlation_history[timeframe]
            if len(history) < lookback_periods:
                return {}

            # Extract correlations for the pair
            recent_correlations = []
            for matrix in history[-lookback_periods:]:
                if pair1 in matrix.index and pair2 in matrix.columns:
                    corr_value = matrix.loc[pair1, pair2]
                    if not np.isnan(corr_value):
                        recent_correlations.append(corr_value)

            if len(recent_correlations) < 5:
                return {}

            # Calculate stability metrics
            correlations = np.array(recent_correlations)

            stability_metrics = {
                "mean_correlation": np.mean(correlations),
                "correlation_std": np.std(correlations),
                "correlation_range": np.max(correlations) - np.min(correlations),
                "stability_score": 1.0
                / (1.0 + np.std(correlations)),  # Higher = more stable
                "trend_slope": self._calculate_trend_slope(correlations),
                "regime_changes": self._count_regime_changes(correlations),
                "current_vs_mean_diff": correlations[-1] - np.mean(correlations),
            }

            return stability_metrics

        except Exception as e:
            logger.error(f"Error analyzing correlation stability: {e}")
            return {}

    def _calculate_trend_slope(self, correlations: np.ndarray) -> float:
        """Calculate trend slope of correlations."""
        if len(correlations) < 3:
            return 0.0

        x = np.arange(len(correlations))
        try:
            slope, intercept, r_value, p_value, std_err = stats.linregress(
                x, correlations
            )
            return slope
        except:
            return 0.0

    def _count_regime_changes(self, correlations: np.ndarray) -> int:
        """Count regime changes in correlation series."""
        if len(correlations) < 3:
            return 0

        thresholds = self.config["regime_thresholds"]
        regime_changes = 0
        current_regime = self._classify_correlation_regime(correlations[0])

        for corr in correlations[1:]:
            new_regime = self._classify_correlation_regime(corr)
            if new_regime != current_regime:
                regime_changes += 1
                current_regime = new_regime

        return regime_changes

    def _classify_correlation_regime(self, correlation: float) -> str:
        """Classify correlation into regime categories."""
        abs_corr = abs(correlation)
        thresholds = self.config["regime_thresholds"]

        if abs_corr >= thresholds["extreme_correlation"]:
            return "extreme"
        elif abs_corr >= thresholds["high_correlation"]:
            return "high"
        elif abs_corr >= thresholds["normal_correlation"]:
            return "normal"
        else:
            return "low"

    def detect_correlation_regime_changes(
        self, timeframe: str = "1H"
    ) -> List[Dict[str, Any]]:
        """
        Detect significant correlation regime changes.

        Args:
            timeframe: Analysis timeframe

        Returns:
            List of detected regime changes
        """
        regime_changes = []

        try:
            if timeframe not in self.correlation_matrices:
                return regime_changes

            current_matrix = self.correlation_matrices[timeframe]

            # Analyze each pair combination
            for i, pair1 in enumerate(current_matrix.index):
                for j, pair2 in enumerate(current_matrix.columns):
                    if i >= j:  # Skip diagonal and duplicate pairs
                        continue

                    current_corr = current_matrix.loc[pair1, pair2]
                    if np.isnan(current_corr):
                        continue

                    # Get stability analysis
                    stability_metrics = self.analyze_correlation_stability(
                        pair1, pair2, timeframe
                    )
                    if not stability_metrics:
                        continue

                    # Check for regime change
                    regime_change = self._check_regime_change(
                        pair1, pair2, current_corr, stability_metrics
                    )

                    if regime_change:
                        regime_changes.append(regime_change)

            return regime_changes

        except Exception as e:
            logger.error(f"Error detecting correlation regime changes: {e}")
            return regime_changes

    def _check_regime_change(
        self,
        pair1: str,
        pair2: str,
        current_corr: float,
        stability_metrics: Dict[str, float],
    ) -> Optional[Dict[str, Any]]:
        """Check if a regime change has occurred for a pair."""
        pair_key = (pair1, pair2)

        # Current regime classification
        current_regime = self._classify_correlation_regime(current_corr)
        previous_regime = self.regime_states.get(pair_key, "unknown")

        # Check for significant change
        mean_corr = stability_metrics.get("mean_correlation", current_corr)
        corr_change = abs(current_corr - mean_corr)

        # Regime change conditions
        regime_changed = (
            current_regime != previous_regime and previous_regime != "unknown"
        )
        significant_change = (
            corr_change >= self.config["alert_thresholds"]["correlation_change"]
        )

        if regime_changed or significant_change:
            # Update regime state
            self.regime_states[pair_key] = current_regime

            return {
                "pair1": pair1,
                "pair2": pair2,
                "previous_regime": previous_regime,
                "current_regime": current_regime,
                "current_correlation": current_corr,
                "mean_correlation": mean_corr,
                "correlation_change": corr_change,
                "stability_score": stability_metrics.get("stability_score", 0),
                "timestamp": datetime.utcnow(),
                "significance": "high" if significant_change else "medium",
            }

        return None

    def generate_correlation_alerts(
        self, timeframe: str = "1H"
    ) -> List[CorrelationAlert]:
        """
        Generate correlation-based alerts and warnings.

        Args:
            timeframe: Analysis timeframe

        Returns:
            List of correlation alerts
        """
        alerts = []

        try:
            # Detect regime changes
            regime_changes = self.detect_correlation_regime_changes(timeframe)

            for change in regime_changes:
                alert = CorrelationAlert(
                    alert_type="regime_change",
                    severity=self._determine_alert_severity(change),
                    pair1=change["pair1"],
                    pair2=change["pair2"],
                    current_correlation=change["current_correlation"],
                    threshold_breached=change["correlation_change"],
                    message=f"Correlation regime change: {change['pair1']}-{change['pair2']} "
                    f"from {change['previous_regime']} to {change['current_regime']}",
                    timestamp=change["timestamp"],
                    recommended_action=self._get_regime_change_recommendation(change),
                )
                alerts.append(alert)

            # Check for extreme correlations
            extreme_alerts = self._check_extreme_correlations(timeframe)
            alerts.extend(extreme_alerts)

            # Check portfolio diversification
            diversification_alerts = self._check_diversification_issues(timeframe)
            alerts.extend(diversification_alerts)

            # Store alerts
            self.alerts.extend(alerts)

            # Keep only recent alerts (last 1000)
            if len(self.alerts) > 1000:
                self.alerts = self.alerts[-1000:]

            return alerts

        except Exception as e:
            logger.error(f"Error generating correlation alerts: {e}")
            return []

    def _determine_alert_severity(self, change: Dict[str, Any]) -> str:
        """Determine alert severity based on change characteristics."""
        corr_change = change["correlation_change"]
        current_regime = change["current_regime"]
        stability_score = change.get("stability_score", 0.5)

        if current_regime == "extreme" or corr_change > 0.5:
            return "critical"
        elif current_regime == "high" or corr_change > 0.3:
            return "high"
        elif corr_change > 0.2 or stability_score < 0.3:
            return "medium"
        else:
            return "low"

    def _get_regime_change_recommendation(self, change: Dict[str, Any]) -> str:
        """Get recommended action for regime change."""
        current_regime = change["current_regime"]
        previous_regime = change["previous_regime"]

        if current_regime == "extreme":
            return "Consider reducing position sizes in correlated pairs"
        elif current_regime == "high" and previous_regime in ["low", "normal"]:
            return "Review portfolio diversification and correlation exposure"
        elif current_regime == "low" and previous_regime in ["high", "extreme"]:
            return "Potential opportunity for increased diversification"
        else:
            return "Monitor correlation development and adjust risk accordingly"

    def _check_extreme_correlations(self, timeframe: str) -> List[CorrelationAlert]:
        """Check for extreme correlation levels."""
        alerts = []

        if timeframe not in self.correlation_matrices:
            return alerts

        matrix = self.correlation_matrices[timeframe]
        extreme_threshold = self.config["regime_thresholds"]["extreme_correlation"]

        for i, pair1 in enumerate(matrix.index):
            for j, pair2 in enumerate(matrix.columns):
                if i >= j:
                    continue

                corr = matrix.loc[pair1, pair2]
                if np.isnan(corr):
                    continue

                if abs(corr) >= extreme_threshold:
                    alert = CorrelationAlert(
                        alert_type="extreme_correlation",
                        severity="critical" if abs(corr) > 0.95 else "high",
                        pair1=pair1,
                        pair2=pair2,
                        current_correlation=corr,
                        threshold_breached=extreme_threshold,
                        message=f"Extreme correlation detected: {pair1}-{pair2} = {corr:.3f}",
                        timestamp=datetime.utcnow(),
                        recommended_action="Reduce exposure to correlated pairs immediately",
                    )
                    alerts.append(alert)

        return alerts

    def _check_diversification_issues(self, timeframe: str) -> List[CorrelationAlert]:
        """Check for portfolio diversification issues."""
        alerts = []

        if timeframe not in self.correlation_matrices:
            return alerts

        matrix = self.correlation_matrices[timeframe]

        # Calculate average correlation
        forex_pairs = [pair for pair in matrix.index if pair in self.currency_pairs]
        if len(forex_pairs) < 2:
            return alerts

        forex_matrix = matrix.loc[forex_pairs, forex_pairs]

        # Calculate diversification score (lower correlation = better diversification)
        upper_triangle = np.triu(forex_matrix, k=1)
        non_zero_mask = upper_triangle != 0
        avg_correlation = np.mean(np.abs(upper_triangle[non_zero_mask]))

        diversification_threshold = self.config["portfolio_analysis"][
            "diversification_threshold"
        ]

        if avg_correlation > diversification_threshold:
            alert = CorrelationAlert(
                alert_type="diversification_loss",
                severity="high" if avg_correlation > 0.7 else "medium",
                pair1="PORTFOLIO",
                pair2="ALL_PAIRS",
                current_correlation=avg_correlation,
                threshold_breached=diversification_threshold,
                message=f"Poor portfolio diversification: Average correlation = {avg_correlation:.3f}",
                timestamp=datetime.utcnow(),
                recommended_action="Reduce position sizes or exclude highly correlated pairs",
            )
            alerts.append(alert)

        return alerts

    def calculate_portfolio_correlation_risk(
        self, positions: Dict[str, float], timeframe: str = "1H"
    ) -> Dict[str, Any]:
        """
        Calculate portfolio-level correlation risk metrics.

        Args:
            positions: Dictionary of pair -> position size
            timeframe: Analysis timeframe

        Returns:
            Portfolio correlation risk metrics
        """
        try:
            if timeframe not in self.correlation_matrices:
                return {}

            matrix = self.correlation_matrices[timeframe]

            # Filter positions to available pairs in correlation matrix
            available_positions = {
                pair: size for pair, size in positions.items() if pair in matrix.index
            }

            if len(available_positions) < 2:
                return {}

            pairs = list(available_positions.keys())
            weights = np.array([available_positions[pair] for pair in pairs])
            weights = weights / np.sum(np.abs(weights))  # Normalize weights

            # Extract correlation submatrix
            corr_submatrix = matrix.loc[pairs, pairs].fillna(0)

            # Calculate portfolio correlation metrics
            portfolio_variance = np.dot(weights, np.dot(corr_submatrix, weights))

            # Individual pair contributions
            pair_contributions = {}
            for i, pair in enumerate(pairs):
                contribution = weights[i] * np.sum(weights * corr_submatrix.iloc[i, :])
                pair_contributions[pair] = contribution

            # Diversification ratio
            weighted_avg_correlation = (np.sum(corr_submatrix.values) - len(pairs)) / (
                len(pairs) * (len(pairs) - 1)
            )
            diversification_ratio = 1.0 - weighted_avg_correlation

            # Risk concentration
            max_correlation = np.max(
                np.abs(corr_submatrix.values[corr_submatrix.values != 1.0])
            )

            return {
                "portfolio_correlation_risk": portfolio_variance,
                "diversification_ratio": diversification_ratio,
                "max_pair_correlation": max_correlation,
                "pair_contributions": pair_contributions,
                "total_positions": len(available_positions),
                "weighted_avg_correlation": weighted_avg_correlation,
                "risk_score": self._calculate_correlation_risk_score(
                    portfolio_variance, diversification_ratio, max_correlation
                ),
            }

        except Exception as e:
            logger.error(f"Error calculating portfolio correlation risk: {e}")
            return {}

    def _calculate_correlation_risk_score(
        self,
        portfolio_variance: float,
        diversification_ratio: float,
        max_correlation: float,
    ) -> float:
        """Calculate overall correlation risk score (0-1, higher = riskier)."""
        try:
            # Combine different risk factors
            variance_score = min(
                portfolio_variance * 2, 1.0
            )  # Scale portfolio variance
            diversification_score = (
                1.0 - diversification_ratio
            )  # Invert (higher = riskier)
            correlation_score = max_correlation

            # Weighted average
            risk_score = (
                variance_score * 0.4
                + diversification_score * 0.35
                + correlation_score * 0.25
            )

            return min(max(risk_score, 0.0), 1.0)  # Clip to [0, 1]

        except:
            return 0.5  # Default moderate risk

    def get_correlation_recommendations(
        self, positions: Dict[str, float], max_correlation_exposure: float = 0.7
    ) -> Dict[str, Any]:
        """
        Get correlation-based trading recommendations.

        Args:
            positions: Current positions
            max_correlation_exposure: Maximum allowed correlation exposure

        Returns:
            Dictionary with recommendations
        """
        recommendations = {
            "reduce_positions": [],
            "avoid_pairs": [],
            "diversification_opportunities": [],
            "risk_assessment": "unknown",
        }

        try:
            # Calculate current portfolio risk
            portfolio_risk = self.calculate_portfolio_correlation_risk(positions)

            if not portfolio_risk:
                return recommendations

            # Risk assessment
            risk_score = portfolio_risk.get("risk_score", 0.5)
            if risk_score > 0.8:
                recommendations["risk_assessment"] = "high"
            elif risk_score > 0.6:
                recommendations["risk_assessment"] = "medium"
            else:
                recommendations["risk_assessment"] = "low"

            # Find highly correlated pairs to reduce
            pair_contributions = portfolio_risk.get("pair_contributions", {})
            for pair, contribution in pair_contributions.items():
                if contribution > max_correlation_exposure:
                    recommendations["reduce_positions"].append(
                        {
                            "pair": pair,
                            "contribution": contribution,
                            "recommended_reduction": (
                                contribution - max_correlation_exposure
                            )
                            * 100,
                        }
                    )

            # Find pairs to avoid (high correlation with existing positions)
            matrix = self.correlation_matrices.get("1H")
            if matrix is not None:
                positioned_pairs = set(positions.keys())
                for pair in self.currency_pairs:
                    if pair not in positioned_pairs and pair in matrix.index:
                        avg_corr_with_positions = np.mean(
                            [
                                abs(matrix.loc[pair, pos_pair])
                                for pos_pair in positioned_pairs
                                if pos_pair in matrix.columns
                                and not np.isnan(matrix.loc[pair, pos_pair])
                            ]
                        )

                        if avg_corr_with_positions > 0.8:
                            recommendations["avoid_pairs"].append(
                                {
                                    "pair": pair,
                                    "avg_correlation": avg_corr_with_positions,
                                }
                            )
                        elif avg_corr_with_positions < 0.3:
                            recommendations["diversification_opportunities"].append(
                                {
                                    "pair": pair,
                                    "avg_correlation": avg_corr_with_positions,
                                    "diversification_benefit": 1.0
                                    - avg_corr_with_positions,
                                }
                            )

            return recommendations

        except Exception as e:
            logger.error(f"Error generating correlation recommendations: {e}")
            return recommendations

    async def start_monitoring(self, update_interval: int = None) -> bool:
        """
        Start real-time correlation monitoring.

        Args:
            update_interval: Update frequency in seconds

        Returns:
            Success status
        """
        try:
            if self.is_monitoring:
                logger.warning("Correlation monitoring already running")
                return False

            update_interval = update_interval or self.config["update_frequency"]

            self.is_monitoring = True

            # Start monitoring in separate thread
            self.monitor_thread = threading.Thread(
                target=self._monitoring_loop, args=(update_interval,), daemon=True
            )
            self.monitor_thread.start()

            logger.info(
                f"Started correlation monitoring with {update_interval}s interval"
            )
            return True

        except Exception as e:
            logger.error(f"Error starting correlation monitoring: {e}")
            return False

    def stop_monitoring(self) -> bool:
        """Stop correlation monitoring."""
        try:
            self.is_monitoring = False

            if self.monitor_thread and self.monitor_thread.is_alive():
                self.monitor_thread.join(timeout=10)

            logger.info("Stopped correlation monitoring")
            return True

        except Exception as e:
            logger.error(f"Error stopping correlation monitoring: {e}")
            return False

    def _monitoring_loop(self, update_interval: int):
        """Main monitoring loop."""
        while self.is_monitoring:
            try:
                # Update correlation matrices
                for timeframe in self.config["correlation_windows"].keys():
                    self.calculate_correlation_matrix(timeframe)

                # Generate alerts
                alerts = self.generate_correlation_alerts()

                if alerts:
                    logger.info(f"Generated {len(alerts)} correlation alerts")
                    for alert in alerts[-5:]:  # Log last 5 alerts
                        logger.info(f"Alert: {alert.message}")

                self.last_update = datetime.utcnow()

                # Sleep until next update
                threading.Event().wait(update_interval)

            except Exception as e:
                logger.error(f"Error in correlation monitoring loop: {e}")
                threading.Event().wait(30)  # Wait 30s on error

    def get_monitoring_status(self) -> Dict[str, Any]:
        """Get current monitoring status."""
        return {
            "is_monitoring": self.is_monitoring,
            "currency_pairs": self.currency_pairs,
            "total_pairs_monitored": len(self.currency_pairs),
            "correlation_matrices": list(self.correlation_matrices.keys()),
            "total_alerts": len(self.alerts),
            "recent_alerts": len(
                [
                    a
                    for a in self.alerts
                    if a.timestamp > datetime.utcnow() - timedelta(hours=24)
                ]
            ),
            "last_update": self.last_update.isoformat() if self.last_update else None,
            "regime_states": len(self.regime_states),
        }

    def export_correlation_data(self, timeframe: str = "1H") -> Dict[str, Any]:
        """Export correlation data for analysis."""
        return {
            "correlation_matrix": self.correlation_matrices.get(
                timeframe, pd.DataFrame()
            ).to_dict(),
            "correlation_metrics": {
                f"{pair[0]}-{pair[1]}": {
                    "pearson_corr": metrics.pearson_corr,
                    "stability_score": metrics.stability_score,
                    "regime": metrics.correlation_regime,
                }
                for pair, metrics in self.correlation_metrics.items()
            },
            "recent_alerts": [
                {
                    "type": alert.alert_type,
                    "severity": alert.severity,
                    "pairs": f"{alert.pair1}-{alert.pair2}",
                    "correlation": alert.current_correlation,
                    "message": alert.message,
                    "timestamp": alert.timestamp.isoformat(),
                }
                for alert in self.alerts[-20:]  # Last 20 alerts
            ],
            "monitoring_status": self.get_monitoring_status(),
        }


# Factory function for easy instantiation
def create_correlation_monitor(
    currency_pairs: List[str] = None, config: Optional[Dict[str, Any]] = None
) -> CrossCurrencyCorrelationMonitor:
    """
    Factory function to create correlation monitor.

    Args:
        currency_pairs: List of pairs to monitor
        config: Configuration parameters

    Returns:
        Configured CrossCurrencyCorrelationMonitor instance
    """
    return CrossCurrencyCorrelationMonitor(currency_pairs=currency_pairs, config=config)
