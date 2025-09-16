#!/usr/bin/env python3
"""
FXML4 Mutation Testing Runner

This script runs comprehensive mutation testing to validate test suite quality
by introducing controlled mutations and verifying that tests detect them.

Usage:
    python scripts/run_mutation_tests.py --source fxml4/core --tests tests/unit
    python scripts/run_mutation_tests.py --file fxml4/risk/calculator.py
    python scripts/run_mutation_tests.py --quick --output mutation_report.json
"""

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from typing import List, Optional

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import mutation testing framework
try:
    from tests.mutation.test_mutation_framework import MutationScore, MutationTester

    MUTATION_TESTING_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Mutation testing framework not available: {e}")
    MUTATION_TESTING_AVAILABLE = False


class MutationTestRunner:
    """High-level mutation test runner with reporting and configuration."""

    def __init__(self, source_dirs: List[str], test_command: str = "pytest"):
        self.source_dirs = source_dirs
        self.test_command = test_command
        self.tester: Optional[MutationTester] = None

    async def run_quick_mutation_test(self) -> dict:
        """Run a quick mutation test on a subset of files."""
        print("Running Quick Mutation Test")
        print("=" * 40)

        if not MUTATION_TESTING_AVAILABLE:
            return {"error": "Mutation testing framework not available"}

        # Create test files for quick validation
        test_results = await self._create_and_test_sample_files()

        return test_results

    async def run_comprehensive_mutation_test(
        self,
        target_files: Optional[List[str]] = None,
        exclude_patterns: Optional[List[str]] = None,
    ) -> dict:
        """Run comprehensive mutation testing on specified files."""
        print("Running Comprehensive Mutation Test")
        print("=" * 45)

        if not MUTATION_TESTING_AVAILABLE:
            return {"error": "Mutation testing framework not available"}

        self.tester = MutationTester(self.source_dirs, self.test_command)

        try:
            # Filter files if needed
            filtered_files = self._filter_target_files(target_files, exclude_patterns)

            # Run mutation testing
            score = self.tester.run_mutation_testing(filtered_files)

            # Generate comprehensive report
            report = self.tester.generate_report()

            return {
                "score": {
                    "total_mutants": score.total_mutants,
                    "killed_mutants": score.killed_mutants,
                    "survived_mutants": score.survived_mutants,
                    "mutation_score": score.mutation_score,
                    "detection_rate": score.detection_rate,
                    "execution_time_seconds": score.execution_time_seconds,
                },
                "detailed_report": report,
            }

        except Exception as e:
            return {"error": f"Mutation testing failed: {e}"}

    def _filter_target_files(
        self, target_files: Optional[List[str]], exclude_patterns: Optional[List[str]]
    ) -> Optional[List[str]]:
        """Filter target files based on inclusion and exclusion patterns."""
        if not target_files:
            return None

        filtered = target_files.copy()

        if exclude_patterns:
            for pattern in exclude_patterns:
                filtered = [f for f in filtered if pattern not in f]

        return filtered

    async def _create_and_test_sample_files(self) -> dict:
        """Create sample files and run mutation testing for validation."""
        import shutil
        from tempfile import TemporaryDirectory

        with TemporaryDirectory(prefix="mutation_test_") as temp_dir:
            temp_path = Path(temp_dir)

            # Create sample source file
            source_dir = temp_path / "src"
            source_dir.mkdir()

            sample_source = '''
def calculate_trading_fee(amount, fee_rate=0.001):
    """Calculate trading fee."""
    if amount <= 0:
        return 0
    return amount * fee_rate

def is_valid_price(price, min_price=0.0001):
    """Check if price is valid for trading."""
    return price > min_price

def get_position_size(balance, risk_percent, stop_loss_pct):
    """Calculate position size based on risk management."""
    if risk_percent <= 0 or stop_loss_pct <= 0:
        return 0

    risk_amount = balance * (risk_percent / 100)
    position_size = risk_amount / (stop_loss_pct / 100)

    return min(position_size, balance * 0.5)  # Max 50% of balance

def calculate_pip_value(symbol, lot_size, account_currency="USD"):
    """Calculate pip value for forex trading."""
    if symbol.endswith("JPY"):
        pip_size = 0.01
    else:
        pip_size = 0.0001

    return lot_size * pip_size
'''

            source_file = source_dir / "trading_calc.py"
            with open(source_file, "w") as f:
                f.write(sample_source)

            # Create test file
            test_dir = temp_path / "tests"
            test_dir.mkdir()

            sample_test = '''
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from trading_calc import calculate_trading_fee, is_valid_price, get_position_size, calculate_pip_value

def test_calculate_trading_fee():
    """Test trading fee calculation."""
    assert calculate_trading_fee(1000) == 1.0
    assert calculate_trading_fee(0) == 0
    assert calculate_trading_fee(-100) == 0
    assert calculate_trading_fee(1000, 0.002) == 2.0

def test_is_valid_price():
    """Test price validation."""
    assert is_valid_price(1.1000) == True
    assert is_valid_price(0.0001) == False
    assert is_valid_price(0.0002) == True
    assert is_valid_price(0) == False

def test_get_position_size():
    """Test position size calculation."""
    # Normal case
    size = get_position_size(10000, 2, 1)  # 2% risk, 1% stop loss
    assert size == 2000

    # Edge cases
    assert get_position_size(10000, 0, 1) == 0
    assert get_position_size(10000, 2, 0) == 0

    # Max position limit
    size = get_position_size(1000, 10, 1)  # Would be 10000, but limited to 500
    assert size == 500

def test_calculate_pip_value():
    """Test pip value calculation."""
    # Non-JPY pair
    assert calculate_pip_value("EURUSD", 100000) == 10.0

    # JPY pair
    assert calculate_pip_value("USDJPY", 100000) == 1000.0
'''

            test_file = test_dir / "test_trading_calc.py"
            with open(test_file, "w") as f:
                f.write(sample_test)

            # Run mutation testing on sample files
            try:
                tester = MutationTester([str(source_dir)], "python -m pytest")

                # Change to temp directory for test execution
                import os

                original_cwd = os.getcwd()
                os.chdir(temp_path)

                try:
                    score = tester.run_mutation_testing(
                        target_files=["trading_calc.py"]
                    )
                    report = tester.generate_report()

                    return {
                        "sample_test_results": {
                            "total_mutants": score.total_mutants,
                            "killed_mutants": score.killed_mutants,
                            "survived_mutants": score.survived_mutants,
                            "mutation_score": score.mutation_score,
                            "execution_time": score.execution_time_seconds,
                        },
                        "recommendations": report.get("recommendations", []),
                        "survived_mutations": report.get("survived_mutations", {}),
                        "success": True,
                    }

                finally:
                    os.chdir(original_cwd)

            except Exception as e:
                return {
                    "error": f"Sample mutation testing failed: {e}",
                    "success": False,
                }

    def print_mutation_results(self, results: dict):
        """Print formatted mutation testing results."""
        if "error" in results:
            print(f"❌ {results['error']}")
            return

        if "sample_test_results" in results:
            # Quick test results
            sample = results["sample_test_results"]
            print(f"\n📊 Sample Mutation Test Results:")
            print(f"   Total Mutants: {sample['total_mutants']}")
            print(f"   Killed: {sample['killed_mutants']}")
            print(f"   Survived: {sample['survived_mutants']}")
            print(f"   Mutation Score: {sample['mutation_score']:.1f}%")
            print(f"   Execution Time: {sample['execution_time']:.1f}s")

            if results.get("recommendations"):
                print(f"\n💡 Recommendations:")
                for rec in results["recommendations"]:
                    print(f"   {rec}")

        elif "score" in results:
            # Comprehensive test results
            score = results["score"]
            print(f"\n📊 Comprehensive Mutation Test Results:")
            print(f"   Total Mutants: {score['total_mutants']}")
            print(f"   Killed: {score['killed_mutants']}")
            print(f"   Survived: {score['survived_mutants']}")
            print(f"   Mutation Score: {score['mutation_score']:.1f}%")
            print(f"   Detection Rate: {score['detection_rate']:.1f}%")
            print(f"   Execution Time: {score['execution_time_seconds']:.1f}s")

            report = results.get("detailed_report", {})
            if report.get("recommendations"):
                print(f"\n💡 Recommendations:")
                for rec in report["recommendations"]:
                    print(f"   {rec}")

    def analyze_mutation_gaps(self, results: dict) -> List[str]:
        """Analyze mutation testing results and identify test gaps."""
        gaps = []

        if "detailed_report" in results:
            report = results["detailed_report"]
            survived = report.get("survived_mutations", {})

            # Analyze by file
            by_file = survived.get("by_file", {})
            if by_file:
                worst_files = sorted(by_file.items(), key=lambda x: x[1], reverse=True)[
                    :3
                ]
                for file_path, count in worst_files:
                    gaps.append(
                        f"File '{Path(file_path).name}' has {count} surviving mutations"
                    )

            # Analyze by mutation type
            by_type = survived.get("by_type", {})
            if by_type:
                worst_types = sorted(by_type.items(), key=lambda x: x[1], reverse=True)[
                    :2
                ]
                for mutation_type, count in worst_types:
                    gaps.append(
                        f"Mutation type '{mutation_type}' has {count} survivors"
                    )

        return gaps


