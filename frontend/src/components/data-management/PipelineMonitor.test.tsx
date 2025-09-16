/**
 * PipelineMonitor Component Tests
 *
 * Tests for real-time ML/ETL pipeline job monitoring and status tracking
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { PipelineMonitor } from './PipelineMonitor';
import { PipelineService } from '@/services/pipeline';
import { NotificationService } from '@/services/notification';
import { Pipeline, PipelineJob, PipelineStatus, JobStatus, JobType } from '@/types/dataManagement';

// Mock services
jest.mock('@/services/pipeline');
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
  BarChart: ({ children }: any) => <div data-testid="bar-chart">{children}</div>,
  Bar: ({ dataKey }: any) => <div data-testid={`bar-${dataKey}`} />,
  ReferenceLine: ({ y }: any) => <div data-testid={`reference-line-${y}`} />,
}));

const mockPipelineService = PipelineService as jest.MockedClass<typeof PipelineService>;
const mockNotificationService = NotificationService as jest.MockedClass<typeof NotificationService>;

// Mock data
const mockPipelines: Pipeline[] = [
  {
    id: 'ml-training-pipeline',
    name: 'ML Model Training',
    description: 'Automated ML model training and validation pipeline',
    type: 'ml_training',
    status: PipelineStatus.ACTIVE,
    schedule: '0 2 * * *', // Daily at 2 AM
    enabled: true,
    lastRun: new Date('2024-01-15T02:00:00Z'),
    nextRun: new Date('2024-01-16T02:00:00Z'),
    averageRuntime: 3600000, // 1 hour
    successRate: 95.5,
    totalRuns: 45,
    failedRuns: 2,
    createdAt: new Date('2024-01-01T00:00:00Z'),
    updatedAt: new Date('2024-01-15T02:30:00Z'),
    configuration: {
      dataSource: 'market_data',
      modelType: 'ensemble',
      features: ['technical_indicators', 'market_sentiment'],
      validationSplit: 0.2,
      hyperparameters: {
        learningRate: 0.01,
        epochs: 100,
        batchSize: 32,
      },
    },
  },
  {
    id: 'data-ingestion-pipeline',
    name: 'Market Data Ingestion',
    description: 'Real-time market data collection and preprocessing',
    type: 'data_ingestion',
    status: PipelineStatus.RUNNING,
    schedule: '*/5 * * * *', // Every 5 minutes
    enabled: true,
    lastRun: new Date('2024-01-15T10:25:00Z'),
    nextRun: new Date('2024-01-15T10:30:00Z'),
    averageRuntime: 180000, // 3 minutes
    successRate: 98.2,
    totalRuns: 2880,
    failedRuns: 52,
    createdAt: new Date('2024-01-01T00:00:00Z'),
    updatedAt: new Date('2024-01-15T10:25:00Z'),
    configuration: {
      dataSources: ['ib_tws', 'polygon', 'alpha_vantage'],
      symbols: ['EURUSD', 'GBPUSD', 'USDJPY'],
      timeframes: ['1m', '5m', '1h', '1d'],
      validation: true,
    },
  },
  {
    id: 'feature-engineering-pipeline',
    name: 'Feature Engineering',
    description: 'Calculate technical indicators and market features',
    type: 'feature_engineering',
    status: PipelineStatus.FAILED,
    schedule: '*/15 * * * *', // Every 15 minutes
    enabled: true,
    lastRun: new Date('2024-01-15T10:15:00Z'),
    nextRun: new Date('2024-01-15T10:30:00Z'),
    averageRuntime: 420000, // 7 minutes
    successRate: 89.3,
    totalRuns: 960,
    failedRuns: 103,
    createdAt: new Date('2024-01-01T00:00:00Z'),
    updatedAt: new Date('2024-01-15T10:15:00Z'),
    configuration: {
      indicators: ['sma', 'ema', 'rsi', 'macd', 'bollinger_bands'],
      lookbackPeriods: [20, 50, 200],
      timeframes: ['5m', '1h', '1d'],
    },
    lastError: {
      message: 'Database connection timeout during indicator calculation',
      timestamp: new Date('2024-01-15T10:18:00Z'),
      details: {
        error: 'ConnectionTimeoutError',
        query: 'SELECT * FROM market_data WHERE symbol = ? AND timestamp > ?',
        duration: 30000,
      },
    },
  },
];

