"""Order processing race condition tests for FXML4.

Tests race conditions in order lifecycle management, state transitions,
execution processing, and multi-adapter coordination.
"""

import asyncio
import random
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from unittest.mock import AsyncMock, Mock

import pytest

from fxml4.brokers.adapters.base import (
    AdapterConfig,
    BrokerAdapter,
    ConnectionStatus,
    OrderInfo,
    OrderStatus,
)
from fxml4.fix.messages.base import OrdType, Side, TimeInForce
from fxml4.fix.messages.orders import ExecutionReport, NewOrderSingle
from tests.utils.concurrency_utils import (
    DeadlockDetector,
    LoadGenerator,
    RaceConditionDetector,
    concurrency_test_environment,
)


class OrderState(Enum):
    """Order state for race condition testing."""

    CREATED = "created"
    PENDING_SUBMISSION = "pending_submission"
    SUBMITTED = "submitted"
    ACKNOWLEDGED = "acknowledged"
    WORKING = "working"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


@dataclass
class OrderTracker:
    """Track order state for race condition detection."""

    cl_ord_id: str
    state: OrderState = OrderState.CREATED
    state_history: List[tuple] = field(default_factory=list)
    thread_access_log: List[Dict] = field(default_factory=list)
    lock_acquisitions: Set[str] = field(default_factory=set)

    def transition_state(self, new_state: OrderState, thread_id: str = None):
        """Transition order state with tracking."""
        old_state = self.state
        timestamp = time.perf_counter()

        # Record state transition
        self.state_history.append((timestamp, old_state, new_state, thread_id))
        self.state = new_state

        # Log thread access
        self.thread_access_log.append(
            {
                "timestamp": timestamp,
                "thread_id": thread_id or threading.get_ident(),
                "operation": f"state_transition_{old_state.value}_to_{new_state.value}",
                "valid": self._is_valid_transition(old_state, new_state),
            }
        )

    def _is_valid_transition(
        self, old_state: OrderState, new_state: OrderState
    ) -> bool:
        """Check if state transition is valid."""
        valid_transitions = {
            OrderState.CREATED: [OrderState.PENDING_SUBMISSION],
            OrderState.PENDING_SUBMISSION: [OrderState.SUBMITTED, OrderState.REJECTED],
            OrderState.SUBMITTED: [OrderState.ACKNOWLEDGED, OrderState.REJECTED],
            OrderState.ACKNOWLEDGED: [OrderState.WORKING, OrderState.REJECTED],
            OrderState.WORKING: [
                OrderState.PARTIALLY_FILLED,
                OrderState.FILLED,
                OrderState.CANCELLED,
                OrderState.REJECTED,
            ],
            OrderState.PARTIALLY_FILLED: [OrderState.FILLED, OrderState.CANCELLED],
            OrderState.FILLED: [],  # Terminal state
            OrderState.CANCELLED: [],  # Terminal state
            OrderState.REJECTED: [],  # Terminal state
            OrderState.EXPIRED: [],  # Terminal state
        }

        return new_state in valid_transitions.get(old_state, [])

    def get_invalid_transitions(self) -> List[tuple]:
        """Get list of invalid state transitions."""
        return [
            (timestamp, old_state, new_state, thread_id)
            for timestamp, old_state, new_state, thread_id in self.state_history
            if not self._is_valid_transition(old_state, new_state)
        ]


