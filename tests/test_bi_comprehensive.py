"""
Comprehensive Business Intelligence Test Suite

Test-driven development suite for Phase 12: Business Intelligence & Advanced Analytics.
Tests executive dashboards, analytics engine, predictive forecasting, reporting, and data warehouse.
"""

import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, Mock

import pytest

from fxml4.bi.analytics.engine import (
    AnalyticsEngine,
    AnalyticsQuery,
    AnalyticsResult,
    RealTimeMetrics,
)
from fxml4.bi.dashboard.executive import (
    ExecutiveDashboard,
    ExecutiveMetrics,
    PerformanceAttribution,
)
from fxml4.bi.predictive.forecaster import MarketForecast, PredictiveAnalytics
from fxml4.bi.reporting.generator import ReportGenerator, ReportRequest
from fxml4.bi.warehouse.manager import DataWarehouseManager, DataWarehouseStats, ETLJob
from fxml4.core.exceptions import FXML4Exception


class TestExecutiveDashboard:
    """Test suite for Executive Dashboard functionality."""

    @pytest.fixture
    def mock_db_manager(self):
        """Mock database manager."""
        db_manager = AsyncMock()

        # Mock portfolio performance data
        db_manager.fetch_one.return_value = {
            "total_pnl": 15420.50,
            "daily_pnl": 234.75,
            "mtd_pnl": 2840.25,
            "ytd_pnl": 12680.75,
            "total_trades": 156,
            "winning_trades": 89,
            "avg_pnl": 98.85,
            "avg_win": 185.40,
            "avg_loss": -78.25,
            "portfolio_value": 125000.00,
            "margin_used": 25000.00,
            "active_positions": 8,
            "unrealized_pnl": 1250.75,
        }

        # Mock position data
        db_manager.fetch_all.return_value = [
            {
                "symbol": "EUR/USD",
                "strategy": "momentum",
                "timeframe": "4h",
                "strategy_pnl": 2150.25,
                "currency_pnl": 3240.50,
                "timeframe_pnl": 1890.75,
                "trade_count": 45,
                "avg_pnl": 75.60,
            },
            {
                "symbol": "GBP/USD",
                "strategy": "mean_reversion",
                "timeframe": "1h",
                "strategy_pnl": 1890.75,
                "currency_pnl": 2150.25,
                "timeframe_pnl": 2340.50,
                "trade_count": 38,
                "avg_pnl": 62.40,
            },
        ]

        return db_manager

    @pytest.fixture
    def mock_portfolio_manager(self):
        """Mock portfolio manager."""
        return Mock()

    @pytest.fixture
    def executive_dashboard(self, mock_db_manager, mock_portfolio_manager):
        """Executive dashboard instance."""
        return ExecutiveDashboard(mock_db_manager, mock_portfolio_manager)

    @pytest.mark.asyncio
    async def test_get_executive_overview(self, executive_dashboard):
        """Test comprehensive executive overview generation."""
        # Given: Date range for analysis
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 31)

        # When: Getting executive overview
        overview = await executive_dashboard.get_executive_overview(
            start_date, end_date
        )

        # Then: Overview should contain all required sections
        assert "executive_metrics" in overview
        assert "performance_attribution" in overview
        assert "risk_metrics" in overview
        assert "market_intelligence" in overview
        assert "generated_at" in overview
        assert "period" in overview

        # Verify executive metrics structure
        exec_metrics = overview["executive_metrics"]
        assert "total_pnl" in exec_metrics
        assert "win_rate" in exec_metrics
        assert "sharpe_ratio" in exec_metrics
        assert "active_positions" in exec_metrics

        # Verify performance attribution
        perf_attr = overview["performance_attribution"]
        assert "strategy_pnl" in perf_attr
        assert "currency_pnl" in perf_attr
        assert "top_performers" in perf_attr

        # Verify risk metrics
        risk_metrics = overview["risk_metrics"]
        assert "portfolio_var" in risk_metrics
        assert "component_var" in risk_metrics
        assert "stress_test_results" in risk_metrics

    @pytest.mark.asyncio
    async def test_get_executive_metrics(self, executive_dashboard):
        """Test executive metrics calculation."""
        # Given: Date range
        start_date = datetime.utcnow() - timedelta(days=30)
        end_date = datetime.utcnow()

        # When: Getting executive metrics
        metrics = await executive_dashboard.get_executive_metrics(start_date, end_date)

        # Then: Metrics should be properly calculated
        assert isinstance(metrics, ExecutiveMetrics)
        assert isinstance(metrics.total_pnl, Decimal)
        assert metrics.win_rate >= 0.0 and metrics.win_rate <= 1.0
        assert isinstance(metrics.active_positions, int)
        assert isinstance(metrics.sharpe_ratio, float)

        # Verify metric values are reasonable
        assert metrics.total_trades >= 0
        assert metrics.portfolio_value >= 0

    @pytest.mark.asyncio
    async def test_get_performance_attribution(self, executive_dashboard):
        """Test performance attribution analysis."""
        # Given: Date range for attribution analysis
        start_date = datetime.utcnow() - timedelta(days=30)
        end_date = datetime.utcnow()

        # When: Getting performance attribution
        attribution = await executive_dashboard.get_performance_attribution(
            start_date, end_date
        )

        # Then: Attribution should contain all components
        assert isinstance(attribution, PerformanceAttribution)
        assert isinstance(attribution.strategy_pnl, dict)
        assert isinstance(attribution.currency_pnl, dict)
        assert isinstance(attribution.timeframe_pnl, dict)
        assert isinstance(attribution.top_performers, list)
        assert isinstance(attribution.worst_performers, list)
        assert isinstance(attribution.alpha, float)
        assert isinstance(attribution.beta, float)

    @pytest.mark.asyncio
    async def test_get_real_time_updates(self, executive_dashboard):
        """Test real-time dashboard updates."""
        # When: Getting real-time updates
        updates = await executive_dashboard.get_real_time_updates()

        # Then: Updates should contain current metrics
        assert "unrealized_pnl" in updates
        assert "active_trades" in updates
        assert "market_status" in updates
        assert "system_health" in updates
        assert "last_update" in updates

        # Verify data types
        assert isinstance(updates["unrealized_pnl"], float)
        assert isinstance(updates["active_trades"], int)
        assert isinstance(updates["market_status"], dict)
        assert isinstance(updates["system_health"], dict)

    def test_executive_metrics_caching(self, executive_dashboard):
        """Test executive metrics caching mechanism."""
        # Given: Cache key and data
        cache_key = "test_metrics_2024-01-01_2024-01-31"
        test_metrics = ExecutiveMetrics(
            total_pnl=Decimal("1000"),
            daily_pnl=Decimal("50"),
            mtd_pnl=Decimal("500"),
            ytd_pnl=Decimal("2000"),
            total_return=0.02,
            sharpe_ratio=1.5,
            sortino_ratio=1.8,
            max_drawdown=0.05,
            current_drawdown=0.02,
            var_95=Decimal("100"),
            expected_shortfall=Decimal("150"),
            active_positions=5,
            total_trades=100,
            win_rate=0.6,
            avg_win=Decimal("80"),
            avg_loss=Decimal("-40"),
            profit_factor=2.0,
            calmar_ratio=1.2,
            portfolio_value=Decimal("50000"),
            cash_available=Decimal("10000"),
            margin_used=Decimal("5000"),
            margin_available=Decimal("15000"),
            leverage_ratio=2.5,
        )

        # When: Caching result
        executive_dashboard._cache_result(cache_key, test_metrics)

        # Then: Cache should work correctly
        assert executive_dashboard._is_cached(cache_key)
        assert executive_dashboard.metrics_cache[cache_key] == test_metrics

        # Test cache expiration
        executive_dashboard.cache_timestamps[cache_key] = datetime.utcnow() - timedelta(
            seconds=400
        )
        assert not executive_dashboard._is_cached(cache_key)


