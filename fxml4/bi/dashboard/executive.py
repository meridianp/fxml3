"""
Executive Dashboard Implementation

Provides high-level business intelligence and executive analytics for FXML4 trading platform.
Features comprehensive portfolio overview, risk metrics, and performance attribution.
"""

import asyncio
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from ...core.exceptions import FXML4Exception
from ...core.logger import setup_logger
from ...data_engineering.database_manager import DatabaseManager
from ...risk_management.portfolio_manager import PortfolioManager

logger = setup_logger(__name__)


@dataclass
class ExecutiveMetrics:
    """Executive-level metrics for dashboard display."""

    total_pnl: Decimal
    daily_pnl: Decimal
    mtd_pnl: Decimal
    ytd_pnl: Decimal
    total_return: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    current_drawdown: float
    var_95: Decimal
    expected_shortfall: Decimal
    active_positions: int
    total_trades: int
    win_rate: float
    avg_win: Decimal
    avg_loss: Decimal
    profit_factor: float
    calmar_ratio: float
    portfolio_value: Decimal
    cash_available: Decimal
    margin_used: Decimal
    margin_available: Decimal
    leverage_ratio: float


@dataclass
class PerformanceAttribution:
    """Performance attribution breakdown."""

    strategy_pnl: Dict[str, Decimal]
    currency_pnl: Dict[str, Decimal]
    timeframe_pnl: Dict[str, Decimal]
    sector_allocation: Dict[str, float]
    top_performers: List[Dict[str, Any]]
    worst_performers: List[Dict[str, Any]]
    alpha: float
    beta: float
    information_ratio: float
    tracking_error: float


@dataclass
class RiskMetrics:
    """Comprehensive risk metrics."""

    portfolio_var: Decimal
    component_var: Dict[str, Decimal]
    expected_shortfall: Decimal
    maximum_drawdown: float
    current_drawdown: float
    volatility: float
    skewness: float
    kurtosis: float
    correlation_risk: float
    concentration_risk: float
    liquidity_risk: float
    stress_test_results: Dict[str, float]
    scenario_analysis: List[Dict[str, Any]]


@dataclass
class MarketIntelligence:
    """Market intelligence and analysis."""

    market_sentiment: str
    volatility_regime: str
    trend_strength: Dict[str, float]
    correlation_matrix: Dict[str, Dict[str, float]]
    economic_indicators: Dict[str, float]
    central_bank_calendar: List[Dict[str, Any]]
    market_news_sentiment: float
    technical_signals: Dict[str, str]
    support_resistance: Dict[str, List[float]]