const mockPipelineJobs: PipelineJob[] = [
  {
    id: 'job-001',
    pipelineId: 'ml-training-pipeline',
    status: JobStatus.RUNNING,
    type: JobType.ML_TRAINING,
    startTime: new Date('2024-01-15T10:00:00Z'),
    progress: 65.5,
    stage: 'model_validation',
    estimatedCompletion: new Date('2024-01-15T11:00:00Z'),
    processedRecords: 650000,
    totalRecords: 1000000,
    metrics: {
      accuracy: 0.892,
      precision: 0.887,
      recall: 0.895,
      f1Score: 0.891,
      loss: 0.245,
    },
    resourceUsage: {
      cpu: 78.5,
      memory: 4.2,
      gpu: 92.1,
      disk: 156.8,
    },
    logs: [
      {
        timestamp: new Date('2024-01-15T10:00:00Z'),
        level: 'info',
        message: 'Starting ML training pipeline',
        component: 'pipeline_orchestrator',
      },
      {
        timestamp: new Date('2024-01-15T10:15:00Z'),
        level: 'info',
        message: 'Data preprocessing completed (500,000 records)',
        component: 'data_preprocessor',
      },
      {
        timestamp: new Date('2024-01-15T10:30:00Z'),
        level: 'info',
        message: 'Model training started with ensemble method',
        component: 'model_trainer',
      },
    ],
  },
  {
    id: 'job-002',
    pipelineId: 'data-ingestion-pipeline',
    status: JobStatus.COMPLETED,
    type: JobType.DATA_INGESTION,
    startTime: new Date('2024-01-15T10:25:00Z'),
    endTime: new Date('2024-01-15T10:28:00Z'),
    progress: 100,
    stage: 'data_validation',
    duration: 180000, // 3 minutes
    processedRecords: 1250,
    totalRecords: 1250,
    metrics: {
      recordsIngested: 1250,
      recordsValidated: 1238,
      recordsRejected: 12,
      duplicatesFound: 3,
      validationErrors: 9,
    },
    resourceUsage: {
      cpu: 25.3,
      memory: 1.8,
      network: 45.2,
      disk: 32.1,
    },
  },
  {
    id: 'job-003',
    pipelineId: 'feature-engineering-pipeline',
    status: JobStatus.FAILED,
    type: JobType.FEATURE_ENGINEERING,
    startTime: new Date('2024-01-15T10:15:00Z'),
    endTime: new Date('2024-01-15T10:18:00Z'),
    progress: 35,
    stage: 'indicator_calculation',
    duration: 180000,
    processedRecords: 175000,
    totalRecords: 500000,
    error: {
      message: 'Database connection timeout during indicator calculation',
      code: 'DB_TIMEOUT',
      timestamp: new Date('2024-01-15T10:18:00Z'),
      stack: 'ConnectionTimeoutError: Connection timed out after 30000ms...',
      retryable: true,
    },
    resourceUsage: {
      cpu: 45.2,
      memory: 2.1,
      disk: 89.3,
    },
  },
];

const mockJobHistory = [
  {
    timestamp: '2024-01-15T09:00:00Z',
    completed: 8,
    failed: 1,
    running: 2,
    queued: 0,
    avgDuration: 285,
    successRate: 88.9,
  },
  {
    timestamp: '2024-01-15T09:30:00Z',
    completed: 12,
    failed: 0,
    running: 3,
    queued: 1,
    avgDuration: 245,
    successRate: 100.0,
  },
  {
    timestamp: '2024-01-15T10:00:00Z',
    completed: 15,
    failed: 2,
    running: 1,
    queued: 0,
    avgDuration: 312,
    successRate: 88.2,
  },
];

