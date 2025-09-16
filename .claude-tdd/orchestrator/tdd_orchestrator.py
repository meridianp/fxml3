#!/usr/bin/env python3
"""
FXML4 Claude TDD Orchestrator
Integrates with Claude Code to automate Test-Driven Development cycles
"""

import asyncio
import json
import os
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml


class TDDPhase(Enum):
    """TDD Cycle phases"""

    RED = "red"
    GREEN = "green"
    REFACTOR = "refactor"
    COMPLETE = "complete"


class TDDResult(Enum):
    """TDD operation results"""

    SUCCESS = "success"
    FAILURE = "failure"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass
class TDDCycleState:
    """State of a TDD cycle"""

    component: str
    phase: TDDPhase
    cycle_number: int
    start_time: datetime
    end_time: Optional[datetime] = None
    test_results: Dict[str, Any] = None
    code_changes: List[str] = None
    error_message: Optional[str] = None
    duration: float = 0.0


@dataclass
class ClaudeCodeTask:
    """Task to be sent to Claude Code"""

    agent_type: str
    description: str
    prompt: str
    context: Dict[str, Any]
    timeout: int = 300


class TDDOrchestrator:
    """Orchestrates TDD cycles using Claude Code integration"""

    def __init__(self, config_path: str = ".claude-tdd/config.yml"):
        self.config = self._load_config(config_path)
        self.project_root = Path.cwd()
        self.tdd_root = self.project_root / ".claude-tdd"
        self.progress_dir = self.tdd_root / "progress"
        self.progress_dir.mkdir(exist_ok=True)

        # Initialize state
        self.current_cycles: Dict[str, TDDCycleState] = {}
        self.cycle_history: List[TDDCycleState] = []

    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load TDD configuration"""
        try:
            with open(config_path, "r") as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"TDD config not found: {config_path}")

    async def start_tdd_cycle(
        self, component: str, test_category: str = "unit"
    ) -> TDDCycleState:
        """Start a new TDD cycle for a component"""
        cycle_number = self._get_next_cycle_number(component)

        cycle_state = TDDCycleState(
            component=component,
            phase=TDDPhase.RED,
            cycle_number=cycle_number,
            start_time=datetime.now(),
            test_results={},
            code_changes=[],
        )

        self.current_cycles[component] = cycle_state
        self._save_cycle_state(cycle_state)

        self._log_info(f"Starting TDD cycle #{cycle_number} for {component}")

        # Execute RED phase
        red_result = await self._execute_red_phase(cycle_state, test_category)

        if red_result == TDDResult.SUCCESS:
            # Proceed to GREEN phase
            green_result = await self._execute_green_phase(cycle_state)

            if green_result == TDDResult.SUCCESS:
                # Proceed to REFACTOR phase
                refactor_result = await self._execute_refactor_phase(cycle_state)

                if refactor_result == TDDResult.SUCCESS:
                    cycle_state.phase = TDDPhase.COMPLETE

        # Finalize cycle
        cycle_state.end_time = datetime.now()
        cycle_state.duration = (
            cycle_state.end_time - cycle_state.start_time
        ).total_seconds()

        self._complete_cycle(cycle_state)
        return cycle_state

    async def _execute_red_phase(
        self, cycle_state: TDDCycleState, test_category: str
    ) -> TDDResult:
        """Execute RED phase - write failing tests"""
        self._log_info(f"Executing RED phase for {cycle_state.component}")

        cycle_state.phase = TDDPhase.RED
        self._save_cycle_state(cycle_state)

        try:
            # First, check if we have existing failing tests
            test_result = await self._run_tests(cycle_state.component, test_category)

            if test_result["failed"] > 0:
                self._log_success(
                    f"Found {test_result['failed']} failing tests - RED phase complete"
                )
                cycle_state.test_results["red"] = test_result
                return TDDResult.SUCCESS
            else:
                # No failing tests, need to write new ones
                self._log_info("No failing tests found, generating new test cases")

                # Use Claude Code to generate failing tests
                task = ClaudeCodeTask(
                    agent_type=self.config["claude"]["agents"]["test_generator"],
                    description=f"Generate failing tests for {cycle_state.component}",
                    prompt=self._build_red_phase_prompt(cycle_state, test_category),
                    context=self._gather_red_phase_context(cycle_state),
                    timeout=self.config["tdd"]["cycle"]["red_timeout"],
                )

                claude_result = await self._execute_claude_task(task)

                if claude_result["success"]:
                    # Verify new tests are actually failing
                    test_result = await self._run_tests(
                        cycle_state.component, test_category
                    )

                    if test_result["failed"] > 0:
                        self._log_success(
                            f"Generated {test_result['failed']} failing tests"
                        )
                        cycle_state.test_results["red"] = test_result
                        return TDDResult.SUCCESS
                    else:
                        self._log_error(
                            "Generated tests are not failing - RED phase failed"
                        )
                        return TDDResult.FAILURE
                else:
                    self._log_error(
                        f"Claude Code task failed: {claude_result['error']}"
                    )
                    cycle_state.error_message = claude_result["error"]
                    return TDDResult.ERROR

        except Exception as e:
            self._log_error(f"RED phase error: {str(e)}")
            cycle_state.error_message = str(e)
            return TDDResult.ERROR

    async def _execute_green_phase(self, cycle_state: TDDCycleState) -> TDDResult:
        """Execute GREEN phase - implement code to make tests pass"""
        self._log_info(f"Executing GREEN phase for {cycle_state.component}")

        cycle_state.phase = TDDPhase.GREEN
        self._save_cycle_state(cycle_state)

        try:
            # Use Claude Code to implement code that makes tests pass
            task = ClaudeCodeTask(
                agent_type=self.config["claude"]["agents"]["tdd_orchestrator"],
                description=f"Implement code to make tests pass for {cycle_state.component}",
                prompt=self._build_green_phase_prompt(cycle_state),
                context=self._gather_green_phase_context(cycle_state),
                timeout=self.config["tdd"]["cycle"]["green_timeout"],
            )

            claude_result = await self._execute_claude_task(task)

            if claude_result["success"]:
                # Verify tests now pass
                test_result = await self._run_tests(cycle_state.component)

                if test_result["failed"] == 0:
                    self._log_success(f"All tests passing - GREEN phase complete")
                    cycle_state.test_results["green"] = test_result
                    cycle_state.code_changes.extend(
                        claude_result.get("files_changed", [])
                    )
                    return TDDResult.SUCCESS
                else:
                    self._log_warning(
                        f"Still have {test_result['failed']} failing tests"
                    )
                    # Try one more iteration
                    retry_result = await self._retry_green_phase(cycle_state)
                    return retry_result
            else:
                self._log_error(f"Claude Code task failed: {claude_result['error']}")
                cycle_state.error_message = claude_result["error"]
                return TDDResult.ERROR

        except Exception as e:
            self._log_error(f"GREEN phase error: {str(e)}")
            cycle_state.error_message = str(e)
            return TDDResult.ERROR

    async def _execute_refactor_phase(self, cycle_state: TDDCycleState) -> TDDResult:
        """Execute REFACTOR phase - improve code quality while keeping tests green"""
        self._log_info(f"Executing REFACTOR phase for {cycle_state.component}")

        cycle_state.phase = TDDPhase.REFACTOR
        self._save_cycle_state(cycle_state)

        try:
            # Use Claude Code to refactor code
            task = ClaudeCodeTask(
                agent_type=self.config["claude"]["agents"]["code_reviewer"],
                description=f"Refactor code for {cycle_state.component} while keeping tests green",
                prompt=self._build_refactor_phase_prompt(cycle_state),
                context=self._gather_refactor_phase_context(cycle_state),
                timeout=self.config["tdd"]["cycle"]["refactor_timeout"],
            )

            claude_result = await self._execute_claude_task(task)

            if claude_result["success"]:
                # Verify tests still pass after refactoring
                test_result = await self._run_tests(cycle_state.component)

                if test_result["failed"] == 0:
                    self._log_success(
                        "Tests still passing after refactoring - REFACTOR phase complete"
                    )
                    cycle_state.test_results["refactor"] = test_result
                    cycle_state.code_changes.extend(
                        claude_result.get("files_changed", [])
                    )
                    return TDDResult.SUCCESS
                else:
                    self._log_error(f"Refactoring broke {test_result['failed']} tests")
                    # Rollback changes if possible
                    await self._rollback_changes(cycle_state)
                    return TDDResult.FAILURE
            else:
                self._log_warning("No refactoring suggestions provided")
                return TDDResult.SKIPPED

        except Exception as e:
            self._log_error(f"REFACTOR phase error: {str(e)}")
            cycle_state.error_message = str(e)
            return TDDResult.ERROR

    async def _retry_green_phase(self, cycle_state: TDDCycleState) -> TDDResult:
        """Retry GREEN phase with additional context"""
        self._log_info("Retrying GREEN phase with additional context")

        # Get test failure details
        test_output = await self._get_detailed_test_output(cycle_state.component)

        task = ClaudeCodeTask(
            agent_type=self.config["claude"]["agents"]["tdd_orchestrator"],
            description=f"Fix remaining test failures for {cycle_state.component}",
            prompt=self._build_green_retry_prompt(cycle_state, test_output),
            context=self._gather_green_phase_context(cycle_state),
            timeout=self.config["tdd"]["cycle"]["green_timeout"],
        )

        claude_result = await self._execute_claude_task(task)

        if claude_result["success"]:
            test_result = await self._run_tests(cycle_state.component)

            if test_result["failed"] == 0:
                self._log_success(
                    "All tests passing after retry - GREEN phase complete"
                )
                cycle_state.test_results["green"] = test_result
                cycle_state.code_changes.extend(claude_result.get("files_changed", []))
                return TDDResult.SUCCESS

        return TDDResult.FAILURE

    async def _run_tests(self, component: str, category: str = "") -> Dict[str, Any]:
        """Run tests for a component and return results"""
        tdd_runner = self.project_root / ".claude-tdd/scripts/tdd_runner.sh"

        cmd = [str(tdd_runner), "test", component]
        if category:
            cmd.extend(["--category", category])

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, cwd=self.project_root, timeout=300
            )

            # Parse test results
            return self._parse_test_output(
                result.stdout, result.stderr, result.returncode
            )

        except subprocess.TimeoutExpired:
            return {
                "passed": 0,
                "failed": 0,
                "error": "Test execution timed out",
                "duration": 300,
            }
        except Exception as e:
            return {"passed": 0, "failed": 0, "error": str(e), "duration": 0}

    def _parse_test_output(
        self, stdout: str, stderr: str, returncode: int
    ) -> Dict[str, Any]:
        """Parse test runner output to extract results"""
        result = {
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "error": None,
            "duration": 0,
            "output": stdout,
            "stderr": stderr,
            "returncode": returncode,
        }

        # Parse pytest output
        if "passed" in stdout or "failed" in stdout:
            lines = stdout.split("\n")
            for line in lines:
                if " passed" in line or " failed" in line:
                    # Extract numbers from pytest summary
                    parts = line.split()
                    for i, part in enumerate(parts):
                        if part == "passed" and i > 0:
                            try:
                                result["passed"] = int(parts[i - 1])
                            except ValueError:
                                pass
                        elif part == "failed" and i > 0:
                            try:
                                result["failed"] = int(parts[i - 1])
                            except ValueError:
                                pass
                        elif part == "skipped" and i > 0:
                            try:
                                result["skipped"] = int(parts[i - 1])
                            except ValueError:
                                pass

        if returncode != 0 and result["failed"] == 0:
            result["error"] = stderr or "Test execution failed"

        return result

    async def _get_detailed_test_output(self, component: str) -> str:
        """Get detailed test output for debugging"""
        tdd_runner = self.project_root / ".claude-tdd/scripts/tdd_runner.sh"

        cmd = [str(tdd_runner), "test", component, "--verbose"]

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, cwd=self.project_root, timeout=300
            )

            return f"STDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}"

        except Exception as e:
            return f"Error getting test output: {str(e)}"

    async def _execute_claude_task(self, task: ClaudeCodeTask) -> Dict[str, Any]:
        """Execute a task using Claude Code (simulated for now)"""
        # This would integrate with actual Claude Code API/CLI
        # For now, simulate the execution

        self._log_info(f"Executing Claude Code task: {task.description}")

        # Simulate Claude Code execution
        await asyncio.sleep(1)  # Simulate processing time

        # Return simulated success
        return {
            "success": True,
            "files_changed": [],
            "output": f"Simulated execution of: {task.description}",
            "error": None,
        }

    def _build_red_phase_prompt(
        self, cycle_state: TDDCycleState, test_category: str
    ) -> str:
        """Build prompt for RED phase (test generation)"""
        component_config = self.config["components"][cycle_state.component]

        return f"""
