#!/usr/bin/env python
"""Integrated forex trading system with ML, Elliott Wave, and Correlation Analysis."""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

import json
import warnings
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

from backtesting.correlation_portfolio_optimizer import CorrelationPortfolioOptimizer
from backtesting.forex_position_sizing import ForexPositionSizer
from scripts.correlation_analysis_system import CorrelationAnalysisSystem
from scripts.ensemble_ml_elliott_wave import EnsembleMLElliottWave


class IntegratedForexSystem:
    """Complete forex trading system integrating all components."""

    def __init__(self, symbols: List[str], initial_capital: float = 100000):
        self.symbols = symbols
        self.initial_capital = initial_capital
        self.current_capital = initial_capital

        # Initialize components
        self.ensemble_models = {
            symbol: EnsembleMLElliottWave(symbol) for symbol in symbols
        }
        self.correlation_analyzer = CorrelationAnalysisSystem()
        self.position_sizer = ForexPositionSizer()

        # Portfolio state
        self.positions = {}
        self.portfolio_weights = {symbol: 0.0 for symbol in symbols}

        # Cached data
        self.correlation_matrix = None
        self.market_regime = None
        self.economic_indicators = None

    def update_correlation_analysis(self, current_date: str):
        """Update correlation analysis and market regime."""
        print("\nUpdating correlation analysis...")

        # Fetch recent economic data
        end_date = current_date
        start_date = (pd.to_datetime(current_date) - timedelta(days=365)).strftime(
            "%Y-%m-%d"
        )

        try:
            # Get economic indicators
            self.economic_indicators = (
                self.correlation_analyzer.fetch_economic_indicators(
                    start_date, end_date
                )
            )

            if self.economic_indicators:
                # Calculate correlations
                corr_matrix, _ = self.correlation_analyzer.calculate_correlations(
                    self.economic_indicators
                )

                # Extract forex correlations
                forex_cols = [
                    col
                    for col in corr_matrix.columns
                    if any(symbol in col for symbol in self.symbols)
                ]

                if forex_cols:
                    self.correlation_matrix = corr_matrix[forex_cols].loc[forex_cols]

                # Detect market regime
                self.market_regime = self.correlation_analyzer.detect_market_regime(
                    self.economic_indicators
                ).iloc[-1]

                print(f"✅ Market Regime: {self.market_regime}")
            else:
                print("⚠️  No economic data available")
                self.market_regime = "NEUTRAL"

        except Exception as e:
            print(f"⚠️  Correlation update error: {e}")
            self.market_regime = "NEUTRAL"

    def optimize_portfolio_weights(self) -> Dict[str, float]:
        """Optimize portfolio weights based on correlations and expected returns."""

        if self.correlation_matrix is None or self.correlation_matrix.empty:
            # Equal weights if no correlation data
            return {symbol: 1.0 / len(self.symbols) for symbol in self.symbols}

        # Calculate expected returns from recent performance
        expected_returns = pd.Series(index=self.symbols)

        for symbol in self.symbols:
            # Use ensemble model confidence and recent performance
            # This is simplified - in production, use proper return forecasts
            if symbol in self.ensemble_models and self.ensemble_models[symbol].ml_model:
                expected_returns[symbol] = 0.02  # Default 2% annual
            else:
                expected_returns[symbol] = 0.01

        # Create correlation matrix for our symbols
        symbol_corr = pd.DataFrame(
            np.eye(len(self.symbols)), index=self.symbols, columns=self.symbols
        )

        # Update with actual correlations if available
        for i, sym1 in enumerate(self.symbols):
            for j, sym2 in enumerate(self.symbols):
                if i != j:
                    # Look for correlation data
                    for col in self.correlation_matrix.columns:
                        if sym1 in col:
                            for row in self.correlation_matrix.index:
                                if sym2 in row:
                                    symbol_corr.iloc[i, j] = (
                                        self.correlation_matrix.loc[row, col]
                                    )

        # Initialize portfolio optimizer
        optimizer = CorrelationPortfolioOptimizer(symbol_corr, expected_returns)

        # Get optimal weights based on regime
        optimal = optimizer.optimize_portfolio(
            max_position=0.4,  # Max 40% per currency
            allow_short=True,
            optimize_for="sharpe" if self.market_regime == "NEUTRAL" else "min_risk",
        )

        # Convert to dictionary
        weights = {}
        for i, symbol in enumerate(optimal.symbols):
            weights[symbol] = optimal.weights[i]

        print(f"\nOptimal Portfolio Weights (Sharpe: {optimal.sharpe_ratio:.2f}):")
        for symbol, weight in weights.items():
            print(f"  {symbol}: {weight:+.1%}")

        return weights

    def generate_integrated_signals(
        self, market_data: Dict[str, pd.DataFrame]
    ) -> Dict[str, Dict]:
        """Generate signals integrating all components."""
        signals = {}

        # Get optimal portfolio weights
        target_weights = self.optimize_portfolio_weights()

        for symbol, df in market_data.items():
            if symbol not in self.ensemble_models:
                continue

            # Get ensemble signals
            ensemble = self.ensemble_models[symbol]
            if ensemble.ml_model is None:
                continue

            signal_df = ensemble.generate_ensemble_signals(df)

            # Get latest signal
            latest_signal = signal_df["ensemble_signal"].iloc[-1]
            confidence = signal_df["confidence"].iloc[-1]

            # Adjust signal based on portfolio optimization
            current_weight = self.portfolio_weights.get(symbol, 0)
            target_weight = target_weights.get(symbol, 0)

            # Position adjustment signal
            weight_diff = target_weight - current_weight

            # Combine tactical (ML/Elliott) and strategic (correlation) signals
            if abs(weight_diff) > 0.05:  # Significant weight difference
                if weight_diff > 0 and latest_signal >= 0:
                    # Both suggest increasing position
                    final_signal = 1
                    final_confidence = min(confidence + 0.1, 1.0)
                elif weight_diff < 0 and latest_signal <= 0:
                    # Both suggest decreasing position
                    final_signal = -1
                    final_confidence = min(confidence + 0.1, 1.0)
                else:
                    # Conflicting signals - use correlation-based with lower confidence
                    final_signal = 1 if weight_diff > 0 else -1
                    final_confidence = confidence * 0.5
            else:
                # Small weight difference - use tactical signal
                final_signal = latest_signal
                final_confidence = confidence

            # Risk adjustment based on regime
            if self.market_regime and "RISK_OFF" in self.market_regime:
                final_confidence *= 0.7  # Reduce confidence in risk-off

            signals[symbol] = {
                "signal": final_signal,
                "confidence": final_confidence,
                "ml_signal": signal_df["ml_signal"].iloc[-1],
                "elliott_signal": signal_df["elliott_signal"].iloc[-1],
                "target_weight": target_weight,
                "current_weight": current_weight,
                "regime": self.market_regime,
            }

        return signals

    def execute_signals(
        self, signals: Dict[str, Dict], current_prices: Dict[str, float]
    ) -> List[Dict]:
        """Execute trading signals with proper position sizing."""
        trades = []

        # Check daily loss limit
        if self.position_sizer.check_daily_loss_limit(self.current_capital):
            print("⚠️  Daily loss limit reached - no new trades")
            return trades

        for symbol, signal_data in signals.items():
            signal = signal_data["signal"]
            confidence = signal_data["confidence"]

            if signal == 0 or confidence < 0.3:
                continue

            current_price = current_prices[symbol]

            # Check if we need to close existing position
            if symbol in self.positions:
                pos = self.positions[symbol]

                # Close if opposite signal
                if (pos["type"] == "long" and signal == -1) or (
                    pos["type"] == "short" and signal == 1
                ):

                    # Calculate P&L
                    if pos["type"] == "long":
                        pnl = pos["units"] * (current_price - pos["entry_price"])
                    else:
                        pnl = pos["units"] * (pos["entry_price"] - current_price)

                    self.current_capital += pnl
                    self.position_sizer.update_daily_pnl(pnl)

                    trades.append(
                        {
                            "symbol": symbol,
                            "action": "close",
                            "type": pos["type"],
                            "units": pos["units"],
                            "exit_price": current_price,
                            "pnl": pnl,
                            "reason": "signal_reversal",
                        }
                    )

                    del self.positions[symbol]
                    self.portfolio_weights[symbol] = 0

            # Open new position
            if symbol not in self.positions:
                # Calculate stop loss
                atr = current_prices.get(f"{symbol}_atr", current_price * 0.001)

                if signal == 1:
                    stop_loss = current_price - (atr * 2.5)
                else:
                    stop_loss = current_price + (atr * 2.5)

                # Calculate position size
                position = self.position_sizer.calculate_position_size(
                    account_balance=self.current_capital,
                    symbol=symbol,
                    entry_price=current_price,
                    stop_loss_price=stop_loss,
                    signal_strength=confidence,
                )

                if position["units"] > 0:
                    # Enter position
                    self.positions[symbol] = {
                        "entry_price": current_price,
                        "stop_loss": stop_loss,
                        "units": position["units"],
                        "type": "long" if signal == 1 else "short",
                        "margin_required": position["margin_required"],
                    }

                    # Update portfolio weight
                    position_value = position["notional_usd"]
                    total_value = (
                        self.current_capital * self.position_sizer.config.leverage
                    )
                    self.portfolio_weights[symbol] = position_value / total_value

                    trades.append(
                        {
                            "symbol": symbol,
                            "action": "open",
                            "type": "long" if signal == 1 else "short",
                            "units": position["units"],
                            "entry_price": current_price,
                            "stop_loss": stop_loss,
                            "notional_usd": position["notional_usd"],
                            "margin_required": position["margin_required"],
                            "confidence": confidence,
                            "regime": signal_data["regime"],
                        }
                    )

        return trades

    def get_system_status(self) -> Dict:
        """Get current system status and performance metrics."""
        total_margin_used = sum(
            pos.get("margin_required", 0) for pos in self.positions.values()
        )

        return {
            "capital": self.current_capital,
            "total_return": (self.current_capital - self.initial_capital)
            / self.initial_capital,
            "positions": len(self.positions),
            "margin_used": total_margin_used,
            "margin_available": self.current_capital - total_margin_used,
            "market_regime": self.market_regime,
            "portfolio_weights": self.portfolio_weights,
        }


