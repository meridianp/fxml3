"""
Core Contract Tester Implementation
===================================

Main contract testing engine that orchestrates validation of API contracts
including schema validation, performance testing, security verification,
and compatibility checking.
"""

import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urljoin, urlparse

import httpx
from pydantic import BaseModel

from .contract_models import (
    APIContract,
    ContractTestResult,
    ContractTestSuite,
    EndpointContract,
    HTTPMethod,
    PerformanceContract,
    SecurityContract,
    ValidationResult,
)
from .performance_validator import PerformanceValidator
from .schema_validator import SchemaValidator
from .security_validator import SecurityValidator
from .utils import discover_api_endpoints, generate_test_data

logger = logging.getLogger(__name__)


class ContractTesterConfig(BaseModel):
    """Configuration for contract tester."""

    base_url: str
    timeout_seconds: int = 30
    max_retries: int = 3
    concurrent_requests: int = 5
    verify_ssl: bool = True
    follow_redirects: bool = True
    default_headers: Dict[str, str] = {}
    authentication_token: Optional[str] = None

    # Testing options
    test_performance: bool = True
    test_security: bool = True
    test_compatibility: bool = True
    generate_test_data: bool = True
    strict_validation: bool = True

    # Performance testing
    performance_samples: int = 5
    performance_percentile: float = 95.0

    # Logging
    log_requests: bool = False
    log_responses: bool = False
    log_level: str = "INFO"


