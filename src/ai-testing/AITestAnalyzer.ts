/**
 * AI-Enhanced Test Analysis Framework for FXML4 TDD
 *
 * Provides intelligent test analysis, optimization recommendations,
 * and predictive insights while maintaining strict audit trails
 * and human-in-the-loop validation for financial trading systems.
 */

export interface TestExecution {
  testName: string;
  filePath: string;
  duration: number;
  status: 'passed' | 'failed' | 'skipped';
  timestamp: number;
  errorMessage?: string;
  stackTrace?: string;
  codeChanges?: string[];
  coverage: {
    statements: number;
    branches: number;
    functions: number;
    lines: number;
  };
}

export interface TestAnalysisInsight {
  type: 'optimization' | 'performance' | 'reliability' | 'coverage';
  severity: 'low' | 'medium' | 'high' | 'critical';
  title: string;
  description: string;
  recommendation: string;
  confidence: number; // 0-100
  impact: 'low' | 'medium' | 'high';
  affectedTests: string[];
  aiGeneratedAt: number;
  humanReviewed: boolean;
  humanApproved?: boolean;
  auditTrail: AuditTrailEntry[];
}

export interface AuditTrailEntry {
  action: string;
  user?: string;
  timestamp: number;
  details: Record<string, any>;
  aiConfidence?: number;
}

export interface PredictiveModel {
  modelType: 'failure_prediction' | 'performance_regression' | 'coverage_gap';
  accuracy: number;
  lastTraining: number;
  features: string[];
  predictions: ModelPrediction[];
}

export interface ModelPrediction {
  testName: string;
  prediction: 'likely_fail' | 'performance_regression' | 'coverage_drop';
  confidence: number;
  reasoning: string[];
  suggestedActions: string[];
}

/**
 * Core AI Test Analyzer with strict safety controls for financial systems
 */
export class AITestAnalyzer {
  private testHistory: TestExecution[] = [];
  private insights: TestAnalysisInsight[] = [];
  private models: Map<string, PredictiveModel> = new Map();
  private auditLog: AuditTrailEntry[] = [];

  constructor(
    private config: {
      maxHistorySize: number;
      minConfidenceThreshold: number;
      enablePredictiveModels: boolean;
      requireHumanApproval: boolean;
      auditRetentionDays: number;
    } = {
      maxHistorySize: 10000,
      minConfidenceThreshold: 75,
      enablePredictiveModels: true,
      requireHumanApproval: true,
      auditRetentionDays: 365
    }
  ) {
    this.logAuditEvent('analyzer_initialized', { config });
  }

  /**
   * Record test execution for analysis
   */
  recordTestExecution(execution: TestExecution): void {
    this.testHistory.push(execution);

    // Maintain history size limit
    if (this.testHistory.length > this.config.maxHistorySize) {
      this.testHistory = this.testHistory.slice(-this.config.maxHistorySize);
    }

    this.logAuditEvent('test_execution_recorded', {
      testName: execution.testName,
      status: execution.status,
      duration: execution.duration
    });

    // Trigger analysis for patterns
    this.analyzeTestPatterns();
  }

  /**
   * Analyze test execution patterns and generate insights
   */
  private analyzeTestPatterns(): void {
    if (this.testHistory.length < 10) return; // Need minimum data

    const recentExecutions = this.testHistory.slice(-100);

    // Performance analysis
    this.analyzePerformancePatterns(recentExecutions);

    // Reliability analysis
    this.analyzeReliabilityPatterns(recentExecutions);

    // Coverage analysis
    this.analyzeCoveragePatterns(recentExecutions);

    // Predictive analysis (if enabled)
    if (this.config.enablePredictiveModels) {
      this.updatePredictiveModels(recentExecutions);
    }
  }

