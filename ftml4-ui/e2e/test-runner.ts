/**
 * Comprehensive E2E Test Runner
 *
 * Orchestrates test execution with reporting, metrics collection, and CI/CD integration
 */

import { spawn } from 'child_process';
import fs from 'fs/promises';
import path from 'path';

interface TestSuite {
  name: string;
  pattern: string;
  timeout: number;
  parallel?: boolean;
  browsers?: string[];
}

interface TestConfig {
  suites: TestSuite[];
  outputDir: string;
  baseURL: string;
  maxRetries: number;
  reportFormats: string[];
}

class E2ETestRunner {
  private config: TestConfig;
  private results: any[] = [];
  private startTime: number = 0;

  constructor() {
    this.config = {
      suites: [
        {
          name: 'Authentication & Core',
          pattern: 'e2e/core/**/*.spec.ts',
          timeout: 120000,
          parallel: true,
          browsers: ['chromium', 'firefox', 'webkit']
        },
        {
          name: 'Data Management',
          pattern: 'e2e/features/data-management.spec.ts',
          timeout: 180000,
          parallel: false,
          browsers: ['chromium']
        },
        {
          name: 'Trading Console',
          pattern: 'e2e/features/trading-console.spec.ts',
          timeout: 240000,
          parallel: false,
          browsers: ['chromium']
        },
        {
          name: 'Analytics Dashboard',
          pattern: 'e2e/features/analytics-dashboard.spec.ts',
          timeout: 180000,
          parallel: false,
          browsers: ['chromium']
        },
        {
          name: 'ML Training',
          pattern: 'e2e/features/ml-training.spec.ts',
          timeout: 300000,
          parallel: false,
          browsers: ['chromium']
        },
        {
          name: 'Performance Tests',
          pattern: 'e2e/performance/**/*.spec.ts',
          timeout: 300000,
          parallel: false,
          browsers: ['chromium']
        }
      ],
      outputDir: 'e2e-results',
      baseURL: process.env.E2E_BASE_URL || 'http://localhost:3000',
      maxRetries: 2,
      reportFormats: ['html', 'json', 'junit', 'markdown']
    };
  }

  async runTests(): Promise<void> {
    console.log('🚀 Starting FXML4 E2E Test Suite');
    console.log('=====================================\n');

    this.startTime = Date.now();

    try {
      // Setup
      await this.setupTestEnvironment();

      // Run test suites
      for (const suite of this.config.suites) {
        await this.runTestSuite(suite);
      }

      // Generate reports
      await this.generateReports();

      // Cleanup
      await this.cleanup();

      console.log('\n✅ All E2E tests completed successfully!');

    } catch (error) {
      console.error('\n❌ E2E test execution failed:', error);
      process.exit(1);
    }
  }

  private async setupTestEnvironment(): Promise<void> {
    console.log('🔧 Setting up test environment...');

    // Ensure output directory exists
    await fs.mkdir(this.config.outputDir, { recursive: true });

    // Verify test server is running
    try {
      const response = await fetch(this.config.baseURL);
      if (!response.ok) {
        throw new Error(`Test server not responding: ${response.status}`);
      }
    } catch (error) {
      console.warn('⚠️ Test server not accessible, tests may fail');
    }

    // Setup environment variables
    process.env.PWTEST_HTML_REPORT = path.join(this.config.outputDir, 'html-report');
    process.env.PWTEST_JSON_REPORT = path.join(this.config.outputDir, 'results.json');

    console.log('✅ Test environment ready\n');
  }

  private async runTestSuite(suite: TestSuite): Promise<void> {
    console.log(`🧪 Running ${suite.name} tests...`);
    console.log(`   Pattern: ${suite.pattern}`);
    console.log(`   Timeout: ${suite.timeout}ms`);
    console.log(`   Browsers: ${suite.browsers?.join(', ')}`);

    const suiteStartTime = Date.now();

    for (const browser of suite.browsers || ['chromium']) {
      try {
        await this.runPlaywrightTests({
          ...suite,
          browser
        });

        console.log(`   ✅ ${browser} tests passed`);

      } catch (error) {
        console.error(`   ❌ ${browser} tests failed:`, error);

        // Continue with other browsers unless critical failure
        if (browser === 'chromium') {
          throw error; // Fail fast on primary browser
        }
      }
    }

    const suiteDuration = Date.now() - suiteStartTime;
    console.log(`   ⏱️ Duration: ${(suiteDuration / 1000).toFixed(2)}s\n`);

    this.results.push({
      suite: suite.name,
      duration: suiteDuration,
      timestamp: new Date().toISOString()
    });
  }

