"""End-to-End Validation Tests for FXML4-ForexConnect Integration.

Comprehensive TDD tests for validating the complete integration between
FXML4 and ForexConnect systems, including real-time market data streaming,
account monitoring, and full trading workflow validation.
"""

import asyncio
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from fxml4.api.account_monitoring import (
    AccountReconciler,
    AccountSnapshot,
    AccountStateManager,
    AlertType,
    MarginMonitor,
    PositionData,
    PositionTracker,
)
from fxml4.api.websocket_market_data import (
    FeedFailoverManager,
    FeedSource,
    OHLCBarAggregator,
    PriceFeedMonitor,
    TickData,
    TimeFrame,
    WebSocketMarketDataManager,
)


@pytest.fixture
def mock_websocket_clients():
    """Create mock WebSocket clients for testing."""
    clients = []
    for i in range(5):
        client = MagicMock()
        client.client_id = f"test_client_{i}"
        client.closed = False
        client.send = AsyncMock()
        clients.append(client)
    return clients


@pytest.fixture
def mock_forexconnect_bridge():
    """Create mock ForexConnect bridge for testing."""
    bridge = MagicMock()
    bridge.connected = True
    bridge.account_data = {
        "account_id": "FC_ACCOUNT_001",
        "balance": 50000.00,
        "equity": 52500.00,
        "margin_used": 2000.00,
        "margin_available": 50500.00,
        "unrealized_pl": 2500.00,
        "currency": "USD",
    }

    bridge.positions = [
        {
            "position_id": "FC_POS_001",
            "symbol": "EURUSD",
            "side": "long",
            "quantity": 100000,
            "open_price": 1.1200,
            "current_price": 1.1350,
            "unrealized_pl": 1500.00,
        },
        {
            "position_id": "FC_POS_002",
            "symbol": "GBPUSD",
            "side": "short",
            "quantity": 75000,
            "open_price": 1.3100,
            "current_price": 1.2950,
            "unrealized_pl": 1125.00,
        },
    ]

    bridge.get_account_data = AsyncMock(return_value=bridge.account_data)
    bridge.get_positions = AsyncMock(return_value=bridge.positions)
    bridge.subscribe_to_prices = AsyncMock()
    bridge.place_order = AsyncMock()

    return bridge


@pytest.fixture
def sample_market_ticks():
    """Generate sample market tick data for testing."""
    base_time = datetime.utcnow()
    ticks = []

    symbols = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF"]
    base_prices = {
        "EURUSD": 1.1200,
        "GBPUSD": 1.3100,
        "USDJPY": 110.50,
        "USDCHF": 0.9800,
    }

    for i in range(100):  # 100 ticks over 5 minutes
        for symbol in symbols:
            base_price = base_prices[symbol]
            # Add some realistic price movement
            price_change = (i % 10 - 5) * 0.0001  # -5 to +4 pips
            price = base_price + price_change

            tick = TickData(
                symbol=symbol,
                bid=price - 0.0001,
                ask=price + 0.0001,
                timestamp=base_time + timedelta(seconds=i * 3),  # Every 3 seconds
                volume=1000 + (i % 500),  # Variable volume
            )
            ticks.append(tick)

    return ticks


