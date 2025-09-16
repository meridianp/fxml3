#!/usr/bin/env python3
"""FXCM Bridge Service.

This service runs in a Docker container and provides a bridge between
the FIX-based broker abstraction and FXCM's ForexConnect API.
"""

import asyncio
import json
import logging
import signal
import sys
import time
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fix_translator import FXCMFIXTranslator
from pydantic import BaseModel

from config import BridgeConfig

# Configure logging
if BridgeConfig.LOG_FORMAT == "json":
    from pythonjsonlogger import jsonlogger

    handler = logging.StreamHandler()
    handler.setFormatter(jsonlogger.JsonFormatter())
    logging.basicConfig(level=BridgeConfig.LOG_LEVEL, handlers=[handler])
else:
    logging.basicConfig(
        level=BridgeConfig.LOG_LEVEL,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

logger = logging.getLogger(__name__)

# Import ForexConnect (will be available in Docker container)
try:
    import forexconnect as fx

    FOREXCONNECT_AVAILABLE = True
except ImportError:
    logger.warning("ForexConnect not available - running in mock mode")
    FOREXCONNECT_AVAILABLE = False
    fx = None


# Pydantic models for API
class OrderRequest(BaseModel):
    """Order submission request."""

    fix_message: str
    correlation_id: Optional[str] = None


class OrderResponse(BaseModel):
    """Order submission response."""

    success: bool
    order_id: Optional[str] = None
    message: Optional[str] = None
    execution_report: Optional[str] = None


class MarketDataRequest(BaseModel):
    """Market data subscription request."""

    symbols: List[str]
    subscribe: bool = True


class StatusResponse(BaseModel):
    """Service status response."""

    status: str
    connected: bool
    account_id: Optional[str] = None
    timestamp: str
    uptime_seconds: float


class FXCMBridgeService:
    """FXCM Bridge Service implementation."""

    def __init__(self):
        self.client: Optional[Any] = None
        self.connected: bool = False
        self.account_id: Optional[str] = None
        self.start_time: float = time.time()
        self.active_orders: Dict[str, Dict[str, Any]] = {}
        self.market_data_subscriptions: set = set()
        self._shutdown_event = asyncio.Event()

    async def startup(self) -> None:
        """Initialize service on startup."""
        logger.info("Starting FXCM Bridge Service")

        # Connect to FXCM
        if FOREXCONNECT_AVAILABLE:
            await self.connect_to_fxcm()
        else:
            logger.warning("Running in mock mode - ForexConnect not available")
            self.connected = True
            self.account_id = "MOCK_ACCOUNT"

    async def shutdown(self) -> None:
        """Cleanup on shutdown."""
        logger.info("Shutting down FXCM Bridge Service")

        if self.client and FOREXCONNECT_AVAILABLE:
            try:
                self.client.logout()
            except Exception as e:
                logger.error(f"Error during logout: {e}")

        self.connected = False
        self._shutdown_event.set()

    async def connect_to_fxcm(self) -> None:
        """Connect to FXCM using ForexConnect."""
        for attempt in range(BridgeConfig.RECONNECT_ATTEMPTS):
            try:
                logger.info(f"Attempting to connect to FXCM (attempt {attempt + 1})")

                # Create ForexConnect client
                self.client = fx.ForexConnectClient(
                    BridgeConfig.FXCM_USERNAME,
                    BridgeConfig.FXCM_PASSWORD,
                    BridgeConfig.FXCM_CONNECTION,
                    BridgeConfig.FXCM_URL,
                )

                # Connect
                self.client.connect()

                # Get account info
                accounts = self.client.get_accounts()
                if accounts:
                    self.account_id = accounts[0].account_id
                    logger.info(f"Connected to FXCM account: {self.account_id}")

                self.connected = True

                # Start monitoring tasks
                asyncio.create_task(self._monitor_connection())
                asyncio.create_task(self._process_executions())

                return

            except Exception as e:
                logger.error(f"Connection attempt {attempt + 1} failed: {e}")
                if attempt < BridgeConfig.RECONNECT_ATTEMPTS - 1:
                    await asyncio.sleep(BridgeConfig.RECONNECT_DELAY)

        raise Exception("Failed to connect to FXCM after all attempts")

    async def _monitor_connection(self) -> None:
        """Monitor connection health and reconnect if needed."""
        while not self._shutdown_event.is_set():
            try:
                if self.connected and self.client:
                    # Check connection health
                    if not self.client.is_connected():
                        logger.warning("Connection lost - attempting reconnect")
                        self.connected = False
                        await self.connect_to_fxcm()

                await asyncio.sleep(BridgeConfig.HEARTBEAT_INTERVAL)

            except Exception as e:
                logger.error(f"Error in connection monitor: {e}")
                await asyncio.sleep(BridgeConfig.HEARTBEAT_INTERVAL)

    async def _process_executions(self) -> None:
        """Process execution updates from FXCM."""
        while not self._shutdown_event.is_set():
            try:
                if self.connected and self.client:
                    # Check for order updates
                    trades = self.client.get_trades()

                    for trade in trades:
                        trade_id = trade.trade_id
                        if trade_id in self.active_orders:
                            # Update order status
                            order_info = self.active_orders[trade_id]
                            order_info["status"] = trade.status
                            order_info["filled_amount"] = trade.amount
                            order_info["avg_rate"] = trade.rate

                await asyncio.sleep(1)  # Check every second

            except Exception as e:
                logger.error(f"Error processing executions: {e}")
                await asyncio.sleep(5)

    async def submit_order(self, fix_message: str) -> OrderResponse:
        """Submit order to FXCM.

        Args:
            fix_message: FIX format order message.

        Returns:
            Order submission response.
        """
        try:
            # Parse FIX message
            fix_fields = FXCMFIXTranslator.parse_fix_order(fix_message)
            cl_ord_id = fix_fields.get("11", "")

            # Convert to ForexConnect format
            fc_order = FXCMFIXTranslator.fix_to_forexconnect_order(fix_fields)

            if not self.connected:
                return OrderResponse(success=False, message="Not connected to FXCM")

            if FOREXCONNECT_AVAILABLE and self.client:
                # Submit order to FXCM
                logger.info(f"Submitting order to FXCM: {fc_order}")

                # Open position based on order type
                if fc_order["order_type"] == "M":  # Market order
                    trade = self.client.open_position(
                        fc_order["instrument"], fc_order["side"], fc_order["amount"]
                    )
                else:
                    # Limit/Stop orders
                    trade = self.client.create_order(
                        fc_order["instrument"],
                        fc_order["side"],
                        fc_order["amount"],
                        fc_order.get("rate"),
                        fc_order.get("stop"),
                        fc_order["order_type"],
                    )

                # Store order info
                trade_id = trade.trade_id
                self.active_orders[trade_id] = {
                    "cl_ord_id": cl_ord_id,
                    "trade": trade,
                    "fc_order": fc_order,
                    "status": "Executing",
                    "timestamp": datetime.utcnow(),
                }

                # Create initial execution report
                exec_report = FXCMFIXTranslator.forexconnect_to_fix_execution_report(
                    fc_order,
                    {
                        "order_id": trade_id,
                        "trade_id": trade_id,
                        "status": "Executing",
                        "instrument": fc_order["instrument"],
                        "side": fc_order["side"],
                        "amount": fc_order["amount"],
                        "rate": fc_order.get("rate", 0),
                        "filled_amount": 0,
                        "avg_rate": 0,
                    },
                    cl_ord_id,
                )

                return OrderResponse(
                    success=True,
                    order_id=trade_id,
                    message="Order submitted successfully",
                    execution_report=exec_report,
                )

            else:
                # Mock mode
                mock_order_id = f"MOCK_{int(time.time() * 1000)}"

                exec_report = FXCMFIXTranslator.forexconnect_to_fix_execution_report(
                    fc_order,
                    {
                        "order_id": mock_order_id,
                        "trade_id": mock_order_id,
                        "status": "Executing",
                        "instrument": fc_order["instrument"],
                        "side": fc_order["side"],
                        "amount": fc_order["amount"],
                        "rate": fc_order.get("rate", 1.1000),
                        "filled_amount": 0,
                        "avg_rate": 0,
                    },
                    cl_ord_id,
                )

                return OrderResponse(
                    success=True,
                    order_id=mock_order_id,
                    message="Order submitted (mock mode)",
                    execution_report=exec_report,
                )

        except Exception as e:
            logger.error(f"Error submitting order: {e}")
            return OrderResponse(success=False, message=str(e))

    async def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """Cancel order on FXCM.

        Args:
            order_id: Order ID to cancel.

        Returns:
            Cancellation result.
        """
        try:
            if order_id not in self.active_orders:
                return {"success": False, "message": "Order not found"}

            if FOREXCONNECT_AVAILABLE and self.client:
                # Close position
                self.client.close_position(order_id)

                # Update order status
                order_info = self.active_orders[order_id]
                order_info["status"] = "Canceled"

                return {"success": True, "message": "Order canceled successfully"}
            else:
                # Mock mode
                if order_id in self.active_orders:
                    self.active_orders[order_id]["status"] = "Canceled"

                return {"success": True, "message": "Order canceled (mock mode)"}

        except Exception as e:
            logger.error(f"Error canceling order: {e}")
            return {"success": False, "message": str(e)}

    async def subscribe_market_data(self, symbols: List[str]) -> Dict[str, Any]:
        """Subscribe to market data.

        Args:
            symbols: List of symbols to subscribe to.

        Returns:
            Subscription result.
        """
        try:
            for symbol in symbols:
                normalized = FXCMFIXTranslator._normalize_symbol(symbol)
                self.market_data_subscriptions.add(normalized)

            logger.info(f"Subscribed to market data: {symbols}")

            return {
                "success": True,
                "subscribed_symbols": list(self.market_data_subscriptions),
            }

        except Exception as e:
            logger.error(f"Error subscribing to market data: {e}")
            return {"success": False, "message": str(e)}

    def get_status(self) -> StatusResponse:
        """Get service status.

        Returns:
            Current service status.
        """
        uptime = time.time() - self.start_time

        return StatusResponse(
            status="running" if self.connected else "disconnected",
            connected=self.connected,
            account_id=self.account_id,
            timestamp=datetime.utcnow().isoformat(),
            uptime_seconds=uptime,
        )


# Create service instance
bridge_service = FXCMBridgeService()


# FastAPI app with lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan."""
    # Startup
    await bridge_service.startup()
    yield
    # Shutdown
    await bridge_service.shutdown()


# Create FastAPI app
app = FastAPI(title="FXCM Bridge Service", version="1.0.0", lifespan=lifespan)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Security dependency
async def verify_api_key(api_key: Optional[str] = Header(None, alias="X-API-Key")):
    """Verify API key if configured."""
    if BridgeConfig.API_KEY:
        if api_key != BridgeConfig.API_KEY:
            raise HTTPException(status_code=401, detail="Invalid API key")


# API endpoints
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "connected": bridge_service.connected}


