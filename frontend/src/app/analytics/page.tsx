/**
 * Analytics Page
 *
 * Performance analytics and business intelligence dashboard
 */

'use client';

import { useState } from 'react';
import {
  ChartBarIcon,
  DocumentChartBarIcon,
  CurrencyDollarIcon,
  ArrowTrendingUpIcon,
  ArrowTrendingDownIcon,
  CalendarDaysIcon,
  ClockIcon
} from '@heroicons/react/24/outline';

export default function AnalyticsPage() {
  const [selectedPeriod, setSelectedPeriod] = useState('30d');
  const [selectedMetric, setSelectedMetric] = useState('pnl');

  const periods = [
    { value: '7d', label: '7 Days' },
    { value: '30d', label: '30 Days' },
    { value: '90d', label: '90 Days' },
    { value: '1y', label: '1 Year' }
  ];

  const metrics = [
    { value: 'pnl', label: 'P&L Analysis' },
    { value: 'risk', label: 'Risk Metrics' },
    { value: 'performance', label: 'Performance' },
    { value: 'trades', label: 'Trade Analysis' }
  ];

  return (
    <div className="p-6">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-white mb-2">Performance Analytics</h1>
        <p className="text-gray-400 text-lg">
          Comprehensive trading performance analysis and business intelligence
        </p>
      </div>

      {/* Controls */}
      <div className="grid grid-cols-4 gap-6 mb-8">
        <div className="bg-gray-900 border border-gray-700 rounded-lg p-4">
          <label className="block text-sm font-medium text-gray-300 mb-2">Time Period</label>
          <select
            value={selectedPeriod}
            onChange={(e) => setSelectedPeriod(e.target.value)}
            className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded text-white focus:border-blue-500"
          >
            {periods.map(period => (
              <option key={period.value} value={period.value}>{period.label}</option>
            ))}
          </select>
        </div>

        <div className="bg-gray-900 border border-gray-700 rounded-lg p-4">
          <label className="block text-sm font-medium text-gray-300 mb-2">Metric Focus</label>
          <select
            value={selectedMetric}
            onChange={(e) => setSelectedMetric(e.target.value)}
            className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded text-white focus:border-blue-500"
          >
            {metrics.map(metric => (
              <option key={metric.value} value={metric.value}>{metric.label}</option>
            ))}
          </select>
        </div>

        <div className="bg-gray-900 border border-gray-700 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-2">
            <ClockIcon className="w-4 h-4 text-blue-400" />
            <span className="text-sm font-medium text-gray-300">Real-time Updates</span>
          </div>
          <div className="text-green-400 text-sm">Live</div>
        </div>

        <div className="bg-gray-900 border border-gray-700 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-2">
            <CalendarDaysIcon className="w-4 h-4 text-purple-400" />
            <span className="text-sm font-medium text-gray-300">Last Updated</span>
          </div>
          <div className="text-white text-sm">Just now</div>
        </div>
      </div>

      {/* Key Metrics Cards */}
      <div className="grid grid-cols-4 gap-6 mb-8">
        <div className="bg-gray-900 border border-gray-700 rounded-lg p-6">
          <div className="flex items-center justify-between mb-4">
            <CurrencyDollarIcon className="w-8 h-8 text-green-400" />
            <ArrowTrendingUpIcon className="w-5 h-5 text-green-400" />
          </div>
          <div className="text-2xl font-bold text-white mb-1">+$12,547</div>
          <div className="text-sm text-gray-400">Total P&L</div>
          <div className="text-green-400 text-xs mt-2">+18.2% this period</div>
        </div>

        <div className="bg-gray-900 border border-gray-700 rounded-lg p-6">
          <div className="flex items-center justify-between mb-4">
            <ChartBarIcon className="w-8 h-8 text-blue-400" />
            <ArrowTrendingUpIcon className="w-5 h-5 text-green-400" />
          </div>
          <div className="text-2xl font-bold text-white mb-1">1.87</div>
          <div className="text-sm text-gray-400">Sharpe Ratio</div>
          <div className="text-green-400 text-xs mt-2">Above target</div>
        </div>

        <div className="bg-gray-900 border border-gray-700 rounded-lg p-6">
          <div className="flex items-center justify-between mb-4">
            <DocumentChartBarIcon className="w-8 h-8 text-orange-400" />
            <ArrowTrendingDownIcon className="w-5 h-5 text-red-400" />
          </div>
          <div className="text-2xl font-bold text-white mb-1">-8.4%</div>
          <div className="text-sm text-gray-400">Max Drawdown</div>
          <div className="text-red-400 text-xs mt-2">Within limits</div>
        </div>

        <div className="bg-gray-900 border border-gray-700 rounded-lg p-6">
          <div className="flex items-center justify-between mb-4">
            <ArrowTrendingUpIcon className="w-8 h-8 text-purple-400" />
            <ArrowTrendingUpIcon className="w-5 h-5 text-green-400" />
          </div>
          <div className="text-2xl font-bold text-white mb-1">68.3%</div>
          <div className="text-sm text-gray-400">Win Rate</div>
          <div className="text-green-400 text-xs mt-2">+2.1% vs avg</div>
        </div>
      </div>

      {/* Main Chart Area */}
      <div className="grid grid-cols-3 gap-6 mb-8">
        <div className="col-span-2 bg-gray-900 border border-gray-700 rounded-lg p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-white">Equity Curve</h3>
            <div className="flex gap-2">
              <button className="px-3 py-1 bg-blue-500/20 text-blue-400 rounded text-xs">Daily</button>
              <button className="px-3 py-1 bg-gray-700 text-gray-400 rounded text-xs">Weekly</button>
              <button className="px-3 py-1 bg-gray-700 text-gray-400 rounded text-xs">Monthly</button>
            </div>
          </div>

          <div className="h-80 bg-gray-800 rounded-lg flex items-center justify-center">
            <div className="text-center text-gray-400">
              <ChartBarIcon className="w-16 h-16 mx-auto mb-4 opacity-50" />
              <p className="text-lg font-medium">Equity Curve Chart</p>
              <p className="text-sm mt-2">
                Real-time P&L performance visualization
              </p>
              <div className="mt-4 text-xs">
                <p>• Daily equity progression</p>
                <p>• Drawdown periods highlighted</p>
                <p>• Benchmark comparisons</p>
              </div>
            </div>
          </div>
        </div>

        <div className="space-y-6">
          {/* Risk Metrics */}
          <div className="bg-gray-900 border border-gray-700 rounded-lg p-6">
            <h3 className="text-lg font-semibold text-white mb-4">Risk Analysis</h3>

            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <span className="text-gray-400">VaR (95%)</span>
                <span className="text-red-400 font-mono">-$1,247</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-gray-400">Beta</span>
                <span className="text-white font-mono">0.73</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-gray-400">Volatility</span>
                <span className="text-yellow-400 font-mono">12.4%</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-gray-400">Correlation</span>
                <span className="text-blue-400 font-mono">0.45</span>
              </div>
            </div>
          </div>

          {/* Trade Statistics */}
          <div className="bg-gray-900 border border-gray-700 rounded-lg p-6">
            <h3 className="text-lg font-semibold text-white mb-4">Trade Stats</h3>

            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <span className="text-gray-400">Total Trades</span>
                <span className="text-white font-mono">247</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-gray-400">Avg Win</span>
                <span className="text-green-400 font-mono">+$187</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-gray-400">Avg Loss</span>
                <span className="text-red-400 font-mono">-$89</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-gray-400">Profit Factor</span>
                <span className="text-green-400 font-mono">2.31</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Performance Breakdown */}
      <div className="grid grid-cols-2 gap-6">
        {/* Symbol Performance */}
        <div className="bg-gray-900 border border-gray-700 rounded-lg p-6">
          <h3 className="text-lg font-semibold text-white mb-4">Performance by Symbol</h3>

          <div className="space-y-3">
            <div className="flex items-center justify-between p-3 bg-gray-800 rounded">
              <div>
                <div className="text-white font-mono">EURUSD</div>
                <div className="text-xs text-gray-400">47 trades</div>
              </div>
              <div className="text-right">
                <div className="text-green-400 font-mono">+$4,231</div>
                <div className="text-xs text-gray-400">72% win rate</div>
              </div>
            </div>

            <div className="flex items-center justify-between p-3 bg-gray-800 rounded">
              <div>
                <div className="text-white font-mono">GBPUSD</div>
                <div className="text-xs text-gray-400">38 trades</div>
              </div>
              <div className="text-right">
                <div className="text-green-400 font-mono">+$2,987</div>
                <div className="text-xs text-gray-400">65% win rate</div>
              </div>
            </div>

            <div className="flex items-center justify-between p-3 bg-gray-800 rounded">
              <div>
                <div className="text-white font-mono">USDJPY</div>
                <div className="text-xs text-gray-400">31 trades</div>
              </div>
              <div className="text-right">
                <div className="text-red-400 font-mono">-$467</div>
                <div className="text-xs text-gray-400">48% win rate</div>
              </div>
            </div>
          </div>
        </div>

        {/* Monthly Breakdown */}
        <div className="bg-gray-900 border border-gray-700 rounded-lg p-6">
          <h3 className="text-lg font-semibold text-white mb-4">Monthly Performance</h3>

          <div className="space-y-3">
            <div className="flex items-center justify-between p-3 bg-gray-800 rounded">
              <div>
                <div className="text-white">August 2024</div>
                <div className="text-xs text-gray-400">89 trades</div>
              </div>
              <div className="text-right">
                <div className="text-green-400 font-mono">+$5,847</div>
                <div className="text-xs text-green-400">+12.4%</div>
              </div>
            </div>

            <div className="flex items-center justify-between p-3 bg-gray-800 rounded">
              <div>
                <div className="text-white">July 2024</div>
                <div className="text-xs text-gray-400">76 trades</div>
              </div>
              <div className="text-right">
                <div className="text-green-400 font-mono">+$3,214</div>
                <div className="text-xs text-green-400">+7.8%</div>
              </div>
            </div>

            <div className="flex items-center justify-between p-3 bg-gray-800 rounded">
              <div>
                <div className="text-white">June 2024</div>
                <div className="text-xs text-gray-400">82 trades</div>
              </div>
              <div className="text-right">
                <div className="text-red-400 font-mono">-$1,186</div>
                <div className="text-xs text-red-400">-2.9%</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
