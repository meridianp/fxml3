/**
 * AnalyticsPanel Component Tests
 *
 * Comprehensive test suite for the AnalyticsPanel component
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AnalyticsPanel, AnalyticsPanelLayout } from './AnalyticsPanel';
import { useAnalyticsEnhancement } from '@/hooks/useAnalyticsEnhancement';
import {
  KPI,
  KPIStatus,
  TrendDirection,
  AnalyticsCategory,
  SystemHealth,
} from '@/types/analytics';
import { DataManagementAlert } from '@/types/dataManagement';

// Mock the analytics enhancement hook
jest.mock('@/hooks/useAnalyticsEnhancement');

const mockUseAnalyticsEnhancement = useAnalyticsEnhancement as jest.MockedFunction<typeof useAnalyticsEnhancement>;

// Mock services
const mockDataSourceService = {
  getConnectionStatus: jest.fn(),
};

const mockStorageMetricsService = {
  getStorageMetrics: jest.fn(),
};

const mockDataQualityService = {
  getQualityReport: jest.fn(),
};

const mockPipelineService = {
  getPipelineStatus: jest.fn(),
};

// Mock data
const mockSystemHealth: SystemHealth = {
  overall: 85,
  components: {
    dataSource: 90,
    storage: 80,
    quality: 85,
    pipeline: 85,
  },
  status: 'healthy',
  lastUpdated: new Date('2024-01-15T10:00:00Z'),
  trends: {
    overall: TrendDirection.STABLE,
  },
};

const mockKPIs: KPI[] = [
  {
    id: 'system-health',
    name: 'System Health',
    description: 'Overall system health score',
    category: AnalyticsCategory.SYSTEM,
    metric: 'system_health',
    target: 95,
    unit: '%',
    thresholds: {
      critical: { min: 60 },
      warning: { min: 80 },
      target: { min: 95, max: 100 },
    },
    status: KPIStatus.GOOD,
    currentValue: 85,
    trend: TrendDirection.STABLE,
    lastUpdated: new Date('2024-01-15T10:00:00Z'),
  },
  {
    id: 'data-quality',
    name: 'Data Quality',
    description: 'Data quality score',
    category: AnalyticsCategory.DATA_QUALITY,
    metric: 'data_quality_score',
    target: 95,
    unit: '%',
    thresholds: {
      critical: { min: 70 },
      warning: { min: 85 },
      target: { min: 95, max: 100 },
    },
    status: KPIStatus.WARNING,
    currentValue: 89,
    trend: TrendDirection.DECREASING,
    lastUpdated: new Date('2024-01-15T10:00:00Z'),
  },
];

const mockAlerts: DataManagementAlert[] = [
  {
    id: 'alert-1',
    type: 'data_quality',
    severity: 'warning',
    title: 'Data Quality Warning',
    message: 'Data quality score below threshold',
    source: 'analytics',
    timestamp: new Date('2024-01-15T10:00:00Z'),
    category: 'quality',
  },
  {
    id: 'alert-2',
    type: 'system',
    severity: 'critical',
    title: 'System Health Critical',
    message: 'System health requires immediate attention',
    source: 'analytics',
    timestamp: new Date('2024-01-15T10:01:00Z'),
    category: 'health',
  },
];

const mockAnalyticsEnhancementReturn = {
  state: {
    isInitialized: true,
    isLoading: false,
    error: null,
    analytics: null,
    systemHealth: mockSystemHealth,
    insights: [],
    kpis: mockKPIs,
    alerts: mockAlerts,
  },
  actions: {
    initialize: jest.fn(),
    refresh: jest.fn(),
    updateTimeRange: jest.fn(),
    generateReport: jest.fn(),
    exportData: jest.fn(),
    dismissAlert: jest.fn(),
    getKPIsByCategory: jest.fn(),
    getSystemHealthScore: jest.fn(() => 85),
    getPerformanceScore: jest.fn(() => 78),
    getRecommendations: jest.fn(() => []),
  },
  isHealthy: true,
  hasWarnings: true,
  hasCriticalIssues: false,
  quickStats: {
    totalKPIs: 2,
    healthyKPIs: 1,
    warningKPIs: 1,
    criticalKPIs: 0,
    systemHealthScore: 85,
    performanceScore: 78,
  },
};

describe('AnalyticsPanel', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockUseAnalyticsEnhancement.mockReturnValue(mockAnalyticsEnhancementReturn);
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  describe('Component Rendering', () => {
    it('renders analytics panel with loading state', () => {
      mockUseAnalyticsEnhancement.mockReturnValue({
        ...mockAnalyticsEnhancementReturn,
        state: {
          ...mockAnalyticsEnhancementReturn.state,
          isLoading: true,
          analytics: null,
        },
      });

      render(<AnalyticsPanel />);

      expect(screen.getByText('Loading analytics...')).toBeInTheDocument();
    });

    it('renders analytics panel after loading', async () => {
      render(<AnalyticsPanel />);

      await waitFor(() => {
        expect(screen.getByTestId('analytics-panel')).toBeInTheDocument();
      });

      expect(screen.getByText('Analytics')).toBeInTheDocument();
    });

    it('renders error state when analytics fails', async () => {
      mockUseAnalyticsEnhancement.mockReturnValue({
        ...mockAnalyticsEnhancementReturn,
        state: {
          ...mockAnalyticsEnhancementReturn.state,
          error: 'Analytics service failed',
        },
      });

      render(<AnalyticsPanel />);

      await waitFor(() => {
        expect(screen.getByText('Analytics Error')).toBeInTheDocument();
        expect(screen.getByText('Analytics service failed')).toBeInTheDocument();
      });
    });

    it('renders with different layouts', async () => {
      const layouts = [
        AnalyticsPanelLayout.VERTICAL,
        AnalyticsPanelLayout.HORIZONTAL,
        AnalyticsPanelLayout.GRID,
        AnalyticsPanelLayout.COMPACT,
      ];

      for (const layout of layouts) {
        const { unmount } = render(<AnalyticsPanel layout={layout} />);

        await waitFor(() => {
          expect(screen.getByTestId('analytics-panel')).toBeInTheDocument();
        });

        unmount();
      }
    });
  });

  describe('Health Indicator', () => {
    it('displays system health indicator with correct status', async () => {
      render(<AnalyticsPanel showSystemHealth={true} />);

      await waitFor(() => {
        expect(screen.getByTestId('health-indicator')).toBeInTheDocument();
      });

      expect(screen.getByText('85%')).toBeInTheDocument();
    });

    it('shows correct health colors based on status', async () => {
      const healthStatuses = [
        { health: mockSystemHealth, isHealthy: true, hasWarnings: false, hasCritical: false },
        {
          health: { ...mockSystemHealth, status: 'warning' as const },
          isHealthy: false,
          hasWarnings: true,
          hasCritical: false
        },
        {
          health: { ...mockSystemHealth, status: 'critical' as const },
          isHealthy: false,
          hasWarnings: false,
          hasCritical: true
        },
      ];

      for (const { health, isHealthy, hasWarnings, hasCritical } of healthStatuses) {
        mockUseAnalyticsEnhancement.mockReturnValue({
          ...mockAnalyticsEnhancementReturn,
          state: {
            ...mockAnalyticsEnhancementReturn.state,
            systemHealth: health,
          },
          isHealthy,
          hasWarnings,
          hasCriticalIssues: hasCritical,
        });

        const { unmount } = render(<AnalyticsPanel showSystemHealth={true} />);

        await waitFor(() => {
          const healthIndicator = screen.getByTestId('health-indicator');
          expect(healthIndicator).toBeInTheDocument();

          if (isHealthy) {
            expect(healthIndicator).toHaveClass('bg-green-100', 'text-green-800');
          } else if (hasWarnings) {
            expect(healthIndicator).toHaveClass('bg-yellow-100', 'text-yellow-800');
          } else if (hasCritical) {
            expect(healthIndicator).toHaveClass('bg-red-100', 'text-red-800');
          }
        });

        unmount();
      }
    });

    it('handles health indicator click', async () => {
      const onHealthClick = jest.fn();

      render(
        <AnalyticsPanel
          showSystemHealth={true}
          onHealthClick={onHealthClick}
        />
      );

      await waitFor(() => {
        const healthIndicator = screen.getByTestId('health-indicator');
        fireEvent.click(healthIndicator);
      });

      expect(onHealthClick).toHaveBeenCalledWith(mockSystemHealth);
    });
  });

  describe('Quick Stats Display', () => {
    it('displays quick stats correctly', async () => {
      render(<AnalyticsPanel showQuickStats={true} />);

      await waitFor(() => {
        expect(screen.getByTestId('quick-stats')).toBeInTheDocument();
      });

      expect(screen.getByText('2')).toBeInTheDocument(); // Total KPIs
      expect(screen.getByText('78%')).toBeInTheDocument(); // Performance
      expect(screen.getByText('0')).toBeInTheDocument(); // Critical (2 instances)
      expect(screen.getByText('1')).toBeInTheDocument(); // Warnings
    });

    it('shows correct colors for performance indicators', async () => {
      render(<AnalyticsPanel showQuickStats={true} />);

      await waitFor(() => {
        const performanceElement = screen.getByText('78%');
        expect(performanceElement).toHaveClass('text-yellow-600'); // Below 80%
      });
    });

    it('hides quick stats when showQuickStats is false', async () => {
      render(<AnalyticsPanel showQuickStats={false} />);

      await waitFor(() => {
        expect(screen.getByTestId('analytics-panel')).toBeInTheDocument();
      });

      expect(screen.queryByTestId('quick-stats')).not.toBeInTheDocument();
    });
  });

  describe('Panel Interactions', () => {
    it('toggles panel expansion', async () => {
      render(<AnalyticsPanel />);

      await waitFor(() => {
        expect(screen.getByTestId('analytics-panel')).toBeInTheDocument();
      });

      const toggleButton = screen.getByTestId('toggle-panel');

      // Panel should be expanded by default
      expect(screen.getByTestId('quick-stats')).toBeInTheDocument();

      // Click to collapse
      fireEvent.click(toggleButton);
      expect(screen.queryByTestId('quick-stats')).not.toBeInTheDocument();

      // Click to expand
      fireEvent.click(toggleButton);
      expect(screen.getByTestId('quick-stats')).toBeInTheDocument();
    });

    it('handles refresh button click', async () => {
      render(<AnalyticsPanel />);

      await waitFor(() => {
        const refreshButton = screen.getByTestId('refresh-button');
        fireEvent.click(refreshButton);
      });

      expect(mockAnalyticsEnhancementReturn.actions.refresh).toHaveBeenCalled();
    });

    it('disables refresh button when loading', async () => {
      mockUseAnalyticsEnhancement.mockReturnValue({
        ...mockAnalyticsEnhancementReturn,
        state: {
          ...mockAnalyticsEnhancementReturn.state,
          isLoading: true,
        },
      });

      render(<AnalyticsPanel />);

      await waitFor(() => {
        const refreshButton = screen.getByTestId('refresh-button');
        expect(refreshButton).toBeDisabled();
      });
    });
  });

  describe('Tab Navigation', () => {
    it('renders tab navigation in non-compact mode', async () => {
      render(<AnalyticsPanel compactMode={false} />);

      await waitFor(() => {
        expect(screen.getByTestId('tab-navigation')).toBeInTheDocument();
      });

      expect(screen.getByTestId('tab-overview')).toBeInTheDocument();
      expect(screen.getByTestId('tab-kpis')).toBeInTheDocument();
      expect(screen.getByTestId('tab-health')).toBeInTheDocument();
      expect(screen.getByTestId('tab-insights')).toBeInTheDocument();
      expect(screen.getByTestId('tab-alerts')).toBeInTheDocument();
    });

    it('hides tab navigation in compact mode', async () => {
      render(<AnalyticsPanel compactMode={true} />);

      await waitFor(() => {
        expect(screen.getByTestId('analytics-panel')).toBeInTheDocument();
      });

      expect(screen.queryByTestId('tab-navigation')).not.toBeInTheDocument();
    });

    it('switches between tabs correctly', async () => {
      render(<AnalyticsPanel compactMode={false} />);

      await waitFor(() => {
        expect(screen.getByTestId('tab-navigation')).toBeInTheDocument();
      });

      // Should start on overview tab
      expect(screen.getByTestId('overview-content')).toBeInTheDocument();

      // Switch to KPIs tab
      const kpisTab = screen.getByTestId('tab-kpis');
      fireEvent.click(kpisTab);

      expect(screen.getByTestId('kpis-content')).toBeInTheDocument();
      expect(screen.queryByTestId('overview-content')).not.toBeInTheDocument();

      // Switch to alerts tab
      const alertsTab = screen.getByTestId('tab-alerts');
      fireEvent.click(alertsTab);

      expect(screen.getByTestId('alerts-content')).toBeInTheDocument();
      expect(screen.queryByTestId('kpis-content')).not.toBeInTheDocument();
    });
  });

  describe('KPI Display', () => {
    it('displays KPIs in overview content', async () => {
      render(<AnalyticsPanel showKPIs={true} />);

      await waitFor(() => {
        expect(screen.getByText('Key Metrics')).toBeInTheDocument();
      });

      expect(screen.getByTestId('kpi-system-health')).toBeInTheDocument();
      expect(screen.getByTestId('kpi-data-quality')).toBeInTheDocument();
      expect(screen.getByText('System Health')).toBeInTheDocument();
      expect(screen.getByText('Data Quality')).toBeInTheDocument();
    });

    it('handles KPI click events', async () => {
      const onKPIClick = jest.fn();

      render(
        <AnalyticsPanel
          showKPIs={true}
          onKPIClick={onKPIClick}
        />
      );

      await waitFor(() => {
        const kpiElement = screen.getByTestId('kpi-system-health');
        fireEvent.click(kpiElement);
      });

      expect(onKPIClick).toHaveBeenCalledWith(mockKPIs[0]);
    });

    it('displays KPI status with correct colors', async () => {
      render(<AnalyticsPanel showKPIs={true} />);

      await waitFor(() => {
        const goodStatus = screen.getByText('good');
        const warningStatus = screen.getByText('warning');

        expect(goodStatus).toHaveClass('text-blue-600', 'bg-blue-100');
        expect(warningStatus).toHaveClass('text-yellow-600', 'bg-yellow-100');
      });
    });

    it('shows trend icons for KPIs', async () => {
      render(<AnalyticsPanel showKPIs={true} />);

      await waitFor(() => {
        // Should show trend icons (emojis)
        expect(screen.getByText('📊')).toBeInTheDocument(); // Stable trend
        expect(screen.getByText('📉')).toBeInTheDocument(); // Decreasing trend
      });
    });
  });

  describe('Alerts Display', () => {
    it('displays alert count in header', async () => {
      render(<AnalyticsPanel showAlerts={true} />);

      await waitFor(() => {
        expect(screen.getByText('2 alerts')).toBeInTheDocument();
      });
    });

    it('displays alerts in alerts tab', async () => {
      render(<AnalyticsPanel compactMode={false} showAlerts={true} />);

      await waitFor(() => {
        const alertsTab = screen.getByTestId('tab-alerts');
        fireEvent.click(alertsTab);
      });

      expect(screen.getByText('Data Quality Warning')).toBeInTheDocument();
      expect(screen.getByText('System Health Critical')).toBeInTheDocument();
    });

    it('handles alert click events', async () => {
      const onAlertClick = jest.fn();

      render(
        <AnalyticsPanel
          compactMode={false}
          showAlerts={true}
          onAlertClick={onAlertClick}
        />
      );

      await waitFor(() => {
        const alertsTab = screen.getByTestId('tab-alerts');
        fireEvent.click(alertsTab);
      });

      const alertElement = screen.getByText('Data Quality Warning').closest('div');
      if (alertElement) {
        fireEvent.click(alertElement);
        expect(onAlertClick).toHaveBeenCalledWith(mockAlerts[0]);
      }
    });

    it('handles alert dismissal', async () => {
      render(<AnalyticsPanel compactMode={false} showAlerts={true} />);

      await waitFor(() => {
        const alertsTab = screen.getByTestId('tab-alerts');
        fireEvent.click(alertsTab);
      });

      const dismissButtons = screen.getAllByText('✕');
      fireEvent.click(dismissButtons[0]);

      expect(mockAnalyticsEnhancementReturn.actions.dismissAlert).toHaveBeenCalledWith('alert-1');
    });

    it('shows no alerts message when no alerts exist', async () => {
      mockUseAnalyticsEnhancement.mockReturnValue({
        ...mockAnalyticsEnhancementReturn,
        state: {
          ...mockAnalyticsEnhancementReturn.state,
          alerts: [],
        },
      });

      render(<AnalyticsPanel compactMode={false} showAlerts={true} />);

      await waitFor(() => {
        const alertsTab = screen.getByTestId('tab-alerts');
        fireEvent.click(alertsTab);
      });

      expect(screen.getByText('No alerts')).toBeInTheDocument();
    });
  });

  describe('Service Integration', () => {
    it('initializes with provided services', async () => {
      render(
        <AnalyticsPanel
          dataSourceService={mockDataSourceService as any}
          storageMetricsService={mockStorageMetricsService as any}
          dataQualityService={mockDataQualityService as any}
          pipelineService={mockPipelineService as any}
        />
      );

      await waitFor(() => {
        expect(mockAnalyticsEnhancementReturn.actions.initialize).toHaveBeenCalledWith({
          dataSource: mockDataSourceService,
          storage: mockStorageMetricsService,
          dataQuality: mockDataQualityService,
          pipeline: mockPipelineService,
        });
      });
    });

    it('handles initialization errors', async () => {
      const onError = jest.fn();
      mockAnalyticsEnhancementReturn.actions.initialize.mockRejectedValue(new Error('Init failed'));

      render(<AnalyticsPanel onError={onError} />);

      await waitFor(() => {
        expect(onError).toHaveBeenCalledWith(expect.any(Error));
      });
    });
  });

  describe('Responsive Design', () => {
    it('adapts layout for compact mode', async () => {
      const { rerender } = render(<AnalyticsPanel compactMode={false} />);

      await waitFor(() => {
        expect(screen.getByTestId('tab-navigation')).toBeInTheDocument();
      });

      rerender(<AnalyticsPanel compactMode={true} />);

      expect(screen.queryByTestId('tab-navigation')).not.toBeInTheDocument();
      expect(screen.getByTestId('overview-content')).toBeInTheDocument();
    });

    it('limits KPIs in compact mode', async () => {
      const manyKPIs = Array.from({ length: 10 }, (_, i) => ({
        ...mockKPIs[0],
        id: `kpi-${i}`,
        name: `KPI ${i}`,
      }));

      mockUseAnalyticsEnhancement.mockReturnValue({
        ...mockAnalyticsEnhancementReturn,
        state: {
          ...mockAnalyticsEnhancementReturn.state,
          kpis: manyKPIs,
        },
      });

      render(<AnalyticsPanel compactMode={true} showKPIs={true} />);

      await waitFor(() => {
        // Should only show first 3 KPIs in compact mode
        expect(screen.getByTestId('kpi-kpi-0')).toBeInTheDocument();
        expect(screen.getByTestId('kpi-kpi-1')).toBeInTheDocument();
        expect(screen.getByTestId('kpi-kpi-2')).toBeInTheDocument();
        expect(screen.queryByTestId('kpi-kpi-3')).not.toBeInTheDocument();
      });
    });
  });

  describe('Accessibility', () => {
    it('has proper button roles and labels', async () => {
      render(<AnalyticsPanel />);

      await waitFor(() => {
        const refreshButton = screen.getByTestId('refresh-button');
        const toggleButton = screen.getByTestId('toggle-panel');

        expect(refreshButton).toHaveAttribute('type', 'button');
        expect(toggleButton).toHaveAttribute('type', 'button');
      });
    });

    it('supports keyboard navigation', async () => {
      render(<AnalyticsPanel />);

      await waitFor(() => {
        const refreshButton = screen.getByTestId('refresh-button');
        refreshButton.focus();
        expect(refreshButton).toHaveFocus();
      });
    });
  });
});
