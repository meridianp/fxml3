#!/usr/bin/env python
"""Comprehensive performance analysis of the enhanced FXML4 system."""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

import json
import logging
import warnings
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from joblib import load

warnings.filterwarnings("ignore")

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

from fxml4.data_engineering.data_aggregator import DataAggregator
from fxml4.ml.features import add_lagged_features, create_technical_features

# Import enhanced components
from scripts.production_system_enhanced import (
    EnhancedProductionConfig,
    EnhancedProductionSystem,
)


class ComprehensivePerformanceAnalyzer:
    """Analyze the enhanced FXML4 system performance in detail."""

    def __init__(self):
        self.data_aggregator = DataAggregator()
        self.results = {}

    def load_market_data(
        self, symbol: str, start_date: str, end_date: str
    ) -> pd.DataFrame:
        """Load and prepare market data for analysis."""
        logger.info(f"Loading {symbol} data from {start_date} to {end_date}")

        # Load data using aggregator
        data = self.data_aggregator.aggregate_data(
            symbol=symbol,
            start_date=pd.Timestamp(start_date),
            end_date=pd.Timestamp(end_date),
            timeframe="4H",
        )

        if data.empty:
            logger.error(f"No data found for {symbol}")
            return pd.DataFrame()

        # Add technical features
        data = create_technical_features(data)
        data = add_lagged_features(data, lags=[1, 2, 3, 5, 10])

        # Clean data
        data = data.dropna()

        logger.info(f"Loaded {len(data)} bars of data")
        return data

    def run_enhanced_backtest(
        self, data: pd.DataFrame, symbol: str, ml_model_path: Optional[str] = None
    ) -> Dict:
        """Run backtest with enhanced production system."""
        logger.info(f"Running enhanced backtest for {symbol}")

        # Configure enhanced system
        config = EnhancedProductionConfig(
            initial_capital=10000,
            max_risk_per_trade=0.015,  # 1.5%
            max_positions=2,
            min_confluences=2,
            min_signal_confidence=0.7,
            use_trailing_stops=True,
            use_partial_profits=True,
        )

        # Initialize system
        system = EnhancedProductionSystem(config)

        # Load ML model if provided
        if ml_model_path and Path(ml_model_path).exists():
            system.ml_model = load(ml_model_path)
            logger.info(f"Loaded ML model from {ml_model_path}")

        # Run backtest bar by bar
        for i in range(200, len(data)):  # Start after warmup period
            current_data = data.iloc[: i + 1]
            current_bar = data.iloc[i]
            current_time = data.index[i]

            # Update positions
            system.update_positions(symbol, current_bar, current_time)

            # Generate signal
            signal = system.generate_combined_signal(current_data, symbol, current_time)

            # Execute trade if signal
            if signal:
                system.execute_trade(signal, current_bar, current_time, symbol)

            # Track equity
            system.equity_curve.append(
                {
                    "time": current_time,
                    "equity": system.capital,
                    "positions": len(system.positions),
                }
            )

        # Close all remaining positions
        for position_id in list(system.positions.keys()):
            system._close_position(
                position_id, data["close"].iloc[-1], data.index[-1], "End of Test"
            )

        # Calculate performance metrics
        results = self._calculate_performance_metrics(system)
        results["symbol"] = symbol
        results["config"] = config.__dict__

        return results

    def _calculate_performance_metrics(self, system) -> Dict:
        """Calculate comprehensive performance metrics."""
        if not system.trades:
            return {
                "total_trades": 0,
                "total_return": 0,
                "win_rate": 0,
                "profit_factor": 0,
                "max_drawdown": 0,
                "sharpe_ratio": 0,
            }

        # Convert to DataFrame for analysis
        trades_df = pd.DataFrame(system.trades)
        equity_df = pd.DataFrame(system.equity_curve)

        # Basic metrics
        total_trades = len(trades_df)
        winning_trades = len(trades_df[trades_df["pnl"] > 0])
        losing_trades = len(trades_df[trades_df["pnl"] < 0])

        win_rate = winning_trades / total_trades if total_trades > 0 else 0

        # Returns
        total_return = (
            system.capital - system.config.initial_capital
        ) / system.config.initial_capital

        # Profit factor
        gross_profit = trades_df[trades_df["pnl"] > 0]["pnl"].sum()
        gross_loss = abs(trades_df[trades_df["pnl"] < 0]["pnl"].sum())
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

        # Drawdown
        equity_df["high_water_mark"] = equity_df["equity"].expanding().max()
        equity_df["drawdown"] = (
            equity_df["equity"] - equity_df["high_water_mark"]
        ) / equity_df["high_water_mark"]
        max_drawdown = equity_df["drawdown"].min()

        # Sharpe ratio (simplified)
        if len(equity_df) > 1:
            returns = equity_df["equity"].pct_change().dropna()
            sharpe_ratio = (
                returns.mean() / returns.std() * np.sqrt(252 * 6)
                if returns.std() > 0
                else 0
            )
        else:
            sharpe_ratio = 0

        # Additional metrics
        avg_win = (
            trades_df[trades_df["pnl"] > 0]["pnl"].mean() if winning_trades > 0 else 0
        )
        avg_loss = (
            trades_df[trades_df["pnl"] < 0]["pnl"].mean() if losing_trades > 0 else 0
        )

        # Signal source analysis
        signal_sources = trades_df["signal_source"].value_counts().to_dict()

        # Confluence analysis
        avg_confluences = (
            trades_df["confluences"].mean() if "confluences" in trades_df else 0
        )

        return {
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate": win_rate,
            "total_return": total_return,
            "profit_factor": profit_factor,
            "max_drawdown": max_drawdown,
            "sharpe_ratio": sharpe_ratio,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "avg_trade": trades_df["pnl"].mean(),
            "best_trade": trades_df["pnl"].max(),
            "worst_trade": trades_df["pnl"].min(),
            "signal_sources": signal_sources,
            "avg_confluences": avg_confluences,
            "final_capital": system.capital,
            "trades": trades_df.to_dict("records"),
            "equity_curve": equity_df.to_dict("records"),
        }

    def analyze_performance_drivers(self, results: Dict) -> Dict:
        """Analyze what drives performance."""
        if not results["trades"]:
            return {}

        trades_df = pd.DataFrame(results["trades"])

        analysis = {
            "by_signal_source": {},
            "by_time_of_day": {},
            "by_day_of_week": {},
            "by_holding_period": {},
            "by_confluence_count": {},
        }

        # Analyze by signal source
        for source in trades_df["signal_source"].unique():
            source_trades = trades_df[trades_df["signal_source"] == source]
            analysis["by_signal_source"][source] = {
                "count": len(source_trades),
                "win_rate": len(source_trades[source_trades["pnl"] > 0])
                / len(source_trades),
                "avg_pnl": source_trades["pnl"].mean(),
                "total_pnl": source_trades["pnl"].sum(),
            }

        # Analyze by time
        if "entry_time" in trades_df:
            trades_df["hour"] = pd.to_datetime(trades_df["entry_time"]).dt.hour
            trades_df["day_of_week"] = pd.to_datetime(
                trades_df["entry_time"]
            ).dt.dayofweek

            # By hour
            for hour in trades_df["hour"].unique():
                hour_trades = trades_df[trades_df["hour"] == hour]
                analysis["by_time_of_day"][hour] = {
                    "count": len(hour_trades),
                    "win_rate": (
                        len(hour_trades[hour_trades["pnl"] > 0]) / len(hour_trades)
                        if len(hour_trades) > 0
                        else 0
                    ),
                    "avg_pnl": hour_trades["pnl"].mean(),
                }

        return analysis

    def generate_performance_report(self, results: Dict, output_path: str):
        """Generate comprehensive performance report."""
        report = []
        report.append("=" * 80)
        report.append("FXML4 Enhanced System Performance Report")
        report.append("=" * 80)
        report.append(f"Generated: {datetime.now()}")
        report.append(f"Symbol: {results['symbol']}")
        report.append("")

        # Summary metrics
        report.append("PERFORMANCE SUMMARY")
        report.append("-" * 40)
        report.append(f"Total Trades: {results['total_trades']}")
        report.append(f"Win Rate: {results['win_rate']:.1%}")
        report.append(f"Total Return: {results['total_return']:.2%}")
        report.append(f"Profit Factor: {results['profit_factor']:.2f}")
        report.append(f"Max Drawdown: {results['max_drawdown']:.2%}")
        report.append(f"Sharpe Ratio: {results['sharpe_ratio']:.2f}")
        report.append(f"Average Trade: ${results['avg_trade']:.2f}")
        report.append("")

        # Risk metrics
        report.append("RISK METRICS")
        report.append("-" * 40)
        report.append(f"Average Win: ${results['avg_win']:.2f}")
        report.append(f"Average Loss: ${results['avg_loss']:.2f}")
        report.append(
            f"Win/Loss Ratio: {abs(results['avg_win']/results['avg_loss']) if results['avg_loss'] != 0 else 0:.2f}"
        )
        report.append(f"Best Trade: ${results['best_trade']:.2f}")
        report.append(f"Worst Trade: ${results['worst_trade']:.2f}")
        report.append("")

        # Signal analysis
        report.append("SIGNAL SOURCE ANALYSIS")
        report.append("-" * 40)
        for source, count in results["signal_sources"].items():
            report.append(f"{source}: {count} trades")
        report.append(f"Average Confluences: {results['avg_confluences']:.1f}")
        report.append("")

        # Save report
        with open(output_path, "w") as f:
            f.write("\n".join(report))

        logger.info(f"Report saved to {output_path}")

        return "\n".join(report)

    def plot_performance(self, results: Dict, output_dir: str):
        """Create performance visualization plots."""
        if not results["equity_curve"]:
            logger.warning("No equity curve data to plot")
            return

        # Create output directory
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        # Equity curve
        equity_df = pd.DataFrame(results["equity_curve"])
        equity_df["time"] = pd.to_datetime(equity_df["time"])

        plt.figure(figsize=(12, 6))
        plt.plot(equity_df["time"], equity_df["equity"], label="Equity")
        plt.title("Equity Curve - Enhanced FXML4 System")
        plt.xlabel("Date")
        plt.ylabel("Equity ($)")
        plt.grid(True)
        plt.legend()
        plt.tight_layout()
        plt.savefig(f"{output_dir}/equity_curve.png")
        plt.close()

        # Drawdown plot
        equity_df["returns"] = equity_df["equity"].pct_change()
        equity_df["cumulative"] = (1 + equity_df["returns"]).cumprod()
        equity_df["running_max"] = equity_df["cumulative"].expanding().max()
        equity_df["drawdown"] = (
            equity_df["cumulative"] - equity_df["running_max"]
        ) / equity_df["running_max"]

        plt.figure(figsize=(12, 4))
        plt.fill_between(
            equity_df["time"], equity_df["drawdown"] * 100, 0, alpha=0.3, color="red"
        )
        plt.plot(equity_df["time"], equity_df["drawdown"] * 100, color="red")
        plt.title("Drawdown Chart")
        plt.xlabel("Date")
        plt.ylabel("Drawdown (%)")
        plt.grid(True)
        plt.tight_layout()
        plt.savefig(f"{output_dir}/drawdown.png")
        plt.close()

        logger.info(f"Performance plots saved to {output_dir}")


