"""TDD Tests for Account Monitoring Bridge Features.

Tests account balance synchronization, position tracking, and reconciliation
between FXML4 and ForexConnect systems following TDD methodology.
"""

import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from fxml4.api.account_monitoring import (
    AccountAlert,
    AccountReconciler,
    AccountSnapshot,
    AccountStateManager,
    AlertType,
    MarginData,
    MarginMonitor,
    PositionData,
    PositionTracker,
)


@pytest.fixture
def account_manager():
    """Create account state manager for testing."""
    return AccountStateManager()


@pytest.fixture
def position_tracker():
    """Create position tracker for testing."""
    return PositionTracker()


@pytest.fixture
def margin_monitor():
    """Create margin monitor for testing."""
    return MarginMonitor()


@pytest.fixture
def account_reconciler():
    """Create account reconciler for testing."""
    return AccountReconciler()


@pytest.fixture
def sample_forex_account_data():
    """Generate sample ForexConnect account data."""
    return {
        "account_id": "12345678",
        "balance": 10000.00,
        "equity": 10250.00,
        "margin_used": 500.00,
        "margin_available": 9750.00,
        "pl": 250.00,
        "currency": "USD",
        "timestamp": datetime.utcnow().isoformat(),
    }


@pytest.fixture
def sample_positions_data():
    """Generate sample position data."""
    return [
        {
            "position_id": "POS_001",
            "symbol": "EURUSD",
            "side": "long",
            "quantity": 100000,
            "open_price": 1.1200,
            "current_price": 1.1250,
            "unrealized_pl": 500.00,
            "timestamp": datetime.utcnow().isoformat(),
        },
        {
            "position_id": "POS_002",
            "symbol": "GBPUSD",
            "side": "short",
            "quantity": 50000,
            "open_price": 1.2800,
            "current_price": 1.2750,
            "unrealized_pl": 250.00,
            "timestamp": datetime.utcnow().isoformat(),
        },
    ]


