"""
Unit tests for Order Manager.

Tests comprehensive order lifecycle management including:
- Order submission and validation
- State management and transitions
- Partial fills and execution tracking
- Order modifications and cancellations
- Multi-broker coordination
- Risk management integration
- Order persistence and recovery
- Performance monitoring
- Error handling and recovery
- Batch order processing
"""

import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from freezegun import freeze_time

from core.exceptions import BrokerError, OrderError, RiskError
from core.order_management.order_manager import OrderManager
from core.order_management.order_types import (
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
    TimeInForce,
)


class TestOrderManager:
    """Test suite for order lifecycle management."""

    @pytest.fixture
    def order_config(self):
        """Configuration for order manager."""
        return {
            "max_orders_per_symbol": 100,
            "max_total_orders": 1000,
            "order_timeout_seconds": 30,
            "partial_fill_timeout": 300,
            "batch_size": 50,
            "persistence_enabled": True,
            "risk_checks_enabled": True,
            "performance_monitoring": True,
            "auto_cancel_on_timeout": True,
            "max_retries": 3,
            "retry_delay_seconds": 1,
        }

    @pytest.fixture
    def mock_order_router(self):
        """Mock order router for testing."""
        router = MagicMock()
        router.route_order.return_value = {
            "selected_broker": "IB",
            "reason": "latency_optimized",
            "routing_score": 95.0,
        }
        return router

    @pytest.fixture
    def mock_risk_manager(self):
        """Mock risk manager for testing."""
        risk_mgr = MagicMock()
        risk_mgr.validate_order.return_value = True
        risk_mgr.check_position_limits.return_value = True
        return risk_mgr

    @pytest.fixture
    def mock_persistence(self):
        """Mock persistence layer for testing."""
        persistence = MagicMock()
        persistence.save_order.return_value = True
        persistence.load_orders.return_value = []
        return persistence

    @pytest.fixture
    def order_manager(
        self, order_config, mock_order_router, mock_risk_manager, mock_persistence
    ):
        """Create order manager for testing."""
        return OrderManager(
            config=order_config,
            order_router=mock_order_router,
            risk_manager=mock_risk_manager,
            persistence=mock_persistence,
        )

    @pytest.fixture
    def sample_order(self):
        """Sample order for testing."""
        return Order(
            order_id="ORDER_001",
            symbol="EUR/USD",
            order_type=OrderType.MARKET,
            side=OrderSide.BUY,
            quantity=100000,
            client_id="CLIENT_001",
            priority="normal",
        )

    def test_submits_order_successfully(
        self, order_manager, sample_order, mock_order_router
    ):
        """Test successful order submission and routing."""
        result = order_manager.submit_order(sample_order)

        assert result["status"] == "submitted"
        assert result["order_id"] == sample_order.order_id
        assert "routing_decision" in result

        # Verify order was routed
        mock_order_router.route_order.assert_called_once_with(sample_order)

        # Verify order is tracked
        assert sample_order.order_id in order_manager.active_orders

    def test_validates_order_before_submission(self, order_manager, mock_risk_manager):
        """Test order validation before submission."""
        # Create invalid order (zero quantity)
        invalid_order = Order(
            order_id="INVALID_001",
            symbol="EUR/USD",
            order_type=OrderType.MARKET,
            side=OrderSide.BUY,
            quantity=0,  # Invalid quantity
            client_id="CLIENT_001",
        )

        with pytest.raises(OrderError) as exc_info:
            order_manager.submit_order(invalid_order)

        assert "invalid quantity" in str(exc_info.value).lower()

        # Verify risk manager was called for validation
        mock_risk_manager.validate_order.assert_called_once()

    def test_handles_order_state_transitions(self, order_manager, sample_order):
        """Test proper order state transitions during lifecycle."""
        # Submit order
        order_manager.submit_order(sample_order)
        assert sample_order.status == OrderStatus.SUBMITTED

        # Acknowledge order
        order_manager.acknowledge_order(sample_order.order_id, broker="IB")
        tracked_order = order_manager.get_order(sample_order.order_id)
        assert tracked_order.status == OrderStatus.ACKNOWLEDGED

        # Partial fill
        order_manager.process_fill(
            sample_order.order_id, filled_quantity=50000, fill_price=Decimal("1.0525")
        )
        assert tracked_order.status == OrderStatus.PARTIALLY_FILLED
        assert tracked_order.filled_quantity == 50000

        # Complete fill
        order_manager.process_fill(
            sample_order.order_id, filled_quantity=50000, fill_price=Decimal("1.0530")
        )
        assert tracked_order.status == OrderStatus.FILLED
        assert tracked_order.filled_quantity == 100000

    def test_manages_partial_fills(self, order_manager, sample_order):
        """Test management of partial fills and remaining quantities."""
        order_manager.submit_order(sample_order)

        # First partial fill
        order_manager.process_fill(
            sample_order.order_id, filled_quantity=30000, fill_price=Decimal("1.0520")
        )

        tracked_order = order_manager.get_order(sample_order.order_id)
        assert tracked_order.filled_quantity == 30000
        assert tracked_order.remaining_quantity == 70000
        assert tracked_order.status == OrderStatus.PARTIALLY_FILLED

        # Second partial fill
        order_manager.process_fill(
            sample_order.order_id, filled_quantity=25000, fill_price=Decimal("1.0525")
        )

        assert tracked_order.filled_quantity == 55000
        assert tracked_order.remaining_quantity == 45000

        # Calculate average fill price
        expected_avg = (30000 * Decimal("1.0520") + 25000 * Decimal("1.0525")) / 55000
        assert abs(tracked_order.average_fill_price - expected_avg) < Decimal("0.0001")

    def test_handles_order_cancellation(self, order_manager, sample_order):
        """Test order cancellation and cleanup."""
        order_manager.submit_order(sample_order)

        # Cancel order
        result = order_manager.cancel_order(
            sample_order.order_id, reason="user_requested"
        )

        assert result["status"] == "cancelled"
        tracked_order = order_manager.get_order(sample_order.order_id)
        assert tracked_order.status == OrderStatus.CANCELLED

        # Verify order moved to historical records
        assert sample_order.order_id not in order_manager.active_orders
        assert sample_order.order_id in order_manager.historical_orders

    def test_modifies_order_attributes(self, order_manager, sample_order):
        """Test order modification capabilities."""
        # Submit limit order
        limit_order = Order(
            order_id="LIMIT_001",
            symbol="GBP/USD",
            order_type=OrderType.LIMIT,
            side=OrderSide.SELL,
            quantity=150000,
            price=Decimal("1.2850"),
            client_id="CLIENT_001",
        )

        order_manager.submit_order(limit_order)

        # Modify price and quantity
        modifications = {"price": Decimal("1.2860"), "quantity": 200000}

        result = order_manager.modify_order(limit_order.order_id, modifications)

        assert result["status"] == "modified"
        tracked_order = order_manager.get_order(limit_order.order_id)
        assert tracked_order.price == Decimal("1.2860")
        assert tracked_order.quantity == 200000

    def test_enforces_order_limits(self, order_manager, order_config):
        """Test enforcement of order quantity and count limits."""
        # Test max orders per symbol limit
        for i in range(order_config["max_orders_per_symbol"] + 1):
            order = Order(
                order_id=f"EUR_ORDER_{i:03d}",
                symbol="EUR/USD",
                order_type=OrderType.MARKET,
                side=OrderSide.BUY,
                quantity=10000,
                client_id="CLIENT_001",
            )

            if i < order_config["max_orders_per_symbol"]:
                order_manager.submit_order(order)
            else:
                with pytest.raises(OrderError) as exc_info:
                    order_manager.submit_order(order)
                assert (
                    "maximum orders per symbol exceeded" in str(exc_info.value).lower()
                )

    def test_processes_batch_orders(self, order_manager):
        """Test batch order processing capabilities."""
        # Create batch of orders
        batch_orders = []
        for i in range(10):
            order = Order(
                order_id=f"BATCH_{i:03d}",
                symbol=f"EUR/USD" if i % 2 == 0 else "GBP/USD",
                order_type=OrderType.MARKET,
                side=OrderSide.BUY if i % 2 == 0 else OrderSide.SELL,
                quantity=50000,
                client_id="CLIENT_001",
            )
            batch_orders.append(order)

        # Submit batch
        results = order_manager.submit_batch_orders(batch_orders)

        assert len(results) == 10
        assert all(result["status"] == "submitted" for result in results)

        # Verify all orders are tracked
        for order in batch_orders:
            assert order.order_id in order_manager.active_orders

    def test_handles_order_timeout(self, order_manager, sample_order):
        """Test automatic order timeout and cancellation."""
        with freeze_time("2025-01-01 12:00:00") as frozen_time:
            order_manager.submit_order(sample_order)

            # Advance time beyond timeout
            frozen_time.tick(delta=timedelta(seconds=35))

            # Process timeouts
            order_manager.process_timeouts()

            tracked_order = order_manager.get_order(sample_order.order_id)
            assert tracked_order.status == OrderStatus.EXPIRED

    def test_recovers_orders_from_persistence(self, order_manager, mock_persistence):
        """Test order recovery from persistent storage."""
        # Mock persisted orders
        persisted_orders = [
            {
                "order_id": "PERSIST_001",
                "symbol": "EUR/USD",
                "status": "partially_filled",
                "filled_quantity": 25000,
                "quantity": 100000,
            }
        ]
        mock_persistence.load_orders.return_value = persisted_orders

        # Initialize recovery
        recovered_count = order_manager.recover_orders()

        assert recovered_count == 1
        mock_persistence.load_orders.assert_called_once()

    def test_tracks_performance_metrics(self, order_manager, sample_order):
        """Test performance metrics tracking."""
        # Submit and fill order
        order_manager.submit_order(sample_order)
        order_manager.acknowledge_order(sample_order.order_id, broker="IB")
        order_manager.process_fill(
            sample_order.order_id, filled_quantity=100000, fill_price=Decimal("1.0525")
        )

        metrics = order_manager.get_performance_metrics()

        assert metrics["total_orders"] >= 1
        assert metrics["filled_orders"] >= 1
        assert "average_fill_time" in metrics
        assert "fill_rate" in metrics
        assert metrics["fill_rate"] <= 1.0

    def test_handles_broker_failures(
        self, order_manager, sample_order, mock_order_router
    ):
        """Test handling of broker failures during order submission."""
        # Mock router failure
        mock_order_router.route_order.side_effect = BrokerError(
            "All brokers unavailable"
        )

        with pytest.raises(BrokerError):
            order_manager.submit_order(sample_order)

        # Verify order is not tracked after failure
        assert sample_order.order_id not in order_manager.active_orders

    def test_implements_retry_logic(
        self, order_manager, sample_order, mock_order_router
    ):
        """Test retry logic for failed order submissions."""
        # Mock intermittent failures
        mock_order_router.route_order.side_effect = [
            BrokerError("Temporary failure"),
            BrokerError("Temporary failure"),
            {
                "selected_broker": "IB",
                "reason": "latency_optimized",
            },  # Success on 3rd attempt
        ]

        result = order_manager.submit_order(sample_order)

        assert result["status"] == "submitted"
        assert mock_order_router.route_order.call_count == 3

    def test_handles_concurrent_operations(self, order_manager):
        """Test thread-safe concurrent order operations."""
        import threading
        import time

        results = []
        errors = []

        def submit_order_worker(order_id: str):
            try:
                order = Order(
                    order_id=order_id,
                    symbol="EUR/USD",
                    order_type=OrderType.MARKET,
                    side=OrderSide.BUY,
                    quantity=10000,
                    client_id=f"CLIENT_{threading.current_thread().ident}",
                )
                result = order_manager.submit_order(order)
                results.append(result)
                time.sleep(0.01)  # Small delay to increase race condition chance
            except Exception as e:
                errors.append(e)

        # Run concurrent submissions
        threads = []
        for i in range(20):
            thread = threading.Thread(
                target=submit_order_worker, args=[f"CONCURRENT_{i:03d}"]
            )
            threads.append(thread)
            thread.start()

        # Wait for completion
        for thread in threads:
            thread.join()

        # Verify results
        assert len(errors) == 0
        assert len(results) == 20
        assert len(order_manager.active_orders) == 20

    def test_validates_modification_constraints(self, order_manager):
        """Test validation of order modification constraints."""
        # Submit order
        limit_order = Order(
            order_id="MOD_TEST_001",
            symbol="USD/JPY",
            order_type=OrderType.LIMIT,
            side=OrderSide.BUY,
            quantity=100000,
            price=Decimal("145.50"),
            client_id="CLIENT_001",
        )

        order_manager.submit_order(limit_order)
        order_manager.acknowledge_order(limit_order.order_id, broker="IB")

        # Try to modify to invalid price (negative)
        invalid_modifications = {"price": Decimal("-1.0")}

        with pytest.raises(OrderError) as exc_info:
            order_manager.modify_order(limit_order.order_id, invalid_modifications)

        assert "invalid price" in str(exc_info.value).lower()

    def test_handles_duplicate_order_ids(self, order_manager, sample_order):
        """Test handling of duplicate order ID submissions."""
        # Submit first order
        order_manager.submit_order(sample_order)

        # Try to submit duplicate order ID
        duplicate_order = Order(
            order_id=sample_order.order_id,  # Same ID
            symbol="GBP/USD",
            order_type=OrderType.LIMIT,
            side=OrderSide.SELL,
            quantity=75000,
            price=Decimal("1.2800"),
            client_id="CLIENT_002",
        )

        with pytest.raises(OrderError) as exc_info:
            order_manager.submit_order(duplicate_order)

        assert "duplicate order id" in str(exc_info.value).lower()

    def test_calculates_order_statistics(self, order_manager):
        """Test calculation of order statistics and analytics."""
        # Submit various orders with different outcomes
        orders_data = [
            ("ORDER_1", OrderStatus.FILLED, 100000, Decimal("1.0500")),
            ("ORDER_2", OrderStatus.PARTIALLY_FILLED, 50000, Decimal("1.0505")),
            ("ORDER_3", OrderStatus.CANCELLED, 0, None),
            ("ORDER_4", OrderStatus.FILLED, 150000, Decimal("1.0510")),
        ]

        for order_id, final_status, filled_qty, fill_price in orders_data:
            order = Order(
                order_id=order_id,
                symbol="EUR/USD",
                order_type=OrderType.MARKET,
                side=OrderSide.BUY,
                quantity=100000 if filled_qty == 0 else max(filled_qty, 100000),
                client_id="CLIENT_001",
            )

            order_manager.submit_order(order)
            if final_status != OrderStatus.CANCELLED:
                order_manager.acknowledge_order(order_id, broker="IB")
                if filled_qty > 0:
                    order_manager.process_fill(order_id, filled_qty, fill_price)
            else:
                order_manager.cancel_order(order_id)

        stats = order_manager.calculate_order_statistics()

        assert stats["total_orders"] == 4
        assert stats["filled_orders"] == 2
        assert stats["partially_filled_orders"] == 1
        assert stats["cancelled_orders"] == 1
        assert "total_volume_traded" in stats
        assert "average_fill_price" in stats

    def test_manages_order_expiration(self, order_manager):
        """Test management of order expiration based on time-in-force."""
        # Create GTD (Good Till Date) order
        gtd_order = Order(
            order_id="GTD_001",
            symbol="EUR/USD",
            order_type=OrderType.LIMIT,
            side=OrderSide.BUY,
            quantity=100000,
            price=Decimal("1.0500"),
            time_in_force="GTD",
            client_id="CLIENT_001",
        )

        with freeze_time("2025-01-01 12:00:00") as frozen_time:
            order_manager.submit_order(gtd_order)

            # Set expiration time
            order_manager.set_order_expiration(
                gtd_order.order_id, datetime.utcnow() + timedelta(hours=1)
            )

            # Advance time past expiration
            frozen_time.tick(delta=timedelta(hours=2))

            # Process expirations
            expired_orders = order_manager.process_expirations()

            assert gtd_order.order_id in expired_orders
            tracked_order = order_manager.get_order(gtd_order.order_id)
            assert tracked_order.status == OrderStatus.EXPIRED

    def test_handles_order_rejection(
        self, order_manager, sample_order, mock_order_router
    ):
        """Test handling of order rejection by broker."""
        # Mock broker rejection
        mock_order_router.route_order.return_value = {
            "status": "rejected",
            "reason": "insufficient_margin",
            "selected_broker": "IB",
        }

        with pytest.raises(OrderError) as exc_info:
            order_manager.submit_order(sample_order)

        assert "rejected" in str(exc_info.value).lower()
        assert sample_order.order_id not in order_manager.active_orders

    def test_persists_order_changes(
        self, order_manager, sample_order, mock_persistence
    ):
        """Test persistence of order state changes."""
        order_manager.submit_order(sample_order)
        order_manager.acknowledge_order(sample_order.order_id, broker="IB")
        order_manager.process_fill(
            sample_order.order_id, filled_quantity=100000, fill_price=Decimal("1.0525")
        )

        # Verify persistence calls were made
        assert mock_persistence.save_order.call_count >= 3  # Submit, ack, fill

    def test_generates_order_reports(self, order_manager):
        """Test generation of comprehensive order reports."""
        # Create and process several orders
        test_orders = [
            ("RPT_001", "EUR/USD", OrderSide.BUY, 100000),
            ("RPT_002", "GBP/USD", OrderSide.SELL, 150000),
            ("RPT_003", "USD/JPY", OrderSide.BUY, 200000),
        ]

        for order_id, symbol, side, quantity in test_orders:
            order = Order(
                order_id=order_id,
                symbol=symbol,
                order_type=OrderType.MARKET,
                side=side,
                quantity=quantity,
                client_id="CLIENT_001",
            )
            order_manager.submit_order(order)
            order_manager.acknowledge_order(order_id, broker="IB")
            order_manager.process_fill(order_id, quantity, Decimal("1.0500"))

        report = order_manager.generate_order_report(
            start_time=datetime.utcnow() - timedelta(hours=1),
            end_time=datetime.utcnow(),
        )

        assert "summary" in report
        assert "orders_by_symbol" in report
        assert "orders_by_status" in report
        assert "performance_metrics" in report
        assert len(report["orders_by_symbol"]) >= 3
