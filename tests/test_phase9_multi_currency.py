"""Comprehensive test suite for Phase 9: Multi-Currency Expansion & Cross-Pair Analysis.

This test suite validates all major components implemented in Phase 9:
- Multi-Currency Portfolio Manager
- Session-Aware Trading System
- Cross-Currency Arbitrage Detection
- Multi-Currency Elliott Wave Libraries
- Economic Calendar Integration
- Multi-Currency Dashboard Integration
"""

import asyncio
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List
from unittest.mock import AsyncMock, Mock, patch

import numpy as np
import pandas as pd
import pytest

from fxml4.analytics.cross_currency_arbitrage import (
    ArbitrageOpportunity,
    ArbitrageType,
    CrossCurrencyArbitrageEngine,
    TriangularArbitrageCalculation,
)
from fxml4.data_engineering.economic_calendar import (
    CurrencyRegion,
    EconomicCalendarManager,
    EconomicEvent,
    EconomicEventImpact,
    EventCategory,
    ForexFactoryProvider,
)

# Phase 9 imports
from fxml4.portfolio.multi_currency_portfolio_manager import (
    CurrencyPairConfig,
    MultiCurrencyPortfolioManager,
    PortfolioState,
    Position,
    TradingOpportunity,
)
from fxml4.trading.session_aware_trading_system import (
    CurrencySessionPreference,
    SessionAwareTradingSystem,
    SessionIntensityCalculator,
    SessionManager,
    TradingSession,
)
from fxml4.wave_analysis.multi_currency_wave_library import (
    CurrencyPairType,
    CurrencySpecificWaveAnalyzer,
    CurrencyWaveCharacteristics,
    MultiCurrencyWaveLibrary,
    WaveSessionOptimization,
)


@pytest.fixture
def sample_market_data():
    """Generate sample market data for testing."""
    dates = pd.date_range(start="2024-01-01", end="2024-01-31", freq="1H")

    # Generate realistic forex data with some volatility
    base_price = 1.0800
    prices = []
    for i, date in enumerate(dates):
        # Add some session-based volatility
        hour = date.hour
        session_volatility = 1.0

        if 0 <= hour < 9:  # Tokyo session
            session_volatility = 0.8
        elif 8 <= hour < 16:  # London session
            session_volatility = 1.2
        elif 13 <= hour < 21:  # New York session
            session_volatility = 1.0
        else:  # Quiet period
            session_volatility = 0.5

        # Generate price with trend and random walk
        trend = 0.0001 * np.sin(i / 24)  # Daily trend
        noise = np.random.normal(0, 0.001 * session_volatility)
        price = base_price + trend + noise

        prices.append(
            {
                "timestamp": date,
                "open": price,
                "high": price + abs(noise) * 0.5,
                "low": price - abs(noise) * 0.5,
                "close": price + noise * 0.2,
                "volume": np.random.randint(1000, 10000) * session_volatility,
            }
        )

    return pd.DataFrame(prices).set_index("timestamp")


@pytest.fixture
def sample_currency_data():
    """Generate sample multi-currency market data."""
    pairs = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD"]
    data = {}

    for pair in pairs:
        # Generate different base prices for each pair
        base_prices = {
            "EURUSD": 1.0800,
            "GBPUSD": 1.2700,
            "USDJPY": 150.00,
            "USDCHF": 0.9200,
            "AUDUSD": 0.6500,
        }

        dates = pd.date_range(start="2024-01-01", end="2024-01-07", freq="1H")
        base_price = base_prices[pair]

        prices = []
        for i, date in enumerate(dates):
            noise = np.random.normal(0, base_price * 0.001)
            price = base_price + noise

            prices.append(
                {
                    "timestamp": date,
                    "open": price,
                    "high": price + abs(noise) * 0.5,
                    "low": price - abs(noise) * 0.5,
                    "close": price + noise * 0.2,
                    "volume": np.random.randint(1000, 10000),
                }
            )

        data[pair] = pd.DataFrame(prices).set_index("timestamp")

    return data


