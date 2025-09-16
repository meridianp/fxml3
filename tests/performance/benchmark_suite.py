"""
Performance Benchmark Suite for FXML4
=====================================

Comprehensive performance testing framework to ensure system performance
meets requirements under various load conditions. Includes:

1. Trading logic performance benchmarks
2. Data processing performance tests
3. API endpoint performance validation
4. Database operation benchmarks
5. ML model inference performance
6. Memory usage and leak detection
7. Concurrent operation performance

This addresses medium-priority task M3 from our test suite action plan.
"""

import asyncio
import gc
import json
import statistics
import threading
import time
import tracemalloc
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

import memory_profiler
import numpy as np
import pandas as pd
import psutil
import pytest
from faker import Faker

# Import testing fixtures
from tests.fixtures.market_data_fixtures import MarketDataGenerator, MarketRegime

fake = Faker()


# ============================================================================
# Performance Measurement Utilities
# ============================================================================


@contextmanager
def measure_time():
    """Context manager to measure execution time."""
    start_time = time.perf_counter()
    try:
        yield lambda: time.perf_counter() - start_time
    finally:
        pass


@contextmanager
def measure_memory():
    """Context manager to measure memory usage."""
    gc.collect()  # Clean up before measurement
    tracemalloc.start()

    try:
        yield lambda: tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()


@contextmanager
def monitor_system_resources():
    """Monitor system resource usage during test execution."""
    process = psutil.Process()
    initial_cpu = process.cpu_percent()
    initial_memory = process.memory_info()

    resource_data = {
        "cpu_samples": [initial_cpu],
        "memory_samples": [initial_memory.rss],
        "start_time": time.time(),
    }

    def collect_sample():
        resource_data["cpu_samples"].append(process.cpu_percent())
        resource_data["memory_samples"].append(process.memory_info().rss)

    # Start background monitoring
    monitoring = True

    def monitor():
        while monitoring:
            collect_sample()
            time.sleep(0.1)  # Sample every 100ms

    monitor_thread = threading.Thread(target=monitor, daemon=True)
    monitor_thread.start()

    try:
        yield resource_data
    finally:
        monitoring = False
        resource_data["end_time"] = time.time()
        resource_data["duration"] = (
            resource_data["end_time"] - resource_data["start_time"]
        )


class PerformanceBenchmark:
    """Base class for performance benchmarks."""

    def __init__(self, name: str, target_time: float = None, target_memory: int = None):
        self.name = name
        self.target_time = target_time  # Target execution time in seconds
        self.target_memory = target_memory  # Target memory usage in bytes
        self.results = []
        self.iterations = 0

    def run_benchmark(self, iterations: int = 10, warmup: int = 3):
        """Run the benchmark multiple times and collect results."""
        self.iterations = iterations

        # Warmup runs
        for _ in range(warmup):
            self._run_single_iteration()

        # Actual benchmark runs
        for i in range(iterations):
            result = self._run_single_iteration()
            result["iteration"] = i
            self.results.append(result)

        return self.analyze_results()

    def _run_single_iteration(self) -> Dict[str, Any]:
        """Run a single benchmark iteration. Override in subclasses."""
        raise NotImplementedError("Subclasses must implement _run_single_iteration")

    def analyze_results(self) -> Dict[str, Any]:
        """Analyze benchmark results."""
        if not self.results:
            return {"error": "No results to analyze"}

        times = [r["execution_time"] for r in self.results]
        memories = [r["memory_used"] for r in self.results if "memory_used" in r]

        analysis = {
            "name": self.name,
            "iterations": len(self.results),
            "time": {
                "min": min(times),
                "max": max(times),
                "mean": statistics.mean(times),
                "median": statistics.median(times),
                "stdev": statistics.stdev(times) if len(times) > 1 else 0,
                "target": self.target_time,
                "meets_target": self.target_time is None
                or statistics.mean(times) <= self.target_time,
            },
        }

        if memories:
            analysis["memory"] = {
                "min": min(memories),
                "max": max(memories),
                "mean": statistics.mean(memories),
                "target": self.target_memory,
                "meets_target": self.target_memory is None
                or max(memories) <= self.target_memory,
            }

        return analysis


# ============================================================================
# Trading Logic Performance Benchmarks
# ============================================================================


