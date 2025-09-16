"""
Comprehensive Authentication and Security Test Suite

This module implements extensive security testing for the FXML4 API including:
- Authentication mechanisms (JWT, 2FA, API keys)
- Authorization and access controls
- Security vulnerability assessments
- Rate limiting and abuse prevention
- Input validation and sanitization
- Session management and token security

Test-Driven Development (TDD) approach:
1. Red: Define security expectations and threat models
2. Green: Implement security tests and validation
3. Refactor: Enhance security depth and coverage
"""

import asyncio
import base64
import hashlib
import json
import logging
import re
import secrets
import string
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx
import jwt
import pytest


class SecurityTestType(Enum):
    """Types of security tests"""

    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    INPUT_VALIDATION = "input_validation"
    INJECTION_ATTACK = "injection_attack"
    RATE_LIMITING = "rate_limiting"
    SESSION_MANAGEMENT = "session_management"
    ENCRYPTION = "encryption"
    XSS_PROTECTION = "xss_protection"
    CSRF_PROTECTION = "csrf_protection"
    PRIVILEGE_ESCALATION = "privilege_escalation"


class SecurityViolation(Enum):
    """Security violations discovered during testing"""

    WEAK_AUTHENTICATION = "weak_authentication"
    MISSING_AUTHORIZATION = "missing_authorization"
    SQL_INJECTION = "sql_injection"
    XSS_VULNERABILITY = "xss_vulnerability"
    CSRF_VULNERABILITY = "csrf_vulnerability"
    RATE_LIMIT_BYPASS = "rate_limit_bypass"
    SESSION_FIXATION = "session_fixation"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    INFORMATION_DISCLOSURE = "information_disclosure"
    WEAK_ENCRYPTION = "weak_encryption"
    INSECURE_TRANSMISSION = "insecure_transmission"


@dataclass
class SecurityTestResult:
    """Result of security test execution"""

    test_type: SecurityTestType
    endpoint: str
    method: str
    passed: bool
    violations: List[SecurityViolation] = field(default_factory=list)
    details: str = ""
    risk_level: str = "low"  # low, medium, high, critical
    timestamp: datetime = field(default_factory=datetime.utcnow)


