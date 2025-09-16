"""Execution module for the backtesting system.

This module handles the execution of orders with realistic simulation of market mechanics.
"""

import logging
import math
import random
import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from fxml4.backtesting.event import EventType, FillEvent, OrderEvent

logger = logging.getLogger(__name__)


class SlippageModel:
    """Base class for slippage models."""
    
    def calculate_slippage(
        self, 
        order: OrderEvent, 
        bar: pd.Series,
        volume: Optional[float] = None,
    ) -> float:
        """Calculate slippage for a given order.
        
        Args:
            order: Order event.
            bar: Current price bar.
            volume: Volume available for execution.
            
        Returns:
            Slippage amount in price units.
        """
        raise NotImplementedError("Subclasses must implement calculate_slippage")


class FixedSlippageModel(SlippageModel):
    """Fixed slippage model.
    
    Applies a fixed percentage slippage to all orders.
    """
    
    def __init__(self, slippage_pct: float = 0.0001):
        """Initialize a fixed slippage model.
        
        Args:
            slippage_pct: Slippage percentage (default: 0.01%).
        """
        self.slippage_pct = slippage_pct
    
    def calculate_slippage(
        self,
        order: OrderEvent,
        bar: pd.Series,
        volume: Optional[float] = None,
    ) -> float:
        """Calculate fixed slippage.
        
        Args:
            order: Order event.
            bar: Current price bar.
            volume: Volume available for execution.
            
        Returns:
            Slippage amount in price units.
        """
        base_price = order.price or bar["close"]
        slippage = base_price * self.slippage_pct
        
        # Apply slippage in the direction of the order
        if order.side.lower() == "buy":
            return slippage
        else:
            return -slippage


class VolumeBasedSlippageModel(SlippageModel):
    """Volume-based slippage model.
    
    Calculates slippage based on order size relative to available volume.
    """
    
    def __init__(
        self,
        base_slippage_pct: float = 0.0001,
        volume_factor: float = 0.1,
        max_slippage_pct: float = 0.01,
    ):
        """Initialize a volume-based slippage model.
        
        Args:
            base_slippage_pct: Base slippage percentage (default: 0.01%).
            volume_factor: Volume impact factor.
            max_slippage_pct: Maximum slippage percentage.
        """
        self.base_slippage_pct = base_slippage_pct
        self.volume_factor = volume_factor
        self.max_slippage_pct = max_slippage_pct
    
    def calculate_slippage(
        self,
        order: OrderEvent,
        bar: pd.Series,
        volume: Optional[float] = None,
    ) -> float:
        """Calculate volume-based slippage.
        
        Args:
            order: Order event.
            bar: Current price bar.
            volume: Volume available for execution.
            
        Returns:
            Slippage amount in price units.
        """
        base_price = order.price or bar["close"]
        
        # If volume is not provided, use bar volume
        if volume is None and "volume" in bar:
            volume = bar["volume"]
        elif volume is None:
            # Default to low volume if not available
            volume = 1000
        
        # Calculate volume ratio (order size / available volume)
        volume_ratio = order.quantity / volume if volume > 0 else 1.0
        
        # Calculate slippage percentage based on volume ratio
        slippage_pct = self.base_slippage_pct + (volume_ratio * self.volume_factor)
        slippage_pct = min(slippage_pct, self.max_slippage_pct)
        
        # Calculate slippage amount
        slippage = base_price * slippage_pct
        
        # Apply slippage in the direction of the order
        if order.side.lower() == "buy":
            return slippage
        else:
            return -slippage


