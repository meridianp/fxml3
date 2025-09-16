/**
 * Simplified Unit Tests for WebSocketService
 *
 * Focus on core functionality with minimal async complexity
 */

import { WebSocketService } from '../../src/services/WebSocketService';

// Simple mock WebSocket
class SimpleWebSocket {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSED = 3;

  readyState = SimpleWebSocket.OPEN;
  url: string;
  onopen: (() => void) | null = null;
  onclose: (() => void) | null = null;
  onmessage: (() => void) | null = null;
  onerror: (() => void) | null = null;
  sentMessages: string[] = [];

  constructor(url: string) {
    this.url = url;
  }

  send(data: string) {
    this.sentMessages.push(data);
  }

  close() {
    this.readyState = SimpleWebSocket.CLOSED;
  }
}

// Mock global WebSocket
(global as any).WebSocket = SimpleWebSocket;

describe('WebSocketService - Simplified', () => {
  let service: WebSocketService;

  beforeEach(() => {
    service = new WebSocketService({
      url: 'ws://localhost:8080/test',
      reconnectInterval: 100,
      maxReconnectAttempts: 3,
      heartbeatInterval: 1000
    });
  });

  afterEach(() => {
    service.disconnect();
  });

  test('creates service with configuration', () => {
    expect(service).toBeDefined();
    expect(service.getConnectionStatus()).toBe('disconnected');
  });

  test('provides performance metrics', () => {
    const metrics = service.getPerformanceMetrics();
    expect(metrics).toHaveProperty('messagesReceived');
    expect(metrics).toHaveProperty('averageLatency');
    expect(typeof metrics.messagesReceived).toBe('number');
    expect(typeof metrics.averageLatency).toBe('number');
  });

  test('handles subscriber management', () => {
    const handler = jest.fn();
    const unsubscribe = service.subscribe('test_message', handler);

    expect(typeof unsubscribe).toBe('function');

    unsubscribe();
    // Should not throw
  });

  test('handles message sending when disconnected', () => {
    expect(() => {
      service.send({
        type: 'test',
        timestamp: new Date().toISOString()
      });
    }).not.toThrow();
  });

  test('provides connection status', () => {
    const status = service.getConnectionStatus();
    expect(['connected', 'disconnected', 'connecting']).toContain(status);
  });

  test('handles disconnect', () => {
    service.disconnect();
    expect(service.getConnectionStatus()).toBe('disconnected');
  });
});
