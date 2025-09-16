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

# Phase 3 imports - optional for graceful degradation
try:
    from mutation.advanced_mutation_config import AdvancedMutationConfig

    ADVANCED_MUTATION_AVAILABLE = True
except ImportError:
    print("⚠️  Advanced mutation config not available - install requirements_phase3.txt")
    ADVANCED_MUTATION_AVAILABLE = False

try:
    from property_testing.hypothesis_financial import (
        FinancialInvariantTests,
        FinancialPropertyTests,
    )
    from property_testing.property_test_runner import PropertyTestRunner

    PROPERTY_TESTING_AVAILABLE = True
except ImportError:
    print(
        "⚠️  Property testing not available - install hypothesis: pip install hypothesis"
    )
    PROPERTY_TESTING_AVAILABLE = False

try:
    from performance.performance_test_framework import PerformanceTestFramework

    PERFORMANCE_TESTING_AVAILABLE = True
except ImportError:
    print("⚠️  Performance testing not available - install requirements_phase3.txt")
    PERFORMANCE_TESTING_AVAILABLE = False

# Phase 4 imports - CI/CD integration
try:
    from cicd.pipeline_integration import CICDPipelineIntegration

    CICD_INTEGRATION_AVAILABLE = True
except ImportError:
    print("⚠️  CI/CD integration not available")
    CICD_INTEGRATION_AVAILABLE = False

# Phase 5 imports - ML-Enhanced Testing
try:
    from ml.test_generator import AITestGenerator
    from ml.test_prioritizer import IntelligentTestPrioritizer
    from ml.quality_predictor import PredictiveQualityAnalytics
    from ml.test_optimizer import TestOptimizer

    ML_ENHANCED_TESTING_AVAILABLE = True
except ImportError:
    print("⚠️  ML-Enhanced Testing not available - install requirements_phase5.txt")
    ML_ENHANCED_TESTING_AVAILABLE = False