class VolatilitySlippageModel(SlippageModel):
    """Volatility-based slippage model.
    
    Calculates slippage based on recent price volatility.
    """
    
    def __init__(
        self,
        base_slippage_pct: float = 0.0001,
        volatility_window: int = 20,
        volatility_factor: float = 0.5,
        max_slippage_pct: float = 0.01,
    ):
        """Initialize a volatility-based slippage model.
        
        Args:
            base_slippage_pct: Base slippage percentage (default: 0.01%).
            volatility_window: Window for volatility calculation.
            volatility_factor: Volatility impact factor.
            max_slippage_pct: Maximum slippage percentage.
        """
        self.base_slippage_pct = base_slippage_pct
        self.volatility_window = volatility_window
        self.volatility_factor = volatility_factor
        self.max_slippage_pct = max_slippage_pct
        self.volatility_cache: Dict[str, float] = {}
    
    def calculate_slippage(
        self,
        order: OrderEvent,
        bar: pd.Series,
        volume: Optional[float] = None,
        data_window: Optional[pd.DataFrame] = None,
    ) -> float:
        """Calculate volatility-based slippage.
        
        Args:
            order: Order event.
            bar: Current price bar.
            volume: Volume available for execution.
            data_window: Recent price data for volatility calculation.
            
        Returns:
            Slippage amount in price units.
        """
        base_price = order.price or bar["close"]
        
        # Calculate volatility if data window is provided
        if data_window is not None and len(data_window) >= self.volatility_window:
            recent_data = data_window.iloc[-self.volatility_window:]
            returns = recent_data["close"].pct_change().dropna()
            volatility = returns.std()
            
            # Cache volatility for this symbol
            self.volatility_cache[order.symbol] = volatility
        else:
            # Use cached volatility or default
            volatility = self.volatility_cache.get(order.symbol, 0.001)
        
        # Calculate slippage percentage based on volatility
        slippage_pct = self.base_slippage_pct + (volatility * self.volatility_factor)
        slippage_pct = min(slippage_pct, self.max_slippage_pct)
        
        # Calculate slippage amount
        slippage = base_price * slippage_pct
        
        # Apply slippage in the direction of the order
        if order.side.lower() == "buy":
            return slippage
        else:
            return -slippage


class HybridSlippageModel(SlippageModel):
    """Hybrid slippage model combining volume and volatility effects.
    
    This model provides the most realistic slippage simulation.
    """
    
    def __init__(
        self,
        base_slippage_pct: float = 0.0001,
        volume_factor: float = 0.1,
        volatility_window: int = 20,
        volatility_factor: float = 0.5,
        random_factor: float = 0.2,
        max_slippage_pct: float = 0.01,
    ):
        """Initialize a hybrid slippage model.
        
        Args:
            base_slippage_pct: Base slippage percentage (default: 0.01%).
            volume_factor: Volume impact factor.
            volatility_window: Window for volatility calculation.
            volatility_factor: Volatility impact factor.
            random_factor: Random noise factor.
            max_slippage_pct: Maximum slippage percentage.
        """
        self.base_slippage_pct = base_slippage_pct
        self.volume_factor = volume_factor
        self.volatility_window = volatility_window
        self.volatility_factor = volatility_factor
        self.random_factor = random_factor
        self.max_slippage_pct = max_slippage_pct
        self.volatility_cache: Dict[str, float] = {}
    
    def calculate_slippage(
        self,
        order: OrderEvent,
        bar: pd.Series,
        volume: Optional[float] = None,
        data_window: Optional[pd.DataFrame] = None,
    ) -> float:
        """Calculate hybrid slippage.
        
        Args:
            order: Order event.
            bar: Current price bar.
            volume: Volume available for execution.
            data_window: Recent price data for volatility calculation.
            
        Returns:
            Slippage amount in price units.
        """
        base_price = order.price or bar["close"]
        
        # Volume component
        if volume is None and "volume" in bar:
            volume = bar["volume"]
        elif volume is None:
            volume = 1000
        
        volume_ratio = order.quantity / volume if volume > 0 else 1.0
        volume_slippage = volume_ratio * self.volume_factor
        
        # Volatility component
        if data_window is not None and len(data_window) >= self.volatility_window:
            recent_data = data_window.iloc[-self.volatility_window:]
            returns = recent_data["close"].pct_change().dropna()
            volatility = returns.std()
            self.volatility_cache[order.symbol] = volatility
        else:
            volatility = self.volatility_cache.get(order.symbol, 0.001)
        
        volatility_slippage = volatility * self.volatility_factor
        
        # Random component (market noise)
        random_slippage = random.uniform(0, self.random_factor * self.base_slippage_pct)
        
        # Combine components
        slippage_pct = self.base_slippage_pct + volume_slippage + volatility_slippage + random_slippage
        slippage_pct = min(slippage_pct, self.max_slippage_pct)
        
        # Calculate slippage amount
        slippage = base_price * slippage_pct
        
        # Apply slippage in the direction of the order
        if order.side.lower() == "buy":
            return slippage
        else:
            return -slippage


