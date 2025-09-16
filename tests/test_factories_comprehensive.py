"""
Comprehensive Test Suite for Factory Boy Data Factories
======================================================

Test suite demonstrating and validating all test data factories including
relationships, traits, and realistic data generation patterns.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List

import factory
import pytest

# Import all factories
from tests.factories import (  # User and Account Factories; Trading Factories; Market Data Factories; ML Factories; Analysis Factories; Risk Factories; Compliance Factories; Infrastructure Factories
    AuditLogFactory,
    BacktestFactory,
    BacktestResultFactory,
    BrokerConnectionFactory,
    CandlestickFactory,
    ComplianceEventFactory,
    CurrencyPairFactory,
    DatabaseConnectionFactory,
    DrawdownEventFactory,
    ExecutionFactory,
    ExposureFactory,
    FeatureFactory,
    FIXSessionFactory,
    MarketDataFactory,
    MarketRegimeFactory,
    MarketSessionFactory,
    MessageQueueFactory,
    ModelFactory,
    OrderFactory,
    PositionFactory,
    PredictionFactory,
    RegulatoryReportFactory,
    RiskLimitFactory,
    RiskMetricFactory,
    SentimentDataFactory,
    SignalFactory,
    TechnicalIndicatorFactory,
    TickDataFactory,
    TradeFactory,
    TradeReportFactory,
    TradingAccountFactory,
    UserFactory,
    UserProfileFactory,
    WavePatternFactory,
)


class TestUserFactories:
    """Test user and account factory data generation."""

    def test_user_factory_basic(self):
        """Test basic user creation."""
        user = UserFactory()

        assert isinstance(user, dict)
        assert "user_id" in user
        assert "username" in user
        assert "email" in user
        assert user["is_active"] is True
        assert user["username"].startswith("trader_")
        assert "@" in user["email"]

    def test_user_factory_traits(self):
        """Test user factory traits."""
        # Test new user trait
        new_user = UserFactory(new_user=True)
        assert new_user["kyc_verified"] is False
        assert new_user["trading_enabled"] is False

        # Test premium user trait
        premium_user = UserFactory(premium_user=True)
        assert premium_user["risk_level"] == "aggressive"
        assert premium_user["api_access_enabled"] is True

        # Test locked user trait
        locked_user = UserFactory(locked_user=True)
        assert locked_user["account_locked"] is True
        assert locked_user["failed_login_attempts"] == 5

    def test_trading_account_factory(self):
        """Test trading account creation with financial constraints."""
        account = TradingAccountFactory()

        assert isinstance(account, dict)
        assert "account_id" in account
        assert "balance" in account
        assert "leverage" in account

        # Validate financial relationships
        assert account["balance"] > 0
        assert account["equity"] >= account["balance"]  # Equity should be >= balance
        assert account["margin_available"] <= account["balance"]
        assert account["leverage"] in [1, 10, 20, 50, 100, 200, 400]

    def test_trading_account_traits(self):
        """Test trading account traits."""
        # High balance account
        high_balance = TradingAccountFactory(high_balance=True)
        assert high_balance["balance"] >= 50000
        assert high_balance["max_positions"] >= 50

        # Demo account
        demo_account = TradingAccountFactory(demo_account=True)
        assert demo_account["account_type"] == "demo"
        assert demo_account["balance"] == Decimal("10000.00")

        # Profitable account
        profitable = TradingAccountFactory(profitable_account=True)
        assert profitable["total_profit_loss"] > 0
        assert profitable["winning_trades"] > profitable["losing_trades"]


class TestTradingFactories:
    """Test trading entity factories."""

    def test_currency_pair_factory(self):
        """Test currency pair creation with forex constraints."""
        pair = CurrencyPairFactory()

        assert isinstance(pair, dict)
        assert len(pair["symbol"]) == 6
        assert pair["base_currency"] == pair["symbol"][:3]
        assert pair["quote_currency"] == pair["symbol"][3:]
        assert pair["bid_price"] < pair["ask_price"]
        assert pair["mid_price"] == (pair["bid_price"] + pair["ask_price"]) / 2

    def test_currency_pair_pip_size(self):
        """Test proper pip size calculation."""
        # JPY pairs should have 0.01 pip size
        jpy_pair = CurrencyPairFactory(symbol="USDJPY")
        assert jpy_pair["pip_size"] == Decimal("0.01")

        # Non-JPY pairs should have 0.0001 pip size
        eur_pair = CurrencyPairFactory(symbol="EURUSD")
        assert eur_pair["pip_size"] == Decimal("0.0001")

    def test_trade_factory_pnl_calculation(self):
        """Test trade P&L calculations."""
        trade = TradeFactory()

        assert isinstance(trade, dict)
        assert "trade_id" in trade
        assert "entry_price" in trade
        assert "exit_price" in trade
        assert "gross_pnl" in trade
        assert "net_pnl" in trade

        # Validate P&L calculation logic
        expected_gross_pnl = (
            (trade["exit_price"] - trade["entry_price"]) * trade["quantity"]
            if trade["side"] == "LONG"
            else (trade["entry_price"] - trade["exit_price"]) * trade["quantity"]
        )
        assert trade["gross_pnl"] == expected_gross_pnl
        assert (
            trade["net_pnl"] == trade["gross_pnl"] - trade["commission"] - trade["swap"]
        )

    def test_trade_factory_traits(self):
        """Test trade factory traits."""
        # Profitable trade
        profitable_trade = TradeFactory(profitable=True)
        assert profitable_trade["net_pnl"] > 0
        assert profitable_trade["exit_reason"] == "TAKE_PROFIT"

        # Losing trade
        losing_trade = TradeFactory(losing=True)
        assert losing_trade["net_pnl"] < 0
        assert losing_trade["exit_reason"] == "STOP_LOSS"

    def test_position_factory_unrealized_pnl(self):
        """Test position unrealized P&L calculation."""
        position = PositionFactory()

        expected_unrealized = (
            (position["current_price"] - position["entry_price"]) * position["quantity"]
            if position["side"] == "LONG"
            else (position["entry_price"] - position["current_price"])
            * position["quantity"]
        )
        assert position["unrealized_pnl"] == expected_unrealized
        assert position["status"] == "OPEN"


class TestMarketDataFactories:
    """Test market data factory generation."""

    def test_market_data_factory_ohlc_constraints(self):
        """Test OHLC price relationships."""
        candle = MarketDataFactory()

        assert isinstance(candle, dict)
        assert candle["high_price"] >= candle["open_price"]
        assert candle["high_price"] >= candle["close_price"]
        assert candle["low_price"] <= candle["open_price"]
        assert candle["low_price"] <= candle["close_price"]
        assert candle["low_price"] <= candle["high_price"]

    def test_market_data_traits(self):
        """Test market data pattern traits."""
        # Trending up candle
        trending_up = MarketDataFactory(trending_up=True)
        assert trending_up["close_price"] > trending_up["open_price"]

        # Trending down candle
        trending_down = MarketDataFactory(trending_down=True)
        assert trending_down["close_price"] < trending_down["open_price"]

        # High volatility candle
        high_vol = MarketDataFactory(high_volatility=True)
        assert high_vol["volume"] > MarketDataFactory()["volume"]  # Should be higher

    def test_candlestick_factory_patterns(self):
        """Test candlestick pattern identification."""
        candle = CandlestickFactory()

        assert "body_size" in candle
        assert "upper_shadow" in candle
        assert "lower_shadow" in candle
        assert "is_bullish" in candle

        # Validate pattern calculations
        expected_body = abs(candle["close_price"] - candle["open_price"])
        assert candle["body_size"] == expected_body

        expected_bullish = candle["close_price"] > candle["open_price"]
        assert candle["is_bullish"] == expected_bullish

    def test_tick_data_factory_spread(self):
        """Test tick data bid/ask spread."""
        tick = TickDataFactory()

        assert tick["ask_price"] > tick["bid_price"]
        assert tick["spread"] == tick["ask_price"] - tick["bid_price"]
        assert tick["mid_price"] == (tick["bid_price"] + tick["ask_price"]) / 2


class TestMLFactories:
    """Test machine learning factory data generation."""

    def test_model_factory_performance_metrics(self):
        """Test ML model performance metrics."""
        model = ModelFactory()

        assert isinstance(model, dict)
        assert "model_id" in model
        assert "algorithm" in model
        assert "accuracy" in model
        assert "precision" in model
        assert "recall" in model

        # Validate metric ranges
        assert 0 <= model["accuracy"] <= 1
        assert 0 <= model["precision"] <= 1
        assert 0 <= model["recall"] <= 1

        # F1 score calculation
        if model["precision"] + model["recall"] > 0:
            expected_f1 = (
                2
                * (model["precision"] * model["recall"])
                / (model["precision"] + model["recall"])
            )
            assert abs(model["f1_score"] - expected_f1) < 0.001

    def test_model_factory_traits(self):
        """Test ML model factory traits."""
        # High performer
        high_performer = ModelFactory(high_performer=True)
        assert high_performer["accuracy"] >= 0.65
        assert high_performer["status"] == "deployed"
        assert high_performer["sharpe_ratio"] >= 1.5

        # Underperformer
        underperformer = ModelFactory(underperformer=True)
        assert underperformer["accuracy"] <= 0.55
        assert underperformer["status"] == "deprecated"

    def test_signal_factory_risk_calculations(self):
        """Test trading signal risk calculations."""
        signal = SignalFactory()

        assert isinstance(signal, dict)
        assert "confidence" in signal
        assert "risk_score" in signal
        assert "expected_return" in signal

        # Risk-reward calculation
        if signal["risk_score"] > 0:
            expected_rr = abs(signal["expected_return"] / signal["risk_score"])
            assert abs(signal["risk_reward_ratio"] - expected_rr) < 0.001

    def test_backtest_result_factory_metrics(self):
        """Test backtest result calculations."""
        result = BacktestResultFactory()

        assert isinstance(result, dict)
        assert result["total_trades"] > 0
        assert (
            result["winning_trades"] + result["losing_trades"] == result["total_trades"]
        )

        # Win rate calculation
        expected_win_rate = (result["winning_trades"] / result["total_trades"]) * 100
        assert abs(result["win_rate"] - expected_win_rate) < 0.001

        # Profit factor calculation
        if result["losing_trades"] > 0 and result["avg_losing_trade"] != 0:
            expected_pf = abs(
                result["avg_winning_trade"]
                * result["winning_trades"]
                / (result["avg_losing_trade"] * result["losing_trades"])
            )
            assert abs(result["profit_factor"] - expected_pf) < 0.001


class TestRiskFactories:
    """Test risk management factory data generation."""

    def test_risk_limit_factory_utilization(self):
        """Test risk limit utilization calculation."""
        limit = RiskLimitFactory()

        assert isinstance(limit, dict)
        assert "limit_value" in limit
        assert "current_value" in limit
        assert "utilization_percentage" in limit

        if limit["limit_value"] != 0:
            expected_utilization = (limit["current_value"] / limit["limit_value"]) * 100
            assert abs(limit["utilization_percentage"] - expected_utilization) < 0.001

    def test_risk_limit_status_logic(self):
        """Test risk limit status determination."""
        # Breached limit
        breached = RiskLimitFactory(breached_limit=True)
        assert breached["status"] == "breached"
        assert breached["current_value"] > breached["limit_value"]
        assert breached["alert_sent"] is True

    def test_drawdown_event_recovery(self):
        """Test drawdown recovery calculations."""
        drawdown = DrawdownEventFactory()

        assert drawdown["peak_balance"] > drawdown["trough_balance"]
        assert (
            drawdown["max_drawdown_amount"]
            == drawdown["peak_balance"] - drawdown["trough_balance"]
        )

        expected_drawdown_pct = (
            drawdown["max_drawdown_amount"] / drawdown["peak_balance"]
        ) * 100
        assert abs(drawdown["max_drawdown_percent"] - expected_drawdown_pct) < 0.001


class TestComplianceFactories:
    """Test compliance and audit factory data generation."""

    def test_compliance_event_factory_severity(self):
        """Test compliance event severity mapping."""
        event = ComplianceEventFactory()

        assert isinstance(event, dict)
        assert event["severity"] in ["low", "medium", "high", "critical"]
        assert event["category"] in [
            "risk_management",
            "market_conduct",
            "customer_protection",
            "anti_money_laundering",
            "know_your_customer",
            "market_abuse",
            "operational_risk",
            "regulatory_reporting",
        ]

    def test_compliance_event_traits(self):
        """Test compliance event traits."""
        # High severity event
        high_severity = ComplianceEventFactory(high_severity=True)
        assert high_severity["severity"] == "critical"
        assert high_severity["requires_regulatory_reporting"] is True
        assert high_severity["status"] == "investigating"

        # AML violation
        aml_violation = ComplianceEventFactory(aml_violation=True)
        assert aml_violation["event_type"] == "aml_alert"
        assert aml_violation["category"] == "anti_money_laundering"

    def test_audit_log_factory_completeness(self):
        """Test audit log completeness."""
        log = AuditLogFactory()

        assert isinstance(log, dict)
        assert "log_id" in log
        assert "user_id" in log
        assert "action_type" in log
        assert "timestamp" in log
        assert "ip_address" in log

        # Validate IP address format
        ip_parts = log["ip_address"].split(".")
        assert len(ip_parts) == 4
        for part in ip_parts:
            assert 0 <= int(part) <= 255


class TestInfrastructureFactories:
    """Test infrastructure factory data generation."""

    def test_broker_connection_factory_configuration(self):
        """Test broker connection configuration."""
        connection = BrokerConnectionFactory()

        assert isinstance(connection, dict)
        assert "broker_name" in connection
        assert "host" in connection
        assert "port" in connection
        assert "protocol" in connection

        # Validate port ranges
        assert 0 <= connection["port"] <= 65535
        assert connection["uptime_percentage"] <= 100.0

    def test_broker_connection_traits(self):
        """Test broker connection traits."""
        # Production ready connection
        prod_connection = BrokerConnectionFactory(production_ready=True)
        assert prod_connection["environment"] == "production"
        assert prod_connection["status"] == "connected"
        assert prod_connection["supports_live_trading"] is True

        # Development setup
        dev_connection = BrokerConnectionFactory(development_setup=True)
        assert dev_connection["environment"] == "development"
        assert dev_connection["supports_live_trading"] is False

    def test_message_queue_factory_metrics(self):
        """Test message queue performance metrics."""
        queue = MessageQueueFactory()

        assert isinstance(queue, dict)
        assert "queue_name" in queue
        assert "message_count" in queue
        assert "publish_rate" in queue
        assert "consume_rate" in queue

        # Validate message statistics
        assert queue["total_consumed"] <= queue["total_published"]
        assert queue["total_acked"] + queue["total_nacked"] == queue["total_consumed"]

    def test_database_connection_factory_pool(self):
        """Test database connection pool settings."""
        db_conn = DatabaseConnectionFactory()

        assert isinstance(db_conn, dict)
        assert "min_connections" in db_conn
        assert "max_connections" in db_conn
        assert db_conn["min_connections"] <= db_conn["max_connections"]
        assert db_conn["active_connections"] <= db_conn["max_connections"]


class TestFactoryRelationships:
    """Test factory relationships and data consistency."""

    def test_user_account_relationship(self):
        """Test user and trading account relationship."""
        user = UserFactory()
        account = TradingAccountFactory(user_id=user["user_id"])

        assert account["user_id"] == user["user_id"]

    def test_trade_execution_relationship(self):
        """Test trade and execution relationship."""
        trade = TradeFactory()
        execution = ExecutionFactory(trade_id=trade["trade_id"])

        assert execution["trade_id"] == trade["trade_id"]

    def test_model_signal_relationship(self):
        """Test ML model and signal relationship."""
        model = ModelFactory()
        signal = SignalFactory(model_id=model["model_id"])

        assert signal["model_id"] == model["model_id"]

    def test_backtest_result_relationship(self):
        """Test backtest and result relationship."""
        backtest = BacktestFactory()
        result = BacktestResultFactory(backtest_id=backtest["backtest_id"])

        assert result["backtest_id"] == backtest["backtest_id"]


class TestFactoryBatching:
    """Test batch creation capabilities."""

    def test_batch_user_creation(self):
        """Test creating multiple users."""
        users = UserFactory.create_batch(5)

        assert len(users) == 5
        assert all(isinstance(user, dict) for user in users)

        # Ensure unique user IDs
        user_ids = [user["user_id"] for user in users]
        assert len(set(user_ids)) == len(user_ids)

    def test_batch_trade_creation(self):
        """Test creating multiple trades."""
        trades = TradeFactory.create_batch(10)

        assert len(trades) == 10
        assert all(trade["status"] == "CLOSED" for trade in trades)

    def test_batch_market_data_creation(self):
        """Test creating market data series."""
        candles = MarketDataFactory.create_batch(20)

        assert len(candles) == 20

        # All candles should have valid OHLC relationships
        for candle in candles:
            assert candle["high_price"] >= max(
                candle["open_price"], candle["close_price"]
            )
            assert candle["low_price"] <= min(
                candle["open_price"], candle["close_price"]
            )


class TestFactoryCustomization:
    """Test factory customization and parameter override."""

    def test_custom_user_parameters(self):
        """Test overriding user factory parameters."""
        custom_user = UserFactory(
            username="custom_trader", email="custom@example.com", country_code="US"
        )

        assert custom_user["username"] == "custom_trader"
        assert custom_user["email"] == "custom@example.com"
        assert custom_user["country_code"] == "US"

    def test_custom_trade_parameters(self):
        """Test overriding trade factory parameters."""
        custom_trade = TradeFactory(
            symbol={"symbol": "GBPUSD"}, side="LONG", quantity=Decimal("5.00")
        )

        assert custom_trade["side"] == "LONG"
        assert custom_trade["quantity"] == Decimal("5.00")

    def test_custom_model_parameters(self):
        """Test overriding ML model factory parameters."""
        custom_model = ModelFactory(
            algorithm="XGBoost", symbol="EURUSD", accuracy=Decimal("0.75")
        )

        assert custom_model["algorithm"] == "XGBoost"
        assert custom_model["symbol"] == "EURUSD"
        assert custom_model["accuracy"] == Decimal("0.75")


@pytest.mark.performance
class TestFactoryPerformance:
    """Test factory creation performance."""

    def test_single_factory_creation_speed(self):
        """Test individual factory creation performance."""
        import time

        start_time = time.time()
        for _ in range(100):
            UserFactory()
        end_time = time.time()

        # Should create 100 users in under 1 second
        assert end_time - start_time < 1.0

    def test_batch_creation_speed(self):
        """Test batch factory creation performance."""
        import time

        start_time = time.time()
        TradeFactory.create_batch(1000)
        end_time = time.time()

        # Should create 1000 trades in under 5 seconds
        assert end_time - start_time < 5.0

    def test_complex_factory_creation(self):
        """Test creation of complex factories with relationships."""
        import time

        start_time = time.time()

        # Create related entities
        for _ in range(50):
            user = UserFactory()
            account = TradingAccountFactory(user_id=user["user_id"])
            trade = TradeFactory(account_id=account["account_id"])

        end_time = time.time()

        # Should create 50 complete entity sets in under 2 seconds
        assert end_time - start_time < 2.0


if __name__ == "__main__":
    # Run tests with verbose output
    pytest.main([__file__, "-v", "--tb=short"])
