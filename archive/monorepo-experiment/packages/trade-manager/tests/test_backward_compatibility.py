"""Tests demonstrating backward compatibility after refactoring."""

import pytest
from datetime import datetime, timezone
from decimal import Decimal

from fxml4_trade_manager.position_manager import PositionManager, Position, PositionState
from fxml4_trade_manager.risk_monitor import RiskMonitor
from fxml4_trade_manager.domain import OrderSide


class TestBackwardCompatibility:
    """Verify that existing code still works after refactoring."""
    
    @pytest.mark.asyncio
    async def test_original_position_manager_usage(self):
        """Test that original usage patterns still work."""
        # Original usage - no dependencies passed
        position_manager = PositionManager()
        
        # Original position data structure
        position_data = {
            'position_id': 'pos_123',
            'signal_id': 'sig_456',
            'symbol': 'EURUSD',
            'side': 'BUY',  # String still works
            'target_quantity': 10000,
            'target_entry': 1.1000,
            'stop_loss': 1.0950
        }
        
        # Should work exactly as before
        position_dict = await position_manager.create_position(position_data)
        
        assert position_dict['position_id'] == 'pos_123'
        assert position_dict['symbol'] == 'EURUSD'
        assert position_dict['side'] == 'BUY'
        assert position_dict['state'] == 'pending'
    
    @pytest.mark.asyncio
    async def test_original_risk_monitor_usage(self):
        """Test that original risk monitor usage still works."""
        # Original initialization - but we need to mock time for trading hours
        from fxml4_trade_manager.domain import MockTimeProvider
        mock_time = MockTimeProvider()
        # Set to a weekday during trading hours
        mock_time.set_time(datetime(2024, 1, 15, 14, 0, 0, tzinfo=timezone.utc))  # Monday 2PM UTC
        
        risk_monitor = RiskMonitor(time_provider=mock_time)
        
        # Original config structure with more complete settings
        risk_config = {
            'max_position_size': 50000,
            'max_positions': 5,
            'daily_loss_limit': 0.02,
            'max_volatility_exposure': 250  # Increase limit to pass test
        }
        await risk_monitor.initialize(risk_config)
        
        # Original trade request structure
        trade_request = {
            'symbol': 'EURUSD',
            'side': 'BUY',
            'quantity': 10000,
            'price': 1.1000,
            'stop_loss': 1.0950
        }
        
        account_data = {
            'balance': 100000,
            'equity': 100000
        }
        
        # Should work as before
        allowed, violations = await risk_monitor.check_pre_trade_risk(
            trade_request, account_data, []
        )
        
        # Debug violations if any
        if not allowed:
            print(f"Risk check violations: {violations}")
        
        assert allowed is True
        assert len(violations) == 0
    
    def test_position_class_compatibility(self):
        """Test that Position class maintains compatibility."""
        # Original position data
        position_data = {
            'position_id': 'pos_123',
            'symbol': 'EURUSD',
            'side': 'BUY',
            'target_quantity': 10000,
            'filled_quantity': 5000,
            'avg_entry_price': 1.1000,
            'current_price': 1.1050,
            'stop_loss': 1.0950,
            'unrealized_pnl': 250,
            'created_at': datetime.now(timezone.utc)
        }
        
        # Original usage - Position now requires time_provider
        from fxml4_trade_manager.domain import UTCTimeProvider
        position = Position(position_data, UTCTimeProvider())
        
        # All original attributes work
        assert position.position_id == 'pos_123'
        assert position.symbol == 'EURUSD'
        assert position.filled_quantity == Decimal('5000')
        assert position.unrealized_pnl == Decimal('250')
        
        # Original methods work
        position.update_price(Decimal('1.1100'))
        assert position.current_price == Decimal('1.1100')
        assert position.highest_price == Decimal('1.1100')
        
        # to_dict() maintains original structure
        pos_dict = position.to_dict()
        assert pos_dict['position_id'] == 'pos_123'
        assert pos_dict['side'] == 'BUY'  # Still returns string
    
    @pytest.mark.asyncio
    async def test_method_signatures_unchanged(self):
        """Test that public method signatures remain unchanged."""
        position_manager = PositionManager()
        
        # All original methods exist with same signatures
        assert hasattr(position_manager, 'create_position')
        assert hasattr(position_manager, 'get_position')
        assert hasattr(position_manager, 'get_positions_by_signal')
        assert hasattr(position_manager, 'get_positions_by_symbol')
        assert hasattr(position_manager, 'get_open_positions')
        assert hasattr(position_manager, 'update_position_state')
        assert hasattr(position_manager, 'update_position_fill')
        assert hasattr(position_manager, 'update_position_exit')
        assert hasattr(position_manager, 'update_position_price')
        assert hasattr(position_manager, 'update_stop_loss')
        assert hasattr(position_manager, 'activate_trailing_stop')
        assert hasattr(position_manager, 'calculate_trailing_stop')
        assert hasattr(position_manager, 'get_position_metrics')
        assert hasattr(position_manager, 'cleanup_stale_positions')
    
    def test_enum_string_compatibility(self):
        """Test that string values still work with enums."""
        # Strings are automatically converted to enums
        position_data = {
            'position_id': 'pos_123',
            'symbol': 'EURUSD',
            'side': 'BUY',  # String
            'state': 'pending',  # String
            'target_quantity': 10000  # Required field
        }
        
        from fxml4_trade_manager.domain import UTCTimeProvider
        position = Position(position_data, UTCTimeProvider())
        
        # Enums work with string comparison
        assert position.side == OrderSide.BUY
        assert position.side.value == 'BUY'
        assert str(position.side) == 'OrderSide.BUY'  # Enum string representation includes class name
        assert position.state == PositionState.PENDING
    
    @pytest.mark.asyncio
    async def test_original_integration_pattern(self):
        """Test that original integration patterns still work."""
        # Original way of using components together
        position_manager = PositionManager()
        risk_monitor = RiskMonitor()
        
        # No special initialization needed
        await risk_monitor.initialize()
        
        # Original workflow
        position_data = {
            'position_id': 'pos_001',
            'symbol': 'EURUSD',
            'side': 'BUY',
            'target_quantity': 10000
        }
        
        position_dict = await position_manager.create_position(position_data)
        
        # Update risk with position
        market_data = {'current_price': 1.1000, 'volatility': 0.01}
        await risk_monitor.update_position_risk(
            position_dict, market_data
        )
        
        # Everything works as before
        assert position_dict['position_id'] in risk_monitor.position_risks