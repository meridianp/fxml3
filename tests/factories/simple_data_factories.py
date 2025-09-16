#!/usr/bin/env python3
"""
Comprehensive Test Data Factories for FXML4

This module provides factory classes for generating realistic test data
for all aspects of the forex trading system.
"""

import random
import string
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Union

import numpy as np

# Try to import Faker for realistic data generation
try:
    from faker import Faker

    fake = Faker()
    Faker.seed(42)  # For reproducible test data
    FAKER_AVAILABLE = True
except ImportError:
    FAKER_AVAILABLE = False

    # Create mock faker
    class MockFaker:
        def name(self):
            return "John Doe"

        def email(self):
            return "test@example.com"

        def address(self):
            return "123 Main St"

    fake = MockFaker()


class OrderSide(Enum):
    """Order side enumeration."""

    BUY = "BUY"
    SELL = "SELL"


class OrderType(Enum):
    """Order type enumeration."""

    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"


class OrderStatus(Enum):
    """Order status enumeration."""

    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    PARTIAL = "PARTIAL"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class SignalStrength(Enum):
    """Trading signal strength."""

    STRONG_BUY = "STRONG_BUY"
    BUY = "BUY"
    NEUTRAL = "NEUTRAL"
    SELL = "SELL"
    STRONG_SELL = "STRONG_SELL"


class MarketCondition(Enum):
    """Market condition types."""

    TRENDING = "TRENDING"
    RANGING = "RANGING"
    VOLATILE = "VOLATILE"
    CALM = "CALM"


@dataclass
class MarketData:
    """Market data structure."""

    symbol: str
    timestamp: datetime
    bid: float
    ask: float
    mid: float
    volume: int
    high: float
    low: float
    open: float
    close: float
    spread: float


@dataclass
class Order:
    """Trading order structure."""

    order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    price: Optional[float]
    stop_price: Optional[float]
    status: OrderStatus
    timestamp: datetime
    filled_quantity: float = 0.0
    average_fill_price: Optional[float] = None
    commission: float = 0.0
    slippage: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Position:
    """Trading position structure."""

    position_id: str
    symbol: str
    side: OrderSide
    quantity: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    realized_pnl: float
    stop_loss: Optional[float]
    take_profit: Optional[float]
    opened_at: datetime
    updated_at: datetime
    margin_used: float
    swap: float = 0.0


@dataclass
class Signal:
    """Trading signal structure."""

    signal_id: str
    symbol: str
    timestamp: datetime
    strength: SignalStrength
    confidence: float
    entry_price: float
    stop_loss: float
    take_profit: float
    risk_reward_ratio: float
    indicators: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Account:
    """Trading account structure."""

    account_id: str
    balance: float
    equity: float
    margin_used: float
    margin_available: float
    unrealized_pnl: float
    realized_pnl: float
    currency: str
    leverage: float
    created_at: datetime
    updated_at: datetime


