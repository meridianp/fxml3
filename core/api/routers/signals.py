"""
Signal generation routes for FXML4 API.

This module handles trading signal generation and real-time signal processing.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query, status

from fxml4.api.auth.auth import User, get_current_active_user
from fxml4.api.schemas.api_models import SignalRequest
from fxml4.api.services.signal_processing import signal_processing_service

# Create router
router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/signals", response_model=Dict[str, Any], tags=["signals"])
async def generate_signals(
    request: SignalRequest, current_user: User = Depends(get_current_active_user)
):
    """Generate trading signals on-demand for a specific symbol."""
    try:
        logger.info(f"Signal request for {request.symbol}")

        # Get recent market data for signal generation with fallback
        from fxml4.api.services.market_data import market_data_service

        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=48)  # Get more data for analysis

        try:
            # Add timeout to prevent hanging
            import asyncio

            market_data = await asyncio.wait_for(
                market_data_service.get_ohlcv_data(
                    symbol=request.symbol,
                    timeframe=request.timeframe,
                    start_time=start_time,
                    end_time=end_time,
                    limit=100,
                ),
                timeout=3.0,  # 3 second timeout
            )

            # Check if we got actual data - if not, trigger fallback
            if not market_data or len(market_data) == 0:
                raise Exception(
                    "Primary service returned no data - triggering live data fallback"
                )

        except Exception as service_error:
            logger.warning(
                f"Primary market data service unavailable: {service_error}. "
                f"Trying live data service."
            )
            # Try live data service as fallback
            try:
                from fxml4.api.services.direct_polygon_service import (
                    direct_polygon_service,
                )

                market_data = await direct_polygon_service.get_real_forex_data(
                    symbol=request.symbol, timeframe=request.timeframe, limit=100
                )

                if market_data:
                    logger.info(
                        f"Successfully retrieved {len(market_data)} live data "
                        f"points for signals"
                    )
                else:
                    raise Exception("No live data available")

            except Exception as live_error:
                logger.error(f"Live data service failed: {live_error}")
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="No market data sources available for signal generation",
                )

        if not market_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No market data available for {request.symbol}",
            )

        # Convert to DataFrame
        import pandas as pd

        df_data = []
        for point in market_data:
            df_data.append(
                {
                    "timestamp": point.time,
                    "open": point.open,
                    "high": point.high,
                    "low": point.low,
                    "close": point.close,
                    "volume": point.volume,
                }
            )

        df = pd.DataFrame(df_data)
        df.set_index("timestamp", inplace=True)
        df.sort_index(inplace=True)

        # Generate signal - use ML generator if available, otherwise simple fallback
        if request.symbol in signal_processing_service.signal_generators:
            logger.info(f"Using ML signal generator for {request.symbol}")
            signal_generator = signal_processing_service.signal_generators[
                request.symbol
            ]
            signal = await signal_processing_service._generate_signal(
                signal_generator, request.symbol, df
            )
        else:
            logger.info(f"Using simple signal fallback for {request.symbol}")
            # Use simple moving average signal as fallback
            signal = signal_processing_service._create_simple_signal(request.symbol, df)

        if not signal:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate signal",
            )

        return {
            "symbol": signal.symbol,
            "timeframe": signal.timeframe,
            "timestamp": signal.timestamp.isoformat(),
            "direction": signal.direction,
            "confidence": signal.confidence,
            "signal_type": signal.signal_type,
            "source": signal.source,
            "metadata": signal.metadata,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error generating signals: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get("/signals/{symbol}", response_model=Dict[str, Any], tags=["signals"])
async def get_recent_signals(
    symbol: str,
    limit: int = Query(
        10, description="Number of recent signals to return", ge=1, le=100
    ),
    hours_back: int = Query(
        24, description="Hours back to look for signals", ge=1, le=168
    ),
    current_user: User = Depends(get_current_active_user),
):
    """Get recent signals for a symbol."""
    try:
        signals = await signal_processing_service.get_recent_signals(
            symbol=symbol, limit=limit, hours_back=hours_back
        )

        # Convert to API response format
        signals_data = []
        for signal in signals:
            signals_data.append(
                {
                    "timestamp": signal.timestamp.isoformat(),
                    "symbol": signal.symbol,
                    "timeframe": signal.timeframe,
                    "direction": signal.direction,
                    "confidence": signal.confidence,
                    "signal_type": signal.signal_type,
                    "source": signal.source,
                    "metadata": signal.metadata,
                }
            )

        return {
            "symbol": symbol,
            "signals": signals_data,
            "count": len(signals_data),
            "hours_back": hours_back,
        }

    except Exception as e:
        logger.exception("Error getting recent signals: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.post("/signals/start/{symbol}", response_model=Dict[str, Any], tags=["signals"])
async def start_signal_processing(
    symbol: str, current_user: User = Depends(get_current_active_user)
):
    """Start real-time signal processing for a symbol."""
    try:
        if symbol not in signal_processing_service.active_symbols:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No signal generator available for {symbol}",
            )

        await signal_processing_service.start_signal_processing([symbol])

        return {
            "message": f"Started signal processing for {symbol}",
            "symbol": symbol,
            "status": "started",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error starting signal processing: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.post("/signals/stop/{symbol}", response_model=Dict[str, Any], tags=["signals"])
async def stop_signal_processing(
    symbol: str, current_user: User = Depends(get_current_active_user)
):
    """Stop real-time signal processing for a symbol."""
    try:
        await signal_processing_service.stop_signal_processing([symbol])

        return {
            "message": f"Stopped signal processing for {symbol}",
            "symbol": symbol,
            "status": "stopped",
        }

    except Exception as e:
        logger.exception("Error stopping signal processing: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get("/signals/status", response_model=Dict[str, Any], tags=["signals"])
async def get_signal_processing_status(
    current_user: User = Depends(get_current_active_user),
):
    """Get the status of signal processing for all symbols."""
    try:
        active_processing = list(signal_processing_service.processing_tasks.keys())
        available_symbols = list(signal_processing_service.active_symbols)

        return {
            "active_processing": active_processing,
            "available_symbols": available_symbols,
            "processing_count": len(active_processing),
            "available_count": len(available_symbols),
        }

    except Exception as e:
        logger.exception("Error getting signal processing status: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


# Startup event to initialize signal processing service
@router.on_event("startup")
async def startup_signal_processing():
    """Initialize the signal processing service on startup."""
    try:
        await signal_processing_service.initialize()
        logger.info("Signal processing service initialized")
    except Exception as e:
        logger.error(f"Failed to initialize signal processing service: {e}")


# Shutdown event to cleanup signal processing service
@router.on_event("shutdown")
async def shutdown_signal_processing():
    """Cleanup the signal processing service on shutdown."""
    try:
        await signal_processing_service.close()
        logger.info("Signal processing service closed")
    except Exception as e:
        logger.error(f"Error closing signal processing service: {e}")
