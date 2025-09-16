/**
 * AnalyticsPanel Component
 *
 * Modular analytics panel that can be integrated into existing dashboards
 */

import React, { useState, useCallback, useMemo } from 'react';
import { useAnalyticsEnhancement } from '@/hooks/useAnalyticsEnhancement';
import { DataSourceService } from '@/services/dataSource';
import { StorageMetricsService } from '@/services/storageMetrics';
import { DataQualityService } from '@/services/dataQuality';
import { PipelineService } from '@/services/pipeline';
import {
  SystemHealth,
  KPI,
  KPIStatus,
  TrendDirection,
  AnalyticsCategory,
  TimeRange,
  TimeInterval,
} from '@/types/analytics';
import { DataManagementAlert } from '@/types/dataManagement';

export interface AnalyticsPanelProps {
  className?: string;
  style?: React.CSSProperties;
  layout?: AnalyticsPanelLayout;
  showQuickStats?: boolean;
  showSystemHealth?: boolean;
  showKPIs?: boolean;
  showInsights?: boolean;
  showAlerts?: boolean;
  compactMode?: boolean;
  autoInitialize?: boolean;

  // Service instances
  dataSourceService?: DataSourceService;
  storageMetricsService?: StorageMetricsService;
  dataQualityService?: DataQualityService;
  pipelineService?: PipelineService;

  // Event callbacks
  onKPIClick?: (kpi: KPI) => void;
  onAlertClick?: (alert: DataManagementAlert) => void;
  onHealthClick?: (health: SystemHealth) => void;
  onError?: (error: Error) => void;
}

export enum AnalyticsPanelLayout {
  VERTICAL = 'vertical',
  HORIZONTAL = 'horizontal',
  GRID = 'grid',
  COMPACT = 'compact',
}

interface PanelState {
  isExpanded: boolean;
  activeTab: AnalyticsTab;
  timeRange: TimeRange;
}

enum AnalyticsTab {
  OVERVIEW = 'overview',
  KPIS = 'kpis',
  HEALTH = 'health',
  INSIGHTS = 'insights',
  ALERTS = 'alerts',
}