class ContractTester:
    """
    Main contract testing engine.

    Validates API contracts by testing endpoints against their specifications
    including schema validation, performance requirements, and security contracts.
    """

    def __init__(self, config: ContractTesterConfig):
        """Initialize contract tester."""
        self.config = config
        self.client = None
        self.schema_validator = SchemaValidator()
        self.performance_validator = PerformanceValidator()
        self.security_validator = SecurityValidator()

        # Setup logging
        logging.basicConfig(level=getattr(logging, config.log_level))

    async def __aenter__(self):
        """Async context manager entry."""
        self.client = httpx.AsyncClient(
            timeout=self.config.timeout_seconds,
            verify=self.config.verify_ssl,
            follow_redirects=self.config.follow_redirects,
            headers=self.config.default_headers,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.client:
            await self.client.aclose()

    def _get_client(self) -> httpx.Client:
        """Get synchronous HTTP client."""
        if not hasattr(self, "_sync_client") or self._sync_client is None:
            self._sync_client = httpx.Client(
                timeout=self.config.timeout_seconds,
                verify=self.config.verify_ssl,
                follow_redirects=self.config.follow_redirects,
                headers=self.config.default_headers,
            )
        return self._sync_client

    def _prepare_headers(
        self, additional_headers: Dict[str, str] = None
    ) -> Dict[str, str]:
        """Prepare request headers."""
        headers = self.config.default_headers.copy()

        if self.config.authentication_token:
            headers["Authorization"] = f"Bearer {self.config.authentication_token}"

        if additional_headers:
            headers.update(additional_headers)

        return headers

    def _build_url(
        self, endpoint: EndpointContract, path_params: Dict[str, Any] = None
    ) -> str:
        """Build complete URL for endpoint."""
        path = endpoint.path

        # Replace path parameters
        if path_params:
            for param, value in path_params.items():
                path = path.replace(f"{{{param}}}", str(value))

        return urljoin(self.config.base_url, path.lstrip("/"))

    def test_endpoint_contract(
        self,
        endpoint: EndpointContract,
        request_data: Dict[str, Any] = None,
        path_params: Dict[str, Any] = None,
        query_params: Dict[str, Any] = None,
        headers: Dict[str, str] = None,
    ) -> ContractTestResult:
        """Test single endpoint contract."""
        start_time = time.time()

        # Generate test data if not provided
        if request_data is None and self.config.generate_test_data:
            request_data = self._generate_request_data(endpoint)

        # Build request
        url = self._build_url(endpoint, path_params)
        request_headers = self._prepare_headers(headers)

        try:
            # Make request
            client = self._get_client()

            if self.config.log_requests:
                logger.info(f"Testing {endpoint.method.value} {url}")
                logger.debug(f"Headers: {request_headers}")
                logger.debug(f"Data: {request_data}")

            response = client.request(
                method=endpoint.method.value,
                url=url,
                json=(
                    request_data
                    if request_data
                    and endpoint.method
                    in [HTTPMethod.POST, HTTPMethod.PUT, HTTPMethod.PATCH]
                    else None
                ),
                params=query_params,
                headers=request_headers,
            )

            if self.config.log_responses:
                logger.debug(
                    f"Response: {response.status_code} - {response.text[:500]}..."
                )

            execution_time = (time.time() - start_time) * 1000

            # Validate contract
            return self._validate_response_contract(
                endpoint=endpoint,
                response=response,
                request_data=request_data or {},
                execution_time_ms=execution_time,
            )

        except Exception as e:
            logger.error(f"Error testing endpoint {endpoint.get_full_path()}: {e}")
            execution_time = (time.time() - start_time) * 1000

            return ContractTestResult(
                endpoint=endpoint.path,
                method=endpoint.method.value,
                status="failed",
                schema_validation=ValidationResult(
                    is_valid=False, errors=[f"Request failed: {str(e)}"]
                ),
                performance_validation=ValidationResult(),
                security_validation=ValidationResult(),
                execution_time_ms=execution_time,
            )

    def _generate_request_data(self, endpoint: EndpointContract) -> Dict[str, Any]:
        """Generate test request data for endpoint."""
        if not endpoint.request_schema:
            return {}

        return generate_test_data(endpoint.request_schema)

    def _validate_response_contract(
        self,
        endpoint: EndpointContract,
        response: httpx.Response,
        request_data: Dict[str, Any],
        execution_time_ms: float,
    ) -> ContractTestResult:
        """Validate response against endpoint contract."""

        # Schema validation
        schema_result = self._validate_response_schema(endpoint, response)

        # Performance validation
        performance_result = ValidationResult()
        if self.config.test_performance and endpoint.performance_contract:
            performance_result = self.performance_validator.validate_response_time(
                endpoint.performance_contract, execution_time_ms
            )

        # Security validation
        security_result = ValidationResult()
        if self.config.test_security and endpoint.security_contract:
            security_result = self.security_validator.validate_response_security(
                endpoint.security_contract,
                response.headers,
                (
                    response.json()
                    if response.headers.get("content-type", "").startswith(
                        "application/json"
                    )
                    else {}
                ),
            )

        # Determine overall status
        overall_valid = (
            schema_result.is_valid
            and performance_result.is_valid
            and security_result.is_valid
        )
        has_warnings = (
            schema_result.warnings
            or performance_result.warnings
            or security_result.warnings
        )

        if overall_valid:
            status = "warning" if has_warnings else "passed"
        else:
            status = "failed"

        try:
            response_data = (
                response.json()
                if response.headers.get("content-type", "").startswith(
                    "application/json"
                )
                else {}
            )
        except:
            response_data = {"raw_content": response.text[:1000]}

        return ContractTestResult(
            endpoint=endpoint.path,
            method=endpoint.method.value,
            status=status,
            schema_validation=schema_result,
            performance_validation=performance_result,
            security_validation=security_result,
            request_data=request_data,
            response_data=response_data,
            execution_time_ms=execution_time_ms,
        )

    def _validate_response_schema(
        self, endpoint: EndpointContract, response: httpx.Response
    ) -> ValidationResult:
        """Validate response schema."""
        result = ValidationResult()

        # Check status code
        if (
            response.status_code not in endpoint.success_status_codes
            and response.status_code not in endpoint.error_status_codes
        ):
            result.add_error(f"Unexpected status code: {response.status_code}")

        # Check content type
        content_type = response.headers.get("content-type", "")
        expected_content_type = endpoint.response_content_type.value
        if not content_type.startswith(expected_content_type.split(";")[0]):
            result.add_warning(
                f"Unexpected content type: {content_type}, expected: {expected_content_type}"
            )

        # Validate response schema if available
        response_schema = endpoint.response_schemas.get(response.status_code)
        if response_schema:
            try:
                response_data = response.json()
                schema_result = response_schema.validate_data(response_data)
                result = result.merge(schema_result)
            except json.JSONDecodeError:
                result.add_error("Response is not valid JSON")
            except Exception as e:
                result.add_error(f"Error validating response schema: {e}")

        return result

    def test_api_contract(self, contract: APIContract) -> ContractTestSuite:
        """Test complete API contract."""
        suite = ContractTestSuite(
            name=f"{contract.title} v{contract.version} Contract Test"
        )

        logger.info(f"Testing API contract: {contract.title} v{contract.version}")
        logger.info(f"Base URL: {contract.base_url}")
        logger.info(f"Endpoints to test: {len(contract.endpoints)}")

        for endpoint in contract.endpoints:
            logger.info(f"Testing endpoint: {endpoint.get_full_path()}")

            try:
                result = self.test_endpoint_contract(endpoint)
                suite.add_result(result)

                if result.failed:
                    logger.warning(
                        f"Endpoint {endpoint.get_full_path()} failed contract test"
                    )
                    for error in result.overall_result.errors:
                        logger.warning(f"  Error: {error}")
                else:
                    logger.info(
                        f"Endpoint {endpoint.get_full_path()} passed contract test"
                    )

            except Exception as e:
                logger.error(
                    f"Exception testing endpoint {endpoint.get_full_path()}: {e}"
                )

                # Add failed result
                failed_result = ContractTestResult(
                    endpoint=endpoint.path,
                    method=endpoint.method.value,
                    status="failed",
                    schema_validation=ValidationResult(
                        is_valid=False, errors=[f"Test execution failed: {str(e)}"]
                    ),
                    performance_validation=ValidationResult(),
                    security_validation=ValidationResult(),
                    execution_time_ms=0,
                )
                suite.add_result(failed_result)

        suite.completed_at = time.time()

        logger.info(
            f"Contract testing completed: {suite.passed_tests}/{suite.total_tests} passed ({suite.success_rate:.1f}%)"
        )

        return suite

    def discover_and_test_api(
        self, api_spec_url: Optional[str] = None
    ) -> ContractTestSuite:
        """Discover API endpoints and test contracts."""

        if api_spec_url:
            # Load from OpenAPI/Swagger spec
            contract = self._load_contract_from_spec(api_spec_url)
        else:
            # Auto-discover endpoints
            endpoints = discover_api_endpoints(self.config.base_url)
            contract = self._build_contract_from_endpoints(endpoints)

        return self.test_api_contract(contract)

    def _load_contract_from_spec(self, spec_url: str) -> APIContract:
        """Load contract from OpenAPI/Swagger specification."""
        # This would parse OpenAPI/Swagger spec and convert to APIContract
        # Implementation depends on specific spec format

        # For now, return a basic contract
        # In real implementation, this would parse the spec file
        return APIContract(
            title="Auto-discovered API",
            version="1.0",
            base_url=self.config.base_url,
            endpoints=[],
        )

    def _build_contract_from_endpoints(self, endpoints: List[str]) -> APIContract:
        """Build basic contract from discovered endpoints."""
        endpoint_contracts = []

        for endpoint_path in endpoints:
            # Create basic endpoint contracts
            # In real implementation, this would introspect endpoints for schemas
            endpoint_contract = EndpointContract(
                path=endpoint_path,
                method=HTTPMethod.GET,  # Default to GET
                summary=f"Auto-discovered endpoint: {endpoint_path}",
            )
            endpoint_contracts.append(endpoint_contract)

        return APIContract(
            title="Auto-discovered API",
            version="1.0",
            base_url=self.config.base_url,
            endpoints=endpoint_contracts,
        )

    async def test_endpoint_performance(
        self,
        endpoint: EndpointContract,
        concurrent_requests: int = None,
        total_requests: int = None,
    ) -> ValidationResult:
        """Test endpoint performance under load."""
        if not self.config.test_performance:
            return ValidationResult()

        concurrent_requests = concurrent_requests or self.config.concurrent_requests
        total_requests = total_requests or self.config.performance_samples

        logger.info(
            f"Performance testing {endpoint.get_full_path()} - {total_requests} requests, {concurrent_requests} concurrent"
        )

        # Generate test data
        request_data = self._generate_request_data(endpoint)
        url = self._build_url(endpoint)
        headers = self._prepare_headers()

        async def make_request():
            """Make single request and measure time."""
            start_time = time.time()
            try:
                if not self.client:
                    raise ValueError(
                        "Client not initialized - use async context manager"
                    )

                response = await self.client.request(
                    method=endpoint.method.value,
                    url=url,
                    json=(
                        request_data
                        if request_data
                        and endpoint.method
                        in [HTTPMethod.POST, HTTPMethod.PUT, HTTPMethod.PATCH]
                        else None
                    ),
                    headers=headers,
                )
                execution_time = (time.time() - start_time) * 1000

                return {
                    "execution_time_ms": execution_time,
                    "status_code": response.status_code,
                    "success": response.status_code < 400,
                }
            except Exception as e:
                execution_time = (time.time() - start_time) * 1000
                return {
                    "execution_time_ms": execution_time,
                    "status_code": 0,
                    "success": False,
                    "error": str(e),
                }

        # Execute concurrent requests
        semaphore = asyncio.Semaphore(concurrent_requests)

        async def bounded_request():
            async with semaphore:
                return await make_request()

        tasks = [bounded_request() for _ in range(total_requests)]
        results = await asyncio.gather(*tasks)

        # Analyze results
        response_times = [r["execution_time_ms"] for r in results]
        successful_requests = [r for r in results if r["success"]]
        failed_requests = [r for r in results if not r["success"]]

        # Calculate statistics
        avg_response_time = sum(response_times) / len(response_times)
        percentile_response_time = sorted(response_times)[
            int(len(response_times) * self.config.performance_percentile / 100)
        ]
        success_rate = len(successful_requests) / len(results) * 100

        # Validate against performance contract
        validation_result = ValidationResult()

        if endpoint.performance_contract:
            if (
                percentile_response_time
                > endpoint.performance_contract.max_response_time_ms
            ):
                validation_result.add_error(
                    f"Performance contract violation: {self.config.performance_percentile}th percentile response time "
                    f"({percentile_response_time:.2f}ms) exceeds maximum ({endpoint.performance_contract.max_response_time_ms}ms)"
                )

        if success_rate < 95.0:
            validation_result.add_error(
                f"Low success rate: {success_rate:.1f}% (expected >= 95%)"
            )

        validation_result.details = {
            "total_requests": total_requests,
            "successful_requests": len(successful_requests),
            "failed_requests": len(failed_requests),
            "success_rate_percent": success_rate,
            "avg_response_time_ms": avg_response_time,
            f"p{self.config.performance_percentile}_response_time_ms": percentile_response_time,
            "min_response_time_ms": min(response_times),
            "max_response_time_ms": max(response_times),
        }

        logger.info(
            f"Performance test completed: {success_rate:.1f}% success rate, "
            f"avg: {avg_response_time:.2f}ms, p{self.config.performance_percentile}: {percentile_response_time:.2f}ms"
        )

        return validation_result

    def cleanup(self):
        """Cleanup resources."""
        if hasattr(self, "_sync_client") and self._sync_client:
            self._sync_client.close()
