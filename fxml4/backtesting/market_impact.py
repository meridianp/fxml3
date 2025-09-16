"""Market impact simulation for realistic backtesting.

This module provides models for simulating market impact in backtesting.
"""

import logging
import math
from typing import Dict, Optional

import numpy as np
import pandas as pd

from fxml4.backtesting.event import OrderEvent

logger = logging.getLogger(__name__)


class MarketImpactModel:
    """Base class for market impact models."""

    def calculate_impact(
        self,
        order: OrderEvent,
        bar: pd.Series,
        volume: Optional[float] = None,
        market_data: Optional[pd.DataFrame] = None,
    ) -> float:
        """Calculate market impact for a given order.

        Args:
            order: Order event.
            bar: Current price bar.
            volume: Volume available for execution.
            market_data: Historical market data.

        Returns:
            Market impact amount in price units.
        """
        raise NotImplementedError("Subclasses must implement calculate_impact")


class FixedMarketImpactModel(MarketImpactModel):
    """Fixed market impact model.

    Applies a fixed percentage impact based on order size.
    """

    def __init__(self, impact_pct: float = 0.0001):
        """Initialize a fixed market impact model.

        Args:
            impact_pct: Impact percentage (default: 0.01%).
        """
        self.impact_pct = impact_pct

    def calculate_impact(
        self,
        order: OrderEvent,
        bar: pd.Series,
        volume: Optional[float] = None,
        market_data: Optional[pd.DataFrame] = None,
    ) -> float:
        """Calculate fixed market impact.

        Args:
            order: Order event.
            bar: Current price bar.
            volume: Volume available for execution.
            market_data: Historical market data.

        Returns:
            Market impact amount in price units.
        """
        base_price = order.price or bar["close"]
        impact = base_price * self.impact_pct

        # Apply impact in the direction of the order
        if order.side.lower() == "buy":
            return impact
        else:
            return -impact


class SquareRootModel(MarketImpactModel):
    """Square root market impact model.

    Implementation of the classic square root law for market impact.
    Formula: impact = k * sigma * sqrt(order_size / ADV)
    """

    def __init__(
        self,
        k: float = 0.1,
        volatility_window: int = 20,
        adv_window: int = 20,
    ):
        """Initialize a square root market impact model.

        Args:
            k: Impact coefficient (empirically determined).
            volatility_window: Window for volatility calculation.
            adv_window: Window for average daily volume calculation.
        """
        self.k = k
        self.volatility_window = volatility_window
        self.adv_window = adv_window
        self.volatility_cache: Dict[str, float] = {}
        self.adv_cache: Dict[str, float] = {}

    def calculate_impact(
        self,
        order: OrderEvent,
        bar: pd.Series,
        volume: Optional[float] = None,
        market_data: Optional[pd.DataFrame] = None,
    ) -> float:
        """Calculate square root market impact.

        Args:
            order: Order event.
            bar: Current price bar.
            volume: Volume available for execution.
            market_data: Historical market data.

        Returns:
            Market impact amount in price units.
        """
        base_price = order.price or bar["close"]

        # Calculate or use cached volatility
        if market_data is not None and len(market_data) >= self.volatility_window:
            recent_data = market_data.iloc[-self.volatility_window :]
            returns = recent_data["close"].pct_change().dropna()
            volatility = returns.std()
            self.volatility_cache[order.symbol] = volatility
        else:
            volatility = self.volatility_cache.get(order.symbol, 0.01)

        # Calculate or use cached average daily volume (ADV)
        if (
            market_data is not None
            and "volume" in market_data.columns
            and len(market_data) >= self.adv_window
        ):
            recent_data = market_data.iloc[-self.adv_window :]
            adv = recent_data["volume"].mean()
            self.adv_cache[order.symbol] = adv
        else:
            adv = self.adv_cache.get(order.symbol, 10000)
            if volume is not None:
                adv = max(adv, volume)

        # Sanity check to avoid division by zero
        if adv <= 0:
            adv = 10000

        # Square root impact formula
        impact_pct = self.k * volatility * math.sqrt(order.quantity / adv)
        impact = base_price * impact_pct

        # Apply impact in the direction of the order
        if order.side.lower() == "buy":
            return impact
        else:
            return -impact


