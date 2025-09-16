/**
 * ExportService
 *
 * Service for multi-format data and report exports
 */

import {
  IExportService,
  ExportJob,
  ExportType,
  ExportFormat,
  ExportStatus,
  ExportParameters,
  AnalyticsQuery,
  AnalyticsDataPoint,
  Report,
  ChartConfig,
  ReportTemplate,
} from '@/types/analytics';
import { AnalyticsService, getAnalyticsService } from './analytics';
import { ReportsService, getReportsService } from './reports';

export class ExportService implements IExportService {
  private baseUrl: string;
  private analyticsService: AnalyticsService;
  private reportsService: ReportsService;
  private exportJobs: Map<string, ExportJob> = new Map();
  private processingQueue: string[] = [];
  private maxConcurrentExports = 3;
  private currentlyProcessing = 0;

  constructor(
    baseUrl: string = '/api/exports',
    analyticsService?: AnalyticsService,
    reportsService?: ReportsService
  ) {
    this.baseUrl = baseUrl;
    this.analyticsService = analyticsService || getAnalyticsService();
    this.reportsService = reportsService || getReportsService();
    this.startProcessingQueue();
  }

  // Export job management methods
  async getExportJobs(): Promise<ExportJob[]> {
    try {
      const response = await fetch(`${this.baseUrl}/jobs`);

      if (!response.ok) {
        throw new Error(`Failed to fetch export jobs: ${response.statusText}`);
      }

      const jobs = await response.json();

      // Update local cache
      jobs.forEach((job: ExportJob) => this.exportJobs.set(job.id, job));

      return jobs;
    } catch (error) {
      console.warn('Failed to fetch export jobs from backend, using local data:', error);

      // Return local jobs
      return Array.from(this.exportJobs.values()).sort(
        (a, b) => b.createdAt.getTime() - a.createdAt.getTime()
      );
    }
  }

  async getExportJob(id: string): Promise<ExportJob> {
    // Check local cache first
    const localJob = this.exportJobs.get(id);
    if (localJob) {
      return localJob;
    }

    try {
      const response = await fetch(`${this.baseUrl}/jobs/${id}`);

      if (!response.ok) {
        throw new Error(`Failed to fetch export job: ${response.statusText}`);
      }

      const job = await response.json();
      this.exportJobs.set(id, job);
      return job;
    } catch (error) {
      throw new Error(`Export job not found: ${id}`);
    }
  }

  async createExportJob(jobData: Omit<ExportJob, 'id' | 'createdAt' | 'status' | 'progress'>): Promise<ExportJob> {
    const job: ExportJob = {
      ...jobData,
      id: this.generateJobId(),
      status: ExportStatus.QUEUED,
      progress: 0,
      createdAt: new Date(),
    };

    try {
      const response = await fetch(`${this.baseUrl}/jobs`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(job),
      });

      if (response.ok) {
        const savedJob = await response.json();
        this.exportJobs.set(savedJob.id, savedJob);
        this.queueJob(savedJob.id);
        return savedJob;
      }
    } catch (error) {
      console.warn('Failed to save export job to backend:', error);
    }

