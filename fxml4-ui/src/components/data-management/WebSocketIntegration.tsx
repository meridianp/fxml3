/**
 * WebSocket Integration Component
 *
 * Provides real-time WebSocket connectivity indicator and management for data management dashboard
 */

import React, { useState, useEffect, useCallback } from 'react';
import { DataManagementWebSocketService, getDataManagementWebSocket } from '@/services/dataManagementWebSocket';
import { WebSocketState, WebSocketConnectionStatus } from '@/types/websocket';

export interface WebSocketIntegrationProps {
  className?: string;
  showConnectionDetails?: boolean;
  onConnectionChange?: (connected: boolean) => void;
  onStatusChange?: (status: WebSocketConnectionStatus) => void;
}

export const WebSocketIntegration: React.FC<WebSocketIntegrationProps> = ({
  className = '',
  showConnectionDetails = false,
  onConnectionChange,
  onStatusChange,
}) => {
  const [websocketService] = useState<DataManagementWebSocketService>(() => getDataManagementWebSocket());
  const [connectionStatus, setConnectionStatus] = useState<WebSocketConnectionStatus>(
    websocketService.getConnectionStatus()
  );
  const [isConnected, setIsConnected] = useState(websocketService.isConnected());

  // Update connection status
  const updateConnectionStatus = useCallback(() => {
    const status = websocketService.getConnectionStatus();
    const connected = websocketService.isConnected();

    setConnectionStatus(status);
    setIsConnected(connected);

    onConnectionChange?.(connected);
    onStatusChange?.(status);
  }, [websocketService, onConnectionChange, onStatusChange]);

  // Set up WebSocket event listeners
  useEffect(() => {
    const handleStateChange = (state: WebSocketState) => {
      updateConnectionStatus();
    };

    const handleOpen = () => {
      updateConnectionStatus();
    };

    const handleClose = () => {
      updateConnectionStatus();
    };

    const handleError = () => {
      updateConnectionStatus();
    };

    const handleReconnect = (attempt: number) => {
      console.log(`[WebSocket] Reconnection attempt ${attempt}`);
      updateConnectionStatus();
    };

    websocketService.addEventListener('stateChange', handleStateChange);
    websocketService.addEventListener('open', handleOpen);
    websocketService.addEventListener('close', handleClose);
    websocketService.addEventListener('error', handleError);
    websocketService.addEventListener('reconnect', handleReconnect);

    // Initial status update
    updateConnectionStatus();

    // Set up periodic status updates
    const statusInterval = setInterval(updateConnectionStatus, 5000);

    return () => {
      websocketService.removeEventListener('stateChange', handleStateChange);
      websocketService.removeEventListener('open', handleOpen);
      websocketService.removeEventListener('close', handleClose);
      websocketService.removeEventListener('error', handleError);
      websocketService.removeEventListener('reconnect', handleReconnect);
      clearInterval(statusInterval);
    };
  }, [websocketService, updateConnectionStatus]);

  // Connect to WebSocket if not connected
  const handleConnect = useCallback(async () => {
    try {
      await websocketService.connect();
    } catch (error) {
      console.error('[WebSocket] Connection failed:', error);
    }
  }, [websocketService]);

  // Disconnect from WebSocket
  const handleDisconnect = useCallback(() => {
    websocketService.disconnect();
  }, [websocketService]);

  // Reconnect WebSocket
  const handleReconnect = useCallback(async () => {
    try {
      await websocketService.reconnect();
    } catch (error) {
      console.error('[WebSocket] Reconnection failed:', error);
    }
  }, [websocketService]);

  // Get status color based on connection state
  const getStatusColor = () => {
    switch (connectionStatus.state) {
      case WebSocketState.CONNECTED:
        return 'text-green-600 bg-green-100';
      case WebSocketState.CONNECTING:
      case WebSocketState.RECONNECTING:
        return 'text-yellow-600 bg-yellow-100';
      case WebSocketState.DISCONNECTED:
        return 'text-gray-600 bg-gray-100';
      case WebSocketState.ERROR:
        return 'text-red-600 bg-red-100';
      default:
        return 'text-gray-600 bg-gray-100';
    }
  };

  // Get status text
  const getStatusText = () => {
    switch (connectionStatus.state) {
      case WebSocketState.CONNECTED:
        return 'Connected';
      case WebSocketState.CONNECTING:
        return 'Connecting...';
      case WebSocketState.RECONNECTING:
        return `Reconnecting (${connectionStatus.reconnectAttempts})`;
      case WebSocketState.DISCONNECTED:
        return 'Disconnected';
      case WebSocketState.ERROR:
        return 'Error';
      case WebSocketState.CLOSED:
        return 'Closed';
      default:
        return 'Unknown';
    }
  };

  return (
    <div className={`flex items-center space-x-3 ${className}`} data-testid="websocket-integration">
      {/* Connection Status Indicator */}
      <div className="flex items-center space-x-2">
        <div
          className={`w-3 h-3 rounded-full ${
            isConnected ? 'bg-green-500' :
            connectionStatus.state === WebSocketState.CONNECTING || connectionStatus.state === WebSocketState.RECONNECTING ? 'bg-yellow-500' :
            'bg-red-500'
          }`}
          data-testid="connection-indicator"
        />

        <span
          className={`px-2 py-1 rounded-full text-xs font-medium ${getStatusColor()}`}
          data-testid="connection-status"
        >
          {getStatusText()}
        </span>
      </div>

      {/* Connection Details */}
      {showConnectionDetails && (
        <div className="flex items-center space-x-4 text-sm text-gray-600">
          {connectionStatus.latency !== undefined && (
            <span data-testid="connection-latency">
              {connectionStatus.latency}ms
            </span>
          )}

          {connectionStatus.lastHeartbeat && (
            <span data-testid="last-heartbeat">
              Last: {connectionStatus.lastHeartbeat.toLocaleTimeString()}
            </span>
          )}

          {connectionStatus.connectedAt && isConnected && (
            <span data-testid="connected-since">
              Since: {connectionStatus.connectedAt.toLocaleTimeString()}
            </span>
          )}
        </div>
      )}

      {/* Connection Controls */}
      <div className="flex items-center space-x-2">
        {!isConnected && connectionStatus.state !== WebSocketState.CONNECTING && (
          <button
            onClick={handleConnect}
            className="px-3 py-1 bg-green-600 text-white rounded text-xs hover:bg-green-700"
            data-testid="connect-button"
          >
            Connect
          </button>
        )}

        {isConnected && (
          <button
            onClick={handleDisconnect}
            className="px-3 py-1 bg-red-600 text-white rounded text-xs hover:bg-red-700"
            data-testid="disconnect-button"
          >
            Disconnect
          </button>
        )}

        {(connectionStatus.state === WebSocketState.ERROR ||
          connectionStatus.state === WebSocketState.DISCONNECTED) && (
          <button
            onClick={handleReconnect}
            className="px-3 py-1 bg-blue-600 text-white rounded text-xs hover:bg-blue-700"
            data-testid="reconnect-button"
          >
            Reconnect
          </button>
        )}
      </div>

      {/* Error Display */}
      {connectionStatus.error && (
        <div className="text-xs text-red-600 max-w-xs truncate" title={connectionStatus.error}>
          Error: {connectionStatus.error}
        </div>
      )}
    </div>
  );
};

