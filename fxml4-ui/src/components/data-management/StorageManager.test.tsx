/**
 * StorageManager Component Tests
 *
 * Tests for storage metrics monitoring with interactive charts and dashboard integration
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { StorageManager } from './StorageManager';
import { StorageMetricsService } from '@/services/storageMetrics';
import { NotificationService } from '@/services/notification';
import { StorageMetrics, SlowQuery, RetentionPolicy } from '@/types/dataManagement';

// Mock services
jest.mock('@/services/storageMetrics');
jest.mock('@/services/notification');
jest.mock('recharts', () => ({
  LineChart: ({ children }: any) => <div data-testid="line-chart">{children}</div>,
  Line: ({ dataKey }: any) => <div data-testid={`line-${dataKey}`} />,
  XAxis: () => <div data-testid="x-axis" />,
  YAxis: () => <div data-testid="y-axis" />,
  CartesianGrid: () => <div data-testid="cartesian-grid" />,
  Tooltip: () => <div data-testid="tooltip" />,
  Legend: () => <div data-testid="legend" />,
  ResponsiveContainer: ({ children }: any) => <div data-testid="responsive-container">{children}</div>,
  AreaChart: ({ children }: any) => <div data-testid="area-chart">{children}</div>,
  Area: ({ dataKey }: any) => <div data-testid={`area-${dataKey}`} />,
  PieChart: ({ children }: any) => <div data-testid="pie-chart">{children}</div>,
  Pie: ({ dataKey }: any) => <div data-testid={`pie-${dataKey}`} />,
  Cell: () => <div data-testid="pie-cell" />,
}));

const mockStorageMetricsService = StorageMetricsService as jest.MockedClass<typeof StorageMetricsService>;
const mockNotificationService = NotificationService as jest.MockedClass<typeof NotificationService>;

// Mock data
const mockStorageMetrics: StorageMetrics = {
  timestamp: new Date('2024-01-15T10:30:00Z'),
  database: {
    totalSize: 1073741824, // 1GB
    tableSize: {
      market_data: 536870912, // 512MB
      features: 268435456, // 256MB
      signals: 134217728, // 128MB
      trades: 67108864, // 64MB
    },
    indexSize: 107374182, // 100MB
    connectionCount: 25,
    activeConnections: 15,
    maxConnections: 100,
    avgQueryTime: 125,
    slowQueries: [],
    queryRate: 150,
    chunks: 1250,
    compressionRatio: 0.75,
    retentionPolicy: [],
  },
  cache: {
    memoryUsage: 134217728, // 128MB
    maxMemory: 268435456, // 256MB
    hitRate: 92.5,
    missRate: 7.5,
    evictionRate: 0.1,
    keyCount: 15000,
    expiredKeys: 125,
    connectedClients: 8,
    opsPerSecond: 2500,
    avgLatency: 0.8,
  },
  filesystem: {
    totalSpace: 107374182400, // 100GB
    usedSpace: 32212254720, // 30GB
    freeSpace: 75161927680, // 70GB
    inodeUsage: 15.5,
  },
};

const mockHistoricalData = [
  {
    timestamp: '2024-01-15T10:00:00Z',
    databaseSize: 1000000000,
    cacheHitRate: 90.5,
    queryRate: 140,
  },
  {
    timestamp: '2024-01-15T10:30:00Z',
    databaseSize: 1073741824,
    cacheHitRate: 92.5,
    queryRate: 150,
  },
];

const mockSlowQueries: SlowQuery[] = [
  {
    id: 'slow-query-1',
    query: 'SELECT * FROM market_data WHERE timestamp > NOW() - INTERVAL \'1 hour\'',
    duration: 5432,
    timestamp: new Date('2024-01-15T10:29:00Z'),
    database: 'fxml4',
    user: 'api_user',
    rowsExamined: 1000000,
    rowsReturned: 50000,
  },
];

const mockTableSizes = {
  market_data: { size: 536870912, rows: 1000000 },
  features: { size: 268435456, rows: 500000 },
  signals: { size: 134217728, rows: 250000 },
};

describe('StorageManager', () => {
  let mockStorageMetricsServiceInstance: jest.Mocked<StorageMetricsService>;
  let mockNotificationServiceInstance: jest.Mocked<NotificationService>;

  beforeEach(() => {
    mockStorageMetricsServiceInstance = {
      getCurrentMetrics: jest.fn(),
      getDatabaseMetrics: jest.fn(),
      getCacheMetrics: jest.fn(),
      getHistoricalMetrics: jest.fn(),
      getSlowQueries: jest.fn(),
      getTableSizes: jest.fn(),
      getActiveConnections: jest.fn(),
      getRetentionPolicies: jest.fn(),
      getCacheStatsByPattern: jest.fn(),
      getCacheKeys: jest.fn(),
      flushCachePattern: jest.fn(),
      runVacuumAnalysis: jest.fn(),
      getCompressionRecommendations: jest.fn(),
      applyCompression: jest.fn(),
      setAlertThresholds: jest.fn(),
      checkStorageHealth: jest.fn(),
      updateMetrics: jest.fn(),
      emitAlert: jest.fn(),
      sendRealtimeUpdate: jest.fn(),
      startPeriodicMetricsCollection: jest.fn(),
      stopPeriodicMetricsCollection: jest.fn(),
      calculateStorageTrends: jest.fn(),
      destroy: jest.fn(),
    } as any;

    mockNotificationServiceInstance = {
      create: jest.fn(),
      getAll: jest.fn(),
      dismiss: jest.fn(),
      markAsRead: jest.fn(),
      destroy: jest.fn(),
    } as any;

    mockStorageMetricsService.mockImplementation(() => mockStorageMetricsServiceInstance);
    mockNotificationService.mockImplementation(() => mockNotificationServiceInstance);

    jest.clearAllMocks();
  });

  describe('Component Rendering', () => {
    it('should render storage manager with loading state initially', () => {
      mockStorageMetricsServiceInstance.getCurrentMetrics.mockResolvedValue(mockStorageMetrics);

      render(<StorageManager />);

      expect(screen.getByText('Storage Manager')).toBeInTheDocument();
      expect(screen.getByText('Loading...')).toBeInTheDocument();
    });

    it('should render storage metrics after loading', async () => {
      mockStorageMetricsServiceInstance.getCurrentMetrics.mockResolvedValue(mockStorageMetrics);
      mockStorageMetricsServiceInstance.getHistoricalMetrics.mockResolvedValue(mockHistoricalData);

      render(<StorageManager />);

      await waitFor(() => {
        expect(screen.getByText('Database Storage')).toBeInTheDocument();
        expect(screen.getByText('Cache Performance')).toBeInTheDocument();
        expect(screen.getByText('File System')).toBeInTheDocument();
      });
    });

    it('should display database storage metrics correctly', async () => {
      mockStorageMetricsServiceInstance.getCurrentMetrics.mockResolvedValue(mockStorageMetrics);
      mockStorageMetricsServiceInstance.getHistoricalMetrics.mockResolvedValue(mockHistoricalData);

      render(<StorageManager />);

      await waitFor(() => {
        expect(screen.getByTestId('database-total-size')).toHaveTextContent('1 GB');
        expect(screen.getByTestId('database-connections')).toHaveTextContent('15/100');
        expect(screen.getByTestId('database-query-rate')).toHaveTextContent('150');
        expect(screen.getByTestId('database-avg-query-time')).toHaveTextContent('125ms');
      });
    });

    it('should display cache performance metrics correctly', async () => {
      mockStorageMetricsServiceInstance.getCurrentMetrics.mockResolvedValue(mockStorageMetrics);
      mockStorageMetricsServiceInstance.getHistoricalMetrics.mockResolvedValue(mockHistoricalData);

      render(<StorageManager />);

      await waitFor(() => {
        expect(screen.getByTestId('cache-memory-usage')).toHaveTextContent('128 MB / 256 MB');
        expect(screen.getByTestId('cache-hit-rate')).toHaveTextContent('92.5%');
        expect(screen.getByTestId('cache-operations')).toHaveTextContent('2,500/s');
        expect(screen.getByTestId('cache-latency')).toHaveTextContent('0.8ms');
      });
    });

    it('should display file system metrics correctly', async () => {
      mockStorageMetricsServiceInstance.getCurrentMetrics.mockResolvedValue(mockStorageMetrics);
      mockStorageMetricsServiceInstance.getHistoricalMetrics.mockResolvedValue(mockHistoricalData);

      render(<StorageManager />);

      await waitFor(() => {
        expect(screen.getByTestId('filesystem-used-space')).toHaveTextContent('30 GB / 100 GB');
        expect(screen.getByTestId('filesystem-usage-percentage')).toHaveTextContent('30.0%');
        expect(screen.getByTestId('filesystem-inode-usage')).toHaveTextContent('15.5%');
      });
    });

    it('should render storage trend charts', async () => {
      mockStorageMetricsServiceInstance.getCurrentMetrics.mockResolvedValue(mockStorageMetrics);
      mockStorageMetricsServiceInstance.getHistoricalMetrics.mockResolvedValue(mockHistoricalData);

      render(<StorageManager />);

      await waitFor(() => {
        expect(screen.getByTestId('storage-trends-chart')).toBeInTheDocument();
        expect(screen.getByTestId('line-chart')).toBeInTheDocument();
        expect(screen.getByTestId('line-databaseSize')).toBeInTheDocument();
        expect(screen.getByTestId('line-cacheHitRate')).toBeInTheDocument();
      });
    });

    it('should render table size distribution chart', async () => {
      mockStorageMetricsServiceInstance.getCurrentMetrics.mockResolvedValue(mockStorageMetrics);
      mockStorageMetricsServiceInstance.getTableSizes.mockResolvedValue(mockTableSizes);

      render(<StorageManager />);

      await waitFor(() => {
        expect(screen.getByTestId('table-distribution-chart')).toBeInTheDocument();
        expect(screen.getByTestId('pie-chart')).toBeInTheDocument();
        expect(screen.getByTestId('pie-size')).toBeInTheDocument();
      });
    });
  });

  describe('Interactive Features', () => {
    it('should allow switching between chart time ranges', async () => {
      mockStorageMetricsServiceInstance.getCurrentMetrics.mockResolvedValue(mockStorageMetrics);
      mockStorageMetricsServiceInstance.getHistoricalMetrics.mockResolvedValue(mockHistoricalData);

      render(<StorageManager />);

      await waitFor(() => {
        expect(screen.getByText('Storage Manager')).toBeInTheDocument();
      });

      // Switch to 24h view
      const timeRangeSelect = screen.getByLabelText('Time range');
      await userEvent.selectOptions(timeRangeSelect, '24h');

      expect(mockStorageMetricsServiceInstance.getHistoricalMetrics).toHaveBeenCalledWith(
        expect.objectContaining({
          interval: '1h',
        })
      );
    });

    it('should allow filtering metrics by type', async () => {
      mockStorageMetricsServiceInstance.getCurrentMetrics.mockResolvedValue(mockStorageMetrics);
      mockStorageMetricsServiceInstance.getHistoricalMetrics.mockResolvedValue(mockHistoricalData);

      render(<StorageManager />);

      await waitFor(() => {
        expect(screen.getByText('Database Storage')).toBeInTheDocument();
        expect(screen.getByText('Cache Performance')).toBeInTheDocument();
      });

      // Filter to show only database metrics
      const metricsFilter = screen.getByLabelText('Filter metrics');
      await userEvent.selectOptions(metricsFilter, 'database');

      await waitFor(() => {
        expect(screen.getByText('Database Storage')).toBeInTheDocument();
        expect(screen.queryByText('Cache Performance')).not.toBeInTheDocument();
      });
    });

    it('should show slow queries when database section is expanded', async () => {
      mockStorageMetricsServiceInstance.getCurrentMetrics.mockResolvedValue(mockStorageMetrics);
      mockStorageMetricsServiceInstance.getSlowQueries.mockResolvedValue(mockSlowQueries);

      render(<StorageManager />);

      await waitFor(() => {
        expect(screen.getByText('Database Storage')).toBeInTheDocument();
      });

      // Expand database section
      const expandButton = screen.getByTestId('expand-database-section');
      await userEvent.click(expandButton);

      await waitFor(() => {
        expect(screen.getByText('Slow Queries')).toBeInTheDocument();
        expect(screen.getByText(/SELECT \* FROM market_data/)).toBeInTheDocument();
        expect(screen.getByText('5,432ms')).toBeInTheDocument();
      });
    });

    it('should allow running vacuum analysis', async () => {
      const mockVacuumResult = {
        tablesAnalyzed: 5,
        spaceClaimed: 268435456,
        duration: 45000,
        recommendations: ['Consider increasing autovacuum_work_mem'],
      };

      mockStorageMetricsServiceInstance.getCurrentMetrics.mockResolvedValue(mockStorageMetrics);
      mockStorageMetricsServiceInstance.runVacuumAnalysis.mockResolvedValue(mockVacuumResult);

      render(<StorageManager />);

      await waitFor(() => {
        expect(screen.getByText('Database Storage')).toBeInTheDocument();
      });

      // Expand database section first
      const expandButton = screen.getByTestId('expand-database-section');
      await userEvent.click(expandButton);

      await waitFor(() => {
        expect(screen.getByTestId('run-vacuum-analysis')).toBeInTheDocument();
      });

      // Click vacuum analysis button
      const vacuumButton = screen.getByTestId('run-vacuum-analysis');
      await userEvent.click(vacuumButton);

      expect(mockStorageMetricsServiceInstance.runVacuumAnalysis).toHaveBeenCalled();

      await waitFor(() => {
        expect(mockNotificationServiceInstance.create).toHaveBeenCalledWith({
          type: 'success',
          title: 'Vacuum Analysis Complete',
          message: 'Analyzed 5 tables, reclaimed 256 MB in 45s',
        });
      });
    });

    it('should allow flushing cache patterns', async () => {
      mockStorageMetricsServiceInstance.getCurrentMetrics.mockResolvedValue(mockStorageMetrics);
      mockStorageMetricsServiceInstance.flushCachePattern.mockResolvedValue({ removedKeys: 150 });

      render(<StorageManager />);

      await waitFor(() => {
        expect(screen.getByText('Cache Performance')).toBeInTheDocument();
      });

      // Enter cache pattern and flush
      const cachePatternInput = screen.getByLabelText('Cache pattern');
      await userEvent.type(cachePatternInput, 'temp:*');

      const flushButton = screen.getByTestId('flush-cache-pattern');
      await userEvent.click(flushButton);

      expect(mockStorageMetricsServiceInstance.flushCachePattern).toHaveBeenCalledWith('temp:*');

      await waitFor(() => {
        expect(mockNotificationServiceInstance.create).toHaveBeenCalledWith({
          type: 'success',
          title: 'Cache Flushed',
          message: 'Removed 150 keys matching pattern: temp:*',
        });
      });
    });
  });

  describe('Alert Generation', () => {
    it('should generate alerts for high database usage', async () => {
      const highUsageMetrics = {
        ...mockStorageMetrics,
        database: {
          ...mockStorageMetrics.database,
          totalSize: 9663676416, // 9GB out of 10GB (90%)
        },
      };

      mockStorageMetricsServiceInstance.getCurrentMetrics.mockResolvedValue(highUsageMetrics);

      const onAlert = jest.fn();
      render(<StorageManager onAlert={onAlert} />);

      await waitFor(() => {
        expect(onAlert).toHaveBeenCalledWith(
          expect.objectContaining({
            type: 'storage',
            severity: 'warning',
            title: 'High Database Usage',
            message: expect.stringContaining('90%'),
          })
        );
      });
    });

    it('should generate alerts for low cache hit rate', async () => {
      const lowCacheMetrics = {
        ...mockStorageMetrics,
        cache: {
          ...mockStorageMetrics.cache,
          hitRate: 75.2, // Below 80% threshold
        },
      };

      mockStorageMetricsServiceInstance.getCurrentMetrics.mockResolvedValue(lowCacheMetrics);

      const onAlert = jest.fn();
      render(<StorageManager onAlert={onAlert} />);

      await waitFor(() => {
        expect(onAlert).toHaveBeenCalledWith(
          expect.objectContaining({
            type: 'storage',
            severity: 'warning',
            title: 'Low Cache Hit Rate',
            message: expect.stringContaining('75.2%'),
          })
        );
      });
    });

    it('should generate alerts for critical file system usage', async () => {
      const criticalFsMetrics = {
        ...mockStorageMetrics,
        filesystem: {
          ...mockStorageMetrics.filesystem!,
          usedSpace: 96636764160, // 90GB out of 100GB (90%)
        },
      };

      mockStorageMetricsServiceInstance.getCurrentMetrics.mockResolvedValue(criticalFsMetrics);

      const onAlert = jest.fn();
      render(<StorageManager onAlert={onAlert} />);

      await waitFor(() => {
        expect(onAlert).toHaveBeenCalledWith(
          expect.objectContaining({
            type: 'storage',
            severity: 'critical',
            title: 'Critical File System Usage',
            message: expect.stringContaining('90%'),
          })
        );
      });
    });
  });

  describe('Real-time Updates', () => {
    it('should auto-refresh metrics at specified intervals', async () => {
      jest.useFakeTimers();

      mockStorageMetricsServiceInstance.getCurrentMetrics.mockResolvedValue(mockStorageMetrics);
      mockStorageMetricsServiceInstance.getHistoricalMetrics.mockResolvedValue(mockHistoricalData);

      render(<StorageManager refreshInterval={5000} />);

      // Initial load
      await waitFor(() => {
        expect(mockStorageMetricsServiceInstance.getCurrentMetrics).toHaveBeenCalledTimes(1);
      });

      // Fast forward 5 seconds
      jest.advanceTimersByTime(5000);

      await waitFor(() => {
        expect(mockStorageMetricsServiceInstance.getCurrentMetrics).toHaveBeenCalledTimes(2);
      });

      jest.useRealTimers();
    });

    it('should emit real-time updates when metrics change', async () => {
      const onMetricsUpdate = jest.fn();
      mockStorageMetricsServiceInstance.getCurrentMetrics.mockResolvedValue(mockStorageMetrics);

      render(<StorageManager onMetricsUpdate={onMetricsUpdate} />);

      await waitFor(() => {
        expect(onMetricsUpdate).toHaveBeenCalledWith(mockStorageMetrics);
      });
    });
  });

  describe('Dashboard Integration', () => {
    it('should accept service instances as props', async () => {
      const customService = mockStorageMetricsServiceInstance;
      customService.getCurrentMetrics.mockResolvedValue(mockStorageMetrics);

      render(<StorageManager storageMetricsService={customService} />);

      await waitFor(() => {
        expect(customService.getCurrentMetrics).toHaveBeenCalled();
      });
    });

    it('should support grid positioning', async () => {
      mockStorageMetricsServiceInstance.getCurrentMetrics.mockResolvedValue(mockStorageMetrics);

      render(<StorageManager gridArea="storage-manager" className="custom-grid-item" />);

      await waitFor(() => {
        const container = screen.getByTestId('storage-manager');
        expect(container).toHaveClass('custom-grid-item');
        expect(container).toHaveStyle('grid-area: storage-manager');
      });
    });

    it('should emit status change events for dashboard coordination', async () => {
      const onStatusChange = jest.fn();
      mockStorageMetricsServiceInstance.getCurrentMetrics.mockResolvedValue(mockStorageMetrics);

      render(<StorageManager onStatusChange={onStatusChange} />);

      await waitFor(() => {
        expect(onStatusChange).toHaveBeenCalledWith(
          expect.objectContaining({
            type: 'storage',
            status: 'healthy',
            metrics: expect.any(Object),
          })
        );
      });
    });
  });

  describe('Error Handling', () => {
    it('should display error message when metrics fail to load', async () => {
      mockStorageMetricsServiceInstance.getCurrentMetrics.mockRejectedValue(new Error('Network error'));

      render(<StorageManager />);

      await waitFor(() => {
        expect(screen.getByText('Error loading storage metrics: Network error')).toBeInTheDocument();
      });
    });

    it('should handle vacuum analysis errors gracefully', async () => {
      mockStorageMetricsServiceInstance.getCurrentMetrics.mockResolvedValue(mockStorageMetrics);
      mockStorageMetricsServiceInstance.runVacuumAnalysis.mockRejectedValue(new Error('Database locked'));

      render(<StorageManager />);

      await waitFor(() => {
        expect(screen.getByText('Database Storage')).toBeInTheDocument();
      });

      // Expand database section first
      const expandButton = screen.getByTestId('expand-database-section');
      await userEvent.click(expandButton);

      await waitFor(() => {
        expect(screen.getByTestId('run-vacuum-analysis')).toBeInTheDocument();
      });

      const vacuumButton = screen.getByTestId('run-vacuum-analysis');
      await userEvent.click(vacuumButton);

      await waitFor(() => {
        expect(mockNotificationServiceInstance.create).toHaveBeenCalledWith({
          type: 'error',
          title: 'Vacuum Analysis Failed',
          message: 'Failed to run vacuum analysis: Database locked',
        });
      });
    });

    it('should handle cache flush errors gracefully', async () => {
      mockStorageMetricsServiceInstance.getCurrentMetrics.mockResolvedValue(mockStorageMetrics);
      mockStorageMetricsServiceInstance.flushCachePattern.mockRejectedValue(new Error('Cache unavailable'));

      render(<StorageManager />);

      await waitFor(() => {
        expect(screen.getByLabelText('Cache pattern')).toBeInTheDocument();
      });

      const cachePatternInput = screen.getByLabelText('Cache pattern');
      await userEvent.type(cachePatternInput, 'temp:*');

      const flushButton = screen.getByTestId('flush-cache-pattern');
      await userEvent.click(flushButton);

      await waitFor(() => {
        expect(mockNotificationServiceInstance.create).toHaveBeenCalledWith({
          type: 'error',
          title: 'Cache Flush Failed',
          message: 'Failed to flush cache pattern: Cache unavailable',
        });
      });
    });
  });

  describe('Accessibility', () => {
    it('should have proper ARIA labels and roles', async () => {
      mockStorageMetricsServiceInstance.getCurrentMetrics.mockResolvedValue(mockStorageMetrics);

      render(<StorageManager />);

      await waitFor(() => {
        expect(screen.getByRole('region', { name: 'Storage Manager' })).toBeInTheDocument();
        expect(screen.getByLabelText('Time range')).toBeInTheDocument();
        expect(screen.getByLabelText('Filter metrics')).toBeInTheDocument();
        expect(screen.getByLabelText('Cache pattern')).toBeInTheDocument();
      });
    });

    it('should support keyboard navigation', async () => {
      mockStorageMetricsServiceInstance.getCurrentMetrics.mockResolvedValue(mockStorageMetrics);
      mockStorageMetricsServiceInstance.runVacuumAnalysis.mockResolvedValue({
        tablesAnalyzed: 5,
        spaceClaimed: 268435456,
        duration: 45000,
        recommendations: [],
      });

      render(<StorageManager />);

      await waitFor(() => {
        expect(screen.getByText('Database Storage')).toBeInTheDocument();
      });

      // Expand database section first
      const expandButton = screen.getByTestId('expand-database-section');
      await userEvent.click(expandButton);

      await waitFor(() => {
        expect(screen.getByTestId('run-vacuum-analysis')).toBeInTheDocument();
      });

      // Tab to vacuum button and press Enter
      const vacuumButton = screen.getByTestId('run-vacuum-analysis');
      vacuumButton.focus();
      fireEvent.keyDown(vacuumButton, { key: 'Enter', code: 'Enter' });

      expect(mockStorageMetricsServiceInstance.runVacuumAnalysis).toHaveBeenCalled();
    });
  });

  describe('Responsive Design', () => {
    it('should adapt layout for mobile screens', async () => {
      // Mock window.innerWidth for mobile
      Object.defineProperty(window, 'innerWidth', {
        writable: true,
        configurable: true,
        value: 375,
      });

      mockStorageMetricsServiceInstance.getCurrentMetrics.mockResolvedValue(mockStorageMetrics);

      render(<StorageManager />);

      await waitFor(() => {
        const container = screen.getByTestId('storage-manager');
        expect(container).toHaveClass('mobile-layout');
      });
    });

    it('should stack charts vertically on small screens', async () => {
      Object.defineProperty(window, 'innerWidth', {
        writable: true,
        configurable: true,
        value: 640,
      });

      mockStorageMetricsServiceInstance.getCurrentMetrics.mockResolvedValue(mockStorageMetrics);
      mockStorageMetricsServiceInstance.getHistoricalMetrics.mockResolvedValue(mockHistoricalData);

      render(<StorageManager />);

      await waitFor(() => {
        const chartsContainer = screen.getByTestId('charts-container');
        expect(chartsContainer).toHaveClass('flex-col');
      });
    });
  });
});
