/**
 * Enhanced DataSourceService with WebSocket Integration
 *
 * Extends the original DataSourceService with real-time WebSocket updates
 * using the DataManagementWebSocketService
 */

import { EventEmitter } from 'events';
import { DataSourceService, DataSourceServiceConfig } from './dataSource';
import { DataManagementWebSocketService, getDataManagementWebSocket } from './dataManagementWebSocket';
import { WebSocketMessageType, DataSourceStatusMessage, DataSourceMetricsMessage } from '@/types/websocket';
import {
  DataSource,
  ConnectionStatus,
  DataSourceType,
} from '@/types/dataManagement';

export interface EnhancedDataSourceServiceConfig extends Omit<DataSourceServiceConfig, 'websocket'> {
  websocketService?: DataManagementWebSocketService;
  enableRealTimeUpdates?: boolean;
  realTimeUpdateInterval?: number;
}

export class EnhancedDataSourceService extends DataSourceService {
  private websocketService: DataManagementWebSocketService;
  private enableRealTime: boolean;
  private subscriptionIds: string[] = [];
  private realTimeUpdateTimer?: NodeJS.Timeout;

  constructor(config: EnhancedDataSourceServiceConfig) {
    // Call parent constructor with legacy websocket config
    super({
      ...config,
      websocket: undefined, // We'll use our own WebSocket service
    });

    this.websocketService = config.websocketService || getDataManagementWebSocket();
    this.enableRealTime = config.enableRealTimeUpdates ?? true;

    if (this.enableRealTime) {
      this.initializeWebSocketIntegration();
    }
  }

  /**
   * Initialize WebSocket integration for real-time updates
   */
  private async initializeWebSocketIntegration(): Promise<void> {
    try {
      // Connect to WebSocket if not already connected
      if (!this.websocketService.isConnected()) {
        await this.websocketService.connect();
      }

      // Subscribe to data source updates
      const statusSubscriptionId = this.websocketService.subscribe({
        type: WebSocketMessageType.DATA_SOURCE_STATUS,
        callback: this.handleDataSourceStatusUpdate.bind(this),
      });

      const metricsSubscriptionId = this.websocketService.subscribe({
        type: WebSocketMessageType.DATA_SOURCE_METRICS,
        callback: this.handleDataSourceMetricsUpdate.bind(this),
      });

      this.subscriptionIds.push(statusSubscriptionId, metricsSubscriptionId);

      // Start periodic status requests
      this.startRealTimeUpdates();

      console.log('[DataSource] Real-time WebSocket integration initialized');
    } catch (error) {
      console.error('[DataSource] Failed to initialize WebSocket integration:', error);
    }
  }

  /**
   * Handle incoming data source status updates via WebSocket
   */
  private handleDataSourceStatusUpdate(message: DataSourceStatusMessage): void {
    const { sourceId, status, metrics, error } = message.data;

    // Update local cache
    this.updateSourceStatus(sourceId, {
      id: sourceId,
      status: this.mapWebSocketStatusToConnectionStatus(status),
      latency: metrics?.latency || null,
      lastUpdate: new Date(),
      errorMessage: error,
    });

    // Emit real-time event
    this.emit('realtime:statusUpdate', {
      sourceId,
      status,
      metrics,
      error,
      timestamp: new Date(message.timestamp),
    });
  }

  /**
   * Handle incoming data source metrics updates via WebSocket
   */
  private handleDataSourceMetricsUpdate(message: DataSourceMetricsMessage): void {
    const { sourceId, metrics } = message.data;

    // Update local cache with metrics
    this.updateSourceMetrics(sourceId, {
      latency: metrics.averageLatency,
      throughput: metrics.recordsProcessed / parseInt(message.data.timeWindow) || 0,
      errorRate: metrics.errorCount / metrics.recordsReceived || 0,
    });

    // Emit real-time event
    this.emit('realtime:metricsUpdate', {
      sourceId,
      metrics,
      timestamp: new Date(message.timestamp),
    });
  }

