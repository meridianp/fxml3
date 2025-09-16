"""Pydantic models for FXML4 API.

This module defines the Pydantic models used for request and response validation in the API.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, validator


class TimeframeEnum(str, Enum):
    """Supported timeframes."""
    ONE_MINUTE = "1m"
    FIVE_MINUTES = "5m"
    FIFTEEN_MINUTES = "15m"
    THIRTY_MINUTES = "30m"
    ONE_HOUR = "1h"
    FOUR_HOURS = "4h"
    ONE_DAY = "1d"
    ONE_WEEK = "1w"
    ONE_MONTH = "1M"


class StrategyEnum(str, Enum):
    """Supported strategy types."""
    INTEGRATED = "integrated_strategy"
    ML = "ml_strategy"
    WAVE = "wave_strategy"
    SENTIMENT = "sentiment_strategy"


class SignalTypeEnum(str, Enum):
    """Signal types."""
    ENTRY_LONG = "entry_long"
    ENTRY_SHORT = "entry_short"
    EXIT_LONG = "exit_long"
    EXIT_SHORT = "exit_short"
    
    
class OrderSideEnum(str, Enum):
    """Order side types."""
    BUY = "buy"
    SELL = "sell"


class DataRequest(BaseModel):
    """Data request model."""
    
    symbol: str = Field(..., description="Trading symbol (e.g., 'EURUSD', 'GBPUSD')")
    timeframe: TimeframeEnum = Field(..., description="Timeframe for the data")
    start_date: Optional[str] = Field(None, description="Start date in ISO format (e.g., '2023-01-01')")
    end_date: Optional[str] = Field(None, description="End date in ISO format (e.g., '2023-12-31')")
    limit: Optional[int] = Field(None, description="Maximum number of data points to return")
    
    @validator("start_date", "end_date", pre=True)
    def validate_dates(cls, v):
        """Validate date format."""
        if v is None:
            return v
        
        # If datetime object, convert to string
        if isinstance(v, datetime):
            return v.isoformat()
        
        # Otherwise, ensure it's a string
        if not isinstance(v, str):
            raise ValueError("Date must be a string in ISO format")
        
        return v


class SignalRequest(BaseModel):
    """Signal generation request model."""
    
    symbol: str = Field(..., description="Trading symbol (e.g., 'EURUSD', 'GBPUSD')")
    timeframe: TimeframeEnum = Field(..., description="Timeframe for the data")
    strategy: StrategyEnum = Field(..., description="Strategy to use for signal generation")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Strategy parameters")


class Signal(BaseModel):
    """Signal model."""
    
    symbol: str = Field(..., description="Trading symbol")
    timestamp: datetime = Field(..., description="Signal timestamp")
    signal_type: SignalTypeEnum = Field(..., description="Signal type")
    confidence: float = Field(..., description="Signal confidence (0.0-1.0)")
    price: float = Field(..., description="Price at signal generation")
    description: Optional[str] = Field(None, description="Signal description")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class SignalResponse(BaseModel):
    """Signal generation response model."""
    
    symbol: str = Field(..., description="Trading symbol")
    timeframe: str = Field(..., description="Timeframe used")
    strategy: str = Field(..., description="Strategy used")
    signals: List[Signal] = Field(default_factory=list, description="Generated signals")


class BacktestRequest(BaseModel):
    """Backtesting request model."""
    
    symbol: str = Field(..., description="Trading symbol (e.g., 'EURUSD', 'GBPUSD')")
    timeframe: TimeframeEnum = Field(..., description="Timeframe for the data")
    strategy: StrategyEnum = Field(..., description="Strategy to use for backtesting")
    start_date: str = Field(..., description="Start date in ISO format (e.g., '2023-01-01')")
    end_date: str = Field(..., description="End date in ISO format (e.g., '2023-12-31')")
    initial_capital: float = Field(10000.0, description="Initial capital for backtesting")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Strategy parameters")
    auto_report: bool = Field(True, description="Automatically generate a performance report")
    

class TradeInfo(BaseModel):
    """Trade information model."""
    
    position_id: str = Field(..., description="Position ID")
    symbol: str = Field(..., description="Trading symbol")
    side: OrderSideEnum = Field(..., description="Trade side (buy/sell)")
    entry_price: float = Field(..., description="Entry price")
    entry_time: Union[str, datetime] = Field(..., description="Entry timestamp")
    quantity: float = Field(..., description="Position size")
    exit_price: Optional[float] = Field(None, description="Exit price")
    exit_time: Optional[Union[str, datetime]] = Field(None, description="Exit timestamp")
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
    total_return_pct: float = Field(..., description="Total return in percentage")
    max_drawdown: float = Field(..., description="Maximum drawdown in account currency")
    max_drawdown_pct: float = Field(..., description="Maximum drawdown in percentage")
    sharpe_ratio: float = Field(..., description="Sharpe ratio")
    sortino_ratio: float = Field(..., description="Sortino ratio")
    win_rate: float = Field(..., description="Win rate")
    profit_factor: float = Field(..., description="Profit factor")
    trade_count: int = Field(..., description="Number of trades")
    report_url: Optional[str] = Field(None, description="URL to access the performance report")


class PerformanceMetricsRequest(BaseModel):
    """Performance metrics request model."""
    
    backtest_id: str = Field(..., description="ID of the backtest to analyze")
    include_trades: bool = Field(False, description="Whether to include trade details")
    include_equity_curve: bool = Field(False, description="Whether to include the equity curve")


class PerformanceReportRequest(BaseModel):
    """Performance report request model."""
    
    backtest_id: str = Field(..., description="ID of the backtest to generate a report for")
    include_figures: bool = Field(True, description="Whether to include figures in the report")
    export_pdf: bool = Field(False, description="Whether to export the report as PDF")
    

class ComparativeAnalysisRequest(BaseModel):
    """Comparative analysis request model."""
    
    backtest_ids: List[str] = Field(..., description="List of backtest IDs to compare")
    metrics: List[str] = Field(["total_return_pct", "max_drawdown_pct", "sharpe_ratio"], 
                             description="Metrics to compare")