You are helping with Test-Driven Development for the FXML4 trading system.

TASK: Generate failing tests for the {cycle_state.component} component

COMPONENT DETAILS:
- Path: {component_config['path']}
- Language: {component_config['language']}
- Framework: {component_config['framework']}
- Test Framework: {component_config['test_framework']}
- Test Category: {test_category}

REQUIREMENTS:
1. Write tests that define the expected behavior but will initially fail
2. Follow TDD RED phase principles - tests should fail for the right reasons
3. Use appropriate test markers: {self.config['tools']['pytest']['markers']}
4. Focus on {test_category} testing patterns
5. Ensure tests are specific, focused, and well-named

FINANCIAL TRADING CONTEXT:
This is a financial trading system with specific requirements:
- Risk management is critical
- Performance and accuracy are essential
- Security and compliance must be maintained
- Real-time data processing requirements

Please generate failing tests that define the expected behavior.
"""

    def _build_green_phase_prompt(self, cycle_state: TDDCycleState) -> str:
        """Build prompt for GREEN phase (implementation)"""
        return f"""
You are helping with Test-Driven Development for the FXML4 trading system.

TASK: Implement minimal code to make the failing tests pass for {cycle_state.component}

CURRENT STATE:
- Cycle: #{cycle_state.cycle_number}
- Phase: GREEN (implementation)
- Failed tests: {cycle_state.test_results.get('red', {}).get('failed', 0)}

