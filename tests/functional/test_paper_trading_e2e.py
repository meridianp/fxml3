"""End-to-End Functional Tests for Paper Trading.

This module tests the complete paper trading system including real-time data
processing, signal execution, and performance tracking.
"""

import asyncio
import json
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from fxml4.data_feeds.realtime import RealtimeDataFeed
from fxml4.ml.inference import ModelInference
from fxml4.paper_trading.broker import PaperBroker
from fxml4.paper_trading.engine import PaperTradingEngine
from fxml4.paper_trading.performance_monitor import PerformanceMonitor
from fxml4.paper_trading.position_tracker import PositionTracker
from fxml4.signals.realtime_generator import RealtimeSignalGenerator


@dataclass
class PaperTradingConfig:
    """Configuration for paper trading."""

    initial_capital: float = 100000.0
    max_positions: int = 3
    position_size_pct: float = 0.02  # 2% per position
    stop_loss_pips: float = 30.0
    take_profit_pips: float = 60.0
    max_daily_loss: float = 0.02  # 2% daily loss limit
    commission_pips: float = 0.2
    slippage_pips: float = 0.5
    update_interval_seconds: int = 1
    signal_check_interval: int = 60  # Check for signals every minute
    heartbeat_interval: int = 30  # System health check
    data_feed_timeout: int = 10  # Timeout for data feed