@pytest.mark.asyncio
class TestAccountStateManager:
    """TDD tests for account state management functionality."""

    async def test_account_manager_initialization(self, account_manager):
        """Test account manager initializes correctly."""
        assert account_manager is not None
        assert account_manager.current_snapshot is None
        assert len(account_manager.balance_history) == 0
        assert account_manager.last_update is None

    async def test_process_forex_account_update(
        self, account_manager, sample_forex_account_data
    ):
        """Test processing ForexConnect account updates."""
        # Process account update
        snapshot = await account_manager.process_forex_account_update(
            sample_forex_account_data
        )

        # Verify snapshot created correctly
        assert snapshot is not None
        assert snapshot.account_id == "12345678"
        assert snapshot.balance == 10000.00
        assert snapshot.equity == 10250.00
        assert snapshot.margin_used == 500.00
        assert snapshot.unrealized_pl == 250.00

        # Verify state updated
        assert account_manager.current_snapshot == snapshot
        assert len(account_manager.balance_history) == 1
        assert account_manager.last_update is not None

    async def test_balance_history_tracking(self, account_manager):
        """Test balance history is tracked over time."""
        # Create series of account updates
        account_updates = [
            {
                "account_id": "12345",
                "balance": 10000.00,
                "equity": 10000.00,
                "timestamp": datetime.utcnow().isoformat(),
            },
            {
                "account_id": "12345",
                "balance": 10100.00,
                "equity": 10150.00,
                "timestamp": (datetime.utcnow() + timedelta(minutes=1)).isoformat(),
            },
            {
                "account_id": "12345",
                "balance": 10050.00,
                "equity": 10080.00,
                "timestamp": (datetime.utcnow() + timedelta(minutes=2)).isoformat(),
            },
        ]

        # Process updates
        for update in account_updates:
            await account_manager.process_forex_account_update(update)

        # Verify history tracking
        assert len(account_manager.balance_history) == 3

        # Check balance progression
        balances = [entry.balance for entry in account_manager.balance_history]
        assert balances == [10000.00, 10100.00, 10050.00]

        # Check equity progression
        equities = [entry.equity for entry in account_manager.balance_history]
        assert equities == [10000.00, 10150.00, 10080.00]

    async def test_account_snapshot_calculation(self, account_manager):
        """Test account snapshot calculations are accurate."""
        account_data = {
            "account_id": "TEST123",
            "balance": 5000.00,
            "equity": 5300.00,
            "margin_used": 200.00,
            "margin_available": 5100.00,
            "pl": 300.00,
            "currency": "USD",
            "timestamp": datetime.utcnow().isoformat(),
        }

        snapshot = await account_manager.process_forex_account_update(account_data)

        # Test calculated fields
        assert (
            snapshot.margin_level == (5300.00 / 200.00) * 100
        )  # (equity / margin_used) * 100
        assert snapshot.free_margin == 5100.00
        assert snapshot.unrealized_pl == 300.00

        # Test percentage calculations
        assert abs(snapshot.pl_percentage - (300.00 / 5000.00)) < 0.001  # 6%

    async def test_balance_change_detection(self, account_manager):
        """Test detection of balance changes."""
        # Initial update
        initial_data = {
            "account_id": "12345",
            "balance": 10000.00,
            "equity": 10000.00,
            "timestamp": datetime.utcnow().isoformat(),
        }

        await account_manager.process_forex_account_update(initial_data)

        # Updated data with balance change
        updated_data = {
            "account_id": "12345",
            "balance": 10500.00,
            "equity": 10600.00,
            "timestamp": (datetime.utcnow() + timedelta(minutes=1)).isoformat(),
        }

        snapshot = await account_manager.process_forex_account_update(updated_data)

        # Check change detection
        balance_change = account_manager.get_balance_change()
        assert balance_change == 500.00

        equity_change = account_manager.get_equity_change()
        assert equity_change == 600.00

    async def test_account_alerts_generation(self, account_manager):
        """Test generation of account-related alerts."""
        # Create account data that should trigger alerts
        alert_data = {
            "account_id": "ALERT_TEST",
            "balance": 1000.00,  # Low balance
            "equity": 800.00,  # Negative equity change
            "margin_used": 900.00,
            "margin_available": 100.00,
            "pl": -200.00,  # Loss
            "currency": "USD",
            "timestamp": datetime.utcnow().isoformat(),
        }

        snapshot = await account_manager.process_forex_account_update(alert_data)

        # Generate alerts based on snapshot
        alerts = await account_manager.generate_alerts(snapshot)

        # Verify alert generation
        assert len(alerts) > 0

        # Check for specific alert types
        alert_types = [alert.alert_type for alert in alerts]
        assert AlertType.LOW_BALANCE in alert_types
        assert AlertType.HIGH_MARGIN_USAGE in alert_types

    async def test_get_account_summary(
        self, account_manager, sample_forex_account_data
    ):
        """Test generation of account summary."""
        await account_manager.process_forex_account_update(sample_forex_account_data)

        summary = account_manager.get_account_summary()

        # Verify summary structure
        assert "account_id" in summary
        assert "current_balance" in summary
        assert "current_equity" in summary
        assert "margin_level" in summary
        assert "unrealized_pl" in summary
        assert "last_update" in summary
        assert "account_age_minutes" in summary

        # Verify values
        assert summary["account_id"] == "12345678"
        assert summary["current_balance"] == 10000.00
        assert summary["current_equity"] == 10250.00


