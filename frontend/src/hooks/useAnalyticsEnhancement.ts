/**
 * Analytics Enhancement Hook
 *
 * React hook to add analytics capabilities to existing data management components
 */

import { useState, useEffect, useCallback, useMemo } from 'react';
import {
  AnalyticsIntegrationService,
  getAnalyticsIntegrationService,
  DataManagementAnalytics
} from '@/services/analyticsIntegration';
import { DataSourceService } from '@/services/dataSource';
import { StorageMetricsService } from '@/services/storageMetrics';
import { DataQualityService } from '@/services/dataQuality';
import { PipelineService } from '@/services/pipeline';
import {
  SystemHealth,
  KPI,
  TimeRange,
  TimeInterval,
  AnalyticsCategory,
  CrossServiceInsights,
} from '@/types/analytics';
import {
  DataManagementAlert,
  DataSourceStatusEvent,
  StorageStatusEvent,
  QualityStatusEvent,
  PipelineStatusEvent,
} from '@/types/dataManagement';

export interface AnalyticsEnhancementConfig {
  autoInitialize?: boolean;
  updateInterval?: number;
  enableRealTimeUpdates?: boolean;
  defaultTimeRange?: TimeRange;
  alertThresholds?: {
    systemHealth: number;
    dataQuality: number;
    storageUsage: number;
    pipelineFailure: number;
  };
}

export interface AnalyticsEnhancementState {
  isInitialized: boolean;
  isLoading: boolean;
  error: string | null;
  analytics: DataManagementAnalytics | null;
  systemHealth: SystemHealth | null;
  insights: CrossServiceInsights[];
  kpis: KPI[];
  alerts: DataManagementAlert[];
}

export interface AnalyticsEnhancementActions {
  initialize: (services: {
    dataSource?: DataSourceService;
    storage?: StorageMetricsService;
    dataQuality?: DataQualityService;
    pipeline?: PipelineService;
  }) => Promise<void>;
  refresh: () => Promise<void>;
  updateTimeRange: (timeRange: TimeRange) => Promise<void>;
  generateReport: (type: string) => Promise<string>;
  exportData: (format: string) => Promise<string>;
  dismissAlert: (alertId: string) => void;
  getKPIsByCategory: (category: AnalyticsCategory) => KPI[];
  getSystemHealthScore: () => number;
  getPerformanceScore: () => number;
  getRecommendations: () => string[];
}

export interface UseAnalyticsEnhancementReturn {
  state: AnalyticsEnhancementState;
  actions: AnalyticsEnhancementActions;
  isHealthy: boolean;
  hasWarnings: boolean;
  hasCriticalIssues: boolean;
  quickStats: {
    totalKPIs: number;
    healthyKPIs: number;
    warningKPIs: number;
    criticalKPIs: number;
    systemHealthScore: number;
    performanceScore: number;
  };
}

/**
 * Analytics Enhancement Hook
 *
 * Adds analytics capabilities to existing data management components
 */
