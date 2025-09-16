"""Test isolation and cleanup utilities.

This module provides utilities for test isolation, cleanup,
and environment management to ensure tests don't interfere with each other.
"""

import asyncio
import os
import shutil
import tempfile
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest


class TestIsolationManager:
    """Manages test isolation and cleanup."""

    def __init__(self):
        self.temp_directories = []
        self.temp_files = []
        self.environment_vars = {}
        self.patches = []
        self.cleanup_functions = []

    def create_temp_directory(self, prefix: str = "fxml4_test_") -> str:
        """Create a temporary directory for the test."""
        temp_dir = tempfile.mkdtemp(prefix=prefix)
        self.temp_directories.append(temp_dir)
        return temp_dir

    def create_temp_file(self, suffix: str = ".tmp", content: str = "") -> str:
        """Create a temporary file for the test."""
        fd, temp_file = tempfile.mkstemp(suffix=suffix)

        if content:
            with os.fdopen(fd, "w") as f:
                f.write(content)
        else:
            os.close(fd)

        self.temp_files.append(temp_file)
        return temp_file

    def set_environment_var(self, key: str, value: str):
        """Set an environment variable for the test."""
        original_value = os.environ.get(key)
        self.environment_vars[key] = original_value
        os.environ[key] = value

    def patch_object(self, target: str, **kwargs):
        """Create a patch for the test."""
        patcher = patch(target, **kwargs)
        mock_obj = patcher.start()
        self.patches.append(patcher)
        return mock_obj

    def register_cleanup(self, cleanup_func: Callable):
        """Register a cleanup function to be called at teardown."""
        self.cleanup_functions.append(cleanup_func)

    def cleanup(self):
        """Clean up all test resources."""
        # Call custom cleanup functions
        for cleanup_func in reversed(self.cleanup_functions):
            try:
                cleanup_func()
            except Exception as e:
                print(f"Warning: Cleanup function failed: {e}")

        # Stop all patches
        for patcher in reversed(self.patches):
            try:
                patcher.stop()
            except Exception as e:
                print(f"Warning: Failed to stop patch: {e}")

        # Restore environment variables
        for key, original_value in self.environment_vars.items():
            if original_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = original_value

        # Remove temporary files
        for temp_file in self.temp_files:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except Exception as e:
                print(f"Warning: Failed to remove temp file {temp_file}: {e}")

        # Remove temporary directories
        for temp_dir in self.temp_directories:
            try:
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
            except Exception as e:
                print(f"Warning: Failed to remove temp dir {temp_dir}: {e}")

        # Clear lists
        self.temp_directories.clear()
        self.temp_files.clear()
        self.environment_vars.clear()
        self.patches.clear()
        self.cleanup_functions.clear()


@pytest.fixture
def test_isolation():
    """Provide test isolation manager."""
    manager = TestIsolationManager()
    yield manager
    manager.cleanup()


@pytest.fixture
def isolated_environment():
    """Provide isolated environment for testing."""
    original_env = os.environ.copy()

    # Set test-specific environment
    test_env = {
        "TESTING": "1",
        "FXML4_TEST_MODE": "1",
        "FXML4_LOG_LEVEL": "WARNING",
        "FXML4_DISABLE_EXTERNAL_APIS": "1",
    }

    for key, value in test_env.items():
        os.environ[key] = value

    yield

    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture
def temp_workspace():
    """Provide a temporary workspace for file operations."""
    temp_dir = tempfile.mkdtemp(prefix="fxml4_workspace_")
    original_cwd = os.getcwd()

    try:
        os.chdir(temp_dir)
        yield temp_dir
    finally:
        os.chdir(original_cwd)
        shutil.rmtree(temp_dir, ignore_errors=True)


@contextmanager
def mock_file_system():
    """Mock file system operations for testing."""
    mock_open = MagicMock()
    mock_exists = MagicMock(return_value=True)
    mock_isfile = MagicMock(return_value=True)
    mock_isdir = MagicMock(return_value=True)

    with (
        patch("builtins.open", mock_open),
        patch("os.path.exists", mock_exists),
        patch("os.path.isfile", mock_isfile),
        patch("os.path.isdir", mock_isdir),
    ):
        yield {
            "open": mock_open,
            "exists": mock_exists,
            "isfile": mock_isfile,
            "isdir": mock_isdir,
        }


@contextmanager
def mock_network():
    """Mock network operations for testing."""
    mock_requests = MagicMock()
    mock_urllib = MagicMock()
    mock_socket = MagicMock()

    with (
        patch("requests.get", mock_requests.get),
        patch("requests.post", mock_requests.post),
        patch("urllib.request.urlopen", mock_urllib.urlopen),
        patch("socket.socket", mock_socket),
    ):
        yield {"requests": mock_requests, "urllib": mock_urllib, "socket": mock_socket}


@pytest.fixture
async def async_test_cleanup():
    """Async test cleanup manager."""
    cleanup_tasks = []

    async def register_cleanup(coro):
        """Register an async cleanup task."""
        cleanup_tasks.append(coro)

    yield register_cleanup

    # Run cleanup tasks
    for task in reversed(cleanup_tasks):
        try:
            if asyncio.iscoroutine(task):
                await task
            elif callable(task):
                await task()
        except Exception as e:
            print(f"Warning: Async cleanup failed: {e}")


