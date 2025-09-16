/**
 * Data Management Types
 *
 * TypeScript interfaces for advanced data management and monitoring
 */

// Connection status for data sources
export enum ConnectionStatus {
  CONNECTED = 'connected',
  DISCONNECTED = 'disconnected',
  ERROR = 'error',
  DEGRADED = 'degraded',
  CONNECTING = 'connecting',
}

// Data source types
export enum DataSourceType {
  WEBSOCKET = 'websocket',
  REST = 'rest',
  DATABASE = 'database',
  BROKER = 'broker',
  FEED = 'feed',
}

// Data quality levels
export enum DataQualityLevel {
  EXCELLENT = 'excellent',
  GOOD = 'good',
  FAIR = 'fair',
  POOR = 'poor',
  CRITICAL = 'critical',
}

// Pipeline job status
export enum PipelineJobStatus {
  RUNNING = 'running',
  COMPLETED = 'completed',
  FAILED = 'failed',
  PENDING = 'pending',
  CANCELLED = 'cancelled',
  QUEUED = 'queued',
}

// Pipeline job types
export enum PipelineJobType {
  FEATURE_ENGINEERING = 'feature_engineering',
  ML_TRAINING = 'ml_training',
  DATA_INGESTION = 'data_ingestion',
  DATA_VALIDATION = 'data_validation',
  DATA_CLEANUP = 'data_cleanup',
  BACKFILL = 'backfill',
}

// Data source monitoring interface
export interface DataSource {
  id: string;
  name: string;
  type: DataSourceType;
  status: ConnectionStatus;
  url?: string;
  lastUpdate: Date;
  lastHeartbeat: Date;

  // Performance metrics
  latency: number; // ms
  throughput: number; // records/second
  errorRate: number; // percentage
  uptime: number; // percentage

  // Data quality
  qualityScore: number; // 0-100
  qualityLevel: DataQualityLevel;

  // Configuration
  enabled: boolean;
  retryCount: number;
  timeout: number;

  // Metadata
  description?: string;
  tags: string[];
  createdAt: Date;
  updatedAt: Date;
}

// Storage metrics interface
export interface StorageMetrics {
  timestamp: Date;

  // Database metrics
  database: {
    // TimescaleDB specific
    totalSize: number; // bytes
    tableSize: Record<string, number>; // table name -> size in bytes
    indexSize: number; // bytes
    connectionCount: number;
    activeConnections: number;
    maxConnections: number;

    // Query performance
    avgQueryTime: number; // ms
    slowQueries: SlowQuery[];
    queryRate: number; // queries/second

    // Hypertable metrics
    chunks: number;
    compressionRatio: number;
    retentionPolicy: RetentionPolicy[];
  };

  // Redis cache metrics
  cache: {
    memoryUsage: number; // bytes
    maxMemory: number; // bytes
    hitRate: number; // percentage
    missRate: number; // percentage
    evictionRate: number; // evictions/second
    keyCount: number;
    expiredKeys: number;
    connectedClients: number;

    // Performance
    opsPerSecond: number;
    avgLatency: number; // ms
  };

  // File system metrics
  filesystem?: {
    totalSpace: number; // bytes
    usedSpace: number; // bytes
    freeSpace: number; // bytes
    inodeUsage: number; // percentage
  };
}

// Slow query interface
export interface SlowQuery {
  id: string;
  query: string;
  duration: number; // ms
  timestamp: Date;
  database: string;
  user: string;
  rowsExamined: number;
  rowsReturned: number;
}

// Retention policy interface
export interface RetentionPolicy {
  tableName: string;
  retentionPeriod: string; // e.g., "30 days", "1 year"
  compressionPolicy?: string;
  lastCleanup: Date;
  dataRemoved: number; // bytes
}

// Data quality metrics interface
export interface DataQualityMetrics {
  timestamp: Date;
  source: string;
  symbol?: string;
  timeframe?: string;

  // Completeness metrics
  completeness: {
    score: number; // 0-100
    expectedRecords: number;
    actualRecords: number;
    missingRecords: number;
    gapCount: number;
    largestGap: number; // seconds
  };

  // Accuracy metrics
  accuracy: {
    score: number; // 0-100
    outlierCount: number;
    outlierPercentage: number;
    validationErrors: ValidationError[];
  };