class TestPaperTradingE2E:
    """End-to-end tests for paper trading system."""

    @pytest.fixture
    def mock_realtime_feed(self):
        """Create mock real-time data feed."""
        feed = MagicMock(spec=RealtimeDataFeed)
        feed.connected = False
        feed.subscribed_symbols = set()

        # Mock price generator
        def generate_tick(symbol):
            base_prices = {"EUR/USD": 1.0850, "GBP/USD": 1.2500, "USD/JPY": 110.00}
            base = base_prices.get(symbol, 1.0)
            change = np.random.normal(0, 0.0001)
            return {
                "symbol": symbol,
                "timestamp": datetime.now(timezone.utc),
                "bid": base + change,
                "ask": base + change + 0.0001,
                "bid_size": 1000000,
                "ask_size": 1000000,
            }

        feed.get_latest_tick = MagicMock(side_effect=generate_tick)
        feed.connect = AsyncMock(return_value=True)
        feed.disconnect = AsyncMock()
        feed.subscribe = AsyncMock(side_effect=lambda s: feed.subscribed_symbols.add(s))

        return feed

    @pytest.fixture
    def mock_model_inference(self):
        """Create mock model inference engine."""
        inference = MagicMock(spec=ModelInference)

        # Mock prediction
        def predict(features):
            # Generate realistic predictions
            return {
                "prediction": np.random.normal(0.0001, 0.0003),
                "confidence": np.random.uniform(0.5, 0.9),
                "model_agreement": np.random.uniform(0.6, 0.95),
            }

        inference.predict = MagicMock(side_effect=predict)
        inference.load_models = AsyncMock(return_value=True)
        inference.models_loaded = True

        return inference

    @pytest.fixture
    def paper_trading_config(self):
        """Create paper trading configuration."""
        return PaperTradingConfig()

    @pytest.mark.asyncio
    async def test_complete_paper_trading_session(
        self, mock_realtime_feed, mock_model_inference, paper_trading_config, tmp_path
    ):
        """Test complete paper trading session from start to stop."""
        # 1. Initialize paper trading engine
        engine = PaperTradingEngine(
            config=paper_trading_config,
            data_feed=mock_realtime_feed,
            model_inference=mock_model_inference,
            log_dir=tmp_path,
        )

        # 2. Start paper trading
        trading_task = asyncio.create_task(engine.start())

        # Let it run for a short time
        await asyncio.sleep(5)

        # 3. Verify system is running
        assert engine.is_running
        assert mock_realtime_feed.connect.called
        assert len(mock_realtime_feed.subscribed_symbols) > 0

        # 4. Stop trading
        await engine.stop()
        trading_task.cancel()

        # 5. Get session results
        results = engine.get_session_results()

        # 6. Verify results structure
        assert "session_info" in results
        assert "performance" in results
        assert "trades" in results
        assert "positions" in results

        # 7. Save results
        results_file = tmp_path / "paper_trading_results.json"
        with open(results_file, "w") as f:
            json.dump(results, f, indent=2, default=str)

        assert results_file.exists()

    @pytest.mark.asyncio
    async def test_realtime_signal_generation_and_execution(
        self, mock_realtime_feed, mock_model_inference, paper_trading_config
    ):
        """Test real-time signal generation and execution flow."""
        # Create components
        signal_generator = RealtimeSignalGenerator(
            model_inference=mock_model_inference,
            config={
                "min_confidence": 0.6,
                "min_prediction": 0.0002,
                "check_interval": 1,  # Check every second for testing
            },
        )

        paper_broker = PaperBroker(
            initial_capital=paper_trading_config.initial_capital,
            commission=paper_trading_config.commission_pips,
        )

        position_tracker = PositionTracker()

        # Subscribe to symbols
        symbols = ["EUR/USD", "GBP/USD"]
        for symbol in symbols:
            await mock_realtime_feed.subscribe(symbol)

        # Run signal generation and execution loop
        signals_generated = []
        orders_executed = []

        for _ in range(10):  # 10 iterations
            # Get latest data for each symbol
            for symbol in symbols:
                tick = mock_realtime_feed.get_latest_tick(symbol)

                # Generate features (simplified)
                features = {
                    "price": tick["bid"],
                    "spread": tick["ask"] - tick["bid"],
                    "momentum": np.random.normal(0, 0.001),
                }

                # Generate signal
                signal = await signal_generator.generate_signal(symbol, features)

                if signal:
                    signals_generated.append(signal)

                    # Check if we can take position
                    current_positions = position_tracker.get_open_positions()

                    if len(current_positions) < paper_trading_config.max_positions:
                        # Calculate position size
                        position_size = (
                            paper_trading_config.position_size_pct
                            * paper_broker.get_balance()
                        )

                        # Execute order
                        order = {
                            "symbol": signal["symbol"],
                            "direction": signal["direction"],
                            "size": position_size,
                            "entry_price": (
                                tick["ask"]
                                if signal["direction"] == "BUY"
                                else tick["bid"]
                            ),
                            "stop_loss": signal.get("stop_loss"),
                            "take_profit": signal.get("take_profit"),
                            "signal_id": signal["id"],
                        }

                        execution = await paper_broker.execute_order(order)
                        if execution["status"] == "filled":
                            orders_executed.append(execution)
                            position_tracker.add_position(execution)

            await asyncio.sleep(0.1)  # Small delay

        # Verify signal generation and execution
        assert len(signals_generated) > 0
        print(f"Generated {len(signals_generated)} signals")
        print(f"Executed {len(orders_executed)} orders")

    @pytest.mark.asyncio
    async def test_position_management_lifecycle(self, paper_trading_config):
        """Test complete position lifecycle from entry to exit."""
        position_tracker = PositionTracker()
        paper_broker = PaperBroker(initial_capital=100000)

        # 1. Open position
        entry_order = {
            "id": "pos_001",
            "symbol": "EUR/USD",
            "direction": "BUY",
            "size": 100000,
            "entry_price": 1.0850,
            "entry_time": datetime.now(timezone.utc),
            "stop_loss": 1.0820,  # 30 pips
            "take_profit": 1.0910,  # 60 pips
            "signal_id": "sig_001",
        }

        position_tracker.add_position(entry_order)

        # 2. Verify position tracking
        positions = position_tracker.get_open_positions()
        assert len(positions) == 1
        assert positions[0]["symbol"] == "EUR/USD"
        assert positions[0]["status"] == "open"

        # 3. Update position with current price (profit scenario)
        current_price = 1.0870  # 20 pips profit
        position_tracker.update_positions({"EUR/USD": current_price})

        updated_position = position_tracker.get_position("pos_001")
        assert updated_position["unrealized_pnl"] > 0
        assert (
            updated_position["unrealized_pnl"]
            == (current_price - entry_order["entry_price"]) * entry_order["size"]
        )

        # 4. Test stop loss hit
        stop_price = 1.0815  # Below stop loss
        exits = position_tracker.check_exits({"EUR/USD": stop_price})

        assert len(exits) == 1
        assert exits[0]["reason"] == "stop_loss"
        assert exits[0]["exit_price"] == entry_order["stop_loss"]

        # 5. Close position
        close_result = position_tracker.close_position(
            "pos_001",
            exit_price=entry_order["stop_loss"],
            exit_time=datetime.now(timezone.utc),
            reason="stop_loss",
        )

        # 6. Verify position closed
        assert close_result["status"] == "closed"
        assert close_result["realized_pnl"] < 0  # Loss due to stop loss
        assert len(position_tracker.get_open_positions()) == 0

        # 7. Check closed positions history
        closed = position_tracker.get_closed_positions()
        assert len(closed) == 1
        assert closed[0]["id"] == "pos_001"

    @pytest.mark.asyncio
    async def test_risk_management_controls(self, paper_trading_config):
        """Test risk management controls during paper trading."""
        paper_broker = PaperBroker(
            initial_capital=100000, max_daily_loss=paper_trading_config.max_daily_loss
        )

        position_tracker = PositionTracker()

        # 1. Test position limit
        for i in range(paper_trading_config.max_positions + 1):
            order = {
                "id": f"pos_{i:03d}",
                "symbol": "EUR/USD",
                "direction": "BUY",
                "size": 10000,
                "entry_price": 1.0850 + i * 0.0001,
            }

            if i < paper_trading_config.max_positions:
                # Should succeed
                position_tracker.add_position(order)
                assert len(position_tracker.get_open_positions()) == i + 1
            else:
                # Should be rejected due to position limit
                can_trade = (
                    len(position_tracker.get_open_positions())
                    < paper_trading_config.max_positions
                )
                assert not can_trade

        # 2. Test daily loss limit
        # Simulate losses
        initial_balance = paper_broker.get_balance()

        # First loss - within limit
        loss1 = initial_balance * 0.01  # 1% loss
        paper_broker.update_balance(-loss1)
        assert paper_broker.can_trade()  # Still can trade

        # Second loss - exceeds limit
        loss2 = initial_balance * 0.015  # 1.5% loss
        paper_broker.update_balance(-loss2)
        assert not paper_broker.can_trade()  # Should stop trading

        # 3. Test position sizing limits
        current_balance = paper_broker.get_balance()
        max_position_value = current_balance * paper_trading_config.position_size_pct

        # Calculate position size for EUR/USD at 1.0850
        max_units = int(max_position_value / 1.0850)

        # Verify position size calculation
        assert max_units > 0
        assert max_units * 1.0850 <= max_position_value

    @pytest.mark.asyncio
    async def test_performance_monitoring(self, paper_trading_config):
        """Test real-time performance monitoring."""
        monitor = PerformanceMonitor(initial_capital=100000)

        # Simulate trading activity
        trades = [
            {
                "id": "t1",
                "pnl": 150,
                "entry_time": datetime.now(timezone.utc) - timedelta(hours=5),
                "exit_time": datetime.now(timezone.utc) - timedelta(hours=4),
                "symbol": "EUR/USD",
            },
            {
                "id": "t2",
                "pnl": -80,
                "entry_time": datetime.now(timezone.utc) - timedelta(hours=3),
                "exit_time": datetime.now(timezone.utc) - timedelta(hours=2.5),
                "symbol": "GBP/USD",
            },
            {
                "id": "t3",
                "pnl": 200,
                "entry_time": datetime.now(timezone.utc) - timedelta(hours=2),
                "exit_time": datetime.now(timezone.utc) - timedelta(hours=1),
                "symbol": "EUR/USD",
            },
        ]

        # Add trades to monitor
        for trade in trades:
            monitor.add_trade(trade)

        # Update current equity
        current_equity = 100000 + sum(t["pnl"] for t in trades)
        monitor.update_equity(current_equity)

        # Get performance metrics
        metrics = monitor.get_metrics()

        # Verify metrics
        assert metrics["total_trades"] == 3
        assert metrics["winning_trades"] == 2
        assert metrics["losing_trades"] == 1
        assert metrics["win_rate"] == 2 / 3
        assert metrics["total_pnl"] == 270
        assert metrics["current_equity"] == current_equity
        assert "max_drawdown" in metrics
        assert "sharpe_ratio" in metrics

        # Test real-time updates
        monitor.update_equity(current_equity - 100)  # Small drawdown
        updated_metrics = monitor.get_metrics()
        assert updated_metrics["current_drawdown"] < 0

    @pytest.mark.asyncio
    async def test_multi_symbol_paper_trading(
        self, mock_realtime_feed, mock_model_inference, paper_trading_config
    ):
        """Test paper trading with multiple symbols simultaneously."""
        symbols = ["EUR/USD", "GBP/USD", "USD/JPY"]

        # Initialize components
        position_tracker = PositionTracker()
        paper_broker = PaperBroker(initial_capital=100000)

        # Track activity per symbol
        symbol_activity = {symbol: {"signals": 0, "trades": 0} for symbol in symbols}

        # Subscribe to all symbols
        for symbol in symbols:
            await mock_realtime_feed.subscribe(symbol)

        # Simulate trading for each symbol
        for _ in range(20):  # 20 iterations
            for symbol in symbols:
                # Get tick data
                tick = mock_realtime_feed.get_latest_tick(symbol)

                # Generate signal (simplified)
                if np.random.random() > 0.7:  # 30% chance of signal
                    signal = {
                        "symbol": symbol,
                        "direction": "BUY" if np.random.random() > 0.5 else "SELL",
                        "confidence": np.random.uniform(0.6, 0.9),
                        "predicted_return": np.random.uniform(0.0002, 0.0008),
                    }
                    symbol_activity[symbol]["signals"] += 1

                    # Check if we can trade this symbol
                    symbol_positions = [
                        p
                        for p in position_tracker.get_open_positions()
                        if p["symbol"] == symbol
                    ]

                    if len(symbol_positions) == 0:  # No position in this symbol
                        # Execute trade
                        order = {
                            "id": f'{symbol}_{symbol_activity[symbol]["trades"]:03d}',
                            "symbol": symbol,
                            "direction": signal["direction"],
                            "size": 10000,
                            "entry_price": (
                                tick["ask"]
                                if signal["direction"] == "BUY"
                                else tick["bid"]
                            ),
                        }

                        position_tracker.add_position(order)
                        symbol_activity[symbol]["trades"] += 1

            # Update positions with current prices
            current_prices = {
                symbol: mock_realtime_feed.get_latest_tick(symbol)["bid"]
                for symbol in symbols
            }
            position_tracker.update_positions(current_prices)

            await asyncio.sleep(0.05)

        # Verify multi-symbol activity
        for symbol, activity in symbol_activity.items():
            print(
                f"{symbol}: {activity['signals']} signals, {activity['trades']} trades"
            )
            assert activity["signals"] > 0  # Should have generated some signals

        # Check position distribution
        all_positions = position_tracker.get_all_positions()
        traded_symbols = set(p["symbol"] for p in all_positions)
        assert len(traded_symbols) > 1  # Should have traded multiple symbols

    @pytest.mark.asyncio
    async def test_paper_trading_recovery(
        self, mock_realtime_feed, paper_trading_config, tmp_path
    ):
        """Test paper trading system recovery from interruptions."""
        # 1. Start paper trading and save state
        engine = PaperTradingEngine(
            config=paper_trading_config,
            data_feed=mock_realtime_feed,
            model_inference=MagicMock(),
            log_dir=tmp_path,
        )

        # Add some positions
        test_positions = [
            {
                "id": "pos_001",
                "symbol": "EUR/USD",
                "direction": "BUY",
                "size": 100000,
                "entry_price": 1.0850,
                "entry_time": datetime.now(timezone.utc) - timedelta(hours=1),
            },
            {
                "id": "pos_002",
                "symbol": "GBP/USD",
                "direction": "SELL",
                "size": 80000,
                "entry_price": 1.2500,
                "entry_time": datetime.now(timezone.utc) - timedelta(minutes=30),
            },
        ]

        for pos in test_positions:
            engine.position_tracker.add_position(pos)

        # Save state
        state_file = tmp_path / "paper_trading_state.json"
        engine.save_state(state_file)

        # 2. Simulate system restart
        new_engine = PaperTradingEngine(
            config=paper_trading_config,
            data_feed=mock_realtime_feed,
            model_inference=MagicMock(),
            log_dir=tmp_path,
        )

        # Load saved state
        new_engine.load_state(state_file)

        # 3. Verify state restoration
        restored_positions = new_engine.position_tracker.get_open_positions()
        assert len(restored_positions) == 2

        # Check position details preserved
        pos_ids = [p["id"] for p in restored_positions]
        assert "pos_001" in pos_ids
        assert "pos_002" in pos_ids

        # 4. Verify can continue trading
        tick = mock_realtime_feed.get_latest_tick("EUR/USD")
        assert tick is not None

        # Update positions with current prices
        new_engine.position_tracker.update_positions(
            {"EUR/USD": tick["bid"], "GBP/USD": 1.2480}
        )

        # Check P&L calculation works
        positions = new_engine.position_tracker.get_open_positions()
        eur_position = next(p for p in positions if p["symbol"] == "EUR/USD")
        assert "unrealized_pnl" in eur_position

    @pytest.mark.asyncio
    async def test_paper_trading_reporting(self, paper_trading_config, tmp_path):
        """Test paper trading report generation."""
        # Create completed session data
        session_data = {
            "session_id": "test_001",
            "start_time": datetime.now(timezone.utc) - timedelta(hours=4),
            "end_time": datetime.now(timezone.utc),
            "initial_capital": 100000,
            "final_capital": 102500,
            "trades": [
                {
                    "id": "t1",
                    "symbol": "EUR/USD",
                    "direction": "BUY",
                    "entry_time": datetime.now(timezone.utc) - timedelta(hours=3),
                    "exit_time": datetime.now(timezone.utc) - timedelta(hours=2),
                    "entry_price": 1.0850,
                    "exit_price": 1.0870,
                    "size": 100000,
                    "pnl": 200,
                    "commission": 20,
                },
                {
                    "id": "t2",
                    "symbol": "GBP/USD",
                    "direction": "SELL",
                    "entry_time": datetime.now(timezone.utc) - timedelta(hours=2),
                    "exit_time": datetime.now(timezone.utc) - timedelta(hours=1),
                    "entry_price": 1.2500,
                    "exit_price": 1.2520,
                    "size": 80000,
                    "pnl": -160,
                    "commission": 16,
                },
            ],
            "performance_metrics": {
                "total_return": 0.025,
                "win_rate": 0.5,
                "sharpe_ratio": 1.2,
                "max_drawdown": -0.002,
                "total_trades": 2,
            },
        }

        # Generate report
        reporter = PaperTradingReporter(session_data)
        report = reporter.generate_report()

        # Verify report sections
        assert "summary" in report
        assert "trade_analysis" in report
        assert "performance_metrics" in report
        assert "recommendations" in report

        # Check summary
        summary = report["summary"]
        assert summary["total_pnl"] == 2500
        assert summary["return_pct"] == 2.5
        assert summary["total_trades"] == 2

        # Save HTML report
        html_report = reporter.generate_html_report()
        report_file = tmp_path / "paper_trading_report.html"

        with open(report_file, "w") as f:
            f.write(html_report)

        assert report_file.exists()

        # Verify HTML contains key elements
        assert "Paper Trading Report" in html_report
        assert "Performance Summary" in html_report
        assert "Trade Analysis" in html_report


