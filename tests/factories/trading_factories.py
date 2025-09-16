"""
Trading Entity Factory Definitions
=================================

Factory Boy factories for creating trading-related entities including currency pairs,
trades, positions, orders, and executions with realistic trading data.
"""

import random
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Dict

import factory
import factory.fuzzy
from faker import Faker

fake = Faker()


class CurrencyPairFactory(factory.Factory):
    """
    Factory for creating currency pairs with proper forex market constraints.

    Generates currency pairs with realistic spreads, pip values, trading sessions,
    and market characteristics suitable for forex trading.
    """

    class Meta:
        model = dict

    # Basic pair information
    symbol = factory.fuzzy.FuzzyChoice(
        [
            "EURUSD",
            "GBPUSD",
            "USDJPY",
            "USDCHF",
            "AUDUSD",
            "USDCAD",
            "NZDUSD",  # Majors
            "EURGBP",
            "EURJPY",
            "EURCHF",
            "EURAUD",
            "EURCAD",
            "EURNZD",  # EUR crosses
            "GBPJPY",
            "GBPCHF",
            "GBPAUD",
            "GBPCAD",
            "GBPNZD",  # GBP crosses
            "AUDJPY",
            "AUDCHF",
            "AUDCAD",
            "AUDNZD",  # AUD crosses
            "CADJPY",
            "CADCHF",
            "CHFJPY",
            "NZDJPY",
            "NZDCHF",  # Other crosses
        ]
    )

    base_currency = factory.LazyAttribute(lambda obj: obj.symbol[:3])
    quote_currency = factory.LazyAttribute(lambda obj: obj.symbol[3:])

    # Market characteristics
    pip_size = factory.LazyAttribute(
        lambda obj: Decimal("0.0001") if "JPY" not in obj.symbol else Decimal("0.01")
    )
    tick_size = factory.LazyAttribute(lambda obj: obj.pip_size)
    min_size = factory.fuzzy.FuzzyDecimal(0.01, 0.1, 2)
    max_size = factory.fuzzy.FuzzyDecimal(100.0, 1000.0, 2)
    lot_size = Decimal("100000")  # Standard lot size

    # Spread and pricing
    spread = factory.LazyAttribute(
        lambda obj: {
            # Major pairs - tighter spreads
            "EURUSD": fake.pydecimal(1, 1, positive=True) + Decimal("1"),
            "GBPUSD": fake.pydecimal(1, 1, positive=True) + Decimal("1.5"),
            "USDJPY": fake.pydecimal(1, 1, positive=True) + Decimal("1"),
            "USDCHF": fake.pydecimal(1, 1, positive=True) + Decimal("1.5"),
            "AUDUSD": fake.pydecimal(1, 1, positive=True) + Decimal("1.5"),
            "USDCAD": fake.pydecimal(1, 1, positive=True) + Decimal("1.5"),
            "NZDUSD": fake.pydecimal(1, 1, positive=True) + Decimal("2"),
        }.get(
            obj.symbol, fake.pydecimal(1, 1, positive=True) + Decimal("2.5")
        )  # Crosses - wider spreads
    )

    # Current pricing
    bid_price = factory.LazyAttribute(
        lambda obj: {
            "EURUSD": Decimal(str(fake.random.uniform(1.0500, 1.1200))),
            "GBPUSD": Decimal(str(fake.random.uniform(1.2000, 1.3500))),
            "USDJPY": Decimal(str(fake.random.uniform(140.00, 155.00))),
            "USDCHF": Decimal(str(fake.random.uniform(0.8500, 0.9200))),
            "AUDUSD": Decimal(str(fake.random.uniform(0.6500, 0.7200))),
            "USDCAD": Decimal(str(fake.random.uniform(1.3000, 1.3800))),
            "NZDUSD": Decimal(str(fake.random.uniform(0.5800, 0.6400))),
        }.get(obj.symbol, Decimal(str(fake.random.uniform(0.5000, 2.0000))))
    )
    ask_price = factory.LazyAttribute(
        lambda obj: obj.bid_price + (obj.spread * obj.pip_size)
    )
    mid_price = factory.LazyAttribute(lambda obj: (obj.bid_price + obj.ask_price) / 2)

    # Trading session information
    trading_sessions = factory.LazyFunction(
        lambda: ["Sydney", "Tokyo", "London", "New York"]
    )
    primary_session = factory.LazyAttribute(
        lambda obj: {
            "EURUSD": "London",
            "GBPUSD": "London",
            "USDJPY": "Tokyo",
            "AUDUSD": "Sydney",
            "USDCAD": "New York",
        }.get(obj.symbol, "London")
    )

    # Market status and metadata
    is_active = True
    last_updated = factory.LazyFunction(lambda: datetime.utcnow())
    daily_volume = factory.fuzzy.FuzzyInteger(
        1000000, 100000000
    )  # Daily volume in base currency

    # Volatility and risk metrics
    daily_volatility = factory.LazyAttribute(
        lambda obj: {
            # Major pairs - lower volatility
            "EURUSD": Decimal(str(fake.random.uniform(0.008, 0.015))),
            "GBPUSD": Decimal(str(fake.random.uniform(0.010, 0.020))),
            "USDJPY": Decimal(str(fake.random.uniform(0.008, 0.015))),
            "AUDUSD": Decimal(str(fake.random.uniform(0.012, 0.025))),
        }.get(
            obj.symbol, Decimal(str(fake.random.uniform(0.015, 0.035)))
        )  # Crosses - higher volatility
    )

    class Params:
        # Traits for different pair types
        major_pair = factory.Trait(
            symbol=factory.fuzzy.FuzzyChoice(["EURUSD", "GBPUSD", "USDJPY", "USDCHF"]),
            spread=factory.fuzzy.FuzzyDecimal(1.0, 2.0, 1),
            daily_volatility=factory.fuzzy.FuzzyDecimal(0.008, 0.015, 3),
        )

        cross_pair = factory.Trait(
            symbol=factory.fuzzy.FuzzyChoice(["EURGBP", "EURJPY", "GBPJPY", "AUDJPY"]),
            spread=factory.fuzzy.FuzzyDecimal(2.0, 4.0, 1),
            daily_volatility=factory.fuzzy.FuzzyDecimal(0.015, 0.030, 3),
        )

        exotic_pair = factory.Trait(
            symbol=factory.fuzzy.FuzzyChoice(["USDTRY", "USDZAR", "USDMXN", "USDRUB"]),
            spread=factory.fuzzy.FuzzyDecimal(10.0, 50.0, 1),
            daily_volatility=factory.fuzzy.FuzzyDecimal(0.025, 0.100, 3),
        )


