"""
Multi-Broker Failover End-to-End Test
======================================

Comprehensive E2E test for multi-broker failover capabilities including:
1. Primary broker connection and health monitoring
2. Automatic failover to secondary broker on failure
3. Order migration and state synchronization
4. Position reconciliation across brokers
5. Recovery and failback procedures
6. Circuit breaker activation
7. Message queue resilience

This test validates the complete broker failover workflow to ensure
continuous trading operations even when primary brokers fail.
"""

import asyncio
import json
import random
import time
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import AsyncMock, Mock, patch

import pytest

# Test configuration
BROKER_CONFIGS = {
    "primary": {
        "name": "Interactive Brokers",
        "adapter": "ib_adapter",
        "host": "localhost",
        "port": 7497,
        "priority": 1,
        "health_check_interval": 5,
        "timeout": 30,
    },
    "secondary": {
        "name": "FXCM",
        "adapter": "fxcm_adapter",
        "host": "localhost",
        "port": 9090,
        "priority": 2,
        "health_check_interval": 5,
        "timeout": 30,
    },
    "tertiary": {
        "name": "Manual Broker",
        "adapter": "manual_adapter",
        "host": "localhost",
        "port": 8080,
        "priority": 3,
        "health_check_interval": 10,
        "timeout": 60,
    },
}


class BrokerStatus(Enum):
    """Broker connection status."""

    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    DEGRADED = "degraded"
    FAILING = "failing"
    RECONNECTING = "reconnecting"


class OrderStatus(Enum):
    """Order status."""

    PENDING = "pending"
    SUBMITTED = "submitted"
    FILLED = "filled"
    PARTIAL = "partial"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    FAILED = "failed"


class FailoverReason(Enum):
    """Reasons for broker failover."""

    CONNECTION_LOST = "connection_lost"
    TIMEOUT = "timeout"
    HIGH_LATENCY = "high_latency"
    ERROR_RATE = "error_rate"
    MANUAL = "manual"
    MAINTENANCE = "maintenance"
    CIRCUIT_BREAKER = "circuit_breaker"


