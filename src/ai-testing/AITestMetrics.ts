/**
 * AI Test Metrics and Validation System
 *
 * Measures the effectiveness and impact of AI enhancements on TDD workflows,
 * providing quantitative validation that AI is improving testing processes
 * while maintaining financial system reliability standards.
 */

export interface MetricSnapshot {
  timestamp: number;
  period: 'hour' | 'day' | 'week' | 'month';
  testExecution: {
    totalTests: number;
    passRate: number;
    averageDuration: number;
    flakyTestCount: number;
    coveragePercentage: number;
  };
  aiAnalysis: {
    insightsGenerated: number;
    insightsApproved: number;
    insightsImplemented: number;
    averageConfidence: number;
    falsePositiveRate: number;
  };
  performance: {
    testSelectionTime: number;
    analysisTime: number;
    reportGenerationTime: number;
    systemResourceUsage: number;
  };
  qualityImpact: {
    bugsFoundByAI: number;
    bugsFoundByHumans: number;
    timeToDetection: number;
    preventedIssues: number;
  };
  developerExperience: {
    timeToInsight: number;
    actionableRecommendations: number;
    developerSatisfactionScore: number;
    adoptionRate: number;
  };
}

export interface AIEffectivenessReport {
  period: { start: number; end: number };
  overallScore: number; // 0-100
  categories: {
    testOptimization: EffectivenessCategory;
    bugDetection: EffectivenessCategory;
    performanceImprovement: EffectivenessCategory;
    developerProductivity: EffectivenessCategory;
    riskReduction: EffectivenessCategory;
  };
  trends: {
    improvement: number; // percentage change
    trendDirection: 'improving' | 'stable' | 'declining';
    keyFactors: string[];
  };
  recommendations: string[];
}

export interface EffectivenessCategory {
  score: number; // 0-100
  metrics: Record<string, number>;
  achievements: string[];
  concerns: string[];
}

export interface AIValidationResult {
  passed: boolean;
  score: number;
  criteria: {
    accuracy: { score: number; details: string };
    performance: { score: number; details: string };
    reliability: { score: number; details: string };
    usability: { score: number; details: string };
    safety: { score: number; details: string };
  };
  recommendations: string[];
  gateDecision: 'proceed' | 'investigate' | 'halt';
}

export interface BenchmarkComparison {
  baseline: MetricSnapshot;
  current: MetricSnapshot;
  improvements: Record<string, {
    value: number;
    percentage: number;
    significance: 'major' | 'moderate' | 'minor' | 'none';
  }>;
  regressions: Record<string, {
    value: number;
    percentage: number;
    severity: 'critical' | 'high' | 'medium' | 'low';
  }>;
}

/**
 * Core metrics collection and validation system for AI testing enhancements
 */
export class AITestMetrics {
  private snapshots: MetricSnapshot[] = [];
  private baseline: MetricSnapshot | null = null;
  private targetKPIs: Record<string, number> = {};
  private validationHistory: AIValidationResult[] = [];

  constructor() {
    this.initializeTargetKPIs();
  }

  /**
   * Record a metric snapshot
   */
  recordSnapshot(snapshot: Omit<MetricSnapshot, 'timestamp'>): void {
    const fullSnapshot: MetricSnapshot = {
      ...snapshot,
      timestamp: Date.now()
    };

    this.snapshots.push(fullSnapshot);

    // Set baseline if this is the first snapshot
    if (!this.baseline && snapshot.period === 'day') {
      this.baseline = fullSnapshot;
    }

    // Keep only last 1000 snapshots
    if (this.snapshots.length > 1000) {
      this.snapshots = this.snapshots.slice(-1000);
    }

    this.triggerValidationIfNeeded(fullSnapshot);
  }

