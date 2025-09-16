"""
Memory Pool and Aligned Allocator

Custom memory management for high-frequency trading:
- Object pooling to reduce GC pressure
- Aligned memory allocation for cache optimization
- Zero-allocation patterns for hot paths
"""

import ctypes
import mmap
import threading
from collections import deque
from dataclasses import dataclass
from typing import Any, Generic, List, Optional, Type, TypeVar

T = TypeVar("T")


class AlignedMemoryAllocator:
    """
    Cache-aligned memory allocator for optimal CPU cache performance

    Ensures data structures are aligned to cache line boundaries (64 bytes)
    to prevent false sharing and optimize memory access patterns.
    """

    CACHE_LINE_SIZE = 64

    def __init__(self, size: int, alignment: int = CACHE_LINE_SIZE):
        self.size = size
        self.alignment = alignment
        self.buffer = mmap.mmap(-1, size + alignment)

        # Calculate aligned start address
        addr = ctypes.addressof(ctypes.c_char.from_buffer(self.buffer))
        aligned_addr = (addr + alignment - 1) & ~(alignment - 1)
        self.offset = aligned_addr - addr
        self.available = size
        self.allocated = 0

    def allocate(self, size: int) -> Optional[int]:
        """Allocate aligned memory block"""
        if self.allocated + size > self.available:
            return None

        # Ensure allocation is aligned
        aligned_size = (size + self.alignment - 1) & ~(self.alignment - 1)
        offset = self.offset + self.allocated
        self.allocated += aligned_size

        return offset

    def get_buffer_slice(self, offset: int, size: int) -> memoryview:
        """Get memory view of allocated block"""
        return memoryview(self.buffer)[offset : offset + size]

    def reset(self):
        """Reset allocator for reuse"""
        self.allocated = 0

    def __del__(self):
        if hasattr(self, "buffer"):
            self.buffer.close()


class MemoryPool(Generic[T]):
    """
    Thread-safe object pool for high-frequency allocation/deallocation

    Reduces garbage collection pressure by reusing objects instead of
    creating new instances. Critical for sub-millisecond performance.
    """

    def __init__(
        self, object_type: Type[T], initial_size: int = 1000, max_size: int = 10000
    ):
        self.object_type = object_type
        self.max_size = max_size
        self.pool: deque = deque(maxlen=max_size)
        self.lock = threading.Lock()

        # Pre-populate pool
        self._populate_pool(initial_size)

        # Statistics
        self.allocations = 0
        self.deallocations = 0
        self.pool_hits = 0
        self.pool_misses = 0

    def _populate_pool(self, count: int):
        """Pre-populate pool with objects"""
        for _ in range(count):
            try:
                obj = self.object_type()
                self.pool.append(obj)
            except Exception:
                # Handle objects that require parameters
                break

    def acquire(self, *args, **kwargs) -> T:
        """Acquire object from pool or create new one"""
        with self.lock:
            if self.pool:
                obj = self.pool.popleft()
                self.pool_hits += 1

                # Reset object if it has a reset method
                if hasattr(obj, "reset"):
                    obj.reset()

                self.allocations += 1
                return obj

        # Pool is empty, create new object
        self.pool_misses += 1
        self.allocations += 1
        return self.object_type(*args, **kwargs)

    def release(self, obj: T):
        """Release object back to pool"""
        if obj is None:
            return

        with self.lock:
            if len(self.pool) < self.max_size:
                # Clear object state if it has a clear method
                if hasattr(obj, "clear"):
                    obj.clear()

                self.pool.append(obj)

            self.deallocations += 1

    def size(self) -> int:
        """Get current pool size"""
        with self.lock:
            return len(self.pool)

    def get_stats(self) -> dict:
        """Get pool statistics"""
        with self.lock:
            hit_rate = (
                self.pool_hits / (self.pool_hits + self.pool_misses)
                if (self.pool_hits + self.pool_misses) > 0
                else 0
            )
            return {
                "pool_size": len(self.pool),
                "max_size": self.max_size,
                "allocations": self.allocations,
                "deallocations": self.deallocations,
                "pool_hits": self.pool_hits,
                "pool_misses": self.pool_misses,
                "hit_rate": hit_rate,
                "active_objects": self.allocations - self.deallocations,
            }

    def clear(self):
        """Clear the entire pool"""
        with self.lock:
            self.pool.clear()


