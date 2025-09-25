#!/usr/bin/env python3
"""
FXML4 Phase 3 Integration Demo
=============================

Comprehensive demonstration of Phase 3: Data Pipeline & Market Integration features:

1. Real-time data feed integration (Alpha Vantage + Polygon)
2. Enhanced WebSocket broadcasting
3. TimescaleDB optimization and storage
4. Data feed manager with failover
5. Performance monitoring and metrics

This demo showcases the complete data pipeline from external feeds
to real-time WebSocket broadcasting with database persistence.

Usage:
    python examples/phase3_integration_demo.py

Requirements:
    - Valid Alpha Vantage API key (set ALPHA_VANTAGE_API_KEY env var)
    - Valid Polygon.io API key (set POLYGON_API_KEY env var) [optional]
    - Running PostgreSQL/TimescaleDB instance
    - Install dependencies: pip install -r requirements.txt
"""

import asyncio
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict

# Add project root to path
sys.path.insert(0, os.path.abspath("."))

from core.api.enhanced_websocket_manager import (
    EnhancedWebSocketManager,
    MessageType,
    WebSocketMessage,
)
from core.data_engineering.timescaledb_optimizer import TimescaleDBOptimizer
from core.data_feeds.alpha_vantage_feed import AlphaVantageDataFeed

# Import our Phase 3 components
from core.data_feeds.feed_manager import DataFeedManager
from core.data_feeds.polygon_feed import PolygonDataFeed

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("phase3_demo.log")],
)

logger = logging.getLogger(__name__)


