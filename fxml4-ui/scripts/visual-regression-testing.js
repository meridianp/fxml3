#!/usr/bin/env node

/**
 * Visual Regression Testing Orchestrator
 *
 * Manages visual regression testing across multiple browsers and viewports
 */

const { spawn } = require('child_process');
const fs = require('fs/promises');
const path = require('path');

class VisualRegressionTestRunner {
  constructor() {
    this.config = {
      outputDir: 'e2e-results/visual',
      baselineDir: 'e2e/visual/baselines',
      diffDir: 'e2e-results/visual/diffs',
      reportsDir: 'e2e-results/visual/reports',
      browsers: ['chromium', 'firefox', 'webkit'],
      testCategories: ['smoke', 'regression', 'comprehensive'],
      updateBaselines: process.env.UPDATE_VISUAL_BASELINES === 'true',
      threshold: parseFloat(process.env.VISUAL_THRESHOLD) || 0.2
    };

    this.results = {
      summary: {
        total: 0,
        passed: 0,
        failed: 0,
        updated: 0,
        startTime: new Date(),
        endTime: null
      },
      tests: [],
      diffs: [],
      errors: []
    };
  }

  async run() {
    console.log('📸 Starting Visual Regression Testing');
    console.log('=====================================\n');

    try {
      // Setup
      await this.setup();

      // Run visual tests by category
      await this.runVisualTests();

      // Process results
      await this.processResults();

      // Generate reports
      await this.generateReports();

      console.log('\n✅ Visual regression testing completed successfully!');
      console.log(`📊 Results: ${this.results.summary.passed} passed, ${this.results.summary.failed} failed`);
      console.log(`📁 Reports saved to: ${this.config.reportsDir}`);

    } catch (error) {
      console.error('\n❌ Visual regression testing failed:', error);
      process.exit(1);
    }
  }

  async setup() {
    console.log('🔧 Setting up visual regression testing environment...');

    // Create output directories
    await Promise.all([
      fs.mkdir(this.config.outputDir, { recursive: true }),
      fs.mkdir(this.config.baselineDir, { recursive: true }),
      fs.mkdir(this.config.diffDir, { recursive: true }),
      fs.mkdir(this.config.reportsDir, { recursive: true })
    ]);

    // Install Playwright browsers
    try {
      await this.runCommand('npx', ['playwright', 'install', '--with-deps']);
      console.log('✅ Playwright browsers verified');
    } catch (error) {
      console.warn('⚠️ Browser installation check failed:', error.message);
    }

    // Clear previous results
    await this.clearPreviousResults();

    console.log('✅ Setup completed\n');
  }

  async clearPreviousResults() {
    try {
      const resultFiles = await fs.readdir(this.config.outputDir);
      await Promise.all(
        resultFiles.map(file =>
          fs.unlink(path.join(this.config.outputDir, file)).catch(() => {})
        )
      );

      const diffFiles = await fs.readdir(this.config.diffDir);
      await Promise.all(
        diffFiles.map(file =>
          fs.unlink(path.join(this.config.diffDir, file)).catch(() => {})
        )
      );
    } catch (error) {
      // Directory might not exist, ignore
    }
  }

  async runVisualTests() {
    console.log('📸 Running visual regression tests...\n');

    const testCategories = this.getTestCategories();

    for (const category of testCategories) {
      console.log(`\n🔍 Running ${category} visual tests...`);
      await this.runTestCategory(category);
    }
  }

  getTestCategories() {
    const requestedCategory = process.env.VISUAL_TEST_CATEGORY;

    if (requestedCategory && this.config.testCategories.includes(requestedCategory)) {
      return [requestedCategory];
    }

    // Default based on environment
    if (process.env.CI) {
      return ['smoke', 'regression'];
    }

    return ['comprehensive'];
  }

