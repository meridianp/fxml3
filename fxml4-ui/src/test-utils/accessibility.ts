/**
 * Accessibility Testing Utilities
 *
 * Comprehensive WCAG 2.1 AA compliance testing framework
 * for professional trading platform accessibility validation
 */

import { configureAxe, toHaveNoViolations } from 'jest-axe';
import { render, RenderResult } from '@testing-library/react';
import { ReactElement } from 'react';

// Extend Jest matchers
expect.extend(toHaveNoViolations);

// WCAG 2.1 AA Configuration with valid axe-core rules
const axe = configureAxe({
  rules: {
    // Core WCAG 2.1 AA rules (using valid axe-core rule names)
    'color-contrast': { enabled: true },
    'aria-valid-attr-value': { enabled: true },
    'aria-valid-attr': { enabled: true },
    'aria-allowed-attr': { enabled: true },
    'button-name': { enabled: true },
    'link-name': { enabled: true },
    'label': { enabled: true },
    'heading-order': { enabled: true },
    'landmark-unique': { enabled: true },
    'list': { enabled: true },
    'image-alt': { enabled: true },
    'form-field-multiple-labels': { enabled: true },

    // Trading-specific accessibility requirements
    'bypass': { enabled: true }, // Skip navigation for screen readers
    'page-has-heading-one': { enabled: true },
    'region': { enabled: true },
    'aria-hidden-focus': { enabled: true },
    'tabindex': { enabled: true },
    'focus-order-semantics': { enabled: true },

    // Disable AAA level rules - we target AA
    'color-contrast-enhanced': { enabled: false },
  },
  tags: ['wcag2a', 'wcag2aa', 'wcag21aa']
});

/**
 * Trading Platform Accessibility Test Suite
 */
export interface AccessibilityTestOptions {
  skipColorContrast?: boolean;
  skipKeyboardNav?: boolean;
  skipScreenReader?: boolean;
  customRules?: any;
  testLevel?: 'AA' | 'AAA';
}

export interface AccessibilityTestResult {
  violations: any[];
  passes: any[];
  incomplete: any[];
  inaccessible: any[];
  summary: {
    totalViolations: number;
    criticalViolations: number;
    seriousViolations: number;
    moderateViolations: number;
    minorViolations: number;
    complianceScore: number;
  };
}

/**
 * Run comprehensive accessibility tests on a component
 */
export async function testAccessibility(
  component: ReactElement,
  options: AccessibilityTestOptions = {}
): Promise<AccessibilityTestResult> {
  const { container } = render(component);

  // Configure axe with custom options
  const customAxe = options.customRules ? configureAxe(options.customRules) : axe;

  // Run accessibility scan
  const results = await customAxe(container, {
    tags: options.testLevel === 'AAA' ? ['wcag2aaa'] : ['wcag2a', 'wcag2aa', 'wcag21aa'],
    rules: {
      ...(!options.skipColorContrast && { 'color-contrast': { enabled: true } }),
      ...(!options.skipKeyboardNav && { 'tabindex': { enabled: true }, 'focus-order-semantics': { enabled: true } }),
      ...(!options.skipScreenReader && { 'aria-valid-attr': { enabled: true }, 'button-name': { enabled: true } }),
    }
  });

  // Calculate compliance metrics
  const summary = calculateComplianceMetrics(results);

  return {
    violations: results.violations,
    passes: results.passes,
    incomplete: results.incomplete,
    inaccessible: results.inaccessible,
    summary
  };
}

/**
 * Test keyboard navigation functionality
 */
export async function testKeyboardNavigation(
  component: ReactElement,
  expectedFocusableElements: string[]
): Promise<{
  success: boolean;
  focusableElements: string[];
  tabOrder: string[];
  issues: string[];
}> {
  const { container } = render(component);
  const issues: string[] = [];

  // Find all focusable elements
  const focusableElements = container.querySelectorAll(
    'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"]), [role="button"], [role="link"]'
  );

  const focusableSelectors = Array.from(focusableElements).map(el =>
    el.tagName.toLowerCase() + (el.id ? `#${el.id}` : '') + (el.className ? `.${el.className.split(' ')[0]}` : '')
  );

  // Check if all expected elements are focusable
  expectedFocusableElements.forEach(selector => {
    if (!focusableSelectors.some(fs => fs.includes(selector))) {
      issues.push(`Expected focusable element not found: ${selector}`);
    }
  });

  // Test tab order
  const tabOrder: string[] = [];
  focusableElements.forEach((element: Element) => {
    const tabIndex = (element as HTMLElement).tabIndex;
    if (tabIndex >= 0) {
      tabOrder.push(element.tagName.toLowerCase() + (element.id ? `#${element.id}` : ''));
    }
  });

  // Check for keyboard traps
  if (focusableElements.length > 0 && tabOrder.length === 0) {
    issues.push('No focusable elements found - potential keyboard trap');
  }

  return {
    success: issues.length === 0,
    focusableElements: focusableSelectors,
    tabOrder,
    issues
  };
}