  /**
   * Map WebSocket status to ConnectionStatus enum
   */
  private mapWebSocketStatusToConnectionStatus(status: string): ConnectionStatus {
    switch (status) {
      case 'connected':
        return ConnectionStatus.CONNECTED;
      case 'disconnected':
        return ConnectionStatus.DISCONNECTED;
      case 'error':
        return ConnectionStatus.ERROR;
      default:
        return ConnectionStatus.UNKNOWN;
    }
  }

  /**
   * Start real-time status updates
   */
  private startRealTimeUpdates(): void {
    // Request initial status for all sources
    this.websocketService.requestDataSourceStatus();

    // Set up periodic status requests
    this.realTimeUpdateTimer = setInterval(() => {
      this.websocketService.requestDataSourceStatus();
    }, 30000); // Every 30 seconds
  }

  /**
   * Stop real-time updates
   */
  private stopRealTimeUpdates(): void {
    if (this.realTimeUpdateTimer) {
      clearInterval(this.realTimeUpdateTimer);
      this.realTimeUpdateTimer = undefined;
    }
  }

  /**
   * Request real-time status for a specific source
   */
  async requestRealTimeStatus(sourceId: string): Promise<void> {
    if (this.enableRealTime && this.websocketService.isConnected()) {
      this.websocketService.requestDataSourceStatus(sourceId);
    }
  }

  /**
   * Enable real-time updates for specific sources
   */
  async subscribeToRealTimeUpdates(sourceIds?: string[]): Promise<string> {
    if (!this.enableRealTime) {
      throw new Error('Real-time updates are disabled');
    }

    const subscriptionId = this.websocketService.subscribeToDataSources(sourceIds);
    this.subscriptionIds.push(subscriptionId);
    return subscriptionId;
  }

  /**
   * Disable real-time updates for specific subscription
   */
  unsubscribeFromRealTimeUpdates(subscriptionId: string): void {
    this.websocketService.unsubscribe(subscriptionId);
    const index = this.subscriptionIds.indexOf(subscriptionId);
    if (index > -1) {
      this.subscriptionIds.splice(index, 1);
    }
  }

  /**
   * Get WebSocket connection status
   */
  getWebSocketStatus(): {
    connected: boolean;
    state: string;
    latency?: number;
    lastHeartbeat?: Date;
  } {
    const status = this.websocketService.getConnectionStatus();
    return {
      connected: this.websocketService.isConnected(),
      state: status.state,
      latency: status.latency,
      lastHeartbeat: status.lastHeartbeat,
    };
  }

  /**
   * Force reconnect WebSocket
   */
  async reconnectWebSocket(): Promise<void> {
    await this.websocketService.reconnect();
  }

  /**
   * Override the original sendRealtimeUpdate to use our WebSocket service
   */
  sendRealtimeUpdate(update: any): void {
    if (this.enableRealTime && this.websocketService.isConnected()) {
      this.websocketService.send({
        type: WebSocketMessageType.DATA_SOURCE_STATUS,
        data: {
          sourceId: update.sourceId,
          status: update.status,
          metrics: update.metrics,
          timestamp: update.timestamp?.toISOString() || new Date().toISOString(),
        },
      });
    }
  }

  /**
   * Get real-time performance summary
   */
  getRealTimePerformanceSummary(): {
    totalSources: number;
    connectedSources: number;
    avgLatency: number;
    errorRate: number;
    lastUpdate: Date;
  } {
    const sources = this.getCachedDataSources();
    const connected = sources.filter(s => s.status === ConnectionStatus.CONNECTED);
    const totalLatency = sources.reduce((sum, s) => sum + (s.latency || 0), 0);
    const totalErrors = sources.reduce((sum, s) => sum + (s.errorRate || 0), 0);

    return {
      totalSources: sources.length,
      connectedSources: connected.length,
      avgLatency: sources.length > 0 ? totalLatency / sources.length : 0,
      errorRate: sources.length > 0 ? totalErrors / sources.length : 0,
      lastUpdate: new Date(),
    };
  }

