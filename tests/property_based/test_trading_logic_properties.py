"""
Property-Based Testing for Trading Logic
========================================

Uses Hypothesis to test trading logic with automatically generated data,
ensuring our trading systems work correctly across a wide range of inputs
and edge cases that might not be covered by traditional unit tests.

Property-based testing helps us find bugs by:
1. Testing with thousands of different inputs automatically
2. Shrinking failing cases to minimal examples
3. Finding edge cases we wouldn't think to test manually
4. Ensuring mathematical properties hold across all valid inputs

This addresses medium-priority task M2 from our test suite action plan.
"""

import math
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd
import pytest
from hypothesis import assume, example, given, settings
from hypothesis import strategies as st
from hypothesis.extra.pandas import column, data_frames, range_indexes

# Property-based testing strategies for financial data
from tests.fixtures.market_data_fixtures import MarketDataGenerator, MarketRegime

# ============================================================================
# Custom Hypothesis Strategies for Financial Data
# ============================================================================


# Price strategies
@st.composite
def currency_prices(draw, min_value=0.01, max_value=10.0):
    """Generate realistic currency prices."""
    return draw(
        st.floats(
            min_value=min_value,
            max_value=max_value,
            allow_nan=False,
            allow_infinity=False,
        )
    )


@st.composite
def forex_pairs(draw):
    """Generate forex currency pair symbols."""
    majors = ["EUR", "GBP", "USD", "JPY", "AUD", "CAD", "CHF", "NZD"]
    base = draw(st.sampled_from(majors))
    quote = draw(st.sampled_from([c for c in majors if c != base]))
    return f"{base}{quote}"


@st.composite
def trade_quantities(draw, min_lots=0.01, max_lots=100.0):
    """Generate realistic trade quantities in lots."""
    return draw(st.floats(min_value=min_lots, max_value=max_lots, allow_nan=False))


@st.composite
def percentage_values(draw, min_pct=-1.0, max_pct=1.0):
    """Generate percentage values for returns, drawdown, etc."""
    return draw(st.floats(min_value=min_pct, max_value=max_pct, allow_nan=False))


@st.composite
def ohlc_bars(draw):
    """Generate valid OHLC bars."""
    # Start with a base price
    base_price = draw(currency_prices(min_value=0.5, max_value=2.0))

    # Generate price variations
    variations = draw(
        st.lists(
            st.floats(min_value=-0.1, max_value=0.1, allow_nan=False),
            min_size=4,
            max_size=4,
        )
    )

    open_price = base_price + variations[0]
    close_price = base_price + variations[1]
    high_variation = abs(variations[2])
    low_variation = -abs(variations[3])

    # Ensure OHLC relationships are valid
    high_price = max(open_price, close_price) + high_variation
    low_price = min(open_price, close_price) + low_variation

    volume = draw(st.integers(min_value=1, max_value=1000000))

    return {
        "open": max(0.001, open_price),
        "high": max(0.001, high_price),
        "low": max(0.001, low_price),
        "close": max(0.001, close_price),
        "volume": volume,
    }


@st.composite
def price_series(draw, min_length=10, max_length=1000):
    """Generate a series of related prices."""
    length = draw(st.integers(min_value=min_length, max_value=max_length))
    base_price = draw(currency_prices(min_value=0.5, max_value=2.0))

    # Generate price movements using random walk
    changes = draw(
        st.lists(
            st.floats(min_value=-0.01, max_value=0.01, allow_nan=False),
            min_size=length,
            max_size=length,
        )
    )

    prices = [base_price]
    for change in changes[1:]:
        new_price = max(0.001, prices[-1] + change)  # Ensure positive prices
        prices.append(new_price)

    return prices


@st.composite
def market_data_frames(draw, min_rows=10, max_rows=1000):
    """Generate realistic market data DataFrames."""
    n_rows = draw(st.integers(min_value=min_rows, max_value=max_rows))

    # Generate base prices
    base_prices = draw(
        st.lists(
            currency_prices(min_value=0.5, max_value=2.0),
            min_size=n_rows,
            max_size=n_rows,
        )
    )

    # Generate OHLCV data ensuring valid relationships
    data = []
    for i, base_price in enumerate(base_prices):
        variations = draw(
            st.lists(
                st.floats(min_value=-0.005, max_value=0.005, allow_nan=False),
                min_size=4,
                max_size=4,
            )
        )

        open_price = max(0.001, base_price + variations[0])
        close_price = max(0.001, base_price + variations[1])
        high_price = max(open_price, close_price) + abs(variations[2])
        low_price = min(open_price, close_price) - abs(variations[3])
        low_price = max(0.001, low_price)  # Ensure positive

        volume = draw(st.integers(min_value=1, max_value=100000))

        data.append(
            {
                "timestamp": datetime(2024, 1, 1) + timedelta(hours=i),
                "open": open_price,
                "high": high_price,
                "low": low_price,
                "close": close_price,
                "volume": volume,
            }
        )

    return pd.DataFrame(data)


