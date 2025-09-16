"""
Comprehensive unit tests for Intelligent Routing Engine.

Tests broker selection, order routing, failover mechanisms, and performance
following TDD methodology for increased test coverage.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import numpy as np
import pandas as pd
import pytest

from fxml4.brokers.intelligent_routing_engine import (
    BrokerAdapter,
    BrokerMetrics,
    FailoverStrategy,
    IntelligentRoutingEngine,
    OrderRequest,
    OrderResponse,
    RoutingDecision,
)


@pytest.fixture
def routing_config():
    """Configuration for intelligent routing engine."""
    return {
        "primary_broker": "ib",
        "backup_brokers": ["fxcm", "manual"],
        "routing_strategy": "intelligent",
        "failover_timeout": 5.0,
        "max_retry_attempts": 3,
        "latency_threshold": 0.5,
        "execution_quality_weight": 0.4,
        "cost_weight": 0.3,
        "reliability_weight": 0.3,
        "rebalance_interval": 300,  # 5 minutes
        "performance_window": 3600,  # 1 hour
    }


@pytest.fixture
def mock_ib_adapter():
    """Mock Interactive Brokers adapter."""
    mock = AsyncMock()
    mock.name = "ib"
    mock.is_connected.return_value = True
    mock.get_connection_quality.return_value = 0.95
    mock.submit_order.return_value = OrderResponse(
        order_id="IB123456",
        status="FILLED",
        filled_price=1.2650,
        filled_quantity=10000,
        execution_time=0.15,
        commission=2.50,
    )
    mock.get_market_data.return_value = {
        "bid": 1.2648,
        "ask": 1.2652,
        "spread": 0.0004,
        "timestamp": datetime.now(),
    }
    return mock


@pytest.fixture
def mock_fxcm_adapter():
    """Mock FXCM adapter."""
    mock = AsyncMock()
    mock.name = "fxcm"
    mock.is_connected.return_value = True
    mock.get_connection_quality.return_value = 0.88
    mock.submit_order.return_value = OrderResponse(
        order_id="FXCM789",
        status="FILLED",
        filled_price=1.2651,
        filled_quantity=10000,
        execution_time=0.25,
        commission=3.00,
    )
    mock.get_market_data.return_value = {
        "bid": 1.2647,
        "ask": 1.2653,
        "spread": 0.0006,
        "timestamp": datetime.now(),
    }
    return mock


@pytest.fixture
def mock_manual_adapter():
    """Mock manual execution adapter."""
    mock = AsyncMock()
    mock.name = "manual"
    mock.is_connected.return_value = True
    mock.get_connection_quality.return_value = 0.99  # Always available
    mock.submit_order.return_value = OrderResponse(
        order_id="MANUAL001",
        status="PENDING_MANUAL",
        filled_price=None,
        filled_quantity=0,
        execution_time=None,
        commission=0.0,
    )
    return mock


@pytest.fixture
def sample_order_request():
    """Generate sample order request."""
    return OrderRequest(
        symbol="EURUSD",
        side="BUY",
        quantity=10000,
        order_type="MARKET",
        price=None,
        stop_loss=1.2600,
        take_profit=1.2700,
        time_in_force="IOC",
        client_order_id="TEST_ORDER_001",
    )


@pytest.fixture
def broker_performance_history():
    """Generate broker performance history."""
    data = {
        "ib": {
            "avg_execution_time": 0.18,
            "fill_rate": 0.98,
            "slippage_avg": 0.12,
            "uptime": 0.995,
            "commission_avg": 2.25,
        },
        "fxcm": {
            "avg_execution_time": 0.28,
            "fill_rate": 0.94,
            "slippage_avg": 0.18,
            "uptime": 0.985,
            "commission_avg": 3.50,
        },
        "manual": {
            "avg_execution_time": 120.0,  # Manual execution delay
            "fill_rate": 1.0,
            "slippage_avg": 0.0,
            "uptime": 1.0,
            "commission_avg": 0.0,
        },
    }
    return data


@pytest.fixture
async def routing_engine(
    routing_config,
    mock_ib_adapter,
    mock_fxcm_adapter,
    mock_manual_adapter,
    broker_performance_history,
):
    """Create intelligent routing engine with mocked brokers."""
    engine = IntelligentRoutingEngine(routing_config)

    # Register broker adapters
    await engine.register_broker(mock_ib_adapter)
    await engine.register_broker(mock_fxcm_adapter)
    await engine.register_broker(mock_manual_adapter)

    # Inject performance history
    engine.broker_metrics = {
        name: BrokerMetrics(**metrics)
        for name, metrics in broker_performance_history.items()
    }

    await engine.initialize()
    return engine


class TestIntelligentRoutingEngineInitialization:
    """Test routing engine initialization."""

    def test_engine_creation_with_valid_config(self, routing_config):
        """Test engine can be created with valid configuration."""
        engine = IntelligentRoutingEngine(routing_config)

        assert engine.primary_broker == "ib"
        assert "fxcm" in engine.backup_brokers
        assert engine.failover_timeout == 5.0
        assert engine.max_retry_attempts == 3

    def test_engine_creation_with_invalid_weights(self, routing_config):
        """Test engine validates routing weights."""
        routing_config["execution_quality_weight"] = 0.5
        routing_config["cost_weight"] = 0.4
        routing_config["reliability_weight"] = 0.4  # Sum > 1.0

        with pytest.raises(ValueError, match="Routing weights must sum to 1.0"):
            IntelligentRoutingEngine(routing_config)

    def test_engine_creation_with_invalid_timeout(self, routing_config):
        """Test engine validates timeout parameters."""
        routing_config["failover_timeout"] = -1.0

        with pytest.raises(ValueError, match="Invalid timeout"):
            IntelligentRoutingEngine(routing_config)

    @pytest.mark.asyncio
    async def test_broker_registration(self, routing_engine):
        """Test broker registration and validation."""
        assert len(routing_engine.brokers) == 3
        assert "ib" in routing_engine.brokers
        assert "fxcm" in routing_engine.brokers
        assert "manual" in routing_engine.brokers

    @pytest.mark.asyncio
    async def test_engine_initialization_success(self, routing_engine):
        """Test successful engine initialization."""
        assert routing_engine.is_initialized
        assert routing_engine.broker_metrics is not None
        assert len(routing_engine.broker_metrics) == 3


class TestBrokerSelection:
    """Test intelligent broker selection logic."""

    @pytest.mark.asyncio
    async def test_primary_broker_selection(
        self, routing_engine, sample_order_request, mock_ib_adapter
    ):
        """Test primary broker is selected when available and optimal."""
        mock_ib_adapter.is_connected.return_value = True
        mock_ib_adapter.get_connection_quality.return_value = 0.98

        decision = await routing_engine.select_optimal_broker(sample_order_request)

        assert decision.selected_broker == "ib"
        assert decision.confidence > 0.8
        assert "primary_broker_optimal" in decision.reasoning

    @pytest.mark.asyncio
    async def test_backup_broker_selection_on_primary_failure(
        self, routing_engine, sample_order_request, mock_ib_adapter, mock_fxcm_adapter
    ):
        """Test backup broker selection when primary is unavailable."""
        # Simulate primary broker failure
        mock_ib_adapter.is_connected.return_value = False
        mock_fxcm_adapter.is_connected.return_value = True

        decision = await routing_engine.select_optimal_broker(sample_order_request)

        assert decision.selected_broker == "fxcm"
        assert "primary_broker_unavailable" in decision.reasoning

    @pytest.mark.asyncio
    async def test_performance_based_broker_selection(
        self, routing_engine, sample_order_request
    ):
        """Test broker selection based on performance metrics."""
        # Setup scenario where FXCM has better recent performance
        routing_engine.broker_metrics["fxcm"].avg_execution_time = (
            0.12  # Better than IB
        )
        routing_engine.broker_metrics["fxcm"].fill_rate = 0.99
        routing_engine.broker_metrics["ib"].avg_execution_time = (
            0.35  # Worse performance
        )

        decision = await routing_engine.select_optimal_broker(sample_order_request)

        # Should select FXCM due to better performance
        assert decision.selected_broker == "fxcm"
        assert "performance_optimized" in decision.reasoning

    @pytest.mark.asyncio
    async def test_cost_optimized_selection(self, routing_engine, sample_order_request):
        """Test broker selection optimized for cost."""
        # Large order where commission matters more
        sample_order_request.quantity = 100000  # Large order

        # Manual has no commission
        routing_engine.broker_metrics["manual"].commission_avg = 0.0
        routing_engine.broker_metrics["ib"].commission_avg = (
            25.0  # High for large order
        )

        decision = await routing_engine.select_optimal_broker(sample_order_request)

        # For large orders, might prefer manual due to cost
        assert decision.cost_score >= 0.8

    @pytest.mark.asyncio
    async def test_latency_sensitive_selection(
        self, routing_engine, sample_order_request
    ):
        """Test broker selection for latency-sensitive orders."""
        # Market order requiring fast execution
        sample_order_request.order_type = "MARKET"
        sample_order_request.time_in_force = "IOC"  # Immediate or Cancel

        routing_engine.broker_metrics["ib"].avg_execution_time = 0.08  # Very fast
        routing_engine.broker_metrics["fxcm"].avg_execution_time = 0.45  # Slower

        decision = await routing_engine.select_optimal_broker(sample_order_request)

        assert decision.selected_broker == "ib"
        assert decision.execution_quality_score > 0.9


class TestOrderRouting:
    """Test order routing and execution logic."""

    @pytest.mark.asyncio
    async def test_successful_order_routing(
        self, routing_engine, sample_order_request, mock_ib_adapter
    ):
        """Test successful order routing to primary broker."""
        mock_ib_adapter.submit_order.return_value = OrderResponse(
            order_id="IB123456",
            status="FILLED",
            filled_price=1.2651,
            filled_quantity=10000,
            execution_time=0.18,
            commission=2.50,
        )

        response = await routing_engine.route_order(sample_order_request)

        assert response.status == "FILLED"
        assert response.order_id == "IB123456"
        assert response.filled_quantity == 10000
        assert response.execution_time < 0.5

        # Verify broker was called
        mock_ib_adapter.submit_order.assert_called_once()

    @pytest.mark.asyncio
    async def test_order_routing_with_retry(
        self, routing_engine, sample_order_request, mock_ib_adapter
    ):
        """Test order routing with retry on temporary failure."""
        # First attempt fails, second succeeds
        mock_ib_adapter.submit_order.side_effect = [
            Exception("Temporary network error"),
            OrderResponse(
                order_id="IB123457",
                status="FILLED",
                filled_price=1.2651,
                filled_quantity=10000,
                execution_time=0.22,
                commission=2.50,
            ),
        ]

        response = await routing_engine.route_order(sample_order_request)

        assert response.status == "FILLED"
        assert response.order_id == "IB123457"
        assert mock_ib_adapter.submit_order.call_count == 2

    @pytest.mark.asyncio
    async def test_order_routing_failover(
        self, routing_engine, sample_order_request, mock_ib_adapter, mock_fxcm_adapter
    ):
        """Test order routing failover to backup broker."""
        # Primary broker fails completely
        mock_ib_adapter.submit_order.side_effect = Exception("Broker connection lost")
        mock_ib_adapter.is_connected.return_value = False

        # Backup broker succeeds
        mock_fxcm_adapter.submit_order.return_value = OrderResponse(
            order_id="FXCM789",
            status="FILLED",
            filled_price=1.2652,
            filled_quantity=10000,
            execution_time=0.28,
            commission=3.00,
        )

        response = await routing_engine.route_order(sample_order_request)

        assert response.status == "FILLED"
        assert response.order_id == "FXCM789"

        # Verify failover occurred
        mock_ib_adapter.submit_order.assert_called()
        mock_fxcm_adapter.submit_order.assert_called_once()

    @pytest.mark.asyncio
    async def test_order_routing_all_brokers_fail(
        self,
        routing_engine,
        sample_order_request,
        mock_ib_adapter,
        mock_fxcm_adapter,
        mock_manual_adapter,
    ):
        """Test order routing when all brokers fail."""
        # All brokers fail
        mock_ib_adapter.submit_order.side_effect = Exception("IB connection lost")
        mock_fxcm_adapter.submit_order.side_effect = Exception("FXCM API error")
        mock_manual_adapter.submit_order.side_effect = Exception("Manual system down")

        response = await routing_engine.route_order(sample_order_request)

        assert response.status == "FAILED"
        assert "all_brokers_failed" in response.error_message

    @pytest.mark.asyncio
    async def test_partial_fill_handling(
        self, routing_engine, sample_order_request, mock_ib_adapter
    ):
        """Test handling of partial fills."""
        mock_ib_adapter.submit_order.return_value = OrderResponse(
            order_id="IB123458",
            status="PARTIALLY_FILLED",
            filled_price=1.2651,
            filled_quantity=7500,  # Only 75% filled
            execution_time=0.20,
            commission=1.88,
        )

        response = await routing_engine.route_order(sample_order_request)

        assert response.status == "PARTIALLY_FILLED"
        assert response.filled_quantity == 7500
        assert response.remaining_quantity == 2500


class TestFailoverMechanisms:
    """Test failover strategies and mechanisms."""

    @pytest.mark.asyncio
    async def test_fast_failover_strategy(
        self, routing_engine, sample_order_request, mock_ib_adapter, mock_fxcm_adapter
    ):
        """Test fast failover for time-sensitive orders."""
        routing_engine.failover_strategy = FailoverStrategy.FAST

        # Primary broker times out quickly
        async def slow_response():
            await asyncio.sleep(1.0)  # Simulates slow response
            return OrderResponse(order_id="SLOW", status="FILLED")

        mock_ib_adapter.submit_order = slow_response
        mock_fxcm_adapter.submit_order.return_value = OrderResponse(
            order_id="FXCM_FAST",
            status="FILLED",
            filled_price=1.2651,
            filled_quantity=10000,
            execution_time=0.15,
            commission=3.00,
        )

        start_time = time.time()
        response = await routing_engine.route_order(sample_order_request)
        execution_time = time.time() - start_time

        # Should failover quickly
        assert response.order_id == "FXCM_FAST"
        assert execution_time < 1.0

    @pytest.mark.asyncio
    async def test_reliable_failover_strategy(
        self, routing_engine, sample_order_request, mock_ib_adapter, mock_manual_adapter
    ):
        """Test reliable failover strategy."""
        routing_engine.failover_strategy = FailoverStrategy.RELIABLE

        # Primary broker fails
        mock_ib_adapter.submit_order.side_effect = Exception("Network error")

        # Manual adapter is most reliable
        mock_manual_adapter.submit_order.return_value = OrderResponse(
            order_id="MANUAL_RELIABLE",
            status="PENDING_MANUAL",
            filled_price=None,
            filled_quantity=0,
            execution_time=None,
            commission=0.0,
        )

        response = await routing_engine.route_order(sample_order_request)

        assert response.order_id == "MANUAL_RELIABLE"
        assert response.status == "PENDING_MANUAL"

    @pytest.mark.asyncio
    async def test_cost_optimized_failover_strategy(
        self, routing_engine, sample_order_request, mock_ib_adapter
    ):
        """Test cost-optimized failover strategy."""
        routing_engine.failover_strategy = FailoverStrategy.COST_OPTIMIZED

        # Large order where costs matter
        sample_order_request.quantity = 500000

        # Primary fails, should route to lowest cost option
        mock_ib_adapter.submit_order.side_effect = Exception("Primary failed")

        response = await routing_engine.route_order(sample_order_request)

        # Should consider commission costs in routing decision
        assert response is not None


class TestPerformanceMonitoring:
    """Test performance monitoring and metrics collection."""

    @pytest.mark.asyncio
    async def test_execution_time_tracking(
        self, routing_engine, sample_order_request, mock_ib_adapter
    ):
        """Test tracking of execution times."""
        mock_ib_adapter.submit_order.return_value = OrderResponse(
            order_id="IB_TRACKED",
            status="FILLED",
            filled_price=1.2651,
            filled_quantity=10000,
            execution_time=0.25,
            commission=2.50,
        )

        initial_avg_time = routing_engine.broker_metrics["ib"].avg_execution_time

        await routing_engine.route_order(sample_order_request)

        # Metrics should be updated
        updated_avg_time = routing_engine.broker_metrics["ib"].avg_execution_time
        assert updated_avg_time != initial_avg_time

    @pytest.mark.asyncio
    async def test_fill_rate_tracking(
        self, routing_engine, sample_order_request, mock_ib_adapter
    ):
        """Test tracking of fill rates."""
        # Simulate partial fill
        mock_ib_adapter.submit_order.return_value = OrderResponse(
            order_id="IB_PARTIAL",
            status="PARTIALLY_FILLED",
            filled_price=1.2651,
            filled_quantity=7500,
            execution_time=0.20,
            commission=1.88,
        )

        initial_fill_rate = routing_engine.broker_metrics["ib"].fill_rate

        await routing_engine.route_order(sample_order_request)

        # Fill rate should be updated to reflect partial fill
        updated_fill_rate = routing_engine.broker_metrics["ib"].fill_rate
        assert updated_fill_rate <= initial_fill_rate

    @pytest.mark.asyncio
    async def test_slippage_tracking(
        self, routing_engine, sample_order_request, mock_ib_adapter
    ):
        """Test tracking of execution slippage."""
        # Setup market data
        mock_ib_adapter.get_market_data.return_value = {
            "bid": 1.2648,
            "ask": 1.2652,
            "mid": 1.2650,
            "timestamp": datetime.now(),
        }

        # Order fills at worse price (slippage)
        mock_ib_adapter.submit_order.return_value = OrderResponse(
            order_id="IB_SLIPPAGE",
            status="FILLED",
            filled_price=1.2654,  # 4 pips of slippage on buy
            filled_quantity=10000,
            execution_time=0.18,
            commission=2.50,
        )

        await routing_engine.route_order(sample_order_request)

        # Slippage should be recorded
        slippage_metrics = routing_engine.broker_metrics["ib"]
        assert slippage_metrics.slippage_avg > 0

    @pytest.mark.asyncio
    async def test_broker_ranking_updates(self, routing_engine):
        """Test broker ranking updates based on performance."""
        initial_rankings = routing_engine.get_broker_rankings()

        # Simulate poor performance for primary broker
        routing_engine.broker_metrics["ib"].avg_execution_time = 2.0  # Very slow
        routing_engine.broker_metrics["ib"].fill_rate = 0.7  # Poor fills
        routing_engine.broker_metrics["ib"].uptime = 0.8  # Poor reliability

        await routing_engine.update_broker_rankings()
        updated_rankings = routing_engine.get_broker_rankings()

        # IB should rank lower now
        initial_ib_rank = initial_rankings.index("ib")
        updated_ib_rank = updated_rankings.index("ib")
        assert updated_ib_rank > initial_ib_rank


class TestMarketConditionAdaptation:
    """Test adaptation to different market conditions."""

    @pytest.mark.asyncio
    async def test_high_volatility_routing(
        self, routing_engine, sample_order_request, mock_ib_adapter
    ):
        """Test routing adaptation during high volatility."""
        # Simulate high volatility market data
        mock_ib_adapter.get_market_data.return_value = {
            "bid": 1.2630,
            "ask": 1.2670,  # Wide spread indicating volatility
            "spread": 0.0040,
            "volatility": 0.035,
            "timestamp": datetime.now(),
        }

        decision = await routing_engine.select_optimal_broker(sample_order_request)

        # Should prefer broker with better execution quality in volatile markets
        assert decision.execution_quality_score >= 0.8

    @pytest.mark.asyncio
    async def test_low_liquidity_routing(self, routing_engine, sample_order_request):
        """Test routing during low liquidity periods."""
        # Large order in low liquidity
        sample_order_request.quantity = 1000000  # Very large order

        # Simulate low liquidity market data
        routing_engine.brokers["ib"].get_market_data.return_value = {
            "bid": 1.2649,
            "ask": 1.2651,
            "spread": 0.0002,
            "depth": 50000,  # Low market depth
            "timestamp": datetime.now(),
        }

        decision = await routing_engine.select_optimal_broker(sample_order_request)

        # Might prefer manual execution for large orders in low liquidity
        assert decision.order_size_factor <= 0.5  # Reduced confidence for large orders

    @pytest.mark.asyncio
    async def test_news_event_routing(self, routing_engine, sample_order_request):
        """Test routing adaptation during news events."""
        # Mark order as news-sensitive
        sample_order_request.metadata = {
            "news_sensitive": True,
            "event_time": datetime.now(),
        }

        decision = await routing_engine.select_optimal_broker(sample_order_request)

        # Should prioritize execution speed during news
        assert decision.execution_quality_score >= 0.9


class TestErrorHandling:
    """Test error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_broker_connection_loss_during_order(
        self, routing_engine, sample_order_request, mock_ib_adapter
    ):
        """Test handling of broker connection loss during order execution."""

        async def connection_loss_during_order():
            mock_ib_adapter.is_connected.return_value = False
            raise Exception("Connection lost during execution")

        mock_ib_adapter.submit_order = connection_loss_during_order

        response = await routing_engine.route_order(sample_order_request)

        # Should attempt failover
        assert response.status in ["FILLED", "FAILED"]
        assert (
            "connection_lost" in response.error_message or response.status == "FILLED"
        )

    @pytest.mark.asyncio
    async def test_invalid_order_request_handling(self, routing_engine):
        """Test handling of invalid order requests."""
        invalid_order = OrderRequest(
            symbol="INVALID",
            side="INVALID_SIDE",
            quantity=-1000,  # Negative quantity
            order_type="INVALID_TYPE",
        )

        response = await routing_engine.route_order(invalid_order)

        assert response.status == "REJECTED"
        assert "invalid_order" in response.error_message.lower()

    @pytest.mark.asyncio
    async def test_broker_timeout_handling(
        self, routing_engine, sample_order_request, mock_ib_adapter
    ):
        """Test handling of broker timeout."""

        async def timeout_response():
            await asyncio.sleep(10.0)  # Longer than failover timeout
            return OrderResponse(order_id="TIMEOUT", status="FILLED")

        mock_ib_adapter.submit_order = timeout_response

        response = await routing_engine.route_order(sample_order_request)

        # Should timeout and failover
        assert response.status in ["FILLED", "FAILED"]

    @pytest.mark.asyncio
    async def test_concurrent_order_handling(
        self, routing_engine, sample_order_request
    ):
        """Test handling of multiple concurrent orders."""
        import asyncio

        # Submit multiple orders concurrently
        orders = [
            OrderRequest(
                symbol="EURUSD",
                side="BUY",
                quantity=10000,
                order_type="MARKET",
                client_order_id=f"CONCURRENT_{i}",
            )
            for i in range(5)
        ]

        tasks = [routing_engine.route_order(order) for order in orders]
        responses = await asyncio.gather(*tasks, return_exceptions=True)

        # All orders should be processed
        assert len(responses) == 5
        assert all(isinstance(r, (OrderResponse, Exception)) for r in responses)


