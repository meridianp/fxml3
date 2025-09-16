#!/usr/bin/env python
"""Dynamic risk management system for forex trading with environment-based configuration."""

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


@dataclass
class RiskParameters:
    """Risk management parameters from environment."""

    min_position_size: float
    account_leverage: float
    max_risk_per_trade: float
    max_positions: int
    max_correlation_exposure: float

    @classmethod
    def from_env(cls):
        """Load parameters from environment variables."""
        return cls(
            min_position_size=float(os.getenv("FOREX_MIN_POSITION_SIZE", 25000)),
            account_leverage=float(os.getenv("FOREX_ACCOUNT_LEVERAGE", 40)),
            max_risk_per_trade=float(os.getenv("FOREX_MAX_RISK_PER_TRADE", 0.02)),
            max_positions=int(os.getenv("FOREX_MAX_POSITIONS", 4)),
            max_correlation_exposure=float(
                os.getenv("FOREX_MAX_CORRELATION_EXPOSURE", 0.6)
            ),
        )


@dataclass
class PositionSize:
    """Position sizing result."""

    units: float
    notional_value: float
    margin_required: float
    risk_amount: float
    position_score: float
    scaling_factor: float


class DynamicRiskManager:
    """Dynamic risk management with environment-based configuration."""

    def __init__(self):
        self.params = RiskParameters.from_env()
        self.positions = {}
        self.daily_pnl = 0
        self.correlation_matrix = None
        self.market_regime = "NEUTRAL"

        print("Dynamic Risk Manager initialized with:")
        print(f"  Min Position Size: ${self.params.min_position_size:,.0f}")
        print(f"  Account Leverage: {self.params.account_leverage:.0f}:1")
        print(f"  Max Risk per Trade: {self.params.max_risk_per_trade:.1%}")
        print(f"  Max Positions: {self.params.max_positions}")
        print(f"  Max Correlation Exposure: {self.params.max_correlation_exposure:.1%}")

    def calculate_position_size(
        self,
        account_balance: float,
        symbol: str,
        entry_price: float,
        stop_loss_price: float,
        signal_strength: float,
        volatility: Optional[float] = None,
    ) -> PositionSize:
        """Calculate position size with dynamic adjustments."""

        # Base risk amount
        risk_amount = account_balance * self.params.max_risk_per_trade

        # Adjust for signal strength
        risk_amount *= signal_strength

        # Adjust for market regime
        regime_multiplier = self._get_regime_multiplier()
        risk_amount *= regime_multiplier

        # Adjust for correlation exposure
        correlation_multiplier = self._get_correlation_multiplier(symbol)
        risk_amount *= correlation_multiplier

        # Adjust for volatility
        if volatility:
            vol_multiplier = self._get_volatility_multiplier(volatility)
            risk_amount *= vol_multiplier

        # Calculate position units based on stop loss
        price_risk = abs(entry_price - stop_loss_price)
        if price_risk > 0:
            units = risk_amount / price_risk
        else:
            units = 0

        # Calculate notional value
        notional_value = units * entry_price

        # Apply minimum position size
        if notional_value < self.params.min_position_size:
            # Scale up to minimum if we have enough margin
            scale_factor = self.params.min_position_size / notional_value
            available_margin = account_balance * self.params.account_leverage
            required_margin = (
                self.params.min_position_size / self.params.account_leverage
            )

            if (
                required_margin <= available_margin * 0.5
            ):  # Use max 50% of available margin
                units *= scale_factor
                notional_value = self.params.min_position_size
                risk_amount *= scale_factor
            else:
                # Can't meet minimum size
                return PositionSize(
                    units=0,
                    notional_value=0,
                    margin_required=0,
                    risk_amount=0,
                    position_score=0,
                    scaling_factor=0,
                )

        # Check leverage constraint
        margin_required = notional_value / self.params.account_leverage
        total_margin_used = self._get_total_margin_used() + margin_required

        if total_margin_used > account_balance:
            # Scale down to fit within margin
            scale_factor = (
                account_balance - self._get_total_margin_used()
            ) / margin_required
            scale_factor = max(0, min(1, scale_factor))

            units *= scale_factor
            notional_value *= scale_factor
            margin_required *= scale_factor
            risk_amount *= scale_factor

        # Calculate position score for ranking
        position_score = signal_strength * regime_multiplier * correlation_multiplier

        # Calculate final scaling factor
        scaling_factor = notional_value / (units * entry_price) if units > 0 else 0

        return PositionSize(
            units=units,
            notional_value=notional_value,
            margin_required=margin_required,
            risk_amount=risk_amount,
            position_score=position_score,
            scaling_factor=scaling_factor,
        )

    def update_correlation_matrix(self, correlation_matrix: pd.DataFrame):
        """Update correlation matrix for position sizing."""
        self.correlation_matrix = correlation_matrix

    def update_market_regime(self, regime: str):
        """Update market regime for dynamic adjustments."""
        self.market_regime = regime

    def add_position(self, symbol: str, position: dict):
        """Add a position to track."""
        self.positions[symbol] = position

    def remove_position(self, symbol: str):
        """Remove a position."""
        if symbol in self.positions:
            del self.positions[symbol]

    def update_daily_pnl(self, pnl: float):
        """Update daily P&L for loss limits."""
        self.daily_pnl += pnl

    def check_daily_loss_limit(self, account_balance: float) -> bool:
        """Check if daily loss limit is reached."""
        daily_loss_limit = (
            account_balance * self.params.max_risk_per_trade * 3
        )  # 3x single trade risk
        return self.daily_pnl < -daily_loss_limit

    def can_open_position(self) -> bool:
        """Check if we can open a new position."""
        return len(self.positions) < self.params.max_positions

    def get_position_weights(self) -> Dict[str, float]:
        """Get current position weights."""
        total_notional = sum(
            pos.get("notional_value", 0) for pos in self.positions.values()
        )

        if total_notional == 0:
            return {}

        return {
            symbol: pos.get("notional_value", 0) / total_notional
            for symbol, pos in self.positions.items()
        }

    def _get_regime_multiplier(self) -> float:
        """Get position size multiplier based on market regime."""
        regime_multipliers = {
            "RISK_OFF": 0.5,
            "RISK_ON": 1.2,
            "NEUTRAL": 1.0,
            "HIGH_VOLATILITY": 0.3,
            "LOW_VOLATILITY": 1.5,
            "TRENDING": 1.3,
            "RANGING": 0.8,
        }

        # Check for compound regimes
        if "RISK_OFF" in self.market_regime:
            return 0.5
        elif "RISK_ON" in self.market_regime:
            return 1.2

        return regime_multipliers.get(self.market_regime, 1.0)

    def _get_correlation_multiplier(self, symbol: str) -> float:
        """Get position size multiplier based on correlation with existing positions."""
        if not self.positions or self.correlation_matrix is None:
            return 1.0

        # Calculate average correlation with existing positions
        correlations = []
        for existing_symbol in self.positions:
            if symbol != existing_symbol:
                try:
                    if (
                        symbol in self.correlation_matrix.index
                        and existing_symbol in self.correlation_matrix.columns
                    ):
                        corr = self.correlation_matrix.loc[symbol, existing_symbol]
                        correlations.append(abs(corr))
                except:
                    pass

        if not correlations:
            return 1.0

        avg_correlation = np.mean(correlations)

        # Reduce position size for highly correlated positions
        if avg_correlation > self.params.max_correlation_exposure:
            return 0.5
        elif avg_correlation > 0.7:
            return 0.7
        elif avg_correlation > 0.5:
            return 0.85

        return 1.0

    def _get_volatility_multiplier(self, volatility: float) -> float:
        """Get position size multiplier based on volatility."""
        # Assume volatility is annualized percentage
        if volatility > 30:  # High volatility
            return 0.5
        elif volatility > 20:
            return 0.7
        elif volatility > 15:
            return 0.9
        elif volatility < 10:  # Low volatility
            return 1.2

        return 1.0

    def _get_total_margin_used(self) -> float:
        """Get total margin used by existing positions."""
        return sum(pos.get("margin_required", 0) for pos in self.positions.values())

    def get_risk_metrics(self) -> dict:
        """Get current risk metrics."""
        total_margin = self._get_total_margin_used()
        position_count = len(self.positions)

        # Calculate correlation risk
        correlation_risk = 0
        if self.correlation_matrix is not None and len(self.positions) > 1:
            symbols = list(self.positions.keys())
            for i, sym1 in enumerate(symbols):
                for j, sym2 in enumerate(symbols[i + 1 :], i + 1):
                    try:
                        if (
                            sym1 in self.correlation_matrix.index
                            and sym2 in self.correlation_matrix.columns
                        ):
                            corr = self.correlation_matrix.loc[sym1, sym2]
                            correlation_risk += abs(corr)
                    except:
                        pass

        return {
            "total_margin_used": total_margin,
            "position_count": position_count,
            "positions_remaining": self.params.max_positions - position_count,
            "daily_pnl": self.daily_pnl,
            "correlation_risk": correlation_risk,
            "market_regime": self.market_regime,
            "regime_multiplier": self._get_regime_multiplier(),
        }

    def suggest_position_adjustments(self, account_balance: float) -> List[dict]:
        """Suggest position adjustments based on risk metrics."""
        suggestions = []

        # Check if overleveraged
        total_margin = self._get_total_margin_used()
        if total_margin > account_balance * 0.8:
            suggestions.append(
                {
                    "type": "reduce_leverage",
                    "message": "Total margin usage exceeds 80% of account balance",
                    "action": "Consider closing or reducing positions",
                }
            )

        # Check correlation risk
        if len(self.positions) > 1:
            high_corr_pairs = []
            symbols = list(self.positions.keys())

            for i, sym1 in enumerate(symbols):
                for j, sym2 in enumerate(symbols[i + 1 :], i + 1):
                    if self.correlation_matrix is not None:
                        try:
                            if (
                                sym1 in self.correlation_matrix.index
                                and sym2 in self.correlation_matrix.columns
                            ):
                                corr = self.correlation_matrix.loc[sym1, sym2]
                                if abs(corr) > self.params.max_correlation_exposure:
                                    high_corr_pairs.append((sym1, sym2, corr))
                        except:
                            pass

            if high_corr_pairs:
                suggestions.append(
                    {
                        "type": "high_correlation",
                        "message": f"High correlation between positions: {high_corr_pairs}",
                        "action": "Consider reducing correlated exposure",
                    }
                )

        # Check daily loss
        if self.daily_pnl < -account_balance * self.params.max_risk_per_trade * 2:
            suggestions.append(
                {
                    "type": "daily_loss_warning",
                    "message": f"Daily loss ({self.daily_pnl:.2f}) approaching limit",
                    "action": "Consider reducing risk or stopping trading for the day",
                }
            )

        return suggestions


