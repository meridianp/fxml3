"""
Integration tests for ML model building and backtesting pipeline.

This module tests the complete ML workflow from data ingestion through
model training, validation, and backtesting with realistic scenarios.
"""

import logging
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from fxml4.backtesting.backtest_engine import run_backtest
from fxml4.config import get_config
from fxml4.data_engineering.data_feeds.base_feed import DataFeedFactory
from fxml4.ml.features import create_technical_features
from fxml4.ml.models import ClassicMLModel, create_model
from fxml4.strategy.ml_signal_generator import MLSignalGenerator

logger = logging.getLogger(__name__)


class TestMLPipeline:
    """Test complete ML pipeline from data to backtest results."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test environment."""
        self.symbol = "EURUSD"
        self.timeframe = "4h"
        self.start_date = "2023-01-01"
        self.end_date = "2023-06-30"
        self.test_data = None
        self.model = None
        self.signal_generator = None

        # Create sample data for testing
        self._create_sample_data()

    def _create_sample_data(self):
        """Create realistic sample market data for testing."""
        # Generate 6 months of 4-hour data
        start = pd.to_datetime(self.start_date)
        end = pd.to_datetime(self.end_date)
        timestamps = pd.date_range(start=start, end=end, freq="4H")

        # Generate realistic OHLCV data with some trend and volatility
        np.random.seed(42)  # For reproducible tests
        n_periods = len(timestamps)

        # Start with a base price around 1.0500
        base_price = 1.0500

        # Generate price movements with trend and noise
        returns = np.random.normal(0.0001, 0.005, n_periods)  # Small positive drift
        log_prices = np.log(base_price) + np.cumsum(returns)
        close_prices = np.exp(log_prices)

        # Generate OHLC from close prices
        data = []
        for i, (timestamp, close) in enumerate(zip(timestamps, close_prices)):
            # Add some realistic OHLC spread
            volatility = np.random.uniform(0.0005, 0.002)
            high = close + np.random.uniform(0, volatility)
            low = close - np.random.uniform(0, volatility)

            if i == 0:
                open_price = close
            else:
                # Open is usually close to previous close with some gap
                gap = np.random.normal(0, 0.0002)
                open_price = close_prices[i - 1] + gap

            volume = np.random.randint(1000, 10000)

            data.append(
                {
                    "timestamp": timestamp,
                    "open": open_price,
                    "high": max(open_price, high, close),
                    "low": min(open_price, low, close),
                    "close": close,
                    "volume": volume,
                }
            )

        self.test_data = pd.DataFrame(data)
        self.test_data.set_index("timestamp", inplace=True)

        logger.info(
            f"Created sample data: {len(self.test_data)} records from {self.start_date} to {self.end_date}"
        )

    def test_01_data_validation(self):
        """Test that our sample data is valid for ML training."""
        assert self.test_data is not None
        assert len(self.test_data) > 100, "Need sufficient data for ML training"

        # Check for required columns
        required_columns = ["open", "high", "low", "close", "volume"]
        for col in required_columns:
            assert col in self.test_data.columns, f"Missing required column: {col}"

        # Check for data quality
        assert not self.test_data.isnull().any().any(), "Data contains null values"
        assert (
            self.test_data["high"] >= self.test_data["low"]
        ).all(), "High prices should be >= low prices"
        assert (
            self.test_data["high"] >= self.test_data["close"]
        ).all(), "High prices should be >= close prices"
        assert (
            self.test_data["low"] <= self.test_data["close"]
        ).all(), "Low prices should be <= close prices"

        logger.info("✅ Data validation passed")

    def test_02_feature_engineering(self):
        """Test feature engineering pipeline."""
        # Create technical features
        features_data = create_technical_features(
            self.test_data.copy(),
            indicators=["sma", "ema", "rsi", "macd", "bollinger", "atr"],
            ma_periods=[10, 20, 50],
            include_original=True,
        )

        # Validate features were created
        assert len(features_data.columns) > len(
            self.test_data.columns
        ), "Features should be added"

        # Check for key technical indicators
        expected_features = [
            "sma_10",
            "sma_20",
            "sma_50",
            "ema_10",
            "ema_20",
            "ema_50",
            "rsi_14",
            "macd",
            "macd_signal",
            "bb_upper",
            "bb_lower",
            "bb_width",
            "atr_14",
        ]

        for feature in expected_features:
            assert (
                feature in features_data.columns
            ), f"Missing expected feature: {feature}"

        # Check that features have reasonable values
        assert (
            features_data["rsi_14"].dropna().between(0, 100).all()
        ), "RSI should be between 0 and 100"
        assert features_data["atr_14"].dropna().gt(0).all(), "ATR should be positive"

        # Store for next tests
        self.features_data = features_data

        logger.info(
            f"✅ Feature engineering passed - created {len(features_data.columns)} features"
        )

    def test_03_ml_model_training(self):
        """Test ML model training with created features."""
        # Prepare data for training
        features_data = self.features_data.copy()

        # Create target variable (next period return)
        features_data["next_return"] = (
            features_data["close"].shift(-1) / features_data["close"] - 1
        )

        # Create classification labels (buy/hold/sell)
        def create_labels(returns, buy_threshold=0.002, sell_threshold=-0.002):
            labels = np.zeros(len(returns))
            labels[returns > buy_threshold] = 1  # Buy signal
            labels[returns < sell_threshold] = 2  # Sell signal
            return labels

        features_data["target"] = create_labels(features_data["next_return"])

        # Remove rows with NaN values
        features_data = features_data.dropna()

        assert len(features_data) > 50, "Need sufficient data after cleaning"

        # Select feature columns (exclude price and target columns)
        feature_columns = [
            col
            for col in features_data.columns
            if col
            not in ["open", "high", "low", "close", "volume", "next_return", "target"]
        ]

        X = features_data[feature_columns]
        y = features_data["target"]

        # Split data for training/testing
        split_idx = int(len(features_data) * 0.7)
        X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
        y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]

        logger.info(
            f"Training data: {len(X_train)} samples, {len(feature_columns)} features"
        )
        logger.info(f"Test data: {len(X_test)} samples")

        # Test different model types
        model_types = ["random_forest", "xgboost", "logistic_regression"]

        for model_type in model_types:
            logger.info(f"Testing {model_type} model...")

            # Create and train model
            model = create_model(model_type=model_type, n_classes=3)
            assert model is not None, f"Failed to create {model_type} model"

            # Train model
            model.fit(X_train, y_train)

            # Test prediction
            predictions = model.predict(X_test)
            probabilities = model.predict_proba(X_test)

            # Validate predictions
            assert len(predictions) == len(X_test), "Prediction length mismatch"
            assert probabilities.shape == (len(X_test), 3), "Probability shape mismatch"
            assert set(predictions).issubset({0, 1, 2}), "Invalid prediction values"

            # Check model performance (basic sanity checks)
            accuracy = (predictions == y_test).mean()
            logger.info(f"{model_type} accuracy: {accuracy:.3f}")

            # Store the best performing model for backtesting
            if not hasattr(self, "best_model") or accuracy > self.best_accuracy:
                self.best_model = model
                self.best_accuracy = accuracy
                self.best_model_type = model_type

        logger.info(
            f"✅ ML model training passed - best model: {self.best_model_type} (accuracy: {self.best_accuracy:.3f})"
        )

    def test_04_signal_generation(self):
        """Test signal generation from trained model."""
        # Create signal generator
        config = {
            "threshold": 0.6,
            "probability_mode": True,
            "use_technical_features": True,
        }

        self.signal_generator = MLSignalGenerator(self.best_model, config)

        # Generate signals on test data
        signals = self.signal_generator.generate_signals(
            self.features_data, symbol=self.symbol, timeframe=self.timeframe
        )

        # Validate signals
        assert len(signals) > 0, "Should generate some signals"

        for signal in signals:
            # Check signal structure
            assert hasattr(signal, "signal_type"), "Signal should have signal_type"
            assert hasattr(signal, "confidence"), "Signal should have confidence"
            assert hasattr(signal, "timestamp"), "Signal should have timestamp"
            assert hasattr(signal, "price"), "Signal should have price"

            # Check signal values
            assert (
                0 <= signal.confidence <= 1
            ), f"Invalid confidence: {signal.confidence}"
            assert signal.price > 0, f"Invalid price: {signal.price}"
            assert signal.signal_type.value in [
                "entry_long",
                "entry_short",
                "exit_long",
                "exit_short",
            ], f"Invalid signal type: {signal.signal_type.value}"

        logger.info(f"✅ Signal generation passed - generated {len(signals)} signals")

    def test_05_backtest_execution(self):
        """Test complete backtest execution with ML strategy."""

        # Create ML strategy function
        def ml_strategy(data, index, params):
            """ML-based strategy for backtesting."""
            signals = {}

            # Get historical data up to current point
            historical_data = data.iloc[: index + 1]

            # Need minimum data for signal generation
            if len(historical_data) < 50:
                return signals

            try:
                # Generate signals using ML model
                ml_signals = self.signal_generator.generate_signals(
                    historical_data,
                    symbol=params.get("symbol", "UNKNOWN"),
                    timeframe=params.get("timeframe", "UNKNOWN"),
                )

                # Process the latest signal
                if ml_signals:
                    latest_signal = ml_signals[-1]

                    if latest_signal.signal_type.value == "entry_long":
                        signals["entry"] = True
                        signals["direction"] = "buy"
                        signals["risk_pct"] = params.get("risk_pct", 0.02)
                    elif latest_signal.signal_type.value == "entry_short":
                        signals["entry"] = True
                        signals["direction"] = "sell"
                        signals["risk_pct"] = params.get("risk_pct", 0.02)
                    elif latest_signal.signal_type.value in ["exit_long", "exit_short"]:
                        signals["exit"] = True

            except Exception as e:
                logger.warning(f"Signal generation error at index {index}: {e}")

            return signals

        # Backtest configuration
        backtest_config = {
            "initial_capital": 10000.0,
            "commission": 0.0002,  # 2 pips
            "slippage": 0.0001,  # 1 pip
        }

        strategy_params = {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "risk_pct": 0.02,
            "model_type": self.best_model_type,
        }

        # Run backtest
        logger.info("Running backtest with ML strategy...")
        result = run_backtest(
            strategy=ml_strategy,
            data=self.features_data,
            strategy_params=strategy_params,
            config=backtest_config,
        )

        # Validate backtest results
        assert result is not None, "Backtest should return results"
        assert hasattr(result, "final_capital"), "Result should have final_capital"
        assert hasattr(result, "total_return"), "Result should have total_return"
        assert hasattr(
            result, "total_return_pct"
        ), "Result should have total_return_pct"
        assert hasattr(result, "trades"), "Result should have trades"

        # Check result values
        assert result.final_capital > 0, "Final capital should be positive"
        assert isinstance(result.trades, list), "Trades should be a list"

        # Log results
        logger.info(f"Backtest Results:")
        logger.info(f"  Initial Capital: ${result.initial_capital:,.2f}")
        logger.info(f"  Final Capital: ${result.final_capital:,.2f}")
        logger.info(f"  Total Return: {result.total_return_pct:.2f}%")
        logger.info(f"  Number of Trades: {len(result.trades)}")

        if hasattr(result, "sharpe_ratio"):
            logger.info(f"  Sharpe Ratio: {result.sharpe_ratio:.3f}")
        if hasattr(result, "max_drawdown_pct"):
            logger.info(f"  Max Drawdown: {result.max_drawdown_pct:.2f}%")

        self.backtest_result = result

        logger.info("✅ Backtest execution passed")

    def test_06_performance_analysis(self):
        """Test performance analysis and reporting."""
        result = self.backtest_result

        # Test basic performance metrics
        assert hasattr(result, "total_return_pct"), "Should have return percentage"
        assert hasattr(result, "sharpe_ratio"), "Should have Sharpe ratio"
        assert hasattr(result, "max_drawdown_pct"), "Should have max drawdown"

        # Test trade analysis
        if len(result.trades) > 0:
            # Check trade structure
            for trade in result.trades[:5]:  # Check first 5 trades
                assert hasattr(trade, "entry_price"), "Trade should have entry_price"
                assert hasattr(trade, "exit_price"), "Trade should have exit_price"
                assert hasattr(trade, "pnl"), "Trade should have pnl"
                assert hasattr(trade, "pnl_pct"), "Trade should have pnl_pct"

                assert trade.entry_price > 0, "Entry price should be positive"
                if trade.exit_price:
                    assert trade.exit_price > 0, "Exit price should be positive"

        # Test equity curve
        if hasattr(result, "equity_curve") and result.equity_curve is not None:
            assert len(result.equity_curve) > 0, "Equity curve should have data"
            assert (
                "equity" in result.equity_curve.columns
            ), "Equity curve should have equity column"

        logger.info("✅ Performance analysis passed")

    def test_07_model_persistence(self):
        """Test saving and loading trained models."""
        with tempfile.TemporaryDirectory() as temp_dir:
            model_path = Path(temp_dir) / "test_model.pkl"

            # Save model
            self.best_model.save(str(model_path))
            assert model_path.exists(), "Model file should be created"

            # Load model
            loaded_model = create_model(model_type=self.best_model_type, n_classes=3)
            loaded_model.load(str(model_path))

            # Test that loaded model works
            test_features = (
                self.features_data.select_dtypes(include=[np.number])
                .dropna()
                .iloc[-10:]
            )
            feature_columns = [
                col
                for col in test_features.columns
                if col not in ["open", "high", "low", "close", "volume"]
            ]
            test_X = test_features[feature_columns]

            original_predictions = self.best_model.predict(test_X)
            loaded_predictions = loaded_model.predict(test_X)

            # Predictions should be identical
            np.testing.assert_array_equal(
                original_predictions,
                loaded_predictions,
                "Loaded model should produce same predictions",
            )

        logger.info("✅ Model persistence passed")


