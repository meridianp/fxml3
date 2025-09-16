"""
Infrastructure Factory Definitions
==================================

Factory Boy factories for creating infrastructure components including
broker connections, FIX sessions, message queues, and database connections.
"""

import json
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List

import factory
import factory.fuzzy
from faker import Faker

fake = Faker()


class BrokerConnectionFactory(factory.Factory):
    """
    Factory for creating broker connection configurations and status.

    Generates realistic broker integration data including connection settings,
    authentication, status monitoring, and performance metrics.
    """

    class Meta:
        model = dict

    # Connection identification
    connection_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    broker_name = factory.fuzzy.FuzzyChoice(
        ["Interactive Brokers", "FXCM", "OANDA", "IG", "Plus500", "Manual Entry"]
    )
    connection_name = factory.LazyAttribute(
        lambda obj: f"{obj.broker_name.replace(' ', '_').lower()}_connection"
    )

    # Connection configuration
    host = factory.LazyAttribute(
        lambda obj: {
            "Interactive Brokers": "localhost",
            "FXCM": "http://www.fxcorporate.com/Hosts.jsp",
            "OANDA": "api-fxpractice.oanda.com",
            "IG": "demo-api.ig.com",
            "Plus500": "api.plus500.com",
            "Manual Entry": "manual.local",
        }.get(obj.broker_name, fake.domain_name())
    )

    port = factory.LazyAttribute(
        lambda obj: {
            "Interactive Brokers": 7497,  # Paper trading port
            "FXCM": 443,
            "OANDA": 443,
            "IG": 443,
            "Plus500": 443,
            "Manual Entry": 0,
        }.get(obj.broker_name, fake.random_int(1000, 9999))
    )

    # Connection protocols
    protocol = factory.LazyAttribute(
        lambda obj: {
            "Interactive Brokers": "TWS_API",
            "FXCM": "ForexConnect",
            "OANDA": "REST_API",
            "IG": "REST_API",
            "Plus500": "WebSocket",
            "Manual Entry": "MANUAL",
        }.get(obj.broker_name, "REST_API")
    )

    # Authentication
    requires_authentication = factory.LazyAttribute(
        lambda obj: obj.broker_name != "Manual Entry"
    )
    username = factory.LazyAttribute(
        lambda obj: (
            f"{obj.broker_name.lower().replace(' ', '_')}_user_{fake.random_int(1000, 9999)}"
            if obj.requires_authentication
            else None
        )
    )

    # API credentials (masked for security)
    api_key = factory.LazyAttribute(
        lambda obj: fake.uuid4() if obj.requires_authentication else None
    )
    api_secret = factory.LazyAttribute(
        lambda obj: fake.sha256() if obj.requires_authentication else None
    )
    access_token = factory.LazyAttribute(
        lambda obj: fake.uuid4() if obj.broker_name in ["OANDA", "IG"] else None
    )

    # Connection status
    status = factory.fuzzy.FuzzyChoice(
        ["connected", "disconnected", "connecting", "error", "maintenance"]
    )
    is_active = factory.LazyAttribute(lambda obj: obj.status == "connected")
    last_connection_attempt = factory.LazyFunction(
        lambda: fake.date_time_between(start_date="-24h", end_date="now")
    )

    # Connection quality metrics
    uptime_percentage = factory.fuzzy.FuzzyDecimal(85.0, 99.9, 1)
    average_latency_ms = factory.LazyAttribute(
        lambda obj: {
            "Interactive Brokers": fake.random.uniform(10, 50),
            "FXCM": fake.random.uniform(50, 200),
            "OANDA": fake.random.uniform(100, 300),
            "Manual Entry": 0,
        }.get(obj.broker_name, fake.random.uniform(50, 500))
    )

    connection_errors_24h = factory.fuzzy.FuzzyInteger(0, 10)
    reconnection_attempts = factory.fuzzy.FuzzyInteger(0, 5)

    # Trading capabilities
    supports_live_trading = factory.LazyAttribute(
        lambda obj: obj.broker_name != "Manual Entry"
    )
    supports_paper_trading = True
    supports_market_data = factory.LazyAttribute(
        lambda obj: obj.broker_name != "Manual Entry"
    )
    supports_historical_data = factory.LazyAttribute(
        lambda obj: obj.broker_name != "Manual Entry"
    )

    # Supported instruments
    supported_instruments = factory.LazyAttribute(
        lambda obj: {
            "Interactive Brokers": ["FOREX", "STOCKS", "FUTURES", "OPTIONS", "BONDS"],
            "FXCM": ["FOREX", "CFD"],
            "OANDA": ["FOREX"],
            "IG": ["FOREX", "CFD", "STOCKS"],
            "Plus500": ["FOREX", "CFD", "CRYPTO"],
            "Manual Entry": ["FOREX"],
        }.get(obj.broker_name, ["FOREX"])
    )

    supported_currency_pairs = factory.LazyFunction(
        lambda: fake.random_elements(
            [
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
            ],
            length=fake.random_int(5, 10),
        )
    )

    # Rate limits and quotas
    requests_per_minute = factory.LazyAttribute(
        lambda obj: {
            "Interactive Brokers": 50,
            "FXCM": 100,
            "OANDA": 120,
            "IG": 60,
            "Plus500": 30,
            "Manual Entry": 0,
        }.get(obj.broker_name, 60)
    )

    daily_request_limit = factory.LazyAttribute(
        lambda obj: obj.requests_per_minute * 1440 if obj.requests_per_minute > 0 else 0
    )
    current_request_count = factory.LazyAttribute(
        lambda obj: (
            fake.random_int(0, obj.requests_per_minute)
            if obj.requests_per_minute > 0
            else 0
        )
    )

    # Configuration metadata
    created_at = factory.LazyFunction(
        lambda: fake.date_time_between(start_date="-90d", end_date="-1d")
    )
    last_updated = factory.LazyAttribute(
        lambda obj: obj.created_at + timedelta(days=fake.random_int(1, 30))
    )
    environment = factory.fuzzy.FuzzyChoice(
        ["production", "staging", "development", "sandbox"]
    )

    class Params:
        # Traits for different connection scenarios
        production_ready = factory.Trait(
            environment="production",
            status="connected",
            uptime_percentage=factory.fuzzy.FuzzyDecimal(98.0, 99.9, 1),
            connection_errors_24h=factory.fuzzy.FuzzyInteger(0, 2),
            supports_live_trading=True,
        )

        development_setup = factory.Trait(
            environment="development",
            status=factory.fuzzy.FuzzyChoice(["connected", "disconnected"]),
            supports_live_trading=False,
            supports_paper_trading=True,
        )

        connection_issues = factory.Trait(
            status=factory.fuzzy.FuzzyChoice(["error", "disconnected"]),
            connection_errors_24h=factory.fuzzy.FuzzyInteger(5, 20),
            uptime_percentage=factory.fuzzy.FuzzyDecimal(70.0, 90.0, 1),
            reconnection_attempts=factory.fuzzy.FuzzyInteger(3, 10),
        )


