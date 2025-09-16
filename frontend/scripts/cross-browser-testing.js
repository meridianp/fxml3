#!/usr/bin/env node

/**
 * Cross-Browser Testing Script
 *
 * Orchestrates comprehensive cross-browser compatibility testing
 */

const { spawn } = require('child_process');
const fs = require('fs/promises');
const path = require('path');

class CrossBrowserTestRunner {
  constructor() {
    this.config = {
      outputDir: 'e2e-results/cross-browser',
      browsers: [
        { name: 'chromium', priority: 'critical' },
        { name: 'firefox', priority: 'high' },
        { name: 'webkit', priority: 'medium' }
      ],
      testSuites: [
        'browser-compatibility',
        'feature-detection'
      ],
      devices: [
        'Desktop Chrome',
        'Desktop Firefox',
        'Desktop Safari',
        'iPhone 12',
        'Galaxy S21'
      ],
      parallel: true,
      maxConcurrency: 3
    };

    this.results = {
      browsers: {},
      devices: {},
      summary: {},
      compatibility: {},
      issues: []
    };
  }

  async run() {
    console.log('🌐 Starting Cross-Browser Compatibility Testing');
    console.log('================================================\n');

    try {
      // Setup
      await this.setup();

      // Run browser compatibility tests
      await this.runBrowserTests();

      // Run device compatibility tests
      await this.runDeviceTests();

      // Run feature detection tests
      await this.runFeatureDetectionTests();

      // Analyze compatibility matrix
      await this.analyzeCompatibility();

      // Generate compatibility reports
      await this.generateReports();

      console.log('\n✅ Cross-browser testing completed successfully!');
      console.log(`📊 Results saved to: ${this.config.outputDir}`);

    } catch (error) {
      console.error('\n❌ Cross-browser testing failed:', error);
      process.exit(1);
    }
  }

  async setup() {
    console.log('🔧 Setting up cross-browser testing environment...');

    // Create output directories
    await fs.mkdir(this.config.outputDir, { recursive: true });
    await fs.mkdir(path.join(this.config.outputDir, 'browsers'), { recursive: true });
    await fs.mkdir(path.join(this.config.outputDir, 'devices'), { recursive: true });
    await fs.mkdir(path.join(this.config.outputDir, 'features'), { recursive: true });

    // Verify Playwright browsers are installed
    try {
      await this.runCommand('npx', ['playwright', 'install', '--with-deps']);
      console.log('✅ Playwright browsers verified');
    } catch (error) {
      console.warn('⚠️ Browser installation check failed:', error.message);
    }

    console.log('✅ Setup completed\n');
  }

  async runBrowserTests() {
    console.log('🖥️ Running browser compatibility tests...');

    const browserPromises = this.config.browsers.map(async (browser) => {
      console.log(`\n🌐 Testing ${browser.name}...`);

      try {
        const startTime = Date.now();

        // Run browser-specific tests
        await this.runPlaywrightTests({
          pattern: 'e2e/cross-browser/browser-compatibility.spec.ts',
          project: browser.name,
          timeout: 120000
        });

        const duration = Date.now() - startTime;

        this.results.browsers[browser.name] = {
          status: 'passed',
          duration,
          priority: browser.priority,
          timestamp: new Date().toISOString()
        };

        console.log(`✅ ${browser.name} tests completed in ${(duration/1000).toFixed(2)}s`);

      } catch (error) {
        this.results.browsers[browser.name] = {
          status: 'failed',
          error: error.message,
          priority: browser.priority,
          timestamp: new Date().toISOString()
        };

        this.results.issues.push({
          type: 'browser',
          browser: browser.name,
          severity: browser.priority,
          issue: error.message
        });

        console.error(`❌ ${browser.name} tests failed:`, error.message);

        // Don't fail completely for non-critical browsers
        if (browser.priority === 'critical') {
          throw error;
        }
      }
    });

    if (this.config.parallel) {
      await Promise.allSettled(browserPromises);
    } else {
      for (const promise of browserPromises) {
        await promise;
      }
    }

    console.log('✅ Browser compatibility tests completed\n');
  }

