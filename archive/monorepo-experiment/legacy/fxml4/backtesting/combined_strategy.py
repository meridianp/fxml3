"""Combined backtesting strategy integrating ML, sentiment, and Elliott Wave analysis.

This module provides a backtesting strategy that leverages the combined signal generator
with ML, sentiment, and Elliott Wave components.
"""

import logging
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from fxml4.backtesting.event import (
    SignalEvent,
    EventType,
    OrderEvent,
)
from fxml4.backtesting.event_driven_engine import Portfolio
from fxml4.backtesting.risk_management import (
    PositionSizer,
    StopLossManager,
    RiskManager,
)

# Temporary implementation of TakeProfitManager until it's properly added to risk_management.py
class TakeProfitManager:
    """Take profit management for backtesting.
    
    This class handles take profit calculations and management.
    """
    
    def __init__(
        self,
        default_profit_pct: float = 2.0,
        use_wave_targets: bool = False
    ):
        """Initialize the take profit manager.
        
        Args:
            default_profit_pct: Default take profit percentage.
            use_wave_targets: Use wave-based targets if available.
        """
        self.default_profit_pct = default_profit_pct
        self.use_wave_targets = use_wave_targets
        
    def calculate_take_profit(
        self,
        entry_price: float,
        signal: SignalEvent,
        risk_amount: float = 0.0
    ) -> float:
        """Calculate take profit level.
        
        Args:
            entry_price: Entry price.
            signal: Signal event.
            risk_amount: Risk amount for risk-reward based calculation.
            
        Returns:
            Take profit level.
        """
        # Check if signal has predefined take profit
        if "metadata" in dir(signal) and isinstance(signal.metadata, dict):
            if "take_profit" in signal.metadata:
                take_profit = signal.metadata["take_profit"]
                if isinstance(take_profit, dict) and "target" in take_profit:
                    return take_profit["target"]
                elif isinstance(take_profit, (int, float)):
                    return take_profit
        
        # Calculate take profit based on default percentage
        if "LONG" in signal.signal_type:
            return entry_price * (1 + self.default_profit_pct / 100)
        else:  # SHORT
            return entry_price * (1 - self.default_profit_pct / 100)
from fxml4.strategy.combined_signal_generator import CombinedSignalGenerator
from fxml4.strategy.integrated_strategy import Signal, SignalType

logger = logging.getLogger(__name__)


