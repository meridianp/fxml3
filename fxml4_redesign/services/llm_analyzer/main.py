"""LLM Analyzer Service - GPT-4V chart analysis and signal validation."""

import asyncio
import sys
from pathlib import Path

# Add parent directories to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import base64
import io
import json
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from chart_generator import MultiTimeframeChartGenerator
from llm_client import LLMClient
from shared.config.rabbitmq_config import (
    Exchanges,
    MessagePriority,
    Queues,
    RoutingKeys,
    format_routing_key,
)
from shared.utils.base_service import BaseService, ServiceConfig
from signal_validator import SignalValidator


class LLMAnalyzerService(BaseService):
    """LLM-powered signal analysis and validation service."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__("llm-analyzer", config)

        # Core components
        self.chart_generator = MultiTimeframeChartGenerator()
        self.llm_client = LLMClient()
        self.signal_validator = SignalValidator()

        # Processing queues
        self.validation_queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self.priority_queue: asyncio.Queue = asyncio.Queue(maxsize=50)

        # Configuration
        self.max_concurrent_analyses = 3
        self.chart_cache_ttl = 300  # 5 minutes
        self.cost_optimization = True

        # Performance tracking
        self.analyses_completed = 0
        self.total_cost = 0.0
        self.processing_times = []
        self.validation_cache = {}

        # Rate limiting
        self.last_llm_call = {}
        self.min_interval_between_calls = 10  # seconds

    async def service_setup(self):
        """Set up LLM analyzer service."""
        # Initialize LLM client
        await self.llm_client.initialize()

        # Initialize chart generator
        await self.chart_generator.initialize()

        # Set up RabbitMQ
        await self.setup_rabbitmq()

        # Load validation cache
        await self.load_validation_cache()

        self.logger.info("LLM Analyzer service initialized")

    async def service_teardown(self):
        """Clean up resources."""
        # Save validation cache
        await self.save_validation_cache()

        # Close LLM client
        await self.llm_client.close()

    async def service_run(self):
        """Main service loop."""
        # Start processing tasks
        self.add_task(self.signal_consumer())
        self.add_task(self.priority_signal_consumer())

        # Start worker tasks for concurrent processing
        for i in range(self.max_concurrent_analyses):
            self.add_task(self.analysis_worker(f"worker-{i}"))

        self.add_task(self.cache_cleanup_loop())
        self.add_task(self.heartbeat_loop())

        # Wait for shutdown
        while self.running:
            await asyncio.sleep(1)

    async def setup_rabbitmq(self):
        """Set up RabbitMQ exchanges and queues."""
        # Declare exchanges
        await self.rabbitmq_channel.declare_exchange(
            Exchanges.SIGNALS, type="topic", durable=True
        )

        # Declare validation queue
        await self.rabbitmq_channel.declare_queue(
            Queues.SIGNAL_VALIDATION,
            durable=True,
            arguments={"x-max-priority": 10, "x-message-ttl": 300000},  # 5 minutes
        )

        self.logger.info("RabbitMQ setup complete")

    async def signal_consumer(self):
        """Consume signals for validation from RabbitMQ."""
        queue = await self.rabbitmq_channel.get_queue(Queues.SIGNAL_VALIDATION)

        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process():
                    try:
                        signal_data = json.loads(message.body.decode())

                        # Check priority
                        priority = message.priority or MessagePriority.NORMAL

                        if priority >= MessagePriority.HIGH:
                            # High priority - process immediately
                            await self.priority_queue.put(signal_data)
                        else:
                            # Normal priority - add to regular queue
                            await self.validation_queue.put(signal_data)

                    except Exception as e:
                        self.logger.error(f"Error processing signal message: {e}")
                        await self.log_error(e, {"message": str(message.body)})

    async def priority_signal_consumer(self):
        """Consumer for high-priority signals."""
        while self.running:
            try:
                # Process priority signals immediately
                signal_data = await asyncio.wait_for(
                    self.priority_queue.get(), timeout=1.0
                )

                # Process immediately (bypass worker queue)
                await self.analyze_signal(signal_data, priority=True)

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                self.logger.error(f"Error in priority consumer: {e}")
                await asyncio.sleep(1)

    async def analysis_worker(self, worker_id: str):
        """Worker task for signal analysis."""
        self.logger.info(f"Analysis worker {worker_id} started")

        while self.running:
            try:
                # Get signal from queue
                signal_data = await asyncio.wait_for(
                    self.validation_queue.get(), timeout=5.0
                )

                # Analyze signal
                await self.analyze_signal(signal_data, worker_id=worker_id)

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                self.logger.error(f"Error in worker {worker_id}: {e}")
                await asyncio.sleep(1)

    async def analyze_signal(
        self, signal_data: Dict[str, Any], priority: bool = False, worker_id: str = None
    ):
        """Analyze a trading signal using LLM.

        Args:
            signal_data: Signal data to analyze
            priority: Whether this is a high-priority signal
            worker_id: ID of the worker processing this signal
        """
        start_time = datetime.utcnow()

        try:
            symbol = signal_data.get("symbol")
            signal_id = signal_data.get("signal_id")

            if not symbol:
                self.logger.warning("Signal missing symbol")
                return

            # Check if we've analyzed this signal recently (cost optimization)
            cache_key = self._get_cache_key(signal_data)

            if not priority and cache_key in self.validation_cache:
                cached_result = self.validation_cache[cache_key]
                if self._is_cache_valid(cached_result):
                    self.logger.debug(f"Using cached validation for {symbol}")
                    await self.publish_validation_result(signal_data, cached_result)
                    return

            # Rate limiting check
            if await self._should_rate_limit(symbol, priority):
                self.logger.info(f"Rate limiting LLM call for {symbol}")
                # Use cached analysis or simplified validation
                result = await self.signal_validator.simple_validation(signal_data)
                await self.publish_validation_result(signal_data, result)
                return

            self.logger.info(f"Analyzing signal for {symbol} (worker: {worker_id})")

            # Get market data for chart generation
            market_data = await self.get_market_data_for_analysis(symbol)

            if not market_data:
                self.logger.warning(f"No market data available for {symbol}")
                return

            # Generate multi-timeframe chart
            chart_image = await self.chart_generator.generate_signal_chart(
                symbol, signal_data, market_data
            )

            # Perform LLM analysis
            validation_result = await self.llm_client.validate_trading_signal(
                signal_data, chart_image, market_data
            )

            # Enhance validation with technical analysis
            enhanced_result = await self.signal_validator.enhance_validation(
                signal_data, validation_result, market_data
            )

            # Cache result
            if not priority:  # Don't cache priority signals
                self.validation_cache[cache_key] = {
                    "result": enhanced_result,
                    "timestamp": datetime.utcnow(),
                    "ttl": self.chart_cache_ttl,
                }

            # Store validation in database
            await self.store_validation_result(signal_data, enhanced_result)

            # Publish result
            await self.publish_validation_result(signal_data, enhanced_result)

            # Update metrics
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            self.processing_times.append(processing_time)
            self.analyses_completed += 1

            # Track costs
            estimated_cost = self._estimate_analysis_cost(signal_data, enhanced_result)
            self.total_cost += estimated_cost

            # Update rate limiting
            self.last_llm_call[symbol] = datetime.utcnow()

            self.logger.info(
                f"Completed analysis for {symbol}: "
                f"valid={enhanced_result.get('valid')}, "
                f"confidence={enhanced_result.get('enhanced_confidence', 0):.2f}, "
                f"time={processing_time:.2f}s"
            )

            # Log analysis event
            await self.log_event(
                "signal_validation",
                f"Validated {symbol} signal",
                {
                    "symbol": symbol,
                    "signal_id": signal_id,
                    "valid": enhanced_result.get("valid"),
                    "llm_confidence": enhanced_result.get("llm_confidence"),
                    "enhanced_confidence": enhanced_result.get("enhanced_confidence"),
                    "processing_time": processing_time,
                    "estimated_cost": estimated_cost,
                    "worker_id": worker_id,
                    "priority": priority,
                },
            )

        except Exception as e:
            self.logger.error(f"Error analyzing signal: {e}")
            await self.log_error(
                e,
                {
                    "signal_data": signal_data,
                    "worker_id": worker_id,
                    "priority": priority,
                },
            )

            # Send fallback validation
            fallback_result = await self.signal_validator.fallback_validation(
                signal_data
            )
            await self.publish_validation_result(signal_data, fallback_result)

    async def get_market_data_for_analysis(
        self, symbol: str
    ) -> Optional[Dict[str, Any]]:
        """Get market data needed for analysis.

        Args:
            symbol: Trading symbol

        Returns:
            Market data for multiple timeframes
        """
        try:
            # Check cache first
            cache_key = f"market_data_analysis:{symbol}"
            cached_data = await self.cache_json_get(cache_key)

            if cached_data and self._is_market_data_fresh(cached_data):
                return cached_data

            # Fetch from database
            timeframes = ["D", "4H", "1H", "15m"]
            market_data = {"symbol": symbol, "timeframes": {}}

            async with self.db_pool.acquire() as conn:
                for tf in timeframes:
                    # Get price data
                    table_name = (
                        f"market_data_{tf.lower()}" if tf != "D" else "market_data_1d"
                    )

                    price_rows = await conn.fetch(
                        f"""
                        SELECT bucket as time, open, high, low, close, volume
                        FROM trading.{table_name}
                        WHERE symbol = $1
                        ORDER BY bucket DESC
                        LIMIT 100
                    """,
                        symbol,
                    )

                    # Get indicators
                    indicator_rows = await conn.fetch(
                        """
                        SELECT time, rsi_14, atr_14, sma_20, sma_50, sma_200,
                               ema_9, ema_21, bb_upper, bb_middle, bb_lower,
                               macd_line, macd_signal, macd_histogram
                        FROM trading.indicators
                        WHERE symbol = $1 AND timeframe = $2
                        ORDER BY time DESC
                        LIMIT 100
                    """,
                        symbol,
                        tf,
                    )

                    if price_rows and indicator_rows:
                        market_data["timeframes"][tf] = {
                            "prices": [dict(row) for row in price_rows],
                            "indicators": [dict(row) for row in indicator_rows],
                        }

            # Cache the data
            await self.cache_json_set(cache_key, market_data, ttl=60)  # 1 minute

            return market_data

        except Exception as e:
            self.logger.error(f"Error getting market data for {symbol}: {e}")
            return None

    async def store_validation_result(
        self, signal_data: Dict[str, Any], validation_result: Dict[str, Any]
    ):
        """Store validation result in database."""
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO trading.llm_validations
                    (validation_time, signal_id, symbol, llm_model, validation_type,
                     llm_confidence, timeframe_alignment, pattern_clarity,
                     enhanced_confidence, visual_patterns, key_observations,
                     concerns, recommendation, response_data, processing_time_ms)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
                """,
                    datetime.utcnow(),
                    signal_data.get("signal_id"),
                    signal_data.get("symbol"),
                    validation_result.get("llm_model", "gpt-4-vision"),
                    "signal_validation",
                    validation_result.get("llm_confidence"),
                    validation_result.get("timeframe_alignment"),
                    validation_result.get("pattern_clarity"),
                    validation_result.get("enhanced_confidence"),
                    validation_result.get("visual_patterns", []),
                    validation_result.get("key_observations", []),
                    validation_result.get("concerns", []),
                    "APPROVE" if validation_result.get("valid") else "REJECT",
                    json.dumps(validation_result),
                    validation_result.get("processing_time_ms", 0),
                )

        except Exception as e:
            self.logger.error(f"Error storing validation result: {e}")

    async def publish_validation_result(
        self, signal_data: Dict[str, Any], validation_result: Dict[str, Any]
    ):
        """Publish validation result to RabbitMQ."""
        try:
            # Combine signal data with validation result
            enhanced_signal = signal_data.copy()
            enhanced_signal.update(
                {
                    "validation": validation_result,
                    "validation_timestamp": datetime.utcnow().isoformat(),
                    "validated": validation_result.get("valid", False),
                }
            )

            # Publish validated signal
            await self.publish_message(
                Exchanges.SIGNALS,
                format_routing_key(
                    RoutingKeys.SIGNAL_VALIDATED, symbol=signal_data["symbol"]
                ),
                enhanced_signal,
            )

        except Exception as e:
            self.logger.error(f"Error publishing validation result: {e}")

    def _get_cache_key(self, signal_data: Dict[str, Any]) -> str:
        """Generate cache key for signal validation."""
        symbol = signal_data.get("symbol", "unknown")
        direction = signal_data.get("direction", "unknown")
        timestamp = signal_data.get("timestamp", datetime.utcnow())

        # Round timestamp to nearest 5 minutes for caching
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))

        rounded_time = timestamp.replace(
            minute=timestamp.minute // 5 * 5, second=0, microsecond=0
        )

        return f"validation:{symbol}:{direction}:{rounded_time.isoformat()}"

    def _is_cache_valid(self, cache_entry: Dict[str, Any]) -> bool:
        """Check if cache entry is still valid."""
        timestamp = cache_entry.get("timestamp")
        ttl = cache_entry.get("ttl", self.chart_cache_ttl)

        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)

        return (datetime.utcnow() - timestamp).total_seconds() < ttl

    def _is_market_data_fresh(self, market_data: Dict[str, Any]) -> bool:
        """Check if market data is fresh enough for analysis."""
        try:
            # Check if we have data for primary timeframe (4H)
            timeframes = market_data.get("timeframes", {})

            if "4H" not in timeframes:
                return False

            prices = timeframes["4H"].get("prices", [])
            if not prices:
                return False

            # Check if latest data is recent enough (within 6 hours)
            latest_time = prices[0].get("time")  # First item should be most recent
            if isinstance(latest_time, str):
                latest_time = datetime.fromisoformat(latest_time)

            time_diff = (datetime.utcnow() - latest_time).total_seconds()
            return time_diff < 21600  # 6 hours

        except Exception:
            return False

    async def _should_rate_limit(self, symbol: str, priority: bool) -> bool:
        """Check if we should rate limit LLM calls for cost optimization."""
        if not self.cost_optimization or priority:
            return False

        last_call = self.last_llm_call.get(symbol)
        if not last_call:
            return False

        time_since_last = (datetime.utcnow() - last_call).total_seconds()
        return time_since_last < self.min_interval_between_calls

    def _estimate_analysis_cost(
        self, signal_data: Dict[str, Any], validation_result: Dict[str, Any]
    ) -> float:
        """Estimate cost of analysis for tracking."""
        # Rough estimate: $0.01-0.03 per GPT-4V image analysis
        base_cost = 0.02

        # Adjust for complexity
        if validation_result.get("timeframe_alignment"):
            base_cost *= 1.2  # Multi-timeframe analysis costs more

        return base_cost

    async def load_validation_cache(self):
        """Load validation cache from Redis."""
        try:
            cache_data = await self.cache_json_get("llm_validation_cache")
            if cache_data:
                self.validation_cache = cache_data
                self.logger.info(
                    f"Loaded {len(self.validation_cache)} cached validations"
                )
        except Exception as e:
            self.logger.error(f"Error loading validation cache: {e}")

    async def save_validation_cache(self):
        """Save validation cache to Redis."""
        try:
            # Clean old entries before saving
            await self.cleanup_cache()

            await self.cache_json_set(
                "llm_validation_cache", self.validation_cache, ttl=3600  # 1 hour
            )
            self.logger.info(f"Saved {len(self.validation_cache)} cached validations")
        except Exception as e:
            self.logger.error(f"Error saving validation cache: {e}")

    async def cleanup_cache(self):
        """Clean up expired cache entries."""
        current_time = datetime.utcnow()
        expired_keys = []

        for key, entry in self.validation_cache.items():
            if not self._is_cache_valid(entry):
                expired_keys.append(key)

        for key in expired_keys:
            del self.validation_cache[key]

        if expired_keys:
            self.logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")

    async def cache_cleanup_loop(self):
        """Periodically clean up cache."""
        while self.running:
            try:
                await self.cleanup_cache()
                await asyncio.sleep(300)  # Clean every 5 minutes
            except Exception as e:
                self.logger.error(f"Error in cache cleanup: {e}")
                await asyncio.sleep(300)

    async def heartbeat_loop(self):
        """Send periodic heartbeats and metrics."""
        while self.running:
            try:
                # Calculate metrics
                avg_processing_time = (
                    sum(self.processing_times[-100:])
                    / len(self.processing_times[-100:])
                    if self.processing_times
                    else 0
                )

                # Send heartbeat
                await self.publish_message(
                    Exchanges.SYSTEM,
                    format_routing_key(
                        RoutingKeys.SYSTEM_HEARTBEAT, service=self.service_name
                    ),
                    {
                        "analyses_completed": self.analyses_completed,
                        "total_cost": self.total_cost,
                        "avg_processing_time": avg_processing_time,
                        "cache_size": len(self.validation_cache),
                        "queue_size": self.validation_queue.qsize(),
                        "priority_queue_size": self.priority_queue.qsize(),
                        "health": await self.health_check(),
                    },
                )

                # Send metrics
                await self.publish_message(
                    Exchanges.SYSTEM,
                    format_routing_key(
                        RoutingKeys.SYSTEM_METRICS, service=self.service_name
                    ),
                    {
                        "analyses_completed_total": self.analyses_completed,
                        "total_cost_usd": self.total_cost,
                        "avg_processing_time_seconds": avg_processing_time,
                        "validation_cache_size": len(self.validation_cache),
                    },
                )

                await asyncio.sleep(30)

            except Exception as e:
                self.logger.error(f"Error in heartbeat loop: {e}")
                await asyncio.sleep(30)


if __name__ == "__main__":
    # Load configuration
    config = ServiceConfig.from_env()

    # Create and run service
    service = LLMAnalyzerService(config)
    asyncio.run(service.run())
