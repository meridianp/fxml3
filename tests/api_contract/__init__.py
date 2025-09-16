"""
API Contract Testing Framework for FXML4
========================================

Comprehensive API contract testing framework that validates:
- Request/response schemas and data types
- HTTP status codes and error handling
- API endpoint consistency and versioning
- Authentication and authorization contracts
- Performance SLA compliance
- Data integrity and business rule validation

This framework ensures that API contracts remain stable across deployments
and that breaking changes are detected early in the development cycle.

Key Features:
- Automated contract discovery from OpenAPI/Swagger specs
- Pydantic-based schema validation
- Property-based contract testing
- Performance contract validation
- Security contract verification
- Backward compatibility testing

Usage:
    from tests.api_contract import ContractTester, APIContractSuite

    # Basic contract testing
    tester = ContractTester(base_url="http://localhost:8000")
    results = tester.test_all_contracts()

    # Specific endpoint testing
    suite = APIContractSuite()
    suite.test_endpoint_contract("/api/trading/orders", method="POST")

    # Performance contract testing
    suite.test_performance_contract("/api/market-data", max_response_time=500)
"""

from .compatibility_checker import CompatibilityChecker
from .contract_models import (
    APIContract,
    EndpointContract,
    PerformanceContract,
    SchemaContract,
    SecurityContract,
)
from .contract_suite import APIContractSuite
from .contract_tester import ContractTester
from .performance_validator import PerformanceValidator
from .schema_validator import SchemaValidator, ValidationResult
from .security_validator import SecurityValidator
from .utils import (
    check_backward_compatibility,
    discover_api_endpoints,
    generate_test_data,
    validate_response_schema,
)

__all__ = [
    # Core testing classes
    "ContractTester",
    "APIContractSuite",
    # Validation components
    "SchemaValidator",
    "ValidationResult",
    "PerformanceValidator",
    "SecurityValidator",
    "CompatibilityChecker",
    # Contract models
    "APIContract",
    "EndpointContract",
    "SchemaContract",
    "PerformanceContract",
    "SecurityContract",
    # Utility functions
    "discover_api_endpoints",
    "generate_test_data",
    "validate_response_schema",
    "check_backward_compatibility",
]