/**
 * Test screen reader compatibility
 */
export async function testScreenReaderCompatibility(
  component: ReactElement
): Promise<{
  success: boolean;
  ariaLabels: string[];
  headingStructure: string[];
  landmarks: string[];
  issues: string[];
}> {
  const { container } = render(component);
  const issues: string[] = [];

  // Check ARIA labels
  const elementsWithAriaLabels = container.querySelectorAll('[aria-label], [aria-labelledby], [aria-describedby]');
  const ariaLabels = Array.from(elementsWithAriaLabels).map(el =>
    (el as HTMLElement).getAttribute('aria-label') ||
    (el as HTMLElement).getAttribute('aria-labelledby') ||
    (el as HTMLElement).getAttribute('aria-describedby') || ''
  );

  // Check heading structure
  const headings = container.querySelectorAll('h1, h2, h3, h4, h5, h6');
  const headingStructure = Array.from(headings).map(h => h.tagName.toLowerCase());

  // Validate heading hierarchy
  if (headings.length > 0) {
    let currentLevel = 0;
    headings.forEach(heading => {
      const level = parseInt(heading.tagName.charAt(1));
      if (currentLevel === 0) {
        currentLevel = level;
      } else if (level > currentLevel + 1) {
        issues.push(`Heading hierarchy skip: ${heading.tagName} follows h${currentLevel}`);
      }
      currentLevel = level;
    });
  }

  // Check landmarks
  const landmarks = container.querySelectorAll('[role="main"], [role="navigation"], [role="banner"], [role="contentinfo"], [role="complementary"], [role="search"], main, nav, header, footer, aside');
  const landmarkTypes = Array.from(landmarks).map(el =>
    (el as HTMLElement).getAttribute('role') || el.tagName.toLowerCase()
  );

  // Check for missing alt text on images
  const images = container.querySelectorAll('img');
  images.forEach(img => {
    if (!(img as HTMLImageElement).alt && !(img as HTMLElement).getAttribute('aria-label')) {
      issues.push(`Image missing alt text: ${(img as HTMLImageElement).src || 'unknown'}`);
    }
  });

  // Check for form labels
  const inputs = container.querySelectorAll('input, select, textarea');
  inputs.forEach(input => {
    const id = (input as HTMLElement).id;
    const label = container.querySelector(`label[for="${id}"]`);
    const ariaLabel = (input as HTMLElement).getAttribute('aria-label');

    if (!label && !ariaLabel) {
      issues.push(`Form input missing label: ${(input as HTMLInputElement).type || input.tagName}`);
    }
  });

  return {
    success: issues.length === 0,
    ariaLabels,
    headingStructure,
    landmarks: landmarkTypes,
    issues
  };
}

/**
 * Test color contrast compliance
 */
export async function testColorContrast(
  component: ReactElement
): Promise<{
  success: boolean;
  contrastRatios: Array<{
    element: string;
    ratio: number;
    required: number;
    passes: boolean;
  }>;
  issues: string[];
}> {
  const { container } = render(component);
  const results = await axe(container, {
    rules: {
      'color-contrast': { enabled: true }
    }
  });

  const issues: string[] = [];
  const contrastRatios: Array<{
    element: string;
    ratio: number;
    required: number;
    passes: boolean;
  }> = [];

  results.violations.forEach(violation => {
    if (violation.id === 'color-contrast') {
      violation.nodes.forEach((node: any) => {
        const ratio = node.any[0]?.data?.contrastRatio || 0;
        const required = node.any[0]?.data?.requiredContrastRatio || 4.5;

        contrastRatios.push({
          element: node.target[0] || 'unknown',
          ratio,
          required,
          passes: ratio >= required
        });

        if (ratio < required) {
          issues.push(`Insufficient color contrast: ${node.target[0]} (${ratio}:1, required: ${required}:1)`);
        }
      });
    }
  });

  return {
    success: issues.length === 0,
    contrastRatios,
    issues
  };
}

/**
 * Calculate compliance metrics
 */
function calculateComplianceMetrics(results: any): AccessibilityTestResult['summary'] {
  const violations = results.violations || [];

  const criticalViolations = violations.filter((v: any) => v.impact === 'critical').length;
  const seriousViolations = violations.filter((v: any) => v.impact === 'serious').length;
  const moderateViolations = violations.filter((v: any) => v.impact === 'moderate').length;
  const minorViolations = violations.filter((v: any) => v.impact === 'minor').length;

  const totalViolations = violations.length;
  const totalTests = (results.passes?.length || 0) + totalViolations + (results.incomplete?.length || 0);

  // Calculate compliance score (0-100)
  const complianceScore = totalTests > 0
    ? Math.round(((totalTests - totalViolations) / totalTests) * 100)
    : 100;

  return {
    totalViolations,
    criticalViolations,
    seriousViolations,
    moderateViolations,
    minorViolations,
    complianceScore
  };
}