@pytest.fixture
def memory_usage_monitor():
    """Monitor memory usage during tests."""
    try:
        import psutil

        process = psutil.Process()
    except ImportError:
        pytest.skip("psutil not available for memory monitoring")

    class MemoryMonitor:
        def __init__(self):
            self.initial_memory = process.memory_info().rss
            self.peak_memory = self.initial_memory
            self.measurements = []

        def measure(self, label: str = ""):
            """Take a memory measurement."""
            current = process.memory_info().rss
            self.peak_memory = max(self.peak_memory, current)
            self.measurements.append(
                {
                    "label": label,
                    "memory_mb": current / 1024 / 1024,
                    "delta_mb": (current - self.initial_memory) / 1024 / 1024,
                }
            )

        def get_summary(self):
            """Get memory usage summary."""
            return {
                "initial_mb": self.initial_memory / 1024 / 1024,
                "peak_mb": self.peak_memory / 1024 / 1024,
                "delta_mb": (self.peak_memory - self.initial_memory) / 1024 / 1024,
                "measurements": self.measurements,
            }

    return MemoryMonitor()


@pytest.fixture
def resource_limits():
    """Set resource limits for tests."""
    import resource

    # Get current limits
    old_limits = {}
    limit_types = ["RLIMIT_CPU", "RLIMIT_AS", "RLIMIT_FSIZE"]

    for limit_type in limit_types:
        if hasattr(resource, limit_type):
            limit_const = getattr(resource, limit_type)
            old_limits[limit_const] = resource.getrlimit(limit_const)

    # Set test limits
    try:
        # Limit CPU time to 60 seconds
        if hasattr(resource, "RLIMIT_CPU"):
            resource.setrlimit(resource.RLIMIT_CPU, (60, 60))

        # Limit memory to 1GB
        if hasattr(resource, "RLIMIT_AS"):
            resource.setrlimit(
                resource.RLIMIT_AS, (1024 * 1024 * 1024, 1024 * 1024 * 1024)
            )

        yield

    finally:
        # Restore original limits
        for limit_const, (soft, hard) in old_limits.items():
            try:
                resource.setrlimit(limit_const, (soft, hard))
            except Exception:
                pass  # Ignore errors when restoring limits


@contextmanager
def timeout_context(seconds: float):
    """Provide a timeout context for operations."""
    import signal

    def timeout_handler(signum, frame):
        raise TimeoutError(f"Operation timed out after {seconds} seconds")

    # Set up the timeout
    old_handler = signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(int(seconds))

    try:
        yield
    finally:
        # Clean up
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)


@pytest.fixture
def test_timeout():
    """Provide timeout context for tests."""
    return timeout_context


class ProcessIsolation:
    """Utilities for process-level test isolation."""

    @staticmethod
    @contextmanager
    def isolated_process():
        """Run code in an isolated subprocess."""
        import pickle
        import subprocess
        import sys

        def run_in_subprocess(func, *args, **kwargs):
            """Run function in subprocess and return result."""
            code = f"""
import pickle
import sys
sys.path.insert(0, '{os.getcwd()}')

func = pickle.loads({pickle.dumps(func)!r})
args = pickle.loads({pickle.dumps(args)!r})
kwargs = pickle.loads({pickle.dumps(kwargs)!r})

try:
    result = func(*args, **kwargs)
    print(pickle.dumps(('success', result)).decode('latin-1'))
except Exception as e:
    print(pickle.dumps(('error', str(e))).decode('latin-1'))
"""

            result = subprocess.run(
                [sys.executable, "-c", code], capture_output=True, text=True
            )

            if result.returncode != 0:
                raise RuntimeError(f"Subprocess failed: {result.stderr}")

            status, data = pickle.loads(result.stdout.encode("latin-1"))
            if status == "error":
                raise RuntimeError(f"Function failed in subprocess: {data}")

            return data

        yield run_in_subprocess


@pytest.fixture
def process_isolation():
    """Provide process isolation utilities."""
    return ProcessIsolation()


@pytest.fixture(autouse=True)
def test_cleanup_validation():
    """Validate that tests properly clean up resources."""
    # Record initial state
    initial_files = set(os.listdir(".")) if os.path.exists(".") else set()
    initial_env_vars = dict(os.environ)

    yield

    # Check for cleanup issues
    if os.path.exists("."):
        final_files = set(os.listdir("."))
        new_files = final_files - initial_files
        if new_files:
            print(f"Warning: Test left behind files: {new_files}")

    # Check for environment variable leaks
    final_env_vars = dict(os.environ)
    for key, value in final_env_vars.items():
        if key not in initial_env_vars and not key.startswith("PYTEST_"):
            print(f"Warning: Test left behind environment variable: {key}={value}")


# Async isolation utilities
@asynccontextmanager
async def async_timeout(seconds: float):
    """Async timeout context."""
    try:
        async with asyncio.timeout(seconds):
            yield
    except asyncio.TimeoutError:
        raise TimeoutError(f"Async operation timed out after {seconds} seconds")


@pytest.fixture
def async_isolation():
    """Provide async test isolation utilities."""

    class AsyncIsolation:
        def __init__(self):
            self.tasks = []
            self.contexts = []

        def create_task(self, coro):
            """Create and track an async task."""
            task = asyncio.create_task(coro)
            self.tasks.append(task)
            return task

        async def cleanup(self):
            """Cancel all tracked tasks."""
            for task in self.tasks:
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass

        def timeout(self, seconds: float):
            """Return async timeout context."""
            return async_timeout(seconds)

    manager = AsyncIsolation()
    yield manager

    # Cleanup
    if manager.tasks:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(manager.cleanup())
        else:
            loop.run_until_complete(manager.cleanup())
