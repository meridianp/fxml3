"""FXCM broker adapter implementation."""

import asyncio
import hashlib
import hmac
import json
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import aiohttp

from ..schemas.broker_messages import (
    AccountReport,
    BrokerCapabilities,
    BrokerError,
    BrokerStatus,
    BrokerType,
    CurrencyCode,
    ExecutionReport,
    ExecutionType,
    MarketDataRequest,
    MarketDataSnapshot,
    OrderCancelRequest,
    OrderModifyRequest,
    OrderRequest,
    OrderResponse,
    OrderSide,
    OrderStatus,
    OrderType,
    PositionReport,
    TimeInForce,
)
from .base_broker_adapter import (
    BaseBrokerAdapter,
    BrokerAuthenticationError,
    BrokerConnectionError,
    BrokerOrderError,
)


class FXCMAdapter(BaseBrokerAdapter):
    """FXCM broker adapter implementation.

    FXCM provides REST API access for forex trading with support for
    major currency pairs, CFDs, and indices.
    """

    def __init__(self, broker_type: BrokerType, config: Dict[str, Any]):
        super().__init__(broker_type, config)

        # FXCM API configuration
        self.api_url = config.get("api_url", "https://api-demo.fxcm.com")
        self.token = config.get("token", "")
        self.environment = config.get("environment", "demo")  # 'demo' or 'real'

        # Session management
        self.session: Optional[aiohttp.ClientSession] = None
        self.socket_id: Optional[str] = None

        # Rate limiting (FXCM limits: 50 requests per second)
        self.rate_limit_per_second = 50
        self.last_request_times: List[datetime] = []

        # Symbol mapping (FXCM uses different symbol format)
        self.symbol_map = {
            "EURUSD": "EUR/USD",
            "GBPUSD": "GBP/USD",
            "USDJPY": "USD/JPY",
            "USDCHF": "USD/CHF",
            "AUDUSD": "AUD/USD",
            "USDCAD": "USD/CAD",
            "NZDUSD": "NZD/USD",
            "EURGBP": "EUR/GBP",
            "EURJPY": "EUR/JPY",
            "GBPJPY": "GBP/JPY",
        }

        # Reverse symbol mapping
        self.reverse_symbol_map = {v: k for k, v in self.symbol_map.items()}

        # Market data cache
        self.market_data_cache: Dict[str, MarketDataSnapshot] = {}
        self.cache_expiry = timedelta(seconds=1)  # 1 second cache

    async def _broker_specific_initialization(self):
        """FXCM-specific initialization."""
        # Create HTTP session with appropriate headers
        self.session = aiohttp.ClientSession(
            headers={
                "User-Agent": "FXML4/1.0",
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
            }
        )

    async def connect(self) -> bool:
        """Connect to FXCM API."""
        try:
            self.logger.info(f"Connecting to FXCM API at {self.api_url}")

            if not self.session:
                await self._broker_specific_initialization()

            # Test connection with a simple API call
            response = await self._make_request("GET", "/subscribe", authenticate=False)

            if response and "socketId" in response:
                self.socket_id = response["socketId"]
                self.connected = True
                self.connection_quality = "GOOD"

                self.logger.info(
                    f"Successfully connected to FXCM API (Socket ID: {self.socket_id})"
                )
                return True
            else:
                self.logger.error("Failed to connect to FXCM API")
                return False

        except Exception as e:
            self.logger.error(f"Error connecting to FXCM API: {e}")
            await self._emit_error(
                BrokerError(
                    broker_type=self.broker_type,
                    account_id=self.account_id or "unknown",
                    error_code="CONNECTION_FAILED",
                    error_message=str(e),
                    error_type="CONNECTION",
                )
            )
            return False

    async def disconnect(self) -> bool:
        """Disconnect from FXCM API."""
        try:
            if self.session:
                await self.session.close()
                self.session = None

            self.connected = False
            self.authenticated = False
            self.connection_quality = "DISCONNECTED"
            self.socket_id = None

            self.logger.info("Disconnected from FXCM API")
            return True

        except Exception as e:
            self.logger.error(f"Error disconnecting from FXCM API: {e}")
            return False

    async def authenticate(self, credentials: Dict[str, Any]) -> bool:
        """Authenticate with FXCM API."""
        try:
            # FXCM uses token-based authentication
            self.token = credentials.get("token", self.token)

            if not self.token:
                raise BrokerAuthenticationError("FXCM API token required")

            # Test authentication with account info request
            account_info = await self._make_request("GET", "/accounts")

            if account_info and "accounts" in account_info:
                self.authenticated = True
                # Use first account as default
                if account_info["accounts"]:
                    self.account_id = str(account_info["accounts"][0]["accountId"])

                self.logger.info(
                    f"Successfully authenticated with FXCM (Account: {self.account_id})"
                )
                return True
            else:
                self.logger.error("Failed to authenticate with FXCM")
                return False

        except Exception as e:
            self.logger.error(f"Error authenticating with FXCM: {e}")
            await self._emit_error(
                BrokerError(
                    broker_type=self.broker_type,
                    account_id=self.account_id or "unknown",
                    error_code="AUTH_FAILED",
                    error_message=str(e),
                    error_type="AUTHENTICATION",
                )
            )
            return False

    async def submit_order(self, order: OrderRequest) -> OrderResponse:
        """Submit an order to FXCM."""
        try:
            # Validate order
            if not self._validate_order(order):
                raise BrokerOrderError("Order validation failed")

            # Check rate limits
            if not await self._check_fxcm_rate_limits():
                raise BrokerOrderError("Rate limit exceeded")

            # Convert symbol format
            fxcm_symbol = self.symbol_map.get(order.symbol, order.symbol)

            # Build order parameters
            params = {
                "account_id": self.account_id,
                "symbol": fxcm_symbol,
                "is_buy": str(order.side == OrderSide.BUY).lower(),
                "amount": int(order.quantity),  # FXCM uses integer lot sizes
                "time_in_force": self._convert_time_in_force(order.time_in_force),
                "order_type": self._convert_order_type(order.order_type),
                "at_market": "0",  # Default to not at market
            }

            # Add price parameters based on order type
            if order.order_type == OrderType.MARKET:
                params["at_market"] = "1"
            elif order.order_type == OrderType.LIMIT:
                params["rate"] = float(order.price)
                params["is_in_pips"] = "false"
            elif order.order_type == OrderType.STOP:
                params["rate"] = float(order.stop_price)
                params["is_in_pips"] = "false"
            elif order.order_type == OrderType.STOP_LIMIT:
                params["rate"] = float(order.price)
                params["stop"] = float(order.stop_price)
                params["is_in_pips"] = "false"

            # Submit order
            response = await self._make_request("POST", "/orders", data=params)

            if response and "orderId" in response:
                # Store order mapping
                broker_order_id = str(response["orderId"])
                self.client_to_broker_orders[order.client_order_id] = broker_order_id
                self.broker_to_client_orders[broker_order_id] = order.client_order_id
                self.active_orders[order.client_order_id] = order

                # Create response
                order_response = OrderResponse(
                    broker_type=self.broker_type,
                    account_id=self.account_id,
                    client_order_id=order.client_order_id,
                    broker_order_id=broker_order_id,
                    status=OrderStatus.SUBMITTED,
                    success=True,
                    symbol=order.symbol,
                    side=order.side,
                    quantity=order.quantity,
                    order_time=datetime.utcnow(),
                    acknowledged_time=datetime.utcnow(),
                )

                # Update order status
                self._update_order_status(order.client_order_id, OrderStatus.SUBMITTED)

                # Emit response
                await self._emit_message(order_response)

                self.logger.info(
                    f"Order submitted to FXCM: {order.client_order_id} -> {broker_order_id}"
                )

                return order_response
            else:
                raise BrokerOrderError("Failed to submit order - no order ID returned")

        except Exception as e:
            self.logger.error(f"Error submitting order to FXCM: {e}")

            # Create error response
            error_response = OrderResponse(
                broker_type=self.broker_type,
                account_id=self.account_id,
                client_order_id=order.client_order_id,
                status=OrderStatus.REJECTED,
                success=False,
                error_code="ORDER_SUBMIT_FAILED",
                error_message=str(e),
                symbol=order.symbol,
                side=order.side,
                quantity=order.quantity,
            )

            await self._emit_message(error_response)
            raise BrokerOrderError(f"Failed to submit order: {e}")

    async def cancel_order(self, cancel_request: OrderCancelRequest) -> OrderResponse:
        """Cancel an order in FXCM."""
        try:
            client_order_id = cancel_request.client_order_id

            # Get broker order ID
            broker_order_id = self.client_to_broker_orders.get(client_order_id)
            if not broker_order_id:
                raise BrokerOrderError(f"Order not found: {client_order_id}")

            # Check rate limits
            if not await self._check_fxcm_rate_limits():
                raise BrokerOrderError("Rate limit exceeded")

            # Cancel order
            params = {"order_id": broker_order_id, "account_id": self.account_id}

            response = await self._make_request(
                "DELETE", f"/orders/{broker_order_id}", data=params
            )

            if response:
                # Create response
                order_response = OrderResponse(
                    broker_type=self.broker_type,
                    account_id=self.account_id,
                    client_order_id=client_order_id,
                    broker_order_id=broker_order_id,
                    status=OrderStatus.CANCELLED,
                    success=True,
                    symbol=cancel_request.symbol,
                    side=OrderSide.BUY,  # Would need to get from stored order
                    quantity=Decimal("0"),  # Would need to get from stored order
                )

                # Update order status
                self._update_order_status(client_order_id, OrderStatus.CANCELLED)

                # Emit response
                await self._emit_message(order_response)

                self.logger.info(f"Order cancelled in FXCM: {client_order_id}")

                return order_response
            else:
                raise BrokerOrderError("Failed to cancel order")

        except Exception as e:
            self.logger.error(f"Error cancelling order in FXCM: {e}")
            raise BrokerOrderError(f"Failed to cancel order: {e}")

    async def modify_order(self, modify_request: OrderModifyRequest) -> OrderResponse:
        """Modify an order in FXCM."""
        try:
            client_order_id = modify_request.client_order_id

            # Get broker order ID
            broker_order_id = self.client_to_broker_orders.get(client_order_id)
            if not broker_order_id:
                raise BrokerOrderError(f"Order not found: {client_order_id}")

            # Check rate limits
            if not await self._check_fxcm_rate_limits():
                raise BrokerOrderError("Rate limit exceeded")

            # Build modification parameters
            params = {"order_id": broker_order_id, "account_id": self.account_id}

            if modify_request.new_quantity:
                params["amount"] = int(modify_request.new_quantity)

            if modify_request.new_price:
                params["rate"] = float(modify_request.new_price)
                params["is_in_pips"] = "false"

            if modify_request.new_stop_price:
                params["stop"] = float(modify_request.new_stop_price)
                params["is_in_pips"] = "false"

            # Modify order
            response = await self._make_request(
                "PUT", f"/orders/{broker_order_id}", data=params
            )

            if response:
                # Get original order
                original_order = self.active_orders.get(client_order_id)

                # Create response
                order_response = OrderResponse(
                    broker_type=self.broker_type,
                    account_id=self.account_id,
                    client_order_id=client_order_id,
                    broker_order_id=broker_order_id,
                    status=OrderStatus.WORKING,
                    success=True,
                    symbol=(
                        original_order.symbol
                        if original_order
                        else modify_request.symbol
                    ),
                    side=original_order.side if original_order else OrderSide.BUY,
                    quantity=modify_request.new_quantity
                    or (original_order.quantity if original_order else Decimal("0")),
                )

                # Emit response
                await self._emit_message(order_response)

                self.logger.info(f"Order modified in FXCM: {client_order_id}")

                return order_response
            else:
                raise BrokerOrderError("Failed to modify order")

        except Exception as e:
            self.logger.error(f"Error modifying order in FXCM: {e}")
            raise BrokerOrderError(f"Failed to modify order: {e}")

    async def get_account_info(self) -> AccountReport:
        """Get account information from FXCM."""
        try:
            # Get account summary
            response = await self._make_request("GET", f"/accounts/{self.account_id}")

            if response:
                # Convert to standard format
                account_report = AccountReport(
                    broker_type=self.broker_type,
                    account_id=self.account_id,
                    account_value=Decimal(str(response.get("equity", 0))),
                    cash_balance=Decimal(str(response.get("balance", 0))),
                    equity=Decimal(str(response.get("equity", 0))),
                    buying_power=Decimal(str(response.get("usableMargin", 0))),
                    initial_margin=Decimal(
                        "0"
                    ),  # FXCM doesn't separate initial/maintenance
                    maintenance_margin=Decimal(str(response.get("usdMr", 0))),
                    available_margin=Decimal(str(response.get("usableMargin", 0))),
                    unrealized_pnl=Decimal(str(response.get("grossPL", 0))),
                    realized_pnl=Decimal("0"),  # Not provided in single call
                    base_currency=CurrencyCode.USD,
                )

                # Update internal account info
                self._update_account_info(account_report)

                return account_report
            else:
                raise Exception("Failed to get account info")

        except Exception as e:
            self.logger.error(f"Error getting account info from FXCM: {e}")
            raise

    async def get_positions(self) -> List[PositionReport]:
        """Get positions from FXCM."""
        try:
            # Get open positions
            response = await self._make_request(
                "GET", "/accounts/accountId/open-positions"
            )

            positions = []
            if response and "data" in response:
                for pos in response["data"]:
                    # Convert symbol back to standard format
                    symbol = self.reverse_symbol_map.get(
                        pos.get("currency", ""), pos.get("currency", "")
                    )

                    position = PositionReport(
                        broker_type=self.broker_type,
                        account_id=self.account_id,
                        symbol=symbol,
                        position_size=Decimal(str(pos.get("amountK", 0)))
                        * Decimal("1000"),
                        average_price=Decimal(str(pos.get("open", 0))),
                        market_price=Decimal(str(pos.get("close", 0))),
                        unrealized_pnl=Decimal(str(pos.get("grossPL", 0))),
                        realized_pnl=Decimal("0"),
                        currency=CurrencyCode.USD,
                    )

                    positions.append(position)
                    self._update_position(position)

            return positions

        except Exception as e:
            self.logger.error(f"Error getting positions from FXCM: {e}")
            return []

    async def get_open_orders(self) -> List[OrderResponse]:
        """Get open orders from FXCM."""
        try:
            # Get open orders
            response = await self._make_request("GET", "/accounts/accountId/orders")

            open_orders = []
            if response and "data" in response:
                for order in response["data"]:
                    broker_order_id = str(order.get("orderId", ""))
                    client_order_id = self.broker_to_client_orders.get(
                        broker_order_id, broker_order_id
                    )

                    # Convert symbol back to standard format
                    symbol = self.reverse_symbol_map.get(
                        order.get("currency", ""), order.get("currency", "")
                    )

                    order_response = OrderResponse(
                        broker_type=self.broker_type,
                        account_id=self.account_id,
                        client_order_id=client_order_id,
                        broker_order_id=broker_order_id,
                        status=self._convert_fxcm_status(order.get("status", "")),
                        success=True,
                        symbol=symbol,
                        side=(
                            OrderSide.BUY
                            if order.get("isBuy", True)
                            else OrderSide.SELL
                        ),
                        quantity=Decimal(str(order.get("amountK", 0)))
                        * Decimal("1000"),
                        filled_quantity=Decimal("0"),
                        remaining_quantity=Decimal(str(order.get("amountK", 0)))
                        * Decimal("1000"),
                    )

                    open_orders.append(order_response)

            return open_orders

        except Exception as e:
            self.logger.error(f"Error getting open orders from FXCM: {e}")
            return []

    async def subscribe_market_data(self, request: MarketDataRequest) -> bool:
        """Subscribe to market data from FXCM."""
        try:
            # FXCM provides market data through their streaming API
            # For REST API, we'll use polling approach

            for symbol in request.symbols:
                # Store subscription request
                self.market_data_subscriptions[symbol] = request.request_id

            self.logger.info(f"Subscribed to market data for: {request.symbols}")
            return True

        except Exception as e:
            self.logger.error(f"Error subscribing to market data: {e}")
            return False

    async def unsubscribe_market_data(self, request_id: str) -> bool:
        """Unsubscribe from market data."""
        try:
            # Remove subscriptions with matching request ID
            symbols_to_remove = [
                symbol
                for symbol, req_id in self.market_data_subscriptions.items()
                if req_id == request_id
            ]

            for symbol in symbols_to_remove:
                self.market_data_subscriptions.pop(symbol, None)

            return True

        except Exception as e:
            self.logger.error(f"Error unsubscribing from market data: {e}")
            return False

    async def get_market_data_snapshot(
        self, symbol: str
    ) -> Optional[MarketDataSnapshot]:
        """Get market data snapshot from FXCM."""
        try:
            # Check cache first
            if symbol in self.market_data_cache:
                cached_data = self.market_data_cache[symbol]
                if datetime.utcnow() - cached_data.market_time < self.cache_expiry:
                    return cached_data

            # Convert symbol format
            fxcm_symbol = self.symbol_map.get(symbol, symbol)

            # Get market data
            response = await self._make_request(
                "GET", f"/subscribe", params={"pairs": fxcm_symbol}
            )

            if response and "offers" in response:
                for offer in response["offers"]:
                    if offer.get("instrument") == fxcm_symbol:
                        snapshot = MarketDataSnapshot(
                            broker_type=self.broker_type,
                            account_id=self.account_id,
                            symbol=symbol,
                            bid_price=Decimal(str(offer.get("bid", 0))),
                            ask_price=Decimal(str(offer.get("ask", 0))),
                            last_price=Decimal(
                                str((offer.get("bid", 0) + offer.get("ask", 0)) / 2)
                            ),
                            bid_size=Decimal("1000000"),  # FXCM doesn't provide size
                            ask_size=Decimal("1000000"),
                            volume=Decimal(str(offer.get("volume", 0))),
                            market_time=datetime.utcnow(),
                        )

                        # Cache the data
                        self.market_data_cache[symbol] = snapshot

                        return snapshot

            return None

        except Exception as e:
            self.logger.error(f"Error getting market data snapshot: {e}")
            return None

    def get_capabilities(self) -> BrokerCapabilities:
        """Get FXCM capabilities."""
        return BrokerCapabilities(
            broker_type=self.broker_type,
            supported_order_types=[
                OrderType.MARKET,
                OrderType.LIMIT,
                OrderType.STOP,
                OrderType.STOP_LIMIT,
            ],
            supported_time_in_force=[
                TimeInForce.GTC,
                TimeInForce.IOC,
                TimeInForce.FOK,
                TimeInForce.DAY,
            ],
            supported_symbols=list(self.symbol_map.keys()),
            min_order_size={
                "EURUSD": Decimal("1000"),  # 0.01 lots
                "GBPUSD": Decimal("1000"),
                "USDJPY": Decimal("1000"),
                "USDCHF": Decimal("1000"),
                "AUDUSD": Decimal("1000"),
                "USDCAD": Decimal("1000"),
                "NZDUSD": Decimal("1000"),
            },
            max_order_size={
                "EURUSD": Decimal("50000000"),  # 500 lots
                "GBPUSD": Decimal("50000000"),
                "USDJPY": Decimal("50000000"),
                "USDCHF": Decimal("50000000"),
                "AUDUSD": Decimal("50000000"),
                "USDCAD": Decimal("50000000"),
                "NZDUSD": Decimal("50000000"),
            },
            max_orders_per_second=50,
            max_orders_per_minute=2000,
            provides_market_data=True,
            real_time_data=True,
            historical_data=True,
            trading_sessions=[
                {
                    "name": "FOREX_MAIN",
                    "start_time": "17:00:00",
                    "end_time": "17:00:00",
                    "timezone": "America/New_York",
                    "days": ["MON", "TUE", "WED", "THU", "FRI"],
                }
            ],
            commission_structure={
                "FOREX": {
                    "type": "SPREAD",
                    "rate": 0.0,  # Commission included in spread
                    "currency": "USD",
                    "minimum": 0.0,
                }
            },
        )

    # Helper methods

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None,
        authenticate: bool = True,
    ) -> Optional[Dict]:
        """Make HTTP request to FXCM API."""
        if not self.session:
            raise BrokerConnectionError("Not connected to FXCM API")

        url = f"{self.api_url}{endpoint}"

        headers = {}
        if authenticate and self.token:
            headers["Authorization"] = f"Bearer {self.token}"
            headers["User-Agent"] = "FXML4/1.0"
            headers["Accept"] = "application/json"

        try:
            async with self.session.request(
                method, url, data=data, params=params, headers=headers
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error_text = await response.text()
                    self.logger.error(
                        f"FXCM API error: {response.status} - {error_text}"
                    )
                    return None

        except Exception as e:
            self.logger.error(f"Error making request to FXCM API: {e}")
            return None

    async def _check_fxcm_rate_limits(self) -> bool:
        """Check FXCM-specific rate limits."""
        current_time = datetime.utcnow()

        # Remove requests older than 1 second
        self.last_request_times = [
            t for t in self.last_request_times if (current_time - t).total_seconds() < 1
        ]

        # Check if we're within rate limit
        if len(self.last_request_times) >= self.rate_limit_per_second:
            return False

        # Add current request time
        self.last_request_times.append(current_time)

        return True

    def _convert_order_type(self, order_type: OrderType) -> str:
        """Convert standard order type to FXCM format."""
        mapping = {
            OrderType.MARKET: "AtMarket",
            OrderType.LIMIT: "Entry",
            OrderType.STOP: "Entry",
            OrderType.STOP_LIMIT: "Entry",
        }
        return mapping.get(order_type, "AtMarket")

    def _convert_time_in_force(self, tif: TimeInForce) -> str:
        """Convert standard time in force to FXCM format."""
        mapping = {
            TimeInForce.GTC: "GTC",
            TimeInForce.IOC: "IOC",
            TimeInForce.FOK: "FOK",
            TimeInForce.DAY: "DAY",
        }
        return mapping.get(tif, "GTC")

    def _convert_fxcm_status(self, fxcm_status: str) -> OrderStatus:
        """Convert FXCM order status to standard format."""
        mapping = {
            "Waiting": OrderStatus.PENDING,
            "InProcess": OrderStatus.WORKING,
            "Executed": OrderStatus.FILLED,
            "Canceled": OrderStatus.CANCELLED,
            "Rejected": OrderStatus.REJECTED,
            "Expired": OrderStatus.EXPIRED,
        }
        return mapping.get(fxcm_status, OrderStatus.PENDING)

    async def _broker_health_check(self) -> Dict[str, Any]:
        """FXCM-specific health check."""
        health = {
            "api_url": self.api_url,
            "environment": self.environment,
            "socket_connected": self.socket_id is not None,
            "rate_limit_usage": len(self.last_request_times),
            "cache_size": len(self.market_data_cache),
        }

        # Check API health
        try:
            response = await self._make_request("GET", "/subscribe", authenticate=False)
            health["api_responsive"] = response is not None
        except:
            health["api_responsive"] = False

        return health

    async def cleanup(self):
        """Clean up resources before shutdown."""
        try:
            # Clear cache
            self.market_data_cache.clear()

            # Close session
            if self.session:
                await self.session.close()

            # Call parent cleanup
            await super().cleanup()

        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")


# Register the adapter
from .base_broker_adapter import BrokerAdapterFactory

BrokerAdapterFactory.register_adapter(BrokerType.FXCM, FXCMAdapter)
