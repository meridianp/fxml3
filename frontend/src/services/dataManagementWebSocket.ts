/**
 * Data Management WebSocket Service
 *
 * Real-time WebSocket service specifically for data management monitoring
 * Handles real-time updates for data sources, storage, quality, and pipelines
 */

import {
  WebSocketState,
  WebSocketConfig,
  WebSocketMessage,
  WebSocketMessageType,
  WebSocketConnectionStatus,
  WebSocketSubscription,
  IWebSocketService,
  DataSourceStatusMessage,
  StorageMetricsMessage,
  QualityReportMessage,
  JobUpdateMessage,
  AlertMessage,
  SystemStatusMessage,
} from '@/types/websocket';

export class DataManagementWebSocketService implements IWebSocketService {
  private ws: WebSocket | null = null;
  private config: WebSocketConfig;
  private state: WebSocketState = WebSocketState.DISCONNECTED;
  private subscriptions: Map<string, WebSocketSubscription> = new Map();
  private eventListeners: Map<string, Function[]> = new Map();
  private reconnectTimer: NodeJS.Timeout | null = null;
  private heartbeatTimer: NodeJS.Timeout | null = null;
  private messageQueue: WebSocketMessage[] = [];
  private connectionAttempts = 0;
  private lastHeartbeat?: Date;
  private connectedAt?: Date;
  private latency = 0;

  constructor(config: Partial<WebSocketConfig> = {}) {
    this.config = {
      url: config.url || (process.env.NODE_ENV === 'production'
        ? 'wss://api.fxml4.com/ws/data-management'
        : 'ws://localhost:8001/ws/data-management'),
      autoConnect: config.autoConnect ?? false, // Don't auto-connect for data management
      reconnect: {
        enabled: config.reconnect?.enabled ?? true,
        maxAttempts: config.reconnect?.maxAttempts ?? 5,
        delay: config.reconnect?.delay ?? 2000,
        backoff: config.reconnect?.backoff ?? 1.5,
      },
      heartbeat: {
        enabled: config.heartbeat?.enabled ?? true,
        interval: config.heartbeat?.interval ?? 30000,
        timeout: config.heartbeat?.timeout ?? 10000,
      },
      auth: config.auth,
      debug: config.debug ?? (process.env.NODE_ENV === 'development'),
      maxMessageSize: config.maxMessageSize ?? 1024 * 1024, // 1MB
      queueSize: config.queueSize ?? 50,
    };
  }

  // Connection management
  async connect(config?: Partial<WebSocketConfig>): Promise<void> {
    if (config) {
      this.config = { ...this.config, ...config };
    }

    if (this.ws && (this.ws.readyState === WebSocket.CONNECTING || this.ws.readyState === WebSocket.OPEN)) {
      this.log('WebSocket already connected or connecting');
      return;
    }

    try {
      this.setState(WebSocketState.CONNECTING);
      this.log(`Connecting to data management WebSocket: ${this.config.url}`);

      this.ws = new WebSocket(this.config.url);
      this.setupWebSocketEventListeners();

      return new Promise((resolve, reject) => {
        const timeout = setTimeout(() => {
          reject(new Error('Connection timeout'));
        }, 10000);

        const onOpen = () => {
          clearTimeout(timeout);
          this.ws?.removeEventListener('open', onOpen);
          this.ws?.removeEventListener('error', onError);
          resolve();
        };

        const onError = (event: Event) => {
          clearTimeout(timeout);
          this.ws?.removeEventListener('open', onOpen);
          this.ws?.removeEventListener('error', onError);
          reject(new Error('WebSocket connection failed'));
        };

        this.ws?.addEventListener('open', onOpen);
        this.ws?.addEventListener('error', onError);
      });
    } catch (error) {
      this.log('Connection error:', error);
      this.setState(WebSocketState.ERROR);
      throw error;
    }
  }

  disconnect(): void {
    this.log('Disconnecting data management WebSocket');
    this.clearTimers();

    if (this.ws) {
      this.ws.close(1000, 'Client disconnect');
      this.ws = null;
    }

    this.setState(WebSocketState.DISCONNECTED);
    this.connectionAttempts = 0;
  }