class FIXSessionFactory(factory.Factory):
    """
    Factory for creating FIX protocol session configurations.
    """

    class Meta:
        model = dict

    # Session identification
    session_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    sender_comp_id = factory.Sequence(lambda n: f"FXML4_SENDER_{n}")
    target_comp_id = factory.LazyAttribute(
        lambda obj: f"BROKER_{fake.random_int(100, 999)}"
    )

    # FIX protocol details
    fix_version = factory.fuzzy.FuzzyChoice(["FIX.4.2", "FIX.4.4", "FIX.5.0"])
    session_qualifier = factory.Sequence(lambda n: f"SESSION_{n}")

    # Connection settings
    socket_connect_host = factory.Faker("domain_name")
    socket_connect_port = factory.fuzzy.FuzzyInteger(7000, 9000)
    socket_accept_port = factory.fuzzy.FuzzyInteger(7000, 9000)

    # Session timing
    start_time = factory.fuzzy.FuzzyChoice(["00:00:00", "08:00:00", "17:00:00"])
    end_time = factory.fuzzy.FuzzyChoice(["23:59:59", "17:00:00", "08:00:00"])
    timezone = factory.fuzzy.FuzzyChoice(["UTC", "America/New_York", "Europe/London"])

    # Authentication and security
    username = factory.LazyAttribute(
        lambda obj: f"fix_user_{obj.sender_comp_id.lower()}"
    )
    password = factory.LazyFunction(lambda: fake.password(length=16))
    reset_on_logon = True
    reset_on_logout = True

    # Message handling
    heartbeat_interval = factory.fuzzy.FuzzyInteger(30, 300)  # seconds
    logon_timeout = factory.fuzzy.FuzzyInteger(30, 120)
    logout_timeout = factory.fuzzy.FuzzyInteger(10, 60)

    # Sequence number management
    sender_sequence_number = factory.fuzzy.FuzzyInteger(1, 1000)
    target_sequence_number = factory.fuzzy.FuzzyInteger(1, 1000)
    persist_messages = True

    # Session status
    session_status = factory.fuzzy.FuzzyChoice(
        [
            "disconnected",
            "connecting",
            "connected",
            "logging_on",
            "logged_on",
            "logging_out",
            "logged_out",
            "error",
        ]
    )

    last_logon_time = factory.LazyAttribute(
        lambda obj: (
            fake.date_time_between(start_date="-24h", end_date="now")
            if obj.session_status in ["connected", "logged_on"]
            else None
        )
    )

    # Message statistics
    messages_sent = factory.fuzzy.FuzzyInteger(0, 10000)
    messages_received = factory.fuzzy.FuzzyInteger(0, 10000)
    sequence_number_gaps = factory.fuzzy.FuzzyInteger(0, 5)
    message_errors = factory.fuzzy.FuzzyInteger(0, 10)

    # Performance metrics
    avg_roundtrip_time_ms = factory.fuzzy.FuzzyDecimal(10.0, 500.0, 1)
    max_roundtrip_time_ms = factory.LazyAttribute(
        lambda obj: obj.avg_roundtrip_time_ms * 3
    )
    throughput_msgs_per_sec = factory.fuzzy.FuzzyDecimal(1.0, 100.0, 1)

    # Configuration files
    config_file_path = factory.LazyAttribute(
        lambda obj: f"config/fix_sessions/{obj.sender_comp_id.lower()}.cfg"
    )
    log_file_path = factory.LazyAttribute(
        lambda obj: f"logs/fix/{obj.sender_comp_id.lower()}.log"
    )
    store_directory = factory.LazyAttribute(
        lambda obj: f"data/fix_store/{obj.sender_comp_id.lower()}"
    )

    class Params:
        # Traits for different session states
        active_session = factory.Trait(
            session_status="logged_on",
            messages_sent=factory.fuzzy.FuzzyInteger(1000, 10000),
            messages_received=factory.fuzzy.FuzzyInteger(1000, 10000),
            sequence_number_gaps=0,
            message_errors=factory.fuzzy.FuzzyInteger(0, 2),
        )

        problematic_session = factory.Trait(
            session_status=factory.fuzzy.FuzzyChoice(["error", "disconnected"]),
            sequence_number_gaps=factory.fuzzy.FuzzyInteger(3, 10),
            message_errors=factory.fuzzy.FuzzyInteger(5, 20),
            avg_roundtrip_time_ms=factory.fuzzy.FuzzyDecimal(200.0, 1000.0, 1),
        )


