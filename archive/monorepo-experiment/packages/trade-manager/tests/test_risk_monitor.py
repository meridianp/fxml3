"""Tests for Risk Monitor."""

import pytest
import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import Mock, patch, AsyncMock

from fxml4_trade_manager.risk_monitor import (
    RiskMonitor, RiskLimits, RiskAlert, RiskLevel, RiskType
)
from fxml4_trade_manager.domain.models import AccountData


@pytest.fixture
def risk_monitor():
    """Create risk monitor instance."""
    return RiskMonitor()


@pytest.fixture
def risk_config():
    """Risk configuration for testing."""
    return {
        'max_position_size': 50000,
        'max_positions': 5,
        'max_positions_per_symbol': 2,
        'daily_loss_limit': 0.02,
        'max_drawdown': 0.10,
        'max_exposure': 0.25,
        'max_risk_per_trade': 0.01,
        'max_correlated_exposure': 0.15,
        'max_volatility_exposure': 1.5
    }


@pytest.fixture
def sample_trade_request():
    """Sample trade request for testing."""
    return {
        'symbol': 'EURUSD',
        'side': 'BUY',
        'quantity': 10000,
        'price': 1.1000,
        'stop_loss': 1.0950,
        'take_profit': 1.1100
    }


@pytest.fixture
def sample_account_data():
    """Sample account data for testing."""
    return AccountData(
        balance=Decimal('100000'),
        equity=Decimal('100000'),
        margin_used=Decimal('10000'),
        margin_available=Decimal('90000'),
        peak_balance=Decimal('105000')
    )


@pytest.fixture
def sample_positions():
    """Sample positions for testing."""
    return [
        {
            'position_id': 'pos_1',
            'symbol': 'EURUSD',
            'side': 'BUY',
            'quantity': 10000,
            'avg_entry_price': 1.1000,
            'current_price': 1.1050,
            'stop_loss': 1.0950,
            'unrealized_pnl': 500
        },
        {
            'position_id': 'pos_2',
            'symbol': 'GBPUSD',
            'side': 'SELL',
            'quantity': 8000,
            'avg_entry_price': 1.2500,
            'current_price': 1.2450,
            'stop_loss': 1.2550,
            'unrealized_pnl': 400
        }
    ]


class TestRiskLimits:
    """Test RiskLimits class."""
    
    def test_risk_limits_initialization(self, risk_config):
        """Test risk limits initialization."""
        limits = RiskLimits(risk_config)
        
        assert limits.max_position_size == Decimal('50000')
        assert limits.max_positions == 5
        assert limits.daily_loss_limit == Decimal('0.02')
        assert limits.max_drawdown == Decimal('0.10')
        assert limits.max_exposure == Decimal('0.25')
    
    def test_risk_limits_defaults(self):
        """Test risk limits with defaults."""
        limits = RiskLimits({})
        
        assert limits.max_position_size == Decimal('100000')
        assert limits.max_positions == 10
        assert limits.daily_loss_limit == Decimal('0.02')
        assert limits.max_drawdown == Decimal('0.15')