@pytest.fixture
def sample_economic_events():
    """Generate sample economic events for testing."""
    events = [
        {
            "id": "nfp_2024_01_05",
            "title": "Non-Farm Payrolls",
            "country": "United States",
            "region": CurrencyRegion.USD,
            "category": EventCategory.EMPLOYMENT,
            "impact": EconomicEventImpact.HIGH,
            "datetime": datetime(2024, 1, 5, 13, 30, tzinfo=timezone.utc),
            "forecast": 200000.0,
            "previous": 180000.0,
            "unit": "jobs",
            "source": "test",
            "description": "Monthly employment data",
            "affected_currencies": ["USD"],
        },
        {
            "id": "ecb_rate_2024_01_25",
            "title": "ECB Interest Rate Decision",
            "country": "Eurozone",
            "region": CurrencyRegion.EUR,
            "category": EventCategory.CENTRAL_BANK,
            "impact": EconomicEventImpact.CRITICAL,
            "datetime": datetime(2024, 1, 25, 12, 45, tzinfo=timezone.utc),
            "forecast": 4.50,
            "previous": 4.50,
            "unit": "%",
            "source": "test",
            "description": "European Central Bank interest rate decision",
            "affected_currencies": ["EUR"],
        },
    ]

    return [EconomicEvent(**event) for event in events]


class TestMultiCurrencyPortfolioManager:
    """Test suite for Multi-Currency Portfolio Manager."""

    @pytest.fixture
    def portfolio_manager(self):
        """Create portfolio manager instance for testing."""
        config = {
            "max_portfolio_risk": 0.06,
            "max_single_position_risk": 0.02,
            "correlation_threshold": 0.7,
            "currencies": ["EURUSD", "GBPUSD", "USDJPY", "USDCHF"],
            "rebalancing": {"frequency": "daily", "threshold": 0.1},
        }
        return MultiCurrencyPortfolioManager(config)

    def test_portfolio_manager_initialization(self, portfolio_manager):
        """Test portfolio manager initializes correctly."""
        assert portfolio_manager is not None
        assert len(portfolio_manager.strategies) == 4
        assert "EURUSD" in portfolio_manager.strategies
        assert "GBPUSD" in portfolio_manager.strategies
        assert portfolio_manager.max_portfolio_risk == 0.06

    @pytest.mark.asyncio
    async def test_add_position(self, portfolio_manager, sample_currency_data):
        """Test adding positions to portfolio."""
        # Create a position
        position = Position(
            symbol="EURUSD",
            direction="long",
            size=100000,
            entry_price=1.0800,
            entry_time=datetime.now(),
            stop_loss=1.0750,
            take_profit=1.0900,
            risk_amount=2000.0,
        )

        # Add position
        await portfolio_manager.add_position(position)

        # Verify position was added
        assert len(portfolio_manager.positions) == 1
        assert portfolio_manager.positions[0].symbol == "EURUSD"
        assert portfolio_manager.positions[0].size == 100000

    @pytest.mark.asyncio
    async def test_correlation_risk_calculation(self, portfolio_manager):
        """Test correlation-based risk calculation."""
        # Add correlated positions
        position1 = Position(
            symbol="EURUSD",
            direction="long",
            size=100000,
            entry_price=1.0800,
            entry_time=datetime.now(),
            stop_loss=1.0750,
            take_profit=1.0900,
            risk_amount=2000.0,
        )

        position2 = Position(
            symbol="GBPUSD",
            direction="long",
            size=50000,
            entry_price=1.2700,
            entry_time=datetime.now(),
            stop_loss=1.2650,
            take_profit=1.2800,
            risk_amount=1500.0,
        )

        await portfolio_manager.add_position(position1)
        await portfolio_manager.add_position(position2)

        # Calculate correlation risk
        correlation_risk = await portfolio_manager.calculate_correlation_risk()

        # Verify correlation risk is calculated
        assert correlation_risk is not None
        assert isinstance(correlation_risk, float)
        assert 0 <= correlation_risk <= 1

    @pytest.mark.asyncio
    async def test_portfolio_optimization(
        self, portfolio_manager, sample_currency_data
    ):
        """Test portfolio optimization with correlation constraints."""
        # Generate trading opportunities
        opportunities = [
            TradingOpportunity(
                symbol="EURUSD",
                direction="long",
                entry_price=1.0800,
                confidence=0.8,
                expected_return=0.02,
                risk_reward_ratio=2.0,
                timeframe="1h",
            ),
            TradingOpportunity(
                symbol="GBPUSD",
                direction="long",
                entry_price=1.2700,
                confidence=0.7,
                expected_return=0.015,
                risk_reward_ratio=1.8,
                timeframe="1h",
            ),
        ]

        # Optimize portfolio
        optimized_opportunities = await portfolio_manager.optimize_portfolio(
            opportunities, sample_currency_data
        )

        # Verify optimization results
        assert len(optimized_opportunities) <= len(opportunities)
        for opp in optimized_opportunities:
            assert hasattr(opp, "adjusted_position_size")
            assert hasattr(opp, "correlation_adjustment")


