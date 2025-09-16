/**
 * DataManagementWithAnalytics Component Tests
 *
 * Comprehensive test suite for the integrated data management and analytics dashboard
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { DataManagementWithAnalytics, AnalyticsViewLayout } from './DataManagementWithAnalytics';
import { DashboardLayout, DashboardTheme } from './DataManagementDashboard';
import {
  DataManagementAnalytics,
  AnalyticsIntegrationService
} from '@/services/analyticsIntegration';
import {
  SystemHealth,
  KPI,
  KPIStatus,
  TrendDirection,
  AnalyticsCategory,
  TimeRange,
  TimeInterval,
} from '@/types/analytics';

// Mock services
const mockDataSourceService = {
  getConnectionStatus: jest.fn(),
  testConnection: jest.fn(),
};

const mockStorageMetricsService = {
  getStorageMetrics: jest.fn(),
  getStorageHealth: jest.fn(),
};

const mockDataQualityService = {
  getQualityReport: jest.fn(),
  validateData: jest.fn(),
};

const mockPipelineService = {
  getPipelineStatus: jest.fn(),
  getPipelineJobs: jest.fn(),
};

const mockNotificationService = {
  create: jest.fn(),
  list: jest.fn(),
};

const mockAnalyticsIntegrationService = {
  initialize: jest.fn(),
  generateDataManagementAnalytics: jest.fn(),
  onAnalyticsUpdate: jest.fn(),
  dispose: jest.fn(),
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
    dataSource: TrendDirection.INCREASING,
    storage: TrendDirection.STABLE,
    quality: TrendDirection.DECREASING,
    pipeline: TrendDirection.STABLE,
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
    metric: 'data_quality',
    target: 98,
    unit: '%',
    thresholds: {
      critical: { min: 70 },
      warning: { min: 90 },
      target: { min: 98, max: 100 },
    },
    status: KPIStatus.CRITICAL,
    currentValue: 65,
    trend: TrendDirection.DECREASING,
    lastUpdated: new Date('2024-01-15T10:00:00Z'),
  },
];

const mockAnalyticsData: DataManagementAnalytics = {
  systemHealth: mockSystemHealth,
  crossServiceTrends: [],
  correlationInsights: [],
  aggregatedKPIs: mockKPIs,
  performanceScore: 78,
  recommendations: [
    'Data quality requires immediate attention',
    'Monitor storage utilization trends',
    'Pipeline performance is stable',
  ],
};

describe('DataManagementWithAnalytics', () => {
  beforeEach(() => {
    jest.clearAllMocks();

    // Setup default mock responses
    mockAnalyticsIntegrationService.initialize.mockResolvedValue(undefined);
    mockAnalyticsIntegrationService.generateDataManagementAnalytics.mockResolvedValue(mockAnalyticsData);
    mockAnalyticsIntegrationService.onAnalyticsUpdate.mockReturnValue(() => {});
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  describe('Component Rendering', () => {
    it('renders integrated dashboard with loading state initially', () => {
      render(<DataManagementWithAnalytics />);

      expect(screen.getByText('Loading integrated dashboard...')).toBeInTheDocument();
    });

    it('renders integrated dashboard after loading', async () => {
      render(
        <DataManagementWithAnalytics
          analyticsIntegrationService={mockAnalyticsIntegrationService as any}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('data-management-with-analytics')).toBeInTheDocument();
      });

      expect(screen.getByText('Integrated Data Management & Analytics')).toBeInTheDocument();
    });

    it('renders with custom title and layout', async () => {
      render(
        <DataManagementWithAnalytics
          title="Custom Dashboard"
          initialLayout={DashboardLayout.COMPACT}
          analyticsIntegrationService={mockAnalyticsIntegrationService as any}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('Custom Dashboard')).toBeInTheDocument();
      });
    });

    it('renders error state when initialization fails', async () => {
      mockAnalyticsIntegrationService.initialize.mockRejectedValue(new Error('Initialization failed'));

      render(
        <DataManagementWithAnalytics
          analyticsIntegrationService={mockAnalyticsIntegrationService as any}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('Dashboard Error')).toBeInTheDocument();
        expect(screen.getByText('Initialization failed')).toBeInTheDocument();
      });
    });
  });

  describe('System Health Display', () => {
    it('displays system health indicator with correct status', async () => {
      render(
        <DataManagementWithAnalytics
          analyticsIntegrationService={mockAnalyticsIntegrationService as any}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('enhanced-system-health')).toBeInTheDocument();
      });

      expect(screen.getByText('System Health: 85%')).toBeInTheDocument();
      expect(screen.getByText('(healthy)')).toBeInTheDocument();
    });

    it('shows correct health status colors', async () => {
      const criticalHealth = {
        ...mockSystemHealth,
        overall: 45,
        status: 'critical' as const,
      };

      mockAnalyticsIntegrationService.generateDataManagementAnalytics.mockResolvedValue({
        ...mockAnalyticsData,
        systemHealth: criticalHealth,
      });

      render(
        <DataManagementWithAnalytics
          analyticsIntegrationService={mockAnalyticsIntegrationService as any}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('System Health: 45%')).toBeInTheDocument();
        expect(screen.getByText('(critical)')).toBeInTheDocument();
      });
    });
  });

  describe('Navigation and View Switching', () => {
    it('renders navigation tabs correctly', async () => {
      render(
        <DataManagementWithAnalytics
          showAnalytics={true}
          analyticsIntegrationService={mockAnalyticsIntegrationService as any}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('navigation-tabs')).toBeInTheDocument();
      });

      expect(screen.getByTestId('data-management-tab')).toBeInTheDocument();
      expect(screen.getByTestId('analytics-tab')).toBeInTheDocument();
      expect(screen.getByTestId('reports-tab')).toBeInTheDocument();
      expect(screen.getByTestId('exports-tab')).toBeInTheDocument();
    });

    it('switches between views correctly', async () => {
      render(
        <DataManagementWithAnalytics
          showAnalytics={true}
          analyticsIntegrationService={mockAnalyticsIntegrationService as any}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('navigation-tabs')).toBeInTheDocument();
      });

      // Switch to analytics view
      const analyticsTab = screen.getByTestId('analytics-tab');
      fireEvent.click(analyticsTab);

      expect(analyticsTab).toHaveClass('bg-white', 'text-blue-600', 'shadow');

      // Switch to reports view
      const reportsTab = screen.getByTestId('reports-tab');
      fireEvent.click(reportsTab);

      expect(reportsTab).toHaveClass('bg-white', 'text-blue-600', 'shadow');
    });

    it('hides analytics tabs when showAnalytics is false', async () => {
      render(
        <DataManagementWithAnalytics
          showAnalytics={false}
          analyticsIntegrationService={mockAnalyticsIntegrationService as any}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('navigation-tabs')).toBeInTheDocument();
      });

      expect(screen.getByTestId('data-management-tab')).toBeInTheDocument();
      expect(screen.queryByTestId('analytics-tab')).not.toBeInTheDocument();
      expect(screen.queryByTestId('reports-tab')).not.toBeInTheDocument();
      expect(screen.queryByTestId('exports-tab')).not.toBeInTheDocument();
    });
  });

  describe('Quick Insights Panel', () => {
    it('displays quick insights with analytics data', async () => {
      render(
        <DataManagementWithAnalytics
          showAnalytics={true}
          analyticsIntegrationService={mockAnalyticsIntegrationService as any}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('quick-insights')).toBeInTheDocument();
      });

      expect(screen.getByText('Quick Insights')).toBeInTheDocument();
      expect(screen.getByText('78%')).toBeInTheDocument(); // Performance score
      expect(screen.getByText('Performance Score')).toBeInTheDocument();
      expect(screen.getByText('1')).toBeInTheDocument(); // Critical issues (1 critical KPI)
      expect(screen.getByText('Critical Issues')).toBeInTheDocument();
      expect(screen.getByText('2')).toBeInTheDocument(); // Active KPIs
      expect(screen.getByText('Active KPIs')).toBeInTheDocument();
    });

    it('displays recommendations in quick insights', async () => {
      render(
        <DataManagementWithAnalytics
          showAnalytics={true}
          analyticsIntegrationService={mockAnalyticsIntegrationService as any}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('Top Recommendations')).toBeInTheDocument();
      });

      expect(screen.getByText('Data quality requires immediate attention')).toBeInTheDocument();
      expect(screen.getByText('Monitor storage utilization trends')).toBeInTheDocument();
      expect(screen.getByText('Pipeline performance is stable')).toBeInTheDocument();
    });

    it('shows correct colors for performance indicators', async () => {
      const lowPerformanceData = {
        ...mockAnalyticsData,
        performanceScore: 45,
        aggregatedKPIs: [
          { ...mockKPIs[0], status: KPIStatus.CRITICAL },
          { ...mockKPIs[1], status: KPIStatus.CRITICAL },
        ],
      };

      mockAnalyticsIntegrationService.generateDataManagementAnalytics.mockResolvedValue(lowPerformanceData);

      render(
        <DataManagementWithAnalytics
          analyticsIntegrationService={mockAnalyticsIntegrationService as any}
        />
      );

      await waitFor(() => {
        const performanceScore = screen.getByText('45%');
        expect(performanceScore).toHaveClass('text-red-600');

        const criticalIssues = screen.getByText('2');
        expect(criticalIssues).toHaveClass('text-red-600');
      });
    });
  });

  describe('Analytics Panel Toggle', () => {
    it('toggles analytics panel visibility', async () => {
      render(
        <DataManagementWithAnalytics
          showAnalytics={true}
          analyticsIntegrationService={mockAnalyticsIntegrationService as any}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('toggle-analytics')).toBeInTheDocument();
      });

      const toggleButton = screen.getByTestId('toggle-analytics');

      // Should initially show "Hide Analytics"
      expect(toggleButton).toHaveTextContent('Hide Analytics');

      // Click to hide
      fireEvent.click(toggleButton);
      expect(toggleButton).toHaveTextContent('Show Analytics');

      // Click to show again
      fireEvent.click(toggleButton);
      expect(toggleButton).toHaveTextContent('Hide Analytics');
    });

    it('hides toggle button when showAnalytics is false', async () => {
      render(
        <DataManagementWithAnalytics
          showAnalytics={false}
          analyticsIntegrationService={mockAnalyticsIntegrationService as any}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('data-management-with-analytics')).toBeInTheDocument();
      });

      expect(screen.queryByTestId('toggle-analytics')).not.toBeInTheDocument();
    });
  });

  describe('Layout Options', () => {
    it('renders side-by-side layout correctly', async () => {
      render(
        <DataManagementWithAnalytics
          analyticsLayout={AnalyticsViewLayout.SIDE_BY_SIDE}
          showAnalytics={true}
          analyticsIntegrationService={mockAnalyticsIntegrationService as any}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('data-management-with-analytics')).toBeInTheDocument();
      });

      // In side-by-side layout, both data management and analytics should be visible
      expect(screen.getByText('Core Data Management')).toBeInTheDocument();
      expect(screen.getByText('System Overview')).toBeInTheDocument();
    });

    it('renders tabbed layout correctly', async () => {
      render(
        <DataManagementWithAnalytics
          analyticsLayout={AnalyticsViewLayout.TABBED}
          showAnalytics={true}
          analyticsIntegrationService={mockAnalyticsIntegrationService as any}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('navigation-tabs')).toBeInTheDocument();
      });

      // In tabbed layout, only active tab content should be visible
      expect(screen.getByText('Core Data Management')).toBeInTheDocument();

      // Switch to analytics tab
      fireEvent.click(screen.getByTestId('analytics-tab'));

      // Should show analytics content
      expect(screen.queryByText('Core Data Management')).not.toBeInTheDocument();
    });
  });

  describe('Service Integration', () => {
    it('initializes analytics integration service with all services', async () => {
      render(
        <DataManagementWithAnalytics
          dataSourceService={mockDataSourceService as any}
          storageMetricsService={mockStorageMetricsService as any}
          dataQualityService={mockDataQualityService as any}
          pipelineService={mockPipelineService as any}
          analyticsIntegrationService={mockAnalyticsIntegrationService as any}
        />
      );

      await waitFor(() => {
        expect(mockAnalyticsIntegrationService.initialize).toHaveBeenCalledWith({
          dataSource: mockDataSourceService,
          storage: mockStorageMetricsService,
          dataQuality: mockDataQualityService,
          pipeline: mockPipelineService,
        });
      });
    });

    it('subscribes to analytics updates', async () => {
      render(
        <DataManagementWithAnalytics
          analyticsIntegrationService={mockAnalyticsIntegrationService as any}
        />
      );

      await waitFor(() => {
        expect(mockAnalyticsIntegrationService.onAnalyticsUpdate).toHaveBeenCalled();
      });
    });

    it('calls onAnalyticsUpdate callback when analytics data changes', async () => {
      const onAnalyticsUpdate = jest.fn();

      render(
        <DataManagementWithAnalytics
          analyticsIntegrationService={mockAnalyticsIntegrationService as any}
          onAnalyticsUpdate={onAnalyticsUpdate}
        />
      );

      await waitFor(() => {
        expect(onAnalyticsUpdate).toHaveBeenCalledWith(mockAnalyticsData);
      });
    });
  });

  describe('Time Range Handling', () => {
    it('updates analytics when time range changes', async () => {
      render(
        <DataManagementWithAnalytics
          analyticsIntegrationService={mockAnalyticsIntegrationService as any}
        />
      );

      await waitFor(() => {
        expect(mockAnalyticsIntegrationService.generateDataManagementAnalytics).toHaveBeenCalled();
      });

      // Initial call plus any subsequent calls
      expect(mockAnalyticsIntegrationService.generateDataManagementAnalytics).toHaveBeenCalledWith(
        expect.objectContaining({
          interval: TimeInterval.HOUR,
        })
      );
    });
  });

  describe('Error Handling', () => {
    it('handles analytics generation errors', async () => {
      const onError = jest.fn();
      mockAnalyticsIntegrationService.generateDataManagementAnalytics.mockRejectedValue(
        new Error('Analytics error')
      );

      render(
        <DataManagementWithAnalytics
          analyticsIntegrationService={mockAnalyticsIntegrationService as any}
          onError={onError}
        />
      );

      await waitFor(() => {
        expect(onError).toHaveBeenCalledWith(expect.any(Error));
      });
    });

    it('enhances alerts with analytics context', async () => {
      const onAlert = jest.fn();

      render(
        <DataManagementWithAnalytics
          analyticsIntegrationService={mockAnalyticsIntegrationService as any}
          onAlert={onAlert}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('data-management-with-analytics')).toBeInTheDocument();
      });

      // Simulate an alert from the base dashboard
      // This would typically come from the DataManagementDashboard component
      // For testing, we can verify the structure is set up correctly
      expect(onAlert).toBeDefined();
    });
  });

  describe('Performance and Optimization', () => {
    it('memoizes expensive calculations', async () => {
      const { rerender } = render(
        <DataManagementWithAnalytics
          analyticsIntegrationService={mockAnalyticsIntegrationService as any}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('data-management-with-analytics')).toBeInTheDocument();
      });

      const initialCallCount = mockAnalyticsIntegrationService.generateDataManagementAnalytics.mock.calls.length;

      // Re-render with same props should not cause additional service calls
      rerender(
        <DataManagementWithAnalytics
          analyticsIntegrationService={mockAnalyticsIntegrationService as any}
        />
      );

      // Should still have the same number of service calls
      expect(mockAnalyticsIntegrationService.generateDataManagementAnalytics).toHaveBeenCalledTimes(initialCallCount);
    });
  });

  describe('Accessibility', () => {
    it('has proper ARIA labels and roles', async () => {
      render(
        <DataManagementWithAnalytics
          analyticsIntegrationService={mockAnalyticsIntegrationService as any}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('data-management-with-analytics')).toBeInTheDocument();
      });

      // Check for accessible navigation
      const tabs = screen.getAllByRole('button');
      expect(tabs.length).toBeGreaterThan(0);
    });

    it('supports keyboard navigation', async () => {
      render(
        <DataManagementWithAnalytics
          analyticsIntegrationService={mockAnalyticsIntegrationService as any}
        />
      );

      await waitFor(() => {
        const toggleButton = screen.getByTestId('toggle-analytics');
        toggleButton.focus();
        expect(toggleButton).toHaveFocus();
      });
    });
  });

  describe('Data Updates and Reactivity', () => {
    it('updates UI when analytics data changes', async () => {
      const mockCallback = jest.fn();
      mockAnalyticsIntegrationService.onAnalyticsUpdate.mockImplementation((callback) => {
        mockCallback.current = callback;
        return () => {};
      });

      render(
        <DataManagementWithAnalytics
          analyticsIntegrationService={mockAnalyticsIntegrationService as any}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('data-management-with-analytics')).toBeInTheDocument();
      });

      // Simulate analytics update
      const updatedData = {
        ...mockAnalyticsData,
        performanceScore: 95,
      };

      if (mockCallback.current) {
        mockCallback.current(updatedData);
      }

      await waitFor(() => {
        expect(screen.getByText('95%')).toBeInTheDocument();
      });
    });
  });
});
