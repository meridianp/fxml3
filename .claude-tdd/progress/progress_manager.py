#!/usr/bin/env python3
"""
FXML4 Progress Preservation System
Manages and preserves TDD cycle progress for incremental synthesis
"""

import gzip
import hashlib
import json
import os
import pickle
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml


class ProgressState(Enum):
    """TDD progress states"""

    INITIALIZED = "initialized"
    RED_PHASE = "red_phase"
    GREEN_PHASE = "green_phase"
    REFACTOR_PHASE = "refactor_phase"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"


@dataclass
class CodeSnapshot:
    """Snapshot of code at a specific point in time"""

    timestamp: datetime
    file_path: str
    content_hash: str
    content: str
    file_size: int
    encoding: str = "utf-8"


@dataclass
class TestSnapshot:
    """Snapshot of test results at a specific point in time"""

    timestamp: datetime
    component: str
    test_framework: str
    total_tests: int
    passed_tests: int
    failed_tests: int
    skipped_tests: int
    execution_time: float
    test_output: str
    coverage_data: Optional[Dict[str, Any]] = None


@dataclass
class TDDCycleProgress:
    """Progress tracking for a TDD cycle"""

    cycle_id: str
    component: str
    cycle_number: int
    state: ProgressState
    start_time: datetime
    last_update: datetime
    total_duration: float = 0.0

    # Phase tracking
    red_phase_completed: bool = False
    green_phase_completed: bool = False
    refactor_phase_completed: bool = False

    # Snapshots
    code_snapshots: List[CodeSnapshot] = field(default_factory=list)
    test_snapshots: List[TestSnapshot] = field(default_factory=list)

    # Metrics
    lines_of_code_added: int = 0
    lines_of_code_modified: int = 0
    tests_added: int = 0
    tests_modified: int = 0

    # Checkpoints
    checkpoints: List[Dict[str, Any]] = field(default_factory=list)

    # Error tracking
    errors: List[Dict[str, Any]] = field(default_factory=list)

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProjectProgress:
    """Overall project progress tracking"""

    project_name: str
    version: str
    created_at: datetime
    last_updated: datetime

    # Component progress
    component_progress: Dict[str, List[TDDCycleProgress]] = field(default_factory=dict)

    # Overall metrics
    total_cycles: int = 0
    successful_cycles: int = 0
    failed_cycles: int = 0
    total_test_coverage: float = 0.0

    # Quality metrics
    mutation_scores: Dict[str, float] = field(default_factory=dict)
    contract_test_results: Dict[str, bool] = field(default_factory=dict)

    # Configuration snapshots
    config_history: List[Dict[str, Any]] = field(default_factory=list)