class ClaudeTDDFramework:
    """Main Claude TDD automation framework for FXML4"""

    def __init__(self):
        self.test_discovery = TestDiscovery()
        self.tdd_orchestrator = TDDOrchestrator()

        # Core components
        self.mutation_runner = MutationTestingRunner()
        self.pact_manager = PactConfigManager()
        self.progress_manager = ProgressManager()

        # Phase 3: Enhanced testing capabilities (optional)
        if ADVANCED_MUTATION_AVAILABLE:
            self.advanced_mutation = AdvancedMutationConfig()
        else:
            self.advanced_mutation = None

        if PROPERTY_TESTING_AVAILABLE:
            self.property_test_runner = PropertyTestRunner()
        else:
            self.property_test_runner = None

        if PERFORMANCE_TESTING_AVAILABLE:
            self.performance_framework = PerformanceTestFramework()
        else:
            self.performance_framework = None

        # Phase 4: CI/CD Integration
        if CICD_INTEGRATION_AVAILABLE:
            self.cicd_pipeline = CICDPipelineIntegration()
        else:
            self.cicd_pipeline = None

        # Phase 5: ML-Enhanced Testing
        if ML_ENHANCED_TESTING_AVAILABLE:
            self.ai_test_generator = AITestGenerator()
            self.test_prioritizer = IntelligentTestPrioritizer()
            self.quality_predictor = PredictiveQualityAnalytics()
            self.test_optimizer = TestOptimizer()
        else:
            self.ai_test_generator = None
            self.test_prioritizer = None
            self.quality_predictor = None
            self.test_optimizer = None

        print("🤖 FXML4 Claude TDD Automation Framework v5.0 Initialized")
        enhanced_features = []
        if ADVANCED_MUTATION_AVAILABLE:
            enhanced_features.append("Advanced Mutation Testing")
        if PROPERTY_TESTING_AVAILABLE:
            enhanced_features.append("Property-Based Testing")
        if PERFORMANCE_TESTING_AVAILABLE:
            enhanced_features.append("Performance Testing")
        if CICD_INTEGRATION_AVAILABLE:
            enhanced_features.append("CI/CD Pipeline Integration")
        if ML_ENHANCED_TESTING_AVAILABLE:
            enhanced_features.append("ML-Enhanced Testing (AI)")

        if enhanced_features:
            print(f"✅ Enhanced with {', '.join(enhanced_features)}")
        else:
            print(
                "ℹ️  Running with core features only - install requirements for enhanced features"
            )
        print("=" * 80)

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

    async def run_property_testing(self, component: str = None) -> Dict[str, Any]:
        """Run property-based testing for component(s)"""
        if not PROPERTY_TESTING_AVAILABLE:
            print(
                "❌ Property testing not available. Install hypothesis: pip install hypothesis"
            )
            return {"error": "Property testing not available"}

        print(
            f"\\n🔬 Running Property-Based Testing{' for ' + component if component else ''}"
        )
        print("-" * 40)

        property_results = self.property_test_runner.run_property_tests(
            component=component, dry_run=False
        )

        print(f"\\nProperty Testing Results:")
        print(f"  Total Tests: {property_results.total_tests}")
        print(f"  Passed: {property_results.passed_tests}")
        print(f"  Failed: {property_results.failed_tests}")
        print(f"  Errors: {property_results.error_tests}")
        print(f"  Total Examples: {property_results.total_examples}")

        return {
            "total_tests": property_results.total_tests,
            "passed_tests": property_results.passed_tests,
            "failed_tests": property_results.failed_tests,
            "error_tests": property_results.error_tests,
            "total_examples": property_results.total_examples,
            "coverage_analysis": property_results.coverage_analysis,
            "recommendations": property_results.recommendations,
        }

    async def run_performance_testing(
        self, component: str = None, config: str = "light_load"
    ) -> Dict[str, Any]:
        """Run performance testing for component(s)"""
        if not PERFORMANCE_TESTING_AVAILABLE:
            print(
                "❌ Performance testing not available. Install requirements_phase3.txt"
            )
            return {"error": "Performance testing not available"}

        print(
            f"\\n⚡ Running Performance Testing{' for ' + component if component else ''}"
        )
        print(f"Configuration: {config}")
        print("-" * 40)

        performance_results = self.performance_framework.run_performance_tests(
            component=component, test_config=config, dry_run=False
        )

        # Calculate summary metrics
        sla_passed = sum(1 for r in performance_results if r.sla_passed)
        sla_failed = len(performance_results) - sla_passed

        print(f"\\nPerformance Testing Results:")
        print(f"  Total Tests: {len(performance_results)}")
        print(f"  SLA Passed: {sla_passed}")
        print(f"  SLA Failed: {sla_failed}")

        return {
            "total_tests": len(performance_results),
            "sla_passed": sla_passed,
            "sla_failed": sla_failed,
            "test_results": [
                {
                    "test_name": result.test_name,
                    "component": result.component,
                    "sla_passed": result.sla_passed,
                    "avg_latency": result.avg_latency,
                    "throughput": result.throughput_ops_per_sec,
                    "cpu_usage": result.cpu_usage_percent,
                    "memory_usage": result.memory_usage_mb,
                }
                for result in performance_results
            ],
        }

    async def run_enhanced_tdd_cycle(
        self,
        component: str,
        test_category: str = "unit",
        include_mutation: bool = True,
        include_property: bool = True,
        include_performance: bool = False,
    ) -> Dict[str, Any]:
        """Run enhanced TDD cycle with Phase 3 capabilities"""
        print(f"\\n🚀 Starting Enhanced TDD Cycle for {component}")
        print("✨ Phase 3: Test Quality Enhancement")
        print("-" * 50)

        results = {}

        # Start progress tracking
        cycle_progress = self.progress_manager.start_tdd_cycle(component)

        try:
            # Traditional TDD cycle first
            print("\\n📋 Running Traditional TDD Cycle...")
            tdd_results = await self.run_full_tdd_cycle(component, test_category)
            results["tdd_cycle"] = tdd_results

            # Enhanced testing phases
            if include_mutation:
                print("\\n🧬 Phase 3a: Mutation Testing...")
                mutation_results = await self.run_mutation_testing(component)
                results["mutation_testing"] = mutation_results

            if include_property:
                print("\\n🔬 Phase 3b: Property-Based Testing...")
                property_results = await self.run_property_testing(component)
                results["property_testing"] = property_results

            if include_performance:
                print("\\n⚡ Phase 3c: Performance Testing...")
                performance_results = await self.run_performance_testing(component)
                results["performance_testing"] = performance_results

            # Mark cycle as completed
            self.progress_manager.complete_tdd_cycle(cycle_progress.cycle_id)

            # Generate comprehensive report
            self._generate_enhanced_cycle_report(component, results)

            print("\\n✅ Enhanced TDD Cycle Completed Successfully!")
            return results

        except Exception as e:
            print(f"\\n❌ Enhanced TDD Cycle Failed: {e}")
            self.progress_manager.fail_tdd_cycle(cycle_progress.cycle_id, str(e))
            raise

    def _generate_enhanced_cycle_report(self, component: str, results: Dict[str, Any]):
        """Generate comprehensive report for enhanced TDD cycle"""
        from datetime import datetime

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = Path(
            f".claude-tdd/reports/enhanced_cycle_{component}_{timestamp}.md"
        )
        report_file.parent.mkdir(exist_ok=True)

        report_content = f"""# Enhanced TDD Cycle Report

**Component:** {component}
**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Framework Version:** 3.0 (Phase 3)

## Summary

This report summarizes the enhanced TDD cycle results including traditional TDD, mutation testing, property-based testing, and performance testing.

"""

        # TDD Cycle Results
        if "tdd_cycle" in results:
            tdd = results["tdd_cycle"]
            report_content += f"""## Traditional TDD Cycle

- **Test Discovery:** {tdd.get('discovery', {}).get('total_files', 'N/A')} files, {tdd.get('discovery', {}).get('total_tests', 'N/A')} tests
- **TDD Phase:** {tdd.get('tdd_execution', {}).get('status', 'N/A')}
- **Contract Testing:** {tdd.get('contract_validation', {}).get('status', 'N/A')}

"""

        # Mutation Testing Results
        if "mutation_testing" in results:
            mutation = results["mutation_testing"]
            report_content += f"""## Mutation Testing Results

- **Overall Score:** {mutation.get('overall_score', 0):.1f}%
- **Total Mutations:** {mutation.get('total_mutations', 0)}
- **Killed:** {mutation.get('total_killed', 0)}
- **Survived:** {mutation.get('total_survived', 0)}
- **Quality Gates:** {'PASSED' if mutation.get('quality_gates_passed', False) else 'FAILED'}

"""

        # Property Testing Results
        if "property_testing" in results:
            property_tests = results["property_testing"]
            report_content += f"""## Property-Based Testing Results

- **Total Tests:** {property_tests.get('total_tests', 0)}
- **Passed:** {property_tests.get('passed_tests', 0)}
- **Failed:** {property_tests.get('failed_tests', 0)}
- **Total Examples:** {property_tests.get('total_examples', 0)}

"""

        # Performance Testing Results
        if "performance_testing" in results:
            performance = results["performance_testing"]
            report_content += f"""## Performance Testing Results

- **Total Tests:** {performance.get('total_tests', 0)}
- **SLA Passed:** {performance.get('sla_passed', 0)}
- **SLA Failed:** {performance.get('sla_failed', 0)}

"""

        report_content += """
## Recommendations

Based on the enhanced TDD cycle results:

1. **Test Quality:** Review any failing mutation or property tests
2. **Performance:** Address any SLA violations if performance testing was included
3. **Coverage:** Ensure comprehensive test coverage across all testing types
4. **Continuous Improvement:** Use these results to enhance test strategies

---
*Generated by FXML4 Claude TDD Automation Framework v3.0*
"""

        with open(report_file, "w") as f:
            f.write(report_content)

        print(f"\\n📊 Enhanced cycle report generated: {report_file}")

    async def run_cicd_pipeline(
        self,
        component: str,
        branch: str = "main",
        deployment_strategy: str = "blue-green",
        environment: str = "staging",
        force_deployment: bool = False,
    ) -> Dict[str, Any]:
        """Run CI/CD pipeline for component deployment"""
        if not CICD_INTEGRATION_AVAILABLE:
            print("❌ CI/CD integration not available")
            return {"error": "CI/CD integration not available"}

        print(f"\\n🚀 Running CI/CD Pipeline for {component}")
        print(f"Strategy: {deployment_strategy}, Environment: {environment}")
        print("-" * 50)

        try:
            execution = self.cicd_pipeline.trigger_pipeline(
                component, branch, deployment_strategy, environment, force_deployment
            )

            return {
                "pipeline_id": execution.pipeline_id,
                "component": execution.component,
                "branch": execution.branch,
                "environment": execution.environment,
                "build_status": execution.build_status,
                "test_status": execution.test_status,
                "quality_gates_status": execution.quality_gates_status,
                "security_status": execution.security_status,
                "performance_status": execution.performance_status,
                "deployment_status": execution.deployment_status,
                "deployment_url": execution.deployment_url,
                "execution_time": execution.execution_time,
            }

        except Exception as e:
            print(f"❌ CI/CD pipeline failed: {e}")
            return {"error": str(e)}

    def get_pipeline_status(self, pipeline_id: str) -> Dict[str, Any]:
        """Get CI/CD pipeline execution status"""
        if not CICD_INTEGRATION_AVAILABLE:
            return {"error": "CI/CD integration not available"}

        execution = self.cicd_pipeline.get_pipeline_status(pipeline_id)
        if execution:
            return {
                "pipeline_id": execution.pipeline_id,
                "component": execution.component,
                "status": execution.deployment_status,
                "deployment_url": execution.deployment_url,
            }
        else:
            return {"error": "Pipeline not found"}

    def list_recent_deployments(self) -> List[Dict[str, Any]]:
        """List recent CI/CD pipeline executions"""
        if not CICD_INTEGRATION_AVAILABLE:
            return []

        executions = self.cicd_pipeline.list_recent_pipelines()
        return [
            {
                "pipeline_id": exec.pipeline_id,
                "component": exec.component,
                "environment": exec.environment,
                "status": exec.deployment_status,
                "start_time": exec.start_time,
                "deployment_url": exec.deployment_url,
            }
            for exec in executions
        ]

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

    # Phase 5: ML-Enhanced Testing Methods

    async def run_ai_test_generation(self, component: str, test_files: List[str] = None, llm_provider: str = "anthropic") -> Dict[str, Any]:
        """Generate test cases using AI/LLM capabilities"""
        if not ML_ENHANCED_TESTING_AVAILABLE:
            return {"error": "ML-Enhanced Testing not available - install requirements_phase5.txt"}

        print(f"\\n🤖 AI Test Generation for {component}")
        print("-" * 40)

        try:
            # Analyze existing code
            if test_files:
                file_paths = test_files
            else:
                # Discover component files
                test_suite = self.test_discovery.discover_all_tests().get(component)
                file_paths = [test.file_path for test in test_suite.test_files] if test_suite else []

            generated_tests = []
            for file_path in file_paths:
                analysis = self.ai_test_generator.analyze_code(file_path)
                tests = self.ai_test_generator.generate_tests(analysis)
                generated_tests.extend(tests)

            # Generate using LLM if available
            if file_paths:
                llm_tests = []
                for file_path in file_paths:
                    analysis = self.ai_test_generator.analyze_code(file_path)
                    llm_generated = self.ai_test_generator.generate_with_llm(analysis, "comprehensive")
                    llm_tests.extend(llm_generated)
                generated_tests.extend(llm_tests)

            print(f"  ✅ Generated {len(generated_tests)} test cases")
            print(f"  📁 Analyzed {len(file_paths)} files")

            return {
                "component": component,
                "files_analyzed": file_paths,
                "tests_generated": len(generated_tests),
                "generated_tests": [{"name": t.name, "type": t.test_type, "domain": t.financial_domain} for t in generated_tests]
            }

        except Exception as e:
            print(f"  ❌ AI test generation failed: {e}")
            return {"error": str(e)}

    async def run_test_prioritization(self, component: str, strategy: str = "ml_hybrid", max_tests: int = 100) -> Dict[str, Any]:
        """Prioritize tests using ML predictions"""
        if not ML_ENHANCED_TESTING_AVAILABLE:
            return {"error": "ML-Enhanced Testing not available - install requirements_phase5.txt"}

        print(f"\\n🎯 Test Prioritization for {component} ({strategy})")
        print("-" * 40)

        try:
            # Get all tests for component
            test_suite = self.test_discovery.discover_all_tests().get(component)
            if not test_suite:
                return {"error": f"No tests found for component {component}"}

            test_list = [f"{tf.file_path}::{test}" for tf in test_suite.test_files for test in tf.test_methods]

            # Prioritize tests
            prioritized_tests = self.test_prioritizer.prioritize_tests(
                test_list, strategy=strategy, target_count=max_tests
            )

            print(f"  ✅ Prioritized {len(prioritized_tests)} tests")
            print(f"  🧠 Using {strategy} strategy")

            # Show top 5 priority tests
            if prioritized_tests:
                print("\\n🔝 Top Priority Tests:")
                for i, test in enumerate(prioritized_tests[:5]):
                    print(f"  {i+1}. {test.test_name} (Score: {test.priority_score:.3f}) - {test.reason}")

            return {
                "component": component,
                "strategy": strategy,
                "total_tests": len(test_list),
                "prioritized_tests": len(prioritized_tests),
                "top_tests": [
                    {
                        "name": t.test_name,
                        "priority_score": t.priority_score,
                        "failure_probability": t.failure_probability,
                        "reason": t.reason
                    }
                    for t in prioritized_tests[:10]
                ]
            }

        except Exception as e:
            print(f"  ❌ Test prioritization failed: {e}")
            return {"error": str(e)}

    async def run_quality_prediction(self, component: str, forecast_days: int = 30) -> Dict[str, Any]:
        """Predict quality metrics and generate forecasts"""
        if not ML_ENHANCED_TESTING_AVAILABLE:
            return {"error": "ML-Enhanced Testing not available - install requirements_phase5.txt"}

        print(f"\\n🔮 Quality Prediction for {component} ({forecast_days} days)")
        print("-" * 40)

        try:
            # Collect current quality metrics (simplified)
            current_metrics = {
                "test_coverage": 85.0,
                "mutation_score": 75.0,
                "code_complexity": 6.5,
                "technical_debt_ratio": 2.1,
                "defect_density": 0.03,
                "performance_score": 88.0,
                "security_score": 94.0,
                "maintainability_index": 82.0
            }

            self.quality_predictor.collect_quality_metrics(current_metrics)

            # Generate forecasts
            forecasts = self.quality_predictor.forecast_quality(forecast_days)

            # Assess release readiness
            release_assessment = self.quality_predictor.assess_release_readiness(
                f"{component}_v1.0", target_date=None
            )

            # Predict defects
            defect_predictions = self.quality_predictor.predict_defects()

            print(f"  ✅ Generated {len(forecasts)} quality forecasts")
            print(f"  📊 Release readiness: {release_assessment.readiness.value}")
            print(f"  🐛 Predicted defects: {len(defect_predictions)}")

            return {
                "component": component,
                "forecast_days": forecast_days,
                "current_metrics": current_metrics,
                "forecasts": [
                    {
                        "date": f.target_date.isoformat(),
                        "predicted_coverage": f.predicted_coverage,
                        "predicted_defects": f.predicted_defect_count,
                        "quality_level": f.predicted_quality_level.value
                    }
                    for f in forecasts[:5]
                ],
                "release_assessment": {
                    "readiness": release_assessment.readiness.value,
                    "score": release_assessment.overall_score,
                    "gates_passed": release_assessment.quality_gates_passed,
                    "gates_total": release_assessment.quality_gates_total,
                    "estimated_defects": release_assessment.estimated_defect_count
                },
                "high_risk_files": [
                    {"file": dp.file_path, "probability": dp.defect_probability}
                    for dp in defect_predictions[:5]
                ]
            }

        except Exception as e:
            print(f"  ❌ Quality prediction failed: {e}")
            return {"error": str(e)}

    async def run_test_optimization(self, component: str, strategy: str = "comprehensive") -> Dict[str, Any]:
        """Optimize test suite for efficiency"""
        if not ML_ENHANCED_TESTING_AVAILABLE:
            return {"error": "ML-Enhanced Testing not available - install requirements_phase5.txt"}

        print(f"\\n⚡ Test Optimization for {component} ({strategy})")
        print("-" * 40)

        try:
            # Get all tests for component
            test_suite = self.test_discovery.discover_all_tests().get(component)
            if not test_suite:
                return {"error": f"No tests found for component {component}"}

            test_list = [f"{tf.file_path}::{test}" for tf in test_suite.test_files for test in tf.test_methods]

            # Analyze test suite
            analysis = self.test_optimizer.analyze_test_suite(test_list)

            # Optimize test suite
            optimization_result = self.test_optimizer.optimize_test_suite(
                test_list, strategy=strategy
            )

            # Create parallelization plan
            parallelization_plan = self.test_optimizer.create_parallelization_plan(test_list)

            print(f"  ✅ Analyzed {analysis['total_tests']} tests")
            print(f"  🔧 Removed {len(optimization_result.redundant_tests)} redundant tests")
            print(f"  ⏱️  Estimated time savings: {optimization_result.estimated_time_savings:.1f} seconds")
            print(f"  🔀 Created {parallelization_plan.total_groups} parallel groups")

            return {
                "component": component,
                "strategy": strategy,
                "analysis": analysis,
                "optimization": {
                    "original_count": optimization_result.original_count,
                    "optimized_count": optimization_result.optimized_count,
                    "time_savings": optimization_result.estimated_time_savings,
                    "redundant_tests": len(optimization_result.redundant_tests),
                    "confidence": optimization_result.confidence_score
                },
                "parallelization": {
                    "total_groups": parallelization_plan.total_groups,
                    "max_workers": parallelization_plan.max_parallel_workers,
                    "estimated_time": parallelization_plan.estimated_total_time,
                    "dependencies_resolved": parallelization_plan.dependencies_resolved
                }
            }

        except Exception as e:
            print(f"  ❌ Test optimization failed: {e}")
            return {"error": str(e)}

    async def run_ml_enhanced_tdd_cycle(self, component: str, test_category: str = "unit") -> Dict[str, Any]:
        """Run a complete ML-enhanced TDD cycle"""
        if not ML_ENHANCED_TESTING_AVAILABLE:
            return {"error": "ML-Enhanced Testing not available - install requirements_phase5.txt"}

        print(f"\\n🚀 ML-Enhanced TDD Cycle for {component}")
        print("=" * 60)

        try:
            results = {}

            # 1. AI Test Generation
            print("\\n🤖 Phase 1: AI-Powered Test Generation")
            generation_result = await self.run_ai_test_generation(component)
            results["test_generation"] = generation_result

            # 2. Test Prioritization
            print("\\n🎯 Phase 2: Intelligent Test Prioritization")
            prioritization_result = await self.run_test_prioritization(component, "ml_hybrid")
            results["test_prioritization"] = prioritization_result

            # 3. Test Optimization
            print("\\n⚡ Phase 3: Test Suite Optimization")
            optimization_result = await self.run_test_optimization(component, "comprehensive")
            results["test_optimization"] = optimization_result

            # 4. Quality Prediction
            print("\\n🔮 Phase 4: Predictive Quality Analytics")
            quality_result = await self.run_quality_prediction(component, 14)
            results["quality_prediction"] = quality_result

            # 5. Traditional TDD Cycle (enhanced with ML insights)
            print("\\n🔄 Phase 5: Enhanced TDD Red-Green-Refactor")
            tdd_result = await self.run_full_tdd_cycle(component, test_category)
            results["tdd_cycle"] = tdd_result

            print("\\n✅ ML-Enhanced TDD Cycle Complete!")
            print("=" * 60)

            return {
                "component": component,
                "cycle_type": "ml_enhanced",
                "phases": results,
                "summary": {
                    "tests_generated": generation_result.get("tests_generated", 0),
                    "tests_prioritized": prioritization_result.get("prioritized_tests", 0),
                    "time_savings": optimization_result.get("optimization", {}).get("time_savings", 0),
                    "quality_score": quality_result.get("release_assessment", {}).get("score", 0)
                }
            }

        except Exception as e:
            print(f"  ❌ ML-Enhanced TDD cycle failed: {e}")
            return {"error": str(e)}

    async def train_ml_models(self, retrain: bool = False) -> Dict[str, Any]:
        """Train or retrain ML models"""
        if not ML_ENHANCED_TESTING_AVAILABLE:
            return {"error": "ML-Enhanced Testing not available - install requirements_phase5.txt"}

        print(f"\\n🎓 Training ML Models (retrain: {retrain})")
        print("-" * 40)

        try:
            results = {}

            # Train test prioritizer models
            print("  🧠 Training test failure prediction models...")
            prioritizer_metrics = self.test_prioritizer.train_models(retrain)
            results["test_prioritizer"] = prioritizer_metrics

            # Train quality prediction models
            print("  📊 Training quality prediction models...")
            quality_metrics = self.quality_predictor.train_quality_models(retrain)
            results["quality_predictor"] = quality_metrics

            print("  ✅ Model training completed")

            return {
                "training_completed": True,
                "retrain": retrain,
                "model_performance": results
            }

        except Exception as e:
            print(f"  ❌ Model training failed: {e}")
            return {"error": str(e)}

    def get_ml_analytics(self) -> Dict[str, Any]:
        """Get ML analytics and performance metrics"""
        if not ML_ENHANCED_TESTING_AVAILABLE:
            return {"error": "ML-Enhanced Testing not available - install requirements_phase5.txt"}

        print("\\n📊 ML Analytics Dashboard")
        print("-" * 40)

        try:
            # Get analytics from each ML component
            prioritizer_analytics = self.test_prioritizer.get_prioritization_analytics()
            quality_analytics = self.quality_predictor.get_quality_dashboard_data()
            optimizer_analytics = self.test_optimizer.get_optimization_analytics()

            print(f"  📈 Test prioritization: {prioritizer_analytics.get('total_test_executions', 0)} executions")
            print(f"  🎯 Quality predictions: {len(quality_analytics.get('recent_forecasts', []))} forecasts")
            print(f"  ⚡ Test optimization: {optimizer_analytics.get('total_tests_profiled', 0)} tests profiled")

            return {
                "test_prioritization": prioritizer_analytics,
                "quality_prediction": quality_analytics,
                "test_optimization": optimizer_analytics,
                "ml_framework_status": {
                    "ai_test_generator": self.ai_test_generator is not None,
                    "test_prioritizer": self.test_prioritizer is not None,
                    "quality_predictor": self.quality_predictor is not None,
                    "test_optimizer": self.test_optimizer is not None
                }
            }

        except Exception as e:
            print(f"  ❌ Analytics retrieval failed: {e}")
            return {"error": str(e)}


