"""
Comprehensive API Test Orchestration System

This module orchestrates the complete API testing suite for FXML4, combining:
- Endpoint discovery and cataloging
- Contract validation testing
- Authentication and security testing
- Performance and load testing
- Comprehensive reporting

Test-Driven Development (TDD) approach:
1. Red: Define orchestration expectations and test coordination
2. Green: Implement test execution pipeline and reporting
3. Refactor: Optimize test execution and enhance reporting
"""

import asyncio
import json
import logging
import sys
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pytest

# Import our test frameworks
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tests.api.test_authentication_security import SecurityTestResult, SecurityTestSuite
from tests.api.test_contract_validation import APIContractValidator, ContractTestResult
from tests.api.test_endpoint_discovery import APIEndpointDiscovery, EndpointCategory


class TestPhase(Enum):
    """Phases of comprehensive testing"""

    DISCOVERY = "discovery"
    CONTRACT_VALIDATION = "contract_validation"
    SECURITY_TESTING = "security_testing"
    PERFORMANCE_TESTING = "performance_testing"
    INTEGRATION_TESTING = "integration_testing"


class TestExecutionStatus(Enum):
    """Status of test execution"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class TestPhaseResult:
    """Result of a test phase execution"""

    phase: TestPhase
    status: TestExecutionStatus
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_seconds: float = 0.0
    tests_run: int = 0
    tests_passed: int = 0
    tests_failed: int = 0
    details: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None


@dataclass
class ComprehensiveTestReport:
    """Comprehensive test execution report"""

    execution_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    total_duration_seconds: float = 0.0
    phase_results: List[TestPhaseResult] = field(default_factory=list)
    endpoints_discovered: int = 0
    contracts_validated: int = 0
    security_tests_run: int = 0
    overall_success_rate: float = 0.0
    critical_issues: List[Dict[str, Any]] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)


class APITestOrchestrator:
    """Orchestrates comprehensive API testing across all frameworks"""

    def __init__(
        self,
        api_base_url: str = "http://localhost:8001",
        api_root_path: Optional[Path] = None,
        parallel_execution: bool = False,
    ):
        self.api_base_url = api_base_url.rstrip("/")
        self.api_root_path = (
            api_root_path or Path(__file__).parent.parent.parent / "fxml4" / "api"
        )
        self.parallel_execution = parallel_execution
        self.logger = logging.getLogger(__name__)

        # Test execution configuration
        self.test_config = {
            "discovery": {"enabled": True, "timeout_seconds": 30},
            "contract_validation": {
                "enabled": True,
                "timeout_seconds": 300,
                "max_endpoints": 50,  # Limit for performance
                "safe_endpoints_only": True,
            },
            "security_testing": {
                "enabled": True,
                "timeout_seconds": 600,
                "include_penetration_tests": False,  # Disable aggressive tests by default
            },
            "performance_testing": {
                "enabled": False,  # Can be resource intensive
                "timeout_seconds": 300,
                "concurrent_requests": 10,
                "duration_seconds": 60,
            },
        }

        # Test frameworks
        self.endpoint_discovery = None
        self.contract_validator = None
        self.security_suite = None

        # Results storage
        self.current_report: Optional[ComprehensiveTestReport] = None
        self.execution_history: List[ComprehensiveTestReport] = []

    async def initialize_frameworks(self):
        """Initialize all testing frameworks"""
        try:
            self.logger.info("Initializing API testing frameworks...")

            # Initialize endpoint discovery
            self.endpoint_discovery = APIEndpointDiscovery(self.api_root_path)

            # Initialize contract validator
            self.contract_validator = APIContractValidator(self.api_base_url)

            # Initialize security test suite
            self.security_suite = SecurityTestSuite(self.api_base_url)

            self.logger.info("All testing frameworks initialized successfully")

        except Exception as e:
            self.logger.error(f"Failed to initialize testing frameworks: {e}")
            raise

    async def execute_comprehensive_test_suite(self) -> ComprehensiveTestReport:
        """Execute the complete API testing suite"""
        execution_id = f"test_execution_{int(time.time())}"
        start_time = datetime.utcnow()

        self.current_report = ComprehensiveTestReport(
            execution_id=execution_id, start_time=start_time
        )

        self.logger.info(f"Starting comprehensive API test execution: {execution_id}")

        try:
            await self.initialize_frameworks()

            # Execute test phases in order
            if self.test_config["discovery"]["enabled"]:
                await self._execute_discovery_phase()

            if self.test_config["contract_validation"]["enabled"]:
                await self._execute_contract_validation_phase()

            if self.test_config["security_testing"]["enabled"]:
                await self._execute_security_testing_phase()

            if self.test_config["performance_testing"]["enabled"]:
                await self._execute_performance_testing_phase()

            # Finalize report
            self._finalize_report()

        except Exception as e:
            self.logger.error(f"Test execution failed: {e}")
            self.current_report.critical_issues.append(
                {
                    "type": "execution_failure",
                    "message": str(e),
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )

        finally:
            # Cleanup
            await self._cleanup_frameworks()

        self.current_report.end_time = datetime.utcnow()
        self.current_report.total_duration_seconds = (
            self.current_report.end_time - self.current_report.start_time
        ).total_seconds()

        # Store in execution history
        self.execution_history.append(self.current_report)

        return self.current_report

    async def _execute_discovery_phase(self):
        """Execute endpoint discovery phase"""
        phase_result = TestPhaseResult(
            phase=TestPhase.DISCOVERY,
            status=TestExecutionStatus.RUNNING,
            start_time=datetime.utcnow(),
        )

        try:
            self.logger.info("Phase 1: Discovering API endpoints...")

            # Discover all endpoints
            endpoints = self.endpoint_discovery.discover_all_endpoints()
            summary = self.endpoint_discovery.generate_endpoint_summary()

            phase_result.tests_run = len(endpoints)
            phase_result.tests_passed = len(endpoints)
            phase_result.status = TestExecutionStatus.COMPLETED
            phase_result.details = {
                "endpoints_discovered": len(endpoints),
                "summary": summary,
                "endpoints_by_category": {
                    category.value: len(
                        [ep for ep in endpoints if ep.category == category]
                    )
                    for category in EndpointCategory
                },
            }

            # Store endpoints for later phases
            self.discovered_endpoints = endpoints
            self.current_report.endpoints_discovered = len(endpoints)

            self.logger.info(f"Discovery completed: {len(endpoints)} endpoints found")

        except Exception as e:
            phase_result.status = TestExecutionStatus.FAILED
            phase_result.error_message = str(e)
            self.logger.error(f"Discovery phase failed: {e}")

        finally:
            phase_result.end_time = datetime.utcnow()
            phase_result.duration_seconds = (
                phase_result.end_time - phase_result.start_time
            ).total_seconds()
            self.current_report.phase_results.append(phase_result)

    async def _execute_contract_validation_phase(self):
        """Execute contract validation phase"""
        phase_result = TestPhaseResult(
            phase=TestPhase.CONTRACT_VALIDATION,
            status=TestExecutionStatus.RUNNING,
            start_time=datetime.utcnow(),
        )

        try:
            self.logger.info("Phase 2: Validating API contracts...")

            if not hasattr(self, "discovered_endpoints"):
                raise Exception(
                    "Endpoints must be discovered before contract validation"
                )

            # Filter endpoints for testing
            test_endpoints = self._filter_endpoints_for_testing(
                self.discovered_endpoints,
                max_endpoints=self.test_config["contract_validation"]["max_endpoints"],
                safe_only=self.test_config["contract_validation"][
                    "safe_endpoints_only"
                ],
            )

            # Execute contract validation
            contract_results = await asyncio.wait_for(
                self.contract_validator.validate_all_endpoints(test_endpoints),
                timeout=self.test_config["contract_validation"]["timeout_seconds"],
            )

            # Generate contract report
            contract_report = self.contract_validator.generate_contract_report(
                contract_results
            )

            phase_result.tests_run = len(contract_results)
            phase_result.tests_passed = len([r for r in contract_results if r.passed])
            phase_result.tests_failed = (
                phase_result.tests_run - phase_result.tests_passed
            )
            phase_result.status = TestExecutionStatus.COMPLETED
            phase_result.details = {
                "contract_report": contract_report,
                "failed_contracts": [
                    {
                        "endpoint": result.endpoint,
                        "method": result.method,
                        "violations": len(result.violations),
                    }
                    for result in contract_results
                    if not result.passed
                ],
            }

            self.current_report.contracts_validated = len(contract_results)

            # Extract critical contract issues
            for result in contract_results:
                if not result.passed and len(result.violations) > 0:
                    self.current_report.critical_issues.append(
                        {
                            "type": "contract_violation",
                            "endpoint": result.endpoint,
                            "method": result.method,
                            "violations": len(result.violations),
                            "timestamp": datetime.utcnow().isoformat(),
                        }
                    )

            self.logger.info(
                f"Contract validation completed: {len(contract_results)} endpoints tested"
            )

        except asyncio.TimeoutError:
            phase_result.status = TestExecutionStatus.FAILED
            phase_result.error_message = "Contract validation timed out"
            self.logger.error("Contract validation phase timed out")
        except Exception as e:
            phase_result.status = TestExecutionStatus.FAILED
            phase_result.error_message = str(e)
            self.logger.error(f"Contract validation phase failed: {e}")

        finally:
            phase_result.end_time = datetime.utcnow()
            phase_result.duration_seconds = (
                phase_result.end_time - phase_result.start_time
            ).total_seconds()
            self.current_report.phase_results.append(phase_result)

    async def _execute_security_testing_phase(self):
        """Execute security testing phase"""
        phase_result = TestPhaseResult(
            phase=TestPhase.SECURITY_TESTING,
            status=TestExecutionStatus.RUNNING,
            start_time=datetime.utcnow(),
        )

        try:
            self.logger.info("Phase 3: Running security tests...")

            all_security_results = []

            # Run authentication tests
            auth_results = await asyncio.wait_for(
                self.security_suite.test_authentication_mechanisms(), timeout=120
            )
            all_security_results.extend(auth_results)

            # Run authorization tests
            authz_results = await asyncio.wait_for(
                self.security_suite.test_authorization_controls(), timeout=120
            )
            all_security_results.extend(authz_results)

            # Run injection vulnerability tests (limited scope for safety)
            if self.test_config["security_testing"]["include_penetration_tests"]:
                injection_results = await asyncio.wait_for(
                    self.security_suite.test_injection_vulnerabilities(), timeout=180
                )
                all_security_results.extend(injection_results)

            # Run rate limiting tests
            rate_limit_results = await asyncio.wait_for(
                self.security_suite.test_rate_limiting(), timeout=60
            )
            all_security_results.extend(rate_limit_results)

            # Run security headers tests
            headers_results = await asyncio.wait_for(
                self.security_suite.test_security_headers(), timeout=30
            )
            all_security_results.extend(headers_results)

            # Generate security report
            security_report = await self.security_suite.generate_security_report(
                all_security_results
            )

            phase_result.tests_run = len(all_security_results)
            phase_result.tests_passed = len(
                [r for r in all_security_results if r.passed]
            )
            phase_result.tests_failed = (
                phase_result.tests_run - phase_result.tests_passed
            )
            phase_result.status = TestExecutionStatus.COMPLETED
            phase_result.details = {
                "security_report": security_report,
                "critical_security_findings": security_report.get(
                    "critical_findings", []
                ),
            }

            self.current_report.security_tests_run = len(all_security_results)

            # Extract critical security issues
            for finding in security_report.get("critical_findings", []):
                if finding.get("risk_level") in ["high", "critical"]:
                    self.current_report.critical_issues.append(
                        {
                            "type": "security_vulnerability",
                            "endpoint": finding.get("endpoint"),
                            "method": finding.get("method"),
                            "risk_level": finding.get("risk_level"),
                            "details": finding.get("details"),
                            "timestamp": datetime.utcnow().isoformat(),
                        }
                    )

            # Add security recommendations
            self.current_report.recommendations.extend(
                security_report.get("recommendations", [])
            )

            self.logger.info(
                f"Security testing completed: {len(all_security_results)} tests run"
            )

        except asyncio.TimeoutError:
            phase_result.status = TestExecutionStatus.FAILED
            phase_result.error_message = "Security testing timed out"
            self.logger.error("Security testing phase timed out")
        except Exception as e:
            phase_result.status = TestExecutionStatus.FAILED
            phase_result.error_message = str(e)
            self.logger.error(f"Security testing phase failed: {e}")

        finally:
            phase_result.end_time = datetime.utcnow()
            phase_result.duration_seconds = (
                phase_result.end_time - phase_result.start_time
            ).total_seconds()
            self.current_report.phase_results.append(phase_result)

    async def _execute_performance_testing_phase(self):
        """Execute performance testing phase"""
        phase_result = TestPhaseResult(
            phase=TestPhase.PERFORMANCE_TESTING,
            status=TestExecutionStatus.RUNNING,
            start_time=datetime.utcnow(),
        )

        try:
            self.logger.info("Phase 4: Running performance tests...")

            # Simple performance test - measure response times for key endpoints
            key_endpoints = ["/health", "/", "/trading/status"]
            performance_results = []

            for endpoint in key_endpoints:
                try:
                    # Measure response time
                    start = time.time()
                    response = await self.contract_validator.client.get(
                        f"{self.api_base_url}{endpoint}"
                    )
                    end = time.time()

                    response_time = (end - start) * 1000  # Convert to ms

                    performance_results.append(
                        {
                            "endpoint": endpoint,
                            "response_time_ms": response_time,
                            "status_code": response.status_code,
                            "success": response.status_code < 400,
                        }
                    )

                except Exception as e:
                    performance_results.append(
                        {"endpoint": endpoint, "error": str(e), "success": False}
                    )

            phase_result.tests_run = len(performance_results)
            phase_result.tests_passed = len(
                [r for r in performance_results if r.get("success", False)]
            )
            phase_result.tests_failed = (
                phase_result.tests_run - phase_result.tests_passed
            )
            phase_result.status = TestExecutionStatus.COMPLETED
            phase_result.details = {
                "performance_results": performance_results,
                "average_response_time_ms": sum(
                    r.get("response_time_ms", 0)
                    for r in performance_results
                    if "response_time_ms" in r
                )
                / max(
                    1, len([r for r in performance_results if "response_time_ms" in r])
                ),
            }

            self.logger.info(
                f"Performance testing completed: {len(performance_results)} endpoints tested"
            )

        except Exception as e:
            phase_result.status = TestExecutionStatus.FAILED
            phase_result.error_message = str(e)
            self.logger.error(f"Performance testing phase failed: {e}")

        finally:
            phase_result.end_time = datetime.utcnow()
            phase_result.duration_seconds = (
                phase_result.end_time - phase_result.start_time
            ).total_seconds()
            self.current_report.phase_results.append(phase_result)

    def _filter_endpoints_for_testing(
        self, endpoints: List, max_endpoints: int = 50, safe_only: bool = True
    ) -> List:
        """Filter endpoints for safe testing"""
        if safe_only:
            # Filter out potentially dangerous endpoints
            dangerous_keywords = [
                "delete",
                "remove",
                "destroy",
                "drop",
                "stop",
                "cancel",
                "reset",
            ]
            safe_endpoints = [
                ep
                for ep in endpoints
                if not any(keyword in ep.path.lower() for keyword in dangerous_keywords)
                and ep.method in ["GET", "POST"]  # Avoid PUT/DELETE for safety
            ]
        else:
            safe_endpoints = endpoints

        # Prioritize by category and importance
        priority_categories = [
            EndpointCategory.CORE,
            EndpointCategory.AUTH,
            EndpointCategory.TRADING,
            EndpointCategory.DATA,
            EndpointCategory.MONITORING,
        ]

        prioritized_endpoints = []
        for category in priority_categories:
            category_endpoints = [
                ep for ep in safe_endpoints if ep.category == category
            ]
            prioritized_endpoints.extend(category_endpoints)

        # Add remaining endpoints
        remaining = [ep for ep in safe_endpoints if ep not in prioritized_endpoints]
        prioritized_endpoints.extend(remaining)

        return prioritized_endpoints[:max_endpoints]

    def _finalize_report(self):
        """Finalize the comprehensive test report"""
        if not self.current_report:
            return

        # Calculate overall metrics
        total_tests = sum(
            phase.tests_run for phase in self.current_report.phase_results
        )
        total_passed = sum(
            phase.tests_passed for phase in self.current_report.phase_results
        )

        self.current_report.overall_success_rate = (
            (total_passed / total_tests * 100) if total_tests > 0 else 0
        )

        # Generate summary
        self.current_report.summary = {
            "total_phases": len(self.current_report.phase_results),
            "completed_phases": len(
                [
                    p
                    for p in self.current_report.phase_results
                    if p.status == TestExecutionStatus.COMPLETED
                ]
            ),
            "failed_phases": len(
                [
                    p
                    for p in self.current_report.phase_results
                    if p.status == TestExecutionStatus.FAILED
                ]
            ),
            "total_tests": total_tests,
            "total_passed": total_passed,
            "total_failed": total_tests - total_passed,
            "success_rate": self.current_report.overall_success_rate,
            "critical_issues_count": len(self.current_report.critical_issues),
            "recommendations_count": len(self.current_report.recommendations),
        }

        # Add general recommendations
        if self.current_report.overall_success_rate < 90:
            self.current_report.recommendations.insert(
                0,
                "Overall test success rate is below 90%. Review failed tests and address issues.",
            )

        if len(self.current_report.critical_issues) > 0:
            self.current_report.recommendations.insert(
                0,
                f"Found {len(self.current_report.critical_issues)} critical issues. "
                "Address these immediately before deployment.",
            )

    async def _cleanup_frameworks(self):
        """Cleanup all testing frameworks"""
        try:
            if self.contract_validator:
                await self.contract_validator.close()
            if self.security_suite:
                await self.security_suite.close()
        except Exception as e:
            self.logger.error(f"Error during framework cleanup: {e}")

    def generate_html_report(self, report: ComprehensiveTestReport) -> str:
        """Generate HTML report"""
        html_template = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>FXML4 API Test Report - {report.execution_id}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ background: #f0f0f0; padding: 20px; border-radius: 5px; }}
                .section {{ margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }}
                .success {{ color: green; }}
                .failure {{ color: red; }}
                .warning {{ color: orange; }}
                .critical {{ background: #ffe6e6; padding: 10px; border-left: 4px solid red; }}
                table {{ width: 100%; border-collapse: collapse; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>FXML4 API Comprehensive Test Report</h1>
                <p><strong>Execution ID:</strong> {report.execution_id}</p>
                <p><strong>Start Time:</strong> {report.start_time}</p>
                <p><strong>Duration:</strong> {report.total_duration_seconds:.2f} seconds</p>
                <p><strong>Success Rate:</strong>
                    <span class="{'success' if report.overall_success_rate > 80 else 'failure'}">
                        {report.overall_success_rate:.1f}%
                    </span>
                </p>
            </div>

            <div class="section">
                <h2>Executive Summary</h2>
                <ul>
                    <li><strong>Endpoints Discovered:</strong> {report.endpoints_discovered}</li>
                    <li><strong>Contracts Validated:</strong> {report.contracts_validated}</li>
                    <li><strong>Security Tests Run:</strong> {report.security_tests_run}</li>
                    <li><strong>Critical Issues:</strong>
                        <span class="{'critical' if len(report.critical_issues) > 0 else 'success'}">
                            {len(report.critical_issues)}
                        </span>
                    </li>
                </ul>
            </div>

            <div class="section">
                <h2>Phase Results</h2>
                <table>
                    <tr>
                        <th>Phase</th>
                        <th>Status</th>
                        <th>Tests Run</th>
                        <th>Passed</th>
                        <th>Failed</th>
                        <th>Duration (s)</th>
                    </tr>
        """

        for phase in report.phase_results:
            status_class = (
                "success"
                if phase.status == TestExecutionStatus.COMPLETED
                else "failure"
            )
            html_template += f"""
                    <tr>
                        <td>{phase.phase.value}</td>
                        <td class="{status_class}">{phase.status.value}</td>
                        <td>{phase.tests_run}</td>
                        <td class="success">{phase.tests_passed}</td>
                        <td class="failure">{phase.tests_failed}</td>
                        <td>{phase.duration_seconds:.2f}</td>
                    </tr>
            """

        html_template += """
                </table>
            </div>
        """

        if report.critical_issues:
            html_template += """
            <div class="section">
                <h2>Critical Issues</h2>
            """
            for issue in report.critical_issues:
                html_template += f"""
                <div class="critical">
                    <strong>{issue.get('type', 'Unknown')}:</strong> {issue.get('details', 'No details available')}
                    <br><small>Endpoint: {issue.get('endpoint', 'N/A')} ({issue.get('method', 'N/A')})</small>
                </div>
                """
            html_template += "</div>"

        if report.recommendations:
            html_template += """
            <div class="section">
                <h2>Recommendations</h2>
                <ul>
            """
            for rec in report.recommendations:
                html_template += f"<li>{rec}</li>"
            html_template += """
                </ul>
            </div>
            """

        html_template += """
        </body>
        </html>
        """

        return html_template

    def save_report(self, report: ComprehensiveTestReport, output_dir: Path = None):
        """Save report in multiple formats"""
        output_dir = output_dir or Path("test_reports")
        output_dir.mkdir(exist_ok=True)

        timestamp = report.start_time.strftime("%Y%m%d_%H%M%S")

        # Save JSON report
        json_path = output_dir / f"api_test_report_{timestamp}.json"
        with open(json_path, "w") as f:
            json.dump(self._report_to_dict(report), f, indent=2, default=str)

        # Save HTML report
        html_path = output_dir / f"api_test_report_{timestamp}.html"
        with open(html_path, "w") as f:
            f.write(self.generate_html_report(report))

        self.logger.info(f"Reports saved: {json_path}, {html_path}")

        return json_path, html_path

    def _report_to_dict(self, report: ComprehensiveTestReport) -> Dict[str, Any]:
        """Convert report to dictionary for JSON serialization"""
        return {
            "execution_id": report.execution_id,
            "start_time": report.start_time.isoformat(),
            "end_time": report.end_time.isoformat() if report.end_time else None,
            "total_duration_seconds": report.total_duration_seconds,
            "endpoints_discovered": report.endpoints_discovered,
            "contracts_validated": report.contracts_validated,
            "security_tests_run": report.security_tests_run,
            "overall_success_rate": report.overall_success_rate,
            "critical_issues": report.critical_issues,
            "recommendations": report.recommendations,
            "summary": report.summary,
            "phase_results": [
                {
                    "phase": phase.phase.value,
                    "status": phase.status.value,
                    "start_time": phase.start_time.isoformat(),
                    "end_time": phase.end_time.isoformat() if phase.end_time else None,
                    "duration_seconds": phase.duration_seconds,
                    "tests_run": phase.tests_run,
                    "tests_passed": phase.tests_passed,
                    "tests_failed": phase.tests_failed,
                    "error_message": phase.error_message,
                }
                for phase in report.phase_results
            ],
        }


