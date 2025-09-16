/**
 * AnalyticsDashboard Component
 *
 * Comprehensive analytics dashboard with interactive visualizations, KPI monitoring,
 * and integrated export capabilities
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import {
  AnalyticsService,
  getAnalyticsService,
} from '@/services/analytics';
import {
  MetricsAggregationService,
  getMetricsAggregationService,
} from '@/services/metricsAggregation';
import {
  ExportService,
  getExportService,
} from '@/services/export';
import {
  AnalyticsCategory,
  AnalyticsMetric,
  AnalyticsDataPoint,
  KPI,
  KPIStatus,
  TimeRange,
  TimeInterval,
  TrendAnalysis,
  TrendDirection,
  ExportFormat,
  ChartType,
  StatisticalSummary,
} from '@/types/analytics';

export interface AnalyticsDashboardProps {
  className?: string;
  layout?: DashboardLayout;
  theme?: DashboardTheme;
  defaultTimeRange?: TimeRange;
  autoRefresh?: boolean;
  refreshInterval?: number;
  analyticsService?: AnalyticsService;
  metricsService?: MetricsAggregationService;
  exportService?: ExportService;
  onMetricClick?: (metric: AnalyticsMetric) => void;
  onKPIClick?: (kpi: KPI) => void;
  onExportComplete?: (jobId: string) => void;
  onError?: (error: Error) => void;
}

export enum DashboardLayout {
  OVERVIEW = 'overview',
  DETAILED = 'detailed',
  COMPACT = 'compact',
  FULL_SCREEN = 'full_screen',
}

export enum DashboardTheme {
  LIGHT = 'light',
  DARK = 'dark',
  AUTO = 'auto',
}

interface DashboardState {
  loading: boolean;
  error: string | null;
  metrics: AnalyticsMetric[];
  kpis: KPI[];
  trendData: Record<string, TrendAnalysis>;
  performanceSummary: any;
  timeRange: TimeRange;
  selectedCategory: AnalyticsCategory | null;
  selectedMetrics: string[];
  refreshing: boolean;
  exportJobs: string[];
}

export const AnalyticsDashboard: React.FC<AnalyticsDashboardProps> = ({
  className = '',
  layout = DashboardLayout.OVERVIEW,
  theme = DashboardTheme.LIGHT,
  defaultTimeRange,
  autoRefresh = true,
  refreshInterval = 30000,
  analyticsService,
  metricsService,
  exportService,
  onMetricClick,
  onKPIClick,
  onExportComplete,
  onError,
}) => {
  const [services] = useState(() => ({
    analytics: analyticsService || getAnalyticsService(),
    metrics: metricsService || getMetricsAggregationService(),
    export: exportService || getExportService(),
  }));

  const [state, setState] = useState<DashboardState>(() => ({
    loading: true,
    error: null,
    metrics: [],
    kpis: [],
    trendData: {},
    performanceSummary: null,
    timeRange: defaultTimeRange || {
      start: new Date(Date.now() - 24 * 60 * 60 * 1000), // Last 24 hours
      end: new Date(),
      interval: TimeInterval.HOUR,
    },
    selectedCategory: null,
    selectedMetrics: [],
    refreshing: false,
    exportJobs: [],
  }));

  // Load dashboard data
  const loadDashboardData = useCallback(async (showRefreshing = false) => {
    if (showRefreshing) {
      setState(prev => ({ ...prev, refreshing: true }));
    } else {
      setState(prev => ({ ...prev, loading: true, error: null }));
    }

    try {
      // Load data in parallel
      const [metrics, performanceSummary] = await Promise.all([
        services.analytics.getMetrics(state.selectedCategory || undefined),
        services.metrics.getPerformanceSummary(state.selectedCategory || undefined),
      ]);

      // Load trend data for selected metrics
      const selectedMetrics = state.selectedMetrics.length > 0
        ? state.selectedMetrics
        : metrics.slice(0, 5).map(m => m.name);

      const trendPromises = selectedMetrics.map(async (metricName) => {
        try {
          const trend = await services.analytics.analyzeTrend(metricName, state.timeRange);
          return [metricName, trend] as const;
        } catch (error) {
          console.warn(`Failed to load trend for ${metricName}:`, error);
          return null;
        }
      });

      const trendResults = await Promise.all(trendPromises);
      const trendData = Object.fromEntries(
        trendResults.filter((result): result is [string, TrendAnalysis] => result !== null)
      );

      setState(prev => ({
        ...prev,
        loading: false,
        refreshing: false,
        error: null,
        metrics,
        kpis: performanceSummary.kpis,
        performanceSummary: performanceSummary.summary,
        trendData,
        selectedMetrics: selectedMetrics,
      }));
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to load dashboard data';
      setState(prev => ({
        ...prev,
        loading: false,
        refreshing: false,
        error: errorMessage,
      }));
      onError?.(error instanceof Error ? error : new Error(errorMessage));
    }
  }, [services, state.selectedCategory, state.selectedMetrics, state.timeRange, onError]);

  // Initial load
  useEffect(() => {
    loadDashboardData();
  }, [loadDashboardData]);

  // Auto-refresh setup
  useEffect(() => {
    if (!autoRefresh) return;

    const interval = setInterval(() => {
      loadDashboardData(true);
    }, refreshInterval);

    return () => clearInterval(interval);
  }, [autoRefresh, refreshInterval, loadDashboardData]);

  // Handle time range change
  const handleTimeRangeChange = useCallback((newTimeRange: TimeRange) => {
    setState(prev => ({ ...prev, timeRange: newTimeRange }));
  }, []);

  // Handle category filter
  const handleCategoryChange = useCallback((category: AnalyticsCategory | null) => {
    setState(prev => ({ ...prev, selectedCategory: category }));
  }, []);

  // Handle metric selection
  const handleMetricSelection = useCallback((metricNames: string[]) => {
    setState(prev => ({ ...prev, selectedMetrics: metricNames }));
  }, []);

  // Export functions
  const handleExportChart = useCallback(async (chartConfig: any, format: ExportFormat) => {
    try {
      const job = await services.export.exportChart(chartConfig, format);
      setState(prev => ({
        ...prev,
        exportJobs: [...prev.exportJobs, job.id]
      }));
      onExportComplete?.(job.id);
    } catch (error) {
      onError?.(error instanceof Error ? error : new Error('Export failed'));
    }
  }, [services.export, onExportComplete, onError]);

  const handleExportData = useCallback(async (metricNames: string[], format: ExportFormat) => {
    try {
      const query = {
        timeRange: state.timeRange,
        metrics: metricNames,
      };
      const job = await services.export.exportData(query, format);
      setState(prev => ({
        ...prev,
        exportJobs: [...prev.exportJobs, job.id]
      }));
      onExportComplete?.(job.id);
    } catch (error) {
      onError?.(error instanceof Error ? error : new Error('Export failed'));
    }
  }, [services.export, state.timeRange, onExportComplete, onError]);

  // Memoized chart data
  const chartData = useMemo(() => {
    if (!state.metrics.length) return [];

    return state.metrics.map(metric => ({
      name: metric.name,
      value: metric.value,
      category: metric.category,
      unit: metric.unit,
      timestamp: metric.timestamp.toISOString(),
    }));
  }, [state.metrics]);

  // KPI status colors
  const getKPIStatusColor = (status: KPIStatus) => {
    switch (status) {
      case KPIStatus.EXCELLENT:
        return 'text-green-600 bg-green-100';
      case KPIStatus.GOOD:
        return 'text-blue-600 bg-blue-100';
      case KPIStatus.WARNING:
        return 'text-yellow-600 bg-yellow-100';
      case KPIStatus.CRITICAL:
        return 'text-red-600 bg-red-100';
      default:
        return 'text-gray-600 bg-gray-100';
    }
  };

  // Trend direction icon
  const getTrendIcon = (direction: TrendDirection) => {
    switch (direction) {
      case TrendDirection.INCREASING:
        return '↗️';
      case TrendDirection.DECREASING:
        return '↘️';
      case TrendDirection.STABLE:
        return '→';
      case TrendDirection.VOLATILE:
        return '↕️';
      default:
        return '?';
    }
  };

  // Loading state
  if (state.loading) {
    return (
      <div className={`flex items-center justify-center h-64 ${className}`} data-testid="analytics-dashboard-loading">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading analytics dashboard...</p>
        </div>
      </div>
    );
  }

  // Error state
  if (state.error) {
    return (
      <div className={`bg-red-50 border border-red-200 rounded-lg p-6 ${className}`} data-testid="analytics-dashboard-error">
        <div className="flex items-center space-x-3">
          <div className="text-red-600 text-xl">⚠️</div>
          <div>
            <h3 className="text-red-800 font-medium">Dashboard Error</h3>
            <p className="text-red-600">{state.error}</p>
            <button
              onClick={() => loadDashboardData()}
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
    <div className={`analytics-dashboard space-y-6 ${className}`} data-testid="analytics-dashboard">
      {/* Dashboard Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between space-y-4 sm:space-y-0">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Analytics Dashboard</h2>
          <p className="text-gray-600">
            Real-time performance analytics and KPI monitoring
            {state.refreshing && (
              <span className="ml-2 text-blue-600">
                <span className="animate-spin inline-block w-4 h-4 border-2 border-blue-600 border-t-transparent rounded-full"></span>
                Refreshing...
              </span>
            )}
          </p>
        </div>

        <div className="flex items-center space-x-4">
          {/* Category Filter */}
          <select
            value={state.selectedCategory || ''}
            onChange={(e) => handleCategoryChange(e.target.value as AnalyticsCategory || null)}
            className="rounded border-gray-300 text-sm"
            data-testid="category-filter"
          >
            <option value="">All Categories</option>
            {Object.values(AnalyticsCategory).map(category => (
              <option key={category} value={category}>
                {category.replace('_', ' ').toUpperCase()}
              </option>
            ))}
          </select>

          {/* Refresh Button */}
          <button
            onClick={() => loadDashboardData(true)}
            disabled={state.refreshing}
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
            data-testid="refresh-button"
          >
            {state.refreshing ? 'Refreshing...' : 'Refresh'}
          </button>

          {/* Export Menu */}
          <div className="relative">
            <select
              onChange={(e) => {
                if (e.target.value) {
                  handleExportData(state.selectedMetrics, e.target.value as ExportFormat);
                  e.target.value = '';
                }
              }}
              className="rounded border-gray-300 text-sm"
              data-testid="export-select"
            >
              <option value="">Export Data</option>
              <option value={ExportFormat.CSV}>CSV</option>
              <option value={ExportFormat.EXCEL}>Excel</option>
              <option value={ExportFormat.JSON}>JSON</option>
            </select>
          </div>
        </div>
      </div>

      {/* KPI Summary Cards */}
      {state.performanceSummary && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4" data-testid="kpi-summary">
          <div className="bg-white rounded-lg p-6 shadow border">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">Total KPIs</p>
                <p className="text-3xl font-bold text-gray-900">{state.performanceSummary.total}</p>
              </div>
              <div className="text-2xl">📊</div>
            </div>
          </div>

          <div className="bg-white rounded-lg p-6 shadow border">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">Excellent</p>
                <p className="text-3xl font-bold text-green-600">{state.performanceSummary.excellent}</p>
              </div>
              <div className="text-2xl">✅</div>
            </div>
          </div>

          <div className="bg-white rounded-lg p-6 shadow border">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">Warnings</p>
                <p className="text-3xl font-bold text-yellow-600">{state.performanceSummary.warning}</p>
              </div>
              <div className="text-2xl">⚠️</div>
            </div>
          </div>

          <div className="bg-white rounded-lg p-6 shadow border">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">Critical</p>
                <p className="text-3xl font-bold text-red-600">{state.performanceSummary.critical}</p>
              </div>
              <div className="text-2xl">🚨</div>
            </div>
          </div>
        </div>
      )}

      {/* Main Dashboard Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
        {/* Metrics Overview Chart */}
        <div className="xl:col-span-2 bg-white rounded-lg p-6 shadow border" data-testid="metrics-chart">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-medium text-gray-900">Metrics Overview</h3>
            <button
              onClick={() => handleExportChart({
                type: ChartType.BAR,
                data: chartData,
                title: 'Metrics Overview'
              }, ExportFormat.PNG)}
              className="text-sm text-blue-600 hover:text-blue-800"
              data-testid="export-chart-button"
            >
              Export Chart
            </button>
          </div>

          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" angle={-45} textAnchor="end" height={100} />
              <YAxis />
              <Tooltip />
              <Legend />
              <Bar dataKey="value" fill="#3B82F6" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* KPI Status List */}
        <div className="bg-white rounded-lg p-6 shadow border" data-testid="kpi-list">
          <h3 className="text-lg font-medium text-gray-900 mb-4">Key Performance Indicators</h3>
          <div className="space-y-3 max-h-80 overflow-y-auto">
            {state.kpis.slice(0, 10).map((kpi) => (
              <div
                key={kpi.id}
                className="flex items-center justify-between p-3 border rounded cursor-pointer hover:bg-gray-50"
                onClick={() => onKPIClick?.(kpi)}
                data-testid={`kpi-item-${kpi.id}`}
              >
                <div className="flex-1">
                  <div className="flex items-center space-x-2">
                    <p className="font-medium text-sm">{kpi.name}</p>
                    <span className={`px-2 py-1 rounded-full text-xs ${getKPIStatusColor(kpi.status)}`}>
                      {kpi.status}
                    </span>
                  </div>
                  <p className="text-sm text-gray-600">
                    {kpi.currentValue.toFixed(2)} {kpi.unit}
                    {kpi.trend && (
                      <span className="ml-2">
                        {getTrendIcon(kpi.trend)}
                      </span>
                    )}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Trend Analysis */}
        <div className="xl:col-span-2 bg-white rounded-lg p-6 shadow border" data-testid="trend-analysis">
          <h3 className="text-lg font-medium text-gray-900 mb-4">Trend Analysis</h3>

          {Object.entries(state.trendData).length > 0 ? (
            <div className="space-y-4">
              {Object.entries(state.trendData).slice(0, 3).map(([metricName, trend]) => (
                <div key={metricName} className="border rounded p-4" data-testid={`trend-${metricName}`}>
                  <div className="flex items-center justify-between mb-2">
                    <h4 className="font-medium">{metricName}</h4>
                    <div className="flex items-center space-x-2">
                      <span className="text-sm text-gray-600">
                        {getTrendIcon(trend.trend)} {trend.trend}
                      </span>
                      <span className="text-sm text-gray-500">
                        ({(trend.confidence * 100).toFixed(1)}% confidence)
                      </span>
                    </div>
                  </div>

                  {trend.forecast && trend.forecast.length > 0 && (
                    <div className="mt-2">
                      <ResponsiveContainer width="100%" height={150}>
                        <LineChart data={trend.forecast.map(f => ({
                          time: f.timestamp.toLocaleTimeString(),
                          value: f.value,
                          upperBound: f.upperBound,
                          lowerBound: f.lowerBound,
                        }))}>
                          <XAxis dataKey="time" />
                          <YAxis />
                          <Tooltip />
                          <Line type="monotone" dataKey="value" stroke="#3B82F6" strokeWidth={2} />
                          <Line type="monotone" dataKey="upperBound" stroke="#93C5FD" strokeDasharray="5 5" />
                          <Line type="monotone" dataKey="lowerBound" stroke="#93C5FD" strokeDasharray="5 5" />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8 text-gray-500">
              <p>No trend data available</p>
              <p className="text-sm">Select metrics to view trend analysis</p>
            </div>
          )}
        </div>

        {/* Category Distribution */}
        <div className="bg-white rounded-lg p-6 shadow border" data-testid="category-distribution">
          <h3 className="text-lg font-medium text-gray-900 mb-4">Category Distribution</h3>

          {state.metrics.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <PieChart>
                <Pie
                  data={Object.entries(
                    state.metrics.reduce((acc, metric) => {
                      acc[metric.category] = (acc[metric.category] || 0) + 1;
                      return acc;
                    }, {} as Record<string, number>)
                  ).map(([category, count]) => ({ name: category, value: count }))}
                  cx="50%"
                  cy="50%"
                  outerRadius={80}
                  fill="#8884d8"
                  dataKey="value"
                  label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                >
                  {Object.keys(AnalyticsCategory).map((_, index) => (
                    <Cell key={`cell-${index}`} fill={`hsl(${index * 45}, 70%, 60%)`} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="text-center py-8 text-gray-500">
              <p>No metrics available</p>
            </div>
          )}
        </div>
      </div>

      {/* Recent Metrics Table */}
      <div className="bg-white rounded-lg shadow border" data-testid="metrics-table">
        <div className="px-6 py-4 border-b border-gray-200">
          <h3 className="text-lg font-medium text-gray-900">Recent Metrics</h3>
        </div>

        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Metric
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Category
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Value
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Unit
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Timestamp
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {state.metrics.slice(0, 10).map((metric) => (
                <tr
                  key={metric.id}
                  className="hover:bg-gray-50 cursor-pointer"
                  onClick={() => onMetricClick?.(metric)}
                  data-testid={`metric-row-${metric.id}`}
                >
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="text-sm font-medium text-gray-900">{metric.name}</div>
                    <div className="text-sm text-gray-500">{metric.description}</div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-blue-100 text-blue-800">
                      {metric.category}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {typeof metric.value === 'number' ? metric.value.toFixed(2) : metric.value}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {metric.unit}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {metric.timestamp.toLocaleString()}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleExportData([metric.name], ExportFormat.CSV);
                      }}
                      className="text-blue-600 hover:text-blue-900"
                    >
                      Export
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {state.metrics.length === 0 && (
          <div className="text-center py-8 text-gray-500">
            <p>No metrics available</p>
            <p className="text-sm">Check your data sources and try refreshing</p>
          </div>
        )}
      </div>
    </div>
  );
};