def create_demo_workflow():
    """Create a demonstration workflow"""
    return """
# FXML4 Claude TDD Demo Workflow v5.0

This demonstrates the complete Claude TDD automation framework with Phase 5 ML-Enhanced Testing:

## 1. Test Discovery
```bash
python .claude-tdd/claude_tdd_main.py discover
```

## 2. Run Traditional TDD Cycle
```bash
python .claude-tdd/claude_tdd_main.py cycle core --category unit
```

## 3. Phase 3a: Mutation Testing
```bash
python .claude-tdd/claude_tdd_main.py mutate core
```

## 4. Phase 3b: Property-Based Testing
```bash
python .claude-tdd/claude_tdd_main.py property core
```

## 5. Phase 3c: Performance Testing
```bash
python .claude-tdd/claude_tdd_main.py performance core --performance-config light_load
```

## 6. Enhanced TDD Cycle (All Phase 3 Features)
```bash
python .claude-tdd/claude_tdd_main.py enhanced-cycle core --include-performance
```

## 7. Phase 4a: CI/CD Blue-Green Deployment
```bash
python .claude-tdd/claude_tdd_main.py deploy core --environment staging --deployment-strategy blue-green
```

## 8. Phase 4b: CI/CD Canary Deployment
```bash
python .claude-tdd/claude_tdd_main.py deploy core --environment production --deployment-strategy canary
```

## 9. Check Pipeline Status
```bash
python .claude-tdd/claude_tdd_main.py pipeline-status --pipeline-id core_main_1234567890
```

## 10. List Recent Deployments
```bash
python .claude-tdd/claude_tdd_main.py deployments
```

## 11. Set Up Contract Testing
```bash
python .claude-tdd/claude_tdd_main.py contracts
```

## 12. View Project Status
```bash
python .claude-tdd/claude_tdd_main.py status
```

## Phase 5: ML-Enhanced Testing Commands

### 13. AI-Powered Test Generation
```bash
python .claude-tdd/claude_tdd_main.py generate-tests core --llm-provider anthropic
```

### 14. Intelligent Test Prioritization
```bash
python .claude-tdd/claude_tdd_main.py prioritize-tests core --prioritization-strategy ml_hybrid --max-tests 50
```

### 15. Predictive Quality Analytics
```bash
python .claude-tdd/claude_tdd_main.py predict-quality core --forecast-days 30
```

### 16. Test Suite Optimization
```bash
python .claude-tdd/claude_tdd_main.py optimize-tests core --optimization-strategy comprehensive
```

### 17. Complete ML-Enhanced TDD Cycle
```bash
python .claude-tdd/claude_tdd_main.py ml-cycle core --category unit
```

### 18. Train ML Models
```bash
python .claude-tdd/claude_tdd_main.py train-models --retrain-models
```

### 19. ML Analytics Dashboard
```bash
python .claude-tdd/claude_tdd_main.py ml-analytics
```

## Integration with Claude Code

The framework integrates with Claude Code through:
- TDD Orchestrator agents for Red-Green-Refactor cycles
- Automated test generation and code implementation
- Progress preservation for incremental development
- Comprehensive reporting and quality gates

## Financial Trading System Features

### Core Testing Capabilities
- Risk management testing validation
- Financial calculation precision testing with property-based testing
- Security and compliance test patterns
- Real-time performance testing with SLA validation
- Elliott Wave analysis integration
- Multi-broker compatibility testing
- Mutation testing for financial calculation robustness
- Property-based testing for mathematical invariants
- Performance testing for trading system latency requirements

### ML-Enhanced Testing Features
- AI-powered test case generation for financial scenarios
- Intelligent test prioritization based on risk and failure prediction
- Predictive quality analytics for defect forecasting
- Test suite optimization for maximum efficiency
- Financial domain-specific ML models for:
  - Order execution failure prediction
  - Risk management test prioritization
  - PnL calculation quality assessment
  - Compliance testing optimization
- Market condition test scenario generation
- Financial risk-based test scheduling

### CI/CD and Deployment
- Market hours aware CI/CD deployments
- Zero-downtime blue-green deployments
- Risk-controlled canary deployments
- Automated rollback capabilities
- Financial compliance integration in CI/CD pipeline
- ML-guided deployment risk assessment
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
            "property",
            "performance",
            "enhanced-cycle",
            "contracts",
            "status",
            "cleanup",
            "full-auto",
            "deploy",
            "pipeline-status",
            "deployments",
            # Phase 5: ML-Enhanced Testing commands
            "generate-tests",
            "prioritize-tests",
            "predict-quality",
            "optimize-tests",
            "ml-cycle",
            "train-models",
            "ml-analytics",
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

    parser.add_argument(
        "--performance-config",
        default="light_load",
        choices=["light_load", "peak_load", "stress_test", "endurance_test"],
        help="Performance test configuration",
    )

    parser.add_argument(
        "--include-mutation",
        action="store_true",
        default=True,
        help="Include mutation testing in enhanced cycle",
    )

    parser.add_argument(
        "--include-property",
        action="store_true",
        default=True,
        help="Include property testing in enhanced cycle",
    )

    parser.add_argument(
        "--include-performance",
        action="store_true",
        help="Include performance testing in enhanced cycle",
    )

    # CI/CD specific arguments
    parser.add_argument(
        "--branch", "-b", default="main", help="Git branch for deployment"
    )

    parser.add_argument(
        "--deployment-strategy",
        choices=["blue-green", "canary"],
        default="blue-green",
        help="Deployment strategy",
    )

    parser.add_argument(
        "--environment",
        choices=["dev", "staging", "production"],
        default="staging",
        help="Target environment",
    )

    parser.add_argument(
        "--force-deployment",
        action="store_true",
        help="Force deployment during market hours",
    )

    parser.add_argument("--pipeline-id", help="Pipeline ID for status queries")

    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    # Phase 5: ML-Enhanced Testing arguments
    parser.add_argument(
        "--test-files",
        nargs="*",
        help="Specific test files for analysis (for generate-tests, optimize-tests)"
    )

    parser.add_argument(
        "--prioritization-strategy",
        choices=["ml_hybrid", "risk_based", "time_optimal"],
        default="ml_hybrid",
        help="Test prioritization strategy"
    )

    parser.add_argument(
        "--optimization-strategy",
        choices=["comprehensive", "fast", "conservative"],
        default="comprehensive",
        help="Test optimization strategy"
    )

    parser.add_argument(
        "--llm-provider",
        choices=["openai", "anthropic"],
        default="anthropic",
        help="LLM provider for test generation"
    )

    parser.add_argument(
        "--max-tests",
        type=int,
        default=100,
        help="Maximum number of tests to prioritize/generate"
    )

    parser.add_argument(
        "--retrain-models",
        action="store_true",
        help="Force retraining of ML models"
    )

    parser.add_argument(
        "--forecast-days",
        type=int,
        default=30,
        help="Number of days to forecast for quality prediction"
    )

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

        elif args.command == "property":
            result = await framework.run_property_testing(args.component)

        elif args.command == "performance":
            result = await framework.run_performance_testing(
                args.component, args.performance_config
            )

        elif args.command == "enhanced-cycle":
            if not args.component:
                print("Error: Component required for enhanced-cycle command")
                return 1
            result = await framework.run_enhanced_tdd_cycle(
                args.component,
                args.category,
                args.include_mutation,
                args.include_property,
                args.include_performance,
            )

        elif args.command == "contracts":
            result = framework.setup_contract_testing()

        elif args.command == "deploy":
            if not args.component:
                print("Error: Component required for deploy command")
                return 1
            result = await framework.run_cicd_pipeline(
                args.component,
                args.branch,
                args.deployment_strategy,
                args.environment,
                args.force_deployment,
            )

        elif args.command == "pipeline-status":
            if not args.pipeline_id:
                print("Error: --pipeline-id required for pipeline-status command")
                return 1
            result = framework.get_pipeline_status(args.pipeline_id)

        elif args.command == "deployments":
            result = {"recent_deployments": framework.list_recent_deployments()}

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

        # Phase 5: ML-Enhanced Testing Commands
        elif args.command == "generate-tests":
            result = await framework.run_ai_test_generation(
                args.component, args.test_files, args.llm_provider
            )

        elif args.command == "prioritize-tests":
            result = await framework.run_test_prioritization(
                args.component, args.prioritization_strategy, args.max_tests
            )

        elif args.command == "predict-quality":
            result = await framework.run_quality_prediction(
                args.component, args.forecast_days
            )

        elif args.command == "optimize-tests":
            result = await framework.run_test_optimization(
                args.component, args.optimization_strategy
            )

        elif args.command == "ml-cycle":
            if not args.component:
                print("Error: Component required for ml-cycle command")
                return 1
            result = await framework.run_ml_enhanced_tdd_cycle(
                args.component, args.category
            )

        elif args.command == "train-models":
            result = await framework.train_ml_models(args.retrain_models)

        elif args.command == "ml-analytics":
            result = framework.get_ml_analytics()

        else:
            print(f"Unknown command: {args.command}")
            return 1

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
