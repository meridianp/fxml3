/**
 * DataSourceService Tests
 *
 * Tests for data source monitoring and connection management
 */

import { DataSourceService } from './dataSource';
import { DataSource, ConnectionStatus, DataSourceType, DataQualityLevel } from '@/types/dataManagement';
import { EventEmitter } from 'events';

// Mock WebSocket
const mockWebSocket = {
  send: jest.fn(),
  close: jest.fn(),
  readyState: WebSocket.OPEN,
  addEventListener: jest.fn(),
  removeEventListener: jest.fn(),
};

// Mock EventEmitter for testing
class MockEventEmitter extends EventEmitter {}

// Mock fetch for API calls
const mockFetch = jest.fn();
global.fetch = mockFetch;

describe('DataSourceService', () => {
  let dataSourceService: DataSourceService;
  let mockEventBus: MockEventEmitter;

  const mockDataSource: DataSource = {
    id: 'test-source-1',
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
    description: 'Interactive Brokers TWS connection',
    tags: ['broker', 'primary', 'real-time'],
    createdAt: new Date('2024-01-01T00:00:00Z'),
    updatedAt: new Date('2024-01-15T10:30:00Z'),
  };

  beforeEach(() => {
    mockEventBus = new MockEventEmitter();
    dataSourceService = new DataSourceService({
      eventBus: mockEventBus,
      websocket: mockWebSocket as any,
      apiBaseUrl: 'http://localhost:8000/api',
    });

    jest.clearAllMocks();
    mockFetch.mockClear();
  });

  afterEach(() => {
    dataSourceService.destroy();
  });

  describe('Data Source Management', () => {
    it('should add a new data source', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockDataSource,
      });

      const result = await dataSourceService.addDataSource({
        name: 'Interactive Brokers',
        type: DataSourceType.BROKER,
        url: 'ws://localhost:7497',
        description: 'Interactive Brokers TWS connection',
        tags: ['broker', 'primary', 'real-time'],
      });

      expect(result).toEqual(mockDataSource);
      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/data-sources',
        expect.objectContaining({
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
        })
      );
    });

    it('should get all data sources', async () => {
      const mockSources = [mockDataSource];
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockSources,
      });

      const sources = await dataSourceService.getDataSources();

      expect(sources).toEqual(mockSources);
      expect(mockFetch).toHaveBeenCalledWith('http://localhost:8000/api/data-sources');
    });

    it('should get data source by ID', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockDataSource,
      });

      const source = await dataSourceService.getDataSource('test-source-1');

      expect(source).toEqual(mockDataSource);
      expect(mockFetch).toHaveBeenCalledWith('http://localhost:8000/api/data-sources/test-source-1');
    });

    it('should return null for non-existent data source', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 404,
      });

      const source = await dataSourceService.getDataSource('non-existent');

      expect(source).toBeNull();
    });

    it('should update data source configuration', async () => {
      const updatedSource = { ...mockDataSource, timeout: 10000 };
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => updatedSource,
      });

      const result = await dataSourceService.updateDataSource('test-source-1', {
        timeout: 10000,
      });

      expect(result).toEqual(updatedSource);
      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/data-sources/test-source-1',
        expect.objectContaining({
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
        })
      );
    });

    it('should delete data source', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
      });

      const result = await dataSourceService.deleteDataSource('test-source-1');

      expect(result).toBe(true);
      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/data-sources/test-source-1',
        expect.objectContaining({
          method: 'DELETE',
        })
      );
    });
  });

  describe('Connection Monitoring', () => {
    it('should test connection to data source', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ status: 'connected', latency: 45 }),
      });

      const result = await dataSourceService.testConnection('test-source-1');

      expect(result).toEqual({
        status: 'connected',
        latency: 45,
        timestamp: expect.any(Date),
      });
      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/data-sources/test-source-1/test-connection',
        expect.objectContaining({
          method: 'POST',
        })
      );
    });

    it('should get real-time status for all sources', async () => {
      const mockStatuses = [
        { id: 'test-source-1', status: ConnectionStatus.CONNECTED, latency: 45 },
        { id: 'test-source-2', status: ConnectionStatus.DISCONNECTED, latency: null },
      ];

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockStatuses,
      });

      const statuses = await dataSourceService.getConnectionStatuses();

      expect(statuses).toEqual(mockStatuses);
      expect(mockFetch).toHaveBeenCalledWith('http://localhost:8000/api/data-sources/status');
    });

    it('should filter sources by status', async () => {
      const mockSources = [
        { ...mockDataSource, id: 'source-1', status: ConnectionStatus.CONNECTED },
        { ...mockDataSource, id: 'source-2', status: ConnectionStatus.DISCONNECTED },
        { ...mockDataSource, id: 'source-3', status: ConnectionStatus.CONNECTED },
      ];

      dataSourceService['dataSources'] = new Map(mockSources.map(s => [s.id, s]));

      const connectedSources = dataSourceService.getSourcesByStatus(ConnectionStatus.CONNECTED);
      expect(connectedSources).toHaveLength(2);
      expect(connectedSources.every(s => s.status === ConnectionStatus.CONNECTED)).toBe(true);
    });

    it('should filter sources by type', async () => {
      const mockSources = [
        { ...mockDataSource, id: 'source-1', type: DataSourceType.BROKER },
        { ...mockDataSource, id: 'source-2', type: DataSourceType.FEED },
        { ...mockDataSource, id: 'source-3', type: DataSourceType.BROKER },
      ];

      dataSourceService['dataSources'] = new Map(mockSources.map(s => [s.id, s]));

      const brokerSources = dataSourceService.getSourcesByType(DataSourceType.BROKER);
      expect(brokerSources).toHaveLength(2);
      expect(brokerSources.every(s => s.type === DataSourceType.BROKER)).toBe(true);
    });
  });

  describe('Performance Metrics', () => {
    it('should get performance metrics for all sources', async () => {
      const mockMetrics = {
        timestamp: new Date().toISOString(),
        sources: [
          {
            id: 'test-source-1',
            latency: 45,
            throughput: 1250,
            errorRate: 0.02,
            uptime: 99.95,
          },
        ],
        summary: {
          totalSources: 1,
          connectedSources: 1,
          avgLatency: 45,
          avgThroughput: 1250,
          avgUptime: 99.95,
        },
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockMetrics,
      });

      const metrics = await dataSourceService.getPerformanceMetrics();

      expect(metrics).toEqual(mockMetrics);
      expect(mockFetch).toHaveBeenCalledWith('http://localhost:8000/api/data-sources/metrics');
    });

    it('should get historical performance data', async () => {
      const mockHistoryData = [
        {
          timestamp: new Date('2024-01-15T10:00:00Z').toISOString(),
          latency: 42,
          throughput: 1180,
          errorRate: 0.01,
        },
        {
          timestamp: new Date('2024-01-15T10:30:00Z').toISOString(),
          latency: 45,
          throughput: 1250,
          errorRate: 0.02,
        },
      ];

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockHistoryData,
      });

      const history = await dataSourceService.getPerformanceHistory('test-source-1', {
        start: new Date('2024-01-15T10:00:00Z'),
        end: new Date('2024-01-15T11:00:00Z'),
        interval: '30m',
      });

      expect(history).toEqual(mockHistoryData);
      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/data-sources/test-source-1/metrics/history?start=2024-01-15T10%3A00%3A00.000Z&end=2024-01-15T11%3A00%3A00.000Z&interval=30m'
      );
    });
  });

  describe('Real-time Updates', () => {
    it('should emit events when data source status changes', () => {
      // Add mock data source to the service's internal Map
      dataSourceService['dataSources'].set('test-source-1', mockDataSource);

      const statusSpy = jest.fn();
      mockEventBus.on('dataSource:statusChanged', statusSpy);

      dataSourceService.updateSourceStatus('test-source-1', {
        status: ConnectionStatus.DISCONNECTED,
        lastUpdate: new Date(),
      });

      expect(statusSpy).toHaveBeenCalledWith({
        sourceId: 'test-source-1',
        status: ConnectionStatus.DISCONNECTED,
        lastUpdate: expect.any(Date),
      });
    });

    it('should emit events when performance metrics are updated', () => {
      // Add mock data source to the service's internal Map
      dataSourceService['dataSources'].set('test-source-1', mockDataSource);

      const metricsSpy = jest.fn();
      mockEventBus.on('dataSource:metricsUpdated', metricsSpy);

      dataSourceService.updateSourceMetrics('test-source-1', {
        latency: 50,
        throughput: 1300,
        errorRate: 0.01,
      });

      expect(metricsSpy).toHaveBeenCalledWith({
        sourceId: 'test-source-1',
        metrics: {
          latency: 50,
          throughput: 1300,
          errorRate: 0.01,
        },
      });
    });

    it('should send updates over WebSocket when connected', () => {
      const update = {
        sourceId: 'test-source-1',
        status: ConnectionStatus.CONNECTED,
        metrics: { latency: 45, throughput: 1250 },
      };

      dataSourceService.sendRealtimeUpdate(update);

      expect(mockWebSocket.send).toHaveBeenCalledTimes(1);

      const sentMessage = mockWebSocket.send.mock.calls[0][0];
      const parsedMessage = JSON.parse(sentMessage);

      expect(parsedMessage.type).toBe('dataSource:update');
      expect(parsedMessage.data.sourceId).toBe('test-source-1');
      expect(parsedMessage.data.status).toBe(ConnectionStatus.CONNECTED);
      expect(parsedMessage.data.metrics).toEqual({ latency: 45, throughput: 1250 });
      expect(parsedMessage.data.timestamp).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}.\d{3}Z$/);
    });

    it('should handle WebSocket connection errors gracefully', () => {
      const errorWebSocket = {
        ...mockWebSocket,
        readyState: WebSocket.CLOSED,
        send: jest.fn(() => {
          throw new Error('WebSocket connection closed');
        }),
      };

      const serviceWithError = new DataSourceService({
        eventBus: mockEventBus,
        websocket: errorWebSocket as any,
        apiBaseUrl: 'http://localhost:8000/api',
      });

      expect(() => {
        serviceWithError.sendRealtimeUpdate({
          sourceId: 'test-source-1',
          status: ConnectionStatus.CONNECTED,
        });
      }).not.toThrow();

      serviceWithError.destroy();
    });
  });

  describe('Auto-discovery and Health Checks', () => {
    it('should discover available data sources', async () => {
      const mockDiscoveredSources = [
        {
          type: DataSourceType.BROKER,
          name: 'Interactive Brokers',
          url: 'ws://localhost:7497',
          detected: true,
        },
        {
          type: DataSourceType.FEED,
          name: 'Polygon.io',
          url: 'wss://socket.polygon.io',
          detected: false,
        },
      ];

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockDiscoveredSources,
      });

      const discovered = await dataSourceService.discoverDataSources();

      expect(discovered).toEqual(mockDiscoveredSources);
      expect(mockFetch).toHaveBeenCalledWith('http://localhost:8000/api/data-sources/discover');
    });

    it('should run health checks on all sources', async () => {
      const mockHealthResults = [
        {
          sourceId: 'test-source-1',
          healthy: true,
          checks: [
            { name: 'connection', status: 'pass', message: 'Connected' },
            { name: 'latency', status: 'pass', message: 'Latency within limits' },
          ],
        },
      ];

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockHealthResults,
      });

      const health = await dataSourceService.runHealthChecks();

      expect(health).toEqual(mockHealthResults);
      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/data-sources/health-check',
        expect.objectContaining({
          method: 'POST',
        })
      );
    });

    it('should schedule periodic health checks', () => {
      jest.useFakeTimers();

      const healthCheckSpy = jest.spyOn(dataSourceService, 'runHealthChecks').mockResolvedValue([]);

      dataSourceService.startPeriodicHealthChecks(1000); // 1 second for testing

      // Fast forward time
      jest.advanceTimersByTime(1000);

      expect(healthCheckSpy).toHaveBeenCalled();

      dataSourceService.stopPeriodicHealthChecks();
      healthCheckSpy.mockRestore();
      jest.useRealTimers();
    });
  });

  describe('Error Handling', () => {
    it('should handle API errors gracefully', async () => {
      mockFetch.mockRejectedValueOnce(new Error('Network error'));

      await expect(dataSourceService.getDataSources()).rejects.toThrow('Network error');
    });

    it('should handle malformed API responses', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => {
          throw new Error('Invalid JSON');
        },
      });

      await expect(dataSourceService.getDataSources()).rejects.toThrow('Invalid JSON');
    });

    it('should handle HTTP error responses', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        statusText: 'Internal Server Error',
      });

      await expect(dataSourceService.getDataSources()).rejects.toThrow('HTTP error! status: 500');
    });
  });
});
