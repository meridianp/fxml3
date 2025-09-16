"""
Security Contract Validator
==========================

Validates API security contracts including authentication, authorization,
data protection, and security headers for trading system APIs.
"""

import base64
import hashlib
import json
import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import parse_qs, urlparse

from .contract_models import SecurityContract, ValidationResult

logger = logging.getLogger(__name__)


class SecurityValidator:
    """
    Security validation engine for API contracts.

    Validates security contracts by checking:
    - Authentication mechanisms
    - Authorization controls
    - Data protection and masking
    - Security headers
    - Input validation and sanitization
    - Rate limiting compliance
    - SSL/TLS requirements
    """

    def __init__(self):
        """Initialize security validator."""
        self.known_vulnerabilities = {}
        self.security_patterns = self._build_security_patterns()

    def validate_response_security(
        self,
        contract: SecurityContract,
        headers: Dict[str, str],
        response_data: Dict[str, Any],
    ) -> ValidationResult:
        """Validate response against security contract."""
        result = ValidationResult()

        # Validate security headers
        header_result = self._validate_security_headers(
            headers, contract.encryption_required
        )
        result = result.merge(header_result)

        # Validate sensitive data masking
        if contract.sensitive_data_fields:
            masking_result = self._validate_data_masking(
                response_data, contract.sensitive_data_fields
            )
            result = result.merge(masking_result)

        # Validate data exposure
        exposure_result = self._validate_data_exposure(response_data)
        result = result.merge(exposure_result)

        # Validate response structure for security
        structure_result = self._validate_response_structure(response_data)
        result = result.merge(structure_result)

        return result

    def validate_request_security(
        self,
        contract: SecurityContract,
        headers: Dict[str, str],
        request_data: Dict[str, Any],
        url: str,
    ) -> ValidationResult:
        """Validate request against security contract."""
        result = ValidationResult()

        # Validate authentication
        if contract.authentication_required:
            auth_result = self._validate_authentication(
                headers, contract.security_scheme
            )
            result = result.merge(auth_result)

        # Validate input sanitization
        sanitization_result = self._validate_input_sanitization(request_data)
        result = result.merge(sanitization_result)

        # Validate URL security
        url_result = self._validate_url_security(url)
        result = result.merge(url_result)

        # Validate request size
        size_result = self._validate_request_size(request_data)
        result = result.merge(size_result)

        return result

    def _validate_security_headers(
        self, headers: Dict[str, str], encryption_required: bool
    ) -> ValidationResult:
        """Validate security-related HTTP headers."""
        result = ValidationResult()

        # Convert headers to lowercase for case-insensitive lookup
        lower_headers = {k.lower(): v for k, v in headers.items()}

        # Required security headers
        required_headers = {
            "x-content-type-options": "nosniff",
            "x-frame-options": ["DENY", "SAMEORIGIN"],
            "x-xss-protection": "1; mode=block",
            "referrer-policy": [
                "strict-origin-when-cross-origin",
                "strict-origin",
                "no-referrer",
            ],
        }

        for header, expected_values in required_headers.items():
            if header not in lower_headers:
                result.add_warning(f"Missing security header: {header}")
                continue

            header_value = lower_headers[header]
            if isinstance(expected_values, list):
                if header_value not in expected_values:
                    result.add_warning(
                        f"Insecure header value for {header}: {header_value}"
                    )
            else:
                if header_value != expected_values:
                    result.add_warning(
                        f"Insecure header value for {header}: {header_value}"
                    )

        # Content Security Policy
        if "content-security-policy" not in lower_headers:
            result.add_warning("Missing Content-Security-Policy header")
        else:
            csp_result = self._validate_csp_header(
                lower_headers["content-security-policy"]
            )
            result = result.merge(csp_result)

        # Strict Transport Security (for HTTPS)
        if encryption_required and "strict-transport-security" not in lower_headers:
            result.add_warning(
                "Missing Strict-Transport-Security header for HTTPS endpoint"
            )

        # Check for information disclosure in headers
        disclosure_result = self._check_header_information_disclosure(headers)
        result = result.merge(disclosure_result)

        return result

    def _validate_csp_header(self, csp_value: str) -> ValidationResult:
        """Validate Content Security Policy header."""
        result = ValidationResult()

        # Basic CSP validation
        if "unsafe-eval" in csp_value:
            result.add_warning("CSP allows unsafe-eval which may enable code injection")

        if "unsafe-inline" in csp_value:
            result.add_warning("CSP allows unsafe-inline which may enable XSS attacks")

        if "*" in csp_value and "data:" not in csp_value:
            result.add_warning("CSP uses wildcard (*) which may be overly permissive")

        return result

    def _validate_authentication(
        self, headers: Dict[str, str], security_scheme
    ) -> ValidationResult:
        """Validate authentication in request headers."""
        result = ValidationResult()

        auth_header = headers.get("Authorization", headers.get("authorization", ""))

        if not auth_header:
            # Check for other auth headers
            api_key_headers = ["x-api-key", "x-auth-token", "api-key"]
            has_alt_auth = any(
                h in headers or h.upper() in headers for h in api_key_headers
            )

            if not has_alt_auth:
                result.add_error("Missing authentication credentials")
                return result

        if auth_header:
            # Validate Bearer token format
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]  # Remove 'Bearer ' prefix
                token_result = self._validate_bearer_token(token)
                result = result.merge(token_result)

            # Validate Basic auth format
            elif auth_header.startswith("Basic "):
                basic_result = self._validate_basic_auth(auth_header)
                result = result.merge(basic_result)

        return result

    def _validate_bearer_token(self, token: str) -> ValidationResult:
        """Validate Bearer token format and properties."""
        result = ValidationResult()

        if not token:
            result.add_error("Empty Bearer token")
            return result

        # Check token length (JWT tokens are typically longer)
        if len(token) < 20:
            result.add_warning("Bearer token appears too short")

        # Check for JWT format
        if token.count(".") == 2:
            jwt_result = self._validate_jwt_token(token)
            result = result.merge(jwt_result)

        # Check for plaintext patterns
        if any(
            pattern in token.lower()
            for pattern in ["password", "secret", "key", "admin"]
        ):
            result.add_error("Bearer token appears to contain plaintext secrets")

        return result

    def _validate_jwt_token(self, token: str) -> ValidationResult:
        """Validate JWT token structure."""
        result = ValidationResult()

        try:
            parts = token.split(".")
            if len(parts) != 3:
                result.add_error("Invalid JWT format: must have 3 parts")
                return result

            # Decode header and payload (without verification)
            header = json.loads(base64.urlsafe_b64decode(parts[0] + "=="))
            payload = json.loads(base64.urlsafe_b64decode(parts[1] + "=="))

            # Validate header
            if "alg" not in header:
                result.add_error("JWT header missing algorithm")
            elif header["alg"] == "none":
                result.add_error("JWT uses 'none' algorithm - security risk")
            elif header["alg"] in ["HS256", "HS384", "HS512"]:
                result.add_warning("JWT uses HMAC algorithm - ensure key security")

            # Validate payload
            current_time = int(time.time()) if "time" in globals() else None

            if "exp" in payload and current_time:
                if payload["exp"] < current_time:
                    result.add_error("JWT token has expired")
                elif payload["exp"] - current_time < 300:  # Expires in < 5 minutes
                    result.add_warning("JWT token expires soon")

            if "iat" in payload and current_time:
                if (
                    payload["iat"] > current_time + 60
                ):  # Issued more than 1 minute in future
                    result.add_warning("JWT issued time is in the future")

        except Exception as e:
            result.add_error(f"Failed to parse JWT token: {str(e)}")

        return result

    def _validate_basic_auth(self, auth_header: str) -> ValidationResult:
        """Validate Basic authentication header."""
        result = ValidationResult()

        try:
            encoded_credentials = auth_header[6:]  # Remove 'Basic ' prefix
            credentials = base64.b64decode(encoded_credentials).decode("utf-8")

            if ":" not in credentials:
                result.add_error("Invalid Basic auth format: missing colon separator")
                return result

            username, password = credentials.split(":", 1)

            # Validate username
            if not username:
                result.add_error("Basic auth: empty username")
            elif len(username) < 3:
                result.add_warning("Basic auth: very short username")

            # Validate password (without exposing it)
            if not password:
                result.add_error("Basic auth: empty password")
            elif len(password) < 8:
                result.add_warning("Basic auth: password appears short")

        except Exception as e:
            result.add_error(f"Failed to decode Basic auth: {str(e)}")

        return result

    def _validate_data_masking(
        self, data: Dict[str, Any], sensitive_fields: List[str]
    ) -> ValidationResult:
        """Validate that sensitive data is properly masked."""
        result = ValidationResult()

        def check_field_masking(obj, path=""):
            """Recursively check for unmasked sensitive data."""
            if isinstance(obj, dict):
                for key, value in obj.items():
                    current_path = f"{path}.{key}" if path else key

                    # Check if this field should be masked
                    if any(
                        sensitive_field.lower() in key.lower()
                        for sensitive_field in sensitive_fields
                    ):
                        if (
                            isinstance(value, str)
                            and value
                            and not self._is_masked_value(value)
                        ):
                            result.add_error(
                                f"Sensitive field '{current_path}' appears unmasked: {value[:10]}..."
                            )

                    # Recurse into nested objects
                    check_field_masking(value, current_path)

            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    check_field_masking(item, f"{path}[{i}]")

        check_field_masking(data)
        return result

    def _is_masked_value(self, value: str) -> bool:
        """Check if a value appears to be masked."""
        masking_patterns = [
            r"^\*+$",  # All asterisks
            r".*\*{3,}.*",  # Contains 3+ asterisks
            r"^x{4,}$",  # All x's (4 or more)
            r".*xxx.*",  # Contains xxx
            r"^\[MASKED\]$",  # Explicit mask
            r"^\[REDACTED\]$",  # Explicit redaction
            r"^•{4,}$",  # Bullet characters
        ]

        return any(
            re.match(pattern, value, re.IGNORECASE) for pattern in masking_patterns
        )

    def _validate_data_exposure(self, data: Dict[str, Any]) -> ValidationResult:
        """Check for potential data exposure issues."""
        result = ValidationResult()

        # Check for common sensitive data patterns
        exposure_patterns = {
            "credit_card": r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b",
            "ssn": r"\b\d{3}-?\d{2}-?\d{4}\b",
            "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
            "phone": r"\b[\+]?[1-9]?[0-9]{7,15}\b",
            "api_key": r"\b[A-Za-z0-9]{32,}\b",
            "password_hash": r"\$2[abyg]\$\d+\$[A-Za-z0-9./]{53}",
            "jwt_token": r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b",
        }

        def scan_for_patterns(obj, path=""):
            """Recursively scan for sensitive patterns."""
            if isinstance(obj, str):
                for pattern_name, pattern in exposure_patterns.items():
                    if re.search(pattern, obj):
                        result.add_warning(
                            f"Potential {pattern_name} exposure at {path}: {obj[:20]}..."
                        )

            elif isinstance(obj, dict):
                for key, value in obj.items():
                    current_path = f"{path}.{key}" if path else key
                    scan_for_patterns(value, current_path)

            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    scan_for_patterns(item, f"{path}[{i}]")

        scan_for_patterns(data)
        return result

    def _validate_input_sanitization(
        self, request_data: Dict[str, Any]
    ) -> ValidationResult:
        """Validate input sanitization and check for injection attacks."""
        result = ValidationResult()

        # Common injection patterns
        injection_patterns = {
            "sql_injection": [
                r"(?i)\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER)\b.*\b(FROM|INTO|SET|WHERE)\b",
                r"(?i)\b(UNION|JOIN)\b.*\b(SELECT)\b",
                r"[';].*--",
                r"\b(OR|AND)\s+\d+\s*=\s*\d+",
            ],
            "xss": [
                r"<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>",
                r"javascript:",
                r"on\w+\s*=",
                r"<iframe\b",
                r"<object\b",
                r"<embed\b",
            ],
            "command_injection": [
                r"[;&|`]",
                r"\$\([^)]*\)",
                r"`[^`]*`",
                r"(?i)\b(cat|ls|pwd|whoami|id|uname)\b",
            ],
            "ldap_injection": [
                r"[()&|!]",
                r"[*]",
            ],
        }

        def scan_input(obj, path=""):
            """Recursively scan input for injection patterns."""
            if isinstance(obj, str):
                for injection_type, patterns in injection_patterns.items():
                    for pattern in patterns:
                        if re.search(pattern, obj):
                            result.add_error(
                                f"Potential {injection_type} detected at {path}: {obj[:50]}..."
                            )
                            break

            elif isinstance(obj, dict):
                for key, value in obj.items():
                    current_path = f"{path}.{key}" if path else key
                    scan_input(value, current_path)

            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    scan_input(item, f"{path}[{i}]")

        scan_input(request_data)
        return result

    def _validate_url_security(self, url: str) -> ValidationResult:
        """Validate URL security aspects."""
        result = ValidationResult()

        parsed_url = urlparse(url)

        # Check for HTTPS
        if parsed_url.scheme != "https":
            result.add_warning("URL uses insecure HTTP instead of HTTPS")

        # Check for suspicious query parameters
        if parsed_url.query:
            query_params = parse_qs(parsed_url.query)
            suspicious_params = ["password", "secret", "token", "key", "admin"]

            for param_name in query_params.keys():
                if any(suspect in param_name.lower() for suspect in suspicious_params):
                    result.add_warning(
                        f"Potentially sensitive parameter in URL: {param_name}"
                    )

        # Check for path traversal
        if "../" in parsed_url.path or "..\\" in parsed_url.path:
            result.add_error("Potential path traversal in URL")

        return result

    def _validate_request_size(self, request_data: Dict[str, Any]) -> ValidationResult:
        """Validate request size to prevent DoS attacks."""
        result = ValidationResult()

        try:
            # Estimate request size
            request_json = json.dumps(request_data)
            request_size_bytes = len(request_json.encode("utf-8"))

            # Check size limits
            if request_size_bytes > 10 * 1024 * 1024:  # 10MB
                result.add_error(
                    f"Request size ({request_size_bytes} bytes) exceeds maximum limit"
                )
            elif request_size_bytes > 1024 * 1024:  # 1MB
                result.add_warning(f"Large request size: {request_size_bytes} bytes")

            # Check for deeply nested objects (potential DoS)
            max_depth = self._get_json_depth(request_data)
            if max_depth > 50:
                result.add_error(f"Request JSON depth ({max_depth}) exceeds safe limit")
            elif max_depth > 20:
                result.add_warning(f"Deep JSON nesting detected: {max_depth} levels")

        except Exception as e:
            result.add_warning(f"Could not validate request size: {str(e)}")

        return result

    def _get_json_depth(self, obj, current_depth=0):
        """Calculate maximum depth of JSON object."""
        if isinstance(obj, dict):
            if not obj:
                return current_depth
            return max(
                self._get_json_depth(value, current_depth + 1) for value in obj.values()
            )
        elif isinstance(obj, list):
            if not obj:
                return current_depth
            return max(self._get_json_depth(item, current_depth + 1) for item in obj)
        else:
            return current_depth

    def _validate_response_structure(
        self, response_data: Dict[str, Any]
    ) -> ValidationResult:
        """Validate response structure for security issues."""
        result = ValidationResult()

        # Check for error information disclosure
        if "error" in response_data or "exception" in response_data:
            error_result = self._validate_error_disclosure(response_data)
            result = result.merge(error_result)

        # Check for debug information
        debug_fields = ["debug", "trace", "stack_trace", "internal", "system"]
        for field in debug_fields:
            if field in response_data:
                result.add_warning(f"Response contains debug information: {field}")

        # Check for version disclosure
        version_fields = ["version", "server", "framework", "database"]
        for field in version_fields:
            if field in response_data:
                result.add_warning(
                    f"Response may disclose version information: {field}"
                )

        return result

    def _validate_error_disclosure(
        self, response_data: Dict[str, Any]
    ) -> ValidationResult:
        """Validate error messages for information disclosure."""
        result = ValidationResult()

        error_fields = ["error", "exception", "message", "detail"]

        for field in error_fields:
            if field in response_data:
                error_message = str(response_data[field])

                # Check for file path disclosure
                if "/" in error_message and (
                    "etc" in error_message or "var" in error_message
                ):
                    result.add_error("Error message may disclose file paths")

                # Check for database information
                if any(
                    db_term in error_message.lower()
                    for db_term in ["sql", "database", "table", "column"]
                ):
                    result.add_error("Error message may disclose database information")

                # Check for internal IP addresses
                if re.search(
                    r"\b(?:10\.|172\.1[6-9]\.|172\.2[0-9]\.|172\.3[01]\.|192\.168\.)\d+\.\d+\b",
                    error_message,
                ):
                    result.add_error("Error message may disclose internal IP addresses")

                # Check for stack traces
                if (
                    "traceback" in error_message.lower()
                    or "at line" in error_message.lower()
                ):
                    result.add_error("Error message contains stack trace information")

        return result

    def _check_header_information_disclosure(
        self, headers: Dict[str, str]
    ) -> ValidationResult:
        """Check headers for information disclosure."""
        result = ValidationResult()

        # Headers that may disclose information
        disclosure_headers = {
            "server": "Server header discloses server information",
            "x-powered-by": "X-Powered-By header discloses technology stack",
            "x-aspnet-version": "ASP.NET version header disclosure",
            "x-generator": "Generator header discloses framework information",
        }

        for header, message in disclosure_headers.items():
            if header in headers or header.upper() in headers:
                result.add_warning(message)

        return result

    def _build_security_patterns(self) -> Dict[str, List[str]]:
        """Build security validation patterns."""
        return {
            "sensitive_fields": [
                "password",
                "secret",
                "key",
                "token",
                "credential",
                "ssn",
                "social_security",
                "credit_card",
                "card_number",
                "pin",
                "cvv",
                "security_code",
                "private_key",
            ],
            "injection_keywords": [
                "select",
                "insert",
                "update",
                "delete",
                "drop",
                "create",
                "union",
                "script",
                "javascript",
                "eval",
                "expression",
            ],
            "system_commands": [
                "cat",
                "ls",
                "pwd",
                "whoami",
                "id",
                "ps",
                "kill",
                "rm",
                "mv",
                "cp",
                "chmod",
                "chown",
                "sudo",
            ],
        }


