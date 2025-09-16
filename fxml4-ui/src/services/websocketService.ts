/**
 * Phase 7 - Enhanced WebSocket Service
 * 
 * Comprehensive real-time data integration service that connects to all
 * Phase 6 backend systems including trading, compliance, and risk management.
 */

import { io, Socket } from 'socket.io-client';

// WebSocket Event Types
export interface MarketDataEvent {
  type: 'market_data';
  symbol: string;
  bid: number;
  ask: number;
  timestamp: string;
  volume?: number;
  spread?: number;
}

export interface TradeEvent {
  type: 'trade_update';
  trade_id: string;
  symbol: string;
  side: 'buy' | 'sell';
  size: number;
  price: number;
  status: 'pending' | 'filled' | 'cancelled' | 'rejected';
  timestamp: string;
  pnl?: number;
}

export interface PositionEvent {
  type: 'position_update';
  position_id: string;
  symbol: string;
  side: 'buy' | 'sell';
  size: number;
  entry_price: number;
  current_price: number;
  unrealized_pnl: number;
  timestamp: string;
}

export interface ComplianceEvent {
  type: 'compliance_alert';
  alert_id: string;
  alert_type: 'surveillance' | 'risk_limit' | 'regulatory';
  severity: 'low' | 'medium' | 'high' | 'critical';
  title: string;
  description: string;
  timestamp: string;
  jurisdiction?: string;
  requires_action?: boolean;
}

export interface RiskEvent {
  type: 'risk_update';
  risk_type: 'limit_breach' | 'var_exceedance' | 'concentration_risk' | 'correlation_spike';
  current_value: number;
  limit_value?: number;
  breach_percentage?: number;
  severity: 'low' | 'medium' | 'high' | 'critical';
  timestamp: string;
  auto_action?: string;
}

export interface SystemEvent {
  type: 'system_status';
  component: 'trading' | 'compliance' | 'risk' | 'data_feed' | 'broker_connection';
  status: 'online' | 'offline' | 'degraded' | 'maintenance';
  message?: string;
  timestamp: string;
}

export interface SignalEvent {
  type: 'trading_signal';
  signal_id: string;
  symbol: string;
  signal_type: 'buy' | 'sell' | 'close';
  confidence: number;
  price_target?: number;
  stop_loss?: number;
  reasoning: string;
  timestamp: string;
  model_source: string;
}

export type WebSocketEvent = 
  | MarketDataEvent 
  | TradeEvent 
  | PositionEvent 
  | ComplianceEvent 
  | RiskEvent 
  | SystemEvent 
  | SignalEvent;

// WebSocket Service Configuration
interface WebSocketConfig {
  url: string;
  reconnectAttempts: number;
  reconnectDelay: number;
  heartbeatInterval: number;
  maxHeartbeatMisses: number;
}

// Subscription Types
export type SubscriptionType = 
  | 'market_data'
  | 'trading_updates'
  | 'compliance_alerts'
  | 'risk_updates'
  | 'system_status'
  | 'trading_signals';

// Event Handler Type
export type EventHandler<T = WebSocketEvent> = (event: T) => void;

// Connection Status
export type ConnectionStatus = 'disconnected' | 'connecting' | 'connected' | 'reconnecting' | 'error';

class EnhancedWebSocketService {
  private socket: Socket | null = null;
  private config: WebSocketConfig;
  private eventHandlers: Map<string, Set<EventHandler>> = new Map();
  private subscriptions: Set<SubscriptionType> = new Set();
  private connectionStatus: ConnectionStatus = 'disconnected';
  private statusHandlers: Set<(status: ConnectionStatus) => void> = new Set();
  private reconnectAttempts = 0;
  private heartbeatInterval: NodeJS.Timeout | null = null;
  private lastHeartbeat: number = Date.now();
  private missedHeartbeats = 0;
  private isReconnecting = false;

  constructor(config?: Partial<WebSocketConfig>) {
    this.config = {
      url: process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8001',
      reconnectAttempts: 5,
      reconnectDelay: 2000,
      heartbeatInterval: 30000, // 30 seconds
      maxHeartbeatMisses: 3,
      ...config
    };
  }

  /**
   * Connect to the WebSocket server
   */
  connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      if (this.socket?.connected) {
        resolve();
        return;
      }

      this.setConnectionStatus('connecting');