class OrderManager:
    """Order manager for race condition testing."""

    def __init__(self):
        self.orders: Dict[str, OrderTracker] = {}
        self.execution_queue = asyncio.Queue()
        self.state_locks: Dict[str, asyncio.Lock] = {}
        self.global_lock = asyncio.Lock()
        self.processing_active = False
        self.race_detector = RaceConditionDetector()
        self.deadlock_detector = DeadlockDetector()

    async def create_order(self, cl_ord_id: str) -> OrderTracker:
        """Create new order with tracking."""
        async with self.global_lock:
            order_tracker = OrderTracker(cl_ord_id=cl_ord_id)
            self.orders[cl_ord_id] = order_tracker
            self.state_locks[cl_ord_id] = asyncio.Lock()

        self.race_detector.access_shared_resource(cl_ord_id, "write", "order_created")
        return order_tracker

    async def submit_order(self, cl_ord_id: str, adapter_id: str) -> bool:
        """Submit order through adapter."""
        if cl_ord_id not in self.orders:
            return False

        thread_id = f"submit_{adapter_id}"
        self.deadlock_detector.acquire_lock(thread_id, f"order_{cl_ord_id}")

        try:
            async with self.state_locks[cl_ord_id]:
                order = self.orders[cl_ord_id]

                # Record resource access
                self.race_detector.access_shared_resource(
                    cl_ord_id, "write", f"submit_order_{adapter_id}"
                )

                # Transition to pending submission
                order.transition_state(OrderState.PENDING_SUBMISSION, thread_id)

                # Simulate submission delay
                await asyncio.sleep(random.uniform(0.001, 0.01))

                # Transition to submitted
                order.transition_state(OrderState.SUBMITTED, thread_id)

                # Queue for acknowledgment processing
                await self.execution_queue.put(
                    {
                        "type": "acknowledgment",
                        "cl_ord_id": cl_ord_id,
                        "adapter_id": adapter_id,
                        "timestamp": time.perf_counter(),
                    }
                )

                return True

        finally:
            self.deadlock_detector.release_lock(thread_id, f"order_{cl_ord_id}")

    async def process_execution(
        self, cl_ord_id: str, exec_type: str, fill_qty: Optional[float] = None
    ) -> bool:
        """Process execution report."""
        if cl_ord_id not in self.orders:
            return False

        thread_id = f"exec_{exec_type}"
        self.deadlock_detector.acquire_lock(thread_id, f"order_{cl_ord_id}")

        try:
            async with self.state_locks[cl_ord_id]:
                order = self.orders[cl_ord_id]

                # Record resource access
                self.race_detector.access_shared_resource(
                    cl_ord_id, "write", f"execution_{exec_type}"
                )

                if exec_type == "acknowledgment":
                    order.transition_state(OrderState.ACKNOWLEDGED, thread_id)
                    await asyncio.sleep(0.001)  # Processing delay
                    order.transition_state(OrderState.WORKING, thread_id)

                elif exec_type == "partial_fill":
                    if order.state == OrderState.WORKING:
                        order.transition_state(OrderState.PARTIALLY_FILLED, thread_id)

                elif exec_type == "fill":
                    if order.state in [OrderState.WORKING, OrderState.PARTIALLY_FILLED]:
                        order.transition_state(OrderState.FILLED, thread_id)

                elif exec_type == "cancel":
                    if order.state in [OrderState.WORKING, OrderState.PARTIALLY_FILLED]:
                        order.transition_state(OrderState.CANCELLED, thread_id)

                elif exec_type == "reject":
                    order.transition_state(OrderState.REJECTED, thread_id)

                return True

        finally:
            self.deadlock_detector.release_lock(thread_id, f"order_{cl_ord_id}")

    async def start_execution_processor(self):
        """Start processing execution queue."""
        self.processing_active = True

        while self.processing_active:
            try:
                # Wait for execution with timeout
                execution = await asyncio.wait_for(
                    self.execution_queue.get(), timeout=0.1
                )

                if execution["type"] == "acknowledgment":
                    await self.process_execution(
                        execution["cl_ord_id"], "acknowledgment"
                    )

                    # Generate random follow-up executions
                    if random.random() < 0.7:  # 70% chance of fill
                        await asyncio.sleep(random.uniform(0.001, 0.01))
                        if random.random() < 0.3:  # 30% chance of partial fill first
                            await self.process_execution(
                                execution["cl_ord_id"], "partial_fill"
                            )
                            await asyncio.sleep(random.uniform(0.001, 0.005))

                        await self.process_execution(execution["cl_ord_id"], "fill")
                    elif random.random() < 0.1:  # 10% chance of cancel
                        await self.process_execution(execution["cl_ord_id"], "cancel")

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                print(f"Execution processing error: {e}")

    async def stop_execution_processor(self):
        """Stop execution processing."""
        self.processing_active = False

    def get_race_conditions(self) -> List[Dict[str, Any]]:
        """Get detected race conditions."""
        race_conditions = []

        # Check for invalid state transitions
        for cl_ord_id, order in self.orders.items():
            invalid_transitions = order.get_invalid_transitions()
            for timestamp, old_state, new_state, thread_id in invalid_transitions:
                race_conditions.append(
                    {
                        "type": "invalid_state_transition",
                        "order_id": cl_ord_id,
                        "timestamp": timestamp,
                        "old_state": old_state.value,
                        "new_state": new_state.value,
                        "thread_id": thread_id,
                    }
                )

        # Add race detector results
        race_conditions.extend(self.race_detector.get_race_conditions())

        return race_conditions

    def get_deadlocks(self) -> List[Dict[str, Any]]:
        """Get detected deadlocks."""
        return self.deadlock_detector.get_deadlocks()


