"""Mock service orchestration for integration testing."""

import logging
import threading
import time
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, Mock

logger = logging.getLogger(__name__)


class MockServiceOrchestrator:
    """Orchestrates lifecycle of mock services for testing."""

    def __init__(self):
        self.services = {}
        self.service_configs = {
            "interactive_brokers": {
                "startup_time": 0.1,
                "default_responses": {
                    "connect": True,
                    "get_market_data": {"symbol": "EURUSD", "price": 1.1000},
                },
            },
            "redis": {
                "startup_time": 0.05,
                "default_responses": {"ping": True, "get": None, "set": True},
            },
            "database": {
                "startup_time": 0.2,
                "default_responses": {"connect": True, "query": []},
            },
        }

    def create_mock(self, service_name: str) -> Mock:
        """Create a mock service."""
        if service_name not in self.service_configs:
            raise ValueError(f"Unknown service: {service_name}")

        config = self.service_configs[service_name]
        mock_service = MockService(service_name, config)
        self.services[service_name] = mock_service

        logger.info(f"Created mock service: {service_name}")
        return mock_service

    def start_all(self):
        """Start all mock services."""
        for service_name, service in self.services.items():
            service.start()
            logger.info(f"Started mock service: {service_name}")

    def stop_all(self):
        """Stop all mock services."""
        for service_name, service in self.services.items():
            service.stop()
            logger.info(f"Stopped mock service: {service_name}")


class MockService:
    """Individual mock service with lifecycle management."""

    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config
        self.running = False
        self._setup_methods()

    def _setup_methods(self):
        """Setup mock methods based on default responses."""
        default_responses = self.config.get("default_responses", {})

        for method_name, response in default_responses.items():
            setattr(self, method_name, Mock(return_value=response))

    def start(self):
        """Start the mock service."""
        startup_time = self.config.get("startup_time", 0.1)
        time.sleep(startup_time)  # Simulate startup time
        self.running = True

    def stop(self):
        """Stop the mock service."""
        self.running = False

    def is_running(self) -> bool:
        """Check if service is running."""
        return self.running


class ScenarioBasedMock:
    """Mock with different behavior scenarios."""

    def __init__(self, service_type: str):
        self.service_type = service_type
        self.current_scenario = "normal_operation"
        self.scenarios = {
            "normal_operation": {
                "connect": lambda: True,
                "get_market_data": lambda symbol: {"symbol": symbol, "price": 1.1000},
                "latency": 0.01,
            },
            "connection_failure": {
                "connect": lambda: False,
                "get_market_data": lambda symbol: None,
                "latency": 0.01,
            },
            "high_latency": {
                "connect": lambda: True,
                "get_market_data": lambda symbol: {"symbol": symbol, "price": 1.1000},
                "latency": 0.5,
            },
            "intermittent_failure": {
                "connect": lambda: time.time() % 4 < 2,  # Fail 50% of the time
                "get_market_data": lambda symbol: {"symbol": symbol, "price": 1.1000},
                "latency": 0.01,
            },
        }

    def set_scenario(self, scenario_name: str):
        """Set the current behavior scenario."""
        if scenario_name not in self.scenarios:
            raise ValueError(f"Unknown scenario: {scenario_name}")
        self.current_scenario = scenario_name
        logger.info(f"Set {self.service_type} to scenario: {scenario_name}")

    def connect(self) -> bool:
        """Mock connect method with scenario-based behavior."""
        scenario = self.scenarios[self.current_scenario]
        time.sleep(scenario["latency"])
        return scenario["connect"]()

    def get_market_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Mock market data method with scenario-based behavior."""
        scenario = self.scenarios[self.current_scenario]
        time.sleep(scenario["latency"])
        return scenario["get_market_data"](symbol)


class StatefulMockCluster:
    """Cluster of mock services with shared state."""

    def __init__(self):
        self.services = {}
        self.shared_state = {
            "accounts": {},
            "orders": {},
            "positions": {},
            "market_data": {},
        }

    def create_mock(self, service_name: str):
        """Create a mock service with shared state."""
        if service_name == "order_service":
            service = OrderServiceMock(self.shared_state)
        elif service_name == "position_service":
            service = PositionServiceMock(self.shared_state)
        elif service_name == "account_service":
            service = AccountServiceMock(self.shared_state)
        else:
            raise ValueError(f"Unknown service: {service_name}")

        self.services[service_name] = service
        return service


class OrderServiceMock:
    """Mock order service with state management."""

    def __init__(self, shared_state: Dict[str, Any]):
        self.state = shared_state

    def place_order(self, order: Dict[str, Any]) -> str:
        """Place an order and update shared state."""
        order_id = f"ORDER_{len(self.state['orders']) + 1:06d}"

        self.state["orders"][order_id] = {
            "id": order_id,
            "symbol": order["symbol"],
            "quantity": order["quantity"],
            "account_id": order["account_id"],
            "status": "filled",
            "price": 1.1000,  # Mock price
        }

        # Update positions
        account_id = order["account_id"]
        symbol = order["symbol"]

        if account_id not in self.state["positions"]:
            self.state["positions"][account_id] = {}

        if symbol not in self.state["positions"][account_id]:
            self.state["positions"][account_id][symbol] = {
                "symbol": symbol,
                "quantity": 0,
                "account_id": account_id,
            }

        self.state["positions"][account_id][symbol]["quantity"] += order["quantity"]

        # Update account margin
        if account_id not in self.state["accounts"]:
            self.state["accounts"][account_id] = {
                "account_id": account_id,
                "balance": 100000.0,
                "used_margin": 0.0,
            }

        margin_required = order["quantity"] * 0.02  # 2% margin
        self.state["accounts"][account_id]["used_margin"] += margin_required

        return order_id


class PositionServiceMock:
    """Mock position service."""

    def __init__(self, shared_state: Dict[str, Any]):
        self.state = shared_state

    def get_positions(self, account_id: str) -> List[Dict[str, Any]]:
        """Get positions for an account."""
        account_positions = self.state["positions"].get(account_id, {})
        return list(account_positions.values())


class AccountServiceMock:
    """Mock account service."""

    def __init__(self, shared_state: Dict[str, Any]):
        self.state = shared_state

    def get_account(self, account_id: str) -> Dict[str, Any]:
        """Get account information."""
        return self.state["accounts"].get(
            account_id,
            {"account_id": account_id, "balance": 100000.0, "used_margin": 0.0},
        )
