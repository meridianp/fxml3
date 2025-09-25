"""
Sprint 3 System Integration Tests
==================================

Comprehensive integration tests verifying that all Sprint 1 & 2 components
work together seamlessly in a production-like environment.

Test Coverage:
- WebSocket → ML Pipeline → Risk Management flow
- Authentication → Order Execution → FIX Translation flow
- Risk Management → Compliance → Audit Trail flow
- End-to-end signal generation to trade execution
- System resilience and error recovery
"""

import asyncio
import time
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import Mock, patch, AsyncMock

import pytest
import pandas as pd
import numpy as np

from core.integration.trading_system_orchestrator import (
    TradingSystemOrchestrator,
    SystemState,
    TradingSignal
)


class TestSystemIntegration:
    """Integration tests for the complete trading system."""

    @pytest.fixture
    async def orchestrator(self):
        """Create and initialize trading system orchestrator."""
        config = {
            "max_concurrent_trades": 5,
            "max_portfolio_risk": 0.02,
            "max_position_size": 500000,
            "confidence_threshold": 0.65,
            "enable_paper_trading": True
        }
        orchestrator = TradingSystemOrchestrator(config)
        return orchestrator

    @pytest.fixture
    def mock_market_data(self):
        """Generate mock market data for testing."""
        dates = pd.date_range(start="2024-01-01", periods=100, freq="1h")
        return pd.DataFrame({
            "timestamp": dates,
            "symbol": ["EURUSD"] * 100,
            "open": np.random.uniform(1.19, 1.21, 100),
            "high": np.random.uniform(1.20, 1.22, 100),
            "low": np.random.uniform(1.18, 1.20, 100),
            "close": np.random.uniform(1.19, 1.21, 100),
            "volume": np.random.randint(100000, 1000000, 100)
        })

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_system_initialization(self, orchestrator):
        """Test that all system components initialize correctly."""
        # Initialize the system
        initialized = await orchestrator.initialize_system()

        # Verify initialization
        assert initialized == True, "System should initialize successfully"
        assert orchestrator.state == SystemState.READY, "System should be in READY state"

        # Check component health
        health = orchestrator.component_health
        assert health["ml_pipeline"] == True, "ML pipeline should be healthy"
        assert health["risk_manager"] == True, "Risk manager should be healthy"
        assert health["compliance"] == True, "Compliance monitor should be healthy"
        assert health["auth"] == True, "Auth service should be healthy"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_websocket_to_ml_pipeline_flow(self, orchestrator, mock_market_data):
        """Test data flow from WebSocket to ML pipeline."""
        await orchestrator.initialize_system()

        # Process market data through ML pipeline
        ml_result = await orchestrator.ml_pipeline.process_market_data(mock_market_data)

        # Verify ML pipeline output
        assert ml_result is not None, "ML pipeline should process data"
        assert "signal" in ml_result, "ML result should contain signal"
        assert "confidence" in ml_result, "ML result should contain confidence"
        assert ml_result["confidence"] >= 0 and ml_result["confidence"] <= 1

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_ml_signal_to_risk_validation_flow(self, orchestrator):
        """Test ML signal processing through risk management."""
        await orchestrator.initialize_system()

        # Create test signal
        signal = TradingSignal(
            symbol="EURUSD",
            action="BUY",
            confidence=0.75,
            quantity=100000,
            stop_loss_pips=20,
            take_profit_pips=40,
            source="test_model",
            timestamp=datetime.now(timezone.utc),
            metadata={}
        )

        # Calculate position size with risk management
        position_size = orchestrator.risk_manager.calculate_position_size(
            symbol=signal.symbol,
            risk_amount=1000,
            stop_loss_pips=signal.stop_loss_pips,
            pip_value=10
        )

        # Verify risk calculations
        assert position_size > 0, "Position size should be calculated"
        assert position_size <= orchestrator.config["max_position_size"]

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_order_creation_to_fix_translation_flow(self, orchestrator):
        """Test order creation and FIX protocol translation."""
        await orchestrator.initialize_system()

        from core.trading.orders import OrderSide, OrderType

        # Create order through order manager
        order = await orchestrator.order_manager.create_order(
            user_id="test_user",
            symbol="EUR/USD",
            side=OrderSide.BUY,
            quantity=100000,
            order_type=OrderType.MARKET
        )

        # Verify order creation
        assert order is not None, "Order should be created"
        assert order.symbol == "EUR/USD"
        assert order.quantity == 100000
        assert order.state.value == "pending"

        # Test FIX translation (if simplefix is available)
        try:
            fix_message = orchestrator.fix_translator.translate_to_fix(order)
            assert fix_message is not None, "FIX message should be created"
            assert fix_message.symbol == "EURUSD"  # FIX format without slash
        except ImportError:
            # Graceful degradation if simplefix not installed
            pass

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_stop_loss_integration(self, orchestrator):
        """Test stop loss calculation and management."""
        await orchestrator.initialize_system()

        from core.risk.stop_loss_manager import StopLossConfig, StopLossType

        # Configure stop loss
        stop_config = StopLossConfig(
            stop_type=StopLossType.FIXED,
            value=Decimal("25.0")  # 25 pips
        )

        # Calculate stop loss price
        entry_price = Decimal("1.2500")
        stop_price = orchestrator.stop_loss_manager.calculate_initial_stop_loss(
            entry_price=entry_price,
            side="long",
            stop_config=stop_config
        )

        # Verify stop loss calculation
        assert stop_price < entry_price, "Stop loss should be below entry for long"
        expected_stop = entry_price - (Decimal("25.0") / Decimal("10000"))
        assert stop_price == expected_stop

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_compliance_validation_flow(self, orchestrator):
        """Test compliance validation in the trading flow."""
        await orchestrator.initialize_system()

        # Test compliant signal
        compliant_signal = TradingSignal(
            symbol="EURUSD",
            action="BUY",
            confidence=0.75,
            quantity=100000,
            stop_loss_pips=20,
            take_profit_pips=40,
            source="test_model",
            timestamp=datetime.now(timezone.utc),
            metadata={}
        )

        compliance_status = await orchestrator._check_compliance(compliant_signal)
        assert compliance_status.value == "compliant"

        # Test non-compliant signal (low confidence)
        non_compliant_signal = TradingSignal(
            symbol="EURUSD",
            action="BUY",
            confidence=0.45,  # Below threshold
            quantity=100000,
            stop_loss_pips=20,
            take_profit_pips=40,
            source="test_model",
            timestamp=datetime.now(timezone.utc),
            metadata={}
        )

        compliance_status = await orchestrator._check_compliance(non_compliant_signal)
        assert compliance_status.value == "non_compliant"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_end_to_end_signal_execution(self, orchestrator):
        """Test complete signal execution from generation to order submission."""
        await orchestrator.initialize_system()

        # Create high-confidence trading signal
        signal = TradingSignal(
            symbol="EURUSD",
            action="BUY",
            confidence=0.85,
            quantity=100000,
            stop_loss_pips=20,
            take_profit_pips=40,
            source="ml_ensemble",
            timestamp=datetime.now(timezone.utc),
            metadata={"model": "ensemble", "features_used": 70}
        )

        # Execute trading signal
        order = await orchestrator.execute_trading_signal(signal)

        # Verify execution metrics
        assert orchestrator.metrics["total_signals"] == 1

        # Order might be None if risk/compliance checks fail
        if order is not None:
            assert orchestrator.metrics["executed_trades"] == 1
            assert order.symbol == "EURUSD"
        else:
            assert orchestrator.metrics["rejected_trades"] == 1

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_system_metrics_tracking(self, orchestrator):
        """Test that system metrics are properly tracked."""
        await orchestrator.initialize_system()

        initial_metrics = orchestrator.metrics.copy()

        # Process multiple signals
        for i in range(5):
            signal = TradingSignal(
                symbol="EURUSD",
                action="BUY" if i % 2 == 0 else "SELL",
                confidence=0.7 + (i * 0.02),
                quantity=100000,
                stop_loss_pips=20,
                take_profit_pips=40,
                source=f"model_{i}",
                timestamp=datetime.now(timezone.utc),
                metadata={}
            )
            await orchestrator.execute_trading_signal(signal)

        # Verify metrics updated
        assert orchestrator.metrics["total_signals"] >= initial_metrics["total_signals"] + 5
        assert (orchestrator.metrics["executed_trades"] +
                orchestrator.metrics["rejected_trades"]) >= 5

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_system_status_reporting(self, orchestrator):
        """Test system status reporting functionality."""
        await orchestrator.initialize_system()

        status = orchestrator.get_system_status()

        # Verify status structure
        assert "state" in status
        assert status["state"] == "ready"
        assert "component_health" in status
        assert "metrics" in status
        assert "config" in status
        assert "timestamp" in status

        # Verify component health reporting
        health = status["component_health"]
        assert isinstance(health, dict)
        assert len(health) >= 5  # At least 5 components

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_graceful_shutdown(self, orchestrator):
        """Test graceful system shutdown."""
        await orchestrator.initialize_system()

        # Create some active orders
        from core.trading.orders import OrderSide, OrderType

        order = await orchestrator.order_manager.create_order(
            user_id="test_user",
            symbol="EUR/USD",
            side=OrderSide.BUY,
            quantity=100000,
            order_type=OrderType.MARKET
        )

        # Shutdown system
        await orchestrator.shutdown()

        # Verify shutdown state
        assert orchestrator.state == SystemState.SHUTDOWN

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_authentication_integration(self, orchestrator):
        """Test JWT authentication integration."""
        await orchestrator.initialize_system()

        # Create test user
        from core.api.auth.models import UserRole

        class MockUser:
            def __init__(self):
                self.user_id = "test_trader"
                self.username = "test_trader"
                self.role = UserRole.TRADER

        user = MockUser()

        # Generate token pair
        token_pair = orchestrator.auth_service.generate_token_pair(user)

        # Verify token generation
        assert token_pair is not None
        assert token_pair.access_token is not None
        assert token_pair.refresh_token is not None
        assert token_pair.token_type == "bearer"

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.performance
    async def test_system_performance_under_load(self, orchestrator):
        """Test system performance with multiple concurrent operations."""
        await orchestrator.initialize_system()

        start_time = time.perf_counter()

        # Simulate concurrent signal processing
        signals = []
        for i in range(100):
            signal = TradingSignal(
                symbol=f"PAIR{i%5}",  # 5 different pairs
                action="BUY" if i % 2 == 0 else "SELL",
                confidence=0.65 + (i % 20) * 0.01,
                quantity=100000,
                stop_loss_pips=20,
                take_profit_pips=40,
                source="load_test",
                timestamp=datetime.now(timezone.utc),
                metadata={}
            )
            signals.append(signal)

        # Process signals concurrently
        tasks = [orchestrator.execute_trading_signal(signal) for signal in signals]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        end_time = time.perf_counter()
        duration = end_time - start_time

        # Performance assertions
        assert duration < 10, f"Processing 100 signals took {duration:.2f}s, should be < 10s"

        # Verify results
        successful_orders = [r for r in results if r is not None and not isinstance(r, Exception)]
        assert len(successful_orders) > 0, "Some orders should execute successfully"

        print(f"Performance Test: Processed {len(signals)} signals in {duration:.2f}s")
        print(f"Throughput: {len(signals)/duration:.1f} signals/second")


# Run integration tests
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])