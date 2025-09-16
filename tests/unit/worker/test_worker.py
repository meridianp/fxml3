"""Unit tests for the worker module."""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest

from fxml4.worker.main import WorkerManager


class TestWorkerManager:
    """Test the WorkerManager class."""

    def test_init_default_config(self):
        """Test WorkerManager initialization with default config."""
        manager = WorkerManager()
        assert manager.worker_name == "fxml4-worker"
        assert manager.poll_interval == 60
        assert manager.max_concurrent_tasks == 5
        assert manager.running is False
        assert len(manager.tasks) == 0

    def test_init_custom_config(self):
        """Test WorkerManager initialization with custom config."""
        config = {"name": "test-worker", "poll_interval": 30, "max_concurrent_tasks": 3}
        manager = WorkerManager(config)
        assert manager.worker_name == "test-worker"
        assert manager.poll_interval == 30
        assert manager.max_concurrent_tasks == 3

    @pytest.mark.asyncio
    async def test_start_and_stop(self):
        """Test starting and stopping the worker manager."""
        manager = WorkerManager({"poll_interval": 0.1})  # Fast polling for test

        # Start the manager in the background
        start_task = asyncio.create_task(manager.start())

        # Give it a moment to start
        await asyncio.sleep(0.05)
        assert manager.running is True

        # Stop the manager
        await manager.stop()
        assert manager.running is False

        # Cancel the start task
        start_task.cancel()
        try:
            await start_task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_cleanup_completed_tasks(self):
        """Test cleanup of completed tasks."""
        manager = WorkerManager()

        # Create mock completed tasks
        completed_task = Mock()
        completed_task.done.return_value = True
        completed_task.exception.return_value = None

        pending_task = Mock()
        pending_task.done.return_value = False

        manager.tasks = [completed_task, pending_task]

        manager._cleanup_completed_tasks()

        # Only pending task should remain
        assert len(manager.tasks) == 1
        assert manager.tasks[0] == pending_task

    @pytest.mark.asyncio
    async def test_cleanup_completed_tasks_with_exception(self):
        """Test cleanup of tasks that completed with exception."""
        manager = WorkerManager()

        # Create mock task that completed with exception
        failed_task = Mock()
        failed_task.done.return_value = True
        failed_task.exception.return_value = Exception("Task failed")

        manager.tasks = [failed_task]

        manager._cleanup_completed_tasks()

        # Failed task should be removed
        assert len(manager.tasks) == 0

    @pytest.mark.asyncio
    async def test_run_task_data_refresh(self):
        """Test running data refresh task."""
        manager = WorkerManager()

        task_config = {"name": "data_refresh", "description": "Refresh market data"}

        # Mock the data refresh method
        manager._refresh_data = AsyncMock()

        await manager._run_task(task_config)

        # Verify the data refresh method was called
        manager._refresh_data.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_task_signal_generation(self):
        """Test running signal generation task."""
        manager = WorkerManager()

        task_config = {
            "name": "signal_generation",
            "description": "Generate trading signals",
        }

        # Mock the signal generation method
        manager._generate_signals = AsyncMock()

        await manager._run_task(task_config)

        # Verify the signal generation method was called
        manager._generate_signals.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_task_portfolio_monitoring(self):
        """Test running portfolio monitoring task."""
        manager = WorkerManager()

        task_config = {
            "name": "portfolio_monitoring",
            "description": "Monitor portfolio health",
        }

        # Mock the portfolio monitoring method
        manager._monitor_portfolio = AsyncMock()

        await manager._run_task(task_config)

        # Verify the portfolio monitoring method was called
        manager._monitor_portfolio.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_task_unknown(self):
        """Test running unknown task type."""
        manager = WorkerManager()

        task_config = {"name": "unknown_task", "description": "Unknown task type"}

        # Should not raise exception, just log warning
        await manager._run_task(task_config)

    @pytest.mark.asyncio
    async def test_run_task_with_exception(self):
        """Test running task that raises exception."""
        manager = WorkerManager()

        task_config = {"name": "data_refresh", "description": "Refresh market data"}

        # Mock the data refresh method to raise exception
        manager._refresh_data = AsyncMock(side_effect=Exception("Refresh failed"))

        # Should not propagate exception, just log it
        await manager._run_task(task_config)

        # Verify the method was called despite exception
        manager._refresh_data.assert_called_once()

    @pytest.mark.asyncio
    async def test_refresh_data(self):
        """Test data refresh implementation."""
        manager = WorkerManager()

        # Should complete without error
        await manager._refresh_data()

    @pytest.mark.asyncio
    async def test_generate_signals(self):
        """Test signal generation implementation."""
        manager = WorkerManager()

        # Should complete without error
        await manager._generate_signals()

    @pytest.mark.asyncio
    async def test_monitor_portfolio(self):
        """Test portfolio monitoring implementation."""
        manager = WorkerManager()

        # Should complete without error
        await manager._monitor_portfolio()

    @pytest.mark.asyncio
    async def test_process_scheduled_tasks_initial_run(self):
        """Test processing scheduled tasks on initial run."""
        manager = WorkerManager({"max_concurrent_tasks": 2, "poll_interval": 0.1})

        # Mock the _run_task method to track calls
        manager._run_task = AsyncMock()

        await manager._process_scheduled_tasks()

        # Should have started some tasks (all have None as last_run initially)
        assert manager._run_task.call_count > 0
        assert len(manager.tasks) > 0

    @pytest.mark.asyncio
    async def test_process_scheduled_tasks_max_concurrent(self):
        """Test that max concurrent tasks limit is respected."""
        manager = WorkerManager(
            {"max_concurrent_tasks": 1, "poll_interval": 0.1}  # Very low limit
        )

        # Fill up task slots with mock running tasks
        manager.tasks = [Mock() for _ in range(manager.max_concurrent_tasks)]

        # Mock the _run_task method
        manager._run_task = AsyncMock()

        await manager._process_scheduled_tasks()

        # Should not start new tasks when at limit
        manager._run_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_check_for_new_tasks(self):
        """Test checking for new tasks from external sources."""
        manager = WorkerManager()

        # Should complete without error (placeholder implementation)
        await manager._check_for_new_tasks()

    @pytest.mark.asyncio
    async def test_worker_loop_single_iteration(self):
        """Test a single iteration of the worker loop."""
        manager = WorkerManager({"poll_interval": 0.01})

        # Mock all the methods called in worker loop
        manager._process_scheduled_tasks = AsyncMock()
        manager._check_for_new_tasks = AsyncMock()
        manager._cleanup_completed_tasks = Mock()

        # Start the manager and let it run one iteration
        manager.running = True

        # Create a task that will stop the loop after one iteration
        async def stop_after_delay():
            await asyncio.sleep(0.05)
            manager.running = False

        stop_task = asyncio.create_task(stop_after_delay())

        # Run the worker loop
        await manager._worker_loop()

        # Wait for stop task to complete
        await stop_task

        # Verify all methods were called
        manager._process_scheduled_tasks.assert_called()
        manager._check_for_new_tasks.assert_called()
        manager._cleanup_completed_tasks.assert_called()

    @pytest.mark.asyncio
    async def test_worker_loop_handles_exception(self):
        """Test that worker loop handles exceptions gracefully."""
        manager = WorkerManager({"poll_interval": 0.01})

        # Mock method to raise exception
        manager._process_scheduled_tasks = AsyncMock(
            side_effect=Exception("Test error")
        )
        manager._check_for_new_tasks = AsyncMock()
        manager._cleanup_completed_tasks = Mock()

        manager.running = True

        # Create a task that will stop the loop after a short delay
        async def stop_after_delay():
            await asyncio.sleep(0.1)
            manager.running = False

        stop_task = asyncio.create_task(stop_after_delay())

        # Worker loop should handle exception and continue
        await manager._worker_loop()

        # Wait for stop task to complete
        await stop_task

        # Verify methods were called despite exception
        manager._process_scheduled_tasks.assert_called()

    @pytest.mark.asyncio
    async def test_stop_cancels_running_tasks(self):
        """Test that stop method cancels running tasks."""
        manager = WorkerManager()

        # Create mock running tasks
        task1 = Mock()
        task1.done.return_value = False
        task1.cancel = Mock()

        task2 = Mock()
        task2.done.return_value = True  # Already completed

        manager.tasks = [task1, task2]

        with patch("asyncio.gather", new_callable=AsyncMock) as mock_gather:
            await manager.stop()

        # Should cancel the running task
        task1.cancel.assert_called_once()

        # Should wait for all tasks to complete
        mock_gather.assert_called_once()


@pytest.mark.asyncio
async def test_main_function():
    """Test the main function (integration test)."""
    # This is more of an integration test and would require mocking
    # the signal handlers and the worker manager

    with patch("fxml4.worker.main.WorkerManager") as mock_worker_class:
        with patch("signal.signal") as mock_signal:
            with patch("fxml4.worker.main.get_config") as mock_get_config:

                # Configure mocks
                mock_get_config.side_effect = lambda key, default: default
                mock_worker = Mock()
                mock_worker.start = AsyncMock()
                mock_worker.stop = AsyncMock()
                mock_worker_class.return_value = mock_worker

                # Import and patch the main function
                from fxml4.worker.main import main

                # Create a task that will simulate KeyboardInterrupt
                async def simulate_interrupt():
                    await asyncio.sleep(0.01)
                    raise KeyboardInterrupt()

                # Replace the worker.start with our interrupt simulation
                mock_worker.start = simulate_interrupt

                # Run main function
                try:
                    await main()
                except KeyboardInterrupt:
                    pass

                # Verify worker was created and stop was called
                mock_worker_class.assert_called_once()
                mock_worker.stop.assert_called_once()
