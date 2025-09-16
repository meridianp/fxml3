#!/usr/bin/env python3
"""
FXML4 API Contract Test Runner

This script runs comprehensive API contract tests for 145+ endpoints across
the FXML4 trading platform. It validates request/response schemas, endpoint
behavior, authentication, and backward compatibility.

Usage:
    python scripts/run_api_contract_tests.py --all
    python scripts/run_api_contract_tests.py --category trading
    python scripts/run_api_contract_tests.py --endpoint "/trading/orders"
    python scripts/run_api_contract_tests.py --parallel --output report.json
"""

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import contract testing framework
try:
    from tests.api_contracts.schemas import (
        ALL_SCHEMAS,
        get_request_schema,
        get_response_schema,
    )
    from tests.api_contracts.test_contract_framework import (
        APIContractTester,
        APIEndpoint,
        ContractTestCase,
        EndpointCategory,
        HTTPMethod,
    )

    CONTRACT_TESTING_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Contract testing framework not available: {e}")
    CONTRACT_TESTING_AVAILABLE = False


class ComprehensiveAPIContractTester:
    """Comprehensive API contract test runner with reporting and analytics."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.tester: Optional[APIContractTester] = None
        self.test_results: List[Dict[str, Any]] = []
        self.start_time: Optional[datetime] = None

    async def run_all_contract_tests(
        self,
        categories: Optional[List[str]] = None,
        endpoints: Optional[List[str]] = None,
        parallel: bool = False,
        max_concurrent: int = 10,
    ) -> Dict[str, Any]:
        """Run comprehensive API contract tests."""
        self.start_time = datetime.now()

        print("FXML4 API Contract Testing Suite")
        print("=" * 60)
        print(f"Base URL: {self.base_url}")
        print(f"Parallel Execution: {parallel}")
        print(f"Max Concurrent: {max_concurrent}")

        if not CONTRACT_TESTING_AVAILABLE:
            return {"error": "Contract testing framework not available"}

        async with APIContractTester(self.base_url) as tester:
            self.tester = tester

            # Generate endpoints to test
            all_endpoints = tester.generate_test_endpoints()

            # Filter endpoints if specified
            endpoints_to_test = self._filter_endpoints(
                all_endpoints, categories, endpoints
            )

            print(f"Testing {len(endpoints_to_test)} endpoints...")

            # Run tests
            if parallel:
                results = await self._run_parallel_tests(
                    endpoints_to_test, max_concurrent
                )
            else:
                results = await self._run_sequential_tests(endpoints_to_test)

            # Generate comprehensive report
            report = self._generate_comprehensive_report(results)

            return report

    def _filter_endpoints(
        self,
        all_endpoints: List[APIEndpoint],
        categories: Optional[List[str]] = None,
        endpoint_paths: Optional[List[str]] = None,
    ) -> List[APIEndpoint]:
        """Filter endpoints based on categories and paths."""
        filtered = all_endpoints

        if categories:
            category_enums = []
            for cat in categories:
                try:
                    category_enums.append(EndpointCategory(cat.lower()))
                except ValueError:
                    print(f"Warning: Unknown category '{cat}'")

            if category_enums:
                filtered = [ep for ep in filtered if ep.category in category_enums]

        if endpoint_paths:
            filtered = [
                ep for ep in filtered if any(path in ep.path for path in endpoint_paths)
            ]

        return filtered

    async def _run_sequential_tests(
        self, endpoints: List[APIEndpoint]
    ) -> List[Dict[str, Any]]:
        """Run tests sequentially."""
        results = []

        for i, endpoint in enumerate(endpoints, 1):
            print(
                f"\n[{i}/{len(endpoints)}] Testing {endpoint.method.value} {endpoint.path}"
            )

            # Generate test cases for endpoint
            test_cases = self._generate_comprehensive_test_cases(endpoint)

            for test_case in test_cases:
                try:
                    result = await self.tester.test_endpoint_contract(test_case)
                    result_dict = self._convert_result_to_dict(result)
                    results.append(result_dict)

                    # Print immediate feedback
                    status_emoji = (
                        "✅" if result.passed else "❌" if result.failed else "⚠️"
                    )
                    print(f"    {status_emoji} {test_case.name}: {result.result.value}")

                except Exception as e:
                    print(f"    💥 {test_case.name}: Error - {e}")
                    results.append(
                        {
                            "test_id": test_case.test_id,
                            "endpoint": endpoint.endpoint_id,
                            "test_name": test_case.name,
                            "result": "error",
                            "error_message": str(e),
                            "execution_time_ms": 0,
                        }
                    )

        return results

    async def _run_parallel_tests(
        self, endpoints: List[APIEndpoint], max_concurrent: int
    ) -> List[Dict[str, Any]]:
        """Run tests in parallel with concurrency control."""
        semaphore = asyncio.Semaphore(max_concurrent)
        tasks = []

        async def test_endpoint_with_semaphore(
            endpoint: APIEndpoint,
        ) -> List[Dict[str, Any]]:
            async with semaphore:
                endpoint_results = []
                test_cases = self._generate_comprehensive_test_cases(endpoint)

                for test_case in test_cases:
                    try:
                        result = await self.tester.test_endpoint_contract(test_case)
                        result_dict = self._convert_result_to_dict(result)
                        endpoint_results.append(result_dict)
                    except Exception as e:
                        endpoint_results.append(
                            {
                                "test_id": test_case.test_id,
                                "endpoint": endpoint.endpoint_id,
                                "test_name": test_case.name,
                                "result": "error",
                                "error_message": str(e),
                                "execution_time_ms": 0,
                            }
                        )

                return endpoint_results

        # Create tasks for all endpoints
        for endpoint in endpoints:
            task = test_endpoint_with_semaphore(endpoint)
            tasks.append(task)

        print(f"Running {len(tasks)} endpoint tests in parallel...")

        # Execute all tasks
        endpoint_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Flatten results
        all_results = []
        for endpoint_result in endpoint_results:
            if isinstance(endpoint_result, Exception):
                print(f"Endpoint test failed: {endpoint_result}")
            else:
                all_results.extend(endpoint_result)

        return all_results

    def _generate_comprehensive_test_cases(
        self, endpoint: APIEndpoint
    ) -> List[ContractTestCase]:
        """Generate comprehensive test cases for an endpoint."""
        test_cases = []

        # Basic success case
        success_data = self._generate_realistic_test_data(endpoint)
        test_cases.append(
            ContractTestCase(
                name="success_case",
                endpoint=endpoint,
                test_data=success_data,
                expected_status=200 if endpoint.method == HTTPMethod.GET else 201,
            )
        )

        # Authentication tests
        if endpoint.auth_required:
            test_cases.append(
                ContractTestCase(
                    name="unauthorized_access",
                    endpoint=endpoint,
                    test_data=success_data,
                    expected_status=401,
                    auth_token=None,
                )
            )

            test_cases.append(
                ContractTestCase(
                    name="invalid_token",
                    endpoint=endpoint,
                    test_data=success_data,
                    expected_status=401,
                    auth_token="invalid_token_12345",
                )
            )

        # Validation tests for POST/PUT endpoints
        if endpoint.method in [HTTPMethod.POST, HTTPMethod.PUT, HTTPMethod.PATCH]:
            # Invalid data test
            invalid_data = self._generate_invalid_test_data(endpoint)
            test_cases.append(
                ContractTestCase(
                    name="invalid_data",
                    endpoint=endpoint,
                    test_data=invalid_data,
                    expected_status=400,
                )
            )

            # Missing required fields
            minimal_data = self._generate_minimal_test_data(endpoint)
            test_cases.append(
                ContractTestCase(
                    name="missing_required_fields",
                    endpoint=endpoint,
                    test_data=minimal_data,
                    expected_status=400,
                )
            )

        # Performance test
        test_cases.append(
            ContractTestCase(
                name="performance_test",
                endpoint=endpoint,
                test_data=success_data,
                expected_status=200 if endpoint.method == HTTPMethod.GET else 201,
                timeout_seconds=5.0,  # Stricter timeout for performance
            )
        )

        return test_cases

    def _generate_realistic_test_data(self, endpoint: APIEndpoint) -> Dict[str, Any]:
        """Generate realistic test data for an endpoint."""
        if "/auth/login" in endpoint.path:
            return {
                "username": "test_trader",
                "password": "SecurePass123!",  # pragma: allowlist secret
                "remember_me": False,
            }
        elif "/trading/orders" in endpoint.path and endpoint.method == HTTPMethod.POST:
            return {
                "symbol": "EURUSD",
                "side": "BUY",
                "quantity": 10000,
                "order_type": "LIMIT",
                "price": 1.1000,
                "time_in_force": "GTC",
                "client_order_id": "CLIENT_ORDER_123",
            }
        elif "/market-data/bars" in endpoint.path:
            return {
                "symbol": "EURUSD",
                "timeframe": "1h",
                "start_date": "2023-01-01T00:00:00Z",
                "end_date": "2023-01-02T00:00:00Z",
                "limit": 100,
            }
        elif "/ml/predictions" in endpoint.path:
            return {
                "symbol": "EURUSD",
                "model_id": "550e8400-e29b-41d4-a716-446655440000",
                "features": {
                    "technical_indicators": {
                        "rsi": 65.5,
                        "macd": 0.0025,
                        "bollinger_upper": 1.1050,
                        "bollinger_lower": 1.0950,
                    },
                    "market_data": {
                        "current_price": 1.1000,
                        "volume": 1500000,
                        "volatility": 0.15,
                    },
                },
                "prediction_horizon": "1h",
            }
        elif "/risk/limits" in endpoint.path and endpoint.method == HTTPMethod.PUT:
            return {
                "max_position_size": 100000,
                "max_daily_loss": 5000,
                "max_leverage": 50,
                "max_open_positions": 10,
                "var_limit": 10000,
            }
        else:
            return {"test_parameter": "test_value"}

    def _generate_invalid_test_data(self, endpoint: APIEndpoint) -> Dict[str, Any]:
        """Generate invalid test data to test validation."""
        if "/auth/login" in endpoint.path:
            return {
                "username": "",  # Invalid: empty username
                "password": "123",  # Invalid: too short
                "remember_me": "yes",  # Invalid: should be boolean
            }
        elif "/trading/orders" in endpoint.path:
            return {
                "symbol": "INVALID",  # Invalid currency pair
                "side": "INVALID_SIDE",  # Invalid side
                "quantity": -1000,  # Invalid: negative quantity
                "order_type": "INVALID_TYPE",  # Invalid order type
                "price": -1.0,  # Invalid: negative price
            }
        else:
            return {"invalid_field": None}

    def _generate_minimal_test_data(self, endpoint: APIEndpoint) -> Dict[str, Any]:
        """Generate minimal test data (missing some required fields)."""
        if "/auth/login" in endpoint.path:
            return {"username": "test_user"}  # Missing password
        elif "/trading/orders" in endpoint.path:
            return {
                "symbol": "EURUSD",
                "side": "BUY",
                # Missing quantity and order_type
            }
        else:
            return {}

    def _convert_result_to_dict(self, result) -> Dict[str, Any]:
        """Convert test result to dictionary for JSON serialization."""
        return {
            "test_id": result.test_case.test_id,
            "endpoint": result.test_case.endpoint.endpoint_id,
            "category": result.test_case.endpoint.category.value,
            "test_name": result.test_case.name,
            "result": result.result.value,
            "execution_time_ms": result.execution_time_ms,
            "response_status": result.response_status,
            "expected_status": result.test_case.expected_status,
            "schema_validation_errors": result.schema_validation_errors,
            "error_message": result.error_message,
            "timestamp": result.timestamp.isoformat(),
        }

    def _generate_comprehensive_report(
        self, results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generate comprehensive test report with analytics."""
        if not results:
            return {"error": "No test results available"}

        # Basic statistics
        total_tests = len(results)
        passed_tests = sum(1 for r in results if r["result"] == "pass")
        failed_tests = sum(1 for r in results if r["result"] == "fail")
        error_tests = sum(1 for r in results if r["result"] == "error")
        skipped_tests = sum(1 for r in results if r["result"] == "skip")

        # Performance statistics
        response_times = [
            r["execution_time_ms"] for r in results if r["execution_time_ms"] > 0
        ]
        avg_response_time = (
            sum(response_times) / len(response_times) if response_times else 0
        )
        max_response_time = max(response_times) if response_times else 0
        min_response_time = min(response_times) if response_times else 0

        # Category breakdown
        category_stats = {}
        for result in results:
            category = result["category"]
            if category not in category_stats:
                category_stats[category] = {
                    "total": 0,
                    "passed": 0,
                    "failed": 0,
                    "errors": 0,
                }

            category_stats[category]["total"] += 1
            if result["result"] == "pass":
                category_stats[category]["passed"] += 1
            elif result["result"] == "fail":
                category_stats[category]["failed"] += 1
            elif result["result"] == "error":
                category_stats[category]["errors"] += 1

        # Endpoint breakdown
        endpoint_stats = {}
        for result in results:
            endpoint = result["endpoint"]
            if endpoint not in endpoint_stats:
                endpoint_stats[endpoint] = {"total": 0, "passed": 0, "failed": 0}

            endpoint_stats[endpoint]["total"] += 1
            if result["result"] == "pass":
                endpoint_stats[endpoint]["passed"] += 1
            elif result["result"] in ["fail", "error"]:
                endpoint_stats[endpoint]["failed"] += 1

        # Failure analysis
        failures = [r for r in results if r["result"] in ["fail", "error"]]
        failure_patterns = {}
        for failure in failures:
            error_msg = failure.get("error_message", "Unknown error")
            if error_msg not in failure_patterns:
                failure_patterns[error_msg] = 0
            failure_patterns[error_msg] += 1

        # Schema validation issues
        schema_issues = []
        for result in results:
            if result.get("schema_validation_errors"):
                schema_issues.extend(result["schema_validation_errors"])

        # Performance issues
        slow_endpoints = [
            r for r in results if r["execution_time_ms"] > 1000  # > 1 second
        ]

        # Generate recommendations
        recommendations = self._generate_recommendations(
            total_tests,
            passed_tests,
            failed_tests,
            avg_response_time,
            category_stats,
            slow_endpoints,
            failure_patterns,
        )

        execution_time = (
            (datetime.now() - self.start_time).total_seconds() if self.start_time else 0
        )

        return {
            "summary": {
                "total_tests": total_tests,
                "passed": passed_tests,
                "failed": failed_tests,
                "errors": error_tests,
                "skipped": skipped_tests,
                "success_rate": (
                    (passed_tests / total_tests * 100) if total_tests > 0 else 0
                ),
                "execution_time_seconds": execution_time,
            },
            "performance": {
                "avg_response_time_ms": avg_response_time,
                "min_response_time_ms": min_response_time,
                "max_response_time_ms": max_response_time,
                "slow_endpoints_count": len(slow_endpoints),
            },
            "category_breakdown": category_stats,
            "endpoint_breakdown": endpoint_stats,
            "failure_analysis": {
                "total_failures": len(failures),
                "failure_patterns": failure_patterns,
                "schema_validation_issues": len(schema_issues),
                "common_schema_errors": list(set(schema_issues))[:10],
            },
            "slow_endpoints": [
                {
                    "endpoint": r["endpoint"],
                    "response_time_ms": r["execution_time_ms"],
                    "test_name": r["test_name"],
                }
                for r in slow_endpoints[:10]  # Top 10 slowest
            ],
            "recommendations": recommendations,
            "detailed_results": results,
            "timestamp": datetime.now().isoformat(),
        }

    def _generate_recommendations(
        self,
        total_tests: int,
        passed_tests: int,
        failed_tests: int,
        avg_response_time: float,
        category_stats: Dict[str, Any],
        slow_endpoints: List[Dict[str, Any]],
        failure_patterns: Dict[str, int],
    ) -> List[str]:
        """Generate actionable recommendations based on test results."""
        recommendations = []

        # Success rate recommendations
        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        if success_rate < 90:
            recommendations.append(
                f"🔴 CRITICAL: Success rate is {success_rate:.1f}%. "
                f"Investigate {failed_tests} failing tests immediately."
            )
        elif success_rate < 95:
            recommendations.append(
                f"🟡 WARNING: Success rate is {success_rate:.1f}%. "
                f"Consider investigating {failed_tests} failing tests."
            )
        else:
            recommendations.append(
                f"🟢 GOOD: Success rate is {success_rate:.1f}%. API contracts are stable."
            )

        # Performance recommendations
        if avg_response_time > 1000:
            recommendations.append(
                f"🔴 PERFORMANCE: Average response time is {avg_response_time:.0f}ms. "
                f"Optimize API performance to meet <500ms target."
            )
        elif avg_response_time > 500:
            recommendations.append(
                f"🟡 PERFORMANCE: Average response time is {avg_response_time:.0f}ms. "
                f"Consider optimizing for better user experience."
            )

        if slow_endpoints:
            recommendations.append(
                f"🟡 SLOW ENDPOINTS: {len(slow_endpoints)} endpoints respond slowly (>1s). "
                f"Optimize: {', '.join(set(ep['endpoint'] for ep in slow_endpoints[:3]))}"
            )

        # Category-specific recommendations
        for category, stats in category_stats.items():
            if stats["total"] > 0:
                category_success_rate = (stats["passed"] / stats["total"]) * 100
                if category_success_rate < 90:
                    recommendations.append(
                        f"🔴 CATEGORY: {category} has {category_success_rate:.1f}% success rate. "
                        f"Focus on fixing {stats['failed'] + stats['errors']} issues."
                    )

        # Common failure pattern recommendations
        if failure_patterns:
            top_failure = max(failure_patterns.items(), key=lambda x: x[1])
            if top_failure[1] > 3:
                recommendations.append(
                    f"🔴 PATTERN: '{top_failure[0]}' occurs {top_failure[1]} times. "
                    f"This indicates a systemic issue requiring attention."
                )

        # General recommendations
        if not recommendations:
            recommendations.append(
                "🎉 EXCELLENT: All API contract tests are passing with good performance!"
            )

        return recommendations


