#!/usr/bin/env python3
"""
Consolidated System Runner for FXML4
Combines functionality from multiple run scripts into a single interface.
"""

import argparse
import asyncio
import json
import logging
import os
import signal
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fxml4.api.main import create_app
from fxml4.backtesting.event_driven_engine import EventDrivenEngine
from fxml4.training.main import TrainingManager
from fxml4.ui.dashboard import DashboardManager
from fxml4.worker.main import WorkerManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ConsolidatedSystemRunner:
    """Consolidated system runner with multiple execution modes."""

    def __init__(self):
        self.running_services = {}
        self.shutdown_event = threading.Event()

        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        self.run_modes = {
            "advanced_features": self.run_advanced_features,
            "aggressive_profitable_system": self.run_aggressive_profitable_system,
            "complete_system_demo": self.run_complete_system_demo,
            "complete_system_with_llm": self.run_complete_system_with_llm,
            "comprehensive_backtests": self.run_comprehensive_backtests,
            "enhanced_backtest_v2": self.run_enhanced_backtest_v2,
            "enhanced_production_400x": self.run_enhanced_production_400x,
            "enhanced_test_suite": self.run_enhanced_test_suite,
            "feature_engineering": self.run_feature_engineering,
            "final_comprehensive_backtest": self.run_final_comprehensive_backtest,
            "full_fxml4_enhanced": self.run_full_fxml4_enhanced,
            "full_optimized_backtest": self.run_full_optimized_backtest,
            "full_production_backtest": self.run_full_production_backtest,
            "full_system_production": self.run_full_system_production,
            "fxml4_full_capabilities": self.run_fxml4_full_capabilities,
            "fxml4_optimized": self.run_fxml4_optimized,
            "fxml4_profitable_final": self.run_fxml4_profitable_final,
            "performance_test": self.run_performance_test,
            "production_400x_robust": self.run_production_400x_robust,
            "production_400x_simple": self.run_production_400x_simple,
            "production_backtest": self.run_production_backtest,
            "production_demo_final": self.run_production_demo_final,
            "profitable_backtest": self.run_profitable_backtest,
            "profitable_fxml4_system": self.run_profitable_fxml4_system,
            "api_server": self.run_api_server,
            "dashboard": self.run_dashboard,
            "worker": self.run_worker,
            "training": self.run_training,
            "all_services": self.run_all_services,
        }

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, shutting down...")
        self.shutdown_event.set()
        self.shutdown_services()

    def shutdown_services(self):
        """Shutdown all running services."""
        for service_name, service in self.running_services.items():
            logger.info(f"Shutting down {service_name}")
            try:
                if hasattr(service, "shutdown"):
                    service.shutdown()
                elif hasattr(service, "stop"):
                    service.stop()
            except Exception as e:
                logger.error(f"Error shutting down {service_name}: {e}")

    def run_advanced_features(self, **kwargs):
        """Run system with advanced features enabled."""
        logger.info("Running system with advanced features")

        config = {
            "use_ml": True,
            "use_elliott_wave": True,
            "use_sentiment": True,
            "use_news_filter": True,
            "use_economic_features": True,
            "use_ensemble_models": True,
            "advanced_risk_management": True,
            "real_time_analysis": True,
        }

        return self._run_system(config, "advanced_features")

    def run_aggressive_profitable_system(self, **kwargs):
        """Run aggressive profitable system configuration."""
        logger.info("Running aggressive profitable system")

        config = {
            "leverage": kwargs.get("leverage", 100),
            "risk_per_trade": kwargs.get("risk_per_trade", 0.05),
            "aggressive_position_sizing": True,
            "short_term_signals": True,
            "high_frequency_trading": True,
            "use_all_signals": True,
        }

        return self._run_system(config, "aggressive_profitable_system")

    def run_complete_system_demo(self, **kwargs):
        """Run complete system demonstration."""
        logger.info("Running complete system demo")

        config = {
            "demo_mode": True,
            "use_sample_data": True,
            "enable_visualization": True,
            "generate_reports": True,
            "show_progress": True,
        }

        return self._run_system(config, "complete_system_demo")

    def run_complete_system_with_llm(self, **kwargs):
        """Run complete system with LLM integration."""
        logger.info("Running complete system with LLM")

        config = {
            "use_llm": True,
            "llm_analysis": True,
            "sentiment_analysis": True,
            "news_analysis": True,
            "market_commentary": True,
            "llm_signal_generation": True,
        }

        return self._run_system(config, "complete_system_with_llm")

    def run_comprehensive_backtests(self, **kwargs):
        """Run comprehensive backtests."""
        logger.info("Running comprehensive backtests")

        symbols = kwargs.get("symbols", ["EURUSD", "GBPUSD", "USDCHF", "USDJPY"])
        strategies = kwargs.get("strategies", ["ml", "elliott_wave", "combined"])

        results = {}

        for symbol in symbols:
            results[symbol] = {}
            for strategy in strategies:
                logger.info(f"Running {strategy} backtest for {symbol}")

                config = {
                    "symbol": symbol,
                    "strategy": strategy,
                    "start_date": kwargs.get("start_date", "2023-01-01"),
                    "end_date": kwargs.get("end_date", "2024-01-01"),
                    "initial_balance": kwargs.get("initial_balance", 100000),
                }

                engine = EventDrivenEngine(config)
                result = engine.run_backtest()
                results[symbol][strategy] = result

        return results

    def run_enhanced_backtest_v2(self, **kwargs):
        """Run enhanced backtest version 2."""
        logger.info("Running enhanced backtest v2")

        config = {
            "version": 2,
            "enhanced_features": True,
            "improved_risk_management": True,
            "better_position_sizing": True,
            "advanced_exit_strategies": True,
            "use_real_spreads": True,
            "use_real_slippage": True,
        }

        return self._run_system(config, "enhanced_backtest_v2")

    def run_enhanced_production_400x(self, **kwargs):
        """Run enhanced production system with 400x leverage."""
        logger.info("Running enhanced production 400x")

        config = {
            "leverage": 400,
            "production_mode": True,
            "enhanced_features": True,
            "strict_risk_management": True,
            "real_time_monitoring": True,
            "emergency_stops": True,
            "compliance_checks": True,
        }

        return self._run_system(config, "enhanced_production_400x")

    def run_enhanced_test_suite(self, **kwargs):
        """Run enhanced test suite."""
        logger.info("Running enhanced test suite")

        import subprocess

        test_commands = [
            ["python", "-m", "pytest", "tests/unit/", "-v"],
            ["python", "-m", "pytest", "tests/integration/", "-v"],
            ["python", "-m", "pytest", "tests/functional/", "-v"],
            ["python", "-m", "pytest", "tests/performance/", "-v"],
        ]

        results = {}

        for cmd in test_commands:
            test_type = cmd[3].split("/")[-2]  # Extract test type
            logger.info(f"Running {test_type} tests")

            try:
                result = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=600
                )
                results[test_type] = {
                    "returncode": result.returncode,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                }
            except subprocess.TimeoutExpired:
                results[test_type] = {"error": "Test timed out"}
            except Exception as e:
                results[test_type] = {"error": str(e)}

        return results

    def run_feature_engineering(self, **kwargs):
        """Run feature engineering pipeline."""
        logger.info("Running feature engineering")

        from fxml4.features.feature_engineering import FeatureEngineer

        symbols = kwargs.get("symbols", ["EURUSD", "GBPUSD"])
        timeframes = kwargs.get("timeframes", ["1h", "4h", "daily"])

        results = {}

        for symbol in symbols:
            results[symbol] = {}
            for timeframe in timeframes:
                logger.info(f"Engineering features for {symbol} on {timeframe}")

                engineer = FeatureEngineer(timeframe=timeframe)
                features = engineer.engineer_features_for_symbol(symbol)

                results[symbol][timeframe] = {
                    "feature_count": len(features.columns),
                    "sample_count": len(features),
                    "date_range": [
                        str(features.index.min()),
                        str(features.index.max()),
                    ],
                }

        return results

    def run_final_comprehensive_backtest(self, **kwargs):
        """Run final comprehensive backtest."""
        logger.info("Running final comprehensive backtest")

        config = {
            "final_version": True,
            "comprehensive_analysis": True,
            "all_features_enabled": True,
            "production_ready": True,
            "detailed_reporting": True,
            "performance_optimization": True,
        }

        return self._run_system(config, "final_comprehensive_backtest")

    def run_full_fxml4_enhanced(self, **kwargs):
        """Run full FXML4 enhanced system."""
        logger.info("Running full FXML4 enhanced")

        config = {
            "full_system": True,
            "enhanced_mode": True,
            "all_components": True,
            "real_time_processing": True,
            "advanced_analytics": True,
            "comprehensive_monitoring": True,
        }

        return self._run_system(config, "full_fxml4_enhanced")

    def run_full_optimized_backtest(self, **kwargs):
        """Run full optimized backtest."""
        logger.info("Running full optimized backtest")

        config = {
            "optimized": True,
            "parameter_optimization": True,
            "hyperparameter_tuning": True,
            "cross_validation": True,
            "walk_forward_analysis": True,
            "monte_carlo_simulation": True,
        }

        return self._run_system(config, "full_optimized_backtest")

    def run_full_production_backtest(self, **kwargs):
        """Run full production backtest."""
        logger.info("Running full production backtest")

        config = {
            "production_mode": True,
            "real_market_conditions": True,
            "production_data": True,
            "compliance_enabled": True,
            "risk_management_strict": True,
            "audit_logging": True,
        }

        return self._run_system(config, "full_production_backtest")

    def run_full_system_production(self, **kwargs):
        """Run full system in production mode."""
        logger.info("Running full system production")

        config = {
            "production_deployment": True,
            "live_trading": kwargs.get("live_trading", False),
            "real_time_data": True,
            "production_database": True,
            "monitoring_enabled": True,
            "alerting_enabled": True,
        }

        return self._run_system(config, "full_system_production")

    def run_fxml4_full_capabilities(self, **kwargs):
        """Run FXML4 with full capabilities."""
        logger.info("Running FXML4 full capabilities")

        config = {
            "all_capabilities": True,
            "ml_enabled": True,
            "elliott_wave_enabled": True,
            "sentiment_enabled": True,
            "news_enabled": True,
            "economic_data_enabled": True,
            "multi_timeframe": True,
            "ensemble_methods": True,
        }

        return self._run_system(config, "fxml4_full_capabilities")

    def run_fxml4_optimized(self, **kwargs):
        """Run optimized FXML4 system."""
        logger.info("Running FXML4 optimized")

        config = {
            "optimized_performance": True,
            "efficient_algorithms": True,
            "memory_optimization": True,
            "cpu_optimization": True,
            "parallel_processing": True,
            "caching_enabled": True,
        }

        return self._run_system(config, "fxml4_optimized")

    def run_fxml4_profitable_final(self, **kwargs):
        """Run final profitable FXML4 configuration."""
        logger.info("Running FXML4 profitable final")

        config = {
            "profitable_mode": True,
            "proven_strategies": True,
            "risk_optimized": True,
            "return_maximized": True,
            "final_version": True,
            "production_ready": True,
        }

        return self._run_system(config, "fxml4_profitable_final")

    def run_performance_test(self, **kwargs):
        """Run performance tests."""
        logger.info("Running performance tests")

        import time

        import psutil

        # Monitor system performance
        start_time = time.time()
        start_memory = psutil.virtual_memory().used

        # Run system with performance monitoring
        config = {
            "performance_monitoring": True,
            "benchmark_mode": True,
            "stress_testing": kwargs.get("stress_testing", False),
        }

        result = self._run_system(config, "performance_test")

        # Calculate performance metrics
        end_time = time.time()
        end_memory = psutil.virtual_memory().used

        performance_metrics = {
            "execution_time": end_time - start_time,
            "memory_usage": end_memory - start_memory,
            "cpu_usage": psutil.cpu_percent(),
            "result": result,
        }

        return performance_metrics

    def run_production_400x_robust(self, **kwargs):
        """Run production 400x robust system."""
        logger.info("Running production 400x robust")

        config = {
            "leverage": 400,
            "robust_mode": True,
            "production_grade": True,
            "fault_tolerance": True,
            "error_recovery": True,
            "monitoring_comprehensive": True,
        }

        return self._run_system(config, "production_400x_robust")

    def run_production_400x_simple(self, **kwargs):
        """Run production 400x simple system."""
        logger.info("Running production 400x simple")

        config = {
            "leverage": 400,
            "simple_mode": True,
            "minimal_features": True,
            "basic_risk_management": True,
            "easy_to_understand": True,
        }

        return self._run_system(config, "production_400x_simple")

    def run_production_backtest(self, **kwargs):
        """Run production backtest."""
        logger.info("Running production backtest")

        config = {
            "production_backtest": True,
            "realistic_conditions": True,
            "production_data_quality": True,
            "comprehensive_reporting": True,
        }

        return self._run_system(config, "production_backtest")

    def run_production_demo_final(self, **kwargs):
        """Run final production demo."""
        logger.info("Running production demo final")

        config = {
            "demo_mode": True,
            "production_features": True,
            "final_version": True,
            "showcase_mode": True,
            "interactive_demo": True,
        }

        return self._run_system(config, "production_demo_final")

    def run_profitable_backtest(self, **kwargs):
        """Run profitable backtest configuration."""
        logger.info("Running profitable backtest")

        config = {
            "profit_focused": True,
            "optimized_for_returns": True,
            "risk_balanced": True,
            "proven_strategies_only": True,
        }

        return self._run_system(config, "profitable_backtest")

    def run_profitable_fxml4_system(self, **kwargs):
        """Run profitable FXML4 system."""
        logger.info("Running profitable FXML4 system")

        config = {
            "profitable_configuration": True,
            "tested_strategies": True,
            "optimized_parameters": True,
            "risk_management_balanced": True,
        }

        return self._run_system(config, "profitable_fxml4_system")

    def run_api_server(self, **kwargs):
        """Run API server."""
        logger.info("Starting API server")

        import uvicorn

        app = create_app()

        config = uvicorn.Config(
            app,
            host=kwargs.get("host", "0.0.0.0"),
            port=kwargs.get("port", 8000),
            log_level=kwargs.get("log_level", "info"),
        )

        server = uvicorn.Server(config)
        self.running_services["api_server"] = server

        try:
            server.run()
        except KeyboardInterrupt:
            logger.info("API server stopped by user")

        return {"status": "API server started"}

    def run_dashboard(self, **kwargs):
        """Run dashboard."""
        logger.info("Starting dashboard")

        dashboard = DashboardManager()
        self.running_services["dashboard"] = dashboard

        try:
            dashboard.run(
                host=kwargs.get("host", "0.0.0.0"), port=kwargs.get("port", 8501)
            )
        except KeyboardInterrupt:
            logger.info("Dashboard stopped by user")

        return {"status": "Dashboard started"}

    def run_worker(self, **kwargs):
        """Run worker process."""
        logger.info("Starting worker")

        worker = WorkerManager()
        self.running_services["worker"] = worker

        try:
            worker.run()
        except KeyboardInterrupt:
            logger.info("Worker stopped by user")

        return {"status": "Worker started"}

    def run_training(self, **kwargs):
        """Run training process."""
        logger.info("Starting training")

        training = TrainingManager()
        self.running_services["training"] = training

        try:
            result = training.run_training(
                symbols=kwargs.get("symbols", ["EURUSD", "GBPUSD"]),
                model_types=kwargs.get("model_types", ["rf", "gb"]),
            )
            return result
        except KeyboardInterrupt:
            logger.info("Training stopped by user")

        return {"status": "Training completed"}

    def run_all_services(self, **kwargs):
        """Run all services simultaneously."""
        logger.info("Starting all services")

        services = [
            ("api_server", self.run_api_server, {"port": 8000}),
            ("dashboard", self.run_dashboard, {"port": 8501}),
            ("worker", self.run_worker, {}),
        ]

        with ThreadPoolExecutor(max_workers=len(services)) as executor:
            futures = []

            for name, func, config in services:
                future = executor.submit(func, **config)
                futures.append((name, future))

            try:
                # Wait for shutdown signal
                self.shutdown_event.wait()
            except KeyboardInterrupt:
                logger.info("All services stopped by user")

            # Shutdown all services
            self.shutdown_services()

        return {"status": "All services started"}

    def _run_system(self, config, system_name):
        """Run system with given configuration."""
        logger.info(f"Running {system_name} with config: {config}")

        try:
            # Initialize system components based on config
            if config.get("use_ml", False):
                from fxml4.ml.models import ModelLoader

                model_loader = ModelLoader()

            if config.get("use_elliott_wave", False):
                from fxml4.wave_analysis.elliott_wave import ElliottWaveAnalyzer

                elliott_analyzer = ElliottWaveAnalyzer()

            if config.get("use_sentiment", False):
                from fxml4.llm_integration.sentiment_analysis import SentimentAnalyzer

                sentiment_analyzer = SentimentAnalyzer()

            # Run system
            engine = EventDrivenEngine(config)
            result = engine.run()

            # Save results
            output_dir = Path("output") / system_name
            output_dir.mkdir(parents=True, exist_ok=True)

            with open(
                output_dir / f'results_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json',
                "w",
            ) as f:
                json.dump(result, f, indent=2, default=str)

            return result

        except Exception as e:
            logger.error(f"Error running {system_name}: {e}")
            return {"error": str(e), "system": system_name}

    def run_mode(self, mode_name, **kwargs):
        """Run a specific mode."""
        if mode_name not in self.run_modes:
            raise ValueError(f"Unknown run mode: {mode_name}")

        return self.run_modes[mode_name](**kwargs)

    def list_run_modes(self):
        """List available run modes."""
        return list(self.run_modes.keys())