class MarketDataFactory:
    """Factory for generating market data."""

    FOREX_PAIRS = [
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
    ]

    TYPICAL_SPREADS = {
        "EURUSD": 0.00015,
        "GBPUSD": 0.00020,
        "USDJPY": 0.015,
        "USDCHF": 0.00025,
        "AUDUSD": 0.00018,
    }

    @classmethod
    def create(cls, **kwargs) -> MarketData:
        """Create a single market data point."""
        symbol = kwargs.get("symbol", random.choice(cls.FOREX_PAIRS))
        timestamp = kwargs.get("timestamp", datetime.now())

        # Generate realistic price based on symbol
        if symbol.startswith("EUR"):
            base_price = random.uniform(1.0500, 1.2000)
        elif symbol.startswith("GBP"):
            base_price = random.uniform(1.2000, 1.4000)
        elif "JPY" in symbol:
            base_price = random.uniform(100.0, 150.0)
        else:
            base_price = random.uniform(0.6000, 1.5000)

        spread = cls.TYPICAL_SPREADS.get(symbol, 0.00020)
        mid = kwargs.get("mid", base_price)
        bid = kwargs.get("bid", mid - spread / 2)
        ask = kwargs.get("ask", mid + spread / 2)

        # Generate OHLC data
        volatility = random.uniform(0.0001, 0.0010)
        high = kwargs.get("high", mid + random.uniform(0, volatility))
        low = kwargs.get("low", mid - random.uniform(0, volatility))
        open_price = kwargs.get(
            "open", mid + random.uniform(-volatility / 2, volatility / 2)
        )
        close = kwargs.get("close", mid)

        return MarketData(
            symbol=symbol,
            timestamp=timestamp,
            bid=bid,
            ask=ask,
            mid=mid,
            volume=kwargs.get("volume", random.randint(1000, 1000000)),
            high=high,
            low=low,
            open=open_price,
            close=close,
            spread=ask - bid,
        )

    @classmethod
    def create_series(
        cls, symbol: str, periods: int = 100, timeframe: str = "1h", **kwargs
    ) -> List[MarketData]:
        """Create a time series of market data."""
        data_points = []
        start_time = kwargs.get("start_time", datetime.now() - timedelta(hours=periods))

        # Determine time delta based on timeframe
        if timeframe == "1m":
            delta = timedelta(minutes=1)
        elif timeframe == "5m":
            delta = timedelta(minutes=5)
        elif timeframe == "15m":
            delta = timedelta(minutes=15)
        elif timeframe == "1h":
            delta = timedelta(hours=1)
        elif timeframe == "4h":
            delta = timedelta(hours=4)
        elif timeframe == "1d":
            delta = timedelta(days=1)
        else:
            delta = timedelta(hours=1)

        # Generate random walk price series
        base_price = 1.1000 if symbol == "EURUSD" else 1.2500
        prices = cls._generate_random_walk(base_price, periods, volatility=0.0005)

        for i in range(periods):
            timestamp = start_time + (delta * i)
            mid_price = prices[i]

            data_points.append(
                cls.create(symbol=symbol, timestamp=timestamp, mid=mid_price, **kwargs)
            )

        return data_points

    @staticmethod
    def _generate_random_walk(
        start_price: float, periods: int, volatility: float = 0.001
    ) -> List[float]:
        """Generate realistic price series using random walk."""
        prices = [start_price]
        for _ in range(periods - 1):
            change = np.random.normal(0, volatility)
            new_price = prices[-1] * (1 + change)
            prices.append(new_price)
        return prices

    @classmethod
    def create_trending_market(
        cls, symbol: str, periods: int = 100, trend: str = "up", **kwargs
    ) -> List[MarketData]:
        """Create trending market data."""
        data_points = []
        start_time = kwargs.get("start_time", datetime.now() - timedelta(hours=periods))
        base_price = 1.1000

        for i in range(periods):
            timestamp = start_time + timedelta(hours=i)

            # Add trend component
            if trend == "up":
                trend_component = i * 0.0001
            else:
                trend_component = -i * 0.0001

            # Add noise
            noise = random.uniform(-0.0005, 0.0005)
            mid_price = base_price + trend_component + noise

            data_points.append(
                cls.create(symbol=symbol, timestamp=timestamp, mid=mid_price, **kwargs)
            )

        return data_points


