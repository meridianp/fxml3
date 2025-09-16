#!/usr/bin/env python3.12
"""
AI Test Generator for Pre-commit Hook
Automatically generates tests for changed Python files using OpenAI Codex
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


def get_staged_python_files() -> List[Path]:
    """Get list of staged Python files."""
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=AM"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            return []

        files = []
        for line in result.stdout.strip().split("\n"):
            if line and line.endswith(".py"):
                path = Path(line)
                # Only include files in fxml4/ directory (not tests, docs, archive, etc.)
                if (
                    path.exists()
                    and str(path).startswith("fxml4/")
                    and "test_" not in path.name
                    and "/tests/" not in str(path)
                ):
                    files.append(path)

        return files

    except subprocess.TimeoutExpired:
        print("⚠️ Git command timeout")
        return []
    except Exception as e:
        print(f"⚠️ Error getting staged files: {e}")
        return []


def find_existing_test_file(source_file: Path) -> Optional[Path]:
    """Find existing test file for a source file."""
    # Common test file patterns
    test_patterns = [
        f"tests/test_{source_file.stem}.py",
        f"tests/{source_file.parent.name}/test_{source_file.stem}.py",
        f"tests/unit/test_{source_file.stem}.py",
        f"tests/integration/test_{source_file.stem}.py",
    ]

    for pattern in test_patterns:
        test_path = Path(pattern)
        if test_path.exists():
            return test_path

    return None


def analyze_source_file(source_file: Path) -> Dict:
    """Analyze source file to understand its structure."""
    try:
        with open(source_file, "r") as f:
            content = f.read()
    except Exception as e:
        return {"error": f"Cannot read {source_file}: {e}"}

    analysis = {
        "file": str(source_file),
        "functions": [],
        "classes": [],
        "imports": [],
        "complexity": "medium",
        "type": "unknown",
    }

    lines = content.split("\n")
    for line in lines:
        line = line.strip()

        # Extract function definitions
        if line.startswith("def ") and not line.startswith("def _"):
            func_name = line.split("(")[0].replace("def ", "")
            analysis["functions"].append(func_name)

        # Extract class definitions
        elif line.startswith("class "):
            class_name = line.split("(")[0].replace("class ", "").rstrip(":")
            analysis["classes"].append(class_name)

        # Extract imports
        elif line.startswith("import ") or line.startswith("from "):
            analysis["imports"].append(line)

    # Determine file type based on path and content
    if "broker" in str(source_file).lower():
        analysis["type"] = "broker_integration"
    elif "ml" in str(source_file).lower() or "model" in str(source_file).lower():
        analysis["type"] = "machine_learning"
    elif "api" in str(source_file).lower():
        analysis["type"] = "api_endpoint"
    elif "strategy" in str(source_file).lower():
        analysis["type"] = "trading_strategy"
    elif "risk" in str(source_file).lower():
        analysis["type"] = "risk_management"
    elif "fix" in str(source_file).lower():
        analysis["type"] = "fix_protocol"
    elif "auth" in str(source_file).lower():
        analysis["type"] = "authentication"

    # Estimate complexity
    total_items = len(analysis["functions"]) + len(analysis["classes"])
    if total_items < 3:
        analysis["complexity"] = "simple"
    elif total_items > 8:
        analysis["complexity"] = "complex"

    return analysis


def generate_test_with_ai(source_file: Path, analysis: Dict) -> Tuple[bool, str, str]:
    """Generate test file using AI."""
    if not check_ai_availability():
        return False, "AI not available", ""

    # Create AI prompt based on analysis
    prompt = create_test_generation_prompt(source_file, analysis)

    try:
        # Use Codex CLI to generate tests
        result = subprocess.run(
            ["codex", "exec", "-p", "fxml4_ci", "--sandbox", "workspace-write", prompt],
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode == 0:
            # Extract generated test code from output
            output = result.stdout
            test_code = extract_test_code_from_output(output)
            return True, "Success", test_code
        else:
            error_msg = result.stderr or result.stdout
            return False, f"AI generation failed: {error_msg}", ""

    except subprocess.TimeoutExpired:
        return False, "AI generation timeout", ""
    except Exception as e:
        return False, f"AI generation error: {e}", ""


def create_test_generation_prompt(source_file: Path, analysis: Dict) -> str:
    """Create AI prompt for test generation."""
    file_type = analysis.get("type", "unknown")
    functions = analysis.get("functions", [])
    classes = analysis.get("classes", [])
    complexity = analysis.get("complexity", "medium")

    prompt = f"""
Generate comprehensive pytest tests for the FXML4 trading system module: {source_file}

File Type: {file_type}
Complexity: {complexity}
Functions to test: {', '.join(functions[:10])}  # Limit to first 10
Classes to test: {', '.join(classes[:5])}       # Limit to first 5

Requirements:
1. Use pytest framework with appropriate fixtures
2. Target 90% code coverage minimum
3. Include positive, negative, and boundary test cases
4. Mock external dependencies (broker APIs, databases, network calls)
5. Follow FXML4 testing patterns and naming conventions
6. Include docstrings explaining test purpose
7. Use appropriate pytest markers (e.g., @pytest.mark.unit, @pytest.mark.{file_type})

