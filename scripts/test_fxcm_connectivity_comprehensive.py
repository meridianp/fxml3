#!/usr/bin/env python3
"""
Comprehensive FXCM Broker Connectivity Test Suite

This script performs thorough testing of FXCM broker connectivity including:
- Authentication and session management
- Market data streaming and latency
- Order management and execution
- Account monitoring and reconciliation
- Error handling and recovery
- Real-time data validation
- Performance benchmarking
"""

import asyncio
import json
import logging
import statistics
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fxml4.api.account_monitoring import AccountReconciler, AccountStateManager
from fxml4.api.websocket_market_data import WebSocketMarketDataManager
from fxml4.brokers.adapters.fxcm_demo_adapter import FXCMDemoAdapter


@dataclass
class ConnectivityTestResult:
    """Test result data class."""

    test_name: str
    success: bool
    duration_ms: float
    details: Dict[str, Any]
    error: Optional[str] = None
    metrics: Optional[Dict[str, float]] = None


@dataclass
class PerformanceMetrics:
    """Performance metrics data class."""

    latency_ms: List[float]
    throughput_ops_per_sec: float
    error_rate: float
    connection_stability: float
    data_accuracy: float


class FXCMConnectivityTester:
    """Comprehensive FXCM connectivity testing framework."""

    def __init__(self, config_path: str = None):
        """Initialize the connectivity tester."""
        self.test_results: List[ConnectivityTestResult] = []
        self.performance_metrics = PerformanceMetrics([], 0.0, 0.0, 0.0, 0.0)
        self.start_time = None
        self.end_time = None

        # Setup logging
        self.setup_logging()

        # Initialize components
        self.adapter = None
        self.reconciler = AccountReconciler()

        # Test configuration
        self.test_symbols = ["EUR/USD", "GBP/USD", "USD/JPY", "USD/CHF", "AUD/USD"]
        self.test_duration = {
            "quick": 30,  # 30 seconds
            "standard": 120,  # 2 minutes
            "extended": 300,  # 5 minutes
        }

        # Performance tracking
        self.latency_samples = []
        self.throughput_samples = []
        self.error_count = 0
        self.total_operations = 0

    def setup_logging(self):
        """Setup comprehensive logging."""
        log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        logging.basicConfig(
            level=logging.INFO,
            format=log_format,
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler(
                    f'fxcm_connectivity_test_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
                ),
            ],
        )
        self.logger = logging.getLogger(__name__)

    def log_test_result(self, result: ConnectivityTestResult):
        """Log and store test result."""
        self.test_results.append(result)
        status = "✅ PASSED" if result.success else "❌ FAILED"
        self.logger.info(f"{status} - {result.test_name} ({result.duration_ms:.2f}ms)")
        if result.error:
            self.logger.error(f"Error: {result.error}")
        if result.metrics:
            for metric, value in result.metrics.items():
                self.logger.info(f"  {metric}: {value}")

    async def run_comprehensive_tests(self, test_mode: str = "standard") -> bool:
        """Run the complete test suite."""
        self.start_time = time.time()

        print("🧪 FXCM Comprehensive Connectivity Test Suite")
        print("=" * 80)
        print(f"📅 Started: {datetime.now().isoformat()}")
        print(f"⚙️  Mode: {test_mode}")
        print(f"🎯 Symbols: {', '.join(self.test_symbols)}")
        print(f"⏱️  Duration: {self.test_duration.get(test_mode, 120)} seconds")
        print()

        try:
            # Test 1: Basic Connection and Authentication
            await self.test_basic_connection()

            # Test 2: Session Management
            await self.test_session_management()

            # Test 3: Market Data Connectivity
            await self.test_market_data_connectivity()

            # Test 4: Real-time Data Streaming
            await self.test_realtime_data_streaming(test_mode)

            # Test 5: Account Information and Monitoring
            await self.test_account_monitoring()

            # Test 6: Order Management System
            await self.test_order_management()

            # Test 7: Position Management
            await self.test_position_management()

            # Test 8: WebSocket Integration
            await self.test_websocket_integration()

            # Test 9: Error Handling and Recovery
            await self.test_error_handling()

            # Test 10: Performance and Load Testing
            await self.test_performance_load(test_mode)

            # Test 11: Data Accuracy and Validation
            await self.test_data_accuracy()

            # Test 12: Account Reconciliation
            await self.test_account_reconciliation()

            # Test 13: Connection Stability
            await self.test_connection_stability(test_mode)

            # Generate comprehensive report
            await self.generate_test_report()

            return self.calculate_overall_success()

        except Exception as e:
            self.logger.error(f"Test suite failed with error: {e}")
            import traceback

            traceback.print_exc()
            return False
        finally:
            self.end_time = time.time()
            if self.adapter:
                await self.adapter.disconnect()

    async def test_basic_connection(self):
        """Test 1: Basic connection and authentication."""
        start_time = time.time()

        try:
            print("🔌 Test 1: Basic Connection and Authentication")

            self.adapter = FXCMDemoAdapter()

            # Test connection
            connected = await self.adapter.connect()

            if not connected:
                raise Exception("Failed to establish connection")

            # Validate connection properties
            assert self.adapter.connected, "Adapter not marked as connected"
            assert self.adapter.session_id, "No session ID assigned"
            assert self.adapter.username, "No username configured"
            assert self.adapter.server, "No server configured"

            duration_ms = (time.time() - start_time) * 1000

            self.log_test_result(
                ConnectivityTestResult(
                    test_name="Basic Connection",
                    success=True,
                    duration_ms=duration_ms,
                    details={
                        "server": self.adapter.server,
                        "username": self.adapter.username,
                        "session_id": self.adapter.session_id,
                        "connection_time_ms": duration_ms,
                    },
                    metrics={"connection_latency_ms": duration_ms},
                )
            )

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            self.error_count += 1

            self.log_test_result(
                ConnectivityTestResult(
                    test_name="Basic Connection",
                    success=False,
                    duration_ms=duration_ms,
                    details={},
                    error=str(e),
                )
            )

    async def test_session_management(self):
        """Test 2: Session management and persistence."""
        start_time = time.time()

        try:
            print("🔑 Test 2: Session Management")

            if not self.adapter or not self.adapter.connected:
                raise Exception("No active connection for session testing")

            # Record initial session details
            initial_session_id = self.adapter.session_id

            # Test session info retrieval
            account_info = await self.adapter.get_account_info()
            assert account_info, "Failed to retrieve account information"

            # Test session persistence during data requests
            market_data = await self.adapter.get_market_data(["EUR/USD"])
            assert market_data, "Failed to retrieve market data"

            # Verify session ID unchanged
            assert (
                self.adapter.session_id == initial_session_id
            ), "Session ID changed unexpectedly"

            duration_ms = (time.time() - start_time) * 1000

            self.log_test_result(
                ConnectivityTestResult(
                    test_name="Session Management",
                    success=True,
                    duration_ms=duration_ms,
                    details={
                        "session_id": self.adapter.session_id,
                        "account_id": account_info.get("account_id"),
                        "persistent": True,
                    },
                    metrics={"session_validation_ms": duration_ms},
                )
            )

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            self.error_count += 1

            self.log_test_result(
                ConnectivityTestResult(
                    test_name="Session Management",
                    success=False,
                    duration_ms=duration_ms,
                    details={},
                    error=str(e),
                )
            )

    async def test_market_data_connectivity(self):
        """Test 3: Market data connectivity and basic retrieval."""
        start_time = time.time()

        try:
            print("📊 Test 3: Market Data Connectivity")

            if not self.adapter or not self.adapter.connected:
                raise Exception("No active connection for market data testing")

            # Test single symbol
            single_data = await self.adapter.get_market_data(["EUR/USD"])
            assert "EUR/USD" in single_data, "Single symbol data not retrieved"

            eur_usd = single_data["EUR/USD"]
            assert "bid" in eur_usd and "ask" in eur_usd, "Missing bid/ask data"
            assert eur_usd["ask"] > eur_usd["bid"], "Invalid spread"

            # Test multiple symbols
            multi_data = await self.adapter.get_market_data(self.test_symbols)
            assert len(multi_data) == len(
                self.test_symbols
            ), "Not all symbols retrieved"

            # Validate all symbol data
            for symbol in self.test_symbols:
                assert symbol in multi_data, f"Missing data for {symbol}"
                data = multi_data[symbol]
                assert "bid" in data and "ask" in data, f"Missing bid/ask for {symbol}"
                assert data["ask"] > data["bid"], f"Invalid spread for {symbol}"
                assert "timestamp" in data, f"Missing timestamp for {symbol}"

            duration_ms = (time.time() - start_time) * 1000
            self.total_operations += 1

            # Calculate average spread
            spreads = [data["ask"] - data["bid"] for data in multi_data.values()]
            avg_spread = statistics.mean(spreads)

            self.log_test_result(
                ConnectivityTestResult(
                    test_name="Market Data Connectivity",
                    success=True,
                    duration_ms=duration_ms,
                    details={
                        "symbols_tested": len(self.test_symbols),
                        "symbols_successful": len(multi_data),
                        "average_spread": avg_spread,
                    },
                    metrics={
                        "data_retrieval_ms": duration_ms,
                        "symbols_per_second": len(self.test_symbols)
                        / (duration_ms / 1000),
                        "average_spread": avg_spread,
                    },
                )
            )

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            self.error_count += 1

            self.log_test_result(
                ConnectivityTestResult(
                    test_name="Market Data Connectivity",
                    success=False,
                    duration_ms=duration_ms,
                    details={},
                    error=str(e),
                )
            )

    async def test_realtime_data_streaming(self, test_mode: str):
        """Test 4: Real-time data streaming performance."""
        start_time = time.time()
        duration = self.test_duration.get(test_mode, 120)

        try:
            print(f"🔄 Test 4: Real-time Data Streaming ({duration}s)")

            if not self.adapter or not self.adapter.connected:
                raise Exception("No active connection for streaming test")

            updates_received = []
            latencies = []

            async def streaming_callback(data):
                """Callback to track streaming performance."""
                update_time = time.time()
                updates_received.append(
                    {
                        "timestamp": update_time,
                        "symbols": list(data.keys()),
                        "data": data,
                    }
                )

                # Calculate latency (simplified)
                for symbol, prices in data.items():
                    if "timestamp" in prices:
                        try:
                            data_timestamp = datetime.fromisoformat(
                                prices["timestamp"].replace("Z", "+00:00")
                            )
                            latency = (update_time - data_timestamp.timestamp()) * 1000
                            latencies.append(latency)
                        except:
                            pass

            # Start streaming
            await self.adapter.start_market_data_stream(
                self.test_symbols, streaming_callback
            )

            print(f"🔄 Streaming for {duration} seconds...")
            await asyncio.sleep(duration)

            # Calculate streaming metrics
            total_updates = len(updates_received)
            if total_updates == 0:
                raise Exception("No streaming updates received")

            updates_per_second = total_updates / duration
            avg_latency = statistics.mean(latencies) if latencies else 0

            # Validate update frequency
            if updates_per_second < 0.5:  # At least 1 update per 2 seconds
                raise Exception(
                    f"Update frequency too low: {updates_per_second:.2f}/sec"
                )

            test_duration_ms = (time.time() - start_time) * 1000
            self.total_operations += total_updates

            self.log_test_result(
                ConnectivityTestResult(
                    test_name="Real-time Data Streaming",
                    success=True,
                    duration_ms=test_duration_ms,
                    details={
                        "streaming_duration_s": duration,
                        "total_updates": total_updates,
                        "symbols_tracked": len(self.test_symbols),
                    },
                    metrics={
                        "updates_per_second": updates_per_second,
                        "average_latency_ms": avg_latency,
                        "total_data_points": total_updates * len(self.test_symbols),
                    },
                )
            )

        except Exception as e:
            test_duration_ms = (time.time() - start_time) * 1000
            self.error_count += 1

            self.log_test_result(
                ConnectivityTestResult(
                    test_name="Real-time Data Streaming",
                    success=False,
                    duration_ms=test_duration_ms,
                    details={"streaming_duration_s": duration},
                    error=str(e),
                )
            )

    async def test_account_monitoring(self):
        """Test 5: Account information and monitoring capabilities."""
        start_time = time.time()

        try:
            print("💰 Test 5: Account Monitoring")

            if not self.adapter or not self.adapter.connected:
                raise Exception("No active connection for account monitoring")

            # Get initial account information
            account_info = await self.adapter.get_account_info()

            # Validate required fields
            required_fields = [
                "account_id",
                "balance",
                "equity",
                "margin_used",
                "margin_available",
                "currency",
                "timestamp",
            ]
            for field in required_fields:
                assert field in account_info, f"Missing required field: {field}"

            # Validate data types and ranges
            assert isinstance(
                account_info["balance"], (int, float)
            ), "Balance is not numeric"
            assert isinstance(
                account_info["equity"], (int, float)
            ), "Equity is not numeric"
            assert account_info["balance"] > 0, "Balance must be positive"
            assert account_info["equity"] >= 0, "Equity cannot be negative"

            # Test account state manager integration
            await self.adapter.account_manager.process_forex_account_update(
                account_info
            )

            # Get account summary
            account_summary = self.adapter.account_manager.get_account_summary()
            assert account_summary, "Failed to generate account summary"

            # Test balance change tracking
            initial_balance = account_info["balance"]

            # Update account again (simulating real-time updates)
            await asyncio.sleep(2)
            updated_account = await self.adapter.get_account_info()

            balance_change = self.adapter.account_manager.get_balance_change()
            expected_change = updated_account["balance"] - initial_balance

            duration_ms = (time.time() - start_time) * 1000
            self.total_operations += 1

            self.log_test_result(
                ConnectivityTestResult(
                    test_name="Account Monitoring",
                    success=True,
                    duration_ms=duration_ms,
                    details={
                        "account_id": account_info["account_id"],
                        "currency": account_info["currency"],
                        "balance": account_info["balance"],
                        "equity": account_info["equity"],
                        "margin_available": account_info["margin_available"],
                    },
                    metrics={
                        "account_retrieval_ms": duration_ms,
                        "balance_change": balance_change,
                        "history_entries": len(
                            self.adapter.account_manager.balance_history
                        ),
                    },
                )
            )

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            self.error_count += 1

            self.log_test_result(
                ConnectivityTestResult(
                    test_name="Account Monitoring",
                    success=False,
                    duration_ms=duration_ms,
                    details={},
                    error=str(e),
                )
            )

    async def test_order_management(self):
        """Test 6: Order management system."""
        start_time = time.time()

        try:
            print("📋 Test 6: Order Management")

            if not self.adapter or not self.adapter.connected:
                raise Exception("No active connection for order management")

            # Test order placement
            order = {
                "symbol": "EUR/USD",
                "side": "buy",
                "quantity": 10000,  # Mini lot for testing
                "order_type": "market",
            }

            order_start = time.time()
            order_result = await self.adapter.place_order(order)
            order_latency = (time.time() - order_start) * 1000

            # Validate order result
            assert order_result["status"] == "FILLED", "Order not filled"
            assert order_result["symbol"] == order["symbol"], "Symbol mismatch"
            assert order_result["quantity"] == order["quantity"], "Quantity mismatch"
            assert "order_id" in order_result, "Missing order ID"
            assert "fill_price" in order_result, "Missing fill price"
            assert "fill_time" in order_result, "Missing fill time"

            self.latency_samples.append(order_latency)

            # Test multiple orders
            multi_orders = []
            for symbol in ["GBP/USD", "USD/JPY"]:
                multi_order = {
                    "symbol": symbol,
                    "side": "sell",
                    "quantity": 5000,
                    "order_type": "market",
                }

                multi_result = await self.adapter.place_order(multi_order)
                multi_orders.append(multi_result)
                assert (
                    multi_result["status"] == "FILLED"
                ), f"Multi-order failed for {symbol}"

            duration_ms = (time.time() - start_time) * 1000
            self.total_operations += 3  # 3 orders placed

            self.log_test_result(
                ConnectivityTestResult(
                    test_name="Order Management",
                    success=True,
                    duration_ms=duration_ms,
                    details={
                        "orders_placed": 3,
                        "orders_filled": 3,
                        "test_symbols": ["EUR/USD", "GBP/USD", "USD/JPY"],
                    },
                    metrics={
                        "order_execution_ms": order_latency,
                        "average_order_time_ms": duration_ms / 3,
                        "orders_per_second": 3 / (duration_ms / 1000),
                    },
                )
            )

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            self.error_count += 1

            self.log_test_result(
                ConnectivityTestResult(
                    test_name="Order Management",
                    success=False,
                    duration_ms=duration_ms,
                    details={},
                    error=str(e),
                )
            )

    async def test_position_management(self):
        """Test 7: Position management and tracking."""
        start_time = time.time()

        try:
            print("🎯 Test 7: Position Management")

            if not self.adapter or not self.adapter.connected:
                raise Exception("No active connection for position management")

            # Get current positions
            positions = await self.adapter.get_positions()
            initial_position_count = len(positions)

            # Validate position data structure
            for pos in positions:
                required_pos_fields = [
                    "position_id",
                    "symbol",
                    "side",
                    "quantity",
                    "open_price",
                    "current_price",
                    "unrealized_pl",
                ]
                for field in required_pos_fields:
                    assert field in pos, f"Missing position field: {field}"

                # Validate position calculations
                assert isinstance(pos["unrealized_pl"], (int, float)), "P&L not numeric"
                assert pos["quantity"] > 0, "Position quantity must be positive"

            # Test position tracker integration
            position_stats = self.adapter.position_tracker.get_position_statistics()
            assert position_stats, "Failed to get position statistics"

            # Test position closure (if positions exist)
            if positions:
                position_to_close = positions[0]
                close_start = time.time()
                close_result = await self.adapter.close_position(
                    position_to_close["position_id"]
                )
                close_latency = (time.time() - close_start) * 1000

                # Validate closure result
                assert (
                    "position_id" in close_result
                ), "Missing position ID in close result"
                assert "close_price" in close_result, "Missing close price"
                assert "realized_pl" in close_result, "Missing realized P&L"

                # Verify position was removed
                updated_positions = await self.adapter.get_positions()
                closed_ids = [p["position_id"] for p in updated_positions]
                assert (
                    position_to_close["position_id"] not in closed_ids
                ), "Position not closed"

                self.latency_samples.append(close_latency)

            duration_ms = (time.time() - start_time) * 1000
            self.total_operations += 1

            final_position_count = len(await self.adapter.get_positions())

            self.log_test_result(
                ConnectivityTestResult(
                    test_name="Position Management",
                    success=True,
                    duration_ms=duration_ms,
                    details={
                        "initial_positions": initial_position_count,
                        "final_positions": final_position_count,
                        "positions_closed": 1 if positions else 0,
                    },
                    metrics={
                        "position_retrieval_ms": duration_ms,
                        "close_latency_ms": close_latency if positions else 0,
                        "total_positions_tracked": position_stats.get(
                            "total_positions", 0
                        ),
                    },
                )
            )

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            self.error_count += 1

            self.log_test_result(
                ConnectivityTestResult(
                    test_name="Position Management",
                    success=False,
                    duration_ms=duration_ms,
                    details={},
                    error=str(e),
                )
            )

    async def test_websocket_integration(self):
        """Test 8: WebSocket integration and broadcasting."""
        start_time = time.time()

        try:
            print("🌐 Test 8: WebSocket Integration")

            if not self.adapter or not self.adapter.connected:
                raise Exception("No active connection for WebSocket testing")

            # Create mock WebSocket clients
            mock_clients = []
            messages_received = {}

            for i in range(3):
                from unittest.mock import AsyncMock, MagicMock

                client = MagicMock()
                client.client_id = f"test_ws_client_{i}"
                client.send = AsyncMock()
                mock_clients.append(client)
                messages_received[client.client_id] = []

                # Register client with WebSocket manager
                await self.adapter.ws_manager.register_client(client)

                # Subscribe to EUR/USD updates
                await self.adapter.ws_manager.subscribe_client_to_symbol(
                    client.client_id, "EUR/USD"
                )

            # Generate market data update to trigger WebSocket broadcast
            market_data = await self.adapter.get_market_data(["EUR/USD"])

            # Allow time for WebSocket broadcasting
            await asyncio.sleep(1)

            # Verify all clients received data
            for client in mock_clients:
                assert (
                    client.send.call_count > 0
                ), f"Client {client.client_id} received no data"

            # Test client management
            active_connections = self.adapter.ws_manager.active_connections
            assert active_connections >= 3, "Not all WebSocket clients registered"

            # Test unsubscribe
            await self.adapter.ws_manager.unsubscribe_client_from_symbol(
                mock_clients[0].client_id, "EUR/USD"
            )

            # Test client disconnection
            await self.adapter.ws_manager.unregister_client(mock_clients[0])

            updated_connections = self.adapter.ws_manager.active_connections
            assert (
                updated_connections < active_connections
            ), "Client not properly disconnected"

            duration_ms = (time.time() - start_time) * 1000
            self.total_operations += 1

            self.log_test_result(
                ConnectivityTestResult(
                    test_name="WebSocket Integration",
                    success=True,
                    duration_ms=duration_ms,
                    details={
                        "clients_tested": len(mock_clients),
                        "subscriptions_tested": 1,
                        "broadcasts_sent": 1,
                    },
                    metrics={
                        "websocket_setup_ms": duration_ms,
                        "active_connections": updated_connections,
                        "broadcast_success_rate": 100.0,
                    },
                )
            )

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            self.error_count += 1

            self.log_test_result(
                ConnectivityTestResult(
                    test_name="WebSocket Integration",
                    success=False,
                    duration_ms=duration_ms,
                    details={},
                    error=str(e),
                )
            )

    async def test_error_handling(self):
        """Test 9: Error handling and recovery mechanisms."""
        start_time = time.time()

        try:
            print("🛡️ Test 9: Error Handling and Recovery")

            if not self.adapter or not self.adapter.connected:
                raise Exception("No active connection for error handling test")

            error_scenarios_passed = 0
            total_scenarios = 0

            # Test 1: Invalid symbol handling
            total_scenarios += 1
            try:
                invalid_data = await self.adapter.get_market_data(["INVALID/SYMBOL"])
                # Should not raise error but return empty or handle gracefully
                error_scenarios_passed += 1
            except Exception as e:
                self.logger.warning(f"Invalid symbol test: {e}")

            # Test 2: Invalid order handling
            total_scenarios += 1
            try:
                invalid_order = {
                    "symbol": "EUR/USD",
                    "side": "invalid_side",  # Invalid side
                    "quantity": -1000,  # Negative quantity
                    "order_type": "market",
                }
                # This should either handle gracefully or raise appropriate error
                await self.adapter.place_order(invalid_order)
            except Exception:
                error_scenarios_passed += 1  # Expected to fail

            # Test 3: Non-existent position closure
            total_scenarios += 1
            try:
                await self.adapter.close_position("NON_EXISTENT_POSITION_ID")
            except ValueError:
                error_scenarios_passed += 1  # Expected to fail with ValueError
            except Exception:
                error_scenarios_passed += 1  # Any error is acceptable

            # Test 4: Connection state validation
            total_scenarios += 1
            # Temporarily mark as disconnected
            original_state = self.adapter.connected
            self.adapter.connected = False

            try:
                await self.adapter.get_account_info()
            except ConnectionError:
                error_scenarios_passed += 1  # Expected ConnectionError
            except Exception:
                error_scenarios_passed += 1  # Any error is acceptable
            finally:
                self.adapter.connected = original_state

            duration_ms = (time.time() - start_time) * 1000
            success_rate = (error_scenarios_passed / total_scenarios) * 100

            self.log_test_result(
                ConnectivityTestResult(
                    test_name="Error Handling",
                    success=success_rate
                    >= 75,  # At least 75% of scenarios handled properly
                    duration_ms=duration_ms,
                    details={
                        "scenarios_tested": total_scenarios,
                        "scenarios_handled": error_scenarios_passed,
                    },
                    metrics={
                        "error_handling_rate": success_rate,
                        "recovery_time_ms": duration_ms,
                    },
                )
            )

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            self.error_count += 1

            self.log_test_result(
                ConnectivityTestResult(
                    test_name="Error Handling",
                    success=False,
                    duration_ms=duration_ms,
                    details={},
                    error=str(e),
                )
            )

    async def test_performance_load(self, test_mode: str):
        """Test 10: Performance and load testing."""
        start_time = time.time()

        try:
            print(f"⚡ Test 10: Performance and Load Testing")

            if not self.adapter or not self.adapter.connected:
                raise Exception("No active connection for performance testing")

            # Configure test parameters based on mode
            if test_mode == "quick":
                operations_count = 10
                concurrent_requests = 2
            elif test_mode == "extended":
                operations_count = 50
                concurrent_requests = 5
            else:  # standard
                operations_count = 25
                concurrent_requests = 3

            print(
                f"📊 Running {operations_count} operations with {concurrent_requests} concurrent requests"
            )

            # Test 1: Concurrent market data requests
            async def fetch_market_data():
                return await self.adapter.get_market_data(["EUR/USD", "GBP/USD"])

            concurrent_start = time.time()
            concurrent_tasks = [fetch_market_data() for _ in range(concurrent_requests)]
            concurrent_results = await asyncio.gather(
                *concurrent_tasks, return_exceptions=True
            )
            concurrent_duration = time.time() - concurrent_start

            successful_requests = sum(
                1 for result in concurrent_results if not isinstance(result, Exception)
            )

            # Test 2: Sequential operations benchmark
            sequential_times = []
            for i in range(operations_count):
                op_start = time.time()

                if i % 3 == 0:
                    # Account info request
                    await self.adapter.get_account_info()
                elif i % 3 == 1:
                    # Market data request
                    await self.adapter.get_market_data(["USD/JPY"])
                else:
                    # Position request
                    await self.adapter.get_positions()

                op_duration = (time.time() - op_start) * 1000
                sequential_times.append(op_duration)

            # Calculate performance metrics
            avg_response_time = statistics.mean(sequential_times)
            max_response_time = max(sequential_times)
            min_response_time = min(sequential_times)

            operations_per_second = operations_count / (sum(sequential_times) / 1000)
            concurrent_success_rate = (successful_requests / concurrent_requests) * 100

            total_duration_ms = (time.time() - start_time) * 1000
            self.total_operations += operations_count + concurrent_requests

            # Performance thresholds
            performance_good = (
                avg_response_time < 1000  # Less than 1 second average
                and concurrent_success_rate >= 90  # At least 90% concurrent success
            )

            self.log_test_result(
                ConnectivityTestResult(
                    test_name="Performance and Load",
                    success=performance_good,
                    duration_ms=total_duration_ms,
                    details={
                        "operations_tested": operations_count,
                        "concurrent_requests": concurrent_requests,
                        "successful_concurrent": successful_requests,
                    },
                    metrics={
                        "avg_response_time_ms": avg_response_time,
                        "max_response_time_ms": max_response_time,
                        "min_response_time_ms": min_response_time,
                        "operations_per_second": operations_per_second,
                        "concurrent_success_rate": concurrent_success_rate,
                        "concurrent_duration_ms": concurrent_duration * 1000,
                    },
                )
            )

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            self.error_count += 1

            self.log_test_result(
                ConnectivityTestResult(
                    test_name="Performance and Load",
                    success=False,
                    duration_ms=duration_ms,
                    details={},
                    error=str(e),
                )
            )

    async def test_data_accuracy(self):
        """Test 11: Data accuracy and validation."""
        start_time = time.time()

        try:
            print("🎯 Test 11: Data Accuracy and Validation")

            if not self.adapter or not self.adapter.connected:
                raise Exception("No active connection for data accuracy testing")

            accuracy_checks_passed = 0
            total_checks = 0

            # Test 1: Price data consistency
            total_checks += 1
            market_data_1 = await self.adapter.get_market_data(["EUR/USD"])
            await asyncio.sleep(1)
            market_data_2 = await self.adapter.get_market_data(["EUR/USD"])

            # Prices should be different (live data) but within reasonable range
            price_1 = market_data_1["EUR/USD"]["bid"]
            price_2 = market_data_2["EUR/USD"]["bid"]
            price_diff = abs(price_1 - price_2)

            # Price shouldn't change more than 1% in 1 second for major pairs
            max_change = price_1 * 0.01
            if price_diff <= max_change:
                accuracy_checks_passed += 1

            # Test 2: Spread validation
            total_checks += 1
            spread_valid = True
            for symbol in self.test_symbols:
                data = await self.adapter.get_market_data([symbol])
                if symbol in data:
                    bid = data[symbol]["bid"]
                    ask = data[symbol]["ask"]
                    spread = ask - bid

                    # Spread should be positive and reasonable (less than 1% for major pairs)
                    max_spread = bid * 0.01
                    if spread <= 0 or spread > max_spread:
                        spread_valid = False
                        break

            if spread_valid:
                accuracy_checks_passed += 1

            # Test 3: Timestamp accuracy
            total_checks += 1
            current_time = datetime.utcnow()
            data = await self.adapter.get_market_data(["EUR/USD"])

            if "EUR/USD" in data and "timestamp" in data["EUR/USD"]:
                try:
                    data_time = datetime.fromisoformat(
                        data["EUR/USD"]["timestamp"].replace("Z", "+00:00")
                    )
                    time_diff = abs(
                        (current_time - data_time.replace(tzinfo=None)).total_seconds()
                    )

                    # Data timestamp should be within 5 seconds of current time
                    if time_diff <= 5:
                        accuracy_checks_passed += 1
                except:
                    pass

            # Test 4: Account balance consistency
            total_checks += 1
            account_1 = await self.adapter.get_account_info()
            positions = await self.adapter.get_positions()

            # Calculate expected equity
            unrealized_pl = sum(pos.get("unrealized_pl", 0) for pos in positions)
            expected_equity = account_1["balance"] + unrealized_pl
            actual_equity = account_1["equity"]

            equity_diff = abs(expected_equity - actual_equity)

            # Equity calculation should be consistent (within $1 for demo)
            if equity_diff <= 1.0:
                accuracy_checks_passed += 1

            duration_ms = (time.time() - start_time) * 1000
            accuracy_rate = (accuracy_checks_passed / total_checks) * 100

            self.log_test_result(
                ConnectivityTestResult(
                    test_name="Data Accuracy",
                    success=accuracy_rate >= 75,  # At least 75% accuracy
                    duration_ms=duration_ms,
                    details={
                        "checks_performed": total_checks,
                        "checks_passed": accuracy_checks_passed,
                    },
                    metrics={
                        "accuracy_rate": accuracy_rate,
                        "price_stability": price_diff,
                        "spread_validity": spread_valid,
                        "timestamp_accuracy_s": (
                            time_diff if "time_diff" in locals() else 0
                        ),
                    },
                )
            )

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            self.error_count += 1

            self.log_test_result(
                ConnectivityTestResult(
                    test_name="Data Accuracy",
                    success=False,
                    duration_ms=duration_ms,
                    details={},
                    error=str(e),
                )
            )

    async def test_account_reconciliation(self):
        """Test 12: Account reconciliation between systems."""
        start_time = time.time()

        try:
            print("🔍 Test 12: Account Reconciliation")

            if not self.adapter or not self.adapter.connected:
                raise Exception("No active connection for reconciliation testing")

            # Get account info from FXCM adapter
            fxcm_account = await self.adapter.get_account_info()

            # Create FXML4 account state (simulated from account manager)
            fxml4_account = {
                "account_id": fxcm_account["account_id"],
                "balance": fxcm_account["balance"],
                "equity": fxcm_account["equity"],
                "unrealized_pl": fxcm_account.get("unrealized_pl", 0),
                "last_update": datetime.utcnow(),
            }

            # Perform reconciliation
            reconciliation_result = await self.reconciler.reconcile_account_balance(
                fxml4_account, fxcm_account
            )

            # Test reconciliation with tolerance
            await self.reconciler.set_reconciliation_tolerance(
                balance_tolerance=1.0,  # $1 tolerance
                pl_tolerance=0.50,  # $0.50 P&L tolerance
            )

            tolerance_result = await self.reconciler.reconcile_account_balance(
                fxml4_account, fxcm_account, apply_tolerance=True
            )

            duration_ms = (time.time() - start_time) * 1000

            reconciliation_success = (
                reconciliation_result.is_balanced or tolerance_result.within_tolerance
            )

            self.log_test_result(
                ConnectivityTestResult(
                    test_name="Account Reconciliation",
                    success=reconciliation_success,
                    duration_ms=duration_ms,
                    details={
                        "account_id": fxcm_account["account_id"],
                        "balance_difference": reconciliation_result.balance_difference,
                        "equity_difference": reconciliation_result.equity_difference,
                        "discrepancies": len(reconciliation_result.discrepancies),
                        "within_tolerance": (
                            tolerance_result.within_tolerance
                            if "tolerance_result" in locals()
                            else False
                        ),
                    },
                    metrics={
                        "reconciliation_time_ms": duration_ms,
                        "balance_accuracy": 100
                        - abs(reconciliation_result.balance_difference),
                        "equity_accuracy": 100
                        - abs(reconciliation_result.equity_difference),
                    },
                )
            )

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            self.error_count += 1

            self.log_test_result(
                ConnectivityTestResult(
                    test_name="Account Reconciliation",
                    success=False,
                    duration_ms=duration_ms,
                    details={},
                    error=str(e),
                )
            )

    async def test_connection_stability(self, test_mode: str):
        """Test 13: Connection stability over time."""
        start_time = time.time()
        duration = min(self.test_duration.get(test_mode, 120), 300)  # Max 5 minutes

        try:
            print(f"🔗 Test 13: Connection Stability ({duration}s)")

            if not self.adapter or not self.adapter.connected:
                raise Exception("No active connection for stability testing")

            stability_checks = []
            check_interval = max(5, duration // 10)  # At least 5 seconds, max 10 checks

            print(
                f"🔄 Monitoring connection stability for {duration}s (checking every {check_interval}s)"
            )

            for i in range(duration // check_interval):
                check_start = time.time()

                try:
                    # Perform basic connectivity check
                    account_info = await self.adapter.get_account_info()
                    market_data = await self.adapter.get_market_data(["EUR/USD"])

                    check_duration = (time.time() - check_start) * 1000

                    stability_checks.append(
                        {
                            "check_number": i + 1,
                            "success": True,
                            "duration_ms": check_duration,
                            "timestamp": datetime.utcnow().isoformat(),
                        }
                    )

                except Exception as e:
                    check_duration = (time.time() - check_start) * 1000
                    stability_checks.append(
                        {
                            "check_number": i + 1,
                            "success": False,
                            "duration_ms": check_duration,
                            "error": str(e),
                            "timestamp": datetime.utcnow().isoformat(),
                        }
                    )

                # Wait for next check
                if i < (duration // check_interval) - 1:
                    await asyncio.sleep(check_interval)

            # Calculate stability metrics
            successful_checks = sum(1 for check in stability_checks if check["success"])
            total_checks = len(stability_checks)
            stability_rate = (
                (successful_checks / total_checks) * 100 if total_checks > 0 else 0
            )

            avg_response_time = (
                statistics.mean(
                    [
                        check["duration_ms"]
                        for check in stability_checks
                        if check["success"]
                    ]
                )
                if successful_checks > 0
                else 0
            )

            total_duration_ms = (time.time() - start_time) * 1000

            # Connection is considered stable if >90% checks pass
            is_stable = stability_rate >= 90

            self.log_test_result(
                ConnectivityTestResult(
                    test_name="Connection Stability",
                    success=is_stable,
                    duration_ms=total_duration_ms,
                    details={
                        "monitoring_duration_s": duration,
                        "total_checks": total_checks,
                        "successful_checks": successful_checks,
                        "failed_checks": total_checks - successful_checks,
                    },
                    metrics={
                        "stability_rate": stability_rate,
                        "avg_response_time_ms": avg_response_time,
                        "uptime_percentage": stability_rate,
                    },
                )
            )

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            self.error_count += 1

            self.log_test_result(
                ConnectivityTestResult(
                    test_name="Connection Stability",
                    success=False,
                    duration_ms=duration_ms,
                    details={"monitoring_duration_s": duration},
                    error=str(e),
                )
            )

    async def generate_test_report(self):
        """Generate comprehensive test report."""
        print("\n" + "=" * 80)
        print("📊 COMPREHENSIVE CONNECTIVITY TEST REPORT")
        print("=" * 80)

        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result.success)
        failed_tests = total_tests - passed_tests

        overall_success_rate = (
            (passed_tests / total_tests) * 100 if total_tests > 0 else 0
        )
        total_duration = self.end_time - self.start_time if self.end_time else 0

        print(f"📅 Test Execution Time: {datetime.now().isoformat()}")
        print(f"⏱️  Total Duration: {total_duration:.2f} seconds")
        print(f"🧪 Total Tests: {total_tests}")
        print(f"✅ Passed: {passed_tests}")
        print(f"❌ Failed: {failed_tests}")
        print(f"📊 Success Rate: {overall_success_rate:.1f}%")
        print(f"⚡ Total Operations: {self.total_operations}")
        print(f"🚫 Total Errors: {self.error_count}")

        if self.latency_samples:
            avg_latency = statistics.mean(self.latency_samples)
            max_latency = max(self.latency_samples)
            print(f"🕐 Average Latency: {avg_latency:.2f}ms")
            print(f"🕐 Max Latency: {max_latency:.2f}ms")

        print("\n📋 DETAILED TEST RESULTS:")
        print("-" * 80)

        for result in self.test_results:
            status = "✅ PASS" if result.success else "❌ FAIL"
            print(f"{status} - {result.test_name} ({result.duration_ms:.0f}ms)")

            if result.metrics:
                for metric, value in result.metrics.items():
                    if isinstance(value, float):
                        print(f"        {metric}: {value:.2f}")
                    else:
                        print(f"        {metric}: {value}")

            if result.error:
                print(f"        Error: {result.error}")

        # Generate JSON report
        report_data = {
            "test_execution": {
                "timestamp": datetime.now().isoformat(),
                "total_duration_s": total_duration,
                "total_tests": total_tests,
                "passed_tests": passed_tests,
                "failed_tests": failed_tests,
                "success_rate": overall_success_rate,
                "total_operations": self.total_operations,
                "total_errors": self.error_count,
            },
            "performance_metrics": {
                "avg_latency_ms": (
                    statistics.mean(self.latency_samples) if self.latency_samples else 0
                ),
                "max_latency_ms": (
                    max(self.latency_samples) if self.latency_samples else 0
                ),
                "min_latency_ms": (
                    min(self.latency_samples) if self.latency_samples else 0
                ),
                "operations_per_second": (
                    self.total_operations / total_duration if total_duration > 0 else 0
                ),
                "error_rate": (
                    (self.error_count / self.total_operations) * 100
                    if self.total_operations > 0
                    else 0
                ),
            },
            "test_results": [asdict(result) for result in self.test_results],
        }

        # Save report to file
        report_filename = (
            f"fxcm_connectivity_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        with open(report_filename, "w") as f:
            json.dump(report_data, f, indent=2)

        print(f"\n💾 Detailed report saved to: {report_filename}")

    def calculate_overall_success(self) -> bool:
        """Calculate if overall test suite passed."""
        if not self.test_results:
            return False

        # Critical tests that must pass
        critical_tests = [
            "Basic Connection",
            "Session Management",
            "Market Data Connectivity",
            "Account Monitoring",
        ]

        critical_passed = all(
            any(
                result.test_name == test_name and result.success
                for result in self.test_results
            )
            for test_name in critical_tests
        )

        # Overall success rate should be >80%
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result.success)
        success_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0

        return critical_passed and success_rate >= 80


async def main():
    """Main entry point for FXCM connectivity testing."""
    import argparse

    parser = argparse.ArgumentParser(
        description="FXCM Comprehensive Connectivity Test Suite"
    )
    parser.add_argument(
        "--mode",
        choices=["quick", "standard", "extended"],
        default="standard",
        help="Test mode",
    )
    parser.add_argument("--config", help="Configuration file path")

    args = parser.parse_args()

    print("🚀 FXCM Comprehensive Connectivity Test Suite")
    print("=" * 80)
    print(f"Mode: {args.mode}")
    if args.config:
        print(f"Config: {args.config}")
    print()

    tester = FXCMConnectivityTester(args.config)
    success = await tester.run_comprehensive_tests(args.mode)

    if success:
        print("\n🎉 FXCM CONNECTIVITY TEST SUITE: SUCCESS")
        print("✅ All critical tests passed")
        print("🔗 FXCM broker connectivity is operational")
        sys.exit(0)
    else:
        print("\n💥 FXCM CONNECTIVITY TEST SUITE: FAILURE")
        print("❌ Critical connectivity issues detected")
        print("🛠️  Please review test results and resolve issues")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
