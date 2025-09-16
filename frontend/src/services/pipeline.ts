/**
 * PipelineService
 *
 * Service for ML/ETL pipeline monitoring and management
 */

import { EventEmitter } from 'events';
import { PipelineJob, PipelineJobStatus, PipelineJobType, PipelineMetrics } from '@/types/dataManagement';

export interface PipelineServiceConfig {
  eventBus: EventEmitter;
  websocket?: WebSocket;
  apiBaseUrl: string;
  monitoringInterval?: number;
}

export interface JobFilter {
  status?: PipelineJobStatus;
  type?: PipelineJobType;
  owner?: string;
  tags?: string[];
  priority?: number;
  limit?: number;
  offset?: number;
}

export interface JobCreateData {
  name: string;
  type: PipelineJobType;
  parameters: Record<string, any>;
  priority?: number;
  description?: string;
  tags?: string[];
  owner?: string;
  maxRetries?: number;
  parentJobId?: string;
}

export interface HistoricalMetricsQuery {
  start: Date;
  end: Date;
  interval: string; // e.g., '5m', '1h', '1d'
}

export interface HistoricalMetricsData {
  timestamp: string;
  throughput: number;
  avgJobDuration: number;
  successRate: number;
  cpuUsage: number;
  memoryUsage?: number;
  queueLength?: number;
}

export interface JobStatisticsQuery {
  period?: string; // e.g., '7d', '30d', '1y'
  groupBy?: string[]; // e.g., ['type', 'owner', 'status']
}

export interface JobStatistics {
  totalJobs: number;
  completedJobs: number;
  failedJobs: number;
  avgDuration: number;
  successRate: number;
  byType?: Record<string, { count: number; successRate: number }>;
  byOwner?: Record<string, { count: number; successRate: number }>;
  byStatus?: Record<string, number>;
}

export interface QueueStatus {
  totalJobs: number;
  runningJobs: number;
  pendingJobs: number;
  queuedJobs: number;
  priorityQueues: {
    high: number;
    normal: number;
    low: number;
  };
  estimatedWaitTime: {
    high: number; // milliseconds
    normal: number;
    low: number;
  };
}

export interface QueueOperation {
  success: boolean;
  message: string;
  pausedAt?: string;
  resumedAt?: string;
  removedJobs?: number;
}

export interface JobTemplate {
  id: string;
  name: string;
  description: string;
  type: PipelineJobType;
  parameters: Record<string, {
    type: string;
    required?: boolean;
    default?: any;
    description?: string;
  }>;
  estimatedDuration: number; // milliseconds
  tags: string[];
}

export interface Workflow {
  id: string;
  name: string;
  description: string;
  steps: Array<{
    order: number;
    template: string;
    parameters: Record<string, any>;
    dependsOn?: number[];
  }>;
  schedule?: string; // cron expression
  enabled: boolean;
  lastRun?: string;
  nextRun?: string;
  createdAt: string;
  updatedAt: string;
}

export interface WorkflowExecution {
  workflowId: string;
  executionId: string;
  status: 'running' | 'completed' | 'failed' | 'cancelled';
  startedAt: string;
  completedAt?: string;
  steps: Array<{
    order: number;
    jobId: string | null;
    status: 'pending' | 'running' | 'completed' | 'failed' | 'skipped';
    startedAt?: string;
    completedAt?: string;
    error?: string;
  }>;
}

export interface JobStatusChangeEvent {
  jobId: string;
  oldStatus: PipelineJobStatus;
  newStatus: PipelineJobStatus;
  timestamp: Date;
  reason?: string;
}

export interface JobProgressEvent {
  jobId: string;
  progress: number; // 0-100
  currentStep?: string;
  estimatedTimeRemaining?: number; // milliseconds
  timestamp: Date;
}

export interface RealtimePipelineUpdate {
  type: string;
  jobId?: string;
  status?: PipelineJobStatus;
  progress?: number;
  metrics?: Partial<PipelineMetrics>;
  [key: string]: any;
}

export interface PipelineHealthMetrics {
  successRate: number;
  avgJobDuration: number;
  queueLength: number;
  cpuUsage: number;
  memoryUsage: number; // 0-1 (percentage as decimal)
}

export interface PerformanceSummary {
  throughput: number; // jobs per hour
  successRate: number; // percentage
  avgJobDuration: number; // milliseconds
  queueLength: number;
  runningJobs: number;
  failedJobs: number;
  healthScore: number; // 0-100
  status: 'healthy' | 'warning' | 'critical';
}

