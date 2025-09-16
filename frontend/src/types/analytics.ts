/**
 * Analytics Types and Interfaces
 *
 * TypeScript definitions for performance analytics, reporting, and export functionality
 */

// Core analytics data structures
export interface AnalyticsMetric {
  id: string;
  name: string;
  description: string;
  category: AnalyticsCategory;
  value: number;
  unit: string;
  timestamp: Date;
  metadata?: Record<string, any>;
  tags?: string[];
}

export interface AnalyticsQuery {
  id?: string;
  name?: string;
  timeRange: TimeRange;
  metrics: string[];
  filters?: AnalyticsFilter[];
  groupBy?: string[];
  aggregation?: AggregationType;
  limit?: number;
  offset?: number;
}

export interface AnalyticsResult {
  query: AnalyticsQuery;
  data: AnalyticsDataPoint[];
  metadata: {
    totalRecords: number;
    executionTime: number;
    dataQuality: number;
    lastUpdated: Date;
  };
}

export interface AnalyticsDataPoint {
  timestamp: Date;
  metrics: Record<string, number>;
  dimensions: Record<string, string>;
  metadata?: Record<string, any>;
}

// Time range definitions
export interface TimeRange {
  start: Date;
  end: Date;
  interval?: TimeInterval;
  timezone?: string;
}

export enum TimeInterval {
  MINUTE = '1m',
  FIVE_MINUTES = '5m',
  FIFTEEN_MINUTES = '15m',
  HOUR = '1h',
  DAY = '1d',
  WEEK = '1w',
  MONTH = '1M',
  QUARTER = '3M',
  YEAR = '1y',
}

// Analytics categories
export enum AnalyticsCategory {
  DATA_SOURCE = 'data_source',
  STORAGE = 'storage',
  DATA_QUALITY = 'data_quality',
  PIPELINE = 'pipeline',
  PERFORMANCE = 'performance',
  SYSTEM = 'system',
  BUSINESS = 'business',
  CUSTOM = 'custom',
}

// Filtering and aggregation
export interface AnalyticsFilter {
  field: string;
  operator: FilterOperator;
  value: any;
  values?: any[];
}

export enum FilterOperator {
  EQUALS = 'eq',
  NOT_EQUALS = 'ne',
  GREATER_THAN = 'gt',
  GREATER_THAN_EQUAL = 'gte',
  LESS_THAN = 'lt',
  LESS_THAN_EQUAL = 'lte',
  IN = 'in',
  NOT_IN = 'nin',
  CONTAINS = 'contains',
  STARTS_WITH = 'starts_with',
  ENDS_WITH = 'ends_with',
  BETWEEN = 'between',
  IS_NULL = 'is_null',
  IS_NOT_NULL = 'is_not_null',
}

export enum AggregationType {
  SUM = 'sum',
  AVG = 'avg',
  MIN = 'min',
  MAX = 'max',
  COUNT = 'count',
  COUNT_DISTINCT = 'count_distinct',
  MEDIAN = 'median',
  PERCENTILE = 'percentile',
  STANDARD_DEVIATION = 'stddev',
  VARIANCE = 'variance',
}

// Trend analysis
export interface TrendAnalysis {
  metric: string;
  timeRange: TimeRange;
  trend: TrendDirection;
  confidence: number;
  slope: number;
  correlation: number;
  forecast?: ForecastData[];
  anomalies?: AnomalyData[];
  seasonality?: SeasonalityData;
}

export enum TrendDirection {
  INCREASING = 'increasing',
  DECREASING = 'decreasing',
  STABLE = 'stable',
  VOLATILE = 'volatile',
  UNKNOWN = 'unknown',
}

export interface ForecastData {
  timestamp: Date;
  value: number;
  confidence: number;
  upperBound: number;
  lowerBound: number;
}

export interface AnomalyData {
  timestamp: Date;
  value: number;
  expectedValue: number;
  deviationScore: number;
  anomalyType: AnomalyType;
  severity: AnomalySeverity;
}

export enum AnomalyType {
  SPIKE = 'spike',
  DIP = 'dip',
  TREND_CHANGE = 'trend_change',
  SEASONAL_DEVIATION = 'seasonal_deviation',
  MISSING_DATA = 'missing_data',
}

export enum AnomalySeverity {
  LOW = 'low',
  MEDIUM = 'medium',
  HIGH = 'high',
  CRITICAL = 'critical',
}