  /**
   * Generate comprehensive effectiveness report
   */
  generateEffectivenessReport(
    period: { start: number; end: number }
  ): AIEffectivenessReport {
    const periodSnapshots = this.snapshots.filter(
      s => s.timestamp >= period.start && s.timestamp <= period.end
    );

    if (periodSnapshots.length === 0) {
      throw new Error('No data available for the specified period');
    }

    const latest = periodSnapshots[periodSnapshots.length - 1];
    const earliest = periodSnapshots[0];

    // Calculate category scores
    const categories = {
      testOptimization: this.evaluateTestOptimization(periodSnapshots),
      bugDetection: this.evaluateBugDetection(periodSnapshots),
      performanceImprovement: this.evaluatePerformanceImprovement(periodSnapshots),
      developerProductivity: this.evaluateDeveloperProductivity(periodSnapshots),
      riskReduction: this.evaluateRiskReduction(periodSnapshots)
    };

    // Calculate overall score
    const overallScore = Object.values(categories).reduce((sum, cat) => sum + cat.score, 0) / 5;

    // Calculate trends
    const trends = this.calculateTrends(earliest, latest);

    // Generate recommendations
    const recommendations = this.generateRecommendations(categories, trends);

    return {
      period,
      overallScore,
      categories,
      trends,
      recommendations
    };
  }

  /**
   * Run validation against success criteria
   */
  validateAIEffectiveness(): AIValidationResult {
    const latestSnapshot = this.snapshots[this.snapshots.length - 1];
    if (!latestSnapshot || !this.baseline) {
      throw new Error('Insufficient data for validation');
    }

    const comparison = this.compareWithBaseline(latestSnapshot);

    // Evaluate each criterion
    const criteria = {
      accuracy: this.evaluateAccuracy(latestSnapshot, comparison),
      performance: this.evaluatePerformance(latestSnapshot, comparison),
      reliability: this.evaluateReliability(latestSnapshot, comparison),
      usability: this.evaluateUsability(latestSnapshot, comparison),
      safety: this.evaluateSafety(latestSnapshot, comparison)
    };

    const overallScore = Object.values(criteria).reduce((sum, c) => sum + c.score, 0) / 5;

    // Determine gate decision
    let gateDecision: AIValidationResult['gateDecision'] = 'proceed';
    if (overallScore < 60) gateDecision = 'halt';
    else if (overallScore < 75) gateDecision = 'investigate';

    const recommendations = this.generateValidationRecommendations(criteria, overallScore);

    const result: AIValidationResult = {
      passed: overallScore >= 75,
      score: overallScore,
      criteria,
      recommendations,
      gateDecision
    };

    this.validationHistory.push(result);
    return result;
  }

  /**
   * Compare current metrics with baseline
   */
  compareWithBaseline(current: MetricSnapshot): BenchmarkComparison {
    if (!this.baseline) {
      throw new Error('No baseline established');
    }

    const improvements: BenchmarkComparison['improvements'] = {};
    const regressions: BenchmarkComparison['regressions'] = {};

    // Test execution improvements
    this.compareMetric('testExecutionTime',
                      this.baseline.testExecution.averageDuration,
                      current.testExecution.averageDuration,
                      improvements, regressions, true); // Lower is better

    this.compareMetric('passRate',
                      this.baseline.testExecution.passRate,
                      current.testExecution.passRate,
                      improvements, regressions, false);

    this.compareMetric('coverage',
                      this.baseline.testExecution.coveragePercentage,
                      current.testExecution.coveragePercentage,
                      improvements, regressions, false);

    // AI analysis effectiveness
    this.compareMetric('aiConfidence',
                      this.baseline.aiAnalysis.averageConfidence,
                      current.aiAnalysis.averageConfidence,
                      improvements, regressions, false);

    this.compareMetric('falsePositiveRate',
                      this.baseline.aiAnalysis.falsePositiveRate,
                      current.aiAnalysis.falsePositiveRate,
                      improvements, regressions, true);

    // Developer experience
    this.compareMetric('timeToInsight',
                      this.baseline.developerExperience.timeToInsight,
                      current.developerExperience.timeToInsight,
                      improvements, regressions, true);

    return {
      baseline: this.baseline,
      current,
      improvements,
      regressions
    };
  }

