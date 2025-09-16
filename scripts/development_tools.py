#!/usr/bin/env python3
"""
Development Tools for FXML4
Consolidated utilities for code analysis, dependency checking, and testing.
"""

import argparse
import ast
import importlib.util
import json
import os
import re
import subprocess
import sys
import unittest
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import pytest


class ImportAnalyzer(ast.NodeVisitor):
    """AST visitor to analyze imports and usage."""

    def __init__(self):
        self.imports = {}  # module -> alias/None
        self.from_imports = {}  # module -> {name -> alias}
        self.used_names = set()  # All names used in the code
        self.import_lines = {}  # line numbers for imports

    def visit_Import(self, node):
        for alias in node.names:
            name = alias.asname if alias.asname else alias.name
            self.imports[alias.name] = alias.asname
            self.import_lines[alias.name] = node.lineno
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.module:
            if node.module not in self.from_imports:
                self.from_imports[node.module] = {}
            for alias in node.names:
                name = alias.asname if alias.asname else alias.name
                self.from_imports[node.module][alias.name] = alias.asname
                self.import_lines[f"{node.module}.{alias.name}"] = node.lineno
        self.generic_visit(node)

    def visit_Name(self, node):
        self.used_names.add(node.id)
        self.generic_visit(node)

    def visit_Attribute(self, node):
        # Track attribute access like module.function
        if isinstance(node.value, ast.Name):
            self.used_names.add(f"{node.value.id}.{node.attr}")
        self.generic_visit(node)


def analyze_imports(directory: str = ".") -> Dict:
    """Analyze import patterns in Python files."""
    issues = {
        "unused_imports": [],
        "circular_imports": [],
        "missing_imports": [],
        "external_dependencies": set(),
        "files_analyzed": 0,
    }

    for py_file in Path(directory).rglob("*.py"):
        try:
            with open(py_file, "r", encoding="utf-8") as f:
                content = f.read()
                tree = ast.parse(content)
                analyzer = ImportAnalyzer()
                analyzer.visit(tree)

                # Check for unused imports
                for module, alias in analyzer.imports.items():
                    name = alias if alias else module
                    if name not in analyzer.used_names:
                        issues["unused_imports"].append(
                            {
                                "file": str(py_file),
                                "module": module,
                                "line": analyzer.import_lines.get(module, 0),
                            }
                        )

                # Track external dependencies
                for module in analyzer.imports:
                    if not module.startswith("fxml4") and not module.startswith("."):
                        issues["external_dependencies"].add(module)

                issues["files_analyzed"] += 1
        except Exception as e:
            print(f"Error analyzing {py_file}: {e}")

    issues["external_dependencies"] = sorted(list(issues["external_dependencies"]))
    return issues


def check_dependencies() -> Dict:
    """Check for missing or problematic dependencies."""
    issues = {"missing_packages": [], "version_conflicts": [], "import_errors": []}

    # Read requirements.txt
    try:
        with open("requirements.txt", "r") as f:
            requirements = f.read().splitlines()
    except FileNotFoundError:
        return {"error": "requirements.txt not found"}

    # Check each requirement
    for req in requirements:
        if req.strip() and not req.startswith("#"):
            package = req.split("==")[0].split(">=")[0].split("<=")[0].strip()
            try:
                __import__(package)
            except ImportError:
                issues["missing_packages"].append(package)

    return issues


def detect_circular_imports(directory: str = ".") -> List[Dict]:
    """Detect circular import patterns."""
    import_graph = {}

    for py_file in Path(directory).rglob("*.py"):
        try:
            with open(py_file, "r", encoding="utf-8") as f:
                content = f.read()
                tree = ast.parse(content)
                analyzer = ImportAnalyzer()
                analyzer.visit(tree)

                file_key = str(py_file.relative_to(Path(directory)))
                import_graph[file_key] = []

                for module in analyzer.imports:
                    if module.startswith("fxml4"):
                        import_graph[file_key].append(module)

                for module in analyzer.from_imports:
                    if module.startswith("fxml4"):
                        import_graph[file_key].append(module)

        except Exception as e:
            print(f"Error analyzing {py_file}: {e}")

    # Simple cycle detection (can be enhanced)
    cycles = []
    for file, imports in import_graph.items():
        for imp in imports:
            if imp in import_graph and file in import_graph[imp]:
                cycles.append({"file1": file, "file2": imp})

    return cycles


