"""Configuration management using Pydantic."""

from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class BaseConfig(BaseSettings):
    """
    Base configuration class using Pydantic BaseSettings.
    
    This provides a foundation for configuration management
    with environment variable support and validation.
    """
    
    # Application settings
    app_name: str = Field(default="fxml4", description="Application name")
    environment: str = Field(default="development", description="Environment (development, staging, production)")
    debug: bool = Field(default=False, description="Debug mode")
    
    # Logging
    log_level: str = Field(default="INFO", description="Logging level")
    log_format: str = Field(default="json", description="Log format (json, text)")
    
    # API settings
    api_host: str = Field(default="0.0.0.0", description="API host")
    api_port: int = Field(default=8000, description="API port")
    
    # Database
    database_url: Optional[str] = Field(default=None, description="Database connection URL")
    
    class Config:
        """Pydantic config."""
        env_prefix = "FXML4_"
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False