def main():
    """Run comprehensive performance analysis."""
    analyzer = ComprehensivePerformanceAnalyzer()

    # Test periods
    test_configs = [
        {
            "symbol": "EURUSD",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "ml_model": None,  # Will use rule-based only
        },
        {
            "symbol": "GBPUSD",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "ml_model": "models/GBPUSD/model.joblib",
        },
    ]

    all_results = []

    for config in test_configs:
        logger.info(f"\nAnalyzing {config['symbol']}...")

        # Load data
        data = analyzer.load_market_data(
            config["symbol"], config["start_date"], config["end_date"]
        )

        if data.empty:
            logger.error(f"Skipping {config['symbol']} - no data")
            continue

        # Run backtest
        results = analyzer.run_enhanced_backtest(
            data, config["symbol"], config["ml_model"]
        )

        # Analyze performance drivers
        performance_drivers = analyzer.analyze_performance_drivers(results)
        results["performance_drivers"] = performance_drivers

        # Generate report
        report_path = f"output/performance_report_{config['symbol']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        analyzer.generate_performance_report(results, report_path)

        # Create plots
        plot_dir = f"output/performance_plots_{config['symbol']}"
        analyzer.plot_performance(results, plot_dir)

        all_results.append(results)

        # Print summary
        print(f"\n{config['symbol']} Results:")
        print(f"Total Return: {results['total_return']:.2%}")
        print(f"Win Rate: {results['win_rate']:.1%}")
        print(f"Max Drawdown: {results['max_drawdown']:.2%}")
        print(f"Sharpe Ratio: {results['sharpe_ratio']:.2f}")
        print(f"Total Trades: {results['total_trades']}")

    # Save all results
    with open(
        f"output/comprehensive_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
        "w",
    ) as f:
        json.dump(all_results, f, indent=2, default=str)

    logger.info("\nAnalysis complete!")


if __name__ == "__main__":
    main()
