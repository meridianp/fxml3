"""Interactive Brokers broker adapter implementation."""

import asyncio
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

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
    BrokerConnectionError,
    BrokerOrderError,
)


# Mock IB API - in real implementation, this would be the actual IB API
class MockIBClient:
    """Mock Interactive Brokers client for demonstration."""

    def __init__(self):
        self.connected = False
        self.next_order_id = 1000
        self.orders = {}
        self.positions = {}
        self.account = {
            "TotalCashValue": 100000,
            "NetLiquidation": 100000,
            "AvailableFunds": 100000,
            "BuyingPower": 400000,
            "InitMarginReq": 0,
            "MaintMarginReq": 0,
            "UnrealizedPnL": 0,
            "RealizedPnL": 0,
        }

    async def connect(self, host: str, port: int, client_id: int):
        """Connect to IB Gateway."""
        await asyncio.sleep(0.1)  # Simulate connection delay
        self.connected = True

    async def disconnect(self):
        """Disconnect from IB Gateway."""
        self.connected = False

    def get_next_order_id(self):
        """Get next valid order ID."""
        order_id = self.next_order_id
        self.next_order_id += 1
        return order_id

    async def place_order(self, order_id: int, contract: dict, order: dict):
        """Place an order."""
        # Simulate order placement
        await asyncio.sleep(0.05)

        self.orders[order_id] = {
            "order_id": order_id,
            "contract": contract,
            "order": order,
            "status": "Submitted",
            "filled": 0,
            "remaining": order["totalQuantity"],
        }

        # Simulate immediate fill for market orders
        if order["orderType"] == "MKT":
            await asyncio.sleep(0.1)
            self.orders[order_id]["status"] = "Filled"
            self.orders[order_id]["filled"] = order["totalQuantity"]
            self.orders[order_id]["remaining"] = 0
            self.orders[order_id]["avgFillPrice"] = 1.0850  # Mock price

    async def cancel_order(self, order_id: int):
        """Cancel an order."""
        if order_id in self.orders:
            self.orders[order_id]["status"] = "Cancelled"

    def get_account_values(self):
        """Get account values."""
        return self.account.copy()

    def get_positions(self):
        """Get positions."""
        return list(self.positions.values())