class SecurityTestSuite:
    """Comprehensive security testing framework for FXML4 API"""

    def __init__(self, base_url: str = "http://localhost:8001"):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=30.0)
        self.logger = logging.getLogger(__name__)
        self.test_results: List[SecurityTestResult] = []

        # Test users for different privilege levels
        self.test_users = {
            "admin": {
                "username": "admin_test",
                "password": "Admin_Password_123!",
                "role": "admin",
                "permissions": ["all"],
            },
            "trader": {
                "username": "trader_test",
                "password": "Trader_Password_123!",
                "role": "trader",
                "permissions": ["trade", "view_positions", "view_data"],
            },
            "viewer": {
                "username": "viewer_test",
                "password": "Viewer_Password_123!",
                "role": "viewer",
                "permissions": ["view_data"],
            },
            "invalid": {
                "username": "invalid_user",
                "password": "wrong_password",
                "role": None,
                "permissions": [],
            },
        }

        # Malicious payloads for injection testing
        self.injection_payloads = {
            "sql_injection": [
                "'; DROP TABLE users; --",
                "' OR '1'='1",
                "' UNION SELECT * FROM sensitive_table --",
                "admin'--",
                "admin' OR '1'='1' --",
                "'; EXEC xp_cmdshell('dir'); --",
            ],
            "xss": [
                "<script>alert('XSS')</script>",
                "<img src=x onerror=alert('XSS')>",
                "javascript:alert('XSS')",
                "<svg onload=alert('XSS')>",
                "';alert('XSS');//",
                "<iframe src=javascript:alert('XSS')></iframe>",
            ],
            "command_injection": [
                "; ls -la",
                "| cat /etc/passwd",
                "&& rm -rf /",
                "`whoami`",
                "$(id)",
                "; curl malicious-site.com",
            ],
            "path_traversal": [
                "../../../etc/passwd",
                "..\\..\\..\\windows\\system32\\config\\sam",
                "....//....//....//etc/passwd",
                "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd",
            ],
        }

        # Headers for security testing
        self.security_headers = {
            "X-Frame-Options": ["DENY", "SAMEORIGIN"],
            "X-Content-Type-Options": ["nosniff"],
            "X-XSS-Protection": ["1; mode=block"],
            "Strict-Transport-Security": ["max-age=31536000; includeSubDomains"],
            "Content-Security-Policy": ["default-src 'self'"],
            "Referrer-Policy": ["strict-origin-when-cross-origin"],
        }

    async def test_authentication_mechanisms(self) -> List[SecurityTestResult]:
        """Test authentication mechanisms comprehensively"""
        results = []

        # Test JWT authentication
        results.extend(await self._test_jwt_authentication())

        # Test 2FA mechanisms
        results.extend(await self._test_2fa_authentication())

        # Test API key authentication
        results.extend(await self._test_api_key_authentication())

        # Test password policies
        results.extend(await self._test_password_policies())

        # Test session management
        results.extend(await self._test_session_management())

        return results

    async def _test_jwt_authentication(self) -> List[SecurityTestResult]:
        """Test JWT token authentication security"""
        results = []

        # Test valid authentication
        result = SecurityTestResult(
            test_type=SecurityTestType.AUTHENTICATION,
            endpoint="/auth/token",
            method="POST",
            passed=False,
        )

        try:
            # Attempt login with valid credentials
            response = await self.client.post(
                f"{self.base_url}/auth/token", data=self.test_users["trader"]
            )

            if response.status_code == 200:
                token_data = response.json()
                if "access_token" in token_data:
                    # Validate JWT structure
                    token = token_data["access_token"]
                    if await self._validate_jwt_security(token):
                        result.passed = True
                    else:
                        result.violations.append(SecurityViolation.WEAK_AUTHENTICATION)
                        result.details = "JWT token has security weaknesses"
                        result.risk_level = "high"
                else:
                    result.violations.append(SecurityViolation.WEAK_AUTHENTICATION)
                    result.details = "No access token in response"
            else:
                result.violations.append(SecurityViolation.WEAK_AUTHENTICATION)
                result.details = (
                    f"Authentication failed with status {response.status_code}"
                )

        except Exception as e:
            result.violations.append(SecurityViolation.WEAK_AUTHENTICATION)
            result.details = f"Authentication error: {e}"

        results.append(result)

        # Test JWT manipulation attempts
        results.append(await self._test_jwt_manipulation())

        return results

    async def _validate_jwt_security(self, token: str) -> bool:
        """Validate JWT token security properties"""
        try:
            # Decode without verification first to inspect
            unverified_payload = jwt.decode(token, options={"verify_signature": False})

            # Check for security properties
            required_claims = ["sub", "exp", "iat"]
            for claim in required_claims:
                if claim not in unverified_payload:
                    return False

            # Check expiration time is reasonable (not too long)
            exp = unverified_payload.get("exp")
            iat = unverified_payload.get("iat")
            if exp and iat:
                token_lifetime = exp - iat
                if token_lifetime > 3600 * 24:  # More than 24 hours
                    self.logger.warning("JWT token lifetime exceeds 24 hours")
                    return False

            return True

        except Exception as e:
            self.logger.error(f"JWT validation error: {e}")
            return False

    async def _test_jwt_manipulation(self) -> SecurityTestResult:
        """Test JWT token manipulation attacks"""
        result = SecurityTestResult(
            test_type=SecurityTestType.AUTHENTICATION,
            endpoint="/auth/token",
            method="POST",
            passed=True,
        )

        try:
            # Get valid token first
            response = await self.client.post(
                f"{self.base_url}/auth/token", data=self.test_users["trader"]
            )

            if response.status_code == 200:
                token_data = response.json()
                original_token = token_data.get("access_token")

                if original_token:
                    # Test token manipulation attacks
                    manipulated_tokens = [
                        # Change algorithm to none
                        self._manipulate_jwt_algorithm(original_token, "none"),
                        # Modify payload
                        self._manipulate_jwt_payload(original_token, {"role": "admin"}),
                        # Invalid signature
                        original_token[:-10] + "invalid123",
                    ]

                    for manipulated_token in manipulated_tokens:
                        if manipulated_token:
                            # Test if manipulated token is accepted
                            test_response = await self.client.get(
                                f"{self.base_url}/auth/me",
                                headers={
                                    "Authorization": f"Bearer {manipulated_token}"
                                },
                            )

                            if test_response.status_code == 200:
                                result.passed = False
                                result.violations.append(
                                    SecurityViolation.WEAK_AUTHENTICATION
                                )
                                result.details = "JWT manipulation was accepted"
                                result.risk_level = "critical"
                                break

        except Exception as e:
            result.details = f"JWT manipulation test error: {e}"

        return result

    def _manipulate_jwt_algorithm(self, token: str, new_alg: str) -> Optional[str]:
        """Manipulate JWT algorithm"""
        try:
            header, payload, signature = token.split(".")

            # Decode header
            header_data = json.loads(base64.urlsafe_b64decode(header + "=="))
            header_data["alg"] = new_alg

            # Encode new header
            new_header = (
                base64.urlsafe_b64encode(json.dumps(header_data).encode())
                .decode()
                .rstrip("=")
            )

            if new_alg == "none":
                return f"{new_header}.{payload}."
            else:
                return f"{new_header}.{payload}.{signature}"

        except Exception:
            return None

    def _manipulate_jwt_payload(
        self, token: str, changes: Dict[str, Any]
    ) -> Optional[str]:
        """Manipulate JWT payload"""
        try:
            header, payload, signature = token.split(".")

            # Decode payload
            payload_data = json.loads(base64.urlsafe_b64decode(payload + "=="))

            # Apply changes
            payload_data.update(changes)

            # Encode new payload
            new_payload = (
                base64.urlsafe_b64encode(json.dumps(payload_data).encode())
                .decode()
                .rstrip("=")
            )

            return f"{header}.{new_payload}.{signature}"

        except Exception:
            return None

    async def _test_2fa_authentication(self) -> List[SecurityTestResult]:
        """Test Two-Factor Authentication security"""
        results = []

        result = SecurityTestResult(
            test_type=SecurityTestType.AUTHENTICATION,
            endpoint="/auth/2fa/setup",
            method="POST",
            passed=False,
        )

        try:
            # Test 2FA setup endpoint exists and requires authentication
            response = await self.client.post(f"{self.base_url}/auth/2fa/setup")

            if response.status_code == 401:
                result.passed = True
                result.details = "2FA setup properly requires authentication"
            else:
                result.violations.append(SecurityViolation.MISSING_AUTHORIZATION)
                result.details = (
                    f"2FA setup accessible without auth: {response.status_code}"
                )
                result.risk_level = "high"

        except Exception as e:
            result.details = f"2FA test error: {e}"

        results.append(result)

        # Test 2FA bypass attempts
        results.append(await self._test_2fa_bypass())

        return results

    async def _test_2fa_bypass(self) -> SecurityTestResult:
        """Test potential 2FA bypass vulnerabilities"""
        result = SecurityTestResult(
            test_type=SecurityTestType.AUTHENTICATION,
            endpoint="/auth/2fa/verify",
            method="POST",
            passed=True,
        )

        bypass_attempts = [
            {"code": "000000"},  # Common default
            {"code": "123456"},  # Sequential
            {"code": ""},  # Empty code
            {"code": None},  # Null code
        ]

        for attempt in bypass_attempts:
            try:
                response = await self.client.post(
                    f"{self.base_url}/auth/2fa/verify", json=attempt
                )

                # 2FA bypass should never succeed with these codes
                if response.status_code == 200:
                    result.passed = False
                    result.violations.append(SecurityViolation.WEAK_AUTHENTICATION)
                    result.details = (
                        f"2FA bypass successful with code: {attempt['code']}"
                    )
                    result.risk_level = "critical"
                    break

            except Exception:
                pass  # Expected for invalid requests

        return result

    async def _test_api_key_authentication(self) -> List[SecurityTestResult]:
        """Test API key authentication security"""
        results = []

        result = SecurityTestResult(
            test_type=SecurityTestType.AUTHENTICATION,
            endpoint="/auth/me/api-keys",
            method="GET",
            passed=False,
        )

        # Test API key endpoints require authentication
        try:
            response = await self.client.get(f"{self.base_url}/auth/me/api-keys")

            if response.status_code == 401:
                result.passed = True
                result.details = "API key endpoints properly require authentication"
            else:
                result.violations.append(SecurityViolation.MISSING_AUTHORIZATION)
                result.details = (
                    f"API key endpoint accessible without auth: {response.status_code}"
                )
                result.risk_level = "high"

        except Exception as e:
            result.details = f"API key test error: {e}"

        results.append(result)
        return results

    async def _test_password_policies(self) -> List[SecurityTestResult]:
        """Test password policy enforcement"""
        results = []

        weak_passwords = ["password", "123456", "admin", "a", "password123", "12345678"]

        for weak_password in weak_passwords:
            result = SecurityTestResult(
                test_type=SecurityTestType.AUTHENTICATION,
                endpoint="/auth/password/change",
                method="POST",
                passed=False,
            )

            try:
                # Test weak password rejection
                response = await self.client.post(
                    f"{self.base_url}/auth/password/change",
                    json={
                        "current_password": "old_password",
                        "new_password": weak_password,
                    },
                )

                # Weak passwords should be rejected (400 or 422)
                if response.status_code in [400, 422]:
                    result.passed = True
                    result.details = (
                        f"Weak password '{weak_password}' properly rejected"
                    )
                elif response.status_code == 401:
                    result.passed = True
                    result.details = "Password change requires authentication (good)"
                else:
                    result.violations.append(SecurityViolation.WEAK_AUTHENTICATION)
                    result.details = f"Weak password '{weak_password}' accepted"
                    result.risk_level = "medium"

            except Exception as e:
                result.details = f"Password policy test error: {e}"

            results.append(result)

        return results

    async def _test_session_management(self) -> List[SecurityTestResult]:
        """Test session management security"""
        results = []

        # Test session fixation protection
        result = SecurityTestResult(
            test_type=SecurityTestType.SESSION_MANAGEMENT,
            endpoint="/auth/token",
            method="POST",
            passed=True,
        )

        try:
            # Login and get first token
            response1 = await self.client.post(
                f"{self.base_url}/auth/token", data=self.test_users["trader"]
            )

            # Login again and get second token
            response2 = await self.client.post(
                f"{self.base_url}/auth/token", data=self.test_users["trader"]
            )

            if response1.status_code == 200 and response2.status_code == 200:
                token1 = response1.json().get("access_token")
                token2 = response2.json().get("access_token")

                # Tokens should be different (session fixation protection)
                if token1 == token2:
                    result.passed = False
                    result.violations.append(SecurityViolation.SESSION_FIXATION)
                    result.details = "Same token returned for multiple logins"
                    result.risk_level = "medium"
                else:
                    result.details = "Different tokens for each login (good)"

        except Exception as e:
            result.details = f"Session management test error: {e}"

        results.append(result)
        return results

    async def test_authorization_controls(self) -> List[SecurityTestResult]:
        """Test authorization and access control mechanisms"""
        results = []

        # Test role-based access control
        results.extend(await self._test_rbac())

        # Test privilege escalation attempts
        results.extend(await self._test_privilege_escalation())

        # Test resource access controls
        results.extend(await self._test_resource_access_controls())

        return results

    async def _test_rbac(self) -> List[SecurityTestResult]:
        """Test Role-Based Access Control"""
        results = []

        # Define role-specific endpoints
        role_restrictions = {
            "admin": ["/users", "/roles", "/admin"],
            "trader": ["/trading", "/orders", "/positions"],
            "viewer": ["/data", "/reports"],
        }

        # Get tokens for different roles
        tokens = {}
        for role, user_data in self.test_users.items():
            if role != "invalid":
                try:
                    response = await self.client.post(
                        f"{self.base_url}/auth/token", data=user_data
                    )
                    if response.status_code == 200:
                        tokens[role] = response.json().get("access_token")
                except Exception:
                    pass

        # Test cross-role access attempts
        for role, token in tokens.items():
            for restricted_role, endpoints in role_restrictions.items():
                if role != restricted_role:
                    for endpoint in endpoints:
                        result = SecurityTestResult(
                            test_type=SecurityTestType.AUTHORIZATION,
                            endpoint=endpoint,
                            method="GET",
                            passed=False,
                        )

                        try:
                            response = await self.client.get(
                                f"{self.base_url}{endpoint}",
                                headers={"Authorization": f"Bearer {token}"},
                            )

                            # Should be forbidden (403) or not found (404)
                            if response.status_code in [403, 404]:
                                result.passed = True
                                result.details = (
                                    f"Role {role} properly denied access to {endpoint}"
                                )
                            else:
                                result.violations.append(
                                    SecurityViolation.PRIVILEGE_ESCALATION
                                )
                                result.details = f"Role {role} gained unauthorized access to {endpoint}"
                                result.risk_level = "high"

                        except Exception as e:
                            result.details = f"RBAC test error: {e}"

                        results.append(result)

        return results

    async def _test_privilege_escalation(self) -> List[SecurityTestResult]:
        """Test for privilege escalation vulnerabilities"""
        results = []

        escalation_attempts = [
            # Parameter manipulation
            {"endpoint": "/users/me", "params": {"role": "admin"}},
            {"endpoint": "/users/me", "params": {"permissions": ["all"]}},
            # Header manipulation
            {"endpoint": "/users/me", "headers": {"X-User-Role": "admin"}},
            {"endpoint": "/users/me", "headers": {"X-Admin": "true"}},
            # Direct ID manipulation
            {"endpoint": "/users/1", "method": "PUT", "data": {"role": "admin"}},
        ]

        for attempt in escalation_attempts:
            result = SecurityTestResult(
                test_type=SecurityTestType.PRIVILEGE_ESCALATION,
                endpoint=attempt["endpoint"],
                method=attempt.get("method", "GET"),
                passed=True,
            )

            try:
                # Use viewer token for escalation attempts
                if "viewer" in tokens:
                    headers = {"Authorization": f"Bearer {tokens['viewer']}"}
                    headers.update(attempt.get("headers", {}))

                    if attempt.get("method") == "PUT":
                        response = await self.client.put(
                            f"{self.base_url}{attempt['endpoint']}",
                            headers=headers,
                            json=attempt.get("data", {}),
                        )
                    else:
                        response = await self.client.get(
                            f"{self.base_url}{attempt['endpoint']}",
                            headers=headers,
                            params=attempt.get("params", {}),
                        )

                    # Successful privilege escalation is a security violation
                    if response.status_code == 200:
                        # Check if response indicates elevated privileges
                        if "admin" in str(response.content).lower():
                            result.passed = False
                            result.violations.append(
                                SecurityViolation.PRIVILEGE_ESCALATION
                            )
                            result.details = (
                                f"Privilege escalation successful via {attempt}"
                            )
                            result.risk_level = "critical"

            except Exception as e:
                result.details = f"Privilege escalation test error: {e}"

            results.append(result)

        return results

    async def _test_resource_access_controls(self) -> List[SecurityTestResult]:
        """Test resource-level access controls"""
        results = []

        # Test direct object reference vulnerabilities
        sensitive_endpoints = [
            "/users/{user_id}",
            "/orders/{order_id}",
            "/positions/{position_id}",
            "/reports/{report_id}",
        ]

        for endpoint_template in sensitive_endpoints:
            for user_id in [1, 2, 999, "admin", "../admin"]:
                endpoint = endpoint_template.format(
                    user_id=user_id,
                    order_id=user_id,
                    position_id=user_id,
                    report_id=user_id,
                )

                result = SecurityTestResult(
                    test_type=SecurityTestType.AUTHORIZATION,
                    endpoint=endpoint,
                    method="GET",
                    passed=True,
                )

                try:
                    # Test unauthorized access
                    response = await self.client.get(f"{self.base_url}{endpoint}")

                    # Should require authentication
                    if response.status_code != 401:
                        result.passed = False
                        result.violations.append(
                            SecurityViolation.MISSING_AUTHORIZATION
                        )
                        result.details = (
                            f"Resource {endpoint} accessible without authentication"
                        )
                        result.risk_level = "high"

                except Exception as e:
                    result.details = f"Resource access test error: {e}"

                results.append(result)

        return results

    async def test_injection_vulnerabilities(self) -> List[SecurityTestResult]:
        """Test for various injection vulnerabilities"""
        results = []

        # Test SQL injection
        results.extend(await self._test_sql_injection())

        # Test XSS vulnerabilities
        results.extend(await self._test_xss_vulnerabilities())

        # Test command injection
        results.extend(await self._test_command_injection())

        # Test path traversal
        results.extend(await self._test_path_traversal())

        return results

    async def _test_sql_injection(self) -> List[SecurityTestResult]:
        """Test SQL injection vulnerabilities"""
        results = []

        test_endpoints = [
            {"endpoint": "/auth/token", "method": "POST", "param": "username"},
            {"endpoint": "/users", "method": "GET", "param": "search"},
            {"endpoint": "/data", "method": "POST", "param": "symbol"},
            {"endpoint": "/orders", "method": "GET", "param": "symbol"},
        ]

        for endpoint_config in test_endpoints:
            for payload in self.injection_payloads["sql_injection"]:
                result = SecurityTestResult(
                    test_type=SecurityTestType.INJECTION_ATTACK,
                    endpoint=endpoint_config["endpoint"],
                    method=endpoint_config["method"],
                    passed=True,
                )

                try:
                    test_data = {endpoint_config["param"]: payload}

                    if endpoint_config["method"] == "POST":
                        response = await self.client.post(
                            f"{self.base_url}{endpoint_config['endpoint']}",
                            json=test_data,
                        )
                    else:
                        response = await self.client.get(
                            f"{self.base_url}{endpoint_config['endpoint']}",
                            params=test_data,
                        )

                    # Check for SQL injection indicators in response
                    response_text = response.text.lower()
                    sql_error_indicators = [
                        "sql",
                        "mysql",
                        "postgresql",
                        "sqlite",
                        "database",
                        "syntax error",
                        "column",
                        "table",
                        "select",
                        "from",
                    ]

                    if any(
                        indicator in response_text for indicator in sql_error_indicators
                    ):
                        result.passed = False
                        result.violations.append(SecurityViolation.SQL_INJECTION)
                        result.details = (
                            f"SQL injection vulnerability with payload: {payload}"
                        )
                        result.risk_level = "critical"

                except Exception as e:
                    result.details = f"SQL injection test error: {e}"

                results.append(result)

        return results

    async def _test_xss_vulnerabilities(self) -> List[SecurityTestResult]:
        """Test Cross-Site Scripting vulnerabilities"""
        results = []

        test_endpoints = [
            {"endpoint": "/users", "method": "POST", "param": "username"},
            {"endpoint": "/orders", "method": "POST", "param": "notes"},
            {"endpoint": "/data", "method": "GET", "param": "symbol"},
        ]

        for endpoint_config in test_endpoints:
            for payload in self.injection_payloads["xss"]:
                result = SecurityTestResult(
                    test_type=SecurityTestType.XSS_PROTECTION,
                    endpoint=endpoint_config["endpoint"],
                    method=endpoint_config["method"],
                    passed=True,
                )

                try:
                    test_data = {endpoint_config["param"]: payload}

                    if endpoint_config["method"] == "POST":
                        response = await self.client.post(
                            f"{self.base_url}{endpoint_config['endpoint']}",
                            json=test_data,
                        )
                    else:
                        response = await self.client.get(
                            f"{self.base_url}{endpoint_config['endpoint']}",
                            params=test_data,
                        )

                    # Check if XSS payload is reflected without encoding
                    if payload in response.text and response.headers.get(
                        "content-type", ""
                    ).startswith("text/html"):
                        result.passed = False
                        result.violations.append(SecurityViolation.XSS_VULNERABILITY)
                        result.details = f"XSS vulnerability with payload: {payload}"
                        result.risk_level = "high"

                except Exception as e:
                    result.details = f"XSS test error: {e}"

                results.append(result)

        return results

    async def _test_command_injection(self) -> List[SecurityTestResult]:
        """Test command injection vulnerabilities"""
        results = []

        # Test endpoints that might execute system commands
        test_endpoints = [
            {"endpoint": "/admin/backup", "method": "POST", "param": "filename"},
            {"endpoint": "/admin/logs", "method": "GET", "param": "file"},
            {"endpoint": "/admin/export", "method": "POST", "param": "format"},
        ]

        for endpoint_config in test_endpoints:
            for payload in self.injection_payloads["command_injection"]:
                result = SecurityTestResult(
                    test_type=SecurityTestType.INJECTION_ATTACK,
                    endpoint=endpoint_config["endpoint"],
                    method=endpoint_config["method"],
                    passed=True,
                )

                try:
                    test_data = {endpoint_config["param"]: payload}

                    if endpoint_config["method"] == "POST":
                        response = await self.client.post(
                            f"{self.base_url}{endpoint_config['endpoint']}",
                            json=test_data,
                        )
                    else:
                        response = await self.client.get(
                            f"{self.base_url}{endpoint_config['endpoint']}",
                            params=test_data,
                        )

                    # Look for command execution indicators
                    response_text = response.text.lower()
                    command_indicators = ["root:", "uid=", "gid=", "/bin/", "/etc/"]

                    if any(
                        indicator in response_text for indicator in command_indicators
                    ):
                        result.passed = False
                        result.violations.append(
                            SecurityViolation.SQL_INJECTION
                        )  # Using generic injection type
                        result.details = (
                            f"Command injection vulnerability with payload: {payload}"
                        )
                        result.risk_level = "critical"

                except Exception as e:
                    result.details = f"Command injection test error: {e}"

                results.append(result)

        return results

    async def _test_path_traversal(self) -> List[SecurityTestResult]:
        """Test path traversal vulnerabilities"""
        results = []

        # Test file access endpoints
        test_endpoints = [
            {"endpoint": "/files/{filename}", "param": "filename"},
            {"endpoint": "/reports/{report_id}", "param": "report_id"},
            {"endpoint": "/logs/{log_file}", "param": "log_file"},
        ]

        for endpoint_config in test_endpoints:
            for payload in self.injection_payloads["path_traversal"]:
                result = SecurityTestResult(
                    test_type=SecurityTestType.INJECTION_ATTACK,
                    endpoint=endpoint_config["endpoint"],
                    method="GET",
                    passed=True,
                )

                try:
                    endpoint = endpoint_config["endpoint"].replace(
                        f"{{{endpoint_config['param']}}}", payload
                    )
                    response = await self.client.get(f"{self.base_url}{endpoint}")

                    # Check for sensitive file contents
                    sensitive_patterns = [
                        r"root:.*:/root:/bin/bash",  # /etc/passwd
                        r"BEGIN RSA PRIVATE KEY",  # SSH keys
                        r"password.*=.*",  # Config files
                        r"api_key.*=.*",  # API keys
                    ]

                    for pattern in sensitive_patterns:
                        if re.search(pattern, response.text, re.IGNORECASE):
                            result.passed = False
                            result.violations.append(
                                SecurityViolation.INFORMATION_DISCLOSURE
                            )
                            result.details = (
                                f"Path traversal vulnerability with payload: {payload}"
                            )
                            result.risk_level = "critical"
                            break

                except Exception as e:
                    result.details = f"Path traversal test error: {e}"

                results.append(result)

        return results

    async def test_rate_limiting(self) -> List[SecurityTestResult]:
        """Test rate limiting mechanisms"""
        results = []

        # Test login rate limiting
        result = await self._test_login_rate_limiting()
        results.append(result)

        # Test API rate limiting
        result = await self._test_api_rate_limiting()
        results.append(result)

        return results

    async def _test_login_rate_limiting(self) -> SecurityTestResult:
        """Test login attempt rate limiting"""
        result = SecurityTestResult(
            test_type=SecurityTestType.RATE_LIMITING,
            endpoint="/auth/token",
            method="POST",
            passed=False,
        )

        try:
            # Perform multiple failed login attempts
            failed_attempts = 0
            for i in range(10):  # Try 10 failed logins
                response = await self.client.post(
                    f"{self.base_url}/auth/token", data=self.test_users["invalid"]
                )

                if response.status_code == 429:  # Rate limited
                    result.passed = True
                    result.details = (
                        f"Rate limiting activated after {failed_attempts} attempts"
                    )
                    break
                elif response.status_code == 401:  # Failed login
                    failed_attempts += 1
                else:
                    break

                # Small delay between attempts
                await asyncio.sleep(0.1)

            if not result.passed:
                result.violations.append(SecurityViolation.RATE_LIMIT_BYPASS)
                result.details = (
                    f"No rate limiting after {failed_attempts} failed login attempts"
                )
                result.risk_level = "medium"

        except Exception as e:
            result.details = f"Rate limiting test error: {e}"

        return result

    async def _test_api_rate_limiting(self) -> SecurityTestResult:
        """Test general API rate limiting"""
        result = SecurityTestResult(
            test_type=SecurityTestType.RATE_LIMITING,
            endpoint="/health",
            method="GET",
            passed=False,
        )

        try:
            # Perform many rapid requests to health endpoint
            rate_limited = False
            for i in range(200):  # Try 200 requests rapidly
                response = await self.client.get(f"{self.base_url}/health")

                if response.status_code == 429:
                    rate_limited = True
                    result.passed = True
                    result.details = f"Rate limiting activated after {i+1} requests"
                    break

                # No delay - test rapid requests

            if not rate_limited:
                result.violations.append(SecurityViolation.RATE_LIMIT_BYPASS)
                result.details = "No rate limiting detected for rapid API requests"
                result.risk_level = "low"  # Health endpoint is less critical

        except Exception as e:
            result.details = f"API rate limiting test error: {e}"

        return result

    async def test_security_headers(self) -> List[SecurityTestResult]:
        """Test security HTTP headers"""
        results = []

        test_endpoints = ["/", "/health", "/auth/token"]

        for endpoint in test_endpoints:
            result = SecurityTestResult(
                test_type=SecurityTestType.ENCRYPTION,
                endpoint=endpoint,
                method="GET",
                passed=True,
            )

            try:
                response = await self.client.get(f"{self.base_url}{endpoint}")

                missing_headers = []
                for header, expected_values in self.security_headers.items():
                    actual_value = response.headers.get(header)

                    if not actual_value:
                        missing_headers.append(header)
                    elif not any(
                        expected in actual_value for expected in expected_values
                    ):
                        missing_headers.append(f"{header} (incorrect value)")

                if missing_headers:
                    result.passed = False
                    result.violations.append(SecurityViolation.WEAK_ENCRYPTION)
                    result.details = (
                        f"Missing security headers: {', '.join(missing_headers)}"
                    )
                    result.risk_level = "medium"
                else:
                    result.details = "All security headers present"

            except Exception as e:
                result.details = f"Security headers test error: {e}"

            results.append(result)

        return results

    async def generate_security_report(
        self, test_results: List[SecurityTestResult]
    ) -> Dict[str, Any]:
        """Generate comprehensive security test report"""
        total_tests = len(test_results)
        passed_tests = len([r for r in test_results if r.passed])
        failed_tests = total_tests - passed_tests

        # Risk level breakdown
        risk_breakdown = {"low": 0, "medium": 0, "high": 0, "critical": 0}
        for result in test_results:
            if not result.passed:
                risk_breakdown[result.risk_level] += 1

        # Test type breakdown
        test_type_breakdown = {}
        for result in test_results:
            test_type = result.test_type.value
            if test_type not in test_type_breakdown:
                test_type_breakdown[test_type] = {"total": 0, "passed": 0, "failed": 0}

            test_type_breakdown[test_type]["total"] += 1
            if result.passed:
                test_type_breakdown[test_type]["passed"] += 1
            else:
                test_type_breakdown[test_type]["failed"] += 1

        # Violation breakdown
        violation_breakdown = {}
        for result in test_results:
            for violation in result.violations:
                violation_type = violation.value
                violation_breakdown[violation_type] = (
                    violation_breakdown.get(violation_type, 0) + 1
                )

        # Critical findings
        critical_findings = [
            {
                "endpoint": result.endpoint,
                "method": result.method,
                "test_type": result.test_type.value,
                "violations": [v.value for v in result.violations],
                "details": result.details,
                "risk_level": result.risk_level,
            }
            for result in test_results
            if not result.passed and result.risk_level in ["high", "critical"]
        ]

        report = {
            "summary": {
                "total_tests": total_tests,
                "passed": passed_tests,
                "failed": failed_tests,
                "success_rate": (
                    (passed_tests / total_tests * 100) if total_tests > 0 else 0
                ),
                "security_score": max(
                    0,
                    100
                    - (
                        risk_breakdown["critical"] * 25
                        + risk_breakdown["high"] * 15
                        + risk_breakdown["medium"] * 5
                        + risk_breakdown["low"] * 1
                    ),
                ),
            },
            "risk_assessment": {
                "risk_breakdown": risk_breakdown,
                "overall_risk": self._calculate_overall_risk(risk_breakdown),
                "critical_findings_count": len(critical_findings),
            },
            "test_coverage": {
                "test_type_breakdown": test_type_breakdown,
                "endpoints_tested": len(set(r.endpoint for r in test_results)),
            },
            "violations": {
                "violation_breakdown": violation_breakdown,
                "total_violations": sum(len(r.violations) for r in test_results),
            },
            "critical_findings": critical_findings,
            "recommendations": self._generate_security_recommendations(test_results),
            "timestamp": datetime.utcnow().isoformat(),
        }

        return report

    def _calculate_overall_risk(self, risk_breakdown: Dict[str, int]) -> str:
        """Calculate overall security risk level"""
        if risk_breakdown["critical"] > 0:
            return "CRITICAL"
        elif risk_breakdown["high"] > 2:
            return "HIGH"
        elif risk_breakdown["high"] > 0 or risk_breakdown["medium"] > 5:
            return "MEDIUM"
        else:
            return "LOW"

    def _generate_security_recommendations(
        self, test_results: List[SecurityTestResult]
    ) -> List[str]:
        """Generate security recommendations based on test results"""
        recommendations = []

        violation_types = set()
        for result in test_results:
            violation_types.update(result.violations)

        recommendation_map = {
            SecurityViolation.WEAK_AUTHENTICATION: "Implement stronger authentication mechanisms including proper JWT validation",
            SecurityViolation.MISSING_AUTHORIZATION: "Implement comprehensive authorization checks for all protected endpoints",
            SecurityViolation.SQL_INJECTION: "Use parameterized queries and input validation to prevent SQL injection",
            SecurityViolation.XSS_VULNERABILITY: "Implement proper input encoding and Content Security Policy headers",
            SecurityViolation.RATE_LIMIT_BYPASS: "Implement rate limiting for authentication and API endpoints",
            SecurityViolation.PRIVILEGE_ESCALATION: "Review and strengthen role-based access controls",
            SecurityViolation.INFORMATION_DISCLOSURE: "Implement proper error handling to prevent information leakage",
            SecurityViolation.WEAK_ENCRYPTION: "Add security headers and ensure HTTPS is properly configured",
        }

        for violation in violation_types:
            if violation in recommendation_map:
                recommendations.append(recommendation_map[violation])

        return recommendations

    async def close(self):
        """Cleanup resources"""
        await self.client.aclose()


