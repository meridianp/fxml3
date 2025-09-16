"""Integration tests for FXML4-ForexConnect bridge.

Tests the complete integration between FXML4 and the ForexConnect middleware,
including message translation, RabbitMQ communication, and end-to-end order flow.
"""

import asyncio
import json
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import aio_pika
import aiohttp
import pytest

from fxml4.brokers.adapters.fxcm_bridge_adapter import FXCMBridgeAdapter
from fxml4.brokers.adapters.message_translator import get_message_translator
from fxml4.core.exceptions import BrokerError
from fxml4.core.exceptions import ConnectionError as FXMLConnectionError
from fxml4.fix.messages.base import OrdType, Side, TimeInForce
from fxml4.fix.messages.orders import NewOrderSingle


class MockRabbitMQConnection:
    """Mock RabbitMQ connection for testing."""

    def __init__(self):
        self.closed = False
        self.channels = []

    async def channel(self):
        channel = MockRabbitMQChannel()
        self.channels.append(channel)
        return channel

    async def close(self):
        self.closed = True

    @property
    def is_closed(self):
        return self.closed


class MockRabbitMQChannel:
    """Mock RabbitMQ channel for testing."""

    def __init__(self):
        self.exchanges = {}
        self.queues = {}
        self.messages = []
        self.consumers = {}

    async def set_qos(self, prefetch_count: int):
        self.prefetch_count = prefetch_count

    async def declare_exchange(self, name: str, exchange_type, durable: bool = True):
        exchange = MockRabbitMQExchange(name, exchange_type)
        self.exchanges[name] = exchange
        return exchange

    async def declare_queue(
        self,
        name: str,
        durable: bool = True,
        auto_delete: bool = False,
        arguments: dict = None,
    ):
        queue = MockRabbitMQQueue(name, durable, auto_delete, arguments)
        self.queues[name] = queue
        return queue

    async def get_exchange(self, name: str):
        return self.exchanges.get(name)


class MockRabbitMQExchange:
    """Mock RabbitMQ exchange for testing."""

    def __init__(self, name: str, exchange_type):
        self.name = name
        self.type = exchange_type
        self.messages = []

    async def publish(self, message, routing_key: str):
        self.messages.append(
            {
                "message": message,
                "routing_key": routing_key,
                "timestamp": datetime.utcnow(),
            }
        )


class MockRabbitMQQueue:
    """Mock RabbitMQ queue for testing."""

    def __init__(self, name: str, durable: bool, auto_delete: bool, arguments: dict):
        self.name = name
        self.durable = durable
        self.auto_delete = auto_delete
        self.arguments = arguments
        self.messages = []
        self.consumers = []

    async def consume(self, callback, no_ack: bool = False):
        self.consumers.append(callback)

    async def put_message(self, message_data: dict):
        """Add message to queue for testing."""
        message = MockRabbitMQMessage(message_data)
        self.messages.append(message)

        # Call consumers
        for consumer in self.consumers:
            await consumer(message)


class MockRabbitMQMessage:
    """Mock RabbitMQ message for testing."""

    def __init__(self, data: dict):
        self.body = json.dumps(data).encode()
        self.headers = data.get("headers", {})
        self.correlation_id = data.get("correlation_id", "")
        self.processed = False

    async def process(self):
        """Context manager for message processing."""
        return MockMessageProcessor(self)


class MockMessageProcessor:
    """Mock message processor context manager."""

    def __init__(self, message):
        self.message = message

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.message.processed = True


class MockHTTPResponse:
    """Mock HTTP response for aiohttp testing."""

    def __init__(self, status: int, data: dict):
        self.status = status
        self._data = data

    async def json(self):
        return self._data

    async def text(self):
        return json.dumps(self._data)


class MockHTTPSession:
    """Mock HTTP session for testing bridge communication."""

    def __init__(self):
        self.closed = False
        self.requests = []
        self.responses = {}

    def get(self, url: str):
        return MockHTTPRequest(self, "GET", url)

    def post(self, url: str, json=None):
        return MockHTTPRequest(self, "POST", url, json=json)

    async def close(self):
        self.closed = True

    def set_response(self, url: str, status: int, data: dict):
        """Set mock response for URL."""
        self.responses[url] = MockHTTPResponse(status, data)