class RingBuffer:
    """
    Lock-free ring buffer for single producer, single consumer scenarios

    Optimized for high-throughput, low-latency data transfer between threads.
    Uses memory barriers to ensure correct ordering without locks.
    """

    def __init__(self, size: int, element_size: int):
        # Size must be power of 2 for efficient modulo operation
        self.size = 1 << (size - 1).bit_length()
        self.mask = self.size - 1
        self.element_size = element_size

        # Aligned memory buffer
        self.allocator = AlignedMemoryAllocator(self.size * element_size)
        self.buffer_offset = self.allocator.allocate(self.size * element_size)

        # Head and tail pointers (cache-line aligned)
        self.head = 0  # Write position
        self.tail = 0  # Read position

        # Statistics
        self.writes = 0
        self.reads = 0
        self.write_failures = 0
        self.read_failures = 0

    def write(self, data: bytes) -> bool:
        """Write data to ring buffer (producer)"""
        if len(data) != self.element_size:
            return False

        next_head = (self.head + 1) & self.mask

        # Check if buffer is full
        if next_head == self.tail:
            self.write_failures += 1
            return False

        # Write data to buffer
        offset = self.buffer_offset + (self.head * self.element_size)
        buffer_slice = self.allocator.get_buffer_slice(offset, self.element_size)
        buffer_slice[:] = data

        # Memory barrier - ensure data is written before updating head
        # In Python, this is handled by the GIL, but in C/C++ would need explicit barriers
        self.head = next_head
        self.writes += 1

        return True

    def read(self) -> Optional[bytes]:
        """Read data from ring buffer (consumer)"""
        # Check if buffer is empty
        if self.head == self.tail:
            self.read_failures += 1
            return None

        # Read data from buffer
        offset = self.buffer_offset + (self.tail * self.element_size)
        buffer_slice = self.allocator.get_buffer_slice(offset, self.element_size)
        data = bytes(buffer_slice)

        # Memory barrier - ensure data is read before updating tail
        self.tail = (self.tail + 1) & self.mask
        self.reads += 1

        return data

    def is_empty(self) -> bool:
        """Check if buffer is empty"""
        return self.head == self.tail

    def is_full(self) -> bool:
        """Check if buffer is full"""
        return ((self.head + 1) & self.mask) == self.tail

    def available_space(self) -> int:
        """Get number of available slots"""
        return (self.tail - self.head - 1) & self.mask

    def used_space(self) -> int:
        """Get number of used slots"""
        return (self.head - self.tail) & self.mask

    def get_stats(self) -> dict:
        """Get buffer statistics"""
        return {
            "size": self.size,
            "element_size": self.element_size,
            "writes": self.writes,
            "reads": self.reads,
            "write_failures": self.write_failures,
            "read_failures": self.read_failures,
            "available_space": self.available_space(),
            "used_space": self.used_space(),
            "utilization": self.used_space() / self.size,
        }


@dataclass
class MemoryStats:
    """Memory usage statistics"""

    total_allocated: int = 0
    total_freed: int = 0
    peak_usage: int = 0
    current_usage: int = 0
    allocations_count: int = 0
    deallocations_count: int = 0
    fragmentation_ratio: float = 0.0


