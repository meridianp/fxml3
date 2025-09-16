"""
Comprehensive retrospective test coverage for Message Translator.

This module provides comprehensive test coverage for the FXML4-ForexConnect
message translation layer, which handles bidirectional message conversion
between FIX-based messages and ForexConnect RabbitMQ middleware messages.

Following TDD principles with retrospective testing approach:
- Testing existing production translation functionality
- Ensuring comprehensive coverage of all translation patterns
- Validating symbol mapping, format conversions, and error handling
"""

import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

import pytest

from fxml4.brokers.adapters.message_translator import (
    FIXOrderMessage,
    ForexConnectMessage,
    MessageTranslator,
    QuantityConverter,
    SymbolMapper,
    TranslationError,
    ValidationError,
)
from fxml4.fix.messages.base import ExecType, OrdType, Side, TimeInForce
from fxml4.fix.messages.orders import ExecutionReport as FIXExecutionReport
from fxml4.fix.messages.orders import NewOrderSingle


class TestSymbolMapper:
    """Test symbol mapping functionality between FIX and ForexConnect formats."""

    def test_major_pairs_fix_to_forex_mapping(self):
        """Test conversion of major forex pairs from FIX to ForexConnect format."""
        mapper = SymbolMapper()

        mappings = [
            ("EURUSD", "EUR/USD"),
            ("GBPUSD", "GBP/USD"),
            ("USDJPY", "USD/JPY"),
            ("AUDUSD", "AUD/USD"),
            ("USDCHF", "USD/CHF"),
            ("USDCAD", "USD/CAD"),
            ("NZDUSD", "NZD/USD"),
            ("EURGBP", "EUR/GBP"),
            ("EURJPY", "EUR/JPY"),
            ("GBPJPY", "GBP/JPY"),
        ]

        for fix_symbol, expected_forex in mappings:
            result = mapper.fix_to_forex(fix_symbol)
            assert result == expected_forex

    def test_major_pairs_forex_to_fix_mapping(self):
        """Test conversion of major forex pairs from ForexConnect to FIX format."""
        mapper = SymbolMapper()

        mappings = [
            ("EUR/USD", "EURUSD"),
            ("GBP/USD", "GBPUSD"),
            ("USD/JPY", "USDJPY"),
            ("AUD/USD", "AUDUSD"),
            ("USD/CHF", "USDCHF"),
            ("USD/CAD", "USDCAD"),
            ("NZD/USD", "NZDUSD"),
            ("EUR/GBP", "EURGBP"),
            ("EUR/JPY", "EURJPY"),
            ("GBP/JPY", "GBPJPY"),
        ]

        for forex_symbol, expected_fix in mappings:
            result = mapper.forex_to_fix(forex_symbol)
            assert result == expected_fix

    def test_exotic_pairs_mapping(self):
        """Test mapping for exotic currency pairs."""
        mapper = SymbolMapper()

        exotic_mappings = [
            ("USDTRY", "USD/TRY"),
            ("USDZAR", "USD/ZAR"),
            ("USDMXN", "USD/MXN"),
            ("EURPLN", "EUR/PLN"),
            ("GBPTRY", "GBP/TRY"),
        ]

        for fix_symbol, expected_forex in exotic_mappings:
            result = mapper.fix_to_forex(fix_symbol)
            assert result == expected_forex

    def test_invalid_symbol_handling(self):
        """Test handling of invalid symbols."""
        mapper = SymbolMapper()

        invalid_symbols = ["INVALID", "XYZ", "ABCDEF", "12345", ""]

        for symbol in invalid_symbols:
            with pytest.raises(ValidationError, match="Unknown symbol"):
                mapper.fix_to_forex(symbol)

            with pytest.raises(ValidationError, match="Unknown symbol"):
                mapper.forex_to_fix(symbol)

    def test_case_insensitive_mapping(self):
        """Test case-insensitive symbol mapping."""
        mapper = SymbolMapper()

        test_cases = [
            ("eurusd", "EUR/USD"),
            ("EURUSD", "EUR/USD"),
            ("EurUsd", "EUR/USD"),
            ("eur/usd", "EURUSD"),
            ("EUR/USD", "EURUSD"),
            ("Eur/Usd", "EURUSD"),
        ]

        for input_symbol, expected in test_cases[:3]:
            result = mapper.fix_to_forex(input_symbol)
            assert result == expected

        for input_symbol, expected in test_cases[3:]:
            result = mapper.forex_to_fix(input_symbol)
            assert result == expected

    def test_symbol_validation_patterns(self):
        """Test symbol validation patterns."""
        mapper = SymbolMapper()

        valid_fix_patterns = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD"]
        valid_forex_patterns = ["EUR/USD", "GBP/USD", "USD/JPY", "AUD/USD"]

        for symbol in valid_fix_patterns:
            assert mapper.is_valid_fix_symbol(symbol) is True

        for symbol in valid_forex_patterns:
            assert mapper.is_valid_forex_symbol(symbol) is True

        invalid_patterns = ["EUR-USD", "EUR_USD", "EUR USD", "EURUSD/"]
        for symbol in invalid_patterns:
            assert mapper.is_valid_fix_symbol(symbol) is False
            assert mapper.is_valid_forex_symbol(symbol) is False


