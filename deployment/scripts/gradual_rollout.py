#!/usr/bin/env python3
"""
FXML4 Gradual Rollout Manager
Manages the phased rollout of trading system with progressive limit increases
"""

import asyncio
import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class RolloutPhase(Enum):
    """Rollout phases."""

    PHASE_1 = "phase_1"  # Initial conservative limits
    PHASE_2 = "phase_2"  # Moderate limits
    PHASE_3 = "phase_3"  # Near-production limits
    PRODUCTION = "production"  # Full production


@dataclass
class RolloutCriteria:
    """Criteria for phase progression."""

    min_duration_days: int
    min_trades: int
    max_loss_percent: float
    min_win_rate: float
    max_drawdown_percent: float
    min_sharpe_ratio: float
    max_error_rate: float
    manual_approval_required: bool


@dataclass
class RolloutMetrics:
    """Metrics tracked during rollout."""

    phase_start_time: datetime
    total_trades: int
    winning_trades: int
    total_pnl: float
    max_drawdown: float
    current_drawdown: float
    error_count: int
    total_requests: int
    daily_metrics: List[Dict[str, Any]]

    @property
    def win_rate(self) -> float:
        """Calculate win rate."""
        if self.total_trades == 0:
            return 0.0
        return self.winning_trades / self.total_trades

    @property
    def error_rate(self) -> float:
        """Calculate error rate."""
        if self.total_requests == 0:
            return 0.0
        return self.error_count / self.total_requests

    @property
    def duration_days(self) -> float:
        """Calculate phase duration in days."""
        return (
            datetime.now(timezone.utc) - self.phase_start_time
        ).total_seconds() / 86400

    def calculate_sharpe_ratio(self) -> float:
        """Calculate Sharpe ratio from daily returns."""
        if len(self.daily_metrics) < 2:
            return 0.0

        daily_returns = [m["daily_return"] for m in self.daily_metrics]

        if not daily_returns:
            return 0.0

        import numpy as np

        returns = np.array(daily_returns)

        if returns.std() == 0:
            return 0.0

        # Annualized Sharpe (252 trading days)
        return np.sqrt(252) * returns.mean() / returns.std()


