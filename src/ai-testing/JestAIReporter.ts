/**
 * Jest Reporter for AI-Enhanced Test Analysis
 *
 * Automatically captures test execution data and feeds it to the AI analyzer
 * for pattern recognition and optimization insights while maintaining
 * audit trails for financial system compliance.
 */

import { Reporter, TestResult, AggregatedResult, TestContext } from '@jest/reporters';
import { Test } from '@jest/test-result';
import { aiTestAnalyzer, TestExecution } from './AITestAnalyzer';
import * as fs from 'fs';
import * as path from 'path';

export class JestAIReporter implements Reporter {
  private startTime: number = 0;
  private testExecutions: TestExecution[] = [];

  constructor(
    private globalConfig: any,
    private options: {
      outputPath?: string;
      enableRealTimeAnalysis?: boolean;
      minimumTestsForAnalysis?: number;
    } = {}
  ) {
    this.options = {
      outputPath: './ai-testing-reports',
      enableRealTimeAnalysis: true,
      minimumTestsForAnalysis: 5,
      ...options
    };

    // Ensure output directory exists
    if (this.options.outputPath && !fs.existsSync(this.options.outputPath)) {
      fs.mkdirSync(this.options.outputPath, { recursive: true });
    }
  }

  onRunStart(): void {
    this.startTime = Date.now();
    console.log('\n🤖 AI-Enhanced Test Analysis: Monitoring test execution...\n');
  }

  onTestResult(test: Test, testResult: TestResult, aggregatedResult: AggregatedResult): void {
    // Process each test case result
    testResult.testResults.forEach(result => {
      const execution: TestExecution = {
        testName: result.fullName,
        filePath: test.path,
        duration: result.duration || 0,
        status: result.status === 'passed' ? 'passed' :
                result.status === 'failed' ? 'failed' : 'skipped',
        timestamp: Date.now(),
        errorMessage: result.failureMessages.length > 0 ? result.failureMessages[0] : undefined,
        stackTrace: result.failureMessages.join('\n'),
        codeChanges: this.detectCodeChanges(test.path),
        coverage: this.extractCoverageData(test.path, aggregatedResult)
      };

      this.testExecutions.push(execution);

      // Feed to AI analyzer for real-time analysis
      if (this.options.enableRealTimeAnalysis) {
        try {
          aiTestAnalyzer.recordTestExecution(execution);
        } catch (error) {
          console.warn('⚠️  AI Analysis Warning:', error);
        }
      }
    });
  }

  onRunComplete(contexts: Set<TestContext>, results: AggregatedResult): void {
    const endTime = Date.now();
    const totalDuration = endTime - this.startTime;

    console.log('\n🤖 AI Test Analysis Summary:');
    console.log('═'.repeat(50));

    // Get AI insights
    const insights = aiTestAnalyzer.getInsights({ minConfidence: 70 });
    const stats = aiTestAnalyzer.getTestStatistics();

    console.log(`📊 Test Execution Statistics:`);
    console.log(`   • Total Executions: ${stats.totalExecutions}`);
    console.log(`   • Pass Rate: ${(stats.passRate * 100).toFixed(1)}%`);
    console.log(`   • Average Duration: ${stats.averageDuration.toFixed(1)}ms`);

    if (insights.length > 0) {
      console.log(`\n🔍 AI Insights Generated: ${insights.length}`);

      insights.slice(0, 5).forEach((insight, index) => {
        const emoji = this.getInsightEmoji(insight.type, insight.severity);
        console.log(`   ${emoji} ${insight.title}`);
        console.log(`     └─ Confidence: ${insight.confidence}% | Impact: ${insight.impact}`);
      });

      if (insights.length > 5) {
        console.log(`   ... and ${insights.length - 5} more insights available`);
      }

      // Generate recommendations
      this.generateActionableRecommendations(insights);
    }

    // Export detailed report
    this.exportDetailedReport(results, insights, stats);

    console.log(`\n⏱️  Total Analysis Time: ${totalDuration}ms`);
    console.log('═'.repeat(50));
  }

  /**
   * Detect recent code changes that might affect tests
   */
  private detectCodeChanges(testFilePath: string): string[] {
    try {
      const sourceFilePath = testFilePath.replace(/\.test\.[jt]sx?$/, '');

      // In a real implementation, this would integrate with Git
      // For now, we'll return a placeholder
      return []; // This would contain actual changed files from git diff
    } catch (error) {
      return [];
    }
  }

  /**
   * Extract coverage data for the test file
   */
  private extractCoverageData(testFilePath: string, results: AggregatedResult): TestExecution['coverage'] {
    // Default coverage data
    const defaultCoverage = {
      statements: 0,
      branches: 0,
      functions: 0,
      lines: 0
    };

    try {
      // Extract from Jest coverage data if available
      const coverageMap = results.coverageMap;
      if (!coverageMap) return defaultCoverage;

      const sourceFile = testFilePath.replace(/\.test\.[jt]sx?$/, '');
      const fileCoverage = coverageMap.fileCoverageFor(sourceFile);

      if (fileCoverage) {
        const summary = fileCoverage.toSummary();
        return {
          statements: summary.statements.pct,
          branches: summary.branches.pct,
          functions: summary.functions.pct,
          lines: summary.lines.pct
        };
      }
    } catch (error) {
      // Coverage data not available, return defaults
    }

    return defaultCoverage;
  }