export class PipelineService {
  private eventBus: EventEmitter;
  private websocket?: WebSocket;
  private config: PipelineServiceConfig;
  private monitoringTimer?: NodeJS.Timeout;
  private lastMetrics?: PipelineMetrics;

  constructor(config: PipelineServiceConfig) {
    this.config = {
      monitoringInterval: 30000, // 30 seconds default
      ...config,
    };

    this.eventBus = config.eventBus;
    this.websocket = config.websocket;
  }

  /**
   * Get pipeline jobs with optional filtering
   */
  async getJobs(filter: JobFilter = {}): Promise<PipelineJob[]> {
    const params = new URLSearchParams();

    if (filter.status) params.append('status', filter.status);
    if (filter.type) params.append('type', filter.type);
    if (filter.owner) params.append('owner', filter.owner);
    if (filter.tags) params.append('tags', filter.tags.join(','));
    if (filter.priority) params.append('priority', filter.priority.toString());
    if (filter.limit) params.append('limit', filter.limit.toString());
    if (filter.offset) params.append('offset', filter.offset.toString());

    const url = params.toString()
      ? `${this.config.apiBaseUrl}/pipeline/jobs?${params}`
      : `${this.config.apiBaseUrl}/pipeline/jobs`;

    const response = await fetch(url);

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return await response.json();
  }

  /**
   * Get specific pipeline job by ID
   */
  async getJob(jobId: string): Promise<PipelineJob | null> {
    const response = await fetch(`${this.config.apiBaseUrl}/pipeline/jobs/${jobId}`);

    if (!response.ok) {
      if (response.status === 404) {
        return null;
      }
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return await response.json();
  }

  /**
   * Create new pipeline job
   */
  async createJob(jobData: JobCreateData): Promise<PipelineJob> {
    const response = await fetch(`${this.config.apiBaseUrl}/pipeline/jobs`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        ...jobData,
        priority: jobData.priority || 5,
        maxRetries: jobData.maxRetries || 3,
        tags: jobData.tags || [],
      }),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const job = await response.json();

    // Emit job creation event
    this.eventBus.emit('pipeline:jobCreated', job);

    return job;
  }