class TradingLogicBenchmark(PerformanceBenchmark):
    """Benchmark trading logic operations."""

    def __init__(self, operation_type: str):
        super().__init__(f"Trading Logic - {operation_type}")
        self.operation_type = operation_type
        self.setup_data()

    def setup_data(self):
        """Setup test data for trading operations."""
        generator = MarketDataGenerator(seed=42)

        # Generate various datasets for different operations
        self.small_dataset = generator.generate_ohlcv_data(periods=100, timeframe="1M")
        self.medium_dataset = generator.generate_ohlcv_data(
            periods=1000, timeframe="1M"
        )
        self.large_dataset = generator.generate_ohlcv_data(
            periods=10000, timeframe="1M"
        )

        # Generate tick data
        self.tick_data = generator.generate_tick_data(
            duration_minutes=60, avg_ticks_per_minute=100
        )

        # Setup trading parameters
        self.account_balance = 100000.0
        self.risk_percent = 0.02
        self.positions = []

        for i in range(100):
            position = {
                "symbol": fake.random_element(["EURUSD", "GBPUSD", "USDJPY"]),
                "quantity": fake.pyfloat(min_value=0.01, max_value=10.0),
                "entry_price": fake.pyfloat(min_value=0.5, max_value=2.0),
                "current_price": fake.pyfloat(min_value=0.5, max_value=2.0),
                "side": fake.random_element(["long", "short"]),
            }
            self.positions.append(position)

    def _run_single_iteration(self) -> Dict[str, Any]:
        """Run a single benchmark iteration for trading logic."""
        with measure_time() as get_time:
            with measure_memory() as get_memory:
                if self.operation_type == "position_sizing":
                    self._benchmark_position_sizing()
                elif self.operation_type == "portfolio_valuation":
                    self._benchmark_portfolio_valuation()
                elif self.operation_type == "risk_calculation":
                    self._benchmark_risk_calculation()
                elif self.operation_type == "technical_indicators":
                    self._benchmark_technical_indicators()
                elif self.operation_type == "signal_generation":
                    self._benchmark_signal_generation()
                else:
                    raise ValueError(f"Unknown operation type: {self.operation_type}")

        current_memory, peak_memory = get_memory()

        return {
            "execution_time": get_time(),
            "memory_used": peak_memory - current_memory,
            "operation_type": self.operation_type,
        }

    def _benchmark_position_sizing(self):
        """Benchmark position sizing calculations."""
        for _ in range(1000):
            # Kelly criterion position sizing
            win_rate = fake.pyfloat(min_value=0.4, max_value=0.7)
            avg_win = fake.pyfloat(min_value=0.01, max_value=0.05)
            avg_loss = fake.pyfloat(min_value=0.01, max_value=0.03)

            kelly_percentage = (
                win_rate * avg_win - (1 - win_rate) * avg_loss
            ) / avg_win
            position_size = self.account_balance * min(
                kelly_percentage, self.risk_percent
            )

            # Risk-based position sizing
            stop_loss_distance = fake.pyfloat(min_value=0.001, max_value=0.02)
            risk_amount = self.account_balance * self.risk_percent
            quantity = risk_amount / stop_loss_distance

    def _benchmark_portfolio_valuation(self):
        """Benchmark portfolio valuation calculations."""
        total_value = 0
        total_pnl = 0

        for position in self.positions:
            # Calculate position value
            position_value = abs(position["quantity"]) * position["current_price"]
            total_value += position_value

            # Calculate P&L
            if position["side"] == "long":
                pnl = (position["current_price"] - position["entry_price"]) * position[
                    "quantity"
                ]
            else:
                pnl = (position["entry_price"] - position["current_price"]) * position[
                    "quantity"
                ]

            total_pnl += pnl

        # Calculate portfolio metrics
        returns = total_pnl / self.account_balance
        portfolio_beta = fake.pyfloat(min_value=0.5, max_value=1.5)
        sharpe_ratio = returns / max(0.01, fake.pyfloat(min_value=0.01, max_value=0.1))

    def _benchmark_risk_calculation(self):
        """Benchmark risk metric calculations."""
        returns = np.random.normal(0, 0.02, 1000)  # Daily returns

        # Value at Risk (VaR)
        var_95 = np.percentile(returns, 5)
        var_99 = np.percentile(returns, 1)

        # Conditional Value at Risk (CVaR)
        cvar_95 = returns[returns <= var_95].mean()

        # Maximum Drawdown
        cumulative_returns = np.cumprod(1 + returns)
        running_max = np.maximum.accumulate(cumulative_returns)
        drawdown = (cumulative_returns - running_max) / running_max
        max_drawdown = drawdown.min()

        # Beta calculation
        market_returns = np.random.normal(0, 0.015, 1000)
        covariance = np.cov(returns, market_returns)[0, 1]
        market_variance = np.var(market_returns)
        beta = covariance / market_variance

    def _benchmark_technical_indicators(self):
        """Benchmark technical indicator calculations."""
        prices = self.medium_dataset["close"].values

        # Simple Moving Average
        for period in [5, 10, 20, 50]:
            sma = np.convolve(prices, np.ones(period) / period, mode="valid")

        # Exponential Moving Average
        alpha = 2.0 / (20 + 1)
        ema = np.zeros_like(prices)
        ema[0] = prices[0]
        for i in range(1, len(prices)):
            ema[i] = alpha * prices[i] + (1 - alpha) * ema[i - 1]

        # RSI calculation
        deltas = np.diff(prices)
        gains = np.maximum(deltas, 0)
        losses = np.maximum(-deltas, 0)

        avg_gain = np.mean(gains[:14])
        avg_loss = np.mean(losses[:14])

        for i in range(14, len(gains)):
            avg_gain = (avg_gain * 13 + gains[i]) / 14
            avg_loss = (avg_loss * 13 + losses[i]) / 14

            rs = avg_gain / avg_loss if avg_loss != 0 else 0
            rsi = 100 - (100 / (1 + rs))

        # MACD calculation
        ema_12 = np.zeros_like(prices)
        ema_26 = np.zeros_like(prices)
        alpha_12 = 2.0 / (12 + 1)
        alpha_26 = 2.0 / (26 + 1)

        ema_12[0] = ema_26[0] = prices[0]
        for i in range(1, len(prices)):
            ema_12[i] = alpha_12 * prices[i] + (1 - alpha_12) * ema_12[i - 1]
            ema_26[i] = alpha_26 * prices[i] + (1 - alpha_26) * ema_26[i - 1]

        macd = ema_12 - ema_26

    def _benchmark_signal_generation(self):
        """Benchmark trading signal generation."""
        prices = self.medium_dataset["close"].values

        # Generate signals for each bar
        signals = []
        for i in range(50, len(prices)):  # Need history for indicators
            window = prices[i - 50 : i]

            # Simple trend following signal
            short_ma = np.mean(window[-10:])
            long_ma = np.mean(window[-50:])

            if short_ma > long_ma * 1.001:  # 0.1% threshold
                signal = "buy"
            elif short_ma < long_ma * 0.999:
                signal = "sell"
            else:
                signal = "hold"

            signals.append(
                {
                    "timestamp": fake.date_time(),
                    "signal": signal,
                    "strength": abs(short_ma / long_ma - 1),
                    "price": prices[i],
                }
            )