export interface SeasonalityData {
  period: TimeInterval;
  strength: number;
  patterns: Array<{
    period: string;
    amplitude: number;
    phase: number;
  }>;
}

// KPI and performance monitoring
export interface KPI {
  id: string;
  name: string;
  description: string;
  category: AnalyticsCategory;
  metric: string;
  target: number;
  unit: string;
  thresholds: KPIThresholds;
  status: KPIStatus;
  currentValue: number;
  previousValue?: number;
  trend: TrendDirection;
  lastUpdated: Date;
}

export interface KPIThresholds {
  critical: { min?: number; max?: number };
  warning: { min?: number; max?: number };
  target: { min: number; max: number };
}

export enum KPIStatus {
  EXCELLENT = 'excellent',
  GOOD = 'good',
  WARNING = 'warning',
  CRITICAL = 'critical',
  UNKNOWN = 'unknown',
}

export interface PerformanceBaseline {
  metric: string;
  category: AnalyticsCategory;
  baseline: number;
  unit: string;
  confidence: number;
  createdAt: Date;
  validUntil: Date;
  metadata: {
    sampleSize: number;
    method: string;
    seasonality: boolean;
  };
}

// Reporting system
export interface Report {
  id: string;
  name: string;
  description: string;
  type: ReportType;
  template: ReportTemplate;
  parameters: ReportParameters;
  schedule?: ReportSchedule;
  status: ReportStatus;
  createdAt: Date;
  updatedAt: Date;
  createdBy: string;
  lastExecuted?: Date;
  nextExecution?: Date;
}

export interface ReportTemplate {
  id: string;
  name: string;
  description: string;
  layout: ReportLayout;
  sections: ReportSection[];
  style: ReportStyle;
  version: string;
  createdAt: Date;
}

export interface ReportSection {
  id: string;
  type: ReportSectionType;
  title: string;
  order: number;
  config: ReportSectionConfig;
  visible: boolean;
}

export enum ReportType {
  OPERATIONAL = 'operational',
  EXECUTIVE = 'executive',
  TECHNICAL = 'technical',
  COMPLIANCE = 'compliance',
  CUSTOM = 'custom',
}

export enum ReportSectionType {
  SUMMARY = 'summary',
  KPI_SCORECARD = 'kpi_scorecard',
  TREND_ANALYSIS = 'trend_analysis',
  DATA_TABLE = 'data_table',
  CHART = 'chart',
  TEXT = 'text',
  IMAGE = 'image',
  CUSTOM = 'custom',
}

export interface ReportSectionConfig {
  query?: AnalyticsQuery;
  chartType?: ChartType;
  chartConfig?: ChartConfig;
  kpis?: string[];
  text?: string;
  imageUrl?: string;
  customConfig?: Record<string, any>;
}

export interface ReportLayout {
  orientation: 'portrait' | 'landscape';
  pageSize: 'A4' | 'A3' | 'Letter' | 'Legal';
  margins: { top: number; right: number; bottom: number; left: number };
  columns: number;
  spacing: number;
}

export interface ReportStyle {
  primaryColor: string;
  secondaryColor: string;
  fontFamily: string;
  fontSize: number;
  headerStyle: TextStyle;
  bodyStyle: TextStyle;
  tableStyle: TableStyle;
}

export interface TextStyle {
  fontFamily?: string;
  fontSize?: number;
  fontWeight?: string;
  color?: string;
  alignment?: 'left' | 'center' | 'right' | 'justify';
}

export interface TableStyle {
  headerBackground: string;
  headerColor: string;
  alternateRowBackground: string;
  borderColor: string;
  borderWidth: number;
}

export interface ReportParameters {
  timeRange: TimeRange;
  filters: AnalyticsFilter[];
  includeCharts: boolean;
  includeData: boolean;
  includeSummary: boolean;
  customParameters?: Record<string, any>;
}

export interface ReportSchedule {
  enabled: boolean;
  frequency: ScheduleFrequency;
  interval: number;
  timezone: string;
  startDate: Date;
  endDate?: Date;
  recipients: ReportRecipient[];
  deliveryMethod: DeliveryMethod[];
}

export enum ScheduleFrequency {
  HOURLY = 'hourly',
  DAILY = 'daily',
  WEEKLY = 'weekly',
  MONTHLY = 'monthly',
  QUARTERLY = 'quarterly',
  YEARLY = 'yearly',
}

export interface ReportRecipient {
  type: 'email' | 'webhook' | 'slack' | 'teams';
  address: string;
  name?: string;
  parameters?: Record<string, any>;
}

