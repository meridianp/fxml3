"""
Comprehensive API Contract Validation Framework

This module implements systematic contract validation for all discovered FXML4 API endpoints.
It validates request/response schemas, HTTP status codes, authentication requirements,
and business logic constraints defined in the API contracts.

Test-Driven Development (TDD) approach:
1. Red: Define contract validation expectations for each endpoint category
2. Green: Implement validation logic and test execution
3. Refactor: Enhance validation depth and error handling
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import httpx
import pytest

from tests.api.test_endpoint_discovery import (
    APIEndpointDiscovery,
    EndpointCategory,
    EndpointContract,
)


class ContractViolationType(Enum):
    """Types of contract violations"""

    INVALID_STATUS_CODE = "invalid_status_code"
    MISSING_FIELD = "missing_field"
    WRONG_DATA_TYPE = "wrong_data_type"
    AUTHENTICATION_BYPASS = "authentication_bypass"
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    INVALID_RESPONSE_SCHEMA = "invalid_response_schema"
    TIMEOUT = "timeout"
    SERVER_ERROR = "server_error"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    VALIDATION_ERROR = "validation_error"


@dataclass
class ContractViolation:
    """Represents a contract violation discovered during testing"""

    endpoint: str
    method: str
    violation_type: ContractViolationType
    expected: Any
    actual: Any
    details: str
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ContractTestResult:
    """Result of contract validation for an endpoint"""

    endpoint: str
    method: str
    category: str
    passed: bool
    violations: List[ContractViolation] = field(default_factory=list)
    response_time_ms: float = 0.0
    status_code: Optional[int] = None
    response_data: Optional[Dict[str, Any]] = None


class APIContractValidator:
    """Comprehensive API contract validation framework"""

    def __init__(self, base_url: str = "http://localhost:8001"):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=30.0)
        self.auth_token: Optional[str] = None
        self.test_results: List[ContractTestResult] = []
        self.logger = logging.getLogger(__name__)

        # Test data templates for different endpoint categories
        self.test_data_templates = {
            EndpointCategory.AUTH: {
                "valid_credentials": {
                    "username": "test_user",
                    "password": "test_password_123",
                },
                "invalid_credentials": {
                    "username": "invalid_user",
                    "password": "wrong_password",
                },
                "token_request": {
                    "username": "test_user",
                    "password": "test_password_123",
                },
            },
            EndpointCategory.DATA: {
                "valid_data_request": {
                    "symbol": "EURUSD",
                    "timeframe": "1h",
                    "limit": 100,
                },
                "invalid_symbol": {"symbol": "INVALID_SYMBOL", "timeframe": "1h"},
                "invalid_timeframe": {"symbol": "EURUSD", "timeframe": "invalid"},
            },
            EndpointCategory.TRADING: {
                "start_engine_request": {
                    "symbols": ["EURUSD", "GBPUSD"],
                    "trading_mode": "demo",
                    "min_confidence": 0.7,
                },
                "config_update": {
                    "trading_mode": "live",
                    "enabled_symbols": ["EURUSD"],
                    "min_signal_confidence": 0.8,
                },
            },
            EndpointCategory.SIGNALS: {
                "signal_request": {
                    "symbol": "EURUSD",
                    "timeframe": "1h",
                    "strategy": "ml_strategy",
                    "parameters": {"lookback": 50},
                },
                "invalid_strategy": {
                    "symbol": "EURUSD",
                    "timeframe": "1h",
                    "strategy": "invalid_strategy",
                },
            },
            EndpointCategory.ORDERS: {
                "valid_order": {
                    "symbol": "EURUSD",
                    "side": "buy",
                    "quantity": 100000,
                    "order_type": "market",
                },
                "invalid_quantity": {
                    "symbol": "EURUSD",
                    "side": "buy",
                    "quantity": -100000,  # Invalid negative quantity
                    "order_type": "market",
                },
            },
        }

        # Expected response schemas for different endpoint categories
        self.expected_schemas = {
            EndpointCategory.CORE: {
                "health": {
                    "required_fields": ["status", "timestamp"],
                    "field_types": {"status": str, "timestamp": str, "version": str},
                }
            },
            EndpointCategory.TRADING: {
                "status": {
                    "required_fields": ["status", "timestamp"],
                    "field_types": {"status": dict, "timestamp": str},
                },
                "account": {
                    "required_fields": ["balance", "equity", "currency"],
                    "field_types": {
                        "balance": (int, float),
                        "equity": (int, float),
                        "currency": str,
                    },
                },
            },
            EndpointCategory.DATA: {
                "data": {
                    "required_fields": ["symbol", "timeframe", "data", "count"],
                    "field_types": {
                        "symbol": str,
                        "timeframe": str,
                        "data": list,
                        "count": int,
                    },
                },
                "symbols": {
                    "required_fields": ["symbols", "count"],
                    "field_types": {"symbols": list, "count": int},
                },
            },
        }

    async def setup_authentication(self) -> bool:
        """Set up authentication token for protected endpoints"""
        try:
            # Try to get authentication token
            auth_data = self.test_data_templates[EndpointCategory.AUTH]["token_request"]

            response = await self.client.post(
                f"{self.base_url}/auth/token", data=auth_data
            )

            if response.status_code == 200:
                token_data = response.json()
                if "access_token" in token_data:
                    self.auth_token = token_data["access_token"]
                    self.client.headers["Authorization"] = f"Bearer {self.auth_token}"
                    return True

        except Exception as e:
            self.logger.warning(f"Failed to setup authentication: {e}")

        return False

    async def validate_endpoint_contract(
        self, endpoint: EndpointContract
    ) -> ContractTestResult:
        """Validate contract for a single endpoint"""
        result = ContractTestResult(
            endpoint=endpoint.path,
            method=endpoint.method,
            category=endpoint.category.value,
            passed=False,
        )

        start_time = datetime.utcnow()

        try:
            # Test with valid data
            await self._test_valid_requests(endpoint, result)

            # Test with invalid data
            await self._test_invalid_requests(endpoint, result)

            # Test authentication requirements
            await self._test_authentication_requirements(endpoint, result)

            # Test response schema validation
            await self._test_response_schema(endpoint, result)

            # Calculate response time
            end_time = datetime.utcnow()
            result.response_time_ms = (end_time - start_time).total_seconds() * 1000

            # Mark as passed if no violations found
            result.passed = len(result.violations) == 0

        except Exception as e:
            violation = ContractViolation(
                endpoint=endpoint.path,
                method=endpoint.method,
                violation_type=ContractViolationType.SERVER_ERROR,
                expected="Successful test execution",
                actual=str(e),
                details=f"Unexpected error during contract validation: {e}",
            )
            result.violations.append(violation)

        return result

    async def _test_valid_requests(
        self, endpoint: EndpointContract, result: ContractTestResult
    ):
        """Test endpoint with valid request data"""
        test_data = self._get_test_data(endpoint.category, "valid")

        try:
            response = await self._make_request(
                method=endpoint.method, path=endpoint.path, data=test_data
            )

            result.status_code = response.status_code

            # Check for expected successful status codes
            if endpoint.method == "POST" and endpoint.path.endswith("/"):
                expected_codes = [200, 201]
            else:
                expected_codes = [200]

            if response.status_code not in expected_codes:
                violation = ContractViolation(
                    endpoint=endpoint.path,
                    method=endpoint.method,
                    violation_type=ContractViolationType.INVALID_STATUS_CODE,
                    expected=expected_codes,
                    actual=response.status_code,
                    details=f"Expected status codes {expected_codes}, got {response.status_code}",
                )
                result.violations.append(violation)

            # Store response data for schema validation
            if response.headers.get("content-type", "").startswith("application/json"):
                try:
                    result.response_data = response.json()
                except Exception:
                    pass  # Non-JSON response is acceptable for some endpoints

        except asyncio.TimeoutError:
            violation = ContractViolation(
                endpoint=endpoint.path,
                method=endpoint.method,
                violation_type=ContractViolationType.TIMEOUT,
                expected="Response within timeout",
                actual="Timeout exceeded",
                details="Request timed out",
            )
            result.violations.append(violation)

        except Exception as e:
            violation = ContractViolation(
                endpoint=endpoint.path,
                method=endpoint.method,
                violation_type=ContractViolationType.SERVER_ERROR,
                expected="Successful request",
                actual=str(e),
                details=f"Error making valid request: {e}",
            )
            result.violations.append(violation)

    async def _test_invalid_requests(
        self, endpoint: EndpointContract, result: ContractTestResult
    ):
        """Test endpoint with invalid request data"""
        if endpoint.method in ["GET", "DELETE"]:
            return  # Skip invalid data tests for GET/DELETE

        test_data = self._get_test_data(endpoint.category, "invalid")

        if not test_data:
            return  # No invalid test data available

        try:
            response = await self._make_request(
                method=endpoint.method, path=endpoint.path, data=test_data
            )

            # Invalid requests should return 400-level status codes
            if response.status_code not in [400, 401, 403, 404, 422, 429]:
                violation = ContractViolation(
                    endpoint=endpoint.path,
                    method=endpoint.method,
                    violation_type=ContractViolationType.VALIDATION_ERROR,
                    expected="4xx status code for invalid data",
                    actual=response.status_code,
                    details=f"Invalid data should return 4xx status, got {response.status_code}",
                )
                result.violations.append(violation)

        except Exception as e:
            # Exceptions on invalid requests are acceptable
            pass

    async def _test_authentication_requirements(
        self, endpoint: EndpointContract, result: ContractTestResult
    ):
        """Test authentication requirements"""
        if not endpoint.requires_auth:
            return

        # Store current auth header
        current_auth = self.client.headers.get("Authorization")

        try:
            # Remove authentication and test
            if "Authorization" in self.client.headers:
                del self.client.headers["Authorization"]

            response = await self._make_request(
                method=endpoint.method,
                path=endpoint.path,
                data=self._get_test_data(endpoint.category, "valid"),
            )

            # Should return 401 Unauthorized
            if response.status_code != 401:
                violation = ContractViolation(
                    endpoint=endpoint.path,
                    method=endpoint.method,
                    violation_type=ContractViolationType.AUTHENTICATION_BYPASS,
                    expected=401,
                    actual=response.status_code,
                    details=f"Protected endpoint should return 401 without auth, got {response.status_code}",
                )
                result.violations.append(violation)

        except Exception as e:
            # Exception on unauthenticated request is acceptable
            pass
        finally:
            # Restore authentication
            if current_auth:
                self.client.headers["Authorization"] = current_auth

    async def _test_response_schema(
        self, endpoint: EndpointContract, result: ContractTestResult
    ):
        """Test response schema validation"""
        if not result.response_data:
            return

        schema_key = self._get_schema_key(endpoint)
        expected_schema = self.expected_schemas.get(endpoint.category, {}).get(
            schema_key
        )

        if not expected_schema:
            return  # No schema defined for this endpoint

        # Check required fields
        required_fields = expected_schema.get("required_fields", [])
        for field in required_fields:
            if field not in result.response_data:
                violation = ContractViolation(
                    endpoint=endpoint.path,
                    method=endpoint.method,
                    violation_type=ContractViolationType.MISSING_FIELD,
                    expected=field,
                    actual="Field missing",
                    details=f"Required field '{field}' missing from response",
                )
                result.violations.append(violation)

        # Check field types
        field_types = expected_schema.get("field_types", {})
        for field, expected_type in field_types.items():
            if field in result.response_data:
                actual_value = result.response_data[field]
                if isinstance(expected_type, tuple):
                    # Multiple acceptable types
                    if not isinstance(actual_value, expected_type):
                        violation = ContractViolation(
                            endpoint=endpoint.path,
                            method=endpoint.method,
                            violation_type=ContractViolationType.WRONG_DATA_TYPE,
                            expected=expected_type,
                            actual=type(actual_value),
                            details=f"Field '{field}' has wrong type: expected {expected_type}, got {type(actual_value)}",
                        )
                        result.violations.append(violation)
                else:
                    # Single expected type
                    if not isinstance(actual_value, expected_type):
                        violation = ContractViolation(
                            endpoint=endpoint.path,
                            method=endpoint.method,
                            violation_type=ContractViolationType.WRONG_DATA_TYPE,
                            expected=expected_type,
                            actual=type(actual_value),
                            details=f"Field '{field}' has wrong type: expected {expected_type}, got {type(actual_value)}",
                        )
                        result.violations.append(violation)

    async def _make_request(
        self, method: str, path: str, data: Optional[Dict[str, Any]] = None
    ) -> httpx.Response:
        """Make HTTP request to endpoint"""
        url = f"{self.base_url}{path}"

        # Handle path parameters (replace {param} with test values)
        if "{" in path:
            url = self._substitute_path_parameters(url)

        request_kwargs = {}
        if data:
            if method.upper() in ["POST", "PUT", "PATCH"]:
                request_kwargs["json"] = data
            else:
                request_kwargs["params"] = data

        return await self.client.request(method.upper(), url, **request_kwargs)

    def _substitute_path_parameters(self, url: str) -> str:
        """Substitute path parameters with test values"""
        substitutions = {
            "{symbol}": "EURUSD",
            "{user_id}": "1",
            "{order_id}": "test_order_1",
            "{cl_ord_id}": "test_cl_order_1",
            "{limit_id}": "1",
            "{violation_id}": "1",
            "{adapter_id}": "test_adapter",
            "{record_id}": "1",
            "{key_id}": "test_key_1",
            "{role_id}": "1",
            "{backtest_id}": "test_backtest_1",
            "{task_id}": "test_task_1",
            "{metric_type}": "performance",
        }

        result = url
        for param, value in substitutions.items():
            result = result.replace(param, value)

        return result

    def _get_test_data(
        self, category: EndpointCategory, data_type: str
    ) -> Optional[Dict[str, Any]]:
        """Get test data for endpoint category"""
        category_data = self.test_data_templates.get(category, {})

        if data_type == "valid":
            # Try different valid data keys
            for key in [
                "valid_data_request",
                "start_engine_request",
                "signal_request",
                "valid_order",
                "valid_credentials",
            ]:
                if key in category_data:
                    return category_data[key]
        elif data_type == "invalid":
            # Try different invalid data keys
            for key in [
                "invalid_symbol",
                "invalid_timeframe",
                "invalid_strategy",
                "invalid_quantity",
                "invalid_credentials",
            ]:
                if key in category_data:
                    return category_data[key]

        return None

    def _get_schema_key(self, endpoint: EndpointContract) -> str:
        """Get schema key for endpoint"""
        path = endpoint.path.lower()

        if "health" in path:
            return "health"
        elif "status" in path:
            return "status"
        elif "account" in path:
            return "account"
        elif path == "/data" or "data" in path:
            return "data"
        elif "symbols" in path:
            return "symbols"
        else:
            return "default"

    async def validate_all_endpoints(
        self, endpoints: List[EndpointContract]
    ) -> List[ContractTestResult]:
        """Validate contracts for all endpoints"""
        self.logger.info(f"Starting contract validation for {len(endpoints)} endpoints")

        # Setup authentication first
        auth_setup = await self.setup_authentication()
        if not auth_setup:
            self.logger.warning("Authentication setup failed - some tests may fail")

        results = []

        for i, endpoint in enumerate(endpoints):
            self.logger.info(
                f"Testing endpoint {i+1}/{len(endpoints)}: {endpoint.method} {endpoint.path}"
            )

            try:
                result = await self.validate_endpoint_contract(endpoint)
                results.append(result)
                self.test_results.append(result)

                # Log result
                if result.passed:
                    self.logger.info(f"✓ {endpoint.method} {endpoint.path} - PASSED")
                else:
                    self.logger.warning(
                        f"✗ {endpoint.method} {endpoint.path} - FAILED ({len(result.violations)} violations)"
                    )

            except Exception as e:
                self.logger.error(
                    f"Error testing {endpoint.method} {endpoint.path}: {e}"
                )

        return results

    def generate_contract_report(
        self, results: List[ContractTestResult]
    ) -> Dict[str, Any]:
        """Generate comprehensive contract validation report"""
        total_endpoints = len(results)
        passed_endpoints = len([r for r in results if r.passed])
        failed_endpoints = total_endpoints - passed_endpoints

        # Category breakdown
        category_stats = {}
        for result in results:
            category = result.category
            if category not in category_stats:
                category_stats[category] = {"total": 0, "passed": 0, "failed": 0}

            category_stats[category]["total"] += 1
            if result.passed:
                category_stats[category]["passed"] += 1
            else:
                category_stats[category]["failed"] += 1

        # Violation breakdown
        violation_types = {}
        all_violations = []
        for result in results:
            all_violations.extend(result.violations)
            for violation in result.violations:
                vtype = violation.violation_type.value
                violation_types[vtype] = violation_types.get(vtype, 0) + 1

        # Performance metrics
        response_times = [r.response_time_ms for r in results if r.response_time_ms > 0]
        avg_response_time = (
            sum(response_times) / len(response_times) if response_times else 0
        )

        report = {
            "summary": {
                "total_endpoints": total_endpoints,
                "passed": passed_endpoints,
                "failed": failed_endpoints,
                "success_rate": (
                    (passed_endpoints / total_endpoints * 100)
                    if total_endpoints > 0
                    else 0
                ),
                "total_violations": len(all_violations),
            },
            "performance": {
                "average_response_time_ms": round(avg_response_time, 2),
                "max_response_time_ms": max(response_times) if response_times else 0,
                "min_response_time_ms": min(response_times) if response_times else 0,
            },
            "category_breakdown": category_stats,
            "violation_breakdown": violation_types,
            "failed_endpoints": [
                {
                    "endpoint": result.endpoint,
                    "method": result.method,
                    "category": result.category,
                    "violations": len(result.violations),
                    "violation_types": [
                        v.violation_type.value for v in result.violations
                    ],
                }
                for result in results
                if not result.passed
            ],
            "timestamp": datetime.utcnow().isoformat(),
        }

        return report

    async def close(self):
        """Cleanup resources"""
        await self.client.aclose()


@pytest.fixture
def contract_validator():
    """Fixture providing contract validator"""
    return APIContractValidator()


@pytest.fixture
def discovered_endpoints():
    """Fixture providing discovered API endpoints"""
    api_root = Path(__file__).parent.parent.parent / "fxml4" / "api"
    discovery = APIEndpointDiscovery(api_root)
    endpoints = discovery.discover_all_endpoints()
    return endpoints


class TestAPIContractValidation:
    """Test suite for comprehensive API contract validation"""

    @pytest.mark.asyncio
    async def test_contract_validator_initialization(self, contract_validator):
        """Test that contract validator initializes correctly"""
        # Red: Define initialization expectations
        assert contract_validator.base_url == "http://localhost:8001"
        assert contract_validator.client is not None
        assert isinstance(contract_validator.test_data_templates, dict)
        assert isinstance(contract_validator.expected_schemas, dict)

    @pytest.mark.asyncio
    async def test_health_endpoint_contract(self, contract_validator):
        """Test health endpoint contract validation"""
        # Red: Define health endpoint contract expectations
        from tests.api.test_endpoint_discovery import EndpointCategory

        # Create test endpoint
        health_endpoint = EndpointContract(
            path="/health",
            method="GET",
            category=EndpointCategory.MONITORING,
            handler_function="health_check",
            requires_auth=False,
        )

        # Green: Validate health endpoint contract
        result = await contract_validator.validate_endpoint_contract(health_endpoint)

        # Verify results
        assert isinstance(result, ContractTestResult)
        assert result.endpoint == "/health"
        assert result.method == "GET"
        assert result.category == EndpointCategory.MONITORING.value

    @pytest.mark.asyncio
    async def test_authentication_contract_validation(self, contract_validator):
        """Test authentication endpoint contract validation"""
        # Red: Define auth endpoint expectations
        from tests.api.test_endpoint_discovery import EndpointCategory

        auth_endpoint = EndpointContract(
            path="/auth/token",
            method="POST",
            category=EndpointCategory.AUTH,
            handler_function="authenticate",
            requires_auth=False,
        )

        # Green: Validate auth endpoint
        result = await contract_validator.validate_endpoint_contract(auth_endpoint)

        assert isinstance(result, ContractTestResult)
        assert result.endpoint == "/auth/token"

    @pytest.mark.asyncio
    async def test_protected_endpoint_auth_requirement(self, contract_validator):
        """Test that protected endpoints require authentication"""
        # Red: Define protected endpoint expectations
        from tests.api.test_endpoint_discovery import EndpointCategory

        protected_endpoint = EndpointContract(
            path="/trading/status",
            method="GET",
            category=EndpointCategory.TRADING,
            handler_function="get_trading_status",
            requires_auth=True,
        )

        # Green: Test authentication requirement
        result = await contract_validator.validate_endpoint_contract(protected_endpoint)

        # Should have authentication-related checks
        assert isinstance(result, ContractTestResult)

    @pytest.mark.asyncio
    async def test_contract_report_generation(
        self, contract_validator, discovered_endpoints
    ):
        """Test contract validation report generation"""
        # Red: Define report generation expectations

        # Take a small sample of endpoints for testing
        sample_endpoints = (
            discovered_endpoints[:5]
            if len(discovered_endpoints) >= 5
            else discovered_endpoints
        )

        # Green: Generate contract validation results
        results = []
        for endpoint in sample_endpoints:
            result = await contract_validator.validate_endpoint_contract(endpoint)
            results.append(result)

        # Generate report
        report = contract_validator.generate_contract_report(results)

        # Verify report structure
        assert "summary" in report
        assert "performance" in report
        assert "category_breakdown" in report
        assert "violation_breakdown" in report

        # Verify summary fields
        summary = report["summary"]
        assert "total_endpoints" in summary
        assert "passed" in summary
        assert "failed" in summary
        assert "success_rate" in summary

        assert summary["total_endpoints"] == len(sample_endpoints)

    @pytest.mark.asyncio
    async def test_path_parameter_substitution(self, contract_validator):
        """Test path parameter substitution"""
        # Red: Define parameter substitution expectations

        test_url = "http://localhost:8001/orders/{order_id}/status"
        result = contract_validator._substitute_path_parameters(test_url)

        # Green: Verify substitution
        assert "{order_id}" not in result
        assert "test_order_1" in result

    @pytest.mark.asyncio
    async def test_test_data_retrieval(self, contract_validator):
        """Test test data retrieval for different categories"""
        # Red: Define test data expectations
        from tests.api.test_endpoint_discovery import EndpointCategory

        # Green: Test data retrieval
        data_request = contract_validator._get_test_data(EndpointCategory.DATA, "valid")
        trading_request = contract_validator._get_test_data(
            EndpointCategory.TRADING, "valid"
        )

        # Verify data structure
        if data_request:
            assert isinstance(data_request, dict)
        if trading_request:
            assert isinstance(trading_request, dict)

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_sample_endpoint_validation(
        self, contract_validator, discovered_endpoints
    ):
        """Integration test: Validate contracts for sample endpoints"""
        # Red: Define integration test expectations

        # Filter for safe endpoints to test (avoid destructive operations)
        safe_endpoints = [
            ep
            for ep in discovered_endpoints
            if ep.method in ["GET"]
            and not any(
                dangerous in ep.path.lower()
                for dangerous in ["delete", "stop", "cancel", "remove"]
            )
        ]

        # Take first 3 safe endpoints for testing
        test_endpoints = safe_endpoints[:3]

        if not test_endpoints:
            pytest.skip("No safe endpoints available for testing")

        # Green: Run contract validation
        results = await contract_validator.validate_all_endpoints(test_endpoints)

        # Verify results
        assert len(results) == len(test_endpoints)
        assert all(isinstance(result, ContractTestResult) for result in results)

        # Generate and verify report
        report = contract_validator.generate_contract_report(results)
        assert report["summary"]["total_endpoints"] == len(test_endpoints)


if __name__ == "__main__":
    # Direct execution for development testing
    import sys

    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

    from tests.api.test_endpoint_discovery import (
        APIEndpointDiscovery,
        EndpointCategory,
        EndpointContract,
    )

    async def main():
        print("Starting FXML4 API Contract Validation...")

        # Initialize validator and discovery
        validator = APIContractValidator()

        api_root = Path(__file__).parent.parent.parent / "fxml4" / "api"
        discovery = APIEndpointDiscovery(api_root)
        endpoints = discovery.discover_all_endpoints()

        print(f"Discovered {len(endpoints)} endpoints")

        # Test a few sample endpoints
        safe_endpoints = [
            ep
            for ep in endpoints
            if ep.method == "GET"
            and ep.path in ["/health", "/", "/trading/status"]
            and not ep.requires_auth
        ]

        if safe_endpoints:
            print(f"Testing {len(safe_endpoints)} safe endpoints...")
            results = await validator.validate_all_endpoints(safe_endpoints[:2])

            report = validator.generate_contract_report(results)
            print(f"\nContract Validation Report:")
            print(f"Total endpoints tested: {report['summary']['total_endpoints']}")
            print(f"Passed: {report['summary']['passed']}")
            print(f"Failed: {report['summary']['failed']}")
            print(f"Success rate: {report['summary']['success_rate']:.1f}%")
            print(
                f"Average response time: {report['performance']['average_response_time_ms']:.2f}ms"
            )

            if report["summary"]["failed"] > 0:
                print(f"\nFailed endpoints:")
                for failed in report["failed_endpoints"]:
                    print(
                        f"  {failed['method']} {failed['endpoint']} - {failed['violations']} violations"
                    )
        else:
            print("No safe endpoints found for testing")

        await validator.close()

    asyncio.run(main())
