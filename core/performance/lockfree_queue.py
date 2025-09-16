"""
Lock-Free Queue Implementations

High-performance concurrent queues for HFT:
- Single Producer Single Consumer (SPSC) queue
- Multiple Producer Multiple Consumer (MPMC) queue
- Lock-free algorithms with memory barriers
- Cache-aligned data structures for optimal performance
"""

import queue
import threading
import time
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass
from typing import Any, Generic, Optional, TypeVar

T = TypeVar("T")


@dataclass
class QueueStats:
    """Queue performance statistics"""

    enqueues: int = 0
    dequeues: int = 0
    enqueue_failures: int = 0
    dequeue_failures: int = 0
    current_size: int = 0
    max_size: int = 0
    total_wait_time_ns: int = 0


class LockFreeQueueInterface(Generic[T], ABC):
    """Abstract interface for lock-free queues"""

    @abstractmethod
    def enqueue(self, item: T) -> bool:
        """Enqueue item, return True if successful"""
        pass

    @abstractmethod
    def dequeue(self) -> Optional[T]:
        """Dequeue item, return None if empty"""
        pass

    @abstractmethod
    def size(self) -> int:
        """Get current queue size"""
        pass

    @abstractmethod
    def is_empty(self) -> bool:
        """Check if queue is empty"""
        pass

    @abstractmethod
    def is_full(self) -> bool:
        """Check if queue is full"""
        pass


class SPSCQueue(LockFreeQueueInterface[T]):
    """
    Single Producer Single Consumer lock-free queue

    Optimized for high-frequency trading scenarios where one thread
    produces orders/ticks and another consumes them. Uses cache-aligned
    head/tail pointers to prevent false sharing.
    """

    def __init__(self, capacity: int):
        # Ensure capacity is power of 2 for efficient modulo
        self.capacity = 1 << (capacity - 1).bit_length()
        self.mask = self.capacity - 1

        # Ring buffer for data storage
        self.buffer = [None] * self.capacity

        # Cache-aligned head and tail pointers
        # In a real implementation, these would be in separate cache lines
        self.head = 0  # Producer writes here
        self.tail = 0  # Consumer reads from here

        # Statistics
        self.stats = QueueStats(max_size=self.capacity)

    def enqueue(self, item: T) -> bool:
        """Producer enqueues item"""
        current_head = self.head
        next_head = (current_head + 1) & self.mask

        # Check if queue is full
        if next_head == self.tail:
            self.stats.enqueue_failures += 1
            return False

        # Store item
        self.buffer[current_head] = item

        # Memory barrier: ensure item is stored before updating head
        # In Python, the GIL provides this, but in C++ would need acquire/release
        self.head = next_head

        self.stats.enqueues += 1
        self.stats.current_size = self._calculate_size()
        return True

    def dequeue(self) -> Optional[T]:
        """Consumer dequeues item"""
        current_tail = self.tail

        # Check if queue is empty
        if current_tail == self.head:
            self.stats.dequeue_failures += 1
            return None

        # Load item
        item = self.buffer[current_tail]

        # Clear reference to prevent memory leaks
        self.buffer[current_tail] = None

        # Memory barrier: ensure item is loaded before updating tail
        self.tail = (current_tail + 1) & self.mask

        self.stats.dequeues += 1
        self.stats.current_size = self._calculate_size()
        return item

    def size(self) -> int:
        """Get current size (approximate due to concurrent access)"""
        return self._calculate_size()

    def _calculate_size(self) -> int:
        """Calculate current queue size"""
        return (self.head - self.tail) & self.mask

    def is_empty(self) -> bool:
        """Check if queue is empty"""
        return self.head == self.tail

    def is_full(self) -> bool:
        """Check if queue is full"""
        return ((self.head + 1) & self.mask) == self.tail

    def get_stats(self) -> QueueStats:
        """Get queue statistics"""
        self.stats.current_size = self.size()
        return self.stats


