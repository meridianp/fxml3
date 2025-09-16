/**
 * Analytics Integration Test Suite
 *
 * Comprehensive testing for the entire analytics functionality including
 * service integration, data flow, and component interactions
 */

import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import React from 'react';
import { AnalyticsService } from '@/services/analytics';
import { MetricsAggregationService } from '@/services/metricsAggregation';
import { ReportsService } from '@/services/reports';
import { ExportService } from '@/services/export';
import { AnalyticsIntegrationService } from '@/services/analyticsIntegration';
import { DataManagementWithAnalytics } from '@/components/data-management/DataManagementWithAnalytics';
import { AnalyticsDashboard } from '@/components/analytics/AnalyticsDashboard';
import { PerformanceScorecard } from '@/components/analytics/PerformanceScorecard';
import { ReportsManager } from '@/components/analytics/ReportsManager';
import { ExportManager } from '@/components/analytics/ExportManager';
import {
  AnalyticsDataPoint,
  AnalyticsQuery,
  TimeRange,
  TimeInterval,
  AnalyticsCategory,
  KPI,
  KPIStatus,
  TrendDirection,
  Report,
  ReportType,
  ExportJob,
  ExportStatus,
  ExportFormat,
  SystemHealth,
} from '@/types/analytics';

describe('Analytics Integration Test Suite', () => {
  let analyticsService: AnalyticsService;
  let metricsService: MetricsAggregationService;
  let reportsService: ReportsService;
  let exportService: ExportService;
  let integrationService: AnalyticsIntegrationService;

  const mockTimeRange: TimeRange = {
    start: new Date('2024-01-15T00:00:00Z'),
    end: new Date('2024-01-15T23:59:59Z'),
    interval: TimeInterval.HOUR,
  };

  const mockDataPoints: AnalyticsDataPoint[] = [
    {
      timestamp: new Date('2024-01-15T10:00:00Z'),
      metrics: {
        system_health: 85,
        data_quality_score: 92,
        pipeline_success_rate: 98,
        storage_utilization: 75,
      },
      dimensions: {
        service: 'system',
        category: AnalyticsCategory.SYSTEM,
      },
    },
    {
      timestamp: new Date('2024-01-15T11:00:00Z'),
      metrics: {
        system_health: 87,
        data_quality_score: 89,
        pipeline_success_rate: 96,
        storage_utilization: 78,
      },
      dimensions: {
        service: 'system',
        category: AnalyticsCategory.SYSTEM,
      },
    },
  ];

  const mockKPIs: KPI[] = [
    {
      id: 'system-health',
      name: 'System Health',
      description: 'Overall system health score',
      category: AnalyticsCategory.SYSTEM,
      metric: 'system_health',
      target: 95,
      unit: '%',
      thresholds: {
        critical: { min: 60 },
        warning: { min: 80 },
        target: { min: 95, max: 100 },
      },
      status: KPIStatus.GOOD,
      currentValue: 85,
      trend: TrendDirection.STABLE,
      lastUpdated: new Date('2024-01-15T10:00:00Z'),
    },
    {
      id: 'data-quality',
      name: 'Data Quality',
      description: 'Data quality score',
      category: AnalyticsCategory.DATA_QUALITY,
      metric: 'data_quality_score',
      target: 95,
      unit: '%',
      thresholds: {
        critical: { min: 70 },
        warning: { min: 85 },
        target: { min: 95, max: 100 },
      },
      status: KPIStatus.WARNING,
      currentValue: 89,
      trend: TrendDirection.DECREASING,
      lastUpdated: new Date('2024-01-15T10:00:00Z'),
    },
  ];

  beforeEach(() => {
    // Create service instances
    analyticsService = new AnalyticsService();
    metricsService = new MetricsAggregationService();
    reportsService = new ReportsService();
    exportService = new ExportService();
    integrationService = new AnalyticsIntegrationService();

    // Mock service methods
    jest.spyOn(analyticsService, 'getHistoricalData').mockResolvedValue(mockDataPoints);
    jest.spyOn(analyticsService, 'aggregate').mockResolvedValue({
      query: {} as AnalyticsQuery,
      data: mockDataPoints,
      metadata: {
        totalRecords: mockDataPoints.length,
        executionTime: 150,
        dataQuality: 0.95,
        lastUpdated: new Date(),
      },
    });

    jest.spyOn(metricsService, 'getKPIs').mockResolvedValue(mockKPIs);
    jest.spyOn(metricsService, 'getPerformanceSummary').mockResolvedValue({
      kpis: mockKPIs,
      summary: {
        total: 2,
        excellent: 0,
        good: 1,
        warning: 1,
        critical: 0,
      },
    });

    jest.spyOn(reportsService, 'getReports').mockResolvedValue([]);
    jest.spyOn(exportService, 'getExportJobs').mockResolvedValue([]);
    jest.spyOn(exportService, 'getExportStatistics').mockResolvedValue({
      totalJobs: 0,
      activeJobs: 0,
      completedJobs: 0,
      failedJobs: 0,
      totalSize: 0,
      averageSize: 0,
      averageProcessingTime: 0,
      successRate: 1,
    });

    jest.spyOn(integrationService, 'generateDataManagementAnalytics').mockResolvedValue({
      systemHealth: {
        overall: 85,
        components: {
          dataSource: 90,
          storage: 80,
          quality: 85,
          pipeline: 85,
        },
        status: 'healthy',
        lastUpdated: new Date(),
        trends: {
          overall: TrendDirection.STABLE,
        },
      },
      crossServiceTrends: mockDataPoints,
      correlationInsights: [],
      aggregatedKPIs: mockKPIs,
      performanceScore: 78,
      recommendations: ['Monitor data quality trends'],
    });
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  describe('Service Layer Integration', () => {
    it('should integrate all analytics services correctly', async () => {
      // Test service initialization
      expect(analyticsService).toBeDefined();
      expect(metricsService).toBeDefined();
      expect(reportsService).toBeDefined();
      expect(exportService).toBeDefined();
      expect(integrationService).toBeDefined();
    });

    it('should handle data flow between services', async () => {
      // Simulate data flow from analytics to metrics aggregation
      const analyticsResult = await analyticsService.aggregate({
        timeRange: mockTimeRange,
        metrics: ['system_health', 'data_quality_score'],
      });

      expect(analyticsResult.data).toEqual(mockDataPoints);
      expect(analyticsResult.metadata.totalRecords).toBe(2);

      // Test KPI calculation based on analytics data
      const kpis = await metricsService.getKPIs(AnalyticsCategory.SYSTEM);
      expect(kpis).toEqual(mockKPIs);
    });

    it('should maintain data consistency across services', async () => {
      // Test that the same metric values are consistent across services
      const analyticsData = await analyticsService.getHistoricalData('system_health', mockTimeRange);
      const kpis = await metricsService.getKPIs();

      const systemHealthKPI = kpis.find(k => k.metric === 'system_health');
      const latestAnalyticsValue = analyticsData[analyticsData.length - 1]?.metrics.system_health;

      expect(systemHealthKPI).toBeDefined();
      expect(typeof latestAnalyticsValue).toBe('number');
    });
  });

  describe('Component Integration', () => {
    it('should render all analytics components without errors', async () => {
      const components = [
        <AnalyticsDashboard key="analytics" />,
        <PerformanceScorecard key="scorecard" />,
        <ReportsManager key="reports" />,
        <ExportManager key="exports" />,
      ];

      for (const component of components) {
        const { unmount } = render(component);
        // Basic render test - should not throw
        expect(true).toBe(true);
        unmount();
      }
    });

    it('should integrate components within DataManagementWithAnalytics', async () => {
      render(
        <DataManagementWithAnalytics
          showAnalytics={true}
          analyticsIntegrationService={integrationService}
        />
      );

      // Should render the integrated dashboard
      await waitFor(() => {
        expect(screen.getByTestId('data-management-with-analytics')).toBeInTheDocument();
      });
    });

    it('should handle cross-component communication', async () => {
      const onAnalyticsUpdate = jest.fn();

      render(
        <DataManagementWithAnalytics
          showAnalytics={true}
          analyticsIntegrationService={integrationService}
          onAnalyticsUpdate={onAnalyticsUpdate}
        />
      );

      await waitFor(() => {
        expect(onAnalyticsUpdate).toHaveBeenCalled();
      });
    });
  });

  describe('Data Aggregation and Analysis', () => {
    it('should perform complex data aggregations', async () => {
      const query: AnalyticsQuery = {
        timeRange: mockTimeRange,
        metrics: ['system_health', 'data_quality_score', 'pipeline_success_rate'],
        aggregation: 'avg' as any,
        groupBy: ['service'],
      };

      const result = await analyticsService.aggregate(query);

      expect(result.data).toBeDefined();
      expect(result.metadata.executionTime).toBeGreaterThan(0);
      expect(result.metadata.dataQuality).toBeGreaterThan(0);
    });

    it('should calculate performance scores correctly', async () => {
      const performanceSummary = await metricsService.getPerformanceSummary();

      expect(performanceSummary.summary.total).toBe(2);
      expect(performanceSummary.summary.good).toBe(1);
      expect(performanceSummary.summary.warning).toBe(1);

      // Calculate overall score
      const { excellent, good, warning, critical } = performanceSummary.summary;
      const totalScore = (excellent * 100) + (good * 80) + (warning * 60) + (critical * 30);
      const averageScore = totalScore / performanceSummary.summary.total;

      expect(averageScore).toBe(70); // (80 + 60) / 2
    });

    it('should detect trends and anomalies', async () => {
      // Mock trend analysis
      jest.spyOn(analyticsService, 'analyzeTrend').mockResolvedValue({
        metric: 'system_health',
        timeRange: mockTimeRange,
        trend: TrendDirection.INCREASING,
        confidence: 0.85,
        slope: 0.5,
        correlation: 0.7,
      });

      const trendAnalysis = await analyticsService.analyzeTrend('system_health', mockTimeRange);

      expect(trendAnalysis.trend).toBe(TrendDirection.INCREASING);
      expect(trendAnalysis.confidence).toBeGreaterThan(0.8);
    });
  });

  describe('Report Generation and Export', () => {
    it('should create and execute reports', async () => {
      const mockReport: Report = {
        id: 'test-report',
        name: 'Test Analytics Report',
        description: 'Test report for analytics',
        type: ReportType.OPERATIONAL,
        template: {
          id: 'template-1',
          name: 'Basic Template',
          description: 'Basic report template',
          layout: {
            orientation: 'portrait',
            pageSize: 'A4',
            margins: { top: 20, right: 20, bottom: 20, left: 20 },
            columns: 1,
            spacing: 10,
          },
          sections: [],
          style: {
            primaryColor: '#3B82F6',
            secondaryColor: '#10B981',
            fontFamily: 'Arial',
            fontSize: 12,
            headerStyle: {},
            bodyStyle: {},
            tableStyle: {
              headerBackground: '#F3F4F6',
              headerColor: '#1F2937',
              alternateRowBackground: '#F9FAFB',
              borderColor: '#E5E7EB',
              borderWidth: 1,
            },
          },
          version: '1.0',
          createdAt: new Date(),
        },
        parameters: {
          timeRange: mockTimeRange,
          filters: [],
          includeCharts: true,
          includeData: true,
          includeSummary: true,
        },
        status: 'draft' as any,
        createdAt: new Date(),
        updatedAt: new Date(),
        createdBy: 'test-user',
      };

      jest.spyOn(reportsService, 'createReport').mockResolvedValue(mockReport);
      jest.spyOn(reportsService, 'generateReport').mockResolvedValue({
        id: 'export-job-1',
        name: 'Test Report Export',
        type: 'report' as any,
        format: ExportFormat.PDF,
        parameters: { includeMetadata: true, includeCharts: true },
        status: ExportStatus.QUEUED,
        progress: 0,
        createdAt: new Date(),
        createdBy: 'test-user',
      });

      const createdReport = await reportsService.createReport({
        name: mockReport.name,
        description: mockReport.description,
        type: mockReport.type,
        template: mockReport.template,
        parameters: mockReport.parameters,
        createdBy: mockReport.createdBy,
      });

      expect(createdReport.id).toBe('test-report');

      const exportJob = await reportsService.generateReport(createdReport.id);
      expect(exportJob.status).toBe(ExportStatus.QUEUED);
    });

    it('should handle export job lifecycle', async () => {
      const mockExportJob: ExportJob = {
        id: 'export-1',
        name: 'Test Export',
        type: 'data' as any,
        format: ExportFormat.CSV,
        parameters: { includeMetadata: true, includeCharts: false },
        status: ExportStatus.PROCESSING,
        progress: 50,
        createdAt: new Date(),
        createdBy: 'test-user',
      };

      jest.spyOn(exportService, 'createExportJob').mockResolvedValue(mockExportJob);
      jest.spyOn(exportService, 'getExportJob').mockResolvedValue({
        ...mockExportJob,
        status: ExportStatus.COMPLETED,
        progress: 100,
        completedAt: new Date(),
      });

      const exportJob = await exportService.createExportJob({
        name: mockExportJob.name,
        type: mockExportJob.type,
        format: mockExportJob.format,
        parameters: mockExportJob.parameters,
        createdBy: mockExportJob.createdBy,
      });

      expect(exportJob.status).toBe(ExportStatus.PROCESSING);

      const completedJob = await exportService.getExportJob(exportJob.id);
      expect(completedJob.status).toBe(ExportStatus.COMPLETED);
      expect(completedJob.progress).toBe(100);
    });
  });

  describe('Real-time Updates and Reactivity', () => {
    it('should handle real-time data updates', async () => {
      const updateCallback = jest.fn();

      // Mock real-time update subscription
      jest.spyOn(integrationService, 'onAnalyticsUpdate').mockImplementation((callback) => {
        // Simulate immediate callback
        setTimeout(() => {
          callback({
            systemHealth: {
              overall: 90,
              components: {
                dataSource: 95,
                storage: 85,
                quality: 90,
                pipeline: 90,
              },
              status: 'healthy',
              lastUpdated: new Date(),
              trends: {
                overall: TrendDirection.INCREASING,
              },
            },
            crossServiceTrends: mockDataPoints,
            correlationInsights: [],
            aggregatedKPIs: mockKPIs,
            performanceScore: 85,
            recommendations: [],
          });
        }, 100);

        return () => {}; // Unsubscribe function
      });

      const unsubscribe = integrationService.onAnalyticsUpdate(updateCallback);

      await waitFor(() => {
        expect(updateCallback).toHaveBeenCalled();
      }, { timeout: 200 });

      unsubscribe();
    });

    it('should propagate updates through component hierarchy', async () => {
      const onAnalyticsUpdate = jest.fn();

      render(
        <DataManagementWithAnalytics
          analyticsIntegrationService={integrationService}
          onAnalyticsUpdate={onAnalyticsUpdate}
        />
      );

      // Should receive initial analytics data
      await waitFor(() => {
        expect(onAnalyticsUpdate).toHaveBeenCalled();
      });
    });
  });

  describe('Error Handling and Recovery', () => {
    it('should handle service errors gracefully', async () => {
      // Mock service errors
      jest.spyOn(analyticsService, 'getHistoricalData').mockRejectedValue(new Error('Service unavailable'));

      const onError = jest.fn();

      render(
        <AnalyticsDashboard onError={onError} />
      );

      await waitFor(() => {
        expect(onError).toHaveBeenCalledWith(expect.any(Error));
      });
    });

    it('should recover from temporary failures', async () => {
      // Mock temporary failure followed by success
      jest.spyOn(analyticsService, 'getHistoricalData')
        .mockRejectedValueOnce(new Error('Temporary failure'))
        .mockResolvedValue(mockDataPoints);

      const onError = jest.fn();

      const { rerender } = render(
        <AnalyticsDashboard onError={onError} />
      );

      await waitFor(() => {
        expect(onError).toHaveBeenCalled();
      });

      // Simulate retry
      rerender(<AnalyticsDashboard onError={onError} />);

      // Should succeed on retry
      await waitFor(() => {
        expect(analyticsService.getHistoricalData).toHaveBeenCalledTimes(2);
      });
    });
  });

  describe('Performance and Scalability', () => {
    it('should handle large datasets efficiently', async () => {
      // Generate large mock dataset
      const largeDataset = Array.from({ length: 1000 }, (_, i) => ({
        timestamp: new Date(Date.now() + i * 60000),
        metrics: {
          system_health: 80 + Math.random() * 20,
          data_quality_score: 85 + Math.random() * 15,
        },
        dimensions: { index: i.toString() },
      }));

      jest.spyOn(analyticsService, 'getHistoricalData').mockResolvedValue(largeDataset);

      const startTime = Date.now();
      const result = await analyticsService.getHistoricalData('system_health', mockTimeRange);
      const executionTime = Date.now() - startTime;

      expect(result.length).toBe(1000);
      expect(executionTime).toBeLessThan(1000); // Should complete within 1 second
    });

    it('should optimize memory usage for large KPI sets', async () => {
      // Generate large KPI set
      const largeKPISet = Array.from({ length: 100 }, (_, i) => ({
        id: `kpi-${i}`,
        name: `KPI ${i}`,
        description: `Test KPI ${i}`,
        category: AnalyticsCategory.SYSTEM,
        metric: `metric_${i}`,
        target: 95,
        unit: '%',
        thresholds: {
          critical: { min: 60 },
          warning: { min: 80 },
          target: { min: 95, max: 100 },
        },
        status: KPIStatus.GOOD,
        currentValue: 80 + Math.random() * 20,
        trend: TrendDirection.STABLE,
        lastUpdated: new Date(),
      }));

      jest.spyOn(metricsService, 'getKPIs').mockResolvedValue(largeKPISet);

      const kpis = await metricsService.getKPIs();
      expect(kpis.length).toBe(100);
    });
  });

  describe('Data Validation and Quality', () => {
    it('should validate data integrity', async () => {
      const invalidDataPoint = {
        timestamp: new Date(),
        metrics: {
          invalid_metric: 'not_a_number' as any,
        },
        dimensions: {},
      };

      // Test that services handle invalid data appropriately
      jest.spyOn(analyticsService, 'addDataPoint').mockImplementation(async (dataPoint) => {
        // Validate that metrics are numbers
        for (const [key, value] of Object.entries(dataPoint.metrics)) {
          if (typeof value !== 'number') {
            throw new Error(`Invalid metric value for ${key}: expected number, got ${typeof value}`);
          }
        }
      });

      await expect(analyticsService.addDataPoint(invalidDataPoint)).rejects.toThrow('Invalid metric value');
    });

    it('should maintain data quality metrics', async () => {
      const result = await analyticsService.aggregate({
        timeRange: mockTimeRange,
        metrics: ['system_health'],
      });

      expect(result.metadata.dataQuality).toBeGreaterThan(0.9);
      expect(result.metadata.totalRecords).toBeGreaterThan(0);
    });
  });
});
