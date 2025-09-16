"""
Validation Tests for FXML4 Security Fixes.

This test suite validates that the specific security fixes implemented
in the remediation plan are working correctly.
"""

import ast
import inspect
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestSecurityFixesValidation:
    """Test that specific security fixes are implemented."""

    def test_auth_bypass_removed_from_main(self):
        """Test that authentication bypass was removed from main.py."""
        main_py_path = Path("fxml4/api/main.py")
        assert main_py_path.exists(), "main.py should exist"

        with open(main_py_path, "r") as f:
            content = f.read()

        # Check that dangerous auth bypass code is not present
        dangerous_patterns = [
            "dev_auth_bypass",
            "bypass_auth",
            "authentication_bypass",
            "# DANGEROUS: Development auth bypass",
            "if environment == 'development' and debug_mode",
            "return None  # Skip auth in development",
        ]

        for pattern in dangerous_patterns:
            assert (
                pattern not in content
            ), f"Dangerous pattern '{pattern}' found in main.py"

    def test_security_middleware_implemented(self):
        """Test that SecurityMiddleware is properly implemented."""
        from fxml4.api.middleware.security import SecurityMiddleware

        # Test that middleware class exists
        assert SecurityMiddleware is not None

        # Test middleware initialization
        middleware = SecurityMiddleware()

        # Should have environment detection
        assert hasattr(middleware, "environment")
        assert middleware.environment in ["development", "production"]

        # Should have security headers
        assert hasattr(middleware, "security_headers")
        assert isinstance(middleware.security_headers, dict)

        # Check required security headers
        required_headers = [
            "X-Content-Type-Options",
            "X-Frame-Options",
            "X-XSS-Protection",
            "Referrer-Policy",
        ]

        for header in required_headers:
            assert header in middleware.security_headers

    def test_security_middleware_in_main(self):
        """Test that SecurityMiddleware is used in main.py."""
        main_py_path = Path("fxml4/api/main.py")

        with open(main_py_path, "r") as f:
            content = f.read()

        # Should import SecurityMiddleware
        assert "from fxml4.api.middleware.security import SecurityMiddleware" in content

        # Should use SecurityMiddleware
        assert "app.add_middleware(SecurityMiddleware)" in content

    def test_signals_router_uses_proper_auth(self):
        """Test that signals router uses proper authentication."""
        signals_py_path = Path("fxml4/api/routers/signals.py")

        with open(signals_py_path, "r") as f:
            content = f.read()

        # Should use proper auth imports
        assert (
            "from fxml4.api.auth.auth import User, get_current_active_user" in content
        )

        # Should NOT use UAT auth
        assert "uat_auth" not in content
        assert "UATUser" not in content
        assert "get_current_active_user_uat" not in content

    def test_trading_engine_has_timeout_handling(self):
        """Test that trading engine has proper timeout handling."""
        from fxml4.api.services.trading_engine import TradingEngine

        # Get the source code
        source = inspect.getsource(TradingEngine)

        # Should use asyncio.wait_for for timeout handling
        assert (
            "asyncio.wait_for" in source
        ), "Trading engine should use asyncio.wait_for for timeouts"
        assert "timeout=" in source, "Trading engine should specify timeout values"

    def test_trading_engine_has_circuit_breaker(self):
        """Test that trading engine has circuit breaker functionality."""
        from fxml4.api.services.trading_engine import TradingEngine, TradingEngineConfig

        # Check configuration has circuit breaker settings
        config = TradingEngineConfig()
        assert hasattr(config, "max_errors_per_minute")
        assert hasattr(config, "circuit_breaker_pause_minutes")

        # Check trading engine has circuit breaker methods
        engine = TradingEngine()
        assert hasattr(engine, "_record_error")
        assert hasattr(engine, "_check_circuit_breaker")

    def test_conditional_imports_have_proper_logging(self):
        """Test that conditional imports have proper error logging."""
        main_py_path = Path("fxml4/api/main.py")

        with open(main_py_path, "r") as f:
            content = f.read()

        # Should have proper exception handling for imports
        assert "except ImportError as e:" in content
        assert "except Exception as e:" in content
        assert "logger.warning" in content
        assert "logger.error" in content

        # Should NOT have silent "pass" statements for critical imports
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if "except ImportError" in line and i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if next_line == "pass":
                    # Check if this is for optional components (ok) or critical ones (not ok)
                    context = " ".join(lines[max(0, i - 5) : i])
                    critical_imports = ["websocket", "orders", "trading"]
                    if any(imp in context.lower() for imp in critical_imports):
                        assert (
                            False
                        ), f"Critical import should not have silent 'pass': {context}"

    def test_typescript_types_generated(self):
        """Test that TypeScript types were generated."""
        types_path = Path("fxml4-ui/src/types/api-generated.ts")
        assert types_path.exists(), "Generated TypeScript types should exist"

        with open(types_path, "r") as f:
            content = f.read()

        # Should contain key types
        expected_types = [
            "export enum TimeframeEnum",
            "export enum TradingEngineState",
            "export enum TradingMode",
            "export interface TradingSignal",
            "export interface OrderRequest",
            "export interface TradingEngineConfig",
            "export interface ApiResponse",
        ]

        for type_def in expected_types:
            assert type_def in content, f"Missing type definition: {type_def}"

    def test_frontend_types_exported(self):
        """Test that frontend types are properly exported."""
        index_path = Path("fxml4-ui/src/types/index.ts")

        if index_path.exists():
            with open(index_path, "r") as f:
                content = f.read()

            # Should export generated types
            assert 'export * from "./api-generated"' in content


