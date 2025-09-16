#!/usr/bin/env python3
"""
MANDATORY LOGIN TEST - CI/CD CRITICAL
=====================================

This test MUST pass for CI/CD to succeed. If login fails, the entire deployment is blocked.

Tests:
1. User authentication flow
2. JWT token generation and validation
3. Session management
4. Login endpoint availability
5. Database authentication integration

CRITICAL: This test runs in both staging and production environments
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict

import pytest
import requests

# Configure logging for CI/CD visibility
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MandatoryLoginTest:
    """Critical login test that must pass for deployment to proceed"""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.test_user = {
            "username": "ci_test_user",
            "email": "ci_test@fxml4.com",
            "password": "SecureTestPass123!",  # pragma: allowlist secret
        }

    def test_api_availability(self) -> bool:
        """Test 1: Verify API is reachable"""
        try:
            response = self.session.get(f"{self.base_url}/health", timeout=10)
            assert (
                response.status_code == 200
            ), f"API health check failed: {response.status_code}"
            logger.info("✅ API is reachable and healthy")
            return True
        except Exception as e:
            logger.error(f"❌ CRITICAL: API unreachable - {e}")
            raise AssertionError(f"API availability test failed: {e}")

    def test_auth_endpoint_exists(self) -> bool:
        """Test 2: Verify authentication endpoints exist"""
        endpoints = ["/auth/login", "/auth/register", "/auth/validate"]

        for endpoint in endpoints:
            try:
                response = self.session.options(
                    f"{self.base_url}{endpoint}", timeout=10
                )
                assert response.status_code in [
                    200,
                    405,
                ], f"Auth endpoint {endpoint} not found"
                logger.info(f"✅ Auth endpoint {endpoint} exists")
            except Exception as e:
                logger.error(f"❌ CRITICAL: Auth endpoint {endpoint} missing - {e}")
                raise AssertionError(f"Auth endpoint validation failed: {e}")

        return True

    def test_user_registration(self) -> Dict[str, Any]:
        """Test 3: Create test user for login testing"""
        try:
            # Try to register test user
            response = self.session.post(
                f"{self.base_url}/auth/register", json=self.test_user, timeout=10
            )

            # User might already exist - that's OK for testing
            if response.status_code == 409:
                logger.info("✅ Test user already exists (acceptable)")
                return {"status": "exists"}

            assert (
                response.status_code == 201
            ), f"User registration failed: {response.status_code} - {response.text}"
            logger.info("✅ Test user registered successfully")
            return response.json()

        except Exception as e:
            logger.error(f"❌ CRITICAL: User registration test failed - {e}")
            raise AssertionError(f"User registration failed: {e}")

    def test_mandatory_login(self) -> Dict[str, Any]:
        """Test 4: MANDATORY LOGIN TEST - This MUST work for deployment to proceed"""
        try:
            # Attempt login with test credentials
            login_data = {
                "username": self.test_user["username"],
                "password": self.test_user["password"],
            }

            response = self.session.post(
                f"{self.base_url}/auth/login", json=login_data, timeout=10
            )

            # CRITICAL: Login must succeed
            assert (
                response.status_code == 200
            ), f"LOGIN FAILED - Status: {response.status_code}, Body: {response.text}"

            token_data = response.json()
            assert (
                "access_token" in token_data
            ), f"No access token in response: {token_data}"
            assert (
                "token_type" in token_data
            ), f"No token type in response: {token_data}"

            # Validate token format
            token = token_data["access_token"]
            assert (
                isinstance(token, str) and len(token) > 20
            ), f"Invalid token format: {token}"

            logger.info("✅ MANDATORY LOGIN TEST PASSED - User can successfully login")
            return token_data

        except AssertionError:
            raise  # Re-raise assertion errors
        except Exception as e:
            logger.error(f"❌ CRITICAL: MANDATORY LOGIN TEST FAILED - {e}")
            raise AssertionError(f"MANDATORY LOGIN FAILED: {e}")

    def test_token_validation(self, token_data: Dict[str, Any]) -> bool:
        """Test 5: Validate JWT token works for authenticated requests"""
        try:
            token = token_data["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            # Test authenticated endpoint
            response = self.session.get(
                f"{self.base_url}/auth/profile", headers=headers, timeout=10
            )

            assert (
                response.status_code == 200
            ), f"Token validation failed: {response.status_code}"

            profile_data = response.json()
            assert (
                "username" in profile_data
            ), f"Invalid profile response: {profile_data}"

            logger.info("✅ JWT token validation successful")
            return True

        except Exception as e:
            logger.error(f"❌ CRITICAL: Token validation failed - {e}")
            raise AssertionError(f"Token validation failed: {e}")

    def test_session_management(self, token_data: Dict[str, Any]) -> bool:
        """Test 6: Verify session management works properly"""
        try:
            token = token_data["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            # Test session endpoint
            response = self.session.get(
                f"{self.base_url}/auth/session", headers=headers, timeout=10
            )

            assert (
                response.status_code == 200
            ), f"Session check failed: {response.status_code}"

            session_data = response.json()
            assert (
                "user_id" in session_data
            ), f"Invalid session response: {session_data}"
            assert (
                "expires_at" in session_data
            ), f"No expiration in session: {session_data}"

            logger.info("✅ Session management validation successful")
            return True

        except Exception as e:
            logger.error(f"❌ CRITICAL: Session management test failed - {e}")
            raise AssertionError(f"Session management failed: {e}")

    def run_all_tests(self) -> Dict[str, Any]:
        """Execute all mandatory login tests - MUST ALL PASS"""
        logger.info(f"🔐 STARTING MANDATORY LOGIN TESTS for {self.base_url}")

        try:
            # Test 1: API Availability
            self.test_api_availability()

            # Test 2: Auth endpoints exist
            self.test_auth_endpoint_exists()

            # Test 3: User registration
            self.test_user_registration()

            # Test 4: MANDATORY LOGIN (CRITICAL)
            token_data = self.test_mandatory_login()

            # Test 5: Token validation
            self.test_token_validation(token_data)

            # Test 6: Session management
            self.test_session_management(token_data)

            logger.info("🎉 ALL MANDATORY LOGIN TESTS PASSED - Deployment can proceed")

            return {
                "status": "PASSED",
                "timestamp": datetime.now().isoformat(),
                "environment": self.base_url,
                "tests_passed": 6,
                "token_valid": True,
                "message": "All login functionality verified - deployment approved",
            }

        except AssertionError as e:
            logger.error(f"💥 MANDATORY LOGIN TESTS FAILED - BLOCKING DEPLOYMENT")
            logger.error(f"Error: {e}")
            raise
        except Exception as e:
            logger.error(f"💥 UNEXPECTED ERROR IN LOGIN TESTS - BLOCKING DEPLOYMENT")
            logger.error(f"Error: {e}")
            raise AssertionError(f"Unexpected login test failure: {e}")


# Pytest integration for CI/CD
@pytest.mark.critical
@pytest.mark.auth
@pytest.mark.mandatory
def test_mandatory_login_staging():
    """Run mandatory login test against staging environment"""
    staging_url = os.getenv("STAGING_URL", "http://staging-api.fxml4.com")
    tester = MandatoryLoginTest(staging_url)
    result = tester.run_all_tests()
    assert result["status"] == "PASSED", "Staging login test failed"


@pytest.mark.critical
@pytest.mark.auth
@pytest.mark.mandatory
@pytest.mark.production
def test_mandatory_login_production():
    """Run mandatory login test against production environment"""
    production_url = os.getenv("PRODUCTION_URL", "https://api.fxml4.com")
    tester = MandatoryLoginTest(production_url)
    result = tester.run_all_tests()
    assert result["status"] == "PASSED", "Production login test failed"


if __name__ == "__main__":
    import sys

    # Command line execution for CI/CD
    if len(sys.argv) > 1:
        environment_url = sys.argv[1]
    else:
        environment_url = os.getenv("API_URL", "http://localhost:8001")

    print(f"🔐 Running MANDATORY LOGIN TESTS against: {environment_url}")

    try:
        tester = MandatoryLoginTest(environment_url)
        result = tester.run_all_tests()

        print(f"✅ RESULT: {result}")
        sys.exit(0)  # Success

    except Exception as e:
        print(f"❌ MANDATORY LOGIN TESTS FAILED: {e}")
        sys.exit(1)  # Failure - blocks CI/CD
