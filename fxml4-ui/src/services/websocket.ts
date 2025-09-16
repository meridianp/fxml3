/**
 * WebSocket service for real-time data streaming
 *
 * Handles real-time market data, trading signals, order updates,
 * and position changes from the FXML4 backend.
 */

import { WS_CONFIG } from '@/config/constants';
import type {
  MarketData,
  Order,
  Position,
  TradingSignal,
  WSMessage,
  MarketDataUpdate,
  OrderUpdate,
  PositionUpdate,
  SignalUpdate,
} from '@/types';

type EventCallback<T = any> = (data: T) => void;
type ErrorCallback = (error: Error) => void;

interface WebSocketEvents {
  // Connection events
  'connected': () => void;
  'disconnected': (reason: string) => void;
  'reconnecting': (attempt: number) => void;
  'reconnected': () => void;
  'error': (error: Error) => void;

  // Market data events
  'market_data': (data: MarketData) => void;
  'market_data_batch': (data: MarketData[]) => void;

  // Trading events
  'order_update': (order: Order) => void;
  'position_update': (position: Position) => void;
  'account_update': (account: any) => void;

  // Signal events
  'signal_update': (signal: TradingSignal) => void;
  'signal_batch': (signals: TradingSignal[]) => void;

  // System events
  'broker_status': (status: any) => void;
  'system_alert': (alert: any) => void;
  'model_status': (status: any) => void;
}

interface QueuedMessage {
  id: string;
  type: keyof WebSocketEvents;
  data: any;
  timestamp: number;
  sequence: number;
}

class WebSocketService {
  private socket: WebSocket | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = WS_CONFIG.reconnectAttempts;
  private reconnectTimer: NodeJS.Timeout | null = null;
  private heartbeatTimer: NodeJS.Timeout | null = null;
  private isConnected = false;
  private subscriptions = new Set<string>();
  private eventListeners = new Map<keyof WebSocketEvents, EventCallback[]>();

  // Message replay functionality
  private lastSequenceNumber = 0;
  private messageQueue: QueuedMessage[] = [];
  private maxQueueSize = 1000; // Maximum messages to keep in queue
  private disconnectedAt: number | null = null;

  constructor() {
    this.setupEventListeners();
  }

  private setupEventListeners() {
    // Initialize event listener arrays
    const events: (keyof WebSocketEvents)[] = [
      'connected', 'disconnected', 'reconnecting', 'reconnected', 'error',
      'market_data', 'market_data_batch', 'order_update', 'position_update',
      'account_update', 'signal_update', 'signal_batch', 'broker_status',
      'system_alert', 'model_status'
    ];

    events.forEach(event => {
      this.eventListeners.set(event, []);
    });
  }

  // Connection management
  connect(token?: string): Promise<void> {
    return new Promise((resolve, reject) => {
      if (this.socket && this.isConnected) {
        resolve();
        return;
      }

      try {
        // Convert ws:// to http:// or wss:// to https:// for proper URL handling
        const wsUrl = WS_CONFIG.url.replace(/^http/, 'ws');
        this.socket = new WebSocket(wsUrl);

        this.socket.onopen = () => {
          this.isConnected = true;
          this.reconnectAttempts = 0;
          this.startHeartbeat();
          this.resubscribe();
          this.emit('connected');
          resolve();
        };

        this.socket.onclose = (event) => {
          this.isConnected = false;
          this.disconnectedAt = Date.now();
          this.stopHeartbeat();
          const reason = event.reason || `Connection closed (${event.code})`;
          this.emit('disconnected', reason);

          console.warn('WebSocket disconnected:', reason, 'at', new Date(this.disconnectedAt));

          // Attempt reconnection unless it was a normal closure
          if (event.code !== 1000) {
            this.attemptReconnection();
          }
        };

        this.socket.onerror = (error) => {
          const wsError = new Error('WebSocket connection failed');
          this.emit('error', wsError);
          reject(wsError);
        };

        this.socket.onmessage = (event) => {
          try {
            const message = JSON.parse(event.data);
            this.handleMessage(message);
          } catch (error) {
            console.error('Failed to parse WebSocket message:', error);
          }
        };

      } catch (error) {
        reject(error);
      }
    });
  }

