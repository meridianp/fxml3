"""
Backtesting router.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
import uuid

from fxml4_core.logging import get_logger
from fxml4_web.api.routers.auth import get_current_active_user

logger = get_logger(__name__)

router = APIRouter()


class BacktestRequest(BaseModel):
    strategy: str
    symbols: List[str]
    start_date: datetime
    end_date: datetime
    initial_capital: float = 10000.0
    parameters: Optional[Dict[str, Any]] = None
    timeframe: str = "1h"
    commission: float = 0.001
    slippage_model: str = "fixed"


class BacktestStatus(BaseModel):
    backtest_id: str
    status: str  # PENDING, RUNNING, COMPLETED, FAILED
    progress: float
    message: str
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None


class BacktestResult(BaseModel):
    backtest_id: str
    status: str
    metrics: Dict[str, float]
    equity_curve: Optional[List[Dict[str, Any]]] = None
    trades: Optional[List[Dict[str, Any]]] = None
    created_at: datetime
    completed_at: datetime
    execution_time: float


# In-memory storage for demo - replace with database
backtest_storage = {}


async def run_backtest_task(backtest_id: str, request: BacktestRequest):
    """Background task to run backtest."""
    try:
        # Update status
        backtest_storage[backtest_id]["status"] = "RUNNING"
        backtest_storage[backtest_id]["updated_at"] = datetime.now()
        
        # Simulate backtest execution
        import time
        import numpy as np
        
        # Simulate progress updates
        for i in range(10):
            time.sleep(0.5)  # Simulate work
            backtest_storage[backtest_id]["progress"] = (i + 1) * 10
            backtest_storage[backtest_id]["updated_at"] = datetime.now()
        
        # Generate mock results
        days = (request.end_date - request.start_date).days
        dates = [request.start_date + timedelta(days=i) for i in range(days)]
        
        # Generate equity curve
        equity = [request.initial_capital]
        for _ in range(len(dates) - 1):
            change = np.random.normal(0.0002, 0.01)
            equity.append(equity[-1] * (1 + change))
        
        equity_curve = [
            {"timestamp": date.isoformat(), "equity": eq}
            for date, eq in zip(dates, equity)
        ]
        
        # Generate some trades
        trades = []
        for i in range(20):
            entry_date = request.start_date + timedelta(days=np.random.randint(0, days//2))
            exit_date = entry_date + timedelta(days=np.random.randint(1, 10))
            
            trade = {
                "id": str(uuid.uuid4()),
                "symbol": np.random.choice(request.symbols),
                "entry_date": entry_date.isoformat(),
                "exit_date": exit_date.isoformat(),
                "side": np.random.choice(["BUY", "SELL"]),
                "quantity": 10000,
                "entry_price": 1.1000 + np.random.uniform(-0.01, 0.01),
                "exit_price": 1.1000 + np.random.uniform(-0.01, 0.01),
                "pnl": np.random.normal(50, 100)
            }
            trades.append(trade)
        
        # Calculate metrics
        total_return = (equity[-1] - request.initial_capital) / request.initial_capital
        
        # Update with results
        backtest_storage[backtest_id].update({
            "status": "COMPLETED",
            "progress": 100,
            "completed_at": datetime.now(),
            "result": {
                "backtest_id": backtest_id,
                "status": "COMPLETED",
                "metrics": {
                    "total_return": round(total_return * 100, 2),
                    "annualized_return": round(total_return * 365 / days * 100, 2),
                    "sharpe_ratio": round(np.random.uniform(0.5, 2.0), 2),
                    "max_drawdown": round(np.random.uniform(-20, -5), 2),
                    "win_rate": round(np.random.uniform(0.4, 0.6) * 100, 2),
                    "profit_factor": round(np.random.uniform(1.0, 2.0), 2),
                    "total_trades": len(trades)
                },
                "equity_curve": equity_curve,
                "trades": trades,
                "created_at": backtest_storage[backtest_id]["created_at"],
                "completed_at": datetime.now(),
                "execution_time": 5.0
            }
        })
        
    except Exception as e:
        logger.error(f"Backtest {backtest_id} failed: {e}")
        backtest_storage[backtest_id].update({
            "status": "FAILED",
            "message": str(e),
            "updated_at": datetime.now()
        })


@router.post("/run")
async def run_backtest(
    request: BacktestRequest,
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_active_user)
):
    """Start a new backtest."""
    # Validate request
    if request.end_date <= request.start_date:
        raise HTTPException(status_code=400, detail="End date must be after start date")
    
    if request.initial_capital <= 0:
        raise HTTPException(status_code=400, detail="Initial capital must be positive")
    
    # Create backtest record
    backtest_id = str(uuid.uuid4())
    
    backtest_storage[backtest_id] = {
        "backtest_id": backtest_id,
        "status": "PENDING",
        "progress": 0,
        "message": "Backtest queued",
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
        "completed_at": None,
        "user": current_user.username,
        "request": request.dict()
    }
    
    # Add to background tasks
    background_tasks.add_task(run_backtest_task, backtest_id, request)
    
    logger.info(f"Backtest {backtest_id} created for user {current_user.username}")
    
    return {
        "backtest_id": backtest_id,
        "status": "PENDING",
        "message": "Backtest started successfully"
    }


@router.get("/{backtest_id}/status", response_model=BacktestStatus)
async def get_backtest_status(
    backtest_id: str,
    current_user=Depends(get_current_active_user)
):
    """Get backtest status."""
    if backtest_id not in backtest_storage:
        raise HTTPException(status_code=404, detail="Backtest not found")
    
    backtest = backtest_storage[backtest_id]
    
    # Check ownership
    if backtest["user"] != current_user.username:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return BacktestStatus(
        backtest_id=backtest_id,
        status=backtest["status"],
        progress=backtest["progress"],
        message=backtest.get("message", ""),
        created_at=backtest["created_at"],
        updated_at=backtest["updated_at"],
        completed_at=backtest.get("completed_at")
    )


@router.get("/{backtest_id}", response_model=BacktestResult)
async def get_backtest_result(
    backtest_id: str,
    current_user=Depends(get_current_active_user)
):
    """Get backtest results."""
    if backtest_id not in backtest_storage:
        raise HTTPException(status_code=404, detail="Backtest not found")
    
    backtest = backtest_storage[backtest_id]
    
    # Check ownership
    if backtest["user"] != current_user.username:
        raise HTTPException(status_code=403, detail="Access denied")
    
    if backtest["status"] != "COMPLETED":
        raise HTTPException(
            status_code=400,
            detail=f"Backtest not completed. Status: {backtest['status']}"
        )
    
    return backtest["result"]


@router.get("/")
async def list_backtests(
    limit: int = 10,
    offset: int = 0,
    current_user=Depends(get_current_active_user)
):
    """List user's backtests."""
    # Filter by user
    user_backtests = [
        {
            "backtest_id": bt["backtest_id"],
            "status": bt["status"],
            "created_at": bt["created_at"],
            "strategy": bt["request"]["strategy"],
            "symbols": bt["request"]["symbols"]
        }
        for bt in backtest_storage.values()
        if bt["user"] == current_user.username
    ]
    
    # Sort by created_at desc
    user_backtests.sort(key=lambda x: x["created_at"], reverse=True)
    
    # Paginate
    total = len(user_backtests)
    items = user_backtests[offset:offset + limit]
    
    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset
    }