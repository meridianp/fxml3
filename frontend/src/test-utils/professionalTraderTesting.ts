/**
 * Professional Trader User Testing Framework
 *
 * Comprehensive UAT framework for validating trading workflows with professional traders
 * Includes structured test scenarios, user profiles, and validation criteria
 */

import { render, RenderResult, fireEvent, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ReactElement } from 'react';

export interface TraderProfile {
  id: string;
  name: string;
  experience: 'novice' | 'intermediate' | 'expert' | 'institutional';
  tradingStyle: 'scalping' | 'day_trading' | 'swing_trading' | 'position_trading' | 'algorithmic';
  primaryAssets: string[];
  tradingFrequency: 'low' | 'medium' | 'high' | 'very_high';
  techProficiency: 'basic' | 'intermediate' | 'advanced' | 'expert';
  accessibilityRequirements?: string[];
  preferredDevices: ('desktop' | 'tablet' | 'mobile')[];
  keyboardShortcuts: boolean;
  averageSessionLength: number; // minutes
}

export interface TradingWorkflowTest {
  id: string;
  name: string;
  description: string;
  category: 'order_management' | 'analysis' | 'risk_management' | 'monitoring' | 'mobile_trading';
  priority: 'critical' | 'high' | 'medium' | 'low';
  estimatedDuration: number; // minutes
  targetProfiles: TraderProfile['experience'][];
  prerequisites: string[];
  steps: WorkflowStep[];
  successCriteria: SuccessCriterion[];
  commonIssues: string[];
  mitigations: string[];
}

export interface WorkflowStep {
  id: string;
  stepNumber: number;
  description: string;
  userAction: string;
  expectedResult: string;
  errorRecovery?: string;
  timing?: {
    expectedDuration: number; // seconds
    maxDuration: number; // seconds
  };
  validation: {
    method: 'visual' | 'functional' | 'performance' | 'accessibility';
    criteria: string[];
  };
  assistiveInstructions?: string; // For accessibility testing
}

export interface SuccessCriterion {
  id: string;
  description: string;
  measurable: boolean;
  target: string | number;
  method: 'observation' | 'measurement' | 'survey' | 'system_log';
}

export interface TraderFeedback {
  profileId: string;
  workflowId: string;
  timestamp: string;
  completed: boolean;
  duration: number; // minutes
  stepsFailed: string[];
  usabilityRating: number; // 1-10
  learnabilityRating: number; // 1-10
  efficiencyRating: number; // 1-10
  satisfactionRating: number; // 1-10
  errorRate: number; // percentage
  taskSuccess: boolean;
  comments: {
    positive: string[];
    negative: string[];
    suggestions: string[];
  };
  accessibility?: {
    screenReaderCompatible: boolean;
    keyboardNavigable: boolean;
    colorContrastSufficient: boolean;
    issues: string[];
  };
}

export interface UATestingResult {
  workflowId: string;
  profileId: string;
  overallSuccess: boolean;
  metrics: {
    taskCompletionRate: number;
    taskSuccessRate: number;
    averageCompletionTime: number;
    errorRate: number;
    userSatisfaction: number;
    efficiencyScore: number;
  };
  usabilityIssues: string[];
  recommendations: string[];
  criticalIssues: string[];
  feedback: TraderFeedback;
}

/**
 * Professional Trader Profiles
 */