async def main():
    """Main entry point for API contract testing."""
    parser = argparse.ArgumentParser(description="FXML4 API Contract Test Runner")

    parser.add_argument("--all", action="store_true", help="Run all contract tests")

    parser.add_argument(
        "--category",
        choices=[
            "auth",
            "trading",
            "market_data",
            "risk",
            "ml",
            "portfolio",
            "user",
            "admin",
            "broker",
        ],
        help="Test specific category",
    )

    parser.add_argument("--endpoint", help="Test specific endpoint path")

    parser.add_argument("--parallel", action="store_true", help="Run tests in parallel")

    parser.add_argument(
        "--max-concurrent",
        type=int,
        default=10,
        help="Maximum concurrent tests (default: 10)",
    )

    parser.add_argument(
        "--output", help="Output file for detailed report (JSON format)"
    )

    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="Base URL for API testing (default: http://localhost:8000)",
    )

    args = parser.parse_args()

    if not (args.all or args.category or args.endpoint):
        print("Error: Must specify --all, --category, or --endpoint")
        parser.print_help()
        return 1

    try:
        tester = ComprehensiveAPIContractTester(args.base_url)

        # Determine what to test
        categories = [args.category] if args.category else None
        endpoints = [args.endpoint] if args.endpoint else None

        # Run tests
        report = await tester.run_all_contract_tests(
            categories=categories,
            endpoints=endpoints,
            parallel=args.parallel,
            max_concurrent=args.max_concurrent,
        )

        # Display summary
        if "error" in report:
            print(f"❌ {report['error']}")
            return 1

        summary = report["summary"]
        performance = report["performance"]

        print(f"\n" + "=" * 60)
        print("API CONTRACT TEST RESULTS")
        print("=" * 60)
        print(f"Total Tests: {summary['total_tests']}")
        print(f"Passed: {summary['passed']}")
        print(f"Failed: {summary['failed']}")
        print(f"Errors: {summary['errors']}")
        print(f"Success Rate: {summary['success_rate']:.1f}%")
        print(f"Execution Time: {summary['execution_time_seconds']:.1f}s")
        print(f"Avg Response Time: {performance['avg_response_time_ms']:.0f}ms")

        print(f"\nCategory Breakdown:")
        for category, stats in report["category_breakdown"].items():
            success_rate = (
                (stats["passed"] / stats["total"]) * 100 if stats["total"] > 0 else 0
            )
            print(
                f"  {category}: {stats['passed']}/{stats['total']} ({success_rate:.1f}%)"
            )

        print(f"\nRecommendations:")
        for rec in report["recommendations"]:
            print(f"  {rec}")

        # Save detailed report if requested
        if args.output:
            with open(args.output, "w") as f:
                json.dump(report, f, indent=2)
            print(f"\nDetailed report saved to: {args.output}")

        # Return appropriate exit code
        return 0 if summary["success_rate"] >= 95 else 1

    except Exception as e:
        print(f"💥 Contract testing failed: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