  async runTestCategory(category) {
    const testPromises = this.config.browsers.map(async (browser) => {
      console.log(`\n🌐 Testing ${category} on ${browser}...`);

      try {
        const startTime = Date.now();

        // Run visual tests for this browser and category
        const output = await this.runPlaywrightVisualTests({
          browser,
          category,
          updateBaselines: this.config.updateBaselines,
          threshold: this.config.threshold
        });

        const duration = Date.now() - startTime;

        this.results.tests.push({
          category,
          browser,
          status: 'passed',
          duration,
          timestamp: new Date().toISOString(),
          output
        });

        this.results.summary.passed++;
        console.log(`✅ ${category} tests on ${browser} completed in ${(duration/1000).toFixed(2)}s`);

      } catch (error) {
        this.results.tests.push({
          category,
          browser,
          status: 'failed',
          error: error.message,
          timestamp: new Date().toISOString()
        });

        this.results.summary.failed++;
        this.results.errors.push({
          category,
          browser,
          error: error.message,
          timestamp: new Date().toISOString()
        });

        console.error(`❌ ${category} tests on ${browser} failed:`, error.message);
      }

      this.results.summary.total++;
    });

    await Promise.allSettled(testPromises);
  }

  async runPlaywrightVisualTests(options) {
    const args = [
      'test',
      'e2e/visual/visual-regression.spec.ts',
      '--project', options.browser,
      '--timeout', '120000'
    ];

    // Add environment variables
    const env = {
      ...process.env,
      VISUAL_TEST_CATEGORY: options.category,
      VISUAL_THRESHOLD: options.threshold.toString(),
      UPDATE_VISUAL_BASELINES: options.updateBaselines ? 'true' : 'false'
    };

    if (process.env.CI) {
      args.push('--reporter=github');
    }

    return this.runCommand('npx', ['playwright', ...args], { env });
  }

  async processResults() {
    console.log('\n📊 Processing visual test results...');

    this.results.summary.endTime = new Date();

    // Scan for diff images
    await this.scanForDiffs();

    // Analyze baseline updates
    if (this.config.updateBaselines) {
      await this.analyzeBaselineUpdates();
    }

    // Calculate statistics
    this.calculateStatistics();
  }

  async scanForDiffs() {
    try {
      const files = await fs.readdir(this.config.diffDir);
      const diffImages = files.filter(file =>
        file.endsWith('.png') && file.includes('-diff-')
      );

      this.results.diffs = diffImages.map(file => ({
        filename: file,
        path: path.join(this.config.diffDir, file),
        size: 0, // Would calculate actual file size
        timestamp: new Date().toISOString()
      }));

      console.log(`📸 Found ${diffImages.length} visual differences`);
    } catch (error) {
      console.warn('⚠️ Could not scan for diffs:', error.message);
    }
  }

  async analyzeBaselineUpdates() {
    try {
      const files = await fs.readdir(this.config.baselineDir);
      const recentFiles = [];

      const oneDayAgo = Date.now() - (24 * 60 * 60 * 1000);

      for (const file of files) {
        const filePath = path.join(this.config.baselineDir, file);
        const stats = await fs.stat(filePath);

        if (stats.mtime.getTime() > oneDayAgo) {
          recentFiles.push({
            filename: file,
            path: filePath,
            updated: stats.mtime.toISOString()
          });
        }
      }

      this.results.summary.updated = recentFiles.length;
      this.results.baselineUpdates = recentFiles;

      console.log(`🔄 Updated ${recentFiles.length} baseline images`);
    } catch (error) {
      console.warn('⚠️ Could not analyze baseline updates:', error.message);
    }
  }

  calculateStatistics() {
    const totalDuration = this.results.summary.endTime - this.results.summary.startTime;
    const avgDuration = this.results.tests.length > 0 ?
      this.results.tests.reduce((sum, test) => sum + (test.duration || 0), 0) / this.results.tests.length : 0;

    this.results.summary.totalDuration = totalDuration;
    this.results.summary.avgTestDuration = avgDuration;
    this.results.summary.successRate = this.results.summary.total > 0 ?
      (this.results.summary.passed / this.results.summary.total) * 100 : 0;
  }

  async generateReports() {
    console.log('📄 Generating visual regression reports...');

    // Generate JSON report
    await this.generateJSONReport();

    // Generate HTML report
    await this.generateHTMLReport();

    // Generate markdown summary
    await this.generateMarkdownReport();

    // Generate CI summary
    await this.generateCISummary();

    console.log('✅ Reports generated successfully');
  }