  /**
   * Analyze performance patterns and identify optimization opportunities
   */
  private analyzePerformancePatterns(executions: TestExecution[]): void {
    const performanceData = new Map<string, number[]>();

    // Group execution times by test
    executions.forEach(exec => {
      if (!performanceData.has(exec.testName)) {
        performanceData.set(exec.testName, []);
      }
      performanceData.get(exec.testName)!.push(exec.duration);
    });

    // Identify performance regressions
    performanceData.forEach((durations, testName) => {
      if (durations.length < 5) return;

      const recent = durations.slice(-5);
      const historical = durations.slice(0, -5);

      const recentAvg = recent.reduce((a, b) => a + b, 0) / recent.length;
      const historicalAvg = historical.reduce((a, b) => a + b, 0) / historical.length;

      const regressionThreshold = historicalAvg * 1.5; // 50% increase

      if (recentAvg > regressionThreshold) {
        this.addInsight({
          type: 'performance',
          severity: recentAvg > historicalAvg * 2 ? 'high' : 'medium',
          title: `Performance Regression Detected: ${testName}`,
          description: `Test execution time increased by ${((recentAvg - historicalAvg) / historicalAvg * 100).toFixed(1)}%`,
          recommendation: 'Review recent code changes that may have introduced performance bottlenecks. Consider optimizing test setup/teardown or the code under test.',
          confidence: 85,
          impact: 'medium',
          affectedTests: [testName],
          aiGeneratedAt: Date.now(),
          humanReviewed: false,
          auditTrail: []
        });
      }
    });
  }

  /**
   * Analyze reliability patterns (flaky tests, frequent failures)
   */
  private analyzeReliabilityPatterns(executions: TestExecution[]): void {
    const reliabilityData = new Map<string, { passed: number; failed: number; total: number }>();

    executions.forEach(exec => {
      if (!reliabilityData.has(exec.testName)) {
        reliabilityData.set(exec.testName, { passed: 0, failed: 0, total: 0 });
      }

      const data = reliabilityData.get(exec.testName)!;
      data.total++;

      if (exec.status === 'passed') {
        data.passed++;
      } else if (exec.status === 'failed') {
        data.failed++;
      }
    });

    // Identify flaky tests
    reliabilityData.forEach((data, testName) => {
      if (data.total < 5) return;

      const failureRate = data.failed / data.total;
      const flakyThreshold = 0.1; // 10% failure rate indicates flaky test

      if (failureRate > flakyThreshold && failureRate < 0.9) {
        this.addInsight({
          type: 'reliability',
          severity: failureRate > 0.3 ? 'high' : 'medium',
          title: `Flaky Test Detected: ${testName}`,
          description: `Test has ${(failureRate * 100).toFixed(1)}% failure rate, indicating potential flakiness`,
          recommendation: 'Investigate non-deterministic behavior, timing issues, or external dependencies. Consider adding retry logic or improving test isolation.',
          confidence: 90,
          impact: 'high',
          affectedTests: [testName],
          aiGeneratedAt: Date.now(),
          humanReviewed: false,
          auditTrail: []
        });
      }
    });
  }

  /**
   * Analyze coverage patterns and identify gaps
   */
  private analyzeCoveragePatterns(executions: TestExecution[]): void {
    const coverageByFile = new Map<string, number[]>();

    executions.forEach(exec => {
      const filePath = exec.filePath.replace(/\.test\.[jt]s$/, '');
      if (!coverageByFile.has(filePath)) {
        coverageByFile.set(filePath, []);
      }
      coverageByFile.get(filePath)!.push(exec.coverage.statements);
    });

    // Identify coverage drops
    coverageByFile.forEach((coverageHistory, filePath) => {
      if (coverageHistory.length < 5) return;

      const recent = coverageHistory.slice(-3);
      const historical = coverageHistory.slice(0, -3);

      const recentAvg = recent.reduce((a, b) => a + b, 0) / recent.length;
      const historicalAvg = historical.reduce((a, b) => a + b, 0) / historical.length;

      const coverageDropThreshold = 5; // 5% drop

      if (historicalAvg - recentAvg > coverageDropThreshold) {
        this.addInsight({
          type: 'coverage',
          severity: 'medium',
          title: `Coverage Drop Detected: ${filePath}`,
          description: `Statement coverage decreased by ${(historicalAvg - recentAvg).toFixed(1)}%`,
          recommendation: 'Review recent changes to ensure adequate test coverage is maintained. Consider adding tests for new code paths.',
          confidence: 80,
          impact: 'medium',
          affectedTests: executions.filter(e => e.filePath.includes(filePath)).map(e => e.testName),
          aiGeneratedAt: Date.now(),
          humanReviewed: false,
          auditTrail: []
        });
      }
    });
  }