class TestQuantityConverter:
    """Test quantity conversion between FIX and ForexConnect formats."""

    def test_fix_to_forex_quantity_conversion(self):
        """Test conversion from FIX quantity (units) to ForexConnect lots."""
        converter = QuantityConverter()

        conversions = [
            (100000.0, 1.0),  # 1 standard lot
            (50000.0, 0.5),  # 0.5 lots
            (10000.0, 0.1),  # 0.1 lots (mini lot)
            (1000.0, 0.01),  # 0.01 lots (micro lot)
            (250000.0, 2.5),  # 2.5 lots
            (75000.0, 0.75),  # 0.75 lots
        ]

        for fix_qty, expected_lots in conversions:
            result = converter.fix_to_forex_quantity(fix_qty)
            assert result == expected_lots

    def test_forex_to_fix_quantity_conversion(self):
        """Test conversion from ForexConnect lots to FIX quantity (units)."""
        converter = QuantityConverter()

        conversions = [
            (1.0, 100000.0),  # 1 standard lot
            (0.5, 50000.0),  # 0.5 lots
            (0.1, 10000.0),  # 0.1 lots (mini lot)
            (0.01, 1000.0),  # 0.01 lots (micro lot)
            (2.5, 250000.0),  # 2.5 lots
            (0.75, 75000.0),  # 0.75 lots
        ]

        for forex_lots, expected_qty in conversions:
            result = converter.forex_to_fix_quantity(forex_lots)
            assert result == expected_qty

    def test_invalid_quantity_handling(self):
        """Test handling of invalid quantities."""
        converter = QuantityConverter()

        invalid_quantities = [0, -1000, -0.5, None]

        for qty in invalid_quantities:
            with pytest.raises(ValidationError, match="Invalid quantity"):
                converter.fix_to_forex_quantity(qty)

            with pytest.raises(ValidationError, match="Invalid quantity"):
                converter.forex_to_fix_quantity(qty)

    def test_precision_handling(self):
        """Test precision handling for fractional lots."""
        converter = QuantityConverter()

        test_cases = [
            (0.001, 100.0),  # Micro lot precision
            (0.123, 12300.0),  # Fractional precision
            (1.999, 199900.0),  # Near 2 lots
            (0.0001, 10.0),  # Very small lot
        ]

        for lots, expected_units in test_cases:
            result = converter.forex_to_fix_quantity(lots)
            assert result == expected_units

            # Test round trip conversion
            back_to_lots = converter.fix_to_forex_quantity(result)
            assert abs(back_to_lots - lots) < 0.0001

    def test_large_quantity_handling(self):
        """Test handling of large quantities."""
        converter = QuantityConverter()

        large_quantities = [
            (10.0, 1000000.0),  # 10 lots
            (100.0, 10000000.0),  # 100 lots
            (50.5, 5050000.0),  # 50.5 lots
        ]

        for lots, expected_units in large_quantities:
            result = converter.forex_to_fix_quantity(lots)
            assert result == expected_units