class OrderFactory:
    """Factory for generating trading orders."""

    @classmethod
    def create_market_order(cls, **kwargs) -> Order:
        """Create a market order."""
        return cls._create_order(OrderType.MARKET, **kwargs)

    @classmethod
    def create_limit_order(cls, **kwargs) -> Order:
        """Create a limit order."""
        return cls._create_order(OrderType.LIMIT, **kwargs)

    @classmethod
    def create_stop_order(cls, **kwargs) -> Order:
        """Create a stop order."""
        return cls._create_order(OrderType.STOP, **kwargs)

    @classmethod
    def _create_order(cls, order_type: OrderType, **kwargs) -> Order:
        """Create an order with specified type."""
        order_id = kwargs.get("order_id", cls._generate_order_id())
        symbol = kwargs.get("symbol", random.choice(MarketDataFactory.FOREX_PAIRS))
        side = kwargs.get("side", random.choice(list(OrderSide)))
        quantity = kwargs.get("quantity", random.uniform(10000, 100000))
        status = kwargs.get("status", OrderStatus.PENDING)
        timestamp = kwargs.get("timestamp", datetime.now())

        # Set prices based on order type
        price = None
        stop_price = None

        if order_type in [OrderType.LIMIT, OrderType.STOP_LIMIT]:
            price = kwargs.get("price", 1.1000)

        if order_type in [OrderType.STOP, OrderType.STOP_LIMIT]:
            stop_price = kwargs.get("stop_price", 1.0950)

        return Order(
            order_id=order_id,
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            stop_price=stop_price,
            status=status,
            timestamp=timestamp,
            filled_quantity=kwargs.get("filled_quantity", 0.0),
            average_fill_price=kwargs.get("average_fill_price"),
            commission=kwargs.get("commission", quantity * 0.00001),
            slippage=kwargs.get("slippage", 0.0),
            metadata=kwargs.get("metadata", {}),
        )

    @classmethod
    def create_filled_order(cls, **kwargs) -> Order:
        """Create a filled order."""
        order = cls.create_market_order(**kwargs)
        order.status = OrderStatus.FILLED
        order.filled_quantity = order.quantity
        order.average_fill_price = kwargs.get("fill_price", 1.1000)
        return order

    @classmethod
    def create_batch(cls, count: int = 10, **kwargs) -> List[Order]:
        """Create multiple orders."""
        return [cls.create_market_order(**kwargs) for _ in range(count)]

    @staticmethod
    def _generate_order_id() -> str:
        """Generate unique order ID."""
        return f"ORD-{datetime.now().strftime('%Y%m%d%H%M%S')}-{''.join(random.choices(string.ascii_uppercase + string.digits, k=6))}"


class PositionFactory:
    """Factory for generating trading positions."""

    @classmethod
    def create(cls, **kwargs) -> Position:
        """Create a trading position."""
        position_id = kwargs.get("position_id", cls._generate_position_id())
        symbol = kwargs.get("symbol", random.choice(MarketDataFactory.FOREX_PAIRS))
        side = kwargs.get("side", random.choice(list(OrderSide)))
        quantity = kwargs.get("quantity", random.uniform(10000, 100000))
        entry_price = kwargs.get("entry_price", 1.1000)
        current_price = kwargs.get(
            "current_price", entry_price + random.uniform(-0.0050, 0.0050)
        )

        # Calculate P&L
        if side == OrderSide.BUY:
            unrealized_pnl = (current_price - entry_price) * quantity
        else:
            unrealized_pnl = (entry_price - current_price) * quantity

        # Set stops
        stop_loss = kwargs.get("stop_loss")
        take_profit = kwargs.get("take_profit")

        if not stop_loss and kwargs.get("with_stops", True):
            if side == OrderSide.BUY:
                stop_loss = entry_price - 0.0050
            else:
                stop_loss = entry_price + 0.0050

        if not take_profit and kwargs.get("with_stops", True):
            if side == OrderSide.BUY:
                take_profit = entry_price + 0.0100
            else:
                take_profit = entry_price - 0.0100

        return Position(
            position_id=position_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            entry_price=entry_price,
            current_price=current_price,
            unrealized_pnl=unrealized_pnl,
            realized_pnl=kwargs.get("realized_pnl", 0.0),
            stop_loss=stop_loss,
            take_profit=take_profit,
            opened_at=kwargs.get(
                "opened_at", datetime.now() - timedelta(hours=random.randint(1, 48))
            ),
            updated_at=kwargs.get("updated_at", datetime.now()),
            margin_used=kwargs.get("margin_used", quantity / 100),
            swap=kwargs.get("swap", random.uniform(-5, 5)),
        )

    @classmethod
    def create_winning_position(cls, **kwargs) -> Position:
        """Create a winning position."""
        side = kwargs.get("side", OrderSide.BUY)
        entry_price = kwargs.get("entry_price", 1.1000)

        if side == OrderSide.BUY:
            current_price = entry_price + random.uniform(0.0020, 0.0100)
        else:
            current_price = entry_price - random.uniform(0.0020, 0.0100)

        return cls.create(
            side=side, entry_price=entry_price, current_price=current_price, **kwargs
        )

    @classmethod
    def create_losing_position(cls, **kwargs) -> Position:
        """Create a losing position."""
        side = kwargs.get("side", OrderSide.BUY)
        entry_price = kwargs.get("entry_price", 1.1000)

        if side == OrderSide.BUY:
            current_price = entry_price - random.uniform(0.0020, 0.0100)
        else:
            current_price = entry_price + random.uniform(0.0020, 0.0100)

        return cls.create(
            side=side, entry_price=entry_price, current_price=current_price, **kwargs
        )

    @classmethod
    def create_portfolio(cls, count: int = 5, **kwargs) -> List[Position]:
        """Create a portfolio of positions."""
        positions = []
        for _ in range(count):
            # Mix of winning and losing positions
            if random.random() > 0.5:
                positions.append(cls.create_winning_position(**kwargs))
            else:
                positions.append(cls.create_losing_position(**kwargs))
        return positions

    @staticmethod
    def _generate_position_id() -> str:
        """Generate unique position ID."""
        return f"POS-{datetime.now().strftime('%Y%m%d%H%M%S')}-{''.join(random.choices(string.ascii_uppercase + string.digits, k=6))}"


