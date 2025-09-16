"""
Live Trading Orchestrator - Core Trading System Validation

This orchestrator coordinates all components for live paper trading validation:
- Real-time market data streaming from Interactive Brokers
- Live ML signal generation and processing
- Real-time risk management and position sizing
- Paper trading order execution and tracking
- Performance validation and compliance logging

Success Criteria (30-day validation period):
- Achieve >15% annualized return with <10% maximum drawdown
- Enforce 2% max trade size / 6% max portfolio exposure
- Execute all trades within 30-second SLA
- Maintain 100% regulatory compliance audit trail
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

import pandas as pd

from ..brokers.adapters.ib_adapter import InteractiveBrokersAdapter
from ..database.timescaledb import TimescaleDBManager
from ..risk_management.position_sizing import PositionSizingManager
from ..strategy.gbpusd_signal_generator import GBPUSDSignalGenerator
from .compliance import ComplianceAuditLogger
from .execution import PaperTradingExecutor
from .market_data import RealTimeMarketDataHandler
from .performance import LivePerformanceTracker
from .risk_manager import LiveRiskManager
from .signal_processor import LiveSignalProcessor


class TradingSessionState(Enum):
    """Live trading session states"""

    INITIALIZING = "initializing"
    MARKET_CLOSED = "market_closed"
    PRE_MARKET = "pre_market"
    ACTIVE_TRADING = "active_trading"
    POST_MARKET = "post_market"
    EMERGENCY_STOP = "emergency_stop"
    SYSTEM_ERROR = "system_error"


@dataclass
class LiveTradingConfig:
    """Configuration for live trading system"""

    # Trading Parameters
    symbol: str = "GBPUSD"
    base_currency: str = "USD"
    paper_trading_account_size: float = 100000.0  # $100k paper account
    max_position_size_pct: float = 0.02  # 2% max per trade
    max_portfolio_exposure_pct: float = 0.06  # 6% max total exposure

    # Performance Targets
    target_annual_return: float = 0.15  # 15% annual return target
    max_drawdown_limit: float = 0.10  # 10% maximum drawdown
    validation_period_days: int = 30  # 30-day validation period

    # SLA Requirements
    max_signal_to_execution_seconds: int = 30  # 30-second execution SLA
    max_signal_generation_seconds: int = 2  # 2-second signal generation SLA
    market_data_timeout_seconds: int = 10  # 10-second market data timeout

    # Trading Sessions (UTC)
    london_session_start: int = 7  # 7:00 UTC
    london_session_end: int = 16  # 16:00 UTC
    ny_session_start: int = 12  # 12:00 UTC (overlap)
    ny_session_end: int = 21  # 21:00 UTC

    # Risk Management
    daily_loss_limit_pct: float = 0.05  # 5% daily loss limit
    consecutive_loss_limit: int = 5  # Stop after 5 consecutive losses
    correlation_limit: float = 0.8  # Max correlation between positions

    # Compliance
    audit_all_activities: bool = True
    regulatory_reporting: bool = True
    mifid_ii_compliance: bool = True


@dataclass
class TradingSessionMetrics:
    """Real-time trading session performance metrics"""

    session_start: datetime = field(default_factory=datetime.utcnow)
    total_signals_generated: int = 0
    total_orders_placed: int = 0
    total_trades_executed: int = 0

    # Performance Metrics
    current_portfolio_value: float = 0.0
    total_pnl: float = 0.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0

    # Risk Metrics
    current_drawdown: float = 0.0
    max_drawdown: float = 0.0
    current_exposure: float = 0.0
    largest_position_size: float = 0.0

    # Performance Ratios
    win_rate: float = 0.0
    profit_factor: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0

    # SLA Metrics
    avg_signal_generation_time: float = 0.0
    avg_execution_time: float = 0.0
    max_execution_time: float = 0.0
    sla_violations: int = 0

    # System Health
    market_data_drops: int = 0
    broker_connection_failures: int = 0
    risk_limit_violations: int = 0
    compliance_issues: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary for logging/storage"""
        return {
            "session_start": self.session_start.isoformat(),
            "total_signals_generated": self.total_signals_generated,
            "total_orders_placed": self.total_orders_placed,
            "total_trades_executed": self.total_trades_executed,
            "current_portfolio_value": self.current_portfolio_value,
            "total_pnl": self.total_pnl,
            "realized_pnl": self.realized_pnl,
            "unrealized_pnl": self.unrealized_pnl,
            "current_drawdown": self.current_drawdown,
            "max_drawdown": self.max_drawdown,
            "current_exposure": self.current_exposure,
            "win_rate": self.win_rate,
            "profit_factor": self.profit_factor,
            "sharpe_ratio": self.sharpe_ratio,
            "avg_signal_generation_time": self.avg_signal_generation_time,
            "avg_execution_time": self.avg_execution_time,
            "sla_violations": self.sla_violations,
            "market_data_drops": self.market_data_drops,
            "risk_limit_violations": self.risk_limit_violations,
        }