class PowerLawModel(MarketImpactModel):
    """Power law market impact model.

    More flexible model with configurable power law exponent.
    Formula: impact = k * sigma * (order_size / ADV)^exponent
    """

    def __init__(
        self,
        k: float = 0.1,
        exponent: float = 0.6,  # Empirically often between 0.5 and 0.7
        volatility_window: int = 20,
        adv_window: int = 20,
    ):
        """Initialize a power law market impact model.

        Args:
            k: Impact coefficient.
            exponent: Power law exponent.
            volatility_window: Window for volatility calculation.
            adv_window: Window for average daily volume calculation.
        """
        self.k = k
        self.exponent = exponent
        self.volatility_window = volatility_window
        self.adv_window = adv_window
        self.volatility_cache: Dict[str, float] = {}
        self.adv_cache: Dict[str, float] = {}

    def calculate_impact(
        self,
        order: OrderEvent,
        bar: pd.Series,
        volume: Optional[float] = None,
        market_data: Optional[pd.DataFrame] = None,
    ) -> float:
        """Calculate power law market impact.

        Args:
            order: Order event.
            bar: Current price bar.
            volume: Volume available for execution.
            market_data: Historical market data.

        Returns:
            Market impact amount in price units.
        """
        base_price = order.price or bar["close"]

        # Calculate or use cached volatility
        if market_data is not None and len(market_data) >= self.volatility_window:
            recent_data = market_data.iloc[-self.volatility_window :]
            returns = recent_data["close"].pct_change().dropna()
            volatility = returns.std()
            self.volatility_cache[order.symbol] = volatility
        else:
            volatility = self.volatility_cache.get(order.symbol, 0.01)

        # Calculate or use cached average daily volume (ADV)
        if (
            market_data is not None
            and "volume" in market_data.columns
            and len(market_data) >= self.adv_window
        ):
            recent_data = market_data.iloc[-self.adv_window :]
            adv = recent_data["volume"].mean()
            self.adv_cache[order.symbol] = adv
        else:
            adv = self.adv_cache.get(order.symbol, 10000)
            if volume is not None:
                adv = max(adv, volume)

        # Sanity check to avoid division by zero
        if adv <= 0:
            adv = 10000

        # Power law impact formula
        impact_pct = self.k * volatility * (order.quantity / adv) ** self.exponent
        impact = base_price * impact_pct

        # Apply impact in the direction of the order
        if order.side.lower() == "buy":
            return impact
        else:
            return -impact


class LiquidityAwareModel(MarketImpactModel):
    """Liquidity-aware market impact model.

    Adjusts impact based on available liquidity in the order book.
    For backtesting, we simulate the order book based on volume and volatility.
    """

    def __init__(
        self,
        base_impact_pct: float = 0.0001,
        volatility_window: int = 20,
        liquidity_factor: float = 1.0,
        max_impact_pct: float = 0.01,
    ):
        """Initialize a liquidity-aware market impact model.

        Args:
            base_impact_pct: Base impact percentage.
            volatility_window: Window for volatility calculation.
            liquidity_factor: Factor to adjust impact based on liquidity.
            max_impact_pct: Maximum impact percentage.
        """
        self.base_impact_pct = base_impact_pct
        self.volatility_window = volatility_window
        self.liquidity_factor = liquidity_factor
        self.max_impact_pct = max_impact_pct
        self.volatility_cache: Dict[str, float] = {}

    def calculate_impact(
        self,
        order: OrderEvent,
        bar: pd.Series,
        volume: Optional[float] = None,
        market_data: Optional[pd.DataFrame] = None,
    ) -> float:
        """Calculate liquidity-aware market impact.

        Args:
            order: Order event.
            bar: Current price bar.
            volume: Volume available for execution.
            market_data: Historical market data.

        Returns:
            Market impact amount in price units.
        """
        base_price = order.price or bar["close"]

        # Calculate or use cached volatility
        if market_data is not None and len(market_data) >= self.volatility_window:
            recent_data = market_data.iloc[-self.volatility_window :]
            returns = recent_data["close"].pct_change().dropna()
            volatility = returns.std()
            self.volatility_cache[order.symbol] = volatility
        else:
            volatility = self.volatility_cache.get(order.symbol, 0.01)

        # Estimate available liquidity from volume
        liquidity = volume if volume is not None else bar.get("volume", 10000)
        if liquidity <= 0:
            liquidity = 10000

        # Calculate volume ratio
        volume_ratio = min(order.quantity / liquidity, 1.0)

        # Calculate liquidity factor
        liquidity_multiplier = 1.0 + (volume_ratio * self.liquidity_factor)

        # Adjust impact based on volatility and liquidity
        impact_pct = self.base_impact_pct * volatility * 100 * liquidity_multiplier
        impact_pct = min(impact_pct, self.max_impact_pct)

        impact = base_price * impact_pct

        # Apply impact in the direction of the order
        if order.side.lower() == "buy":
            return impact
        else:
            return -impact