def main():
    """Main CLI interface."""
    parser = argparse.ArgumentParser(description="FXML4 Consolidated System Runner")
    parser.add_argument("--mode", required=True, help="Run mode to execute")
    parser.add_argument("--symbols", nargs="+", help="Trading symbols")
    parser.add_argument("--leverage", type=float, default=1, help="Leverage")
    parser.add_argument("--host", default="0.0.0.0", help="Host for services")
    parser.add_argument("--port", type=int, help="Port for services")
    parser.add_argument(
        "--list-modes", action="store_true", help="List available run modes"
    )
    parser.add_argument(
        "--live-trading", action="store_true", help="Enable live trading"
    )
    parser.add_argument(
        "--stress-testing", action="store_true", help="Enable stress testing"
    )

    args = parser.parse_args()

    runner = ConsolidatedSystemRunner()

    if args.list_modes:
        print("Available run modes:")
        for mode in runner.list_run_modes():
            print(f"  - {mode}")
        return

    # Run specified mode
    kwargs = {
        "symbols": args.symbols,
        "leverage": args.leverage,
        "host": args.host,
        "port": args.port,
        "live_trading": args.live_trading,
        "stress_testing": args.stress_testing,
    }

    logger.info(f"Running mode: {args.mode}")

    try:
        result = runner.run_mode(args.mode, **kwargs)

        if "error" in result:
            logger.error(f"Run failed: {result['error']}")
            sys.exit(1)
        else:
            logger.info(f"Run completed successfully")

    except KeyboardInterrupt:
        logger.info("Run interrupted by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
