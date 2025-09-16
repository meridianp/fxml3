#!/usr/bin/env python3
"""
FXML4 TDD Helper Script

Provides utilities for Test-Driven Development workflow including
test template generation, file creation, and TDD validation.
"""

import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


class TDDHelper:
    """Helper class for TDD workflow automation."""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.core_path = project_root / "core"
        self.tests_path = project_root / "core" / "tests"
        self.templates_path = self.tests_path / "templates"

    def create_test_file(self, module_path: str, test_type: str = "unit") -> str:
        """Create a test file for a given module."""
        # Convert module path to test path
        if module_path.startswith("core/"):
            module_path = module_path[5:]  # Remove 'core/' prefix

        module_path = module_path.replace("/", ".").replace(".py", "")

        # Determine test file path
        test_file_name = f"test_{module_path.split('.')[-1]}.py"
        test_dir = self.tests_path / test_type / module_path.replace(".", "/")
        test_dir = test_dir.parent
        test_file_path = test_dir / test_file_name

        # Create directories if they don't exist
        test_dir.mkdir(parents=True, exist_ok=True)

        # Generate test content
        test_content = self._generate_test_template(module_path, test_type)

        # Write test file
        test_file_path.write_text(test_content)

        return str(test_file_path)

    def _generate_test_template(self, module_path: str, test_type: str) -> str:
        """Generate test template based on module type."""
        module_name = module_path.split(".")[-1]
        class_name = "".join(word.capitalize() for word in module_name.split("_"))

        template = f'''"""
TDD Tests for {class_name}

Test-driven development tests for the {module_name} module.
Following Red-Green-Refactor methodology.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any


@pytest.mark.tdd
@pytest.mark.{test_type}
class Test{class_name}:
    """
    TDD test suite for {class_name}.

    Tests follow the Red-Green-Refactor cycle:
    1. RED: Write failing test first
    2. GREEN: Write minimal code to pass
    3. REFACTOR: Improve code quality
    """

    @pytest.fixture
    def {module_name}_instance(self):
        """Create {module_name} instance for testing."""
        # TODO: Import and create actual instance
        # from core.{module_path.replace(".", ".")} import {class_name}
        # return {class_name}()
        return Mock()

    @pytest.fixture
    def sample_data(self):
        """Sample data for testing."""
        return {{
            "test_data": "sample_value",
            "timestamp": datetime.now(),
            "amount": 1000.0
        }}

    # -------------------------------------------------------------------------
    # RED Phase Tests - Write failing tests first
    # -------------------------------------------------------------------------

    @pytest.mark.red
    def test_{module_name}_initialization(self, {module_name}_instance):
        """RED: Test {module_name} initialization."""
        # This test should fail initially
        assert {module_name}_instance is not None
        # TODO: Add specific initialization assertions

    @pytest.mark.red
    def test_{module_name}_core_functionality(self, {module_name}_instance, sample_data):
        """RED: Test core functionality."""
        # This test should fail initially
        result = {module_name}_instance.process(sample_data)

        # TODO: Define expected behavior
        assert result is not None
        # Add more specific assertions based on requirements

    @pytest.mark.red
    def test_{module_name}_error_handling(self, {module_name}_instance):
        """RED: Test error handling."""
        # This test should fail initially
        with pytest.raises(ValueError):
            {module_name}_instance.process(None)

    @pytest.mark.red
    def test_{module_name}_edge_cases(self, {module_name}_instance):
        """RED: Test edge cases."""
        # This test should fail initially
        # TODO: Add edge case tests based on requirements
        pass

    # -------------------------------------------------------------------------
    # GREEN Phase Tests - Minimal implementation tests
    # -------------------------------------------------------------------------

    @pytest.mark.green
    def test_{module_name}_minimal_implementation(self, {module_name}_instance):
        """GREEN: Test minimal working implementation."""
        # This test should pass with minimal code
        # TODO: Test minimal functionality
        pass

    # -------------------------------------------------------------------------
    # REFACTOR Phase Tests - Comprehensive functionality
    # -------------------------------------------------------------------------

    @pytest.mark.refactor
    def test_{module_name}_comprehensive_functionality(self, {module_name}_instance, sample_data):
        """REFACTOR: Test comprehensive functionality after refactoring."""
        # TODO: Add comprehensive tests after refactoring
        pass

    @pytest.mark.refactor
    def test_{module_name}_performance(self, {module_name}_instance, performance_timer):
        """REFACTOR: Test performance requirements."""
        performance_timer.start()

        # TODO: Add performance test
        result = {module_name}_instance.process({{"test": "data"}})

        elapsed = performance_timer.stop()

        # Performance assertion (adjust threshold as needed)
        assert elapsed < 0.1  # 100ms threshold
        assert result is not None

    @pytest.mark.refactor
    def test_{module_name}_integration(self, {module_name}_instance):
        """REFACTOR: Test integration with other components."""
        # TODO: Add integration tests
        pass

    # -------------------------------------------------------------------------
    # Async Tests (if applicable)
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    @pytest.mark.red
    async def test_{module_name}_async_functionality(self, {module_name}_instance):
        """RED: Test async functionality if applicable."""
        # TODO: Add async tests if the module has async methods
        pass

    # -------------------------------------------------------------------------
    # Property-based Tests (optional)
    # -------------------------------------------------------------------------

    # @pytest.mark.property
    # def test_{module_name}_properties(self, {module_name}_instance):
    #     """Property-based tests using hypothesis."""
    #     # TODO: Add property-based tests if needed
    #     pass
'''

        return template

    def check_test_coverage(self, module_path: str) -> Dict[str, Any]:
        """Check if tests exist for a given module."""
        # Convert module path to potential test paths
        module_name = Path(module_path).stem
        test_patterns = [f"test_{module_name}.py", f"{module_name}_test.py"]

        coverage_info = {
            "module_path": module_path,
            "test_files_found": [],
            "test_files_missing": [],
            "coverage_percentage": 0,
        }

        # Search for existing test files
        for pattern in test_patterns:
            test_files = list(self.tests_path.rglob(pattern))
            if test_files:
                coverage_info["test_files_found"].extend([str(f) for f in test_files])
            else:
                coverage_info["test_files_missing"].append(pattern)

        # Calculate basic coverage percentage
        if coverage_info["test_files_found"]:
            coverage_info["coverage_percentage"] = 100
        else:
            coverage_info["coverage_percentage"] = 0

        return coverage_info

    def validate_tdd_markers(self, test_file: str) -> Dict[str, Any]:
        """Validate TDD markers in test file."""
        test_path = Path(test_file)

        if not test_path.exists():
            return {"error": f"Test file not found: {test_file}"}

        content = test_path.read_text()

        validation_result = {
            "file": test_file,
            "has_tdd_marker": "@pytest.mark.tdd" in content,
            "has_red_tests": "@pytest.mark.red" in content,
            "has_green_tests": "@pytest.mark.green" in content,
            "has_refactor_tests": "@pytest.mark.refactor" in content,
            "red_test_count": len(re.findall(r"@pytest\.mark\.red", content)),
            "green_test_count": len(re.findall(r"@pytest\.mark\.green", content)),
            "refactor_test_count": len(re.findall(r"@pytest\.mark\.refactor", content)),
            "total_test_count": len(re.findall(r"def test_", content)),
            "recommendations": [],
        }

        # Add recommendations
        if not validation_result["has_tdd_marker"]:
            validation_result["recommendations"].append(
                "Add @pytest.mark.tdd to test class"
            )

        if validation_result["red_test_count"] == 0:
            validation_result["recommendations"].append(
                "Add RED phase tests (@pytest.mark.red)"
            )

        if validation_result["total_test_count"] > 0:
            red_ratio = (
                validation_result["red_test_count"]
                / validation_result["total_test_count"]
            )
            if red_ratio < 0.3:
                validation_result["recommendations"].append(
                    "Consider adding more RED phase tests"
                )

        return validation_result

    def generate_test_report(self) -> Dict[str, Any]:
        """Generate comprehensive test coverage report."""
        report = {
            "timestamp": datetime.now().isoformat(),
            "project_root": str(self.project_root),
            "total_modules": 0,
            "modules_with_tests": 0,
            "test_files": [],
            "coverage_summary": {},
        }

        # Find all Python modules in core
        python_files = list(self.core_path.rglob("*.py"))
        python_files = [f for f in python_files if not f.name.startswith("test_")]
        python_files = [f for f in python_files if "tests" not in f.parts]

        report["total_modules"] = len(python_files)

        modules_with_tests = 0
        for py_file in python_files:
            relative_path = py_file.relative_to(self.project_root)
            coverage_info = self.check_test_coverage(str(relative_path))

            if coverage_info["test_files_found"]:
                modules_with_tests += 1

            report["test_files"].append(coverage_info)

        report["modules_with_tests"] = modules_with_tests
        report["coverage_summary"] = {
            "overall_percentage": (
                (modules_with_tests / report["total_modules"] * 100)
                if report["total_modules"] > 0
                else 0
            ),
            "modules_with_tests": modules_with_tests,
            "modules_without_tests": report["total_modules"] - modules_with_tests,
        }

        return report

    def create_tdd_workflow_file(self, feature_name: str) -> str:
        """Create a complete TDD workflow file for a new feature."""
        # Create feature test file
        test_file_name = f"test_{feature_name.lower().replace(' ', '_')}.py"
        test_file_path = self.tests_path / "unit" / test_file_name

        # Ensure directory exists
        test_file_path.parent.mkdir(parents=True, exist_ok=True)

        # Generate comprehensive TDD workflow template
        workflow_content = self._generate_tdd_workflow_template(feature_name)

        # Write workflow file
        test_file_path.write_text(workflow_content)

        return str(test_file_path)

    def _generate_tdd_workflow_template(self, feature_name: str) -> str:
        """Generate comprehensive TDD workflow template."""
        class_name = "".join(word.capitalize() for word in feature_name.split())
        module_name = feature_name.lower().replace(" ", "_")

        return f'''"""
TDD Workflow for {feature_name}

Complete Test-Driven Development workflow for {feature_name} feature.
This file demonstrates the full Red-Green-Refactor cycle.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any


@pytest.mark.tdd
@pytest.mark.unit
class Test{class_name}TDDWorkflow:
    """
    Complete TDD workflow for {feature_name}.

    This test class demonstrates the Red-Green-Refactor methodology:

    🔴 RED Phase: Write failing tests that define the desired behavior
    🟢 GREEN Phase: Write minimal code to make tests pass
    🔵 REFACTOR Phase: Improve code quality while keeping tests green
    """

    @pytest.fixture
    def {module_name}_config(self):
        """Configuration for {feature_name}."""
        return {{
            "feature_enabled": True,
            "timeout": 30,
            "retry_attempts": 3
        }}

    @pytest.fixture
    def mock_dependencies(self):
        """Mock external dependencies."""
        return {{
            "database": Mock(),
            "api_client": Mock(),
            "cache": Mock()
        }}

    # =========================================================================
    # 🔴 RED PHASE: Write failing tests first
    # =========================================================================

    @pytest.mark.red
    def test_should_initialize_{module_name}_with_config(self, {module_name}_config):
        """
        RED: {class_name} should initialize with configuration.

        This test will fail initially because the class doesn't exist yet.
        """
        # Arrange - This import will fail initially
        # from core.features.{module_name} import {class_name}

        # Act - This will fail because class doesn't exist
        # {module_name}_instance = {class_name}(config={module_name}_config)

        # Assert - Define what we expect
        # assert {module_name}_instance.config == {module_name}_config
        # assert {module_name}_instance.is_enabled is True

        # Temporary assertion to make test fail for the right reason
        pytest.fail("Feature not implemented yet - this is expected in RED phase")

    @pytest.mark.red
    def test_should_process_valid_input(self, {module_name}_config, mock_dependencies):
        """
        RED: {class_name} should process valid input successfully.

        This test defines the core functionality we want to implement.
        """
        # Arrange
        # from core.features.{module_name} import {class_name}
        # {module_name}_instance = {class_name}(config={module_name}_config)

        valid_input = {{
            "data": "test_data",
            "timestamp": datetime.now()
        }}

        # Act
        # result = {module_name}_instance.process(valid_input)

        # Assert - Define expected behavior
        # assert result is not None
        # assert result["status"] == "success"
        # assert "processed_data" in result

        pytest.fail("Feature not implemented yet - this is expected in RED phase")

    @pytest.mark.red
    def test_should_handle_invalid_input_gracefully(self, {module_name}_config):
        """
        RED: {class_name} should handle invalid input gracefully.

        This test defines error handling behavior.
        """
        # Arrange
        # from core.features.{module_name} import {class_name}
        # {module_name}_instance = {class_name}(config={module_name}_config)

        invalid_input = None

        # Act & Assert
        # with pytest.raises(ValueError, match="Invalid input"):
        #     {module_name}_instance.process(invalid_input)

        pytest.fail("Feature not implemented yet - this is expected in RED phase")

    @pytest.mark.red
    async def test_should_handle_async_operations(self, {module_name}_config):
        """
        RED: {class_name} should handle async operations if needed.
        """
        # Arrange
        # from core.features.{module_name} import {class_name}
        # {module_name}_instance = {class_name}(config={module_name}_config)

        # Act
        # result = await {module_name}_instance.process_async({{"data": "async_test"}})

        # Assert
        # assert result is not None

        pytest.fail("Feature not implemented yet - this is expected in RED phase")

    # =========================================================================
    # 🟢 GREEN PHASE: Minimal implementation to pass tests
    # =========================================================================

    @pytest.mark.green
    def test_minimal_implementation_passes(self):
        """
        GREEN: Verify minimal implementation makes tests pass.

        After implementing minimal code, this test should pass.
        """
        # This test will be enabled once we have minimal implementation
        #
        # Minimal implementation example:
        #
        # class {class_name}:
        #     def __init__(self, config):
        #         self.config = config
        #         self.is_enabled = config.get("feature_enabled", False)
        #
        #     def process(self, input_data):
        #         if input_data is None:
        #             raise ValueError("Invalid input")
        #         return {{"status": "success", "processed_data": input_data}}
        #
        #     async def process_async(self, input_data):
        #         return self.process(input_data)

        pytest.skip("Enable this test once minimal implementation is complete")

    # =========================================================================
    # 🔵 REFACTOR PHASE: Improve code quality
    # =========================================================================

    @pytest.mark.refactor
    def test_refactored_implementation_maintains_functionality(self, {module_name}_config):
        """
        REFACTOR: Verify refactored code maintains all functionality.

        After refactoring, all original tests should still pass.
        """
        # After refactoring, this test ensures we haven't broken anything
        pytest.skip("Enable this test after refactoring phase")

    @pytest.mark.refactor
    def test_performance_meets_requirements(self, {module_name}_config, performance_timer):
        """
        REFACTOR: Verify performance meets requirements.
        """
        # Performance test after refactoring
        # from core.features.{module_name} import {class_name}
        # {module_name}_instance = {class_name}(config={module_name}_config)

        large_input = {{"data": "x" * 10000}}

        performance_timer.start()
        # result = {module_name}_instance.process(large_input)
        elapsed = performance_timer.stop()

        # Performance requirements
        # assert elapsed < 0.1  # 100ms max
        # assert result["status"] == "success"

        pytest.skip("Enable this test after refactoring phase")

    @pytest.mark.refactor
    def test_integration_with_other_components(self, {module_name}_config, mock_dependencies):
        """
        REFACTOR: Test integration with other system components.
        """
        # Integration tests after refactoring
        pytest.skip("Enable this test after refactoring phase")

    @pytest.mark.refactor
    def test_edge_cases_handled_properly(self, {module_name}_config):
        """
        REFACTOR: Verify all edge cases are handled properly.
        """
        # Edge case tests after refactoring
        pytest.skip("Enable this test after refactoring phase")

    # =========================================================================
    # HELPER METHODS FOR TDD WORKFLOW
    # =========================================================================

    def _run_red_phase_tests(self):
        """Helper to run only RED phase tests."""
        # pytest -m "red" --tb=short -v
        pass

    def _run_green_phase_tests(self):
        """Helper to run only GREEN phase tests."""
        # pytest -m "green" --tb=short -v
        pass

    def _run_refactor_phase_tests(self):
        """Helper to run only REFACTOR phase tests."""
        # pytest -m "refactor" --tb=short -v
        pass

    def _verify_tdd_cycle_completion(self):
        """Verify complete TDD cycle has been followed."""
        # This method can be used to verify that all phases have been completed
        # and that the feature is ready for production
        pass


# =============================================================================
# TDD WORKFLOW INSTRUCTIONS
# =============================================================================

"""
TDD Workflow Instructions for {feature_name}:

1. 🔴 RED PHASE:
   - Run: pytest -m "red" test_{module_name}.py -v
   - All tests should FAIL (this is expected and correct!)
   - Verify tests fail for the right reasons (missing implementation)

2. 🟢 GREEN PHASE:
   - Create minimal implementation in core/features/{module_name}.py
   - Write just enough code to make RED tests pass
   - Don't worry about code quality yet - focus on making tests pass
   - Run: pytest -m "red" test_{module_name}.py -v
   - All RED tests should now PASS

3. 🔵 REFACTOR PHASE:
   - Improve code quality, add error handling, optimize performance
   - Enable GREEN and REFACTOR phase tests
   - Run full test suite: pytest test_{module_name}.py -v
   - All tests should PASS after refactoring

4. 🔄 REPEAT:
   - Add new RED tests for additional functionality
   - Implement minimal code to pass (GREEN)
   - Refactor and improve (REFACTOR)

Remember: The goal is to have failing tests BEFORE writing any production code!
"""
'''


