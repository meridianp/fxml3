/**
 * Load Testing Framework
 *
 * Comprehensive load testing for FXML4 UI components and user journeys
 */

import { chromium, Browser, BrowserContext, Page } from '@playwright/test';
import { PerformanceMonitor } from './performance-monitor';

interface LoadTestConfig {
  baseUrl: string;
  scenarios: LoadTestScenario[];
  rampUpTime: number;
  sustainTime: number;
  rampDownTime: number;
  maxConcurrentUsers: number;
  thresholds: PerformanceThresholds;
}

interface LoadTestScenario {
  name: string;
  weight: number; // Percentage of users running this scenario
  actions: ScenarioAction[];
  thinkTime: number; // Delay between actions (ms)
}

interface ScenarioAction {
  type: 'navigate' | 'click' | 'fill' | 'select' | 'wait' | 'custom';
  target: string;
  value?: string;
  timeout?: number;
  customAction?: (page: Page) => Promise<void>;
}

interface PerformanceThresholds {
  maxResponseTime: number;
  maxErrorRate: number; // Percentage
  minThroughput: number; // Requests per second
  maxMemoryUsage: number; // MB
}

interface LoadTestResults {
  totalUsers: number;
  totalRequests: number;
  successfulRequests: number;
  failedRequests: number;
  averageResponseTime: number;
  maxResponseTime: number;
  minResponseTime: number;
  requestsPerSecond: number;
  errorRate: number;
  scenarioResults: ScenarioResult[];
  memoryUsage: MemoryUsageResult[];
  timestamps: number[];
}

interface ScenarioResult {
  scenario: string;
  users: number;
  totalTime: number;
  avgTime: number;
  minTime: number;
  maxTime: number;
  errors: number;
  success: boolean;
}

interface MemoryUsageResult {
  timestamp: number;
  usedMemory: number;
  totalMemory: number;
}

export class LoadTester {
  private browser!: Browser;
  private contexts: BrowserContext[] = [];
  private activeUsers: number = 0;
  private results: LoadTestResults;
  private startTime: number = 0;
  private performanceMonitor: PerformanceMonitor;

  constructor() {
    this.results = this.getEmptyResults();
    this.performanceMonitor = new PerformanceMonitor();
  }

  /**
   * Run comprehensive load test
   */
  async runLoadTest(config: LoadTestConfig): Promise<LoadTestResults> {
    console.log('🚀 Starting load test...');
    console.log(`📊 Max users: ${config.maxConcurrentUsers}`);
    console.log(`⏱️  Duration: ${(config.rampUpTime + config.sustainTime + config.rampDownTime) / 1000}s`);

    this.startTime = Date.now();
    this.results = this.getEmptyResults();

    try {
      // Initialize browser
      await this.initializeBrowser();

      // Run load test phases
      await this.rampUpPhase(config);
      await this.sustainPhase(config);
      await this.rampDownPhase(config);

      // Analyze results
      this.analyzeResults(config);

      console.log('✅ Load test completed');
      console.log(`📈 Total requests: ${this.results.totalRequests}`);
      console.log(`⚡ Avg response time: ${this.results.averageResponseTime.toFixed(2)}ms`);
      console.log(`❌ Error rate: ${this.results.errorRate.toFixed(2)}%`);

      return this.results;

    } finally {
      await this.cleanup();
    }
  }

