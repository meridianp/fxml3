"""Manual trading adapter for manual execution notifications."""

import asyncio
import json
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
    ManualTradeConfirmation,
    ManualTradeNotification,
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
from .base_broker_adapter import BaseBrokerAdapter, BrokerOrderError


class ManualTradingAdapter(BaseBrokerAdapter):
    """Manual trading adapter for handling manual trade notifications.

    This adapter is used when trades are executed manually through a broker's
    web platform, mobile app, or phone orders, and need to be recorded in the
    FXML4 system for tracking and analysis.
    """

    def __init__(self, broker_type: BrokerType, config: Dict[str, Any]):
        super().__init__(broker_type, config)

        # Manual trading configuration
        self.require_confirmation = config.get("require_confirmation", True)
        self.auto_confirm_threshold = config.get(
            "auto_confirm_threshold", 10000
        )  # Auto-confirm trades under $10k
        self.confirmation_timeout = config.get("confirmation_timeout", 300)  # 5 minutes

        # Pending trades awaiting confirmation
        self.pending_trades: Dict[str, ManualTradeNotification] = {}
        self.pending_orders: Dict[str, OrderRequest] = {}

        # Manual position tracking
        self.manual_positions: Dict[str, Decimal] = {}
        self.manual_account_balance = Decimal("100000")  # Default starting balance

        # Notification handlers
        self.notification_handlers: List[callable] = []

    async def connect(self) -> bool:
        """Connect to manual trading system (always successful)."""
        try:
            self.connected = True
            self.authenticated = True
            self.connection_quality = "EXCELLENT"
            self.account_id = self.config.get("account_id", "MANUAL_001")

            self.logger.info("Manual trading adapter connected")
            return True

        except Exception as e:
            self.logger.error(f"Error in manual trading adapter: {e}")
            return False

    async def disconnect(self) -> bool:
        """Disconnect from manual trading system."""
        self.connected = False
        self.authenticated = False
        self.connection_quality = "DISCONNECTED"

        self.logger.info("Manual trading adapter disconnected")
        return True

    async def authenticate(self, credentials: Dict[str, Any]) -> bool:
        """Authenticate manual trading user."""
        # For manual trading, authentication is based on user credentials
        trader_id = credentials.get("trader_id")
        api_key = credentials.get("api_key")

        if trader_id and api_key:
            self.authenticated = True
            self.config["trader_id"] = trader_id
            return True

        return False

    async def submit_order(self, order: OrderRequest) -> OrderResponse:
        """Submit a manual order (creates notification for manual execution)."""
        try:
            # For manual trading, we don't execute orders automatically
            # Instead, we create a pending order that requires manual execution

            self.pending_orders[order.client_order_id] = order
            self._update_order_status(order.client_order_id, OrderStatus.PENDING)

            # Create response indicating order is pending manual execution
            response = OrderResponse(
                broker_type=self.broker_type,
                account_id=self.account_id,
                client_order_id=order.client_order_id,
                status=OrderStatus.PENDING,
                success=True,
                symbol=order.symbol,
                side=order.side,
                quantity=order.quantity,
                order_time=datetime.utcnow(),
                metadata={
                    "execution_method": "manual",
                    "requires_manual_execution": True,
                    "instructions": self._generate_execution_instructions(order),
                },
            )

            # Notify handlers about pending manual order
            await self._notify_manual_order_required(order)

            await self._emit_message(response)

            self.logger.info(f"Manual order created: {order.client_order_id}")
            return response

        except Exception as e:
            self.logger.error(f"Error creating manual order: {e}")
            raise BrokerOrderError(f"Failed to create manual order: {e}")

    async def cancel_order(self, cancel_request: OrderCancelRequest) -> OrderResponse:
        """Cancel a manual order (removes from pending)."""
        try:
            client_order_id = cancel_request.client_order_id

            # Remove from pending orders
            order = self.pending_orders.pop(client_order_id, None)

            if not order:
                raise BrokerOrderError(f"Order not found: {client_order_id}")

            # Update status
            self._update_order_status(client_order_id, OrderStatus.CANCELLED)

            response = OrderResponse(
                broker_type=self.broker_type,
                account_id=self.account_id,
                client_order_id=client_order_id,
                status=OrderStatus.CANCELLED,
                success=True,
                symbol=order.symbol,
                side=order.side,
                quantity=order.quantity,
            )

            await self._emit_message(response)

            self.logger.info(f"Manual order cancelled: {client_order_id}")
            return response

        except Exception as e:
            self.logger.error(f"Error cancelling manual order: {e}")
            raise BrokerOrderError(f"Failed to cancel manual order: {e}")

    async def modify_order(self, modify_request: OrderModifyRequest) -> OrderResponse:
        """Modify a manual order."""
        try:
            client_order_id = modify_request.client_order_id

            # Get pending order
            order = self.pending_orders.get(client_order_id)
            if not order:
                raise BrokerOrderError(f"Order not found: {client_order_id}")

            # Update order parameters
            if modify_request.new_quantity:
                order.quantity = modify_request.new_quantity
            if modify_request.new_price:
                order.price = modify_request.new_price
            if modify_request.new_stop_price:
                order.stop_price = modify_request.new_stop_price
            if modify_request.new_time_in_force:
                order.time_in_force = modify_request.new_time_in_force

            # Update pending order
            self.pending_orders[client_order_id] = order

            response = OrderResponse(
                broker_type=self.broker_type,
                account_id=self.account_id,
                client_order_id=client_order_id,
                status=OrderStatus.PENDING,
                success=True,
                symbol=order.symbol,
                side=order.side,
                quantity=order.quantity,
                metadata={
                    "modified": True,
                    "instructions": self._generate_execution_instructions(order),
                },
            )

            # Notify handlers about order modification
            await self._notify_manual_order_modified(order)

            await self._emit_message(response)

            self.logger.info(f"Manual order modified: {client_order_id}")
            return response

        except Exception as e:
            self.logger.error(f"Error modifying manual order: {e}")
            raise BrokerOrderError(f"Failed to modify manual order: {e}")

    async def record_manual_trade(
        self, trade_notification: ManualTradeNotification
    ) -> bool:
        """Record a manually executed trade.

        Args:
            trade_notification: Notification of manual trade execution

        Returns:
            True if trade recorded successfully
        """
        try:
            # Validate trade notification
            if not self._validate_trade_notification(trade_notification):
                raise ValueError("Invalid trade notification")

            # Check if confirmation is required
            trade_value = float(trade_notification.quantity * trade_notification.price)

            if self.require_confirmation and trade_value > self.auto_confirm_threshold:
                # Add to pending trades
                self.pending_trades[trade_notification.trade_id] = trade_notification

                # Request confirmation
                await self._request_trade_confirmation(trade_notification)

                self.logger.info(
                    f"Manual trade pending confirmation: {trade_notification.trade_id}"
                )
                return True
            else:
                # Auto-confirm small trades
                await self._confirm_trade(trade_notification, auto_confirmed=True)
                return True

        except Exception as e:
            self.logger.error(f"Error recording manual trade: {e}")
            return False

    async def confirm_manual_trade(self, confirmation: ManualTradeConfirmation) -> bool:
        """Confirm a manually executed trade.

        Args:
            confirmation: Trade confirmation

        Returns:
            True if confirmation successful
        """
        try:
            trade_id = confirmation.trade_notification_id

            # Get pending trade
            trade_notification = self.pending_trades.get(trade_id)
            if not trade_notification:
                self.logger.warning(f"Trade not found for confirmation: {trade_id}")
                return False

            if confirmation.confirmed:
                # Confirm the trade
                await self._confirm_trade(trade_notification, auto_confirmed=False)

                # Remove from pending
                del self.pending_trades[trade_id]

                self.logger.info(f"Manual trade confirmed: {trade_id}")
                return True
            else:
                # Reject the trade
                await self._reject_trade(
                    trade_notification, confirmation.rejection_reason
                )

                # Remove from pending
                del self.pending_trades[trade_id]

                self.logger.info(f"Manual trade rejected: {trade_id}")
                return True

        except Exception as e:
            self.logger.error(f"Error confirming manual trade: {e}")
            return False

    async def get_account_info(self) -> AccountReport:
        """Get manual account information."""
        try:
            # Calculate account metrics from manual positions
            total_position_value = sum(
                pos_size * Decimal("1.0841")  # Mock current price
                for pos_size in self.manual_positions.values()
            )

            unrealized_pnl = Decimal(
                "0"
            )  # Would calculate based on entry vs current prices

            account_report = AccountReport(
                broker_type=self.broker_type,
                account_id=self.account_id,
                account_value=self.manual_account_balance + unrealized_pnl,
                cash_balance=self.manual_account_balance,
                equity=self.manual_account_balance + unrealized_pnl,
                buying_power=self.manual_account_balance * 4,  # Assume 4:1 leverage
                unrealized_pnl=unrealized_pnl,
                base_currency=CurrencyCode.USD,
            )

            self._update_account_info(account_report)
            return account_report

        except Exception as e:
            self.logger.error(f"Error getting manual account info: {e}")
            raise

    async def get_positions(self) -> List[PositionReport]:
        """Get manual positions."""
        try:
            positions = []

            for symbol, position_size in self.manual_positions.items():
                if position_size != 0:
                    position = PositionReport(
                        broker_type=self.broker_type,
                        account_id=self.account_id,
                        symbol=symbol,
                        position_size=position_size,
                        average_price=Decimal(
                            "1.0841"
                        ),  # Would track actual entry price
                        market_price=Decimal(
                            "1.0841"
                        ),  # Would get current market price
                        unrealized_pnl=Decimal("0"),  # Would calculate
                        currency=CurrencyCode.USD,
                    )

                    positions.append(position)
                    self._update_position(position)

            return positions

        except Exception as e:
            self.logger.error(f"Error getting manual positions: {e}")
            return []

    async def get_open_orders(self) -> List[OrderResponse]:
        """Get pending manual orders."""
        try:
            open_orders = []

            for client_order_id, order in self.pending_orders.items():
                order_response = OrderResponse(
                    broker_type=self.broker_type,
                    account_id=self.account_id,
                    client_order_id=client_order_id,
                    status=OrderStatus.PENDING,
                    success=True,
                    symbol=order.symbol,
                    side=order.side,
                    quantity=order.quantity,
                    metadata={
                        "execution_method": "manual",
                        "awaiting_manual_execution": True,
                    },
                )

                open_orders.append(order_response)

            return open_orders

        except Exception as e:
            self.logger.error(f"Error getting manual open orders: {e}")
            return []

    async def subscribe_market_data(self, request: MarketDataRequest) -> bool:
        """Manual trading doesn't provide market data."""
        self.logger.info("Manual trading adapter doesn't provide market data")
        return False

    async def unsubscribe_market_data(self, request_id: str) -> bool:
        """Manual trading doesn't provide market data."""
        return False

    async def get_market_data_snapshot(
        self, symbol: str
    ) -> Optional[MarketDataSnapshot]:
        """Manual trading doesn't provide market data."""
        return None

    def get_capabilities(self) -> BrokerCapabilities:
        """Get manual trading capabilities."""
        return BrokerCapabilities(
            broker_type=self.broker_type,
            supported_order_types=[
                OrderType.MARKET,
                OrderType.LIMIT,
                OrderType.STOP,
                OrderType.STOP_LIMIT,
            ],
            supported_time_in_force=[TimeInForce.GTC, TimeInForce.DAY],
            supported_symbols=[
                "EURUSD",
                "GBPUSD",
                "USDJPY",
                "USDCHF",
                "AUDUSD",
                "USDCAD",
                "NZDUSD",
            ],
            provides_market_data=False,
            real_time_data=False,
            historical_data=False,
            metadata={
                "execution_method": "manual",
                "requires_confirmation": self.require_confirmation,
                "auto_confirm_threshold": float(self.auto_confirm_threshold),
            },
        )

    # Helper methods

    def _validate_trade_notification(self, trade: ManualTradeNotification) -> bool:
        """Validate manual trade notification."""
        required_fields = [
            "trade_id",
            "symbol",
            "side",
            "quantity",
            "price",
            "execution_time",
        ]

        for field in required_fields:
            if not hasattr(trade, field) or getattr(trade, field) is None:
                self.logger.error(f"Missing required field: {field}")
                return False

        if trade.quantity <= 0:
            self.logger.error("Quantity must be positive")
            return False

        if trade.price <= 0:
            self.logger.error("Price must be positive")
            return False

        return True

    def _generate_execution_instructions(self, order: OrderRequest) -> str:
        """Generate human-readable execution instructions."""
        instructions = (
            f"Execute {order.side.value} order for {order.quantity} {order.symbol}"
        )

        if order.order_type == OrderType.LIMIT:
            instructions += f" at limit price {order.price}"
        elif order.order_type == OrderType.STOP:
            instructions += f" when price reaches {order.stop_price}"
        elif order.order_type == OrderType.STOP_LIMIT:
            instructions += (
                f" as stop-limit: stop at {order.stop_price}, limit at {order.price}"
            )

        if order.time_in_force != TimeInForce.GTC:
            instructions += f" (TIF: {order.time_in_force.value})"

        return instructions

    async def _notify_manual_order_required(self, order: OrderRequest):
        """Notify that manual order execution is required."""
        notification = {
            "type": "manual_order_required",
            "order_id": order.client_order_id,
            "symbol": order.symbol,
            "side": order.side.value,
            "quantity": float(order.quantity),
            "order_type": order.order_type.value,
            "instructions": self._generate_execution_instructions(order),
            "created_time": datetime.utcnow().isoformat(),
        }

        # Send to notification handlers
        for handler in self.notification_handlers:
            try:
                await handler(notification)
            except Exception as e:
                self.logger.error(f"Error in notification handler: {e}")

    async def _notify_manual_order_modified(self, order: OrderRequest):
        """Notify that manual order has been modified."""
        notification = {
            "type": "manual_order_modified",
            "order_id": order.client_order_id,
            "symbol": order.symbol,
            "new_instructions": self._generate_execution_instructions(order),
            "modified_time": datetime.utcnow().isoformat(),
        }

        for handler in self.notification_handlers:
            try:
                await handler(notification)
            except Exception as e:
                self.logger.error(f"Error in notification handler: {e}")

    async def _request_trade_confirmation(self, trade: ManualTradeNotification):
        """Request confirmation for a manual trade."""
        confirmation_request = {
            "type": "trade_confirmation_required",
            "trade_id": trade.trade_id,
            "symbol": trade.symbol,
            "side": trade.side.value,
            "quantity": float(trade.quantity),
            "price": float(trade.price),
            "value": float(trade.quantity * trade.price),
            "execution_time": trade.execution_time.isoformat(),
            "timeout": self.confirmation_timeout,
        }

        for handler in self.notification_handlers:
            try:
                await handler(confirmation_request)
            except Exception as e:
                self.logger.error(f"Error in confirmation request handler: {e}")

    async def _confirm_trade(
        self, trade: ManualTradeNotification, auto_confirmed: bool = False
    ):
        """Confirm and process a manual trade."""
        # Update position
        position_change = (
            trade.quantity if trade.side == OrderSide.BUY else -trade.quantity
        )
        current_position = self.manual_positions.get(trade.symbol, Decimal("0"))
        self.manual_positions[trade.symbol] = current_position + position_change

        # Create execution report
        execution_report = ExecutionReport(
            broker_type=self.broker_type,
            account_id=self.account_id,
            client_order_id=trade.related_order_id or str(uuid.uuid4()),
            broker_order_id=trade.trade_id,
            execution_id=f"MANUAL_{trade.trade_id}",
            execution_type=ExecutionType.FILL,
            order_status=OrderStatus.FILLED,
            symbol=trade.symbol,
            side=trade.side,
            last_quantity=trade.quantity,
            last_price=trade.price,
            cumulative_quantity=trade.quantity,
            leaves_quantity=Decimal("0"),
            average_price=trade.price,
            order_quantity=trade.quantity,
            order_type=OrderType.MARKET,  # Assume manual trades are market orders
            time_in_force=TimeInForce.GTC,
            transaction_time=trade.execution_time,
            metadata={
                "execution_method": "manual",
                "entry_method": trade.entry_method,
                "auto_confirmed": auto_confirmed,
                "trader_id": trade.trader_id,
                "notes": trade.notes,
            },
        )

        # Emit execution report
        await self._emit_message(execution_report)

        # Update account balance (simplified)
        trade_value = trade.quantity * trade.price
        if trade.side == OrderSide.SELL:
            self.manual_account_balance += trade_value
        # For BUY orders, we assume the cash was already committed

        self.logger.info(f"Manual trade confirmed: {trade.trade_id}")

    async def _reject_trade(
        self, trade: ManualTradeNotification, reason: Optional[str]
    ):
        """Reject a manual trade."""
        # Create error for rejected trade
        error = BrokerError(
            broker_type=self.broker_type,
            account_id=self.account_id,
            error_code="TRADE_REJECTED",
            error_message=f"Manual trade rejected: {reason or 'No reason provided'}",
            error_type="MANUAL_EXECUTION",
            related_order_id=trade.related_order_id,
            metadata={"trade_id": trade.trade_id, "rejection_reason": reason},
        )

        await self._emit_error(error)

        self.logger.info(f"Manual trade rejected: {trade.trade_id} - {reason}")

    def add_notification_handler(self, handler: callable):
        """Add a notification handler for manual trading events."""
        self.notification_handlers.append(handler)

    async def _broker_health_check(self) -> Dict[str, Any]:
        """Manual trading specific health check."""
        return {
            "pending_orders": len(self.pending_orders),
            "pending_confirmations": len(self.pending_trades),
            "manual_positions": len(
                [p for p in self.manual_positions.values() if p != 0]
            ),
            "require_confirmation": self.require_confirmation,
            "auto_confirm_threshold": float(self.auto_confirm_threshold),
        }


# Register the adapter
from .base_broker_adapter import BrokerAdapterFactory

BrokerAdapterFactory.register_adapter(BrokerType.MANUAL, ManualTradingAdapter)