class TestSessionAwareTradingSystem:
    """Test suite for Session-Aware Trading System."""

    @pytest.fixture
    def session_manager(self):
        """Create session manager for testing."""
        return SessionManager()

    @pytest.fixture
    def trading_system(self):
        """Create session-aware trading system for testing."""
        config = {
            "session_preferences": {
                "EURUSD": {"london": 0.9, "new_york": 0.8, "tokyo": 0.4},
                "GBPUSD": {"london": 1.0, "new_york": 0.7, "tokyo": 0.2},
                "USDJPY": {"tokyo": 0.8, "new_york": 0.7, "london": 0.6},
            }
        }
        return SessionAwareTradingSystem(config)

    def test_session_manager_initialization(self, session_manager):
        """Test session manager initializes correctly."""
        assert session_manager is not None
        assert len(session_manager.session_schedules) == 4  # Tokyo, London, NY, Sydney
        assert TradingSession.LONDON in session_manager.session_schedules

    def test_current_session_detection(self, session_manager):
        """Test current session detection."""
        # Test with specific time
        test_time = datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc)  # London session
        session = session_manager.get_session_for_time(test_time)

        assert session is not None
        assert isinstance(session, TradingSession)

    def test_session_intensity_calculation(self, session_manager):
        """Test session intensity calculation."""
        # Test intensity for London session
        intensity = session_manager.calculate_session_intensity(TradingSession.LONDON)

        assert isinstance(intensity, float)
        assert 0 <= intensity <= 100

    @pytest.mark.asyncio
    async def test_session_optimization(self, trading_system, sample_currency_data):
        """Test session-based trading optimization."""
        # Get current session
        current_session = trading_system.session_manager.get_current_session()

        # Optimize for current session
        optimized_pairs = await trading_system.optimize_for_session(
            current_session, list(sample_currency_data.keys())
        )

        # Verify optimization results
        assert isinstance(optimized_pairs, list)
        assert all(isinstance(pair, str) for pair in optimized_pairs)

    @pytest.mark.asyncio
    async def test_cross_session_analysis(self, trading_system):
        """Test cross-session analysis and transition management."""
        analysis = await trading_system.analyze_session_transitions()

        # Verify analysis structure
        assert "current_session" in analysis
        assert "next_session" in analysis
        assert "transition_time" in analysis
        assert "recommended_actions" in analysis

        # Verify recommended actions
        assert isinstance(analysis["recommended_actions"], list)