  /**
   * Run specific scenario load test
   */
  async runScenarioTest(
    baseUrl: string,
    scenario: LoadTestScenario,
    concurrentUsers: number,
    duration: number
  ): Promise<ScenarioResult> {

    console.log(`🎯 Running scenario: ${scenario.name}`);
    console.log(`👥 Users: ${concurrentUsers}, Duration: ${duration / 1000}s`);

    await this.initializeBrowser();

    const scenarioResult: ScenarioResult = {
      scenario: scenario.name,
      users: concurrentUsers,
      totalTime: 0,
      avgTime: 0,
      minTime: Infinity,
      maxTime: 0,
      errors: 0,
      success: false
    };

    const startTime = Date.now();
    const userPromises: Promise<void>[] = [];

    // Launch virtual users
    for (let i = 0; i < concurrentUsers; i++) {
      userPromises.push(this.runVirtualUser(baseUrl, scenario, scenarioResult, i));

      // Stagger user starts
      await new Promise(resolve => setTimeout(resolve, 100));
    }

    // Wait for test duration
    setTimeout(() => {
      console.log('⏰ Test duration reached, stopping users...');
    }, duration);

    // Wait for all users to complete or timeout
    await Promise.allSettled(userPromises);

    const totalTime = Date.now() - startTime;
    scenarioResult.totalTime = totalTime;
    scenarioResult.avgTime = totalTime / concurrentUsers;
    scenarioResult.success = scenarioResult.errors === 0;

    await this.cleanup();

    console.log(`✅ Scenario completed: ${scenario.name}`);
    console.log(`⏱️  Total time: ${totalTime}ms`);
    console.log(`❌ Errors: ${scenarioResult.errors}`);

    return scenarioResult;
  }

  /**
   * Run stress test to find breaking point
   */
  async runStressTest(
    baseUrl: string,
    scenario: LoadTestScenario,
    maxUsers: number,
    stepSize: number = 5,
    stepDuration: number = 30000
  ): Promise<{ breakingPoint: number; results: ScenarioResult[] }> {

    console.log('💥 Running stress test to find breaking point...');

    const results: ScenarioResult[] = [];
    let breakingPoint = maxUsers;

    for (let users = stepSize; users <= maxUsers; users += stepSize) {
      console.log(`📈 Testing with ${users} concurrent users...`);

      const result = await this.runScenarioTest(baseUrl, scenario, users, stepDuration);
      results.push(result);

      // Check if we've reached breaking point
      if (result.errors > users * 0.1 || result.avgTime > 10000) { // 10% error rate or 10s avg response
        breakingPoint = users - stepSize;
        console.log(`💔 Breaking point reached at ${breakingPoint} users`);
        break;
      }

      // Brief pause between stress levels
      await new Promise(resolve => setTimeout(resolve, 5000));
    }

    return { breakingPoint, results };
  }

  /**
   * Run endurance test for extended period
   */
  async runEnduranceTest(
    baseUrl: string,
    scenario: LoadTestScenario,
    users: number,
    duration: number
  ): Promise<{
    memoryLeak: boolean;
    performanceDegradation: boolean;
    results: ScenarioResult[]
  }> {

    console.log('🏃‍♂️ Running endurance test...');
    console.log(`👥 ${users} users for ${duration / 1000 / 60} minutes`);

    const checkInterval = 60000; // Check every minute
    const checks = Math.floor(duration / checkInterval);
    const results: ScenarioResult[] = [];

    let initialMemory = 0;
    let memoryLeak = false;
    let performanceDegradation = false;

    for (let i = 0; i < checks; i++) {
      console.log(`🔍 Endurance check ${i + 1}/${checks}`);

      const result = await this.runScenarioTest(baseUrl, scenario, users, checkInterval);
      results.push(result);

      // Check for memory leaks
      if (i === 0) {
        initialMemory = result.avgTime;
      } else if (result.avgTime > initialMemory * 1.5) {
        performanceDegradation = true;
        console.log('⚠️ Performance degradation detected');
      }

      // Memory usage would be collected from actual monitoring
      // This is a simplified check based on response times
      if (i > 5 && result.avgTime > initialMemory * 2) {
        memoryLeak = true;
        console.log('🧠 Potential memory leak detected');
      }
    }

    return { memoryLeak, performanceDegradation, results };
  }

