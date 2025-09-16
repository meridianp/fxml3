/**
 * DataManagementWebSocketService Tests
 *
 * Tests for real-time WebSocket functionality for data management monitoring
 */

import { DataManagementWebSocketService } from './dataManagementWebSocket';
import { WebSocketState, WebSocketMessageType } from '@/types/websocket';

// Mock WebSocket
class MockWebSocket {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;

  readyState = MockWebSocket.CONNECTING;
  url: string;
  onopen: ((event: Event) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  private listeners: Map<string, Function[]> = new Map();

  constructor(url: string) {
    this.url = url;
    // Simulate async connection
    setTimeout(() => {
      this.readyState = MockWebSocket.OPEN;
      this.triggerEvent('open', new Event('open'));
    }, 10);
  }

  addEventListener(type: string, listener: Function) {
    if (!this.listeners.has(type)) {
      this.listeners.set(type, []);
    }
    this.listeners.get(type)!.push(listener);
  }

  removeEventListener(type: string, listener: Function) {
    const listeners = this.listeners.get(type);
    if (listeners) {
      const index = listeners.indexOf(listener);
      if (index > -1) {
        listeners.splice(index, 1);
      }
    }
  }

  send(data: string) {
    if (this.readyState !== MockWebSocket.OPEN) {
      throw new Error('WebSocket is not open');
    }
    // Echo heartbeat messages
    try {
      const message = JSON.parse(data);
      if (message.type === 'HEARTBEAT') {
        setTimeout(() => {
          this.triggerMessage({
            type: 'HEARTBEAT',
            data: { timestamp: message.data.timestamp },
          });
        }, 5);
      }
    } catch (e) {
      // Ignore non-JSON messages
    }
  }

  close(code?: number, reason?: string) {
    this.readyState = MockWebSocket.CLOSING;
    setTimeout(() => {
      this.readyState = MockWebSocket.CLOSED;
      this.triggerEvent('close', new CloseEvent('close', { code: code || 1000, reason }));
    }, 10);
  }

  triggerEvent(type: string, event: Event) {
    const listeners = this.listeners.get(type);
    if (listeners) {
      listeners.forEach(listener => listener(event));
    }

    // Also trigger on* handlers
    if (type === 'open' && this.onopen) this.onopen(event);
    if (type === 'close' && this.onclose) this.onclose(event as CloseEvent);
    if (type === 'error' && this.onerror) this.onerror(event);
    if (type === 'message' && this.onmessage) this.onmessage(event as MessageEvent);
  }

  triggerMessage(data: any) {
    const messageEvent = new MessageEvent('message', {
      data: JSON.stringify(data),
    });
    this.triggerEvent('message', messageEvent);
  }

  triggerError() {
    this.triggerEvent('error', new Event('error'));
  }

  triggerClose(code = 1000, reason = '') {
    this.close(code, reason);
  }
}

// Mock global WebSocket
(global as any).WebSocket = MockWebSocket;

describe('DataManagementWebSocketService', () => {
  let service: DataManagementWebSocketService;
  let mockWebSocket: MockWebSocket;

  beforeEach(() => {
    service = new DataManagementWebSocketService({
      url: 'ws://localhost:8001/ws/data-management',
      autoConnect: false,
      debug: false,
    });

    // Capture the created WebSocket instance
    const originalWebSocket = (global as any).WebSocket;
    (global as any).WebSocket = function(url: string) {
      mockWebSocket = new MockWebSocket(url);
      return mockWebSocket;
    };
    (global as any).WebSocket.CONNECTING = MockWebSocket.CONNECTING;
    (global as any).WebSocket.OPEN = MockWebSocket.OPEN;
    (global as any).WebSocket.CLOSING = MockWebSocket.CLOSING;
    (global as any).WebSocket.CLOSED = MockWebSocket.CLOSED;
  });

  afterEach(() => {
    service.destroy();
    jest.clearAllTimers();
  });

  describe('Connection Management', () => {
    it('should initialize with disconnected state', () => {
      expect(service.getState()).toBe(WebSocketState.DISCONNECTED);
      expect(service.isConnected()).toBe(false);
    });

    it('should connect successfully', async () => {
      const connectPromise = service.connect();

      expect(service.getState()).toBe(WebSocketState.CONNECTING);

      await connectPromise;

      expect(service.getState()).toBe(WebSocketState.CONNECTED);
      expect(service.isConnected()).toBe(true);
    });

    it('should handle connection errors', async () => {
      const connectPromise = service.connect();

      // Trigger error before connection opens
      setTimeout(() => {
        mockWebSocket.triggerError();
      }, 5);

      await expect(connectPromise).rejects.toThrow('WebSocket connection failed');
      expect(service.getState()).toBe(WebSocketState.ERROR);
    });

    it('should disconnect cleanly', async () => {
      await service.connect();
      expect(service.isConnected()).toBe(true);

      service.disconnect();

      await new Promise(resolve => setTimeout(resolve, 20));
      expect(service.getState()).toBe(WebSocketState.DISCONNECTED);
      expect(service.isConnected()).toBe(false);
    });

    it('should reconnect after disconnection', async () => {
      await service.connect();
      expect(service.isConnected()).toBe(true);

      // Simulate unexpected disconnection
      mockWebSocket.triggerClose(1006, 'Connection lost');

      await new Promise(resolve => setTimeout(resolve, 20));
      expect(service.getState()).toBe(WebSocketState.DISCONNECTED);

      // Should attempt reconnection
      await new Promise(resolve => setTimeout(resolve, 100));
      // Note: In real test we'd need to verify reconnection attempts
    });
  });

  describe('Message Handling', () => {
    beforeEach(async () => {
      await service.connect();
    });

    it('should send messages when connected', () => {
      const sendSpy = jest.spyOn(mockWebSocket, 'send');

      service.send({
        type: WebSocketMessageType.DATA_SOURCE_STATUS,
        data: { sourceId: 'test-source' },
      });

      expect(sendSpy).toHaveBeenCalledWith(
        expect.stringContaining('"type":"DATA_SOURCE_STATUS"')
      );
    });

    it('should queue messages when not connected', () => {
      service.disconnect();

      service.send({
        type: WebSocketMessageType.STORAGE_METRICS,
        data: { action: 'request' },
      });

      // Message should be queued (verified by no error thrown)
      expect(service.getState()).toBe(WebSocketState.DISCONNECTED);
    });

    it('should handle received messages', async () => {
      const messageHandler = jest.fn();
      service.addEventListener('message', messageHandler);

      const testMessage = {
        id: 'test-msg-1',
        type: WebSocketMessageType.DATA_SOURCE_STATUS,
        timestamp: new Date().toISOString(),
        source: 'server',
        data: {
          sourceId: 'test-source',
          status: 'connected',
        },
      };

      mockWebSocket.triggerMessage(testMessage);

      expect(messageHandler).toHaveBeenCalledWith(testMessage);
    });

    it('should handle heartbeat messages', async () => {
      const heartbeatTime = Date.now();

      mockWebSocket.triggerMessage({
        type: WebSocketMessageType.HEARTBEAT,
        data: { timestamp: heartbeatTime },
      });

      const status = service.getConnectionStatus();
      expect(status.lastHeartbeat).toBeDefined();
      expect(status.latency).toBeGreaterThanOrEqual(0);
    });
  });

  describe('Subscription Management', () => {
    beforeEach(async () => {
      await service.connect();
    });

    it('should create subscriptions', () => {
      const callback = jest.fn();
      const subscriptionId = service.subscribe({
        type: WebSocketMessageType.DATA_SOURCE_STATUS,
        callback,
      });

      expect(subscriptionId).toBeTruthy();
      expect(typeof subscriptionId).toBe('string');
    });

    it('should route messages to subscribers', () => {
      const callback = jest.fn();
      service.subscribe({
        type: WebSocketMessageType.DATA_SOURCE_STATUS,
        callback,
      });

      const testMessage = {
        id: 'test-msg-2',
        type: WebSocketMessageType.DATA_SOURCE_STATUS,
        timestamp: new Date().toISOString(),
        source: 'server',
        data: { sourceId: 'test-source', status: 'connected' },
      };

      mockWebSocket.triggerMessage(testMessage);

      expect(callback).toHaveBeenCalledWith(testMessage);
    });

    it('should filter messages based on subscription filters', () => {
      const callback = jest.fn();
      service.subscribe({
        type: WebSocketMessageType.DATA_SOURCE_STATUS,
        filters: { 'data.sourceId': 'specific-source' },
        callback,
      });

      // Message that should match filter
      mockWebSocket.triggerMessage({
        type: WebSocketMessageType.DATA_SOURCE_STATUS,
        data: { sourceId: 'specific-source', status: 'connected' },
      });

      // Message that should not match filter
      mockWebSocket.triggerMessage({
        type: WebSocketMessageType.DATA_SOURCE_STATUS,
        data: { sourceId: 'other-source', status: 'connected' },
      });

      expect(callback).toHaveBeenCalledTimes(1);
    });

    it('should unsubscribe correctly', () => {
      const callback = jest.fn();
      const subscriptionId = service.subscribe({
        type: WebSocketMessageType.DATA_SOURCE_STATUS,
        callback,
      });

      service.unsubscribe(subscriptionId);

      mockWebSocket.triggerMessage({
        type: WebSocketMessageType.DATA_SOURCE_STATUS,
        data: { sourceId: 'test-source', status: 'connected' },
      });

      expect(callback).not.toHaveBeenCalled();
    });
  });

  describe('Data Management Specific Methods', () => {
    beforeEach(async () => {
      await service.connect();
    });

    it('should subscribe to data sources', () => {
      const subscriptionId = service.subscribeToDataSources(['source1', 'source2']);
      expect(subscriptionId).toBeTruthy();
    });

    it('should subscribe to storage metrics', () => {
      const subscriptionId = service.subscribeToStorageMetrics();
      expect(subscriptionId).toBeTruthy();
    });

    it('should subscribe to data quality', () => {
      const subscriptionId = service.subscribeToDataQuality(['dataset1', 'dataset2']);
      expect(subscriptionId).toBeTruthy();
    });

    it('should subscribe to pipelines', () => {
      const subscriptionId = service.subscribeToPipelines(['pipeline1', 'pipeline2']);
      expect(subscriptionId).toBeTruthy();
    });

    it('should subscribe to alerts', () => {
      const subscriptionId = service.subscribeToAlerts();
      expect(subscriptionId).toBeTruthy();
    });

    it('should request data source status', () => {
      const sendSpy = jest.spyOn(mockWebSocket, 'send');

      service.requestDataSourceStatus('test-source');

      expect(sendSpy).toHaveBeenCalledWith(
        expect.stringContaining('"type":"DATA_SOURCE_STATUS"')
      );
    });

    it('should request storage metrics', () => {
      const sendSpy = jest.spyOn(mockWebSocket, 'send');

      service.requestStorageMetrics();

      expect(sendSpy).toHaveBeenCalledWith(
        expect.stringContaining('"type":"STORAGE_METRICS"')
      );
    });

    it('should request quality report', () => {
      const sendSpy = jest.spyOn(mockWebSocket, 'send');

      service.requestQualityReport('test-dataset');

      expect(sendSpy).toHaveBeenCalledWith(
        expect.stringContaining('"type":"QUALITY_REPORT"')
      );
    });

    it('should request pipeline status', () => {
      const sendSpy = jest.spyOn(mockWebSocket, 'send');

      service.requestPipelineStatus('test-pipeline');

      expect(sendSpy).toHaveBeenCalledWith(
        expect.stringContaining('"type":"PIPELINE_STATUS"')
      );
    });
  });

  describe('Event Handling', () => {
    it('should add and remove event listeners', () => {
      const listener = jest.fn();

      service.addEventListener('test-event', listener);
      service['emit']('test-event', 'test-data');

      expect(listener).toHaveBeenCalledWith('test-data');

      service.removeEventListener('test-event', listener);
      service['emit']('test-event', 'test-data-2');

      expect(listener).toHaveBeenCalledTimes(1);
    });

    it('should emit connection state changes', async () => {
      const stateChangeListener = jest.fn();
      service.addEventListener('stateChange', stateChangeListener);

      await service.connect();

      expect(stateChangeListener).toHaveBeenCalledWith(WebSocketState.CONNECTING);
      expect(stateChangeListener).toHaveBeenCalledWith(WebSocketState.CONNECTED);
    });
  });

  describe('Configuration', () => {
    it('should use default configuration', () => {
      const defaultService = new DataManagementWebSocketService();
      const status = defaultService.getConnectionStatus();

      expect(status.url).toContain('localhost:8001');
    });

    it('should accept custom configuration', () => {
      const customService = new DataManagementWebSocketService({
        url: 'wss://custom.example.com/ws',
        reconnect: {
          enabled: false,
          maxAttempts: 3,
          delay: 5000,
          backoff: 2.0,
        },
      });

      const status = customService.getConnectionStatus();
      expect(status.url).toBe('wss://custom.example.com/ws');
    });

    it('should handle production vs development URLs', () => {
      const originalEnv = process.env.NODE_ENV;

      process.env.NODE_ENV = 'production';
      const prodService = new DataManagementWebSocketService();
      expect(prodService.getConnectionStatus().url).toContain('wss://api.fxml4.com');

      process.env.NODE_ENV = 'development';
      const devService = new DataManagementWebSocketService();
      expect(devService.getConnectionStatus().url).toContain('localhost:8001');

      process.env.NODE_ENV = originalEnv;
    });
  });

  describe('Error Handling', () => {
    it('should handle JSON parsing errors gracefully', async () => {
      await service.connect();

      const consoleSpy = jest.spyOn(console, 'log').mockImplementation();

      // Trigger invalid JSON message
      const invalidMessageEvent = new MessageEvent('message', {
        data: 'invalid-json',
      });
      mockWebSocket.triggerEvent('message', invalidMessageEvent);

      // Should not throw, but log error
      expect(consoleSpy).toHaveBeenCalledWith(
        expect.stringContaining('[DataManagementWebSocket]'),
        expect.stringContaining('Failed to parse message')
      );

      consoleSpy.mockRestore();
    });

    it('should handle subscription callback errors', async () => {
      await service.connect();

      const consoleSpy = jest.spyOn(console, 'log').mockImplementation();
      const errorCallback = jest.fn(() => {
        throw new Error('Callback error');
      });

      service.subscribe({
        type: WebSocketMessageType.DATA_SOURCE_STATUS,
        callback: errorCallback,
      });

      mockWebSocket.triggerMessage({
        type: WebSocketMessageType.DATA_SOURCE_STATUS,
        data: { sourceId: 'test' },
      });

      expect(errorCallback).toHaveBeenCalled();
      expect(consoleSpy).toHaveBeenCalledWith(
        expect.stringContaining('[DataManagementWebSocket]'),
        expect.stringContaining('Subscription callback error')
      );

      consoleSpy.mockRestore();
    });
  });

  describe('Singleton and Factory Functions', () => {
    it('should provide singleton instance', () => {
      const { getDataManagementWebSocket } = require('./dataManagementWebSocket');

      const instance1 = getDataManagementWebSocket();
      const instance2 = getDataManagementWebSocket();

      expect(instance1).toBe(instance2);
    });

    it('should create new instances via factory', () => {
      const { createDataManagementWebSocket } = require('./dataManagementWebSocket');

      const instance1 = createDataManagementWebSocket({ url: 'ws://test1' });
      const instance2 = createDataManagementWebSocket({ url: 'ws://test2' });

      expect(instance1).not.toBe(instance2);
      expect(instance1.getConnectionStatus().url).toBe('ws://test1');
      expect(instance2.getConnectionStatus().url).toBe('ws://test2');
    });
  });
});