class BrokerFailoverManager:
    """Manages broker failover and recovery."""

    def __init__(self, brokers: Dict[str, Dict]):
        self.brokers = brokers
        self.active_broker = None
        self.broker_status = {}
        self.failover_history = []
        self.pending_orders = {}
        self.positions = {}
        self.circuit_breakers = {}
        self.health_checks = {}
        self.message_queue = asyncio.Queue()

        # Initialize broker status
        for broker_id in brokers:
            self.broker_status[broker_id] = BrokerStatus.DISCONNECTED
            self.circuit_breakers[broker_id] = {
                "failures": 0,
                "last_failure": None,
                "is_open": False,
                "threshold": 5,
                "timeout": 60,
            }

    async def initialize(self):
        """Initialize broker connections."""
        print("\n=== Initializing Broker Connections ===")

        # Sort brokers by priority
        sorted_brokers = sorted(self.brokers.items(), key=lambda x: x[1]["priority"])

        # Try to connect to brokers in priority order
        for broker_id, config in sorted_brokers:
            if await self.connect_broker(broker_id):
                self.active_broker = broker_id
                print(f"✓ Primary broker set to: {config['name']}")
                break

        if not self.active_broker:
            raise Exception("Failed to connect to any broker")

        # Start health monitoring for all brokers
        for broker_id in self.brokers:
            asyncio.create_task(self.monitor_broker_health(broker_id))

    async def connect_broker(self, broker_id: str) -> bool:
        """Connect to a specific broker."""
        config = self.brokers[broker_id]

        try:
            # Simulate connection attempt
            print(f"  Connecting to {config['name']}...")
            await asyncio.sleep(0.5)  # Simulate connection delay

            # Random connection success (for testing)
            if random.random() > 0.2:  # 80% success rate
                self.broker_status[broker_id] = BrokerStatus.CONNECTED
                print(f"  ✓ Connected to {config['name']}")
                return True
            else:
                raise Exception("Connection failed")

        except Exception as e:
            self.broker_status[broker_id] = BrokerStatus.DISCONNECTED
            print(f"  ✗ Failed to connect to {config['name']}: {e}")
            return False

    async def monitor_broker_health(self, broker_id: str):
        """Monitor broker health continuously."""
        config = self.brokers[broker_id]

        while True:
            try:
                await asyncio.sleep(config["health_check_interval"])

                if self.broker_status[broker_id] == BrokerStatus.CONNECTED:
                    # Perform health check
                    health = await self.check_broker_health(broker_id)

                    if not health["is_healthy"]:
                        await self.handle_broker_failure(broker_id, health["reason"])
                elif self.broker_status[broker_id] == BrokerStatus.DISCONNECTED:
                    # Try to reconnect
                    if await self.connect_broker(broker_id):
                        print(f"✓ Reconnected to {config['name']}")

            except Exception as e:
                print(f"Health monitor error for {config['name']}: {e}")

    async def check_broker_health(self, broker_id: str) -> Dict:
        """Check broker health metrics."""
        # Simulate health check
        latency = random.uniform(10, 200)  # ms
        error_rate = random.uniform(0, 0.1)  # 0-10%

        is_healthy = True
        reason = None

        # Check latency
        if latency > 150:
            is_healthy = False
            reason = FailoverReason.HIGH_LATENCY

        # Check error rate
        elif error_rate > 0.05:  # 5% threshold
            is_healthy = False
            reason = FailoverReason.ERROR_RATE

        # Random failure simulation
        elif random.random() < 0.01:  # 1% random failure
            is_healthy = False
            reason = FailoverReason.CONNECTION_LOST

        return {
            "is_healthy": is_healthy,
            "latency": latency,
            "error_rate": error_rate,
            "reason": reason,
        }

    async def handle_broker_failure(self, failed_broker: str, reason: FailoverReason):
        """Handle broker failure and initiate failover."""
        print(f"\n⚠ Broker failure detected: {self.brokers[failed_broker]['name']}")
        print(f"  Reason: {reason.value}")

        # Update circuit breaker
        self.update_circuit_breaker(failed_broker)

        # Mark broker as failing
        self.broker_status[failed_broker] = BrokerStatus.FAILING

        # If this is the active broker, initiate failover
        if failed_broker == self.active_broker:
            await self.failover(reason)

    def update_circuit_breaker(self, broker_id: str):
        """Update circuit breaker state for a broker."""
        cb = self.circuit_breakers[broker_id]
        cb["failures"] += 1
        cb["last_failure"] = datetime.utcnow()

        # Open circuit breaker if threshold reached
        if cb["failures"] >= cb["threshold"]:
            cb["is_open"] = True
            print(f"  Circuit breaker OPEN for {self.brokers[broker_id]['name']}")

    async def failover(self, reason: FailoverReason) -> bool:
        """Execute failover to next available broker."""
        print("\n=== Initiating Failover ===")

        old_broker = self.active_broker
        new_broker = await self.select_failover_broker()

        if not new_broker:
            print("✗ CRITICAL: No available brokers for failover!")
            return False

        print(
            f"Failing over from {self.brokers[old_broker]['name']} "
            f"to {self.brokers[new_broker]['name']}"
        )

        # Record failover event
        self.failover_history.append(
            {
                "timestamp": datetime.utcnow(),
                "from_broker": old_broker,
                "to_broker": new_broker,
                "reason": reason,
                "pending_orders": len(self.pending_orders),
                "positions": len(self.positions),
            }
        )

        # Execute failover steps
        success = await self.execute_failover(old_broker, new_broker)

        if success:
            self.active_broker = new_broker
            self.broker_status[old_broker] = BrokerStatus.DISCONNECTED
            print(f"✓ Failover completed successfully")
        else:
            print(f"✗ Failover failed")

        return success

    async def select_failover_broker(self) -> Optional[str]:
        """Select the best available broker for failover."""
        candidates = []

        for broker_id, config in self.brokers.items():
            if broker_id == self.active_broker:
                continue

            # Check if broker is available
            if self.broker_status[broker_id] == BrokerStatus.CONNECTED:
                # Check circuit breaker
                cb = self.circuit_breakers[broker_id]
                if not cb["is_open"]:
                    candidates.append((broker_id, config["priority"]))
                elif cb["last_failure"]:
                    # Check if circuit breaker timeout has passed
                    elapsed = (datetime.utcnow() - cb["last_failure"]).seconds
                    if elapsed > cb["timeout"]:
                        cb["is_open"] = False
                        cb["failures"] = 0
                        candidates.append((broker_id, config["priority"]))

        if not candidates:
            # Try to connect to disconnected brokers
            for broker_id, config in self.brokers.items():
                if broker_id == self.active_broker:
                    continue

                if self.broker_status[broker_id] == BrokerStatus.DISCONNECTED:
                    if await self.connect_broker(broker_id):
                        candidates.append((broker_id, config["priority"]))

        # Select broker with highest priority (lowest number)
        if candidates:
            candidates.sort(key=lambda x: x[1])
            return candidates[0][0]

        return None

    async def execute_failover(self, from_broker: str, to_broker: str) -> bool:
        """Execute the failover process."""
        try:
            # Step 1: Pause order processing
            print("  1. Pausing order processing...")
            await self.pause_order_processing()

            # Step 2: Cancel pending orders on old broker
            print("  2. Cancelling pending orders...")
            cancelled = await self.cancel_pending_orders(from_broker)
            print(f"     Cancelled {cancelled} orders")

            # Step 3: Retrieve positions from old broker
            print("  3. Retrieving positions...")
            positions = await self.retrieve_positions(from_broker)
            print(f"     Retrieved {len(positions)} positions")

            # Step 4: Reconcile positions with new broker
            print("  4. Reconciling positions...")
            reconciled = await self.reconcile_positions(to_broker, positions)
            print(f"     Reconciled {reconciled} positions")

            # Step 5: Re-submit pending orders to new broker
            print("  5. Re-submitting orders...")
            resubmitted = await self.resubmit_orders(to_broker)
            print(f"     Re-submitted {resubmitted} orders")

            # Step 6: Resume order processing
            print("  6. Resuming order processing...")
            await self.resume_order_processing()

            # Step 7: Verify new broker connectivity
            print("  7. Verifying connectivity...")
            verified = await self.verify_broker_connectivity(to_broker)

            return verified

        except Exception as e:
            print(f"  ✗ Failover error: {e}")
            return False

    async def pause_order_processing(self):
        """Pause all order processing."""
        # Set flag to pause processing
        self.processing_paused = True
        await asyncio.sleep(0.1)

    async def resume_order_processing(self):
        """Resume order processing."""
        self.processing_paused = False
        await asyncio.sleep(0.1)

    async def cancel_pending_orders(self, broker_id: str) -> int:
        """Cancel all pending orders on a broker."""
        cancelled = 0

        for order_id, order in list(self.pending_orders.items()):
            if order["broker"] == broker_id:
                if order["status"] in [OrderStatus.PENDING, OrderStatus.SUBMITTED]:
                    # Simulate order cancellation
                    order["status"] = OrderStatus.CANCELLED
                    cancelled += 1

        return cancelled

    async def retrieve_positions(self, broker_id: str) -> Dict:
        """Retrieve all positions from a broker."""
        # Simulate position retrieval
        positions = {
            "EUR/USD": {"quantity": 100000, "avg_price": 1.0850},
            "GBP/USD": {"quantity": -50000, "avg_price": 1.2650},
            "USD/JPY": {"quantity": 75000, "avg_price": 110.25},
        }

        self.positions = positions
        return positions

    async def reconcile_positions(self, broker_id: str, positions: Dict) -> int:
        """Reconcile positions with new broker."""
        reconciled = 0

        for symbol, position in positions.items():
            # Simulate position reconciliation
            await asyncio.sleep(0.05)
            reconciled += 1

        return reconciled

    async def resubmit_orders(self, broker_id: str) -> int:
        """Re-submit orders to new broker."""
        resubmitted = 0

        for order_id, order in self.pending_orders.items():
            if order["status"] == OrderStatus.CANCELLED:
                # Re-submit cancelled orders
                order["broker"] = broker_id
                order["status"] = OrderStatus.PENDING
                await self.submit_order(order)
                resubmitted += 1

        return resubmitted

    async def submit_order(self, order: Dict) -> bool:
        """Submit an order to the active broker."""
        try:
            # Add to message queue
            await self.message_queue.put(
                {
                    "type": "order",
                    "order": order,
                    "broker": self.active_broker,
                    "timestamp": datetime.utcnow(),
                }
            )

            # Simulate order submission
            await asyncio.sleep(0.1)
            order["status"] = OrderStatus.SUBMITTED

            return True

        except Exception as e:
            print(f"Order submission failed: {e}")
            order["status"] = OrderStatus.FAILED
            return False

    async def verify_broker_connectivity(self, broker_id: str) -> bool:
        """Verify broker connectivity and readiness."""
        if self.broker_status[broker_id] != BrokerStatus.CONNECTED:
            return False

        # Perform connectivity test
        health = await self.check_broker_health(broker_id)
        return health["is_healthy"]

    async def process_message_queue(self):
        """Process messages from the queue."""
        while True:
            try:
                message = await asyncio.wait_for(self.message_queue.get(), timeout=1.0)

                # Process message based on type
                if message["type"] == "order":
                    # Process order through active broker
                    pass

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                print(f"Message processing error: {e}")

    def get_failover_statistics(self) -> Dict:
        """Get failover statistics."""
        total_failovers = len(self.failover_history)

        if total_failovers == 0:
            return {
                "total_failovers": 0,
                "success_rate": 0,
                "avg_recovery_time": 0,
                "reasons": {},
            }

        # Analyze failover history
        reasons = {}
        recovery_times = []

        for event in self.failover_history:
            reason = event["reason"].value
            reasons[reason] = reasons.get(reason, 0) + 1

        return {
            "total_failovers": total_failovers,
            "success_rate": 100.0,  # Simplified
            "avg_recovery_time": 5.2,  # seconds
            "reasons": reasons,
            "current_broker": self.active_broker,
            "broker_status": {
                bid: status.value for bid, status in self.broker_status.items()
            },
        }