@pytest.mark.asyncio
class TestPositionTracker:
    """TDD tests for position tracking functionality."""

    async def test_position_tracker_initialization(self, position_tracker):
        """Test position tracker initializes correctly."""
        assert position_tracker is not None
        assert len(position_tracker.active_positions) == 0
        assert len(position_tracker.closed_positions) == 0
        assert position_tracker.total_unrealized_pl == 0.0

    async def test_process_forex_position_update(
        self, position_tracker, sample_positions_data
    ):
        """Test processing ForexConnect position updates."""
        # Process position updates
        for position_data in sample_positions_data:
            position = await position_tracker.process_forex_position_update(
                position_data
            )
            assert position is not None
            assert position.symbol in ["EURUSD", "GBPUSD"]

        # Verify positions tracked
        assert len(position_tracker.active_positions) == 2
        assert "POS_001" in position_tracker.active_positions
        assert "POS_002" in position_tracker.active_positions

    async def test_position_pl_calculation(self, position_tracker):
        """Test position P&L calculations."""
        position_data = {
            "position_id": "PL_TEST",
            "symbol": "EURUSD",
            "side": "long",
            "quantity": 100000,
            "open_price": 1.1000,
            "current_price": 1.1100,  # 100 pips profit
            "timestamp": datetime.utcnow().isoformat(),
        }

        position = await position_tracker.process_forex_position_update(position_data)

        # Verify P&L calculation (for EURUSD: 100000 * 0.01 = $1000 for 100 pips)
        expected_pl = (1.1100 - 1.1000) * 100000
        assert abs(position.unrealized_pl - expected_pl) < 0.01
        assert position.unrealized_pl > 0  # Profit

        # Test short position
        short_position_data = {
            "position_id": "SHORT_TEST",
            "symbol": "GBPUSD",
            "side": "short",
            "quantity": 50000,
            "open_price": 1.3000,
            "current_price": 1.2950,  # 50 pips profit for short
            "timestamp": datetime.utcnow().isoformat(),
        }

        short_position = await position_tracker.process_forex_position_update(
            short_position_data
        )

        # For short: profit when current < open
        expected_short_pl = (1.3000 - 1.2950) * 50000
        assert abs(short_position.unrealized_pl - expected_short_pl) < 0.01
        assert short_position.unrealized_pl > 0  # Profit

    async def test_total_unrealized_pl_aggregation(
        self, position_tracker, sample_positions_data
    ):
        """Test aggregation of total unrealized P&L."""
        # Process positions
        for position_data in sample_positions_data:
            await position_tracker.process_forex_position_update(position_data)

        # Calculate total P&L
        total_pl = position_tracker.calculate_total_unrealized_pl()

        # Should equal sum of individual position P&L (500 + 250 = 750)
        expected_total = 500.00 + 250.00
        assert abs(total_pl - expected_total) < 0.01
        assert position_tracker.total_unrealized_pl == total_pl

    async def test_position_update_vs_new_position(self, position_tracker):
        """Test updating existing position vs creating new position."""
        # Create initial position
        initial_position = {
            "position_id": "UPDATE_TEST",
            "symbol": "EURUSD",
            "side": "long",
            "quantity": 100000,
            "open_price": 1.1000,
            "current_price": 1.1050,
            "unrealized_pl": 500.00,
            "timestamp": datetime.utcnow().isoformat(),
        }

        position1 = await position_tracker.process_forex_position_update(
            initial_position
        )
        assert len(position_tracker.active_positions) == 1

        # Update same position with new price
        updated_position = {
            "position_id": "UPDATE_TEST",  # Same ID
            "symbol": "EURUSD",
            "side": "long",
            "quantity": 100000,
            "open_price": 1.1000,
            "current_price": 1.1100,  # New current price
            "unrealized_pl": 1000.00,  # Updated P&L
            "timestamp": (datetime.utcnow() + timedelta(minutes=1)).isoformat(),
        }

        position2 = await position_tracker.process_forex_position_update(
            updated_position
        )

        # Should still have only 1 position (updated, not new)
        assert len(position_tracker.active_positions) == 1

        # Verify it was updated, not replaced
        updated_pos = position_tracker.active_positions["UPDATE_TEST"]
        assert updated_pos.current_price == 1.1100
        assert updated_pos.unrealized_pl == 1000.00

    async def test_position_closure_handling(self, position_tracker):
        """Test handling of position closures."""
        # Create active position
        position_data = {
            "position_id": "CLOSE_TEST",
            "symbol": "EURUSD",
            "side": "long",
            "quantity": 100000,
            "open_price": 1.1000,
            "current_price": 1.1050,
            "unrealized_pl": 500.00,
            "timestamp": datetime.utcnow().isoformat(),
        }

        await position_tracker.process_forex_position_update(position_data)
        assert len(position_tracker.active_positions) == 1

        # Close the position
        closed_position = await position_tracker.close_position(
            "CLOSE_TEST", 1.1080, 800.00
        )

        # Verify position moved from active to closed
        assert len(position_tracker.active_positions) == 0
        assert len(position_tracker.closed_positions) == 1

        # Verify closed position data
        assert closed_position.position_id == "CLOSE_TEST"
        assert closed_position.close_price == 1.1080
        assert closed_position.realized_pl == 800.00
        assert closed_position.is_closed == True

    async def test_get_positions_by_symbol(
        self, position_tracker, sample_positions_data
    ):
        """Test filtering positions by symbol."""
        # Process positions
        for position_data in sample_positions_data:
            await position_tracker.process_forex_position_update(position_data)

        # Get positions by symbol
        eurusd_positions = position_tracker.get_positions_by_symbol("EURUSD")
        gbpusd_positions = position_tracker.get_positions_by_symbol("GBPUSD")
        usdjpy_positions = position_tracker.get_positions_by_symbol("USDJPY")

        # Verify filtering
        assert len(eurusd_positions) == 1
        assert len(gbpusd_positions) == 1
        assert len(usdjpy_positions) == 0

        assert eurusd_positions[0].symbol == "EURUSD"
        assert gbpusd_positions[0].symbol == "GBPUSD"

    async def test_position_statistics(self, position_tracker, sample_positions_data):
        """Test position statistics calculation."""
        # Process positions
        for position_data in sample_positions_data:
            await position_tracker.process_forex_position_update(position_data)

        # Get statistics
        stats = position_tracker.get_position_statistics()

        # Verify statistics structure and values
        assert "total_positions" in stats
        assert "long_positions" in stats
        assert "short_positions" in stats
        assert "total_unrealized_pl" in stats
        assert "profitable_positions" in stats
        assert "losing_positions" in stats

        assert stats["total_positions"] == 2
        assert stats["long_positions"] == 1  # EURUSD long
        assert stats["short_positions"] == 1  # GBPUSD short
        assert stats["profitable_positions"] == 2  # Both have positive P&L
        assert stats["losing_positions"] == 0


