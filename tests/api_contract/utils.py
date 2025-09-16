"""
API Contract Testing Utilities
==============================

Utility functions for API contract testing including endpoint discovery,
test data generation, schema validation helpers, and OpenAPI integration.
"""

import json
import logging
import random
import re
import string
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Set, Union
from urllib.parse import urljoin, urlparse
from uuid import uuid4

import requests
import yaml

from .contract_models import (
    APIContract,
    ContentType,
    EndpointContract,
    FieldSchema,
    HTTPMethod,
    PerformanceContract,
    SchemaContract,
    SecurityContract,
)

logger = logging.getLogger(__name__)


def discover_api_endpoints(base_url: str, timeout: int = 10) -> List[str]:
    """
    Discover API endpoints from a running service.

    Args:
        base_url: Base URL of the API
        timeout: Request timeout in seconds

    Returns:
        List of discovered endpoint paths
    """
    endpoints = []

    try:
        # Try common discovery endpoints
        discovery_paths = [
            "/openapi.json",
            "/swagger.json",
            "/api-docs",
            "/docs/swagger.json",
            "/v1/openapi.json",
            "/api/openapi.json",
        ]

        for path in discovery_paths:
            try:
                url = urljoin(base_url, path)
                response = requests.get(url, timeout=timeout)

                if response.status_code == 200:
                    spec_data = response.json()
                    discovered_endpoints = _extract_endpoints_from_openapi(spec_data)
                    endpoints.extend(discovered_endpoints)
                    logger.info(
                        f"Discovered {len(discovered_endpoints)} endpoints from {url}"
                    )
                    break

            except Exception as e:
                logger.debug(f"Failed to fetch {path}: {e}")
                continue

        # If no OpenAPI spec found, try common endpoint patterns
        if not endpoints:
            logger.info("No OpenAPI spec found, trying common endpoint patterns")
            endpoints = _discover_common_endpoints(base_url, timeout)

    except Exception as e:
        logger.error(f"Error discovering endpoints: {e}")

    return endpoints


def _extract_endpoints_from_openapi(spec_data: Dict[str, Any]) -> List[str]:
    """Extract endpoint paths from OpenAPI specification."""
    endpoints = []

    if "paths" in spec_data:
        for path, path_item in spec_data["paths"].items():
            if isinstance(path_item, dict):
                for method in path_item.keys():
                    if method.upper() in [
                        "GET",
                        "POST",
                        "PUT",
                        "DELETE",
                        "PATCH",
                        "HEAD",
                        "OPTIONS",
                    ]:
                        endpoints.append(path)
                        break  # Only add path once regardless of methods

    return endpoints


def _discover_common_endpoints(base_url: str, timeout: int = 10) -> List[str]:
    """Discover endpoints using common patterns."""
    common_endpoints = [
        "/health",
        "/status",
        "/version",
        "/api/health",
        "/api/status",
        "/api/v1/health",
        "/ping",
        "/ready",
        "/metrics",
    ]

    discovered = []

    for endpoint in common_endpoints:
        try:
            url = urljoin(base_url, endpoint)
            response = requests.head(url, timeout=timeout)

            if response.status_code < 500:  # Any response except server error
                discovered.append(endpoint)

        except Exception:
            continue  # Skip endpoints that can't be reached

    logger.info(f"Discovered {len(discovered)} common endpoints")
    return discovered


def generate_test_data(schema: SchemaContract) -> Dict[str, Any]:
    """
    Generate realistic test data based on schema contract.

    Args:
        schema: Schema contract defining data structure

    Returns:
        Dictionary with generated test data
    """
    test_data = {}

    for field in schema.fields:
        if not field.required and random.random() > 0.7:
            continue  # Sometimes skip optional fields

        test_data[field.name] = _generate_field_value(field)

    return test_data


def _generate_field_value(field: FieldSchema) -> Any:
    """Generate value for a specific field."""

    # Handle enum fields first
    if field.enum:
        return random.choice(field.enum)

    # Generate based on field type
    if field.type == "string":
        return _generate_string_value(field)
    elif field.type == "number" or field.type == "decimal":
        return _generate_number_value(field)
    elif field.type == "integer":
        return _generate_integer_value(field)
    elif field.type == "boolean":
        return random.choice([True, False])
    elif field.type == "array":
        return _generate_array_value(field)
    elif field.type == "object":
        return _generate_object_value(field)
    elif field.type == "datetime":
        return _generate_datetime_value()
    elif field.type == "date":
        return _generate_date_value()
    elif field.type == "uuid":
        return str(uuid4())
    else:
        return None


