/**
 * Backtest Card Component
 *
 * Displays backtest information with results, metrics, and actions
 */

'use client';

import { useState } from 'react';
import { formatRelativeTime, formatCurrency, formatPercentage } from '@/lib/utils';
import type { Backtest } from '@/types';
import {
  PlayIcon,
  StopIcon,
  EyeIcon,
  TrashIcon,
  ChartBarIcon,
  DocumentDuplicateIcon,
  ArrowDownTrayIcon
} from '@heroicons/react/24/outline';

interface BacktestCardProps {
  backtest: Backtest;
  onRun?: (backtest: Backtest) => void;
  onStop?: (backtest: Backtest) => void;
  onView?: (backtest: Backtest) => void;
  onDuplicate?: (backtest: Backtest) => void;
  onDelete?: (backtest: Backtest) => void;
  onExport?: (backtest: Backtest) => void;
  className?: string;
}

const getStatusColor = (status: string) => {
  switch (status) {
    case 'completed': return 'bg-green-500/20 text-green-400 border-green-500/30';
    case 'running': return 'bg-blue-500/20 text-blue-400 border-blue-500/30';
    case 'failed': return 'bg-red-500/20 text-red-400 border-red-500/30';
    case 'cancelled': return 'bg-gray-500/20 text-gray-400 border-gray-500/30';
    case 'pending': return 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30';
    default: return 'bg-gray-500/20 text-gray-400 border-gray-500/30';
  }
};

const getProfitColor = (value: number) => {
  if (value > 0) return 'text-green-400';
  if (value < 0) return 'text-red-400';
  return 'text-gray-400';
};

