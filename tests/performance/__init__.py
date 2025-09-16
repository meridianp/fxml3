"""
FXML4 Performance Testing Framework

Comprehensive load testing and benchmarking for high-frequency trading systems:
- Load testing with realistic trading workloads
- Stress testing for extreme market conditions
- Latency benchmarking for sub-millisecond requirements
- Scalability testing for auto-scaling validation
- Performance regression detection
"""

# Import available modules with graceful fallback
try:
    from .latency_benchmarks import LatencyBenchmark, LatencyProfile
except ImportError:
    LatencyBenchmark = None
    LatencyProfile = None

try:
    from .load_testing_framework import (
        LoadTestConfig,
        LoadTestFramework,
        LoadTestResult,
    )
except ImportError:
    LoadTestConfig = None
    LoadTestFramework = None
    LoadTestResult = None

try:
    from .performance_regression_tests import PerformanceBaseline, RegressionTestSuite
except ImportError:
    PerformanceBaseline = None
    RegressionTestSuite = None

try:
    from .stress_testing import StressTestConfig, StressTestSuite
except ImportError:
    StressTestConfig = None
    StressTestSuite = None

try:
    from .trading_simulation import MarketCondition, TradingScenario, TradingSimulator
except ImportError:
    MarketCondition = None
    TradingScenario = None
    TradingSimulator = None

# Export available classes
__all__ = [
    name
    for name in [
        "LoadTestFramework",
        "LoadTestConfig",
        "LoadTestResult",
        "TradingSimulator",
        "MarketCondition",
        "TradingScenario",
        "StressTestSuite",
        "StressTestConfig",
        "LatencyBenchmark",
        "LatencyProfile",
        "RegressionTestSuite",
        "PerformanceBaseline",
    ]
    if globals().get(name) is not None
]
