/**
 * TradingConsole Accessibility Tests
 *
 * Comprehensive WCAG 2.1 AA compliance testing for the trading console
 * Validates keyboard navigation, screen reader compatibility, and color contrast
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {
  testAccessibility,
  testKeyboardNavigation,
  testScreenReaderCompatibility,
  testColorContrast,
  generateAccessibilityReport,
  tradingAccessibilityHelpers
} from '@/test-utils/accessibility';
import TradingConsole from '../TradingConsole';

// Mock dependencies
jest.mock('@/stores/useTradingStore', () => ({
  useTradingStore: jest.fn(() => ({
    accountInfo: {
      balance: 100000,
      equity: 102500,
      marginUsed: 2500,
      availableMargin: 97500,
      marginLevel: 4100,
    },
    positions: [],
    orders: [],
    getTotalPnL: jest.fn(() => 2500),
  })),
}));

jest.mock('@/stores/useMarketDataStore', () => ({
  useMarketDataStore: jest.fn(() => ({
    isConnected: true,
    marketData: {
      EURUSD: { bid: 1.08245, ask: 1.08248 },
      GBPUSD: { bid: 1.27156, ask: 1.27159 }
    },
    lastUpdateTime: new Date().toISOString(),
  })),
}));

jest.mock('@/hooks/useWebSocket', () => ({
  useWebSocket: jest.fn(() => ({
    connect: jest.fn(),
    connectionStatus: 'connected',
  })),
}));

jest.mock('../OrderPanel', () => {
  return function MockOrderPanel() {
    return (
      <div role="region" aria-label="Order Panel">
        <h2>Quick Order</h2>
        <form aria-label="Place Order">
          <label htmlFor="symbol-select">Symbol</label>
          <select id="symbol-select" aria-required="true">
            <option value="EURUSD">EUR/USD</option>
            <option value="GBPUSD">GBP/USD</option>
          </select>

          <label htmlFor="quantity-input">Quantity</label>
          <input
            id="quantity-input"
            type="number"
            aria-required="true"
            aria-describedby="quantity-help"
          />
          <div id="quantity-help" className="sr-only">
            Enter the trade quantity in base currency units
          </div>

          <button type="submit" aria-describedby="order-submit-help">
            Place Order
          </button>
          <div id="order-submit-help" className="sr-only">
            Submit your trading order for execution
          </div>
        </form>
      </div>
    );
  };
});

jest.mock('../PositionsTable', () => {
  return function MockPositionsTable() {
    return (
      <table role="table" aria-label="Open Positions">
        <caption>Currently open trading positions</caption>
        <thead>
          <tr>
            <th scope="col">Symbol</th>
            <th scope="col">Side</th>
            <th scope="col">Quantity</th>
            <th scope="col">P&L</th>
            <th scope="col">Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>EUR/USD</td>
            <td>Long</td>
            <td>10,000</td>
            <td>+$45.00</td>
            <td>
              <button aria-label="Close EUR/USD position">Close</button>
            </td>
          </tr>
        </tbody>
      </table>
    );
  };
});

jest.mock('../OrdersTable', () => {
  return function MockOrdersTable() {
    return (
      <table role="table" aria-label="Active Orders">
        <caption>Pending and active trading orders</caption>
        <thead>
          <tr>
            <th scope="col">Symbol</th>
            <th scope="col">Type</th>
            <th scope="col">Quantity</th>
            <th scope="col">Price</th>
            <th scope="col">Status</th>
            <th scope="col">Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>GBP/USD</td>
            <td>Limit Buy</td>
            <td>5,000</td>
            <td>1.2700</td>
            <td>Pending</td>
            <td>
              <button aria-label="Cancel GBP/USD order">Cancel</button>
            </td>
          </tr>
        </tbody>
      </table>
    );
  };
});

jest.mock('@/components/data/MarketDataGrid', () => {
  return function MockMarketDataGrid() {
    return (
      <div role="grid" aria-label="Market Data">
        <div role="row" aria-label="Header row">
          <div role="columnheader">Symbol</div>
          <div role="columnheader">Bid</div>
          <div role="columnheader">Ask</div>
          <div role="columnheader">Spread</div>
        </div>
        <div role="row" aria-label="EUR/USD market data">
          <div role="gridcell">EUR/USD</div>
          <div role="gridcell">1.08245</div>
          <div role="gridcell">1.08248</div>
          <div role="gridcell">0.3</div>
        </div>
      </div>
    );
  };
});

describe('TradingConsole Accessibility Tests', () => {
  let user: ReturnType<typeof userEvent.setup>;

  beforeEach(() => {
    user = userEvent.setup();
  });

  describe('WCAG 2.1 AA Compliance', () => {
    it('should pass comprehensive accessibility audit', async () => {
      const { container } = render(<TradingConsole />);

      const results = await testAccessibility(<TradingConsole />);

      // Generate detailed report
      const report = generateAccessibilityReport(results, 'TradingConsole');
      console.log('\n' + report);

      // Assert compliance
      expect(results.summary.complianceScore).toBeGreaterThanOrEqual(90);
      expect(results.summary.criticalViolations).toBe(0);
      expect(results.violations).toHaveLength(0);
    });

    it('should have proper heading structure', async () => {
      render(<TradingConsole />);

      const screenReaderResults = await testScreenReaderCompatibility(<TradingConsole />);

      expect(screenReaderResults.success).toBe(true);
      expect(screenReaderResults.headingStructure).toContain('h1');
      expect(screenReaderResults.issues).toHaveLength(0);
    });

    it('should have sufficient color contrast', async () => {
      const contrastResults = await testColorContrast(<TradingConsole />);

      expect(contrastResults.success).toBe(true);
      expect(contrastResults.issues).toHaveLength(0);

      // All contrast ratios should meet AA standard (4.5:1 for normal text, 3:1 for large text)
      contrastResults.contrastRatios.forEach(ratio => {
        expect(ratio.passes).toBe(true);
      });
    });
  });

  describe('Keyboard Navigation', () => {
    it('should support comprehensive keyboard navigation', async () => {
      render(<TradingConsole />);

      const expectedFocusableElements = [
        'button', // Refresh button
        '[role="tab"]', // Tab navigation
        'select', // Order panel select
        'input', // Order panel inputs
        '[role="button"]', // Action buttons
      ];

      const keyboardResults = await testKeyboardNavigation(
        <TradingConsole />,
        expectedFocusableElements
      );

      expect(keyboardResults.success).toBe(true);
      expect(keyboardResults.issues).toHaveLength(0);
      expect(keyboardResults.focusableElements.length).toBeGreaterThan(5);
    });

    it('should handle tab navigation correctly', async () => {
      render(<TradingConsole />);

      // Test tab sequence
      await user.tab();
      expect(document.activeElement).toHaveAttribute('aria-label');

      // Continue tabbing through focusable elements
      await user.tab();
      await user.tab();

      // Should not create keyboard traps
      expect(document.activeElement).not.toBe(null);
    });

    it('should support arrow key navigation in tabs', async () => {
      render(<TradingConsole />);

      // Focus on tab list
      const overviewTab = screen.getByRole('tab', { name: /overview/i });
      await user.click(overviewTab);

      // Test arrow key navigation
      await user.keyboard('{ArrowRight}');
      expect(document.activeElement).toHaveAttribute('role', 'tab');

      await user.keyboard('{ArrowLeft}');
      expect(document.activeElement).toHaveAttribute('role', 'tab');
    });

    it('should support Enter and Space for button activation', async () => {
      render(<TradingConsole />);

      const refreshButton = screen.getByRole('button', { name: /refresh/i });
      refreshButton.focus();

      // Test Enter key activation
      await user.keyboard('{Enter}');
      expect(refreshButton).toHaveBeenCalled;

      // Test Space key activation
      await user.keyboard(' ');
      expect(refreshButton).toHaveBeenCalled;
    });
  });

  describe('Screen Reader Compatibility', () => {
    it('should have proper ARIA labels and descriptions', async () => {
      render(<TradingConsole />);

      const screenReaderResults = await testScreenReaderCompatibility(<TradingConsole />);

      expect(screenReaderResults.success).toBe(true);
      expect(screenReaderResults.ariaLabels.length).toBeGreaterThan(5);
      expect(screenReaderResults.issues).toHaveLength(0);
    });

    it('should announce account balance changes', () => {
      render(<TradingConsole />);

      const balanceElement = screen.getByTestId('account-balance');
      expect(balanceElement).toHaveAttribute('aria-live', 'polite');
      expect(balanceElement).toHaveTextContent('$100,000.00');
    });

    it('should announce P&L changes', () => {
      render(<TradingConsole />);

      const balanceElement = screen.getByTestId('account-balance');
      expect(balanceElement).toBeInTheDocument();

      // P&L should be announced when it changes
      const pnlIndicators = screen.getAllByText(/\+?\$[\d,]+\.?\d*/);
      expect(pnlIndicators.length).toBeGreaterThan(0);
    });

    it('should have proper table structure', () => {
      render(<TradingConsole />);

      // Check for proper table semantics
      const tables = screen.getAllByRole('table');
      expect(tables.length).toBeGreaterThanOrEqual(1);

      tables.forEach(table => {
        expect(table).toHaveAttribute('aria-label');
      });
    });

    it('should have proper landmark regions', () => {
      render(<TradingConsole />);

      // Main content should be in a main landmark
      const mainContent = screen.getByRole('main', { hidden: true }) || screen.getByTestId('trading-console');
      expect(mainContent).toBeInTheDocument();

      // Order panel should be a complementary region
      const orderRegion = screen.getByRole('region', { name: /order panel/i });
      expect(orderRegion).toBeInTheDocument();
    });
  });

  describe('Form Accessibility', () => {
    it('should have properly labeled form controls', async () => {
      render(<TradingConsole />);

      const forms = screen.getAllByRole('form');

      for (const form of forms) {
        const formResults = await tradingAccessibilityHelpers.testTradingForm(form as HTMLElement);
        expect(formResults.success).toBe(true);
        expect(formResults.issues).toHaveLength(0);
      }
    });

    it('should associate error messages with form fields', () => {
      render(<TradingConsole />);

      // Check for proper error message association
      const quantityInput = screen.getByLabelText(/quantity/i);
      const helpText = screen.getByText(/enter the trade quantity/i);

      expect(quantityInput).toHaveAttribute('aria-describedby');
      expect(helpText).toHaveAttribute('id');
    });

    it('should indicate required fields', () => {
      render(<TradingConsole />);

      const requiredFields = screen.getAllByRole('textbox', { required: true }) ||
                           screen.getAllByRole('combobox', { required: true });

      requiredFields.forEach(field => {
        expect(field).toHaveAttribute('aria-required', 'true');
      });
    });
  });

  describe('Mobile Accessibility', () => {
    it('should maintain accessibility on mobile viewports', async () => {
      // Mock mobile viewport
      Object.defineProperty(window, 'innerWidth', {
        writable: true,
        configurable: true,
        value: 375,
      });

      const results = await testAccessibility(<TradingConsole />);

      expect(results.summary.complianceScore).toBeGreaterThanOrEqual(90);
      expect(results.summary.criticalViolations).toBe(0);
    });

    it('should have touch-friendly target sizes', () => {
      render(<TradingConsole />);

      const buttons = screen.getAllByRole('button');

      buttons.forEach(button => {
        const styles = window.getComputedStyle(button);
        const height = parseInt(styles.height);
        const width = parseInt(styles.width);

        // WCAG guideline: touch targets should be at least 44x44px
        expect(height).toBeGreaterThanOrEqual(44);
        expect(width).toBeGreaterThanOrEqual(44);
      });
    });
  });

  describe('High Contrast Mode', () => {
    it('should remain functional in high contrast mode', () => {
      // Mock high contrast mode
      Object.defineProperty(window, 'matchMedia', {
        writable: true,
        value: jest.fn().mockImplementation(query => ({
          matches: query === '(prefers-contrast: high)',
          media: query,
          onchange: null,
          addListener: jest.fn(),
          removeListener: jest.fn(),
          addEventListener: jest.fn(),
          removeEventListener: jest.fn(),
          dispatchEvent: jest.fn(),
        })),
      });

      render(<TradingConsole />);

      // Elements should still be visible and functional
      const tradingConsole = screen.getByTestId('trading-console');
      expect(tradingConsole).toBeVisible();

      const buttons = screen.getAllByRole('button');
      buttons.forEach(button => {
        expect(button).toBeVisible();
      });
    });
  });

  describe('Reduced Motion', () => {
    it('should respect reduced motion preferences', () => {
      // Mock reduced motion preference
      Object.defineProperty(window, 'matchMedia', {
        writable: true,
        value: jest.fn().mockImplementation(query => ({
          matches: query === '(prefers-reduced-motion: reduce)',
          media: query,
          onchange: null,
          addListener: jest.fn(),
          removeListener: jest.fn(),
          addEventListener: jest.fn(),
          removeEventListener: jest.fn(),
          dispatchEvent: jest.fn(),
        })),
      });

      render(<TradingConsole />);

      // Animations should be disabled or reduced
      const animatedElements = screen.getAllByRole('button');
      animatedElements.forEach(element => {
        const styles = window.getComputedStyle(element);
        // Check that animations are disabled when motion is reduced
        expect(styles.animationDuration).toBe('0s');
      });
    });
  });

  describe('Focus Management', () => {
    it('should manage focus when switching tabs', async () => {
      render(<TradingConsole />);

      const positionsTab = screen.getByRole('tab', { name: /positions/i });
      const ordersTab = screen.getByRole('tab', { name: /orders/i });

      // Click positions tab
      await user.click(positionsTab);
      expect(positionsTab).toHaveAttribute('aria-selected', 'true');

      // Click orders tab
      await user.click(ordersTab);
      expect(ordersTab).toHaveAttribute('aria-selected', 'true');
      expect(positionsTab).toHaveAttribute('aria-selected', 'false');
    });

    it('should trap focus in modal dialogs', async () => {
      render(<TradingConsole />);

      // On mobile, the floating action button should open a modal
      const fab = screen.getByRole('button', { name: /open order panel/i });
      if (fab) {
        await user.click(fab);

        // Focus should be trapped within the modal
        const modal = screen.getByRole('dialog', { hidden: true });
        if (modal) {
          const focusableElements = modal.querySelectorAll(
            'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
          );

          expect(focusableElements.length).toBeGreaterThan(0);
        }
      }
    });
  });
});