class ExecutiveDashboard:
    """
    Executive Dashboard for comprehensive business intelligence.

    Provides high-level metrics, performance attribution, risk analysis,
    and market intelligence for executive decision-making.
    """

    def __init__(
        self, db_manager: DatabaseManager, portfolio_manager: PortfolioManager
    ):
        """Initialize executive dashboard."""
        self.db = db_manager
        self.portfolio = portfolio_manager
        self.logger = setup_logger(__name__)

        # Cache for expensive calculations
        self.metrics_cache = {}
        self.cache_timestamp = {}
        self.cache_ttl = 300  # 5 minutes

        # Performance tracking
        self.start_time = datetime.utcnow()
        self.query_count = 0
        self.total_query_time = 0.0

    async def get_executive_overview(
        self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get comprehensive executive overview.

        Args:
            start_date: Start date for analysis (default: 30 days ago)
            end_date: End date for analysis (default: now)

        Returns:
            Dict containing executive metrics, performance attribution,
            risk metrics, and market intelligence
        """
        try:
            if not start_date:
                start_date = datetime.utcnow() - timedelta(days=30)
            if not end_date:
                end_date = datetime.utcnow()

            self.logger.info(
                f"Generating executive overview from {start_date} to {end_date}"
            )

            # Get all components concurrently
            metrics_task = self.get_executive_metrics(start_date, end_date)
            attribution_task = self.get_performance_attribution(start_date, end_date)
            risk_task = self.get_risk_metrics(start_date, end_date)
            intelligence_task = self.get_market_intelligence()

            metrics, attribution, risk_metrics, market_intel = await asyncio.gather(
                metrics_task, attribution_task, risk_task, intelligence_task
            )

            return {
                "executive_metrics": asdict(metrics),
                "performance_attribution": asdict(attribution),
                "risk_metrics": asdict(risk_metrics),
                "market_intelligence": asdict(market_intel),
                "generated_at": datetime.utcnow().isoformat(),
                "period": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat(),
                },
            }

        except Exception as e:
            self.logger.error(f"Error generating executive overview: {e}")
            raise FXML4Exception(f"Failed to generate executive overview: {e}")

    async def get_executive_metrics(
        self, start_date: datetime, end_date: datetime
    ) -> ExecutiveMetrics:
        """Get executive-level performance metrics."""
        try:
            cache_key = f"exec_metrics_{start_date.date()}_{end_date.date()}"
            if self._is_cached(cache_key):
                return self.metrics_cache[cache_key]

            # Portfolio performance queries
            portfolio_query = """
            SELECT
                SUM(pnl) as total_pnl,
                SUM(CASE WHEN DATE(created_at) = CURRENT_DATE THEN pnl ELSE 0 END) as daily_pnl,
                SUM(CASE WHEN DATE(created_at) >= DATE_TRUNC('month', CURRENT_DATE) THEN pnl ELSE 0 END) as mtd_pnl,
                SUM(CASE WHEN DATE(created_at) >= DATE_TRUNC('year', CURRENT_DATE) THEN pnl ELSE 0 END) as ytd_pnl,
                COUNT(*) as total_trades,
                COUNT(CASE WHEN pnl > 0 THEN 1 END) as winning_trades,
                AVG(CASE WHEN pnl > 0 THEN pnl END) as avg_win,
                AVG(CASE WHEN pnl < 0 THEN pnl END) as avg_loss
            FROM trades
            WHERE created_at BETWEEN %s AND %s
            """

            portfolio_data = await self.db.fetch_one(
                portfolio_query, (start_date, end_date)
            )

            # Position and margin queries
            position_query = """
            SELECT
                COUNT(*) as active_positions,
                SUM(current_value) as portfolio_value,
                SUM(margin_used) as margin_used
            FROM positions
            WHERE status = 'active'
            """

            position_data = await self.db.fetch_one(position_query)

            # Risk metrics query
            risk_query = """
            SELECT
                portfolio_var,
                expected_shortfall,
                max_drawdown,
                current_drawdown,
                sharpe_ratio,
                sortino_ratio
            FROM risk_metrics
            WHERE date = CURRENT_DATE
            ORDER BY created_at DESC
            LIMIT 1
            """

            risk_data = await self.db.fetch_one(risk_query)

            # Calculate derived metrics
            win_rate = portfolio_data.get("winning_trades", 0) / max(
                portfolio_data.get("total_trades", 1), 1
            )

            profit_factor = abs(
                portfolio_data.get("avg_win", 0)
                * portfolio_data.get("winning_trades", 0)
                / max(
                    portfolio_data.get("avg_loss", 1)
                    * (
                        portfolio_data.get("total_trades", 0)
                        - portfolio_data.get("winning_trades", 0)
                    ),
                    1,
                )
            )

            calmar_ratio = portfolio_data.get("ytd_pnl", 0) / max(
                abs(risk_data.get("max_drawdown", 1)), 0.01
            )

            # Account information
            account_info = await self._get_account_info()

            metrics = ExecutiveMetrics(
                total_pnl=Decimal(str(portfolio_data.get("total_pnl", 0))),
                daily_pnl=Decimal(str(portfolio_data.get("daily_pnl", 0))),
                mtd_pnl=Decimal(str(portfolio_data.get("mtd_pnl", 0))),
                ytd_pnl=Decimal(str(portfolio_data.get("ytd_pnl", 0))),
                total_return=float(portfolio_data.get("ytd_pnl", 0))
                / 100000.0,  # Assuming 100k starting capital
                sharpe_ratio=float(risk_data.get("sharpe_ratio", 0)),
                sortino_ratio=float(risk_data.get("sortino_ratio", 0)),
                max_drawdown=float(risk_data.get("max_drawdown", 0)),
                current_drawdown=float(risk_data.get("current_drawdown", 0)),
                var_95=Decimal(str(risk_data.get("portfolio_var", 0))),
                expected_shortfall=Decimal(str(risk_data.get("expected_shortfall", 0))),
                active_positions=int(position_data.get("active_positions", 0)),
                total_trades=int(portfolio_data.get("total_trades", 0)),
                win_rate=win_rate,
                avg_win=Decimal(str(portfolio_data.get("avg_win", 0))),
                avg_loss=Decimal(str(portfolio_data.get("avg_loss", 0))),
                profit_factor=profit_factor,
                calmar_ratio=calmar_ratio,
                portfolio_value=Decimal(str(position_data.get("portfolio_value", 0))),
                cash_available=Decimal(str(account_info.get("cash_available", 0))),
                margin_used=Decimal(str(position_data.get("margin_used", 0))),
                margin_available=Decimal(str(account_info.get("margin_available", 0))),
                leverage_ratio=float(account_info.get("leverage_ratio", 0)),
            )

            self._cache_result(cache_key, metrics)
            return metrics

        except Exception as e:
            self.logger.error(f"Error calculating executive metrics: {e}")
            raise FXML4Exception(f"Failed to calculate executive metrics: {e}")

    async def get_performance_attribution(
        self, start_date: datetime, end_date: datetime
    ) -> PerformanceAttribution:
        """Get detailed performance attribution analysis."""
        try:
            # Strategy performance breakdown
            strategy_query = """
            SELECT
                strategy,
                SUM(pnl) as strategy_pnl
            FROM trades
            WHERE created_at BETWEEN %s AND %s
            GROUP BY strategy
            ORDER BY strategy_pnl DESC
            """

            strategy_data = await self.db.fetch_all(
                strategy_query, (start_date, end_date)
            )
            strategy_pnl = {
                row["strategy"]: Decimal(str(row["strategy_pnl"]))
                for row in strategy_data
            }

            # Currency pair performance
            currency_query = """
            SELECT
                symbol,
                SUM(pnl) as currency_pnl
            FROM trades
            WHERE created_at BETWEEN %s AND %s
            GROUP BY symbol
            ORDER BY currency_pnl DESC
            """

            currency_data = await self.db.fetch_all(
                currency_query, (start_date, end_date)
            )
            currency_pnl = {
                row["symbol"]: Decimal(str(row["currency_pnl"]))
                for row in currency_data
            }

            # Timeframe analysis
            timeframe_query = """
            SELECT
                timeframe,
                SUM(pnl) as timeframe_pnl
            FROM trades
            WHERE created_at BETWEEN %s AND %s
            GROUP BY timeframe
            ORDER BY timeframe_pnl DESC
            """

            timeframe_data = await self.db.fetch_all(
                timeframe_query, (start_date, end_date)
            )
            timeframe_pnl = {
                row["timeframe"]: Decimal(str(row["timeframe_pnl"]))
                for row in timeframe_data
            }

            # Top and worst performers
            performers_query = """
            (SELECT
                symbol, strategy, timeframe,
                SUM(pnl) as total_pnl,
                COUNT(*) as trades,
                AVG(pnl) as avg_pnl
            FROM trades
            WHERE created_at BETWEEN %s AND %s
            GROUP BY symbol, strategy, timeframe
            ORDER BY total_pnl DESC
            LIMIT 10)
            UNION ALL
            (SELECT
                symbol, strategy, timeframe,
                SUM(pnl) as total_pnl,
                COUNT(*) as trades,
                AVG(pnl) as avg_pnl
            FROM trades
            WHERE created_at BETWEEN %s AND %s
            GROUP BY symbol, strategy, timeframe
            ORDER BY total_pnl ASC
            LIMIT 10)
            """

            performers_data = await self.db.fetch_all(
                performers_query, (start_date, end_date, start_date, end_date)
            )

            top_performers = [dict(row) for row in performers_data[:10]]
            worst_performers = [dict(row) for row in performers_data[10:]]

            # Sector allocation (for forex pairs)
            sector_allocation = await self._calculate_sector_allocation()

            # Risk-adjusted metrics
            alpha, beta, info_ratio, tracking_error = (
                await self._calculate_risk_adjusted_metrics(start_date, end_date)
            )

            return PerformanceAttribution(
                strategy_pnl=strategy_pnl,
                currency_pnl=currency_pnl,
                timeframe_pnl=timeframe_pnl,
                sector_allocation=sector_allocation,
                top_performers=top_performers,
                worst_performers=worst_performers,
                alpha=alpha,
                beta=beta,
                information_ratio=info_ratio,
                tracking_error=tracking_error,
            )

        except Exception as e:
            self.logger.error(f"Error calculating performance attribution: {e}")
            raise FXML4Exception(f"Failed to calculate performance attribution: {e}")

    async def get_risk_metrics(
        self, start_date: datetime, end_date: datetime
    ) -> RiskMetrics:
        """Get comprehensive risk metrics and analysis."""
        try:
            # Portfolio VaR and risk metrics
            risk_query = """
            SELECT
                portfolio_var,
                expected_shortfall,
                max_drawdown,
                current_drawdown,
                volatility,
                skewness,
                kurtosis
            FROM risk_metrics
            WHERE date BETWEEN %s AND %s
            ORDER BY date DESC
            LIMIT 1
            """

            risk_data = await self.db.fetch_one(risk_query, (start_date, end_date))

            # Component VaR by position
            component_var_query = """
            SELECT
                p.symbol,
                p.current_value * rm.position_var as component_var
            FROM positions p
            JOIN risk_metrics rm ON rm.symbol = p.symbol
            WHERE p.status = 'active'
            AND rm.date = CURRENT_DATE
            """

            component_data = await self.db.fetch_all(component_var_query)
            component_var = {
                row["symbol"]: Decimal(str(row["component_var"]))
                for row in component_data
            }

            # Stress test results
            stress_test_results = await self._run_stress_tests()

            # Scenario analysis
            scenario_analysis = await self._run_scenario_analysis()

            # Risk concentration metrics
            correlation_risk = await self._calculate_correlation_risk()
            concentration_risk = await self._calculate_concentration_risk()
            liquidity_risk = await self._calculate_liquidity_risk()

            return RiskMetrics(
                portfolio_var=Decimal(str(risk_data.get("portfolio_var", 0))),
                component_var=component_var,
                expected_shortfall=Decimal(str(risk_data.get("expected_shortfall", 0))),
                maximum_drawdown=float(risk_data.get("max_drawdown", 0)),
                current_drawdown=float(risk_data.get("current_drawdown", 0)),
                volatility=float(risk_data.get("volatility", 0)),
                skewness=float(risk_data.get("skewness", 0)),
                kurtosis=float(risk_data.get("kurtosis", 0)),
                correlation_risk=correlation_risk,
                concentration_risk=concentration_risk,
                liquidity_risk=liquidity_risk,
                stress_test_results=stress_test_results,
                scenario_analysis=scenario_analysis,
            )

        except Exception as e:
            self.logger.error(f"Error calculating risk metrics: {e}")
            raise FXML4Exception(f"Failed to calculate risk metrics: {e}")

    async def get_market_intelligence(self) -> MarketIntelligence:
        """Get comprehensive market intelligence and analysis."""
        try:
            # Market sentiment analysis
            sentiment_query = """
            SELECT
                AVG(sentiment_score) as avg_sentiment,
                volatility_regime,
                trend_strength
            FROM market_analysis
            WHERE date = CURRENT_DATE
            """

            sentiment_data = await self.db.fetch_one(sentiment_query)

            # Determine market sentiment
            avg_sentiment = sentiment_data.get("avg_sentiment", 0)
            if avg_sentiment > 0.3:
                market_sentiment = "Bullish"
            elif avg_sentiment < -0.3:
                market_sentiment = "Bearish"
            else:
                market_sentiment = "Neutral"

            # Correlation matrix for major pairs
            correlation_matrix = await self._calculate_correlation_matrix()

            # Economic indicators
            economic_indicators = await self._get_economic_indicators()

            # Central bank calendar
            central_bank_calendar = await self._get_central_bank_calendar()

            # Technical signals
            technical_signals = await self._get_technical_signals()

            # Support/resistance levels
            support_resistance = await self._get_support_resistance_levels()

            # Trend strength by currency pair
            trend_strength = await self._calculate_trend_strength()

            return MarketIntelligence(
                market_sentiment=market_sentiment,
                volatility_regime=sentiment_data.get("volatility_regime", "Normal"),
                trend_strength=trend_strength,
                correlation_matrix=correlation_matrix,
                economic_indicators=economic_indicators,
                central_bank_calendar=central_bank_calendar,
                market_news_sentiment=float(avg_sentiment),
                technical_signals=technical_signals,
                support_resistance=support_resistance,
            )

        except Exception as e:
            self.logger.error(f"Error getting market intelligence: {e}")
            raise FXML4Exception(f"Failed to get market intelligence: {e}")

    async def get_real_time_updates(self) -> Dict[str, Any]:
        """Get real-time dashboard updates."""
        try:
            # Current P&L
            current_pnl_query = """
            SELECT SUM(unrealized_pnl) as unrealized_pnl
            FROM positions
            WHERE status = 'active'
            """

            pnl_data = await self.db.fetch_one(current_pnl_query)

            # Active trades count
            active_trades_query = """
            SELECT COUNT(*) as active_trades
            FROM trades
            WHERE status = 'open'
            """

            trades_data = await self.db.fetch_one(active_trades_query)

            # Market status
            market_status = await self._get_market_status()

            # System health
            system_health = await self._get_system_health()

            return {
                "unrealized_pnl": float(pnl_data.get("unrealized_pnl", 0)),
                "active_trades": int(trades_data.get("active_trades", 0)),
                "market_status": market_status,
                "system_health": system_health,
                "last_update": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            self.logger.error(f"Error getting real-time updates: {e}")
            return {
                "error": f"Failed to get real-time updates: {e}",
                "last_update": datetime.utcnow().isoformat(),
            }

    # Helper methods
    async def _get_account_info(self) -> Dict[str, Any]:
        """Get account information."""
        try:
            account_query = """
            SELECT
                cash_balance as cash_available,
                margin_available,
                buying_power,
                net_liquidation_value
            FROM account_info
            ORDER BY updated_at DESC
            LIMIT 1
            """

            account_data = await self.db.fetch_one(account_query)

            leverage_ratio = (
                float(account_data.get("net_liquidation_value", 0))
                - float(account_data.get("cash_available", 0))
            ) / max(float(account_data.get("cash_available", 1)), 1)

            return {
                "cash_available": account_data.get("cash_available", 0),
                "margin_available": account_data.get("margin_available", 0),
                "leverage_ratio": leverage_ratio,
            }

        except Exception as e:
            self.logger.error(f"Error getting account info: {e}")
            return {"cash_available": 0, "margin_available": 0, "leverage_ratio": 0}

    async def _calculate_sector_allocation(self) -> Dict[str, float]:
        """Calculate sector allocation for forex pairs."""
        try:
            # Group currency pairs by region/sector
            allocation_query = """
            SELECT
                CASE
                    WHEN symbol LIKE '%USD%' THEN 'USD_Pairs'
                    WHEN symbol LIKE '%EUR%' THEN 'EUR_Pairs'
                    WHEN symbol LIKE '%GBP%' THEN 'GBP_Pairs'
                    WHEN symbol LIKE '%JPY%' THEN 'JPY_Pairs'
                    WHEN symbol LIKE '%CHF%' THEN 'CHF_Pairs'
                    WHEN symbol LIKE '%CAD%' THEN 'CAD_Pairs'
                    WHEN symbol LIKE '%AUD%' THEN 'AUD_Pairs'
                    WHEN symbol LIKE '%NZD%' THEN 'NZD_Pairs'
                    ELSE 'Other_Pairs'
                END as sector,
                SUM(ABS(current_value)) as sector_value
            FROM positions
            WHERE status = 'active'
            GROUP BY sector
            """

            sector_data = await self.db.fetch_all(allocation_query)
            total_value = sum(float(row["sector_value"]) for row in sector_data)

            if total_value > 0:
                return {
                    row["sector"]: float(row["sector_value"]) / total_value
                    for row in sector_data
                }
            else:
                return {}

        except Exception as e:
            self.logger.error(f"Error calculating sector allocation: {e}")
            return {}

    async def _calculate_risk_adjusted_metrics(
        self, start_date: datetime, end_date: datetime
    ) -> Tuple[float, float, float, float]:
        """Calculate alpha, beta, information ratio, and tracking error."""
        try:
            # Get portfolio returns
            portfolio_query = """
            SELECT
                DATE(created_at) as date,
                SUM(pnl) as daily_pnl
            FROM trades
            WHERE created_at BETWEEN %s AND %s
            GROUP BY DATE(created_at)
            ORDER BY date
            """

            portfolio_data = await self.db.fetch_all(
                portfolio_query, (start_date, end_date)
            )

            if len(portfolio_data) < 2:
                return 0.0, 1.0, 0.0, 0.0

            # Calculate portfolio returns
            portfolio_returns = [
                float(row["daily_pnl"]) / 100000.0 for row in portfolio_data
            ]  # Assuming 100k base

            # Mock benchmark returns (in real implementation, would use actual benchmark)
            benchmark_returns = [
                r * 0.8 + np.random.normal(0, 0.001) for r in portfolio_returns
            ]

            # Calculate metrics using numpy
            portfolio_returns = np.array(portfolio_returns)
            benchmark_returns = np.array(benchmark_returns)

            # Beta calculation
            covariance = np.cov(portfolio_returns, benchmark_returns)[0, 1]
            benchmark_variance = np.var(benchmark_returns)
            beta = covariance / max(benchmark_variance, 1e-6)

            # Alpha calculation
            portfolio_mean = np.mean(portfolio_returns)
            benchmark_mean = np.mean(benchmark_returns)
            alpha = portfolio_mean - beta * benchmark_mean

            # Information ratio and tracking error
            excess_returns = portfolio_returns - benchmark_returns
            tracking_error = np.std(excess_returns) * np.sqrt(252)  # Annualized
            information_ratio = np.mean(excess_returns) / max(
                np.std(excess_returns), 1e-6
            )

            return (
                float(alpha),
                float(beta),
                float(information_ratio),
                float(tracking_error),
            )

        except Exception as e:
            self.logger.error(f"Error calculating risk-adjusted metrics: {e}")
            return 0.0, 1.0, 0.0, 0.0

    async def _run_stress_tests(self) -> Dict[str, float]:
        """Run portfolio stress tests."""
        try:
            # Define stress test scenarios
            scenarios = {
                "Market_Crash": -0.20,
                "Currency_Crisis": -0.15,
                "Central_Bank_Shock": -0.10,
                "Liquidity_Crisis": -0.25,
                "Black_Swan": -0.30,
            }

            current_portfolio_query = """
            SELECT
                symbol,
                quantity,
                current_price,
                current_value
            FROM positions
            WHERE status = 'active'
            """

            positions = await self.db.fetch_all(current_portfolio_query)

            stress_results = {}
            for scenario, shock in scenarios.items():
                scenario_pnl = 0.0
                for position in positions:
                    shocked_value = float(position["current_value"]) * (1 + shock)
                    scenario_pnl += shocked_value - float(position["current_value"])

                stress_results[scenario] = scenario_pnl

            return stress_results

        except Exception as e:
            self.logger.error(f"Error running stress tests: {e}")
            return {}

    async def _run_scenario_analysis(self) -> List[Dict[str, Any]]:
        """Run comprehensive scenario analysis."""
        try:
            scenarios = [
                {
                    "name": "Bull Market",
                    "description": "Strong economic growth, low volatility",
                    "probability": 0.25,
                    "expected_return": 0.15,
                    "volatility": 0.12,
                },
                {
                    "name": "Bear Market",
                    "description": "Economic recession, high volatility",
                    "probability": 0.20,
                    "expected_return": -0.10,
                    "volatility": 0.25,
                },
                {
                    "name": "Sideways Market",
                    "description": "Range-bound market, moderate volatility",
                    "probability": 0.40,
                    "expected_return": 0.03,
                    "volatility": 0.15,
                },
                {
                    "name": "High Volatility",
                    "description": "Increased market uncertainty",
                    "probability": 0.15,
                    "expected_return": 0.05,
                    "volatility": 0.30,
                },
            ]

            return scenarios

        except Exception as e:
            self.logger.error(f"Error running scenario analysis: {e}")
            return []

    async def _calculate_correlation_risk(self) -> float:
        """Calculate portfolio correlation risk."""
        try:
            # Get active positions
            positions_query = """
            SELECT symbol, current_value
            FROM positions
            WHERE status = 'active'
            """

            positions = await self.db.fetch_all(positions_query)

            if len(positions) < 2:
                return 0.0

            # Mock correlation calculation (in real implementation, use actual correlations)
            # Removed unused total_value variable

            # Simple correlation risk approximation
            correlation_risk = min(0.8, len(positions) / 10.0)

            return correlation_risk

        except Exception as e:
            self.logger.error(f"Error calculating correlation risk: {e}")
            return 0.0

    async def _calculate_concentration_risk(self) -> float:
        """Calculate portfolio concentration risk."""
        try:
            positions_query = """
            SELECT
                symbol,
                ABS(current_value) as abs_value
            FROM positions
            WHERE status = 'active'
            ORDER BY abs_value DESC
            """

            positions = await self.db.fetch_all(positions_query)

            if not positions:
                return 0.0

            total_value = sum(float(pos["abs_value"]) for pos in positions)

            if total_value == 0:
                return 0.0

            # Calculate Herfindahl-Hirschman Index for concentration
            hhi = sum((float(pos["abs_value"]) / total_value) ** 2 for pos in positions)

            # Normalize to 0-1 scale where 1 is maximum concentration
            concentration_risk = min(1.0, hhi * len(positions))

            return concentration_risk

        except Exception as e:
            self.logger.error(f"Error calculating concentration risk: {e}")
            return 0.0

    async def _calculate_liquidity_risk(self) -> float:
        """Calculate portfolio liquidity risk."""
        try:
            # Mock liquidity risk calculation
            # In real implementation, would use actual bid-ask spreads and volume data

            positions_query = """
            SELECT COUNT(*) as position_count
            FROM positions
            WHERE status = 'active'
            """

            position_data = await self.db.fetch_one(positions_query)
            position_count = int(position_data.get("position_count", 0))

            # Simple liquidity risk approximation
            # More positions generally means better liquidity
            if position_count == 0:
                return 1.0
            elif position_count < 3:
                return 0.8
            elif position_count < 5:
                return 0.5
            else:
                return 0.2

        except Exception as e:
            self.logger.error(f"Error calculating liquidity risk: {e}")
            return 0.5

    async def _calculate_correlation_matrix(self) -> Dict[str, Dict[str, float]]:
        """Calculate correlation matrix for major currency pairs."""
        try:
            # Mock correlation data (in real implementation, calculate from price data)
            major_pairs = [
                "EUR/USD",
                "GBP/USD",
                "USD/JPY",
                "USD/CHF",
                "AUD/USD",
                "USD/CAD",
            ]

            correlation_matrix = {}
            for pair1 in major_pairs:
                correlation_matrix[pair1] = {}
                for pair2 in major_pairs:
                    if pair1 == pair2:
                        correlation_matrix[pair1][pair2] = 1.0
                    else:
                        # Mock correlation (in real implementation, calculate from historical data)
                        correlation_matrix[pair1][pair2] = np.random.uniform(-0.8, 0.8)

            return correlation_matrix

        except Exception as e:
            self.logger.error(f"Error calculating correlation matrix: {e}")
            return {}

    async def _get_economic_indicators(self) -> Dict[str, float]:
        """Get key economic indicators."""
        try:
            # Mock economic indicators (in real implementation, fetch from economic data API)
            indicators = {
                "USD_Interest_Rate": 5.25,
                "EUR_Interest_Rate": 4.50,
                "GBP_Interest_Rate": 5.00,
                "JPY_Interest_Rate": -0.10,
                "US_Unemployment": 3.7,
                "EUR_Inflation": 2.8,
                "US_GDP_Growth": 2.1,
                "EUR_GDP_Growth": 0.8,
            }

            return indicators

        except Exception as e:
            self.logger.error(f"Error getting economic indicators: {e}")
            return {}

    async def _get_central_bank_calendar(self) -> List[Dict[str, Any]]:
        """Get upcoming central bank events."""
        try:
            # Mock central bank calendar (in real implementation, fetch from economic calendar API)
            events = [
                {
                    "date": (datetime.utcnow() + timedelta(days=2)).strftime(
                        "%Y-%m-%d"
                    ),
                    "time": "14:00",
                    "bank": "Federal Reserve",
                    "event": "FOMC Meeting Minutes",
                    "importance": "High",
                    "currency": "USD",
                },
                {
                    "date": (datetime.utcnow() + timedelta(days=5)).strftime(
                        "%Y-%m-%d"
                    ),
                    "time": "12:45",
                    "bank": "European Central Bank",
                    "event": "Interest Rate Decision",
                    "importance": "High",
                    "currency": "EUR",
                },
                {
                    "date": (datetime.utcnow() + timedelta(days=7)).strftime(
                        "%Y-%m-%d"
                    ),
                    "time": "03:00",
                    "bank": "Bank of Japan",
                    "event": "Monetary Policy Statement",
                    "importance": "Medium",
                    "currency": "JPY",
                },
            ]

            return events

        except Exception as e:
            self.logger.error(f"Error getting central bank calendar: {e}")
            return []

    async def _get_technical_signals(self) -> Dict[str, str]:
        """Get technical analysis signals for major pairs."""
        try:
            # Mock technical signals (in real implementation, calculate from price data)
            signals = {
                "EUR/USD": "Buy",
                "GBP/USD": "Sell",
                "USD/JPY": "Hold",
                "USD/CHF": "Buy",
                "AUD/USD": "Sell",
                "USD/CAD": "Hold",
            }

            return signals

        except Exception as e:
            self.logger.error(f"Error getting technical signals: {e}")
            return {}

    async def _get_support_resistance_levels(self) -> Dict[str, List[float]]:
        """Get support and resistance levels for major pairs."""
        try:
            # Mock support/resistance levels (in real implementation, calculate from price data)
            levels = {
                "EUR/USD": [1.0850, 1.0920, 1.0980, 1.1050],
                "GBP/USD": [1.2650, 1.2720, 1.2800, 1.2880],
                "USD/JPY": [148.50, 149.20, 150.00, 150.80],
                "USD/CHF": [0.8850, 0.8920, 0.9000, 0.9080],
            }

            return levels

        except Exception as e:
            self.logger.error(f"Error getting support/resistance levels: {e}")
            return {}

    async def _calculate_trend_strength(self) -> Dict[str, float]:
        """Calculate trend strength for major currency pairs."""
        try:
            # Mock trend strength calculation (in real implementation, use technical indicators)
            pairs = ["EUR/USD", "GBP/USD", "USD/JPY", "USD/CHF", "AUD/USD", "USD/CAD"]

            trend_strength = {}
            for pair in pairs:
                # Random trend strength between -1 (strong downtrend) and 1 (strong uptrend)
                trend_strength[pair] = np.random.uniform(-1.0, 1.0)

            return trend_strength

        except Exception as e:
            self.logger.error(f"Error calculating trend strength: {e}")
            return {}

    async def _get_market_status(self) -> Dict[str, str]:
        """Get current market status."""
        try:
            # Mock market status (in real implementation, check actual market hours)
            current_hour = datetime.utcnow().hour

            if 7 <= current_hour <= 21:  # Simplified forex market hours
                status = "Open"
            else:
                status = "Closed"

            return {
                "forex": status,
                "session": (
                    "London"
                    if 8 <= current_hour <= 17
                    else (
                        "Asian"
                        if 23 <= current_hour or current_hour <= 7
                        else "New York"
                    )
                ),
            }

        except Exception as e:
            self.logger.error(f"Error getting market status: {e}")
            return {"forex": "Unknown", "session": "Unknown"}

    async def _get_system_health(self) -> Dict[str, Any]:
        """Get system health metrics."""
        try:
            # Mock system health (in real implementation, check actual system metrics)
            return {
                "status": "Healthy",
                "uptime": str(datetime.utcnow() - self.start_time),
                "cpu_usage": 45.2,
                "memory_usage": 62.8,
                "database_connections": 15,
                "api_response_time": 120,
                "last_health_check": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            self.logger.error(f"Error getting system health: {e}")
            return {"status": "Unknown", "error": str(e)}

    def _is_cached(self, cache_key: str) -> bool:
        """Check if result is cached and still valid."""
        if cache_key not in self.metrics_cache:
            return False

        if cache_key not in self.cache_timestamp:
            return False

        cache_age = (
            datetime.utcnow() - self.cache_timestamp[cache_key]
        ).total_seconds()
        return cache_age < self.cache_ttl

    def _cache_result(self, cache_key: str, result: Any) -> None:
        """Cache a result with timestamp."""
        self.metrics_cache[cache_key] = result
        self.cache_timestamp[cache_key] = datetime.utcnow()

        # Clean old cache entries
        current_time = datetime.utcnow()
        keys_to_remove = [
            key
            for key, timestamp in self.cache_timestamp.items()
            if (current_time - timestamp).total_seconds() > self.cache_ttl * 2
        ]

        for key in keys_to_remove:
            self.metrics_cache.pop(key, None)
            self.cache_timestamp.pop(key, None)

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get dashboard performance metrics."""
        uptime = datetime.utcnow() - self.start_time
        avg_query_time = self.total_query_time / max(self.query_count, 1)

        return {
            "uptime_seconds": uptime.total_seconds(),
            "total_queries": self.query_count,
            "average_query_time": avg_query_time,
            "cache_hit_ratio": len(self.metrics_cache) / max(self.query_count, 1),
            "cache_size": len(self.metrics_cache),
        }