export const useAnalyticsEnhancement = (
  config: AnalyticsEnhancementConfig = {}
): UseAnalyticsEnhancementReturn => {
  const {
    autoInitialize = true,
    updateInterval = 30000,
    enableRealTimeUpdates = true,
    defaultTimeRange,
    alertThresholds = {
      systemHealth: 80,
      dataQuality: 90,
      storageUsage: 85,
      pipelineFailure: 10,
    },
  } = config;

  // State management
  const [state, setState] = useState<AnalyticsEnhancementState>({
    isInitialized: false,
    isLoading: false,
    error: null,
    analytics: null,
    systemHealth: null,
    insights: [],
    kpis: [],
    alerts: [],
  });

  // Integration service
  const [integrationService] = useState(() => getAnalyticsIntegrationService());

  // Current time range
  const [timeRange, setTimeRange] = useState<TimeRange>(() =>
    defaultTimeRange || {
      start: new Date(Date.now() - 24 * 60 * 60 * 1000), // Last 24 hours
      end: new Date(),
      interval: TimeInterval.HOUR,
    }
  );

  // Initialize analytics integration
  const initialize = useCallback(async (services: {
    dataSource?: DataSourceService;
    storage?: StorageMetricsService;
    dataQuality?: DataQualityService;
    pipeline?: PipelineService;
  }) => {
    setState(prev => ({ ...prev, isLoading: true, error: null }));

    try {
      await integrationService.initialize(services);

      // Subscribe to real-time updates
      if (enableRealTimeUpdates) {
        integrationService.onAnalyticsUpdate((analytics) => {
          setState(prev => ({
            ...prev,
            analytics,
            systemHealth: analytics.systemHealth,
            insights: analytics.correlationInsights,
            kpis: analytics.aggregatedKPIs,
          }));

          // Generate alerts based on analytics
          const newAlerts = generateAlertsFromAnalytics(analytics, alertThresholds);
          setState(prev => ({
            ...prev,
            alerts: [...prev.alerts, ...newAlerts],
          }));
        });
      }

      // Initial analytics generation
      const initialAnalytics = await integrationService.generateDataManagementAnalytics(timeRange);

      setState(prev => ({
        ...prev,
        isInitialized: true,
        isLoading: false,
        analytics: initialAnalytics,
        systemHealth: initialAnalytics.systemHealth,
        insights: initialAnalytics.correlationInsights,
        kpis: initialAnalytics.aggregatedKPIs,
      }));

    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to initialize analytics';
      setState(prev => ({
        ...prev,
        isLoading: false,
        error: errorMessage,
      }));
    }
  }, [integrationService, enableRealTimeUpdates, timeRange, alertThresholds]);

  // Refresh analytics data
  const refresh = useCallback(async () => {
    if (!state.isInitialized) return;

    setState(prev => ({ ...prev, isLoading: true }));

    try {
      const analytics = await integrationService.generateDataManagementAnalytics(timeRange);

      setState(prev => ({
        ...prev,
        isLoading: false,
        error: null,
        analytics,
        systemHealth: analytics.systemHealth,
        insights: analytics.correlationInsights,
        kpis: analytics.aggregatedKPIs,
      }));
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to refresh analytics';
      setState(prev => ({
        ...prev,
        isLoading: false,
        error: errorMessage,
      }));
    }
  }, [integrationService, timeRange, state.isInitialized]);

  // Update time range
  const updateTimeRange = useCallback(async (newTimeRange: TimeRange) => {
    setTimeRange(newTimeRange);
    if (state.isInitialized) {
      await refresh();
    }
  }, [refresh, state.isInitialized]);

  // Generate report
  const generateReport = useCallback(async (type: string): Promise<string> => {
    // This would integrate with the reports service
    return `report-${type}-${Date.now()}`;
  }, []);

  // Export data
  const exportData = useCallback(async (format: string): Promise<string> => {
    // This would integrate with the export service
    return `export-${format}-${Date.now()}`;
  }, []);

  // Dismiss alert
  const dismissAlert = useCallback((alertId: string) => {
    setState(prev => ({
      ...prev,
      alerts: prev.alerts.filter(alert => alert.id !== alertId),
    }));
  }, []);

  // Get KPIs by category
  const getKPIsByCategory = useCallback((category: AnalyticsCategory): KPI[] => {
    return state.kpis.filter(kpi => kpi.category === category);
  }, [state.kpis]);

  // Get system health score
  const getSystemHealthScore = useCallback((): number => {
    return state.systemHealth?.overall || 0;
  }, [state.systemHealth]);

  // Get performance score
  const getPerformanceScore = useCallback((): number => {
    return state.analytics?.performanceScore || 0;
  }, [state.analytics]);

  // Get recommendations
  const getRecommendations = useCallback((): string[] => {
    return state.analytics?.recommendations || [];
  }, [state.analytics]);

  // Auto-initialize if enabled
  useEffect(() => {
    if (autoInitialize && !state.isInitialized) {
      initialize({});
    }
  }, [autoInitialize, state.isInitialized, initialize]);

  // Auto-refresh setup
  useEffect(() => {
    if (!state.isInitialized || !enableRealTimeUpdates) return;

    const interval = setInterval(refresh, updateInterval);
    return () => clearInterval(interval);
  }, [state.isInitialized, enableRealTimeUpdates, updateInterval, refresh]);

  // Computed values
  const isHealthy = useMemo(() => {
    return state.systemHealth?.status === 'healthy';
  }, [state.systemHealth]);

  const hasWarnings = useMemo(() => {
    return state.systemHealth?.status === 'warning' ||
           state.kpis.some(kpi => kpi.status === 'warning');
  }, [state.systemHealth, state.kpis]);

  const hasCriticalIssues = useMemo(() => {
    return state.systemHealth?.status === 'critical' ||
           state.kpis.some(kpi => kpi.status === 'critical');
  }, [state.systemHealth, state.kpis]);

  const quickStats = useMemo(() => {
    const totalKPIs = state.kpis.length;
    const healthyKPIs = state.kpis.filter(kpi => kpi.status === 'excellent' || kpi.status === 'good').length;
    const warningKPIs = state.kpis.filter(kpi => kpi.status === 'warning').length;
    const criticalKPIs = state.kpis.filter(kpi => kpi.status === 'critical').length;

    return {
      totalKPIs,
      healthyKPIs,
      warningKPIs,
      criticalKPIs,
      systemHealthScore: getSystemHealthScore(),
      performanceScore: getPerformanceScore(),
    };
  }, [state.kpis, getSystemHealthScore, getPerformanceScore]);

  // Actions object
  const actions: AnalyticsEnhancementActions = {
    initialize,
    refresh,
    updateTimeRange,
    generateReport,
    exportData,
    dismissAlert,
    getKPIsByCategory,
    getSystemHealthScore,
    getPerformanceScore,
    getRecommendations,
  };

  return {
    state,
    actions,
    isHealthy,
    hasWarnings,
    hasCriticalIssues,
    quickStats,
  };
};