  async runDeviceTests() {
    console.log('📱 Running device compatibility tests...');

    for (const device of this.config.devices) {
      console.log(`📱 Testing ${device}...`);

      try {
        const startTime = Date.now();

        // Run device-specific tests
        await this.runPlaywrightTests({
          pattern: 'e2e/cross-browser/browser-compatibility.spec.ts',
          project: 'chromium',
          timeout: 90000,
          extraArgs: [`--global-timeout=90000`]
        });

        const duration = Date.now() - startTime;

        this.results.devices[device] = {
          status: 'passed',
          duration,
          timestamp: new Date().toISOString()
        };

        console.log(`✅ ${device} tests completed in ${(duration/1000).toFixed(2)}s`);

      } catch (error) {
        this.results.devices[device] = {
          status: 'failed',
          error: error.message,
          timestamp: new Date().toISOString()
        };

        this.results.issues.push({
          type: 'device',
          device: device,
          severity: 'medium',
          issue: error.message
        });

        console.error(`❌ ${device} tests failed:`, error.message);
      }
    }

    console.log('✅ Device compatibility tests completed\n');
  }

  async runFeatureDetectionTests() {
    console.log('🔍 Running feature detection tests...');

    const featureTests = this.config.browsers.map(async (browser) => {
      console.log(`🔧 Testing features on ${browser.name}...`);

      try {
        const startTime = Date.now();

        // Run feature detection tests
        await this.runPlaywrightTests({
          pattern: 'e2e/cross-browser/feature-detection.spec.ts',
          project: browser.name,
          timeout: 60000
        });

        const duration = Date.now() - startTime;

        if (!this.results.browsers[browser.name]) {
          this.results.browsers[browser.name] = {};
        }

        this.results.browsers[browser.name].features = {
          status: 'passed',
          duration,
          timestamp: new Date().toISOString()
        };

        console.log(`✅ ${browser.name} feature tests completed`);

      } catch (error) {
        if (!this.results.browsers[browser.name]) {
          this.results.browsers[browser.name] = {};
        }

        this.results.browsers[browser.name].features = {
          status: 'failed',
          error: error.message,
          timestamp: new Date().toISOString()
        };

        this.results.issues.push({
          type: 'feature',
          browser: browser.name,
          severity: 'medium',
          issue: `Feature detection failed: ${error.message}`
        });

        console.error(`❌ ${browser.name} feature tests failed:`, error.message);
      }
    });

    await Promise.allSettled(featureTests);
    console.log('✅ Feature detection tests completed\n');
  }

  async analyzeCompatibility() {
    console.log('📊 Analyzing cross-browser compatibility...');

    // Calculate overall compatibility scores
    const browserScores = {};
    let totalScore = 0;
    let browserCount = 0;

    Object.entries(this.results.browsers).forEach(([browser, result]) => {
      let score = 0;

      // Base score for browser working
      if (result.status === 'passed') {
        score += 70;
      }

      // Additional score for features working
      if (result.features && result.features.status === 'passed') {
        score += 30;
      }

      browserScores[browser] = score;
      totalScore += score;
      browserCount++;
    });

    this.results.compatibility = {
      overallScore: browserCount > 0 ? Math.round(totalScore / browserCount) : 0,
      browserScores,
      supportMatrix: this.generateSupportMatrix(),
      riskAssessment: this.assessCompatibilityRisks()
    };

    // Device compatibility analysis
    const deviceResults = Object.entries(this.results.devices);
    const workingDevices = deviceResults.filter(([_, result]) => result.status === 'passed').length;
    const deviceCompatibility = deviceResults.length > 0 ?
      Math.round((workingDevices / deviceResults.length) * 100) : 0;

    this.results.compatibility.deviceCompatibility = deviceCompatibility;

    console.log(`📊 Overall compatibility score: ${this.results.compatibility.overallScore}%`);
    console.log(`📱 Device compatibility: ${deviceCompatibility}%`);
    console.log(`⚠️ Issues found: ${this.results.issues.length}`);
  }

  generateSupportMatrix() {
    const matrix = {};

    // Core features support matrix
    const coreFeatures = [
      'authentication',
      'navigation',
      'trading-interface',
      'data-visualization',
      'real-time-updates',
      'responsive-layout'
    ];

    this.config.browsers.forEach(browser => {
      matrix[browser.name] = {};

      coreFeatures.forEach(feature => {
        // Determine support based on test results
        const browserResult = this.results.browsers[browser.name];

        if (browserResult && browserResult.status === 'passed') {
          matrix[browser.name][feature] = 'supported';
        } else if (browserResult && browserResult.status === 'failed') {
          matrix[browser.name][feature] = 'unsupported';
        } else {
          matrix[browser.name][feature] = 'unknown';
        }
      });
    });

    return matrix;
  }

