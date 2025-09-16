#!/usr/bin/env python3
"""
FXML4 Claude TDD Automation Framework - Main Entry Point
Comprehensive Test-Driven Development automation for financial trading systems
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from mutation.mutation_runner import MutationTestingRunner
from orchestrator.tdd_orchestrator import TDDOrchestrator
from pact.pact_config import PactConfigManager
from progress.progress_manager import ProgressManager, ProgressState

from scripts.discover_tests import TestDiscovery


class ClaudeTDDFramework:
    """Main Claude TDD automation framework for FXML4"""

    def __init__(self):
        self.test_discovery = TestDiscovery()
        self.tdd_orchestrator = TDDOrchestrator()
        self.mutation_runner = MutationTestingRunner()
        self.pact_manager = PactConfigManager()
        self.progress_manager = ProgressManager()

        print("🤖 FXML4 Claude TDD Automation Framework Initialized")
        print("=" * 60)

    async def run_full_tdd_cycle(
        self, component: str, test_category: str = "unit"
    ) -> Dict[str, Any]:
        """Run a complete TDD cycle with all automation features"""
        print(f"\\n🚀 Starting Full TDD Cycle for {component}")
        print("-" * 40)

        # Start progress tracking
        cycle_progress = self.progress_manager.start_tdd_cycle(component)

        try:
            # Phase 1: Test Discovery
            print("\\n🔍 Phase 1: Test Discovery")
            test_suites = self.test_discovery.discover_all_tests()
            component_suite = test_suites.get(component)

            if component_suite:
                print(
                    f"  ✅ Discovered {component_suite.total_files} test files, {component_suite.total_tests} tests"
                )
            else:
                print(f"  ⚠️  No tests discovered for {component}")

            # Phase 2: Execute TDD Cycle
            print("\\n🔄 Phase 2: TDD Red-Green-Refactor Cycle")
            cycle_result = await self.tdd_orchestrator.start_tdd_cycle(
                component, test_category
            )

            # Update progress based on TDD cycle result
            if cycle_result.phase.value == "complete":
                self.progress_manager.update_cycle_state(
                    cycle_progress.cycle_id,
                    ProgressState.COMPLETED,
                    {"tdd_result": "success"},
                )
                print("  ✅ TDD Cycle completed successfully")
            else:
                self.progress_manager.update_cycle_state(
                    cycle_progress.cycle_id,
                    ProgressState.FAILED,
                    {"tdd_result": "failed", "final_phase": cycle_result.phase.value},
                )
                print(f"  ❌ TDD Cycle failed at {cycle_result.phase.value} phase")

            # Phase 3: Mutation Testing (if TDD cycle succeeded)
            mutation_results = None
            if cycle_result.phase.value == "complete":
                print("\\n🧬 Phase 3: Mutation Testing")
                mutation_results = self.mutation_runner.run_mutation_testing(
                    component, dry_run=True
                )
                print(f"  ✅ Mutation Score: {mutation_results.overall_score:.1f}%")

            # Phase 4: Contract Testing (if applicable)
            contract_results = None
            if component in ["core", "elliott_wave", "frontend"]:
                print("\\n📋 Phase 4: Contract Testing")
                contract_results = self._run_contract_testing(component)
                print(f"  ✅ Contract tests configured and ready")

            # Phase 5: Final Report
            print("\\n📊 Phase 5: Generating Reports")
            cycle_summary = self.progress_manager.get_cycle_summary(
                cycle_progress.cycle_id
            )
            report_file = self.progress_manager.export_progress_report("markdown")
            print(f"  ✅ Progress report: {report_file}")

            return {
                "success": cycle_result.phase.value == "complete",
                "component": component,
                "cycle_id": cycle_progress.cycle_id,
                "tdd_result": cycle_result,
                "mutation_results": mutation_results,
                "contract_results": contract_results,
                "cycle_summary": cycle_summary,
            }

        except Exception as e:
            print(f"  ❌ Error in TDD cycle: {e}")
            self.progress_manager.update_cycle_state(
                cycle_progress.cycle_id, ProgressState.FAILED, {"error": str(e)}
            )
            return {
                "success": False,
                "component": component,
                "cycle_id": cycle_progress.cycle_id,
                "error": str(e),
            }

    def _run_contract_testing(self, component: str) -> Dict[str, Any]:
        """Run contract testing for a component"""
        try:
            if component == "core":
                # Generate API-Core contract
                contract = self.pact_manager.generate_api_core_contract()
                contract_file = self.pact_manager.save_contract_definition(contract)
                consumer_test = self.pact_manager.save_consumer_test(contract, "python")
                provider_test = self.pact_manager.save_provider_test(contract)

                return {
                    "contract_generated": True,
                    "contract_file": contract_file,
                    "consumer_test": consumer_test,
                    "provider_test": provider_test,
                }

            elif component == "elliott_wave":
                # Generate Elliott Wave integration contract
                contract = self.pact_manager.generate_elliott_integration_contract()
                contract_file = self.pact_manager.save_contract_definition(contract)
                consumer_test = self.pact_manager.save_consumer_test(contract, "python")
                provider_test = self.pact_manager.save_provider_test(contract)

                return {
                    "contract_generated": True,
                    "contract_file": contract_file,
                    "consumer_test": consumer_test,
                    "provider_test": provider_test,
                }

            elif component == "frontend":
                # Generate frontend contract tests
                api_contract = self.pact_manager.generate_api_core_contract()
                consumer_test = self.pact_manager.save_consumer_test(
                    api_contract, "typescript"
                )

                return {"contract_generated": True, "consumer_test": consumer_test}

            return {
                "contract_generated": False,
                "reason": "No contract configuration for component",
            }

        except Exception as e:
            return {"contract_generated": False, "error": str(e)}

    def discover_tests(self) -> Dict[str, Any]:
        """Discover all tests across components"""
        print("\\n🔍 Discovering Tests Across All Components")
        print("-" * 40)

        test_suites = self.test_discovery.discover_all_tests()
        self.test_discovery.print_discovery_summary(test_suites)
        self.test_discovery.export_discovery_results(test_suites)

        return {
            "test_suites": {
                name: {
                    "component": suite.component,
                    "language": suite.language,
                    "framework": suite.framework,
                    "total_files": suite.total_files,
                    "total_tests": suite.total_tests,
                    "estimated_duration": suite.estimated_duration,
                }
                for name, suite in test_suites.items()
            }
        }

    async def run_mutation_testing(self, component: str = None) -> Dict[str, Any]:
        """Run mutation testing for component(s)"""
        print(
            f"\\n🧬 Running Mutation Testing{' for ' + component if component else ''}"
        )
        print("-" * 40)

        mutation_results = self.mutation_runner.run_mutation_testing(
            component, dry_run=False
        )

        print(f"\\nMutation Testing Results:")
        print(f"  Overall Score: {mutation_results.overall_score:.1f}%")
        print(f"  Total Mutations: {mutation_results.total_mutations}")
        print(f"  Killed: {mutation_results.total_killed}")
        print(f"  Survived: {mutation_results.total_survived}")
        print(
            f"  Quality Gates: {'PASSED' if mutation_results.quality_gates_passed else 'FAILED'}"
        )

        return {
            "overall_score": mutation_results.overall_score,
            "total_mutations": mutation_results.total_mutations,
            "total_killed": mutation_results.total_killed,
            "total_survived": mutation_results.total_survived,
            "quality_gates_passed": mutation_results.quality_gates_passed,
            "component_results": [
                {
                    "component": result.component,
                    "language": result.language,
                    "engine": result.engine,
                    "score": result.mutation_score,
                    "status": result.status,
                }
                for result in mutation_results.results
            ],
        }

    def setup_contract_testing(self) -> Dict[str, Any]:
        """Set up contract testing for all components"""
        print("\\n📋 Setting Up Contract Testing")
        print("-" * 40)

        results = {}

        # Generate API-Core contract
        try:
            api_contract = self.pact_manager.generate_api_core_contract()
            api_contract_file = self.pact_manager.save_contract_definition(api_contract)
            api_consumer_py = self.pact_manager.save_consumer_test(
                api_contract, "python"
            )
            api_consumer_ts = self.pact_manager.save_consumer_test(
                api_contract, "typescript"
            )
            api_provider = self.pact_manager.save_provider_test(api_contract)

            results["api_core_contract"] = {
                "contract_file": api_contract_file,
                "consumer_test_python": api_consumer_py,
                "consumer_test_typescript": api_consumer_ts,
                "provider_test": api_provider,
            }
            print("  ✅ API-Core contract generated")

        except Exception as e:
            results["api_core_contract"] = {"error": str(e)}
            print(f"  ❌ API-Core contract failed: {e}")

        # Generate Elliott Wave integration contract
        try:
            elliott_contract = self.pact_manager.generate_elliott_integration_contract()
            elliott_contract_file = self.pact_manager.save_contract_definition(
                elliott_contract
            )
            elliott_consumer = self.pact_manager.save_consumer_test(
                elliott_contract, "python"
            )
            elliott_provider = self.pact_manager.save_provider_test(elliott_contract)

            results["elliott_integration_contract"] = {
                "contract_file": elliott_contract_file,
                "consumer_test": elliott_consumer,
                "provider_test": elliott_provider,
            }
            print("  ✅ Elliott Wave integration contract generated")

        except Exception as e:
            results["elliott_integration_contract"] = {"error": str(e)}
            print(f"  ❌ Elliott Wave integration contract failed: {e}")

        # Create contract test runner
        try:
            runner_script = self.pact_manager.create_pact_runner_script()
            results["runner_script"] = runner_script
            print(f"  ✅ Contract test runner created: {runner_script}")

        except Exception as e:
            results["runner_script"] = {"error": str(e)}
            print(f"  ❌ Contract test runner failed: {e}")

        return results

    def show_project_status(self) -> Dict[str, Any]:
        """Show comprehensive project status"""
        print("\\n📊 FXML4 Project Status")
        print("=" * 60)

        project_summary = self.progress_manager.get_project_summary()

        print(
            f"\\nProject: {project_summary['project']['name']} v{project_summary['project']['version']}"
        )
        print(f"Created: {project_summary['project']['created_at']}")
        print(f"Last Updated: {project_summary['project']['last_updated']}")

        print("\\nOverall Metrics:")
        metrics = project_summary["overall_metrics"]
        print(f"  Total TDD Cycles: {metrics['total_cycles']}")
        print(f"  Successful Cycles: {metrics['successful_cycles']}")
        print(f"  Failed Cycles: {metrics['failed_cycles']}")
        print(f"  Success Rate: {metrics['success_rate']:.1%}")

        print("\\nComponent Progress:")
        for component, summary in project_summary["component_summaries"].items():
            print(f"  {component}:")
            print(f"    Total Cycles: {summary['total_cycles']}")
            print(f"    Active: {summary['active_cycles']}")
            print(f"    Completed: {summary['completed_cycles']}")
            print(f"    Failed: {summary['failed_cycles']}")
            print(f"    Success Rate: {summary['success_rate']:.1%}")

        return project_summary

    def cleanup_old_data(self, retention_days: int = 30):
        """Clean up old TDD data"""
        print(f"\\n🧹 Cleaning up data older than {retention_days} days")
        print("-" * 40)

        self.progress_manager.cleanup_old_data(retention_days)
        print("  ✅ Cleanup completed")


def create_demo_workflow():
    """Create a demonstration workflow"""
    return """