@pytest.mark.asyncio
class TestMarginMonitor:
    """TDD tests for margin monitoring functionality."""

    async def test_margin_monitor_initialization(self, margin_monitor):
        """Test margin monitor initializes correctly."""
        assert margin_monitor is not None
        assert margin_monitor.margin_alert_threshold == 100.0  # Default 100%
        assert margin_monitor.margin_call_threshold == 50.0  # Default 50%
        assert len(margin_monitor.margin_history) == 0

    async def test_margin_level_monitoring(self, margin_monitor):
        """Test margin level monitoring and alert generation."""
        # Test healthy margin level
        healthy_margin_data = {
            "account_id": "MARGIN_TEST",
            "equity": 10000.00,
            "margin_used": 1000.00,
            "timestamp": datetime.utcnow().isoformat(),
        }

        margin_data = await margin_monitor.process_margin_update(healthy_margin_data)

        # Verify margin level calculation
        expected_margin_level = (10000.00 / 1000.00) * 100  # 1000%
        assert abs(margin_data.margin_level - expected_margin_level) < 0.01
        assert margin_data.status == "healthy"

        # Test low margin level (should trigger alert)
        low_margin_data = {
            "account_id": "MARGIN_TEST",
            "equity": 600.00,
            "margin_used": 1000.00,  # 60% margin level
            "timestamp": datetime.utcnow().isoformat(),
        }

        margin_data = await margin_monitor.process_margin_update(low_margin_data)

        # Verify alert conditions
        assert margin_data.margin_level == 60.0
        assert margin_data.status == "margin_call"  # Below 50% threshold

        # Check if alert was generated
        alerts = await margin_monitor.check_margin_alerts(margin_data)
        assert len(alerts) > 0
        assert alerts[0].alert_type == AlertType.MARGIN_CALL

    async def test_margin_threshold_configuration(self, margin_monitor):
        """Test configuration of margin alert thresholds."""
        # Set custom thresholds
        await margin_monitor.set_margin_thresholds(
            alert_threshold=200.0,  # Alert at 200%
            call_threshold=100.0,  # Margin call at 100%
        )

        assert margin_monitor.margin_alert_threshold == 200.0
        assert margin_monitor.margin_call_threshold == 100.0

        # Test margin data against custom thresholds
        margin_data = {
            "account_id": "THRESHOLD_TEST",
            "equity": 1500.00,
            "margin_used": 1000.00,  # 150% margin level
            "timestamp": datetime.utcnow().isoformat(),
        }

        result = await margin_monitor.process_margin_update(margin_data)

        # Should trigger alert (150% < 200%) but not margin call (150% > 100%)
        assert result.status == "warning"

        alerts = await margin_monitor.check_margin_alerts(result)
        alert_types = [alert.alert_type for alert in alerts]
        assert AlertType.MARGIN_WARNING in alert_types
        assert AlertType.MARGIN_CALL not in alert_types

    async def test_margin_history_tracking(self, margin_monitor):
        """Test margin level history tracking."""
        # Create series of margin updates
        margin_updates = [
            {"equity": 10000.00, "margin_used": 1000.00},  # 1000%
            {"equity": 8000.00, "margin_used": 1000.00},  # 800%
            {"equity": 5000.00, "margin_used": 1000.00},  # 500%
            {"equity": 2000.00, "margin_used": 1000.00},  # 200%
            {"equity": 800.00, "margin_used": 1000.00},  # 80%
        ]

        for i, update in enumerate(margin_updates):
            update["account_id"] = "HISTORY_TEST"
            update["timestamp"] = (datetime.utcnow() + timedelta(minutes=i)).isoformat()
            await margin_monitor.process_margin_update(update)

        # Verify history tracking
        assert len(margin_monitor.margin_history) == 5

        # Check margin level progression
        margin_levels = [entry.margin_level for entry in margin_monitor.margin_history]
        expected_levels = [1000.0, 800.0, 500.0, 200.0, 80.0]

        for actual, expected in zip(margin_levels, expected_levels):
            assert abs(actual - expected) < 0.1

    async def test_margin_trend_analysis(self, margin_monitor):
        """Test margin trend analysis (improving vs deteriorating)."""
        # Create declining margin trend
        declining_updates = [
            {"equity": 10000.00, "margin_used": 1000.00},  # 1000%
            {"equity": 7000.00, "margin_used": 1000.00},  # 700%
            {"equity": 4000.00, "margin_used": 1000.00},  # 400%
        ]

        for i, update in enumerate(declining_updates):
            update["account_id"] = "TREND_TEST"
            update["timestamp"] = (datetime.utcnow() + timedelta(minutes=i)).isoformat()
            await margin_monitor.process_margin_update(update)

        # Analyze trend
        trend = margin_monitor.analyze_margin_trend(lookback_periods=3)

        assert trend["direction"] == "declining"
        assert trend["rate_of_change"] < 0  # Negative rate
        assert trend["periods_analyzed"] == 3

    async def test_get_margin_summary(self, margin_monitor):
        """Test generation of margin summary."""
        margin_data = {
            "account_id": "SUMMARY_TEST",
            "equity": 5000.00,
            "margin_used": 2000.00,
            "margin_available": 3000.00,
            "timestamp": datetime.utcnow().isoformat(),
        }

        await margin_monitor.process_margin_update(margin_data)

        summary = margin_monitor.get_margin_summary()

        # Verify summary structure
        assert "current_margin_level" in summary
        assert "margin_status" in summary
        assert "margin_used" in summary
        assert "margin_available" in summary
        assert "distance_to_margin_call" in summary
        assert "last_update" in summary

        # Verify calculated values
        assert summary["current_margin_level"] == 250.0  # (5000/2000) * 100
        assert summary["margin_used"] == 2000.00
        assert summary["margin_available"] == 3000.00


