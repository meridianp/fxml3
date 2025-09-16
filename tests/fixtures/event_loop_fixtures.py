"""
Centralized Event Loop Fixtures for FXML4 Test Suite
====================================================

This module provides a single, centralized event loop configuration to prevent
conflicts during parallel test execution with pytest-xdist.

Key Features:
- Single session-scoped event loop for all async tests
- Proper cleanup and isolation
- Compatible with pytest-asyncio
- Prevents event loop conflicts in parallel execution
"""

import asyncio
import sys
from typing import Generator

import pytest


def pytest_configure(config):
    """Configure pytest-asyncio to use our centralized event loop."""
    # Ensure pytest-asyncio uses our event loop policy
    if sys.platform == "win32":
        # Windows requires ProactorEventLoop for subprocess support
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    else:
        # Use the default event loop policy for Unix-like systems
        asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())


@pytest.fixture(scope="session")
def event_loop_policy():
    """
    Create and configure the event loop policy for the test session.

    This ensures consistent event loop behavior across all tests.
    """
    if sys.platform == "win32":
        policy = asyncio.WindowsProactorEventLoopPolicy()
    else:
        policy = asyncio.DefaultEventLoopPolicy()

    asyncio.set_event_loop_policy(policy)
    return policy


@pytest.fixture(scope="session")
def event_loop(event_loop_policy) -> Generator[asyncio.AbstractEventLoop, None, None]:
    """
    Create a single event loop for the entire test session.

    This fixture prevents event loop conflicts when running tests in parallel
    with pytest-xdist. All async tests will share this event loop, but each
    test's tasks are properly isolated.

    Returns:
        asyncio.AbstractEventLoop: The session-wide event loop
    """
    # Create a new event loop
    loop = event_loop_policy.new_event_loop()

    # Set as the current event loop
    asyncio.set_event_loop(loop)

    # Configure the loop for testing
    loop.set_debug(True)  # Enable debug mode for better error messages

    try:
        yield loop
    finally:
        # Clean up any pending tasks
        try:
            # Cancel all remaining tasks
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()

            # Wait for all tasks to complete cancellation
            if pending:
                loop.run_until_complete(
                    asyncio.gather(*pending, return_exceptions=True)
                )
        except Exception:
            pass  # Ignore cleanup errors

        # Close the event loop
        loop.close()

        # Reset the event loop policy
        asyncio.set_event_loop_policy(None)


@pytest.fixture
async def async_client(event_loop):
    """
    Fixture for creating async clients with proper event loop binding.

    This ensures that any async client created in tests uses the centralized
    event loop, preventing conflicts.
    """
    # Ensure the event loop is set for this thread
    asyncio.set_event_loop(event_loop)

    # Return the event loop for client creation
    return event_loop


@pytest.fixture(autouse=True)
async def cleanup_tasks(event_loop):
    """
    Automatically cleanup tasks after each test.

    This fixture runs after each test to ensure no tasks leak between tests,
    maintaining proper isolation.
    """
    yield

    # Get all tasks for this event loop
    tasks = [
        task
        for task in asyncio.all_tasks(event_loop)
        if not task.done() and task != asyncio.current_task()
    ]

    # Cancel any remaining tasks
    for task in tasks:
        task.cancel()

    # Wait for cancellation to complete
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


@pytest.fixture
async def isolated_async_context(event_loop):
    """
    Provide an isolated async context for tests that need complete isolation.

    This fixture creates a subprocess with its own event loop for tests that
    absolutely cannot share the session event loop.
    """
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:

        def run_isolated():
            # Create a new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop

        # Create isolated loop in separate thread
        isolated_loop = await event_loop.run_in_executor(executor, run_isolated)

        try:
            yield isolated_loop
        finally:
            # Clean up the isolated loop
            def cleanup():
                isolated_loop.close()

            await event_loop.run_in_executor(executor, cleanup)


# Compatibility markers for pytest-asyncio
pytest_plugins = ["pytest_asyncio"]


def pytest_collection_modifyitems(config, items):
    """
    Add asyncio marker to all async tests automatically.

    This ensures all async tests are properly marked and use our event loop.
    """
    for item in items:
        if asyncio.iscoroutinefunction(item.function):
            item.add_marker(pytest.mark.asyncio)