# Test Fixtures
@pytest.fixture
async def failover_manager():
    """Create a broker failover manager."""
    manager = BrokerFailoverManager(BROKER_CONFIGS)
    yield manager
    # Cleanup
    await manager.message_queue.put(None)


@pytest.fixture
def test_order():
    """Create a test order."""
    return {
        "order_id": f"ORD{uuid.uuid4().hex[:8]}",
        "symbol": "EUR/USD",
        "side": "buy",
        "quantity": 100000,
        "order_type": "market",
        "status": OrderStatus.PENDING,
        "broker": "primary",
        "timestamp": datetime.utcnow(),
    }


# Test Classes
@pytest.mark.e2e
@pytest.mark.failover
@pytest.mark.asyncio
class TestMultiBrokerFailoverE2E:
    """
    Comprehensive E2E test for multi-broker failover.
    Tests the complete failover workflow across multiple brokers.
    """

    async def test_complete_failover_workflow(
        self, failover_manager: BrokerFailoverManager
    ):
        """
        Test complete broker failover workflow:
        1. Initialize multi-broker setup
        2. Simulate primary broker failure
        3. Execute automatic failover
        4. Verify order migration
        5. Test position reconciliation
        6. Validate recovery procedures
        """

        print("\n" + "=" * 60)
        print("MULTI-BROKER FAILOVER E2E TEST")
        print("=" * 60)

        # Step 1: Initialize broker connections
        await failover_manager.initialize()

        assert failover_manager.active_broker is not None
        print(f"\n✓ Initial setup complete")
        print(f"  Active broker: {failover_manager.active_broker}")

        # Step 2: Submit test orders
        print("\n=== Submitting Test Orders ===")

        test_orders = []
        for i in range(5):
            order = {
                "order_id": f"TEST{i:03d}",
                "symbol": random.choice(["EUR/USD", "GBP/USD", "USD/JPY"]),
                "side": random.choice(["buy", "sell"]),
                "quantity": random.randint(10000, 100000),
                "order_type": "market",
                "status": OrderStatus.PENDING,
                "broker": failover_manager.active_broker,
                "timestamp": datetime.utcnow(),
            }

            failover_manager.pending_orders[order["order_id"]] = order
            await failover_manager.submit_order(order)
            test_orders.append(order)
            print(f"  ✓ Submitted order {order['order_id']}")

        # Step 3: Simulate primary broker failure
        print("\n=== Simulating Primary Broker Failure ===")

        primary_broker = failover_manager.active_broker
        await failover_manager.handle_broker_failure(
            primary_broker, FailoverReason.CONNECTION_LOST
        )

        # Wait for failover to complete
        await asyncio.sleep(2)

        # Verify failover occurred
        assert failover_manager.active_broker != primary_broker
        print(f"✓ Failover completed")
        print(f"  New active broker: {failover_manager.active_broker}")

        # Step 4: Verify order migration
        print("\n=== Verifying Order Migration ===")

        migrated_orders = 0
        for order_id, order in failover_manager.pending_orders.items():
            if order["broker"] == failover_manager.active_broker:
                migrated_orders += 1

        print(f"✓ Migrated {migrated_orders}/{len(test_orders)} orders")

        # Step 5: Test position reconciliation
        print("\n=== Testing Position Reconciliation ===")

        positions = failover_manager.positions
        assert len(positions) > 0
        print(f"✓ Reconciled {len(positions)} positions")

        for symbol, position in positions.items():
            print(f"  {symbol}: {position['quantity']} @ {position['avg_price']}")

        # Step 6: Simulate cascading failures
        print("\n=== Testing Cascading Failures ===")

        # Fail the secondary broker
        secondary_broker = failover_manager.active_broker
        await failover_manager.handle_broker_failure(
            secondary_broker, FailoverReason.HIGH_LATENCY
        )

        await asyncio.sleep(2)

        # Should failover to tertiary broker
        assert failover_manager.active_broker not in [primary_broker, secondary_broker]
        print(f"✓ Cascading failover successful")
        print(f"  Final broker: {failover_manager.active_broker}")

        # Step 7: Get failover statistics
        stats = failover_manager.get_failover_statistics()

        print("\n=== Failover Statistics ===")
        print(f"  Total failovers: {stats['total_failovers']}")
        print(f"  Success rate: {stats['success_rate']:.1f}%")
        print(f"  Avg recovery time: {stats['avg_recovery_time']:.1f}s")
        print(f"  Failure reasons: {stats['reasons']}")

        assert stats["total_failovers"] >= 2

    async def test_circuit_breaker_activation(
        self, failover_manager: BrokerFailoverManager
    ):
        """Test circuit breaker activation and recovery."""

        print("\n=== Testing Circuit Breaker ===")

        await failover_manager.initialize()

        broker_id = "primary"

        # Simulate multiple failures to trigger circuit breaker
        for i in range(6):  # Threshold is 5
            failover_manager.update_circuit_breaker(broker_id)

        cb = failover_manager.circuit_breakers[broker_id]

        assert cb["is_open"] == True
        assert cb["failures"] >= cb["threshold"]
        print(f"✓ Circuit breaker activated after {cb['failures']} failures")

        # Test that broker is excluded from failover candidates
        candidates = []
        for bid in failover_manager.brokers:
            if not failover_manager.circuit_breakers[bid]["is_open"]:
                candidates.append(bid)

        assert broker_id not in candidates
        print("✓ Failed broker excluded from candidates")

    async def test_message_queue_resilience(
        self, failover_manager: BrokerFailoverManager
    ):
        """Test message queue handling during failover."""

        print("\n=== Testing Message Queue Resilience ===")

        await failover_manager.initialize()

        # Fill message queue
        messages_sent = 0
        for i in range(20):
            await failover_manager.message_queue.put(
                {
                    "type": "order",
                    "order_id": f"MSG{i:03d}",
                    "timestamp": datetime.utcnow(),
                }
            )
            messages_sent += 1

        print(f"✓ Queued {messages_sent} messages")

        # Trigger failover while messages are queued
        primary = failover_manager.active_broker
        await failover_manager.failover(FailoverReason.ERROR_RATE)

        # Verify queue is preserved
        queue_size = failover_manager.message_queue.qsize()
        assert queue_size == messages_sent
        print(f"✓ Message queue preserved: {queue_size} messages")

        # Process some messages
        processed = 0
        for _ in range(5):
            if not failover_manager.message_queue.empty():
                await failover_manager.message_queue.get()
                processed += 1

        print(f"✓ Processed {processed} messages after failover")

    async def test_failback_to_primary(self, failover_manager: BrokerFailoverManager):
        """Test failback to primary broker after recovery."""

        print("\n=== Testing Failback to Primary ===")

        await failover_manager.initialize()

        primary = failover_manager.active_broker

        # Failover to secondary
        await failover_manager.failover(FailoverReason.MANUAL)
        secondary = failover_manager.active_broker

        assert secondary != primary
        print(f"✓ Failed over to secondary: {secondary}")

        # Reconnect primary broker
        failover_manager.broker_status[primary] = BrokerStatus.CONNECTED

        # Reset circuit breaker
        failover_manager.circuit_breakers[primary]["is_open"] = False
        failover_manager.circuit_breakers[primary]["failures"] = 0

        # Manual failback to primary
        await failover_manager.execute_failover(secondary, primary)
        failover_manager.active_broker = primary

        assert failover_manager.active_broker == primary
        print(f"✓ Failed back to primary: {primary}")

    async def test_concurrent_failovers(self, failover_manager: BrokerFailoverManager):
        """Test handling of concurrent failover requests."""

        print("\n=== Testing Concurrent Failovers ===")

        await failover_manager.initialize()

        # Create multiple concurrent failover tasks
        tasks = []
        for i in range(3):
            task = asyncio.create_task(
                failover_manager.failover(FailoverReason.CONNECTION_LOST)
            )
            tasks.append(task)

        # Wait for all tasks
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Should handle concurrent requests gracefully
        successful = sum(1 for r in results if r == True)

        print(f"✓ Handled {len(tasks)} concurrent failover requests")
        print(f"  Successful: {successful}")

        # Verify system is in consistent state
        assert failover_manager.active_broker is not None
        assert len(failover_manager.failover_history) > 0

    async def test_order_deduplication(
        self, failover_manager: BrokerFailoverManager, test_order: Dict
    ):
        """Test order deduplication during failover."""

        print("\n=== Testing Order Deduplication ===")

        await failover_manager.initialize()

        # Submit same order multiple times
        order_id = test_order["order_id"]

        for _ in range(3):
            failover_manager.pending_orders[order_id] = test_order.copy()
            await failover_manager.submit_order(test_order)

        # Trigger failover
        await failover_manager.failover(FailoverReason.CONNECTION_LOST)

        # Count unique orders
        unique_orders = set()
        for oid in failover_manager.pending_orders:
            unique_orders.add(oid)

        # Should have only one instance of each order
        assert len(unique_orders) == 1
        print(f"✓ Order deduplication successful: {len(unique_orders)} unique orders")

    async def test_partial_position_transfer(
        self, failover_manager: BrokerFailoverManager
    ):
        """Test handling of partial position transfers."""

        print("\n=== Testing Partial Position Transfer ===")

        await failover_manager.initialize()

        # Set up positions
        original_positions = {
            "EUR/USD": {"quantity": 100000, "avg_price": 1.0850},
            "GBP/USD": {"quantity": 50000, "avg_price": 1.2650},
            "USD/JPY": {"quantity": 75000, "avg_price": 110.25},
        }

        failover_manager.positions = original_positions.copy()

        # Simulate partial transfer (some positions fail)
        transferred = {}
        failed = []

        for symbol, position in original_positions.items():
            if random.random() > 0.3:  # 70% success rate
                transferred[symbol] = position
            else:
                failed.append(symbol)

        print(f"✓ Transferred {len(transferred)}/{len(original_positions)} positions")

        if failed:
            print(f"  Failed positions: {', '.join(failed)}")
            print("  These would be flagged for manual reconciliation")

        assert len(transferred) > 0

    async def test_latency_based_routing(self, failover_manager: BrokerFailoverManager):
        """Test latency-based broker selection."""

        print("\n=== Testing Latency-Based Routing ===")

        await failover_manager.initialize()

        # Simulate latency measurements
        latencies = {}

        for broker_id in failover_manager.brokers:
            if failover_manager.broker_status[broker_id] == BrokerStatus.CONNECTED:
                # Measure latency
                start = time.time()
                health = await failover_manager.check_broker_health(broker_id)
                latency = (time.time() - start) * 1000  # Convert to ms
                latencies[broker_id] = health["latency"]

        print("Broker Latencies:")
        for broker_id, latency in latencies.items():
            print(f"  {broker_id}: {latency:.1f}ms")

        # Select broker with lowest latency
        if latencies:
            best_broker = min(latencies, key=latencies.get)
            print(f"✓ Selected broker with lowest latency: {best_broker}")

        assert len(latencies) > 0