class TestCrossCurrencyArbitrage:
    """Test suite for Cross-Currency Arbitrage Detection."""

    @pytest.fixture
    def arbitrage_engine(self):
        """Create arbitrage engine for testing."""
        config = {
            "min_profit_threshold": 0.001,
            "max_execution_time": 300,
            "supported_currencies": ["EUR", "USD", "GBP", "JPY", "CHF", "AUD"],
            "risk_limits": {"max_exposure": 1000000, "max_positions": 5},
        }
        return CrossCurrencyArbitrageEngine(config)

    @pytest.mark.asyncio
    async def test_triangular_arbitrage_detection(self, arbitrage_engine):
        """Test triangular arbitrage opportunity detection."""
        # Mock market data
        mock_rates = {"EURUSD": 1.0800, "GBPUSD": 1.2700, "EURGBP": 0.8500}

        with patch.object(
            arbitrage_engine, "_get_current_rates", return_value=mock_rates
        ):
            opportunities = await arbitrage_engine.detect_arbitrage_opportunities()

        # Verify detection results
        assert isinstance(opportunities, list)
        if opportunities:  # If arbitrage found
            for opp in opportunities:
                assert isinstance(opp, ArbitrageOpportunity)
                assert opp.type in [
                    ArbitrageType.TRIANGULAR,
                    ArbitrageType.STATISTICAL,
                    ArbitrageType.CARRY_TRADE,
                ]

    @pytest.mark.asyncio
    async def test_statistical_arbitrage(self, arbitrage_engine, sample_currency_data):
        """Test statistical arbitrage detection."""
        # Use sample data for statistical analysis
        opportunities = await arbitrage_engine._detect_statistical_arbitrage(
            sample_currency_data
        )

        # Verify statistical arbitrage results
        assert isinstance(opportunities, list)
        for opp in opportunities:
            assert opp.type == ArbitrageType.STATISTICAL
            assert hasattr(opp, "expected_profit")
            assert hasattr(opp, "confidence_level")

    @pytest.mark.asyncio
    async def test_carry_trade_analysis(self, arbitrage_engine):
        """Test carry trade arbitrage analysis."""
        # Mock interest rate data
        mock_rates = {
            "USD": 0.0525,
            "EUR": 0.0450,
            "JPY": 0.0010,
            "GBP": 0.0525,
            "CHF": 0.0175,
            "AUD": 0.0435,
        }

        with patch.object(
            arbitrage_engine, "_get_interest_rates", return_value=mock_rates
        ):
            opportunities = await arbitrage_engine._detect_carry_trade_arbitrage()

        # Verify carry trade analysis
        assert isinstance(opportunities, list)
        for opp in opportunities:
            assert opp.type == ArbitrageType.CARRY_TRADE
            assert len(opp.currency_path) == 2  # Carry trades involve 2 currencies

    def test_arbitrage_opportunity_validation(self, arbitrage_engine):
        """Test arbitrage opportunity validation logic."""
        # Create test opportunity
        opportunity = ArbitrageOpportunity(
            id="test_triangular_1",
            type=ArbitrageType.TRIANGULAR,
            currency_path=["EUR", "GBP", "USD"],
            expected_profit=0.0025,
            risk_level="low",
            execution_time=180,
            required_capital=100000,
            confidence_level=0.85,
            market_impact=0.0001,
        )

        # Validate opportunity
        is_valid = arbitrage_engine._validate_opportunity(opportunity)

        assert isinstance(is_valid, bool)


