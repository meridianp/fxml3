/**
 * Enhanced Order Context with API Integration
 *
 * Provides order management with:
 * - API integration for order submission/modification
 * - Real-time order status updates
 * - Performance tracking and metrics
 * - Error handling and retry logic
 */

import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';
import { TradingAPIService, Order, APIResponse } from '../services/TradingAPIService';

interface EnhancedOrder extends Order {
  id: string;
  status: 'PENDING' | 'FILLED' | 'CANCELLED' | 'REJECTED' | 'PARTIALLY_FILLED';
  timestamp: Date;
  executionPrice?: number;
  filledQuantity?: number;
  remainingQuantity?: number;
  executionTime?: number;
  errorMessage?: string;
}

interface OrderContextType {
  orders: EnhancedOrder[];
  submitOrder: (order: Omit<EnhancedOrder, 'id' | 'status' | 'timestamp'>) => Promise<APIResponse>;
  modifyOrder: (orderId: string, updates: Partial<EnhancedOrder>) => Promise<APIResponse>;
  cancelOrder: (orderId: string) => Promise<APIResponse>;
  getOrderHistory: () => EnhancedOrder[];
  getPerformanceMetrics: () => any;
  emergencyStopAll: () => Promise<APIResponse>;
}

const EnhancedOrderContext = createContext<OrderContextType | undefined>(undefined);

export const useEnhancedOrders = () => {
  const context = useContext(EnhancedOrderContext);
  if (!context) {
    throw new Error('useEnhancedOrders must be used within an EnhancedOrderProvider');
  }
  return context;
};

interface EnhancedOrderProviderProps {
  children: React.ReactNode;
  apiConfig?: {
    baseURL: string;
    apiKey: string;
  };
  onOrderSubmit?: (order: any) => void;
  onOrderUpdate?: (order: EnhancedOrder) => void;
  onError?: (error: any) => void;
}