class TestBacktestIntegration:
    """Test backtesting integration with different strategies and scenarios."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test environment."""
        self.sample_data = self._create_test_data()

    def _create_test_data(self):
        """Create test data with known patterns."""
        # Create data with trending pattern for testing
        dates = pd.date_range("2023-01-01", "2023-03-31", freq="1H")
        np.random.seed(123)

        # Create uptrend data
        base_price = 1.0500
        trend = np.linspace(0, 0.02, len(dates))  # 2% uptrend
        noise = np.random.normal(0, 0.001, len(dates))
        prices = base_price * (1 + trend + noise)

        data = pd.DataFrame(
            {
                "timestamp": dates,
                "open": prices,
                "high": prices * (1 + np.random.uniform(0, 0.002, len(dates))),
                "low": prices * (1 - np.random.uniform(0, 0.002, len(dates))),
                "close": prices,
                "volume": np.random.randint(1000, 5000, len(dates)),
            }
        )

        data.set_index("timestamp", inplace=True)
        return data

    def test_simple_strategy_backtest(self):
        """Test backtest with simple moving average strategy."""

        def simple_ma_strategy(data, index, params):
            """Simple moving average crossover strategy."""
            signals = {}

            if index < 50:  # Need enough data for MA calculation
                return signals

            # Calculate short and long moving averages
            short_window = params.get("short_window", 10)
            long_window = params.get("long_window", 30)

            recent_data = data.iloc[max(0, index - long_window) : index + 1]

            if len(recent_data) >= long_window:
                short_ma = recent_data["close"].tail(short_window).mean()
                long_ma = recent_data["close"].tail(long_window).mean()
                prev_short_ma = recent_data["close"].iloc[-short_window - 1 : -1].mean()
                prev_long_ma = recent_data["close"].iloc[-long_window - 1 : -1].mean()

                # Golden cross - buy signal
                if short_ma > long_ma and prev_short_ma <= prev_long_ma:
                    signals["entry"] = True
                    signals["direction"] = "buy"
                    signals["risk_pct"] = 0.02

                # Death cross - sell signal
                elif short_ma < long_ma and prev_short_ma >= prev_long_ma:
                    signals["entry"] = True
                    signals["direction"] = "sell"
                    signals["risk_pct"] = 0.02

            return signals

        # Run backtest
        result = run_backtest(
            strategy=simple_ma_strategy,
            data=self.sample_data,
            strategy_params={"short_window": 10, "long_window": 30},
            config={"initial_capital": 10000, "commission": 0.0001},
        )

        assert result is not None
        assert result.final_capital > 0
        logger.info(f"Simple MA strategy return: {result.total_return_pct:.2f}%")

    def test_multiple_strategy_comparison(self):
        """Test comparing multiple strategies."""
        strategies = {
            "ma_fast": {"short_window": 5, "long_window": 15},
            "ma_medium": {"short_window": 10, "long_window": 30},
            "ma_slow": {"short_window": 20, "long_window": 50},
        }

        def ma_strategy(data, index, params):
            """Parameterized MA strategy."""
            signals = {}
            short_window = params["short_window"]
            long_window = params["long_window"]

            if index < long_window:
                return signals

            recent_data = data.iloc[max(0, index - long_window) : index + 1]

            if len(recent_data) >= long_window:
                short_ma = recent_data["close"].tail(short_window).mean()
                long_ma = recent_data["close"].tail(long_window).mean()

                # Simple crossover logic
                if short_ma > long_ma * 1.001:  # 0.1% threshold
                    signals["entry"] = True
                    signals["direction"] = "buy"
                    signals["risk_pct"] = 0.01
                elif short_ma < long_ma * 0.999:
                    signals["entry"] = True
                    signals["direction"] = "sell"
                    signals["risk_pct"] = 0.01

            return signals

        results = {}
        for strategy_name, params in strategies.items():
            result = run_backtest(
                strategy=ma_strategy,
                data=self.sample_data,
                strategy_params=params,
                config={"initial_capital": 10000, "commission": 0.0001},
            )

            results[strategy_name] = {
                "return_pct": result.total_return_pct,
                "final_capital": result.final_capital,
                "trade_count": len(result.trades),
            }

        # Log comparison
        logger.info("Strategy Comparison:")
        for name, metrics in results.items():
            logger.info(
                f"  {name}: {metrics['return_pct']:.2f}% ({metrics['trade_count']} trades)"
            )

        assert len(results) == len(strategies)

    def test_risk_management(self):
        """Test risk management features in backtesting."""

        def risky_strategy(data, index, params):
            """Strategy that tests risk management."""
            signals = {}

            if index % 20 == 0:  # Signal every 20 periods
                signals["entry"] = True
                signals["direction"] = "buy" if index % 40 == 0 else "sell"
                signals["risk_pct"] = params.get("risk_pct", 0.05)  # 5% risk per trade
                signals["stop_loss"] = params.get("stop_loss", 0.02)  # 2% stop loss
                signals["take_profit"] = params.get(
                    "take_profit", 0.04
                )  # 4% take profit

            return signals

        # Test with different risk parameters
        risk_configs = [
            {"risk_pct": 0.01, "stop_loss": 0.01, "take_profit": 0.02},
            {"risk_pct": 0.03, "stop_loss": 0.02, "take_profit": 0.04},
            {"risk_pct": 0.05, "stop_loss": 0.03, "take_profit": 0.06},
        ]

        for i, risk_params in enumerate(risk_configs):
            result = run_backtest(
                strategy=risky_strategy,
                data=self.sample_data,
                strategy_params=risk_params,
                config={"initial_capital": 10000, "commission": 0.0001},
            )

            logger.info(
                f"Risk config {i+1}: {result.total_return_pct:.2f}% "
                f"(Max DD: {result.max_drawdown_pct:.2f}%)"
            )

            # Higher risk should not necessarily mean higher returns due to risk management
            assert result.final_capital > 0