def run_integrated_backtest(symbols: List[str], start_date: str, end_date: str):
    """Run backtest with the integrated system."""
    print("=" * 80)
    print("INTEGRATED FOREX TRADING SYSTEM BACKTEST")
    print("ML + Elliott Wave + Correlation Analysis + Portfolio Optimization")
    print("=" * 80)

    # Initialize system
    system = IntegratedForexSystem(symbols)

    # Load data for all symbols
    sys.path.append(str(Path(__file__).parent))
    from load_polygon_data import load_aggregated_data

    market_data = {}
    for symbol in symbols:
        df = load_aggregated_data(f"C_{symbol}", start_date, end_date)
        if df is not None and len(df) > 100:
            market_data[symbol] = df

    if not market_data:
        print("❌ No data available for backtesting")
        return

    print(f"\n✅ Loaded data for {len(market_data)} symbols")

    # Get date range
    all_dates = set()
    for df in market_data.values():
        all_dates.update(df.index)
    all_dates = sorted(all_dates)

    # Track performance
    trades_log = []
    equity_curve = [system.initial_capital]

    # Process each date
    update_frequency = 20  # Update correlations every 20 days

    for i, current_date in enumerate(all_dates[:-1]):
        # Update correlation analysis periodically
        if i % update_frequency == 0:
            system.update_correlation_analysis(current_date.strftime("%Y-%m-%d"))

        # Get current data slice
        current_data = {}
        current_prices = {}

        for symbol, df in market_data.items():
            if current_date in df.index:
                # Get data up to current date
                historical = df[df.index <= current_date].tail(100)
                if len(historical) > 50:
                    current_data[symbol] = historical
                    current_prices[symbol] = df.loc[current_date, "close"]
                    # Add ATR for stop loss calculation
                    atr = df.loc[current_date, "high"] - df.loc[current_date, "low"]
                    current_prices[f"{symbol}_atr"] = atr

        if not current_data:
            continue

        # Generate signals
        signals = system.generate_integrated_signals(current_data)

        # Execute trades
        trades = system.execute_signals(signals, current_prices)

        # Log trades
        for trade in trades:
            trade["date"] = current_date
            trades_log.append(trade)

            if trade["action"] == "open":
                print(
                    f"\n{current_date.strftime('%Y-%m-%d')} - "
                    f"{'BUY' if trade['type'] == 'long' else 'SELL'} {trade['symbol']}"
                )
                print(f"  Price: {trade['entry_price']:.5f}")
                print(f"  Notional: ${trade['notional_usd']:,.0f}")
                print(f"  Confidence: {trade['confidence']:.1%}")
                print(f"  Regime: {trade['regime']}")
            elif trade["action"] == "close":
                print(
                    f"\n{current_date.strftime('%Y-%m-%d')} - CLOSE {trade['symbol']}"
                )
                print(f"  P&L: ${trade['pnl']:,.2f}")

        # Update positions with current prices
        for symbol, pos in list(system.positions.items()):
            if symbol in current_prices:
                current_price = current_prices[symbol]

                # Check stop loss
                if (pos["type"] == "long" and current_price <= pos["stop_loss"]) or (
                    pos["type"] == "short" and current_price >= pos["stop_loss"]
                ):

                    # Stop loss hit
                    if pos["type"] == "long":
                        pnl = pos["units"] * (pos["stop_loss"] - pos["entry_price"])
                    else:
                        pnl = pos["units"] * (pos["entry_price"] - pos["stop_loss"])

                    system.current_capital += pnl

                    trades_log.append(
                        {
                            "date": current_date,
                            "symbol": symbol,
                            "action": "close",
                            "type": pos["type"],
                            "units": pos["units"],
                            "exit_price": pos["stop_loss"],
                            "pnl": pnl,
                            "reason": "stop_loss",
                        }
                    )

                    del system.positions[symbol]
                    system.portfolio_weights[symbol] = 0

        # Track equity
        equity_curve.append(system.current_capital)

    # Get final status
    status = system.get_system_status()

    # Calculate performance metrics
    completed_trades = [t for t in trades_log if t["action"] == "close"]

    if completed_trades:
        wins = [t for t in completed_trades if t["pnl"] > 0]
        losses = [t for t in completed_trades if t["pnl"] < 0]

        win_rate = len(wins) / len(completed_trades)
        avg_win = np.mean([t["pnl"] for t in wins]) if wins else 0
        avg_loss = np.mean([abs(t["pnl"]) for t in losses]) if losses else 0

        # Sharpe ratio
        equity_array = np.array(equity_curve)
        returns = np.diff(equity_array) / equity_array[:-1]
        sharpe = (
            np.mean(returns) / np.std(returns) * np.sqrt(252)
            if np.std(returns) > 0
            else 0
        )
    else:
        win_rate = avg_win = avg_loss = sharpe = 0

    # Print results
    print(f"\n{'='*80}")
    print("INTEGRATED SYSTEM RESULTS")
    print(f"{'='*80}")
    print(f"Initial Capital:    ${system.initial_capital:,.2f}")
    print(f"Final Capital:      ${system.current_capital:,.2f}")
    print(f"Total Return:       {status['total_return']:+.2%}")
    print(f"Sharpe Ratio:       {sharpe:.2f}")
    print(f"Total Trades:       {len(completed_trades)}")
    print(f"Win Rate:           {win_rate:.1%}")
    print(f"Average Win:        ${avg_win:,.2f}")
    print(f"Average Loss:       ${avg_loss:,.2f}")

    print(f"\nFinal Portfolio Weights:")
    for symbol, weight in status["portfolio_weights"].items():
        if abs(weight) > 0.01:
            print(f"  {symbol}: {weight:+.1%}")

    # Calculate basic risk metrics
    equity_array = np.array(equity_curve)
    returns = np.diff(equity_array) / equity_array[:-1]
    max_dd = (equity_array / np.maximum.accumulate(equity_array) - 1).min()

    print(f"\nRisk Metrics:")
    print(f"  Max Drawdown: {max_dd:.2%}")
    print(f"  Volatility:   {np.std(returns) * np.sqrt(252):.2%}")

    return status, trades_log, equity_curve


def main():
    """Run integrated forex trading system backtest."""
    symbols = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF"]
    start_date = "2024-01-01"
    end_date = "2025-06-01"

    # Note: Make sure to run setup_correlation_analysis.sh first
    print(
        "Note: Run './scripts/setup_correlation_analysis.sh' to install required libraries\n"
    )

    status, trades, equity = run_integrated_backtest(symbols, start_date, end_date)


if __name__ == "__main__":
    main()
