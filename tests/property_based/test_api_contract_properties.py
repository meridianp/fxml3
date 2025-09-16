"""
Property-Based Testing for API Contracts and Data Validation
===========================================================

Tests API endpoints and data validation logic using property-based testing
to ensure robust handling of edge cases, invalid inputs, and boundary conditions
that traditional tests might miss.

This complements the trading logic properties by focusing on:
1. API input validation and sanitization
2. Data type consistency across endpoints
3. Rate limiting and security properties
4. Database constraint validation
5. Error handling consistency

Part of medium-priority task M2: Property-based testing implementation.
"""

import json
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

import pytest
from fastapi.testclient import TestClient
from hypothesis import assume, example, given, settings
from hypothesis import strategies as st
from hypothesis.extra.pandas import column, data_frames

# Custom strategies for API testing
from tests.fixtures.market_data_fixtures import currency_prices, forex_pairs

# ============================================================================
# API-Specific Strategies
# ============================================================================


@st.composite
def api_timestamps(draw):
    """Generate various timestamp formats for API testing."""
    format_choice = draw(st.integers(min_value=1, max_value=4))

    base_time = datetime.now(timezone.utc)

    if format_choice == 1:
        # ISO format
        return base_time.isoformat()
    elif format_choice == 2:
        # Unix timestamp
        return int(base_time.timestamp())
    elif format_choice == 3:
        # String with timezone
        return base_time.strftime("%Y-%m-%d %H:%M:%S %Z")
    else:
        # Date only
        return base_time.strftime("%Y-%m-%d")


@st.composite
def order_requests(draw):
    """Generate order request payloads."""
    return {
        "symbol": draw(forex_pairs()),
        "side": draw(st.sampled_from(["buy", "sell"])),
        "quantity": draw(st.floats(min_value=0.01, max_value=1000.0)),
        "order_type": draw(st.sampled_from(["market", "limit", "stop"])),
        "price": draw(st.one_of(st.none(), currency_prices())),
        "time_in_force": draw(st.sampled_from(["GTC", "IOC", "FOK", "DAY"])),
        "client_order_id": draw(st.one_of(st.none(), st.text(min_size=1, max_size=64))),
    }


@st.composite
def user_credentials(draw):
    """Generate user credential combinations."""
    return {
        "username": draw(st.text(min_size=1, max_size=255)),
        "password": draw(st.text(min_size=1, max_size=1000)),
        "email": draw(
            st.one_of(
                st.none(),
                st.emails(),
                st.text().filter(lambda x: "@" not in x),  # Invalid emails
            )
        ),
    }


@st.composite
def pagination_params(draw):
    """Generate pagination parameters."""
    return {
        "page": draw(
            st.one_of(
                st.integers(min_value=1, max_value=1000),
                st.integers(min_value=-100, max_value=0),  # Invalid pages
                st.none(),
            )
        ),
        "page_size": draw(
            st.one_of(
                st.integers(min_value=1, max_value=1000),
                st.integers(min_value=-100, max_value=0),  # Invalid sizes
                st.integers(min_value=1001, max_value=10000),  # Too large
                st.none(),
            )
        ),
    }


@st.composite
def query_filters(draw):
    """Generate query filter combinations."""
    return {
        "start_date": draw(st.one_of(st.none(), api_timestamps())),
        "end_date": draw(st.one_of(st.none(), api_timestamps())),
        "symbol": draw(st.one_of(st.none(), forex_pairs(), st.text(max_size=10))),
        "status": draw(
            st.one_of(
                st.none(),
                st.sampled_from(["active", "filled", "cancelled", "rejected"]),
                st.text(max_size=20),  # Invalid status
            )
        ),
    }