class Phase3IntegrationDemo:
    """
    Comprehensive demo of Phase 3 integration components.

    This demo creates a complete data pipeline that:
    1. Connects to multiple market data providers
    2. Streams real-time data via WebSocket
    3. Stores data in optimized TimescaleDB
    4. Provides performance monitoring
    """

    def __init__(self):
        self.data_feed_manager: DataFeedManager = None
        self.websocket_manager: EnhancedWebSocketManager = None
        self.db_optimizer: TimescaleDBOptimizer = None

        # Configuration
        self.symbols = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF"]
        self.websocket_port = 8765
        self.db_connection_string = self._get_db_connection_string()

        # Performance metrics
        self.demo_start_time = datetime.now(timezone.utc)
        self.messages_processed = 0
        self.websocket_messages_sent = 0

    def _get_db_connection_string(self) -> str:
        """Get database connection string from environment or use defaults."""
        host = os.getenv("DB_HOST", "localhost")
        port = os.getenv("DB_PORT", "5432")
        database = os.getenv("DB_NAME", "fxml4")
        user = os.getenv("DB_USER", "postgres")
        password = os.getenv("DB_PASSWORD", "dev-postgres-secure-password")

        return f"postgresql://{user}:{password}@{host}:{port}/{database}"

    def _create_data_feed_configs(self) -> list:
        """Create data feed configurations."""
        configs = []

        # Alpha Vantage configuration
        alpha_vantage_key = os.getenv("ALPHA_VANTAGE_API_KEY")
        if alpha_vantage_key:
            configs.append(
                {
                    "name": "alpha_vantage_primary",
                    "type": "alpha_vantage",
                    "config": {
                        "api_key": alpha_vantage_key,
                        "rate_limit": 5,  # Free tier limit
                        "polling_interval": 60,
                        "health_check_interval": 120,
                    },
                    "priority": 1,  # Primary feed
                    "enabled": True,
                    "symbols": self.symbols,
                    "max_failures": 3,
                    "failure_window_minutes": 10,
                }
            )
            logger.info("✅ Alpha Vantage feed configured")
        else:
            logger.warning(
                "⚠️ ALPHA_VANTAGE_API_KEY not set, skipping Alpha Vantage feed"
            )

        # Polygon.io configuration (optional)
        polygon_key = os.getenv("POLYGON_API_KEY")
        if polygon_key:
            configs.append(
                {
                    "name": "polygon_secondary",
                    "type": "polygon",
                    "config": {
                        "api_key": polygon_key,
                        "rate_limit": 100,  # Conservative default
                    },
                    "priority": 2,  # Secondary feed
                    "enabled": True,
                    "symbols": self.symbols,
                    "max_failures": 5,
                    "failure_window_minutes": 15,
                }
            )
            logger.info("✅ Polygon.io feed configured")
        else:
            logger.info("ℹ️ POLYGON_API_KEY not set, using Alpha Vantage only")

        if not configs:
            raise ValueError(
                "❌ No API keys configured. Set ALPHA_VANTAGE_API_KEY or POLYGON_API_KEY"
            )

        return configs

    async def initialize_components(self) -> bool:
        """Initialize all Phase 3 components."""
        logger.info("🚀 Initializing Phase 3 Integration Demo...")

        try:
            # 1. Initialize TimescaleDB Optimizer
            logger.info("📊 Initializing TimescaleDB Optimizer...")
            db_config = {
                "target_insert_throughput": 50000,
                "target_query_latency_ms": 10,
                "target_compression_ratio": 0.3,
            }

            self.db_optimizer = TimescaleDBOptimizer(
                self.db_connection_string, db_config
            )

            db_success = await self.db_optimizer.initialize()
            if not db_success:
                logger.error("❌ Failed to initialize TimescaleDB optimizer")
                return False

            logger.info("✅ TimescaleDB optimizer initialized")

            # 2. Initialize Data Feed Manager
            logger.info("📡 Initializing Data Feed Manager...")
            feed_configs = self._create_data_feed_configs()

            manager_config = {"health_check_interval": 60, "metrics_interval": 120}

            self.data_feed_manager = DataFeedManager(manager_config)

            feed_success = await self.data_feed_manager.initialize(feed_configs)
            if not feed_success:
                logger.error("❌ Failed to initialize data feed manager")
                return False

            logger.info("✅ Data feed manager initialized")

            # 3. Initialize Enhanced WebSocket Manager
            logger.info("🔌 Initializing Enhanced WebSocket Manager...")
            websocket_config = {
                "host": "0.0.0.0",
                "port": self.websocket_port,
                "max_connections": 1000,  # Reduced for demo
                "compression": "zlib",
            }

            self.websocket_manager = EnhancedWebSocketManager(websocket_config)

            websocket_success = await self.websocket_manager.start()
            if not websocket_success:
                logger.error("❌ Failed to start WebSocket manager")
                return False

            logger.info(f"✅ WebSocket server started on port {self.websocket_port}")

            # 4. Set up data pipeline connections
            await self._setup_data_pipeline()

            logger.info("✅ All Phase 3 components initialized successfully!")
            return True

        except Exception as e:
            logger.error(f"❌ Initialization failed: {e}")
            return False

    async def _setup_data_pipeline(self):
        """Set up the complete data pipeline from feeds to WebSocket broadcast."""
        logger.info("🔗 Setting up data pipeline...")

        async def handle_real_time_data(tick_data):
            """Handle incoming real-time tick data."""
            try:
                self.messages_processed += 1

                # Store in database (simplified for demo)
                logger.debug(
                    f"📥 Processing tick: {tick_data.symbol} @ {tick_data.last}"
                )

                # Broadcast via WebSocket
                await self.websocket_manager.broadcast_tick_data(
                    symbol=tick_data.symbol,
                    tick_data={
                        "symbol": tick_data.symbol,
                        "bid": tick_data.bid,
                        "ask": tick_data.ask,
                        "last": tick_data.last,
                        "timestamp": (
                            tick_data.timestamp.isoformat()
                            if tick_data.timestamp
                            else None
                        ),
                        "source": tick_data.source,
                    },
                )

                self.websocket_messages_sent += 1

            except Exception as e:
                logger.error(f"❌ Error processing tick data: {e}")

        # Subscribe to real-time data for all symbols
        subscription_results = await self.data_feed_manager.subscribe_real_time(
            symbols=self.symbols, callback=handle_real_time_data
        )

        successful_subscriptions = sum(
            1 for success in subscription_results.values() if success
        )
        logger.info(
            f"✅ Data pipeline setup complete: {successful_subscriptions}/{len(self.symbols)} symbols subscribed"
        )

    async def run_demo_cycle(self):
        """Run the main demo cycle with periodic updates and monitoring."""
        logger.info("🔄 Starting demo cycle...")

        cycle_count = 0

        try:
            while True:
                cycle_count += 1
                logger.info(f"📊 Demo Cycle #{cycle_count}")

                # 1. Get real-time quotes for demonstration
                for symbol in self.symbols[:2]:  # Limit to avoid rate limits
                    try:
                        quote = await self.data_feed_manager.get_real_time_quote(symbol)
                        if quote:
                            logger.info(
                                f"💹 {symbol}: {quote.last} (from {quote.source})"
                            )
                        else:
                            logger.warning(f"⚠️ No quote available for {symbol}")
                    except Exception as e:
                        logger.error(f"❌ Error getting quote for {symbol}: {e}")

                # 2. Display performance metrics
                await self._display_performance_metrics()

                # 3. Check system health
                await self._check_system_health()

                # 4. Wait before next cycle
                logger.info(f"⏱️ Waiting 60 seconds before next cycle...")
                await asyncio.sleep(60)

        except KeyboardInterrupt:
            logger.info("⏹️ Demo interrupted by user")
        except Exception as e:
            logger.error(f"❌ Demo cycle error: {e}")

    async def _display_performance_metrics(self):
        """Display comprehensive performance metrics."""
        logger.info("📈 Performance Metrics:")

        # Data feed manager statistics
        feed_stats = self.data_feed_manager.get_feed_statistics()
        for feed_name, stats in feed_stats.items():
            logger.info(
                f"  📡 {feed_name}: {stats['success_rate_percent']:.1f}% success, "
                f"{stats['avg_response_time_ms']:.0f}ms avg"
            )

        # WebSocket manager statistics
        ws_stats = self.websocket_manager.get_performance_stats()
        logger.info(
            f"  🔌 WebSocket: {ws_stats['active_connections']} connections, "
            f"{ws_stats['messages_per_second']:.1f} msg/s"
        )

        # Database performance (if available)
        try:
            db_metrics = await self.db_optimizer.get_performance_metrics()
            if db_metrics.get("database_metrics"):
                cache_hit_ratio = db_metrics["database_metrics"].get(
                    "cache_hit_ratio", 0
                )
                logger.info(f"  🗄️ Database: {cache_hit_ratio:.1f}% cache hit ratio")
        except Exception as e:
            logger.debug(f"Database metrics unavailable: {e}")

        # Demo-specific metrics
        uptime = (datetime.now(timezone.utc) - self.demo_start_time).total_seconds()
        logger.info(
            f"  ⏱️ Demo: {uptime:.0f}s uptime, {self.messages_processed} messages processed, "
            f"{self.websocket_messages_sent} WebSocket broadcasts"
        )

    async def _check_system_health(self):
        """Check health of all system components."""
        logger.info("🏥 System Health Check:")

        # Check data feed manager health
        active_feeds = self.data_feed_manager.get_active_feeds()
        failed_feeds = self.data_feed_manager.get_failed_feeds()

        if active_feeds:
            logger.info(f"  ✅ Data Feeds: {len(active_feeds)} active")
        if failed_feeds:
            logger.warning(
                f"  ⚠️ Data Feeds: {len(failed_feeds)} failed - {failed_feeds}"
            )

        # Check WebSocket health
        if self.websocket_manager.is_running:
            logger.info(
                f"  ✅ WebSocket: Running with {self.websocket_manager.active_connections} connections"
            )
        else:
            logger.error("  ❌ WebSocket: Not running")

        # Check database connectivity
        try:
            db_metrics = await self.db_optimizer.get_performance_metrics()
            if db_metrics:
                logger.info("  ✅ Database: Connected and responsive")
            else:
                logger.warning("  ⚠️ Database: Connected but no metrics available")
        except Exception as e:
            logger.error(f"  ❌ Database: Connection issues - {e}")

    async def get_historical_data_demo(self):
        """Demonstrate historical data retrieval."""
        logger.info("📚 Historical Data Demo:")

        for symbol in self.symbols[:1]:  # Test with one symbol to avoid rate limits
            try:
                historical_data = await self.data_feed_manager.get_historical_data(
                    symbol=symbol, timeframe="1d", limit=5
                )

                if historical_data:
                    logger.info(
                        f"  📊 {symbol}: Retrieved {len(historical_data)} daily candles"
                    )
                    latest = historical_data[0]
                    logger.info(
                        f"    Latest: {latest.timestamp.strftime('%Y-%m-%d')} "
                        f"OHLC: {latest.open}/{latest.high}/{latest.low}/{latest.close}"
                    )
                else:
                    logger.warning(f"  ⚠️ No historical data for {symbol}")

            except Exception as e:
                logger.error(f"  ❌ Historical data error for {symbol}: {e}")

    async def cleanup(self):
        """Cleanup all resources."""
        logger.info("🧹 Cleaning up resources...")

        try:
            # Stop data feed manager
            if self.data_feed_manager:
                await self.data_feed_manager.shutdown()
                logger.info("✅ Data feed manager stopped")

            # Stop WebSocket manager
            if self.websocket_manager:
                await self.websocket_manager.stop()
                logger.info("✅ WebSocket manager stopped")

            # Close database connections
            if self.db_optimizer:
                await self.db_optimizer.close()
                logger.info("✅ Database connections closed")

        except Exception as e:
            logger.error(f"❌ Cleanup error: {e}")

        logger.info("✅ Cleanup complete")

    async def run(self):
        """Run the complete Phase 3 integration demo."""
        print("=" * 80)
        print("🚀 FXML4 PHASE 3 INTEGRATION DEMO")
        print("=" * 80)
        print()
        print("This demo showcases:")
        print("• Real-time data feed integration (Alpha Vantage + Polygon)")
        print("• Enhanced WebSocket broadcasting")
        print("• TimescaleDB optimization and storage")
        print("• Data feed manager with failover")
        print("• Performance monitoring and metrics")
        print()
        print(
            f"WebSocket server will be available at: ws://localhost:{self.websocket_port}"
        )
        print("Press Ctrl+C to stop the demo")
        print()

        try:
            # Initialize all components
            success = await self.initialize_components()
            if not success:
                logger.error("❌ Failed to initialize demo components")
                return

            # Run historical data demo
            await self.get_historical_data_demo()

            # Start the main demo cycle
            await self.run_demo_cycle()

        except KeyboardInterrupt:
            logger.info("🛑 Demo stopped by user")
        except Exception as e:
            logger.error(f"❌ Demo failed: {e}")
        finally:
            await self.cleanup()

        print("\n" + "=" * 80)
        print("✅ FXML4 PHASE 3 INTEGRATION DEMO COMPLETE")
        print("=" * 80)


