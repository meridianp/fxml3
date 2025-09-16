"""
Test Suite for Shared Market Data Fixtures
==========================================

Demonstrates the usage and validates the functionality of the shared
market data fixtures. This test serves as both validation and documentation
for the new centralized data generation system.
"""

from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest
from fixtures.market_data_fixtures import (
    MarketDataGenerator,
    MarketRegime,
    SessionType,
    create_custom_market_data,
    validate_market_data_integrity,
)


class TestMarketDataGenerator:
    """Test the core MarketDataGenerator functionality."""

    def test_basic_ohlcv_generation(self, market_data_generator):
        """Test basic OHLCV data generation."""
        data = market_data_generator.generate_ohlcv_data(
            symbol="EURUSD", periods=100, timeframe="1H"
        )

        assert len(data) == 100
        assert "timestamp" in data.columns
        assert "symbol" in data.columns
        assert all(data["symbol"] == "EURUSD")

        # Validate OHLC relationships
        integrity = validate_market_data_integrity(data)
        assert all(integrity.values()), f"Data integrity failed: {integrity}"

    def test_different_market_regimes(self, market_data_generator, market_regime):
        """Test data generation with different market regimes."""
        data = market_data_generator.generate_ohlcv_data(
            symbol="EURUSD",
            periods=200,
            regime=market_regime,
        )

        assert len(data) == 200

        # Calculate returns to verify regime characteristics
        returns = data["close"].pct_change().dropna()

        if market_regime == MarketRegime.QUIET:
            # Should have low volatility
            assert returns.std() < 0.002
        elif market_regime == MarketRegime.VOLATILE:
            # Should have high volatility
            assert returns.std() > 0.005

    def test_multiple_currency_pairs(self, market_data_generator, major_currency_pair):
        """Test data generation for different currency pairs."""
        data = market_data_generator.generate_ohlcv_data(
            symbol=major_currency_pair,
            periods=50,
        )

        assert all(data["symbol"] == major_currency_pair)

        # Each currency pair should have realistic price levels
        avg_price = data["close"].mean()
        if "JPY" in major_currency_pair:
            assert 80 < avg_price < 150  # JPY pairs are in different range
        else:
            assert 0.5 < avg_price < 2.0  # Other major pairs

    def test_multiple_timeframes(self, market_data_generator, common_timeframe):
        """Test data generation with different timeframes."""
        data = market_data_generator.generate_ohlcv_data(
            symbol="EURUSD",
            periods=100,
            timeframe=common_timeframe,
        )

        assert len(data) == 100

        # Check that timestamps are properly spaced
        if len(data) > 1:
            time_diffs = data["timestamp"].diff().dropna()
            # All time differences should be the same for regular intervals
            unique_diffs = time_diffs.nunique()
            assert unique_diffs <= 2  # Allow for minor variations

    def test_trend_strength_impact(self, market_data_generator):
        """Test that trend strength affects price direction."""
        # Strong uptrend
        up_data = market_data_generator.generate_ohlcv_data(
            symbol="EURUSD",
            periods=100,
            regime=MarketRegime.TRENDING_UP,
            trend_strength=0.8,
            seed=123,
        )

        # Strong downtrend
        down_data = market_data_generator.generate_ohlcv_data(
            symbol="EURUSD",
            periods=100,
            regime=MarketRegime.TRENDING_DOWN,
            trend_strength=-0.8,
            seed=123,
        )

        up_return = (up_data["close"].iloc[-1] - up_data["close"].iloc[0]) / up_data[
            "close"
        ].iloc[0]
        down_return = (
            down_data["close"].iloc[-1] - down_data["close"].iloc[0]
        ) / down_data["close"].iloc[0]

        assert up_return > 0.01  # Should trend up
        assert down_return < -0.01  # Should trend down

    def test_session_effects(self, market_data_generator):
        """Test that session effects influence volatility."""
        # Generate data with session effects
        with_sessions = market_data_generator.generate_ohlcv_data(
            symbol="EURUSD",
            periods=200,
            session_effects=True,
            seed=42,
        )

        # Generate data without session effects
        without_sessions = market_data_generator.generate_ohlcv_data(
            symbol="EURUSD",
            periods=200,
            session_effects=False,
            seed=42,
        )

        # Data with sessions should have different volatility patterns
        with_vol = with_sessions["close"].pct_change().rolling(24).std().mean()
        without_vol = without_sessions["close"].pct_change().rolling(24).std().mean()

        # Should be different (not asserting which is higher as it depends on timing)
        assert abs(with_vol - without_vol) > 0.0001