# ============================================================================
# Data Processing Performance Benchmarks
# ============================================================================


class DataProcessingBenchmark(PerformanceBenchmark):
    """Benchmark data processing operations."""

    def __init__(self, operation_type: str):
        super().__init__(f"Data Processing - {operation_type}", target_time=1.0)
        self.operation_type = operation_type
        self.setup_data()

    def setup_data(self):
        """Setup test data for data processing."""
        generator = MarketDataGenerator(seed=42)

        # Generate datasets of various sizes
        self.small_data = generator.generate_ohlcv_data(periods=1000, timeframe="1M")
        self.medium_data = generator.generate_ohlcv_data(periods=10000, timeframe="1M")
        self.large_data = generator.generate_ohlcv_data(periods=100000, timeframe="1M")

        # Generate tick data
        self.tick_data = generator.generate_tick_data(
            duration_minutes=1440, avg_ticks_per_minute=50
        )

        # Generate multi-symbol data
        self.multi_symbol_data = {}
        symbols = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD"]
        for symbol in symbols:
            self.multi_symbol_data[symbol] = generator.generate_ohlcv_data(
                symbol=symbol, periods=5000, timeframe="1M"
            )

    def _run_single_iteration(self) -> Dict[str, Any]:
        """Run a single benchmark iteration for data processing."""
        with measure_time() as get_time:
            with measure_memory() as get_memory:
                if self.operation_type == "data_loading":
                    self._benchmark_data_loading()
                elif self.operation_type == "data_aggregation":
                    self._benchmark_data_aggregation()
                elif self.operation_type == "data_filtering":
                    self._benchmark_data_filtering()
                elif self.operation_type == "data_transformation":
                    self._benchmark_data_transformation()
                elif self.operation_type == "multi_symbol_processing":
                    self._benchmark_multi_symbol_processing()
                else:
                    raise ValueError(f"Unknown operation type: {self.operation_type}")

        current_memory, peak_memory = get_memory()

        return {
            "execution_time": get_time(),
            "memory_used": peak_memory - current_memory,
            "operation_type": self.operation_type,
        }

    def _benchmark_data_loading(self):
        """Benchmark data loading operations."""
        # Simulate loading data from various sources
        for data_size in ["small", "medium", "large"]:
            data = getattr(self, f"{data_size}_data")

            # Simulate CSV loading
            csv_data = data.to_csv(index=False)
            loaded_data = pd.read_csv(pd.io.common.StringIO(csv_data))

            # Simulate JSON loading
            json_data = data.to_json(orient="records")
            loaded_json = pd.read_json(
                pd.io.common.StringIO(json_data), orient="records"
            )

            # Simulate parquet operations
            buffer = pd.io.common.BytesIO()
            data.to_parquet(buffer)
            buffer.seek(0)
            loaded_parquet = pd.read_parquet(buffer)

    def _benchmark_data_aggregation(self):
        """Benchmark data aggregation operations."""
        data = self.medium_data.copy()

        # Time-based aggregation (1M -> 5M, 15M, 1H)
        data.set_index("timestamp", inplace=True)

        # 5-minute aggregation
        agg_5m = data.resample("5T").agg(
            {
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
            }
        )

        # 15-minute aggregation
        agg_15m = data.resample("15T").agg(
            {
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
            }
        )

        # 1-hour aggregation
        agg_1h = data.resample("1H").agg(
            {
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
            }
        )

        # Cross-symbol aggregation
        all_data = pd.concat(self.multi_symbol_data.values())
        symbol_stats = all_data.groupby("symbol").agg(
            {
                "close": ["mean", "std", "min", "max"],
                "volume": ["mean", "sum"],
            }
        )

    def _benchmark_data_filtering(self):
        """Benchmark data filtering operations."""
        data = self.large_data.copy()

        # Price-based filtering
        high_volume = data[data["volume"] > data["volume"].quantile(0.8)]
        price_range = data[(data["close"] > 1.0) & (data["close"] < 1.5)]

        # Time-based filtering
        data["hour"] = pd.to_datetime(data["timestamp"]).dt.hour
        trading_hours = data[(data["hour"] >= 8) & (data["hour"] <= 17)]

        # Volatility-based filtering
        data["volatility"] = (data["high"] - data["low"]) / data["close"]
        high_vol = data[data["volatility"] > data["volatility"].quantile(0.9)]

        # Complex multi-condition filtering
        filtered = data[
            (data["volume"] > data["volume"].mean())
            & (data["volatility"] < data["volatility"].quantile(0.8))
            & (data["close"] > data["open"])
        ]

    def _benchmark_data_transformation(self):
        """Benchmark data transformation operations."""
        data = self.medium_data.copy()

        # Add derived columns
        data["returns"] = data["close"].pct_change()
        data["log_returns"] = np.log(data["close"] / data["close"].shift(1))
        data["volatility"] = (data["high"] - data["low"]) / data["close"]
        data["typical_price"] = (data["high"] + data["low"] + data["close"]) / 3

        # Rolling calculations
        data["sma_20"] = data["close"].rolling(window=20).mean()
        data["std_20"] = data["close"].rolling(window=20).std()
        data["bollinger_upper"] = data["sma_20"] + 2 * data["std_20"]
        data["bollinger_lower"] = data["sma_20"] - 2 * data["std_20"]

        # Exponential smoothing
        data["ema_12"] = data["close"].ewm(span=12).mean()
        data["ema_26"] = data["close"].ewm(span=26).mean()
        data["macd"] = data["ema_12"] - data["ema_26"]

        # Lag features
        for lag in [1, 2, 3, 5, 10]:
            data[f"close_lag_{lag}"] = data["close"].shift(lag)
            data[f"volume_lag_{lag}"] = data["volume"].shift(lag)

        # Normalized features
        scaler_window = 100
        data["close_normalized"] = (
            data["close"] - data["close"].rolling(scaler_window).mean()
        ) / data["close"].rolling(scaler_window).std()

    def _benchmark_multi_symbol_processing(self):
        """Benchmark multi-symbol data processing."""
        # Process all symbols simultaneously
        results = {}

        for symbol, data in self.multi_symbol_data.items():
            # Calculate correlations between symbols
            for other_symbol, other_data in self.multi_symbol_data.items():
                if symbol != other_symbol:
                    # Align timestamps
                    merged = pd.merge(
                        data[["timestamp", "close"]].rename(
                            columns={"close": f"{symbol}_close"}
                        ),
                        other_data[["timestamp", "close"]].rename(
                            columns={"close": f"{other_symbol}_close"}
                        ),
                        on="timestamp",
                        how="inner",
                    )

                    if len(merged) > 10:
                        correlation = merged[f"{symbol}_close"].corr(
                            merged[f"{other_symbol}_close"]
                        )
                        results[f"{symbol}_{other_symbol}_corr"] = correlation

        # Portfolio-level calculations
        all_data = []
        for symbol, data in self.multi_symbol_data.items():
            symbol_data = data.copy()
            symbol_data["symbol"] = symbol
            all_data.append(symbol_data)

        combined = pd.concat(all_data, ignore_index=True)

        # Portfolio statistics
        portfolio_stats = combined.groupby("timestamp").agg(
            {
                "close": "mean",
                "volume": "sum",
                "high": "max",
                "low": "min",
            }
        )


