"""
Unit tests for Order Router.

Tests comprehensive order routing functionality including:
- Multi-broker order routing and failover
- Order type validation and transformation
- Latency-based routing optimization
- Load balancing across multiple brokers
- Order execution prioritization
- Risk-aware routing decisions
- Real-time broker health monitoring
- Order splitting and aggregation
- Regulatory compliance routing
- Market hours and session handling
"""

import asyncio
from datetime import datetime, time, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from freezegun import freeze_time

from core.exceptions import (
    BrokerError,
    ConfigurationError,
    OrderError,
    RiskManagementError,
)
from core.order_management.order_router import OrderRouter
from core.order_management.order_types import Order, OrderSide, OrderStatus, OrderType


class TestOrderRouter:
    """Test suite for order routing functionality."""

    @pytest.fixture
    def router_config(self):
        """Configuration for order router."""
        return {
            "brokers": {
                "IB": {
                    "priority": 1,
                    "weight": 40,
                    "max_orders_per_second": 5,
                    "supported_symbols": ["EUR/USD", "GBP/USD", "USD/JPY"],
                    "supported_order_types": ["market", "limit", "stop"],
                    "min_size": 1000,
                    "max_size": 10000000,
                    "trading_hours": {"start": "09:30", "end": "16:00"},
                    "commission": 0.0002,
                },
                "FXCM": {
                    "priority": 2,
                    "weight": 35,
                    "max_orders_per_second": 3,
                    "supported_symbols": ["EUR/USD", "GBP/USD", "AUD/USD"],
                    "supported_order_types": ["market", "limit"],
                    "min_size": 1000,
                    "max_size": 5000000,
                    "trading_hours": {"start": "08:00", "end": "17:00"},
                    "commission": 0.0003,
                },
                "OANDA": {
                    "priority": 3,
                    "weight": 25,
                    "max_orders_per_second": 2,
                    "supported_symbols": ["EUR/USD", "USD/CAD", "NZD/USD"],
                    "supported_order_types": [
                        "market",
                        "limit",
                        "stop",
                        "trailing_stop",
                    ],
                    "min_size": 100,
                    "max_size": 1000000,
                    "trading_hours": {"start": "00:00", "end": "23:59"},
                    "commission": 0.0004,
                },
            },
            "routing_strategy": "latency_optimized",
            "failover_enabled": True,
            "max_routing_attempts": 3,
            "health_check_interval": 30,
            "load_balancing": True,
            "risk_limits": {
                "max_order_size": 1000000,
                "max_daily_volume": 50000000,
                "position_limits": {"EUR/USD": 5000000},
            },
        }

    @pytest.fixture
    def order_router(self, router_config):
        """Create order router instance for testing."""
        return OrderRouter(router_config)

    @pytest.fixture
    def sample_order(self):
        """Sample order for testing."""
        return Order(
            order_id="ORDER_001",
            symbol="EUR/USD",
            order_type=OrderType.MARKET,
            side=OrderSide.BUY,
            quantity=10000,
            price=None,
            stop_price=None,
            time_in_force="IOC",
            client_id="CLIENT_001",
            created_at=datetime.utcnow(),
        )

    def test_routes_order_to_best_broker(self, order_router, sample_order):
        """Test routing order to broker with best conditions."""
        # Mock broker clients
        with patch.object(
            order_router,
            "_get_broker_latencies",
            return_value={"IB": 1.2, "FXCM": 2.1, "OANDA": 3.5},
        ):
            with patch.object(order_router, "_check_broker_health", return_value=True):
                routing_decision = order_router.route_order(sample_order)

                # Should route to IB (lowest latency, highest priority)
                assert routing_decision["selected_broker"] == "IB"
                assert routing_decision["reason"] == "latency_optimized"
                assert "routing_score" in routing_decision
                assert routing_decision["fallback_brokers"] == ["FXCM", "OANDA"]

    def test_validates_order_constraints(self, order_router, sample_order):
        """Test order validation against broker constraints."""
        # Test minimum size constraint
        sample_order.quantity = 500  # Below IB minimum of 1000

        with pytest.raises(OrderError) as exc_info:
            order_router.validate_order_constraints(sample_order, "IB")

        assert "below minimum size" in str(exc_info.value).lower()

    def test_handles_unsupported_order_type(self, order_router):
        """Test handling of unsupported order types."""
        trailing_stop_order = Order(
            order_id="ORDER_002",
            symbol="EUR/USD",
            order_type=OrderType.TRAILING_STOP,
            side=OrderSide.SELL,
            quantity=10000,
            stop_price=1.0950,
            trailing_amount=0.0020,
            client_id="CLIENT_001",
        )

        # FXCM doesn't support trailing stops
        with pytest.raises(OrderError) as exc_info:
            order_router.validate_order_constraints(trailing_stop_order, "FXCM")

        assert "unsupported order type" in str(exc_info.value).lower()

    def test_implements_failover_routing(self, order_router, sample_order):
        """Test failover to backup brokers when primary fails."""
        # Mock primary broker failure
        with patch.object(order_router, "_check_broker_health") as mock_health:
            mock_health.side_effect = (
                lambda broker: broker != "IB"
            )  # IB fails health check

            routing_decision = order_router.route_order(sample_order)

            # Should failover to FXCM
            assert routing_decision["selected_broker"] == "FXCM"
            assert routing_decision["reason"] == "failover"
            assert "IB" not in routing_decision["fallback_brokers"]

    def test_balances_load_across_brokers(self, order_router, sample_order):
        """Test load balancing to distribute orders."""
        order_router.config["routing_strategy"] = "load_balanced"

        # Track routing decisions over multiple orders
        routing_decisions = []
        for i in range(10):
            order = Order(
                order_id=f"ORDER_{i:03d}",
                symbol="EUR/USD",
                order_type=OrderType.MARKET,
                side=OrderSide.BUY,
                quantity=10000,
                client_id="CLIENT_001",
            )

            with patch.object(order_router, "_check_broker_health", return_value=True):
                decision = order_router.route_order(order)
                routing_decisions.append(decision["selected_broker"])

        # Should distribute across multiple brokers based on weights
        unique_brokers = set(routing_decisions)
        assert len(unique_brokers) >= 2  # At least 2 different brokers used

    def test_monitors_broker_health(self, order_router):
        """Test real-time broker health monitoring."""
        # Mock broker client responses
        mock_ib_client = MagicMock()
        mock_ib_client.ping.return_value = True
        mock_ib_client.get_connection_status.return_value = "connected"

        mock_fxcm_client = MagicMock()
        mock_fxcm_client.ping.return_value = False  # Unhealthy

        broker_clients = {"IB": mock_ib_client, "FXCM": mock_fxcm_client}

        with patch.object(order_router, "broker_clients", broker_clients):
            health_status = order_router.check_all_broker_health()

            assert health_status["IB"]["healthy"] is True
            assert health_status["FXCM"]["healthy"] is False
            assert "last_check" in health_status["IB"]

    @pytest.mark.asyncio
    async def test_measures_broker_latencies(self, order_router):
        """Test measurement of broker response latencies."""
        # Mock async broker ping methods
        mock_ib_client = AsyncMock()
        mock_ib_client.ping_async.return_value = True

        mock_fxcm_client = AsyncMock()
        mock_fxcm_client.ping_async.return_value = True

        broker_clients = {"IB": mock_ib_client, "FXCM": mock_fxcm_client}

        with patch.object(order_router, "broker_clients", broker_clients):
            latencies = await order_router.measure_broker_latencies()

            assert "IB" in latencies
            assert "FXCM" in latencies
            assert all(isinstance(lat, (int, float)) for lat in latencies.values())
            assert all(lat >= 0 for lat in latencies.values())

    def test_splits_large_orders(self, order_router):
        """Test order splitting for large quantities."""
        large_order = Order(
            order_id="ORDER_LARGE",
            symbol="EUR/USD",
            order_type=OrderType.MARKET,
            side=OrderSide.BUY,
            quantity=15000000,  # Exceeds IB max of 10M
            client_id="CLIENT_001",
        )

        split_orders = order_router.split_large_order(large_order, "IB")

        assert len(split_orders) == 2  # Should split into 2 orders
        assert split_orders[0].quantity == 10000000  # Max size
        assert split_orders[1].quantity == 5000000  # Remainder
        assert all(order.order_id.startswith("ORDER_LARGE_") for order in split_orders)

    def test_aggregates_small_orders(self, order_router):
        """Test order aggregation for efficiency."""
        small_orders = [
            Order(
                order_id=f"SMALL_{i}",
                symbol="EUR/USD",
                order_type=OrderType.MARKET,
                side=OrderSide.BUY,
                quantity=500,
                client_id="CLIENT_001",
            )
            for i in range(5)
        ]

        aggregated = order_router.aggregate_small_orders(small_orders, "OANDA")

        assert len(aggregated) == 1  # Aggregated into single order
        assert aggregated[0].quantity == 2500  # Total quantity
        assert aggregated[0].order_id.startswith("AGG_")

    def test_handles_market_hours(self, order_router, sample_order):
        """Test market hours validation for different brokers."""
        # Test during IB trading hours (9:30-16:00)
        with freeze_time("2025-01-15 10:30:00"):  # Wednesday 10:30 AM
            assert order_router.is_market_open("IB") is True
            assert order_router.can_route_order(sample_order, "IB") is True

        # Test outside IB trading hours
        with freeze_time("2025-01-15 08:00:00"):  # Wednesday 8:00 AM
            assert order_router.is_market_open("IB") is False

            with pytest.raises(OrderError) as exc_info:
                order_router.validate_trading_hours(sample_order, "IB")

            assert "outside trading hours" in str(exc_info.value).lower()

    def test_enforces_risk_limits(self, order_router, sample_order):
        """Test risk limit enforcement during routing."""
        # Test order size limit
        sample_order.quantity = 2000000  # Exceeds max_order_size of 1M

        with pytest.raises(RiskManagementError) as exc_info:
            order_router.validate_risk_limits(sample_order)

        assert "exceeds maximum order size" in str(exc_info.value).lower()

    def test_calculates_routing_scores(self, order_router, sample_order):
        """Test broker scoring for routing decisions."""
        broker_metrics = {
            "IB": {"latency": 1.5, "health_score": 0.98, "load": 0.3},
            "FXCM": {"latency": 2.2, "health_score": 0.95, "load": 0.6},
            "OANDA": {"latency": 3.1, "health_score": 0.92, "load": 0.2},
        }

        scores = order_router.calculate_routing_scores(sample_order, broker_metrics)

        # IB should have highest score (lowest latency, high health, low load)
        assert scores["IB"] > scores["FXCM"]
        assert scores["IB"] > scores["OANDA"]
        assert all(0 <= score <= 100 for score in scores.values())

    def test_handles_symbol_routing(self, order_router):
        """Test symbol-specific routing logic."""
        # Test symbol supported by specific broker
        usd_cad_order = Order(
            order_id="ORDER_CAD",
            symbol="USD/CAD",
            order_type=OrderType.MARKET,
            side=OrderSide.BUY,
            quantity=10000,
            client_id="CLIENT_001",
        )

        available_brokers = order_router.get_brokers_for_symbol("USD/CAD")

        # Only OANDA supports USD/CAD
        assert available_brokers == ["OANDA"]

        routing_decision = order_router.route_order(usd_cad_order)
        assert routing_decision["selected_broker"] == "OANDA"

    def test_implements_commission_optimization(self, order_router, sample_order):
        """Test routing optimization based on commission costs."""
        order_router.config["routing_strategy"] = "cost_optimized"

        # Mock all brokers as healthy with similar latencies
        with patch.object(
            order_router,
            "_get_broker_latencies",
            return_value={"IB": 2.0, "FXCM": 2.1, "OANDA": 2.2},
        ):
            with patch.object(order_router, "_check_broker_health", return_value=True):
                routing_decision = order_router.route_order(sample_order)

                # Should route to IB (lowest commission: 0.0002)
                assert routing_decision["selected_broker"] == "IB"
                assert routing_decision["reason"] == "cost_optimized"

    def test_tracks_order_routing_metrics(self, order_router, sample_order):
        """Test tracking of routing performance metrics."""
        # Route multiple orders
        for i in range(5):
            order = Order(
                order_id=f"METRIC_{i}",
                symbol="EUR/USD",
                order_type=OrderType.MARKET,
                side=OrderSide.BUY,
                quantity=10000,
                client_id="CLIENT_001",
            )

            with patch.object(order_router, "_check_broker_health", return_value=True):
                order_router.route_order(order)

        metrics = order_router.get_routing_metrics()

        assert metrics["total_orders"] == 5
        assert "broker_distribution" in metrics
        assert "average_routing_time" in metrics
        assert "success_rate" in metrics

    def test_handles_order_modifications(self, order_router, sample_order):
        """Test routing for order modifications."""
        # Original order routed to IB
        original_routing = {"selected_broker": "IB", "order_id": "ORDER_001"}

        # Modify order
        modified_order = Order(
            order_id="ORDER_001",
            symbol="EUR/USD",
            order_type=OrderType.LIMIT,
            side=OrderSide.BUY,
            quantity=15000,  # Changed quantity
            price=1.0500,  # Added limit price
            client_id="CLIENT_001",
        )

        # Should route modification to same broker
        routing_decision = order_router.route_order_modification(
            modified_order, original_routing
        )

        assert routing_decision["selected_broker"] == "IB"
        assert routing_decision["reason"] == "modification_same_broker"

    def test_handles_emergency_routing(self, order_router, sample_order):
        """Test emergency routing when all primary brokers fail."""
        sample_order.priority = "emergency"

        # Mock all preferred brokers as unhealthy except OANDA
        with patch.object(order_router, "_check_broker_health") as mock_health:
            mock_health.side_effect = lambda broker: broker == "OANDA"

            routing_decision = order_router.route_order(sample_order)

            assert routing_decision["selected_broker"] == "OANDA"
            assert routing_decision["reason"] == "emergency_routing"

    def test_validates_regulatory_compliance(self, order_router):
        """Test regulatory compliance checks during routing."""
        # Order that violates position limits
        large_eur_order = Order(
            order_id="ORDER_LARGE_EUR",
            symbol="EUR/USD",
            order_type=OrderType.MARKET,
            side=OrderSide.BUY,
            quantity=6000000,  # Exceeds EUR/USD position limit of 5M
            client_id="CLIENT_001",
        )

        with pytest.raises(RiskManagementError) as exc_info:
            order_router.validate_risk_limits(large_eur_order)

        assert "exceeds position limit" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_concurrent_order_routing(self, order_router):
        """Test handling of concurrent order routing requests."""
        orders = [
            Order(
                order_id=f"CONCURRENT_{i}",
                symbol="EUR/USD",
                order_type=OrderType.MARKET,
                side=OrderSide.BUY,
                quantity=10000,
                client_id="CLIENT_001",
            )
            for i in range(10)
        ]

        with patch.object(order_router, "_check_broker_health", return_value=True):
            # Route orders concurrently
            routing_tasks = [order_router.route_order_async(order) for order in orders]
            routing_results = await asyncio.gather(*routing_tasks)

            assert len(routing_results) == 10
            assert all("selected_broker" in result for result in routing_results)

    def test_handles_partial_fills(self, order_router, sample_order):
        """Test routing logic for partial fill scenarios."""
        # Simulate partial fill
        partial_fill_info = {
            "filled_quantity": 6000,
            "remaining_quantity": 4000,
            "original_broker": "IB",
        }

        remaining_order = order_router.create_remaining_order(
            sample_order, partial_fill_info
        )

        assert remaining_order.quantity == 4000
        assert remaining_order.order_id.endswith("_REMAINING")

        # Route remaining quantity
        routing_decision = order_router.route_remaining_order(remaining_order, "IB")

        # Should try same broker first for consistency
        assert routing_decision["selected_broker"] == "IB"
        assert routing_decision["reason"] == "partial_fill_continuation"
