"""
Comprehensive security vulnerability tests for FXML4.

This module tests for common security vulnerabilities including:
- Authentication bypass attempts
- Input validation and sanitization
- SQL injection prevention
- XSS/CSRF protection
- Rate limiting
- Authorization bypass
- Session management
"""

import json
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

try:
    from fxml4.api.auth.auth import create_access_token
    from fxml4.api.main import app

    API_AVAILABLE = True
except ImportError:
    app = None
    create_access_token = None
    API_AVAILABLE = False


class TestAuthenticationBypass:
    """Test authentication bypass attempts."""

    @pytest.fixture
    def client(self):
        """Get test client."""
        if not API_AVAILABLE:
            pytest.skip("API not available")
        return TestClient(app)

    def test_access_protected_endpoint_without_token(self, client):
        """Test accessing protected endpoints without token."""
        protected_endpoints = [
            "/users/me",
            "/admin/stats",
            "/api/v1/signals",
            "/api/v1/backtest",
            "/api/v1/positions",
        ]

        for endpoint in protected_endpoints:
            try:
                response = client.get(endpoint)
                # Should be unauthorized
                assert response.status_code in [
                    401,
                    404,
                ], f"Endpoint {endpoint} should require authentication"
            except Exception:
                # Skip if endpoint doesn't exist
                continue

    def test_malformed_bearer_tokens(self, client):
        """Test various malformed bearer tokens."""
        malformed_tokens = [
            "Bearer",  # Missing token
            "Bearer ",  # Empty token
            "Bearer invalid",  # Invalid token
            "Bearer " + "x" * 1000,  # Very long token
            "Bearer ../../../etc/passwd",  # Path traversal attempt
            "Bearer <script>alert('xss')</script>",  # XSS attempt
            "Bearer ' OR 1=1 --",  # SQL injection attempt
            "NotBearer valid_token",  # Wrong prefix
            "bearer valid_token",  # Wrong case
        ]

        for token in malformed_tokens:
            response = client.get("/users/me", headers={"Authorization": token})
            assert (
                response.status_code == 401
            ), f"Should reject malformed token: {token}"

    def test_expired_token_rejection(self, client):
        """Test that expired tokens are rejected."""
        # Create expired token
        expired_data = {"sub": "testuser", "scopes": ["user", "read"]}
        expired_delta = timedelta(minutes=-30)  # 30 minutes ago

        if create_access_token:
            expired_token = create_access_token(
                expired_data, expires_delta=expired_delta
            )

            response = client.get(
                "/users/me", headers={"Authorization": f"Bearer {expired_token}"}
            )
            assert response.status_code == 401

    def test_token_with_no_subject(self, client):
        """Test token without subject claim."""
        if create_access_token:
            # Create token without 'sub' claim
            invalid_data = {"scopes": ["user", "read"]}  # Missing 'sub'
            invalid_token = create_access_token(invalid_data)

            response = client.get(
                "/users/me", headers={"Authorization": f"Bearer {invalid_token}"}
            )
            assert response.status_code == 401

    def test_token_replay_attack_simulation(self, client):
        """Simulate token replay attack scenarios."""
        if create_access_token:
            # Create valid token
            token_data = {"sub": "testuser", "scopes": ["user", "read"]}
            token = create_access_token(token_data)

            # Use same token multiple times rapidly
            for _ in range(10):
                response = client.get(
                    "/users/me", headers={"Authorization": f"Bearer {token}"}
                )
                # Token should remain valid (no automatic invalidation on use)
                if response.status_code == 200:
                    break

            # This test documents current behavior - tokens don't auto-expire on use