class OrderFactory(factory.Factory):
    """
    Factory for creating trading orders with realistic order management data.
    """

    class Meta:
        model = dict

    # Order identification
    order_id = factory.Sequence(lambda n: f"ORD{n:010d}")
    client_order_id = factory.LazyAttribute(lambda obj: f"CLT-{obj.order_id}")
    account_id = factory.Sequence(lambda n: f"ACC{n:08d}")

    # Order details
    symbol = factory.SubFactory(CurrencyPairFactory)
    side = factory.fuzzy.FuzzyChoice(["BUY", "SELL"])
    order_type = factory.fuzzy.FuzzyChoice(["MARKET", "LIMIT", "STOP", "STOP_LIMIT"])
    quantity = factory.fuzzy.FuzzyDecimal(0.01, 10.0, 2)

    # Pricing
    price = factory.LazyAttribute(
        lambda obj: (
            None
            if obj.order_type == "MARKET"
            else Decimal(str(fake.random.uniform(1.0000, 1.5000)))
        )
    )
    stop_price = factory.LazyAttribute(
        lambda obj: (
            Decimal(str(fake.random.uniform(1.0000, 1.5000)))
            if "STOP" in obj.order_type
            else None
        )
    )

    # Order status and execution
    status = factory.fuzzy.FuzzyChoice(
        ["PENDING", "PARTIAL_FILLED", "FILLED", "CANCELLED", "REJECTED", "EXPIRED"]
    )
    filled_quantity = factory.LazyAttribute(
        lambda obj: (
            obj.quantity
            if obj.status == "FILLED"
            else (
                obj.quantity * Decimal(str(fake.random.uniform(0.1, 0.9)))
                if obj.status == "PARTIAL_FILLED"
                else Decimal("0")
            )
        )
    )
    remaining_quantity = factory.LazyAttribute(
        lambda obj: obj.quantity - obj.filled_quantity
    )

    # Timestamps
    created_at = factory.LazyFunction(
        lambda: fake.date_time_between(start_date="-30d", end_date="now")
    )
    updated_at = factory.LazyAttribute(
        lambda obj: obj.created_at + timedelta(minutes=fake.random_int(1, 60))
    )
    filled_at = factory.LazyAttribute(
        lambda obj: (
            obj.updated_at if obj.status in ["FILLED", "PARTIAL_FILLED"] else None
        )
    )

    # Order parameters
    time_in_force = factory.fuzzy.FuzzyChoice(
        ["GTC", "DAY", "IOC", "FOK"]
    )  # Good Till Canceled, Day, Immediate or Cancel, Fill or Kill
    reduce_only = False
    post_only = False

    # Risk management
    stop_loss = factory.LazyAttribute(
        lambda obj: (
            obj.price - (Decimal("0.0050") if obj.side == "BUY" else -Decimal("0.0050"))
            if obj.price
            else None
        )
    )
    take_profit = factory.LazyAttribute(
        lambda obj: (
            obj.price + (Decimal("0.0100") if obj.side == "BUY" else -Decimal("0.0100"))
            if obj.price
            else None
        )
    )

    class Params:
        # Traits for different order scenarios
        market_order = factory.Trait(
            order_type="MARKET",
            price=None,
            stop_price=None,
            status="FILLED",
            time_in_force="IOC",
        )

        pending_limit = factory.Trait(
            order_type="LIMIT",
            status="PENDING",
            filled_quantity=Decimal("0"),
            remaining_quantity=factory.LazyAttribute(lambda obj: obj.quantity),
        )

        cancelled_order = factory.Trait(
            status="CANCELLED",
            filled_quantity=Decimal("0"),
            remaining_quantity=factory.LazyAttribute(lambda obj: obj.quantity),
        )