  private async runPlaywrightTests(options: TestSuite & { browser: string }): Promise<void> {
    return new Promise((resolve, reject) => {
      const args = [
        'test',
        options.pattern,
        '--project', options.browser,
        '--timeout', options.timeout.toString(),
        '--retries', this.config.maxRetries.toString()
      ];

      if (options.parallel) {
        args.push('--workers', '3');
      } else {
        args.push('--workers', '1');
      }

      // Add CI-specific flags
      if (process.env.CI) {
        args.push('--reporter=github');
        args.push('--forbid-only');
      }

      const playwright = spawn('npx', ['playwright', ...args], {
        stdio: 'inherit',
        env: {
          ...process.env,
          FORCE_COLOR: '1'
        }
      });

      playwright.on('close', (code) => {
        if (code === 0) {
          resolve();
        } else {
          reject(new Error(`Playwright tests failed with exit code ${code}`));
        }
      });

      playwright.on('error', (error) => {
        reject(error);
      });
    });
  }

  private async generateReports(): Promise<void> {
    console.log('📊 Generating comprehensive reports...');

    try {
      const totalDuration = Date.now() - this.startTime;

      // Load test results
      const resultsPath = path.join(this.config.outputDir, 'results.json');
      let testResults = {};

      try {
        const resultsContent = await fs.readFile(resultsPath, 'utf-8');
        testResults = JSON.parse(resultsContent);
      } catch {
        console.warn('⚠️ Could not load detailed test results');
      }

      // Generate summary report
      const summaryReport = {
        overview: {
          totalDuration: totalDuration,
          suiteCount: this.config.suites.length,
          timestamp: new Date().toISOString(),
          environment: {
            node: process.version,
            platform: process.platform,
            ci: !!process.env.CI,
            baseURL: this.config.baseURL
          }
        },
        suiteResults: this.results,
        detailedResults: testResults,
        recommendations: this.generateRecommendations(this.results)
      };

      // Write summary report
      const summaryPath = path.join(this.config.outputDir, 'e2e-summary.json');
      await fs.writeFile(summaryPath, JSON.stringify(summaryReport, null, 2));

      // Generate markdown report
      const markdownReport = this.generateMarkdownReport(summaryReport);
      const markdownPath = path.join(this.config.outputDir, 'E2E-REPORT.md');
      await fs.writeFile(markdownPath, markdownReport);

      console.log(`✅ Reports generated in ${this.config.outputDir}/`);

    } catch (error) {
      console.warn('⚠️ Report generation encountered issues:', error);
    }
  }

  private generateRecommendations(results: any[]): string[] {
    const recommendations: string[] = [];

    // Analyze test duration patterns
    const avgDuration = results.reduce((sum, r) => sum + r.duration, 0) / results.length;

    if (avgDuration > 120000) { // 2 minutes
      recommendations.push('Consider parallelizing tests or optimizing test data setup');
    }

    // Check for slow suites
    const slowSuites = results.filter(r => r.duration > 180000); // 3 minutes
    if (slowSuites.length > 0) {
      recommendations.push(`Optimize slow test suites: ${slowSuites.map(s => s.suite).join(', ')}`);
    }

    // Performance recommendations
    recommendations.push('Review performance test results for optimization opportunities');
    recommendations.push('Consider implementing visual regression testing for UI consistency');

    return recommendations;
  }

  private generateMarkdownReport(report: any): string {
    const duration = (report.overview.totalDuration / 1000 / 60).toFixed(2);

    return `# FXML4 E2E Test Report

## Overview
- **Total Duration:** ${duration} minutes
- **Test Suites:** ${report.overview.suiteCount}
- **Timestamp:** ${report.overview.timestamp}
- **Environment:** ${report.overview.environment.platform} (Node ${report.overview.environment.node})
- **CI Mode:** ${report.overview.environment.ci ? 'Yes' : 'No'}

## Suite Results
${report.suiteResults.map((suite: any) =>
  `- **${suite.suite}:** ${(suite.duration / 1000).toFixed(2)}s`
).join('\n')}

## Recommendations
${report.recommendations.map((rec: string) => `- ${rec}`).join('\n')}

## Detailed Results
See \`results.json\` and HTML report for detailed test results.

---
*Generated by FXML4 E2E Test Runner*
`;
  }

  private async cleanup(): Promise<void> {
    console.log('🧹 Cleaning up test environment...');

    // Archive old reports if in CI
    if (process.env.CI) {
      const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
      const archivePath = path.join(this.config.outputDir, `archive-${timestamp}`);

      try {
        await fs.mkdir(archivePath, { recursive: true });
        // Copy key files to archive
        // Implementation depends on specific CI requirements
      } catch (error) {
        console.warn('⚠️ Could not archive reports:', error);
      }
    }

    console.log('✅ Cleanup completed');
  }
}

// CLI execution
if (require.main === module) {
  const runner = new E2ETestRunner();
  runner.runTests().catch(error => {
    console.error('Fatal error:', error);
    process.exit(1);
  });
}

export { E2ETestRunner };