  /**
   * Cancel running job
   */
  async cancelJob(jobId: string): Promise<PipelineJob> {
    const response = await fetch(`${this.config.apiBaseUrl}/pipeline/jobs/${jobId}/cancel`, {
      method: 'POST',
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const job = await response.json();

    // Emit status change event
    this.emitJobStatusChange({
      jobId,
      oldStatus: PipelineJobStatus.RUNNING,
      newStatus: PipelineJobStatus.CANCELLED,
      timestamp: new Date(),
      reason: 'User cancelled',
    });

    return job;
  }

  /**
   * Retry failed job
   */
  async retryJob(jobId: string): Promise<PipelineJob> {
    const response = await fetch(`${this.config.apiBaseUrl}/pipeline/jobs/${jobId}/retry`, {
      method: 'POST',
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const job = await response.json();

    // Emit status change event
    this.emitJobStatusChange({
      jobId,
      oldStatus: PipelineJobStatus.FAILED,
      newStatus: PipelineJobStatus.PENDING,
      timestamp: new Date(),
      reason: 'Manual retry',
    });

    return job;
  }

  /**
   * Delete completed job
   */
  async deleteJob(jobId: string): Promise<boolean> {
    const response = await fetch(`${this.config.apiBaseUrl}/pipeline/jobs/${jobId}`, {
      method: 'DELETE',
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    this.eventBus.emit('pipeline:jobDeleted', jobId);
    return true;
  }

  /**
   * Get current pipeline metrics
   */
  async getMetrics(): Promise<PipelineMetrics> {
    const response = await fetch(`${this.config.apiBaseUrl}/pipeline/metrics`);

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const metrics = await response.json();
    this.lastMetrics = metrics;
    return metrics;
  }

  /**
   * Get historical pipeline metrics
   */
  async getHistoricalMetrics(query: HistoricalMetricsQuery): Promise<HistoricalMetricsData[]> {
    const params = new URLSearchParams({
      start: query.start.toISOString(),
      end: query.end.toISOString(),
      interval: query.interval,
    });

    const response = await fetch(`${this.config.apiBaseUrl}/pipeline/metrics/history?${params}`);

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return await response.json();
  }

  /**
   * Get job execution statistics
   */
  async getJobStatistics(query: JobStatisticsQuery = {}): Promise<JobStatistics> {
    const params = new URLSearchParams();

    if (query.period) params.append('period', query.period);
    if (query.groupBy) params.append('groupBy', query.groupBy.join(','));

    const url = params.toString()
      ? `${this.config.apiBaseUrl}/pipeline/jobs/statistics?${params}`
      : `${this.config.apiBaseUrl}/pipeline/jobs/statistics`;

    const response = await fetch(url);

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return await response.json();
  }

  /**
   * Get job queue status
   */
  async getQueueStatus(): Promise<QueueStatus> {
    const response = await fetch(`${this.config.apiBaseUrl}/pipeline/queue/status`);

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return await response.json();
  }

  /**
   * Pause job queue
   */
  async pauseQueue(): Promise<QueueOperation> {
    const response = await fetch(`${this.config.apiBaseUrl}/pipeline/queue/pause`, {
      method: 'POST',
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const result = await response.json();
    this.eventBus.emit('pipeline:queuePaused', result);
    return result;
  }

  /**
   * Resume job queue
   */
  async resumeQueue(): Promise<QueueOperation> {
    const response = await fetch(`${this.config.apiBaseUrl}/pipeline/queue/resume`, {
      method: 'POST',
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const result = await response.json();
    this.eventBus.emit('pipeline:queueResumed', result);
    return result;
  }

  /**
   * Clear completed jobs from queue
   */
  async clearCompletedJobs(): Promise<QueueOperation> {
    const response = await fetch(`${this.config.apiBaseUrl}/pipeline/queue/clear-completed`, {
      method: 'POST',
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const result = await response.json();
    this.eventBus.emit('pipeline:queueCleared', result);
    return result;
  }

  /**
   * Get available job templates
   */
  async getJobTemplates(): Promise<JobTemplate[]> {
    const response = await fetch(`${this.config.apiBaseUrl}/pipeline/templates`);

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return await response.json();
  }

  /**
   * Create job from template
   */
  async createJobFromTemplate(templateId: string, parameters: Record<string, any>): Promise<PipelineJob> {
    const response = await fetch(`${this.config.apiBaseUrl}/pipeline/templates/${templateId}/create-job`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(parameters),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const job = await response.json();
    this.eventBus.emit('pipeline:jobCreated', job);
    return job;
  }

  /**
   * Get pipeline workflows
   */
  async getWorkflows(): Promise<Workflow[]> {
    const response = await fetch(`${this.config.apiBaseUrl}/pipeline/workflows`);

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return await response.json();
  }

  /**
   * Execute workflow
   */
  async executeWorkflow(workflowId: string): Promise<WorkflowExecution> {
    const response = await fetch(`${this.config.apiBaseUrl}/pipeline/workflows/${workflowId}/execute`, {
      method: 'POST',
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const execution = await response.json();
    this.eventBus.emit('pipeline:workflowExecuted', execution);
    return execution;
  }

  /**
   * Emit job status change event
   */
  emitJobStatusChange(event: JobStatusChangeEvent): void {
    this.eventBus.emit('pipeline:jobStatusChanged', event);
  }

  /**
   * Emit job progress event
   */
  emitJobProgress(event: JobProgressEvent): void {
    this.eventBus.emit('pipeline:jobProgress', event);
  }

  /**
   * Send real-time update over WebSocket
   */
  sendRealtimeUpdate(update: RealtimePipelineUpdate): void {
    if (!this.websocket || this.websocket.readyState !== WebSocket.OPEN) {
      return;
    }

    try {
      this.websocket.send(JSON.stringify({
        type: 'pipeline:update',
        data: {
          ...update,
          timestamp: new Date(),
        },
      }));
    } catch (error) {
      console.warn('Failed to send real-time pipeline update over WebSocket:', error);
    }
  }

  /**
   * Start periodic pipeline monitoring
   */
  startPeriodicMonitoring(interval?: number): void {
    const monitoringInterval = interval || this.config.monitoringInterval || 30000;

    this.monitoringTimer = setInterval(async () => {
      try {
        const metrics = await this.getMetrics();

        // Emit metrics update event
        this.eventBus.emit('pipeline:metricsUpdated', metrics);

        // Send real-time updates
        this.sendRealtimeUpdate({
          type: 'metrics',
          metrics: {
            queue: metrics.queue,
            performance: metrics.performance,
            resources: metrics.resources,
          },
        });

        // Check for performance issues and emit alerts
        const healthScore = this.calculateHealthScore({
          successRate: metrics.performance.successRate,
          avgJobDuration: metrics.performance.avgJobDuration,
          queueLength: metrics.queue.queueLength,
          cpuUsage: metrics.resources.cpuUsage,
          memoryUsage: (metrics.resources.memoryUsage / (16 * 1024 * 1024 * 1024)), // Assume 16GB total
        });

        if (healthScore < 70) {
          this.eventBus.emit('pipeline:healthAlert', {
            severity: healthScore < 50 ? 'critical' : 'warning',
            healthScore,
            metrics,
            timestamp: new Date(),
          });
        }

      } catch (error) {
        console.error('Failed to monitor pipeline:', error);
      }
    }, monitoringInterval);
  }

  /**
   * Stop periodic monitoring
   */
  stopPeriodicMonitoring(): void {
    if (this.monitoringTimer) {
      clearInterval(this.monitoringTimer);
      this.monitoringTimer = undefined;
    }
  }

  /**
   * Calculate pipeline health score
   */
  calculateHealthScore(metrics: PipelineHealthMetrics): number {
    // Weight factors for different metrics
    const weights = {
      successRate: 0.3,
      performance: 0.25,
      queueHealth: 0.2,
      resourceUsage: 0.25,
    };

    // Success rate score (0-100)
    const successScore = metrics.successRate;

    // Performance score based on job duration (assume 30 minutes is optimal)
    const optimalDuration = 1800000; // 30 minutes in milliseconds
    const performanceScore = Math.max(0, Math.min(100,
      100 - ((metrics.avgJobDuration - optimalDuration) / optimalDuration) * 50
    ));

    // Queue health score (lower queue length is better)
    const queueScore = Math.max(0, Math.min(100, 100 - (metrics.queueLength * 5)));

    // Resource usage score (optimal around 70% usage)
    const optimalUsage = 0.7;
    const avgResourceUsage = (metrics.cpuUsage / 100 + metrics.memoryUsage) / 2;
    const resourceScore = Math.max(0, Math.min(100,
      100 - Math.abs(avgResourceUsage - optimalUsage) * 200
    ));

    // Calculate weighted average
    const healthScore =
      successScore * weights.successRate +
      performanceScore * weights.performance +
      queueScore * weights.queueHealth +
      resourceScore * weights.resourceUsage;

    return Math.round(healthScore);
  }

  /**
   * Get performance summary
   */
  getPerformanceSummary(): PerformanceSummary | null {
    if (!this.lastMetrics) return null;

    const { queue, performance, resources } = this.lastMetrics;

    const healthScore = this.calculateHealthScore({
      successRate: performance.successRate,
      avgJobDuration: performance.avgJobDuration,
      queueLength: queue.queueLength,
      cpuUsage: resources.cpuUsage,
      memoryUsage: (resources.memoryUsage / (16 * 1024 * 1024 * 1024)), // Assume 16GB total
    });

    let status: 'healthy' | 'warning' | 'critical';
    if (healthScore >= 80) status = 'healthy';
    else if (healthScore >= 60) status = 'warning';
    else status = 'critical';

    return {
      throughput: performance.throughput,
      successRate: performance.successRate,
      avgJobDuration: performance.avgJobDuration,
      queueLength: queue.queueLength,
      runningJobs: queue.runningJobs,
      failedJobs: queue.failedJobs,
      healthScore,
      status,
    };
  }

  /**
   * Get jobs by status
   */
  async getJobsByStatus(status: PipelineJobStatus): Promise<PipelineJob[]> {
    return this.getJobs({ status });
  }

  /**
   * Get jobs by type
   */
  async getJobsByType(type: PipelineJobType): Promise<PipelineJob[]> {
    return this.getJobs({ type });
  }

  /**
   * Get running jobs
   */
  async getRunningJobs(): Promise<PipelineJob[]> {
    return this.getJobs({ status: PipelineJobStatus.RUNNING });
  }

  /**
   * Get failed jobs
   */
  async getFailedJobs(): Promise<PipelineJob[]> {
    return this.getJobs({ status: PipelineJobStatus.FAILED });
  }

  /**
   * Get last cached metrics
   */
  getLastMetrics(): PipelineMetrics | undefined {
    return this.lastMetrics;
  }

  /**
   * Clean up resources
   */
  destroy(): void {
    this.stopPeriodicMonitoring();
    this.lastMetrics = undefined;
    this.eventBus.removeAllListeners();
  }
}

// Singleton instance for global use
let globalPipelineService: PipelineService | null = null;

/**
 * Get or create global pipeline service instance
 */
export const getPipelineService = (config?: PipelineServiceConfig): PipelineService => {
  if (!globalPipelineService && config) {
    globalPipelineService = new PipelineService(config);
  }

  if (!globalPipelineService) {
    throw new Error('PipelineService not initialized. Call getPipelineService with config first.');
  }

  return globalPipelineService;
};
