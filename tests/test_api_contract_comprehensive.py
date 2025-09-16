"""
Comprehensive API Contract Testing Suite
=======================================

Comprehensive test suite demonstrating and validating the API contract testing
framework including schema validation, performance testing, security validation,
and compatibility checking.
"""

import json
import tempfile
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock, Mock, patch

import pytest

from tests.api_contract import (
    APIContract,
    APIContractSuite,
    CompatibilityChecker,
    ContentType,
    ContractTester,
    EndpointContract,
    FieldSchema,
    HTTPMethod,
    PerformanceContract,
    PerformanceValidator,
    SchemaContract,
    SchemaValidator,
    SecurityContract,
    SecurityScheme,
    SecurityValidator,
    ValidationResult,
)
from tests.api_contract.contract_suite import ContractTestConfig


@pytest.fixture
def sample_schema_contract():
    """Sample schema contract for testing."""
    return SchemaContract(
        name="TradeRequest",
        fields=[
            FieldSchema(
                name="symbol", type="string", required=True, format="trading_symbol"
            ),
            FieldSchema(name="side", type="string", required=True, format="trade_side"),
            FieldSchema(
                name="quantity",
                type="decimal",
                required=True,
                minimum=0.01,
                maximum=1000.0,
            ),
            FieldSchema(name="price", type="decimal", required=False, minimum=0.0001),
            FieldSchema(
                name="order_type", type="string", required=True, format="order_type"
            ),
            FieldSchema(
                name="account_id", type="string", required=True, format="account_id"
            ),
        ],
    )


@pytest.fixture
def sample_endpoint_contract():
    """Sample endpoint contract for testing."""
    return EndpointContract(
        path="/api/trading/orders",
        method=HTTPMethod.POST,
        summary="Create trading order",
        description="Create a new trading order with specified parameters",
        request_schema=SchemaContract(
            name="CreateOrderRequest",
            fields=[
                FieldSchema(name="symbol", type="string", required=True),
                FieldSchema(name="side", type="string", required=True),
                FieldSchema(name="quantity", type="decimal", required=True),
                FieldSchema(name="order_type", type="string", required=True),
            ],
        ),
        response_schemas={
            200: SchemaContract(
                name="OrderResponse",
                fields=[
                    FieldSchema(name="order_id", type="string", required=True),
                    FieldSchema(name="status", type="string", required=True),
                    FieldSchema(name="created_at", type="datetime", required=True),
                ],
            ),
            400: SchemaContract(
                name="ErrorResponse",
                fields=[
                    FieldSchema(name="error", type="string", required=True),
                    FieldSchema(name="message", type="string", required=True),
                ],
            ),
        },
        success_status_codes=[200, 201],
        error_status_codes=[400, 401, 403, 500],
        performance_contract=PerformanceContract(
            max_response_time_ms=1000, min_throughput_rps=10.0
        ),
        security_contract=SecurityContract(
            authentication_required=True,
            authorization_required=True,
            security_scheme=SecurityScheme.BEARER,
            sensitive_data_fields=["account_id"],
            rate_limit_per_minute=60,
        ),
    )


@pytest.fixture
def sample_api_contract(sample_endpoint_contract):
    """Sample API contract for testing."""
    return APIContract(
        title="FXML4 Trading API",
        version="1.0.0",
        description="Comprehensive forex trading API",
        base_url="http://localhost:8000",
        endpoints=[sample_endpoint_contract],
        global_security=SecurityContract(
            authentication_required=True,
            security_scheme=SecurityScheme.BEARER,
            rate_limit_per_minute=100,
        ),
        global_performance=PerformanceContract(
            max_response_time_ms=2000, min_throughput_rps=50.0
        ),
    )


