"""
Position Sizing Calculator - TDD Implementation (GREEN Phase)
Minimal implementation to make tests pass
"""

import math
from typing import Any, Dict, List, Optional


class PositionSizingCalculator:
    """
    Calculate optimal position sizes based on risk management rules.
    GREEN phase: Minimal implementation to pass tests.
    """

    def __init__(
        self,
        account_balance: float = 10000,
        starting_balance: float = None,
        current_balance: float = None,
        risk_percentage: float = 2.0,
        available_margin: float = None,
        leverage: int = 50,
        max_position_size: float = None,
        sizing_method: str = "fixed_risk",
        sizing_strategy: str = None,
        target_portfolio_risk: float = None,
        use_volatility_sizing: bool = False,
        pyramiding_enabled: bool = False,
        news_adjustment: bool = False,
        delta: float = None,
    ):
        """Initialize position sizing calculator."""
        self.account_balance = account_balance
        self.starting_balance = starting_balance or account_balance
        self.current_balance = current_balance or account_balance
        self.risk_percentage = risk_percentage
        self.available_margin = available_margin
        self.leverage = leverage
        self.max_position_size = max_position_size
        self.sizing_method = sizing_method
        self.sizing_strategy = sizing_strategy
        self.target_portfolio_risk = target_portfolio_risk
        self.use_volatility_sizing = use_volatility_sizing
        self.pyramiding_enabled = pyramiding_enabled
        self.news_adjustment = news_adjustment
        self.delta = delta

    def calculate_position_size(
        self, entry_price: float, stop_loss: float, symbol: str
    ) -> Dict[str, Any]:
        """Calculate position size based on fixed risk percentage."""
        # Check for invalid stop loss
        if stop_loss == entry_price:
            raise ValueError("Invalid stop loss: cannot be same as entry price")

        # Calculate stop distance in pips
        stop_distance = abs(entry_price - stop_loss)
        stop_distance_pips = stop_distance * 10000  # For forex pairs

        # Calculate risk amount
        risk_amount = self.account_balance * (self.risk_percentage / 100)

        # Check if balance is too small
        if self.account_balance < 1000:
            return {
                "lots": 0,
                "units": 0,
                "risk_amount": 0,
                "stop_distance_pips": stop_distance_pips,
                "error": "Insufficient balance",
            }

        # Calculate position size in lots
        # Risk per pip = risk_amount / stop_distance_pips
        # For standard lot (100,000 units), 1 pip = $10
        risk_per_pip = risk_amount / stop_distance_pips
        lots = risk_per_pip / 10  # $10 per pip for standard lot

        # Apply maximum position size cap
        original_lots = lots
        capped = False
        if self.max_position_size and lots > self.max_position_size:
            lots = self.max_position_size
            capped = True

        units = int(round(lots * 100000))

        return {
            "lots": round(lots, 2),
            "units": units,
            "risk_amount": risk_amount,
            "stop_distance_pips": stop_distance_pips,
            "capped": capped,
            "original_lots": original_lots,
        }

    def calculate_kelly_position(
        self, win_rate: float, avg_win: float, avg_loss: float, confidence_factor: float
    ) -> Dict[str, Any]:
        """Calculate position size using Kelly Criterion."""
        # Kelly formula: f = (p*b - q) / b
        # where p = win probability, q = loss probability, b = win/loss ratio
        p = win_rate
        q = 1 - win_rate
        b = avg_win / avg_loss

        kelly_raw = (p * b - q) / b

        # Check for negative Kelly (don't trade)
        if kelly_raw <= 0:
            return {
                "kelly_percentage": 0,
                "position_value": 0,
                "recommendation": "DO_NOT_TRADE",
            }

        # Apply confidence factor (fractional Kelly)
        kelly_percentage = kelly_raw * confidence_factor * 100

        # Calculate position value
        position_value = self.account_balance * (kelly_percentage / 100)

        return {
            "kelly_percentage": round(kelly_percentage, 2),
            "position_value": round(position_value, 0),
        }

    def calculate_with_correlation(
        self,
        entry_price: float,
        stop_loss: float,
        symbol: str,
        existing_positions: List[Dict],
    ) -> Dict[str, Any]:
        """Calculate position size adjusted for correlation risk."""
        # Start with base position calculation
        base_position = self.calculate_position_size(entry_price, stop_loss, symbol)

        # Calculate correlation adjustment
        total_correlation = sum(
            pos["correlation"] * pos["lots"] for pos in existing_positions
        )

        # Reduce position size based on correlation
        correlation_factor = max(0.3, 1 - (total_correlation * 0.3))  # Reduce up to 70%
        adjusted_lots = base_position["lots"] * correlation_factor

        # Calculate effective risk
        effective_risk = self.risk_percentage * correlation_factor

        return {
            "lots": round(adjusted_lots, 2),
            "units": int(adjusted_lots * 100000),
            "correlation_adjustment": round(1 - correlation_factor, 2),
            "effective_risk": round(effective_risk, 2),
            "risk_amount": base_position["risk_amount"],
            "stop_distance_pips": base_position["stop_distance_pips"],
        }

    def calculate_anti_martingale(
        self,
        base_lots: float,
        recent_trades: List[Dict],
        increase_factor: float,
        decrease_factor: float,
    ) -> Dict[str, Any]:
        """Calculate position with anti-martingale adjustment."""
        # Count consecutive wins/losses
        consecutive_wins = 0
        for trade in reversed(recent_trades):
            if trade["result"] == "win":
                consecutive_wins += 1
            else:
                break

        # Calculate multiplier based on streak
        if consecutive_wins > 0:
            streak_multiplier = 1 + (
                (increase_factor - 1) * min(consecutive_wins, 3) / 3
            )
        else:
            streak_multiplier = decrease_factor

        adjusted_lots = base_lots * streak_multiplier

        return {
            "adjusted_lots": round(adjusted_lots, 2),
            "streak_multiplier": round(streak_multiplier, 2),
            "strategy": "anti_martingale",
            "consecutive_wins": consecutive_wins,
        }

    def calculate_risk_parity(
        self, symbol: str, volatility: float, portfolio_positions: List[Dict]
    ) -> Dict[str, Any]:
        """Calculate position for risk parity portfolio."""
        # Target risk contribution (equal across all positions)
        num_positions = len(portfolio_positions) + 1
        target_risk_contribution = self.target_portfolio_risk / num_positions

        # Calculate position value for equal risk contribution
        position_value = (
            (target_risk_contribution / volatility) * self.account_balance / 100
        )

        # Calculate weight
        weight = position_value / self.account_balance

        return {
            "risk_contribution": round(target_risk_contribution, 2),
            "position_value": round(position_value, 0),
            "weight": round(weight, 4),
        }

    def calculate_volatility_adjusted(
        self,
        entry_price: float,
        stop_loss: float,
        symbol: str,
        current_atr: float,
        average_atr: float,
    ) -> Dict[str, Any]:
        """Calculate position adjusted for market volatility."""
        # Base position
        base_position = self.calculate_position_size(entry_price, stop_loss, symbol)

        # Volatility adjustment (inverse relationship)
        volatility_ratio = current_atr / average_atr
        volatility_multiplier = 1 / volatility_ratio

        adjusted_lots = base_position["lots"] * volatility_multiplier

        return {
            "lots": round(adjusted_lots, 2),
            "units": int(adjusted_lots * 100000),
            "volatility_multiplier": round(volatility_multiplier, 3),
            "adjusted_lots": round(adjusted_lots, 2),
            "risk_amount": base_position["risk_amount"],
            "stop_distance_pips": base_position["stop_distance_pips"],
        }

    def calculate_with_margin_check(
        self, entry_price: float, stop_loss: float, symbol: str
    ) -> Dict[str, Any]:
        """Calculate position respecting margin requirements."""
        # Maximum units based on available margin
        max_units_by_margin = (self.available_margin * self.leverage) / entry_price

        # Calculate risk-based position
        risk_position = self.calculate_position_size(entry_price, stop_loss, symbol)

        # Use smaller of the two
        if risk_position["units"] * entry_price / self.leverage > self.available_margin:
            units = int(max_units_by_margin)
            lots = units / 100000
            margin_limited = True
        else:
            units = risk_position["units"]
            lots = risk_position["lots"]
            margin_limited = False

        margin_used = (units * entry_price) / self.leverage

        return {
            "lots": round(lots, 2),
            "units": units,
            "margin_used": round(margin_used, 2),
            "margin_limited": margin_limited,
            "risk_amount": risk_position["risk_amount"],
            "stop_distance_pips": risk_position["stop_distance_pips"],
        }

    def calculate_pyramid_addition(
        self,
        existing_position: Dict,
        new_entry: float,
        new_stop: float,
        max_pyramid_units: int,
    ) -> Dict[str, Any]:
        """Calculate pyramid position addition."""
        # Current units count
        current_units = 1  # Start with 1 unit for existing position

        # Pyramid should be smaller than initial position
        add_lots = existing_position["lots"] * 0.5  # 50% of initial

        # Check max units
        if current_units >= max_pyramid_units:
            add_lots = 0

        # Calculate new weighted entry
        total_lots = existing_position["lots"] + add_lots
        weighted_entry = (
            (
                existing_position["entry"] * existing_position["lots"]
                + new_entry * add_lots
            )
            / total_lots
            if total_lots > 0
            else new_entry
        )

        return {
            "add_lots": round(add_lots, 2),
            "total_units": min(current_units + 1, max_pyramid_units),
            "weighted_entry": round(weighted_entry, 4),
        }

    def calculate_optimal_f(
        self, trade_history: List[float], safety_factor: float
    ) -> Dict[str, Any]:
        """Calculate position using Optimal f method."""
        if not trade_history:
            return {"optimal_f": 0, "risk_amount": 0}

        # Find worst loss
        worst_loss = abs(min(trade_history))

        # Calculate optimal f (simplified version)
        # Real optimal f requires iterative calculation
        wins = [t for t in trade_history if t > 0]
        losses = [abs(t) for t in trade_history if t < 0]

        if not losses:
            return {"optimal_f": 0, "risk_amount": 0}

        win_rate = len(wins) / len(trade_history)
        avg_win = sum(wins) / len(wins) if wins else 0
        avg_loss = sum(losses) / len(losses) if losses else worst_loss

        # Simplified optimal f calculation
        if avg_loss > 0:
            optimal_f_raw = (
                win_rate * avg_win - (1 - win_rate) * avg_loss
            ) / worst_loss
        else:
            optimal_f_raw = 0

        optimal_f = max(0, min(optimal_f_raw, 0.25))  # Cap at 25%
        optimal_f *= safety_factor

        risk_amount = self.account_balance * optimal_f

        return {
            "optimal_f": round(optimal_f, 4),
            "risk_amount": round(risk_amount, 2),
        }

    def calculate_with_news_adjustment(
        self,
        entry_price: float,
        stop_loss: float,
        symbol: str,
        upcoming_news: List[Dict],
    ) -> Dict[str, Any]:
        """Calculate position with news event adjustment."""
        # Base position
        base_position = self.calculate_position_size(entry_price, stop_loss, symbol)

        # Check for high impact news
        high_impact = any(
            news["impact"] == "high" and news["minutes_until"] < 60
            for news in upcoming_news
        )

        # Reduce position for news
        if high_impact:
            news_multiplier = 0.5  # Reduce by 50%
        elif any(news["impact"] == "medium" for news in upcoming_news):
            news_multiplier = 0.75  # Reduce by 25%
        else:
            news_multiplier = 1.0

        adjusted_lots = base_position["lots"] * news_multiplier

        result = {
            "lots": round(adjusted_lots, 2),
            "units": int(adjusted_lots * 100000),
            "news_multiplier": news_multiplier,
            "adjusted_lots": round(adjusted_lots, 2),
            "risk_amount": base_position["risk_amount"],
            "stop_distance_pips": base_position["stop_distance_pips"],
        }

        if high_impact:
            result["high_impact_warning"] = "High impact news in < 60 minutes"

        return result

    def calculate_fixed_ratio(
        self, base_units: int, min_units: int, max_units: int
    ) -> Dict[str, Any]:
        """Calculate position using fixed ratio money management."""
        # Calculate profit
        profit = self.current_balance - self.starting_balance

        if profit <= 0:
            units = min_units
        else:
            # Fixed ratio formula: N = base + sqrt(2 * P / delta)
            # Simplified: units = base + (profit / delta)
            additional_units = int(profit / self.delta)
            units = min(base_units + additional_units, max_units)

        return {
            "units": units,
            "method": "fixed_ratio",
            "profit_per_unit": self.delta,
        }