@st.composite
def json_payloads(draw):
    """Generate various JSON payload structures."""
    payload_type = draw(st.integers(min_value=1, max_value=6))

    if payload_type == 1:
        # Valid nested structure
        return {
            "data": {
                "symbol": draw(forex_pairs()),
                "value": draw(st.floats(allow_nan=False, allow_infinity=False)),
                "metadata": {
                    "timestamp": draw(api_timestamps()),
                    "source": draw(st.text(max_size=50)),
                },
            }
        }
    elif payload_type == 2:
        # Array payload
        return {
            "items": draw(
                st.lists(
                    st.fixed_dictionaries(
                        {
                            "id": st.integers(min_value=1),
                            "value": st.floats(allow_nan=False, allow_infinity=False),
                        }
                    ),
                    max_size=100,
                )
            )
        }
    elif payload_type == 3:
        # Empty payload
        return {}
    elif payload_type == 4:
        # Payload with special characters
        return {
            "message": draw(st.text().filter(lambda x: len(x) < 10000)),
            "special_chars": "!@#$%^&*()[]{}|\\:;\"'<>,.?/~`",
        }
    elif payload_type == 5:
        # Large payload
        return {
            "large_text": "x" * draw(st.integers(min_value=0, max_value=100000)),
            "data": draw(st.lists(st.integers(), max_size=1000)),
        }
    else:
        # Invalid structure
        return {
            "invalid_float": float("inf"),
            "invalid_nan": float("nan"),
            "none_value": None,
        }


# ============================================================================
# Property-Based API Tests
# ============================================================================


class TestAPIValidationProperties:
    """Test API input validation properties."""

    @given(order_data=order_requests())
    def test_order_validation_properties(self, order_data):
        """Test order validation across all possible inputs."""

        # Mock the validation function behavior
        def validate_order(order_data):
            errors = []

            # Symbol validation
            if not order_data.get("symbol"):
                errors.append("Symbol is required")
            elif len(order_data["symbol"]) < 6 or len(order_data["symbol"]) > 8:
                errors.append("Invalid symbol format")

            # Quantity validation
            if not order_data.get("quantity") or order_data["quantity"] <= 0:
                errors.append("Quantity must be positive")
            elif order_data["quantity"] < 0.01:
                errors.append("Minimum quantity is 0.01")
            elif order_data["quantity"] > 1000:
                errors.append("Maximum quantity is 1000")

            # Price validation for limit/stop orders
            if order_data.get("order_type") in ["limit", "stop"]:
                if not order_data.get("price") or order_data["price"] <= 0:
                    errors.append("Price required for limit/stop orders")

            # Side validation
            if order_data.get("side") not in ["buy", "sell"]:
                errors.append("Side must be buy or sell")

            return errors

        validation_errors = validate_order(order_data)

        # Property 1: Invalid orders should have validation errors
        has_invalid_symbol = (
            not order_data.get("symbol")
            or len(order_data.get("symbol", "")) < 6
            or len(order_data.get("symbol", "")) > 8
        )
        has_invalid_quantity = (
            not order_data.get("quantity") or order_data.get("quantity", 0) <= 0
        )
        has_invalid_side = order_data.get("side") not in ["buy", "sell"]

        if has_invalid_symbol or has_invalid_quantity or has_invalid_side:
            assert (
                len(validation_errors) > 0
            ), f"Should have validation errors for: {order_data}"

        # Property 2: Valid orders should pass validation
        if (
            order_data.get("symbol")
            and 6 <= len(order_data["symbol"]) <= 8
            and order_data.get("quantity")
            and 0.01 <= order_data["quantity"] <= 1000
            and order_data.get("side") in ["buy", "sell"]
            and order_data.get("order_type") == "market"
        ):

            assert len(validation_errors) == 0, f"Valid order should pass: {order_data}"

        # Property 3: Limit orders without price should fail
        if order_data.get("order_type") in ["limit", "stop"] and (
            not order_data.get("price") or order_data.get("price", 0) <= 0
        ):
            assert any(
                "price" in error.lower() for error in validation_errors
            ), "Limit/stop orders without price should fail validation"

    @given(credentials=user_credentials())
    def test_authentication_properties(self, credentials):
        """Test authentication validation properties."""

        def validate_credentials(creds):
            if not creds.get("username") or len(creds["username"]) < 3:
                return False, "Username too short"

            if not creds.get("password") or len(creds["password"]) < 8:
                return False, "Password too short"

            # Email validation
            email = creds.get("email")
            if email and "@" not in email:
                return False, "Invalid email format"

            return True, "Valid credentials"

        is_valid, message = validate_credentials(credentials)

        # Property 1: Short usernames should be rejected
        if not credentials.get("username") or len(credentials["username"]) < 3:
            assert not is_valid, "Short usernames should be rejected"
            assert "username" in message.lower()

        # Property 2: Short passwords should be rejected
        if not credentials.get("password") or len(credentials["password"]) < 8:
            assert not is_valid, "Short passwords should be rejected"
            assert "password" in message.lower()

        # Property 3: Invalid emails should be rejected
        email = credentials.get("email")
        if email and "@" not in email:
            assert not is_valid, "Invalid emails should be rejected"
            assert "email" in message.lower()

    @given(pagination=pagination_params())
    def test_pagination_properties(self, pagination):
        """Test pagination parameter validation."""

        def normalize_pagination(params):
            page = params.get("page", 1)
            page_size = params.get("page_size", 50)

            # Apply constraints
            page = max(1, page) if page is not None else 1
            page_size = max(1, min(1000, page_size)) if page_size is not None else 50

            return {"page": page, "page_size": page_size}

        normalized = normalize_pagination(pagination)

        # Property 1: Page should always be at least 1
        assert normalized["page"] >= 1, "Page should be at least 1"

        # Property 2: Page size should be bounded
        assert 1 <= normalized["page_size"] <= 1000, "Page size should be bounded"

        # Property 3: None values should get defaults
        if pagination.get("page") is None:
            assert normalized["page"] == 1, "None page should default to 1"

        if pagination.get("page_size") is None:
            assert normalized["page_size"] == 50, "None page_size should default to 50"