class MessageQueueFactory(factory.Factory):
    """
    Factory for creating message queue configurations and status.
    """

    class Meta:
        model = dict

    # Queue identification
    queue_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    queue_name = factory.fuzzy.FuzzyChoice(
        [
            "trading_orders",
            "market_data",
            "risk_alerts",
            "compliance_events",
            "audit_logs",
            "notifications",
            "backtest_results",
            "ml_predictions",
        ]
    )

    # Queue type and configuration
    queue_type = factory.fuzzy.FuzzyChoice(["direct", "topic", "fanout", "headers"])
    exchange_name = factory.LazyAttribute(lambda obj: f"{obj.queue_name}_exchange")
    routing_key = factory.LazyAttribute(lambda obj: f"{obj.queue_name}.routing")

    # RabbitMQ specific settings
    durable = True
    exclusive = False
    auto_delete = False
    persistent_messages = True

    # Queue capacity and limits
    max_length = factory.fuzzy.FuzzyInteger(1000, 100000)
    max_length_bytes = factory.LazyAttribute(
        lambda obj: obj.max_length * 1024
    )  # ~1KB per message
    message_ttl_ms = factory.fuzzy.FuzzyInteger(3600000, 86400000)  # 1-24 hours

    # Current queue status
    message_count = factory.fuzzy.FuzzyInteger(0, 1000)
    consumer_count = factory.fuzzy.FuzzyInteger(0, 10)
    memory_usage_bytes = factory.LazyAttribute(
        lambda obj: obj.message_count * fake.random_int(500, 2000)
    )

    # Performance metrics
    publish_rate = factory.fuzzy.FuzzyDecimal(0.0, 100.0, 1)  # messages/second
    consume_rate = factory.fuzzy.FuzzyDecimal(0.0, 100.0, 1)  # messages/second
    ack_rate = factory.fuzzy.FuzzyDecimal(0.0, 100.0, 1)  # acks/second

    # Message statistics
    total_published = factory.fuzzy.FuzzyInteger(1000, 1000000)
    total_consumed = factory.LazyAttribute(
        lambda obj: min(obj.total_published, obj.total_published - obj.message_count)
    )
    total_acked = factory.LazyAttribute(
        lambda obj: int(obj.total_consumed * 0.95)
    )  # 95% ack rate
    total_nacked = factory.LazyAttribute(
        lambda obj: obj.total_consumed - obj.total_acked
    )

    # Error handling
    dead_letter_exchange = factory.LazyAttribute(lambda obj: f"{obj.queue_name}_dlx")
    dead_letter_routing_key = factory.LazyAttribute(lambda obj: f"{obj.queue_name}.dlq")
    max_retries = factory.fuzzy.FuzzyInteger(3, 10)

    # Connection details
    host = factory.fuzzy.FuzzyChoice(
        ["localhost", "rabbitmq-cluster", "message-queue.internal"]
    )
    port = factory.fuzzy.FuzzyChoice([5672, 5673])
    virtual_host = factory.fuzzy.FuzzyChoice(["/", "/fxml4", "/production"])

    # Health and monitoring
    status = factory.fuzzy.FuzzyChoice(["running", "idle", "flow", "blocked", "error"])
    last_activity = factory.LazyFunction(
        lambda: fake.date_time_between(start_date="-1h", end_date="now")
    )
    health_check_passed = factory.LazyAttribute(
        lambda obj: obj.status in ["running", "idle", "flow"]
    )

    class Params:
        # Traits for different queue scenarios
        high_throughput = factory.Trait(
            publish_rate=factory.fuzzy.FuzzyDecimal(50.0, 1000.0, 1),
            consume_rate=factory.fuzzy.FuzzyDecimal(45.0, 950.0, 1),
            message_count=factory.fuzzy.FuzzyInteger(100, 5000),
            consumer_count=factory.fuzzy.FuzzyInteger(5, 20),
        )

        backlog_queue = factory.Trait(
            message_count=factory.fuzzy.FuzzyInteger(5000, 50000),
            publish_rate=factory.fuzzy.FuzzyDecimal(100.0, 200.0, 1),
            consume_rate=factory.fuzzy.FuzzyDecimal(10.0, 50.0, 1),
            status="blocked",
        )

        idle_queue = factory.Trait(
            message_count=0,
            publish_rate=Decimal("0.0"),
            consume_rate=Decimal("0.0"),
            consumer_count=0,
            status="idle",
        )


