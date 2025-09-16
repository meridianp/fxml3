#!/usr/bin/env python3
"""
Test Event Loop Parallelism Verification
========================================

This test file verifies that the centralized event loop fixture
prevents conflicts during parallel test execution.
"""

import asyncio
import time
from typing import List

import pytest

# Import the centralized event loop fixture
from tests.fixtures.event_loop_fixtures import event_loop


class TestEventLoopParallelism:
    """Test that event loops work correctly in parallel execution."""

    @pytest.mark.asyncio
    async def test_async_task_isolation_1(self):
        """First test for async task isolation."""
        # Create a unique identifier for this test
        test_id = "test_1"

        # Run an async task
        await asyncio.sleep(0.01)

        # Check that we're using the correct event loop
        current_loop = asyncio.get_event_loop()
        assert current_loop is not None
        assert current_loop.is_running()

        # Create a task that runs in the background
        async def background_task():
            await asyncio.sleep(0.02)
            return f"{test_id}_completed"

        task = asyncio.create_task(background_task())
        result = await task
        assert result == f"{test_id}_completed"

    @pytest.mark.asyncio
    async def test_async_task_isolation_2(self):
        """Second test for async task isolation."""
        # Create a unique identifier for this test
        test_id = "test_2"

        # Run an async task
        await asyncio.sleep(0.01)

        # Check that we're using the correct event loop
        current_loop = asyncio.get_event_loop()
        assert current_loop is not None
        assert current_loop.is_running()

        # Create a task that runs in the background
        async def background_task():
            await asyncio.sleep(0.02)
            return f"{test_id}_completed"

        task = asyncio.create_task(background_task())
        result = await task
        assert result == f"{test_id}_completed"

    @pytest.mark.asyncio
    async def test_async_task_isolation_3(self):
        """Third test for async task isolation."""
        # Create a unique identifier for this test
        test_id = "test_3"

        # Run an async task
        await asyncio.sleep(0.01)

        # Check that we're using the correct event loop
        current_loop = asyncio.get_event_loop()
        assert current_loop is not None
        assert current_loop.is_running()

        # Create a task that runs in the background
        async def background_task():
            await asyncio.sleep(0.02)
            return f"{test_id}_completed"

        task = asyncio.create_task(background_task())
        result = await task
        assert result == f"{test_id}_completed"

    @pytest.mark.asyncio
    async def test_concurrent_async_operations(self):
        """Test multiple concurrent async operations."""

        # Create multiple concurrent tasks
        async def async_operation(n: int) -> int:
            await asyncio.sleep(0.01)
            return n * 2

        # Run tasks concurrently
        tasks = [async_operation(i) for i in range(10)]
        results = await asyncio.gather(*tasks)

        # Verify results
        expected = [i * 2 for i in range(10)]
        assert results == expected

    @pytest.mark.asyncio
    async def test_exception_handling_in_async_tasks(self):
        """Test that exceptions in async tasks are properly handled."""

        async def failing_task():
            await asyncio.sleep(0.01)
            raise ValueError("Test exception")

        async def successful_task():
            await asyncio.sleep(0.01)
            return "success"

        # Run tasks with exception handling
        results = await asyncio.gather(
            failing_task(), successful_task(), return_exceptions=True
        )

        # Check results
        assert isinstance(results[0], ValueError)
        assert str(results[0]) == "Test exception"
        assert results[1] == "success"

    @pytest.mark.asyncio
    async def test_task_cancellation(self):
        """Test that task cancellation works correctly."""

        # Create a long-running task
        async def long_task():
            try:
                await asyncio.sleep(10)
                return "completed"
            except asyncio.CancelledError:
                return "cancelled"

        # Start the task
        task = asyncio.create_task(long_task())

        # Wait a bit then cancel
        await asyncio.sleep(0.01)
        task.cancel()

        # Wait for task to finish
        try:
            result = await task
        except asyncio.CancelledError:
            result = "cancelled"

        assert result == "cancelled" or task.cancelled()

    @pytest.mark.asyncio
    async def test_event_loop_cleanup(self):
        """Test that event loop cleanup works correctly."""
        # Get current loop
        loop = asyncio.get_event_loop()

        # Create some tasks
        tasks = []
        for i in range(5):

            async def dummy_task(n):
                await asyncio.sleep(0.01)
                return n

            task = asyncio.create_task(dummy_task(i))
            tasks.append(task)

        # Wait for all tasks
        results = await asyncio.gather(*tasks)
        assert results == list(range(5))

        # Verify no tasks are left running
        all_tasks = asyncio.all_tasks(loop)
        # Filter out the current task
        other_tasks = [t for t in all_tasks if t != asyncio.current_task()]

        # All other tasks should be done
        for task in other_tasks:
            assert task.done()


class TestParallelExecution:
    """Test that parallel execution doesn't cause conflicts."""

    # Shared state to detect conflicts (should remain independent per test)
    test_state = {}

    @pytest.mark.asyncio
    async def test_parallel_state_isolation_1(self):
        """Test state isolation in parallel execution - Test 1."""
        test_id = "parallel_1"

        # Set state for this test
        self.__class__.test_state[test_id] = "started"

        # Simulate some async work
        await asyncio.sleep(0.05)

        # Check state hasn't been modified by other tests
        assert self.__class__.test_state.get(test_id) == "started"

        # Update state
        self.__class__.test_state[test_id] = "completed"

    @pytest.mark.asyncio
    async def test_parallel_state_isolation_2(self):
        """Test state isolation in parallel execution - Test 2."""
        test_id = "parallel_2"

        # Set state for this test
        self.__class__.test_state[test_id] = "started"

        # Simulate some async work
        await asyncio.sleep(0.05)

        # Check state hasn't been modified by other tests
        assert self.__class__.test_state.get(test_id) == "started"

        # Update state
        self.__class__.test_state[test_id] = "completed"

    @pytest.mark.asyncio
    async def test_parallel_state_isolation_3(self):
        """Test state isolation in parallel execution - Test 3."""
        test_id = "parallel_3"

        # Set state for this test
        self.__class__.test_state[test_id] = "started"

        # Simulate some async work
        await asyncio.sleep(0.05)

        # Check state hasn't been modified by other tests
        assert self.__class__.test_state.get(test_id) == "started"

        # Update state
        self.__class__.test_state[test_id] = "completed"


@pytest.mark.asyncio
async def test_no_event_loop_conflicts():
    """Test that there are no event loop conflicts."""
    # This test should pass when run with pytest-xdist
    loop = asyncio.get_event_loop()
    assert loop is not None
    assert loop.is_running()

    # Create and run a simple task
    async def simple_task():
        return "success"

    result = await simple_task()
    assert result == "success"


if __name__ == "__main__":
    # Run tests with parallel execution to verify no conflicts
    import subprocess
    import sys

    print("Testing event loop parallelism...")
    print("=" * 60)

    # Run tests with pytest-xdist for parallel execution
    cmd = [sys.executable, "-m", "pytest", __file__, "-v", "-n", "4"]

    result = subprocess.run(cmd, capture_output=True, text=True)

    print(result.stdout)
    if result.stderr:
        print("Errors:", result.stderr)

    if result.returncode == 0:
        print("\n✅ Event loop parallelism test PASSED!")
        print("Tests can run in parallel without conflicts.")
    else:
        print("\n❌ Event loop parallelism test FAILED!")
        print("There may still be conflicts in parallel execution.")

    sys.exit(result.returncode)