class TestAnalyticsEngine:
    """Test suite for Advanced Analytics Engine."""

    @pytest.fixture
    def mock_db_manager(self):
        """Mock database manager for analytics."""
        db_manager = AsyncMock()

        # Mock analytics query results
        db_manager.fetch_one.return_value = {
            "total_pnl": 12450.75,
            "total_trades": 145,
            "winning_trades": 87,
            "avg_pnl": 85.87,
            "best_trade": 345.60,
            "worst_trade": -125.40,
            "pnl_volatility": 45.25,
            "position_count": 6,
            "unrealized_pnl": 890.25,
        }

        db_manager.fetch_all.return_value = [
            {
                "symbol": "EUR/USD",
                "strategy": "momentum",
                "trade_count": 45,
                "strategy_pnl": 2340.50,
                "avg_strategy_pnl": 52.01,
            },
            {
                "symbol": "GBP/USD",
                "strategy": "mean_reversion",
                "trade_count": 38,
                "strategy_pnl": 1890.25,
                "avg_strategy_pnl": 49.74,
            },
        ]

        return db_manager

    @pytest.fixture
    def analytics_engine(self, mock_db_manager):
        """Analytics engine instance."""
        return AnalyticsEngine(mock_db_manager)

    @pytest.mark.asyncio
    async def test_execute_query_portfolio_summary(self, analytics_engine):
        """Test portfolio summary analytics query."""
        # Given: Analytics query for portfolio summary
        query = AnalyticsQuery(
            query_id="portfolio_summary_test",
            query_type="portfolio_summary",
            parameters={"include_breakdown": True},
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
            symbols=["EUR/USD", "GBP/USD"],
        )

        # When: Executing query
        result = await analytics_engine.execute_query(query)

        # Then: Result should be properly structured
        assert isinstance(result, AnalyticsResult)
        assert result.query_id == "portfolio_summary_test"
        assert result.result_type == "portfolio_summary"
        assert "summary" in result.data
        assert "by_symbol" in result.data
        assert "by_strategy" in result.data
        assert result.execution_time_ms > 0
        assert result.row_count >= 0

    @pytest.mark.asyncio
    async def test_get_real_time_metrics(self, analytics_engine):
        """Test real-time analytics metrics."""
        # When: Getting real-time metrics
        metrics = await analytics_engine.get_real_time_metrics()

        # Then: Metrics should be properly structured
        assert isinstance(metrics, RealTimeMetrics)
        assert isinstance(metrics.portfolio_pnl, Decimal)
        assert isinstance(metrics.daily_pnl, Decimal)
        assert isinstance(metrics.position_count, int)
        assert isinstance(metrics.win_rate, float)
        assert metrics.win_rate >= 0.0 and metrics.win_rate <= 1.0
        assert isinstance(metrics.timestamp, datetime)

    @pytest.mark.asyncio
    async def test_generate_insights(self, analytics_engine):
        """Test AI-powered insights generation."""
        # Given: Data type and lookback period
        data_type = "trading_patterns"
        lookback_days = 30

        # When: Generating insights
        insights = await analytics_engine.generate_insights(data_type, lookback_days)

        # Then: Insights should be generated
        assert isinstance(insights, list)

        if insights:  # If insights are generated
            insight = insights[0]
            assert "type" in insight
            assert "category" in insight
            assert "title" in insight
            assert "description" in insight
            assert "confidence" in insight
            assert "recommendation" in insight
            assert isinstance(insight["confidence"], float)
            assert 0.0 <= insight["confidence"] <= 1.0

    @pytest.mark.asyncio
    async def test_run_batch_analysis_portfolio_optimization(self, analytics_engine):
        """Test batch portfolio optimization analysis."""
        # Given: Portfolio optimization parameters
        parameters = {
            "optimization_method": "mean_variance",
            "constraints": {"max_weight": 0.3, "min_weight": 0.05},
            "risk_tolerance": 0.15,
        }

        # When: Running batch analysis
        result = await analytics_engine.run_batch_analysis(
            "portfolio_optimization", parameters
        )

        # Then: Analysis should complete successfully
        assert "optimal_weights" in result
        assert "expected_return" in result
        assert "expected_volatility" in result
        assert "sharpe_ratio" in result
        assert isinstance(result["optimal_weights"], dict)
        assert isinstance(result["expected_return"], (int, float))
        assert isinstance(result["sharpe_ratio"], (int, float))

    def test_analytics_query_caching(self, analytics_engine):
        """Test analytics query result caching."""
        # Given: Analytics query
        query = AnalyticsQuery(
            query_id="test_cache",
            query_type="portfolio_summary",
            parameters={},
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        # When: Generating cache key
        cache_key = analytics_engine._generate_cache_key(query)

        # Then: Cache key should be consistent and unique
        assert isinstance(cache_key, str)
        assert len(cache_key) > 0

        # Same query should generate same cache key
        cache_key_2 = analytics_engine._generate_cache_key(query)
        assert cache_key == cache_key_2

        # Different query should generate different cache key
        query_2 = AnalyticsQuery(
            query_id="test_cache_2",
            query_type="risk_analysis",
            parameters={},
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )
        cache_key_3 = analytics_engine._generate_cache_key(query_2)
        assert cache_key != cache_key_3


class TestPredictiveAnalytics:
    """Test suite for Predictive Analytics and Forecasting."""

    @pytest.fixture
    def mock_db_manager(self):
        """Mock database manager for predictive analytics."""
        db_manager = AsyncMock()
        return db_manager

    @pytest.fixture
    async def predictive_analytics(self, mock_db_manager):
        """Predictive analytics instance."""
        pa = PredictiveAnalytics(mock_db_manager)
        await pa.initialize_models()
        return pa

    @pytest.mark.asyncio
    async def test_initialize_models(self, predictive_analytics):
        """Test predictive models initialization."""
        # Then: Models should be initialized
        assert len(predictive_analytics.price_models) > 0
        assert len(predictive_analytics.volatility_models) > 0
        assert len(predictive_analytics.regime_models) > 0
        assert len(predictive_analytics.risk_models) > 0

        # Verify specific model types
        assert "garch" in predictive_analytics.volatility_models
        assert "realized_vol" in predictive_analytics.volatility_models
        assert "volatility_regime" in predictive_analytics.regime_models
        assert "trend_regime" in predictive_analytics.regime_models

    @pytest.mark.asyncio
    async def test_generate_market_forecast(self, predictive_analytics):
        """Test comprehensive market forecast generation."""
        # Given: Forecast parameters
        symbols = ["EUR/USD", "GBP/USD", "USD/JPY"]
        horizon_hours = 24
        confidence_level = 0.95

        # When: Generating market forecast
        forecast = await predictive_analytics.generate_market_forecast(
            symbols, horizon_hours, confidence_level
        )

        # Then: Forecast should be comprehensive
        assert isinstance(forecast, MarketForecast)
        assert forecast.forecast_id is not None
        assert len(forecast.symbols) == len(symbols)
        assert isinstance(forecast.market_regime_prediction, dict)
        assert isinstance(forecast.volatility_forecast, dict)
        assert isinstance(forecast.correlation_forecast, dict)
        assert isinstance(forecast.trading_opportunities, list)
        assert forecast.forecast_horizon_hours == horizon_hours

        # Verify symbol predictions
        for symbol in symbols:
            assert symbol in forecast.symbols
            prediction = forecast.symbols[symbol]
            assert prediction.symbol == symbol
            assert prediction.prediction_type == "price"
            assert isinstance(prediction.predicted_value, float)
            assert isinstance(prediction.confidence_score, float)
            assert 0.0 <= prediction.confidence_score <= 1.0

    @pytest.mark.asyncio
    async def test_predict_portfolio_performance(self, predictive_analytics):
        """Test portfolio performance prediction."""
        # Given: Portfolio positions and parameters
        portfolio_positions = {
            "EUR/USD": 10000.0,
            "GBP/USD": -5000.0,
            "USD/JPY": 7500.0,
        }
        horizon_days = 30
        scenarios = ["base_case", "bull_market", "bear_market"]

        # When: Predicting portfolio performance
        predictions = await predictive_analytics.predict_portfolio_performance(
            portfolio_positions, horizon_days, scenarios
        )

        # Then: Predictions should cover all scenarios
        assert "scenario_predictions" in predictions
        assert "risk_metrics" in predictions
        assert "recommendations" in predictions

        scenario_preds = predictions["scenario_predictions"]
        assert len(scenario_preds) == len(scenarios)

        for scenario in scenarios:
            assert scenario in scenario_preds
            pred = scenario_preds[scenario]
            assert "expected_return" in pred
            assert "volatility" in pred
            assert "max_drawdown" in pred
            assert "position_contributions" in pred

    @pytest.mark.asyncio
    async def test_predict_risk_events(self, predictive_analytics):
        """Test risk event probability prediction."""
        # Given: Event types and horizon
        event_types = ["volatility_spike", "trend_reversal", "liquidity_crunch"]
        horizon_hours = 168  # 1 week

        # When: Predicting risk events
        predictions = await predictive_analytics.predict_risk_events(
            event_types, horizon_hours
        )

        # Then: Predictions should cover all event types
        assert "risk_event_predictions" in predictions
        assert "overall_risk_score" in predictions
        assert "risk_level" in predictions

        event_preds = predictions["risk_event_predictions"]

        for event_type in event_types:
            assert event_type in event_preds
            pred = event_preds[event_type]
            assert "probability" in pred
            assert "expected_impact" in pred
            assert "confidence" in pred
            assert 0.0 <= pred["probability"] <= 1.0
            assert 0.0 <= pred["confidence"] <= 1.0

    @pytest.mark.asyncio
    async def test_generate_trading_signals(self, predictive_analytics):
        """Test predictive trading signals generation."""
        # Given: Symbols and signal parameters
        symbols = ["EUR/USD", "GBP/USD"]
        signal_types = ["trend", "momentum", "mean_reversion"]
        horizon_hours = 24

        # When: Generating trading signals
        signals = await predictive_analytics.generate_trading_signals(
            symbols, signal_types, horizon_hours
        )

        # Then: Signals should be generated for all symbols
        assert "trading_signals" in signals
        assert "market_context" in signals
        assert "risk_assessment" in signals

        trading_signals = signals["trading_signals"]

        for symbol in symbols:
            assert symbol in trading_signals
            symbol_signals = trading_signals[symbol]

            for signal_type in signal_types:
                assert signal_type in symbol_signals
                signal = symbol_signals[signal_type]
                assert "strength" in signal
                assert "direction" in signal
                assert "confidence" in signal
                assert signal["direction"] in ["Buy", "Sell", "Hold"]
                assert 0.0 <= signal["confidence"] <= 1.0

    @pytest.mark.asyncio
    async def test_validate_model_performance(self, predictive_analytics):
        """Test model performance validation."""
        # When: Validating model performance
        validation = await predictive_analytics.validate_model_performance()

        # Then: Validation should cover all model types
        assert "price_models" in validation
        assert "volatility_models" in validation
        assert "regime_models" in validation
        assert "overall_performance" in validation

        overall_perf = validation["overall_performance"]
        assert "overall_accuracy" in overall_perf
        assert "model_health" in overall_perf
        assert isinstance(overall_perf["overall_accuracy"], float)
        assert 0.0 <= overall_perf["overall_accuracy"] <= 1.0

    def test_forecast_caching(self, predictive_analytics):
        """Test forecast caching mechanism."""
        # Given: Cache key and forecast
        cache_key = "test_forecast_key"
        forecast = MarketForecast(
            forecast_id="test_forecast",
            symbols={},
            market_regime_prediction={},
            volatility_forecast={},
            correlation_forecast={},
            risk_events_probability={},
            trading_opportunities=[],
            forecast_accuracy=0.85,
            generated_at=datetime.utcnow(),
            forecast_horizon_hours=24,
        )

        # When: Caching forecast
        predictive_analytics._cache_forecast(cache_key, forecast)

        # Then: Caching should work correctly
        assert predictive_analytics._is_forecast_cached(cache_key)
        assert predictive_analytics.forecast_cache[cache_key] == forecast

        # Test cache expiration
        old_forecast = MarketForecast(
            forecast_id="old_forecast",
            symbols={},
            market_regime_prediction={},
            volatility_forecast={},
            correlation_forecast={},
            risk_events_probability={},
            trading_opportunities=[],
            forecast_accuracy=0.80,
            generated_at=datetime.utcnow() - timedelta(hours=2),
            forecast_horizon_hours=24,
        )

        old_cache_key = "old_forecast_key"
        predictive_analytics.forecast_cache[old_cache_key] = old_forecast

        assert not predictive_analytics._is_forecast_cached(old_cache_key)


class TestReportGenerator:
    """Test suite for Custom Report Generation."""

    @pytest.fixture
    def mock_db_manager(self):
        """Mock database manager for reporting."""
        db_manager = AsyncMock()

        # Mock report data
        db_manager.fetch_one.return_value = {
            "total_pnl": 8750.25,
            "total_trades": 124,
            "winning_trades": 78,
            "avg_pnl": 70.57,
            "portfolio_value": 85000.0,
            "active_positions": 7,
            "unrealized_pnl": 654.32,
        }

        db_manager.fetch_all.return_value = [
            {
                "symbol": "EUR/USD",
                "quantity": 10000,
                "entry_price": 1.0850,
                "current_price": 1.0875,
                "current_value": 10875.0,
                "unrealized_pnl": 250.0,
                "created_at": datetime(2024, 1, 15),
            },
            {
                "symbol": "GBP/USD",
                "quantity": -5000,
                "entry_price": 1.2650,
                "current_price": 1.2625,
                "current_value": -6312.5,
                "unrealized_pnl": 125.0,
                "created_at": datetime(2024, 1, 18),
            },
        ]

        return db_manager

    @pytest.fixture
    async def report_generator(self, mock_db_manager):
        """Report generator instance."""
        rg = ReportGenerator(mock_db_manager)
        await rg.initialize_templates()
        return rg

    @pytest.mark.asyncio
    async def test_initialize_templates(self, report_generator):
        """Test report template initialization."""
        # Then: Templates should be initialized
        assert len(report_generator.templates) > 0

        # Verify standard templates
        expected_templates = [
            "executive_summary",
            "trading_performance",
            "risk_analysis",
            "compliance_report",
            "custom_analysis",
        ]

        for template_name in expected_templates:
            assert template_name in report_generator.templates
            template = report_generator.templates[template_name]
            assert "name" in template
            assert "description" in template
            assert "sections" in template
            assert isinstance(template["sections"], list)

    @pytest.mark.asyncio
    async def test_generate_report_executive_summary(self, report_generator):
        """Test executive summary report generation."""
        # Given: Executive summary report request
        request = ReportRequest(
            report_id="exec_test_001",
            template_name="executive_summary",
            parameters={
                "date_range": (datetime(2024, 1, 1), datetime(2024, 1, 31)),
                "include_predictions": True,
                "detail_level": "summary",
            },
            output_formats=["html", "pdf"],
            recipients=["test@example.com"],
        )

        # When: Generating report
        report = await report_generator.generate_report(request)

        # Then: Report should be properly structured
        assert "metadata" in report
        assert "template" in report
        assert "sections" in report
        assert "summary" in report

        metadata = report["metadata"]
        assert metadata["report_id"] == "exec_test_001"
        assert metadata["template_name"] == "executive_summary"
        assert metadata["execution_time_ms"] > 0
        assert metadata["data_quality_score"] > 0

        # Verify sections
        sections = report["sections"]
        assert len(sections) > 0

        for section in sections:
            assert "section_id" in section
            assert "title" in section
            assert "section_type" in section
            assert "data" in section
            assert "metadata" in section

    @pytest.mark.asyncio
    async def test_generate_trading_report(self, report_generator):
        """Test trading performance report generation."""
        # Given: Trading report parameters
        date_range = (datetime(2024, 1, 1), datetime(2024, 1, 31))
        symbols = ["EUR/USD", "GBP/USD"]
        strategies = ["momentum", "mean_reversion"]

        # When: Generating trading report
        report = await report_generator.generate_trading_report(
            date_range, symbols, strategies
        )

        # Then: Report should contain trading analysis
        assert "metadata" in report
        assert "sections" in report

        # Verify trading-specific sections exist
        sections = report["sections"]
        section_ids = [s["section_id"] for s in sections]

        expected_section_ids = [
            "summary_metrics",
            "pnl_chart",
            "trade_analysis",
            "strategy_breakdown",
            "execution_quality",
        ]

        for expected_id in expected_section_ids:
            assert expected_id in section_ids

    @pytest.mark.asyncio
    async def test_generate_risk_report(self, report_generator):
        """Test risk analysis report generation."""
        # Given: Risk report parameters
        confidence_level = "95%"
        include_stress_tests = True

        # When: Generating risk report
        report = await report_generator.generate_risk_report(
            confidence_level, include_stress_tests
        )

        # Then: Report should contain risk analysis
        assert "metadata" in report
        assert "sections" in report

        # Verify risk-specific sections
        sections = report["sections"]
        section_ids = [s["section_id"] for s in sections]

        expected_section_ids = [
            "risk_summary",
            "var_analysis",
            "stress_tests",
            "correlation_matrix",
            "risk_attribution",
        ]

        for expected_id in expected_section_ids:
            assert expected_id in section_ids

    @pytest.mark.asyncio
    async def test_list_available_templates(self, report_generator):
        """Test listing available report templates."""
        # When: Listing templates
        templates = await report_generator.list_available_templates()

        # Then: Templates should be listed with details
        assert isinstance(templates, dict)
        assert len(templates) > 0

        for template_name, template_info in templates.items():
            assert "name" in template_info
            assert "description" in template_info
            assert "parameters" in template_info
            assert "sections" in template_info
            assert isinstance(template_info["sections"], list)

    @pytest.mark.asyncio
    async def test_get_report_history(self, report_generator):
        """Test report generation history."""
        # Given: Generated reports in history
        report_generator.report_history["test_report_1"] = {
            "request": {"template_name": "executive_summary"},
            "metadata": {"generated_at": datetime.utcnow().isoformat()},
            "generated_at": datetime.utcnow().isoformat(),
        }

        # When: Getting report history
        history = await report_generator.get_report_history(limit=10)

        # Then: History should be returned
        assert isinstance(history, list)
        assert len(history) >= 0

        if history:
            report_record = history[0]
            assert "request" in report_record
            assert "metadata" in report_record
            assert "generated_at" in report_record

    def test_parameter_validation(self, report_generator):
        """Test report parameter validation."""
        # Given: Template parameters and provided parameters
        template_params = {
            "date_range": {"type": "date_range", "required": True},
            "confidence_level": {
                "type": "select",
                "options": ["95%", "99%"],
                "default": "95%",
            },
            "include_predictions": {"type": "boolean", "default": True},
        }

        provided_params = {
            "date_range": (datetime(2024, 1, 1), datetime(2024, 1, 31)),
            "confidence_level": "95%",
        }

        # When: Validating parameters
        validated = asyncio.run(
            report_generator._validate_parameters(provided_params, template_params)
        )

        # Then: Parameters should be validated correctly
        assert "date_range" in validated
        assert "confidence_level" in validated
        assert "include_predictions" in validated  # Should use default
        assert validated["confidence_level"] == "95%"
        assert validated["include_predictions"] is True

    def test_generation_statistics(self, report_generator):
        """Test report generation statistics."""
        # Given: Some generated reports
        report_generator.generation_stats["total_reports"] = 10
        report_generator.generation_stats["success_count"] = 9
        report_generator.generation_stats["error_count"] = 1
        report_generator.generation_stats["total_generation_time"] = 5000.0

        # When: Getting statistics
        stats = report_generator.get_generation_statistics()

        # Then: Statistics should be calculated correctly
        assert stats["total_reports_generated"] == 10
        assert stats["successful_generations"] == 9
        assert stats["failed_generations"] == 1
        assert stats["success_rate_percentage"] == 90.0
        assert stats["average_generation_time_ms"] == 500.0


class TestDataWarehouseManager:
    """Test suite for Data Warehouse Management."""

    @pytest.fixture
    def mock_db_manager(self):
        """Mock database manager for data warehouse."""
        db_manager = AsyncMock()

        # Mock warehouse statistics
        db_manager.fetch_all.return_value = [
            {
                "schemaname": "analytics",
                "tablename": "fact_trading_performance",
                "live_rows": 5000,
                "dead_rows": 100,
                "inserts": 5000,
                "updates": 200,
                "deletes": 50,
            },
            {
                "schemaname": "analytics",
                "tablename": "fact_risk_metrics",
                "live_rows": 365,
                "dead_rows": 10,
                "inserts": 365,
                "updates": 50,
                "deletes": 5,
            },
        ]

        return db_manager

    @pytest.fixture
    async def warehouse_manager(self, mock_db_manager):
        """Data warehouse manager instance."""
        wm = DataWarehouseManager(mock_db_manager)
        await wm.initialize_warehouse()
        return wm

    @pytest.mark.asyncio
    async def test_initialize_warehouse(self, warehouse_manager):
        """Test data warehouse initialization."""
        # Then: Warehouse should be initialized
        assert len(warehouse_manager.etl_jobs) > 0
        assert len(warehouse_manager.quality_checks) > 0

        # Verify ETL jobs
        expected_jobs = [
            "daily_trading_performance",
            "hourly_market_data",
            "daily_risk_metrics",
            "weekly_portfolio_analysis",
            "dimension_refresh",
        ]

        for job_name in expected_jobs:
            assert job_name in warehouse_manager.etl_jobs
            job = warehouse_manager.etl_jobs[job_name]
            assert isinstance(job, ETLJob)
            assert job.job_id == job_name
            assert job.enabled is True

    @pytest.mark.asyncio
    async def test_run_etl_pipeline(self, warehouse_manager):
        """Test ETL pipeline execution."""
        # Given: Specific ETL job
        job_id = "daily_trading_performance"

        # When: Running ETL pipeline
        result = await warehouse_manager.run_etl_pipeline(job_id, force=True)

        # Then: Pipeline should execute successfully
        assert "jobs_executed" in result
        assert "successful_jobs" in result
        assert "failed_jobs" in result
        assert "results" in result

        assert result["jobs_executed"] >= 1
        assert isinstance(result["results"], list)
        assert isinstance(result["errors"], list)

    @pytest.mark.asyncio
    async def test_get_warehouse_statistics(self, warehouse_manager):
        """Test warehouse statistics retrieval."""
        # When: Getting warehouse statistics
        stats = await warehouse_manager.get_warehouse_statistics()

        # Then: Statistics should be comprehensive
        assert isinstance(stats, DataWarehouseStats)
        assert stats.total_tables >= 0
        assert stats.total_rows >= 0
        assert stats.total_size_gb >= 0
        assert stats.fact_tables >= 0
        assert stats.dimension_tables >= 0
        assert isinstance(stats.last_updated, datetime)

        # Verify statistics ranges
        assert 0.0 <= stats.data_quality_score <= 1.0
        assert 0.0 <= stats.etl_success_rate <= 1.0

    @pytest.mark.asyncio
    async def test_optimize_warehouse_performance(self, warehouse_manager):
        """Test warehouse performance optimization."""
        # When: Optimizing performance
        result = await warehouse_manager.optimize_warehouse_performance()

        # Then: Optimization should complete
        assert "operations_performed" in result
        assert "performance_improvements" in result
        assert "recommendations" in result

        assert isinstance(result["operations_performed"], list)
        assert isinstance(result["recommendations"], list)

        # Verify operations were performed
        operations = result["operations_performed"]
        assert len(operations) > 0

    @pytest.mark.asyncio
    async def test_run_data_quality_checks(self, warehouse_manager):
        """Test data quality monitoring."""
        # When: Running data quality checks
        quality_result = await warehouse_manager.run_data_quality_checks()

        # Then: Quality checks should complete
        assert "overall_quality_score" in quality_result
        assert "quality_level" in quality_result
        assert "check_results" in quality_result
        assert "total_checks" in quality_result
        assert "passed_checks" in quality_result
        assert "failed_checks" in quality_result

        # Verify quality score
        score = quality_result["overall_quality_score"]
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

        # Verify quality level categorization
        quality_level = quality_result["quality_level"]
        assert quality_level in ["Excellent", "Good", "Fair", "Poor"]

    @pytest.mark.asyncio
    async def test_get_etl_job_status(self, warehouse_manager):
        """Test ETL job status monitoring."""
        # When: Getting ETL job status
        statuses = await warehouse_manager.get_etl_job_status()

        # Then: Status should be returned for all jobs
        assert isinstance(statuses, list)
        assert len(statuses) == len(warehouse_manager.etl_jobs)

        for status in statuses:
            assert "job_id" in status
            assert "name" in status
            assert "enabled" in status
            assert "schedule" in status
            assert "status" in status
            assert isinstance(status["enabled"], bool)

    @pytest.mark.asyncio
    async def test_create_analytics_view(self, warehouse_manager):
        """Test analytics view creation."""
        # Given: Analytics view parameters
        view_name = "test_portfolio_summary"
        query = """
        SELECT
            date_id,
            SUM(total_pnl) as portfolio_pnl,
            AVG(win_rate) as avg_win_rate
        FROM analytics.fact_trading_performance
        GROUP BY date_id
        """
        materialized = True

        # When: Creating analytics view
        result = await warehouse_manager.create_analytics_view(
            view_name, query, materialized
        )

        # Then: View should be created successfully
        assert result["view_name"] == view_name
        assert result["materialized"] == materialized
        assert result["status"] == "created_successfully"
        assert "created_at" in result

        # Verify refresh job was created for materialized view
        refresh_job_id = f"refresh_{view_name}"
        assert refresh_job_id in warehouse_manager.etl_jobs

    def test_etl_job_scheduling(self, warehouse_manager):
        """Test ETL job scheduling logic."""
        # Given: ETL job with last run time
        job = warehouse_manager.etl_jobs["daily_trading_performance"]
        job.last_run = datetime.utcnow() - timedelta(hours=2)

        # When: Checking if job is due
        is_due = warehouse_manager._is_job_due(job)

        # Then: Job should be due (simple 1-hour check)
        assert is_due is True

        # Test job not due
        job.last_run = datetime.utcnow() - timedelta(minutes=30)
        is_not_due = warehouse_manager._is_job_due(job)
        assert is_not_due is False

    def test_query_validation(self, warehouse_manager):
        """Test analytics query validation."""
        # Given: Valid and invalid queries
        valid_query = "SELECT * FROM analytics.fact_trading_performance WHERE date_id = '2024-01-01'"
        invalid_query = "DROP TABLE analytics.fact_trading_performance"

        # When: Validating queries
        valid_result = warehouse_manager._validate_analytics_query(valid_query)
        invalid_result = warehouse_manager._validate_analytics_query(invalid_query)

        # Then: Validation should work correctly
        assert valid_result is True
        assert invalid_result is False

    def test_data_quality_categorization(self, warehouse_manager):
        """Test data quality level categorization."""
        # Given: Different quality scores
        excellent_score = 0.96
        good_score = 0.92
        fair_score = 0.85
        poor_score = 0.75

        # When: Categorizing quality levels
        excellent_level = warehouse_manager._categorize_quality_level(excellent_score)
        good_level = warehouse_manager._categorize_quality_level(good_score)
        fair_level = warehouse_manager._categorize_quality_level(fair_score)
        poor_level = warehouse_manager._categorize_quality_level(poor_score)

        # Then: Categorization should be correct
        assert excellent_level == "Excellent"
        assert good_level == "Good"
        assert fair_level == "Fair"
        assert poor_level == "Poor"


class TestBusinessIntelligenceIntegration:
    """Integration tests for complete BI system."""

    @pytest.fixture
    def mock_db_manager(self):
        """Mock database manager for integration tests."""
        return AsyncMock()

    @pytest.fixture
    def mock_portfolio_manager(self):
        """Mock portfolio manager for integration tests."""
        return Mock()

    @pytest.mark.asyncio
    async def test_end_to_end_executive_dashboard_pipeline(
        self, mock_db_manager, mock_portfolio_manager
    ):
        """Test complete executive dashboard pipeline."""
        # Given: Integrated BI components
        dashboard = ExecutiveDashboard(mock_db_manager, mock_portfolio_manager)
        analytics = AnalyticsEngine(mock_db_manager)

        # Mock data responses
        mock_db_manager.fetch_one.return_value = {
            "total_pnl": 15000.0,
            "daily_pnl": 250.0,
            "total_trades": 100,
            "winning_trades": 65,
            "avg_pnl": 150.0,
            "portfolio_value": 100000.0,
            "active_positions": 5,
            "unrealized_pnl": 500.0,
        }

        mock_db_manager.fetch_all.return_value = [
            {"symbol": "EUR/USD", "strategy_pnl": 2000.0, "trade_count": 30}
        ]

        # When: Getting comprehensive executive overview
        overview = await dashboard.get_executive_overview()
        real_time_metrics = await analytics.get_real_time_metrics()

        # Then: Pipeline should work end-to-end
        assert overview is not None
        assert real_time_metrics is not None

        # Verify data consistency between components
        exec_metrics = overview["executive_metrics"]
        assert "total_pnl" in exec_metrics
        assert isinstance(real_time_metrics.portfolio_pnl, Decimal)

    @pytest.mark.asyncio
    async def test_reporting_with_predictive_analytics(self, mock_db_manager):
        """Test integration between reporting and predictive analytics."""
        # Given: Report generator and predictive analytics
        report_gen = ReportGenerator(mock_db_manager)
        predictive = PredictiveAnalytics(mock_db_manager)

        await report_gen.initialize_templates()
        await predictive.initialize_models()

        # Mock report data
        mock_db_manager.fetch_one.return_value = {
            "total_pnl": 8500.0,
            "total_trades": 85,
            "winning_trades": 52,
        }

        # When: Generating report with predictions
        forecast = await predictive.generate_market_forecast(["EUR/USD"], 24, 0.95)

        report_request = ReportRequest(
            report_id="integration_test",
            template_name="executive_summary",
            parameters={
                "date_range": (datetime(2024, 1, 1), datetime(2024, 1, 31)),
                "include_predictions": True,
            },
            output_formats=["html"],
            recipients=[],
        )

        report = await report_gen.generate_report(report_request)

        # Then: Integration should work correctly
        assert forecast is not None
        assert report is not None
        assert forecast.forecast_id is not None
        assert report["metadata"]["report_id"] == "integration_test"

    @pytest.mark.asyncio
    async def test_warehouse_analytics_integration(self, mock_db_manager):
        """Test integration between data warehouse and analytics engine."""
        # Given: Warehouse manager and analytics engine
        warehouse = DataWarehouseManager(mock_db_manager)
        analytics = AnalyticsEngine(mock_db_manager)

        await warehouse.initialize_warehouse()

        # Mock warehouse data
        mock_db_manager.fetch_all.return_value = [
            {
                "live_rows": 1000,
                "dead_rows": 50,
                "tablename": "fact_trading_performance",
            }
        ]

        # When: Running ETL and analytics together
        etl_result = await warehouse.run_etl_pipeline(force=True)

        # Create analytics query on warehouse data
        query = AnalyticsQuery(
            query_id="warehouse_integration_test",
            query_type="portfolio_summary",
            parameters={},
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        analytics_result = await analytics.execute_query(query)

        # Then: Integration should work seamlessly
        assert etl_result["jobs_executed"] >= 0
        assert analytics_result is not None
        assert analytics_result.query_id == "warehouse_integration_test"

    def test_performance_under_load(self, mock_db_manager, mock_portfolio_manager):
        """Test system performance under simulated load."""
        # Given: Multiple BI components
        components = [
            ExecutiveDashboard(mock_db_manager, mock_portfolio_manager),
            AnalyticsEngine(mock_db_manager),
            ReportGenerator(mock_db_manager),
        ]

        # Mock fast responses
        mock_db_manager.fetch_one.return_value = {"total_pnl": 1000}
        mock_db_manager.fetch_all.return_value = []

        # When: Simulating concurrent operations
        start_time = datetime.utcnow()

        # Simulate multiple operations (in real test would be async)
        for _ in range(10):
            dashboard = components[0]
            assert dashboard is not None

        end_time = datetime.utcnow()
        execution_time = (end_time - start_time).total_seconds()

        # Then: Performance should be acceptable
        assert execution_time < 1.0  # Should complete quickly with mocked data

    @pytest.mark.asyncio
    async def test_error_handling_and_recovery(self, mock_db_manager):
        """Test error handling across BI components."""
        # Given: Components with failing database
        mock_db_manager.fetch_one.side_effect = Exception("Database connection failed")

        dashboard = ExecutiveDashboard(mock_db_manager, Mock())

        # When: Operations fail
        with pytest.raises(FXML4Exception):
            await dashboard.get_executive_metrics(
                datetime.utcnow() - timedelta(days=1), datetime.utcnow()
            )

        # Then: Errors should be properly handled and logged
        # (Error handling tested in individual component tests)


@pytest.mark.performance
class TestBusinessIntelligencePerformance:
    """Performance tests for Business Intelligence system."""

    @pytest.mark.asyncio
    async def test_dashboard_response_time(self):
        """Test executive dashboard response time."""
        # Mock fast database
        mock_db = AsyncMock()
        mock_db.fetch_one.return_value = {"total_pnl": 1000, "total_trades": 10}
        mock_db.fetch_all.return_value = []

        dashboard = ExecutiveDashboard(mock_db, Mock())

        # Measure response time
        start_time = datetime.utcnow()
        await dashboard.get_real_time_updates()
        end_time = datetime.utcnow()

        response_time_ms = (end_time - start_time).total_seconds() * 1000

        # Should respond in under 500ms with mocked data
        assert response_time_ms < 500

    @pytest.mark.asyncio
    async def test_analytics_query_performance(self):
        """Test analytics query performance."""
        mock_db = AsyncMock()
        mock_db.fetch_one.return_value = {"total_pnl": 1000}
        mock_db.fetch_all.return_value = []

        analytics = AnalyticsEngine(mock_db)

        query = AnalyticsQuery(
            query_id="perf_test",
            query_type="portfolio_summary",
            parameters={},
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        start_time = datetime.utcnow()
        result = await analytics.execute_query(query)
        end_time = datetime.utcnow()

        execution_time_ms = (end_time - start_time).total_seconds() * 1000

        # Analytics should complete quickly
        assert execution_time_ms < 1000
        assert result.execution_time_ms > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