  /**
   * Update predictive models based on execution data
   */
  private updatePredictiveModels(executions: TestExecution[]): void {
    // This is a simplified ML approach - in production, you'd use proper ML libraries
    const failurePatterns = this.identifyFailurePatterns(executions);

    failurePatterns.forEach(pattern => {
      const prediction: ModelPrediction = {
        testName: pattern.testName,
        prediction: 'likely_fail',
        confidence: pattern.confidence,
        reasoning: pattern.indicators,
        suggestedActions: [
          'Review recent code changes affecting this test',
          'Check for environmental dependencies',
          'Validate test data assumptions'
        ]
      };

      // Update or create failure prediction model
      let model = this.models.get('failure_prediction');
      if (!model) {
        model = {
          modelType: 'failure_prediction',
          accuracy: 0,
          lastTraining: Date.now(),
          features: ['historical_failure_rate', 'recent_changes', 'execution_time_variance'],
          predictions: []
        };
        this.models.set('failure_prediction', model);
      }

      model.predictions.push(prediction);
      model.lastTraining = Date.now();

      // Only keep recent predictions
      model.predictions = model.predictions.slice(-50);
    });
  }

  /**
   * Identify patterns that may indicate future test failures
   */
  private identifyFailurePatterns(executions: TestExecution[]): Array<{
    testName: string;
    confidence: number;
    indicators: string[];
  }> {
    const patterns: Array<{ testName: string; confidence: number; indicators: string[] }> = [];
    const testData = new Map<string, TestExecution[]>();

    // Group executions by test
    executions.forEach(exec => {
      if (!testData.has(exec.testName)) {
        testData.set(exec.testName, []);
      }
      testData.get(exec.testName)!.push(exec);
    });

    testData.forEach((history, testName) => {
      if (history.length < 10) return;

      const indicators: string[] = [];
      let confidence = 0;

      // Check for increasing execution time variance
      const durations = history.map(h => h.duration);
      const variance = this.calculateVariance(durations);
      const recentVariance = this.calculateVariance(durations.slice(-5));

      if (recentVariance > variance * 1.5) {
        indicators.push('Increasing execution time variance detected');
        confidence += 20;
      }

      // Check for error message patterns
      const recentErrors = history.slice(-5).filter(h => h.errorMessage);
      if (recentErrors.length > 0) {
        indicators.push('Recent error messages indicate potential issues');
        confidence += 30;
      }

      // Check for code change correlation with failures
      const failuresWithChanges = history.filter(h => h.status === 'failed' && h.codeChanges?.length);
      if (failuresWithChanges.length > history.filter(h => h.status === 'failed').length * 0.7) {
        indicators.push('Failures correlate with code changes');
        confidence += 25;
      }

      if (confidence >= this.config.minConfidenceThreshold) {
        patterns.push({ testName, confidence, indicators });
      }
    });

    return patterns;
  }

  /**
   * Add insight with proper audit trail
   */
  private addInsight(insight: Omit<TestAnalysisInsight, 'auditTrail'>): void {
    const auditTrail: AuditTrailEntry[] = [
      {
        action: 'insight_generated',
        timestamp: Date.now(),
        details: {
          type: insight.type,
          confidence: insight.confidence,
          aiModel: 'pattern_analysis_v1.0'
        },
        aiConfidence: insight.confidence
      }
    ];

    this.insights.push({
      ...insight,
      auditTrail
    });

    this.logAuditEvent('insight_generated', {
      type: insight.type,
      severity: insight.severity,
      confidence: insight.confidence,
      affectedTests: insight.affectedTests.length
    });
  }