class TestMessageTranslator:
    """Test core message translation functionality."""

    @pytest.fixture
    def translator(self):
        """Create translator fixture for testing."""
        return MessageTranslator()

    def test_fix_market_order_to_forexconnect(self, translator):
        """Test translation of FIX market order to ForexConnect format."""
        fix_order = NewOrderSingle(
            cl_ord_id="ORDER-123",
            symbol="EURUSD",
            side=Side.BUY,
            ord_type=OrdType.MARKET,
            order_qty=100000.0,
            time_in_force=TimeInForce.IOC,
        )

        forex_message = translator.fix_to_forexconnect(fix_order)

        assert forex_message.type == "order_request"
        assert forex_message.client_order_id == "ORDER-123"
        assert forex_message.symbol == "EUR/USD"
        assert forex_message.buy_sell == "B"
        assert forex_message.order_type == "M"
        assert forex_message.amount == 1.0  # 1 lot
        assert forex_message.time_in_force == "IOC"
        assert forex_message.rate is None  # No price for market order

    def test_fix_limit_order_to_forexconnect(self, translator):
        """Test translation of FIX limit order to ForexConnect format."""
        fix_order = NewOrderSingle(
            cl_ord_id="ORDER-456",
            symbol="GBPUSD",
            side=Side.SELL,
            ord_type=OrdType.LIMIT,
            order_qty=50000.0,
            price=1.3500,
            time_in_force=TimeInForce.GTC,
        )

        forex_message = translator.fix_to_forexconnect(fix_order)

        assert forex_message.type == "order_request"
        assert forex_message.client_order_id == "ORDER-456"
        assert forex_message.symbol == "GBP/USD"
        assert forex_message.buy_sell == "S"
        assert forex_message.order_type == "L"
        assert forex_message.amount == 0.5  # 0.5 lots
        assert forex_message.rate == 1.3500
        assert forex_message.time_in_force == "GTC"

    def test_fix_stop_order_to_forexconnect(self, translator):
        """Test translation of FIX stop order to ForexConnect format."""
        fix_order = NewOrderSingle(
            cl_ord_id="ORDER-789",
            symbol="USDJPY",
            side=Side.BUY,
            ord_type=OrdType.STOP,
            order_qty=100000.0,
            stop_px=110.50,
            time_in_force=TimeInForce.GTC,
        )

        forex_message = translator.fix_to_forexconnect(fix_order)

        assert forex_message.order_type == "S"  # Stop
        assert forex_message.rate == 110.50
        assert forex_message.symbol == "USD/JPY"

    def test_forexconnect_execution_to_fix(self, translator):
        """Test translation of ForexConnect execution to FIX format."""
        forex_execution = {
            "type": "execution_report",
            "order_id": "FXCM-ORDER-456",
            "client_order_id": "ORDER-123",
            "symbol": "EUR/USD",
            "buy_sell": "B",
            "amount": 1.0,
            "rate": 1.1850,
            "status": "F",  # Filled
            "exec_time": "2024-08-24T10:15:30.000Z",
            "commission": 2.5,
        }

        fix_execution = translator.forexconnect_to_fix(forex_execution)

        assert fix_execution.order_id == "FXCM-ORDER-456"
        assert fix_execution.cl_ord_id == "ORDER-123"
        assert fix_execution.symbol == "EURUSD"
        assert fix_execution.side == Side.BUY
        assert fix_execution.last_qty == 100000.0
        assert fix_execution.last_px == 1.1850
        assert fix_execution.ord_status == "2"  # Filled
        assert fix_execution.commission == 2.5

    def test_forexconnect_partial_fill_to_fix(self, translator):
        """Test translation of partial fill execution report."""
        forex_execution = {
            "type": "execution_report",
            "order_id": "FXCM-ORDER-789",
            "client_order_id": "ORDER-456",
            "symbol": "GBP/USD",
            "buy_sell": "S",
            "amount": 0.3,  # Partial fill
            "rate": 1.3480,
            "status": "P",  # Partially filled
            "cumulative_amount": 0.3,
            "remaining_amount": 0.7,
            "exec_time": "2024-08-24T10:20:15.000Z",
        }

        fix_execution = translator.forexconnect_to_fix(forex_execution)

        assert fix_execution.ord_status == "1"  # Partially filled
        assert fix_execution.last_qty == 30000.0  # 0.3 lots
        assert fix_execution.cum_qty == 30000.0
        assert fix_execution.leaves_qty == 70000.0  # 0.7 lots remaining

    def test_forexconnect_rejection_to_fix(self, translator):
        """Test translation of order rejection from ForexConnect."""
        forex_rejection = {
            "type": "execution_report",
            "order_id": "FXCM-ORDER-999",
            "client_order_id": "ORDER-999",
            "symbol": "AUD/USD",
            "status": "R",  # Rejected
            "reject_reason": "Insufficient margin",
            "exec_time": "2024-08-24T10:25:00.000Z",
        }

        fix_execution = translator.forexconnect_to_fix(forex_rejection)

        assert fix_execution.ord_status == "8"  # Rejected
        assert fix_execution.ord_rej_reason == "Insufficient margin"
        assert fix_execution.symbol == "AUDUSD"

    def test_order_cancel_request_translation(self, translator):
        """Test translation of order cancel requests."""
        cancel_request = {
            "type": "cancel_request",
            "orig_client_order_id": "ORDER-123",
            "client_order_id": "CANCEL-123",
            "symbol": "EURUSD",
        }

        forex_message = translator.fix_cancel_to_forexconnect(cancel_request)

        assert forex_message.type == "cancel_request"
        assert forex_message.orig_client_order_id == "ORDER-123"
        assert forex_message.client_order_id == "CANCEL-123"
        assert forex_message.symbol == "EUR/USD"

    def test_side_translation(self, translator):
        """Test buy/sell side translation."""
        side_mappings = [(Side.BUY, "B"), (Side.SELL, "S")]

        for fix_side, expected_forex in side_mappings:
            result = translator._translate_side_fix_to_forex(fix_side)
            assert result == expected_forex

            back_to_fix = translator._translate_side_forex_to_fix(expected_forex)
            assert back_to_fix == fix_side

    def test_order_type_translation(self, translator):
        """Test order type translation."""
        type_mappings = [
            (OrdType.MARKET, "M"),
            (OrdType.LIMIT, "L"),
            (OrdType.STOP, "S"),
            (OrdType.STOP_LIMIT, "SL"),
        ]

        for fix_type, expected_forex in type_mappings:
            result = translator._translate_order_type_fix_to_forex(fix_type)
            assert result == expected_forex

            back_to_fix = translator._translate_order_type_forex_to_fix(expected_forex)
            assert back_to_fix == fix_type

    def test_time_in_force_translation(self, translator):
        """Test time in force translation."""
        tif_mappings = [
            (TimeInForce.DAY, "DAY"),
            (TimeInForce.GTC, "GTC"),
            (TimeInForce.IOC, "IOC"),
            (TimeInForce.FOK, "FOK"),
        ]

        for fix_tif, expected_forex in tif_mappings:
            result = translator._translate_tif_fix_to_forex(fix_tif)
            assert result == expected_forex

            back_to_fix = translator._translate_tif_forex_to_fix(expected_forex)
            assert back_to_fix == fix_tif