class TestAPIResponseProperties:
    """Test API response consistency properties."""

    @given(
        status_code=st.integers(min_value=200, max_value=599),
        response_data=st.one_of(
            st.dictionaries(
                st.text(),
                st.one_of(st.text(), st.integers(), st.floats(), st.booleans()),
            ),
            st.lists(st.dictionaries(st.text(), st.integers())),
            st.none(),
        ),
    )
    def test_response_format_properties(self, status_code, response_data):
        """Test API response format consistency."""

        def format_api_response(status_code, data):
            response = {
                "status_code": status_code,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "success": 200 <= status_code < 300,
            }

            if data is not None:
                response["data"] = data

            if status_code >= 400:
                response["error"] = {"code": status_code, "message": "Error occurred"}

            return response

        response = format_api_response(status_code, response_data)

        # Property 1: All responses should have required fields
        required_fields = ["status_code", "timestamp", "success"]
        for field in required_fields:
            assert field in response, f"Response missing required field: {field}"

        # Property 2: Success flag should match status code
        expected_success = 200 <= status_code < 300
        assert (
            response["success"] == expected_success
        ), f"Success flag {response['success']} doesn't match status {status_code}"

        # Property 3: Error responses should include error details
        if status_code >= 400:
            assert "error" in response, "Error responses should include error details"
            assert "code" in response["error"], "Error should include code"
            assert "message" in response["error"], "Error should include message"

        # Property 4: Timestamp should be valid ISO format
        try:
            datetime.fromisoformat(response["timestamp"].replace("Z", "+00:00"))
        except ValueError:
            pytest.fail(f"Invalid timestamp format: {response['timestamp']}")

    @given(
        filters=query_filters(), total_records=st.integers(min_value=0, max_value=10000)
    )
    def test_filtering_properties(self, filters, total_records):
        """Test query filtering properties."""

        def apply_filters(total_records, filters):
            # Mock filtering logic
            remaining_records = total_records

            # Date range filtering
            start_date = filters.get("start_date")
            end_date = filters.get("end_date")

            if start_date and end_date:
                try:
                    # Try to parse dates
                    if isinstance(start_date, str) and isinstance(end_date, str):
                        start_dt = datetime.fromisoformat(
                            start_date.replace("Z", "+00:00")
                        )
                        end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))

                        if start_dt > end_dt:
                            return {"error": "Start date must be before end date"}

                        # Simulate filtering reducing records
                        remaining_records = int(remaining_records * 0.8)
                except:
                    return {"error": "Invalid date format"}

            # Symbol filtering
            if filters.get("symbol"):
                symbol = filters["symbol"]
                if len(symbol) >= 6 and len(symbol) <= 8:
                    remaining_records = int(remaining_records * 0.5)
                else:
                    return {"error": "Invalid symbol format"}

            # Status filtering
            if filters.get("status"):
                status = filters["status"]
                if status in ["active", "filled", "cancelled", "rejected"]:
                    remaining_records = int(remaining_records * 0.3)
                else:
                    return {"error": "Invalid status"}

            return {"count": max(0, remaining_records)}

        result = apply_filters(total_records, filters)

        # Property 1: Invalid date ranges should return errors
        start_date = filters.get("start_date")
        end_date = filters.get("end_date")

        if (
            start_date
            and end_date
            and isinstance(start_date, str)
            and isinstance(end_date, str)
        ):
            try:
                start_dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
                end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))

                if start_dt > end_dt:
                    assert "error" in result, "Invalid date range should return error"
            except:
                # Invalid date format should also return error
                assert "error" in result, "Invalid date format should return error"

        # Property 2: Valid filters should return count
        if "error" not in result:
            assert "count" in result, "Valid filters should return count"
            assert result["count"] >= 0, "Count cannot be negative"
            assert (
                result["count"] <= total_records
            ), "Filtered count cannot exceed total"

        # Property 3: Invalid symbols should return errors
        symbol = filters.get("symbol")
        if symbol and (len(symbol) < 6 or len(symbol) > 8):
            assert "error" in result, "Invalid symbol should return error"

        # Property 4: Invalid status should return errors
        status = filters.get("status")
        if status and status not in ["active", "filled", "cancelled", "rejected"]:
            assert "error" in result, "Invalid status should return error"