  /**
   * Get historical trends data for visualization
   */
  getHistoricalTrends(
    metric: string,
    period: 'day' | 'week' | 'month',
    limit: number = 30
  ): Array<{ timestamp: number; value: number }> {
    return this.snapshots
      .filter(s => s.period === period)
      .slice(-limit)
      .map(s => ({
        timestamp: s.timestamp,
        value: this.extractMetricValue(s, metric)
      }));
  }

  /**
   * Get current AI performance dashboard data
   */
  getDashboardData(): {
    currentScore: number;
    trends: Record<string, { value: number; change: number; trend: 'up' | 'down' | 'stable' }>;
    recentValidations: AIValidationResult[];
    alerts: Array<{ level: 'info' | 'warning' | 'error'; message: string }>;
  } {
    const latest = this.snapshots[this.snapshots.length - 1];
    const previous = this.snapshots[this.snapshots.length - 2];

    if (!latest) {
      throw new Error('No metrics data available');
    }

    const currentScore = this.calculateOverallScore(latest);

    const trends = previous ? {
      testSpeed: this.calculateTrendMetric(previous.testExecution.averageDuration, latest.testExecution.averageDuration, true),
      accuracy: this.calculateTrendMetric(previous.aiAnalysis.averageConfidence, latest.aiAnalysis.averageConfidence, false),
      productivity: this.calculateTrendMetric(previous.developerExperience.timeToInsight, latest.developerExperience.timeToInsight, true),
      quality: this.calculateTrendMetric(previous.testExecution.passRate, latest.testExecution.passRate, false)
    } : {};

    const recentValidations = this.validationHistory.slice(-5);

    const alerts = this.generateAlerts(latest);

    return {
      currentScore,
      trends,
      recentValidations,
      alerts
    };
  }

  /**
   * Export metrics for external analysis
   */
  exportMetrics(format: 'json' | 'csv' = 'json'): string {
    const data = {
      baseline: this.baseline,
      snapshots: this.snapshots,
      validations: this.validationHistory,
      targetKPIs: this.targetKPIs,
      exportedAt: new Date().toISOString()
    };

    if (format === 'json') {
      return JSON.stringify(data, null, 2);
    } else {
      // Simple CSV format for snapshots
      const headers = [
        'timestamp', 'totalTests', 'passRate', 'averageDuration',
        'insightsGenerated', 'averageConfidence', 'timeToInsight'
      ];

      const rows = this.snapshots.map(s => [
        s.timestamp,
        s.testExecution.totalTests,
        s.testExecution.passRate,
        s.testExecution.averageDuration,
        s.aiAnalysis.insightsGenerated,
        s.aiAnalysis.averageConfidence,
        s.developerExperience.timeToInsight
      ].join(','));

      return [headers.join(','), ...rows].join('\n');
    }
  }

  // Private helper methods

  private initializeTargetKPIs(): void {
    this.targetKPIs = {
      testExecutionImprovement: 15, // 15% faster test execution
      coverageIncrease: 5, // 5% increase in coverage
      bugDetectionImprovement: 25, // 25% more bugs found
      falsePositiveReduction: 30, // 30% reduction in false positives
      developerSatisfaction: 80, // 80% satisfaction score
      aiInsightAccuracy: 85, // 85% accuracy for AI insights
      timeToInsightReduction: 40 // 40% faster time to insight
    };
  }