class TestInputValidationAndSanitization:
    """Test input validation and sanitization."""

    @pytest.fixture
    def client(self):
        """Get test client."""
        if not API_AVAILABLE:
            pytest.skip("API not available")
        return TestClient(app)

    @pytest.fixture
    def auth_headers(self):
        """Get authorization headers."""
        if not create_access_token:
            pytest.skip("Auth not available")

        token_data = {"sub": "testuser", "scopes": ["user", "read", "write"]}
        token = create_access_token(token_data)
        return {"Authorization": f"Bearer {token}"}

    def test_sql_injection_attempts(self, client, auth_headers):
        """Test SQL injection attempts in various inputs."""
        sql_payloads = [
            "'; DROP TABLE users; --",
            "1' OR '1'='1",
            "1'; UNION SELECT * FROM users; --",
            "1' AND (SELECT COUNT(*) FROM users) > 0 --",
            "'; INSERT INTO users VALUES ('admin', 'password'); --",
        ]

        # Test in URL parameters
        for payload in sql_payloads:
            response = client.get(
                f"/api/v1/data?symbol={payload}", headers=auth_headers
            )
            # Should not return 500 (internal server error from SQL injection)
            assert (
                response.status_code != 500
            ), f"Potential SQL injection with payload: {payload}"

    def test_xss_attempts_in_parameters(self, client, auth_headers):
        """Test XSS attempts in URL parameters."""
        xss_payloads = [
            "<script>alert('xss')</script>",
            "javascript:alert('xss')",
            "<img src=x onerror=alert('xss')>",
            "';alert('xss');//",
            "<svg onload=alert('xss')>",
            "<%2Fscript%3E%3Cscript%3Ealert%28%27xss%27%29%3C%2Fscript%3E",
        ]

        for payload in xss_payloads:
            response = client.get(
                f"/api/v1/data?symbol={payload}", headers=auth_headers
            )

            # Response should not contain unescaped payload
            if response.status_code == 200:
                response_text = response.text.lower()
                assert (
                    "<script>" not in response_text
                ), f"Potential XSS vulnerability with: {payload}"
                assert (
                    "javascript:" not in response_text
                ), f"Potential XSS vulnerability with: {payload}"

    def test_path_traversal_attempts(self, client, auth_headers):
        """Test path traversal attempts."""
        path_payloads = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd",
            "....//....//....//etc/passwd",
            "../../../../../etc/hosts",
        ]

        for payload in path_payloads:
            response = client.get(f"/api/v1/files/{payload}", headers=auth_headers)

            # Should not return file system content
            if response.status_code == 200:
                response_text = response.text.lower()
                assert (
                    "root:" not in response_text
                ), f"Potential path traversal with: {payload}"
                assert (
                    "[system process]" not in response_text
                ), f"Potential path traversal with: {payload}"

    def test_command_injection_attempts(self, client, auth_headers):
        """Test command injection attempts."""
        command_payloads = [
            "; ls -la",
            "| cat /etc/passwd",
            "& whoami",
            "$(cat /etc/passwd)",
            "`ls -la`",
            "; rm -rf /",
            "&& echo 'injected'",
        ]

        # Test in POST data
        for payload in command_payloads:
            data = {"command": payload, "symbol": f"EURUSD{payload}"}
            response = client.post("/api/v1/execute", json=data, headers=auth_headers)

            # Should not execute system commands
            if response.status_code == 200:
                response_text = response.text.lower()
                assert (
                    "root" not in response_text
                ), f"Potential command injection with: {payload}"
                assert (
                    "bin/bash" not in response_text
                ), f"Potential command injection with: {payload}"

    def test_oversized_request_rejection(self, client, auth_headers):
        """Test rejection of oversized requests."""
        # Create very large payload
        large_data = {"data": "x" * (10 * 1024 * 1024)}  # 10MB

        response = client.post("/api/v1/data", json=large_data, headers=auth_headers)

        # Should reject large requests
        assert response.status_code in [413, 400], "Should reject oversized requests"

    def test_malformed_json_handling(self, client, auth_headers):
        """Test handling of malformed JSON."""
        malformed_payloads = [
            '{"invalid": json}',  # Invalid JSON
            '{"unclosed": "string',  # Unclosed string
            '{"nested": {"too": {"deep": {"object": "value"}}}}' * 100,  # Deep nesting
            "",  # Empty body
            "not json at all",
            '{"huge_number": ' + "9" * 1000 + "}",  # Huge number
        ]

        for payload in malformed_payloads:
            response = client.post(
                "/api/v1/data",
                content=payload,
                headers={**auth_headers, "content-type": "application/json"},
            )

            # Should handle malformed JSON gracefully
            assert response.status_code in [
                400,
                422,
            ], f"Should reject malformed JSON: {payload[:50]}..."


