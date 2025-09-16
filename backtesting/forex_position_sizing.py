"""Forex-specific position sizing with leverage and minimum trade requirements."""

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd


@dataclass
class ForexPositionConfig:
    """Configuration for forex position sizing."""

    leverage: float = 40.0  # 40:1 leverage
    min_trade_size_usd: float = 25000  # $25k minimum notional
    max_position_pct: float = 0.10  # Max 10% of account per position
    max_total_exposure: float = 0.50  # Max 50% total exposure
    pip_value_multiplier: float = 10000  # For standard pip calculations

    # Risk parameters
    risk_per_trade: float = 0.02  # 2% risk per trade
    max_daily_loss: float = 0.06  # 6% max daily loss


class ForexPositionSizer:
    """Position sizing for forex trading with proper leverage and minimums."""

    def __init__(self, config: Optional[ForexPositionConfig] = None):
        self.config = config or ForexPositionConfig()
        self.current_positions = {}
        self.daily_pnl = 0.0

    def calculate_position_size(
        self,
        account_balance: float,
        symbol: str,
        entry_price: float,
        stop_loss_price: float,
        signal_strength: float = 1.0,
    ) -> Dict[str, float]:
        """Calculate position size for forex trade."""

        # 1. Calculate base position from risk
        risk_amount = account_balance * self.config.risk_per_trade * signal_strength

        # 2. Calculate pip risk
        pip_risk = self._calculate_pip_risk(symbol, entry_price, stop_loss_price)

        # 3. Calculate units from risk
        if pip_risk > 0:
            # Standard lot size calculation
            pip_value = self._get_pip_value(symbol, entry_price)
            units_from_risk = risk_amount / (pip_risk * pip_value)
        else:
            return {"units": 0, "notional_usd": 0, "margin_required": 0}

        # 4. Calculate notional value
        notional_usd = units_from_risk * entry_price

        # 5. Apply minimum trade size
        if notional_usd < self.config.min_trade_size_usd:
            # Scale up to minimum
            scale_factor = self.config.min_trade_size_usd / notional_usd
            units_from_risk *= scale_factor
            notional_usd = self.config.min_trade_size_usd

            # Check if we can afford the minimum
            margin_required = notional_usd / self.config.leverage
            if margin_required > account_balance * self.config.max_position_pct:
                return {"units": 0, "notional_usd": 0, "margin_required": 0}

        # 6. Apply maximum position limits
        max_notional = (
            account_balance * self.config.max_position_pct * self.config.leverage
        )
        if notional_usd > max_notional:
            units_from_risk *= max_notional / notional_usd
            notional_usd = max_notional

        # 7. Check total exposure
        current_exposure = self._calculate_total_exposure()
        margin_required = notional_usd / self.config.leverage

        if (current_exposure + margin_required) > (
            account_balance * self.config.max_total_exposure
        ):
            # Reduce position to fit within exposure limit
            available_margin = (
                account_balance * self.config.max_total_exposure - current_exposure
            )
            if available_margin <= 0:
                return {"units": 0, "notional_usd": 0, "margin_required": 0}

            scale_factor = available_margin / margin_required
            units_from_risk *= scale_factor
            notional_usd *= scale_factor
            margin_required = available_margin

        # 8. Round to standard lot sizes
        units_final = self._round_to_lot_size(units_from_risk, symbol)

        # Recalculate final values
        notional_final = units_final * entry_price
        margin_final = notional_final / self.config.leverage

        # Final check against minimum
        if notional_final < self.config.min_trade_size_usd:
            return {"units": 0, "notional_usd": 0, "margin_required": 0}

        return {
            "units": units_final,
            "notional_usd": notional_final,
            "margin_required": margin_final,
            "pip_risk": pip_risk,
            "risk_amount": risk_amount,
            "leverage_used": self.config.leverage,
        }

    def calculate_scaled_position(
        self,
        initial_balance: float,
        current_balance: float,
        base_position: Dict[str, float],
    ) -> Dict[str, float]:
        """Scale position size based on account growth."""

        # Calculate growth factor
        growth_factor = current_balance / initial_balance

        # Apply scaling with safety limits
        scale_factor = min(growth_factor, 3.0)  # Cap at 3x initial size
        scale_factor = max(scale_factor, 0.5)  # Floor at 0.5x initial size

        # Scale the position
        scaled_position = base_position.copy()
        scaled_position["units"] *= scale_factor
        scaled_position["notional_usd"] *= scale_factor
        scaled_position["margin_required"] *= scale_factor

        # Ensure minimum is still met
        if scaled_position["notional_usd"] < self.config.min_trade_size_usd:
            # Jump to minimum
            min_scale = self.config.min_trade_size_usd / base_position["notional_usd"]
            scaled_position["units"] = base_position["units"] * min_scale
            scaled_position["notional_usd"] = self.config.min_trade_size_usd
            scaled_position["margin_required"] = (
                self.config.min_trade_size_usd / self.config.leverage
            )

        return scaled_position

    def _calculate_pip_risk(self, symbol: str, entry: float, stop: float) -> float:
        """Calculate risk in pips."""
        if "JPY" in symbol:
            # JPY pairs have different pip calculation
            pip_size = 0.01
        else:
            pip_size = 0.0001

        price_diff = abs(entry - stop)
        pips = price_diff / pip_size

        return pips

    def _get_pip_value(self, symbol: str, price: float) -> float:
        """Get pip value for the symbol."""
        # Simplified pip value calculation
        # In reality, this would depend on the account currency

        if symbol.endswith("USD"):
            # USD is quote currency
            pip_value = 10.0  # $10 per pip per standard lot
        elif symbol.startswith("USD"):
            # USD is base currency
            pip_value = 10.0 / price
        else:
            # Cross pairs - would need more complex calculation
            pip_value = 10.0

        return pip_value

    def _round_to_lot_size(self, units: float, symbol: str) -> float:
        """Round to standard forex lot sizes."""
        # Standard lot = 100,000 units
        # Mini lot = 10,000 units
        # Micro lot = 1,000 units

        if units >= 100000:
            # Round to nearest standard lot
            return round(units / 100000) * 100000
        elif units >= 10000:
            # Round to nearest mini lot
            return round(units / 10000) * 10000
        elif units >= 1000:
            # Round to nearest micro lot
            return round(units / 1000) * 1000
        else:
            return 0  # Too small

    def _calculate_total_exposure(self) -> float:
        """Calculate total margin used by current positions."""
        total_margin = 0
        for position in self.current_positions.values():
            total_margin += position.get("margin_required", 0)
        return total_margin

    def update_position(self, symbol: str, position_data: Dict):
        """Update current position tracking."""
        if position_data["units"] == 0:
            # Position closed
            if symbol in self.current_positions:
                del self.current_positions[symbol]
        else:
            self.current_positions[symbol] = position_data

    def check_daily_loss_limit(self, account_balance: float) -> bool:
        """Check if daily loss limit has been exceeded."""
        daily_loss_pct = abs(self.daily_pnl) / account_balance
        return daily_loss_pct >= self.config.max_daily_loss

    def update_daily_pnl(self, pnl: float):
        """Update daily P&L tracking."""
        self.daily_pnl += pnl

    def reset_daily_tracking(self):
        """Reset daily tracking (call at start of new trading day)."""
        self.daily_pnl = 0.0