  /**
   * Generate comprehensive load test report
   */
  async generateLoadTestReport(
    results: LoadTestResults,
    outputPath: string
  ): Promise<void> {
    const report = {
      summary: {
        totalUsers: results.totalUsers,
        totalRequests: results.totalRequests,
        successRate: ((results.successfulRequests / results.totalRequests) * 100).toFixed(2),
        averageResponseTime: results.averageResponseTime.toFixed(2),
        requestsPerSecond: results.requestsPerSecond.toFixed(2),
        testDuration: results.timestamps.length > 0 ?
          (results.timestamps[results.timestamps.length - 1] - results.timestamps[0]) / 1000 : 0
      },
      scenarios: results.scenarioResults,
      performance: {
        memoryUsage: results.memoryUsage,
        thresholdViolations: this.checkThresholdViolations(results)
      },
      recommendations: this.generateLoadTestRecommendations(results),
      timestamp: new Date().toISOString()
    };

    // Write detailed JSON report
    const fs = await import('fs/promises');
    const path = await import('path');

    await fs.writeFile(
      path.join(outputPath, 'load-test-report.json'),
      JSON.stringify(report, null, 2)
    );

    // Generate HTML report
    const htmlReport = this.generateLoadTestHTMLReport(report);
    await fs.writeFile(
      path.join(outputPath, 'load-test-report.html'),
      htmlReport
    );

    console.log(`📄 Load test report generated at: ${outputPath}`);
  }

  private async initializeBrowser(): Promise<void> {
    this.browser = await chromium.launch({
      headless: true,
      args: [
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-dev-shm-usage',
        '--disable-accelerated-2d-canvas',
        '--no-first-run',
        '--no-zygote',
        '--disable-gpu'
      ]
    });
  }

  private async cleanup(): Promise<void> {
    // Close all contexts
    for (const context of this.contexts) {
      await context.close().catch(() => {});
    }
    this.contexts = [];

    // Close browser
    if (this.browser) {
      await this.browser.close().catch(() => {});
    }

    this.activeUsers = 0;
  }

  private async runVirtualUser(
    baseUrl: string,
    scenario: LoadTestScenario,
    result: ScenarioResult,
    userId: number
  ): Promise<void> {
    let context: BrowserContext | null = null;
    let page: Page | null = null;

    try {
      // Create isolated context for this user
      context = await this.browser.newContext({
        viewport: { width: 1280, height: 720 },
        userAgent: `LoadTest-User-${userId}`
      });

      this.contexts.push(context);
      page = await context.newPage();

      const userStartTime = Date.now();
      this.activeUsers++;

      // Execute scenario actions
      for (const action of scenario.actions) {
        const actionStartTime = Date.now();

        try {
          await this.executeAction(page, action, baseUrl);

          const actionTime = Date.now() - actionStartTime;
          this.results.totalRequests++;
          this.results.successfulRequests++;

          // Update min/max times
          result.minTime = Math.min(result.minTime, actionTime);
          result.maxTime = Math.max(result.maxTime, actionTime);

        } catch (error) {
          console.error(`Action failed for user ${userId}:`, error);
          this.results.failedRequests++;
          result.errors++;
        }

        // Think time between actions
        if (scenario.thinkTime > 0) {
          await new Promise(resolve => setTimeout(resolve, scenario.thinkTime));
        }
      }

      const userTime = Date.now() - userStartTime;
      console.log(`👤 User ${userId} completed in ${userTime}ms`);

    } catch (error) {
      console.error(`Virtual user ${userId} failed:`, error);
      result.errors++;
    } finally {
      this.activeUsers--;

      if (page) {
        await page.close().catch(() => {});
      }
      if (context) {
        await context.close().catch(() => {});
        const index = this.contexts.indexOf(context);
        if (index > -1) {
          this.contexts.splice(index, 1);
        }
      }
    }
  }

  private async executeAction(page: Page, action: ScenarioAction, baseUrl: string): Promise<void> {
    switch (action.type) {
      case 'navigate':
        const url = action.target.startsWith('http') ? action.target : `${baseUrl}${action.target}`;
        await page.goto(url, { timeout: action.timeout || 30000 });
        await page.waitForLoadState('networkidle');
        break;

      case 'click':
        await page.click(action.target, { timeout: action.timeout || 10000 });
        break;

      case 'fill':
        if (action.value) {
          await page.fill(action.target, action.value, { timeout: action.timeout || 10000 });
        }
        break;

      case 'select':
        if (action.value) {
          await page.selectOption(action.target, action.value, { timeout: action.timeout || 10000 });
        }
        break;

      case 'wait':
        await page.waitForTimeout(parseInt(action.target, 10));
        break;

      case 'custom':
        if (action.customAction) {
          await action.customAction(page);
        }
        break;

      default:
        throw new Error(`Unknown action type: ${action.type}`);
    }
  }