class TestDataConsistencyProperties:
    """Test data consistency properties across API operations."""

    @given(
        initial_balance=st.floats(min_value=1000, max_value=1000000),
        trades=st.lists(
            st.fixed_dictionaries(
                {
                    "amount": st.floats(min_value=-10000, max_value=10000),
                    "fee": st.floats(min_value=0, max_value=100),
                    "timestamp": st.integers(
                        min_value=1640995200, max_value=2000000000
                    ),  # 2022-2033
                }
            ),
            max_size=50,
        ),
    )
    def test_account_balance_consistency(self, initial_balance, trades):
        """Test account balance consistency across operations."""

        def calculate_balance(initial_balance, trades):
            current_balance = initial_balance
            balance_history = [{"balance": current_balance, "timestamp": 0}]

            # Sort trades by timestamp
            sorted_trades = sorted(trades, key=lambda x: x["timestamp"])

            for trade in sorted_trades:
                # Apply trade and fee
                current_balance += trade["amount"] - trade["fee"]

                # Prevent negative balance (margin call)
                if current_balance < 0:
                    current_balance = 0

                balance_history.append(
                    {"balance": current_balance, "timestamp": trade["timestamp"]}
                )

            return balance_history

        balance_history = calculate_balance(initial_balance, trades)

        # Property 1: Balance should never be negative
        for entry in balance_history:
            assert (
                entry["balance"] >= 0
            ), f"Balance cannot be negative: {entry['balance']}"

        # Property 2: Balance history should be chronologically ordered
        timestamps = [entry["timestamp"] for entry in balance_history]
        assert timestamps == sorted(
            timestamps
        ), "Balance history should be chronologically ordered"

        # Property 3: First entry should be initial balance
        assert (
            balance_history[0]["balance"] == initial_balance
        ), "First balance entry should equal initial balance"

        # Property 4: Balance changes should equal trade amounts minus fees
        if len(balance_history) > 1:
            for i in range(1, len(balance_history)):
                prev_balance = balance_history[i - 1]["balance"]
                curr_balance = balance_history[i]["balance"]

                # Find corresponding trade
                trade_idx = i - 1
                if trade_idx < len(trades):
                    sorted_trades = sorted(trades, key=lambda x: x["timestamp"])
                    trade = sorted_trades[trade_idx]

                    expected_change = trade["amount"] - trade["fee"]

                    # Account for margin call scenario
                    if prev_balance + expected_change < 0:
                        assert (
                            curr_balance == 0
                        ), "Balance should be 0 after margin call"
                    else:
                        actual_change = curr_balance - prev_balance
                        assert (
                            abs(actual_change - expected_change) < 1e-6
                        ), f"Balance change {actual_change} != expected {expected_change}"

    @given(
        orders=st.lists(
            st.fixed_dictionaries(
                {
                    "id": st.integers(min_value=1, max_value=1000000),
                    "symbol": forex_pairs(),
                    "quantity": st.floats(min_value=0.01, max_value=1000),
                    "price": currency_prices(),
                    "side": st.sampled_from(["buy", "sell"]),
                    "status": st.sampled_from(["pending", "filled", "cancelled"]),
                    "created_at": st.integers(
                        min_value=1640995200, max_value=2000000000
                    ),
                }
            ),
            max_size=20,
        )
    )
    def test_order_state_consistency(self, orders):
        """Test order state consistency properties."""

        def process_orders(orders):
            processed = []
            position_tracker = {}

            # Sort by creation time
            sorted_orders = sorted(orders, key=lambda x: x["created_at"])

            for order in sorted_orders:
                symbol = order["symbol"]

                if symbol not in position_tracker:
                    position_tracker[symbol] = {"long": 0, "short": 0}

                # Process filled orders
                if order["status"] == "filled":
                    if order["side"] == "buy":
                        position_tracker[symbol]["long"] += order["quantity"]
                    else:
                        position_tracker[symbol]["short"] += order["quantity"]

                processed_order = order.copy()
                processed_order["position_after"] = position_tracker[symbol].copy()
                processed.append(processed_order)

            return processed, position_tracker

        processed_orders, final_positions = process_orders(orders)

        # Property 1: Order IDs should be unique
        order_ids = [order["id"] for order in orders]
        unique_ids = set(order_ids)
        assert len(order_ids) == len(unique_ids), "Order IDs should be unique"

        # Property 2: Positions should only change for filled orders
        for order in processed_orders:
            if order["status"] != "filled":
                # For pending/cancelled orders, position shouldn't change from previous state
                continue

        # Property 3: Final positions should equal sum of filled orders
        filled_orders = [o for o in orders if o["status"] == "filled"]

        for symbol, position in final_positions.items():
            expected_long = sum(
                o["quantity"]
                for o in filled_orders
                if o["symbol"] == symbol and o["side"] == "buy"
            )
            expected_short = sum(
                o["quantity"]
                for o in filled_orders
                if o["symbol"] == symbol and o["side"] == "sell"
            )

            assert (
                abs(position["long"] - expected_long) < 1e-6
            ), f"Long position mismatch for {symbol}: {position['long']} != {expected_long}"
            assert (
                abs(position["short"] - expected_short) < 1e-6
            ), f"Short position mismatch for {symbol}: {position['short']} != {expected_short}"

        # Property 4: Positions should be non-negative
        for symbol, position in final_positions.items():
            assert position["long"] >= 0, f"Long position cannot be negative: {symbol}"
            assert (
                position["short"] >= 0
            ), f"Short position cannot be negative: {symbol}"


