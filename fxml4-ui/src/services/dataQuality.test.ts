/**
 * DataQualityService Tests
 *
 * Tests for real-time data quality monitoring and validation
 */

import { DataQualityService } from './dataQuality';
import { DataQualityMetrics, ValidationError, DataQualityLevel } from '@/types/dataManagement';
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

describe('DataQualityService', () => {
  let dataQualityService: DataQualityService;
  let mockEventBus: MockEventEmitter;

  const mockQualityMetrics: DataQualityMetrics = {
    timestamp: new Date('2024-01-15T10:30:00Z'),
    source: 'Interactive Brokers',
    symbol: 'EURUSD',
    timeframe: '1m',
    completeness: {
      score: 98.5,
      expectedRecords: 1440, // 24 hours * 60 minutes
      actualRecords: 1418,
      missingRecords: 22,
      gapCount: 3,
      largestGap: 300, // 5 minutes
    },
    accuracy: {
      score: 95.2,
      outlierCount: 12,
      outlierPercentage: 0.85,
      validationErrors: [],
    },
    timeliness: {
      score: 92.8,
      avgDelay: 125, // ms
      maxDelay: 2500, // ms
      lateRecords: 45,
      onTimePercentage: 96.9,
    },
    consistency: {
      score: 99.1,
      duplicateCount: 2,
      inconsistencyCount: 1,
      schemaViolations: 0,
    },
    overallScore: 96.4,
    qualityLevel: DataQualityLevel.EXCELLENT,
    trend: 'stable',
    previousScore: 96.1,
  };

  const mockValidationError: ValidationError = {
    id: 'validation-error-1',
    timestamp: new Date('2024-01-15T10:29:30Z'),
    severity: 'warning',
    rule: 'bid_ask_spread_check',
    field: 'spread',
    value: 0.05,
    message: 'Bid-ask spread unusually high for EURUSD',
    source: 'Interactive Brokers',
  };

  beforeEach(() => {
    mockEventBus = new MockEventEmitter();
    dataQualityService = new DataQualityService({
      eventBus: mockEventBus,
      websocket: mockWebSocket as any,
      apiBaseUrl: 'http://localhost:8000/api',
    });

    jest.clearAllMocks();
    mockFetch.mockClear();
  });

  afterEach(() => {
    dataQualityService.destroy();
  });

  describe('Quality Metrics Retrieval', () => {
    it('should get current quality metrics for all sources', async () => {
      const allMetrics = [mockQualityMetrics];
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => allMetrics,
      });

      const metrics = await dataQualityService.getCurrentQualityMetrics();

      expect(metrics).toEqual(allMetrics);
      expect(mockFetch).toHaveBeenCalledWith('http://localhost:8000/api/data-quality/metrics');
    });

    it('should get quality metrics for specific source', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockQualityMetrics,
      });

      const metrics = await dataQualityService.getQualityMetricsBySource('Interactive Brokers');

      expect(metrics).toEqual(mockQualityMetrics);
      expect(mockFetch).toHaveBeenCalledWith('http://localhost:8000/api/data-quality/metrics/source/Interactive%20Brokers');
    });

    it('should get quality metrics for specific symbol', async () => {
      const symbolMetrics = [mockQualityMetrics];
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => symbolMetrics,
      });

      const metrics = await dataQualityService.getQualityMetricsBySymbol('EURUSD');

      expect(metrics).toEqual(symbolMetrics);
      expect(mockFetch).toHaveBeenCalledWith('http://localhost:8000/api/data-quality/metrics/symbol/EURUSD');
    });

    it('should get historical quality trends', async () => {
      const trendData = [
        {
          timestamp: new Date('2024-01-15T10:00:00Z').toISOString(),
          overallScore: 95.8,
          completenessScore: 98.2,
          accuracyScore: 94.5,
          timelinessScore: 93.1,
          consistencyScore: 99.3,
        },
        {
          timestamp: new Date('2024-01-15T10:30:00Z').toISOString(),
          overallScore: 96.4,
          completenessScore: 98.5,
          accuracyScore: 95.2,
          timelinessScore: 92.8,
          consistencyScore: 99.1,
        },
      ];

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => trendData,
      });

      const trends = await dataQualityService.getQualityTrends({
        source: 'Interactive Brokers',
        symbol: 'EURUSD',
        start: new Date('2024-01-15T10:00:00Z'),
        end: new Date('2024-01-15T11:00:00Z'),
        interval: '30m',
      });

      expect(trends).toEqual(trendData);
    });
  });

  describe('Validation Rules Management', () => {
    it('should get all validation rules', async () => {
      const validationRules = [
        {
          id: 'bid_ask_spread_check',
          name: 'Bid-Ask Spread Validation',
          description: 'Validates that bid-ask spread is within normal range',
          enabled: true,
          parameters: {
            maxSpread: 0.01,
            warnThreshold: 0.005,
          },
          appliesTo: ['forex'],
          createdAt: new Date('2024-01-01T00:00:00Z').toISOString(),
        },
        {
          id: 'price_continuity_check',
          name: 'Price Continuity Validation',
          description: 'Checks for unusual price jumps',
          enabled: true,
          parameters: {
            maxPriceChange: 0.05, // 5%
            lookbackPeriods: 5,
          },
          appliesTo: ['forex', 'stocks'],
          createdAt: new Date('2024-01-01T00:00:00Z').toISOString(),
        },
      ];

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => validationRules,
      });

      const rules = await dataQualityService.getValidationRules();

      expect(rules).toEqual(validationRules);
      expect(mockFetch).toHaveBeenCalledWith('http://localhost:8000/api/data-quality/validation-rules');
    });

    it('should create new validation rule', async () => {
      const newRule = {
        name: 'Volume Spike Detection',
        description: 'Detects unusual volume spikes',
        parameters: {
          volumeThreshold: 10, // 10x average
          lookbackPeriods: 20,
        },
        appliesTo: ['forex'],
        enabled: true,
      };

      const createdRule = {
        id: 'volume_spike_check',
        ...newRule,
        createdAt: new Date().toISOString(),
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => createdRule,
      });

      const result = await dataQualityService.createValidationRule(newRule);

      expect(result).toEqual(createdRule);
      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/data-quality/validation-rules',
        expect.objectContaining({
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(newRule),
        })
      );
    });

    it('should update validation rule', async () => {
      const updatedRule = {
        id: 'bid_ask_spread_check',
        parameters: {
          maxSpread: 0.015,
          warnThreshold: 0.008,
        },
        enabled: true,
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => updatedRule,
      });

      const result = await dataQualityService.updateValidationRule('bid_ask_spread_check', {
        parameters: {
          maxSpread: 0.015,
          warnThreshold: 0.008,
        },
      });

      expect(result).toEqual(updatedRule);
      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/data-quality/validation-rules/bid_ask_spread_check',
        expect.objectContaining({
          method: 'PUT',
        })
      );
    });

    it('should delete validation rule', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
      });

      const result = await dataQualityService.deleteValidationRule('volume_spike_check');

      expect(result).toBe(true);
      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/data-quality/validation-rules/volume_spike_check',
        expect.objectContaining({
          method: 'DELETE',
        })
      );
    });
  });

  describe('Real-time Validation', () => {
    it('should validate data record against all rules', async () => {
      const dataRecord = {
        symbol: 'EURUSD',
        timestamp: new Date().toISOString(),
        bid: 1.08245,
        ask: 1.08248,
        volume: 1000000,
        source: 'Interactive Brokers',
      };

      const validationResult = {
        valid: true,
        errors: [],
        warnings: [mockValidationError],
        qualityScore: 95.5,
        appliedRules: ['bid_ask_spread_check', 'price_continuity_check'],
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => validationResult,
      });

      const result = await dataQualityService.validateDataRecord(dataRecord);

      expect(result).toEqual(validationResult);
      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/data-quality/validate',
        expect.objectContaining({
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(dataRecord),
        })
      );
    });

    it('should validate batch of data records', async () => {
      const dataRecords = [
        {
          symbol: 'EURUSD',
          timestamp: new Date().toISOString(),
          bid: 1.08245,
          ask: 1.08248,
        },
        {
          symbol: 'GBPUSD',
          timestamp: new Date().toISOString(),
          bid: 1.25123,
          ask: 1.25127,
        },
      ];

      const batchValidationResult = {
        totalRecords: 2,
        validRecords: 2,
        invalidRecords: 0,
        warnings: 1,
        errors: 0,
        overallQualityScore: 97.8,
        results: [
          { recordIndex: 0, valid: true, errors: [], warnings: [] },
          { recordIndex: 1, valid: true, errors: [], warnings: [mockValidationError] },
        ],
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => batchValidationResult,
      });

      const result = await dataQualityService.validateDataBatch(dataRecords);

      expect(result).toEqual(batchValidationResult);
      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/data-quality/validate-batch',
        expect.objectContaining({
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ records: dataRecords }),
        })
      );
    });
  });

  describe('Anomaly Detection', () => {
    it('should detect anomalies in data stream', async () => {
      const anomalies = [
        {
          id: 'anomaly-1',
          timestamp: new Date('2024-01-15T10:29:45Z'),
          symbol: 'EURUSD',
          anomalyType: 'price_spike',
          severity: 'high',
          description: 'Price increased by 0.8% in 1 minute',
          value: 1.08950,
          expectedRange: { min: 1.08200, max: 1.08300 },
          confidence: 0.94,
          source: 'Interactive Brokers',
        },
        {
          id: 'anomaly-2',
          timestamp: new Date('2024-01-15T10:28:30Z'),
          symbol: 'GBPUSD',
          anomalyType: 'volume_spike',
          severity: 'medium',
          description: 'Volume 15x higher than average',
          value: 15000000,
          expectedRange: { min: 800000, max: 1200000 },
          confidence: 0.87,
          source: 'FXCM',
        },
      ];

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => anomalies,
      });

      const result = await dataQualityService.getAnomalies({
        timeframe: '1h',
        minSeverity: 'medium',
        symbols: ['EURUSD', 'GBPUSD'],
      });

      expect(result).toEqual(anomalies);
      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/data-quality/anomalies?timeframe=1h&minSeverity=medium&symbols=EURUSD%2CGBPUSD'
      );
    });

    it('should configure anomaly detection settings', async () => {
      const settings = {
        priceAnomalyThreshold: 0.005, // 0.5%
        volumeAnomalyThreshold: 5.0, // 5x average
        enableRealTimeDetection: true,
        detectionWindow: '5m',
        confidenceThreshold: 0.8,
        notificationSettings: {
          email: true,
          webhook: true,
          dashboard: true,
        },
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => settings,
      });

      const result = await dataQualityService.configureAnomalyDetection(settings);

      expect(result).toEqual(settings);
      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/data-quality/anomaly-detection/config',
        expect.objectContaining({
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(settings),
        })
      );
    });
  });

  describe('Data Profiling', () => {
    it('should generate data profile for symbol', async () => {
      const dataProfile = {
        symbol: 'EURUSD',
        timeframe: '1h',
        period: '30d',
        statistics: {
          recordCount: 720, // 30 days * 24 hours
          completeness: 98.6,
          uniqueness: 100.0,
          validity: 96.8,
          averageLatency: 105, // ms
          dataSize: 1048576, // bytes
        },
        patterns: {
          peakHours: [8, 9, 10, 14, 15, 16], // UTC hours with most activity
          quietHours: [22, 23, 0, 1, 2, 3],
          weekendDataGaps: true,
          holidayDataGaps: true,
        },
        qualityIssues: [
          {
            type: 'missing_data',
            count: 10,
            description: 'Missing records during weekend',
          },
          {
            type: 'duplicate_data',
            count: 3,
            description: 'Duplicate timestamps detected',
          },
        ],
        recommendations: [
          'Consider implementing weekend data backfill',
          'Add duplicate detection in data ingestion pipeline',
        ],
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => dataProfile,
      });

      const result = await dataQualityService.generateDataProfile('EURUSD', {
        timeframe: '1h',
        period: '30d',
      });

      expect(result).toEqual(dataProfile);
      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/data-quality/profile/EURUSD?timeframe=1h&period=30d'
      );
    });

    it('should compare data profiles between sources', async () => {
      const comparison = {
        symbol: 'EURUSD',
        sources: ['Interactive Brokers', 'FXCM'],
        comparisonMetrics: {
          completeness: {
            'Interactive Brokers': 98.6,
            'FXCM': 97.2,
            difference: 1.4,
          },
          accuracy: {
            'Interactive Brokers': 96.8,
            'FXCM': 95.1,
            difference: 1.7,
          },
          timeliness: {
            'Interactive Brokers': 92.3,
            'FXCM': 89.7,
            difference: 2.6,
          },
        },
        discrepancies: [
          {
            type: 'price_difference',
            timestamp: new Date('2024-01-15T10:30:00Z').toISOString(),
            values: {
              'Interactive Brokers': 1.08245,
              'FXCM': 1.08247,
            },
            difference: 0.00002,
          },
        ],
        recommendation: 'Interactive Brokers shows better overall quality',
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => comparison,
      });

      const result = await dataQualityService.compareDataSources('EURUSD', [
        'Interactive Brokers',
        'FXCM',
      ]);

      expect(result).toEqual(comparison);
    });
  });

  describe('Real-time Updates and Events', () => {
    it('should emit quality alerts when thresholds are breached', () => {
      const alertSpy = jest.fn();
      mockEventBus.on('dataQuality:alert', alertSpy);

      const alert = {
        type: 'quality_degradation',
        severity: 'warning' as const,
        symbol: 'EURUSD',
        metric: 'completeness',
        currentValue: 85.5,
        threshold: 90.0,
        message: 'Data completeness below threshold for EURUSD',
        timestamp: new Date(),
      };

      dataQualityService.emitQualityAlert(alert);

      expect(alertSpy).toHaveBeenCalledWith(alert);
    });

    it('should emit validation events when data is processed', () => {
      const validationSpy = jest.fn();
      mockEventBus.on('dataQuality:validation', validationSpy);

      const validationEvent = {
        symbol: 'EURUSD',
        recordCount: 100,
        validRecords: 98,
        warnings: 2,
        errors: 0,
        qualityScore: 98.5,
        timestamp: new Date(),
      };

      dataQualityService.emitValidationEvent(validationEvent);

      expect(validationSpy).toHaveBeenCalledWith(validationEvent);
    });

    it('should send real-time quality updates over WebSocket', () => {
      const update = {
        type: 'quality_metrics',
        symbol: 'EURUSD',
        overallScore: 96.4,
        trend: 'improving',
        lastUpdate: new Date(),
      };

      dataQualityService.sendRealtimeUpdate(update);

      expect(mockWebSocket.send).toHaveBeenCalledTimes(1);

      const sentMessage = mockWebSocket.send.mock.calls[0][0];
      const parsedMessage = JSON.parse(sentMessage);

      expect(parsedMessage.type).toBe('dataQuality:update');
      expect(parsedMessage.data.type).toBe('quality_metrics');
      expect(parsedMessage.data.symbol).toBe('EURUSD');
      expect(parsedMessage.data.overallScore).toBe(96.4);
    });

    it('should handle WebSocket connection errors gracefully', () => {
      const errorWebSocket = {
        ...mockWebSocket,
        readyState: WebSocket.CLOSED,
        send: jest.fn(() => {
          throw new Error('WebSocket connection closed');
        }),
      };

      const serviceWithError = new DataQualityService({
        eventBus: mockEventBus,
        websocket: errorWebSocket as any,
        apiBaseUrl: 'http://localhost:8000/api',
      });

      expect(() => {
        serviceWithError.sendRealtimeUpdate({
          type: 'quality_metrics',
          symbol: 'EURUSD',
          overallScore: 96.4,
        });
      }).not.toThrow();

      serviceWithError.destroy();
    });
  });

  describe('Performance and Caching', () => {
    it('should start periodic quality monitoring', () => {
      jest.useFakeTimers();

      const monitoringSpy = jest.spyOn(dataQualityService, 'getCurrentQualityMetrics').mockResolvedValue([mockQualityMetrics]);

      dataQualityService.startPeriodicQualityMonitoring(10000); // 10 seconds for testing

      // Fast forward time
      jest.advanceTimersByTime(10000);

      expect(monitoringSpy).toHaveBeenCalled();

      dataQualityService.stopPeriodicQualityMonitoring();
      monitoringSpy.mockRestore();
      jest.useRealTimers();
    });

    it('should cache quality metrics for performance', () => {
      const cachedMetrics = [mockQualityMetrics];

      // Set cache
      dataQualityService['cachedMetrics'] = cachedMetrics;
      dataQualityService['cacheTimestamp'] = Date.now();

      const result = dataQualityService.getCachedQualityMetrics();

      expect(result).toEqual(cachedMetrics);
    });

    it('should return null for expired cache', () => {
      const cachedMetrics = [mockQualityMetrics];

      // Set expired cache
      dataQualityService['cachedMetrics'] = cachedMetrics;
      dataQualityService['cacheTimestamp'] = Date.now() - 600000; // 10 minutes ago

      const result = dataQualityService.getCachedQualityMetrics();

      expect(result).toBeNull();
    });
  });

  describe('Error Handling', () => {
    it('should handle API errors gracefully', async () => {
      mockFetch.mockRejectedValueOnce(new Error('Network error'));

      await expect(dataQualityService.getCurrentQualityMetrics()).rejects.toThrow('Network error');
    });

    it('should handle HTTP error responses', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        statusText: 'Internal Server Error',
      });

      await expect(dataQualityService.getCurrentQualityMetrics()).rejects.toThrow('HTTP error! status: 500');
    });

    it('should handle malformed API responses', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => {
          throw new Error('Invalid JSON');
        },
      });

      await expect(dataQualityService.getCurrentQualityMetrics()).rejects.toThrow('Invalid JSON');
    });
  });
});