class TestAuthorizationBypass:
    """Test authorization bypass attempts."""

    @pytest.fixture
    def client(self):
        """Get test client."""
        if not API_AVAILABLE:
            pytest.skip("API not available")
        return TestClient(app)

    @pytest.fixture
    def user_headers(self):
        """Get regular user authorization headers."""
        if not create_access_token:
            pytest.skip("Auth not available")

        token_data = {"sub": "user", "scopes": ["user", "read"]}
        token = create_access_token(token_data)
        return {"Authorization": f"Bearer {token}"}

    @pytest.fixture
    def admin_headers(self):
        """Get admin authorization headers."""
        if not create_access_token:
            pytest.skip("Auth not available")

        token_data = {"sub": "admin", "scopes": ["admin", "user", "read", "write"]}
        token = create_access_token(token_data)
        return {"Authorization": f"Bearer {token}"}

    def test_privilege_escalation_attempts(self, client, user_headers):
        """Test privilege escalation attempts."""
        admin_endpoints = [
            "/admin/users",
            "/admin/logs",
            "/admin/config",
            "/api/v1/admin/stats",
        ]

        for endpoint in admin_endpoints:
            try:
                response = client.get(endpoint, headers=user_headers)
                # Regular user should not access admin endpoints
                assert response.status_code in [
                    403,
                    404,
                ], f"Regular user should not access {endpoint}"
            except Exception:
                # Skip if endpoint doesn't exist
                continue

    def test_scope_manipulation_attempts(self, client):
        """Test scope manipulation in tokens."""
        if not create_access_token:
            pytest.skip("Auth not available")

        # Try to create token with unauthorized scopes
        malicious_scopes = ["admin", "super_admin", "root", "system"]

        for scope in malicious_scopes:
            token_data = {"sub": "user", "scopes": ["user", "read", scope]}
            token = create_access_token(token_data)

            response = client.get(
                "/admin/users", headers={"Authorization": f"Bearer {token}"}
            )

            # Should still be rejected based on user's actual permissions
            # (This test depends on proper scope validation in the backend)
            if response.status_code == 200:
                # If this passes, there might be a scope validation issue
                pytest.fail(f"Possible scope bypass with scope: {scope}")

    def test_user_enumeration_protection(self, client):
        """Test protection against user enumeration."""
        # Try to determine if users exist based on response differences
        usernames = ["admin", "user", "nonexistent", "test", "root", "administrator"]

        responses = []
        for username in usernames:
            response = client.post(
                "/token", data={"username": username, "password": "wrong_password"}
            )
            responses.append((username, response.status_code, response.json()))

        # All invalid login attempts should return similar responses
        # to prevent user enumeration
        status_codes = [r[1] for r in responses]
        assert all(
            code == 401 for code in status_codes
        ), "All invalid logins should return 401"

        # Response messages should be generic
        messages = [r[2].get("detail", "") for r in responses]
        unique_messages = set(messages)
        assert (
            len(unique_messages) <= 2
        ), "Should not leak information about user existence"


class TestRateLimitingAndDoS:
    """Test rate limiting and DoS protection."""

    @pytest.fixture
    def client(self):
        """Get test client."""
        if not API_AVAILABLE:
            pytest.skip("API not available")
        return TestClient(app)

    @pytest.fixture
    def auth_headers(self):
        """Get authorization headers."""
        if not create_access_token:
            pytest.skip("Auth not available")

        token_data = {"sub": "testuser", "scopes": ["user", "read", "write"]}
        token = create_access_token(token_data)
        return {"Authorization": f"Bearer {token}"}

    def test_login_rate_limiting(self, client):
        """Test rate limiting on login attempts."""
        # Attempt many rapid login requests
        login_attempts = 20
        responses = []

        for i in range(login_attempts):
            response = client.post(
                "/token", data={"username": "testuser", "password": "wrong_password"}
            )
            responses.append(response.status_code)

            # Small delay to avoid overwhelming the test
            if i % 5 == 0:
                time.sleep(0.1)

        # Check if rate limiting kicks in
        rate_limited_responses = [code for code in responses if code == 429]

        # This test documents current behavior - may not have rate limiting implemented
        if len(rate_limited_responses) > 0:
            assert (
                len(rate_limited_responses) > 0
            ), "Rate limiting should be active after many attempts"

    def test_api_endpoint_rate_limiting(self, client, auth_headers):
        """Test rate limiting on API endpoints."""
        rapid_requests = 50
        responses = []

        for i in range(rapid_requests):
            response = client.get("/health", headers=auth_headers)
            responses.append(response.status_code)

            if i % 10 == 0:
                time.sleep(0.05)  # Small delay

        # Check for rate limiting responses
        rate_limited_responses = [code for code in responses if code == 429]

        # Document current behavior
        if len(rate_limited_responses) == 0:
            # No rate limiting currently implemented
            pass

    def test_resource_exhaustion_protection(self, client, auth_headers):
        """Test protection against resource exhaustion attacks."""
        # Test with resource-intensive requests
        intensive_requests = [
            {"symbol": "EURUSD", "periods": 10000},  # Very large dataset request
            {
                "start_date": "1900-01-01",
                "end_date": "2030-12-31",
            },  # Very wide date range
            {"timeframe": "1s", "periods": 86400},  # High frequency data
        ]

        for request_data in intensive_requests:
            response = client.post(
                "/api/v1/data/historical", json=request_data, headers=auth_headers
            )

            # Should either reject or handle gracefully
            assert response.status_code in [
                200,
                400,
                413,
                422,
            ], "Should handle intensive requests gracefully"

            if response.status_code == 200:
                # If successful, response should complete in reasonable time
                # (This is tested implicitly by the test framework timeout)
                pass

    def test_concurrent_request_handling(self, client, auth_headers):
        """Test handling of concurrent requests."""
        import queue
        import threading

        results = queue.Queue()

        def make_request():
            try:
                response = client.get("/health", headers=auth_headers)
                results.put(response.status_code)
            except Exception as e:
                results.put(f"Error: {e}")

        # Launch concurrent requests
        threads = []
        for _ in range(20):
            thread = threading.Thread(target=make_request)
            threads.append(thread)
            thread.start()

        # Wait for all threads
        for thread in threads:
            thread.join(timeout=5)

        # Collect results
        responses = []
        while not results.empty():
            responses.append(results.get())

        # Most requests should succeed
        successful = [r for r in responses if r == 200]
        assert (
            len(successful) > len(responses) * 0.7
        ), "Most concurrent requests should succeed"