class FeeModel:
    """Base class for fee models."""
    
    def calculate_fee(self, order: OrderEvent, fill_price: float) -> float:
        """Calculate fee for an executed order.
        
        Args:
            order: Order event.
            fill_price: Execution price.
            
        Returns:
            Fee amount.
        """
        raise NotImplementedError("Subclasses must implement calculate_fee")


class FixedFeeModel(FeeModel):
    """Fixed fee model.
    
    Applies a fixed percentage fee to all orders.
    """
    
    def __init__(self, fee_pct: float = 0.001):
        """Initialize a fixed fee model.
        
        Args:
            fee_pct: Fee percentage (default: 0.1%).
        """
        self.fee_pct = fee_pct
    
    def calculate_fee(self, order: OrderEvent, fill_price: float) -> float:
        """Calculate fixed fee.
        
        Args:
            order: Order event.
            fill_price: Execution price.
            
        Returns:
            Fee amount.
        """
        notional_value = order.quantity * fill_price
        return notional_value * self.fee_pct


class TieredFeeModel(FeeModel):
    """Tiered fee model.
    
    Applies different fee percentages based on order size.
    """
    
    def __init__(
        self,
        tiers: Optional[List[Tuple[float, float]]] = None,
        base_fee_pct: float = 0.001,
    ):
        """Initialize a tiered fee model.
        
        Args:
            tiers: List of (threshold, fee_pct) tuples.
            base_fee_pct: Base fee percentage.
        """
        self.base_fee_pct = base_fee_pct
        self.tiers = tiers or [
            (1000, 0.002),    # < $1000: 0.2%
            (10000, 0.0015),  # $1000-$10000: 0.15%
            (100000, 0.001),  # $10000-$100000: 0.1%
            (float('inf'), 0.0005),  # > $100000: 0.05%
        ]
        
        # Sort tiers by threshold
        self.tiers.sort(key=lambda x: x[0])
    
    def calculate_fee(self, order: OrderEvent, fill_price: float) -> float:
        """Calculate tiered fee.
        
        Args:
            order: Order event.
            fill_price: Execution price.
            
        Returns:
            Fee amount.
        """
        notional_value = order.quantity * fill_price
        
        # Find applicable tier
        fee_pct = self.base_fee_pct
        for threshold, tier_fee_pct in self.tiers:
            if notional_value <= threshold:
                fee_pct = tier_fee_pct
                break
        
        return notional_value * fee_pct