class TestSecurityConfiguration:
    """Test security configuration is correct."""

    def test_jwt_secret_key_handling(self):
        """Test JWT secret key is handled securely."""
        # Import should work
        from fxml4.api.auth.auth import SECRET_KEY

        # Should have a secret key
        assert SECRET_KEY is not None
        assert len(SECRET_KEY) > 0

        # Should prefer environment variable
        with patch.dict(
            os.environ,
            {"FXML4_JWT_SECRET_KEY": "test-secret-key"},  # pragma: allowlist secret
        ):
            # Re-import to get updated value
            import importlib

            import fxml4.api.auth.auth

            importlib.reload(fxml4.api.auth.auth)

            from fxml4.api.auth.auth import SECRET_KEY as updated_key

            assert updated_key == "test-secret-key"

    def test_environment_detection(self):
        """Test environment detection works correctly."""
        from fxml4.api.middleware.security import SecurityMiddleware

        # Test production environment
        with patch.dict(os.environ, {"FXML4_ENVIRONMENT": "production"}):
            middleware = SecurityMiddleware()
            assert middleware.environment == "production"
            # Should have production security headers
            assert "Strict-Transport-Security" in middleware.security_headers

        # Test development environment
        with patch.dict(os.environ, {"FXML4_ENVIRONMENT": "development"}):
            middleware = SecurityMiddleware()
            assert middleware.environment == "development"
            # Should not have HSTS in development
            assert "Strict-Transport-Security" not in middleware.security_headers

    def test_cors_configuration(self):
        """Test CORS configuration is restrictive."""
        main_py_path = Path("fxml4/api/main.py")

        with open(main_py_path, "r") as f:
            content = f.read()

        # Should have specific allowed origins, not wildcard
        assert 'allow_origins=["*"]' not in content, "CORS should not allow all origins"
        assert "localhost:3000" in content, "Should allow localhost for development"


class TestTimeoutConfiguration:
    """Test timeout configuration is correct."""

    def test_trading_engine_timeouts(self):
        """Test trading engine has reasonable timeout values."""
        from fxml4.api.services.trading_engine import TradingEngineConfig

        config = TradingEngineConfig()

        # Check timeout values are reasonable
        assert (
            0 < config.signal_timeout_minutes < 60
        ), "Signal timeout should be reasonable"
        assert (
            0 < config.order_timeout_minutes < 120
        ), "Order timeout should be reasonable"
        assert (
            0 < config.max_errors_per_minute < 100
        ), "Error threshold should be reasonable"
        assert (
            0 < config.circuit_breaker_pause_minutes < 60
        ), "Circuit breaker pause should be reasonable"

    def test_async_timeout_patterns(self):
        """Test that async operations have timeout patterns."""
        from fxml4.api.services.trading_engine import TradingEngine

        # Get source code
        source = inspect.getsource(TradingEngine._process_signals)

        # Should have timeout handling
        assert "asyncio.wait_for" in source
        assert "timeout=" in source
        assert "TimeoutError" in source or "asyncio.TimeoutError" in source


class TestFrontendBackendAlignment:
    """Test frontend-backend type alignment."""

    def test_api_client_exists(self):
        """Test that API client exists and is well-structured."""
        api_client_path = Path("fxml4-ui/src/services/api.ts")
        assert api_client_path.exists(), "API client should exist"

        with open(api_client_path, "r") as f:
            content = f.read()

        # Should have proper error handling
        assert "ApiError" in content or "error handling" in content
        assert "timeout" in content, "Should have timeout configuration"
        assert "Authorization" in content, "Should handle authentication"

    def test_types_consistency(self):
        """Test that frontend types are consistent with backend."""
        # This is a basic check - more comprehensive checks would require
        # parsing both TypeScript and Python type definitions

        types_path = Path("fxml4-ui/src/types/api-generated.ts")
        if not types_path.exists():
            pytest.skip("Generated types not found")

        with open(types_path, "r") as f:
            ts_content = f.read()

        # Check that key enums match expected backend values
        backend_patterns = [
            ("TimeframeEnum", ["1m", "5m", "15m", "1h", "4h", "1d"]),
            ("TradingMode", ["manual", "semi_auto", "fully_auto"]),
            ("TradingEngineState", ["inactive", "active", "paused", "error"]),
        ]

        for enum_name, expected_values in backend_patterns:
            assert f"export enum {enum_name}" in ts_content
            for value in expected_values:
                assert (
                    f'"{value}"' in ts_content
                ), f"Missing enum value {value} in {enum_name}"


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v", "--tb=short"])
