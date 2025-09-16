"""End-to-End Functional Tests for Backtesting Framework.

This module tests the complete backtesting pipeline including event-driven
simulation, portfolio management, and performance calculation.
"""

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from fxml4.backtesting.data_handler import HistoricalDataHandler
from fxml4.backtesting.engine import BacktestEngine
from fxml4.backtesting.event import (
    Event,
    EventType,
    FillEvent,
    MarketEvent,
    OrderEvent,
    SignalEvent,
)
from fxml4.backtesting.execution import SimulatedExecutionHandler
from fxml4.backtesting.performance import PerformanceCalculator
from fxml4.backtesting.portfolio import Portfolio
from fxml4.backtesting.risk_manager import RiskManager
from fxml4.backtesting.strategy import Strategy


@dataclass
class BacktestConfig:
    """Configuration for backtesting."""

    initial_capital: float = 100000.0
    commission: float = 0.0002  # 2 pips per trade
    slippage_model: str = "fixed"  # or 'variable'
    slippage_pips: float = 0.5
    max_positions: int = 3
    position_sizing: str = "fixed"  # or 'risk_based'
    position_size: float = 0.01  # 1% per trade
    stop_loss_pips: float = 50.0
    take_profit_pips: float = 100.0
    risk_per_trade: float = 0.01  # 1% risk per trade