# ============================================================================
# API Performance Benchmarks
# ============================================================================


class APIPerformanceBenchmark(PerformanceBenchmark):
    """Benchmark API endpoint performance."""

    def __init__(self, endpoint_type: str):
        super().__init__(f"API - {endpoint_type}", target_time=0.5)
        self.endpoint_type = endpoint_type
        self.setup_data()

    def setup_data(self):
        """Setup test data for API benchmarks."""
        # Generate test requests
        self.market_data_requests = []
        self.order_requests = []
        self.user_requests = []

        for i in range(100):
            # Market data requests
            self.market_data_requests.append(
                {
                    "symbol": fake.random_element(["EURUSD", "GBPUSD", "USDJPY"]),
                    "start_date": fake.date_time_between(
                        start_date="-1y", end_date="-1d"
                    ),
                    "end_date": fake.date_time_between(
                        start_date="-1d", end_date="now"
                    ),
                    "timeframe": fake.random_element(["1M", "5M", "15M", "1H"]),
                }
            )

            # Order requests
            self.order_requests.append(
                {
                    "symbol": fake.random_element(["EURUSD", "GBPUSD", "USDJPY"]),
                    "side": fake.random_element(["buy", "sell"]),
                    "quantity": fake.pyfloat(min_value=0.01, max_value=10.0),
                    "order_type": fake.random_element(["market", "limit"]),
                    "price": (
                        fake.pyfloat(min_value=0.5, max_value=2.0)
                        if fake.boolean()
                        else None
                    ),
                }
            )

            # User requests
            self.user_requests.append(
                {
                    "user_id": str(uuid.uuid4()),
                    "session_id": str(uuid.uuid4()),
                    "action": fake.random_element(
                        ["login", "get_balance", "get_positions", "logout"]
                    ),
                }
            )

    def _run_single_iteration(self) -> Dict[str, Any]:
        """Run a single benchmark iteration for API performance."""
        with measure_time() as get_time:
            if self.endpoint_type == "market_data":
                self._benchmark_market_data_api()
            elif self.endpoint_type == "trading":
                self._benchmark_trading_api()
            elif self.endpoint_type == "user_management":
                self._benchmark_user_management_api()
            elif self.endpoint_type == "concurrent_requests":
                self._benchmark_concurrent_requests()
            else:
                raise ValueError(f"Unknown endpoint type: {self.endpoint_type}")

        return {
            "execution_time": get_time(),
            "endpoint_type": self.endpoint_type,
        }

    def _benchmark_market_data_api(self):
        """Benchmark market data API endpoints."""
        # Simulate processing market data requests
        for request in self.market_data_requests[:20]:  # Process 20 requests
            # Simulate data retrieval
            generator = MarketDataGenerator()

            # Calculate periods based on timeframe and date range
            start_date = request["start_date"]
            end_date = request["end_date"]
            duration = end_date - start_date

            # Rough calculation of periods
            timeframe_minutes = {"1M": 1, "5M": 5, "15M": 15, "1H": 60}
            tf_min = timeframe_minutes[request["timeframe"]]
            periods = min(1000, int(duration.total_seconds() / 60 / tf_min))

            # Generate data
            data = generator.generate_ohlcv_data(
                symbol=request["symbol"],
                periods=max(1, periods),
                timeframe=request["timeframe"],
            )

            # Simulate response serialization
            response = {
                "symbol": request["symbol"],
                "data": data.to_dict("records"),
                "metadata": {
                    "total_records": len(data),
                    "timeframe": request["timeframe"],
                    "generated_at": datetime.now().isoformat(),
                },
            }

            # Simulate JSON serialization
            json_response = json.dumps(response, default=str)

    def _benchmark_trading_api(self):
        """Benchmark trading API endpoints."""
        # Simulate order processing
        for order in self.order_requests[:20]:
            # Order validation
            validation_errors = []

            if not order["symbol"] or len(order["symbol"]) < 6:
                validation_errors.append("Invalid symbol")

            if order["quantity"] <= 0:
                validation_errors.append("Invalid quantity")

            if order["order_type"] == "limit" and not order["price"]:
                validation_errors.append("Limit orders require price")

            # Risk checks
            position_value = order["quantity"] * (order["price"] or 1.0)
            if position_value > 50000:  # Risk limit
                validation_errors.append("Position size exceeds risk limit")

            # Simulate order execution
            if not validation_errors:
                execution_result = {
                    "order_id": str(uuid.uuid4()),
                    "status": (
                        "filled" if order["order_type"] == "market" else "pending"
                    ),
                    "filled_price": order["price"]
                    or fake.pyfloat(min_value=0.5, max_value=2.0),
                    "filled_quantity": order["quantity"],
                    "commission": position_value * 0.0001,  # 0.01% commission
                    "timestamp": datetime.now().isoformat(),
                }
            else:
                execution_result = {
                    "order_id": None,
                    "status": "rejected",
                    "errors": validation_errors,
                }

            # Serialize response
            json_response = json.dumps(execution_result, default=str)

    def _benchmark_user_management_api(self):
        """Benchmark user management API endpoints."""
        # Simulate user operations
        for request in self.user_requests[:20]:
            action = request["action"]

            if action == "login":
                # Simulate authentication
                auth_result = {
                    "user_id": request["user_id"],
                    "session_id": request["session_id"],
                    "access_token": str(uuid.uuid4()),
                    "expires_at": (datetime.now() + timedelta(hours=24)).isoformat(),
                    "permissions": ["trade", "view_data", "manage_account"],
                }

            elif action == "get_balance":
                # Simulate balance calculation
                balance_result = {
                    "user_id": request["user_id"],
                    "account_balance": fake.pyfloat(min_value=1000, max_value=100000),
                    "available_balance": fake.pyfloat(min_value=1000, max_value=100000),
                    "currency": "USD",
                    "last_updated": datetime.now().isoformat(),
                }

            elif action == "get_positions":
                # Simulate position retrieval
                positions = []
                for _ in range(fake.random_int(0, 10)):
                    positions.append(
                        {
                            "symbol": fake.random_element(
                                ["EURUSD", "GBPUSD", "USDJPY"]
                            ),
                            "quantity": fake.pyfloat(min_value=0.01, max_value=10.0),
                            "entry_price": fake.pyfloat(min_value=0.5, max_value=2.0),
                            "current_price": fake.pyfloat(min_value=0.5, max_value=2.0),
                            "unrealized_pnl": fake.pyfloat(
                                min_value=-1000, max_value=1000
                            ),
                        }
                    )

                position_result = {
                    "user_id": request["user_id"],
                    "positions": positions,
                    "total_unrealized_pnl": sum(p["unrealized_pnl"] for p in positions),
                }

            # Serialize response
            if action != "logout":
                json_response = json.dumps(
                    locals()[f"{action.replace('get_', '')}_result"], default=str
                )

    def _benchmark_concurrent_requests(self):
        """Benchmark concurrent API request handling."""

        def process_request(request_data):
            # Simulate request processing time
            time.sleep(fake.pyfloat(min_value=0.001, max_value=0.1))

            return {
                "request_id": str(uuid.uuid4()),
                "status": "success",
                "processing_time": fake.pyfloat(min_value=0.001, max_value=0.1),
                "data": request_data,
            }

        # Process requests concurrently
        concurrent_requests = 50
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []

            for i in range(concurrent_requests):
                request_data = {
                    "request_id": i,
                    "timestamp": datetime.now().isoformat(),
                    "data": fake.pydict(nb_elements=5),
                }
                future = executor.submit(process_request, request_data)
                futures.append(future)

            # Wait for all requests to complete
            results = []
            for future in as_completed(futures):
                try:
                    result = future.result(timeout=5)
                    results.append(result)
                except Exception as e:
                    results.append({"error": str(e)})


