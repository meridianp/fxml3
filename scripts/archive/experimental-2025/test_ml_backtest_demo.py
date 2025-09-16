#!/usr/bin/env python3
"""
FXML4 ML Model and Backtesting Demo Script

This script demonstrates how to build ML models and run backtests
with the FXML4 system. It provides a complete workflow example.
"""

import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score

# Add fxml4 to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fxml4.backtesting.backtest_engine import run_backtest
from fxml4.config import get_config
from fxml4.data_engineering.data_feeds.base_feed import DataFeedFactory
from fxml4.ml.features import create_technical_features
from fxml4.ml.models import create_model
from fxml4.strategy.ml_signal_generator import MLSignalGenerator

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class MLBacktestDemo:
    """Demonstration of ML model building and backtesting."""

    def __init__(self):
        self.symbol = "EURUSD"
        self.timeframe = "4h"
        self.data = None
        self.features_data = None
        self.model = None
        self.signal_generator = None
        self.backtest_result = None

    def step_1_generate_sample_data(self):
        """Generate realistic sample data for the demo."""
        logger.info("🔄 Step 1: Generating sample market data...")

        # Generate 1 year of 4-hour data
        start_date = datetime.now() - timedelta(days=365)
        end_date = datetime.now() - timedelta(
            days=30
        )  # Leave recent data for out-of-sample testing

        timestamps = pd.date_range(start=start_date, end=end_date, freq="4H")

        # Generate realistic forex data with some trends and volatility
        np.random.seed(42)  # For reproducible results
        n_periods = len(timestamps)

        # Start with EUR/USD around 1.05
        base_price = 1.0500

        # Add some realistic market dynamics
        # - Long term trend
        # - Seasonal patterns
        # - Random walk with volatility clustering

        # Create price movements
        daily_volatility = 0.008  # ~0.8% daily volatility
        hour_volatility = daily_volatility / np.sqrt(6)  # 4-hour periods

        # Add trend and seasonality
        trend = np.linspace(0, 0.05, n_periods)  # 5% trend over the period
        seasonal = 0.01 * np.sin(
            2 * np.pi * np.arange(n_periods) / (365.25 * 6)
        )  # Yearly cycle

        # Generate returns with volatility clustering (GARCH-like)
        returns = []
        volatility = hour_volatility

        for i in range(n_periods):
            # Volatility clustering
            volatility = (
                0.9 * volatility
                + 0.1 * hour_volatility
                + 0.05 * abs(returns[-1] if returns else 0)
            )

            # Generate return
            return_val = np.random.normal(
                trend[i] / n_periods + seasonal[i] / n_periods, volatility
            )
            returns.append(return_val)

        # Convert to prices
        log_prices = np.log(base_price) + np.cumsum(returns)
        close_prices = np.exp(log_prices)

        # Generate OHLC data
        data = []
        for i, (timestamp, close) in enumerate(zip(timestamps, close_prices)):
            if i == 0:
                open_price = close
            else:
                # Open with small gap
                gap = np.random.normal(0, hour_volatility * 0.3)
                open_price = close_prices[i - 1] * (1 + gap)

            # High/Low with realistic spreads
            intrabar_volatility = abs(returns[i]) * 2
            high = max(open_price, close) * (
                1 + np.random.uniform(0, intrabar_volatility)
            )
            low = min(open_price, close) * (
                1 - np.random.uniform(0, intrabar_volatility)
            )

            volume = np.random.randint(5000, 25000)

            data.append(
                {
                    "timestamp": timestamp,
                    "open": open_price,
                    "high": high,
                    "low": low,
                    "close": close,
                    "volume": volume,
                }
            )

        self.data = pd.DataFrame(data)
        self.data.set_index("timestamp", inplace=True)

        logger.info(
            f"✅ Generated {len(self.data)} data points from {start_date.date()} to {end_date.date()}"
        )
        logger.info(
            f"   Price range: {self.data['close'].min():.4f} - {self.data['close'].max():.4f}"
        )
        logger.info(
            f"   Total return: {(self.data['close'].iloc[-1] / self.data['close'].iloc[0] - 1) * 100:.2f}%"
        )

    def step_2_feature_engineering(self):
        """Create technical features for ML model."""
        logger.info("🔄 Step 2: Creating technical features...")

        # Create comprehensive technical features
        self.features_data = create_technical_features(
            self.data.copy(),
            indicators=[
                "sma",
                "ema",
                "rsi",
                "macd",
                "bollinger",
                "atr",
                "adx",
                "stochastic",
                "williams_r",
            ],
            ma_periods=[5, 10, 20, 50, 100],
            include_original=True,
        )

        logger.info(f"✅ Created {len(self.features_data.columns)} features")

        # Show some feature statistics
        feature_cols = [
            col
            for col in self.features_data.columns
            if col not in ["open", "high", "low", "close", "volume"]
        ]

        logger.info(f"   Technical indicators: {len(feature_cols)}")
        logger.info(f"   Sample features: {', '.join(feature_cols[:5])}...")

    def step_3_prepare_training_data(self):
        """Prepare data for ML training."""
        logger.info("🔄 Step 3: Preparing training data...")

        # Create target variable
        # Predict next period's return direction
        self.features_data["next_return"] = (
            self.features_data["close"].shift(-1) / self.features_data["close"] - 1
        )

        # Create classification targets
        buy_threshold = 0.002  # 20 pips for EUR/USD
        sell_threshold = -0.002  # -20 pips for EUR/USD

        def create_target(returns):
            """Create multi-class target: 0=hold, 1=buy, 2=sell"""
            targets = np.zeros(len(returns))
            targets[returns > buy_threshold] = 1  # Buy signal
            targets[returns < sell_threshold] = 2  # Sell signal
            return targets

        self.features_data["target"] = create_target(self.features_data["next_return"])

        # Remove NaN values
        self.features_data = self.features_data.dropna()

        # Split data chronologically
        split_ratio = 0.7
        split_idx = int(len(self.features_data) * split_ratio)

        self.train_data = self.features_data.iloc[:split_idx]
        self.test_data = self.features_data.iloc[split_idx:]

        # Prepare feature matrices
        self.feature_columns = [
            col
            for col in self.features_data.columns
            if col
            not in ["open", "high", "low", "close", "volume", "next_return", "target"]
        ]

        self.X_train = self.train_data[self.feature_columns]
        self.y_train = self.train_data["target"]
        self.X_test = self.test_data[self.feature_columns]
        self.y_test = self.test_data["target"]

        logger.info(f"✅ Training data prepared:")
        logger.info(f"   Training samples: {len(self.X_train)}")
        logger.info(f"   Test samples: {len(self.X_test)}")
        logger.info(f"   Features: {len(self.feature_columns)}")
        logger.info(
            f"   Target distribution (train): Hold={sum(self.y_train==0)}, Buy={sum(self.y_train==1)}, Sell={sum(self.y_train==2)}"
        )

    def step_4_train_models(self):
        """Train and compare different ML models."""
        logger.info("🔄 Step 4: Training ML models...")

        # Test different model types
        model_configs = {
            "random_forest": {
                "n_estimators": 100,
                "max_depth": 10,
                "min_samples_split": 20,
            },
            "xgboost": {"n_estimators": 100, "max_depth": 6, "learning_rate": 0.1},
            "logistic_regression": {"max_iter": 1000, "random_state": 42},
        }

        model_results = {}

        for model_type, config in model_configs.items():
            logger.info(f"   Training {model_type}...")

            # Create and train model
            # Fix model_type mapping for create_model function
            model_type_map = {
                "random_forest": "random_forest",
                "xgboost": "xgboost",
                "logistic_regression": "logistic",
            }
            model = create_model(
                model_type=model_type_map.get(model_type, model_type),
                n_classes=3,
                model_params=config,
            )
            model.train(self.X_train, self.y_train)

            # Evaluate model
            train_predictions = model.predict(self.X_train)
            test_predictions = model.predict(self.X_test)
            train_accuracy = accuracy_score(self.y_train, train_predictions)
            test_accuracy = accuracy_score(self.y_test, test_predictions)

            # Get predictions and probabilities
            test_probabilities = model.predict_proba(self.X_test)

            model_results[model_type] = {
                "model": model,
                "train_accuracy": train_accuracy,
                "test_accuracy": test_accuracy,
                "predictions": test_predictions,
                "probabilities": test_probabilities,
            }

            logger.info(f"     Train accuracy: {train_accuracy:.3f}")
            logger.info(f"     Test accuracy: {test_accuracy:.3f}")

        # Select best model based on test accuracy
        best_model_type = max(
            model_results.keys(), key=lambda k: model_results[k]["test_accuracy"]
        )

        self.model = model_results[best_model_type]["model"]
        self.best_model_type = best_model_type

        logger.info(
            f"✅ Best model: {best_model_type} (test accuracy: {model_results[best_model_type]['test_accuracy']:.3f})"
        )

        # Feature importance for tree-based models
        if hasattr(self.model, "feature_importances_"):
            feature_names = self.X_train.columns
            importance_df = pd.DataFrame(
                {
                    "feature": feature_names,
                    "importance": self.model.feature_importances_,
                }
            ).sort_values("importance", ascending=False)

            logger.info("   Top 5 most important features:")
            for _, row in importance_df.head().iterrows():
                logger.info(f"     {row['feature']}: {row['importance']:.3f}")

    def step_5_generate_signals(self):
        """Generate trading signals using the trained model."""
        logger.info("🔄 Step 5: Generating trading signals...")

        # Create signal generator
        config = {
            "threshold": 0.6,  # Minimum confidence for signal
            "probability_mode": True,  # Use probability threshold
            "use_technical_features": False,  # Don't regenerate features
            "feature_columns": self.feature_columns,  # Use same features as training
        }

        self.signal_generator = MLSignalGenerator(self.model, config)

        # Generate signals on full dataset
        signals = self.signal_generator.generate_signals(
            self.features_data, symbol=self.symbol, timeframe=self.timeframe
        )

        logger.info(f"✅ Generated {len(signals)} trading signals")

        if signals:
            # Analyze signal distribution
            signal_types = [s.signal_type.value for s in signals]
            signal_counts = pd.Series(signal_types).value_counts()

            logger.info("   Signal distribution:")
            for signal_type, count in signal_counts.items():
                logger.info(f"     {signal_type}: {count}")

            # Show sample signals
            logger.info("   Sample signals:")
            for i, signal in enumerate(signals[:3]):
                logger.info(
                    f"     {i+1}. {signal.timestamp.strftime('%Y-%m-%d %H:%M')} - "
                    f"{signal.signal_type.value} (confidence: {signal.confidence:.3f}, "
                    f"price: {signal.price:.4f})"
                )

        self.signals = signals

    def step_6_run_backtest(self):
        """Run backtest using the ML-generated signals."""
        logger.info("🔄 Step 6: Running backtest...")

        # Create ML strategy for backtesting
        def ml_strategy(data, index, params):
            """ML-based trading strategy."""
            signals = {}

            # Need minimum data for signal generation
            if index < 50:
                return signals

            try:
                # Get historical data up to current point
                historical_data = data.iloc[: index + 1]

                # Generate signals
                ml_signals = self.signal_generator.generate_signals(
                    historical_data,
                    symbol=params.get("symbol", "UNKNOWN"),
                    timeframe=params.get("timeframe", "UNKNOWN"),
                )

                # Process latest signal
                if ml_signals:
                    latest_signal = ml_signals[-1]

                    # Only act on signals from the current bar
                    current_time = data.index[index]
                    signal_age = (
                        current_time - latest_signal.timestamp
                    ).total_seconds() / 3600  # hours

                    if (
                        signal_age < 8
                    ):  # Signal from last 8 hours (2 bars for 4h timeframe)
                        if latest_signal.signal_type.value == "entry_long":
                            signals["entry"] = True
                            signals["direction"] = "buy"
                            signals["risk_pct"] = params.get("risk_pct", 0.02)
                        elif latest_signal.signal_type.value == "entry_short":
                            signals["entry"] = True
                            signals["direction"] = "sell"
                            signals["risk_pct"] = params.get("risk_pct", 0.02)
                        elif latest_signal.signal_type.value in [
                            "exit_long",
                            "exit_short",
                        ]:
                            signals["exit"] = True

            except Exception as e:
                # Don't let signal generation errors break backtesting
                pass

            return signals

        # Backtest configuration
        backtest_config = {
            "initial_capital": 10000.0,
            "commission": 0.0002,  # 2 pips commission
            "slippage": 0.0001,  # 1 pip slippage
        }

        strategy_params = {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "risk_pct": 0.02,  # Risk 2% per trade
            "model_type": self.best_model_type,
        }

        # Run backtest
        self.backtest_result = run_backtest(
            strategy=ml_strategy,
            data=self.features_data,
            strategy_params=strategy_params,
            config=backtest_config,
        )

        logger.info("✅ Backtest completed")

    def step_7_analyze_results(self):
        """Analyze and display backtest results."""
        logger.info("🔄 Step 7: Analyzing results...")

        result = self.backtest_result

        # Basic performance metrics
        logger.info(
            f"""
📊 BACKTEST RESULTS SUMMARY
{'='*50}
Strategy: ML-based ({self.best_model_type})
Symbol: {self.symbol}
Timeframe: {self.timeframe}
Period: {self.features_data.index[0].strftime('%Y-%m-%d')} to {self.features_data.index[-1].strftime('%Y-%m-%d')}

💰 PERFORMANCE METRICS
Initial Capital: ${result.initial_capital:,.2f}
Final Capital: ${result.final_capital:,.2f}
Total Return: ${result.total_return:,.2f} ({result.total_return_pct:.2f}%)
"""
        )

        # Risk metrics
        if hasattr(result, "max_drawdown_pct"):
            logger.info(f"Max Drawdown: {result.max_drawdown_pct:.2f}%")
        if hasattr(result, "sharpe_ratio"):
            logger.info(f"Sharpe Ratio: {result.sharpe_ratio:.3f}")
        if hasattr(result, "sortino_ratio"):
            logger.info(f"Sortino Ratio: {result.sortino_ratio:.3f}")

        # Trade statistics
        logger.info(
            f"""
📈 TRADE STATISTICS
Total Trades: {len(result.trades)}
"""
        )

        if len(result.trades) > 0:
            # Calculate additional trade stats
            winning_trades = [t for t in result.trades if t.pnl > 0]
            losing_trades = [t for t in result.trades if t.pnl < 0]

            win_rate = len(winning_trades) / len(result.trades) if result.trades else 0
            avg_win = np.mean([t.pnl for t in winning_trades]) if winning_trades else 0
            avg_loss = np.mean([t.pnl for t in losing_trades]) if losing_trades else 0
            profit_factor = (
                abs(
                    sum(t.pnl for t in winning_trades)
                    / sum(t.pnl for t in losing_trades)
                )
                if losing_trades
                else float("inf")
            )

            logger.info(f"Winning Trades: {len(winning_trades)} ({win_rate:.1%})")
            logger.info(f"Losing Trades: {len(losing_trades)}")
            logger.info(f"Average Win: ${avg_win:.2f}")
            logger.info(f"Average Loss: ${avg_loss:.2f}")
            logger.info(f"Profit Factor: {profit_factor:.2f}")

            # Show sample trades
            logger.info(
                f"""
📝 SAMPLE TRADES (First 5)
"""
            )
            for i, trade in enumerate(result.trades[:5]):
                entry_time = trade.entry_timestamp.strftime("%Y-%m-%d %H:%M")
                exit_time = (
                    trade.exit_timestamp.strftime("%Y-%m-%d %H:%M")
                    if trade.exit_timestamp
                    else "Open"
                )
                duration = (
                    (trade.exit_timestamp - trade.entry_timestamp).total_seconds()
                    / 3600
                    if trade.exit_timestamp
                    else 0
                )

                logger.info(
                    f"  {i+1}. {trade.side.value.upper()} | "
                    f"Entry: {entry_time} @ {trade.entry_price:.4f} | "
                    f"Exit: {exit_time} @ {trade.exit_price:.4f} | "
                    f"P&L: ${trade.pnl:.2f} ({trade.pnl_pct:.2f}%) | "
                    f"Duration: {duration:.1f}h"
                )

        # Buy and hold comparison
        bh_return = (
            self.features_data["close"].iloc[-1] / self.features_data["close"].iloc[0]
            - 1
        ) * 100
        logger.info(
            f"""
📊 BENCHMARK COMPARISON
Buy & Hold Return: {bh_return:.2f}%
Strategy Return: {result.total_return_pct:.2f}%
Outperformance: {result.total_return_pct - bh_return:.2f}%
"""
        )

        logger.info("✅ Analysis completed")

    def step_8_save_results(self):
        """Save results and model for future use."""
        logger.info("🔄 Step 8: Saving results...")

        # Create output directory
        output_dir = Path("output/ml_backtest_demo")
        output_dir.mkdir(parents=True, exist_ok=True)

        # Save model
        model_path = (
            output_dir
            / f"ml_model_{self.best_model_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pkl"
        )
        self.model.save(str(model_path))
        logger.info(f"   Model saved: {model_path}")

        # Save results summary
        results_summary = {
            "model_type": self.best_model_type,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "period_start": self.features_data.index[0].isoformat(),
            "period_end": self.features_data.index[-1].isoformat(),
            "initial_capital": self.backtest_result.initial_capital,
            "final_capital": self.backtest_result.final_capital,
            "total_return": self.backtest_result.total_return,
            "total_return_pct": self.backtest_result.total_return_pct,
            "trade_count": len(self.backtest_result.trades),
            "timestamp": datetime.now().isoformat(),
        }

        import json

        summary_path = (
            output_dir
            / f"backtest_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        with open(summary_path, "w") as f:
            json.dump(results_summary, f, indent=2)
        logger.info(f"   Summary saved: {summary_path}")

        # Save trades
        if self.backtest_result.trades:
            trades_data = []
            for trade in self.backtest_result.trades:
                trades_data.append(
                    {
                        "entry_time": trade.entry_timestamp.isoformat(),
                        "exit_time": (
                            trade.exit_timestamp.isoformat()
                            if trade.exit_timestamp
                            else None
                        ),
                        "side": trade.side.value,
                        "entry_price": trade.entry_price,
                        "exit_price": trade.exit_price,
                        "quantity": trade.quantity,
                        "pnl": trade.pnl,
                        "pnl_pct": trade.pnl_pct,
                    }
                )

            trades_df = pd.DataFrame(trades_data)
            trades_path = (
                output_dir / f"trades_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            )
            trades_df.to_csv(trades_path, index=False)
            logger.info(f"   Trades saved: {trades_path}")

        logger.info("✅ Results saved successfully")

    def run_demo(self):
        """Run the complete ML backtest demo."""
        logger.info("🚀 Starting FXML4 ML Backtest Demo")
        logger.info("=" * 60)

        try:
            self.step_1_generate_sample_data()
            self.step_2_feature_engineering()
            self.step_3_prepare_training_data()
            self.step_4_train_models()
            self.step_5_generate_signals()
            self.step_6_run_backtest()
            self.step_7_analyze_results()
            self.step_8_save_results()

            logger.info("=" * 60)
            logger.info("🎉 Demo completed successfully!")
            logger.info(
                "   Check the output/ml_backtest_demo/ directory for saved results"
            )

        except Exception as e:
            logger.error(f"❌ Demo failed: {e}")
            raise


def main():
    """Main function to run the demo."""
    demo = MLBacktestDemo()
    demo.run_demo()


if __name__ == "__main__":
    main()