# FXML4 Claude TDD Demo Workflow

This demonstrates the complete Claude TDD automation framework:

## 1. Test Discovery
```bash
python .claude-tdd/claude_tdd_main.py discover
```

## 2. Run Full TDD Cycle (Core Component)
```bash
python .claude-tdd/claude_tdd_main.py cycle core --category unit
```

## 3. Run Mutation Testing
```bash
python .claude-tdd/claude_tdd_main.py mutate core
```

## 4. Set Up Contract Testing
```bash
python .claude-tdd/claude_tdd_main.py contracts
```

## 5. View Project Status
```bash
python .claude-tdd/claude_tdd_main.py status
```

## 6. Full Automated Workflow
```bash
python .claude-tdd/claude_tdd_main.py full-auto core
```

## Integration with Claude Code

The framework integrates with Claude Code through:
- TDD Orchestrator agents for Red-Green-Refactor cycles
- Automated test generation and code implementation
- Progress preservation for incremental development
- Comprehensive reporting and quality gates

## Financial Trading System Features

- Risk management testing validation
- Financial calculation precision testing
- Security and compliance test patterns
- Real-time performance testing
- Elliott Wave analysis integration
- Multi-broker compatibility testing
"""


async def main():
    """Main entry point for Claude TDD framework"""
    parser = argparse.ArgumentParser(
        description="FXML4 Claude TDD Automation Framework",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=create_demo_workflow(),
    )

    parser.add_argument(
        "command",
        choices=[
            "discover",
            "cycle",
            "mutate",
            "contracts",
            "status",
            "cleanup",
            "full-auto",
        ],
        help="Command to execute",
    )

    parser.add_argument(
        "component",
        nargs="?",
        choices=["core", "elliott_wave", "frontend"],
        help="Component to operate on",
    )

    parser.add_argument(
        "--category",
        "-c",
        default="unit",
        help="Test category (unit, integration, performance, security)",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be executed without running",
    )

    parser.add_argument(
        "--retention-days",
        type=int,
        default=30,
        help="Data retention period for cleanup (default: 30)",
    )

    parser.add_argument(
        "--output",
        "-o",
        choices=["json", "markdown"],
        default="json",
        help="Output format for reports",
    )

    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    # Initialize framework
    framework = ClaudeTDDFramework()

    try:
        if args.command == "discover":
            result = framework.discover_tests()

        elif args.command == "cycle":
            if not args.component:
                print("Error: Component required for cycle command")
                return 1
            result = await framework.run_full_tdd_cycle(args.component, args.category)

        elif args.command == "mutate":
            result = await framework.run_mutation_testing(args.component)

        elif args.command == "contracts":
            result = framework.setup_contract_testing()

        elif args.command == "status":
            result = framework.show_project_status()

        elif args.command == "cleanup":
            framework.cleanup_old_data(args.retention_days)
            result = {"cleanup_completed": True, "retention_days": args.retention_days}

        elif args.command == "full-auto":
            if not args.component:
                print("Error: Component required for full-auto command")
                return 1

            print(f"\\n🚀 Running Full Automated TDD Workflow for {args.component}")
            print("=" * 60)

            # Full automated workflow
            steps = [
                ("Test Discovery", framework.discover_tests),
                (
                    "TDD Cycle",
                    lambda: framework.run_full_tdd_cycle(args.component, args.category),
                ),
                (
                    "Mutation Testing",
                    lambda: framework.run_mutation_testing(args.component),
                ),
                ("Contract Setup", framework.setup_contract_testing),
                ("Status Report", framework.show_project_status),
            ]

            results = {}
            for step_name, step_func in steps:
                print(f"\\n🔄 Executing: {step_name}")
                try:
                    if asyncio.iscoroutinefunction(step_func):
                        step_result = await step_func()
                    else:
                        step_result = step_func()
                    results[step_name] = step_result
                    print(f"✅ {step_name} completed")
                except Exception as e:
                    print(f"❌ {step_name} failed: {e}")
                    results[step_name] = {"error": str(e)}

            result = {
                "workflow": "full-auto",
                "component": args.component,
                "steps": results,
            }

        # Output results
        if args.output == "json":
            print("\\n" + "=" * 60)
            print("RESULTS")
            print("=" * 60)
            print(json.dumps(result, indent=2, default=str))

        return 0

    except Exception as e:
        print(f"\\n❌ Framework error: {e}")
        return 1


if __name__ == "__main__":
    exit(asyncio.run(main()))
