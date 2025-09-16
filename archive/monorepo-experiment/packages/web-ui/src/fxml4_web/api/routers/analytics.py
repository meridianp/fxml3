"""
Analytics router for performance metrics.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
import numpy as np

from fxml4_core.logging import get_logger
from fxml4_web.api.routers.auth import get_current_active_user

logger = get_logger(__name__)

router = APIRouter()


class PerformanceMetrics(BaseModel):
    period: str
    total_return: float
    annualized_return: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    avg_win: float
    avg_loss: float
    total_trades: int
    winning_trades: int
    losing_trades: int


class RiskMetrics(BaseModel):
    value_at_risk_95: float
    conditional_var_95: float
    max_drawdown: float
    max_drawdown_duration: int
    current_drawdown: float
    margin_usage: float
    leverage: float
    correlation_risk: float


class TradeHistory(BaseModel):
    id: str
    timestamp: datetime
    symbol: str
    side: str
    quantity: float
    entry_price: float
    exit_price: float
    pnl: float
    duration_hours: float
    commission: float


@router.get("/performance", response_model=PerformanceMetrics)
async def get_performance_metrics(
    period: str = Query("1M", description="Period: 1D, 1W, 1M, 3M, 6M, 1Y, ALL"),
    current_user=Depends(get_current_active_user)
):
    """Get performance metrics for specified period."""
    # Calculate period days
    period_days = {
        "1D": 1, "1W": 7, "1M": 30, "3M": 90,
        "6M": 180, "1Y": 365, "ALL": 1000
    }.get(period, 30)
    
    # Generate mock metrics - replace with real calculations
    np.random.seed(42)
    
    # Simulate performance based on period
    base_return = np.random.normal(0.05, 0.02) * (period_days / 365)
    
    metrics = PerformanceMetrics(
        period=period,
        total_return=round(base_return * 100, 2),
        annualized_return=round(base_return * 365 / period_days * 100, 2),
        sharpe_ratio=round(np.random.uniform(0.5, 2.0), 2),
        sortino_ratio=round(np.random.uniform(0.7, 2.5), 2),
        max_drawdown=round(np.random.uniform(-15, -5), 2),
        win_rate=round(np.random.uniform(0.45, 0.65) * 100, 2),
        profit_factor=round(np.random.uniform(1.1, 2.0), 2),
        avg_win=round(np.random.uniform(50, 150), 2),
        avg_loss=round(np.random.uniform(30, 80), 2),
        total_trades=int(period_days * 0.5),
        winning_trades=int(period_days * 0.5 * 0.55),
        losing_trades=int(period_days * 0.5 * 0.45)
    )
    
    return metrics


@router.get("/risk", response_model=RiskMetrics)
async def get_risk_metrics(
    current_user=Depends(get_current_active_user)
):
    """Get current risk metrics."""
    # Generate mock risk metrics - replace with real calculations
    np.random.seed(42)
    
    metrics = RiskMetrics(
        value_at_risk_95=round(np.random.uniform(-5, -2), 2),
        conditional_var_95=round(np.random.uniform(-7, -3), 2),
        max_drawdown=round(np.random.uniform(-15, -5), 2),
        max_drawdown_duration=int(np.random.uniform(5, 30)),
        current_drawdown=round(np.random.uniform(-5, 0), 2),
        margin_usage=round(np.random.uniform(20, 60), 2),
        leverage=round(np.random.uniform(1, 10), 1),
        correlation_risk=round(np.random.uniform(0.3, 0.7), 2)
    )
    
    return metrics


@router.get("/trades", response_model=List[TradeHistory])
async def get_trade_history(
    limit: int = Query(50, le=1000),
    offset: int = 0,
    symbol: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    current_user=Depends(get_current_active_user)
):
    """Get trade history."""
    # Generate mock trades - replace with real data
    trades = []
    
    if not end_date:
        end_date = datetime.now()
    if not start_date:
        start_date = end_date - timedelta(days=30)
    
    # Generate sample trades
    import uuid
    np.random.seed(42)
    
    symbols = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD"]
    if symbol:
        symbols = [symbol] if symbol in symbols else symbols
    
    for i in range(limit):
        trade_symbol = np.random.choice(symbols)
        entry_price = 1.1000 + np.random.uniform(-0.05, 0.05)
        exit_price = entry_price * (1 + np.random.uniform(-0.01, 0.01))
        quantity = np.random.choice([10000, 20000, 50000])
        
        pnl = (exit_price - entry_price) * quantity
        if trade_symbol == "USDJPY":
            pnl = pnl / 100  # Adjust for JPY
        
        trade = TradeHistory(
            id=str(uuid.uuid4()),
            timestamp=start_date + timedelta(
                seconds=np.random.randint(0, int((end_date - start_date).total_seconds()))
            ),
            symbol=trade_symbol,
            side=np.random.choice(["BUY", "SELL"]),
            quantity=quantity,
            entry_price=round(entry_price, 5),
            exit_price=round(exit_price, 5),
            pnl=round(pnl, 2),
            duration_hours=round(np.random.uniform(0.5, 48), 1),
            commission=round(quantity * 0.00001, 2)
        )
        trades.append(trade)
    
    # Sort by timestamp desc
    trades.sort(key=lambda x: x.timestamp, reverse=True)
    
    return trades[offset:offset + limit]


@router.get("/equity-curve")
async def get_equity_curve(
    period: str = Query("1M", description="Period: 1D, 1W, 1M, 3M, 6M, 1Y, ALL"),
    current_user=Depends(get_current_active_user)
):
    """Get equity curve data."""
    # Calculate period
    period_days = {
        "1D": 1, "1W": 7, "1M": 30, "3M": 90,
        "6M": 180, "1Y": 365, "ALL": 1000
    }.get(period, 30)
    
    # Generate equity curve
    end_date = datetime.now()
    start_date = end_date - timedelta(days=period_days)
    
    # Create data points
    dates = []
    current = start_date
    while current <= end_date:
        dates.append(current)
        current += timedelta(hours=4)  # 4-hour intervals
    
    # Generate equity values
    np.random.seed(42)
    initial_equity = 10000
    returns = np.random.normal(0.0001, 0.005, len(dates))
    equity = initial_equity * np.cumprod(1 + returns)
    
    # Calculate drawdown
    running_max = np.maximum.accumulate(equity)
    drawdown = (equity - running_max) / running_max * 100
    
    data = [
        {
            "timestamp": date.isoformat(),
            "equity": round(eq, 2),
            "drawdown": round(dd, 2)
        }
        for date, eq, dd in zip(dates, equity, drawdown)
    ]
    
    return {
        "period": period,
        "start_date": start_date,
        "end_date": end_date,
        "initial_equity": initial_equity,
        "final_equity": round(equity[-1], 2),
        "data": data
    }


@router.get("/summary")
async def get_account_summary(
    current_user=Depends(get_current_active_user)
):
    """Get account summary."""
    # Generate mock summary - replace with real data
    np.random.seed(42)
    
    return {
        "account_value": round(10000 * (1 + np.random.uniform(-0.1, 0.3)), 2),
        "cash_balance": round(5000 * (1 + np.random.uniform(-0.2, 0.2)), 2),
        "positions_value": round(5000 * (1 + np.random.uniform(-0.1, 0.4)), 2),
        "daily_pnl": round(np.random.uniform(-200, 300), 2),
        "daily_pnl_pct": round(np.random.uniform(-2, 3), 2),
        "open_positions": int(np.random.uniform(0, 5)),
        "pending_orders": int(np.random.uniform(0, 3)),
        "margin_used": round(np.random.uniform(1000, 5000), 2),
        "margin_available": round(np.random.uniform(3000, 8000), 2),
        "last_updated": datetime.now()
    }