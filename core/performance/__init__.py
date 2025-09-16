"""
FXML4 Performance Optimization Module

High-frequency trading performance optimizations for sub-millisecond execution.
Implements memory-mapped data structures, lock-free queues, and zero-copy I/O
for institutional-grade trading performance.
"""

from .hft_engine import HighFrequencyTradingEngine
from .latency_monitor import LatencyMonitor, MicrosecondTimer
from .lockfree_queue import LockFreeQueue, MPMCQueue, SPSCQueue
from .memory_pool import AlignedMemoryAllocator, MemoryPool
from .zero_copy_io import MemoryMappedBuffer, ZeroCopyBuffer

__all__ = [
    "HighFrequencyTradingEngine",
    "MemoryPool",
    "AlignedMemoryAllocator",
    "LockFreeQueue",
    "SPSCQueue",
    "MPMCQueue",
    "ZeroCopyBuffer",
    "MemoryMappedBuffer",
    "LatencyMonitor",
    "MicrosecondTimer",
]