/**
 * Generate alerts from analytics data
 */
function generateAlertsFromAnalytics(
  analytics: DataManagementAnalytics,
  thresholds: AnalyticsEnhancementConfig['alertThresholds']
): DataManagementAlert[] {
  const alerts: DataManagementAlert[] = [];

  // System health alerts
  if (analytics.systemHealth.overall < thresholds!.systemHealth) {
    alerts.push({
      id: `system-health-${Date.now()}`,
      type: 'system',
      severity: analytics.systemHealth.overall < 60 ? 'critical' : 'warning',
      title: 'System Health Alert',
      message: `System health score is ${analytics.systemHealth.overall.toFixed(1)}%, below threshold of ${thresholds!.systemHealth}%`,
      source: 'analytics',
      timestamp: new Date(),
      category: 'health',
    });
  }

  // Data quality alerts
  const dataQualityKPIs = analytics.aggregatedKPIs.filter(kpi =>
    kpi.category === AnalyticsCategory.DATA_QUALITY
  );

  dataQualityKPIs.forEach(kpi => {
    if (kpi.currentValue < thresholds!.dataQuality) {
      alerts.push({
        id: `data-quality-${kpi.id}-${Date.now()}`,
        type: 'data_quality',
        severity: kpi.status === 'critical' ? 'critical' : 'warning',
        title: 'Data Quality Alert',
        message: `${kpi.name} is ${kpi.currentValue}${kpi.unit}, below threshold of ${thresholds!.dataQuality}%`,
        source: 'analytics',
        timestamp: new Date(),
        category: 'quality',
      });
    }
  });

  // Performance recommendations as info alerts
  analytics.recommendations.forEach((recommendation, index) => {
    alerts.push({
      id: `recommendation-${index}-${Date.now()}`,
      type: 'recommendation',
      severity: 'info',
      title: 'Performance Recommendation',
      message: recommendation,
      source: 'analytics',
      timestamp: new Date(),
      category: 'recommendation',
    });
  });

  return alerts;
}