class TestSchemaValidator:
    """Test schema validation functionality."""

    def test_schema_validator_initialization(self):
        """Test schema validator initialization."""
        validator = SchemaValidator()

        assert validator is not None
        assert hasattr(validator, "format_validators")
        assert hasattr(validator, "custom_validators")
        assert "email" in validator.format_validators
        assert "trading_symbol" in validator.format_validators

    def test_valid_schema_validation(self, sample_schema_contract):
        """Test validation of valid data against schema."""
        validator = SchemaValidator()

        valid_data = {
            "symbol": "EURUSD",
            "side": "BUY",
            "quantity": "1.50",
            "price": "1.1234",
            "order_type": "LIMIT",
            "account_id": "ACC12345678",
        }

        result = validator.validate_schema(sample_schema_contract, valid_data)

        assert result.is_valid
        assert len(result.errors) == 0
        assert result.execution_time_ms is not None

    def test_invalid_schema_validation(self, sample_schema_contract):
        """Test validation of invalid data against schema."""
        validator = SchemaValidator()

        invalid_data = {
            "symbol": "INVALID",  # Invalid trading symbol
            "side": "INVALID",  # Invalid trade side
            "quantity": "-1.0",  # Below minimum
            "order_type": "INVALID",  # Invalid order type
            # Missing required account_id
        }

        result = validator.validate_schema(sample_schema_contract, invalid_data)

        assert not result.is_valid
        assert len(result.errors) > 0
        assert any(
            "Missing required field: account_id" in error for error in result.errors
        )

    def test_business_rule_validation(self):
        """Test business rule validation."""
        validator = SchemaValidator()

        # Test trade business rules
        trade_data = {
            "entry_price": "1.1000",
            "exit_price": "1.0900",  # Loss for LONG position
            "side": "LONG",
            "quantity": "1.0",
            "gross_pnl": "-100.0",
            "commission": "2.0",
            "swap": "1.0",
            "net_pnl": "-103.0",
        }

        trade_schema = SchemaContract(
            name="TradeData",
            fields=[
                FieldSchema(name="entry_price", type="decimal", required=True),
                FieldSchema(name="exit_price", type="decimal", required=True),
                FieldSchema(name="side", type="string", required=True),
                FieldSchema(name="quantity", type="decimal", required=True),
                FieldSchema(name="gross_pnl", type="decimal", required=True),
                FieldSchema(name="net_pnl", type="decimal", required=True),
                FieldSchema(name="commission", type="decimal", required=True),
                FieldSchema(name="swap", type="decimal", required=True),
            ],
        )

        result = validator.validate_schema(trade_schema, trade_data)

        # Should be valid but with warnings about loss
        assert result.is_valid
        assert any("indicates loss" in warning for warning in result.warnings)

    def test_format_validators(self):
        """Test specific format validators."""
        validator = SchemaValidator()

        # Test email format
        assert validator._validate_email("user@example.com")
        assert not validator._validate_email("invalid-email")

        # Test trading symbol format
        assert validator._validate_trading_symbol("EURUSD")
        assert not validator._validate_trading_symbol("INVALID")

        # Test trade side format
        assert validator._validate_trade_side("BUY")
        assert validator._validate_trade_side("SELL")
        assert not validator._validate_trade_side("INVALID")

        # Test currency format
        assert validator._validate_currency("USD")
        assert not validator._validate_currency("usd")
        assert not validator._validate_currency("INVALID")


class TestPerformanceValidator:
    """Test performance validation functionality."""

    def test_performance_validator_initialization(self):
        """Test performance validator initialization."""
        validator = PerformanceValidator()

        assert validator is not None
        assert hasattr(validator, "baseline_metrics")
        assert hasattr(validator, "performance_history")

    def test_response_time_validation(self):
        """Test response time validation."""
        validator = PerformanceValidator()

        contract = PerformanceContract(
            max_response_time_ms=1000, min_throughput_rps=10.0
        )

        # Test valid response time
        valid_result = validator.validate_response_time(contract, 500.0)
        assert valid_result.is_valid

        # Test invalid response time
        invalid_result = validator.validate_response_time(contract, 1500.0)
        assert not invalid_result.is_valid
        assert "exceeds maximum allowed" in invalid_result.errors[0]

        # Test warning threshold
        warning_result = validator.validate_response_time(contract, 900.0)
        assert warning_result.is_valid
        assert len(warning_result.warnings) > 0

    def test_throughput_validation(self):
        """Test throughput validation."""
        validator = PerformanceValidator()

        contract = PerformanceContract(
            max_response_time_ms=1000, min_throughput_rps=10.0
        )

        # Test valid throughput
        valid_result = validator.validate_throughput(contract, 15.0)
        assert valid_result.is_valid

        # Test invalid throughput
        invalid_result = validator.validate_throughput(contract, 5.0)
        assert not invalid_result.is_valid
        assert "below minimum required" in invalid_result.errors[0]

        # Test warning threshold
        warning_result = validator.validate_throughput(contract, 11.0)
        assert warning_result.is_valid
        assert len(warning_result.warnings) > 0


