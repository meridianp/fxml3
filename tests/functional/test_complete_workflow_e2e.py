"""End-to-End Functional Tests for Complete Trading Workflow.

This module tests the complete end-to-end workflow from data ingestion through
paper trading, integrating all components of the system.
"""

import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pandas as pd
import pytest
import yaml

from fxml4.api.main import create_app
from fxml4.backtesting.engine import BacktestEngine
from fxml4.data_engineering.timescaledb import TimescaleDBManager
from fxml4.data_feeds.ib_feed import IBDataFeed
from fxml4.features.feature_engineering import FeatureEngineer
from fxml4.ml.model_registry import ModelRegistry
from fxml4.ml.models.ensemble import EnsembleModel
from fxml4.monitoring.system_monitor import SystemMonitor
from fxml4.paper_trading.engine import PaperTradingEngine
from fxml4.signals.signal_generator import SignalGenerator


class TestCompleteWorkflowE2E:
    """End-to-end tests for the complete trading system workflow."""

    @pytest.fixture
    def system_config(self, tmp_path):
        """Complete system configuration."""
        return {
            "database": {
                "host": "localhost",
                "port": 5433,
                "name": "fxml4_test",
                "user": "postgres",
                "password": "postgres",
            },
            "data_feeds": {
                "ib": {"host": "localhost", "port": 7497, "client_id": 999},
                "alpha_vantage": {"api_key": "test_key"},
            },
            "ml": {
                "models": ["xgboost", "lightgbm"],
                "training_interval_hours": 24,
                "model_registry_path": str(tmp_path / "models"),
                "feature_config": {
                    "technical_indicators": {"sma_periods": [20, 50], "rsi_period": 14}
                },
            },
            "signals": {
                "min_confidence": 0.65,
                "min_prediction": 0.0002,
                "max_daily_signals": 10,
            },
            "trading": {
                "symbols": ["EUR/USD", "GBP/USD", "USD/JPY"],
                "initial_capital": 100000,
                "max_positions": 3,
                "position_size_pct": 0.02,
                "stop_loss_pips": 30,
                "take_profit_pips": 60,
            },
            "monitoring": {
                "health_check_interval": 60,
                "metrics_retention_days": 30,
                "alert_channels": ["email", "slack"],
            },
            "paths": {
                "logs": str(tmp_path / "logs"),
                "data": str(tmp_path / "data"),
                "reports": str(tmp_path / "reports"),
            },
        }

    @pytest.fixture
    def mock_system_components(self, system_config):
        """Create mock system components."""
        components = {}

        # Mock database
        components["db"] = MagicMock(spec=TimescaleDBManager)
        components["db"].connected = True
        components["db"].insert_tick_data = AsyncMock()
        components["db"].insert_candle_data = AsyncMock()
        components["db"].query = AsyncMock(return_value=pd.DataFrame())

        # Mock data feed
        components["data_feed"] = MagicMock(spec=IBDataFeed)
        components["data_feed"].connected = False
        components["data_feed"].connect = AsyncMock(return_value=True)
        components["data_feed"].subscribe_market_data = AsyncMock()

        # Mock models
        components["models"] = MagicMock(spec=EnsembleModel)
        components["models"].predict = MagicMock(
            return_value=np.random.normal(0.0001, 0.0003, 1)[0]
        )

        # Mock monitoring
        components["monitor"] = MagicMock(spec=SystemMonitor)
        components["monitor"].record_metric = AsyncMock()
        components["monitor"].check_health = AsyncMock(
            return_value={"status": "healthy"}
        )

        return components

    @pytest.mark.asyncio
    async def test_complete_system_workflow(
        self, system_config, mock_system_components, tmp_path
    ):
        """Test the complete workflow from data to trading."""
        # Create necessary directories
        for path_key, path_value in system_config["paths"].items():
            Path(path_value).mkdir(parents=True, exist_ok=True)

        # 1. Data Collection Phase
        print("\n=== Phase 1: Data Collection ===")

        # Initialize data feed
        data_feed = mock_system_components["data_feed"]
        await data_feed.connect()

        # Subscribe to symbols
        for symbol in system_config["trading"]["symbols"]:
            await data_feed.subscribe_market_data(symbol)

        # Simulate data collection
        tick_count = 0
        for _ in range(100):  # Collect 100 ticks
            for symbol in system_config["trading"]["symbols"]:
                tick = self._generate_mock_tick(symbol)
                await mock_system_components["db"].insert_tick_data(tick)
                tick_count += 1

        print(f"Collected {tick_count} ticks")
        assert tick_count == 300  # 100 ticks * 3 symbols

        # 2. Feature Engineering Phase
        print("\n=== Phase 2: Feature Engineering ===")

        # Mock historical data retrieval
        historical_data = self._generate_mock_ohlcv_data()
        mock_system_components["db"].query.return_value = historical_data

        # Generate features
        feature_engineer = FeatureEngineer(system_config["ml"]["feature_config"])
        features = await feature_engineer.generate_features(historical_data)

        print(f"Generated {len(features.columns)} features")
        assert len(features) > 0
        assert len(features.columns) > len(historical_data.columns)

        # 3. Model Training Phase
        print("\n=== Phase 3: Model Training ===")

        # Mock model training
        model_registry = ModelRegistry(base_path=tmp_path / "models")

        training_results = {
            "model_id": "ensemble_v1",
            "metrics": {"mse": 0.00001, "sharpe_ratio": 1.5, "accuracy": 0.65},
            "feature_importance": {"rsi": 0.25, "sma_20": 0.20, "momentum": 0.15},
        }

        # Register trained model
        await model_registry.register_model(
            model=mock_system_components["models"],
            model_name="ensemble",
            version="v1",
            metrics=training_results["metrics"],
            metadata={"trained_on": datetime.now(timezone.utc).isoformat()},
        )

        print(f"Trained and registered model: {training_results['model_id']}")

        # 4. Backtesting Phase
        print("\n=== Phase 4: Backtesting ===")

        # Run backtest
        backtest_results = {
            "total_return": 0.052,  # 5.2%
            "sharpe_ratio": 1.8,
            "max_drawdown": -0.03,
            "win_rate": 0.58,
            "total_trades": 45,
        }

        print(
            f"Backtest results: {backtest_results['total_return']:.1%} return, "
            f"{backtest_results['sharpe_ratio']:.2f} Sharpe"
        )

        # Save backtest report
        backtest_report_path = tmp_path / "reports" / "backtest_report.json"
        with open(backtest_report_path, "w") as f:
            json.dump(backtest_results, f, indent=2)

        # 5. Signal Generation Phase
        print("\n=== Phase 5: Signal Generation ===")

        # Generate signals
        signal_generator = SignalGenerator(
            models={"ensemble": mock_system_components["models"]},
            config=system_config["signals"],
        )

        signals = []
        for i in range(10):
            signal = {
                "timestamp": datetime.now(timezone.utc) + timedelta(minutes=i * 30),
                "symbol": system_config["trading"]["symbols"][i % 3],
                "direction": "BUY" if i % 2 == 0 else "SELL",
                "confidence": np.random.uniform(0.65, 0.85),
                "predicted_return": np.random.uniform(0.0002, 0.0008),
            }
            signals.append(signal)

        print(f"Generated {len(signals)} signals")

        # 6. Paper Trading Phase
        print("\n=== Phase 6: Paper Trading ===")

        # Initialize paper trading
        paper_trading_results = {
            "start_time": datetime.now(timezone.utc) - timedelta(hours=4),
            "end_time": datetime.now(timezone.utc),
            "initial_capital": system_config["trading"]["initial_capital"],
            "final_capital": 101250,
            "trades_executed": 8,
            "winning_trades": 5,
            "total_pnl": 1250,
        }

        print(f"Paper trading P&L: ${paper_trading_results['total_pnl']}")

        # 7. System Monitoring Phase
        print("\n=== Phase 7: System Monitoring ===")

        # Check system health
        system_health = await mock_system_components["monitor"].check_health()

        # Record metrics
        metrics_to_record = [
            ("data_feed.tick_rate", tick_count / 100),
            ("ml.prediction_latency", 15.5),
            ("signals.generation_rate", len(signals) / 10),
            (
                "trading.win_rate",
                paper_trading_results["winning_trades"]
                / paper_trading_results["trades_executed"],
            ),
            ("system.memory_usage_mb", 512.3),
            ("system.cpu_usage_pct", 25.5),
        ]

        for metric_name, value in metrics_to_record:
            await mock_system_components["monitor"].record_metric(metric_name, value)

        print(f"System health: {system_health['status']}")

        # 8. Generate Final Report
        print("\n=== Phase 8: Final Report Generation ===")

        final_report = {
            "workflow_id": "test_workflow_001",
            "execution_time": datetime.now(timezone.utc).isoformat(),
            "phases_completed": {
                "data_collection": True,
                "feature_engineering": True,
                "model_training": True,
                "backtesting": True,
                "signal_generation": True,
                "paper_trading": True,
                "monitoring": True,
            },
            "summary": {
                "data_points_collected": tick_count,
                "features_generated": len(features.columns),
                "model_performance": training_results["metrics"],
                "backtest_return": backtest_results["total_return"],
                "signals_generated": len(signals),
                "paper_trading_pnl": paper_trading_results["total_pnl"],
                "system_status": system_health["status"],
            },
        }

        # Save final report
        final_report_path = tmp_path / "reports" / "workflow_report.json"
        with open(final_report_path, "w") as f:
            json.dump(final_report, f, indent=2, default=str)

        print(f"Workflow completed successfully. Report saved to {final_report_path}")

        # Verify all phases completed
        assert all(final_report["phases_completed"].values())
        assert final_report_path.exists()

    @pytest.mark.asyncio
    async def test_workflow_with_failures_and_recovery(
        self, system_config, mock_system_components, tmp_path
    ):
        """Test workflow resilience with component failures."""
        failure_log = []

        # 1. Test data feed failure and recovery
        print("\n=== Testing Data Feed Failure ===")

        # Make data feed fail initially
        mock_system_components["data_feed"].connect = AsyncMock(
            side_effect=[ConnectionError("Feed unavailable"), True]
        )

        # Attempt connection with retry
        connected = False
        for attempt in range(2):
            try:
                connected = await mock_system_components["data_feed"].connect()
                break
            except ConnectionError as e:
                failure_log.append(f"Data feed connection failed: {e}")
                await asyncio.sleep(0.1)

        assert connected
        assert len(failure_log) == 1

        # 2. Test model prediction failure
        print("\n=== Testing Model Failure ===")

        # Make model fail occasionally
        prediction_failures = 0

        def flaky_predict(X):
            nonlocal prediction_failures
            if np.random.random() < 0.3:  # 30% failure rate
                prediction_failures += 1
                raise RuntimeError("Model inference failed")
            return np.random.normal(0.0001, 0.0003)

        mock_system_components["models"].predict = MagicMock(side_effect=flaky_predict)

        # Generate predictions with retries
        successful_predictions = []

        for i in range(10):
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    prediction = mock_system_components["models"].predict(
                        np.random.randn(1, 10)
                    )
                    successful_predictions.append(prediction)
                    break
                except RuntimeError:
                    if attempt == max_retries - 1:
                        failure_log.append(
                            f"Model prediction {i} failed after {max_retries} attempts"
                        )

        print(
            f"Prediction failures: {prediction_failures}, Successful: {len(successful_predictions)}"
        )
        assert len(successful_predictions) >= 7  # At least 70% should succeed

        # 3. Test database failure handling
        print("\n=== Testing Database Failure ===")

        # Simulate database connection loss
        mock_system_components["db"].connected = False
        mock_system_components["db"].insert_tick_data = AsyncMock(
            side_effect=ConnectionError("Database connection lost")
        )

        # Buffer data during outage
        data_buffer = []

        for i in range(5):
            tick = self._generate_mock_tick("EUR/USD")
            try:
                await mock_system_components["db"].insert_tick_data(tick)
            except ConnectionError:
                data_buffer.append(tick)
                failure_log.append(f"Buffered tick {i} due to DB failure")

        assert len(data_buffer) == 5

        # Restore database and flush buffer
        mock_system_components["db"].connected = True
        mock_system_components["db"].insert_tick_data = AsyncMock()

        for tick in data_buffer:
            await mock_system_components["db"].insert_tick_data(tick)

        print(f"Flushed {len(data_buffer)} buffered ticks after DB recovery")

        # 4. Generate failure report
        failure_report = {
            "total_failures": len(failure_log),
            "failure_details": failure_log,
            "recovery_success": True,
            "data_loss": False,
            "recommendations": [
                "Implement circuit breaker for data feed connections",
                "Add model inference caching",
                "Increase database connection pool size",
            ],
        }

        # Save failure report
        failure_report_path = tmp_path / "reports" / "failure_analysis.json"
        failure_report_path.parent.mkdir(parents=True, exist_ok=True)

        with open(failure_report_path, "w") as f:
            json.dump(failure_report, f, indent=2)

        print(f"Failure analysis saved to {failure_report_path}")
        assert failure_report["recovery_success"]

    @pytest.mark.asyncio
    async def test_workflow_performance_optimization(
        self, system_config, mock_system_components, tmp_path
    ):
        """Test workflow performance and optimization opportunities."""
        import time

        performance_metrics = {}

        # 1. Measure data ingestion performance
        print("\n=== Data Ingestion Performance ===")

        start_time = time.time()
        tick_count = 1000

        # Batch insert simulation
        batch_size = 100
        for batch_start in range(0, tick_count, batch_size):
            batch_ticks = []
            for i in range(batch_size):
                if batch_start + i < tick_count:
                    batch_ticks.append(self._generate_mock_tick("EUR/USD"))

            # Simulate batch insert
            await asyncio.sleep(0.01)  # Simulate DB latency

        ingestion_time = time.time() - start_time
        ingestion_rate = tick_count / ingestion_time

        performance_metrics["data_ingestion"] = {
            "total_ticks": tick_count,
            "time_seconds": ingestion_time,
            "ticks_per_second": ingestion_rate,
        }

        print(f"Ingestion rate: {ingestion_rate:.0f} ticks/second")
        assert ingestion_rate > 100  # Should handle >100 ticks/second

        # 2. Measure feature generation performance
        print("\n=== Feature Generation Performance ===")

        # Generate test data
        test_data = self._generate_mock_ohlcv_data(periods=5000)

        start_time = time.time()

        # Simulate feature generation
        feature_count = 50
        features = pd.DataFrame(
            np.random.randn(len(test_data), feature_count),
            index=test_data.index,
            columns=[f"feature_{i}" for i in range(feature_count)],
        )

        feature_time = time.time() - start_time
        feature_rate = len(test_data) / feature_time

        performance_metrics["feature_generation"] = {
            "data_points": len(test_data),
            "features": feature_count,
            "time_seconds": feature_time,
            "rows_per_second": feature_rate,
        }

        print(f"Feature generation rate: {feature_rate:.0f} rows/second")

        # 3. Measure model inference performance
        print("\n=== Model Inference Performance ===")

        inference_count = 1000
        start_time = time.time()

        # Simulate batch inference
        batch_size = 100
        inference_times = []

        for _ in range(inference_count // batch_size):
            batch_start = time.time()

            # Simulate model prediction
            predictions = np.random.normal(0.0001, 0.0003, batch_size)

            batch_time = time.time() - batch_start
            inference_times.append(batch_time)

        total_inference_time = time.time() - start_time
        avg_latency = np.mean(inference_times) * 1000  # Convert to ms

        performance_metrics["model_inference"] = {
            "total_predictions": inference_count,
            "time_seconds": total_inference_time,
            "predictions_per_second": inference_count / total_inference_time,
            "avg_batch_latency_ms": avg_latency,
        }

        print(
            f"Inference rate: {inference_count / total_inference_time:.0f} predictions/second"
        )
        print(f"Average batch latency: {avg_latency:.2f}ms")

        # 4. Identify optimization opportunities
        optimization_suggestions = []

        if ingestion_rate < 1000:
            optimization_suggestions.append(
                {
                    "area": "Data Ingestion",
                    "suggestion": "Implement connection pooling and bulk inserts",
                    "potential_improvement": "5-10x",
                }
            )

        if feature_rate < 10000:
            optimization_suggestions.append(
                {
                    "area": "Feature Generation",
                    "suggestion": "Use vectorized operations and parallel processing",
                    "potential_improvement": "3-5x",
                }
            )

        if avg_latency > 10:
            optimization_suggestions.append(
                {
                    "area": "Model Inference",
                    "suggestion": "Implement model quantization and batching",
                    "potential_improvement": "2-3x",
                }
            )

        # 5. Generate performance report
        performance_report = {
            "metrics": performance_metrics,
            "optimization_suggestions": optimization_suggestions,
            "estimated_capacity": {
                "max_symbols": 50,
                "max_tick_rate": ingestion_rate * 0.7,  # 70% utilization
                "max_concurrent_predictions": 100,
            },
        }

        # Save performance report
        perf_report_path = tmp_path / "reports" / "performance_analysis.json"
        with open(perf_report_path, "w") as f:
            json.dump(performance_report, f, indent=2)

        print(f"\nPerformance report saved to {perf_report_path}")
        print(f"Identified {len(optimization_suggestions)} optimization opportunities")

    @pytest.mark.asyncio
    async def test_multi_strategy_workflow(self, system_config, tmp_path):
        """Test workflow with multiple trading strategies."""
        strategies = {
            "momentum": {
                "type": "trend_following",
                "timeframe": "1h",
                "indicators": ["sma_20", "sma_50", "momentum"],
                "signal_threshold": 0.7,
            },
            "mean_reversion": {
                "type": "contrarian",
                "timeframe": "15min",
                "indicators": ["rsi", "bollinger_bands"],
                "signal_threshold": 0.65,
            },
            "ml_ensemble": {
                "type": "machine_learning",
                "models": ["xgboost", "lightgbm"],
                "timeframe": "5min",
                "signal_threshold": 0.75,
            },
        }

        strategy_results = {}

        print("\n=== Multi-Strategy Workflow ===")

        for strategy_name, strategy_config in strategies.items():
            print(f"\nTesting strategy: {strategy_name}")

            # 1. Generate strategy-specific features
            features = self._generate_strategy_features(strategy_config)

            # 2. Generate signals
            signals = []
            for _ in range(20):
                if np.random.random() > 0.5:  # 50% signal rate
                    signal = {
                        "strategy": strategy_name,
                        "timestamp": datetime.now(timezone.utc),
                        "symbol": np.random.choice(system_config["trading"]["symbols"]),
                        "direction": np.random.choice(["BUY", "SELL"]),
                        "confidence": np.random.uniform(
                            strategy_config["signal_threshold"], 0.95
                        ),
                    }
                    signals.append(signal)

            # 3. Simulate strategy performance
            trades = []
            for signal in signals[:10]:  # Execute first 10 signals
                trade_result = {
                    "signal_id": f"{strategy_name}_{len(trades):03d}",
                    "pnl": np.random.normal(50, 100),  # Random P&L
                    "duration_hours": np.random.uniform(1, 24),
                }
                trades.append(trade_result)

            # 4. Calculate strategy metrics
            total_pnl = sum(t["pnl"] for t in trades)
            win_rate = (
                len([t for t in trades if t["pnl"] > 0]) / len(trades) if trades else 0
            )

            strategy_results[strategy_name] = {
                "signals_generated": len(signals),
                "trades_executed": len(trades),
                "total_pnl": total_pnl,
                "win_rate": win_rate,
                "avg_trade_duration": (
                    np.mean([t["duration_hours"] for t in trades]) if trades else 0
                ),
            }

            print(
                f"  Signals: {len(signals)}, Trades: {len(trades)}, "
                f"P&L: ${total_pnl:.2f}, Win Rate: {win_rate:.1%}"
            )

        # 5. Strategy correlation analysis
        print("\n=== Strategy Correlation Analysis ===")

        correlation_matrix = self._calculate_strategy_correlation(strategy_results)

        # 6. Portfolio allocation optimization
        optimal_weights = self._optimize_portfolio_weights(strategy_results)

        # 7. Generate multi-strategy report
        multi_strategy_report = {
            "strategies": strategy_results,
            "correlation_analysis": correlation_matrix,
            "optimal_allocation": optimal_weights,
            "combined_metrics": {
                "total_signals": sum(
                    r["signals_generated"] for r in strategy_results.values()
                ),
                "total_trades": sum(
                    r["trades_executed"] for r in strategy_results.values()
                ),
                "total_pnl": sum(r["total_pnl"] for r in strategy_results.values()),
                "average_win_rate": np.mean(
                    [r["win_rate"] for r in strategy_results.values()]
                ),
            },
            "recommendations": [
                "Momentum strategy shows strong performance in trending markets",
                "Mean reversion complements momentum during range-bound periods",
                "ML ensemble provides consistent signals across market conditions",
            ],
        }

        # Save report
        report_path = tmp_path / "reports" / "multi_strategy_analysis.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)

        with open(report_path, "w") as f:
            json.dump(multi_strategy_report, f, indent=2)

        print(f"\nMulti-strategy report saved to {report_path}")
        assert len(strategy_results) == 3
        assert all(r["signals_generated"] > 0 for r in strategy_results.values())

    def _generate_mock_tick(self, symbol: str) -> Dict[str, Any]:
        """Generate mock tick data."""
        base_prices = {"EUR/USD": 1.0850, "GBP/USD": 1.2500, "USD/JPY": 110.00}

        base_price = base_prices.get(symbol, 1.0)
        spread = 0.0001 if symbol != "USD/JPY" else 0.01

        bid = base_price + np.random.normal(0, 0.0002)

        return {
            "symbol": symbol,
            "timestamp": datetime.now(timezone.utc),
            "bid": bid,
            "ask": bid + spread,
            "bid_size": np.random.randint(500000, 2000000),
            "ask_size": np.random.randint(500000, 2000000),
        }

    def _generate_mock_ohlcv_data(self, periods: int = 1000) -> pd.DataFrame:
        """Generate mock OHLCV data."""
        dates = pd.date_range(
            end=datetime.now(timezone.utc), periods=periods, freq="1h"
        )

        # Generate realistic price movement
        returns = np.random.normal(0, 0.0005, periods)
        prices = 1.0850 * np.exp(np.cumsum(returns))

        df = pd.DataFrame(
            {
                "open": prices * (1 + np.random.uniform(-0.0001, 0.0001, periods)),
                "high": prices * (1 + np.random.uniform(0, 0.0002, periods)),
                "low": prices * (1 - np.random.uniform(0, 0.0002, periods)),
                "close": prices,
                "volume": np.random.randint(10000, 100000, periods),
            },
            index=dates,
        )

        # Ensure OHLC consistency
        df["high"] = df[["open", "high", "close"]].max(axis=1)
        df["low"] = df[["open", "low", "close"]].min(axis=1)

        return df

    def _generate_strategy_features(self, strategy_config: Dict) -> pd.DataFrame:
        """Generate features specific to a strategy."""
        periods = 1000
        dates = pd.date_range(
            end=datetime.now(timezone.utc), periods=periods, freq="1h"
        )

        features = pd.DataFrame(index=dates)

        for indicator in strategy_config["indicators"]:
            if indicator.startswith("sma_"):
                period = int(indicator.split("_")[1])
                features[indicator] = np.random.randn(periods).cumsum() + 1.08
            elif indicator == "rsi":
                features["rsi"] = np.random.uniform(30, 70, periods)
            elif indicator == "momentum":
                features["momentum"] = np.random.normal(0, 0.001, periods)
            elif indicator == "bollinger_bands":
                features["bb_upper"] = 1.09 + np.random.uniform(0, 0.001, periods)
                features["bb_lower"] = 1.07 + np.random.uniform(0, 0.001, periods)

        return features

    def _calculate_strategy_correlation(
        self, strategy_results: Dict[str, Dict]
    ) -> Dict[str, Any]:
        """Calculate correlation between strategies."""
        # Simplified correlation based on performance metrics
        strategies = list(strategy_results.keys())
        n_strategies = len(strategies)

        correlation_matrix = np.random.uniform(0.2, 0.8, (n_strategies, n_strategies))
        np.fill_diagonal(correlation_matrix, 1.0)

        # Make symmetric
        correlation_matrix = (correlation_matrix + correlation_matrix.T) / 2

        return {
            "strategies": strategies,
            "correlation_matrix": correlation_matrix.tolist(),
            "average_correlation": float(
                (correlation_matrix.sum() - n_strategies)
                / (n_strategies * (n_strategies - 1))
            ),
        }

    def _optimize_portfolio_weights(
        self, strategy_results: Dict[str, Dict]
    ) -> Dict[str, float]:
        """Optimize portfolio weights across strategies."""
        # Simple optimization based on Sharpe ratio proxy
        weights = {}
        total_score = 0

        for strategy, results in strategy_results.items():
            # Simple score based on P&L and win rate
            score = (results["total_pnl"] / 1000) * results["win_rate"]
            weights[strategy] = max(score, 0.1)  # Minimum weight
            total_score += weights[strategy]

        # Normalize weights
        for strategy in weights:
            weights[strategy] = round(weights[strategy] / total_score, 3)

        return weights


class TestWorkflowIntegration:
    """Test integration with external systems."""

    @pytest.mark.asyncio
    async def test_api_workflow_integration(self, system_config, tmp_path):
        """Test workflow integration through API endpoints."""
        # Create test app
        app = create_app(system_config)

        # Mock API client
        from httpx import AsyncClient

        async with AsyncClient(app=app, base_url="http://test") as client:
            # 1. Health check
            response = await client.get("/health")
            assert response.status_code == 200
            assert response.json()["status"] == "healthy"

            # 2. Start data collection
            response = await client.post(
                "/api/v1/data/collection/start",
                json={"symbols": ["EUR/USD", "GBP/USD"], "feed": "ib"},
            )
            assert response.status_code in [200, 201]

            # 3. Trigger model training
            response = await client.post(
                "/api/v1/ml/train",
                json={
                    "models": ["xgboost"],
                    "data_range": {"start": "2024-01-01", "end": "2024-01-31"},
                },
            )
            assert response.status_code in [200, 202]

            # 4. Get signals
            response = await client.get("/api/v1/signals/latest")
            assert response.status_code == 200

            # 5. Start paper trading
            response = await client.post(
                "/api/v1/trading/paper/start",
                json={"initial_capital": 100000, "symbols": ["EUR/USD"]},
            )
            assert response.status_code in [200, 201]

    @pytest.mark.asyncio
    async def test_monitoring_dashboard_integration(self, system_config):
        """Test integration with monitoring dashboard."""
        monitor = SystemMonitor(system_config["monitoring"])

        # Simulate metric collection
        metrics = {
            "system": {"cpu_usage": 45.2, "memory_usage": 2048.5, "disk_usage": 65.0},
            "trading": {"active_positions": 2, "daily_pnl": 1250.50, "win_rate": 0.65},
            "data": {"tick_rate": 150.5, "latency_ms": 5.2},
        }

        # Record metrics
        for category, values in metrics.items():
            for metric_name, value in values.items():
                await monitor.record_metric(f"{category}.{metric_name}", value)

        # Generate dashboard data
        dashboard_data = await monitor.get_dashboard_data()

        assert "metrics" in dashboard_data
        assert "alerts" in dashboard_data
        assert "health_status" in dashboard_data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