REQUIREMENTS:
1. Write the MINIMAL amount of code to make tests pass
2. Do not over-engineer - implement just enough for tests to pass
3. Follow the component's existing patterns and conventions
4. Maintain code quality and security standards
5. Do not modify the tests - only implement the code

FINANCIAL TRADING CONTEXT:
- Ensure any financial calculations are accurate
- Implement proper error handling for trading operations
- Maintain security for financial data
- Consider performance for real-time requirements

Please implement the minimal code to make the failing tests pass.
"""

    def _build_refactor_phase_prompt(self, cycle_state: TDDCycleState) -> str:
        """Build prompt for REFACTOR phase (code improvement)"""
        return f"""
You are helping with Test-Driven Development for the FXML4 trading system.

TASK: Refactor and improve code quality for {cycle_state.component} while keeping all tests green

CURRENT STATE:
- Cycle: #{cycle_state.cycle_number}
- Phase: REFACTOR (improvement)
- All tests are currently passing

REFACTORING GOALS:
1. Improve code readability and maintainability
2. Remove duplication (DRY principle)
3. Improve performance where appropriate
4. Enhance error handling and logging
5. Add documentation and type hints
6. Follow SOLID principles

CONSTRAINTS:
- Do NOT modify any tests
- Do NOT change public interfaces
- All tests must continue to pass
- Maintain backward compatibility