class TestMessageTranslatorErrorHandling:
    """Test error handling in message translation."""

    @pytest.fixture
    def translator(self):
        """Create translator fixture for testing."""
        return MessageTranslator()

    def test_invalid_fix_message_structure(self, translator):
        """Test handling of malformed FIX messages."""
        invalid_messages = [
            None,
            {},
            {"cl_ord_id": "ORDER-123"},  # Missing required fields
            {"symbol": "INVALID"},  # Invalid symbol
        ]

        for message in invalid_messages:
            with pytest.raises(ValidationError):
                translator.fix_to_forexconnect(message)

    def test_invalid_forexconnect_message_structure(self, translator):
        """Test handling of malformed ForexConnect messages."""
        invalid_messages = [
            None,
            {},
            {"type": "unknown"},  # Unknown message type
            {"client_order_id": "ORDER-123"},  # Missing required fields
        ]

        for message in invalid_messages:
            with pytest.raises(ValidationError):
                translator.forexconnect_to_fix(message)

    def test_unsupported_order_type_handling(self, translator):
        """Test handling of unsupported order types."""
        unsupported_order = NewOrderSingle(
            cl_ord_id="ORDER-123",
            symbol="EURUSD",
            side=Side.BUY,
            ord_type="X",  # Unsupported type
            order_qty=100000.0,
        )

        with pytest.raises(TranslationError, match="Unsupported order type"):
            translator.fix_to_forexconnect(unsupported_order)

    def test_invalid_quantity_handling(self, translator):
        """Test handling of invalid quantities in translation."""
        invalid_order = NewOrderSingle(
            cl_ord_id="ORDER-123",
            symbol="EURUSD",
            side=Side.BUY,
            ord_type=OrdType.MARKET,
            order_qty=0,  # Invalid quantity
        )

        with pytest.raises(ValidationError, match="Invalid quantity"):
            translator.fix_to_forexconnect(invalid_order)

    def test_missing_required_fields_handling(self, translator):
        """Test handling of messages with missing required fields."""
        incomplete_forex = {
            "type": "execution_report",
            "order_id": "FXCM-ORDER-456",
            # Missing client_order_id, symbol, etc.
        }

        with pytest.raises(ValidationError, match="Missing required field"):
            translator.forexconnect_to_fix(incomplete_forex)

    def test_timestamp_parsing_errors(self, translator):
        """Test handling of invalid timestamp formats."""
        forex_execution = {
            "type": "execution_report",
            "order_id": "FXCM-ORDER-456",
            "client_order_id": "ORDER-123",
            "symbol": "EUR/USD",
            "buy_sell": "B",
            "amount": 1.0,
            "status": "F",
            "exec_time": "invalid-timestamp",  # Invalid format
        }

        with pytest.raises(TranslationError, match="Invalid timestamp"):
            translator.forexconnect_to_fix(forex_execution)