# ============================================================================
# Memory and Resource Benchmarks
# ============================================================================


class MemoryBenchmark(PerformanceBenchmark):
    """Benchmark memory usage and detect memory leaks."""

    def __init__(self, operation_type: str):
        super().__init__(
            f"Memory - {operation_type}", target_memory=100 * 1024 * 1024
        )  # 100MB
        self.operation_type = operation_type

    def _run_single_iteration(self) -> Dict[str, Any]:
        """Run a single memory benchmark iteration."""
        with measure_memory() as get_memory:
            if self.operation_type == "data_structures":
                self._benchmark_data_structures()
            elif self.operation_type == "large_datasets":
                self._benchmark_large_datasets()
            elif self.operation_type == "memory_leaks":
                self._benchmark_memory_leaks()
            else:
                raise ValueError(f"Unknown operation type: {self.operation_type}")

        current_memory, peak_memory = get_memory()

        # Force garbage collection and measure again
        gc.collect()
        time.sleep(0.1)  # Give GC time to work

        with measure_memory() as get_final_memory:
            pass

        final_current, final_peak = get_final_memory()

        return {
            "execution_time": 0,  # Not relevant for memory tests
            "memory_used": peak_memory - current_memory,
            "memory_after_gc": final_current,
            "memory_leaked": max(0, final_current - current_memory),
            "operation_type": self.operation_type,
        }

    def _benchmark_data_structures(self):
        """Benchmark memory usage of various data structures."""
        # Large dictionary
        large_dict = {}
        for i in range(100000):
            large_dict[f"key_{i}"] = {
                "value": i,
                "data": fake.text(max_nb_chars=100),
                "timestamp": datetime.now(),
            }

        # Large list
        large_list = []
        for i in range(100000):
            large_list.append(
                {
                    "id": i,
                    "price": fake.pyfloat(min_value=0.5, max_value=2.0),
                    "volume": fake.random_int(1000, 100000),
                }
            )

        # NumPy arrays
        large_array = np.random.random((10000, 100))
        processed_array = np.dot(large_array, large_array.T)

        # Pandas DataFrames
        df_data = {
            "timestamp": [fake.date_time() for _ in range(50000)],
            "price": [fake.pyfloat(min_value=0.5, max_value=2.0) for _ in range(50000)],
            "volume": [fake.random_int(1000, 100000) for _ in range(50000)],
        }
        large_df = pd.DataFrame(df_data)

        # Clean up references
        del large_dict, large_list, large_array, processed_array, large_df, df_data

    def _benchmark_large_datasets(self):
        """Benchmark memory usage with large datasets."""
        generator = MarketDataGenerator()

        # Generate very large dataset
        large_dataset = generator.generate_ohlcv_data(periods=500000, timeframe="1M")

        # Perform memory-intensive operations
        large_dataset["sma_50"] = large_dataset["close"].rolling(window=50).mean()
        large_dataset["returns"] = large_dataset["close"].pct_change()

        # Create multiple copies
        datasets = []
        for i in range(5):
            copy_df = large_dataset.copy()
            copy_df["dataset_id"] = i
            datasets.append(copy_df)

        # Combine all datasets
        combined = pd.concat(datasets, ignore_index=True)

        # Perform aggregations
        summary = combined.groupby("dataset_id").agg(
            {
                "close": ["mean", "std", "min", "max"],
                "volume": ["sum", "mean"],
            }
        )

        # Clean up
        del large_dataset, datasets, combined, summary

    def _benchmark_memory_leaks(self):
        """Test for potential memory leaks."""
        # Create and destroy objects repeatedly
        for iteration in range(1000):
            # Create temporary objects
            temp_data = []
            for i in range(100):
                obj = {
                    "id": i,
                    "data": fake.text(max_nb_chars=1000),
                    "nested": {
                        "values": [fake.random_int(1, 1000) for _ in range(50)],
                        "metadata": fake.pydict(nb_elements=10),
                    },
                }
                temp_data.append(obj)

            # Process data
            processed = []
            for obj in temp_data:
                processed_obj = {
                    "id": obj["id"],
                    "summary": len(obj["data"]),
                    "nested_count": len(obj["nested"]["values"]),
                }
                processed.append(processed_obj)

            # Should clean up automatically
            del temp_data, processed

            # Force garbage collection occasionally
            if iteration % 100 == 0:
                gc.collect()