class TestBacktestingE2E:
    """End-to-end tests for backtesting framework."""

    @pytest.fixture
    def sample_market_data(self):
        """Create sample market data for backtesting."""
        dates = pd.date_range(start="2024-01-01", periods=1000, freq="1h", tz="UTC")

        # Generate realistic price data
        np.random.seed(42)
        prices = []
        current_price = 1.0850

        for _ in range(len(dates)):
            change = np.random.normal(0, 0.0005)
            current_price *= 1 + change
            prices.append(current_price)

        data = {}
        for symbol in ["EUR/USD", "GBP/USD"]:
            if symbol == "GBP/USD":
                symbol_prices = [p * 1.15 for p in prices]  # Adjust for GBP
            else:
                symbol_prices = prices

            df = pd.DataFrame(
                {
                    "open": [
                        p * (1 + np.random.uniform(-0.0002, 0.0002))
                        for p in symbol_prices
                    ],
                    "high": [
                        p * (1 + np.random.uniform(0, 0.0003)) for p in symbol_prices
                    ],
                    "low": [
                        p * (1 - np.random.uniform(0, 0.0003)) for p in symbol_prices
                    ],
                    "close": symbol_prices,
                    "volume": np.random.randint(10000, 100000, len(dates)),
                    "spread": np.random.uniform(0.0001, 0.0003, len(dates)),
                },
                index=dates,
            )

            # Ensure OHLC consistency
            df["high"] = df[["open", "high", "close"]].max(axis=1)
            df["low"] = df[["open", "low", "close"]].min(axis=1)

            data[symbol] = df

        return data

    @pytest.fixture
    def sample_signals(self):
        """Create sample trading signals."""
        signals = []
        base_time = datetime(2024, 1, 2, 9, 0, tzinfo=timezone.utc)

        # Generate diverse signals
        signal_configs = [
            # (hours_offset, symbol, direction, confidence, predicted_return)
            (0, "EUR/USD", "BUY", 0.75, 0.0005),
            (2, "EUR/USD", "SELL", 0.65, -0.0003),
            (5, "GBP/USD", "BUY", 0.80, 0.0006),
            (8, "EUR/USD", "BUY", 0.70, 0.0004),
            (12, "GBP/USD", "SELL", 0.72, -0.0005),
            (15, "EUR/USD", "SELL", 0.68, -0.0004),
            (20, "GBP/USD", "BUY", 0.77, 0.0005),
            (24, "EUR/USD", "BUY", 0.82, 0.0007),
        ]

        for hours, symbol, direction, confidence, pred_return in signal_configs:
            signals.append(
                {
                    "timestamp": base_time + timedelta(hours=hours),
                    "symbol": symbol,
                    "direction": direction,
                    "confidence": confidence,
                    "predicted_return": pred_return,
                    "signal_id": f"sig_{hours:03d}",
                }
            )

        return signals

    @pytest.mark.asyncio
    async def test_complete_backtest_workflow(
        self, sample_market_data, sample_signals, tmp_path
    ):
        """Test complete backtesting workflow from data to results."""
        config = BacktestConfig()

        # 1. Initialize backtest engine
        engine = BacktestEngine(
            initial_capital=config.initial_capital,
            data_handler=HistoricalDataHandler(sample_market_data),
            execution_handler=SimulatedExecutionHandler(
                commission=config.commission, slippage_pips=config.slippage_pips
            ),
            portfolio=Portfolio(initial_capital=config.initial_capital),
            strategy=MockStrategy(sample_signals),
            risk_manager=RiskManager(config),
        )

        # 2. Run backtest
        results = await engine.run_backtest(
            start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 1, 10, tzinfo=timezone.utc),
        )

        # 3. Verify execution
        assert results is not None
        assert "trades" in results
        assert "performance" in results
        assert "equity_curve" in results

        # 4. Check trade execution
        trades = results["trades"]
        assert len(trades) > 0

        # Verify trade structure
        for trade in trades:
            assert "entry_time" in trade
            assert "exit_time" in trade or trade["status"] == "open"
            assert "symbol" in trade
            assert "direction" in trade
            assert "entry_price" in trade
            assert "size" in trade
            assert "pnl" in trade or trade["status"] == "open"

        # 5. Verify performance metrics
        performance = results["performance"]
        assert "total_return" in performance
        assert "sharpe_ratio" in performance
        assert "max_drawdown" in performance
        assert "win_rate" in performance
        assert "profit_factor" in performance

        # 6. Save results
        results_file = tmp_path / "backtest_results.json"
        with open(results_file, "w") as f:
            json.dump(results, f, indent=2, default=str)

        assert results_file.exists()

    @pytest.mark.asyncio
    async def test_event_driven_simulation(self, sample_market_data):
        """Test event-driven architecture of backtesting."""
        events_processed = []

        # Create event queue
        event_queue = asyncio.Queue()

        # Create simple strategy that records events
        class EventRecordingStrategy(Strategy):
            async def calculate_signals(
                self, event: MarketEvent
            ) -> Optional[SignalEvent]:
                events_processed.append(("market", event.timestamp))

                # Generate signal occasionally
                if np.random.random() > 0.8:
                    return SignalEvent(
                        timestamp=event.timestamp,
                        symbol=event.symbol,
                        signal_type="BUY" if np.random.random() > 0.5 else "SELL",
                        strength=np.random.uniform(0.6, 0.9),
                    )
                return None

        # Initialize components
        data_handler = HistoricalDataHandler(sample_market_data)
        strategy = EventRecordingStrategy()
        portfolio = Portfolio(initial_capital=100000)
        execution = SimulatedExecutionHandler()

        # Process first 50 bars
        for i in range(50):
            # Generate market events
            market_events = data_handler.get_latest_bars(["EUR/USD", "GBP/USD"])

            for symbol, bar_data in market_events.items():
                if bar_data is not None:
                    market_event = MarketEvent(
                        timestamp=bar_data.name, symbol=symbol, data=bar_data
                    )

                    # Process through strategy
                    signal_event = await strategy.calculate_signals(market_event)

                    if signal_event:
                        events_processed.append(("signal", signal_event.timestamp))

                        # Generate order
                        order_event = OrderEvent(
                            timestamp=signal_event.timestamp,
                            symbol=signal_event.symbol,
                            order_type="MARKET",
                            quantity=10000,
                            direction=signal_event.signal_type,
                        )
                        events_processed.append(("order", order_event.timestamp))

                        # Simulate fill
                        fill_event = FillEvent(
                            timestamp=order_event.timestamp,
                            symbol=order_event.symbol,
                            exchange="SIMULATED",
                            quantity=order_event.quantity,
                            direction=order_event.direction,
                            fill_cost=bar_data["close"] * order_event.quantity,
                            commission=0.0002,
                        )
                        events_processed.append(("fill", fill_event.timestamp))

                        # Update portfolio
                        portfolio.update_fill(fill_event)

            # Move to next bar
            data_handler.update_bars()

        # Verify event flow
        assert len(events_processed) > 0

        # Check event sequence
        event_types = [e[0] for e in events_processed]
        assert "market" in event_types

        # If signals generated, check proper sequence
        if "signal" in event_types:
            first_signal_idx = event_types.index("signal")
            # Should have market event before signal
            assert event_types[first_signal_idx - 1] == "market"

    @pytest.mark.asyncio
    async def test_portfolio_management(self, sample_market_data):
        """Test portfolio tracking and position management."""
        portfolio = Portfolio(initial_capital=100000)

        # Test position opening
        fill1 = FillEvent(
            timestamp=datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc),
            symbol="EUR/USD",
            exchange="SIMULATED",
            quantity=100000,
            direction="BUY",
            fill_cost=108500,  # 1.085 * 100000
            commission=20,
        )

        portfolio.update_fill(fill1)

        # Verify position
        positions = portfolio.get_positions()
        assert "EUR/USD" in positions
        assert positions["EUR/USD"]["quantity"] == 100000
        assert positions["EUR/USD"]["direction"] == "BUY"

        # Test P&L calculation with price update
        current_prices = {"EUR/USD": 1.0860}
        portfolio.update_prices(current_prices)

        pnl = portfolio.get_unrealized_pnl()
        assert pnl["EUR/USD"] == 100  # (1.086 - 1.085) * 100000

        # Test position closing
        fill2 = FillEvent(
            timestamp=datetime(2024, 1, 1, 14, 0, tzinfo=timezone.utc),
            symbol="EUR/USD",
            exchange="SIMULATED",
            quantity=100000,
            direction="SELL",
            fill_cost=108600,
            commission=20,
        )

        portfolio.update_fill(fill2)

        # Position should be closed
        positions = portfolio.get_positions()
        assert "EUR/USD" not in positions or positions["EUR/USD"]["quantity"] == 0

        # Check realized P&L
        realized_pnl = portfolio.get_realized_pnl()
        assert realized_pnl > 0  # Should have profit minus commissions

    @pytest.mark.asyncio
    async def test_execution_simulation(self, sample_market_data):
        """Test order execution with slippage and commission."""
        execution_handler = SimulatedExecutionHandler(
            commission=0.0002,  # 2 pips
            slippage_model="variable",
            max_slippage_pips=2.0,
        )

        # Test market order execution
        market_order = OrderEvent(
            timestamp=datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc),
            symbol="EUR/USD",
            order_type="MARKET",
            quantity=100000,
            direction="BUY",
        )

        current_price = 1.0850
        fill = execution_handler.execute_order(
            market_order,
            current_price=current_price,
            spread=0.0002,
            volume=50000,  # Half the order size - may impact slippage
        )

        # Verify fill
        assert fill.symbol == market_order.symbol
        assert fill.quantity == market_order.quantity
        assert fill.direction == market_order.direction

        # Check slippage applied
        expected_price = current_price + 0.0002  # Add spread for buy
        assert fill.fill_cost >= expected_price * fill.quantity

        # Test limit order execution
        limit_order = OrderEvent(
            timestamp=datetime(2024, 1, 1, 11, 0, tzinfo=timezone.utc),
            symbol="EUR/USD",
            order_type="LIMIT",
            quantity=100000,
            direction="SELL",
            price=1.0855,
        )

        # Should not fill if price not reached
        fill = execution_handler.execute_order(
            limit_order, current_price=1.0852, spread=0.0002
        )
        assert fill is None  # No fill

        # Should fill when price reached
        fill = execution_handler.execute_order(
            limit_order, current_price=1.0856, spread=0.0002
        )
        assert fill is not None
        assert fill.fill_cost == limit_order.price * limit_order.quantity

    @pytest.mark.asyncio
    async def test_risk_management_controls(self, sample_market_data):
        """Test risk management during backtesting."""
        config = BacktestConfig(
            max_positions=2,
            position_size=0.02,  # 2% per trade
            stop_loss_pips=30,
            risk_per_trade=0.01,  # 1% risk
        )

        risk_manager = RiskManager(config)
        portfolio = Portfolio(initial_capital=100000)

        # Test position limit
        can_trade = risk_manager.check_position_limit(
            current_positions={"EUR/USD": {}, "GBP/USD": {}}, new_symbol="USD/JPY"
        )
        assert not can_trade  # Should reject - at position limit

        # Test position sizing
        position_size = risk_manager.calculate_position_size(
            account_balance=100000, stop_loss_pips=30, price=1.0850
        )

        # With 1% risk and 30 pip stop, position size should be calculated
        # Risk amount = 100000 * 0.01 = 1000
        # Position size = 1000 / (30 * 0.0001) = 333,333
        assert 300000 < position_size < 350000

        # Test drawdown limit
        portfolio.equity_curve = [100000, 98000, 96000, 94000]  # 6% drawdown

        can_continue = risk_manager.check_drawdown_limit(
            equity_curve=portfolio.equity_curve, max_drawdown=0.05  # 5% limit
        )
        assert not can_continue  # Should stop - exceeded drawdown

    @pytest.mark.asyncio
    async def test_performance_calculation(self, sample_market_data):
        """Test comprehensive performance metric calculation."""
        # Create sample trade results
        trades = [
            {"pnl": 150, "return": 0.0015},
            {"pnl": -80, "return": -0.0008},
            {"pnl": 200, "return": 0.002},
            {"pnl": -50, "return": -0.0005},
            {"pnl": 300, "return": 0.003},
            {"pnl": -120, "return": -0.0012},
            {"pnl": 180, "return": 0.0018},
            {"pnl": 90, "return": 0.0009},
        ]

        equity_curve = [100000]
        for trade in trades:
            equity_curve.append(equity_curve[-1] + trade["pnl"])

        calculator = PerformanceCalculator()
        metrics = calculator.calculate_metrics(
            trades=trades, equity_curve=equity_curve, initial_capital=100000
        )

        # Verify basic metrics
        assert metrics["total_trades"] == 8
        assert metrics["winning_trades"] == 5
        assert metrics["losing_trades"] == 3
        assert metrics["win_rate"] == 5 / 8

        # Verify return metrics
        total_pnl = sum(t["pnl"] for t in trades)
        assert abs(metrics["total_pnl"] - total_pnl) < 0.01
        assert abs(metrics["total_return"] - total_pnl / 100000) < 0.0001

        # Verify risk metrics
        assert "sharpe_ratio" in metrics
        assert "sortino_ratio" in metrics
        assert "max_drawdown" in metrics
        assert metrics["max_drawdown"] < 0  # Should be negative

        # Verify trade statistics
        assert metrics["average_win"] == 184  # (150+200+300+180+90)/5
        assert metrics["average_loss"] == -83.33  # (-80-50-120)/3
        assert metrics["profit_factor"] > 1  # Profitable system

    @pytest.mark.asyncio
    async def test_multi_symbol_backtesting(self, sample_market_data, sample_signals):
        """Test backtesting with multiple symbols."""
        config = BacktestConfig()

        # Filter signals for multiple symbols
        multi_symbol_signals = [
            s for s in sample_signals if s["symbol"] in ["EUR/USD", "GBP/USD"]
        ]

        # Run backtest
        engine = BacktestEngine(
            initial_capital=config.initial_capital,
            data_handler=HistoricalDataHandler(sample_market_data),
            execution_handler=SimulatedExecutionHandler(config.commission),
            portfolio=Portfolio(initial_capital=config.initial_capital),
            strategy=MockStrategy(multi_symbol_signals),
            risk_manager=RiskManager(config),
        )

        results = await engine.run_backtest(
            start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 1, 5, tzinfo=timezone.utc),
        )

        # Verify multi-symbol execution
        trades = results["trades"]
        traded_symbols = set(t["symbol"] for t in trades)

        assert len(traded_symbols) > 1  # Should trade multiple symbols
        assert "EUR/USD" in traded_symbols
        assert "GBP/USD" in traded_symbols

        # Check position management across symbols
        symbol_performance = {}
        for trade in trades:
            symbol = trade["symbol"]
            if symbol not in symbol_performance:
                symbol_performance[symbol] = {"trades": 0, "pnl": 0}
            symbol_performance[symbol]["trades"] += 1
            symbol_performance[symbol]["pnl"] += trade.get("pnl", 0)

        # Each symbol should have trades
        for symbol, perf in symbol_performance.items():
            assert perf["trades"] > 0

    @pytest.mark.asyncio
    async def test_stop_loss_take_profit(self, sample_market_data):
        """Test stop loss and take profit execution."""
        config = BacktestConfig(stop_loss_pips=20, take_profit_pips=40)

        portfolio = Portfolio(initial_capital=100000)

        # Open position
        entry_price = 1.0850
        position = {
            "symbol": "EUR/USD",
            "direction": "BUY",
            "quantity": 100000,
            "entry_price": entry_price,
            "stop_loss": entry_price - 0.0020,  # 20 pips
            "take_profit": entry_price + 0.0040,  # 40 pips
            "entry_time": datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc),
        }

        # Test stop loss hit
        current_price = 1.0828  # Below stop loss
        should_close, close_reason = check_exit_conditions(position, current_price)
        assert should_close
        assert close_reason == "stop_loss"

        # Test take profit hit
        current_price = 1.0892  # Above take profit
        should_close, close_reason = check_exit_conditions(position, current_price)
        assert should_close
        assert close_reason == "take_profit"

        # Test normal price movement (no exit)
        current_price = 1.0860
        should_close, close_reason = check_exit_conditions(position, current_price)
        assert not should_close

    @pytest.mark.asyncio
    async def test_backtest_result_analysis(
        self, sample_market_data, sample_signals, tmp_path
    ):
        """Test comprehensive analysis of backtest results."""
        config = BacktestConfig()

        # Run backtest
        engine = BacktestEngine(
            initial_capital=config.initial_capital,
            data_handler=HistoricalDataHandler(sample_market_data),
            execution_handler=SimulatedExecutionHandler(config.commission),
            portfolio=Portfolio(initial_capital=config.initial_capital),
            strategy=MockStrategy(sample_signals),
            risk_manager=RiskManager(config),
        )

        results = await engine.run_backtest(
            start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 1, 10, tzinfo=timezone.utc),
        )

        # Analyze results
        analyzer = BacktestAnalyzer(results)

        # Generate analysis report
        analysis = analyzer.generate_report()

        # Verify analysis components
        assert "summary" in analysis
        assert "trade_analysis" in analysis
        assert "risk_analysis" in analysis
        assert "time_analysis" in analysis

        # Check summary statistics
        summary = analysis["summary"]
        assert "total_return" in summary
        assert "annualized_return" in summary
        assert "volatility" in summary
        assert "sharpe_ratio" in summary

        # Check trade analysis
        trade_analysis = analysis["trade_analysis"]
        assert "trade_distribution" in trade_analysis
        assert "holding_time_stats" in trade_analysis
        assert "win_loss_streaks" in trade_analysis

        # Save analysis report
        report_file = tmp_path / "backtest_analysis.json"
        with open(report_file, "w") as f:
            json.dump(analysis, f, indent=2, default=str)

        assert report_file.exists()


