"""Test configuration management for FXML4 test suite.

This module provides centralized configuration management for tests,
including environment-specific settings and test data paths.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

import yaml


@dataclass
class TestConfig:
    """Test configuration container."""

    # Environment settings
    test_env: str = "test"
    debug_mode: bool = True
    log_level: str = "WARNING"

    # Database settings
    database_url: str = "sqlite:///test.db"
    database_host: str = "localhost"
    database_port: int = 5433
    database_name: str = "fxml4_test"
    database_user: str = "test_user"
    database_password: str = "test_password"

    # API settings
    api_host: str = "localhost"
    api_port: int = 8000
    api_timeout: int = 30

    # External service settings
    disable_external_apis: bool = True
    mock_network_calls: bool = True

    # Test execution settings
    test_timeout: int = 300  # 5 minutes
    parallel_workers: int = 4
    coverage_threshold: float = 60.0

    # Performance settings
    performance_test_iterations: int = 10
    memory_limit_mb: float = 512.0
    cpu_timeout_seconds: float = 60.0

    # File paths
    test_data_dir: Path = field(default_factory=lambda: Path("tests/fixtures/data"))
    temp_dir: Path = field(default_factory=lambda: Path("/tmp/fxml4_tests"))
    log_dir: Path = field(default_factory=lambda: Path("logs/tests"))

    # Test markers and selection
    default_markers: list = field(
        default_factory=lambda: ["not slow", "not requires_ib"]
    )
    skip_integration: bool = False
    skip_performance: bool = False
    skip_security: bool = False

    # API test settings
    test_api_keys: Dict[str, str] = field(
        default_factory=lambda: {
            "alpha_vantage": "test-key",
            "polygon": "test-key",
            "openai": "test-key",
            "anthropic": "test-key",
        }
    )

    # Broker test settings
    mock_brokers: bool = True
    ib_test_account: str = "TEST_ACCOUNT"
    ib_test_host: str = "127.0.0.1"
    ib_test_port: int = 7497

    # ML test settings
    test_model_dir: Path = field(default_factory=lambda: Path("tests/fixtures/models"))
    mock_ml_training: bool = True
    small_dataset_size: int = 100

    def __post_init__(self):
        """Post-initialization setup."""
        # Ensure Path objects
        if isinstance(self.test_data_dir, str):
            self.test_data_dir = Path(self.test_data_dir)
        if isinstance(self.temp_dir, str):
            self.temp_dir = Path(self.temp_dir)
        if isinstance(self.log_dir, str):
            self.log_dir = Path(self.log_dir)
        if isinstance(self.test_model_dir, str):
            self.test_model_dir = Path(self.test_model_dir)

        # Create directories if they don't exist
        for directory in [
            self.test_data_dir,
            self.temp_dir,
            self.log_dir,
            self.test_model_dir,
        ]:
            directory.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_environment(cls) -> "TestConfig":
        """Create configuration from environment variables."""
        config = cls()

        # Override with environment variables
        env_mapping = {
            "FXML4_TEST_ENV": "test_env",
            "FXML4_DEBUG": "debug_mode",
            "FXML4_LOG_LEVEL": "log_level",
            "FXML4_DB_HOST": "database_host",
            "FXML4_DB_PORT": "database_port",
            "FXML4_DB_NAME": "database_name",
            "FXML4_DB_USER": "database_user",
            "FXML4_DB_PASSWORD": "database_password",
            "FXML4_API_HOST": "api_host",
            "FXML4_API_PORT": "api_port",
            "FXML4_DISABLE_EXTERNAL_APIS": "disable_external_apis",
            "FXML4_MOCK_NETWORK": "mock_network_calls",
            "FXML4_TEST_TIMEOUT": "test_timeout",
            "FXML4_PARALLEL_WORKERS": "parallel_workers",
            "FXML4_COVERAGE_THRESHOLD": "coverage_threshold",
            "ALPHA_VANTAGE_API_KEY": ("test_api_keys", "alpha_vantage"),
            "POLYGON_API_KEY": ("test_api_keys", "polygon"),
            "OPENAI_API_KEY": ("test_api_keys", "openai"),
            "ANTHROPIC_API_KEY": ("test_api_keys", "anthropic"),
        }

        for env_var, attr_path in env_mapping.items():
            value = os.environ.get(env_var)
            if value is not None:
                if isinstance(attr_path, tuple):
                    # Nested attribute
                    obj = getattr(config, attr_path[0])
                    obj[attr_path[1]] = value
                else:
                    # Direct attribute
                    attr_type = type(getattr(config, attr_path))
                    if attr_type == bool:
                        value = value.lower() in ("true", "1", "yes", "on")
                    elif attr_type == int:
                        value = int(value)
                    elif attr_type == float:
                        value = float(value)
                    elif attr_type == Path:
                        value = Path(value)

                    setattr(config, attr_path, value)

        return config

    @classmethod
    def from_file(cls, config_file: Path) -> "TestConfig":
        """Load configuration from YAML file."""
        if not config_file.exists():
            raise FileNotFoundError(f"Config file not found: {config_file}")

        with open(config_file, "r") as f:
            data = yaml.safe_load(f)

        # Create base config from environment
        config = cls.from_environment()

        # Override with file settings
        for key, value in data.items():
            if hasattr(config, key):
                if isinstance(value, dict) and isinstance(getattr(config, key), dict):
                    # Merge dictionaries
                    getattr(config, key).update(value)
                else:
                    setattr(config, key, value)

        return config

    def get_database_url(self) -> str:
        """Get database URL for testing."""
        if self.database_url != "sqlite:///test.db":
            return self.database_url

        # Build PostgreSQL URL from components
        return (
            f"postgresql://{self.database_user}:{self.database_password}"
            f"@{self.database_host}:{self.database_port}/{self.database_name}"
        )

    def get_async_database_url(self) -> str:
        """Get async database URL for testing."""
        base_url = self.get_database_url()
        if base_url.startswith("postgresql://"):
            return base_url.replace("postgresql://", "postgresql+asyncpg://")
        return base_url

    def setup_environment(self):
        """Setup environment variables for testing."""
        env_vars = {
            "TESTING": "1",
            "FXML4_TEST_MODE": "1",
            "FXML4_LOG_LEVEL": self.log_level,
            "FXML4_DB_HOST": self.database_host,
            "FXML4_DB_PORT": str(self.database_port),
            "FXML4_DB_NAME": self.database_name,
            "FXML4_DB_USER": self.database_user,
            "FXML4_DB_PASSWORD": self.database_password,
            "FXML4_API_HOST": self.api_host,
            "FXML4_API_PORT": str(self.api_port),
            "PYTHONPATH": str(Path.cwd()),
        }

        if self.disable_external_apis:
            env_vars["FXML4_DISABLE_EXTERNAL_APIS"] = "1"

        if self.mock_network_calls:
            env_vars["FXML4_MOCK_NETWORK"] = "1"

        # Set API keys
        for service, key in self.test_api_keys.items():
            env_var = f"{service.upper()}_API_KEY"
            env_vars[env_var] = key

        # Update environment
        for key, value in env_vars.items():
            os.environ[key] = value

    def get_test_data_path(self, filename: str) -> Path:
        """Get path to test data file."""
        return self.test_data_dir / filename

    def get_temp_path(self, filename: str) -> Path:
        """Get path to temporary file."""
        return self.temp_dir / filename

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {}
        for key, value in self.__dict__.items():
            if isinstance(value, Path):
                result[key] = str(value)
            else:
                result[key] = value
        return result


class TestConfigManager:
    """Manages test configuration singleton."""

    _instance: Optional[TestConfig] = None

    @classmethod
    def get_config(cls) -> TestConfig:
        """Get test configuration instance."""
        if cls._instance is None:
            # Try to load from file first
            config_files = [
                Path("tests/config/test_config.yaml"),
                Path("test_config.yaml"),
                Path("config/test.yaml"),
            ]

            for config_file in config_files:
                if config_file.exists():
                    cls._instance = TestConfig.from_file(config_file)
                    break
            else:
                # Fall back to environment-based config
                cls._instance = TestConfig.from_environment()

        return cls._instance

    @classmethod
    def set_config(cls, config: TestConfig):
        """Set test configuration instance."""
        cls._instance = config

    @classmethod
    def reset(cls):
        """Reset configuration (for testing)."""
        cls._instance = None


# Predefined configurations for different test scenarios
TEST_CONFIGS = {
    "fast": TestConfig(
        default_markers=["fast", "not slow", "not requires_ib", "not requires_db"],
        skip_integration=True,
        skip_performance=True,
        test_timeout=60,
        performance_test_iterations=1,
    ),
    "unit": TestConfig(
        default_markers=["unit"],
        skip_integration=True,
        skip_performance=True,
        test_timeout=120,
    ),
    "integration": TestConfig(
        default_markers=["integration"],
        skip_performance=True,
        test_timeout=600,
        disable_external_apis=False,
    ),
    "performance": TestConfig(
        default_markers=["performance"],
        test_timeout=900,
        performance_test_iterations=100,
        memory_limit_mb=1024.0,
    ),
    "security": TestConfig(
        default_markers=["security"],
        test_timeout=300,
        disable_external_apis=False,
        mock_network_calls=False,
    ),
    "comprehensive": TestConfig(
        default_markers=["not requires_ib"],  # Exclude IB tests
        test_timeout=1800,  # 30 minutes
        coverage_threshold=80.0,
        disable_external_apis=False,
    ),
}


def get_test_config(preset: str = None) -> TestConfig:
    """Get test configuration."""
    if preset and preset in TEST_CONFIGS:
        config = TEST_CONFIGS[preset]
        config.setup_environment()
        return config

    return TestConfigManager.get_config()


def create_test_config_file(config: TestConfig, output_path: Path):
    """Create a test configuration file."""
    config_data = config.to_dict()

    with open(output_path, "w") as f:
        yaml.dump(config_data, f, indent=2, default_flow_style=False)


# Global configuration access
def config() -> TestConfig:
    """Get global test configuration."""
    return TestConfigManager.get_config()