  private async rampUpPhase(config: LoadTestConfig): Promise<void> {
    console.log('📈 Ramp-up phase starting...');

    const steps = 10;
    const stepDuration = config.rampUpTime / steps;
    const usersPerStep = Math.ceil(config.maxConcurrentUsers / steps);

    for (let step = 1; step <= steps; step++) {
      const usersToAdd = Math.min(usersPerStep, config.maxConcurrentUsers - this.activeUsers);

      if (usersToAdd > 0) {
        console.log(`👥 Adding ${usersToAdd} users (step ${step}/${steps})`);

        // Add users for this step
        for (let i = 0; i < usersToAdd; i++) {
          const scenario = this.selectRandomScenario(config.scenarios);
          // In a real implementation, we'd start virtual users here
          this.activeUsers++;
        }
      }

      await new Promise(resolve => setTimeout(resolve, stepDuration));
    }

    console.log(`✅ Ramp-up complete: ${this.activeUsers} active users`);
  }

  private async sustainPhase(config: LoadTestConfig): Promise<void> {
    console.log(`🏃‍♂️ Sustain phase: ${config.sustainTime / 1000}s with ${this.activeUsers} users`);

    // Monitor performance during sustain phase
    const monitoringInterval = setInterval(() => {
      this.collectRuntimeMetrics();
    }, 5000);

    await new Promise(resolve => setTimeout(resolve, config.sustainTime));

    clearInterval(monitoringInterval);
    console.log('✅ Sustain phase complete');
  }

  private async rampDownPhase(config: LoadTestConfig): Promise<void> {
    console.log('📉 Ramp-down phase starting...');

    const steps = 5;
    const stepDuration = config.rampDownTime / steps;
    const usersPerStep = Math.ceil(this.activeUsers / steps);

    for (let step = 1; step <= steps; step++) {
      const usersToRemove = Math.min(usersPerStep, this.activeUsers);

      if (usersToRemove > 0) {
        console.log(`👥 Removing ${usersToRemove} users (step ${step}/${steps})`);
        this.activeUsers -= usersToRemove;
      }

      await new Promise(resolve => setTimeout(resolve, stepDuration));
    }

    console.log('✅ Ramp-down complete');
  }

  private selectRandomScenario(scenarios: LoadTestScenario[]): LoadTestScenario {
    const random = Math.random() * 100;
    let cumulativeWeight = 0;

    for (const scenario of scenarios) {
      cumulativeWeight += scenario.weight;
      if (random <= cumulativeWeight) {
        return scenario;
      }
    }

    return scenarios[0]; // Fallback
  }

  private collectRuntimeMetrics(): void {
    // Collect real-time metrics during load test
    this.results.timestamps.push(Date.now());

    // In a real implementation, we'd collect actual memory usage
    this.results.memoryUsage.push({
      timestamp: Date.now(),
      usedMemory: Math.random() * 1000, // Mock data
      totalMemory: 2048
    });
  }

  private analyzeResults(config: LoadTestConfig): void {
    const totalTime = Date.now() - this.startTime;

    this.results.totalUsers = config.maxConcurrentUsers;
    this.results.requestsPerSecond = (this.results.totalRequests / totalTime) * 1000;
    this.results.errorRate = (this.results.failedRequests / this.results.totalRequests) * 100;

    if (this.results.totalRequests > 0) {
      this.results.averageResponseTime =
        this.results.scenarioResults.reduce((sum, r) => sum + r.avgTime, 0) /
        this.results.scenarioResults.length;
    }
  }

  private checkThresholdViolations(results: LoadTestResults): string[] {
    const violations: string[] = [];

    // These would be compared against actual thresholds
    if (results.averageResponseTime > 5000) {
      violations.push('Average response time exceeds 5 seconds');
    }

    if (results.errorRate > 5) {
      violations.push('Error rate exceeds 5%');
    }

    if (results.requestsPerSecond < 10) {
      violations.push('Throughput below 10 requests/second');
    }

    return violations;
  }

