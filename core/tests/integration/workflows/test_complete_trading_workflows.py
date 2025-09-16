"""
TDD Integration Tests for Complete Trading Workflows

End-to-end integration tests that validate complete trading scenarios
from signal generation through order execution to position management.
"""

import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import numpy as np
import pandas as pd
import pytest


@pytest.mark.tdd
@pytest.mark.integration
@pytest.mark.workflow
class TestCompleteTradingWorkflows:
    """
    Integration tests for complete trading workflows.

    Tests end-to-end scenarios including signal generation, risk validation,
    order execution, position management, and performance tracking.
    """

    @pytest.fixture
    def trading_system_config(self):
        """Complete trading system configuration."""
        return {
            "risk_limits": {
                "max_position_size": 1000000,
                "max_daily_loss": 0.02,
                "max_drawdown": 0.15,
                "leverage_limit": 50,
            },
            "trading_params": {
                "signal_confidence_threshold": 0.7,
                "stop_loss_pips": 20,
                "take_profit_pips": 40,
                "position_size_pct": 0.02,
            },
            "execution_params": {
                "slippage_tolerance": 0.0002,
                "max_execution_time": 30,
                "retry_attempts": 3,
            },
            "data_feeds": {
                "primary": "ib_market_data",
                "backup": "external_feed",
                "update_frequency": "real_time",
            },
        }

    @pytest.fixture
    def market_data_stream(self):
        """Simulated real-time market data stream."""
        base_prices = {
            "EUR/USD": 1.0850,
            "GBP/USD": 1.2500,
            "USD/JPY": 110.50,
            "AUD/USD": 0.7500,
        }

        def generate_market_tick(symbol: str, base_price: float, tick_count: int):
            """Generate realistic market ticks."""
            ticks = []
            current_price = base_price

            for i in range(tick_count):
                # Simulate price movement
                price_change = np.random.normal(0, 0.0001)
                current_price += price_change

                tick = {
                    "symbol": symbol,
                    "timestamp": datetime.now() + timedelta(milliseconds=i * 100),
                    "bid": current_price - 0.0001,
                    "ask": current_price + 0.0001,
                    "last": current_price,
                    "volume": np.random.randint(1, 10),
                }
                ticks.append(tick)

            return ticks

        market_stream = {}
        for symbol, base_price in base_prices.items():
            market_stream[symbol] = generate_market_tick(symbol, base_price, 1000)

        return market_stream

    @pytest.fixture
    async def integrated_trading_system(self, trading_system_config):
        """Create fully integrated trading system."""
        # Mock all major components
        components = {
            "signal_generator": Mock(),
            "risk_manager": Mock(),
            "order_executor": Mock(),
            "position_manager": Mock(),
            "data_feed": Mock(),
            "broker_adapter": Mock(),
            "portfolio_tracker": Mock(),
        }

        # Configure mocks with realistic behavior
        components["signal_generator"].generate_signal = AsyncMock()
        components["risk_manager"].validate_trade = AsyncMock()
        components["order_executor"].execute_order = AsyncMock()
        components["position_manager"].update_position = AsyncMock()
        components["broker_adapter"].place_order = AsyncMock()

        from core.trading.trading_system import TradingSystem

        with patch.multiple(
            "core.trading.trading_system",
            SignalGenerator=lambda: components["signal_generator"],
            RiskManager=lambda config: components["risk_manager"],
            OrderExecutor=lambda config: components["order_executor"],
            PositionManager=lambda config: components["position_manager"],
            BrokerAdapter=lambda config: components["broker_adapter"],
        ):
            system = TradingSystem(config=trading_system_config)
            await system.initialize()
            yield system, components
            await system.shutdown()

    # -------------------------------------------------------------------------
    # Complete Signal-to-Execution Workflow Tests
    # -------------------------------------------------------------------------

    @pytest.mark.red
    async def test_complete_buy_signal_workflow(
        self, integrated_trading_system, market_data_stream
    ):
        """RED: Test complete workflow from buy signal to order execution."""
        system, components = integrated_trading_system

        # Configure signal generation
        buy_signal = {
            "symbol": "EUR/USD",
            "direction": "BUY",
            "confidence": 0.85,
            "entry_price": 1.0850,
            "stop_loss": 1.0830,
            "take_profit": 1.0890,
            "timestamp": datetime.now(),
            "signal_strength": "STRONG",
        }

        components["signal_generator"].generate_signal.return_value = buy_signal

        # Configure risk validation (approved)
        risk_validation = {
            "approved": True,
            "position_size": 100000,
            "risk_amount": 2000,
            "margin_required": 2000,
            "warnings": [],
        }

        components["risk_manager"].validate_trade.return_value = risk_validation

        # Configure order execution
        execution_result = {
            "order_id": "ORDER_12345",
            "status": "FILLED",
            "filled_quantity": 100000,
            "avg_fill_price": 1.0851,
            "commission": 5.0,
            "execution_time": datetime.now(),
        }

        components["order_executor"].execute_order.return_value = execution_result

        # Process market data and generate signal
        market_tick = market_data_stream["EUR/USD"][0]
        await system.process_market_data(market_tick)

        # Verify complete workflow execution
        components["signal_generator"].generate_signal.assert_called_once()
        components["risk_manager"].validate_trade.assert_called_once()
        components["order_executor"].execute_order.assert_called_once()

        # Verify signal was processed correctly
        signal_call_args = components["signal_generator"].generate_signal.call_args
        assert signal_call_args[1]["symbol"] == "EUR/USD"

        # Verify risk validation was performed
        risk_call_args = components["risk_manager"].validate_trade.call_args
        assert risk_call_args[1]["signal"]["direction"] == "BUY"

        # Verify order execution parameters
        execution_call_args = components["order_executor"].execute_order.call_args
        assert execution_call_args[1]["quantity"] == 100000
        assert execution_call_args[1]["symbol"] == "EUR/USD"

    @pytest.mark.red
    async def test_signal_rejection_workflow(
        self, integrated_trading_system, market_data_stream
    ):
        """RED: Test workflow when signal is rejected by risk management."""
        system, components = integrated_trading_system

        # Generate high-risk signal
        risky_signal = {
            "symbol": "EUR/USD",
            "direction": "BUY",
            "confidence": 0.95,
            "entry_price": 1.0850,
            "stop_loss": 1.0800,  # Large stop loss
            "take_profit": 1.0870,  # Small profit target
            "timestamp": datetime.now(),
        }

        components["signal_generator"].generate_signal.return_value = risky_signal

        # Risk manager rejects the trade
        risk_rejection = {
            "approved": False,
            "rejection_reason": "EXCESSIVE_RISK",
            "risk_score": 0.95,
            "max_allowed_risk": 0.80,
            "warnings": ["Position size too large", "Poor risk-reward ratio"],
        }

        components["risk_manager"].validate_trade.return_value = risk_rejection

        # Process market data
        market_tick = market_data_stream["EUR/USD"][0]
        await system.process_market_data(market_tick)

        # Verify signal was generated but order was not executed
        components["signal_generator"].generate_signal.assert_called_once()
        components["risk_manager"].validate_trade.assert_called_once()
        components["order_executor"].execute_order.assert_not_called()

        # Verify rejection was logged
        assert system.get_rejected_signals_count() > 0
        latest_rejection = system.get_latest_rejection()
        assert latest_rejection["reason"] == "EXCESSIVE_RISK"

    @pytest.mark.red
    async def test_multi_symbol_concurrent_workflow(
        self, integrated_trading_system, market_data_stream
    ):
        """RED: Test concurrent signal processing for multiple symbols."""
        system, components = integrated_trading_system

        # Configure signals for multiple symbols
        signals = {
            "EUR/USD": {
                "symbol": "EUR/USD",
                "direction": "BUY",
                "confidence": 0.80,
                "entry_price": 1.0850,
            },
            "GBP/USD": {
                "symbol": "GBP/USD",
                "direction": "SELL",
                "confidence": 0.75,
                "entry_price": 1.2500,
            },
            "USD/JPY": {
                "symbol": "USD/JPY",
                "direction": "BUY",
                "confidence": 0.85,
                "entry_price": 110.50,
            },
        }

        def signal_side_effect(*args, **kwargs):
            symbol = kwargs.get("symbol")
            return signals.get(symbol)

        components["signal_generator"].generate_signal.side_effect = signal_side_effect

        # All trades approved by risk manager
        components["risk_manager"].validate_trade.return_value = {
            "approved": True,
            "position_size": 50000,
            "risk_amount": 1000,
        }

        # Successful executions
        def execution_side_effect(*args, **kwargs):
            return {
                "order_id": f"ORDER_{np.random.randint(10000, 99999)}",
                "status": "FILLED",
                "filled_quantity": kwargs.get("quantity", 50000),
                "avg_fill_price": kwargs.get("price", 1.0000),
            }

        components["order_executor"].execute_order.side_effect = execution_side_effect

        # Process market data for all symbols concurrently
        market_tasks = []
        for symbol, ticks in market_data_stream.items():
            if symbol in signals:
                task = system.process_market_data(ticks[0])
                market_tasks.append(task)

        await asyncio.gather(*market_tasks)

        # Verify all signals were processed
        assert components["signal_generator"].generate_signal.call_count == 3
        assert components["risk_manager"].validate_trade.call_count == 3
        assert components["order_executor"].execute_order.call_count == 3

    # -------------------------------------------------------------------------
    # Position Management Workflow Tests
    # -------------------------------------------------------------------------

    @pytest.mark.red
    async def test_position_lifecycle_workflow(
        self, integrated_trading_system, market_data_stream
    ):
        """RED: Test complete position lifecycle from entry to exit."""
        system, components = integrated_trading_system

        # Step 1: Position entry
        entry_signal = {
            "symbol": "EUR/USD",
            "direction": "BUY",
            "confidence": 0.80,
            "entry_price": 1.0850,
            "stop_loss": 1.0830,
            "take_profit": 1.0890,
        }

        components["signal_generator"].generate_signal.return_value = entry_signal
        components["risk_manager"].validate_trade.return_value = {
            "approved": True,
            "position_size": 100000,
        }

        entry_execution = {
            "order_id": "ENTRY_001",
            "status": "FILLED",
            "filled_quantity": 100000,
            "avg_fill_price": 1.0851,
            "position_id": "POS_001",
        }

        components["order_executor"].execute_order.return_value = entry_execution

        # Execute entry
        await system.process_market_data(market_data_stream["EUR/USD"][0])

        # Step 2: Position monitoring and updates
        # Simulate price movement in favor
        favorable_tick = {
            "symbol": "EUR/USD",
            "timestamp": datetime.now(),
            "bid": 1.0875,
            "ask": 1.0877,
            "last": 1.0876,
        }

        # Configure position update
        position_update = {
            "position_id": "POS_001",
            "current_price": 1.0876,
            "unrealized_pnl": 250,  # $250 profit
            "status": "OPEN",
            "should_adjust_stops": True,
            "new_stop_loss": 1.0850,  # Trail stop loss
        }

        components["position_manager"].update_position.return_value = position_update

        await system.process_market_data(favorable_tick)

        # Step 3: Position exit (take profit hit)
        exit_tick = {
            "symbol": "EUR/USD",
            "timestamp": datetime.now(),
            "bid": 1.0890,
            "ask": 1.0892,
            "last": 1.0891,
        }

        # Configure exit signal
        exit_signal = {
            "symbol": "EUR/USD",
            "direction": "SELL",
            "signal_type": "TAKE_PROFIT",
            "position_id": "POS_001",
            "exit_price": 1.0890,
        }

        components["signal_generator"].generate_signal.return_value = exit_signal

        exit_execution = {
            "order_id": "EXIT_001",
            "status": "FILLED",
            "filled_quantity": 100000,
            "avg_fill_price": 1.0890,
            "realized_pnl": 390,  # $390 profit after commission
        }

        components["order_executor"].execute_order.return_value = exit_execution

        await system.process_market_data(exit_tick)

        # Verify complete lifecycle
        assert (
            components["order_executor"].execute_order.call_count >= 2
        )  # Entry + Exit
        components["position_manager"].update_position.assert_called()

        # Verify position was closed profitably
        final_pnl = system.get_position_pnl("POS_001")
        assert final_pnl > 0

    @pytest.mark.red
    async def test_stop_loss_triggered_workflow(
        self, integrated_trading_system, market_data_stream
    ):
        """RED: Test workflow when stop loss is triggered."""
        system, components = integrated_trading_system

        # Create position
        entry_signal = {
            "symbol": "EUR/USD",
            "direction": "BUY",
            "entry_price": 1.0850,
            "stop_loss": 1.0830,
            "position_size": 100000,
        }

        components["signal_generator"].generate_signal.return_value = entry_signal
        components["risk_manager"].validate_trade.return_value = {
            "approved": True,
            "position_size": 100000,
        }
        components["order_executor"].execute_order.return_value = {
            "order_id": "ENTRY_001",
            "status": "FILLED",
            "position_id": "POS_STOPLOSS_001",
        }

        # Execute entry
        await system.process_market_data(market_data_stream["EUR/USD"][0])

        # Simulate adverse price movement triggering stop loss
        adverse_tick = {
            "symbol": "EUR/USD",
            "timestamp": datetime.now(),
            "bid": 1.0829,
            "ask": 1.0831,
            "last": 1.0830,
        }

        # Stop loss signal generated
        stop_loss_signal = {
            "symbol": "EUR/USD",
            "direction": "SELL",
            "signal_type": "STOP_LOSS",
            "position_id": "POS_STOPLOSS_001",
            "exit_price": 1.0830,
            "urgency": "HIGH",
        }

        components["signal_generator"].generate_signal.return_value = stop_loss_signal

        # Stop loss execution
        stop_loss_execution = {
            "order_id": "STOP_001",
            "status": "FILLED",
            "filled_quantity": 100000,
            "avg_fill_price": 1.0829,  # Some slippage
            "realized_pnl": -210,  # Loss including commission
        }

        components["order_executor"].execute_order.return_value = stop_loss_execution

        await system.process_market_data(adverse_tick)

        # Verify stop loss was triggered and executed
        assert components["order_executor"].execute_order.call_count >= 2

        # Verify loss was limited
        final_pnl = system.get_position_pnl("POS_STOPLOSS_001")
        assert final_pnl < 0  # Loss occurred
        assert final_pnl > -500  # But loss was limited

    # -------------------------------------------------------------------------
    # Risk Management Integration Tests
    # -------------------------------------------------------------------------

    @pytest.mark.red
    async def test_portfolio_risk_limit_workflow(
        self, integrated_trading_system, market_data_stream
    ):
        """RED: Test workflow when portfolio risk limits are reached."""
        system, components = integrated_trading_system

        # Simulate existing high-risk portfolio
        existing_portfolio = [
            {"symbol": "EUR/USD", "position_size": 500000, "unrealized_pnl": -8000},
            {"symbol": "GBP/USD", "position_size": -300000, "unrealized_pnl": -5000},
            {"symbol": "USD/JPY", "position_size": 200000, "unrealized_pnl": -3000},
        ]

        system.set_current_portfolio(existing_portfolio)

        # New signal that would exceed risk limits
        new_signal = {
            "symbol": "AUD/USD",
            "direction": "BUY",
            "confidence": 0.90,
            "entry_price": 0.7500,
            "position_size": 400000,  # Large position
        }

        components["signal_generator"].generate_signal.return_value = new_signal

        # Risk manager blocks due to portfolio limits
        risk_block = {
            "approved": False,
            "rejection_reason": "PORTFOLIO_RISK_LIMIT_EXCEEDED",
            "current_portfolio_risk": 0.16,  # 16% portfolio risk
            "max_allowed_risk": 0.15,  # 15% limit
            "recommended_action": "REDUCE_EXISTING_POSITIONS",
        }

        components["risk_manager"].validate_trade.return_value = risk_block

        # Process new signal
        await system.process_market_data(market_data_stream["AUD/USD"][0])

        # Verify trade was blocked
        components["signal_generator"].generate_signal.assert_called_once()
        components["risk_manager"].validate_trade.assert_called_once()
        components["order_executor"].execute_order.assert_not_called()

        # Verify risk management action was triggered
        risk_actions = system.get_pending_risk_actions()
        assert len(risk_actions) > 0
        assert any(action["type"] == "REDUCE_POSITIONS" for action in risk_actions)

    @pytest.mark.red
    async def test_margin_call_workflow(
        self, integrated_trading_system, market_data_stream
    ):
        """RED: Test workflow during margin call scenario."""
        system, components = integrated_trading_system

        # Simulate margin call scenario
        margin_call_state = {
            "account_equity": 8000,
            "used_margin": 7500,
            "free_margin": 500,
            "margin_level": 106.7,  # Below margin call threshold
            "status": "MARGIN_CALL",
        }

        system.set_account_state(margin_call_state)

        # Any new signal should be blocked
        new_signal = {"symbol": "EUR/USD", "direction": "BUY", "confidence": 0.95}

        components["signal_generator"].generate_signal.return_value = new_signal

        # Risk manager blocks all new trades
        margin_block = {
            "approved": False,
            "rejection_reason": "MARGIN_CALL_ACTIVE",
            "required_action": "CLOSE_POSITIONS",
            "positions_to_close": ["POS_001", "POS_002"],
        }

        components["risk_manager"].validate_trade.return_value = margin_block

        # Process signal during margin call
        await system.process_market_data(market_data_stream["EUR/USD"][0])

        # Verify no new positions opened
        components["order_executor"].execute_order.assert_not_called()

        # Verify margin call response initiated
        margin_actions = system.get_margin_call_actions()
        assert len(margin_actions) > 0
        assert "CLOSE_POSITIONS" in [action["type"] for action in margin_actions]

    # -------------------------------------------------------------------------
    # Performance Monitoring Workflow Tests
    # -------------------------------------------------------------------------

    @pytest.mark.red
    async def test_performance_tracking_workflow(
        self, integrated_trading_system, market_data_stream
    ):
        """RED: Test performance tracking throughout trading workflow."""
        system, components = integrated_trading_system

        # Execute multiple trades to track performance
        trade_scenarios = [
            {
                "symbol": "EUR/USD",
                "direction": "BUY",
                "entry": 1.0850,
                "exit": 1.0890,
                "expected_pnl": 400,
            },
            {
                "symbol": "GBP/USD",
                "direction": "SELL",
                "entry": 1.2500,
                "exit": 1.2470,
                "expected_pnl": 300,
            },
            {
                "symbol": "USD/JPY",
                "direction": "BUY",
                "entry": 110.50,
                "exit": 110.20,
                "expected_pnl": -300,
            },
        ]

        total_expected_pnl = sum(trade["expected_pnl"] for trade in trade_scenarios)

        # Configure mock responses
        components["risk_manager"].validate_trade.return_value = {
            "approved": True,
            "position_size": 100000,
        }

        execution_results = []
        for i, trade in enumerate(trade_scenarios):
            execution_results.append(
                {
                    "order_id": f"TRADE_{i:03d}",
                    "status": "FILLED",
                    "realized_pnl": trade["expected_pnl"],
                }
            )

        components["order_executor"].execute_order.side_effect = execution_results

        # Execute all trades
        for i, trade in enumerate(trade_scenarios):
            signal = {
                "symbol": trade["symbol"],
                "direction": trade["direction"],
                "entry_price": trade["entry"],
            }
            components["signal_generator"].generate_signal.return_value = signal

            # Process entry and exit
            await system.process_market_data(market_data_stream[trade["symbol"]][i])

        # Verify performance metrics
        performance_stats = system.get_performance_statistics()

        assert "total_pnl" in performance_stats
        assert "win_rate" in performance_stats
        assert "sharpe_ratio" in performance_stats
        assert "max_drawdown" in performance_stats

        # Check that PnL tracking is working
        assert abs(performance_stats["total_pnl"] - total_expected_pnl) < 100

        # Verify trade count
        assert performance_stats["total_trades"] == len(trade_scenarios)

    # -------------------------------------------------------------------------
    # Error Recovery Workflow Tests
    # -------------------------------------------------------------------------

    @pytest.mark.red
    async def test_connection_failure_recovery_workflow(
        self, integrated_trading_system, market_data_stream
    ):
        """RED: Test workflow recovery after connection failure."""
        system, components = integrated_trading_system

        # Simulate connection failure during order execution
        connection_error = ConnectionError("Broker connection lost")
        components["order_executor"].execute_order.side_effect = connection_error

        # Generate signal
        signal = {"symbol": "EUR/USD", "direction": "BUY", "confidence": 0.80}

        components["signal_generator"].generate_signal.return_value = signal
        components["risk_manager"].validate_trade.return_value = {
            "approved": True,
            "position_size": 100000,
        }

        # Process signal (should trigger error handling)
        await system.process_market_data(market_data_stream["EUR/USD"][0])

        # Verify error was caught and logged
        assert system.get_error_count() > 0
        latest_error = system.get_latest_error()
        assert "connection" in latest_error["message"].lower()

        # Verify order was queued for retry
        pending_orders = system.get_pending_orders()
        assert len(pending_orders) > 0

        # Simulate connection recovery
        components["order_executor"].execute_order.side_effect = None
        components["order_executor"].execute_order.return_value = {
            "order_id": "RECOVERY_001",
            "status": "FILLED",
        }

        # Trigger retry mechanism
        await system.retry_failed_operations()

        # Verify order was successfully executed after recovery
        assert components["order_executor"].execute_order.call_count >= 2
        assert len(system.get_pending_orders()) == 0

    @pytest.mark.red
    async def test_data_feed_interruption_workflow(
        self, integrated_trading_system, market_data_stream
    ):
        """RED: Test workflow during data feed interruption."""
        system, components = integrated_trading_system

        # Simulate data feed interruption
        system.simulate_data_feed_interruption()

        # Attempt to process stale data
        stale_tick = {
            "symbol": "EUR/USD",
            "timestamp": datetime.now() - timedelta(minutes=5),  # 5 minutes old
            "bid": 1.0850,
            "ask": 1.0852,
        }

        # Signal generator should handle stale data
        components["signal_generator"].generate_signal.return_value = (
            None  # No signal on stale data
        )

        await system.process_market_data(stale_tick)

        # Verify no trades executed on stale data
        components["order_executor"].execute_order.assert_not_called()

        # Verify system entered safe mode
        assert system.get_operating_mode() == "SAFE_MODE"

        # Simulate data feed recovery
        system.restore_data_feed()

        # Fresh data should restore normal operation
        fresh_tick = {
            "symbol": "EUR/USD",
            "timestamp": datetime.now(),
            "bid": 1.0850,
            "ask": 1.0852,
        }

        components["signal_generator"].generate_signal.return_value = {
            "symbol": "EUR/USD",
            "direction": "BUY",
        }
        components["risk_manager"].validate_trade.return_value = {
            "approved": True,
            "position_size": 100000,
        }
        components["order_executor"].execute_order.return_value = {
            "order_id": "RECOVERY_002",
            "status": "FILLED",
        }

        await system.process_market_data(fresh_tick)

        # Verify normal operation resumed
        assert system.get_operating_mode() == "NORMAL"
        components["order_executor"].execute_order.assert_called_once()

    # -------------------------------------------------------------------------
    # Compliance and Audit Workflow Tests
    # -------------------------------------------------------------------------

    @pytest.mark.red
    async def test_audit_trail_workflow(
        self, integrated_trading_system, market_data_stream
    ):
        """RED: Test complete audit trail generation workflow."""
        system, components = integrated_trading_system

        # Execute a complete trade with full audit logging
        trade_signal = {
            "symbol": "EUR/USD",
            "direction": "BUY",
            "confidence": 0.85,
            "signal_id": "SIG_AUDIT_001",
            "strategy": "ML_ENSEMBLE_v2.1",
        }

        components["signal_generator"].generate_signal.return_value = trade_signal
        components["risk_manager"].validate_trade.return_value = {
            "approved": True,
            "position_size": 100000,
            "validation_id": "RISK_AUDIT_001",
        }
        components["order_executor"].execute_order.return_value = {
            "order_id": "ORDER_AUDIT_001",
            "status": "FILLED",
            "execution_id": "EXEC_AUDIT_001",
        }

        # Process trade
        await system.process_market_data(market_data_stream["EUR/USD"][0])

        # Verify audit trail completeness
        audit_trail = system.get_audit_trail("SIG_AUDIT_001")

        required_audit_events = [
            "SIGNAL_GENERATED",
            "RISK_VALIDATION_PERFORMED",
            "ORDER_SUBMITTED",
            "ORDER_EXECUTED",
            "POSITION_UPDATED",
        ]

        for event_type in required_audit_events:
            assert any(event["type"] == event_type for event in audit_trail)

        # Verify audit trail integrity
        assert all(event["timestamp"] is not None for event in audit_trail)
        assert all(event["user_id"] is not None for event in audit_trail)
        assert all(event["system_state_hash"] is not None for event in audit_trail)

    @pytest.mark.red
    async def test_regulatory_reporting_workflow(
        self, integrated_trading_system, market_data_stream
    ):
        """RED: Test regulatory reporting during trading workflow."""
        system, components = integrated_trading_system

        # Execute large position requiring regulatory reporting
        large_position_signal = {
            "symbol": "EUR/USD",
            "direction": "BUY",
            "position_size": 5000000,  # $5M position - reportable
            "confidence": 0.90,
        }

        components["signal_generator"].generate_signal.return_value = (
            large_position_signal
        )
        components["risk_manager"].validate_trade.return_value = {
            "approved": True,
            "position_size": 5000000,
            "regulatory_reporting_required": True,
        }
        components["order_executor"].execute_order.return_value = {
            "order_id": "LARGE_POS_001",
            "status": "FILLED",
            "filled_quantity": 5000000,
        }

        # Process large trade
        await system.process_market_data(market_data_stream["EUR/USD"][0])

        # Verify regulatory reporting was triggered
        regulatory_reports = system.get_pending_regulatory_reports()
        assert len(regulatory_reports) > 0

        large_position_report = next(
            (
                report
                for report in regulatory_reports
                if report["position_size"] >= 5000000
            ),
            None,
        )
        assert large_position_report is not None
        assert large_position_report["report_type"] == "LARGE_POSITION"
        assert large_position_report["status"] == "PENDING_SUBMISSION"
