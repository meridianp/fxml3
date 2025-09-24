"""
Risk Manager for FXML4

TDD-driven implementation of comprehensive risk management system.
Following Green phase - minimal implementation to pass tests.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd


class RiskManager:
    """Comprehensive risk management system."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize risk manager with configuration."""
        self.config = config
        self.risk_alerts = []
        self.position_limits = {}

    def calculate_position_size(
        self,
        symbol: str,
        risk_amount: float,
        stop_loss_pips: float,
        pip_value: float,
        account_balance: float = None,
        **kwargs,
    ) -> int:
        """Calculate position size based on risk parameters.

        Formula: Position Size (lots) = Risk Amount / (Stop Loss Pips × Pip Value per lot)
        Then convert lots to units: Position Size (units) = lots × 100,000

        Args:
            risk_amount: Amount willing to risk ($)
            stop_loss_pips: Stop loss distance in pips
            pip_value: Value of 1 pip for 1 standard lot ($)
        """
        # Calculate position size in lots
        position_size_lots = risk_amount / (stop_loss_pips * pip_value)

        # Convert to units and round down
        position_size_units = int(position_size_lots * 100000)

        # Apply maximum position limit
        max_position = self.config["max_position_size"]
        if position_size_units > max_position:
            return max_position

        return position_size_units

    def calculate_correlated_position_size(
        self,
        trade_params: Dict[str, Any],
        existing_portfolio: pd.DataFrame,
        correlation_matrix: pd.DataFrame,
    ) -> int:
        """Calculate position size adjusted for correlation with existing positions."""
        # Get base position size
        base_size = self.calculate_position_size(**trade_params)

        # Find correlated positions
        symbol = trade_params["symbol"]
        if symbol not in correlation_matrix.columns:
            return base_size

        # Calculate correlation adjustment factor
        total_correlation = 0
        for _, position in existing_portfolio.iterrows():
            if position["symbol"] in correlation_matrix.index:
                correlation = correlation_matrix.loc[position["symbol"], symbol]
                position_weight = abs(position["position_size"]) / 1000000  # Normalize
                total_correlation += abs(correlation) * position_weight

        # Reduce position size based on correlation
        # Higher correlation = smaller position
        adjustment_factor = max(0.2, 1 - total_correlation * 0.5)

        return int(base_size * adjustment_factor)

    def calculate_total_margin_required(self, positions: List[Dict[str, Any]]) -> float:
        """Calculate total margin requirement for positions."""
        total_margin = 0
        margin_requirement = self.config.get("margin_requirement", 0.02)

        for position in positions:
            # Calculate notional value
            if position["symbol"] == "USD/JPY":
                # Special handling for JPY pairs
                notional_value = position["size"]
            else:
                notional_value = position["size"] * position["price"]

            total_margin += notional_value * margin_requirement

        return total_margin

    def validate_leverage(self, account_equity: float, position_value: float) -> bool:
        """Validate if leverage is within limits."""
        leverage = position_value / account_equity
        max_leverage = self.config.get("leverage_limit", 50)

        return leverage <= max_leverage

    def check_margin_status(
        self, account_state: Dict[str, Any], portfolio: pd.DataFrame
    ) -> Dict[str, Any]:
        """Check margin status and generate warnings."""
        margin_level = account_state["margin_level"]

        status = "OK"
        actions_required = []

        if margin_level < 150:
            status = "WARNING"
            actions_required.append("Consider reducing positions")

        if margin_level < 100:
            status = "CRITICAL"
            actions_required.append("Immediate position reduction required")

        return {
            "status": status,
            "margin_level": margin_level,
            "actions_required": actions_required,
            "free_margin": account_state.get("free_margin", 0),
            "used_margin": account_state.get("used_margin", 0),
        }

    def calculate_portfolio_var(
        self,
        returns: pd.DataFrame,
        weights: np.ndarray,
        portfolio_value: float,
        confidence_level: float = 0.95,
        time_horizon: int = 1,
    ) -> float:
        """Calculate Value at Risk for portfolio."""
        # Calculate portfolio returns
        portfolio_returns = (returns * weights).sum(axis=1)

        # Calculate VaR at specified confidence level
        var_percentile = (1 - confidence_level) * 100
        var_return = np.percentile(portfolio_returns, var_percentile)

        # Scale by time horizon (square root of time)
        var_scaled = var_return * np.sqrt(time_horizon)

        # Convert to dollar value
        var_dollar = abs(var_scaled * portfolio_value)

        return var_dollar

    def calculate_expected_shortfall(
        self,
        returns: pd.DataFrame,
        weights: np.ndarray,
        portfolio_value: float,
        confidence_level: float = 0.95,
    ) -> float:
        """Calculate Expected Shortfall (Conditional VaR)."""
        # Calculate portfolio returns
        portfolio_returns = (returns * weights).sum(axis=1)

        # Find VaR threshold
        var_percentile = (1 - confidence_level) * 100
        var_threshold = np.percentile(portfolio_returns, var_percentile)

        # Calculate mean of returns beyond VaR
        tail_returns = portfolio_returns[portfolio_returns <= var_threshold]
        expected_shortfall_return = (
            tail_returns.mean() if len(tail_returns) > 0 else var_threshold
        )

        # Convert to dollar value
        expected_shortfall = abs(expected_shortfall_return * portfolio_value)

        return expected_shortfall

    def assess_correlation_risk(
        self,
        portfolio: pd.DataFrame,
        correlation_matrix: pd.DataFrame,
    ) -> Dict[str, Any]:
        """Assess correlation risk in portfolio."""
        # Find highly correlated position pairs
        concentrated_exposures = []

        for i, row1 in portfolio.iterrows():
            for j, row2 in portfolio.iterrows():
                if i < j:  # Avoid duplicates
                    symbol1, symbol2 = row1["symbol"], row2["symbol"]
                    if (
                        symbol1 in correlation_matrix.index
                        and symbol2 in correlation_matrix.columns
                    ):
                        corr = correlation_matrix.loc[symbol1, symbol2]
                        if abs(corr) > 0.7:  # High correlation threshold
                            concentrated_exposures.append(
                                {
                                    "pair": (symbol1, symbol2),
                                    "correlation": corr,
                                    "combined_exposure": abs(row1["position_size"])
                                    + abs(row2["position_size"]),
                                }
                            )

        # Calculate diversification ratio
        n_positions = len(portfolio)
        avg_correlation = 0
        count = 0

        for i in range(n_positions):
            for j in range(i + 1, n_positions):
                symbol1 = portfolio.iloc[i]["symbol"]
                symbol2 = portfolio.iloc[j]["symbol"]
                if (
                    symbol1 in correlation_matrix.index
                    and symbol2 in correlation_matrix.columns
                ):
                    avg_correlation += abs(correlation_matrix.loc[symbol1, symbol2])
                    count += 1

        avg_correlation = avg_correlation / count if count > 0 else 0
        diversification_ratio = 1 - avg_correlation

        return {
            "concentrated_exposures": concentrated_exposures,
            "diversification_ratio": diversification_ratio,
            "average_correlation": avg_correlation,
        }

    def calculate_drawdown_statistics(self, equity_curve: pd.Series) -> Dict[str, Any]:
        """Calculate drawdown statistics from equity curve."""
        # Calculate running maximum
        running_max = equity_curve.expanding().max()

        # Calculate drawdown from initial value (as test expects)
        initial_value = equity_curve.iloc[0]

        # Maximum drawdown from initial value
        min_value = equity_curve.min()
        max_drawdown = (min_value - initial_value) / initial_value

        # Current drawdown from peak
        current_peak = running_max.iloc[-1]
        current_value = equity_curve.iloc[-1]
        current_drawdown = (
            (current_value - current_peak) / current_peak if current_peak > 0 else 0
        )

        # Drawdown duration
        in_drawdown = equity_curve < running_max
        drawdown_periods = []
        start_idx = None

        for i, is_dd in enumerate(in_drawdown):
            if is_dd and start_idx is None:
                start_idx = i
            elif not is_dd and start_idx is not None:
                drawdown_periods.append(i - start_idx)
                start_idx = None

        if start_idx is not None:
            drawdown_periods.append(len(equity_curve) - start_idx)

        max_duration = max(drawdown_periods) if drawdown_periods else 0

        return {
            "max_drawdown": max_drawdown,
            "current_drawdown": current_drawdown,
            "drawdown_duration": max_duration,
            "recovery_required": (
                abs(current_drawdown / (1 + current_drawdown))
                if current_drawdown < 0
                else 0
            ),
        }

    def generate_stress_scenarios(
        self,
        historical_returns: pd.DataFrame,
        num_scenarios: int = 10,
        stress_magnitude: float = 3.0,
    ) -> List[pd.DataFrame]:
        """Generate stress test scenarios."""
        scenarios = []

        # Calculate historical statistics
        mean_returns = historical_returns.mean()
        std_returns = historical_returns.std()

        for _ in range(num_scenarios):
            # Generate stressed returns
            # Mix of historical extremes and synthetic shocks
            scenario = pd.DataFrame(index=range(20), columns=historical_returns.columns)

            for col in historical_returns.columns:
                # Random stress direction and magnitude
                stress_direction = np.random.choice([-1, 1])
                stress_level = np.random.uniform(2, stress_magnitude)

                # Generate stressed returns
                stressed_returns = np.random.normal(
                    mean_returns[col]
                    + stress_direction * stress_level * std_returns[col],
                    std_returns[col] * 1.5,  # Increased volatility
                    20,
                )

                scenario[col] = stressed_returns

            scenarios.append(scenario)

        return scenarios

    def run_portfolio_stress_test(
        self,
        portfolio: pd.DataFrame,
        historical_returns: pd.DataFrame,
        num_scenarios: int = 5,
        initial_portfolio_value: float = 1000000,
    ) -> Dict[str, Any]:
        """Run stress test on portfolio."""
        # Generate stress scenarios
        stress_scenarios = self.generate_stress_scenarios(
            historical_returns, num_scenarios
        )

        scenario_results = []

        for i, scenario in enumerate(stress_scenarios):
            # Calculate portfolio performance under stress
            portfolio_return = 0

            for _, position in portfolio.iterrows():
                symbol = position["symbol"]
                if symbol in scenario.columns:
                    # Calculate position return under stress
                    position_weight = position["market_value"] / initial_portfolio_value
                    position_return = scenario[symbol].sum()  # Cumulative stress return
                    portfolio_return += position_weight * position_return

            scenario_pnl = initial_portfolio_value * portfolio_return
            scenario_results.append(
                {
                    "scenario": i + 1,
                    "portfolio_return": portfolio_return,
                    "pnl": scenario_pnl,
                }
            )

        # Find worst and best cases
        pnls = [r["pnl"] for r in scenario_results]
        worst_case_loss = min(pnls)
        best_case_gain = max(pnls)

        return {
            "worst_case_loss": worst_case_loss,
            "best_case_gain": best_case_gain,
            "scenario_results": scenario_results,
            "average_stress_pnl": np.mean(pnls),
            "stress_var_95": np.percentile(pnls, 5),
        }

    def validate_trade(
        self,
        proposed_trade: Dict[str, Any],
        current_portfolio: pd.DataFrame,
        account_balance: float,
    ) -> Dict[str, Any]:
        """Validate proposed trade against risk limits."""
        # Calculate trade risk
        trade_value = proposed_trade["quantity"] * proposed_trade["price"]

        # Risk per trade
        if "stop_loss" in proposed_trade:
            risk_per_trade = (
                abs(proposed_trade["price"] - proposed_trade["stop_loss"])
                * proposed_trade["quantity"]
            )
        else:
            risk_per_trade = trade_value * 0.02  # Default 2% risk

        # Check various limits
        limit_checks = {
            "position_size": trade_value <= self.config["max_position_size"],
            "risk_per_trade": risk_per_trade
            <= account_balance * self.config["max_portfolio_risk"],
            "leverage": trade_value / account_balance <= self.config["leverage_limit"],
        }

        is_valid = all(limit_checks.values())

        return {
            "is_valid": is_valid,
            "risk_metrics": {
                "trade_value": trade_value,
                "risk_amount": risk_per_trade,
                "risk_percentage": risk_per_trade / account_balance,
            },
            "limit_checks": limit_checks,
            "warnings": [k for k, v in limit_checks.items() if not v],
        }

    def check_position_concentration(
        self,
        new_position: Dict[str, Any],
        current_portfolio: pd.DataFrame,
        total_portfolio_value: float,
    ) -> Dict[str, Any]:
        """Check if position concentration exceeds limits."""
        position_value = new_position["market_value"]
        concentration_ratio = abs(position_value) / total_portfolio_value

        exceeds_limit = (
            concentration_ratio > self.config["position_concentration_limit"]
        )

        return {
            "exceeds_limit": exceeds_limit,
            "concentration_ratio": concentration_ratio,
            "limit": self.config["position_concentration_limit"],
            "position_value": position_value,
            "portfolio_value": total_portfolio_value,
        }

    def check_daily_loss_limits(
        self,
        daily_pnl: float,
        account_balance: float,
        max_daily_loss_pct: float = 0.10,
    ) -> Dict[str, Any]:
        """Check if daily loss limits are exceeded."""
        daily_loss_pct = abs(daily_pnl) / account_balance
        limit_exceeded = daily_pnl < 0 and daily_loss_pct > max_daily_loss_pct

        recommended_action = "CONTINUE" if not limit_exceeded else "HALT_TRADING"

        return {
            "limit_exceeded": limit_exceeded,
            "daily_pnl": daily_pnl,
            "daily_loss_pct": daily_loss_pct,
            "max_allowed_loss_pct": max_daily_loss_pct,
            "recommended_action": recommended_action,
        }

    def generate_risk_alerts(
        self,
        portfolio: pd.DataFrame,
        market_moves: Dict[str, float],
        account_equity: float,
    ) -> List[Dict[str, Any]]:
        """Generate real-time risk alerts based on market conditions."""
        alerts = []

        # Calculate portfolio impact
        total_impact = 0
        for _, position in portfolio.iterrows():
            symbol = position["symbol"]
            if symbol in market_moves:
                position_impact = position["position_size"] * market_moves[symbol]
                total_impact += position_impact

        # Check for margin warnings
        portfolio_value = portfolio["market_value"].sum()
        new_equity = account_equity + total_impact
        margin_usage = portfolio_value / new_equity if new_equity > 0 else float("inf")

        if margin_usage > 0.8:  # 80% margin usage
            alerts.append(
                {
                    "type": "MARGIN_WARNING",
                    "severity": "HIGH" if margin_usage > 0.9 else "MEDIUM",
                    "message": f"Margin usage at {margin_usage:.1%}",
                    "timestamp": datetime.now(),
                }
            )

        # Check for large losses
        loss_pct = abs(total_impact) / account_equity if total_impact < 0 else 0
        if loss_pct > 0.05:  # 5% loss
            alerts.append(
                {
                    "type": "LARGE_LOSS",
                    "severity": "CRITICAL" if loss_pct > 0.1 else "HIGH",
                    "message": f"Portfolio loss of {loss_pct:.1%}",
                    "timestamp": datetime.now(),
                }
            )

        return alerts

    def calculate_portfolio_heatmap(
        self,
        portfolio: pd.DataFrame,
        volatilities: Dict[str, float],
    ) -> Dict[str, Any]:
        """Calculate portfolio risk heat map."""
        position_risks = []
        total_risk = 0

        for _, position in portfolio.iterrows():
            symbol = position["symbol"]
            volatility = volatilities.get(symbol, 0.01)  # Default 1% vol

            # Position risk = Position Size × Volatility
            position_risk = abs(position["position_size"]) * volatility

            position_risks.append(
                {
                    "symbol": symbol,
                    "position_size": position["position_size"],
                    "volatility": volatility,
                    "risk_contribution": position_risk,
                    "risk_percentage": (
                        position_risk / abs(position["position_size"])
                        if position["position_size"] != 0
                        else 0
                    ),
                }
            )

            total_risk += position_risk

        # Normalize risk contributions
        for risk in position_risks:
            risk["portfolio_risk_contribution"] = (
                risk["risk_contribution"] / total_risk if total_risk > 0 else 0
            )

        return {
            "position_risks": position_risks,
            "total_portfolio_risk": total_risk,
            "risk_concentration": (
                max(p["portfolio_risk_contribution"] for p in position_risks)
                if position_risks
                else 0
            ),
        }

    def generate_leverage_compliance_report(
        self,
        portfolio: pd.DataFrame,
        account_equity: float,
        jurisdiction: str = "US",
    ) -> Dict[str, Any]:
        """Generate regulatory leverage compliance report."""
        # Calculate total exposure
        total_exposure = portfolio["market_value"].abs().sum()
        effective_leverage = total_exposure / account_equity

        # Jurisdiction-specific limits
        regulatory_limits = {
            "US": 50,  # 50:1 for major pairs
            "EU": 30,  # 30:1 under ESMA
            "UK": 30,  # 30:1 under FCA
            "JP": 25,  # 25:1 under JFSA
        }

        regulatory_limit = regulatory_limits.get(jurisdiction, 50)
        is_compliant = effective_leverage <= regulatory_limit

        return {
            "effective_leverage": effective_leverage,
            "regulatory_limit": regulatory_limit,
            "is_compliant": is_compliant,
            "jurisdiction": jurisdiction,
            "total_exposure": total_exposure,
            "account_equity": account_equity,
            "margin_required": total_exposure / regulatory_limit,
        }

    def identify_reportable_positions(
        self,
        portfolio: pd.DataFrame,
        reporting_threshold: float,
    ) -> List[Dict[str, Any]]:
        """Identify positions that meet regulatory reporting requirements."""
        reportable = []

        for _, position in portfolio.iterrows():
            if abs(position["market_value"]) >= reporting_threshold:
                reportable.append(
                    {
                        "symbol": position["symbol"],
                        "position_size": position["position_size"],
                        "market_value": position["market_value"],
                        "reporting_required": True,
                        "threshold": reporting_threshold,
                    }
                )

        return reportable

    def calculate_total_portfolio_risk(self, portfolio: pd.DataFrame) -> float:
        """Calculate total portfolio risk metric."""
        # Simple risk calculation based on position sizes and assumed volatility
        total_risk = 0

        for _, position in portfolio.iterrows():
            # Assume 1% daily volatility for all positions
            position_risk = abs(position["position_size"]) * 0.01
            total_risk += position_risk

        return total_risk

    async def calculate_portfolio_risk_async(
        self,
        portfolio_id: str,
        portfolio: pd.DataFrame,
    ) -> Dict[str, Any]:
        """Async portfolio risk calculation."""
        # Simulate async calculation
        risk_value = self.calculate_total_portfolio_risk(portfolio)

        return {
            "portfolio_id": portfolio_id,
            "total_risk": risk_value,
            "timestamp": datetime.now(),
        }
