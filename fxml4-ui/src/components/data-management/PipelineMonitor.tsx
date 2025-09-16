/**
 * PipelineMonitor Component
 *
 * Real-time monitoring dashboard for ML/ETL pipeline jobs and status tracking
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  BarChart,
  Bar,
  ReferenceLine,
} from 'recharts';
import { PipelineService } from '@/services/pipeline';
import { NotificationService } from '@/services/notification';
import {
  Pipeline,
  PipelineJob,
  PipelineStatus,
  JobStatus,
  JobType,
  DataManagementAlert,
  PipelineStatusEvent,
} from '@/types/dataManagement';

export interface PipelineMonitorProps {
  className?: string;
  gridArea?: string;
  refreshInterval?: number;
  autoRefresh?: boolean;

  // Dashboard integration props
  pipelineService?: PipelineService;
  notificationService?: NotificationService;
  onAlert?: (alert: DataManagementAlert) => void;
  onStatusChange?: (event: PipelineStatusEvent) => void;
}

interface JobHistoryPoint {
  timestamp: string;
  completed: number;
  failed: number;
  running: number;
  queued: number;
  avgDuration: number;
  successRate: number;
}

interface ResourceUsageData {
  jobId: string;
  jobName: string;
  cpu: number;
  memory: number;
  gpu?: number;
  disk: number;
}

export const PipelineMonitor: React.FC<PipelineMonitorProps> = ({
  className = '',
  gridArea,
  refreshInterval = 10000,
  autoRefresh = true,
  pipelineService,
  notificationService,
  onAlert,
  onStatusChange,
}) => {
  // State management
  const [pipelines, setPipelines] = useState<Pipeline[]>([]);
  const [jobs, setJobs] = useState<PipelineJob[]>([]);
  const [jobHistory, setJobHistory] = useState<JobHistoryPoint[]>([]);
  const [selectedJob, setSelectedJob] = useState<PipelineJob | null>(null);
  const [statusFilter, setStatusFilter] = useState<PipelineStatus | 'all'>('all');
  const [typeFilter, setTypeFilter] = useState<string>('all');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isMobile, setIsMobile] = useState(false);

  // Service instances
  const pipelineServiceRef = useMemo(
    () => pipelineService || new PipelineService(),
    [pipelineService]
  );
  const notificationServiceRef = useMemo(
    () => notificationService || new NotificationService(),
    [notificationService]
  );

  // Responsive design detection
  useEffect(() => {
    const checkScreenSize = () => {
      setIsMobile(window.innerWidth < 768);
    };

    checkScreenSize();
    window.addEventListener('resize', checkScreenSize);
    return () => window.removeEventListener('resize', checkScreenSize);
  }, []);

  // Load pipeline data
  const loadPipelineData = useCallback(async () => {
    try {
      setError(null);

      const [pipelinesData, jobsData, historyData] = await Promise.all([
        pipelineServiceRef.getPipelines(),
        pipelineServiceRef.getPipelineJobs(),
        pipelineServiceRef.getJobHistory({
          timeRange: '24h',
          interval: '30m'
        })
      ]);

      setPipelines(pipelinesData);
      setJobs(jobsData);
      setJobHistory(historyData);

      // Generate alerts for failed jobs
      const failedJobs = jobsData.filter(job => job.status === JobStatus.FAILED);
      if (failedJobs.length > 0 && onAlert) {
        onAlert({
          id: `pipeline-failures-${Date.now()}`,
          type: 'pipeline',
          severity: failedJobs.length > 3 ? 'critical' : 'warning',
          title: `Pipeline Job Failures Detected`,
          message: `${failedJobs.length} pipeline jobs have failed`,
          timestamp: new Date(),
          source: 'pipeline_monitor',
          data: {
            failedJobs: failedJobs.map(job => ({
              id: job.id,
              type: job.type,
              error: job.error?.message,
            })),
          },
        });
      }

      // Emit status change event
      if (onStatusChange) {
        const activePipelines = pipelinesData.filter(p => p.status !== PipelineStatus.INACTIVE).length;
        const runningJobs = jobsData.filter(job => job.status === JobStatus.RUNNING).length;
        const failedJobsCount = failedJobs.length;

        onStatusChange({
          type: 'pipeline',
          activePipelines,
          runningJobs,
          failedJobs: failedJobsCount,
          totalJobs: jobsData.length,
          timestamp: new Date(),
        });
      }

    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error';
      setError(`Error loading pipelines: ${errorMessage}`);
    } finally {
      setIsLoading(false);
    }
  }, [pipelineServiceRef, onAlert, onStatusChange]);

  // Auto-refresh effect
  useEffect(() => {
    loadPipelineData();

    if (autoRefresh && refreshInterval > 0) {
      const interval = setInterval(loadPipelineData, refreshInterval);
      return () => clearInterval(interval);
    }
  }, [loadPipelineData, autoRefresh, refreshInterval]);

  // Pipeline control actions
  const handleStartPipeline = useCallback(async (pipelineId: string) => {
    try {
      await pipelineServiceRef.startPipeline(pipelineId);
      const pipeline = pipelines.find(p => p.id === pipelineId);

      notificationServiceRef.create({
        type: 'success',
        title: 'Pipeline Started',
        message: `${pipeline?.name} pipeline has been started successfully`,
      });

      loadPipelineData();
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error';
      notificationServiceRef.create({
        type: 'error',
        title: 'Pipeline Start Failed',
        message: `Failed to start pipeline: ${errorMessage}`,
      });
    }
  }, [pipelineServiceRef, notificationServiceRef, pipelines, loadPipelineData]);

  const handleStopPipeline = useCallback(async (pipelineId: string) => {
    try {
      await pipelineServiceRef.stopPipeline(pipelineId);
      const pipeline = pipelines.find(p => p.id === pipelineId);

      notificationServiceRef.create({
        type: 'success',
        title: 'Pipeline Stopped',
        message: `${pipeline?.name} pipeline has been stopped successfully`,
      });

      loadPipelineData();
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error';
      notificationServiceRef.create({
        type: 'error',
        title: 'Pipeline Stop Failed',
        message: `Failed to stop pipeline: ${errorMessage}`,
      });
    }
  }, [pipelineServiceRef, notificationServiceRef, pipelines, loadPipelineData]);

  const handleCancelJob = useCallback(async (jobId: string) => {
    try {
      await pipelineServiceRef.cancelJob(jobId);

      notificationServiceRef.create({
        type: 'success',
        title: 'Job Cancelled',
        message: `Job ${jobId} has been cancelled successfully`,
      });

      loadPipelineData();
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error';
      notificationServiceRef.create({
        type: 'error',
        title: 'Job Cancellation Failed',
        message: `Failed to cancel job ${jobId}: ${errorMessage}`,
      });
    }
  }, [pipelineServiceRef, notificationServiceRef, loadPipelineData]);

  const handleRetryJob = useCallback(async (jobId: string) => {
    try {
      const result = await pipelineServiceRef.retryJob(jobId);

      notificationServiceRef.create({
        type: 'success',
        title: 'Job Retried',
        message: `Job ${jobId} has been restarted as ${result.jobId}`,
      });

      loadPipelineData();
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error';
      notificationServiceRef.create({
        type: 'error',
        title: 'Job Retry Failed',
        message: `Failed to retry job ${jobId}: ${errorMessage}`,
      });
    }
  }, [pipelineServiceRef, notificationServiceRef, loadPipelineData]);

  // Filtered data
  const filteredPipelines = useMemo(() => {
    return pipelines.filter(pipeline => {
      const statusMatch = statusFilter === 'all' || pipeline.status === statusFilter;
      const typeMatch = typeFilter === 'all' || pipeline.type === typeFilter;
      return statusMatch && typeMatch;
    });
  }, [pipelines, statusFilter, typeFilter]);

  // Resource usage data for chart
  const resourceUsageData = useMemo((): ResourceUsageData[] => {
    return jobs
      .filter(job => job.status === JobStatus.RUNNING && job.resourceUsage)
      .map(job => ({
        jobId: job.id,
        jobName: `${job.type}-${job.id.slice(-4)}`,
        cpu: job.resourceUsage!.cpu,
        memory: job.resourceUsage!.memory,
        gpu: job.resourceUsage!.gpu,
        disk: job.resourceUsage!.disk,
      }));
  }, [jobs]);

  // Status color mapping
  const getStatusColor = (status: PipelineStatus | JobStatus): string => {
    switch (status) {
      case PipelineStatus.ACTIVE:
      case JobStatus.RUNNING:
        return 'text-blue-600 bg-blue-100';
      case PipelineStatus.RUNNING:
      case JobStatus.QUEUED:
        return 'text-yellow-600 bg-yellow-100';
      case PipelineStatus.FAILED:
      case JobStatus.FAILED:
        return 'text-red-600 bg-red-100';
      case JobStatus.COMPLETED:
        return 'text-green-600 bg-green-100';
      case PipelineStatus.INACTIVE:
        return 'text-gray-600 bg-gray-100';
      default:
        return 'text-gray-600 bg-gray-100';
    }
  };

  const formatDuration = (milliseconds: number): string => {
    const seconds = Math.floor(milliseconds / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);

    if (hours > 0) return `${hours}h ${minutes % 60}m`;
    if (minutes > 0) return `${minutes}m ${seconds % 60}s`;
    return `${seconds}s`;
  };

  const formatBytes = (bytes: number): string => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  if (isLoading) {
    return (
      <div
        data-testid="pipeline-monitor"
        className={`p-6 bg-white rounded-lg shadow-sm border ${className}`}
        style={{ gridArea }}
      >
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold text-gray-900">Pipeline Monitor</h2>
        </div>
        <div className="flex items-center justify-center h-64">
          <div className="text-gray-500">Loading...</div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div
        data-testid="pipeline-monitor"
        className={`p-6 bg-white rounded-lg shadow-sm border ${className}`}
        style={{ gridArea }}
      >
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold text-gray-900">Pipeline Monitor</h2>
        </div>
        <div className="text-red-600 p-4 bg-red-50 rounded-lg">
          {error}
        </div>
      </div>
    );
  }

  return (
    <div
      data-testid="pipeline-monitor"
      className={`p-6 bg-white rounded-lg shadow-sm border ${className} ${
        isMobile ? 'mobile-layout' : ''
      }`}
      style={{ gridArea }}
      role="region"
      aria-label="Pipeline Monitor"
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-semibold text-gray-900">Pipeline Monitor</h2>

        <div className="flex items-center space-x-4">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as PipelineStatus | 'all')}
            className="px-3 py-1 border border-gray-300 rounded-md text-sm"
            aria-label="Filter by status"
          >
            <option value="all">All Statuses</option>
            <option value={PipelineStatus.ACTIVE}>Active</option>
            <option value={PipelineStatus.RUNNING}>Running</option>
            <option value={PipelineStatus.FAILED}>Failed</option>
            <option value={PipelineStatus.INACTIVE}>Inactive</option>
          </select>

          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="px-3 py-1 border border-gray-300 rounded-md text-sm"
            aria-label="Filter by type"
          >
            <option value="all">All Types</option>
            <option value="ml_training">ML Training</option>
            <option value="data_ingestion">Data Ingestion</option>
            <option value="feature_engineering">Feature Engineering</option>
            <option value="data_validation">Data Validation</option>
          </select>
        </div>
      </div>

      {/* Pipeline Overview */}
      <div className="mb-8">
        <h3 className="text-lg font-medium text-gray-900 mb-4">Pipeline Overview</h3>
        <div className={`grid gap-4 ${isMobile ? 'grid-cols-1' : 'grid-cols-1 md:grid-cols-2 lg:grid-cols-3'}`}>
          {filteredPipelines.map((pipeline) => (
            <div
              key={pipeline.id}
              data-testid={`pipeline-${pipeline.id}`}
              className="p-4 border rounded-lg hover:shadow-md transition-shadow"
            >
              <div className="flex items-center justify-between mb-2">
                <h4 className="font-medium text-gray-900">{pipeline.name}</h4>
                <span className={`px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(pipeline.status)}`}>
                  {pipeline.status}
                </span>
              </div>

              <p className="text-sm text-gray-600 mb-3">{pipeline.description}</p>

              <div className="space-y-1 text-xs text-gray-500">
                <div>Success Rate: {pipeline.successRate.toFixed(1)}%</div>
                <div>Total Runs: {pipeline.totalRuns}</div>
                <div>Avg Runtime: {formatDuration(pipeline.averageRuntime)}</div>
                {pipeline.lastRun && (
                  <div>Last Run: {pipeline.lastRun.toLocaleString()}</div>
                )}
              </div>

              <div className="flex justify-end mt-3 space-x-2">
                {pipeline.status !== PipelineStatus.RUNNING && (
                  <button
                    data-testid={`start-pipeline-${pipeline.id}`}
                    onClick={() => handleStartPipeline(pipeline.id)}
                    className="px-3 py-1 bg-green-600 text-white rounded text-xs hover:bg-green-700"
                  >
                    Start
                  </button>
                )}
                {pipeline.status === PipelineStatus.RUNNING && (
                  <button
                    data-testid={`stop-pipeline-${pipeline.id}`}
                    onClick={() => handleStopPipeline(pipeline.id)}
                    className="px-3 py-1 bg-red-600 text-white rounded text-xs hover:bg-red-700"
                  >
                    Stop
                  </button>
                )}
              </div>

              {pipeline.lastError && (
                <div className="mt-3 p-2 bg-red-50 rounded text-xs">
                  <div className="text-red-800 font-medium">Last Error:</div>
                  <div className="text-red-600">{pipeline.lastError.message}</div>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Active Jobs */}
      <div className="mb-8">
        <h3 className="text-lg font-medium text-gray-900 mb-4">Active Jobs</h3>
        <div className={`grid gap-4 ${isMobile ? 'grid-cols-1' : 'grid-cols-1 md:grid-cols-2'}`}>
          {jobs.map((job) => (
            <div
              key={job.id}
              data-testid={`job-${job.id}`}
              className="p-4 border rounded-lg hover:shadow-md transition-shadow cursor-pointer"
              onClick={() => setSelectedJob(job)}
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === 'Enter') setSelectedJob(job);
              }}
            >
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center space-x-2">
                  <span className="text-sm font-medium text-gray-900">
                    {job.type.replace('_', ' ')}
                  </span>
                  <span
                    data-testid={`job-status-${job.status}`}
                    className={`px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(job.status)}`}
                  >
                    {job.status}
                  </span>
                </div>
                <span className="text-xs text-gray-500">#{job.id.slice(-8)}</span>
              </div>

              {job.status === JobStatus.RUNNING && job.progress !== undefined && (
                <div className="mb-3">
                  <div className="flex justify-between text-xs text-gray-600 mb-1">
                    <span>Progress</span>
                    <span>{job.progress.toFixed(1)}%</span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div
                      className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                      style={{ width: `${job.progress}%` }}
                    />
                  </div>
                </div>
              )}

              <div className="space-y-1 text-xs text-gray-500">
                <div>Started: {job.startTime.toLocaleString()}</div>
                {job.stage && <div>Stage: {job.stage}</div>}
                {job.processedRecords && job.totalRecords && (
                  <div>
                    Records: {job.processedRecords.toLocaleString()} / {job.totalRecords.toLocaleString()}
                  </div>
                )}
                {job.duration && <div>Duration: {formatDuration(job.duration)}</div>}
              </div>

              {job.error && (
                <div className="mt-2 p-2 bg-red-50 rounded text-xs">
                  <div className="text-red-800 font-medium">Error:</div>
                  <div className="text-red-600">{job.error.message}</div>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Charts */}
      <div className={`grid gap-6 mb-8 ${isMobile ? 'grid-cols-1' : 'grid-cols-1 lg:grid-cols-2'}`} data-testid="charts-container">
        {/* Job History Chart */}
        <div className="p-4 border rounded-lg">
          <h4 className="text-sm font-medium text-gray-900 mb-3">Job History (24h)</h4>
          <div data-testid="job-history-chart" style={{ height: '200px' }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={jobHistory}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis
                  dataKey="timestamp"
                  tickFormatter={(value) => new Date(value).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                />
                <YAxis />
                <Tooltip
                  labelFormatter={(value) => new Date(value).toLocaleString()}
                />
                <Legend />
                <Line type="monotone" dataKey="completed" stroke="#10b981" strokeWidth={2} />
                <Line type="monotone" dataKey="failed" stroke="#ef4444" strokeWidth={2} />
                <Line type="monotone" dataKey="running" stroke="#3b82f6" strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Resource Usage Chart */}
        <div className="p-4 border rounded-lg">
          <h4 className="text-sm font-medium text-gray-900 mb-3">Resource Usage (Running Jobs)</h4>
          <div data-testid="resource-usage-chart" style={{ height: '200px' }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={resourceUsageData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="jobName" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Bar dataKey="cpu" fill="#3b82f6" name="CPU %" />
                <Bar dataKey="memory" fill="#10b981" name="Memory GB" />
                {resourceUsageData.some(d => d.gpu !== undefined) && (
                  <Bar dataKey="gpu" fill="#f59e0b" name="GPU %" />
                )}
                <ReferenceLine y={80} stroke="#ef4444" strokeDasharray="5 5" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Job Details Modal */}
      {selectedJob && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className={`bg-white rounded-lg shadow-lg ${isMobile ? 'w-full h-full' : 'max-w-4xl max-h-[80vh]'} overflow-hidden`}>
            <div className="p-6 border-b">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-medium text-gray-900">Job Details</h3>
                <button
                  onClick={() => setSelectedJob(null)}
                  className="text-gray-400 hover:text-gray-600"
                >
                  ✕
                </button>
              </div>
            </div>

            <div className="p-6 overflow-y-auto">
              <div className="grid gap-6 md:grid-cols-2">
                {/* Job Information */}
                <div>
                  <h4 className="font-medium text-gray-900 mb-3">Job Information</h4>
                  <div className="space-y-2 text-sm">
                    <div><span className="font-medium">ID:</span> {selectedJob.id}</div>
                    <div><span className="font-medium">Type:</span> {selectedJob.type}</div>
                    <div><span className="font-medium">Status:</span> {selectedJob.status}</div>
                    <div><span className="font-medium">Started:</span> {selectedJob.startTime.toLocaleString()}</div>
                    {selectedJob.endTime && (
                      <div><span className="font-medium">Ended:</span> {selectedJob.endTime.toLocaleString()}</div>
                    )}
                    {selectedJob.duration && (
                      <div><span className="font-medium">Duration:</span> {formatDuration(selectedJob.duration)}</div>
                    )}
                  </div>

                  {selectedJob.progress !== undefined && (
                    <div className="mt-4">
                      <div className="flex justify-between text-sm text-gray-600 mb-1">
                        <span>Progress: {selectedJob.progress.toFixed(1)}%</span>
                        {selectedJob.stage && <span>Stage: {selectedJob.stage}</span>}
                      </div>
                      <div className="w-full bg-gray-200 rounded-full h-2">
                        <div
                          className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                          style={{ width: `${selectedJob.progress}%` }}
                        />
                      </div>
                    </div>
                  )}

                  {selectedJob.processedRecords && selectedJob.totalRecords && (
                    <div className="mt-4">
                      <div className="text-sm">
                        <span className="font-medium">Processed:</span> {selectedJob.processedRecords.toLocaleString()} / {selectedJob.totalRecords.toLocaleString()} records
                      </div>
                    </div>
                  )}
                </div>

                {/* Resource Usage */}
                {selectedJob.resourceUsage && (
                  <div>
                    <h4 className="font-medium text-gray-900 mb-3">Resource Usage</h4>
                    <div className="space-y-3">
                      <div>
                        <div className="flex justify-between text-sm mb-1">
                          <span>CPU</span>
                          <span>{selectedJob.resourceUsage.cpu.toFixed(1)}%</span>
                        </div>
                        <div className="w-full bg-gray-200 rounded-full h-2">
                          <div
                            className="bg-blue-600 h-2 rounded-full"
                            style={{ width: `${selectedJob.resourceUsage.cpu}%` }}
                          />
                        </div>
                      </div>

                      <div>
                        <div className="flex justify-between text-sm mb-1">
                          <span>Memory</span>
                          <span>{selectedJob.resourceUsage.memory.toFixed(1)} GB</span>
                        </div>
                        <div className="w-full bg-gray-200 rounded-full h-2">
                          <div
                            className="bg-green-600 h-2 rounded-full"
                            style={{ width: `${Math.min(selectedJob.resourceUsage.memory * 10, 100)}%` }}
                          />
                        </div>
                      </div>

                      {selectedJob.resourceUsage.gpu && (
                        <div>
                          <div className="flex justify-between text-sm mb-1">
                            <span>GPU</span>
                            <span>{selectedJob.resourceUsage.gpu.toFixed(1)}%</span>
                          </div>
                          <div className="w-full bg-gray-200 rounded-full h-2">
                            <div
                              className="bg-yellow-600 h-2 rounded-full"
                              style={{ width: `${selectedJob.resourceUsage.gpu}%` }}
                            />
                          </div>
                        </div>
                      )}

                      <div>
                        <div className="flex justify-between text-sm mb-1">
                          <span>Disk I/O</span>
                          <span>{formatBytes(selectedJob.resourceUsage.disk * 1024 * 1024)}/s</span>
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {/* Job Actions */}
              <div className="mt-6 flex space-x-3">
                {selectedJob.status === JobStatus.RUNNING && (
                  <button
                    data-testid={`cancel-job-${selectedJob.id}`}
                    onClick={() => {
                      handleCancelJob(selectedJob.id);
                      setSelectedJob(null);
                    }}
                    className="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700"
                  >
                    Cancel Job
                  </button>
                )}

                {selectedJob.status === JobStatus.FAILED && selectedJob.error?.retryable && (
                  <button
                    data-testid={`retry-job-${selectedJob.id}`}
                    onClick={() => {
                      handleRetryJob(selectedJob.id);
                      setSelectedJob(null);
                    }}
                    className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
                  >
                    Retry Job
                  </button>
                )}
              </div>

              {/* Job Logs */}
              {selectedJob.logs && selectedJob.logs.length > 0 && (
                <div className="mt-6">
                  <h4 className="font-medium text-gray-900 mb-3">Job Logs</h4>
                  <div className="bg-gray-900 text-green-400 p-4 rounded-lg max-h-64 overflow-y-auto font-mono text-sm">
                    {selectedJob.logs.map((log, index) => (
                      <div key={index} className="mb-1">
                        <span className="text-gray-500">
                          [{log.timestamp.toLocaleTimeString()}]
                        </span>
                        <span className={`ml-2 ${
                          log.level === 'error' ? 'text-red-400' :
                          log.level === 'warn' ? 'text-yellow-400' :
                          'text-green-400'
                        }`}>
                          [{log.level.toUpperCase()}]
                        </span>
                        <span className="ml-2">{log.message}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Error Details */}
              {selectedJob.error && (
                <div className="mt-6">
                  <h4 className="font-medium text-gray-900 mb-3">Error Details</h4>
                  <div className="bg-red-50 p-4 rounded-lg">
                    <div className="text-red-800 font-medium mb-2">{selectedJob.error.message}</div>
                    {selectedJob.error.code && (
                      <div className="text-red-600 text-sm mb-2">Error Code: {selectedJob.error.code}</div>
                    )}
                    <div className="text-red-500 text-xs">
                      {selectedJob.error.timestamp.toLocaleString()}
                    </div>
                    {selectedJob.error.stack && (
                      <details className="mt-3">
                        <summary className="text-red-600 text-sm cursor-pointer">Stack Trace</summary>
                        <pre className="mt-2 text-xs text-red-500 whitespace-pre-wrap overflow-x-auto">
                          {selectedJob.error.stack}
                        </pre>
                      </details>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
