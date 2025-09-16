"""
Multi-Pair Portfolio Management with Correlation-Based Risk Control for FXML4.

This module provides comprehensive portfolio management across multiple currency pairs,
incorporating correlation-based risk control, dynamic position sizing, and intelligent
rebalancing to optimize risk-adjusted returns while maintaining proper diversification.

Key Features:
- Multi-currency portfolio optimization with correlation constraints
- Dynamic position sizing based on correlation matrices
- Automatic rebalancing triggered by correlation regime changes
- Risk budget allocation across currency pairs and strategies
- Portfolio stress testing and scenario analysis
- Real-time risk monitoring and limit enforcement
- Integration with all currency-specific strategies
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
from scipy.optimize import minimize

warnings.filterwarnings("ignore")

from ..core.events import Event, EventType
from ..risk_management.portfolio_risk import PortfolioRiskManager
from .cross_currency_correlation import CrossCurrencyCorrelationMonitor
from .eurusd_strategy import EURUSDStrategy
from .gbpusd_strategy import GBPUSDStrategy
from .usdchf_strategy import USDCHFStrategy
from .usdjpy_strategy import USDJPYStrategy

logger = logging.getLogger(__name__)


@dataclass
class PositionAllocation:
    """Individual position allocation within portfolio."""

    currency_pair: str
    strategy_name: str
    target_weight: float
    current_weight: float
    position_size: float
    risk_contribution: float
    correlation_risk: float
    individual_risk: float
    last_rebalance: datetime
    rebalance_trigger: str = "none"  # 'correlation', 'risk', 'signal', 'time'


@dataclass
class PortfolioMetrics:
    """Portfolio-level performance and risk metrics."""

    total_value: float
    total_pnl: float
    portfolio_volatility: float
    correlation_risk: float
    diversification_ratio: float
    max_drawdown: float
    sharpe_ratio: float
    var_95: float  # Value at Risk (95%)
    cvar_95: float  # Conditional VaR
    risk_budget_utilization: float
    number_of_positions: int
    average_correlation: float
    concentration_score: float
    last_updated: datetime


@dataclass
class RebalanceRecommendation:
    """Portfolio rebalancing recommendation."""

    currency_pair: str
    current_weight: float
    target_weight: float
    weight_change: float
    reason: str
    priority: str  # 'low', 'medium', 'high', 'critical'
    expected_impact: Dict[str, float]  # Expected impact on risk metrics
    execution_urgency: str  # 'immediate', 'next_session', 'within_day'


class MultiPairPortfolioManager:
    """
    Comprehensive multi-currency portfolio manager with correlation-based risk control.

    Manages positions across multiple currency pairs using correlation-aware
    risk management, dynamic allocation, and intelligent rebalancing.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize multi-pair portfolio manager.

        Args:
            config: Configuration parameters
        """
        self.config = self._get_default_config()
        if config:
            self.config.update(config)

        # Initialize strategy components
        self.correlation_monitor = CrossCurrencyCorrelationMonitor(
            currency_pairs=["GBPUSD", "EURUSD", "USDJPY", "USDCHF"],
            config=self.config.get("correlation_config", {}),
        )

        # Initialize currency-specific strategies
        self.strategies = {
            "GBPUSD": GBPUSDStrategy(),
            "EURUSD": EURUSDStrategy(),
            "USDJPY": USDJPYStrategy(),
            "USDCHF": USDCHFStrategy(),
        }

        # Portfolio state tracking
        self.positions: Dict[str, PositionAllocation] = {}
        self.portfolio_metrics = PortfolioMetrics(
            total_value=0,
            total_pnl=0,
            portfolio_volatility=0,
            correlation_risk=0,
            diversification_ratio=0,
            max_drawdown=0,
            sharpe_ratio=0,
            var_95=0,
            cvar_95=0,
            risk_budget_utilization=0,
            number_of_positions=0,
            average_correlation=0,
            concentration_score=0,
            last_updated=datetime.utcnow(),
        )

        # Risk management
        self.risk_manager = PortfolioRiskManager(self.config.get("risk_config", {}))

        # Portfolio history and performance tracking
        self.portfolio_history: List[PortfolioMetrics] = []
        self.rebalance_history: List[Dict[str, Any]] = []
        self.events: List[Event] = []

        # Monitoring and control
        self.is_active = False
        self.monitoring_thread = None
        self.last_rebalance = datetime.utcnow()

        logger.info(
            "Initialized MultiPairPortfolioManager with correlation-based risk control"
        )

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration parameters."""
        return {
            # Portfolio allocation constraints
            "allocation_constraints": {
                "max_single_pair_weight": 0.4,  # Maximum 40% in any single pair
                "min_position_weight": 0.05,  # Minimum 5% position size
                "max_total_risk": 0.15,  # Maximum 15% portfolio risk
                "target_pairs": 4,  # Target number of active pairs
                "max_correlation_exposure": 0.7,  # Maximum correlation exposure
            },
            # Rebalancing triggers and thresholds
            "rebalancing": {
                "correlation_change_threshold": 0.2,  # Rebalance if correlation changes by 20%
                "weight_drift_threshold": 0.15,  # Rebalance if weights drift by 15%
                "risk_breach_threshold": 1.2,  # Rebalance if risk exceeds target by 20%
                "time_based_frequency": 24,  # Hours between time-based rebalances
                "min_rebalance_interval": 4,  # Minimum hours between rebalances
                "emergency_threshold": 0.25,  # Emergency rebalance threshold
            },
            # Risk management parameters
            "risk_management": {
                "var_confidence_level": 0.95,
                "lookback_period": 252,  # Days for risk calculations
                "stress_test_scenarios": 5,  # Number of stress test scenarios
                "max_drawdown_limit": 0.20,  # 20% maximum drawdown
                "correlation_stress_factor": 1.5,  # Stress test correlation multiplier
                "volatility_multiplier": 1.2,  # Safety margin for volatility estimates
            },
            # Performance optimization
            "optimization": {
                "objective": "sharpe_ratio",  # 'sharpe_ratio', 'information_ratio', 'risk_parity'
                "constraint_tolerance": 0.01,  # Optimization constraint tolerance
                "max_iterations": 100,  # Maximum optimization iterations
                "convergence_threshold": 1e-6,  # Optimization convergence threshold
                "regularization_factor": 0.01,  # L2 regularization for stability
            },
            # Signal integration
            "signal_integration": {
                "signal_weight_cap": 0.3,  # Maximum weight adjustment from signals
                "signal_decay_hours": 12,  # Signal strength decay period
                "min_signal_strength": 0.6,  # Minimum signal strength for allocation
                "signal_correlation_adjustment": True,  # Adjust signals for correlation
            },
            # Monitoring and alerts
            "monitoring": {
                "update_frequency": 300,  # Update every 5 minutes
                "alert_thresholds": {
                    "high_correlation": 0.8,
                    "concentration_risk": 0.5,
                    "risk_budget_breach": 1.1,
                },
                "performance_tracking_window": 30,  # Days for performance tracking
            },
        }

    async def initialize_portfolio(
        self,
        initial_capital: float,
        target_allocations: Optional[Dict[str, float]] = None,
    ) -> bool:
        """
        Initialize portfolio with target allocations.

        Args:
            initial_capital: Initial portfolio capital
            target_allocations: Target weight allocations by currency pair

        Returns:
            Success status
        """
        try:
            logger.info(f"Initializing portfolio with ${initial_capital:,.2f} capital")

            # Set default equal-weight allocation if not provided
            if target_allocations is None:
                num_pairs = len(self.strategies)
                target_allocations = {
                    pair: 1.0 / num_pairs for pair in self.strategies.keys()
                }

            # Validate and normalize allocations
            total_weight = sum(target_allocations.values())
            if abs(total_weight - 1.0) > 0.01:
                logger.warning(
                    f"Target allocations sum to {total_weight:.3f}, normalizing..."
                )
                target_allocations = {
                    pair: weight / total_weight
                    for pair, weight in target_allocations.items()
                }

            # Initialize positions
            current_time = datetime.utcnow()
            for pair, target_weight in target_allocations.items():
                if pair in self.strategies:
                    self.positions[pair] = PositionAllocation(
                        currency_pair=pair,
                        strategy_name=self.strategies[pair].name,
                        target_weight=target_weight,
                        current_weight=target_weight,  # Start at target
                        position_size=initial_capital * target_weight,
                        risk_contribution=0.0,  # Will be calculated
                        correlation_risk=0.0,
                        individual_risk=0.0,
                        last_rebalance=current_time,
                    )

            # Initialize portfolio metrics
            self.portfolio_metrics.total_value = initial_capital
            self.portfolio_metrics.number_of_positions = len(self.positions)
            self.portfolio_metrics.last_updated = current_time

            # Start correlation monitoring
            await self.correlation_monitor.start_monitoring()

            # Calculate initial risk metrics
            await self.update_portfolio_metrics()

            logger.info(f"Portfolio initialized with {len(self.positions)} positions")
            return True

        except Exception as e:
            logger.error(f"Error initializing portfolio: {e}")
            return False

    async def update_portfolio_metrics(self) -> bool:
        """Update comprehensive portfolio metrics."""
        try:
            if not self.positions:
                return False

            # Calculate current portfolio value and weights
            total_value = sum(pos.position_size for pos in self.positions.values())

            # Update current weights
            for position in self.positions.values():
                position.current_weight = (
                    position.position_size / total_value if total_value > 0 else 0
                )

            # Get correlation matrix
            correlation_matrix = self.correlation_monitor.calculate_correlation_matrix(
                "1H"
            )

            # Calculate portfolio-level metrics
            if not correlation_matrix.empty:
                portfolio_risk = (
                    self.correlation_monitor.calculate_portfolio_correlation_risk(
                        {
                            pos.currency_pair: pos.current_weight
                            for pos in self.positions.values()
                        },
                        "1H",
                    )
                )

                self.portfolio_metrics.correlation_risk = portfolio_risk.get(
                    "portfolio_correlation_risk", 0
                )
                self.portfolio_metrics.diversification_ratio = portfolio_risk.get(
                    "diversification_ratio", 0
                )
                self.portfolio_metrics.average_correlation = portfolio_risk.get(
                    "weighted_avg_correlation", 0
                )

            # Update individual position risk contributions
            await self._update_position_risk_contributions()

            # Calculate concentration metrics
            weights = [pos.current_weight for pos in self.positions.values()]
            self.portfolio_metrics.concentration_score = (
                self._calculate_concentration_score(weights)
            )

            # Update portfolio totals
            self.portfolio_metrics.total_value = total_value
            self.portfolio_metrics.number_of_positions = len(self.positions)
            self.portfolio_metrics.last_updated = datetime.utcnow()

            # Store in history
            self.portfolio_history.append(self.portfolio_metrics)
            if len(self.portfolio_history) > 1000:  # Keep last 1000 records
                self.portfolio_history = self.portfolio_history[-1000:]

            return True

        except Exception as e:
            logger.error(f"Error updating portfolio metrics: {e}")
            return False

    async def _update_position_risk_contributions(self):
        """Update risk contribution for each position."""
        try:
            correlation_matrix = self.correlation_monitor.calculate_correlation_matrix(
                "1H"
            )
            if correlation_matrix.empty:
                return

            for position in self.positions.values():
                pair = position.currency_pair

                if pair not in correlation_matrix.index:
                    continue

                # Individual risk (simplified volatility measure)
                # In production, this would use actual volatility calculations
                position.individual_risk = 0.15  # Placeholder: 15% annual volatility

                # Correlation risk contribution
                other_positions = {
                    other_pair: other_pos.current_weight
                    for other_pair, other_pos in self.positions.items()
                    if other_pair != pair and other_pair in correlation_matrix.columns
                }

                if other_positions:
                    correlation_risk = 0
                    for other_pair, other_weight in other_positions.items():
                        corr = correlation_matrix.loc[pair, other_pair]
                        if not np.isnan(corr):
                            correlation_risk += (
                                position.current_weight * other_weight * abs(corr)
                            )

                    position.correlation_risk = correlation_risk

                # Total risk contribution (simplified)
                position.risk_contribution = (
                    position.individual_risk * position.current_weight
                    + position.correlation_risk
                )

        except Exception as e:
            logger.error(f"Error updating position risk contributions: {e}")

    def _calculate_concentration_score(self, weights: List[float]) -> float:
        """Calculate portfolio concentration score (Herfindahl index)."""
        if not weights:
            return 0.0

        # Herfindahl-Hirschman Index
        hhi = sum(w**2 for w in weights)

        # Normalize to 0-1 scale (1 = maximum concentration)
        n = len(weights)
        normalized_hhi = (hhi - 1 / n) / (1 - 1 / n) if n > 1 else 0

        return normalized_hhi

    async def generate_rebalancing_recommendations(
        self,
    ) -> List[RebalanceRecommendation]:
        """
        Generate portfolio rebalancing recommendations.

        Returns:
            List of rebalancing recommendations
        """
        recommendations = []

        try:
            if not self.positions:
                return recommendations

            # Check for correlation-driven rebalancing
            correlation_recs = await self._analyze_correlation_rebalancing()
            recommendations.extend(correlation_recs)

            # Check for risk-driven rebalancing
            risk_recs = await self._analyze_risk_rebalancing()
            recommendations.extend(risk_recs)

            # Check for signal-driven rebalancing
            signal_recs = await self._analyze_signal_rebalancing()
            recommendations.extend(signal_recs)

            # Check for time-driven rebalancing
            time_recs = await self._analyze_time_rebalancing()
            recommendations.extend(time_recs)

            # Optimize and prioritize recommendations
            optimized_recs = await self._optimize_rebalancing_recommendations(
                recommendations
            )

            logger.info(f"Generated {len(optimized_recs)} rebalancing recommendations")
            return optimized_recs

        except Exception as e:
            logger.error(f"Error generating rebalancing recommendations: {e}")
            return recommendations

    async def _analyze_correlation_rebalancing(self) -> List[RebalanceRecommendation]:
        """Analyze correlation-driven rebalancing needs."""
        recommendations = []

        try:
            # Get correlation recommendations from monitor
            position_weights = {
                pos.currency_pair: pos.current_weight for pos in self.positions.values()
            }

            corr_recommendations = (
                self.correlation_monitor.get_correlation_recommendations(
                    position_weights,
                    self.config["allocation_constraints"]["max_correlation_exposure"],
                )
            )

            # Convert to rebalancing recommendations
            for reduction in corr_recommendations.get("reduce_positions", []):
                pair = reduction["pair"]
                current_weight = position_weights.get(pair, 0)
                reduction_pct = reduction.get("recommended_reduction", 0) / 100
                target_weight = max(
                    current_weight * (1 - reduction_pct),
                    self.config["allocation_constraints"]["min_position_weight"],
                )

                if current_weight - target_weight > 0.05:  # Minimum 5% change
                    recommendations.append(
                        RebalanceRecommendation(
                            currency_pair=pair,
                            current_weight=current_weight,
                            target_weight=target_weight,
                            weight_change=target_weight - current_weight,
                            reason=f"High correlation exposure: {reduction['contribution']:.1%}",
                            priority=(
                                "high" if reduction["contribution"] > 0.8 else "medium"
                            ),
                            expected_impact={"correlation_risk": -0.1},
                            execution_urgency="next_session",
                        )
                    )

            return recommendations

        except Exception as e:
            logger.error(f"Error analyzing correlation rebalancing: {e}")
            return []

    async def _analyze_risk_rebalancing(self) -> List[RebalanceRecommendation]:
        """Analyze risk-driven rebalancing needs."""
        recommendations = []

        try:
            risk_budget = self.config["allocation_constraints"]["max_total_risk"]
            current_risk = self.portfolio_metrics.correlation_risk

            if (
                current_risk
                > risk_budget * self.config["rebalancing"]["risk_breach_threshold"]
            ):
                # Portfolio risk exceeded, recommend reducing highest risk positions
                risk_contributions = [
                    (pos.currency_pair, pos.risk_contribution)
                    for pos in self.positions.values()
                ]
                risk_contributions.sort(key=lambda x: x[1], reverse=True)

                # Reduce top risk contributors
                for pair, risk_contrib in risk_contributions[:2]:  # Top 2 contributors
                    position = self.positions[pair]
                    reduction_factor = min(
                        0.3, (current_risk - risk_budget) / current_risk
                    )
                    target_weight = position.current_weight * (1 - reduction_factor)
                    target_weight = max(
                        target_weight,
                        self.config["allocation_constraints"]["min_position_weight"],
                    )

                    if position.current_weight - target_weight > 0.05:
                        recommendations.append(
                            RebalanceRecommendation(
                                currency_pair=pair,
                                current_weight=position.current_weight,
                                target_weight=target_weight,
                                weight_change=target_weight - position.current_weight,
                                reason=f"Risk budget breach: {current_risk:.1%} > {risk_budget:.1%}",
                                priority="critical",
                                expected_impact={"portfolio_risk": -0.05},
                                execution_urgency="immediate",
                            )
                        )

            return recommendations

        except Exception as e:
            logger.error(f"Error analyzing risk rebalancing: {e}")
            return []

    async def _analyze_signal_rebalancing(self) -> List[RebalanceRecommendation]:
        """Analyze signal-driven rebalancing opportunities."""
        recommendations = []

        try:
            # This would integrate with actual signal generation from strategies
            # For now, implementing a simplified version

            signal_weight_cap = self.config["signal_integration"]["signal_weight_cap"]
            min_signal_strength = self.config["signal_integration"][
                "min_signal_strength"
            ]

            # Placeholder: In production, get real signals from strategies
            strong_signals = {
                "EURUSD": {"strength": 0.8, "direction": 1},  # Strong buy
                "USDJPY": {"strength": 0.7, "direction": -1},  # Strong sell
            }

            for pair, signal in strong_signals.items():
                if pair not in self.positions:
                    continue

                signal_strength = signal["strength"]
                if signal_strength < min_signal_strength:
                    continue

                position = self.positions[pair]
                current_weight = position.current_weight

                # Calculate target adjustment based on signal
                if signal["direction"] > 0:  # Buy signal
                    weight_adjustment = signal_strength * signal_weight_cap
                    target_weight = min(
                        current_weight + weight_adjustment,
                        self.config["allocation_constraints"]["max_single_pair_weight"],
                    )
                else:  # Sell signal
                    weight_adjustment = signal_strength * signal_weight_cap
                    target_weight = max(
                        current_weight - weight_adjustment,
                        self.config["allocation_constraints"]["min_position_weight"],
                    )

                if abs(target_weight - current_weight) > 0.05:  # Minimum 5% change
                    recommendations.append(
                        RebalanceRecommendation(
                            currency_pair=pair,
                            current_weight=current_weight,
                            target_weight=target_weight,
                            weight_change=target_weight - current_weight,
                            reason=f"Strong signal: {signal_strength:.1%} strength",
                            priority="medium",
                            expected_impact={"expected_return": signal_strength * 0.1},
                            execution_urgency="next_session",
                        )
                    )

            return recommendations

        except Exception as e:
            logger.error(f"Error analyzing signal rebalancing: {e}")
            return []

    async def _analyze_time_rebalancing(self) -> List[RebalanceRecommendation]:
        """Analyze time-based rebalancing needs."""
        recommendations = []

        try:
            time_frequency = self.config["rebalancing"]["time_based_frequency"]
            hours_since_rebalance = (
                datetime.utcnow() - self.last_rebalance
            ).total_seconds() / 3600

            if hours_since_rebalance >= time_frequency:
                # Check for significant weight drift from targets
                drift_threshold = self.config["rebalancing"]["weight_drift_threshold"]

                for position in self.positions.values():
                    weight_drift = abs(position.current_weight - position.target_weight)

                    if weight_drift > drift_threshold:
                        recommendations.append(
                            RebalanceRecommendation(
                                currency_pair=position.currency_pair,
                                current_weight=position.current_weight,
                                target_weight=position.target_weight,
                                weight_change=position.target_weight
                                - position.current_weight,
                                reason=f"Time-based rebalance: {weight_drift:.1%} drift",
                                priority="low",
                                expected_impact={"tracking_error": -weight_drift},
                                execution_urgency="within_day",
                            )
                        )

            return recommendations

        except Exception as e:
            logger.error(f"Error analyzing time rebalancing: {e}")
            return []

    async def _optimize_rebalancing_recommendations(
        self, recommendations: List[RebalanceRecommendation]
    ) -> List[RebalanceRecommendation]:
        """Optimize and prioritize rebalancing recommendations."""
        try:
            if not recommendations:
                return recommendations

            # Group recommendations by currency pair
            pair_recommendations = defaultdict(list)
            for rec in recommendations:
                pair_recommendations[rec.currency_pair].append(rec)

            # Optimize recommendations for each pair
            optimized_recs = []
            for pair, pair_recs in pair_recommendations.items():
                if len(pair_recs) == 1:
                    optimized_recs.append(pair_recs[0])
                else:
                    # Multiple recommendations for same pair - optimize
                    optimized_rec = await self._optimize_pair_recommendations(
                        pair, pair_recs
                    )
                    if optimized_rec:
                        optimized_recs.append(optimized_rec)

            # Sort by priority and expected impact
            priority_order = {"critical": 4, "high": 3, "medium": 2, "low": 1}
            optimized_recs.sort(
                key=lambda x: (priority_order.get(x.priority, 0), abs(x.weight_change)),
                reverse=True,
            )

            return optimized_recs

        except Exception as e:
            logger.error(f"Error optimizing rebalancing recommendations: {e}")
            return recommendations

    async def _optimize_pair_recommendations(
        self, pair: str, recommendations: List[RebalanceRecommendation]
    ) -> Optional[RebalanceRecommendation]:
        """Optimize multiple recommendations for a single currency pair."""
        try:
            if not recommendations:
                return None

            # Weight recommendations by priority and expected impact
            priority_weights = {"critical": 4, "high": 3, "medium": 2, "low": 1}

            weighted_target = 0
            total_weight = 0
            combined_reasons = []
            max_priority = "low"

            for rec in recommendations:
                weight = priority_weights.get(rec.priority, 1)
                weighted_target += rec.target_weight * weight
                total_weight += weight
                combined_reasons.append(rec.reason)

                if priority_weights.get(rec.priority, 0) > priority_weights.get(
                    max_priority, 0
                ):
                    max_priority = rec.priority

            if total_weight == 0:
                return recommendations[0]  # Fallback

            optimized_target = weighted_target / total_weight
            current_weight = recommendations[0].current_weight

            return RebalanceRecommendation(
                currency_pair=pair,
                current_weight=current_weight,
                target_weight=optimized_target,
                weight_change=optimized_target - current_weight,
                reason=f"Combined: {'; '.join(combined_reasons[:2])}",  # Top 2 reasons
                priority=max_priority,
                expected_impact={},  # Would calculate combined impact
                execution_urgency=recommendations[0].execution_urgency,
            )

        except Exception as e:
            logger.error(f"Error optimizing pair recommendations for {pair}: {e}")
            return recommendations[0] if recommendations else None

    async def execute_rebalancing(
        self, recommendations: List[RebalanceRecommendation], dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Execute portfolio rebalancing based on recommendations.

        Args:
            recommendations: List of rebalancing recommendations
            dry_run: If True, simulate rebalancing without executing

        Returns:
            Execution results and statistics
        """
        results = {
            "executed_count": 0,
            "total_recommendations": len(recommendations),
            "execution_errors": [],
            "before_metrics": self.portfolio_metrics,
            "after_metrics": None,
            "execution_time": datetime.utcnow(),
            "dry_run": dry_run,
        }

        try:
            logger.info(
                f"{'Simulating' if dry_run else 'Executing'} {len(recommendations)} rebalancing recommendations"
            )

            if not recommendations:
                return results

            # Check minimum rebalance interval
            min_interval = self.config["rebalancing"]["min_rebalance_interval"]
            hours_since_last = (
                datetime.utcnow() - self.last_rebalance
            ).total_seconds() / 3600

            if hours_since_last < min_interval and not dry_run:
                logger.warning(
                    f"Minimum rebalance interval not met: {hours_since_last:.1f} < {min_interval}"
                )
                return results

            # Execute each recommendation
            for rec in recommendations:
                try:
                    if rec.currency_pair not in self.positions:
                        continue

                    position = self.positions[rec.currency_pair]

                    if not dry_run:
                        # Update position allocation
                        old_weight = position.current_weight
                        position.target_weight = rec.target_weight
                        position.last_rebalance = datetime.utcnow()
                        position.rebalance_trigger = rec.reason.split(":")[0].lower()

                        # Recalculate position size based on current portfolio value
                        total_value = self.portfolio_metrics.total_value
                        new_position_size = total_value * rec.target_weight
                        position.position_size = new_position_size
                        position.current_weight = rec.target_weight

                        logger.info(
                            f"Rebalanced {rec.currency_pair}: {old_weight:.1%} → {rec.target_weight:.1%}"
                        )

                    results["executed_count"] += 1

                    # Store rebalance record
                    rebalance_record = {
                        "timestamp": datetime.utcnow(),
                        "currency_pair": rec.currency_pair,
                        "old_weight": (
                            position.current_weight if dry_run else old_weight
                        ),
                        "new_weight": rec.target_weight,
                        "reason": rec.reason,
                        "priority": rec.priority,
                        "dry_run": dry_run,
                    }

                    if not dry_run:
                        self.rebalance_history.append(rebalance_record)

                except Exception as e:
                    error_msg = f"Error rebalancing {rec.currency_pair}: {e}"
                    logger.error(error_msg)
                    results["execution_errors"].append(error_msg)

            if not dry_run and results["executed_count"] > 0:
                # Update last rebalance time
                self.last_rebalance = datetime.utcnow()

                # Recalculate portfolio metrics
                await self.update_portfolio_metrics()
                results["after_metrics"] = self.portfolio_metrics

                # Generate rebalance event
                event = Event(
                    event_type=EventType.PORTFOLIO_REBALANCE,
                    timestamp=datetime.utcnow(),
                    data={
                        "rebalanced_positions": results["executed_count"],
                        "total_recommendations": results["total_recommendations"],
                        "success_rate": results["executed_count"]
                        / len(recommendations),
                    },
                )
                self.events.append(event)

                logger.info(
                    f"Portfolio rebalancing completed: {results['executed_count']} positions updated"
                )

            return results

        except Exception as e:
            logger.error(f"Error executing portfolio rebalancing: {e}")
            results["execution_errors"].append(str(e))
            return results

    async def run_stress_tests(self) -> Dict[str, Any]:
        """
        Run portfolio stress tests under various market scenarios.

        Returns:
            Stress test results and risk metrics
        """
        stress_results = {
            "scenarios": {},
            "worst_case_loss": 0,
            "best_case_gain": 0,
            "average_impact": 0,
            "positions_at_risk": [],
            "recommendations": [],
        }

        try:
            # Define stress test scenarios
            scenarios = {
                "correlation_spike": {
                    "description": "All correlations increase to 0.9",
                    "correlation_multiplier": 3.0,
                    "volatility_multiplier": 1.0,
                },
                "volatility_shock": {
                    "description": "50% increase in all volatilities",
                    "correlation_multiplier": 1.0,
                    "volatility_multiplier": 1.5,
                },
                "combined_stress": {
                    "description": "High correlation + high volatility",
                    "correlation_multiplier": 2.0,
                    "volatility_multiplier": 1.3,
                },
                "safe_haven_flight": {
                    "description": "Flight to safe havens (USD, CHF strength)",
                    "correlation_multiplier": 1.5,
                    "volatility_multiplier": 1.2,
                    "pair_specific_shocks": {"USDCHF": -0.1, "USDJPY": -0.1},
                },
                "risk_on_rally": {
                    "description": "Risk-on rally (USD weakness)",
                    "correlation_multiplier": 1.2,
                    "volatility_multiplier": 0.8,
                    "pair_specific_shocks": {"EURUSD": 0.1, "GBPUSD": 0.1},
                },
            }

            # Run each stress test scenario
            scenario_results = []
            for scenario_name, scenario_config in scenarios.items():
                scenario_result = await self._run_single_stress_test(
                    scenario_name, scenario_config
                )
                stress_results["scenarios"][scenario_name] = scenario_result
                scenario_results.append(scenario_result["portfolio_impact"])

            # Calculate aggregate stress metrics
            stress_results["worst_case_loss"] = min(scenario_results)
            stress_results["best_case_gain"] = max(scenario_results)
            stress_results["average_impact"] = np.mean(scenario_results)

            # Identify positions most at risk
            position_risks = []
            for position in self.positions.values():
                avg_scenario_impact = np.mean(
                    [
                        result.get("position_impacts", {}).get(
                            position.currency_pair, 0
                        )
                        for result in stress_results["scenarios"].values()
                    ]
                )

                if avg_scenario_impact < -0.05:  # More than 5% average loss
                    position_risks.append(
                        {
                            "currency_pair": position.currency_pair,
                            "current_weight": position.current_weight,
                            "average_stress_impact": avg_scenario_impact,
                            "risk_level": (
                                "high" if avg_scenario_impact < -0.1 else "medium"
                            ),
                        }
                    )

            stress_results["positions_at_risk"] = sorted(
                position_risks, key=lambda x: x["average_stress_impact"]
            )

            # Generate recommendations based on stress test results
            if stress_results["worst_case_loss"] < -0.15:  # Worst case > 15% loss
                stress_results["recommendations"].append(
                    "Consider reducing overall portfolio risk exposure"
                )

            if len(stress_results["positions_at_risk"]) > len(self.positions) * 0.5:
                stress_results["recommendations"].append(
                    "High concentration of at-risk positions - improve diversification"
                )

            logger.info(
                f"Stress testing completed. Worst case: {stress_results['worst_case_loss']:.1%}"
            )
            return stress_results

        except Exception as e:
            logger.error(f"Error running portfolio stress tests: {e}")
            return stress_results

    async def _run_single_stress_test(
        self, scenario_name: str, scenario_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Run a single stress test scenario."""
        try:
            # Get current correlation matrix
            correlation_matrix = self.correlation_monitor.calculate_correlation_matrix(
                "1H"
            )

            if correlation_matrix.empty:
                return {"portfolio_impact": 0, "position_impacts": {}}

            # Apply stress scenario
            stressed_correlations = (
                correlation_matrix * scenario_config["correlation_multiplier"]
            )
            stressed_correlations = np.clip(
                stressed_correlations, -0.99, 0.99
            )  # Keep within valid range

            # Calculate stressed portfolio risk
            position_weights = {
                pos.currency_pair: pos.current_weight for pos in self.positions.values()
            }

            # Simplified stress calculation (in production, use more sophisticated models)
            portfolio_impact = 0
            position_impacts = {}

            for pair, weight in position_weights.items():
                # Individual position stress impact
                individual_impact = (
                    -weight * 0.1 * scenario_config["volatility_multiplier"]
                )  # Simplified

                # Add pair-specific shocks if defined
                pair_shock = scenario_config.get("pair_specific_shocks", {}).get(
                    pair, 0
                )
                individual_impact += weight * pair_shock

                position_impacts[pair] = individual_impact
                portfolio_impact += individual_impact

            # Add correlation stress impact
            if len(position_weights) > 1:
                avg_correlation_increase = (
                    scenario_config["correlation_multiplier"] - 1
                ) * 0.1
                correlation_impact = (
                    -avg_correlation_increase * sum(position_weights.values()) * 0.5
                )
                portfolio_impact += correlation_impact

            return {
                "scenario_name": scenario_name,
                "portfolio_impact": portfolio_impact,
                "position_impacts": position_impacts,
                "correlation_impact": (
                    correlation_impact if "correlation_impact" in locals() else 0
                ),
            }

        except Exception as e:
            logger.error(f"Error running stress test scenario {scenario_name}: {e}")
            return {"portfolio_impact": 0, "position_impacts": {}}

    async def start_monitoring(self) -> bool:
        """Start portfolio monitoring and automatic rebalancing."""
        try:
            if self.is_active:
                logger.warning("Portfolio manager already active")
                return False

            self.is_active = True

            # Start monitoring thread
            self.monitoring_thread = threading.Thread(
                target=self._monitoring_loop, daemon=True
            )
            self.monitoring_thread.start()

            logger.info("Started portfolio monitoring and management")
            return True

        except Exception as e:
            logger.error(f"Error starting portfolio monitoring: {e}")
            return False

    def stop_monitoring(self) -> bool:
        """Stop portfolio monitoring."""
        try:
            self.is_active = False

            if self.monitoring_thread and self.monitoring_thread.is_alive():
                self.monitoring_thread.join(timeout=10)

            self.correlation_monitor.stop_monitoring()

            logger.info("Stopped portfolio monitoring")
            return True

        except Exception as e:
            logger.error(f"Error stopping portfolio monitoring: {e}")
            return False

    def _monitoring_loop(self):
        """Main portfolio monitoring loop."""
        update_frequency = self.config["monitoring"]["update_frequency"]

        while self.is_active:
            try:
                # Update portfolio metrics
                asyncio.run(self.update_portfolio_metrics())

                # Check for rebalancing needs
                recommendations = asyncio.run(
                    self.generate_rebalancing_recommendations()
                )

                # Execute critical and high priority rebalances automatically
                critical_recs = [
                    rec
                    for rec in recommendations
                    if rec.priority in ["critical", "high"]
                ]
                if critical_recs:
                    logger.info(
                        f"Executing {len(critical_recs)} critical/high priority rebalances"
                    )
                    asyncio.run(self.execute_rebalancing(critical_recs))

                # Check alert conditions
                await self._check_alert_conditions()

                # Sleep until next update
                threading.Event().wait(update_frequency)

            except Exception as e:
                logger.error(f"Error in portfolio monitoring loop: {e}")
                threading.Event().wait(60)  # Wait 1 minute on error

    async def _check_alert_conditions(self):
        """Check for alert conditions and generate events."""
        try:
            alert_thresholds = self.config["monitoring"]["alert_thresholds"]

            # High correlation alert
            if (
                self.portfolio_metrics.average_correlation
                > alert_thresholds["high_correlation"]
            ):
                event = Event(
                    event_type=EventType.RISK_ALERT,
                    timestamp=datetime.utcnow(),
                    data={
                        "alert_type": "high_correlation",
                        "current_correlation": self.portfolio_metrics.average_correlation,
                        "threshold": alert_thresholds["high_correlation"],
                    },
                )
                self.events.append(event)

            # Concentration risk alert
            if (
                self.portfolio_metrics.concentration_score
                > alert_thresholds["concentration_risk"]
            ):
                event = Event(
                    event_type=EventType.RISK_ALERT,
                    timestamp=datetime.utcnow(),
                    data={
                        "alert_type": "concentration_risk",
                        "concentration_score": self.portfolio_metrics.concentration_score,
                        "threshold": alert_thresholds["concentration_risk"],
                    },
                )
                self.events.append(event)

        except Exception as e:
            logger.error(f"Error checking alert conditions: {e}")

    def get_portfolio_status(self) -> Dict[str, Any]:
        """Get comprehensive portfolio status."""
        return {
            "portfolio_metrics": {
                "total_value": self.portfolio_metrics.total_value,
                "total_pnl": self.portfolio_metrics.total_pnl,
                "number_of_positions": self.portfolio_metrics.number_of_positions,
                "correlation_risk": self.portfolio_metrics.correlation_risk,
                "diversification_ratio": self.portfolio_metrics.diversification_ratio,
                "concentration_score": self.portfolio_metrics.concentration_score,
                "last_updated": self.portfolio_metrics.last_updated.isoformat(),
            },
            "positions": {
                pos.currency_pair: {
                    "current_weight": pos.current_weight,
                    "target_weight": pos.target_weight,
                    "position_size": pos.position_size,
                    "risk_contribution": pos.risk_contribution,
                    "last_rebalance": pos.last_rebalance.isoformat(),
                }
                for pos in self.positions.values()
            },
            "monitoring_status": {
                "is_active": self.is_active,
                "last_rebalance": self.last_rebalance.isoformat(),
                "recent_events": len(
                    [
                        e
                        for e in self.events
                        if e.timestamp > datetime.utcnow() - timedelta(hours=24)
                    ]
                ),
                "correlation_monitoring": self.correlation_monitor.get_monitoring_status(),
            },
        }


# Factory function for easy instantiation
def create_portfolio_manager(
    config: Optional[Dict[str, Any]] = None
) -> MultiPairPortfolioManager:
    """
    Factory function to create multi-pair portfolio manager.

    Args:
        config: Configuration parameters

    Returns:
        Configured MultiPairPortfolioManager instance
    """
    return MultiPairPortfolioManager(config=config)