  async generateJSONReport() {
    const report = {
      summary: this.results.summary,
      config: {
        browsers: this.config.browsers,
        threshold: this.config.threshold,
        updateBaselines: this.config.updateBaselines,
        environment: process.env.NODE_ENV || 'test'
      },
      tests: this.results.tests,
      diffs: this.results.diffs,
      errors: this.results.errors,
      baselineUpdates: this.results.baselineUpdates || [],
      metadata: {
        playwrightVersion: await this.getPlaywrightVersion(),
        nodeVersion: process.version,
        timestamp: new Date().toISOString()
      }
    };

    await fs.writeFile(
      path.join(this.config.reportsDir, 'visual-regression-report.json'),
      JSON.stringify(report, null, 2)
    );
  }

  async generateHTMLReport() {
    const html = `
<!DOCTYPE html>
<html>
<head>
    <title>FXML4 Visual Regression Test Report</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; line-height: 1.6; }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
        .summary { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin: 20px 0; }
        .metric { background: #f8f9fa; padding: 20px; border-radius: 8px; text-align: center; }
        .metric-value { font-size: 2em; font-weight: bold; color: #007acc; }
        .metric-label { color: #666; margin-top: 5px; }
        .section { margin: 30px 0; }
        .test-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 15px; }
        .test-card { background: #f8f9fa; padding: 15px; border-radius: 8px; border-left: 4px solid #007acc; }
        .test-passed { border-left-color: #28a745; }
        .test-failed { border-left-color: #dc3545; }
        .diff-gallery { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; }
        .diff-item { background: #f8f9fa; padding: 15px; border-radius: 8px; }
        .diff-image { width: 100%; height: 200px; object-fit: contain; border: 1px solid #ddd; }
        table { width: 100%; border-collapse: collapse; margin: 20px 0; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background-color: #f2f2f2; }
        .status-passed { color: #28a745; font-weight: bold; }
        .status-failed { color: #dc3545; font-weight: bold; }
    </style>
</head>
<body>
    <div class="header">
        <h1>FXML4 Visual Regression Test Report</h1>
        <p>Generated on ${this.results.summary.endTime.toISOString()}</p>
    </div>

    <div class="summary">
        <div class="metric">
            <div class="metric-value">${this.results.summary.total}</div>
            <div class="metric-label">Total Tests</div>
        </div>
        <div class="metric">
            <div class="metric-value" style="color: #28a745">${this.results.summary.passed}</div>
            <div class="metric-label">Passed</div>
        </div>
        <div class="metric">
            <div class="metric-value" style="color: #dc3545">${this.results.summary.failed}</div>
            <div class="metric-label">Failed</div>
        </div>
        <div class="metric">
            <div class="metric-value">${this.results.summary.successRate.toFixed(1)}%</div>
            <div class="metric-label">Success Rate</div>
        </div>
        <div class="metric">
            <div class="metric-value">${this.results.diffs.length}</div>
            <div class="metric-label">Visual Diffs</div>
        </div>
        <div class="metric">
            <div class="metric-value">${this.results.summary.updated || 0}</div>
            <div class="metric-label">Baselines Updated</div>
        </div>
    </div>

    <div class="section">
        <h2>Test Results</h2>
        <div class="test-grid">
            ${this.results.tests.map(test => `
                <div class="test-card test-${test.status}">
                    <h4>${test.category} - ${test.browser}</h4>
                    <p><strong>Status:</strong> <span class="status-${test.status}">${test.status}</span></p>
                    <p><strong>Duration:</strong> ${test.duration ? (test.duration/1000).toFixed(2) + 's' : 'N/A'}</p>
                    ${test.error ? `<p><strong>Error:</strong> ${test.error}</p>` : ''}
                </div>
            `).join('')}
        </div>
    </div>

    ${this.results.diffs.length > 0 ? `
    <div class="section">
        <h2>Visual Differences (${this.results.diffs.length})</h2>
        <div class="diff-gallery">
            ${this.results.diffs.map(diff => `
                <div class="diff-item">
                    <h4>${diff.filename}</h4>
                    <img src="${diff.path}" alt="Visual diff" class="diff-image" loading="lazy">
                    <p><small>Generated: ${diff.timestamp}</small></p>
                </div>
            `).join('')}
        </div>
    </div>
    ` : ''}

    <div class="section">
        <h2>Configuration</h2>
        <table>
            <tr><th>Setting</th><th>Value</th></tr>
            <tr><td>Browsers</td><td>${this.config.browsers.join(', ')}</td></tr>
            <tr><td>Threshold</td><td>${this.config.threshold}</td></tr>
            <tr><td>Update Baselines</td><td>${this.config.updateBaselines ? 'Yes' : 'No'}</td></tr>
            <tr><td>Environment</td><td>${process.env.NODE_ENV || 'test'}</td></tr>
            <tr><td>Total Duration</td><td>${(this.results.summary.totalDuration / 1000).toFixed(2)}s</td></tr>
        </table>
    </div>

    <footer style="margin-top: 40px; text-align: center; color: #666;">
        <p>Generated by FXML4 Visual Regression Testing Suite</p>
    </footer>
</body>
</html>`;

    await fs.writeFile(
      path.join(this.config.reportsDir, 'visual-regression-report.html'),
      html
    );
  }

