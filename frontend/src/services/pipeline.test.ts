/**
 * PipelineService Tests
 *
 * Tests for ML/ETL pipeline monitoring and management
 */

import { PipelineService } from './pipeline';
import { PipelineJob, PipelineJobStatus, PipelineJobType, PipelineMetrics } from '@/types/dataManagement';
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

describe('PipelineService', () => {
  let pipelineService: PipelineService;
  let mockEventBus: MockEventEmitter;

  const mockPipelineJob: PipelineJob = {
    id: 'job-12345',
    name: 'EURUSD Feature Engineering',
    type: PipelineJobType.FEATURE_ENGINEERING,
    status: PipelineJobStatus.RUNNING,
    createdAt: new Date('2024-01-15T10:00:00Z'),
    startedAt: new Date('2024-01-15T10:01:00Z'),
    duration: 1800000, // 30 minutes
    estimatedDuration: 2400000, // 40 minutes
    progress: 75,
    currentStep: 'Generating technical indicators',
    totalSteps: 8,
    completedSteps: 6,
    cpuUsage: 85.5,
    memoryUsage: 2147483648, // 2GB
    diskUsage: 536870912, // 512MB
    recordsProcessed: 150000,
    recordsGenerated: 75000,
    errorCount: 2,
    warnings: ['High memory usage detected', 'Slow processing for RSI calculation'],
    parameters: {
      symbol: 'EURUSD',
      timeframe: '1h',
      startDate: '2024-01-01',
      endDate: '2024-01-15',
      indicators: ['SMA', 'EMA', 'RSI', 'MACD'],
    },
    priority: 7,
    retryCount: 0,
    maxRetries: 3,
    description: 'Generate technical indicators for EURUSD hourly data',
    tags: ['feature-engineering', 'eurusd', 'technical-indicators'],
    owner: 'ml-service',
  };

  const mockPipelineMetrics: PipelineMetrics = {
    timestamp: new Date('2024-01-15T10:30:00Z'),
    queue: {
      totalJobs: 25,
      runningJobs: 3,
      pendingJobs: 15,
      completedJobs: 150,
      failedJobs: 7,
      queueLength: 15,
      avgWaitTime: 300000, // 5 minutes
    },
    performance: {
      throughput: 12.5, // jobs per hour
      avgJobDuration: 1800000, // 30 minutes
      successRate: 95.5,
      failureRate: 4.5,
      retryRate: 8.2,
    },
    resources: {
      cpuUsage: 65.8,
      memoryUsage: 8589934592, // 8GB
      diskUsage: 21474836480, // 20GB
      networkUsage: 1048576, // 1MB/s
    },
    recentJobs: [mockPipelineJob],
    failedJobs: [],
  };

  beforeEach(() => {
    mockEventBus = new MockEventEmitter();
    pipelineService = new PipelineService({
      eventBus: mockEventBus,
      websocket: mockWebSocket as any,
      apiBaseUrl: 'http://localhost:8000/api',
    });

    jest.clearAllMocks();
    mockFetch.mockClear();
  });

  afterEach(() => {
    pipelineService.destroy();
  });

  describe('Pipeline Job Management', () => {
    it('should get all pipeline jobs', async () => {
      const jobs = [mockPipelineJob];
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => jobs,
      });

      const result = await pipelineService.getJobs();

      expect(result).toEqual(jobs);
      expect(mockFetch).toHaveBeenCalledWith('http://localhost:8000/api/pipeline/jobs');
    });

    it('should get pipeline jobs with filtering', async () => {
      const filteredJobs = [mockPipelineJob];
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => filteredJobs,
      });

      const result = await pipelineService.getJobs({
        status: PipelineJobStatus.RUNNING,
        type: PipelineJobType.FEATURE_ENGINEERING,
        limit: 10,
      });

      expect(result).toEqual(filteredJobs);
      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/pipeline/jobs?status=running&type=feature_engineering&limit=10'
      );
    });

    it('should get specific pipeline job by ID', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockPipelineJob,
      });

      const result = await pipelineService.getJob('job-12345');

      expect(result).toEqual(mockPipelineJob);
      expect(mockFetch).toHaveBeenCalledWith('http://localhost:8000/api/pipeline/jobs/job-12345');
    });

    it('should return null for non-existent job', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 404,
      });

      const result = await pipelineService.getJob('non-existent');

      expect(result).toBeNull();
    });

    it('should create new pipeline job', async () => {
      const newJobData = {
        name: 'GBPUSD ML Training',
        type: PipelineJobType.ML_TRAINING,
        parameters: {
          symbol: 'GBPUSD',
          model: 'RandomForest',
          features: ['SMA', 'EMA', 'RSI'],
        },
        priority: 8,
        description: 'Train ML model for GBPUSD trading signals',
        tags: ['ml-training', 'gbpusd'],
      };

      const createdJob = {
        id: 'job-67890',
        ...newJobData,
        status: PipelineJobStatus.PENDING,
        createdAt: new Date(),
        progress: 0,
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => createdJob,
      });

      const result = await pipelineService.createJob(newJobData);

      expect(result).toEqual(createdJob);
      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/pipeline/jobs',
        expect.objectContaining({
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            ...newJobData,
            maxRetries: 3,
          }),
        })
      );
    });

    it('should cancel running job', async () => {
      const cancelledJob = {
        ...mockPipelineJob,
        status: PipelineJobStatus.CANCELLED,
        completedAt: new Date(),
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => cancelledJob,
      });

      const result = await pipelineService.cancelJob('job-12345');

      expect(result).toEqual(cancelledJob);
      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/pipeline/jobs/job-12345/cancel',
        expect.objectContaining({
          method: 'POST',
        })
      );
    });

    it('should retry failed job', async () => {
      const retriedJob = {
        ...mockPipelineJob,
        status: PipelineJobStatus.PENDING,
        retryCount: 1,
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => retriedJob,
      });

      const result = await pipelineService.retryJob('job-12345');

      expect(result).toEqual(retriedJob);
      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/pipeline/jobs/job-12345/retry',
        expect.objectContaining({
          method: 'POST',
        })
      );
    });

    it('should delete completed job', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
      });

      const result = await pipelineService.deleteJob('job-12345');

      expect(result).toBe(true);
      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/pipeline/jobs/job-12345',
        expect.objectContaining({
          method: 'DELETE',
        })
      );
    });
  });

  describe('Pipeline Metrics and Monitoring', () => {
    it('should get current pipeline metrics', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockPipelineMetrics,
      });

      const result = await pipelineService.getMetrics();

      expect(result).toEqual(mockPipelineMetrics);
      expect(mockFetch).toHaveBeenCalledWith('http://localhost:8000/api/pipeline/metrics');
    });

    it('should get historical pipeline metrics', async () => {
      const historicalData = [
        {
          timestamp: new Date('2024-01-15T10:00:00Z').toISOString(),
          throughput: 10.2,
          avgJobDuration: 1950000,
          successRate: 94.1,
          cpuUsage: 72.3,
        },
        {
          timestamp: new Date('2024-01-15T10:30:00Z').toISOString(),
          throughput: 12.5,
          avgJobDuration: 1800000,
          successRate: 95.5,
          cpuUsage: 65.8,
        },
      ];

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => historicalData,
      });

      const result = await pipelineService.getHistoricalMetrics({
        start: new Date('2024-01-15T10:00:00Z'),
        end: new Date('2024-01-15T11:00:00Z'),
        interval: '30m',
      });

      expect(result).toEqual(historicalData);
      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/pipeline/metrics/history?start=2024-01-15T10%3A00%3A00.000Z&end=2024-01-15T11%3A00%3A00.000Z&interval=30m'
      );
    });

    it('should get job execution statistics', async () => {
      const stats = {
        totalJobs: 500,
        completedJobs: 475,
        failedJobs: 25,
        avgDuration: 1800000, // 30 minutes
        successRate: 95.0,
        byType: {
          [PipelineJobType.FEATURE_ENGINEERING]: { count: 200, successRate: 97.5 },
          [PipelineJobType.ML_TRAINING]: { count: 150, successRate: 94.0 },
          [PipelineJobType.DATA_INGESTION]: { count: 100, successRate: 99.0 },
          [PipelineJobType.DATA_VALIDATION]: { count: 50, successRate: 96.0 },
        },
        byOwner: {
          'ml-service': { count: 300, successRate: 96.0 },
          'data-pipeline': { count: 200, successRate: 94.0 },
        },
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => stats,
      });

      const result = await pipelineService.getJobStatistics({
        period: '30d',
        groupBy: ['type', 'owner'],
      });

      expect(result).toEqual(stats);
      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/pipeline/jobs/statistics?period=30d&groupBy=type%2Cowner'
      );
    });
  });

  describe('Pipeline Queue Management', () => {
    it('should get job queue status', async () => {
      const queueStatus = {
        totalJobs: 25,
        runningJobs: 3,
        pendingJobs: 15,
        queuedJobs: 7,
        priorityQueues: {
          high: 3,
          normal: 10,
          low: 2,
        },
        estimatedWaitTime: {
          high: 180000, // 3 minutes
          normal: 600000, // 10 minutes
          low: 1800000, // 30 minutes
        },
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => queueStatus,
      });

      const result = await pipelineService.getQueueStatus();

      expect(result).toEqual(queueStatus);
      expect(mockFetch).toHaveBeenCalledWith('http://localhost:8000/api/pipeline/queue/status');
    });

    it('should pause job queue', async () => {
      const pauseResult = {
        success: true,
        message: 'Job queue paused successfully',
        pausedAt: new Date().toISOString(),
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => pauseResult,
      });

      const result = await pipelineService.pauseQueue();

      expect(result).toEqual(pauseResult);
      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/pipeline/queue/pause',
        expect.objectContaining({
          method: 'POST',
        })
      );
    });

    it('should resume job queue', async () => {
      const resumeResult = {
        success: true,
        message: 'Job queue resumed successfully',
        resumedAt: new Date().toISOString(),
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => resumeResult,
      });

      const result = await pipelineService.resumeQueue();

      expect(result).toEqual(resumeResult);
      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/pipeline/queue/resume',
        expect.objectContaining({
          method: 'POST',
        })
      );
    });

    it('should clear completed jobs from queue', async () => {
      const clearResult = {
        success: true,
        removedJobs: 45,
        message: '45 completed jobs removed from queue',
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => clearResult,
      });

      const result = await pipelineService.clearCompletedJobs();

      expect(result).toEqual(clearResult);
      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/pipeline/queue/clear-completed',
        expect.objectContaining({
          method: 'POST',
        })
      );
    });
  });

  describe('Pipeline Templates and Workflows', () => {
    it('should get available job templates', async () => {
      const templates = [
        {
          id: 'feature-engineering-template',
          name: 'Feature Engineering',
          description: 'Generate technical indicators and features',
          type: PipelineJobType.FEATURE_ENGINEERING,
          parameters: {
            symbol: { type: 'string', required: true },
            timeframe: { type: 'string', default: '1h' },
            indicators: { type: 'array', default: ['SMA', 'EMA', 'RSI'] },
          },
          estimatedDuration: 1800000,
          tags: ['feature-engineering', 'technical-indicators'],
        },
        {
          id: 'ml-training-template',
          name: 'ML Model Training',
          description: 'Train machine learning models',
          type: PipelineJobType.ML_TRAINING,
          parameters: {
            symbol: { type: 'string', required: true },
            model: { type: 'string', default: 'RandomForest' },
            features: { type: 'array', required: true },
          },
          estimatedDuration: 3600000,
          tags: ['ml-training', 'model'],
        },
      ];

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => templates,
      });

      const result = await pipelineService.getJobTemplates();

      expect(result).toEqual(templates);
      expect(mockFetch).toHaveBeenCalledWith('http://localhost:8000/api/pipeline/templates');
    });

    it('should create job from template', async () => {
      const templateParams = {
        symbol: 'EURUSD',
        timeframe: '1h',
        indicators: ['SMA', 'EMA', 'RSI', 'MACD'],
      };

      const createdJob = {
        ...mockPipelineJob,
        id: 'job-template-123',
        parameters: templateParams,
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => createdJob,
      });

      const result = await pipelineService.createJobFromTemplate('feature-engineering-template', templateParams);

      expect(result).toEqual(createdJob);
      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/pipeline/templates/feature-engineering-template/create-job',
        expect.objectContaining({
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(templateParams),
        })
      );
    });

    it('should get pipeline workflows', async () => {
      const workflows = [
        {
          id: 'eurusd-training-workflow',
          name: 'EURUSD Model Training Workflow',
          description: 'Complete workflow for EURUSD model training',
          steps: [
            { order: 1, template: 'data-ingestion-template', parameters: { symbol: 'EURUSD' } },
            { order: 2, template: 'feature-engineering-template', parameters: { symbol: 'EURUSD' } },
            { order: 3, template: 'ml-training-template', parameters: { symbol: 'EURUSD' } },
          ],
          schedule: '0 2 * * *', // Daily at 2 AM
          enabled: true,
          lastRun: new Date('2024-01-15T02:00:00Z').toISOString(),
          nextRun: new Date('2024-01-16T02:00:00Z').toISOString(),
        },
      ];

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => workflows,
      });

      const result = await pipelineService.getWorkflows();

      expect(result).toEqual(workflows);
      expect(mockFetch).toHaveBeenCalledWith('http://localhost:8000/api/pipeline/workflows');
    });

    it('should execute workflow', async () => {
      const workflowExecution = {
        workflowId: 'eurusd-training-workflow',
        executionId: 'exec-12345',
        status: 'running',
        startedAt: new Date().toISOString(),
        steps: [
          { order: 1, jobId: 'job-1', status: 'completed' },
          { order: 2, jobId: 'job-2', status: 'running' },
          { order: 3, jobId: null, status: 'pending' },
        ],
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => workflowExecution,
      });

      const result = await pipelineService.executeWorkflow('eurusd-training-workflow');

      expect(result).toEqual(workflowExecution);
      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/pipeline/workflows/eurusd-training-workflow/execute',
        expect.objectContaining({
          method: 'POST',
        })
      );
    });
  });

  describe('Real-time Updates and Events', () => {
    it('should emit job status change events', () => {
      const statusSpy = jest.fn();
      mockEventBus.on('pipeline:jobStatusChanged', statusSpy);

      const statusUpdate = {
        jobId: 'job-12345',
        oldStatus: PipelineJobStatus.RUNNING,
        newStatus: PipelineJobStatus.COMPLETED,
        timestamp: new Date(),
      };

      pipelineService.emitJobStatusChange(statusUpdate);

      expect(statusSpy).toHaveBeenCalledWith(statusUpdate);
    });

    it('should emit job progress updates', () => {
      const progressSpy = jest.fn();
      mockEventBus.on('pipeline:jobProgress', progressSpy);

      const progressUpdate = {
        jobId: 'job-12345',
        progress: 85,
        currentStep: 'Final calculations',
        estimatedTimeRemaining: 300000, // 5 minutes
        timestamp: new Date(),
      };

      pipelineService.emitJobProgress(progressUpdate);

      expect(progressSpy).toHaveBeenCalledWith(progressUpdate);
    });

    it('should send real-time updates over WebSocket', () => {
      const update = {
        type: 'job_status',
        jobId: 'job-12345',
        status: PipelineJobStatus.COMPLETED,
        progress: 100,
      };

      pipelineService.sendRealtimeUpdate(update);

      expect(mockWebSocket.send).toHaveBeenCalledTimes(1);

      const sentMessage = mockWebSocket.send.mock.calls[0][0];
      const parsedMessage = JSON.parse(sentMessage);

      expect(parsedMessage.type).toBe('pipeline:update');
      expect(parsedMessage.data.type).toBe('job_status');
      expect(parsedMessage.data.jobId).toBe('job-12345');
      expect(parsedMessage.data.status).toBe(PipelineJobStatus.COMPLETED);
    });

    it('should handle WebSocket connection errors gracefully', () => {
      const errorWebSocket = {
        ...mockWebSocket,
        readyState: WebSocket.CLOSED,
        send: jest.fn(() => {
          throw new Error('WebSocket connection closed');
        }),
      };

      const serviceWithError = new PipelineService({
        eventBus: mockEventBus,
        websocket: errorWebSocket as any,
        apiBaseUrl: 'http://localhost:8000/api',
      });

      expect(() => {
        serviceWithError.sendRealtimeUpdate({
          type: 'job_status',
          jobId: 'job-12345',
          status: PipelineJobStatus.COMPLETED,
        });
      }).not.toThrow();

      serviceWithError.destroy();
    });
  });

  describe('Performance Monitoring', () => {
    it('should start periodic pipeline monitoring', () => {
      jest.useFakeTimers();

      const metricsSpy = jest.spyOn(pipelineService, 'getMetrics').mockResolvedValue(mockPipelineMetrics);

      pipelineService.startPeriodicMonitoring(15000); // 15 seconds for testing

      // Fast forward time
      jest.advanceTimersByTime(15000);

      expect(metricsSpy).toHaveBeenCalled();

      pipelineService.stopPeriodicMonitoring();
      metricsSpy.mockRestore();
      jest.useRealTimers();
    });

    it('should calculate pipeline health score', () => {
      const metrics = {
        successRate: 95.5,
        avgJobDuration: 1800000, // 30 minutes
        queueLength: 5,
        cpuUsage: 65.8,
        memoryUsage: 0.8, // 80% of available
      };

      const healthScore = pipelineService.calculateHealthScore(metrics);

      expect(healthScore).toBeGreaterThan(80);
      expect(healthScore).toBeLessThanOrEqual(100);
    });

    it('should get pipeline performance summary', () => {
      pipelineService['lastMetrics'] = mockPipelineMetrics;

      const summary = pipelineService.getPerformanceSummary();

      expect(summary).toEqual({
        throughput: 12.5,
        successRate: 95.5,
        avgJobDuration: 1800000,
        queueLength: 15,
        runningJobs: 3,
        failedJobs: 7,
        healthScore: expect.any(Number),
        status: expect.any(String),
      });
    });
  });

  describe('Error Handling', () => {
    it('should handle API errors gracefully', async () => {
      mockFetch.mockRejectedValueOnce(new Error('Network error'));

      await expect(pipelineService.getJobs()).rejects.toThrow('Network error');
    });

    it('should handle HTTP error responses', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        statusText: 'Internal Server Error',
      });

      await expect(pipelineService.getJobs()).rejects.toThrow('HTTP error! status: 500');
    });

    it('should handle malformed API responses', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => {
          throw new Error('Invalid JSON');
        },
      });

      await expect(pipelineService.getJobs()).rejects.toThrow('Invalid JSON');
    });
  });
});