  async reconnect(): Promise<void> {
    if (this.state === WebSocketState.RECONNECTING) {
      this.log('Reconnection already in progress');
      return;
    }

    this.disconnect();
    await new Promise(resolve => setTimeout(resolve, 100));
    return this.connect();
  }

  // State management
  getState(): WebSocketState {
    return this.state;
  }

  getConnectionStatus(): WebSocketConnectionStatus {
    return {
      state: this.state,
      url: this.config.url,
      connectedAt: this.connectedAt,
      lastHeartbeat: this.lastHeartbeat,
      reconnectAttempts: this.connectionAttempts,
      latency: this.latency,
      error: this.state === WebSocketState.ERROR ? 'Connection error' : undefined,
    };
  }

  isConnected(): boolean {
    return this.state === WebSocketState.CONNECTED && this.ws?.readyState === WebSocket.OPEN;
  }

  // Messaging
  send(message: Partial<WebSocketMessage>): void {
    const fullMessage: WebSocketMessage = {
      id: message.id || this.generateId(),
      type: message.type || WebSocketMessageType.ERROR,
      timestamp: new Date().toISOString(),
      source: message.source || 'data-management-client',
      data: message.data || {},
      correlationId: message.correlationId,
    };

    if (!this.isConnected()) {
      if (this.messageQueue.length < this.config.queueSize) {
        this.messageQueue.push(fullMessage);
        this.log('Message queued (not connected):', fullMessage.type);
      } else {
        this.log('Message queue full, dropping message:', fullMessage.type);
      }
      return;
    }

    try {
      const messageStr = JSON.stringify(fullMessage);

      if (messageStr.length > this.config.maxMessageSize) {
        this.log('Message too large, dropping:', fullMessage.type);
        return;
      }

      this.ws!.send(messageStr);
      this.log('Message sent:', fullMessage.type);
    } catch (error) {
      this.log('Failed to send message:', error);
    }
  }

  subscribe(subscription: Omit<WebSocketSubscription, 'id' | 'active' | 'createdAt'>): string {
    const id = this.generateId();
    const fullSubscription: WebSocketSubscription = {
      id,
      type: subscription.type,
      filters: subscription.filters,
      callback: subscription.callback,
      active: true,
      createdAt: new Date(),
    };

    this.subscriptions.set(id, fullSubscription);
    this.log('Subscription created:', id, fullSubscription.type);

    // Send subscription request to server
    this.send({
      type: WebSocketMessageType.CONNECT,
      data: {
        action: 'subscribe',
        types: Array.isArray(subscription.type) ? subscription.type : [subscription.type],
        filters: subscription.filters,
      },
    });

    return id;
  }

  unsubscribe(subscriptionId: string): void {
    const subscription = this.subscriptions.get(subscriptionId);
    if (subscription) {
      // Send unsubscribe request to server
      this.send({
        type: WebSocketMessageType.DISCONNECT,
        data: {
          action: 'unsubscribe',
          types: Array.isArray(subscription.type) ? subscription.type : [subscription.type],
        },
      });

      this.subscriptions.delete(subscriptionId);
      this.log('Subscription removed:', subscriptionId);
    }
  }

  // Event handling
  addEventListener(event: string, listener: Function): void {
    if (!this.eventListeners.has(event)) {
      this.eventListeners.set(event, []);
    }
    this.eventListeners.get(event)!.push(listener);
  }

  removeEventListener(event: string, listener: Function): void {
    const listeners = this.eventListeners.get(event);
    if (listeners) {
      const index = listeners.indexOf(listener);
      if (index > -1) {
        listeners.splice(index, 1);
      }
    }
  }

  destroy(): void {
    this.log('Destroying data management WebSocket service');
    this.disconnect();
    this.subscriptions.clear();
    this.eventListeners.clear();
    this.messageQueue = [];
  }

  // Data Management specific subscription methods
  subscribeToDataSources(sourceIds?: string[]): string {
    return this.subscribe({
      type: [WebSocketMessageType.DATA_SOURCE_STATUS, WebSocketMessageType.DATA_SOURCE_METRICS],
      filters: sourceIds ? { 'data.sourceId': sourceIds } : undefined,
      callback: (message) => {
        this.emit('dataSourceUpdate', message);
      },
    });
  }

