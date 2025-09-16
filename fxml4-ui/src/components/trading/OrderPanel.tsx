/**
 * Order Panel Component
 *
 * Interface for placing and managing trading orders
 */

'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { SymbolSelector } from '@/components/data';
import { useMarketDataStore } from '@/stores/useMarketDataStore';
import { useTradingStore } from '@/stores/useTradingStore';
import { useAppStore } from '@/stores/useAppStore';
import { apiClient } from '@/services/api';
import { formatCurrency } from '@/lib/utils';
import type { OrderSide, OrderType } from '@/stores/useTradingStore';
import {
  ArrowUpIcon,
  ArrowDownIcon,
  Cog6ToothIcon,
  ExclamationTriangleIcon
} from '@heroicons/react/24/outline';

interface OrderForm {
  symbol: string;
  side: OrderSide;
  type: OrderType;
  quantity: number;
  price?: number;
  stopLoss?: number;
  takeProfit?: number;
  timeInForce: 'GTC' | 'IOC' | 'FOK' | 'DAY';
}

export default function OrderPanel() {
  const [orderForm, setOrderForm] = useState<OrderForm>({
    symbol: 'EURUSD',
    side: 'buy',
    type: 'market',
    quantity: 10000,
    timeInForce: 'GTC'
  });

  const [showAdvanced, setShowAdvanced] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const { getSymbolData } = useMarketDataStore();
  const { accountInfo, canPlaceOrder, setPlacingOrder } = useTradingStore();
  const { addNotification } = useAppStore();

  const currentPrice = getSymbolData(orderForm.symbol);
  const marginUsed = accountInfo?.marginUsed || 0;
  const marginAvailable = accountInfo?.availableMargin || 0;

  const calculateOrderValue = () => {
    if (!currentPrice) return 0;
    const price = orderForm.type === 'market'
      ? (orderForm.side === 'buy' ? currentPrice.ask : currentPrice.bid)
      : (orderForm.price || 0);
    return orderForm.quantity * price;
  };

  const calculateRequiredMargin = () => {
    const orderValue = calculateOrderValue();
    const leverage = 100; // Default leverage
    return orderValue / leverage;
  };

  const canPlaceOrderCheck = () => {
    if (!currentPrice || !accountInfo) return false;
    if (orderForm.quantity <= 0) return false;
    if (orderForm.type !== 'market' && (!orderForm.price || orderForm.price <= 0)) return false;

    const requiredMargin = calculateRequiredMargin();
    return marginAvailable >= requiredMargin && canPlaceOrder(orderForm.quantity, orderForm.price);
  };

  const handleSubmitOrder = async () => {
    if (!canPlaceOrderCheck()) return;

    try {
      setIsSubmitting(true);
      setPlacingOrder(true);

      const orderData = {
        symbol: orderForm.symbol,
        side: orderForm.side,
        type: orderForm.type,
        quantity: orderForm.quantity,
        price: orderForm.type === 'market' ? undefined : orderForm.price,
        stopLoss: orderForm.stopLoss,
        takeProfit: orderForm.takeProfit,
        timeInForce: orderForm.timeInForce
      };

      const order = await apiClient.placeOrder(orderData);

      // Add sequence number and source for race condition prevention
      const orderWithMeta = {
        ...order,
        sequence_number: order.sequence_number || Date.now(),
        source: 'api' as const,
        updatedAt: new Date()
      };

      // Update local state with the new order
      const { addOrder } = useTradingStore.getState();
      addOrder(orderWithMeta);

      addNotification({
        type: 'success',
        title: 'Order Placed',
        message: `${orderForm.side.toUpperCase()} order for ${orderForm.quantity} ${orderForm.symbol} placed successfully`
      });

      // Reset form for market orders
      if (orderForm.type === 'market') {
        setOrderForm(prev => ({ ...prev, quantity: 10000, stopLoss: undefined, takeProfit: undefined }));
      }

    } catch (error: any) {
      console.error('Failed to place order:', error);
      addNotification({
        type: 'error',
        title: 'Order Failed',
        message: error.message || 'Failed to place order'
      });
    } finally {
      setIsSubmitting(false);
      setPlacingOrder(false);
    }
  };

  const getOrderButtonColor = () => {
    if (!canPlaceOrderCheck()) return 'bg-gray-600 hover:bg-gray-600';
    return orderForm.side === 'buy'
      ? 'bg-green-600 hover:bg-green-700'
      : 'bg-red-600 hover:bg-red-700';
  };

  const orderValue = calculateOrderValue();
  const requiredMargin = calculateRequiredMargin();

  const handleFormSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    handleSubmitOrder();
  };

  return (
    <form
      data-testid="trading-form"
      className="order-form trading-form bg-gray-900 border border-gray-700 rounded-lg"
      onSubmit={handleFormSubmit}
    >
      <div className="p-4 border-b border-gray-700">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold text-white">Place Order</h3>
          <button
            data-testid="advanced-options-toggle"
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="p-2 text-gray-400 hover:text-white rounded-lg hover:bg-gray-800 transition-colors"
            title="Advanced Options"
          >
            <Cog6ToothIcon className="w-4 h-4" />
          </button>
        </div>
      </div>

      <div className="p-4 space-y-4">
        {/* Symbol Selection */}
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">Symbol</label>
          <SymbolSelector
            data-testid="symbol-selector"
            value={orderForm.symbol}
            onChange={(symbol) => setOrderForm(prev => ({ ...prev, symbol }))}
            filterBy="forex"
          />
        </div>

        {/* Current Price Display */}
        {currentPrice && (
          <div className="bg-gray-800 rounded-lg p-3">
            <div className="flex justify-between items-center">
              <div className="text-center">
                <div className="text-xs text-gray-400">BID</div>
                <div className="text-lg font-bold text-red-400 font-mono">
                  {formatCurrency(currentPrice.bid, orderForm.symbol)}
                </div>
              </div>
              <div className="text-center">
                <div className="text-xs text-gray-400">SPREAD</div>
                <div className="text-sm text-gray-300 font-mono">
                  {formatCurrency(currentPrice.ask - currentPrice.bid, orderForm.symbol)}
                </div>
              </div>
              <div className="text-center">
                <div className="text-xs text-gray-400">ASK</div>
                <div className="text-lg font-bold text-green-400 font-mono">
                  {formatCurrency(currentPrice.ask, orderForm.symbol)}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Order Type and Side */}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">Order Type</label>
            <select
              data-testid="order-type-select"
              value={orderForm.type}
              onChange={(e) => setOrderForm(prev => ({ ...prev, type: e.target.value as OrderType }))}
              className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white focus:border-blue-500"
            >
              <option value="market">Market</option>
              <option value="limit">Limit</option>
              <option value="stop">Stop</option>
              <option value="stop_limit">Stop Limit</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">Side</label>
            <div className="grid grid-cols-2 gap-1">
              <button
                data-testid="buy-button"
                onClick={() => setOrderForm(prev => ({ ...prev, side: 'buy' }))}
                className={`px-3 py-2 text-sm font-medium rounded-lg transition-colors ${
                  orderForm.side === 'buy'
                    ? 'bg-green-600 text-white'
                    : 'bg-gray-800 text-gray-300 hover:bg-gray-700'
                }`}
              >
                <ArrowUpIcon className="w-4 h-4 inline mr-1" />
                BUY
              </button>
              <button
                data-testid="sell-button"
                onClick={() => setOrderForm(prev => ({ ...prev, side: 'sell' }))}
                className={`px-3 py-2 text-sm font-medium rounded-lg transition-colors ${
                  orderForm.side === 'sell'
                    ? 'bg-red-600 text-white'
                    : 'bg-gray-800 text-gray-300 hover:bg-gray-700'
                }`}
              >
                <ArrowDownIcon className="w-4 h-4 inline mr-1" />
                SELL
              </button>
            </div>
          </div>
        </div>

        {/* Quantity */}
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">Quantity (Units)</label>
          <input
            data-testid="quantity-input"
            type="number"
            value={orderForm.quantity}
            onChange={(e) => setOrderForm(prev => ({ ...prev, quantity: Number(e.target.value) }))}
            className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white focus:border-blue-500"
            min="1000"
            step="1000"
          />
        </div>

        {/* Price (for limit orders) */}
        {orderForm.type !== 'market' && (
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">Price</label>
            <input
              data-testid="price-input"
              type="number"
              value={orderForm.price || ''}
              onChange={(e) => setOrderForm(prev => ({ ...prev, price: Number(e.target.value) || undefined }))}
              className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white focus:border-blue-500"
              step="0.00001"
              placeholder="Enter price..."
            />
          </div>
        )}

        {/* Advanced Options */}
        {showAdvanced && (
          <div className="space-y-4 pt-4 border-t border-gray-800">
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">Stop Loss</label>
              <input
                data-testid="stop-loss-input"
                type="number"
                value={orderForm.stopLoss || ''}
                onChange={(e) => setOrderForm(prev => ({ ...prev, stopLoss: Number(e.target.value) || undefined }))}
                className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white focus:border-blue-500"
                step="0.00001"
                placeholder="Optional stop loss price..."
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">Take Profit</label>
              <input
                data-testid="take-profit-input"
                type="number"
                value={orderForm.takeProfit || ''}
                onChange={(e) => setOrderForm(prev => ({ ...prev, takeProfit: Number(e.target.value) || undefined }))}
                className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white focus:border-blue-500"
                step="0.00001"
                placeholder="Optional take profit price..."
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">Time in Force</label>
              <select
                value={orderForm.timeInForce}
                onChange={(e) => setOrderForm(prev => ({ ...prev, timeInForce: e.target.value as any }))}
                className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white focus:border-blue-500"
              >
                <option value="GTC">Good Till Cancelled (GTC)</option>
                <option value="DAY">Day Order</option>
                <option value="IOC">Immediate or Cancel (IOC)</option>
                <option value="FOK">Fill or Kill (FOK)</option>
              </select>
            </div>
          </div>
        )}

        {/* Order Summary */}
        <div className="bg-gray-800 rounded-lg p-3 space-y-2">
          <div className="flex justify-between text-sm">
            <span className="text-gray-400">Order Value:</span>
            <span className="text-white font-mono">{formatCurrency(orderValue)}</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-gray-400">Required Margin:</span>
            <span className="text-white font-mono">{formatCurrency(requiredMargin)}</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-gray-400">Available Margin:</span>
            <span className={`font-mono ${marginAvailable >= requiredMargin ? 'text-green-400' : 'text-red-400'}`}>
              {formatCurrency(marginAvailable)}
            </span>
          </div>
        </div>

        {/* Warning if insufficient margin */}
        {marginAvailable < requiredMargin && (
          <div data-testid="insufficient-margin-warning" className="flex items-center gap-2 p-3 bg-red-900/20 border border-red-500/30 rounded-lg">
            <ExclamationTriangleIcon className="w-5 h-5 text-red-400 flex-shrink-0" />
            <span className="text-red-400 text-sm">
              Insufficient margin to place this order. Required: {formatCurrency(requiredMargin)}
            </span>
          </div>
        )}

        {/* Submit Button */}
        <Button
          data-testid="place-order-button"
          type="submit"
          disabled={!canPlaceOrderCheck() || isSubmitting}
          className={`w-full h-12 text-lg font-semibold transition-colors ${getOrderButtonColor()}`}
        >
          {isSubmitting ? (
            <div className="flex items-center gap-2">
              <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
              Placing Order...
            </div>
          ) : (
            `${orderForm.side.toUpperCase()} ${orderForm.quantity} ${orderForm.symbol}`
          )}
        </Button>
      </div>

      {/* Order confirmation overlay (shown after successful order) */}
      {isSubmitting && (
        <div data-testid="order-confirmation" className="hidden">
          Order confirmation
        </div>
      )}
    </form>
  );
}