@pytest.mark.concurrency
@pytest.mark.orders
class TestOrderProcessingRaceConditions:
    """Test order processing race conditions."""

    @pytest.fixture
    def order_manager(self):
        """Create order manager for testing."""
        manager = OrderManager()
        yield manager

        # Cleanup
        asyncio.create_task(manager.stop_execution_processor())

    @pytest.mark.asyncio
    async def test_concurrent_order_submission(self, order_manager):
        """Test concurrent order submission race conditions."""

        # Start execution processor
        processor_task = asyncio.create_task(order_manager.start_execution_processor())

        async def submit_order_sequence(order_id: str, adapter_id: str):
            """Submit order and track race conditions."""
            # Create order
            await order_manager.create_order(order_id)

            # Submit order
            success = await order_manager.submit_order(order_id, adapter_id)
            return success

        # Generate concurrent order submissions
        num_orders = 100
        adapters = ["ib_adapter", "fxcm_adapter", "manual_adapter"]
        order_submissions = []

        for i in range(num_orders):
            order_id = f"ORDER_{i:04d}"
            adapter_id = adapters[i % len(adapters)]
            order_submissions.append((order_id, adapter_id))

        async with concurrency_test_environment(max_concurrent=30) as env:
            result = await env.test_async_operation(
                submit_order_sequence,
                order_submissions,
                max_concurrent=30,
                timeout=10.0,
            )

            # Stop processor
            await order_manager.stop_execution_processor()
            processor_task.cancel()

            # Validate results
            assert result.operations_completed == num_orders
            assert result.operations_failed == 0

            # Check for race conditions
            race_conditions = order_manager.get_race_conditions()
            invalid_transitions = [
                rc
                for rc in race_conditions
                if rc.get("type") == "invalid_state_transition"
            ]

            # Should have no invalid state transitions
            assert (
                len(invalid_transitions) == 0
            ), f"Found invalid transitions: {invalid_transitions}"

            # Check order state consistency
            for order_id, order in order_manager.orders.items():
                # All orders should have progressed beyond CREATED state
                assert order.state != OrderState.CREATED

                # State history should show valid progression
                assert (
                    len(order.state_history) >= 2
                )  # At least CREATED -> PENDING -> SUBMITTED

    @pytest.mark.asyncio
    async def test_execution_processing_race_conditions(self, order_manager):
        """Test execution report processing race conditions."""

        # Create orders first
        num_orders = 50
        order_ids = []

        for i in range(num_orders):
            order_id = f"EXEC_TEST_{i:04d}"
            await order_manager.create_order(order_id)
            await order_manager.submit_order(order_id, "test_adapter")
            order_ids.append(order_id)

        # Start execution processor
        processor_task = asyncio.create_task(order_manager.start_execution_processor())
        await asyncio.sleep(0.1)  # Let initial processing start

        async def concurrent_execution_processing(order_id: str, exec_type: str):
            """Process execution concurrently."""
            return await order_manager.process_execution(order_id, exec_type)

        # Generate concurrent execution reports
        execution_operations = []
        exec_types = ["acknowledgment", "partial_fill", "fill", "cancel", "reject"]

        for order_id in order_ids:
            # Random execution type for race condition testing
            exec_type = random.choice(exec_types)
            execution_operations.append((order_id, exec_type))

        async with concurrency_test_environment(max_concurrent=25) as env:
            result = await env.test_async_operation(
                concurrent_execution_processing,
                execution_operations,
                max_concurrent=25,
                timeout=5.0,
            )

            # Stop processor
            await order_manager.stop_execution_processor()
            processor_task.cancel()

            # Most executions should succeed
            assert result.operations_completed > num_orders * 0.7  # At least 70%

            # Check for race conditions in execution processing
            race_conditions = order_manager.get_race_conditions()
            execution_races = [rc for rc in race_conditions if "execution" in str(rc)]

            # Should handle concurrent executions safely
            assert len(execution_races) == 0

    @pytest.mark.asyncio
    async def test_order_state_consistency_under_load(self, order_manager):
        """Test order state consistency under high load."""

        # Start execution processor
        processor_task = asyncio.create_task(order_manager.start_execution_processor())

        async def order_lifecycle_simulation(order_base_id: str, sequence_id: int):
            """Simulate complete order lifecycle."""
            order_id = f"{order_base_id}_{sequence_id:04d}"

            try:
                # Create order
                await order_manager.create_order(order_id)

                # Submit order
                await order_manager.submit_order(order_id, f"adapter_{sequence_id % 3}")

                # Let execution processor handle acknowledgment
                await asyncio.sleep(random.uniform(0.01, 0.05))

                # Potentially send additional executions
                if random.random() < 0.3:  # 30% chance of manual cancel
                    await order_manager.process_execution(order_id, "cancel")

                return order_id

            except Exception as e:
                return f"error_{order_id}_{e}"

        # High-load order lifecycle simulation
        num_order_sequences = 200
        order_sequences = [("LOAD_TEST", i) for i in range(num_order_sequences)]

        async with concurrency_test_environment(max_concurrent=50) as env:
            result = await env.test_async_operation(
                order_lifecycle_simulation,
                order_sequences,
                max_concurrent=50,
                timeout=15.0,
            )

            # Stop processor
            await order_manager.stop_execution_processor()
            processor_task.cancel()

            # Wait for final processing
            await asyncio.sleep(0.2)

            # Validate high-load performance
            assert (
                result.operations_completed > num_order_sequences * 0.8
            )  # 80% success

            # Check state consistency
            race_conditions = order_manager.get_race_conditions()
            deadlocks = order_manager.get_deadlocks()

            assert (
                len(race_conditions) == 0
            ), f"Race conditions detected: {race_conditions}"
            assert len(deadlocks) == 0, f"Deadlocks detected: {deadlocks}"

            # Verify final states are valid
            for order_id, order in order_manager.orders.items():
                # All orders should be in a valid terminal or working state
                valid_final_states = [
                    OrderState.FILLED,
                    OrderState.CANCELLED,
                    OrderState.REJECTED,
                    OrderState.WORKING,
                    OrderState.PARTIALLY_FILLED,
                ]
                assert (
                    order.state in valid_final_states
                ), f"Order {order_id} in invalid final state: {order.state}"

    @pytest.mark.asyncio
    async def test_multi_adapter_order_coordination(self, order_manager):
        """Test order coordination across multiple adapters."""

        # Start execution processor
        processor_task = asyncio.create_task(order_manager.start_execution_processor())

        async def multi_adapter_order_handling(order_group_id: str, adapter_count: int):
            """Handle orders across multiple adapters."""
            order_results = []

            for adapter_id in range(adapter_count):
                order_id = f"{order_group_id}_ADAPTER_{adapter_id}"

                # Create and submit order
                await order_manager.create_order(order_id)
                success = await order_manager.submit_order(
                    order_id, f"adapter_{adapter_id}"
                )

                if success:
                    # Simulate adapter-specific processing
                    await asyncio.sleep(random.uniform(0.001, 0.01))

                    # Random execution outcome
                    if random.random() < 0.8:  # 80% fill rate
                        await order_manager.process_execution(order_id, "fill")
                    else:
                        await order_manager.process_execution(order_id, "cancel")

                order_results.append(order_id)

            return len(order_results)

        # Test with multiple adapter groups
        adapter_groups = [
            (f"GROUP_{i}", 5) for i in range(20)
        ]  # 20 groups, 5 adapters each

        async with concurrency_test_environment(max_concurrent=20) as env:
            result = await env.test_async_operation(
                multi_adapter_order_handling,
                adapter_groups,
                max_concurrent=20,
                timeout=10.0,
            )

            # Stop processor
            await order_manager.stop_execution_processor()
            processor_task.cancel()

            # Validate multi-adapter coordination
            assert result.operations_completed == 20  # All groups processed
            assert result.operations_failed == 0

            # Check for adapter coordination race conditions
            race_conditions = order_manager.get_race_conditions()
            deadlocks = order_manager.get_deadlocks()

            # Should coordinate across adapters without conflicts
            assert len(race_conditions) == 0
            assert len(deadlocks) == 0

            # Verify order distribution across adapters
            adapter_order_counts = {}
            for order_id, order in order_manager.orders.items():
                # Extract adapter info from order processing history
                for log_entry in order.thread_access_log:
                    if "submit_order" in log_entry["operation"]:
                        adapter = log_entry["operation"].split("_")[-1]
                        adapter_order_counts[adapter] = (
                            adapter_order_counts.get(adapter, 0) + 1
                        )
                        break

            # Should have distributed orders across adapters
            assert len(adapter_order_counts) > 1

    @pytest.mark.asyncio
    async def test_order_cancellation_race_conditions(self, order_manager):
        """Test race conditions in order cancellation."""

        # Start execution processor
        processor_task = asyncio.create_task(order_manager.start_execution_processor())

        async def cancellation_race_scenario(order_id: str, scenario_type: str):
            """Create cancellation race condition scenarios."""
            # Create and submit order
            await order_manager.create_order(order_id)
            await order_manager.submit_order(order_id, "race_adapter")

            # Let order reach working state
            await asyncio.sleep(0.01)

            if scenario_type == "cancel_vs_fill":
                # Race between cancel and fill
                cancel_task = asyncio.create_task(
                    order_manager.process_execution(order_id, "cancel")
                )
                fill_task = asyncio.create_task(
                    order_manager.process_execution(order_id, "fill")
                )

                results = await asyncio.gather(
                    cancel_task, fill_task, return_exceptions=True
                )
                return f"cancel_fill_race_{order_id}"

            elif scenario_type == "double_cancel":
                # Race between multiple cancels
                cancel_tasks = [
                    asyncio.create_task(
                        order_manager.process_execution(order_id, "cancel")
                    )
                    for _ in range(3)
                ]

                results = await asyncio.gather(*cancel_tasks, return_exceptions=True)
                return f"double_cancel_{order_id}"

            elif scenario_type == "cancel_vs_partial":
                # Race between cancel and partial fill
                partial_task = asyncio.create_task(
                    order_manager.process_execution(order_id, "partial_fill")
                )
                await asyncio.sleep(0.001)  # Small delay
                cancel_task = asyncio.create_task(
                    order_manager.process_execution(order_id, "cancel")
                )

                results = await asyncio.gather(
                    partial_task, cancel_task, return_exceptions=True
                )
                return f"cancel_partial_race_{order_id}"

        # Generate cancellation race scenarios
        scenarios = [
            (f"CANCEL_RACE_{i:03d}", scenario_type)
            for i in range(60)
            for scenario_type in [
                "cancel_vs_fill",
                "double_cancel",
                "cancel_vs_partial",
            ]
        ][
            :60
        ]  # 60 total scenarios

        async with concurrency_test_environment(max_concurrent=30) as env:
            result = await env.test_async_operation(
                cancellation_race_scenario, scenarios, max_concurrent=30, timeout=10.0
            )

            # Stop processor
            await order_manager.stop_execution_processor()
            processor_task.cancel()

            # Wait for final processing
            await asyncio.sleep(0.1)

            # Validate cancellation race handling
            assert result.operations_completed > 50  # Most should complete

            # Check for race conditions in cancellation
            race_conditions = order_manager.get_race_conditions()
            invalid_transitions = [
                rc
                for rc in race_conditions
                if rc.get("type") == "invalid_state_transition"
            ]

            # Should handle cancellation races properly
            assert len(invalid_transitions) == 0

            # Verify final states are consistent
            for order_id, order in order_manager.orders.items():
                if order.state == OrderState.CANCELLED:
                    # If cancelled, should not have been filled
                    state_values = [state for _, _, state, _ in order.state_history]
                    assert (
                        OrderState.FILLED not in state_values
                    ), f"Order {order_id} both cancelled and filled"

                elif order.state == OrderState.FILLED:
                    # If filled, should not have been cancelled
                    state_values = [state for _, _, state, _ in order.state_history]
                    assert (
                        OrderState.CANCELLED not in state_values
                    ), f"Order {order_id} both filled and cancelled"


