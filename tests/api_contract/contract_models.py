"""
API Contract Data Models
========================

Pydantic models for defining and validating API contracts including
endpoint schemas, performance SLAs, security requirements, and compatibility rules.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field, validator


class HTTPMethod(str, Enum):
    """Supported HTTP methods."""

    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"


class ContentType(str, Enum):
    """Supported content types."""

    JSON = "application/json"
    FORM_DATA = "application/x-www-form-urlencoded"
    MULTIPART = "multipart/form-data"
    TEXT = "text/plain"
    XML = "application/xml"


class SecurityScheme(str, Enum):
    """Supported security schemes."""

    BEARER = "bearer"
    API_KEY = "apiKey"
    OAUTH2 = "oauth2"
    BASIC = "basic"
    NONE = "none"


class ValidationResult(BaseModel):
    """Result of contract validation."""

    is_valid: bool = Field(description="Whether validation passed")
    errors: List[str] = Field(default=[], description="Validation errors")
    warnings: List[str] = Field(default=[], description="Validation warnings")
    details: Dict[str, Any] = Field(
        default={}, description="Additional validation details"
    )
    execution_time_ms: Optional[float] = Field(
        None, description="Validation execution time"
    )

    def add_error(self, error: str) -> None:
        """Add validation error."""
        self.errors.append(error)
        self.is_valid = False

    def add_warning(self, warning: str) -> None:
        """Add validation warning."""
        self.warnings.append(warning)

    def merge(self, other: "ValidationResult") -> "ValidationResult":
        """Merge with another validation result."""
        return ValidationResult(
            is_valid=self.is_valid and other.is_valid,
            errors=self.errors + other.errors,
            warnings=self.warnings + other.warnings,
            details={**self.details, **other.details},
            execution_time_ms=(self.execution_time_ms or 0)
            + (other.execution_time_ms or 0),
        )


class FieldSchema(BaseModel):
    """Schema definition for API fields."""

    name: str = Field(description="Field name")
    type: str = Field(description="Field type (string, number, boolean, etc.)")
    required: bool = Field(default=True, description="Whether field is required")
    format: Optional[str] = Field(None, description="Field format (email, date, etc.)")
    minimum: Optional[Union[int, float]] = Field(None, description="Minimum value")
    maximum: Optional[Union[int, float]] = Field(None, description="Maximum value")
    min_length: Optional[int] = Field(None, description="Minimum string length")
    max_length: Optional[int] = Field(None, description="Maximum string length")
    pattern: Optional[str] = Field(None, description="Regex pattern")
    enum: Optional[List[Any]] = Field(None, description="Allowed values")
    description: Optional[str] = Field(None, description="Field description")
    example: Optional[Any] = Field(None, description="Example value")

    @validator("type")
    def validate_type(cls, v):
        """Validate field type."""
        allowed_types = [
            "string",
            "number",
            "integer",
            "boolean",
            "array",
            "object",
            "null",
            "decimal",
            "datetime",
            "date",
            "time",
            "uuid",
        ]
        if v not in allowed_types:
            raise ValueError(f"Invalid field type: {v}. Must be one of {allowed_types}")
        return v


class SchemaContract(BaseModel):
    """Contract for request/response schemas."""

    name: str = Field(description="Schema name")
    fields: List[FieldSchema] = Field(description="Schema fields")
    additional_properties: bool = Field(
        default=False, description="Allow additional properties"
    )
    strict_validation: bool = Field(default=True, description="Use strict validation")

    def validate_data(self, data: Dict[str, Any]) -> ValidationResult:
        """Validate data against schema."""
        result = ValidationResult()

        # Check required fields
        required_fields = {f.name for f in self.fields if f.required}
        missing_fields = required_fields - set(data.keys())
        for field in missing_fields:
            result.add_error(f"Missing required field: {field}")

        # Check field types and constraints
        field_map = {f.name: f for f in self.fields}
        for key, value in data.items():
            if key not in field_map:
                if not self.additional_properties:
                    result.add_error(f"Unexpected field: {key}")
                continue

            field = field_map[key]
            field_result = self._validate_field_value(field, value)
            result = result.merge(field_result)

        return result

    def _validate_field_value(self, field: FieldSchema, value: Any) -> ValidationResult:
        """Validate individual field value."""
        result = ValidationResult()

        # Type validation
        if not self._check_type(field.type, value):
            result.add_error(
                f"Field '{field.name}' has incorrect type. Expected {field.type}, got {type(value).__name__}"
            )
            return result

        # Constraint validation
        if (
            field.minimum is not None
            and isinstance(value, (int, float))
            and value < field.minimum
        ):
            result.add_error(
                f"Field '{field.name}' value {value} is below minimum {field.minimum}"
            )

        if (
            field.maximum is not None
            and isinstance(value, (int, float))
            and value > field.maximum
        ):
            result.add_error(
                f"Field '{field.name}' value {value} is above maximum {field.maximum}"
            )

        if (
            field.min_length is not None
            and isinstance(value, str)
            and len(value) < field.min_length
        ):
            result.add_error(
                f"Field '{field.name}' length {len(value)} is below minimum {field.min_length}"
            )

        if (
            field.max_length is not None
            and isinstance(value, str)
            and len(value) > field.max_length
        ):
            result.add_error(
                f"Field '{field.name}' length {len(value)} is above maximum {field.max_length}"
            )

        if field.enum is not None and value not in field.enum:
            result.add_error(
                f"Field '{field.name}' value '{value}' is not in allowed values: {field.enum}"
            )

        return result

    def _check_type(self, expected_type: str, value: Any) -> bool:
        """Check if value matches expected type."""
        type_checks = {
            "string": lambda v: isinstance(v, str),
            "number": lambda v: isinstance(v, (int, float, Decimal)),
            "integer": lambda v: isinstance(v, int),
            "boolean": lambda v: isinstance(v, bool),
            "array": lambda v: isinstance(v, list),
            "object": lambda v: isinstance(v, dict),
            "null": lambda v: v is None,
            "decimal": lambda v: isinstance(v, (Decimal, float, int)),
            "datetime": lambda v: isinstance(v, (str, datetime)),
            "date": lambda v: isinstance(v, str),  # Simplified
            "time": lambda v: isinstance(v, str),  # Simplified
            "uuid": lambda v: isinstance(v, str) and len(v) == 36,  # Simplified
        }

        checker = type_checks.get(expected_type)
        return checker(value) if checker else True


class PerformanceContract(BaseModel):
    """Contract for API performance requirements."""

    max_response_time_ms: int = Field(
        description="Maximum response time in milliseconds"
    )
    max_response_size_bytes: Optional[int] = Field(
        None, description="Maximum response size"
    )
    min_throughput_rps: Optional[float] = Field(
        None, description="Minimum requests per second"
    )
    max_memory_usage_mb: Optional[float] = Field(
        None, description="Maximum memory usage"
    )
    max_cpu_usage_percent: Optional[float] = Field(
        None, description="Maximum CPU usage"
    )

    @validator("max_response_time_ms")
    def validate_response_time(cls, v):
        if v <= 0:
            raise ValueError("Response time must be positive")
        return v


class SecurityContract(BaseModel):
    """Contract for API security requirements."""

    authentication_required: bool = Field(
        default=True, description="Whether authentication is required"
    )
    authorization_required: bool = Field(
        default=True, description="Whether authorization is required"
    )
    security_scheme: SecurityScheme = Field(
        default=SecurityScheme.BEARER, description="Security scheme"
    )
    required_permissions: List[str] = Field(
        default=[], description="Required permissions"
    )
    rate_limit_per_minute: Optional[int] = Field(
        None, description="Rate limit per minute"
    )
    sensitive_data_fields: List[str] = Field(
        default=[], description="Fields containing sensitive data"
    )
    encryption_required: bool = Field(
        default=True, description="Whether encryption is required"
    )

    def validate_security(
        self, headers: Dict[str, str], data: Dict[str, Any]
    ) -> ValidationResult:
        """Validate security requirements."""
        result = ValidationResult()

        if self.authentication_required:
            auth_headers = ["authorization", "x-api-key", "x-auth-token"]
            if not any(header.lower() in headers for header in auth_headers):
                result.add_error("Authentication required but no auth header found")

        # Check for sensitive data exposure
        for field in self.sensitive_data_fields:
            if field in data and isinstance(data[field], str):
                # Simple check for masked data
                if not ("*" in data[field] or "xxx" in data[field].lower()):
                    result.add_warning(f"Potentially unmasked sensitive field: {field}")

        return result


class EndpointContract(BaseModel):
    """Complete contract for an API endpoint."""

    path: str = Field(description="API endpoint path")
    method: HTTPMethod = Field(description="HTTP method")
    summary: Optional[str] = Field(None, description="Endpoint summary")
    description: Optional[str] = Field(None, description="Endpoint description")

    # Request specifications
    request_content_type: ContentType = Field(
        default=ContentType.JSON, description="Request content type"
    )
    request_schema: Optional[SchemaContract] = Field(None, description="Request schema")
    query_parameters: List[FieldSchema] = Field(
        default=[], description="Query parameters"
    )
    path_parameters: List[FieldSchema] = Field(
        default=[], description="Path parameters"
    )
    headers: List[FieldSchema] = Field(default=[], description="Required headers")

    # Response specifications
    response_content_type: ContentType = Field(
        default=ContentType.JSON, description="Response content type"
    )
    success_status_codes: List[int] = Field(
        default=[200], description="Success status codes"
    )
    error_status_codes: List[int] = Field(
        default=[400, 401, 403, 404, 500], description="Error status codes"
    )
    response_schemas: Dict[int, SchemaContract] = Field(
        default={}, description="Response schemas by status code"
    )

    # Contracts
    performance_contract: Optional[PerformanceContract] = Field(
        None, description="Performance requirements"
    )
    security_contract: Optional[SecurityContract] = Field(
        None, description="Security requirements"
    )

    # Metadata
    version: str = Field(default="1.0", description="API version")
    deprecated: bool = Field(
        default=False, description="Whether endpoint is deprecated"
    )
    tags: List[str] = Field(default=[], description="Endpoint tags")

    @validator("path")
    def validate_path(cls, v):
        if not v.startswith("/"):
            raise ValueError("Path must start with '/'")
        return v

    def get_full_path(self) -> str:
        """Get full path with method."""
        return f"{self.method.value} {self.path}"


class APIContract(BaseModel):
    """Complete API contract specification."""

    title: str = Field(description="API title")
    version: str = Field(description="API version")
    description: Optional[str] = Field(None, description="API description")
    base_url: str = Field(description="Base URL")

    endpoints: List[EndpointContract] = Field(description="API endpoints")
    global_security: Optional[SecurityContract] = Field(
        None, description="Global security settings"
    )
    global_performance: Optional[PerformanceContract] = Field(
        None, description="Global performance requirements"
    )

    # Metadata
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Contract creation time"
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, description="Last update time"
    )
    contact: Optional[Dict[str, str]] = Field(
        None, description="API contact information"
    )
    license: Optional[Dict[str, str]] = Field(
        None, description="API license information"
    )

    def get_endpoint(self, path: str, method: HTTPMethod) -> Optional[EndpointContract]:
        """Get endpoint by path and method."""
        for endpoint in self.endpoints:
            if endpoint.path == path and endpoint.method == method:
                return endpoint
        return None

    def get_endpoints_by_tag(self, tag: str) -> List[EndpointContract]:
        """Get endpoints by tag."""
        return [ep for ep in self.endpoints if tag in ep.tags]

    def validate_consistency(self) -> ValidationResult:
        """Validate internal contract consistency."""
        result = ValidationResult()

        # Check for duplicate endpoints
        seen_endpoints = set()
        for endpoint in self.endpoints:
            key = (endpoint.path, endpoint.method)
            if key in seen_endpoints:
                result.add_error(f"Duplicate endpoint: {endpoint.get_full_path()}")
            seen_endpoints.add(key)

        # Check version consistency
        version_patterns = set(ep.version for ep in self.endpoints)
        if len(version_patterns) > 1:
            result.add_warning(f"Inconsistent endpoint versions: {version_patterns}")

        return result


class ContractTestResult(BaseModel):
    """Result of contract testing."""

    endpoint: str = Field(description="Tested endpoint")
    method: str = Field(description="HTTP method")
    status: Literal["passed", "failed", "warning"] = Field(description="Test status")

    schema_validation: ValidationResult = Field(description="Schema validation result")
    performance_validation: ValidationResult = Field(
        description="Performance validation result"
    )
    security_validation: ValidationResult = Field(
        description="Security validation result"
    )

    request_data: Dict[str, Any] = Field(default={}, description="Request data used")
    response_data: Dict[str, Any] = Field(
        default={}, description="Response data received"
    )

    execution_time_ms: float = Field(description="Test execution time")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Test timestamp"
    )

    @property
    def overall_result(self) -> ValidationResult:
        """Get overall validation result."""
        return self.schema_validation.merge(self.performance_validation).merge(
            self.security_validation
        )

    @property
    def passed(self) -> bool:
        """Whether test passed."""
        return self.status == "passed"

    @property
    def failed(self) -> bool:
        """Whether test failed."""
        return self.status == "failed"


class ContractTestSuite(BaseModel):
    """Collection of contract test results."""

    name: str = Field(description="Test suite name")
    results: List[ContractTestResult] = Field(default=[], description="Test results")
    started_at: datetime = Field(
        default_factory=datetime.utcnow, description="Suite start time"
    )
    completed_at: Optional[datetime] = Field(None, description="Suite completion time")

    @property
    def total_tests(self) -> int:
        """Total number of tests."""
        return len(self.results)

    @property
    def passed_tests(self) -> int:
        """Number of passed tests."""
        return sum(1 for r in self.results if r.passed)

    @property
    def failed_tests(self) -> int:
        """Number of failed tests."""
        return sum(1 for r in self.results if r.failed)

    @property
    def success_rate(self) -> float:
        """Test success rate as percentage."""
        if self.total_tests == 0:
            return 0.0
        return (self.passed_tests / self.total_tests) * 100

    @property
    def total_execution_time_ms(self) -> float:
        """Total execution time."""
        return sum(r.execution_time_ms for r in self.results)

    def add_result(self, result: ContractTestResult) -> None:
        """Add test result."""
        self.results.append(result)

    def get_failed_results(self) -> List[ContractTestResult]:
        """Get failed test results."""
        return [r for r in self.results if r.failed]

    def get_results_by_endpoint(self, endpoint: str) -> List[ContractTestResult]:
        """Get results for specific endpoint."""
        return [r for r in self.results if r.endpoint == endpoint]

    def generate_summary(self) -> Dict[str, Any]:
        """Generate test suite summary."""
        return {
            "name": self.name,
            "total_tests": self.total_tests,
            "passed_tests": self.passed_tests,
            "failed_tests": self.failed_tests,
            "success_rate": self.success_rate,
            "execution_time_ms": self.total_execution_time_ms,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "failed_endpoints": [r.endpoint for r in self.get_failed_results()],
        }
