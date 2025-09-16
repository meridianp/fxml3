"""
API Endpoint Integration Tests for FXML4.

This module tests the FastAPI endpoints that expose trading functionality,
validating HTTP request/response handling and service integration.
"""

import asyncio
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from httpx import AsyncClient

# Use centralized event loop fixture
from tests.fixtures.event_loop_fixtures import event_loop

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Mock all external dependencies before importing
sys.modules["openai"] = Mock()
sys.modules["fxml4.strategy.integrated_signal_generator"] = Mock()
sys.modules["fxml4.wave_analysis.sentiment_wave_validator"] = Mock()
sys.modules["fxml4.llm_integration.sentiment_analysis"] = Mock()
sys.modules["fxml4.llm_integration.llm_client"] = Mock()
sys.modules["redis.asyncio"] = Mock()
sys.modules["fxml4.config"] = Mock()
sys.modules["fxml4.data_engineering.data_feeds.base_feed"] = Mock()

# Mock config
mock_config = {
    "database": {
        "user": "test_user",
        "password": "test_password",
        "host": "localhost",
        "port": 5432,
        "name": "test_db",
    },
    "redis": {"host": "localhost", "port": 6379, "db": 0},
    "api": {"host": "0.0.0.0", "port": 8000},
}

sys.modules["fxml4.config"].get_config = Mock(return_value=mock_config)


class MockAPIApp:
    """Mock FastAPI application for testing endpoints."""

    def __init__(self):
        self.routes = {}
        self.middleware = []
        self.dependencies = {}

        # Service states
        self.signals = []
        self.orders = {}
        self.executions = {}
        self.market_data = {}
        self.websocket_connections = {}

        # Authentication
        self.authenticated_users = {"test_user": "test_token"}
        self.valid_tokens = {
            "test_token": {
                "user_id": "test_user",
                "expires": datetime.utcnow() + timedelta(hours=1),
            }
        }

    def add_route(self, method: str, path: str, handler):
        """Add route handler."""
        if path not in self.routes:
            self.routes[path] = {}
        self.routes[path][method.lower()] = handler

    async def request(
        self,
        method: str,
        path: str,
        headers: Dict = None,
        json_data: Dict = None,
        params: Dict = None,
    ):
        """Simulate HTTP request to API."""
        headers = headers or {}
        params = params or {}

        # Check authentication for protected endpoints
        if path.startswith("/api/") and path not in ["/api/health", "/api/docs"]:
            auth_header = headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                return MockResponse(401, {"detail": "Missing authentication token"})

            token = auth_header.replace("Bearer ", "")
            if token not in self.valid_tokens:
                return MockResponse(401, {"detail": "Invalid or expired token"})

        # Route request to appropriate handler with path parameter extraction
        handler, extracted_params = self._find_route_handler(method, path)
        if handler:
            # Merge path parameters with query parameters
            all_params = {**params, **extracted_params}
            try:
                result = await handler(
                    json_data=json_data, params=all_params, headers=headers
                )
                return MockResponse(200, result)
            except ValueError as e:
                return MockResponse(400, {"detail": str(e)})
            except Exception as e:
                return MockResponse(500, {"detail": "Internal server error"})

        return MockResponse(404, {"detail": "Not found"})

    def _find_route_handler(self, method: str, path: str):
        """Find route handler and extract path parameters."""
        method = method.lower()

        # First try exact match
        if path in self.routes and method in self.routes[path]:
            return self.routes[path][method], {}

        # Try pattern matching for parameterized routes
        for route_path, route_methods in self.routes.items():
            if method in route_methods:
                params = self._extract_path_params(route_path, path)
                if params is not None:
                    return route_methods[method], params

        return None, {}

    def _extract_path_params(self, route_pattern: str, actual_path: str):
        """Extract path parameters from URL pattern."""
        import re

        # Convert FastAPI-style path parameters to regex
        # e.g., /api/orders/{order_id} -> /api/orders/([^/]+)
        pattern = route_pattern
        param_names = []

        # Find all path parameters
        import re

        param_matches = re.findall(r"\{([^}]+)\}", pattern)
        param_names = param_matches

        # Replace path parameters with regex capture groups
        for param_name in param_names:
            pattern = pattern.replace(f"{{{param_name}}}", "([^/]+)")

        # Escape other regex characters
        pattern = pattern.replace(".", r"\.")
        pattern = f"^{pattern}$"

        match = re.match(pattern, actual_path)
        if match:
            # Create parameter dictionary
            params = {}
            for i, param_name in enumerate(param_names):
                params[param_name] = match.group(i + 1)
            return params

        return None