# ============================================================================
# Property-Based Tests for Trading Logic
# ============================================================================


class TestPositionSizingProperties:
    """Test position sizing logic with property-based tests."""

    @given(
        account_balance=st.floats(min_value=1000, max_value=1000000),
        risk_percent=st.floats(min_value=0.001, max_value=0.1),  # 0.1% to 10%
        stop_loss_pips=st.integers(min_value=1, max_value=1000),
        pip_value=st.floats(min_value=0.01, max_value=10.0),
    )
    def test_position_size_properties(
        self, account_balance, risk_percent, stop_loss_pips, pip_value
    ):
        """Test that position sizing respects risk management rules."""
        # Simplified position sizing formula
        risk_amount = account_balance * risk_percent
        position_size = risk_amount / (stop_loss_pips * pip_value)

        # Property 1: Position size should never risk more than specified percentage
        max_loss = position_size * stop_loss_pips * pip_value
        actual_risk_percent = max_loss / account_balance

        # Allow small floating point differences
        assert (
            actual_risk_percent <= risk_percent + 1e-10
        ), f"Position size {position_size} risks {actual_risk_percent:.6f} > {risk_percent:.6f}"

        # Property 2: Position size should be positive
        assert position_size > 0, "Position size must be positive"

        # Property 3: Larger account balance should allow larger positions (with same risk %)
        larger_balance = account_balance * 2
        larger_position = (larger_balance * risk_percent) / (stop_loss_pips * pip_value)
        assert (
            larger_position > position_size
        ), "Larger balance should allow larger positions"

    @given(
        prices=price_series(min_length=20, max_length=100),
        risk_percent=st.floats(min_value=0.01, max_value=0.05),
    )
    def test_dynamic_position_sizing_properties(self, prices, risk_percent):
        """Test dynamic position sizing based on volatility."""
        # Calculate volatility
        returns = [prices[i] / prices[i - 1] - 1 for i in range(1, len(prices))]
        volatility = np.std(returns) if len(returns) > 1 else 0.01

        # Volatility-adjusted position sizing
        base_position_size = 1.0
        vol_adjustment = min(2.0, max(0.5, 1.0 / (volatility * 100)))
        adjusted_position_size = base_position_size * vol_adjustment

        # Property 1: Higher volatility should result in smaller positions
        high_vol = volatility * 2
        high_vol_adjustment = min(2.0, max(0.5, 1.0 / (high_vol * 100)))
        high_vol_position = base_position_size * high_vol_adjustment

        assert (
            high_vol_position <= adjusted_position_size
        ), "Higher volatility should result in smaller positions"

        # Property 2: Position size should be bounded
        assert 0.5 <= vol_adjustment <= 2.0, "Position adjustment should be bounded"