    // Save to local cache and queue for processing
    this.exportJobs.set(job.id, job);
    this.queueJob(job.id);
    return job;
  }

  async cancelExportJob(id: string): Promise<boolean> {
    const job = this.exportJobs.get(id);
    if (!job) {
      return false;
    }

    if (job.status === ExportStatus.PROCESSING) {
      // Mark for cancellation (actual cancellation logic would be more complex in production)
      job.status = ExportStatus.CANCELLED;
      this.exportJobs.set(id, job);
    } else if (job.status === ExportStatus.QUEUED) {
      // Remove from queue
      const queueIndex = this.processingQueue.indexOf(id);
      if (queueIndex > -1) {
        this.processingQueue.splice(queueIndex, 1);
      }
      job.status = ExportStatus.CANCELLED;
      this.exportJobs.set(id, job);
    }

    try {
      await fetch(`${this.baseUrl}/jobs/${id}/cancel`, {
        method: 'POST',
      });
    } catch (error) {
      console.warn('Failed to cancel job on backend:', error);
    }

    return true;
  }

  // Data export methods
  async exportData(
    query: AnalyticsQuery,
    format: ExportFormat,
    parameters: ExportParameters = { includeMetadata: true, includeCharts: false }
  ): Promise<ExportJob> {
    const job = await this.createExportJob({
      name: `Data Export - ${query.name || 'Query'} - ${new Date().toLocaleString()}`,
      type: ExportType.DATA,
      format,
      query,
      parameters,
      createdBy: 'current-user', // This should come from auth context
    });

    return job;
  }

  async exportReport(
    reportId: string,
    format: ExportFormat,
    parameters: ExportParameters = { includeMetadata: true, includeCharts: true }
  ): Promise<ExportJob> {
    const job = await this.createExportJob({
      name: `Report Export - ${reportId} - ${new Date().toLocaleString()}`,
      type: ExportType.REPORT,
      format,
      report: reportId,
      parameters,
      createdBy: 'current-user',
    });

    return job;
  }

  async exportChart(
    chartConfig: any,
    format: ExportFormat,
    parameters: ExportParameters = { includeMetadata: false, includeCharts: true, chartResolution: 300 }
  ): Promise<ExportJob> {
    const job = await this.createExportJob({
      name: `Chart Export - ${chartConfig.title || 'Chart'} - ${new Date().toLocaleString()}`,
      type: ExportType.CHART,
      format,
      parameters: {
        ...parameters,
        customParameters: { chartConfig },
      },
      createdBy: 'current-user',
    });

    return job;
  }

  // File management methods
  async downloadExport(jobId: string): Promise<Blob> {
    const job = this.exportJobs.get(jobId);
    if (!job || job.status !== ExportStatus.COMPLETED || !job.downloadUrl) {
      throw new Error('Export not available for download');
    }

    try {
      const response = await fetch(job.downloadUrl);

      if (!response.ok) {
        throw new Error(`Download failed: ${response.statusText}`);
      }

      return await response.blob();
    } catch (error) {
      // For development, simulate file download
      return this.simulateFileDownload(job);
    }
  }

  async getExportUrl(jobId: string): Promise<string> {
    const job = this.exportJobs.get(jobId);
    if (!job || job.status !== ExportStatus.COMPLETED) {
      throw new Error('Export not completed or not found');
    }

    if (job.downloadUrl) {
      return job.downloadUrl;
    }

    // Generate temporary download URL
    const temporaryUrl = `${this.baseUrl}/download/${jobId}?token=${this.generateDownloadToken()}`;

    // Update job with download URL
    job.downloadUrl = temporaryUrl;
    this.exportJobs.set(jobId, job);

    return temporaryUrl;
  }

  async deleteExport(jobId: string): Promise<boolean> {
    try {
      const response = await fetch(`${this.baseUrl}/jobs/${jobId}`, {
        method: 'DELETE',
      });

      if (response.ok) {
        this.exportJobs.delete(jobId);
        return true;
      }
    } catch (error) {
      console.warn('Failed to delete export from backend:', error);
    }

    // Remove from local cache
    return this.exportJobs.delete(jobId);
  }

  // Bulk export operations
  async exportMultipleReports(
    reportIds: string[],
    format: ExportFormat,
    parameters?: ExportParameters
  ): Promise<ExportJob[]> {
    const jobs = await Promise.all(
      reportIds.map(reportId => this.exportReport(reportId, format, parameters))
    );

    return jobs;
  }

  async exportDashboard(
    dashboardConfig: any,
    format: ExportFormat,
    parameters?: ExportParameters
  ): Promise<ExportJob> {
    const job = await this.createExportJob({
      name: `Dashboard Export - ${dashboardConfig.name || 'Dashboard'} - ${new Date().toLocaleString()}`,
      type: ExportType.DASHBOARD,
      format,
      parameters: {
        includeMetadata: true,
        includeCharts: true,
        ...parameters,
        customParameters: { dashboardConfig },
      },
      createdBy: 'current-user',
    });

    return job;
  }

  // Batch processing and optimization
  async createBatchExport(exports: Array<{
    type: ExportType;
    id: string;
    format: ExportFormat;
    parameters?: ExportParameters;
  }>): Promise<ExportJob> {
    const batchJob = await this.createExportJob({
      name: `Batch Export - ${exports.length} items - ${new Date().toLocaleString()}`,
      type: ExportType.DATA, // Batch exports are treated as data exports
      format: ExportFormat.JSON, // Batch results are typically JSON
      parameters: {
        includeMetadata: true,
        includeCharts: false,
        customParameters: { batchExports: exports },
      },
      createdBy: 'current-user',
    });

    return batchJob;
  }

  async getExportStatistics(timeRange?: { start: Date; end: Date }): Promise<{
    totalExports: number;
    completedExports: number;
    failedExports: number;
    averageProcessingTime: number;
    formatBreakdown: Record<ExportFormat, number>;
    typeBreakdown: Record<ExportType, number>;
    sizeBreakdown: { totalSize: number; averageSize: number };
  }> {
    const allJobs = Array.from(this.exportJobs.values());

    const filteredJobs = timeRange
      ? allJobs.filter(job => job.createdAt >= timeRange.start && job.createdAt <= timeRange.end)
      : allJobs;

    const completed = filteredJobs.filter(job => job.status === ExportStatus.COMPLETED);
    const failed = filteredJobs.filter(job => job.status === ExportStatus.FAILED);

    const processingTimes = completed
      .filter(job => job.startedAt && job.completedAt)
      .map(job => job.completedAt!.getTime() - job.startedAt!.getTime());

    const averageProcessingTime = processingTimes.length > 0
      ? processingTimes.reduce((sum, time) => sum + time, 0) / processingTimes.length
      : 0;

    const formatBreakdown: Record<ExportFormat, number> = Object.values(ExportFormat).reduce(
      (acc, format) => ({ ...acc, [format]: 0 }),
      {} as Record<ExportFormat, number>
    );

    const typeBreakdown: Record<ExportType, number> = Object.values(ExportType).reduce(
      (acc, type) => ({ ...acc, [type]: 0 }),
      {} as Record<ExportType, number>
    );

    filteredJobs.forEach(job => {
      formatBreakdown[job.format]++;
      typeBreakdown[job.type]++;
    });

    const totalSize = completed.reduce((sum, job) => sum + (job.fileSize || 0), 0);
    const averageSize = completed.length > 0 ? totalSize / completed.length : 0;

    return {
      totalExports: filteredJobs.length,
      completedExports: completed.length,
      failedExports: failed.length,
      averageProcessingTime,
      formatBreakdown,
      typeBreakdown,
      sizeBreakdown: { totalSize, averageSize },
    };
  }

  // Private processing methods
  private queueJob(jobId: string): void {
    this.processingQueue.push(jobId);
    this.processNextJob();
  }

  private async processNextJob(): Promise<void> {
    if (this.currentlyProcessing >= this.maxConcurrentExports || this.processingQueue.length === 0) {
      return;
    }

    const jobId = this.processingQueue.shift();
    if (!jobId) return;

    this.currentlyProcessing++;

    try {
      await this.processExportJob(jobId);
    } catch (error) {
      console.error(`Failed to process export job ${jobId}:`, error);
    } finally {
      this.currentlyProcessing--;
      // Process next job in queue
      setTimeout(() => this.processNextJob(), 100);
    }
  }

  private async processExportJob(jobId: string): Promise<void> {
    const job = this.exportJobs.get(jobId);
    if (!job || job.status !== ExportStatus.QUEUED) {
      return;
    }

    // Update job status
    job.status = ExportStatus.PROCESSING;
    job.startedAt = new Date();
    job.progress = 10;
    this.exportJobs.set(jobId, job);

    try {
      switch (job.type) {
        case ExportType.DATA:
          await this.processDataExport(job);
          break;
        case ExportType.REPORT:
          await this.processReportExport(job);
          break;
        case ExportType.CHART:
          await this.processChartExport(job);
          break;
        case ExportType.DASHBOARD:
          await this.processDashboardExport(job);
          break;
      }

      // Mark as completed
      job.status = ExportStatus.COMPLETED;
      job.progress = 100;
      job.completedAt = new Date();
      job.downloadUrl = this.generateDownloadUrl(jobId);
      job.fileSize = this.estimateFileSize(job);
    } catch (error) {
      job.status = ExportStatus.FAILED;
      job.error = error instanceof Error ? error.message : 'Unknown error occurred';
    }

    this.exportJobs.set(jobId, job);
  }

  private async processDataExport(job: ExportJob): Promise<void> {
    if (!job.query) {
      throw new Error('No query specified for data export');
    }

    job.progress = 20;
    this.exportJobs.set(job.id, job);

    // Get data from analytics service
    const result = await this.analyticsService.aggregate(job.query);

    job.progress = 60;
    this.exportJobs.set(job.id, job);

    // Convert data to requested format
    const exportData = await this.convertDataToFormat(result.data, job.format, job.parameters);

    job.progress = 90;
    this.exportJobs.set(job.id, job);

    // In a real implementation, this would save the file to storage
    await this.simulateFileSave(job.id, exportData);
  }

  private async processReportExport(job: ExportJob): Promise<void> {
    if (!job.report) {
      throw new Error('No report specified for export');
    }

    job.progress = 20;
    this.exportJobs.set(job.id, job);

    // Generate report
    const reportJob = await this.reportsService.generateReport(job.report);

    job.progress = 70;
    this.exportJobs.set(job.id, job);

    // Convert to requested format if needed
    if (job.format !== ExportFormat.PDF) {
      // Additional format conversion would happen here
    }

    job.progress = 90;
    this.exportJobs.set(job.id, job);

    // Save file
    await this.simulateFileSave(job.id, `report-${job.report}`);
  }

  private async processChartExport(job: ExportJob): Promise<void> {
    const chartConfig = job.parameters.customParameters?.chartConfig;
    if (!chartConfig) {
      throw new Error('No chart configuration specified');
    }

    job.progress = 30;
    this.exportJobs.set(job.id, job);

    // Generate chart data
    const chartData = await this.generateChartData(chartConfig);

    job.progress = 70;
    this.exportJobs.set(job.id, job);

    // Render chart to requested format
    const renderedChart = await this.renderChart(chartData, job.format, job.parameters);

    job.progress = 90;
    this.exportJobs.set(job.id, job);

    // Save file
    await this.simulateFileSave(job.id, renderedChart);
  }

  private async processDashboardExport(job: ExportJob): Promise<void> {
    const dashboardConfig = job.parameters.customParameters?.dashboardConfig;
    if (!dashboardConfig) {
      throw new Error('No dashboard configuration specified');
    }

    job.progress = 25;
    this.exportJobs.set(job.id, job);

    // Export all dashboard components
    const components = await this.exportDashboardComponents(dashboardConfig);

    job.progress = 75;
    this.exportJobs.set(job.id, job);

    // Combine into single export
    const combinedExport = await this.combineDashboardExports(components, job.format);

    job.progress = 90;
    this.exportJobs.set(job.id, job);

    // Save file
    await this.simulateFileSave(job.id, combinedExport);
  }

  // Format conversion methods
  private async convertDataToFormat(
    data: AnalyticsDataPoint[],
    format: ExportFormat,
    parameters: ExportParameters
  ): Promise<any> {
    switch (format) {
      case ExportFormat.JSON:
        return this.convertToJSON(data, parameters);
      case ExportFormat.CSV:
        return this.convertToCSV(data, parameters);
      case ExportFormat.EXCEL:
        return this.convertToExcel(data, parameters);
      default:
        throw new Error(`Unsupported data export format: ${format}`);
    }
  }

  private convertToJSON(data: AnalyticsDataPoint[], parameters: ExportParameters): string {
    const exportData = {
      data,
      metadata: parameters.includeMetadata ? {
        exportedAt: new Date(),
        recordCount: data.length,
        format: 'JSON',
      } : undefined,
    };

    return JSON.stringify(exportData, null, 2);
  }

  private convertToCSV(data: AnalyticsDataPoint[], parameters: ExportParameters): string {
    if (data.length === 0) return '';

    // Get all metric keys
    const metricKeys = new Set<string>();
    const dimensionKeys = new Set<string>();

    data.forEach(point => {
      Object.keys(point.metrics).forEach(key => metricKeys.add(key));
      Object.keys(point.dimensions).forEach(key => dimensionKeys.add(key));
    });

    // Build headers
    const headers = ['timestamp', ...Array.from(metricKeys), ...Array.from(dimensionKeys)];

    // Build rows
    const rows = data.map(point => {
      const row = [point.timestamp.toISOString()];

      metricKeys.forEach(key => {
        row.push(point.metrics[key]?.toString() || '');
      });

      dimensionKeys.forEach(key => {
        row.push(point.dimensions[key] || '');
      });

      return row.join(',');
    });

    return [headers.join(','), ...rows].join('\n');
  }

  private async convertToExcel(data: AnalyticsDataPoint[], parameters: ExportParameters): Promise<any> {
    // In a real implementation, this would use a library like xlsx or exceljs
    // For now, return a simulated Excel format
    return {
      format: 'Excel',
      data: this.convertToCSV(data, parameters),
      sheets: ['Data'],
    };
  }

  // Helper methods
  private async generateChartData(chartConfig: ChartConfig): Promise<any> {
    // Simulate chart data generation
    return {
      config: chartConfig,
      data: Array.from({ length: 10 }, (_, i) => ({
        x: i,
        y: Math.random() * 100,
      })),
    };
  }

  private async renderChart(chartData: any, format: ExportFormat, parameters: ExportParameters): Promise<any> {
    // In a real implementation, this would render the chart using a library like Chart.js or D3
    return {
      format,
      resolution: parameters.chartResolution || 300,
      data: chartData,
    };
  }

  private async exportDashboardComponents(dashboardConfig: any): Promise<any[]> {
    // Simulate exporting dashboard components
    return dashboardConfig.components || [];
  }

  private async combineDashboardExports(components: any[], format: ExportFormat): Promise<any> {
    return {
      format,
      components,
      combinedAt: new Date(),
    };
  }

  private async simulateFileSave(jobId: string, data: any): Promise<void> {
    // Simulate file save operation
    await new Promise(resolve => setTimeout(resolve, 500));
  }

  private simulateFileDownload(job: ExportJob): Blob {
    const content = `Simulated export data for job: ${job.id}\nFormat: ${job.format}\nType: ${job.type}`;
    return new Blob([content], { type: this.getMimeType(job.format) });
  }

  private getMimeType(format: ExportFormat): string {
    const mimeTypes: Record<ExportFormat, string> = {
      [ExportFormat.PDF]: 'application/pdf',
      [ExportFormat.EXCEL]: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      [ExportFormat.CSV]: 'text/csv',
      [ExportFormat.JSON]: 'application/json',
      [ExportFormat.PNG]: 'image/png',
      [ExportFormat.SVG]: 'image/svg+xml',
    };

    return mimeTypes[format] || 'application/octet-stream';
  }

  private generateDownloadUrl(jobId: string): string {
    return `${this.baseUrl}/download/${jobId}`;
  }

  private generateDownloadToken(): string {
    return Math.random().toString(36).substr(2) + Date.now().toString(36);
  }

  private estimateFileSize(job: ExportJob): number {
    // Simulate file size estimation based on type and format
    const baseSizes: Record<ExportFormat, number> = {
      [ExportFormat.PDF]: 500000, // 500KB
      [ExportFormat.EXCEL]: 100000, // 100KB
      [ExportFormat.CSV]: 50000, // 50KB
      [ExportFormat.JSON]: 75000, // 75KB
      [ExportFormat.PNG]: 200000, // 200KB
      [ExportFormat.SVG]: 25000, // 25KB
    };

    const baseSize = baseSizes[job.format] || 100000;
    return baseSize + Math.floor(Math.random() * baseSize * 0.5);
  }

  private generateJobId(): string {
    return `export_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  private startProcessingQueue(): void {
    // Start processing queue immediately and then check every 5 seconds
    this.processNextJob();
    setInterval(() => this.processNextJob(), 5000);
  }
}

// Singleton instance
let globalExportService: ExportService | null = null;

export const getExportService = (
  baseUrl?: string,
  analyticsService?: AnalyticsService,
  reportsService?: ReportsService
): ExportService => {
  if (!globalExportService) {
    globalExportService = new ExportService(baseUrl, analyticsService, reportsService);
  }
  return globalExportService;
};