class InteractiveBrokersAdapter(BaseBrokerAdapter):
    """Interactive Brokers adapter implementation."""

    def __init__(self, broker_type: BrokerType, config: Dict[str, Any]):
        super().__init__(broker_type, config)

        # IB-specific configuration
        self.host = config.get("host", "127.0.0.1")
        self.port = config.get("port", 7497)  # 7497 for paper, 7496 for live
        self.client_id = config.get("client_id", 1)

        # IB client instance
        self.ib_client = MockIBClient()  # In real implementation: use ib_insync

        # Order mapping
        self.client_to_broker_orders: Dict[str, int] = {}
        self.broker_to_client_orders: Dict[int, str] = {}

        # Market data subscriptions
        self.market_data_subscriptions: Dict[str, int] = {}
        self.req_id_counter = 1000

    async def connect(self) -> bool:
        """Connect to Interactive Brokers Gateway."""
        try:
            self.logger.info(f"Connecting to IB Gateway at {self.host}:{self.port}")

            await self.ib_client.connect(self.host, self.port, self.client_id)

            if self.ib_client.connected:
                self.connected = True
                self.authenticated = True  # IB handles auth via gateway
                self.connection_quality = "EXCELLENT"

                # Get account ID (in real implementation, this comes from IB)
                self.account_id = config.get("account_id", "DU123456")

                self.logger.info("Successfully connected to IB Gateway")
                return True
            else:
                self.logger.error("Failed to connect to IB Gateway")
                return False

        except Exception as e:
            self.logger.error(f"Error connecting to IB Gateway: {e}")
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
        """Disconnect from Interactive Brokers Gateway."""
        try:
            await self.ib_client.disconnect()
            self.connected = False
            self.authenticated = False
            self.connection_quality = "DISCONNECTED"

            self.logger.info("Disconnected from IB Gateway")
            return True

        except Exception as e:
            self.logger.error(f"Error disconnecting from IB Gateway: {e}")
            return False

    async def authenticate(self, credentials: Dict[str, Any]) -> bool:
        """Authenticate with Interactive Brokers.

        Note: IB authentication is handled by the Gateway/TWS application,
        not through API credentials.
        """
        # IB authentication happens through the Gateway application
        # This method is here for interface compliance
        if self.connected:
            self.authenticated = True
            return True
        return False

    async def submit_order(self, order: OrderRequest) -> OrderResponse:
        """Submit an order to Interactive Brokers."""
        try:
            # Validate order
            if not self._validate_order(order):
                raise BrokerOrderError("Order validation failed")

            # Check rate limits
            if not await self._check_rate_limits("order"):
                raise BrokerOrderError("Rate limit exceeded")

            # Convert to IB order format
            ib_contract = self._create_ib_contract(order)
            ib_order = self._create_ib_order(order)

            # Get broker order ID
            broker_order_id = self.ib_client.get_next_order_id()

            # Store order mapping
            self.client_to_broker_orders[order.client_order_id] = broker_order_id
            self.broker_to_client_orders[broker_order_id] = order.client_order_id

            # Store active order
            self.active_orders[order.client_order_id] = order

            # Submit to IB
            await self.ib_client.place_order(broker_order_id, ib_contract, ib_order)

            # Create response
            response = OrderResponse(
                broker_type=self.broker_type,
                account_id=self.account_id,
                client_order_id=order.client_order_id,
                broker_order_id=str(broker_order_id),
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
            await self._emit_message(response)

            self.logger.info(
                f"Order submitted: {order.client_order_id} -> {broker_order_id}"
            )

            return response

        except Exception as e:
            self.logger.error(f"Error submitting order: {e}")

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
        """Cancel an order in Interactive Brokers."""
        try:
            client_order_id = cancel_request.client_order_id

            # Get broker order ID
            broker_order_id = self.client_to_broker_orders.get(client_order_id)
            if not broker_order_id:
                raise BrokerOrderError(f"Order not found: {client_order_id}")

            # Cancel with IB
            await self.ib_client.cancel_order(broker_order_id)

            # Create response
            response = OrderResponse(
                broker_type=self.broker_type,
                account_id=self.account_id,
                client_order_id=client_order_id,
                broker_order_id=str(broker_order_id),
                status=OrderStatus.CANCELLED,
                success=True,
                symbol=cancel_request.symbol,
                side=OrderSide.BUY,  # Would need to get from stored order
                quantity=Decimal("0"),  # Would need to get from stored order
            )

            # Update order status
            self._update_order_status(client_order_id, OrderStatus.CANCELLED)

            # Emit response
            await self._emit_message(response)

            self.logger.info(f"Order cancelled: {client_order_id}")

            return response

        except Exception as e:
            self.logger.error(f"Error cancelling order: {e}")
            raise BrokerOrderError(f"Failed to cancel order: {e}")

    async def modify_order(self, modify_request: OrderModifyRequest) -> OrderResponse:
        """Modify an order in Interactive Brokers."""
        try:
            # IB doesn't support direct order modification
            # Need to cancel and replace

            client_order_id = modify_request.client_order_id

            # Get original order
            original_order = self.active_orders.get(client_order_id)
            if not original_order:
                raise BrokerOrderError(f"Original order not found: {client_order_id}")

            # Cancel original order
            cancel_request = OrderCancelRequest(
                broker_type=self.broker_type,
                account_id=self.account_id,
                client_order_id=client_order_id,
                symbol=original_order.symbol,
            )

            await self.cancel_order(cancel_request)

            # Create new order with modifications
            new_order = OrderRequest(
                broker_type=self.broker_type,
                account_id=self.account_id,
                client_order_id=str(uuid.uuid4()),  # New client order ID
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
                f"Order modified: {client_order_id} -> {new_order.client_order_id}"
            )

            return response

        except Exception as e:
            self.logger.error(f"Error modifying order: {e}")
            raise BrokerOrderError(f"Failed to modify order: {e}")

    async def get_account_info(self) -> AccountReport:
        """Get account information from Interactive Brokers."""
        try:
            # Get account values from IB
            account_values = self.ib_client.get_account_values()

            # Convert to standard format
            account_report = AccountReport(
                broker_type=self.broker_type,
                account_id=self.account_id,
                account_value=Decimal(str(account_values.get("NetLiquidation", 0))),
                cash_balance=Decimal(str(account_values.get("TotalCashValue", 0))),
                equity=Decimal(str(account_values.get("NetLiquidation", 0))),
                buying_power=Decimal(str(account_values.get("BuyingPower", 0))),
                initial_margin=Decimal(str(account_values.get("InitMarginReq", 0))),
                maintenance_margin=Decimal(
                    str(account_values.get("MaintMarginReq", 0))
                ),
                available_margin=Decimal(str(account_values.get("AvailableFunds", 0))),
                unrealized_pnl=Decimal(str(account_values.get("UnrealizedPnL", 0))),
                realized_pnl=Decimal(str(account_values.get("RealizedPnL", 0))),
                base_currency=CurrencyCode.USD,
            )

            # Update internal account info
            self._update_account_info(account_report)

            return account_report

        except Exception as e:
            self.logger.error(f"Error getting account info: {e}")
            raise

    async def get_positions(self) -> List[PositionReport]:
        """Get positions from Interactive Brokers."""
        try:
            # Get positions from IB
            ib_positions = self.ib_client.get_positions()

            # Convert to standard format
            positions = []
            for ib_pos in ib_positions:
                position = PositionReport(
                    broker_type=self.broker_type,
                    account_id=self.account_id,
                    symbol=ib_pos.get("symbol", "UNKNOWN"),
                    position_size=Decimal(str(ib_pos.get("position", 0))),
                    average_price=Decimal(str(ib_pos.get("avgCost", 0))),
                    market_price=Decimal(str(ib_pos.get("marketPrice", 0))),
                    unrealized_pnl=Decimal(str(ib_pos.get("unrealizedPNL", 0))),
                    realized_pnl=Decimal(str(ib_pos.get("realizedPNL", 0))),
                    currency=CurrencyCode.USD,
                )

                positions.append(position)
                self._update_position(position)

            return positions

        except Exception as e:
            self.logger.error(f"Error getting positions: {e}")
            return []

    async def get_open_orders(self) -> List[OrderResponse]:
        """Get open orders from Interactive Brokers."""
        try:
            open_orders = []

            # Get orders from IB client
            for broker_order_id, ib_order in self.ib_client.orders.items():
                if ib_order["status"] in ["Submitted", "PreSubmitted", "PendingSubmit"]:
                    client_order_id = self.broker_to_client_orders.get(
                        broker_order_id, str(broker_order_id)
                    )

                    order_response = OrderResponse(
                        broker_type=self.broker_type,
                        account_id=self.account_id,
                        client_order_id=client_order_id,
                        broker_order_id=str(broker_order_id),
                        status=self._convert_ib_status(ib_order["status"]),
                        success=True,
                        symbol=ib_order["contract"].get("symbol", "UNKNOWN"),
                        side=self._convert_ib_action(
                            ib_order["order"].get("action", "BUY")
                        ),
                        quantity=Decimal(
                            str(ib_order["order"].get("totalQuantity", 0))
                        ),
                        filled_quantity=Decimal(str(ib_order.get("filled", 0))),
                        remaining_quantity=Decimal(str(ib_order.get("remaining", 0))),
                    )

                    open_orders.append(order_response)

            return open_orders

        except Exception as e:
            self.logger.error(f"Error getting open orders: {e}")
            return []

    async def subscribe_market_data(self, request: MarketDataRequest) -> bool:
        """Subscribe to market data from Interactive Brokers."""
        try:
            # For each symbol, create a subscription
            for symbol in request.symbols:
                req_id = self._get_next_req_id()

                # Store subscription
                self.market_data_subscriptions[symbol] = req_id

                # In real implementation, would call:
                # self.ib_client.reqMktData(req_id, contract, "", False, False, [])

            self.logger.info(f"Subscribed to market data for: {request.symbols}")
            return True

        except Exception as e:
            self.logger.error(f"Error subscribing to market data: {e}")
            return False

    async def unsubscribe_market_data(self, request_id: str) -> bool:
        """Unsubscribe from market data."""
        try:
            # Find and remove subscription
            symbol_to_remove = None
            for symbol, req_id in self.market_data_subscriptions.items():
                if str(req_id) == request_id:
                    symbol_to_remove = symbol
                    break

            if symbol_to_remove:
                req_id = self.market_data_subscriptions.pop(symbol_to_remove)
                # In real implementation: self.ib_client.cancelMktData(req_id)

            return True

        except Exception as e:
            self.logger.error(f"Error unsubscribing from market data: {e}")
            return False

    async def get_market_data_snapshot(
        self, symbol: str
    ) -> Optional[MarketDataSnapshot]:
        """Get market data snapshot from Interactive Brokers."""
        try:
            # In real implementation, would request snapshot from IB
            # For now, return mock data

            snapshot = MarketDataSnapshot(
                broker_type=self.broker_type,
                account_id=self.account_id,
                symbol=symbol,
                bid_price=Decimal("1.0840"),
                ask_price=Decimal("1.0842"),
                last_price=Decimal("1.0841"),
                bid_size=Decimal("1000000"),
                ask_size=Decimal("1000000"),
                volume=Decimal("10000"),
                market_time=datetime.utcnow(),
            )

            return snapshot

        except Exception as e:
            self.logger.error(f"Error getting market data snapshot: {e}")
            return None

    def get_capabilities(self) -> BrokerCapabilities:
        """Get Interactive Brokers capabilities."""
        return BrokerCapabilities(
            broker_type=self.broker_type,
            supported_order_types=[
                OrderType.MARKET,
                OrderType.LIMIT,
                OrderType.STOP,
                OrderType.STOP_LIMIT,
                OrderType.TRAILING_STOP,
                OrderType.BRACKET,
            ],
            supported_time_in_force=[
                TimeInForce.DAY,
                TimeInForce.GTC,
                TimeInForce.IOC,
                TimeInForce.FOK,
            ],
            supported_symbols=[
                "EURUSD",
                "GBPUSD",
                "USDJPY",
                "USDCHF",
                "AUDUSD",
                "USDCAD",
                "NZDUSD",
            ],
            min_order_size={"EURUSD": Decimal("20000"), "GBPUSD": Decimal("20000")},
            max_order_size={
                "EURUSD": Decimal("200000000"),
                "GBPUSD": Decimal("200000000"),
            },
            max_orders_per_second=10,
            max_orders_per_minute=50,
            provides_market_data=True,
            real_time_data=True,
            historical_data=True,
            trading_sessions=[
                {
                    "name": "FOREX_24H",
                    "start_time": "17:00:00",
                    "end_time": "17:00:00",
                    "timezone": "America/New_York",
                    "days": ["MON", "TUE", "WED", "THU", "FRI"],
                }
            ],
            commission_structure={
                "FOREX": {
                    "type": "FIXED",
                    "rate": 2.50,
                    "currency": "USD",
                    "minimum": 2.50,
                }
            },
        )

    # Helper methods

    def _create_ib_contract(self, order: OrderRequest) -> dict:
        """Create IB contract from order request."""
        return {
            "symbol": order.symbol[:3],  # Base currency
            "secType": "CASH",
            "exchange": "IDEALPRO",
            "currency": order.symbol[3:6],  # Quote currency
        }

    def _create_ib_order(self, order: OrderRequest) -> dict:
        """Create IB order from order request."""
        ib_order = {
            "action": "BUY" if order.side == OrderSide.BUY else "SELL",
            "totalQuantity": int(order.quantity),
            "orderType": self._convert_order_type(order.order_type),
            "tif": self._convert_time_in_force(order.time_in_force),
        }

        if order.price:
            ib_order["lmtPrice"] = float(order.price)

        if order.stop_price:
            ib_order["auxPrice"] = float(order.stop_price)

        return ib_order

    def _convert_order_type(self, order_type: OrderType) -> str:
        """Convert standard order type to IB format."""
        mapping = {
            OrderType.MARKET: "MKT",
            OrderType.LIMIT: "LMT",
            OrderType.STOP: "STP",
            OrderType.STOP_LIMIT: "STP LMT",
            OrderType.TRAILING_STOP: "TRAIL",
        }
        return mapping.get(order_type, "MKT")

    def _convert_time_in_force(self, tif: TimeInForce) -> str:
        """Convert standard time in force to IB format."""
        mapping = {
            TimeInForce.DAY: "DAY",
            TimeInForce.GTC: "GTC",
            TimeInForce.IOC: "IOC",
            TimeInForce.FOK: "FOK",
        }
        return mapping.get(tif, "GTC")

    def _convert_ib_status(self, ib_status: str) -> OrderStatus:
        """Convert IB order status to standard format."""
        mapping = {
            "Submitted": OrderStatus.SUBMITTED,
            "PreSubmitted": OrderStatus.PENDING,
            "PendingSubmit": OrderStatus.PENDING,
            "Filled": OrderStatus.FILLED,
            "Cancelled": OrderStatus.CANCELLED,
            "Inactive": OrderStatus.SUSPENDED,
        }
        return mapping.get(ib_status, OrderStatus.PENDING)

    def _convert_ib_action(self, ib_action: str) -> OrderSide:
        """Convert IB action to standard order side."""
        return OrderSide.BUY if ib_action == "BUY" else OrderSide.SELL

    def _get_next_req_id(self) -> int:
        """Get next request ID for market data."""
        req_id = self.req_id_counter
        self.req_id_counter += 1
        return req_id

    async def _broker_health_check(self) -> Dict[str, Any]:
        """IB-specific health check."""
        return {
            "gateway_connected": self.ib_client.connected if self.ib_client else False,
            "next_order_id": self.ib_client.next_order_id if self.ib_client else None,
            "active_subscriptions": len(self.market_data_subscriptions),
            "pending_orders": len(
                [
                    o
                    for o in self.ib_client.orders.values()
                    if o["status"] in ["Submitted", "PreSubmitted"]
                ]
            ),
        }


# Register the adapter
from .base_broker_adapter import BrokerAdapterFactory

BrokerAdapterFactory.register_adapter(
    BrokerType.INTERACTIVE_BROKERS, InteractiveBrokersAdapter
)