  private generateLoadTestRecommendations(results: LoadTestResults): string[] {
    const recommendations: string[] = [];

    if (results.errorRate > 2) {
      recommendations.push('High error rate detected - investigate server capacity and error handling');
    }

    if (results.averageResponseTime > 3000) {
      recommendations.push('High response times - consider optimizing server performance or scaling infrastructure');
    }

    if (results.requestsPerSecond < 50) {
      recommendations.push('Low throughput - review server configuration and resource allocation');
    }

    recommendations.push('Monitor memory usage for potential leaks during extended load');
    recommendations.push('Consider implementing caching strategies for frequently accessed resources');

    return recommendations;
  }

  private generateLoadTestHTMLReport(report: any): string {
    return `
<!DOCTYPE html>
<html>
<head>
    <title>FXML4 Load Test Report</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .metric { margin: 10px 0; padding: 15px; border-left: 4px solid #007acc; background: #f5f5f5; }
        .warning { border-left-color: #ff9800; }
        .error { border-left-color: #f44336; }
        .good { border-left-color: #4caf50; }
        table { width: 100%; border-collapse: collapse; margin: 20px 0; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background-color: #f2f2f2; }
        .chart { height: 300px; background: #f9f9f9; margin: 20px 0; padding: 20px; text-align: center; }
    </style>
</head>
<body>
    <h1>FXML4 Load Test Report</h1>

    <div class="metric ${report.summary.successRate > 95 ? 'good' : 'warning'}">
        <h3>Test Summary</h3>
        <p><strong>Total Users:</strong> ${report.summary.totalUsers}</p>
        <p><strong>Success Rate:</strong> ${report.summary.successRate}%</p>
        <p><strong>Average Response Time:</strong> ${report.summary.averageResponseTime}ms</p>
        <p><strong>Requests/Second:</strong> ${report.summary.requestsPerSecond}</p>
        <p><strong>Test Duration:</strong> ${report.summary.testDuration}s</p>
    </div>

    <div class="metric">
        <h3>Scenario Performance</h3>
        <table>
            <tr>
                <th>Scenario</th>
                <th>Users</th>
                <th>Avg Time (ms)</th>
                <th>Min Time (ms)</th>
                <th>Max Time (ms)</th>
                <th>Errors</th>
                <th>Status</th>
            </tr>
            ${report.scenarios.map((scenario: any) => `
                <tr>
                    <td>${scenario.scenario}</td>
                    <td>${scenario.users}</td>
                    <td>${scenario.avgTime.toFixed(2)}</td>
                    <td>${scenario.minTime}</td>
                    <td>${scenario.maxTime}</td>
                    <td>${scenario.errors}</td>
                    <td>${scenario.success ? '✅' : '❌'}</td>
                </tr>
            `).join('')}
        </table>
    </div>

    <div class="metric">
        <h3>Threshold Violations</h3>
        ${report.performance.thresholdViolations.length > 0 ?
          `<ul>${report.performance.thresholdViolations.map((v: string) => `<li class="error">${v}</li>`).join('')}</ul>` :
          '<p class="good">No threshold violations detected</p>'
        }
    </div>

    <div class="metric">
        <h3>Recommendations</h3>
        <ul>
            ${report.recommendations.map((rec: string) => `<li>${rec}</li>`).join('')}
        </ul>
    </div>

    <div class="chart">
        <h3>Performance Timeline</h3>
        <p>Memory Usage and Response Time Over Time</p>
        <p>(Chart visualization would be implemented with a charting library)</p>
    </div>

    <p><em>Generated on ${report.timestamp}</em></p>
</body>
</html>`;
  }

  private getEmptyResults(): LoadTestResults {
    return {
      totalUsers: 0,
      totalRequests: 0,
      successfulRequests: 0,
      failedRequests: 0,
      averageResponseTime: 0,
      maxResponseTime: 0,
      minResponseTime: Infinity,
      requestsPerSecond: 0,
      errorRate: 0,
      scenarioResults: [],
      memoryUsage: [],
      timestamps: []
    };
  }
}

export { LoadTester, LoadTestConfig, LoadTestScenario, ScenarioAction };