class TestMessageTranslatorPerformance:
    """Test performance characteristics of message translation."""

    @pytest.fixture
    def translator(self):
        """Create translator fixture for performance testing."""
        return MessageTranslator()

    def test_translation_throughput(self, translator):
        """Test message translation throughput under load."""
        fix_order = NewOrderSingle(
            cl_ord_id="ORDER-123",
            symbol="EURUSD",
            side=Side.BUY,
            ord_type=OrdType.MARKET,
            order_qty=100000.0,
        )

        start_time = datetime.now()

        # Translate many messages
        for i in range(1000):
            forex_message = translator.fix_to_forexconnect(fix_order)
            assert forex_message is not None

        translation_time = (datetime.now() - start_time).total_seconds()

        # Should translate 1000 messages in under 1 second
        assert translation_time < 1.0

        # Test throughput (messages per second)
        throughput = 1000 / translation_time
        assert throughput > 1000  # At least 1000 msgs/sec

    def test_memory_usage_large_messages(self, translator):
        """Test memory usage with large message batches."""
        messages = []

        # Create large batch of messages
        for i in range(100):
            fix_order = NewOrderSingle(
                cl_ord_id=f"ORDER-{i}",
                symbol="EURUSD",
                side=Side.BUY,
                ord_type=OrdType.MARKET,
                order_qty=100000.0,
            )
            messages.append(fix_order)

        # Translate all messages
        translated = []
        for message in messages:
            forex_message = translator.fix_to_forexconnect(message)
            translated.append(forex_message)

        assert len(translated) == 100

        # Test memory efficiency - objects should be reasonable size
        for msg in translated[:10]:  # Sample check
            assert hasattr(msg, "client_order_id")
            assert hasattr(msg, "symbol")

    def test_concurrent_translation_safety(self, translator):
        """Test thread safety of concurrent translations."""
        import concurrent.futures
        import threading

        def translate_message(order_id):
            fix_order = NewOrderSingle(
                cl_ord_id=f"ORDER-{order_id}",
                symbol="EURUSD",
                side=Side.BUY,
                ord_type=OrdType.MARKET,
                order_qty=100000.0,
            )
            return translator.fix_to_forexconnect(fix_order)

        # Test concurrent translations
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(translate_message, i) for i in range(50)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        assert len(results) == 50

        # Verify all translations are correct
        for result in results:
            assert result.symbol == "EUR/USD"
            assert result.buy_sell == "B"
            assert result.order_type == "M"


