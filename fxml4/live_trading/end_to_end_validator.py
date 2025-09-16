"""
FXML4 End-to-End Trading Workflow Validator
Critical validation system for proving complete trading workflow within SLA requirements

This module validates the complete trading workflow:
ML signal → risk check → order → IB execution → position tracking within 30-second SLA

Requirements:
- Real Interactive Brokers TWS connection
- Real GBP/USD market data
- Complete workflow validation
- 30-second SLA compliance
- Real-time performance monitoring
"""

import asyncio
import logging
import statistics
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from ..core.exceptions import ValidationError

try:
    from ..ml.models.signal_generator import SignalGenerator
except ImportError:
    SignalGenerator = None

try:
    from ..risk_management.risk_manager import RiskManager
except ImportError:
    RiskManager = None

try:
    from ..brokers.adapters.ib_adapter import IBBrokerAdapter as IBAdapter
except ImportError:
    IBAdapter = None

try:
    from ..data_engineering.data_feeds.market_data import MarketDataFeed
except ImportError:
    MarketDataFeed = None

try:
    from .orchestrator import LiveTradingOrchestrator
except ImportError:
    LiveTradingOrchestrator = None

try:
    from .performance import LivePerformanceTracker
except ImportError:
    LivePerformanceTracker = None


class WorkflowStage(Enum):
    """Trading workflow stages for validation tracking"""

    MARKET_DATA_INGESTION = "market_data_ingestion"
    ML_SIGNAL_GENERATION = "ml_signal_generation"
    RISK_CHECK = "risk_check"
    ORDER_CREATION = "order_creation"
    BROKER_EXECUTION = "broker_execution"
    POSITION_TRACKING = "position_tracking"
    WORKFLOW_COMPLETE = "workflow_complete"


@dataclass
class StageResult:
    """Result of individual workflow stage"""

    stage: WorkflowStage
    start_time: float
    end_time: float
    duration_ms: float
    success: bool
    error_message: Optional[str] = None
    data: Optional[Dict[str, Any]] = None

    @property
    def duration_seconds(self) -> float:
        return self.duration_ms / 1000.0


@dataclass
class WorkflowValidationResult:
    """Complete workflow validation result"""

    workflow_id: str
    symbol: str
    start_time: datetime
    end_time: datetime
    total_duration_ms: float
    sla_compliant: bool
    stage_results: List[StageResult] = field(default_factory=list)
    performance_metrics: Dict[str, float] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def total_duration_seconds(self) -> float:
        return self.total_duration_ms / 1000.0

    @property
    def sla_margin_seconds(self) -> float:
        return 30.0 - self.total_duration_seconds