@pytest.fixture
def test_orchestrator():
    """Fixture providing test orchestrator"""
    return APITestOrchestrator()


class TestOrchestrationFramework:
    """Test suite for the orchestration framework"""

    @pytest.mark.asyncio
    async def test_orchestrator_initialization(self, test_orchestrator):
        """Test orchestrator initializes correctly"""
        # Red: Define orchestrator expectations
        assert test_orchestrator.api_base_url == "http://localhost:8001"
        assert test_orchestrator.api_root_path is not None
        assert isinstance(test_orchestrator.test_config, dict)
        assert "discovery" in test_orchestrator.test_config
        assert "contract_validation" in test_orchestrator.test_config
        assert "security_testing" in test_orchestrator.test_config

    @pytest.mark.asyncio
    async def test_framework_initialization(self, test_orchestrator):
        """Test that frameworks initialize correctly"""
        # Red: Define framework initialization expectations

        # Green: Initialize frameworks
        await test_orchestrator.initialize_frameworks()

        # Verify frameworks are initialized
        assert test_orchestrator.endpoint_discovery is not None
        assert test_orchestrator.contract_validator is not None
        assert test_orchestrator.security_suite is not None

        # Cleanup
        await test_orchestrator._cleanup_frameworks()

    def test_report_generation(self, test_orchestrator):
        """Test report generation functionality"""
        # Red: Define report generation expectations

        # Create sample report
        sample_report = ComprehensiveTestReport(
            execution_id="test_execution",
            start_time=datetime.utcnow(),
            endpoints_discovered=10,
            contracts_validated=8,
            security_tests_run=15,
            overall_success_rate=85.0,
        )

        # Green: Test HTML report generation
        html_report = test_orchestrator.generate_html_report(sample_report)

        # Verify HTML contains expected content
        assert "FXML4 API Comprehensive Test Report" in html_report
        assert "test_execution" in html_report
        assert "85.0%" in html_report
        assert "Endpoints Discovered" in html_report

    def test_endpoint_filtering(self, test_orchestrator):
        """Test endpoint filtering for safe testing"""
        # Red: Define filtering expectations
        from tests.api.test_endpoint_discovery import EndpointCategory, EndpointContract

        # Create sample endpoints including dangerous ones
        sample_endpoints = [
            EndpointContract(
                "/health", "GET", EndpointCategory.MONITORING, "health_check", False
            ),
            EndpointContract(
                "/users/delete", "DELETE", EndpointCategory.USERS, "delete_user", True
            ),
            EndpointContract("/data", "POST", EndpointCategory.DATA, "get_data", True),
            EndpointContract(
                "/trading/stop", "POST", EndpointCategory.TRADING, "stop_trading", True
            ),
        ]

        # Green: Filter endpoints
        safe_endpoints = test_orchestrator._filter_endpoints_for_testing(
            sample_endpoints, max_endpoints=10, safe_only=True
        )

        # Verify dangerous endpoints are filtered out
        safe_paths = [ep.path for ep in safe_endpoints]
        assert "/health" in safe_paths
        assert "/data" in safe_paths
        assert "/users/delete" not in safe_paths
        assert "/trading/stop" not in safe_paths