  /**
   * Get insights with optional filtering
   */
  getInsights(filter?: {
    type?: TestAnalysisInsight['type'];
    severity?: TestAnalysisInsight['severity'];
    humanReviewed?: boolean;
    minConfidence?: number;
  }): TestAnalysisInsight[] {
    let filtered = this.insights;

    if (filter) {
      if (filter.type) filtered = filtered.filter(i => i.type === filter.type);
      if (filter.severity) filtered = filtered.filter(i => i.severity === filter.severity);
      if (filter.humanReviewed !== undefined) filtered = filtered.filter(i => i.humanReviewed === filter.humanReviewed);
      if (filter.minConfidence) filtered = filtered.filter(i => i.confidence >= filter.minConfidence);
    }

    return filtered.sort((a, b) => {
      // Sort by severity (critical first) and confidence
      const severityOrder = { critical: 0, high: 1, medium: 2, low: 3 };
      const severityDiff = severityOrder[a.severity] - severityOrder[b.severity];
      if (severityDiff !== 0) return severityDiff;
      return b.confidence - a.confidence;
    });
  }

  /**
   * Approve or reject AI-generated insight
   */
  approveInsight(insightIndex: number, approved: boolean, reviewer: string, notes?: string): void {
    if (insightIndex < 0 || insightIndex >= this.insights.length) {
      throw new Error('Invalid insight index');
    }

    const insight = this.insights[insightIndex];
    insight.humanReviewed = true;
    insight.humanApproved = approved;

    insight.auditTrail.push({
      action: approved ? 'insight_approved' : 'insight_rejected',
      user: reviewer,
      timestamp: Date.now(),
      details: { notes }
    });

    this.logAuditEvent(approved ? 'insight_approved' : 'insight_rejected', {
      insightType: insight.type,
      reviewer,
      notes
    });
  }

  /**
   * Get test execution statistics
   */
  getTestStatistics(): {
    totalExecutions: number;
    averageDuration: number;
    passRate: number;
    flakyTests: number;
    performanceRegressions: number;
    coverageDrops: number;
  } {
    const total = this.testHistory.length;
    const passed = this.testHistory.filter(t => t.status === 'passed').length;
    const avgDuration = this.testHistory.reduce((sum, t) => sum + t.duration, 0) / total;

    const insights = this.getInsights({ humanApproved: true });
    const flakyTests = insights.filter(i => i.type === 'reliability').length;
    const performanceRegressions = insights.filter(i => i.type === 'performance').length;
    const coverageDrops = insights.filter(i => i.type === 'coverage').length;

    return {
      totalExecutions: total,
      averageDuration: avgDuration,
      passRate: passed / total,
      flakyTests,
      performanceRegressions,
      coverageDrops
    };
  }

  /**
   * Log audit event
   */
  private logAuditEvent(action: string, details: Record<string, any>): void {
    this.auditLog.push({
      action,
      timestamp: Date.now(),
      details
    });

    // Clean old audit logs
    const retentionMs = this.config.auditRetentionDays * 24 * 60 * 60 * 1000;
    const cutoff = Date.now() - retentionMs;
    this.auditLog = this.auditLog.filter(entry => entry.timestamp > cutoff);
  }

  /**
   * Get audit log
   */
  getAuditLog(limit?: number): AuditTrailEntry[] {
    const log = [...this.auditLog].reverse(); // Most recent first
    return limit ? log.slice(0, limit) : log;
  }

  /**
   * Calculate variance for array of numbers
   */
  private calculateVariance(numbers: number[]): number {
    if (numbers.length === 0) return 0;

    const mean = numbers.reduce((sum, num) => sum + num, 0) / numbers.length;
    const squaredDiffs = numbers.map(num => Math.pow(num - mean, 2));
    return squaredDiffs.reduce((sum, diff) => sum + diff, 0) / numbers.length;
  }

  /**
   * Export analysis data for external tools
   */
  exportAnalysisData(): {
    testHistory: TestExecution[];
    insights: TestAnalysisInsight[];
    statistics: ReturnType<AITestAnalyzer['getTestStatistics']>;
    auditLog: AuditTrailEntry[];
    exportedAt: number;
  } {
    return {
      testHistory: this.testHistory,
      insights: this.insights,
      statistics: this.getTestStatistics(),
      auditLog: this.auditLog,
      exportedAt: Date.now()
    };
  }
}

/**
 * Singleton instance for global access
 */
export const aiTestAnalyzer = new AITestAnalyzer();