def main():
    """Main CLI interface for TDD helper."""
    import argparse

    parser = argparse.ArgumentParser(
        description="FXML4 TDD Helper - Automate TDD workflow tasks",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tdd_helper.py create-test core/trading/order_manager.py
  python tdd_helper.py create-workflow "Order Management"
  python tdd_helper.py check-coverage core/trading/order_manager.py
  python tdd_helper.py validate-tdd tests/unit/test_order_manager.py
  python tdd_helper.py report
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Create test command
    create_parser = subparsers.add_parser(
        "create-test", help="Create test file for module"
    )
    create_parser.add_argument("module_path", help="Path to module file")
    create_parser.add_argument(
        "--type", choices=["unit", "integration", "e2e"], default="unit"
    )

    # Create workflow command
    workflow_parser = subparsers.add_parser(
        "create-workflow", help="Create complete TDD workflow"
    )
    workflow_parser.add_argument("feature_name", help="Name of the feature")

    # Check coverage command
    coverage_parser = subparsers.add_parser(
        "check-coverage", help="Check test coverage for module"
    )
    coverage_parser.add_argument("module_path", help="Path to module file")

    # Validate TDD command
    validate_parser = subparsers.add_parser(
        "validate-tdd", help="Validate TDD markers in test file"
    )
    validate_parser.add_argument("test_file", help="Path to test file")

    # Report command
    subparsers.add_parser("report", help="Generate comprehensive test coverage report")

    args = parser.parse_args()

    # Find project root
    current_dir = Path.cwd()
    project_root = current_dir

    for parent in [current_dir] + list(current_dir.parents):
        if (parent / "pytest.ini").exists() or (parent / "core").is_dir():
            project_root = parent
            break

    helper = TDDHelper(project_root)

    if args.command == "create-test":
        test_file = helper.create_test_file(args.module_path, args.type)
        print(f"✅ Created test file: {test_file}")

    elif args.command == "create-workflow":
        workflow_file = helper.create_tdd_workflow_file(args.feature_name)
        print(f"✅ Created TDD workflow file: {workflow_file}")

    elif args.command == "check-coverage":
        coverage = helper.check_test_coverage(args.module_path)
        print(f"📊 Coverage for {args.module_path}:")
        print(f"  Found tests: {len(coverage['test_files_found'])}")
        print(f"  Coverage: {coverage['coverage_percentage']}%")

    elif args.command == "validate-tdd":
        validation = helper.validate_tdd_markers(args.test_file)
        print(f"🔍 TDD Validation for {args.test_file}:")
        print(f"  RED tests: {validation['red_test_count']}")
        print(f"  GREEN tests: {validation['green_test_count']}")
        print(f"  REFACTOR tests: {validation['refactor_test_count']}")

        if validation["recommendations"]:
            print("  Recommendations:")
            for rec in validation["recommendations"]:
                print(f"    - {rec}")

    elif args.command == "report":
        report = helper.generate_test_report()
        print(f"📋 Test Coverage Report")
        print(f"  Total modules: {report['total_modules']}")
        print(f"  Modules with tests: {report['modules_with_tests']}")
        print(
            f"  Overall coverage: {report['coverage_summary']['overall_percentage']:.1f}%"
        )

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