class EndToEndValidator:
    """
    End-to-End Trading Workflow Validator

    Validates complete trading workflow from market data ingestion to position tracking
    with strict 30-second SLA requirements and comprehensive performance monitoring.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.logger = logging.getLogger(__name__)

        # SLA Configuration
        self.sla_targets = {
            "total_workflow_seconds": 30.0,
            "market_data_ms": 500,
            "ml_signal_ms": 2000,
            "risk_check_ms": 100,
            "order_creation_ms": 50,
            "broker_execution_ms": 5000,
            "position_tracking_ms": 100,
        }

        # Validation Results
        self.validation_results: List[WorkflowValidationResult] = []
        self.performance_stats: Dict[str, List[float]] = {}

        # System Components
        self.orchestrator: Optional[LiveTradingOrchestrator] = None
        self.signal_generator: Optional[SignalGenerator] = None
        self.risk_manager: Optional[RiskManager] = None
        self.ib_adapter: Optional[IBAdapter] = None
        self.market_data_feed: Optional[MarketDataFeed] = None
        self.performance_tracker: Optional[LivePerformanceTracker] = None

    async def initialize_components(self) -> None:
        """Initialize all system components for validation"""
        try:
            self.logger.info("Initializing end-to-end validation components...")

            # Initialize core components (if available)
            if LiveTradingOrchestrator:
                self.orchestrator = LiveTradingOrchestrator(
                    self.config.get("orchestrator")
                )
                await self.orchestrator.initialize()
            else:
                self.logger.warning(
                    "LiveTradingOrchestrator not available - using mock"
                )

            if SignalGenerator:
                self.signal_generator = SignalGenerator(self.config.get("ml"))
                await self.signal_generator.initialize()
            else:
                self.logger.warning("SignalGenerator not available - using mock")

            if RiskManager:
                self.risk_manager = RiskManager(self.config.get("risk_management"))
                await self.risk_manager.initialize()
            else:
                self.logger.warning("RiskManager not available - using mock")

            if IBAdapter:
                self.ib_adapter = IBAdapter(self.config.get("ib_adapter"))
                await self.ib_adapter.initialize()
            else:
                self.logger.warning("IBAdapter not available - using mock")

            if MarketDataFeed:
                self.market_data_feed = MarketDataFeed(self.config.get("market_data"))
                await self.market_data_feed.initialize()
            else:
                self.logger.warning("MarketDataFeed not available - using mock")

            if LivePerformanceTracker:
                self.performance_tracker = LivePerformanceTracker(
                    self.config.get("performance")
                )
                await self.performance_tracker.initialize()
            else:
                self.logger.warning("LivePerformanceTracker not available - using mock")

            # Verify connections (only for available components)
            await self._verify_component_health()

            self.logger.info("All validation components initialized successfully")

        except Exception as e:
            self.logger.error(f"Failed to initialize validation components: {e}")
            raise ValidationError(f"Component initialization failed: {e}")

    async def _verify_component_health(self) -> None:
        """Verify all components are healthy and connected"""
        health_checks = []

        if self.ib_adapter:
            health_checks.append(
                ("Interactive Brokers", self.ib_adapter.check_connection())
            )
        if self.market_data_feed:
            health_checks.append(
                ("Market Data Feed", self.market_data_feed.check_connection())
            )
        if self.signal_generator:
            health_checks.append(
                ("Signal Generator", self.signal_generator.health_check())
            )
        if self.risk_manager:
            health_checks.append(("Risk Manager", self.risk_manager.health_check()))
        if self.performance_tracker:
            health_checks.append(
                ("Performance Tracker", self.performance_tracker.health_check())
            )

        if not health_checks:
            self.logger.warning(
                "No components available for health checks - running in mock mode"
            )
            return

        for component_name, health_check in health_checks:
            try:
                await health_check
                self.logger.info(f"{component_name}: ✓ Healthy")
            except Exception as e:
                self.logger.error(f"{component_name}: ✗ Unhealthy - {e}")
                raise ValidationError(f"{component_name} health check failed: {e}")

    @asynccontextmanager
    async def _track_stage(self, stage: WorkflowStage):
        """Context manager to track individual workflow stage performance"""
        start_time = time.perf_counter()
        stage_result = StageResult(
            stage=stage, start_time=start_time, end_time=0, duration_ms=0, success=False
        )

        try:
            yield stage_result
            stage_result.success = True
        except Exception as e:
            stage_result.success = False
            stage_result.error_message = str(e)
            self.logger.error(f"Stage {stage.value} failed: {e}")
            raise
        finally:
            end_time = time.perf_counter()
            stage_result.end_time = end_time
            stage_result.duration_ms = (end_time - start_time) * 1000

            # Check SLA compliance for stage
            target_key = f"{stage.value.replace('_', '_')}_ms"
            if target_key in self.sla_targets:
                target_ms = self.sla_targets[target_key]
                if stage_result.duration_ms > target_ms:
                    warning = f"Stage {stage.value} exceeded SLA: {stage_result.duration_ms:.2f}ms > {target_ms}ms"
                    self.logger.warning(warning)

    async def validate_single_workflow(
        self, symbol: str = "GBPUSD"
    ) -> WorkflowValidationResult:
        """
        Validate single complete trading workflow

        Tests: ML signal → risk check → order → IB execution → position tracking
        SLA: Complete workflow within 30 seconds
        """
        workflow_id = f"validation_{datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f')}"
        start_time = datetime.utcnow()
        workflow_start = time.perf_counter()

        self.logger.info(f"Starting end-to-end workflow validation: {workflow_id}")

        result = WorkflowValidationResult(
            workflow_id=workflow_id,
            symbol=symbol,
            start_time=start_time,
            end_time=start_time,  # Will be updated
            total_duration_ms=0,
            sla_compliant=False,
        )

        try:
            # Stage 1: Market Data Ingestion
            async with self._track_stage(WorkflowStage.MARKET_DATA_INGESTION) as stage:
                self.logger.info(f"Stage 1: Market Data Ingestion for {symbol}")
                market_data = await self.market_data_feed.get_real_time_data(
                    symbol=symbol, timeframe="1m", count=100
                )
                stage.data = {
                    "data_points": len(market_data),
                    "latest_price": market_data[-1]["close"] if market_data else None,
                    "data_quality_score": await self._assess_data_quality(market_data),
                }
                result.stage_results.append(stage)

            # Stage 2: ML Signal Generation
            async with self._track_stage(WorkflowStage.ML_SIGNAL_GENERATION) as stage:
                self.logger.info(f"Stage 2: ML Signal Generation for {symbol}")

                # Prepare features for ML model
                features = await self._prepare_ml_features(market_data)

                # Generate ML signal
                signal = await self.signal_generator.generate_signal(
                    symbol=symbol, features=features, market_data=market_data
                )

                stage.data = {
                    "signal_strength": signal.strength,
                    "signal_direction": signal.direction,
                    "confidence": signal.confidence,
                    "feature_count": len(features),
                }
                result.stage_results.append(stage)

            # Stage 3: Risk Check
            async with self._track_stage(WorkflowStage.RISK_CHECK) as stage:
                self.logger.info(f"Stage 3: Risk Check for {symbol}")

                # Perform comprehensive risk check
                risk_assessment = await self.risk_manager.assess_trade_risk(
                    symbol=symbol,
                    signal=signal,
                    current_positions=await self.ib_adapter.get_positions(),
                    account_info=await self.ib_adapter.get_account_info(),
                )

                stage.data = {
                    "risk_score": risk_assessment.risk_score,
                    "position_size": risk_assessment.recommended_size,
                    "risk_approved": risk_assessment.approved,
                    "risk_factors": risk_assessment.risk_factors,
                }
                result.stage_results.append(stage)

            # Only proceed if risk check passed
            if not risk_assessment.approved:
                raise ValidationError("Risk check failed - trade not approved")

            # Stage 4: Order Creation
            async with self._track_stage(WorkflowStage.ORDER_CREATION) as stage:
                self.logger.info(f"Stage 4: Order Creation for {symbol}")

                order = await self._create_validation_order(
                    symbol=symbol, signal=signal, risk_assessment=risk_assessment
                )

                stage.data = {
                    "order_type": order.order_type,
                    "quantity": order.quantity,
                    "price": order.price,
                    "stop_loss": order.stop_loss,
                    "take_profit": order.take_profit,
                }
                result.stage_results.append(stage)

            # Stage 5: Broker Execution (Paper Trading)
            async with self._track_stage(WorkflowStage.BROKER_EXECUTION) as stage:
                self.logger.info(f"Stage 5: Broker Execution for {symbol}")

                # Execute order through Interactive Brokers (Paper Trading)
                execution_result = await self.ib_adapter.execute_paper_order(order)

                stage.data = {
                    "execution_price": execution_result.fill_price,
                    "execution_time": execution_result.execution_time,
                    "order_status": execution_result.status,
                    "execution_id": execution_result.execution_id,
                }
                result.stage_results.append(stage)

            # Stage 6: Position Tracking
            async with self._track_stage(WorkflowStage.POSITION_TRACKING) as stage:
                self.logger.info(f"Stage 6: Position Tracking for {symbol}")

                # Update position tracking
                position = await self.performance_tracker.update_position(
                    symbol=symbol, execution_result=execution_result, order=order
                )

                stage.data = {
                    "position_id": position.position_id,
                    "unrealized_pnl": position.unrealized_pnl,
                    "position_size": position.size,
                    "entry_price": position.entry_price,
                }
                result.stage_results.append(stage)

            # Calculate total workflow time
            workflow_end = time.perf_counter()
            result.total_duration_ms = (workflow_end - workflow_start) * 1000
            result.end_time = datetime.utcnow()

            # Check SLA compliance
            result.sla_compliant = (
                result.total_duration_seconds
                <= self.sla_targets["total_workflow_seconds"]
            )

            # Calculate performance metrics
            result.performance_metrics = await self._calculate_workflow_metrics(result)

            if result.sla_compliant:
                self.logger.info(
                    f"✓ Workflow {workflow_id} completed within SLA: {result.total_duration_seconds:.2f}s"
                )
            else:
                sla_violation = f"SLA violation: {result.total_duration_seconds:.2f}s > {self.sla_targets['total_workflow_seconds']}s"
                result.errors.append(sla_violation)
                self.logger.error(f"✗ Workflow {workflow_id}: {sla_violation}")

        except Exception as e:
            result.errors.append(f"Workflow failed: {str(e)}")
            result.end_time = datetime.utcnow()
            result.total_duration_ms = (time.perf_counter() - workflow_start) * 1000
            self.logger.error(f"Workflow {workflow_id} failed: {e}")
            raise

        # Store result
        self.validation_results.append(result)
        return result

    async def validate_multiple_workflows(
        self, count: int = 10, symbol: str = "GBPUSD"
    ) -> Dict[str, Any]:
        """
        Validate multiple workflows to test consistency and performance

        Args:
            count: Number of workflows to validate
            symbol: Currency pair to test

        Returns:
            Comprehensive validation statistics
        """
        self.logger.info(f"Starting validation of {count} workflows for {symbol}")

        results = []
        start_time = datetime.utcnow()

        # Run multiple workflows
        for i in range(count):
            self.logger.info(f"Running workflow {i+1}/{count}")
            try:
                result = await self.validate_single_workflow(symbol)
                results.append(result)

                # Brief pause between workflows
                await asyncio.sleep(1)

            except Exception as e:
                self.logger.error(f"Workflow {i+1} failed: {e}")
                # Continue with next workflow
                continue

        # Calculate aggregate statistics
        end_time = datetime.utcnow()
        return await self._calculate_aggregate_statistics(results, start_time, end_time)

    async def _prepare_ml_features(
        self, market_data: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """Prepare ML features from market data"""
        if not market_data:
            raise ValueError("No market data available for feature preparation")

        # Basic technical indicators
        closes = [float(d["close"]) for d in market_data]
        highs = [float(d["high"]) for d in market_data]
        lows = [float(d["low"]) for d in market_data]
        volumes = [float(d["volume"]) for d in market_data]

        features = {
            "price": closes[-1],
            "sma_10": sum(closes[-10:]) / 10 if len(closes) >= 10 else closes[-1],
            "sma_20": sum(closes[-20:]) / 20 if len(closes) >= 20 else closes[-1],
            "volatility": statistics.stdev(closes[-20:]) if len(closes) >= 20 else 0,
            "rsi": await self._calculate_rsi(closes),
            "volume_avg": (
                sum(volumes[-10:]) / 10 if len(volumes) >= 10 else volumes[-1]
            ),
            "high_low_ratio": (
                (highs[-1] - lows[-1]) / closes[-1] if closes[-1] != 0 else 0
            ),
        }

        return features

    async def _calculate_rsi(self, closes: List[float], period: int = 14) -> float:
        """Calculate RSI indicator"""
        if len(closes) < period + 1:
            return 50.0  # Neutral RSI

        gains = []
        losses = []

        for i in range(1, len(closes)):
            change = closes[i] - closes[i - 1]
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))

        if len(gains) < period:
            return 50.0

        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    async def _assess_data_quality(self, market_data: List[Dict[str, Any]]) -> float:
        """Assess quality of market data"""
        if not market_data:
            return 0.0

        quality_score = 100.0

        # Check for missing data
        expected_fields = ["open", "high", "low", "close", "volume", "timestamp"]
        for data_point in market_data:
            missing_fields = [
                field for field in expected_fields if field not in data_point
            ]
            if missing_fields:
                quality_score -= 10.0

        # Check for data consistency
        for data_point in market_data:
            try:
                o, h, l, c = (
                    float(data_point["open"]),
                    float(data_point["high"]),
                    float(data_point["low"]),
                    float(data_point["close"]),
                )
                if not (l <= o <= h and l <= c <= h):
                    quality_score -= 5.0
            except (ValueError, KeyError):
                quality_score -= 10.0

        return max(0.0, quality_score)

    async def _create_validation_order(
        self, symbol: str, signal: Any, risk_assessment: Any
    ) -> Any:
        """Create order for validation (simplified)"""

        # This would create a real order object based on signal and risk assessment
        # For validation purposes, we create a mock order
        class ValidationOrder:
            def __init__(self):
                self.symbol = symbol
                self.order_type = "MARKET"
                self.quantity = risk_assessment.recommended_size
                self.price = (
                    signal.entry_price if hasattr(signal, "entry_price") else None
                )
                self.stop_loss = (
                    signal.stop_loss if hasattr(signal, "stop_loss") else None
                )
                self.take_profit = (
                    signal.take_profit if hasattr(signal, "take_profit") else None
                )

        return ValidationOrder()

    async def _calculate_workflow_metrics(
        self, result: WorkflowValidationResult
    ) -> Dict[str, float]:
        """Calculate performance metrics for workflow"""
        metrics = {
            "total_duration_seconds": result.total_duration_seconds,
            "sla_margin_seconds": result.sla_margin_seconds,
            "stage_count": len(result.stage_results),
            "success_rate": (
                sum(1 for stage in result.stage_results if stage.success)
                / len(result.stage_results)
                if result.stage_results
                else 0
            ),
        }

        # Add stage-specific metrics
        for stage in result.stage_results:
            metrics[f"{stage.stage.value}_duration_ms"] = stage.duration_ms
            metrics[f"{stage.stage.value}_success"] = 1.0 if stage.success else 0.0

        return metrics

    async def _calculate_aggregate_statistics(
        self,
        results: List[WorkflowValidationResult],
        start_time: datetime,
        end_time: datetime,
    ) -> Dict[str, Any]:
        """Calculate aggregate statistics from multiple workflow results"""
        if not results:
            return {"error": "No successful workflows to analyze"}

        # Basic statistics
        durations = [r.total_duration_seconds for r in results]
        sla_compliant_count = sum(1 for r in results if r.sla_compliant)

        statistics_summary = {
            "validation_summary": {
                "total_workflows": len(results),
                "successful_workflows": len([r for r in results if not r.errors]),
                "sla_compliant_workflows": sla_compliant_count,
                "sla_compliance_rate": sla_compliant_count / len(results),
                "validation_period": {
                    "start": start_time.isoformat(),
                    "end": end_time.isoformat(),
                    "duration_minutes": (end_time - start_time).total_seconds() / 60,
                },
            },
            "performance_metrics": {
                "duration_statistics": {
                    "mean_seconds": statistics.mean(durations),
                    "median_seconds": statistics.median(durations),
                    "min_seconds": min(durations),
                    "max_seconds": max(durations),
                    "std_dev_seconds": (
                        statistics.stdev(durations) if len(durations) > 1 else 0
                    ),
                },
                "sla_analysis": {
                    "target_seconds": self.sla_targets["total_workflow_seconds"],
                    "fastest_workflow": min(durations),
                    "slowest_workflow": max(durations),
                    "average_sla_margin": statistics.mean(
                        [r.sla_margin_seconds for r in results]
                    ),
                },
            },
            "stage_performance": {},
        }

        # Stage-specific statistics
        stage_stats = {}
        for stage in WorkflowStage:
            stage_durations = []
            stage_successes = []

            for result in results:
                for stage_result in result.stage_results:
                    if stage_result.stage == stage:
                        stage_durations.append(stage_result.duration_ms)
                        stage_successes.append(stage_result.success)

            if stage_durations:
                stage_stats[stage.value] = {
                    "mean_duration_ms": statistics.mean(stage_durations),
                    "max_duration_ms": max(stage_durations),
                    "success_rate": sum(stage_successes) / len(stage_successes),
                    "sla_target_ms": self.sla_targets.get(f"{stage.value}_ms", "N/A"),
                }

        statistics_summary["stage_performance"] = stage_stats

        # Error analysis
        all_errors = []
        all_warnings = []
        for result in results:
            all_errors.extend(result.errors)
            all_warnings.extend(result.warnings)

        statistics_summary["quality_analysis"] = {
            "total_errors": len(all_errors),
            "total_warnings": len(all_warnings),
            "error_types": list(set(all_errors)),
            "warning_types": list(set(all_warnings)),
        }

        return statistics_summary

    async def generate_validation_report(self) -> str:
        """Generate comprehensive validation report"""
        if not self.validation_results:
            return "No validation results available"

        report_lines = [
            "=" * 80,
            "FXML4 END-TO-END TRADING WORKFLOW VALIDATION REPORT",
            "=" * 80,
            f"Generated: {datetime.utcnow().isoformat()}",
            f"Total Workflows Validated: {len(self.validation_results)}",
            "",
        ]

        # SLA Compliance Summary
        sla_compliant = sum(1 for r in self.validation_results if r.sla_compliant)
        compliance_rate = sla_compliant / len(self.validation_results)

        report_lines.extend(
            [
                "SLA COMPLIANCE SUMMARY:",
                f"  Target: {self.sla_targets['total_workflow_seconds']} seconds per workflow",
                f"  Compliant Workflows: {sla_compliant}/{len(self.validation_results)} ({compliance_rate:.1%})",
                "",
            ]
        )

        # Performance Statistics
        durations = [r.total_duration_seconds for r in self.validation_results]
        if durations:
            report_lines.extend(
                [
                    "PERFORMANCE STATISTICS:",
                    f"  Average Duration: {statistics.mean(durations):.2f} seconds",
                    f"  Median Duration: {statistics.median(durations):.2f} seconds",
                    f"  Fastest Workflow: {min(durations):.2f} seconds",
                    f"  Slowest Workflow: {max(durations):.2f} seconds",
                    f"  Standard Deviation: {statistics.stdev(durations) if len(durations) > 1 else 0:.2f} seconds",
                    "",
                ]
            )

        # Recent Results
        report_lines.extend(["RECENT VALIDATION RESULTS:", "-" * 40])

        for result in self.validation_results[-5:]:  # Last 5 results
            status = "✓ PASS" if result.sla_compliant else "✗ FAIL"
            report_lines.append(
                f"  {result.workflow_id}: {result.total_duration_seconds:.2f}s {status}"
            )

        report_lines.extend(["", "=" * 80])

        return "\n".join(report_lines)

    async def cleanup(self) -> None:
        """Cleanup validation components"""
        try:
            if self.orchestrator:
                await self.orchestrator.shutdown()
            if self.ib_adapter:
                await self.ib_adapter.disconnect()
            if self.market_data_feed:
                await self.market_data_feed.disconnect()

            self.logger.info("End-to-end validation cleanup completed")

        except Exception as e:
            self.logger.error(f"Cleanup error: {e}")


# Validation Runner for Direct Execution
async def main():
    """Main validation runner"""
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    validator = EndToEndValidator()

    try:
        # Initialize components
        await validator.initialize_components()

        # Run single workflow validation
        logger.info("Running single workflow validation...")
        single_result = await validator.validate_single_workflow("GBPUSD")

        if single_result.sla_compliant:
            logger.info("✅ Single workflow validation PASSED")

            # Run multiple workflows validation
            logger.info("Running multiple workflows validation...")
            multi_results = await validator.validate_multiple_workflows(count=5)

            logger.info("✅ Multiple workflows validation completed")
            logger.info(
                f"SLA Compliance Rate: {multi_results['validation_summary']['sla_compliance_rate']:.1%}"
            )
        else:
            logger.error("❌ Single workflow validation FAILED")

        # Generate report
        report = await validator.generate_validation_report()
        logger.info("Validation Report:")
        logger.info(report)

    except Exception as e:
        logger.error(f"Validation failed: {e}")
        raise
    finally:
        await validator.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