class SignalFactory:
    """Factory for generating trading signals."""

    @classmethod
    def create(cls, **kwargs) -> Signal:
        """Create a trading signal."""
        signal_id = kwargs.get("signal_id", cls._generate_signal_id())
        symbol = kwargs.get("symbol", random.choice(MarketDataFactory.FOREX_PAIRS))
        timestamp = kwargs.get("timestamp", datetime.now())
        strength = kwargs.get("strength", random.choice(list(SignalStrength)))
        confidence = kwargs.get("confidence", random.uniform(0.5, 1.0))

        # Generate entry and exit prices
        entry_price = kwargs.get("entry_price", 1.1000)

        if strength in [SignalStrength.BUY, SignalStrength.STRONG_BUY]:
            stop_loss = kwargs.get("stop_loss", entry_price - 0.0050)
            take_profit = kwargs.get("take_profit", entry_price + 0.0100)
        else:
            stop_loss = kwargs.get("stop_loss", entry_price + 0.0050)
            take_profit = kwargs.get("take_profit", entry_price - 0.0100)

        # Calculate risk-reward ratio
        risk = abs(entry_price - stop_loss)
        reward = abs(take_profit - entry_price)
        risk_reward_ratio = reward / risk if risk > 0 else 0

        # Generate indicator values
        indicators = kwargs.get(
            "indicators",
            {
                "rsi": random.uniform(20, 80),
                "macd": random.uniform(-0.001, 0.001),
                "ema_50": entry_price + random.uniform(-0.0020, 0.0020),
                "ema_200": entry_price + random.uniform(-0.0050, 0.0050),
                "atr": random.uniform(0.0010, 0.0050),
                "volume": random.randint(10000, 1000000),
            },
        )

        return Signal(
            signal_id=signal_id,
            symbol=symbol,
            timestamp=timestamp,
            strength=strength,
            confidence=confidence,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            risk_reward_ratio=risk_reward_ratio,
            indicators=indicators,
            metadata=kwargs.get("metadata", {}),
        )

    @classmethod
    def create_buy_signal(cls, **kwargs) -> Signal:
        """Create a buy signal."""
        strength = random.choice([SignalStrength.BUY, SignalStrength.STRONG_BUY])
        return cls.create(strength=strength, **kwargs)

    @classmethod
    def create_sell_signal(cls, **kwargs) -> Signal:
        """Create a sell signal."""
        strength = random.choice([SignalStrength.SELL, SignalStrength.STRONG_SELL])
        return cls.create(strength=strength, **kwargs)

    @classmethod
    def create_signal_series(
        cls, symbol: str, periods: int = 10, **kwargs
    ) -> List[Signal]:
        """Create a series of signals over time."""
        signals = []
        start_time = kwargs.get("start_time", datetime.now() - timedelta(hours=periods))

        for i in range(periods):
            timestamp = start_time + timedelta(hours=i)

            # Alternate between buy and sell signals with some neutral
            if i % 3 == 0:
                signal = cls.create_buy_signal(
                    symbol=symbol, timestamp=timestamp, **kwargs
                )
            elif i % 3 == 1:
                signal = cls.create_sell_signal(
                    symbol=symbol, timestamp=timestamp, **kwargs
                )
            else:
                signal = cls.create(
                    symbol=symbol,
                    timestamp=timestamp,
                    strength=SignalStrength.NEUTRAL,
                    **kwargs,
                )

            signals.append(signal)

        return signals

    @staticmethod
    def _generate_signal_id() -> str:
        """Generate unique signal ID."""
        return f"SIG-{datetime.now().strftime('%Y%m%d%H%M%S')}-{''.join(random.choices(string.ascii_uppercase + string.digits, k=6))}"


