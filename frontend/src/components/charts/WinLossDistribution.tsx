/**
 * Win/Loss Distribution Chart
 *
 * Statistical analysis of trade outcomes with distribution histograms,
 * profit factor analysis, and trade performance metrics
 */

'use client';

import { useState, useEffect } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from 'recharts';

interface TradeDistributionData {
  range: string;
  wins: number;
  losses: number;
  winAmount: number;
  lossAmount: number;
}

interface TradeMetrics {
  totalTrades: number;
  winningTrades: number;
  losingTrades: number;
  winRate: number;
  avgWin: number;
  avgLoss: number;
  profitFactor: number;
  largestWin: number;
  largestLoss: number;
  expectancy: number;
  consecutiveWins: number;
  consecutiveLosses: number;
}

interface WinLossDistributionProps {
  trades?: Array<{
    pnl: number;
    pnl_pct: number;
    duration_hours: number;
  }>;
  avgWin?: number;
  avgLoss?: number;
  winRate?: number;
  className?: string;
}

export default function WinLossDistribution({
  trades = [],
  avgWin = 125.30,
  avgLoss = -89.20,
  winRate = 0.58,
  className = ''
}: WinLossDistributionProps) {
  const [distributionData, setDistributionData] = useState<TradeDistributionData[]>([]);
  const [metrics, setMetrics] = useState<TradeMetrics | null>(null);
  const [viewType, setViewType] = useState<'amount' | 'percentage' | 'duration'>('amount');

  useEffect(() => {
    // Generate or process trade data
    const generateTradeAnalysis = () => {
      let tradesToAnalyze = trades;

      // If no trades provided, generate realistic sample data
      if (trades.length === 0) {
        tradesToAnalyze = generateSampleTrades(200);
      }

      const processedMetrics = calculateMetrics(tradesToAnalyze);
      const distribution = createDistribution(tradesToAnalyze, viewType);

      setMetrics(processedMetrics);
      setDistributionData(distribution);
    };

    generateTradeAnalysis();
  }, [trades, viewType, avgWin, avgLoss, winRate]);

  const generateSampleTrades = (count: number) => {
    const sampleTrades = [];

    for (let i = 0; i < count; i++) {
      const isWin = Math.random() < winRate;
      const baseAmount = isWin ? avgWin : Math.abs(avgLoss);
      const volatility = 1 + (Math.random() - 0.5) * 1.5;
      const pnl = isWin ? baseAmount * volatility : -baseAmount * volatility;

      sampleTrades.push({
        pnl,
        pnl_pct: (pnl / 10000) * 100, // Assuming 10k position size
        duration_hours: Math.random() * 72 + 1 // 1-73 hours
      });
    }

    return sampleTrades;
  };

  const calculateMetrics = (tradeData: Array<{pnl: number; pnl_pct: number; duration_hours: number}>): TradeMetrics => {
    const winningTrades = tradeData.filter(t => t.pnl > 0);
    const losingTrades = tradeData.filter(t => t.pnl < 0);

    const totalWinAmount = winningTrades.reduce((sum, t) => sum + t.pnl, 0);
    const totalLossAmount = Math.abs(losingTrades.reduce((sum, t) => sum + t.pnl, 0));

    const avgWinCalc = winningTrades.length > 0 ? totalWinAmount / winningTrades.length : 0;
    const avgLossCalc = losingTrades.length > 0 ? totalLossAmount / losingTrades.length : 0;

    // Calculate consecutive wins/losses
    let maxConsecutiveWins = 0;
    let maxConsecutiveLosses = 0;
    let currentWinStreak = 0;
    let currentLossStreak = 0;

    tradeData.forEach(trade => {
      if (trade.pnl > 0) {
        currentWinStreak++;
        currentLossStreak = 0;
        maxConsecutiveWins = Math.max(maxConsecutiveWins, currentWinStreak);
      } else {
        currentLossStreak++;
        currentWinStreak = 0;
        maxConsecutiveLosses = Math.max(maxConsecutiveLosses, currentLossStreak);
      }
    });

    return {
      totalTrades: tradeData.length,
      winningTrades: winningTrades.length,
      losingTrades: losingTrades.length,
      winRate: winningTrades.length / tradeData.length,
      avgWin: avgWinCalc,
      avgLoss: avgLossCalc,
      profitFactor: avgLossCalc > 0 ? totalWinAmount / totalLossAmount : 0,
      largestWin: Math.max(...winningTrades.map(t => t.pnl), 0),
      largestLoss: Math.min(...losingTrades.map(t => t.pnl), 0),
      expectancy: (totalWinAmount - totalLossAmount) / tradeData.length,
      consecutiveWins: maxConsecutiveWins,
      consecutiveLosses: maxConsecutiveLosses
    };
  };

  const createDistribution = (tradeData: Array<{pnl: number; pnl_pct: number; duration_hours: number}>, type: string) => {
    let ranges: string[] = [];
    let getValue: (trade: any) => number;

    switch (type) {
      case 'percentage':
        ranges = ['-5%+', '-4%', '-3%', '-2%', '-1%', '0-1%', '1-2%', '2-3%', '3-4%', '4%+'];
        getValue = (trade) => trade.pnl_pct;
        break;
      case 'duration':
        ranges = ['<1h', '1-4h', '4-8h', '8-12h', '12-24h', '24-48h', '48h+'];
        getValue = (trade) => trade.duration_hours;
        break;
      default: // amount
        ranges = ['-500+', '-400', '-300', '-200', '-100', '0-100', '100-200', '200-300', '300-400', '400+'];
        getValue = (trade) => trade.pnl;
    }

    const distribution = ranges.map(range => ({
      range,
      wins: 0,
      losses: 0,
      winAmount: 0,
      lossAmount: 0
    }));

    tradeData.forEach(trade => {
      const value = getValue(trade);
      let rangeIndex = 0;

      if (type === 'percentage') {
        if (value <= -5) rangeIndex = 0;
        else if (value <= -4) rangeIndex = 1;
        else if (value <= -3) rangeIndex = 2;
        else if (value <= -2) rangeIndex = 3;
        else if (value <= -1) rangeIndex = 4;
        else if (value <= 1) rangeIndex = 5;
        else if (value <= 2) rangeIndex = 6;
        else if (value <= 3) rangeIndex = 7;
        else if (value <= 4) rangeIndex = 8;
        else rangeIndex = 9;
      } else if (type === 'duration') {
        if (value < 1) rangeIndex = 0;
        else if (value <= 4) rangeIndex = 1;
        else if (value <= 8) rangeIndex = 2;
        else if (value <= 12) rangeIndex = 3;
        else if (value <= 24) rangeIndex = 4;
        else if (value <= 48) rangeIndex = 5;
        else rangeIndex = 6;
      } else { // amount
        if (value <= -500) rangeIndex = 0;
        else if (value <= -400) rangeIndex = 1;
        else if (value <= -300) rangeIndex = 2;
        else if (value <= -200) rangeIndex = 3;
        else if (value <= -100) rangeIndex = 4;
        else if (value <= 100) rangeIndex = 5;
        else if (value <= 200) rangeIndex = 6;
        else if (value <= 300) rangeIndex = 7;
        else if (value <= 400) rangeIndex = 8;
        else rangeIndex = 9;
      }

      if (trade.pnl > 0) {
        distribution[rangeIndex].wins++;
        distribution[rangeIndex].winAmount += trade.pnl;
      } else {
        distribution[rangeIndex].losses++;
        distribution[rangeIndex].lossAmount += Math.abs(trade.pnl);
      }
    });

    return distribution;
  };

  const pieData = metrics ? [
    { name: 'Winning Trades', value: metrics.winningTrades, color: '#10B981' },
    { name: 'Losing Trades', value: metrics.losingTrades, color: '#EF4444' }
  ] : [];

  const formatCurrency = (value: number) => `$${Math.abs(value).toFixed(0)}`;
  const formatPercent = (value: number) => `${(value * 100).toFixed(1)}%`;

  return (
    <div className={`${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h3 className="text-lg font-semibold text-white">Trade Distribution Analysis</h3>
          <p className="text-sm text-gray-400">Statistical breakdown of trading performance</p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setViewType('amount')}
            className={`px-3 py-1 rounded text-sm font-medium transition-colors ${
              viewType === 'amount' ? 'bg-blue-600 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
            }`}
          >
            P&L Amount
          </button>
          <button
            onClick={() => setViewType('percentage')}
            className={`px-3 py-1 rounded text-sm font-medium transition-colors ${
              viewType === 'percentage' ? 'bg-blue-600 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
            }`}
          >
            Percentage
          </button>
          <button
            onClick={() => setViewType('duration')}
            className={`px-3 py-1 rounded text-sm font-medium transition-colors ${
              viewType === 'duration' ? 'bg-blue-600 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
            }`}
          >
            Duration
          </button>
        </div>
      </div>

      {/* Key Metrics */}
      {metrics && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <div className="bg-gray-800/50 rounded-lg p-4 border border-gray-600">
            <div className="text-sm text-gray-400">Win Rate</div>
            <div className="text-2xl font-bold text-green-400">{formatPercent(metrics.winRate)}</div>
          </div>

          <div className="bg-gray-800/50 rounded-lg p-4 border border-gray-600">
            <div className="text-sm text-gray-400">Profit Factor</div>
            <div className="text-2xl font-bold text-blue-400">{metrics.profitFactor.toFixed(2)}</div>
          </div>

          <div className="bg-gray-800/50 rounded-lg p-4 border border-gray-600">
            <div className="text-sm text-gray-400">Expectancy</div>
            <div className={`text-2xl font-bold ${metrics.expectancy >= 0 ? 'text-green-400' : 'text-red-400'}`}>
              {formatCurrency(metrics.expectancy)}
            </div>
          </div>

          <div className="bg-gray-800/50 rounded-lg p-4 border border-gray-600">
            <div className="text-sm text-gray-400">Total Trades</div>
            <div className="text-2xl font-bold text-white">{metrics.totalTrades}</div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Distribution Chart */}
        <div className="lg:col-span-2 bg-gray-800/50 rounded-lg p-4 border border-gray-600">
          <h4 className="font-medium text-white mb-4">Trade Distribution Histogram</h4>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={distributionData} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis
                dataKey="range"
                stroke="#9CA3AF"
                fontSize={11}
                angle={-45}
                textAnchor="end"
                height={60}
              />
              <YAxis stroke="#9CA3AF" fontSize={12} />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#1F2937',
                  border: '1px solid #374151',
                  borderRadius: '8px',
                  color: '#F9FAFB'
                }}
                formatter={(value, name) => [
                  `${value} trades`,
                  name === 'wins' ? 'Winning Trades' : 'Losing Trades'
                ]}
              />
              <Legend />
              <Bar
                dataKey="wins"
                stackId="trades"
                fill="#10B981"
                name="Wins"
                radius={[0, 0, 0, 0]}
              />
              <Bar
                dataKey="losses"
                stackId="trades"
                fill="#EF4444"
                name="Losses"
                radius={[2, 2, 0, 0]}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Win/Loss Pie Chart */}
        <div className="bg-gray-800/50 rounded-lg p-4 border border-gray-600">
          <h4 className="font-medium text-white mb-4">Win/Loss Ratio</h4>
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={pieData}
                  cx="50%"
                  cy="50%"
                  outerRadius={60}
                  innerRadius={30}
                  dataKey="value"
                  stroke="none"
                >
                  {pieData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#1F2937',
                    border: '1px solid #374151',
                    borderRadius: '8px',
                    color: '#F9FAFB'
                  }}
                  formatter={(value) => [`${value} trades`]}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>

          <div className="space-y-2 mt-4">
            <div className="flex justify-between text-sm">
              <span className="flex items-center gap-2">
                <div className="w-3 h-3 bg-green-500 rounded-sm"></div>
                Wins:
              </span>
              <span className="text-white">{metrics?.winningTrades || 0}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="flex items-center gap-2">
                <div className="w-3 h-3 bg-red-500 rounded-sm"></div>
                Losses:
              </span>
              <span className="text-white">{metrics?.losingTrades || 0}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Advanced Metrics */}
      {metrics && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mt-6">
          <div className="bg-gray-800/50 rounded-lg p-4 border border-gray-600">
            <div className="text-sm text-gray-400 mb-2">Average Performance</div>
            <div className="space-y-1 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-300">Avg Win:</span>
                <span className="text-green-400">{formatCurrency(metrics.avgWin)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-300">Avg Loss:</span>
                <span className="text-red-400">{formatCurrency(metrics.avgLoss)}</span>
              </div>
            </div>
          </div>

          <div className="bg-gray-800/50 rounded-lg p-4 border border-gray-600">
            <div className="text-sm text-gray-400 mb-2">Extreme Values</div>
            <div className="space-y-1 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-300">Best Trade:</span>
                <span className="text-green-400">{formatCurrency(metrics.largestWin)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-300">Worst Trade:</span>
                <span className="text-red-400">{formatCurrency(metrics.largestLoss)}</span>
              </div>
            </div>
          </div>

          <div className="bg-gray-800/50 rounded-lg p-4 border border-gray-600">
            <div className="text-sm text-gray-400 mb-2">Streak Analysis</div>
            <div className="space-y-1 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-300">Max Win Streak:</span>
                <span className="text-green-400">{metrics.consecutiveWins}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-300">Max Loss Streak:</span>
                <span className="text-red-400">{metrics.consecutiveLosses}</span>
              </div>
            </div>
          </div>

          <div className="bg-gray-800/50 rounded-lg p-4 border border-gray-600">
            <div className="text-sm text-gray-400 mb-2">Risk Assessment</div>
            <div className="space-y-1 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-300">Risk/Reward:</span>
                <span className="text-white">{(metrics.avgWin / metrics.avgLoss).toFixed(2)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-300">Kelly %:</span>
                <span className="text-blue-400">
                  {((metrics.winRate - (1 - metrics.winRate) / (metrics.avgWin / metrics.avgLoss)) * 100).toFixed(1)}%
                </span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
