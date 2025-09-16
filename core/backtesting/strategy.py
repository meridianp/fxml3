"""
Base strategy classes for backtesting.
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from queue import Queue
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from fxml4.backtesting.events import EventType, MarketEvent, SignalEvent

# Set up logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class Signal:
    """Trading signal."""

    def __init__(
        self,
        symbol: str,
        signal_type: str,
        strength: float = 1.0,
        price: Optional[float] = None,
        quantity: Optional[float] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.symbol = symbol
        self.signal_type = signal_type  # 'BUY', 'SELL', 'EXIT', 'HOLD'
        self.strength = max(0.0, min(1.0, strength))  # Clamp to [0, 1]
        self.price = price
        self.quantity = quantity
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.metadata = metadata or {}
        self.timestamp = datetime.now()


class Strategy(ABC):
    """Abstract base strategy class."""

    def __init__(self, name: str = "BaseStrategy"):
        self.name = name
        self.data_handler = None
        self.portfolio = None
        self.events_queue = None
        self.params = {}
        self.indicators = {}
        self.signals_history = []

    def set_components(
        self, data_handler: Any, portfolio: Any, events_queue: Queue
    ) -> None:
        """Set strategy components."""
        self.data_handler = data_handler
        self.portfolio = portfolio
        self.events_queue = events_queue
        logger.info("Strategy %s components initialized", self.name)

    def set_params(self, **params) -> None:
        """Set strategy parameters."""
        self.params.update(params)
        logger.info("Strategy %s parameters updated: %s", self.name, params)

    @abstractmethod
    def calculate_signals(self, event: MarketEvent) -> None:
        """Calculate trading signals from market event."""
        pass

    def create_signal(
        self, symbol: str, signal_type: str, strength: float = 1.0, **kwargs
    ) -> SignalEvent:
        """Create a signal event."""
        # Get current price if not provided
        price = kwargs.get("price")
        if price is None and self.data_handler:
            latest_bar = self.data_handler.get_latest_bar(symbol)
            if latest_bar is not None:
                price = latest_bar.get("close", 0)

        # Create signal
        signal = Signal(
            symbol=symbol,
            signal_type=signal_type,
            strength=strength,
            price=price,
            quantity=kwargs.get("quantity"),
            stop_loss=kwargs.get("stop_loss"),
            take_profit=kwargs.get("take_profit"),
            metadata=kwargs.get("metadata", {}),
        )

        # Store in history
        self.signals_history.append(signal)

        # Create event
        event = SignalEvent(
            type=EventType.SIGNAL,
            timestamp=datetime.now(),
            symbol=symbol,
            signal_type=signal_type,
            strength=strength,
            price=price or 0,
            quantity=kwargs.get("quantity"),
            metadata=signal.metadata,
        )

        return event

    def send_signal(self, signal_event: SignalEvent) -> None:
        """Send signal to events queue."""
        if self.events_queue is not None:
            self.events_queue.put(signal_event)
            logger.debug(
                "Signal sent - %s %s (strength: %.2f)",
                signal_event.signal_type,
                signal_event.symbol,
                signal_event.strength,
            )

    def get_position(self, symbol: str) -> Optional[Any]:
        """Get current position for symbol."""
        if self.portfolio:
            positions = self.portfolio.get_current_positions()
            return positions.get(symbol)
        return None

    def has_position(self, symbol: str) -> bool:
        """Check if we have a position in symbol."""
        return self.get_position(symbol) is not None

    # For vectorized backtesting
    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """Generate signals for vectorized backtesting."""
        # Default implementation - should be overridden
        signals = pd.DataFrame(index=data.index)
        signals["signal"] = 0
        return signals


class BuyAndHoldStrategy(Strategy):
    """Simple buy and hold strategy."""

    def __init__(self):
        super().__init__("BuyAndHold")
        self.bought = False

    def calculate_signals(self, event: MarketEvent) -> None:
        """Buy once and hold."""
        if not self.bought:
            signal = self.create_signal(
                symbol=event.symbol, signal_type="BUY", strength=1.0
            )
            self.send_signal(signal)
            self.bought = True


class MovingAverageCrossStrategy(Strategy):
    """Moving average crossover strategy."""

    def __init__(
        self, short_window: int = 20, long_window: int = 50, use_ema: bool = False
    ):
        super().__init__("MACross")
        self.short_window = short_window
        self.long_window = long_window
        self.use_ema = use_ema
        self.prices = {}
        self.short_ma = {}
        self.long_ma = {}

    def calculate_signals(self, event: MarketEvent) -> None:
        """Calculate MA crossover signals."""
        symbol = event.symbol
        price = event.data.get("close", 0)

        # Update price history
        if symbol not in self.prices:
            self.prices[symbol] = []
        self.prices[symbol].append(price)

        # Keep only required history
        max_window = max(self.short_window, self.long_window)
        if len(self.prices[symbol]) > max_window * 2:
            self.prices[symbol] = self.prices[symbol][-max_window * 2 :]

        # Need enough data
        if len(self.prices[symbol]) < self.long_window:
            return

        # Calculate moving averages
        prices_array = np.array(self.prices[symbol])

        if self.use_ema:
            short_ma = self._calculate_ema(prices_array, self.short_window)
            long_ma = self._calculate_ema(prices_array, self.long_window)
        else:
            short_ma = np.mean(prices_array[-self.short_window :])
            long_ma = np.mean(prices_array[-self.long_window :])

        # Store current MA values
        prev_short = self.short_ma.get(symbol)
        prev_long = self.long_ma.get(symbol)
        self.short_ma[symbol] = short_ma
        self.long_ma[symbol] = long_ma

        # Check for crossover
        if prev_short is not None and prev_long is not None:
            # Golden cross - short MA crosses above long MA
            if prev_short <= prev_long and short_ma > long_ma:
                if not self.has_position(symbol):
                    signal = self.create_signal(
                        symbol=symbol,
                        signal_type="BUY",
                        strength=0.8,
                        metadata={
                            "short_ma": short_ma,
                            "long_ma": long_ma,
                            "pattern": "golden_cross",
                        },
                    )
                    self.send_signal(signal)

            # Death cross - short MA crosses below long MA
            elif prev_short >= prev_long and short_ma < long_ma:
                if self.has_position(symbol):
                    signal = self.create_signal(
                        symbol=symbol,
                        signal_type="SELL",
                        strength=0.8,
                        metadata={
                            "short_ma": short_ma,
                            "long_ma": long_ma,
                            "pattern": "death_cross",
                        },
                    )
                    self.send_signal(signal)

    def _calculate_ema(self, prices: np.ndarray, period: int) -> float:
        """Calculate exponential moving average."""
        if len(prices) < period:
            return np.mean(prices)

        alpha = 2 / (period + 1)
        ema = prices[-period]

        for price in prices[-period + 1 :]:
            ema = (price * alpha) + (ema * (1 - alpha))

        return ema

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """Generate signals for vectorized backtesting."""
        signals = pd.DataFrame(index=data.index)

        # Calculate moving averages
        if self.use_ema:
            short_ma = data["close"].ewm(span=self.short_window, adjust=False).mean()
            long_ma = data["close"].ewm(span=self.long_window, adjust=False).mean()
        else:
            short_ma = data["close"].rolling(window=self.short_window).mean()
            long_ma = data["close"].rolling(window=self.long_window).mean()

        # Generate signals
        signals["signal"] = 0
        signals.loc[short_ma > long_ma, "signal"] = 1
        signals.loc[short_ma < long_ma, "signal"] = -1

        # Only signal on crossovers
        signals["positions"] = signals["signal"].diff()

        return signals