  async generateMarkdownReport() {
    const markdown = `# FXML4 Visual Regression Test Report

## Summary
- **Total Tests**: ${this.results.summary.total}
- **Passed**: ${this.results.summary.passed}
- **Failed**: ${this.results.summary.failed}
- **Success Rate**: ${this.results.summary.successRate.toFixed(1)}%
- **Visual Diffs**: ${this.results.diffs.length}
- **Baselines Updated**: ${this.results.summary.updated || 0}

## Test Results
${this.results.tests.map(test => `
### ${test.category} - ${test.browser}
- **Status**: ${test.status}
- **Duration**: ${test.duration ? (test.duration/1000).toFixed(2) + 's' : 'N/A'}
${test.error ? `- **Error**: ${test.error}` : ''}
`).join('\n')}

## Configuration
- **Browsers**: ${this.config.browsers.join(', ')}
- **Threshold**: ${this.config.threshold}
- **Update Baselines**: ${this.config.updateBaselines ? 'Yes' : 'No'}
- **Environment**: ${process.env.NODE_ENV || 'test'}

${this.results.diffs.length > 0 ? `
## Visual Differences
${this.results.diffs.map(diff => `- ${diff.filename}`).join('\n')}
` : ''}

---
*Generated by FXML4 Visual Regression Testing Suite*
`;

    await fs.writeFile(
      path.join(this.config.reportsDir, 'VISUAL-REGRESSION-SUMMARY.md'),
      markdown
    );
  }

  async generateCISummary() {
    const summary = {
      success: this.results.summary.failed === 0,
      total: this.results.summary.total,
      passed: this.results.summary.passed,
      failed: this.results.summary.failed,
      diffs: this.results.diffs.length,
      successRate: this.results.summary.successRate,
      threshold: this.config.threshold,
      hasVisualChanges: this.results.diffs.length > 0
    };

    await fs.writeFile(
      path.join(this.config.reportsDir, 'ci-summary.json'),
      JSON.stringify(summary, null, 2)
    );

    // Set GitHub Actions outputs if in CI
    if (process.env.GITHUB_ACTIONS) {
      console.log(`::set-output name=visual_tests_success::${summary.success}`);
      console.log(`::set-output name=visual_tests_total::${summary.total}`);
      console.log(`::set-output name=visual_diffs_count::${summary.diffs}`);
      console.log(`::set-output name=visual_success_rate::${summary.successRate.toFixed(1)}`);
    }
  }

  async getPlaywrightVersion() {
    try {
      const output = await this.runCommand('npx', ['playwright', '--version']);
      return output.trim();
    } catch {
      return 'unknown';
    }
  }

  async runCommand(command, args, options = {}) {
    return new Promise((resolve, reject) => {
      const process = spawn(command, args, {
        stdio: 'pipe',
        ...options
      });

      let output = '';
      process.stdout.on('data', (data) => {
        output += data.toString();
      });

      process.stderr.on('data', (data) => {
        output += data.toString();
      });

      process.on('close', (code) => {
        if (code === 0) {
          resolve(output);
        } else {
          reject(new Error(`Command failed with exit code ${code}\n${output}`));
        }
      });

      process.on('error', reject);
    });
  }
}

// Run if called directly
if (require.main === module) {
  const runner = new VisualRegressionTestRunner();
  runner.run().catch(error => {
    console.error('Fatal error:', error);
    process.exit(1);
  });
}

module.exports = { VisualRegressionTestRunner };