class MockHTTPRequest:
    """Mock HTTP request context manager."""

    def __init__(self, session, method: str, url: str, json=None):
        self.session = session
        self.method = method
        self.url = url
        self.json_data = json

    async def __aenter__(self):
        # Record request
        self.session.requests.append(
            {
                "method": self.method,
                "url": self.url,
                "json": self.json_data,
                "timestamp": datetime.utcnow(),
            }
        )

        # Return mock response
        if self.url in self.session.responses:
            return self.session.responses[self.url]

        # Default responses
        if "/health" in self.url:
            return MockHTTPResponse(
                200, {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}
            )
        elif "/market-data/subscribe" in self.url:
            return MockHTTPResponse(
                200, {"status": "subscribed", "symbols": ["EUR/USD"]}
            )
        elif "/orders" in self.url and self.method == "POST":
            return MockHTTPResponse(200, {"order_id": "FC_001", "status": "accepted"})

        return MockHTTPResponse(404, {"error": "Not found"})

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


@pytest.fixture
async def mock_rabbitmq():
    """Create mock RabbitMQ connection."""
    return MockRabbitMQConnection()


@pytest.fixture
async def mock_http_session():
    """Create mock HTTP session."""
    return MockHTTPSession()


@pytest.fixture
async def bridge_adapter(mock_rabbitmq, mock_http_session):
    """Create bridge adapter with mocked dependencies."""
    config = {
        "bridge_url": "http://test-bridge:8080",
        "api_key": "test_key",
        "rabbitmq": {
            "host": "test-rabbitmq",
            "port": 5672,
            "username": "test",
            "password": "test",
        },
    }

    adapter = FXCMBridgeAdapter(config)

    # Patch dependencies
    with (
        patch("aio_pika.connect_robust", return_value=mock_rabbitmq),
        patch("aiohttp.ClientSession", return_value=mock_http_session),
    ):

        yield adapter


