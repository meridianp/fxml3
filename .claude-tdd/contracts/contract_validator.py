#!/usr/bin/env python3
"""
FXML4 Contract Testing Validator
Validates API contracts between FXML4 components
"""

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urljoin

import jsonschema
import requests
import yaml


@dataclass
class APIContract:
    """Represents an API contract definition"""

    service_name: str
    endpoint: str
    method: str
    request_schema: Dict[str, Any]
    response_schema: Dict[str, Any]
    description: str
    examples: List[Dict[str, Any]] = field(default_factory=list)
    performance_requirements: Dict[str, float] = field(default_factory=dict)


@dataclass
class ContractTestResult:
    """Result of a contract test"""

    contract: APIContract
    success: bool
    response_time: float
    status_code: Optional[int] = None
    error_message: Optional[str] = None
    validation_errors: List[str] = field(default_factory=list)


class ContractValidator:
    """Validates API contracts between FXML4 components"""

    def __init__(self, base_url: str = "http://localhost:8001"):
        self.base_url = base_url
        self.contracts = {}
        self.test_results = []
        self._load_fxml4_contracts()

    def _load_fxml4_contracts(self):
        """Load FXML4-specific API contracts"""
        # Core API contracts
        self.contracts["core_health"] = APIContract(
            service_name="core",
            endpoint="/health",
            method="GET",
            request_schema={},
            response_schema={
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["healthy", "degraded", "critical"],
                    },
                    "timestamp": {"type": "string", "format": "date-time"},
                    "version": {"type": "string"},
                    "components": {
                        "type": "object",
                        "properties": {
                            "database": {"type": "string"},
                            "rabbitmq": {"type": "string"},
                            "brokers": {"type": "object"},
                        },
                    },
                },
                "required": ["status", "timestamp"],
            },
            description="Core system health check",
            performance_requirements={"response_time": 0.1},
        )

        self.contracts["wave_analysis"] = APIContract(
            service_name="core",
            endpoint="/api/v1/elliott-wave/analyze",
            method="POST",
            request_schema={
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "pattern": "^[A-Z]{6}$"},
                    "timeframe": {
                        "type": "string",
                        "enum": ["1m", "5m", "15m", "1h", "4h", "1d"],
                    },
                    "lookback_bars": {
                        "type": "integer",
                        "minimum": 50,
                        "maximum": 1000,
                    },
                },
                "required": ["symbol", "timeframe"],
            },
            response_schema={
                "type": "object",
                "properties": {
                    "wave_count": {
                        "type": "object",
                        "properties": {
                            "current_wave": {
                                "type": "integer",
                                "minimum": 1,
                                "maximum": 5,
                            },
                            "wave_type": {
                                "type": "string",
                                "enum": ["impulse", "corrective"],
                            },
                            "confidence": {
                                "type": "number",
                                "minimum": 0,
                                "maximum": 1,
                            },
                        },
                    },
                    "fibonacci_levels": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "level": {"type": "number"},
                                "price": {"type": "number"},
                                "type": {"type": "string"},
                            },
                        },
                    },
                    "signals": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "signal": {
                                    "type": "string",
                                    "enum": ["buy", "sell", "hold"],
                                },
                                "strength": {
                                    "type": "number",
                                    "minimum": 0,
                                    "maximum": 1,
                                },
                                "reasoning": {"type": "string"},
                            },
                        },
                    },
                },
                "required": ["wave_count", "signals"],
            },
            description="Elliott Wave analysis API",
            examples=[
                {
                    "request": {
                        "symbol": "GBPUSD",
                        "timeframe": "4h",
                        "lookback_bars": 200,
                    },
                    "response": {
                        "wave_count": {
                            "current_wave": 3,
                            "wave_type": "impulse",
                            "confidence": 0.82,
                        },
                        "signals": [
                            {
                                "signal": "buy",
                                "strength": 0.75,
                                "reasoning": "Wave 3 extension pattern",
                            }
                        ],
                    },
                }
            ],
            performance_requirements={"response_time": 2.0},
        )

        self.contracts["trading_signals"] = APIContract(
            service_name="core",
            endpoint="/api/v1/signals/generate",
            method="POST",
            request_schema={
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "strategy": {"type": "string"},
                    "timeframe": {"type": "string"},
                    "risk_level": {
                        "type": "string",
                        "enum": ["conservative", "moderate", "aggressive"],
                    },
                },
                "required": ["symbol", "strategy"],
            },
            response_schema={
                "type": "object",
                "properties": {
                    "signal_id": {"type": "string"},
                    "timestamp": {"type": "string", "format": "date-time"},
                    "symbol": {"type": "string"},
                    "action": {"type": "string", "enum": ["buy", "sell", "hold"]},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "entry_price": {"type": "number", "minimum": 0},
                    "stop_loss": {"type": "number", "minimum": 0},
                    "take_profit": {"type": "number", "minimum": 0},
                    "position_size": {"type": "number", "minimum": 0},
                    "risk_reward_ratio": {"type": "number", "minimum": 0},
                },
                "required": [
                    "signal_id",
                    "timestamp",
                    "symbol",
                    "action",
                    "confidence",
                ],
            },
            description="Trading signal generation",
            performance_requirements={"response_time": 1.0},
        )

        self.contracts["portfolio_status"] = APIContract(
            service_name="core",
            endpoint="/api/v1/portfolio/status",
            method="GET",
            request_schema={},
            response_schema={
                "type": "object",
                "properties": {
                    "account_balance": {"type": "number"},
                    "equity": {"type": "number"},
                    "margin_used": {"type": "number"},
                    "margin_available": {"type": "number"},
                    "open_positions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "symbol": {"type": "string"},
                                "side": {"type": "string", "enum": ["long", "short"]},
                                "size": {"type": "number"},
                                "entry_price": {"type": "number"},
                                "current_price": {"type": "number"},
                                "unrealized_pnl": {"type": "number"},
                            },
                        },
                    },
                    "daily_pnl": {"type": "number"},
                    "total_pnl": {"type": "number"},
                },
                "required": ["account_balance", "equity", "open_positions"],
            },
            description="Portfolio status and positions",
            performance_requirements={"response_time": 0.5},
        )

    def validate_contract(
        self, contract_name: str, test_data: Dict[str, Any] = None
    ) -> ContractTestResult:
        """Validate a specific contract"""
        if contract_name not in self.contracts:
            return ContractTestResult(
                contract=None,
                success=False,
                response_time=0,
                error_message=f"Contract '{contract_name}' not found",
            )

        contract = self.contracts[contract_name]

        try:
            start_time = time.time()

            # Prepare request
            url = urljoin(self.base_url, contract.endpoint.lstrip("/"))
            headers = {"Content-Type": "application/json"}

            # Use test data or example data
            if test_data:
                request_data = test_data
            elif contract.examples:
                request_data = contract.examples[0]["request"]
            else:
                request_data = self._generate_sample_request_data(contract)

            # Validate request schema
            request_validation_errors = self._validate_schema(
                request_data, contract.request_schema
            )

            # Make API call
            if contract.method.upper() == "GET":
                response = requests.get(
                    url, headers=headers, params=request_data, timeout=10
                )
            elif contract.method.upper() == "POST":
                response = requests.post(
                    url, headers=headers, json=request_data, timeout=10
                )
            else:
                return ContractTestResult(
                    contract=contract,
                    success=False,
                    response_time=0,
                    error_message=f"Unsupported HTTP method: {contract.method}",
                )

            response_time = time.time() - start_time

            # Validate response
            try:
                response_data = response.json()
            except json.JSONDecodeError:
                response_data = {"raw_response": response.text}

            response_validation_errors = self._validate_schema(
                response_data, contract.response_schema
            )

            # Check performance requirements
            performance_errors = []
            if "response_time" in contract.performance_requirements:
                max_time = contract.performance_requirements["response_time"]
                if response_time > max_time:
                    performance_errors.append(
                        f"Response time {response_time:.3f}s exceeds requirement {max_time}s"
                    )

            all_errors = (
                request_validation_errors
                + response_validation_errors
                + performance_errors
            )
            success = response.status_code == 200 and len(all_errors) == 0

            result = ContractTestResult(
                contract=contract,
                success=success,
                response_time=response_time,
                status_code=response.status_code,
                validation_errors=all_errors,
                error_message=None if success else f"Status: {response.status_code}",
            )

            self.test_results.append(result)
            return result

        except requests.RequestException as e:
            response_time = time.time() - start_time
            result = ContractTestResult(
                contract=contract,
                success=False,
                response_time=response_time,
                error_message=f"Request failed: {str(e)}",
            )
            self.test_results.append(result)
            return result

    def _validate_schema(self, data: Any, schema: Dict[str, Any]) -> List[str]:
        """Validate data against JSON schema"""
        if not schema:
            return []

        try:
            jsonschema.validate(data, schema)
            return []
        except jsonschema.ValidationError as e:
            return [f"Schema validation error: {e.message}"]
        except Exception as e:
            return [f"Schema validation failed: {str(e)}"]

    def _generate_sample_request_data(self, contract: APIContract) -> Dict[str, Any]:
        """Generate sample request data based on schema"""
        # Simple sample data generation
        sample_data = {}

        if not contract.request_schema or "properties" not in contract.request_schema:
            return sample_data

        properties = contract.request_schema["properties"]
        required = contract.request_schema.get("required", [])

        for prop_name, prop_schema in properties.items():
            if (
                prop_name in required or len(sample_data) < 3
            ):  # Generate at least some data
                sample_data[prop_name] = self._generate_sample_value(prop_schema)

        return sample_data

    def _generate_sample_value(self, schema: Dict[str, Any]) -> Any:
        """Generate a sample value for a schema property"""
        if schema.get("type") == "string":
            if "enum" in schema:
                return schema["enum"][0]
            elif schema.get("pattern") == "^[A-Z]{6}$":
                return "GBPUSD"
            else:
                return "sample_string"
        elif schema.get("type") == "integer":
            minimum = schema.get("minimum", 1)
            maximum = schema.get("maximum", 100)
            return min(maximum, max(minimum, 50))
        elif schema.get("type") == "number":
            minimum = schema.get("minimum", 0.0)
            maximum = schema.get("maximum", 100.0)
            return min(maximum, max(minimum, 1.0))
        elif schema.get("type") == "boolean":
            return True
        elif schema.get("type") == "array":
            return []
        elif schema.get("type") == "object":
            return {}
        else:
            return None

    def validate_all_contracts(self) -> List[ContractTestResult]:
        """Validate all defined contracts"""
        results = []

        print("Validating FXML4 API contracts...")
        for contract_name in self.contracts:
            print(f"  Testing {contract_name}...")
            result = self.validate_contract(contract_name)
            results.append(result)

        return results

    def generate_contract_report(self) -> str:
        """Generate a contract validation report"""
        if not self.test_results:
            return "No contract tests have been executed."

        total_tests = len(self.test_results)
        successful_tests = sum(1 for r in self.test_results if r.success)
        failed_tests = total_tests - successful_tests

        report = []
        report.append("FXML4 API Contract Validation Report")
        report.append("=" * 45)
        report.append(f"Generated: {datetime.now().isoformat()}")
        report.append("")

        # Summary
        report.append("SUMMARY")
        report.append("-" * 20)
        report.append(f"Total Contracts Tested: {total_tests}")
        report.append(f"Successful Validations: {successful_tests}")
        report.append(f"Failed Validations: {failed_tests}")
        report.append(f"Success Rate: {successful_tests/total_tests:.1%}")
        report.append("")

        # Performance Summary
        avg_response_time = (
            sum(r.response_time for r in self.test_results) / total_tests
        )
        report.append(f"Average Response Time: {avg_response_time:.3f}s")
        report.append("")

        # Detailed Results
        report.append("DETAILED RESULTS")
        report.append("-" * 20)

        for result in self.test_results:
            status = "✓ PASS" if result.success else "✗ FAIL"
            contract_name = (
                result.contract.service_name + ":" + result.contract.endpoint
            )
            report.append(
                f"{status} {contract_name} ({result.contract.method}) - "
                f"{result.response_time:.3f}s"
            )

            if result.status_code:
                report.append(f"      Status Code: {result.status_code}")

            if result.validation_errors:
                for error in result.validation_errors:
                    report.append(f"      Error: {error}")

            if result.error_message:
                report.append(f"      Message: {result.error_message}")

        return "\n".join(report)


def main():
    """Demo usage of contract validator"""
    validator = ContractValidator()

    # Validate all contracts
    results = validator.validate_all_contracts()

    # Generate report
    report = validator.generate_contract_report()
    print(report)

    # Save report
    with open(".claude-tdd/reports/contract_validation.txt", "w") as f:
        f.write(report)


if __name__ == "__main__":
    main()
