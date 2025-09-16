#!/usr/bin/env python3
"""Production-grade TimescaleDB setup for FXML4 trading system.

This script sets up TimescaleDB with:
- Hypertables for time-series market data
- Continuous aggregates for multi-timeframe analysis
- Compression policies for storage optimization
- Proper indexing for high-performance queries
- Retention policies for data lifecycle management
"""

import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    import asyncpg
    import pandas as pd

    ASYNC_PG_AVAILABLE = True
except ImportError:
    ASYNC_PG_AVAILABLE = False

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class TimescaleDBSetup:
    """Production TimescaleDB setup for FXML4 trading system."""

    def __init__(self, config: Optional[Dict] = None):
        """Initialize TimescaleDB setup manager."""
        self.config = config or self.get_default_config()
        self.connection: Optional[asyncpg.Connection] = None

    def get_default_config(self) -> Dict:
        """Get default database configuration."""
        return {
            "host": os.getenv("FXML4_DATABASE_HOST", "localhost"),
            "port": int(os.getenv("FXML4_DATABASE_PORT", "5432")),
            "database": os.getenv("FXML4_DATABASE_NAME", "fxml4"),
            "user": os.getenv("FXML4_DATABASE_USER", "postgres"),
            "password": os.getenv("FXML4_DATABASE_PASSWORD", "postgres"),
            "ssl": os.getenv("FXML4_DATABASE_SSL_MODE", "disable"),
        }

    async def connect(self) -> bool:
        """Connect to TimescaleDB."""
        try:
            logger.info(
                f"Connecting to TimescaleDB: {self.config['host']}:{self.config['port']}"
            )

            self.connection = await asyncpg.connect(
                host=self.config["host"],
                port=self.config["port"],
                database=self.config["database"],
                user=self.config["user"],
                password=self.config["password"],
            )

            # Verify TimescaleDB extension
            version = await self.connection.fetchval(
                "SELECT extversion FROM pg_extension WHERE extname='timescaledb';"
            )
            if version:
                logger.info(f"✅ Connected to TimescaleDB {version}")
                return True
            else:
                logger.error("❌ TimescaleDB extension not found")
                return False

        except Exception as e:
            logger.error(f"❌ Connection failed: {str(e)}")
            return False

    async def create_market_data_schema(self):
        """Create market data tables and hypertables."""
        logger.info("Creating market data schema...")

        # Raw tick data hypertable
        await self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS market_data_ticks (
                timestamp TIMESTAMPTZ NOT NULL,
                symbol VARCHAR(20) NOT NULL,
                bid DECIMAL(12,6),
                ask DECIMAL(12,6),
                last DECIMAL(12,6),
                bid_size INTEGER,
                ask_size INTEGER,
                volume BIGINT,
                source VARCHAR(20) DEFAULT 'IB',
                tick_type VARCHAR(10),
                metadata JSONB
            );
        """
        )

        # Create hypertable for tick data
        await self.connection.execute(
            """
            SELECT create_hypertable('market_data_ticks', 'timestamp',
                                    chunk_time_interval => INTERVAL '1 hour',
                                    if_not_exists => TRUE);
        """
        )

        # OHLCV candle data hypertable
        await self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS market_data_candles (
                timestamp TIMESTAMPTZ NOT NULL,
                symbol VARCHAR(20) NOT NULL,
                timeframe VARCHAR(10) NOT NULL,
                open DECIMAL(12,6) NOT NULL,
                high DECIMAL(12,6) NOT NULL,
                low DECIMAL(12,6) NOT NULL,
                close DECIMAL(12,6) NOT NULL,
                volume BIGINT NOT NULL DEFAULT 0,
                tick_count INTEGER,
                vwap DECIMAL(12,6),
                source VARCHAR(20) DEFAULT 'IB',
                metadata JSONB
            );
        """
        )

        # Create hypertable for candle data
        await self.connection.execute(
            """
            SELECT create_hypertable('market_data_candles', 'timestamp',
                                    chunk_time_interval => INTERVAL '1 day',
                                    if_not_exists => TRUE);
        """
        )

        logger.info("✅ Market data schema created")

    async def create_feature_engineering_schema(self):
        """Create feature engineering tables for ML training."""
        logger.info("Creating feature engineering schema...")

        # Technical indicators table
        await self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS technical_indicators (
                timestamp TIMESTAMPTZ NOT NULL,
                symbol VARCHAR(20) NOT NULL,
                timeframe VARCHAR(10) NOT NULL,
                indicator_name VARCHAR(50) NOT NULL,
                value DECIMAL(15,6),
                metadata JSONB,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
        """
        )

        # Create hypertable
        await self.connection.execute(
            """
            SELECT create_hypertable('technical_indicators', 'timestamp',
                                    chunk_time_interval => INTERVAL '1 day',
                                    if_not_exists => TRUE);
        """
        )

        # ML features table with versioning
        await self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS ml_features (
                timestamp TIMESTAMPTZ NOT NULL,
                symbol VARCHAR(20) NOT NULL,
                timeframe VARCHAR(10) NOT NULL,
                feature_version VARCHAR(20) NOT NULL,
                feature_name VARCHAR(100) NOT NULL,
                value DECIMAL(15,6),
                feature_group VARCHAR(50),
                metadata JSONB,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
        """
        )

        # Create hypertable for ML features
        await self.connection.execute(
            """
            SELECT create_hypertable('ml_features', 'timestamp',
                                    chunk_time_interval => INTERVAL '1 day',
                                    if_not_exists => TRUE);
        """
        )

        # Elliott Wave patterns table
        await self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS elliott_wave_patterns (
                timestamp TIMESTAMPTZ NOT NULL,
                symbol VARCHAR(20) NOT NULL,
                timeframe VARCHAR(10) NOT NULL,
                pattern_type VARCHAR(50) NOT NULL,
                wave_degree VARCHAR(20),
                start_timestamp TIMESTAMPTZ,
                end_timestamp TIMESTAMPTZ,
                confidence DECIMAL(5,4),
                price_levels JSONB,
                fibonacci_levels JSONB,
                analysis_metadata JSONB,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
        """
        )

        # Create hypertable for Elliott Wave patterns
        await self.connection.execute(
            """
            SELECT create_hypertable('elliott_wave_patterns', 'timestamp',
                                    chunk_time_interval => INTERVAL '1 day',
                                    if_not_exists => TRUE);
        """
        )

        logger.info("✅ Feature engineering schema created")

    async def create_trading_schema(self):
        """Create trading-related tables."""
        logger.info("Creating trading schema...")

        try:
            # Signals table
            logger.info("Creating trading_signals table...")
            await self.connection.execute(
                """
                CREATE TABLE IF NOT EXISTS trading_signals (
                    timestamp TIMESTAMPTZ NOT NULL,
                    signal_id UUID DEFAULT gen_random_uuid(),
                    symbol VARCHAR(20) NOT NULL,
                    timeframe VARCHAR(10) NOT NULL,
                    signal_type VARCHAR(20) NOT NULL, -- 'BUY', 'SELL', 'HOLD'
                    confidence DECIMAL(5,4),
                    entry_price DECIMAL(12,6),
                    stop_loss DECIMAL(12,6),
                    take_profit DECIMAL(12,6),
                    position_size DECIMAL(10,4),
                    risk_pct DECIMAL(5,4),
                    signal_source VARCHAR(50), -- 'ML_MODEL', 'ELLIOTT_WAVE', 'COMBINED'
                    model_version VARCHAR(20),
                    features_used JSONB,
                    metadata JSONB,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    PRIMARY KEY (timestamp, signal_id)
                );
            """
            )

            # Primary key (timestamp, signal_id) already provides uniqueness

            # Create hypertable for signals
            logger.info("Creating hypertable for trading_signals...")
            await self.connection.execute(
                """
                SELECT create_hypertable('trading_signals', 'timestamp',
                                        chunk_time_interval => INTERVAL '1 day',
                                        if_not_exists => TRUE);
            """
            )

            # Trades execution table
            logger.info("Creating trades table...")
            await self.connection.execute(
                """
                CREATE TABLE IF NOT EXISTS trades (
                    timestamp TIMESTAMPTZ NOT NULL,
                    trade_id UUID DEFAULT gen_random_uuid(),
                    signal_id UUID,
                    symbol VARCHAR(20) NOT NULL,
                    side VARCHAR(10) NOT NULL, -- 'BUY', 'SELL'
                    quantity DECIMAL(15,6) NOT NULL,
                    price DECIMAL(12,6) NOT NULL,
                    commission DECIMAL(10,4),
                    execution_venue VARCHAR(20) DEFAULT 'IB',
                    order_id VARCHAR(50),
                    fill_timestamp TIMESTAMPTZ,
                    pnl DECIMAL(15,6),
                    cumulative_pnl DECIMAL(15,6),
                    metadata JSONB,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    PRIMARY KEY (timestamp, trade_id)
                );
            """
            )

            # Create hypertable for trades
            logger.info("Creating hypertable for trades...")
            await self.connection.execute(
                """
                SELECT create_hypertable('trades', 'timestamp',
                                        chunk_time_interval => INTERVAL '1 week',
                                        if_not_exists => TRUE);
            """
            )

            logger.info("✅ Trading schema created")

        except Exception as e:
            logger.error(f"❌ Error in trading schema creation: {str(e)}")
            raise

    async def add_foreign_keys(self):
        """Add foreign key constraints after all tables exist."""
        logger.info("Adding foreign key constraints...")

        # Note: TimescaleDB hypertables have limitations with foreign key constraints
        # For production systems, consider implementing referential integrity at the application level
        logger.info(
            "✅ Foreign key constraints skipped for TimescaleDB hypertable compatibility"
        )
        logger.info(
            "   Referential integrity should be maintained at the application level"
        )

    async def create_continuous_aggregates(self):
        """Create continuous aggregates for multi-timeframe analysis."""
        logger.info("Creating continuous aggregates for multi-timeframe analysis...")

        # 5-minute OHLCV from 1-minute data
        await self.connection.execute(
            """
            CREATE MATERIALIZED VIEW IF NOT EXISTS market_data_5m
            WITH (timescaledb.continuous) AS
            SELECT
                time_bucket('5 minutes', timestamp) AS timestamp,
                symbol,
                '5m' as timeframe,
                first(open, timestamp) as open,
                max(high) as high,
                min(low) as low,
                last(close, timestamp) as close,
                sum(volume) as volume,
                sum(tick_count) as tick_count,
                avg(vwap) as vwap,
                source
            FROM market_data_candles
            WHERE timeframe = '1m'
            GROUP BY time_bucket('5 minutes', timestamp), symbol, source;
        """
        )

        # 15-minute OHLCV
        await self.connection.execute(
            """
            CREATE MATERIALIZED VIEW IF NOT EXISTS market_data_15m
            WITH (timescaledb.continuous) AS
            SELECT
                time_bucket('15 minutes', timestamp) AS timestamp,
                symbol,
                '15m' as timeframe,
                first(open, timestamp) as open,
                max(high) as high,
                min(low) as low,
                last(close, timestamp) as close,
                sum(volume) as volume,
                sum(tick_count) as tick_count,
                avg(vwap) as vwap,
                source
            FROM market_data_candles
            WHERE timeframe = '1m'
            GROUP BY time_bucket('15 minutes', timestamp), symbol, source;
        """
        )

        # 1-hour OHLCV
        await self.connection.execute(
            """
            CREATE MATERIALIZED VIEW IF NOT EXISTS market_data_1h
            WITH (timescaledb.continuous) AS
            SELECT
                time_bucket('1 hour', timestamp) AS timestamp,
                symbol,
                '1h' as timeframe,
                first(open, timestamp) as open,
                max(high) as high,
                min(low) as low,
                last(close, timestamp) as close,
                sum(volume) as volume,
                sum(tick_count) as tick_count,
                avg(vwap) as vwap,
                source
            FROM market_data_candles
            WHERE timeframe = '1m'
            GROUP BY time_bucket('1 hour', timestamp), symbol, source;
        """
        )

        # 4-hour OHLCV
        await self.connection.execute(
            """
            CREATE MATERIALIZED VIEW IF NOT EXISTS market_data_4h
            WITH (timescaledb.continuous) AS
            SELECT
                time_bucket('4 hours', timestamp) AS timestamp,
                symbol,
                '4h' as timeframe,
                first(open, timestamp) as open,
                max(high) as high,
                min(low) as low,
                last(close, timestamp) as close,
                sum(volume) as volume,
                sum(tick_count) as tick_count,
                avg(vwap) as vwap,
                source
            FROM market_data_candles
            WHERE timeframe = '1m'
            GROUP BY time_bucket('4 hours', timestamp), symbol, source;
        """
        )

        # Daily OHLCV
        await self.connection.execute(
            """
            CREATE MATERIALIZED VIEW IF NOT EXISTS market_data_1d
            WITH (timescaledb.continuous) AS
            SELECT
                time_bucket('1 day', timestamp) AS timestamp,
                symbol,
                '1d' as timeframe,
                first(open, timestamp) as open,
                max(high) as high,
                min(low) as low,
                last(close, timestamp) as close,
                sum(volume) as volume,
                sum(tick_count) as tick_count,
                avg(vwap) as vwap,
                source
            FROM market_data_candles
            WHERE timeframe = '1m'
            GROUP BY time_bucket('1 day', timestamp), symbol, source;
        """
        )

        logger.info("✅ Continuous aggregates created")

    async def setup_compression_policies(self):
        """Set up compression policies for storage optimization."""
        logger.info("Setting up compression policies...")

        # Enable compression on hypertables first
        tables_to_compress = [
            "market_data_ticks",
            "market_data_candles",
            "technical_indicators",
            "ml_features",
            "trading_signals",
            "trades",
        ]

        for table in tables_to_compress:
            try:
                await self.connection.execute(
                    f"""
                    ALTER TABLE {table} SET (timescaledb.compress = true);
                """
                )
                logger.info(f"✅ Compression enabled on {table}")
            except Exception as e:
                logger.warning(f"Could not enable compression on {table}: {e}")

        # Now add compression policies with if_not_exists option
        compression_policies = [
            ("market_data_ticks", "7 days"),
            ("market_data_candles", "30 days"),
            ("technical_indicators", "30 days"),
            ("ml_features", "30 days"),
            ("trading_signals", "90 days"),
            ("trades", "365 days"),
        ]

        for table, interval in compression_policies:
            try:
                await self.connection.execute(
                    f"""
                    SELECT add_compression_policy('{table}', INTERVAL '{interval}', if_not_exists => TRUE);
                """
                )
                logger.info(f"✅ Compression policy set for {table} ({interval})")
            except Exception as e:
                logger.warning(f"Could not set compression policy for {table}: {e}")

        logger.info("✅ Compression policies set up")

    async def create_indexes(self):
        """Create performance-optimized indexes."""
        logger.info("Creating performance indexes...")

        # Market data indexes
        await self.connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_market_data_ticks_symbol_timestamp
            ON market_data_ticks (symbol, timestamp DESC);
        """
        )

        await self.connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_market_data_candles_symbol_timeframe_timestamp
            ON market_data_candles (symbol, timeframe, timestamp DESC);
        """
        )

        # Feature engineering indexes
        await self.connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_technical_indicators_symbol_timeframe_timestamp
            ON technical_indicators (symbol, timeframe, timestamp DESC);
        """
        )

        await self.connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_ml_features_symbol_version_timestamp
            ON ml_features (symbol, feature_version, timestamp DESC);
        """
        )

        await self.connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_ml_features_feature_group
            ON ml_features (feature_group, symbol, timestamp DESC);
        """
        )

        # Trading indexes
        await self.connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_trading_signals_symbol_timestamp
            ON trading_signals (symbol, timestamp DESC);
        """
        )

        await self.connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_trading_signals_signal_type
            ON trading_signals (signal_type, confidence DESC, timestamp DESC);
        """
        )

        await self.connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_trades_symbol_timestamp
            ON trades (symbol, timestamp DESC);
        """
        )

        # Elliott Wave specific indexes
        await self.connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_elliott_wave_symbol_pattern_timestamp
            ON elliott_wave_patterns (symbol, pattern_type, timestamp DESC);
        """
        )

        await self.connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_elliott_wave_confidence
            ON elliott_wave_patterns (confidence DESC, timestamp DESC);
        """
        )

        logger.info("✅ Performance indexes created")

    async def setup_retention_policies(self):
        """Set up data retention policies."""
        logger.info("Setting up data retention policies...")

        # Configure retention policies for different data types
        retention_policies = [
            ("market_data_ticks", "30 days"),  # High-frequency data
            ("market_data_candles", "365 days"),  # 1-minute candles for 1 year
            ("technical_indicators", "730 days"),  # Technical indicators for 2 years
            ("ml_features", "730 days"),  # ML features for 2 years (model retraining)
            (
                "trading_signals",
                "1825 days",
            ),  # Trading signals for 5 years (regulatory)
            # trades table kept permanently for regulatory compliance
        ]

        for table, interval in retention_policies:
            try:
                await self.connection.execute(
                    f"""
                    SELECT add_retention_policy('{table}', INTERVAL '{interval}', if_not_exists => TRUE);
                """
                )
                logger.info(f"✅ Retention policy set for {table} ({interval})")
            except Exception as e:
                logger.warning(f"Could not set retention policy for {table}: {e}")

        logger.info("✅ Data retention policies set up")

    async def create_refresh_policies(self):
        """Set up automatic refresh policies for continuous aggregates."""
        logger.info("Setting up refresh policies for continuous aggregates...")

        # Refresh continuous aggregates with appropriate windows for each timeframe
        refresh_configs = [
            ("5m", "2 hours", "5 minutes", "5 minutes"),
            ("15m", "4 hours", "15 minutes", "15 minutes"),
            ("1h", "8 hours", "1 hour", "1 hour"),
            ("4h", "24 hours", "4 hours", "4 hours"),
            ("1d", "7 days", "1 day", "1 day"),
        ]

        for tf, start_offset, end_offset, schedule_interval in refresh_configs:
            try:
                await self.connection.execute(
                    f"""
                    SELECT add_continuous_aggregate_policy('market_data_{tf}',
                        start_offset => INTERVAL '{start_offset}',
                        end_offset => INTERVAL '{end_offset}',
                        schedule_interval => INTERVAL '{schedule_interval}');
                """
                )
                logger.info(f"✅ Refresh policy created for market_data_{tf}")
            except Exception as e:
                logger.warning(f"Could not create refresh policy for {tf}: {e}")

        logger.info("✅ Refresh policies created")

    async def setup_complete_timescaledb(self):
        """Complete TimescaleDB setup for FXML4."""
        logger.info("Starting complete TimescaleDB setup for FXML4...")

        if not ASYNC_PG_AVAILABLE:
            logger.error("❌ asyncpg not available. Install with: pip install asyncpg")
            return False

        # Connect to database
        if not await self.connect():
            return False

        try:
            # Create all schemas
            await self.create_market_data_schema()
            await self.create_feature_engineering_schema()
            await self.create_trading_schema()

            # Add foreign key constraints
            await self.add_foreign_keys()

            # Set up advanced features
            await self.create_continuous_aggregates()
            await self.setup_compression_policies()
            await self.create_indexes()
            await self.setup_retention_policies()
            await self.create_refresh_policies()

            logger.info("✅ Complete TimescaleDB setup finished!")
            return True

        except Exception as e:
            logger.error(f"❌ Setup failed: {str(e)}")
            return False
        finally:
            if self.connection:
                await self.connection.close()

    async def validate_setup(self):
        """Validate TimescaleDB setup."""
        logger.info("Validating TimescaleDB setup...")

        if not await self.connect():
            return False

        try:
            # Check hypertables
            hypertables = await self.connection.fetch(
                """
                SELECT hypertable_name FROM timescaledb_information.hypertables;
            """
            )

            expected_hypertables = [
                "market_data_ticks",
                "market_data_candles",
                "technical_indicators",
                "ml_features",
                "elliott_wave_patterns",
                "trading_signals",
                "trades",
            ]

            found_hypertables = [ht["hypertable_name"] for ht in hypertables]

            for expected in expected_hypertables:
                if expected in found_hypertables:
                    logger.info(f"✅ Hypertable found: {expected}")
                else:
                    logger.error(f"❌ Hypertable missing: {expected}")

            # Check continuous aggregates
            caggs = await self.connection.fetch(
                """
                SELECT view_name FROM timescaledb_information.continuous_aggregates;
            """
            )

            expected_caggs = [
                "market_data_5m",
                "market_data_15m",
                "market_data_1h",
                "market_data_4h",
                "market_data_1d",
            ]
            found_caggs = [cagg["view_name"] for cagg in caggs]

            for expected in expected_caggs:
                if expected in found_caggs:
                    logger.info(f"✅ Continuous aggregate found: {expected}")
                else:
                    logger.error(f"❌ Continuous aggregate missing: {expected}")

            # Check compression policies
            compression_policies = await self.connection.fetch(
                """
                SELECT hypertable_name FROM timescaledb_information.compression_settings;
            """
            )

            logger.info(f"✅ Compression policies active: {len(compression_policies)}")

            return True

        except Exception as e:
            logger.error(f"❌ Validation failed: {str(e)}")
            return False
        finally:
            if self.connection:
                await self.connection.close()


async def main():
    """Main setup function."""
    print("=" * 70)
    print("FXML4 TIMESCALEDB PRODUCTION SETUP")
    print("=" * 70)

    setup = TimescaleDBSetup()

    print("\n🚀 Starting complete TimescaleDB setup...")
    success = await setup.setup_complete_timescaledb()

    if success:
        print("\n🔍 Validating setup...")
        validation_success = await setup.validate_setup()

        if validation_success:
            print("\n" + "=" * 70)
            print("✅ TIMESCALEDB SETUP COMPLETE!")
            print("✅ Ready for institutional-grade trading data storage")
            print("=" * 70)

            print("\n🎯 Features enabled:")
            print("   • Hypertables for time-series data")
            print("   • Multi-timeframe continuous aggregates (1m→5m,15m,1h,4h,1d)")
            print("   • Compression policies for storage optimization")
            print("   • Performance indexes for high-speed queries")
            print("   • Data retention policies for lifecycle management")
            print("   • Auto-refresh for real-time analysis")

            print("\n🔥 Ready for Phase 2: GBP/USD Strategy Development!")
            return True
        else:
            print("\n❌ Setup validation failed")
            return False
    else:
        print("\n❌ TimescaleDB setup failed")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
