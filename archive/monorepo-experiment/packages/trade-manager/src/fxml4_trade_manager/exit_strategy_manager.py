"""Exit Strategy Manager - Handles stop loss, take profit, and trailing stops."""

from typing import Dict, Any, List, Optional, Tuple
from datetime import timedelta
from decimal import Decimal
import asyncio
import logging
from enum import Enum

from .domain import (
    OrderSide, OrderType, TimeInForce,
    BrokerMessageFactory, MarketData,
    ITimeProvider, IExitStrategyManager, IBrokerAdapter,
    IEventPublisher, UTCTimeProvider
)

logger = logging.getLogger(__name__)


class ExitReason(str, Enum):
    """Reasons for position exit."""
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"
    TRAILING_STOP = "trailing_stop"
    TIME_EXIT = "time_exit"
    SIGNAL_EXIT = "signal_exit"
    MANUAL_EXIT = "manual_exit"
    RISK_LIMIT = "risk_limit"
    DRAWDOWN_LIMIT = "drawdown_limit"
    PARTIAL_PROFIT = "partial_profit"
    VOLATILITY_SPIKE = "volatility_spike"
    RSI_OVERBOUGHT = "rsi_overbought"
    RSI_OVERSOLD = "rsi_oversold"
    TECHNICAL_INDICATOR = "technical_indicator"


class ExitLevel(str, Enum):
    """Exit level definitions."""
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT_1 = "take_profit_1"
    TAKE_PROFIT_2 = "take_profit_2"
    TAKE_PROFIT_3 = "take_profit_3"
    TRAILING_STOP = "trailing_stop"
    BREAK_EVEN = "break_even"


class ExitCondition(str, Enum):
    """Exit condition types."""
    PRICE_BELOW_TRAILING = "price_below_trailing"
    PRICE_ABOVE_TRAILING = "price_above_trailing"
    PRICE_HIT_STOP = "price_hit_stop"
    PRICE_HIT_TARGET = "price_hit_target"
    TIME_LIMIT_REACHED = "time_limit_reached"
    VOLATILITY_HIGH = "volatility_high"
    RSI_OVERBOUGHT = "rsi_overbought"
    RSI_OVERSOLD = "rsi_oversold"
    EMERGENCY_STOP = "emergency_stop"
    PARTIAL_EXIT_TARGET = "partial_exit_target"


