/**
 * Orders Table Component
 *
 * Displays active orders with management capabilities
 */

'use client';

import { useState } from 'react';
import { useTradingStore } from '@/stores/useTradingStore';
import { useWebSocket } from '@/hooks/useWebSocket';
import { formatCurrency, formatRelativeTime } from '@/lib/utils';
import { apiClient } from '@/services/api';
import { useAppStore } from '@/stores/useAppStore';
import type { Order } from '@/stores/useTradingStore';
import {
  XMarkIcon,
  PencilIcon,
  ClockIcon,
  CheckCircleIcon,
  XCircleIcon,
  DocumentTextIcon
} from '@heroicons/react/24/outline';

interface OrdersTableProps {
  showAll?: boolean;
  className?: string;
}

export default function OrdersTable({ showAll = false, className = '' }: OrdersTableProps) {
  const [selectedOrder, setSelectedOrder] = useState<Order | null>(null);
  const [isCancelling, setIsCancelling] = useState<string | null>(null);

  const { orders, setSelectedOrderId } = useTradingStore();
  const { addNotification } = useAppStore();

  // Subscribe to order updates
  useWebSocket({
    autoConnect: true,
    subscribeToTradingUpdates: true
  });

  const filteredOrders = showAll
    ? orders
    : orders.filter(order => order.status === 'pending' || order.status === 'partially_filled');

  const handleCancelOrder = async (order: Order) => {
    try {
      setIsCancelling(order.id);

      await apiClient.cancelOrder(order.id);

      addNotification({
        type: 'success',
        title: 'Order Cancelled',
        message: `Cancelled ${order.side} order for ${order.symbol}`
      });

    } catch (error: any) {
      console.error('Failed to cancel order:', error);
      addNotification({
        type: 'error',
        title: 'Cancel Failed',
        message: error.message || 'Failed to cancel order'
      });
    } finally {
      setIsCancelling(null);
    }
  };

  const handleModifyOrder = (order: Order) => {
    setSelectedOrder(order);
    setSelectedOrderId(order.id);
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'filled': return 'text-green-400 bg-green-500/20 border-green-500/30';
      case 'pending': return 'text-yellow-400 bg-yellow-500/20 border-yellow-500/30';
      case 'partially_filled': return 'text-blue-400 bg-blue-500/20 border-blue-500/30';
      case 'cancelled': return 'text-gray-400 bg-gray-500/20 border-gray-500/30';
      case 'rejected': return 'text-red-400 bg-red-500/20 border-red-500/30';
      case 'expired': return 'text-orange-400 bg-orange-500/20 border-orange-500/30';
      default: return 'text-gray-400 bg-gray-500/20 border-gray-500/30';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'filled': return <CheckCircleIcon className="w-4 h-4" />;
      case 'pending': return <ClockIcon className="w-4 h-4" />;
      case 'partially_filled': return <ClockIcon className="w-4 h-4" />;
      case 'cancelled': return <XCircleIcon className="w-4 h-4" />;
      case 'rejected': return <XCircleIcon className="w-4 h-4" />;
      case 'expired': return <XCircleIcon className="w-4 h-4" />;
      default: return <ClockIcon className="w-4 h-4" />;
    }
  };

  const getSideColor = (side: string) => {
    return side === 'buy' ? 'text-green-400' : 'text-red-400';
  };

  const canModifyOrder = (order: Order) => {
    return order.status === 'pending' || order.status === 'partially_filled';
  };

  const canCancelOrder = (order: Order) => {
    return order.status === 'pending' || order.status === 'partially_filled';
  };

  if (filteredOrders.length === 0) {
    return (
      <div className={`bg-gray-900 border border-gray-700 rounded-lg p-6 text-center ${className}`}>
        <DocumentTextIcon className="w-12 h-12 text-gray-400 mx-auto mb-4" />
        <h3 className="text-lg font-semibold text-white mb-2">
          {showAll ? 'No Orders' : 'No Active Orders'}
        </h3>
        <p className="text-gray-400">
          {showAll
            ? 'Your order history will appear here'
            : 'Your pending orders will appear here'
          }
        </p>
      </div>
    );
  }

  // Calculate stats
  const pendingOrders = filteredOrders.filter(o => o.status === 'pending').length;
  const filledOrders = filteredOrders.filter(o => o.status === 'filled').length;

  return (
    <div data-testid="orders-table" className={`bg-gray-900 border border-gray-700 rounded-lg ${className}`}>
      {/* Header */}
      <div className="p-4 border-b border-gray-700">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold text-white">
            {showAll ? 'All Orders' : 'Active Orders'} ({filteredOrders.length})
          </h3>
          <div className="flex items-center gap-4 text-sm">
            <div className="text-gray-400">
              Pending: <span className="text-yellow-400 font-medium">{pendingOrders}</span>
            </div>
            {showAll && (
              <div className="text-gray-400">
                Filled: <span className="text-green-400 font-medium">{filledOrders}</span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-gray-800 text-left">
              <th className="p-3 text-gray-400 font-medium">Symbol</th>
              <th className="p-3 text-gray-400 font-medium">Type</th>
              <th className="p-3 text-gray-400 font-medium">Side</th>
              <th className="p-3 text-gray-400 font-medium text-right">Quantity</th>
              <th className="p-3 text-gray-400 font-medium text-right">Price</th>
              <th className="p-3 text-gray-400 font-medium text-right">Filled</th>
              <th className="p-3 text-gray-400 font-medium text-center">Status</th>
              <th className="p-3 text-gray-400 font-medium text-right">Created</th>
              <th className="p-3 text-gray-400 font-medium text-center">Actions</th>
            </tr>
          </thead>
          <tbody>
            {filteredOrders.map((order) => {
              const filledQuantity = order.filled_quantity || 0;
              const filledPercentage = (filledQuantity / order.quantity) * 100;

              return (
                <tr
                  key={order.id}
                  data-testid="order-row"
                  className="border-b border-gray-800/50 hover:bg-gray-800/30 transition-colors"
                >
                  <td className="p-3">
                    <span className="font-medium font-mono text-white">
                      {order.symbol}
                    </span>
                  </td>

                  <td className="p-3">
                    <span className="text-gray-300 text-sm capitalize">
                      {order.type.replace('_', ' ')}
                    </span>
                  </td>

                  <td className="p-3">
                    <span className={`font-medium ${getSideColor(order.side)}`}>
                      {order.side.toUpperCase()}
                    </span>
                  </td>

                  <td className="p-3 text-right">
                    <div className="font-mono text-white">
                      {order.quantity.toLocaleString()}
                      {filledQuantity > 0 && (
                        <div className="text-xs text-gray-400">
                          {filledQuantity.toLocaleString()} filled ({filledPercentage.toFixed(1)}%)
                        </div>
                      )}
                    </div>
                  </td>

                  <td className="p-3 text-right">
                    <span className="font-mono text-white">
                      {order.type === 'market'
                        ? 'Market'
                        : formatCurrency(order.price || 0, order.symbol)
                      }
                    </span>
                  </td>

                  <td className="p-3 text-right">
                    {order.avg_fill_price ? (
                      <span className="font-mono text-white">
                        {formatCurrency(order.avg_fill_price, order.symbol)}
                      </span>
                    ) : (
                      <span className="text-gray-500">--</span>
                    )}
                  </td>

                  <td className="p-3 text-center">
                    <span data-testid="order-status" className={`inline-flex items-center gap-1 px-2 py-1 text-xs font-medium rounded-full border ${getStatusColor(order.status)}`}>
                      {getStatusIcon(order.status)}
                      {order.status.replace('_', ' ').toUpperCase()}
                    </span>
                  </td>

                  <td className="p-3 text-right">
                    <span className="text-gray-400 text-sm">
                      {formatRelativeTime(order.created_at)}
                    </span>
                  </td>

                  <td className="p-3">
                    <div className="flex items-center justify-center gap-1">
                      {canModifyOrder(order) && (
                        <button
                          onClick={() => handleModifyOrder(order)}
                          className="p-1.5 text-gray-400 hover:text-blue-400 hover:bg-blue-500/20 rounded transition-colors"
                          title="Modify Order"
                        >
                          <PencilIcon className="w-4 h-4" />
                        </button>
                      )}

                      {canCancelOrder(order) && (
                        <button
                          data-testid="cancel-order-button"
                          onClick={() => handleCancelOrder(order)}
                          disabled={isCancelling === order.id}
                          className="p-1.5 text-gray-400 hover:text-red-400 hover:bg-red-500/20 rounded transition-colors disabled:opacity-50"
                          title="Cancel Order"
                        >
                          {isCancelling === order.id ? (
                            <div className="w-4 h-4 border-2 border-red-400 border-t-transparent rounded-full animate-spin" />
                          ) : (
                            <XMarkIcon className="w-4 h-4" />
                          )}
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Footer */}
      {!showAll && (
        <div className="p-3 border-t border-gray-800 text-center">
          <button className="text-blue-400 hover:text-blue-300 text-sm font-medium transition-colors">
            View All Orders
          </button>
        </div>
      )}
    </div>
  );
}
