"""
Market data router.
"""

from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
import pandas as pd

from fxml4_core.logging import get_logger
from fxml4_web.api.routers.auth import get_current_active_user

logger = get_logger(__name__)

router = APIRouter()


class Symbol(BaseModel):
    symbol: str
    name: str
    base_currency: str
    quote_currency: str
    pip_size: float
    min_lot_size: float
    max_lot_size: float


class MarketData(BaseModel):
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    bid: Optional[float] = None
    ask: Optional[float] = None
    spread: Optional[float] = None


class MarketDataRequest(BaseModel):
    symbol: str
    timeframe: str = "1h"
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    limit: int = 1000


@router.get("/symbols", response_model=List[Symbol])
async def get_symbols(current_user=Depends(get_current_active_user)):
    """Get available trading symbols."""
    # Mock data - replace with real data source
    symbols = [
        Symbol(
            symbol="EURUSD",
            name="Euro / US Dollar",
            base_currency="EUR",
            quote_currency="USD",
            pip_size=0.0001,
            min_lot_size=0.01,
            max_lot_size=100.0
        ),
        Symbol(
            symbol="GBPUSD",
            name="British Pound / US Dollar",
            base_currency="GBP",
            quote_currency="USD",
            pip_size=0.0001,
            min_lot_size=0.01,
            max_lot_size=100.0
        ),
        Symbol(
            symbol="USDJPY",
            name="US Dollar / Japanese Yen",
            base_currency="USD",
            quote_currency="JPY",
            pip_size=0.01,
            min_lot_size=0.01,
            max_lot_size=100.0
        ),
    ]
    
    return symbols


@router.get("/data/{symbol}", response_model=List[MarketData])
async def get_market_data(
    symbol: str,
    timeframe: str = Query("1h", description="Timeframe: 1m, 5m, 15m, 1h, 4h, 1d"),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = Query(100, le=5000),
    current_user=Depends(get_current_active_user)
):
    """Get historical market data."""
    # Validate symbol
    valid_symbols = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD"]
    if symbol not in valid_symbols:
        raise HTTPException(status_code=404, detail=f"Symbol {symbol} not found")
    
    # Generate mock data - replace with real data source
    if not end_date:
        end_date = datetime.now()
    if not start_date:
        # Default to last N bars based on timeframe
        timeframe_minutes = {
            "1m": 1, "5m": 5, "15m": 15, "30m": 30,
            "1h": 60, "4h": 240, "1d": 1440
        }
        minutes = timeframe_minutes.get(timeframe, 60)
        start_date = end_date - timedelta(minutes=minutes * limit)
    
    # Generate sample data
    import numpy as np
    np.random.seed(42)
    
    dates = pd.date_range(start=start_date, end=end_date, freq=timeframe)[:limit]
    
    # Base prices for different symbols
    base_prices = {
        "EURUSD": 1.1000,
        "GBPUSD": 1.3000,
        "USDJPY": 110.00,
        "USDCHF": 0.9200,
        "AUDUSD": 0.7500
    }
    
    base_price = base_prices[symbol]
    
    # Generate realistic OHLC data
    data = []
    for i, date in enumerate(dates):
        # Random walk
        change = np.random.normal(0, 0.001)
        open_price = base_price * (1 + change)
        
        # Intraday movement
        high_price = open_price * (1 + abs(np.random.normal(0, 0.0005)))
        low_price = open_price * (1 - abs(np.random.normal(0, 0.0005)))
        close_price = np.random.uniform(low_price, high_price)
        
        # Update base price for next bar
        base_price = close_price
        
        data.append(MarketData(
            symbol=symbol,
            timestamp=date,
            open=round(open_price, 5),
            high=round(high_price, 5),
            low=round(low_price, 5),
            close=round(close_price, 5),
            volume=round(np.random.uniform(1000, 5000), 2),
            bid=round(close_price - 0.00005, 5),
            ask=round(close_price + 0.00005, 5),
            spread=0.0001
        ))
    
    return data


@router.post("/data", response_model=List[MarketData])
async def post_market_data(
    request: MarketDataRequest,
    current_user=Depends(get_current_active_user)
):
    """Get market data with POST request."""
    return await get_market_data(
        symbol=request.symbol,
        timeframe=request.timeframe,
        start_date=request.start_date,
        end_date=request.end_date,
        limit=request.limit,
        current_user=current_user
    )


@router.get("/quote/{symbol}")
async def get_quote(
    symbol: str,
    current_user=Depends(get_current_active_user)
):
    """Get current quote for symbol."""
    # Mock real-time quote
    import numpy as np
    
    base_prices = {
        "EURUSD": 1.1000,
        "GBPUSD": 1.3000,
        "USDJPY": 110.00,
        "USDCHF": 0.9200,
        "AUDUSD": 0.7500
    }
    
    if symbol not in base_prices:
        raise HTTPException(status_code=404, detail=f"Symbol {symbol} not found")
    
    base = base_prices[symbol]
    spread = 0.0001 if symbol != "USDJPY" else 0.01
    
    # Add some randomness
    mid = base * (1 + np.random.normal(0, 0.001))
    
    return {
        "symbol": symbol,
        "timestamp": datetime.now(),
        "bid": round(mid - spread/2, 5),
        "ask": round(mid + spread/2, 5),
        "mid": round(mid, 5),
        "spread": spread,
        "daily_change": round(np.random.normal(0, 0.005), 4),
        "daily_change_pct": round(np.random.normal(0, 0.5), 2)
    }