class MPMCQueue(LockFreeQueueInterface[T]):
    """
    Multiple Producer Multiple Consumer queue

    Uses atomic operations (simulated with locks in Python) for thread safety.
    In a real implementation, this would use CAS (Compare-And-Swap) operations.
    """

    def __init__(self, capacity: int):
        self.capacity = capacity
        self.buffer = [None] * capacity
        self.head = 0  # Next position to write
        self.tail = 0  # Next position to read

        # Use locks to simulate atomic operations
        # In C++, this would be replaced with atomic variables and CAS
        self.head_lock = threading.Lock()
        self.tail_lock = threading.Lock()

        # Statistics
        self.stats = QueueStats(max_size=capacity)

    def enqueue(self, item: T) -> bool:
        """Thread-safe enqueue operation"""
        with self.head_lock:
            current_head = self.head
            next_head = (current_head + 1) % self.capacity

            # Check if full
            if next_head == self.tail:
                self.stats.enqueue_failures += 1
                return False

            # Store item and update head
            self.buffer[current_head] = item
            self.head = next_head

            self.stats.enqueues += 1
            self.stats.current_size = self._calculate_size()
            return True

    def dequeue(self) -> Optional[T]:
        """Thread-safe dequeue operation"""
        with self.tail_lock:
            current_tail = self.tail

            # Check if empty
            if current_tail == self.head:
                self.stats.dequeue_failures += 1
                return None

            # Load item and update tail
            item = self.buffer[current_tail]
            self.buffer[current_tail] = None
            self.tail = (current_tail + 1) % self.capacity

            self.stats.dequeues += 1
            self.stats.current_size = self._calculate_size()
            return item

    def size(self) -> int:
        """Get current size"""
        return self._calculate_size()

    def _calculate_size(self) -> int:
        """Calculate current queue size"""
        if self.head >= self.tail:
            return self.head - self.tail
        else:
            return self.capacity - self.tail + self.head

    def is_empty(self) -> bool:
        """Check if queue is empty"""
        return self.head == self.tail

    def is_full(self) -> bool:
        """Check if queue is full"""
        return ((self.head + 1) % self.capacity) == self.tail

    def get_stats(self) -> QueueStats:
        """Get queue statistics"""
        self.stats.current_size = self.size()
        return self.stats


class LockFreeQueue(LockFreeQueueInterface[T]):
    """
    Adaptive lock-free queue that chooses implementation based on usage pattern

    Defaults to SPSC for maximum performance, falls back to MPMC if needed.
    """

    def __init__(self, capacity: int, force_mpmc: bool = False):
        self.capacity = capacity

        if force_mpmc:
            self.impl = MPMCQueue(capacity)
            self.queue_type = "MPMC"
        else:
            self.impl = SPSCQueue(capacity)
            self.queue_type = "SPSC"

        # Track producer/consumer thread IDs for optimization
        self.producer_thread = None
        self.consumer_thread = None
        self.multi_producer_detected = False
        self.multi_consumer_detected = False

    def enqueue(self, item: T) -> bool:
        """Enqueue with thread tracking"""
        current_thread = threading.current_thread().ident

        # Track producer threads for SPSC validation
        if self.queue_type == "SPSC":
            if self.producer_thread is None:
                self.producer_thread = current_thread
            elif self.producer_thread != current_thread:
                self.multi_producer_detected = True
                self._upgrade_to_mpmc()

        return self.impl.enqueue(item)

    def dequeue(self) -> Optional[T]:
        """Dequeue with thread tracking"""
        current_thread = threading.current_thread().ident

        # Track consumer threads for SPSC validation
        if self.queue_type == "SPSC":
            if self.consumer_thread is None:
                self.consumer_thread = current_thread
            elif self.consumer_thread != current_thread:
                self.multi_consumer_detected = True
                self._upgrade_to_mpmc()

        return self.impl.dequeue()

    def _upgrade_to_mpmc(self):
        """Upgrade from SPSC to MPMC when multiple threads detected"""
        if self.queue_type == "MPMC":
            return

        print(f"Upgrading queue to MPMC due to multiple producers/consumers")

        # Create new MPMC queue
        new_impl = MPMCQueue(self.capacity)

        # Transfer existing items
        while not self.impl.is_empty():
            item = self.impl.dequeue()
            if item is not None:
                new_impl.enqueue(item)

        # Replace implementation
        self.impl = new_impl
        self.queue_type = "MPMC"

    def size(self) -> int:
        return self.impl.size()

    def is_empty(self) -> bool:
        return self.impl.is_empty()

    def is_full(self) -> bool:
        return self.impl.is_full()

    def get_stats(self) -> dict:
        """Get comprehensive queue statistics"""
        base_stats = self.impl.get_stats()
        return {
            **base_stats.__dict__,
            "queue_type": self.queue_type,
            "capacity": self.capacity,
            "multi_producer_detected": self.multi_producer_detected,
            "multi_consumer_detected": self.multi_consumer_detected,
            "utilization": (
                base_stats.current_size / self.capacity if self.capacity > 0 else 0
            ),
        }