/**
 * Hook for using WebSocket connection in components
 */
export const useDataManagementWebSocket = () => {
  const [websocketService] = useState<DataManagementWebSocketService>(() => getDataManagementWebSocket());
  const [isConnected, setIsConnected] = useState(websocketService.isConnected());
  const [connectionStatus, setConnectionStatus] = useState(websocketService.getConnectionStatus());

  useEffect(() => {
    const updateStatus = () => {
      setIsConnected(websocketService.isConnected());
      setConnectionStatus(websocketService.getConnectionStatus());
    };

    const handleStateChange = () => updateStatus();
    const handleOpen = () => updateStatus();
    const handleClose = () => updateStatus();
    const handleError = () => updateStatus();

    websocketService.addEventListener('stateChange', handleStateChange);
    websocketService.addEventListener('open', handleOpen);
    websocketService.addEventListener('close', handleClose);
    websocketService.addEventListener('error', handleError);

    // Auto-connect if not connected
    if (!websocketService.isConnected() && connectionStatus.state === WebSocketState.DISCONNECTED) {
      websocketService.connect().catch(console.error);
    }

    return () => {
      websocketService.removeEventListener('stateChange', handleStateChange);
      websocketService.removeEventListener('open', handleOpen);
      websocketService.removeEventListener('close', handleClose);
      websocketService.removeEventListener('error', handleError);
    };
  }, [websocketService, connectionStatus.state]);

  const subscribe = useCallback((
    type: any,
    callback: (message: any) => void,
    filters?: Record<string, any>
  ) => {
    return websocketService.subscribe({ type, callback, filters });
  }, [websocketService]);

  const unsubscribe = useCallback((subscriptionId: string) => {
    websocketService.unsubscribe(subscriptionId);
  }, [websocketService]);

  const send = useCallback((message: any) => {
    websocketService.send(message);
  }, [websocketService]);

  return {
    websocketService,
    isConnected,
    connectionStatus,
    subscribe,
    unsubscribe,
    send,
  };
};