class TestSecurityValidator:
    """Test security validation functionality."""

    def test_security_validator_initialization(self):
        """Test security validator initialization."""
        validator = SecurityValidator()

        assert validator is not None
        assert hasattr(validator, "security_patterns")
        assert hasattr(validator, "known_vulnerabilities")

    def test_authentication_validation(self):
        """Test authentication validation."""
        validator = SecurityValidator()

        contract = SecurityContract(
            authentication_required=True, security_scheme=SecurityScheme.BEARER
        )

        # Test valid bearer token
        valid_headers = {
            "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
        }
        valid_result = validator._validate_authentication(
            valid_headers, contract.security_scheme
        )
        assert valid_result.is_valid

        # Test missing authentication
        invalid_headers = {}
        invalid_result = validator._validate_authentication(
            invalid_headers, contract.security_scheme
        )
        assert not invalid_result.is_valid
        assert "Missing authentication credentials" in invalid_result.errors[0]

    def test_security_headers_validation(self):
        """Test security headers validation."""
        validator = SecurityValidator()

        # Test with good security headers
        good_headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Content-Security-Policy": "default-src 'self'",
            "Strict-Transport-Security": "max-age=31536000",
        }

        good_result = validator._validate_security_headers(good_headers, True)
        assert (
            good_result.is_valid or len(good_result.warnings) <= 2
        )  # Allow some warnings

        # Test with missing security headers
        bad_headers = {"Content-Type": "application/json"}

        bad_result = validator._validate_security_headers(bad_headers, True)
        assert not bad_result.is_valid or len(bad_result.warnings) > 0

    def test_data_masking_validation(self):
        """Test sensitive data masking validation."""
        validator = SecurityValidator()

        # Test properly masked data
        masked_data = {
            "account_id": "ACC****5678",
            "password": "********",
            "credit_card": "****-****-****-1234",
        }

        masked_result = validator._validate_data_masking(
            masked_data, ["account_id", "password", "credit_card"]
        )
        assert masked_result.is_valid

        # Test unmasked sensitive data
        unmasked_data = {
            "account_id": "ACC12345678",
            "password": "mypassword123",
            "credit_card": "4111-1111-1111-1111",
        }

        unmasked_result = validator._validate_data_masking(
            unmasked_data, ["account_id", "password", "credit_card"]
        )
        assert not unmasked_result.is_valid
        assert len(unmasked_result.errors) > 0

    def test_injection_detection(self):
        """Test injection attack detection."""
        validator = SecurityValidator()

        # Test SQL injection patterns
        sql_injection_data = {
            "query": "SELECT * FROM users WHERE id = '1' OR '1'='1'",
            "filter": "'; DROP TABLE users; --",
        }

        sql_result = validator._validate_input_sanitization(sql_injection_data)
        assert not sql_result.is_valid
        assert any("sql_injection" in error for error in sql_result.errors)

        # Test XSS patterns
        xss_data = {
            "comment": "<script>alert('xss')</script>",
            "description": "javascript:alert('xss')",
        }

        xss_result = validator._validate_input_sanitization(xss_data)
        assert not xss_result.is_valid
        assert any("xss" in error for error in xss_result.errors)