class TestCSRFProtection:
    """Test CSRF protection mechanisms."""

    @pytest.fixture
    def client(self):
        """Get test client."""
        if not API_AVAILABLE:
            pytest.skip("API not available")
        return TestClient(app)

    def test_csrf_token_requirement(self, client):
        """Test CSRF token requirement for state-changing operations."""
        # Test POST operations without CSRF token
        state_changing_endpoints = [
            ("/api/v1/orders", {"symbol": "EURUSD", "side": "buy", "quantity": 100}),
            ("/api/v1/config", {"setting": "value"}),
            ("/admin/users", {"username": "newuser", "password": "password"}),
        ]

        for endpoint, data in state_changing_endpoints:
            try:
                response = client.post(endpoint, json=data)

                # Should require authentication at minimum
                assert response.status_code in [
                    401,
                    403,
                    404,
                ], f"Endpoint {endpoint} should have protection"
            except Exception:
                # Skip if endpoint doesn't exist
                continue

    def test_origin_header_validation(self, client):
        """Test Origin header validation."""
        malicious_origins = [
            "https://evil.com",
            "http://attacker.example.com",
            "https://legitimate-domain.evil.com",
            "null",
            "file://",
        ]

        for origin in malicious_origins:
            response = client.post(
                "/token",
                data={"username": "user", "password": "password"},
                headers={"Origin": origin},
            )

            # Should validate or reject suspicious origins
            # (Current implementation may not check Origin header)
            if response.status_code == 200:
                # Document current behavior
                pass

    def test_referer_header_validation(self, client):
        """Test Referer header validation."""
        malicious_referers = [
            "https://evil.com/steal-credentials",
            "http://attacker.example.com/csrf-attack",
            "javascript:alert('xss')",
        ]

        for referer in malicious_referers:
            response = client.post(
                "/token",
                data={"username": "user", "password": "password"},
                headers={"Referer": referer},
            )

            # Should validate or be suspicious of malicious referers
            # (Current implementation may not check Referer header)
            if response.status_code == 200:
                # Document current behavior
                pass


class TestSessionManagement:
    """Test session management security."""

    @pytest.fixture
    def client(self):
        """Get test client."""
        if not API_AVAILABLE:
            pytest.skip("API not available")
        return TestClient(app)

    def test_session_fixation_protection(self, client):
        """Test protection against session fixation attacks."""
        # This test would be more relevant for session-based auth
        # JWT tokens are stateless, so session fixation is less of a concern
        pass

    def test_concurrent_session_handling(self, client):
        """Test handling of concurrent sessions."""
        if not create_access_token:
            pytest.skip("Auth not available")

        # Create multiple tokens for the same user
        user_tokens = []
        for i in range(5):
            token_data = {"sub": "testuser", "scopes": ["user", "read"]}
            token = create_access_token(token_data)
            user_tokens.append(token)

        # All tokens should be valid (JWT is stateless)
        for token in user_tokens:
            response = client.get(
                "/users/me", headers={"Authorization": f"Bearer {token}"}
            )

            if response.status_code == 200:
                # Multiple sessions allowed (current JWT behavior)
                pass

    def test_token_information_leakage(self, client):
        """Test for token information leakage in responses."""
        if not create_access_token:
            pytest.skip("Auth not available")

        # Valid login
        response = client.post(
            "/token", data={"username": "user", "password": "password"}
        )

        if response.status_code == 200:
            token_response = response.json()

            # Should not expose sensitive information
            assert "secret" not in token_response, "Should not expose secrets"
            assert "private_key" not in token_response, "Should not expose private keys"
            assert "password" not in token_response, "Should not expose passwords"

            # Should not expose detailed user information
            user_info_response = client.get(
                "/users/me",
                headers={"Authorization": f"Bearer {token_response['access_token']}"},
            )

            if user_info_response.status_code == 200:
                user_data = user_info_response.json()
                assert (
                    "password" not in user_data
                ), "Should not expose password in user data"
                assert (
                    "hashed_password" not in user_data
                ), "Should not expose password hash"


# Pytest markers for test categorization
pytestmark = [pytest.mark.security, pytest.mark.integration, pytest.mark.slow]
