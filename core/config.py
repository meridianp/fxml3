"""
Configuration module for FXML4.

This module provides centralized configuration management with production security validation.
"""

import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

# Load .env file if it exists
try:
    from dotenv import load_dotenv

    # Load .env from project root
    project_root = Path(__file__).parent.parent
    env_file = project_root / ".env"
    if env_file.exists():
        load_dotenv(env_file)
        logger = logging.getLogger(__name__)
        logger.info(f"Loaded environment variables from {env_file}")
except ImportError:
    # dotenv not available, environment variables must be set manually
    pass


logger = logging.getLogger(__name__)


class ProductionSecurityError(Exception):
    """Raised when production security requirements are not met."""

    pass


class ConfigValidationError(Exception):
    """Raised when configuration validation fails."""

    pass


class Config:
    """Configuration manager for FXML4."""

    def __init__(
        self, config_path: Optional[str] = None, validate_production: bool = None
    ):
        """Initialize configuration.

        Args:
            config_path: Path to configuration file
            validate_production: Whether to validate production requirements.
                                If None, auto-detects based on FXML4_ENV.
        """
        self._config = {}
        self._load_config(config_path)

        # Auto-detect production environment if not specified
        if validate_production is None:
            env = os.environ.get("FXML4_ENV", "development").lower()
            validate_production = env == "production"

        if validate_production:
            self._validate_production_requirements()

    def _load_config(self, config_path: Optional[str] = None):
        """Load configuration from file."""
        if config_path is None:
            # Look for config in standard locations
            project_root = Path(__file__).parent.parent
            config_locations = [
                project_root / "config" / "default.yaml",
                project_root / "config" / "config.yaml",
                Path.home() / ".fxml4" / "config.yaml",
                Path("/etc/fxml4/config.yaml"),
            ]

            for location in config_locations:
                if location.exists():
                    config_path = str(location)
                    break

        # Start with default configuration
        self._config = self._get_default_config()

        # Override with config file if exists
        if config_path and Path(config_path).exists():
            with open(config_path, "r") as f:
                file_config = yaml.safe_load(f) or {}
                # Perform environment variable substitution
                file_config = self._substitute_env_vars(file_config)
                self._merge_configs(self._config, file_config)

        # Override with environment variables
        self._override_with_env()

    def _substitute_env_vars(self, config: Any) -> Any:
        """Recursively substitute environment variables in configuration.

        Supports syntax: ${VAR_NAME:-default_value}
        """
        if isinstance(config, dict):
            return {k: self._substitute_env_vars(v) for k, v in config.items()}
        elif isinstance(config, list):
            return [self._substitute_env_vars(item) for item in config]
        elif isinstance(config, str):
            # Pattern to match ${VAR:-default} or ${VAR}
            pattern = r"\$\{([^}]+)\}"

            def replace_env_var(match):
                var_expr = match.group(1)
                if ":-" in var_expr:
                    var_name, default_value = var_expr.split(":-", 1)
                    # Remove quotes from default value
                    default_value = default_value.strip("\"'")
                    return os.environ.get(var_name, default_value)
                else:
                    var_name = var_expr
                    env_value = os.environ.get(var_name)
                    if env_value is None:
                        # For development, provide sensible defaults for non-critical vars
                        if var_name in [
                            "ALPHA_VANTAGE_API_KEY",
                            "OPENAI_API_KEY",
                            "PINECONE_API_KEY",
                        ]:
                            logger.warning(
                                f"Environment variable {var_name} not set, using placeholder"
                            )
                            return "NOT_SET"
                        else:
                            raise ValueError(
                                f"Environment variable {var_name} is required but not set"
                            )
                    return env_value

            return re.sub(pattern, replace_env_var, config)
        else:
            return config

    def _merge_configs(self, default: Dict[str, Any], override: Dict[str, Any]):
        """Recursively merge configuration dictionaries."""
        for key, value in override.items():
            if (
                key in default
                and isinstance(default[key], dict)
                and isinstance(value, dict)
            ):
                self._merge_configs(default[key], value)
            else:
                default[key] = value

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration."""
        return {
            "database": {
                "host": "localhost",
                "port": 5432,
                "name": "fxml4",
                "user": "postgres",
                "password": "password",
            },
            "timescaledb": {
                "host": "localhost",
                "port": 5433,
                "name": "fxml4",
                "user": "postgres",
                "password": "password",
            },
            "api": {"host": "0.0.0.0", "port": 8000, "debug": False},
            "polygon": {
                "api_key": os.environ.get("POLYGON_API_KEY", ""),
                "base_url": "https://api.polygon.io",
            },
            "alpha_vantage": {
                "api_key": os.environ.get("ALPHA_VANTAGE_API_KEY", ""),
                "base_url": "https://www.alphavantage.co",
            },
            "interactive_brokers": {"host": "127.0.0.1", "port": 7497, "client_id": 1},
            "redis": {"host": "localhost", "port": 6379, "db": 0},
            "logging": {
                "level": "INFO",
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            },
            "ml": {
                "models_dir": "models",
                "data_dir": "data",
                "features_version": "v1",
            },
            "backtesting": {
                "initial_capital": 10000,
                "commission": 0.001,
                "slippage": 0.0001,
            },
        }

    def _override_with_env(self):
        """Override configuration with environment variables."""
        # Database - support both legacy and FXML4 prefixed variables
        env_mappings = [
            ("DB_HOST", "FXML4_DATABASE_HOST", ["database", "host"]),
            ("DB_PORT", "FXML4_DATABASE_PORT", ["database", "port"], int),
            ("DB_NAME", "FXML4_DATABASE_NAME", ["database", "name"]),
            ("DB_USER", "FXML4_DATABASE_USER", ["database", "user"]),
            ("DB_PASSWORD", "FXML4_DATABASE_PASSWORD", ["database", "password"]),
            # TimescaleDB
            ("TIMESCALE_HOST", "FXML4_TIMESCALE_HOST", ["timescaledb", "host"]),
            ("TIMESCALE_PORT", "FXML4_TIMESCALE_PORT", ["timescaledb", "port"], int),
            # API Keys
            ("POLYGON_API_KEY", None, ["polygon", "api_key"]),
            ("ALPHA_VANTAGE_API_KEY", None, ["alpha_vantage", "api_key"]),
            ("FRED_API_KEY", None, ["fred", "api_key"]),
            ("OPENAI_API_KEY", None, ["openai", "api_key"]),
            ("PINECONE_API_KEY", None, ["pinecone", "api_key"]),
            ("PINECONE_ENVIRONMENT", None, ["pinecone", "environment"]),
            # IB
            ("IB_HOST", "FXML4_IB_HOST", ["interactive_brokers", "host"]),
            ("IB_PORT", "FXML4_IB_PORT", ["interactive_brokers", "port"], int),
            # API Configuration
            ("FXML4_API_HOST", None, ["api", "host"]),
            ("FXML4_API_PORT", None, ["api", "port"], int),
            ("FXML4_API_DEBUG", None, ["api", "debug"], lambda x: x.lower() == "true"),
            # JWT Configuration
            ("FXML4_JWT_SECRET_KEY", None, ["api", "auth", "secret_key"]),
            (
                "FXML4_JWT_TOKEN_EXPIRE_MINUTES",
                None,
                ["api", "auth", "token_expire_minutes"],
                int,
            ),
        ]

        for mapping in env_mappings:
            env_var1 = mapping[0]
            env_var2 = mapping[1] if len(mapping) > 1 else None
            config_path = mapping[2] if len(mapping) > 2 else []
            converter = mapping[3] if len(mapping) > 3 else None

            # Check both environment variables (prefer FXML4 prefixed)
            value = None
            if env_var2 and os.environ.get(env_var2):
                value = os.environ[env_var2]
            elif os.environ.get(env_var1):
                value = os.environ[env_var1]

            if value is not None and config_path:
                # Apply converter if specified
                if converter:
                    try:
                        value = converter(value)
                    except (ValueError, TypeError):
                        continue

                # Set nested configuration
                config = self._config
                for key in config_path[:-1]:
                    if key not in config:
                        config[key] = {}
                    config = config[key]
                config[config_path[-1]] = value

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by key."""
        keys = key.split(".")
        value = self._config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def set(self, key: str, value: Any):
        """Set configuration value."""
        keys = key.split(".")
        config = self._config

        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]

        config[keys[-1]] = value

    def get_database_url(self, db_type: str = "postgresql") -> str:
        """Get database connection URL."""
        db = self._config.get("database", {})

        # Validate required database fields
        required_fields = ["host", "port", "name", "user", "password"]
        for field in required_fields:
            if field not in db:
                raise ValueError(
                    f"Database configuration missing required field: {field}"
                )

        return (
            f"postgresql://{db['user']}:{db['password']}@"
            f"{db['host']}:{db['port']}/{db['name']}"
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return self._config.copy()

    def _validate_production_requirements(self) -> None:
        """Validate that production security requirements are met."""
        errors = []
        warnings = []

        # Define critical production requirements
        required_secrets = [
            ("FXML4_JWT_SECRET_KEY", "JWT signing secret", 32),
            ("FXML4_DATABASE_PASSWORD", "Database password", 12),
            ("ALPHA_VANTAGE_API_KEY", "Alpha Vantage API key", 8),
            ("OPENAI_API_KEY", "OpenAI API key", 20),
            ("DATA_ENCRYPTION_KEY", "Data encryption key", 32),
        ]

        # Check for required secrets
        for env_var, description, min_length in required_secrets:
            value = os.environ.get(env_var)

            if not value:
                errors.append(
                    f"MISSING: {env_var} ({description}) is required for production"
                )
            elif len(value) < min_length:
                errors.append(
                    f"WEAK: {env_var} must be at least {min_length} characters"
                )
            elif value.lower() in ["password", "secret", "key", "changeme", "default"]:
                errors.append(f"INSECURE: {env_var} uses a common/default value")

        # Check database SSL configuration
        ssl_mode = self.get("database.ssl_mode", "disable")
        if ssl_mode == "disable":
            warnings.append(
                "DATABASE: SSL is disabled. Enable with FXML4_DATABASE_SSL_MODE=require"
            )

        # Check Interactive Brokers port
        ib_port = self.get("data.data_feeds.ib.port", 7497)
        if ib_port == 7497:
            warnings.append(
                "IB: Using paper trading port 7497. Set IB_PORT=7496 for live trading"
            )

        # Check API debug mode
        if self.get("api.debug", False):
            warnings.append(
                "API: Debug mode is enabled. Set FXML4_API_DEBUG=false for production"
            )

        # Check for insecure defaults
        jwt_secret = self.get("api.auth.secret_key", "")
        if "INSECURE" in jwt_secret or "DEFAULT" in jwt_secret:
            errors.append("JWT: Secret key contains insecure default value")

        # Log warnings
        if warnings:
            logger.warning("Production security warnings:")
            for warning in warnings:
                logger.warning(f"  ⚠️  {warning}")

        # Fail on errors
        if errors:
            error_msg = "Production security validation failed:\n"
            for error in errors:
                error_msg += f"  ❌ {error}\n"
            error_msg += "\nSet required environment variables before starting in production mode."
            raise ProductionSecurityError(error_msg)

        logger.info("✅ Production security validation passed")


# Global configuration instance
_config_instance = None


def get_config(config_path: Optional[str] = None) -> Config:
    """Get global configuration instance."""
    global _config_instance

    if _config_instance is None:
        _config_instance = Config(config_path)

    return _config_instance


def reset_config():
    """Reset global configuration instance."""
    global _config_instance
    _config_instance = None


# Convenience functions
def get(key: str, default: Any = None) -> Any:
    """Get configuration value."""
    return get_config().get(key, default)


def set(key: str, value: Any):
    """Set configuration value."""
    get_config().set(key, value)