class TestCompatibilityChecker:
    """Test API compatibility checking functionality."""

    def test_compatibility_checker_initialization(self):
        """Test compatibility checker initialization."""
        checker = CompatibilityChecker()

        assert checker is not None
        assert hasattr(checker, "versioning_rules")
        assert hasattr(checker, "breaking_change_rules")

    def test_compatible_changes(self, sample_api_contract):
        """Test detection of compatible changes."""
        checker = CompatibilityChecker()

        # Create modified contract with compatible changes
        new_contract = APIContract(
            title=sample_api_contract.title,
            version="1.1.0",  # Minor version bump
            description="Updated API with new features",  # Description change
            base_url=sample_api_contract.base_url,
            endpoints=sample_api_contract.endpoints
            + [
                # Added new endpoint (compatible)
                EndpointContract(
                    path="/api/trading/positions",
                    method=HTTPMethod.GET,
                    summary="Get positions",
                )
            ],
        )

        report = checker.check_compatibility(sample_api_contract, new_contract)

        assert report.is_compatible
        assert len(report.breaking_changes) == 0
        assert len(report.changes) > 0  # Should detect the changes

    def test_breaking_changes(self, sample_api_contract):
        """Test detection of breaking changes."""
        checker = CompatibilityChecker()

        # Create modified contract with breaking changes
        modified_endpoints = []
        for endpoint in sample_api_contract.endpoints:
            # Remove an endpoint (breaking change)
            if endpoint.path != "/api/trading/orders":
                modified_endpoints.append(endpoint)

        new_contract = APIContract(
            title=sample_api_contract.title,
            version="2.0.0",  # Major version bump
            description=sample_api_contract.description,
            base_url="https://newapi.example.com",  # Changed base URL (breaking)
            endpoints=modified_endpoints,
        )

        report = checker.check_compatibility(sample_api_contract, new_contract)

        assert not report.is_compatible
        assert len(report.breaking_changes) > 0
        assert report.has_breaking_changes

    def test_version_analysis(self):
        """Test semantic version analysis."""
        checker = CompatibilityChecker()

        # Test major version change
        major_change = checker._analyze_version_change("1.0.0", "2.0.0")
        assert major_change.change_type.value == "breaking"
        assert major_change.severity == "critical"

        # Test minor version change
        minor_change = checker._analyze_version_change("1.0.0", "1.1.0")
        assert minor_change.change_type.value == "compatible"
        assert minor_change.severity == "medium"

        # Test patch version change
        patch_change = checker._analyze_version_change("1.0.0", "1.0.1")
        assert patch_change.change_type.value == "non_breaking"
        assert patch_change.severity == "low"


class TestContractTester:
    """Test main contract tester functionality."""

    @patch("tests.api_contract.contract_tester.httpx.Client")
    def test_contract_tester_initialization(self, mock_client):
        """Test contract tester initialization."""
        from tests.api_contract.contract_tester import ContractTesterConfig

        config = ContractTesterConfig(
            base_url="http://localhost:8000",
            timeout_seconds=30,
            authentication_token="test-token",
        )

        tester = ContractTester(config)

        assert tester.config.base_url == "http://localhost:8000"
        assert tester.config.timeout_seconds == 30
        assert tester.config.authentication_token == "test-token"
        assert tester.schema_validator is not None
        assert tester.performance_validator is not None
        assert tester.security_validator is not None

    @patch("tests.api_contract.contract_tester.httpx.Client")
    def test_endpoint_contract_testing(self, mock_client, sample_endpoint_contract):
        """Test endpoint contract testing."""
        from tests.api_contract.contract_tester import ContractTesterConfig

        # Mock HTTP response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {
            "order_id": "ORDER123",
            "status": "PENDING",
            "created_at": "2023-12-01T10:00:00Z",
        }

        mock_client_instance = Mock()
        mock_client_instance.request.return_value = mock_response
        mock_client.return_value = mock_client_instance

        config = ContractTesterConfig(
            base_url="http://localhost:8000", generate_test_data=True
        )

        tester = ContractTester(config)

        result = tester.test_endpoint_contract(sample_endpoint_contract)

        assert result is not None
        assert result.endpoint == sample_endpoint_contract.path
        assert result.method == sample_endpoint_contract.method.value
        assert result.execution_time_ms > 0


