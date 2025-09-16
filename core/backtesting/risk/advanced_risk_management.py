"""Advanced risk management system for FXML4."""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


class RiskLevel(Enum):
    """Risk levels for position sizing."""

    VERY_LOW = 0.005  # 0.5% risk
    LOW = 0.01  # 1% risk
    NORMAL = 0.02  # 2% risk
    HIGH = 0.03  # 3% risk
    VERY_HIGH = 0.05  # 5% risk


@dataclass
class RiskMetrics:
    """Container for risk metrics."""

    current_drawdown: float
    max_drawdown: float
    var_95: float  # Value at Risk 95%
    cvar_95: float  # Conditional VaR 95%
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    correlation_risk: float
    concentration_risk: float


class AdvancedRiskManager:
    """Advanced risk management with dynamic position sizing."""

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}

        # Risk parameters
        self.max_drawdown_limit = self.config.get("max_drawdown_limit", 0.20)  # 20%
        self.daily_loss_limit = self.config.get("daily_loss_limit", 0.05)  # 5%
        self.position_limit = self.config.get(
            "position_limit", 0.10
        )  # 10% per position
        self.correlation_limit = self.config.get(
            "correlation_limit", 0.7
        )  # 70% correlation

        # Dynamic adjustment parameters
        self.use_volatility_scaling = self.config.get("use_volatility_scaling", True)
        self.use_drawdown_scaling = self.config.get("use_drawdown_scaling", True)
        self.use_kelly_criterion = self.config.get("use_kelly_criterion", True)

        # Performance tracking
        self.equity_curve = []
        self.trade_history = []
        self.daily_returns = []

    def calculate_position_size(
        self,
        signal_strength: float,
        market_data: pd.DataFrame,
        current_portfolio: Dict,
        symbol: str,
    ) -> float:
        """Calculate optimal position size based on multiple factors."""

        # 1. Base position size from risk level
        base_size = self._get_base_position_size(signal_strength)

        # 2. Volatility adjustment
        if self.use_volatility_scaling:
            vol_scalar = self._calculate_volatility_scalar(market_data)
            base_size *= vol_scalar

        # 3. Drawdown adjustment
        if self.use_drawdown_scaling:
            dd_scalar = self._calculate_drawdown_scalar()
            base_size *= dd_scalar

        # 4. Kelly Criterion
        if self.use_kelly_criterion:
            kelly_size = self._calculate_kelly_size(symbol)
            base_size = min(base_size, kelly_size)

        # 5. Correlation adjustment
        corr_scalar = self._calculate_correlation_scalar(symbol, current_portfolio)
        base_size *= corr_scalar

        # 6. Apply limits
        base_size = self._apply_position_limits(base_size, current_portfolio)

        return base_size

    def _get_base_position_size(self, signal_strength: float) -> float:
        """Get base position size based on signal strength."""
        if abs(signal_strength) < 0.3:
            return RiskLevel.VERY_LOW.value
        elif abs(signal_strength) < 0.5:
            return RiskLevel.LOW.value
        elif abs(signal_strength) < 0.7:
            return RiskLevel.NORMAL.value
        elif abs(signal_strength) < 0.9:
            return RiskLevel.HIGH.value
        else:
            return RiskLevel.VERY_HIGH.value

    def _calculate_volatility_scalar(self, market_data: pd.DataFrame) -> float:
        """Scale position size based on market volatility."""
        if "atr_14" not in market_data.columns:
            return 1.0

        # Current vs average volatility
        current_vol = market_data["atr_14"].iloc[-1]
        avg_vol = market_data["atr_14"].rolling(50).mean().iloc[-1]

        if pd.isna(avg_vol) or avg_vol == 0:
            return 1.0

        vol_ratio = current_vol / avg_vol

        # Inverse volatility scaling (higher vol = smaller position)
        scalar = 1.0 / np.sqrt(vol_ratio)

        # Cap the adjustment
        return np.clip(scalar, 0.5, 1.5)

    def _calculate_drawdown_scalar(self) -> float:
        """Scale position size based on current drawdown."""
        if not self.equity_curve:
            return 1.0

        # Calculate current drawdown
        equity_array = np.array(self.equity_curve)
        peak = np.maximum.accumulate(equity_array)
        dd = (peak - equity_array) / peak
        current_dd = dd[-1]

        # Progressive reduction as drawdown increases
        if current_dd < 0.05:  # Less than 5%
            return 1.0
        elif current_dd < 0.10:  # 5-10%
            return 0.75
        elif current_dd < 0.15:  # 10-15%
            return 0.5
        else:  # Greater than 15%
            return 0.25

    def _calculate_kelly_size(self, symbol: str) -> float:
        """Calculate position size using Kelly Criterion."""
        if len(self.trade_history) < 20:
            return RiskLevel.NORMAL.value  # Default until enough history

        # Get trades for this symbol
        symbol_trades = [t for t in self.trade_history if t["symbol"] == symbol]

        if len(symbol_trades) < 10:
            return RiskLevel.NORMAL.value

        # Calculate win rate and win/loss ratio
        wins = [t["return"] for t in symbol_trades if t["return"] > 0]
        losses = [abs(t["return"]) for t in symbol_trades if t["return"] < 0]

        if not wins or not losses:
            return RiskLevel.LOW.value

        win_rate = len(wins) / len(symbol_trades)
        avg_win = np.mean(wins)
        avg_loss = np.mean(losses)

        if avg_loss == 0:
            return RiskLevel.LOW.value

        # Kelly formula: f = (p * b - q) / b
        # where p = win rate, q = loss rate, b = win/loss ratio
        b = avg_win / avg_loss
        q = 1 - win_rate

        kelly_fraction = (win_rate * b - q) / b

        # Apply Kelly with safety factor (25% of full Kelly)
        safe_kelly = kelly_fraction * 0.25

        # Convert to position size
        position_size = max(0, min(safe_kelly, 0.25))  # Cap at 25%

        return position_size

    def _calculate_correlation_scalar(
        self, symbol: str, current_portfolio: Dict
    ) -> float:
        """Reduce position size for correlated positions."""
        if not current_portfolio:
            return 1.0

        # Simplified correlation groups
        correlation_groups = {
            "USD_LONG": ["EURUSD_SHORT", "GBPUSD_SHORT", "USDCHF_LONG", "USDJPY_LONG"],
            "USD_SHORT": ["EURUSD_LONG", "GBPUSD_LONG", "USDCHF_SHORT", "USDJPY_SHORT"],
            "EUR_LONG": ["EURUSD_LONG", "EURGBP_LONG", "EURJPY_LONG"],
            "EUR_SHORT": ["EURUSD_SHORT", "EURGBP_SHORT", "EURJPY_SHORT"],
        }

        # Count correlated positions
        correlated_exposure = 0
        for group, symbols in correlation_groups.items():
            if symbol in symbols:
                for other_symbol in symbols:
                    if other_symbol != symbol and other_symbol in current_portfolio:
                        correlated_exposure += abs(current_portfolio[other_symbol])

        # Reduce size based on correlation
        if correlated_exposure > 0.1:  # More than 10% in correlated positions
            return 0.5
        elif correlated_exposure > 0.05:  # More than 5%
            return 0.75
        else:
            return 1.0

    def _apply_position_limits(
        self, position_size: float, current_portfolio: Dict
    ) -> float:
        """Apply position and portfolio limits."""
        # Single position limit
        position_size = min(position_size, self.position_limit)

        # Total exposure limit
        total_exposure = sum(abs(pos) for pos in current_portfolio.values())
        if total_exposure + position_size > 1.0:  # 100% exposure limit
            position_size = max(0, 1.0 - total_exposure)

        # Daily loss limit check
        if self._check_daily_loss_limit():
            position_size = 0  # Stop trading for the day

        return position_size

    def _check_daily_loss_limit(self) -> bool:
        """Check if daily loss limit has been hit."""
        if not self.daily_returns:
            return False

        today_return = self.daily_returns[-1] if self.daily_returns else 0
        return today_return < -self.daily_loss_limit

    def calculate_stop_loss(
        self,
        entry_price: float,
        position_size: float,
        market_data: pd.DataFrame,
        signal_type: int,
    ) -> float:
        """Calculate dynamic stop loss level."""

        # 1. ATR-based stop
        if "atr_14" in market_data.columns:
            atr = market_data["atr_14"].iloc[-1]
            atr_multiplier = 2.0 if position_size < 0.02 else 1.5
            atr_stop = atr * atr_multiplier
        else:
            atr_stop = entry_price * 0.02  # 2% default

        # 2. Support/Resistance based stop
        if signal_type == 1:  # Long position
            if "support_level" in market_data.columns:
                support = market_data["support_level"].iloc[-1]
                sr_stop = entry_price - support
            else:
                sr_stop = entry_price * 0.015
        else:  # Short position
            if "resistance_level" in market_data.columns:
                resistance = market_data["resistance_level"].iloc[-1]
                sr_stop = resistance - entry_price
            else:
                sr_stop = entry_price * 0.015

        # 3. Volatility-adjusted stop
        if "volatility_20" in market_data.columns:
            vol = market_data["volatility_20"].iloc[-1]
            vol_stop = entry_price * vol * 2
        else:
            vol_stop = entry_price * 0.02

        # Use the most conservative stop
        stop_distance = min(atr_stop, sr_stop, vol_stop)

        # Calculate stop price
        if signal_type == 1:  # Long
            stop_price = entry_price - stop_distance
        else:  # Short
            stop_price = entry_price + stop_distance

        return stop_price

    def calculate_take_profit(
        self,
        entry_price: float,
        stop_loss: float,
        market_data: pd.DataFrame,
        signal_type: int,
    ) -> List[float]:
        """Calculate multiple take profit levels."""

        # Risk amount
        risk = abs(entry_price - stop_loss)

        # Multiple TP levels with different risk/reward ratios
        tp_levels = []

        # TP1: 1:1 risk/reward
        if signal_type == 1:  # Long
            tp1 = entry_price + risk
        else:  # Short
            tp1 = entry_price - risk
        tp_levels.append(tp1)

        # TP2: 2:1 risk/reward
        if signal_type == 1:
            tp2 = entry_price + (risk * 2)
        else:
            tp2 = entry_price - (risk * 2)
        tp_levels.append(tp2)

        # TP3: Based on resistance/support
        if signal_type == 1 and "resistance_level" in market_data.columns:
            resistance = market_data["resistance_level"].iloc[-1]
            if resistance > entry_price:
                tp_levels.append(resistance * 0.995)  # Just below resistance
        elif signal_type == -1 and "support_level" in market_data.columns:
            support = market_data["support_level"].iloc[-1]
            if support < entry_price:
                tp_levels.append(support * 1.005)  # Just above support

        return tp_levels

    def update_performance(self, trade_result: Dict):
        """Update performance metrics with new trade."""
        self.trade_history.append(trade_result)

        # Update equity curve
        if self.equity_curve:
            new_equity = self.equity_curve[-1] * (1 + trade_result["return"])
        else:
            new_equity = 1.0 * (1 + trade_result["return"])

        self.equity_curve.append(new_equity)

        # Update daily returns
        # This would need proper date handling in production
        self.daily_returns.append(trade_result["return"])

    def get_risk_metrics(self) -> RiskMetrics:
        """Calculate current risk metrics."""
        if len(self.equity_curve) < 2:
            return RiskMetrics(0, 0, 0, 0, 0, 0, 0, 0, 0)

        equity_array = np.array(self.equity_curve)
        returns = np.diff(equity_array) / equity_array[:-1]

        # Drawdown
        peak = np.maximum.accumulate(equity_array)
        dd = (peak - equity_array) / peak
        current_dd = dd[-1]
        max_dd = np.max(dd)

        # VaR and CVaR
        var_95 = np.percentile(returns, 5)
        cvar_95 = np.mean(returns[returns <= var_95])

        # Sharpe Ratio
        if len(returns) > 0 and np.std(returns) > 0:
            sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252)
        else:
            sharpe = 0

        # Sortino Ratio
        downside_returns = returns[returns < 0]
        if len(downside_returns) > 0 and np.std(downside_returns) > 0:
            sortino = np.mean(returns) / np.std(downside_returns) * np.sqrt(252)
        else:
            sortino = 0

        # Calmar Ratio
        if max_dd > 0:
            annual_return = (equity_array[-1] / equity_array[0]) ** (
                252 / len(returns)
            ) - 1
            calmar = annual_return / max_dd
        else:
            calmar = 0

        # Simplified correlation and concentration risk
        correlation_risk = 0.0  # Would need portfolio data
        concentration_risk = 0.0  # Would need position data

        return RiskMetrics(
            current_drawdown=current_dd,
            max_drawdown=max_dd,
            var_95=var_95,
            cvar_95=cvar_95,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            calmar_ratio=calmar,
            correlation_risk=correlation_risk,
            concentration_risk=concentration_risk,
        )
