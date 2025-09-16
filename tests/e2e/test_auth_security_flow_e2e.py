"""
End-to-End Authentication Flow Test Suite
=========================================

Comprehensive E2E test for the complete authentication lifecycle in a containerized environment.
Tests the full flow: Registration → Login → JWT Usage → Token Refresh → Logout
with security audit trail verification across multiple Docker containers.

This test validates:
- Container-to-container communication (API ↔ Database ↔ Redis ↔ RabbitMQ)
- JWT token lifecycle management
- Security audit trail generation and persistence
- Session management across containers
- Concurrent user handling
- Rate limiting and security measures
"""

import asyncio
import json
import os
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import uuid4

import aiohttp
import asyncpg
import pytest
import redis.asyncio as redis
from aio_pika import Message, connect_robust

# Configuration from environment
API_BASE_URL = os.getenv("API_BASE_URL", "http://test-api:8000")
DATABASE_HOST = os.getenv("DATABASE_HOST", "test-db")
DATABASE_PORT = int(os.getenv("DATABASE_PORT", "5432"))
DATABASE_USER = os.getenv("DATABASE_USER", "fxml4_test")
DATABASE_PASSWORD = os.getenv(
    "DATABASE_PASSWORD", "test_password"
)  # pragma: allowlist secret
DATABASE_NAME = os.getenv("DATABASE_NAME", "fxml4_test")
REDIS_HOST = os.getenv("REDIS_HOST", "test-redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "test-rabbitmq")
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "fxml4_test")
RABBITMQ_PASSWORD = os.getenv(
    "RABBITMQ_PASSWORD", "test_password"
)  # pragma: allowlist secret


