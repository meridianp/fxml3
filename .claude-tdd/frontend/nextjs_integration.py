#!/usr/bin/env python3
"""
FXML4 Next.js Frontend Testing Integration
Specialized integration for Next.js TypeScript testing within the TDD framework
"""

import json
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml


@dataclass
class NextJSTestConfig:
    """Configuration for Next.js testing integration"""

    project_path: str
    test_frameworks: List[str] = field(
        default_factory=lambda: ["jest", "cypress", "playwright"]
    )
    test_patterns: List[str] = field(
        default_factory=lambda: ["**/*.test.{ts,tsx}", "**/*.spec.{ts,tsx}"]
    )
    coverage_threshold: float = 80.0
    performance_budget: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FrontendTestResult:
    """Result of frontend test execution"""

    test_type: str
    success: bool
    execution_time: float
    coverage_percentage: Optional[float] = None
    failed_tests: List[str] = field(default_factory=list)
    performance_metrics: Dict[str, float] = field(default_factory=dict)
    error_message: Optional[str] = None


class NextJSIntegration:
    """Integration layer for Next.js testing within FXML4 TDD framework"""

    def __init__(self, project_path: str = "fxml4-ui/"):
        self.project_path = Path(project_path)
        self.config = self._load_frontend_config()
        self.test_results = []

    def _load_frontend_config(self) -> NextJSTestConfig:
        """Load frontend-specific configuration"""
        return NextJSTestConfig(
            project_path=str(self.project_path),
            performance_budget={
                "largest_contentful_paint": 2500,  # ms
                "first_input_delay": 100,  # ms
                "cumulative_layout_shift": 0.1,
                "bundle_size_limit": 250000,  # bytes
            },
        )

    def setup_frontend_testing(self) -> bool:
        """Set up frontend testing environment"""
        try:
            print("Setting up FXML4 frontend testing environment...")

            # Check if frontend directory exists
            if not self.project_path.exists():
                print(f"Warning: Frontend path {self.project_path} does not exist")
                return False

            # Create necessary testing configuration files
            self._create_jest_config()
            self._create_cypress_config()
            self._create_playwright_config()
            self._create_testing_library_setup()

            print("Frontend testing environment setup complete")
            return True

        except Exception as e:
            print(f"Error setting up frontend testing: {e}")
            return False

    def _create_jest_config(self):
        """Create Jest configuration for React/Next.js testing"""
        jest_config = {
            "preset": "next/jest",
            "setupFilesAfterEnv": ["<rootDir>/jest.setup.js"],
            "testEnvironment": "jsdom",
            "collectCoverageFrom": [
                "src/**/*.{ts,tsx}",
                "!src/**/*.d.ts",
                "!src/**/*.stories.{ts,tsx}",
                "!src/pages/_app.tsx",
                "!src/pages/_document.tsx",
            ],
            "coverageThreshold": {
                "global": {
                    "branches": 80,
                    "functions": 80,
                    "lines": 80,
                    "statements": 80,
                }
            },
            "moduleNameMapping": {
                "^@/(.*)$": "<rootDir>/src/$1",
                "^@/components/(.*)$": "<rootDir>/src/components/$1",
                "^@/hooks/(.*)$": "<rootDir>/src/hooks/$1",
                "^@/utils/(.*)$": "<rootDir>/src/utils/$1",
            },
            "testMatch": [
                "<rootDir>/src/**/__tests__/**/*.{ts,tsx}",
                "<rootDir>/src/**/*.{test,spec}.{ts,tsx}",
            ],
            "testPathIgnorePatterns": [
                "<rootDir>/.next/",
                "<rootDir>/node_modules/",
                "<rootDir>/cypress/",
            ],
            "transformIgnorePatterns": [
                "node_modules/(?!(.*\\.mjs$|@next/|next/|swiper/|ssr-window/|dom7/))",
            ],
        }

        config_path = self.project_path / "jest.config.js"
        with open(config_path, "w") as f:
            f.write("/** @type {import('jest').Config} */\n")
            f.write(f"const config = {json.dumps(jest_config, indent=2)}\n")
            f.write("module.exports = config\n")

    def _create_cypress_config(self):
        """Create Cypress configuration for e2e testing"""
        cypress_config = {
            "e2e": {
                "baseUrl": "http://localhost:3000",
                "supportFile": "cypress/support/e2e.ts",
                "specPattern": "cypress/e2e/**/*.cy.{ts,tsx}",
                "viewportWidth": 1280,
                "viewportHeight": 720,
                "video": True,
                "screenshotOnRunFailure": True,
                "defaultCommandTimeout": 10000,
                "requestTimeout": 10000,
                "responseTimeout": 10000,
                "env": {
                    "API_BASE_URL": "http://localhost:8001",
                    "TEST_USER_EMAIL": "test@fxml4.com",
                    "TEST_USER_PASSWORD": "test123",  # pragma: allowlist secret
                },
            },
            "component": {
                "devServer": {
                    "framework": "next",
                    "bundler": "webpack",
                },
                "specPattern": "src/**/*.cy.{ts,tsx}",
                "supportFile": "cypress/support/component.ts",
            },
        }

        config_path = self.project_path / "cypress.config.ts"
        with open(config_path, "w") as f:
            f.write("import { defineConfig } from 'cypress'\n\n")
            f.write(
                f"export default defineConfig({json.dumps(cypress_config, indent=2)})\n"
            )

    def _create_playwright_config(self):
        """Create Playwright configuration for cross-browser testing"""
        playwright_config = {
            "testDir": "./tests/e2e",
            "timeout": 30000,
            "expect": {"timeout": 5000},
            "fullyParallel": True,
            "forbidOnly": True,
            "retries": 2,
            "workers": 1,
            "reporter": [["html"], ["json", {"outputFile": "test-results.json"}]],
            "use": {
                "baseURL": "http://localhost:3000",
                "trace": "on-first-retry",
                "screenshot": "only-on-failure",
            },
            "projects": [
                {
                    "name": "chromium",
                    "use": {"...devices['Desktop Chrome']"},
                },
                {
                    "name": "firefox",
                    "use": {"...devices['Desktop Firefox']"},
                },
                {
                    "name": "webkit",
                    "use": {"...devices['Desktop Safari']"},
                },
                {
                    "name": "Mobile Chrome",
                    "use": {"...devices['Pixel 5']"},
                },
            ],
            "webServer": {
                "command": "npm run dev",
                "port": 3000,
                "reuseExistingServer": True,
            },
        }

        config_path = self.project_path / "playwright.config.ts"
        with open(config_path, "w") as f:
            f.write("import { defineConfig, devices } from '@playwright/test'\n\n")
            f.write(
                f"export default defineConfig({json.dumps(playwright_config, indent=2)})\n"
            )

    def _create_testing_library_setup(self):
        """Create React Testing Library setup"""
        setup_content = """
import '@testing-library/jest-dom'
import { configure } from '@testing-library/react'

// Configure Testing Library
configure({
  testIdAttribute: 'data-testid',
})

// Mock Next.js router
jest.mock('next/router', () => ({
  useRouter() {
    return {
      route: '/',
      pathname: '/',
      query: {},
      asPath: '/',
      push: jest.fn(),
      pop: jest.fn(),
      reload: jest.fn(),
      back: jest.fn(),
      prefetch: jest.fn().mockResolvedValue(undefined),
      beforePopState: jest.fn(),
      events: {
        on: jest.fn(),
        off: jest.fn(),
        emit: jest.fn(),
      },
      isFallback: false,
    }
  },
}))

// Mock window.matchMedia
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: jest.fn().mockImplementation(query => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: jest.fn(),
    removeListener: jest.fn(),
    addEventListener: jest.fn(),
    removeEventListener: jest.fn(),
    dispatchEvent: jest.fn(),
  })),
})

// Mock WebSocket for real-time trading features
global.WebSocket = jest.fn().mockImplementation(() => ({
  readyState: 1,
  send: jest.fn(),
  close: jest.fn(),
  addEventListener: jest.fn(),
  removeEventListener: jest.fn(),
}))

// Mock ResizeObserver
global.ResizeObserver = jest.fn().mockImplementation(() => ({
  observe: jest.fn(),
  unobserve: jest.fn(),
  disconnect: jest.fn(),
}))
"""

        setup_path = self.project_path / "jest.setup.js"
        with open(setup_path, "w") as f:
            f.write(setup_content.strip())

    def run_unit_tests(self) -> FrontendTestResult:
        """Run Jest unit tests"""
        try:
            print("Running frontend unit tests...")

            cmd = [
                "npm",
                "run",
                "test",
                "--",
                "--coverage",
                "--watchAll=false",
                "--passWithNoTests",
            ]
            result = subprocess.run(
                cmd,
                cwd=self.project_path,
                capture_output=True,
                text=True,
                timeout=300,
            )

            success = result.returncode == 0
            coverage = self._extract_coverage_from_output(result.stdout)

            test_result = FrontendTestResult(
                test_type="unit",
                success=success,
                execution_time=0,  # Jest doesn't provide this easily
                coverage_percentage=coverage,
                error_message=result.stderr if not success else None,
            )

            self.test_results.append(test_result)
            return test_result

        except subprocess.TimeoutExpired:
            return FrontendTestResult(
                test_type="unit",
                success=False,
                execution_time=300,
                error_message="Test execution timeout",
            )
        except Exception as e:
            return FrontendTestResult(
                test_type="unit",
                success=False,
                execution_time=0,
                error_message=str(e),
            )

    def run_e2e_tests(self, framework: str = "cypress") -> FrontendTestResult:
        """Run end-to-end tests"""
        try:
            print(f"Running {framework} e2e tests...")

            if framework == "cypress":
                cmd = ["npx", "cypress", "run", "--headless"]
            elif framework == "playwright":
                cmd = ["npx", "playwright", "test"]
            else:
                raise ValueError(f"Unsupported e2e framework: {framework}")

            result = subprocess.run(
                cmd,
                cwd=self.project_path,
                capture_output=True,
                text=True,
                timeout=600,  # 10 minutes for e2e tests
            )

            success = result.returncode == 0
            failed_tests = self._extract_failed_tests(result.stdout, framework)

            test_result = FrontendTestResult(
                test_type=f"e2e_{framework}",
                success=success,
                execution_time=0,
                failed_tests=failed_tests,
                error_message=result.stderr if not success else None,
            )

            self.test_results.append(test_result)
            return test_result

        except subprocess.TimeoutExpired:
            return FrontendTestResult(
                test_type=f"e2e_{framework}",
                success=False,
                execution_time=600,
                error_message="E2E test execution timeout",
            )
        except Exception as e:
            return FrontendTestResult(
                test_type=f"e2e_{framework}",
                success=False,
                execution_time=0,
                error_message=str(e),
            )

    def run_performance_tests(self) -> FrontendTestResult:
        """Run frontend performance tests"""
        try:
            print("Running frontend performance tests...")

            # Use Lighthouse CI for performance testing
            cmd = ["npx", "lhci", "autorun"]
            result = subprocess.run(
                cmd,
                cwd=self.project_path,
                capture_output=True,
                text=True,
                timeout=300,
            )

            success = result.returncode == 0
            performance_metrics = self._extract_lighthouse_metrics(result.stdout)

            test_result = FrontendTestResult(
                test_type="performance",
                success=success,
                execution_time=0,
                performance_metrics=performance_metrics,
                error_message=result.stderr if not success else None,
            )

            self.test_results.append(test_result)
            return test_result

        except subprocess.TimeoutExpired:
            return FrontendTestResult(
                test_type="performance",
                success=False,
                execution_time=300,
                error_message="Performance test timeout",
            )
        except Exception as e:
            return FrontendTestResult(
                test_type="performance",
                success=False,
                execution_time=0,
                error_message=str(e),
            )

    def _extract_coverage_from_output(self, output: str) -> Optional[float]:
        """Extract coverage percentage from Jest output"""
        lines = output.split("\n")
        for line in lines:
            if "All files" in line and "%" in line:
                # Extract percentage from line like "All files | 85.42 | 78.95 | 92.31 | 85.42 |"
                parts = line.split("|")
                if len(parts) > 1:
                    try:
                        return float(parts[1].strip())
                    except (ValueError, IndexError):
                        pass
        return None

    def _extract_failed_tests(self, output: str, framework: str) -> List[str]:
        """Extract failed test names from test output"""
        failed_tests = []
        lines = output.split("\n")

        if framework == "cypress":
            for line in lines:
                if "failing" in line.lower() or "failed" in line.lower():
                    failed_tests.append(line.strip())
        elif framework == "playwright":
            for line in lines:
                if "FAILED" in line or "✘" in line:
                    failed_tests.append(line.strip())

        return failed_tests

    def _extract_lighthouse_metrics(self, output: str) -> Dict[str, float]:
        """Extract Lighthouse performance metrics"""
        metrics = {}
        lines = output.split("\n")

        for line in lines:
            if "Performance" in line and "score" in line.lower():
                # Extract performance score
                try:
                    score = float(line.split()[-1])
                    metrics["performance_score"] = score
                except (ValueError, IndexError):
                    pass

        return metrics

    def run_all_frontend_tests(self) -> List[FrontendTestResult]:
        """Run all frontend test suites"""
        print("Running complete FXML4 frontend test suite...")

        results = []

        # Unit tests
        unit_result = self.run_unit_tests()
        results.append(unit_result)

        # E2E tests (Cypress)
        if self._has_cypress():
            cypress_result = self.run_e2e_tests("cypress")
            results.append(cypress_result)

        # Performance tests
        performance_result = self.run_performance_tests()
        results.append(performance_result)

        return results

    def _has_cypress(self) -> bool:
        """Check if Cypress is available"""
        try:
            subprocess.run(
                ["npx", "cypress", "--version"],
                cwd=self.project_path,
                capture_output=True,
                timeout=10,
            )
            return True
        except:
            return False

    def generate_frontend_report(self) -> str:
        """Generate comprehensive frontend testing report"""
        if not self.test_results:
            return "No frontend tests have been executed."

        report = []
        report.append("FXML4 Frontend Testing Report")
        report.append("=" * 35)
        report.append(f"Generated: {Path.cwd()}")
        report.append("")

        # Summary
        total_tests = len(self.test_results)
        successful_tests = sum(1 for r in self.test_results if r.success)
        failed_tests = total_tests - successful_tests

        report.append("SUMMARY")
        report.append("-" * 20)
        report.append(f"Total Test Suites: {total_tests}")
        report.append(f"Successful Suites: {successful_tests}")
        report.append(f"Failed Suites: {failed_tests}")
        report.append(f"Success Rate: {successful_tests/total_tests:.1%}")
        report.append("")

        # Detailed Results
        report.append("DETAILED RESULTS")
        report.append("-" * 20)

        for result in self.test_results:
            status = "✓ PASS" if result.success else "✗ FAIL"
            report.append(f"{status} {result.test_type.upper()} Tests")

            if result.coverage_percentage:
                report.append(f"      Coverage: {result.coverage_percentage:.1f}%")

            if result.performance_metrics:
                for metric, value in result.performance_metrics.items():
                    report.append(f"      {metric}: {value}")

            if result.failed_tests:
                report.append(f"      Failed Tests: {len(result.failed_tests)}")
                for failed_test in result.failed_tests[:3]:  # Show first 3
                    report.append(f"        - {failed_test}")

            if result.error_message:
                report.append(f"      Error: {result.error_message}")

        return "\n".join(report)


def main():
    """Demo usage of Next.js integration"""
    integration = NextJSIntegration()

    # Setup testing environment
    setup_success = integration.setup_frontend_testing()
    if not setup_success:
        print("Failed to set up frontend testing environment")
        return

    # Run tests (if frontend exists)
    if integration.project_path.exists():
        results = integration.run_all_frontend_tests()

        # Generate report
        report = integration.generate_frontend_report()
        print(report)

        # Save report
        with open(".claude-tdd/reports/frontend_testing.txt", "w") as f:
            f.write(report)
    else:
        print(f"Frontend directory {integration.project_path} not found")


if __name__ == "__main__":
    main()