def calculate_forex_position_example():
    """Example of forex position calculation."""

    # Initialize position sizer
    sizer = ForexPositionSizer()

    # Account details
    account_balance = 100000  # $100k account

    # Trade setup
    symbol = "EURUSD"
    entry_price = 1.0850
    stop_loss = 1.0820  # 30 pips risk

    # Calculate position
    position = sizer.calculate_position_size(
        account_balance=account_balance,
        symbol=symbol,
        entry_price=entry_price,
        stop_loss_price=stop_loss,
        signal_strength=1.0,
    )

    print(f"Forex Position Calculation Example")
    print(f"{'='*50}")
    print(f"Account Balance: ${account_balance:,.2f}")
    print(f"Symbol: {symbol}")
    print(f"Entry Price: {entry_price}")
    print(f"Stop Loss: {stop_loss}")
    print(f"Risk: {position['pip_risk']:.1f} pips")
    print(f"\nPosition Details:")
    print(f"Units: {position['units']:,.0f}")
    print(f"Notional Value: ${position['notional_usd']:,.2f}")
    print(f"Margin Required: ${position['margin_required']:,.2f}")
    print(f"Leverage Used: {position['leverage_used']}:1")
    print(f"Risk Amount: ${position['risk_amount']:,.2f}")

    # Example with account growth
    print(f"\n{'='*50}")
    print(f"Position Scaling with Account Growth:")

    grown_balance = 150000  # Account grew to $150k
    scaled_position = sizer.calculate_scaled_position(
        initial_balance=account_balance,
        current_balance=grown_balance,
        base_position=position,
    )

    print(f"Grown Balance: ${grown_balance:,.2f}")
    print(f"Growth Factor: {grown_balance/account_balance:.2f}x")
    print(f"Scaled Units: {scaled_position['units']:,.0f}")
    print(f"Scaled Notional: ${scaled_position['notional_usd']:,.2f}")
    print(f"Scaled Margin: ${scaled_position['margin_required']:,.2f}")


if __name__ == "__main__":
    calculate_forex_position_example()
