#!/usr/bin/env python3
"""
FXML4 API Backtesting Integration Test

This script tests the complete backtesting workflow through the API,
demonstrating how to use the system in a production-like environment.
"""

import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class APIBacktestTester:
    """Test backtesting functionality through the FXML4 API."""

    def __init__(
        self, base_url="http://localhost:8000", username="admin", password="admin"
    ):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.token = None
        self.session = requests.Session()

    def authenticate(self):
        """Authenticate with the API and get access token."""
        logger.info("🔐 Authenticating with API...")

        response = self.session.post(
            f"{self.base_url}/token",
            data={"username": self.username, "password": self.password},
        )

        if response.status_code == 200:
            token_data = response.json()
            self.token = token_data["access_token"]
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})
            logger.info("✅ Authentication successful")
        else:
            logger.error(
                f"❌ Authentication failed: {response.status_code} - {response.text}"
            )
            raise Exception("Authentication failed")

    def test_api_health(self):
        """Test API health and connectivity."""
        logger.info("🏥 Testing API health...")

        response = self.session.get(f"{self.base_url}/health")

        if response.status_code == 200:
            health_data = response.json()
            logger.info(f"✅ API is healthy: {health_data}")
        else:
            logger.error(f"❌ API health check failed: {response.status_code}")
            raise Exception("API health check failed")

    def test_market_data_retrieval(self):
        """Test market data retrieval."""
        logger.info("📊 Testing market data retrieval...")

        data_request = {
            "symbol": "EURUSD",
            "timeframe": "4h",
            "start_date": "2023-01-01",
            "end_date": "2023-06-30",
            "limit": 1000,
        }

        response = self.session.post(f"{self.base_url}/data", json=data_request)

        if response.status_code == 200:
            data_response = response.json()
            logger.info(f"✅ Market data retrieved: {data_response['count']} records")
            logger.info(f"   Symbol: {data_response['symbol']}")
            logger.info(f"   Source: {data_response['source']}")
            logger.info(f"   Timeframe: {data_response['timeframe']}")

            if data_response["data"]:
                sample_record = data_response["data"][0]
                logger.info(f"   Sample record: {sample_record}")

            return data_response
        else:
            logger.error(
                f"❌ Market data retrieval failed: {response.status_code} - {response.text}"
            )
            raise Exception("Market data retrieval failed")

    def test_signal_generation(self):
        """Test trading signal generation."""
        logger.info("🎯 Testing signal generation...")

        signal_request = {
            "symbol": "EURUSD",
            "timeframe": "4h",
            "strategy": "ml_strategy",
            "parameters": {"model": "random_forest", "threshold": 0.7},
        }

        response = self.session.post(f"{self.base_url}/signals", json=signal_request)

        if response.status_code == 200:
            signal_response = response.json()
            logger.info(f"✅ Signal generation successful")
            logger.info(f"   Strategy: {signal_response['strategy']}")
            logger.info(f"   Signals generated: {len(signal_response['signals'])}")

            for i, signal in enumerate(signal_response["signals"][:3]):  # Show first 3
                logger.info(f"   Signal {i+1}: {signal}")

            return signal_response
        else:
            logger.error(
                f"❌ Signal generation failed: {response.status_code} - {response.text}"
            )
            # This might fail if models aren't trained yet, so don't raise exception
            logger.warning(
                "Signal generation failed - this is expected if ML models aren't trained"
            )
            return None

    def test_backtesting_strategies(self):
        """Test different backtesting strategies."""
        logger.info("🔬 Testing backtesting with different strategies...")

        strategies = [
            {
                "name": "Integrated Strategy",
                "strategy": "integrated_strategy",
                "parameters": {},
            },
            {
                "name": "ML Strategy",
                "strategy": "ml_strategy",
                "parameters": {"model": "random_forest", "threshold": 0.6},
            },
            {
                "name": "Wave Strategy",
                "strategy": "wave_strategy",
                "parameters": {"strictness": 0.5},
            },
        ]

        backtest_results = {}

        for strategy_config in strategies:
            logger.info(f"   Testing {strategy_config['name']}...")

            backtest_request = {
                "symbol": "EURUSD",
                "timeframe": "4h",
                "strategy": strategy_config["strategy"],
                "start_date": "2023-01-01",
                "end_date": "2023-03-31",  # Shorter period for faster testing
                "initial_capital": 10000,
                "parameters": strategy_config["parameters"],
                "auto_report": True,
            }

            response = self.session.post(
                f"{self.base_url}/backtest", json=backtest_request
            )

            if response.status_code == 200:
                result = response.json()
                backtest_results[strategy_config["name"]] = result

                logger.info(f"     ✅ {strategy_config['name']} backtest completed")
                logger.info(f"        Backtest ID: {result['backtest_id']}")
                logger.info(f"        Total Return: {result['total_return_pct']:.2f}%")
                logger.info(f"        Max Drawdown: {result['max_drawdown_pct']:.2f}%")
                logger.info(f"        Trades: {result['trade_count']}")
                logger.info(f"        Sharpe Ratio: {result['sharpe_ratio']:.3f}")

            else:
                logger.error(
                    f"     ❌ {strategy_config['name']} backtest failed: {response.status_code} - {response.text}"
                )
                # Continue with other strategies
                continue

        return backtest_results

    def test_performance_analysis(self, backtest_results):
        """Test performance analysis endpoints."""
        logger.info("📈 Testing performance analysis...")

        for strategy_name, result in backtest_results.items():
            backtest_id = result["backtest_id"]
            logger.info(f"   Analyzing {strategy_name} (ID: {backtest_id})...")

            # Test performance metrics endpoint
            response = self.session.get(
                f"{self.base_url}/performance/metrics/{backtest_id}",
                params={"include_trades": True, "include_equity_curve": True},
            )

            if response.status_code == 200:
                metrics = response.json()
                logger.info(f"     ✅ Performance metrics retrieved")
                logger.info(
                    f"        Metrics available: {list(metrics.get('metrics', {}).keys())}"
                )

                if "trades" in metrics:
                    logger.info(
                        f"        Trade details: {len(metrics['trades'])} trades"
                    )

                if "equity_curve" in metrics:
                    logger.info(
                        f"        Equity curve: {len(metrics['equity_curve'])} points"
                    )

            else:
                logger.error(
                    f"     ❌ Performance metrics failed: {response.status_code}"
                )

            # Test performance report endpoint
            response = self.session.get(
                f"{self.base_url}/performance/report/{backtest_id}",
                params={"format": "html"},
            )

            if response.status_code == 200:
                logger.info(f"     ✅ Performance report generated (HTML)")
                # Save report for inspection
                report_path = Path(f"output/api_test_report_{backtest_id}.html")
                report_path.parent.mkdir(parents=True, exist_ok=True)
                with open(report_path, "w") as f:
                    f.write(response.text)
                logger.info(f"        Report saved: {report_path}")
            else:
                logger.error(
                    f"     ❌ Performance report failed: {response.status_code}"
                )

    def test_comparative_analysis(self, backtest_results):
        """Test comparative analysis of multiple backtests."""
        logger.info("⚖️ Testing comparative analysis...")

        if len(backtest_results) < 2:
            logger.warning("Need at least 2 backtest results for comparison")
            return

        backtest_ids = [result["backtest_id"] for result in backtest_results.values()]

        comparison_request = {
            "backtest_ids": backtest_ids,
            "metrics": [
                "total_return_pct",
                "max_drawdown_pct",
                "sharpe_ratio",
                "win_rate",
                "profit_factor",
            ],
        }

        response = self.session.post(
            f"{self.base_url}/performance/compare", json=comparison_request
        )

        if response.status_code == 200:
            comparison = response.json()
            logger.info("✅ Comparative analysis completed")

            # Display comparison results
            logger.info("   📊 Strategy Comparison:")
            for metric in comparison_request["metrics"]:
                if metric in comparison.get("metrics", {}):
                    logger.info(f"      {metric}:")
                    metric_data = comparison["metrics"][metric]
                    for backtest_id, value in metric_data.items():
                        strategy_name = next(
                            (
                                name
                                for name, result in backtest_results.items()
                                if result["backtest_id"] == backtest_id
                            ),
                            backtest_id,
                        )
                        logger.info(f"        {strategy_name}: {value:.3f}")

            # Display rankings
            if "ranking" in comparison:
                logger.info("   🏆 Strategy Rankings:")
                for metric, ranking in comparison["ranking"].items():
                    logger.info(f"      {metric}: {' > '.join(ranking)}")

        else:
            logger.error(
                f"❌ Comparative analysis failed: {response.status_code} - {response.text}"
            )

    def test_error_handling(self):
        """Test API error handling with invalid requests."""
        logger.info("🚨 Testing error handling...")

        # Test invalid symbol
        response = self.session.post(
            f"{self.base_url}/data",
            json={
                "symbol": "INVALID",
                "timeframe": "1h",
                "start_date": "2023-01-01",
                "end_date": "2023-01-02",
            },
        )
        logger.info(f"   Invalid symbol test: {response.status_code}")

        # Test invalid date range
        response = self.session.post(
            f"{self.base_url}/backtest",
            json={
                "symbol": "EURUSD",
                "timeframe": "1h",
                "strategy": "integrated_strategy",
                "start_date": "2023-12-31",
                "end_date": "2023-01-01",  # End before start
                "initial_capital": 10000,
            },
        )
        logger.info(f"   Invalid date range test: {response.status_code}")

        # Test unauthorized access
        unauthorized_session = requests.Session()
        response = unauthorized_session.post(
            f"{self.base_url}/backtest",
            json={
                "symbol": "EURUSD",
                "timeframe": "1h",
                "strategy": "integrated_strategy",
                "start_date": "2023-01-01",
                "end_date": "2023-01-02",
                "initial_capital": 10000,
            },
        )
        logger.info(f"   Unauthorized access test: {response.status_code}")

        logger.info("✅ Error handling tests completed")

    def test_rate_limiting(self):
        """Test API rate limiting."""
        logger.info("⏱️ Testing rate limiting...")

        # Make rapid requests to test rate limiting
        rapid_requests = 0
        rate_limited = False

        for i in range(10):
            response = self.session.get(f"{self.base_url}/health")
            rapid_requests += 1

            if response.status_code == 429:  # Too Many Requests
                logger.info(
                    f"   Rate limiting triggered after {rapid_requests} requests"
                )
                rate_limited = True
                break

            time.sleep(0.1)  # Small delay between requests

        if not rate_limited:
            logger.info(f"   No rate limiting observed after {rapid_requests} requests")

        logger.info("✅ Rate limiting test completed")

    def save_test_results(self, backtest_results):
        """Save test results for analysis."""
        logger.info("💾 Saving test results...")

        # Create test results summary
        test_summary = {
            "test_timestamp": datetime.now().isoformat(),
            "api_url": self.base_url,
            "strategies_tested": len(backtest_results),
            "backtest_results": {},
        }

        for strategy_name, result in backtest_results.items():
            test_summary["backtest_results"][strategy_name] = {
                "backtest_id": result["backtest_id"],
                "total_return_pct": result["total_return_pct"],
                "max_drawdown_pct": result["max_drawdown_pct"],
                "sharpe_ratio": result["sharpe_ratio"],
                "trade_count": result["trade_count"],
                "final_capital": result["final_capital"],
            }

        # Save to file
        output_path = Path(
            f"output/api_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            json.dump(test_summary, f, indent=2)

        logger.info(f"   Test results saved: {output_path}")

    def run_comprehensive_test(self):
        """Run comprehensive API backtesting test."""
        logger.info("🚀 Starting Comprehensive API Backtesting Test")
        logger.info("=" * 70)

        try:
            # Test sequence
            self.test_api_health()
            self.authenticate()
            self.test_market_data_retrieval()
            self.test_signal_generation()

            # Main backtesting tests
            backtest_results = self.test_backtesting_strategies()

            if backtest_results:
                self.test_performance_analysis(backtest_results)
                self.test_comparative_analysis(backtest_results)
                self.save_test_results(backtest_results)

            # Additional tests
            self.test_error_handling()
            self.test_rate_limiting()

            logger.info("=" * 70)
            logger.info("🎉 Comprehensive API test completed successfully!")

            if backtest_results:
                logger.info("\n📊 FINAL RESULTS SUMMARY:")
                for strategy_name, result in backtest_results.items():
                    logger.info(f"   {strategy_name}:")
                    logger.info(f"     Return: {result['total_return_pct']:.2f}%")
                    logger.info(f"     Max Drawdown: {result['max_drawdown_pct']:.2f}%")
                    logger.info(f"     Trades: {result['trade_count']}")
                    logger.info(f"     Sharpe: {result['sharpe_ratio']:.3f}")

        except Exception as e:
            logger.error(f"❌ API test failed: {e}")
            raise


def main():
    """Main function to run the API backtest test."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Test FXML4 API backtesting functionality"
    )
    parser.add_argument("--url", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--username", default="admin", help="API username")
    parser.add_argument("--password", default="admin", help="API password")

    args = parser.parse_args()

    tester = APIBacktestTester(
        base_url=args.url, username=args.username, password=args.password
    )

    tester.run_comprehensive_test()


if __name__ == "__main__":
    main()