/**
 * Generate accessibility report
 */
export function generateAccessibilityReport(
  testResults: AccessibilityTestResult,
  componentName: string
): string {
  const { summary, violations, passes } = testResults;

  let report = `# Accessibility Report: ${componentName}\n\n`;
  report += `## Summary\n`;
  report += `- **Compliance Score**: ${summary.complianceScore}%\n`;
  report += `- **Total Violations**: ${summary.totalViolations}\n`;
  report += `- **Tests Passed**: ${passes.length}\n\n`;

  if (summary.criticalViolations > 0) {
    report += `🔴 **Critical Issues**: ${summary.criticalViolations}\n`;
  }
  if (summary.seriousViolations > 0) {
    report += `🟠 **Serious Issues**: ${summary.seriousViolations}\n`;
  }
  if (summary.moderateViolations > 0) {
    report += `🟡 **Moderate Issues**: ${summary.moderateViolations}\n`;
  }
  if (summary.minorViolations > 0) {
    report += `🟢 **Minor Issues**: ${summary.minorViolations}\n`;
  }

  if (violations.length > 0) {
    report += `\n## Violations\n`;
    violations.forEach((violation, index) => {
      report += `\n### ${index + 1}. ${violation.description}\n`;
      report += `- **Impact**: ${violation.impact}\n`;
      report += `- **Help**: ${violation.helpUrl}\n`;
      if (violation.nodes?.length > 0) {
        report += `- **Elements**: ${violation.nodes.map((n: any) => n.target[0]).join(', ')}\n`;
      }
    });
  }

  report += `\n## Recommendations\n`;

  if (summary.complianceScore < 80) {
    report += `- 🚨 **Critical**: Compliance score below 80% - immediate attention required\n`;
  }
  if (summary.criticalViolations > 0) {
    report += `- 🔴 **High Priority**: Address critical accessibility violations\n`;
  }
  if (summary.seriousViolations > 0) {
    report += `- 🟠 **Medium Priority**: Fix serious accessibility issues\n`;
  }

  report += `- ✅ **WCAG 2.1 AA Target**: Achieve 100% compliance score\n`;
  report += `- 📱 **Mobile Testing**: Validate on mobile devices\n`;
  report += `- 🔊 **Screen Reader Testing**: Test with NVDA, JAWS, VoiceOver\n`;

  return report;
}

// Trading-specific accessibility helpers
export const tradingAccessibilityHelpers = {
  /**
   * Verify trading chart accessibility
   */
  async testTradingChart(chartContainer: HTMLElement) {
    const issues: string[] = [];

    // Check for accessible labels
    const hasAriaLabel = chartContainer.hasAttribute('aria-label') || chartContainer.hasAttribute('aria-labelledby');
    const hasRole = chartContainer.hasAttribute('role');
    const isFocusable = chartContainer.hasAttribute('tabindex') || chartContainer.tabIndex >= 0;
    const hasDescription = chartContainer.hasAttribute('aria-describedby') ||
                          chartContainer.querySelector('[aria-describedby]');

    if (!hasAriaLabel) {
      issues.push('Chart should have aria-label or aria-labelledby for screen readers');
    }
    if (!hasRole) {
      issues.push('Chart should have appropriate role (application, img, or region)');
    }
    if (!isFocusable) {
      issues.push('Chart should be keyboard accessible with tabindex');
    }
    if (!hasDescription) {
      issues.push('Chart should have accessible description for complex content');
    }

    return { success: issues.length === 0, issues };
  },

  /**
   * Verify trading form accessibility
   */
  async testTradingForm(formElement: HTMLElement) {
    const issues: string[] = [];

    // Check required field indicators
    const requiredFields = formElement.querySelectorAll('[required]');
    requiredFields.forEach(field => {
      const label = formElement.querySelector(`label[for="${(field as HTMLElement).id}"]`);
      if (label && !label.textContent?.includes('*') && !(field as HTMLElement).getAttribute('aria-required')) {
        issues.push(`Required field missing indicator: ${(field as HTMLInputElement).name || field.id}`);
      }
    });

    // Check error message association
    const errorMessages = formElement.querySelectorAll('[role="alert"], .error-message');
    errorMessages.forEach(error => {
      const associatedField = formElement.querySelector(`[aria-describedby="${error.id}"]`);
      if (!associatedField) {
        issues.push(`Error message not associated with form field: ${error.textContent}`);
      }
    });

    return { success: issues.length === 0, issues };
  }
};