class PriorityLockFreeQueue(LockFreeQueueInterface[T]):
    """
    Priority queue with lock-free characteristics for order prioritization

    Uses multiple queues for different priority levels with atomic selection.
    Critical for HFT where order priority affects execution speed.
    """

    def __init__(self, capacity: int, num_priorities: int = 4):
        self.capacity = capacity
        self.num_priorities = num_priorities

        # Create separate queues for each priority level
        self.priority_queues = [
            SPSCQueue(capacity // num_priorities) for _ in range(num_priorities)
        ]

        # Priority selection state
        self.last_priority_served = 0
        self.priority_lock = threading.Lock()

        # Statistics
        self.stats = QueueStats(max_size=capacity)
        self.priority_stats = [QueueStats() for _ in range(num_priorities)]

    def enqueue(self, item: T, priority: int = 0) -> bool:
        """Enqueue item with priority (0 = highest priority)"""
        if priority >= self.num_priorities:
            priority = self.num_priorities - 1

        success = self.priority_queues[priority].enqueue(item)

        if success:
            self.stats.enqueues += 1
            self.priority_stats[priority].enqueues += 1
        else:
            self.stats.enqueue_failures += 1
            self.priority_stats[priority].enqueue_failures += 1

        return success

    def dequeue(self) -> Optional[T]:
        """Dequeue highest priority item available"""
        # Try each priority level starting from highest
        for priority in range(self.num_priorities):
            item = self.priority_queues[priority].dequeue()
            if item is not None:
                self.stats.dequeues += 1
                self.priority_stats[priority].dequeues += 1
                return item

        # No items available
        self.stats.dequeue_failures += 1
        return None

    def dequeue_round_robin(self) -> Optional[T]:
        """Dequeue using round-robin to prevent starvation"""
        with self.priority_lock:
            start_priority = self.last_priority_served

            # Try each priority starting from last served + 1
            for i in range(self.num_priorities):
                priority = (start_priority + i + 1) % self.num_priorities
                item = self.priority_queues[priority].dequeue()

                if item is not None:
                    self.last_priority_served = priority
                    self.stats.dequeues += 1
                    self.priority_stats[priority].dequeues += 1
                    return item

        self.stats.dequeue_failures += 1
        return None

    def size(self) -> int:
        """Total size across all priority levels"""
        return sum(q.size() for q in self.priority_queues)

    def size_by_priority(self, priority: int) -> int:
        """Size of specific priority queue"""
        if priority < self.num_priorities:
            return self.priority_queues[priority].size()
        return 0

    def is_empty(self) -> bool:
        """Check if all priority queues are empty"""
        return all(q.is_empty() for q in self.priority_queues)

    def is_full(self) -> bool:
        """Check if any priority queue is full"""
        return any(q.is_full() for q in self.priority_queues)

    def get_comprehensive_stats(self) -> dict:
        """Get detailed statistics for all priority levels"""
        return {
            "overall_stats": self.stats.__dict__,
            "priority_stats": [stats.__dict__ for stats in self.priority_stats],
            "queue_sizes": [q.size() for q in self.priority_queues],
            "num_priorities": self.num_priorities,
            "total_size": self.size(),
        }


# Performance testing and benchmarking
class QueueBenchmark:
    """Benchmark suite for lock-free queue implementations"""

    @staticmethod
    def benchmark_spsc(iterations: int = 100000) -> dict:
        """Benchmark SPSC queue performance"""
        queue = SPSCQueue(1024)

        # Single producer, single consumer test
        def producer():
            for i in range(iterations):
                while not queue.enqueue(i):
                    pass  # Retry until successful

        def consumer():
            consumed = 0
            while consumed < iterations:
                item = queue.dequeue()
                if item is not None:
                    consumed += 1

        # Measure performance
        start_time = time.time()

        producer_thread = threading.Thread(target=producer)
        consumer_thread = threading.Thread(target=consumer)

        producer_thread.start()
        consumer_thread.start()

        producer_thread.join()
        consumer_thread.join()

        duration = time.time() - start_time
        stats = queue.get_stats()

        return {
            "queue_type": "SPSC",
            "iterations": iterations,
            "duration_seconds": duration,
            "throughput_ops_per_sec": iterations / duration,
            "stats": stats.__dict__,
        }

    @staticmethod
    def benchmark_mpmc(
        iterations: int = 100000, num_producers: int = 2, num_consumers: int = 2
    ) -> dict:
        """Benchmark MPMC queue performance"""
        queue = MPMCQueue(1024)
        completed_operations = threading.Event()
        operations_counter = threading.Barrier(num_producers + num_consumers + 1)

        def producer(producer_id: int):
            items_per_producer = iterations // num_producers
            for i in range(items_per_producer):
                value = producer_id * items_per_producer + i
                while not queue.enqueue(value):
                    time.sleep(0.0001)  # Small backoff
            operations_counter.wait()

        def consumer(consumer_id: int):
            consumed = 0
            target = iterations // num_consumers
            while consumed < target:
                item = queue.dequeue()
                if item is not None:
                    consumed += 1
                else:
                    time.sleep(0.0001)  # Small backoff
            operations_counter.wait()

        # Start benchmark
        start_time = time.time()

        # Create threads
        threads = []

        for i in range(num_producers):
            t = threading.Thread(target=producer, args=(i,))
            threads.append(t)
            t.start()

        for i in range(num_consumers):
            t = threading.Thread(target=consumer, args=(i,))
            threads.append(t)
            t.start()

        # Wait for completion
        operations_counter.wait()  # Wait for all operations to complete

        for t in threads:
            t.join()

        duration = time.time() - start_time
        stats = queue.get_stats()

        return {
            "queue_type": "MPMC",
            "iterations": iterations,
            "num_producers": num_producers,
            "num_consumers": num_consumers,
            "duration_seconds": duration,
            "throughput_ops_per_sec": iterations / duration,
            "stats": stats.__dict__,
        }


# Example usage and testing
if __name__ == "__main__":
    print("Lock-Free Queue Performance Benchmark")
    print("=" * 50)

    # Benchmark SPSC queue
    print("Testing SPSC Queue...")
    spsc_results = QueueBenchmark.benchmark_spsc(100000)
    print(f"SPSC Throughput: {spsc_results['throughput_ops_per_sec']:,.0f} ops/second")
    print(f"SPSC Duration: {spsc_results['duration_seconds']:.4f} seconds")

    # Benchmark MPMC queue
    print("\nTesting MPMC Queue...")
    mpmc_results = QueueBenchmark.benchmark_mpmc(100000, 2, 2)
    print(f"MPMC Throughput: {mpmc_results['throughput_ops_per_sec']:,.0f} ops/second")
    print(f"MPMC Duration: {mpmc_results['duration_seconds']:.4f} seconds")

    # Test priority queue
    print("\nTesting Priority Queue...")
    pqueue = PriorityLockFreeQueue(1000, 4)

    # Add items with different priorities
    for i in range(100):
        priority = i % 4
        pqueue.enqueue(f"item_{i}", priority)

    # Dequeue items (should get highest priority first)
    dequeued_items = []
    while not pqueue.is_empty():
        item = pqueue.dequeue()
        if item:
            dequeued_items.append(item)

    print(f"Priority queue dequeued {len(dequeued_items)} items")
    print(f"First 10 items: {dequeued_items[:10]}")

    stats = pqueue.get_comprehensive_stats()
    print(f"Priority queue stats: {stats}")

    print("\nAll benchmarks completed!")