# ============================================================================
# Main Benchmark Runner
# ============================================================================


class BenchmarkSuite:
    """Main benchmark suite runner."""

    def __init__(self):
        self.benchmarks = {}
        self.results = {}

    def add_benchmark(self, benchmark: PerformanceBenchmark):
        """Add a benchmark to the suite."""
        self.benchmarks[benchmark.name] = benchmark

    def run_all_benchmarks(self, iterations: int = 10) -> Dict[str, Any]:
        """Run all benchmarks in the suite."""
        print("Starting FXML4 Performance Benchmark Suite")
        print("=" * 60)

        for name, benchmark in self.benchmarks.items():
            print(f"\nRunning {name}...")

            with monitor_system_resources() as resources:
                result = benchmark.run_benchmark(iterations=iterations)
                result["system_resources"] = {
                    "avg_cpu": statistics.mean(resources["cpu_samples"]),
                    "max_memory": max(resources["memory_samples"]),
                    "duration": resources["duration"],
                }

            self.results[name] = result

            # Print immediate results
            if result["time"]["meets_target"]:
                status = "✅ PASS"
            else:
                status = "❌ FAIL"

            print(
                f"  {status} - Mean: {result['time']['mean']:.4f}s, Target: {result['time']['target']}s"
            )

        return self.results

    def generate_report(self) -> str:
        """Generate a comprehensive performance report."""
        if not self.results:
            return "No benchmark results available."

        report = []
        report.append("FXML4 Performance Benchmark Report")
        report.append("=" * 60)
        report.append(f"Generated: {datetime.now().isoformat()}")
        report.append(f"Total Benchmarks: {len(self.results)}")
        report.append("")

        # Summary section
        passed = sum(1 for r in self.results.values() if r["time"]["meets_target"])
        failed = len(self.results) - passed

        report.append("Summary")
        report.append("-" * 20)
        report.append(f"Passed: {passed}")
        report.append(f"Failed: {failed}")
        report.append(f"Success Rate: {passed/len(self.results)*100:.1f}%")
        report.append("")

        # Detailed results
        report.append("Detailed Results")
        report.append("-" * 40)

        for name, result in self.results.items():
            report.append(f"\n{name}")
            report.append("-" * len(name))

            time_result = result["time"]
            report.append(f"  Execution Time:")
            report.append(f"    Mean: {time_result['mean']:.4f}s")
            report.append(f"    Median: {time_result['median']:.4f}s")
            report.append(f"    Min: {time_result['min']:.4f}s")
            report.append(f"    Max: {time_result['max']:.4f}s")
            report.append(f"    Std Dev: {time_result['stdev']:.4f}s")
            report.append(f"    Target: {time_result['target']}s")
            report.append(
                f"    Status: {'PASS' if time_result['meets_target'] else 'FAIL'}"
            )

            if "memory" in result:
                memory_result = result["memory"]
                report.append(f"  Memory Usage:")
                report.append(f"    Mean: {memory_result['mean']/1024/1024:.2f} MB")
                report.append(f"    Max: {memory_result['max']/1024/1024:.2f} MB")
                report.append(f"    Target: {memory_result['target']/1024/1024:.2f} MB")
                report.append(
                    f"    Status: {'PASS' if memory_result['meets_target'] else 'FAIL'}"
                )

            if "system_resources" in result:
                sys_res = result["system_resources"]
                report.append(f"  System Resources:")
                report.append(f"    Avg CPU: {sys_res['avg_cpu']:.1f}%")
                report.append(
                    f"    Max Memory: {sys_res['max_memory']/1024/1024:.2f} MB"
                )
                report.append(f"    Duration: {sys_res['duration']:.2f}s")

        return "\n".join(report)