@pytest.mark.integration
class TestEndToEndMLPipeline:
    """End-to-end integration test of the complete ML and backtesting pipeline."""

    def test_complete_pipeline(self):
        """Test the complete pipeline from data to backtested results."""
        logger.info("🚀 Starting end-to-end ML pipeline test...")

        # Step 1: Initialize test pipeline
        pipeline = TestMLPipeline()
        pipeline.setup()

        # Step 2: Run all pipeline steps
        try:
            pipeline.test_01_data_validation()
            pipeline.test_02_feature_engineering()
            pipeline.test_03_ml_model_training()
            pipeline.test_04_signal_generation()
            pipeline.test_05_backtest_execution()
            pipeline.test_06_performance_analysis()
            pipeline.test_07_model_persistence()

            logger.info("✅ Complete end-to-end pipeline test PASSED")

            # Log final results
            result = pipeline.backtest_result
            logger.info(
                f"""
📊 Final Pipeline Results:
   Model Type: {pipeline.best_model_type}
   Model Accuracy: {pipeline.best_accuracy:.3f}
   Backtest Return: {result.total_return_pct:.2f}%
   Number of Trades: {len(result.trades)}
   Sharpe Ratio: {getattr(result, 'sharpe_ratio', 'N/A')}
   Max Drawdown: {getattr(result, 'max_drawdown_pct', 'N/A')}%
            """
            )

        except Exception as e:
            logger.error(f"❌ Pipeline test FAILED: {e}")
            raise


# Pytest markers for test categorization
pytestmark = [
    pytest.mark.integration,
    pytest.mark.ml,
    pytest.mark.slow,
    pytest.mark.requires_api,
]


if __name__ == "__main__":
    # Configure logging for standalone execution
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Run tests
    pytest.main([__file__, "-v", "-s"])