class AccountFactory:
    """Factory for generating trading accounts."""

    @classmethod
    def create(cls, **kwargs) -> Account:
        """Create a trading account."""
        account_id = kwargs.get("account_id", cls._generate_account_id())
        balance = kwargs.get("balance", random.uniform(10000, 100000))
        margin_used = kwargs.get("margin_used", balance * random.uniform(0, 0.3))
        unrealized_pnl = kwargs.get("unrealized_pnl", random.uniform(-1000, 1000))
        realized_pnl = kwargs.get("realized_pnl", random.uniform(-500, 500))

        equity = balance + unrealized_pnl
        margin_available = balance - margin_used

        return Account(
            account_id=account_id,
            balance=balance,
            equity=equity,
            margin_used=margin_used,
            margin_available=margin_available,
            unrealized_pnl=unrealized_pnl,
            realized_pnl=realized_pnl,
            currency=kwargs.get("currency", "USD"),
            leverage=kwargs.get("leverage", 100.0),
            created_at=kwargs.get(
                "created_at", datetime.now() - timedelta(days=random.randint(30, 365))
            ),
            updated_at=kwargs.get("updated_at", datetime.now()),
        )

    @classmethod
    def create_funded_account(cls, balance: float = 50000, **kwargs) -> Account:
        """Create a well-funded account."""
        return cls.create(
            balance=balance, margin_used=0, unrealized_pnl=0, realized_pnl=0, **kwargs
        )

    @classmethod
    def create_margin_call_account(cls, **kwargs) -> Account:
        """Create an account near margin call."""
        balance = kwargs.get("balance", 10000)
        margin_used = balance * 0.95  # 95% margin used

        return cls.create(
            balance=balance,
            margin_used=margin_used,
            unrealized_pnl=-balance * 0.2,  # 20% drawdown
            **kwargs,
        )

    @staticmethod
    def _generate_account_id() -> str:
        """Generate unique account ID."""
        return f"ACC-{datetime.now().strftime('%Y%m%d')}-{''.join(random.choices(string.ascii_uppercase + string.digits, k=8))}"