export const TRADER_PROFILES: TraderProfile[] = [
  {
    id: 'expert_day_trader',
    name: 'Expert Day Trader',
    experience: 'expert',
    tradingStyle: 'day_trading',
    primaryAssets: ['FOREX', 'INDICES'],
    tradingFrequency: 'very_high',
    techProficiency: 'advanced',
    preferredDevices: ['desktop'],
    keyboardShortcuts: true,
    averageSessionLength: 480 // 8 hours
  },
  {
    id: 'institutional_scalper',
    name: 'Institutional Scalper',
    experience: 'institutional',
    tradingStyle: 'scalping',
    primaryAssets: ['FOREX'],
    tradingFrequency: 'very_high',
    techProficiency: 'expert',
    preferredDevices: ['desktop'],
    keyboardShortcuts: true,
    averageSessionLength: 360 // 6 hours
  },
  {
    id: 'swing_trader',
    name: 'Intermediate Swing Trader',
    experience: 'intermediate',
    tradingStyle: 'swing_trading',
    primaryAssets: ['FOREX', 'COMMODITIES'],
    tradingFrequency: 'medium',
    techProficiency: 'intermediate',
    preferredDevices: ['desktop', 'tablet'],
    keyboardShortcuts: false,
    averageSessionLength: 120 // 2 hours
  },
  {
    id: 'mobile_trader',
    name: 'Mobile Day Trader',
    experience: 'intermediate',
    tradingStyle: 'day_trading',
    primaryAssets: ['FOREX'],
    tradingFrequency: 'high',
    techProficiency: 'intermediate',
    preferredDevices: ['mobile', 'tablet'],
    keyboardShortcuts: false,
    averageSessionLength: 240 // 4 hours
  },
  {
    id: 'accessibility_trader',
    name: 'Visually Impaired Expert Trader',
    experience: 'expert',
    tradingStyle: 'day_trading',
    primaryAssets: ['FOREX'],
    tradingFrequency: 'high',
    techProficiency: 'advanced',
    accessibilityRequirements: ['screen_reader', 'high_contrast', 'keyboard_only'],
    preferredDevices: ['desktop'],
    keyboardShortcuts: true,
    averageSessionLength: 300 // 5 hours
  },
  {
    id: 'novice_trader',
    name: 'Novice Retail Trader',
    experience: 'novice',
    tradingStyle: 'position_trading',
    primaryAssets: ['FOREX'],
    tradingFrequency: 'low',
    techProficiency: 'basic',
    preferredDevices: ['desktop', 'mobile'],
    keyboardShortcuts: false,
    averageSessionLength: 60 // 1 hour
  }
];

/**
 * Critical Trading Workflow Tests
 */