@pytest.mark.asyncio
class TestE2EMarketDataFlow:
    """End-to-end tests for market data flow validation."""

    async def test_complete_market_data_streaming_pipeline(
        self, mock_websocket_clients, sample_market_ticks
    ):
        """Test complete market data pipeline from ForexConnect to WebSocket clients."""
        # Initialize components
        ws_manager = WebSocketMarketDataManager()
        ohlc_aggregator = OHLCBarAggregator()

        # Register WebSocket clients
        for client in mock_websocket_clients:
            await ws_manager.register_client(client)
            await ws_manager.subscribe_client_to_symbol(client.client_id, "EURUSD")
            await ws_manager.subscribe_client_to_symbol(client.client_id, "GBPUSD")

        # Verify client registration
        assert ws_manager.active_connections == 5
        assert len(ws_manager.subscriptions["EURUSD"]) == 5
        assert len(ws_manager.subscriptions["GBPUSD"]) == 5

        # Process market tick data through pipeline
        completed_bars_count = 0
        message_count = 0

        for tick in sample_market_ticks:
            if tick.symbol in ["EURUSD", "GBPUSD"]:  # Only process subscribed symbols
                # Process through OHLC aggregator
                completed_bars = await ohlc_aggregator.process_tick(
                    tick, TimeFrame.ONE_MINUTE
                )
                completed_bars_count += len(completed_bars)

                # Broadcast tick data to WebSocket clients
                tick_message = {
                    "type": "tick",
                    "symbol": tick.symbol,
                    "bid": tick.bid,
                    "ask": tick.ask,
                    "timestamp": tick.timestamp.isoformat(),
                }

                await ws_manager.broadcast_to_symbol_subscribers(
                    tick.symbol, tick_message
                )
                message_count += 1

        # Verify data processing
        assert completed_bars_count > 0, "Should have completed some OHLC bars"
        assert message_count > 0, "Should have broadcast tick messages"

        # Verify all clients received messages
        for client in mock_websocket_clients:
            assert (
                client.send.call_count > 0
            ), f"Client {client.client_id} should have received messages"

        print(
            f"✓ Processed {len(sample_market_ticks)} ticks, created {completed_bars_count} OHLC bars"
        )
        print(
            f"✓ Broadcast {message_count} messages to {len(mock_websocket_clients)} WebSocket clients"
        )

    async def test_market_data_feed_failover_scenario(self):
        """Test market data feed failover in E2E scenario."""
        # Set up multiple feeds with different priorities
        feed_monitor = PriceFeedMonitor()
        failover_manager = FeedFailoverManager()

        # Primary feed (highest priority)
        primary_feed = FeedSource(
            name="ForexConnect_Primary",
            priority=1,
            url="tcp://primary.forexconnect.com:1234",
            symbols=["EURUSD", "GBPUSD", "USDJPY"],
            health_check_interval=30,
            max_latency_ms=100,
        )

        # Secondary feed (backup)
        secondary_feed = FeedSource(
            name="ForexConnect_Secondary",
            priority=2,
            url="tcp://secondary.forexconnect.com:1234",
            symbols=["EURUSD", "GBPUSD", "USDJPY"],
            health_check_interval=30,
            max_latency_ms=200,
        )

        await feed_monitor.register_feed(primary_feed)
        await feed_monitor.register_feed(secondary_feed)

        # Mock feed objects
        mock_primary = MagicMock()
        mock_primary.name = "ForexConnect_Primary"
        mock_primary.connected = True
        mock_primary.update_count = 100
        mock_primary.error_count = 0
        mock_primary.last_update = datetime.utcnow()

        mock_secondary = MagicMock()
        mock_secondary.name = "ForexConnect_Secondary"
        mock_secondary.connected = True
        mock_secondary.update_count = 80
        mock_secondary.error_count = 2
        mock_secondary.last_update = datetime.utcnow()

        await failover_manager.register_feed(primary_feed, mock_primary)
        await failover_manager.register_feed(secondary_feed, mock_secondary)

        # Test initial feed selection
        best_feed = await failover_manager.select_best_available_feed("EURUSD")
        assert best_feed.name == "ForexConnect_Primary"
        assert failover_manager.current_active_feed == primary_feed

        # Simulate primary feed failure
        mock_primary.connected = False
        failed_feed = await failover_manager.handle_feed_failure(mock_primary, "EURUSD")

        # Should failover to secondary
        assert failed_feed.name == "ForexConnect_Secondary"
        assert failover_manager.current_active_feed == secondary_feed

        # Verify failover events logged
        events = failover_manager.get_failover_events()
        assert len(events) >= 2  # Selection + failover events
        assert any(event["event_type"] == "failover" for event in events)

        print("✓ Market data feed failover scenario validated")

    async def test_high_frequency_data_processing_performance(
        self, sample_market_ticks
    ):
        """Test system performance under high-frequency data load."""
        start_time = time.time()

        # Initialize components for performance test
        ws_manager = WebSocketMarketDataManager()
        ohlc_aggregator = OHLCBarAggregator()

        # Create more clients for load testing
        clients = []
        for i in range(20):  # 20 concurrent clients
            client = MagicMock()
            client.client_id = f"perf_client_{i}"
            client.send = AsyncMock()
            clients.append(client)

            await ws_manager.register_client(client)
            await ws_manager.subscribe_client_to_symbol(client.client_id, "EURUSD")

        # Process data at high frequency
        tick_processing_times = []
        broadcast_times = []

        for tick in sample_market_ticks:
            if tick.symbol == "EURUSD":
                # Measure tick processing time
                tick_start = time.time()
                await ohlc_aggregator.process_tick(tick, TimeFrame.ONE_MINUTE)
                tick_processing_times.append(time.time() - tick_start)

                # Measure broadcast time
                broadcast_start = time.time()
                message = {
                    "type": "tick",
                    "symbol": tick.symbol,
                    "bid": tick.bid,
                    "ask": tick.ask,
                }
                await ws_manager.broadcast_to_symbol_subscribers(tick.symbol, message)
                broadcast_times.append(time.time() - broadcast_start)

        total_time = time.time() - start_time

        # Performance assertions
        avg_tick_processing_time = sum(tick_processing_times) / len(
            tick_processing_times
        )
        avg_broadcast_time = sum(broadcast_times) / len(broadcast_times)
        ticks_per_second = (
            len([t for t in sample_market_ticks if t.symbol == "EURUSD"]) / total_time
        )

        # Performance targets
        assert (
            avg_tick_processing_time < 0.001
        ), f"Tick processing too slow: {avg_tick_processing_time:.4f}s"
        assert (
            avg_broadcast_time < 0.010
        ), f"Broadcast too slow: {avg_broadcast_time:.4f}s"
        assert (
            ticks_per_second > 50
        ), f"Throughput too low: {ticks_per_second:.1f} ticks/sec"

        print(f"✓ Performance test passed:")
        print(f"  - Avg tick processing: {avg_tick_processing_time*1000:.2f}ms")
        print(f"  - Avg broadcast time: {avg_broadcast_time*1000:.2f}ms")
        print(f"  - Throughput: {ticks_per_second:.1f} ticks/second")
        print(f"  - Total time: {total_time:.2f}s for {len(sample_market_ticks)} ticks")