class TestMultiCurrencyWaveLibrary:
    """Test suite for Multi-Currency Elliott Wave Libraries."""

    @pytest.fixture
    def wave_library(self):
        """Create multi-currency wave library for testing."""
        config = {
            "detection_sensitivity": 0.7,
            "fibonacci_tolerance": 0.05,
            "session_optimization": True,
        }
        return MultiCurrencyWaveLibrary(config)

    @pytest.fixture
    def currency_analyzer(self):
        """Create currency-specific wave analyzer for testing."""
        return CurrencySpecificWaveAnalyzer("EURUSD")

    def test_wave_library_initialization(self, wave_library):
        """Test wave library initializes correctly."""
        assert wave_library is not None
        assert len(wave_library.currency_characteristics) > 0
        assert "EURUSD" in wave_library.currency_characteristics
        assert len(wave_library.wave_detectors) > 0

    def test_currency_characteristics(self, wave_library):
        """Test currency-specific characteristics."""
        eurusd_chars = wave_library.currency_characteristics["EURUSD"]

        assert isinstance(eurusd_chars, CurrencyWaveCharacteristics)
        assert eurusd_chars.pair == "EURUSD"
        assert isinstance(eurusd_chars.volatility_profile, dict)
        assert isinstance(eurusd_chars.wave_completion_times, dict)
        assert 0 <= eurusd_chars.fibonacci_sensitivity <= 1

    @pytest.mark.asyncio
    async def test_currency_wave_detection(self, wave_library, sample_market_data):
        """Test wave detection for specific currency."""
        patterns = await wave_library.detect_currency_waves(
            "EURUSD", sample_market_data, "1h"
        )

        assert isinstance(patterns, list)
        # Note: Patterns may be empty for test data, which is valid

    @pytest.mark.asyncio
    async def test_session_optimization(self, wave_library, sample_market_data):
        """Test session-specific wave optimization."""
        # Test London session optimization
        patterns = await wave_library.detect_currency_waves(
            "EURUSD", sample_market_data, "1h", WaveSessionOptimization.LONDON_OPTIMIZED
        )

        assert isinstance(patterns, list)

    @pytest.mark.asyncio
    async def test_cross_currency_correlations(
        self, wave_library, sample_currency_data
    ):
        """Test cross-currency wave correlation analysis."""
        # First, detect patterns for multiple currencies
        for pair, data in sample_currency_data.items():
            if pair in wave_library.wave_detectors:
                await wave_library.detect_currency_waves(pair, data, "1h")

        # Then test correlation calculation
        correlations = await wave_library.get_cross_currency_correlations()

        assert isinstance(correlations, dict)
        for pair1, corr_dict in correlations.items():
            assert isinstance(corr_dict, dict)
            for pair2, correlation in corr_dict.items():
                assert -1 <= correlation <= 1

    @pytest.mark.asyncio
    async def test_multi_currency_optimization(
        self, wave_library, sample_currency_data
    ):
        """Test multi-currency wave detection optimization."""
        results = await wave_library.optimize_multi_currency_detection(
            sample_currency_data
        )

        assert isinstance(results, dict)
        for pair, patterns in results.items():
            assert isinstance(patterns, list)

    @pytest.mark.asyncio
    async def test_currency_specific_analyzer(
        self, currency_analyzer, sample_market_data
    ):
        """Test currency-specific wave analyzer."""
        analysis = await currency_analyzer.analyze_currency_waves(
            sample_market_data, timeframes=["15m", "1h"], session_optimization=True
        )

        assert isinstance(analysis, dict)
        assert "pair" in analysis
        assert "timeframe_analysis" in analysis
        assert "overall_wave_state" in analysis
        assert "trading_recommendations" in analysis


