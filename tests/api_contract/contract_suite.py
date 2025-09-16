"""
API Contract Test Suite
======================

High-level API contract testing suite that orchestrates comprehensive
contract validation including schema, performance, security, and compatibility testing.
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from .compatibility_checker import APIEvolutionTracker, CompatibilityChecker
from .contract_models import (
    APIContract,
    ContractTestResult,
    ContractTestSuite,
    EndpointContract,
    PerformanceContract,
    SecurityContract,
    ValidationResult,
)
from .contract_tester import ContractTester, ContractTesterConfig
from .performance_validator import PerformanceBenchmark, PerformanceValidator
from .schema_validator import SchemaValidator
from .security_validator import SecurityAudit, SecurityValidator
from .utils import (
    create_test_suite_from_contract,
    discover_api_endpoints,
    generate_test_data,
    load_contract_from_openapi,
)

logger = logging.getLogger(__name__)


@dataclass
class ContractTestConfig:
    """Configuration for contract test suite."""

    # API connection
    base_url: str
    timeout_seconds: int = 30
    authentication_token: Optional[str] = None

    # Test execution
    run_schema_tests: bool = True
    run_performance_tests: bool = True
    run_security_tests: bool = True
    run_compatibility_tests: bool = True

    # Performance testing
    performance_samples: int = 10
    concurrent_requests: int = 5

    # Security testing
    security_audit_level: str = "standard"  # minimal, standard, comprehensive

    # Output configuration
    generate_reports: bool = True
    report_format: str = "json"  # json, html, markdown
    output_directory: Optional[str] = None

    # Test data
    use_generated_data: bool = True
    custom_test_data: Dict[str, Any] = None


class APIContractSuite:
    """
    Comprehensive API contract testing suite.

    Orchestrates all aspects of API contract testing including schema validation,
    performance testing, security auditing, and backward compatibility checking.
    """

    def __init__(self, config: ContractTestConfig):
        """Initialize contract test suite."""
        self.config = config

        # Initialize validators
        self.schema_validator = SchemaValidator()
        self.performance_validator = PerformanceValidator()
        self.security_validator = SecurityValidator()
        self.compatibility_checker = CompatibilityChecker()
        self.evolution_tracker = APIEvolutionTracker()
        self.security_audit = SecurityAudit()
        self.performance_benchmark = PerformanceBenchmark()

        # Test results
        self.test_results = []
        self.performance_baselines = {}

        logger.info(f"Initialized API Contract Suite for {config.base_url}")

    def test_api_contract(
        self, contract: APIContract, baseline_contract: Optional[APIContract] = None
    ) -> ContractTestSuite:
        """
        Test complete API contract.

        Args:
            contract: API contract to test
            baseline_contract: Previous contract version for compatibility testing

        Returns:
            Complete test suite results
        """
        logger.info(
            f"Starting comprehensive contract testing for {contract.title} v{contract.version}"
        )

        suite = ContractTestSuite(
            name=f"{contract.title} v{contract.version} Contract Test Suite"
        )

        # Configure contract tester
        tester_config = ContractTesterConfig(
            base_url=self.config.base_url,
            timeout_seconds=self.config.timeout_seconds,
            authentication_token=self.config.authentication_token,
            test_performance=self.config.run_performance_tests,
            test_security=self.config.run_security_tests,
            performance_samples=self.config.performance_samples,
            concurrent_requests=self.config.concurrent_requests,
        )

        tester = ContractTester(tester_config)

        try:
            # Test each endpoint
            for endpoint in contract.endpoints:
                logger.info(f"Testing endpoint: {endpoint.get_full_path()}")

                # Generate test data
                test_data = self._get_test_data_for_endpoint(endpoint)

                # Run contract tests
                if self.config.run_schema_tests:
                    result = tester.test_endpoint_contract(
                        endpoint, request_data=test_data
                    )
                    suite.add_result(result)

                # Run performance tests
                if self.config.run_performance_tests:
                    perf_results = self._run_performance_tests(endpoint, tester)
                    suite.results.extend(perf_results)

                # Run security tests
                if self.config.run_security_tests:
                    security_results = self._run_security_tests(endpoint, test_data)
                    suite.results.extend(security_results)

            # Run compatibility tests
            if self.config.run_compatibility_tests and baseline_contract:
                compatibility_results = self._run_compatibility_tests(
                    baseline_contract, contract
                )
                suite.results.extend(compatibility_results)

            # Run comprehensive security audit
            if (
                self.config.run_security_tests
                and self.config.security_audit_level != "minimal"
            ):
                audit_results = self._run_security_audit(contract)
                suite.results.extend(audit_results)

            # Generate performance benchmarks
            if self.config.run_performance_tests:
                self._establish_performance_baselines(contract, tester)

        finally:
            tester.cleanup()

        suite.completed_at = time.time()

        # Generate reports if requested
        if self.config.generate_reports:
            self._generate_reports(suite, contract)

        logger.info(
            f"Contract testing completed: {suite.passed_tests}/{suite.total_tests} passed "
            f"({suite.success_rate:.1f}%)"
        )

        return suite

    def test_api_from_openapi_spec(
        self, spec_url_or_path: str, baseline_spec_url_or_path: Optional[str] = None
    ) -> ContractTestSuite:
        """
        Test API from OpenAPI specification.

        Args:
            spec_url_or_path: URL or path to OpenAPI specification
            baseline_spec_url_or_path: URL or path to baseline spec for compatibility testing

        Returns:
            Test suite results
        """
        try:
            # Load main contract
            contract = load_contract_from_openapi(spec_url_or_path)
            contract.base_url = self.config.base_url  # Override with test URL

            # Load baseline contract if provided
            baseline_contract = None
            if baseline_spec_url_or_path:
                baseline_contract = load_contract_from_openapi(
                    baseline_spec_url_or_path
                )
                baseline_contract.base_url = self.config.base_url

            return self.test_api_contract(contract, baseline_contract)

        except Exception as e:
            logger.error(f"Failed to load OpenAPI specification: {e}")
            raise

    def discover_and_test_api(self) -> ContractTestSuite:
        """
        Discover API endpoints and test contracts.

        Returns:
            Test suite results
        """
        logger.info(f"Discovering API endpoints at {self.config.base_url}")

        # Discover endpoints
        endpoints = discover_api_endpoints(self.config.base_url)

        if not endpoints:
            logger.warning("No API endpoints discovered")
            return ContractTestSuite(name="Discovery Test - No Endpoints Found")

        logger.info(f"Discovered {len(endpoints)} endpoints")

        # Create basic contract from discovered endpoints
        contract = APIContract(
            title="Auto-Discovered API",
            version="discovered",
            base_url=self.config.base_url,
            endpoints=[
                EndpointContract(
                    path=endpoint,
                    method="GET",  # Default to GET for discovery
                    summary=f"Auto-discovered endpoint: {endpoint}",
                )
                for endpoint in endpoints
            ],
        )

        return self.test_api_contract(contract)

    def _get_test_data_for_endpoint(self, endpoint: EndpointContract) -> Dict[str, Any]:
        """Get test data for endpoint."""
        if (
            self.config.custom_test_data
            and endpoint.path in self.config.custom_test_data
        ):
            return self.config.custom_test_data[endpoint.path]

        if self.config.use_generated_data and endpoint.request_schema:
            return generate_test_data(endpoint.request_schema)

        return {}

    def _run_performance_tests(
        self, endpoint: EndpointContract, tester: ContractTester
    ) -> List[ContractTestResult]:
        """Run performance tests for endpoint."""
        results = []

        try:
            # Create request function for performance testing
            test_data = self._get_test_data_for_endpoint(endpoint)

            def make_request():
                result = tester.test_endpoint_contract(endpoint, request_data=test_data)
                return result.passed, result.execution_time_ms

            # Measure baseline performance
            baseline_metrics = self.performance_benchmark.establish_baseline(
                endpoint.get_full_path(),
                make_request,
                iterations=self.config.performance_samples,
            )

            # Store baseline
            self.performance_baselines[endpoint.get_full_path()] = baseline_metrics

            # Validate against performance contract if available
            if endpoint.performance_contract:
                validation_result = (
                    self.performance_validator.validate_performance_contract(
                        endpoint.performance_contract, baseline_metrics
                    )
                )

                result = ContractTestResult(
                    endpoint=endpoint.path,
                    method=endpoint.method.value,
                    status="passed" if validation_result.is_valid else "failed",
                    schema_validation=ValidationResult(),
                    performance_validation=validation_result,
                    security_validation=ValidationResult(),
                    execution_time_ms=baseline_metrics.avg_response_time_ms,
                )
                results.append(result)

        except Exception as e:
            logger.error(
                f"Performance testing failed for {endpoint.get_full_path()}: {e}"
            )

            result = ContractTestResult(
                endpoint=endpoint.path,
                method=endpoint.method.value,
                status="failed",
                schema_validation=ValidationResult(),
                performance_validation=ValidationResult(
                    is_valid=False, errors=[f"Performance test failed: {str(e)}"]
                ),
                security_validation=ValidationResult(),
                execution_time_ms=0,
            )
            results.append(result)

        return results

    def _run_security_tests(
        self, endpoint: EndpointContract, test_data: Dict[str, Any]
    ) -> List[ContractTestResult]:
        """Run security tests for endpoint."""
        results = []

        if not endpoint.security_contract:
            return results

        try:
            # Validate request security
            request_result = self.security_validator.validate_request_security(
                endpoint.security_contract,
                headers={"Authorization": f"Bearer {self.config.authentication_token}"},
                request_data=test_data,
                url=f"{self.config.base_url}{endpoint.path}",
            )

            # Create mock response for response security validation
            mock_response_data = (
                generate_test_data(list(endpoint.response_schemas.values())[0])
                if endpoint.response_schemas
                else {}
            )

            response_result = self.security_validator.validate_response_security(
                endpoint.security_contract,
                headers={"Content-Type": "application/json"},
                response_data=mock_response_data,
            )

            # Combine results
            combined_result = request_result.merge(response_result)

            result = ContractTestResult(
                endpoint=endpoint.path,
                method=endpoint.method.value,
                status="passed" if combined_result.is_valid else "failed",
                schema_validation=ValidationResult(),
                performance_validation=ValidationResult(),
                security_validation=combined_result,
                execution_time_ms=0,
            )
            results.append(result)

        except Exception as e:
            logger.error(f"Security testing failed for {endpoint.get_full_path()}: {e}")

            result = ContractTestResult(
                endpoint=endpoint.path,
                method=endpoint.method.value,
                status="failed",
                schema_validation=ValidationResult(),
                performance_validation=ValidationResult(),
                security_validation=ValidationResult(
                    is_valid=False, errors=[f"Security test failed: {str(e)}"]
                ),
                execution_time_ms=0,
            )
            results.append(result)

        return results

    def _run_compatibility_tests(
        self, old_contract: APIContract, new_contract: APIContract
    ) -> List[ContractTestResult]:
        """Run compatibility tests between contract versions."""
        results = []

        try:
            compatibility_report = self.compatibility_checker.check_compatibility(
                old_contract, new_contract
            )

            # Create result based on compatibility
            result = ContractTestResult(
                endpoint="compatibility",
                method="ALL",
                status="passed" if compatibility_report.is_compatible else "failed",
                schema_validation=ValidationResult(
                    is_valid=compatibility_report.is_compatible,
                    errors=[
                        f"Breaking change: {change.description}"
                        for change in compatibility_report.breaking_changes
                    ],
                    warnings=[
                        f"Change: {change.description}"
                        for change in compatibility_report.changes
                        if change not in compatibility_report.breaking_changes
                    ],
                    details=compatibility_report.to_dict(),
                ),
                performance_validation=ValidationResult(),
                security_validation=ValidationResult(),
                execution_time_ms=0,
            )
            results.append(result)

            # Track evolution
            self.evolution_tracker.add_version(old_contract)
            self.evolution_tracker.add_version(new_contract)

        except Exception as e:
            logger.error(f"Compatibility testing failed: {e}")

            result = ContractTestResult(
                endpoint="compatibility",
                method="ALL",
                status="failed",
                schema_validation=ValidationResult(
                    is_valid=False, errors=[f"Compatibility test failed: {str(e)}"]
                ),
                performance_validation=ValidationResult(),
                security_validation=ValidationResult(),
                execution_time_ms=0,
            )
            results.append(result)

        return results

    def _run_security_audit(self, contract: APIContract) -> List[ContractTestResult]:
        """Run comprehensive security audit."""
        results = []

        try:
            # Prepare endpoint data for audit
            endpoints_data = [
                {
                    "path": endpoint.path,
                    "method": endpoint.method.value,
                    "security_contract": endpoint.security_contract,
                }
                for endpoint in contract.endpoints
            ]

            audit_result = self.security_audit.audit_api_security(
                endpoints_data, contract.base_url
            )

            result = ContractTestResult(
                endpoint="security_audit",
                method="ALL",
                status="passed" if audit_result.is_valid else "failed",
                schema_validation=ValidationResult(),
                performance_validation=ValidationResult(),
                security_validation=audit_result,
                execution_time_ms=0,
            )
            results.append(result)

        except Exception as e:
            logger.error(f"Security audit failed: {e}")

            result = ContractTestResult(
                endpoint="security_audit",
                method="ALL",
                status="failed",
                schema_validation=ValidationResult(),
                performance_validation=ValidationResult(),
                security_validation=ValidationResult(
                    is_valid=False, errors=[f"Security audit failed: {str(e)}"]
                ),
                execution_time_ms=0,
            )
            results.append(result)

        return results

    def _establish_performance_baselines(
        self, contract: APIContract, tester: ContractTester
    ) -> None:
        """Establish performance baselines for all endpoints."""
        logger.info("Establishing performance baselines")

        for endpoint in contract.endpoints:
            if endpoint.get_full_path() not in self.performance_baselines:
                try:
                    test_data = self._get_test_data_for_endpoint(endpoint)

                    def make_request():
                        result = tester.test_endpoint_contract(
                            endpoint, request_data=test_data
                        )
                        return result.passed, result.execution_time_ms

                    baseline = self.performance_benchmark.establish_baseline(
                        endpoint.get_full_path(), make_request
                    )
                    self.performance_baselines[endpoint.get_full_path()] = baseline

                except Exception as e:
                    logger.error(
                        f"Failed to establish baseline for {endpoint.get_full_path()}: {e}"
                    )

    def _generate_reports(
        self, suite: ContractTestSuite, contract: APIContract
    ) -> None:
        """Generate test reports."""
        if not self.config.output_directory:
            return

        output_dir = Path(self.config.output_directory)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate summary report
        summary = self._generate_summary_report(suite, contract)

        if self.config.report_format == "json":
            report_file = output_dir / f"contract_test_report_{contract.version}.json"
            with open(report_file, "w") as f:
                json.dump(summary, f, indent=2, default=str)

        elif self.config.report_format == "html":
            report_file = output_dir / f"contract_test_report_{contract.version}.html"
            html_content = self._generate_html_report(summary)
            with open(report_file, "w") as f:
                f.write(html_content)

        elif self.config.report_format == "markdown":
            report_file = output_dir / f"contract_test_report_{contract.version}.md"
            md_content = self._generate_markdown_report(summary)
            with open(report_file, "w") as f:
                f.write(md_content)

        logger.info(f"Generated test report: {report_file}")

    def _generate_summary_report(
        self, suite: ContractTestSuite, contract: APIContract
    ) -> Dict[str, Any]:
        """Generate comprehensive summary report."""
        return {
            "test_suite": suite.generate_summary(),
            "api_contract": {
                "title": contract.title,
                "version": contract.version,
                "base_url": contract.base_url,
                "total_endpoints": len(contract.endpoints),
            },
            "test_configuration": {
                "schema_tests_enabled": self.config.run_schema_tests,
                "performance_tests_enabled": self.config.run_performance_tests,
                "security_tests_enabled": self.config.run_security_tests,
                "compatibility_tests_enabled": self.config.run_compatibility_tests,
            },
            "performance_baselines": {
                endpoint: metrics.to_dict()
                for endpoint, metrics in self.performance_baselines.items()
            },
            "failed_tests": [
                {
                    "endpoint": result.endpoint,
                    "method": result.method,
                    "errors": result.overall_result.errors,
                    "warnings": result.overall_result.warnings,
                }
                for result in suite.get_failed_results()
            ],
        }

    def _generate_html_report(self, summary: Dict[str, Any]) -> str:
        """Generate HTML report."""
        # This would generate a comprehensive HTML report
        # For now, return a simple template
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>API Contract Test Report</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; }}
                .header {{ color: #333; border-bottom: 2px solid #ccc; }}
                .summary {{ background: #f9f9f9; padding: 20px; margin: 20px 0; }}
                .success {{ color: green; }}
                .failure {{ color: red; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>API Contract Test Report</h1>
                <h2>{summary['api_contract']['title']} v{summary['api_contract']['version']}</h2>
            </div>

            <div class="summary">
                <h3>Test Summary</h3>
                <p>Total Tests: {summary['test_suite']['total_tests']}</p>
                <p class="success">Passed: {summary['test_suite']['passed_tests']}</p>
                <p class="failure">Failed: {summary['test_suite']['failed_tests']}</p>
                <p>Success Rate: {summary['test_suite']['success_rate']:.1f}%</p>
            </div>

            <div class="details">
                <h3>Test Details</h3>
                <pre>{json.dumps(summary, indent=2)}</pre>
            </div>
        </body>
        </html>
        """

    def _generate_markdown_report(self, summary: Dict[str, Any]) -> str:
        """Generate Markdown report."""
        return f"""
# API Contract Test Report

## {summary['api_contract']['title']} v{summary['api_contract']['version']}

### Test Summary

- **Total Tests**: {summary['test_suite']['total_tests']}
- **Passed**: {summary['test_suite']['passed_tests']}
- **Failed**: {summary['test_suite']['failed_tests']}
- **Success Rate**: {summary['test_suite']['success_rate']:.1f}%
- **Execution Time**: {summary['test_suite']['execution_time_ms']:.2f}ms

### Configuration

- Schema Tests: {'✅' if summary['test_configuration']['schema_tests_enabled'] else '❌'}
- Performance Tests: {'✅' if summary['test_configuration']['performance_tests_enabled'] else '❌'}
- Security Tests: {'✅' if summary['test_configuration']['security_tests_enabled'] else '❌'}
- Compatibility Tests: {'✅' if summary['test_configuration']['compatibility_tests_enabled'] else '❌'}

### Failed Tests

{chr(10).join([f"- **{test['method']} {test['endpoint']}**: {', '.join(test['errors'])}" for test in summary['failed_tests']])}

### Performance Baselines

{chr(10).join([f"- **{endpoint}**: {metrics['avg_response_time_ms']:.2f}ms avg" for endpoint, metrics in summary['performance_baselines'].items()])}
        """
