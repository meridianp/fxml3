"""Enhanced position sizing algorithms for optimal performance.

This module provides advanced position sizing algorithms that integrate ML confidence,
performance tracking, volatility regimes, and other optimizations.
"""

import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from fxml4.backtesting.event import SignalEvent
from fxml4.backtesting.risk_management import PositionSizer
from fxml4.config import get_config

logger = logging.getLogger(__name__)


class VolatilityRegime(Enum):
    """Volatility regime classifications."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    EXTREME = "extreme"


class VolatilityRegimeDetector:
    """Detects current volatility regime for position sizing adjustments."""

    def __init__(
        self,
        lookback_periods: int = 252,
        low_percentile: float = 20,
        high_percentile: float = 80,
        extreme_percentile: float = 95,
    ):
        """Initialize volatility regime detector.

        Args:
            lookback_periods: Number of periods for historical volatility.
            low_percentile: Percentile threshold for low volatility.
            high_percentile: Percentile threshold for high volatility.
            extreme_percentile: Percentile threshold for extreme volatility.
        """
        self.lookback_periods = lookback_periods
        self.low_percentile = low_percentile
        self.high_percentile = high_percentile
        self.extreme_percentile = extreme_percentile
        self.volatility_history = {}

    def update_volatility(self, symbol: str, returns: pd.Series) -> None:
        """Update volatility history for a symbol.

        Args:
            symbol: Trading symbol.
            returns: Series of returns.
        """
        if symbol not in self.volatility_history:
            self.volatility_history[symbol] = []

        # Calculate realized volatility
        current_vol = returns.std() * np.sqrt(252)  # Annualized
        self.volatility_history[symbol].append(current_vol)

        # Keep only recent history
        if len(self.volatility_history[symbol]) > self.lookback_periods:
            self.volatility_history[symbol] = self.volatility_history[symbol][
                -self.lookback_periods :
            ]

    def get_regime(
        self, symbol: str, current_volatility: Optional[float] = None
    ) -> VolatilityRegime:
        """Get current volatility regime for a symbol.

        Args:
            symbol: Trading symbol.
            current_volatility: Current volatility (if not provided, uses latest).

        Returns:
            Current volatility regime.
        """
        if (
            symbol not in self.volatility_history
            or len(self.volatility_history[symbol]) < 20
        ):
            return VolatilityRegime.NORMAL

        history = np.array(self.volatility_history[symbol])

        if current_volatility is None:
            current_volatility = history[-1]

        # Calculate percentiles
        low_threshold = np.percentile(history, self.low_percentile)
        high_threshold = np.percentile(history, self.high_percentile)
        extreme_threshold = np.percentile(history, self.extreme_percentile)

        # Determine regime
        if current_volatility >= extreme_threshold:
            return VolatilityRegime.EXTREME
        elif current_volatility >= high_threshold:
            return VolatilityRegime.HIGH
        elif current_volatility <= low_threshold:
            return VolatilityRegime.LOW
        else:
            return VolatilityRegime.NORMAL


class PerformanceTracker:
    """Tracks trading performance for dynamic position sizing."""

    def __init__(self, lookback_trades: int = 20):
        """Initialize performance tracker.

        Args:
            lookback_trades: Number of recent trades to consider.
        """
        self.lookback_trades = lookback_trades
        self.trade_history = []
        self.win_rates = {}
        self.profit_factors = {}
        self.sharpe_ratios = {}
        self.max_drawdowns = {}

    def add_trade(self, trade_result: Dict[str, Any]) -> None:
        """Add a trade result to history.

        Args:
            trade_result: Dictionary with trade information.
        """
        self.trade_history.append(trade_result)

        # Keep only recent trades
        if len(self.trade_history) > self.lookback_trades * 2:
            self.trade_history = self.trade_history[-self.lookback_trades * 2 :]

        # Update performance metrics
        self._update_metrics()

    def _update_metrics(self) -> None:
        """Update performance metrics based on recent trades."""
        if len(self.trade_history) < 5:
            return

        # Calculate metrics for recent trades
        recent_trades = self.trade_history[-self.lookback_trades :]

        # Win rate
        wins = sum(1 for t in recent_trades if t.get("pnl", 0) > 0)
        self.win_rates["recent"] = wins / len(recent_trades) if recent_trades else 0

        # Profit factor
        gross_profit = sum(t["pnl"] for t in recent_trades if t.get("pnl", 0) > 0)
        gross_loss = abs(sum(t["pnl"] for t in recent_trades if t.get("pnl", 0) < 0))
        self.profit_factors["recent"] = (
            gross_profit / gross_loss if gross_loss > 0 else float("inf")
        )

        # Rolling Sharpe ratio (simplified)
        returns = [t.get("return", 0) for t in recent_trades]
        if returns:
            mean_return = np.mean(returns)
            std_return = np.std(returns)
            self.sharpe_ratios["recent"] = (
                mean_return / std_return * np.sqrt(252) if std_return > 0 else 0
            )

        # Max drawdown
        cumulative_returns = np.cumprod([1 + r for r in returns])
        running_max = np.maximum.accumulate(cumulative_returns)
        drawdowns = (cumulative_returns - running_max) / running_max
        self.max_drawdowns["recent"] = np.min(drawdowns)

    def get_performance_score(self) -> float:
        """Get a composite performance score for position sizing.

        Returns:
            Performance score between 0 and 1.
        """
        if len(self.trade_history) < 5:
            return 0.5  # Neutral score for insufficient data

        # Weighted composite score
        win_rate_score = self.win_rates.get("recent", 0.5)
        sharpe_score = max(0, min(1, (self.sharpe_ratios.get("recent", 0) + 2) / 4))
        drawdown_score = 1 - abs(self.max_drawdowns.get("recent", 0))

        # Weighted average
        score = 0.3 * win_rate_score + 0.4 * sharpe_score + 0.3 * drawdown_score

        return max(0.1, min(1.0, score))  # Clamp between 0.1 and 1.0


class EnhancedKellyPositionSizer(PositionSizer):
    """Enhanced Kelly Criterion position sizer with ML confidence integration."""

    def __init__(
        self,
        kelly_fraction: float = 0.25,
        max_position_pct: float = 0.1,
        confidence_weight: float = 0.5,
        use_rolling_stats: bool = True,
        lookback_trades: int = 50,
    ):
        """Initialize enhanced Kelly position sizer.

        Args:
            kelly_fraction: Fraction of Kelly to use (0.25 = quarter Kelly).
            max_position_pct: Maximum position size as percentage of equity.
            confidence_weight: Weight for ML confidence in sizing (0-1).
            use_rolling_stats: Use rolling statistics for win rate calculation.
            lookback_trades: Number of trades for rolling statistics.
        """
        self.kelly_fraction = kelly_fraction
        self.max_position_pct = max_position_pct
        self.confidence_weight = confidence_weight
        self.use_rolling_stats = use_rolling_stats
        self.lookback_trades = lookback_trades
        self.trade_results = []

    def calculate_position_size(
        self,
        signal: SignalEvent,
        portfolio: Any,
        current_price: float,
    ) -> float:
        """Calculate position size using enhanced Kelly criterion.

        Args:
            signal: Signal event with ML confidence.
            portfolio: Portfolio instance.
            current_price: Current price of the asset.

        Returns:
            Position size (quantity).
        """
        # Get ML confidence from signal
        ml_confidence = signal.signal_data.get("ml_confidence", 0.5)
        if "metadata" in signal.signal_data:
            ml_confidence = signal.signal_data["metadata"].get(
                "raw_probability", ml_confidence
            )

        # Calculate win rate and average win/loss
        if self.use_rolling_stats and len(self.trade_results) >= 10:
            recent_trades = self.trade_results[-self.lookback_trades :]
            wins = [t for t in recent_trades if t["pnl"] > 0]
            losses = [t for t in recent_trades if t["pnl"] < 0]

            win_rate = len(wins) / len(recent_trades) if recent_trades else 0.5
            avg_win = np.mean([t["pnl"] for t in wins]) if wins else 1.0
            avg_loss = abs(np.mean([t["pnl"] for t in losses])) if losses else 1.0
        else:
            # Use default values or signal-provided estimates
            win_rate = signal.signal_data.get("win_rate", 0.55)
            avg_win = signal.signal_data.get("avg_win", 1.0)
            avg_loss = signal.signal_data.get("avg_loss", 1.0)

        # Adjust win rate based on ML confidence
        confidence_adjusted_win_rate = (
            win_rate * (1 - self.confidence_weight)
            + ml_confidence * self.confidence_weight
        )

        # Calculate Kelly percentage
        if avg_loss > 0:
            win_loss_ratio = avg_win / avg_loss
            kelly_pct = (
                confidence_adjusted_win_rate * win_loss_ratio
                - (1 - confidence_adjusted_win_rate)
            ) / win_loss_ratio
        else:
            kelly_pct = 0

        # Apply Kelly fraction
        kelly_pct = max(0, kelly_pct * self.kelly_fraction)

        # Apply maximum position constraint
        position_pct = min(kelly_pct, self.max_position_pct)

        # Calculate position size
        position_value = portfolio.equity * position_pct
        quantity = position_value / current_price if current_price > 0 else 0

        # Store sizing metadata in signal
        signal.signal_data["position_sizing"] = {
            "method": "enhanced_kelly",
            "ml_confidence": ml_confidence,
            "win_rate": win_rate,
            "adjusted_win_rate": confidence_adjusted_win_rate,
            "kelly_pct": kelly_pct,
            "final_pct": position_pct,
            "position_value": position_value,
        }

        return quantity

    def update_trade_result(self, trade_result: Dict[str, Any]) -> None:
        """Update with trade result for rolling statistics.

        Args:
            trade_result: Dictionary with trade PnL information.
        """
        self.trade_results.append(trade_result)
        if len(self.trade_results) > self.lookback_trades * 2:
            self.trade_results = self.trade_results[-self.lookback_trades * 2 :]


class DynamicPositionSizer(PositionSizer):
    """Dynamic position sizer that adjusts based on performance and market conditions."""

    def __init__(
        self,
        base_sizer: PositionSizer,
        performance_tracker: PerformanceTracker,
        volatility_detector: VolatilityRegimeDetector,
        performance_weight: float = 0.3,
        volatility_weight: float = 0.3,
        drawdown_weight: float = 0.4,
        min_size_multiplier: float = 0.5,
        max_size_multiplier: float = 1.5,
    ):
        """Initialize dynamic position sizer.

        Args:
            base_sizer: Base position sizing algorithm.
            performance_tracker: Performance tracking instance.
            volatility_detector: Volatility regime detector.
            performance_weight: Weight for performance adjustment.
            volatility_weight: Weight for volatility adjustment.
            drawdown_weight: Weight for drawdown adjustment.
            min_size_multiplier: Minimum size multiplier.
            max_size_multiplier: Maximum size multiplier.
        """
        self.base_sizer = base_sizer
        self.performance_tracker = performance_tracker
        self.volatility_detector = volatility_detector
        self.performance_weight = performance_weight
        self.volatility_weight = volatility_weight
        self.drawdown_weight = drawdown_weight
        self.min_size_multiplier = min_size_multiplier
        self.max_size_multiplier = max_size_multiplier

    def calculate_position_size(
        self,
        signal: SignalEvent,
        portfolio: Any,
        current_price: float,
    ) -> float:
        """Calculate dynamically adjusted position size.

        Args:
            signal: Signal event.
            portfolio: Portfolio instance.
            current_price: Current price of the asset.

        Returns:
            Position size (quantity).
        """
        # Get base position size
        base_size = self.base_sizer.calculate_position_size(
            signal, portfolio, current_price
        )

        # Performance adjustment
        performance_score = self.performance_tracker.get_performance_score()
        performance_multiplier = 0.5 + performance_score  # Range: 0.5 to 1.5

        # Volatility adjustment
        symbol = signal.symbol
        current_regime = self.volatility_detector.get_regime(symbol)

        volatility_multipliers = {
            VolatilityRegime.LOW: 1.2,
            VolatilityRegime.NORMAL: 1.0,
            VolatilityRegime.HIGH: 0.7,
            VolatilityRegime.EXTREME: 0.4,
        }
        volatility_multiplier = volatility_multipliers.get(current_regime, 1.0)

        # Drawdown adjustment
        current_drawdown = abs(self.performance_tracker.max_drawdowns.get("recent", 0))
        drawdown_multiplier = 1.0 - (
            current_drawdown * 0.5
        )  # Reduce by up to 50% in drawdown

        # Combine adjustments
        total_multiplier = (
            performance_multiplier * self.performance_weight
            + volatility_multiplier * self.volatility_weight
            + drawdown_multiplier * self.drawdown_weight
        )

        # Apply constraints
        total_multiplier = max(
            self.min_size_multiplier, min(self.max_size_multiplier, total_multiplier)
        )

        # Calculate final size
        adjusted_size = base_size * total_multiplier

        # Store adjustment metadata
        signal.signal_data["position_sizing"]["dynamic_adjustments"] = {
            "performance_score": performance_score,
            "performance_multiplier": performance_multiplier,
            "volatility_regime": current_regime.value,
            "volatility_multiplier": volatility_multiplier,
            "current_drawdown": current_drawdown,
            "drawdown_multiplier": drawdown_multiplier,
            "total_multiplier": total_multiplier,
        }

        return adjusted_size


class ConfidenceWeightedPositionSizer(PositionSizer):
    """Position sizer that scales size based on ML model confidence."""

    def __init__(
        self,
        base_position_pct: float = 0.02,
        min_confidence: float = 0.6,
        max_confidence: float = 0.9,
        confidence_power: float = 2.0,
    ):
        """Initialize confidence-weighted position sizer.

        Args:
            base_position_pct: Base position size as percentage of equity.
            min_confidence: Minimum confidence for position entry.
            max_confidence: Confidence level for maximum position size.
            confidence_power: Power factor for confidence scaling (higher = more aggressive).
        """
        self.base_position_pct = base_position_pct
        self.min_confidence = min_confidence
        self.max_confidence = max_confidence
        self.confidence_power = confidence_power

    def calculate_position_size(
        self,
        signal: SignalEvent,
        portfolio: Any,
        current_price: float,
    ) -> float:
        """Calculate confidence-weighted position size.

        Args:
            signal: Signal event with ML confidence.
            portfolio: Portfolio instance.
            current_price: Current price of the asset.

        Returns:
            Position size (quantity).
        """
        # Get ML confidence
        ml_confidence = signal.strength  # Signal strength represents confidence
        if "metadata" in signal.signal_data:
            ml_confidence = signal.signal_data["metadata"].get(
                "raw_probability", ml_confidence
            )

        # Check minimum confidence
        if ml_confidence < self.min_confidence:
            return 0.0

        # Scale confidence to 0-1 range
        confidence_range = self.max_confidence - self.min_confidence
        scaled_confidence = (ml_confidence - self.min_confidence) / confidence_range
        scaled_confidence = max(0, min(1, scaled_confidence))

        # Apply power scaling
        confidence_multiplier = scaled_confidence**self.confidence_power

        # Calculate position size
        position_pct = self.base_position_pct * confidence_multiplier
        position_value = portfolio.equity * position_pct
        quantity = position_value / current_price if current_price > 0 else 0

        # Store metadata
        signal.signal_data["position_sizing"] = {
            "method": "confidence_weighted",
            "ml_confidence": ml_confidence,
            "scaled_confidence": scaled_confidence,
            "confidence_multiplier": confidence_multiplier,
            "position_pct": position_pct,
            "position_value": position_value,
        }

        return quantity


class RiskParityPositionSizer(PositionSizer):
    """Risk parity position sizer that equalizes risk contribution across positions."""

    def __init__(
        self,
        target_risk: float = 0.01,
        lookback_periods: int = 60,
        use_correlation: bool = True,
        max_position_pct: float = 0.2,
    ):
        """Initialize risk parity position sizer.

        Args:
            target_risk: Target risk per position (as fraction of portfolio).
            lookback_periods: Periods for volatility calculation.
            use_correlation: Whether to consider correlations.
            max_position_pct: Maximum position size as percentage of equity.
        """
        self.target_risk = target_risk
        self.lookback_periods = lookback_periods
        self.use_correlation = use_correlation
        self.max_position_pct = max_position_pct
        self.returns_history = {}
        self.correlation_matrix = None

    def update_returns(self, symbol: str, returns: pd.Series) -> None:
        """Update returns history for a symbol.

        Args:
            symbol: Trading symbol.
            returns: Series of returns.
        """
        self.returns_history[symbol] = returns.tail(self.lookback_periods)

        # Update correlation matrix if using correlations
        if self.use_correlation and len(self.returns_history) > 1:
            returns_df = pd.DataFrame(self.returns_history)
            self.correlation_matrix = returns_df.corr()

    def calculate_position_size(
        self,
        signal: SignalEvent,
        portfolio: Any,
        current_price: float,
    ) -> float:
        """Calculate risk parity position size.

        Args:
            signal: Signal event.
            portfolio: Portfolio instance.
            current_price: Current price of the asset.

        Returns:
            Position size (quantity).
        """
        symbol = signal.symbol

        # Get volatility for the symbol
        if symbol not in self.returns_history or len(self.returns_history[symbol]) < 20:
            # Use default sizing if insufficient data
            default_pct = self.target_risk
            position_value = portfolio.equity * default_pct
            return position_value / current_price if current_price > 0 else 0

        # Calculate volatility
        returns = self.returns_history[symbol]
        volatility = returns.std() * np.sqrt(252)  # Annualized

        # Calculate position size for target risk
        if volatility > 0:
            position_pct = self.target_risk / volatility
        else:
            position_pct = self.target_risk

        # Adjust for correlations if available
        if self.use_correlation and self.correlation_matrix is not None:
            # Get current positions
            current_positions = portfolio.positions
            if current_positions:
                # Calculate marginal risk contribution
                position_symbols = list(current_positions.keys())
                if symbol in self.correlation_matrix.columns:
                    correlations = self.correlation_matrix.loc[
                        symbol, position_symbols
                    ].values
                    position_weights = np.array(
                        [
                            pos["value"] / portfolio.equity
                            for pos in current_positions.values()
                        ]
                    )

                    # Adjust for correlation impact
                    correlation_adjustment = (
                        1 + np.sum(correlations * position_weights) * 0.5
                    )
                    position_pct = position_pct / correlation_adjustment

        # Apply maximum position constraint
        position_pct = min(position_pct, self.max_position_pct)

        # Calculate final position size
        position_value = portfolio.equity * position_pct
        quantity = position_value / current_price if current_price > 0 else 0

        # Store metadata
        signal.signal_data["position_sizing"] = {
            "method": "risk_parity",
            "volatility": volatility,
            "target_risk": self.target_risk,
            "position_pct": position_pct,
            "position_value": position_value,
        }

        return quantity