class MockStrategy(Strategy):
    """Mock strategy for testing."""

    def __init__(self, signals):
        self.signals = signals
        self.signal_index = 0

    async def calculate_signals(self, event: MarketEvent) -> Optional[SignalEvent]:
        # Check if we have a signal for this timestamp
        if self.signal_index < len(self.signals):
            signal = self.signals[self.signal_index]
            if (
                event.timestamp >= signal["timestamp"]
                and event.symbol == signal["symbol"]
            ):
                self.signal_index += 1
                return SignalEvent(
                    timestamp=signal["timestamp"],
                    symbol=signal["symbol"],
                    signal_type=signal["direction"],
                    strength=signal["confidence"],
                )
        return None


def check_exit_conditions(
    position: Dict, current_price: float
) -> Tuple[bool, Optional[str]]:
    """Check if position should be closed."""
    if position["direction"] == "BUY":
        if current_price <= position["stop_loss"]:
            return True, "stop_loss"
        if current_price >= position["take_profit"]:
            return True, "take_profit"
    else:  # SELL
        if current_price >= position["stop_loss"]:
            return True, "stop_loss"
        if current_price <= position["take_profit"]:
            return True, "take_profit"

    return False, None


class BacktestAnalyzer:
    """Analyzer for backtest results."""

    def __init__(self, results):
        self.results = results

    def generate_report(self) -> Dict[str, Any]:
        """Generate comprehensive analysis report."""
        return {
            "summary": self._calculate_summary(),
            "trade_analysis": self._analyze_trades(),
            "risk_analysis": self._analyze_risk(),
            "time_analysis": self._analyze_time_patterns(),
        }

    def _calculate_summary(self) -> Dict[str, Any]:
        """Calculate summary statistics."""
        perf = self.results["performance"]
        return {
            "total_return": perf.get("total_return", 0),
            "annualized_return": perf.get("annualized_return", 0),
            "volatility": perf.get("volatility", 0),
            "sharpe_ratio": perf.get("sharpe_ratio", 0),
            "max_drawdown": perf.get("max_drawdown", 0),
            "win_rate": perf.get("win_rate", 0),
        }

    def _analyze_trades(self) -> Dict[str, Any]:
        """Analyze trade patterns."""
        trades = self.results["trades"]

        # Calculate trade distribution
        winning_trades = [t for t in trades if t.get("pnl", 0) > 0]
        losing_trades = [t for t in trades if t.get("pnl", 0) < 0]

        return {
            "trade_distribution": {
                "total": len(trades),
                "winners": len(winning_trades),
                "losers": len(losing_trades),
            },
            "holding_time_stats": self._calculate_holding_times(trades),
            "win_loss_streaks": self._calculate_streaks(trades),
        }

    def _analyze_risk(self) -> Dict[str, Any]:
        """Analyze risk metrics."""
        equity_curve = self.results.get("equity_curve", [])

        if len(equity_curve) > 1:
            returns = pd.Series(equity_curve).pct_change().dropna()

            return {
                "value_at_risk_95": float(returns.quantile(0.05)),
                "conditional_var_95": float(
                    returns[returns <= returns.quantile(0.05)].mean()
                ),
                "downside_deviation": float(returns[returns < 0].std()),
                "max_consecutive_losses": self._max_consecutive_losses(),
            }

        return {}

    def _analyze_time_patterns(self) -> Dict[str, Any]:
        """Analyze performance by time patterns."""
        trades = self.results["trades"]

        # Group by hour of day
        hourly_performance = {}
        for trade in trades:
            if "entry_time" in trade:
                hour = trade["entry_time"].hour
                if hour not in hourly_performance:
                    hourly_performance[hour] = []
                hourly_performance[hour].append(trade.get("pnl", 0))

        return {
            "hourly_performance": {
                hour: {"trades": len(pnls), "avg_pnl": np.mean(pnls) if pnls else 0}
                for hour, pnls in hourly_performance.items()
            }
        }

    def _calculate_holding_times(self, trades: List[Dict]) -> Dict[str, float]:
        """Calculate holding time statistics."""
        holding_times = []

        for trade in trades:
            if "entry_time" in trade and "exit_time" in trade:
                duration = (
                    trade["exit_time"] - trade["entry_time"]
                ).total_seconds() / 3600
                holding_times.append(duration)

        if holding_times:
            return {
                "avg_hours": np.mean(holding_times),
                "min_hours": np.min(holding_times),
                "max_hours": np.max(holding_times),
                "median_hours": np.median(holding_times),
            }

        return {}

    def _calculate_streaks(self, trades: List[Dict]) -> Dict[str, int]:
        """Calculate winning and losing streaks."""
        max_win_streak = 0
        max_loss_streak = 0
        current_win_streak = 0
        current_loss_streak = 0

        for trade in trades:
            pnl = trade.get("pnl", 0)
            if pnl > 0:
                current_win_streak += 1
                current_loss_streak = 0
                max_win_streak = max(max_win_streak, current_win_streak)
            elif pnl < 0:
                current_loss_streak += 1
                current_win_streak = 0
                max_loss_streak = max(max_loss_streak, current_loss_streak)

        return {"max_win_streak": max_win_streak, "max_loss_streak": max_loss_streak}

    def _max_consecutive_losses(self) -> int:
        """Calculate maximum consecutive losses."""
        trades = self.results["trades"]
        max_consecutive = 0
        current_consecutive = 0

        for trade in trades:
            if trade.get("pnl", 0) < 0:
                current_consecutive += 1
                max_consecutive = max(max_consecutive, current_consecutive)
            else:
                current_consecutive = 0

        return max_consecutive


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