def run_test_suite(test_type: str = "basic") -> Dict:
    """Run different types of test suites."""
    results = {"test_type": test_type, "status": "unknown", "output": "", "errors": []}

    try:
        if test_type == "basic":
            # Run basic tests
            result = subprocess.run(
                [sys.executable, "-m", "pytest", "tests/", "-v", "--tb=short"],
                capture_output=True,
                text=True,
                timeout=300,
            )

        elif test_type == "unit":
            # Run unit tests only
            result = subprocess.run(
                [sys.executable, "-m", "pytest", "tests/unit/", "-v"],
                capture_output=True,
                text=True,
                timeout=300,
            )

        elif test_type == "integration":
            # Run integration tests
            result = subprocess.run(
                [sys.executable, "-m", "pytest", "tests/integration/", "-v"],
                capture_output=True,
                text=True,
                timeout=600,
            )

        elif test_type == "comprehensive":
            # Run comprehensive test suite
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    "tests/",
                    "-v",
                    "--cov=fxml4",
                    "--cov-report=term-missing",
                ],
                capture_output=True,
                text=True,
                timeout=900,
            )

        else:
            raise ValueError(f"Unknown test type: {test_type}")

        results["status"] = "passed" if result.returncode == 0 else "failed"
        results["output"] = result.stdout
        results["errors"] = result.stderr.split("\n") if result.stderr else []

    except subprocess.TimeoutExpired:
        results["status"] = "timeout"
        results["errors"] = ["Test execution timed out"]
    except Exception as e:
        results["status"] = "error"
        results["errors"] = [str(e)]

    return results


def analyze_tests(directory: str = "tests") -> Dict:
    """Analyze test files and test coverage."""
    analysis = {
        "test_files": [],
        "total_tests": 0,
        "test_categories": {},
        "missing_tests": [],
        "recommendations": [],
    }

    test_path = Path(directory)
    if not test_path.exists():
        return {"error": f"Test directory {directory} not found"}

    # Analyze test files
    for test_file in test_path.rglob("test_*.py"):
        try:
            with open(test_file, "r", encoding="utf-8") as f:
                content = f.read()
                tree = ast.parse(content)

                file_info = {
                    "file": str(test_file),
                    "test_functions": [],
                    "test_classes": [],
                }

                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef) and node.name.startswith(
                        "test_"
                    ):
                        file_info["test_functions"].append(node.name)
                        analysis["total_tests"] += 1
                    elif isinstance(node, ast.ClassDef) and node.name.startswith(
                        "Test"
                    ):
                        file_info["test_classes"].append(node.name)

                analysis["test_files"].append(file_info)

        except Exception as e:
            print(f"Error analyzing {test_file}: {e}")

    # Check for missing test categories
    expected_categories = [
        "unit",
        "integration",
        "functional",
        "performance",
        "security",
        "api",
        "brokers",
        "ml",
        "backtesting",
    ]

    for category in expected_categories:
        category_path = test_path / category
        if not category_path.exists():
            analysis["missing_tests"].append(category)

    # Generate recommendations
    if analysis["total_tests"] < 100:
        analysis["recommendations"].append(
            "Consider adding more comprehensive test coverage"
        )

    if "integration" in analysis["missing_tests"]:
        analysis["recommendations"].append(
            "Add integration tests for critical workflows"
        )

    return analysis


def main():
    """Main CLI interface for development tools."""
    parser = argparse.ArgumentParser(description="FXML4 Development Tools")
    parser.add_argument(
        "command",
        choices=[
            "analyze-imports",
            "check-deps",
            "detect-circular",
            "run-tests",
            "analyze-tests",
            "all",
        ],
        help="Command to run",
    )
    parser.add_argument("--directory", default=".", help="Directory to analyze")
    parser.add_argument(
        "--test-type",
        default="basic",
        choices=["basic", "unit", "integration", "comprehensive"],
        help="Type of tests to run",
    )
    parser.add_argument("--output", help="Output file for results")

    args = parser.parse_args()

    results = {}

    if args.command == "analyze-imports" or args.command == "all":
        print("Analyzing imports...")
        results["import_analysis"] = analyze_imports(args.directory)

    if args.command == "check-deps" or args.command == "all":
        print("Checking dependencies...")
        results["dependency_check"] = check_dependencies()

    if args.command == "detect-circular" or args.command == "all":
        print("Detecting circular imports...")
        results["circular_imports"] = detect_circular_imports(args.directory)

    if args.command == "run-tests" or args.command == "all":
        print(f"Running {args.test_type} tests...")
        results["test_results"] = run_test_suite(args.test_type)

    if args.command == "analyze-tests" or args.command == "all":
        print("Analyzing test suite...")
        results["test_analysis"] = analyze_tests()

    # Output results
    if args.output:
        with open(args.output, "w") as f:
            json.dump(results, f, indent=2)
        print(f"Results saved to {args.output}")
    else:
        print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