def _generate_string_value(field: FieldSchema) -> str:
    """Generate string value based on field constraints."""

    # Handle specific formats
    if field.format:
        if field.format == "email":
            username = "".join(
                random.choices(string.ascii_lowercase, k=random.randint(5, 10))
            )
            domain = "".join(
                random.choices(string.ascii_lowercase, k=random.randint(3, 8))
            )
            return f"{username}@{domain}.com"

        elif field.format == "currency":
            return random.choice(["USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD"])

        elif field.format == "trading_symbol":
            pairs = [
                "EURUSD",
                "GBPUSD",
                "USDJPY",
                "USDCHF",
                "AUDUSD",
                "USDCAD",
                "NZDUSD",
            ]
            return random.choice(pairs)

        elif field.format == "trade_side":
            return random.choice(["BUY", "SELL", "LONG", "SHORT"])

        elif field.format == "order_type":
            return random.choice(["MARKET", "LIMIT", "STOP", "STOP_LIMIT"])

        elif field.format == "account_id":
            return f"ACC{random.randint(10000000, 99999999)}"

        elif field.format == "phone":
            return f"+1{random.randint(1000000000, 9999999999)}"

        elif field.format == "country_code":
            return random.choice(["US", "GB", "EU", "CA", "AU", "JP"])

        elif field.format == "timezone":
            return random.choice(
                ["America/New_York", "Europe/London", "Asia/Tokyo", "Australia/Sydney"]
            )

    # Handle pattern constraints
    if field.pattern:
        try:
            # Simple pattern generation (limited support)
            if field.pattern == r"^\d{3}-\d{2}-\d{4}$":  # SSN pattern
                return f"{random.randint(100, 999)}-{random.randint(10, 99)}-{random.randint(1000, 9999)}"
        except:
            pass  # Fall through to default generation

    # Generate based on length constraints
    min_length = max(field.min_length or 1, 1)
    max_length = min(field.max_length or 50, 100)  # Cap at reasonable limit

    length = random.randint(min_length, max_length)

    # Generate meaningful strings based on field name
    if "name" in field.name.lower():
        first_names = [
            "John",
            "Jane",
            "Alice",
            "Bob",
            "Charlie",
            "Diana",
            "Eve",
            "Frank",
        ]
        last_names = [
            "Smith",
            "Johnson",
            "Williams",
            "Brown",
            "Jones",
            "Garcia",
            "Miller",
        ]
        if "first" in field.name.lower():
            return random.choice(first_names)
        elif "last" in field.name.lower():
            return random.choice(last_names)
        else:
            return f"{random.choice(first_names)} {random.choice(last_names)}"

    elif "description" in field.name.lower() or "comment" in field.name.lower():
        words = [
            "market",
            "trading",
            "analysis",
            "strategy",
            "profit",
            "loss",
            "trend",
            "signal",
        ]
        return " ".join(random.choices(words, k=min(length // 8, 10)))

    elif "address" in field.name.lower():
        return f"{random.randint(100, 9999)} {random.choice(['Main', 'Oak', 'Pine', 'Elm'])} St"

    else:
        # Generate random string
        return "".join(random.choices(string.ascii_letters + string.digits, k=length))


def _generate_number_value(field: FieldSchema) -> float:
    """Generate number value based on field constraints."""

    # Set reasonable defaults for financial data
    min_val = field.minimum if field.minimum is not None else 0.0
    max_val = field.maximum if field.maximum is not None else 100000.0

    # Adjust for specific field types
    if "price" in field.name.lower():
        min_val = max(min_val, 0.0001)
        max_val = (
            min(max_val, 10.0)
            if "forex" in field.name.lower()
            else min(max_val, 1000.0)
        )

    elif "percentage" in field.name.lower() or "rate" in field.name.lower():
        min_val = max(min_val, -100.0)
        max_val = min(max_val, 1000.0)

    elif "quantity" in field.name.lower() or "amount" in field.name.lower():
        min_val = max(min_val, 0.01)
        max_val = min(max_val, 1000000.0)

    value = random.uniform(min_val, max_val)

    # Round to reasonable precision for financial data
    if "price" in field.name.lower():
        return round(value, 4)
    elif "percentage" in field.name.lower():
        return round(value, 2)
    else:
        return round(value, 2)


def _generate_integer_value(field: FieldSchema) -> int:
    """Generate integer value based on field constraints."""

    min_val = int(field.minimum) if field.minimum is not None else 1
    max_val = int(field.maximum) if field.maximum is not None else 1000

    # Adjust for specific field types
    if "id" in field.name.lower():
        min_val = max(min_val, 1)
        max_val = min(max_val, 999999)

    elif "count" in field.name.lower():
        min_val = max(min_val, 0)
        max_val = min(max_val, 1000)

    elif "year" in field.name.lower():
        min_val = max(min_val, 1900)
        max_val = min(max_val, 2030)

    return random.randint(min_val, max_val)


def _generate_array_value(field: FieldSchema) -> List[Any]:
    """Generate array value."""
    # Generate 1-5 items
    length = random.randint(1, 5)

    # Create a simplified field for array items
    item_field = FieldSchema(
        name=f"{field.name}_item",
        type="string",  # Default to string items
        required=True,
    )

    return [_generate_field_value(item_field) for _ in range(length)]


def _generate_object_value(field: FieldSchema) -> Dict[str, Any]:
    """Generate object value."""
    # Generate simple object with 2-4 properties
    obj = {}
    properties = ["id", "name", "value", "status"]

    for prop in random.sample(properties, k=random.randint(2, 4)):
        prop_field = FieldSchema(
            name=prop,
            type="string" if prop in ["name", "status"] else "integer",
            required=True,
        )
        obj[prop] = _generate_field_value(prop_field)

    return obj


def _generate_datetime_value() -> str:
    """Generate datetime value in ISO format."""
    # Generate datetime within last 30 days
    start_date = datetime.utcnow() - timedelta(days=30)
    end_date = datetime.utcnow()

    time_between = end_date - start_date
    days_between = time_between.days
    random_days = random.randrange(days_between)

    random_date = start_date + timedelta(days=random_days)
    return random_date.isoformat() + "Z"


def _generate_date_value() -> str:
    """Generate date value in ISO format."""
    datetime_value = _generate_datetime_value()
    return datetime_value.split("T")[0]  # Extract date part


def validate_response_schema(
    response_data: Dict[str, Any], schema: SchemaContract
) -> bool:
    """
    Validate response data against schema.

    Args:
        response_data: Response data to validate
        schema: Schema contract to validate against

    Returns:
        True if valid, False otherwise
    """
    try:
        validation_result = schema.validate_data(response_data)
        return validation_result.is_valid
    except Exception as e:
        logger.error(f"Schema validation error: {e}")
        return False


def check_backward_compatibility(
    old_schema: SchemaContract, new_schema: SchemaContract
) -> bool:
    """
    Check if new schema is backward compatible with old schema.

    Args:
        old_schema: Previous schema version
        new_schema: New schema version

    Returns:
        True if backward compatible, False otherwise
    """
    from .compatibility_checker import CompatibilityChecker

    # Create dummy contracts for compatibility checking
    old_contract = APIContract(
        title="Old API", version="1.0", base_url="http://example.com", endpoints=[]
    )

    new_contract = APIContract(
        title="New API", version="2.0", base_url="http://example.com", endpoints=[]
    )

    checker = CompatibilityChecker()
    report = checker.check_compatibility(old_contract, new_contract)

    return report.is_compatible


def load_contract_from_openapi(spec_url_or_path: str) -> APIContract:
    """
    Load API contract from OpenAPI/Swagger specification.

    Args:
        spec_url_or_path: URL or file path to OpenAPI spec

    Returns:
        APIContract instance
    """
    try:
        # Determine if it's a URL or file path
        if spec_url_or_path.startswith(("http://", "https://")):
            response = requests.get(spec_url_or_path)
            response.raise_for_status()
            spec_data = response.json()
        else:
            with open(spec_url_or_path, "r") as f:
                if spec_url_or_path.endswith(".yaml") or spec_url_or_path.endswith(
                    ".yml"
                ):
                    spec_data = yaml.safe_load(f)
                else:
                    spec_data = json.load(f)

        return _convert_openapi_to_contract(spec_data)

    except Exception as e:
        logger.error(f"Error loading OpenAPI spec: {e}")
        raise


def _convert_openapi_to_contract(spec_data: Dict[str, Any]) -> APIContract:
    """Convert OpenAPI specification to API contract."""

    # Extract basic info
    info = spec_data.get("info", {})
    title = info.get("title", "API")
    version = info.get("version", "1.0")
    description = info.get("description")

    # Extract base URL
    base_url = "http://localhost"
    if "servers" in spec_data and spec_data["servers"]:
        base_url = spec_data["servers"][0].get("url", base_url)

    # Convert endpoints
    endpoints = []
    paths = spec_data.get("paths", {})

    for path, path_item in paths.items():
        for method, operation in path_item.items():
            if method.upper() in [
                "GET",
                "POST",
                "PUT",
                "DELETE",
                "PATCH",
                "HEAD",
                "OPTIONS",
            ]:
                endpoint = _convert_openapi_operation(path, method.upper(), operation)
                endpoints.append(endpoint)

    return APIContract(
        title=title,
        version=version,
        description=description,
        base_url=base_url,
        endpoints=endpoints,
    )


def _convert_openapi_operation(
    path: str, method: str, operation: Dict[str, Any]
) -> EndpointContract:
    """Convert OpenAPI operation to endpoint contract."""

    summary = operation.get("summary", "")
    description = operation.get("description", "")
    deprecated = operation.get("deprecated", False)
    tags = operation.get("tags", [])

    # Convert parameters
    query_parameters = []
    path_parameters = []
    headers = []

    parameters = operation.get("parameters", [])
    for param in parameters:
        field_schema = _convert_openapi_parameter(param)

        if param.get("in") == "query":
            query_parameters.append(field_schema)
        elif param.get("in") == "path":
            path_parameters.append(field_schema)
        elif param.get("in") == "header":
            headers.append(field_schema)

    # Convert request body
    request_schema = None
    request_body = operation.get("requestBody")
    if request_body:
        content = request_body.get("content", {})
        if "application/json" in content:
            json_schema = content["application/json"].get("schema", {})
            request_schema = _convert_openapi_schema(json_schema, "request")

    # Convert responses
    response_schemas = {}
    responses = operation.get("responses", {})

    for status_code, response_def in responses.items():
        if isinstance(status_code, str) and status_code.isdigit():
            status_int = int(status_code)
            content = response_def.get("content", {})

            if "application/json" in content:
                json_schema = content["application/json"].get("schema", {})
                response_schemas[status_int] = _convert_openapi_schema(
                    json_schema, f"response_{status_code}"
                )

    # Determine success and error status codes
    success_codes = [code for code in response_schemas.keys() if 200 <= code < 300]
    error_codes = [code for code in response_schemas.keys() if code >= 400]

    if not success_codes:
        success_codes = [200]  # Default

    if not error_codes:
        error_codes = [400, 401, 403, 404, 500]  # Common error codes

    return EndpointContract(
        path=path,
        method=HTTPMethod(method),
        summary=summary,
        description=description,
        deprecated=deprecated,
        tags=tags,
        query_parameters=query_parameters,
        path_parameters=path_parameters,
        headers=headers,
        request_schema=request_schema,
        success_status_codes=success_codes,
        error_status_codes=error_codes,
        response_schemas=response_schemas,
    )


def _convert_openapi_parameter(param: Dict[str, Any]) -> FieldSchema:
    """Convert OpenAPI parameter to field schema."""

    name = param.get("name", "")
    required = param.get("required", False)
    description = param.get("description", "")

    # Extract schema
    schema = param.get("schema", {})
    param_type = schema.get("type", "string")
    format_type = schema.get("format")
    enum_values = schema.get("enum")
    minimum = schema.get("minimum")
    maximum = schema.get("maximum")

    return FieldSchema(
        name=name,
        type=param_type,
        required=required,
        format=format_type,
        enum=enum_values,
        minimum=minimum,
        maximum=maximum,
        description=description,
    )


def _convert_openapi_schema(schema: Dict[str, Any], schema_name: str) -> SchemaContract:
    """Convert OpenAPI schema to schema contract."""

    schema_type = schema.get("type", "object")
    required_fields = schema.get("required", [])
    properties = schema.get("properties", {})
    additional_properties = schema.get("additionalProperties", False)

    fields = []

    if schema_type == "object" and properties:
        for field_name, field_def in properties.items():
            field_schema = FieldSchema(
                name=field_name,
                type=field_def.get("type", "string"),
                required=field_name in required_fields,
                format=field_def.get("format"),
                enum=field_def.get("enum"),
                minimum=field_def.get("minimum"),
                maximum=field_def.get("maximum"),
                min_length=field_def.get("minLength"),
                max_length=field_def.get("maxLength"),
                pattern=field_def.get("pattern"),
                description=field_def.get("description"),
                example=field_def.get("example"),
            )
            fields.append(field_schema)

    return SchemaContract(
        name=schema_name, fields=fields, additional_properties=additional_properties
    )


def create_test_suite_from_contract(contract: APIContract) -> Dict[str, Any]:
    """
    Create test suite configuration from API contract.

    Args:
        contract: API contract to create tests for

    Returns:
        Test suite configuration dictionary
    """
    test_suite = {
        "name": f"{contract.title} Contract Tests",
        "base_url": contract.base_url,
        "version": contract.version,
        "endpoints": [],
        "global_settings": {"timeout": 30, "retries": 3, "verify_ssl": True},
    }

    for endpoint in contract.endpoints:
        endpoint_test = {
            "path": endpoint.path,
            "method": endpoint.method.value,
            "name": endpoint.summary or f"{endpoint.method.value} {endpoint.path}",
            "description": endpoint.description,
            "tags": endpoint.tags,
            "deprecated": endpoint.deprecated,
            "test_data": (
                generate_test_data(endpoint.request_schema)
                if endpoint.request_schema
                else {}
            ),
            "expected_status_codes": endpoint.success_status_codes,
            "performance_requirements": {
                "max_response_time_ms": (
                    endpoint.performance_contract.max_response_time_ms
                    if endpoint.performance_contract
                    else 5000
                )
            },
            "security_requirements": {
                "authentication_required": (
                    endpoint.security_contract.authentication_required
                    if endpoint.security_contract
                    else True
                )
            },
        }

        test_suite["endpoints"].append(endpoint_test)

    return test_suite


def normalize_json_schema(schema: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize JSON schema for consistent comparison.

    Args:
        schema: JSON schema to normalize

    Returns:
        Normalized schema
    """
    normalized = schema.copy()

    # Sort properties for consistent comparison
    if "properties" in normalized and isinstance(normalized["properties"], dict):
        normalized["properties"] = dict(sorted(normalized["properties"].items()))

    # Sort required fields
    if "required" in normalized and isinstance(normalized["required"], list):
        normalized["required"] = sorted(normalized["required"])

    # Sort enum values
    if "enum" in normalized and isinstance(normalized["enum"], list):
        try:
            normalized["enum"] = sorted(normalized["enum"])
        except TypeError:
            pass  # Keep original order if items are not sortable

    return normalized


def generate_contract_diff(
    old_contract: APIContract, new_contract: APIContract
) -> Dict[str, Any]:
    """
    Generate detailed diff between two API contracts.

    Args:
        old_contract: Previous contract version
        new_contract: New contract version

    Returns:
        Detailed diff dictionary
    """
    from .compatibility_checker import CompatibilityChecker

    checker = CompatibilityChecker()
    compatibility_report = checker.check_compatibility(old_contract, new_contract)

    # Create detailed diff
    diff = {
        "summary": {
            "old_version": old_contract.version,
            "new_version": new_contract.version,
            "total_changes": len(compatibility_report.changes),
            "breaking_changes": len(compatibility_report.breaking_changes),
            "is_compatible": compatibility_report.is_compatible,
        },
        "changes_by_category": {},
        "detailed_changes": [
            change.to_dict() for change in compatibility_report.changes
        ],
        "affected_endpoints": set(),
    }

    # Categorize changes
    for change in compatibility_report.changes:
        category = change.location.split(".")[0]
        if category not in diff["changes_by_category"]:
            diff["changes_by_category"][category] = []
        diff["changes_by_category"][category].append(change.to_dict())

        # Track affected endpoints
        if "endpoint" in change.location:
            endpoint_path = (
                change.location.split(".")[1]
                if len(change.location.split(".")) > 1
                else "unknown"
            )
            diff["affected_endpoints"].add(endpoint_path)

    diff["affected_endpoints"] = list(diff["affected_endpoints"])

    return diff
