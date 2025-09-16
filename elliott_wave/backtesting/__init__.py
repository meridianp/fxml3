"""Backtesting framework for FXML3."""

from fxml3.backtesting.optimization import ParameterOptimizer
from fxml3.backtesting.performance_metrics import PerformanceMetrics
from fxml3.backtesting.result_visualizer import ResultVisualizer
from fxml3.backtesting.wave_backtester import WaveBacktester

__all__ = [
    "WaveBacktester",
    "PerformanceMetrics",
    "ResultVisualizer",
    "ParameterOptimizer",
]
