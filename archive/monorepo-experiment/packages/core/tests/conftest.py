"""Pytest configuration for fxml4-core tests."""

import pytest
import os
import tempfile
from pathlib import Path


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def clean_env(monkeypatch):
    """Clean environment variables with FXML4_ prefix."""
    env_vars = [key for key in os.environ if key.startswith("FXML4_")]
    for var in env_vars:
        monkeypatch.delenv(var, raising=False)
    yield


@pytest.fixture
def mock_config(monkeypatch):
    """Mock configuration values."""
    config = {
        "FXML4_APP_NAME": "test-app",
        "FXML4_ENVIRONMENT": "testing",
        "FXML4_DEBUG": "true",
        "FXML4_LOG_LEVEL": "DEBUG",
        "FXML4_API_PORT": "9999",
        "FXML4_DATABASE_URL": "postgresql://test:test@localhost/testdb",
    }
    
    for key, value in config.items():
        monkeypatch.setenv(key, value)
    
    return config