/**
 * ReportsService
 *
 * Service for report generation, template management, and report scheduling
 */

import {
  IReportsService,
  Report,
  ReportTemplate,
  ReportSection,
  ReportType,
  ReportSectionType,
  ReportParameters,
  ReportSchedule,
  ReportStatus,
  ScheduleFrequency,
  DeliveryMethod,
  ExportJob,
  ExportFormat,
  AnalyticsQuery,
  AnalyticsCategory,
  TimeRange,
  TimeInterval,
} from '@/types/analytics';
import { AnalyticsService, getAnalyticsService } from './analytics';
import { MetricsAggregationService, getMetricsAggregationService } from './metricsAggregation';

export class ReportsService implements IReportsService {
  private baseUrl: string;
  private analyticsService: AnalyticsService;
  private metricsService: MetricsAggregationService;
  private reports: Map<string, Report> = new Map();
  private templates: Map<string, ReportTemplate> = new Map();
  private cache: Map<string, { data: any; expiry: number }> = new Map();
  private cacheTimeout = 10 * 60 * 1000; // 10 minutes

  constructor(
    baseUrl: string = '/api/reports',
    analyticsService?: AnalyticsService,
    metricsService?: MetricsAggregationService
  ) {
    this.baseUrl = baseUrl;
    this.analyticsService = analyticsService || getAnalyticsService();
    this.metricsService = metricsService || getMetricsAggregationService();
    this.initializeDefaultTemplates();
  }

  // Report management methods
  async getReports(): Promise<Report[]> {
    const cacheKey = 'reports:all';
    const cached = this.getFromCache(cacheKey);
    if (cached) return cached;

    try {
      const response = await fetch(`${this.baseUrl}/reports`);

      if (!response.ok) {
        throw new Error(`Failed to fetch reports: ${response.statusText}`);
      }

      const reports = await response.json();

      // Update local cache
      reports.forEach((report: Report) => this.reports.set(report.id, report));

      this.setCache(cacheKey, reports);
      return reports;
    } catch (error) {
      console.warn('Failed to fetch reports from backend, using local data:', error);

      // Return local reports
      const localReports = Array.from(this.reports.values());
      return localReports.length > 0 ? localReports : this.generateSampleReports();
    }
  }

  async getReport(id: string): Promise<Report> {
    const cacheKey = `report:${id}`;
    const cached = this.getFromCache(cacheKey);
    if (cached) return cached;

    // Check local cache first
    const localReport = this.reports.get(id);
    if (localReport) {
      this.setCache(cacheKey, localReport);
      return localReport;
    }

    try {
      const response = await fetch(`${this.baseUrl}/reports/${id}`);

      if (!response.ok) {
        throw new Error(`Failed to fetch report: ${response.statusText}`);
      }

      const report = await response.json();
      this.reports.set(id, report);
      this.setCache(cacheKey, report);
      return report;
    } catch (error) {
      throw new Error(`Report not found: ${id}`);
    }
  }

  async createReport(reportData: Omit<Report, 'id' | 'createdAt' | 'updatedAt' | 'status'>): Promise<Report> {
    const report: Report = {
      ...reportData,
      id: this.generateReportId(reportData.name),
      status: ReportStatus.DRAFT,
      createdAt: new Date(),
      updatedAt: new Date(),
    };

    try {
      const response = await fetch(`${this.baseUrl}/reports`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(report),
      });

      if (response.ok) {
        const savedReport = await response.json();
        this.reports.set(savedReport.id, savedReport);
        this.clearCacheByPattern('reports:');
        return savedReport;
      }
    } catch (error) {
      console.warn('Failed to save report to backend:', error);
    }

