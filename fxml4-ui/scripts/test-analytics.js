#!/usr/bin/env node

/**
 * Analytics Test Runner Script
 *
 * Command-line script to run analytics test suite with various options
 */

const { execSync } = require('child_process');
const path = require('path');
const fs = require('fs');

// Parse command line arguments
const args = process.argv.slice(2);
const options = {
  quick: args.includes('--quick'),
  coverage: !args.includes('--no-coverage'),
  verbose: args.includes('--verbose'),
  watch: args.includes('--watch'),
  component: args.find(arg => arg.startsWith('--component='))?.split('=')[1],
  service: args.find(arg => arg.startsWith('--service='))?.split('=')[1],
  help: args.includes('--help') || args.includes('-h'),
};

function printHelp() {
  console.log(`
Analytics Test Runner

Usage: npm run test:analytics [options]

Options:
  --quick           Run quick tests without coverage
  --no-coverage     Skip coverage generation
  --verbose         Show detailed test output
  --watch          Run tests in watch mode
  --component=name  Run tests for specific component
  --service=name    Run tests for specific service
  --help, -h       Show this help message

Examples:
  npm run test:analytics                    # Run all analytics tests with coverage
  npm run test:analytics -- --quick        # Quick test run
  npm run test:analytics -- --verbose      # Verbose output
  npm run test:analytics -- --component=AnalyticsDashboard
  npm run test:analytics -- --service=analytics
  npm run test:analytics -- --watch        # Watch mode for development
`);
}

function buildJestCommand() {
  const jestArgs = [];

  // Base configuration
  jestArgs.push('--testPathPattern="(analytics|Analytics)"');

  // Coverage options
  if (options.coverage && !options.quick) {
    jestArgs.push('--coverage');
    jestArgs.push('--coverageDirectory=coverage/analytics');
    jestArgs.push('--collectCoverageFrom="src/**/*analytics*.{ts,tsx}"');
    jestArgs.push('--collectCoverageFrom="src/services/{analytics,reports,export,metricsAggregation}*.ts"');
    jestArgs.push('--collectCoverageFrom="src/components/analytics/**/*.{ts,tsx}"');
    jestArgs.push('--coverageReporters=text-summary');
    jestArgs.push('--coverageReporters=lcov');
    jestArgs.push('--coverageReporters=html');
  }

  // Verbose output
  if (options.verbose) {
    jestArgs.push('--verbose');
  }

  // Watch mode
  if (options.watch) {
    jestArgs.push('--watch');
  }

  // Component-specific tests
  if (options.component) {
    jestArgs.push(`--testNamePattern="${options.component}"`);
  }

  // Service-specific tests
  if (options.service) {
    jestArgs.push(`--testPathPattern="services/${options.service}"`);
  }

  // Quick mode optimizations
  if (options.quick) {
    jestArgs.push('--bail');
    jestArgs.push('--maxWorkers=50%');
  }

  return `npx jest ${jestArgs.join(' ')}`;
}

function runTests() {
  console.log('🚀 Starting Analytics Test Suite...\n');

  if (options.quick) {
    console.log('⚡ Quick mode: Running tests without coverage\n');
  }

  const command = buildJestCommand();

  if (options.verbose) {
    console.log(`Running command: ${command}\n`);
  }

  try {
    execSync(command, {
      stdio: 'inherit',
      cwd: process.cwd(),
      env: {
        ...process.env,
        NODE_ENV: 'test',
        CI: 'true',
      }
    });

    console.log('\n✅ Analytics tests completed successfully!');

    if (options.coverage && !options.quick) {
      console.log('📊 Coverage report generated in coverage/analytics/');
    }

    process.exit(0);

  } catch (error) {
    console.error('\n❌ Analytics tests failed!');

    if (error.status) {
      process.exit(error.status);
    } else {
      console.error(error.message);
      process.exit(1);
    }
  }
}

function validateEnvironment() {
  // Check if we're in the right directory
  if (!fs.existsSync('package.json')) {
    console.error('❌ Error: package.json not found. Please run from project root.');
    process.exit(1);
  }

  // Check if Jest is available
  try {
    execSync('npx jest --version', { stdio: 'pipe' });
  } catch (error) {
    console.error('❌ Error: Jest not found. Please install dependencies first.');
    console.error('Run: npm install');
    process.exit(1);
  }

  // Check if test files exist
  const testFiles = [
    'src/services/analytics.test.ts',
    'src/components/analytics',
    'src/test/analytics.integration.test.ts',
  ];

  const missingFiles = testFiles.filter(file => !fs.existsSync(file));
  if (missingFiles.length > 0) {
    console.warn('⚠️ Warning: Some test files are missing:');
    missingFiles.forEach(file => console.warn(`  - ${file}`));
    console.log('Continuing with available tests...\n');
  }
}

function generateTestReport() {
  const reportDir = 'test-reports';

  if (!fs.existsSync(reportDir)) {
    fs.mkdirSync(reportDir, { recursive: true });
  }

  const report = {
    timestamp: new Date().toISOString(),
    suite: 'Analytics Tests',
    command: process.argv.join(' '),
    options,
    environment: {
      node: process.version,
      platform: process.platform,
      arch: process.arch,
    },
  };

  fs.writeFileSync(
    path.join(reportDir, 'analytics-test-run.json'),
    JSON.stringify(report, null, 2)
  );
}

// Main execution
if (options.help) {
  printHelp();
  process.exit(0);
}

console.log('Analytics Test Runner\n');

// Validate environment
validateEnvironment();

// Generate test report
generateTestReport();

// Run tests
runTests();