export enum DeliveryMethod {
  EMAIL = 'email',
  WEBHOOK = 'webhook',
  SLACK = 'slack',
  TEAMS = 'teams',
  SFTP = 'sftp',
  S3 = 's3',
}

export enum ReportStatus {
  DRAFT = 'draft',
  ACTIVE = 'active',
  PAUSED = 'paused',
  ARCHIVED = 'archived',
  ERROR = 'error',
}

// Export system
export interface ExportJob {
  id: string;
  name: string;
  type: ExportType;
  format: ExportFormat;
  query?: AnalyticsQuery;
  report?: string; // Report ID
  parameters: ExportParameters;
  status: ExportStatus;
  progress: number;
  createdAt: Date;
  startedAt?: Date;
  completedAt?: Date;
  createdBy: string;
  fileSize?: number;
  downloadUrl?: string;
  error?: string;
}

export enum ExportType {
  DATA = 'data',
  REPORT = 'report',
  CHART = 'chart',
  DASHBOARD = 'dashboard',
}

export enum ExportFormat {
  PDF = 'pdf',
  EXCEL = 'xlsx',
  CSV = 'csv',
  JSON = 'json',
  PNG = 'png',
  SVG = 'svg',
}

export interface ExportParameters {
  includeMetadata: boolean;
  includeCharts: boolean;
  chartResolution?: number;
  compression?: boolean;
  password?: string;
  customParameters?: Record<string, any>;
}

export enum ExportStatus {
  QUEUED = 'queued',
  PROCESSING = 'processing',
  COMPLETED = 'completed',
  FAILED = 'failed',
  CANCELLED = 'cancelled',
}

// Chart configurations
export enum ChartType {
  LINE = 'line',
  AREA = 'area',
  BAR = 'bar',
  COLUMN = 'column',
  PIE = 'pie',
  DOUGHNUT = 'doughnut',
  SCATTER = 'scatter',
  HEATMAP = 'heatmap',
  GAUGE = 'gauge',
  TREEMAP = 'treemap',
  FUNNEL = 'funnel',
  WATERFALL = 'waterfall',
}

export interface ChartConfig {
  title?: string;
  subtitle?: string;
  xAxis?: AxisConfig;
  yAxis?: AxisConfig;
  legend?: LegendConfig;
  colors?: string[];
  animations?: boolean;
  responsive?: boolean;
  height?: number;
  width?: number;
}

export interface AxisConfig {
  title?: string;
  type?: 'linear' | 'logarithmic' | 'datetime' | 'category';
  min?: number;
  max?: number;
  format?: string;
  gridLines?: boolean;
}

export interface LegendConfig {
  show: boolean;
  position: 'top' | 'bottom' | 'left' | 'right';
  alignment: 'start' | 'center' | 'end';
}

// Statistical analysis
export interface StatisticalSummary {
  metric: string;
  timeRange: TimeRange;
  count: number;
  sum: number;
  mean: number;
  median: number;
  mode?: number;
  min: number;
  max: number;
  range: number;
  variance: number;
  standardDeviation: number;
  skewness: number;
  kurtosis: number;
  percentiles: Record<string, number>; // 25th, 50th, 75th, 90th, 95th, 99th
}

export interface CorrelationAnalysis {
  metric1: string;
  metric2: string;
  timeRange: TimeRange;
  coefficient: number;
  pValue: number;
  significance: number;
  type: 'pearson' | 'spearman' | 'kendall';
}

// Service interfaces
export interface IAnalyticsService {
  // Data aggregation
  aggregate(query: AnalyticsQuery): Promise<AnalyticsResult>;
  getMetrics(category?: AnalyticsCategory): Promise<AnalyticsMetric[]>;
  getHistoricalData(metric: string, timeRange: TimeRange): Promise<AnalyticsDataPoint[]>;
  addDataPoint(dataPoint: AnalyticsDataPoint): Promise<void>;

  // Trend analysis
  analyzeTrend(metric: string, timeRange: TimeRange): Promise<TrendAnalysis>;
  detectAnomalies(metric: string, timeRange: TimeRange): Promise<AnomalyData[]>;
  generateForecast(metric: string, timeRange: TimeRange, horizon: TimeInterval): Promise<ForecastData[]>;

  // Statistical analysis
  getStatisticalSummary(metric: string, timeRange: TimeRange): Promise<StatisticalSummary>;
  calculateCorrelation(metric1: string, metric2: string, timeRange: TimeRange): Promise<CorrelationAnalysis>;