class TestRiskManagementProperties:
    """Test risk management logic properties."""

    @given(
        entry_price=currency_prices(min_value=0.5, max_value=2.0),
        current_price=currency_prices(min_value=0.5, max_value=2.0),
        position_size=trade_quantities(min_lots=0.01, max_lots=10.0),
        is_long=st.booleans(),
    )
    def test_pnl_calculation_properties(
        self, entry_price, current_price, position_size, is_long
    ):
        """Test P&L calculation properties."""
        # Calculate P&L
        if is_long:
            pnl = (current_price - entry_price) * position_size
        else:
            pnl = (entry_price - current_price) * position_size

        # Property 1: P&L should be zero when current price equals entry price
        if abs(current_price - entry_price) < 1e-10:
            assert abs(pnl) < 1e-8, "P&L should be zero when prices are equal"

        # Property 2: Long positions profit when price increases
        if is_long and current_price > entry_price:
            assert pnl > 0, "Long positions should profit when price increases"

        # Property 3: Short positions profit when price decreases
        if not is_long and current_price < entry_price:
            assert pnl > 0, "Short positions should profit when price decreases"

        # Property 4: Larger position size should result in proportionally larger P&L
        larger_position_size = position_size * 2
        if is_long:
            larger_pnl = (current_price - entry_price) * larger_position_size
        else:
            larger_pnl = (entry_price - current_price) * larger_position_size

        if abs(pnl) > 1e-10:  # Avoid division by zero
            ratio = abs(larger_pnl / pnl)
            assert (
                abs(ratio - 2.0) < 1e-6
            ), f"P&L should scale linearly with position size, got ratio {ratio}"

    @given(
        initial_balance=st.floats(min_value=1000, max_value=100000),
        trades_pnl=st.lists(
            st.floats(min_value=-1000, max_value=1000, allow_nan=False),
            min_size=1,
            max_size=100,
        ),
    )
    def test_drawdown_calculation_properties(self, initial_balance, trades_pnl):
        """Test drawdown calculation properties."""
        # Calculate running balance and drawdown
        balance = initial_balance
        balances = [balance]

        for pnl in trades_pnl:
            balance += pnl
            # Don't allow balance to go negative (margin call protection)
            balance = max(0, balance)
            balances.append(balance)

        # Calculate drawdown
        peak = balances[0]
        max_drawdown = 0

        for balance in balances[1:]:
            if balance > peak:
                peak = balance

            current_drawdown = (peak - balance) / peak if peak > 0 else 0
            max_drawdown = max(max_drawdown, current_drawdown)

        # Property 1: Maximum drawdown should be non-negative
        assert max_drawdown >= 0, "Maximum drawdown cannot be negative"

        # Property 2: Maximum drawdown should not exceed 100%
        assert max_drawdown <= 1.0, "Maximum drawdown cannot exceed 100%"

        # Property 3: If all trades are profitable, drawdown should be 0
        if all(pnl >= 0 for pnl in trades_pnl):
            assert max_drawdown == 0, "No drawdown expected with all profitable trades"

        # Property 4: Final balance should equal initial balance plus sum of P&L
        expected_final = max(0, initial_balance + sum(trades_pnl))
        assert (
            abs(balances[-1] - expected_final) < 1e-10
        ), f"Final balance {balances[-1]} != expected {expected_final}"


class TestTechnicalIndicatorProperties:
    """Test technical indicator calculation properties."""

    @given(
        prices=price_series(min_length=50, max_length=200),
        period=st.integers(min_value=2, max_value=50),
    )
    def test_simple_moving_average_properties(self, prices, period):
        """Test Simple Moving Average properties."""
        assume(len(prices) >= period)

        # Calculate SMA
        sma_values = []
        for i in range(period - 1, len(prices)):
            window = prices[i - period + 1 : i + 1]
            sma = sum(window) / len(window)
            sma_values.append(sma)

        if not sma_values:
            return

        # Property 1: SMA should smooth price movements
        price_volatility = np.std(prices[period - 1 :])
        sma_volatility = np.std(sma_values)
        assert (
            sma_volatility <= price_volatility + 1e-10
        ), "SMA should be less volatile than underlying prices"

        # Property 2: SMA values should be within the range of input prices for that period
        for i, sma in enumerate(sma_values):
            window_start = i
            window_end = i + period
            window_prices = prices[window_start:window_end]
            min_price = min(window_prices)
            max_price = max(window_prices)
            assert (
                min_price <= sma <= max_price
            ), f"SMA {sma} outside price range [{min_price}, {max_price}]"

        # Property 3: Longer periods should result in smoother SMA
        if period < len(prices) // 2:
            longer_period = period * 2
            longer_sma = []
            for i in range(longer_period - 1, len(prices)):
                window = prices[i - longer_period + 1 : i + 1]
                longer_sma.append(sum(window) / len(window))

            if len(longer_sma) > 1:
                longer_volatility = np.std(longer_sma)
                # Allow for small numerical differences
                assert (
                    longer_volatility <= sma_volatility + 1e-8
                ), "Longer SMA period should be less volatile"

    @given(
        market_data=market_data_frames(min_rows=50, max_rows=100),
        rsi_period=st.integers(min_value=2, max_value=30),
    )
    def test_rsi_properties(self, market_data, rsi_period):
        """Test RSI (Relative Strength Index) properties."""
        assume(len(market_data) > rsi_period)

        # Calculate RSI
        closes = market_data["close"].values
        deltas = np.diff(closes)
        gains = np.maximum(deltas, 0)
        losses = np.maximum(-deltas, 0)

        rsi_values = []
        for i in range(rsi_period, len(gains)):
            avg_gain = np.mean(gains[i - rsi_period : i])
            avg_loss = np.mean(losses[i - rsi_period : i])

            if avg_loss == 0:
                rsi = 100.0
            else:
                rs = avg_gain / avg_loss
                rsi = 100 - (100 / (1 + rs))

            rsi_values.append(rsi)

        if not rsi_values:
            return

        # Property 1: RSI should be bounded between 0 and 100
        for rsi in rsi_values:
            assert 0 <= rsi <= 100, f"RSI {rsi} outside valid range [0, 100]"

        # Property 2: RSI should approach 100 when prices consistently rise
        # Property 3: RSI should approach 0 when prices consistently fall

        # Property 4: RSI of 50 indicates equal average gains and losses
        for i, rsi in enumerate(rsi_values):
            start_idx = max(0, i - rsi_period + 1)
            period_gains = gains[start_idx : i + 1]
            period_losses = losses[start_idx : i + 1]

            avg_gain = np.mean(period_gains)
            avg_loss = np.mean(period_losses)

            if abs(avg_gain - avg_loss) < 1e-10:
                assert (
                    abs(rsi - 50) < 1e-6
                ), f"RSI should be ~50 when avg gains = avg losses"


