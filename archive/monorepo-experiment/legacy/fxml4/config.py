"""Configuration module for FXML4.

This module handles loading and accessing configuration settings from YAML files
and environment variables.
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional, Union

import yaml
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Configuration manager for FXML4.
    
    Handles loading configuration from YAML files and environment variables.
    Provides access to configuration settings through a unified interface.
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize configuration manager.
        
        Args:
            config_path: Path to the configuration file. If None, uses default path.
        """
        self._config: Dict[str, Any] = {}
        
        # Default config path is <project_root>/config/default.yaml
        if config_path is None:
            root_dir = Path(__file__).parent.parent
            config_path = os.path.join(root_dir, "config", "default.yaml")
        
        self.load_config(config_path)
    
    def load_config(self, config_path: str) -> None:
        """Load configuration from a YAML file.
        
        Args:
            config_path: Path to the configuration file.
        
        Raises:
            FileNotFoundError: If the configuration file is not found.
            yaml.YAMLError: If the configuration file is not valid YAML.
        """
        try:
            with open(config_path, "r") as file:
                self._config = yaml.safe_load(file)
        except FileNotFoundError:
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        except yaml.YAMLError as e:
            raise yaml.YAMLError(f"Error parsing configuration file: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value.
        
        Supports nested keys with dot notation, e.g., "data.base_path".
        Environment variables take precedence over configuration file values.
        
        Args:
            key: Configuration key to retrieve.
            default: Default value to return if key is not found.
            
        Returns:
            The configuration value or default if not found.
        """
        # Check if there's an environment variable with the key
        env_key = f"FXML4_{key.upper().replace('.', '_')}"
        env_value = os.environ.get(env_key)
        if env_value is not None:
            return env_value
        
        # Navigate through nested dictionary using dot notation
        value = self._config
        for part in key.split("."):
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return default
        
        return value
    
    def get_all(self) -> Dict[str, Any]:
        """Get the entire configuration dictionary.
        
        Returns:
            A copy of the configuration dictionary.
        """
        return self._config.copy()


# Global configuration instance
config = Config()


def get_config(key: str, default: Any = None) -> Any:
    """Get a configuration value from the global configuration instance.
    
    Args:
        key: Configuration key to retrieve.
        default: Default value to return if key is not found.
        
    Returns:
        The configuration value or default if not found.
    """
    return config.get(key, default)


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """Load and return the full configuration.
    
    Args:
        config_path: Optional path to a specific config file
        
    Returns:
        The full configuration dictionary
    """
    if config_path:
        custom_config = Config(config_path)
        return custom_config.get_all()
    return config.get_all()


def get_data_feed_config(feed_name: str) -> Dict[str, Any]:
    """Get configuration for a specific data feed.
    
    Args:
        feed_name: Name of the data feed (e.g., "ib", "yahoo")
        
    Returns:
        Configuration dictionary for the data feed
    """
    feeds_config = config.get("data.data_feeds", {})
    return feeds_config.get(feed_name, {})