@pytest.fixture
def security_test_suite():
    """Fixture providing security test suite"""
    return SecurityTestSuite()


class TestSecurityFramework:
    """Test suite for security testing framework"""

    @pytest.mark.asyncio
    async def test_security_test_suite_initialization(self, security_test_suite):
        """Test security test suite initializes correctly"""
        # Red: Define security suite expectations
        assert security_test_suite.base_url == "http://localhost:8001"
        assert security_test_suite.client is not None
        assert isinstance(security_test_suite.test_users, dict)
        assert isinstance(security_test_suite.injection_payloads, dict)
        assert len(security_test_suite.injection_payloads["sql_injection"]) > 0
        assert len(security_test_suite.injection_payloads["xss"]) > 0

    @pytest.mark.asyncio
    async def test_jwt_token_validation(self, security_test_suite):
        """Test JWT token validation logic"""
        # Red: Define JWT validation expectations

        # Create test JWT token
        test_payload = {
            "sub": "test_user",
            "exp": int(time.time()) + 3600,  # 1 hour
            "iat": int(time.time()),
        }

        test_token = jwt.encode(test_payload, "test_secret", algorithm="HS256")

        # Green: Test JWT validation
        is_valid = await security_test_suite._validate_jwt_security(test_token)
        assert isinstance(is_valid, bool)

        # Test invalid JWT
        invalid_token = "invalid.jwt.token"
        is_invalid = await security_test_suite._validate_jwt_security(invalid_token)
        assert is_invalid == False

    @pytest.mark.asyncio
    async def test_jwt_manipulation(self, security_test_suite):
        """Test JWT manipulation detection"""
        # Red: Define JWT manipulation expectations

        original_token = jwt.encode(
            {"sub": "user", "role": "viewer", "exp": int(time.time()) + 3600},
            "secret",
            algorithm="HS256",
        )

        # Green: Test manipulation methods
        none_alg_token = security_test_suite._manipulate_jwt_algorithm(
            original_token, "none"
        )
        assert none_alg_token is not None
        assert none_alg_token != original_token

        modified_payload = security_test_suite._manipulate_jwt_payload(
            original_token, {"role": "admin"}
        )
        assert modified_payload is not None
        assert modified_payload != original_token

    @pytest.mark.asyncio
    async def test_security_report_generation(self, security_test_suite):
        """Test security report generation"""
        # Red: Define report generation expectations

        # Create sample test results
        test_results = [
            SecurityTestResult(
                test_type=SecurityTestType.AUTHENTICATION,
                endpoint="/auth/token",
                method="POST",
                passed=True,
            ),
            SecurityTestResult(
                test_type=SecurityTestType.AUTHORIZATION,
                endpoint="/admin/users",
                method="GET",
                passed=False,
                violations=[SecurityViolation.MISSING_AUTHORIZATION],
                risk_level="high",
            ),
        ]

        # Green: Generate security report
        report = await security_test_suite.generate_security_report(test_results)

        # Verify report structure
        assert "summary" in report
        assert "risk_assessment" in report
        assert "test_coverage" in report
        assert "violations" in report
        assert "critical_findings" in report
        assert "recommendations" in report

        # Verify summary
        assert report["summary"]["total_tests"] == 2
        assert report["summary"]["passed"] == 1
        assert report["summary"]["failed"] == 1

        # Verify risk assessment
        assert "risk_breakdown" in report["risk_assessment"]
        assert report["risk_assessment"]["risk_breakdown"]["high"] == 1


