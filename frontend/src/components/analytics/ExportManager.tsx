/**
 * ExportManager Component
 *
 * Centralized export job management interface with configuration, monitoring, and bulk operations
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  ExportService,
  getExportService,
} from '@/services/export';
import {
  ExportJob,
  ExportType,
  ExportFormat,
  ExportStatus,
  ExportParameters,
  AnalyticsQuery,
  TimeRange,
  TimeInterval,
} from '@/types/analytics';

export interface ExportManagerProps {
  className?: string;
  view?: ExportManagerView;
  refreshInterval?: number;
  autoRefresh?: boolean;
  showCompleted?: boolean;
  showFailed?: boolean;
  maxDisplayJobs?: number;
  exportService?: ExportService;
  onJobSelect?: (job: ExportJob) => void;
  onJobCancel?: (jobId: string) => void;
  onJobDownload?: (jobId: string) => void;
  onJobDelete?: (jobId: string) => void;
  onBulkAction?: (action: BulkAction, jobIds: string[]) => void;
  onError?: (error: Error) => void;
}

export enum ExportManagerView {
  ACTIVE = 'active',
  HISTORY = 'history',
  SETTINGS = 'settings',
  TEMPLATES = 'templates',
}

export enum BulkAction {
  CANCEL = 'cancel',
  DELETE = 'delete',
  DOWNLOAD = 'download',
  RETRY = 'retry',
}

interface ExportManagerState {
  loading: boolean;
  error: string | null;
  jobs: ExportJob[];
  selectedJobs: Set<string>;
  currentView: ExportManagerView;
  filterStatus: ExportStatus | 'all';
  filterType: ExportType | 'all';
  filterFormat: ExportFormat | 'all';
  searchQuery: string;
  sortBy: SortOption;
  sortOrder: 'asc' | 'desc';
  refreshing: boolean;
  statistics: ExportStatistics | null;
}

interface ExportStatistics {
  totalJobs: number;
  activeJobs: number;
  completedJobs: number;
  failedJobs: number;
  totalSize: number;
  averageSize: number;
  averageProcessingTime: number;
  successRate: number;
}

enum SortOption {
  CREATED_AT = 'createdAt',
  NAME = 'name',
  STATUS = 'status',
  FORMAT = 'format',
  SIZE = 'fileSize',
  PROGRESS = 'progress',
}

export const ExportManager: React.FC<ExportManagerProps> = ({
  className = '',
  view = ExportManagerView.ACTIVE,
  refreshInterval = 5000,
  autoRefresh = true,
  showCompleted = true,
  showFailed = true,
  maxDisplayJobs = 100,
  exportService,
  onJobSelect,
  onJobCancel,
  onJobDownload,
  onJobDelete,
  onBulkAction,
  onError,
}) => {
  const [service] = useState(() => exportService || getExportService());

  const [state, setState] = useState<ExportManagerState>(() => ({
    loading: true,
    error: null,
    jobs: [],
    selectedJobs: new Set(),
    currentView: view,
    filterStatus: 'all',
    filterType: 'all',
    filterFormat: 'all',
    searchQuery: '',
    sortBy: SortOption.CREATED_AT,
    sortOrder: 'desc',
    refreshing: false,
    statistics: null,
  }));

  // Load export jobs
  const loadExportJobs = useCallback(async (showRefreshing = false) => {
    if (showRefreshing) {
      setState(prev => ({ ...prev, refreshing: true }));
    } else {
      setState(prev => ({ ...prev, loading: true, error: null }));
    }

    try {
      const [jobs, statistics] = await Promise.all([
        service.getExportJobs(),
        service.getExportStatistics(),
      ]);

      setState(prev => ({
        ...prev,
        loading: false,
        refreshing: false,
        error: null,
        jobs: jobs.slice(0, maxDisplayJobs),
        statistics,
      }));
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to load export jobs';
      setState(prev => ({
        ...prev,
        loading: false,
        refreshing: false,
        error: errorMessage,
      }));
      onError?.(error instanceof Error ? error : new Error(errorMessage));
    }
  }, [service, maxDisplayJobs, onError]);

  // Initial load
  useEffect(() => {
    loadExportJobs();
  }, [loadExportJobs]);

  // Auto-refresh setup
  useEffect(() => {
    if (!autoRefresh) return;

    const interval = setInterval(() => {
      loadExportJobs(true);
    }, refreshInterval);

    return () => clearInterval(interval);
  }, [autoRefresh, refreshInterval, loadExportJobs]);

  // Handle view change
  const handleViewChange = useCallback((newView: ExportManagerView) => {
    setState(prev => ({ ...prev, currentView: newView }));
  }, []);

  // Handle job selection
  const handleJobSelection = useCallback((jobId: string, selected: boolean) => {
    setState(prev => {
      const newSelectedJobs = new Set(prev.selectedJobs);
      if (selected) {
        newSelectedJobs.add(jobId);
      } else {
        newSelectedJobs.delete(jobId);
      }
      return { ...prev, selectedJobs: newSelectedJobs };
    });
  }, []);

  // Handle select all
  const handleSelectAll = useCallback((selected: boolean) => {
    setState(prev => ({
      ...prev,
      selectedJobs: selected ? new Set(prev.jobs.map(job => job.id)) : new Set(),
    }));
  }, []);

  // Handle job actions
  const handleJobAction = useCallback(async (action: string, jobId: string) => {
    try {
      switch (action) {
        case 'cancel':
          await service.cancelExportJob(jobId);
          onJobCancel?.(jobId);
          break;
        case 'download':
          const blob = await service.downloadExport(jobId);
          // Create download link
          const url = URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = url;
          a.download = `export-${jobId}`;
          document.body.appendChild(a);
          a.click();
          document.body.removeChild(a);
          URL.revokeObjectURL(url);
          onJobDownload?.(jobId);
          break;
        case 'delete':
          await service.deleteExport(jobId);
          onJobDelete?.(jobId);
          break;
      }

      // Refresh jobs after action
      await loadExportJobs(true);
    } catch (error) {
      onError?.(error instanceof Error ? error : new Error(`Failed to ${action} job`));
    }
  }, [service, loadExportJobs, onJobCancel, onJobDownload, onJobDelete, onError]);

  // Handle bulk actions
  const handleBulkAction = useCallback(async (action: BulkAction) => {
    const selectedJobIds = Array.from(state.selectedJobs);
    if (selectedJobIds.length === 0) return;

    try {
      const actionPromises = selectedJobIds.map(jobId => {
        switch (action) {
          case BulkAction.CANCEL:
            return service.cancelExportJob(jobId);
          case BulkAction.DELETE:
            return service.deleteExport(jobId);
          case BulkAction.DOWNLOAD:
            return handleJobAction('download', jobId);
          default:
            return Promise.resolve();
        }
      });

      await Promise.all(actionPromises);

      setState(prev => ({ ...prev, selectedJobs: new Set() }));
      onBulkAction?.(action, selectedJobIds);

      // Refresh jobs after bulk action
      await loadExportJobs(true);
    } catch (error) {
      onError?.(error instanceof Error ? error : new Error(`Failed to perform bulk ${action}`));
    }
  }, [state.selectedJobs, service, handleJobAction, loadExportJobs, onBulkAction, onError]);

  // Filtered and sorted jobs
  const filteredJobs = useMemo(() => {
    let filtered = state.jobs;

    // Apply status filter
    if (state.filterStatus !== 'all') {
      filtered = filtered.filter(job => job.status === state.filterStatus);
    }

    // Apply type filter
    if (state.filterType !== 'all') {
      filtered = filtered.filter(job => job.type === state.filterType);
    }

    // Apply format filter
    if (state.filterFormat !== 'all') {
      filtered = filtered.filter(job => job.format === state.filterFormat);
    }

    // Apply search filter
    if (state.searchQuery) {
      const query = state.searchQuery.toLowerCase();
      filtered = filtered.filter(job =>
        job.name.toLowerCase().includes(query) ||
        job.id.toLowerCase().includes(query)
      );
    }

    // Apply visibility filters
    if (!showCompleted) {
      filtered = filtered.filter(job => job.status !== ExportStatus.COMPLETED);
    }

    if (!showFailed) {
      filtered = filtered.filter(job => job.status !== ExportStatus.FAILED);
    }

    // Sort jobs
    filtered.sort((a, b) => {
      let aValue: any, bValue: any;

      switch (state.sortBy) {
        case SortOption.CREATED_AT:
          aValue = a.createdAt.getTime();
          bValue = b.createdAt.getTime();
          break;
        case SortOption.NAME:
          aValue = a.name.toLowerCase();
          bValue = b.name.toLowerCase();
          break;
        case SortOption.STATUS:
          aValue = a.status;
          bValue = b.status;
          break;
        case SortOption.FORMAT:
          aValue = a.format;
          bValue = b.format;
          break;
        case SortOption.SIZE:
          aValue = a.fileSize || 0;
          bValue = b.fileSize || 0;
          break;
        case SortOption.PROGRESS:
          aValue = a.progress;
          bValue = b.progress;
          break;
        default:
          aValue = a.createdAt.getTime();
          bValue = b.createdAt.getTime();
      }

      if (state.sortOrder === 'asc') {
        return aValue < bValue ? -1 : aValue > bValue ? 1 : 0;
      } else {
        return aValue > bValue ? -1 : aValue < bValue ? 1 : 0;
      }
    });

    return filtered;
  }, [state.jobs, state.filterStatus, state.filterType, state.filterFormat, state.searchQuery, state.sortBy, state.sortOrder, showCompleted, showFailed]);

  // Get status color
  const getStatusColor = (status: ExportStatus) => {
    switch (status) {
      case ExportStatus.COMPLETED:
        return 'text-green-600 bg-green-100';
      case ExportStatus.PROCESSING:
        return 'text-blue-600 bg-blue-100';
      case ExportStatus.QUEUED:
        return 'text-yellow-600 bg-yellow-100';
      case ExportStatus.FAILED:
        return 'text-red-600 bg-red-100';
      case ExportStatus.CANCELLED:
        return 'text-gray-600 bg-gray-100';
      default:
        return 'text-gray-600 bg-gray-100';
    }
  };

  // Format file size
  const formatFileSize = (bytes: number | undefined) => {
    if (!bytes) return 'N/A';
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${sizes[i]}`;
  };

  // Format duration
  const formatDuration = (startTime?: Date, endTime?: Date) => {
    if (!startTime) return 'N/A';
    const end = endTime || new Date();
    const duration = end.getTime() - startTime.getTime();
    const seconds = Math.floor(duration / 1000);
    if (seconds < 60) return `${seconds}s`;
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m ${seconds % 60}s`;
    const hours = Math.floor(minutes / 60);
    return `${hours}h ${minutes % 60}m`;
  };

  // Loading state
  if (state.loading) {
    return (
      <div className={`flex items-center justify-center h-64 ${className}`} data-testid="export-manager-loading">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading export manager...</p>
        </div>
      </div>
    );
  }

  // Error state
  if (state.error) {
    return (
      <div className={`bg-red-50 border border-red-200 rounded-lg p-6 ${className}`} data-testid="export-manager-error">
        <div className="flex items-center space-x-3">
          <div className="text-red-600 text-xl">⚠️</div>
          <div>
            <h3 className="text-red-800 font-medium">Export Manager Error</h3>
            <p className="text-red-600">{state.error}</p>
            <button
              onClick={() => loadExportJobs()}
              className="mt-2 px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700"
            >
              Retry
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={`export-manager space-y-6 ${className}`} data-testid="export-manager">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between space-y-4 sm:space-y-0">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Export Manager</h2>
          <p className="text-gray-600">
            Manage export jobs, downloads, and configurations
            {state.refreshing && (
              <span className="ml-2 text-blue-600">
                <span className="animate-spin inline-block w-4 h-4 border-2 border-blue-600 border-t-transparent rounded-full"></span>
                Refreshing...
              </span>
            )}
          </p>
        </div>

        <div className="flex items-center space-x-4">
          {/* View Navigation */}
          <div className="flex bg-gray-100 rounded-lg p-1" data-testid="view-navigation">
            <button
              onClick={() => handleViewChange(ExportManagerView.ACTIVE)}
              className={`px-3 py-2 rounded text-sm font-medium ${
                state.currentView === ExportManagerView.ACTIVE
                  ? 'bg-white text-blue-600 shadow'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
              data-testid="active-view-button"
            >
              Active ({state.statistics?.activeJobs || 0})
            </button>
            <button
              onClick={() => handleViewChange(ExportManagerView.HISTORY)}
              className={`px-3 py-2 rounded text-sm font-medium ${
                state.currentView === ExportManagerView.HISTORY
                  ? 'bg-white text-blue-600 shadow'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
              data-testid="history-view-button"
            >
              History
            </button>
            <button
              onClick={() => handleViewChange(ExportManagerView.SETTINGS)}
              className={`px-3 py-2 rounded text-sm font-medium ${
                state.currentView === ExportManagerView.SETTINGS
                  ? 'bg-white text-blue-600 shadow'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
              data-testid="settings-view-button"
            >
              Settings
            </button>
          </div>

          <button
            onClick={() => loadExportJobs(true)}
            disabled={state.refreshing}
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
            data-testid="refresh-button"
          >
            {state.refreshing ? 'Refreshing...' : 'Refresh'}
          </button>
        </div>
      </div>

      {/* Statistics Cards */}
      {state.statistics && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4" data-testid="export-statistics">
          <div className="bg-white rounded-lg p-6 shadow border">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">Total Jobs</p>
                <p className="text-3xl font-bold text-gray-900">{state.statistics.totalJobs}</p>
              </div>
              <div className="text-2xl">📋</div>
            </div>
          </div>

          <div className="bg-white rounded-lg p-6 shadow border">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">Success Rate</p>
                <p className="text-3xl font-bold text-green-600">{(state.statistics.successRate * 100).toFixed(1)}%</p>
              </div>
              <div className="text-2xl">✅</div>
            </div>
          </div>

          <div className="bg-white rounded-lg p-6 shadow border">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">Total Size</p>
                <p className="text-3xl font-bold text-blue-600">{formatFileSize(state.statistics.totalSize)}</p>
              </div>
              <div className="text-2xl">💾</div>
            </div>
          </div>

          <div className="bg-white rounded-lg p-6 shadow border">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">Avg Processing</p>
                <p className="text-3xl font-bold text-purple-600">{formatDuration(new Date(0), new Date(state.statistics.averageProcessingTime))}</p>
              </div>
              <div className="text-2xl">⏱️</div>
            </div>
          </div>
        </div>
      )}

      {/* Controls and Filters */}
      <div className="bg-white rounded-lg p-6 shadow border" data-testid="export-controls">
        <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between space-y-4 lg:space-y-0">
          {/* Search and Filters */}
          <div className="flex flex-col sm:flex-row space-y-2 sm:space-y-0 sm:space-x-4">
            <input
              type="text"
              placeholder="Search jobs..."
              value={state.searchQuery}
              onChange={(e) => setState(prev => ({ ...prev, searchQuery: e.target.value }))}
              className="rounded border-gray-300 text-sm"
              data-testid="search-input"
            />

            <select
              value={state.filterStatus}
              onChange={(e) => setState(prev => ({ ...prev, filterStatus: e.target.value as ExportStatus | 'all' }))}
              className="rounded border-gray-300 text-sm"
              data-testid="status-filter"
            >
              <option value="all">All Status</option>
              {Object.values(ExportStatus).map(status => (
                <option key={status} value={status}>
                  {status.toUpperCase()}
                </option>
              ))}
            </select>

            <select
              value={state.filterFormat}
              onChange={(e) => setState(prev => ({ ...prev, filterFormat: e.target.value as ExportFormat | 'all' }))}
              className="rounded border-gray-300 text-sm"
              data-testid="format-filter"
            >
              <option value="all">All Formats</option>
              {Object.values(ExportFormat).map(format => (
                <option key={format} value={format}>
                  {format.toUpperCase()}
                </option>
              ))}
            </select>
          </div>

          {/* Bulk Actions */}
          {state.selectedJobs.size > 0 && (
            <div className="flex items-center space-x-2" data-testid="bulk-actions">
              <span className="text-sm text-gray-600">
                {state.selectedJobs.size} selected
              </span>
              <button
                onClick={() => handleBulkAction(BulkAction.CANCEL)}
                className="px-3 py-1 bg-yellow-600 text-white rounded text-sm hover:bg-yellow-700"
                data-testid="bulk-cancel-button"
              >
                Cancel
              </button>
              <button
                onClick={() => handleBulkAction(BulkAction.DELETE)}
                className="px-3 py-1 bg-red-600 text-white rounded text-sm hover:bg-red-700"
                data-testid="bulk-delete-button"
              >
                Delete
              </button>
            </div>
          )}

          {/* Sort Options */}
          <div className="flex items-center space-x-2">
            <select
              value={state.sortBy}
              onChange={(e) => setState(prev => ({ ...prev, sortBy: e.target.value as SortOption }))}
              className="rounded border-gray-300 text-sm"
              data-testid="sort-select"
            >
              <option value={SortOption.CREATED_AT}>Created At</option>
              <option value={SortOption.NAME}>Name</option>
              <option value={SortOption.STATUS}>Status</option>
              <option value={SortOption.FORMAT}>Format</option>
              <option value={SortOption.SIZE}>Size</option>
              <option value={SortOption.PROGRESS}>Progress</option>
            </select>
            <button
              onClick={() => setState(prev => ({ ...prev, sortOrder: prev.sortOrder === 'asc' ? 'desc' : 'asc' }))}
              className="px-2 py-1 border border-gray-300 rounded text-sm hover:bg-gray-50"
              data-testid="sort-order-button"
            >
              {state.sortOrder === 'asc' ? '↑' : '↓'}
            </button>
          </div>
        </div>
      </div>

      {/* Jobs Table */}
      <div className="bg-white rounded-lg shadow border" data-testid="jobs-table">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left">
                  <input
                    type="checkbox"
                    checked={state.selectedJobs.size === filteredJobs.length && filteredJobs.length > 0}
                    onChange={(e) => handleSelectAll(e.target.checked)}
                    className="rounded border-gray-300"
                    data-testid="select-all-checkbox"
                  />
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Job
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Progress
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Format
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Size
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Duration
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Created
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {filteredJobs.map((job) => (
                <tr
                  key={job.id}
                  className={`hover:bg-gray-50 ${state.selectedJobs.has(job.id) ? 'bg-blue-50' : ''}`}
                  data-testid={`job-row-${job.id}`}
                >
                  <td className="px-6 py-4 whitespace-nowrap">
                    <input
                      type="checkbox"
                      checked={state.selectedJobs.has(job.id)}
                      onChange={(e) => handleJobSelection(job.id, e.target.checked)}
                      className="rounded border-gray-300"
                      data-testid={`job-checkbox-${job.id}`}
                    />
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div
                      className="cursor-pointer"
                      onClick={() => onJobSelect?.(job)}
                      data-testid={`job-name-${job.id}`}
                    >
                      <div className="text-sm font-medium text-gray-900">{job.name}</div>
                      <div className="text-sm text-gray-500">{job.id}</div>
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className={`px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(job.status)}`}>
                      {job.status}
                    </span>
                    {job.error && (
                      <div className="text-xs text-red-600 mt-1" title={job.error}>
                        Error: {job.error.substring(0, 50)}...
                      </div>
                    )}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="w-full bg-gray-200 rounded-full h-2">
                      <div
                        className={`h-2 rounded-full ${
                          job.status === ExportStatus.COMPLETED ? 'bg-green-500' :
                          job.status === ExportStatus.FAILED ? 'bg-red-500' :
                          'bg-blue-500'
                        }`}
                        style={{ width: `${job.progress}%` }}
                      ></div>
                    </div>
                    <div className="text-xs text-gray-500 mt-1">{job.progress}%</div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-gray-100 text-gray-800">
                      {job.format.toUpperCase()}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {formatFileSize(job.fileSize)}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {formatDuration(job.startedAt, job.completedAt)}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {job.createdAt.toLocaleString()}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium space-x-2">
                    {job.status === ExportStatus.COMPLETED && job.downloadUrl && (
                      <button
                        onClick={() => handleJobAction('download', job.id)}
                        className="text-green-600 hover:text-green-900"
                        data-testid={`download-button-${job.id}`}
                      >
                        Download
                      </button>
                    )}
                    {(job.status === ExportStatus.QUEUED || job.status === ExportStatus.PROCESSING) && (
                      <button
                        onClick={() => handleJobAction('cancel', job.id)}
                        className="text-yellow-600 hover:text-yellow-900"
                        data-testid={`cancel-button-${job.id}`}
                      >
                        Cancel
                      </button>
                    )}
                    <button
                      onClick={() => handleJobAction('delete', job.id)}
                      className="text-red-600 hover:text-red-900"
                      data-testid={`delete-button-${job.id}`}
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {filteredJobs.length === 0 && (
          <div className="text-center py-12" data-testid="no-jobs-message">
            <div className="text-gray-400 text-6xl mb-4">📤</div>
            <h3 className="text-lg font-medium text-gray-900 mb-2">No export jobs found</h3>
            <p className="text-gray-600">
              {state.searchQuery || state.filterStatus !== 'all' || state.filterFormat !== 'all'
                ? 'Try adjusting your filters'
                : 'No export jobs have been created yet'
              }
            </p>
          </div>
        )}
      </div>

      {/* Settings View */}
      {state.currentView === ExportManagerView.SETTINGS && (
        <div className="bg-white rounded-lg p-6 shadow border" data-testid="export-settings">
          <h3 className="text-lg font-medium text-gray-900 mb-6">Export Settings</h3>

          <div className="space-y-6">
            <div>
              <h4 className="text-base font-medium text-gray-900 mb-4">Default Export Preferences</h4>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Default Format
                  </label>
                  <select className="w-full rounded border-gray-300" data-testid="default-format-select">
                    <option value={ExportFormat.PDF}>PDF</option>
                    <option value={ExportFormat.EXCEL}>Excel</option>
                    <option value={ExportFormat.CSV}>CSV</option>
                    <option value={ExportFormat.JSON}>JSON</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Auto-cleanup After (days)
                  </label>
                  <input
                    type="number"
                    min="1"
                    max="365"
                    defaultValue="30"
                    className="w-full rounded border-gray-300"
                    data-testid="cleanup-days-input"
                  />
                </div>
              </div>
            </div>

            <div>
              <h4 className="text-base font-medium text-gray-900 mb-4">Notification Settings</h4>
              <div className="space-y-3">
                <label className="flex items-center">
                  <input
                    type="checkbox"
                    defaultChecked
                    className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                    data-testid="notify-completion-checkbox"
                  />
                  <span className="ml-2 text-sm text-gray-700">Notify on export completion</span>
                </label>

                <label className="flex items-center">
                  <input
                    type="checkbox"
                    defaultChecked
                    className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                    data-testid="notify-failure-checkbox"
                  />
                  <span className="ml-2 text-sm text-gray-700">Notify on export failure</span>
                </label>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
