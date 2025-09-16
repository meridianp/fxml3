"""
TDD Integration Tests for Interactive Brokers Adapter

Comprehensive test suite for IB adapter functionality following TDD principles.
Tests real broker integration with proper mocking for CI/CD.
"""

import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pandas as pd
import pytest


@pytest.mark.tdd
@pytest.mark.integration
@pytest.mark.broker
class TestInteractiveBrokersAdapter:
    """
    Integration tests for Interactive Brokers adapter.

    These tests verify the complete integration with IB API,
    including connection, order execution, and market data.
    """

    @pytest.fixture
    def ib_config(self):
        """IB connection configuration."""
        return {
            "host": "127.0.0.1",
            "port": 7497,  # Paper trading port
            "client_id": 999,
            "account": "DU123456",
            "timeout": 10,
            "market_data_type": 3,  # Delayed data
        }

    @pytest.fixture
    def mock_ib_client(self):
        """Mock IB API client."""
        client = MagicMock()
        client.connect = MagicMock(return_value=True)
        client.disconnect = MagicMock()
        client.isConnected = MagicMock(return_value=True)
        client.reqAccountSummary = MagicMock()
        client.placeOrder = MagicMock()
        client.reqMktData = MagicMock()
        client.reqPositions = MagicMock()
        return client

    @pytest.fixture
    async def ib_adapter(self, ib_config, mock_ib_client):
        """Create IB adapter instance."""
        with patch("core.brokers.ib_adapter.IBApi") as mock_api:
            mock_api.return_value = mock_ib_client

            from core.brokers.ib_adapter import InteractiveBrokersAdapter

            adapter = InteractiveBrokersAdapter(config=ib_config)
            await adapter.connect()
            yield adapter
            await adapter.disconnect()

    # -------------------------------------------------------------------------
    # Connection and Authentication Tests
    # -------------------------------------------------------------------------

    @pytest.mark.red
    async def test_connection_establishment(self, ib_config):
        """RED: Test establishing connection to IB Gateway/TWS."""
        from core.brokers.ib_adapter import InteractiveBrokersAdapter

        adapter = InteractiveBrokersAdapter(config=ib_config)

        # Test connection
        connected = await adapter.connect()
        assert connected is True
        assert adapter.is_connected() is True

        # Test disconnection
        await adapter.disconnect()
        assert adapter.is_connected() is False

    @pytest.mark.red
    async def test_connection_retry_logic(self, ib_config, mock_ib_client):
        """RED: Test connection retry with exponential backoff."""
        mock_ib_client.connect.side_effect = [
            Exception("Connection failed"),
            Exception("Still failing"),
            True,  # Success on third attempt
        ]

        with patch("core.brokers.ib_adapter.IBApi") as mock_api:
            mock_api.return_value = mock_ib_client

            from core.brokers.ib_adapter import InteractiveBrokersAdapter

            adapter = InteractiveBrokersAdapter(config=ib_config)

            connected = await adapter.connect(max_retries=3)
            assert connected is True
            assert mock_ib_client.connect.call_count == 3

    @pytest.mark.red
    async def test_connection_heartbeat(self, ib_adapter, mock_ib_client):
        """RED: Test connection heartbeat monitoring."""
        # Simulate heartbeat
        await asyncio.sleep(0.1)

        # Check heartbeat called
        mock_ib_client.reqCurrentTime.assert_called()

        # Simulate connection loss
        mock_ib_client.isConnected.return_value = False
        is_alive = await ib_adapter.check_connection_health()
        assert is_alive is False

    # -------------------------------------------------------------------------
    # Account Information Tests
    # -------------------------------------------------------------------------

    @pytest.mark.red
    async def test_get_account_summary(self, ib_adapter, mock_ib_client):
        """RED: Test retrieving account summary."""
        # Mock account data
        mock_ib_client.account_data = {
            "NetLiquidation": 100000.00,
            "TotalCashValue": 50000.00,
            "UnrealizedPnL": 1500.00,
            "RealizedPnL": 500.00,
            "BuyingPower": 400000.00,
        }

        account_info = await ib_adapter.get_account_summary()

        assert account_info["balance"] == 100000.00
        assert account_info["cash"] == 50000.00
        assert account_info["unrealized_pnl"] == 1500.00
        assert account_info["buying_power"] == 400000.00

    @pytest.mark.red
    async def test_get_positions(self, ib_adapter, mock_ib_client):
        """RED: Test retrieving current positions."""
        # Mock positions
        mock_positions = [
            {
                "symbol": "EUR.USD",
                "position": 100000,
                "avg_cost": 1.0850,
                "market_price": 1.0860,
                "unrealized_pnl": 100.00,
            },
            {
                "symbol": "GBP.USD",
                "position": -50000,
                "avg_cost": 1.2500,
                "market_price": 1.2480,
                "unrealized_pnl": 100.00,
            },
        ]

        mock_ib_client.positions = mock_positions
        positions = await ib_adapter.get_positions()

        assert len(positions) == 2
        assert positions[0]["symbol"] == "EUR.USD"
        assert positions[0]["quantity"] == 100000
        assert positions[1]["unrealized_pnl"] == 100.00

    # -------------------------------------------------------------------------
    # Order Execution Tests
    # -------------------------------------------------------------------------

    @pytest.mark.red
    async def test_place_market_order(self, ib_adapter, mock_ib_client):
        """RED: Test placing market order."""
        # Prepare order
        order_params = {
            "symbol": "EUR.USD",
            "action": "BUY",
            "quantity": 100000,
            "order_type": "MARKET",
        }

        # Mock order response
        mock_ib_client.next_order_id = 1001
        mock_ib_client.order_status = {
            1001: {
                "status": "Filled",
                "filled": 100000,
                "avg_fill_price": 1.0855,
                "commission": 2.50,
            }
        }

        # Place order
        order_result = await ib_adapter.place_order(**order_params)

        assert order_result["order_id"] == 1001
        assert order_result["status"] == "Filled"
        assert order_result["filled_quantity"] == 100000
        assert order_result["avg_price"] == 1.0855

    @pytest.mark.red
    async def test_place_limit_order(self, ib_adapter, mock_ib_client):
        """RED: Test placing limit order."""
        order_params = {
            "symbol": "EUR.USD",
            "action": "SELL",
            "quantity": 50000,
            "order_type": "LIMIT",
            "limit_price": 1.0870,
        }

        mock_ib_client.next_order_id = 1002
        mock_ib_client.order_status = {
            1002: {"status": "Submitted", "filled": 0, "remaining": 50000}
        }

        order_result = await ib_adapter.place_order(**order_params)

        assert order_result["order_id"] == 1002
        assert order_result["status"] == "Submitted"
        assert order_result["filled_quantity"] == 0

    @pytest.mark.red
    async def test_place_stop_loss_order(self, ib_adapter, mock_ib_client):
        """RED: Test placing stop loss order."""
        order_params = {
            "symbol": "GBP.USD",
            "action": "SELL",
            "quantity": 75000,
            "order_type": "STOP",
            "stop_price": 1.2450,
            "parent_order_id": 1001,  # Attached to parent order
        }

        mock_ib_client.next_order_id = 1003
        order_result = await ib_adapter.place_order(**order_params)

        assert order_result["order_id"] == 1003
        assert order_result["order_type"] == "STOP"
        assert order_result["stop_price"] == 1.2450

    @pytest.mark.red
    async def test_bracket_order(self, ib_adapter):
        """RED: Test placing bracket order (entry + stop loss + take profit)."""
        bracket_params = {
            "symbol": "EUR.USD",
            "action": "BUY",
            "quantity": 100000,
            "order_type": "MARKET",
            "stop_loss": 1.0820,
            "take_profit": 1.0900,
        }

        orders = await ib_adapter.place_bracket_order(**bracket_params)

        assert len(orders) == 3
        assert orders[0]["order_type"] == "MARKET"  # Parent order
        assert orders[1]["order_type"] == "STOP"  # Stop loss
        assert orders[2]["order_type"] == "LIMIT"  # Take profit

    @pytest.mark.red
    async def test_modify_order(self, ib_adapter, mock_ib_client):
        """RED: Test modifying existing order."""
        order_id = 1002
        modifications = {"limit_price": 1.0875, "quantity": 60000}

        mock_ib_client.order_status[order_id] = {
            "status": "Modified",
            "limit_price": 1.0875,
            "quantity": 60000,
        }

        result = await ib_adapter.modify_order(order_id, **modifications)

        assert result["status"] == "Modified"
        assert result["limit_price"] == 1.0875
        assert result["quantity"] == 60000

    @pytest.mark.red
    async def test_cancel_order(self, ib_adapter, mock_ib_client):
        """RED: Test cancelling order."""
        order_id = 1002

        mock_ib_client.order_status[order_id] = {"status": "Cancelled"}

        result = await ib_adapter.cancel_order(order_id)

        assert result["status"] == "Cancelled"
        mock_ib_client.cancelOrder.assert_called_once_with(order_id)

    # -------------------------------------------------------------------------
    # Market Data Tests
    # -------------------------------------------------------------------------

    @pytest.mark.red
    async def test_subscribe_market_data(self, ib_adapter, mock_ib_client):
        """RED: Test subscribing to real-time market data."""
        symbols = ["EUR.USD", "GBP.USD", "USD.JPY"]

        # Mock market data
        mock_ib_client.market_data = {
            "EUR.USD": {"bid": 1.0850, "ask": 1.0852, "last": 1.0851},
            "GBP.USD": {"bid": 1.2500, "ask": 1.2502, "last": 1.2501},
            "USD.JPY": {"bid": 110.50, "ask": 110.52, "last": 110.51},
        }

        # Subscribe
        await ib_adapter.subscribe_market_data(symbols)

        # Get snapshot
        market_data = await ib_adapter.get_market_snapshot(symbols)

        assert len(market_data) == 3
        assert market_data["EUR.USD"]["bid"] == 1.0850
        assert market_data["GBP.USD"]["spread"] == 0.0002

    @pytest.mark.red
    async def test_streaming_market_data(self, ib_adapter):
        """RED: Test streaming market data with callback."""
        received_ticks = []

        async def on_tick(tick_data):
            received_ticks.append(tick_data)

        # Subscribe with callback
        await ib_adapter.subscribe_market_data(["EUR.USD"], callback=on_tick)

        # Simulate ticks
        await asyncio.sleep(0.5)

        assert len(received_ticks) > 0
        assert all("symbol" in tick for tick in received_ticks)
        assert all("timestamp" in tick for tick in received_ticks)

    @pytest.mark.red
    async def test_get_historical_data(self, ib_adapter, mock_ib_client):
        """RED: Test retrieving historical market data."""
        # Mock historical data
        mock_historical = pd.DataFrame(
            {
                "timestamp": pd.date_range(start="2024-01-01", periods=100, freq="1H"),
                "open": [1.0850 + i * 0.0001 for i in range(100)],
                "high": [1.0860 + i * 0.0001 for i in range(100)],
                "low": [1.0840 + i * 0.0001 for i in range(100)],
                "close": [1.0851 + i * 0.0001 for i in range(100)],
                "volume": [1000000 + i * 1000 for i in range(100)],
            }
        )

        mock_ib_client.historical_data = mock_historical

        # Request historical data
        historical = await ib_adapter.get_historical_data(
            symbol="EUR.USD", duration="1 D", bar_size="1 hour", end_time=datetime.now()
        )

        assert len(historical) == 100
        assert "close" in historical.columns
        assert historical["close"].iloc[-1] > historical["close"].iloc[0]

    # -------------------------------------------------------------------------
    # Risk Management Tests
    # -------------------------------------------------------------------------

    @pytest.mark.red
    async def test_position_size_validation(self, ib_adapter):
        """RED: Test position size limits are enforced."""
        # Try to place order exceeding max size
        oversized_order = {
            "symbol": "EUR.USD",
            "action": "BUY",
            "quantity": 10000000,  # 10M - too large
            "order_type": "MARKET",
        }

        with pytest.raises(ValueError, match="Position size exceeds maximum"):
            await ib_adapter.place_order(**oversized_order)

    @pytest.mark.red
    async def test_margin_requirement_check(self, ib_adapter, mock_ib_client):
        """RED: Test margin requirements are checked before order."""
        mock_ib_client.account_data = {"BuyingPower": 10000.00}  # Low buying power

        large_order = {
            "symbol": "EUR.USD",
            "action": "BUY",
            "quantity": 1000000,  # Requires ~20k margin
            "order_type": "MARKET",
        }

        with pytest.raises(ValueError, match="Insufficient margin"):
            await ib_adapter.place_order(**large_order)

    # -------------------------------------------------------------------------
    # Error Handling Tests
    # -------------------------------------------------------------------------

    @pytest.mark.red
    async def test_handle_connection_loss(self, ib_adapter, mock_ib_client):
        """RED: Test handling of connection loss during operation."""
        # Simulate connection loss
        mock_ib_client.isConnected.return_value = False
        mock_ib_client.placeOrder.side_effect = Exception("Not connected")

        order = {
            "symbol": "EUR.USD",
            "action": "BUY",
            "quantity": 100000,
            "order_type": "MARKET",
        }

        with pytest.raises(ConnectionError, match="Connection lost"):
            await ib_adapter.place_order(**order)

        # Test auto-reconnection
        await ib_adapter.reconnect()
        assert mock_ib_client.connect.called

    @pytest.mark.red
    async def test_handle_api_errors(self, ib_adapter, mock_ib_client):
        """RED: Test handling of IB API errors."""
        # Simulate various API errors
        error_scenarios = [
            (201, "Order rejected - Invalid symbol"),
            (202, "Order cancelled - Insufficient funds"),
            (2106, "Historical data request pacing violation"),
        ]

        for error_code, error_msg in error_scenarios:
            mock_ib_client.error_code = error_code
            mock_ib_client.error_message = error_msg

            error_handled = await ib_adapter.handle_error(error_code, error_msg)
            assert error_handled is True

    # -------------------------------------------------------------------------
    # Performance Tests
    # -------------------------------------------------------------------------

    @pytest.mark.red
    async def test_order_execution_latency(self, ib_adapter, performance_timer):
        """RED: Test order execution latency."""
        order = {
            "symbol": "EUR.USD",
            "action": "BUY",
            "quantity": 100000,
            "order_type": "MARKET",
        }

        performance_timer.start()
        await ib_adapter.place_order(**order)
        latency = performance_timer.stop()

        assert latency < 0.1  # Less than 100ms

    @pytest.mark.red
    async def test_bulk_order_handling(self, ib_adapter):
        """RED: Test handling multiple orders efficiently."""
        orders = [
            {
                "symbol": "EUR.USD",
                "action": "BUY",
                "quantity": 10000,
                "order_type": "MARKET",
            }
            for _ in range(10)
        ]

        results = await ib_adapter.place_bulk_orders(orders)

        assert len(results) == 10
        assert all(r["status"] in ["Filled", "Submitted"] for r in results)