      try {
        this.socket = io(this.config.url, {
          transports: ['websocket', 'polling'],
          timeout: 10000,
          forceNew: true,
          reconnection: false, // We handle reconnection manually
          auth: {
            // Add authentication token if available
            token: localStorage.getItem('auth_token') || undefined
          }
        });

        this.setupEventListeners();
        
        // Set up connection timeout
        const connectionTimeout = setTimeout(() => {
          this.socket?.disconnect();
          reject(new Error('Connection timeout'));
        }, 10000);

        this.socket.on('connect', () => {
          clearTimeout(connectionTimeout);
          this.setConnectionStatus('connected');
          this.reconnectAttempts = 0;
          this.startHeartbeat();
          this.resubscribeAll();
          resolve();
        });

        this.socket.on('connect_error', (error: Error) => {
          clearTimeout(connectionTimeout);
          console.error('WebSocket connection error:', error);
          this.setConnectionStatus('error');
          reject(error);
        });

      } catch (error) {
        this.setConnectionStatus('error');
        reject(error);
      }
    });
  }

  /**
   * Disconnect from the WebSocket server
   */
  disconnect(): void {
    if (this.socket) {
      this.socket.disconnect();
      this.socket = null;
    }
    this.stopHeartbeat();
    this.setConnectionStatus('disconnected');
    this.subscriptions.clear();
  }

  /**
   * Subscribe to specific event types
   */
  subscribe<T extends WebSocketEvent>(
    eventType: SubscriptionType, 
    handler: EventHandler<T>,
    symbols?: string[]
  ): void {
    // Add handler to local registry
    if (!this.eventHandlers.has(eventType)) {
      this.eventHandlers.set(eventType, new Set());
    }
    this.eventHandlers.get(eventType)!.add(handler as EventHandler);

    // Add to subscriptions
    this.subscriptions.add(eventType);

    // Send subscription to server if connected
    if (this.socket?.connected) {
      this.socket.emit('subscribe', {
        type: eventType,
        symbols: symbols || []
      });
    }
  }

  /**
   * Unsubscribe from event types
   */
  unsubscribe(eventType: SubscriptionType, handler?: EventHandler): void {
    const handlers = this.eventHandlers.get(eventType);
    if (handlers) {
      if (handler) {
        handlers.delete(handler);
      } else {
        handlers.clear();
      }
    }

    // Remove from subscriptions if no handlers left
    if (!handlers || handlers.size === 0) {
      this.subscriptions.delete(eventType);
      
      // Send unsubscribe to server if connected
      if (this.socket?.connected) {
        this.socket.emit('unsubscribe', { type: eventType });
      }
    }
  }

  /**
   * Subscribe to connection status changes
   */
  onConnectionStatusChange(handler: (status: ConnectionStatus) => void): void {
    this.statusHandlers.add(handler);
  }

  /**
   * Unsubscribe from connection status changes
   */
  offConnectionStatusChange(handler: (status: ConnectionStatus) => void): void {
    this.statusHandlers.delete(handler);
  }

  /**
   * Get current connection status
   */
  getConnectionStatus(): ConnectionStatus {
    return this.connectionStatus;
  }

  /**
   * Check if connected
   */
  isConnected(): boolean {
    return this.connectionStatus === 'connected' && this.socket?.connected === true;
  }

  /**
   * Send a message to the server
   */
  send(event: string, data: any): void {
    if (this.socket?.connected) {
      this.socket.emit(event, data);
    } else {
      console.warn('Cannot send message: WebSocket not connected');
    }
  }

  /**
   * Request historical data
   */
  requestHistoricalData(
    symbol: string, 
    timeframe: string, 
    startDate: string, 
    endDate: string
  ): Promise<any> {
    return new Promise((resolve, reject) => {
      if (!this.socket?.connected) {
        reject(new Error('WebSocket not connected'));
        return;
      }

      const requestId = `hist_${Date.now()}`;
      
      // Set up one-time response handler
      const responseHandler = (data: any) => {
        if (data.requestId === requestId) {
          this.socket!.off('historical_data_response', responseHandler);
          if (data.error) {
            reject(new Error(data.error));
          } else {
            resolve(data.data);
          }
        }
      };

      this.socket.on('historical_data_response', responseHandler);
      
      // Send request
      this.socket.emit('historical_data_request', {
        requestId,
        symbol,
        timeframe,
        startDate,
        endDate
      });

      // Set timeout
      setTimeout(() => {
        this.socket!.off('historical_data_response', responseHandler);
        reject(new Error('Historical data request timeout'));
      }, 30000);
    });
  }

  /**
   * Place a trading order
   */
  placeOrder(order: {
    symbol: string;
    side: 'buy' | 'sell';
    type: 'market' | 'limit' | 'stop';
    size: number;
    price?: number;
    stopLoss?: number;
    takeProfit?: number;
  }): Promise<any> {
    return new Promise((resolve, reject) => {
      if (!this.socket?.connected) {
        reject(new Error('WebSocket not connected'));
        return;
      }

      const orderId = `order_${Date.now()}`;
      
      // Set up response handler
      const responseHandler = (data: any) => {
        if (data.orderId === orderId) {
          this.socket!.off('order_response', responseHandler);
          if (data.error) {
            reject(new Error(data.error));
          } else {
            resolve(data);
          }
        }
      };

      this.socket.on('order_response', responseHandler);
      
      // Send order
      this.socket.emit('place_order', {
        orderId,
        ...order
      });

      // Set timeout
      setTimeout(() => {
        this.socket!.off('order_response', responseHandler);
        reject(new Error('Order placement timeout'));
      }, 10000);
    });
  }

  private setupEventListeners(): void {
    if (!this.socket) return;

    // Handle disconnection
    this.socket.on('disconnect', (reason: string) => {
      console.log('WebSocket disconnected:', reason);
      this.stopHeartbeat();
      this.setConnectionStatus('disconnected');
      
      // Attempt reconnection if not intentional
      if (reason !== 'io client disconnect' && !this.isReconnecting) {
        this.attemptReconnection();
      }
    });

    // Handle errors
    this.socket.on('error', (error: Error) => {
      console.error('WebSocket error:', error);
      this.setConnectionStatus('error');
    });

    // Handle all event types
    this.socket.on('market_data', (data: MarketDataEvent) => {
      this.emit('market_data', data);
    });

    this.socket.on('trade_update', (data: TradeEvent) => {
      this.emit('trading_updates', data);
    });

    this.socket.on('position_update', (data: PositionEvent) => {
      this.emit('trading_updates', data);
    });

    this.socket.on('compliance_alert', (data: ComplianceEvent) => {
      this.emit('compliance_alerts', data);
    });

    this.socket.on('risk_update', (data: RiskEvent) => {
      this.emit('risk_updates', data);
    });

    this.socket.on('system_status', (data: SystemEvent) => {
      this.emit('system_status', data);
    });

    this.socket.on('trading_signal', (data: SignalEvent) => {
      this.emit('trading_signals', data);
    });

    // Handle heartbeat
    this.socket.on('heartbeat', () => {
      this.lastHeartbeat = Date.now();
      this.missedHeartbeats = 0;
    });

    // Handle authentication challenges
    this.socket.on('auth_required', () => {
      const token = localStorage.getItem('auth_token');
      if (token) {
        this.socket!.emit('authenticate', { token });
      }
    });

    this.socket.on('auth_success', () => {
      console.log('WebSocket authentication successful');
    });

    this.socket.on('auth_failed', () => {
      console.error('WebSocket authentication failed');
      this.setConnectionStatus('error');
    });
  }

  private emit(eventType: string, data: WebSocketEvent): void {
    const handlers = this.eventHandlers.get(eventType);
    if (handlers) {
      handlers.forEach(handler => {
        try {
          handler(data);
        } catch (error) {
          console.error('Error in event handler:', error);
        }
      });
    }
  }

  private setConnectionStatus(status: ConnectionStatus): void {
    if (this.connectionStatus !== status) {
      this.connectionStatus = status;
      this.statusHandlers.forEach(handler => {
        try {
          handler(status);
        } catch (error) {
          console.error('Error in status handler:', error);
        }
      });
    }
  }

  private attemptReconnection(): void {
    if (this.isReconnecting || this.reconnectAttempts >= this.config.reconnectAttempts) {
      return;
    }

    this.isReconnecting = true;
    this.setConnectionStatus('reconnecting');
    this.reconnectAttempts++;

    const delay = this.config.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);
    
    setTimeout(async () => {
      try {
        await this.connect();
        this.isReconnecting = false;
      } catch (error) {
        this.isReconnecting = false;
        console.error(`Reconnection attempt ${this.reconnectAttempts} failed:`, error);
        
        if (this.reconnectAttempts < this.config.reconnectAttempts) {
          this.attemptReconnection();
        } else {
          this.setConnectionStatus('error');
        }
      }
    }, delay);
  }

  private resubscribeAll(): void {
    if (!this.socket?.connected) return;

    this.subscriptions.forEach(eventType => {
      this.socket!.emit('subscribe', { type: eventType });
    });
  }

  private startHeartbeat(): void {
    this.stopHeartbeat();
    this.lastHeartbeat = Date.now();
    this.missedHeartbeats = 0;

    this.heartbeatInterval = setInterval(() => {
      const now = Date.now();
      const timeSinceLastHeartbeat = now - this.lastHeartbeat;

      if (timeSinceLastHeartbeat > this.config.heartbeatInterval) {
        this.missedHeartbeats++;
        
        if (this.missedHeartbeats >= this.config.maxHeartbeatMisses) {
          console.warn('Too many missed heartbeats, reconnecting...');
          this.socket?.disconnect();
          return;
        }
      }

      // Send heartbeat
      if (this.socket?.connected) {
        this.socket.emit('heartbeat', { timestamp: now });
      }
    }, this.config.heartbeatInterval);
  }

  private stopHeartbeat(): void {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }
  }
}

// Create singleton instance
const websocketService = new EnhancedWebSocketService();

// Export service instance and types
export default websocketService;
export { EnhancedWebSocketService };
export type { WebSocketConfig, SubscriptionType, EventHandler, ConnectionStatus };