async def main():
    """Main entry point for mutation testing."""
    parser = argparse.ArgumentParser(description="FXML4 Mutation Testing Runner")

    parser.add_argument(
        "--quick", action="store_true", help="Run quick mutation test with sample files"
    )

    parser.add_argument(
        "--source",
        nargs="+",
        default=["fxml4"],
        help="Source directories to test (default: fxml4)",
    )

    parser.add_argument("--file", help="Specific file to test")

    parser.add_argument("--exclude", nargs="+", help="Patterns to exclude from testing")

    parser.add_argument(
        "--test-command", default="pytest", help="Test command to run (default: pytest)"
    )

    parser.add_argument(
        "--output", help="Output file for detailed report (JSON format)"
    )

    parser.add_argument(
        "--timeout", type=int, default=30, help="Test timeout in seconds (default: 30)"
    )

    args = parser.parse_args()

    if not MUTATION_TESTING_AVAILABLE:
        print("❌ Mutation testing framework not available")
        return 1

    try:
        runner = MutationTestRunner(args.source, args.test_command)

        if args.quick:
            # Run quick validation test
            results = await runner.run_quick_mutation_test()
        else:
            # Run comprehensive mutation testing
            target_files = [args.file] if args.file else None
            results = await runner.run_comprehensive_mutation_test(
                target_files=target_files, exclude_patterns=args.exclude
            )

        # Display results
        runner.print_mutation_results(results)

        # Analyze test gaps
        gaps = runner.analyze_mutation_gaps(results)
        if gaps:
            print(f"\n🎯 Test Coverage Gaps:")
            for gap in gaps:
                print(f"   • {gap}")

        # Save detailed report if requested
        if args.output and "detailed_report" in results:
            with open(args.output, "w") as f:
                json.dump(results["detailed_report"], f, indent=2)
            print(f"\n📄 Detailed report saved to: {args.output}")

        # Determine success based on mutation score
        if "sample_test_results" in results:
            mutation_score = results["sample_test_results"].get("mutation_score", 0)
        elif "score" in results:
            mutation_score = results["score"].get("mutation_score", 0)
        else:
            mutation_score = 0

        if mutation_score >= 70:
            print(f"\n✅ Mutation testing passed! Score: {mutation_score:.1f}%")
            return 0
        elif mutation_score >= 50:
            print(f"\n⚠️  Mutation testing acceptable. Score: {mutation_score:.1f}%")
            return 0
        else:
            print(
                f"\n❌ Mutation testing indicates weak test coverage. Score: {mutation_score:.1f}%"
            )
            return 1

    except Exception as e:
        print(f"💥 Mutation testing failed: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