  // Timeliness metrics
  timeliness: {
    score: number; // 0-100
    avgDelay: number; // ms
    maxDelay: number; // ms
    lateRecords: number;
    onTimePercentage: number;
  };

  // Consistency metrics
  consistency: {
    score: number; // 0-100
    duplicateCount: number;
    inconsistencyCount: number;
    schemaViolations: number;
  };

  // Overall quality
  overallScore: number; // 0-100
  qualityLevel: DataQualityLevel;

  // Trending
  trend: 'improving' | 'stable' | 'degrading';
  previousScore?: number;
}

// Validation error interface
export interface ValidationError {
  id: string;
  timestamp: Date;
  severity: 'warning' | 'error' | 'critical';
  rule: string;
  field: string;
  value: any;
  message: string;
  source: string;
}

// Pipeline job interface
export interface PipelineJob {
  id: string;
  name: string;
  type: PipelineJobType;
  status: PipelineJobStatus;

  // Timing
  createdAt: Date;
  startedAt?: Date;
  completedAt?: Date;
  duration?: number; // ms
  estimatedDuration?: number; // ms

  // Progress
  progress: number; // 0-100
  currentStep?: string;
  totalSteps?: number;
  completedSteps?: number;

  // Resources
  cpuUsage?: number; // percentage
  memoryUsage?: number; // bytes
  diskUsage?: number; // bytes

  // Results
  recordsProcessed?: number;
  recordsGenerated?: number;
  errorCount?: number;
  warnings?: string[];

  // Configuration
  parameters: Record<string, any>;
  priority: number; // 1-10
  retryCount: number;
  maxRetries: number;

  // Metadata
  description?: string;
  tags: string[];
  owner?: string;
  parentJobId?: string;
  childJobIds?: string[];
}

// Pipeline metrics interface
export interface PipelineMetrics {
  timestamp: Date;

  // Job queue metrics
  queue: {
    totalJobs: number;
    runningJobs: number;
    pendingJobs: number;
    completedJobs: number;
    failedJobs: number;
    queueLength: number;
    avgWaitTime: number; // ms
  };

  // Performance metrics
  performance: {
    throughput: number; // jobs/hour
    avgJobDuration: number; // ms
    successRate: number; // percentage
    failureRate: number; // percentage
    retryRate: number; // percentage
  };

  // Resource utilization
  resources: {
    cpuUsage: number; // percentage
    memoryUsage: number; // bytes
    diskUsage: number; // bytes
    networkUsage: number; // bytes/second
  };

  // Recent jobs
  recentJobs: PipelineJob[];
  failedJobs: PipelineJob[];
}

// Data management alert interface
export interface DataManagementAlert {
  id: string;
  type: 'connection' | 'storage' | 'quality' | 'pipeline';
  severity: 'info' | 'warning' | 'error' | 'critical';
  title: string;
  message: string;
  source: string;
  timestamp: Date;
  acknowledged: boolean;
  acknowledgedBy?: string;
  acknowledgedAt?: Date;
  resolved: boolean;
  resolvedAt?: Date;
  metadata: Record<string, any>;
}

// Data export configuration interface
export interface DataExportConfig {
  id: string;
  name: string;
  type: 'csv' | 'json' | 'excel' | 'pdf';
  tables: string[];
  dateRange: {
    start: Date;
    end: Date;
  };
  filters: Record<string, any>;
  schedule?: {
    enabled: boolean;
    frequency: 'daily' | 'weekly' | 'monthly';
    time: string; // HH:MM format
  };
  destination: {
    type: 'download' | 'email' | 's3' | 'ftp';
    configuration: Record<string, any>;
  };
  createdAt: Date;
  lastExported?: Date;
  enabled: boolean;
}

// Dashboard configuration interface
export interface DataManagementDashboardConfig {
  id: string;
  name: string;
  layout: DashboardWidget[];
  refreshInterval: number; // seconds
  autoRefresh: boolean;
  theme: 'light' | 'dark';
  createdAt: Date;
  updatedAt: Date;
  isDefault: boolean;
  owner?: string;
}

// Dashboard widget interface
export interface DashboardWidget {
  id: string;
  type: 'data_sources' | 'storage' | 'quality' | 'pipeline' | 'alerts' | 'custom';
  title: string;
  position: {
    x: number;
    y: number;
    width: number;
    height: number;
  };
  configuration: Record<string, any>;
  enabled: boolean;
  refreshInterval?: number; // seconds, overrides dashboard default
}
