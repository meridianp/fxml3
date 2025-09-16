/**
 * DataManagementDashboard Component
 *
 * Main container dashboard for data management with grid layout and unified alerts
 */

import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { DataSourceMonitor } from './DataSourceMonitor';
import { StorageManager } from './StorageManager';
import { DataQualityDashboard } from './DataQualityDashboard';
import { PipelineMonitor } from './PipelineMonitor';
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

export interface DataManagementDashboardProps {
  className?: string;
  style?: React.CSSProperties;
  title?: string;

  // Layout and theming
  initialLayout?: DashboardLayout;
  initialTheme?: DashboardTheme;

  // Refresh configuration
  autoRefresh?: boolean;
  refreshInterval?: number;

  // Service instances
  dataSourceService?: DataSourceService;
  storageMetricsService?: StorageMetricsService;
  dataQualityService?: DataQualityService;
  pipelineService?: PipelineService;
  notificationService?: NotificationService;

  // Event callbacks
  onAlert?: (alert: DataManagementAlert) => void;
  onStatusUpdate?: (status: DashboardStatus) => void;
  onRefresh?: () => void;

  children?: React.ReactNode;
}

export enum DashboardLayout {
  DEFAULT = 'default',
  COMPACT = 'compact',
  DETAILED = 'detailed',
  MOBILE = 'mobile',
}

export enum DashboardTheme {
  LIGHT = 'light',
  DARK = 'dark',
  AUTO = 'auto',
}

interface DashboardStatus {
  dataSource?: DataSourceStatusEvent;
  storage?: StorageStatusEvent;
  quality?: QualityStatusEvent;
  pipeline?: PipelineStatusEvent;
  overall: {
    health: 'healthy' | 'warning' | 'critical';
    score: number;
    timestamp: Date;
  };
}

interface DashboardState {
  alerts: DataManagementAlert[];
  status: DashboardStatus;
  layout: DashboardLayout;
  theme: DashboardTheme;
  isRefreshing: boolean;
  showAlertsPanel: boolean;
  isMobile: boolean;
}

class ErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { hasError: boolean; error?: Error }
> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('Dashboard component error:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div
          data-testid="error-boundary"
          className="p-8 bg-red-50 border-2 border-red-200 rounded-lg text-center"
        >
          <h2 className="text-xl font-semibold text-red-800 mb-2">Something went wrong</h2>
          <p className="text-red-600 mb-4">
            The dashboard encountered an error and cannot be displayed properly.
          </p>
          <button
            onClick={() => this.setState({ hasError: false })}
            className="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700"
          >
            Try Again
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}