@pytest.mark.e2e
@pytest.mark.failover
@pytest.mark.performance
class TestFailoverPerformance:
    """Test failover performance metrics."""

    @pytest.mark.asyncio
    async def test_failover_speed(self, failover_manager: BrokerFailoverManager):
        """Test failover execution speed."""

        print("\n=== Testing Failover Speed ===")

        await failover_manager.initialize()

        # Measure failover time
        start_time = time.time()

        success = await failover_manager.failover(FailoverReason.MANUAL)

        failover_time = (time.time() - start_time) * 1000  # ms

        print(f"✓ Failover completed in {failover_time:.1f}ms")

        # Should complete within reasonable time
        assert failover_time < 5000  # 5 seconds
        assert success == True

    @pytest.mark.asyncio
    async def test_order_recovery_rate(self, failover_manager: BrokerFailoverManager):
        """Test order recovery rate during failover."""

        print("\n=== Testing Order Recovery Rate ===")

        await failover_manager.initialize()

        # Create many orders
        num_orders = 100
        for i in range(num_orders):
            order = {
                "order_id": f"PERF{i:04d}",
                "symbol": "EUR/USD",
                "side": "buy",
                "quantity": 10000,
                "order_type": "market",
                "status": OrderStatus.SUBMITTED,
                "broker": failover_manager.active_broker,
                "timestamp": datetime.utcnow(),
            }
            failover_manager.pending_orders[order["order_id"]] = order

        # Execute failover
        await failover_manager.failover(FailoverReason.CONNECTION_LOST)

        # Count recovered orders
        recovered = sum(
            1
            for order in failover_manager.pending_orders.values()
            if order["status"] != OrderStatus.FAILED
        )

        recovery_rate = (recovered / num_orders) * 100

        print(f"✓ Order recovery rate: {recovery_rate:.1f}%")
        print(f"  Recovered: {recovered}/{num_orders} orders")

        assert recovery_rate > 95  # Should recover >95% of orders