  /**
   * Get sources with recent activity (last 5 minutes)
   */
  getRecentlyActiveSources(): DataSource[] {
    const fiveMinutesAgo = new Date(Date.now() - 5 * 60 * 1000);
    return this.getCachedDataSources().filter(source =>
      source.lastUpdate && source.lastUpdate > fiveMinutesAgo
    );
  }

  /**
   * Get sources by real-time health status
   */
  getSourcesByHealth(): {
    healthy: DataSource[];
    warning: DataSource[];
    critical: DataSource[];
  } {
    const sources = this.getCachedDataSources();

    return {
      healthy: sources.filter(s =>
        s.status === ConnectionStatus.CONNECTED &&
        (s.errorRate || 0) < 0.01 &&
        (s.latency || 0) < 500
      ),
      warning: sources.filter(s =>
        s.status === ConnectionStatus.CONNECTED &&
        ((s.errorRate || 0) >= 0.01 || (s.latency || 0) >= 500)
      ),
      critical: sources.filter(s =>
        s.status !== ConnectionStatus.CONNECTED ||
        (s.errorRate || 0) >= 0.05
      ),
    };
  }

  /**
   * Export real-time data for analytics
   */
  exportRealTimeData(): {
    timestamp: string;
    sources: Array<{
      id: string;
      name: string;
      type: DataSourceType;
      status: ConnectionStatus;
      latency: number;
      throughput: number;
      errorRate: number;
      uptime: number;
      lastUpdate: string;
    }>;
    summary: {
      total: number;
      connected: number;
      avgLatency: number;
      avgThroughput: number;
      avgErrorRate: number;
    };
  } {
    const sources = this.getCachedDataSources();

    return {
      timestamp: new Date().toISOString(),
      sources: sources.map(source => ({
        id: source.id,
        name: source.name,
        type: source.type,
        status: source.status,
        latency: source.latency || 0,
        throughput: source.throughput || 0,
        errorRate: source.errorRate || 0,
        uptime: source.uptime || 0,
        lastUpdate: source.lastUpdate?.toISOString() || '',
      })),
      summary: {
        total: sources.length,
        connected: sources.filter(s => s.status === ConnectionStatus.CONNECTED).length,
        avgLatency: sources.reduce((sum, s) => sum + (s.latency || 0), 0) / sources.length || 0,
        avgThroughput: sources.reduce((sum, s) => sum + (s.throughput || 0), 0) / sources.length || 0,
        avgErrorRate: sources.reduce((sum, s) => sum + (s.errorRate || 0), 0) / sources.length || 0,
      },
    };
  }

  /**
   * Enhanced destroy method
   */
  destroy(): void {
    // Unsubscribe from all WebSocket subscriptions
    this.subscriptionIds.forEach(id => {
      this.websocketService.unsubscribe(id);
    });
    this.subscriptionIds = [];

    // Stop real-time updates
    this.stopRealTimeUpdates();

    // Call parent destroy
    super.destroy();

    console.log('[DataSource] Enhanced service destroyed');
  }

  /**
   * Event emitter methods for type safety
   */
  private emit(event: string, data: any): void {
    if (this['eventBus']) {
      this['eventBus'].emit(event, data);
    }
  }

  on(event: string, listener: (...args: any[]) => void): void {
    if (this['eventBus']) {
      this['eventBus'].on(event, listener);
    }
  }

  off(event: string, listener: (...args: any[]) => void): void {
    if (this['eventBus']) {
      this['eventBus'].off(event, listener);
    }
  }
}

// Enhanced singleton instance
let globalEnhancedDataSourceService: EnhancedDataSourceService | null = null;

/**
 * Get or create global enhanced data source service instance
 */
export const getEnhancedDataSourceService = (config?: EnhancedDataSourceServiceConfig): EnhancedDataSourceService => {
  if (!globalEnhancedDataSourceService && config) {
    globalEnhancedDataSourceService = new EnhancedDataSourceService(config);
  }

  if (!globalEnhancedDataSourceService) {
    throw new Error('Enhanced DataSourceService not initialized. Call getEnhancedDataSourceService with config first.');
  }

  return globalEnhancedDataSourceService;
};
