/**
 * Professional Trader Testing Integration Tests
 *
 * Comprehensive integration tests for the professional trader UAT framework
 * Validates trader profiles, workflows, and feedback collection
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import {
  runProfessionalTraderTest,
  TRADER_PROFILES,
  TRADING_WORKFLOW_TESTS,
  generateProfessionalTraderReport
} from '@/test-utils/professionalTraderTesting';

// Mock professional trading platform for testing
const MockProfessionalTradingPlatform = () => (
  <div data-testid="professional-trading-platform">
    <header role="banner">
      <h1>FXML4 Professional Trading Platform</h1>
      <nav role="navigation" aria-label="Main navigation">
        <ul>
          <li><a href="/dashboard" aria-current="page">Dashboard</a></li>
          <li><a href="/trading">Trading Console</a></li>
          <li><a href="/analysis">Market Analysis</a></li>
          <li><a href="/risk">Risk Management</a></li>
          <li><a href="/reports">Reports</a></li>
        </ul>
      </nav>
    </header>

    <main role="main">
      {/* Login Section */}
      <section aria-labelledby="login-section" className="login-form">
        <h2 id="login-section">Secure Login</h2>
        <form aria-label="Login form">
          <label htmlFor="email">Email</label>
          <input id="email" type="email" aria-required="true" />

          <label htmlFor="password">Password</label>
          <input id="password" type="password" aria-required="true" />

          <button type="submit" aria-describedby="login-help">
            Login
          </button>
          <div id="login-help" className="sr-only">
            Login to access your professional trading account
          </div>
        </form>
      </section>

      {/* Trading Console */}
      <section aria-labelledby="trading-console">
        <h2 id="trading-console">Professional Trading Console</h2>

        {/* Quick Order Panel */}
        <div className="order-panel" role="region" aria-label="Quick Order Entry">
          <h3>Quick Order Entry</h3>
          <form aria-label="Professional order placement">
            <label htmlFor="pro-symbol">Symbol</label>
            <select id="pro-symbol" aria-required="true">
              <option value="">Select Symbol</option>
              <option value="EURUSD">EUR/USD</option>
              <option value="GBPUSD">GBP/USD</option>
              <option value="USDJPY">USD/JPY</option>
              <option value="AUDUSD">AUD/USD</option>
            </select>

            <label htmlFor="pro-quantity">Quantity</label>
            <input
              id="pro-quantity"
              type="number"
              aria-required="true"
              min="10000"
              max="50000000"
              step="10000"
            />

            <label htmlFor="pro-price">Price</label>
            <input
              id="pro-price"
              type="number"
              step="0.00001"
              aria-describedby="price-help"
            />
            <div id="price-help" className="help-text">
              Leave blank for market order
            </div>

            <div className="order-actions">
              <button
                type="button"
                className="buy-order"
                aria-label="Place buy order"
                data-testid="professional-buy-button"
              >
                BUY
              </button>
              <button
                type="button"
                className="sell-order"
                aria-label="Place sell order"
                data-testid="professional-sell-button"
              >
                SELL
              </button>
              <button
                type="button"
                className="close-all"
                aria-label="Close all positions"
                data-testid="close-all-button"
              >
                CLOSE ALL
              </button>
            </div>
          </form>
        </div>

        {/* Professional Market Data */}
        <div className="market-data-professional" role="region" aria-label="Professional Market Data">
          <h3>Live Market Data</h3>
          <table role="table" aria-label="Professional market quotes">
            <caption>Real-time professional market data with Level II quotes</caption>
            <thead>
              <tr>
                <th scope="col">Symbol</th>
                <th scope="col">Bid</th>
                <th scope="col">Ask</th>
                <th scope="col">Spread</th>
                <th scope="col">Volume</th>
                <th scope="col">Change</th>
                <th scope="col">Volatility</th>
              </tr>
            </thead>
            <tbody>
              {[
                { symbol: 'EURUSD', bid: '1.08234', ask: '1.08237', spread: '0.3', volume: '2.4M', change: '+0.12%', volatility: '0.45%' },
                { symbol: 'GBPUSD', bid: '1.27145', ask: '1.27149', spread: '0.4', volume: '1.8M', change: '-0.08%', volatility: '0.62%' },
                { symbol: 'USDJPY', bid: '149.234', ask: '149.237', spread: '0.3', volume: '3.1M', change: '+0.34%', volatility: '0.38%' },
                { symbol: 'AUDUSD', bid: '0.65432', ask: '0.65436', spread: '0.4', volume: '1.2M', change: '-0.15%', volatility: '0.55%' }
              ].map(quote => (
                <tr key={quote.symbol} data-testid={`market-${quote.symbol}`}>
                  <td>{quote.symbol}</td>
                  <td aria-live="polite">{quote.bid}</td>
                  <td aria-live="polite">{quote.ask}</td>
                  <td>{quote.spread}</td>
                  <td>{quote.volume}</td>
                  <td className={quote.change.startsWith('+') ? 'positive' : 'negative'}>
                    {quote.change}
                  </td>
                  <td>{quote.volatility}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Professional Position Management */}
        <div className="position-management" role="region" aria-label="Position Management">
          <h3>Active Positions</h3>
          <table role="table" aria-label="Active trading positions">
            <caption>Currently active positions with real-time P&L</caption>
            <thead>
              <tr>
                <th scope="col">Position ID</th>
                <th scope="col">Symbol</th>
                <th scope="col">Side</th>
                <th scope="col">Quantity</th>
                <th scope="col">Entry Price</th>
                <th scope="col">Current Price</th>
                <th scope="col">P&L</th>
                <th scope="col">Stop Loss</th>
                <th scope="col">Take Profit</th>
                <th scope="col">Actions</th>
              </tr>
            </thead>
            <tbody>
              {Array.from({ length: 15 }, (_, i) => {
                const symbols = ['EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD'];
                const symbol = symbols[i % symbols.length];
                const side = i % 2 === 0 ? 'Long' : 'Short';
                const pnl = (Math.random() - 0.5) * 5000;

                return (
                  <tr key={i} data-testid={`professional-position-${i}`}>
                    <td>POS_{String(i + 1000).padStart(6, '0')}</td>
                    <td>{symbol}</td>
                    <td>{side}</td>
                    <td>{(100000 + Math.floor(Math.random() * 4900000)).toLocaleString()}</td>
                    <td>{(1.0000 + Math.random() * 0.5).toFixed(5)}</td>
                    <td aria-live="polite">{(1.0000 + Math.random() * 0.5).toFixed(5)}</td>
                    <td
                      aria-live="polite"
                      className={pnl >= 0 ? 'positive' : 'negative'}
                      data-testid={`professional-pnl-${i}`}
                    >
                      {pnl >= 0 ? '+' : ''}${pnl.toFixed(2)}
                    </td>
                    <td>{(1.0000 + Math.random() * 0.3).toFixed(5)}</td>
                    <td>{(1.0000 + Math.random() * 0.7).toFixed(5)}</td>
                    <td>
                      <button
                        aria-label={`Close ${symbol} position`}
                        data-testid={`close-position-${i}`}
                        className="action-button"
                      >
                        Close
                      </button>
                      <button
                        aria-label={`Modify ${symbol} position`}
                        data-testid={`modify-position-${i}`}
                        className="action-button"
                      >
                        Modify
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* Risk Management Dashboard */}
        <div className="risk-dashboard" role="region" aria-label="Risk Management">
          <h3>Risk Management</h3>
          <div className="risk-metrics">
            <div className="risk-card">
              <h4>Account Risk</h4>
              <div className="risk-value" data-testid="account-risk">2.3%</div>
              <div className="risk-limit">Max: 5.0%</div>
            </div>
            <div className="risk-card">
              <h4>Position Risk</h4>
              <div className="risk-value" data-testid="position-risk">1.8%</div>
              <div className="risk-limit">Max: 2.0%</div>
            </div>
            <div className="risk-card">
              <h4>Margin Usage</h4>
              <div className="risk-value" data-testid="margin-usage">45.2%</div>
              <div className="risk-limit">Max: 80.0%</div>
            </div>
            <div className="risk-card">
              <h4>Daily VaR</h4>
              <div className="risk-value" data-testid="daily-var">$12,450</div>
              <div className="risk-limit">Max: $25,000</div>
            </div>
          </div>

          <div className="risk-actions">
            <button
              className="emergency-close"
              aria-label="Emergency close all positions"
              data-testid="emergency-close-button"
            >
              EMERGENCY CLOSE ALL
            </button>
            <button
              className="risk-settings"
              aria-label="Configure risk settings"
              data-testid="risk-settings-button"
            >
              Risk Settings
            </button>
          </div>
        </div>
      </section>

      {/* Professional Chart Analysis */}
      <section aria-labelledby="chart-analysis">
        <h2 id="chart-analysis">Advanced Chart Analysis</h2>
        <div
          role="application"
          aria-label="Professional trading chart with advanced analysis tools"
          aria-describedby="chart-description"
          tabIndex="0"
          className="professional-chart"
          data-testid="professional-chart"
          style={{ width: '100%', height: '600px', background: '#0a0a0a', border: '1px solid #333' }}
        >
          <div id="chart-description" className="sr-only">
            Advanced professional trading chart with multiple timeframes, technical indicators,
            and drawing tools. Use arrow keys to navigate, + and - to zoom, space to draw.
          </div>

          {/* Chart Controls */}
          <div className="chart-controls" role="toolbar" aria-label="Chart controls">
            <button aria-label="Zoom in" data-testid="zoom-in">+</button>
            <button aria-label="Zoom out" data-testid="zoom-out">-</button>
            <button aria-label="Pan mode" data-testid="pan-mode">Pan</button>
            <button aria-label="Draw trend line" data-testid="trend-line">Line</button>
            <button aria-label="Add Fibonacci retracement" data-testid="fibonacci">Fib</button>
          </div>

          {/* Mock chart data points */}
          <div className="chart-data">
            {Array.from({ length: 2000 }, (_, i) => (
              <div
                key={i}
                className="chart-candle"
                style={{
                  position: 'absolute',
                  left: `${(i / 2000) * 100}%`,
                  top: `${20 + Math.random() * 60}%`,
                  width: '1px',
                  height: `${Math.random() * 20 + 5}px`,
                  background: i % 2 === 0 ? '#00ff00' : '#ff0000'
                }}
                data-testid={`candle-${i}`}
              />
            ))}
          </div>
        </div>
      </section>
    </main>

    {/* Status and Alerts */}
    <div role="status" aria-live="polite" aria-label="System status">
      <div data-testid="connection-status">Connected to professional trading servers</div>
      <div data-testid="latency-status">Latency: 12ms</div>
    </div>

    <div role="alert" aria-live="assertive" className="alert-container">
      {/* Professional trading alerts appear here */}
    </div>
  </div>
);

describe('Professional Trader Testing Integration', () => {
  describe('Trader Profile Validation', () => {
    it('should have comprehensive trader profiles defined', () => {
      expect(TRADER_PROFILES.length).toBeGreaterThanOrEqual(5);

      const expertTrader = TRADER_PROFILES.find(p => p.experience === 'expert');
      const institutionalTrader = TRADER_PROFILES.find(p => p.experience === 'institutional');
      const accessibilityTrader = TRADER_PROFILES.find(p => p.accessibilityRequirements);

      expect(expertTrader).toBeDefined();
      expect(institutionalTrader).toBeDefined();
      expect(accessibilityTrader).toBeDefined();

      // Validate profile structure
      TRADER_PROFILES.forEach(profile => {
        expect(profile).toHaveProperty('id');
        expect(profile).toHaveProperty('experience');
        expect(profile).toHaveProperty('tradingStyle');
        expect(profile).toHaveProperty('primaryAssets');
        expect(profile).toHaveProperty('tradingFrequency');
        expect(profile).toHaveProperty('techProficiency');
        expect(profile).toHaveProperty('preferredDevices');
        expect(profile).toHaveProperty('keyboardShortcuts');
        expect(profile).toHaveProperty('averageSessionLength');

        expect(Array.isArray(profile.primaryAssets)).toBe(true);
        expect(Array.isArray(profile.preferredDevices)).toBe(true);
        expect(typeof profile.keyboardShortcuts).toBe('boolean');
        expect(typeof profile.averageSessionLength).toBe('number');
      });
    });

    it('should have profiles covering different experience levels', () => {
      const experiences = TRADER_PROFILES.map(p => p.experience);
      const uniqueExperiences = [...new Set(experiences)];

      expect(uniqueExperiences).toContain('novice');
      expect(uniqueExperiences).toContain('intermediate');
      expect(uniqueExperiences).toContain('expert');
      expect(uniqueExperiences.length).toBeGreaterThanOrEqual(3);
    });

    it('should have profiles covering different trading styles', () => {
      const styles = TRADER_PROFILES.map(p => p.tradingStyle);
      const uniqueStyles = [...new Set(styles)];

      expect(uniqueStyles).toContain('day_trading');
      expect(uniqueStyles).toContain('scalping');
      expect(uniqueStyles.length).toBeGreaterThanOrEqual(3);
    });
  });

  describe('Trading Workflow Tests Validation', () => {
    it('should have comprehensive trading workflow tests', () => {
      expect(TRADING_WORKFLOW_TESTS.length).toBeGreaterThanOrEqual(4);

      const criticalWorkflows = TRADING_WORKFLOW_TESTS.filter(w => w.priority === 'critical');
      const orderManagementWorkflows = TRADING_WORKFLOW_TESTS.filter(w => w.category === 'order_management');
      const accessibilityWorkflows = TRADING_WORKFLOW_TESTS.filter(w => w.targetProfiles.includes('expert') &&
        w.steps.some(s => s.assistiveInstructions));

      expect(criticalWorkflows.length).toBeGreaterThanOrEqual(2);
      expect(orderManagementWorkflows.length).toBeGreaterThanOrEqual(1);
      expect(accessibilityWorkflows.length).toBeGreaterThanOrEqual(1);
    });

    it('should have properly structured workflow tests', () => {
      TRADING_WORKFLOW_TESTS.forEach(workflow => {
        expect(workflow).toHaveProperty('id');
        expect(workflow).toHaveProperty('name');
        expect(workflow).toHaveProperty('description');
        expect(workflow).toHaveProperty('category');
        expect(workflow).toHaveProperty('priority');
        expect(workflow).toHaveProperty('estimatedDuration');
        expect(workflow).toHaveProperty('targetProfiles');
        expect(workflow).toHaveProperty('steps');
        expect(workflow).toHaveProperty('successCriteria');

        expect(Array.isArray(workflow.targetProfiles)).toBe(true);
        expect(Array.isArray(workflow.steps)).toBe(true);
        expect(Array.isArray(workflow.successCriteria)).toBe(true);
        expect(workflow.steps.length).toBeGreaterThan(0);
        expect(workflow.successCriteria.length).toBeGreaterThan(0);

        // Validate step structure
        workflow.steps.forEach(step => {
          expect(step).toHaveProperty('id');
          expect(step).toHaveProperty('stepNumber');
          expect(step).toHaveProperty('description');
          expect(step).toHaveProperty('userAction');
          expect(step).toHaveProperty('expectedResult');
          expect(step).toHaveProperty('validation');
          expect(step.validation).toHaveProperty('method');
          expect(step.validation).toHaveProperty('criteria');
          expect(Array.isArray(step.validation.criteria)).toBe(true);
        });

        // Validate success criteria
        workflow.successCriteria.forEach(criterion => {
          expect(criterion).toHaveProperty('id');
          expect(criterion).toHaveProperty('description');
          expect(criterion).toHaveProperty('measurable');
          expect(criterion).toHaveProperty('target');
          expect(criterion).toHaveProperty('method');
          expect(typeof criterion.measurable).toBe('boolean');
        });
      });
    });
  });

  describe('Professional Trader Test Execution', () => {
    it('should run expert trader rapid order execution test', async () => {
      render(<MockProfessionalTradingPlatform />);

      const expertTrader = TRADER_PROFILES.find(p => p.id === 'expert_day_trader')!;
      const rapidOrderTest = TRADING_WORKFLOW_TESTS.find(t => t.id === 'rapid_order_execution')!;

      expect(expertTrader).toBeDefined();
      expect(rapidOrderTest).toBeDefined();

      const result = await runProfessionalTraderTest(
        <MockProfessionalTradingPlatform />,
        rapidOrderTest,
        expertTrader
      );

      expect(result).toHaveProperty('workflowId', 'rapid_order_execution');
      expect(result).toHaveProperty('profileId', 'expert_day_trader');
      expect(result).toHaveProperty('overallSuccess');
      expect(result).toHaveProperty('metrics');
      expect(result).toHaveProperty('feedback');

      expect(result.metrics).toHaveProperty('taskCompletionRate');
      expect(result.metrics).toHaveProperty('userSatisfaction');
      expect(result.feedback).toHaveProperty('usabilityRating');
      expect(result.feedback).toHaveProperty('comments');
    }, 20000);

    it('should run mobile trader workflow test', async () => {
      render(<MockProfessionalTradingPlatform />);

      const mobileTrader = TRADER_PROFILES.find(p => p.id === 'mobile_trader')!;
      const mobileWorkflow = TRADING_WORKFLOW_TESTS.find(t => t.id === 'mobile_trading_workflow')!;

      expect(mobileTrader).toBeDefined();
      expect(mobileWorkflow).toBeDefined();

      const result = await runProfessionalTraderTest(
        <MockProfessionalTradingPlatform />,
        mobileWorkflow,
        mobileTrader
      );

      expect(result.workflowId).toBe('mobile_trading_workflow');
      expect(result.profileId).toBe('mobile_trader');
      expect(typeof result.overallSuccess).toBe('boolean');
      expect(result.metrics.taskCompletionRate).toBeGreaterThanOrEqual(0);
      expect(result.metrics.taskCompletionRate).toBeLessThanOrEqual(100);
    }, 15000);

    it('should run accessibility compliance test', async () => {
      render(<MockProfessionalTradingPlatform />);

      const accessibilityTrader = TRADER_PROFILES.find(p => p.accessibilityRequirements)!;
      const accessibilityTest = TRADING_WORKFLOW_TESTS.find(t => t.id === 'accessibility_compliance_test')!;

      expect(accessibilityTrader).toBeDefined();
      expect(accessibilityTest).toBeDefined();

      const result = await runProfessionalTraderTest(
        <MockProfessionalTradingPlatform />,
        accessibilityTest,
        accessibilityTrader
      );

      expect(result.workflowId).toBe('accessibility_compliance_test');
      expect(result.feedback.accessibility).toBeDefined();
      expect(result.feedback.accessibility?.screenReaderCompatible).toBeDefined();
      expect(result.feedback.accessibility?.keyboardNavigable).toBeDefined();
    }, 25000);

    it('should run risk management workflow test', async () => {
      render(<MockProfessionalTradingPlatform />);

      const institutionalTrader = TRADER_PROFILES.find(p => p.experience === 'institutional')!;
      const riskTest = TRADING_WORKFLOW_TESTS.find(t => t.id === 'risk_management_workflow')!;

      expect(institutionalTrader).toBeDefined();
      expect(riskTest).toBeDefined();

      const result = await runProfessionalTraderTest(
        <MockProfessionalTradingPlatform />,
        riskTest,
        institutionalTrader
      );

      expect(result.workflowId).toBe('risk_management_workflow');
      expect(result.metrics.errorRate).toBeLessThanOrEqual(100);
      expect(result.recommendations).toBeInstanceOf(Array);
    }, 18000);
  });

  describe('UAT Report Generation', () => {
    it('should generate comprehensive professional trader report', async () => {
      // Run a subset of tests to generate report data
      const expertTrader = TRADER_PROFILES.find(p => p.experience === 'expert')!;
      const orderTest = TRADING_WORKFLOW_TESTS.find(t => t.category === 'order_management')!;

      const testResults = [];

      // Run test
      const result = await runProfessionalTraderTest(
        <MockProfessionalTradingPlatform />,
        orderTest,
        expertTrader
      );
      testResults.push(result);

      // Generate report
      const report = generateProfessionalTraderReport(testResults);

      expect(report).toContain('Professional Trader User Acceptance Testing Report');
      expect(report).toContain('Executive Summary');
      expect(report).toContain('Test Results by Profile');
      expect(report).toContain('Workflow Performance Analysis');
      expect(report).toContain('Production Readiness Assessment');

      console.log('\n=== PROFESSIONAL TRADER UAT REPORT ===\n' + report.substring(0, 2000) + '...\n');
    }, 15000);
  });

  describe('Platform Component Validation', () => {
    it('should have professional trading interface elements', () => {
      render(<MockProfessionalTradingPlatform />);

      // Verify professional trading elements exist
      const platform = screen.getByTestId('professional-trading-platform');
      expect(platform).toBeInTheDocument();

      // Check professional order buttons
      const buyButton = screen.getByTestId('professional-buy-button');
      const sellButton = screen.getByTestId('professional-sell-button');
      const closeAllButton = screen.getByTestId('close-all-button');

      expect(buyButton).toBeInTheDocument();
      expect(sellButton).toBeInTheDocument();
      expect(closeAllButton).toBeInTheDocument();
    });

    it('should have professional market data structure', () => {
      render(<MockProfessionalTradingPlatform />);

      // Check market data table
      const marketTable = screen.getByRole('table', { name: /professional market quotes/i });
      expect(marketTable).toBeInTheDocument();

      // Verify specific market data rows
      const eurUsdRow = screen.getByTestId('market-EURUSD');
      const gbpUsdRow = screen.getByTestId('market-GBPUSD');
      expect(eurUsdRow).toBeInTheDocument();
      expect(gbpUsdRow).toBeInTheDocument();
    });

    it('should have professional position management', () => {
      render(<MockProfessionalTradingPlatform />);

      // Check positions table
      const positionsTable = screen.getByRole('table', { name: /active trading positions/i });
      expect(positionsTable).toBeInTheDocument();

      // Verify position rows exist
      const position0 = screen.getByTestId('professional-position-0');
      const position10 = screen.getByTestId('professional-position-10');
      expect(position0).toBeInTheDocument();
      expect(position10).toBeInTheDocument();
    });

    it('should have risk management dashboard', () => {
      render(<MockProfessionalTradingPlatform />);

      // Check risk metrics
      const accountRisk = screen.getByTestId('account-risk');
      const positionRisk = screen.getByTestId('position-risk');
      const marginUsage = screen.getByTestId('margin-usage');
      const dailyVar = screen.getByTestId('daily-var');

      expect(accountRisk).toBeInTheDocument();
      expect(positionRisk).toBeInTheDocument();
      expect(marginUsage).toBeInTheDocument();
      expect(dailyVar).toBeInTheDocument();

      // Check emergency controls
      const emergencyCloseButton = screen.getByTestId('emergency-close-button');
      expect(emergencyCloseButton).toBeInTheDocument();
    });

    it('should have professional chart interface', () => {
      render(<MockProfessionalTradingPlatform />);

      // Check professional chart
      const chart = screen.getByTestId('professional-chart');
      expect(chart).toBeInTheDocument();
      expect(chart).toHaveAttribute('role', 'application');
      expect(chart).toHaveAttribute('tabIndex', '0');

      // Check chart controls
      const zoomIn = screen.getByTestId('zoom-in');
      const zoomOut = screen.getByTestId('zoom-out');
      const trendLine = screen.getByTestId('trend-line');

      expect(zoomIn).toBeInTheDocument();
      expect(zoomOut).toBeInTheDocument();
      expect(trendLine).toBeInTheDocument();
    });

    it('should have system status indicators', () => {
      render(<MockProfessionalTradingPlatform />);

      // Check status indicators
      const connectionStatus = screen.getByTestId('connection-status');
      const latencyStatus = screen.getByTestId('latency-status');

      expect(connectionStatus).toBeInTheDocument();
      expect(latencyStatus).toBeInTheDocument();
      expect(connectionStatus).toHaveTextContent('Connected to professional trading servers');
    });
  });
});