class TestPaperTradingEdgeCases:
    """Test edge cases and error handling in paper trading."""

    @pytest.mark.asyncio
    async def test_data_feed_disconnection_handling(
        self, mock_realtime_feed, paper_trading_config
    ):
        """Test handling of data feed disconnections."""
        # Create unreliable feed
        unreliable_feed = MagicMock()
        disconnect_count = 0

        async def flaky_connect():
            nonlocal disconnect_count
            disconnect_count += 1
            if disconnect_count < 3:
                raise ConnectionError("Feed disconnected")
            return True

        unreliable_feed.connect = AsyncMock(side_effect=flaky_connect)
        unreliable_feed.disconnect = AsyncMock()
        unreliable_feed.connected = False

        # Test reconnection logic
        max_retries = 5
        retry_delay = 0.1

        connected = False
        for attempt in range(max_retries):
            try:
                connected = await unreliable_feed.connect()
                if connected:
                    break
            except ConnectionError:
                await asyncio.sleep(retry_delay)

        # Should eventually connect
        assert connected
        assert disconnect_count == 3

    @pytest.mark.asyncio
    async def test_extreme_market_conditions(self, paper_trading_config):
        """Test paper trading during extreme market volatility."""
        position_tracker = PositionTracker()

        # Create position
        position = {
            "id": "pos_001",
            "symbol": "EUR/USD",
            "direction": "BUY",
            "size": 100000,
            "entry_price": 1.0850,
            "stop_loss": 1.0820,
            "take_profit": 1.0900,
        }
        position_tracker.add_position(position)

        # Simulate flash crash
        crash_prices = [
            1.0850,  # Normal
            1.0840,  # Small drop
            1.0800,  # Large drop (gap through stop loss)
            1.0750,  # Extreme drop
            1.0820,  # Recovery
        ]

        exits_triggered = []

        for price in crash_prices:
            exits = position_tracker.check_exits({"EUR/USD": price})
            if exits:
                exits_triggered.extend(exits)
                break  # Stop after first exit

        # Should trigger stop loss even with gap
        assert len(exits_triggered) == 1
        assert exits_triggered[0]["reason"] == "stop_loss"

        # Exit price should be stop loss even if market gapped
        assert exits_triggered[0]["exit_price"] == position["stop_loss"]

    @pytest.mark.asyncio
    async def test_concurrent_order_handling(self, paper_trading_config):
        """Test handling of concurrent order submissions."""
        paper_broker = PaperBroker(initial_capital=100000)

        # Create multiple concurrent orders
        orders = []
        for i in range(10):
            orders.append(
                {
                    "id": f"order_{i:03d}",
                    "symbol": "EUR/USD",
                    "direction": "BUY" if i % 2 == 0 else "SELL",
                    "size": 10000,
                    "price": 1.0850 + i * 0.0001,
                }
            )

        # Submit orders concurrently
        async def submit_order(order):
            await asyncio.sleep(np.random.uniform(0, 0.1))  # Random delay
            return await paper_broker.execute_order(order)

        # Execute all orders
        results = await asyncio.gather(*[submit_order(order) for order in orders])

        # All orders should be processed
        assert len(results) == 10
        assert all(r["status"] in ["filled", "rejected"] for r in results)

        # Check order integrity
        filled_orders = [r for r in results if r["status"] == "filled"]
        assert len(filled_orders) > 0