    // Save to local cache
    this.reports.set(report.id, report);
    this.clearCacheByPattern('reports:');
    return report;
  }

  async updateReport(id: string, updates: Partial<Report>): Promise<Report> {
    const existingReport = this.reports.get(id);
    if (!existingReport) {
      throw new Error(`Report not found: ${id}`);
    }

    const updatedReport: Report = {
      ...existingReport,
      ...updates,
      updatedAt: new Date(),
    };

    try {
      const response = await fetch(`${this.baseUrl}/reports/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updatedReport),
      });

      if (response.ok) {
        const savedReport = await response.json();
        this.reports.set(id, savedReport);
        this.clearCacheByPattern('reports:');
        return savedReport;
      }
    } catch (error) {
      console.warn('Failed to update report in backend:', error);
    }

    // Update local cache
    this.reports.set(id, updatedReport);
    this.clearCacheByPattern('reports:');
    return updatedReport;
  }

  async deleteReport(id: string): Promise<boolean> {
    try {
      const response = await fetch(`${this.baseUrl}/reports/${id}`, {
        method: 'DELETE',
      });

      if (response.ok) {
        this.reports.delete(id);
        this.clearCacheByPattern('reports:');
        return true;
      }
    } catch (error) {
      console.warn('Failed to delete report from backend:', error);
    }

    // Remove from local cache
    const existed = this.reports.delete(id);
    this.clearCacheByPattern('reports:');
    return existed;
  }

  // Template management methods
  async getTemplates(): Promise<ReportTemplate[]> {
    const cacheKey = 'templates:all';
    const cached = this.getFromCache(cacheKey);
    if (cached) return cached;

    try {
      const response = await fetch(`${this.baseUrl}/templates`);

      if (!response.ok) {
        throw new Error(`Failed to fetch templates: ${response.statusText}`);
      }

      const templates = await response.json();

      // Update local cache
      templates.forEach((template: ReportTemplate) => this.templates.set(template.id, template));

      this.setCache(cacheKey, templates);
      return templates;
    } catch (error) {
      console.warn('Failed to fetch templates from backend, using local data:', error);

      // Return local templates
      return Array.from(this.templates.values());
    }
  }

  async createTemplate(templateData: Omit<ReportTemplate, 'id' | 'createdAt'>): Promise<ReportTemplate> {
    const template: ReportTemplate = {
      ...templateData,
      id: this.generateTemplateId(templateData.name),
      createdAt: new Date(),
    };

    try {
      const response = await fetch(`${this.baseUrl}/templates`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(template),
      });

      if (response.ok) {
        const savedTemplate = await response.json();
        this.templates.set(savedTemplate.id, savedTemplate);
        this.clearCacheByPattern('templates:');
        return savedTemplate;
      }
    } catch (error) {
      console.warn('Failed to save template to backend:', error);
    }

    // Save to local cache
    this.templates.set(template.id, template);
    this.clearCacheByPattern('templates:');
    return template;
  }

  // Report generation methods
  async generateReport(reportId: string, parameters?: Partial<ReportParameters>): Promise<ExportJob> {
    const report = await this.getReport(reportId);

    // Merge parameters with report defaults
    const finalParameters: ReportParameters = {
      ...report.parameters,
      ...parameters,
    };

    // Create export job
    const exportJob: ExportJob = {
      id: this.generateJobId(),
      name: `${report.name} - ${new Date().toLocaleString()}`,
      type: 'report' as any,
      format: ExportFormat.PDF,
      report: reportId,
      parameters: {
        includeMetadata: true,
        includeCharts: finalParameters.includeCharts,
        customParameters: finalParameters.customParameters,
      },
      status: 'queued' as any,
      progress: 0,
      createdAt: new Date(),
      createdBy: 'current-user', // This should come from auth context
    };

    try {
      // Start report generation process
      await this.processReportGeneration(report, finalParameters, exportJob);

      // Submit to backend
      const response = await fetch(`${this.baseUrl}/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          reportId,
          parameters: finalParameters,
          jobId: exportJob.id,
        }),
      });

      if (response.ok) {
        const updatedJob = await response.json();
        return updatedJob;
      }
    } catch (error) {
      console.warn('Failed to generate report in backend:', error);
      exportJob.status = 'failed' as any;
      exportJob.error = error instanceof Error ? error.message : 'Unknown error';
    }

    return exportJob;
  }

  async previewReport(reportId: string, parameters?: Partial<ReportParameters>): Promise<any> {
    const report = await this.getReport(reportId);
    const finalParameters: ReportParameters = {
      ...report.parameters,
      ...parameters,
    };

    // Generate preview data for each section
    const previewData = await this.generatePreviewData(report, finalParameters);

    return {
      report,
      parameters: finalParameters,
      sections: previewData,
      generatedAt: new Date(),
    };
  }

  // Scheduling methods
  async scheduleReport(reportId: string, schedule: ReportSchedule): Promise<Report> {
    const report = await this.getReport(reportId);

    const updatedReport = await this.updateReport(reportId, {
      schedule,
      status: schedule.enabled ? ReportStatus.ACTIVE : ReportStatus.PAUSED,
      nextExecution: this.calculateNextExecution(schedule),
    });

    // Register schedule with backend
    try {
      await fetch(`${this.baseUrl}/reports/${reportId}/schedule`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(schedule),
      });
    } catch (error) {
      console.warn('Failed to register schedule with backend:', error);
    }

    return updatedReport;
  }

  async pauseSchedule(reportId: string): Promise<Report> {
    const report = await this.getReport(reportId);

    if (!report.schedule) {
      throw new Error('Report has no schedule to pause');
    }

    const updatedSchedule: ReportSchedule = {
      ...report.schedule,
      enabled: false,
    };

    return this.updateReport(reportId, {
      schedule: updatedSchedule,
      status: ReportStatus.PAUSED,
      nextExecution: undefined,
    });
  }

  async resumeSchedule(reportId: string): Promise<Report> {
    const report = await this.getReport(reportId);

    if (!report.schedule) {
      throw new Error('Report has no schedule to resume');
    }

    const updatedSchedule: ReportSchedule = {
      ...report.schedule,
      enabled: true,
    };

    return this.updateReport(reportId, {
      schedule: updatedSchedule,
      status: ReportStatus.ACTIVE,
      nextExecution: this.calculateNextExecution(updatedSchedule),
    });
  }

  // Advanced report analysis methods
  async getReportAnalytics(reportId: string, timeRange: TimeRange): Promise<{
    executionCount: number;
    averageGenerationTime: number;
    successRate: number;
    popularSections: Array<{ sectionId: string; accessCount: number }>;
    deliverySuccess: Record<DeliveryMethod, number>;
  }> {
    // This would integrate with analytics service to track report usage
    return {
      executionCount: Math.floor(Math.random() * 100) + 10,
      averageGenerationTime: Math.random() * 30 + 5, // 5-35 seconds
      successRate: Math.random() * 0.15 + 0.85, // 85-100%
      popularSections: [
        { sectionId: 'summary', accessCount: Math.floor(Math.random() * 50) + 20 },
        { sectionId: 'kpi_scorecard', accessCount: Math.floor(Math.random() * 40) + 15 },
        { sectionId: 'trend_analysis', accessCount: Math.floor(Math.random() * 30) + 10 },
      ],
      deliverySuccess: {
        [DeliveryMethod.EMAIL]: Math.random() * 0.1 + 0.9,
        [DeliveryMethod.WEBHOOK]: Math.random() * 0.05 + 0.95,
        [DeliveryMethod.SLACK]: Math.random() * 0.08 + 0.92,
        [DeliveryMethod.TEAMS]: Math.random() * 0.12 + 0.88,
        [DeliveryMethod.SFTP]: Math.random() * 0.15 + 0.85,
        [DeliveryMethod.S3]: Math.random() * 0.03 + 0.97,
      },
    };
  }

  async validateReportConfiguration(report: Omit<Report, 'id' | 'createdAt' | 'updatedAt'>): Promise<{
    valid: boolean;
    errors: string[];
    warnings: string[];
  }> {
    const errors: string[] = [];
    const warnings: string[] = [];

    // Validate basic report structure
    if (!report.name || report.name.trim().length === 0) {
      errors.push('Report name is required');
    }

    if (!report.template || !report.template.sections || report.template.sections.length === 0) {
      errors.push('Report must have at least one section');
    }

    // Validate sections
    if (report.template.sections) {
      report.template.sections.forEach((section, index) => {
        if (section.type === ReportSectionType.CHART && !section.config.chartType) {
          errors.push(`Chart section ${index + 1} missing chart type`);
        }

        if (section.type === ReportSectionType.KPI_SCORECARD && (!section.config.kpis || section.config.kpis.length === 0)) {
          warnings.push(`KPI section ${index + 1} has no KPIs defined`);
        }

        if (section.config.query) {
          if (!section.config.query.metrics || section.config.query.metrics.length === 0) {
            errors.push(`Section ${index + 1} query has no metrics`);
          }
        }
      });
    }

    // Validate schedule if present
    if (report.schedule) {
      if (report.schedule.enabled && (!report.schedule.recipients || report.schedule.recipients.length === 0)) {
        warnings.push('Scheduled report has no recipients');
      }

      if (report.schedule.endDate && report.schedule.endDate < report.schedule.startDate) {
        errors.push('Schedule end date cannot be before start date');
      }
    }

    return {
      valid: errors.length === 0,
      errors,
      warnings,
    };
  }

  // Private helper methods
  private async processReportGeneration(
    report: Report,
    parameters: ReportParameters,
    exportJob: ExportJob
  ): Promise<void> {
    exportJob.status = 'processing' as any;
    exportJob.startedAt = new Date();
    exportJob.progress = 10;

    try {
      // Process each section
      for (let i = 0; i < report.template.sections.length; i++) {
        const section = report.template.sections[i];
        await this.processSectionData(section, parameters);
        exportJob.progress = 10 + ((i + 1) / report.template.sections.length) * 80;
      }

      exportJob.status = 'completed' as any;
      exportJob.progress = 100;
      exportJob.completedAt = new Date();
      exportJob.downloadUrl = `/api/exports/${exportJob.id}/download`;
      exportJob.fileSize = Math.floor(Math.random() * 1000000) + 100000; // Simulated file size
    } catch (error) {
      exportJob.status = 'failed' as any;
      exportJob.error = error instanceof Error ? error.message : 'Processing failed';
    }
  }

  private async processSectionData(section: ReportSection, parameters: ReportParameters): Promise<any> {
    switch (section.type) {
      case ReportSectionType.SUMMARY:
        return this.generateSummaryData(parameters);

      case ReportSectionType.KPI_SCORECARD:
        return this.generateKPIData(section.config.kpis || [], parameters);

      case ReportSectionType.TREND_ANALYSIS:
        return this.generateTrendData(section.config.query, parameters);

      case ReportSectionType.DATA_TABLE:
        return this.generateTableData(section.config.query, parameters);

      case ReportSectionType.CHART:
        return this.generateChartData(section.config, parameters);

      default:
        return null;
    }
  }

  private async generatePreviewData(report: Report, parameters: ReportParameters): Promise<any[]> {
    const sectionData = [];

    for (const section of report.template.sections) {
      const data = await this.processSectionData(section, parameters);
      sectionData.push({
        section,
        data,
        timestamp: new Date(),
      });
    }

    return sectionData;
  }

  private async generateSummaryData(parameters: ReportParameters): Promise<any> {
    const performanceSummary = await this.metricsService.getPerformanceSummary();

    return {
      timeRange: parameters.timeRange,
      kpiSummary: performanceSummary.summary,
      topMetrics: performanceSummary.kpis.slice(0, 5),
      alerts: await this.metricsService.evaluateKPIThresholds(),
    };
  }

  private async generateKPIData(kpiIds: string[], parameters: ReportParameters): Promise<any> {
    const allKPIs = await this.metricsService.getKPIs();
    const selectedKPIs = kpiIds.length > 0
      ? allKPIs.filter(kpi => kpiIds.includes(kpi.id))
      : allKPIs.slice(0, 10); // Default to top 10

    return {
      kpis: selectedKPIs,
      timestamp: new Date(),
      timeRange: parameters.timeRange,
    };
  }

  private async generateTrendData(query: AnalyticsQuery | undefined, parameters: ReportParameters): Promise<any> {
    if (!query || !query.metrics || query.metrics.length === 0) {
      return { error: 'No metrics specified for trend analysis' };
    }

    const trendPromises = query.metrics.map(metric =>
      this.analyticsService.analyzeTrend(metric, parameters.timeRange)
    );

    const trends = await Promise.all(trendPromises);

    return {
      trends,
      timeRange: parameters.timeRange,
      timestamp: new Date(),
    };
  }

  private async generateTableData(query: AnalyticsQuery | undefined, parameters: ReportParameters): Promise<any> {
    if (!query) {
      return { error: 'No query specified for data table' };
    }

    const finalQuery: AnalyticsQuery = {
      ...query,
      timeRange: parameters.timeRange,
    };

    const result = await this.analyticsService.aggregate(finalQuery);

    return {
      query: finalQuery,
      data: result.data,
      metadata: result.metadata,
      timestamp: new Date(),
    };
  }

  private async generateChartData(config: any, parameters: ReportParameters): Promise<any> {
    if (!config.query) {
      return { error: 'No query specified for chart' };
    }

    const chartQuery: AnalyticsQuery = {
      ...config.query,
      timeRange: parameters.timeRange,
    };

    const result = await this.analyticsService.aggregate(chartQuery);

    return {
      chartType: config.chartType,
      chartConfig: config.chartConfig,
      data: result.data,
      metadata: result.metadata,
      timestamp: new Date(),
    };
  }

  private calculateNextExecution(schedule: ReportSchedule): Date {
    const now = new Date();
    const startDate = new Date(schedule.startDate);

    if (startDate > now) {
      return startDate;
    }

    const next = new Date(now);

    switch (schedule.frequency) {
      case ScheduleFrequency.HOURLY:
        next.setHours(next.getHours() + schedule.interval);
        break;
      case ScheduleFrequency.DAILY:
        next.setDate(next.getDate() + schedule.interval);
        break;
      case ScheduleFrequency.WEEKLY:
        next.setDate(next.getDate() + (schedule.interval * 7));
        break;
      case ScheduleFrequency.MONTHLY:
        next.setMonth(next.getMonth() + schedule.interval);
        break;
      case ScheduleFrequency.QUARTERLY:
        next.setMonth(next.getMonth() + (schedule.interval * 3));
        break;
      case ScheduleFrequency.YEARLY:
        next.setFullYear(next.getFullYear() + schedule.interval);
        break;
    }

    return next;
  }

  private initializeDefaultTemplates(): void {
    const defaultTemplates: Array<Omit<ReportTemplate, 'id' | 'createdAt'>> = [
      {
        name: 'Executive Summary',
        description: 'High-level overview for executives',
        layout: {
          orientation: 'portrait',
          pageSize: 'A4',
          margins: { top: 20, right: 20, bottom: 20, left: 20 },
          columns: 1,
          spacing: 10,
        },
        sections: [
          {
            id: 'summary',
            type: ReportSectionType.SUMMARY,
            title: 'Executive Summary',
            order: 1,
            config: {},
            visible: true,
          },
          {
            id: 'kpi-scorecard',
            type: ReportSectionType.KPI_SCORECARD,
            title: 'Key Performance Indicators',
            order: 2,
            config: { kpis: [] },
            visible: true,
          },
          {
            id: 'trend-overview',
            type: ReportSectionType.TREND_ANALYSIS,
            title: 'Performance Trends',
            order: 3,
            config: {
              query: {
                timeRange: {
                  start: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000),
                  end: new Date(),
                  interval: TimeInterval.DAY,
                },
                metrics: ['system_performance', 'data_quality', 'pipeline_success'],
                aggregation: 'avg' as any,
              },
            },
            visible: true,
          },
        ],
        style: {
          primaryColor: '#3B82F6',
          secondaryColor: '#1F2937',
          fontFamily: 'Inter, sans-serif',
          fontSize: 12,
          headerStyle: {
            fontSize: 18,
            fontWeight: 'bold',
            color: '#1F2937',
            alignment: 'left',
          },
          bodyStyle: {
            fontSize: 12,
            color: '#374151',
            alignment: 'left',
          },
          tableStyle: {
            headerBackground: '#F3F4F6',
            headerColor: '#1F2937',
            alternateRowBackground: '#F9FAFB',
            borderColor: '#E5E7EB',
            borderWidth: 1,
          },
        },
        version: '1.0',
      },
      {
        name: 'Technical Performance Report',
        description: 'Detailed technical metrics and analysis',
        layout: {
          orientation: 'landscape',
          pageSize: 'A4',
          margins: { top: 15, right: 15, bottom: 15, left: 15 },
          columns: 2,
          spacing: 15,
        },
        sections: [
          {
            id: 'system-metrics',
            type: ReportSectionType.DATA_TABLE,
            title: 'System Metrics',
            order: 1,
            config: {
              query: {
                timeRange: {
                  start: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000),
                  end: new Date(),
                  interval: TimeInterval.HOUR,
                },
                metrics: ['cpu_usage', 'memory_usage', 'disk_usage', 'network_io'],
                aggregation: 'avg' as any,
              },
            },
            visible: true,
          },
          {
            id: 'performance-charts',
            type: ReportSectionType.CHART,
            title: 'Performance Trends',
            order: 2,
            config: {
              chartType: 'line',
              chartConfig: {
                title: 'System Performance Over Time',
                responsive: true,
                animations: true,
              },
              query: {
                timeRange: {
                  start: new Date(Date.now() - 24 * 60 * 60 * 1000),
                  end: new Date(),
                  interval: TimeInterval.HOUR,
                },
                metrics: ['response_time', 'throughput', 'error_rate'],
                aggregation: 'avg' as any,
              },
            },
            visible: true,
          },
          {
            id: 'alerts-summary',
            type: ReportSectionType.SUMMARY,
            title: 'Alerts and Issues',
            order: 3,
            config: {},
            visible: true,
          },
        ],
        style: {
          primaryColor: '#059669',
          secondaryColor: '#1F2937',
          fontFamily: 'Inter, sans-serif',
          fontSize: 11,
          headerStyle: {
            fontSize: 16,
            fontWeight: 'bold',
            color: '#1F2937',
            alignment: 'left',
          },
          bodyStyle: {
            fontSize: 11,
            color: '#374151',
            alignment: 'left',
          },
          tableStyle: {
            headerBackground: '#ECFDF5',
            headerColor: '#1F2937',
            alternateRowBackground: '#F0FDF4',
            borderColor: '#D1FAE5',
            borderWidth: 1,
          },
        },
        version: '1.0',
      },
    ];

    defaultTemplates.forEach(templateData => {
      const template: ReportTemplate = {
        ...templateData,
        id: this.generateTemplateId(templateData.name),
        createdAt: new Date(),
      };
      this.templates.set(template.id, template);
    });
  }

  private generateSampleReports(): Report[] {
    const templates = Array.from(this.templates.values());

    return [
      {
        id: 'report-daily-summary',
        name: 'Daily System Summary',
        description: 'Daily overview of system performance',
        type: ReportType.OPERATIONAL,
        template: templates[0],
        parameters: {
          timeRange: {
            start: new Date(Date.now() - 24 * 60 * 60 * 1000),
            end: new Date(),
            interval: TimeInterval.HOUR,
          },
          filters: [],
          includeCharts: true,
          includeData: true,
          includeSummary: true,
        },
        schedule: {
          enabled: true,
          frequency: ScheduleFrequency.DAILY,
          interval: 1,
          timezone: 'UTC',
          startDate: new Date(),
          recipients: [
            { type: 'email', address: 'admin@example.com', name: 'System Admin' },
          ],
          deliveryMethod: [DeliveryMethod.EMAIL],
        },
        status: ReportStatus.ACTIVE,
        createdAt: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000),
        updatedAt: new Date(),
        createdBy: 'system',
        lastExecuted: new Date(Date.now() - 60 * 60 * 1000),
        nextExecution: new Date(Date.now() + 23 * 60 * 60 * 1000),
      },
      {
        id: 'report-weekly-performance',
        name: 'Weekly Performance Report',
        description: 'Comprehensive weekly performance analysis',
        type: ReportType.TECHNICAL,
        template: templates[1],
        parameters: {
          timeRange: {
            start: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000),
            end: new Date(),
            interval: TimeInterval.DAY,
          },
          filters: [],
          includeCharts: true,
          includeData: true,
          includeSummary: true,
        },
        status: ReportStatus.DRAFT,
        createdAt: new Date(Date.now() - 3 * 24 * 60 * 60 * 1000),
        updatedAt: new Date(),
        createdBy: 'user',
      },
    ];
  }

  private generateReportId(name: string): string {
    return `report_${name.toLowerCase().replace(/\s+/g, '_')}_${Date.now()}`;
  }

  private generateTemplateId(name: string): string {
    return `template_${name.toLowerCase().replace(/\s+/g, '_')}_${Date.now()}`;
  }

  private generateJobId(): string {
    return `job_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  private getFromCache(key: string): any {
    const cached = this.cache.get(key);
    if (cached && cached.expiry > Date.now()) {
      return cached.data;
    }
    this.cache.delete(key);
    return null;
  }

  private setCache(key: string, data: any): void {
    this.cache.set(key, {
      data,
      expiry: Date.now() + this.cacheTimeout,
    });
  }

  private clearCacheByPattern(pattern: string): void {
    for (const key of this.cache.keys()) {
      if (key.includes(pattern)) {
        this.cache.delete(key);
      }
    }
  }
}

// Singleton instance
let globalReportsService: ReportsService | null = null;

export const getReportsService = (
  baseUrl?: string,
  analyticsService?: AnalyticsService,
  metricsService?: MetricsAggregationService
): ReportsService => {
  if (!globalReportsService) {
    globalReportsService = new ReportsService(baseUrl, analyticsService, metricsService);
  }
  return globalReportsService;
};
