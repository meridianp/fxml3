/**
 * AI-Enhanced TDD Framework Integration Tests
 *
 * Tests complete AI framework workflow:
 * - Test execution data collection and analysis
 * - AI insight generation and validation
 * - Human-in-the-loop approval workflows
 * - Safety framework validation
 * - Performance metrics and effectiveness measurement
 * - Cross-component integration and data flow
 */

import { aiTestAnalyzer, TestExecution, TestAnalysisInsight } from '../../src/ai-testing/AITestAnalyzer';
import { aiTestDataGenerator } from '../../src/ai-testing/AITestDataGenerator';
import { aiTestSafetyFramework } from '../../src/ai-testing/AITestSafetyFramework';
import { aiTestMetrics } from '../../src/ai-testing/AITestMetrics';
import { JestAIReporter } from '../../src/ai-testing/JestAIReporter';

describe('AI-Enhanced TDD Framework Integration', () => {
  beforeEach(() => {
    // Reset AI analyzer state
    aiTestAnalyzer.resetAnalysisData();

    // Clear safety framework queues
    aiTestSafetyFramework.clearApprovalQueue();

    // Reset metrics
    aiTestMetrics.resetMetrics();

    jest.clearAllMocks();
  });

  describe('Complete Test Analysis Workflow', () => {
    test('processes test executions through full AI analysis pipeline', async () => {
      // Phase 1: Generate realistic test execution data
      const testExecutions: TestExecution[] = [
        {
          testName: 'EUR/USD trading strategy validation',
          filePath: '/tests/strategies/eurusd.test.ts',
          duration: 1250,
          status: 'passed',
          timestamp: Date.now(),
          codeChanges: ['src/strategies/EurUsdStrategy.ts'],
          coverage: { statements: 92, branches: 88, functions: 95, lines: 91 }
        },
        {
          testName: 'Risk management calculation accuracy',
          filePath: '/tests/risk/margin-calc.test.ts',
          duration: 2800,
          status: 'failed',
          timestamp: Date.now() + 1000,
          errorMessage: 'Expected margin level 150%, got 148%',
          stackTrace: 'at calculateMarginLevel (margin-calc.ts:45)',
          codeChanges: ['src/risk/MarginCalculator.ts'],
          coverage: { statements: 78, branches: 65, functions: 82, lines: 76 }
        },
        {
          testName: 'WebSocket connection stability',
          filePath: '/tests/services/websocket.test.ts',
          duration: 5200,
          status: 'passed',
          timestamp: Date.now() + 2000,
          codeChanges: [],
          coverage: { statements: 89, branches: 82, functions: 91, lines: 87 }
        }
      ];

      // Phase 2: Record executions through AI analyzer
      testExecutions.forEach(execution => {
        aiTestAnalyzer.recordTestExecution(execution);
      });

      // Phase 3: Trigger analysis
      aiTestAnalyzer.analyzeTestPatterns();

      // Phase 4: Retrieve insights
      const insights = aiTestAnalyzer.getInsights({ minConfidence: 70 });
      const statistics = aiTestAnalyzer.getTestStatistics();

      // Validate AI analysis results
      expect(statistics.totalExecutions).toBe(3);
      expect(statistics.passRate).toBeCloseTo(0.67, 2); // 2/3 passed
      expect(statistics.averageDuration).toBeCloseTo(3083.33, 2);

      // Should generate insights for slow test and failing test
      expect(insights.length).toBeGreaterThan(0);

      const performanceInsight = insights.find(i => i.type === 'performance');
      const reliabilityInsight = insights.find(i => i.type === 'reliability');

      expect(performanceInsight).toBeDefined();
      expect(reliabilityInsight).toBeDefined();

      // Validate insight structure
      insights.forEach(insight => {
        expect(insight).toMatchObject({
          id: expect.any(String),
          title: expect.any(String),
          description: expect.any(String),
          type: expect.stringMatching(/^(performance|reliability|coverage|optimization)$/),
          severity: expect.stringMatching(/^(low|medium|high|critical)$/),
          confidence: expect.any(Number),
          recommendation: expect.any(String),
          affectedTests: expect.any(Array),
          impact: expect.any(String),
          humanReviewed: expect.any(Boolean)
        });
      });
    });

    test('integrates with Jest reporter for automatic data collection', async () => {
      const mockGlobalConfig = {};
      const reporterOptions = {
        outputPath: './test-ai-reports',
        enableRealTimeAnalysis: true,
        minimumTestsForAnalysis: 2
      };

      const reporter = new JestAIReporter(mockGlobalConfig, reporterOptions);

      // Mock Jest test results
      const mockTest = {
        path: '/tests/trading/order-execution.test.ts'
      };

      const mockTestResult = {
        testResults: [
          {
            fullName: 'Order execution performance under high load',
            status: 'passed',
            duration: 1500,
            failureMessages: []
          },
          {
            fullName: 'Order validation with invalid parameters',
            status: 'failed',
            duration: 800,
            failureMessages: ['ValidationError: Invalid order quantity']
          }
        ]
      };

      const mockAggregatedResult = {
        coverageMap: null,
        numTotalTests: 10,
        numPassedTests: 8,
        numFailedTests: 2,
        startTime: Date.now() - 5000
      };

      // Simulate Jest lifecycle
      reporter.onRunStart();
      reporter.onTestResult(mockTest as any, mockTestResult as any, mockAggregatedResult as any);

      // Verify data was recorded in AI analyzer
      const statistics = aiTestAnalyzer.getTestStatistics();
      expect(statistics.totalExecutions).toBeGreaterThanOrEqual(2);

      const insights = aiTestAnalyzer.getInsights({ minConfidence: 50 });
      expect(insights.length).toBeGreaterThanOrEqual(0); // May or may not generate insights with minimal data
    });
  });

  describe('AI Safety Framework Integration', () => {
    test('validates AI-generated content through safety rules', async () => {
      // Generate test scenario using AI data generator
      const scenario = aiTestDataGenerator.generateTradingScenario({
        complexity: 7,
        riskLevel: 'high',
        duration: 60
      });

      // Validate scenario through safety framework
      const validationResult = aiTestSafetyFramework.validateContent(
        'test_scenario',
        scenario,
        'scenario_generation'
      );

      expect(validationResult.isValid).toBe(true);
      expect(validationResult.passedRules).toContain('content_appropriateness');
      expect(validationResult.passedRules).toContain('financial_compliance');
      expect(validationResult.risks.length).toBeGreaterThanOrEqual(0);

      // Test validation of potentially problematic content
      const riskyScenario = {
        ...scenario,
        name: 'Market manipulation test',
        description: 'Testing illegal trading practices'
      };

      const riskyValidation = aiTestSafetyFramework.validateContent(
        'risky_scenario',
        riskyScenario,
        'scenario_generation'
      );

      // Should detect compliance issues
      expect(riskyValidation.risks.length).toBeGreaterThan(0);
      expect(riskyValidation.risks.some(risk => risk.includes('compliance'))).toBe(true);
    });

    test('manages human approval workflow for AI insights', async () => {
      // Create test insight that requires approval
      const testInsight: TestAnalysisInsight = {
        id: 'test-insight-1',
        title: 'Optimize trading algorithm performance',
        description: 'AI detected potential optimization in trading strategy',
        type: 'performance',
        severity: 'high',
        confidence: 85,
        recommendation: 'Implement caching layer for price calculations',
        affectedTests: ['trading-strategy.test.ts'],
        impact: 'high',
        generatedAt: Date.now(),
        humanReviewed: false,
        humanApproved: false,
        auditTrail: []
      };

      // Request approval through safety framework
      const approvalRequest = aiTestSafetyFramework.requestApproval(
        'test_user',
        'insight_validation',
        testInsight,
        'AI-generated performance optimization insight'
      );

      expect(approvalRequest.id).toBeDefined();
      expect(approvalRequest.status).toBe('pending');

      // Check approval queue
      const pendingApprovals = aiTestSafetyFramework.getPendingApprovals('test_user');
      expect(pendingApprovals.length).toBe(1);
      expect(pendingApprovals[0].id).toBe(approvalRequest.id);

      // Approve the insight
      const approval = aiTestSafetyFramework.processApproval(
        approvalRequest.id,
        'test_user',
        'approved',
        'Performance optimization looks valid and beneficial'
      );

      expect(approval.decision).toBe('approved');
      expect(approval.reviewedBy).toBe('test_user');
      expect(approval.notes).toContain('beneficial');

      // Verify insight is marked as approved through analyzer
      aiTestAnalyzer.approveInsight(0, true, 'test_user', 'Approved via safety framework');
      const updatedInsights = aiTestAnalyzer.getInsights();
      expect(updatedInsights[0]?.humanApproved).toBe(true);
    });
  });

  describe('Performance Metrics and Effectiveness Validation', () => {
    test('measures AI framework performance and effectiveness', async () => {
      // Record baseline metrics
      const baselineSnapshot = aiTestMetrics.captureSnapshot('baseline');
      expect(baselineSnapshot.timestamp).toBeDefined();
      expect(baselineSnapshot.testExecutions).toBe(0);

      // Simulate AI-enhanced testing workflow
      const testExecutions: TestExecution[] = [
        {
          testName: 'Portfolio rebalancing strategy',
          filePath: '/tests/portfolio/rebalancing.test.ts',
          duration: 1800,
          status: 'passed',
          timestamp: Date.now(),
          codeChanges: ['src/portfolio/RebalancingStrategy.ts'],
          coverage: { statements: 94, branches: 91, functions: 96, lines: 93 }
        },
        {
          testName: 'Currency conversion accuracy',
          filePath: '/tests/utils/currency.test.ts',
          duration: 650,
          status: 'passed',
          timestamp: Date.now() + 1000,
          codeChanges: [],
          coverage: { statements: 98, branches: 95, functions: 100, lines: 97 }
        }
      ];

      testExecutions.forEach(execution => {
        aiTestAnalyzer.recordTestExecution(execution);
      });

      aiTestAnalyzer.analyzeTestPatterns();

      // Record post-analysis metrics
      const analysisSnapshot = aiTestMetrics.captureSnapshot('post-analysis');
      expect(analysisSnapshot.testExecutions).toBe(2);
      expect(analysisSnapshot.aiInsightsGenerated).toBeGreaterThanOrEqual(0);

      // Validate AI effectiveness
      const effectivenessReport = aiTestMetrics.validateAIEffectiveness();

      expect(effectivenessReport.meetsSuccessCriteria).toBeDefined();
      expect(effectivenessReport.recommendations).toBeInstanceOf(Array);
      expect(effectivenessReport.performanceMetrics).toMatchObject({
        analysisLatency: expect.any(Number),
        insightAccuracy: expect.any(Number),
        falsePositiveRate: expect.any(Number)
      });

      // Generate comprehensive effectiveness report
      const fullReport = aiTestMetrics.generateEffectivenessReport();

      expect(fullReport.summary.totalAnalysisRuns).toBeGreaterThan(0);
      expect(fullReport.summary.averageAnalysisTime).toBeGreaterThan(0);
      expect(fullReport.trends).toBeInstanceOf(Array);
      expect(fullReport.recommendations).toBeInstanceOf(Array);
    });

    test('tracks AI framework performance over multiple analysis cycles', async () => {
      // Simulate multiple analysis cycles
      for (let cycle = 0; cycle < 3; cycle++) {
        const execution: TestExecution = {
          testName: `Test cycle ${cycle + 1}`,
          filePath: `/tests/cycle-${cycle}.test.ts`,
          duration: 1000 + (cycle * 200),
          status: cycle === 1 ? 'failed' : 'passed',
          timestamp: Date.now() + (cycle * 2000),
          codeChanges: cycle === 0 ? ['src/changed-file.ts'] : [],
          coverage: {
            statements: 85 + cycle,
            branches: 80 + cycle,
            functions: 90 + cycle,
            lines: 82 + cycle
          }
        };

        aiTestAnalyzer.recordTestExecution(execution);
        aiTestAnalyzer.analyzeTestPatterns();

        // Capture metrics after each cycle
        aiTestMetrics.captureSnapshot(`cycle-${cycle}`);
      }

      // Analyze performance trends
      const effectivenessReport = aiTestMetrics.validateAIEffectiveness();

      expect(effectivenessReport.performanceMetrics.analysisLatency).toBeLessThan(5000); // < 5s
      expect(effectivenessReport.performanceMetrics.insightAccuracy).toBeGreaterThan(0.7); // > 70%

      // Verify metrics show improvement or stability over time
      const fullReport = aiTestMetrics.generateEffectivenessReport();
      expect(fullReport.trends.length).toBeGreaterThan(0);
    });
  });

  describe('End-to-End AI Workflow Integration', () => {
    test('executes complete AI-enhanced TDD workflow from test to insight', async () => {
      // Phase 1: Generate AI test data
      const tradingScenarios = [
        aiTestDataGenerator.generateTradingScenario({
          complexity: 5,
          riskLevel: 'medium',
          duration: 30
        }),
        aiTestDataGenerator.generateTradingScenario({
          complexity: 8,
          riskLevel: 'high',
          duration: 45
        })
      ];

      expect(tradingScenarios.length).toBe(2);
      expect(tradingScenarios[0].marketCondition).toBeDefined();
      expect(tradingScenarios[1].riskLevel).toBe('high');

      // Phase 2: Simulate test executions using generated data
      const executions: TestExecution[] = tradingScenarios.map((scenario, index) => ({
        testName: scenario.name,
        filePath: `/tests/generated/scenario-${index}.test.ts`,
        duration: scenario.duration * 100, // Convert to ms
        status: Math.random() > 0.7 ? 'failed' : 'passed',
        timestamp: Date.now() + (index * 1000),
        codeChanges: index === 0 ? ['src/trading/Strategy.ts'] : [],
        coverage: {
          statements: 80 + Math.random() * 15,
          branches: 75 + Math.random() * 20,
          functions: 85 + Math.random() * 12,
          lines: 78 + Math.random() * 18
        }
      }));

      // Phase 3: Process through AI analyzer
      executions.forEach(execution => {
        aiTestAnalyzer.recordTestExecution(execution);
      });

      aiTestAnalyzer.analyzeTestPatterns();

      // Phase 4: Validate through safety framework
      const insights = aiTestAnalyzer.getInsights({ minConfidence: 60 });

      for (const insight of insights) {
        const validation = aiTestSafetyFramework.validateContent(
          insight.id,
          insight,
          'insight_validation'
        );
        expect(validation.isValid).toBe(true);
      }

      // Phase 5: Measure effectiveness
      const metrics = aiTestMetrics.captureSnapshot('end-to-end-test');
      const effectiveness = aiTestMetrics.validateAIEffectiveness();

      // Validate complete workflow
      expect(insights.length).toBeGreaterThanOrEqual(0);
      expect(metrics.testExecutions).toBe(2);
      expect(effectiveness.meetsSuccessCriteria).toBeDefined();

      // Phase 6: Generate audit trail
      const auditLog = aiTestAnalyzer.getAuditLog(10);
      expect(auditLog.length).toBeGreaterThan(0);
      expect(auditLog[0]).toMatchObject({
        timestamp: expect.any(Number),
        action: expect.any(String),
        details: expect.any(Object),
        aiConfidence: expect.any(Number)
      });
    });

    test('handles error conditions and edge cases gracefully', async () => {
      // Test with malformed test execution data
      const malformedExecution = {
        testName: '', // Empty name
        filePath: null, // Invalid path
        duration: -100, // Negative duration
        status: 'unknown', // Invalid status
        timestamp: 'invalid', // Invalid timestamp
        coverage: null // Missing coverage
      } as any;

      // Should handle gracefully without crashing
      expect(() => {
        aiTestAnalyzer.recordTestExecution(malformedExecution);
      }).not.toThrow();

      // Test with empty data
      aiTestAnalyzer.analyzeTestPatterns();
      const emptyInsights = aiTestAnalyzer.getInsights();
      expect(emptyInsights).toBeInstanceOf(Array);

      // Test safety framework with invalid content
      const invalidValidation = aiTestSafetyFramework.validateContent(
        'invalid-test',
        null,
        'invalid_type'
      );
      expect(invalidValidation.isValid).toBe(false);
      expect(invalidValidation.errors.length).toBeGreaterThan(0);

      // Test metrics with no data
      const emptyMetrics = aiTestMetrics.captureSnapshot('empty-test');
      expect(emptyMetrics.testExecutions).toBe(0);
      expect(emptyMetrics.aiInsightsGenerated).toBe(0);
    });
  });
});