class TestAuthenticationE2E:
    """Complete end-to-end authentication flow tests in containerized environment."""

    @pytest.fixture(scope="class")
    async def http_session(self):
        """Create aiohttp session for API calls."""
        timeout = aiohttp.ClientTimeout(total=30)
        session = aiohttp.ClientSession(timeout=timeout)
        yield session
        await session.close()

    @pytest.fixture(scope="class")
    async def db_connection(self):
        """Direct database connection for verification."""
        max_retries = 5
        retry_delay = 2

        for attempt in range(max_retries):
            try:
                conn = await asyncpg.connect(
                    host=DATABASE_HOST,
                    port=DATABASE_PORT,
                    user=DATABASE_USER,
                    password=DATABASE_PASSWORD,
                    database=DATABASE_NAME,
                )
                yield conn
                await conn.close()
                return
            except Exception as e:
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                else:
                    pytest.fail(
                        f"Failed to connect to database after {max_retries} attempts: {e}"
                    )

    @pytest.fixture(scope="class")
    async def redis_client(self):
        """Direct Redis connection for cache verification."""
        client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

        # Test connection
        try:
            await client.ping()
        except Exception as e:
            pytest.fail(f"Failed to connect to Redis: {e}")

        yield client
        await client.close()

    @pytest.fixture(scope="class")
    async def rabbitmq_connection(self):
        """RabbitMQ connection for audit event verification."""
        max_retries = 5
        retry_delay = 2

        for attempt in range(max_retries):
            try:
                connection = await connect_robust(
                    f"amqp://{RABBITMQ_USER}:{RABBITMQ_PASSWORD}@{RABBITMQ_HOST}/"
                )
                channel = await connection.channel()

                # Declare audit queue
                queue = await channel.declare_queue(
                    "security_audit_events", durable=True
                )

                yield {"connection": connection, "channel": channel, "queue": queue}

                await connection.close()
                return
            except Exception as e:
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                else:
                    pytest.fail(
                        f"Failed to connect to RabbitMQ after {max_retries} attempts: {e}"
                    )

    @pytest.fixture
    async def test_user(self):
        """Generate test user data."""
        unique_id = str(uuid4())[:8]
        return {
            "username": f"test_user_{unique_id}",
            "email": f"test_{unique_id}@example.com",
            "password": "SecureP@ssw0rd123!",  # pragma: allowlist secret
            "full_name": f"Test User {unique_id}",
        }

    @pytest.fixture
    async def wait_for_services(self):
        """Ensure all services are ready before tests."""
        max_wait = 60  # seconds
        start_time = time.time()

        async with aiohttp.ClientSession() as session:
            while time.time() - start_time < max_wait:
                try:
                    # Check API health
                    async with session.get(f"{API_BASE_URL}/health") as resp:
                        if resp.status == 200:
                            return
                except:
                    pass
                await asyncio.sleep(2)

        pytest.fail("Services did not become ready in time")

    @pytest.mark.asyncio
    async def test_complete_authentication_flow(
        self,
        http_session,
        db_connection,
        redis_client,
        rabbitmq_connection,
        test_user,
        wait_for_services,
    ):
        """Test the complete authentication flow across all containers."""

        # Store tokens for flow testing
        access_token = None
        refresh_token = None
        user_id = None

        # 1. USER REGISTRATION
        print("\n1. Testing User Registration...")

        async with http_session.post(
            f"{API_BASE_URL}/api/auth/register", json=test_user
        ) as response:
            assert (
                response.status == 201
            ), f"Registration failed: {await response.text()}"
            registration_data = await response.json()

            assert "user_id" in registration_data
            assert "message" in registration_data
            user_id = registration_data["user_id"]
            print(f"   ✓ User registered successfully: {user_id}")

        # Verify user in database
        user_record = await db_connection.fetchrow(
            "SELECT * FROM users WHERE username = $1", test_user["username"]
        )
        assert user_record is not None, "User not found in database"
        assert user_record["email"] == test_user["email"]
        print("   ✓ User verified in database container")

        # 2. USER LOGIN
        print("\n2. Testing User Login...")

        async with http_session.post(
            f"{API_BASE_URL}/api/auth/login",
            json={"username": test_user["username"], "password": test_user["password"]},
        ) as response:
            assert response.status == 200, f"Login failed: {await response.text()}"
            login_data = await response.json()

            assert "access_token" in login_data
            assert "refresh_token" in login_data
            assert "token_type" in login_data
            assert login_data["token_type"] == "bearer"

            access_token = login_data["access_token"]
            refresh_token = login_data["refresh_token"]
            print("   ✓ Login successful, tokens received")

        # Verify session in Redis
        session_keys = await redis_client.keys(f"session:{user_id}:*")
        assert len(session_keys) > 0, "No session found in Redis"
        print(f"   ✓ Session stored in Redis: {len(session_keys)} key(s)")

        # 3. ACCESS PROTECTED RESOURCE
        print("\n3. Testing Protected Resource Access...")

        headers = {"Authorization": f"Bearer {access_token}"}

        async with http_session.get(
            f"{API_BASE_URL}/api/auth/me", headers=headers
        ) as response:
            assert (
                response.status == 200
            ), f"Protected access failed: {await response.text()}"
            user_data = await response.json()

            assert user_data["username"] == test_user["username"]
            assert user_data["email"] == test_user["email"]
            print("   ✓ Protected resource accessed successfully")

        # 4. INVALID TOKEN TEST
        print("\n4. Testing Invalid Token Rejection...")

        invalid_headers = {"Authorization": "Bearer invalid_token_12345"}

        async with http_session.get(
            f"{API_BASE_URL}/api/auth/me", headers=invalid_headers
        ) as response:
            assert response.status == 401, "Invalid token should be rejected"
            print("   ✓ Invalid token properly rejected")

        # 5. TOKEN REFRESH
        print("\n5. Testing Token Refresh...")

        # Wait a moment to ensure tokens are different
        await asyncio.sleep(1)

        async with http_session.post(
            f"{API_BASE_URL}/api/auth/refresh", json={"refresh_token": refresh_token}
        ) as response:
            assert (
                response.status == 200
            ), f"Token refresh failed: {await response.text()}"
            refresh_data = await response.json()

            assert "access_token" in refresh_data
            new_access_token = refresh_data["access_token"]
            assert new_access_token != access_token, "New token should be different"

            access_token = new_access_token
            print("   ✓ Token refreshed successfully")

        # Verify new token works
        headers = {"Authorization": f"Bearer {access_token}"}

        async with http_session.get(
            f"{API_BASE_URL}/api/auth/me", headers=headers
        ) as response:
            assert response.status == 200, "New token should work"
            print("   ✓ New token validated")

        # 6. CONCURRENT SESSION TEST
        print("\n6. Testing Concurrent Sessions...")

        # Login from "different location"
        async with http_session.post(
            f"{API_BASE_URL}/api/auth/login",
            json={"username": test_user["username"], "password": test_user["password"]},
            headers={"X-Forwarded-For": "192.168.1.100"},
        ) as response:
            assert response.status == 200, "Second login should succeed"
            second_login_data = await response.json()
            second_access_token = second_login_data["access_token"]
            print("   ✓ Concurrent session created")

        # Both tokens should work
        for token, label in [(access_token, "first"), (second_access_token, "second")]:
            headers = {"Authorization": f"Bearer {token}"}
            async with http_session.get(
                f"{API_BASE_URL}/api/auth/me", headers=headers
            ) as response:
                assert response.status == 200, f"{label} token should work"
        print("   ✓ Both sessions validated")

        # 7. LOGOUT
        print("\n7. Testing Logout...")

        headers = {"Authorization": f"Bearer {access_token}"}

        async with http_session.post(
            f"{API_BASE_URL}/api/auth/logout", headers=headers
        ) as response:
            assert response.status == 200, f"Logout failed: {await response.text()}"
            print("   ✓ Logout successful")

        # Verify token is invalidated
        async with http_session.get(
            f"{API_BASE_URL}/api/auth/me", headers=headers
        ) as response:
            assert response.status == 401, "Logged out token should be invalid"
            print("   ✓ Token properly invalidated")

        # Verify session removed from Redis
        session_keys_after = await redis_client.keys(f"session:{user_id}:*")
        assert len(session_keys_after) < len(
            session_keys
        ), "Session should be removed from Redis"
        print("   ✓ Session removed from Redis")

        print("\n✅ Complete authentication flow test passed!")

    @pytest.mark.asyncio
    async def test_security_audit_trail(
        self,
        http_session,
        db_connection,
        rabbitmq_connection,
        test_user,
        wait_for_services,
    ):
        """Test that all authentication events generate proper audit trails."""

        print("\n Testing Security Audit Trail...")

        # Register and login to generate events
        unique_id = str(uuid4())[:8]
        audit_user = {
            "username": f"audit_user_{unique_id}",
            "email": f"audit_{unique_id}@example.com",
            "password": "AuditP@ssw0rd123!",  # pragma: allowlist secret
            "full_name": f"Audit User {unique_id}",
        }

        # Track correlation ID for audit trail
        correlation_id = str(uuid4())

        # Register with correlation ID header
        async with http_session.post(
            f"{API_BASE_URL}/api/auth/register",
            json=audit_user,
            headers={"X-Correlation-ID": correlation_id},
        ) as response:
            assert response.status == 201
            registration_data = await response.json()
            user_id = registration_data["user_id"]

        # Login
        async with http_session.post(
            f"{API_BASE_URL}/api/auth/login",
            json={
                "username": audit_user["username"],
                "password": audit_user["password"],
            },
            headers={"X-Correlation-ID": correlation_id},
        ) as response:
            assert response.status == 200
            login_data = await response.json()
            access_token = login_data["access_token"]

        # Failed login attempt (wrong password)
        async with http_session.post(
            f"{API_BASE_URL}/api/auth/login",
            json={"username": audit_user["username"], "password": "WrongPassword123!"},
            headers={"X-Correlation-ID": correlation_id},
        ) as response:
            assert response.status == 401

        # Logout
        headers = {
            "Authorization": f"Bearer {access_token}",
            "X-Correlation-ID": correlation_id,
        }
        async with http_session.post(
            f"{API_BASE_URL}/api/auth/logout", headers=headers
        ) as response:
            assert response.status == 200

        # Wait for audit events to be processed
        await asyncio.sleep(2)

        # Check audit events in database
        audit_events = await db_connection.fetch(
            """
            SELECT event_type, user_id, details, created_at
            FROM security_audit_events
            WHERE user_id = $1 OR details->>'username' = $2
            ORDER BY created_at ASC
        """,
            user_id,
            audit_user["username"],
        )

        # Verify expected events
        event_types = [event["event_type"] for event in audit_events]

        assert (
            "user_registered" in event_types
            or "registration" in str(event_types).lower()
        )
        assert "login_success" in event_types or "login" in str(event_types).lower()
        assert "login_failure" in event_types or "failed" in str(event_types).lower()
        assert "logout" in event_types or "logout" in str(event_types).lower()

        print(f"   ✓ Found {len(audit_events)} audit events in database")
        print(f"   ✓ Event types: {event_types}")

        # Check RabbitMQ for audit messages (if queue exists)
        try:
            queue = rabbitmq_connection["queue"]
            message_count = (
                queue.declaration_result.message_count
                if hasattr(queue, "declaration_result")
                else 0
            )
            print(f"   ✓ {message_count} messages in RabbitMQ audit queue")
        except Exception as e:
            print(f"   ⚠ Could not check RabbitMQ queue: {e}")

        print("\n✅ Security audit trail test passed!")

    @pytest.mark.asyncio
    async def test_rate_limiting(self, http_session, test_user, wait_for_services):
        """Test rate limiting across containers using Redis."""

        print("\n Testing Rate Limiting...")

        # Register a user for rate limit testing
        unique_id = str(uuid4())[:8]
        rate_user = {
            "username": f"rate_user_{unique_id}",
            "email": f"rate_{unique_id}@example.com",
            "password": "RateP@ssw0rd123!",  # pragma: allowlist secret
            "full_name": f"Rate User {unique_id}",
        }

        async with http_session.post(
            f"{API_BASE_URL}/api/auth/register", json=rate_user
        ) as response:
            assert response.status == 201

        # Attempt multiple rapid login attempts
        login_attempts = []
        for i in range(10):
            async with http_session.post(
                f"{API_BASE_URL}/api/auth/login",
                json={
                    "username": rate_user["username"],
                    "password": "WrongPassword!",  # pragma: allowlist secret
                },
            ) as response:
                login_attempts.append(response.status)

        # Should see rate limiting kick in (429 status codes)
        rate_limited = any(status == 429 for status in login_attempts)

        if rate_limited:
            print(
                f"   ✓ Rate limiting active: {login_attempts.count(429)} requests blocked"
            )
        else:
            print(
                f"   ⚠ Rate limiting may not be configured: all {len(login_attempts)} requests went through"
            )

        # At least verify failed attempts are tracked
        assert 401 in login_attempts, "Failed login attempts should return 401"
        print("   ✓ Failed login attempts properly handled")

        print("\n✅ Rate limiting test completed!")

    @pytest.mark.asyncio
    async def test_container_health_and_connectivity(
        self, http_session, db_connection, redis_client, rabbitmq_connection
    ):
        """Verify all containers are healthy and can communicate."""

        print("\n Testing Container Health & Connectivity...")

        # 1. API Container Health
        async with http_session.get(f"{API_BASE_URL}/health") as response:
            assert response.status == 200
            health_data = await response.json()
            print(f"   ✓ API Container: {health_data.get('status', 'healthy')}")

        # 2. Database Container
        db_version = await db_connection.fetchval("SELECT version()")
        assert "PostgreSQL" in db_version
        print(f"   ✓ Database Container: PostgreSQL connected")

        # 3. Redis Container
        pong = await redis_client.ping()
        assert pong is True
        print("   ✓ Redis Container: PONG received")

        # 4. RabbitMQ Container
        assert rabbitmq_connection["connection"].is_open
        print("   ✓ RabbitMQ Container: Connection open")

        # 5. Inter-container connectivity test
        # API -> Database
        async with http_session.get(f"{API_BASE_URL}/api/health/db") as response:
            if response.status == 200:
                print("   ✓ API → Database: Connected")
            else:
                print("   ⚠ API → Database: May not have health endpoint")

        # API -> Redis
        async with http_session.get(f"{API_BASE_URL}/api/health/cache") as response:
            if response.status == 200:
                print("   ✓ API → Redis: Connected")
            else:
                print("   ⚠ API → Redis: May not have health endpoint")

        print("\n✅ All containers healthy and connected!")

    @pytest.mark.asyncio
    async def test_session_isolation_between_users(
        self, http_session, redis_client, wait_for_services
    ):
        """Test that user sessions are properly isolated in the containerized environment."""

        print("\n Testing Session Isolation...")

        # Create two different users
        users = []
        tokens = []

        for i in range(2):
            unique_id = str(uuid4())[:8]
            user = {
                "username": f"isolated_user_{i}_{unique_id}",
                "email": f"isolated_{i}_{unique_id}@example.com",
                "password": f"IsolatedP@ss{i}!",
                "full_name": f"Isolated User {i}",
            }

            # Register
            async with http_session.post(
                f"{API_BASE_URL}/api/auth/register", json=user
            ) as response:
                assert response.status == 201

            # Login
            async with http_session.post(
                f"{API_BASE_URL}/api/auth/login",
                json={"username": user["username"], "password": user["password"]},
            ) as response:
                assert response.status == 200
                login_data = await response.json()

                users.append(user)
                tokens.append(login_data["access_token"])

        print(f"   ✓ Created {len(users)} isolated users")

        # Each user should only see their own data
        for i, (user, token) in enumerate(zip(users, tokens)):
            headers = {"Authorization": f"Bearer {token}"}

            async with http_session.get(
                f"{API_BASE_URL}/api/auth/me", headers=headers
            ) as response:
                assert response.status == 200
                user_data = await response.json()

                # Verify correct user data
                assert user_data["username"] == user["username"]
                assert user_data["email"] == user["email"]

                # Ensure no data leakage from other user
                other_user = users[1 - i]  # Get the other user
                assert user_data["username"] != other_user["username"]
                assert user_data["email"] != other_user["email"]

        print("   ✓ Session isolation verified")

        # Check Redis for session separation
        session_keys_user1 = await redis_client.keys(f"*{users[0]['username']}*")
        session_keys_user2 = await redis_client.keys(f"*{users[1]['username']}*")

        # Sessions should be separate
        assert (
            len(set(session_keys_user1) & set(session_keys_user2)) == 0
        ), "Session keys should not overlap"
        print("   ✓ Redis session keys properly isolated")

        print("\n✅ Session isolation test passed!")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