  // Baselines and benchmarks
  createBaseline(metric: string, timeRange: TimeRange): Promise<PerformanceBaseline>;
  getBaselines(category?: AnalyticsCategory): Promise<PerformanceBaseline[]>;
  compareToBaseline(metric: string, value: number): Promise<{ deviation: number; significance: number }>;
}

export interface IMetricsAggregationService {
  // KPI management
  getKPIs(category?: AnalyticsCategory): Promise<KPI[]>;
  createKPI(kpi: Omit<KPI, 'id' | 'currentValue' | 'status' | 'lastUpdated'>): Promise<KPI>;
  updateKPI(id: string, updates: Partial<KPI>): Promise<KPI>;
  deleteKPI(id: string): Promise<boolean>;
  calculateKPIStatus(kpi: KPI): KPIStatus;

  // Performance monitoring
  getPerformanceSummary(category?: AnalyticsCategory): Promise<{
    kpis: KPI[];
    summary: {
      total: number;
      excellent: number;
      good: number;
      warning: number;
      critical: number;
    };
  }>;

  // Real-time aggregation
  aggregateRealTimeMetrics(): Promise<AnalyticsMetric[]>;
  calculateRollingAverages(metric: string, windowSize: number): Promise<AnalyticsDataPoint[]>;
}

export interface IReportsService {
  // Report management
  getReports(): Promise<Report[]>;
  getReport(id: string): Promise<Report>;
  createReport(report: Omit<Report, 'id' | 'createdAt' | 'updatedAt' | 'status'>): Promise<Report>;
  updateReport(id: string, updates: Partial<Report>): Promise<Report>;
  deleteReport(id: string): Promise<boolean>;

  // Template management
  getTemplates(): Promise<ReportTemplate[]>;
  createTemplate(template: Omit<ReportTemplate, 'id' | 'createdAt'>): Promise<ReportTemplate>;

  // Report generation
  generateReport(reportId: string, parameters?: Partial<ReportParameters>): Promise<ExportJob>;
  previewReport(reportId: string, parameters?: Partial<ReportParameters>): Promise<any>;

  // Scheduling
  scheduleReport(reportId: string, schedule: ReportSchedule): Promise<Report>;
  pauseSchedule(reportId: string): Promise<Report>;
  resumeSchedule(reportId: string): Promise<Report>;
}

export interface IExportService {
  // Export job management
  getExportJobs(): Promise<ExportJob[]>;
  getExportJob(id: string): Promise<ExportJob>;
  createExportJob(job: Omit<ExportJob, 'id' | 'createdAt' | 'status' | 'progress'>): Promise<ExportJob>;
  cancelExportJob(id: string): Promise<boolean>;

  // Data export
  exportData(query: AnalyticsQuery, format: ExportFormat, parameters?: ExportParameters): Promise<ExportJob>;
  exportReport(reportId: string, format: ExportFormat, parameters?: ExportParameters): Promise<ExportJob>;
  exportChart(chartConfig: any, format: ExportFormat, parameters?: ExportParameters): Promise<ExportJob>;

  // File management
  downloadExport(jobId: string): Promise<Blob>;
  getExportUrl(jobId: string): Promise<string>;
  deleteExport(jobId: string): Promise<boolean>;

  // Export statistics
  getExportStatistics(): Promise<ExportStatistics>;
}

// Additional types for analytics integration
export interface SystemHealth {
  overall: number;
  components: {
    dataSource: number;
    storage: number;
    quality: number;
    pipeline: number;
  };
  status: 'healthy' | 'warning' | 'critical';
  lastUpdated: Date;
  trends: Record<string, TrendDirection>;
}

export interface IntegratedMetrics {
  systemHealth: SystemHealth;
  crossServiceMetrics: AnalyticsDataPoint[];
  correlations: CorrelationAnalysis[];
  aggregatedKPIs: KPI[];
}

export interface CrossServiceInsights {
  type: 'correlation' | 'anomaly' | 'trend' | 'pattern';
  description: string;
  strength: number;
  direction?: 'positive' | 'negative';
  confidence: number;
  recommendations: string[];
  affectedServices?: string[];
  impactLevel?: 'low' | 'medium' | 'high' | 'critical';
}

export interface ExportStatistics {
  totalJobs: number;
  activeJobs: number;
  completedJobs: number;
  failedJobs: number;
  totalSize: number;
  averageSize: number;
  averageProcessingTime: number;
  successRate: number;
}
