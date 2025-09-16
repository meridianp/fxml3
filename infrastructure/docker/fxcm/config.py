"""Configuration for FXCM Bridge Service."""

import os
from typing import Optional


class BridgeConfig:
    """Configuration for FXCM bridge service."""

    # Bridge service settings
    HOST: str = os.getenv("BRIDGE_HOST", "0.0.0.0")
    PORT: int = int(os.getenv("BRIDGE_PORT", "9090"))

    # FXCM connection settings
    FXCM_URL: str = os.getenv("FXCM_URL", "www.fxcorporate.com/Hosts.jsp")
    FXCM_USERNAME: str = os.getenv("FXCM_USERNAME", "")
    FXCM_PASSWORD: str = os.getenv("FXCM_PASSWORD", "")
    FXCM_CONNECTION: str = os.getenv("FXCM_CONNECTION", "Demo")  # Demo or Real
    FXCM_ACCOUNT_ID: Optional[str] = os.getenv("FXCM_ACCOUNT_ID")

    # Connection settings
    RECONNECT_ATTEMPTS: int = int(os.getenv("RECONNECT_ATTEMPTS", "5"))
    RECONNECT_DELAY: int = int(os.getenv("RECONNECT_DELAY", "10"))
    HEARTBEAT_INTERVAL: int = int(os.getenv("HEARTBEAT_INTERVAL", "30"))

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT: str = os.getenv("LOG_FORMAT", "json")  # json or text

    # Performance
    MAX_CONCURRENT_ORDERS: int = int(os.getenv("MAX_CONCURRENT_ORDERS", "100"))
    ORDER_TIMEOUT: int = int(os.getenv("ORDER_TIMEOUT", "60"))

    # Security
    API_KEY: Optional[str] = os.getenv("BRIDGE_API_KEY")  # Optional API key for bridge

    @classmethod
    def validate(cls) -> None:
        """Validate required configuration."""
        if not cls.FXCM_USERNAME:
            raise ValueError("FXCM_USERNAME environment variable is required")
        if not cls.FXCM_PASSWORD:
            raise ValueError("FXCM_PASSWORD environment variable is required")

        if cls.FXCM_CONNECTION not in ["Demo", "Real"]:
            raise ValueError("FXCM_CONNECTION must be 'Demo' or 'Real'")

        # Check if ForexConnect API is available
        forexconnect_root = os.getenv("FOREXCONNECT_ROOT", "/app/ForexConnectAPI")
        if not os.path.exists(forexconnect_root):
            raise ValueError(f"ForexConnect API not found at {forexconnect_root}")


# Validate configuration on import
try:
    BridgeConfig.validate()
except ValueError as e:
    # Log warning but don't fail import
    import logging

    logging.warning(f"Configuration validation warning: {e}")