  subscribeToStorageMetrics(): string {
    return this.subscribe({
      type: WebSocketMessageType.STORAGE_METRICS,
      callback: (message) => {
        this.emit('storageUpdate', message);
      },
    });
  }

  subscribeToDataQuality(datasets?: string[]): string {
    return this.subscribe({
      type: [WebSocketMessageType.QUALITY_REPORT, WebSocketMessageType.VALIDATION_RESULT],
      filters: datasets ? { 'data.dataset': datasets } : undefined,
      callback: (message) => {
        this.emit('qualityUpdate', message);
      },
    });
  }

  subscribeToPipelines(pipelineIds?: string[]): string {
    return this.subscribe({
      type: [WebSocketMessageType.PIPELINE_STATUS, WebSocketMessageType.JOB_UPDATE],
      filters: pipelineIds ? { 'data.pipelineId': pipelineIds } : undefined,
      callback: (message) => {
        this.emit('pipelineUpdate', message);
      },
    });
  }

  subscribeToAlerts(): string {
    return this.subscribe({
      type: [WebSocketMessageType.ALERT, WebSocketMessageType.SYSTEM_STATUS],
      callback: (message) => {
        this.emit('alertUpdate', message);
      },
    });
  }

  // Request methods for pulling data
  requestDataSourceStatus(sourceId?: string): void {
    this.send({
      type: WebSocketMessageType.DATA_SOURCE_STATUS,
      data: { action: 'request', sourceId },
    });
  }

  requestStorageMetrics(): void {
    this.send({
      type: WebSocketMessageType.STORAGE_METRICS,
      data: { action: 'request' },
    });
  }

  requestQualityReport(dataset?: string): void {
    this.send({
      type: WebSocketMessageType.QUALITY_REPORT,
      data: { action: 'request', dataset },
    });
  }

  requestPipelineStatus(pipelineId?: string): void {
    this.send({
      type: WebSocketMessageType.PIPELINE_STATUS,
      data: { action: 'request', pipelineId },
    });
  }

  // Private methods
  private setupWebSocketEventListeners(): void {
    if (!this.ws) return;

    this.ws.addEventListener('open', this.handleOpen.bind(this));
    this.ws.addEventListener('close', this.handleClose.bind(this));
    this.ws.addEventListener('error', this.handleError.bind(this));
    this.ws.addEventListener('message', this.handleMessage.bind(this));
  }

  private handleOpen(event: Event): void {
    this.log('Data management WebSocket connected');
    this.setState(WebSocketState.CONNECTED);
    this.connectedAt = new Date();
    this.connectionAttempts = 0;

    // Send authentication if configured
    if (this.config.auth) {
      this.send({
        type: WebSocketMessageType.AUTH,
        data: {
          token: this.config.auth.token,
          type: this.config.auth.type,
        },
      });
    }

    // Start heartbeat
    if (this.config.heartbeat.enabled) {
      this.startHeartbeat();
    }

    // Reestablish subscriptions
    this.reestablishSubscriptions();

    // Send queued messages
    this.flushMessageQueue();

    this.emit('open', event);
  }

  private handleClose(event: CloseEvent): void {
    this.log('Data management WebSocket closed:', event.code, event.reason);
    this.clearTimers();

    if (event.code === 1000) {
      // Normal closure
      this.setState(WebSocketState.CLOSED);
    } else {
      // Abnormal closure
      this.setState(WebSocketState.DISCONNECTED);

      if (this.config.reconnect.enabled && this.connectionAttempts < this.config.reconnect.maxAttempts) {
        this.scheduleReconnect();
      }
    }

    this.emit('close', event);
  }

  private handleError(event: Event): void {
    this.log('Data management WebSocket error:', event);
    this.setState(WebSocketState.ERROR);
    this.emit('error', event);
  }

  private handleMessage(event: MessageEvent): void {
    try {
      const message: WebSocketMessage = JSON.parse(event.data);
      this.log('Message received:', message.type);

      // Handle heartbeat response
      if (message.type === WebSocketMessageType.HEARTBEAT) {
        this.lastHeartbeat = new Date();
        this.calculateLatency(message);
        return;
      }

      // Route message to subscribers
      this.routeMessage(message);
      this.emit('message', message);
    } catch (error) {
      this.log('Failed to parse message:', error);
    }
  }