class ProgressManager:
    """Manages TDD progress preservation and synthesis"""

    def __init__(self, config_path: str = ".claude-tdd/config.yml"):
        self.config = self._load_config(config_path)
        self.project_root = Path.cwd()
        self.progress_root = self.project_root / ".claude-tdd/progress"
        self.progress_root.mkdir(exist_ok=True)

        # Storage paths
        self.snapshots_dir = self.progress_root / "snapshots"
        self.checkpoints_dir = self.progress_root / "checkpoints"
        self.backups_dir = self.progress_root / "backups"

        for dir_path in [self.snapshots_dir, self.checkpoints_dir, self.backups_dir]:
            dir_path.mkdir(exist_ok=True)

        # Load existing project progress
        self.project_progress = self._load_project_progress()

        # Auto-backup configuration
        self.auto_backup_enabled = self.config["progress"]["auto_backup"]
        self.backup_interval = self.config["progress"]["backup_interval"]

    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load TDD configuration"""
        with open(config_path, "r") as f:
            return yaml.safe_load(f)

    def _load_project_progress(self) -> ProjectProgress:
        """Load existing project progress or create new"""
        progress_file = self.progress_root / "project_progress.json"

        if progress_file.exists():
            try:
                with open(progress_file, "r") as f:
                    data = json.load(f)

                # Convert datetime strings back to datetime objects
                data["created_at"] = datetime.fromisoformat(data["created_at"])
                data["last_updated"] = datetime.fromisoformat(data["last_updated"])

                # Reconstruct component progress
                component_progress = {}
                for component, cycles in data.get("component_progress", {}).items():
                    component_progress[component] = []
                    for cycle_data in cycles:
                        cycle_data["start_time"] = datetime.fromisoformat(
                            cycle_data["start_time"]
                        )
                        cycle_data["last_update"] = datetime.fromisoformat(
                            cycle_data["last_update"]
                        )
                        cycle_data["state"] = ProgressState(cycle_data["state"])

                        # Reconstruct snapshots
                        for snapshot in cycle_data.get("code_snapshots", []):
                            snapshot["timestamp"] = datetime.fromisoformat(
                                snapshot["timestamp"]
                            )

                        for snapshot in cycle_data.get("test_snapshots", []):
                            snapshot["timestamp"] = datetime.fromisoformat(
                                snapshot["timestamp"]
                            )

                        cycle_progress = TDDCycleProgress(**cycle_data)
                        component_progress[component].append(cycle_progress)

                data["component_progress"] = component_progress

                return ProjectProgress(**data)

            except Exception as e:
                print(f"Error loading project progress: {e}")
                print("Creating new project progress...")

        # Create new project progress
        return ProjectProgress(
            project_name=self.config["project"]["name"],
            version=self.config["project"]["version"],
            created_at=datetime.now(),
            last_updated=datetime.now(),
        )

    def start_tdd_cycle(self, component: str) -> TDDCycleProgress:
        """Start a new TDD cycle for a component"""
        cycle_number = self._get_next_cycle_number(component)
        cycle_id = f"{component}_cycle_{cycle_number}_{int(datetime.now().timestamp())}"

        cycle_progress = TDDCycleProgress(
            cycle_id=cycle_id,
            component=component,
            cycle_number=cycle_number,
            state=ProgressState.INITIALIZED,
            start_time=datetime.now(),
            last_update=datetime.now(),
            metadata={
                "framework": self.config["components"][component]["test_framework"],
                "language": self.config["components"][component]["language"],
            },
        )

        # Add to project progress
        if component not in self.project_progress.component_progress:
            self.project_progress.component_progress[component] = []

        self.project_progress.component_progress[component].append(cycle_progress)
        self.project_progress.total_cycles += 1

        # Create initial checkpoint
        self._create_checkpoint(cycle_progress, "cycle_started")

        # Save progress
        self._save_project_progress()

        print(f"Started TDD cycle {cycle_number} for {component} (ID: {cycle_id})")

        return cycle_progress

    def update_cycle_state(
        self,
        cycle_id: str,
        new_state: ProgressState,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Update the state of a TDD cycle"""
        cycle_progress = self._find_cycle_by_id(cycle_id)

        if not cycle_progress:
            print(f"Cycle not found: {cycle_id}")
            return False

        old_state = cycle_progress.state
        cycle_progress.state = new_state
        cycle_progress.last_update = datetime.now()

        # Update phase completion flags
        if new_state == ProgressState.GREEN_PHASE:
            cycle_progress.red_phase_completed = True
        elif new_state == ProgressState.REFACTOR_PHASE:
            cycle_progress.green_phase_completed = True
        elif new_state == ProgressState.COMPLETED:
            cycle_progress.refactor_phase_completed = True
            self.project_progress.successful_cycles += 1
        elif new_state == ProgressState.FAILED:
            self.project_progress.failed_cycles += 1

        # Add metadata if provided
        if metadata:
            cycle_progress.metadata.update(metadata)

        # Create checkpoint for state transition
        self._create_checkpoint(
            cycle_progress,
            f"state_transition_{old_state.value}_to_{new_state.value}",
            metadata,
        )

        # Auto-backup if enabled
        if self.auto_backup_enabled:
            self._create_auto_backup()

        # Save progress
        self._save_project_progress()

        print(f"Updated cycle {cycle_id} state: {old_state.value} → {new_state.value}")

        return True

    def capture_code_snapshot(self, cycle_id: str, file_paths: List[str]) -> bool:
        """Capture a snapshot of code files"""
        cycle_progress = self._find_cycle_by_id(cycle_id)

        if not cycle_progress:
            return False

        timestamp = datetime.now()

        for file_path in file_paths:
            full_path = self.project_root / file_path

            if not full_path.exists():
                continue

            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    content = f.read()

                content_hash = hashlib.sha256(content.encode()).hexdigest()
                file_size = len(content.encode())

                snapshot = CodeSnapshot(
                    timestamp=timestamp,
                    file_path=file_path,
                    content_hash=content_hash,
                    content=content,
                    file_size=file_size,
                )

                cycle_progress.code_snapshots.append(snapshot)

                # Save snapshot to file for large files
                if file_size > 50000:  # 50KB threshold
                    self._save_large_snapshot(cycle_id, snapshot)
                    # Replace content with reference
                    snapshot.content = f"__LARGE_FILE__{content_hash}"

            except Exception as e:
                print(f"Error capturing snapshot of {file_path}: {e}")

        cycle_progress.last_update = datetime.now()
        self._save_project_progress()

        return True

    def capture_test_snapshot(
        self, cycle_id: str, test_results: Dict[str, Any]
    ) -> bool:
        """Capture a snapshot of test results"""
        cycle_progress = self._find_cycle_by_id(cycle_id)

        if not cycle_progress:
            return False

        snapshot = TestSnapshot(
            timestamp=datetime.now(),
            component=cycle_progress.component,
            test_framework=cycle_progress.metadata.get("framework", "unknown"),
            total_tests=test_results.get("total", 0),
            passed_tests=test_results.get("passed", 0),
            failed_tests=test_results.get("failed", 0),
            skipped_tests=test_results.get("skipped", 0),
            execution_time=test_results.get("duration", 0.0),
            test_output=test_results.get("output", ""),
            coverage_data=test_results.get("coverage"),
        )

        cycle_progress.test_snapshots.append(snapshot)
        cycle_progress.last_update = datetime.now()

        self._save_project_progress()

        return True

    def create_checkpoint(
        self,
        cycle_id: str,
        checkpoint_name: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Create a checkpoint for the current cycle state"""
        cycle_progress = self._find_cycle_by_id(cycle_id)

        if not cycle_progress:
            return False

        return self._create_checkpoint(cycle_progress, checkpoint_name, metadata)

    def _create_checkpoint(
        self,
        cycle_progress: TDDCycleProgress,
        checkpoint_name: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Internal method to create a checkpoint"""
        checkpoint = {
            "name": checkpoint_name,
            "timestamp": datetime.now().isoformat(),
            "state": cycle_progress.state.value,
            "cycle_id": cycle_progress.cycle_id,
            "metadata": metadata or {},
        }

        cycle_progress.checkpoints.append(checkpoint)

        # Save checkpoint to file
        checkpoint_file = (
            self.checkpoints_dir / f"{cycle_progress.cycle_id}_{checkpoint_name}.json"
        )
        with open(checkpoint_file, "w") as f:
            json.dump(checkpoint, f, indent=2, default=str)

        return True

    def rollback_to_checkpoint(self, cycle_id: str, checkpoint_name: str) -> bool:
        """Rollback cycle to a specific checkpoint"""
        cycle_progress = self._find_cycle_by_id(cycle_id)

        if not cycle_progress:
            return False

        # Find the checkpoint
        checkpoint = None
        for cp in cycle_progress.checkpoints:
            if cp["name"] == checkpoint_name:
                checkpoint = cp
                break

        if not checkpoint:
            print(f"Checkpoint '{checkpoint_name}' not found for cycle {cycle_id}")
            return False

        # Restore state
        cycle_progress.state = ProgressState(checkpoint["state"])

        # Remove snapshots after checkpoint timestamp
        checkpoint_time = datetime.fromisoformat(checkpoint["timestamp"])
        cycle_progress.code_snapshots = [
            s for s in cycle_progress.code_snapshots if s.timestamp <= checkpoint_time
        ]
        cycle_progress.test_snapshots = [
            s for s in cycle_progress.test_snapshots if s.timestamp <= checkpoint_time
        ]

        # Add rollback record
        rollback_metadata = {
            "rollback_to": checkpoint_name,
            "rollback_time": datetime.now().isoformat(),
            "reason": "manual_rollback",
        }
        self._create_checkpoint(
            cycle_progress, f"rollback_to_{checkpoint_name}", rollback_metadata
        )

        print(f"Rolled back cycle {cycle_id} to checkpoint '{checkpoint_name}'")

        self._save_project_progress()
        return True

    def get_cycle_summary(self, cycle_id: str) -> Optional[Dict[str, Any]]:
        """Get a summary of a TDD cycle"""
        cycle_progress = self._find_cycle_by_id(cycle_id)

        if not cycle_progress:
            return None

        return {
            "cycle_id": cycle_progress.cycle_id,
            "component": cycle_progress.component,
            "cycle_number": cycle_progress.cycle_number,
            "state": cycle_progress.state.value,
            "duration": cycle_progress.total_duration,
            "phases_completed": {
                "red": cycle_progress.red_phase_completed,
                "green": cycle_progress.green_phase_completed,
                "refactor": cycle_progress.refactor_phase_completed,
            },
            "snapshots": {
                "code_snapshots": len(cycle_progress.code_snapshots),
                "test_snapshots": len(cycle_progress.test_snapshots),
            },
            "checkpoints": len(cycle_progress.checkpoints),
            "errors": len(cycle_progress.errors),
            "metrics": {
                "lines_added": cycle_progress.lines_of_code_added,
                "lines_modified": cycle_progress.lines_of_code_modified,
                "tests_added": cycle_progress.tests_added,
                "tests_modified": cycle_progress.tests_modified,
            },
        }

    def get_project_summary(self) -> Dict[str, Any]:
        """Get overall project progress summary"""
        component_summaries = {}

        for component, cycles in self.project_progress.component_progress.items():
            active_cycles = [
                c
                for c in cycles
                if c.state not in [ProgressState.COMPLETED, ProgressState.FAILED]
            ]
            completed_cycles = [c for c in cycles if c.state == ProgressState.COMPLETED]
            failed_cycles = [c for c in cycles if c.state == ProgressState.FAILED]

            component_summaries[component] = {
                "total_cycles": len(cycles),
                "active_cycles": len(active_cycles),
                "completed_cycles": len(completed_cycles),
                "failed_cycles": len(failed_cycles),
                "success_rate": len(completed_cycles) / len(cycles) if cycles else 0,
            }

        return {
            "project": {
                "name": self.project_progress.project_name,
                "version": self.project_progress.version,
                "created_at": self.project_progress.created_at.isoformat(),
                "last_updated": self.project_progress.last_updated.isoformat(),
            },
            "overall_metrics": {
                "total_cycles": self.project_progress.total_cycles,
                "successful_cycles": self.project_progress.successful_cycles,
                "failed_cycles": self.project_progress.failed_cycles,
                "success_rate": self.project_progress.successful_cycles
                / max(1, self.project_progress.total_cycles),
                "total_test_coverage": self.project_progress.total_test_coverage,
            },
            "component_summaries": component_summaries,
            "quality_metrics": {
                "mutation_scores": self.project_progress.mutation_scores,
                "contract_test_results": self.project_progress.contract_test_results,
            },
        }

    def export_progress_report(self, output_format: str = "json") -> str:
        """Export comprehensive progress report"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        if output_format == "json":
            report_file = self.progress_root / f"progress_report_{timestamp}.json"

            report_data = {
                "export_timestamp": datetime.now().isoformat(),
                "project_summary": self.get_project_summary(),
                "detailed_cycles": {},
            }

            # Add detailed cycle information
            for component, cycles in self.project_progress.component_progress.items():
                report_data["detailed_cycles"][component] = []
                for cycle in cycles:
                    cycle_summary = self.get_cycle_summary(cycle.cycle_id)
                    if cycle_summary:
                        report_data["detailed_cycles"][component].append(cycle_summary)

            with open(report_file, "w") as f:
                json.dump(report_data, f, indent=2, default=str)

        elif output_format == "markdown":
            report_file = self.progress_root / f"progress_report_{timestamp}.md"

            with open(report_file, "w") as f:
                self._write_markdown_report(f)

        return str(report_file)

    def _write_markdown_report(self, file_handle):
        """Write progress report in markdown format"""
        project_summary = self.get_project_summary()

        file_handle.write(f"# FXML4 TDD Progress Report\\n\\n")
        file_handle.write(
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\\n\\n"
        )

        # Project overview
        file_handle.write(f"## Project Overview\\n\\n")
        file_handle.write(f"- **Project:** {project_summary['project']['name']}\\n")
        file_handle.write(f"- **Version:** {project_summary['project']['version']}\\n")
        file_handle.write(
            f"- **Created:** {project_summary['project']['created_at']}\\n"
        )
        file_handle.write(
            f"- **Last Updated:** {project_summary['project']['last_updated']}\\n\\n"
        )

        # Overall metrics
        metrics = project_summary["overall_metrics"]
        file_handle.write(f"## Overall Metrics\\n\\n")
        file_handle.write(f"- **Total Cycles:** {metrics['total_cycles']}\\n")
        file_handle.write(f"- **Successful Cycles:** {metrics['successful_cycles']}\\n")
        file_handle.write(f"- **Failed Cycles:** {metrics['failed_cycles']}\\n")
        file_handle.write(f"- **Success Rate:** {metrics['success_rate']:.1%}\\n")
        file_handle.write(
            f"- **Test Coverage:** {metrics['total_test_coverage']:.1%}\\n\\n"
        )

        # Component summaries
        file_handle.write(f"## Component Progress\\n\\n")
        file_handle.write(
            f"| Component | Total | Active | Completed | Failed | Success Rate |\\n"
        )
        file_handle.write(
            f"|-----------|-------|--------|-----------|---------|--------------|\\n"
        )

        for component, summary in project_summary["component_summaries"].items():
            file_handle.write(
                f"| {component} | {summary['total_cycles']} | {summary['active_cycles']} | {summary['completed_cycles']} | {summary['failed_cycles']} | {summary['success_rate']:.1%} |\\n"
            )

        file_handle.write(f"\\n")

    def cleanup_old_data(self, retention_days: int = 30):
        """Clean up old progress data beyond retention period"""
        cutoff_date = datetime.now() - timedelta(days=retention_days)

        # Clean up old snapshots
        for snapshot_file in self.snapshots_dir.glob("*.json"):
            try:
                file_time = datetime.fromtimestamp(snapshot_file.stat().st_mtime)
                if file_time < cutoff_date:
                    snapshot_file.unlink()
            except Exception as e:
                print(f"Error cleaning up {snapshot_file}: {e}")

        # Clean up old checkpoints
        for checkpoint_file in self.checkpoints_dir.glob("*.json"):
            try:
                file_time = datetime.fromtimestamp(checkpoint_file.stat().st_mtime)
                if file_time < cutoff_date:
                    checkpoint_file.unlink()
            except Exception as e:
                print(f"Error cleaning up {checkpoint_file}: {e}")

        # Clean up old backups
        for backup_file in self.backups_dir.glob("*.gz"):
            try:
                file_time = datetime.fromtimestamp(backup_file.stat().st_mtime)
                if file_time < cutoff_date:
                    backup_file.unlink()
            except Exception as e:
                print(f"Error cleaning up {backup_file}: {e}")

    def _find_cycle_by_id(self, cycle_id: str) -> Optional[TDDCycleProgress]:
        """Find a cycle by its ID"""
        for component, cycles in self.project_progress.component_progress.items():
            for cycle in cycles:
                if cycle.cycle_id == cycle_id:
                    return cycle
        return None

    def _get_next_cycle_number(self, component: str) -> int:
        """Get the next cycle number for a component"""
        if component not in self.project_progress.component_progress:
            return 1

        cycles = self.project_progress.component_progress[component]
        if not cycles:
            return 1

        return max(cycle.cycle_number for cycle in cycles) + 1

    def _save_project_progress(self):
        """Save project progress to file"""
        progress_file = self.progress_root / "project_progress.json"

        with open(progress_file, "w") as f:
            json.dump(asdict(self.project_progress), f, indent=2, default=str)

        self.project_progress.last_updated = datetime.now()

    def _save_large_snapshot(self, cycle_id: str, snapshot: CodeSnapshot):
        """Save large file snapshot to separate file"""
        snapshot_file = self.snapshots_dir / f"{cycle_id}_{snapshot.content_hash}.json"

        snapshot_data = {
            "cycle_id": cycle_id,
            "file_path": snapshot.file_path,
            "content_hash": snapshot.content_hash,
            "timestamp": snapshot.timestamp.isoformat(),
            "content": snapshot.content,
        }

        with open(snapshot_file, "w") as f:
            json.dump(snapshot_data, f, indent=2)

    def _create_auto_backup(self):
        """Create automatic backup of progress data"""
        if not self.auto_backup_enabled:
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = self.backups_dir / f"progress_backup_{timestamp}.tar.gz"

        # Create compressed backup of progress directory
        import tarfile

        with tarfile.open(backup_file, "w:gz") as tar:
            tar.add(
                self.progress_root / "project_progress.json",
                arcname="project_progress.json",
            )

            # Add recent checkpoints and snapshots
            recent_time = datetime.now() - timedelta(hours=24)

            for checkpoint_file in self.checkpoints_dir.glob("*.json"):
                file_time = datetime.fromtimestamp(checkpoint_file.stat().st_mtime)
                if file_time > recent_time:
                    tar.add(
                        checkpoint_file, arcname=f"checkpoints/{checkpoint_file.name}"
                    )


def main():
    """Main function for progress management demonstration"""
    manager = ProgressManager()

    print("FXML4 Progress Preservation System")
    print("=================================")

    # Demonstrate creating a cycle
    cycle = manager.start_tdd_cycle("core")

    # Simulate progress updates
    manager.update_cycle_state(cycle.cycle_id, ProgressState.RED_PHASE)
    manager.capture_test_snapshot(
        cycle.cycle_id,
        {
            "total": 5,
            "passed": 0,
            "failed": 5,
            "duration": 2.3,
            "output": "All tests failed as expected (RED phase)",
        },
    )

    manager.update_cycle_state(cycle.cycle_id, ProgressState.GREEN_PHASE)
    manager.capture_test_snapshot(
        cycle.cycle_id,
        {
            "total": 5,
            "passed": 5,
            "failed": 0,
            "duration": 1.8,
            "output": "All tests passing (GREEN phase)",
        },
    )

    manager.update_cycle_state(cycle.cycle_id, ProgressState.COMPLETED)

    # Display summary
    project_summary = manager.get_project_summary()
    print("\\nProject Summary:")
    print(json.dumps(project_summary, indent=2, default=str))

    # Export report
    report_file = manager.export_progress_report("markdown")
    print(f"\\nProgress report exported to: {report_file}")


if __name__ == "__main__":
    main()
