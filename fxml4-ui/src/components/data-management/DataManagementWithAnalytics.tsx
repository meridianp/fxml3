/**
 * DataManagementWithAnalytics Component
 *
 * Enhanced data management dashboard with integrated analytics capabilities
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { DataManagementDashboard, DashboardLayout, DashboardTheme } from './DataManagementDashboard';
import { AnalyticsDashboard, DashboardLayout as AnalyticsDashboardLayout } from '@/components/analytics/AnalyticsDashboard';
import { PerformanceScorecard, ScorecardLayout } from '@/components/analytics/PerformanceScorecard';
import { ReportsManager } from '@/components/analytics/ReportsManager';
import { ExportManager } from '@/components/analytics/ExportManager';
import {
  AnalyticsIntegrationService,
  getAnalyticsIntegrationService,
  DataManagementAnalytics
} from '@/services/analyticsIntegration';
import { DataSourceService } from '@/services/dataSource';
import { StorageMetricsService } from '@/services/storageMetrics';
import { DataQualityService } from '@/services/dataQuality';
import { PipelineService } from '@/services/pipeline';
import { NotificationService } from '@/services/notification';
import {
  DataManagementAlert,
  DataSourceStatusEvent,
  StorageStatusEvent,
  QualityStatusEvent,
  PipelineStatusEvent,
} from '@/types/dataManagement';
import {
  SystemHealth,
  KPI,
  TimeRange,
  TimeInterval,
  AnalyticsCategory,
} from '@/types/analytics';

export interface DataManagementWithAnalyticsProps {
  className?: string;
  style?: React.CSSProperties;
  title?: string;

  // Layout and theming
  initialLayout?: DashboardLayout;
  initialTheme?: DashboardTheme;
  showAnalytics?: boolean;
  analyticsLayout?: AnalyticsViewLayout;

  // Refresh configuration
  autoRefresh?: boolean;
  refreshInterval?: number;

  // Service instances
  dataSourceService?: DataSourceService;
  storageMetricsService?: StorageMetricsService;
  dataQualityService?: DataQualityService;
  pipelineService?: PipelineService;
  notificationService?: NotificationService;
  analyticsIntegrationService?: AnalyticsIntegrationService;

  // Event callbacks
  onAlert?: (alert: DataManagementAlert) => void;
  onAnalyticsUpdate?: (analytics: DataManagementAnalytics) => void;
  onError?: (error: Error) => void;
}

export enum AnalyticsViewLayout {
  SIDE_BY_SIDE = 'side-by-side',
  TABBED = 'tabbed',
  INTEGRATED = 'integrated',
  MODAL = 'modal',
}

interface IntegratedDashboardState {
  currentView: 'data-management' | 'analytics' | 'reports' | 'exports';
  analyticsData: DataManagementAnalytics | null;
  systemHealth: SystemHealth | null;
  loading: boolean;
  error: string | null;
  showAnalyticsPanel: boolean;
  analyticsTimeRange: TimeRange;
}

export const DataManagementWithAnalytics: React.FC<DataManagementWithAnalyticsProps> = ({
  className = '',
  style = {},
  title = 'Integrated Data Management & Analytics',
  initialLayout = DashboardLayout.DEFAULT,
  initialTheme = DashboardTheme.LIGHT,
  showAnalytics = true,
  analyticsLayout = AnalyticsViewLayout.SIDE_BY_SIDE,
  autoRefresh = true,
  refreshInterval = 30000,
  dataSourceService,
  storageMetricsService,
  dataQualityService,
  pipelineService,
  notificationService,
  analyticsIntegrationService,
  onAlert,
  onAnalyticsUpdate,
  onError,
}) => {
  const [integrationService] = useState(() =>
    analyticsIntegrationService || getAnalyticsIntegrationService()
  );

  const [state, setState] = useState<IntegratedDashboardState>(() => ({
    currentView: 'data-management',
    analyticsData: null,
    systemHealth: null,
    loading: true,
    error: null,
    showAnalyticsPanel: showAnalytics,
    analyticsTimeRange: {
      start: new Date(Date.now() - 24 * 60 * 60 * 1000), // Last 24 hours
      end: new Date(),
      interval: TimeInterval.HOUR,
    },
  }));

  // Initialize analytics integration
  useEffect(() => {
    const initializeAnalytics = async () => {
      try {
        await integrationService.initialize({
          dataSource: dataSourceService,
          storage: storageMetricsService,
          dataQuality: dataQualityService,
          pipeline: pipelineService,
        });

        // Subscribe to analytics updates
        const unsubscribe = integrationService.onAnalyticsUpdate((analytics) => {
          setState(prev => ({
            ...prev,
            analyticsData: analytics,
            systemHealth: analytics.systemHealth,
            loading: false,
          }));
          onAnalyticsUpdate?.(analytics);
        });

        // Initial analytics generation
        const initialAnalytics = await integrationService.generateDataManagementAnalytics(
          state.analyticsTimeRange
        );

        setState(prev => ({
          ...prev,
          analyticsData: initialAnalytics,
          systemHealth: initialAnalytics.systemHealth,
          loading: false,
        }));

        return unsubscribe;
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : 'Failed to initialize analytics';
        setState(prev => ({ ...prev, error: errorMessage, loading: false }));
        onError?.(error instanceof Error ? error : new Error(errorMessage));
      }
    };

    initializeAnalytics();
  }, [integrationService, dataSourceService, storageMetricsService, dataQualityService, pipelineService, state.analyticsTimeRange, onAnalyticsUpdate, onError]);

  // Handle view switching
  const handleViewChange = useCallback((view: typeof state.currentView) => {
    setState(prev => ({ ...prev, currentView: view }));
  }, []);

  // Handle analytics panel toggle
  const toggleAnalyticsPanel = useCallback(() => {
    setState(prev => ({ ...prev, showAnalyticsPanel: !prev.showAnalyticsPanel }));
  }, []);

  // Handle time range change
  const handleTimeRangeChange = useCallback(async (timeRange: TimeRange) => {
    setState(prev => ({ ...prev, analyticsTimeRange: timeRange, loading: true }));

    try {
      const analytics = await integrationService.generateDataManagementAnalytics(timeRange);
      setState(prev => ({
        ...prev,
        analyticsData: analytics,
        systemHealth: analytics.systemHealth,
        loading: false,
      }));
    } catch (error) {
      setState(prev => ({ ...prev, loading: false }));
      onError?.(error instanceof Error ? error : new Error('Failed to update analytics'));
    }
  }, [integrationService, onError]);

  // Enhanced alert handler that includes analytics context
  const handleEnhancedAlert = useCallback((alert: DataManagementAlert) => {
    // Add analytics context to alerts
    const enhancedAlert = {
      ...alert,
      context: {
        systemHealth: state.systemHealth?.overall,
        timestamp: new Date(),
        ...(alert.context || {}),
      },
    };

    onAlert?.(enhancedAlert);
  }, [onAlert, state.systemHealth]);

  // System health indicator with analytics data
  const systemHealthIndicator = useMemo(() => {
    if (!state.systemHealth) return null;

    const { overall, status } = state.systemHealth;
    const healthColor = status === 'healthy' ? 'green' : status === 'warning' ? 'yellow' : 'red';

    return (
      <div
        className={`flex items-center space-x-2 px-3 py-1 rounded-full text-sm font-medium bg-${healthColor}-100 text-${healthColor}-800`}
        data-testid="enhanced-system-health"
      >
        <div className={`w-2 h-2 rounded-full bg-${healthColor}-500`} />
        <span>System Health: {Math.round(overall)}%</span>
        <span className="text-xs">({status})</span>
      </div>
    );
  }, [state.systemHealth]);

  // Navigation component
  const Navigation = () => (
    <div className="flex bg-gray-100 rounded-lg p-1 mb-4" data-testid="navigation-tabs">
      <button
        onClick={() => handleViewChange('data-management')}
        className={`px-4 py-2 rounded text-sm font-medium transition-colors ${
          state.currentView === 'data-management'
            ? 'bg-white text-blue-600 shadow'
            : 'text-gray-600 hover:text-gray-900'
        }`}
        data-testid="data-management-tab"
      >
        Data Management
      </button>

      {showAnalytics && (
        <>
          <button
            onClick={() => handleViewChange('analytics')}
            className={`px-4 py-2 rounded text-sm font-medium transition-colors ${
              state.currentView === 'analytics'
                ? 'bg-white text-blue-600 shadow'
                : 'text-gray-600 hover:text-gray-900'
            }`}
            data-testid="analytics-tab"
          >
            Analytics
          </button>

          <button
            onClick={() => handleViewChange('reports')}
            className={`px-4 py-2 rounded text-sm font-medium transition-colors ${
              state.currentView === 'reports'
                ? 'bg-white text-blue-600 shadow'
                : 'text-gray-600 hover:text-gray-900'
            }`}
            data-testid="reports-tab"
          >
            Reports
          </button>

          <button
            onClick={() => handleViewChange('exports')}
            className={`px-4 py-2 rounded text-sm font-medium transition-colors ${
              state.currentView === 'exports'
                ? 'bg-white text-blue-600 shadow'
                : 'text-gray-600 hover:text-gray-900'
            }`}
            data-testid="exports-tab"
          >
            Exports
          </button>
        </>
      )}
    </div>
  );

  // Quick insights panel
  const QuickInsights = () => {
    if (!state.analyticsData) return null;

    const { performanceScore, recommendations, aggregatedKPIs } = state.analyticsData;
    const criticalKPIs = aggregatedKPIs.filter(kpi => kpi.status === 'critical');

    return (
      <div className="bg-white rounded-lg p-4 shadow border mb-4" data-testid="quick-insights">
        <h3 className="text-lg font-medium text-gray-900 mb-3">Quick Insights</h3>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
          <div className="text-center">
            <div className={`text-2xl font-bold ${
              performanceScore >= 80 ? 'text-green-600' :
              performanceScore >= 60 ? 'text-yellow-600' : 'text-red-600'
            }`}>
              {performanceScore}%
            </div>
            <div className="text-sm text-gray-600">Performance Score</div>
          </div>

          <div className="text-center">
            <div className={`text-2xl font-bold ${
              criticalKPIs.length === 0 ? 'text-green-600' : 'text-red-600'
            }`}>
              {criticalKPIs.length}
            </div>
            <div className="text-sm text-gray-600">Critical Issues</div>
          </div>

          <div className="text-center">
            <div className="text-2xl font-bold text-blue-600">
              {aggregatedKPIs.length}
            </div>
            <div className="text-sm text-gray-600">Active KPIs</div>
          </div>
        </div>

        {recommendations.length > 0 && (
          <div className="border-t pt-3">
            <h4 className="text-sm font-medium text-gray-900 mb-2">Top Recommendations</h4>
            <ul className="space-y-1">
              {recommendations.slice(0, 3).map((rec, index) => (
                <li key={index} className="text-sm text-gray-600 flex items-start">
                  <span className="text-blue-500 mr-2">•</span>
                  {rec}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    );
  };

  // Loading state
  if (state.loading) {
    return (
      <div className={`flex items-center justify-center h-64 ${className}`} style={style}>
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading integrated dashboard...</p>
        </div>
      </div>
    );
  }

  // Error state
  if (state.error) {
    return (
      <div className={`bg-red-50 border border-red-200 rounded-lg p-6 ${className}`} style={style}>
        <div className="flex items-center space-x-3">
          <div className="text-red-600 text-xl">⚠️</div>
          <div>
            <h3 className="text-red-800 font-medium">Dashboard Error</h3>
            <p className="text-red-600">{state.error}</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div
      className={`integrated-dashboard space-y-6 ${className}`}
      style={style}
      data-testid="data-management-with-analytics"
    >
      {/* Enhanced Header */}
      <div className="flex flex-col space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div className="flex items-center space-x-4">
            <h1 className="text-2xl font-bold">{title}</h1>
            {systemHealthIndicator}
          </div>

          <div className="flex items-center space-x-3">
            {showAnalytics && (
              <button
                onClick={toggleAnalyticsPanel}
                className={`px-3 py-1 rounded text-sm font-medium transition-colors ${
                  state.showAnalyticsPanel
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                }`}
                data-testid="toggle-analytics"
              >
                {state.showAnalyticsPanel ? 'Hide Analytics' : 'Show Analytics'}
              </button>
            )}
          </div>
        </div>

        {/* Navigation */}
        <Navigation />

        {/* Quick Insights */}
        {state.showAnalyticsPanel && <QuickInsights />}
      </div>

      {/* Main Content */}
      <div className={`${
        analyticsLayout === AnalyticsViewLayout.SIDE_BY_SIDE && state.showAnalyticsPanel
          ? 'grid grid-cols-1 xl:grid-cols-3 gap-6'
          : ''
      }`}>
        {/* Data Management Dashboard */}
        {(state.currentView === 'data-management' || analyticsLayout === AnalyticsViewLayout.SIDE_BY_SIDE) && (
          <div className={`${
            analyticsLayout === AnalyticsViewLayout.SIDE_BY_SIDE && state.showAnalyticsPanel
              ? 'xl:col-span-2'
              : ''
          }`}>
            <DataManagementDashboard
              title="Core Data Management"
              initialLayout={initialLayout}
              initialTheme={initialTheme}
              autoRefresh={autoRefresh}
              refreshInterval={refreshInterval}
              dataSourceService={dataSourceService}
              storageMetricsService={storageMetricsService}
              dataQualityService={dataQualityService}
              pipelineService={pipelineService}
              notificationService={notificationService}
              onAlert={handleEnhancedAlert}
            />
          </div>
        )}

        {/* Analytics Panel */}
        {state.showAnalyticsPanel && (
          <div className={`${
            analyticsLayout === AnalyticsViewLayout.SIDE_BY_SIDE
              ? 'xl:col-span-1'
              : ''
          }`}>
            {state.currentView === 'analytics' && (
              <div className="space-y-6">
                <PerformanceScorecard
                  layout={ScorecardLayout.COMPACT}
                  categories={[
                    AnalyticsCategory.SYSTEM,
                    AnalyticsCategory.PERFORMANCE,
                    AnalyticsCategory.DATA_QUALITY,
                  ]}
                  showScores={true}
                  showTrends={true}
                  compactMode={true}
                  onError={onError}
                />

                <AnalyticsDashboard
                  layout={AnalyticsDashboardLayout.COMPACT}
                  defaultTimeRange={state.analyticsTimeRange}
                  onTimeRangeChange={handleTimeRangeChange}
                  onError={onError}
                />
              </div>
            )}

            {state.currentView === 'reports' && (
              <ReportsManager
                onError={onError}
              />
            )}

            {state.currentView === 'exports' && (
              <ExportManager
                onError={onError}
              />
            )}

            {analyticsLayout === AnalyticsViewLayout.SIDE_BY_SIDE && (
              <div className="space-y-4">
                <div className="bg-white rounded-lg p-4 shadow border">
                  <h3 className="text-lg font-medium text-gray-900 mb-3">System Overview</h3>
                  <PerformanceScorecard
                    layout={ScorecardLayout.COMPACT}
                    categories={[AnalyticsCategory.SYSTEM]}
                    showScores={true}
                    compactMode={true}
                    onError={onError}
                  />
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
