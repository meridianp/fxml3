"""Oanda broker adapter implementation."""

import asyncio
import json
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, AsyncGenerator, Dict, List, Optional
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


class OandaAdapter(BaseBrokerAdapter):
    """Oanda broker adapter implementation.

    Oanda provides v20 REST API for forex and CFD trading with
    fractional pip pricing and net position model.
    """

    def __init__(self, broker_type: BrokerType, config: Dict[str, Any]):
        super().__init__(broker_type, config)

        # Oanda API configuration
        self.environment = config.get("environment", "practice")  # 'practice', 'live'
        self.api_url = self._get_api_url(self.environment)
        self.stream_url = self._get_stream_url(self.environment)
        self.access_token = config.get("access_token", "")

        # Session management
        self.session: Optional[aiohttp.ClientSession] = None
        self.stream_session: Optional[aiohttp.ClientSession] = None

        # Streaming connections
        self.price_stream: Optional[AsyncGenerator] = None
        self.transaction_stream: Optional[AsyncGenerator] = None

        # Rate limiting (Oanda limits: 120 requests per second)
        self.rate_limit_per_second = 120
        self.last_request_times: List[datetime] = []

        # Oanda uses net positions (aggregated by symbol)
        self.net_positions: Dict[str, PositionReport] = {}

        # Oanda-specific settings
        self.units_precision = {
            "EURUSD": 5,
            "GBPUSD": 5,
            "USDJPY": 3,
            "USDCHF": 5,
            "AUDUSD": 5,
            "USDCAD": 5,
            "NZDUSD": 5,
        }

        # Price streaming cache
        self.latest_prices: Dict[str, MarketDataSnapshot] = {}
        self.price_stream_active = False

    def _get_api_url(self, environment: str) -> str:
        """Get API URL based on environment."""
        if environment == "live":
            return "https://api-fxtrade.oanda.com/v3"
        else:
            return "https://api-fxpractice.oanda.com/v3"

    def _get_stream_url(self, environment: str) -> str:
        """Get streaming URL based on environment."""
        if environment == "live":
            return "https://stream-fxtrade.oanda.com/v3"
        else:
            return "https://stream-fxpractice.oanda.com/v3"

    async def _broker_specific_initialization(self):
        """Oanda-specific initialization."""
        # Create HTTP sessions with appropriate headers
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        self.session = aiohttp.ClientSession(headers=headers)
        self.stream_session = aiohttp.ClientSession(headers=headers)

    async def connect(self) -> bool:
        """Connect to Oanda v20 API."""
        try:
            self.logger.info(f"Connecting to Oanda API ({self.environment})")

            if not self.session:
                await self._broker_specific_initialization()

            # Test connection with account request
            accounts = await self._make_request("GET", "/accounts")

            if accounts and "accounts" in accounts:
                # Use first account as default
                if accounts["accounts"]:
                    self.account_id = accounts["accounts"][0]["id"]

                self.connected = True
                self.connection_quality = "EXCELLENT"

                self.logger.info(
                    f"Successfully connected to Oanda API (Account: {self.account_id})"
                )
                return True
            else:
                self.logger.error("Failed to connect to Oanda API")
                return False

        except Exception as e:
            self.logger.error(f"Error connecting to Oanda API: {e}")
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
        """Disconnect from Oanda API."""
        try:
            # Stop streaming
            self.price_stream_active = False

            # Close sessions
            if self.session:
                await self.session.close()
                self.session = None

            if self.stream_session:
                await self.stream_session.close()
                self.stream_session = None

            self.connected = False
            self.authenticated = False
            self.connection_quality = "DISCONNECTED"

            self.logger.info("Disconnected from Oanda API")
            return True

        except Exception as e:
            self.logger.error(f"Error disconnecting from Oanda API: {e}")
            return False

    async def authenticate(self, credentials: Dict[str, Any]) -> bool:
        """Authenticate with Oanda API."""
        try:
            # Oanda uses token-based authentication
            self.access_token = credentials.get("access_token", self.access_token)

            if not self.access_token:
                raise BrokerAuthenticationError("Oanda access token required")

            # Update headers with new token
            if self.session:
                self.session.headers.update(
                    {"Authorization": f"Bearer {self.access_token}"}
                )

            # Test authentication with account info
            account_info = await self._make_request(
                "GET", f"/accounts/{self.account_id}"
            )

            if account_info and "account" in account_info:
                self.authenticated = True
                self.logger.info(f"Successfully authenticated with Oanda")
                return True
            else:
                self.logger.error("Failed to authenticate with Oanda")
                return False

        except Exception as e:
            self.logger.error(f"Error authenticating with Oanda: {e}")
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
        """Submit an order to Oanda."""
        try:
            # Validate order
            if not self._validate_order(order):
                raise BrokerOrderError("Order validation failed")

            # Check rate limits
            if not await self._check_oanda_rate_limits():
                raise BrokerOrderError("Rate limit exceeded")

            # Convert to Oanda instrument format
            instrument = self._format_instrument(order.symbol)

            # Calculate units (positive for buy, negative for sell)
            units = int(order.quantity)
            if order.side == OrderSide.SELL:
                units = -units

            # Build order data based on order type
            order_data = {
                "order": {
                    "instrument": instrument,
                    "units": str(units),
                    "timeInForce": self._convert_time_in_force(order.time_in_force),
                    "positionFill": "DEFAULT",
                }
            }

            # Add order type specific fields
            if order.order_type == OrderType.MARKET:
                order_data["order"]["type"] = "MARKET"

            elif order.order_type == OrderType.LIMIT:
                order_data["order"]["type"] = "LIMIT"
                order_data["order"]["price"] = str(order.price)

            elif order.order_type == OrderType.STOP:
                order_data["order"]["type"] = "STOP"
                order_data["order"]["price"] = str(order.stop_price)

            elif order.order_type == OrderType.STOP_LIMIT:
                # Oanda doesn't have STOP_LIMIT, use LIMIT with stop loss
                order_data["order"]["type"] = "LIMIT"
                order_data["order"]["price"] = str(order.price)
                order_data["order"]["stopLossOnFill"] = {"price": str(order.stop_price)}

            # Add client extensions for tracking
            order_data["order"]["clientExtensions"] = {
                "id": order.client_order_id,
                "comment": (
                    f"FXML4_{order.correlation_id}" if order.correlation_id else "FXML4"
                ),
            }

            # Submit order
            response = await self._make_request(
                "POST", f"/accounts/{self.account_id}/orders", json=order_data
            )

            if response and "orderCreateTransaction" in response:
                transaction = response["orderCreateTransaction"]
                broker_order_id = str(transaction.get("id", ""))

                # Store order mapping
                self.client_to_broker_orders[order.client_order_id] = broker_order_id
                self.broker_to_client_orders[broker_order_id] = order.client_order_id
                self.active_orders[order.client_order_id] = order

                # Determine status
                if "orderFillTransaction" in response:
                    status = OrderStatus.FILLED
                else:
                    status = OrderStatus.SUBMITTED

                # Create response
                order_response = OrderResponse(
                    broker_type=self.broker_type,
                    account_id=self.account_id,
                    client_order_id=order.client_order_id,
                    broker_order_id=broker_order_id,
                    status=status,
                    success=True,
                    symbol=order.symbol,
                    side=order.side,
                    quantity=order.quantity,
                    order_time=datetime.utcnow(),
                    acknowledged_time=datetime.utcnow(),
                )

                # Add fill information if order was filled
                if "orderFillTransaction" in response:
                    fill = response["orderFillTransaction"]
                    order_response.filled_quantity = abs(
                        Decimal(fill.get("units", "0"))
                    )
                    order_response.average_fill_price = Decimal(fill.get("price", "0"))
                    order_response.remaining_quantity = Decimal("0")

                # Update order status
                self._update_order_status(order.client_order_id, status)

                # Emit response
                await self._emit_message(order_response)

                self.logger.info(
                    f"Order submitted to Oanda: {order.client_order_id} -> {broker_order_id}"
                )

                return order_response
            else:
                error_msg = (
                    response.get("errorMessage", "Unknown error")
                    if response
                    else "No response"
                )
                raise BrokerOrderError(f"Failed to submit order: {error_msg}")

        except Exception as e:
            self.logger.error(f"Error submitting order to Oanda: {e}")

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
        """Cancel an order in Oanda."""
        try:
            client_order_id = cancel_request.client_order_id

            # Get broker order ID
            broker_order_id = self.client_to_broker_orders.get(client_order_id)
            if not broker_order_id:
                raise BrokerOrderError(f"Order not found: {client_order_id}")

            # Check rate limits
            if not await self._check_oanda_rate_limits():
                raise BrokerOrderError("Rate limit exceeded")

            # Cancel order
            response = await self._make_request(
                "PUT", f"/accounts/{self.account_id}/orders/{broker_order_id}/cancel"
            )

            if response and "orderCancelTransaction" in response:
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

                self.logger.info(f"Order cancelled in Oanda: {client_order_id}")

                return order_response
            else:
                error_msg = (
                    response.get("errorMessage", "Unknown error")
                    if response
                    else "No response"
                )
                raise BrokerOrderError(f"Failed to cancel order: {error_msg}")

        except Exception as e:
            self.logger.error(f"Error cancelling order in Oanda: {e}")
            raise BrokerOrderError(f"Failed to cancel order: {e}")

    async def modify_order(self, modify_request: OrderModifyRequest) -> OrderResponse:
        """Modify an order in Oanda."""
        try:
            client_order_id = modify_request.client_order_id

            # Get broker order ID
            broker_order_id = self.client_to_broker_orders.get(client_order_id)
            if not broker_order_id:
                raise BrokerOrderError(f"Order not found: {client_order_id}")

            # Check rate limits
            if not await self._check_oanda_rate_limits():
                raise BrokerOrderError("Rate limit exceeded")

            # Get original order
            original_order = self.active_orders.get(client_order_id)
            if not original_order:
                raise BrokerOrderError(f"Original order not found: {client_order_id}")

            # Oanda requires replacing the order
            # First cancel the existing order
            await self._make_request(
                "PUT", f"/accounts/{self.account_id}/orders/{broker_order_id}/cancel"
            )

            # Create new order with modifications
            new_order = OrderRequest(
                broker_type=self.broker_type,
                account_id=self.account_id,
                client_order_id=str(uuid.uuid4()),
                symbol=original_order.symbol,
                order_type=original_order.order_type,
                side=original_order.side,
                quantity=modify_request.new_quantity or original_order.quantity,
                price=modify_request.new_price or original_order.price,
                stop_price=modify_request.new_stop_price or original_order.stop_price,
                time_in_force=modify_request.new_time_in_force
                or original_order.time_in_force,
                correlation_id=modify_request.correlation_id,
            )

            # Submit new order
            response = await self.submit_order(new_order)

            self.logger.info(
                f"Order modified in Oanda: {client_order_id} -> {new_order.client_order_id}"
            )

            return response

        except Exception as e:
            self.logger.error(f"Error modifying order in Oanda: {e}")
            raise BrokerOrderError(f"Failed to modify order: {e}")

    async def get_account_info(self) -> AccountReport:
        """Get account information from Oanda."""
        try:
            # Get account summary
            response = await self._make_request(
                "GET", f"/accounts/{self.account_id}/summary"
            )

            if response and "account" in response:
                account = response["account"]

                # Convert to standard format
                account_report = AccountReport(
                    broker_type=self.broker_type,
                    account_id=self.account_id,
                    account_value=Decimal(account.get("NAV", "0")),
                    cash_balance=Decimal(account.get("balance", "0")),
                    equity=Decimal(account.get("NAV", "0")),
                    buying_power=Decimal(account.get("marginAvailable", "0")),
                    initial_margin=Decimal("0"),  # Oanda uses different margin model
                    maintenance_margin=Decimal(account.get("marginUsed", "0")),
                    available_margin=Decimal(account.get("marginAvailable", "0")),
                    unrealized_pnl=Decimal(account.get("unrealizedPL", "0")),
                    realized_pnl=Decimal(account.get("pl", "0")),
                    base_currency=CurrencyCode(account.get("currency", "USD")),
                )

                # Update internal account info
                self._update_account_info(account_report)

                return account_report
            else:
                raise Exception("Failed to get account info")

        except Exception as e:
            self.logger.error(f"Error getting account info from Oanda: {e}")
            raise

    async def get_positions(self) -> List[PositionReport]:
        """Get positions from Oanda."""
        try:
            # Get open positions
            response = await self._make_request(
                "GET", f"/accounts/{self.account_id}/positions"
            )

            positions = []
            if response and "positions" in response:
                for pos in response["positions"]:
                    instrument = pos.get("instrument", "")
                    symbol = self._convert_instrument_to_symbol(instrument)

                    # Oanda uses net positions
                    long_units = Decimal(pos.get("long", {}).get("units", "0"))
                    short_units = Decimal(pos.get("short", {}).get("units", "0"))
                    net_units = long_units + short_units  # Short units are negative

                    if net_units != 0:
                        # Calculate average price
                        if net_units > 0:
                            avg_price = Decimal(
                                pos.get("long", {}).get("averagePrice", "0")
                            )
                            unrealized_pnl = Decimal(
                                pos.get("long", {}).get("unrealizedPL", "0")
                            )
                        else:
                            avg_price = Decimal(
                                pos.get("short", {}).get("averagePrice", "0")
                            )
                            unrealized_pnl = Decimal(
                                pos.get("short", {}).get("unrealizedPL", "0")
                            )

                        position = PositionReport(
                            broker_type=self.broker_type,
                            account_id=self.account_id,
                            symbol=symbol,
                            position_size=net_units,
                            average_price=avg_price,
                            market_price=Decimal(
                                "0"
                            ),  # Will be updated from market data
                            unrealized_pnl=unrealized_pnl,
                            realized_pnl=Decimal(pos.get("pl", "0")),
                            currency=CurrencyCode.USD,
                        )

                        positions.append(position)
                        self._update_position(position)

            return positions

        except Exception as e:
            self.logger.error(f"Error getting positions from Oanda: {e}")
            return []

    async def get_open_orders(self) -> List[OrderResponse]:
        """Get open orders from Oanda."""
        try:
            # Get pending orders
            response = await self._make_request(
                "GET", f"/accounts/{self.account_id}/pendingOrders"
            )

            open_orders = []
            if response and "orders" in response:
                for order in response["orders"]:
                    broker_order_id = str(order.get("id", ""))

                    # Try to find client order ID from extensions
                    client_extensions = order.get("clientExtensions", {})
                    client_order_id = client_extensions.get("id", broker_order_id)

                    if client_order_id not in self.broker_to_client_orders:
                        self.broker_to_client_orders[broker_order_id] = client_order_id

                    # Convert instrument to symbol
                    instrument = order.get("instrument", "")
                    symbol = self._convert_instrument_to_symbol(instrument)

                    # Determine side from units
                    units = Decimal(order.get("units", "0"))
                    side = OrderSide.BUY if units > 0 else OrderSide.SELL

                    order_response = OrderResponse(
                        broker_type=self.broker_type,
                        account_id=self.account_id,
                        client_order_id=client_order_id,
                        broker_order_id=broker_order_id,
                        status=self._convert_oanda_state(order.get("state", "")),
                        success=True,
                        symbol=symbol,
                        side=side,
                        quantity=abs(units),
                        filled_quantity=Decimal("0"),
                        remaining_quantity=abs(units),
                    )

                    open_orders.append(order_response)

            return open_orders

        except Exception as e:
            self.logger.error(f"Error getting open orders from Oanda: {e}")
            return []

    async def subscribe_market_data(self, request: MarketDataRequest) -> bool:
        """Subscribe to market data from Oanda."""
        try:
            # Start price streaming if not already active
            if not self.price_stream_active:
                self.price_stream_active = True
                asyncio.create_task(self._price_stream_handler(request.symbols))

            # Add symbols to subscriptions
            for symbol in request.symbols:
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

            # Stop streaming if no more subscriptions
            if not self.market_data_subscriptions:
                self.price_stream_active = False

            return True

        except Exception as e:
            self.logger.error(f"Error unsubscribing from market data: {e}")
            return False

    async def get_market_data_snapshot(
        self, symbol: str
    ) -> Optional[MarketDataSnapshot]:
        """Get market data snapshot from Oanda."""
        try:
            # Check if we have recent streaming data
            if symbol in self.latest_prices:
                return self.latest_prices[symbol]

            # Otherwise fetch current pricing
            instrument = self._format_instrument(symbol)

            response = await self._make_request(
                "GET",
                f"/accounts/{self.account_id}/pricing",
                params={"instruments": instrument},
            )

            if response and "prices" in response:
                for price in response["prices"]:
                    if price.get("instrument") == instrument:
                        # Get best bid/ask
                        bids = price.get("bids", [])
                        asks = price.get("asks", [])

                        if bids and asks:
                            best_bid = bids[0]
                            best_ask = asks[0]

                            snapshot = MarketDataSnapshot(
                                broker_type=self.broker_type,
                                account_id=self.account_id,
                                symbol=symbol,
                                bid_price=Decimal(best_bid.get("price", "0")),
                                ask_price=Decimal(best_ask.get("price", "0")),
                                last_price=Decimal(price.get("closeoutAsk", "0")),
                                bid_size=Decimal(best_bid.get("liquidity", "1000000")),
                                ask_size=Decimal(best_ask.get("liquidity", "1000000")),
                                volume=Decimal("0"),  # Oanda doesn't provide volume
                                market_time=datetime.fromisoformat(
                                    price.get("time", "").replace("Z", "+00:00")
                                ),
                            )

                            # Cache the data
                            self.latest_prices[symbol] = snapshot

                            return snapshot

            return None

        except Exception as e:
            self.logger.error(f"Error getting market data snapshot: {e}")
            return None

    def get_capabilities(self) -> BrokerCapabilities:
        """Get Oanda capabilities."""
        return BrokerCapabilities(
            broker_type=self.broker_type,
            supported_order_types=[
                OrderType.MARKET,
                OrderType.LIMIT,
                OrderType.STOP,
                OrderType.TRAILING_STOP,
            ],
            supported_time_in_force=[
                TimeInForce.FOK,
                TimeInForce.IOC,
                TimeInForce.GTC,
                TimeInForce.GTD,
                TimeInForce.DAY,
            ],
            supported_symbols=[
                "EURUSD",
                "GBPUSD",
                "USDJPY",
                "USDCHF",
                "AUDUSD",
                "USDCAD",
                "NZDUSD",
                "EURGBP",
                "EURJPY",
                "GBPJPY",
                "AUDJPY",
                "EURAUD",
                "GBPAUD",
                "CADJPY",
            ],
            min_order_size={
                "EURUSD": Decimal("1"),  # 1 unit minimum
                "GBPUSD": Decimal("1"),
                "USDJPY": Decimal("1"),
                "USDCHF": Decimal("1"),
                "AUDUSD": Decimal("1"),
                "USDCAD": Decimal("1"),
                "NZDUSD": Decimal("1"),
            },
            max_order_size={
                "EURUSD": Decimal("100000000"),  # 100M units
                "GBPUSD": Decimal("100000000"),
                "USDJPY": Decimal("100000000"),
                "USDCHF": Decimal("100000000"),
                "AUDUSD": Decimal("100000000"),
                "USDCAD": Decimal("100000000"),
                "NZDUSD": Decimal("100000000"),
            },
            max_orders_per_second=120,
            max_orders_per_minute=1000,
            provides_market_data=True,
            real_time_data=True,
            historical_data=True,
            trading_sessions=[
                {
                    "name": "FOREX_24H",
                    "start_time": "17:00:00",
                    "end_time": "17:00:00",
                    "timezone": "America/New_York",
                    "days": ["SUN", "MON", "TUE", "WED", "THU", "FRI"],
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
        json: Optional[Dict] = None,
        params: Optional[Dict] = None,
    ) -> Optional[Dict]:
        """Make HTTP request to Oanda API."""
        if not self.session:
            raise BrokerConnectionError("Not connected to Oanda API")

        url = f"{self.api_url}{endpoint}"

        try:
            async with self.session.request(
                method, url, json=json, params=params
            ) as response:
                response_data = await response.json()

                if response.status in [200, 201]:
                    return response_data
                else:
                    self.logger.error(
                        f"Oanda API error: {response.status} - {response_data}"
                    )
                    return response_data  # Return error response for handling

        except Exception as e:
            self.logger.error(f"Error making request to Oanda API: {e}")
            return None

    async def _price_stream_handler(self, symbols: List[str]):
        """Handle streaming prices from Oanda."""
        if not self.stream_session:
            return

        try:
            # Convert symbols to instruments
            instruments = [self._format_instrument(symbol) for symbol in symbols]

            # Build streaming URL
            params = {"instruments": ",".join(instruments)}
            url = f"{self.stream_url}/accounts/{self.account_id}/pricing/stream"

            async with self.stream_session.get(url, params=params) as response:
                async for line in response.content:
                    if not self.price_stream_active:
                        break

                    try:
                        data = json.loads(line.decode("utf-8"))

                        if data.get("type") == "PRICE":
                            # Convert to market data snapshot
                            instrument = data.get("instrument", "")
                            symbol = self._convert_instrument_to_symbol(instrument)

                            if symbol in self.market_data_subscriptions:
                                bids = data.get("bids", [])
                                asks = data.get("asks", [])

                                if bids and asks:
                                    snapshot = MarketDataSnapshot(
                                        broker_type=self.broker_type,
                                        account_id=self.account_id,
                                        symbol=symbol,
                                        bid_price=Decimal(bids[0].get("price", "0")),
                                        ask_price=Decimal(asks[0].get("price", "0")),
                                        last_price=Decimal(
                                            data.get("closeoutAsk", "0")
                                        ),
                                        bid_size=Decimal(
                                            bids[0].get("liquidity", "1000000")
                                        ),
                                        ask_size=Decimal(
                                            asks[0].get("liquidity", "1000000")
                                        ),
                                        volume=Decimal("0"),
                                        market_time=datetime.fromisoformat(
                                            data.get("time", "").replace("Z", "+00:00")
                                        ),
                                    )

                                    # Update cache
                                    self.latest_prices[symbol] = snapshot

                                    # Emit to handlers
                                    await self._emit_message(snapshot)

                    except json.JSONDecodeError:
                        continue
                    except Exception as e:
                        self.logger.error(f"Error processing price stream: {e}")

        except Exception as e:
            self.logger.error(f"Error in price stream handler: {e}")
            self.price_stream_active = False

    async def _check_oanda_rate_limits(self) -> bool:
        """Check Oanda-specific rate limits."""
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

    def _format_instrument(self, symbol: str) -> str:
        """Convert symbol to Oanda instrument format."""
        # Oanda uses underscore format: EUR_USD
        if len(symbol) == 6:
            return f"{symbol[:3]}_{symbol[3:]}"
        return symbol

    def _convert_instrument_to_symbol(self, instrument: str) -> str:
        """Convert Oanda instrument to standard symbol format."""
        # Convert EUR_USD to EURUSD
        return instrument.replace("_", "")

    def _convert_time_in_force(self, tif: TimeInForce) -> str:
        """Convert standard time in force to Oanda format."""
        mapping = {
            TimeInForce.FOK: "FOK",
            TimeInForce.IOC: "IOC",
            TimeInForce.GTC: "GTC",
            TimeInForce.GTD: "GTD",
            TimeInForce.DAY: "DAY",
        }
        return mapping.get(tif, "FOK")

    def _convert_oanda_state(self, state: str) -> OrderStatus:
        """Convert Oanda order state to standard format."""
        mapping = {
            "PENDING": OrderStatus.PENDING,
            "FILLED": OrderStatus.FILLED,
            "TRIGGERED": OrderStatus.WORKING,
            "CANCELLED": OrderStatus.CANCELLED,
        }
        return mapping.get(state, OrderStatus.PENDING)

    async def _broker_health_check(self) -> Dict[str, Any]:
        """Oanda-specific health check."""
        health = {
            "api_url": self.api_url,
            "environment": self.environment,
            "stream_active": self.price_stream_active,
            "rate_limit_usage": len(self.last_request_times),
            "cached_prices": len(self.latest_prices),
            "net_positions": len(self.net_positions),
        }

        # Check API health
        try:
            response = await self._make_request("GET", "/accounts")
            health["api_responsive"] = response is not None
        except:
            health["api_responsive"] = False

        return health

    async def cleanup(self):
        """Clean up resources before shutdown."""
        try:
            # Stop streaming
            self.price_stream_active = False

            # Clear cache
            self.latest_prices.clear()

            # Close sessions
            if self.session:
                await self.session.close()

            if self.stream_session:
                await self.stream_session.close()

            # Call parent cleanup
            await super().cleanup()

        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")


# Register the adapter
from .base_broker_adapter import BrokerAdapterFactory

BrokerAdapterFactory.register_adapter(BrokerType.OANDA, OandaAdapter)