@pytest.mark.concurrency
@pytest.mark.orders
@pytest.mark.performance
class TestOrderProcessingPerformance:
    """Performance tests for order processing under concurrent load."""

    @pytest.mark.asyncio
    async def test_order_throughput_under_concurrency(self):
        """Test order processing throughput under concurrent load."""

        order_manager = OrderManager()
        processor_task = asyncio.create_task(order_manager.start_execution_processor())

        async def order_throughput_test(batch_id: str, orders_per_batch: int):
            """Process batch of orders for throughput testing."""
            completed_orders = 0

            for i in range(orders_per_batch):
                order_id = f"{batch_id}_ORDER_{i:04d}"

                # Create and submit order
                await order_manager.create_order(order_id)
                success = await order_manager.submit_order(
                    order_id, f"perf_adapter_{batch_id}"
                )

                if success:
                    completed_orders += 1

            return completed_orders

        # High-throughput test
        num_batches = 20
        orders_per_batch = 50
        batches = [(f"BATCH_{i:02d}", orders_per_batch) for i in range(num_batches)]

        start_time = time.perf_counter()

        async with concurrency_test_environment(max_concurrent=20) as env:
            result = await env.test_async_operation(
                order_throughput_test, batches, max_concurrent=20, timeout=15.0
            )

            end_time = time.perf_counter()

            # Stop processor
            await order_manager.stop_execution_processor()
            processor_task.cancel()

            # Performance validation
            total_time = end_time - start_time
            total_orders = num_batches * orders_per_batch
            orders_per_second = total_orders / total_time

            assert result.operations_completed == num_batches
            assert orders_per_second > 200  # > 200 orders/second
            assert result.avg_response_time < 0.1  # < 100ms per batch

    @pytest.mark.asyncio
    async def test_execution_processing_latency(self):
        """Test execution processing latency under load."""

        order_manager = OrderManager()
        processor_task = asyncio.create_task(order_manager.start_execution_processor())

        # Pre-create orders for latency testing
        order_ids = []
        for i in range(100):
            order_id = f"LATENCY_TEST_{i:04d}"
            await order_manager.create_order(order_id)
            await order_manager.submit_order(order_id, "latency_adapter")
            order_ids.append(order_id)

        # Wait for orders to reach working state
        await asyncio.sleep(0.1)

        async def execution_latency_test(order_id: str, exec_type: str):
            """Test execution processing latency."""
            start_time = time.perf_counter()
            success = await order_manager.process_execution(order_id, exec_type)
            end_time = time.perf_counter()

            return {
                "success": success,
                "latency": end_time - start_time,
                "order_id": order_id,
            }

        # Generate execution operations
        exec_operations = []
        exec_types = ["fill", "partial_fill", "cancel"]

        for order_id in order_ids:
            exec_type = random.choice(exec_types)
            exec_operations.append((order_id, exec_type))

        async with concurrency_test_environment(max_concurrent=50) as env:
            result = await env.test_async_operation(
                execution_latency_test, exec_operations, max_concurrent=50, timeout=10.0
            )

            # Stop processor
            await order_manager.stop_execution_processor()
            processor_task.cancel()

            # Latency requirements
            assert result.operations_completed == 100
            assert result.avg_response_time < 0.005  # < 5ms average latency
            assert result.throughput_ops_per_sec > 500  # > 500 executions/second