if __name__ == "__main__":
    # Direct execution for comprehensive testing
    async def main():
        print("=" * 60)
        print("FXML4 API COMPREHENSIVE TEST ORCHESTRATION")
        print("=" * 60)

        # Initialize orchestrator
        orchestrator = APITestOrchestrator()

        # Configure for demonstration (limited scope)
        orchestrator.test_config.update(
            {
                "discovery": {"enabled": True, "timeout_seconds": 30},
                "contract_validation": {
                    "enabled": True,
                    "timeout_seconds": 120,
                    "max_endpoints": 10,
                    "safe_endpoints_only": True,
                },
                "security_testing": {
                    "enabled": True,
                    "timeout_seconds": 180,
                    "include_penetration_tests": False,
                },
                "performance_testing": {"enabled": True, "timeout_seconds": 60},
            }
        )

        try:
            # Execute comprehensive test suite
            report = await orchestrator.execute_comprehensive_test_suite()

            # Display results
            print(f"\nTest Execution Completed: {report.execution_id}")
            print(f"Total Duration: {report.total_duration_seconds:.2f} seconds")
            print(f"Overall Success Rate: {report.overall_success_rate:.1f}%")
            print(f"Endpoints Discovered: {report.endpoints_discovered}")
            print(f"Contracts Validated: {report.contracts_validated}")
            print(f"Security Tests Run: {report.security_tests_run}")
            print(f"Critical Issues: {len(report.critical_issues)}")

            print(f"\nPhase Results:")
            for phase in report.phase_results:
                status_symbol = (
                    "✓" if phase.status == TestExecutionStatus.COMPLETED else "✗"
                )
                print(
                    f"  {status_symbol} {phase.phase.value}: {phase.tests_passed}/{phase.tests_run} passed ({phase.duration_seconds:.1f}s)"
                )
                if phase.error_message:
                    print(f"    Error: {phase.error_message}")

            if report.critical_issues:
                print(f"\nCritical Issues:")
                for issue in report.critical_issues[:3]:  # Show top 3
                    print(
                        f"  - {issue.get('type', 'Unknown')}: {issue.get('details', 'No details')}"
                    )

            if report.recommendations:
                print(f"\nTop Recommendations:")
                for rec in report.recommendations[:3]:  # Show top 3
                    print(f"  - {rec}")

            # Save reports
            try:
                json_path, html_path = orchestrator.save_report(report)
                print(f"\nReports saved:")
                print(f"  JSON: {json_path}")
                print(f"  HTML: {html_path}")
            except Exception as e:
                print(f"  Warning: Could not save reports: {e}")

        except Exception as e:
            print(f"\nTest execution failed: {e}")
            traceback.print_exc()

        print("\n" + "=" * 60)
        print("Test orchestration completed!")

    # Run the main function
    asyncio.run(main())
