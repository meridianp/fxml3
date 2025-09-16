/**
 * Elliott Wave Analysis Page
 *
 * Elliott Wave pattern analysis and LLM-enhanced insights
 */

'use client';

import { useState } from 'react';
import {
  ChartBarSquareIcon,
  SparklesIcon,
  CpuChipIcon,
  DocumentChartBarIcon,
  BeakerIcon
} from '@heroicons/react/24/outline';

export default function ElliottWavePage() {
  const [selectedSymbol, setSelectedSymbol] = useState('EURUSD');
  const [selectedTimeframe, setSelectedTimeframe] = useState('4h');

  const symbols = ['EURUSD', 'GBPUSD', 'USDJPY', 'USDCHF', 'AUDUSD'];
  const timeframes = ['1h', '4h', '1d', '1w'];

  return (
    <div className="p-6">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-white mb-2">Elliott Wave Analysis</h1>
        <p className="text-gray-400 text-lg">
          Advanced wave pattern recognition with AI-powered insights
        </p>
      </div>

      {/* Controls */}
      <div className="grid grid-cols-4 gap-6 mb-8">
        <div className="bg-gray-900 border border-gray-700 rounded-lg p-4">
          <label className="block text-sm font-medium text-gray-300 mb-2">Symbol</label>
          <select
            value={selectedSymbol}
            onChange={(e) => setSelectedSymbol(e.target.value)}
            className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded text-white focus:border-blue-500"
          >
            {symbols.map(symbol => (
              <option key={symbol} value={symbol}>{symbol}</option>
            ))}
          </select>
        </div>

        <div className="bg-gray-900 border border-gray-700 rounded-lg p-4">
          <label className="block text-sm font-medium text-gray-300 mb-2">Timeframe</label>
          <select
            value={selectedTimeframe}
            onChange={(e) => setSelectedTimeframe(e.target.value)}
            className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded text-white focus:border-blue-500"
          >
            {timeframes.map(tf => (
              <option key={tf} value={tf}>{tf}</option>
            ))}
          </select>
        </div>

        <div className="bg-gray-900 border border-gray-700 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-2">
            <SparklesIcon className="w-4 h-4 text-purple-400" />
            <span className="text-sm font-medium text-gray-300">LLM Analysis</span>
          </div>
          <div className="text-purple-400 text-sm">Claude 3.5 Sonnet</div>
        </div>

        <div className="bg-gray-900 border border-gray-700 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-2">
            <CpuChipIcon className="w-4 h-4 text-blue-400" />
            <span className="text-sm font-medium text-gray-300">Pattern Recognition</span>
          </div>
          <div className="text-green-400 text-sm">Active</div>
        </div>
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-3 gap-6">
        {/* Chart Area */}
        <div className="col-span-2 bg-gray-900 border border-gray-700 rounded-lg p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-white">Price Chart & Wave Analysis</h3>
            <ChartBarSquareIcon className="w-5 h-5 text-blue-400" />
          </div>

          <div className="h-96 bg-gray-800 rounded-lg flex items-center justify-center">
            <div className="text-center text-gray-400">
              <ChartBarSquareIcon className="w-16 h-16 mx-auto mb-4 opacity-50" />
              <p className="text-lg font-medium">Elliott Wave Chart</p>
              <p className="text-sm mt-2">
                Chart integration with TradingView or custom charting library
              </p>
              <div className="mt-4 text-xs">
                <p>• Wave pattern overlay</p>
                <p>• Fibonacci retracements</p>
                <p>• Support/resistance levels</p>
              </div>
            </div>
          </div>
        </div>

        {/* Analysis Panel */}
        <div className="space-y-6">
          {/* Current Wave Count */}
          <div className="bg-gray-900 border border-gray-700 rounded-lg p-6">
            <div className="flex items-center gap-2 mb-4">
              <DocumentChartBarIcon className="w-5 h-5 text-green-400" />
              <h3 className="text-lg font-semibold text-white">Current Wave Count</h3>
            </div>

            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <span className="text-gray-400">Primary Wave</span>
                <span className="text-white font-mono">Wave 3</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-gray-400">Sub Wave</span>
                <span className="text-white font-mono">Wave (3)</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-gray-400">Degree</span>
                <span className="text-white font-mono">Intermediate</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-gray-400">Confidence</span>
                <span className="text-green-400 font-mono">87%</span>
              </div>
            </div>
          </div>

          {/* LLM Insights */}
          <div className="bg-gray-900 border border-gray-700 rounded-lg p-6">
            <div className="flex items-center gap-2 mb-4">
              <SparklesIcon className="w-5 h-5 text-purple-400" />
              <h3 className="text-lg font-semibold text-white">AI Insights</h3>
            </div>

            <div className="space-y-3 text-sm">
              <div className="bg-gray-800 rounded p-3">
                <p className="text-gray-300">
                  <span className="text-purple-400 font-medium">Pattern Recognition:</span>
                  {" "}Strong impulse wave developing with extended third wave characteristics.
                </p>
              </div>

              <div className="bg-gray-800 rounded p-3">
                <p className="text-gray-300">
                  <span className="text-blue-400 font-medium">Market Structure:</span>
                  {" "}Higher highs and higher lows confirm bullish wave structure.
                </p>
              </div>

              <div className="bg-gray-800 rounded p-3">
                <p className="text-gray-300">
                  <span className="text-green-400 font-medium">Next Target:</span>
                  {" "}Wave 3 projection suggests target at 1.1250-1.1300 zone.
                </p>
              </div>
            </div>
          </div>

          {/* Trading Signals */}
          <div className="bg-gray-900 border border-gray-700 rounded-lg p-6">
            <div className="flex items-center gap-2 mb-4">
              <BeakerIcon className="w-5 h-5 text-orange-400" />
              <h3 className="text-lg font-semibold text-white">Wave-Based Signals</h3>
            </div>

            <div className="space-y-3">
              <div className="flex items-center justify-between p-3 bg-green-500/10 border border-green-500/20 rounded">
                <div>
                  <div className="text-green-400 font-medium">BUY Signal</div>
                  <div className="text-xs text-gray-400">Wave 3 extension</div>
                </div>
                <div className="text-green-400 font-mono">ACTIVE</div>
              </div>

              <div className="flex items-center justify-between p-3 bg-gray-800 rounded">
                <div>
                  <div className="text-gray-400 font-medium">SELL Signal</div>
                  <div className="text-xs text-gray-500">Awaiting Wave 4</div>
                </div>
                <div className="text-gray-500 font-mono">PENDING</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Wave History Table */}
      <div className="mt-8 bg-gray-900 border border-gray-700 rounded-lg p-6">
        <h3 className="text-lg font-semibold text-white mb-4">Recent Wave Patterns</h3>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-700">
                <th className="text-left text-gray-400 py-3">Date</th>
                <th className="text-left text-gray-400 py-3">Wave</th>
                <th className="text-left text-gray-400 py-3">Start Price</th>
                <th className="text-left text-gray-400 py-3">End Price</th>
                <th className="text-left text-gray-400 py-3">Move</th>
                <th className="text-left text-gray-400 py-3">Confidence</th>
                <th className="text-left text-gray-400 py-3">Status</th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-b border-gray-800">
                <td className="py-3 text-gray-300">2024-08-29</td>
                <td className="py-3 text-white font-mono">Wave 2</td>
                <td className="py-3 text-white font-mono">1.1120</td>
                <td className="py-3 text-white font-mono">1.1085</td>
                <td className="py-3 text-red-400">-35 pips</td>
                <td className="py-3 text-green-400">92%</td>
                <td className="py-3"><span className="px-2 py-1 bg-green-500/20 text-green-400 rounded text-xs">Completed</span></td>
              </tr>
              <tr className="border-b border-gray-800">
                <td className="py-3 text-gray-300">2024-08-28</td>
                <td className="py-3 text-white font-mono">Wave 1</td>
                <td className="py-3 text-white font-mono">1.1050</td>
                <td className="py-3 text-white font-mono">1.1120</td>
                <td className="py-3 text-green-400">+70 pips</td>
                <td className="py-3 text-green-400">89%</td>
                <td className="py-3"><span className="px-2 py-1 bg-green-500/20 text-green-400 rounded text-xs">Completed</span></td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
