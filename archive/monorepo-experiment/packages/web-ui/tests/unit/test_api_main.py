"""Tests for main FastAPI application."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, AsyncMock
import json

from fxml4_web.api.main import create_app, APIConfig, lifespan


@pytest.fixture
def api_config():
    """Create test API configuration."""
    return APIConfig(
        api_title="Test API",
        api_version="0.1.0",
        api_description="Test Description",
        cors_origins=["http://testhost:3000"],
        secret_key="test-secret-key",
        database_url="postgresql://test:test@localhost/test",
        redis_url="redis://localhost:6379/0"
    )


@pytest.fixture
def test_client(api_config):
    """Create test client with test configuration."""
    app = create_app(api_config)
    return TestClient(app)


@pytest.fixture
def test_app(api_config):
    """Create test app instance."""
    return create_app(api_config)


class TestAPIConfig:
    """Test APIConfig class."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = APIConfig()
        assert config.api_title == "FXML4 Trading API"
        assert config.api_version == "1.0.0"
        assert config.api_description == "REST API for FXML4 forex trading system"
        assert "http://localhost:3000" in config.cors_origins
        assert "http://localhost:8501" in config.cors_origins
    
    def test_custom_config(self, api_config):
        """Test custom configuration values."""
        assert api_config.api_title == "Test API"
        assert api_config.api_version == "0.1.0"
        assert api_config.cors_origins == ["http://testhost:3000"]
        assert api_config.secret_key == "test-secret-key"


class TestCreateApp:
    """Test application creation."""
    
    def test_create_app_default(self):
        """Test creating app with default config."""
        app = create_app()
        assert app.title == "FXML4 Trading API"
        assert app.version == "1.0.0"
    
    def test_create_app_custom_config(self, api_config):
        """Test creating app with custom config."""
        app = create_app(api_config)
        assert app.title == "Test API"
        assert app.version == "0.1.0"
    
    def test_cors_middleware_added(self, test_app):
        """Test that CORS middleware is added."""
        # Check if CORSMiddleware is in the middleware stack
        middleware_classes = [type(m) for m in test_app.user_middleware]
        assert any("CORSMiddleware" in str(m) for m in middleware_classes)
    
    def test_routers_included(self, test_app):
        """Test that all routers are included."""
        routes = [route.path for route in test_app.routes]
        
        # Check API routes
        assert any("/api/v1/auth" in route for route in routes)
        assert any("/api/v1/market" in route for route in routes)
        assert any("/api/v1/trading" in route for route in routes)
        assert any("/api/v1/backtest" in route for route in routes)
        assert any("/api/v1/analytics" in route for route in routes)
        assert any("/api/v1/ws" in route for route in routes)
    
    def test_root_endpoint_exists(self, test_app):
        """Test that root endpoint exists."""
        routes = [route.path for route in test_app.routes]
        assert "/" in routes
    
    def test_health_endpoint_exists(self, test_app):
        """Test that health endpoint exists."""
        routes = [route.path for route in test_app.routes]
        assert "/health" in routes


class TestRootEndpoint:
    """Test root endpoint."""
    
    def test_root_response(self, test_client, api_config):
        """Test root endpoint response."""
        response = test_client.get("/")
        assert response.status_code == 200
        
        data = response.json()
        assert data["message"] == "FXML4 Trading API"
        assert data["version"] == api_config.api_version
        assert data["docs"] == "/docs"
        assert data["redoc"] == "/redoc"


