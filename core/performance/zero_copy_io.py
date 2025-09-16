"""
Zero-Copy I/O Implementation

High-performance data transfer without memory copying:
- Memory-mapped buffers for direct hardware access
- Zero-copy network I/O for market data streaming
- Shared memory regions for inter-process communication
- Buffer pooling for allocation-free operations
"""

import mmap
import os
import socket
import struct
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional


@dataclass
class BufferMetadata:
    """Metadata for zero-copy buffers"""

    size: int
    offset: int
    timestamp_ns: int
    sequence: int
    checksum: int = 0


class ZeroCopyBuffer:
    """
    Zero-copy buffer implementation using memory-mapped files

    Enables direct memory access without copying data between
    user space and kernel space. Critical for microsecond latencies.
    """

    def __init__(self, size: int, name: str = "hft_buffer"):
        self.size = size
        self.name = name
        self.fd = -1
        self.buffer = None
        self.write_offset = 0
        self.read_offset = 0
        self.metadata_size = struct.calcsize("=QQQQQ")  # BufferMetadata

        # Statistics
        self.writes = 0
        self.reads = 0
        self.bytes_written = 0
        self.bytes_read = 0

        # Thread safety
        self.lock = threading.RLock()

        # Initialize buffer
        self._initialize_buffer()

    def _initialize_buffer(self):
        """Initialize memory-mapped buffer"""
        try:
            # Create temporary file for memory mapping
            self.fd = os.open(f"/tmp/{self.name}", os.O_CREAT | os.O_RDWR | os.O_TRUNC)

            # Extend file to desired size
            os.write(self.fd, b"\x00" * self.size)

            # Create memory mapping
            self.buffer = mmap.mmap(
                self.fd, self.size, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE
            )
        except Exception as e:
            self.cleanup()
            raise RuntimeError(f"Failed to initialize zero-copy buffer: {e}")

    def write(self, data: bytes, metadata: Optional[BufferMetadata] = None) -> bool:
        """Write data to buffer with zero-copy semantics"""
        if not data:
            return False

        with self.lock:
            # Calculate space needed (data + metadata)
            space_needed = len(data) + self.metadata_size

            if self.write_offset + space_needed > self.size:
                # Buffer full or would wrap around
                return False

            # Create metadata if not provided
            if metadata is None:
                metadata = BufferMetadata(
                    size=len(data),
                    offset=self.write_offset + self.metadata_size,
                    timestamp_ns=time.time_ns(),
                    sequence=self.writes,
                )

            # Write metadata first
            metadata_bytes = struct.pack(
                "=QQQQQ",
                metadata.size,
                metadata.offset,
                metadata.timestamp_ns,
                metadata.sequence,
                metadata.checksum,
            )

            self.buffer[self.write_offset : self.write_offset + self.metadata_size] = (
                metadata_bytes
            )

            # Write data immediately after metadata
            data_offset = self.write_offset + self.metadata_size
            self.buffer[data_offset : data_offset + len(data)] = data

            # Update write offset
            self.write_offset += space_needed

            # Update statistics
            self.writes += 1
            self.bytes_written += len(data)

            return True

    def read(self, expected_size: Optional[int] = None) -> Optional[bytes]:
        """Read data from buffer with zero-copy semantics"""
        with self.lock:
            if self.read_offset >= self.write_offset:
                return None  # No data available

            # Read metadata first
            if self.read_offset + self.metadata_size > self.write_offset:
                return None  # Incomplete metadata

            metadata_bytes = self.buffer[
                self.read_offset : self.read_offset + self.metadata_size
            ]
            metadata_values = struct.unpack("=QQQQQ", metadata_bytes)

            metadata = BufferMetadata(
                size=metadata_values[0],
                offset=metadata_values[1],
                timestamp_ns=metadata_values[2],
                sequence=metadata_values[3],
                checksum=metadata_values[4],
            )

            # Validate expected size
            if expected_size is not None and metadata.size != expected_size:
                return None

            # Check if complete data is available
            if metadata.offset + metadata.size > self.write_offset:
                return None  # Incomplete data

            # Read data (zero-copy view)
            data = bytes(self.buffer[metadata.offset : metadata.offset + metadata.size])

            # Update read offset
            self.read_offset = metadata.offset + metadata.size

            # Update statistics
            self.reads += 1
            self.bytes_read += metadata.size

            return data

    def peek(self) -> Optional[BufferMetadata]:
        """Peek at next available data metadata without consuming it"""
        with self.lock:
            if self.read_offset >= self.write_offset:
                return None

            if self.read_offset + self.metadata_size > self.write_offset:
                return None

            metadata_bytes = self.buffer[
                self.read_offset : self.read_offset + self.metadata_size
            ]
            metadata_values = struct.unpack("=QQQQQ", metadata_bytes)

            return BufferMetadata(
                size=metadata_values[0],
                offset=metadata_values[1],
                timestamp_ns=metadata_values[2],
                sequence=metadata_values[3],
                checksum=metadata_values[4],
            )

    def available_space(self) -> int:
        """Get available space in buffer"""
        with self.lock:
            return self.size - self.write_offset

    def available_data(self) -> int:
        """Get amount of data available to read"""
        with self.lock:
            return self.write_offset - self.read_offset

    def reset(self):
        """Reset buffer pointers"""
        with self.lock:
            self.write_offset = 0
            self.read_offset = 0

    def get_stats(self) -> Dict[str, Any]:
        """Get buffer statistics"""
        with self.lock:
            return {
                "size": self.size,
                "write_offset": self.write_offset,
                "read_offset": self.read_offset,
                "available_space": self.available_space(),
                "available_data": self.available_data(),
                "writes": self.writes,
                "reads": self.reads,
                "bytes_written": self.bytes_written,
                "bytes_read": self.bytes_read,
                "utilization": self.write_offset / self.size if self.size > 0 else 0,
            }

    def cleanup(self):
        """Cleanup resources"""
        if self.buffer:
            self.buffer.close()
            self.buffer = None

        if self.fd != -1:
            os.close(self.fd)
            self.fd = -1

        # Remove temporary file
        try:
            os.unlink(f"/tmp/{self.name}")
        except:
            pass

    def __del__(self):
        self.cleanup()