def example_usage():
    """Example of using the dynamic risk manager."""
    # Initialize risk manager
    risk_manager = DynamicRiskManager()

    # Example account and market data
    account_balance = 100000

    # Example correlation matrix
    symbols = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF"]
    corr_data = np.array(
        [
            [1.00, 0.85, -0.70, -0.90],  # EURUSD
            [0.85, 1.00, -0.60, -0.75],  # GBPUSD
            [-0.70, -0.60, 1.00, 0.80],  # USDJPY
            [-0.90, -0.75, 0.80, 1.00],  # USDCHF
        ]
    )
    corr_matrix = pd.DataFrame(corr_data, index=symbols, columns=symbols)
    risk_manager.update_correlation_matrix(corr_matrix)

    # Set market regime
    risk_manager.update_market_regime("RISK_ON")

    # Calculate position size for EURUSD
    position = risk_manager.calculate_position_size(
        account_balance=account_balance,
        symbol="EURUSD",
        entry_price=1.0850,
        stop_loss_price=1.0800,  # 50 pip stop
        signal_strength=0.8,
        volatility=12.5,  # 12.5% annualized volatility
    )

    print(f"\nPosition Sizing for EURUSD:")
    print(f"  Units: {position.units:,.0f}")
    print(f"  Notional Value: ${position.notional_value:,.2f}")
    print(f"  Margin Required: ${position.margin_required:,.2f}")
    print(f"  Risk Amount: ${position.risk_amount:,.2f}")
    print(f"  Position Score: {position.position_score:.2f}")

    # Add position
    risk_manager.add_position(
        "EURUSD",
        {
            "units": position.units,
            "notional_value": position.notional_value,
            "margin_required": position.margin_required,
        },
    )

    # Calculate position for correlated pair
    position2 = risk_manager.calculate_position_size(
        account_balance=account_balance,
        symbol="GBPUSD",
        entry_price=1.2700,
        stop_loss_price=1.2650,
        signal_strength=0.7,
        volatility=15.0,
    )

    print(f"\nPosition Sizing for GBPUSD (with correlation adjustment):")
    print(f"  Units: {position2.units:,.0f}")
    print(f"  Notional Value: ${position2.notional_value:,.2f}")
    print(f"  Note: Reduced due to high correlation with EURUSD")

    # Get risk metrics
    metrics = risk_manager.get_risk_metrics()
    print(f"\nRisk Metrics:")
    for key, value in metrics.items():
        print(f"  {key}: {value}")

    # Get suggestions
    suggestions = risk_manager.suggest_position_adjustments(account_balance)
    if suggestions:
        print(f"\nRisk Management Suggestions:")
        for suggestion in suggestions:
            print(f"  - {suggestion['message']}")
            print(f"    Action: {suggestion['action']}")


if __name__ == "__main__":
    example_usage()
