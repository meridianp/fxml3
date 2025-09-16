/**
 * DataQualityDashboard Component
 *
 * Real-time data quality monitoring and validation dashboard with interactive management
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  ShieldCheckIcon,
  ExclamationTriangleIcon,
  ChartBarIcon,
  DocumentArrowDownIcon,
  ArrowPathIcon,
  CogIcon,
  PlusIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  XMarkIcon,
  CheckIcon,
} from '@heroicons/react/24/outline';
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
  PieChart,
  Pie,
  Cell,
} from 'recharts';
import { DataQualityService } from '@/services/dataQuality';
import { NotificationService } from '@/services/notification';
import { DataQualityReport, ValidationRule, QualityLevel, DataManagementAlert } from '@/types/dataManagement';
import { clsx } from 'clsx';

export interface DataQualityDashboardProps {
  className?: string;
  gridArea?: string;
  refreshInterval?: number;
  autoRefresh?: boolean;

  // Dashboard integration props
  dataQualityService?: DataQualityService;
  notificationService?: NotificationService;
  onAlert?: (alert: DataManagementAlert) => void;
  onQualityUpdate?: (report: DataQualityReport) => void;
  onStatusChange?: (event: QualityStatusEvent) => void;
}

interface QualityStatusEvent {
  type: 'data_quality';
  status: 'excellent' | 'good' | 'fair' | 'poor' | 'critical';
  qualityScore: number;
  level: QualityLevel;
  timestamp: Date;
}

interface QualityTrendData {
  timestamp: string;
  overallScore: number;
  completeness: number;
  accuracy: number;
  consistency: number;
  timeliness: number;
}

interface DatasetChartData {
  name: string;
  score: number;
  level: QualityLevel;
}

interface QualityFilter {
  timeRange: '1h' | '24h' | '7d' | '30d';
  dataset: 'all' | string;
}

interface NewValidationRule {
  name: string;
  description: string;
  dataset: string;
  field: string;
  type: 'range' | 'regex' | 'freshness' | 'uniqueness';
  parameters: Record<string, any>;
  severity: 'warning' | 'error';
}

const COLORS = ['#22c55e', '#3b82f6', '#f59e0b', '#ef4444', '#dc2626'];
const QUALITY_THRESHOLDS = {
  EXCELLENT: 90,
  GOOD: 75,
  FAIR: 60,
  POOR: 45,
};

export const DataQualityDashboard: React.FC<DataQualityDashboardProps> = ({
  className = '',
  gridArea,
  refreshInterval = 30000,
  autoRefresh = true,
  dataQualityService: providedDataQualityService,
  notificationService: providedNotificationService,
  onAlert,
  onQualityUpdate,
  onStatusChange,
}) => {
  const [report, setReport] = useState<DataQualityReport | null>(null);
  const [qualityHistory, setQualityHistory] = useState<QualityTrendData[]>([]);
  const [validationRules, setValidationRules] = useState<ValidationRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set());
  const [showRulesManagement, setShowRulesManagement] = useState(false);
  const [showCreateRule, setShowCreateRule] = useState(false);
  const [isRunningValidation, setIsRunningValidation] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [filters, setFilters] = useState<QualityFilter>({
    timeRange: '1h',
    dataset: 'all',
  });
  const [newRule, setNewRule] = useState<NewValidationRule>({
    name: '',
    description: '',
    dataset: 'market_data',
    field: '',
    type: 'range',
    parameters: {},
    severity: 'warning',
  });

  // Services
  const dataQualityService = useMemo(() =>
    providedDataQualityService || new DataQualityService({
      apiBaseUrl: process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000/api',
    }), [providedDataQualityService]);

  const notificationService = useMemo(() =>
    providedNotificationService || new NotificationService(), [providedNotificationService]);

  // Format numbers
  const formatNumber = useCallback((num: number) => {
    return new Intl.NumberFormat().format(Math.round(num));
  }, []);

  // Format percentage
  const formatPercentage = useCallback((num: number) => {
    return `${num.toFixed(1)}%`;
  }, []);

  // Get quality level color
  const getQualityLevelColor = useCallback((level: QualityLevel) => {
    switch (level) {
      case QualityLevel.EXCELLENT:
        return 'text-green-600';
      case QualityLevel.GOOD:
        return 'text-blue-600';
      case QualityLevel.FAIR:
        return 'text-yellow-600';
      case QualityLevel.POOR:
        return 'text-orange-600';
      case QualityLevel.CRITICAL:
        return 'text-red-600';
      default:
        return 'text-gray-600';
    }
  }, []);

  // Get quality level background color
  const getQualityLevelBgColor = useCallback((level: QualityLevel) => {
    switch (level) {
      case QualityLevel.EXCELLENT:
        return 'bg-green-100';
      case QualityLevel.GOOD:
        return 'bg-blue-100';
      case QualityLevel.FAIR:
        return 'bg-yellow-100';
      case QualityLevel.POOR:
        return 'bg-orange-100';
      case QualityLevel.CRITICAL:
        return 'bg-red-100';
      default:
        return 'bg-gray-100';
    }
  }, []);

  // Get quality status from score
  const getQualityStatus = useCallback((score: number): 'excellent' | 'good' | 'fair' | 'poor' | 'critical' => {
    if (score >= QUALITY_THRESHOLDS.EXCELLENT) return 'excellent';
    if (score >= QUALITY_THRESHOLDS.GOOD) return 'good';
    if (score >= QUALITY_THRESHOLDS.FAIR) return 'fair';
    if (score >= QUALITY_THRESHOLDS.POOR) return 'poor';
    return 'critical';
  }, []);

  // Load quality report
  const loadQualityReport = useCallback(async () => {
    try {
      setError(null);
      const qualityReport = await dataQualityService.getQualityReport();
      setReport(qualityReport);

      if (onQualityUpdate) {
        onQualityUpdate(qualityReport);
      }

      // Check for alerts
      checkAndGenerateAlerts(qualityReport);

      // Emit status change event
      if (onStatusChange) {
        const status = getQualityStatus(qualityReport.overall.score);
        onStatusChange({
          type: 'data_quality',
          status,
          qualityScore: qualityReport.overall.score,
          level: qualityReport.overall.level,
          timestamp: new Date(),
        });
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error';
      setError(`Error loading data quality report: ${errorMessage}`);
    } finally {
      setLoading(false);
    }
  }, [dataQualityService, onQualityUpdate, onStatusChange, getQualityStatus]);

  // Load quality history
  const loadQualityHistory = useCallback(async () => {
    try {
      const endTime = new Date();
      const startTime = new Date();

      // Calculate start time based on selected range
      switch (filters.timeRange) {
        case '1h':
          startTime.setHours(endTime.getHours() - 1);
          break;
        case '24h':
          startTime.setDate(endTime.getDate() - 1);
          break;
        case '7d':
          startTime.setDate(endTime.getDate() - 7);
          break;
        case '30d':
          startTime.setDate(endTime.getDate() - 30);
          break;
      }

      const interval = filters.timeRange === '1h' ? '5m' :
                     filters.timeRange === '24h' ? '1h' :
                     filters.timeRange === '7d' ? '6h' : '1d';

      const history = await dataQualityService.getQualityHistory({
        start: startTime,
        end: endTime,
        interval,
      });

      setQualityHistory(history);
    } catch (err) {
      console.error('Error loading quality history:', err);
    }
  }, [dataQualityService, filters.timeRange]);

  // Load validation rules
  const loadValidationRules = useCallback(async () => {
    try {
      const rules = await dataQualityService.getValidationRules();
      setValidationRules(rules);
    } catch (err) {
      console.error('Error loading validation rules:', err);
    }
  }, [dataQualityService]);

  // Check and generate alerts
  const checkAndGenerateAlerts = useCallback((qualityReport: DataQualityReport) => {
    if (!onAlert) return;

    const alerts: DataManagementAlert[] = [];

    // Overall quality score alerts
    const overallScore = qualityReport.overall.score;
    if (overallScore < QUALITY_THRESHOLDS.POOR) {
      alerts.push({
        id: `quality-critical-${Date.now()}`,
        type: 'data_quality',
        severity: 'critical',
        title: 'Critical Data Quality Issues',
        message: `Overall data quality score is ${formatPercentage(overallScore)} - immediate attention required`,
        source: 'DataQualityDashboard',
        timestamp: new Date(),
        acknowledged: false,
        resolved: false,
        metadata: { score: overallScore, threshold: QUALITY_THRESHOLDS.POOR },
      });
    } else if (overallScore < QUALITY_THRESHOLDS.FAIR) {
      alerts.push({
        id: `quality-poor-${Date.now()}`,
        type: 'data_quality',
        severity: 'warning',
        title: 'Poor Data Quality Detected',
        message: `Overall data quality score is ${formatPercentage(overallScore)} - review recommended`,
        source: 'DataQualityDashboard',
        timestamp: new Date(),
        acknowledged: false,
        resolved: false,
        metadata: { score: overallScore, threshold: QUALITY_THRESHOLDS.FAIR },
      });
    }

    // High validation failure rate alerts
    const totalFailures = qualityReport.failedValidations.reduce((sum, failure) => sum + failure.count, 0);
    const failureRate = totalFailures / qualityReport.overall.totalRecords;

    if (failureRate > 0.1) { // More than 10% failure rate
      alerts.push({
        id: `validation-failures-${Date.now()}`,
        type: 'data_quality',
        severity: 'critical',
        title: 'High Validation Failure Rate',
        message: `${formatNumber(totalFailures)} failed validations detected (${formatPercentage(failureRate * 100)} failure rate)`,
        source: 'DataQualityDashboard',
        timestamp: new Date(),
        acknowledged: false,
        resolved: false,
        metadata: { totalFailures, failureRate, threshold: 0.1 },
      });
    }

    // Emit alerts
    alerts.forEach(alert => onAlert(alert));
  }, [onAlert, formatPercentage, formatNumber]);

  // Run validation
  const runValidation = useCallback(async () => {
    setIsRunningValidation(true);
    try {
      const result = await dataQualityService.runValidation({
        datasets: ['all'],
        rules: ['all'],
      });

      notificationService.create({
        type: 'success',
        title: 'Validation Complete',
        message: `Validated ${formatNumber(result.validatedRecords)} records with ${formatNumber(result.failedRecords)} failures in ${(result.executionTime / 1000).toFixed(1)}s`,
      });

      // Reload quality report after validation
      loadQualityReport();
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error';
      notificationService.create({
        type: 'error',
        title: 'Validation Failed',
        message: `Failed to run data validation: ${errorMessage}`,
      });
    } finally {
      setIsRunningValidation(false);
    }
  }, [dataQualityService, notificationService, formatNumber, loadQualityReport]);

  // Export quality report
  const exportReport = useCallback(async () => {
    setIsExporting(true);
    try {
      const result = await dataQualityService.exportReport({
        format: 'pdf',
        includeCharts: true,
        includeDetails: true,
      });

      const sizeKB = Math.round(result.size / 1024);
      notificationService.create({
        type: 'success',
        title: 'Report Exported',
        message: `Quality report exported as ${result.filename} (${sizeKB} KB)`,
      });
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error';
      notificationService.create({
        type: 'error',
        title: 'Export Failed',
        message: `Failed to export quality report: ${errorMessage}`,
      });
    } finally {
      setIsExporting(false);
    }
  }, [dataQualityService, notificationService]);

  // Toggle validation rule enabled state
  const toggleValidationRule = useCallback(async (ruleId: string, enabled: boolean) => {
    try {
      await dataQualityService.updateValidationRule(ruleId, { enabled });
      loadValidationRules();

      notificationService.create({
        type: 'success',
        title: 'Rule Updated',
        message: `Validation rule ${enabled ? 'enabled' : 'disabled'} successfully`,
      });
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error';
      notificationService.create({
        type: 'error',
        title: 'Update Failed',
        message: `Failed to update validation rule: ${errorMessage}`,
      });
    }
  }, [dataQualityService, notificationService, loadValidationRules]);

  // Create new validation rule
  const createValidationRule = useCallback(async () => {
    try {
      const rule: Omit<ValidationRule, 'id' | 'createdAt' | 'updatedAt'> = {
        ...newRule,
        enabled: true,
      };

      await dataQualityService.createValidationRule(rule);
      loadValidationRules();
      setShowCreateRule(false);
      setNewRule({
        name: '',
        description: '',
        dataset: 'market_data',
        field: '',
        type: 'range',
        parameters: {},
        severity: 'warning',
      });

      notificationService.create({
        type: 'success',
        title: 'Rule Created',
        message: `Validation rule "${rule.name}" created successfully`,
      });
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error';
      notificationService.create({
        type: 'error',
        title: 'Create Failed',
        message: `Failed to create validation rule: ${errorMessage}`,
      });
    }
  }, [dataQualityService, notificationService, newRule, loadValidationRules]);

  // Toggle section expansion
  const toggleSection = useCallback((section: string) => {
    setExpandedSections(prev => {
      const newSet = new Set(prev);
      if (newSet.has(section)) {
        newSet.delete(section);
      } else {
        newSet.add(section);
      }
      return newSet;
    });
  }, []);

  // Filter datasets
  const filteredDatasets = useMemo(() => {
    if (!report) return [];

    const datasets = Object.entries(report.datasetMetrics);
    if (filters.dataset === 'all') {
      return datasets;
    }
    return datasets.filter(([name]) => name === filters.dataset);
  }, [report, filters.dataset]);

  // Convert datasets to chart data
  const datasetChartData = useMemo(() => {
    if (!report) return [];

    return Object.entries(report.datasetMetrics).map(([name, metrics]) => ({
      name,
      score: metrics.score,
      level: metrics.level,
    }));
  }, [report]);

  // Mobile detection
  const isMobile = typeof window !== 'undefined' && window.innerWidth <= 768;
  const isSmallScreen = typeof window !== 'undefined' && window.innerWidth <= 640;

  // Initial load
  useEffect(() => {
    loadQualityReport();
    loadQualityHistory();
  }, [loadQualityReport, loadQualityHistory]);

  // Auto-refresh
  useEffect(() => {
    if (!autoRefresh || refreshInterval <= 0) return;

    const interval = setInterval(() => {
      loadQualityReport();
      loadQualityHistory();
    }, refreshInterval);

    return () => clearInterval(interval);
  }, [autoRefresh, refreshInterval, loadQualityReport, loadQualityHistory]);

  // Update history when time range changes
  useEffect(() => {
    if (!loading) {
      loadQualityHistory();
    }
  }, [filters.timeRange, loadQualityHistory, loading]);

  if (loading) {
    return (
      <div
        className={clsx('bg-white shadow rounded-lg p-6', className)}
        style={gridArea ? { gridArea } : undefined}
      >
        <h2 className="text-lg font-medium text-gray-900 mb-4">Data Quality Dashboard</h2>
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
      style={gridArea ? { gridArea } : undefined}
      data-testid="data-quality-dashboard"
      role="region"
      aria-label="Data Quality Dashboard"
    >
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-200">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-medium text-gray-900">Data Quality Dashboard</h2>
          <div className="flex items-center space-x-2">
            <button
              onClick={runValidation}
              disabled={isRunningValidation}
              data-testid="run-validation"
              className={clsx(
                'inline-flex items-center px-3 py-2 border border-gray-300 shadow-sm text-sm leading-4 font-medium rounded-md focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500',
                isRunningValidation
                  ? 'text-gray-400 bg-gray-100 cursor-not-allowed'
                  : 'text-gray-700 bg-white hover:bg-gray-50'
              )}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !isRunningValidation) {
                  runValidation();
                }
              }}
            >
              {isRunningValidation ? (
                <>
                  <ArrowPathIcon className="h-4 w-4 mr-2 animate-spin" />
                  Validating...
                </>
              ) : (
                <>
                  <ShieldCheckIcon className="h-4 w-4 mr-2" />
                  Run Validation
                </>
              )}
            </button>
            <button
              onClick={exportReport}
              disabled={isExporting}
              data-testid="export-report"
              className={clsx(
                'inline-flex items-center px-3 py-2 border border-gray-300 shadow-sm text-sm leading-4 font-medium rounded-md focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500',
                isExporting
                  ? 'text-gray-400 bg-gray-100 cursor-not-allowed'
                  : 'text-gray-700 bg-white hover:bg-gray-50'
              )}
            >
              {isExporting ? (
                <>
                  <ArrowPathIcon className="h-4 w-4 mr-2 animate-spin" />
                  Exporting...
                </>
              ) : (
                <>
                  <DocumentArrowDownIcon className="h-4 w-4 mr-2" />
                  Export
                </>
              )}
            </button>
            <button
              onClick={() => setShowRulesManagement(!showRulesManagement)}
              data-testid="manage-validation-rules"
              className="inline-flex items-center px-3 py-2 border border-gray-300 shadow-sm text-sm leading-4 font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
            >
              <CogIcon className="h-4 w-4 mr-2" />
              Manage Rules
            </button>
            <button
              onClick={() => {
                loadQualityReport();
                loadQualityHistory();
              }}
              className="inline-flex items-center px-3 py-2 border border-gray-300 shadow-sm text-sm leading-4 font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
            >
              <ArrowPathIcon className="h-4 w-4 mr-2" />
              Refresh
            </button>
          </div>
        </div>

        {/* Controls */}
        <div className="mt-4 flex flex-col md:flex-row md:items-center md:space-x-4 space-y-2 md:space-y-0">
          {/* Time Range Filter */}
          <div className="min-w-0">
            <select
              value={filters.timeRange}
              onChange={(e) => setFilters(prev => ({ ...prev, timeRange: e.target.value as QualityFilter['timeRange'] }))}
              className="block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-blue-500 focus:border-blue-500 text-sm rounded-md"
              aria-label="Time range"
            >
              <option value="1h">Last Hour</option>
              <option value="24h">Last 24 Hours</option>
              <option value="7d">Last 7 Days</option>
              <option value="30d">Last 30 Days</option>
            </select>
          </div>

          {/* Dataset Filter */}
          <div className="min-w-0">
            <select
              value={filters.dataset}
              onChange={(e) => setFilters(prev => ({ ...prev, dataset: e.target.value }))}
              className="block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-blue-500 focus:border-blue-500 text-sm rounded-md"
              aria-label="Filter datasets"
            >
              <option value="all">All Datasets</option>
              <option value="market_data">Market Data</option>
              <option value="features">Features</option>
              <option value="signals">Signals</option>
            </select>
          </div>
        </div>
      </div>

      {/* Error Message */}
      {error && (
        <div className="px-6 py-4 bg-red-50 border-l-4 border-red-400">
          <div className="text-sm text-red-700">{error}</div>
        </div>
      )}

      {/* Quality Metrics */}
      <div className="px-6 py-4">
        {report && (
          <div className="space-y-6">
            {/* Overall Quality Score Section */}
            <div className="border border-gray-200 rounded-lg p-6">
              <h3 className="text-lg font-medium text-gray-900 mb-4">Overall Quality Score</h3>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                <div className="text-center">
                  <div
                    className={clsx('text-3xl font-bold', getQualityLevelColor(report.overall.level))}
                    data-testid="overall-quality-score"
                  >
                    {report.overall.score.toFixed(1)}
                  </div>
                  <div className="text-sm text-gray-500">Quality Score</div>
                  <div
                    className={clsx('text-xs px-2 py-1 rounded-full mt-1 capitalize', getQualityLevelBgColor(report.overall.level), getQualityLevelColor(report.overall.level))}
                    data-testid="quality-level"
                  >
                    {report.overall.level}
                  </div>
                </div>

                <div className="text-center">
                  <div className="text-2xl font-semibold text-gray-900" data-testid="total-records">
                    {formatNumber(report.overall.totalRecords)}
                  </div>
                  <div className="text-sm text-gray-500">Total Records</div>
                </div>

                <div className="text-center">
                  <div className="text-2xl font-semibold text-green-600" data-testid="valid-records">
                    {formatNumber(report.overall.validRecords)}
                  </div>
                  <div className="text-sm text-gray-500">Valid Records</div>
                </div>

                <div className="text-center">
                  <div className="text-2xl font-semibold text-red-600" data-testid="invalid-records">
                    {formatNumber(report.overall.invalidRecords)}
                  </div>
                  <div className="text-sm text-gray-500">Invalid Records</div>
                </div>
              </div>

              {/* Quality Dimensions */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="text-center">
                  <div className="text-xl font-semibold text-blue-600" data-testid="completeness-score">
                    {formatPercentage(report.overall.completeness)}
                  </div>
                  <div className="text-sm text-gray-500">Completeness</div>
                </div>
                <div className="text-center">
                  <div className="text-xl font-semibold text-green-600" data-testid="accuracy-score">
                    {formatPercentage(report.overall.accuracy)}
                  </div>
                  <div className="text-sm text-gray-500">Accuracy</div>
                </div>
                <div className="text-center">
                  <div className="text-xl font-semibold text-purple-600" data-testid="consistency-score">
                    {formatPercentage(report.overall.consistency)}
                  </div>
                  <div className="text-sm text-gray-500">Consistency</div>
                </div>
                <div className="text-center">
                  <div className="text-xl font-semibold text-indigo-600" data-testid="timeliness-score">
                    {formatPercentage(report.overall.timeliness)}
                  </div>
                  <div className="text-sm text-gray-500">Timeliness</div>
                </div>
              </div>
            </div>

            {/* Dataset Quality Section */}
            <div className="border border-gray-200 rounded-lg">
              <div className="px-4 py-3 bg-gray-50 border-b border-gray-200">
                <h3 className="text-lg font-medium text-gray-900">Dataset Quality</h3>
              </div>

              <div className="p-4">
                <div className="space-y-4">
                  {filteredDatasets.map(([datasetName, metrics]) => (
                    <div
                      key={datasetName}
                      className="border border-gray-100 rounded-lg p-4"
                      data-testid={`dataset-${datasetName}`}
                    >
                      <div className="flex items-center justify-between mb-3">
                        <div className="flex items-center">
                          <h4 className="text-md font-medium text-gray-900">{datasetName}</h4>
                          <div
                            className={clsx('ml-2 text-xs px-2 py-1 rounded-full capitalize', getQualityLevelBgColor(metrics.level), getQualityLevelColor(metrics.level))}
                          >
                            {metrics.level}
                          </div>
                        </div>
                        <div className={clsx('text-xl font-bold', getQualityLevelColor(metrics.level))}>
                          {metrics.score.toFixed(1)}
                        </div>
                      </div>

                      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                        <div>
                          <div className="text-gray-500">Records</div>
                          <div className="font-medium">{formatNumber(metrics.recordCount)}</div>
                        </div>
                        <div>
                          <div className="text-gray-500">Completeness</div>
                          <div className="font-medium">{formatPercentage(metrics.completeness)}</div>
                        </div>
                        <div>
                          <div className="text-gray-500">Accuracy</div>
                          <div className="font-medium">{formatPercentage(metrics.accuracy)}</div>
                        </div>
                        <div>
                          <div className="text-gray-500">Last Updated</div>
                          <div className="font-medium">{metrics.lastUpdated.toLocaleTimeString()}</div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Failed Validations Section */}
            <div className="border border-gray-200 rounded-lg">
              <div
                className="px-4 py-3 bg-gray-50 border-b border-gray-200 flex items-center justify-between cursor-pointer"
                onClick={() => toggleSection('validation-failures')}
              >
                <h3 className="text-lg font-medium text-gray-900">Failed Validations</h3>
                <button
                  data-testid="expand-validation-failures"
                  className="text-gray-400 hover:text-gray-600"
                >
                  {expandedSections.has('validation-failures') ? (
                    <ChevronDownIcon className="h-5 w-5" />
                  ) : (
                    <ChevronRightIcon className="h-5 w-5" />
                  )}
                </button>
              </div>

              <div className="p-4">
                <div className="text-sm text-gray-600 mb-4">
                  {formatNumber(report.failedValidations.reduce((sum, failure) => sum + failure.count, 0))} total validation failures
                </div>

                {expandedSections.has('validation-failures') && (
                  <div className="space-y-4">
                    {report.failedValidations.map((failure) => (
                      <div key={failure.id} className="border border-gray-100 rounded-lg p-4">
                        <div className="flex items-start justify-between mb-2">
                          <div>
                            <h4 className="text-md font-medium text-gray-900">{failure.rule.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}</h4>
                            <div className="text-sm text-gray-600">{failure.dataset}.{failure.field}</div>
                          </div>
                          <div className="text-right">
                            <div className={clsx('text-lg font-bold', failure.severity === 'error' ? 'text-red-600' : 'text-orange-600')}>
                              {formatNumber(failure.count)} failures
                            </div>
                            <div className={clsx('text-xs px-2 py-1 rounded-full', failure.severity === 'error' ? 'bg-red-100 text-red-700' : 'bg-orange-100 text-orange-700')}>
                              {failure.severity}
                            </div>
                          </div>
                        </div>
                        <div className="text-sm text-gray-700 mb-2">{failure.message}</div>
                        {failure.samples && failure.samples.length > 0 && (
                          <div className="text-xs text-gray-500">
                            Sample failures: {failure.samples.map(sample => sample.recordId).join(', ')}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Charts Section */}
            <div
              className={clsx(
                'flex gap-6',
                isSmallScreen ? 'flex-col' : 'flex-col lg:flex-row'
              )}
              data-testid="charts-container"
            >
              {/* Quality Trends Chart */}
              {qualityHistory && qualityHistory.length > 0 && (
                <div className="border border-gray-200 rounded-lg p-4 flex-1" data-testid="quality-trends-chart">
                  <h3 className="text-lg font-medium text-gray-900 mb-4">Quality Trends</h3>
                  <ResponsiveContainer width="100%" height={300}>
                    <LineChart data={qualityHistory}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis
                        dataKey="timestamp"
                        tickFormatter={(value) => new Date(value).toLocaleTimeString()}
                      />
                      <YAxis domain={[0, 100]} />
                      <Tooltip
                        labelFormatter={(value) => new Date(value).toLocaleString()}
                        formatter={(value: any, name: string) => [`${value.toFixed(1)}%`, name]}
                      />
                      <Legend />
                      <Line
                        type="monotone"
                        dataKey="overallScore"
                        stroke="#3b82f6"
                        name="Overall Score"
                      />
                      <Line
                        type="monotone"
                        dataKey="completeness"
                        stroke="#22c55e"
                        name="Completeness"
                      />
                      <Line
                        type="monotone"
                        dataKey="accuracy"
                        stroke="#ef4444"
                        name="Accuracy"
                      />
                      <Line
                        type="monotone"
                        dataKey="timeliness"
                        stroke="#8b5cf6"
                        name="Timeliness"
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              )}

              {/* Dataset Distribution Chart */}
              {datasetChartData.length > 0 && (
                <div className="border border-gray-200 rounded-lg p-4 flex-1" data-testid="dataset-distribution-chart">
                  <h3 className="text-lg font-medium text-gray-900 mb-4">Dataset Quality Distribution</h3>
                  <ResponsiveContainer width="100%" height={300}>
                    <PieChart>
                      <Pie
                        data={datasetChartData}
                        cx="50%"
                        cy="50%"
                        labelLine={false}
                        label={({ name, score }) => `${name} (${score.toFixed(1)})`}
                        outerRadius={80}
                        fill="#8884d8"
                        dataKey="score"
                      >
                        {datasetChartData.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip formatter={(value: any) => [`${value.toFixed(1)}`, 'Quality Score']} />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Validation Rules Management Modal */}
      {showRulesManagement && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-4xl max-h-[90vh] overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
              <h3 className="text-lg font-medium text-gray-900">Validation Rules</h3>
              <div className="flex items-center space-x-2">
                <button
                  onClick={() => {
                    setShowCreateRule(true);
                    loadValidationRules();
                  }}
                  data-testid="create-validation-rule"
                  className="inline-flex items-center px-3 py-2 border border-transparent shadow-sm text-sm leading-4 font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                >
                  <PlusIcon className="h-4 w-4 mr-2" />
                  Create Rule
                </button>
                <button
                  onClick={() => setShowRulesManagement(false)}
                  className="text-gray-400 hover:text-gray-600"
                >
                  <XMarkIcon className="h-5 w-5" />
                </button>
              </div>
            </div>

            <div className="px-6 py-4 max-h-96 overflow-y-auto">
              <div className="space-y-4">
                {validationRules.map((rule) => (
                  <div key={rule.id} className="border border-gray-200 rounded-lg p-4">
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <h4 className="text-md font-medium text-gray-900">{rule.name}</h4>
                        <p className="text-sm text-gray-600 mt-1">{rule.description}</p>
                        <div className="text-xs text-gray-500 mt-2">
                          {rule.dataset}.{rule.field} | {rule.type} | {rule.severity}
                        </div>
                      </div>
                      <div className="flex items-center space-x-2">
                        <button
                          onClick={() => toggleValidationRule(rule.id, !rule.enabled)}
                          data-testid={`toggle-rule-${rule.id}`}
                          className={clsx(
                            'inline-flex items-center px-2 py-1 rounded-full text-xs font-medium',
                            rule.enabled
                              ? 'bg-green-100 text-green-800'
                              : 'bg-gray-100 text-gray-800'
                          )}
                        >
                          {rule.enabled ? (
                            <>
                              <CheckIcon className="h-3 w-3 mr-1" />
                              Enabled
                            </>
                          ) : (
                            <>
                              <XMarkIcon className="h-3 w-3 mr-1" />
                              Disabled
                            </>
                          )}
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Create Rule Modal */}
      {showCreateRule && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full mx-4">
            <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
              <h3 className="text-lg font-medium text-gray-900">Create Validation Rule</h3>
              <button
                onClick={() => setShowCreateRule(false)}
                className="text-gray-400 hover:text-gray-600"
              >
                <XMarkIcon className="h-5 w-5" />
              </button>
            </div>

            <div className="px-6 py-4">
              <div className="space-y-4">
                <div>
                  <label htmlFor="rule-name" className="block text-sm font-medium text-gray-700">
                    Rule Name
                  </label>
                  <input
                    type="text"
                    id="rule-name"
                    value={newRule.name}
                    onChange={(e) => setNewRule(prev => ({ ...prev, name: e.target.value }))}
                    className="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 text-sm"
                    aria-label="Rule Name"
                  />
                </div>

                <div>
                  <label htmlFor="rule-description" className="block text-sm font-medium text-gray-700">
                    Description
                  </label>
                  <textarea
                    id="rule-description"
                    value={newRule.description}
                    onChange={(e) => setNewRule(prev => ({ ...prev, description: e.target.value }))}
                    rows={3}
                    className="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 text-sm"
                    aria-label="Description"
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label htmlFor="rule-dataset" className="block text-sm font-medium text-gray-700">
                      Dataset
                    </label>
                    <select
                      id="rule-dataset"
                      value={newRule.dataset}
                      onChange={(e) => setNewRule(prev => ({ ...prev, dataset: e.target.value }))}
                      className="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 text-sm"
                      aria-label="Dataset"
                    >
                      <option value="market_data">Market Data</option>
                      <option value="features">Features</option>
                      <option value="signals">Signals</option>
                    </select>
                  </div>

                  <div>
                    <label htmlFor="rule-field" className="block text-sm font-medium text-gray-700">
                      Field
                    </label>
                    <input
                      type="text"
                      id="rule-field"
                      value={newRule.field}
                      onChange={(e) => setNewRule(prev => ({ ...prev, field: e.target.value }))}
                      className="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 text-sm"
                      aria-label="Field"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label htmlFor="rule-type" className="block text-sm font-medium text-gray-700">
                      Rule Type
                    </label>
                    <select
                      id="rule-type"
                      value={newRule.type}
                      onChange={(e) => setNewRule(prev => ({ ...prev, type: e.target.value as NewValidationRule['type'] }))}
                      className="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 text-sm"
                    >
                      <option value="range">Range</option>
                      <option value="regex">Regex</option>
                      <option value="freshness">Freshness</option>
                      <option value="uniqueness">Uniqueness</option>
                    </select>
                  </div>

                  <div>
                    <label htmlFor="rule-severity" className="block text-sm font-medium text-gray-700">
                      Severity
                    </label>
                    <select
                      id="rule-severity"
                      value={newRule.severity}
                      onChange={(e) => setNewRule(prev => ({ ...prev, severity: e.target.value as NewValidationRule['severity'] }))}
                      className="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 text-sm"
                    >
                      <option value="warning">Warning</option>
                      <option value="error">Error</option>
                    </select>
                  </div>
                </div>
              </div>
            </div>

            <div className="px-6 py-4 border-t border-gray-200 flex items-center justify-end space-x-2">
              <button
                onClick={() => setShowCreateRule(false)}
                className="inline-flex items-center px-3 py-2 border border-gray-300 shadow-sm text-sm leading-4 font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
              >
                Cancel
              </button>
              <button
                onClick={createValidationRule}
                disabled={!newRule.name || !newRule.field}
                data-testid="save-validation-rule"
                className={clsx(
                  'inline-flex items-center px-3 py-2 border border-transparent shadow-sm text-sm leading-4 font-medium rounded-md focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500',
                  !newRule.name || !newRule.field
                    ? 'text-gray-400 bg-gray-100 cursor-not-allowed'
                    : 'text-white bg-blue-600 hover:bg-blue-700'
                )}
              >
                Save Rule
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