  assessCompatibilityRisks() {
    const risks = [];

    // Check for critical browser failures
    const criticalBrowsers = this.config.browsers.filter(b => b.priority === 'critical');
    const failedCritical = criticalBrowsers.filter(b =>
      this.results.browsers[b.name] && this.results.browsers[b.name].status === 'failed'
    );

    if (failedCritical.length > 0) {
      risks.push({
        level: 'high',
        type: 'critical-browser-failure',
        description: `Critical browsers failed: ${failedCritical.map(b => b.name).join(', ')}`,
        impact: 'Major user impact - core functionality broken on primary browsers'
      });
    }

    // Check for widespread device issues
    const deviceFailures = Object.entries(this.results.devices)
      .filter(([_, result]) => result.status === 'failed').length;

    if (deviceFailures > Object.keys(this.results.devices).length * 0.5) {
      risks.push({
        level: 'medium',
        type: 'device-compatibility',
        description: `${deviceFailures} devices failed compatibility tests`,
        impact: 'Mobile/tablet users may experience issues'
      });
    }

    // Check for feature detection issues
    const featureIssues = this.results.issues.filter(issue => issue.type === 'feature');
    if (featureIssues.length > 2) {
      risks.push({
        level: 'medium',
        type: 'feature-support',
        description: `Multiple feature detection failures across browsers`,
        impact: 'Some advanced features may not work consistently'
      });
    }

    return risks;
  }

  async generateReports() {
    console.log('📄 Generating cross-browser compatibility reports...');

    // Generate comprehensive JSON report
    const report = {
      summary: {
        testDate: new Date().toISOString(),
        environment: process.env.NODE_ENV || 'development',
        overallCompatibility: this.results.compatibility.overallScore,
        browsersTestedCount: Object.keys(this.results.browsers).length,
        devicesTestedCount: Object.keys(this.results.devices).length,
        issuesFound: this.results.issues.length
      },
      results: this.results,
      recommendations: this.generateRecommendations(),
      actionItems: this.generateActionItems()
    };

    // Write JSON report
    await fs.writeFile(
      path.join(this.config.outputDir, 'compatibility-report.json'),
      JSON.stringify(report, null, 2)
    );

    // Generate HTML dashboard
    const htmlReport = this.generateHTMLReport(report);
    await fs.writeFile(
      path.join(this.config.outputDir, 'compatibility-dashboard.html'),
      htmlReport
    );

    // Generate markdown summary
    const markdownReport = this.generateMarkdownReport(report);
    await fs.writeFile(
      path.join(this.config.outputDir, 'COMPATIBILITY-SUMMARY.md'),
      markdownReport
    );

    // Generate CI-friendly summary
    await this.generateCISummary(report);

    console.log('✅ Reports generated successfully');
  }

  generateRecommendations() {
    const recommendations = [];

    // Browser-specific recommendations
    Object.entries(this.results.browsers).forEach(([browser, result]) => {
      if (result.status === 'failed') {
        recommendations.push({
          category: 'Browser Support',
          priority: result.priority || 'medium',
          browser: browser,
          issue: `${browser} compatibility issues detected`,
          action: `Investigate and fix ${browser}-specific problems`
        });
      }
    });

    // Device-specific recommendations
    const deviceFailures = Object.entries(this.results.devices)
      .filter(([_, result]) => result.status === 'failed');

    if (deviceFailures.length > 0) {
      recommendations.push({
        category: 'Mobile Compatibility',
        priority: 'high',
        issue: `${deviceFailures.length} devices failed tests`,
        action: 'Improve responsive design and mobile-specific functionality'
      });
    }

    // Feature support recommendations
    const featureIssues = this.results.issues.filter(issue => issue.type === 'feature');
    if (featureIssues.length > 0) {
      recommendations.push({
        category: 'Feature Support',
        priority: 'medium',
        issue: 'Inconsistent feature support across browsers',
        action: 'Implement progressive enhancement and polyfills'
      });
    }

    // General recommendations
    if (this.results.compatibility.overallScore < 80) {
      recommendations.push({
        category: 'Overall Compatibility',
        priority: 'high',
        issue: 'Low overall compatibility score',
        action: 'Prioritize cross-browser testing and compatibility fixes'
      });
    }

    return recommendations;
  }

