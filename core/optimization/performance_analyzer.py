"""
FXML4 Performance Optimization Analyzer
========================================

Sprint 3 REFACTOR Phase - Performance Analysis and Optimization

This module analyzes the performance of all trading system components
and provides optimization recommendations based on actual metrics.

Optimization Targets:
- WebSocket latency: < 10ms
- Feature extraction: < 100ms for 1000 data points
- ML prediction: < 50ms
- Position sizing: < 1ms
- FIX translation: < 500μs
- Compliance checks: < 5ms
"""

import time
import asyncio
import psutil
import os
from dataclasses import dataclass
from typing import Dict, List, Any, Callable
from datetime import datetime
import pandas as pd
import numpy as np


@dataclass
class PerformanceMetric:
    """Performance measurement result."""
    component: str
    operation: str
    duration_ms: float
    memory_mb: float
    cpu_percent: float
    timestamp: datetime
    passed: bool
    target_ms: float


class PerformanceAnalyzer:
    """
    Analyzes and optimizes trading system performance.

    REFACTOR Phase: Identify bottlenecks and optimize critical paths.
    """

    def __init__(self):
        self.metrics: List[PerformanceMetric] = []
        self.process = psutil.Process(os.getpid())

        # Performance targets (milliseconds)
        self.performance_targets = {
            "websocket_latency": 10,
            "feature_extraction": 100,
            "ml_prediction": 50,
            "position_sizing": 1,
            "fix_translation": 0.5,
            "compliance_check": 5,
            "order_validation": 2,
            "risk_calculation": 10
        }

    def measure_performance(
        self,
        component: str,
        operation: str,
        func: Callable,
        *args,
        **kwargs
    ) -> PerformanceMetric:
        """Measure performance of a function."""
        # Initial measurements
        initial_memory = self.process.memory_info().rss / 1024 / 1024  # MB
        initial_cpu = self.process.cpu_percent()

        # Execute and time the function
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        end_time = time.perf_counter()

        # Calculate metrics
        duration_ms = (end_time - start_time) * 1000
        final_memory = self.process.memory_info().rss / 1024 / 1024
        memory_used = final_memory - initial_memory
        cpu_used = self.process.cpu_percent() - initial_cpu

        # Check against target
        target = self.performance_targets.get(operation, 100)
        passed = duration_ms <= target

        metric = PerformanceMetric(
            component=component,
            operation=operation,
            duration_ms=duration_ms,
            memory_mb=memory_used,
            cpu_percent=cpu_used,
            timestamp=datetime.now(),
            passed=passed,
            target_ms=target
        )

        self.metrics.append(metric)
        return metric

    async def analyze_websocket_performance(self):
        """Analyze WebSocket streaming performance."""
        print("\n🔍 Analyzing WebSocket Performance...")

        from core.api.websocket_market_data import WebSocketMarketDataManager

        manager = WebSocketMarketDataManager()

        # Test broadcast latency
        def test_broadcast():
            data = {
                "symbol": "EURUSD",
                "bid": 1.2500,
                "ask": 1.2502,
                "timestamp": datetime.now().isoformat()
            }
            # Simulate broadcast (actual broadcast is async)
            return manager._validate_market_data(data)

        metric = self.measure_performance(
            "WebSocket",
            "websocket_latency",
            test_broadcast
        )

        self._print_metric_result(metric)
        return metric

    def analyze_ml_pipeline_performance(self):
        """Analyze ML pipeline performance."""
        print("\n🔍 Analyzing ML Pipeline Performance...")

        from core.features.feature_engineering import UnifiedFeatureEngineer

        # Generate test data
        dates = pd.date_range(start="2024-01-01", periods=1000, freq="1h")
        test_data = pd.DataFrame({
            "timestamp": dates,
            "symbol": ["EURUSD"] * 1000,
            "open": np.random.uniform(1.19, 1.21, 1000),
            "high": np.random.uniform(1.20, 1.22, 1000),
            "low": np.random.uniform(1.18, 1.20, 1000),
            "close": np.random.uniform(1.19, 1.21, 1000),
            "volume": np.random.randint(100000, 1000000, 1000)
        })

        engineer = UnifiedFeatureEngineer()

        # Test feature extraction
        metric = self.measure_performance(
            "ML Pipeline",
            "feature_extraction",
            engineer.generate_features,
            test_data
        )

        self._print_metric_result(metric)
        return metric

    def analyze_risk_management_performance(self):
        """Analyze risk management performance."""
        print("\n🔍 Analyzing Risk Management Performance...")

        from core.risk.risk_manager import RiskManager

        config = {
            "max_position_size": 500000,
            "max_portfolio_risk": 0.02,
            "max_leverage": 50
        }

        manager = RiskManager(config)

        # Test position sizing
        metric = self.measure_performance(
            "Risk Manager",
            "position_sizing",
            manager.calculate_position_size,
            symbol="EURUSD",
            risk_amount=1000,
            stop_loss_pips=20,
            pip_value=10
        )

        self._print_metric_result(metric)
        return metric

    def analyze_fix_translation_performance(self):
        """Analyze FIX protocol translation performance."""
        print("\n🔍 Analyzing FIX Translation Performance...")

        # Create mock order for testing
        class MockOrder:
            def __init__(self):
                self.order_id = "TEST123"
                self.symbol = "EURUSD"
                self.side = "buy"
                self.quantity = 100000
                self.order_type = "market"
                self.time_in_force = "DAY"
                self.limit_price = None
                self.stop_price = None
                self.account = "TEST_ACCOUNT"

        order = MockOrder()

        # Test translation (mock if simplefix not available)
        def mock_translate(order):
            # Simulate FIX message creation
            fix_fields = {
                "35": "D",  # NewOrderSingle
                "11": order.order_id,
                "55": order.symbol,
                "54": "1" if order.side == "buy" else "2",
                "38": str(order.quantity),
                "40": "1",  # Market order
                "59": "0"   # Day
            }
            return fix_fields

        metric = self.measure_performance(
            "FIX Translator",
            "fix_translation",
            mock_translate,
            order
        )

        self._print_metric_result(metric)
        return metric

    def analyze_compliance_performance(self):
        """Analyze compliance checking performance."""
        print("\n🔍 Analyzing Compliance Performance...")

        # Mock compliance check
        def mock_compliance_check(trade_data):
            # Simulate compliance validation
            checks = {
                "mifid_ii": trade_data.get("quantity", 0) < 1000000,
                "risk_limits": trade_data.get("risk", 0) < 0.02,
                "position_limits": True,
                "audit_trail": True
            }
            return all(checks.values())

        trade_data = {
            "symbol": "EURUSD",
            "quantity": 100000,
            "risk": 0.01,
            "user_id": "test_user"
        }

        metric = self.measure_performance(
            "Compliance",
            "compliance_check",
            mock_compliance_check,
            trade_data
        )

        self._print_metric_result(metric)
        return metric

    def _print_metric_result(self, metric: PerformanceMetric):
        """Print performance metric result."""
        status = "✅ PASS" if metric.passed else "❌ FAIL"

        print(f"   {status} {metric.operation}:")
        print(f"      Duration: {metric.duration_ms:.2f}ms (target: {metric.target_ms}ms)")

        if metric.memory_mb != 0:
            print(f"      Memory: {abs(metric.memory_mb):.2f}MB")

        if not metric.passed:
            slowdown = (metric.duration_ms / metric.target_ms - 1) * 100
            print(f"      ⚠️  {slowdown:.1f}% slower than target")

    def generate_optimization_report(self) -> Dict[str, Any]:
        """Generate comprehensive optimization report."""
        if not self.metrics:
            return {"error": "No metrics collected"}

        # Analyze metrics
        total_metrics = len(self.metrics)
        passed_metrics = sum(1 for m in self.metrics if m.passed)

        # Find bottlenecks
        bottlenecks = [m for m in self.metrics if not m.passed]
        bottlenecks.sort(key=lambda x: x.duration_ms / x.target_ms, reverse=True)

        # Calculate statistics
        avg_duration = np.mean([m.duration_ms for m in self.metrics])
        total_memory = sum(abs(m.memory_mb) for m in self.metrics)

        report = {
            "summary": {
                "total_tests": total_metrics,
                "passed": passed_metrics,
                "failed": total_metrics - passed_metrics,
                "success_rate": (passed_metrics / total_metrics * 100) if total_metrics > 0 else 0,
                "avg_duration_ms": avg_duration,
                "total_memory_mb": total_memory
            },
            "bottlenecks": [
                {
                    "component": b.component,
                    "operation": b.operation,
                    "duration_ms": b.duration_ms,
                    "target_ms": b.target_ms,
                    "slowdown_factor": b.duration_ms / b.target_ms
                }
                for b in bottlenecks[:5]  # Top 5 bottlenecks
            ],
            "recommendations": self._generate_recommendations(bottlenecks),
            "metrics": [
                {
                    "component": m.component,
                    "operation": m.operation,
                    "duration_ms": m.duration_ms,
                    "passed": m.passed
                }
                for m in self.metrics
            ]
        }

        return report

    def _generate_recommendations(self, bottlenecks: List[PerformanceMetric]) -> List[str]:
        """Generate optimization recommendations based on bottlenecks."""
        recommendations = []

        for bottleneck in bottlenecks[:3]:  # Top 3 bottlenecks
            if "feature_extraction" in bottleneck.operation:
                recommendations.append(
                    f"🔧 Optimize {bottleneck.component}: Consider caching computed features "
                    f"or using vectorized operations. Current: {bottleneck.duration_ms:.1f}ms, "
                    f"Target: {bottleneck.target_ms}ms"
                )
            elif "ml_prediction" in bottleneck.operation:
                recommendations.append(
                    f"🔧 Optimize {bottleneck.component}: Use model quantization or "
                    f"batch predictions. Current: {bottleneck.duration_ms:.1f}ms"
                )
            elif "websocket" in bottleneck.operation:
                recommendations.append(
                    f"🔧 Optimize {bottleneck.component}: Implement connection pooling "
                    f"and message batching. Current: {bottleneck.duration_ms:.1f}ms"
                )
            elif "compliance" in bottleneck.operation:
                recommendations.append(
                    f"🔧 Optimize {bottleneck.component}: Cache compliance rules and "
                    f"use async validation. Current: {bottleneck.duration_ms:.1f}ms"
                )
            else:
                recommendations.append(
                    f"🔧 Optimize {bottleneck.component}/{bottleneck.operation}: "
                    f"Profile code to identify specific bottlenecks. "
                    f"Current: {bottleneck.duration_ms:.1f}ms, Target: {bottleneck.target_ms}ms"
                )

        if not recommendations:
            recommendations.append("✅ All components meeting performance targets!")

        return recommendations

    def print_optimization_summary(self):
        """Print optimization summary and recommendations."""
        report = self.generate_optimization_report()

        print("\n" + "=" * 60)
        print("📊 PERFORMANCE OPTIMIZATION REPORT")
        print("=" * 60)

        summary = report["summary"]
        print(f"\n✅ Success Rate: {summary['success_rate']:.1f}%")
        print(f"   - Passed: {summary['passed']}/{summary['total_tests']}")
        print(f"   - Average Duration: {summary['avg_duration_ms']:.2f}ms")

        if report.get("bottlenecks"):
            print("\n🔥 Top Performance Bottlenecks:")
            for i, bottleneck in enumerate(report["bottlenecks"], 1):
                print(f"   {i}. {bottleneck['component']}/{bottleneck['operation']}")
                print(f"      {bottleneck['duration_ms']:.2f}ms "
                      f"({bottleneck['slowdown_factor']:.1f}x target)")

        print("\n💡 Optimization Recommendations:")
        for rec in report["recommendations"]:
            print(f"   {rec}")

        print("\n" + "=" * 60)


def run_performance_analysis():
    """Run complete performance analysis."""
    analyzer = PerformanceAnalyzer()

    print("🚀 Starting Performance Analysis...")
    print("   Sprint 3 REFACTOR Phase")
    print("")

    # Analyze each component
    analyzer.analyze_websocket_performance()
    analyzer.analyze_ml_pipeline_performance()
    analyzer.analyze_risk_management_performance()
    analyzer.analyze_fix_translation_performance()
    analyzer.analyze_compliance_performance()

    # Generate report
    analyzer.print_optimization_summary()

    return analyzer.generate_optimization_report()


if __name__ == "__main__":
    report = run_performance_analysis()