class ExchangeFeeModel(FeeModel):
    """Exchange-specific fee model.
    
    Models the fee structure of specific exchanges.
    """
    
    def __init__(
        self,
        exchange: str = "generic",
        maker_fee_pct: float = 0.001,
        taker_fee_pct: float = 0.002,
    ):
        """Initialize an exchange fee model.
        
        Args:
            exchange: Exchange name.
            maker_fee_pct: Maker fee percentage.
            taker_fee_pct: Taker fee percentage.
        """
        self.exchange = exchange.lower()
        self.maker_fee_pct = maker_fee_pct
        self.taker_fee_pct = taker_fee_pct
        
        # Exchange-specific fee structures
        if self.exchange == "binance":
            self.maker_fee_pct = 0.0010
            self.taker_fee_pct = 0.0010
        elif self.exchange == "kraken":
            self.maker_fee_pct = 0.0016
            self.taker_fee_pct = 0.0026
        elif self.exchange == "coinbase":
            self.maker_fee_pct = 0.0040
            self.taker_fee_pct = 0.0060
        elif self.exchange == "forex":
            self.maker_fee_pct = 0.0002
            self.taker_fee_pct = 0.0002
        elif self.exchange == "interactive_brokers":
            self.maker_fee_pct = 0.0005
            self.taker_fee_pct = 0.0005
        elif self.exchange == "tradier":
            self.maker_fee_pct = 0.0005
            self.taker_fee_pct = 0.0005
    
    def calculate_fee(self, order: OrderEvent, fill_price: float) -> float:
        """Calculate exchange-specific fee.
        
        Args:
            order: Order event.
            fill_price: Execution price.
            
        Returns:
            Fee amount.
        """
        notional_value = order.quantity * fill_price
        
        # Determine if order is maker or taker
        is_taker = order.order_type.lower() in ["market", "stop", "stop_limit"]
        fee_pct = self.taker_fee_pct if is_taker else self.maker_fee_pct
        
        return notional_value * fee_pct