class GradualRolloutManager:
    """Manages gradual rollout of trading system."""

    def __init__(self, config_path: str):
        self.config = self._load_config(config_path)
        self.state_file = Path("deployment/rollout_state.json")
        self.current_state = self._load_state()

        # Define rollout criteria
        self.criteria = {
            RolloutPhase.PHASE_1: RolloutCriteria(
                min_duration_days=7,
                min_trades=50,
                max_loss_percent=2.0,
                min_win_rate=0.45,
                max_drawdown_percent=3.0,
                min_sharpe_ratio=0.5,
                max_error_rate=0.05,
                manual_approval_required=True,
            ),
            RolloutPhase.PHASE_2: RolloutCriteria(
                min_duration_days=14,
                min_trades=100,
                max_loss_percent=3.0,
                min_win_rate=0.48,
                max_drawdown_percent=4.0,
                min_sharpe_ratio=0.8,
                max_error_rate=0.03,
                manual_approval_required=True,
            ),
            RolloutPhase.PHASE_3: RolloutCriteria(
                min_duration_days=21,
                min_trades=200,
                max_loss_percent=4.0,
                min_win_rate=0.50,
                max_drawdown_percent=5.0,
                min_sharpe_ratio=1.0,
                max_error_rate=0.02,
                manual_approval_required=True,
            ),
        }

    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load environment configuration."""
        with open(config_path, "r") as f:
            return yaml.safe_load(f)

    def _load_state(self) -> Dict[str, Any]:
        """Load rollout state."""
        if self.state_file.exists():
            with open(self.state_file, "r") as f:
                return json.load(f)

        # Initialize state
        return {
            "current_phase": RolloutPhase.PHASE_1.value,
            "phase_start_time": datetime.now(timezone.utc).isoformat(),
            "metrics": asdict(
                RolloutMetrics(
                    phase_start_time=datetime.now(timezone.utc),
                    total_trades=0,
                    winning_trades=0,
                    total_pnl=0.0,
                    max_drawdown=0.0,
                    current_drawdown=0.0,
                    error_count=0,
                    total_requests=0,
                    daily_metrics=[],
                )
            ),
            "phase_history": [],
        }

    def _save_state(self):
        """Save rollout state."""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_file, "w") as f:
            json.dump(self.current_state, f, indent=2, default=str)

    async def check_phase_progression(self) -> Tuple[bool, Optional[str]]:
        """Check if current phase can be progressed."""
        current_phase = RolloutPhase(self.current_state["current_phase"])

        if current_phase == RolloutPhase.PRODUCTION:
            return False, "Already in production phase"

        # Get current metrics
        metrics = RolloutMetrics(**self.current_state["metrics"])
        metrics.phase_start_time = datetime.fromisoformat(
            str(metrics.phase_start_time).replace("Z", "+00:00")
        )

        # Get criteria for current phase
        criteria = self.criteria[current_phase]

        # Check all criteria
        checks = []

        # Duration check
        if metrics.duration_days < criteria.min_duration_days:
            checks.append(
                f"Insufficient duration: {metrics.duration_days:.1f} < {criteria.min_duration_days} days"
            )

        # Trade count check
        if metrics.total_trades < criteria.min_trades:
            checks.append(
                f"Insufficient trades: {metrics.total_trades} < {criteria.min_trades}"
            )

        # Loss check
        if metrics.total_pnl < 0:
            loss_percent = abs(metrics.total_pnl) / self._get_initial_capital() * 100
            if loss_percent > criteria.max_loss_percent:
                checks.append(
                    f"Excessive loss: {loss_percent:.2f}% > {criteria.max_loss_percent}%"
                )

        # Win rate check
        if metrics.win_rate < criteria.min_win_rate:
            checks.append(
                f"Low win rate: {metrics.win_rate:.2%} < {criteria.min_win_rate:.2%}"
            )

        # Drawdown check
        if abs(metrics.max_drawdown) > criteria.max_drawdown_percent:
            checks.append(
                f"Excessive drawdown: {abs(metrics.max_drawdown):.2f}% > {criteria.max_drawdown_percent}%"
            )

        # Sharpe ratio check
        sharpe = metrics.calculate_sharpe_ratio()
        if sharpe < criteria.min_sharpe_ratio:
            checks.append(
                f"Low Sharpe ratio: {sharpe:.2f} < {criteria.min_sharpe_ratio}"
            )

        # Error rate check
        if metrics.error_rate > criteria.max_error_rate:
            checks.append(
                f"High error rate: {metrics.error_rate:.2%} > {criteria.max_error_rate:.2%}"
            )

        if checks:
            return False, f"Criteria not met: {'; '.join(checks)}"

        # Check manual approval
        if criteria.manual_approval_required:
            if not self._check_manual_approval(current_phase):
                return False, "Manual approval required"

        return True, None

    def _get_initial_capital(self) -> float:
        """Get initial capital from config."""
        return self.config["trading"].get("initial_capital", 100000)

    def _check_manual_approval(self, phase: RolloutPhase) -> bool:
        """Check if manual approval has been granted."""
        approval_file = Path(f"deployment/approvals/{phase.value}_approved.txt")
        return approval_file.exists()

    async def progress_phase(self) -> bool:
        """Progress to next phase."""
        current_phase = RolloutPhase(self.current_state["current_phase"])

        # Check if progression is allowed
        can_progress, reason = await self.check_phase_progression()

        if not can_progress:
            logger.warning(f"Cannot progress phase: {reason}")
            return False

        # Determine next phase
        phase_order = [
            RolloutPhase.PHASE_1,
            RolloutPhase.PHASE_2,
            RolloutPhase.PHASE_3,
            RolloutPhase.PRODUCTION,
        ]

        current_index = phase_order.index(current_phase)
        if current_index >= len(phase_order) - 1:
            logger.info("Already at final phase")
            return False

        next_phase = phase_order[current_index + 1]

        # Archive current phase metrics
        self.current_state["phase_history"].append(
            {
                "phase": current_phase.value,
                "start_time": self.current_state["phase_start_time"],
                "end_time": datetime.now(timezone.utc).isoformat(),
                "metrics": self.current_state["metrics"],
            }
        )

        # Update to next phase
        self.current_state["current_phase"] = next_phase.value
        self.current_state["phase_start_time"] = datetime.now(timezone.utc).isoformat()
        self.current_state["metrics"] = asdict(
            RolloutMetrics(
                phase_start_time=datetime.now(timezone.utc),
                total_trades=0,
                winning_trades=0,
                total_pnl=0.0,
                max_drawdown=0.0,
                current_drawdown=0.0,
                error_count=0,
                total_requests=0,
                daily_metrics=[],
            )
        )

        # Save state
        self._save_state()

        # Apply new limits
        await self._apply_phase_limits(next_phase)

        logger.info(f"Successfully progressed to {next_phase.value}")
        return True

    async def _apply_phase_limits(self, phase: RolloutPhase):
        """Apply trading limits for phase."""
        logger.info(f"Applying limits for {phase.value}")

        # Get limits from config
        if phase == RolloutPhase.PHASE_1:
            limits = self.config["trading"]["phase1_limits"]
        elif phase == RolloutPhase.PHASE_2:
            limits = self.config["trading"]["phase2_limits"]
        elif phase == RolloutPhase.PHASE_3:
            limits = self.config["trading"].get(
                "phase3_limits", self.config["trading"]["phase2_limits"]
            )
        else:
            limits = self.config["trading"]["production_limits"]

        # Update configuration in Kubernetes
        config_map = {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {"name": "trading-limits", "namespace": "default"},
            "data": {"limits.json": json.dumps(limits, indent=2)},
        }

        # Save ConfigMap
        config_file = Path(f"/tmp/trading-limits-{phase.value}.yaml")
        with open(config_file, "w") as f:
            yaml.dump(config_map, f)

        # Apply to cluster
        import subprocess

        result = subprocess.run(
            ["kubectl", "apply", "-f", str(config_file)], capture_output=True
        )

        if result.returncode != 0:
            logger.error(f"Failed to apply limits: {result.stderr}")
            raise RuntimeError("Failed to apply phase limits")

        # Restart trading engine to pick up new limits
        subprocess.run(
            ["kubectl", "rollout", "restart", "deployment/fxml4-trading-engine"]
        )

        logger.info(f"Applied {phase.value} limits: {limits}")

    async def update_metrics(
        self,
        trade_result: Optional[Dict[str, Any]] = None,
        request_success: bool = True,
    ):
        """Update rollout metrics."""
        metrics = RolloutMetrics(**self.current_state["metrics"])
        metrics.phase_start_time = datetime.fromisoformat(
            str(metrics.phase_start_time).replace("Z", "+00:00")
        )

        # Update request metrics
        metrics.total_requests += 1
        if not request_success:
            metrics.error_count += 1

        # Update trade metrics if provided
        if trade_result:
            metrics.total_trades += 1

            if trade_result["pnl"] > 0:
                metrics.winning_trades += 1

            metrics.total_pnl += trade_result["pnl"]

            # Update drawdown
            if metrics.total_pnl < metrics.max_drawdown:
                metrics.max_drawdown = metrics.total_pnl

            # Current drawdown from peak
            peak_pnl = (
                max(m.get("cumulative_pnl", 0) for m in metrics.daily_metrics)
                if metrics.daily_metrics
                else 0
            )
            metrics.current_drawdown = (
                (metrics.total_pnl - peak_pnl) / self._get_initial_capital() * 100
            )

        # Update state
        self.current_state["metrics"] = asdict(metrics)
        self._save_state()

    async def record_daily_metrics(self):
        """Record daily metrics snapshot."""
        metrics = RolloutMetrics(**self.current_state["metrics"])
        metrics.phase_start_time = datetime.fromisoformat(
            str(metrics.phase_start_time).replace("Z", "+00:00")
        )

        # Calculate daily return
        initial_capital = self._get_initial_capital()
        daily_return = metrics.total_pnl / initial_capital

        # Add to daily metrics
        daily_snapshot = {
            "date": datetime.now(timezone.utc).date().isoformat(),
            "trades": metrics.total_trades,
            "pnl": metrics.total_pnl,
            "cumulative_pnl": metrics.total_pnl,
            "daily_return": daily_return,
            "win_rate": metrics.win_rate,
            "error_rate": metrics.error_rate,
            "max_drawdown": metrics.max_drawdown,
        }

        metrics.daily_metrics.append(daily_snapshot)

        # Keep only last 30 days
        if len(metrics.daily_metrics) > 30:
            metrics.daily_metrics = metrics.daily_metrics[-30:]

        # Update state
        self.current_state["metrics"] = asdict(metrics)
        self._save_state()

        logger.info(f"Recorded daily metrics: {daily_snapshot}")

    def get_current_status(self) -> Dict[str, Any]:
        """Get current rollout status."""
        current_phase = RolloutPhase(self.current_state["current_phase"])
        metrics = RolloutMetrics(**self.current_state["metrics"])
        metrics.phase_start_time = datetime.fromisoformat(
            str(metrics.phase_start_time).replace("Z", "+00:00")
        )

        # Get current limits
        if current_phase == RolloutPhase.PHASE_1:
            current_limits = self.config["trading"]["phase1_limits"]
        elif current_phase == RolloutPhase.PHASE_2:
            current_limits = self.config["trading"]["phase2_limits"]
        elif current_phase == RolloutPhase.PHASE_3:
            current_limits = self.config["trading"].get(
                "phase3_limits", self.config["trading"]["phase2_limits"]
            )
        else:
            current_limits = self.config["trading"]["production_limits"]

        # Check progression readiness
        can_progress, reason = asyncio.run(self.check_phase_progression())

        return {
            "current_phase": current_phase.value,
            "phase_duration_days": metrics.duration_days,
            "current_limits": current_limits,
            "metrics": {
                "total_trades": metrics.total_trades,
                "win_rate": metrics.win_rate,
                "total_pnl": metrics.total_pnl,
                "max_drawdown": metrics.max_drawdown,
                "current_drawdown": metrics.current_drawdown,
                "error_rate": metrics.error_rate,
                "sharpe_ratio": metrics.calculate_sharpe_ratio(),
            },
            "can_progress": can_progress,
            "progression_status": reason or "Ready to progress",
            "phase_history": self.current_state["phase_history"],
        }

    async def emergency_rollback(self) -> bool:
        """Emergency rollback to previous phase."""
        current_phase = RolloutPhase(self.current_state["current_phase"])

        if current_phase == RolloutPhase.PHASE_1:
            logger.warning("Already at minimum phase, cannot rollback further")
            return False

        # Get previous phase
        phase_order = [
            RolloutPhase.PHASE_1,
            RolloutPhase.PHASE_2,
            RolloutPhase.PHASE_3,
            RolloutPhase.PRODUCTION,
        ]

        current_index = phase_order.index(current_phase)
        previous_phase = phase_order[current_index - 1]

        logger.warning(
            f"Emergency rollback from {current_phase.value} to {previous_phase.value}"
        )

        # Update state
        self.current_state["current_phase"] = previous_phase.value
        self.current_state["phase_start_time"] = datetime.now(timezone.utc).isoformat()

        # Reset metrics but keep history
        self.current_state["metrics"] = asdict(
            RolloutMetrics(
                phase_start_time=datetime.now(timezone.utc),
                total_trades=0,
                winning_trades=0,
                total_pnl=0.0,
                max_drawdown=0.0,
                current_drawdown=0.0,
                error_count=0,
                total_requests=0,
                daily_metrics=[],
            )
        )

        # Add rollback event to history
        self.current_state["phase_history"].append(
            {
                "event": "emergency_rollback",
                "from_phase": current_phase.value,
                "to_phase": previous_phase.value,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "reason": "Emergency rollback triggered",
            }
        )

        self._save_state()

        # Apply previous phase limits
        await self._apply_phase_limits(previous_phase)

        return True

    def generate_rollout_report(self) -> str:
        """Generate comprehensive rollout report."""
        status = self.get_current_status()

        report = f"""
