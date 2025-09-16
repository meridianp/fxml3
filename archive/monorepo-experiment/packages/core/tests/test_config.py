"""Tests for configuration module."""

import os
import pytest
from fxml4_core.config import BaseConfig


def test_default_config():
    """Test default configuration values."""
    config = BaseConfig()
    assert config.app_name == "fxml4"
    assert config.environment == "development"
    assert config.debug is False
    assert config.log_level == "INFO"
    assert config.api_port == 8000


def test_config_from_env(monkeypatch):
    """Test configuration from environment variables."""
    monkeypatch.setenv("FXML4_APP_NAME", "test-app")
    monkeypatch.setenv("FXML4_DEBUG", "true")
    monkeypatch.setenv("FXML4_API_PORT", "9000")
    
    config = BaseConfig()
    assert config.app_name == "test-app"
    assert config.debug is True
    assert config.api_port == 9000


def test_config_case_insensitive(monkeypatch):
    """Test that config is case insensitive."""
    monkeypatch.setenv("fxml4_environment", "production")
    config = BaseConfig()
    assert config.environment == "production"