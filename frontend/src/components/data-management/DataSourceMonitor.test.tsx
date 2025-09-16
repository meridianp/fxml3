/**
 * DataSourceMonitor Component Tests
 *
 * Tests for data source connection monitoring and status display
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { DataSourceMonitor } from './DataSourceMonitor';
import { DataSourceService } from '@/services/dataSource';
import { NotificationService } from '@/services/notification';
import { DataSource, DataSourceType, ConnectionStatus, DataQualityLevel } from '@/types/dataManagement';

// Mock services
jest.mock('@/services/dataSource');
jest.mock('@/services/notification');

const mockDataSourceService = DataSourceService as jest.MockedClass<typeof DataSourceService>;
const mockNotificationService = NotificationService as jest.MockedClass<typeof NotificationService>;

// Mock data
const mockDataSources: DataSource[] = [
  {
    id: 'ib-source',
    name: 'Interactive Brokers',
    type: DataSourceType.BROKER,
    status: ConnectionStatus.CONNECTED,
    url: 'ws://localhost:7497',
    lastUpdate: new Date('2024-01-15T10:30:00Z'),
    lastHeartbeat: new Date('2024-01-15T10:29:55Z'),
    latency: 45,
    throughput: 1250,
    errorRate: 0.02,
    uptime: 99.95,
    qualityScore: 98,
    qualityLevel: DataQualityLevel.EXCELLENT,
    enabled: true,
    retryCount: 0,
    timeout: 5000,
    description: 'Primary broker connection',
    tags: ['broker', 'primary', 'real-time'],
    createdAt: new Date('2024-01-01T00:00:00Z'),
    updatedAt: new Date('2024-01-15T10:30:00Z'),
  },
  {
    id: 'polygon-source',
    name: 'Polygon.io',
    type: DataSourceType.FEED,
    status: ConnectionStatus.DISCONNECTED,
    url: 'wss://socket.polygon.io',
    lastUpdate: new Date('2024-01-15T10:20:00Z'),
    lastHeartbeat: new Date('2024-01-15T10:15:00Z'),
    latency: 0,
    throughput: 0,
    errorRate: 100,
    uptime: 85.3,
    qualityScore: 25,
    qualityLevel: DataQualityLevel.POOR,
    enabled: true,
    retryCount: 3,
    timeout: 5000,
    description: 'Market data feed',
    tags: ['feed', 'backup'],
    createdAt: new Date('2024-01-01T00:00:00Z'),
    updatedAt: new Date('2024-01-15T10:20:00Z'),
  },
  {
    id: 'database-source',
    name: 'TimescaleDB',
    type: DataSourceType.DATABASE,
    status: ConnectionStatus.DEGRADED,
    url: 'postgresql://localhost:5433/fxml4',
    lastUpdate: new Date('2024-01-15T10:29:00Z'),
    lastHeartbeat: new Date('2024-01-15T10:28:50Z'),
    latency: 150,
    throughput: 800,
    errorRate: 5.2,
    uptime: 97.1,
    qualityScore: 78,
    qualityLevel: DataQualityLevel.GOOD,
    enabled: true,
    retryCount: 1,
    timeout: 10000,
    description: 'Primary database',
    tags: ['database', 'timeseries'],
    createdAt: new Date('2024-01-01T00:00:00Z'),
    updatedAt: new Date('2024-01-15T10:29:00Z'),
  },
];

const mockPerformanceMetrics = {
  timestamp: new Date().toISOString(),
  sources: [
    {
      id: 'ib-source',
      latency: 45,
      throughput: 1250,
      errorRate: 0.02,
      uptime: 99.95,
    },
  ],
  summary: {
    totalSources: 3,
    connectedSources: 1,
    avgLatency: 65,
    avgThroughput: 683,
    avgUptime: 94.12,
  },
};

describe('DataSourceMonitor', () => {
  let mockDataSourceServiceInstance: jest.Mocked<DataSourceService>;
  let mockNotificationServiceInstance: jest.Mocked<NotificationService>;

  beforeEach(() => {
    mockDataSourceServiceInstance = {
      getDataSources: jest.fn(),
      getDataSource: jest.fn(),
      addDataSource: jest.fn(),
      updateDataSource: jest.fn(),
      deleteDataSource: jest.fn(),
      testConnection: jest.fn(),
      getConnectionStatuses: jest.fn(),
      getPerformanceMetrics: jest.fn(),
      getPerformanceHistory: jest.fn(),
      getSourcesByStatus: jest.fn(),
      getSourcesByType: jest.fn(),
      updateSourceStatus: jest.fn(),
      updateSourceMetrics: jest.fn(),
      sendRealtimeUpdate: jest.fn(),
      discoverDataSources: jest.fn(),
      runHealthChecks: jest.fn(),
      startPeriodicHealthChecks: jest.fn(),
      stopPeriodicHealthChecks: jest.fn(),
      destroy: jest.fn(),
    } as any;

    mockNotificationServiceInstance = {
      create: jest.fn(),
      getAll: jest.fn(),
      dismiss: jest.fn(),
      markAsRead: jest.fn(),
      destroy: jest.fn(),
    } as any;

    mockDataSourceService.mockImplementation(() => mockDataSourceServiceInstance);
    mockNotificationService.mockImplementation(() => mockNotificationServiceInstance);

    // Reset all mocks
    jest.clearAllMocks();
  });

  describe('Component Rendering', () => {
    it('should render data source monitor with loading state initially', () => {
      mockDataSourceServiceInstance.getDataSources.mockResolvedValue([]);
      mockDataSourceServiceInstance.getPerformanceMetrics.mockResolvedValue(mockPerformanceMetrics);

      render(<DataSourceMonitor />);

      expect(screen.getByText('Data Source Monitor')).toBeInTheDocument();
      expect(screen.getByText('Loading...')).toBeInTheDocument();
    });

    it('should render data sources after loading', async () => {
      mockDataSourceServiceInstance.getDataSources.mockResolvedValue(mockDataSources);
      mockDataSourceServiceInstance.getPerformanceMetrics.mockResolvedValue(mockPerformanceMetrics);

      render(<DataSourceMonitor />);

      await waitFor(() => {
        expect(screen.getByText('Interactive Brokers')).toBeInTheDocument();
        expect(screen.getByText('Polygon.io')).toBeInTheDocument();
        expect(screen.getByText('TimescaleDB')).toBeInTheDocument();
      });
    });

    it('should display connection status indicators correctly', async () => {
      mockDataSourceServiceInstance.getDataSources.mockResolvedValue(mockDataSources);
      mockDataSourceServiceInstance.getPerformanceMetrics.mockResolvedValue(mockPerformanceMetrics);

      render(<DataSourceMonitor />);

      await waitFor(() => {
        // Connected source should show green indicator
        const ibSource = screen.getByTestId('data-source-ib-source');
        expect(within(ibSource).getByTestId('status-connected')).toBeInTheDocument();

        // Disconnected source should show red indicator
        const polygonSource = screen.getByTestId('data-source-polygon-source');
        expect(within(polygonSource).getByTestId('status-disconnected')).toBeInTheDocument();

        // Degraded source should show yellow indicator
        const dbSource = screen.getByTestId('data-source-database-source');
        expect(within(dbSource).getByTestId('status-degraded')).toBeInTheDocument();
      });
    });

    it('should display performance metrics correctly', async () => {
      mockDataSourceServiceInstance.getDataSources.mockResolvedValue(mockDataSources);
      mockDataSourceServiceInstance.getPerformanceMetrics.mockResolvedValue(mockPerformanceMetrics);

      render(<DataSourceMonitor />);

      await waitFor(() => {
        // Check latency display
        expect(screen.getByText('45ms')).toBeInTheDocument();
        expect(screen.getByText('150ms')).toBeInTheDocument();

        // Check throughput display
        expect(screen.getByText('1,250')).toBeInTheDocument();
        expect(screen.getByText('800')).toBeInTheDocument();

        // Check uptime display
        expect(screen.getByText('99.95%')).toBeInTheDocument();
        expect(screen.getByText('97.1%')).toBeInTheDocument();
      });
    });

    it('should display quality scores with appropriate colors', async () => {
      mockDataSourceServiceInstance.getDataSources.mockResolvedValue(mockDataSources);
      mockDataSourceServiceInstance.getPerformanceMetrics.mockResolvedValue(mockPerformanceMetrics);

      render(<DataSourceMonitor />);

      await waitFor(() => {
        // Excellent quality score (98) should be green
        const excellentScore = screen.getByTestId('quality-score-ib-source');
        expect(excellentScore).toHaveClass('text-green-600');
        expect(excellentScore).toHaveTextContent('98');

        // Poor quality score (25) should be orange
        const poorScore = screen.getByTestId('quality-score-polygon-source');
        expect(poorScore).toHaveClass('text-orange-600');
        expect(poorScore).toHaveTextContent('25');

        // Good quality score (78) should be blue
        const goodScore = screen.getByTestId('quality-score-database-source');
        expect(goodScore).toHaveClass('text-blue-600');
        expect(goodScore).toHaveTextContent('78');
      });
    });
  });

  describe('Interactive Features', () => {
    it('should allow filtering by connection status', async () => {
      mockDataSourceServiceInstance.getDataSources.mockResolvedValue(mockDataSources);
      mockDataSourceServiceInstance.getPerformanceMetrics.mockResolvedValue(mockPerformanceMetrics);

      render(<DataSourceMonitor />);

      await waitFor(() => {
        expect(screen.getByText('Interactive Brokers')).toBeInTheDocument();
        expect(screen.getByText('Polygon.io')).toBeInTheDocument();
      });

      // Filter by connected status
      const statusFilter = screen.getByLabelText('Filter by status');
      await userEvent.selectOptions(statusFilter, 'connected');

      await waitFor(() => {
        expect(screen.getByText('Interactive Brokers')).toBeInTheDocument();
        expect(screen.queryByText('Polygon.io')).not.toBeInTheDocument();
      });
    });

    it('should allow filtering by data source type', async () => {
      mockDataSourceServiceInstance.getDataSources.mockResolvedValue(mockDataSources);
      mockDataSourceServiceInstance.getPerformanceMetrics.mockResolvedValue(mockPerformanceMetrics);

      render(<DataSourceMonitor />);

      await waitFor(() => {
        expect(screen.getByText('Interactive Brokers')).toBeInTheDocument();
        expect(screen.getByText('TimescaleDB')).toBeInTheDocument();
      });

      // Filter by broker type
      const typeFilter = screen.getByLabelText('Filter by type');
      await userEvent.selectOptions(typeFilter, 'broker');

      await waitFor(() => {
        expect(screen.getByText('Interactive Brokers')).toBeInTheDocument();
        expect(screen.queryByText('TimescaleDB')).not.toBeInTheDocument();
      });
    });

    it('should allow searching by data source name', async () => {
      mockDataSourceServiceInstance.getDataSources.mockResolvedValue(mockDataSources);
      mockDataSourceServiceInstance.getPerformanceMetrics.mockResolvedValue(mockPerformanceMetrics);

      render(<DataSourceMonitor />);

      await waitFor(() => {
        expect(screen.getByText('Interactive Brokers')).toBeInTheDocument();
        expect(screen.getByText('Polygon.io')).toBeInTheDocument();
      });

      // Search for "Interactive"
      const searchInput = screen.getByLabelText('Search data sources');
      await userEvent.type(searchInput, 'Interactive');

      await waitFor(() => {
        expect(screen.getByText('Interactive Brokers')).toBeInTheDocument();
        expect(screen.queryByText('Polygon.io')).not.toBeInTheDocument();
      });
    });

    it('should test connection when test button is clicked', async () => {
      const mockConnectionResult = {
        status: 'connected' as const,
        latency: 45,
        timestamp: new Date(),
      };

      mockDataSourceServiceInstance.getDataSources.mockResolvedValue(mockDataSources);
      mockDataSourceServiceInstance.getPerformanceMetrics.mockResolvedValue(mockPerformanceMetrics);
      mockDataSourceServiceInstance.testConnection.mockResolvedValue(mockConnectionResult);

      render(<DataSourceMonitor />);

      await waitFor(() => {
        expect(screen.getByText('Interactive Brokers')).toBeInTheDocument();
      });

      // Click test connection button
      const testButton = screen.getByTestId('test-connection-ib-source');
      await userEvent.click(testButton);

      expect(mockDataSourceServiceInstance.testConnection).toHaveBeenCalledWith('ib-source');

      await waitFor(() => {
        expect(mockNotificationServiceInstance.create).toHaveBeenCalledWith({
          type: 'success',
          title: 'Connection Test',
          message: 'Connection to Interactive Brokers successful (45ms)',
        });
      });
    });

    it('should show error notification when connection test fails', async () => {
      mockDataSourceServiceInstance.getDataSources.mockResolvedValue(mockDataSources);
      mockDataSourceServiceInstance.getPerformanceMetrics.mockResolvedValue(mockPerformanceMetrics);
      mockDataSourceServiceInstance.testConnection.mockRejectedValue(new Error('Connection failed'));

      render(<DataSourceMonitor />);

      await waitFor(() => {
        expect(screen.getByText('Interactive Brokers')).toBeInTheDocument();
      });

      // Click test connection button
      const testButton = screen.getByTestId('test-connection-ib-source');
      await userEvent.click(testButton);

      await waitFor(() => {
        expect(mockNotificationServiceInstance.create).toHaveBeenCalledWith({
          type: 'error',
          title: 'Connection Test Failed',
          message: 'Failed to test connection to Interactive Brokers: Connection failed',
        });
      });
    });
  });

  describe('Real-time Updates', () => {
    it('should update data source status from real-time events', async () => {
      mockDataSourceServiceInstance.getDataSources.mockResolvedValue(mockDataSources);
      mockDataSourceServiceInstance.getPerformanceMetrics.mockResolvedValue(mockPerformanceMetrics);

      render(<DataSourceMonitor />);

      await waitFor(() => {
        const ibSource = screen.getByTestId('data-source-ib-source');
        expect(within(ibSource).getByTestId('status-connected')).toBeInTheDocument();
      });

      // Simulate status change by updating mock and triggering refresh button
      const updatedSources = mockDataSources.map(source =>
        source.id === 'ib-source'
          ? { ...source, status: ConnectionStatus.DISCONNECTED }
          : source
      );

      mockDataSourceServiceInstance.getDataSources.mockResolvedValue(updatedSources);

      // Click refresh button to trigger data reload
      const refreshButton = screen.getByText('Refresh');
      await userEvent.click(refreshButton);

      await waitFor(() => {
        const ibSource = screen.getByTestId('data-source-ib-source');
        expect(within(ibSource).getByTestId('status-disconnected')).toBeInTheDocument();
      });
    });

    it('should auto-refresh data at specified intervals', async () => {
      jest.useFakeTimers();

      mockDataSourceServiceInstance.getDataSources.mockResolvedValue(mockDataSources);
      mockDataSourceServiceInstance.getPerformanceMetrics.mockResolvedValue(mockPerformanceMetrics);

      render(<DataSourceMonitor refreshInterval={5000} />);

      // Initial load
      await waitFor(() => {
        expect(mockDataSourceServiceInstance.getDataSources).toHaveBeenCalledTimes(1);
      });

      // Fast forward 5 seconds
      jest.advanceTimersByTime(5000);

      await waitFor(() => {
        expect(mockDataSourceServiceInstance.getDataSources).toHaveBeenCalledTimes(2);
      });

      jest.useRealTimers();
    });
  });

  describe('Summary Statistics', () => {
    it('should display correct summary statistics', async () => {
      mockDataSourceServiceInstance.getDataSources.mockResolvedValue(mockDataSources);
      mockDataSourceServiceInstance.getPerformanceMetrics.mockResolvedValue(mockPerformanceMetrics);

      render(<DataSourceMonitor />);

      await waitFor(() => {
        expect(screen.getByTestId('total-sources')).toHaveTextContent('3');
        expect(screen.getByTestId('connected-sources')).toHaveTextContent('1');
        expect(screen.getByTestId('average-latency')).toHaveTextContent('65ms');
        expect(screen.getByTestId('average-uptime')).toHaveTextContent('94.12%');
      });
    });

    it('should update summary when data sources change', async () => {
      mockDataSourceServiceInstance.getDataSources.mockResolvedValue(mockDataSources.slice(0, 1)); // Only IB
      mockDataSourceServiceInstance.getPerformanceMetrics.mockResolvedValue({
        ...mockPerformanceMetrics,
        summary: {
          totalSources: 1,
          connectedSources: 1,
          avgLatency: 45,
          avgThroughput: 1250,
          avgUptime: 99.95,
        },
      });

      render(<DataSourceMonitor />);

      await waitFor(() => {
        expect(screen.getByTestId('total-sources')).toHaveTextContent('1');
        expect(screen.getByTestId('connected-sources')).toHaveTextContent('1');
        expect(screen.getByTestId('average-latency')).toHaveTextContent('45ms');
        expect(screen.getByTestId('average-uptime')).toHaveTextContent('99.95%');
      });
    });
  });

  describe('Error Handling', () => {
    it('should display error message when data sources fail to load', async () => {
      mockDataSourceServiceInstance.getDataSources.mockRejectedValue(new Error('Network error'));
      mockDataSourceServiceInstance.getPerformanceMetrics.mockResolvedValue(mockPerformanceMetrics);

      render(<DataSourceMonitor />);

      await waitFor(() => {
        expect(screen.getByText('Error loading data sources: Network error')).toBeInTheDocument();
      });
    });

    it('should display error message when performance metrics fail to load', async () => {
      mockDataSourceServiceInstance.getDataSources.mockResolvedValue(mockDataSources);
      mockDataSourceServiceInstance.getPerformanceMetrics.mockRejectedValue(new Error('Metrics error'));

      render(<DataSourceMonitor />);

      await waitFor(() => {
        expect(screen.getByText('Error loading performance metrics: Metrics error')).toBeInTheDocument();
      });
    });

    it('should handle empty data sources gracefully', async () => {
      mockDataSourceServiceInstance.getDataSources.mockResolvedValue([]);
      mockDataSourceServiceInstance.getPerformanceMetrics.mockResolvedValue({
        ...mockPerformanceMetrics,
        sources: [],
        summary: {
          totalSources: 0,
          connectedSources: 0,
          avgLatency: 0,
          avgThroughput: 0,
          avgUptime: 0,
        },
      });

      render(<DataSourceMonitor />);

      await waitFor(() => {
        expect(screen.getByText('No data sources found')).toBeInTheDocument();
        expect(screen.getByTestId('total-sources')).toHaveTextContent('0');
      });
    });
  });

  describe('Accessibility', () => {
    it('should have proper ARIA labels and roles', async () => {
      mockDataSourceServiceInstance.getDataSources.mockResolvedValue(mockDataSources);
      mockDataSourceServiceInstance.getPerformanceMetrics.mockResolvedValue(mockPerformanceMetrics);

      render(<DataSourceMonitor />);

      await waitFor(() => {
        expect(screen.getByRole('region', { name: 'Data Source Monitor' })).toBeInTheDocument();
        expect(screen.getByRole('table', { name: 'Data sources' })).toBeInTheDocument();
        expect(screen.getByLabelText('Search data sources')).toBeInTheDocument();
        expect(screen.getByLabelText('Filter by status')).toBeInTheDocument();
        expect(screen.getByLabelText('Filter by type')).toBeInTheDocument();
      });
    });

    it('should support keyboard navigation', async () => {
      mockDataSourceServiceInstance.getDataSources.mockResolvedValue(mockDataSources);
      mockDataSourceServiceInstance.getPerformanceMetrics.mockResolvedValue(mockPerformanceMetrics);
      mockDataSourceServiceInstance.testConnection.mockResolvedValue({
        status: 'connected',
        latency: 45,
        timestamp: new Date(),
      });

      render(<DataSourceMonitor />);

      await waitFor(() => {
        expect(screen.getByText('Interactive Brokers')).toBeInTheDocument();
      });

      // Tab to test connection button and press Enter
      const testButton = screen.getByTestId('test-connection-ib-source');
      testButton.focus();
      fireEvent.keyDown(testButton, { key: 'Enter', code: 'Enter' });

      expect(mockDataSourceServiceInstance.testConnection).toHaveBeenCalledWith('ib-source');
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

      mockDataSourceServiceInstance.getDataSources.mockResolvedValue(mockDataSources);
      mockDataSourceServiceInstance.getPerformanceMetrics.mockResolvedValue(mockPerformanceMetrics);

      render(<DataSourceMonitor />);

      await waitFor(() => {
        // Check if mobile-specific classes are applied
        const container = screen.getByTestId('data-source-monitor');
        expect(container).toHaveClass('mobile-layout');
      });
    });
  });

  describe('Component Props', () => {
    it('should accept and use custom CSS classes', async () => {
      mockDataSourceServiceInstance.getDataSources.mockResolvedValue(mockDataSources);
      mockDataSourceServiceInstance.getPerformanceMetrics.mockResolvedValue(mockPerformanceMetrics);

      render(<DataSourceMonitor className="custom-monitor-class" />);

      await waitFor(() => {
        const container = screen.getByTestId('data-source-monitor');
        expect(container).toHaveClass('custom-monitor-class');
      });
    });

    it('should use custom refresh interval', async () => {
      jest.useFakeTimers();

      mockDataSourceServiceInstance.getDataSources.mockResolvedValue(mockDataSources);
      mockDataSourceServiceInstance.getPerformanceMetrics.mockResolvedValue(mockPerformanceMetrics);

      render(<DataSourceMonitor refreshInterval={10000} />);

      await waitFor(() => {
        expect(mockDataSourceServiceInstance.getDataSources).toHaveBeenCalledTimes(1);
      });

      // Fast forward 10 seconds
      jest.advanceTimersByTime(10000);

      await waitFor(() => {
        expect(mockDataSourceServiceInstance.getDataSources).toHaveBeenCalledTimes(2);
      });

      jest.useRealTimers();
    });

    it('should disable auto-refresh when specified', async () => {
      jest.useFakeTimers();

      mockDataSourceServiceInstance.getDataSources.mockResolvedValue(mockDataSources);
      mockDataSourceServiceInstance.getPerformanceMetrics.mockResolvedValue(mockPerformanceMetrics);

      render(<DataSourceMonitor autoRefresh={false} />);

      await waitFor(() => {
        expect(mockDataSourceServiceInstance.getDataSources).toHaveBeenCalledTimes(1);
      });

      // Fast forward time - should not trigger refresh
      jest.advanceTimersByTime(30000);

      expect(mockDataSourceServiceInstance.getDataSources).toHaveBeenCalledTimes(1);

      jest.useRealTimers();
    });
  });
});