class TestAPIContractSuite:
    """Test comprehensive API contract suite functionality."""

    def test_contract_suite_initialization(self):
        """Test contract suite initialization."""
        config = ContractTestConfig(
            base_url="http://localhost:8000",
            run_schema_tests=True,
            run_performance_tests=True,
            run_security_tests=True,
        )

        suite = APIContractSuite(config)

        assert suite.config.base_url == "http://localhost:8000"
        assert suite.config.run_schema_tests is True
        assert suite.schema_validator is not None
        assert suite.performance_validator is not None
        assert suite.security_validator is not None
        assert suite.compatibility_checker is not None

    @patch("tests.api_contract.contract_tester.ContractTester")
    def test_api_contract_testing(self, mock_tester_class, sample_api_contract):
        """Test complete API contract testing."""
        # Mock contract tester
        mock_tester = Mock()
        mock_result = Mock()
        mock_result.passed = True
        mock_result.execution_time_ms = 250.0
        mock_result.endpoint = "/api/trading/orders"
        mock_result.method = "POST"
        mock_result.status = "passed"
        mock_result.overall_result.errors = []
        mock_result.overall_result.warnings = []

        mock_tester.test_endpoint_contract.return_value = mock_result
        mock_tester_class.return_value = mock_tester

        config = ContractTestConfig(
            base_url="http://localhost:8000",
            run_schema_tests=True,
            run_performance_tests=False,  # Disable for mocking simplicity
            run_security_tests=False,
            run_compatibility_tests=False,
        )

        suite = APIContractSuite(config)

        test_suite = suite.test_api_contract(sample_api_contract)

        assert test_suite is not None
        assert test_suite.total_tests > 0
        assert test_suite.name.startswith("FXML4 Trading API")

    def test_test_data_generation(self, sample_endpoint_contract):
        """Test test data generation for endpoints."""
        config = ContractTestConfig(
            base_url="http://localhost:8000", use_generated_data=True
        )

        suite = APIContractSuite(config)

        test_data = suite._get_test_data_for_endpoint(sample_endpoint_contract)

        assert isinstance(test_data, dict)
        if sample_endpoint_contract.request_schema:
            assert len(test_data) > 0
            # Should contain data for required fields
            required_fields = [
                f.name
                for f in sample_endpoint_contract.request_schema.fields
                if f.required
            ]
            for field in required_fields:
                assert field in test_data


class TestUtilityFunctions:
    """Test utility functions."""

    def test_test_data_generation(self, sample_schema_contract):
        """Test test data generation."""
        from tests.api_contract.utils import generate_test_data

        test_data = generate_test_data(sample_schema_contract)

        assert isinstance(test_data, dict)

        # Check required fields are present
        required_fields = [f.name for f in sample_schema_contract.fields if f.required]
        for field in required_fields:
            assert field in test_data

        # Validate data types
        if "symbol" in test_data:
            assert isinstance(test_data["symbol"], str)
            assert len(test_data["symbol"]) == 6  # Forex pair format

        if "quantity" in test_data:
            quantity_val = (
                float(test_data["quantity"])
                if isinstance(test_data["quantity"], str)
                else test_data["quantity"]
            )
            assert quantity_val >= 0.01  # Minimum constraint

    @patch("tests.api_contract.utils.requests.get")
    def test_endpoint_discovery(self, mock_get):
        """Test API endpoint discovery."""
        from tests.api_contract.utils import discover_api_endpoints

        # Mock OpenAPI spec response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "paths": {
                "/api/health": {"get": {}},
                "/api/trading/orders": {"post": {}, "get": {}},
                "/api/trading/positions": {"get": {}},
            }
        }
        mock_get.return_value = mock_response

        endpoints = discover_api_endpoints("http://localhost:8000")

        assert isinstance(endpoints, list)
        assert len(endpoints) > 0
        assert "/api/health" in endpoints
        assert "/api/trading/orders" in endpoints

    def test_schema_validation_utility(self, sample_schema_contract):
        """Test schema validation utility function."""
        from tests.api_contract.utils import validate_response_schema

        valid_data = {
            "symbol": "EURUSD",
            "side": "BUY",
            "quantity": 1.5,
            "order_type": "MARKET",
            "account_id": "ACC12345678",
        }

        is_valid = validate_response_schema(valid_data, sample_schema_contract)
        assert is_valid

        invalid_data = {
            "symbol": "INVALID",
            "side": "BUY",
            # Missing required fields
        }

        is_invalid = validate_response_schema(invalid_data, sample_schema_contract)
        assert not is_invalid