class TestTickDataGeneration:
    """Test tick data generation functionality."""

    def test_basic_tick_generation(self, market_data_generator):
        """Test basic tick data generation."""
        ticks = market_data_generator.generate_tick_data(
            symbol="EURUSD",
            duration_minutes=10,
            avg_ticks_per_minute=20,
        )

        # Should generate approximately the expected number of ticks
        expected_ticks = 10 * 20
        assert len(ticks) > expected_ticks * 0.5  # Allow for randomness
        assert len(ticks) < expected_ticks * 2.0

        # Check tick structure
        tick = ticks[0]
        required_fields = ["symbol", "timestamp", "bid", "ask", "bid_size", "ask_size"]
        assert all(field in tick for field in required_fields)

        # Validate bid/ask relationship
        for tick in ticks[:10]:  # Check first 10 ticks
            assert tick["ask"] > tick["bid"], "Ask should be higher than bid"
            assert tick["ask"] - tick["bid"] < 0.001, "Spread too wide"

    def test_session_impact_on_ticks(self, market_data_generator):
        """Test that different sessions affect tick generation."""
        london_ticks = market_data_generator.generate_tick_data(
            symbol="EURUSD",
            duration_minutes=30,
            session=SessionType.LONDON,
        )

        asian_ticks = market_data_generator.generate_tick_data(
            symbol="EURUSD",
            duration_minutes=30,
            session=SessionType.ASIAN,
        )

        # London session should generate more ticks (higher activity)
        assert len(london_ticks) > len(asian_ticks)

        # London session should have larger average volumes
        london_avg_volume = np.mean([tick["bid_size"] for tick in london_ticks])
        asian_avg_volume = np.mean([tick["bid_size"] for tick in asian_ticks])
        assert london_avg_volume > asian_avg_volume


class TestMultiTimeframeData:
    """Test multi-timeframe data generation."""

    def test_timeframe_aggregation(self, market_data_generator):
        """Test that higher timeframes properly aggregate lower timeframes."""
        multi_tf_data = market_data_generator.generate_multi_timeframe_data(
            symbol="EURUSD",
            base_timeframe="1M",
            target_timeframes=["5M", "15M", "1H"],
            periods=300,  # 5 hours of 1M data
        )

        base_data = multi_tf_data["1M"]
        tf_5m = multi_tf_data["5M"]
        tf_15m = multi_tf_data["15M"]
        tf_1h = multi_tf_data["1H"]

        # Higher timeframes should have fewer periods
        assert len(base_data) == 300
        assert len(tf_5m) < len(base_data)
        assert len(tf_15m) < len(tf_5m)
        assert len(tf_1h) < len(tf_15m)

        # Verify aggregation logic: first 5M bar should contain first 5 1M bars
        first_5m_bar = tf_5m.iloc[0]
        first_5_1m_bars = base_data.iloc[:5]

        # Open of 5M should equal open of first 1M
        assert abs(first_5m_bar["open"] - first_5_1m_bars["open"].iloc[0]) < 0.0001

        # Close of 5M should equal close of last 1M in the period
        assert abs(first_5m_bar["close"] - first_5_1m_bars["close"].iloc[-1]) < 0.0001

        # High of 5M should equal max high of the 5 1M bars
        assert abs(first_5m_bar["high"] - first_5_1m_bars["high"].max()) < 0.0001

        # Low of 5M should equal min low of the 5 1M bars
        assert abs(first_5m_bar["low"] - first_5_1m_bars["low"].min()) < 0.0001

    def test_timeframe_consistency(self, market_data_generator):
        """Test that multi-timeframe data is consistent across timeframes."""
        multi_tf_data = market_data_generator.generate_multi_timeframe_data(
            symbol="EURUSD",
            periods=120,  # 2 hours
        )

        # Check that all timeframes have the same symbol
        for tf, data in multi_tf_data.items():
            assert all(data["symbol"] == "EURUSD")

            # Validate data integrity for each timeframe
            integrity = validate_market_data_integrity(data)
            assert all(integrity.values()), f"Integrity failed for {tf}: {integrity}"