@pytest.mark.asyncio
class TestAccountReconciler:
    """TDD tests for account reconciliation between FXML4 and ForexConnect."""

    async def test_reconciler_initialization(self, account_reconciler):
        """Test account reconciler initializes correctly."""
        assert account_reconciler is not None
        assert len(account_reconciler.reconciliation_history) == 0
        assert account_reconciler.last_reconciliation is None

    async def test_balance_reconciliation(self, account_reconciler):
        """Test reconciliation of account balances between systems."""
        # FXML4 account state
        fxml4_state = {
            "account_id": "RECON_TEST",
            "balance": 10000.00,
            "equity": 10500.00,
            "unrealized_pl": 500.00,
            "last_update": datetime.utcnow(),
        }

        # ForexConnect account state
        forex_state = {
            "account_id": "RECON_TEST",
            "balance": 10000.00,
            "equity": 10500.00,
            "pl": 500.00,
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Perform reconciliation
        reconciliation_result = await account_reconciler.reconcile_account_balance(
            fxml4_state, forex_state
        )

        # Verify reconciliation result
        assert reconciliation_result.is_balanced == True
        assert reconciliation_result.balance_difference == 0.0
        assert reconciliation_result.equity_difference == 0.0
        assert len(reconciliation_result.discrepancies) == 0

    async def test_balance_discrepancy_detection(self, account_reconciler):
        """Test detection of balance discrepancies between systems."""
        # FXML4 state with different values
        fxml4_state = {
            "account_id": "DISCREPANCY_TEST",
            "balance": 10000.00,
            "equity": 10300.00,
            "unrealized_pl": 300.00,
            "last_update": datetime.utcnow(),
        }

        # ForexConnect state with discrepancies
        forex_state = {
            "account_id": "DISCREPANCY_TEST",
            "balance": 10050.00,  # $50 difference
            "equity": 10400.00,  # $100 difference
            "pl": 350.00,  # $50 difference
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Perform reconciliation
        reconciliation_result = await account_reconciler.reconcile_account_balance(
            fxml4_state, forex_state
        )

        # Verify discrepancy detection
        assert reconciliation_result.is_balanced == False
        assert reconciliation_result.balance_difference == -50.00  # FXML4 is $50 less
        assert reconciliation_result.equity_difference == -100.00  # FXML4 is $100 less
        assert len(reconciliation_result.discrepancies) > 0

        # Check discrepancy details
        discrepancy_types = [d.field for d in reconciliation_result.discrepancies]
        assert "balance" in discrepancy_types
        assert "equity" in discrepancy_types
        assert "unrealized_pl" in discrepancy_types

    async def test_position_reconciliation(self, account_reconciler):
        """Test reconciliation of positions between systems."""
        # FXML4 positions
        fxml4_positions = [
            {
                "position_id": "POS_001",
                "symbol": "EURUSD",
                "quantity": 100000,
                "unrealized_pl": 500.00,
            },
            {
                "position_id": "POS_002",
                "symbol": "GBPUSD",
                "quantity": -50000,
                "unrealized_pl": -200.00,
            },
        ]

        # ForexConnect positions (matching)
        forex_positions = [
            {
                "position_id": "POS_001",
                "symbol": "EURUSD",
                "quantity": 100000,
                "unrealized_pl": 500.00,
            },
            {
                "position_id": "POS_002",
                "symbol": "GBPUSD",
                "quantity": -50000,
                "unrealized_pl": -200.00,
            },
        ]

        reconciliation_result = await account_reconciler.reconcile_positions(
            fxml4_positions, forex_positions
        )

        # Verify position reconciliation
        assert reconciliation_result.positions_match == True
        assert len(reconciliation_result.missing_in_fxml4) == 0
        assert len(reconciliation_result.missing_in_forex) == 0
        assert len(reconciliation_result.quantity_differences) == 0

    async def test_position_discrepancy_detection(self, account_reconciler):
        """Test detection of position discrepancies."""
        # FXML4 positions
        fxml4_positions = [
            {
                "position_id": "POS_001",
                "symbol": "EURUSD",
                "quantity": 100000,
                "unrealized_pl": 500.00,
            },
            {
                "position_id": "POS_002",
                "symbol": "GBPUSD",
                "quantity": -50000,
                "unrealized_pl": -200.00,
            },
        ]

        # ForexConnect positions with discrepancies
        forex_positions = [
            {
                "position_id": "POS_001",
                "symbol": "EURUSD",
                "quantity": 120000,
                "unrealized_pl": 600.00,
            },  # Quantity diff
            {
                "position_id": "POS_003",
                "symbol": "USDJPY",
                "quantity": 75000,
                "unrealized_pl": 100.00,
            },  # Missing in FXML4
            # POS_002 missing in ForexConnect
        ]

        reconciliation_result = await account_reconciler.reconcile_positions(
            fxml4_positions, forex_positions
        )

        # Verify discrepancy detection
        assert reconciliation_result.positions_match == False
        assert len(reconciliation_result.missing_in_fxml4) == 1  # POS_003
        assert len(reconciliation_result.missing_in_forex) == 1  # POS_002
        assert len(reconciliation_result.quantity_differences) == 1  # POS_001

        # Check specific discrepancies
        assert "POS_003" in [
            p["position_id"] for p in reconciliation_result.missing_in_fxml4
        ]
        assert "POS_002" in [
            p["position_id"] for p in reconciliation_result.missing_in_forex
        ]

        qty_diff = reconciliation_result.quantity_differences[0]
        assert qty_diff["position_id"] == "POS_001"
        assert qty_diff["fxml4_quantity"] == 100000
        assert qty_diff["forex_quantity"] == 120000

    async def test_reconciliation_tolerance(self, account_reconciler):
        """Test reconciliation with tolerance for minor differences."""
        # Set tolerance for minor differences (e.g., rounding)
        await account_reconciler.set_reconciliation_tolerance(
            balance_tolerance=1.00, pl_tolerance=0.50  # $1 tolerance  # $0.50 tolerance
        )

        # States with minor differences within tolerance
        fxml4_state = {
            "account_id": "TOLERANCE_TEST",
            "balance": 10000.00,
            "equity": 10300.50,
            "unrealized_pl": 300.25,
            "last_update": datetime.utcnow(),
        }

        forex_state = {
            "account_id": "TOLERANCE_TEST",
            "balance": 10000.50,  # $0.50 difference (within tolerance)
            "equity": 10301.00,  # $0.50 difference (within tolerance)
            "pl": 300.50,  # $0.25 difference (within tolerance)
            "timestamp": datetime.utcnow().isoformat(),
        }

        reconciliation_result = await account_reconciler.reconcile_account_balance(
            fxml4_state, forex_state, apply_tolerance=True
        )

        # Should be considered balanced due to tolerance
        assert reconciliation_result.is_balanced == True
        assert reconciliation_result.within_tolerance == True

    async def test_reconciliation_history_tracking(self, account_reconciler):
        """Test tracking of reconciliation history."""
        # Perform multiple reconciliations
        for i in range(3):
            fxml4_state = {
                "account_id": f"HISTORY_TEST_{i}",
                "balance": 10000.00 + i * 100,
                "equity": 10000.00 + i * 100,
                "last_update": datetime.utcnow(),
            }

            forex_state = {
                "account_id": f"HISTORY_TEST_{i}",
                "balance": 10000.00 + i * 100,
                "equity": 10000.00 + i * 100,
                "timestamp": datetime.utcnow().isoformat(),
            }

            await account_reconciler.reconcile_account_balance(fxml4_state, forex_state)

        # Verify history tracking
        assert len(account_reconciler.reconciliation_history) == 3
        assert account_reconciler.last_reconciliation is not None

        # Check history contains expected data
        for result in account_reconciler.reconciliation_history:
            assert result.is_balanced == True
            assert "HISTORY_TEST" in result.account_id

    async def test_get_reconciliation_report(self, account_reconciler):
        """Test generation of reconciliation report."""
        # Perform reconciliation with some discrepancies
        fxml4_state = {
            "account_id": "REPORT_TEST",
            "balance": 10000.00,
            "equity": 10200.00,
            "last_update": datetime.utcnow(),
        }

        forex_state = {
            "account_id": "REPORT_TEST",
            "balance": 10050.00,
            "equity": 10250.00,
            "timestamp": datetime.utcnow().isoformat(),
        }

        await account_reconciler.reconcile_account_balance(fxml4_state, forex_state)

        # Generate report
        report = account_reconciler.get_reconciliation_report()

        # Verify report structure
        assert "total_reconciliations" in report
        assert "successful_reconciliations" in report
        assert "failed_reconciliations" in report
        assert "last_reconciliation" in report
        assert "common_discrepancy_types" in report

        # Verify report data
        assert report["total_reconciliations"] == 1
        assert report["failed_reconciliations"] == 1  # Due to balance discrepancy
        assert report["success_rate"] < 1.0


if __name__ == "__main__":
    """Run account monitoring tests."""
    pytest.main([__file__, "-v"])
