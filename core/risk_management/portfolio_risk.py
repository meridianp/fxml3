"""
Portfolio Risk Aggregator - TDD Implementation (GREEN Phase)
Minimal implementation to make tests pass
"""

import math
import statistics
from typing import Any, Dict, List, Optional, Tuple


class PortfolioRiskAggregator:
    """
    Aggregate and monitor portfolio-level risk metrics.
    GREEN phase: Minimal implementation to pass tests.
    """

    def __init__(
        self,
        account_balance: float = 100000,
        max_portfolio_risk: float = 10.0,
        max_daily_loss: float = 5.0,
        max_single_position: float = 15.0,
        max_sector_concentration: float = 30.0,
        max_correlation_exposure: float = 25.0,
        max_total_leverage: float = 10.0,
        warning_margin_ratio: float = 50.0,
        critical_margin_ratio: float = 80.0,
        var_confidence: float = 0.95,
        var_horizon_days: int = 1,
        risk_threshold_warning: float = 3.0,
        risk_threshold_critical: float = 5.0,
        base_currency: str = "USD",
    ):
        """Initialize portfolio risk aggregator."""
        self.account_balance = account_balance
        self.max_portfolio_risk = max_portfolio_risk
        self.max_daily_loss = max_daily_loss
        self.max_single_position = max_single_position
        self.max_sector_concentration = max_sector_concentration
        self.max_correlation_exposure = max_correlation_exposure
        self.max_total_leverage = max_total_leverage
        self.warning_margin_ratio = warning_margin_ratio
        self.critical_margin_ratio = critical_margin_ratio
        self.var_confidence = var_confidence
        self.var_horizon_days = var_horizon_days
        self.risk_threshold_warning = risk_threshold_warning
        self.risk_threshold_critical = risk_threshold_critical
        self.base_currency = base_currency

    def calculate_total_risk(self, positions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate total risk exposure across all positions."""
        if not positions:
            return {
                "total_risk_amount": 0,
                "total_portfolio_value": 0,
                "risk_percentage": 0,
                "positions_count": 0,
            }

        total_risk_amount = sum(pos.get("risk_amount", 0) for pos in positions)
        total_portfolio_value = sum(pos.get("position_value", 0) for pos in positions)
        risk_percentage = (total_risk_amount / self.account_balance) * 100

        return {
            "total_risk_amount": total_risk_amount,
            "total_portfolio_value": total_portfolio_value,
            "risk_percentage": risk_percentage,
            "positions_count": len(positions),
        }

    def calculate_correlation_adjusted_risk(
        self, positions: List[Dict[str, Any]], correlation_matrix: Dict[Tuple, float]
    ) -> Dict[str, Any]:
        """Adjust risk based on correlation between positions."""
        raw_risk = sum(pos.get("risk_amount", 0) for pos in positions)

        if not correlation_matrix or len(positions) < 2:
            return {
                "raw_risk": raw_risk,
                "correlation_adjusted_risk": raw_risk,
                "diversification_benefit": 0,
                "effective_risk_reduction": 0,
            }

        # Simplified correlation adjustment
        # In practice, this would use full covariance matrix calculation
        total_correlation_effect = 0
        pair_count = 0

        for i, pos1 in enumerate(positions):
            for j, pos2 in enumerate(positions[i + 1 :], i + 1):
                symbol1 = pos1.get("symbol")
                symbol2 = pos2.get("symbol")
                corr = correlation_matrix.get((symbol1, symbol2), 0)
                if corr == 0:
                    corr = correlation_matrix.get((symbol2, symbol1), 0)

                # Weight correlation by position sizes
                weight1 = pos1.get("risk_amount", 0) / raw_risk if raw_risk > 0 else 0
                weight2 = pos2.get("risk_amount", 0) / raw_risk if raw_risk > 0 else 0
                correlation_contribution = abs(corr) * weight1 * weight2
                total_correlation_effect += correlation_contribution
                pair_count += 1

        # Reduce risk based on diversification (negative correlations help)
        if pair_count > 0:
            avg_correlation = total_correlation_effect / pair_count
            risk_reduction_factor = 1 - (avg_correlation * 0.3)  # Max 30% reduction
            correlation_adjusted_risk = raw_risk * max(0.7, risk_reduction_factor)
        else:
            correlation_adjusted_risk = raw_risk

        diversification_benefit = raw_risk - correlation_adjusted_risk
        effective_risk_reduction = (
            (diversification_benefit / raw_risk) * 100 if raw_risk > 0 else 0
        )

        return {
            "raw_risk": raw_risk,
            "correlation_adjusted_risk": correlation_adjusted_risk,
            "diversification_benefit": diversification_benefit,
            "effective_risk_reduction": effective_risk_reduction,
        }

    def calculate_portfolio_var(
        self,
        positions: List[Dict[str, Any]],
        historical_returns: Dict[str, List[float]],
    ) -> Dict[str, Any]:
        """Calculate Value at Risk for portfolio."""
        if not positions or not historical_returns:
            return {
                "var_amount": 0,
                "var_percentage": 0,
                "confidence_level": self.var_confidence,
                "horizon_days": self.var_horizon_days,
                "worst_case_loss": 0,
            }

        # Calculate portfolio returns
        portfolio_returns = []
        total_value = sum(pos.get("position_value", 0) for pos in positions)

        # Get minimum return length
        min_length = min(len(returns) for returns in historical_returns.values())

        for i in range(min_length):
            portfolio_return = 0
            for pos in positions:
                symbol = pos.get("symbol")
                weight = pos.get(
                    "weight",
                    (
                        pos.get("position_value", 0) / total_value
                        if total_value > 0
                        else 0
                    ),
                )
                if symbol in historical_returns and i < len(historical_returns[symbol]):
                    portfolio_return += weight * historical_returns[symbol][i]
            portfolio_returns.append(portfolio_return)

        if not portfolio_returns:
            return {
                "var_amount": 0,
                "var_percentage": 0,
                "confidence_level": self.var_confidence,
                "horizon_days": self.var_horizon_days,
                "worst_case_loss": 0,
            }

        # Calculate VaR at specified confidence level
        portfolio_returns.sort()
        var_index = int((1 - self.var_confidence) * len(portfolio_returns))
        var_return = (
            portfolio_returns[var_index]
            if var_index < len(portfolio_returns)
            else portfolio_returns[0]
        )

        var_amount = abs(var_return * total_value)
        var_percentage = abs(var_return) * 100
        worst_case_loss = abs(portfolio_returns[0] * total_value)

        return {
            "var_amount": var_amount,
            "var_percentage": var_percentage,
            "confidence_level": self.var_confidence,
            "horizon_days": self.var_horizon_days,
            "worst_case_loss": worst_case_loss,
        }

    def calculate_concentration_risk(
        self, positions: List[Dict[str, Any]], portfolio_value: float
    ) -> Dict[str, Any]:
        """Identify concentration risk in portfolio."""
        if not positions or portfolio_value == 0:
            return {
                "largest_position_pct": 0,
                "concentration_warning": False,
                "over_concentrated_sectors": [],
            }

        # Calculate position concentrations
        position_percentages = []
        for pos in positions:
            pct = (pos.get("position_value", 0) / portfolio_value) * 100
            position_percentages.append(pct)

        largest_position_pct = max(position_percentages) if position_percentages else 0

        # Calculate sector concentrations
        sector_totals = {}
        for pos in positions:
            sector = pos.get("sector", "unknown")
            value = pos.get("position_value", 0)
            sector_totals[sector] = sector_totals.get(sector, 0) + value

        # Check for over-concentration
        over_concentrated_sectors = []
        concentration_warning = largest_position_pct > self.max_single_position

        result = {
            "largest_position_pct": largest_position_pct,
            "concentration_warning": concentration_warning,
            "over_concentrated_sectors": over_concentrated_sectors,
        }

        # Add sector-specific concentrations
        for sector, value in sector_totals.items():
            sector_pct = (value / portfolio_value) * 100
            result[f"{sector}_concentration"] = sector_pct
            if sector_pct > self.max_sector_concentration:
                over_concentrated_sectors.append(sector)
                concentration_warning = True

        result["concentration_warning"] = concentration_warning
        result["over_concentrated_sectors"] = over_concentrated_sectors

        return result

    def calculate_leverage_exposure(
        self, positions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Calculate total leverage exposure across positions."""
        total_notional = sum(pos.get("position_value", 0) for pos in positions)
        total_margin_used = sum(pos.get("margin_used", 0) for pos in positions)

        effective_leverage = (
            total_notional / self.account_balance if self.account_balance > 0 else 0
        )
        margin_utilization = (
            (total_margin_used / self.account_balance) * 100
            if self.account_balance > 0
            else 0
        )

        return {
            "total_notional": total_notional,
            "total_margin_used": total_margin_used,
            "effective_leverage": effective_leverage,
            "margin_utilization": margin_utilization,
        }

    def validate_risk_limits(
        self, positions: List[Dict[str, Any]], current_daily_pnl: float
    ) -> Dict[str, Any]:
        """Validate portfolio against risk limits."""
        violations = []
        within_limits = True

        # Check daily loss limit
        daily_loss_pct = abs(current_daily_pnl) / self.account_balance * 100
        if current_daily_pnl < 0 and daily_loss_pct > self.max_daily_loss:
            violations.append("daily_loss_breach")
            within_limits = False

        # Check single position limits
        for pos in positions:
            position_pct = (pos.get("position_value", 0) / self.account_balance) * 100
            if position_pct > self.max_single_position:
                violations.append("single_position_breach")
                within_limits = False
                break

        # Check total portfolio risk
        total_risk = sum(pos.get("risk_amount", 0) for pos in positions)
        portfolio_risk_pct = (total_risk / self.account_balance) * 100
        if portfolio_risk_pct > self.max_portfolio_risk:
            violations.append("portfolio_risk_breach")
            within_limits = False

        return {"within_limits": within_limits, "violations": violations}

    def calculate_margin_analysis(
        self, positions: List[Dict[str, Any]], current_equity: float
    ) -> Dict[str, Any]:
        """Calculate margin utilization relative to equity."""
        total_margin_used = sum(pos.get("margin_used", 0) for pos in positions)
        margin_to_equity_ratio = (
            (total_margin_used / current_equity) * 100 if current_equity > 0 else 0
        )
        available_margin = current_equity - total_margin_used

        # Determine margin level
        if margin_to_equity_ratio >= self.critical_margin_ratio:
            margin_level = "critical"
        elif margin_to_equity_ratio >= self.warning_margin_ratio:
            margin_level = "warning"
        else:
            margin_level = "safe"

        return {
            "total_margin_used": total_margin_used,
            "margin_to_equity_ratio": margin_to_equity_ratio,
            "available_margin": available_margin,
            "margin_level": margin_level,
        }

    def calculate_sector_exposure(
        self, positions: List[Dict[str, Any]], total_portfolio_value: float
    ) -> Dict[str, Any]:
        """Calculate exposure by sector/asset class."""
        sector_exposure = {}

        for pos in positions:
            sector = pos.get("sector", "unknown")
            value = pos.get("position_value", 0)

            if sector not in sector_exposure:
                sector_exposure[sector] = {"value": 0, "percentage": 0}

            sector_exposure[sector]["value"] += value

        # Calculate percentages
        for sector in sector_exposure:
            sector_exposure[sector]["percentage"] = (
                (sector_exposure[sector]["value"] / total_portfolio_value) * 100
                if total_portfolio_value > 0
                else 0
            )

        return sector_exposure

    def calculate_drawdown_scenarios(
        self, positions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Calculate potential drawdown scenarios."""
        normal_max_loss = sum(pos.get("stop_loss_risk", 0) for pos in positions)
        stress_max_loss = sum(pos.get("stress_scenario_loss", 0) for pos in positions)

        normal_drawdown_pct = (normal_max_loss / self.account_balance) * 100
        stress_drawdown_pct = (stress_max_loss / self.account_balance) * 100

        return {
            "normal_scenario": {
                "max_loss": normal_max_loss,
                "drawdown_pct": normal_drawdown_pct,
            },
            "stress_scenario": {
                "max_loss": stress_max_loss,
                "drawdown_pct": stress_drawdown_pct,
            },
        }

    def calculate_risk_change(
        self,
        initial_positions: List[Dict[str, Any]],
        updated_positions: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Monitor risk changes as prices move."""
        price_changes = {}
        unrealized_pnl_change = 0

        # Create lookup for updated positions
        updated_lookup = {pos.get("symbol"): pos for pos in updated_positions}

        for initial_pos in initial_positions:
            symbol = initial_pos.get("symbol")
            if symbol in updated_lookup:
                updated_pos = updated_lookup[symbol]
                initial_price = initial_pos.get(
                    "current_price", initial_pos.get("entry_price", 0)
                )
                updated_price = updated_pos.get("current_price", 0)
                price_change = updated_price - initial_price
                price_changes[symbol] = price_change

                # Calculate P&L change (simplified)
                quantity = initial_pos.get("quantity", 0)
                if quantity > 0:
                    pnl_change = price_change * quantity * 10000  # Pip value for 1 lot
                    unrealized_pnl_change += pnl_change

        # Risk decreases when we have profits (increases equity)
        portfolio_risk_change = -unrealized_pnl_change / self.account_balance * 100

        return {
            "price_change": price_changes,
            "unrealized_pnl_change": unrealized_pnl_change,
            "portfolio_risk_change": portfolio_risk_change,
        }

    def calculate_portfolio_beta(
        self, positions: List[Dict[str, Any]], market_volatility: float
    ) -> Dict[str, Any]:
        """Calculate portfolio beta and systematic risk."""
        if not positions:
            return {"portfolio_beta": 0, "systematic_risk": 0, "market_correlation": 0}

        # Calculate weighted portfolio beta
        total_value = sum(pos.get("position_value", 0) for pos in positions)
        portfolio_beta = 0

        for pos in positions:
            weight = pos.get(
                "weight",
                pos.get("position_value", 0) / total_value if total_value > 0 else 0,
            )
            beta = pos.get("beta", 1.0)
            portfolio_beta += weight * beta

        # Calculate systematic risk
        systematic_risk = portfolio_beta * market_volatility * total_value
        market_correlation = min(abs(portfolio_beta), 1.0)  # Simplified correlation

        return {
            "portfolio_beta": portfolio_beta,
            "systematic_risk": systematic_risk,
            "market_correlation": market_correlation,
        }

    def identify_risk_hotspots(self, positions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Identify areas of elevated risk in portfolio."""
        critical_risks = []
        high_risk_positions = []
        risk_score = 0

        for pos in positions:
            symbol = pos.get("symbol")
            concentration = pos.get("concentration", 0)
            correlation_risk = pos.get("correlation_risk", "low")
            leverage = pos.get("leverage", 1)

            # Check concentration risk
            if concentration > 35:  # High concentration threshold
                critical_risks.append("concentration")
                high_risk_positions.append(symbol)
                risk_score += 2

            # Check correlation risk
            if correlation_risk == "high":
                critical_risks.append("correlation")
                risk_score += 1.5

            # Check leverage risk
            if leverage > 40:
                critical_risks.append("leverage")
                risk_score += 1

        return {
            "critical_risks": list(set(critical_risks)),
            "high_risk_positions": high_risk_positions,
            "risk_score": risk_score,
        }

    def calculate_liquidity_risk(
        self, positions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Assess liquidity risk of portfolio positions."""
        liquidity_analysis = {}
        total_liquidity_score = 0
        position_count = 0

        for pos in positions:
            symbol = pos.get("symbol")
            volume = pos.get("avg_daily_volume", 0)
            spread = pos.get("bid_ask_spread", 0)
            market_impact = pos.get("market_impact", 0)

            # Calculate liquidity score (0-10 scale)
            volume_score = min(
                10, math.log10(volume / 100000000) if volume > 0 else 0
            )  # Log scale adjusted
            spread_score = max(
                0, 10 - (spread * 5000)
            )  # Lower spread = higher score (adjusted)
            impact_score = max(
                0, 10 - (market_impact * 200)
            )  # Lower impact = higher score (adjusted)

            liquidity_score = (volume_score + spread_score + impact_score) / 3

            liquidity_analysis[symbol] = {
                "liquidity_score": liquidity_score,
                "volume_score": volume_score,
                "spread_score": spread_score,
                "impact_score": impact_score,
            }

            total_liquidity_score += liquidity_score
            position_count += 1

        # Determine overall portfolio liquidity risk
        avg_liquidity = (
            total_liquidity_score / position_count if position_count > 0 else 0
        )
        if avg_liquidity >= 7:
            portfolio_liquidity_risk = "low"
        elif avg_liquidity >= 4:
            portfolio_liquidity_risk = "medium"
        else:
            portfolio_liquidity_risk = "high"

        liquidity_analysis["portfolio_liquidity_risk"] = portfolio_liquidity_risk

        return liquidity_analysis

    def calculate_currency_exposure(
        self, positions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Calculate currency exposure across portfolio."""
        currency_exposure = {}

        for pos in positions:
            base_exp = pos.get("base_currency_exposure", 0)
            quote_exp = pos.get("quote_currency_exposure", 0)

            # Extract currencies from symbol (assumes XXX/YYY format)
            symbol = pos.get("symbol", "")
            if "/" in symbol:
                base_curr, quote_curr = symbol.split("/")

                # Track base currency exposure
                if base_curr not in currency_exposure:
                    currency_exposure[base_curr] = {"net_exposure": 0}
                currency_exposure[base_curr]["net_exposure"] += base_exp

                # Track quote currency exposure
                if quote_curr not in currency_exposure:
                    currency_exposure[quote_curr] = {"net_exposure": 0}
                currency_exposure[quote_curr]["net_exposure"] += quote_exp

        return currency_exposure

    def validate_leverage_limits(self, positions: List[Dict[str, Any]]) -> None:
        """Validate leverage limits and raise exception if exceeded."""
        leverage_data = self.calculate_leverage_exposure(positions)
        effective_leverage = leverage_data["effective_leverage"]

        if effective_leverage > self.max_total_leverage:
            raise ValueError(
                f"Leverage limit exceeded: {effective_leverage:.1f}:1 > {self.max_total_leverage}:1"
            )