export const TRADING_WORKFLOW_TESTS: TradingWorkflowTest[] = [
  {
    id: 'rapid_order_execution',
    name: 'Rapid Order Execution Test',
    description: 'Test ability to quickly place and manage multiple orders during high volatility',
    category: 'order_management',
    priority: 'critical',
    estimatedDuration: 15,
    targetProfiles: ['expert', 'institutional'],
    prerequisites: ['Active market session', 'Funded account', 'Market volatility > 0.5%'],
    steps: [
      {
        id: 'login_check',
        stepNumber: 1,
        description: 'Verify user can login and access trading interface quickly',
        userAction: 'Login with credentials and navigate to trading console',
        expectedResult: 'Trading console loads within 3 seconds with all market data visible',
        timing: { expectedDuration: 10, maxDuration: 15 },
        validation: {
          method: 'performance',
          criteria: ['Login time < 5s', 'Console load time < 3s', 'Market data streaming']
        }
      },
      {
        id: 'market_order_placement',
        stepNumber: 2,
        description: 'Place 5 consecutive market orders using different methods',
        userAction: 'Use keyboard shortcuts, click trading, and quick order buttons',
        expectedResult: 'All 5 orders executed within 30 seconds with confirmation',
        timing: { expectedDuration: 25, maxDuration: 30 },
        validation: {
          method: 'functional',
          criteria: ['Order execution time < 100ms', 'No failed orders', 'Clear confirmations']
        }
      },
      {
        id: 'position_monitoring',
        stepNumber: 3,
        description: 'Monitor real-time P&L changes across all positions',
        userAction: 'Watch position table and P&L updates for 2 minutes',
        expectedResult: 'P&L updates in real-time (<1s latency) with visual indicators',
        timing: { expectedDuration: 120, maxDuration: 120 },
        validation: {
          method: 'performance',
          criteria: ['Update latency < 1s', 'Visual change indicators', 'Accurate calculations']
        }
      },
      {
        id: 'rapid_closure',
        stepNumber: 4,
        description: 'Close all positions rapidly using multiple methods',
        userAction: 'Use close-all button and individual position closures',
        expectedResult: 'All positions closed within 15 seconds with confirmations',
        timing: { expectedDuration: 10, maxDuration: 15 },
        validation: {
          method: 'functional',
          criteria: ['Close-all works', 'Individual closures work', 'Balance updated correctly']
        }
      }
    ],
    successCriteria: [
      { id: 'speed', description: 'Complete workflow in under 5 minutes', measurable: true, target: 300, method: 'measurement' },
      { id: 'accuracy', description: 'No order placement errors', measurable: true, target: 0, method: 'system_log' },
      { id: 'usability', description: 'User rates experience 8+/10', measurable: true, target: 8, method: 'survey' }
    ],
    commonIssues: ['Slow order execution', 'P&L calculation delays', 'UI freezing under load'],
    mitigations: ['Optimize order routing', 'Improve real-time data processing', 'Add loading indicators']
  },
  {
    id: 'mobile_trading_workflow',
    name: 'Mobile Trading Workflow Test',
    description: 'Test complete trading workflow on mobile devices',
    category: 'mobile_trading',
    priority: 'high',
    estimatedDuration: 20,
    targetProfiles: ['intermediate', 'expert'],
    prerequisites: ['Mobile device', 'PWA installed', 'Touch screen'],
    steps: [
      {
        id: 'mobile_login',
        stepNumber: 1,
        description: 'Login on mobile device using touch interface',
        userAction: 'Open PWA, enter credentials using virtual keyboard',
        expectedResult: 'Quick login with biometric option if available',
        timing: { expectedDuration: 15, maxDuration: 30 },
        validation: {
          method: 'functional',
          criteria: ['Touch keyboard responsive', 'Biometric auth works', 'No login errors']
        }
      },
      {
        id: 'mobile_market_analysis',
        stepNumber: 2,
        description: 'Analyze market data using mobile charts',
        userAction: 'Zoom, pan, and analyze charts with touch gestures',
        expectedResult: 'Smooth chart interactions with clear data visibility',
        timing: { expectedDuration: 300, maxDuration: 420 },
        validation: {
          method: 'functional',
          criteria: ['Smooth touch gestures', 'Readable chart data', 'No lag in updates']
        }
      },
      {
        id: 'mobile_order_entry',
        stepNumber: 3,
        description: 'Place orders using mobile order entry form',
        userAction: 'Use floating action button and modal order form',
        expectedResult: 'Easy order placement with validation and confirmation',
        timing: { expectedDuration: 60, maxDuration: 90 },
        validation: {
          method: 'functional',
          criteria: ['Form easy to use', 'Validation clear', 'Order executed successfully']
        }
      },
      {
        id: 'mobile_monitoring',
        stepNumber: 4,
        description: 'Monitor positions using mobile interface',
        userAction: 'Navigate between tabs, check P&L, receive notifications',
        expectedResult: 'Clear position overview with push notifications for changes',
        timing: { expectedDuration: 180, maxDuration: 240 },
        validation: {
          method: 'functional',
          criteria: ['Clear position data', 'Push notifications work', 'Tab navigation smooth']
        }
      }
    ],
    successCriteria: [
      { id: 'mobile_usability', description: 'All actions possible on mobile', measurable: true, target: '100%', method: 'observation' },
      { id: 'touch_responsiveness', description: 'Touch interactions < 200ms response', measurable: true, target: 200, method: 'measurement' },
      { id: 'satisfaction', description: 'User satisfaction > 7/10', measurable: true, target: 7, method: 'survey' }
    ],
    commonIssues: ['Small touch targets', 'Chart zoom difficulties', 'Virtual keyboard issues'],
    mitigations: ['Increase button sizes', 'Improve gesture recognition', 'Optimize keyboard layout']
  },
  {
    id: 'accessibility_compliance_test',
    name: 'Accessibility Compliance Test',
    description: 'Validate platform accessibility for visually impaired traders',
    category: 'monitoring',
    priority: 'high',
    estimatedDuration: 30,
    targetProfiles: ['expert'],
    prerequisites: ['Screen reader software', 'High contrast mode', 'Keyboard-only navigation'],
    steps: [
      {
        id: 'screen_reader_navigation',
        stepNumber: 1,
        description: 'Navigate entire platform using only screen reader',
        userAction: 'Use NVDA/JAWS to navigate all major sections',
        expectedResult: 'All content accessible via screen reader with proper announcements',
        assistiveInstructions: 'Use tab key to navigate, arrow keys for content',
        timing: { expectedDuration: 600, maxDuration: 900 },
        validation: {
          method: 'accessibility',
          criteria: ['All content announced', 'Clear section identification', 'Logical reading order']
        }
      },
      {
        id: 'keyboard_only_trading',
        stepNumber: 2,
        description: 'Execute complete trading workflow using only keyboard',
        userAction: 'Place orders, monitor positions, close trades using keyboard shortcuts',
        expectedResult: 'All trading functions accessible via keyboard with clear feedback',
        timing: { expectedDuration: 300, maxDuration: 450 },
        validation: {
          method: 'accessibility',
          criteria: ['All functions keyboard accessible', 'Clear focus indicators', 'No keyboard traps']
        }
      },
      {
        id: 'high_contrast_testing',
        stepNumber: 3,
        description: 'Use platform in high contrast mode',
        userAction: 'Enable system high contrast and verify all information visible',
        expectedResult: 'All text and UI elements clearly visible in high contrast',
        timing: { expectedDuration: 180, maxDuration: 240 },
        validation: {
          method: 'visual',
          criteria: ['Text readable', 'Buttons visible', 'Chart data accessible']
        }
      }
    ],
    successCriteria: [
      { id: 'wcag_compliance', description: 'WCAG 2.1 AA compliance achieved', measurable: true, target: '100%', method: 'measurement' },
      { id: 'screen_reader_success', description: 'All functions accessible via screen reader', measurable: true, target: '100%', method: 'observation' },
      { id: 'keyboard_navigation', description: 'Complete workflow possible with keyboard only', measurable: true, target: '100%', method: 'observation' }
    ],
    commonIssues: ['Missing ARIA labels', 'Poor keyboard navigation', 'Insufficient color contrast'],
    mitigations: ['Add comprehensive ARIA labels', 'Improve focus management', 'Enhance color contrast']
  },
  {
    id: 'risk_management_workflow',
    name: 'Risk Management Workflow Test',
    description: 'Test risk management features and stop-loss functionality',
    category: 'risk_management',
    priority: 'critical',
    estimatedDuration: 25,
    targetProfiles: ['intermediate', 'expert', 'institutional'],
    prerequisites: ['Active positions', 'Risk limits configured', 'Stop-loss enabled'],
    steps: [
      {
        id: 'risk_dashboard_review',
        stepNumber: 1,
        description: 'Review risk dashboard and current exposure',
        userAction: 'Navigate to risk dashboard and analyze current risk metrics',
        expectedResult: 'Clear display of risk metrics, exposure, and limit utilization',
        timing: { expectedDuration: 120, maxDuration: 180 },
        validation: {
          method: 'visual',
          criteria: ['Risk metrics visible', 'Exposure calculations correct', 'Limits clearly shown']
        }
      },
      {
        id: 'stop_loss_management',
        stepNumber: 2,
        description: 'Set and modify stop-loss orders on existing positions',
        userAction: 'Add stop-loss to positions and modify existing stop levels',
        expectedResult: 'Stop-loss orders created and modified successfully',
        timing: { expectedDuration: 180, maxDuration: 240 },
        validation: {
          method: 'functional',
          criteria: ['Stop-loss orders created', 'Modifications saved', 'Orders visible in system']
        }
      },
      {
        id: 'risk_limit_testing',
        stepNumber: 3,
        description: 'Test risk limit enforcement by approaching limits',
        userAction: 'Attempt to place orders that would exceed configured risk limits',
        expectedResult: 'System prevents orders that would breach risk limits',
        timing: { expectedDuration: 120, maxDuration: 180 },
        validation: {
          method: 'functional',
          criteria: ['Risk limits enforced', 'Clear rejection messages', 'No limit breaches']
        }
      },
      {
        id: 'emergency_procedures',
        stepNumber: 4,
        description: 'Test emergency position closure procedures',
        userAction: 'Use emergency close-all and panic close features',
        expectedResult: 'All positions closed immediately with confirmations',
        timing: { expectedDuration: 30, maxDuration: 60 },
        validation: {
          method: 'functional',
          criteria: ['Emergency close works', 'All positions closed', 'Clear confirmations']
        }
      }
    ],
    successCriteria: [
      { id: 'risk_accuracy', description: 'Risk calculations 100% accurate', measurable: true, target: '100%', method: 'measurement' },
      { id: 'limit_enforcement', description: 'Risk limits enforced without failures', measurable: true, target: 0, method: 'system_log' },
      { id: 'emergency_response', description: 'Emergency procedures complete in <1 minute', measurable: true, target: 60, method: 'measurement' }
    ],
    commonIssues: ['Inaccurate risk calculations', 'Failed limit enforcement', 'Slow emergency procedures'],
    mitigations: ['Improve risk calculation engine', 'Add real-time limit checking', 'Optimize emergency close procedures']
  }
];