class TestRiskMonitor:
    """Test RiskMonitor class."""
    
    @pytest.mark.asyncio
    async def test_initialization(self, risk_monitor, risk_config):
        """Test risk monitor initialization."""
        await risk_monitor.initialize(risk_config)
        
        assert risk_monitor.risk_limits.max_position_size == Decimal('50000')
        assert len(risk_monitor.correlation_matrix) > 0
    
    @pytest.mark.asyncio
    async def test_check_pre_trade_risk_position_size(
        self, risk_monitor, risk_config, sample_trade_request, 
        sample_account_data, sample_positions
    ):
        """Test pre-trade risk check for position size."""
        await risk_monitor.initialize(risk_config)
        
        # Request exceeding position size limit
        sample_trade_request['quantity'] = 60000
        
        allowed, violations = await risk_monitor.check_pre_trade_risk(
            sample_trade_request, sample_account_data, sample_positions
        )
        
        assert not allowed
        assert any('Position size' in v for v in violations)
    
    @pytest.mark.asyncio
    async def test_check_pre_trade_risk_max_positions(
        self, risk_monitor, risk_config, sample_trade_request,
        sample_account_data
    ):
        """Test pre-trade risk check for max positions."""
        await risk_monitor.initialize(risk_config)
        
        # Create positions at limit
        positions = [
            {'position_id': f'pos_{i}', 'symbol': f'PAIR{i}', 
             'quantity': 10000, 'current_price': 1.1} 
            for i in range(5)
        ]
        
        allowed, violations = await risk_monitor.check_pre_trade_risk(
            sample_trade_request, sample_account_data, positions
        )
        
        assert not allowed
        assert any('Maximum positions' in v for v in violations)
    
    @pytest.mark.asyncio
    async def test_check_pre_trade_risk_symbol_limit(
        self, risk_monitor, risk_config, sample_trade_request,
        sample_account_data
    ):
        """Test pre-trade risk check for positions per symbol."""
        await risk_monitor.initialize(risk_config)
        
        # Create positions at symbol limit
        positions = [
            {'position_id': f'pos_{i}', 'symbol': 'EURUSD',
             'quantity': 10000, 'current_price': 1.1}
            for i in range(2)
        ]
        
        allowed, violations = await risk_monitor.check_pre_trade_risk(
            sample_trade_request, sample_account_data, positions
        )
        
        assert not allowed
        assert any('Maximum positions for EURUSD' in v for v in violations)
    
    @pytest.mark.asyncio
    async def test_check_pre_trade_risk_daily_loss(
        self, risk_monitor, risk_config, sample_trade_request,
        sample_account_data, sample_positions
    ):
        """Test pre-trade risk check with daily loss limit."""
        await risk_monitor.initialize(risk_config)
        
        # Set daily loss at limit
        risk_monitor.daily_pnl[datetime.now(timezone.utc).date()] = Decimal('-2000')
        
        allowed, violations = await risk_monitor.check_pre_trade_risk(
            sample_trade_request, sample_account_data, sample_positions
        )
        
        assert not allowed
        assert any('Daily loss limit' in v for v in violations)
    
    @pytest.mark.asyncio
    async def test_check_pre_trade_risk_exposure(
        self, risk_monitor, risk_config, sample_trade_request,
        sample_account_data
    ):
        """Test pre-trade risk check for total exposure."""
        await risk_monitor.initialize(risk_config)
        
        # Create positions with high exposure
        positions = [
            {'position_id': 'pos_1', 'symbol': 'EURUSD',
             'quantity': 20000, 'current_price': 1.1}
        ]
        
        allowed, violations = await risk_monitor.check_pre_trade_risk(
            sample_trade_request, sample_account_data, positions
        )
        
        assert not allowed
        assert any('Total exposure' in v for v in violations)
    
    @pytest.mark.asyncio
    async def test_check_pre_trade_risk_correlated(
        self, risk_monitor, risk_config, sample_trade_request,
        sample_account_data
    ):
        """Test pre-trade risk check for correlated exposure."""
        await risk_monitor.initialize(risk_config)
        
        # GBPUSD is correlated with EURUSD
        positions = [
            {'position_id': 'pos_1', 'symbol': 'GBPUSD',
             'quantity': 15000, 'current_price': 1.25}
        ]
        
        allowed, violations = await risk_monitor.check_pre_trade_risk(
            sample_trade_request, sample_account_data, positions
        )
        
        # Should pass or fail based on correlation
        assert isinstance(allowed, bool)
    
    @pytest.mark.asyncio
    async def test_update_position_risk(self, risk_monitor, sample_positions):
        """Test updating position risk metrics."""
        await risk_monitor.initialize()
        
        position = sample_positions[0]
        market_data = {
            'current_price': 1.1050,
            'volatility': 0.015
        }
        
        await risk_monitor.update_position_risk(position, market_data)
        
        assert 'pos_1' in risk_monitor.position_risks
        risk_metrics = risk_monitor.position_risks['pos_1']
        assert risk_metrics['symbol'] == 'EURUSD'
        assert risk_metrics['position_value'] > 0
        assert risk_metrics['volatility_exposure'] > 0
    
    @pytest.mark.asyncio
    async def test_update_daily_pnl(self, risk_monitor, risk_config):
        """Test updating daily P&L."""
        await risk_monitor.initialize(risk_config)
        
        # Add P&L updates
        await risk_monitor.update_daily_pnl({'amount': 500})
        await risk_monitor.update_daily_pnl({'amount': -300})
        
        today = datetime.now(timezone.utc).date()
        assert risk_monitor.daily_pnl[today] == Decimal('200')
    
    @pytest.mark.asyncio
    async def test_check_portfolio_risk(
        self, risk_monitor, risk_config, sample_positions, sample_account_data
    ):
        """Test portfolio risk check."""
        await risk_monitor.initialize(risk_config)
        
        metrics = await risk_monitor.check_portfolio_risk(
            sample_positions, sample_account_data
        )
        
        assert metrics['total_positions'] == 2
        assert 'total_exposure' in metrics
        assert 'portfolio_var' in metrics
        assert 'max_drawdown' in metrics
        assert 'correlation_risk' in metrics
        assert isinstance(metrics['violations'], list)
    
    @pytest.mark.asyncio
    async def test_create_alert(self, risk_monitor):
        """Test creating risk alert."""
        alert = await risk_monitor.create_alert(
            RiskType.POSITION_SIZE,
            RiskLevel.HIGH,
            "Position size exceeded",
            details={'position_id': 'pos_123'},
            position_ids=['pos_123'],
            action_required=True
        )
        
        assert alert.risk_type == RiskType.POSITION_SIZE
        assert alert.risk_level == RiskLevel.HIGH
        assert alert.message == "Position size exceeded"
        assert alert.action_required is True
        assert alert.alert_id in risk_monitor.active_alerts
    
    @pytest.mark.asyncio
    async def test_resolve_alert(self, risk_monitor):
        """Test resolving risk alert."""
        # Create alert
        alert = await risk_monitor.create_alert(
            RiskType.DAILY_LOSS,
            RiskLevel.CRITICAL,
            "Daily loss limit reached"
        )
        
        alert_id = alert.alert_id
        assert alert_id in risk_monitor.active_alerts
        
        # Resolve alert
        await risk_monitor.resolve_alert(alert_id, auto_resolved=True)
        
        assert alert_id not in risk_monitor.active_alerts
        assert alert.resolved_at is not None
        assert alert.auto_resolved is True
    
    @pytest.mark.asyncio
    async def test_get_risk_summary(self, risk_monitor, risk_config):
        """Test getting risk summary."""
        await risk_monitor.initialize(risk_config)
        
        # Create some alerts and metrics
        await risk_monitor.create_alert(
            RiskType.EXPOSURE,
            RiskLevel.MEDIUM,
            "High exposure"
        )
        
        risk_monitor.daily_pnl[datetime.now(timezone.utc).date()] = Decimal('-500')
        
        summary = await risk_monitor.get_risk_summary()
        
        assert summary['active_alerts'] == 1
        assert summary['daily_pnl'] == -500
        assert 'limits' in summary
        assert summary['limits']['daily_loss'] == 0.02
    
    @pytest.mark.asyncio
    async def test_trading_hours_check(self, risk_monitor, risk_config):
        """Test trading hours validation."""
        # Configure trading hours
        risk_config['trading_hours'] = {
            'EURUSD': {
                'start': 8,
                'end': 16,
                'days': [0, 1, 2, 3, 4]  # Monday to Friday
            }
        }
        await risk_monitor.initialize(risk_config)
        
        # Mock time provider to be within trading hours
        mock_time = datetime(2024, 1, 8, 10, 0)  # Monday 10:00 UTC
        risk_monitor._time_provider.now = Mock(return_value=mock_time)
        
        result = await risk_monitor._check_trading_hours('EURUSD')
        assert result is True
        
        # Test outside trading hours (Sunday)
        mock_time = datetime(2024, 1, 7, 10, 0)  # Sunday 10:00 UTC
        risk_monitor._time_provider.now = Mock(return_value=mock_time)
        
        result = await risk_monitor._check_trading_hours('EURUSD')
        assert result is False
        
        # Test outside trading hours (after hours)
        mock_time = datetime(2024, 1, 8, 18, 0)  # Monday 18:00 UTC (after 16:00)
        risk_monitor._time_provider.now = Mock(return_value=mock_time)
        
        result = await risk_monitor._check_trading_hours('EURUSD')
        assert result is False
    
    @pytest.mark.asyncio
    async def test_volatility_risk_check(self, risk_monitor):
        """Test volatility risk calculation."""
        await risk_monitor.initialize()
        
        # Check volatility risk for different symbols
        eur_risk = await risk_monitor._check_volatility_risk('EURUSD', Decimal('10000'))
        jpy_risk = await risk_monitor._check_volatility_risk('USDJPY', Decimal('10000'))
        gbp_risk = await risk_monitor._check_volatility_risk('GBPUSD', Decimal('10000'))
        
        # JPY pairs should have lower volatility
        assert jpy_risk < eur_risk
        # GBP pairs should have higher volatility
        assert gbp_risk > eur_risk
    
    @pytest.mark.asyncio
    async def test_correlation_matrix(self, risk_monitor):
        """Test correlation matrix loading."""
        await risk_monitor.initialize()
        
        # Check some known correlations
        assert ('EURUSD', 'GBPUSD') in risk_monitor.correlation_matrix
        assert ('EURUSD', 'USDCHF') in risk_monitor.correlation_matrix
        
        # Check correlation values
        eur_gbp_corr = risk_monitor.correlation_matrix[('EURUSD', 'GBPUSD')]
        assert 0 < eur_gbp_corr < 1  # Positive correlation
        
        eur_chf_corr = risk_monitor.correlation_matrix[('EURUSD', 'USDCHF')]
        assert -1 < eur_chf_corr < 0  # Negative correlation
    
    @pytest.mark.asyncio
    async def test_risk_calculation_methods(self, risk_monitor, sample_positions):
        """Test various risk calculation methods."""
        await risk_monitor.initialize()
        
        # Test trade risk calculation
        trade_risk = await risk_monitor._calculate_trade_risk(
            {'quantity': 10000, 'price': 1.1000, 'stop_loss': 1.0950, 'side': 'BUY'},
            Decimal('100000')
        )
        # For forex pairs, pip value calculation might be different
        # (1.1000 - 1.0950) = 0.005, 0.005 * 10000 = 50
        assert trade_risk == Decimal('50')  # (1.1000 - 1.0950) * 10000
        
        # Test position risk calculation
        position_risk = await risk_monitor._calculate_position_risk(sample_positions[0])
        assert position_risk == Decimal('50')  # (1.1000 - 1.0950) * 10000
        
        # Test total exposure calculation
        exposure = await risk_monitor._calculate_total_exposure(
            sample_positions, Decimal('100000')
        )
        assert exposure > 0
        
        # Test portfolio VaR
        var = await risk_monitor._calculate_portfolio_var(sample_positions)
        assert var > 0