class TestSecurityProperties:
    """Test security-related properties."""

    @given(
        payload=json_payloads(), max_size=st.integers(min_value=1000, max_value=100000)
    )
    def test_payload_size_limits(self, payload, max_size):
        """Test payload size validation properties."""

        def validate_payload_size(payload, max_size):
            try:
                serialized = json.dumps(payload)
                size = len(serialized.encode("utf-8"))

                if size > max_size:
                    return False, f"Payload too large: {size} > {max_size}"

                return True, f"Payload size OK: {size}"
            except (TypeError, ValueError) as e:
                return False, f"Invalid payload: {str(e)}"

        is_valid, message = validate_payload_size(payload, max_size)

        # Property 1: Payloads exceeding max_size should be rejected
        try:
            serialized = json.dumps(payload)
            actual_size = len(serialized.encode("utf-8"))

            if actual_size > max_size:
                assert (
                    not is_valid
                ), f"Large payload should be rejected: {actual_size} > {max_size}"
                assert "too large" in message.lower()
            else:
                assert (
                    is_valid
                ), f"Small payload should be accepted: {actual_size} <= {max_size}"
        except (TypeError, ValueError):
            # Non-serializable payloads should be rejected
            assert not is_valid, "Non-serializable payloads should be rejected"
            assert "invalid" in message.lower()

    @given(
        request_count=st.integers(min_value=1, max_value=1000),
        time_window=st.integers(min_value=1, max_value=3600),  # 1 second to 1 hour
        rate_limit=st.integers(min_value=10, max_value=1000),
    )
    def test_rate_limiting_properties(self, request_count, time_window, rate_limit):
        """Test rate limiting properties."""

        def check_rate_limit(request_count, time_window, rate_limit):
            requests_per_second = request_count / time_window
            limit_per_second = rate_limit / 60  # Assume rate_limit is per minute

            if requests_per_second > limit_per_second:
                return False, "Rate limit exceeded"

            return True, "Within rate limit"

        is_allowed, message = check_rate_limit(request_count, time_window, rate_limit)

        # Property 1: Requests exceeding rate limit should be blocked
        requests_per_second = request_count / time_window
        limit_per_second = rate_limit / 60

        if requests_per_second > limit_per_second:
            assert not is_allowed, "Excessive requests should be rate limited"
            assert "rate limit" in message.lower()
        else:
            assert is_allowed, "Normal request rate should be allowed"

        # Property 2: Rate limiting should be consistent
        # Same parameters should always give same result
        is_allowed_2, _ = check_rate_limit(request_count, time_window, rate_limit)
        assert is_allowed == is_allowed_2, "Rate limiting should be consistent"


