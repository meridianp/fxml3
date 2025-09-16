/**
 * WebSocket Types and Interfaces
 *
 * TypeScript definitions for real-time WebSocket communication
 */

// Connection states
export enum WebSocketState {
  CONNECTING = 'CONNECTING',
  CONNECTED = 'CONNECTED',
  DISCONNECTED = 'DISCONNECTED',
  RECONNECTING = 'RECONNECTING',
  ERROR = 'ERROR',
  CLOSED = 'CLOSED',
}

// Message types
export enum WebSocketMessageType {
  // Connection management
  CONNECT = 'CONNECT',
  DISCONNECT = 'DISCONNECT',
  HEARTBEAT = 'HEARTBEAT',
  AUTH = 'AUTH',

  // Data sources
  DATA_SOURCE_STATUS = 'DATA_SOURCE_STATUS',
  DATA_SOURCE_METRICS = 'DATA_SOURCE_METRICS',
  CONNECTION_HEALTH = 'CONNECTION_HEALTH',

  // Storage
  STORAGE_METRICS = 'STORAGE_METRICS',
  STORAGE_ALERT = 'STORAGE_ALERT',
  CACHE_METRICS = 'CACHE_METRICS',

  // Data quality
  QUALITY_REPORT = 'QUALITY_REPORT',
  VALIDATION_RESULT = 'VALIDATION_RESULT',
  QUALITY_ALERT = 'QUALITY_ALERT',

  // Pipeline
  PIPELINE_STATUS = 'PIPELINE_STATUS',
  JOB_UPDATE = 'JOB_UPDATE',
  JOB_COMPLETE = 'JOB_COMPLETE',
  JOB_FAILED = 'JOB_FAILED',

  // Notifications
  ALERT = 'ALERT',
  NOTIFICATION = 'NOTIFICATION',
  SYSTEM_STATUS = 'SYSTEM_STATUS',

  // Error handling
  ERROR = 'ERROR',
  WARNING = 'WARNING',
}

// Base message interface
export interface WebSocketMessage {
  id: string;
  type: WebSocketMessageType;
  timestamp: string;
  source: string;
  data: any;
  correlationId?: string;
}

// Connection info
export interface WebSocketConnectionInfo {
  url: string;
  protocols?: string[];
  headers?: Record<string, string>;
  auth?: {
    token: string;
    type: 'Bearer' | 'Basic' | 'Custom';
  };
  reconnect?: {
    enabled: boolean;
    maxAttempts: number;
    delay: number;
    backoff: number;
  };
  heartbeat?: {
    enabled: boolean;
    interval: number;
    timeout: number;
  };
}

// Connection status
export interface WebSocketConnectionStatus {
  state: WebSocketState;
  url: string;
  connectedAt?: Date;
  lastHeartbeat?: Date;
  reconnectAttempts: number;
  error?: string;
  latency?: number;
}

// Event listeners
export interface WebSocketEventListeners {
  onOpen?: (event: Event) => void;
  onClose?: (event: CloseEvent) => void;
  onError?: (event: Event) => void;
  onMessage?: (message: WebSocketMessage) => void;
  onReconnect?: (attempt: number) => void;
  onStateChange?: (state: WebSocketState) => void;
}

// Data source real-time messages
export interface DataSourceStatusMessage extends WebSocketMessage {
  type: WebSocketMessageType.DATA_SOURCE_STATUS;
  data: {
    sourceId: string;
    status: 'connected' | 'disconnected' | 'error';
    metrics?: {
      latency: number;
      throughput: number;
      errorRate: number;
    };
    error?: string;
  };
}

export interface DataSourceMetricsMessage extends WebSocketMessage {
  type: WebSocketMessageType.DATA_SOURCE_METRICS;
  data: {
    sourceId: string;
    metrics: {
      recordsReceived: number;
      recordsProcessed: number;
      bytesReceived: number;
      averageLatency: number;
      peakLatency: number;
      errorCount: number;
    };
    timeWindow: string;
  };
}

// Storage real-time messages
export interface StorageMetricsMessage extends WebSocketMessage {
  type: WebSocketMessageType.STORAGE_METRICS;
  data: {
    database: {
      connections: number;
      usage: number;
      performance: {
        avgQueryTime: number;
        slowQueries: number;
        cacheHitRate: number;
      };
    };
    cache: {
      hitRate: number;
      missRate: number;
      evictions: number;
      memory: {
        used: number;
        total: number;
        available: number;
      };
    };
    disk: {
      usage: number;
      total: number;
      available: number;
      iops: number;
    };
  };
}

