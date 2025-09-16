"""
WebSocket routes for FXML4 API.

This module handles real-time WebSocket connections for market data and trading updates.
"""

import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from fastapi.security import HTTPBearer

from fxml4.api.services.websocket import websocket_service

# Create router
router = APIRouter()
logger = logging.getLogger(__name__)

# Security scheme for WebSocket (optional)
security = HTTPBearer(auto_error=False)


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    client_id: Optional[str] = Query(None, description="Optional client identifier"),
):
    """
    WebSocket endpoint for real-time data streaming.

    Supported message types:
    - subscribe: Subscribe to data streams
    - unsubscribe: Unsubscribe from data streams
    - ping: Heartbeat message
    - get_symbols: Get available symbols
    - get_latest_tick: Get latest tick for a symbol

    Subscription keys:
    - tick:{symbol} - Real-time tick data for symbol
    - ohlcv:{symbol}:{timeframe} - OHLCV data updates
    - trades:{symbol} - Trade execution updates
    - signals:{symbol} - Trading signals
    """

    # Generate client ID if not provided
    if not client_id:
        client_id = str(uuid.uuid4())

    logger.info(f"WebSocket connection attempt from client {client_id}")

    try:
        await websocket_service.handle_websocket(websocket, client_id)
    except WebSocketDisconnect:
        logger.info(f"WebSocket client {client_id} disconnected normally")
    except Exception as e:
        logger.error(f"WebSocket error for client {client_id}: {e}")


@router.websocket("/ws/{symbol}")
async def symbol_websocket_endpoint(
    websocket: WebSocket,
    symbol: str,
    timeframe: str = Query("1m", description="Timeframe for OHLCV data"),
    client_id: Optional[str] = Query(None, description="Optional client identifier"),
):
    """
    Symbol-specific WebSocket endpoint for convenience.

    Automatically subscribes to tick data and OHLCV data for the specified symbol.
    """

    # Generate client ID if not provided
    if not client_id:
        client_id = str(uuid.uuid4())

    logger.info(
        f"Symbol-specific WebSocket connection for {symbol} from client {client_id}"
    )

    try:
        await websocket_service.connect_client(websocket, client_id)

        # Auto-subscribe to symbol data
        await websocket_service.manager.subscribe(client_id, f"tick:{symbol}")
        await websocket_service.manager.subscribe(
            client_id, f"ohlcv:{symbol}:{timeframe}"
        )

        # Send welcome message
        await websocket_service.manager.send_personal_message(
            client_id,
            {
                "type": "welcome",
                "message": f"Connected to {symbol} data stream",
                "symbol": symbol,
                "timeframe": timeframe,
                "auto_subscriptions": [f"tick:{symbol}", f"ohlcv:{symbol}:{timeframe}"],
                "client_id": client_id,
            },
        )

        # Handle connection
        await websocket_service.handle_websocket(websocket, client_id)

    except WebSocketDisconnect:
        logger.info(f"Symbol WebSocket client {client_id} disconnected normally")
    except Exception as e:
        logger.error(f"Symbol WebSocket error for client {client_id}: {e}")
    finally:
        await websocket_service.disconnect_client(client_id)


@router.on_event("startup")
async def startup_websocket_service():
    """Start WebSocket background tasks."""
    await websocket_service.start_background_tasks()
    logger.info("WebSocket service started")


@router.on_event("shutdown")
async def shutdown_websocket_service():
    """Stop WebSocket background tasks."""
    await websocket_service.stop_background_tasks()
    logger.info("WebSocket service stopped")