import time  # Import time for JWT validation


class SecurityAudit:
    """
    Security audit utilities for API contract testing.
    """

    def __init__(self):
        """Initialize security audit."""
        self.audit_results = {}
        self.security_validator = SecurityValidator()

    def audit_api_security(
        self, endpoints: List[Dict[str, Any]], base_url: str
    ) -> ValidationResult:
        """Perform comprehensive security audit of API."""
        result = ValidationResult()

        logger.info(f"Starting security audit of {len(endpoints)} endpoints")

        for endpoint in endpoints:
            endpoint_result = self._audit_endpoint_security(endpoint, base_url)
            result = result.merge(endpoint_result)

        # Generate security score
        security_score = self._calculate_security_score(result)
        result.details["security_score"] = security_score

        return result

    def _audit_endpoint_security(
        self, endpoint: Dict[str, Any], base_url: str
    ) -> ValidationResult:
        """Audit security of individual endpoint."""
        result = ValidationResult()

        endpoint_path = endpoint.get("path", "")
        method = endpoint.get("method", "GET")

        # Check endpoint path for security issues
        path_result = self._audit_endpoint_path(endpoint_path)
        result = result.merge(path_result)

        # Check for sensitive data in URLs
        if any(
            sensitive in endpoint_path.lower()
            for sensitive in ["password", "secret", "key"]
        ):
            result.add_error(f"Sensitive data in URL path: {endpoint_path}")

        # Check HTTP methods
        if method.upper() in ["GET"] and "password" in endpoint_path.lower():
            result.add_error(f"Sensitive operation using GET method: {endpoint_path}")

        return result

    def _audit_endpoint_path(self, path: str) -> ValidationResult:
        """Audit endpoint path for security issues."""
        result = ValidationResult()

        # Check for path traversal vulnerabilities
        if "../" in path or ".." in path:
            result.add_error("Potential path traversal vulnerability in endpoint")

        # Check for admin/debug endpoints
        admin_patterns = ["admin", "debug", "test", "dev", "internal"]
        if any(pattern in path.lower() for pattern in admin_patterns):
            result.add_warning(f"Endpoint appears to be administrative: {path}")

        # Check for version in path
        if re.search(r"/v\d+/", path):
            result.add_warning("API version in path may aid in targeted attacks")

        return result

    def _calculate_security_score(self, result: ValidationResult) -> Dict[str, Any]:
        """Calculate overall security score based on validation results."""
        total_issues = len(result.errors) + len(result.warnings)
        critical_issues = len(result.errors)

        # Base score
        base_score = 100

        # Deduct points for issues
        score = base_score - (critical_issues * 10) - (len(result.warnings) * 2)
        score = max(0, score)  # Don't go below 0

        # Determine rating
        if score >= 90:
            rating = "Excellent"
        elif score >= 80:
            rating = "Good"
        elif score >= 70:
            rating = "Fair"
        elif score >= 60:
            rating = "Poor"
        else:
            rating = "Critical"

        return {
            "score": score,
            "rating": rating,
            "total_issues": total_issues,
            "critical_issues": critical_issues,
            "warnings": len(result.warnings),
        }