class TestEconomicCalendar:
    """Test suite for Economic Calendar Integration."""

    @pytest.fixture
    def calendar_manager(self):
        """Create economic calendar manager for testing."""
        config = {
            "database": {"url": "sqlite:///:memory:"},
            "providers": {"forex_factory": {}},
        }
        return EconomicCalendarManager(config)

    def test_calendar_manager_initialization(self, calendar_manager):
        """Test calendar manager initializes correctly."""
        assert calendar_manager is not None
        assert len(calendar_manager.providers) > 0
        assert "forex_factory" in calendar_manager.providers

    def test_economic_event_creation(self, sample_economic_events):
        """Test economic event data structure."""
        event = sample_economic_events[0]

        assert isinstance(event, EconomicEvent)
        assert event.title == "Non-Farm Payrolls"
        assert event.impact == EconomicEventImpact.HIGH
        assert event.region == CurrencyRegion.USD
        assert "USD" in event.affected_currencies

    def test_event_market_impact_assessment(self, sample_economic_events):
        """Test market impact assessment for events."""
        event = sample_economic_events[1]  # ECB rate decision

        assert event.is_market_moving()  # Critical impact event should be market-moving

        # Test with actual vs forecast surprise
        event.actual = 4.75  # Higher than forecast
        event.forecast = 4.50
        event.surprise_index = None  # Reset to trigger recalculation
        event.__post_init__()  # Recalculate surprise index

        assert event.surprise_index is not None
        assert event.surprise_index > 0  # Positive surprise

    @pytest.mark.asyncio
    async def test_event_fetching(self, calendar_manager):
        """Test fetching economic events."""
        start_date = datetime.now()
        end_date = start_date + timedelta(days=7)

        # Mock the provider to return test data
        mock_provider = Mock()
        mock_provider.get_events = AsyncMock(return_value=[])
        calendar_manager.providers["test"] = mock_provider

        events = await calendar_manager.get_economic_events(
            start_date, end_date, use_cache=False, save_to_db=False
        )

        assert isinstance(events, list)

    @pytest.mark.asyncio
    async def test_currency_specific_events(
        self, calendar_manager, sample_economic_events
    ):
        """Test filtering events by currency."""
        # Mock the get_economic_events method to return sample events
        with patch.object(
            calendar_manager, "get_economic_events", return_value=sample_economic_events
        ):
            usd_events = await calendar_manager.get_events_for_currency("USD")
            eur_events = await calendar_manager.get_events_for_currency("EUR")

        # Verify currency filtering
        assert len(usd_events) == 1
        assert len(eur_events) == 1
        assert usd_events[0].region == CurrencyRegion.USD
        assert eur_events[0].region == CurrencyRegion.EUR

    @pytest.mark.asyncio
    async def test_market_impact_analysis(
        self, calendar_manager, sample_economic_events
    ):
        """Test market impact analysis for currency pairs."""

        # Mock the get_events_for_currency method
        def mock_get_events(currency, hours_ahead):
            if currency == "EUR":
                return [
                    e for e in sample_economic_events if e.region == CurrencyRegion.EUR
                ]
            elif currency == "USD":
                return [
                    e for e in sample_economic_events if e.region == CurrencyRegion.USD
                ]
            return []

        with patch.object(
            calendar_manager, "get_events_for_currency", side_effect=mock_get_events
        ):
            analysis = await calendar_manager.get_market_impact_analysis("EURUSD", 24)

        # Verify analysis structure
        assert isinstance(analysis, dict)
        assert analysis["currency_pair"] == "EURUSD"
        assert "risk_level" in analysis
        assert "trading_recommendation" in analysis
        assert "critical_events" in analysis
        assert "high_impact_events" in analysis