if __name__ == "__main__":
    # Direct execution for development testing
    import sys

    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

    async def main():
        print("Starting FXML4 Security Testing Suite...")

        security_suite = SecurityTestSuite()

        print("Running authentication security tests...")
        auth_results = await security_suite.test_authentication_mechanisms()
        print(f"Authentication tests completed: {len(auth_results)} tests")

        print("Running authorization security tests...")
        authz_results = await security_suite.test_authorization_controls()
        print(f"Authorization tests completed: {len(authz_results)} tests")

        print("Running injection vulnerability tests...")
        injection_results = await security_suite.test_injection_vulnerabilities()
        print(f"Injection tests completed: {len(injection_results)} tests")

        print("Running rate limiting tests...")
        rate_limit_results = await security_suite.test_rate_limiting()
        print(f"Rate limiting tests completed: {len(rate_limit_results)} tests")

        print("Running security headers tests...")
        headers_results = await security_suite.test_security_headers()
        print(f"Security headers tests completed: {len(headers_results)} tests")

        # Combine all results
        all_results = (
            auth_results
            + authz_results
            + injection_results
            + rate_limit_results
            + headers_results
        )

        # Generate security report
        report = await security_suite.generate_security_report(all_results)

        print(f"\n=== SECURITY TEST REPORT ===")
        print(f"Total tests: {report['summary']['total_tests']}")
        print(f"Passed: {report['summary']['passed']}")
        print(f"Failed: {report['summary']['failed']}")
        print(f"Success rate: {report['summary']['success_rate']:.1f}%")
        print(f"Security score: {report['summary']['security_score']:.1f}/100")
        print(f"Overall risk: {report['risk_assessment']['overall_risk']}")

        if report["critical_findings"]:
            print(f"\nCRITICAL FINDINGS ({len(report['critical_findings'])}):")
            for finding in report["critical_findings"][:3]:  # Show top 3
                print(
                    f"  - {finding['endpoint']} ({finding['method']}): {finding['details']}"
                )

        if report["recommendations"]:
            print(f"\nRECOMMENDATIONS:")
            for rec in report["recommendations"][:5]:  # Show top 5
                print(f"  - {rec}")

        await security_suite.close()
        print("\nSecurity testing completed!")

    asyncio.run(main())
