/**
 * Dashboard Page
 *
 * Main dashboard with overview of all trading platform features
 */

'use client';

import Link from 'next/link';
import {
  ChartBarIcon,
  RocketLaunchIcon,
  BeakerIcon,
  CurrencyDollarIcon,
  WifiIcon,
  CloudArrowDownIcon,
  DocumentChartBarIcon,
  Cog6ToothIcon,
  ArrowPathIcon
} from '@heroicons/react/24/outline';
import { useDashboardStats, useModels, useBacktests, usePositions } from '@/hooks/useApiData';
import { useWebSocket } from '@/hooks/useWebSocket';
import { useEffect } from 'react';

const features = [
  {
    title: 'Data Management',
    description: 'Monitor real-time market data, manage historical data, and configure data feeds',
    href: '/data',
    icon: WifiIcon,
    color: 'text-blue-400',
    bgColor: 'bg-blue-500/20',
    borderColor: 'border-blue-500/30'
  },
  {
    title: 'ML Training Studio',
    description: 'Train and manage machine learning models for forex trading signals',
    href: '/training',
    icon: RocketLaunchIcon,
    color: 'text-purple-400',
    bgColor: 'bg-purple-500/20',
    borderColor: 'border-purple-500/30'
  },
  {
    title: 'Backtesting Workbench',
    description: 'Create and analyze trading strategy backtests with comprehensive metrics',
    href: '/backtesting',
    icon: BeakerIcon,
    color: 'text-green-400',
    bgColor: 'bg-green-500/20',
    borderColor: 'border-green-500/30'
  },
  {
    title: 'Trading Console',
    description: 'Live trading operations, order management, and portfolio monitoring',
    href: '/trading',
    icon: CurrencyDollarIcon,
    color: 'text-orange-400',
    bgColor: 'bg-orange-500/20',
    borderColor: 'border-orange-500/30'
  }
];