class DecayingImpactModel(MarketImpactModel):
    """Decaying market impact model.

    Models the fact that market impact decays over time.
    This is useful for simulating multiple orders executed over time.
    """

    def __init__(
        self,
        k: float = 0.1,
        exponent: float = 0.6,
        decay_rate: float = 0.5,
        volatility_window: int = 20,
        adv_window: int = 20,
    ):
        """Initialize a decaying market impact model.

        Args:
            k: Impact coefficient.
            exponent: Power law exponent.
            decay_rate: Rate at which impact decays over time.
            volatility_window: Window for volatility calculation.
            adv_window: Window for average daily volume calculation.
        """
        self.k = k
        self.exponent = exponent
        self.decay_rate = decay_rate
        self.volatility_window = volatility_window
        self.adv_window = adv_window
        self.volatility_cache: Dict[str, float] = {}
        self.adv_cache: Dict[str, float] = {}
        self.current_impact: Dict[str, float] = {}
        self.last_update: Dict[str, pd.Timestamp] = {}

    def calculate_impact(
        self,
        order: OrderEvent,
        bar: pd.Series,
        volume: Optional[float] = None,
        market_data: Optional[pd.DataFrame] = None,
    ) -> float:
        """Calculate decaying market impact.

        Args:
            order: Order event.
            bar: Current price bar.
            volume: Volume available for execution.
            market_data: Historical market data.

        Returns:
            Market impact amount in price units.
        """
        base_price = order.price or bar["close"]
        symbol = order.symbol
        timestamp = pd.Timestamp(order.timestamp)

        # Calculate or use cached volatility
        if market_data is not None and len(market_data) >= self.volatility_window:
            recent_data = market_data.iloc[-self.volatility_window :]
            returns = recent_data["close"].pct_change().dropna()
            volatility = returns.std()
            self.volatility_cache[symbol] = volatility
        else:
            volatility = self.volatility_cache.get(symbol, 0.01)

        # Calculate or use cached average daily volume (ADV)
        if (
            market_data is not None
            and "volume" in market_data.columns
            and len(market_data) >= self.adv_window
        ):
            recent_data = market_data.iloc[-self.adv_window :]
            adv = recent_data["volume"].mean()
            self.adv_cache[symbol] = adv
        else:
            adv = self.adv_cache.get(symbol, 10000)
            if volume is not None:
                adv = max(adv, volume)

        # Sanity check to avoid division by zero
        if adv <= 0:
            adv = 10000

        # Calculate new impact
        new_impact_pct = self.k * volatility * (order.quantity / adv) ** self.exponent
        new_impact = base_price * new_impact_pct

        # Get current decayed impact
        current_impact = 0.0
        if symbol in self.current_impact:
            last_update = self.last_update[symbol]
            time_diff = (
                timestamp - last_update
            ).total_seconds() / 60.0  # Convert to minutes
            decay_factor = math.exp(-self.decay_rate * time_diff)
            current_impact = self.current_impact[symbol] * decay_factor

        # Combine current decayed impact with new impact
        total_impact = current_impact + new_impact

        # Store the updated impact
        self.current_impact[symbol] = total_impact
        self.last_update[symbol] = timestamp

        # Apply impact in the direction of the order
        if order.side.lower() == "buy":
            return total_impact
        else:
            return -total_impact

    def update_impact_decay(self, symbol: str, timestamp: pd.Timestamp) -> None:
        """Update the impact decay for a symbol at a given timestamp.

        Args:
            symbol: Symbol to update.
            timestamp: Current timestamp.
        """
        if symbol in self.current_impact:
            last_update = self.last_update[symbol]
            time_diff = (
                timestamp - last_update
            ).total_seconds() / 60.0  # Convert to minutes
            decay_factor = math.exp(-self.decay_rate * time_diff)
            self.current_impact[symbol] *= decay_factor
            self.last_update[symbol] = timestamp

    def reset(self) -> None:
        """Reset the impact model state."""
        self.current_impact.clear()
        self.last_update.clear()


class MarketImpactHandler:
    """Handler for calculating and applying market impact."""

    def __init__(self, model: Optional[MarketImpactModel] = None):
        """Initialize the market impact handler.

        Args:
            model: Market impact model to use.
        """
        self.model = model or SquareRootModel()

    def calculate_impact(
        self,
        order: OrderEvent,
        bar: pd.Series,
        market_data: Optional[pd.DataFrame] = None,
    ) -> float:
        """Calculate market impact for an order.

        Args:
            order: Order event.
            bar: Current price bar.
            market_data: Historical market data.

        Returns:
            Market impact amount in price units.
        """
        volume = bar.get("volume", None)
        return self.model.calculate_impact(order, bar, volume, market_data)

    def apply_impact(
        self,
        price: float,
        impact: float,
        side: str,
    ) -> float:
        """Apply market impact to a price.

        Args:
            price: Base price.
            impact: Impact amount.
            side: Order side.

        Returns:
            Price with impact applied.
        """
        # Impact is already adjusted for side in calculate_impact
        return price + impact

    def reset(self) -> None:
        """Reset the handler state."""
        if hasattr(self.model, "reset"):
            self.model.reset()