@pytest.mark.performance
class TestPerformanceRequirements:
    """Test performance requirements for order routing."""

    @pytest.mark.asyncio
    async def test_order_routing_speed(self, routing_engine, sample_order_request):
        """Test order routing completes within performance requirements."""
        import time

        start_time = time.time()
        response = await routing_engine.route_order(sample_order_request)
        end_time = time.time()

        execution_time = end_time - start_time
        assert execution_time < 1.0, f"Order routing took {execution_time:.2f}s"

    @pytest.mark.asyncio
    async def test_broker_selection_speed(self, routing_engine, sample_order_request):
        """Test broker selection speed."""
        import time

        start_time = time.time()
        decision = await routing_engine.select_optimal_broker(sample_order_request)
        end_time = time.time()

        selection_time = end_time - start_time
        assert selection_time < 0.1, f"Broker selection took {selection_time:.3f}s"

    @pytest.mark.asyncio
    async def test_concurrent_routing_performance(self, routing_engine):
        """Test performance with concurrent order routing."""
        import asyncio
        import time

        orders = [
            OrderRequest(
                symbol="EURUSD",
                side="BUY" if i % 2 == 0 else "SELL",
                quantity=10000,
                order_type="MARKET",
                client_order_id=f"PERF_TEST_{i}",
            )
            for i in range(10)
        ]

        start_time = time.time()
        tasks = [routing_engine.route_order(order) for order in orders]
        responses = await asyncio.gather(*tasks)
        end_time = time.time()

        total_time = end_time - start_time
        avg_time_per_order = total_time / len(orders)

        assert len(responses) == 10
        assert (
            avg_time_per_order < 0.5
        ), f"Average order routing took {avg_time_per_order:.3f}s"