export default function DashboardPage() {
  // API hooks for real data
  const { stats, loading: statsLoading, error: statsError } = useDashboardStats();
  const { data: models, loading: modelsLoading, refresh: refreshModels } = useModels();
  const { data: backtests, loading: backtestsLoading, refresh: refreshBacktests } = useBacktests();
  const { data: positions, loading: positionsLoading, refresh: refreshPositions } = usePositions();

  // WebSocket for real-time updates
  const { isConnected, connectionStatus, connect } = useWebSocket({
    autoConnect: true,
    subscribeToTradingUpdates: true,
    subscribeToSignals: true,
    subscribeToSystemUpdates: true
  });

  // Connect WebSocket on mount if not connected
  useEffect(() => {
    if (!isConnected && connectionStatus === 'disconnected') {
      connect();
    }
  }, [isConnected, connectionStatus, connect]);

  // Format currency values
  const formatCurrency = (value: number) => {
    const sign = value >= 0 ? '+' : '';
    return `${sign}$${value.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
  };

  // Dynamic stats array from real data with error fallbacks
  const dashboardStats = [
    {
      label: 'Active Models',
      value: statsLoading ? '...' : statsError ? 'N/A' : stats.activeModels.toString(),
      change: statsError ? 'API Error' : stats.totalModels > 0 ? `+${stats.totalModels - stats.activeModels}` : '0',
      changeType: statsError ? 'negative' : 'neutral',
      testId: 'models'
    },
    {
      label: 'Running Backtests',
      value: statsLoading ? '...' : statsError ? 'N/A' : stats.runningBacktests.toString(),
      change: statsError ? 'API Error' : stats.completedBacktests > 0 ? `${stats.completedBacktests} completed` : '0',
      changeType: statsError ? 'negative' : 'neutral',
      testId: 'backtests'
    },
    {
      label: 'Open Positions',
      value: statsLoading ? '...' : statsError ? 'N/A' : stats.openPositions.toString(),
      change: statsError ? 'API Error' : stats.openPositions > 0 ? 'active' : 'none',
      changeType: statsError ? 'negative' : stats.openPositions > 0 ? 'positive' : 'neutral',
      testId: 'positions'
    },
    {
      label: 'Total P&L',
      value: statsLoading ? '...' : statsError ? 'N/A' : formatCurrency(stats.totalPnL + stats.unrealizedPnL),
      change: statsError ? 'API Error' : formatCurrency(stats.unrealizedPnL),
      changeType: statsError ? 'negative' : stats.unrealizedPnL >= 0 ? 'positive' : 'negative',
      testId: 'pl'
    }
  ];

  return (
    <div className="p-6">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-white mb-2">FXML4 Trading Platform</h1>
              <p className="text-gray-400 text-lg">
                Professional forex trading with ML-powered signals and comprehensive analytics
              </p>
            </div>
            <div className="flex items-center gap-3">
              <div className={`flex items-center gap-2 px-3 py-1 rounded-full text-sm ${
                isConnected
                  ? 'bg-green-500/20 text-green-400 border border-green-500/30'
                  : 'bg-red-500/20 text-red-400 border border-red-500/30'
              }`}>
                <div className={`w-2 h-2 rounded-full ${
                  isConnected ? 'bg-green-400' : 'bg-red-400'
                }`} />
                {connectionStatus === 'connected' ? 'Live' : connectionStatus || 'Disconnected'}
              </div>
              {statsError && (
                <div className="text-red-400 text-sm px-3 py-1 bg-red-500/20 rounded border border-red-500/30" title={statsError}>
                  API Connection Issues
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Quick Stats */}
        <div className="grid grid-cols-4 gap-6 mb-8">
          {dashboardStats.map((stat) => (
            <div
              key={stat.label}
              data-testid={stat.testId}
              className="metric-card dashboard-card bg-gray-900 border border-gray-700 rounded-lg p-4 relative">
              {statsLoading && (
                <div className="absolute inset-0 bg-gray-900/50 flex items-center justify-center rounded-lg">
                  <ArrowPathIcon className="w-5 h-5 text-gray-400 animate-spin" />
                </div>
              )}
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-gray-400 text-sm">{stat.label}</p>
                  <p className="text-2xl font-bold text-white mt-1">{stat.value}</p>
                </div>
                <div className={`text-sm font-medium ${
                  stat.changeType === 'positive' ? 'text-green-400' :
                  stat.changeType === 'negative' ? 'text-red-400' :
                  'text-gray-400'
                }`}>
                  {stat.change}
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Feature Grid */}
        <div className="grid grid-cols-2 gap-6 mb-8">
          {features.map((feature) => (
            <Link
              key={feature.title}
              href={feature.href}
              className="group block"
            >
              <div className={`
                bg-gray-900 border rounded-lg p-6 h-full
                transition-all duration-200 hover:scale-[1.02]
                ${feature.borderColor} hover:${feature.bgColor}
                group-hover:shadow-xl
              `}>
                <div className="flex items-start gap-4">
                  <div className={`p-3 rounded-lg ${feature.bgColor} border ${feature.borderColor}`}>
                    <feature.icon className={`w-8 h-8 ${feature.color}`} />
                  </div>

                  <div className="flex-1">
                    <h3 className="text-xl font-semibold text-white mb-2 group-hover:text-blue-400 transition-colors">
                      {feature.title}
                    </h3>
                    <p className="text-gray-400 leading-relaxed">
                      {feature.description}
                    </p>

                    <div className="mt-4 flex items-center text-sm text-gray-500 group-hover:text-blue-400 transition-colors">
                      <span>Explore →</span>
                    </div>
                  </div>
                </div>
              </div>
            </Link>
          ))}
        </div>

        {/* Recent Activity */}
        <div className="grid grid-cols-3 gap-6">
          <div className="bg-gray-900 border border-gray-700 rounded-lg p-6">
            <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <ChartBarIcon className="w-5 h-5 text-blue-400" />
              Recent Models
              {modelsLoading && <ArrowPathIcon className="w-4 h-4 text-gray-400 animate-spin" />}
            </h3>
            <div className="space-y-3">
              {!models || models.length === 0 ? (
                <div className={`text-sm py-4 text-center ${
                  modelsLoading ? 'text-gray-400' : 'text-red-400'
                }`}>
                  {modelsLoading ? 'Loading models...' : 'API connection failed - unable to load models'}
                  {!modelsLoading && (
                    <div className="text-xs text-gray-500 mt-1">Check backend API status</div>
                  )}
                </div>
              ) : (
                models.slice(0, 3).map((model) => (
                  <div key={model.id} className="flex items-center justify-between py-2">
                    <div>
                      <p className="text-white font-medium">{model.name}</p>
                      <p className="text-gray-400 text-sm">
                        {model.status === 'training' ? 'Currently training' :
                         model.status === 'deployed' ? 'Deployed' :
                         model.status === 'completed' ? 'Training completed' :
                         model.status}
                      </p>
                    </div>
                    <div className={`text-sm ${
                      model.status === 'deployed' ? 'text-purple-400' :
                      model.status === 'training' ? 'text-blue-400' :
                      model.status === 'completed' ? 'text-green-400' :
                      'text-gray-400'
                    }`}>
                      {model.status === 'deployed' ? 'Live signals' :
                       model.status === 'training' ? `${Math.round((model.training_progress || 0) * 100)}% complete` :
                       model.status === 'completed' ? `${(model.performance_metrics?.accuracy || 0).toFixed(1)}% accuracy` :
                       model.status}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          <div className="bg-gray-900 border border-gray-700 rounded-lg p-6">
            <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <DocumentChartBarIcon className="w-5 h-5 text-green-400" />
              Recent Backtests
              {backtestsLoading && <ArrowPathIcon className="w-4 h-4 text-gray-400 animate-spin" />}
            </h3>
            <div className="space-y-3">
              {!backtests || backtests.length === 0 ? (
                <div className={`text-sm py-4 text-center ${
                  backtestsLoading ? 'text-gray-400' : 'text-red-400'
                }`}>
                  {backtestsLoading ? 'Loading backtests...' : 'API connection failed - unable to load backtests'}
                  {!backtestsLoading && (
                    <div className="text-xs text-gray-500 mt-1">Check backend API status</div>
                  )}
                </div>
              ) : (
                backtests.slice(0, 3).map((backtest) => {
                  const totalReturn = backtest.performance_metrics?.total_return || 0;
                  const createdAt = new Date(backtest.created_at);
                  const timeAgo = Math.floor((Date.now() - createdAt.getTime()) / (1000 * 60 * 60));

                  return (
                    <div key={backtest.id} className="flex items-center justify-between py-2">
                      <div>
                        <p className="text-white font-medium">
                          {backtest.strategy_name} {backtest.symbol}
                        </p>
                        <p className="text-gray-400 text-sm">
                          {backtest.status === 'running' ? 'Running' :
                           backtest.status === 'completed' ? `Completed ${timeAgo}h ago` :
                           backtest.status}
                        </p>
                      </div>
                      <div className={`text-sm ${
                        backtest.status === 'running' ? 'text-blue-400' :
                        totalReturn >= 0 ? 'text-green-400' : 'text-red-400'
                      }`}>
                        {backtest.status === 'running'
                          ? `${Math.round((backtest.progress || 0) * 100)}% complete`
                          : `${totalReturn >= 0 ? '+' : ''}${totalReturn.toFixed(1)}%`
                        }
                      </div>
                    </div>
                  )
                })
              )}
            </div>
          </div>

          <div className="bg-gray-900 border border-gray-700 rounded-lg p-6">
            <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <CurrencyDollarIcon className="w-5 h-5 text-orange-400" />
              Active Positions
              {positionsLoading && <ArrowPathIcon className="w-4 h-4 text-gray-400 animate-spin" />}
            </h3>
            <div className="space-y-3">
              {!positions || positions.length === 0 ? (
                <div className={`text-sm py-4 text-center ${
                  positionsLoading ? 'text-gray-400' : 'text-red-400'
                }`}>
                  {positionsLoading ? 'Loading positions...' : 'API connection failed - unable to load positions'}
                  {!positionsLoading && (
                    <div className="text-xs text-gray-500 mt-1">Check backend API status</div>
                  )}
                </div>
              ) : (
                positions.slice(0, 3).map((position) => (
                  <div key={position.id} className="flex items-center justify-between py-2">
                    <div>
                      <p className="text-white font-medium">
                        {position.symbol} {position.side.toUpperCase()}
                      </p>
                      <p className="text-gray-400 text-sm">
                        {position.quantity.toLocaleString()} units
                      </p>
                    </div>
                    <div className={`text-sm ${
                      position.unrealizedPnL >= 0 ? 'text-green-400' : 'text-red-400'
                    }`}>
                      {formatCurrency(position.unrealizedPnL)}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="mt-12 pt-8 border-t border-gray-800 text-center text-gray-500">
          <p>FXML4 Professional Trading Platform - Advanced ML-Powered Forex Trading</p>
        </div>
    </div>
  );
}