class TestHealthEndpoint:
    """Test health check endpoint."""
    
    def test_health_check_response(self, test_client):
        """Test health check endpoint response."""
        response = test_client.get("/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "fxml4-api"


class TestExceptionHandlers:
    """Test exception handlers."""
    
    def test_404_handler(self, test_client):
        """Test 404 not found handler."""
        response = test_client.get("/nonexistent-endpoint")
        assert response.status_code == 404
        
        data = response.json()
        assert data["detail"] == "Not found"
    
    def test_405_method_not_allowed(self, test_client):
        """Test method not allowed response."""
        # Try POST on GET-only endpoint
        response = test_client.post("/health")
        assert response.status_code == 405


class TestLifespan:
    """Test application lifespan manager."""
    
    @pytest.mark.asyncio
    async def test_lifespan_startup_shutdown(self):
        """Test lifespan startup and shutdown."""
        app = Mock()
        
        with patch('fxml4_web.api.main.logger') as mock_logger:
            # Use lifespan as async context manager
            async with lifespan(app):
                # Startup should have been logged
                mock_logger.info.assert_any_call("Starting FXML4 API...")
            
            # Shutdown should have been logged
            mock_logger.info.assert_any_call("Shutting down FXML4 API...")


class TestAPIDocumentation:
    """Test API documentation endpoints."""
    
    def test_swagger_ui_available(self, test_client):
        """Test that Swagger UI is available."""
        response = test_client.get("/docs")
        assert response.status_code == 200
        assert "swagger" in response.text.lower() or "openapi" in response.text.lower()
    
    def test_redoc_available(self, test_client):
        """Test that ReDoc is available."""
        response = test_client.get("/redoc")
        assert response.status_code == 200
        assert "redoc" in response.text.lower()
    
    def test_openapi_json_available(self, test_client):
        """Test that OpenAPI JSON schema is available."""
        response = test_client.get("/openapi.json")
        assert response.status_code == 200
        
        schema = response.json()
        assert "openapi" in schema
        assert "info" in schema
        assert schema["info"]["title"] == "Test API"
        assert schema["info"]["version"] == "0.1.0"


class TestCORSConfiguration:
    """Test CORS configuration."""
    
    def test_cors_preflight_request(self, test_client, api_config):
        """Test CORS preflight request."""
        response = test_client.options(
            "/api/v1/market/data",
            headers={
                "Origin": api_config.cors_origins[0],
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "Content-Type"
            }
        )
        
        # Should allow the origin
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == api_config.cors_origins[0]
        assert response.headers.get("access-control-allow-credentials") == "true"
    
    def test_cors_actual_request(self, test_client, api_config):
        """Test CORS headers on actual request."""
        response = test_client.get(
            "/health",
            headers={"Origin": api_config.cors_origins[0]}
        )
        
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == api_config.cors_origins[0]
    
    def test_cors_disallowed_origin(self, test_client):
        """Test CORS with disallowed origin."""
        response = test_client.options(
            "/api/v1/market/data",
            headers={
                "Origin": "http://evil.com",
                "Access-Control-Request-Method": "GET"
            }
        )
        
        # Should not include the evil origin in response
        assert response.headers.get("access-control-allow-origin") != "http://evil.com"


class TestRouterIntegration:
    """Test router integration."""
    
    def test_auth_router_integrated(self, test_client):
        """Test that auth router is integrated."""
        # Should be able to access auth endpoints
        response = test_client.post(
            "/api/v1/auth/token",
            data={"username": "test", "password": "test"}
        )
        # Will fail authentication but endpoint should exist
        assert response.status_code in [401, 422]  # Unauthorized or validation error
    
    def test_market_router_integrated(self, test_client):
        """Test that market router is integrated."""
        # Try to access a market endpoint (may require auth)
        response = test_client.get("/api/v1/market/symbols")
        # Should get 401 or actual data
        assert response.status_code in [200, 401]
    
    def test_trading_router_integrated(self, test_client):
        """Test that trading router is integrated."""
        response = test_client.get("/api/v1/trading/positions")
        assert response.status_code in [200, 401]
    
    def test_backtest_router_integrated(self, test_client):
        """Test that backtest router is integrated."""
        response = test_client.get("/api/v1/backtest/strategies")
        assert response.status_code in [200, 401]
    
    def test_analytics_router_integrated(self, test_client):
        """Test that analytics router is integrated."""
        response = test_client.get("/api/v1/analytics/performance")
        assert response.status_code in [200, 401]


class TestErrorResponses:
    """Test error response formats."""
    
    def test_json_error_response(self, test_client):
        """Test that errors return JSON responses."""
        response = test_client.get("/api/v1/nonexistent")
        assert response.status_code == 404
        
        # Should be valid JSON
        data = response.json()
        assert isinstance(data, dict)
        assert "detail" in data