  private routeMessage(message: WebSocketMessage): void {
    for (const subscription of this.subscriptions.values()) {
      if (!subscription.active) continue;

      const typeMatches = Array.isArray(subscription.type)
        ? subscription.type.includes(message.type)
        : subscription.type === message.type;

      if (typeMatches && this.matchesFilters(message, subscription.filters)) {
        try {
          subscription.callback(message);
        } catch (error) {
          this.log('Subscription callback error:', error);
        }
      }
    }
  }

  private matchesFilters(message: WebSocketMessage, filters?: Record<string, any>): boolean {
    if (!filters) return true;

    for (const [key, value] of Object.entries(filters)) {
      const messageValue = this.getNestedValue(message, key);
      if (Array.isArray(value)) {
        if (!value.includes(messageValue)) return false;
      } else {
        if (messageValue !== value) return false;
      }
    }

    return true;
  }

  private getNestedValue(obj: any, path: string): any {
    return path.split('.').reduce((current, key) => current?.[key], obj);
  }

  private scheduleReconnect(): void {
    if (this.reconnectTimer) return;

    this.setState(WebSocketState.RECONNECTING);
    this.connectionAttempts++;

    const delay = this.config.reconnect.delay * Math.pow(this.config.reconnect.backoff, this.connectionAttempts - 1);

    this.log(`Scheduling reconnect attempt ${this.connectionAttempts} in ${delay}ms`);

    this.reconnectTimer = setTimeout(async () => {
      this.reconnectTimer = null;
      this.emit('reconnect', this.connectionAttempts);

      try {
        await this.connect();
      } catch (error) {
        this.log('Reconnect failed:', error);
        if (this.connectionAttempts < this.config.reconnect.maxAttempts) {
          this.scheduleReconnect();
        } else {
          this.setState(WebSocketState.ERROR);
        }
      }
    }, delay);
  }

  private startHeartbeat(): void {
    if (this.heartbeatTimer) return;

    this.heartbeatTimer = setInterval(() => {
      if (this.isConnected()) {
        this.send({
          type: WebSocketMessageType.HEARTBEAT,
          data: { timestamp: Date.now() },
        });
      }
    }, this.config.heartbeat.interval);
  }

  private calculateLatency(message: WebSocketMessage): void {
    if (message.data?.timestamp) {
      this.latency = Date.now() - message.data.timestamp;
    }
  }

  private reestablishSubscriptions(): void {
    // Re-send subscription requests for all active subscriptions
    for (const subscription of this.subscriptions.values()) {
      if (subscription.active) {
        this.send({
          type: WebSocketMessageType.CONNECT,
          data: {
            action: 'subscribe',
            types: Array.isArray(subscription.type) ? subscription.type : [subscription.type],
            filters: subscription.filters,
          },
        });
      }
    }
  }

  private flushMessageQueue(): void {
    while (this.messageQueue.length > 0 && this.isConnected()) {
      const message = this.messageQueue.shift()!;
      this.send(message);
    }
  }

  private clearTimers(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }

    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  private setState(newState: WebSocketState): void {
    if (this.state !== newState) {
      this.log(`State change: ${this.state} -> ${newState}`);
      this.state = newState;
      this.emit('stateChange', newState);
    }
  }

  private emit(event: string, data?: any): void {
    const listeners = this.eventListeners.get(event);
    if (listeners) {
      listeners.forEach(listener => {
        try {
          listener(data);
        } catch (error) {
          this.log('Event listener error:', error);
        }
      });
    }
  }

  private generateId(): string {
    return `dm_ws_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  private log(...args: any[]): void {
    if (this.config.debug) {
      console.log('[DataManagementWebSocket]', ...args);
    }
  }
}

// Singleton instance for data management
let dataManagementWebSocketInstance: DataManagementWebSocketService | null = null;

export const getDataManagementWebSocket = (config?: Partial<WebSocketConfig>): DataManagementWebSocketService => {
  if (!dataManagementWebSocketInstance) {
    dataManagementWebSocketInstance = new DataManagementWebSocketService(config);
  }
  return dataManagementWebSocketInstance;
};

export const createDataManagementWebSocket = (config: Partial<WebSocketConfig>): DataManagementWebSocketService => {
  return new DataManagementWebSocketService(config);
};
