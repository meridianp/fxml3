"""
Simple data routes for UAT testing.

This module provides a simplified data endpoint that returns mock data for UAT testing.
"""

import logging
import random
from datetime import datetime, timedelta
from typing import Any, Dict

from fastapi import APIRouter, Depends, Header, HTTPException
from jose import JWTError, jwt

from fxml4.api.auth.auth import User
from fxml4.api.schemas.api_models import DataRequest

# Create router
router = APIRouter()
logger = logging.getLogger(__name__)

# UAT Authentication (no database required)
SECRET_KEY = "uattest123456789012345678901234567890"  # UAT test key
ALGORITHM = "HS256"


def get_current_user_uat(authorization: str = Header(None)) -> User:
    """Simplified authentication for UAT testing (no database)."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401, detail="Missing or invalid authorization header"
        )

    token = authorization[7:]  # Remove "Bearer " prefix

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        scopes = payload.get("scopes", [])

        if not username:
            raise HTTPException(status_code=401, detail="Invalid token")

        # Create mock user for UAT
        class UATUser:
            def __init__(self, username: str, scopes: list):
                self.username = username
                self.scopes = scopes
                self.is_active = True

        return UATUser(username=username, scopes=scopes)

    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


@router.post("/data", response_model=Dict[str, Any], tags=["data"])
async def get_market_data(
    request: DataRequest, current_user=Depends(get_current_user_uat)
):
    """Get mock market data for UAT testing."""
    logger.info(f"UAT Data request: {request.symbol} {request.timeframe}")

    # Generate mock OHLCV data
    limit = request.limit or 10
    base_prices = {
        "EURUSD": 1.0850,
        "GBPUSD": 1.2650,
        "USDJPY": 149.50,
        "USDCHF": 0.8750,
    }
    base_price = base_prices.get(request.symbol, 1.0000)

    # Generate realistic time series data
    data_points = []
    current_time = datetime.now() - timedelta(hours=limit)
    current_price = base_price

    for i in range(limit):
        # Generate realistic OHLC data
        open_price = current_price
        change = random.uniform(-0.002, 0.002)  # ±0.2% change
        close_price = open_price * (1 + change)
        high_price = max(open_price, close_price) * (1 + random.uniform(0, 0.001))
        low_price = min(open_price, close_price) * (1 - random.uniform(0, 0.001))

        data_points.append(
            {
                "time": (current_time + timedelta(hours=i)).isoformat(),
                "symbol": request.symbol,
                "open": round(open_price, 5),
                "high": round(high_price, 5),
                "low": round(low_price, 5),
                "close": round(close_price, 5),
                "volume": random.randint(100, 1000),
                "tick_count": random.randint(50, 200),
                "source": "mock_uat",
            }
        )
        current_price = close_price

    return {
        "symbol": request.symbol,
        "timeframe": request.timeframe,
        "start_date": request.start_date,
        "end_date": request.end_date,
        "data": data_points,
        "count": len(data_points),
        "source": "mock_uat",
        "status": "success",
    }