@app.get("/status", response_model=StatusResponse)
async def get_status(api_key: str = Depends(verify_api_key)):
    """Get detailed service status."""
    return bridge_service.get_status()


@app.post("/orders", response_model=OrderResponse)
async def submit_order(request: OrderRequest, api_key: str = Depends(verify_api_key)):
    """Submit order to FXCM."""
    return await bridge_service.submit_order(request.fix_message)


@app.delete("/orders/{order_id}")
async def cancel_order(order_id: str, api_key: str = Depends(verify_api_key)):
    """Cancel order on FXCM."""
    return await bridge_service.cancel_order(order_id)


@app.post("/market-data/subscribe")
async def subscribe_market_data(
    request: MarketDataRequest, api_key: str = Depends(verify_api_key)
):
    """Subscribe to market data."""
    return await bridge_service.subscribe_market_data(request.symbols)


@app.get("/orders/{order_id}")
async def get_order_status(order_id: str, api_key: str = Depends(verify_api_key)):
    """Get order status."""
    if order_id in bridge_service.active_orders:
        order_info = bridge_service.active_orders[order_id]
        return {
            "order_id": order_id,
            "cl_ord_id": order_info["cl_ord_id"],
            "status": order_info["status"],
            "timestamp": order_info["timestamp"].isoformat(),
        }
    else:
        raise HTTPException(status_code=404, detail="Order not found")


# Signal handlers
def signal_handler(sig, frame):
    """Handle shutdown signals."""
    logger.info(f"Received signal {sig}, shutting down...")
    sys.exit(0)


# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


# Main entry point
if __name__ == "__main__":
    logger.info(
        f"Starting FXCM Bridge Service on {BridgeConfig.HOST}:{BridgeConfig.PORT}"
    )

    uvicorn.run(
        app,
        host=BridgeConfig.HOST,
        port=BridgeConfig.PORT,
        log_config=None,  # Use our own logging config
    )