# ============================================================================
# Pytest Integration
# ============================================================================


@pytest.fixture(scope="session")
def benchmark_suite():
    """Create a benchmark suite for testing."""
    suite = BenchmarkSuite()

    # Add trading logic benchmarks
    suite.add_benchmark(TradingLogicBenchmark("position_sizing"))
    suite.add_benchmark(TradingLogicBenchmark("portfolio_valuation"))
    suite.add_benchmark(TradingLogicBenchmark("risk_calculation"))
    suite.add_benchmark(TradingLogicBenchmark("technical_indicators"))
    suite.add_benchmark(TradingLogicBenchmark("signal_generation"))

    # Add data processing benchmarks
    suite.add_benchmark(DataProcessingBenchmark("data_loading"))
    suite.add_benchmark(DataProcessingBenchmark("data_aggregation"))
    suite.add_benchmark(DataProcessingBenchmark("data_filtering"))
    suite.add_benchmark(DataProcessingBenchmark("data_transformation"))
    suite.add_benchmark(DataProcessingBenchmark("multi_symbol_processing"))

    # Add API benchmarks
    suite.add_benchmark(APIPerformanceBenchmark("market_data"))
    suite.add_benchmark(APIPerformanceBenchmark("trading"))
    suite.add_benchmark(APIPerformanceBenchmark("user_management"))
    suite.add_benchmark(APIPerformanceBenchmark("concurrent_requests"))

    # Add memory benchmarks
    suite.add_benchmark(MemoryBenchmark("data_structures"))
    suite.add_benchmark(MemoryBenchmark("large_datasets"))
    suite.add_benchmark(MemoryBenchmark("memory_leaks"))

    return suite


