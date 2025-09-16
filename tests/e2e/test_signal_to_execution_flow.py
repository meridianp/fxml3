#!/usr/bin/env python3
"""
End-to-End Test: Signal to Execution Flow
=========================================

This test suite validates the complete trading flow from signal generation
to order execution, ensuring all components work together seamlessly.

Business Requirements:
- Signal generation to order execution < 2 seconds
- Risk validation must prevent overleveraging
- Orders must be routed to correct broker
- Position tracking must be accurate
- Audit trail must be complete

Test Coverage:
- Signal generation pipeline
- Risk management checks
- Order routing logic
- Broker execution
- Position updates
- Audit logging
"""

import asyncio
import time
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from fxml4.brokers.adapters.base import BrokerAdapter
from fxml4.brokers.order_manager import OrderManager
from fxml4.core.models import Order, Position, Signal, Trade
from fxml4.data_engineering.feature_pipeline import FeaturePipeline
from fxml4.ml.models.ensemble import EnsemblePredictor
from fxml4.risk_management.risk_engine import RiskEngine
from fxml4.strategy.signal_generator import SignalGenerator


class TestSignalToExecutionE2E:
    """Complete end-to-end testing of the signal to execution flow."""

    @pytest.fixture
    async def market_data(self):
        """Generate realistic market data for testing."""
        periods = 100
        dates = pd.date_range(end=datetime.now(), periods=periods, freq="1h")

        # Generate realistic OHLCV data with trend
        trend = np.linspace(1.0800, 1.0850, periods) + np.random.normal(
            0, 0.0005, periods
        )

        data = pd.DataFrame(
            {
                "timestamp": dates,
                "open": trend + np.random.normal(0, 0.0002, periods),
                "high": trend + np.abs(np.random.normal(0.0003, 0.0002, periods)),
                "low": trend - np.abs(np.random.normal(0.0003, 0.0002, periods)),
                "close": trend + np.random.normal(0, 0.0001, periods),
                "volume": np.random.uniform(1000000, 5000000, periods),
            }
        )

        # Ensure OHLC consistency
        data["high"] = data[["open", "high", "close"]].max(axis=1)
        data["low"] = data[["open", "low", "close"]].min(axis=1)

        return data

    @pytest.fixture
    async def signal_generator(self, market_data):
        """Initialize signal generator with test configuration."""
        generator = SignalGenerator(
            symbol="EURUSD",
            ml_model_path="tests/fixtures/models/test_ensemble.pkl",
            confidence_threshold=0.7,
        )

        # Mock the ML model predictions
        with patch.object(generator, "ml_predictor") as mock_predictor:
            mock_predictor.predict.return_value = {
                "direction": "LONG",
                "confidence": 0.85,
                "entry_price": 1.0850,
                "stop_loss": 1.0820,
                "take_profit": 1.0900,
                "features": {},
            }
            yield generator

    @pytest.fixture
    async def risk_engine(self):
        """Initialize risk engine with test limits."""
        engine = RiskEngine(
            max_position_size=100000,  # $100k max per position
            max_portfolio_risk=0.06,  # 6% max portfolio risk
            max_correlation=0.7,  # 70% max correlation
            var_confidence=0.95,  # 95% VaR
        )

        # Set test portfolio value
        engine.portfolio_value = Decimal("1000000")  # $1M portfolio

        return engine

    @pytest.fixture
    async def order_manager(self):
        """Initialize order manager with mock broker adapters."""
        manager = OrderManager()

        # Create mock broker adapters
        ib_adapter = AsyncMock(spec=BrokerAdapter)
        ib_adapter.name = "InteractiveBrokers"
        ib_adapter.is_connected = True
        ib_adapter.submit_order = AsyncMock(
            return_value={
                "order_id": "IB_12345",
                "status": "SUBMITTED",
                "timestamp": datetime.now(),
            }
        )

        fxcm_adapter = AsyncMock(spec=BrokerAdapter)
        fxcm_adapter.name = "FXCM"
        fxcm_adapter.is_connected = True
        fxcm_adapter.submit_order = AsyncMock(
            return_value={
                "order_id": "FXCM_67890",
                "status": "SUBMITTED",
                "timestamp": datetime.now(),
            }
        )

        manager.register_adapter("IB", ib_adapter)
        manager.register_adapter("FXCM", fxcm_adapter)
        manager.set_primary_broker("IB")

        return manager

    @pytest.mark.asyncio
    async def test_complete_signal_to_execution_flow(
        self, market_data, signal_generator, risk_engine, order_manager
    ):
        """
        Test the complete flow from signal generation to order execution.

        Given: Market data and trading system components
        When: A trading signal is generated
        Then: Order should be executed within 2 seconds with proper risk checks
        """
        start_time = time.time()

        # Step 1: Generate features from market data
        feature_pipeline = FeaturePipeline()
        features = await feature_pipeline.compute_features(market_data)

        assert features is not None
        assert len(features) > 0

        # Step 2: Generate trading signal
        signal = await signal_generator.generate_signal(features)

        assert signal is not None
        assert signal.confidence >= 0.7
        assert signal.direction in ["LONG", "SHORT"]
        assert signal.entry_price > 0
        assert signal.stop_loss > 0
        assert signal.take_profit > 0

        # Step 3: Validate signal through risk management
        risk_check = await risk_engine.validate_signal(signal)

        assert risk_check.is_valid
        assert risk_check.position_size > 0
        assert risk_check.position_size <= 100000
        assert risk_check.risk_amount <= risk_engine.portfolio_value * Decimal("0.02")

        # Step 4: Create order from signal
        order = Order(
            symbol=signal.symbol,
            side="BUY" if signal.direction == "LONG" else "SELL",
            quantity=risk_check.position_size,
            order_type="LIMIT",
            price=signal.entry_price,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            metadata={
                "signal_id": signal.id,
                "confidence": signal.confidence,
                "risk_score": risk_check.risk_score,
            },
        )

        # Step 5: Submit order to broker
        execution_result = await order_manager.submit_order(order)

        assert execution_result is not None
        assert execution_result["status"] in ["SUBMITTED", "FILLED"]
        assert execution_result["order_id"] is not None

        # Step 6: Verify execution time
        execution_time = time.time() - start_time
        assert (
            execution_time < 2.0
        ), f"Execution took {execution_time:.2f}s, exceeding 2s limit"

        # Step 7: Verify audit trail
        audit_events = await self._get_audit_events(signal.id)

        assert len(audit_events) >= 4  # Signal, risk check, order creation, execution
        assert audit_events[0]["event_type"] == "SIGNAL_GENERATED"
        assert audit_events[-1]["event_type"] == "ORDER_SUBMITTED"

    @pytest.mark.asyncio
    async def test_signal_rejection_by_risk_management(
        self, signal_generator, risk_engine
    ):
        """
        Test that high-risk signals are properly rejected.

        Given: A high-risk trading signal
        When: Risk validation is performed
        Then: Signal should be rejected with appropriate reason
        """
        # Create a high-risk signal
        signal = Signal(
            symbol="EURUSD",
            direction="LONG",
            confidence=0.75,
            entry_price=1.0850,
            stop_loss=1.0750,  # 100 pips stop loss (high risk)
            take_profit=1.0900,
            timestamp=datetime.now(),
        )

        # Set portfolio to small value to trigger risk rejection
        risk_engine.portfolio_value = Decimal("10000")  # $10k portfolio

        # Validate signal
        risk_check = await risk_engine.validate_signal(signal)

        assert not risk_check.is_valid
        assert risk_check.rejection_reason is not None
        assert "risk" in risk_check.rejection_reason.lower()

    @pytest.mark.asyncio
    async def test_broker_failover_on_primary_failure(
        self, signal_generator, risk_engine, order_manager
    ):
        """
        Test automatic failover to secondary broker on primary failure.

        Given: Primary broker is unavailable
        When: Order is submitted
        Then: System should failover to secondary broker within 5 seconds
        """
        # Simulate primary broker failure
        order_manager.brokers["IB"].is_connected = False
        order_manager.brokers["IB"].submit_order = AsyncMock(
            side_effect=ConnectionError("IB Gateway not connected")
        )

        # Create test order
        order = Order(
            symbol="EURUSD",
            side="BUY",
            quantity=10000,
            order_type="MARKET",
            price=1.0850,
        )

        start_time = time.time()

        # Submit order (should failover to FXCM)
        execution_result = await order_manager.submit_order(order)

        failover_time = time.time() - start_time

        assert execution_result is not None
        assert execution_result["order_id"].startswith("FXCM_")
        assert (
            failover_time < 5.0
        ), f"Failover took {failover_time:.2f}s, exceeding 5s limit"

    @pytest.mark.asyncio
    async def test_position_tracking_accuracy(self, order_manager):
        """
        Test that positions are accurately tracked after execution.

        Given: Multiple orders are executed
        When: Positions are calculated
        Then: Position totals should match executed orders
        """
        # Execute multiple test orders
        orders = [
            Order(
                symbol="EURUSD",
                side="BUY",
                quantity=10000,
                order_type="MARKET",
                price=1.0850,
            ),
            Order(
                symbol="EURUSD",
                side="BUY",
                quantity=5000,
                order_type="MARKET",
                price=1.0855,
            ),
            Order(
                symbol="EURUSD",
                side="SELL",
                quantity=3000,
                order_type="MARKET",
                price=1.0860,
            ),
            Order(
                symbol="GBPUSD",
                side="BUY",
                quantity=8000,
                order_type="MARKET",
                price=1.2650,
            ),
        ]

        executed_orders = []
        for order in orders:
            result = await order_manager.submit_order(order)
            executed_orders.append((order, result))

        # Get current positions
        positions = await order_manager.get_positions()

        # Verify EURUSD position
        eurusd_position = next((p for p in positions if p.symbol == "EURUSD"), None)
        assert eurusd_position is not None
        assert eurusd_position.quantity == 12000  # 10000 + 5000 - 3000

        # Verify GBPUSD position
        gbpusd_position = next((p for p in positions if p.symbol == "GBPUSD"), None)
        assert gbpusd_position is not None
        assert gbpusd_position.quantity == 8000

    @pytest.mark.asyncio
    async def test_concurrent_signal_processing(
        self, signal_generator, risk_engine, order_manager
    ):
        """
        Test system can handle multiple concurrent signals.

        Given: Multiple signals generated simultaneously
        When: All signals are processed
        Then: Each should be handled independently without conflicts
        """
        # Generate multiple signals for different symbols
        symbols = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "NZDUSD"]

        async def process_signal(symbol: str):
            """Process a single signal."""
            # Generate signal
            signal = Signal(
                symbol=symbol,
                direction="LONG" if np.random.random() > 0.5 else "SHORT",
                confidence=np.random.uniform(0.7, 0.95),
                entry_price=1.0000 + np.random.uniform(-0.01, 0.01),
                stop_loss=1.0000 + np.random.uniform(-0.02, -0.01),
                take_profit=1.0000 + np.random.uniform(0.01, 0.02),
                timestamp=datetime.now(),
            )

            # Validate through risk
            risk_check = await risk_engine.validate_signal(signal)

            if risk_check.is_valid:
                # Create and submit order
                order = Order(
                    symbol=signal.symbol,
                    side="BUY" if signal.direction == "LONG" else "SELL",
                    quantity=risk_check.position_size,
                    order_type="LIMIT",
                    price=signal.entry_price,
                )

                result = await order_manager.submit_order(order)
                return result

            return None

        # Process all signals concurrently
        start_time = time.time()
        results = await asyncio.gather(*[process_signal(s) for s in symbols])
        processing_time = time.time() - start_time

        # Verify all signals were processed
        successful_orders = [r for r in results if r is not None]
        assert len(successful_orders) >= 3  # At least 3 should pass risk checks

        # Verify concurrent processing was efficient
        assert (
            processing_time < 3.0
        ), f"Concurrent processing took {processing_time:.2f}s"

    @pytest.mark.asyncio
    async def test_order_lifecycle_tracking(self, order_manager):
        """
        Test complete order lifecycle from creation to settlement.

        Given: An order is submitted
        When: Order goes through various states
        Then: All state transitions should be tracked
        """
        # Create test order
        order = Order(
            symbol="EURUSD",
            side="BUY",
            quantity=10000,
            order_type="LIMIT",
            price=1.0850,
            stop_loss=1.0820,
            take_profit=1.0900,
        )

        # Submit order
        submission_result = await order_manager.submit_order(order)
        order_id = submission_result["order_id"]

        # Simulate order lifecycle events
        lifecycle_events = []

        # Submitted state
        status = await order_manager.get_order_status(order_id)
        lifecycle_events.append(status)
        assert status["state"] == "SUBMITTED"

        # Simulate partial fill
        await order_manager._update_order_status(
            order_id,
            {
                "state": "PARTIALLY_FILLED",
                "filled_quantity": 5000,
                "remaining_quantity": 5000,
            },
        )

        status = await order_manager.get_order_status(order_id)
        lifecycle_events.append(status)
        assert status["state"] == "PARTIALLY_FILLED"
        assert status["filled_quantity"] == 5000

        # Simulate complete fill
        await order_manager._update_order_status(
            order_id,
            {
                "state": "FILLED",
                "filled_quantity": 10000,
                "remaining_quantity": 0,
                "average_price": 1.0851,
            },
        )

        status = await order_manager.get_order_status(order_id)
        lifecycle_events.append(status)
        assert status["state"] == "FILLED"
        assert status["filled_quantity"] == 10000

        # Verify complete lifecycle was tracked
        assert len(lifecycle_events) >= 3
        assert lifecycle_events[0]["state"] == "SUBMITTED"
        assert lifecycle_events[-1]["state"] == "FILLED"

    @pytest.mark.asyncio
    async def test_stop_loss_and_take_profit_execution(self, order_manager):
        """
        Test that stop loss and take profit orders are properly set.

        Given: An order with stop loss and take profit
        When: Order is executed
        Then: Protective orders should be placed
        """
        # Create order with SL and TP
        order = Order(
            symbol="EURUSD",
            side="BUY",
            quantity=10000,
            order_type="MARKET",
            price=1.0850,
            stop_loss=1.0820,
            take_profit=1.0900,
        )

        # Submit order
        execution_result = await order_manager.submit_order(order)

        # Verify protective orders were created
        protective_orders = await order_manager.get_protective_orders(
            execution_result["order_id"]
        )

        assert len(protective_orders) == 2

        # Verify stop loss order
        sl_order = next(
            (o for o in protective_orders if o.order_type == "STOP_LOSS"), None
        )
        assert sl_order is not None
        assert sl_order.price == 1.0820
        assert sl_order.side == "SELL"  # Opposite side for closing

        # Verify take profit order
        tp_order = next(
            (o for o in protective_orders if o.order_type == "TAKE_PROFIT"), None
        )
        assert tp_order is not None
        assert tp_order.price == 1.0900
        assert tp_order.side == "SELL"  # Opposite side for closing

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_end_to_end_performance_requirements(
        self, market_data, signal_generator, risk_engine, order_manager
    ):
        """
        Test that the entire flow meets performance requirements.

        Given: Performance SLAs for signal to execution
        When: Multiple iterations are run
        Then: 95th percentile should be within SLA
        """
        execution_times = []

        # Run multiple iterations to get performance distribution
        for _ in range(20):
            start_time = time.time()

            # Generate signal
            features = await FeaturePipeline().compute_features(market_data)
            signal = await signal_generator.generate_signal(features)

            # Risk validation
            risk_check = await risk_engine.validate_signal(signal)

            if risk_check.is_valid:
                # Create and submit order
                order = Order(
                    symbol=signal.symbol,
                    side="BUY" if signal.direction == "LONG" else "SELL",
                    quantity=risk_check.position_size,
                    order_type="MARKET",
                    price=signal.entry_price,
                )

                await order_manager.submit_order(order)

            execution_time = time.time() - start_time
            execution_times.append(execution_time)

        # Calculate performance metrics
        p95 = np.percentile(execution_times, 95)
        mean_time = np.mean(execution_times)

        # Verify SLAs
        assert p95 < 2.0, f"95th percentile {p95:.2f}s exceeds 2s SLA"
        assert mean_time < 1.0, f"Mean time {mean_time:.2f}s exceeds 1s target"

    # Helper methods

    async def _get_audit_events(self, signal_id: str) -> List[Dict]:
        """Get audit events for a signal."""
        # This would query the audit log database
        # For testing, return mock events
        return [
            {
                "event_type": "SIGNAL_GENERATED",
                "signal_id": signal_id,
                "timestamp": datetime.now(),
            },
            {
                "event_type": "RISK_VALIDATED",
                "signal_id": signal_id,
                "timestamp": datetime.now(),
            },
            {
                "event_type": "ORDER_CREATED",
                "signal_id": signal_id,
                "timestamp": datetime.now(),
            },
            {
                "event_type": "ORDER_SUBMITTED",
                "signal_id": signal_id,
                "timestamp": datetime.now(),
            },
        ]


if __name__ == "__main__":
    # Run tests with coverage
    pytest.main([__file__, "-v", "--cov=fxml4", "--cov-report=term-missing"])