Special considerations for {file_type}:
"""

    # Add type-specific requirements
    type_requirements = {
        "broker_integration": """
- Mock broker API responses and connection states
- Test connection failure scenarios and retries
- Validate FIX protocol message handling
- Test order execution and status updates
""",
        "machine_learning": """
- Mock model training and inference
- Test data preprocessing and feature engineering
- Validate model performance metrics
- Test prediction accuracy and error handling
""",
        "api_endpoint": """
- Test HTTP status codes and response formats
- Validate authentication and authorization
- Test input validation and error responses
- Include security test cases (SQL injection, XSS)
""",
        "trading_strategy": """
- Mock market data and price feeds
- Test signal generation logic
- Validate risk management integration
- Test portfolio management functions
""",
        "risk_management": """
- Test position sizing calculations
- Validate risk limit enforcement
- Test drawdown and stop-loss logic
- Mock portfolio and trade data
""",
        "fix_protocol": """
- Mock FIX message parsing and generation
- Test session management
- Validate message routing and handling
- Test protocol compliance
""",
        "authentication": """
- Test JWT token generation and validation
- Mock user authentication flows
- Test permission and role validation
- Include security vulnerability tests
""",
    }

    prompt += type_requirements.get(
        file_type,
        """
- Mock external dependencies appropriately
- Test error handling and edge cases
- Validate input parameters and return values
- Include performance considerations if relevant
""",
    )

    prompt += f"""
Generate test file structure:
```python
import pytest
from unittest.mock import Mock, patch, MagicMock
from fxml4.{str(source_file).replace('fxml4/', '').replace('.py', '').replace('/', '.')} import *

# Test fixtures
@pytest.fixture
def sample_data():
    # Mock data for testing
    pass

# Test classes and functions here
# Each test should have clear docstring
# Use descriptive test names: test_function_name_when_condition_then_expected_outcome
```

Focus on:
- Critical business logic paths
- Error handling and exception cases
- Integration points with other components
- Security and validation logic
- Performance-critical sections