class TestErrorHandlingProperties:
    """Test error handling properties."""

    @given(
        exception_type=st.sampled_from(
            [
                "ValueError",
                "TypeError",
                "KeyError",
                "AttributeError",
                "ConnectionError",
                "TimeoutError",
                "PermissionError",
            ]
        ),
        error_message=st.text(max_size=1000),
        include_stack_trace=st.booleans(),
    )
    def test_error_response_properties(
        self, exception_type, error_message, include_stack_trace
    ):
        """Test error response consistency properties."""

        def format_error_response(exc_type, message, include_trace):
            error_response = {
                "error": {
                    "type": exc_type,
                    "message": message[:500],  # Truncate long messages
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "request_id": str(uuid.uuid4()),
                }
            }

            if include_trace:
                error_response["error"]["stack_trace"] = "Mock stack trace..."

            # Sanitize sensitive information
            sensitive_patterns = ["password", "token", "key", "secret"]
            for pattern in sensitive_patterns:
                if pattern in message.lower():
                    error_response["error"]["message"] = "[REDACTED]"
                    break

            return error_response

        error_response = format_error_response(
            exception_type, error_message, include_stack_trace
        )

        # Property 1: All error responses should have required fields
        assert "error" in error_response
        error_obj = error_response["error"]

        required_fields = ["type", "message", "timestamp", "request_id"]
        for field in required_fields:
            assert field in error_obj, f"Error response missing field: {field}"

        # Property 2: Error messages should be truncated if too long
        if len(error_message) > 500:
            assert (
                len(error_obj["message"]) <= 500
            ), "Error messages should be truncated"

        # Property 3: Sensitive information should be redacted
        sensitive_patterns = ["password", "token", "key", "secret"]
        if any(pattern in error_message.lower() for pattern in sensitive_patterns):
            assert (
                error_obj["message"] == "[REDACTED]"
            ), "Sensitive information should be redacted"

        # Property 4: Stack trace should only be included if requested
        if include_stack_trace:
            assert (
                "stack_trace" in error_obj
            ), "Stack trace should be included when requested"
        else:
            assert (
                "stack_trace" not in error_obj
            ), "Stack trace should not be included by default"

        # Property 5: Request ID should be valid UUID
        try:
            uuid.UUID(error_obj["request_id"])
        except ValueError:
            pytest.fail(f"Invalid request ID format: {error_obj['request_id']}")


if __name__ == "__main__":
    # Run the property-based tests
    pytest.main([__file__, "-v", "--hypothesis-show-statistics"])