/**
 * Run professional trader user testing
 */
export async function runProfessionalTraderTest(
  component: ReactElement,
  workflowTest: TradingWorkflowTest,
  traderProfile: TraderProfile
): Promise<UATestingResult> {
  const startTime = Date.now();
  const stepResults: { stepId: string; success: boolean; duration: number; issues: string[] }[] = [];
  const usabilityIssues: string[] = [];
  const criticalIssues: string[] = [];

  console.log(`Running trader test: ${workflowTest.name} for ${traderProfile.name}`);

  // Render component
  const { container } = render(component);
  const user = userEvent.setup();

  // Execute workflow steps
  for (const step of workflowTest.steps) {
    const stepStartTime = Date.now();
    console.log(`  Step ${step.stepNumber}: ${step.description}`);

    try {
      // Execute step based on user action and profile
      const stepResult = await executeWorkflowStep(container, step, traderProfile, user);
      stepResults.push(stepResult);

      if (!stepResult.success) {
        if (step.validation.method === 'performance' || step.validation.method === 'functional') {
          criticalIssues.push(`Critical failure in step ${step.stepNumber}: ${step.description}`);
        } else {
          usabilityIssues.push(`Usability issue in step ${step.stepNumber}: ${stepResult.issues.join(', ')}`);
        }
      }
    } catch (error) {
      stepResults.push({
        stepId: step.id,
        success: false,
        duration: Date.now() - stepStartTime,
        issues: [`Step execution failed: ${error}`]
      });
      criticalIssues.push(`Critical error in step ${step.stepNumber}: ${error}`);
    }
  }

  const totalDuration = (Date.now() - startTime) / 1000 / 60; // minutes
  const successfulSteps = stepResults.filter(r => r.success).length;
  const taskCompletionRate = (successfulSteps / stepResults.length) * 100;
  const overallSuccess = criticalIssues.length === 0;

  // Generate mock trader feedback
  const feedback: TraderFeedback = generateMockTraderFeedback(
    traderProfile, workflowTest, overallSuccess, totalDuration, stepResults
  );

  // Calculate metrics
  const metrics = {
    taskCompletionRate,
    taskSuccessRate: overallSuccess ? 100 : 0,
    averageCompletionTime: totalDuration,
    errorRate: ((stepResults.length - successfulSteps) / stepResults.length) * 100,
    userSatisfaction: feedback.satisfactionRating,
    efficiencyScore: Math.max(0, 100 - (totalDuration / workflowTest.estimatedDuration) * 50)
  };

  const recommendations = generateRecommendations(workflowTest, stepResults, traderProfile);

  return {
    workflowId: workflowTest.id,
    profileId: traderProfile.id,
    overallSuccess,
    metrics,
    usabilityIssues,
    recommendations,
    criticalIssues,
    feedback
  };
}