class MemoryManager:
    """
    Central memory manager for HFT system

    Coordinates all memory allocation strategies:
    - Object pools for frequently used objects
    - Aligned allocators for cache optimization
    - Ring buffers for lock-free communication
    """

    def __init__(self):
        self.pools: dict = {}
        self.allocators: dict = {}
        self.ring_buffers: dict = {}
        self.stats = MemoryStats()
        self.lock = threading.Lock()

    def create_pool(
        self, name: str, object_type: Type[T], initial_size: int = 1000
    ) -> MemoryPool[T]:
        """Create named object pool"""
        with self.lock:
            if name in self.pools:
                return self.pools[name]

            pool = MemoryPool(object_type, initial_size)
            self.pools[name] = pool
            return pool

    def get_pool(self, name: str) -> Optional[MemoryPool]:
        """Get existing pool by name"""
        return self.pools.get(name)

    def create_allocator(
        self, name: str, size: int, alignment: int = 64
    ) -> AlignedMemoryAllocator:
        """Create named aligned allocator"""
        with self.lock:
            if name in self.allocators:
                return self.allocators[name]

            allocator = AlignedMemoryAllocator(size, alignment)
            self.allocators[name] = allocator
            return allocator

    def get_allocator(self, name: str) -> Optional[AlignedMemoryAllocator]:
        """Get existing allocator by name"""
        return self.allocators.get(name)

    def create_ring_buffer(self, name: str, size: int, element_size: int) -> RingBuffer:
        """Create named ring buffer"""
        with self.lock:
            if name in self.ring_buffers:
                return self.ring_buffers[name]

            buffer = RingBuffer(size, element_size)
            self.ring_buffers[name] = buffer
            return buffer

    def get_ring_buffer(self, name: str) -> Optional[RingBuffer]:
        """Get existing ring buffer by name"""
        return self.ring_buffers.get(name)

    def get_comprehensive_stats(self) -> dict:
        """Get comprehensive memory statistics"""
        with self.lock:
            pool_stats = {name: pool.get_stats() for name, pool in self.pools.items()}
            buffer_stats = {
                name: buf.get_stats() for name, buf in self.ring_buffers.items()
            }

            return {
                "global_stats": self.stats.__dict__,
                "pools": pool_stats,
                "ring_buffers": buffer_stats,
                "total_pools": len(self.pools),
                "total_allocators": len(self.allocators),
                "total_ring_buffers": len(self.ring_buffers),
            }

    def reset_all(self):
        """Reset all memory structures"""
        with self.lock:
            for pool in self.pools.values():
                pool.clear()

            for allocator in self.allocators.values():
                allocator.reset()

            # Note: Ring buffers don't need explicit reset as they're circular


# Global memory manager instance
memory_manager = MemoryManager()


# Example usage and testing
if __name__ == "__main__":
    import time
    from dataclasses import dataclass

    @dataclass
    class TestObject:
        value: int = 0
        data: str = ""

        def reset(self):
            self.value = 0
            self.data = ""

    # Test memory pool performance
    pool = memory_manager.create_pool("test_objects", TestObject, 1000)

    start_time = time.time()
    objects = []

    # Allocate objects
    for i in range(10000):
        obj = pool.acquire()
        obj.value = i
        obj.data = f"test_{i}"
        objects.append(obj)

    # Release objects
    for obj in objects:
        pool.release(obj)

    duration = time.time() - start_time
    stats = pool.get_stats()

    print(f"Pool test completed in {duration:.4f} seconds")
    print(f"Pool stats: {stats}")

    # Test ring buffer performance
    ring_buffer = memory_manager.create_ring_buffer("test_buffer", 1024, 64)

    # Test data throughput
    test_data = b"x" * 64
    start_time = time.time()

    for i in range(100000):
        if not ring_buffer.write(test_data):
            # Buffer full, read some data
            ring_buffer.read()
            ring_buffer.write(test_data)

    duration = time.time() - start_time
    buffer_stats = ring_buffer.get_stats()

    print(f"Ring buffer test completed in {duration:.4f} seconds")
    print(f"Throughput: {100000 / duration:.0f} ops/second")
    print(f"Buffer stats: {buffer_stats}")

    # Comprehensive stats
    comprehensive_stats = memory_manager.get_comprehensive_stats()
    print(f"\nComprehensive memory stats:")
    for category, data in comprehensive_stats.items():
        print(f"{category}: {data}")
