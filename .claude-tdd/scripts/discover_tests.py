#!/usr/bin/env python3
"""
FXML4 Claude TDD - Language-Agnostic Test Discovery
Discovers tests across Python and TypeScript components in the monorepo
"""

import glob
import json
import os
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


@dataclass
class TestFile:
    """Represents a discovered test file"""

    path: str
    language: str
    framework: str
    component: str
    category: str
    estimated_duration: float
    dependencies: List[str]
    markers: List[str]


@dataclass
class TestSuite:
    """Represents a collection of test files for a component"""

    component: str
    language: str
    framework: str
    total_files: int
    total_tests: int
    estimated_duration: float
    test_files: List[TestFile]


class TestDiscovery:
    """Language-agnostic test discovery for FXML4 monorepo"""

    def __init__(self, config_path: str = ".claude-tdd/config.yml"):
        self.config = self._load_config(config_path)
        self.project_root = Path.cwd()
        self.discovery_cache = {}

    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load TDD configuration"""
        try:
            with open(config_path, "r") as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"TDD config not found: {config_path}")

    def discover_all_tests(self) -> Dict[str, TestSuite]:
        """Discover tests across all components"""
        test_suites = {}

        for component_name, component_config in self.config["components"].items():
            print(f"Discovering tests for component: {component_name}")
            test_suite = self._discover_component_tests(
                component_name, component_config
            )
            test_suites[component_name] = test_suite

        return test_suites

    def _discover_component_tests(
        self, component_name: str, component_config: Dict[str, Any]
    ) -> TestSuite:
        """Discover tests for a specific component"""
        language = component_config["language"]
        framework = component_config["test_framework"]
        component_path = component_config["path"]
        test_paths = component_config["test_paths"]

        test_files = []

        if language == "python":
            test_files = self._discover_python_tests(
                component_name, component_path, test_paths, framework
            )
        elif language == "typescript":
            test_files = self._discover_typescript_tests(
                component_name, component_path, test_paths, framework
            )

        # Calculate totals
        total_files = len(test_files)
        total_tests = sum(self._count_tests_in_file(tf) for tf in test_files)
        estimated_duration = sum(tf.estimated_duration for tf in test_files)

        return TestSuite(
            component=component_name,
            language=language,
            framework=framework,
            total_files=total_files,
            total_tests=total_tests,
            estimated_duration=estimated_duration,
            test_files=test_files,
        )

    def _discover_python_tests(
        self,
        component_name: str,
        component_path: str,
        test_paths: List[str],
        framework: str,
    ) -> List[TestFile]:
        """Discover Python test files"""
        test_files = []
        test_patterns = self.config["tdd"]["test_patterns"]["python"]

        for test_path in test_paths:
            full_path = os.path.join(component_path, test_path)
            if not os.path.exists(full_path):
                continue

            for pattern in test_patterns:
                pattern_path = os.path.join(full_path, "**", pattern)
                for test_file in glob.glob(pattern_path, recursive=True):
                    test_file_obj = self._analyze_python_test_file(
                        test_file, component_name, framework
                    )
                    if test_file_obj:
                        test_files.append(test_file_obj)

        return test_files

    def _discover_typescript_tests(
        self,
        component_name: str,
        component_path: str,
        test_paths: List[str],
        framework: str,
    ) -> List[TestFile]:
        """Discover TypeScript test files"""
        test_files = []
        test_patterns = self.config["tdd"]["test_patterns"]["typescript"]

        for test_path in test_paths:
            full_path = os.path.join(component_path, test_path)
            if not os.path.exists(full_path):
                continue

            for pattern in test_patterns:
                pattern_path = os.path.join(full_path, "**", pattern)
                for test_file in glob.glob(pattern_path, recursive=True):
                    test_file_obj = self._analyze_typescript_test_file(
                        test_file, component_name, framework
                    )
                    if test_file_obj:
                        test_files.append(test_file_obj)

        return test_files

    def _analyze_python_test_file(
        self, file_path: str, component: str, framework: str
    ) -> Optional[TestFile]:
        """Analyze Python test file for metadata"""
        try:
            with open(file_path, "r") as f:
                content = f.read()

            # Extract pytest markers
            markers = self._extract_pytest_markers(content)

            # Determine category from markers and file path
            category = self._determine_test_category(markers, file_path)

            # Estimate duration based on category and markers
            estimated_duration = self._estimate_test_duration(markers, category)

            # Extract dependencies
            dependencies = self._extract_python_dependencies(content)

            return TestFile(
                path=file_path,
                language="python",
                framework=framework,
                component=component,
                category=category,
                estimated_duration=estimated_duration,
                dependencies=dependencies,
                markers=markers,
            )
        except Exception as e:
            print(f"Error analyzing Python test file {file_path}: {e}")
            return None

    def _analyze_typescript_test_file(
        self, file_path: str, component: str, framework: str
    ) -> Optional[TestFile]:
        """Analyze TypeScript test file for metadata"""
        try:
            with open(file_path, "r") as f:
                content = f.read()

            # Extract test categories from describe blocks and file path
            category = self._determine_typescript_test_category(content, file_path)

            # Estimate duration based on content analysis
            estimated_duration = self._estimate_typescript_test_duration(
                content, category
            )

            # Extract dependencies from imports
            dependencies = self._extract_typescript_dependencies(content)

            # Extract markers from comments and describe blocks
            markers = self._extract_typescript_markers(content)

            return TestFile(
                path=file_path,
                language="typescript",
                framework=framework,
                component=component,
                category=category,
                estimated_duration=estimated_duration,
                dependencies=dependencies,
                markers=markers,
            )
        except Exception as e:
            print(f"Error analyzing TypeScript test file {file_path}: {e}")
            return None

    def _extract_pytest_markers(self, content: str) -> List[str]:
        """Extract pytest markers from Python test file"""
        markers = []
        lines = content.split("\n")

        for line in lines:
            line = line.strip()
            if line.startswith("@pytest.mark."):
                marker = line.replace("@pytest.mark.", "").split("(")[0]
                markers.append(marker)

        return markers

    def _extract_typescript_markers(self, content: str) -> List[str]:
        """Extract test markers from TypeScript test file"""
        markers = []

        # Look for comment-based markers
        lines = content.split("\n")
        for line in lines:
            line = line.strip()
            if "// @test-marker:" in line:
                marker = line.split("// @test-marker:")[1].strip()
                markers.append(marker)

        # Infer markers from describe blocks
        if "describe(" in content:
            if "integration" in content.lower():
                markers.append("integration")
            if "unit" in content.lower():
                markers.append("unit")
            if "e2e" in content.lower():
                markers.append("e2e")

        return markers

    def _determine_test_category(self, markers: List[str], file_path: str) -> str:
        """Determine test category from markers and file path"""
        category_mapping = self.config["tdd"]["test_categories"]

        # Check markers first - prioritize critical tests
        if any(marker in ["critical", "mandatory"] for marker in markers):
            return "critical"

        # Check for specific test types
        for category, category_markers in category_mapping.items():
            if any(marker in markers for marker in category_markers):
                return category

        # Enhanced path-based detection for FXML4 structure
        if "/unit/" in file_path or "test_unit_" in file_path:
            return "unit"
        elif "/integration/" in file_path or "test_integration_" in file_path:
            return "integration"
        elif "/performance/" in file_path or "test_performance_" in file_path:
            return "performance"
        elif "/security/" in file_path or "test_security_" in file_path:
            return "security"
        elif "/critical/" in file_path or "test_critical_" in file_path:
            return "critical"
        elif "/api/" in file_path or "test_api_" in file_path:
            return "integration"
        elif "/stress/" in file_path or "test_stress_" in file_path:
            return "performance"
        elif "/e2e/" in file_path or "test_e2e_" in file_path:
            return "e2e"
        elif "/ml/" in file_path or "test_ml_" in file_path:
            return "ml"
        elif "/wave/" in file_path or "wave_analysis" in file_path:
            return "ml"

        return "unit"  # default

    def _determine_typescript_test_category(self, content: str, file_path: str) -> str:
        """Determine TypeScript test category"""
        if "integration" in content.lower() or "/integration/" in file_path:
            return "integration"
        elif "e2e" in content.lower() or "/e2e/" in file_path:
            return "integration"
        elif "performance" in content.lower() or "/performance/" in file_path:
            return "performance"
        elif "security" in content.lower() or "/security/" in file_path:
            return "security"

        return "unit"  # default

    def _estimate_test_duration(self, markers: List[str], category: str) -> float:
        """Estimate test duration in seconds"""
        base_duration = {
            "unit": 0.1,
            "integration": 2.0,
            "performance": 10.0,
            "security": 5.0,
            "ml": 15.0,
            "trading": 8.0,
            "critical": 1.0,
            "e2e": 30.0,
            "external_deps": 5.0,
            "database": 2.0,
            "real_time": 12.0,
            "infrastructure": 8.0,
        }

        duration = base_duration.get(category, 1.0)

        # Adjust based on FXML4-specific markers
        if "slow" in markers:
            duration *= 5
        if "stress" in markers:
            duration *= 10
        if "requires_ib" in markers or "requires_fxcm" in markers:
            duration *= 3
        if "requires_db" in markers:
            duration *= 2
        if "requires_rabbitmq" in markers:
            duration *= 2.5
        if "critical" in markers or "mandatory" in markers:
            duration *= 0.8  # Critical tests should be fast
        if "concurrency" in markers:
            duration *= 4
        if "production" in markers:
            duration *= 0.5  # Read-only production tests

        return duration

    def _estimate_typescript_test_duration(self, content: str, category: str) -> float:
        """Estimate TypeScript test duration"""
        base_duration = {
            "unit": 0.05,
            "integration": 1.0,
            "performance": 5.0,
            "security": 2.0,
        }

        duration = base_duration.get(category, 0.5)

        # Adjust based on content complexity
        test_count = content.count("it(") + content.count("test(")
        duration *= max(1, test_count * 0.1)

        return duration

    def _extract_python_dependencies(self, content: str) -> List[str]:
        """Extract Python dependencies from imports"""
        dependencies = []
        lines = content.split("\n")

        for line in lines:
            line = line.strip()
            if line.startswith("import ") or line.startswith("from "):
                if "fxml4" in line or "elliott_wave" in line:
                    dependencies.append(line)

        return dependencies

    def _extract_typescript_dependencies(self, content: str) -> List[str]:
        """Extract TypeScript dependencies from imports"""
        dependencies = []
        lines = content.split("\n")

        for line in lines:
            line = line.strip()
            if line.startswith("import ") and ("from " in line):
                if "../" in line or "./" in line or "@/" in line:
                    dependencies.append(line)

        return dependencies

    def _count_tests_in_file(self, test_file: TestFile) -> int:
        """Count number of tests in a test file"""
        try:
            with open(test_file.path, "r") as f:
                content = f.read()

            if test_file.language == "python":
                return content.count("def test_") + content.count("async def test_")
            elif test_file.language == "typescript":
                return content.count("it(") + content.count("test(")

        except Exception:
            return 1  # default estimate

        return 1

    def export_discovery_results(
        self,
        test_suites: Dict[str, TestSuite],
        output_file: str = ".claude-tdd/discovery_results.json",
    ):
        """Export discovery results to JSON"""
        results = {
            "timestamp": datetime.now().isoformat(),
            "project": self.config["project"]["name"],
            "version": self.config["project"]["version"],
            "test_suites": {name: asdict(suite) for name, suite in test_suites.items()},
        }

        with open(output_file, "w") as f:
            json.dump(results, f, indent=2)

        print(f"Discovery results exported to: {output_file}")

    def print_discovery_summary(self, test_suites: Dict[str, TestSuite]):
        """Print a summary of discovered tests"""
        print("\n" + "=" * 60)
        print("FXML4 Test Discovery Summary")
        print("=" * 60)

        total_files = sum(suite.total_files for suite in test_suites.values())
        total_tests = sum(suite.total_tests for suite in test_suites.values())
        total_duration = sum(suite.estimated_duration for suite in test_suites.values())

        print(f"Total Test Files: {total_files}")
        print(f"Total Test Cases: {total_tests}")
        print(f"Estimated Duration: {total_duration:.1f} seconds")
        print()

        for component_name, suite in test_suites.items():
            print(f"{component_name.upper()} Component:")
            print(f"  Language: {suite.language}")
            print(f"  Framework: {suite.framework}")
            print(f"  Files: {suite.total_files}")
            print(f"  Tests: {suite.total_tests}")
            print(f"  Duration: {suite.estimated_duration:.1f}s")
            print()


def main():
    """Main entry point for test discovery"""
    discovery = TestDiscovery()
    test_suites = discovery.discover_all_tests()

    discovery.print_discovery_summary(test_suites)
    discovery.export_discovery_results(test_suites)


if __name__ == "__main__":
    main()
