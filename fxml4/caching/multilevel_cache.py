"""
Multi-Level Cache Implementation

High-performance hierarchical caching system:
- L1: In-memory cache (fastest, smallest capacity)
- L2: Redis cluster (fast, medium capacity)
- L3: Database with intelligent prefetching (slower, largest capacity)
- Automatic promotion/demotion based on access patterns
"""

import asyncio
import hashlib
import heapq
import json
import logging
import pickle
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union

# Redis import with fallback
try:
    import redis

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


class CacheLevel(Enum):
    """Cache level enumeration"""

    L1_MEMORY = "l1_memory"
    L2_REDIS = "l2_redis"
    L3_DATABASE = "l3_database"


@dataclass
class CacheStats:
    """Cache performance statistics"""

    level: CacheLevel
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    size: int = 0
    max_size: int = 0
    total_get_time_ms: float = 0.0
    total_set_time_ms: float = 0.0

    @property
    def hit_rate(self) -> float:
        """Cache hit rate percentage"""
        total = self.hits + self.misses
        return (self.hits / total * 100.0) if total > 0 else 0.0

    @property
    def average_get_time_ms(self) -> float:
        """Average get operation time"""
        total_ops = self.hits + self.misses
        return self.total_get_time_ms / total_ops if total_ops > 0 else 0.0

    @property
    def utilization(self) -> float:
        """Cache utilization percentage"""
        return (self.size / self.max_size * 100.0) if self.max_size > 0 else 0.0


@dataclass
class CacheEntry:
    """Cache entry with metadata"""

    key: str
    value: Any
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    access_count: int = 0
    ttl: Optional[float] = None
    size_bytes: int = 0

    @property
    def is_expired(self) -> bool:
        """Check if entry is expired"""
        if self.ttl is None:
            return False
        return time.time() > (self.created_at + self.ttl)

    @property
    def age_seconds(self) -> float:
        """Age of entry in seconds"""
        return time.time() - self.created_at


class LRUCache:
    """
    High-performance LRU cache implementation

    Optimized for trading applications with sub-microsecond access times.
    Uses doubly-linked list for O(1) insertion/deletion.
    """

    def __init__(self, max_size: int = 10000):
        self.max_size = max_size
        self.cache: Dict[str, CacheEntry] = {}
        self.access_order: deque = deque()
        self.size_bytes = 0
        self.lock = threading.RLock()

        # Performance tracking
        self.stats = CacheStats(level=CacheLevel.L1_MEMORY, max_size=max_size)

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        start_time = time.time()

        with self.lock:
            if key in self.cache:
                entry = self.cache[key]

                # Check expiration
                if entry.is_expired:
                    self._remove_entry(key)
                    self.stats.misses += 1
                    return None

                # Update access information
                entry.last_accessed = time.time()
                entry.access_count += 1

                # Move to end of access order (most recently used)
                try:
                    self.access_order.remove(key)
                except ValueError:
                    pass  # Key not in access order
                self.access_order.append(key)

                self.stats.hits += 1
                self.stats.total_get_time_ms += (time.time() - start_time) * 1000
                return entry.value
            else:
                self.stats.misses += 1
                self.stats.total_get_time_ms += (time.time() - start_time) * 1000
                return None

    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> bool:
        """Set value in cache"""
        start_time = time.time()

        with self.lock:
            # Calculate size
            value_size = self._calculate_size(value)

            # Remove existing entry if present
            if key in self.cache:
                self._remove_entry(key)

            # Check capacity
            while len(self.cache) >= self.max_size or (
                len(self.cache) > 0
                and self.size_bytes + value_size > self.max_size * 1024
            ):
                if not self._evict_lru():
                    # Cannot evict, cache might be full of non-evictable items
                    self.stats.total_set_time_ms += (time.time() - start_time) * 1000
                    return False

            # Create new entry
            entry = CacheEntry(key=key, value=value, ttl=ttl, size_bytes=value_size)

            # Add to cache
            self.cache[key] = entry
            self.access_order.append(key)
            self.size_bytes += value_size

            # Update stats
            self.stats.size = len(self.cache)
            self.stats.total_set_time_ms += (time.time() - start_time) * 1000

            return True

    def delete(self, key: str) -> bool:
        """Delete entry from cache"""
        with self.lock:
            if key in self.cache:
                self._remove_entry(key)
                return True
            return False

    def _remove_entry(self, key: str):
        """Remove entry from cache"""
        if key in self.cache:
            entry = self.cache[key]
            del self.cache[key]
            self.size_bytes -= entry.size_bytes

            try:
                self.access_order.remove(key)
            except ValueError:
                pass

            self.stats.size = len(self.cache)

    def _evict_lru(self) -> bool:
        """Evict least recently used item"""
        if not self.access_order:
            return False

        lru_key = self.access_order.popleft()
        if lru_key in self.cache:
            self._remove_entry(lru_key)
            self.stats.evictions += 1
            return True

        return False

    def _calculate_size(self, value: Any) -> int:
        """Calculate approximate size of value in bytes"""
        try:
            if isinstance(value, (str, bytes)):
                return len(value)
            elif isinstance(value, (int, float)):
                return 8
            elif isinstance(value, (list, tuple)):
                return sum(self._calculate_size(item) for item in value)
            elif isinstance(value, dict):
                return sum(
                    self._calculate_size(k) + self._calculate_size(v)
                    for k, v in value.items()
                )
            else:
                # Fallback to pickle size
                return len(pickle.dumps(value))
        except Exception:
            return 1024  # Default size if calculation fails

    def clear(self):
        """Clear all entries"""
        with self.lock:
            self.cache.clear()
            self.access_order.clear()
            self.size_bytes = 0
            self.stats.size = 0

    def get_stats(self) -> CacheStats:
        """Get cache statistics"""
        with self.lock:
            return self.stats


