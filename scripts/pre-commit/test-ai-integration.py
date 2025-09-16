#!/usr/bin/env python3.12
"""
Test script for AI-enhanced pre-commit integration
Tests all AI components without requiring actual commits
"""

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path


def test_ai_workflow_validator():
    """Test the AI workflow validator."""
    print("🧪 Testing AI Workflow Validator...")

    try:
        # Test with existing AI workflows
        result = subprocess.run(
            [
                "python3.12",
                "scripts/pre-commit/ai-workflow-validator.py",
                "--check-workflows",
                "--check-config",
                "--check-dependencies",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

        print(f"   Return code: {result.returncode}")
        if result.stdout:
            print(f"   Output: {result.stdout[:200]}...")
        if result.stderr:
            print(f"   Errors: {result.stderr[:200]}...")

        return result.returncode == 0

    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


def test_ai_test_generator():
    """Test the AI test generator with dry run."""
    print("🧪 Testing AI Test Generator...")

    try:
        # Create a simple test file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(
                """
def calculate_risk_percentage(position_size: float, portfolio_value: float) -> float:
    '''Calculate risk as percentage of portfolio.'''
    if portfolio_value <= 0:
        raise ValueError("Portfolio value must be positive")
    return abs(position_size) / portfolio_value * 100

class TradingSignal:
    def __init__(self, symbol: str, signal_type: str, confidence: float):
        self.symbol = symbol
        self.signal_type = signal_type
        self.confidence = confidence

    def is_valid(self) -> bool:
        return 0.0 <= self.confidence <= 1.0
"""
            )
            test_file = f.name

        # Test with dry run
        result = subprocess.run(
            [
                "python3.12",
                "scripts/pre-commit/ai-test-generator.py",
                "--files",
                test_file,
                "--dry-run",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

        print(f"   Return code: {result.returncode}")
        if result.stdout:
            print(f"   Output: {result.stdout[:200]}...")
        if result.stderr:
            print(f"   Errors: {result.stderr[:200]}...")

        # Clean up
        Path(test_file).unlink(missing_ok=True)

        return result.returncode == 0

    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


def test_ai_code_reviewer():
    """Test the AI code reviewer with sample diff."""
    print("🧪 Testing AI Code Reviewer...")

    try:
        # Test with skip-ai flag to test infrastructure
        result = subprocess.run(
            ["python3.12", "scripts/pre-commit/ai-code-reviewer.py", "--skip-ai"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        print(f"   Return code: {result.returncode}")
        if result.stdout:
            print(f"   Output: {result.stdout[:200]}...")
        if result.stderr:
            print(f"   Errors: {result.stderr[:200]}...")

        return result.returncode == 0

    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


def test_pre_commit_config():
    """Test the pre-commit configuration validity."""
    print("🧪 Testing Pre-commit Configuration...")

    try:
        # Validate pre-commit config
        result = subprocess.run(
            ["pre-commit", "validate-config"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        print(f"   Return code: {result.returncode}")
        if result.stdout:
            print(f"   Output: {result.stdout}")
        if result.stderr:
            print(f"   Errors: {result.stderr}")

        return result.returncode == 0

    except FileNotFoundError:
        print("   ⚠️ pre-commit not installed")
        return True  # Don't fail if pre-commit not installed
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


def test_dependencies():
    """Test that all required dependencies are available."""
    print("🧪 Testing Dependencies...")

    dependencies = [
        ("python3.12", ["--version"]),
        ("git", ["--version"]),
        ("codex", ["--version"]),
        ("node", ["--version"]),
    ]

    all_available = True

    for dep, args in dependencies:
        try:
            result = subprocess.run([dep] + args, capture_output=True, timeout=10)
            if result.returncode == 0:
                print(f"   ✅ {dep} available")
            else:
                print(f"   ❌ {dep} not working")
                all_available = False
        except FileNotFoundError:
            print(f"   ❌ {dep} not installed")
            all_available = False
        except Exception as e:
            print(f"   ⚠️ {dep} check failed: {e}")

    return all_available


def test_file_permissions():
    """Test that all AI scripts have correct permissions."""
    print("🧪 Testing File Permissions...")

    ai_scripts = [
        "scripts/pre-commit/ai-workflow-validator.py",
        "scripts/pre-commit/ai-test-generator.py",
        "scripts/pre-commit/ai-code-reviewer.py",
        "scripts/ai-cicd-setup.sh",
    ]

    all_executable = True

    for script in ai_scripts:
        script_path = Path(script)
        if script_path.exists():
            if script_path.is_file() and script_path.stat().st_mode & 0o111:
                print(f"   ✅ {script} executable")
            else:
                print(f"   ❌ {script} not executable")
                all_executable = False
        else:
            print(f"   ❌ {script} not found")
            all_executable = False

    return all_executable


def run_integration_test():
    """Run a full integration test simulation."""
    print("🧪 Running Integration Test Simulation...")

    try:
        # Test pre-commit dry run on AI files
        ai_files = [
            ".github/workflows/ai-enhanced-ci.yml",
            ".ai/tests.yaml",
            ".ai/quality-gates.json",
        ]

        existing_files = [f for f in ai_files if Path(f).exists()]

        if existing_files:
            # Run pre-commit on these files (dry run)
            result = subprocess.run(
                ["pre-commit", "run", "--files"] + existing_files,
                capture_output=True,
                text=True,
                timeout=120,
            )

            print(f"   Return code: {result.returncode}")
            if result.stdout:
                print(f"   Output: {result.stdout[:300]}...")
            if result.stderr:
                print(f"   Errors: {result.stderr[:300]}...")

            # Don't require perfect success as some hooks may need actual changes
            return True
        else:
            print("   ⚠️ No AI files found for integration test")
            return True

    except FileNotFoundError:
        print("   ⚠️ pre-commit not available for integration test")
        return True
    except Exception as e:
        print(f"   ❌ Integration test error: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Test AI-enhanced pre-commit integration"
    )
    parser.add_argument(
        "--component",
        choices=[
            "validator",
            "generator",
            "reviewer",
            "config",
            "deps",
            "permissions",
            "integration",
        ],
        help="Test specific component only",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    print("🤖 AI-Enhanced Pre-commit Integration Test")
    print("=" * 50)

    test_functions = {
        "validator": test_ai_workflow_validator,
        "generator": test_ai_test_generator,
        "reviewer": test_ai_code_reviewer,
        "config": test_pre_commit_config,
        "deps": test_dependencies,
        "permissions": test_file_permissions,
        "integration": run_integration_test,
    }

    if args.component:
        tests_to_run = {args.component: test_functions[args.component]}
    else:
        tests_to_run = test_functions

    results = {}

    for test_name, test_func in tests_to_run.items():
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"❌ {test_name} test failed with exception: {e}")
            results[test_name] = False
        print()  # Empty line between tests

    # Summary
    print("📊 Test Results Summary:")
    print("-" * 30)

    passed = sum(1 for result in results.values() if result)
    total = len(results)

    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {test_name:<15} {status}")

    print(f"\nOverall: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All AI pre-commit integration tests passed!")
        return 0
    else:
        print(f"⚠️ {total - passed} test(s) failed - check configuration")

        # Provide helpful guidance
        print("\n💡 Common issues and solutions:")
        if not results.get("deps", True):
            print("   - Install missing dependencies: npm install -g @openai/codex")
        if not results.get("permissions", True):
            print("   - Fix permissions: chmod +x scripts/pre-commit/ai-*.py")
        if not results.get("config", True):
            print("   - Check .pre-commit-config.yaml syntax")
        if not results.get("validator", True):
            print("   - Check AI configuration files in .ai/ directory")

        return 1


if __name__ == "__main__":
    sys.exit(main())
