#!/usr/bin/env python3
"""
Consolidated Backtest Suite for FXML4
Combines functionality from multiple backtest scripts into a single interface.
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fxml4.backtesting.event_driven_engine import EventDrivenEngine
from fxml4.backtesting.performance_metrics import PerformanceMetrics
from fxml4.ml.models import ModelLoader
from fxml4.strategy.integrated_signal_generator import IntegratedSignalGenerator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ConsolidatedBacktestSuite:
    """Consolidated backtesting suite with multiple strategies and configurations."""

    def __init__(self):
        self.strategies = {
            "enhanced_realistic": self.enhanced_realistic_backtest,
            "enhanced_strategy": self.enhanced_strategy_backtest,
            "full_system_400x": self.full_system_400x_backtest,
            "integrated_daily": self.integrated_daily_backtest,
            "integrated_system": self.integrated_system_backtest,
            "ml_elliott_combined": self.ml_elliott_combined_backtest,
            "original_with_enhancements": self.original_with_enhancements_backtest,
            "production_ready": self.production_ready_backtest,
            "production_system": self.production_system_backtest,
            "v2_without_ml": self.v2_without_ml_backtest,
            "with_improvements": self.with_improvements_backtest,
            "with_real_data": self.with_real_data_backtest,
            "with_visual_elliott": self.with_visual_elliott_backtest,
        }

    def enhanced_realistic_backtest(self, symbol, start_date, end_date, **kwargs):
        """Enhanced realistic backtest with proper risk management."""
        logger.info(f"Running enhanced realistic backtest for {symbol}")

        # Configure realistic parameters
        config = {
            "symbol": symbol,
            "start_date": start_date,
            "end_date": end_date,
            "initial_balance": kwargs.get("initial_balance", 10000),
            "leverage": kwargs.get("leverage", 1),
            "risk_per_trade": kwargs.get("risk_per_trade", 0.02),
            "max_position_size": kwargs.get("max_position_size", 0.1),
            "use_ml": kwargs.get("use_ml", True),
            "use_elliott_wave": kwargs.get("use_elliott_wave", True),
            "timeframe": kwargs.get("timeframe", "4h"),
        }

        return self._run_backtest(config, "enhanced_realistic")

    def enhanced_strategy_backtest(self, symbol, start_date, end_date, **kwargs):
        """Enhanced strategy backtest with advanced features."""
        logger.info(f"Running enhanced strategy backtest for {symbol}")

        config = {
            "symbol": symbol,
            "start_date": start_date,
            "end_date": end_date,
            "initial_balance": kwargs.get("initial_balance", 10000),
            "leverage": kwargs.get("leverage", 2),
            "use_sentiment": kwargs.get("use_sentiment", True),
            "use_news_filter": kwargs.get("use_news_filter", True),
            "dynamic_position_sizing": kwargs.get("dynamic_position_sizing", True),
            "timeframe": kwargs.get("timeframe", "4h"),
        }

        return self._run_backtest(config, "enhanced_strategy")

    def full_system_400x_backtest(self, symbol, start_date, end_date, **kwargs):
        """Full system backtest with 400x leverage (demo purposes)."""
        logger.info(f"Running full system 400x backtest for {symbol}")

        config = {
            "symbol": symbol,
            "start_date": start_date,
            "end_date": end_date,
            "initial_balance": kwargs.get("initial_balance", 1000),
            "leverage": 400,  # Extreme leverage for demonstration
            "risk_per_trade": 0.001,  # Very low risk per trade
            "max_position_size": 0.05,
            "use_all_features": True,
            "timeframe": kwargs.get("timeframe", "4h"),
        }

        return self._run_backtest(config, "full_system_400x")

    def integrated_daily_backtest(self, symbol, start_date, end_date, **kwargs):
        """Integrated daily backtest with comprehensive features."""
        logger.info(f"Running integrated daily backtest for {symbol}")

        config = {
            "symbol": symbol,
            "start_date": start_date,
            "end_date": end_date,
            "initial_balance": kwargs.get("initial_balance", 50000),
            "leverage": kwargs.get("leverage", 5),
            "timeframe": "daily",
            "use_ml": True,
            "use_elliott_wave": True,
            "use_sentiment": True,
            "use_economic_features": True,
        }

        return self._run_backtest(config, "integrated_daily")

    def integrated_system_backtest(self, symbol, start_date, end_date, **kwargs):
        """Integrated system backtest with all components."""
        logger.info(f"Running integrated system backtest for {symbol}")

        config = {
            "symbol": symbol,
            "start_date": start_date,
            "end_date": end_date,
            "initial_balance": kwargs.get("initial_balance", 100000),
            "leverage": kwargs.get("leverage", 10),
            "use_all_signals": True,
            "use_ensemble_models": True,
            "dynamic_risk_management": True,
            "timeframe": kwargs.get("timeframe", "4h"),
        }

        return self._run_backtest(config, "integrated_system")

    def ml_elliott_combined_backtest(self, symbol, start_date, end_date, **kwargs):
        """Combined ML and Elliott Wave backtest."""
        logger.info(f"Running ML + Elliott Wave backtest for {symbol}")

        config = {
            "symbol": symbol,
            "start_date": start_date,
            "end_date": end_date,
            "initial_balance": kwargs.get("initial_balance", 25000),
            "leverage": kwargs.get("leverage", 3),
            "ml_weight": kwargs.get("ml_weight", 0.6),
            "elliott_weight": kwargs.get("elliott_weight", 0.4),
            "timeframe": kwargs.get("timeframe", "4h"),
        }

        return self._run_backtest(config, "ml_elliott_combined")

    def original_with_enhancements_backtest(
        self, symbol, start_date, end_date, **kwargs
    ):
        """Original strategy with enhancements."""
        logger.info(f"Running original with enhancements backtest for {symbol}")

        config = {
            "symbol": symbol,
            "start_date": start_date,
            "end_date": end_date,
            "initial_balance": kwargs.get("initial_balance", 10000),
            "leverage": kwargs.get("leverage", 1),
            "enhanced_features": True,
            "improved_risk_management": True,
            "timeframe": kwargs.get("timeframe", "4h"),
        }

        return self._run_backtest(config, "original_with_enhancements")

    def production_ready_backtest(self, symbol, start_date, end_date, **kwargs):
        """Production-ready backtest configuration."""
        logger.info(f"Running production ready backtest for {symbol}")

        config = {
            "symbol": symbol,
            "start_date": start_date,
            "end_date": end_date,
            "initial_balance": kwargs.get("initial_balance", 100000),
            "leverage": kwargs.get("leverage", 2),
            "production_mode": True,
            "strict_risk_management": True,
            "compliance_checks": True,
            "timeframe": kwargs.get("timeframe", "4h"),
        }

        return self._run_backtest(config, "production_ready")

    def production_system_backtest(self, symbol, start_date, end_date, **kwargs):
        """Production system backtest."""
        logger.info(f"Running production system backtest for {symbol}")

        config = {
            "symbol": symbol,
            "start_date": start_date,
            "end_date": end_date,
            "initial_balance": kwargs.get("initial_balance", 100000),
            "leverage": kwargs.get("leverage", 2),
            "production_features": True,
            "real_market_conditions": True,
            "timeframe": kwargs.get("timeframe", "4h"),
        }

        return self._run_backtest(config, "production_system")

    def v2_without_ml_backtest(self, symbol, start_date, end_date, **kwargs):
        """V2 backtest without ML components."""
        logger.info(f"Running v2 without ML backtest for {symbol}")

        config = {
            "symbol": symbol,
            "start_date": start_date,
            "end_date": end_date,
            "initial_balance": kwargs.get("initial_balance", 10000),
            "leverage": kwargs.get("leverage", 1),
            "use_ml": False,
            "use_elliott_wave": True,
            "use_technical_indicators": True,
            "timeframe": kwargs.get("timeframe", "4h"),
        }

        return self._run_backtest(config, "v2_without_ml")

    def with_improvements_backtest(self, symbol, start_date, end_date, **kwargs):
        """Backtest with improvements."""
        logger.info(f"Running backtest with improvements for {symbol}")

        config = {
            "symbol": symbol,
            "start_date": start_date,
            "end_date": end_date,
            "initial_balance": kwargs.get("initial_balance", 10000),
            "leverage": kwargs.get("leverage", 1),
            "improvements": True,
            "enhanced_signals": True,
            "better_risk_management": True,
            "timeframe": kwargs.get("timeframe", "4h"),
        }

        return self._run_backtest(config, "with_improvements")

    def with_real_data_backtest(self, symbol, start_date, end_date, **kwargs):
        """Backtest with real market data."""
        logger.info(f"Running backtest with real data for {symbol}")

        config = {
            "symbol": symbol,
            "start_date": start_date,
            "end_date": end_date,
            "initial_balance": kwargs.get("initial_balance", 10000),
            "leverage": kwargs.get("leverage", 1),
            "use_real_data": True,
            "real_spreads": True,
            "real_slippage": True,
            "timeframe": kwargs.get("timeframe", "4h"),
        }

        return self._run_backtest(config, "with_real_data")

    def with_visual_elliott_backtest(self, symbol, start_date, end_date, **kwargs):
        """Backtest with visual Elliott Wave analysis."""
        logger.info(f"Running backtest with visual Elliott Wave for {symbol}")

        config = {
            "symbol": symbol,
            "start_date": start_date,
            "end_date": end_date,
            "initial_balance": kwargs.get("initial_balance", 10000),
            "leverage": kwargs.get("leverage", 1),
            "use_elliott_wave": True,
            "visual_analysis": True,
            "chart_generation": True,
            "timeframe": kwargs.get("timeframe", "4h"),
        }

        return self._run_backtest(config, "with_visual_elliott")

    def _run_backtest(self, config, strategy_name):
        """Run backtest with given configuration."""
        try:
            # Initialize backtest engine
            engine = EventDrivenEngine(config)

            # Run backtest
            results = engine.run_backtest()

            # Calculate performance metrics
            metrics = PerformanceMetrics(results)
            performance = metrics.calculate_all_metrics()

            # Create summary
            summary = {
                "strategy": strategy_name,
                "config": config,
                "performance": performance,
                "timestamp": datetime.now().isoformat(),
            }

            # Save results
            output_dir = Path("output") / strategy_name
            output_dir.mkdir(parents=True, exist_ok=True)

            with open(
                output_dir / f'results_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json',
                "w",
            ) as f:
                json.dump(summary, f, indent=2, default=str)

            return summary

        except Exception as e:
            logger.error(f"Error running {strategy_name} backtest: {e}")
            return {"error": str(e), "strategy": strategy_name}

    def run_strategy(self, strategy_name, symbol, start_date, end_date, **kwargs):
        """Run a specific strategy."""
        if strategy_name not in self.strategies:
            raise ValueError(f"Unknown strategy: {strategy_name}")

        return self.strategies[strategy_name](symbol, start_date, end_date, **kwargs)

    def list_strategies(self):
        """List available strategies."""
        return list(self.strategies.keys())

    def run_comparison(self, strategies, symbol, start_date, end_date, **kwargs):
        """Run comparison between multiple strategies."""
        results = {}

        for strategy in strategies:
            logger.info(f"Running {strategy} for comparison")
            results[strategy] = self.run_strategy(
                strategy, symbol, start_date, end_date, **kwargs
            )

        # Generate comparison report
        comparison = {
            "symbol": symbol,
            "period": f"{start_date} to {end_date}",
            "strategies": results,
            "timestamp": datetime.now().isoformat(),
        }

        # Save comparison
        output_dir = Path("output") / "comparisons"
        output_dir.mkdir(parents=True, exist_ok=True)

        with open(
            output_dir / f'comparison_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json',
            "w",
        ) as f:
            json.dump(comparison, f, indent=2, default=str)

        return comparison


def main():
    """Main CLI interface."""
    parser = argparse.ArgumentParser(description="FXML4 Consolidated Backtest Suite")
    parser.add_argument("--strategy", required=True, help="Strategy to run")
    parser.add_argument("--symbol", required=True, help="Trading symbol")
    parser.add_argument("--start-date", required=True, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", required=True, help="End date (YYYY-MM-DD)")
    parser.add_argument(
        "--initial-balance", type=float, default=10000, help="Initial balance"
    )
    parser.add_argument("--leverage", type=float, default=1, help="Leverage")
    parser.add_argument("--timeframe", default="4h", help="Timeframe")
    parser.add_argument(
        "--list-strategies", action="store_true", help="List available strategies"
    )
    parser.add_argument("--compare", nargs="+", help="Compare multiple strategies")

    args = parser.parse_args()

    suite = ConsolidatedBacktestSuite()

    if args.list_strategies:
        print("Available strategies:")
        for strategy in suite.list_strategies():
            print(f"  - {strategy}")
        return

    if args.compare:
        logger.info(f"Running comparison between strategies: {args.compare}")
        result = suite.run_comparison(
            args.compare,
            args.symbol,
            args.start_date,
            args.end_date,
            initial_balance=args.initial_balance,
            leverage=args.leverage,
            timeframe=args.timeframe,
        )
        print(f"Comparison completed. Results saved to output/comparisons/")
        return

    # Run single strategy
    logger.info(f"Running strategy: {args.strategy}")
    result = suite.run_strategy(
        args.strategy,
        args.symbol,
        args.start_date,
        args.end_date,
        initial_balance=args.initial_balance,
        leverage=args.leverage,
        timeframe=args.timeframe,
    )

    if "error" in result:
        logger.error(f"Backtest failed: {result['error']}")
        sys.exit(1)
    else:
        logger.info(
            f"Backtest completed successfully. Results saved to output/{args.strategy}/"
        )


if __name__ == "__main__":
    main()
