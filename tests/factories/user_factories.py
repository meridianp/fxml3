"""
User and Account Factory Definitions
===================================

Factory Boy factories for creating user accounts, trading accounts, and related
authentication/profile data for testing.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict

import factory
import factory.fuzzy
from faker import Faker

# Initialize faker with financial locale
fake = Faker(["en_US", "en_GB"])  # US/UK for financial data


class UserFactory(factory.Factory):
    """
    Factory for creating user accounts with realistic data.

    Generates users with proper authentication data, contact information,
    and account settings suitable for financial trading applications.
    """

    class Meta:
        model = dict  # Using dict for now, can be adapted to SQLAlchemy models

    # Basic user information
    user_id = factory.Sequence(lambda n: f"user_{n:06d}")
    username = factory.Sequence(lambda n: f"trader_{n}")
    email = factory.LazyAttribute(lambda obj: f"{obj.username}@{fake.domain_name()}")

    # Authentication
    password_hash = factory.LazyFunction(
        lambda: "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LLVMxryCHmN2nOZuu"  # "password123"
    )
    is_active = True
    is_verified = True
    failed_login_attempts = 0
    account_locked = False

    # Personal information
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    full_name = factory.LazyAttribute(lambda obj: f"{obj.first_name} {obj.last_name}")

    # Contact information
    phone_number = factory.Faker("phone_number")
    country_code = factory.fuzzy.FuzzyChoice(["US", "GB", "EU", "CA", "AU"])
    timezone = factory.LazyAttribute(
        lambda obj: {
            "US": "America/New_York",
            "GB": "Europe/London",
            "EU": "Europe/Frankfurt",
            "CA": "America/Toronto",
            "AU": "Australia/Sydney",
        }[obj.country_code]
    )

    # Account metadata
    created_at = factory.LazyFunction(
        lambda: fake.date_time_between(start_date="-2y", end_date="now")
    )
    updated_at = factory.LazyAttribute(
        lambda obj: obj.created_at + timedelta(days=fake.random_int(0, 30))
    )
    last_login = factory.LazyFunction(
        lambda: fake.date_time_between(start_date="-30d", end_date="now")
    )

    # Trading permissions and settings
    trading_enabled = True
    api_access_enabled = factory.fuzzy.FuzzyChoice([True, False])
    risk_level = factory.fuzzy.FuzzyChoice(["conservative", "moderate", "aggressive"])

    # Compliance and verification
    kyc_verified = True
    kyc_verification_date = factory.LazyAttribute(
        lambda obj: obj.created_at + timedelta(days=fake.random_int(1, 7))
    )
    aml_status = factory.fuzzy.FuzzyChoice(["passed", "pending", "flagged"])

    class Params:
        # Traits for different user types
        new_user = factory.Trait(
            created_at=factory.LazyFunction(
                lambda: datetime.utcnow() - timedelta(days=1)
            ),
            last_login=None,
            kyc_verified=False,
            trading_enabled=False,
        )

        premium_user = factory.Trait(
            risk_level="aggressive",
            api_access_enabled=True,
            trading_enabled=True,
            kyc_verified=True,
        )

        demo_user = factory.Trait(
            username=factory.Sequence(lambda n: f"demo_{n}"),
            trading_enabled=True,
            risk_level="moderate",
        )

        locked_user = factory.Trait(
            account_locked=True,
            failed_login_attempts=5,
            is_active=False,
            trading_enabled=False,
        )


class UserProfileFactory(factory.Factory):
    """
    Factory for creating detailed user profiles with preferences and settings.
    """

    class Meta:
        model = dict

    user_id = factory.LazyFunction(lambda: UserFactory().user_id)

    # Trading preferences
    default_lot_size = factory.fuzzy.FuzzyDecimal(0.01, 2.0, 2)
    max_risk_per_trade = factory.fuzzy.FuzzyDecimal(0.01, 0.05, 3)  # 1-5%
    max_daily_loss = factory.fuzzy.FuzzyDecimal(0.05, 0.15, 3)  # 5-15%
    preferred_timeframe = factory.fuzzy.FuzzyChoice(
        ["1m", "5m", "15m", "1h", "4h", "1d"]
    )

    # UI/UX preferences
    theme = factory.fuzzy.FuzzyChoice(["light", "dark", "auto"])
    language = factory.fuzzy.FuzzyChoice(["en", "es", "fr", "de", "ja"])
    currency_display = factory.fuzzy.FuzzyChoice(["USD", "EUR", "GBP", "JPY"])

    # Notification preferences
    email_notifications = True
    sms_notifications = factory.fuzzy.FuzzyChoice([True, False])
    push_notifications = True
    trade_alerts = True
    news_alerts = factory.fuzzy.FuzzyChoice([True, False])

    # Trading strategy preferences
    preferred_strategies = factory.LazyFunction(
        lambda: fake.random_elements(
            ["trend_following", "mean_reversion", "breakout", "scalping"], length=2
        )
    )
    auto_trading_enabled = factory.fuzzy.FuzzyChoice([True, False])
    copy_trading_enabled = factory.fuzzy.FuzzyChoice([True, False])

    # Experience and background
    trading_experience = factory.fuzzy.FuzzyChoice(
        ["beginner", "intermediate", "advanced", "professional"]
    )
    years_trading = factory.fuzzy.FuzzyInteger(0, 20)
    primary_trading_style = factory.fuzzy.FuzzyChoice(
        ["day_trading", "swing_trading", "position_trading", "scalping"]
    )

    # Profile metadata
    profile_completed = factory.fuzzy.FuzzyChoice([True, False])
    last_updated = factory.LazyFunction(
        lambda: fake.date_time_between(start_date="-30d", end_date="now")
    )


class TradingAccountFactory(factory.Factory):
    """
    Factory for creating trading accounts with realistic balances and settings.

    Creates trading accounts linked to users with appropriate financial data,
    trading permissions, and account configurations.
    """

    class Meta:
        model = dict

    # Account identification
    account_id = factory.Sequence(lambda n: f"ACC{n:08d}")
    user_id = factory.LazyFunction(lambda: UserFactory().user_id)
    broker_account_id = factory.LazyAttribute(lambda obj: f"BRK-{obj.account_id}")

    # Account type and status
    account_type = factory.fuzzy.FuzzyChoice(["live", "demo", "paper"])
    account_status = factory.fuzzy.FuzzyChoice(
        ["active", "inactive", "suspended", "closed"]
    )
    is_primary = True

    # Financial data
    base_currency = factory.fuzzy.FuzzyChoice(["USD", "EUR", "GBP", "CHF", "JPY"])
    balance = factory.fuzzy.FuzzyDecimal(1000.0, 100000.0, 2)
    equity = factory.LazyAttribute(
        lambda obj: obj.balance + fake.pydecimal(2, 2, positive=True) * 100
    )
    margin_used = factory.LazyAttribute(
        lambda obj: obj.balance * Decimal(str(fake.random.uniform(0.0, 0.3)))
    )
    margin_available = factory.LazyAttribute(lambda obj: obj.balance - obj.margin_used)
    free_margin = factory.LazyAttribute(
        lambda obj: obj.margin_available * Decimal("0.8")
    )

    # Leverage and risk settings
    leverage = factory.fuzzy.FuzzyChoice([1, 10, 20, 50, 100, 200, 400])
    max_leverage = factory.LazyAttribute(lambda obj: obj.leverage)
    margin_call_level = factory.fuzzy.FuzzyDecimal(50.0, 100.0, 1)
    stop_out_level = factory.fuzzy.FuzzyDecimal(20.0, 50.0, 1)

    # Trading limits
    max_positions = factory.fuzzy.FuzzyInteger(10, 100)
    max_lot_size = factory.fuzzy.FuzzyDecimal(1.0, 100.0, 2)
    daily_loss_limit = factory.fuzzy.FuzzyDecimal(1000.0, 10000.0, 2)
    monthly_loss_limit = factory.LazyAttribute(lambda obj: obj.daily_loss_limit * 20)

    # Performance metrics
    total_trades = factory.fuzzy.FuzzyInteger(0, 1000)
    winning_trades = factory.LazyAttribute(
        lambda obj: int(obj.total_trades * fake.random.uniform(0.3, 0.7))
    )
    losing_trades = factory.LazyAttribute(
        lambda obj: obj.total_trades - obj.winning_trades
    )
    total_profit_loss = factory.fuzzy.FuzzyDecimal(-10000.0, 20000.0, 2)
    max_drawdown = factory.fuzzy.FuzzyDecimal(0.0, 30.0, 2)  # Percentage

    # Account metadata
    created_at = factory.LazyFunction(
        lambda: fake.date_time_between(start_date="-1y", end_date="now")
    )
    activated_at = factory.LazyAttribute(
        lambda obj: obj.created_at + timedelta(days=fake.random_int(0, 7))
    )
    last_activity = factory.LazyFunction(
        lambda: fake.date_time_between(start_date="-7d", end_date="now")
    )

    # Broker integration
    broker_name = factory.fuzzy.FuzzyChoice(
        ["Interactive Brokers", "FXCM", "OANDA", "Manual"]
    )
    broker_server = factory.LazyAttribute(
        lambda obj: {
            "Interactive Brokers": "tws-api",
            "FXCM": "forex-connect",
            "OANDA": "v20-api",
            "Manual": "manual-entry",
        }[obj.broker_name]
    )
    connection_status = factory.fuzzy.FuzzyChoice(
        ["connected", "disconnected", "error"]
    )

    class Params:
        # Traits for different account types
        high_balance = factory.Trait(
            balance=factory.fuzzy.FuzzyDecimal(50000.0, 500000.0, 2),
            leverage=factory.fuzzy.FuzzyChoice([50, 100, 200]),
            max_positions=factory.fuzzy.FuzzyInteger(50, 200),
        )

        demo_account = factory.Trait(
            account_type="demo",
            balance=Decimal("10000.00"),
            leverage=100,
            broker_name="Demo Broker",
        )

        new_account = factory.Trait(
            balance=factory.fuzzy.FuzzyDecimal(1000.0, 5000.0, 2),
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            total_profit_loss=Decimal("0.00"),
            max_drawdown=Decimal("0.00"),
            created_at=factory.LazyFunction(
                lambda: datetime.utcnow() - timedelta(days=1)
            ),
        )

        profitable_account = factory.Trait(
            total_profit_loss=factory.fuzzy.FuzzyDecimal(5000.0, 50000.0, 2),
            winning_trades=factory.LazyAttribute(
                lambda obj: int(obj.total_trades * 0.65)  # 65% win rate
            ),
            max_drawdown=factory.fuzzy.FuzzyDecimal(5.0, 15.0, 2),
        )

        risky_account = factory.Trait(
            leverage=factory.fuzzy.FuzzyChoice([200, 400, 500]),
            max_drawdown=factory.fuzzy.FuzzyDecimal(20.0, 40.0, 2),
            margin_call_level=factory.fuzzy.FuzzyDecimal(30.0, 50.0, 1),
        )


class BrokerAccountFactory(factory.Factory):
    """
    Factory for creating broker-specific account configurations.
    """

    class Meta:
        model = dict

    account_id = factory.LazyFunction(lambda: TradingAccountFactory().account_id)
    broker_name = factory.fuzzy.FuzzyChoice(["Interactive Brokers", "FXCM", "OANDA"])

    # Broker-specific identifiers
    broker_account_number = factory.Sequence(lambda n: f"DU{n:06d}")
    broker_username = factory.Sequence(lambda n: f"trader{n}")

    # Connection settings
    server_host = factory.LazyAttribute(
        lambda obj: {
            "Interactive Brokers": "localhost",
            "FXCM": "http://www.fxcorporate.com/Hosts.jsp",
            "OANDA": "api-fxtrade.oanda.com",
        }[obj.broker_name]
    )
    server_port = factory.LazyAttribute(
        lambda obj: {"Interactive Brokers": 7497, "FXCM": 443, "OANDA": 443}[
            obj.broker_name
        ]
    )

    # API credentials (masked for security)
    api_key = factory.LazyFunction(lambda: fake.uuid4())
    api_secret = factory.LazyFunction(lambda: fake.sha256())
    access_token = factory.LazyFunction(lambda: fake.uuid4())

    # Connection status and metadata
    is_connected = factory.fuzzy.FuzzyChoice([True, False])
    last_connection = factory.LazyFunction(
        lambda: fake.date_time_between(start_date="-24h", end_date="now")
    )
    connection_errors = factory.fuzzy.FuzzyInteger(0, 5)

    # Trading permissions
    live_trading_enabled = True
    paper_trading_enabled = True
    data_feed_enabled = True
    order_management_enabled = True