class ExecutionFactory(factory.Factory):
    """
    Factory for creating trade executions with realistic fill data.
    """

    class Meta:
        model = dict

    # Execution identification
    execution_id = factory.Sequence(lambda n: f"EXE{n:010d}")
    order_id = factory.LazyFunction(lambda: OrderFactory().order_id)
    trade_id = factory.Sequence(lambda n: f"TRD{n:010d}")

    # Execution details
    symbol = factory.SubFactory(CurrencyPairFactory)
    side = factory.fuzzy.FuzzyChoice(["BUY", "SELL"])
    quantity = factory.fuzzy.FuzzyDecimal(0.01, 5.0, 2)
    price = factory.fuzzy.FuzzyDecimal(1.0000, 1.5000, 4)

    # Execution metadata
    executed_at = factory.LazyFunction(
        lambda: fake.date_time_between(start_date="-7d", end_date="now")
    )
    venue = factory.fuzzy.FuzzyChoice(["IB", "FXCM", "OANDA", "EBS", "Reuters"])
    liquidity = factory.fuzzy.FuzzyChoice(["MAKER", "TAKER"])

    # Financial calculations
    gross_amount = factory.LazyAttribute(lambda obj: obj.quantity * obj.price)
    commission = factory.LazyAttribute(
        lambda obj: obj.gross_amount * Decimal("0.0002")
    )  # 2 basis points
    net_amount = factory.LazyAttribute(lambda obj: obj.gross_amount - obj.commission)

    # Market impact and slippage
    expected_price = factory.LazyAttribute(
        lambda obj: obj.price + Decimal(str(fake.random.uniform(-0.0005, 0.0005)))
    )
    slippage = factory.LazyAttribute(lambda obj: abs(obj.price - obj.expected_price))

    class Params:
        # Traits for different execution qualities
        good_fill = factory.Trait(
            slippage=factory.fuzzy.FuzzyDecimal(0.0000, 0.0002, 4), liquidity="MAKER"
        )

        poor_fill = factory.Trait(
            slippage=factory.fuzzy.FuzzyDecimal(0.0005, 0.0020, 4), liquidity="TAKER"
        )