Output only the complete test file code, no additional explanation.
"""

    return prompt


def extract_test_code_from_output(output: str) -> str:
    """Extract Python test code from AI output."""
    lines = output.split("\n")
    code_lines = []
    in_code_block = False

    for line in lines:
        # Detect code block boundaries
        if line.strip().startswith("```python") or line.strip().startswith("```"):
            in_code_block = not in_code_block
            continue

        # Extract code lines
        if in_code_block:
            code_lines.append(line)
        elif (
            line.strip().startswith("import ")
            or line.strip().startswith("from ")
            or line.strip().startswith("def ")
            or line.strip().startswith("class ")
        ):
            # Direct code without code blocks
            code_lines.append(line)
        elif code_lines and (
            line.strip().startswith(" ")
            or line.strip().startswith("@")
            or line.strip() == ""
        ):
            # Continuation of code
            code_lines.append(line)

    return "\n".join(code_lines).strip()


def write_test_file(test_code: str, test_file_path: Path) -> bool:
    """Write generated test code to file."""
    try:
        # Ensure test directory exists
        test_file_path.parent.mkdir(parents=True, exist_ok=True)

        with open(test_file_path, "w") as f:
            f.write(test_code)

        return True
    except Exception as e:
        print(f"❌ Error writing test file {test_file_path}: {e}")
        return False


def validate_generated_test(test_file_path: Path) -> Tuple[bool, str]:
    """Validate that generated test file is syntactically correct."""
    try:
        # Check Python syntax
        result = subprocess.run(
            ["python", "-m", "py_compile", str(test_file_path)],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0:
            return True, "Valid Python syntax"
        else:
            return False, f"Syntax error: {result.stderr}"

    except subprocess.TimeoutExpired:
        return False, "Validation timeout"
    except Exception as e:
        return False, f"Validation error: {e}"


def determine_test_file_path(source_file: Path) -> Path:
    """Determine appropriate path for test file."""
    # Map source directories to test directories
    if "brokers" in str(source_file):
        return Path(f"tests/brokers/test_{source_file.stem}.py")
    elif "ml" in str(source_file):
        return Path(f"tests/ml/test_{source_file.stem}.py")
    elif "api" in str(source_file):
        return Path(f"tests/api/test_{source_file.stem}.py")
    elif "strategy" in str(source_file):
        return Path(f"tests/strategy/test_{source_file.stem}.py")
    elif "fix" in str(source_file):
        return Path(f"tests/fix/test_{source_file.stem}.py")
    else:
        return Path(f"tests/unit/test_{source_file.stem}.py")


def check_ai_availability() -> bool:
    """Check if AI tools are available in test context/environment."""
    try:
        # Check Codex CLI availability
        result = subprocess.run(["codex", "--version"], capture_output=True, timeout=10)
        if result.returncode != 0:
            print("❌ Codex CLI not available - return code:", result.returncode)
            print("stderr:", result.stderr.decode() if result.stderr else "No stderr")
            return False

        print("✅ Codex CLI available:", result.stdout.decode().strip())

        # Check Node.js availability (required for Codex CLI)
        node_result = subprocess.run(
            ["node", "--version"], capture_output=True, timeout=5
        )
        if node_result.returncode != 0:
            print("❌ Node.js not available (required for Codex CLI)")
            return False

        print("✅ Node.js available:", node_result.stdout.decode().strip())

        # Ensure Codex CLI is in PATH
        which_result = subprocess.run(
            ["which", "codex"], capture_output=True, timeout=5
        )
        if which_result.returncode != 0:
            print("❌ Codex CLI not found in PATH")
            return False

        print("✅ Codex CLI path:", which_result.stdout.decode().strip())

        # Check OpenAI API key in environment or GitHub secrets
        if not os.getenv("OPENAI_API_KEY"):
            print("⚠️ OPENAI_API_KEY not set - AI generation may fail in CI/CD")
            # Don't fail completely as it might be in GitHub secrets
            print("   This is expected in pre-commit context, will work in CI/CD")

        # Test basic Codex CLI functionality
        try:
            test_result = subprocess.run(
                ["codex", "--help"], capture_output=True, timeout=10
            )
            if test_result.returncode != 0:
                print("❌ Codex CLI help command failed")
                return False
            print("✅ Codex CLI basic functionality verified")
        except subprocess.TimeoutExpired:
            print("❌ Codex CLI help command timeout")
            return False

        return True

    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        print(f"❌ Codex CLI not installed or not accessible: {e}")
        print("   Install with: npm install -g @openai/codex")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Generate AI-powered tests for staged files"
    )
    parser.add_argument(
        "--files", nargs="*", help="Specific files to generate tests for"
    )
    parser.add_argument(
        "--force", action="store_true", help="Force regeneration even if tests exist"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without doing it",
    )
    parser.add_argument(
        "--skip-validation", action="store_true", help="Skip test validation"
    )

    args = parser.parse_args()

    # Get files to process
    if args.files:
        source_files = [Path(f) for f in args.files if f.endswith(".py")]
    else:
        source_files = get_staged_python_files()

    if not source_files:
        print("✅ No Python files to generate tests for")
        return 0

    print(f"🤖 AI Test Generator - Processing {len(source_files)} files")

    if not check_ai_availability():
        print("⚠️ AI not available - skipping test generation")
        return 0

    generated_count = 0
    error_count = 0

    for source_file in source_files:
        print(f"\n📄 Processing: {source_file}")

        # Check if test already exists
        existing_test = find_existing_test_file(source_file)
        if existing_test and not args.force:
            print(f"  ✅ Test exists: {existing_test}")
            continue

        # Analyze source file
        analysis = analyze_source_file(source_file)
        if "error" in analysis:
            print(f"  ❌ {analysis['error']}")
            error_count += 1
            continue

        print(f"  📊 Type: {analysis['type']}, Complexity: {analysis['complexity']}")
        print(
            f"  🔍 Functions: {len(analysis['functions'])}, Classes: {len(analysis['classes'])}"
        )

        if args.dry_run:
            test_path = determine_test_file_path(source_file)
            print(f"  🔮 Would generate: {test_path}")
            continue

        # Generate tests with AI
        print(f"  🤖 Generating tests with AI...")
        success, message, test_code = generate_test_with_ai(source_file, analysis)

        if not success:
            print(f"  ❌ Generation failed: {message}")
            error_count += 1
            continue

        if not test_code:
            print(f"  ⚠️ No test code generated")
            continue

        # Determine test file path
        test_file_path = determine_test_file_path(source_file)
        print(f"  📝 Writing test: {test_file_path}")

        # Write test file
        if write_test_file(test_code, test_file_path):
            # Validate generated test
            if not args.skip_validation:
                valid, validation_msg = validate_generated_test(test_file_path)
                if valid:
                    print(f"  ✅ Test generated and validated")
                    generated_count += 1

                    # Stage the generated test file
                    try:
                        subprocess.run(["git", "add", str(test_file_path)], timeout=10)
                        print(f"  📋 Staged test file")
                    except Exception as e:
                        print(f"  ⚠️ Could not stage test file: {e}")
                else:
                    print(f"  ❌ Validation failed: {validation_msg}")
                    # Remove invalid test file
                    test_file_path.unlink(missing_ok=True)
                    error_count += 1
            else:
                print(f"  ✅ Test generated (validation skipped)")
                generated_count += 1
        else:
            error_count += 1

    # Summary
    print(f"\n📊 AI Test Generation Summary:")
    print(f"  ✅ Generated: {generated_count} test files")
    print(f"  ❌ Errors: {error_count}")

    if generated_count > 0:
        print(f"\n💡 Next steps:")
        print(f"  - Review generated tests for accuracy")
        print(f"  - Run: pytest -v to validate tests")
        print(f"  - Adjust coverage thresholds if needed")

    # Exit with error if any generation failed
    return 1 if error_count > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