  generateActionItems() {
    const actionItems = [];

    // High priority issues
    const criticalIssues = this.results.issues.filter(issue =>
      issue.severity === 'critical' || issue.severity === 'high'
    );

    criticalIssues.forEach(issue => {
      actionItems.push({
        priority: 'immediate',
        task: `Fix ${issue.type} issue: ${issue.issue}`,
        assignee: 'frontend-team',
        dueDate: this.addDays(new Date(), 3).toISOString().split('T')[0]
      });
    });

    // Medium priority browser support
    const mediumIssues = this.results.issues.filter(issue => issue.severity === 'medium');
    if (mediumIssues.length > 0) {
      actionItems.push({
        priority: 'high',
        task: 'Address medium priority compatibility issues',
        assignee: 'frontend-team',
        dueDate: this.addDays(new Date(), 7).toISOString().split('T')[0]
      });
    }

    // Testing improvements
    actionItems.push({
      priority: 'medium',
      task: 'Integrate cross-browser testing into CI/CD pipeline',
      assignee: 'devops-team',
      dueDate: this.addDays(new Date(), 14).toISOString().split('T')[0]
    });

    return actionItems;
  }

  generateHTMLReport(report) {
    const compatibilityColor = report.summary.overallCompatibility >= 80 ? '#4caf50' :
                              report.summary.overallCompatibility >= 60 ? '#ff9800' : '#f44336';

    return `
<!DOCTYPE html>
<html>
<head>
    <title>FXML4 Cross-Browser Compatibility Report</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; line-height: 1.6; }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
        .score { font-size: 3em; font-weight: bold; color: ${compatibilityColor}; text-align: center; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin: 20px 0; }
        .card { background: #f8f9fa; padding: 20px; border-radius: 8px; border-left: 4px solid #007acc; }
        .status-passed { color: #28a745; }
        .status-failed { color: #dc3545; }
        .priority-critical { border-left-color: #dc3545; }
        .priority-high { border-left-color: #fd7e14; }
        .priority-medium { border-left-color: #ffc107; }
        table { width: 100%; border-collapse: collapse; margin: 20px 0; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background-color: #f2f2f2; }
        .matrix { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; }
        .matrix-item { padding: 10px; border-radius: 4px; text-align: center; }
        .supported { background: #d4edda; color: #155724; }
        .unsupported { background: #f8d7da; color: #721c24; }
        .unknown { background: #fff3cd; color: #856404; }
    </style>
</head>
<body>
    <div class="header">
        <h1>FXML4 Cross-Browser Compatibility Report</h1>
        <p>Generated on ${report.summary.testDate}</p>
        <div class="score">${report.summary.overallCompatibility}%</div>
        <p style="text-align: center; margin-top: 0;">Overall Compatibility Score</p>
    </div>

    <div class="grid">
        <div class="card">
            <h3>Test Summary</h3>
            <p><strong>Browsers Tested:</strong> ${report.summary.browsersTestedCount}</p>
            <p><strong>Devices Tested:</strong> ${report.summary.devicesTestedCount}</p>
            <p><strong>Issues Found:</strong> ${report.summary.issuesFound}</p>
        </div>

        <div class="card">
            <h3>Browser Results</h3>
            ${Object.entries(report.results.browsers).map(([browser, result]) => `
                <div class="status-${result.status}">${browser}: ${result.status}</div>
            `).join('')}
        </div>

        <div class="card">
            <h3>Device Results</h3>
            ${Object.entries(report.results.devices).map(([device, result]) => `
                <div class="status-${result.status}">${device}: ${result.status}</div>
            `).join('')}
        </div>
    </div>

    <h2>Support Matrix</h2>
    <div class="matrix">
        ${Object.entries(report.results.compatibility.supportMatrix).map(([browser, features]) => `
            <div>
                <h4>${browser}</h4>
                ${Object.entries(features).map(([feature, support]) => `
                    <div class="matrix-item ${support}">${feature}</div>
                `).join('')}
            </div>
        `).join('')}
    </div>

    <h2>Recommendations</h2>
    ${report.recommendations.map(rec => `
        <div class="card priority-${rec.priority}">
            <h4>${rec.category} - ${rec.priority} Priority</h4>
            <p><strong>Issue:</strong> ${rec.issue}</p>
            <p><strong>Action:</strong> ${rec.action}</p>
        </div>
    `).join('')}

    <h2>Action Items</h2>
    <table>
        <tr><th>Priority</th><th>Task</th><th>Assignee</th><th>Due Date</th></tr>
        ${report.actionItems.map(item => `
            <tr>
                <td class="priority-${item.priority}">${item.priority}</td>
                <td>${item.task}</td>
                <td>${item.assignee}</td>
                <td>${item.dueDate}</td>
            </tr>
        `).join('')}
    </table>

    <footer style="margin-top: 40px; text-align: center; color: #666;">
        <p>Generated by FXML4 Cross-Browser Testing Suite</p>
    </footer>
</body>
</html>`;
  }

