"""
Data routes for FXML4 API.

This module handles market data retrieval from TimescaleDB and external data sources.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query, status

from fxml4.api.auth.uat_auth import UATUser, get_current_active_user_uat
from fxml4.api.schemas.api_models import DataRequest
from fxml4.api.services.market_data import MarketDataPoint, market_data_service

# Create router
router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/data", response_model=Dict[str, Any], tags=["data"])
async def get_data(
    request: DataRequest, current_user: UATUser = Depends(get_current_active_user_uat)
):
    """Get market data from TimescaleDB or external feeds."""
    try:
        logger.info(f"Data request: {request.symbol} {request.timeframe}")

        # Parse dates
        start_date = None
        if request.start_date:
            start_date = pd.to_datetime(request.start_date)

        end_date = None
        if request.end_date:
            end_date = pd.to_datetime(request.end_date)

        # Try to get data from our service, fallback to live data for UAT
        try:
            # Add timeout to prevent hanging
            import asyncio

            data_points = await asyncio.wait_for(
                market_data_service.get_ohlcv_data(
                    symbol=request.symbol,
                    timeframe=request.timeframe,
                    start_time=start_date,
                    end_time=end_date,
                    limit=request.limit,
                ),
                timeout=3.0,  # 3 second timeout
            )

            # Check if we got actual data - if not, trigger fallback
            if not data_points or len(data_points) == 0:
                raise Exception(
                    "Primary service returned no data - triggering live data fallback"
                )

        except Exception as service_error:
            logger.warning(
                f"Primary market data service unavailable: {service_error}. Using fast data service."
            )
            # Use fast data service for performance
            try:
                from fxml4.api.services.fast_market_data import fast_market_data_service

                data_points = await fast_market_data_service.get_ohlcv_data(
                    symbol=request.symbol,
                    timeframe=request.timeframe,
                    start_time=start_date,
                    end_time=end_date,
                    limit=request.limit or 100,
                )

                if data_points:
                    logger.info(
                        f"Fast service: Retrieved {len(data_points)} data points"
                    )
                else:
                    raise Exception("Fast service returned no data")

            except Exception as fast_error:
                logger.error(f"Fast data service failed: {fast_error}")
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Market data services are temporarily unavailable. Please try again later.",
                )

        # Convert to JSON-serializable format
        data_dict = []
        for point in data_points:
            data_dict.append(
                {
                    "time": point.time.isoformat(),
                    "symbol": point.symbol,
                    "open": point.open,
                    "high": point.high,
                    "low": point.low,
                    "close": point.close,
                    "volume": point.volume,
                    "tick_count": point.tick_count,
                    "source": point.source,
                }
            )

        source = data_points[0].source if data_points else "no_data"

        return {
            "symbol": request.symbol,
            "timeframe": request.timeframe,
            "start_date": request.start_date,
            "end_date": request.end_date,
            "data": data_dict,
            "count": len(data_dict),
            "source": source,
        }
    except Exception as e:
        logger.exception("Error getting data: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/symbols", response_model=Dict[str, Any], tags=["data"])
async def get_symbols(current_user: UATUser = Depends(get_current_active_user_uat)):
    """Get list of available symbols."""
    try:
        symbols = await market_data_service.get_available_symbols()

        return {"symbols": symbols, "count": len(symbols)}
    except Exception as e:
        logger.exception("Error getting symbols: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/tick/{symbol}", response_model=Dict[str, Any], tags=["data"])
async def get_latest_tick(
    symbol: str,
    tick_type: str = Query("trade", description="Type of tick data (trade, bid, ask)"),
    current_user: UATUser = Depends(get_current_active_user_uat),
):
    """Get latest tick data for a symbol."""
    try:
        tick_data = await market_data_service.get_latest_tick(symbol, tick_type)

        if not tick_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No tick data found for {symbol}",
            )

        return tick_data
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error getting latest tick: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/ohlcv/{symbol}", response_model=Dict[str, Any], tags=["data"])
async def get_ohlcv(
    symbol: str,
    timeframe: str = Query(
        "1h", description="Timeframe (1m, 5m, 15m, 30m, 1h, 4h, 1d)"
    ),
    limit: int = Query(
        100, description="Number of data points to return", ge=1, le=5000
    ),
    current_user: UATUser = Depends(get_current_active_user_uat),
):
    """Get OHLCV data for a symbol (GET endpoint for convenience)."""
    try:
        data_points = await market_data_service.get_ohlcv_data(
            symbol=symbol, timeframe=timeframe, limit=limit
        )

        # Convert to JSON-serializable format
        data_dict = []
        for point in data_points:
            data_dict.append(
                {
                    "time": point.time.isoformat(),
                    "symbol": point.symbol,
                    "open": point.open,
                    "high": point.high,
                    "low": point.low,
                    "close": point.close,
                    "volume": point.volume,
                    "tick_count": point.tick_count,
                    "source": point.source,
                }
            )

        source = data_points[0].source if data_points else "no_data"

        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "data": data_dict,
            "count": len(data_dict),
            "source": source,
        }
    except Exception as e:
        logger.exception("Error getting OHLCV data: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post("/store", response_model=Dict[str, Any], tags=["data"])
async def store_market_data(
    symbol: str,
    timeframe: str,
    data_points: List[Dict[str, Any]],
    current_user: UATUser = Depends(get_current_active_user_uat),
):
    """Store market data in TimescaleDB (admin only)."""
    try:
        # Convert dict data to MarketDataPoint objects
        market_data_points = []
        for point_data in data_points:
            market_data_points.append(
                MarketDataPoint(
                    time=datetime.fromisoformat(
                        point_data["time"].replace("Z", "+00:00")
                    ),
                    symbol=symbol,
                    open=point_data["open"],
                    high=point_data["high"],
                    low=point_data["low"],
                    close=point_data["close"],
                    volume=point_data.get("volume", 0),
                    tick_count=point_data.get("tick_count", 0),
                    source=point_data.get("source", "api"),
                )
            )

        success = await market_data_service.store_market_data(
            symbol=symbol, data_points=market_data_points, timeframe=timeframe
        )

        if success:
            return {
                "message": f"Stored {len(market_data_points)} data points for {symbol}",
                "count": len(market_data_points),
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to store market data",
            )

    except Exception as e:
        logger.exception("Error storing market data: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
