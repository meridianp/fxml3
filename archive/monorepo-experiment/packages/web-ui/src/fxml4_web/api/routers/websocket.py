"""
WebSocket router for real-time data.
"""

from typing import Dict, Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from datetime import datetime
import json
import asyncio

from fxml4_core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


class ConnectionManager:
    """Manage WebSocket connections."""
    
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {
            "market": set(),
            "signals": set(),
            "positions": set()
        }
    
    async def connect(self, websocket: WebSocket, channel: str):
        """Accept connection and add to channel."""
        await websocket.accept()
        if channel not in self.active_connections:
            self.active_connections[channel] = set()
        self.active_connections[channel].add(websocket)
        logger.info(f"Client connected to {channel} channel")
    
    def disconnect(self, websocket: WebSocket, channel: str):
        """Remove connection from channel."""
        if channel in self.active_connections:
            self.active_connections[channel].discard(websocket)
            logger.info(f"Client disconnected from {channel} channel")
    
    async def send_personal_message(self, message: str, websocket: WebSocket):
        """Send message to specific connection."""
        await websocket.send_text(message)
    
    async def broadcast(self, message: str, channel: str):
        """Broadcast message to all connections in channel."""
        if channel in self.active_connections:
            disconnected = set()
            for connection in self.active_connections[channel]:
                try:
                    await connection.send_text(message)
                except:
                    disconnected.add(connection)
            
            # Remove disconnected clients
            for conn in disconnected:
                self.active_connections[channel].discard(conn)


manager = ConnectionManager()


@router.websocket("/market/{symbol}")
async def market_data_stream(websocket: WebSocket, symbol: str):
    """Stream real-time market data for a symbol."""
    channel = f"market_{symbol}"
    await manager.connect(websocket, channel)
    
    try:
        # Send initial message
        await websocket.send_json({
            "type": "connected",
            "channel": channel,
            "timestamp": datetime.now().isoformat()
        })
        
        # Simulate market data stream
        import numpy as np
        base_price = 1.1000
        
        while True:
            # Generate tick data
            change = np.random.normal(0, 0.0001)
            base_price *= (1 + change)
            
            tick_data = {
                "type": "tick",
                "symbol": symbol,
                "timestamp": datetime.now().isoformat(),
                "bid": round(base_price - 0.00005, 5),
                "ask": round(base_price + 0.00005, 5),
                "mid": round(base_price, 5),
                "volume": round(np.random.uniform(100, 1000), 2)
            }
            
            await websocket.send_json(tick_data)
            await asyncio.sleep(1)  # Send tick every second
            
    except WebSocketDisconnect:
        manager.disconnect(websocket, channel)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket, channel)


@router.websocket("/signals")
async def signals_stream(websocket: WebSocket):
    """Stream real-time trading signals."""
    await manager.connect(websocket, "signals")
    
    try:
        # Send initial message
        await websocket.send_json({
            "type": "connected",
            "channel": "signals",
            "timestamp": datetime.now().isoformat()
        })
        
        # Simulate signal stream
        import numpy as np
        import uuid
        
        symbols = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD"]
        signal_types = ["BUY", "SELL", "HOLD"]
        
        while True:
            # Random chance of generating a signal
            if np.random.random() < 0.1:  # 10% chance per iteration
                signal = {
                    "type": "signal",
                    "id": str(uuid.uuid4()),
                    "timestamp": datetime.now().isoformat(),
                    "symbol": np.random.choice(symbols),
                    "signal_type": np.random.choice(signal_types),
                    "strength": round(np.random.uniform(0.5, 1.0), 2),
                    "price": round(1.1000 + np.random.uniform(-0.01, 0.01), 5),
                    "source": "ml_strategy"
                }
                
                await websocket.send_json(signal)
            
            await asyncio.sleep(5)  # Check every 5 seconds
            
    except WebSocketDisconnect:
        manager.disconnect(websocket, "signals")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket, "signals")


@router.websocket("/positions")
async def positions_stream(websocket: WebSocket):
    """Stream real-time position updates."""
    await manager.connect(websocket, "positions")
    
    try:
        # Send initial message
        await websocket.send_json({
            "type": "connected",
            "channel": "positions",
            "timestamp": datetime.now().isoformat()
        })
        
        # Simulate position updates
        import numpy as np
        
        # Mock positions
        positions = {
            "pos_001": {
                "symbol": "EURUSD",
                "side": "LONG",
                "quantity": 10000,
                "entry_price": 1.1000,
                "current_price": 1.1000
            },
            "pos_002": {
                "symbol": "GBPUSD",
                "side": "SHORT",
                "quantity": 5000,
                "entry_price": 1.3000,
                "current_price": 1.3000
            }
        }
        
        while True:
            # Update position prices
            for pos_id, pos in positions.items():
                # Random price movement
                change = np.random.normal(0, 0.0005)
                pos["current_price"] *= (1 + change)
                
                # Calculate P&L
                if pos["side"] == "LONG":
                    pnl = (pos["current_price"] - pos["entry_price"]) * pos["quantity"]
                else:
                    pnl = (pos["entry_price"] - pos["current_price"]) * pos["quantity"]
                
                update = {
                    "type": "position_update",
                    "id": pos_id,
                    "timestamp": datetime.now().isoformat(),
                    "symbol": pos["symbol"],
                    "current_price": round(pos["current_price"], 5),
                    "unrealized_pnl": round(pnl, 2),
                    "pnl_pct": round(pnl / (pos["entry_price"] * pos["quantity"]) * 100, 2)
                }
                
                await websocket.send_json(update)
            
            await asyncio.sleep(2)  # Update every 2 seconds
            
    except WebSocketDisconnect:
        manager.disconnect(websocket, "positions")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket, "positions")


@router.websocket("/echo")
async def echo_websocket(websocket: WebSocket):
    """Echo WebSocket for testing."""
    await websocket.accept()
    
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(f"Echo: {data}")
    except WebSocketDisconnect:
        logger.info("Echo WebSocket disconnected")