class CombinedStrategy:
    """Combined strategy for backtesting with ML, sentiment, and Elliott Wave signals."""
    
    def __init__(
        self,
        signal_generator: CombinedSignalGenerator,
        config: Optional[Dict[str, Any]] = None
    ):
        """Initialize the combined strategy.
        
        Args:
            signal_generator: Combined signal generator.
            config: Configuration dictionary.
        """
        self.signal_generator = signal_generator
        self.config = config or {}
        
        # Risk management settings
        self.use_dynamic_stops = self.config.get("use_dynamic_stops", True)
        self.use_wave_stops = self.config.get("use_wave_stops", True)
        self.position_size_pct = self.config.get("position_size_pct", 2.0)
        self.max_risk_pct = self.config.get("max_risk_pct", 2.0)
        self.adjustable_stops = self.config.get("adjustable_stops", True)
        
        # Signal processing settings
        self.signal_cooldown = self.config.get("signal_cooldown", 0)
        self.min_signal_strength = self.config.get("min_signal_strength", 0.6)
        
        # Position tracking
        self.current_position: Optional[Dict[str, Any]] = None
        self.last_signal_time: Dict[str, pd.Timestamp] = {}
        
        # Risk managers
        self.position_sizer = PositionSizer(
            sizing_method="risk_pct",
            default_size_pct=self.position_size_pct,
            max_risk_pct=self.max_risk_pct
        )
        
        self.stop_loss_manager = StopLossManager(
            default_stop_pct=1.5,
            trailing_stop=self.adjustable_stops,
            enable_wave_stops=self.use_wave_stops
        )
        
        self.take_profit_manager = TakeProfitManager(
            default_profit_pct=3.0,
            use_wave_targets=self.use_wave_stops
        )
        
        self.risk_manager = RiskManager(
            position_sizer=self.position_sizer,
            stop_loss_manager=self.stop_loss_manager,
            take_profit_manager=self.take_profit_manager
        )
        
        logger.info("Initialized combined strategy")
    
    def _should_ignore_signal(
        self, 
        signal: Signal, 
        current_time: pd.Timestamp
    ) -> bool:
        """Check if a signal should be ignored due to cooldown.
        
        Args:
            signal: Trading signal.
            current_time: Current timestamp.
            
        Returns:
            Whether to ignore the signal.
        """
        signal_key = f"{signal.signal_type.value}_{signal.symbol}"
        
        # If no cooldown, don't ignore
        if self.signal_cooldown <= 0:
            return False
            
        # Check if we've seen a signal of this type recently
        if signal_key in self.last_signal_time:
            last_time = self.last_signal_time[signal_key]
            time_diff = (current_time - last_time).total_seconds()
            
            # If signal is within cooldown period, ignore it
            if time_diff < self.signal_cooldown:
                return True
                
        # Update last signal time
        self.last_signal_time[signal_key] = current_time
        
        return False
    
    def _process_entry_signals(
        self, 
        signals: List[Signal], 
        symbol: str,
        timestamp: pd.Timestamp,
        current_price: float,
        portfolio: Optional[Portfolio] = None
    ) -> List[SignalEvent]:
        """Process entry signals and generate signal events.
        
        Args:
            signals: List of trading signals.
            symbol: Market symbol.
            timestamp: Current timestamp.
            current_price: Current price.
            portfolio: Optional portfolio instance.
            
        Returns:
            List of signal events.
        """
        signal_events = []
        
        # Filter signals by strength and type
        entry_signals = [
            s for s in signals 
            if s.signal_type in [SignalType.ENTRY_LONG, SignalType.ENTRY_SHORT] 
            and s.strength >= self.min_signal_strength
            and not self._should_ignore_signal(s, timestamp)
        ]
        
        for signal in entry_signals:
            # Skip if we're already in a position
            if self.current_position is not None:
                # If position is in the same direction, ignore
                if (self.current_position["direction"] == "LONG" and 
                    signal.signal_type == SignalType.ENTRY_LONG) or \
                   (self.current_position["direction"] == "SHORT" and 
                    signal.signal_type == SignalType.ENTRY_SHORT):
                    continue
                    
                # If position is in the opposite direction, close it first
                signal_events.extend(self._create_exit_events(
                    self.current_position["direction"], 
                    symbol, 
                    timestamp,
                    "Signal in opposite direction"
                ))
            
            # Determine direction based on signal type
            direction = "LONG" if signal.signal_type == SignalType.ENTRY_LONG else "SHORT"
            
            # Determine position size based on risk
            position_size = 1.0  # Default
            stop_loss_price = None
            take_profit_price = None
            
            # Extract stop loss and take profit levels from signal metadata
            if "stop_loss" in signal.metadata:
                stop_loss_price = signal.metadata["stop_loss"]
                
            if "take_profit" in signal.metadata and isinstance(signal.metadata["take_profit"], dict):
                take_profit_data = signal.metadata["take_profit"]
                if "target" in take_profit_data:
                    take_profit_price = take_profit_data["target"]
                elif "moderate" in take_profit_data:
                    take_profit_price = take_profit_data["moderate"]
            
            # Calculate risk-based position size if we have stop loss
            if stop_loss_price is not None and portfolio is not None:
                risk_per_share = abs(current_price - stop_loss_price)
                if risk_per_share > 0:
                    max_risk_amount = portfolio.equity * (self.max_risk_pct / 100)
                    position_size = max_risk_amount / risk_per_share
            
            # Create signal event
            signal_event = SignalEvent(
                symbol=symbol,
                timestamp=timestamp,
                signal_type=direction,  # "LONG" or "SHORT"
                strength=signal.strength,
                quantity=position_size,
                limit_price=None,  # Market order
                stop_price=None,  # Market order
                metadata={
                    "stop_loss": stop_loss_price,
                    "take_profit": take_profit_price,
                    "source": signal.source.value,
                    "confidence": signal.strength,
                    "signals": [s.to_dict() for s in signals],  # Include all signals
                    "current_price": current_price,
                }
            )
            
            signal_events.append(signal_event)
            
            # Update current position
            self.current_position = {
                "direction": direction,
                "entry_price": current_price,
                "entry_time": timestamp,
                "stop_loss": stop_loss_price,
                "take_profit": take_profit_price,
                "quantity": position_size,
                "metadata": signal.metadata,
            }
        
        return signal_events
    
    def _process_exit_signals(
        self, 
        signals: List[Signal], 
        symbol: str,
        timestamp: pd.Timestamp,
        current_price: float
    ) -> List[SignalEvent]:
        """Process exit signals and generate signal events.
        
        Args:
            signals: List of trading signals.
            symbol: Market symbol.
            timestamp: Current timestamp.
            current_price: Current price.
            
        Returns:
            List of signal events.
        """
        signal_events = []
        
        # Check if we have a position
        if self.current_position is None:
            return signal_events
            
        # Filter signals by strength and type
        exit_long_signals = [
            s for s in signals 
            if s.signal_type == SignalType.EXIT_LONG 
            and s.strength >= self.min_signal_strength
            and not self._should_ignore_signal(s, timestamp)
        ]
        
        exit_short_signals = [
            s for s in signals 
            if s.signal_type == SignalType.EXIT_SHORT 
            and s.strength >= self.min_signal_strength
            and not self._should_ignore_signal(s, timestamp)
        ]
        
        # Check if we have a matching exit signal
        if self.current_position["direction"] == "LONG" and exit_long_signals:
            # Use the strongest exit signal
            exit_signal = max(exit_long_signals, key=lambda s: s.strength)
            signal_events.extend(self._create_exit_events(
                "LONG", 
                symbol, 
                timestamp,
                f"Exit signal from {exit_signal.source.value}"
            ))
            
        elif self.current_position["direction"] == "SHORT" and exit_short_signals:
            # Use the strongest exit signal
            exit_signal = max(exit_short_signals, key=lambda s: s.strength)
            signal_events.extend(self._create_exit_events(
                "SHORT", 
                symbol, 
                timestamp,
                f"Exit signal from {exit_signal.source.value}"
            ))
        
        return signal_events
    
    def _check_stop_loss(
        self, 
        symbol: str,
        timestamp: pd.Timestamp,
        current_price: float
    ) -> List[SignalEvent]:
        """Check if stop loss has been triggered.
        
        Args:
            symbol: Market symbol.
            timestamp: Current timestamp.
            current_price: Current price.
            
        Returns:
            List of signal events.
        """
        if self.current_position is None or self.current_position["stop_loss"] is None:
            return []
            
        # Check stop loss
        if self.current_position["direction"] == "LONG":
            if current_price <= self.current_position["stop_loss"]:
                return self._create_exit_events("LONG", symbol, timestamp, "Stop loss triggered")
        else:  # SHORT
            if current_price >= self.current_position["stop_loss"]:
                return self._create_exit_events("SHORT", symbol, timestamp, "Stop loss triggered")
                
        return []
    
    def _check_take_profit(
        self, 
        symbol: str,
        timestamp: pd.Timestamp,
        current_price: float
    ) -> List[SignalEvent]:
        """Check if take profit has been triggered.
        
        Args:
            symbol: Market symbol.
            timestamp: Current timestamp.
            current_price: Current price.
            
        Returns:
            List of signal events.
        """
        if self.current_position is None or self.current_position["take_profit"] is None:
            return []
            
        # Check take profit
        if self.current_position["direction"] == "LONG":
            if current_price >= self.current_position["take_profit"]:
                return self._create_exit_events("LONG", symbol, timestamp, "Take profit triggered")
        else:  # SHORT
            if current_price <= self.current_position["take_profit"]:
                return self._create_exit_events("SHORT", symbol, timestamp, "Take profit triggered")
                
        return []
    
    def _create_exit_events(
        self, 
        direction: str,
        symbol: str,
        timestamp: pd.Timestamp,
        reason: str
    ) -> List[SignalEvent]:
        """Create exit signal events.
        
        Args:
            direction: Position direction.
            symbol: Market symbol.
            timestamp: Current timestamp.
            reason: Exit reason.
            
        Returns:
            List of signal events.
        """
        # Reset current position
        self.current_position = None
        
        # Create signal event
        signal_event = SignalEvent(
            symbol=symbol,
            timestamp=timestamp,
            signal_type=f"EXIT_{direction}",
            strength=1.0,
            quantity=None,  # Close all
            limit_price=None,  # Market order
            stop_price=None,  # Market order
            metadata={
                "reason": reason,
            }
        )
        
        return [signal_event]
    
    def _update_stops(
        self, 
        current_price: float,
        current_bar: pd.Series
    ) -> None:
        """Update trailing stop loss and take profit levels.
        
        Args:
            current_price: Current price.
            current_bar: Current price bar.
        """
        if self.current_position is None or not self.adjustable_stops:
            return
            
        # Update trailing stop loss
        if self.current_position["direction"] == "LONG":
            # Update stop loss to trail price
            if self.current_position["stop_loss"] is not None:
                new_stop = current_bar["low"] * 0.995  # 0.5% below the low
                if new_stop > self.current_position["stop_loss"]:
                    self.current_position["stop_loss"] = new_stop
        else:  # SHORT
            # Update stop loss to trail price
            if self.current_position["stop_loss"] is not None:
                new_stop = current_bar["high"] * 1.005  # 0.5% above the high
                if new_stop < self.current_position["stop_loss"]:
                    self.current_position["stop_loss"] = new_stop
    
    def generate_signals(
        self,
        symbol: str,
        current_bar: pd.Series,
        market_data: pd.DataFrame,
        portfolio: Optional[Portfolio] = None
    ) -> List[SignalEvent]:
        """Generate trading signals for the current bar.
        
        Args:
            symbol: Market symbol.
            current_bar: Current price bar.
            market_data: Historical market data.
            portfolio: Optional portfolio instance.
            
        Returns:
            List of signal events.
        """
        # Get current timestamp and price
        timestamp = current_bar.name if isinstance(current_bar.name, pd.Timestamp) else pd.Timestamp.now()
        current_price = current_bar["close"]
        
        # Initialize signal events list
        signal_events = []
        
        # Update trailing stops if in a position
        self._update_stops(current_price, current_bar)
        
        # Check stop loss and take profit
        signal_events.extend(self._check_stop_loss(symbol, timestamp, current_price))
        signal_events.extend(self._check_take_profit(symbol, timestamp, current_price))
        
        # Get signals from combined signal generator
        signals = self.signal_generator.generate_signals(market_data)
        
        if not signals:
            return signal_events
            
        # Process exit signals first
        signal_events.extend(self._process_exit_signals(signals, symbol, timestamp, current_price))
        
        # Then process entry signals
        signal_events.extend(self._process_entry_signals(signals, symbol, timestamp, current_price, portfolio))
        
        return signal_events