#!/usr/bin/env node

/**
 * Test Coverage Reporter
 *
 * Runs tests with coverage reporting and generates detailed reports
 */

const { execSync, spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

const COVERAGE_DIR = path.join(process.cwd(), 'coverage');
const REPORTS_DIR = path.join(process.cwd(), 'test-reports');

// Colors for console output
const colors = {
  reset: '\x1b[0m',
  bright: '\x1b[1m',
  red: '\x1b[31m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
  magenta: '\x1b[35m',
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

function logInfo(message) {
  log(`ℹ️  ${message}`, 'blue');
}

function ensureDirectories() {
  [COVERAGE_DIR, REPORTS_DIR].forEach(dir => {
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
      logInfo(`Created directory: ${dir}`);
    }
  });
}

async function runTests(options = {}) {
  logStep('Running test suite with coverage...');

  const jestArgs = [
    '--coverage',
    '--coverageDirectory=coverage',
    '--coverageReporters=text',
    '--coverageReporters=html',
    '--coverageReporters=lcov',
    '--coverageReporters=json',
    '--coverageReporters=json-summary',
    '--verbose',
  ];

  // Add specific test patterns if provided
  if (options.testPattern) {
    jestArgs.push(`--testNamePattern=${options.testPattern}`);
  }

  if (options.testFiles) {
    jestArgs.push(options.testFiles);
  }

  // Add component-specific coverage thresholds
  if (options.component) {
    const componentPath = `./src/components/${options.component}/`;
    jestArgs.push(`--collectCoverageFrom=${componentPath}**/*.{ts,tsx}`);
  }

  try {
    const result = execSync(`npx jest ${jestArgs.join(' ')}`, {
      stdio: 'inherit',
      encoding: 'utf-8',
    });

    logSuccess('Test suite completed successfully');
    return true;
  } catch (error) {
    if (error.status === 1) {
      // Tests failed but coverage was still generated
      logWarning('Some tests failed, but coverage report was generated');
      return false;
    } else {
      logError(`Test execution failed: ${error.message}`);
      throw error;
    }
  }
}

function parseCoverageSummary() {
  const summaryPath = path.join(COVERAGE_DIR, 'coverage-summary.json');

  if (!fs.existsSync(summaryPath)) {
    logWarning('Coverage summary not found');
    return null;
  }

  try {
    const summary = JSON.parse(fs.readFileSync(summaryPath, 'utf8'));
    return summary;
  } catch (error) {
    logError(`Failed to parse coverage summary: ${error.message}`);
    return null;
  }
}

function displayCoverageSummary(summary) {
  if (!summary) return;

  logStep('Coverage Summary');

  const { total } = summary;

  const metrics = [
    { name: 'Lines', data: total.lines },
    { name: 'Functions', data: total.functions },
    { name: 'Branches', data: total.branches },
    { name: 'Statements', data: total.statements },
  ];

  console.table(
    metrics.reduce((acc, metric) => {
      const { pct, covered, total } = metric.data;
      const color = pct >= 80 ? 'green' : pct >= 60 ? 'yellow' : 'red';

      acc[metric.name] = {
        'Coverage %': `${colors[color]}${pct}%${colors.reset}`,
        'Covered': covered,
        'Total': total,
        'Uncovered': total - covered,
      };

      return acc;
    }, {})
  );
}

function analyzeComponentCoverage(summary) {
  if (!summary) return;

  logStep('Component Coverage Analysis');

  // Group by component directories
  const componentCoverage = {};

  Object.entries(summary).forEach(([filePath, data]) => {
    if (filePath === 'total') return;

    const match = filePath.match(/src\/components\/([^\/]+)/);
    if (match) {
      const component = match[1];
      if (!componentCoverage[component]) {
        componentCoverage[component] = {
          files: 0,
          lines: { covered: 0, total: 0 },
          functions: { covered: 0, total: 0 },
          branches: { covered: 0, total: 0 },
          statements: { covered: 0, total: 0 },
        };
      }

      componentCoverage[component].files++;
      ['lines', 'functions', 'branches', 'statements'].forEach(metric => {
        componentCoverage[component][metric].covered += data[metric].covered;
        componentCoverage[component][metric].total += data[metric].total;
      });
    }
  });

  // Calculate percentages and display
  Object.entries(componentCoverage).forEach(([component, data]) => {
    const linesPct = ((data.lines.covered / data.lines.total) * 100).toFixed(1);
    const functionsPct = ((data.functions.covered / data.functions.total) * 100).toFixed(1);
    const branchesPct = ((data.branches.covered / data.branches.total) * 100).toFixed(1);

    const avgCoverage = ((+linesPct + +functionsPct + +branchesPct) / 3).toFixed(1);
    const color = avgCoverage >= 80 ? 'green' : avgCoverage >= 60 ? 'yellow' : 'red';

    log(`${component}: ${colors[color]}${avgCoverage}%${colors.reset} (${data.files} files)`);
  });
}

function checkCoverageThresholds(summary) {
  if (!summary) return false;

  logStep('Checking Coverage Thresholds');

  const thresholds = {
    global: { lines: 80, functions: 80, branches: 80, statements: 80 },
    trading: { lines: 90, functions: 90, branches: 90, statements: 90 },
    services: { lines: 85, functions: 85, branches: 85, statements: 85 },
  };

  let allPassed = true;
  const { total } = summary;

  // Check global thresholds
  Object.entries(thresholds.global).forEach(([metric, threshold]) => {
    const actual = total[metric].pct;
    const passed = actual >= threshold;
    allPassed = allPassed && passed;

    const status = passed ? '✅' : '❌';
    const color = passed ? 'green' : 'red';

    log(`${status} Global ${metric}: ${colors[color]}${actual}%${colors.reset} (threshold: ${threshold}%)`);
  });

  // Check component-specific thresholds
  Object.entries(summary).forEach(([filePath, data]) => {
    let componentThreshold = thresholds.global;

    if (filePath.includes('components/trading/')) {
      componentThreshold = thresholds.trading;
    } else if (filePath.includes('services/')) {
      componentThreshold = thresholds.services;
    }

    Object.entries(componentThreshold).forEach(([metric, threshold]) => {
      if (data[metric] && data[metric].pct < threshold) {
        allPassed = false;
        logWarning(`${filePath} ${metric}: ${data[metric].pct}% < ${threshold}%`);
      }
    });
  });

  return allPassed;
}

function generateReports() {
  logStep('Generating additional reports');

  // Generate badge data
  const summaryPath = path.join(COVERAGE_DIR, 'coverage-summary.json');
  if (fs.existsSync(summaryPath)) {
    const summary = JSON.parse(fs.readFileSync(summaryPath, 'utf8'));
    const coverage = summary.total.lines.pct;

    const badgeColor = coverage >= 80 ? 'brightgreen' : coverage >= 60 ? 'yellow' : 'red';
    const badgeData = {
      schemaVersion: 1,
      label: 'coverage',
      message: `${coverage}%`,
      color: badgeColor,
    };

    fs.writeFileSync(
      path.join(REPORTS_DIR, 'coverage-badge.json'),
      JSON.stringify(badgeData, null, 2)
    );

    logSuccess(`Coverage badge data generated: ${coverage}%`);
  }

  // Copy HTML report to reports directory
  const htmlReportSrc = path.join(COVERAGE_DIR, 'lcov-report');
  const htmlReportDest = path.join(REPORTS_DIR, 'coverage-html');

  if (fs.existsSync(htmlReportSrc)) {
    execSync(`cp -r "${htmlReportSrc}" "${htmlReportDest}"`);
    logSuccess(`HTML coverage report copied to ${htmlReportDest}`);
    logInfo(`Open ${htmlReportDest}/index.html in your browser to view the report`);
  }
}

async function main() {
  const args = process.argv.slice(2);
  const options = {};

  // Parse command line arguments
  for (let i = 0; i < args.length; i++) {
    switch (args[i]) {
      case '--component':
        options.component = args[++i];
        break;
      case '--pattern':
        options.testPattern = args[++i];
        break;
      case '--files':
        options.testFiles = args[++i];
        break;
      case '--help':
        console.log(`
Usage: npm run test:coverage [options]

Options:
  --component <name>    Focus on specific component
  --pattern <pattern>   Run tests matching pattern
  --files <glob>        Run specific test files
  --help               Show this help

Examples:
  npm run test:coverage
  npm run test:coverage -- --component trading
  npm run test:coverage -- --pattern "should render"
  npm run test:coverage -- --files "src/components/trading/**/*.test.tsx"
        `);
        return;
    }
  }

  try {
    log('🧪 FXML4 Test Coverage Reporter', 'bright');
    log('=====================================', 'bright');

    ensureDirectories();

    const testsSucceeded = await runTests(options);
    const summary = parseCoverageSummary();

    displayCoverageSummary(summary);
    analyzeComponentCoverage(summary);

    const thresholdsPassed = checkCoverageThresholds(summary);

    generateReports();

    log('\n📊 Coverage Analysis Complete', 'bright');

    if (testsSucceeded && thresholdsPassed) {
      logSuccess('All tests passed and coverage thresholds met!');
      process.exit(0);
    } else if (!testsSucceeded && thresholdsPassed) {
      logWarning('Tests failed but coverage thresholds met');
      process.exit(1);
    } else if (testsSucceeded && !thresholdsPassed) {
      logWarning('Tests passed but coverage thresholds not met');
      process.exit(1);
    } else {
      logError('Tests failed and coverage thresholds not met');
      process.exit(1);
    }

  } catch (error) {
    logError(`Coverage analysis failed: ${error.message}`);
    process.exit(1);
  }
}

if (require.main === module) {
  main();
}

module.exports = {
  runTests,
  parseCoverageSummary,
  displayCoverageSummary,
  checkCoverageThresholds,
  generateReports,
};