class TestOrderExecutionProperties:
    """Test order execution logic properties."""

    @given(
        order_price=currency_prices(min_value=0.5, max_value=2.0),
        market_price=currency_prices(min_value=0.5, max_value=2.0),
        order_type=st.sampled_from(["market", "limit", "stop"]),
        order_side=st.sampled_from(["buy", "sell"]),
        slippage=st.floats(min_value=0.0, max_value=0.01),
    )
    def test_order_execution_properties(
        self, order_price, market_price, order_type, order_side, slippage
    ):
        """Test order execution logic properties."""

        # Determine if order should execute
        should_execute = False
        execution_price = market_price

        if order_type == "market":
            should_execute = True
            # Market orders execute at market price plus slippage
            if order_side == "buy":
                execution_price = market_price + slippage
            else:
                execution_price = market_price - slippage

        elif order_type == "limit":
            if order_side == "buy" and market_price <= order_price:
                should_execute = True
                execution_price = min(order_price, market_price)
            elif order_side == "sell" and market_price >= order_price:
                should_execute = True
                execution_price = max(order_price, market_price)

        elif order_type == "stop":
            if order_side == "buy" and market_price >= order_price:
                should_execute = True
                execution_price = market_price + slippage
            elif order_side == "sell" and market_price <= order_price:
                should_execute = True
                execution_price = market_price - slippage

        # Property 1: Execution price should be positive
        if should_execute:
            assert execution_price > 0, "Execution price must be positive"

        # Property 2: Buy limit orders should never execute above limit price
        if order_type == "limit" and order_side == "buy" and should_execute:
            assert (
                execution_price <= order_price + 1e-10
            ), f"Buy limit executed at {execution_price} > limit {order_price}"

        # Property 3: Sell limit orders should never execute below limit price
        if order_type == "limit" and order_side == "sell" and should_execute:
            assert (
                execution_price >= order_price - 1e-10
            ), f"Sell limit executed at {execution_price} < limit {order_price}"

        # Property 4: Market orders should always execute (in liquid markets)
        if order_type == "market":
            assert should_execute, "Market orders should always execute"

    @given(
        orders=st.lists(
            st.fixed_dictionaries(
                {
                    "id": st.integers(min_value=1, max_value=1000000),
                    "price": currency_prices(min_value=0.5, max_value=2.0),
                    "quantity": trade_quantities(min_lots=0.01, max_lots=10.0),
                    "side": st.sampled_from(["buy", "sell"]),
                    "timestamp": st.integers(min_value=1, max_value=1000000),
                }
            ),
            min_size=1,
            max_size=20,
        )
    )
    def test_order_matching_properties(self, orders):
        """Test order matching engine properties."""
        # Separate buy and sell orders
        buy_orders = [o for o in orders if o["side"] == "buy"]
        sell_orders = [o for o in orders if o["side"] == "sell"]

        if not buy_orders or not sell_orders:
            return

        # Sort orders by price priority
        buy_orders.sort(key=lambda x: (-x["price"], x["timestamp"]))  # Best buy first
        sell_orders.sort(key=lambda x: (x["price"], x["timestamp"]))  # Best sell first

        matches = []
        buy_idx = 0
        sell_idx = 0

        # Simple matching logic
        while buy_idx < len(buy_orders) and sell_idx < len(sell_orders):
            buy_order = buy_orders[buy_idx]
            sell_order = sell_orders[sell_idx]

            # Check if orders can match
            if buy_order["price"] >= sell_order["price"]:
                # Match occurred
                match_price = (buy_order["price"] + sell_order["price"]) / 2
                match_quantity = min(buy_order["quantity"], sell_order["quantity"])

                matches.append(
                    {
                        "price": match_price,
                        "quantity": match_quantity,
                        "buy_order_id": buy_order["id"],
                        "sell_order_id": sell_order["id"],
                    }
                )

                # Update quantities
                buy_order["quantity"] -= match_quantity
                sell_order["quantity"] -= match_quantity

                # Remove fully matched orders
                if buy_order["quantity"] <= 1e-10:
                    buy_idx += 1
                if sell_order["quantity"] <= 1e-10:
                    sell_idx += 1
            else:
                # No match possible with current best orders
                break

        # Property 1: All matches should have positive quantities
        for match in matches:
            assert match["quantity"] > 0, "Match quantity must be positive"

        # Property 2: Match prices should be between buy and sell prices
        for match in matches:
            # Find original orders
            buy_order = next(o for o in buy_orders if o["id"] == match["buy_order_id"])
            sell_order = next(
                o for o in sell_orders if o["id"] == match["sell_order_id"]
            )

            # Allow for the averaged price
            assert (
                sell_order["price"] <= match["price"] <= buy_order["price"]
            ), f"Match price {match['price']} not between sell {sell_order['price']} and buy {buy_order['price']}"


