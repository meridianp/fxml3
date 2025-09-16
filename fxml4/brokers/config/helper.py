"""Configuration Helper for Broker System.

This module provides standardized configuration parsing and validation
for broker adapters, eliminating code duplication and ensuring consistent
configuration handling across all broker components.
"""

import logging
import os
from dataclasses import dataclass, field, fields
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, Union

import yaml

from ...config import get_config

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ConfigurationError(Exception):
    """Exception raised for configuration errors."""

    pass


@dataclass
class ConnectionLimits:
    """Connection and rate limiting configuration."""

    max_connections: int = 10
    max_orders_per_second: int = 10
    max_requests_per_minute: int = 600
    connection_timeout_seconds: int = 30
    request_timeout_seconds: int = 10
    max_retries: int = 3
    retry_delay_seconds: float = 1.0
    retry_backoff_multiplier: float = 2.0

    def validate(self):
        """Validate limits configuration."""
        if self.max_connections <= 0:
            raise ConfigurationError("max_connections must be positive")
        if self.max_orders_per_second <= 0:
            raise ConfigurationError("max_orders_per_second must be positive")
        if self.connection_timeout_seconds <= 0:
            raise ConfigurationError("connection_timeout_seconds must be positive")


@dataclass
class SecurityConfig:
    """Security configuration for broker connections."""

    use_ssl: bool = True
    ssl_cert_path: Optional[str] = None
    ssl_key_path: Optional[str] = None
    ssl_ca_path: Optional[str] = None
    verify_ssl: bool = True

    # Authentication
    username: Optional[str] = None
    password: Optional[str] = None
    api_key: Optional[str] = None
    secret_key: Optional[str] = None

    # Token-based auth
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_url: Optional[str] = None

    def validate(self):
        """Validate security configuration."""
        if self.use_ssl:
            if self.ssl_cert_path and not Path(self.ssl_cert_path).exists():
                raise ConfigurationError(
                    f"SSL certificate not found: {self.ssl_cert_path}"
                )
            if self.ssl_key_path and not Path(self.ssl_key_path).exists():
                raise ConfigurationError(f"SSL key not found: {self.ssl_key_path}")
            if self.ssl_ca_path and not Path(self.ssl_ca_path).exists():
                raise ConfigurationError(
                    f"SSL CA certificate not found: {self.ssl_ca_path}"
                )