// Data quality real-time messages
export interface QualityReportMessage extends WebSocketMessage {
  type: WebSocketMessageType.QUALITY_REPORT;
  data: {
    overall: {
      score: number;
      level: string;
      totalRecords: number;
      validRecords: number;
      invalidRecords: number;
    };
    datasets: Record<string, {
      score: number;
      level: string;
      recordCount: number;
      validRecords: number;
      invalidRecords: number;
    }>;
    trends: Array<{
      timestamp: string;
      overallScore: number;
      completeness: number;
      accuracy: number;
      consistency: number;
      timeliness: number;
    }>;
  };
}

export interface ValidationResultMessage extends WebSocketMessage {
  type: WebSocketMessageType.VALIDATION_RESULT;
  data: {
    ruleId: string;
    dataset: string;
    field: string;
    result: 'passed' | 'failed' | 'warning';
    recordCount: number;
    failedCount: number;
    samples?: Array<{
      recordId: string;
      value: any;
      expected: any;
      reason: string;
    }>;
  };
}

// Pipeline real-time messages
export interface JobUpdateMessage extends WebSocketMessage {
  type: WebSocketMessageType.JOB_UPDATE;
  data: {
    jobId: string;
    pipelineId: string;
    status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';
    progress?: number;
    stage?: string;
    processedRecords?: number;
    totalRecords?: number;
    estimatedCompletion?: string;
    resourceUsage?: {
      cpu: number;
      memory: number;
      gpu?: number;
      disk: number;
    };
    metrics?: Record<string, any>;
    error?: {
      message: string;
      code: string;
      stack?: string;
    };
  };
}

export interface PipelineStatusMessage extends WebSocketMessage {
  type: WebSocketMessageType.PIPELINE_STATUS;
  data: {
    pipelineId: string;
    status: 'active' | 'inactive' | 'running' | 'failed';
    lastRun?: string;
    nextRun?: string;
    runningJobs: number;
    queuedJobs: number;
    metrics: {
      successRate: number;
      averageRuntime: number;
      totalRuns: number;
      failedRuns: number;
    };
  };
}

// Alert and notification messages
export interface AlertMessage extends WebSocketMessage {
  type: WebSocketMessageType.ALERT;
  data: {
    alertId: string;
    alertType: 'data_source' | 'storage' | 'data_quality' | 'pipeline' | 'system';
    severity: 'info' | 'warning' | 'error' | 'critical';
    title: string;
    message: string;
    source: string;
    metadata?: Record<string, any>;
    actions?: Array<{
      id: string;
      label: string;
      type: 'button' | 'link';
      action: string;
    }>;
  };
}

export interface SystemStatusMessage extends WebSocketMessage {
  type: WebSocketMessageType.SYSTEM_STATUS;
  data: {
    health: 'healthy' | 'warning' | 'critical';
    score: number;
    components: Record<string, {
      status: 'online' | 'offline' | 'degraded';
      health: number;
      lastCheck: string;
    }>;
    alerts: number;
    warnings: number;
    errors: number;
  };
}

// Subscription management
export interface WebSocketSubscription {
  id: string;
  type: WebSocketMessageType | WebSocketMessageType[];
  filters?: Record<string, any>;
  callback: (message: WebSocketMessage) => void;
  active: boolean;
  createdAt: Date;
}

// Configuration
export interface WebSocketConfig {
  url: string;
  autoConnect: boolean;
  reconnect: {
    enabled: boolean;
    maxAttempts: number;
    delay: number;
    backoff: number;
  };
  heartbeat: {
    enabled: boolean;
    interval: number;
    timeout: number;
  };
  auth?: {
    token: string;
    type: 'Bearer' | 'Basic' | 'Custom';
  };
  debug: boolean;
  maxMessageSize: number;
  queueSize: number;
}

// Service interface
export interface IWebSocketService {
  // Connection management
  connect(config?: Partial<WebSocketConfig>): Promise<void>;
  disconnect(): void;
  reconnect(): Promise<void>;

  // State
  getState(): WebSocketState;
  getConnectionStatus(): WebSocketConnectionStatus;
  isConnected(): boolean;

  // Messaging
  send(message: Partial<WebSocketMessage>): void;
  subscribe(subscription: Omit<WebSocketSubscription, 'id' | 'active' | 'createdAt'>): string;
  unsubscribe(subscriptionId: string): void;

  // Events
  addEventListener(event: string, listener: Function): void;
  removeEventListener(event: string, listener: Function): void;

  // Lifecycle
  destroy(): void;
}