class LiveTradingOrchestrator:
    """
    Main orchestrator for live paper trading validation system.

    Coordinates all components to prove the trading system works profitably
    with real market data before proceeding to performance optimization.
    """

    def __init__(self, config: Optional[LiveTradingConfig] = None):
        self.config = config or LiveTradingConfig()
        self.session_state = TradingSessionState.INITIALIZING
        self.session_metrics = TradingSessionMetrics()

        # Core Components
        self.market_data_handler: Optional[RealTimeMarketDataHandler] = None
        self.signal_processor: Optional[LiveSignalProcessor] = None
        self.risk_manager: Optional[LiveRiskManager] = None
        self.executor: Optional[PaperTradingExecutor] = None
        self.performance_tracker: Optional[LivePerformanceTracker] = None
        self.compliance_logger: Optional[ComplianceAuditLogger] = None

        # Database and External Connections
        self.db_manager: Optional[TimescaleDBManager] = None
        self.ib_adapter: Optional[InteractiveBrokersAdapter] = None

        # Internal State
        self.active_positions: Dict[str, Any] = {}
        self.pending_orders: Dict[str, Any] = {}
        self.signal_history: List[Dict[str, Any]] = []

        # Control Flags
        self.is_running = False
        self.emergency_stop = False
        self.validation_complete = False

        self.logger = logging.getLogger(__name__)

    async def initialize(self) -> bool:
        """Initialize all trading system components"""
        try:
            self.logger.info("Initializing Live Trading System for Core Validation...")

            # Initialize database connection
            self.db_manager = TimescaleDBManager()
            await self.db_manager.initialize()

            # Initialize market data handler
            self.market_data_handler = RealTimeMarketDataHandler(
                symbol=self.config.symbol,
                timeout_seconds=self.config.market_data_timeout_seconds,
            )

            # Initialize signal processor with existing ML models
            self.signal_processor = LiveSignalProcessor(
                symbol=self.config.symbol,
                max_generation_time=self.config.max_signal_generation_seconds,
            )

            # Initialize risk management
            self.risk_manager = LiveRiskManager(
                account_size=self.config.paper_trading_account_size,
                max_position_pct=self.config.max_position_size_pct,
                max_portfolio_pct=self.config.max_portfolio_exposure_pct,
                daily_loss_limit=self.config.daily_loss_limit_pct,
            )

            # Initialize paper trading executor
            self.executor = PaperTradingExecutor(
                account_size=self.config.paper_trading_account_size,
                max_execution_time=self.config.max_signal_to_execution_seconds,
            )

            # Initialize performance tracking
            self.performance_tracker = LivePerformanceTracker(
                target_return=self.config.target_annual_return,
                max_drawdown=self.config.max_drawdown_limit,
                validation_days=self.config.validation_period_days,
            )

            # Initialize compliance logging
            self.compliance_logger = ComplianceAuditLogger(
                enable_mifid_ii=self.config.mifid_ii_compliance,
                enable_audit_trail=self.config.audit_all_activities,
            )

            # Initialize all components
            await self.market_data_handler.initialize()
            await self.signal_processor.initialize()
            await self.risk_manager.initialize()
            await self.executor.initialize()
            await self.performance_tracker.initialize()
            await self.compliance_logger.initialize()

            self.session_state = TradingSessionState.MARKET_CLOSED
            self.logger.info("✅ Live Trading System initialized successfully")
            return True

        except Exception as e:
            self.logger.error(f"❌ Failed to initialize Live Trading System: {e}")
            self.session_state = TradingSessionState.SYSTEM_ERROR
            return False

    async def start_validation_session(self) -> bool:
        """Start live paper trading validation session"""
        try:
            if not await self.initialize():
                return False

            self.logger.info("🚀 Starting 30-Day Live Paper Trading Validation Session")
            self.logger.info(
                f"Target: {self.config.target_annual_return*100:.1f}% return, <{self.config.max_drawdown_limit*100:.1f}% drawdown"
            )

            self.is_running = True
            self.session_metrics.session_start = datetime.utcnow()

            # Log validation start
            await self.compliance_logger.log_session_start(
                {
                    "session_type": "paper_trading_validation",
                    "validation_period_days": self.config.validation_period_days,
                    "target_return": self.config.target_annual_return,
                    "max_drawdown": self.config.max_drawdown_limit,
                    "account_size": self.config.paper_trading_account_size,
                }
            )

            # Main trading loop
            await self._run_trading_session()

            return True

        except Exception as e:
            self.logger.error(f"❌ Validation session failed: {e}")
            await self._emergency_stop()
            return False

    async def _run_trading_session(self):
        """Main trading session loop"""
        while self.is_running and not self.emergency_stop:
            try:
                # Check market hours and session state
                await self._update_session_state()

                if self.session_state == TradingSessionState.ACTIVE_TRADING:
                    # Core trading workflow
                    await self._execute_trading_cycle()
                elif self.session_state == TradingSessionState.MARKET_CLOSED:
                    # End-of-day processing
                    await self._process_end_of_day()
                    await asyncio.sleep(300)  # 5-minute check during closed market
                else:
                    # Pre/post market monitoring
                    await asyncio.sleep(60)  # 1-minute check

                # Update performance metrics
                await self._update_session_metrics()

                # Check validation completion
                if await self._check_validation_complete():
                    break

                # Health checks and safety stops
                await self._perform_health_checks()

            except Exception as e:
                self.logger.error(f"Error in trading session: {e}")
                await self._handle_session_error(e)
                await asyncio.sleep(30)  # Recovery pause

    async def _execute_trading_cycle(self):
        """Execute one complete trading cycle"""
        cycle_start = datetime.utcnow()

        try:
            # 1. Get real-time market data
            market_data = await self.market_data_handler.get_latest_data()
            if not market_data:
                self.session_metrics.market_data_drops += 1
                return

            # 2. Generate trading signal
            signal_start = datetime.utcnow()
            signal = await self.signal_processor.generate_live_signal(market_data)
            signal_time = (datetime.utcnow() - signal_start).total_seconds()

            # Update SLA metrics
            self.session_metrics.avg_signal_generation_time = (
                self.session_metrics.avg_signal_generation_time
                * self.session_metrics.total_signals_generated
                + signal_time
            ) / (self.session_metrics.total_signals_generated + 1)
            self.session_metrics.total_signals_generated += 1

            # Check signal generation SLA
            if signal_time > self.config.max_signal_generation_seconds:
                self.session_metrics.sla_violations += 1
                self.logger.warning(
                    f"⚠️ Signal generation SLA violation: {signal_time:.2f}s > {self.config.max_signal_generation_seconds}s"
                )

            if not signal or signal.get("action") == "hold":
                return

            # 3. Risk management validation
            risk_check = await self.risk_manager.validate_signal(
                signal, self.active_positions, market_data
            )

            if not risk_check.approved:
                self.session_metrics.risk_limit_violations += 1
                await self.compliance_logger.log_risk_rejection(
                    {
                        "signal": signal,
                        "rejection_reason": risk_check.rejection_reason,
                        "current_exposure": self.session_metrics.current_exposure,
                    }
                )
                return

            # 4. Execute trade
            execution_start = datetime.utcnow()
            execution_result = await self.executor.execute_signal(
                signal, risk_check.position_size, market_data
            )
            execution_time = (datetime.utcnow() - execution_start).total_seconds()

            # Update execution metrics
            total_exec_time = (
                self.session_metrics.avg_execution_time
                * self.session_metrics.total_orders_placed
                + execution_time
            )
            self.session_metrics.total_orders_placed += 1
            self.session_metrics.avg_execution_time = (
                total_exec_time / self.session_metrics.total_orders_placed
            )
            self.session_metrics.max_execution_time = max(
                self.session_metrics.max_execution_time, execution_time
            )

            # Check execution SLA
            total_cycle_time = (datetime.utcnow() - cycle_start).total_seconds()
            if total_cycle_time > self.config.max_signal_to_execution_seconds:
                self.session_metrics.sla_violations += 1
                self.logger.warning(
                    f"⚠️ End-to-end execution SLA violation: {total_cycle_time:.2f}s > {self.config.max_signal_to_execution_seconds}s"
                )

            # 5. Update positions and performance
            if execution_result.success:
                await self._update_positions(execution_result)
                await self.performance_tracker.record_trade(execution_result)
                self.session_metrics.total_trades_executed += 1

                self.logger.info(
                    f"✅ Trade executed: {signal['action']} {execution_result.quantity} {self.config.symbol} @ {execution_result.price}"
                )

            # 6. Compliance logging
            await self.compliance_logger.log_trading_activity(
                {
                    "signal": signal,
                    "risk_check": risk_check.to_dict(),
                    "execution": (
                        execution_result.to_dict() if execution_result else None
                    ),
                    "cycle_time_seconds": total_cycle_time,
                    "sla_compliant": total_cycle_time
                    <= self.config.max_signal_to_execution_seconds,
                }
            )

        except Exception as e:
            self.logger.error(f"Error in trading cycle: {e}")
            await self.compliance_logger.log_system_error(
                {
                    "error_type": "trading_cycle_error",
                    "error_message": str(e),
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )

    async def _update_session_state(self):
        """Update trading session state based on market hours"""
        current_hour = datetime.utcnow().hour

        # Check if market is open (London or NY session)
        london_active = (
            self.config.london_session_start
            <= current_hour
            < self.config.london_session_end
        )
        ny_active = (
            self.config.ny_session_start <= current_hour < self.config.ny_session_end
        )

        if london_active or ny_active:
            if self.session_state != TradingSessionState.ACTIVE_TRADING:
                self.session_state = TradingSessionState.ACTIVE_TRADING
                self.logger.info("🟢 Market session active - starting live trading")
        else:
            if self.session_state == TradingSessionState.ACTIVE_TRADING:
                self.session_state = TradingSessionState.MARKET_CLOSED
                self.logger.info("🔴 Market session closed - stopping live trading")

    async def _update_session_metrics(self):
        """Update real-time session metrics"""
        try:
            # Get current portfolio value from performance tracker
            current_performance = (
                await self.performance_tracker.get_current_performance()
            )

            self.session_metrics.current_portfolio_value = (
                current_performance.portfolio_value
            )
            self.session_metrics.total_pnl = current_performance.total_pnl
            self.session_metrics.realized_pnl = current_performance.realized_pnl
            self.session_metrics.unrealized_pnl = current_performance.unrealized_pnl

            # Risk metrics
            self.session_metrics.current_drawdown = current_performance.current_drawdown
            self.session_metrics.max_drawdown = current_performance.max_drawdown
            self.session_metrics.current_exposure = sum(
                abs(pos.get("market_value", 0))
                for pos in self.active_positions.values()
            )

            # Performance ratios
            self.session_metrics.win_rate = current_performance.win_rate
            self.session_metrics.profit_factor = current_performance.profit_factor
            self.session_metrics.sharpe_ratio = current_performance.sharpe_ratio

            # Log metrics periodically
            session_hours = (
                datetime.utcnow() - self.session_metrics.session_start
            ).total_seconds() / 3600
            if int(session_hours) > 0 and int(session_hours) % 6 == 0:  # Every 6 hours
                self.logger.info(
                    f"📊 Session Update: P&L {self.session_metrics.total_pnl:+.2f}, "
                    f"Drawdown {self.session_metrics.current_drawdown:.2%}, "
                    f"Trades {self.session_metrics.total_trades_executed}, "
                    f"Win Rate {self.session_metrics.win_rate:.1%}"
                )

        except Exception as e:
            self.logger.error(f"Error updating session metrics: {e}")

    async def _check_validation_complete(self) -> bool:
        """Check if 30-day validation period is complete and assess success"""
        session_days = (datetime.utcnow() - self.session_metrics.session_start).days

        if session_days >= self.config.validation_period_days:
            self.validation_complete = True
            await self._complete_validation_assessment()
            return True

        return False

    async def _complete_validation_assessment(self):
        """Complete final validation assessment"""
        self.logger.info("🏁 Completing 30-Day Paper Trading Validation Assessment...")

        # Get final performance metrics
        final_performance = await self.performance_tracker.get_validation_results()

        # Success criteria assessment
        success_criteria = {
            "target_return_met": final_performance.annualized_return
            >= self.config.target_annual_return,
            "drawdown_within_limit": final_performance.max_drawdown
            <= self.config.max_drawdown_limit,
            "risk_limits_enforced": self.session_metrics.risk_limit_violations == 0,
            "sla_compliance": self.session_metrics.sla_violations
            < 10,  # <1% of trading cycles
            "system_stability": self.session_metrics.market_data_drops
            < 50,  # <5% data loss
        }

        validation_successful = all(success_criteria.values())

        # Final validation report
        validation_report = {
            "validation_period_days": self.config.validation_period_days,
            "session_start": self.session_metrics.session_start.isoformat(),
            "session_end": datetime.utcnow().isoformat(),
            "validation_successful": validation_successful,
            "success_criteria": success_criteria,
            "final_performance": final_performance.to_dict(),
            "session_metrics": self.session_metrics.to_dict(),
            "recommendation": (
                "APPROVED_FOR_LIVE_TRADING"
                if validation_successful
                else "REQUIRES_OPTIMIZATION"
            ),
        }

        # Log final results
        if validation_successful:
            self.logger.info(
                "🎉 VALIDATION SUCCESSFUL - Core Trading System APPROVED for Live Trading!"
            )
            self.logger.info(
                f"📈 Achieved {final_performance.annualized_return:.1%} return with {final_performance.max_drawdown:.1%} max drawdown"
            )
        else:
            self.logger.warning(
                "⚠️ VALIDATION INCOMPLETE - System requires optimization before live trading"
            )
            self.logger.warning(
                f"📉 Return: {final_performance.annualized_return:.1%}, Drawdown: {final_performance.max_drawdown:.1%}"
            )

        # Store validation report
        await self.compliance_logger.log_validation_completion(validation_report)

        # Store in database for analysis
        if self.db_manager:
            await self.db_manager.store_validation_results(validation_report)

        self.is_running = False

    async def _perform_health_checks(self):
        """Perform system health checks and safety stops"""
        try:
            # Check drawdown limits
            if (
                self.session_metrics.current_drawdown
                > self.config.max_drawdown_limit * 1.5
            ):  # 150% of limit
                self.logger.error(
                    f"❌ EMERGENCY STOP: Drawdown {self.session_metrics.current_drawdown:.2%} exceeds limit"
                )
                await self._emergency_stop()
                return

            # Check daily loss limits
            daily_pnl = await self.performance_tracker.get_daily_pnl()
            if (
                daily_pnl
                < -self.config.daily_loss_limit_pct
                * self.config.paper_trading_account_size
            ):
                self.logger.warning(f"⚠️ Daily loss limit reached: {daily_pnl:.2f}")
                self.session_state = (
                    TradingSessionState.MARKET_CLOSED
                )  # Stop trading for the day

            # Check system connectivity
            if not await self.market_data_handler.health_check():
                self.session_metrics.broker_connection_failures += 1
                if self.session_metrics.broker_connection_failures > 5:
                    self.logger.error(
                        "❌ Multiple broker connection failures - emergency stop"
                    )
                    await self._emergency_stop()

        except Exception as e:
            self.logger.error(f"Error in health checks: {e}")

    async def _emergency_stop(self):
        """Emergency stop all trading activities"""
        self.logger.critical("🚨 EMERGENCY STOP ACTIVATED")
        self.emergency_stop = True
        self.session_state = TradingSessionState.EMERGENCY_STOP

        try:
            # Close all open positions
            for position_id in list(self.active_positions.keys()):
                await self.executor.close_position(position_id, "EMERGENCY_STOP")

            # Cancel pending orders
            for order_id in list(self.pending_orders.keys()):
                await self.executor.cancel_order(order_id)

            await self.compliance_logger.log_emergency_stop(
                {
                    "reason": "system_safety_stop",
                    "active_positions": len(self.active_positions),
                    "pending_orders": len(self.pending_orders),
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )

        except Exception as e:
            self.logger.error(f"Error during emergency stop: {e}")

    async def _update_positions(self, execution_result):
        """Update position tracking"""
        position_id = execution_result.position_id

        if position_id in self.active_positions:
            # Update existing position
            position = self.active_positions[position_id]
            position["quantity"] += execution_result.quantity
            position["market_value"] = position["quantity"] * execution_result.price

            # Close position if quantity is zero
            if abs(position["quantity"]) < 1e-6:
                self.active_positions.pop(position_id)
        else:
            # New position
            self.active_positions[position_id] = {
                "symbol": self.config.symbol,
                "quantity": execution_result.quantity,
                "entry_price": execution_result.price,
                "current_price": execution_result.price,
                "market_value": execution_result.quantity * execution_result.price,
                "open_time": datetime.utcnow(),
                "pnl": 0.0,
            }

    async def _process_end_of_day(self):
        """End-of-day processing and reporting"""
        try:
            # Update position values with current market prices
            if self.active_positions:
                current_prices = await self.market_data_handler.get_current_prices()
                for position in self.active_positions.values():
                    if position["symbol"] in current_prices:
                        position["current_price"] = current_prices[position["symbol"]]
                        position["pnl"] = (
                            position["current_price"] - position["entry_price"]
                        ) * position["quantity"]

            # Calculate end-of-day metrics
            daily_performance = await self.performance_tracker.get_daily_performance()

            # End-of-day report
            self.logger.info(
                f"📅 End-of-Day Report: P&L {daily_performance.daily_pnl:+.2f}, "
                f"Trades {daily_performance.daily_trades}, "
                f"Active Positions {len(self.active_positions)}"
            )

            # Store daily summary
            await self.compliance_logger.log_daily_summary(
                {
                    "date": datetime.utcnow().date().isoformat(),
                    "daily_pnl": daily_performance.daily_pnl,
                    "daily_trades": daily_performance.daily_trades,
                    "active_positions": len(self.active_positions),
                    "session_metrics": self.session_metrics.to_dict(),
                }
            )

        except Exception as e:
            self.logger.error(f"Error in end-of-day processing: {e}")

    async def _handle_session_error(self, error: Exception):
        """Handle session-level errors"""
        self.logger.error(f"Session error: {error}")
        await self.compliance_logger.log_system_error(
            {
                "error_type": "session_error",
                "error_message": str(error),
                "session_state": self.session_state.value,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

        # If critical error, initiate emergency stop
        if isinstance(error, (ConnectionError, TimeoutError)):
            await self._emergency_stop()

    async def get_validation_status(self) -> Dict[str, Any]:
        """Get current validation status"""
        session_days = (datetime.utcnow() - self.session_metrics.session_start).days
        days_remaining = max(0, self.config.validation_period_days - session_days)

        current_performance = await self.performance_tracker.get_current_performance()

        return {
            "validation_active": self.is_running,
            "validation_complete": self.validation_complete,
            "days_elapsed": session_days,
            "days_remaining": days_remaining,
            "session_state": self.session_state.value,
            "current_return": current_performance.annualized_return,
            "target_return": self.config.target_annual_return,
            "current_drawdown": self.session_metrics.current_drawdown,
            "max_drawdown_limit": self.config.max_drawdown_limit,
            "total_trades": self.session_metrics.total_trades_executed,
            "win_rate": self.session_metrics.win_rate,
            "sla_violations": self.session_metrics.sla_violations,
            "system_health": "healthy" if not self.emergency_stop else "emergency_stop",
            "recommendation": self._get_current_recommendation(),
        }

    def _get_current_recommendation(self) -> str:
        """Get current recommendation based on performance"""
        if self.validation_complete:
            return "validation_complete"
        elif self.emergency_stop:
            return "system_requires_repair"
        elif self.session_metrics.current_drawdown > self.config.max_drawdown_limit:
            return "risk_optimization_required"
        elif self.session_metrics.sla_violations > 10:
            return "performance_optimization_required"
        else:
            return "validation_in_progress"

    async def cleanup(self):
        """Cleanup resources"""
        try:
            self.logger.info("Cleaning up Live Trading System...")
            self.is_running = False

            # Cleanup all components
            if self.market_data_handler:
                await self.market_data_handler.cleanup()
            if self.signal_processor:
                await self.signal_processor.cleanup()
            if self.risk_manager:
                await self.risk_manager.cleanup()
            if self.executor:
                await self.executor.cleanup()
            if self.performance_tracker:
                await self.performance_tracker.cleanup()
            if self.compliance_logger:
                await self.compliance_logger.cleanup()
            if self.db_manager:
                await self.db_manager.cleanup()

            self.logger.info("✅ Live Trading System cleanup completed")

        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