@dataclass
class LoggingConfig:
    """Logging configuration for broker components."""

    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file_path: Optional[str] = None
    max_file_size_mb: int = 100
    backup_count: int = 5

    # Component-specific logging levels
    adapter_level: Optional[str] = None
    messaging_level: Optional[str] = None
    risk_level: Optional[str] = None
    compliance_level: Optional[str] = None

    def validate(self):
        """Validate logging configuration."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if self.level.upper() not in valid_levels:
            raise ConfigurationError(f"Invalid log level: {self.level}")


@dataclass
class MonitoringConfig:
    """Monitoring and metrics configuration."""

    enabled: bool = True
    metrics_port: int = 9090
    health_check_interval_seconds: int = 30

    # Performance metrics
    track_latency: bool = True
    track_throughput: bool = True
    track_error_rates: bool = True

    # Alerting
    alert_on_connection_loss: bool = True
    alert_on_high_error_rate: bool = True
    error_rate_threshold_percent: float = 5.0

    # External monitoring
    prometheus_enabled: bool = False
    statsd_enabled: bool = False
    statsd_host: str = "localhost"
    statsd_port: int = 8125

    def validate(self):
        """Validate monitoring configuration."""
        if self.metrics_port <= 0 or self.metrics_port > 65535:
            raise ConfigurationError("metrics_port must be between 1 and 65535")
        if (
            self.error_rate_threshold_percent < 0
            or self.error_rate_threshold_percent > 100
        ):
            raise ConfigurationError(
                "error_rate_threshold_percent must be between 0 and 100"
            )


class ConfigHelper:
    """Helper class for standardized configuration parsing and validation."""

    def __init__(self, config_source: Optional[Dict[str, Any]] = None):
        """Initialize configuration helper.

        Args:
            config_source: Optional configuration dictionary. If None, uses global config.
        """
        self.config = config_source or get_config().to_dict()
        self._cache: Dict[str, Any] = {}

    def get_broker_config(
        self,
        broker_name: str,
        adapter_type: str,
        defaults: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Get configuration for a specific broker adapter.

        Args:
            broker_name: Name of the broker (e.g., 'ib', 'fxcm', 'fix').
            adapter_type: Type of adapter (e.g., 'trading', 'rabbitmq').
            defaults: Optional default values.

        Returns:
            Merged configuration dictionary.
        """
        cache_key = f"{broker_name}_{adapter_type}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Build configuration hierarchy
        base_config = defaults or {}

        # Global broker defaults
        global_broker_config = self.config.get("brokers", {})

        # Broker-specific config
        broker_config = global_broker_config.get(broker_name, {})

        # Adapter-specific config
        adapter_config = broker_config.get(adapter_type, {})

        # Merge in order of precedence
        merged_config = {}
        merged_config.update(base_config)
        merged_config.update(global_broker_config.get("defaults", {}))
        merged_config.update(broker_config)
        merged_config.update(adapter_config)

        # Environment variable overrides
        self._apply_env_overrides(merged_config, broker_name, adapter_type)

        self._cache[cache_key] = merged_config
        return merged_config

    def get_connection_config(
        self, broker_name: str, defaults: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Get connection configuration for a broker.

        Args:
            broker_name: Name of the broker.
            defaults: Optional default values.

        Returns:
            Connection configuration dictionary.
        """
        config = self.get_broker_config(broker_name, "connection", defaults)

        # Add common connection defaults
        connection_defaults = {
            "timeout": 30,
            "keepalive": True,
            "keepalive_interval": 60,
            "max_retries": 3,
            "retry_delay": 1.0,
        }

        for key, value in connection_defaults.items():
            if key not in config:
                config[key] = value

        return config

    def get_limits_config(self, broker_name: str) -> ConnectionLimits:
        """Get connection limits configuration.

        Args:
            broker_name: Name of the broker.

        Returns:
            ConnectionLimits configuration object.
        """
        config = self.get_broker_config(broker_name, "limits")
        return self._create_dataclass_from_config(ConnectionLimits, config)

    def get_security_config(self, broker_name: str) -> SecurityConfig:
        """Get security configuration.

        Args:
            broker_name: Name of the broker.

        Returns:
            SecurityConfig configuration object.
        """
        config = self.get_broker_config(broker_name, "security")

        # Load credentials from environment if not in config
        if (
            not config.get("username")
            and f"{broker_name.upper()}_USERNAME" in os.environ
        ):
            config["username"] = os.environ[f"{broker_name.upper()}_USERNAME"]
        if (
            not config.get("password")
            and f"{broker_name.upper()}_PASSWORD" in os.environ
        ):
            config["password"] = os.environ[f"{broker_name.upper()}_PASSWORD"]
        if not config.get("api_key") and f"{broker_name.upper()}_API_KEY" in os.environ:
            config["api_key"] = os.environ[f"{broker_name.upper()}_API_KEY"]
        if (
            not config.get("secret_key")
            and f"{broker_name.upper()}_SECRET_KEY" in os.environ
        ):
            config["secret_key"] = os.environ[f"{broker_name.upper()}_SECRET_KEY"]

        return self._create_dataclass_from_config(SecurityConfig, config)

    def get_logging_config(self, broker_name: str) -> LoggingConfig:
        """Get logging configuration.

        Args:
            broker_name: Name of the broker.

        Returns:
            LoggingConfig configuration object.
        """
        config = self.get_broker_config(broker_name, "logging")
        return self._create_dataclass_from_config(LoggingConfig, config)

    def get_monitoring_config(self, broker_name: str) -> MonitoringConfig:
        """Get monitoring configuration.

        Args:
            broker_name: Name of the broker.

        Returns:
            MonitoringConfig configuration object.
        """
        config = self.get_broker_config(broker_name, "monitoring")
        return self._create_dataclass_from_config(MonitoringConfig, config)

    def get_messaging_config(
        self, broker_name: str, defaults: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Get messaging configuration for RabbitMQ integration.

        Args:
            broker_name: Name of the broker.
            defaults: Optional default values.

        Returns:
            Messaging configuration dictionary.
        """
        config = self.get_broker_config(broker_name, "messaging", defaults)

        # Add RabbitMQ defaults
        rabbitmq_defaults = {
            "rabbitmq": {
                "host": "localhost",
                "port": 5672,
                "virtual_host": "/",
                "username": "guest",
                "password": "guest",
                "exchange_name": f"{broker_name}_exchange",
                "exchange_type": "topic",
                "exchange_durable": True,
            }
        }

        if "rabbitmq" not in config:
            config.update(rabbitmq_defaults)

        return config

    def validate_config(self, broker_name: str) -> List[str]:
        """Validate broker configuration and return any errors.

        Args:
            broker_name: Name of the broker to validate.

        Returns:
            List of validation error messages.
        """
        errors = []

        try:
            # Validate limits
            limits = self.get_limits_config(broker_name)
            limits.validate()
        except ConfigurationError as e:
            errors.append(f"Limits config error: {e}")

        try:
            # Validate security
            security = self.get_security_config(broker_name)
            security.validate()
        except ConfigurationError as e:
            errors.append(f"Security config error: {e}")

        try:
            # Validate logging
            logging_config = self.get_logging_config(broker_name)
            logging_config.validate()
        except ConfigurationError as e:
            errors.append(f"Logging config error: {e}")

        try:
            # Validate monitoring
            monitoring = self.get_monitoring_config(broker_name)
            monitoring.validate()
        except ConfigurationError as e:
            errors.append(f"Monitoring config error: {e}")

        # Validate required connection parameters
        connection_config = self.get_connection_config(broker_name)
        required_fields = ["host", "port"]

        for field in required_fields:
            if field not in connection_config or connection_config[field] is None:
                errors.append(f"Missing required connection parameter: {field}")

        return errors

    def _create_dataclass_from_config(
        self, dataclass_type: Type[T], config: Dict[str, Any]
    ) -> T:
        """Create dataclass instance from configuration dictionary.

        Args:
            dataclass_type: Type of dataclass to create.
            config: Configuration dictionary.

        Returns:
            Dataclass instance with configuration values.
        """
        # Get field names for the dataclass
        field_names = {f.name for f in fields(dataclass_type)}

        # Filter config to only include valid fields
        filtered_config = {
            key: value for key, value in config.items() if key in field_names
        }

        try:
            return dataclass_type(**filtered_config)
        except TypeError as e:
            raise ConfigurationError(f"Error creating {dataclass_type.__name__}: {e}")

    def _apply_env_overrides(
        self, config: Dict[str, Any], broker_name: str, adapter_type: str
    ):
        """Apply environment variable overrides to configuration.

        Args:
            config: Configuration dictionary to modify.
            broker_name: Name of the broker.
            adapter_type: Type of adapter.
        """
        prefix = f"{broker_name.upper()}_{adapter_type.upper()}_"

        # Common environment variable mappings
        env_mappings = {
            f"{prefix}HOST": "host",
            f"{prefix}PORT": "port",
            f"{prefix}USERNAME": "username",
            f"{prefix}PASSWORD": "password",
            f"{prefix}API_KEY": "api_key",
            f"{prefix}SECRET_KEY": "secret_key",
            f"{prefix}TIMEOUT": "timeout",
            f"{prefix}MAX_RETRIES": "max_retries",
            f"{prefix}SSL": "use_ssl",
            f"{prefix}DEBUG": "debug",
        }

        for env_var, config_key in env_mappings.items():
            if env_var in os.environ:
                value = os.environ[env_var]

                # Type conversion
                if config_key in ["port", "timeout", "max_retries"]:
                    value = int(value)
                elif config_key in ["use_ssl", "debug"]:
                    value = value.lower() in ["true", "1", "yes", "on"]

                config[config_key] = value

    def dump_config(self, broker_name: str) -> str:
        """Dump complete configuration for a broker as YAML.

        Args:
            broker_name: Name of the broker.

        Returns:
            YAML string representation of the configuration.
        """
        complete_config = {
            "connection": self.get_connection_config(broker_name),
            "limits": self.get_limits_config(broker_name).__dict__,
            "security": self.get_security_config(broker_name).__dict__,
            "logging": self.get_logging_config(broker_name).__dict__,
            "monitoring": self.get_monitoring_config(broker_name).__dict__,
            "messaging": self.get_messaging_config(broker_name),
        }

        return yaml.dump(complete_config, default_flow_style=False, indent=2)

    def clear_cache(self):
        """Clear configuration cache."""
        self._cache.clear()


# Convenience functions


def get_broker_config(
    broker_name: str,
    adapter_type: str = "trading",
    config_source: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Get configuration for a broker adapter.

    Args:
        broker_name: Name of the broker.
        adapter_type: Type of adapter.
        config_source: Optional configuration source.

    Returns:
        Configuration dictionary.
    """
    helper = ConfigHelper(config_source)
    return helper.get_broker_config(broker_name, adapter_type)


def validate_broker_config(
    broker_name: str, config_source: Optional[Dict[str, Any]] = None
) -> List[str]:
    """Validate broker configuration.

    Args:
        broker_name: Name of the broker to validate.
        config_source: Optional configuration source.

    Returns:
        List of validation error messages.
    """
    helper = ConfigHelper(config_source)
    return helper.validate_config(broker_name)


def create_config_template(broker_name: str) -> str:
    """Create a configuration template for a broker.

    Args:
        broker_name: Name of the broker.

    Returns:
        YAML configuration template.
    """
    template = {
        "brokers": {
            broker_name: {
                "connection": {
                    "host": "localhost",
                    "port": 7497,
                    "timeout": 30,
                    "keepalive": True,
                    "max_retries": 3,
                },
                "limits": {
                    "max_connections": 10,
                    "max_orders_per_second": 10,
                    "max_requests_per_minute": 600,
                    "connection_timeout_seconds": 30,
                },
                "security": {
                    "use_ssl": True,
                    "verify_ssl": True,
                    "username": "${" + f"{broker_name.upper()}_USERNAME" + "}",
                    "password": "${" + f"{broker_name.upper()}_PASSWORD" + "}",
                },
                "logging": {
                    "level": "INFO",
                    "file_path": f"/var/log/fxml4/{broker_name}_adapter.log",
                },
                "monitoring": {
                    "enabled": True,
                    "health_check_interval_seconds": 30,
                    "alert_on_connection_loss": True,
                },
                "messaging": {
                    "rabbitmq": {
                        "host": "localhost",
                        "port": 5672,
                        "username": "guest",
                        "password": "guest",
                        "exchange_name": f"{broker_name}_exchange",
                    }
                },
            }
        }
    }

    return yaml.dump(template, default_flow_style=False, indent=2)


# Global configuration helper instance
_global_helper = None


def get_global_config_helper() -> ConfigHelper:
    """Get global configuration helper instance.

    Returns:
        Global ConfigHelper instance.
    """
    global _global_helper
    if _global_helper is None:
        _global_helper = ConfigHelper()
    return _global_helper


def reset_global_config_helper():
    """Reset global configuration helper instance."""
    global _global_helper
    _global_helper = None
