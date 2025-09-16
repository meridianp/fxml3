/**
 * PerformanceScorecard Component
 *
 * Focused KPI tracking and performance monitoring dashboard with visual scorecards
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
  RadialBarChart,
  RadialBar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import {
  MetricsAggregationService,
  getMetricsAggregationService,
} from '@/services/metricsAggregation';
import {
  AnalyticsService,
  getAnalyticsService,
} from '@/services/analytics';
import {
  ExportService,
  getExportService,
} from '@/services/export';
import {
  KPI,
  KPIStatus,
  KPIThresholds,
  AnalyticsCategory,
  AnalyticsDataPoint,
  TimeRange,
  TimeInterval,
  TrendDirection,
  ExportFormat,
} from '@/types/analytics';

export interface PerformanceScorecardProps {
  className?: string;
  layout?: ScorecardLayout;
  categories?: AnalyticsCategory[];
  refreshInterval?: number;
  autoRefresh?: boolean;
  showTrends?: boolean;
  showScores?: boolean;
  compactMode?: boolean;
  metricsService?: MetricsAggregationService;
  analyticsService?: AnalyticsService;
  exportService?: ExportService;
  onKPIClick?: (kpi: KPI) => void;
  onCategoryClick?: (category: AnalyticsCategory) => void;
  onScoreChange?: (score: PerformanceScore) => void;
  onExport?: (jobId: string) => void;
  onError?: (error: Error) => void;
}

export enum ScorecardLayout {
  GRID = 'grid',
  LIST = 'list',
  COMPACT = 'compact',
  DETAILED = 'detailed',
}

interface PerformanceScore {
  overall: number;
  categoryScores: Record<AnalyticsCategory, number>;
  trend: TrendDirection;
  lastUpdated: Date;
}

interface ScorecardState {
  loading: boolean;
  error: string | null;
  kpis: KPI[];
  performanceScore: PerformanceScore | null;
  categoryKPIs: Record<AnalyticsCategory, KPI[]>;
  trendData: Record<string, AnalyticsDataPoint[]>;
  selectedCategory: AnalyticsCategory | null;
  refreshing: boolean;
}

export const PerformanceScorecard: React.FC<PerformanceScorecardProps> = ({
  className = '',
  layout = ScorecardLayout.GRID,
  categories = Object.values(AnalyticsCategory),
  refreshInterval = 30000,
  autoRefresh = true,
  showTrends = true,
  showScores = true,
  compactMode = false,
  metricsService,
  analyticsService,
  exportService,
  onKPIClick,
  onCategoryClick,
  onScoreChange,
  onExport,
  onError,
}) => {
  const [services] = useState(() => ({
    metrics: metricsService || getMetricsAggregationService(),
    analytics: analyticsService || getAnalyticsService(),
    export: exportService || getExportService(),
  }));

  const [state, setState] = useState<ScorecardState>(() => ({
    loading: true,
    error: null,
    kpis: [],
    performanceScore: null,
    categoryKPIs: {} as Record<AnalyticsCategory, KPI[]>,
    trendData: {},
    selectedCategory: null,
    refreshing: false,
  }));

  // Load performance data
  const loadPerformanceData = useCallback(async (showRefreshing = false) => {
    if (showRefreshing) {
      setState(prev => ({ ...prev, refreshing: true }));
    } else {
      setState(prev => ({ ...prev, loading: true, error: null }));
    }

    try {
      // Load KPIs for each category
      const categoryPromises = categories.map(async (category) => {
        const kpis = await services.metrics.getKPIs(category);
        return [category, kpis] as const;
      });

      const categoryResults = await Promise.all(categoryPromises);
      const categoryKPIs = Object.fromEntries(categoryResults) as Record<AnalyticsCategory, KPI[]>;
      const allKPIs = categoryResults.flatMap(([, kpis]) => kpis);

      // Load trend data for top KPIs if enabled
      const trendData: Record<string, AnalyticsDataPoint[]> = {};
      if (showTrends) {
        const topKPIs = allKPIs.slice(0, 8); // Top 8 KPIs for performance
        const timeRange: TimeRange = {
          start: new Date(Date.now() - 24 * 60 * 60 * 1000), // Last 24 hours
          end: new Date(),
          interval: TimeInterval.HOUR,
        };

        const trendPromises = topKPIs.map(async (kpi) => {
          try {
            const data = await services.analytics.getHistoricalData(kpi.metric, timeRange);
            return [kpi.id, data] as const;
          } catch (error) {
            console.warn(`Failed to load trend data for KPI ${kpi.id}:`, error);
            return [kpi.id, []] as const;
          }
        });

        const trendResults = await Promise.all(trendPromises);
        Object.assign(trendData, Object.fromEntries(trendResults));
      }

      // Calculate performance score
      const performanceScore = calculatePerformanceScore(allKPIs, categoryKPIs);

      setState(prev => ({
        ...prev,
        loading: false,
        refreshing: false,
        error: null,
        kpis: allKPIs,
        categoryKPIs,
        trendData,
        performanceScore,
      }));

      onScoreChange?.(performanceScore);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to load performance data';
      setState(prev => ({
        ...prev,
        loading: false,
        refreshing: false,
        error: errorMessage,
      }));
      onError?.(error instanceof Error ? error : new Error(errorMessage));
    }
  }, [categories, services, showTrends, onScoreChange, onError]);

  // Initial load
  useEffect(() => {
    loadPerformanceData();
  }, [loadPerformanceData]);

  // Auto-refresh setup
  useEffect(() => {
    if (!autoRefresh) return;

    const interval = setInterval(() => {
      loadPerformanceData(true);
    }, refreshInterval);

    return () => clearInterval(interval);
  }, [autoRefresh, refreshInterval, loadPerformanceData]);

  // Calculate performance score
  const calculatePerformanceScore = (kpis: KPI[], categoryKPIs: Record<AnalyticsCategory, KPI[]>): PerformanceScore => {
    if (kpis.length === 0) {
      return {
        overall: 0,
        categoryScores: {} as Record<AnalyticsCategory, number>,
        trend: TrendDirection.UNKNOWN,
        lastUpdated: new Date(),
      };
    }

    // Calculate category scores
    const categoryScores: Record<AnalyticsCategory, number> = {} as any;

    Object.entries(categoryKPIs).forEach(([category, kpis]) => {
      if (kpis.length === 0) {
        categoryScores[category as AnalyticsCategory] = 0;
        return;
      }

      const categoryScore = kpis.reduce((sum, kpi) => {
        const statusScore = getKPIStatusScore(kpi.status);
        return sum + statusScore;
      }, 0) / kpis.length;

      categoryScores[category as AnalyticsCategory] = Math.round(categoryScore);
    });

    // Calculate overall score
    const overallScore = Object.values(categoryScores).reduce((sum, score) => sum + score, 0) / Object.keys(categoryScores).length;

    // Determine overall trend
    const trends = kpis.map(kpi => kpi.trend).filter(trend => trend !== TrendDirection.UNKNOWN);
    const increasingCount = trends.filter(t => t === TrendDirection.INCREASING).length;
    const decreasingCount = trends.filter(t => t === TrendDirection.DECREASING).length;

    let overallTrend: TrendDirection;
    if (increasingCount > decreasingCount * 1.5) {
      overallTrend = TrendDirection.INCREASING;
    } else if (decreasingCount > increasingCount * 1.5) {
      overallTrend = TrendDirection.DECREASING;
    } else {
      overallTrend = TrendDirection.STABLE;
    }

    return {
      overall: Math.round(overallScore),
      categoryScores,
      trend: overallTrend,
      lastUpdated: new Date(),
    };
  };

  // Get score for KPI status
  const getKPIStatusScore = (status: KPIStatus): number => {
    switch (status) {
      case KPIStatus.EXCELLENT: return 100;
      case KPIStatus.GOOD: return 80;
      case KPIStatus.WARNING: return 60;
      case KPIStatus.CRITICAL: return 30;
      default: return 50;
    }
  };

  // Handle category selection
  const handleCategorySelect = useCallback((category: AnalyticsCategory | null) => {
    setState(prev => ({ ...prev, selectedCategory: category }));
    if (category) {
      onCategoryClick?.(category);
    }
  }, [onCategoryClick]);

  // Handle KPI click
  const handleKPIClick = useCallback((kpi: KPI) => {
    onKPIClick?.(kpi);
  }, [onKPIClick]);

  // Export scorecard
  const handleExportScorecard = useCallback(async (format: ExportFormat) => {
    try {
      const chartConfig = {
        title: 'Performance Scorecard',
        data: state.performanceScore,
        kpis: state.kpis,
        categories: categories,
      };

      const job = await services.export.exportChart(chartConfig, format);
      onExport?.(job.id);
    } catch (error) {
      onError?.(error instanceof Error ? error : new Error('Export failed'));
    }
  }, [services.export, state.performanceScore, state.kpis, categories, onExport, onError]);

  // Get status color classes
  const getStatusColor = (status: KPIStatus) => {
    switch (status) {
      case KPIStatus.EXCELLENT:
        return 'text-green-600 bg-green-100 border-green-200';
      case KPIStatus.GOOD:
        return 'text-blue-600 bg-blue-100 border-blue-200';
      case KPIStatus.WARNING:
        return 'text-yellow-600 bg-yellow-100 border-yellow-200';
      case KPIStatus.CRITICAL:
        return 'text-red-600 bg-red-100 border-red-200';
      default:
        return 'text-gray-600 bg-gray-100 border-gray-200';
    }
  };

  // Get score color
  const getScoreColor = (score: number) => {
    if (score >= 90) return 'text-green-600';
    if (score >= 75) return 'text-blue-600';
    if (score >= 60) return 'text-yellow-600';
    return 'text-red-600';
  };

  // Get trend icon
  const getTrendIcon = (trend: TrendDirection) => {
    switch (trend) {
      case TrendDirection.INCREASING: return '📈';
      case TrendDirection.DECREASING: return '📉';
      case TrendDirection.STABLE: return '📊';
      case TrendDirection.VOLATILE: return '📊';
      default: return '❓';
    }
  };

  // Filtered KPIs based on selected category
  const filteredKPIs = useMemo(() => {
    if (!state.selectedCategory) return state.kpis;
    return state.categoryKPIs[state.selectedCategory] || [];
  }, [state.kpis, state.categoryKPIs, state.selectedCategory]);

  // Performance chart data
  const performanceChartData = useMemo(() => {
    if (!state.performanceScore) return [];

    return Object.entries(state.performanceScore.categoryScores).map(([category, score]) => ({
      category: category.replace('_', ' ').toUpperCase(),
      score,
      fullMark: 100,
    }));
  }, [state.performanceScore]);

  // Loading state
  if (state.loading) {
    return (
      <div className={`flex items-center justify-center h-64 ${className}`} data-testid="scorecard-loading">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading performance scorecard...</p>
        </div>
      </div>
    );
  }

  // Error state
  if (state.error) {
    return (
      <div className={`bg-red-50 border border-red-200 rounded-lg p-6 ${className}`} data-testid="scorecard-error">
        <div className="flex items-center space-x-3">
          <div className="text-red-600 text-xl">⚠️</div>
          <div>
            <h3 className="text-red-800 font-medium">Scorecard Error</h3>
            <p className="text-red-600">{state.error}</p>
            <button
              onClick={() => loadPerformanceData()}
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
    <div className={`performance-scorecard space-y-6 ${className}`} data-testid="performance-scorecard">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between space-y-4 sm:space-y-0">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Performance Scorecard</h2>
          <p className="text-gray-600">
            Real-time KPI monitoring and performance tracking
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
            onChange={(e) => handleCategorySelect(e.target.value as AnalyticsCategory || null)}
            className="rounded border-gray-300 text-sm"
            data-testid="category-filter"
          >
            <option value="">All Categories</option>
            {categories.map(category => (
              <option key={category} value={category}>
                {category.replace('_', ' ').toUpperCase()}
              </option>
            ))}
          </select>

          {/* Export Button */}
          <select
            onChange={(e) => {
              if (e.target.value) {
                handleExportScorecard(e.target.value as ExportFormat);
                e.target.value = '';
              }
            }}
            className="rounded border-gray-300 text-sm"
            data-testid="export-select"
          >
            <option value="">Export</option>
            <option value={ExportFormat.PNG}>PNG</option>
            <option value={ExportFormat.PDF}>PDF</option>
            <option value={ExportFormat.CSV}>CSV</option>
          </select>

          {/* Refresh Button */}
          <button
            onClick={() => loadPerformanceData(true)}
            disabled={state.refreshing}
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
            data-testid="refresh-button"
          >
            {state.refreshing ? 'Refreshing...' : 'Refresh'}
          </button>
        </div>
      </div>

      {/* Performance Score Overview */}
      {showScores && state.performanceScore && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6" data-testid="performance-overview">
          {/* Overall Score */}
          <div className="bg-white rounded-lg p-6 shadow border">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-medium text-gray-900">Overall Performance</h3>
              <div className="text-2xl">{getTrendIcon(state.performanceScore.trend)}</div>
            </div>

            <div className="text-center">
              <div className={`text-4xl font-bold mb-2 ${getScoreColor(state.performanceScore.overall)}`}>
                {state.performanceScore.overall}
              </div>
              <div className="text-sm text-gray-500">
                Score out of 100
              </div>
              <div className="text-xs text-gray-400 mt-2">
                Last updated: {state.performanceScore.lastUpdated.toLocaleTimeString()}
              </div>
            </div>

            {/* Radial Progress */}
            <div className="mt-4">
              <ResponsiveContainer width="100%" height={150}>
                <RadialBarChart cx="50%" cy="50%" innerRadius="60%" outerRadius="90%" data={[{
                  name: 'Score',
                  value: state.performanceScore.overall,
                  fill: state.performanceScore.overall >= 75 ? '#10B981' :
                        state.performanceScore.overall >= 60 ? '#F59E0B' : '#EF4444'
                }]}>
                  <RadialBar dataKey="value" cornerRadius={10} fill="#8884d8" />
                </RadialBarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Category Scores */}
          <div className="lg:col-span-2 bg-white rounded-lg p-6 shadow border">
            <h3 className="text-lg font-medium text-gray-900 mb-4">Category Performance</h3>

            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={performanceChartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="category" angle={-45} textAnchor="end" height={80} />
                <YAxis domain={[0, 100]} />
                <Tooltip />
                <Bar dataKey="score" fill="#3B82F6" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* KPI Cards */}
      <div className={`grid gap-4 ${
        layout === ScorecardLayout.GRID ? 'grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4' :
        layout === ScorecardLayout.COMPACT ? 'grid-cols-1 md:grid-cols-2' :
        'grid-cols-1'
      }`} data-testid="kpi-cards">
        {filteredKPIs.map((kpi) => (
          <div
            key={kpi.id}
            className={`bg-white rounded-lg shadow border cursor-pointer hover:shadow-md transition-shadow ${
              compactMode ? 'p-4' : 'p-6'
            }`}
            onClick={() => handleKPIClick(kpi)}
            data-testid={`kpi-card-${kpi.id}`}
          >
            <div className="flex items-center justify-between mb-2">
              <h4 className={`font-medium text-gray-900 ${compactMode ? 'text-sm' : 'text-base'}`}>
                {kpi.name}
              </h4>
              <span className={`px-2 py-1 rounded-full text-xs font-medium border ${getStatusColor(kpi.status)}`}>
                {kpi.status}
              </span>
            </div>

            <div className="flex items-center justify-between">
              <div>
                <div className={`font-bold ${getScoreColor(getKPIStatusScore(kpi.status))} ${
                  compactMode ? 'text-xl' : 'text-2xl'
                }`}>
                  {typeof kpi.currentValue === 'number' ? kpi.currentValue.toFixed(1) : kpi.currentValue}
                  <span className="text-sm text-gray-500 ml-1">{kpi.unit}</span>
                </div>
                {kpi.target && (
                  <div className="text-xs text-gray-500">
                    Target: {kpi.target} {kpi.unit}
                  </div>
                )}
              </div>

              {kpi.trend && kpi.trend !== TrendDirection.UNKNOWN && (
                <div className="text-lg">
                  {getTrendIcon(kpi.trend)}
                </div>
              )}
            </div>

            {/* Mini trend chart if data available */}
            {showTrends && state.trendData[kpi.id] && state.trendData[kpi.id].length > 0 && (
              <div className="mt-3">
                <ResponsiveContainer width="100%" height={40}>
                  <LineChart data={state.trendData[kpi.id].slice(-12).map((point, index) => ({
                    index,
                    value: point.metrics[kpi.metric] || 0,
                  }))}>
                    <Line
                      type="monotone"
                      dataKey="value"
                      stroke="#3B82F6"
                      strokeWidth={2}
                      dot={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}

            {!compactMode && kpi.description && (
              <p className="text-xs text-gray-600 mt-2">{kpi.description}</p>
            )}
          </div>
        ))}
      </div>

      {/* No KPIs Message */}
      {filteredKPIs.length === 0 && (
        <div className="text-center py-12" data-testid="no-kpis-message">
          <div className="text-gray-400 text-6xl mb-4">📊</div>
          <h3 className="text-lg font-medium text-gray-900 mb-2">No KPIs Available</h3>
          <p className="text-gray-600">
            {state.selectedCategory
              ? `No KPIs found for ${state.selectedCategory.replace('_', ' ')} category`
              : 'No performance indicators configured'
            }
          </p>
          {state.selectedCategory && (
            <button
              onClick={() => handleCategorySelect(null)}
              className="mt-4 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
            >
              Show All Categories
            </button>
          )}
        </div>
      )}
    </div>
  );
};