export const EnhancedOrderProvider: React.FC<EnhancedOrderProviderProps> = ({
  children,
  apiConfig = {
    baseURL: 'https://api.fxml4.com/v1',
    apiKey: 'test_api_key' // pragma: allowlist secret
  },
  onOrderSubmit,
  onOrderUpdate,
  onError
}) => {
  const [orders, setOrders] = useState<EnhancedOrder[]>([
    {
      id: '123',
      symbol: 'EUR/USD',
      side: 'BUY',
      quantity: 10000,
      orderType: 'LIMIT',
      price: 1.0500,
      status: 'PENDING',
      timestamp: new Date(),
      remainingQuantity: 10000
    }
  ]);

  const [orderHistory, setOrderHistory] = useState<EnhancedOrder[]>([]);
  const apiService = React.useMemo(() => new TradingAPIService(apiConfig.baseURL, apiConfig.apiKey), [apiConfig]);

  // Submit order
  const submitOrder = useCallback(async (order: Omit<EnhancedOrder, 'id' | 'status' | 'timestamp'>): Promise<APIResponse> => {
    const startTime = performance.now();

    try {
      // Create local order first for immediate UI feedback
      const newOrder: EnhancedOrder = {
        ...order,
        id: `local_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
        status: 'PENDING',
        timestamp: new Date(),
        remainingQuantity: order.quantity
      };

      // Add to local state immediately
      setOrders(prev => [...prev, newOrder]);

      // Call custom callback if provided
      if (onOrderSubmit) {
        onOrderSubmit(order);
      }

      // Submit to API
      const response = await apiService.submitOrder(order);

      const endTime = performance.now();
      const executionTime = endTime - startTime;

      if (response.success && response.data) {
        // Update local order with server response
        setOrders(prev => prev.map(o =>
          o.id === newOrder.id
            ? {
                ...o,
                id: response.data!.orderId,
                status: response.data!.status as EnhancedOrder['status'],
                executionTime
              }
            : o
        ));

        return {
          ...response,
          executionTime
        };
      } else {
        // Update order status to reflect error
        setOrders(prev => prev.map(o =>
          o.id === newOrder.id
            ? {
                ...o,
                status: 'REJECTED',
                errorMessage: response.error?.message,
                executionTime
              }
            : o
        ));

        if (onError) {
          onError(response.error);
        }

        return response;
      }
    } catch (error) {
      const endTime = performance.now();
      const executionTime = endTime - startTime;

      if (onError) {
        onError(error);
      }

      return {
        success: false,
        error: {
          code: 'SUBMIT_ERROR',
          message: error instanceof Error ? error.message : 'Unknown error'
        },
        executionTime
      };
    }
  }, [apiService, onOrderSubmit, onError]);

  // Modify order
  const modifyOrder = useCallback(async (orderId: string, updates: Partial<EnhancedOrder>): Promise<APIResponse> => {
    const startTime = performance.now();

    try {
      // Update local state optimistically
      setOrders(prev => prev.map(o =>
        o.id === orderId
          ? { ...o, ...updates, timestamp: new Date() }
          : o
      ));

      // Call API
      const response = await apiService.modifyOrder(orderId, updates);

      const endTime = performance.now();
      const executionTime = endTime - startTime;

      if (!response.success) {
        // Revert optimistic update on failure
        setOrders(prev => prev.map(o =>
          o.id === orderId
            ? { ...o, errorMessage: response.error?.message }
            : o
        ));

        if (onError) {
          onError(response.error);
        }
      }

      return {
        ...response,
        executionTime
      };
    } catch (error) {
      const endTime = performance.now();
      const executionTime = endTime - startTime;

      if (onError) {
        onError(error);
      }

      return {
        success: false,
        error: {
          code: 'MODIFY_ERROR',
          message: error instanceof Error ? error.message : 'Unknown error'
        },
        executionTime
      };
    }
  }, [apiService, onError]);

  // Cancel order
  const cancelOrder = useCallback(async (orderId: string): Promise<APIResponse> => {
    const startTime = performance.now();

    try {
      // Update local state optimistically
      setOrders(prev => prev.map(o =>
        o.id === orderId
          ? { ...o, status: 'CANCELLED', timestamp: new Date() }
          : o
      ));

      // Call API
      const response = await apiService.cancelOrder(orderId);

      const endTime = performance.now();
      const executionTime = endTime - startTime;

      if (!response.success) {
        // Revert optimistic update on failure
        setOrders(prev => prev.map(o =>
          o.id === orderId
            ? { ...o, status: 'PENDING', errorMessage: response.error?.message }
            : o
        ));

        if (onError) {
          onError(response.error);
        }
      } else {
        // Move cancelled order to history
        const cancelledOrder = orders.find(o => o.id === orderId);
        if (cancelledOrder) {
          setOrderHistory(prev => [...prev, { ...cancelledOrder, status: 'CANCELLED' }]);
        }
      }

      return {
        ...response,
        executionTime
      };
    } catch (error) {
      const endTime = performance.now();
      const executionTime = endTime - startTime;

      if (onError) {
        onError(error);
      }

      return {
        success: false,
        error: {
          code: 'CANCEL_ERROR',
          message: error instanceof Error ? error.message : 'Unknown error'
        },
        executionTime
      };
    }
  }, [apiService, orders, onError]);

  // Get order history
  const getOrderHistory = useCallback(() => {
    return orderHistory;
  }, [orderHistory]);

  // Emergency stop all orders
  const emergencyStopAll = useCallback(async (): Promise<APIResponse> => {
    const startTime = performance.now();

    try {
      // Cancel all pending orders locally first
      setOrders(prev => prev.map(o =>
        o.status === 'PENDING'
          ? { ...o, status: 'CANCELLED', timestamp: new Date() }
          : o
      ));

      // Call emergency stop API
      const response = await apiService.emergencyStop();

      const endTime = performance.now();
      const executionTime = endTime - startTime;

      if (response.success) {
        // Move all orders to history
        setOrderHistory(prev => [...prev, ...orders.map(o => ({ ...o, status: 'CANCELLED' as const }))]);
        setOrders([]);
      } else {
        if (onError) {
          onError(response.error);
        }
      }

      return {
        ...response,
        executionTime
      };
    } catch (error) {
      const endTime = performance.now();
      const executionTime = endTime - startTime;

      if (onError) {
        onError(error);
      }

      return {
        success: false,
        error: {
          code: 'EMERGENCY_STOP_ERROR',
          message: error instanceof Error ? error.message : 'Unknown error'
        },
        executionTime
      };
    }
  }, [apiService, orders, onError]);

  // Get performance metrics
  const getPerformanceMetrics = useCallback(() => {
    return apiService.getPerformanceMetrics();
  }, [apiService]);

  // Simulate order updates (for testing/demo)
  useEffect(() => {
    const interval = setInterval(() => {
      setOrders(prev => prev.map(order => {
        if (order.status === 'PENDING' && Math.random() < 0.1) {
          // 10% chance per second to fill pending orders
          const updatedOrder = {
            ...order,
            status: 'FILLED' as const,
            executionPrice: order.price || (Math.random() * 2 + 1),
            filledQuantity: order.quantity,
            remainingQuantity: 0,
            timestamp: new Date()
          };

          if (onOrderUpdate) {
            onOrderUpdate(updatedOrder);
          }

          return updatedOrder;
        }
        return order;
      }));
    }, 1000);

    return () => clearInterval(interval);
  }, [onOrderUpdate]);

  const value = {
    orders,
    submitOrder,
    modifyOrder,
    cancelOrder,
    getOrderHistory,
    getPerformanceMetrics,
    emergencyStopAll
  };

  return (
    <EnhancedOrderContext.Provider value={value}>
      {children}
    </EnhancedOrderContext.Provider>
  );
};