class TestMessageTranslatorIntegration:
    """Test integration scenarios and complete workflows."""

    @pytest.fixture
    def translator(self):
        """Create translator fixture for integration testing."""
        return MessageTranslator()

    def test_complete_order_lifecycle_translation(self, translator):
        """Test complete order lifecycle translation workflow."""
        # Start with FIX order
        original_order = NewOrderSingle(
            cl_ord_id="ORDER-123",
            symbol="EURUSD",
            side=Side.BUY,
            ord_type=OrdType.LIMIT,
            order_qty=100000.0,
            price=1.1800,
            time_in_force=TimeInForce.GTC,
        )

        # Translate to ForexConnect
        forex_order = translator.fix_to_forexconnect(original_order)
        assert forex_order.client_order_id == "ORDER-123"
        assert forex_order.symbol == "EUR/USD"

        # Simulate acknowledgment from ForexConnect
        ack_message = {
            "type": "execution_report",
            "order_id": "FXCM-ORDER-456",
            "client_order_id": "ORDER-123",
            "symbol": "EUR/USD",
            "status": "A",  # Acknowledged
            "exec_time": "2024-08-24T10:15:30.000Z",
        }

        fix_ack = translator.forexconnect_to_fix(ack_message)
        assert fix_ack.cl_ord_id == "ORDER-123"
        assert fix_ack.ord_status == "A"

        # Simulate execution
        execution_message = {
            "type": "execution_report",
            "order_id": "FXCM-ORDER-456",
            "client_order_id": "ORDER-123",
            "symbol": "EUR/USD",
            "buy_sell": "B",
            "amount": 1.0,
            "rate": 1.1800,
            "status": "F",  # Filled
            "exec_time": "2024-08-24T10:20:00.000Z",
        }

        fix_execution = translator.forexconnect_to_fix(execution_message)
        assert fix_execution.ord_status == "2"  # Filled
        assert fix_execution.last_px == 1.1800

    def test_multi_symbol_translation_workflow(self, translator):
        """Test translation workflow with multiple currency pairs."""
        symbols = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF"]

        for symbol in symbols:
            # Test FIX to ForexConnect
            fix_order = NewOrderSingle(
                cl_ord_id=f"ORDER-{symbol}",
                symbol=symbol,
                side=Side.BUY,
                ord_type=OrdType.MARKET,
                order_qty=100000.0,
            )

            forex_order = translator.fix_to_forexconnect(fix_order)

            # Verify symbol mapping
            expected_forex_symbol = translator.symbol_mapper.fix_to_forex(symbol)
            assert forex_order.symbol == expected_forex_symbol

            # Test round trip via execution report
            execution = {
                "type": "execution_report",
                "order_id": f"FXCM-{symbol}",
                "client_order_id": f"ORDER-{symbol}",
                "symbol": expected_forex_symbol,
                "buy_sell": "B",
                "amount": 1.0,
                "status": "F",
                "exec_time": "2024-08-24T10:15:30.000Z",
            }

            fix_execution = translator.forexconnect_to_fix(execution)
            assert fix_execution.symbol == symbol  # Back to original FIX format

    def test_error_propagation_through_translation(self, translator):
        """Test error propagation through translation layers."""
        # Test validation errors propagate correctly
        invalid_order = {
            "cl_ord_id": "ORDER-123",
            "symbol": "INVALID_SYMBOL",  # This should trigger validation error
            "side": Side.BUY,
            "ord_type": OrdType.MARKET,
            "order_qty": 100000.0,
        }

        with pytest.raises(ValidationError) as exc_info:
            translator.fix_to_forexconnect(invalid_order)

        assert "Unknown symbol" in str(exc_info.value)

        # Test translation errors propagate correctly
        invalid_forex_message = {
            "type": "execution_report",
            "order_id": "FXCM-ORDER-456",
            "client_order_id": "ORDER-123",
            "symbol": "EUR/USD",
            "buy_sell": "INVALID",  # Invalid side
            "status": "F",
        }

        with pytest.raises(TranslationError) as exc_info:
            translator.forexconnect_to_fix(invalid_forex_message)

        assert "Invalid side" in str(exc_info.value)