  /**
   * Get appropriate emoji for insight type and severity
   */
  private getInsightEmoji(type: string, severity: string): string {
    const emojiMap: Record<string, Record<string, string>> = {
      performance: {
        low: '⚡',
        medium: '🐌',
        high: '🚨',
        critical: '💥'
      },
      reliability: {
        low: '🔄',
        medium: '🎲',
        high: '❌',
        critical: '💥'
      },
      coverage: {
        low: '📊',
        medium: '📉',
        high: '⚠️',
        critical: '🚨'
      },
      optimization: {
        low: '💡',
        medium: '⚡',
        high: '🚀',
        critical: '💎'
      }
    };

    return emojiMap[type]?.[severity] || '🔍';
  }

  /**
   * Generate actionable recommendations based on AI insights
   */
  private generateActionableRecommendations(insights: any[]): void {
    const criticalInsights = insights.filter(i => i.severity === 'critical' || i.severity === 'high');

    if (criticalInsights.length > 0) {
      console.log('\n🎯 Immediate Action Recommended:');

      criticalInsights.slice(0, 3).forEach((insight, index) => {
        console.log(`   ${index + 1}. ${insight.recommendation}`);
        console.log(`      └─ Affects: ${insight.affectedTests.length} test(s)`);
      });
    }

    // Performance optimization suggestions
    const performanceInsights = insights.filter(i => i.type === 'performance');
    if (performanceInsights.length > 0) {
      console.log('\n⚡ Performance Optimization Opportunities:');
      console.log(`   • ${performanceInsights.length} test(s) showing performance degradation`);
      console.log('   • Run detailed performance analysis: npm run test:performance');
    }

    // Reliability improvements
    const reliabilityInsights = insights.filter(i => i.type === 'reliability');
    if (reliabilityInsights.length > 0) {
      console.log('\n🎯 Test Reliability Improvements:');
      console.log(`   • ${reliabilityInsights.length} flaky test(s) detected`);
      console.log('   • Consider implementing retry logic or improving test isolation');
    }
  }

  /**
   * Export detailed analysis report
   */
  private exportDetailedReport(
    results: AggregatedResult,
    insights: any[],
    stats: any
  ): void {
    if (!this.options.outputPath) return;

    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    const reportPath = path.join(this.options.outputPath, `ai-analysis-${timestamp}.json`);

    const report = {
      metadata: {
        generatedAt: new Date().toISOString(),
        totalTests: results.numTotalTests,
        passedTests: results.numPassedTests,
        failedTests: results.numFailedTests,
        duration: results.startTime ? Date.now() - results.startTime : 0
      },
      aiAnalysis: {
        statistics: stats,
        insights: insights.map(insight => ({
          ...insight,
          // Remove sensitive data for export
          auditTrail: insight.auditTrail.map((entry: any) => ({
            action: entry.action,
            timestamp: entry.timestamp,
            aiConfidence: entry.aiConfidence
          }))
        })),
        testExecutions: this.testExecutions.length
      },
      recommendations: this.generateRecommendationsList(insights)
    };

    try {
      fs.writeFileSync(reportPath, JSON.stringify(report, null, 2));
      console.log(`\n📄 Detailed AI analysis report: ${reportPath}`);
    } catch (error) {
      console.warn('⚠️  Failed to write AI analysis report:', error);
    }
  }

  /**
   * Generate structured list of recommendations
   */
  private generateRecommendationsList(insights: any[]): Array<{
    priority: 'critical' | 'high' | 'medium' | 'low';
    category: string;
    action: string;
    impact: string;
    effort: string;
  }> {
    const recommendations: Array<{
      priority: 'critical' | 'high' | 'medium' | 'low';
      category: string;
      action: string;
      impact: string;
      effort: string;
    }> = [];

    insights.forEach(insight => {
      recommendations.push({
        priority: insight.severity,
        category: insight.type,
        action: insight.recommendation,
        impact: insight.impact,
        effort: this.estimateEffort(insight)
      });
    });

    return recommendations.sort((a, b) => {
      const priorityOrder = { critical: 0, high: 1, medium: 2, low: 3 };
      return priorityOrder[a.priority] - priorityOrder[b.priority];
    });
  }

  /**
   * Estimate effort required to address insight
   */
  private estimateEffort(insight: any): 'low' | 'medium' | 'high' {
    // Simple heuristic based on insight type and affected tests
    const affectedCount = insight.affectedTests.length;

    if (insight.type === 'performance' && affectedCount <= 3) return 'low';
    if (insight.type === 'reliability' && affectedCount <= 5) return 'medium';
    if (insight.type === 'coverage') return 'low';

    return affectedCount > 10 ? 'high' : 'medium';
  }
}

/**
 * Create configured reporter instance
 */
export function createAIReporter(options?: {
  outputPath?: string;
  enableRealTimeAnalysis?: boolean;
  minimumTestsForAnalysis?: number;
}): JestAIReporter {
  return new JestAIReporter({}, options);
}