@pytest.mark.asyncio
class TestE2EAccountMonitoring:
    """End-to-end tests for account monitoring validation."""

    async def test_complete_account_synchronization_flow(
        self, mock_forexconnect_bridge
    ):
        """Test complete account synchronization between ForexConnect and FXML4."""
        # Initialize monitoring components
        account_manager = AccountStateManager()
        position_tracker = PositionTracker()
        margin_monitor = MarginMonitor()
        reconciler = AccountReconciler()

        # Simulate ForexConnect account data updates
        fc_account_data = await mock_forexconnect_bridge.get_account_data()
        fc_account_data["timestamp"] = datetime.utcnow().isoformat()

        # Process account update through FXML4
        account_snapshot = await account_manager.process_forex_account_update(
            fc_account_data
        )

        # Verify account synchronization
        assert account_snapshot.account_id == "FC_ACCOUNT_001"
        assert account_snapshot.balance == 50000.00
        assert account_snapshot.equity == 52500.00
        assert account_snapshot.unrealized_pl == 2500.00

        # Process position updates
        fc_positions = await mock_forexconnect_bridge.get_positions()
        for pos_data in fc_positions:
            pos_data["timestamp"] = datetime.utcnow().isoformat()
            await position_tracker.process_forex_position_update(pos_data)

        # Verify position synchronization
        assert len(position_tracker.active_positions) == 2
        assert "FC_POS_001" in position_tracker.active_positions
        assert "FC_POS_002" in position_tracker.active_positions

        total_pl = position_tracker.calculate_total_unrealized_pl()
        expected_total = 1500.00 + 1125.00  # Sum of position P&L
        assert abs(total_pl - expected_total) < 0.01

        # Process margin data
        margin_data = {
            "account_id": fc_account_data["account_id"],
            "equity": fc_account_data["equity"],
            "margin_used": fc_account_data["margin_used"],
            "margin_available": fc_account_data["margin_available"],
            "timestamp": datetime.utcnow().isoformat(),
        }

        margin_result = await margin_monitor.process_margin_update(margin_data)
        assert margin_result.margin_level > 2500  # (52500 / 2000) * 100
        assert margin_result.status == "healthy"

        print("✓ Complete account synchronization flow validated")

    async def test_account_reconciliation_with_live_data(self):
        """Test account reconciliation with simulated live data discrepancies."""
        reconciler = AccountReconciler()

        # Simulate slight timing differences between systems
        fxml4_timestamp = datetime.utcnow()
        fc_timestamp = fxml4_timestamp + timedelta(milliseconds=500)  # 500ms delay

        # FXML4 state (slightly behind)
        fxml4_state = {
            "account_id": "RECONCILE_TEST",
            "balance": 25000.00,
            "equity": 25800.00,
            "unrealized_pl": 800.00,
            "last_update": fxml4_timestamp,
        }

        # ForexConnect state (more recent)
        fc_state = {
            "account_id": "RECONCILE_TEST",
            "balance": 25000.00,
            "equity": 25850.00,  # $50 difference due to price movements
            "pl": 850.00,  # $50 P&L difference
            "timestamp": fc_timestamp.isoformat(),
        }

        # Test reconciliation without tolerance
        result = await reconciler.reconcile_account_balance(fxml4_state, fc_state)
        assert result.is_balanced == False
        assert len(result.discrepancies) == 2  # Equity and P&L differences

        # Test with reasonable tolerance for timing differences
        await reconciler.set_reconciliation_tolerance(
            balance_tolerance=100.00,  # $100 tolerance
            pl_tolerance=100.00,  # $100 P&L tolerance
        )

        tolerance_result = await reconciler.reconcile_account_balance(
            fxml4_state, fc_state, apply_tolerance=True
        )
        assert tolerance_result.is_balanced == True
        assert tolerance_result.within_tolerance == True

        print("✓ Account reconciliation with live data validated")

    async def test_real_time_alert_generation_flow(self):
        """Test real-time alert generation across all monitoring components."""
        account_manager = AccountStateManager()
        margin_monitor = MarginMonitor()

        # Set up alert thresholds
        await margin_monitor.set_margin_thresholds(
            alert_threshold=300.0, call_threshold=150.0  # 300%  # 150%
        )

        # Simulate deteriorating account conditions
        account_states = [
            # Initial healthy state
            {
                "balance": 10000.00,
                "equity": 12000.00,
                "margin_used": 1000.00,
                "pl": 2000.00,
            },
            # Declining equity
            {
                "balance": 10000.00,
                "equity": 10500.00,
                "margin_used": 1500.00,
                "pl": 500.00,
            },
            # Low margin warning
            {
                "balance": 10000.00,
                "equity": 4000.00,
                "margin_used": 1500.00,
                "pl": -6000.00,
            },
            # Margin call territory
            {
                "balance": 10000.00,
                "equity": 2000.00,
                "margin_used": 1500.00,
                "pl": -8000.00,
            },
        ]

        all_alerts = []

        for i, state in enumerate(account_states):
            state["account_id"] = "ALERT_TEST"
            state["currency"] = "USD"
            state["margin_available"] = state["equity"] - state["margin_used"]
            state["timestamp"] = (datetime.utcnow() + timedelta(minutes=i)).isoformat()

            # Process through account manager
            snapshot = await account_manager.process_forex_account_update(state)
            account_alerts = await account_manager.generate_alerts(snapshot)
            all_alerts.extend(account_alerts)

            # Process through margin monitor
            margin_data = await margin_monitor.process_margin_update(state)
            margin_alerts = await margin_monitor.check_margin_alerts(margin_data)
            all_alerts.extend(margin_alerts)

        # Verify alert progression
        alert_types = [alert.alert_type for alert in all_alerts]

        # Should see escalating alerts
        assert AlertType.LOW_BALANCE in alert_types
        assert AlertType.MARGIN_WARNING in alert_types
        assert AlertType.MARGIN_CALL in alert_types

        # Verify alert timestamps are sequential
        alert_times = [alert.timestamp for alert in all_alerts]
        assert alert_times == sorted(alert_times)

        print(
            f"✓ Generated {len(all_alerts)} real-time alerts across degrading conditions"
        )