  private evaluateTestOptimization(snapshots: MetricSnapshot[]): EffectivenessCategory {
    const latest = snapshots[snapshots.length - 1];
    const metrics = {
      testSpeed: latest.testExecution.averageDuration,
      coverage: latest.testExecution.coveragePercentage,
      flakyTestReduction: latest.testExecution.flakyTestCount
    };

    let score = 0;
    const achievements: string[] = [];
    const concerns: string[] = [];

    // Evaluate test speed improvement
    if (this.baseline) {
      const speedImprovement = (this.baseline.testExecution.averageDuration - latest.testExecution.averageDuration) /
                              this.baseline.testExecution.averageDuration * 100;
      if (speedImprovement >= this.targetKPIs.testExecutionImprovement) {
        score += 30;
        achievements.push(`Test execution improved by ${speedImprovement.toFixed(1)}%`);
      } else if (speedImprovement > 0) {
        score += 15;
      } else {
        concerns.push('Test execution speed has not improved');
      }
    }

    // Evaluate coverage
    if (latest.testExecution.coveragePercentage >= 85) {
      score += 25;
      achievements.push(`High test coverage: ${latest.testExecution.coveragePercentage}%`);
    } else if (latest.testExecution.coveragePercentage >= 75) {
      score += 15;
    } else {
      concerns.push('Test coverage below 75%');
    }

    // Evaluate flaky test reduction
    if (latest.testExecution.flakyTestCount <= 5) {
      score += 25;
      achievements.push('Low flaky test count');
    } else if (latest.testExecution.flakyTestCount <= 10) {
      score += 15;
    } else {
      concerns.push('High flaky test count detected');
    }

    // Evaluate pass rate
    if (latest.testExecution.passRate >= 0.95) {
      score += 20;
      achievements.push(`High pass rate: ${(latest.testExecution.passRate * 100).toFixed(1)}%`);
    } else if (latest.testExecution.passRate >= 0.90) {
      score += 10;
    } else {
      concerns.push('Pass rate below 90%');
    }

    return {
      score: Math.min(100, score),
      metrics,
      achievements,
      concerns
    };
  }

  private evaluateBugDetection(snapshots: MetricSnapshot[]): EffectivenessCategory {
    const latest = snapshots[snapshots.length - 1];
    const metrics = {
      aiBugsFound: latest.qualityImpact.bugsFoundByAI,
      humanBugsFound: latest.qualityImpact.bugsFoundByHumans,
      timeToDetection: latest.qualityImpact.timeToDetection,
      preventedIssues: latest.qualityImpact.preventedIssues
    };

    let score = 0;
    const achievements: string[] = [];
    const concerns: string[] = [];

    const totalBugs = metrics.aiBugsFound + metrics.humanBugsFound;
    const aiDetectionRate = totalBugs > 0 ? metrics.aiBugsFound / totalBugs : 0;

    if (aiDetectionRate >= 0.6) {
      score += 30;
      achievements.push(`AI detects ${(aiDetectionRate * 100).toFixed(1)}% of bugs`);
    } else if (aiDetectionRate >= 0.4) {
      score += 20;
    } else {
      concerns.push('AI bug detection rate below 40%');
    }

    if (metrics.timeToDetection <= 30) {
      score += 25;
      achievements.push(`Fast bug detection: ${metrics.timeToDetection} minutes`);
    } else if (metrics.timeToDetection <= 60) {
      score += 15;
    }

    if (metrics.preventedIssues >= 5) {
      score += 25;
      achievements.push(`${metrics.preventedIssues} issues prevented`);
    }

    if (latest.aiAnalysis.falsePositiveRate <= 0.1) {
      score += 20;
      achievements.push('Low false positive rate');
    } else if (latest.aiAnalysis.falsePositiveRate <= 0.2) {
      score += 10;
    } else {
      concerns.push('High false positive rate');
    }

    return {
      score: Math.min(100, score),
      metrics,
      achievements,
      concerns
    };
  }

