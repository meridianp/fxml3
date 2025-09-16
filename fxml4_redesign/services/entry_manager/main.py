"""Entry Manager Service - Precision 1-minute entry timing and execution."""

import asyncio
import sys
from pathlib import Path

# Add parent directories to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import json
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from entry_analyzer import EntryAnalyzer
from risk_calculator import RiskCalculator
from shared.brokers.base_broker_adapter import BrokerAdapterFactory
from shared.config.rabbitmq_config import (
    Exchanges,
    MessagePriority,
    Queues,
    RoutingKeys,
    format_routing_key,
)
from shared.schemas.broker_messages import (
    BrokerMessageFactory,
    BrokerType,
    OrderRequest,
    OrderResponse,
    OrderSide,
    OrderType,
    TimeInForce,
)
from shared.utils.base_service import BaseService, ServiceConfig
from timing_optimizer import TimingOptimizer


class EntryManagerService(BaseService):
    """Entry Manager Service for precision trade entry timing and execution."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__("entry-manager", config)

        # Core components
        self.entry_analyzer = EntryAnalyzer()
        self.timing_optimizer = TimingOptimizer()
        self.risk_calculator = RiskCalculator()

        # Broker management
        self.broker_adapters: Dict[BrokerType, Any] = {}
        self.default_broker = BrokerType.INTERACTIVE_BROKERS

        # Signal tracking
        self.validated_signals: Dict[str, Dict[str, Any]] = {}
        self.pending_entries: Dict[str, Dict[str, Any]] = {}
        self.executed_entries: Dict[str, Dict[str, Any]] = {}

        # Market data cache for timing
        self.market_data_1m: Dict[str, List[Dict[str, Any]]] = {}
        self.market_data_5s: Dict[str, List[Dict[str, Any]]] = {}

        # Configuration
        self.max_entry_delay = config.get("max_entry_delay", 300)  # 5 minutes
        self.min_signal_confidence = config.get("min_signal_confidence", 0.65)
        self.risk_per_trade = config.get("risk_per_trade", 0.02)  # 2%
        self.max_concurrent_entries = config.get("max_concurrent_entries", 5)

        # Performance tracking
        self.entries_executed = 0
        self.avg_slippage = 0.0
        self.timing_scores = []

    async def service_setup(self):
        """Set up entry manager service."""
        # Initialize broker adapters
        await self.setup_broker_adapters()

        # Initialize analysis components
        await self.entry_analyzer.initialize()
        await self.timing_optimizer.initialize()
        await self.risk_calculator.initialize()

        # Set up RabbitMQ
        await self.setup_rabbitmq()

        self.logger.info("Entry Manager service initialized")

    async def service_teardown(self):
        """Clean up resources."""
        # Disconnect broker adapters
        for adapter in self.broker_adapters.values():
            await adapter.cleanup()

    async def service_run(self):
        """Main service loop."""
        # Start processing tasks
        self.add_task(self.validated_signals_consumer())
        self.add_task(self.market_data_consumer())
        self.add_task(self.entry_timing_loop())
        self.add_task(self.execution_monitor_loop())
        self.add_task(self.heartbeat_loop())

        # Wait for shutdown
        while self.running:
            await asyncio.sleep(1)

    async def setup_broker_adapters(self):
        """Set up broker adapters for order execution."""
        try:
            # Configure brokers based on config
            broker_configs = self.config.get("brokers", {})

            for broker_type_str, broker_config in broker_configs.items():
                try:
                    broker_type = BrokerType(broker_type_str)

                    # Create adapter
                    adapter = BrokerAdapterFactory.create_adapter(
                        broker_type, broker_config
                    )

                    # Initialize and connect
                    if await adapter.initialize():
                        if await adapter.connect():
                            if await adapter.authenticate(
                                broker_config.get("credentials", {})
                            ):
                                self.broker_adapters[broker_type] = adapter

                                # Set up message handlers
                                adapter.add_message_handler(
                                    "ORDER_RESPONSE", self.handle_order_response
                                )
                                adapter.add_message_handler(
                                    "EXECUTION_REPORT", self.handle_execution_report
                                )
                                adapter.add_error_handler(self.handle_broker_error)

                                self.logger.info(
                                    f"Connected to {broker_type.value} broker"
                                )
                            else:
                                self.logger.error(
                                    f"Failed to authenticate with {broker_type.value}"
                                )
                        else:
                            self.logger.error(
                                f"Failed to connect to {broker_type.value}"
                            )
                    else:
                        self.logger.error(
                            f"Failed to initialize {broker_type.value} adapter"
                        )

                except Exception as e:
                    self.logger.error(
                        f"Error setting up {broker_type_str} adapter: {e}"
                    )

            if not self.broker_adapters:
                self.logger.warning(
                    "No broker adapters connected - running in simulation mode"
                )

        except Exception as e:
            self.logger.error(f"Error setting up broker adapters: {e}")

    async def setup_rabbitmq(self):
        """Set up RabbitMQ exchanges and queues."""
        # Declare exchanges
        await self.rabbitmq_channel.declare_exchange(
            Exchanges.SIGNALS, type="topic", durable=True
        )

        await self.rabbitmq_channel.declare_exchange(
            Exchanges.MARKET_DATA, type="topic", durable=True
        )

        await self.rabbitmq_channel.declare_exchange(
            Exchanges.TRADES, type="topic", durable=True
        )

        # Declare entry queue
        await self.rabbitmq_channel.declare_queue(
            Queues.TRADE_ENTRY_QUEUE,
            durable=True,
            arguments={"x-max-priority": 10, "x-message-ttl": 60000},  # 1 minute
        )

        self.logger.info("RabbitMQ setup complete")

    async def validated_signals_consumer(self):
        """Consume validated signals for entry execution."""
        queue = await self.rabbitmq_channel.get_queue(Queues.TRADE_ENTRY_QUEUE)

        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process():
                    try:
                        signal_data = json.loads(message.body.decode())
                        await self.process_validated_signal(signal_data)

                    except Exception as e:
                        self.logger.error(f"Error processing validated signal: {e}")
                        await self.log_error(e, {"message": str(message.body)})

    async def market_data_consumer(self):
        """Consume 1-minute market data for entry timing."""
        # Subscribe to 1-minute market data
        queue_name = "entry_manager_market_data"

        # Create temporary queue for market data
        queue = await self.rabbitmq_channel.declare_queue(
            queue_name, durable=False, auto_delete=True
        )

        # Bind to market data
        await queue.bind(Exchanges.MARKET_DATA, "market.1min.*")
        await queue.bind(Exchanges.MARKET_DATA, "market.tick.*")

        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process():
                    try:
                        market_data = json.loads(message.body.decode())
                        await self.process_market_data(market_data)

                    except Exception as e:
                        self.logger.error(f"Error processing market data: {e}")

    async def process_validated_signal(self, signal_data: Dict[str, Any]):
        """Process a validated trading signal for entry execution.

        Args:
            signal_data: Validated signal from LLM analyzer
        """
        try:
            signal_id = signal_data.get("signal_id")
            symbol = signal_data.get("symbol")
            validation = signal_data.get("validation", {})

            if not signal_id or not symbol:
                self.logger.warning("Invalid signal data - missing ID or symbol")
                return

            # Check if signal is valid and above confidence threshold
            if not validation.get("valid", False):
                self.logger.debug(f"Signal {signal_id} not valid, skipping")
                return

            enhanced_confidence = validation.get("enhanced_confidence", 0)
            if enhanced_confidence < self.min_signal_confidence:
                self.logger.debug(
                    f"Signal {signal_id} confidence too low: {enhanced_confidence}"
                )
                return

            # Check if we're already at max concurrent entries
            if len(self.pending_entries) >= self.max_concurrent_entries:
                self.logger.warning(
                    f"Max concurrent entries reached, deferring signal {signal_id}"
                )
                await self.defer_signal(signal_data)
                return

            # Store validated signal
            self.validated_signals[signal_id] = signal_data

            # Start entry analysis
            await self.analyze_entry_opportunity(signal_data)

            self.logger.info(f"Processing validated signal: {signal_id} for {symbol}")

        except Exception as e:
            self.logger.error(f"Error processing validated signal: {e}")
            await self.log_error(e, {"signal_data": signal_data})

    async def analyze_entry_opportunity(self, signal_data: Dict[str, Any]):
        """Analyze entry opportunity and timing.

        Args:
            signal_data: Validated signal data
        """
        try:
            signal_id = signal_data.get("signal_id")
            symbol = signal_data.get("symbol")

            # Get current market conditions
            market_conditions = await self.get_current_market_conditions(symbol)

            if not market_conditions:
                self.logger.warning(f"No market data available for {symbol}")
                return

            # Analyze entry timing
            entry_analysis = await self.entry_analyzer.analyze_entry_timing(
                signal_data, market_conditions
            )

            # Calculate optimal entry parameters
            entry_params = await self.calculate_entry_parameters(
                signal_data, entry_analysis, market_conditions
            )

            # Check if entry should be immediate or wait for better timing
            if entry_analysis.get("immediate_entry", False):
                await self.execute_immediate_entry(signal_data, entry_params)
            else:
                await self.schedule_timed_entry(
                    signal_data, entry_params, entry_analysis
                )

        except Exception as e:
            self.logger.error(f"Error analyzing entry opportunity: {e}")
            await self.log_error(e, {"signal_data": signal_data})

    async def calculate_entry_parameters(
        self,
        signal_data: Dict[str, Any],
        entry_analysis: Dict[str, Any],
        market_conditions: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Calculate precise entry parameters.

        Args:
            signal_data: Signal information
            entry_analysis: Entry timing analysis
            market_conditions: Current market conditions

        Returns:
            Entry parameters including size, price, stops
        """
        try:
            symbol = signal_data.get("symbol")
            direction = signal_data.get("direction")

            # Get account information for position sizing
            account_info = await self.get_account_info()

            # Calculate position size based on risk
            risk_amount = account_info["equity"] * self.risk_per_trade

            position_size = await self.risk_calculator.calculate_position_size(
                symbol=symbol,
                direction=direction,
                risk_amount=risk_amount,
                entry_price=signal_data.get("entry_price"),
                stop_loss=signal_data.get("stop_loss"),
                market_conditions=market_conditions,
            )

            # Optimize entry price based on current market
            optimized_entry = await self.timing_optimizer.optimize_entry_price(
                signal_data, market_conditions, entry_analysis
            )

            # Calculate dynamic stops based on current volatility
            dynamic_stops = await self.risk_calculator.calculate_dynamic_stops(
                symbol=symbol,
                entry_price=optimized_entry["price"],
                direction=direction,
                market_conditions=market_conditions,
                signal_confidence=signal_data.get("validation", {}).get(
                    "enhanced_confidence", 0.5
                ),
            )

            return {
                "position_size": position_size,
                "entry_price": optimized_entry["price"],
                "order_type": optimized_entry["order_type"],
                "stop_loss": dynamic_stops["stop_loss"],
                "take_profit_1": dynamic_stops["take_profit_1"],
                "take_profit_2": dynamic_stops["take_profit_2"],
                "take_profit_3": dynamic_stops["take_profit_3"],
                "time_in_force": TimeInForce.GTC,
                "slippage_tolerance": optimized_entry.get("slippage_tolerance", 0.0001),
                "max_wait_time": entry_analysis.get("max_wait_time", 60),  # seconds
                "priority": self._calculate_entry_priority(signal_data, entry_analysis),
            }

        except Exception as e:
            self.logger.error(f"Error calculating entry parameters: {e}")
            return {}

    async def execute_immediate_entry(
        self, signal_data: Dict[str, Any], entry_params: Dict[str, Any]
    ):
        """Execute immediate market entry.

        Args:
            signal_data: Signal data
            entry_params: Calculated entry parameters
        """
        try:
            signal_id = signal_data.get("signal_id")
            symbol = signal_data.get("symbol")
            direction = signal_data.get("direction")

            # Create market order
            order_request = BrokerMessageFactory.create_market_order(
                broker_type=self.default_broker,
                account_id=self.config.get("account_id", "default"),
                symbol=symbol,
                side=OrderSide.BUY if direction == "BUY" else OrderSide.SELL,
                quantity=entry_params["position_size"],
                signal_id=signal_id,
                stop_loss_price=entry_params["stop_loss"],
                take_profit_price=entry_params["take_profit_1"],
                metadata={
                    "entry_type": "immediate",
                    "signal_confidence": signal_data.get("validation", {}).get(
                        "enhanced_confidence"
                    ),
                    "risk_amount": entry_params.get("risk_amount"),
                    "entry_reason": "immediate_execution",
                },
            )

            # Execute order
            await self.submit_order(order_request, entry_params)

            # Track as pending entry
            self.pending_entries[signal_id] = {
                "signal_data": signal_data,
                "entry_params": entry_params,
                "order_request": order_request,
                "entry_time": datetime.utcnow(),
                "status": "submitted",
            }

            self.logger.info(f"Executed immediate entry for signal {signal_id}")

        except Exception as e:
            self.logger.error(f"Error executing immediate entry: {e}")
            await self.log_error(
                e, {"signal_data": signal_data, "entry_params": entry_params}
            )

    async def schedule_timed_entry(
        self,
        signal_data: Dict[str, Any],
        entry_params: Dict[str, Any],
        entry_analysis: Dict[str, Any],
    ):
        """Schedule entry for optimal timing.

        Args:
            signal_data: Signal data
            entry_params: Entry parameters
            entry_analysis: Timing analysis
        """
        try:
            signal_id = signal_data.get("signal_id")

            # Add to pending entries for monitoring
            self.pending_entries[signal_id] = {
                "signal_data": signal_data,
                "entry_params": entry_params,
                "entry_analysis": entry_analysis,
                "scheduled_time": datetime.utcnow(),
                "status": "waiting_for_timing",
                "entry_conditions": entry_analysis.get("entry_conditions", {}),
                "timeout": datetime.utcnow()
                + timedelta(seconds=entry_params.get("max_wait_time", 60)),
            }

            self.logger.info(f"Scheduled timed entry for signal {signal_id}")

        except Exception as e:
            self.logger.error(f"Error scheduling timed entry: {e}")

    async def entry_timing_loop(self):
        """Monitor pending entries for optimal timing."""
        while self.running:
            try:
                current_time = datetime.utcnow()
                entries_to_execute = []
                entries_to_timeout = []

                # Check all pending entries
                for signal_id, entry_data in list(self.pending_entries.items()):
                    if entry_data.get("status") != "waiting_for_timing":
                        continue

                    # Check timeout
                    if current_time > entry_data.get("timeout", current_time):
                        entries_to_timeout.append(signal_id)
                        continue

                    # Check entry conditions
                    symbol = entry_data["signal_data"].get("symbol")
                    market_conditions = await self.get_current_market_conditions(symbol)

                    if market_conditions:
                        should_enter = (
                            await self.timing_optimizer.check_entry_conditions(
                                entry_data["entry_conditions"], market_conditions
                            )
                        )

                        if should_enter:
                            entries_to_execute.append(signal_id)

                # Execute ready entries
                for signal_id in entries_to_execute:
                    entry_data = self.pending_entries[signal_id]
                    await self.execute_timed_entry(entry_data)

                # Handle timeouts
                for signal_id in entries_to_timeout:
                    await self.handle_entry_timeout(signal_id)

                # Sleep briefly
                await asyncio.sleep(1)

            except Exception as e:
                self.logger.error(f"Error in entry timing loop: {e}")
                await asyncio.sleep(5)

    async def execute_timed_entry(self, entry_data: Dict[str, Any]):
        """Execute a timed entry when conditions are met."""
        try:
            signal_data = entry_data["signal_data"]
            entry_params = entry_data["entry_params"]
            signal_id = signal_data.get("signal_id")
            symbol = signal_data.get("symbol")
            direction = signal_data.get("direction")

            # Update entry price based on current market
            current_market = await self.get_current_market_conditions(symbol)
            optimized_price = await self.timing_optimizer.get_optimal_entry_price(
                entry_params, current_market
            )

            # Create limit order for precise entry
            order_request = BrokerMessageFactory.create_limit_order(
                broker_type=self.default_broker,
                account_id=self.config.get("account_id", "default"),
                symbol=symbol,
                side=OrderSide.BUY if direction == "BUY" else OrderSide.SELL,
                quantity=entry_params["position_size"],
                price=optimized_price,
                signal_id=signal_id,
                time_in_force=TimeInForce.IOC,  # Immediate or Cancel for timing precision
                metadata={
                    "entry_type": "timed",
                    "signal_confidence": signal_data.get("validation", {}).get(
                        "enhanced_confidence"
                    ),
                    "wait_time": (
                        datetime.utcnow()
                        - entry_data.get("scheduled_time", datetime.utcnow())
                    ).total_seconds(),
                    "entry_reason": "optimal_timing_conditions",
                },
            )

            # Execute order
            await self.submit_order(order_request, entry_params)

            # Update entry status
            entry_data["status"] = "submitted"
            entry_data["order_request"] = order_request
            entry_data["execution_time"] = datetime.utcnow()

            self.logger.info(f"Executed timed entry for signal {signal_id}")

        except Exception as e:
            self.logger.error(f"Error executing timed entry: {e}")

    async def submit_order(
        self, order_request: OrderRequest, entry_params: Dict[str, Any]
    ):
        """Submit order to appropriate broker.

        Args:
            order_request: Order to submit
            entry_params: Entry parameters for context
        """
        try:
            # Select broker (could implement broker routing logic here)
            broker_adapter = self.broker_adapters.get(self.default_broker)

            if not broker_adapter:
                # Simulation mode - create mock response
                await self.handle_simulation_order(order_request, entry_params)
                return

            # Submit to broker
            response = await broker_adapter.submit_order(order_request)

            self.logger.info(f"Order submitted: {order_request.client_order_id}")

        except Exception as e:
            self.logger.error(f"Error submitting order: {e}")
            await self.log_error(e, {"order_request": order_request.dict()})

    async def handle_simulation_order(
        self, order_request: OrderRequest, entry_params: Dict[str, Any]
    ):
        """Handle order in simulation mode."""
        # Create simulated execution
        execution_price = order_request.price or entry_params.get(
            "entry_price", Decimal("1.0000")
        )

        # Simulate slight slippage
        slippage = (
            Decimal("0.0001")
            if order_request.order_type == OrderType.MARKET
            else Decimal("0")
        )

        if order_request.side == OrderSide.BUY:
            fill_price = execution_price + slippage
        else:
            fill_price = execution_price - slippage

        # Create execution report
        execution_data = {
            "client_order_id": order_request.client_order_id,
            "symbol": order_request.symbol,
            "side": order_request.side.value,
            "quantity": float(order_request.quantity),
            "fill_price": float(fill_price),
            "fill_time": datetime.utcnow().isoformat(),
            "status": "filled",
            "simulation": True,
        }

        # Emit execution to trade manager
        await self.publish_message(
            Exchanges.TRADES,
            format_routing_key(RoutingKeys.TRADE_EXECUTED, symbol=order_request.symbol),
            execution_data,
        )

        self.logger.info(f"Simulated order execution: {order_request.client_order_id}")

    # Message handlers

    async def handle_order_response(self, response):
        """Handle order response from broker."""
        try:
            client_order_id = response.client_order_id

            # Update pending entry status
            for signal_id, entry_data in self.pending_entries.items():
                if (
                    entry_data.get("order_request", {}).get("client_order_id")
                    == client_order_id
                ):
                    entry_data["status"] = response.status.value.lower()
                    entry_data["broker_response"] = response
                    break

            self.logger.info(f"Order response: {client_order_id} - {response.status}")

        except Exception as e:
            self.logger.error(f"Error handling order response: {e}")

    async def handle_execution_report(self, execution):
        """Handle execution report from broker."""
        try:
            client_order_id = execution.client_order_id

            # Find corresponding entry
            signal_id = None
            for sid, entry_data in self.pending_entries.items():
                if (
                    entry_data.get("order_request", {}).get("client_order_id")
                    == client_order_id
                ):
                    signal_id = sid
                    break

            if signal_id:
                # Move to executed entries
                entry_data = self.pending_entries.pop(signal_id)
                entry_data["execution"] = execution
                entry_data["final_status"] = "executed"
                self.executed_entries[signal_id] = entry_data

                # Calculate timing score
                timing_score = self._calculate_timing_score(entry_data, execution)
                self.timing_scores.append(timing_score)

                # Update metrics
                self.entries_executed += 1

                # Publish execution to trade manager
                await self.publish_execution_to_trade_manager(
                    signal_id, entry_data, execution
                )

                self.logger.info(f"Entry executed: {signal_id}")

        except Exception as e:
            self.logger.error(f"Error handling execution report: {e}")

    async def handle_broker_error(self, error):
        """Handle broker error."""
        self.logger.error(f"Broker error: {error.error_code} - {error.error_message}")

        # Handle order-specific errors
        if error.related_order_id:
            # Find and handle failed entry
            for signal_id, entry_data in list(self.pending_entries.items()):
                if (
                    entry_data.get("order_request", {}).get("client_order_id")
                    == error.related_order_id
                ):
                    await self.handle_entry_failure(signal_id, str(error.error_message))
                    break

    # Helper methods

    async def get_current_market_conditions(
        self, symbol: str
    ) -> Optional[Dict[str, Any]]:
        """Get current market conditions for a symbol."""
        try:
            # Get latest 1-minute data
            market_1m = self.market_data_1m.get(symbol, [])
            if not market_1m:
                return None

            latest_1m = market_1m[-1]

            # Get recent tick data for spread
            ticks_5s = self.market_data_5s.get(symbol, [])

            return {
                "symbol": symbol,
                "current_price": latest_1m.get("close"),
                "bid": latest_1m.get("bid", latest_1m.get("close")),
                "ask": latest_1m.get("ask", latest_1m.get("close")),
                "spread": latest_1m.get("spread", 0.0001),
                "volume": latest_1m.get("volume", 0),
                "volatility": self._calculate_short_term_volatility(market_1m),
                "trend": self._calculate_short_term_trend(market_1m),
                "timestamp": latest_1m.get("time"),
                "tick_data": ticks_5s[-10:] if len(ticks_5s) >= 10 else ticks_5s,
            }

        except Exception as e:
            self.logger.error(f"Error getting market conditions: {e}")
            return None

    async def get_account_info(self) -> Dict[str, Any]:
        """Get account information from broker or cache."""
        try:
            # Try to get from broker
            if self.broker_adapters:
                adapter = list(self.broker_adapters.values())[0]
                account_report = await adapter.get_account_info()

                return {
                    "equity": float(account_report.equity),
                    "balance": float(account_report.cash_balance),
                    "margin_used": float(account_report.initial_margin),
                    "margin_available": float(account_report.available_margin),
                }
            else:
                # Simulation defaults
                return {
                    "equity": 100000.0,
                    "balance": 100000.0,
                    "margin_used": 0.0,
                    "margin_available": 400000.0,
                }

        except Exception as e:
            self.logger.error(f"Error getting account info: {e}")
            return {
                "equity": 100000.0,
                "balance": 100000.0,
                "margin_used": 0.0,
                "margin_available": 400000.0,
            }

    # Additional helper methods would continue here...

    def _calculate_entry_priority(
        self, signal_data: Dict[str, Any], entry_analysis: Dict[str, Any]
    ) -> int:
        """Calculate entry priority for queue ordering."""
        base_priority = MessagePriority.NORMAL

        # Higher priority for higher confidence
        confidence = signal_data.get("validation", {}).get("enhanced_confidence", 0.5)
        if confidence > 0.8:
            base_priority = MessagePriority.HIGH
        elif confidence > 0.9:
            base_priority = MessagePriority.CRITICAL

        # Adjust for urgency
        if entry_analysis.get("time_sensitive", False):
            base_priority = min(base_priority + 2, MessagePriority.CRITICAL)

        return base_priority

    def _calculate_timing_score(self, entry_data: Dict[str, Any], execution) -> float:
        """Calculate timing score for performance tracking."""
        try:
            # Compare actual execution to optimal timing
            scheduled_time = entry_data.get("scheduled_time")
            execution_time = execution.transaction_time

            if scheduled_time:
                delay = (execution_time - scheduled_time).total_seconds()
                # Score decreases with delay
                timing_score = max(
                    0, 1.0 - (delay / 60.0)
                )  # Perfect score if executed within 1 minute
            else:
                timing_score = 0.8  # Default for immediate entries

            # Adjust for slippage
            expected_price = entry_data.get("entry_params", {}).get("entry_price", 0)
            actual_price = execution.last_price

            if expected_price and actual_price:
                slippage_ratio = abs(float(actual_price - expected_price)) / float(
                    expected_price
                )
                slippage_penalty = min(slippage_ratio * 10, 0.3)  # Max 30% penalty
                timing_score = max(0, timing_score - slippage_penalty)

            return timing_score

        except Exception as e:
            self.logger.error(f"Error calculating timing score: {e}")
            return 0.5

    async def process_market_data(self, market_data: Dict[str, Any]):
        """Process incoming market data for timing analysis."""
        try:
            symbol = market_data.get("symbol")
            timeframe = market_data.get("timeframe", "1m")

            if not symbol:
                return

            # Store 1-minute data
            if timeframe == "1m":
                if symbol not in self.market_data_1m:
                    self.market_data_1m[symbol] = []

                self.market_data_1m[symbol].append(market_data.get("data", {}))

                # Keep only last 100 bars
                if len(self.market_data_1m[symbol]) > 100:
                    self.market_data_1m[symbol] = self.market_data_1m[symbol][-100:]

            # Store tick data as 5-second aggregates
            elif "tick" in timeframe or timeframe == "5s":
                if symbol not in self.market_data_5s:
                    self.market_data_5s[symbol] = []

                # Add ticks or 5s data
                ticks = market_data.get("ticks", [market_data.get("data", {})])
                self.market_data_5s[symbol].extend(ticks)

                # Keep only last 1000 ticks
                if len(self.market_data_5s[symbol]) > 1000:
                    self.market_data_5s[symbol] = self.market_data_5s[symbol][-1000:]

        except Exception as e:
            self.logger.error(f"Error processing market data: {e}")

    def _calculate_short_term_volatility(
        self, price_data: List[Dict[str, Any]]
    ) -> float:
        """Calculate short-term volatility from recent price data."""
        try:
            if len(price_data) < 10:
                return 0.001  # Default volatility

            # Calculate returns
            returns = []
            for i in range(1, len(price_data)):
                prev_close = price_data[i - 1].get("close", 0)
                curr_close = price_data[i].get("close", 0)

                if prev_close > 0:
                    returns.append((curr_close - prev_close) / prev_close)

            if returns:
                import statistics

                return statistics.stdev(returns)
            else:
                return 0.001

        except Exception:
            return 0.001

    def _calculate_short_term_trend(self, price_data: List[Dict[str, Any]]) -> str:
        """Calculate short-term trend from recent price data."""
        try:
            if len(price_data) < 5:
                return "neutral"

            recent_closes = [bar.get("close", 0) for bar in price_data[-5:]]

            if recent_closes[-1] > recent_closes[0] * 1.001:
                return "up"
            elif recent_closes[-1] < recent_closes[0] * 0.999:
                return "down"
            else:
                return "neutral"

        except Exception:
            return "neutral"

    async def defer_signal(self, signal_data: Dict[str, Any]):
        """Defer signal when at max capacity."""
        # Could implement priority queue or defer to later
        pass

    async def handle_entry_timeout(self, signal_id: str):
        """Handle entry timeout."""
        entry_data = self.pending_entries.pop(signal_id, None)
        if entry_data:
            self.logger.warning(f"Entry timeout for signal {signal_id}")

            # Could implement fallback to market order or cancel
            await self.log_event(
                "entry_timeout",
                f"Entry timed out for signal {signal_id}",
                {"signal_id": signal_id, "timeout_reason": "conditions_not_met"},
            )

    async def handle_entry_failure(self, signal_id: str, reason: str):
        """Handle entry execution failure."""
        entry_data = self.pending_entries.pop(signal_id, None)
        if entry_data:
            self.logger.error(f"Entry failed for signal {signal_id}: {reason}")

            await self.log_event(
                "entry_failure",
                f"Entry failed for signal {signal_id}",
                {"signal_id": signal_id, "failure_reason": reason},
            )

    async def publish_execution_to_trade_manager(
        self, signal_id: str, entry_data: Dict[str, Any], execution
    ):
        """Publish successful execution to trade manager."""
        trade_data = {
            "signal_id": signal_id,
            "entry_execution": {
                "client_order_id": execution.client_order_id,
                "broker_order_id": execution.broker_order_id,
                "symbol": execution.symbol,
                "side": execution.side.value,
                "quantity": float(execution.last_quantity),
                "fill_price": float(execution.last_price),
                "fill_time": execution.transaction_time.isoformat(),
                "commission": (
                    float(execution.commission) if execution.commission else 0
                ),
            },
            "trade_parameters": {
                "stop_loss": float(entry_data["entry_params"]["stop_loss"]),
                "take_profit_1": float(entry_data["entry_params"]["take_profit_1"]),
                "take_profit_2": float(
                    entry_data["entry_params"].get("take_profit_2", 0)
                ),
                "take_profit_3": float(
                    entry_data["entry_params"].get("take_profit_3", 0)
                ),
            },
            "signal_data": entry_data["signal_data"],
        }

        await self.publish_message(
            Exchanges.TRADES,
            format_routing_key(RoutingKeys.TRADE_EXECUTED, symbol=execution.symbol),
            trade_data,
        )

    async def execution_monitor_loop(self):
        """Monitor execution status and cleanup completed entries."""
        while self.running:
            try:
                current_time = datetime.utcnow()

                # Cleanup old executed entries (keep for 1 hour)
                cleanup_time = current_time - timedelta(hours=1)

                old_entries = [
                    signal_id
                    for signal_id, entry_data in self.executed_entries.items()
                    if entry_data.get("execution_time", current_time) < cleanup_time
                ]

                for signal_id in old_entries:
                    del self.executed_entries[signal_id]

                if old_entries:
                    self.logger.debug(f"Cleaned up {len(old_entries)} old entries")

                await asyncio.sleep(300)  # Check every 5 minutes

            except Exception as e:
                self.logger.error(f"Error in execution monitor loop: {e}")
                await asyncio.sleep(60)

    async def heartbeat_loop(self):
        """Send periodic heartbeats and metrics."""
        while self.running:
            try:
                # Calculate metrics
                avg_timing_score = (
                    sum(self.timing_scores[-100:]) / len(self.timing_scores[-100:])
                    if self.timing_scores
                    else 0
                )

                # Send heartbeat
                await self.publish_message(
                    Exchanges.SYSTEM,
                    format_routing_key(
                        RoutingKeys.SYSTEM_HEARTBEAT, service=self.service_name
                    ),
                    {
                        "pending_entries": len(self.pending_entries),
                        "executed_entries": self.entries_executed,
                        "avg_timing_score": avg_timing_score,
                        "connected_brokers": list(self.broker_adapters.keys()),
                        "health": await self.health_check(),
                    },
                )

                # Send metrics
                await self.publish_message(
                    Exchanges.SYSTEM,
                    format_routing_key(
                        RoutingKeys.SYSTEM_METRICS, service=self.service_name
                    ),
                    {
                        "entries_executed_total": self.entries_executed,
                        "avg_timing_score": avg_timing_score,
                        "pending_entries_count": len(self.pending_entries),
                        "broker_connections": len(self.broker_adapters),
                    },
                )

                await asyncio.sleep(30)

            except Exception as e:
                self.logger.error(f"Error in heartbeat loop: {e}")
                await asyncio.sleep(30)


if __name__ == "__main__":
    # Load configuration
    config = ServiceConfig.from_env()

    # Add broker configuration
    config.update(
        {
            "brokers": {
                "INTERACTIVE_BROKERS": {
                    "host": config.get("ib_gateway_host", "127.0.0.1"),
                    "port": config.get("ib_gateway_port", 7497),
                    "client_id": config.get("ib_client_id", 2),
                    "credentials": {},
                }
            },
            "account_id": "DU123456",
            "risk_per_trade": 0.02,
            "max_concurrent_entries": 5,
        }
    )

    # Create and run service
    service = EntryManagerService(config)
    asyncio.run(service.run())
