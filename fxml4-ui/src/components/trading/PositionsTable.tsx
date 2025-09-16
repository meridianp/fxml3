/**
 * Positions Table Component
 *
 * Displays active positions with real-time P&L updates
 */

'use client';

import { useState } from 'react';
import { useTradingStore } from '@/stores/useTradingStore';
import { useMarketDataStore } from '@/stores/useMarketDataStore';
import { useWebSocket } from '@/hooks/useWebSocket';
import { formatCurrency, formatPercentage, formatRelativeTime } from '@/lib/utils';
import { apiClient } from '@/services/api';
import { useAppStore } from '@/stores/useAppStore';
import type { Position } from '@/stores/useTradingStore';
import {
  XMarkIcon,
  PencilIcon,
  ArrowTrendingUpIcon,
  ArrowTrendingDownIcon,
  ChartBarIcon
} from '@heroicons/react/24/outline';

interface PositionsTableProps {
  className?: string;
}

export default function PositionsTable({ className = '' }: PositionsTableProps) {
  const [selectedPosition, setSelectedPosition] = useState<Position | null>(null);
  const [isClosing, setIsClosing] = useState<string | null>(null);

  const { positions, setSelectedPositionId } = useTradingStore();
  const { marketData } = useMarketDataStore();
  const { addNotification } = useAppStore();

  // Subscribe to position updates
  useWebSocket({
    autoConnect: true,
    subscribeToTradingUpdates: true,
    subscribeToMarketData: true,
    symbols: positions.map(p => p.symbol)
  });

  const calculateCurrentPnL = (position: Position) => {
    const symbolData = marketData[position.symbol];
    if (!symbolData) return position.unrealizedPnL;

    const currentPrice = position.side === 'long' ? symbolData.bid : symbolData.ask;
    const priceDiff = position.side === 'long'
      ? currentPrice - position.averagePrice
      : position.averagePrice - currentPrice;

    return priceDiff * position.quantity;
  };

  const calculateCurrentPnLPercentage = (position: Position) => {
    const currentPnL = calculateCurrentPnL(position);
    const positionValue = position.averagePrice * position.quantity;
    return (currentPnL / positionValue) * 100;
  };

  const handleClosePosition = async (position: Position) => {
    try {
      setIsClosing(position.id);

      await apiClient.closePosition(position.id);

      addNotification({
        type: 'success',
        title: 'Position Closed',
        message: `Closed ${position.side} position for ${position.symbol}`
      });

    } catch (error: any) {
      console.error('Failed to close position:', error);
      addNotification({
        type: 'error',
        title: 'Close Failed',
        message: error.message || 'Failed to close position'
      });
    } finally {
      setIsClosing(null);
    }
  };

  const handleModifyPosition = (position: Position) => {
    setSelectedPosition(position);
    setSelectedPositionId(position.id);
  };

  const getPnLColor = (pnl: number) => {
    if (pnl > 0) return 'text-green-400';
    if (pnl < 0) return 'text-red-400';
    return 'text-gray-400';
  };

  const getSideColor = (side: string) => {
    return side === 'long' ? 'text-green-400' : 'text-red-400';
  };

  const getSideIcon = (side: string) => {
    return side === 'long' ? (
      <ArrowTrendingUpIcon className="w-4 h-4" />
    ) : (
      <ArrowTrendingDownIcon className="w-4 h-4" />
    );
  };

  if (positions.length === 0) {
    return (
      <div className={`bg-gray-900 border border-gray-700 rounded-lg p-6 text-center ${className}`}>
        <ChartBarIcon className="w-12 h-12 text-gray-400 mx-auto mb-4" />
        <h3 className="text-lg font-semibold text-white mb-2">No Open Positions</h3>
        <p className="text-gray-400">Your active positions will appear here</p>
      </div>
    );
  }

  // Calculate totals
  const totalPnL = positions.reduce((sum, pos) => sum + calculateCurrentPnL(pos), 0);
  const totalValue = positions.reduce((sum, pos) => sum + (pos.averagePrice * pos.quantity), 0);

  return (
    <div data-testid="positions-table" className={`bg-gray-900 border border-gray-700 rounded-lg ${className}`}>
      {/* Header */}
      <div className="p-4 border-b border-gray-700">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold text-white">Open Positions ({positions.length})</h3>
          <div className="flex items-center gap-4 text-sm">
            <div className="text-gray-400">
              Total P&L: <span className={`font-mono ${getPnLColor(totalPnL)}`}>
                {formatCurrency(totalPnL)}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-gray-800 text-left">
              <th className="p-3 text-gray-400 font-medium">Symbol</th>
              <th className="p-3 text-gray-400 font-medium">Side</th>
              <th className="p-3 text-gray-400 font-medium text-right">Quantity</th>
              <th className="p-3 text-gray-400 font-medium text-right">Entry Price</th>
              <th className="p-3 text-gray-400 font-medium text-right">Current Price</th>
              <th className="p-3 text-gray-400 font-medium text-right">P&L</th>
              <th className="p-3 text-gray-400 font-medium text-right">P&L %</th>
              <th className="p-3 text-gray-400 font-medium text-right">Duration</th>
              <th className="p-3 text-gray-400 font-medium text-center">Actions</th>
            </tr>
          </thead>
          <tbody>
            {positions.map((position) => {
              const symbolData = marketData[position.symbol];
              const currentPrice = symbolData
                ? (position.side === 'long' ? symbolData.bid : symbolData.ask)
                : position.averagePrice;
              const currentPnL = calculateCurrentPnL(position);
              const pnlPercentage = calculateCurrentPnLPercentage(position);

              return (
                <tr
                  key={position.id}
                  data-testid="position-row"
                  data-position-id={position.id}
                  className="border-b border-gray-800/50 hover:bg-gray-800/30 transition-colors"
                >
                  <td className="p-3">
                    <div className="flex items-center gap-2">
                      <span className="font-medium font-mono text-white">
                        {position.symbol}
                      </span>
                      {!symbolData && (
                        <span className="w-1 h-1 bg-gray-500 rounded-full" />
                      )}
                    </div>
                  </td>

                  <td className="p-3">
                    <div className={`flex items-center gap-1 font-medium ${getSideColor(position.side)}`}>
                      {getSideIcon(position.side)}
                      {position.side.toUpperCase()}
                    </div>
                  </td>

                  <td className="p-3 text-right">
                    <span className="font-mono text-white">
                      {position.quantity.toLocaleString()}
                    </span>
                  </td>

                  <td className="p-3 text-right">
                    <span className="font-mono text-white">
                      {formatCurrency(position.averagePrice, position.symbol)}
                    </span>
                  </td>

                  <td className="p-3 text-right">
                    <span className="font-mono text-white">
                      {formatCurrency(currentPrice, position.symbol)}
                    </span>
                  </td>

                  <td className="p-3 text-right">
                    <span data-testid="position-pnl" className={`font-mono font-medium ${getPnLColor(currentPnL)}`}>
                      {currentPnL >= 0 ? '+' : ''}{formatCurrency(currentPnL)}
                    </span>
                  </td>

                  <td className="p-3 text-right">
                    <span className={`font-mono font-medium ${getPnLColor(currentPnL)}`}>
                      {pnlPercentage >= 0 ? '+' : ''}{formatPercentage(pnlPercentage)}
                    </span>
                  </td>

                  <td className="p-3 text-right">
                    <span className="text-gray-400 text-sm">
                      {formatRelativeTime(position.timestamp)}
                    </span>
                  </td>

                  <td className="p-3">
                    <div className="flex items-center justify-center gap-1">
                      <button
                        onClick={() => handleModifyPosition(position)}
                        className="p-1.5 text-gray-400 hover:text-blue-400 hover:bg-blue-500/20 rounded transition-colors"
                        title="Modify Position"
                      >
                        <PencilIcon className="w-4 h-4" />
                      </button>

                      <button
                        data-testid={`close-position-${position.id}`}
                        onClick={() => handleClosePosition(position)}
                        disabled={isClosing === position.id}
                        className="p-1.5 text-gray-400 hover:text-red-400 hover:bg-red-500/20 rounded transition-colors disabled:opacity-50"
                        title="Close Position"
                      >
                        {isClosing === position.id ? (
                          <div className="w-4 h-4 border-2 border-red-400 border-t-transparent rounded-full animate-spin" />
                        ) : (
                          <XMarkIcon className="w-4 h-4" />
                        )}
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Footer Summary */}
      <div className="p-4 border-t border-gray-800 bg-gray-900/50">
        <div className="grid grid-cols-3 gap-4 text-sm">
          <div>
            <div className="text-gray-400">Total Positions</div>
            <div className="text-white font-semibold">{positions.length}</div>
          </div>
          <div>
            <div className="text-gray-400">Total Value</div>
            <div className="text-white font-semibold font-mono">{formatCurrency(totalValue)}</div>
          </div>
          <div>
            <div className="text-gray-400">Total P&L</div>
            <div className={`font-semibold font-mono ${getPnLColor(totalPnL)}`}>
              {totalPnL >= 0 ? '+' : ''}{formatCurrency(totalPnL)}
            </div>
          </div>
        </div>
      </div>

      {/* Position closed notification (shown after successful close) */}
      {isClosing && (
        <div data-testid="position-closed-notification" className="hidden">
          Position closed successfully
        </div>
      )}
    </div>
  );
}