export const DataManagementDashboard: React.FC<DataManagementDashboardProps> = ({
  className = '',
  style = {},
  title = 'Data Management Dashboard',
  initialLayout = DashboardLayout.DEFAULT,
  initialTheme = DashboardTheme.LIGHT,
  autoRefresh = true,
  refreshInterval = 30000,
  dataSourceService,
  storageMetricsService,
  dataQualityService,
  pipelineService,
  notificationService,
  onAlert,
  onStatusUpdate,
  onRefresh,
  children,
}) => {
  // State management
  const [state, setState] = useState<DashboardState>({
    alerts: [],
    status: {
      overall: {
        health: 'healthy',
        score: 100,
        timestamp: new Date(),
      },
    },
    layout: initialLayout,
    theme: initialTheme,
    isRefreshing: false,
    showAlertsPanel: false,
    isMobile: false,
  });

  const fileInputRef = useRef<HTMLInputElement>(null);

  // Service instances
  const notificationServiceRef = useMemo(
    () => notificationService || new NotificationService(),
    [notificationService]
  );

  // Load preferences from localStorage
  useEffect(() => {
    try {
      const savedLayout = localStorage.getItem('data-dashboard-layout') as DashboardLayout;
      const savedTheme = localStorage.getItem('data-dashboard-theme') as DashboardTheme;

      setState(prev => ({
        ...prev,
        layout: savedLayout || prev.layout,
        theme: savedTheme || prev.theme,
      }));
    } catch (error) {
      console.warn('Failed to load dashboard preferences:', error);
    }
  }, []);

  // Responsive design detection
  useEffect(() => {
    const checkScreenSize = () => {
      const isMobile = window.innerWidth < 768;
      setState(prev => ({
        ...prev,
        isMobile,
        layout: isMobile ? DashboardLayout.MOBILE : prev.layout,
      }));
    };

    checkScreenSize();
    window.addEventListener('resize', checkScreenSize);
    return () => window.removeEventListener('resize', checkScreenSize);
  }, []);

  // Auto-refresh functionality
  useEffect(() => {
    if (autoRefresh && refreshInterval > 0) {
      const interval = setInterval(() => {
        handleRefresh();
      }, refreshInterval);
      return () => clearInterval(interval);
    }
  }, [autoRefresh, refreshInterval]);

  // Layout change handler
  const handleLayoutChange = useCallback((newLayout: DashboardLayout) => {
    setState(prev => ({ ...prev, layout: newLayout }));
    localStorage.setItem('data-dashboard-layout', newLayout);
  }, []);

  // Theme change handler
  const handleThemeChange = useCallback((newTheme: DashboardTheme) => {
    setState(prev => ({ ...prev, theme: newTheme }));
    localStorage.setItem('data-dashboard-theme', newTheme);
  }, []);

  // Alert handling
  const handleAlert = useCallback((alert: DataManagementAlert) => {
    setState(prev => ({
      ...prev,
      alerts: [...prev.alerts, alert],
    }));

    // Forward to external handler
    if (onAlert) {
      onAlert(alert);
    }

    // Create notification
    notificationServiceRef.create({
      type: alert.severity === 'critical' ? 'error' : 'warning',
      title: alert.title,
      message: alert.message,
    });
  }, [onAlert, notificationServiceRef]);

  // Status update handling
  const handleStatusChange = useCallback((
    type: 'data_source' | 'storage' | 'quality' | 'pipeline',
    event: DataSourceStatusEvent | StorageStatusEvent | QualityStatusEvent | PipelineStatusEvent
  ) => {
    setState(prev => {
      const newStatus = {
        ...prev.status,
        [type]: event,
      };

      // Calculate overall health
      const healthScores: number[] = [];

      if (newStatus.dataSource) {
        const dsStatus = newStatus.dataSource as DataSourceStatusEvent;
        const connectionRatio = dsStatus.activeConnections / (dsStatus.activeConnections + dsStatus.failedConnections);
        healthScores.push(connectionRatio * 100);
      }

      if (newStatus.storage) {
        const storageStatus = newStatus.storage as StorageStatusEvent;
        const usageRatio = storageStatus.usedStorage / storageStatus.totalStorage;
        healthScores.push((1 - usageRatio) * 100); // Invert so lower usage = higher score
      }

      if (newStatus.quality) {
        const qualityStatus = newStatus.quality as QualityStatusEvent;
        healthScores.push(qualityStatus.qualityScore);
      }

      if (newStatus.pipeline) {
        const pipelineStatus = newStatus.pipeline as PipelineStatusEvent;
        const successRatio = (pipelineStatus.totalJobs - pipelineStatus.failedJobs) / pipelineStatus.totalJobs;
        healthScores.push(successRatio * 100);
      }

      const overallScore = healthScores.length > 0
        ? healthScores.reduce((sum, score) => sum + score, 0) / healthScores.length
        : 100;

      const overallHealth = overallScore >= 80 ? 'healthy' : overallScore >= 60 ? 'warning' : 'critical';

      newStatus.overall = {
        health: overallHealth,
        score: overallScore,
        timestamp: new Date(),
      };

      return {
        ...prev,
        status: newStatus,
      };
    });

    // Forward to external handler
    if (onStatusUpdate) {
      onStatusUpdate(state.status);
    }
  }, [onStatusUpdate, state.status]);

  // Refresh handler
  const handleRefresh = useCallback(async () => {
    setState(prev => ({ ...prev, isRefreshing: true }));

    try {
      if (onRefresh) {
        await onRefresh();
      }
    } catch (error) {
      console.error('Refresh failed:', error);
    } finally {
      setState(prev => ({ ...prev, isRefreshing: false }));
    }
  }, [onRefresh]);

  // Alert management
  const dismissAlert = useCallback((alertId: string) => {
    setState(prev => ({
      ...prev,
      alerts: prev.alerts.filter(alert => alert.id !== alertId),
    }));
  }, []);

  const clearAllAlerts = useCallback(() => {
    setState(prev => ({ ...prev, alerts: [] }));
  }, []);

  // Configuration export/import
  const exportConfiguration = useCallback(() => {
    const config = {
      layout: state.layout,
      theme: state.theme,
      timestamp: new Date().toISOString(),
    };

    const blob = new Blob([JSON.stringify(config, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'dashboard-config.json';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    notificationServiceRef.create({
      type: 'success',
      title: 'Configuration Exported',
      message: 'Dashboard configuration has been exported successfully',
    });
  }, [state.layout, state.theme, notificationServiceRef]);

  const importConfiguration = useCallback((event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const config = JSON.parse(e.target?.result as string);

        if (config.layout) {
          handleLayoutChange(config.layout);
        }
        if (config.theme) {
          handleThemeChange(config.theme);
        }

        notificationServiceRef.create({
          type: 'success',
          title: 'Configuration Imported',
          message: 'Dashboard configuration has been imported successfully',
        });
      } catch (error) {
        notificationServiceRef.create({
          type: 'error',
          title: 'Import Failed',
          message: 'Failed to import dashboard configuration',
        });
      }
    };
    reader.readAsText(file);
  }, [handleLayoutChange, handleThemeChange, notificationServiceRef]);

  // Grid layout classes
  const getLayoutClasses = () => {
    const baseClasses = 'grid gap-6 h-full';

    switch (state.layout) {
      case DashboardLayout.COMPACT:
        return `${baseClasses} grid-cols-1 lg:grid-cols-2 xl:grid-cols-4 auto-rows-min layout-compact`;
      case DashboardLayout.DETAILED:
        return `${baseClasses} grid-cols-1 xl:grid-cols-3 auto-rows-fr layout-detailed`;
      case DashboardLayout.MOBILE:
        return `${baseClasses} grid-cols-1 auto-rows-min mobile-layout`;
      default:
        return `${baseClasses} grid-cols-1 lg:grid-cols-2 xl:grid-cols-4
                grid-rows-[auto_1fr_1fr] xl:grid-rows-[auto_1fr]
                [grid-template-areas:'header_header_header_header'_'data-sources_data-sources_storage_storage'_'quality_quality_pipelines_pipelines']
                xl:[grid-template-areas:'header_header_header_header'_'data-sources_storage_quality_pipelines']`;
    }
  };

  const getThemeClasses = () => {
    switch (state.theme) {
      case DashboardTheme.DARK:
        return 'theme-dark bg-gray-900 text-white';
      case DashboardTheme.AUTO:
        return window.matchMedia('(prefers-color-scheme: dark)').matches ?
               'theme-dark bg-gray-900 text-white' : 'theme-light bg-gray-50 text-gray-900';
      default:
        return 'theme-light bg-gray-50 text-gray-900';
    }
  };

  return (
    <ErrorBoundary>
      <div
        data-testid="data-management-dashboard"
        className={`min-h-screen p-6 ${getThemeClasses()} ${className}`}
        style={style}
        role="main"
        aria-label="Data Management Dashboard"
      >
        {/* Dashboard Header */}
        <div className="mb-6" style={{ gridArea: 'header' }}>
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div className="flex items-center space-x-4">
              <h1 className="text-2xl font-bold">{title}</h1>

              {/* System Health Indicator */}
              <div
                data-testid="system-health-indicator"
                className={`flex items-center space-x-2 px-3 py-1 rounded-full text-sm font-medium ${
                  state.status.overall.health === 'healthy' ? 'bg-green-100 text-green-800' :
                  state.status.overall.health === 'warning' ? 'bg-yellow-100 text-yellow-800' :
                  'bg-red-100 text-red-800'
                }`}
              >
                <div
                  className={`w-2 h-2 rounded-full ${
                    state.status.overall.health === 'healthy' ? 'bg-green-500' :
                    state.status.overall.health === 'warning' ? 'bg-yellow-500' :
                    'bg-red-500'
                  }`}
                />
                <span data-testid="overall-status">
                  {state.status.overall.health === 'healthy' ? 'Healthy' :
                   state.status.overall.health === 'warning' ? 'Warning' : 'Critical'}
                </span>
                <span className="text-xs">({Math.round(state.status.overall.score)}%)</span>
              </div>
            </div>

            {/* Dashboard Controls */}
            <div className="flex items-center space-x-3">
              {/* Alert Indicator */}
              {state.alerts.length > 0 && (
                <button
                  data-testid="alert-indicator"
                  className="relative p-2 text-red-600 hover:text-red-800 has-alerts"
                  onClick={() => setState(prev => ({ ...prev, showAlertsPanel: !prev.showAlertsPanel }))}
                  aria-label={`${state.alerts.length} alerts`}
                >
                  <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                  </svg>
                  <span
                    data-testid="alert-count"
                    className="absolute -top-1 -right-1 bg-red-500 text-white text-xs rounded-full h-5 w-5 flex items-center justify-center"
                  >
                    {state.alerts.length}
                  </span>
                </button>
              )}

              {/* Layout Selector */}
              <select
                data-testid="layout-selector"
                value={state.layout}
                onChange={(e) => handleLayoutChange(e.target.value as DashboardLayout)}
                className="px-3 py-1 border border-gray-300 rounded-md text-sm bg-white dark:bg-gray-800 dark:border-gray-600"
                aria-label="Dashboard layout"
              >
                <option value={DashboardLayout.DEFAULT}>Default</option>
                <option value={DashboardLayout.COMPACT}>Compact</option>
                <option value={DashboardLayout.DETAILED}>Detailed</option>
              </select>

              {/* Theme Selector */}
              <select
                data-testid="theme-selector"
                value={state.theme}
                onChange={(e) => handleThemeChange(e.target.value as DashboardTheme)}
                className="px-3 py-1 border border-gray-300 rounded-md text-sm bg-white dark:bg-gray-800 dark:border-gray-600"
                aria-label="Dashboard theme"
              >
                <option value={DashboardTheme.LIGHT}>Light</option>
                <option value={DashboardTheme.DARK}>Dark</option>
                <option value={DashboardTheme.AUTO}>Auto</option>
              </select>

              {/* Export/Import */}
              <button
                data-testid="export-config"
                onClick={exportConfiguration}
                className="p-2 text-gray-600 hover:text-gray-800 dark:text-gray-400 dark:hover:text-gray-200"
                aria-label="Export configuration"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
              </button>

              <button
                data-testid="import-config"
                onClick={() => fileInputRef.current?.click()}
                className="p-2 text-gray-600 hover:text-gray-800 dark:text-gray-400 dark:hover:text-gray-200"
                aria-label="Import configuration"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M9 19l3 3m0 0l3-3m-3 3V10" />
                </svg>
              </button>

              <input
                ref={fileInputRef}
                data-testid="config-file-input"
                type="file"
                accept=".json"
                onChange={importConfiguration}
                className="hidden"
              />

              {/* Refresh Button */}
              <button
                data-testid="refresh-button"
                onClick={handleRefresh}
                disabled={state.isRefreshing}
                className={`p-2 rounded-md transition-colors ${
                  state.isRefreshing
                    ? 'text-gray-400 cursor-not-allowed'
                    : 'text-gray-600 hover:text-gray-800 hover:bg-gray-100 dark:text-gray-400 dark:hover:text-gray-200 dark:hover:bg-gray-800'
                }`}
                aria-label="Refresh dashboard"
              >
                <svg
                  data-testid="refresh-indicator"
                  className={`w-5 h-5 ${state.isRefreshing ? 'animate-spin refreshing' : ''}`}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
              </button>
            </div>
          </div>
        </div>

        {/* Alert Panel */}
        {state.showAlertsPanel && state.alerts.length > 0 && (
          <div
            data-testid="alerts-panel"
            className="mb-6 p-4 bg-white dark:bg-gray-800 rounded-lg shadow-md border border-gray-200 dark:border-gray-700"
            role="alert"
            aria-live="polite"
          >
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-lg font-semibold">Active Alerts</h3>
              <button
                data-testid="clear-all-alerts"
                onClick={clearAllAlerts}
                className="px-3 py-1 bg-red-600 text-white rounded text-sm hover:bg-red-700"
              >
                Clear All
              </button>
            </div>

            <div className="space-y-2 max-h-64 overflow-y-auto">
              {state.alerts.map((alert) => (
                <div
                  key={alert.id}
                  className={`p-3 rounded-md border-l-4 ${
                    alert.severity === 'critical' ? 'bg-red-50 border-red-400 dark:bg-red-900/20' :
                    alert.severity === 'warning' ? 'bg-yellow-50 border-yellow-400 dark:bg-yellow-900/20' :
                    'bg-blue-50 border-blue-400 dark:bg-blue-900/20'
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <div>
                      <h4 className={`font-medium ${
                        alert.severity === 'critical' ? 'text-red-800 dark:text-red-200' :
                        alert.severity === 'warning' ? 'text-yellow-800 dark:text-yellow-200' :
                        'text-blue-800 dark:text-blue-200'
                      }`}>
                        {alert.title}
                      </h4>
                      <p className={`text-sm mt-1 ${
                        alert.severity === 'critical' ? 'text-red-600 dark:text-red-300' :
                        alert.severity === 'warning' ? 'text-yellow-600 dark:text-yellow-300' :
                        'text-blue-600 dark:text-blue-300'
                      }`}>
                        {alert.message}
                      </p>
                      <p className="text-xs text-gray-500 mt-1">
                        {alert.timestamp.toLocaleString()} • {alert.source}
                      </p>
                    </div>
                    <button
                      data-testid={`dismiss-alert-${alert.id}`}
                      onClick={() => dismissAlert(alert.id)}
                      className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200"
                    >
                      ✕
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Screen reader announcements */}
        {state.alerts.length > 0 && (
          <div className="sr-only" role="alert" aria-live="assertive">
            New alert: {state.alerts[state.alerts.length - 1]?.title}
          </div>
        )}

        {/* Dashboard Grid */}
        <div className={getLayoutClasses()}>
          {/* Data Source Monitor */}
          <DataSourceMonitor
            gridArea="data-sources"
            dataSourceService={dataSourceService}
            notificationService={notificationService}
            onAlert={handleAlert}
            onStatusChange={(event) => handleStatusChange('data_source', event)}
            autoRefresh={autoRefresh}
            refreshInterval={refreshInterval}
          />

          {/* Storage Manager */}
          <StorageManager
            gridArea="storage"
            storageMetricsService={storageMetricsService}
            notificationService={notificationService}
            onAlert={handleAlert}
            onStatusChange={(event) => handleStatusChange('storage', event)}
            autoRefresh={autoRefresh}
            refreshInterval={refreshInterval}
          />

          {/* Data Quality Dashboard */}
          <DataQualityDashboard
            gridArea="quality"
            dataQualityService={dataQualityService}
            notificationService={notificationService}
            onAlert={handleAlert}
            onQualityUpdate={(report) => handleStatusChange('quality', {
              type: 'data_quality',
              qualityScore: report.overall.score,
              level: report.overall.level,
              timestamp: report.timestamp,
            })}
            autoRefresh={autoRefresh}
            refreshInterval={refreshInterval}
          />

          {/* Pipeline Monitor */}
          <PipelineMonitor
            gridArea="pipelines"
            pipelineService={pipelineService}
            notificationService={notificationService}
            onAlert={handleAlert}
            onStatusChange={(event) => handleStatusChange('pipeline', event)}
            autoRefresh={autoRefresh}
            refreshInterval={refreshInterval}
          />

          {/* Custom children */}
          {children}
        </div>
      </div>
    </ErrorBoundary>
  );
};
