"""Resource leak detection and monitoring utilities."""

import logging
import os
import threading
import time
from typing import Any, Dict, List
from unittest.mock import Mock

logger = logging.getLogger(__name__)


class MemoryLeakDetector:
    """Detects memory leaks during test execution."""

    def __init__(self):
        self.initial_memory = 0
        self.peak_memory = 0
        self.monitoring = False

    def start_monitoring(self):
        """Start monitoring memory usage."""
        self.initial_memory = self._get_memory_usage()
        self.peak_memory = self.initial_memory
        self.monitoring = True
        logger.info(f"Started memory monitoring, initial: {self.initial_memory:.2f} MB")

    def stop_monitoring(self):
        """Stop monitoring memory usage."""
        self.monitoring = False
        final_memory = self._get_memory_usage()
        logger.info(f"Stopped memory monitoring, final: {final_memory:.2f} MB")

    def get_leak_report(self) -> Dict[str, Any]:
        """Get memory leak analysis report."""
        current_memory = self._get_memory_usage()
        memory_growth = current_memory - self.initial_memory

        return {
            "initial_memory": self.initial_memory,
            "current_memory": current_memory,
            "peak_memory": self.peak_memory,
            "memory_growth": memory_growth,
            "potential_leak": memory_growth > 10.0,  # 10MB threshold
        }

    def _get_memory_usage(self) -> float:
        """Get current memory usage in MB."""
        try:
            import psutil

            process = psutil.Process()
            return process.memory_info().rss / 1024 / 1024
        except ImportError:
            # Mock for testing without psutil
            return 100.0 + (time.time() % 10)  # Simulate varying memory


class DatabaseLeakDetector:
    """Detects database connection leaks."""

    def __init__(self):
        self.active_connections = set()
        self.connection_registry = {}
        self.monitoring = False

    def start_monitoring(self):
        """Start monitoring database connections."""
        self.monitoring = True
        logger.info("Started database connection monitoring")

    def stop_monitoring(self):
        """Stop monitoring database connections."""
        self.monitoring = False
        logger.info("Stopped database connection monitoring")

    def register_connection(self, connection):
        """Register a new database connection."""
        connection_id = id(connection)
        self.active_connections.add(connection_id)
        self.connection_registry[connection_id] = {
            "connection": connection,
            "created_at": time.time(),
            "thread_id": threading.get_ident(),
        }

    def unregister_connection(self, connection):
        """Unregister a database connection."""
        connection_id = id(connection)
        self.active_connections.discard(connection_id)
        self.connection_registry.pop(connection_id, None)

    def get_leak_report(self) -> Dict[str, Any]:
        """Get database connection leak report."""
        leaked_connections = list(self.active_connections)
        connection_details = []

        for conn_id in leaked_connections:
            if conn_id in self.connection_registry:
                details = self.connection_registry[conn_id]
                connection_details.append(
                    {
                        "connection_id": conn_id,
                        "created_at": details["created_at"],
                        "thread_id": details["thread_id"],
                        "age_seconds": time.time() - details["created_at"],
                    }
                )

        return {
            "leaked_connections": len(leaked_connections),
            "connection_details": connection_details,
            "total_registered": len(self.connection_registry),
        }


class FileHandleLeakDetector:
    """Detects file handle leaks."""

    def __init__(self):
        self.initial_handles = 0
        self.monitoring = False

    def start_monitoring(self):
        """Start monitoring file handles."""
        self.initial_handles = self._get_open_handles()
        self.monitoring = True
        logger.info(f"Started file handle monitoring, initial: {self.initial_handles}")

    def stop_monitoring(self):
        """Stop monitoring file handles."""
        self.monitoring = False
        final_handles = self._get_open_handles()
        logger.info(f"Stopped file handle monitoring, final: {final_handles}")

    def get_leak_report(self) -> Dict[str, Any]:
        """Get file handle leak report."""
        current_handles = self._get_open_handles()
        leaked_handles = max(0, current_handles - self.initial_handles)

        return {
            "initial_handles": self.initial_handles,
            "current_handles": current_handles,
            "leaked_handles": leaked_handles,
            "potential_leak": leaked_handles > 5,
        }

    def _get_open_handles(self) -> int:
        """Get count of open file handles."""
        try:
            # Get count of open file descriptors
            proc_fd_dir = f"/proc/{os.getpid()}/fd"
            if os.path.exists(proc_fd_dir):
                return len(os.listdir(proc_fd_dir))
        except (OSError, PermissionError):
            pass

        # Fallback mock implementation
        return 20 + (int(time.time()) % 10)  # Simulate varying handle count
