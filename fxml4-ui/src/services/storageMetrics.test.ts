/**
 * StorageMetricsService Tests
 *
 * Tests for database and cache storage monitoring
 */

import { StorageMetricsService } from './storageMetrics';
import { StorageMetrics, SlowQuery, RetentionPolicy } from '@/types/dataManagement';
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

describe('StorageMetricsService', () => {
  let storageMetricsService: StorageMetricsService;
  let mockEventBus: MockEventEmitter;

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

  const mockSlowQuery: SlowQuery = {
    id: 'slow-query-1',
    query: 'SELECT * FROM market_data WHERE timestamp > NOW() - INTERVAL \'1 hour\'',
    duration: 5432,
    timestamp: new Date('2024-01-15T10:29:00Z'),
    database: 'fxml4',
    user: 'api_user',
    rowsExamined: 1000000,
    rowsReturned: 50000,
  };

  beforeEach(() => {
    mockEventBus = new MockEventEmitter();
    storageMetricsService = new StorageMetricsService({
      eventBus: mockEventBus,
      websocket: mockWebSocket as any,
      apiBaseUrl: 'http://localhost:8000/api',
    });

    jest.clearAllMocks();
    mockFetch.mockClear();
  });

  afterEach(() => {
    storageMetricsService.destroy();
  });

  describe('Storage Metrics Retrieval', () => {
    it('should get current storage metrics', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockStorageMetrics,
      });

      const metrics = await storageMetricsService.getCurrentMetrics();

      expect(metrics).toEqual(mockStorageMetrics);
      expect(mockFetch).toHaveBeenCalledWith('http://localhost:8000/api/storage/metrics');
    });

    it('should get database-specific metrics', async () => {
      const databaseMetrics = {
        timestamp: new Date().toISOString(),
        database: mockStorageMetrics.database,
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => databaseMetrics,
      });

      const metrics = await storageMetricsService.getDatabaseMetrics();

      expect(metrics).toEqual(databaseMetrics);
      expect(mockFetch).toHaveBeenCalledWith('http://localhost:8000/api/storage/database/metrics');
    });

    it('should get cache-specific metrics', async () => {
      const cacheMetrics = {
        timestamp: new Date().toISOString(),
        cache: mockStorageMetrics.cache,
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => cacheMetrics,
      });

      const metrics = await storageMetricsService.getCacheMetrics();

      expect(metrics).toEqual(cacheMetrics);
      expect(mockFetch).toHaveBeenCalledWith('http://localhost:8000/api/storage/cache/metrics');
    });

    it('should get historical storage metrics', async () => {
      const historicalData = [
        {
          timestamp: new Date('2024-01-15T10:00:00Z').toISOString(),
          databaseSize: 1000000000,
          cacheHitRate: 90.5,
          queryRate: 140,
        },
        {
          timestamp: new Date('2024-01-15T10:30:00Z').toISOString(),
          databaseSize: 1073741824,
          cacheHitRate: 92.5,
          queryRate: 150,
        },
      ];

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => historicalData,
      });

      const history = await storageMetricsService.getHistoricalMetrics({
        start: new Date('2024-01-15T10:00:00Z'),
        end: new Date('2024-01-15T11:00:00Z'),
        interval: '30m',
      });

      expect(history).toEqual(historicalData);
      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/storage/metrics/history?start=2024-01-15T10%3A00%3A00.000Z&end=2024-01-15T11%3A00%3A00.000Z&interval=30m'
      );
    });
  });

  describe('Database Monitoring', () => {
    it('should get slow queries', async () => {
      const slowQueries = [mockSlowQuery];
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => slowQueries,
      });

      const queries = await storageMetricsService.getSlowQueries({
        limit: 50,
        minDuration: 1000,
      });

      expect(queries).toEqual(slowQueries);
      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/storage/database/slow-queries?limit=50&minDuration=1000'
      );
    });

    it('should get table sizes', async () => {
      const tableSizes = {
        market_data: { size: 536870912, rows: 1000000 },
        features: { size: 268435456, rows: 500000 },
        signals: { size: 134217728, rows: 250000 },
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => tableSizes,
      });

      const sizes = await storageMetricsService.getTableSizes();

      expect(sizes).toEqual(tableSizes);
      expect(mockFetch).toHaveBeenCalledWith('http://localhost:8000/api/storage/database/table-sizes');
    });

    it('should get active connections', async () => {
      const connections = [
        {
          pid: 12345,
          database: 'fxml4',
          username: 'api_user',
          clientAddress: '127.0.0.1',
          state: 'active',
          query: 'SELECT * FROM market_data LIMIT 100',
          duration: 1250,
        },
        {
          pid: 12346,
          database: 'fxml4',
          username: 'worker_user',
          clientAddress: '127.0.0.1',
          state: 'idle',
          query: null,
          duration: 0,
        },
      ];

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => connections,
      });

      const activeConnections = await storageMetricsService.getActiveConnections();

      expect(activeConnections).toEqual(connections);
      expect(mockFetch).toHaveBeenCalledWith('http://localhost:8000/api/storage/database/connections');
    });

    it('should get retention policies', async () => {
      const retentionPolicies: RetentionPolicy[] = [
        {
          tableName: 'market_data',
          retentionPeriod: '90 days',
          compressionPolicy: '7 days',
          lastCleanup: new Date('2024-01-14T00:00:00Z'),
          dataRemoved: 1073741824,
        },
        {
          tableName: 'features',
          retentionPeriod: '30 days',
          lastCleanup: new Date('2024-01-14T00:00:00Z'),
          dataRemoved: 536870912,
        },
      ];

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => retentionPolicies,
      });

      const policies = await storageMetricsService.getRetentionPolicies();

      expect(policies).toEqual(retentionPolicies);
      expect(mockFetch).toHaveBeenCalledWith('http://localhost:8000/api/storage/database/retention-policies');
    });
  });

  describe('Cache Monitoring', () => {
    it('should get cache statistics by key pattern', async () => {
      const cacheStats = {
        pattern: 'market_data:*',
        keyCount: 5000,
        totalMemory: 67108864, // 64MB
        avgTtl: 3600, // 1 hour
        hitRate: 95.2,
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => cacheStats,
      });

      const stats = await storageMetricsService.getCacheStatsByPattern('market_data:*');

      expect(stats).toEqual(cacheStats);
      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/storage/cache/stats?pattern=market_data%3A*'
      );
    });

    it('should get cache key information', async () => {
      const cacheKeys = [
        {
          key: 'market_data:EURUSD:1h',
          type: 'list',
          size: 1024,
          ttl: 3600,
          memory: 2048,
        },
        {
          key: 'features:EURUSD:latest',
          type: 'hash',
          size: 512,
          ttl: 1800,
          memory: 1024,
        },
      ];

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => cacheKeys,
      });

      const keys = await storageMetricsService.getCacheKeys({
        pattern: 'market_data:*',
        limit: 100,
      });

      expect(keys).toEqual(cacheKeys);
      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/storage/cache/keys?pattern=market_data%3A*&limit=100'
      );
    });

    it('should flush cache by pattern', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ removedKeys: 150 }),
      });

      const result = await storageMetricsService.flushCachePattern('temp:*');

      expect(result).toEqual({ removedKeys: 150 });
      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/storage/cache/flush',
        expect.objectContaining({
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ pattern: 'temp:*' }),
        })
      );
    });
  });

  describe('Storage Optimization', () => {
    it('should run database vacuum analysis', async () => {
      const vacuumResult = {
        tablesAnalyzed: 5,
        spaceClaimed: 268435456, // 256MB
        duration: 45000, // 45 seconds
        recommendations: [
          'Consider increasing autovacuum_work_mem',
          'Table market_data may benefit from manual CLUSTER',
        ],
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => vacuumResult,
      });

      const result = await storageMetricsService.runVacuumAnalysis();

      expect(result).toEqual(vacuumResult);
      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/storage/database/vacuum-analyze',
        expect.objectContaining({
          method: 'POST',
        })
      );
    });

    it('should get compression recommendations', async () => {
      const compressionRecommendations = [
        {
          tableName: 'market_data',
          currentSize: 536870912,
          estimatedCompressedSize: 134217728,
          compressionRatio: 0.25,
          recommendation: 'Enable compression on chunks older than 7 days',
        },
        {
          tableName: 'features',
          currentSize: 268435456,
          estimatedCompressedSize: 67108864,
          compressionRatio: 0.25,
          recommendation: 'Enable compression on chunks older than 3 days',
        },
      ];

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => compressionRecommendations,
      });

      const recommendations = await storageMetricsService.getCompressionRecommendations();

      expect(recommendations).toEqual(compressionRecommendations);
      expect(mockFetch).toHaveBeenCalledWith('http://localhost:8000/api/storage/database/compression-recommendations');
    });

    it('should apply compression to table chunks', async () => {
      const compressionResult = {
        tableName: 'market_data',
        chunksCompressed: 50,
        spaceSaved: 402653184, // ~384MB
        duration: 120000, // 2 minutes
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => compressionResult,
      });

      const result = await storageMetricsService.applyCompression('market_data', {
        olderThan: '7 days',
        algorithm: 'lz4',
      });

      expect(result).toEqual(compressionResult);
      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/storage/database/compress',
        expect.objectContaining({
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            tableName: 'market_data',
            olderThan: '7 days',
            algorithm: 'lz4',
          }),
        })
      );
    });
  });

  describe('Alerting and Thresholds', () => {
    it('should set storage alert thresholds', async () => {
      const thresholds = {
        databaseSizeWarning: 0.8, // 80%
        databaseSizeCritical: 0.9, // 90%
        cacheHitRateWarning: 85, // 85%
        cacheHitRateCritical: 75, // 75%
        slowQueryThreshold: 5000, // 5 seconds
        connectionCountWarning: 80, // 80 connections
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => thresholds,
      });

      const result = await storageMetricsService.setAlertThresholds(thresholds);

      expect(result).toEqual(thresholds);
      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/storage/alert-thresholds',
        expect.objectContaining({
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(thresholds),
        })
      );
    });

    it('should check storage health and generate alerts', async () => {
      const healthCheck = {
        overall: 'warning',
        checks: [
          {
            name: 'database_size',
            status: 'healthy',
            value: 75.2,
            threshold: 80,
            message: 'Database size within normal limits',
          },
          {
            name: 'cache_hit_rate',
            status: 'warning',
            value: 82.3,
            threshold: 85,
            message: 'Cache hit rate below warning threshold',
          },
          {
            name: 'slow_queries',
            status: 'healthy',
            value: 3,
            threshold: 10,
            message: 'Slow query count within limits',
          },
        ],
        timestamp: new Date().toISOString(),
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => healthCheck,
      });

      const health = await storageMetricsService.checkStorageHealth();

      expect(health).toEqual(healthCheck);
      expect(mockFetch).toHaveBeenCalledWith('http://localhost:8000/api/storage/health-check');
    });
  });

  describe('Real-time Updates', () => {
    it('should emit events when storage metrics are updated', () => {
      const metricsSpy = jest.fn();
      mockEventBus.on('storage:metricsUpdated', metricsSpy);

      storageMetricsService.updateMetrics(mockStorageMetrics);

      expect(metricsSpy).toHaveBeenCalledWith(mockStorageMetrics);
    });

    it('should emit alerts when thresholds are exceeded', () => {
      const alertSpy = jest.fn();
      mockEventBus.on('storage:alert', alertSpy);

      const alert = {
        type: 'database_size',
        severity: 'warning' as const,
        message: 'Database size approaching limit',
        value: 85.5,
        threshold: 80,
        timestamp: new Date(),
      };

      storageMetricsService.emitAlert(alert);

      expect(alertSpy).toHaveBeenCalledWith(alert);
    });

    it('should send real-time updates over WebSocket', () => {
      const update = {
        type: 'storage_metrics',
        data: {
          databaseSize: 1073741824,
          cacheHitRate: 92.5,
          activeConnections: 15,
        },
      };

      storageMetricsService.sendRealtimeUpdate(update);

      expect(mockWebSocket.send).toHaveBeenCalledTimes(1);

      const sentMessage = mockWebSocket.send.mock.calls[0][0];
      const parsedMessage = JSON.parse(sentMessage);

      expect(parsedMessage.type).toBe('storage:update');
      expect(parsedMessage.data.type).toBe('storage_metrics');
      expect(parsedMessage.data.data).toEqual(update.data);
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

      const serviceWithError = new StorageMetricsService({
        eventBus: mockEventBus,
        websocket: errorWebSocket as any,
        apiBaseUrl: 'http://localhost:8000/api',
      });

      expect(() => {
        serviceWithError.sendRealtimeUpdate({
          type: 'storage_metrics',
          data: { databaseSize: 1073741824 },
        });
      }).not.toThrow();

      serviceWithError.destroy();
    });
  });

  describe('Performance Monitoring', () => {
    it('should start periodic metrics collection', () => {
      jest.useFakeTimers();

      const metricsSpy = jest.spyOn(storageMetricsService, 'getCurrentMetrics').mockResolvedValue(mockStorageMetrics);

      storageMetricsService.startPeriodicMetricsCollection(5000); // 5 seconds for testing

      // Fast forward time
      jest.advanceTimersByTime(5000);

      expect(metricsSpy).toHaveBeenCalled();

      storageMetricsService.stopPeriodicMetricsCollection();
      metricsSpy.mockRestore();
      jest.useRealTimers();
    });

    it('should calculate storage trends', () => {
      const historicalData = [
        { timestamp: '2024-01-15T10:00:00Z', databaseSize: 1000000000 },
        { timestamp: '2024-01-15T10:30:00Z', databaseSize: 1050000000 },
        { timestamp: '2024-01-15T11:00:00Z', databaseSize: 1073741824 },
      ];

      const trends = storageMetricsService.calculateStorageTrends(historicalData);

      expect(trends.databaseSize.trend).toBe('increasing');
      expect(trends.databaseSize.rate).toBeGreaterThan(0);
      expect(trends.databaseSize.projection).toBeDefined();
    });
  });

  describe('Error Handling', () => {
    it('should handle API errors gracefully', async () => {
      mockFetch.mockRejectedValueOnce(new Error('Network error'));

      await expect(storageMetricsService.getCurrentMetrics()).rejects.toThrow('Network error');
    });

    it('should handle HTTP error responses', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        statusText: 'Internal Server Error',
      });

      await expect(storageMetricsService.getCurrentMetrics()).rejects.toThrow('HTTP error! status: 500');
    });

    it('should handle malformed API responses', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => {
          throw new Error('Invalid JSON');
        },
      });

      await expect(storageMetricsService.getCurrentMetrics()).rejects.toThrow('Invalid JSON');
    });
  });
});