def print_setup_instructions():
    """Print setup instructions for the demo."""
    print("📋 SETUP INSTRUCTIONS")
    print("-" * 40)
    print()
    print("Before running this demo, please ensure:")
    print()
    print("1. Environment Variables:")
    print("   export ALPHA_VANTAGE_API_KEY='your_alpha_vantage_key'")
    print("   export POLYGON_API_KEY='your_polygon_key'  # Optional")
    print()
    print("2. Database Setup:")
    print("   • PostgreSQL with TimescaleDB extension running")
    print(
        "   • Default connection: postgresql://postgres:dev-postgres-secure-password@localhost:5432/fxml4"
    )
    print(
        "   • Or set DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD environment variables"
    )
    print()
    print("3. Dependencies:")
    print("   pip install -r requirements.txt")
    print("   pip install -r docs-requirements.txt")
    print()
    print("4. API Keys:")
    print("   • Alpha Vantage: https://www.alphavantage.co/support/#api-key")
    print("   • Polygon.io: https://polygon.io/ (optional, for enhanced features)")
    print()


async def main():
    """Main entry point for the demo."""
    import argparse

    parser = argparse.ArgumentParser(description="FXML4 Phase 3 Integration Demo")
    parser.add_argument("--setup", action="store_true", help="Show setup instructions")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    if args.setup:
        print_setup_instructions()
        return

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Check for required environment variables
    if not os.getenv("ALPHA_VANTAGE_API_KEY") and not os.getenv("POLYGON_API_KEY"):
        print("❌ Error: No API keys configured!")
        print("Run with --setup flag for setup instructions")
        print()
        print("Quick start:")
        print("export ALPHA_VANTAGE_API_KEY='your_key_here'")
        print("python examples/phase3_integration_demo.py")
        return

    # Run the demo
    demo = Phase3IntegrationDemo()
    await demo.run()


if __name__ == "__main__":
    asyncio.run(main())