class TestPhase9Integration:
    """Integration tests for Phase 9 components working together."""

    @pytest.fixture
    def integrated_system(self):
        """Create integrated multi-currency system for testing."""
        return {
            "portfolio_manager": MultiCurrencyPortfolioManager(),
            "session_system": SessionAwareTradingSystem(),
            "arbitrage_engine": CrossCurrencyArbitrageEngine(),
            "wave_library": MultiCurrencyWaveLibrary(),
            "economic_calendar": EconomicCalendarManager(
                {
                    "database": {"url": "sqlite:///:memory:"},
                    "providers": {"forex_factory": {}},
                }
            ),
        }

    @pytest.mark.asyncio
    async def test_integrated_decision_making(
        self, integrated_system, sample_currency_data
    ):
        """Test integrated decision-making across all Phase 9 components."""
        portfolio = integrated_system["portfolio_manager"]
        sessions = integrated_system["session_system"]
        arbitrage = integrated_system["arbitrage_engine"]
        waves = integrated_system["wave_library"]
        calendar = integrated_system["economic_calendar"]

        # Get current session
        current_session = sessions.session_manager.get_current_session()

        # Get session-optimized currency pairs
        optimized_pairs = await sessions.optimize_for_session(
            current_session, list(sample_currency_data.keys())
        )

        # Detect wave patterns for optimized pairs
        wave_results = {}
        for pair in optimized_pairs[:2]:  # Test with first 2 pairs
            if pair in sample_currency_data:
                patterns = await waves.detect_currency_waves(
                    pair, sample_currency_data[pair], "1h"
                )
                wave_results[pair] = patterns

        # Check for arbitrage opportunities
        arb_opportunities = await arbitrage.detect_arbitrage_opportunities()

        # Mock economic events check
        with patch.object(calendar, "get_upcoming_events", return_value=[]):
            upcoming_events = await calendar.get_upcoming_events(24)

        # Verify integrated analysis
        assert current_session is not None
        assert isinstance(optimized_pairs, list)
        assert isinstance(wave_results, dict)
        assert isinstance(arb_opportunities, list)
        assert isinstance(upcoming_events, list)

    @pytest.mark.asyncio
    async def test_risk_management_integration(self, integrated_system):
        """Test integrated risk management across components."""
        portfolio = integrated_system["portfolio_manager"]
        calendar = integrated_system["economic_calendar"]

        # Add test positions
        position1 = Position(
            symbol="EURUSD",
            direction="long",
            size=100000,
            entry_price=1.0800,
            entry_time=datetime.now(),
            stop_loss=1.0750,
            take_profit=1.0900,
            risk_amount=2000.0,
        )

        await portfolio.add_position(position1)

        # Mock high-impact economic events
        high_impact_events = [
            EconomicEvent(
                id="test_critical",
                title="Test Critical Event",
                country="Eurozone",
                region=CurrencyRegion.EUR,
                category=EventCategory.CENTRAL_BANK,
                impact=EconomicEventImpact.CRITICAL,
                datetime=datetime.now() + timedelta(hours=2),
                affected_currencies=["EUR"],
            )
        ]

        with patch.object(
            calendar, "get_upcoming_events", return_value=high_impact_events
        ):
            # Get market impact analysis for our position
            impact_analysis = await calendar.get_market_impact_analysis("EURUSD", 24)

        # Verify risk assessment includes economic calendar impact
        assert impact_analysis["risk_level"] in ["critical", "high", "medium", "low"]
        assert "trading_recommendation" in impact_analysis

        # Calculate portfolio correlation risk
        correlation_risk = await portfolio.calculate_correlation_risk()
        assert isinstance(correlation_risk, float)

    @pytest.mark.asyncio
    async def test_performance_benchmarks(
        self, integrated_system, sample_currency_data
    ):
        """Test performance benchmarks for Phase 9 components."""
        import time

        # Test portfolio optimization performance
        start_time = time.time()
        portfolio = integrated_system["portfolio_manager"]

        opportunities = [
            TradingOpportunity(
                symbol="EURUSD",
                direction="long",
                entry_price=1.0800,
                confidence=0.8,
                expected_return=0.02,
                risk_reward_ratio=2.0,
                timeframe="1h",
            )
        ]

        await portfolio.optimize_portfolio(opportunities, sample_currency_data)
        portfolio_time = time.time() - start_time

        # Test wave detection performance
        start_time = time.time()
        waves = integrated_system["wave_library"]

        await waves.detect_currency_waves(
            "EURUSD", sample_currency_data["EURUSD"], "1h"
        )
        wave_time = time.time() - start_time

        # Test arbitrage detection performance
        start_time = time.time()
        arbitrage = integrated_system["arbitrage_engine"]

        await arbitrage.detect_arbitrage_opportunities()
        arbitrage_time = time.time() - start_time

        # Verify performance targets (should complete within reasonable time)
        assert portfolio_time < 5.0  # Portfolio optimization under 5 seconds
        assert wave_time < 3.0  # Wave detection under 3 seconds
        assert arbitrage_time < 2.0  # Arbitrage detection under 2 seconds


