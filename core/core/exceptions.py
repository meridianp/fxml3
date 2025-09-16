"""Core exceptions for FXML4.

This module defines the base exception hierarchy used throughout
the FXML4 trading system.
"""


class FXMLError(Exception):
    """Base exception for all FXML4 errors.

    This is the root exception class that all other FXML4-specific
    exceptions should inherit from.
    """

    def __init__(self, message: str, error_code: str = None, details: dict = None):
        """Initialize FXML error.

        Args:
            message: Human-readable error message
            error_code: Optional error code for categorization
            details: Optional dictionary with additional error details
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}

    def __str__(self) -> str:
        """Return string representation of the error."""
        if self.error_code:
            return f"[{self.error_code}] {self.message}"
        return self.message


class ConfigurationError(FXMLError):
    """Exception raised when configuration is invalid or missing."""

    def __init__(self, message: str, config_key: str = None, details: dict = None):
        """Initialize configuration error.

        Args:
            message: Error message
            config_key: The configuration key that caused the error
            details: Additional error details
        """
        super().__init__(message, "CONFIG_ERROR", details)
        self.config_key = config_key


class ValidationError(FXMLError):
    """Exception raised when data validation fails."""

    def __init__(
        self, message: str, field_name: str = None, value=None, details: dict = None
    ):
        """Initialize validation error.

        Args:
            message: Error message
            field_name: Name of the field that failed validation
            value: The value that failed validation
            details: Additional error details
        """
        super().__init__(message, "VALIDATION_ERROR", details)
        self.field_name = field_name
        self.value = value


class ConnectionError(FXMLError):
    """Exception raised when connection operations fail."""

    def __init__(self, message: str, connection_type: str = None, details: dict = None):
        """Initialize connection error.

        Args:
            message: Error message
            connection_type: Type of connection (database, broker, etc.)
            details: Additional error details
        """
        super().__init__(message, "CONNECTION_ERROR", details)
        self.connection_type = connection_type


class AuthenticationError(FXMLError):
    """Exception raised when authentication fails."""

    def __init__(self, message: str, user_id: str = None, details: dict = None):
        """Initialize authentication error.

        Args:
            message: Error message
            user_id: User identifier that failed authentication
            details: Additional error details
        """
        super().__init__(message, "AUTH_ERROR", details)
        self.user_id = user_id


class AuthorizationError(FXMLError):
    """Exception raised when authorization fails."""

    def __init__(
        self,
        message: str,
        user_id: str = None,
        resource: str = None,
        details: dict = None,
    ):
        """Initialize authorization error.

        Args:
            message: Error message
            user_id: User identifier
            resource: Resource that was accessed
            details: Additional error details
        """
        super().__init__(message, "AUTHZ_ERROR", details)
        self.user_id = user_id
        self.resource = resource


class TokenError(FXMLError):
    """Exception raised when JWT token operations fail."""

    def __init__(
        self,
        message: str,
        token_type: str = None,
        user_id: str = None,
        details: dict = None,
    ):
        """Initialize token error.

        Args:
            message: Error message
            token_type: Type of token (access, refresh)
            user_id: User identifier associated with the token
            details: Additional error details
        """
        super().__init__(message, "TOKEN_ERROR", details)
        self.token_type = token_type
        self.user_id = user_id


class BrokerError(FXMLError):
    """Exception raised when broker operations fail."""

    def __init__(
        self,
        message: str,
        broker_name: str = None,
        operation: str = None,
        details: dict = None,
    ):
        """Initialize broker error.

        Args:
            message: Error message
            broker_name: Name of the broker
            operation: Operation that failed
            details: Additional error details
        """
        super().__init__(message, "BROKER_ERROR", details)
        self.broker_name = broker_name
        self.operation = operation


class TradingError(FXMLError):
    """Exception raised when trading operations fail."""

    def __init__(
        self,
        message: str,
        symbol: str = None,
        order_id: str = None,
        details: dict = None,
    ):
        """Initialize trading error.

        Args:
            message: Error message
            symbol: Trading symbol
            order_id: Order identifier
            details: Additional error details
        """
        super().__init__(message, "TRADING_ERROR", details)
        self.symbol = symbol
        self.order_id = order_id


class RiskError(FXMLError):
    """Exception raised when risk management rules are violated."""

    def __init__(
        self,
        message: str,
        risk_type: str = None,
        limit_value=None,
        details: dict = None,
    ):
        """Initialize risk error.

        Args:
            message: Error message
            risk_type: Type of risk violation
            limit_value: The risk limit that was exceeded
            details: Additional error details
        """
        super().__init__(message, "RISK_ERROR", details)
        self.risk_type = risk_type
        self.limit_value = limit_value


class DataError(FXMLError):
    """Exception raised when data operations fail."""

    def __init__(
        self,
        message: str,
        data_source: str = None,
        symbol: str = None,
        details: dict = None,
    ):
        """Initialize data error.

        Args:
            message: Error message
            data_source: Source of the data
            symbol: Trading symbol
            details: Additional error details
        """
        super().__init__(message, "DATA_ERROR", details)
        self.data_source = data_source
        self.symbol = symbol


class ModelError(FXMLError):
    """Exception raised when ML model operations fail."""

    def __init__(
        self,
        message: str,
        model_name: str = None,
        operation: str = None,
        details: dict = None,
    ):
        """Initialize model error.

        Args:
            message: Error message
            model_name: Name of the model
            operation: Operation that failed (training, prediction, etc.)
            details: Additional error details
        """
        super().__init__(message, "MODEL_ERROR", details)
        self.model_name = model_name
        self.operation = operation


class TimeoutError(FXMLError):
    """Exception raised when operations timeout."""

    def __init__(
        self,
        message: str,
        timeout_duration: float = None,
        operation: str = None,
        details: dict = None,
    ):
        """Initialize timeout error.

        Args:
            message: Error message
            timeout_duration: Duration that was exceeded
            operation: Operation that timed out
            details: Additional error details
        """
        super().__init__(message, "TIMEOUT_ERROR", details)
        self.timeout_duration = timeout_duration
        self.operation = operation


class ComplianceError(FXMLError):
    """Exception raised when regulatory compliance operations fail."""

    def __init__(
        self,
        message: str,
        regulation: str = None,
        violation_type: str = None,
        details: dict = None,
    ):
        """Initialize compliance error.

        Args:
            message: Error message
            regulation: Regulatory framework (MiFID II, SOX, PCI-DSS, etc.)
            violation_type: Type of compliance violation
            details: Additional error details
        """
        super().__init__(message, "COMPLIANCE_ERROR", details)
        self.regulation = regulation
        self.violation_type = violation_type


class MonitoringError(FXMLError):
    """Exception raised when monitoring operations fail."""

    def __init__(
        self,
        message: str,
        component: str = None,
        metric: str = None,
        details: dict = None,
    ):
        """Initialize monitoring error.

        Args:
            message: Error message
            component: Component being monitored
            metric: Metric that failed
            details: Additional error details
        """
        super().__init__(message, "MONITORING_ERROR", details)
        self.component = component
        self.metric = metric
