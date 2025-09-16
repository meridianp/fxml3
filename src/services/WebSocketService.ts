/**
 * WebSocket Service for Real-Time Market Data
 *
 * Handles WebSocket connections with automatic reconnection,
 * message queuing, and performance monitoring.
 */

export interface WebSocketMessage {
  type: string;
  symbol?: string;
  price?: number;
  bid?: number;
  ask?: number;
  volume?: number;
  timestamp: string;
  [key: string]: any;
}

export interface WebSocketConfig {
  url: string;
  reconnectInterval: number;
  maxReconnectAttempts: number;
  heartbeatInterval: number;
}

export class WebSocketService {
  private ws: WebSocket | null = null;
  private config: WebSocketConfig;
  private reconnectCount = 0;
  private messageQueue: WebSocketMessage[] = [];
  private subscribers: Map<string, ((message: WebSocketMessage) => void)[]> = new Map();
  private connectionStatus: 'connecting' | 'connected' | 'disconnected' = 'disconnected';
  private heartbeatTimer?: NodeJS.Timeout;
  private reconnectTimer?: NodeJS.Timeout;
  private performanceMetrics = {
    messagesReceived: 0,
    averageLatency: 0,
    totalLatency: 0,
    lastMessageTime: 0
  };

  constructor(config: WebSocketConfig) {
    this.config = config;
  }

  connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      this.connectionStatus = 'connecting';
      this.ws = new WebSocket(this.config.url);

      this.ws.onopen = () => {
        this.connectionStatus = 'connected';
        this.reconnectCount = 0;
        this.startHeartbeat();
        this.flushMessageQueue();
        resolve();
      };

      this.ws.onmessage = (event) => {
        const message: WebSocketMessage = JSON.parse(event.data);
        this.updatePerformanceMetrics();
        this.notifySubscribers(message);
      };

      this.ws.onclose = () => {
        this.connectionStatus = 'disconnected';
        this.stopHeartbeat();
        this.handleReconnect();
      };

      this.ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        reject(error);
      };

      // Timeout connection attempt
      setTimeout(() => {
        if (this.connectionStatus === 'connecting') {
          reject(new Error('WebSocket connection timeout'));
        }
      }, 10000);
    });
  }

  disconnect(): void {
    if (this.ws) {
      this.ws.close();
    }
    this.stopHeartbeat();
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
    }
  }

  subscribe(messageType: string, callback: (message: WebSocketMessage) => void): () => void {
    if (!this.subscribers.has(messageType)) {
      this.subscribers.set(messageType, []);
    }
    this.subscribers.get(messageType)!.push(callback);

    // Return unsubscribe function
    return () => {
      const callbacks = this.subscribers.get(messageType);
      if (callbacks) {
        const index = callbacks.indexOf(callback);
        if (index > -1) {
          callbacks.splice(index, 1);
        }
      }
    };
  }

  send(message: WebSocketMessage): void {
    if (this.connectionStatus === 'connected' && this.ws) {
      this.ws.send(JSON.stringify(message));
    } else {
      this.messageQueue.push(message);
    }
  }

  getConnectionStatus(): string {
    return this.connectionStatus;
  }

  getPerformanceMetrics() {
    return { ...this.performanceMetrics };
  }

  private handleReconnect(): void {
    if (this.reconnectCount < this.config.maxReconnectAttempts) {
      this.reconnectCount++;
      this.reconnectTimer = setTimeout(() => {
        this.connect().catch(() => {
          // Retry will be handled by the next reconnect attempt
        });
      }, this.config.reconnectInterval);
    }
  }

  private startHeartbeat(): void {
    this.heartbeatTimer = setInterval(() => {
      if (this.connectionStatus === 'connected') {
        this.send({
          type: 'heartbeat',
          timestamp: new Date().toISOString()
        });
      }
    }, this.config.heartbeatInterval);
  }

  private stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
    }
  }

  private flushMessageQueue(): void {
    while (this.messageQueue.length > 0) {
      const message = this.messageQueue.shift();
      if (message && this.ws) {
        this.ws.send(JSON.stringify(message));
      }
    }
  }

  private notifySubscribers(message: WebSocketMessage): void {
    const callbacks = this.subscribers.get(message.type);
    if (callbacks) {
      callbacks.forEach(callback => {
        try {
          callback(message);
        } catch (error) {
          console.error('Error in WebSocket subscriber:', error);
        }
      });
    }
  }

  private updatePerformanceMetrics(): void {
    this.performanceMetrics.messagesReceived++;
    const now = performance.now();

    if (this.performanceMetrics.lastMessageTime > 0) {
      const latency = now - this.performanceMetrics.lastMessageTime;
      this.performanceMetrics.totalLatency += latency;
      this.performanceMetrics.averageLatency =
        this.performanceMetrics.totalLatency / this.performanceMetrics.messagesReceived;
    }

    this.performanceMetrics.lastMessageTime = now;
  }
}