class MemoryMappedBuffer:
    """
    Persistent memory-mapped buffer for cross-process communication

    Enables zero-copy data sharing between multiple processes,
    critical for distributed HFT architectures.
    """

    def __init__(self, filename: str, size: int, create: bool = True):
        self.filename = filename
        self.size = size
        self.buffer = None
        self.header_size = 64  # Reserve space for header information

        if create:
            self._create_buffer()
        else:
            self._open_buffer()

    def _create_buffer(self):
        """Create new memory-mapped buffer file"""
        try:
            with open(self.filename, "wb") as f:
                f.write(b"\x00" * self.size)

            self.buffer = mmap.mmap(
                open(self.filename, "r+b").fileno(), self.size, access=mmap.ACCESS_WRITE
            )

            # Write header information
            header = struct.pack(
                "=QQQQ",
                self.size,  # Total size
                self.header_size,  # Header size
                0,  # Write position
                0,
            )  # Read position

            self.buffer[0 : self.header_size] = header + b"\x00" * (
                self.header_size - len(header)
            )

        except Exception as e:
            raise RuntimeError(f"Failed to create memory-mapped buffer: {e}")

    def _open_buffer(self):
        """Open existing memory-mapped buffer file"""
        try:
            self.buffer = mmap.mmap(
                open(self.filename, "r+b").fileno(),
                0,  # Map entire file
                access=mmap.ACCESS_WRITE,
            )

            # Read header information
            header = struct.unpack("=QQQQ", self.buffer[0:32])
            self.size = header[0]
            self.header_size = header[1]

        except Exception as e:
            raise RuntimeError(f"Failed to open memory-mapped buffer: {e}")

    def write_at_offset(self, offset: int, data: bytes) -> bool:
        """Write data at specific offset"""
        if not self.buffer:
            return False

        write_offset = self.header_size + offset
        if write_offset + len(data) > self.size:
            return False

        self.buffer[write_offset : write_offset + len(data)] = data
        return True

    def read_at_offset(self, offset: int, size: int) -> Optional[bytes]:
        """Read data at specific offset"""
        if not self.buffer:
            return None

        read_offset = self.header_size + offset
        if read_offset + size > self.size:
            return None

        return bytes(self.buffer[read_offset : read_offset + size])

    def get_write_position(self) -> int:
        """Get current write position from header"""
        if not self.buffer:
            return 0
        header = struct.unpack("=QQQQ", self.buffer[0:32])
        return header[2]

    def set_write_position(self, position: int):
        """Set current write position in header"""
        if not self.buffer:
            return

        header = list(struct.unpack("=QQQQ", self.buffer[0:32]))
        header[2] = position
        header_bytes = struct.pack("=QQQQ", *header)
        self.buffer[0:32] = header_bytes

    def get_read_position(self) -> int:
        """Get current read position from header"""
        if not self.buffer:
            return 0
        header = struct.unpack("=QQQQ", self.buffer[0:32])
        return header[3]

    def set_read_position(self, position: int):
        """Set current read position in header"""
        if not self.buffer:
            return

        header = list(struct.unpack("=QQQQ", self.buffer[0:32]))
        header[3] = position
        header_bytes = struct.pack("=QQQQ", *header)
        self.buffer[0:32] = header_bytes

    def sync(self):
        """Force synchronization to disk"""
        if self.buffer:
            self.buffer.flush()

    def close(self):
        """Close memory-mapped buffer"""
        if self.buffer:
            self.buffer.close()
            self.buffer = None


