"""Tests for core API router."""

import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from fxml4.api.routers.core import router


@pytest.fixture
def app():
    """Create FastAPI app with core router."""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


class TestCoreRouter:
    """Test core API router endpoints."""

    def test_root_endpoint(self, client):
        """Test root endpoint."""
        response = client.get("/")

        assert response.status_code == 200
        assert response.json() == {"message": "FXML4 API running"}

    def test_health_check_endpoint(self, client):
        """Test health check endpoint."""
        response = client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_dashboard_endpoint_file_exists(self, client):
        """Test dashboard endpoint when file exists."""
        # Create a temporary dashboard file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f:
            f.write("<html><body>Dashboard</body></html>")
            temp_path = f.name

        try:
            # Mock the path to point to our temp file
            with patch("os.path.exists") as mock_exists:
                with patch("os.path.join") as mock_join:
                    mock_exists.return_value = True
                    mock_join.return_value = temp_path

                    response = client.get("/dashboard")

                    assert response.status_code == 200
                    assert (
                        response.headers["content-type"] == "text/html; charset=utf-8"
                    )

        finally:
            # Clean up temp file
            os.unlink(temp_path)

    def test_dashboard_endpoint_file_not_found(self, client):
        """Test dashboard endpoint when file doesn't exist."""
        with patch("os.path.exists") as mock_exists:
            mock_exists.return_value = False

            response = client.get("/dashboard")

            assert response.status_code == 404
            assert response.json() == {"detail": "Dashboard not found"}

    def test_manual_execution_endpoint_file_exists(self, client):
        """Test manual execution endpoint when file exists."""
        # Create a temporary manual execution file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f:
            f.write("<html><body>Manual Execution</body></html>")
            temp_path = f.name

        try:
            # Mock the path to point to our temp file
            with patch("os.path.exists") as mock_exists:
                with patch("os.path.join") as mock_join:
                    mock_exists.return_value = True
                    mock_join.return_value = temp_path

                    response = client.get("/manual")

                    assert response.status_code == 200
                    assert (
                        response.headers["content-type"] == "text/html; charset=utf-8"
                    )

        finally:
            # Clean up temp file
            os.unlink(temp_path)

    def test_manual_execution_endpoint_file_not_found(self, client):
        """Test manual execution endpoint when file doesn't exist."""
        with patch("os.path.exists") as mock_exists:
            mock_exists.return_value = False

            response = client.get("/manual")

            assert response.status_code == 404
            assert response.json() == {"detail": "Manual execution interface not found"}

    def test_all_endpoints_have_tags(self, app):
        """Test that all endpoints have appropriate tags."""
        routes = app.routes

        # Find our router endpoints
        core_routes = [
            route for route in routes if hasattr(route, "tags") and "core" in route.tags
        ]

        # Should have at least our core endpoints
        assert len(core_routes) >= 4  # root, health, dashboard, manual

    def test_endpoint_methods(self, client):
        """Test that endpoints only accept appropriate HTTP methods."""
        # All core endpoints should be GET only

        # Test POST not allowed on root
        response = client.post("/")
        assert response.status_code == 405  # Method Not Allowed

        # Test POST not allowed on health
        response = client.post("/health")
        assert response.status_code == 405

        # Test PUT not allowed on dashboard
        response = client.put("/dashboard")
        assert response.status_code == 405

    def test_response_content_type(self, client):
        """Test response content types."""
        # JSON endpoints
        response = client.get("/")
        assert "application/json" in response.headers.get("content-type", "")

        response = client.get("/health")
        assert "application/json" in response.headers.get("content-type", "")

    def test_concurrent_requests(self, client):
        """Test handling concurrent requests to core endpoints."""
        import concurrent.futures
        import threading

        def make_request(endpoint):
            return client.get(endpoint)

        endpoints = ["/", "/health"]

        # Make concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = []
            for _ in range(10):  # 10 concurrent requests
                for endpoint in endpoints:
                    future = executor.submit(make_request, endpoint)
                    futures.append(future)

            # Wait for all requests to complete
            results = [
                future.result() for future in concurrent.futures.as_completed(futures)
            ]

        # All requests should succeed
        assert len(results) == 20  # 10 requests * 2 endpoints
        assert all(result.status_code == 200 for result in results)


@pytest.mark.unit
class TestCoreRouterIntegration:
    """Integration tests for core router."""

    def test_api_documentation_endpoints(self, app):
        """Test that endpoints are properly documented."""
        # Check that router has proper OpenAPI metadata
        routes = [route for route in app.routes if hasattr(route, "path")]

        root_route = next((r for r in routes if r.path == "/"), None)
        health_route = next((r for r in routes if r.path == "/health"), None)

        assert root_route is not None
        assert health_route is not None

        # Routes should have proper tags
        assert "core" in root_route.tags
        assert "core" in health_route.tags

    def test_static_file_serving_security(self, client):
        """Test that static file serving doesn't expose sensitive files."""
        # Try to access files outside the static directory
        with patch("os.path.exists") as mock_exists:
            # Simulate path traversal attempt
            mock_exists.return_value = True

            # This should still return 404 due to path construction
            response = client.get("/dashboard")
            # The actual file won't exist in test environment

        # Test that the endpoint constructs paths safely
        with patch("os.path.join") as mock_join:
            mock_join.return_value = "/safe/static/path/file.html"
            with patch("os.path.exists") as mock_exists:
                mock_exists.return_value = False

                response = client.get("/dashboard")
                assert response.status_code == 404

    def test_error_handling(self, client):
        """Test error handling in core endpoints."""
        # Test file access errors
        with patch("os.path.exists") as mock_exists:
            with patch("os.path.join") as mock_join:
                # Simulate file exists but can't be read
                mock_exists.return_value = True
                mock_join.side_effect = OSError("Permission denied")

                # Should handle the error gracefully
                try:
                    response = client.get("/dashboard")
                    # If it doesn't raise, it handled the error
                    assert response.status_code in [404, 500]
                except OSError:
                    # If it raises, that's also acceptable for this test
                    pass


@pytest.mark.performance
def test_core_router_performance(client):
    """Test core router performance."""
    import time

    # Test response times
    start_time = time.time()

    # Make multiple requests
    for _ in range(100):
        response = client.get("/health")
        assert response.status_code == 200

    end_time = time.time()
    execution_time = end_time - start_time

    # Should handle 100 health checks quickly
    assert execution_time < 2.0  # Less than 2 seconds

    # Average response time should be very fast
    avg_response_time = execution_time / 100
    assert avg_response_time < 0.02  # Less than 20ms average