@pytest.mark.asyncio
class TestE2EIntegratedTradingWorkflow:
    """End-to-end tests for complete trading workflow validation."""

    async def test_signal_to_execution_complete_flow(self, mock_forexconnect_bridge):
        """Test complete flow from market signal to trade execution."""
        # Initialize all components
        ws_manager = WebSocketMarketDataManager()
        account_manager = AccountStateManager()
        position_tracker = PositionTracker()

        # Mock signal generation (would come from ML models in real system)
        trading_signal = {
            "signal_id": "SIG_001",
            "symbol": "EURUSD",
            "action": "BUY",
            "quantity": 100000,
            "confidence": 0.85,
            "target_price": 1.1250,
            "stop_loss": 1.1200,
            "take_profit": 1.1300,
            "timestamp": datetime.utcnow().isoformat(),
        }

        # 1. Signal validation and risk check
        account_data = await mock_forexconnect_bridge.get_account_data()
        account_data["timestamp"] = datetime.utcnow().isoformat()
        snapshot = await account_manager.process_forex_account_update(account_data)

        # Verify sufficient margin
        required_margin = trading_signal["quantity"] * 0.02  # 2% margin requirement
        assert snapshot.margin_available > required_margin

        # 2. Order placement through ForexConnect bridge
        order_request = {
            "order_type": "MARKET",
            "symbol": trading_signal["symbol"],
            "action": trading_signal["action"],
            "quantity": trading_signal["quantity"],
            "stop_loss": trading_signal["stop_loss"],
            "take_profit": trading_signal["take_profit"],
        }

        # Mock order execution
        mock_forexconnect_bridge.place_order.return_value = {
            "order_id": "FC_ORDER_001",
            "status": "FILLED",
            "fill_price": 1.1248,
            "fill_quantity": trading_signal["quantity"],
            "commission": 10.00,
        }

        order_result = await mock_forexconnect_bridge.place_order(order_request)
        assert order_result["status"] == "FILLED"

        # 3. Position tracking update
        new_position = {
            "position_id": f"FC_POS_{order_result['order_id']}",
            "symbol": trading_signal["symbol"],
            "side": "long",
            "quantity": order_result["fill_quantity"],
            "open_price": order_result["fill_price"],
            "current_price": order_result["fill_price"],  # Initially same
            "unrealized_pl": 0.0,
            "timestamp": datetime.utcnow().isoformat(),
        }

        position = await position_tracker.process_forex_position_update(new_position)
        assert position.symbol == "EURUSD"
        assert position.quantity == 100000

        # 4. Real-time price update simulation
        price_updates = [1.1250, 1.1260, 1.1255, 1.1270, 1.1280]

        for new_price in price_updates:
            # Update position with new price
            new_position["current_price"] = new_price
            new_position["unrealized_pl"] = (
                new_price - new_position["open_price"]
            ) * new_position["quantity"]
            new_position["timestamp"] = datetime.utcnow().isoformat()

            await position_tracker.process_forex_position_update(new_position)

            # Broadcast price update to WebSocket clients
            price_message = {
                "type": "price_update",
                "symbol": trading_signal["symbol"],
                "price": new_price,
                "position_pl": new_position["unrealized_pl"],
            }

            await ws_manager.broadcast_to_all(price_message)

        # 5. Final validation
        final_position = position_tracker.active_positions[new_position["position_id"]]
        expected_pl = (1.1280 - 1.1248) * 100000  # Final P&L
        assert abs(final_position.unrealized_pl - expected_pl) < 1.0

        print(f"✓ Complete signal-to-execution flow validated")
        print(
            f"  - Signal: {trading_signal['action']} {trading_signal['quantity']} {trading_signal['symbol']}"
        )
        print(f"  - Fill price: {order_result['fill_price']}")
        print(f"  - Final P&L: ${final_position.unrealized_pl:.2f}")

    async def test_multi_symbol_concurrent_processing(self):
        """Test concurrent processing of multiple symbols and positions."""
        # Initialize components
        ws_manager = WebSocketMarketDataManager()
        position_tracker = PositionTracker()
        ohlc_aggregator = OHLCBarAggregator()

        symbols = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD"]

        # Create concurrent WebSocket subscriptions
        clients = []
        for i, symbol in enumerate(symbols):
            client = MagicMock()
            client.client_id = f"multi_client_{i}"
            client.send = AsyncMock()
            clients.append(client)

            await ws_manager.register_client(client)
            await ws_manager.subscribe_client_to_symbol(client.client_id, symbol)

        # Create positions for each symbol
        positions = []
        for i, symbol in enumerate(symbols):
            position_data = {
                "position_id": f"MULTI_POS_{i:03d}",
                "symbol": symbol,
                "side": "long" if i % 2 == 0 else "short",
                "quantity": 100000 + (i * 10000),
                "open_price": 1.1000 + (i * 0.01),
                "current_price": 1.1000 + (i * 0.01),
                "unrealized_pl": 0.0,
                "timestamp": datetime.utcnow().isoformat(),
            }
            positions.append(position_data)
            await position_tracker.process_forex_position_update(position_data)

        assert len(position_tracker.active_positions) == 5

        # Simulate concurrent price updates
        async def update_symbol_prices(symbol: str, position_data: dict):
            """Update prices for a specific symbol concurrently."""
            price_changes = [
                0.001,
                -0.0005,
                0.002,
                -0.001,
                0.0015,
            ]  # Various price movements

            for change in price_changes:
                new_price = position_data["open_price"] + change

                # Create tick data
                tick = TickData(
                    symbol=symbol,
                    bid=new_price - 0.0001,
                    ask=new_price + 0.0001,
                    timestamp=datetime.utcnow(),
                )

                # Process through OHLC aggregator
                await ohlc_aggregator.process_tick(tick, TimeFrame.ONE_MINUTE)

                # Update position
                position_data["current_price"] = new_price
                if position_data["side"] == "long":
                    position_data["unrealized_pl"] = (
                        new_price - position_data["open_price"]
                    ) * position_data["quantity"]
                else:
                    position_data["unrealized_pl"] = (
                        position_data["open_price"] - new_price
                    ) * position_data["quantity"]

                await position_tracker.process_forex_position_update(position_data)

                # Broadcast update
                message = {
                    "type": "price_update",
                    "symbol": symbol,
                    "price": new_price,
                    "position_pl": position_data["unrealized_pl"],
                }
                await ws_manager.broadcast_to_symbol_subscribers(symbol, message)

                # Small delay to simulate real-time updates
                await asyncio.sleep(0.01)

        # Run concurrent updates for all symbols
        update_tasks = []
        for position_data in positions:
            task = asyncio.create_task(
                update_symbol_prices(position_data["symbol"], position_data)
            )
            update_tasks.append(task)

        # Wait for all concurrent updates to complete
        start_time = time.time()
        await asyncio.gather(*update_tasks)
        processing_time = time.time() - start_time

        # Verify concurrent processing worked
        total_pl = position_tracker.calculate_total_unrealized_pl()
        assert abs(total_pl) > 0  # Should have some P&L from price movements

        # Verify all clients received updates
        for client in clients:
            assert client.send.call_count > 0

        # Performance assertion
        assert (
            processing_time < 5.0
        ), f"Concurrent processing too slow: {processing_time:.2f}s"

        print(
            f"✓ Multi-symbol concurrent processing completed in {processing_time:.2f}s"
        )
        print(f"  - Processed {len(symbols)} symbols concurrently")
        print(f"  - Total portfolio P&L: ${total_pl:.2f}")
        print(f"  - All {len(clients)} clients received real-time updates")


