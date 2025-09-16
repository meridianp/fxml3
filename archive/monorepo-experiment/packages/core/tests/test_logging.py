"""Tests for logging module."""

import json
import logging
from io import StringIO
import pytest
from fxml4_core.logging import configure_logging, get_logger


def test_json_logging(caplog):
    """Test JSON logging output."""
    configure_logging(level=logging.INFO, format_as_json=True)
    logger = get_logger("test")
    
    with caplog.at_level(logging.INFO):
        logger.info("test message", user="john", count=42)
    
    # Check that log was captured
    assert len(caplog.records) == 1
    
    # Parse JSON output
    log_output = caplog.records[0].getMessage()
    log_data = json.loads(log_output)
    
    assert log_data["event"] == "test message"
    assert log_data["user"] == "john"
    assert log_data["count"] == 42
    assert "timestamp" in log_data


def test_text_logging(caplog):
    """Test text logging output."""
    configure_logging(level=logging.INFO, format_as_json=False)
    logger = get_logger("test")
    
    with caplog.at_level(logging.INFO):
        logger.info("test message")
    
    assert "test message" in caplog.text


def test_logger_context_binding():
    """Test logger context binding."""
    logger = get_logger("test", service="api", version="1.0")
    
    # Logger should have bound context
    assert hasattr(logger, "_context")
    assert logger._context["service"] == "api"
    assert logger._context["version"] == "1.0"