class TradeFactory(factory.Factory):
    """
    Factory for creating completed trades with profit/loss and risk metrics.

    Generates realistic trading data including entry/exit points, P&L calculations,
    risk metrics, and trade performance data.
    """

    class Meta:
        model = dict

    # Trade identification
    trade_id = factory.Sequence(lambda n: f"TRD{n:010d}")
    account_id = factory.Sequence(lambda n: f"ACC{n:08d}")
    strategy_name = factory.fuzzy.FuzzyChoice(
        [
            "GBP_USD_Strategy",
            "EUR_USD_Scalper",
            "Trend_Following",
            "Mean_Reversion",
            "Breakout_Strategy",
            "News_Trading",
        ]
    )

    # Trade details
    symbol = factory.SubFactory(CurrencyPairFactory)
    side = factory.fuzzy.FuzzyChoice(["LONG", "SHORT"])
    quantity = factory.fuzzy.FuzzyDecimal(0.01, 10.0, 2)

    # Entry execution
    entry_price = factory.fuzzy.FuzzyDecimal(1.0000, 1.5000, 4)
    entry_time = factory.LazyFunction(
        lambda: fake.date_time_between(start_date="-30d", end_date="-1d")
    )
    entry_order_id = factory.LazyFunction(lambda: OrderFactory().order_id)

    # Exit execution
    exit_price = factory.LazyAttribute(
        lambda obj: obj.entry_price
        + (
            Decimal(str(fake.random.uniform(-0.0100, 0.0200)))
            if obj.side == "LONG"
            else Decimal(str(fake.random.uniform(-0.0200, 0.0100)))
        )
    )
    exit_time = factory.LazyAttribute(
        lambda obj: obj.entry_time
        + timedelta(minutes=fake.random_int(5, 1440))  # 5 minutes to 24 hours
    )
    exit_order_id = factory.LazyFunction(lambda: OrderFactory().order_id)
    exit_reason = factory.fuzzy.FuzzyChoice(
        ["TAKE_PROFIT", "STOP_LOSS", "MANUAL_CLOSE", "TIME_EXIT", "SIGNAL_REVERSAL"]
    )

    # P&L calculations
    gross_pnl = factory.LazyAttribute(
        lambda obj: (
            (obj.exit_price - obj.entry_price) * obj.quantity
            if obj.side == "LONG"
            else (obj.entry_price - obj.exit_price) * obj.quantity
        )
    )
    commission = factory.LazyAttribute(
        lambda obj: (abs(obj.entry_price) + abs(obj.exit_price))
        * obj.quantity
        * Decimal("0.0002")
    )
    swap = factory.LazyAttribute(
        lambda obj: (
            obj.quantity * Decimal(str(fake.random.uniform(-2.0, 1.0)))
            if (obj.exit_time - obj.entry_time).days > 0
            else Decimal("0")
        )
    )
    net_pnl = factory.LazyAttribute(
        lambda obj: obj.gross_pnl - obj.commission - obj.swap
    )

    # Risk metrics
    risk_amount = factory.fuzzy.FuzzyDecimal(100.0, 2000.0, 2)
    risk_reward_ratio = factory.LazyAttribute(
        lambda obj: (
            abs(obj.net_pnl / obj.risk_amount) if obj.risk_amount != 0 else Decimal("0")
        )
    )
    max_adverse_excursion = factory.fuzzy.FuzzyDecimal(0.0, 500.0, 2)
    max_favorable_excursion = factory.fuzzy.FuzzyDecimal(0.0, 1000.0, 2)

    # Trade duration and timing
    duration_minutes = factory.LazyAttribute(
        lambda obj: int((obj.exit_time - obj.entry_time).total_seconds() / 60)
    )
    session = factory.LazyAttribute(
        lambda obj: {
            0: "Sydney",
            1: "Sydney",
            2: "Sydney",
            3: "Sydney",
            4: "Sydney",
            5: "Sydney",
            6: "Tokyo",
            7: "Tokyo",
            8: "Tokyo",
            9: "Tokyo",
            10: "Tokyo",
            11: "Tokyo",
            12: "London",
            13: "London",
            14: "London",
            15: "London",
            16: "London",
            17: "London",
            18: "New York",
            19: "New York",
            20: "New York",
            21: "New York",
            22: "New York",
            23: "New York",
        }.get(obj.entry_time.hour, "London")
    )

    # Trade status
    status = "CLOSED"
    is_profitable = factory.LazyAttribute(lambda obj: obj.net_pnl > 0)

    class Params:
        # Traits for different trade outcomes
        profitable = factory.Trait(
            exit_price=factory.LazyAttribute(
                lambda obj: (
                    obj.entry_price + Decimal("0.0050")
                    if obj.side == "LONG"
                    else obj.entry_price - Decimal("0.0050")
                )
            ),
            exit_reason="TAKE_PROFIT",
        )

        losing = factory.Trait(
            exit_price=factory.LazyAttribute(
                lambda obj: (
                    obj.entry_price - Decimal("0.0030")
                    if obj.side == "LONG"
                    else obj.entry_price + Decimal("0.0030")
                )
            ),
            exit_reason="STOP_LOSS",
        )

        scalp = factory.Trait(
            quantity=factory.fuzzy.FuzzyDecimal(1.0, 5.0, 2),
            duration_minutes=factory.fuzzy.FuzzyInteger(1, 15),
            strategy_name="Scalping_Strategy",
        )

        swing = factory.Trait(
            duration_minutes=factory.fuzzy.FuzzyInteger(1440, 10080),  # 1 day to 1 week
            strategy_name="Swing_Trading",
        )