@pytest.mark.integration
class TestIntegrationScenarios:
    """Integration test scenarios combining multiple components."""

    def test_full_contract_validation_pipeline(self, sample_api_contract):
        """Test complete contract validation pipeline."""
        config = ContractTestConfig(
            base_url="http://localhost:8000",
            run_schema_tests=True,
            run_performance_tests=True,
            run_security_tests=True,
            run_compatibility_tests=False,
            generate_reports=False,  # Disable for test
        )

        suite = APIContractSuite(config)

        # This would normally make real HTTP requests
        # For testing, we'll verify the pipeline structure
        assert suite.schema_validator is not None
        assert suite.performance_validator is not None
        assert suite.security_validator is not None

        # Verify configuration propagation
        assert suite.config.run_schema_tests
        assert suite.config.run_performance_tests
        assert suite.config.run_security_tests

    def test_openapi_spec_integration(self, tmp_path):
        """Test OpenAPI specification integration."""
        # Create a temporary OpenAPI spec file
        openapi_spec = {
            "openapi": "3.0.0",
            "info": {"title": "Test API", "version": "1.0.0"},
            "servers": [{"url": "http://localhost:8000"}],
            "paths": {
                "/health": {
                    "get": {
                        "summary": "Health check",
                        "responses": {
                            "200": {
                                "description": "OK",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "object",
                                            "properties": {
                                                "status": {"type": "string"}
                                            },
                                        }
                                    }
                                },
                            }
                        },
                    }
                }
            },
        }

        spec_file = tmp_path / "api_spec.json"
        with open(spec_file, "w") as f:
            json.dump(openapi_spec, f)

        # Test loading contract from spec
        from tests.api_contract.utils import load_contract_from_openapi

        contract = load_contract_from_openapi(str(spec_file))

        assert contract.title == "Test API"
        assert contract.version == "1.0.0"
        assert len(contract.endpoints) == 1
        assert contract.endpoints[0].path == "/health"
        assert contract.endpoints[0].method == HTTPMethod.GET

    def test_compatibility_evolution_tracking(self, sample_api_contract):
        """Test API evolution tracking across versions."""
        from tests.api_contract.compatibility_checker import APIEvolutionTracker

        tracker = APIEvolutionTracker()

        # Add original version
        tracker.add_version(sample_api_contract)

        # Create v1.1.0 with minor changes
        v1_1_contract = APIContract(
            title=sample_api_contract.title,
            version="1.1.0",
            description=sample_api_contract.description,
            base_url=sample_api_contract.base_url,
            endpoints=sample_api_contract.endpoints
            + [
                EndpointContract(
                    path="/api/trading/positions",
                    method=HTTPMethod.GET,
                    summary="Get positions",
                )
            ],
        )
        tracker.add_version(v1_1_contract)

        # Create v2.0.0 with breaking changes
        v2_0_contract = APIContract(
            title=sample_api_contract.title,
            version="2.0.0",
            description=sample_api_contract.description,
            base_url="https://api-v2.example.com",  # Breaking: base URL change
            endpoints=sample_api_contract.endpoints[:-1],  # Breaking: removed endpoint
        )
        tracker.add_version(v2_0_contract)

        # Track evolution
        evolution_reports = tracker.track_evolution()

        assert len(evolution_reports) == 2  # Two transitions
        assert "1.0.0->1.1.0" in evolution_reports
        assert "1.1.0->2.0.0" in evolution_reports

        # v1.0.0 -> v1.1.0 should be compatible
        v1_to_v1_1 = evolution_reports["1.0.0->1.1.0"]
        assert v1_to_v1_1.is_compatible

        # v1.1.0 -> v2.0.0 should have breaking changes
        v1_1_to_v2 = evolution_reports["1.1.0->2.0.0"]
        assert not v1_1_to_v2.is_compatible
        assert len(v1_1_to_v2.breaking_changes) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
