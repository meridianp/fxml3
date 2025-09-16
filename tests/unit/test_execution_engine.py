"""
Unit tests for Execution Engine.

Tests comprehensive trade execution functionality including:
- Real-time order execution
- Multi-broker communication
- Fill processing and reconciliation
- Execution quality monitoring
- Slippage tracking
- Market impact analysis
- Smart order routing
- Execution algorithms (TWAP, VWAP, etc.)
- Liquidity sourcing
- Pre-trade and post-trade analysis
"""

import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest
from freezegun import freeze_time

from core.exceptions import BrokerError, ExecutionError, OrderError
from core.order_management.order_types import Order, OrderSide, OrderStatus, OrderType
from core.trading.execution_engine import ExecutionEngine


class TestExecutionEngine:
    """Test suite for trade execution engine."""

    @pytest.fixture
    def execution_config(self):
        """Configuration for execution engine."""
        return {
            "max_slippage_bps": 10,  # basis points
            "max_market_impact_bps": 5,
            "execution_timeout_seconds": 5,
            "smart_routing_enabled": True,
            "liquidity_aggregation": True,
            "execution_algorithms": ["TWAP", "VWAP", "POV", "ICEBERG"],
            "pre_trade_checks": True,
            "post_trade_analysis": True,
            "fill_reconciliation_interval": 1,
            "max_execution_retries": 3,
            "partial_fill_timeout": 30,
        }

    @pytest.fixture
    def mock_broker_connections(self):
        """Mock broker connections for testing."""
        connections = {"IB": MagicMock(), "FXCM": MagicMock(), "OANDA": MagicMock()}
        for broker, conn in connections.items():
            conn.execute_order = AsyncMock(
                return_value={
                    "status": "executed",
                    "fill_price": Decimal("1.0525"),
                    "fill_quantity": 100000,
                }
            )
        return connections

    @pytest.fixture
    def mock_market_data(self):
        """Mock market data provider."""
        market_data = MagicMock()
        market_data.get_bid_ask.return_value = {
            "bid": Decimal("1.0520"),
            "ask": Decimal("1.0522"),
            "bid_size": 1000000,
            "ask_size": 1000000,
        }
        market_data.get_market_depth.return_value = {
            "bids": [(Decimal("1.0520"), 500000), (Decimal("1.0519"), 300000)],
            "asks": [(Decimal("1.0522"), 500000), (Decimal("1.0523"), 300000)],
        }
        return market_data

    @pytest.fixture
    def mock_order_manager(self):
        """Mock order manager for testing."""
        order_mgr = MagicMock()
        order_mgr.get_order.return_value = Order(
            order_id="ORDER_001",
            symbol="EUR/USD",
            order_type=OrderType.MARKET,
            side=OrderSide.BUY,
            quantity=100000,
            client_id="CLIENT_001",
        )
        return order_mgr

    @pytest.fixture
    def execution_engine(
        self,
        execution_config,
        mock_broker_connections,
        mock_market_data,
        mock_order_manager,
    ):
        """Create execution engine for testing."""
        return ExecutionEngine(
            config=execution_config,
            broker_connections=mock_broker_connections,
            market_data=mock_market_data,
            order_manager=mock_order_manager,
        )

    @pytest.fixture
    def sample_order(self):
        """Sample order for execution testing."""
        return Order(
            order_id="EXEC_001",
            symbol="EUR/USD",
            order_type=OrderType.MARKET,
            side=OrderSide.BUY,
            quantity=100000,
            client_id="CLIENT_001",
            routed_broker="IB",
        )

    @pytest.mark.asyncio
    async def test_executes_market_order(self, execution_engine, sample_order):
        """Test execution of market order."""
        result = await execution_engine.execute_order(sample_order)

        assert result["status"] == "executed"
        assert "execution_id" in result
        assert "fill_price" in result
        assert "fill_quantity" in result
        assert result["fill_quantity"] == sample_order.quantity

    @pytest.mark.asyncio
    async def test_executes_limit_order(self, execution_engine):
        """Test execution of limit order with price improvement."""
        limit_order = Order(
            order_id="LIMIT_001",
            symbol="GBP/USD",
            order_type=OrderType.LIMIT,
            side=OrderSide.SELL,
            quantity=150000,
            price=Decimal("1.2850"),
            client_id="CLIENT_001",
            routed_broker="FXCM",
        )

        result = await execution_engine.execute_order(limit_order)

        assert result["status"] == "executed"
        # Should get price improvement or exact limit price
        assert result["fill_price"] >= limit_order.price

    @pytest.mark.asyncio
    async def test_handles_partial_fills(self, execution_engine, sample_order):
        """Test handling of partial order fills."""
        # Mock partial fills
        execution_engine.broker_connections["IB"].execute_order = AsyncMock(
            side_effect=[
                {
                    "status": "partial",
                    "fill_price": Decimal("1.0525"),
                    "fill_quantity": 30000,
                },
                {
                    "status": "partial",
                    "fill_price": Decimal("1.0526"),
                    "fill_quantity": 40000,
                },
                {
                    "status": "executed",
                    "fill_price": Decimal("1.0527"),
                    "fill_quantity": 30000,
                },
            ]
        )

        result = await execution_engine.execute_order(sample_order)

        assert result["status"] == "executed"
        assert result["total_filled"] == 100000
        assert "average_price" in result
        assert len(result["fills"]) == 3

    @pytest.mark.asyncio
    async def test_monitors_slippage(
        self, execution_engine, sample_order, mock_market_data
    ):
        """Test slippage monitoring and reporting."""
        # Set expected price
        mock_market_data.get_bid_ask.return_value = {
            "bid": Decimal("1.0520"),
            "ask": Decimal("1.0522"),
        }

        # Execute with slippage
        execution_engine.broker_connections["IB"].execute_order = AsyncMock(
            return_value={
                "status": "executed",
                "fill_price": Decimal("1.0530"),  # 8 bps slippage
                "fill_quantity": 100000,
            }
        )

        result = await execution_engine.execute_order(sample_order)

        assert "slippage_bps" in result
        assert result["slippage_bps"] > 0
        assert result["slippage_bps"] <= execution_engine.config["max_slippage_bps"]

    @pytest.mark.asyncio
    async def test_implements_twap_algorithm(self, execution_engine):
        """Test Time-Weighted Average Price execution algorithm."""
        twap_order = Order(
            order_id="TWAP_001",
            symbol="EUR/USD",
            order_type=OrderType.MARKET,
            side=OrderSide.BUY,
            quantity=1000000,
            client_id="CLIENT_001",
            metadata={"algorithm": "TWAP", "duration_minutes": 5, "slices": 10},
        )

        result = await execution_engine.execute_with_algorithm(
            twap_order, algorithm="TWAP"
        )

        assert result["status"] == "executed"
        assert result["algorithm_used"] == "TWAP"
        assert len(result["executions"]) == 10  # 10 time slices
        assert sum(e["quantity"] for e in result["executions"]) == 1000000

    @pytest.mark.asyncio
    async def test_implements_vwap_algorithm(self, execution_engine, mock_market_data):
        """Test Volume-Weighted Average Price execution algorithm."""
        vwap_order = Order(
            order_id="VWAP_001",
            symbol="GBP/USD",
            order_type=OrderType.MARKET,
            side=OrderSide.SELL,
            quantity=2000000,
            client_id="CLIENT_001",
            metadata={"algorithm": "VWAP", "participation_rate": 0.2},
        )

        # Mock volume profile
        mock_market_data.get_volume_profile.return_value = [
            {"time": "09:00", "volume": 10000000},
            {"time": "10:00", "volume": 15000000},
            {"time": "11:00", "volume": 20000000},
        ]

        result = await execution_engine.execute_with_algorithm(
            vwap_order, algorithm="VWAP"
        )

        assert result["status"] == "executed"
        assert result["algorithm_used"] == "VWAP"
        assert "volume_participation" in result

    @pytest.mark.asyncio
    async def test_implements_iceberg_algorithm(self, execution_engine):
        """Test Iceberg order execution (hidden quantity)."""
        iceberg_order = Order(
            order_id="ICEBERG_001",
            symbol="USD/JPY",
            order_type=OrderType.LIMIT,
            side=OrderSide.BUY,
            quantity=5000000,
            price=Decimal("145.50"),
            client_id="CLIENT_001",
            metadata={"algorithm": "ICEBERG", "display_quantity": 100000},
        )

        result = await execution_engine.execute_with_algorithm(
            iceberg_order, algorithm="ICEBERG"
        )

        assert result["status"] == "executed"
        assert result["algorithm_used"] == "ICEBERG"
        # Should execute in chunks matching display quantity
        assert all(e["quantity"] <= 100000 for e in result["executions"])

    @pytest.mark.asyncio
    async def test_aggregates_liquidity(self, execution_engine, sample_order):
        """Test liquidity aggregation across multiple brokers."""
        large_order = Order(
            order_id="LARGE_001",
            symbol="EUR/USD",
            order_type=OrderType.MARKET,
            side=OrderSide.BUY,
            quantity=10000000,  # Large order requiring liquidity aggregation
            client_id="CLIENT_001",
        )

        result = await execution_engine.execute_with_liquidity_aggregation(large_order)

        assert result["status"] == "executed"
        assert len(result["broker_fills"]) > 1  # Used multiple brokers
        assert sum(f["quantity"] for f in result["broker_fills"]) == 10000000

    @pytest.mark.asyncio
    async def test_performs_pre_trade_checks(self, execution_engine, sample_order):
        """Test pre-trade risk and compliance checks."""
        result = await execution_engine.perform_pre_trade_checks(sample_order)

        assert "risk_check" in result
        assert "compliance_check" in result
        assert "liquidity_check" in result
        assert "market_impact_estimate" in result

        # All checks should pass for valid order
        assert result["risk_check"]["passed"] is True
        assert result["compliance_check"]["passed"] is True

    @pytest.mark.asyncio
    async def test_calculates_market_impact(self, execution_engine, mock_market_data):
        """Test market impact calculation and monitoring."""
        large_order = Order(
            order_id="IMPACT_001",
            symbol="EUR/USD",
            order_type=OrderType.MARKET,
            side=OrderSide.BUY,
            quantity=50000000,  # Very large order
            client_id="CLIENT_001",
        )

        impact = await execution_engine.calculate_market_impact(large_order)

        assert "estimated_impact_bps" in impact
        assert "confidence_level" in impact
        assert impact["estimated_impact_bps"] > 0
        assert impact["estimated_impact_bps"] <= 100  # Reasonable bound

    @pytest.mark.asyncio
    async def test_handles_execution_failures(self, execution_engine, sample_order):
        """Test handling of execution failures and retries."""
        # Mock execution failures
        execution_engine.broker_connections["IB"].execute_order = AsyncMock(
            side_effect=[
                BrokerError("Connection timeout"),
                BrokerError("Insufficient liquidity"),
                {
                    "status": "executed",
                    "fill_price": Decimal("1.0525"),
                    "fill_quantity": 100000,
                },
            ]
        )

        result = await execution_engine.execute_order(sample_order)

        assert result["status"] == "executed"
        assert result["retry_count"] == 2

    @pytest.mark.asyncio
    async def test_reconciles_fills(self, execution_engine, sample_order):
        """Test fill reconciliation and confirmation."""
        # Execute order
        execution_result = await execution_engine.execute_order(sample_order)

        # Reconcile fills
        reconciliation = await execution_engine.reconcile_fills(
            order_id=sample_order.order_id,
            broker_fills=[
                {"broker": "IB", "quantity": 100000, "price": Decimal("1.0525")}
            ],
        )

        assert reconciliation["status"] == "reconciled"
        assert reconciliation["discrepancies"] == []

    @pytest.mark.asyncio
    async def test_tracks_execution_quality(self, execution_engine, sample_order):
        """Test execution quality metrics and reporting."""
        # Execute multiple orders
        for i in range(5):
            order = Order(
                order_id=f"QUALITY_{i:03d}",
                symbol="EUR/USD",
                order_type=OrderType.MARKET,
                side=OrderSide.BUY if i % 2 == 0 else OrderSide.SELL,
                quantity=100000,
                client_id="CLIENT_001",
                routed_broker="IB",
            )
            await execution_engine.execute_order(order)

        # Get execution quality metrics
        quality_metrics = execution_engine.get_execution_quality_metrics()

        assert "average_slippage" in quality_metrics
        assert "fill_rate" in quality_metrics
        assert "average_execution_time" in quality_metrics
        assert "best_execution_rate" in quality_metrics

    @pytest.mark.asyncio
    async def test_implements_smart_order_routing(self, execution_engine, sample_order):
        """Test smart order routing for best execution."""
        result = await execution_engine.execute_with_smart_routing(sample_order)

        assert result["status"] == "executed"
        assert "routing_decisions" in result
        assert result["achieved_best_execution"] is True

    @pytest.mark.asyncio
    async def test_handles_market_close(self, execution_engine, sample_order):
        """Test handling of market close during execution."""
        with freeze_time("2025-01-01 21:59:00"):  # Just before forex market close
            # Mock market closing during execution
            execution_engine.broker_connections["IB"].execute_order = AsyncMock(
                side_effect=BrokerError("Market closed")
            )

            with pytest.raises(ExecutionError) as exc_info:
                await execution_engine.execute_order(sample_order)

            assert "market closed" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_performs_post_trade_analysis(self, execution_engine, sample_order):
        """Test post-trade analysis and TCA (Transaction Cost Analysis)."""
        # Execute order
        execution_result = await execution_engine.execute_order(sample_order)

        # Perform post-trade analysis
        tca_result = await execution_engine.perform_tca(
            order_id=sample_order.order_id, execution_result=execution_result
        )

        assert "implementation_shortfall" in tca_result
        assert "arrival_price" in tca_result
        assert "effective_spread" in tca_result
        assert "market_impact" in tca_result
        assert "timing_cost" in tca_result

    @pytest.mark.asyncio
    async def test_handles_order_amendments(self, execution_engine, sample_order):
        """Test handling of order amendments during execution."""
        # Start execution
        execution_task = asyncio.create_task(
            execution_engine.execute_order(sample_order)
        )

        # Amend order during execution
        await asyncio.sleep(0.1)
        amendment_result = await execution_engine.amend_executing_order(
            order_id=sample_order.order_id, new_quantity=150000
        )

        assert amendment_result["status"] == "amended"

        # Complete execution
        result = await execution_task
        assert result["fill_quantity"] == 150000

    @pytest.mark.asyncio
    async def test_implements_dark_pool_routing(self, execution_engine):
        """Test routing to dark pools for large orders."""
        large_order = Order(
            order_id="DARK_001",
            symbol="EUR/USD",
            order_type=OrderType.MARKET,
            side=OrderSide.BUY,
            quantity=100000000,  # Very large order
            client_id="CLIENT_001",
            metadata={"allow_dark_pools": True},
        )

        result = await execution_engine.execute_with_dark_pools(large_order)

        assert result["status"] == "executed"
        assert "dark_pool_fills" in result
        assert len(result["dark_pool_fills"]) > 0

    @pytest.mark.asyncio
    async def test_monitors_regulatory_compliance(self, execution_engine, sample_order):
        """Test regulatory compliance monitoring during execution."""
        compliance_result = await execution_engine.check_execution_compliance(
            sample_order
        )

        assert "mifid_compliant" in compliance_result
        assert "best_execution_achieved" in compliance_result
        assert "audit_trail" in compliance_result
        assert compliance_result["mifid_compliant"] is True

    @pytest.mark.asyncio
    async def test_handles_concurrent_executions(self, execution_engine):
        """Test concurrent execution of multiple orders."""
        orders = []
        for i in range(10):
            order = Order(
                order_id=f"CONCURRENT_{i:03d}",
                symbol="EUR/USD" if i % 2 == 0 else "GBP/USD",
                order_type=OrderType.MARKET,
                side=OrderSide.BUY if i % 2 == 0 else OrderSide.SELL,
                quantity=100000,
                client_id="CLIENT_001",
                routed_broker="IB" if i % 3 == 0 else "FXCM",
            )
            orders.append(order)

        # Execute concurrently
        tasks = [execution_engine.execute_order(order) for order in orders]
        results = await asyncio.gather(*tasks)

        assert len(results) == 10
        assert all(r["status"] == "executed" for r in results)