FINANCIAL TRADING FOCUS:
- Optimize performance for real-time trading
- Enhance security measures
- Improve error handling for financial operations
- Add comprehensive logging for audit trails

Please suggest and implement refactoring improvements.
"""

    def _build_green_retry_prompt(
        self, cycle_state: TDDCycleState, test_output: str
    ) -> str:
        """Build prompt for GREEN phase retry"""
        return f"""
You are helping with Test-Driven Development for the FXML4 trading system.

TASK: Fix the remaining test failures for {cycle_state.component}

PREVIOUS ATTEMPT: The initial GREEN phase implementation did not make all tests pass.

FAILING TEST OUTPUT:
{test_output}

REQUIREMENTS:
1. Analyze the test failures and understand what's missing
2. Implement the necessary code to make ALL tests pass
3. Do not modify the tests - only fix the implementation
4. Maintain existing functionality that was already working

Please analyze the failures and implement the missing functionality.
"""

    def _gather_red_phase_context(self, cycle_state: TDDCycleState) -> Dict[str, Any]:
        """Gather context for RED phase"""
        component_config = self.config["components"][cycle_state.component]

        return {
            "component": cycle_state.component,
            "component_path": component_config["path"],
            "language": component_config["language"],
            "framework": component_config["framework"],
            "test_framework": component_config["test_framework"],
            "cycle_number": cycle_state.cycle_number,
            "project_type": "financial-trading-system",
        }

    def _gather_green_phase_context(self, cycle_state: TDDCycleState) -> Dict[str, Any]:
        """Gather context for GREEN phase"""
        context = self._gather_red_phase_context(cycle_state)
        context.update(
            {
                "red_results": cycle_state.test_results.get("red", {}),
                "failing_tests": cycle_state.test_results.get("red", {}).get(
                    "failed", 0
                ),
            }
        )
        return context

    def _gather_refactor_phase_context(
        self, cycle_state: TDDCycleState
    ) -> Dict[str, Any]:
        """Gather context for REFACTOR phase"""
        context = self._gather_green_phase_context(cycle_state)
        context.update(
            {
                "green_results": cycle_state.test_results.get("green", {}),
                "code_changes": cycle_state.code_changes,
            }
        )
        return context

    async def _rollback_changes(self, cycle_state: TDDCycleState):
        """Rollback changes if refactoring breaks tests"""
        self._log_warning("Rolling back changes due to test failures")
        # Implementation would depend on version control integration
        pass

    def _get_next_cycle_number(self, component: str) -> int:
        """Get next cycle number for component"""
        existing_cycles = [c for c in self.cycle_history if c.component == component]
        if existing_cycles:
            return max(c.cycle_number for c in existing_cycles) + 1
        return 1

    def _save_cycle_state(self, cycle_state: TDDCycleState):
        """Save cycle state to disk"""
        filename = f"{cycle_state.component}_cycle_{cycle_state.cycle_number}.json"
        filepath = self.progress_dir / filename

        with open(filepath, "w") as f:
            json.dump(asdict(cycle_state), f, indent=2, default=str)

    def _complete_cycle(self, cycle_state: TDDCycleState):
        """Complete a TDD cycle"""
        self.cycle_history.append(cycle_state)
        if cycle_state.component in self.current_cycles:
            del self.current_cycles[cycle_state.component]

        self._save_cycle_state(cycle_state)

        if cycle_state.phase == TDDPhase.COMPLETE:
            self._log_success(
                f"TDD cycle #{cycle_state.cycle_number} completed for {cycle_state.component}"
            )
        else:
            self._log_warning(
                f"TDD cycle #{cycle_state.cycle_number} incomplete for {cycle_state.component}"
            )

    def _log_info(self, message: str):
        """Log info message"""
        print(f"[INFO] {datetime.now().strftime('%H:%M:%S')} {message}")

    def _log_success(self, message: str):
        """Log success message"""
        print(f"[SUCCESS] {datetime.now().strftime('%H:%M:%S')} {message}")

    def _log_warning(self, message: str):
        """Log warning message"""
        print(f"[WARNING] {datetime.now().strftime('%H:%M:%S')} {message}")

    def _log_error(self, message: str):
        """Log error message"""
        print(f"[ERROR] {datetime.now().strftime('%H:%M:%S')} {message}")


async def main():
    """Main entry point for TDD orchestrator"""
    orchestrator = TDDOrchestrator()

    # Example usage
    component = "core"
    test_category = "unit"

    try:
        cycle_result = await orchestrator.start_tdd_cycle(component, test_category)
        print(f"\nTDD Cycle Result:")
        print(f"Component: {cycle_result.component}")
        print(f"Phase: {cycle_result.phase.value}")
        print(f"Duration: {cycle_result.duration:.1f}s")
        print(f"Success: {cycle_result.phase == TDDPhase.COMPLETE}")

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