class TestDataGenerator:
    """High-level test data generator combining all factories."""

    def __init__(self):
        self.market_factory = MarketDataFactory()
        self.order_factory = OrderFactory()
        self.position_factory = PositionFactory()
        self.signal_factory = SignalFactory()
        self.account_factory = AccountFactory()

    def generate_complete_trading_scenario(self) -> Dict[str, Any]:
        """Generate a complete trading scenario with all components."""
        symbol = "EURUSD"

        # Generate market data
        market_data = self.market_factory.create_series(symbol, periods=100)

        # Generate account
        account = self.account_factory.create_funded_account(balance=50000)

        # Generate signals based on market data
        signals = self.signal_factory.create_signal_series(symbol, periods=10)

        # Generate orders based on signals
        orders = []
        for signal in signals[:5]:  # Create orders for first 5 signals
            if signal.strength in [SignalStrength.BUY, SignalStrength.STRONG_BUY]:
                order = self.order_factory.create_market_order(
                    symbol=symbol, side=OrderSide.BUY, quantity=10000
                )
            elif signal.strength in [SignalStrength.SELL, SignalStrength.STRONG_SELL]:
                order = self.order_factory.create_market_order(
                    symbol=symbol, side=OrderSide.SELL, quantity=10000
                )
            else:
                continue
            orders.append(order)

        # Generate positions from filled orders
        positions = []
        for order in orders[:3]:  # Convert first 3 orders to positions
            position = self.position_factory.create(
                symbol=order.symbol, side=order.side, quantity=order.quantity
            )
            positions.append(position)

        return {
            "account": account,
            "market_data": market_data,
            "signals": signals,
            "orders": orders,
            "positions": positions,
        }

    def generate_backtest_data(
        self, symbols: List[str], days: int = 30
    ) -> Dict[str, Any]:
        """Generate data for backtesting."""
        data = {"market_data": {}, "signals": {}, "orders": []}

        for symbol in symbols:
            # Generate market data
            periods = days * 24  # Hourly data
            data["market_data"][symbol] = self.market_factory.create_series(
                symbol, periods=periods, timeframe="1h"
            )

            # Generate signals
            data["signals"][symbol] = self.signal_factory.create_signal_series(
                symbol, periods=days
            )

            # Generate some historical orders
            for _ in range(10):
                data["orders"].append(
                    self.order_factory.create_filled_order(symbol=symbol)
                )

        return data

    def generate_stress_test_data(self) -> Dict[str, Any]:
        """Generate data for stress testing."""
        return {
            "high_frequency_orders": self.order_factory.create_batch(count=1000),
            "volatile_market": self.market_factory.create_series(
                "EURUSD", periods=1000, volatility=0.005  # High volatility
            ),
            "large_positions": [
                self.position_factory.create(quantity=1000000)  # Large position
                for _ in range(10)
            ],
            "margin_accounts": [
                self.account_factory.create_margin_call_account() for _ in range(5)
            ],
        }


# Convenience functions for quick data generation
def create_test_order(**kwargs) -> Order:
    """Quick function to create a test order."""
    return OrderFactory.create_market_order(**kwargs)


def create_test_position(**kwargs) -> Position:
    """Quick function to create a test position."""
    return PositionFactory.create(**kwargs)


def create_test_signal(**kwargs) -> Signal:
    """Quick function to create a test signal."""
    return SignalFactory.create(**kwargs)


def create_test_market_data(**kwargs) -> MarketData:
    """Quick function to create test market data."""
    return MarketDataFactory.create(**kwargs)


def create_test_account(**kwargs) -> Account:
    """Quick function to create a test account."""
    return AccountFactory.create(**kwargs)


# Example usage and testing
if __name__ == "__main__":
    # Test market data generation
    print("Testing Market Data Factory...")
    market_data = MarketDataFactory.create(symbol="EURUSD")
    print(f"  Created: {market_data.symbol} @ {market_data.mid:.5f}")

    series = MarketDataFactory.create_series("GBPUSD", periods=5)
    print(f"  Created series with {len(series)} data points")

    # Test order generation
    print("\nTesting Order Factory...")
    order = OrderFactory.create_market_order(symbol="EURUSD", side=OrderSide.BUY)
    print(f"  Created: {order.order_id} - {order.side.value} {order.quantity}")

    # Test position generation
    print("\nTesting Position Factory...")
    position = PositionFactory.create_winning_position()
    print(f"  Created: {position.position_id} - P&L: ${position.unrealized_pnl:.2f}")

    # Test signal generation
    print("\nTesting Signal Factory...")
    signal = SignalFactory.create_buy_signal()
    print(
        f"  Created: {signal.signal_id} - {signal.strength.value} @ {signal.confidence:.2%}"
    )

    # Test account generation
    print("\nTesting Account Factory...")
    account = AccountFactory.create_funded_account()
    print(f"  Created: {account.account_id} - Balance: ${account.balance:.2f}")

    # Test complete scenario
    print("\nTesting Complete Trading Scenario...")
    generator = TestDataGenerator()
    scenario = generator.generate_complete_trading_scenario()
    print(f"  Generated scenario with:")
    print(f"    - {len(scenario['market_data'])} market data points")
    print(f"    - {len(scenario['signals'])} signals")
    print(f"    - {len(scenario['orders'])} orders")
    print(f"    - {len(scenario['positions'])} positions")
    print(f"    - Account balance: ${scenario['account'].balance:.2f}")

    print("\n✅ All test data factories working correctly!")