  private evaluatePerformanceImprovement(snapshots: MetricSnapshot[]): EffectivenessCategory {
    const latest = snapshots[snapshots.length - 1];
    const metrics = {
      testSelectionTime: latest.performance.testSelectionTime,
      analysisTime: latest.performance.analysisTime,
      resourceUsage: latest.performance.systemResourceUsage
    };

    let score = 0;
    const achievements: string[] = [];
    const concerns: string[] = [];

    if (metrics.testSelectionTime <= 5) {
      score += 25;
      achievements.push('Fast test selection');
    } else if (metrics.testSelectionTime <= 10) {
      score += 15;
    } else {
      concerns.push('Slow test selection');
    }

    if (metrics.analysisTime <= 30) {
      score += 25;
      achievements.push('Fast AI analysis');
    } else if (metrics.analysisTime <= 60) {
      score += 15;
    } else {
      concerns.push('Slow AI analysis');
    }

    if (metrics.resourceUsage <= 70) {
      score += 25;
      achievements.push('Efficient resource usage');
    } else if (metrics.resourceUsage <= 85) {
      score += 15;
    } else {
      concerns.push('High resource usage');
    }

    // Performance stability
    const recentSnapshots = snapshots.slice(-5);
    const performanceVariance = this.calculateVariance(
      recentSnapshots.map(s => s.performance.analysisTime)
    );

    if (performanceVariance <= 10) {
      score += 25;
      achievements.push('Stable performance');
    } else if (performanceVariance <= 20) {
      score += 15;
    } else {
      concerns.push('Unstable performance');
    }

    return {
      score: Math.min(100, score),
      metrics,
      achievements,
      concerns
    };
  }

  private evaluateDeveloperProductivity(snapshots: MetricSnapshot[]): EffectivenessCategory {
    const latest = snapshots[snapshots.length - 1];
    const metrics = {
      timeToInsight: latest.developerExperience.timeToInsight,
      actionableRecommendations: latest.developerExperience.actionableRecommendations,
      satisfactionScore: latest.developerExperience.developerSatisfactionScore,
      adoptionRate: latest.developerExperience.adoptionRate
    };

    let score = 0;
    const achievements: string[] = [];
    const concerns: string[] = [];

    if (metrics.satisfactionScore >= this.targetKPIs.developerSatisfaction) {
      score += 30;
      achievements.push(`High satisfaction: ${metrics.satisfactionScore}%`);
    } else if (metrics.satisfactionScore >= 70) {
      score += 20;
    } else {
      concerns.push('Low developer satisfaction');
    }

    if (metrics.adoptionRate >= 80) {
      score += 25;
      achievements.push('High adoption rate');
    } else if (metrics.adoptionRate >= 60) {
      score += 15;
    } else {
      concerns.push('Low adoption rate');
    }

    if (metrics.timeToInsight <= 10) {
      score += 25;
      achievements.push('Fast insights delivery');
    } else if (metrics.timeToInsight <= 20) {
      score += 15;
    }

    if (metrics.actionableRecommendations >= 5) {
      score += 20;
      achievements.push('High number of actionable insights');
    }

    return {
      score: Math.min(100, score),
      metrics,
      achievements,
      concerns
    };
  }

  private evaluateRiskReduction(snapshots: MetricSnapshot[]): EffectivenessCategory {
    const latest = snapshots[snapshots.length - 1];
    const metrics = {
      preventedIssues: latest.qualityImpact.preventedIssues,
      falsePositiveRate: latest.aiAnalysis.falsePositiveRate,
      insightAccuracy: latest.aiAnalysis.averageConfidence
    };

    let score = 0;
    const achievements: string[] = [];
    const concerns: string[] = [];

    if (metrics.preventedIssues >= 10) {
      score += 30;
      achievements.push(`${metrics.preventedIssues} issues prevented`);
    } else if (metrics.preventedIssues >= 5) {
      score += 20;
    }

    if (metrics.insightAccuracy >= this.targetKPIs.aiInsightAccuracy) {
      score += 35;
      achievements.push(`High AI accuracy: ${metrics.insightAccuracy}%`);
    } else if (metrics.insightAccuracy >= 75) {
      score += 25;
    } else {
      concerns.push('AI accuracy below 75%');
    }

    if (metrics.falsePositiveRate <= 0.1) {
      score += 35;
      achievements.push('Very low false positive rate');
    } else if (metrics.falsePositiveRate <= 0.2) {
      score += 20;
    } else {
      concerns.push('High false positive rate affects reliability');
    }

    return {
      score: Math.min(100, score),
      metrics,
      achievements,
      concerns
    };
  }