# FXML4 Gradual Rollout Report
Generated: {datetime.now(timezone.utc).isoformat()}

## Current Status
- **Phase**: {status['current_phase']}
- **Duration**: {status['phase_duration_days']:.1f} days
- **Progress**: {status['progression_status']}

## Current Limits
- Max Daily Trades: {status['current_limits']['max_daily_trades']}
- Max Position Size: ${status['current_limits']['max_position_size_usd']:,}
- Max Total Exposure: ${status['current_limits']['max_total_exposure_usd']:,}
- Allowed Symbols: {', '.join(status['current_limits']['allowed_symbols'])}
- Max Leverage: {status['current_limits']['max_leverage']}x

## Performance Metrics
- Total Trades: {status['metrics']['total_trades']}
- Win Rate: {status['metrics']['win_rate']:.1%}
- Total P&L: ${status['metrics']['total_pnl']:,.2f}
- Max Drawdown: {status['metrics']['max_drawdown']:.2f}%
- Current Drawdown: {status['metrics']['current_drawdown']:.2f}%
- Error Rate: {status['metrics']['error_rate']:.2%}
- Sharpe Ratio: {status['metrics']['sharpe_ratio']:.2f}

## Phase History
"""

        for event in status["phase_history"]:
            if "event" in event:
                report += f"\n### {event['event']} - {event['timestamp']}"
                report += f"\n- From: {event['from_phase']}"
                report += f"\n- To: {event['to_phase']}"
                report += f"\n- Reason: {event['reason']}\n"
            else:
                report += f"\n### Phase: {event['phase']}"
                report += f"\n- Duration: {event['start_time']} to {event['end_time']}"
                metrics = event["metrics"]
                report += f"\n- Trades: {metrics['total_trades']}"
                report += f"\n- P&L: ${metrics['total_pnl']:,.2f}"
                report += f"\n- Win Rate: {metrics['winning_trades']/max(metrics['total_trades'],1):.1%}\n"

        # Add recommendations
        report += "\n## Recommendations\n"

        if status["can_progress"]:
            report += "- ✅ **Ready for phase progression**\n"
            report += "- Ensure manual approval is documented\n"
            report += "- Review phase history for any concerns\n"
        else:
            report += (
                f"- ⚠️ **Not ready for progression**: {status['progression_status']}\n"
            )

            metrics = status["metrics"]
            if metrics["win_rate"] < 0.5:
                report += "- Investigate low win rate - review signal generation\n"
            if metrics["error_rate"] > 0.02:
                report += "- Address high error rate - check system stability\n"
            if abs(metrics["max_drawdown"]) > 3:
                report += "- Review risk management - drawdown exceeds comfort zone\n"

        return report


async def main():
    """CLI for gradual rollout management."""
    import argparse

    parser = argparse.ArgumentParser(description="FXML4 Gradual Rollout Manager")

    parser.add_argument(
        "action",
        choices=["status", "progress", "rollback", "report", "update-metrics"],
        help="Action to perform",
    )

    parser.add_argument(
        "--config",
        default="deployment/environments/production.yaml",
        help="Path to environment config",
    )

    parser.add_argument(
        "--trade-result", type=json.loads, help="Trade result JSON for metrics update"
    )

    parser.add_argument(
        "--request-success",
        type=bool,
        default=True,
        help="Whether request was successful",
    )

    args = parser.parse_args()

    manager = GradualRolloutManager(args.config)

    if args.action == "status":
        status = manager.get_current_status()
        print(json.dumps(status, indent=2, default=str))

    elif args.action == "progress":
        success = await manager.progress_phase()
        if success:
            print("Successfully progressed to next phase")
        else:
            print("Failed to progress phase - check criteria")

    elif args.action == "rollback":
        success = await manager.emergency_rollback()
        if success:
            print("Successfully rolled back to previous phase")
        else:
            print("Rollback failed")

    elif args.action == "report":
        report = manager.generate_rollout_report()
        print(report)

        # Save report
        report_file = Path(
            f"deployment/reports/rollout_report_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.md"
        )
        report_file.parent.mkdir(parents=True, exist_ok=True)
        with open(report_file, "w") as f:
            f.write(report)
        print(f"\nReport saved to: {report_file}")

    elif args.action == "update-metrics":
        await manager.update_metrics(
            trade_result=args.trade_result, request_success=args.request_success
        )
        print("Metrics updated")


if __name__ == "__main__":
    asyncio.run(main())
