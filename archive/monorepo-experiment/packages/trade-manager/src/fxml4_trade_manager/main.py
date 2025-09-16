"""Trade Manager Service - Position management, exits, and P&L tracking."""

import asyncio
import sys
from pathlib import Path

# Add parent directories to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional, Tuple
import json
import logging
from decimal import Decimal
from enum import Enum

from shared.utils.base_service import BaseService, ServiceConfig
from shared.config.rabbitmq_config import (
    Exchanges, Queues, RoutingKeys, format_routing_key
)
from shared.schemas.broker_messages import (
    OrderRequest, OrderResponse, OrderModifyRequest, BrokerType, 
    OrderSide, OrderType, TimeInForce, BrokerMessageFactory
)
from shared.brokers.base_broker_adapter import BrokerAdapterFactory

from position_manager import PositionManager
from exit_strategy_manager import ExitStrategyManager
from risk_monitor import RiskMonitor
from pnl_tracker import PnLTracker


class TradeStatus(str, Enum):
    """Trade lifecycle status."""
    OPEN = "open"
    CLOSING = "closing"
    CLOSED = "closed"
    STOPPED = "stopped"
    EXPIRED = "expired"


class Trade:
    """Trade object representing a position."""
    
    def __init__(self, trade_data: Dict[str, Any]):
        self.trade_id = trade_data.get('trade_id')
        self.signal_id = trade_data.get('signal_id')
        self.symbol = trade_data.get('symbol')
        self.side = trade_data.get('side')
        self.entry_time = trade_data.get('entry_time')
        self.entry_price = Decimal(str(trade_data.get('entry_price', 0)))
        self.position_size = Decimal(str(trade_data.get('position_size', 0)))
        self.status = TradeStatus(trade_data.get('status', TradeStatus.OPEN))
        
        # Exit parameters
        self.stop_loss = Decimal(str(trade_data.get('stop_loss', 0)))
        self.take_profit_1 = Decimal(str(trade_data.get('take_profit_1', 0)))
        self.take_profit_2 = Decimal(str(trade_data.get('take_profit_2', 0)))
        self.take_profit_3 = Decimal(str(trade_data.get('take_profit_3', 0)))
        
        # Tracking
        self.exit_time = trade_data.get('exit_time')
        self.exit_price = Decimal(str(trade_data.get('exit_price', 0))) if trade_data.get('exit_price') else None
        self.realized_pnl = Decimal(str(trade_data.get('realized_pnl', 0)))
        self.unrealized_pnl = Decimal(str(trade_data.get('unrealized_pnl', 0)))
        
        # Management
        self.trailing_stop_active = trade_data.get('trailing_stop_active', False)
        self.trailing_stop_distance = Decimal(str(trade_data.get('trailing_stop_distance', 0)))
        self.partial_exits = trade_data.get('partial_exits', [])
        self.metadata = trade_data.get('metadata', {})