  private calculateTrends(earliest: MetricSnapshot, latest: MetricSnapshot): {
    improvement: number;
    trendDirection: 'improving' | 'stable' | 'declining';
    keyFactors: string[];
  } {
    const improvementFactors = [];
    let totalImprovement = 0;

    // Test execution improvement
    const testSpeedImprovement = (earliest.testExecution.averageDuration - latest.testExecution.averageDuration) /
                                earliest.testExecution.averageDuration * 100;
    if (testSpeedImprovement > 5) {
      improvementFactors.push(`${testSpeedImprovement.toFixed(1)}% faster test execution`);
      totalImprovement += testSpeedImprovement;
    }

    // Coverage improvement
    const coverageImprovement = latest.testExecution.coveragePercentage - earliest.testExecution.coveragePercentage;
    if (coverageImprovement > 2) {
      improvementFactors.push(`${coverageImprovement.toFixed(1)}% coverage increase`);
      totalImprovement += coverageImprovement * 2; // Weight coverage improvements
    }

    // AI effectiveness improvement
    const confidenceImprovement = latest.aiAnalysis.averageConfidence - earliest.aiAnalysis.averageConfidence;
    if (confidenceImprovement > 5) {
      improvementFactors.push(`${confidenceImprovement.toFixed(1)}% higher AI confidence`);
      totalImprovement += confidenceImprovement;
    }

    let trendDirection: 'improving' | 'stable' | 'declining';
    if (totalImprovement > 10) trendDirection = 'improving';
    else if (totalImprovement < -10) trendDirection = 'declining';
    else trendDirection = 'stable';

    return {
      improvement: totalImprovement,
      trendDirection,
      keyFactors: improvementFactors.length > 0 ? improvementFactors : ['No significant changes detected']
    };
  }

  private generateRecommendations(
    categories: Record<string, EffectivenessCategory>,
    trends: any
  ): string[] {
    const recommendations: string[] = [];

    // Analyze each category for recommendations
    Object.entries(categories).forEach(([category, data]) => {
      if (data.score < 70) {
        recommendations.push(`Improve ${category}: Focus on ${data.concerns.join(', ')}`);
      }
    });

    if (trends.trendDirection === 'declining') {
      recommendations.push('Address declining trend: ' + trends.keyFactors.join(', '));
    }

    if (categories.testOptimization.score < 75) {
      recommendations.push('Optimize test selection algorithms for better performance');
    }

    if (categories.bugDetection.score < 75) {
      recommendations.push('Improve AI model training with more edge cases');
    }

    return recommendations;
  }

  private triggerValidationIfNeeded(snapshot: MetricSnapshot): void {
    // Run validation daily
    const lastValidation = this.validationHistory[this.validationHistory.length - 1];
    const oneDayAgo = Date.now() - (24 * 60 * 60 * 1000);

    if (!lastValidation || lastValidation.score < 0 || snapshot.timestamp > oneDayAgo) {
      try {
        this.validateAIEffectiveness();
      } catch (error) {
        // Validation failed, but don't break the metrics collection
      }
    }
  }

  private compareMetric(
    name: string,
    baseline: number,
    current: number,
    improvements: BenchmarkComparison['improvements'],
    regressions: BenchmarkComparison['regressions'],
    lowerIsBetter: boolean
  ): void {
    const difference = current - baseline;
    const percentage = (difference / baseline) * 100;

    const isImprovement = lowerIsBetter ? difference < 0 : difference > 0;

    if (isImprovement) {
      let significance: 'major' | 'moderate' | 'minor' | 'none';
      if (Math.abs(percentage) >= 20) significance = 'major';
      else if (Math.abs(percentage) >= 10) significance = 'moderate';
      else if (Math.abs(percentage) >= 5) significance = 'minor';
      else significance = 'none';

      improvements[name] = {
        value: Math.abs(difference),
        percentage: Math.abs(percentage),
        significance
      };
    } else {
      let severity: 'critical' | 'high' | 'medium' | 'low';
      if (Math.abs(percentage) >= 30) severity = 'critical';
      else if (Math.abs(percentage) >= 15) severity = 'high';
      else if (Math.abs(percentage) >= 5) severity = 'medium';
      else severity = 'low';

      regressions[name] = {
        value: Math.abs(difference),
        percentage: Math.abs(percentage),
        severity
      };
    }
  }