  generateMarkdownReport(report) {
    return `# FXML4 Cross-Browser Compatibility Report

## Summary
- **Overall Compatibility:** ${report.summary.overallCompatibility}%
- **Browsers Tested:** ${report.summary.browsersTestedCount}
- **Devices Tested:** ${report.summary.devicesTestedCount}
- **Issues Found:** ${report.summary.issuesFound}

## Browser Results
${Object.entries(report.results.browsers).map(([browser, result]) =>
  `- **${browser}:** ${result.status} ${result.status === 'failed' ? `(${result.error})` : ''}`
).join('\n')}

## Device Results
${Object.entries(report.results.devices).map(([device, result]) =>
  `- **${device}:** ${result.status} ${result.status === 'failed' ? `(${result.error})` : ''}`
).join('\n')}

## Key Recommendations
${report.recommendations.slice(0, 5).map(rec =>
  `- **${rec.category}** (${rec.priority}): ${rec.action}`
).join('\n')}

## Action Items
${report.actionItems.map(item =>
  `- [ ] **${item.priority.toUpperCase()}**: ${item.task} (Due: ${item.dueDate})`
).join('\n')}

---
*Generated by FXML4 Cross-Browser Testing Suite*
`;
  }

  async generateCISummary(report) {
    const summary = {
      success: report.summary.overallCompatibility >= 70,
      score: report.summary.overallCompatibility,
      criticalIssues: this.results.issues.filter(i => i.severity === 'critical').length,
      browserFailures: Object.values(report.results.browsers).filter(r => r.status === 'failed').length,
      deviceFailures: Object.values(report.results.devices).filter(r => r.status === 'failed').length
    };

    await fs.writeFile(
      path.join(this.config.outputDir, 'ci-summary.json'),
      JSON.stringify(summary, null, 2)
    );

    // Set GitHub Actions outputs if in CI
    if (process.env.GITHUB_ACTIONS) {
      console.log(`::set-output name=compatibility_score::${summary.score}`);
      console.log(`::set-output name=compatibility_success::${summary.success}`);
      console.log(`::set-output name=critical_issues::${summary.criticalIssues}`);
    }
  }

  async runPlaywrightTests(options) {
    return new Promise((resolve, reject) => {
      const args = [
        'test',
        options.pattern,
        '--project', options.project,
        '--timeout', options.timeout.toString()
      ];

      if (options.extraArgs) {
        args.push(...options.extraArgs);
      }

      if (process.env.CI) {
        args.push('--reporter=github');
      }

      const playwright = spawn('npx', ['playwright', ...args], {
        stdio: 'pipe', // Capture output to prevent noise
        env: {
          ...process.env,
          FORCE_COLOR: '0'
        }
      });

      let output = '';
      playwright.stdout.on('data', (data) => {
        output += data.toString();
      });

      playwright.stderr.on('data', (data) => {
        output += data.toString();
      });

      playwright.on('close', (code) => {
        if (code === 0) {
          resolve(output);
        } else {
          reject(new Error(`Tests failed with exit code ${code}\n${output}`));
        }
      });

      playwright.on('error', reject);
    });
  }

  async runCommand(command, args) {
    return new Promise((resolve, reject) => {
      const process = spawn(command, args, { stdio: 'pipe' });

      let output = '';
      process.stdout.on('data', (data) => {
        output += data.toString();
      });

      process.on('close', (code) => {
        if (code === 0) {
          resolve(output);
        } else {
          reject(new Error(`Command failed with exit code ${code}`));
        }
      });

      process.on('error', reject);
    });
  }

  addDays(date, days) {
    const result = new Date(date);
    result.setDate(result.getDate() + days);
    return result;
  }
}

// Run if called directly
if (require.main === module) {
  const runner = new CrossBrowserTestRunner();
  runner.run().catch(error => {
    console.error('Fatal error:', error);
    process.exit(1);
  });
}

module.exports = { CrossBrowserTestRunner };
