"""
Core exceptions for FXML4 system.

Defines custom exception classes for various error conditions
throughout the trading system.
"""


class FXML4Exception(Exception):
    """Base exception for all FXML4 errors."""

    pass


class AuthenticationError(FXML4Exception):
    """Raised when authentication fails."""

    pass


class TokenExpiredError(AuthenticationError):
    """Raised when a JWT token has expired."""

    pass


class InvalidTokenError(AuthenticationError):
    """Raised when a JWT token is invalid or corrupted."""

    pass


class RateLimitError(AuthenticationError):
    """Raised when rate limits are exceeded."""

    pass


class TradingError(FXML4Exception):
    """Base class for trading-related errors."""

    pass


class OrderError(TradingError):
    """Raised when order operations fail."""

    pass


class BrokerError(TradingError):
    """Raised when broker operations fail."""

    pass


class RiskManagementError(TradingError):
    """Raised when risk management checks fail."""

    pass


class RiskError(TradingError):
    """Raised when risk validation fails."""

    pass


class ExecutionError(TradingError):
    """Raised when trade execution fails."""

    pass


class EmergencyShutdownError(TradingError):
    """Raised during emergency shutdown procedures."""

    pass


class DataError(FXML4Exception):
    """Raised when data operations fail."""

    pass


class ConfigurationError(FXML4Exception):
    """Raised when configuration is invalid."""

    pass