describe('PipelineMonitor', () => {
  let mockPipelineServiceInstance: jest.Mocked<PipelineService>;
  let mockNotificationServiceInstance: jest.Mocked<NotificationService>;

  beforeEach(() => {
    mockPipelineServiceInstance = {
      getPipelines: jest.fn(),
      getPipeline: jest.fn(),
      createPipeline: jest.fn(),
      updatePipeline: jest.fn(),
      deletePipeline: jest.fn(),
      startPipeline: jest.fn(),
      stopPipeline: jest.fn(),
      getPipelineJobs: jest.fn(),
      getJobHistory: jest.fn(),
      getJobLogs: jest.fn(),
      cancelJob: jest.fn(),
      retryJob: jest.fn(),
      getPipelineMetrics: jest.fn(),
      getResourceUsage: jest.fn(),
      subscribeToUpdates: jest.fn(),
      unsubscribeFromUpdates: jest.fn(),
      exportLogs: jest.fn(),
      destroy: jest.fn(),
    } as any;

    mockNotificationServiceInstance = {
      create: jest.fn(),
      getAll: jest.fn(),
      dismiss: jest.fn(),
      markAsRead: jest.fn(),
      destroy: jest.fn(),
    } as any;

    mockPipelineService.mockImplementation(() => mockPipelineServiceInstance);
    mockNotificationService.mockImplementation(() => mockNotificationServiceInstance);

    jest.clearAllMocks();
  });

  describe('Component Rendering', () => {
    it('should render pipeline monitor with loading state initially', () => {
      mockPipelineServiceInstance.getPipelines.mockResolvedValue(mockPipelines);
      mockPipelineServiceInstance.getPipelineJobs.mockResolvedValue(mockPipelineJobs);

      render(<PipelineMonitor />);

      expect(screen.getByText('Pipeline Monitor')).toBeInTheDocument();
      expect(screen.getByText('Loading...')).toBeInTheDocument();
    });

    it('should render pipeline overview after loading', async () => {
      mockPipelineServiceInstance.getPipelines.mockResolvedValue(mockPipelines);
      mockPipelineServiceInstance.getPipelineJobs.mockResolvedValue(mockPipelineJobs);
      mockPipelineServiceInstance.getJobHistory.mockResolvedValue(mockJobHistory);

      render(<PipelineMonitor />);

      await waitFor(() => {
        expect(screen.getByText('Pipeline Overview')).toBeInTheDocument();
        expect(screen.getByText('Active Jobs')).toBeInTheDocument();
        expect(screen.getByText('Job History')).toBeInTheDocument();
      });
    });

    it('should display pipeline status correctly', async () => {
      mockPipelineServiceInstance.getPipelines.mockResolvedValue(mockPipelines);
      mockPipelineServiceInstance.getPipelineJobs.mockResolvedValue(mockPipelineJobs);

      render(<PipelineMonitor />);

      await waitFor(() => {
        expect(screen.getByTestId('pipeline-ml-training-pipeline')).toBeInTheDocument();
        expect(screen.getByTestId('pipeline-data-ingestion-pipeline')).toBeInTheDocument();
        expect(screen.getByTestId('pipeline-feature-engineering-pipeline')).toBeInTheDocument();
      });

      expect(screen.getByText('ML Model Training')).toBeInTheDocument();
      expect(screen.getByText('Market Data Ingestion')).toBeInTheDocument();
      expect(screen.getByText('Feature Engineering')).toBeInTheDocument();
    });

    it('should display job statuses with correct indicators', async () => {
      mockPipelineServiceInstance.getPipelines.mockResolvedValue(mockPipelines);
      mockPipelineServiceInstance.getPipelineJobs.mockResolvedValue(mockPipelineJobs);

      render(<PipelineMonitor />);

      await waitFor(() => {
        expect(screen.getByTestId('job-job-001')).toBeInTheDocument();
        expect(screen.getByTestId('job-job-002')).toBeInTheDocument();
        expect(screen.getByTestId('job-job-003')).toBeInTheDocument();
      });

      // Check job status indicators
      expect(screen.getByTestId('job-status-running')).toBeInTheDocument();
      expect(screen.getByTestId('job-status-completed')).toBeInTheDocument();
      expect(screen.getByTestId('job-status-failed')).toBeInTheDocument();
    });

    it('should render job history chart', async () => {
      mockPipelineServiceInstance.getPipelines.mockResolvedValue(mockPipelines);
      mockPipelineServiceInstance.getPipelineJobs.mockResolvedValue(mockPipelineJobs);
      mockPipelineServiceInstance.getJobHistory.mockResolvedValue(mockJobHistory);

      render(<PipelineMonitor />);

      await waitFor(() => {
        expect(screen.getByTestId('job-history-chart')).toBeInTheDocument();
        expect(screen.getByTestId('line-chart')).toBeInTheDocument();
        expect(screen.getByTestId('line-completed')).toBeInTheDocument();
        expect(screen.getByTestId('line-failed')).toBeInTheDocument();
      });
    });

    it('should render resource usage chart for running jobs', async () => {
      mockPipelineServiceInstance.getPipelines.mockResolvedValue(mockPipelines);
      mockPipelineServiceInstance.getPipelineJobs.mockResolvedValue(mockPipelineJobs);

      render(<PipelineMonitor />);

      await waitFor(() => {
        expect(screen.getByTestId('resource-usage-chart')).toBeInTheDocument();
        expect(screen.getByTestId('bar-chart')).toBeInTheDocument();
        expect(screen.getByTestId('bar-cpu')).toBeInTheDocument();
        expect(screen.getByTestId('bar-memory')).toBeInTheDocument();
      });
    });
  });

  describe('Interactive Features', () => {
    it('should allow filtering pipelines by status', async () => {
      mockPipelineServiceInstance.getPipelines.mockResolvedValue(mockPipelines);
      mockPipelineServiceInstance.getPipelineJobs.mockResolvedValue(mockPipelineJobs);

      render(<PipelineMonitor />);

      await waitFor(() => {
        expect(screen.getByLabelText('Filter by status')).toBeInTheDocument();
      });

      // Filter to show only failed pipelines
      const statusFilter = screen.getByLabelText('Filter by status');
      await userEvent.selectOptions(statusFilter, 'failed');

      await waitFor(() => {
        expect(screen.getByTestId('pipeline-feature-engineering-pipeline')).toBeInTheDocument();
        expect(screen.queryByTestId('pipeline-ml-training-pipeline')).not.toBeInTheDocument();
        expect(screen.queryByTestId('pipeline-data-ingestion-pipeline')).not.toBeInTheDocument();
      });
    });

    it('should allow filtering pipelines by type', async () => {
      mockPipelineServiceInstance.getPipelines.mockResolvedValue(mockPipelines);
      mockPipelineServiceInstance.getPipelineJobs.mockResolvedValue(mockPipelineJobs);

      render(<PipelineMonitor />);

      await waitFor(() => {
        expect(screen.getByLabelText('Filter by type')).toBeInTheDocument();
      });

      // Filter to show only ML training pipelines
      const typeFilter = screen.getByLabelText('Filter by type');
      await userEvent.selectOptions(typeFilter, 'ml_training');

      await waitFor(() => {
        expect(screen.getByTestId('pipeline-ml-training-pipeline')).toBeInTheDocument();
        expect(screen.queryByTestId('pipeline-data-ingestion-pipeline')).not.toBeInTheDocument();
        expect(screen.queryByTestId('pipeline-feature-engineering-pipeline')).not.toBeInTheDocument();
      });
    });

    it('should show job details when job card is clicked', async () => {
      mockPipelineServiceInstance.getPipelines.mockResolvedValue(mockPipelines);
      mockPipelineServiceInstance.getPipelineJobs.mockResolvedValue(mockPipelineJobs);
      mockPipelineServiceInstance.getJobLogs.mockResolvedValue(mockPipelineJobs[0].logs || []);

      render(<PipelineMonitor />);

      await waitFor(() => {
        expect(screen.getByTestId('job-job-001')).toBeInTheDocument();
      });

      // Click on running job to view details
      const jobCard = screen.getByTestId('job-job-001');
      await userEvent.click(jobCard);

      await waitFor(() => {
        expect(screen.getByText('Job Details')).toBeInTheDocument();
        expect(screen.getByText('Progress: 65.5%')).toBeInTheDocument();
        expect(screen.getByText('Stage: model_validation')).toBeInTheDocument();
        expect(screen.getByText('Processed: 650,000 / 1,000,000 records')).toBeInTheDocument();
      });
    });

    it('should display job logs in detail view', async () => {
      mockPipelineServiceInstance.getPipelines.mockResolvedValue(mockPipelines);
      mockPipelineServiceInstance.getPipelineJobs.mockResolvedValue(mockPipelineJobs);
      mockPipelineServiceInstance.getJobLogs.mockResolvedValue(mockPipelineJobs[0].logs || []);

      render(<PipelineMonitor />);

      await waitFor(() => {
        expect(screen.getByTestId('job-job-001')).toBeInTheDocument();
      });

      const jobCard = screen.getByTestId('job-job-001');
      await userEvent.click(jobCard);

      await waitFor(() => {
        expect(screen.getByText('Job Logs')).toBeInTheDocument();
        expect(screen.getByText('Starting ML training pipeline')).toBeInTheDocument();
        expect(screen.getByText('Data preprocessing completed')).toBeInTheDocument();
        expect(screen.getByText('Model training started with ensemble method')).toBeInTheDocument();
      });
    });

    it('should allow starting/stopping pipelines', async () => {
      mockPipelineServiceInstance.getPipelines.mockResolvedValue(mockPipelines);
      mockPipelineServiceInstance.getPipelineJobs.mockResolvedValue(mockPipelineJobs);
      mockPipelineServiceInstance.startPipeline.mockResolvedValue({ success: true });
      mockPipelineServiceInstance.stopPipeline.mockResolvedValue({ success: true });

      render(<PipelineMonitor />);

      await waitFor(() => {
        expect(screen.getByTestId('pipeline-feature-engineering-pipeline')).toBeInTheDocument();
      });

      // Start failed pipeline
      const startButton = screen.getByTestId('start-pipeline-feature-engineering-pipeline');
      await userEvent.click(startButton);

      expect(mockPipelineServiceInstance.startPipeline).toHaveBeenCalledWith('feature-engineering-pipeline');

      await waitFor(() => {
        expect(mockNotificationServiceInstance.create).toHaveBeenCalledWith({
          type: 'success',
          title: 'Pipeline Started',
          message: 'Feature Engineering pipeline has been started successfully',
        });
      });
    });

    it('should allow canceling running jobs', async () => {
      mockPipelineServiceInstance.getPipelines.mockResolvedValue(mockPipelines);
      mockPipelineServiceInstance.getPipelineJobs.mockResolvedValue(mockPipelineJobs);
      mockPipelineServiceInstance.cancelJob.mockResolvedValue({ success: true });

      render(<PipelineMonitor />);

      await waitFor(() => {
        expect(screen.getByTestId('job-job-001')).toBeInTheDocument();
      });

      const jobCard = screen.getByTestId('job-job-001');
      await userEvent.click(jobCard);

      await waitFor(() => {
        expect(screen.getByTestId('cancel-job-job-001')).toBeInTheDocument();
      });

      const cancelButton = screen.getByTestId('cancel-job-job-001');
      await userEvent.click(cancelButton);

      expect(mockPipelineServiceInstance.cancelJob).toHaveBeenCalledWith('job-001');

      await waitFor(() => {
        expect(mockNotificationServiceInstance.create).toHaveBeenCalledWith({
          type: 'success',
          title: 'Job Cancelled',
          message: 'Job job-001 has been cancelled successfully',
        });
      });
    });

    it('should allow retrying failed jobs', async () => {
      mockPipelineServiceInstance.getPipelines.mockResolvedValue(mockPipelines);
      mockPipelineServiceInstance.getPipelineJobs.mockResolvedValue(mockPipelineJobs);
      mockPipelineServiceInstance.retryJob.mockResolvedValue({ success: true, jobId: 'job-004' });

      render(<PipelineMonitor />);

      await waitFor(() => {
        expect(screen.getByTestId('job-job-003')).toBeInTheDocument();
      });

      const jobCard = screen.getByTestId('job-job-003');
      await userEvent.click(jobCard);

      await waitFor(() => {
        expect(screen.getByTestId('retry-job-job-003')).toBeInTheDocument();
      });

      const retryButton = screen.getByTestId('retry-job-job-003');
      await userEvent.click(retryButton);

      expect(mockPipelineServiceInstance.retryJob).toHaveBeenCalledWith('job-003');

      await waitFor(() => {
        expect(mockNotificationServiceInstance.create).toHaveBeenCalledWith({
          type: 'success',
          title: 'Job Retried',
          message: 'Job job-003 has been restarted as job-004',
        });
      });
    });
  });

  describe('Real-time Updates', () => {
    it('should auto-refresh pipeline status at specified intervals', async () => {
      jest.useFakeTimers();

      mockPipelineServiceInstance.getPipelines.mockResolvedValue(mockPipelines);
      mockPipelineServiceInstance.getPipelineJobs.mockResolvedValue(mockPipelineJobs);

      render(<PipelineMonitor refreshInterval={5000} />);

      // Initial load
      await waitFor(() => {
        expect(mockPipelineServiceInstance.getPipelines).toHaveBeenCalledTimes(1);
      });

      // Fast forward 5 seconds
      jest.advanceTimersByTime(5000);

      await waitFor(() => {
        expect(mockPipelineServiceInstance.getPipelines).toHaveBeenCalledTimes(2);
      });

      jest.useRealTimers();
    });

    it('should emit status change events', async () => {
      const onStatusChange = jest.fn();
      mockPipelineServiceInstance.getPipelines.mockResolvedValue(mockPipelines);
      mockPipelineServiceInstance.getPipelineJobs.mockResolvedValue(mockPipelineJobs);

      render(<PipelineMonitor onStatusChange={onStatusChange} />);

      await waitFor(() => {
        expect(onStatusChange).toHaveBeenCalledWith(
          expect.objectContaining({
            type: 'pipeline',
            activePipelines: 2,
            runningJobs: 1,
            failedJobs: 1,
            totalJobs: 3,
          })
        );
      });
    });
  });

  describe('Dashboard Integration', () => {
    it('should accept service instances as props', async () => {
      const customService = mockPipelineServiceInstance;
      customService.getPipelines.mockResolvedValue(mockPipelines);
      customService.getPipelineJobs.mockResolvedValue(mockPipelineJobs);

      render(<PipelineMonitor pipelineService={customService} />);

      await waitFor(() => {
        expect(customService.getPipelines).toHaveBeenCalled();
      });
    });

    it('should support grid positioning', async () => {
      mockPipelineServiceInstance.getPipelines.mockResolvedValue(mockPipelines);
      mockPipelineServiceInstance.getPipelineJobs.mockResolvedValue(mockPipelineJobs);

      render(<PipelineMonitor gridArea="pipeline-monitor" className="custom-grid-item" />);

      await waitFor(() => {
        const container = screen.getByTestId('pipeline-monitor');
        expect(container).toHaveClass('custom-grid-item');
        expect(container).toHaveStyle('grid-area: pipeline-monitor');
      });
    });
  });

  describe('Error Handling', () => {
    it('should display error message when pipelines fail to load', async () => {
      mockPipelineServiceInstance.getPipelines.mockRejectedValue(new Error('API error'));

      render(<PipelineMonitor />);

      await waitFor(() => {
        expect(screen.getByText('Error loading pipelines: API error')).toBeInTheDocument();
      });
    });

    it('should handle job cancellation errors gracefully', async () => {
      mockPipelineServiceInstance.getPipelines.mockResolvedValue(mockPipelines);
      mockPipelineServiceInstance.getPipelineJobs.mockResolvedValue(mockPipelineJobs);
      mockPipelineServiceInstance.cancelJob.mockRejectedValue(new Error('Cancellation failed'));

      render(<PipelineMonitor />);

      await waitFor(() => {
        expect(screen.getByTestId('job-job-001')).toBeInTheDocument();
      });

      const jobCard = screen.getByTestId('job-job-001');
      await userEvent.click(jobCard);

      await waitFor(() => {
        expect(screen.getByTestId('cancel-job-job-001')).toBeInTheDocument();
      });

      const cancelButton = screen.getByTestId('cancel-job-job-001');
      await userEvent.click(cancelButton);

      await waitFor(() => {
        expect(mockNotificationServiceInstance.create).toHaveBeenCalledWith({
          type: 'error',
          title: 'Job Cancellation Failed',
          message: 'Failed to cancel job job-001: Cancellation failed',
        });
      });
    });
  });

  describe('Accessibility', () => {
    it('should have proper ARIA labels and roles', async () => {
      mockPipelineServiceInstance.getPipelines.mockResolvedValue(mockPipelines);
      mockPipelineServiceInstance.getPipelineJobs.mockResolvedValue(mockPipelineJobs);

      render(<PipelineMonitor />);

      await waitFor(() => {
        expect(screen.getByRole('region', { name: 'Pipeline Monitor' })).toBeInTheDocument();
        expect(screen.getByLabelText('Filter by status')).toBeInTheDocument();
        expect(screen.getByLabelText('Filter by type')).toBeInTheDocument();
      });
    });

    it('should support keyboard navigation for job cards', async () => {
      mockPipelineServiceInstance.getPipelines.mockResolvedValue(mockPipelines);
      mockPipelineServiceInstance.getPipelineJobs.mockResolvedValue(mockPipelineJobs);

      render(<PipelineMonitor />);

      await waitFor(() => {
        expect(screen.getByTestId('job-job-001')).toBeInTheDocument();
      });

      // Tab to job card and press Enter
      const jobCard = screen.getByTestId('job-job-001');
      jobCard.focus();
      fireEvent.keyDown(jobCard, { key: 'Enter', code: 'Enter' });

      await waitFor(() => {
        expect(screen.getByText('Job Details')).toBeInTheDocument();
      });
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

      mockPipelineServiceInstance.getPipelines.mockResolvedValue(mockPipelines);
      mockPipelineServiceInstance.getPipelineJobs.mockResolvedValue(mockPipelineJobs);

      render(<PipelineMonitor />);

      await waitFor(() => {
        const container = screen.getByTestId('pipeline-monitor');
        expect(container).toHaveClass('mobile-layout');
      });
    });

    it('should stack charts vertically on small screens', async () => {
      Object.defineProperty(window, 'innerWidth', {
        writable: true,
        configurable: true,
        value: 640,
      });

      mockPipelineServiceInstance.getPipelines.mockResolvedValue(mockPipelines);
      mockPipelineServiceInstance.getPipelineJobs.mockResolvedValue(mockPipelineJobs);
      mockPipelineServiceInstance.getJobHistory.mockResolvedValue(mockJobHistory);

      render(<PipelineMonitor />);

      await waitFor(() => {
        const chartsContainer = screen.getByTestId('charts-container');
        expect(chartsContainer).toHaveClass('flex-col');
      });
    });
  });
});