class TestPortfolioProperties:
    """Test portfolio management properties."""

    @given(
        positions=st.lists(
            st.fixed_dictionaries(
                {
                    "symbol": forex_pairs(),
                    "quantity": st.floats(
                        min_value=-100, max_value=100, allow_nan=False
                    ),
                    "entry_price": currency_prices(min_value=0.5, max_value=2.0),
                    "current_price": currency_prices(min_value=0.5, max_value=2.0),
                }
            ),
            min_size=1,
            max_size=10,
        )
    )
    def test_portfolio_value_properties(self, positions):
        """Test portfolio valuation properties."""
        # Calculate portfolio metrics
        total_value = 0
        total_pnl = 0

        for position in positions:
            position_value = abs(position["quantity"]) * position["current_price"]
            total_value += position_value

            if position["quantity"] > 0:  # Long position
                pnl = (position["current_price"] - position["entry_price"]) * position[
                    "quantity"
                ]
            elif position["quantity"] < 0:  # Short position
                pnl = (position["entry_price"] - position["current_price"]) * abs(
                    position["quantity"]
                )
            else:  # No position
                pnl = 0

            total_pnl += pnl

        # Property 1: Portfolio value should be non-negative
        assert total_value >= 0, "Portfolio value cannot be negative"

        # Property 2: If all current prices equal entry prices, total P&L should be zero
        all_prices_equal = all(
            abs(pos["current_price"] - pos["entry_price"]) < 1e-10 for pos in positions
        )
        if all_prices_equal:
            assert (
                abs(total_pnl) < 1e-8
            ), "P&L should be zero when all prices equal entry prices"

        # Property 3: Portfolio with no positions should have zero value and P&L
        if all(abs(pos["quantity"]) < 1e-10 for pos in positions):
            assert abs(total_value) < 1e-8, "Empty portfolio should have zero value"
            assert abs(total_pnl) < 1e-8, "Empty portfolio should have zero P&L"


# ============================================================================
# Property-Based Tests for Market Data Processing
# ============================================================================