class TestEconomicIndicators:
    """Test economic indicators generation."""

    def test_indicators_structure(self, economic_indicators):
        """Test economic indicators data structure."""
        assert len(economic_indicators) > 0

        required_columns = [
            "date",
            "us_interest_rate",
            "eu_interest_rate",
            "uk_interest_rate",
            "us_gdp_growth",
            "eu_gdp_growth",
            "us_inflation",
            "eu_inflation",
            "us_unemployment",
            "eu_unemployment",
            "vix",
            "dollar_index",
        ]

        assert all(col in economic_indicators.columns for col in required_columns)

    def test_indicators_ranges(self, economic_indicators):
        """Test that economic indicators are within realistic ranges."""
        # Interest rates should be positive and reasonable
        assert (economic_indicators["us_interest_rate"] >= 0).all()
        assert (economic_indicators["us_interest_rate"] <= 15).all()

        # VIX should be within reasonable bounds
        assert (economic_indicators["vix"] >= 10).all()
        assert (economic_indicators["vix"] <= 80).all()

        # Unemployment rates should be reasonable
        assert (economic_indicators["us_unemployment"] >= 2).all()
        assert (economic_indicators["us_unemployment"] <= 15).all()


class TestChartPatterns:
    """Test chart pattern generation."""

    def test_pattern_availability(self, chart_patterns):
        """Test that all expected patterns are generated."""
        expected_patterns = [
            "head_shoulders",
            "double_top",
            "double_bottom",
            "ascending_triangle",
            "descending_triangle",
            "symmetrical_triangle",
            "bull_flag",
            "bear_flag",
        ]

        for pattern in expected_patterns:
            assert pattern in chart_patterns
            assert len(chart_patterns[pattern]) > 0

    def test_head_shoulders_pattern(self, chart_patterns):
        """Test head and shoulders pattern characteristics."""
        hs_data = chart_patterns["head_shoulders"]

        # Should have the characteristic shape
        prices = hs_data["close"].values

        # Find the three peaks (simplified test)
        peaks = []
        for i in range(1, len(prices) - 1):
            if prices[i] > prices[i - 1] and prices[i] > prices[i + 1]:
                peaks.append((i, prices[i]))

        assert len(peaks) >= 2, "Should have at least 2 peaks"

    def test_double_top_pattern(self, chart_patterns):
        """Test double top pattern characteristics."""
        dt_data = chart_patterns["double_top"]

        # Should end lower than it started (bearish pattern)
        start_price = dt_data["close"].iloc[0]
        end_price = dt_data["close"].iloc[-1]

        assert end_price < start_price, "Double top should be bearish"


class TestStressScenarios:
    """Test stress test scenario generation."""

    def test_scenario_availability(self, stress_scenarios):
        """Test that all stress scenarios are available."""
        expected_scenarios = [
            "flash_crash",
            "gap_opening",
            "high_volatility",
            "trending_market",
            "whipsaw_market",
        ]

        for scenario in expected_scenarios:
            assert scenario in stress_scenarios
            assert "data" in stress_scenarios[scenario]
            assert "description" in stress_scenarios[scenario]

    def test_flash_crash_scenario(self, stress_scenarios):
        """Test flash crash scenario characteristics."""
        crash_data = stress_scenarios["flash_crash"]["data"]
        expected_drawdown = stress_scenarios["flash_crash"]["expected_drawdown"]

        # Calculate maximum drawdown
        peak = crash_data["high"].expanding().max()
        drawdown = (crash_data["low"] - peak) / peak
        max_drawdown = drawdown.min()

        assert (
            max_drawdown <= -expected_drawdown * 0.8
        ), "Flash crash should create significant drawdown"

    def test_high_volatility_scenario(self, stress_scenarios):
        """Test high volatility scenario."""
        vol_data = stress_scenarios["high_volatility"]["data"]
        expected_vol_increase = stress_scenarios["high_volatility"][
            "expected_volatility_increase"
        ]

        # Calculate volatility
        returns = vol_data["close"].pct_change().dropna()
        volatility = returns.std()

        # Should have elevated volatility
        assert volatility > 0.01, f"Volatility {volatility} should be elevated"

    def test_gap_scenario(self, stress_scenarios):
        """Test gap opening scenario."""
        gap_data = stress_scenarios["gap_opening"]["data"]
        expected_gap = stress_scenarios["gap_opening"]["expected_gap"]

        # Find the gap (look for large price jump between consecutive periods)
        price_gaps = []
        for i in range(1, len(gap_data)):
            gap = abs(gap_data["open"].iloc[i] - gap_data["close"].iloc[i - 1])
            gap_pct = gap / gap_data["close"].iloc[i - 1]
            price_gaps.append(gap_pct)

        max_gap = max(price_gaps)
        assert (
            max_gap >= expected_gap * 0.8
        ), f"Should have gap of at least {expected_gap*0.8:.2%}"


