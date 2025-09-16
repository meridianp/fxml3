/**
 * AnalyticsDashboard Component Tests
 *
 * Comprehensive test suite for the AnalyticsDashboard component
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AnalyticsDashboard, DashboardLayout, DashboardTheme } from './AnalyticsDashboard';
import {
  AnalyticsCategory,
  AnalyticsMetric,
  KPI,
  KPIStatus,
  TrendDirection,
  TimeInterval,
  ExportFormat,
} from '@/types/analytics';

// Mock services
const mockAnalyticsService = {
  getMetrics: jest.fn(),
  analyzeTrend: jest.fn(),
  aggregate: jest.fn(),
  getStatisticalSummary: jest.fn(),
};

const mockMetricsService = {
  getPerformanceSummary: jest.fn(),
  getKPIs: jest.fn(),
  evaluateKPIThresholds: jest.fn(),
};

const mockExportService = {
  exportChart: jest.fn(),
  exportData: jest.fn(),
  getExportJobs: jest.fn(),
};

// Mock data
const mockMetrics: AnalyticsMetric[] = [
  {
    id: 'metric-1',
    name: 'CPU Usage',
    description: 'System CPU utilization',
    category: AnalyticsCategory.PERFORMANCE,
    value: 75.5,
    unit: '%',
    timestamp: new Date('2024-01-15T10:00:00Z'),
    tags: ['system', 'performance'],
  },
  {
    id: 'metric-2',
    name: 'Memory Usage',
    description: 'System memory utilization',
    category: AnalyticsCategory.PERFORMANCE,
    value: 68.2,
    unit: '%',
    timestamp: new Date('2024-01-15T10:01:00Z'),
    tags: ['system', 'memory'],
  },
  {
    id: 'metric-3',
    name: 'Data Quality Score',
    description: 'Overall data quality percentage',
    category: AnalyticsCategory.DATA_QUALITY,
    value: 92.1,
    unit: '%',
    timestamp: new Date('2024-01-15T10:02:00Z'),
    tags: ['data', 'quality'],
  },
];

const mockKPIs: KPI[] = [
  {
    id: 'kpi-1',
    name: 'System Availability',
    description: 'Overall system uptime',
    category: AnalyticsCategory.SYSTEM,
    metric: 'uptime_percentage',
    target: 99.9,
    unit: '%',
    thresholds: {
      critical: { min: 95 },
      warning: { min: 98 },
      target: { min: 99.5, max: 100 },
    },
    status: KPIStatus.EXCELLENT,
    currentValue: 99.95,
    trend: TrendDirection.STABLE,
    lastUpdated: new Date('2024-01-15T10:00:00Z'),
  },
  {
    id: 'kpi-2',
    name: 'Response Time',
    description: 'Average API response time',
    category: AnalyticsCategory.PERFORMANCE,
    metric: 'avg_response_time',
    target: 200,
    unit: 'ms',
    thresholds: {
      critical: { max: 1000 },
      warning: { max: 500 },
      target: { min: 0, max: 200 },
    },
    status: KPIStatus.WARNING,
    currentValue: 350,
    trend: TrendDirection.INCREASING,
    lastUpdated: new Date('2024-01-15T10:01:00Z'),
  },
];

const mockPerformanceSummary = {
  kpis: mockKPIs,
  summary: {
    total: 10,
    excellent: 6,
    good: 2,
    warning: 1,
    critical: 1,
  },
};

const mockTrendAnalysis = {
  metric: 'CPU Usage',
  timeRange: {
    start: new Date('2024-01-14T10:00:00Z'),
    end: new Date('2024-01-15T10:00:00Z'),
    interval: TimeInterval.HOUR,
  },
  trend: TrendDirection.INCREASING,
  confidence: 0.85,
  slope: 0.5,
  correlation: 0.75,
  forecast: [
    {
      timestamp: new Date('2024-01-15T11:00:00Z'),
      value: 76.0,
      confidence: 0.9,
      upperBound: 80.0,
      lowerBound: 72.0,
    },
    {
      timestamp: new Date('2024-01-15T12:00:00Z'),
      value: 76.5,
      confidence: 0.85,
      upperBound: 81.0,
      lowerBound: 72.0,
    },
  ],
};

describe('AnalyticsDashboard', () => {
  beforeEach(() => {
    jest.clearAllMocks();

    // Setup default mock responses
    mockAnalyticsService.getMetrics.mockResolvedValue(mockMetrics);
    mockAnalyticsService.analyzeTrend.mockResolvedValue(mockTrendAnalysis);
    mockMetricsService.getPerformanceSummary.mockResolvedValue(mockPerformanceSummary);
    mockExportService.exportChart.mockResolvedValue({ id: 'export-job-1' });
    mockExportService.exportData.mockResolvedValue({ id: 'export-job-2' });
  });

  describe('Component Rendering', () => {
    it('renders dashboard with loading state initially', () => {
      render(<AnalyticsDashboard />);

      expect(screen.getByTestId('analytics-dashboard-loading')).toBeInTheDocument();
      expect(screen.getByText('Loading analytics dashboard...')).toBeInTheDocument();
    });

    it('renders dashboard content after loading', async () => {
      render(
        <AnalyticsDashboard
          analyticsService={mockAnalyticsService as any}
          metricsService={mockMetricsService as any}
          exportService={mockExportService as any}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('analytics-dashboard')).toBeInTheDocument();
      });

      expect(screen.getByText('Analytics Dashboard')).toBeInTheDocument();
      expect(screen.getByText('Real-time performance analytics and KPI monitoring')).toBeInTheDocument();
    });

    it('renders error state when data loading fails', async () => {
      mockAnalyticsService.getMetrics.mockRejectedValue(new Error('API Error'));

      render(
        <AnalyticsDashboard
          analyticsService={mockAnalyticsService as any}
          metricsService={mockMetricsService as any}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('analytics-dashboard-error')).toBeInTheDocument();
      });

      expect(screen.getByText('Dashboard Error')).toBeInTheDocument();
      expect(screen.getByText('API Error')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
    });

    it('renders with custom className and layout', async () => {
      render(
        <AnalyticsDashboard
          className="custom-dashboard"
          layout={DashboardLayout.DETAILED}
          analyticsService={mockAnalyticsService as any}
          metricsService={mockMetricsService as any}
        />
      );

      await waitFor(() => {
        const dashboard = screen.getByTestId('analytics-dashboard');
        expect(dashboard).toHaveClass('custom-dashboard');
      });
    });
  });

  describe('KPI Summary Display', () => {
    it('displays KPI summary cards with correct values', async () => {
      render(
        <AnalyticsDashboard
          analyticsService={mockAnalyticsService as any}
          metricsService={mockMetricsService as any}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('kpi-summary')).toBeInTheDocument();
      });

      // Check summary values
      expect(screen.getByText('10')).toBeInTheDocument(); // Total
      expect(screen.getByText('6')).toBeInTheDocument(); // Excellent
      expect(screen.getByText('1')).toBeInTheDocument(); // Warning
      expect(screen.getByText('1')).toBeInTheDocument(); // Critical
    });

    it('displays individual KPIs in the KPI list', async () => {
      render(
        <AnalyticsDashboard
          analyticsService={mockAnalyticsService as any}
          metricsService={mockMetricsService as any}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('kpi-list')).toBeInTheDocument();
      });

      expect(screen.getByText('System Availability')).toBeInTheDocument();
      expect(screen.getByText('Response Time')).toBeInTheDocument();
      expect(screen.getByText('99.95 %')).toBeInTheDocument();
      expect(screen.getByText('350.00 ms')).toBeInTheDocument();
    });

    it('shows correct KPI status colors', async () => {
      render(
        <AnalyticsDashboard
          analyticsService={mockAnalyticsService as any}
          metricsService={mockMetricsService as any}
        />
      );

      await waitFor(() => {
        const excellentStatus = screen.getByText('excellent');
        const warningStatus = screen.getByText('warning');

        expect(excellentStatus).toHaveClass('text-green-600', 'bg-green-100');
        expect(warningStatus).toHaveClass('text-yellow-600', 'bg-yellow-100');
      });
    });
  });

  describe('Charts and Visualizations', () => {
    it('displays metrics overview chart', async () => {
      render(
        <AnalyticsDashboard
          analyticsService={mockAnalyticsService as any}
          metricsService={mockMetricsService as any}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('metrics-chart')).toBeInTheDocument();
      });

      expect(screen.getByText('Metrics Overview')).toBeInTheDocument();
      expect(screen.getByTestId('export-chart-button')).toBeInTheDocument();
    });

    it('displays trend analysis section', async () => {
      render(
        <AnalyticsDashboard
          analyticsService={mockAnalyticsService as any}
          metricsService={mockMetricsService as any}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('trend-analysis')).toBeInTheDocument();
      });

      expect(screen.getByText('Trend Analysis')).toBeInTheDocument();

      await waitFor(() => {
        expect(screen.getByTestId('trend-CPU Usage')).toBeInTheDocument();
      });
    });

    it('displays category distribution chart', async () => {
      render(
        <AnalyticsDashboard
          analyticsService={mockAnalyticsService as any}
          metricsService={mockMetricsService as any}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('category-distribution')).toBeInTheDocument();
      });

      expect(screen.getByText('Category Distribution')).toBeInTheDocument();
    });

    it('shows empty state when no metrics available', async () => {
      mockAnalyticsService.getMetrics.mockResolvedValue([]);
      mockMetricsService.getPerformanceSummary.mockResolvedValue({
        kpis: [],
        summary: { total: 0, excellent: 0, good: 0, warning: 0, critical: 0 },
      });

      render(
        <AnalyticsDashboard
          analyticsService={mockAnalyticsService as any}
          metricsService={mockMetricsService as any}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('No metrics available')).toBeInTheDocument();
      });
    });
  });

  describe('Data Table', () => {
    it('displays metrics table with correct data', async () => {
      render(
        <AnalyticsDashboard
          analyticsService={mockAnalyticsService as any}
          metricsService={mockMetricsService as any}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('metrics-table')).toBeInTheDocument();
      });

      expect(screen.getByText('Recent Metrics')).toBeInTheDocument();
      expect(screen.getByText('CPU Usage')).toBeInTheDocument();
      expect(screen.getByText('Memory Usage')).toBeInTheDocument();
      expect(screen.getByText('Data Quality Score')).toBeInTheDocument();
    });

    it('handles metric row clicks', async () => {
      const onMetricClick = jest.fn();

      render(
        <AnalyticsDashboard
          analyticsService={mockAnalyticsService as any}
          metricsService={mockMetricsService as any}
          onMetricClick={onMetricClick}
        />
      );

      await waitFor(() => {
        const metricRow = screen.getByTestId('metric-row-metric-1');
        fireEvent.click(metricRow);
      });

      expect(onMetricClick).toHaveBeenCalledWith(mockMetrics[0]);
    });

    it('handles KPI clicks', async () => {
      const onKPIClick = jest.fn();

      render(
        <AnalyticsDashboard
          analyticsService={mockAnalyticsService as any}
          metricsService={mockMetricsService as any}
          onKPIClick={onKPIClick}
        />
      );

      await waitFor(() => {
        const kpiItem = screen.getByTestId('kpi-item-kpi-1');
        fireEvent.click(kpiItem);
      });

      expect(onKPIClick).toHaveBeenCalledWith(mockKPIs[0]);
    });
  });

  describe('Filtering and Controls', () => {
    it('handles category filter changes', async () => {
      render(
        <AnalyticsDashboard
          analyticsService={mockAnalyticsService as any}
          metricsService={mockMetricsService as any}
        />
      );

      await waitFor(() => {
        const categoryFilter = screen.getByTestId('category-filter');
        fireEvent.change(categoryFilter, { target: { value: AnalyticsCategory.PERFORMANCE } });
      });

      // Should call services with the new category filter
      await waitFor(() => {
        expect(mockAnalyticsService.getMetrics).toHaveBeenCalledWith(AnalyticsCategory.PERFORMANCE);
      });
    });

    it('handles refresh button click', async () => {
      render(
        <AnalyticsDashboard
          analyticsService={mockAnalyticsService as any}
          metricsService={mockMetricsService as any}
        />
      );

      await waitFor(() => {
        const refreshButton = screen.getByTestId('refresh-button');
        fireEvent.click(refreshButton);
      });

      expect(screen.getByText('Refreshing...')).toBeInTheDocument();
    });

    it('displays refreshing indicator during auto-refresh', async () => {
      render(
        <AnalyticsDashboard
          analyticsService={mockAnalyticsService as any}
          metricsService={mockMetricsService as any}
          autoRefresh={true}
          refreshInterval={1000}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('analytics-dashboard')).toBeInTheDocument();
      });

      // Simulate refreshing state
      const refreshButton = screen.getByTestId('refresh-button');
      fireEvent.click(refreshButton);

      expect(screen.getByText('Refreshing...')).toBeInTheDocument();
    });
  });

  describe('Export Functionality', () => {
    it('handles chart export', async () => {
      const onExportComplete = jest.fn();

      render(
        <AnalyticsDashboard
          analyticsService={mockAnalyticsService as any}
          metricsService={mockMetricsService as any}
          exportService={mockExportService as any}
          onExportComplete={onExportComplete}
        />
      );

      await waitFor(() => {
        const exportButton = screen.getByTestId('export-chart-button');
        fireEvent.click(exportButton);
      });

      expect(mockExportService.exportChart).toHaveBeenCalled();
      expect(onExportComplete).toHaveBeenCalledWith('export-job-1');
    });

    it('handles data export from dropdown', async () => {
      const onExportComplete = jest.fn();

      render(
        <AnalyticsDashboard
          analyticsService={mockAnalyticsService as any}
          metricsService={mockMetricsService as any}
          exportService={mockExportService as any}
          onExportComplete={onExportComplete}
        />
      );

      await waitFor(() => {
        const exportSelect = screen.getByTestId('export-select');
        fireEvent.change(exportSelect, { target: { value: ExportFormat.CSV } });
      });

      expect(mockExportService.exportData).toHaveBeenCalled();
      expect(onExportComplete).toHaveBeenCalledWith('export-job-2');
    });

    it('handles individual metric export', async () => {
      render(
        <AnalyticsDashboard
          analyticsService={mockAnalyticsService as any}
          metricsService={mockMetricsService as any}
          exportService={mockExportService as any}
        />
      );

      await waitFor(() => {
        const table = screen.getByTestId('metrics-table');
        const exportButton = within(table).getAllByText('Export')[0];
        fireEvent.click(exportButton);
      });

      expect(mockExportService.exportData).toHaveBeenCalledWith(
        ['CPU Usage'],
        ExportFormat.CSV
      );
    });
  });

  describe('Error Handling', () => {
    it('handles service errors gracefully', async () => {
      const onError = jest.fn();
      mockAnalyticsService.getMetrics.mockRejectedValue(new Error('Service unavailable'));

      render(
        <AnalyticsDashboard
          analyticsService={mockAnalyticsService as any}
          metricsService={mockMetricsService as any}
          onError={onError}
        />
      );

      await waitFor(() => {
        expect(onError).toHaveBeenCalledWith(expect.any(Error));
      });
    });

    it('handles export errors', async () => {
      const onError = jest.fn();
      mockExportService.exportChart.mockRejectedValue(new Error('Export failed'));

      render(
        <AnalyticsDashboard
          analyticsService={mockAnalyticsService as any}
          metricsService={mockMetricsService as any}
          exportService={mockExportService as any}
          onError={onError}
        />
      );

      await waitFor(() => {
        const exportButton = screen.getByTestId('export-chart-button');
        fireEvent.click(exportButton);
      });

      await waitFor(() => {
        expect(onError).toHaveBeenCalledWith(expect.any(Error));
      });
    });

    it('retries data loading on error state retry button click', async () => {
      mockAnalyticsService.getMetrics.mockRejectedValueOnce(new Error('Network error'));
      mockAnalyticsService.getMetrics.mockResolvedValueOnce(mockMetrics);

      render(
        <AnalyticsDashboard
          analyticsService={mockAnalyticsService as any}
          metricsService={mockMetricsService as any}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('analytics-dashboard-error')).toBeInTheDocument();
      });

      const retryButton = screen.getByRole('button', { name: /retry/i });
      fireEvent.click(retryButton);

      await waitFor(() => {
        expect(screen.getByTestId('analytics-dashboard')).toBeInTheDocument();
      });
    });
  });

  describe('Accessibility', () => {
    it('has proper ARIA labels and roles', async () => {
      render(
        <AnalyticsDashboard
          analyticsService={mockAnalyticsService as any}
          metricsService={mockMetricsService as any}
        />
      );

      await waitFor(() => {
        // Check for table structure
        const table = screen.getByRole('table');
        expect(table).toBeInTheDocument();

        // Check for button accessibility
        const refreshButton = screen.getByRole('button', { name: /refresh/i });
        expect(refreshButton).toBeInTheDocument();
      });
    });

    it('supports keyboard navigation', async () => {
      const user = userEvent.setup();

      render(
        <AnalyticsDashboard
          analyticsService={mockAnalyticsService as any}
          metricsService={mockMetricsService as any}
        />
      );

      await waitFor(() => {
        const refreshButton = screen.getByTestId('refresh-button');
        refreshButton.focus();
        expect(refreshButton).toHaveFocus();
      });
    });
  });

  describe('Responsive Design', () => {
    it('adapts layout for different screen sizes', async () => {
      render(
        <AnalyticsDashboard
          analyticsService={mockAnalyticsService as any}
          metricsService={mockMetricsService as any}
          layout={DashboardLayout.COMPACT}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('analytics-dashboard')).toBeInTheDocument();
      });

      // Dashboard should render with responsive classes
      const dashboard = screen.getByTestId('analytics-dashboard');
      expect(dashboard).toHaveClass('space-y-6');
    });
  });

  describe('Auto-refresh Functionality', () => {
    beforeEach(() => {
      jest.useFakeTimers();
    });

    afterEach(() => {
      jest.useRealTimers();
    });

    it('auto-refreshes data at specified intervals', async () => {
      render(
        <AnalyticsDashboard
          analyticsService={mockAnalyticsService as any}
          metricsService={mockMetricsService as any}
          autoRefresh={true}
          refreshInterval={5000}
        />
      );

      // Wait for initial load
      await waitFor(() => {
        expect(mockAnalyticsService.getMetrics).toHaveBeenCalledTimes(1);
      });

      // Fast-forward time to trigger refresh
      jest.advanceTimersByTime(5000);

      await waitFor(() => {
        expect(mockAnalyticsService.getMetrics).toHaveBeenCalledTimes(2);
      });
    });

    it('does not auto-refresh when disabled', async () => {
      render(
        <AnalyticsDashboard
          analyticsService={mockAnalyticsService as any}
          metricsService={mockMetricsService as any}
          autoRefresh={false}
        />
      );

      // Wait for initial load
      await waitFor(() => {
        expect(mockAnalyticsService.getMetrics).toHaveBeenCalledTimes(1);
      });

      // Fast-forward time
      jest.advanceTimersByTime(30000);

      // Should not have triggered additional calls
      expect(mockAnalyticsService.getMetrics).toHaveBeenCalledTimes(1);
    });
  });

  describe('Performance Optimization', () => {
    it('memoizes expensive computations', async () => {
      const { rerender } = render(
        <AnalyticsDashboard
          analyticsService={mockAnalyticsService as any}
          metricsService={mockMetricsService as any}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('analytics-dashboard')).toBeInTheDocument();
      });

      // Re-render with same props should not cause additional service calls
      rerender(
        <AnalyticsDashboard
          analyticsService={mockAnalyticsService as any}
          metricsService={mockMetricsService as any}
        />
      );

      // Should still only have initial service calls
      expect(mockAnalyticsService.getMetrics).toHaveBeenCalledTimes(1);
    });
  });
});