class TradeManagerService(BaseService):
    """Trade Manager Service for position lifecycle management."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__("trade-manager", config)
        
        # Core components
        self.position_manager = PositionManager()
        self.exit_strategy_manager = ExitStrategyManager()
        self.risk_monitor = RiskMonitor()
        self.pnl_tracker = PnLTracker()
        
        # Broker management
        self.broker_adapters: Dict[BrokerType, Any] = {}
        self.default_broker = BrokerType.INTERACTIVE_BROKERS
        
        # Trade tracking
        self.active_trades: Dict[str, Trade] = {}
        self.closed_trades: Dict[str, Trade] = {}
        self.trade_history: List[Trade] = []
        
        # Market data cache
        self.market_prices: Dict[str, Dict[str, Any]] = {}
        self.market_data_1m: Dict[str, List[Dict[str, Any]]] = {}
        
        # Configuration
        self.max_positions = config.get('max_positions', 10)
        self.max_daily_loss = config.get('max_daily_loss', 0.05)  # 5%
        self.trailing_stop_activation = config.get('trailing_stop_activation', 0.01)  # 1%
        self.partial_exit_levels = config.get('partial_exit_levels', [0.33, 0.33, 0.34])
        
        # Performance tracking
        self.daily_pnl = Decimal('0')
        self.total_pnl = Decimal('0')
        self.win_count = 0
        self.loss_count = 0
        self.max_drawdown = Decimal('0')
        
        # Risk management state
        self.trading_enabled = True
        self.daily_loss_limit_hit = False
        
    async def service_setup(self):
        """Set up trade manager service."""
        # Initialize broker adapters
        await self.setup_broker_adapters()
        
        # Initialize components
        await self.position_manager.initialize()
        await self.exit_strategy_manager.initialize()
        await self.risk_monitor.initialize()
        await self.pnl_tracker.initialize()
        
        # Set up RabbitMQ
        await self.setup_rabbitmq()
        
        # Load existing positions from database
        await self.load_existing_positions()
        
        self.logger.info("Trade Manager service initialized")
    
    async def service_teardown(self):
        """Clean up resources."""
        # Save state before shutdown
        await self.save_positions_state()
        
        # Disconnect broker adapters
        for adapter in self.broker_adapters.values():
            await adapter.cleanup()
    
    async def service_run(self):
        """Main service loop."""
        # Start processing tasks
        self.add_task(self.trade_execution_consumer())
        self.add_task(self.market_data_consumer())
        self.add_task(self.position_monitoring_loop())
        self.add_task(self.risk_management_loop())
        self.add_task(self.performance_tracking_loop())
        self.add_task(self.heartbeat_loop())
        
        # Wait for shutdown
        while self.running:
            await asyncio.sleep(1)
    
    async def setup_broker_adapters(self):
        """Set up broker adapters for position management."""
        try:
            broker_configs = self.config.get('brokers', {})
            
            for broker_type_str, broker_config in broker_configs.items():
                try:
                    broker_type = BrokerType(broker_type_str)
                    adapter = BrokerAdapterFactory.create_adapter(broker_type, broker_config)
                    
                    if await adapter.initialize():
                        if await adapter.connect():
                            if await adapter.authenticate(broker_config.get('credentials', {})):
                                self.broker_adapters[broker_type] = adapter
                                
                                # Set up handlers
                                adapter.add_message_handler('EXECUTION_REPORT', self.handle_execution_report)
                                adapter.add_message_handler('ORDER_RESPONSE', self.handle_order_response)
                                adapter.add_error_handler(self.handle_broker_error)
                                
                                self.logger.info(f"Connected to {broker_type.value} broker")
                                
                except Exception as e:
                    self.logger.error(f"Error setting up {broker_type_str} adapter: {e}")
            
        except Exception as e:
            self.logger.error(f"Error setting up broker adapters: {e}")
    
    async def setup_rabbitmq(self):
        """Set up RabbitMQ exchanges and queues."""
        # Declare exchanges
        await self.rabbitmq_channel.declare_exchange(
            Exchanges.TRADES,
            type='topic',
            durable=True
        )
        
        await self.rabbitmq_channel.declare_exchange(
            Exchanges.MARKET_DATA,
            type='topic',
            durable=True
        )
        
        # Declare trade management queue
        await self.rabbitmq_channel.declare_queue(
            Queues.TRADE_MANAGEMENT,
            durable=True
        )
        
        self.logger.info("RabbitMQ setup complete")
    
    async def load_existing_positions(self):
        """Load existing open positions from database."""
        try:
            async with self.db_pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT * FROM trading.trades
                    WHERE status = 'open'
                    ORDER BY entry_time DESC
                """)
                
                for row in rows:
                    trade_data = dict(row)
                    trade = Trade(trade_data)
                    self.active_trades[trade.trade_id] = trade
                    
                    self.logger.info(f"Loaded open trade: {trade.trade_id}")
            
            self.logger.info(f"Loaded {len(self.active_trades)} existing positions")
            
        except Exception as e:
            self.logger.error(f"Error loading existing positions: {e}")
    
    async def trade_execution_consumer(self):
        """Consume trade execution messages from Entry Manager."""
        queue = await self.rabbitmq_channel.get_queue(Queues.TRADE_MANAGEMENT)
        
        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process():
                    try:
                        trade_data = json.loads(message.body.decode())
                        await self.process_trade_execution(trade_data)
                        
                    except Exception as e:
                        self.logger.error(f"Error processing trade execution: {e}")
                        await self.log_error(e, {"message": str(message.body)})
    
    async def market_data_consumer(self):
        """Consume market data for position monitoring."""
        # Create temporary queue
        queue_name = "trade_manager_market_data"
        queue = await self.rabbitmq_channel.declare_queue(
            queue_name,
            durable=False,
            auto_delete=True
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
    
    async def process_trade_execution(self, execution_data: Dict[str, Any]):
        """Process new trade execution from Entry Manager.
        
        Args:
            execution_data: Trade execution details
        """
        try:
            # Check if trading is enabled
            if not self.trading_enabled:
                self.logger.warning("Trading disabled - ignoring new execution")
                return
            
            # Check position limits
            if len(self.active_trades) >= self.max_positions:
                self.logger.warning(f"Max positions ({self.max_positions}) reached")
                await self.close_oldest_position()
            
            # Create new trade
            trade_id = execution_data.get('signal_id', str(uuid.uuid4()))
            
            trade_data = {
                'trade_id': trade_id,
                'signal_id': execution_data.get('signal_id'),
                'symbol': execution_data['entry_execution']['symbol'],
                'side': execution_data['entry_execution']['side'],
                'entry_time': datetime.now(timezone.utc),
                'entry_price': execution_data['entry_execution']['fill_price'],
                'position_size': execution_data['entry_execution']['quantity'],
                'stop_loss': execution_data['trade_parameters']['stop_loss'],
                'take_profit_1': execution_data['trade_parameters']['take_profit_1'],
                'take_profit_2': execution_data['trade_parameters'].get('take_profit_2', 0),
                'take_profit_3': execution_data['trade_parameters'].get('take_profit_3', 0),
                'status': TradeStatus.OPEN,
                'metadata': {
                    'order_id': execution_data['entry_execution']['client_order_id'],
                    'broker_order_id': execution_data['entry_execution']['broker_order_id'],
                    'signal_confidence': execution_data.get('signal_data', {}).get('confidence', 0)
                }
            }
            
            trade = Trade(trade_data)
            
            # Store in active trades
            self.active_trades[trade_id] = trade
            
            # Save to database
            await self.save_trade_to_db(trade)
            
            # Set up exit orders
            await self.setup_exit_orders(trade)
            
            # Initialize position monitoring
            await self.position_manager.add_position(trade)
            
            # Update P&L tracker
            await self.pnl_tracker.add_new_trade(trade)
            
            self.logger.info(f"New trade opened: {trade_id} - {trade.symbol} {trade.side}")
            
            # Emit trade opened event
            await self.emit_trade_event('trade_opened', trade)
            
        except Exception as e:
            self.logger.error(f"Error processing trade execution: {e}")
            await self.log_error(e, {'execution_data': execution_data})
    
    async def setup_exit_orders(self, trade: Trade):
        """Set up exit orders (stop loss and take profits) for a trade.
        
        Args:
            trade: Trade object
        """
        try:
            broker_adapter = self.broker_adapters.get(self.default_broker)
            if not broker_adapter:
                self.logger.warning("No broker adapter - skipping exit order setup")
                return
            
            # Create stop loss order
            if trade.stop_loss > 0:
                stop_order = BrokerMessageFactory.create_order_request(
                    broker_type=self.default_broker,
                    account_id=self.config.get('account_id', 'default'),
                    symbol=trade.symbol,
                    side=OrderSide.SELL if trade.side == 'BUY' else OrderSide.BUY,
                    quantity=trade.position_size,
                    order_type=OrderType.STOP,
                    stop_price=trade.stop_loss,
                    time_in_force=TimeInForce.GTC,
                    metadata={
                        'trade_id': trade.trade_id,
                        'exit_type': 'stop_loss',
                        'parent_order_id': trade.metadata.get('order_id')
                    }
                )
                
                response = await broker_adapter.submit_order(stop_order)
                trade.metadata['stop_order_id'] = response.client_order_id
            
            # Create take profit orders (if using OCO or bracket orders)
            # For now, we'll monitor and execute manually for flexibility
            
            self.logger.info(f"Exit orders set up for trade {trade.trade_id}")
            
        except Exception as e:
            self.logger.error(f"Error setting up exit orders: {e}")
    
    async def position_monitoring_loop(self):
        """Monitor active positions for exit conditions."""
        while self.running:
            try:
                for trade_id, trade in list(self.active_trades.items()):
                    if trade.status != TradeStatus.OPEN:
                        continue
                    
                    # Get current market price
                    current_price = await self.get_current_price(trade.symbol)
                    if not current_price:
                        continue
                    
                    # Update unrealized P&L
                    trade.unrealized_pnl = self.calculate_unrealized_pnl(trade, current_price)
                    
                    # Check exit conditions
                    exit_signal = await self.exit_strategy_manager.check_exit_conditions(
                        trade, current_price, self.market_data_1m.get(trade.symbol, [])
                    )
                    
                    if exit_signal:
                        await self.execute_exit(trade, exit_signal)
                    
                    # Check for trailing stop activation
                    elif await self.should_activate_trailing_stop(trade, current_price):
                        await self.activate_trailing_stop(trade, current_price)
                    
                    # Update trailing stop if active
                    elif trade.trailing_stop_active:
                        await self.update_trailing_stop(trade, current_price)
                    
                    # Check for partial exits
                    partial_exit = await self.check_partial_exit_levels(trade, current_price)
                    if partial_exit:
                        await self.execute_partial_exit(trade, partial_exit)
                
                # Brief sleep
                await asyncio.sleep(1)
                
            except Exception as e:
                self.logger.error(f"Error in position monitoring: {e}")
                await asyncio.sleep(5)
    
    async def risk_management_loop(self):
        """Monitor overall risk and enforce limits."""
        while self.running:
            try:
                # Calculate current risk metrics
                risk_metrics = await self.risk_monitor.calculate_risk_metrics(
                    self.active_trades,
                    self.market_prices
                )
                
                # Check daily loss limit
                if risk_metrics['daily_pnl'] < -self.max_daily_loss:
                    if not self.daily_loss_limit_hit:
                        self.daily_loss_limit_hit = True
                        self.trading_enabled = False
                        
                        self.logger.warning(f"Daily loss limit hit: {risk_metrics['daily_pnl']:.2%}")
                        
                        # Close all positions
                        await self.close_all_positions("Daily loss limit")
                        
                        # Send alert
                        await self.send_risk_alert("Daily loss limit exceeded", risk_metrics)
                
                # Check correlation risk
                if risk_metrics.get('correlation_risk', 0) > 0.8:
                    self.logger.warning("High correlation risk detected")
                    await self.reduce_correlated_exposure()
                
                # Check margin usage
                if risk_metrics.get('margin_usage', 0) > 0.9:
                    self.logger.warning("High margin usage - reducing positions")
                    await self.reduce_position_sizes()
                
                # Update max drawdown
                if risk_metrics['total_pnl'] < self.max_drawdown:
                    self.max_drawdown = risk_metrics['total_pnl']
                
                # Store risk metrics
                await self.store_risk_metrics(risk_metrics)
                
                # Sleep for 30 seconds
                await asyncio.sleep(30)
                
            except Exception as e:
                self.logger.error(f"Error in risk management: {e}")
                await asyncio.sleep(60)
    
    async def execute_exit(self, trade: Trade, exit_signal: Dict[str, Any]):
        """Execute trade exit based on exit signal.
        
        Args:
            trade: Trade to exit
            exit_signal: Exit signal details
        """
        try:
            trade.status = TradeStatus.CLOSING
            
            # Create exit order
            exit_order = BrokerMessageFactory.create_market_order(
                broker_type=self.default_broker,
                account_id=self.config.get('account_id', 'default'),
                symbol=trade.symbol,
                side=OrderSide.SELL if trade.side == 'BUY' else OrderSide.BUY,
                quantity=trade.position_size,
                metadata={
                    'trade_id': trade.trade_id,
                    'exit_type': exit_signal.get('exit_type', 'manual'),
                    'exit_reason': exit_signal.get('reason', 'unknown')
                }
            )
            
            # Submit exit order
            broker_adapter = self.broker_adapters.get(self.default_broker)
            if broker_adapter:
                response = await broker_adapter.submit_order(exit_order)
                trade.metadata['exit_order_id'] = response.client_order_id
            else:
                # Simulation mode
                await self.simulate_exit(trade, exit_signal)
            
            self.logger.info(f"Executing exit for trade {trade.trade_id}: {exit_signal.get('reason')}")
            
        except Exception as e:
            self.logger.error(f"Error executing exit: {e}")
            trade.status = TradeStatus.OPEN  # Revert status
    
    async def execute_partial_exit(self, trade: Trade, partial_exit: Dict[str, Any]):
        """Execute partial position exit.
        
        Args:
            trade: Trade to partially exit
            partial_exit: Partial exit details
        """
        try:
            exit_quantity = Decimal(str(partial_exit['quantity']))
            
            # Create partial exit order
            partial_order = BrokerMessageFactory.create_market_order(
                broker_type=self.default_broker,
                account_id=self.config.get('account_id', 'default'),
                symbol=trade.symbol,
                side=OrderSide.SELL if trade.side == 'BUY' else OrderSide.BUY,
                quantity=exit_quantity,
                metadata={
                    'trade_id': trade.trade_id,
                    'exit_type': 'partial',
                    'exit_level': partial_exit.get('level', 1),
                    'target_price': partial_exit.get('target_price')
                }
            )
            
            # Submit order
            broker_adapter = self.broker_adapters.get(self.default_broker)
            if broker_adapter:
                response = await broker_adapter.submit_order(partial_order)
                
                # Track partial exit
                trade.partial_exits.append({
                    'order_id': response.client_order_id,
                    'quantity': float(exit_quantity),
                    'target_price': float(partial_exit.get('target_price', 0)),
                    'timestamp': datetime.now(timezone.utc).isoformat()
                })
                
                # Update position size
                trade.position_size -= exit_quantity
            
            self.logger.info(f"Executing partial exit for trade {trade.trade_id}: {exit_quantity}")
            
        except Exception as e:
            self.logger.error(f"Error executing partial exit: {e}")
    
    async def should_activate_trailing_stop(self, trade: Trade, current_price: Decimal) -> bool:
        """Check if trailing stop should be activated.
        
        Args:
            trade: Trade to check
            current_price: Current market price
            
        Returns:
            True if trailing stop should be activated
        """
        if trade.trailing_stop_active:
            return False
        
        # Calculate profit percentage
        if trade.side == 'BUY':
            profit_pct = (current_price - trade.entry_price) / trade.entry_price
        else:
            profit_pct = (trade.entry_price - current_price) / trade.entry_price
        
        return profit_pct >= self.trailing_stop_activation
    
    async def activate_trailing_stop(self, trade: Trade, current_price: Decimal):
        """Activate trailing stop for a trade.
        
        Args:
            trade: Trade to activate trailing stop for
            current_price: Current market price
        """
        try:
            # Calculate trailing distance (e.g., 50% of current profit)
            if trade.side == 'BUY':
                profit = current_price - trade.entry_price
                trailing_distance = profit * Decimal('0.5')
                new_stop = current_price - trailing_distance
            else:
                profit = trade.entry_price - current_price
                trailing_distance = profit * Decimal('0.5')
                new_stop = current_price + trailing_distance
            
            # Update stop loss
            trade.trailing_stop_active = True
            trade.trailing_stop_distance = trailing_distance
            trade.stop_loss = new_stop
            
            # Modify stop order if exists
            await self.modify_stop_order(trade, new_stop)
            
            self.logger.info(f"Trailing stop activated for trade {trade.trade_id} at {new_stop}")
            
            # Emit event
            await self.emit_trade_event('trailing_stop_activated', trade)
            
        except Exception as e:
            self.logger.error(f"Error activating trailing stop: {e}")
    
    async def update_trailing_stop(self, trade: Trade, current_price: Decimal):
        """Update trailing stop based on current price.
        
        Args:
            trade: Trade with active trailing stop
            current_price: Current market price
        """
        try:
            if trade.side == 'BUY':
                new_stop = current_price - trade.trailing_stop_distance
                if new_stop > trade.stop_loss:
                    trade.stop_loss = new_stop
                    await self.modify_stop_order(trade, new_stop)
            else:
                new_stop = current_price + trade.trailing_stop_distance
                if new_stop < trade.stop_loss:
                    trade.stop_loss = new_stop
                    await self.modify_stop_order(trade, new_stop)
                    
        except Exception as e:
            self.logger.error(f"Error updating trailing stop: {e}")
    
    async def modify_stop_order(self, trade: Trade, new_stop_price: Decimal):
        """Modify stop loss order for a trade.
        
        Args:
            trade: Trade to modify stop for
            new_stop_price: New stop loss price
        """
        try:
            stop_order_id = trade.metadata.get('stop_order_id')
            if not stop_order_id:
                return
            
            broker_adapter = self.broker_adapters.get(self.default_broker)
            if broker_adapter:
                modify_request = OrderModifyRequest(
                    broker_type=self.default_broker,
                    account_id=self.config.get('account_id', 'default'),
                    client_order_id=stop_order_id,
                    new_stop_price=new_stop_price
                )
                
                await broker_adapter.modify_order(modify_request)
                
                self.logger.debug(f"Modified stop order for trade {trade.trade_id} to {new_stop_price}")
                
        except Exception as e:
            self.logger.error(f"Error modifying stop order: {e}")
    
    async def check_partial_exit_levels(self, trade: Trade, current_price: Decimal) -> Optional[Dict[str, Any]]:
        """Check if any partial exit levels have been reached.
        
        Args:
            trade: Trade to check
            current_price: Current market price
            
        Returns:
            Partial exit details if level reached, None otherwise
        """
        # Count how many partial exits have been done
        exits_done = len(trade.partial_exits)
        
        if exits_done >= len(self.partial_exit_levels):
            return None  # All partial exits completed
        
        # Check take profit levels
        take_profits = [trade.take_profit_1, trade.take_profit_2, trade.take_profit_3]
        
        for i, tp in enumerate(take_profits):
            if i < exits_done or tp == 0:
                continue
            
            # Check if price reached take profit
            if trade.side == 'BUY' and current_price >= tp:
                return {
                    'level': i + 1,
                    'target_price': tp,
                    'quantity': trade.position_size * Decimal(str(self.partial_exit_levels[i]))
                }
            elif trade.side == 'SELL' and current_price <= tp:
                return {
                    'level': i + 1,
                    'target_price': tp,
                    'quantity': trade.position_size * Decimal(str(self.partial_exit_levels[i]))
                }
        
        return None
    
    async def process_market_data(self, market_data: Dict[str, Any]):
        """Process incoming market data.
        
        Args:
            market_data: Market data update
        """
        try:
            symbol = market_data.get('symbol')
            if not symbol:
                return
            
            # Update price cache
            data = market_data.get('data', {})
            if data:
                self.market_prices[symbol] = {
                    'bid': data.get('bid', data.get('close')),
                    'ask': data.get('ask', data.get('close')),
                    'last': data.get('close'),
                    'timestamp': market_data.get('timestamp', datetime.now(timezone.utc))
                }
            
            # Store 1-minute data
            timeframe = market_data.get('timeframe')
            if timeframe == '1m':
                if symbol not in self.market_data_1m:
                    self.market_data_1m[symbol] = []
                
                self.market_data_1m[symbol].append(data)
                
                # Keep only last 100 bars
                if len(self.market_data_1m[symbol]) > 100:
                    self.market_data_1m[symbol] = self.market_data_1m[symbol][-100:]
            
        except Exception as e:
            self.logger.error(f"Error processing market data: {e}")
    
    async def get_current_price(self, symbol: str) -> Optional[Decimal]:
        """Get current market price for a symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Current price or None if not available
        """
        price_data = self.market_prices.get(symbol)
        if price_data:
            return Decimal(str(price_data.get('last', 0)))
        return None
    
    def calculate_unrealized_pnl(self, trade: Trade, current_price: Decimal) -> Decimal:
        """Calculate unrealized P&L for a trade.
        
        Args:
            trade: Trade object
            current_price: Current market price
            
        Returns:
            Unrealized P&L
        """
        if trade.side == 'BUY':
            return (current_price - trade.entry_price) * trade.position_size
        else:
            return (trade.entry_price - current_price) * trade.position_size
    
    async def close_all_positions(self, reason: str):
        """Close all active positions.
        
        Args:
            reason: Reason for closing all positions
        """
        self.logger.warning(f"Closing all positions: {reason}")
        
        for trade_id, trade in list(self.active_trades.items()):
            if trade.status == TradeStatus.OPEN:
                await self.execute_exit(trade, {
                    'exit_type': 'risk_limit',
                    'reason': reason
                })
    
    async def close_oldest_position(self):
        """Close the oldest position to make room for new ones."""
        if not self.active_trades:
            return
        
        # Find oldest trade
        oldest_trade = min(
            self.active_trades.values(),
            key=lambda t: t.entry_time
        )
        
        await self.execute_exit(oldest_trade, {
            'exit_type': 'position_limit',
            'reason': 'Max positions reached'
        })
    
    async def reduce_correlated_exposure(self):
        """Reduce exposure in highly correlated positions."""
        # Implementation would analyze correlation between positions
        # and reduce sizes or close some positions
        pass
    
    async def reduce_position_sizes(self):
        """Reduce position sizes to lower margin usage."""
        # Implementation would partially close positions
        # to reduce overall margin usage
        pass
    
    async def simulate_exit(self, trade: Trade, exit_signal: Dict[str, Any]):
        """Simulate trade exit in demo mode.
        
        Args:
            trade: Trade to exit
            exit_signal: Exit signal details
        """
        # Get current price
        current_price = await self.get_current_price(trade.symbol)
        if not current_price:
            current_price = trade.entry_price  # Fallback
        
        # Calculate P&L
        if trade.side == 'BUY':
            pnl = (current_price - trade.entry_price) * trade.position_size
        else:
            pnl = (trade.entry_price - current_price) * trade.position_size
        
        # Update trade
        trade.exit_time = datetime.now(timezone.utc)
        trade.exit_price = current_price
        trade.realized_pnl = pnl
        trade.status = TradeStatus.CLOSED
        
        # Move to closed trades
        self.closed_trades[trade.trade_id] = trade
        del self.active_trades[trade.trade_id]
        
        # Update statistics
        if pnl > 0:
            self.win_count += 1
        else:
            self.loss_count += 1
        
        self.total_pnl += pnl
        self.daily_pnl += pnl
        
        # Save to database
        await self.update_trade_in_db(trade)
        
        # Emit event
        await self.emit_trade_event('trade_closed', trade)
        
        self.logger.info(f"Trade {trade.trade_id} closed: P&L = {pnl:.2f}")
    
    async def save_trade_to_db(self, trade: Trade):
        """Save trade to database.
        
        Args:
            trade: Trade to save
        """
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO trading.trades
                    (id, signal_id, symbol, direction, entry_time, entry_price,
                     position_size, leverage, stop_loss, take_profit, status,
                     metadata)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                    ON CONFLICT (id) DO UPDATE SET
                        status = EXCLUDED.status,
                        metadata = EXCLUDED.metadata,
                        updated_at = CURRENT_TIMESTAMP
                """,
                trade.trade_id,
                trade.signal_id,
                trade.symbol,
                trade.side,
                trade.entry_time,
                trade.entry_price,
                trade.position_size,
                50,  # Default leverage
                trade.stop_loss,
                trade.take_profit_1,
                trade.status.value,
                json.dumps(trade.metadata)
                )
                
        except Exception as e:
            self.logger.error(f"Error saving trade to database: {e}")
    
    async def update_trade_in_db(self, trade: Trade):
        """Update trade in database.
        
        Args:
            trade: Trade to update
        """
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    UPDATE trading.trades SET
                        exit_time = $2,
                        exit_price = $3,
                        gross_pnl = $4,
                        net_pnl = $4,
                        pnl_percent = $5,
                        status = $6,
                        close_reason = $7,
                        metadata = $8,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = $1
                """,
                trade.trade_id,
                trade.exit_time,
                trade.exit_price,
                trade.realized_pnl,
                float(trade.realized_pnl / (trade.entry_price * trade.position_size)) * 100,
                trade.status.value,
                trade.metadata.get('exit_reason', 'manual'),
                json.dumps(trade.metadata)
                )
                
        except Exception as e:
            self.logger.error(f"Error updating trade in database: {e}")
    
    async def store_risk_metrics(self, risk_metrics: Dict[str, Any]):
        """Store risk metrics to database.
        
        Args:
            risk_metrics: Risk metrics to store
        """
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO trading.performance_metrics
                    (period_start, period_end, timeframe, total_trades,
                     winning_trades, losing_trades, win_rate, avg_win,
                     avg_loss, profit_factor, sharpe_ratio, max_drawdown_percent,
                     total_pnl, net_pnl)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                """,
                datetime.now(timezone.utc).replace(hour=0, minute=0, second=0),
                datetime.now(timezone.utc),
                'daily',
                risk_metrics.get('total_trades', 0),
                risk_metrics.get('winning_trades', 0),
                risk_metrics.get('losing_trades', 0),
                risk_metrics.get('win_rate', 0),
                risk_metrics.get('avg_win', 0),
                risk_metrics.get('avg_loss', 0),
                risk_metrics.get('profit_factor', 0),
                risk_metrics.get('sharpe_ratio', 0),
                abs(float(self.max_drawdown)),
                float(self.total_pnl),
                float(self.total_pnl)
                )
                
        except Exception as e:
            self.logger.error(f"Error storing risk metrics: {e}")
    
    async def emit_trade_event(self, event_type: str, trade: Trade):
        """Emit trade event to monitoring systems.
        
        Args:
            event_type: Type of event (trade_opened, trade_closed, etc.)
            trade: Trade object
        """
        event_data = {
            'event_type': event_type,
            'trade_id': trade.trade_id,
            'symbol': trade.symbol,
            'side': trade.side,
            'entry_price': float(trade.entry_price),
            'position_size': float(trade.position_size),
            'status': trade.status.value,
            'unrealized_pnl': float(trade.unrealized_pnl),
            'realized_pnl': float(trade.realized_pnl),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        # Publish to system events
        await self.publish_message(
            Exchanges.SYSTEM,
            format_routing_key(RoutingKeys.SYSTEM_ALERT, severity='info'),
            event_data
        )
    
    async def send_risk_alert(self, alert_type: str, risk_metrics: Dict[str, Any]):
        """Send risk management alert.
        
        Args:
            alert_type: Type of alert
            risk_metrics: Current risk metrics
        """
        alert_data = {
            'alert_type': alert_type,
            'severity': 'critical',
            'risk_metrics': risk_metrics,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'action_taken': 'Trading disabled, all positions closed'
        }
        
        await self.publish_message(
            Exchanges.SYSTEM,
            format_routing_key(RoutingKeys.SYSTEM_ALERT, severity='critical'),
            alert_data
        )
    
    # Handler methods
    
    async def handle_execution_report(self, execution):
        """Handle execution report from broker."""
        try:
            # Find trade by order ID
            for trade in self.active_trades.values():
                if (trade.metadata.get('exit_order_id') == execution.client_order_id or
                    trade.metadata.get('order_id') == execution.client_order_id):
                    
                    if execution.order_status.value == 'FILLED':
                        # Update trade with execution details
                        trade.exit_time = execution.transaction_time
                        trade.exit_price = execution.last_price
                        trade.realized_pnl = self.calculate_unrealized_pnl(trade, execution.last_price)
                        trade.status = TradeStatus.CLOSED
                        
                        # Move to closed trades
                        self.closed_trades[trade.trade_id] = trade
                        del self.active_trades[trade.trade_id]
                        
                        # Update statistics
                        if trade.realized_pnl > 0:
                            self.win_count += 1
                        else:
                            self.loss_count += 1
                        
                        self.total_pnl += trade.realized_pnl
                        self.daily_pnl += trade.realized_pnl
                        
                        # Save to database
                        await self.update_trade_in_db(trade)
                        
                        # Emit event
                        await self.emit_trade_event('trade_closed', trade)
                        
                        self.logger.info(f"Trade {trade.trade_id} closed via execution report")
                    
                    break
                    
        except Exception as e:
            self.logger.error(f"Error handling execution report: {e}")
    
    async def handle_order_response(self, response):
        """Handle order response from broker."""
        # Log order status updates
        self.logger.info(f"Order response: {response.client_order_id} - {response.status}")
    
    async def handle_broker_error(self, error):
        """Handle broker error."""
        self.logger.error(f"Broker error: {error.error_code} - {error.error_message}")
    
    async def save_positions_state(self):
        """Save current positions state before shutdown."""
        try:
            state_data = {
                'active_trades': {
                    trade_id: {
                        'trade_id': trade.trade_id,
                        'symbol': trade.symbol,
                        'side': trade.side,
                        'entry_price': float(trade.entry_price),
                        'position_size': float(trade.position_size),
                        'stop_loss': float(trade.stop_loss),
                        'unrealized_pnl': float(trade.unrealized_pnl),
                        'metadata': trade.metadata
                    }
                    for trade_id, trade in self.active_trades.items()
                },
                'daily_pnl': float(self.daily_pnl),
                'total_pnl': float(self.total_pnl),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
            await self.cache_json_set('trade_manager_state', state_data, ttl=86400)
            
            self.logger.info("Saved positions state")
            
        except Exception as e:
            self.logger.error(f"Error saving positions state: {e}")
    
    async def performance_tracking_loop(self):
        """Track and report trading performance."""
        while self.running:
            try:
                # Calculate performance metrics
                metrics = await self.pnl_tracker.calculate_performance_metrics(
                    self.active_trades,
                    self.closed_trades,
                    self.daily_pnl,
                    self.total_pnl
                )
                
                # Store in database
                await self.store_performance_metrics(metrics)
                
                # Reset daily metrics at midnight
                current_time = datetime.now(timezone.utc)
                if current_time.hour == 0 and current_time.minute < 1:
                    self.daily_pnl = Decimal('0')
                    self.daily_loss_limit_hit = False
                    self.trading_enabled = True
                
                # Sleep for 1 minute
                await asyncio.sleep(60)
                
            except Exception as e:
                self.logger.error(f"Error in performance tracking: {e}")
                await asyncio.sleep(60)
    
    async def store_performance_metrics(self, metrics: Dict[str, Any]):
        """Store performance metrics.
        
        Args:
            metrics: Performance metrics to store
        """
        # Implementation would store detailed performance metrics
        pass
    
    async def heartbeat_loop(self):
        """Send periodic heartbeats and metrics."""
        while self.running:
            try:
                # Send heartbeat
                await self.publish_message(
                    Exchanges.SYSTEM,
                    format_routing_key(
                        RoutingKeys.SYSTEM_HEARTBEAT,
                        service=self.service_name
                    ),
                    {
                        'active_trades': len(self.active_trades),
                        'closed_trades_today': len([t for t in self.closed_trades.values() 
                                                   if t.exit_time and t.exit_time.date() == datetime.now(timezone.utc).date()]),
                        'daily_pnl': float(self.daily_pnl),
                        'total_pnl': float(self.total_pnl),
                        'win_rate': self.win_count / (self.win_count + self.loss_count) if (self.win_count + self.loss_count) > 0 else 0,
                        'trading_enabled': self.trading_enabled,
                        'health': await self.health_check()
                    }
                )
                
                # Send metrics
                await self.publish_message(
                    Exchanges.SYSTEM,
                    format_routing_key(
                        RoutingKeys.SYSTEM_METRICS,
                        service=self.service_name
                    ),
                    {
                        'active_trades_count': len(self.active_trades),
                        'daily_pnl': float(self.daily_pnl),
                        'total_pnl': float(self.total_pnl),
                        'win_count': self.win_count,
                        'loss_count': self.loss_count,
                        'max_drawdown': float(self.max_drawdown)
                    }
                )
                
                await asyncio.sleep(30)
                
            except Exception as e:
                self.logger.error(f"Error in heartbeat loop: {e}")
                await asyncio.sleep(30)


if __name__ == "__main__":
    import uuid
    
    # Load configuration
    config = ServiceConfig.from_env()
    
    # Add trade manager specific config
    config.update({
        'brokers': {
            'INTERACTIVE_BROKERS': {
                'host': config.get('ib_gateway_host', '127.0.0.1'),
                'port': config.get('ib_gateway_port', 7497),
                'client_id': config.get('ib_client_id', 3),
                'credentials': {}
            }
        },
        'account_id': 'DU123456',
        'max_positions': 10,
        'max_daily_loss': 0.05,
        'trailing_stop_activation': 0.01,
        'partial_exit_levels': [0.33, 0.33, 0.34]
    })
    
    # Create and run service
    service = TradeManagerService(config)
    asyncio.run(service.run())