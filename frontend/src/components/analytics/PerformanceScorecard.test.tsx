/**
 * PerformanceScorecard Component Tests
 *
 * Comprehensive test suite for the PerformanceScorecard component
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { PerformanceScorecard, ScorecardLayout } from './PerformanceScorecard';
import {
  KPI,
  KPIStatus,
  TrendDirection,
  AnalyticsCategory,
  AnalyticsDataPoint,
  TimeInterval,
  ExportFormat,
} from '@/types/analytics';

// Mock services
const mockMetricsService = {
  getKPIs: jest.fn(),
  getPerformanceSummary: jest.fn(),
};

const mockAnalyticsService = {
  getHistoricalData: jest.fn(),
};

const mockExportService = {
  exportChart: jest.fn(),
};

// Mock data
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
  {
    id: 'kpi-3',
    name: 'Data Quality Score',
    description: 'Overall data quality percentage',
    category: AnalyticsCategory.DATA_QUALITY,
    metric: 'quality_score',
    target: 95,
    unit: '%',
    thresholds: {
      critical: { min: 80 },
      warning: { min: 90 },
      target: { min: 95, max: 100 },
    },
    status: KPIStatus.GOOD,
    currentValue: 92.5,
    trend: TrendDirection.DECREASING,
    lastUpdated: new Date('2024-01-15T10:02:00Z'),
  },
  {
    id: 'kpi-4',
    name: 'Error Rate',
    description: 'System error rate percentage',
    category: AnalyticsCategory.PERFORMANCE,
    metric: 'error_rate',
    target: 0.1,
    unit: '%',
    thresholds: {
      critical: { max: 5 },
      warning: { max: 1 },
      target: { min: 0, max: 0.5 },
    },
    status: KPIStatus.CRITICAL,
    currentValue: 2.5,
    trend: TrendDirection.VOLATILE,
    lastUpdated: new Date('2024-01-15T10:03:00Z'),
  },
];

const mockTrendData: AnalyticsDataPoint[] = [
  {
    timestamp: new Date('2024-01-15T09:00:00Z'),
    metrics: { uptime_percentage: 99.9 },
    dimensions: {},
  },
  {
    timestamp: new Date('2024-01-15T09:30:00Z'),
    metrics: { uptime_percentage: 99.95 },
    dimensions: {},
  },
  {
    timestamp: new Date('2024-01-15T10:00:00Z'),
    metrics: { uptime_percentage: 99.95 },
    dimensions: {},
  },
];

describe('PerformanceScorecard', () => {
  beforeEach(() => {
    jest.clearAllMocks();

    // Setup default mock responses
    mockMetricsService.getKPIs.mockImplementation((category) => {
      if (category) {
        return Promise.resolve(mockKPIs.filter(kpi => kpi.category === category));
      }
      return Promise.resolve(mockKPIs);
    });
    mockAnalyticsService.getHistoricalData.mockResolvedValue(mockTrendData);
    mockExportService.exportChart.mockResolvedValue({ id: 'export-job-1' });
  });

  describe('Component Rendering', () => {
    it('renders scorecard with loading state initially', () => {
      render(<PerformanceScorecard />);

      expect(screen.getByTestId('scorecard-loading')).toBeInTheDocument();
      expect(screen.getByText('Loading performance scorecard...')).toBeInTheDocument();
    });

    it('renders scorecard content after loading', async () => {
      render(
        <PerformanceScorecard
          metricsService={mockMetricsService as any}
          analyticsService={mockAnalyticsService as any}
          exportService={mockExportService as any}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('performance-scorecard')).toBeInTheDocument();
      });

      expect(screen.getByText('Performance Scorecard')).toBeInTheDocument();
      expect(screen.getByText('Real-time KPI monitoring and performance tracking')).toBeInTheDocument();
    });

    it('renders error state when data loading fails', async () => {
      mockMetricsService.getKPIs.mockRejectedValue(new Error('API Error'));

      render(
        <PerformanceScorecard
          metricsService={mockMetricsService as any}
          analyticsService={mockAnalyticsService as any}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('scorecard-error')).toBeInTheDocument();
      });

      expect(screen.getByText('Scorecard Error')).toBeInTheDocument();
      expect(screen.getByText('API Error')).toBeInTheDocument();
    });

    it('renders with custom layout and compact mode', async () => {
      render(
        <PerformanceScorecard
          layout={ScorecardLayout.COMPACT}
          compactMode={true}
          metricsService={mockMetricsService as any}
          analyticsService={mockAnalyticsService as any}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('performance-scorecard')).toBeInTheDocument();
      });
    });
  });

  describe('Performance Score Display', () => {
    it('displays overall performance score', async () => {
      render(
        <PerformanceScorecard
          showScores={true}
          metricsService={mockMetricsService as any}
          analyticsService={mockAnalyticsService as any}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('performance-overview')).toBeInTheDocument();
      });

      expect(screen.getByText('Overall Performance')).toBeInTheDocument();
      expect(screen.getByText('Score out of 100')).toBeInTheDocument();
    });

    it('calculates correct performance score', async () => {
      render(
        <PerformanceScorecard
          showScores={true}
          metricsService={mockMetricsService as any}
          analyticsService={mockAnalyticsService as any}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('performance-overview')).toBeInTheDocument();
      });

      // Score should be calculated based on KPI statuses
      // Excellent=100, Good=80, Warning=60, Critical=30
      // (100 + 60 + 80 + 30) / 4 = 67.5, rounded to 68
      expect(screen.getByText('68')).toBeInTheDocument();
    });

    it('displays category performance chart', async () => {
      render(
        <PerformanceScorecard
          showScores={true}
          metricsService={mockMetricsService as any}
          analyticsService={mockAnalyticsService as any}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('Category Performance')).toBeInTheDocument();
      });
    });

    it('shows trend icons correctly', async () => {
      render(
        <PerformanceScorecard
          showScores={true}
          metricsService={mockMetricsService as any}
          analyticsService={mockAnalyticsService as any}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('performance-overview')).toBeInTheDocument();
      });

      // Should show trend icon based on overall trend calculation
      expect(screen.getByText('📉')).toBeInTheDocument(); // Decreasing trend icon
    });
  });

  describe('KPI Cards Display', () => {
    it('displays all KPI cards with correct data', async () => {
      render(
        <PerformanceScorecard
          metricsService={mockMetricsService as any}
          analyticsService={mockAnalyticsService as any}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('kpi-cards')).toBeInTheDocument();
      });

      expect(screen.getByTestId('kpi-card-kpi-1')).toBeInTheDocument();
      expect(screen.getByTestId('kpi-card-kpi-2')).toBeInTheDocument();
      expect(screen.getByTestId('kpi-card-kpi-3')).toBeInTheDocument();
      expect(screen.getByTestId('kpi-card-kpi-4')).toBeInTheDocument();

      expect(screen.getByText('System Availability')).toBeInTheDocument();
      expect(screen.getByText('Response Time')).toBeInTheDocument();
      expect(screen.getByText('Data Quality Score')).toBeInTheDocument();
      expect(screen.getByText('Error Rate')).toBeInTheDocument();
    });

    it('displays KPI status with correct colors', async () => {
      render(
        <PerformanceScorecard
          metricsService={mockMetricsService as any}
          analyticsService={mockAnalyticsService as any}
        />
      );

      await waitFor(() => {
        const excellentStatus = screen.getByText('excellent');
        const warningStatus = screen.getByText('warning');
        const goodStatus = screen.getByText('good');
        const criticalStatus = screen.getByText('critical');

        expect(excellentStatus).toHaveClass('text-green-600', 'bg-green-100');
        expect(warningStatus).toHaveClass('text-yellow-600', 'bg-yellow-100');
        expect(goodStatus).toHaveClass('text-blue-600', 'bg-blue-100');
        expect(criticalStatus).toHaveClass('text-red-600', 'bg-red-100');
      });
    });

    it('displays KPI values and targets correctly', async () => {
      render(
        <PerformanceScorecard
          metricsService={mockMetricsService as any}
          analyticsService={mockAnalyticsService as any}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('99.9')).toBeInTheDocument(); // System availability value
        expect(screen.getByText('350.0')).toBeInTheDocument(); // Response time value
        expect(screen.getByText('92.5')).toBeInTheDocument(); // Data quality value
        expect(screen.getByText('2.5')).toBeInTheDocument(); // Error rate value
      });
    });

    it('shows trend charts when enabled', async () => {
      render(
        <PerformanceScorecard
          showTrends={true}
          metricsService={mockMetricsService as any}
          analyticsService={mockAnalyticsService as any}
        />
      );

      await waitFor(() => {
        expect(mockAnalyticsService.getHistoricalData).toHaveBeenCalled();
      });
    });

    it('handles KPI click events', async () => {
      const onKPIClick = jest.fn();

      render(
        <PerformanceScorecard
          metricsService={mockMetricsService as any}
          analyticsService={mockAnalyticsService as any}
          onKPIClick={onKPIClick}
        />
      );

      await waitFor(() => {
        const kpiCard = screen.getByTestId('kpi-card-kpi-1');
        fireEvent.click(kpiCard);
      });

      expect(onKPIClick).toHaveBeenCalledWith(mockKPIs[0]);
    });
  });

  describe('Category Filtering', () => {
    it('filters KPIs by selected category', async () => {
      render(
        <PerformanceScorecard
          metricsService={mockMetricsService as any}
          analyticsService={mockAnalyticsService as any}
        />
      );

      await waitFor(() => {
        const categoryFilter = screen.getByTestId('category-filter');
        fireEvent.change(categoryFilter, { target: { value: AnalyticsCategory.PERFORMANCE } });
      });

      // Should only show performance KPIs
      await waitFor(() => {
        expect(screen.getByText('Response Time')).toBeInTheDocument();
        expect(screen.getByText('Error Rate')).toBeInTheDocument();
        expect(screen.queryByText('System Availability')).not.toBeInTheDocument();
      });
    });

    it('handles category click events', async () => {
      const onCategoryClick = jest.fn();

      render(
        <PerformanceScorecard
          metricsService={mockMetricsService as any}
          analyticsService={mockAnalyticsService as any}
          onCategoryClick={onCategoryClick}
        />
      );

      await waitFor(() => {
        const categoryFilter = screen.getByTestId('category-filter');
        fireEvent.change(categoryFilter, { target: { value: AnalyticsCategory.SYSTEM } });
      });

      expect(onCategoryClick).toHaveBeenCalledWith(AnalyticsCategory.SYSTEM);
    });

    it('shows all categories when filter is cleared', async () => {
      render(
        <PerformanceScorecard
          metricsService={mockMetricsService as any}
          analyticsService={mockAnalyticsService as any}
        />
      );

      await waitFor(() => {
        const categoryFilter = screen.getByTestId('category-filter');
        fireEvent.change(categoryFilter, { target: { value: AnalyticsCategory.PERFORMANCE } });
      });

      await waitFor(() => {
        fireEvent.change(categoryFilter, { target: { value: '' } });
      });

      // Should show all KPIs again
      await waitFor(() => {
        expect(screen.getByText('System Availability')).toBeInTheDocument();
        expect(screen.getByText('Response Time')).toBeInTheDocument();
        expect(screen.getByText('Data Quality Score')).toBeInTheDocument();
        expect(screen.getByText('Error Rate')).toBeInTheDocument();
      });
    });
  });

  describe('Layout Options', () => {
    it('renders grid layout correctly', async () => {
      render(
        <PerformanceScorecard
          layout={ScorecardLayout.GRID}
          metricsService={mockMetricsService as any}
          analyticsService={mockAnalyticsService as any}
        />
      );

      await waitFor(() => {
        const kpiCards = screen.getByTestId('kpi-cards');
        expect(kpiCards).toHaveClass('grid-cols-1', 'md:grid-cols-2', 'lg:grid-cols-3', 'xl:grid-cols-4');
      });
    });

    it('renders compact layout correctly', async () => {
      render(
        <PerformanceScorecard
          layout={ScorecardLayout.COMPACT}
          metricsService={mockMetricsService as any}
          analyticsService={mockAnalyticsService as any}
        />
      );

      await waitFor(() => {
        const kpiCards = screen.getByTestId('kpi-cards');
        expect(kpiCards).toHaveClass('grid-cols-1', 'md:grid-cols-2');
      });
    });

    it('renders list layout correctly', async () => {
      render(
        <PerformanceScorecard
          layout={ScorecardLayout.LIST}
          metricsService={mockMetricsService as any}
          analyticsService={mockAnalyticsService as any}
        />
      );

      await waitFor(() => {
        const kpiCards = screen.getByTestId('kpi-cards');
        expect(kpiCards).toHaveClass('grid-cols-1');
      });
    });
  });

  describe('Export Functionality', () => {
    it('handles export selection', async () => {
      const onExport = jest.fn();

      render(
        <PerformanceScorecard
          metricsService={mockMetricsService as any}
          analyticsService={mockAnalyticsService as any}
          exportService={mockExportService as any}
          onExport={onExport}
        />
      );

      await waitFor(() => {
        const exportSelect = screen.getByTestId('export-select');
        fireEvent.change(exportSelect, { target: { value: ExportFormat.PNG } });
      });

      expect(mockExportService.exportChart).toHaveBeenCalled();
      expect(onExport).toHaveBeenCalledWith('export-job-1');
    });

    it('handles export errors gracefully', async () => {
      const onError = jest.fn();
      mockExportService.exportChart.mockRejectedValue(new Error('Export failed'));

      render(
        <PerformanceScorecard
          metricsService={mockMetricsService as any}
          analyticsService={mockAnalyticsService as any}
          exportService={mockExportService as any}
          onError={onError}
        />
      );

      await waitFor(() => {
        const exportSelect = screen.getByTestId('export-select');
        fireEvent.change(exportSelect, { target: { value: ExportFormat.PNG } });
      });

      await waitFor(() => {
        expect(onError).toHaveBeenCalledWith(expect.any(Error));
      });
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
        <PerformanceScorecard
          autoRefresh={true}
          refreshInterval={5000}
          metricsService={mockMetricsService as any}
          analyticsService={mockAnalyticsService as any}
        />
      );

      // Wait for initial load
      await waitFor(() => {
        expect(mockMetricsService.getKPIs).toHaveBeenCalledTimes(4); // Called for each category
      });

      // Fast-forward time to trigger refresh
      jest.advanceTimersByTime(5000);

      await waitFor(() => {
        expect(mockMetricsService.getKPIs).toHaveBeenCalledTimes(8); // Called again for each category
      });
    });

    it('does not auto-refresh when disabled', async () => {
      render(
        <PerformanceScorecard
          autoRefresh={false}
          metricsService={mockMetricsService as any}
          analyticsService={mockAnalyticsService as any}
        />
      );

      // Wait for initial load
      await waitFor(() => {
        expect(mockMetricsService.getKPIs).toHaveBeenCalledTimes(4);
      });

      // Fast-forward time
      jest.advanceTimersByTime(30000);

      // Should not have triggered additional calls
      expect(mockMetricsService.getKPIs).toHaveBeenCalledTimes(4);
    });

    it('shows refreshing indicator during refresh', async () => {
      render(
        <PerformanceScorecard
          metricsService={mockMetricsService as any}
          analyticsService={mockAnalyticsService as any}
        />
      );

      await waitFor(() => {
        const refreshButton = screen.getByTestId('refresh-button');
        fireEvent.click(refreshButton);
      });

      expect(screen.getByText('Refreshing...')).toBeInTheDocument();
    });
  });

  describe('Empty States', () => {
    it('shows no KPIs message when no data available', async () => {
      mockMetricsService.getKPIs.mockResolvedValue([]);

      render(
        <PerformanceScorecard
          metricsService={mockMetricsService as any}
          analyticsService={mockAnalyticsService as any}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('no-kpis-message')).toBeInTheDocument();
      });

      expect(screen.getByText('No KPIs Available')).toBeInTheDocument();
      expect(screen.getByText('No performance indicators configured')).toBeInTheDocument();
    });

    it('shows category-specific empty message', async () => {
      mockMetricsService.getKPIs.mockImplementation((category) => {
        if (category === AnalyticsCategory.CUSTOM) {
          return Promise.resolve([]);
        }
        return Promise.resolve(mockKPIs.filter(kpi => kpi.category === category));
      });

      render(
        <PerformanceScorecard
          metricsService={mockMetricsService as any}
          analyticsService={mockAnalyticsService as any}
        />
      );

      await waitFor(() => {
        const categoryFilter = screen.getByTestId('category-filter');
        fireEvent.change(categoryFilter, { target: { value: AnalyticsCategory.CUSTOM } });
      });

      await waitFor(() => {
        expect(screen.getByText('No KPIs found for custom category')).toBeInTheDocument();
        expect(screen.getByText('Show All Categories')).toBeInTheDocument();
      });
    });
  });

  describe('Error Handling', () => {
    it('handles service errors gracefully', async () => {
      const onError = jest.fn();
      mockMetricsService.getKPIs.mockRejectedValue(new Error('Service unavailable'));

      render(
        <PerformanceScorecard
          metricsService={mockMetricsService as any}
          analyticsService={mockAnalyticsService as any}
          onError={onError}
        />
      );

      await waitFor(() => {
        expect(onError).toHaveBeenCalledWith(expect.any(Error));
      });
    });

    it('retries data loading on error state retry button click', async () => {
      mockMetricsService.getKPIs.mockRejectedValueOnce(new Error('Network error'));
      mockMetricsService.getKPIs.mockResolvedValue(mockKPIs);

      render(
        <PerformanceScorecard
          metricsService={mockMetricsService as any}
          analyticsService={mockAnalyticsService as any}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('scorecard-error')).toBeInTheDocument();
      });

      const retryButton = screen.getByRole('button', { name: /retry/i });
      fireEvent.click(retryButton);

      await waitFor(() => {
        expect(screen.getByTestId('performance-scorecard')).toBeInTheDocument();
      });
    });
  });

  describe('Accessibility', () => {
    it('has proper ARIA labels and structure', async () => {
      render(
        <PerformanceScorecard
          metricsService={mockMetricsService as any}
          analyticsService={mockAnalyticsService as any}
        />
      );

      await waitFor(() => {
        // Check for proper button accessibility
        const refreshButton = screen.getByRole('button', { name: /refresh/i });
        expect(refreshButton).toBeInTheDocument();
      });
    });

    it('supports keyboard navigation', async () => {
      render(
        <PerformanceScorecard
          metricsService={mockMetricsService as any}
          analyticsService={mockAnalyticsService as any}
        />
      );

      await waitFor(() => {
        const refreshButton = screen.getByTestId('refresh-button');
        refreshButton.focus();
        expect(refreshButton).toHaveFocus();
      });
    });
  });

  describe('Performance Optimization', () => {
    it('memoizes expensive calculations', async () => {
      const { rerender } = render(
        <PerformanceScorecard
          metricsService={mockMetricsService as any}
          analyticsService={mockAnalyticsService as any}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('performance-scorecard')).toBeInTheDocument();
      });

      const initialCallCount = mockMetricsService.getKPIs.mock.calls.length;

      // Re-render with same props should not cause additional service calls
      rerender(
        <PerformanceScorecard
          metricsService={mockMetricsService as any}
          analyticsService={mockAnalyticsService as any}
        />
      );

      // Should still have the same number of service calls
      expect(mockMetricsService.getKPIs).toHaveBeenCalledTimes(initialCallCount);
    });
  });

  describe('Score Change Callbacks', () => {
    it('calls onScoreChange when performance score updates', async () => {
      const onScoreChange = jest.fn();

      render(
        <PerformanceScorecard
          metricsService={mockMetricsService as any}
          analyticsService={mockAnalyticsService as any}
          onScoreChange={onScoreChange}
        />
      );

      await waitFor(() => {
        expect(onScoreChange).toHaveBeenCalledWith(expect.objectContaining({
          overall: expect.any(Number),
          categoryScores: expect.any(Object),
          trend: expect.any(String),
          lastUpdated: expect.any(Date),
        }));
      });
    });
  });
});