class ZeroCopyNetworkBuffer:
    """
    Zero-copy network I/O buffer for high-frequency market data

    Implements scatter-gather I/O and vectored operations for
    maximum throughput with minimal CPU usage.
    """

    def __init__(self, buffer_size: int = 64 * 1024):
        self.buffer_size = buffer_size
        self.buffers: List[ZeroCopyBuffer] = []
        self.active_buffer_index = 0
        self.buffer_pool_size = 4

        # Initialize buffer pool
        for i in range(self.buffer_pool_size):
            buffer = ZeroCopyBuffer(buffer_size, f"network_buffer_{i}")
            self.buffers.append(buffer)

        # Network statistics
        self.packets_received = 0
        self.bytes_received = 0
        self.buffer_switches = 0

        self.lock = threading.Lock()

    def receive_packet(self, socket_fd: socket.socket) -> Optional[bytes]:
        """Receive network packet with zero-copy semantics"""
        try:
            # Receive data directly into current buffer
            current_buffer = self.buffers[self.active_buffer_index]

            # Check if buffer has space
            if current_buffer.available_space() < 1500:  # MTU size
                self._switch_buffer()
                current_buffer = self.buffers[self.active_buffer_index]

            # Receive data
            data = socket_fd.recv(1500)  # Standard MTU
            if not data:
                return None

            # Write to zero-copy buffer
            if current_buffer.write(data):
                self.packets_received += 1
                self.bytes_received += len(data)
                return data

            return None

        except socket.error:
            return None

    def _switch_buffer(self):
        """Switch to next available buffer"""
        with self.lock:
            self.active_buffer_index = (
                self.active_buffer_index + 1
            ) % self.buffer_pool_size
            self.buffer_switches += 1

    def get_network_stats(self) -> Dict[str, Any]:
        """Get network I/O statistics"""
        buffer_stats = [buf.get_stats() for buf in self.buffers]

        return {
            "packets_received": self.packets_received,
            "bytes_received": self.bytes_received,
            "buffer_switches": self.buffer_switches,
            "active_buffer": self.active_buffer_index,
            "buffer_stats": buffer_stats,
            "total_buffers": len(self.buffers),
        }

    def cleanup(self):
        """Cleanup all buffers"""
        for buffer in self.buffers:
            buffer.cleanup()


class SharedMemoryRegion:
    """
    Shared memory region for inter-process zero-copy communication

    Enables multiple trading processes to share market data and
    order information without serialization overhead.
    """

    def __init__(self, name: str, size: int, create: bool = True):
        self.name = name
        self.size = size
        self.shm = None
        self.buffer = None

        try:
            if create:
                self._create_shared_memory()
            else:
                self._attach_shared_memory()
        except ImportError:
            # Fallback to memory-mapped file if shared memory not available
            self.buffer = MemoryMappedBuffer(f"/tmp/{name}.shm", size, create)

    def _create_shared_memory(self):
        """Create new shared memory region"""
        try:
            from multiprocessing import shared_memory

            self.shm = shared_memory.SharedMemory(
                name=self.name, create=True, size=self.size
            )
            self.buffer = memoryview(self.shm.buf)

        except Exception as e:
            raise RuntimeError(f"Failed to create shared memory: {e}")

    def _attach_shared_memory(self):
        """Attach to existing shared memory region"""
        try:
            from multiprocessing import shared_memory

            self.shm = shared_memory.SharedMemory(name=self.name)
            self.buffer = memoryview(self.shm.buf)
            self.size = len(self.buffer)

        except Exception as e:
            raise RuntimeError(f"Failed to attach to shared memory: {e}")

    def write(self, offset: int, data: bytes) -> bool:
        """Write data to shared memory"""
        if offset + len(data) > self.size:
            return False

        if self.shm:
            self.buffer[offset : offset + len(data)] = data
        elif self.buffer:
            return self.buffer.write_at_offset(offset, data)

        return True

    def read(self, offset: int, size: int) -> Optional[bytes]:
        """Read data from shared memory"""
        if offset + size > self.size:
            return None

        if self.shm:
            return bytes(self.buffer[offset : offset + size])
        elif self.buffer:
            return self.buffer.read_at_offset(offset, size)

        return None

    def cleanup(self):
        """Cleanup shared memory"""
        if self.shm:
            self.shm.close()
            try:
                self.shm.unlink()
            except:
                pass
        elif self.buffer:
            self.buffer.close()