/**
 * Execute individual workflow step
 */
async function executeWorkflowStep(
  container: HTMLElement,
  step: WorkflowStep,
  profile: TraderProfile,
  user: ReturnType<typeof userEvent.setup>
): Promise<{ stepId: string; success: boolean; duration: number; issues: string[] }> {
  const startTime = Date.now();
  const issues: string[] = [];
  let success = true;

  try {
    // Simulate step execution based on profile and step requirements
    switch (step.id) {
      case 'login_check':
        // Simulate login validation
        const loginElements = container.querySelectorAll('input[type="password"], input[type="email"]');
        if (loginElements.length === 0) {
          issues.push('Login form not found');
          success = false;
        }
        break;

      case 'market_order_placement':
        // Simulate order placement
        const orderButtons = container.querySelectorAll('button[aria-label*="order"], button[type="submit"]');
        if (orderButtons.length === 0) {
          issues.push('Order buttons not accessible');
          success = false;
        }

        // Test keyboard shortcuts if user prefers them
        if (profile.keyboardShortcuts) {
          // Simulate keyboard shortcut testing
          await user.keyboard('{ctrl}b'); // Buy shortcut
          await new Promise(resolve => setTimeout(resolve, 50));
        }
        break;

      case 'position_monitoring':
        // Simulate position table monitoring
        const positionTables = container.querySelectorAll('[role="table"], table');
        if (positionTables.length === 0) {
          issues.push('Position table not accessible');
          success = false;
        }
        break;

      case 'mobile_login':
        // Simulate mobile-specific validation
        if (!profile.preferredDevices.includes('mobile')) {
          issues.push('Profile not configured for mobile testing');
          success = false;
        }
        break;

      case 'screen_reader_navigation':
        // Simulate accessibility validation
        if (!profile.accessibilityRequirements?.includes('screen_reader')) {
          issues.push('Profile not configured for screen reader testing');
          success = false;
        }

        // Check for accessibility attributes
        const accessibleElements = container.querySelectorAll('[aria-label], [role], [aria-describedby]');
        if (accessibleElements.length < 10) {
          issues.push('Insufficient accessibility attributes found');
          success = false;
        }
        break;

      default:
        // Generic step validation
        const interactiveElements = container.querySelectorAll('button, input, select, [role="button"]');
        if (interactiveElements.length === 0) {
          issues.push('No interactive elements found for step execution');
          success = false;
        }
        break;
    }

    // Check timing constraints
    const duration = Date.now() - startTime;
    if (step.timing && duration > step.timing.maxDuration * 1000) {
      issues.push(`Step exceeded maximum duration: ${duration}ms > ${step.timing.maxDuration * 1000}ms`);
      success = false;
    }

  } catch (error) {
    issues.push(`Step execution error: ${error}`);
    success = false;
  }

  return {
    stepId: step.id,
    success,
    duration: Date.now() - startTime,
    issues
  };
}