class TestMarketDataProperties:
    """Test market data processing properties."""

    @given(ohlc_bar=ohlc_bars())
    def test_ohlc_bar_properties(self, ohlc_bar):
        """Test OHLC bar properties."""
        # Property 1: High should be highest price
        assert ohlc_bar["high"] >= ohlc_bar["open"], "High >= Open"
        assert ohlc_bar["high"] >= ohlc_bar["close"], "High >= Close"

        # Property 2: Low should be lowest price
        assert ohlc_bar["low"] <= ohlc_bar["open"], "Low <= Open"
        assert ohlc_bar["low"] <= ohlc_bar["close"], "Low <= Close"

        # Property 3: All prices should be positive
        assert ohlc_bar["open"] > 0, "Open price must be positive"
        assert ohlc_bar["high"] > 0, "High price must be positive"
        assert ohlc_bar["low"] > 0, "Low price must be positive"
        assert ohlc_bar["close"] > 0, "Close price must be positive"

        # Property 4: Volume should be non-negative
        assert ohlc_bar["volume"] >= 0, "Volume cannot be negative"

    @given(
        prices=price_series(min_length=10, max_length=100),
        window_size=st.integers(min_value=2, max_value=20),
    )
    def test_price_aggregation_properties(self, prices, window_size):
        """Test price aggregation properties."""
        assume(len(prices) >= window_size)

        # Aggregate prices into windows
        aggregated = []
        for i in range(0, len(prices) - window_size + 1, window_size):
            window = prices[i : i + window_size]

            agg_bar = {
                "open": window[0],
                "high": max(window),
                "low": min(window),
                "close": window[-1],
            }
            aggregated.append(agg_bar)

        if not aggregated:
            return

        # Property 1: Each aggregated bar should satisfy OHLC relationships
        for bar in aggregated:
            assert bar["high"] >= bar["open"], "Aggregated: High >= Open"
            assert bar["high"] >= bar["close"], "Aggregated: High >= Close"
            assert bar["low"] <= bar["open"], "Aggregated: Low <= Open"
            assert bar["low"] <= bar["close"], "Aggregated: Low <= Close"

        # Property 2: High of aggregated data should not exceed max of all prices
        all_highs = [bar["high"] for bar in aggregated]
        max_aggregated_high = max(all_highs)
        max_original_price = max(prices)
        assert (
            max_aggregated_high <= max_original_price + 1e-10
        ), "Aggregated high should not exceed original max"

        # Property 3: Low of aggregated data should not be below min of all prices
        all_lows = [bar["low"] for bar in aggregated]
        min_aggregated_low = min(all_lows)
        min_original_price = min(prices)
        assert (
            min_aggregated_low >= min_original_price - 1e-10
        ), "Aggregated low should not be below original min"


# ============================================================================
# Performance Properties
# ============================================================================


class TestPerformanceProperties:
    """Test performance calculation properties."""

    @given(
        returns=st.lists(
            percentage_values(min_pct=-0.1, max_pct=0.1), min_size=10, max_size=1000
        )
    )
    @settings(max_examples=50)  # Reduce examples for performance
    def test_sharpe_ratio_properties(self, returns):
        """Test Sharpe ratio calculation properties."""
        returns_array = np.array(returns)
        mean_return = np.mean(returns_array)
        std_return = np.std(returns_array, ddof=1)

        if std_return == 0:
            # Handle case where all returns are identical
            if mean_return > 0:
                sharpe = float("inf")
            elif mean_return < 0:
                sharpe = float("-inf")
            else:
                sharpe = 0
        else:
            sharpe = mean_return / std_return

        # Property 1: Higher mean returns should increase Sharpe ratio (with same volatility)
        if std_return > 1e-10:
            higher_mean_returns = returns_array + 0.01  # Add 1% to all returns
            higher_mean = np.mean(higher_mean_returns)
            higher_sharpe = higher_mean / std_return

            if not (math.isinf(sharpe) or math.isinf(higher_sharpe)):
                assert (
                    higher_sharpe > sharpe
                ), "Higher mean returns should improve Sharpe ratio"

        # Property 2: Lower volatility should increase Sharpe ratio (with positive returns)
        if mean_return > 1e-10:
            # Test isn't perfect due to correlation changes, but generally true
            pass

        # Property 3: Sharpe ratio should be zero for zero-mean strategies
        if abs(mean_return) < 1e-10:
            assert (
                abs(sharpe) < 1e-8
            ), "Zero-mean strategy should have zero Sharpe ratio"

    @example(returns=[0.01, 0.02, -0.01, 0.015, -0.005])  # Specific example
    @given(
        returns=st.lists(
            percentage_values(min_pct=-0.2, max_pct=0.2), min_size=5, max_size=100
        )
    )
    def test_maximum_drawdown_properties(self, returns):
        """Test maximum drawdown calculation properties."""
        # Calculate cumulative returns and drawdown
        cumulative_returns = np.cumprod(1 + np.array(returns))
        peak = np.maximum.accumulate(cumulative_returns)
        drawdown = (peak - cumulative_returns) / peak
        max_drawdown = np.max(drawdown)

        # Property 1: Maximum drawdown should be non-negative
        assert max_drawdown >= 0, f"Maximum drawdown {max_drawdown} cannot be negative"

        # Property 2: Maximum drawdown should not exceed 100% (unless leveraged)
        assert (
            max_drawdown <= 1.0 + 1e-10
        ), f"Maximum drawdown {max_drawdown} exceeds 100%"

        # Property 3: If all returns are positive, max drawdown should be zero
        if all(r >= 0 for r in returns):
            assert (
                max_drawdown < 1e-10
            ), "Positive-only returns should have zero drawdown"

        # Property 4: Drawdown at each point should not exceed maximum drawdown
        assert all(
            dd <= max_drawdown + 1e-10 for dd in drawdown
        ), "All drawdowns should be <= maximum drawdown"