@pytest.mark.asyncio
class TestFXCMBridgeIntegration:
    """Integration tests for FXML4-ForexConnect bridge."""

    async def test_adapter_connection(self, bridge_adapter, mock_http_session):
        """Test adapter connects to RabbitMQ and bridge service."""
        # Set up mock health response
        mock_http_session.set_response(
            "http://test-bridge:8080/health",
            200,
            {"status": "healthy", "forex_connect": "connected"},
        )

        # Test connection
        await bridge_adapter.connect()

        assert bridge_adapter.is_connected
        assert len(mock_http_session.requests) >= 1

        # Check health request was made
        health_requests = [
            r for r in mock_http_session.requests if "/health" in r["url"]
        ]
        assert len(health_requests) > 0

        await bridge_adapter.disconnect()
        assert not bridge_adapter.is_connected

    async def test_order_submission_flow(self, bridge_adapter, mock_http_session):
        """Test complete order submission flow."""
        await bridge_adapter.connect()

        # Create test order
        test_order = NewOrderSingle(
            cl_ord_id="TEST_001",
            symbol="EURUSD",
            side=Side.BUY,
            order_qty=100000,
            ord_type=OrdType.MARKET,
        )

        # Submit order
        order_id = await bridge_adapter.submit_order(test_order)

        assert order_id == "TEST_001"
        assert test_order.cl_ord_id in bridge_adapter._pending_orders

        # Verify message was published to RabbitMQ
        orders_exchange = bridge_adapter._channel.exchanges.get("forex.orders")
        assert orders_exchange is not None
        assert len(orders_exchange.messages) > 0

        # Check message content
        published_message = orders_exchange.messages[0]
        message_data = json.loads(published_message["message"].body.decode())

        assert message_data["correlation_id"] == "TEST_001"
        assert message_data["instrument"] == "EUR/USD"
        assert message_data["side"] == "buy"
        assert message_data["amount"] == 100000

        await bridge_adapter.disconnect()

    async def test_order_response_handling(self, bridge_adapter):
        """Test handling of order responses from ForexConnect."""
        await bridge_adapter.connect()

        # Create test order for correlation
        test_order = NewOrderSingle(
            cl_ord_id="TEST_002",
            symbol="GBPUSD",
            side=Side.SELL,
            order_qty=50000,
            ord_type=OrdType.LIMIT,
            price=1.2500,
        )

        # Submit order to create pending state
        await bridge_adapter.submit_order(test_order)

        # Simulate ForexConnect response
        forex_response = {
            "type": "order_response",
            "correlation_id": "TEST_002",
            "request_id": str(uuid.uuid4()),
            "status": "executed",
            "order_id": "FC_12345",
            "trade_id": "TR_54321",
            "instrument": "GBP/USD",
            "amount": 50000,
            "rate": 1.2505,
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Get response queue and simulate message
        response_queue = bridge_adapter._order_response_queue
        await response_queue.put_message(forex_response)

        # Verify order was processed and removed from pending
        assert "TEST_002" not in bridge_adapter._pending_orders

        await bridge_adapter.disconnect()

    async def test_market_data_subscription(self, bridge_adapter, mock_http_session):
        """Test market data subscription and handling."""
        await bridge_adapter.connect()

        # Set up subscription response
        mock_http_session.set_response(
            "http://test-bridge:8080/market-data/subscribe",
            200,
            {"status": "subscribed", "symbols": ["EUR/USD", "GBP/USD"]},
        )

        # Track market data updates
        received_updates = []

        async def market_data_callback(symbol: str, data: Dict[str, Any]):
            received_updates.append({"symbol": symbol, "data": data})

        # Subscribe to market data
        await bridge_adapter.subscribe_market_data(
            ["EURUSD", "GBPUSD"], market_data_callback
        )

        # Verify subscription request was made
        subscribe_requests = [
            r
            for r in mock_http_session.requests
            if "/market-data/subscribe" in r["url"]
        ]
        assert len(subscribe_requests) > 0

        # Simulate market data update
        market_update = {
            "type": "price_update",
            "instrument": "EUR/USD",
            "bid": 1.1234,
            "ask": 1.1236,
            "timestamp": datetime.utcnow().isoformat(),
            "digits": 5,
        }

        # Send market data through queue
        market_data_queue = bridge_adapter._market_data_queue
        await market_data_queue.put_message(market_update)

        # Allow time for processing
        await asyncio.sleep(0.1)

        # Verify callback was called
        assert len(received_updates) > 0
        assert received_updates[0]["symbol"] == "EURUSD"
        assert received_updates[0]["data"]["bid"] == 1.1234

        await bridge_adapter.disconnect()

    async def test_message_translation(self):
        """Test message translation between FIX and ForexConnect formats."""
        translator = get_message_translator()

        # Test FIX to ForexConnect translation
        fix_order = NewOrderSingle(
            cl_ord_id="TRANS_001",
            symbol="USDJPY",
            side=Side.BUY,
            order_qty=200000,
            ord_type=OrdType.LIMIT,
            price=110.50,
            time_in_force=TimeInForce.GTC,
        )

        forex_order = translator.translate_order_to_forex(fix_order)

        assert forex_order["correlation_id"] == "TRANS_001"
        assert forex_order["instrument"] == "USD/JPY"
        assert forex_order["side"] == "buy"
        assert forex_order["amount"] == 200000
        assert forex_order["order_type"] == "limit"
        assert forex_order["rate"] == 110.50
        assert forex_order["time_in_force"] == "GTC"

        # Test ForexConnect to FIX translation
        forex_response = {
            "type": "order_response",
            "correlation_id": "TRANS_001",
            "status": "executed",
            "instrument": "USD/JPY",
            "amount": 200000,
            "rate": 110.55,
            "timestamp": datetime.utcnow().isoformat(),
        }

        fxml_report = translator.translate_response_to_fxml(forex_response, fix_order)

        assert fxml_report["cl_ord_id"] == "TRANS_001"
        assert fxml_report["symbol"] == "USDJPY"
        assert fxml_report["cum_qty"] == 200000
        assert fxml_report["avg_px"] == 110.55

    async def test_error_handling(self, bridge_adapter, mock_http_session):
        """Test error handling and recovery scenarios."""
        # Test connection failure
        mock_http_session.set_response(
            "http://test-bridge:8080/health",
            503,
            {"status": "unhealthy", "error": "ForexConnect disconnected"},
        )

        await bridge_adapter.connect()
        await bridge_adapter._check_bridge_health()

        assert not bridge_adapter._bridge_healthy

        # Test order submission failure when unhealthy
        test_order = NewOrderSingle(
            cl_ord_id="ERROR_001",
            symbol="EURGBP",
            side=Side.SELL,
            order_qty=75000,
            ord_type=OrdType.MARKET,
        )

        # Should still submit to queue even if bridge is unhealthy
        order_id = await bridge_adapter.submit_order(test_order)
        assert order_id == "ERROR_001"

        # Test order rejection handling
        rejection_response = {
            "type": "order_response",
            "correlation_id": "ERROR_001",
            "status": "rejected",
            "error": "Insufficient margin",
            "timestamp": datetime.utcnow().isoformat(),
        }

        response_queue = bridge_adapter._order_response_queue
        await response_queue.put_message(rejection_response)

        # Verify rejected order is cleaned up
        await asyncio.sleep(0.1)
        assert "ERROR_001" not in bridge_adapter._pending_orders

        await bridge_adapter.disconnect()

    async def test_health_monitoring(self, bridge_adapter, mock_http_session):
        """Test health monitoring and status reporting."""
        # Set up various health responses
        mock_http_session.set_response(
            "http://test-bridge:8080/health",
            200,
            {
                "status": "healthy",
                "forex_connect": "connected",
                "last_heartbeat": datetime.utcnow().isoformat(),
                "pending_orders": 5,
                "active_subscriptions": 3,
            },
        )

        await bridge_adapter.connect()

        # Get health status
        health = await bridge_adapter.health_check()

        assert health["adapter"] == "fxcm_bridge"
        assert health["connected"]
        assert health["bridge_healthy"]
        assert "bridge_status" in health
        assert health["bridge_status"]["status"] == "healthy"

        await bridge_adapter.disconnect()

    async def test_concurrent_operations(self, bridge_adapter):
        """Test concurrent order submissions and market data handling."""
        await bridge_adapter.connect()

        # Submit multiple orders concurrently
        orders = []
        for i in range(5):
            order = NewOrderSingle(
                cl_ord_id=f"CONCURRENT_{i:03d}",
                symbol="AUDUSD",
                side=Side.BUY if i % 2 == 0 else Side.SELL,
                order_qty=10000 * (i + 1),
                ord_type=OrdType.MARKET,
            )
            orders.append(order)

        # Submit all orders concurrently
        tasks = [bridge_adapter.submit_order(order) for order in orders]
        order_ids = await asyncio.gather(*tasks)

        # Verify all orders were submitted
        assert len(order_ids) == 5
        assert len(bridge_adapter._pending_orders) == 5

        # Simulate concurrent responses
        response_tasks = []
        for i, order in enumerate(orders):
            response = {
                "type": "order_response",
                "correlation_id": order.cl_ord_id,
                "status": "executed",
                "order_id": f"FC_{i:05d}",
                "amount": order.order_qty,
                "rate": 0.7500 + (i * 0.0001),
                "timestamp": datetime.utcnow().isoformat(),
            }

            task = bridge_adapter._order_response_queue.put_message(response)
            response_tasks.append(task)

        # Process all responses
        await asyncio.gather(*response_tasks)
        await asyncio.sleep(0.1)  # Allow processing time

        # Verify all orders were processed
        assert len(bridge_adapter._pending_orders) == 0

        await bridge_adapter.disconnect()

    async def test_message_correlation_cleanup(self, bridge_adapter):
        """Test correlation tracking and cleanup of stale orders."""
        await bridge_adapter.connect()

        # Submit test order
        test_order = NewOrderSingle(
            cl_ord_id="CLEANUP_001",
            symbol="NZDUSD",
            side=Side.BUY,
            order_qty=25000,
            ord_type=OrdType.MARKET,
        )

        await bridge_adapter.submit_order(test_order)

        # Verify order is pending
        assert "CLEANUP_001" in bridge_adapter._pending_orders

        # Manually age the order
        bridge_adapter._pending_orders["CLEANUP_001"][
            "submitted_at"
        ] = datetime.utcnow() - timedelta(hours=2)

        # TODO: Implement cleanup mechanism in adapter
        # This would normally be handled by a periodic cleanup task

        await bridge_adapter.disconnect()


@pytest.mark.asyncio
class TestIntegrationScenarios:
    """End-to-end integration scenarios."""

    async def test_complete_trading_workflow(self, bridge_adapter):
        """Test complete workflow: connect → subscribe → order → execution → disconnect."""
        # Step 1: Connect
        await bridge_adapter.connect()
        assert bridge_adapter.is_connected

        # Step 2: Subscribe to market data
        market_updates = []

        async def track_updates(symbol: str, data: Dict[str, Any]):
            market_updates.append(f"{symbol}: {data['bid']}/{data['ask']}")

        await bridge_adapter.subscribe_market_data(["EURUSD"], track_updates)

        # Step 3: Submit order
        order = NewOrderSingle(
            cl_ord_id="WORKFLOW_001",
            symbol="EURUSD",
            side=Side.BUY,
            order_qty=100000,
            ord_type=OrdType.MARKET,
        )

        order_id = await bridge_adapter.submit_order(order)
        assert order_id == "WORKFLOW_001"

        # Step 4: Simulate market data
        market_data = {
            "type": "price_update",
            "instrument": "EUR/USD",
            "bid": 1.1250,
            "ask": 1.1252,
            "timestamp": datetime.utcnow().isoformat(),
        }

        await bridge_adapter._market_data_queue.put_message(market_data)
        await asyncio.sleep(0.1)

        # Step 5: Simulate execution
        execution = {
            "type": "order_response",
            "correlation_id": "WORKFLOW_001",
            "status": "executed",
            "order_id": "FC_WORKFLOW",
            "amount": 100000,
            "rate": 1.1251,
            "timestamp": datetime.utcnow().isoformat(),
        }

        await bridge_adapter._order_response_queue.put_message(execution)
        await asyncio.sleep(0.1)

        # Step 6: Verify results
        assert len(market_updates) > 0
        assert "WORKFLOW_001" not in bridge_adapter._pending_orders

        # Step 7: Disconnect
        await bridge_adapter.disconnect()
        assert not bridge_adapter.is_connected


if __name__ == "__main__":
    """Run integration tests manually."""
    import sys

    async def run_tests():
        """Run basic integration tests."""
        print("Running FXML4-ForexConnect Bridge Integration Tests...")

        # Create test adapter
        config = {
            "bridge_url": "http://localhost:8080",
            "rabbitmq": {
                "host": "localhost",
                "port": 5672,
                "username": "fxml4",
                "password": "fxml4_pass",
            },
        }

        adapter = FXCMBridgeAdapter(config)

        try:
            # Test basic connection
            await adapter.connect()
            print("✓ Connection successful")

            # Test health check
            health = await adapter.health_check()
            print(f"✓ Health check: {health['connected']}")

            # Test message translation
            translator = get_message_translator()
            order = NewOrderSingle(
                cl_ord_id="TEST001",
                symbol="EURUSD",
                side=Side.BUY,
                order_qty=100000,
                ord_type=OrdType.MARKET,
            )

            forex_order = translator.translate_order_to_forex(order)
            print(f"✓ Message translation: {forex_order['instrument']}")

            await adapter.disconnect()
            print("✓ Disconnection successful")

            print("\nAll basic integration tests passed!")

        except Exception as e:
            print(f"✗ Test failed: {e}")
            sys.exit(1)

    # Run tests
    asyncio.run(run_tests())