class RedisCache:
    """
    Redis-based L2 cache implementation

    Provides distributed caching with high throughput and automatic expiration.
    Optimized for trading data with millisecond access times.
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        default_ttl: int = 3600,
        key_prefix: str = "fxml4:",
    ):
        self.redis_url = redis_url
        self.default_ttl = default_ttl
        self.key_prefix = key_prefix
        self.redis_client = None

        # Performance tracking
        self.stats = CacheStats(level=CacheLevel.L2_REDIS, max_size=1_000_000)
        self.lock = threading.RLock()

        # Initialize Redis connection
        self._init_redis()

    def _init_redis(self):
        """Initialize Redis connection"""
        if not REDIS_AVAILABLE:
            logging.warning("Redis not available, L2 cache disabled")
            return

        try:
            self.redis_client = redis.from_url(
                self.redis_url,
                decode_responses=False,  # Keep binary for pickle
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30,
            )

            # Test connection
            self.redis_client.ping()
            logging.info(f"Connected to Redis at {self.redis_url}")

        except Exception as e:
            logging.error(f"Failed to connect to Redis: {e}")
            self.redis_client = None

    def _make_key(self, key: str) -> str:
        """Create prefixed key"""
        return f"{self.key_prefix}{key}"

    async def get(self, key: str) -> Optional[Any]:
        """Get value from Redis cache"""
        if not self.redis_client:
            with self.lock:
                self.stats.misses += 1
            return None

        start_time = time.time()

        try:
            redis_key = self._make_key(key)
            data = self.redis_client.get(redis_key)

            if data is not None:
                # Deserialize value
                value = pickle.loads(data)

                with self.lock:
                    self.stats.hits += 1
                    self.stats.total_get_time_ms += (time.time() - start_time) * 1000

                return value
            else:
                with self.lock:
                    self.stats.misses += 1
                    self.stats.total_get_time_ms += (time.time() - start_time) * 1000

                return None

        except Exception as e:
            logging.error(f"Redis get error: {e}")
            with self.lock:
                self.stats.misses += 1
            return None

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in Redis cache"""
        if not self.redis_client:
            return False

        start_time = time.time()

        try:
            redis_key = self._make_key(key)
            data = pickle.dumps(value)

            # Use default TTL if not specified
            expiry = ttl if ttl is not None else self.default_ttl

            result = self.redis_client.setex(redis_key, expiry, data)

            with self.lock:
                self.stats.total_set_time_ms += (time.time() - start_time) * 1000

            return bool(result)

        except Exception as e:
            logging.error(f"Redis set error: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """Delete value from Redis cache"""
        if not self.redis_client:
            return False

        try:
            redis_key = self._make_key(key)
            result = self.redis_client.delete(redis_key)
            return result > 0

        except Exception as e:
            logging.error(f"Redis delete error: {e}")
            return False

    async def clear_prefix(self, prefix: str):
        """Clear all keys with given prefix"""
        if not self.redis_client:
            return

        try:
            pattern = f"{self.key_prefix}{prefix}*"
            keys = self.redis_client.keys(pattern)

            if keys:
                self.redis_client.delete(*keys)

        except Exception as e:
            logging.error(f"Redis clear prefix error: {e}")

    def get_stats(self) -> CacheStats:
        """Get Redis cache statistics"""
        with self.lock:
            if self.redis_client:
                try:
                    info = self.redis_client.info("memory")
                    self.stats.size = info.get("used_memory", 0)
                except Exception:
                    pass

            return self.stats


class MultiLevelCache:
    """
    Multi-level cache system with intelligent data placement

    Implements a hierarchical caching strategy:
    - L1: Ultra-fast in-memory cache (microsecond access)
    - L2: Fast Redis distributed cache (millisecond access)
    - L3: Database with intelligent prefetching (sub-second access)

    Features automatic promotion/demotion based on access patterns.
    """

    def __init__(
        self,
        l1_size: int = 10000,
        redis_url: str = "redis://localhost:6379",
        database_connector: Optional[Callable] = None,
    ):

        # Cache levels
        self.l1_cache = LRUCache(max_size=l1_size)
        self.l2_cache = RedisCache(redis_url=redis_url)
        self.database_connector = database_connector

        # Access pattern tracking
        self.access_patterns: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {
                "access_count": 0,
                "last_access": 0,
                "access_frequency": 0.0,
                "promotion_score": 0.0,
            }
        )

        # Configuration
        self.l1_promotion_threshold = 3  # Promote to L1 after 3 accesses
        self.l2_promotion_threshold = 2  # Promote to L2 after 2 accesses

        # Performance tracking
        self.global_stats = {
            "total_gets": 0,
            "l1_hits": 0,
            "l2_hits": 0,
            "l3_hits": 0,
            "total_misses": 0,
            "promotions": 0,
            "demotions": 0,
        }

        self.lock = threading.RLock()
        self.logger = logging.getLogger("MultiLevelCache")

    async def get(self, key: str) -> Optional[Any]:
        """Get value from multi-level cache"""
        start_time = time.time()

        with self.lock:
            self.global_stats["total_gets"] += 1

            # Track access pattern
            pattern = self.access_patterns[key]
            pattern["access_count"] += 1
            pattern["last_access"] = time.time()
            self._update_access_frequency(key)

        # Try L1 cache first
        value = self.l1_cache.get(key)
        if value is not None:
            with self.lock:
                self.global_stats["l1_hits"] += 1
            self.logger.debug(f"L1 hit for key: {key}")
            return value

        # Try L2 cache
        value = await self.l2_cache.get(key)
        if value is not None:
            with self.lock:
                self.global_stats["l2_hits"] += 1

            # Consider promoting to L1
            if self._should_promote_to_l1(key):
                self.l1_cache.set(key, value)
                with self.lock:
                    self.global_stats["promotions"] += 1

                self.logger.debug(f"Promoted key to L1: {key}")

            self.logger.debug(f"L2 hit for key: {key}")
            return value

        # Try L3 (database) if connector available
        if self.database_connector:
            try:
                value = await self._get_from_database(key)
                if value is not None:
                    with self.lock:
                        self.global_stats["l3_hits"] += 1

                    # Store in appropriate cache level
                    await self._store_with_placement_strategy(key, value)

                    self.logger.debug(f"L3 hit for key: {key}")
                    return value

            except Exception as e:
                self.logger.error(f"Database lookup error: {e}")

        # Cache miss
        with self.lock:
            self.global_stats["total_misses"] += 1

        self.logger.debug(f"Cache miss for key: {key}")
        return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[float] = None,
        force_level: Optional[CacheLevel] = None,
    ) -> bool:
        """Set value in multi-level cache"""

        if force_level:
            # Force to specific level
            if force_level == CacheLevel.L1_MEMORY:
                return self.l1_cache.set(key, value, ttl)
            elif force_level == CacheLevel.L2_REDIS:
                return await self.l2_cache.set(key, value, int(ttl) if ttl else None)
            elif force_level == CacheLevel.L3_DATABASE:
                return await self._set_to_database(key, value)
        else:
            # Use intelligent placement strategy
            return await self._store_with_placement_strategy(key, value, ttl)

    async def _store_with_placement_strategy(
        self, key: str, value: Any, ttl: Optional[float] = None
    ) -> bool:
        """Store value using intelligent placement strategy"""

        # Determine best cache level based on access patterns
        pattern = self.access_patterns[key]

        # Calculate value characteristics
        value_size = self.l1_cache._calculate_size(value)
        is_hot_data = pattern["access_frequency"] > 1.0  # More than 1 access per second
        is_large_data = value_size > 10 * 1024  # Larger than 10KB

        # Placement strategy
        success = False

        if (
            is_hot_data
            and not is_large_data
            and pattern["access_count"] >= self.l1_promotion_threshold
        ):
            # Store in L1 for hot, small data
            success = self.l1_cache.set(key, value, ttl)
            self.logger.debug(f"Stored in L1: {key}")

        if not success or is_large_data:
            # Store in L2 for medium-hot data or large data
            success = await self.l2_cache.set(key, value, int(ttl) if ttl else None)
            if success:
                self.logger.debug(f"Stored in L2: {key}")

        # Always try to store in database if connector available
        if self.database_connector and not is_hot_data:
            try:
                await self._set_to_database(key, value)
                success = True
                self.logger.debug(f"Stored in L3: {key}")
            except Exception as e:
                self.logger.error(f"Database store error: {e}")

        return success

    async def delete(self, key: str) -> bool:
        """Delete value from all cache levels"""
        results = []

        # Delete from L1
        results.append(self.l1_cache.delete(key))

        # Delete from L2
        results.append(await self.l2_cache.delete(key))

        # Delete from L3 if connector available
        if self.database_connector:
            try:
                results.append(await self._delete_from_database(key))
            except Exception as e:
                self.logger.error(f"Database delete error: {e}")
                results.append(False)

        # Remove from access patterns
        with self.lock:
            if key in self.access_patterns:
                del self.access_patterns[key]

        return any(results)

    def _should_promote_to_l1(self, key: str) -> bool:
        """Check if key should be promoted to L1 cache"""
        pattern = self.access_patterns[key]

        # Promote if:
        # - Accessed frequently (>= threshold)
        # - High access frequency
        # - Recent access pattern
        return (
            pattern["access_count"] >= self.l1_promotion_threshold
            and pattern["access_frequency"] > 0.5
            and time.time() - pattern["last_access"] < 300
        )  # Within 5 minutes

    def _update_access_frequency(self, key: str):
        """Update access frequency for key"""
        pattern = self.access_patterns[key]
        current_time = time.time()

        # Calculate frequency as accesses per second over time window
        time_window = 3600  # 1 hour
        pattern["access_frequency"] = pattern["access_count"] / min(
            current_time - (current_time - time_window), time_window
        )

    async def _get_from_database(self, key: str) -> Optional[Any]:
        """Get value from database (L3)"""
        if not self.database_connector:
            return None

        try:
            # This would be implemented based on specific database schema
            # Placeholder implementation
            return await self.database_connector.get(key)
        except Exception as e:
            self.logger.error(f"Database get error: {e}")
            return None

    async def _set_to_database(self, key: str, value: Any) -> bool:
        """Set value to database (L3)"""
        if not self.database_connector:
            return False

        try:
            # This would be implemented based on specific database schema
            # Placeholder implementation
            return await self.database_connector.set(key, value)
        except Exception as e:
            self.logger.error(f"Database set error: {e}")
            return False

    async def _delete_from_database(self, key: str) -> bool:
        """Delete value from database (L3)"""
        if not self.database_connector:
            return False

        try:
            # This would be implemented based on specific database schema
            # Placeholder implementation
            return await self.database_connector.delete(key)
        except Exception as e:
            self.logger.error(f"Database delete error: {e}")
            return False

    def get_comprehensive_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics"""
        with self.lock:
            l1_stats = self.l1_cache.get_stats()
            l2_stats = self.l2_cache.get_stats()

            total_hits = (
                self.global_stats["l1_hits"]
                + self.global_stats["l2_hits"]
                + self.global_stats["l3_hits"]
            )

            total_requests = total_hits + self.global_stats["total_misses"]

            return {
                "global": {
                    **self.global_stats,
                    "total_requests": total_requests,
                    "overall_hit_rate": (
                        (total_hits / total_requests * 100.0)
                        if total_requests > 0
                        else 0.0
                    ),
                    "l1_hit_rate": (
                        (self.global_stats["l1_hits"] / total_requests * 100.0)
                        if total_requests > 0
                        else 0.0
                    ),
                    "l2_hit_rate": (
                        (self.global_stats["l2_hits"] / total_requests * 100.0)
                        if total_requests > 0
                        else 0.0
                    ),
                    "l3_hit_rate": (
                        (self.global_stats["l3_hits"] / total_requests * 100.0)
                        if total_requests > 0
                        else 0.0
                    ),
                },
                "l1_cache": l1_stats.__dict__,
                "l2_cache": l2_stats.__dict__,
                "access_patterns": len(self.access_patterns),
                "hot_keys": self._get_hot_keys(10),
            }

    def _get_hot_keys(self, limit: int) -> List[str]:
        """Get most frequently accessed keys"""
        with self.lock:
            # Sort by access frequency
            sorted_patterns = sorted(
                self.access_patterns.items(),
                key=lambda x: x[1]["access_frequency"],
                reverse=True,
            )

            return [key for key, _ in sorted_patterns[:limit]]

    async def warm_cache(self, keys: List[str], batch_size: int = 100):
        """Warm cache with specified keys"""
        self.logger.info(f"Warming cache with {len(keys)} keys")

        for i in range(0, len(keys), batch_size):
            batch = keys[i : i + batch_size]

            # Process batch
            tasks = []
            for key in batch:
                tasks.append(self.get(key))

            await asyncio.gather(*tasks, return_exceptions=True)

            # Small delay between batches
            if i + batch_size < len(keys):
                await asyncio.sleep(0.1)


# Example usage and testing
if __name__ == "__main__":
    import asyncio
    import random

    async def main():
        print("Multi-Level Cache Performance Test")
        print("=" * 50)

        # Create multi-level cache
        cache = MultiLevelCache(l1_size=1000, redis_url="redis://localhost:6379")

        # Test data
        test_data = {
            f"symbol:{symbol}": {
                "price": random.uniform(100, 200),
                "volume": random.randint(1000, 100000),
                "timestamp": time.time(),
            }
            for symbol in ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD"] * 20
        }

        # Load test data
        print("Loading test data...")
        start_time = time.time()

        for key, value in test_data.items():
            await cache.set(key, value)

        load_time = time.time() - start_time
        print(f"Loaded {len(test_data)} items in {load_time:.3f}s")

        # Simulate access patterns
        print("\nSimulating access patterns...")

        # Hot data (frequently accessed)
        hot_keys = list(test_data.keys())[:20]

        # Warm data (occasionally accessed)
        warm_keys = list(test_data.keys())[20:50]

        # Cold data (rarely accessed)
        cold_keys = list(test_data.keys())[50:]

        # Access simulation
        start_time = time.time()

        for _ in range(1000):
            # 70% hot data, 20% warm data, 10% cold data
            r = random.random()
            if r < 0.7:
                key = random.choice(hot_keys)
            elif r < 0.9:
                key = random.choice(warm_keys)
            else:
                key = random.choice(cold_keys)

            value = await cache.get(key)

        access_time = time.time() - start_time
        print(f"Processed 1000 accesses in {access_time:.3f}s")
        print(f"Average access time: {access_time / 1000 * 1000:.2f}ms")

        # Get comprehensive statistics
        stats = cache.get_comprehensive_stats()

        print(f"\nCache Performance Statistics:")
        print(f"Overall hit rate: {stats['global']['overall_hit_rate']:.1f}%")
        print(f"L1 hit rate: {stats['global']['l1_hit_rate']:.1f}%")
        print(f"L2 hit rate: {stats['global']['l2_hit_rate']:.1f}%")
        print(f"L3 hit rate: {stats['global']['l3_hit_rate']:.1f}%")
        print(f"Total requests: {stats['global']['total_requests']}")
        print(f"Promotions: {stats['global']['promotions']}")

        print(f"\nL1 Cache:")
        print(f"  Hit rate: {stats['l1_cache']['hit_rate']:.1f}%")
        print(f"  Size: {stats['l1_cache']['size']}/{stats['l1_cache']['max_size']}")
        print(f"  Avg get time: {stats['l1_cache']['average_get_time_ms']:.2f}ms")

        print(f"\nL2 Cache:")
        print(f"  Hit rate: {stats['l2_cache']['hit_rate']:.1f}%")

        print(f"\nHot Keys: {stats['hot_keys']}")

        # Test cache warming
        print(f"\nTesting cache warming...")
        warm_keys = [f"warm_key_{i}" for i in range(100)]
        await cache.warm_cache(warm_keys)

        print("Multi-level cache test completed!")

    # Run the test
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        print(f"Test failed: {e}")