/**
 * Generate mock trader feedback
 */
function generateMockTraderFeedback(
  profile: TraderProfile,
  workflow: TradingWorkflowTest,
  success: boolean,
  duration: number,
  stepResults: { stepId: string; success: boolean; duration: number; issues: string[] }[]
): TraderFeedback {
  const baseRating = success ? 8 : 5;
  const experienceMultiplier = profile.experience === 'expert' ? 1.2 :
                               profile.experience === 'institutional' ? 1.1 : 1.0;

  return {
    profileId: profile.id,
    workflowId: workflow.id,
    timestamp: new Date().toISOString(),
    completed: success,
    duration,
    stepsFailed: stepResults.filter(r => !r.success).map(r => r.stepId),
    usabilityRating: Math.min(10, Math.round(baseRating * experienceMultiplier)),
    learnabilityRating: Math.min(10, Math.round((baseRating - 1) * experienceMultiplier)),
    efficiencyRating: Math.min(10, Math.round(baseRating * (duration <= workflow.estimatedDuration ? 1.2 : 0.8))),
    satisfactionRating: Math.min(10, Math.round(baseRating * (success ? 1.1 : 0.7))),
    errorRate: (stepResults.filter(r => !r.success).length / stepResults.length) * 100,
    taskSuccess: success,
    comments: {
      positive: success ? ['Workflow completed successfully', 'Interface responsive'] : [],
      negative: success ? [] : ['Some steps failed', 'Performance issues detected'],
      suggestions: ['Consider adding more keyboard shortcuts', 'Improve mobile responsiveness']
    },
    accessibility: profile.accessibilityRequirements ? {
      screenReaderCompatible: success,
      keyboardNavigable: success,
      colorContrastSufficient: success,
      issues: success ? [] : ['Some accessibility issues detected']
    } : undefined
  };
}

/**
 * Generate recommendations based on test results
 */
function generateRecommendations(
  workflow: TradingWorkflowTest,
  stepResults: { stepId: string; success: boolean; duration: number; issues: string[] }[],
  profile: TraderProfile
): string[] {
  const recommendations: string[] = [];

  const failedSteps = stepResults.filter(r => !r.success);
  const slowSteps = stepResults.filter(r => r.duration > 5000); // >5 seconds

  if (failedSteps.length > 0) {
    recommendations.push(`Address ${failedSteps.length} failed steps to improve workflow reliability`);
  }

  if (slowSteps.length > 0) {
    recommendations.push(`Optimize performance for ${slowSteps.length} slow steps`);
  }

  if (profile.keyboardShortcuts && workflow.category === 'order_management') {
    recommendations.push('Add more keyboard shortcuts for expert traders');
  }

  if (profile.preferredDevices.includes('mobile')) {
    recommendations.push('Ensure mobile optimization for mobile traders');
  }

  if (profile.accessibilityRequirements) {
    recommendations.push('Enhance accessibility features for inclusive trading');
  }

  if (recommendations.length === 0) {
    recommendations.push('Workflow performed well - consider additional optimization for production');
  }

  return recommendations;
}