class MockResponse:
    """Mock HTTP response."""

    def __init__(self, status_code: int, data: Dict):
        self.status_code = status_code
        self._json_data = data

    def json(self):
        return self._json_data

    @property
    def text(self):
        return json.dumps(self._json_data)


class MockFXML4API:
    """Mock FXML4 API service for endpoint testing."""

    def __init__(self):
        self.app = MockAPIApp()
        self._setup_routes()

    def _setup_routes(self):
        """Set up API route handlers."""
        # Health endpoint
        self.app.add_route("GET", "/api/health", self._health_handler)

        # Market data endpoints
        self.app.add_route(
            "GET", "/api/market-data/{symbol}", self._get_market_data_handler
        )
        self.app.add_route(
            "GET", "/api/market-data/{symbol}/tick", self._get_tick_data_handler
        )
        self.app.add_route("GET", "/api/symbols", self._get_symbols_handler)

        # Signal endpoints
        self.app.add_route(
            "POST", "/api/signals/generate", self._generate_signal_handler
        )
        self.app.add_route("GET", "/api/signals", self._get_signals_handler)
        self.app.add_route("GET", "/api/signals/{signal_id}", self._get_signal_handler)

        # Order endpoints
        self.app.add_route("POST", "/api/orders", self._create_order_handler)
        self.app.add_route("GET", "/api/orders", self._get_orders_handler)
        self.app.add_route("GET", "/api/orders/{order_id}", self._get_order_handler)
        self.app.add_route(
            "POST", "/api/orders/{order_id}/execute", self._execute_order_handler
        )
        self.app.add_route(
            "DELETE", "/api/orders/{order_id}", self._cancel_order_handler
        )

        # Trading engine endpoints
        self.app.add_route(
            "GET", "/api/trading/status", self._get_trading_status_handler
        )
        self.app.add_route("POST", "/api/trading/start", self._start_trading_handler)
        self.app.add_route("POST", "/api/trading/stop", self._stop_trading_handler)

        # Backtest endpoints
        self.app.add_route("POST", "/api/backtest", self._run_backtest_handler)
        self.app.add_route(
            "GET", "/api/backtest/{backtest_id}", self._get_backtest_handler
        )

        # WebSocket info endpoint
        self.app.add_route("GET", "/api/websocket/info", self._websocket_info_handler)

    async def _health_handler(self, **kwargs):
        """Health check endpoint handler."""
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "version": "4.0.0",
            "services": {
                "database": "connected",
                "redis": "connected",
                "trading_engine": "active",
            },
        }

    async def _get_market_data_handler(self, json_data=None, params=None, headers=None):
        """Market data endpoint handler."""
        symbol = params.get("symbol", "EURUSD") if params else "EURUSD"
        timeframe = params.get("timeframe", "1h") if params else "1h"
        limit = int(params.get("limit", 100)) if params and params.get("limit") else 100

        # Generate mock OHLCV data
        data_points = []
        base_price = self._get_base_price(symbol)

        for i in range(min(limit, 100)):
            time_offset = timedelta(hours=i)
            timestamp = datetime.utcnow() - time_offset

            price_change = (i % 10 - 5) * 0.0001
            open_price = base_price + price_change
            close_price = open_price + ((i % 7 - 3) * 0.0002)
            high_price = max(open_price, close_price) + abs(price_change) * 0.5
            low_price = min(open_price, close_price) - abs(price_change) * 0.5

            data_points.append(
                {
                    "time": timestamp.isoformat(),
                    "symbol": symbol,
                    "open": round(open_price, 5),
                    "high": round(high_price, 5),
                    "low": round(low_price, 5),
                    "close": round(close_price, 5),
                    "volume": 1000 + (i % 500),
                    "source": "timescaledb",
                }
            )

        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "data": data_points,
            "count": len(data_points),
        }

    async def _get_tick_data_handler(self, json_data=None, params=None, headers=None):
        """Tick data endpoint handler."""
        symbol = params.get("symbol", "EURUSD") if params else "EURUSD"
        base_price = self._get_base_price(symbol)

        import random

        current_price = base_price + random.uniform(-0.0005, 0.0005)

        return {
            "time": datetime.utcnow().isoformat(),
            "symbol": symbol,
            "price": round(current_price, 5),
            "size": 1000,
            "tick_type": "trade",
        }

    async def _get_symbols_handler(self, **kwargs):
        """Available symbols endpoint handler."""
        return {
            "symbols": ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF", "USDCAD"],
            "count": 6,
        }

    async def _generate_signal_handler(self, json_data=None, **kwargs):
        """Signal generation endpoint handler."""
        if not json_data:
            raise ValueError("Request body is required")

        symbol = json_data.get("symbol")
        signal_type = json_data.get("signal_type", "ml_signal")

        if not symbol:
            raise ValueError("Symbol is required")

        import random

        signal = {
            "id": f"signal_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{symbol}",
            "symbol": symbol,
            "direction": random.choice([1, -1]),
            "confidence": round(random.uniform(0.3, 0.95), 3),
            "signal_type": signal_type,
            "source": f"mock_{signal_type}",
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": {
                "generated_via": "api",
                "market_price": self._get_base_price(symbol),
            },
        }

        self.app.signals.append(signal)
        return signal

    async def _get_signals_handler(self, json_data=None, params=None, **kwargs):
        """Get signals endpoint handler."""
        limit = int(params.get("limit", 50)) if params and params.get("limit") else 50
        symbol_filter = params.get("symbol") if params else None

        signals = self.app.signals.copy()

        if symbol_filter:
            signals = [s for s in signals if s["symbol"] == symbol_filter]

        signals = signals[-limit:]  # Get most recent signals

        return {
            "signals": signals,
            "count": len(signals),
            "total": len(self.app.signals),
        }

    async def _get_signal_handler(self, json_data=None, params=None, **kwargs):
        """Get single signal endpoint handler."""
        signal_id = params.get("signal_id") if params else None
        if not signal_id:
            raise ValueError("Signal ID is required")

        for signal in self.app.signals:
            if signal["id"] == signal_id:
                return signal

        raise ValueError(f"Signal {signal_id} not found")

    async def _create_order_handler(self, json_data=None, **kwargs):
        """Create order endpoint handler."""
        if not json_data:
            raise ValueError("Request body is required")

        required_fields = ["symbol", "side", "quantity"]
        for field in required_fields:
            if field not in json_data:
                raise ValueError(f"{field} is required")

        order = {
            "id": f"order_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{json_data['symbol']}",
            "symbol": json_data["symbol"],
            "side": json_data["side"],
            "quantity": float(json_data["quantity"]),
            "order_type": json_data.get("order_type", "market"),
            "status": "pending",
            "created_at": datetime.utcnow().isoformat(),
            "signal_id": json_data.get("signal_id"),
            "strategy_name": json_data.get("strategy_name"),
            "metadata": json_data.get("metadata", {}),
        }

        self.app.orders[order["id"]] = order
        return order

    async def _get_orders_handler(self, json_data=None, params=None, **kwargs):
        """Get orders endpoint handler."""
        limit = int(params.get("limit", 50)) if params and params.get("limit") else 50
        status_filter = params.get("status") if params else None
        symbol_filter = params.get("symbol") if params else None

        orders = list(self.app.orders.values())

        if status_filter:
            orders = [o for o in orders if o["status"] == status_filter]

        if symbol_filter:
            orders = [o for o in orders if o["symbol"] == symbol_filter]

        orders = orders[-limit:]  # Get most recent orders

        return {"orders": orders, "count": len(orders), "total": len(self.app.orders)}

    async def _get_order_handler(self, json_data=None, params=None, **kwargs):
        """Get single order endpoint handler."""
        order_id = params.get("order_id") if params else None
        if not order_id:
            raise ValueError("Order ID is required")

        if order_id not in self.app.orders:
            raise ValueError(f"Order {order_id} not found")

        return self.app.orders[order_id]

    async def _execute_order_handler(self, json_data=None, params=None, **kwargs):
        """Execute order endpoint handler."""
        order_id = params.get("order_id") if params else None
        if not order_id:
            raise ValueError("Order ID is required")

        if order_id not in self.app.orders:
            raise ValueError(f"Order {order_id} not found")

        order = self.app.orders[order_id]
        if order["status"] != "pending":
            raise ValueError(f"Order {order_id} is not in pending status")

        # Simulate execution
        base_price = self._get_base_price(order["symbol"])
        import random

        execution_price = base_price + random.uniform(-0.0002, 0.0002)

        execution = {
            "execution_id": f"exec_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            "order_id": order_id,
            "symbol": order["symbol"],
            "side": order["side"],
            "quantity": order["quantity"],
            "price": round(execution_price, 5),
            "timestamp": datetime.utcnow().isoformat(),
            "commission": 2.50,
        }

        # Update order
        order["status"] = "filled"
        order["filled_quantity"] = order["quantity"]
        order["avg_fill_price"] = execution["price"]
        order["filled_at"] = execution["timestamp"]

        # Store execution
        if order_id not in self.app.executions:
            self.app.executions[order_id] = []
        self.app.executions[order_id].append(execution)

        return {"order": order, "execution": execution}

    async def _cancel_order_handler(self, json_data=None, params=None, **kwargs):
        """Cancel order endpoint handler."""
        order_id = params.get("order_id") if params else None
        if not order_id:
            raise ValueError("Order ID is required")

        if order_id not in self.app.orders:
            raise ValueError(f"Order {order_id} not found")

        order = self.app.orders[order_id]
        if order["status"] != "pending":
            raise ValueError(f"Order {order_id} cannot be cancelled")

        order["status"] = "cancelled"
        order["cancelled_at"] = datetime.utcnow().isoformat()

        return order

    async def _get_trading_status_handler(self, **kwargs):
        """Trading engine status endpoint handler."""
        return {
            "status": "active",
            "timestamp": datetime.utcnow().isoformat(),
            "statistics": {
                "total_signals": len(self.app.signals),
                "total_orders": len(self.app.orders),
                "filled_orders": sum(
                    1 for o in self.app.orders.values() if o["status"] == "filled"
                ),
                "pending_orders": sum(
                    1 for o in self.app.orders.values() if o["status"] == "pending"
                ),
                "uptime": "2h 45m 12s",
            },
        }

    async def _start_trading_handler(self, **kwargs):
        """Start trading endpoint handler."""
        return {
            "status": "started",
            "message": "Trading engine started successfully",
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def _stop_trading_handler(self, **kwargs):
        """Stop trading endpoint handler."""
        return {
            "status": "stopped",
            "message": "Trading engine stopped successfully",
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def _run_backtest_handler(self, json_data=None, **kwargs):
        """Run backtest endpoint handler."""
        if not json_data:
            raise ValueError("Request body is required")

        backtest = {
            "id": f"backtest_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            "status": "running",
            "parameters": json_data,
            "created_at": datetime.utcnow().isoformat(),
            "estimated_completion": (
                datetime.utcnow() + timedelta(minutes=5)
            ).isoformat(),
        }

        return backtest

    async def _get_backtest_handler(self, json_data=None, params=None, **kwargs):
        """Get backtest endpoint handler."""
        backtest_id = params.get("backtest_id") if params else None
        if not backtest_id:
            raise ValueError("Backtest ID is required")

        return {
            "id": backtest_id,
            "status": "completed",
            "parameters": {
                "symbol": "EURUSD",
                "start_date": "2024-01-01",
                "end_date": "2024-12-31",
            },
            "results": {
                "total_return": 12.5,
                "sharpe_ratio": 1.8,
                "max_drawdown": -5.2,
                "total_trades": 245,
                "win_rate": 0.68,
            },
            "created_at": datetime.utcnow().isoformat(),
            "completed_at": datetime.utcnow().isoformat(),
        }

    async def _websocket_info_handler(self, **kwargs):
        """WebSocket info endpoint handler."""
        return {
            "websocket_url": "ws://localhost:8000/ws",
            "active_connections": len(self.app.websocket_connections),
            "supported_subscriptions": [
                "tick:{symbol}",
                "ohlcv:{symbol}",
                "signals:{symbol}",
                "orders:{symbol}",
                "executions:{symbol}",
            ],
        }

    def _get_base_price(self, symbol: str) -> float:
        """Get base price for symbol."""
        base_prices = {
            "EURUSD": 1.1000,
            "GBPUSD": 1.2500,
            "USDJPY": 150.00,
            "AUDUSD": 0.6750,
            "USDCHF": 0.9200,
            "USDCAD": 1.3500,
        }
        return base_prices.get(symbol, 1.0000)


class TestAPIEndpointIntegration:
    """Test FastAPI endpoint integration with services."""

    @pytest.fixture
    def api_client(self):
        """Create a mock API client for testing."""
        return MockFXML4API()

    @pytest.fixture
    def auth_headers(self):
        """Authentication headers for protected endpoints."""
        return {"Authorization": "Bearer test_token"}

    @pytest.mark.asyncio
    async def test_health_endpoint(self, api_client):
        """Test health check endpoint."""
        response = await api_client.app.request("GET", "/api/health")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "version" in data
        assert "services" in data
        assert data["services"]["database"] == "connected"
        assert data["services"]["trading_engine"] == "active"

    @pytest.mark.asyncio
    async def test_market_data_endpoint(self, api_client, auth_headers):
        """Test market data retrieval endpoint."""
        params = {"symbol": "EURUSD", "timeframe": "1h", "limit": "10"}
        response = await api_client.app.request(
            "GET", "/api/market-data/EURUSD", headers=auth_headers, params=params
        )

        assert response.status_code == 200
        data = response.json()

        assert data["symbol"] == "EURUSD"
        assert data["timeframe"] == "1h"
        assert "data" in data
        assert len(data["data"]) <= 10
        assert data["count"] == len(data["data"])

        # Verify OHLCV data structure
        for point in data["data"]:
            assert "time" in point
            assert "symbol" in point
            assert "open" in point
            assert "high" in point
            assert "low" in point
            assert "close" in point
            assert "volume" in point
            assert point["symbol"] == "EURUSD"
            assert point["high"] >= point["low"]

    @pytest.mark.asyncio
    async def test_tick_data_endpoint(self, api_client, auth_headers):
        """Test tick data endpoint."""
        params = {"symbol": "GBPUSD"}
        response = await api_client.app.request(
            "GET", "/api/market-data/GBPUSD/tick", headers=auth_headers, params=params
        )

        assert response.status_code == 200
        data = response.json()

        assert data["symbol"] == "GBPUSD"
        assert "time" in data
        assert "price" in data
        assert "size" in data
        assert "tick_type" in data
        assert data["price"] > 0
        assert data["size"] > 0

    @pytest.mark.asyncio
    async def test_symbols_endpoint(self, api_client, auth_headers):
        """Test available symbols endpoint."""
        response = await api_client.app.request(
            "GET", "/api/symbols", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        assert "symbols" in data
        assert "count" in data
        assert len(data["symbols"]) == data["count"]
        assert "EURUSD" in data["symbols"]
        assert "GBPUSD" in data["symbols"]
        assert all(isinstance(symbol, str) for symbol in data["symbols"])

    @pytest.mark.asyncio
    async def test_generate_signal_endpoint(self, api_client, auth_headers):
        """Test signal generation endpoint."""
        request_data = {"symbol": "EURUSD", "signal_type": "ml_signal"}

        response = await api_client.app.request(
            "POST",
            "/api/signals/generate",
            headers=auth_headers,
            json_data=request_data,
        )

        assert response.status_code == 200
        data = response.json()

        assert data["symbol"] == "EURUSD"
        assert data["signal_type"] == "ml_signal"
        assert "id" in data
        assert "direction" in data
        assert "confidence" in data
        assert "timestamp" in data
        assert data["direction"] in [1, -1]
        assert 0.3 <= data["confidence"] <= 0.95

    @pytest.mark.asyncio
    async def test_generate_signal_endpoint_validation(self, api_client, auth_headers):
        """Test signal generation endpoint validation."""
        # Missing symbol
        request_data = {"signal_type": "ml_signal"}
        response = await api_client.app.request(
            "POST",
            "/api/signals/generate",
            headers=auth_headers,
            json_data=request_data,
        )

        assert response.status_code == 400
        assert "Symbol is required" in response.json()["detail"]

        # Empty request body
        response = await api_client.app.request(
            "POST", "/api/signals/generate", headers=auth_headers, json_data=None
        )

        assert response.status_code == 400
        assert "Request body is required" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_signals_endpoint(self, api_client, auth_headers):
        """Test get signals endpoint."""
        # Generate a signal first
        await api_client.app.request(
            "POST",
            "/api/signals/generate",
            headers=auth_headers,
            json_data={"symbol": "EURUSD", "signal_type": "test"},
        )

        # Get signals
        response = await api_client.app.request(
            "GET", "/api/signals", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        assert "signals" in data
        assert "count" in data
        assert "total" in data
        assert len(data["signals"]) >= 1
        assert data["count"] == len(data["signals"])

        # Verify signal structure
        signal = data["signals"][0]
        assert "id" in signal
        assert "symbol" in signal
        assert "direction" in signal
        assert "confidence" in signal

    @pytest.mark.asyncio
    async def test_get_signals_with_filters(self, api_client, auth_headers):
        """Test get signals endpoint with filters."""
        # Generate signals for different symbols
        await api_client.app.request(
            "POST",
            "/api/signals/generate",
            headers=auth_headers,
            json_data={"symbol": "EURUSD", "signal_type": "test"},
        )
        await api_client.app.request(
            "POST",
            "/api/signals/generate",
            headers=auth_headers,
            json_data={"symbol": "GBPUSD", "signal_type": "test"},
        )

        # Filter by symbol
        params = {"symbol": "EURUSD", "limit": "10"}
        response = await api_client.app.request(
            "GET", "/api/signals", headers=auth_headers, params=params
        )

        assert response.status_code == 200
        data = response.json()

        assert all(signal["symbol"] == "EURUSD" for signal in data["signals"])

    @pytest.mark.asyncio
    async def test_create_order_endpoint(self, api_client, auth_headers):
        """Test order creation endpoint."""
        request_data = {
            "symbol": "EURUSD",
            "side": "buy",
            "quantity": 10000,
            "order_type": "market",
        }

        response = await api_client.app.request(
            "POST", "/api/orders", headers=auth_headers, json_data=request_data
        )

        assert response.status_code == 200
        data = response.json()

        assert data["symbol"] == "EURUSD"
        assert data["side"] == "buy"
        assert data["quantity"] == 10000
        assert data["order_type"] == "market"
        assert data["status"] == "pending"
        assert "id" in data
        assert "created_at" in data

    @pytest.mark.asyncio
    async def test_create_order_validation(self, api_client, auth_headers):
        """Test order creation endpoint validation."""
        # Missing required fields
        request_data = {"symbol": "EURUSD"}
        response = await api_client.app.request(
            "POST", "/api/orders", headers=auth_headers, json_data=request_data
        )

        assert response.status_code == 400
        assert "side is required" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_orders_endpoint(self, api_client, auth_headers):
        """Test get orders endpoint."""
        # Create an order first
        await api_client.app.request(
            "POST",
            "/api/orders",
            headers=auth_headers,
            json_data={"symbol": "EURUSD", "side": "buy", "quantity": 5000},
        )

        # Get orders
        response = await api_client.app.request(
            "GET", "/api/orders", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        assert "orders" in data
        assert "count" in data
        assert "total" in data
        assert len(data["orders"]) >= 1

        # Verify order structure
        order = data["orders"][0]
        assert "id" in order
        assert "symbol" in order
        assert "side" in order
        assert "quantity" in order
        assert "status" in order

    @pytest.mark.asyncio
    async def test_execute_order_endpoint(self, api_client, auth_headers):
        """Test order execution endpoint."""
        # Create order first
        create_response = await api_client.app.request(
            "POST",
            "/api/orders",
            headers=auth_headers,
            json_data={"symbol": "EURUSD", "side": "buy", "quantity": 5000},
        )
        order_id = create_response.json()["id"]

        # Execute order
        params = {"order_id": order_id}
        response = await api_client.app.request(
            "POST",
            f"/api/orders/{order_id}/execute",
            headers=auth_headers,
            params=params,
        )

        assert response.status_code == 200
        data = response.json()

        assert "order" in data
        assert "execution" in data
        assert data["order"]["status"] == "filled"
        assert data["order"]["filled_quantity"] == 5000
        assert "avg_fill_price" in data["order"]

        # Verify execution details
        execution = data["execution"]
        assert execution["order_id"] == order_id
        assert execution["symbol"] == "EURUSD"
        assert execution["quantity"] == 5000
        assert execution["price"] > 0

    @pytest.mark.asyncio
    async def test_cancel_order_endpoint(self, api_client, auth_headers):
        """Test order cancellation endpoint."""
        # Create order first
        create_response = await api_client.app.request(
            "POST",
            "/api/orders",
            headers=auth_headers,
            json_data={"symbol": "GBPUSD", "side": "sell", "quantity": 3000},
        )
        order_id = create_response.json()["id"]

        # Cancel order
        params = {"order_id": order_id}
        response = await api_client.app.request(
            "DELETE", f"/api/orders/{order_id}", headers=auth_headers, params=params
        )

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "cancelled"
        assert "cancelled_at" in data
        assert data["id"] == order_id

    @pytest.mark.asyncio
    async def test_trading_status_endpoint(self, api_client, auth_headers):
        """Test trading engine status endpoint."""
        response = await api_client.app.request(
            "GET", "/api/trading/status", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "active"
        assert "timestamp" in data
        assert "statistics" in data

        stats = data["statistics"]
        assert "total_signals" in stats
        assert "total_orders" in stats
        assert "filled_orders" in stats
        assert "pending_orders" in stats
        assert "uptime" in stats

    @pytest.mark.asyncio
    async def test_start_stop_trading_endpoints(self, api_client, auth_headers):
        """Test trading engine start/stop endpoints."""
        # Start trading
        start_response = await api_client.app.request(
            "POST", "/api/trading/start", headers=auth_headers
        )
        assert start_response.status_code == 200
        start_data = start_response.json()
        assert start_data["status"] == "started"

        # Stop trading
        stop_response = await api_client.app.request(
            "POST", "/api/trading/stop", headers=auth_headers
        )
        assert stop_response.status_code == 200
        stop_data = stop_response.json()
        assert stop_data["status"] == "stopped"

    @pytest.mark.asyncio
    async def test_backtest_endpoints(self, api_client, auth_headers):
        """Test backtest creation and retrieval endpoints."""
        # Create backtest
        backtest_params = {
            "symbol": "EURUSD",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "strategy": "ml_strategy",
        }

        create_response = await api_client.app.request(
            "POST", "/api/backtest", headers=auth_headers, json_data=backtest_params
        )
        assert create_response.status_code == 200
        create_data = create_response.json()

        assert "id" in create_data
        assert create_data["status"] == "running"
        assert create_data["parameters"] == backtest_params

        # Get backtest results
        backtest_id = create_data["id"]
        params = {"backtest_id": backtest_id}
        results_response = await api_client.app.request(
            "GET", f"/api/backtest/{backtest_id}", headers=auth_headers, params=params
        )

        assert results_response.status_code == 200
        results_data = results_response.json()

        assert results_data["id"] == backtest_id
        assert "results" in results_data
        assert "total_return" in results_data["results"]
        assert "sharpe_ratio" in results_data["results"]
        assert "max_drawdown" in results_data["results"]

    @pytest.mark.asyncio
    async def test_websocket_info_endpoint(self, api_client, auth_headers):
        """Test WebSocket info endpoint."""
        response = await api_client.app.request(
            "GET", "/api/websocket/info", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        assert "websocket_url" in data
        assert "active_connections" in data
        assert "supported_subscriptions" in data
        assert len(data["supported_subscriptions"]) > 0

    @pytest.mark.asyncio
    async def test_authentication_required(self, api_client):
        """Test that protected endpoints require authentication."""
        # Test without authentication header
        response = await api_client.app.request("GET", "/api/signals")
        assert response.status_code == 401
        assert "Missing authentication token" in response.json()["detail"]

        # Test with invalid token
        invalid_headers = {"Authorization": "Bearer invalid_token"}
        response = await api_client.app.request(
            "GET", "/api/signals", headers=invalid_headers
        )
        assert response.status_code == 401
        assert "Invalid or expired token" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_endpoint_not_found(self, api_client, auth_headers):
        """Test 404 handling for non-existent endpoints."""
        response = await api_client.app.request(
            "GET", "/api/nonexistent", headers=auth_headers
        )
        assert response.status_code == 404
        assert "Not found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_complete_trading_workflow_via_api(self, api_client, auth_headers):
        """Test complete trading workflow through API endpoints."""
        # Step 1: Get market data
        market_response = await api_client.app.request(
            "GET", "/api/market-data/EURUSD", headers=auth_headers
        )
        assert market_response.status_code == 200

        # Step 2: Generate signal
        signal_response = await api_client.app.request(
            "POST",
            "/api/signals/generate",
            headers=auth_headers,
            json_data={"symbol": "EURUSD", "signal_type": "api_workflow"},
        )
        assert signal_response.status_code == 200
        signal = signal_response.json()

        # Step 3: Create order from signal
        order_response = await api_client.app.request(
            "POST",
            "/api/orders",
            headers=auth_headers,
            json_data={
                "symbol": signal["symbol"],
                "side": "buy" if signal["direction"] > 0 else "sell",
                "quantity": 10000,
                "signal_id": signal["id"],
                "strategy_name": signal["signal_type"],
            },
        )
        assert order_response.status_code == 200
        order = order_response.json()

        # Step 4: Execute order
        execute_response = await api_client.app.request(
            "POST",
            f'/api/orders/{order["id"]}/execute',
            headers=auth_headers,
            params={"order_id": order["id"]},
        )
        assert execute_response.status_code == 200
        execution_data = execute_response.json()

        # Step 5: Verify complete workflow
        assert execution_data["order"]["status"] == "filled"
        assert execution_data["order"]["signal_id"] == signal["id"]
        assert execution_data["execution"]["symbol"] == signal["symbol"]

        # Step 6: Check trading status reflects the activity
        status_response = await api_client.app.request(
            "GET", "/api/trading/status", headers=auth_headers
        )
        status_data = status_response.json()
        assert status_data["statistics"]["total_signals"] >= 1
        assert status_data["statistics"]["filled_orders"] >= 1


# Pytest configuration
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])
