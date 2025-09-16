"""
Unified API Schemas for FXML4.

This module consolidates all Pydantic models used for request/response validation,
filtering, pagination, and error handling in the FXML4 API.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Generic, List, Optional, TypeVar, Union
from uuid import UUID

from pydantic import BaseModel, Field, root_validator, validator
from pydantic.generics import GenericModel
from pydantic.types import confloat, conint

# =============================================================================
# ENUMS
# =============================================================================


class TimeframeEnum(str, Enum):
    """Supported timeframes with extended options."""

    ONE_MINUTE = "1m"
    THREE_MINUTES = "3m"
    FIVE_MINUTES = "5m"
    FIFTEEN_MINUTES = "15m"
    THIRTY_MINUTES = "30m"
    ONE_HOUR = "1h"
    TWO_HOURS = "2h"
    FOUR_HOURS = "4h"
    SIX_HOURS = "6h"
    TWELVE_HOURS = "12h"
    ONE_DAY = "1d"
    ONE_WEEK = "1w"
    ONE_MONTH = "1M"


class StrategyEnum(str, Enum):
    """Supported strategy types."""

    INTEGRATED = "integrated_strategy"
    ML = "ml_strategy"
    WAVE = "wave_strategy"
    SENTIMENT = "sentiment_strategy"
    HYBRID = "hybrid_strategy"
    CUSTOM = "custom_strategy"
    ENSEMBLE = "ensemble_strategy"


class SignalTypeEnum(str, Enum):
    """Extended signal types."""

    ENTRY_LONG = "entry_long"
    ENTRY_SHORT = "entry_short"
    EXIT_LONG = "exit_long"
    EXIT_SHORT = "exit_short"
    SCALE_IN = "scale_in"
    SCALE_OUT = "scale_out"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"
    TRAILING_STOP = "trailing_stop"


class OrderSideEnum(str, Enum):
    """Order side types."""

    BUY = "buy"
    SELL = "sell"


class DataSourceEnum(str, Enum):
    """Data source options."""

    ALPHA_VANTAGE = "alpha_vantage"
    INTERACTIVE_BROKERS = "interactive_brokers"
    POLYGON = "polygon"
    YAHOO = "yahoo"
    BINANCE = "binance"
    CUSTOM = "custom"


# =============================================================================
# AUTHENTICATION MODELS
# =============================================================================


class Token(BaseModel):
    """JWT token response model."""

    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")

    class Config:
        schema_extra = {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
            }
        }


class User(BaseModel):
    """User response model."""

    username: str = Field(..., description="Username")
    email: Optional[str] = Field(None, description="Email address")
    full_name: Optional[str] = Field(None, description="Full name")
    is_active: bool = Field(True, description="Whether user is active")
    scopes: List[str] = Field(default_factory=list, description="User permissions")

    class Config:
        schema_extra = {
            "example": {
                "username": "admin",
                "email": "admin@fxml4.com",
                "full_name": "FXML4 Admin",
                "is_active": True,
                "scopes": ["read", "write", "admin"],
            }
        }


# =============================================================================
# CORE API MODELS
# =============================================================================


class DataRequest(BaseModel):
    """Enhanced data request model with validation."""

    symbol: str = Field(
        ...,
        description="Trading symbol (e.g., 'EURUSD', 'GBPUSD', 'BTCUSD')",
        example="EURUSD",
        regex="^[A-Z]{3,10}$",
    )
    timeframe: TimeframeEnum = Field(
        ..., description="Timeframe for the data", example=TimeframeEnum.ONE_HOUR
    )
    start_date: Optional[datetime] = Field(
        None, description="Start date in ISO format", example="2023-01-01T00:00:00Z"
    )
    end_date: Optional[datetime] = Field(
        None, description="End date in ISO format", example="2023-12-31T23:59:59Z"
    )
    limit: Optional[conint(ge=1, le=10000)] = Field(
        None,
        description="Maximum number of data points to return (1-10000)",
        example=1000,
    )
    source: Optional[DataSourceEnum] = Field(
        None, description="Data source preference", example=DataSourceEnum.ALPHA_VANTAGE
    )

    @validator("end_date")
    def validate_date_range(cls, v, values):
        """Ensure end_date is after start_date if both provided."""
        if v and "start_date" in values and values["start_date"]:
            if v < values["start_date"]:
                raise ValueError("end_date must be after or equal to start_date")
        return v

    class Config:
        schema_extra = {
            "example": {
                "symbol": "EURUSD",
                "timeframe": "1h",
                "start_date": "2023-01-01T00:00:00Z",
                "end_date": "2023-12-31T23:59:59Z",
                "limit": 1000,
                "source": "alpha_vantage",
            }
        }


class SignalRequest(BaseModel):
    """Enhanced signal generation request model."""

    symbol: str = Field(
        ...,
        description="Trading symbol (e.g., 'EURUSD', 'GBPUSD')",
        example="EURUSD",
        regex="^[A-Z]{3,10}$",
    )
    timeframe: TimeframeEnum = Field(
        ..., description="Timeframe for the data", example=TimeframeEnum.ONE_HOUR
    )
    strategy: StrategyEnum = Field(
        ...,
        description="Strategy to use for signal generation",
        example=StrategyEnum.ML,
    )
    parameters: Optional[Dict[str, Any]] = Field(
        None, description="Strategy parameters"
    )
    confidence_threshold: Optional[confloat(ge=0.0, le=1.0)] = Field(
        0.5, description="Minimum confidence threshold for signals", example=0.7
    )

    class Config:
        schema_extra = {
            "example": {
                "symbol": "EURUSD",
                "timeframe": "1h",
                "strategy": "ml_strategy",
                "parameters": {"lookback_period": 20, "model_type": "lstm"},
                "confidence_threshold": 0.7,
            }
        }


class Signal(BaseModel):
    """Enhanced signal model."""

    signal_id: Optional[str] = Field(None, description="Unique signal identifier")
    symbol: str = Field(..., description="Trading symbol")
    timestamp: datetime = Field(..., description="Signal timestamp")
    signal_type: SignalTypeEnum = Field(..., description="Signal type")
    confidence: confloat(ge=0.0, le=1.0) = Field(
        ..., description="Signal confidence (0.0-1.0)"
    )
    strength: Optional[confloat(ge=0.0, le=1.0)] = Field(
        None, description="Signal strength (0.0-1.0)"
    )
    price: float = Field(..., description="Price at signal generation")
    target_price: Optional[float] = Field(
        None, description="Target price for the signal"
    )
    stop_loss: Optional[float] = Field(None, description="Stop loss price")
    description: Optional[str] = Field(None, description="Signal description")
    strategy: Optional[str] = Field(
        None, description="Strategy that generated the signal"
    )
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")

    class Config:
        schema_extra = {
            "example": {
                "signal_id": "sig_123456",
                "symbol": "EURUSD",
                "timestamp": "2023-06-15T14:30:00Z",
                "signal_type": "entry_long",
                "confidence": 0.85,
                "strength": 0.75,
                "price": 1.0950,
                "target_price": 1.1050,
                "stop_loss": 1.0850,
                "description": "Strong bullish signal based on technical analysis",
                "strategy": "ml_strategy",
                "metadata": {"indicators": ["RSI", "MACD"], "timeframe": "1h"},
            }
        }


class SignalResponse(BaseModel):
    """Enhanced signal generation response model."""

    symbol: str = Field(..., description="Trading symbol")
    timeframe: str = Field(..., description="Timeframe used")
    strategy: str = Field(..., description="Strategy used")
    signals: List[Signal] = Field(..., description="Generated signals")
    total_signals: int = Field(..., description="Total number of signals")
    processing_time_ms: Optional[float] = Field(
        None, description="Processing time in milliseconds"
    )

    class Config:
        schema_extra = {
            "example": {
                "symbol": "EURUSD",
                "timeframe": "1h",
                "strategy": "ml_strategy",
                "signals": [],
                "total_signals": 1,
                "processing_time_ms": 125.5,
            }
        }


class BacktestRequest(BaseModel):
    """Backtesting request model."""

    symbol: str = Field(..., description="Trading symbol (e.g., 'EURUSD', 'GBPUSD')")
    timeframe: TimeframeEnum = Field(..., description="Timeframe for the data")
    strategy: StrategyEnum = Field(..., description="Strategy to use for backtesting")
    start_date: str = Field(
        ..., description="Start date in ISO format (e.g., '2023-01-01')"
    )
    end_date: str = Field(
        ..., description="End date in ISO format (e.g., '2023-12-31')"
    )
    initial_capital: float = Field(
        10000.0, description="Initial capital for backtesting"
    )
    commission: float = Field(0.0002, description="Commission per trade")
    slippage: float = Field(0.0001, description="Slippage per trade")
    max_position_size: float = Field(
        0.1, description="Maximum position size as fraction of capital"
    )
    stop_loss_pct: Optional[float] = Field(None, description="Stop loss percentage")
    take_profit_pct: Optional[float] = Field(None, description="Take profit percentage")
    strategy_params: Optional[Dict[str, Any]] = Field(
        None, description="Strategy parameters"
    )
    auto_report: bool = Field(
        True, description="Automatically generate a performance report"
    )


class TradeInfo(BaseModel):
    """Trade information model."""

    position_id: str = Field(..., description="Position ID")
    symbol: str = Field(..., description="Trading symbol")
    side: OrderSideEnum = Field(..., description="Trade side (buy/sell)")
    entry_price: float = Field(..., description="Entry price")
    entry_time: Union[str, datetime] = Field(..., description="Entry timestamp")
    quantity: float = Field(..., description="Position size")
    exit_price: Optional[float] = Field(None, description="Exit price")
    exit_time: Optional[Union[str, datetime]] = Field(
        None, description="Exit timestamp"
    )
    pnl: Optional[float] = Field(None, description="Profit/Loss in account currency")
    pnl_pct: Optional[float] = Field(None, description="Profit/Loss in percentage")
    status: str = Field(..., description="Position status (open/closed)")
    reason: Optional[str] = Field(None, description="Entry/exit reason")


class BacktestResponse(BaseModel):
    """Backtesting response model."""

    backtest_id: str = Field(..., description="Unique backtest ID")
    symbol: str = Field(..., description="Trading symbol")
    timeframe: str = Field(..., description="Timeframe used")
    strategy: str = Field(..., description="Strategy used")
    start_date: str = Field(..., description="Start date")
    end_date: str = Field(..., description="End date")
    initial_capital: float = Field(..., description="Initial capital")
    final_capital: float = Field(..., description="Final capital")
    total_return: float = Field(..., description="Total return in account currency")
    sharpe_ratio: float = Field(..., description="Sharpe ratio")
    max_drawdown: float = Field(..., description="Maximum drawdown in account currency")
    num_trades: int = Field(..., description="Number of trades")
    win_rate: float = Field(..., description="Win rate")
    avg_trade_return: float = Field(..., description="Average trade return")
    status: str = Field(..., description="Backtest status")
    created_at: str = Field(..., description="Creation timestamp")
    duration: str = Field(..., description="Backtest duration")


class PerformanceMetricsRequest(BaseModel):
    """Performance metrics request model."""

    backtest_id: str = Field(..., description="ID of the backtest to analyze")
    include_trades: bool = Field(False, description="Whether to include trade details")
    include_equity_curve: bool = Field(
        False, description="Whether to include the equity curve"
    )


class PerformanceReportRequest(BaseModel):
    """Performance report request model."""

    backtest_id: str = Field(
        ..., description="ID of the backtest to generate a report for"
    )
    include_figures: bool = Field(
        True, description="Whether to include figures in the report"
    )
    export_pdf: bool = Field(False, description="Whether to export the report as PDF")


class ComparativeAnalysisRequest(BaseModel):
    """Comparative analysis request model."""

    backtest_ids: List[str] = Field(..., description="List of backtest IDs to compare")
    metrics: List[str] = Field(
        ["total_return_pct", "max_drawdown_pct", "sharpe_ratio"],
        description="Metrics to compare",
    )


# =============================================================================
# FILTER MODELS
# =============================================================================


class DateRangeFilter(BaseModel):
    """Date range filter."""

    start_date: Optional[datetime] = Field(
        None, description="Start date (inclusive)", example="2023-01-01T00:00:00Z"
    )
    end_date: Optional[datetime] = Field(
        None, description="End date (inclusive)", example="2023-12-31T23:59:59Z"
    )

    @validator("end_date")
    def validate_date_range(cls, v, values):
        """Ensure end_date is after start_date if both provided."""
        if v and "start_date" in values and values["start_date"]:
            if v < values["start_date"]:
                raise ValueError("end_date must be after or equal to start_date")
        return v


class DataFilter(BaseModel):
    """Filter for data queries."""

    symbols: Optional[List[str]] = Field(
        None, description="Filter by symbols", example=["EURUSD", "GBPUSD"]
    )
    timeframes: Optional[List[str]] = Field(
        None, description="Filter by timeframes", example=["1h", "4h"]
    )
    sources: Optional[List[str]] = Field(
        None, description="Filter by data sources", example=["alpha_vantage", "polygon"]
    )
    date_range: Optional[DateRangeFilter] = Field(
        None, description="Filter by date range"
    )
    quality_score_min: Optional[confloat(ge=0.0, le=1.0)] = Field(
        None, description="Minimum data quality score", example=0.8
    )

    class Config:
        schema_extra = {
            "example": {
                "symbols": ["EURUSD", "GBPUSD"],
                "timeframes": ["1h"],
                "date_range": {
                    "start_date": "2023-01-01T00:00:00Z",
                    "end_date": "2023-12-31T23:59:59Z",
                },
                "quality_score_min": 0.8,
            }
        }


class SignalFilter(BaseModel):
    """Filter for signal queries."""

    symbols: Optional[List[str]] = Field(
        None, description="Filter by symbols", example=["EURUSD"]
    )
    signal_types: Optional[List[str]] = Field(
        None, description="Filter by signal types", example=["entry_long", "exit_long"]
    )
    strategies: Optional[List[str]] = Field(
        None,
        description="Filter by strategies",
        example=["ml_strategy", "wave_strategy"],
    )
    confidence_min: Optional[confloat(ge=0.0, le=1.0)] = Field(
        None, description="Minimum confidence score", example=0.7
    )
    strength_min: Optional[confloat(ge=0.0, le=1.0)] = Field(
        None, description="Minimum signal strength", example=0.6
    )
    date_range: Optional[DateRangeFilter] = Field(
        None, description="Filter by date range"
    )
    active_only: Optional[bool] = Field(
        False, description="Show only active signals", example=True
    )

    class Config:
        schema_extra = {
            "example": {
                "symbols": ["EURUSD"],
                "signal_types": ["entry_long"],
                "strategies": ["ml_strategy"],
                "confidence_min": 0.7,
                "active_only": True,
            }
        }


class BacktestFilter(BaseModel):
    """Filter for backtest queries."""

    symbols: Optional[List[str]] = Field(
        None, description="Filter by symbols", example=["EURUSD"]
    )
    strategies: Optional[List[str]] = Field(
        None, description="Filter by strategies", example=["ml_strategy"]
    )
    date_range: Optional[DateRangeFilter] = Field(
        None, description="Filter by backtest creation date"
    )
    min_return: Optional[float] = Field(
        None, description="Minimum total return percentage", example=10.0
    )
    max_drawdown: Optional[float] = Field(
        None, description="Maximum drawdown percentage", example=20.0
    )
    min_sharpe: Optional[float] = Field(
        None, description="Minimum Sharpe ratio", example=1.0
    )
    status: Optional[List[str]] = Field(
        None, description="Filter by status", example=["completed", "running"]
    )
    tags: Optional[List[str]] = Field(
        None, description="Filter by tags", example=["production", "experimental"]
    )

    class Config:
        schema_extra = {
            "example": {
                "symbols": ["EURUSD"],
                "strategies": ["ml_strategy"],
                "min_return": 10.0,
                "max_drawdown": 20.0,
                "min_sharpe": 1.0,
                "status": ["completed"],
            }
        }


# =============================================================================
# PAGINATION MODELS
# =============================================================================

T = TypeVar("T")


class PaginationParams(BaseModel):
    """Pagination parameters for requests."""

    page: int = Field(1, ge=1, description="Page number (1-based)", example=1)
    page_size: int = Field(
        20, ge=1, le=100, description="Number of items per page (1-100)", example=20
    )
    sort_by: Optional[str] = Field(
        None, description="Field to sort by", example="timestamp"
    )
    sort_order: Optional[str] = Field(
        "desc",
        regex="^(asc|desc)$",
        description="Sort order (asc/desc)",
        example="desc",
    )

    @property
    def offset(self) -> int:
        """Calculate offset for database queries."""
        return (self.page - 1) * self.page_size

    class Config:
        schema_extra = {
            "example": {
                "page": 1,
                "page_size": 20,
                "sort_by": "timestamp",
                "sort_order": "desc",
            }
        }


class PaginationMeta(BaseModel):
    """Metadata for paginated responses."""

    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Items per page")
    total_items: int = Field(..., description="Total number of items")
    total_pages: int = Field(..., description="Total number of pages")
    has_next: bool = Field(..., description="Whether there is a next page")
    has_previous: bool = Field(..., description="Whether there is a previous page")

    class Config:
        schema_extra = {
            "example": {
                "page": 1,
                "page_size": 20,
                "total_items": 150,
                "total_pages": 8,
                "has_next": True,
                "has_previous": False,
            }
        }


class PaginatedResponse(GenericModel, Generic[T]):
    """Generic paginated response model."""

    items: List[T] = Field(..., description="List of items")
    meta: PaginationMeta = Field(..., description="Pagination metadata")

    class Config:
        schema_extra = {
            "example": {
                "items": [],
                "meta": {
                    "page": 1,
                    "page_size": 20,
                    "total_items": 150,
                    "total_pages": 8,
                    "has_next": True,
                    "has_previous": False,
                },
            }
        }


# =============================================================================
# RESPONSE MODELS
# =============================================================================


class ApiResponse(BaseModel):
    """Base API response model."""

    success: bool = Field(..., description="Whether the request was successful")
    message: str = Field(..., description="Response message")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Response timestamp"
    )
    request_id: Optional[str] = Field(
        None, description="Unique request identifier for tracing"
    )

    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "message": "Request processed successfully",
                "timestamp": "2023-06-15T14:30:00Z",
                "request_id": "req_123456",
            }
        }


class ErrorDetail(BaseModel):
    """Error detail model."""

    field: Optional[str] = Field(None, description="Field with error")
    message: str = Field(..., description="Error message")
    code: Optional[str] = Field(None, description="Error code")

    class Config:
        schema_extra = {
            "example": {
                "field": "symbol",
                "message": "Invalid symbol format",
                "code": "INVALID_FORMAT",
            }
        }


class ErrorResponse(ApiResponse):
    """Error response model."""

    success: bool = Field(False, description="Always false for errors")
    error: str = Field(..., description="Error type")
    details: Optional[List[ErrorDetail]] = Field(
        None, description="Detailed error information"
    )
    help_url: Optional[str] = Field(
        None, description="URL to documentation for this error"
    )

    class Config:
        schema_extra = {
            "example": {
                "success": False,
                "message": "Validation error",
                "timestamp": "2023-06-15T14:30:00Z",
                "request_id": "req_123456",
                "error": "ValidationError",
                "details": [
                    {
                        "field": "symbol",
                        "message": "Invalid symbol format",
                        "code": "INVALID_FORMAT",
                    }
                ],
                "help_url": "https://api.fxml4.com/docs/errors#validation",
            }
        }


class SuccessResponse(ApiResponse):
    """Success response model with data."""

    success: bool = Field(True, description="Always true for success")
    data: Optional[Any] = Field(None, description="Response data")

    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "message": "Data retrieved successfully",
                "timestamp": "2023-06-15T14:30:00Z",
                "request_id": "req_123456",
                "data": {},
            }
        }


class BatchResponse(ApiResponse):
    """Batch operation response."""

    total: int = Field(..., description="Total number of operations")
    successful: int = Field(..., description="Number of successful operations")
    failed: int = Field(..., description="Number of failed operations")
    results: List[Dict[str, Any]] = Field(
        ..., description="Individual operation results"
    )

    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "message": "Batch operation completed",
                "timestamp": "2023-06-15T14:30:00Z",
                "total": 10,
                "successful": 8,
                "failed": 2,
                "results": [
                    {"id": "1", "status": "success"},
                    {"id": "2", "status": "failed", "error": "Invalid data"},
                ],
            }
        }


class WebSocketMessage(BaseModel):
    """WebSocket message format."""

    type: str = Field(..., description="Message type")
    channel: str = Field(..., description="Channel name")
    data: Any = Field(..., description="Message data")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Message timestamp"
    )
    sequence: Optional[int] = Field(None, description="Message sequence number")

    class Config:
        schema_extra = {
            "example": {
                "type": "signal",
                "channel": "signals.EURUSD",
                "data": {"signal_type": "entry_long", "confidence": 0.85},
                "timestamp": "2023-06-15T14:30:00Z",
                "sequence": 12345,
            }
        }


class RateLimitInfo(BaseModel):
    """Rate limit information."""

    limit: int = Field(..., description="Request limit")
    remaining: int = Field(..., description="Remaining requests")
    reset: datetime = Field(..., description="Reset timestamp")
    retry_after: Optional[int] = Field(None, description="Seconds to wait before retry")

    class Config:
        schema_extra = {
            "example": {
                "limit": 100,
                "remaining": 75,
                "reset": "2023-06-15T15:00:00Z",
                "retry_after": None,
            }
        }


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================


def create_pagination_meta(
    page: int, page_size: int, total_items: int
) -> PaginationMeta:
    """Create pagination metadata.

    Args:
        page: Current page number
        page_size: Items per page
        total_items: Total number of items

    Returns:
        PaginationMeta object
    """
    total_pages = (total_items + page_size - 1) // page_size

    return PaginationMeta(
        page=page,
        page_size=page_size,
        total_items=total_items,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_previous=page > 1,
    )


def create_success_response(
    message: str, data: Optional[Any] = None, request_id: Optional[str] = None
) -> SuccessResponse:
    """Create a success response.

    Args:
        message: Success message
        data: Response data
        request_id: Request identifier

    Returns:
        SuccessResponse object
    """
    return SuccessResponse(
        success=True, message=message, data=data, request_id=request_id
    )


def create_error_response(
    error: str,
    message: str,
    details: Optional[List[ErrorDetail]] = None,
    help_url: Optional[str] = None,
    request_id: Optional[str] = None,
) -> ErrorResponse:
    """Create an error response.

    Args:
        error: Error type
        message: Error message
        details: Error details
        help_url: Help URL
        request_id: Request identifier

    Returns:
        ErrorResponse object
    """
    return ErrorResponse(
        success=False,
        error=error,
        message=message,
        details=details,
        help_url=help_url,
        request_id=request_id,
    )


# =============================================================================
# LEGACY COMPATIBILITY
# =============================================================================

# Legacy model aliases for backward compatibility
DataRequestV2 = DataRequest
SignalRequestV2 = SignalRequest
SignalV2 = Signal
SignalResponseV2 = SignalResponse


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Enums
    "TimeframeEnum",
    "StrategyEnum",
    "SignalTypeEnum",
    "OrderSideEnum",
    "DataSourceEnum",
    # Authentication
    "Token",
    "User",
    # Core Models
    "DataRequest",
    "SignalRequest",
    "Signal",
    "SignalResponse",
    "BacktestRequest",
    "BacktestResponse",
    "TradeInfo",
    "PerformanceMetricsRequest",
    "PerformanceReportRequest",
    "ComparativeAnalysisRequest",
    # Filter Models
    "DateRangeFilter",
    "DataFilter",
    "SignalFilter",
    "BacktestFilter",
    # Pagination Models
    "PaginationParams",
    "PaginationMeta",
    "PaginatedResponse",
    # Response Models
    "ApiResponse",
    "ErrorDetail",
    "ErrorResponse",
    "SuccessResponse",
    "BatchResponse",
    "WebSocketMessage",
    "RateLimitInfo",
    # Utility Functions
    "create_pagination_meta",
    "create_success_response",
    "create_error_response",
    # Legacy Aliases
    "DataRequestV2",
    "SignalRequestV2",
    "SignalV2",
    "SignalResponseV2",
]