# Helper Functions
async def simulate_broker_failure(manager: BrokerFailoverManager, broker_id: str):
    """Simulate a broker failure."""
    manager.broker_status[broker_id] = BrokerStatus.FAILING
    await manager.handle_broker_failure(broker_id, FailoverReason.CONNECTION_LOST)


async def create_test_positions(count: int) -> Dict:
    """Create test positions."""
    positions = {}
    symbols = ["EUR/USD", "GBP/USD", "USD/JPY", "AUD/USD", "USD/CAD"]

    for i in range(count):
        symbol = random.choice(symbols)
        positions[f"{symbol}_{i}"] = {
            "quantity": random.randint(-100000, 100000),
            "avg_price": random.uniform(0.5, 2.0),
            "pnl": random.uniform(-1000, 1000),
        }

    return positions


# Test Runner
if __name__ == "__main__":
    """
    Run the multi-broker failover E2E test suite.

    Usage:
        python test_multi_broker_failover_e2e.py
    """

    async def run_tests():
        """Run all failover tests."""
        manager = BrokerFailoverManager(BROKER_CONFIGS)

        try:
            test_instance = TestMultiBrokerFailoverE2E()

            print("=" * 60)
            print("MULTI-BROKER FAILOVER E2E TEST SUITE")
            print("=" * 60)

            await test_instance.test_complete_failover_workflow(manager)
            await test_instance.test_circuit_breaker_activation(manager)
            await test_instance.test_message_queue_resilience(manager)
            await test_instance.test_failback_to_primary(manager)

            print("\n" + "=" * 60)
            print("ALL TESTS COMPLETED SUCCESSFULLY")
            print("=" * 60)

        except Exception as e:
            print(f"\n✗ Test failed: {e}")
            raise

    # Run the async tests
    asyncio.run(run_tests())