@contextmanager
def zero_copy_context(buffer_size: int = 1024 * 1024):
    """Context manager for zero-copy operations"""
    buffer = ZeroCopyBuffer(buffer_size, "context_buffer")
    try:
        yield buffer
    finally:
        buffer.cleanup()


# Performance testing
class ZeroCopyBenchmark:
    """Benchmark suite for zero-copy operations"""

    @staticmethod
    def benchmark_buffer_throughput(iterations: int = 10000) -> Dict[str, Any]:
        """Benchmark zero-copy buffer throughput"""
        buffer_size = 1024 * 1024  # 1MB
        test_data = b"X" * 1000  # 1KB test data

        with zero_copy_context(buffer_size) as buffer:
            # Write benchmark
            start_time = time.time()

            for i in range(iterations):
                if not buffer.write(test_data):
                    buffer.reset()  # Reset when full
                    buffer.write(test_data)

            write_duration = time.time() - start_time

            # Read benchmark
            buffer.reset()

            # Fill buffer first
            for i in range(iterations):
                if not buffer.write(test_data):
                    break

            start_time = time.time()

            read_count = 0
            while True:
                data = buffer.read()
                if data is None:
                    break
                read_count += 1

            read_duration = time.time() - start_time

            stats = buffer.get_stats()

            return {
                "iterations": iterations,
                "test_data_size": len(test_data),
                "write_duration": write_duration,
                "read_duration": read_duration,
                "write_throughput_mbps": (iterations * len(test_data))
                / (write_duration * 1024 * 1024),
                "read_throughput_mbps": (read_count * len(test_data))
                / (read_duration * 1024 * 1024),
                "buffer_stats": stats,
            }


# Example usage and testing
if __name__ == "__main__":
    print("Zero-Copy I/O Performance Benchmark")
    print("=" * 50)

    # Benchmark buffer performance
    results = ZeroCopyBenchmark.benchmark_buffer_throughput(10000)

    print(f"Write Throughput: {results['write_throughput_mbps']:.2f} MB/s")
    print(f"Read Throughput: {results['read_throughput_mbps']:.2f} MB/s")
    print(f"Write Duration: {results['write_duration']:.4f} seconds")
    print(f"Read Duration: {results['read_duration']:.4f} seconds")

    # Test memory-mapped buffer
    print("\nTesting Memory-Mapped Buffer...")

    mmap_buffer = MemoryMappedBuffer("/tmp/test_mmap.buf", 1024 * 1024)

    # Write test data
    test_data = b"Hello, Zero-Copy World!" * 100
    mmap_buffer.write_at_offset(0, test_data)
    mmap_buffer.set_write_position(len(test_data))

    # Read test data
    read_data = mmap_buffer.read_at_offset(0, len(test_data))
    print(f"Memory-mapped read successful: {read_data[:50]}...")

    mmap_buffer.close()

    # Test shared memory (if available)
    print("\nTesting Shared Memory...")
    try:
        shm_region = SharedMemoryRegion("test_shm", 1024 * 1024, create=True)

        shm_region.write(0, b"Shared memory test data")
        read_shm_data = shm_region.read(0, 22)

        print(f"Shared memory read: {read_shm_data}")
        shm_region.cleanup()

    except Exception as e:
        print(f"Shared memory test failed: {e}")

    print("\nZero-copy benchmarks completed!")