class TestUtilityFunctions:
    """Test utility functions."""

    def test_create_custom_market_data(self):
        """Test custom market data creation."""
        scenarios = [
            "quiet_market",
            "trending_bull",
            "trending_bear",
            "high_volatility",
        ]

        for scenario in scenarios:
            data = create_custom_market_data("EURUSD", scenario)

            assert len(data) > 0
            assert all(data["symbol"] == "EURUSD")

            integrity = validate_market_data_integrity(data)
            assert all(
                integrity.values()
            ), f"Custom data integrity failed for {scenario}"

    def test_data_integrity_validation(self, sample_ohlcv_data):
        """Test data integrity validation function."""
        # Test with valid data
        integrity = validate_market_data_integrity(sample_ohlcv_data)
        assert all(integrity.values())

        # Test with corrupted data
        corrupted_data = sample_ohlcv_data.copy()
        corrupted_data.loc[0, "high"] = (
            corrupted_data.loc[0, "low"] - 0.01
        )  # Invalid OHLC

        integrity = validate_market_data_integrity(corrupted_data)
        assert not integrity["valid_ohlc_relationships"]

        # Test with missing data
        corrupted_data = sample_ohlcv_data.copy()
        corrupted_data.loc[0, "close"] = None

        integrity = validate_market_data_integrity(corrupted_data)
        assert not integrity["no_missing_data"]


class TestDataReproducibility:
    """Test that data generation is reproducible."""

    def test_seed_reproducibility(self):
        """Test that using the same seed produces identical data."""
        generator1 = MarketDataGenerator(seed=42)
        generator2 = MarketDataGenerator(seed=42)

        data1 = generator1.generate_ohlcv_data(symbol="EURUSD", periods=100)
        data2 = generator2.generate_ohlcv_data(symbol="EURUSD", periods=100)

        # Should be identical
        pd.testing.assert_frame_equal(data1, data2)

    def test_different_seeds_produce_different_data(self):
        """Test that different seeds produce different data."""
        generator1 = MarketDataGenerator(seed=42)
        generator2 = MarketDataGenerator(seed=123)

        data1 = generator1.generate_ohlcv_data(symbol="EURUSD", periods=100)
        data2 = generator2.generate_ohlcv_data(symbol="EURUSD", periods=100)

        # Should be different
        assert not data1["close"].equals(data2["close"])


class TestPerformance:
    """Test performance of data generation."""

    def test_large_data_generation_performance(self, market_data_generator):
        """Test performance with large datasets."""
        import time

        start_time = time.time()

        # Generate 1 year of 1-minute data (525,600 bars)
        large_data = market_data_generator.generate_ohlcv_data(
            symbol="EURUSD",
            periods=10000,  # Reduced for testing
            timeframe="1M",
        )

        generation_time = time.time() - start_time

        assert len(large_data) == 10000
        assert (
            generation_time < 5.0
        ), f"Generation took {generation_time:.2f}s, should be < 5s"

    def test_tick_generation_performance(self, market_data_generator):
        """Test tick generation performance."""
        import time

        start_time = time.time()

        # Generate 1 hour of active tick data
        ticks = market_data_generator.generate_tick_data(
            symbol="EURUSD",
            duration_minutes=60,
            avg_ticks_per_minute=100,  # High frequency
        )

        generation_time = time.time() - start_time

        assert len(ticks) > 1000
        assert (
            generation_time < 3.0
        ), f"Tick generation took {generation_time:.2f}s, should be < 3s"


# Integration test to verify fixtures work together
class TestFixtureIntegration:
    """Test that fixtures work well together."""

    def test_multiple_fixtures_together(
        self,
        sample_ohlcv_data,
        sample_tick_data,
        economic_indicators,
        chart_patterns,
    ):
        """Test using multiple fixtures in the same test."""
        # All fixtures should provide valid data
        assert len(sample_ohlcv_data) > 0
        assert len(sample_tick_data) > 0
        assert len(economic_indicators) > 0
        assert len(chart_patterns) > 0

        # Verify data quality
        ohlcv_integrity = validate_market_data_integrity(sample_ohlcv_data)
        assert all(ohlcv_integrity.values())

        # Verify tick data structure
        assert all("bid" in tick for tick in sample_tick_data[:5])
        assert all("ask" in tick for tick in sample_tick_data[:5])

        # Verify economic indicators
        assert "us_interest_rate" in economic_indicators.columns

        # Verify patterns
        assert "head_shoulders" in chart_patterns

        print(f"Integration test passed:")
        print(f"  - OHLCV data: {len(sample_ohlcv_data)} bars")
        print(f"  - Tick data: {len(sample_tick_data)} ticks")
        print(f"  - Economic indicators: {len(economic_indicators)} entries")
        print(f"  - Chart patterns: {len(chart_patterns)} patterns")