export const AnalyticsPanel: React.FC<AnalyticsPanelProps> = ({
  className = '',
  style = {},
  layout = AnalyticsPanelLayout.VERTICAL,
  showQuickStats = true,
  showSystemHealth = true,
  showKPIs = true,
  showInsights = true,
  showAlerts = true,
  compactMode = false,
  autoInitialize = true,
  dataSourceService,
  storageMetricsService,
  dataQualityService,
  pipelineService,
  onKPIClick,
  onAlertClick,
  onHealthClick,
  onError,
}) => {
  const [panelState, setPanelState] = useState<PanelState>({
    isExpanded: !compactMode,
    activeTab: AnalyticsTab.OVERVIEW,
    timeRange: {
      start: new Date(Date.now() - 24 * 60 * 60 * 1000), // Last 24 hours
      end: new Date(),
      interval: TimeInterval.HOUR,
    },
  });

  // Analytics enhancement hook
  const {
    state: analyticsState,
    actions,
    isHealthy,
    hasWarnings,
    hasCriticalIssues,
    quickStats,
  } = useAnalyticsEnhancement({
    autoInitialize,
    enableRealTimeUpdates: true,
    defaultTimeRange: panelState.timeRange,
  });

  // Initialize services if provided
  React.useEffect(() => {
    if (autoInitialize && !analyticsState.isInitialized) {
      actions.initialize({
        dataSource: dataSourceService,
        storage: storageMetricsService,
        dataQuality: dataQualityService,
        pipeline: pipelineService,
      }).catch(error => {
        onError?.(error instanceof Error ? error : new Error('Analytics initialization failed'));
      });
    }
  }, [
    autoInitialize,
    analyticsState.isInitialized,
    actions,
    dataSourceService,
    storageMetricsService,
    dataQualityService,
    pipelineService,
    onError,
  ]);

  // Handle panel toggle
  const togglePanel = useCallback(() => {
    setPanelState(prev => ({ ...prev, isExpanded: !prev.isExpanded }));
  }, []);

  // Handle tab change
  const handleTabChange = useCallback((tab: AnalyticsTab) => {
    setPanelState(prev => ({ ...prev, activeTab: tab }));
  }, []);

  // Handle time range change
  const handleTimeRangeChange = useCallback(async (timeRange: TimeRange) => {
    setPanelState(prev => ({ ...prev, timeRange }));
    await actions.updateTimeRange(timeRange);
  }, [actions]);

  // Handle KPI click
  const handleKPIClick = useCallback((kpi: KPI) => {
    onKPIClick?.(kpi);
  }, [onKPIClick]);

  // Handle alert click
  const handleAlertClick = useCallback((alert: DataManagementAlert) => {
    onAlertClick?.(alert);
  }, [onAlertClick]);

  // Handle health click
  const handleHealthClick = useCallback(() => {
    if (analyticsState.systemHealth) {
      onHealthClick?.(analyticsState.systemHealth);
    }
  }, [analyticsState.systemHealth, onHealthClick]);

  // Get layout classes
  const getLayoutClasses = () => {
    const baseClasses = 'analytics-panel bg-white rounded-lg shadow border';

    switch (layout) {
      case AnalyticsPanelLayout.HORIZONTAL:
        return `${baseClasses} flex flex-row`;
      case AnalyticsPanelLayout.GRID:
        return `${baseClasses} grid gap-4`;
      case AnalyticsPanelLayout.COMPACT:
        return `${baseClasses} space-y-2`;
      default:
        return `${baseClasses} flex flex-col`;
    }
  };

  // Get status color
  const getStatusColor = (status: KPIStatus | string) => {
    switch (status) {
      case 'excellent':
        return 'text-green-600 bg-green-100';
      case 'good':
        return 'text-blue-600 bg-blue-100';
      case 'warning':
        return 'text-yellow-600 bg-yellow-100';
      case 'critical':
        return 'text-red-600 bg-red-100';
      default:
        return 'text-gray-600 bg-gray-100';
    }
  };

  // Get trend icon
  const getTrendIcon = (trend: TrendDirection) => {
    switch (trend) {
      case TrendDirection.INCREASING:
        return '📈';
      case TrendDirection.DECREASING:
        return '📉';
      case TrendDirection.STABLE:
        return '📊';
      case TrendDirection.VOLATILE:
        return '📊';
      default:
        return '❓';
    }
  };

  // Loading state
  if (analyticsState.isLoading && !analyticsState.analytics) {
    return (
      <div className={`${getLayoutClasses()} p-4 ${className}`} style={style}>
        <div className="flex items-center justify-center h-32">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          <span className="ml-2 text-gray-600">Loading analytics...</span>
        </div>
      </div>
    );
  }

  // Error state
  if (analyticsState.error) {
    return (
      <div className={`${getLayoutClasses()} p-4 ${className}`} style={style}>
        <div className="bg-red-50 border border-red-200 rounded p-4">
          <div className="flex items-center">
            <div className="text-red-600 text-xl mr-2">⚠️</div>
            <div>
              <h4 className="text-red-800 font-medium">Analytics Error</h4>
              <p className="text-red-600 text-sm">{analyticsState.error}</p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div
      className={`${getLayoutClasses()} ${className}`}
      style={style}
      data-testid="analytics-panel"
    >
      {/* Panel Header */}
      <div className="flex items-center justify-between p-4 border-b">
        <div className="flex items-center space-x-3">
          <h3 className="text-lg font-medium text-gray-900">Analytics</h3>

          {/* Health Indicator */}
          {showSystemHealth && analyticsState.systemHealth && (
            <button
              onClick={handleHealthClick}
              className={`flex items-center space-x-2 px-2 py-1 rounded-full text-xs font-medium cursor-pointer ${
                isHealthy ? 'bg-green-100 text-green-800' :
                hasWarnings ? 'bg-yellow-100 text-yellow-800' :
                hasCriticalIssues ? 'bg-red-100 text-red-800' :
                'bg-gray-100 text-gray-800'
              }`}
              data-testid="health-indicator"
            >
              <div className={`w-2 h-2 rounded-full ${
                isHealthy ? 'bg-green-500' :
                hasWarnings ? 'bg-yellow-500' :
                hasCriticalIssues ? 'bg-red-500' :
                'bg-gray-500'
              }`} />
              <span>{Math.round(quickStats.systemHealthScore)}%</span>
            </button>
          )}

          {/* Alert Count */}
          {showAlerts && analyticsState.alerts.length > 0 && (
            <span className="bg-red-100 text-red-800 text-xs font-medium px-2 py-1 rounded-full">
              {analyticsState.alerts.length} alerts
            </span>
          )}
        </div>

        <div className="flex items-center space-x-2">
          {/* Refresh Button */}
          <button
            onClick={() => actions.refresh()}
            disabled={analyticsState.isLoading}
            className="p-1 text-gray-600 hover:text-gray-800 disabled:opacity-50"
            data-testid="refresh-button"
          >
            <svg
              className={`w-4 h-4 ${analyticsState.isLoading ? 'animate-spin' : ''}`}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
          </button>

          {/* Toggle Button */}
          <button
            onClick={togglePanel}
            className="p-1 text-gray-600 hover:text-gray-800"
            data-testid="toggle-panel"
          >
            <svg
              className={`w-4 h-4 transform transition-transform ${panelState.isExpanded ? 'rotate-180' : ''}`}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>
        </div>
      </div>

      {/* Panel Content */}
      {panelState.isExpanded && (
        <div className="p-4 space-y-4">
          {/* Quick Stats */}
          {showQuickStats && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4" data-testid="quick-stats">
              <div className="text-center">
                <div className="text-2xl font-bold text-blue-600">{quickStats.totalKPIs}</div>
                <div className="text-xs text-gray-600">Total KPIs</div>
              </div>
              <div className="text-center">
                <div className={`text-2xl font-bold ${quickStats.performanceScore >= 80 ? 'text-green-600' : 'text-yellow-600'}`}>
                  {quickStats.performanceScore}%
                </div>
                <div className="text-xs text-gray-600">Performance</div>
              </div>
              <div className="text-center">
                <div className={`text-2xl font-bold ${quickStats.criticalKPIs > 0 ? 'text-red-600' : 'text-green-600'}`}>
                  {quickStats.criticalKPIs}
                </div>
                <div className="text-xs text-gray-600">Critical</div>
              </div>
              <div className="text-center">
                <div className={`text-2xl font-bold ${quickStats.warningKPIs > 0 ? 'text-yellow-600' : 'text-green-600'}`}>
                  {quickStats.warningKPIs}
                </div>
                <div className="text-xs text-gray-600">Warnings</div>
              </div>
            </div>
          )}

          {/* Tab Navigation */}
          {!compactMode && (
            <div className="flex space-x-1 bg-gray-100 rounded-lg p-1" data-testid="tab-navigation">
              {Object.values(AnalyticsTab).map(tab => (
                <button
                  key={tab}
                  onClick={() => handleTabChange(tab)}
                  className={`px-3 py-1 rounded text-sm font-medium transition-colors ${
                    panelState.activeTab === tab
                      ? 'bg-white text-blue-600 shadow'
                      : 'text-gray-600 hover:text-gray-900'
                  }`}
                  data-testid={`tab-${tab}`}
                >
                  {tab.charAt(0).toUpperCase() + tab.slice(1)}
                </button>
              ))}
            </div>
          )}

          {/* Tab Content */}
          <div className="space-y-4">
            {/* Overview Tab */}
            {(panelState.activeTab === AnalyticsTab.OVERVIEW || compactMode) && (
              <div data-testid="overview-content">
                {/* System Health */}
                {showSystemHealth && analyticsState.systemHealth && (
                  <div className="bg-gray-50 rounded-lg p-3">
                    <h4 className="text-sm font-medium text-gray-900 mb-2">System Health</h4>
                    <div className="flex items-center justify-between">
                      <span className="text-lg font-bold">{Math.round(analyticsState.systemHealth.overall)}%</span>
                      <span className={`px-2 py-1 rounded text-xs font-medium ${
                        getStatusColor(analyticsState.systemHealth.status)
                      }`}>
                        {analyticsState.systemHealth.status}
                      </span>
                    </div>
                  </div>
                )}

                {/* Top KPIs */}
                {showKPIs && analyticsState.kpis.length > 0 && (
                  <div className="space-y-2">
                    <h4 className="text-sm font-medium text-gray-900">Key Metrics</h4>
                    {analyticsState.kpis.slice(0, compactMode ? 3 : 5).map(kpi => (
                      <div
                        key={kpi.id}
                        className="flex items-center justify-between p-2 bg-gray-50 rounded cursor-pointer hover:bg-gray-100"
                        onClick={() => handleKPIClick(kpi)}
                        data-testid={`kpi-${kpi.id}`}
                      >
                        <div className="flex items-center space-x-2">
                          <span className="text-sm font-medium">{kpi.name}</span>
                          <span className="text-lg">{getTrendIcon(kpi.trend)}</span>
                        </div>
                        <div className="flex items-center space-x-2">
                          <span className="text-sm font-bold">
                            {typeof kpi.currentValue === 'number' ? kpi.currentValue.toFixed(1) : kpi.currentValue}
                            {kpi.unit}
                          </span>
                          <span className={`px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(kpi.status)}`}>
                            {kpi.status}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* KPIs Tab */}
            {panelState.activeTab === AnalyticsTab.KPIS && !compactMode && showKPIs && (
              <div data-testid="kpis-content">
                <div className="space-y-3">
                  {analyticsState.kpis.map(kpi => (
                    <div
                      key={kpi.id}
                      className="p-3 border rounded-lg cursor-pointer hover:bg-gray-50"
                      onClick={() => handleKPIClick(kpi)}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <h5 className="font-medium">{kpi.name}</h5>
                        <span className={`px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(kpi.status)}`}>
                          {kpi.status}
                        </span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-lg font-bold">
                          {typeof kpi.currentValue === 'number' ? kpi.currentValue.toFixed(1) : kpi.currentValue}
                          {kpi.unit}
                        </span>
                        <div className="flex items-center space-x-2">
                          <span className="text-sm text-gray-600">Target: {kpi.target}{kpi.unit}</span>
                          <span className="text-lg">{getTrendIcon(kpi.trend)}</span>
                        </div>
                      </div>
                      {kpi.description && (
                        <p className="text-xs text-gray-600 mt-1">{kpi.description}</p>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Alerts Tab */}
            {panelState.activeTab === AnalyticsTab.ALERTS && !compactMode && showAlerts && (
              <div data-testid="alerts-content">
                {analyticsState.alerts.length > 0 ? (
                  <div className="space-y-2">
                    {analyticsState.alerts.map(alert => (
                      <div
                        key={alert.id}
                        className={`p-3 rounded-lg border-l-4 cursor-pointer ${
                          alert.severity === 'critical' ? 'bg-red-50 border-red-400' :
                          alert.severity === 'warning' ? 'bg-yellow-50 border-yellow-400' :
                          'bg-blue-50 border-blue-400'
                        }`}
                        onClick={() => handleAlertClick(alert)}
                      >
                        <div className="flex items-start justify-between">
                          <div>
                            <h5 className="font-medium text-sm">{alert.title}</h5>
                            <p className="text-xs text-gray-600 mt-1">{alert.message}</p>
                            <p className="text-xs text-gray-500 mt-1">
                              {alert.timestamp.toLocaleTimeString()}
                            </p>
                          </div>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              actions.dismissAlert(alert.id);
                            }}
                            className="text-gray-400 hover:text-gray-600"
                          >
                            ✕
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-8 text-gray-500">
                    <div className="text-4xl mb-2">✅</div>
                    <p>No alerts</p>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