class TestPhase9ErrorHandling:
    """Test error handling and edge cases for Phase 9 components."""

    @pytest.mark.asyncio
    async def test_portfolio_manager_error_handling(self):
        """Test portfolio manager handles errors gracefully."""
        portfolio = MultiCurrencyPortfolioManager()

        # Test invalid position
        invalid_position = Position(
            symbol="INVALID",
            direction="long",
            size=-100000,  # Invalid negative size
            entry_price=0,  # Invalid zero price
            entry_time=datetime.now(),
            stop_loss=0,
            take_profit=0,
            risk_amount=0,
        )

        # Should handle invalid position gracefully
        with pytest.raises((ValueError, AssertionError)):
            await portfolio.add_position(invalid_position)

    @pytest.mark.asyncio
    async def test_wave_library_edge_cases(self):
        """Test wave library handles edge cases."""
        wave_library = MultiCurrencyWaveLibrary()

        # Test with empty data
        empty_data = pd.DataFrame()
        patterns = await wave_library.detect_currency_waves("EURUSD", empty_data, "1h")
        assert isinstance(patterns, list)
        assert len(patterns) == 0

        # Test with invalid currency pair
        patterns = await wave_library.detect_currency_waves("INVALID", empty_data, "1h")
        assert isinstance(patterns, list)

    @pytest.mark.asyncio
    async def test_arbitrage_engine_error_handling(self):
        """Test arbitrage engine error handling."""
        arbitrage = CrossCurrencyArbitrageEngine()

        # Test with no market data
        with patch.object(arbitrage, "_get_current_rates", return_value={}):
            opportunities = await arbitrage.detect_arbitrage_opportunities()
            assert isinstance(opportunities, list)

    def test_economic_calendar_data_validation(self):
        """Test economic calendar data validation."""
        # Test invalid event data
        with pytest.raises((ValueError, TypeError)):
            EconomicEvent(
                id="",  # Empty ID
                title="",  # Empty title
                country="",
                region="invalid_region",  # Invalid region
                category="invalid_category",  # Invalid category
                impact="invalid_impact",  # Invalid impact
                datetime="invalid_datetime",  # Invalid datetime
            )


# Performance and stress tests
class TestPhase9Performance:
    """Performance tests for Phase 9 components."""

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_high_frequency_portfolio_updates(self):
        """Test portfolio manager performance with high-frequency updates."""
        portfolio = MultiCurrencyPortfolioManager()

        # Simulate rapid position updates
        start_time = time.time()

        for i in range(100):
            position = Position(
                symbol=f"TEST{i%4}USD",
                direction="long" if i % 2 == 0 else "short",
                size=10000 + i * 1000,
                entry_price=1.0 + i * 0.0001,
                entry_time=datetime.now(),
                stop_loss=1.0 + i * 0.0001 - 0.005,
                take_profit=1.0 + i * 0.0001 + 0.01,
                risk_amount=100 + i * 10,
            )

            await portfolio.add_position(position)

        update_time = time.time() - start_time

        # Should handle 100 updates within reasonable time
        assert update_time < 10.0
        assert len(portfolio.positions) == 100

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_large_dataset_wave_analysis(self):
        """Test wave analysis performance with large datasets."""
        wave_library = MultiCurrencyWaveLibrary()

        # Generate large dataset
        dates = pd.date_range(start="2023-01-01", end="2024-01-01", freq="1min")
        large_data = pd.DataFrame(
            {
                "timestamp": dates,
                "open": 1.0800 + np.random.normal(0, 0.001, len(dates)),
                "high": 1.0800 + np.random.normal(0, 0.001, len(dates)) + 0.0005,
                "low": 1.0800 + np.random.normal(0, 0.001, len(dates)) - 0.0005,
                "close": 1.0800 + np.random.normal(0, 0.001, len(dates)),
                "volume": np.random.randint(1000, 10000, len(dates)),
            }
        ).set_index("timestamp")

        start_time = time.time()
        patterns = await wave_library.detect_currency_waves("EURUSD", large_data, "1h")
        analysis_time = time.time() - start_time

        # Should analyze large dataset within reasonable time
        assert analysis_time < 30.0  # Under 30 seconds for 1 year of minute data
        assert isinstance(patterns, list)


if __name__ == "__main__":
    # Run the test suite
    pytest.main(
        [
            __file__,
            "-v",
            "--tb=short",
            "--durations=10",
            "-m",
            "not performance",  # Exclude performance tests by default
        ]
    )