  private evaluateAccuracy(snapshot: MetricSnapshot, comparison: BenchmarkComparison): { score: number; details: string } {
    let score = 50; // Base score
    const details: string[] = [];

    if (snapshot.aiAnalysis.averageConfidence >= 85) {
      score += 30;
      details.push(`High AI confidence: ${snapshot.aiAnalysis.averageConfidence}%`);
    } else if (snapshot.aiAnalysis.averageConfidence >= 75) {
      score += 15;
      details.push(`Moderate AI confidence: ${snapshot.aiAnalysis.averageConfidence}%`);
    } else {
      details.push(`Low AI confidence: ${snapshot.aiAnalysis.averageConfidence}%`);
    }

    if (snapshot.aiAnalysis.falsePositiveRate <= 0.15) {
      score += 20;
      details.push('Acceptable false positive rate');
    } else {
      details.push('High false positive rate');
    }

    return { score: Math.min(100, score), details: details.join(', ') };
  }

  private evaluatePerformance(snapshot: MetricSnapshot, comparison: BenchmarkComparison): { score: number; details: string } {
    let score = 50; // Base score
    const details: string[] = [];

    if (snapshot.performance.analysisTime <= 30) {
      score += 25;
      details.push('Fast analysis time');
    } else if (snapshot.performance.analysisTime <= 60) {
      score += 15;
      details.push('Acceptable analysis time');
    } else {
      details.push('Slow analysis time');
    }

    if (snapshot.performance.systemResourceUsage <= 70) {
      score += 25;
      details.push('Efficient resource usage');
    }

    return { score: Math.min(100, score), details: details.join(', ') };
  }

  private evaluateReliability(snapshot: MetricSnapshot, comparison: BenchmarkComparison): { score: number; details: string } {
    let score = 50;
    const details: string[] = [];

    if (snapshot.testExecution.passRate >= 0.95) {
      score += 30;
      details.push('High test pass rate');
    } else if (snapshot.testExecution.passRate >= 0.90) {
      score += 15;
      details.push('Acceptable test pass rate');
    } else {
      details.push('Low test pass rate');
    }

    if (snapshot.testExecution.flakyTestCount <= 5) {
      score += 20;
      details.push('Low flaky test count');
    }

    return { score: Math.min(100, score), details: details.join(', ') };
  }

  private evaluateUsability(snapshot: MetricSnapshot, comparison: BenchmarkComparison): { score: number; details: string } {
    let score = 50;
    const details: string[] = [];

    if (snapshot.developerExperience.developerSatisfactionScore >= 80) {
      score += 30;
      details.push('High developer satisfaction');
    } else if (snapshot.developerExperience.developerSatisfactionScore >= 70) {
      score += 15;
      details.push('Moderate developer satisfaction');
    }

    if (snapshot.developerExperience.adoptionRate >= 80) {
      score += 20;
      details.push('High adoption rate');
    }

    return { score: Math.min(100, score), details: details.join(', ') };
  }

  private evaluateSafety(snapshot: MetricSnapshot, comparison: BenchmarkComparison): { score: number; details: string } {
    let score = 50;
    const details: string[] = [];

    if (snapshot.qualityImpact.preventedIssues >= 5) {
      score += 25;
      details.push('Good issue prevention');
    }

    if (snapshot.aiAnalysis.insightsApproved / snapshot.aiAnalysis.insightsGenerated >= 0.7) {
      score += 25;
      details.push('High insight approval rate');
    }

    return { score: Math.min(100, score), details: details.join(', ') };
  }

