#!/usr/bin/env python3
"""
Consumer test for api_core_contract
Generated automatically by FXML4 Claude TDD framework
"""

import pytest
import requests
import json
from pact import Consumer, Provider, Like, EachLike, Term
from pact.verifier import Verifier

# Pact setup
pact = Consumer("frontend").has_pact_with(Provider("core"))


class TestApiCoreContractContract:
    """Consumer tests for core → frontend contract"""

    def setup_method(self):
        """Setup method run before each test"""
        pact.start()

    def teardown_method(self):
        """Teardown method run after each test"""
        pact.stop()

    def test_api_health_check(self):
        """Test: API health check"""
        # Given
        expected_response = {
            "status": "healthy",
            "timestamp": "2024-01-15T10:30:00Z",
            "version": "0.2.0",
        }

        pact.given("API is running").upon_receiving("API health check").with_request(
            method="GET",
            path="/health",
        ).will_respond_with(
            status=200,
            headers={"Content-Type": "application/json"},
            body=expected_response,
        )

        # When
        with pact:
            response = self._make_request(
                method="GET", path="/health", headers={}, params={}, json=None
            )

        # Then
        assert response.status_code == 200
        assert response.headers.get("Content-Type") == "application/json"

        response_data = response.json()
        # Add specific assertions based on the response structure
        self._assert_response_structure(response_data, expected_response)

    def test_user_authentication(self):
        """Test: User authentication"""
        # Given
        expected_response = {
            "access_token": "jwt_token_here",
            "refresh_token": "refresh_token_here",
            "expires_in": 3600,
            "user": {"id": 1, "username": "trader@fxml4.com", "role": "trader"},
        }

        pact.given("User credentials are valid").upon_receiving(
            "User authentication"
        ).with_request(
            method="POST",
            path="/auth/login",
            headers={"Content-Type": "application/json"},
            body={"username": "trader@fxml4.com", "password": "secure_password"},
        ).will_respond_with(
            status=200,
            headers={"Content-Type": "application/json"},
            body=expected_response,
        )

        # When
        with pact:
            response = self._make_request(
                method="POST",
                path="/auth/login",
                headers={"Content-Type": "application/json"},
                params={},
                json={"username": "trader@fxml4.com", "password": "secure_password"},
            )

        # Then
        assert response.status_code == 200
        assert response.headers.get("Content-Type") == "application/json"

        response_data = response.json()
        # Add specific assertions based on the response structure
        self._assert_response_structure(response_data, expected_response)

    def test_get_trading_signals(self):
        """Test: Get trading signals"""
        # Given
        expected_response = {
            "signals": [
                {
                    "id": "signal_123",
                    "symbol": "GBPUSD",
                    "timeframe": "1h",
                    "signal_type": "buy",
                    "strength": 0.85,
                    "price": 1.265,
                    "stop_loss": 1.26,
                    "take_profit": 1.275,
                    "timestamp": "2024-01-15T10:30:00Z",
                    "confidence": 0.92,
                    "risk_score": 0.25,
                }
            ],
            "metadata": {
                "total_signals": 1,
                "generated_at": "2024-01-15T10:30:00Z",
                "model_version": "v2.1.0",
            },
        }

        pact.given("Trading signals are available").upon_receiving(
            "Get trading signals"
        ).with_request(
            method="GET",
            path="/signals",
            headers={"Authorization": "Bearer jwt_token_here"},
            query={"symbol": "GBPUSD", "timeframe": "1h"},
        ).will_respond_with(
            status=200,
            headers={"Content-Type": "application/json"},
            body=expected_response,
        )

        # When
        with pact:
            response = self._make_request(
                method="GET",
                path="/signals",
                headers={"Authorization": "Bearer jwt_token_here"},
                params={"symbol": "GBPUSD", "timeframe": "1h"},
                json=None,
            )

        # Then
        assert response.status_code == 200
        assert response.headers.get("Content-Type") == "application/json"

        response_data = response.json()
        # Add specific assertions based on the response structure
        self._assert_response_structure(response_data, expected_response)

    def test_get_market_data(self):
        """Test: Get market data"""
        # Given
        expected_response = {
            "data": [
                {
                    "timestamp": "2024-01-15T10:30:00Z",
                    "open": 1.2645,
                    "high": 1.2655,
                    "low": 1.264,
                    "close": 1.265,
                    "volume": 1500000,
                }
            ],
            "metadata": {
                "symbol": "GBPUSD",
                "timeframe": "1m",
                "count": 1,
                "start_time": "2024-01-15T10:30:00Z",
                "end_time": "2024-01-15T10:30:00Z",
            },
        }

        pact.given("Market data is available").upon_receiving(
            "Get market data"
        ).with_request(
            method="GET",
            path="/data/market",
            headers={"Authorization": "Bearer jwt_token_here"},
            query={"symbol": "GBPUSD", "timeframe": "1m", "limit": "100"},
        ).will_respond_with(
            status=200,
            headers={"Content-Type": "application/json"},
            body=expected_response,
        )

        # When
        with pact:
            response = self._make_request(
                method="GET",
                path="/data/market",
                headers={"Authorization": "Bearer jwt_token_here"},
                params={"symbol": "GBPUSD", "timeframe": "1m", "limit": "100"},
                json=None,
            )

        # Then
        assert response.status_code == 200
        assert response.headers.get("Content-Type") == "application/json"

        response_data = response.json()
        # Add specific assertions based on the response structure
        self._assert_response_structure(response_data, expected_response)

    def test_run_backtest(self):
        """Test: Run backtest"""
        # Given
        expected_response = {
            "backtest_id": "bt_123456",
            "status": "queued",
            "estimated_completion": "2024-01-15T10:35:00Z",
            "message": "Backtest queued for execution",
        }

        pact.given("Backtest service is available").upon_receiving(
            "Run backtest"
        ).with_request(
            method="POST",
            path="/backtest",
            headers={
                "Authorization": "Bearer jwt_token_here",
                "Content-Type": "application/json",
            },
            body={
                "strategy": "gbpusd_ml_strategy",
                "symbol": "GBPUSD",
                "start_date": "2024-01-01",
                "end_date": "2024-01-15",
                "initial_capital": 10000,
                "parameters": {"risk_per_trade": 0.02, "max_drawdown": 0.06},
            },
        ).will_respond_with(
            status=202,
            headers={"Content-Type": "application/json"},
            body=expected_response,
        )

        # When
        with pact:
            response = self._make_request(
                method="POST",
                path="/backtest",
                headers={
                    "Authorization": "Bearer jwt_token_here",
                    "Content-Type": "application/json",
                },
                params={},
                json={
                    "strategy": "gbpusd_ml_strategy",
                    "symbol": "GBPUSD",
                    "start_date": "2024-01-01",
                    "end_date": "2024-01-15",
                    "initial_capital": 10000,
                    "parameters": {"risk_per_trade": 0.02, "max_drawdown": 0.06},
                },
            )

        # Then
        assert response.status_code == 202
        assert response.headers.get("Content-Type") == "application/json"

        response_data = response.json()
        # Add specific assertions based on the response structure
        self._assert_response_structure(response_data, expected_response)

    def test_place_trading_order(self):
        """Test: Place trading order"""
        # Given
        expected_response = {
            "order_id": "ord_789",
            "status": "pending",
            "symbol": "GBPUSD",
            "side": "buy",
            "quantity": 0.1,
            "filled_quantity": 0.0,
            "average_price": null,
            "created_at": "2024-01-15T10:30:00Z",
            "updated_at": "2024-01-15T10:30:00Z",
        }

        pact.given("Trading system is operational").upon_receiving(
            "Place trading order"
        ).with_request(
            method="POST",
            path="/orders",
            headers={
                "Authorization": "Bearer jwt_token_here",
                "Content-Type": "application/json",
            },
            body={
                "symbol": "GBPUSD",
                "side": "buy",
                "quantity": 0.1,
                "order_type": "market",
                "stop_loss": 1.26,
                "take_profit": 1.275,
                "risk_management": {
                    "max_risk_percent": 2.0,
                    "position_sizing": "fixed",
                },
            },
        ).will_respond_with(
            status=201,
            headers={"Content-Type": "application/json"},
            body=expected_response,
        )

        # When
        with pact:
            response = self._make_request(
                method="POST",
                path="/orders",
                headers={
                    "Authorization": "Bearer jwt_token_here",
                    "Content-Type": "application/json",
                },
                params={},
                json={
                    "symbol": "GBPUSD",
                    "side": "buy",
                    "quantity": 0.1,
                    "order_type": "market",
                    "stop_loss": 1.26,
                    "take_profit": 1.275,
                    "risk_management": {
                        "max_risk_percent": 2.0,
                        "position_sizing": "fixed",
                    },
                },
            )

        # Then
        assert response.status_code == 201
        assert response.headers.get("Content-Type") == "application/json"

        response_data = response.json()
        # Add specific assertions based on the response structure
        self._assert_response_structure(response_data, expected_response)

    def _make_request(self, method, path, headers=None, params=None, json=None):
        """Make HTTP request to the provider"""
        url = f"{pact.provider.host}:{pact.provider.port}{path}"

        return requests.request(
            method=method,
            url=url,
            headers=headers,
            params=params,
            json=json if json != "None" else None,
            timeout=30,
        )

    def _assert_response_structure(self, actual, expected):
        """Assert that response structure matches expected"""
        if isinstance(expected, dict):
            assert isinstance(actual, dict), f"Expected dict, got {type(actual)}"
            for key, value in expected.items():
                assert key in actual, f"Missing key: {key}"
                if isinstance(value, (dict, list)):
                    self._assert_response_structure(actual[key], value)
        elif isinstance(expected, list):
            assert isinstance(actual, list), f"Expected list, got {type(actual)}"
            if expected and actual:
                self._assert_response_structure(actual[0], expected[0])

    @classmethod
    def teardown_class(cls):
        """Write pact file after all tests complete"""
        pact.write_pact_file()


def verify_pact():
    """Verify the pact against the provider"""
    verifier = Verifier(
        provider="{contract.provider}", provider_base_url="http://localhost:8001"
    )

    success, logs = verifier.verify_pacts(
        "./pacts/{contract.consumer}-{contract.provider}.json",
        verbose=True,
        provider_states_setup_url="http://localhost:8001/_pact/provider_states",
    )

    assert success, f"Pact verification failed: {logs}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
