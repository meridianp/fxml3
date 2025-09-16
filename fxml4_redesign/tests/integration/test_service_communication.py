"""Integration tests for service communication."""

import asyncio
import json
from datetime import datetime
from typing import Any, Dict, List

import pytest
from fixtures.market_data_fixtures import MarketDataGenerator
from fixtures.rabbitmq_fixtures import RabbitMQTestHarness, create_test_messages


@pytest.mark.integration
class TestServiceCommunication:
    """Test inter-service communication patterns."""

    @pytest.fixture
    async def rabbitmq_harness(self):
        """Create RabbitMQ test harness."""
        harness = RabbitMQTestHarness()
        await harness.setup()
        yield harness
        await harness.teardown()

    @pytest.mark.asyncio
    async def test_market_data_flow(self, rabbitmq_harness):
        """Test market data flow from collector to signal generator."""
        # Set up bindings
        await rabbitmq_harness.bind_queue(
            "market.data.eurusd", "market.data", "market.ready.EURUSD"
        )

        # Create test market data
        market_data = MarketDataGenerator.generate_market_snapshot("EURUSD")

        # Simulate data collector publishing
        await rabbitmq_harness.publish(
            "market.data",
            "market.ready.EURUSD",
            {
                "symbol": "EURUSD",
                "timeframe": "4H",
                "data": market_data,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

        # Verify message was published
        messages = rabbitmq_harness.get_published_messages("market.data")
        assert len(messages) == 1
        assert messages[0]["body"]["symbol"] == "EURUSD"
        assert messages[0]["routing_key"] == "market.ready.EURUSD"

    @pytest.mark.asyncio
    async def test_signal_generation_flow(self, rabbitmq_harness):
        """Test signal flow from generator to entry manager."""
        # Set up exchanges and queues
        await rabbitmq_harness.bind_queue(
            "trading.signals.all", "trading.signals", "signal.new.#"
        )

        # Create test signal
        test_signal = {
            "symbol": "EURUSD",
            "direction": "BUY",
            "entry_price": 1.0850,
            "stop_loss": 1.0820,
            "take_profit": 1.0880,
            "confidence": 0.75,
            "source": "ml_model",
        }

        # Simulate signal generator publishing
        await rabbitmq_harness.publish(
            "trading.signals", "signal.new.EURUSD", test_signal
        )

        # Verify
        messages = rabbitmq_harness.get_published_messages("trading.signals")
        assert len(messages) == 1
        assert messages[0]["body"]["direction"] == "BUY"

    @pytest.mark.asyncio
    async def test_trade_execution_flow(self, rabbitmq_harness):
        """Test complete trade execution flow."""
        # Create all necessary exchanges and queues
        await rabbitmq_harness.declare_exchange("trades", "topic")
        await rabbitmq_harness.declare_queue("trades.executions")
        await rabbitmq_harness.bind_queue(
            "trades.executions", "trades", "trade.executed.#"
        )

        # Messages to track
        execution_messages = []

        async def execution_handler(message):
            execution_messages.append(message)

        # Set up consumer
        await rabbitmq_harness.consume("trades.executions", execution_handler)

        # Simulate trade execution
        trade_execution = {
            "trade_id": "TRADE-001",
            "symbol": "EURUSD",
            "direction": "BUY",
            "entry_price": 1.0850,
            "position_size": 10000,
            "status": "filled",
            "execution_time": datetime.utcnow().isoformat(),
        }

        # Publish and simulate message delivery
        await rabbitmq_harness.publish(
            "trades", "trade.executed.EURUSD", trade_execution
        )
        await rabbitmq_harness.simulate_message(
            "trades.executions", trade_execution, "trade.executed.EURUSD"
        )

        # Wait for processing
        await asyncio.sleep(0.1)

        # Verify execution was received
        assert len(execution_messages) == 1
        assert execution_messages[0]["trade_id"] == "TRADE-001"

    @pytest.mark.asyncio
    async def test_multi_service_workflow(self, rabbitmq_harness):
        """Test complete multi-service workflow."""
        # Track messages through the system
        workflow_messages = {
            "market_data": [],
            "signals": [],
            "trades": [],
            "updates": [],
        }

        # Set up all exchanges and queues
        exchanges = ["market.data", "trading.signals", "trades", "system"]
        for exchange in exchanges:
            await rabbitmq_harness.declare_exchange(exchange, "topic")

        # 1. Market data update
        market_update = {
            "symbol": "GBPUSD",
            "timeframe": "4H",
            "data": {"close": 1.2650, "volume": 5000},
            "indicators": {"rsi_14": 65.5, "macd": 0.0003},
        }

        await rabbitmq_harness.publish(
            "market.data", "market.ready.GBPUSD", market_update
        )

        # 2. Signal generation (simulated)
        signal = {
            "symbol": "GBPUSD",
            "direction": "SELL",
            "entry_price": 1.2650,
            "confidence": 0.82,
            "based_on": "market.ready.GBPUSD",
        }

        await rabbitmq_harness.publish("trading.signals", "signal.new.GBPUSD", signal)

        # 3. Trade execution (simulated)
        trade = {
            "trade_id": "TRADE-GBPUSD-001",
            "signal_id": "SIG-001",
            "symbol": "GBPUSD",
            "direction": "SELL",
            "entry_price": 1.2649,  # Slight slippage
            "position_size": 5000,
            "status": "filled",
        }

        await rabbitmq_harness.publish("trades", "trade.executed.GBPUSD", trade)

        # 4. Position update
        position_update = {
            "trade_id": "TRADE-GBPUSD-001",
            "symbol": "GBPUSD",
            "current_price": 1.2645,
            "pnl": 20.0,  # 4 pips profit
            "status": "open",
        }

        await rabbitmq_harness.publish("trades", "trade.update.GBPUSD", position_update)

        # Verify all messages were published
        market_messages = rabbitmq_harness.get_published_messages("market.data")
        signal_messages = rabbitmq_harness.get_published_messages("trading.signals")
        trade_messages = rabbitmq_harness.get_published_messages("trades")

        assert len(market_messages) == 1
        assert len(signal_messages) == 1
        assert len(trade_messages) == 2  # execution + update

        # Verify message flow
        assert signal_messages[0]["body"]["based_on"] == "market.ready.GBPUSD"
        assert trade_messages[0]["body"]["signal_id"] == "SIG-001"

    @pytest.mark.asyncio
    async def test_error_propagation(self, rabbitmq_harness):
        """Test error propagation between services."""
        # Set up error handling
        await rabbitmq_harness.declare_exchange("system", "topic")
        await rabbitmq_harness.declare_queue("system.errors")
        await rabbitmq_harness.bind_queue("system.errors", "system", "error.#")

        errors_received = []

        async def error_handler(message):
            errors_received.append(message)

        await rabbitmq_harness.consume("system.errors", error_handler)

        # Simulate various service errors
        errors = [
            {
                "service": "data-collector",
                "error_type": "ConnectionError",
                "message": "Failed to connect to IB Gateway",
                "context": {"symbol": "EURUSD", "attempt": 3},
            },
            {
                "service": "signal-generator",
                "error_type": "ModelError",
                "message": "Model prediction failed",
                "context": {"model": "ml_v2", "symbol": "GBPUSD"},
            },
            {
                "service": "trade-manager",
                "error_type": "ExecutionError",
                "message": "Order rejected by broker",
                "context": {"order_id": "ORD-001", "reason": "Insufficient margin"},
            },
        ]

        # Publish errors
        for error in errors:
            await rabbitmq_harness.publish("system", f"error.{error['service']}", error)

            # Simulate delivery
            await rabbitmq_harness.simulate_message(
                "system.errors", error, f"error.{error['service']}"
            )

        # Wait for processing
        await asyncio.sleep(0.1)

        # Verify all errors were received
        assert len(errors_received) == 3

        # Verify error details
        service_errors = {e["service"]: e for e in errors_received}

        assert "data-collector" in service_errors
        assert service_errors["data-collector"]["error_type"] == "ConnectionError"

        assert "signal-generator" in service_errors
        assert service_errors["signal-generator"]["context"]["model"] == "ml_v2"

        assert "trade-manager" in service_errors
        assert (
            "Insufficient margin"
            in service_errors["trade-manager"]["context"]["reason"]
        )

    @pytest.mark.asyncio
    async def test_heartbeat_monitoring(self, rabbitmq_harness):
        """Test service heartbeat monitoring."""
        # Set up heartbeat monitoring
        await rabbitmq_harness.declare_exchange("system", "topic")
        await rabbitmq_harness.declare_queue("system.heartbeats")
        await rabbitmq_harness.bind_queue("system.heartbeats", "system", "heartbeat.#")

        heartbeats = {}

        async def heartbeat_handler(message):
            heartbeats[message["service_name"]] = message

        await rabbitmq_harness.consume("system.heartbeats", heartbeat_handler)

        # Simulate heartbeats from all services
        services = [
            "data-collector",
            "signal-generator",
            "llm-analyzer",
            "entry-manager",
            "trade-manager",
            "monitor",
        ]

        for service in services:
            heartbeat = {
                "service_name": service,
                "status": "healthy",
                "timestamp": datetime.utcnow().isoformat(),
                "metrics": {"cpu_usage": 45.2, "memory_mb": 256, "active_tasks": 5},
            }

            await rabbitmq_harness.publish("system", f"heartbeat.{service}", heartbeat)

            await rabbitmq_harness.simulate_message(
                "system.heartbeats", heartbeat, f"heartbeat.{service}"
            )

        # Wait for processing
        await asyncio.sleep(0.1)

        # Verify all services reported
        assert len(heartbeats) == 6

        # All should be healthy
        for service, heartbeat in heartbeats.items():
            assert heartbeat["status"] == "healthy"
            assert "metrics" in heartbeat

    @pytest.mark.asyncio
    @pytest.mark.benchmark
    async def test_message_throughput(self, rabbitmq_harness, performance_benchmark):
        """Benchmark message throughput."""
        # Set up high-volume queue
        await rabbitmq_harness.declare_queue("performance.test")

        messages_received = []

        async def message_handler(msg):
            messages_received.append(msg)

        await rabbitmq_harness.consume("performance.test", message_handler)

        # Generate messages
        num_messages = 1000

        performance_benchmark.start("message_throughput")

        # Publish messages
        for i in range(num_messages):
            message = {
                "index": i,
                "timestamp": datetime.utcnow().isoformat(),
                "data": "x" * 100,  # 100 byte payload
            }

            await rabbitmq_harness.simulate_message(
                "performance.test", message, "perf.test"
            )

        # Wait for all messages
        while len(messages_received) < num_messages:
            await asyncio.sleep(0.01)

        performance_benchmark.stop("message_throughput")

        # Verify
        assert len(messages_received) == num_messages

        # Check performance
        duration = performance_benchmark.get_duration("message_throughput")
        throughput = num_messages / duration

        print(f"\nMessage throughput: {throughput:.0f} messages/second")
        assert throughput > 100, f"Throughput too low: {throughput:.0f} msg/s"