  disconnect(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }

    this.stopHeartbeat();

    if (this.socket) {
      this.socket.close(1000, 'Client disconnect');
      this.socket = null;
    }

    this.isConnected = false;
    this.subscriptions.clear();
  }

  private handleMessage(message: any): void {
    // Handle different message types from the WebSocket
    switch (message.type) {
      case 'market_data':
        this.emit('market_data', message.data);
        break;
      case 'market_data_batch':
        this.emit('market_data_batch', message.data);
        break;
      case 'order_update':
        this.emit('order_update', message.data);
        break;
      case 'position_update':
        this.emit('position_update', message.data);
        break;
      case 'account_update':
        this.emit('account_update', message.data);
        break;
      case 'signal_update':
        this.emit('signal_update', message.data);
        break;
      case 'signal_batch':
        this.emit('signal_batch', message.data);
        break;
      case 'broker_status':
        this.emit('broker_status', message.data);
        break;
      case 'system_alert':
        this.emit('system_alert', message.data);
        break;
      case 'model_status':
        this.emit('model_status', message.data);
        break;
      case 'pong':
        // Heartbeat response received
        break;
      default:
        console.log('Unknown message type:', message.type);
    }
  }

  private attemptReconnection(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      this.emit('error', new Error('Max reconnection attempts reached'));
      return;
    }

    this.reconnectAttempts++;
    this.emit('reconnecting', this.reconnectAttempts);

    this.reconnectTimer = setTimeout(() => {
      this.connect()
        .then(() => {
          this.requestMessageReplay();
          this.emit('reconnected');
        })
        .catch((error) => {
          console.error('Reconnection failed:', error);
          this.attemptReconnection();
        });
    }, WS_CONFIG.reconnectInterval * this.reconnectAttempts);
  }

  private startHeartbeat(): void {
    this.heartbeatTimer = setInterval(() => {
      if (this.socket && this.isConnected && this.socket.readyState === WebSocket.OPEN) {
        this.socket.send(JSON.stringify({ type: 'ping' }));
      }
    }, WS_CONFIG.heartbeatInterval);
  }

  private stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  private resubscribe(): void {
    // Resubscribe to all previously subscribed channels
    this.subscriptions.forEach(subscription => {
      if (this.socket && this.socket.readyState === WebSocket.OPEN) {
        this.socket.send(JSON.stringify({ type: 'subscribe', channel: subscription }));
      }
    });
  }

  private requestMessageReplay(): void {
    if (!this.socket || !this.disconnectedAt || this.socket.readyState !== WebSocket.OPEN) return;

    const reconnectedAt = Date.now();
    const disconnectionDuration = reconnectedAt - this.disconnectedAt;

    console.log(`Requesting message replay for ${disconnectionDuration}ms disconnection period`);
    console.log(`Last sequence: ${this.lastSequenceNumber}, disconnected at: ${new Date(this.disconnectedAt)}`);

    // Request message replay from server
    this.socket.send(JSON.stringify({
      type: 'replay_messages',
      last_sequence: this.lastSequenceNumber,
      disconnected_at: this.disconnectedAt,
      reconnected_at: reconnectedAt,
      subscriptions: Array.from(this.subscriptions)
    }));

    // Clear disconnection timestamp
    this.disconnectedAt = null;
  }

  private processQueuedMessage(message: QueuedMessage): void {
    // Check if this message is newer than our last processed sequence
    if (message.sequence <= this.lastSequenceNumber) {
      console.debug('Ignoring duplicate/old message:', message.sequence);
      return;
    }

    // Update last sequence number
    this.lastSequenceNumber = message.sequence;

    // Add to message queue for replay protection
    this.messageQueue.push(message);

    // Trim queue if it gets too large
    if (this.messageQueue.length > this.maxQueueSize) {
      this.messageQueue = this.messageQueue.slice(-this.maxQueueSize);
    }

    // Emit the message event
    this.emit(message.type, message.data);
  }

  private handleReplayedMessages(messages: QueuedMessage[]): void {
    console.log(`Processing ${messages.length} replayed messages`);

    // Sort messages by sequence number to ensure proper order
    const sortedMessages = messages.sort((a, b) => a.sequence - b.sequence);

    // Process each message
    sortedMessages.forEach(message => {
      this.processQueuedMessage(message);
    });

    console.log(`Replay complete. Current sequence: ${this.lastSequenceNumber}`);
  }

  // Subscription management
  subscribeToMarketData(symbols: string[]): void {
    const subscription = `market_data:${symbols.join(',')}`;
    this.subscriptions.add(subscription);

    if (this.socket && this.isConnected && this.socket.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify({
        type: 'subscribe',
        channel: 'market_data',
        symbols: symbols,
      }));
    }
  }

  subscribeToSignals(models?: string[]): void {
    const subscription = `signals${models ? ':' + models.join(',') : ''}`;
    this.subscriptions.add(subscription);

    if (this.socket && this.isConnected && this.socket.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify({
        type: 'subscribe',
        channel: 'signals',
        models: models,
      }));
    }
  }

  subscribeToTradingUpdates(): void {
    const subscription = 'trading_updates';
    this.subscriptions.add(subscription);

    if (this.socket && this.isConnected && this.socket.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify({
        type: 'subscribe',
        channel: 'trading_updates',
      }));
    }
  }

  subscribeToSystemUpdates(): void {
    const subscription = 'system_updates';
    this.subscriptions.add(subscription);

    if (this.socket && this.isConnected && this.socket.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify({
        type: 'subscribe',
        channel: 'system_updates',
      }));
    }
  }

  unsubscribe(channel: string): void {
    this.subscriptions.delete(channel);

    if (this.socket && this.isConnected && this.socket.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify({ type: 'unsubscribe', channel }));
    }
  }

  // Event management
  on<K extends keyof WebSocketEvents>(
    event: K,
    callback: WebSocketEvents[K]
  ): () => void {
    const listeners = this.eventListeners.get(event) || [];
    listeners.push(callback as EventCallback);
    this.eventListeners.set(event, listeners);

    // Return unsubscribe function
    return () => {
      const currentListeners = this.eventListeners.get(event) || [];
      const index = currentListeners.indexOf(callback as EventCallback);
      if (index > -1) {
        currentListeners.splice(index, 1);
      }
    };
  }

  off<K extends keyof WebSocketEvents>(
    event: K,
    callback?: WebSocketEvents[K]
  ): void {
    if (!callback) {
      // Remove all listeners for event
      this.eventListeners.set(event, []);
      return;
    }

    const listeners = this.eventListeners.get(event) || [];
    const index = listeners.indexOf(callback as EventCallback);
    if (index > -1) {
      listeners.splice(index, 1);
    }
  }

  private emit<K extends keyof WebSocketEvents>(
    event: K,
    ...args: Parameters<WebSocketEvents[K]>
  ): void {
    const listeners = this.eventListeners.get(event) || [];
    listeners.forEach(callback => {
      try {
        (callback as any)(...args);
      } catch (error) {
        console.error(`Error in WebSocket event handler for ${event}:`, error);
      }
    });
  }

  // Utility methods
  isSocketConnected(): boolean {
    return this.isConnected && this.socket?.readyState === WebSocket.OPEN;
  }

  getConnectionState(): string {
    if (!this.socket) return 'disconnected';
    if (this.isConnected) return 'connected';
    if (this.reconnectAttempts > 0) return 'reconnecting';
    return 'connecting';
  }

  getSubscriptions(): string[] {
    return Array.from(this.subscriptions);
  }

  // Direct emit methods for specific actions
  requestMarketData(symbol: string, timeframe: string): void {
    if (this.socket && this.isConnected && this.socket.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify({
        type: 'request_market_data',
        symbol,
        timeframe
      }));
    }
  }

  requestSignalGeneration(symbol: string, modelName?: string): void {
    if (this.socket && this.isConnected && this.socket.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify({
        type: 'request_signal',
        symbol,
        model_name: modelName
      }));
    }
  }
}

// Export singleton instance
export const wsService = new WebSocketService();
export default wsService;