  private generateValidationRecommendations(criteria: any, overallScore: number): string[] {
    const recommendations: string[] = [];

    if (criteria.accuracy.score < 75) {
      recommendations.push('Improve AI model accuracy through better training data');
    }
    if (criteria.performance.score < 75) {
      recommendations.push('Optimize AI analysis performance and resource usage');
    }
    if (criteria.usability.score < 75) {
      recommendations.push('Enhance developer experience and adoption');
    }
    if (overallScore < 75) {
      recommendations.push('Consider adjusting AI parameters or reverting changes');
    }

    return recommendations;
  }

  private calculateOverallScore(snapshot: MetricSnapshot): number {
    // Weighted calculation of overall AI effectiveness score
    const weights = {
      accuracy: 0.3,
      performance: 0.2,
      usability: 0.2,
      reliability: 0.2,
      safety: 0.1
    };

    // Simplified scoring logic
    let score = 0;
    score += (snapshot.aiAnalysis.averageConfidence / 100) * 100 * weights.accuracy;
    score += (snapshot.performance.analysisTime <= 60 ? 80 : 40) * weights.performance;
    score += (snapshot.developerExperience.developerSatisfactionScore / 100) * 100 * weights.usability;
    score += (snapshot.testExecution.passRate * 100) * weights.reliability;
    score += (snapshot.qualityImpact.preventedIssues >= 5 ? 90 : 60) * weights.safety;

    return Math.round(score);
  }

  private calculateTrendMetric(previous: number, current: number, lowerIsBetter: boolean): {
    value: number;
    change: number;
    trend: 'up' | 'down' | 'stable';
  } {
    const change = ((current - previous) / previous) * 100;
    const trend = Math.abs(change) < 2 ? 'stable' :
                  (lowerIsBetter ? (change < 0 ? 'up' : 'down') : (change > 0 ? 'up' : 'down'));

    return {
      value: current,
      change,
      trend
    };
  }

  private generateAlerts(snapshot: MetricSnapshot): Array<{ level: 'info' | 'warning' | 'error'; message: string }> {
    const alerts: Array<{ level: 'info' | 'warning' | 'error'; message: string }> = [];

    if (snapshot.testExecution.passRate < 0.90) {
      alerts.push({ level: 'error', message: 'Test pass rate below 90%' });
    }

    if (snapshot.aiAnalysis.falsePositiveRate > 0.25) {
      alerts.push({ level: 'warning', message: 'High AI false positive rate detected' });
    }

    if (snapshot.performance.analysisTime > 120) {
      alerts.push({ level: 'warning', message: 'AI analysis taking longer than expected' });
    }

    if (snapshot.developerExperience.adoptionRate < 50) {
      alerts.push({ level: 'warning', message: 'Low AI feature adoption rate' });
    }

    return alerts;
  }

  private extractMetricValue(snapshot: MetricSnapshot, metric: string): number {
    const pathMap: Record<string, string> = {
      'passRate': 'testExecution.passRate',
      'averageDuration': 'testExecution.averageDuration',
      'coverage': 'testExecution.coveragePercentage',
      'aiConfidence': 'aiAnalysis.averageConfidence',
      'satisfaction': 'developerExperience.developerSatisfactionScore'
    };

    const path = pathMap[metric];
    if (!path) return 0;

    const keys = path.split('.');
    let value: any = snapshot;
    for (const key of keys) {
      value = value[key];
      if (value === undefined) return 0;
    }

    return typeof value === 'number' ? value : 0;
  }

  private calculateVariance(numbers: number[]): number {
    if (numbers.length === 0) return 0;

    const mean = numbers.reduce((sum, num) => sum + num, 0) / numbers.length;
    const squaredDiffs = numbers.map(num => Math.pow(num - mean, 2));
    return squaredDiffs.reduce((sum, diff) => sum + diff, 0) / numbers.length;
  }
}

/**
 * Singleton instance for global access
 */
export const aiTestMetrics = new AITestMetrics();