class ExitRule:
    """Individual exit rule configuration."""
    
    def __init__(self, rule_data: Dict[str, Any]):
        self.rule_id = rule_data['rule_id']
        self.exit_reason = ExitReason(rule_data['exit_reason'])
        self.condition = ExitCondition(rule_data['condition'])
        self.parameters = rule_data.get('parameters', {})
        self.enabled = rule_data.get('enabled', True)
        self.priority = rule_data.get('priority', 1)
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert rule to dictionary."""
        return {
            'rule_id': self.rule_id,
            'exit_reason': self.exit_reason.value,
            'condition': self.condition.value,
            'parameters': self.parameters,
            'enabled': self.enabled,
            'priority': self.priority
        }


class ExitStrategy:
    """Exit strategy configuration."""
    
    def __init__(self, strategy_config: Dict[str, Any]):
        self.strategy_id = strategy_config.get('strategy_id')
        self.name = strategy_config.get('name', 'default')
        
        # Stop loss
        self.stop_loss_type = strategy_config.get('stop_loss_type', 'fixed')  # fixed, atr, percent
        self.stop_loss_value = Decimal(str(strategy_config.get('stop_loss_value', 50)))
        self.stop_loss_atr_multiplier = Decimal(str(strategy_config.get('stop_loss_atr_multiplier', 2)))
        
        # Take profit levels
        self.take_profit_levels = []
        for i in range(1, 4):
            tp_config = strategy_config.get(f'take_profit_{i}', {})
            if tp_config:
                self.take_profit_levels.append({
                    'level': i,
                    'target': Decimal(str(tp_config.get('target', 100 * i))),
                    'exit_percent': Decimal(str(tp_config.get('exit_percent', 33.33))),
                    'move_stop_to_breakeven': tp_config.get('move_stop_to_breakeven', i == 1)
                })
        
        # Trailing stop
        self.trailing_stop_enabled = strategy_config.get('trailing_stop_enabled', True)
        self.trailing_stop_activation = Decimal(str(strategy_config.get('trailing_stop_activation', 50)))
        self.trailing_stop_distance = Decimal(str(strategy_config.get('trailing_stop_distance', 30)))
        self.trailing_stop_type = strategy_config.get('trailing_stop_type', 'pips')  # pips, atr, percent
        
        # Time-based exits
        self.time_exit_enabled = strategy_config.get('time_exit_enabled', False)
        self.max_hold_hours = strategy_config.get('max_hold_hours', 72)
        self.weekend_exit_enabled = strategy_config.get('weekend_exit_enabled', True)
        
        # Risk-based exits
        self.daily_loss_limit = Decimal(str(strategy_config.get('daily_loss_limit', 0.05)))  # 5%
        self.drawdown_limit = Decimal(str(strategy_config.get('drawdown_limit', 0.10)))  # 10%
        
        # Dynamic adjustments
        self.adjust_stops_on_volatility = strategy_config.get('adjust_stops_on_volatility', True)
        self.tighten_stops_on_news = strategy_config.get('tighten_stops_on_news', True)


class ExitStrategyManager(IExitStrategyManager):
    """Manages exit strategies and order placement."""
    
    def __init__(
        self,
        time_provider: Optional[ITimeProvider] = None,
        event_publisher: Optional[IEventPublisher] = None
    ):
        self._time_provider = time_provider or UTCTimeProvider()
        self._event_publisher = event_publisher
        
        self.strategies: Dict[str, ExitStrategy] = {}
        self.position_strategies: Dict[str, str] = {}  # position_id -> strategy_id
        self.position_states: Dict[str, Dict[str, Any]] = {}  # position_id -> state data
        self.exit_orders: Dict[str, Dict[str, Any]] = {}  # position_id -> orders
        self.market_conditions: Dict[str, Any] = {}
        self.config: Dict[str, Any] = {}
        self.rules: List[ExitRule] = []
        self._lock = asyncio.Lock()
        
        # Load default strategies
        self._load_default_strategies()
    
    async def initialize(self, config: Optional[Dict[str, Any]] = None):
        """Initialize exit strategy manager with configuration."""
        if config:
            # Convert numeric values to Decimal for financial precision
            self.config = self._convert_config_to_decimal(config)
            await self._create_rules_from_config(self.config)
        logger.info("Exit Strategy Manager initialized")
    
    def _convert_config_to_decimal(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Convert numeric values in config to Decimal for financial precision."""
        converted = config.copy()
        decimal_fields = [
            'trailing_stop_distance', 'breakeven_trigger', 'breakeven_offset',
            'volatility_multiplier'
        ]
        for field in decimal_fields:
            if field in converted and isinstance(converted[field], (int, float)):
                converted[field] = Decimal(str(converted[field]))
        return converted
    
    async def _create_rules_from_config(self, config: Dict[str, Any]):
        """Create exit rules from configuration."""
        self.rules = []
        
        # Create stop loss rule (highest priority - always enabled)
        rule = ExitRule({
            'rule_id': 'stop_loss',
            'exit_reason': 'stop_loss',
            'condition': 'price_hit_stop',
            'parameters': {},
            'enabled': True,
            'priority': 0  # Highest priority
        })
        self.rules.append(rule)
        
        # Create take profit rule
        rule = ExitRule({
            'rule_id': 'take_profit',
            'exit_reason': 'take_profit',
            'condition': 'price_hit_target',
            'parameters': {},
            'enabled': True,
            'priority': 1
        })
        self.rules.append(rule)
        
        # Create trailing stop rule if enabled
        if config.get('trailing_stop_enabled', False):
            rule = ExitRule({
                'rule_id': 'trailing_stop',
                'exit_reason': 'trailing_stop',
                'condition': 'price_below_trailing',
                'parameters': {
                    'distance': config.get('trailing_stop_distance', 0.005)
                },
                'enabled': True,
                'priority': 2
            })
            self.rules.append(rule)
        
        # Create breakeven rule if enabled
        if config.get('breakeven_enabled', False):
            rule = ExitRule({
                'rule_id': 'breakeven',
                'exit_reason': 'trailing_stop', 
                'condition': 'price_hit_target',
                'parameters': {
                    'trigger': config.get('breakeven_trigger', 0.003),
                    'offset': config.get('breakeven_offset', 0.0001)
                },
                'enabled': True,
                'priority': 3
            })
            self.rules.append(rule)
        
        # Create time-based exit rule if enabled
        if config.get('time_stop_enabled', False):
            rule = ExitRule({
                'rule_id': 'time_stop',
                'exit_reason': 'time_exit',
                'condition': 'time_limit_reached',
                'parameters': {
                    'max_hold_time_minutes': config.get('max_hold_time_minutes', 240)
                },
                'enabled': True,
                'priority': 4
            })
            self.rules.append(rule)
        
        # Create partial exit rules if enabled
        if config.get('partial_exit_enabled', False):
            partial_exits = config.get('partial_exits', [])
            for i, partial_exit in enumerate(partial_exits):
                rule = ExitRule({
                    'rule_id': f'partial_exit_{i+1}',
                    'exit_reason': 'partial_profit',
                    'condition': 'partial_exit_target',
                    'parameters': {
                        'profit_target': partial_exit.get('profit_target'),
                        'exit_percentage': partial_exit.get('exit_percentage'),
                        'profit_level': i + 1
                    },
                    'enabled': True,
                    'priority': 5 + i  # Partial exits have lower priority
                })
                self.rules.append(rule)
        
        # Create volatility exit rule if enabled
        if config.get('volatility_exit_enabled', False):
            rule = ExitRule({
                'rule_id': 'volatility_exit',
                'exit_reason': 'volatility_spike',
                'condition': 'volatility_high',
                'parameters': {
                    'volatility_multiplier': config.get('volatility_multiplier', 2.0)
                },
                'enabled': True,
                'priority': 10  # Volatility exit has lower priority
            })
            self.rules.append(rule)
        
        # Create RSI exit rules if enabled
        if config.get('rsi_exit_enabled', False):
            # RSI overbought rule
            rule = ExitRule({
                'rule_id': 'rsi_overbought',
                'exit_reason': 'technical_indicator',
                'condition': 'rsi_overbought',
                'parameters': {
                    'rsi_overbought': config.get('rsi_overbought', 70),
                    'indicator': 'RSI'
                },
                'enabled': True,
                'priority': 11
            })
            self.rules.append(rule)
            
            # RSI oversold rule
            rule = ExitRule({
                'rule_id': 'rsi_oversold',
                'exit_reason': 'technical_indicator',
                'condition': 'rsi_oversold',
                'parameters': {
                    'rsi_oversold': config.get('rsi_oversold', 30),
                    'indicator': 'RSI'
                },
                'enabled': True,
                'priority': 12
            })
            self.rules.append(rule)
    
    async def check_exit_conditions(
        self,
        position: Dict[str, Any],
        market_data: Dict[str, Any]
    ) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """Check if any exit conditions are met."""
        position_id = position.get('position_id', 'unknown')
        current_price = Decimal(str(position.get('current_price', 0)))
        side = position.get('side', 'long')
        
        # Normalize side format
        if side.upper() in ['BUY', 'LONG']:
            side = 'long'
        elif side.upper() in ['SELL', 'SHORT']:
            side = 'short'
        
        # Get position state
        position_state = self.position_states.get(position_id, {})
        
        # Check emergency stop loss first (highest priority)
        stop_loss = position.get('stop_loss')
        if stop_loss:
            stop_loss = Decimal(str(stop_loss))
            if side == 'long':
                # For long positions, exit if price drops to or below stop loss
                if current_price <= stop_loss:
                    return True, ExitReason.STOP_LOSS, {
                        'stop_price': stop_loss,
                        'exit_price': Decimal(str(market_data.get('bid', current_price)))
                    }
            else:
                # For short positions, exit if price rises to or above stop loss
                if current_price >= stop_loss:
                    return True, ExitReason.STOP_LOSS, {
                        'stop_price': stop_loss,
                        'exit_price': Decimal(str(market_data.get('ask', current_price)))
                    }
        
        # Check take profit targets (second highest priority)
        for i in range(1, 4):  # Check up to 3 take profit levels
            tp_key = f'take_profit_{i}'
            take_profit = position.get(tp_key)
            if take_profit and take_profit != '0' and take_profit != 0:
                take_profit = Decimal(str(take_profit))
                if take_profit > 0:  # Only valid positive take profit levels
                    if side == 'long':
                        # For long positions, exit if price reaches or exceeds take profit
                        if current_price >= take_profit:
                            return True, ExitReason.TAKE_PROFIT, {
                                'target_price': take_profit,
                                'exit_price': Decimal(str(market_data.get('bid', current_price))),
                                'profit_level': i
                            }
                    else:
                        # For short positions, exit if price drops to or below take profit
                        if current_price <= take_profit:
                            return True, ExitReason.TAKE_PROFIT, {
                                'target_price': take_profit,
                                'exit_price': Decimal(str(market_data.get('ask', current_price))),
                                'profit_level': i
                            }
        
        # Check trailing stop condition
        trailing_stop_level = position_state.get('trailing_stop_level')
        if trailing_stop_level:
            trailing_stop_level = Decimal(str(trailing_stop_level))
            
            if side == 'long':
                # For long positions, exit if price drops below trailing stop
                if current_price <= trailing_stop_level:
                    return True, ExitReason.TRAILING_STOP, {
                        'exit_price': Decimal(str(market_data.get('bid', current_price))),
                        'trailing_stop_level': trailing_stop_level
                    }
            else:
                # For short positions, exit if price rises above trailing stop
                if current_price >= trailing_stop_level:
                    return True, ExitReason.TRAILING_STOP, {
                        'exit_price': Decimal(str(market_data.get('ask', current_price))),
                        'trailing_stop_level': trailing_stop_level
                    }
        
        # Check other exit rules
        for rule in self.rules:
            if rule.enabled and await self._check_rule_condition(rule, position, market_data):
                details = {
                    'rule_id': rule.rule_id,
                    'condition': rule.condition,
                    'parameters': rule.parameters
                }
                
                # Add specific details for time-based exit
                if rule.condition == ExitCondition.TIME_LIMIT_REACHED and 'opened_at' in position:
                    opened_at = position['opened_at']
                    current_time = self._time_provider.now()
                    elapsed_minutes = (current_time - opened_at).total_seconds() / 60
                    details['hold_time_minutes'] = elapsed_minutes
                
                # Add specific details for partial exit
                elif rule.condition == ExitCondition.PARTIAL_EXIT_TARGET:
                    details['exit_percentage'] = Decimal(str(rule.parameters.get('exit_percentage', 0)))
                    filled_quantity = Decimal(str(position.get('filled_quantity', 0)))
                    details['exit_quantity'] = int(filled_quantity * details['exit_percentage'])
                    details['profit_level'] = rule.parameters.get('profit_level', 1)
                
                # Add specific details for volatility exit
                elif rule.condition == ExitCondition.VOLATILITY_HIGH:
                    details['current_volatility'] = market_data.get('volatility', 0)
                
                # Add specific details for RSI exit
                elif rule.condition in [ExitCondition.RSI_OVERBOUGHT, ExitCondition.RSI_OVERSOLD]:
                    details['indicator'] = rule.parameters.get('indicator', 'RSI')
                    details['rsi_value'] = market_data.get('rsi', 50)
                
                return True, rule.exit_reason, details
        
        return False, None, None
    
    async def _check_rule_condition(
        self,
        rule: ExitRule,
        position: Dict[str, Any],
        market_data: Dict[str, Any]
    ) -> bool:
        """Check if a specific exit rule condition is met."""
        # Basic implementation for common conditions
        current_price = Decimal(str(position.get('current_price', 0)))
        
        if rule.condition == ExitCondition.PRICE_HIT_STOP:
            stop_price = rule.parameters.get('stop_price')
            if stop_price:
                return current_price <= Decimal(str(stop_price))
        
        elif rule.condition == ExitCondition.PRICE_HIT_TARGET:
            target_price = rule.parameters.get('target_price')
            if target_price:
                return current_price >= Decimal(str(target_price))
        
        elif rule.condition == ExitCondition.TIME_LIMIT_REACHED:
            # Time-based exit logic
            max_hold_time = rule.parameters.get('max_hold_time_minutes')
            if max_hold_time and 'opened_at' in position:
                opened_at = position['opened_at']
                current_time = self._time_provider.now()
                elapsed_minutes = (current_time - opened_at).total_seconds() / 60
                
                if elapsed_minutes >= max_hold_time:
                    return True
        
        elif rule.condition == ExitCondition.PARTIAL_EXIT_TARGET:
            # Partial exit logic
            profit_target = rule.parameters.get('profit_target')
            profit_level = rule.parameters.get('profit_level', 1)
            position_id = position.get('position_id', 'unknown')
            
            # Check if this partial exit has already been executed
            if await self._check_partial_exit_executed(position_id, profit_level):
                return False
            
            if profit_target:
                entry_price = Decimal(str(position.get('entry_price', 0)))
                side = position.get('side', 'long').lower()
                
                # Normalize side format
                if side in ['buy', 'long']:
                    # For long positions, check if price is above target
                    target_price = entry_price * (1 + Decimal(str(profit_target)))
                    if current_price >= target_price:
                        return True
                else:
                    # For short positions, check if price is below target
                    target_price = entry_price * (1 - Decimal(str(profit_target)))
                    if current_price <= target_price:
                        return True
        
        elif rule.condition == ExitCondition.VOLATILITY_HIGH:
            # Volatility exit logic
            volatility = market_data.get('volatility', 0)
            volatility_multiplier = float(rule.parameters.get('volatility_multiplier', 2.0))
            
            # Check if volatility exceeds threshold (1% baseline * multiplier)
            volatility_threshold = 0.01 * volatility_multiplier
            if volatility > volatility_threshold:
                return True
        
        elif rule.condition == ExitCondition.RSI_OVERBOUGHT:
            # RSI overbought exit logic (for long positions)
            rsi = market_data.get('rsi', 50)
            rsi_overbought = rule.parameters.get('rsi_overbought', 70)
            side = position.get('side', 'long').lower()
            
            # Only exit long positions when RSI is overbought
            if side in ['buy', 'long'] and rsi >= rsi_overbought:
                return True
        
        elif rule.condition == ExitCondition.RSI_OVERSOLD:
            # RSI oversold exit logic (for short positions)
            rsi = market_data.get('rsi', 50)
            rsi_oversold = rule.parameters.get('rsi_oversold', 30)
            side = position.get('side', 'long').lower()
            
            # Only exit short positions when RSI is oversold
            if side in ['sell', 'short'] and rsi <= rsi_oversold:
                return True
        
        return False
    
    async def record_partial_exit(self, position_id: str, profit_level: int, exit_percentage: Decimal) -> None:
        """Record a partial exit that has been executed."""
        if position_id not in self.position_states:
            self.position_states[position_id] = {}
        
        position_state = self.position_states[position_id]
        if 'partial_exits_completed' not in position_state:
            position_state['partial_exits_completed'] = []
        
        position_state['partial_exits_completed'].append(profit_level)
        logger.info(f"Recorded partial exit for position {position_id}: level {profit_level}, {exit_percentage * 100}%")
    
    async def _check_partial_exit_executed(self, position_id: str, profit_level: int) -> bool:
        """Check if a partial exit has already been executed."""
        position_state = self.position_states.get(position_id, {})
        partial_exits_completed = position_state.get('partial_exits_completed', [])
        return profit_level in partial_exits_completed
    
    async def update_breakeven_stop(self, position: Dict[str, Any]) -> bool:
        """Update breakeven stop for a position."""
        position_id = position.get('position_id', 'unknown')
        entry_price = Decimal(str(position.get('entry_price', position.get('avg_entry_price', 0))))
        current_price = Decimal(str(position.get('current_price', 0)))
        side = position.get('side', 'long')
        
        # Normalize side format
        if side.upper() in ['BUY', 'LONG']:
            side = 'long'
        elif side.upper() in ['SELL', 'SHORT']:
            side = 'short'
        
        # Check if breakeven is enabled in config
        if not self.config.get('breakeven_enabled', False):
            return False
        
        # Get breakeven parameters
        breakeven_trigger = self.config.get('breakeven_trigger', Decimal('0.003'))
        breakeven_offset = self.config.get('breakeven_offset', Decimal('0.0001'))
        
        # Calculate profit
        if side == 'long':
            profit = current_price - entry_price
            profit_percentage = profit / entry_price
        else:
            profit = entry_price - current_price
            profit_percentage = profit / entry_price
        
        # Check if profit is enough to trigger breakeven
        if profit_percentage >= breakeven_trigger:
            # Set breakeven stop
            if position_id not in self.position_states:
                self.position_states[position_id] = {}
            
            if side == 'long':
                breakeven_level = entry_price + breakeven_offset
            else:
                breakeven_level = entry_price - breakeven_offset
            
            self.position_states[position_id]['breakeven_stop'] = breakeven_level
            self.position_states[position_id]['stop_loss'] = breakeven_level
            self.position_states[position_id]['breakeven_activated'] = True
            
            return True
        
        return False
    
    async def update_trailing_stop(self, position: Dict[str, Any]) -> bool:
        """Update trailing stop for a position."""
        # Basic implementation for trailing stop update
        return False
    
    def _load_default_strategies(self):
        """Load default exit strategies."""
        # Conservative strategy
        self.strategies['conservative'] = ExitStrategy({
            'strategy_id': 'conservative',
            'name': 'Conservative',
            'stop_loss_type': 'fixed',
            'stop_loss_value': 30,
            'take_profit_1': {
                'target': 50,
                'exit_percent': 50,
                'move_stop_to_breakeven': True
            },
            'take_profit_2': {
                'target': 100,
                'exit_percent': 30,
                'move_stop_to_breakeven': False
            },
            'take_profit_3': {
                'target': 150,
                'exit_percent': 20,
                'move_stop_to_breakeven': False
            },
            'trailing_stop_enabled': True,
            'trailing_stop_activation': 50,
            'trailing_stop_distance': 20
        })
        
        # Aggressive strategy
        self.strategies['aggressive'] = ExitStrategy({
            'strategy_id': 'aggressive',
            'name': 'Aggressive',
            'stop_loss_type': 'atr',
            'stop_loss_atr_multiplier': 1.5,
            'take_profit_1': {
                'target': 100,
                'exit_percent': 30,
                'move_stop_to_breakeven': True
            },
            'take_profit_2': {
                'target': 200,
                'exit_percent': 30,
                'move_stop_to_breakeven': False
            },
            'take_profit_3': {
                'target': 300,
                'exit_percent': 40,
                'move_stop_to_breakeven': False
            },
            'trailing_stop_enabled': True,
            'trailing_stop_activation': 100,
            'trailing_stop_distance': 50,
            'trailing_stop_type': 'atr'
        })
        
        # Scalping strategy
        self.strategies['scalping'] = ExitStrategy({
            'strategy_id': 'scalping',
            'name': 'Scalping',
            'stop_loss_type': 'fixed',
            'stop_loss_value': 10,
            'take_profit_1': {
                'target': 15,
                'exit_percent': 100,
                'move_stop_to_breakeven': False
            },
            'trailing_stop_enabled': False,
            'time_exit_enabled': True,
            'max_hold_hours': 1
        })
    
    async def assign_strategy(
        self,
        position_id: str,
        strategy_id: Optional[str] = None,
        custom_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Assign exit strategy to position."""
        async with self._lock:
            if custom_config:
                # Create custom strategy
                strategy = ExitStrategy(custom_config)
                self.strategies[f"custom_{position_id}"] = strategy
                self.position_strategies[position_id] = f"custom_{position_id}"
            else:
                # Use existing strategy
                strategy_id = strategy_id or 'conservative'
                if strategy_id not in self.strategies:
                    strategy_id = 'conservative'
                self.position_strategies[position_id] = strategy_id
                strategy = self.strategies[strategy_id]
            
            logger.info(f"Assigned strategy '{strategy.name}' to position {position_id}")
            
            # Publish event if publisher available
            if self._event_publisher:
                await self._event_publisher.publish(
                    'exit_strategy.assigned',
                    {
                        'position_id': position_id,
                        'strategy_id': strategy.strategy_id,
                        'strategy_name': strategy.name
                    }
                )
            
            return {
                'strategy_id': strategy.strategy_id,
                'name': strategy.name,
                'take_profit_levels': len(strategy.take_profit_levels),
                'trailing_stop_enabled': strategy.trailing_stop_enabled
            }
    
    async def calculate_exit_levels(
        self,
        position_data: Dict[str, Any],
        market_data: Optional[MarketData] = None
    ) -> Dict[str, Decimal]:
        """Calculate exit levels for a position."""
        strategy_id = self.position_strategies.get(
            position_data['position_id'], 
            'conservative'
        )
        strategy = self.strategies[strategy_id]
        
        entry_price = Decimal(str(position_data.get('entry_price', position_data.get('avg_entry_price', 0))))
        side = OrderSide(position_data['side'])
        symbol = position_data['symbol']
        
        # Get ATR if needed
        atr = Decimal('0')
        if market_data and market_data.atr:
            atr = market_data.atr
        
        # Calculate stop loss
        if strategy.stop_loss_type == 'fixed':
            sl_distance = self._pips_to_price(symbol, strategy.stop_loss_value)
        elif strategy.stop_loss_type == 'atr' and atr > 0:
            sl_distance = atr * strategy.stop_loss_atr_multiplier
        elif strategy.stop_loss_type == 'percent':
            sl_distance = entry_price * strategy.stop_loss_value / 100
        else:
            sl_distance = self._pips_to_price(symbol, 50)  # Default
        
        if side == OrderSide.BUY:
            stop_loss = entry_price - sl_distance
        else:
            stop_loss = entry_price + sl_distance
        
        levels = {'stop_loss': stop_loss}
        
        # Calculate take profit levels
        for tp in strategy.take_profit_levels:
            tp_distance = self._pips_to_price(symbol, tp['target'])
            if side == OrderSide.BUY:
                tp_price = entry_price + tp_distance
            else:
                tp_price = entry_price - tp_distance
            levels[f"take_profit_{tp['level']}"] = tp_price
        
        # Adjust for market conditions
        if strategy.adjust_stops_on_volatility and market_data:
            levels = await self._adjust_for_volatility(levels, market_data.to_dict())
        
        return levels
    
    async def create_exit_orders(
        self,
        position_data: Dict[str, Any],
        exit_levels: Dict[str, Decimal],
        broker_adapter: Any
    ) -> Dict[str, str]:
        """Create exit orders for a position."""
        position_id = position_data['position_id']
        symbol = position_data['symbol']
        side = OrderSide(position_data['side'])
        quantity = Decimal(str(position_data['quantity']))
        
        strategy_id = self.position_strategies.get(position_id, 'conservative')
        strategy = self.strategies[strategy_id]
        
        order_ids = {}
        
        # Create stop loss order
        if 'stop_loss' in exit_levels:
            stop_side = OrderSide.SELL if side == OrderSide.BUY else OrderSide.BUY
            stop_order = BrokerMessageFactory.create_order_request(
                symbol=symbol,
                side=stop_side,
                quantity=quantity,
                order_type=OrderType.STOP,
                stop_price=exit_levels['stop_loss'],
                time_in_force=TimeInForce.GTC,
                metadata={
                    'position_id': position_id,
                    'exit_type': 'stop_loss'
                }
            )
            
            response = await broker_adapter.place_order(stop_order)
            if response.status == 'ACCEPTED':
                order_ids['stop_loss'] = response.broker_order_id
                logger.info(f"Created stop loss order {response.broker_order_id} for position {position_id}")
        
        # Create take profit orders
        remaining_quantity = quantity
        for tp in strategy.take_profit_levels:
            tp_key = f"take_profit_{tp['level']}"
            if tp_key in exit_levels and remaining_quantity > 0:
                tp_quantity = quantity * tp['exit_percent'] / 100
                tp_quantity = min(tp_quantity, remaining_quantity)
                
                tp_side = OrderSide.SELL if side == OrderSide.BUY else OrderSide.BUY
                tp_order = BrokerMessageFactory.create_order_request(
                    symbol=symbol,
                    side=tp_side,
                    quantity=tp_quantity,
                    order_type=OrderType.LIMIT,
                    price=exit_levels[tp_key],
                    time_in_force=TimeInForce.GTC,
                    metadata={
                        'position_id': position_id,
                        'exit_type': tp_key,
                        'exit_level': tp['level']
                    }
                )
                
                response = await broker_adapter.place_order(tp_order)
                if response.status == 'ACCEPTED':
                    order_ids[tp_key] = response.broker_order_id
                    remaining_quantity -= tp_quantity
                    logger.info(f"Created {tp_key} order {response.broker_order_id} for position {position_id}")
        
        # Store exit orders
        async with self._lock:
            self.exit_orders[position_id] = {
                'order_ids': order_ids,
                'levels': exit_levels,
                'created_at': self._time_provider.now()
            }
        
        return order_ids
    
    async def update_trailing_stop(
        self,
        position_data: Dict[str, Any],
        current_price: Decimal,
        broker_adapter: Any
    ) -> Optional[str]:
        """Update trailing stop for position."""
        position_id = position_data['position_id']
        strategy_id = self.position_strategies.get(position_id, 'conservative')
        strategy = self.strategies[strategy_id]
        
        if not strategy.trailing_stop_enabled:
            return None
        
        entry_price = Decimal(str(position_data.get('entry_price', position_data.get('avg_entry_price', 0))))
        side = OrderSide(position_data['side'])
        symbol = position_data['symbol']
        
        # Check if trailing stop should be activated
        activation_distance = self._pips_to_price(symbol, strategy.trailing_stop_activation)
        
        if side == OrderSide.BUY:
            if current_price < entry_price + activation_distance:
                return None
        else:
            if current_price > entry_price - activation_distance:
                return None
        
        # Calculate new trailing stop level
        trail_distance = self._pips_to_price(symbol, strategy.trailing_stop_distance)
        
        if side == OrderSide.BUY:
            new_stop = current_price - trail_distance
            current_stop = Decimal(str(position_data.get('stop_loss', 0)))
            if new_stop <= current_stop:
                return None
        else:
            new_stop = current_price + trail_distance
            current_stop = Decimal(str(position_data.get('stop_loss', float('inf'))))
            if new_stop >= current_stop:
                return None
        
        # Get current stop order
        exit_info = self.exit_orders.get(position_id, {})
        stop_order_id = exit_info.get('order_ids', {}).get('stop_loss')
        
        if stop_order_id:
            # Modify existing stop order
            modify_request = BrokerMessageFactory.create_order_modify_request(
                broker_order_id=stop_order_id,
                stop_price=new_stop
            )
            
            response = await broker_adapter.modify_order(modify_request)
            if response.status == 'MODIFIED':
                logger.info(f"Updated trailing stop for position {position_id} to {new_stop}")
                return stop_order_id
        
        return None
    
    async def check_time_exits(
        self,
        position_data: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """Check if position should be exited based on time."""
        position_id = position_data['position_id']
        strategy_id = self.position_strategies.get(position_id, 'conservative')
        strategy = self.strategies[strategy_id]
        
        if not strategy.time_exit_enabled:
            return False, None
        
        # Check max hold time
        opened_at = position_data.get('opened_at')
        if opened_at:
            hold_time = self._time_provider.now() - opened_at
            if hold_time.total_seconds() / 3600 > strategy.max_hold_hours:
                return True, ExitReason.TIME_EXIT.value
        
        # Check weekend exit
        if strategy.weekend_exit_enabled:
            now = self._time_provider.now()
            # Friday after 16:00 UTC
            if now.weekday() == 4 and now.hour >= 16:
                return True, ExitReason.TIME_EXIT.value
        
        return False, None
    
    async def move_stop_to_breakeven(
        self,
        position_data: Dict[str, Any],
        broker_adapter: Any
    ) -> bool:
        """Move stop loss to breakeven."""
        position_id = position_data['position_id']
        entry_price = Decimal(str(position_data.get('entry_price', position_data.get('avg_entry_price', 0))))
        
        # Add small buffer for spread/commission
        symbol = position_data['symbol']
        buffer = self._pips_to_price(symbol, 2)
        
        side = OrderSide(position_data['side'])
        if side == OrderSide.BUY:
            breakeven_price = entry_price + buffer
        else:
            breakeven_price = entry_price - buffer
        
        # Get current stop order
        exit_info = self.exit_orders.get(position_id, {})
        stop_order_id = exit_info.get('order_ids', {}).get('stop_loss')
        
        if stop_order_id:
            modify_request = BrokerMessageFactory.create_order_modify_request(
                broker_order_id=stop_order_id,
                stop_price=breakeven_price
            )
            
            response = await broker_adapter.modify_order(modify_request)
            if response.status == 'MODIFIED':
                logger.info(f"Moved stop to breakeven for position {position_id} at {breakeven_price}")
                return True
        
        return False
    
    async def cancel_exit_orders(
        self,
        position_id: str,
        broker_adapter: Any
    ) -> List[str]:
        """Cancel all exit orders for a position."""
        exit_info = self.exit_orders.get(position_id, {})
        order_ids = exit_info.get('order_ids', {})
        
        cancelled = []
        for exit_type, order_id in order_ids.items():
            response = await broker_adapter.cancel_order(order_id)
            if response.status in ['CANCELLED', 'PENDING_CANCEL']:
                cancelled.append(order_id)
                logger.info(f"Cancelled {exit_type} order {order_id} for position {position_id}")
        
        # Remove from tracking
        if position_id in self.exit_orders:
            del self.exit_orders[position_id]
        
        return cancelled
    
    async def get_exit_status(self, position_id: str) -> Dict[str, Any]:
        """Get exit order status for position."""
        exit_info = self.exit_orders.get(position_id, {})
        
        return {
            'position_id': position_id,
            'has_exits': bool(exit_info),
            'order_ids': exit_info.get('order_ids', {}),
            'levels': exit_info.get('levels', {}),
            'created_at': exit_info.get('created_at'),
            'strategy': self.position_strategies.get(position_id, 'unknown')
        }
    
    def _pips_to_price(self, symbol: str, pips: Decimal) -> Decimal:
        """Convert pips to price for a symbol."""
        # JPY pairs
        if 'JPY' in symbol:
            return pips * Decimal('0.01')
        # Standard pairs
        else:
            return pips * Decimal('0.0001')
    
    async def _adjust_for_volatility(
        self,
        levels: Dict[str, Decimal],
        market_data: Dict[str, Any]
    ) -> Dict[str, Decimal]:
        """Adjust exit levels based on market volatility."""
        volatility_ratio = Decimal(str(market_data.get('volatility_ratio', 1.0)))
        
        if volatility_ratio > 1.5:
            # High volatility - widen stops
            multiplier = Decimal('1.2')
        elif volatility_ratio < 0.7:
            # Low volatility - tighten stops
            multiplier = Decimal('0.8')
        else:
            return levels
        
        # Adjust levels (implementation simplified)
        # In production, this would be more sophisticated
        return levels
    
    async def get_exit_summary(self, position_id: str) -> Dict[str, Any]:
        """Get comprehensive exit strategy summary for a position."""
        position_state = self.position_states.get(position_id, {})
        
        # Count completed partial exits
        partial_exits_completed = len(position_state.get('partial_exits_completed', []))
        
        # Determine active rules
        active_rules = []
        for rule in self.rules:
            if rule.enabled:
                active_rules.append({
                    'rule_id': rule.rule_id,
                    'exit_reason': rule.exit_reason.value,
                    'priority': rule.priority
                })
        
        summary = {
            'position_id': position_id,
            'trailing_stop_active': position_state.get('trailing_stop_level') is not None,
            'trailing_stop_level': position_state.get('trailing_stop_level'),
            'breakeven_activated': position_state.get('breakeven_activated', False),
            'partial_exits_completed': partial_exits_completed,
            'active_rules': active_rules,
            'position_state': position_state
        }
        
        return summary
    
    async def clear_position_state(self, position_id: str):
        """Clear position state when position is closed."""
        if position_id in self.position_states:
            del self.position_states[position_id]
            logger.info(f"Cleared position state for {position_id}")
    
    async def record_partial_exit(self, position_id: str, level: int, percentage: Decimal):
        """Record that a partial exit has been executed."""
        # Ensure position state exists
        if position_id not in self.position_states:
            self.position_states[position_id] = {'partial_exits_completed': []}
        
        # Ensure partial_exits_completed list exists
        if 'partial_exits_completed' not in self.position_states[position_id]:
            self.position_states[position_id]['partial_exits_completed'] = []
        
        # Update position state
        self.position_states[position_id]['partial_exits_completed'].append(level)
        logger.info(f"Recorded partial exit level {level} for position {position_id}")
    
    async def calculate_trailing_stop_level(
        self, 
        position: Dict[str, Any], 
        market_data: Optional[Dict[str, Any]] = None
    ) -> Optional[Decimal]:
        """Calculate the trailing stop level for a position."""
        highest_price = Decimal(str(position.get('highest_price', position.get('current_price', 0))))
        side = position.get('side', 'BUY').upper()
        
        # Check for percentage-based trailing stop in config
        if self.config.get('trailing_stop_type') == 'percentage':
            distance = self.config.get('trailing_stop_distance', Decimal('0.005'))
            if side == 'BUY' or side == 'long':
                return highest_price * (Decimal('1') - Decimal(str(distance)))
            else:
                # For short positions, trail from lowest price
                lowest_price = Decimal(str(position.get('lowest_price', position.get('current_price', 0))))
                return lowest_price * (Decimal('1') + Decimal(str(distance)))
        
        # Check for ATR-based trailing stop
        elif self.config.get('trailing_stop_type') == 'atr' and market_data:
            atr = Decimal(str(market_data.get('atr', 0)))
            multiplier = Decimal(str(self.config.get('trailing_stop_distance', 2.0)))
            distance = atr * multiplier
            
            if side == 'BUY' or side == 'long':
                return highest_price - distance
            else:
                lowest_price = Decimal(str(position.get('lowest_price', position.get('current_price', 0))))
                return lowest_price + distance
        
        return None