class ExecutionHandler:
    """Execution handler for processing order events."""
    
    def __init__(
        self,
        slippage_model: Optional[SlippageModel] = None,
        fee_model: Optional[FeeModel] = None,
    ):
        """Initialize the execution handler.
        
        Args:
            slippage_model: Slippage model to use.
            fee_model: Fee model to use.
        """
        self.slippage_model = slippage_model or HybridSlippageModel()
        self.fee_model = fee_model or ExchangeFeeModel()
        self.orders: Dict[str, OrderEvent] = {}
        self.pending_orders: Dict[str, OrderEvent] = {}
        self.filled_orders: Dict[str, FillEvent] = {}
        
        logger.info(
            "Initialized execution handler with %s slippage model and %s fee model",
            self.slippage_model.__class__.__name__,
            self.fee_model.__class__.__name__,
        )
    
    def process_order(
        self,
        order: OrderEvent,
        bar: pd.Series,
        data_window: Optional[pd.DataFrame] = None,
    ) -> Optional[FillEvent]:
        """Process an order and generate fill event if executed.
        
        Args:
            order: Order event to process.
            bar: Current price bar.
            data_window: Recent price data for volatility calculation.
            
        Returns:
            Fill event if the order is executed, None otherwise.
        """
        # Save the order
        self.orders[order.order_id] = order
        
        # Process different order types
        if order.order_type.lower() == "market":
            return self._execute_market_order(order, bar, data_window)
        elif order.order_type.lower() == "limit":
            return self._process_limit_order(order, bar)
        elif order.order_type.lower() == "stop":
            return self._process_stop_order(order, bar)
        elif order.order_type.lower() == "stop_limit":
            return self._process_stop_limit_order(order, bar)
        else:
            logger.warning("Unknown order type: %s", order.order_type)
            return None
    
    def process_bar(
        self,
        bar: pd.Series,
        data_window: Optional[pd.DataFrame] = None,
    ) -> List[FillEvent]:
        """Process pending orders against a new price bar.
        
        Args:
            bar: New price bar.
            data_window: Recent price data for volatility calculation.
            
        Returns:
            List of fill events generated.
        """
        fills: List[FillEvent] = []
        
        # Process each pending order
        for order_id, order in list(self.pending_orders.items()):
            fill = None
            
            if order.order_type.lower() == "limit":
                fill = self._check_limit_execution(order, bar, data_window)
            elif order.order_type.lower() == "stop":
                fill = self._check_stop_execution(order, bar, data_window)
            elif order.order_type.lower() == "stop_limit":
                fill = self._check_stop_limit_execution(order, bar, data_window)
            
            if fill:
                fills.append(fill)
                self.filled_orders[order_id] = fill
                del self.pending_orders[order_id]
        
        return fills
    
    def _execute_market_order(
        self,
        order: OrderEvent,
        bar: pd.Series,
        data_window: Optional[pd.DataFrame] = None,
    ) -> FillEvent:
        """Execute a market order.
        
        Args:
            order: Market order to execute.
            bar: Current price bar.
            data_window: Recent price data for volatility calculation.
            
        Returns:
            Fill event.
        """
        # Calculate execution price with slippage
        slippage = self.slippage_model.calculate_slippage(
            order, bar, data_window=data_window
        )
        
        # Determine execution price
        if order.side.lower() == "buy":
            # For buys, higher price due to slippage
            fill_price = bar["close"] + slippage
        else:
            # For sells, lower price due to slippage
            fill_price = bar["close"] + slippage
        
        # Calculate commission
        commission = self.fee_model.calculate_fee(order, fill_price)
        
        # Create fill event
        fill = FillEvent(
            timestamp=order.timestamp,
            order_id=order.order_id,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            filled_price=fill_price,
            commission=commission,
            slippage=abs(slippage),
            fill_time=order.timestamp,
        )
        
        logger.debug(
            "Executed market order %s: %s %s %s @ %s (slippage: %s, commission: %s)",
            order.order_id,
            order.symbol,
            order.side,
            order.quantity,
            fill_price,
            slippage,
            commission,
        )
        
        return fill
    
    def _process_limit_order(
        self,
        order: OrderEvent,
        bar: pd.Series,
    ) -> Optional[FillEvent]:
        """Process a limit order.
        
        Args:
            order: Limit order to process.
            bar: Current price bar.
            
        Returns:
            Fill event if the order is immediately executed, None otherwise.
        """
        if order.price is None:
            logger.warning("Limit order %s has no price", order.order_id)
            return None
        
        # Check if the limit order can be immediately executed
        if order.side.lower() == "buy" and bar["low"] <= order.price:
            # Buy limit executed if price drops to or below limit price
            execution_price = min(bar["open"], order.price)
            return self._create_limit_fill(order, execution_price)
        elif order.side.lower() == "sell" and bar["high"] >= order.price:
            # Sell limit executed if price rises to or above limit price
            execution_price = max(bar["open"], order.price)
            return self._create_limit_fill(order, execution_price)
        else:
            # Add to pending orders
            self.pending_orders[order.order_id] = order
            return None
    
    def _process_stop_order(
        self,
        order: OrderEvent,
        bar: pd.Series,
    ) -> Optional[FillEvent]:
        """Process a stop order.
        
        Args:
            order: Stop order to process.
            bar: Current price bar.
            
        Returns:
            Fill event if the order is immediately executed, None otherwise.
        """
        if order.stop_price is None:
            logger.warning("Stop order %s has no stop price", order.order_id)
            return None
        
        # Check if the stop order is triggered in this bar
        if order.side.lower() == "buy" and bar["high"] >= order.stop_price:
            # Buy stop triggered if price rises to or above stop price
            execution_price = max(bar["open"], order.stop_price)
            return self._create_stop_fill(order, execution_price, bar)
        elif order.side.lower() == "sell" and bar["low"] <= order.stop_price:
            # Sell stop triggered if price drops to or below stop price
            execution_price = min(bar["open"], order.stop_price)
            return self._create_stop_fill(order, execution_price, bar)
        else:
            # Add to pending orders
            self.pending_orders[order.order_id] = order
            return None
    
    def _process_stop_limit_order(
        self,
        order: OrderEvent,
        bar: pd.Series,
    ) -> Optional[FillEvent]:
        """Process a stop-limit order.
        
        Args:
            order: Stop-limit order to process.
            bar: Current price bar.
            
        Returns:
            Fill event if the order is immediately executed, None otherwise.
        """
        if order.stop_price is None or order.limit_price is None:
            logger.warning("Stop-limit order %s missing prices", order.order_id)
            return None
        
        # Check if the stop price is triggered
        is_triggered = False
        
        if order.side.lower() == "buy" and bar["high"] >= order.stop_price:
            # Buy stop-limit triggered if price rises to or above stop price
            is_triggered = True
        elif order.side.lower() == "sell" and bar["low"] <= order.stop_price:
            # Sell stop-limit triggered if price drops to or below stop price
            is_triggered = True
        
        if is_triggered:
            # Convert to a limit order once triggered
            limit_order = OrderEvent(
                timestamp=order.timestamp,
                order_id=order.order_id,
                symbol=order.symbol,
                order_type="limit",
                side=order.side,
                quantity=order.quantity,
                price=order.limit_price,
                time_in_force=order.time_in_force,
                parent_order_id=order.parent_order_id,
                signal_id=order.signal_id,
                additional_params=order.additional_params,
            )
            
            # Process as a limit order
            return self._process_limit_order(limit_order, bar)
        else:
            # Add to pending orders
            self.pending_orders[order.order_id] = order
            return None
    
    def _check_limit_execution(
        self,
        order: OrderEvent,
        bar: pd.Series,
        data_window: Optional[pd.DataFrame] = None,
    ) -> Optional[FillEvent]:
        """Check if a pending limit order can be executed with the new bar.
        
        Args:
            order: Pending limit order.
            bar: New price bar.
            data_window: Recent price data for volatility calculation.
            
        Returns:
            Fill event if the order is executed, None otherwise.
        """
        if order.price is None:
            return None
        
        if order.side.lower() == "buy" and bar["low"] <= order.price:
            # Buy limit executed if price drops to or below limit price
            execution_price = order.price  # Fill at limit price
            return self._create_limit_fill(order, execution_price, data_window)
        elif order.side.lower() == "sell" and bar["high"] >= order.price:
            # Sell limit executed if price rises to or above limit price
            execution_price = order.price  # Fill at limit price
            return self._create_limit_fill(order, execution_price, data_window)
        
        return None
    
    def _check_stop_execution(
        self,
        order: OrderEvent,
        bar: pd.Series,
        data_window: Optional[pd.DataFrame] = None,
    ) -> Optional[FillEvent]:
        """Check if a pending stop order can be executed with the new bar.
        
        Args:
            order: Pending stop order.
            bar: New price bar.
            data_window: Recent price data for volatility calculation.
            
        Returns:
            Fill event if the order is executed, None otherwise.
        """
        if order.stop_price is None:
            return None
        
        if order.side.lower() == "buy" and bar["high"] >= order.stop_price:
            # Buy stop triggered if price rises to or above stop price
            execution_price = max(bar["open"], order.stop_price)
            return self._create_stop_fill(order, execution_price, bar, data_window)
        elif order.side.lower() == "sell" and bar["low"] <= order.stop_price:
            # Sell stop triggered if price drops to or below stop price
            execution_price = min(bar["open"], order.stop_price)
            return self._create_stop_fill(order, execution_price, bar, data_window)
        
        return None
    
    def _check_stop_limit_execution(
        self,
        order: OrderEvent,
        bar: pd.Series,
        data_window: Optional[pd.DataFrame] = None,
    ) -> Optional[FillEvent]:
        """Check if a pending stop-limit order can be executed with the new bar.
        
        Args:
            order: Pending stop-limit order.
            bar: New price bar.
            data_window: Recent price data for volatility calculation.
            
        Returns:
            Fill event if the order is executed, None otherwise.
        """
        if order.stop_price is None or order.limit_price is None:
            return None
        
        # Check if the stop price is triggered
        is_triggered = False
        
        if order.side.lower() == "buy" and bar["high"] >= order.stop_price:
            # Buy stop-limit triggered if price rises to or above stop price
            is_triggered = True
        elif order.side.lower() == "sell" and bar["low"] <= order.stop_price:
            # Sell stop-limit triggered if price drops to or below stop price
            is_triggered = True
        
        if is_triggered:
            # Convert to a limit order once triggered
            limit_order = OrderEvent(
                timestamp=order.timestamp,
                order_id=order.order_id,
                symbol=order.symbol,
                order_type="limit",
                side=order.side,
                quantity=order.quantity,
                price=order.limit_price,
                time_in_force=order.time_in_force,
                parent_order_id=order.parent_order_id,
                signal_id=order.signal_id,
                additional_params=order.additional_params,
            )
            
            # Check if the limit order can be executed immediately
            return self._check_limit_execution(limit_order, bar, data_window)
        
        return None
    
    def _create_limit_fill(
        self,
        order: OrderEvent,
        execution_price: float,
        data_window: Optional[pd.DataFrame] = None,
    ) -> FillEvent:
        """Create a fill event for a limit order.
        
        Args:
            order: Limit order.
            execution_price: Execution price.
            data_window: Recent price data for volatility calculation.
            
        Returns:
            Fill event.
        """
        # Calculate commission
        commission = self.fee_model.calculate_fee(order, execution_price)
        
        # Create fill event
        fill = FillEvent(
            timestamp=order.timestamp,
            order_id=order.order_id,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            filled_price=execution_price,
            commission=commission,
            slippage=0.0,  # No slippage for limit orders
            fill_time=order.timestamp,
        )
        
        logger.debug(
            "Executed limit order %s: %s %s %s @ %s (commission: %s)",
            order.order_id,
            order.symbol,
            order.side,
            order.quantity,
            execution_price,
            commission,
        )
        
        return fill
    
    def _create_stop_fill(
        self,
        order: OrderEvent,
        trigger_price: float,
        bar: pd.Series,
        data_window: Optional[pd.DataFrame] = None,
    ) -> FillEvent:
        """Create a fill event for a stop order.
        
        Args:
            order: Stop order.
            trigger_price: Price that triggered the stop.
            bar: Current price bar.
            data_window: Recent price data for volatility calculation.
            
        Returns:
            Fill event.
        """
        # Convert to market order once triggered
        market_order = OrderEvent(
            timestamp=order.timestamp,
            order_id=order.order_id,
            symbol=order.symbol,
            order_type="market",
            side=order.side,
            quantity=order.quantity,
            time_in_force=order.time_in_force,
            parent_order_id=order.parent_order_id,
            signal_id=order.signal_id,
            additional_params=order.additional_params,
        )
        
        # Calculate slippage for market execution after stop trigger
        slippage = self.slippage_model.calculate_slippage(
            market_order, bar, data_window=data_window
        )
        
        # Determine execution price with slippage
        if order.side.lower() == "buy":
            # For buy stops, higher price due to slippage
            fill_price = trigger_price + slippage
        else:
            # For sell stops, lower price due to slippage
            fill_price = trigger_price + slippage
        
        # Calculate commission
        commission = self.fee_model.calculate_fee(order, fill_price)
        
        # Create fill event
        fill = FillEvent(
            timestamp=order.timestamp,
            order_id=order.order_id,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            filled_price=fill_price,
            commission=commission,
            slippage=abs(slippage),
            fill_time=order.timestamp,
        )
        
        logger.debug(
            "Executed stop order %s: %s %s %s @ %s (slippage: %s, commission: %s)",
            order.order_id,
            order.symbol,
            order.side,
            order.quantity,
            fill_price,
            slippage,
            commission,
        )
        
        return fill
    
    def get_order(self, order_id: str) -> Optional[OrderEvent]:
        """Get an order by ID.
        
        Args:
            order_id: Order ID.
            
        Returns:
            Order event if found, None otherwise.
        """
        return self.orders.get(order_id)
    
    def get_fill(self, order_id: str) -> Optional[FillEvent]:
        """Get a fill by order ID.
        
        Args:
            order_id: Order ID.
            
        Returns:
            Fill event if found, None otherwise.
        """
        return self.filled_orders.get(order_id)
    
    def clear(self) -> None:
        """Clear all orders and fills."""
        self.orders.clear()
        self.pending_orders.clear()
        self.filled_orders.clear()
        logger.debug("Cleared execution handler state")