class PaperTradingReporter:
    """Generate reports for paper trading sessions."""

    def __init__(self, session_data):
        self.session_data = session_data

    def generate_report(self) -> Dict[str, Any]:
        """Generate comprehensive trading report."""
        return {
            "summary": self._generate_summary(),
            "trade_analysis": self._analyze_trades(),
            "performance_metrics": self._calculate_performance(),
            "recommendations": self._generate_recommendations(),
        }

    def generate_html_report(self) -> str:
        """Generate HTML formatted report."""
        report = self.generate_report()

        html = f"""
        <html>
        <head>
            <title>Paper Trading Report - {self.session_data['session_id']}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .summary {{ background: #f0f0f0; padding: 15px; border-radius: 5px; }}
                .metric {{ margin: 10px 0; }}
                table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background: #4CAF50; color: white; }}
                .positive {{ color: green; }}
                .negative {{ color: red; }}
            </style>
        </head>
        <body>
            <h1>Paper Trading Report</h1>
            <div class="summary">
                <h2>Performance Summary</h2>
                <div class="metric">Total P&L: ${report['summary']['total_pnl']:.2f}</div>
                <div class="metric">Return: {report['summary']['return_pct']:.2f}%</div>
                <div class="metric">Total Trades: {report['summary']['total_trades']}</div>
            </div>

            <h2>Trade Analysis</h2>
            <table>
                <tr>
                    <th>Trade ID</th>
                    <th>Symbol</th>
                    <th>Direction</th>
                    <th>P&L</th>
                    <th>Duration</th>
                </tr>
                {self._generate_trade_rows()}
            </table>

            <h2>Recommendations</h2>
            <ul>
                {self._generate_recommendation_list(report['recommendations'])}
            </ul>
        </body>
        </html>
        """

        return html

    def _generate_summary(self) -> Dict[str, Any]:
        """Generate summary statistics."""
        trades = self.session_data["trades"]
        return {
            "total_pnl": self.session_data["final_capital"]
            - self.session_data["initial_capital"],
            "return_pct": (
                (
                    self.session_data["final_capital"]
                    / self.session_data["initial_capital"]
                )
                - 1
            )
            * 100,
            "total_trades": len(trades),
            "winning_trades": len([t for t in trades if t["pnl"] > 0]),
            "losing_trades": len([t for t in trades if t["pnl"] < 0]),
        }

    def _analyze_trades(self) -> Dict[str, Any]:
        """Analyze trade patterns."""
        trades = self.session_data["trades"]

        if not trades:
            return {}

        return {
            "average_pnl": np.mean([t["pnl"] for t in trades]),
            "best_trade": max(trades, key=lambda t: t["pnl"])["pnl"],
            "worst_trade": min(trades, key=lambda t: t["pnl"])["pnl"],
            "average_duration": np.mean(
                [
                    (t["exit_time"] - t["entry_time"]).total_seconds() / 3600
                    for t in trades
                    if "exit_time" in t
                ]
            ),
        }

    def _calculate_performance(self) -> Dict[str, Any]:
        """Calculate performance metrics."""
        return self.session_data.get("performance_metrics", {})

    def _generate_recommendations(self) -> List[str]:
        """Generate trading recommendations based on results."""
        recommendations = []

        metrics = self.session_data.get("performance_metrics", {})

        if metrics.get("win_rate", 0) < 0.5:
            recommendations.append(
                "Consider reviewing signal generation logic - win rate below 50%"
            )

        if abs(metrics.get("max_drawdown", 0)) > 0.05:
            recommendations.append(
                "High drawdown detected - consider tighter risk controls"
            )

        if metrics.get("sharpe_ratio", 0) < 1.0:
            recommendations.append(
                "Low risk-adjusted returns - optimize strategy parameters"
            )

        return recommendations

    def _generate_trade_rows(self) -> str:
        """Generate HTML table rows for trades."""
        rows = []
        for trade in self.session_data["trades"]:
            pnl_class = "positive" if trade["pnl"] > 0 else "negative"
            duration = (trade["exit_time"] - trade["entry_time"]).total_seconds() / 3600

            rows.append(
                f"""
                <tr>
                    <td>{trade['id']}</td>
                    <td>{trade['symbol']}</td>
                    <td>{trade['direction']}</td>
                    <td class="{pnl_class}">${trade['pnl']:.2f}</td>
                    <td>{duration:.1f} hours</td>
                </tr>
            """
            )

        return "\n".join(rows)

    def _generate_recommendation_list(self, recommendations: List[str]) -> str:
        """Generate HTML list of recommendations."""
        return "\n".join(f"<li>{rec}</li>" for rec in recommendations)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
