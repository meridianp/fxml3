#!/usr/bin/env node

/**
 * Comprehensive Test Runner
 *
 * Runs all test types with proper organization and reporting
 */

const { execSync, spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

// Colors for console output
const colors = {
  reset: '\x1b[0m',
  bright: '\x1b[1m',
  red: '\x1b[31m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
  cyan: '\x1b[36m',
};

function log(message, color = 'reset') {
  console.log(`${colors[color]}${message}${colors.reset}`);
}

function logStep(step) {
  log(`\n🔍 ${step}`, 'cyan');
}

function logSuccess(message) {
  log(`✅ ${message}`, 'green');
}

function logError(message) {
  log(`❌ ${message}`, 'red');
}

function logWarning(message) {
  log(`⚠️  ${message}`, 'yellow');
}

class TestRunner {
  constructor() {
    this.results = {
      unit: { passed: false, duration: 0 },
      integration: { passed: false, duration: 0 },
      component: { passed: false, duration: 0 },
      coverage: { passed: false, percentage: 0 },
    };

    this.startTime = Date.now();
  }

  async runUnitTests() {
    logStep('Running Unit Tests');

    try {
      const startTime = Date.now();

      execSync('npx jest src/**/__tests__/**/*.test.ts --testNamePattern="^((?!integration).)*$"', {
        stdio: 'inherit',
        encoding: 'utf-8',
      });

      this.results.unit.passed = true;
      this.results.unit.duration = Date.now() - startTime;
      logSuccess(`Unit tests completed in ${this.results.unit.duration}ms`);

    } catch (error) {
      this.results.unit.passed = false;
      logError('Unit tests failed');

      if (process.env.CI !== 'true') {
        throw error;
      }
    }
  }

  async runIntegrationTests() {
    logStep('Running Integration Tests');

    try {
      const startTime = Date.now();

      execSync('npx jest src/**/__tests__/**/*.integration.test.ts', {
        stdio: 'inherit',
        encoding: 'utf-8',
      });

      this.results.integration.passed = true;
      this.results.integration.duration = Date.now() - startTime;
      logSuccess(`Integration tests completed in ${this.results.integration.duration}ms`);

    } catch (error) {
      this.results.integration.passed = false;
      logError('Integration tests failed');

      if (process.env.CI !== 'true') {
        throw error;
      }
    }
  }

  async runComponentTests() {
    logStep('Running Component Tests');

    try {
      const startTime = Date.now();

      execSync('npx jest src/components/**/__tests__/**/*.test.tsx', {
        stdio: 'inherit',
        encoding: 'utf-8',
      });

      this.results.component.passed = true;
      this.results.component.duration = Date.now() - startTime;
      logSuccess(`Component tests completed in ${this.results.component.duration}ms`);

    } catch (error) {
      this.results.component.passed = false;
      logError('Component tests failed');

      if (process.env.CI !== 'true') {
        throw error;
      }
    }
  }

  async runCoverageAnalysis() {
    logStep('Running Coverage Analysis');

    try {
      const startTime = Date.now();

      execSync('npx jest --coverage --coverageReporters=json-summary --silent', {
        stdio: 'pipe',
        encoding: 'utf-8',
      });

      // Parse coverage results
      const summaryPath = path.join(process.cwd(), 'coverage', 'coverage-summary.json');
      if (fs.existsSync(summaryPath)) {
        const summary = JSON.parse(fs.readFileSync(summaryPath, 'utf8'));
        this.results.coverage.percentage = summary.total.lines.pct;
        this.results.coverage.passed = summary.total.lines.pct >= 80; // 80% threshold
      }

      this.results.coverage.duration = Date.now() - startTime;

      if (this.results.coverage.passed) {
        logSuccess(`Coverage analysis completed: ${this.results.coverage.percentage}%`);
      } else {
        logWarning(`Coverage below threshold: ${this.results.coverage.percentage}% < 80%`);
      }

    } catch (error) {
      this.results.coverage.passed = false;
      logError('Coverage analysis failed');
    }
  }

  async runLinting() {
    logStep('Running Code Linting');

    try {
      execSync('npm run lint', {
        stdio: 'inherit',
        encoding: 'utf-8',
      });

      logSuccess('Linting passed');
      return true;

    } catch (error) {
      logError('Linting failed');
      return false;
    }
  }

  async runTypeChecking() {
    logStep('Running Type Checking');

    try {
      execSync('npm run type-check', {
        stdio: 'inherit',
        encoding: 'utf-8',
      });

      logSuccess('Type checking passed');
      return true;

    } catch (error) {
      logError('Type checking failed');
      return false;
    }
  }

  generateReport() {
    logStep('Test Report Summary');

    const totalDuration = Date.now() - this.startTime;

    log('\n📊 Test Results:', 'bright');
    console.table({
      'Unit Tests': {
        Status: this.results.unit.passed ? '✅ PASS' : '❌ FAIL',
        Duration: `${this.results.unit.duration}ms`,
      },
      'Integration Tests': {
        Status: this.results.integration.passed ? '✅ PASS' : '❌ FAIL',
        Duration: `${this.results.integration.duration}ms`,
      },
      'Component Tests': {
        Status: this.results.component.passed ? '✅ PASS' : '❌ FAIL',
        Duration: `${this.results.component.duration}ms`,
      },
      'Coverage': {
        Status: this.results.coverage.passed ? '✅ PASS' : '❌ FAIL',
        Duration: `${this.results.coverage.percentage}%`,
      },
    });

    const allPassed = Object.values(this.results).every(result => result.passed);

    log(`\n⏱️  Total Duration: ${totalDuration}ms`, 'blue');

    if (allPassed) {
      logSuccess('🎉 All tests passed!');
    } else {
      logError('❌ Some tests failed');
    }

    return allPassed;
  }

  async saveReportToFile() {
    const report = {
      timestamp: new Date().toISOString(),
      results: this.results,
      totalDuration: Date.now() - this.startTime,
      passed: Object.values(this.results).every(result => result.passed),
    };

    const reportsDir = path.join(process.cwd(), 'test-reports');
    if (!fs.existsSync(reportsDir)) {
      fs.mkdirSync(reportsDir, { recursive: true });
    }

    const reportPath = path.join(reportsDir, 'test-results.json');
    fs.writeFileSync(reportPath, JSON.stringify(report, null, 2));

    logSuccess(`Test report saved to ${reportPath}`);
  }
}

async function main() {
  const args = process.argv.slice(2);
  const options = {
    skipLint: args.includes('--skip-lint'),
    skipTypeCheck: args.includes('--skip-type-check'),
    coverage: args.includes('--coverage'),
    ci: process.env.CI === 'true',
  };

  if (args.includes('--help')) {
    console.log(`
Usage: npm run test:all [options]

Options:
  --skip-lint         Skip ESLint
  --skip-type-check   Skip TypeScript type checking
  --coverage          Include coverage analysis
  --help              Show this help

Examples:
  npm run test:all
  npm run test:all -- --coverage
  npm run test:all -- --skip-lint --skip-type-check
    `);
    return;
  }

  const runner = new TestRunner();

  try {
    log('🧪 FXML4 Comprehensive Test Suite', 'bright');
    log('==================================', 'bright');

    // Pre-test validation
    if (!options.skipLint) {
      await runner.runLinting();
    }

    if (!options.skipTypeCheck) {
      await runner.runTypeChecking();
    }

    // Core test suites
    await runner.runUnitTests();
    await runner.runComponentTests();
    await runner.runIntegrationTests();

    // Coverage analysis
    if (options.coverage) {
      await runner.runCoverageAnalysis();
    }

    // Generate and save report
    const allPassed = runner.generateReport();
    await runner.saveReportToFile();

    // Exit with appropriate code
    if (allPassed) {
      log('\n🎉 All tests completed successfully!', 'green');
      process.exit(0);
    } else {
      log('\n❌ Test suite failed', 'red');
      process.exit(1);
    }

  } catch (error) {
    logError(`Test execution failed: ${error.message}`);
    process.exit(1);
  }
}

if (require.main === module) {
  main();
}

module.exports = { TestRunner };