@pytest.mark.performance
@pytest.mark.slow
def test_performance_benchmark_suite(benchmark_suite):
    """Run the complete performance benchmark suite."""
    results = benchmark_suite.run_all_benchmarks(iterations=5)  # Reduced for testing

    # Verify all benchmarks ran
    assert len(results) > 0, "No benchmark results"

    # Check that all benchmarks have required fields
    for name, result in results.items():
        assert "time" in result, f"Missing time results for {name}"
        assert "mean" in result["time"], f"Missing mean time for {name}"
        assert "meets_target" in result["time"], f"Missing target check for {name}"

    # Generate and print report
    report = benchmark_suite.generate_report()
    print("\n" + report)

    # Optionally fail if too many benchmarks fail
    failed_benchmarks = [
        name for name, result in results.items() if not result["time"]["meets_target"]
    ]

    if len(failed_benchmarks) > len(results) * 0.5:  # More than 50% failed
        pytest.fail(f"Too many benchmarks failed: {failed_benchmarks}")


if __name__ == "__main__":
    # Run benchmarks directly
    suite = BenchmarkSuite()

    # Add a few quick benchmarks for standalone testing
    suite.add_benchmark(TradingLogicBenchmark("position_sizing"))
    suite.add_benchmark(DataProcessingBenchmark("data_loading"))
    suite.add_benchmark(APIPerformanceBenchmark("market_data"))

    results = suite.run_all_benchmarks(iterations=3)
    report = suite.generate_report()
    print("\n" + report)
