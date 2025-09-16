"""Unified API schemas for FXML4."""

from typing import List, Optional

from pydantic import BaseModel, Field

# Import all schemas from the unified module
from fxml4.api.schemas import *


# Authentication models (defined here to avoid circular imports)
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


# Backward compatibility - re-export key models
__all__ = [
    # Authentication
    "Token",
    "User",
    # Enums
    "TimeframeEnum",
    "StrategyEnum",
    "SignalTypeEnum",
    "OrderSideEnum",
    "DataSourceEnum",
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