@pytest.mark.asyncio
class TestE2EErrorHandlingAndResilience:
    """End-to-end tests for error handling and system resilience."""

    async def test_websocket_client_disconnection_handling(self):
        """Test graceful handling of WebSocket client disconnections."""
        ws_manager = WebSocketMarketDataManager()

        # Create clients with various failure scenarios
        stable_client = MagicMock()
        stable_client.client_id = "stable_client"
        stable_client.send = AsyncMock()

        failing_client = MagicMock()
        failing_client.client_id = "failing_client"
        failing_client.send = AsyncMock(side_effect=ConnectionError("Connection lost"))

        slow_client = MagicMock()
        slow_client.client_id = "slow_client"
        slow_client.send = AsyncMock(side_effect=asyncio.TimeoutError("Timeout"))

        clients = [stable_client, failing_client, slow_client]

        # Register all clients
        for client in clients:
            await ws_manager.register_client(client)
            await ws_manager.subscribe_client_to_symbol(client.client_id, "EURUSD")

        assert ws_manager.active_connections == 3

        # Broadcast message - should handle failures gracefully
        test_message = {"type": "test", "symbol": "EURUSD", "data": "test_data"}

        await ws_manager.broadcast_to_symbol_subscribers("EURUSD", test_message)

        # Verify failed clients were removed
        assert ws_manager.active_connections == 1  # Only stable_client remains
        assert "stable_client" in ws_manager.connections
        assert "failing_client" not in ws_manager.connections
        assert "slow_client" not in ws_manager.connections

        # Verify stable client received message
        stable_client.send.assert_called_once()

        print("✓ WebSocket client disconnection handling validated")

    async def test_forexconnect_bridge_failure_recovery(self):
        """Test recovery from ForexConnect bridge failures."""
        account_manager = AccountStateManager()
        position_tracker = PositionTracker()

        # Create mock bridge that starts healthy, then fails, then recovers
        class MockFailingBridge:
            def __init__(self):
                self.connected = True
                self.failure_mode = False
                self.call_count = 0

            async def get_account_data(self):
                self.call_count += 1
                if self.failure_mode:
                    raise ConnectionError("ForexConnect bridge disconnected")

                return {
                    "account_id": "RECOVERY_TEST",
                    "balance": 30000.00 + (self.call_count * 100),  # Changing data
                    "equity": 31000.00 + (self.call_count * 100),
                    "margin_used": 1000.00,
                    "margin_available": 30000.00,
                    "unrealized_pl": 1000.00,
                    "currency": "USD",
                    "timestamp": datetime.utcnow().isoformat(),
                }

        mock_bridge = MockFailingBridge()

        # Test normal operation
        account_data = await mock_bridge.get_account_data()
        snapshot = await account_manager.process_forex_account_update(account_data)
        assert snapshot.balance == 30100.00  # First call

        # Simulate bridge failure
        mock_bridge.failure_mode = True

        try:
            await mock_bridge.get_account_data()
            assert False, "Should have raised ConnectionError"
        except ConnectionError:
            pass  # Expected failure

        # Simulate recovery with retry logic
        mock_bridge.failure_mode = False

        # Test recovery
        recovered_data = await mock_bridge.get_account_data()
        recovered_snapshot = await account_manager.process_forex_account_update(
            recovered_data
        )

        # Verify data continuity after recovery
        assert len(account_manager.balance_history) == 2
        assert (
            recovered_snapshot.balance > snapshot.balance
        )  # Data progression continued

        print("✓ ForexConnect bridge failure recovery validated")

    async def test_data_consistency_under_high_load_with_errors(self):
        """Test data consistency when processing high load with intermittent errors."""
        position_tracker = PositionTracker()
        account_manager = AccountStateManager()

        # Generate high-frequency updates with some corrupt data
        good_updates = []
        bad_updates = []

        for i in range(100):
            if i % 10 == 0:  # Every 10th update is corrupted
                bad_update = {
                    "position_id": f"BAD_POS_{i}",
                    "symbol": "INVALID_SYMBOL",
                    "side": "invalid_side",  # Invalid side
                    "quantity": "not_a_number",  # Invalid quantity type
                    "open_price": None,  # Missing price
                    "current_price": -1.0,  # Invalid negative price
                    "timestamp": "invalid_date",  # Invalid timestamp
                }
                bad_updates.append(bad_update)
            else:
                good_update = {
                    "position_id": f"GOOD_POS_{i}",
                    "symbol": "EURUSD",
                    "side": "long" if i % 2 == 0 else "short",
                    "quantity": 100000,
                    "open_price": 1.1000 + (i * 0.0001),
                    "current_price": 1.1050 + (i * 0.0001),
                    "unrealized_pl": 500.00,
                    "timestamp": datetime.utcnow().isoformat(),
                }
                good_updates.append(good_update)

        # Process all updates - good ones should succeed, bad ones should be handled gracefully
        successful_positions = 0
        failed_positions = 0

        for update in good_updates + bad_updates:
            try:
                await position_tracker.process_forex_position_update(update)
                successful_positions += 1
            except (ValueError, TypeError, KeyError) as e:
                failed_positions += 1
                # Log error but continue processing
                continue

        # Verify data integrity
        assert successful_positions == len(good_updates)  # All good updates processed
        assert failed_positions == len(bad_updates)  # All bad updates failed gracefully
        assert len(position_tracker.active_positions) == successful_positions

        # Verify no partial or corrupted data in the system
        for position in position_tracker.active_positions.values():
            assert isinstance(position.quantity, int)
            assert isinstance(position.open_price, float)
            assert position.open_price > 0
            assert position.side in ["long", "short"]
            assert position.symbol == "EURUSD"

        print(f"✓ Data consistency maintained under high load with errors")
        print(f"  - Processed {successful_positions} valid positions")
        print(f"  - Gracefully handled {failed_positions} corrupted updates")
        print(f"  - Zero data corruption or partial updates")


if __name__ == "__main__":
    """Run E2E validation tests."""
    pytest.main([__file__, "-v", "--tb=short"])