class DatabaseConnectionFactory(factory.Factory):
    """
    Factory for creating database connection configurations and monitoring.
    """

    class Meta:
        model = dict

    # Connection identification
    connection_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    database_name = factory.fuzzy.FuzzyChoice(
        ["fxml4_prod", "fxml4_dev", "fxml4_test", "timescale_db", "redis_cache"]
    )
    connection_name = factory.LazyAttribute(
        lambda obj: f"{obj.database_name}_connection"
    )

    # Database type and configuration
    database_type = factory.LazyAttribute(
        lambda obj: {
            "fxml4_prod": "PostgreSQL",
            "fxml4_dev": "PostgreSQL",
            "fxml4_test": "SQLite",
            "timescale_db": "TimescaleDB",
            "redis_cache": "Redis",
        }.get(obj.database_name, "PostgreSQL")
    )

    # Connection details
    host = factory.LazyAttribute(
        lambda obj: {
            "fxml4_prod": "prod-db.internal",
            "fxml4_dev": "localhost",
            "fxml4_test": "localhost",
            "timescale_db": "timescale.internal",
            "redis_cache": "redis.internal",
        }.get(obj.database_name, "localhost")
    )

    port = factory.LazyAttribute(
        lambda obj: {
            "PostgreSQL": 5432,
            "TimescaleDB": 5433,
            "SQLite": 0,
            "Redis": 6379,
        }.get(obj.database_type, 5432)
    )

    username = factory.LazyAttribute(
        lambda obj: (
            f"{obj.database_name.split('_')[0]}_user"
            if obj.database_type != "SQLite"
            else None
        )
    )

    # Connection pool settings
    min_connections = factory.fuzzy.FuzzyInteger(1, 5)
    max_connections = factory.fuzzy.FuzzyInteger(10, 100)
    connection_timeout_ms = factory.fuzzy.FuzzyInteger(5000, 30000)
    idle_timeout_ms = factory.fuzzy.FuzzyInteger(300000, 1800000)  # 5-30 minutes

    # Current connection status
    active_connections = factory.LazyAttribute(
        lambda obj: fake.random_int(obj.min_connections, obj.max_connections)
    )
    idle_connections = factory.LazyAttribute(
        lambda obj: fake.random_int(0, obj.max_connections - obj.active_connections)
    )

    status = factory.fuzzy.FuzzyChoice(
        ["connected", "connecting", "disconnected", "error", "maintenance"]
    )
    last_connection_test = factory.LazyFunction(
        lambda: fake.date_time_between(start_date="-1h", end_date="now")
    )

    # Performance metrics
    average_query_time_ms = factory.fuzzy.FuzzyDecimal(1.0, 100.0, 1)
    slow_queries_count = factory.fuzzy.FuzzyInteger(0, 50)
    failed_connections = factory.fuzzy.FuzzyInteger(0, 10)

    # Database-specific metrics
    database_size_mb = factory.LazyAttribute(
        lambda obj: {
            "fxml4_prod": fake.random.uniform(1000, 100000),
            "timescale_db": fake.random.uniform(5000, 500000),
            "redis_cache": fake.random.uniform(100, 10000),
            "fxml4_test": fake.random.uniform(10, 1000),
        }.get(obj.database_name, fake.random.uniform(100, 10000))
    )

    # Health monitoring
    cpu_usage_percent = factory.fuzzy.FuzzyDecimal(5.0, 80.0, 1)
    memory_usage_percent = factory.fuzzy.FuzzyDecimal(30.0, 90.0, 1)
    disk_usage_percent = factory.fuzzy.FuzzyDecimal(20.0, 85.0, 1)

    # Backup and maintenance
    last_backup = factory.LazyFunction(
        lambda: fake.date_time_between(start_date="-7d", end_date="-1d")
    )
    backup_frequency = factory.fuzzy.FuzzyChoice(["daily", "weekly", "monthly"])
    maintenance_window = factory.fuzzy.FuzzyChoice(
        ["Sunday 02:00-04:00", "Saturday 01:00-03:00"]
    )

    class Params:
        # Traits for different database scenarios
        production_database = factory.Trait(
            database_name="fxml4_prod",
            max_connections=factory.fuzzy.FuzzyInteger(50, 200),
            status="connected",
            failed_connections=factory.fuzzy.FuzzyInteger(0, 2),
            backup_frequency="daily",
        )

        development_database = factory.Trait(
            database_name="fxml4_dev",
            max_connections=factory.fuzzy.FuzzyInteger(5, 20),
            status=factory.fuzzy.FuzzyChoice(["connected", "disconnected"]),
            backup_frequency="weekly",
        )

        performance_issues = factory.Trait(
            average_query_time_ms=factory.fuzzy.FuzzyDecimal(500.0, 5000.0, 1),
            slow_queries_count=factory.fuzzy.FuzzyInteger(20, 100),
            cpu_usage_percent=factory.fuzzy.FuzzyDecimal(70.0, 95.0, 1),
            memory_usage_percent=factory.fuzzy.FuzzyDecimal(80.0, 95.0, 1),
        )
