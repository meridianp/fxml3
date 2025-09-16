/**
 * DataSourceMonitor Component
 *
 * Real-time monitoring dashboard for data source connections and performance
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  WifiIcon,
  ExclamationTriangleIcon,
  SignalIcon,
  ClockIcon,
  ChartBarIcon,
  MagnifyingGlassIcon,
  ArrowPathIcon,
  CheckCircleIcon,
  XCircleIcon,
  ExclamationCircleIcon,
} from '@heroicons/react/24/outline';
import { DataSourceService } from '@/services/dataSource';
import { NotificationService } from '@/services/notification';
import { DataSource, DataSourceType, ConnectionStatus, DataQualityLevel } from '@/types/dataManagement';
import { clsx } from 'clsx';

export interface DataSourceMonitorProps {
  className?: string;
  refreshInterval?: number;
  autoRefresh?: boolean;
}

interface PerformanceMetrics {
  timestamp: string;
  sources: Array<{
    id: string;
    latency: number;
    throughput: number;
    errorRate: number;
    uptime: number;
  }>;
  summary: {
    totalSources: number;
    connectedSources: number;
    avgLatency: number;
    avgThroughput: number;
    avgUptime: number;
  };
}

interface Filters {
  status: ConnectionStatus | 'all';
  type: DataSourceType | 'all';
  search: string;
}

export const DataSourceMonitor: React.FC<DataSourceMonitorProps> = ({
  className = '',
  refreshInterval = 30000,
  autoRefresh = true,
}) => {
  const [dataSources, setDataSources] = useState<DataSource[]>([]);
  const [performanceMetrics, setPerformanceMetrics] = useState<PerformanceMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [metricsError, setMetricsError] = useState<string | null>(null);
  const [testingConnections, setTestingConnections] = useState<Set<string>>(new Set());
  const [filters, setFilters] = useState<Filters>({
    status: 'all',
    type: 'all',
    search: '',
  });

  // Services
  const dataSourceService = useMemo(() => new DataSourceService({
    apiBaseUrl: process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000/api',
  }), []);

  const notificationService = useMemo(() => new NotificationService(), []);

  // Load data sources
  const loadDataSources = useCallback(async () => {
    try {
      setError(null);
      const sources = await dataSourceService.getDataSources();
      setDataSources(sources);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error';
      setError(`Error loading data sources: ${errorMessage}`);
    } finally {
      setLoading(false);
    }
  }, [dataSourceService]);

  // Load performance metrics
  const loadPerformanceMetrics = useCallback(async () => {
    try {
      setMetricsError(null);
      const metrics = await dataSourceService.getPerformanceMetrics();
      setPerformanceMetrics(metrics);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error';
      setMetricsError(`Error loading performance metrics: ${errorMessage}`);
    }
  }, [dataSourceService]);

  // Test connection
  const testConnection = useCallback(async (sourceId: string, sourceName: string) => {
    setTestingConnections(prev => new Set([...prev, sourceId]));

    try {
      const result = await dataSourceService.testConnection(sourceId);

      notificationService.create({
        type: 'success',
        title: 'Connection Test',
        message: `Connection to ${sourceName} successful (${result.latency}ms)`,
      });
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error';
      notificationService.create({
        type: 'error',
        title: 'Connection Test Failed',
        message: `Failed to test connection to ${sourceName}: ${errorMessage}`,
      });
    } finally {
      setTestingConnections(prev => {
        const newSet = new Set(prev);
        newSet.delete(sourceId);
        return newSet;
      });
    }
  }, [dataSourceService, notificationService]);

  // Filter data sources
  const filteredDataSources = useMemo(() => {
    return dataSources.filter(source => {
      // Status filter
      if (filters.status !== 'all' && source.status !== filters.status) {
        return false;
      }

      // Type filter
      if (filters.type !== 'all' && source.type !== filters.type) {
        return false;
      }

      // Search filter
      if (filters.search) {
        const searchTerm = filters.search.toLowerCase();
        return (
          source.name.toLowerCase().includes(searchTerm) ||
          source.description?.toLowerCase().includes(searchTerm) ||
          source.tags.some(tag => tag.toLowerCase().includes(searchTerm))
        );
      }

      return true;
    });
  }, [dataSources, filters]);

  // Get status icon and color
  const getStatusDisplay = useCallback((status: ConnectionStatus) => {
    switch (status) {
      case ConnectionStatus.CONNECTED:
        return {
          icon: CheckCircleIcon,
          color: 'text-green-600',
          bgColor: 'bg-green-100',
          testId: 'status-connected',
        };
      case ConnectionStatus.DISCONNECTED:
        return {
          icon: XCircleIcon,
          color: 'text-red-600',
          bgColor: 'bg-red-100',
          testId: 'status-disconnected',
        };
      case ConnectionStatus.ERROR:
        return {
          icon: ExclamationCircleIcon,
          color: 'text-red-600',
          bgColor: 'bg-red-100',
          testId: 'status-error',
        };
      case ConnectionStatus.DEGRADED:
        return {
          icon: ExclamationTriangleIcon,
          color: 'text-yellow-600',
          bgColor: 'bg-yellow-100',
          testId: 'status-degraded',
        };
      case ConnectionStatus.CONNECTING:
        return {
          icon: ArrowPathIcon,
          color: 'text-blue-600',
          bgColor: 'bg-blue-100',
          testId: 'status-connecting',
        };
      default:
        return {
          icon: XCircleIcon,
          color: 'text-gray-600',
          bgColor: 'bg-gray-100',
          testId: 'status-unknown',
        };
    }
  }, []);

  // Get quality score color
  const getQualityScoreColor = useCallback((level: DataQualityLevel) => {
    switch (level) {
      case DataQualityLevel.EXCELLENT:
        return 'text-green-600';
      case DataQualityLevel.GOOD:
        return 'text-blue-600';
      case DataQualityLevel.FAIR:
        return 'text-yellow-600';
      case DataQualityLevel.POOR:
        return 'text-orange-600';
      case DataQualityLevel.CRITICAL:
        return 'text-red-600';
      default:
        return 'text-gray-600';
    }
  }, []);

  // Format numbers
  const formatNumber = useCallback((num: number) => {
    return new Intl.NumberFormat().format(Math.round(num));
  }, []);

  const formatPercentage = useCallback((num: number) => {
    return `${num}%`;
  }, []);

  const formatLatency = useCallback((num: number) => {
    return `${Math.round(num)}ms`;
  }, []);

  // Initial load
  useEffect(() => {
    loadDataSources();
    loadPerformanceMetrics();
  }, [loadDataSources, loadPerformanceMetrics]);

  // Auto-refresh
  useEffect(() => {
    if (!autoRefresh || refreshInterval <= 0) return;

    const interval = setInterval(() => {
      loadDataSources();
      loadPerformanceMetrics();
    }, refreshInterval);

    return () => clearInterval(interval);
  }, [autoRefresh, refreshInterval, loadDataSources, loadPerformanceMetrics]);

  // Mobile detection
  const isMobile = typeof window !== 'undefined' && window.innerWidth <= 768;

  if (loading) {
    return (
      <div className={clsx('bg-white shadow rounded-lg p-6', className)}>
        <h2 className="text-lg font-medium text-gray-900 mb-4">Data Source Monitor</h2>
        <div className="text-gray-500">Loading...</div>
      </div>
    );
  }

  return (
    <div
      className={clsx(
        'bg-white shadow rounded-lg',
        isMobile && 'mobile-layout',
        className
      )}
      data-testid="data-source-monitor"
      role="region"
      aria-label="Data Source Monitor"
    >
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-200">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-medium text-gray-900">Data Source Monitor</h2>
          <div className="flex items-center space-x-2">
            <button
              onClick={() => {
                loadDataSources();
                loadPerformanceMetrics();
              }}
              className="inline-flex items-center px-3 py-2 border border-gray-300 shadow-sm text-sm leading-4 font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
            >
              <ArrowPathIcon className="h-4 w-4 mr-2" />
              Refresh
            </button>
          </div>
        </div>

        {/* Summary Statistics */}
        {performanceMetrics && (
          <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="text-center">
              <div className="text-2xl font-semibold text-gray-900" data-testid="total-sources">
                {performanceMetrics.summary.totalSources}
              </div>
              <div className="text-sm text-gray-500">Total Sources</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-semibold text-green-600" data-testid="connected-sources">
                {performanceMetrics.summary.connectedSources}
              </div>
              <div className="text-sm text-gray-500">Connected</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-semibold text-blue-600" data-testid="average-latency">
                {formatLatency(performanceMetrics.summary.avgLatency)}
              </div>
              <div className="text-sm text-gray-500">Avg Latency</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-semibold text-purple-600" data-testid="average-uptime">
                {formatPercentage(performanceMetrics.summary.avgUptime)}
              </div>
              <div className="text-sm text-gray-500">Avg Uptime</div>
            </div>
          </div>
        )}
      </div>

      {/* Filters */}
      <div className="px-6 py-4 border-b border-gray-200 bg-gray-50">
        <div className="flex flex-col md:flex-row md:items-center md:space-x-4 space-y-2 md:space-y-0">
          {/* Search */}
          <div className="flex-1 min-w-0">
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                <MagnifyingGlassIcon className="h-5 w-5 text-gray-400" />
              </div>
              <input
                type="text"
                placeholder="Search data sources..."
                value={filters.search}
                onChange={(e) => setFilters(prev => ({ ...prev, search: e.target.value }))}
                className="block w-full pl-10 pr-3 py-2 border border-gray-300 rounded-md leading-5 bg-white placeholder-gray-500 focus:outline-none focus:placeholder-gray-400 focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 text-sm"
                aria-label="Search data sources"
              />
            </div>
          </div>

          {/* Status Filter */}
          <div className="min-w-0">
            <select
              value={filters.status}
              onChange={(e) => setFilters(prev => ({ ...prev, status: e.target.value as ConnectionStatus | 'all' }))}
              className="block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 text-sm rounded-md"
              aria-label="Filter by status"
            >
              <option value="all">All Status</option>
              <option value="connected">Connected</option>
              <option value="disconnected">Disconnected</option>
              <option value="degraded">Degraded</option>
              <option value="error">Error</option>
              <option value="connecting">Connecting</option>
            </select>
          </div>

          {/* Type Filter */}
          <div className="min-w-0">
            <select
              value={filters.type}
              onChange={(e) => setFilters(prev => ({ ...prev, type: e.target.value as DataSourceType | 'all' }))}
              className="block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 text-sm rounded-md"
              aria-label="Filter by type"
            >
              <option value="all">All Types</option>
              <option value="broker">Broker</option>
              <option value="feed">Feed</option>
              <option value="database">Database</option>
              <option value="websocket">WebSocket</option>
              <option value="rest">REST</option>
            </select>
          </div>
        </div>
      </div>

      {/* Error Messages */}
      {error && (
        <div className="px-6 py-4 bg-red-50 border-l-4 border-red-400">
          <div className="text-sm text-red-700">{error}</div>
        </div>
      )}

      {metricsError && (
        <div className="px-6 py-4 bg-yellow-50 border-l-4 border-yellow-400">
          <div className="text-sm text-yellow-700">{metricsError}</div>
        </div>
      )}

      {/* Data Sources Table */}
      <div className="px-6 py-4">
        {filteredDataSources.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            No data sources found
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200" role="table" aria-label="Data sources">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Source
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Performance
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Quality
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {filteredDataSources.map((source) => {
                  const statusDisplay = getStatusDisplay(source.status);
                  const qualityColor = getQualityScoreColor(source.qualityLevel);
                  const StatusIcon = statusDisplay.icon;
                  const isTestingConnection = testingConnections.has(source.id);

                  return (
                    <tr key={source.id} data-testid={`data-source-${source.id}`}>
                      {/* Source */}
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="flex items-center">
                          <div className="flex-shrink-0 h-10 w-10">
                            <div className={clsx(
                              'h-10 w-10 rounded-full flex items-center justify-center',
                              statusDisplay.bgColor
                            )}>
                              <StatusIcon className={clsx('h-5 w-5', statusDisplay.color)} />
                            </div>
                          </div>
                          <div className="ml-4">
                            <div className="text-sm font-medium text-gray-900">{source.name}</div>
                            <div className="text-sm text-gray-500">{source.type}</div>
                            {source.description && (
                              <div className="text-xs text-gray-400 mt-1">{source.description}</div>
                            )}
                          </div>
                        </div>
                      </td>

                      {/* Status */}
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="flex items-center">
                          <StatusIcon
                            className={clsx('h-4 w-4 mr-2', statusDisplay.color)}
                            data-testid={statusDisplay.testId}
                          />
                          <span className="text-sm font-medium capitalize">{source.status}</span>
                        </div>
                        <div className="text-xs text-gray-500 mt-1">
                          Last update: {new Date(source.lastUpdate).toLocaleTimeString()}
                        </div>
                      </td>

                      {/* Performance */}
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="space-y-1">
                          <div className="flex items-center text-sm">
                            <ClockIcon className="h-4 w-4 mr-1 text-gray-400" />
                            {formatLatency(source.latency)}
                          </div>
                          <div className="flex items-center text-sm">
                            <ChartBarIcon className="h-4 w-4 mr-1 text-gray-400" />
                            {formatNumber(source.throughput)}
                          </div>
                          <div className="flex items-center text-sm">
                            <SignalIcon className="h-4 w-4 mr-1 text-gray-400" />
                            {formatPercentage(source.uptime)}
                          </div>
                        </div>
                      </td>

                      {/* Quality */}
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div
                          className={clsx('text-lg font-semibold', qualityColor)}
                          data-testid={`quality-score-${source.id}`}
                        >
                          {source.qualityScore}
                        </div>
                        <div className="text-xs text-gray-500 capitalize">{source.qualityLevel}</div>
                      </td>

                      {/* Actions */}
                      <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                        <button
                          onClick={() => testConnection(source.id, source.name)}
                          disabled={isTestingConnection}
                          data-testid={`test-connection-${source.id}`}
                          className={clsx(
                            'inline-flex items-center px-3 py-2 border border-gray-300 shadow-sm text-sm leading-4 font-medium rounded-md focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500',
                            isTestingConnection
                              ? 'text-gray-400 bg-gray-100 cursor-not-allowed'
                              : 'text-gray-700 bg-white hover:bg-gray-50'
                          )}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter' && !isTestingConnection) {
                              testConnection(source.id, source.name);
                            }
                          }}
                        >
                          {isTestingConnection ? (
                            <>
                              <ArrowPathIcon className="h-4 w-4 mr-1 animate-spin" />
                              Testing...
                            </>
                          ) : (
                            <>
                              <WifiIcon className="h-4 w-4 mr-1" />
                              Test
                            </>
                          )}
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