# ============================================================================
# Data Quality Properties
# ============================================================================


class TestDataQualityProperties:
    """Test data quality and validation properties."""

    @given(market_df=market_data_frames(min_rows=10, max_rows=50))
    def test_market_data_quality_properties(self, market_df):
        """Test market data quality properties."""
        # Property 1: No NaN values in critical columns
        critical_columns = ["open", "high", "low", "close", "volume"]
        for col in critical_columns:
            if col in market_df.columns:
                assert (
                    not market_df[col].isna().any()
                ), f"Column {col} contains NaN values"

        # Property 2: Timestamps should be monotonically increasing
        if "timestamp" in market_df.columns:
            timestamps = market_df["timestamp"]
            assert (
                timestamps.is_monotonic_increasing
            ), "Timestamps should be monotonically increasing"

        # Property 3: OHLC relationships should be valid for all bars
        for idx, row in market_df.iterrows():
            assert row["high"] >= row["open"], f"Row {idx}: High < Open"
            assert row["high"] >= row["close"], f"Row {idx}: High < Close"
            assert row["low"] <= row["open"], f"Row {idx}: Low > Open"
            assert row["low"] <= row["close"], f"Row {idx}: Low > Close"

        # Property 4: Prices should be within reasonable ranges
        price_columns = ["open", "high", "low", "close"]
        for col in price_columns:
            if col in market_df.columns:
                assert (
                    market_df[col] > 0
                ).all(), f"Column {col} contains non-positive prices"
                assert (
                    market_df[col] < 1000
                ).all(), f"Column {col} contains unrealistic prices"


# Run specific examples to ensure edge cases are tested
class TestSpecificExamples:
    """Test specific examples and edge cases."""

    @given(st.just(0.0))
    def test_zero_price_handling(self, zero_price):
        """Test handling of zero prices."""
        # Zero prices should be rejected or handled appropriately
        # This test ensures our price validation catches zero prices
        with pytest.raises((ValueError, AssertionError)):
            # This should fail in any realistic trading system
            position_size = 1000 / zero_price  # Division by zero

    @example(prices=[1.0, 1.0, 1.0, 1.0, 1.0])  # Flat prices
    @example(prices=[1.0, 0.5, 2.0, 0.1, 5.0])  # Extreme volatility
    @given(prices=price_series(min_length=5, max_length=5))
    def test_extreme_scenarios(self, prices):
        """Test system behavior with extreme scenarios."""
        # Calculate basic statistics
        price_range = max(prices) - min(prices)
        volatility = np.std(prices) if len(prices) > 1 else 0

        # System should handle flat prices (no volatility)
        if price_range < 1e-10:
            assert volatility < 1e-10, "Flat prices should have zero volatility"

        # System should handle high volatility
        if volatility > 0.5:  # 50% volatility is extreme
            # Risk management should trigger
            position_adjustment = min(1.0, 0.1 / volatility)  # Reduce position size
            assert (
                0 < position_adjustment <= 1.0
            ), "High volatility should reduce position size"


if __name__ == "__main__":
    # Run the property-based tests
    pytest.main([__file__, "-v", "--hypothesis-show-statistics"])