class PositionFactory(factory.Factory):
    """
    Factory for creating open trading positions with current market data.
    """

    class Meta:
        model = dict

    # Position identification
    position_id = factory.Sequence(lambda n: f"POS{n:010d}")
    account_id = factory.Sequence(lambda n: f"ACC{n:08d}")

    # Position details
    symbol = factory.SubFactory(CurrencyPairFactory)
    side = factory.fuzzy.FuzzyChoice(["LONG", "SHORT"])
    quantity = factory.fuzzy.FuzzyDecimal(0.01, 10.0, 2)

    # Entry data
    entry_price = factory.fuzzy.FuzzyDecimal(1.0000, 1.5000, 4)
    entry_time = factory.LazyFunction(
        lambda: fake.date_time_between(start_date="-7d", end_date="now")
    )

    # Current market data
    current_price = factory.LazyAttribute(
        lambda obj: obj.entry_price + Decimal(str(fake.random.uniform(-0.0050, 0.0050)))
    )

    # P&L calculations
    unrealized_pnl = factory.LazyAttribute(
        lambda obj: (
            (obj.current_price - obj.entry_price) * obj.quantity
            if obj.side == "LONG"
            else (obj.entry_price - obj.current_price) * obj.quantity
        )
    )

    # Risk management
    stop_loss = factory.LazyAttribute(
        lambda obj: (
            obj.entry_price - Decimal("0.0030")
            if obj.side == "LONG"
            else obj.entry_price + Decimal("0.0030")
        )
    )
    take_profit = factory.LazyAttribute(
        lambda obj: (
            obj.entry_price + Decimal("0.0060")
            if obj.side == "LONG"
            else obj.entry_price - Decimal("0.0060")
        )
    )

    # Margin and exposure
    margin_used = factory.LazyAttribute(
        lambda obj: obj.quantity * obj.entry_price * Decimal("0.01")
    )  # 1% margin
    exposure = factory.LazyAttribute(lambda obj: obj.quantity * obj.current_price)

    # Position status
    status = "OPEN"
    last_updated = factory.LazyFunction(lambda: datetime.utcnow())

    class Params:
        # Traits for different position states
        profitable = factory.Trait(
            current_price=factory.LazyAttribute(
                lambda obj: (
                    obj.entry_price + Decimal("0.0025")
                    if obj.side == "LONG"
                    else obj.entry_price - Decimal("0.0025")
                )
            )
        )

        losing = factory.Trait(
            current_price=factory.LazyAttribute(
                lambda obj: (
                    obj.entry_price - Decimal("0.0015")
                    if obj.side == "LONG"
                    else obj.entry_price + Decimal("0.0015")
                )
            )
        )

        large_position = factory.Trait(
            quantity=factory.fuzzy.FuzzyDecimal(5.0, 50.0, 2)
        )