export default function BacktestCard({
  backtest,
  onRun,
  onStop,
  onView,
  onDuplicate,
  onDelete,
  onExport,
  className = ''
}: BacktestCardProps) {
  const [isActionLoading, setIsActionLoading] = useState<string | null>(null);

  const handleAction = async (action: string, callback?: () => void) => {
    setIsActionLoading(action);
    try {
      if (callback) {
        await callback();
      }
    } finally {
      setIsActionLoading(null);
    }
  };

  const canRun = ['draft', 'completed', 'failed', 'cancelled'].includes(backtest.status);
  const canStop = backtest.status === 'running';
  const hasResults = backtest.results && backtest.status === 'completed';

  return (
    <div className={`bg-gray-900 border border-gray-700 rounded-lg hover:border-gray-600 transition-colors ${className}`}>
      {/* Header */}
      <div className="p-4 border-b border-gray-800">
        <div className="flex items-start justify-between">
          <div>
            <h3 className="font-semibold text-white text-lg">{backtest.name}</h3>
            <p className="text-gray-400 text-sm mt-1">{backtest.description}</p>
            <div className="flex items-center gap-3 mt-2">
              <span className={`px-2 py-1 text-xs font-medium rounded-full border ${getStatusColor(backtest.status)}`}>
                {backtest.status.toUpperCase()}
              </span>
              <span className="text-xs text-gray-500">{backtest.strategy_name}</span>
              <span className="text-xs text-gray-500">{backtest.symbol}</span>
              <span className="text-xs text-gray-500">{backtest.timeframe}</span>
            </div>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-2">
            {canRun && (
              <button
                onClick={() => handleAction('run', () => onRun?.(backtest))}
                disabled={isActionLoading === 'run'}
                className="p-2 text-green-400 hover:bg-green-500/20 rounded-lg transition-colors disabled:opacity-50"
                title="Run Backtest"
              >
                {isActionLoading === 'run' ? (
                  <div className="w-4 h-4 border-2 border-green-400 border-t-transparent rounded-full animate-spin" />
                ) : (
                  <PlayIcon className="w-4 h-4" />
                )}
              </button>
            )}

            {canStop && (
              <button
                onClick={() => handleAction('stop', () => onStop?.(backtest))}
                disabled={isActionLoading === 'stop'}
                className="p-2 text-red-400 hover:bg-red-500/20 rounded-lg transition-colors disabled:opacity-50"
                title="Stop Backtest"
              >
                {isActionLoading === 'stop' ? (
                  <div className="w-4 h-4 border-2 border-red-400 border-t-transparent rounded-full animate-spin" />
                ) : (
                  <StopIcon className="w-4 h-4" />
                )}
              </button>
            )}

            {hasResults && (
              <button
                onClick={() => onView?.(backtest)}
                className="p-2 text-blue-400 hover:bg-blue-500/20 rounded-lg transition-colors"
                title="View Results"
              >
                <ChartBarIcon className="w-4 h-4" />
              </button>
            )}

            <button
              onClick={() => handleAction('duplicate', () => onDuplicate?.(backtest))}
              disabled={isActionLoading === 'duplicate'}
              className="p-2 text-gray-400 hover:bg-gray-700 rounded-lg transition-colors disabled:opacity-50"
              title="Duplicate"
            >
              {isActionLoading === 'duplicate' ? (
                <div className="w-4 h-4 border-2 border-gray-400 border-t-transparent rounded-full animate-spin" />
              ) : (
                <DocumentDuplicateIcon className="w-4 h-4" />
              )}
            </button>

            {hasResults && (
              <button
                onClick={() => handleAction('export', () => onExport?.(backtest))}
                disabled={isActionLoading === 'export'}
                className="p-2 text-gray-400 hover:bg-gray-700 rounded-lg transition-colors disabled:opacity-50"
                title="Export Results"
              >
                {isActionLoading === 'export' ? (
                  <div className="w-4 h-4 border-2 border-gray-400 border-t-transparent rounded-full animate-spin" />
                ) : (
                  <ArrowDownTrayIcon className="w-4 h-4" />
                )}
              </button>
            )}

            <button
              onClick={() => handleAction('delete', () => onDelete?.(backtest))}
              disabled={isActionLoading === 'delete'}
              className="p-2 text-red-400 hover:bg-red-500/20 rounded-lg transition-colors disabled:opacity-50"
              title="Delete"
            >
              {isActionLoading === 'delete' ? (
                <div className="w-4 h-4 border-2 border-red-400 border-t-transparent rounded-full animate-spin" />
              ) : (
                <TrashIcon className="w-4 h-4" />
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Progress (for running backtests) */}
      {backtest.status === 'running' && backtest.progress !== undefined && (
        <div className="p-4 border-b border-gray-800">
          <div className="flex justify-between text-xs text-gray-400 mb-1">
            <span>Progress</span>
            <span>{Math.round(backtest.progress * 100)}%</span>
          </div>
          <div className="w-full bg-gray-800 rounded-full h-2">
            <div
              className="bg-blue-500 h-2 rounded-full transition-all duration-300"
              style={{ width: `${backtest.progress * 100}%` }}
            />
          </div>
        </div>
      )}

      {/* Results Summary */}
      {hasResults && backtest.results && (
        <div className="p-4 border-b border-gray-800">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <div className="text-xs text-gray-500 mb-1">Total Return</div>
              <div className={`text-lg font-semibold ${getProfitColor(backtest.results.total_return)}`}>
                {formatPercentage(backtest.results.total_return * 100)}
              </div>
            </div>
            <div>
              <div className="text-xs text-gray-500 mb-1">Max Drawdown</div>
              <div className="text-lg font-semibold text-red-400">
                {formatPercentage(Math.abs(backtest.results.max_drawdown) * 100)}
              </div>
            </div>
            <div>
              <div className="text-xs text-gray-500 mb-1">Sharpe Ratio</div>
              <div className="text-lg font-semibold text-white">
                {backtest.results.sharpe_ratio.toFixed(2)}
              </div>
            </div>
            <div>
              <div className="text-xs text-gray-500 mb-1">Win Rate</div>
              <div className="text-lg font-semibold text-white">
                {formatPercentage(backtest.results.win_rate * 100)}
              </div>
            </div>
          </div>

          {/* Trade Summary */}
          <div className="mt-4 pt-4 border-t border-gray-800">
            <div className="grid grid-cols-3 gap-4 text-sm">
              <div className="text-center">
                <div className="font-semibold text-white">{backtest.results.total_trades}</div>
                <div className="text-gray-500">Total Trades</div>
              </div>
              <div className="text-center">
                <div className="font-semibold text-green-400">{backtest.results.winning_trades}</div>
                <div className="text-gray-500">Winners</div>
              </div>
              <div className="text-center">
                <div className="font-semibold text-red-400">{backtest.results.losing_trades}</div>
                <div className="text-gray-500">Losers</div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Footer */}
      <div className="p-4">
        <div className="text-xs text-gray-500 space-y-1">
          <div className="flex justify-between">
            <span>Period:</span>
            <span className="text-gray-300">
              {new Date(backtest.start_date).toLocaleDateString()} - {new Date(backtest.end_date).toLocaleDateString()}
            </span>
          </div>
          <div className="flex justify-between">
            <span>Initial Capital:</span>
            <span className="text-gray-300">{formatCurrency(backtest.initial_capital)}</span>
          </div>
          <div className="flex justify-between">
            <span>Created:</span>
            <span className="text-gray-300">{formatRelativeTime(backtest.created_at)}</span>
          </div>
          {backtest.completed_at && (
            <div className="flex justify-between">
              <span>Completed:</span>
              <span className="text-gray-300">{formatRelativeTime(backtest.completed_at)}</span>
            </div>
          )}
          {backtest.duration && (
            <div className="flex justify-between">
              <span>Duration:</span>
              <span className="text-gray-300">{backtest.duration}s</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