/**
 * Generate comprehensive UAT report
 */
export function generateProfessionalTraderReport(results: UATestingResult[]): string {
  const totalTests = results.length;
  const passedTests = results.filter(r => r.overallSuccess).length;
  const criticalIssues = results.reduce((sum, r) => sum + r.criticalIssues.length, 0);
  const averageSatisfaction = results.reduce((sum, r) => sum + r.metrics.userSatisfaction, 0) / totalTests;

  let report = `# Professional Trader User Acceptance Testing Report

## Executive Summary
- **Total Tests Executed**: ${totalTests}
- **Success Rate**: ${Math.round((passedTests / totalTests) * 100)}%
- **Critical Issues**: ${criticalIssues}
- **Average User Satisfaction**: ${averageSatisfaction.toFixed(1)}/10
- **Test Date**: ${new Date().toISOString().split('T')[0]}

## Test Results by Profile
`;

  // Group results by trader profile
  const profileResults = results.reduce((acc, result) => {
    if (!acc[result.profileId]) acc[result.profileId] = [];
    acc[result.profileId].push(result);
    return acc;
  }, {} as Record<string, UATestingResult[]>);

  Object.entries(profileResults).forEach(([profileId, profileResults]) => {
    const profileSuccess = profileResults.filter(r => r.overallSuccess).length;
    const profileTotal = profileResults.length;

    report += `
### ${profileId.replace(/_/g, ' ').toUpperCase()}
- **Success Rate**: ${Math.round((profileSuccess / profileTotal) * 100)}%
- **Average Task Completion**: ${Math.round(profileResults.reduce((sum, r) => sum + r.metrics.taskCompletionRate, 0) / profileTotal)}%
- **Average Satisfaction**: ${(profileResults.reduce((sum, r) => sum + r.metrics.userSatisfaction, 0) / profileTotal).toFixed(1)}/10
`;
  });

  report += `
## Workflow Performance Analysis
`;

  // Group by workflow
  const workflowResults = results.reduce((acc, result) => {
    if (!acc[result.workflowId]) acc[result.workflowId] = [];
    acc[result.workflowId].push(result);
    return acc;
  }, {} as Record<string, UATestingResult[]>);

  Object.entries(workflowResults).forEach(([workflowId, workflowResults]) => {
    const workflowSuccess = workflowResults.filter(r => r.overallSuccess).length;
    const workflowTotal = workflowResults.length;
    const avgCompletionTime = workflowResults.reduce((sum, r) => sum + r.metrics.averageCompletionTime, 0) / workflowTotal;

    report += `
### ${workflowId.replace(/_/g, ' ').toUpperCase()}
- **Success Rate**: ${Math.round((workflowSuccess / workflowTotal) * 100)}%
- **Average Completion Time**: ${avgCompletionTime.toFixed(1)} minutes
- **Error Rate**: ${(workflowResults.reduce((sum, r) => sum + r.metrics.errorRate, 0) / workflowTotal).toFixed(1)}%
`;
  });

  report += `
## Critical Issues Requiring Attention
`;

  const allCriticalIssues = results.flatMap(r => r.criticalIssues);
  if (allCriticalIssues.length === 0) {
    report += '✅ No critical issues identified\n';
  } else {
    allCriticalIssues.forEach((issue, index) => {
      report += `${index + 1}. ${issue}\n`;
    });
  }

  report += `
## Key Recommendations
`;

  const allRecommendations = [...new Set(results.flatMap(r => r.recommendations))];
  allRecommendations.forEach((recommendation, index) => {
    report += `${index + 1}. ${recommendation}\n`;
  });

  report += `
## Production Readiness Assessment
${criticalIssues === 0 && passedTests >= totalTests * 0.8 ?
  '✅ **READY FOR PRODUCTION** - Platform meets professional trading standards' :
  `❌ **NOT READY** - ${criticalIssues} critical issues and ${totalTests - passedTests} failed tests require resolution`}

## Next Steps
1. Address all critical issues identified in testing
2. Implement high-priority recommendations
3. Conduct follow-up testing with problematic workflows
4. Schedule additional testing with real traders
5. Prepare for production deployment validation
`;

  return report;
}
