/**
 * Advanced Performance Analytics Component
 *
 * Comprehensive performance analysis with advanced metrics, charts, and visualizations
 * Migrated from FXML4 Legacy Streamlit dashboard with enhanced React functionality
 */

'use client';

import { useState, useEffect } from 'react';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { useAppStore } from '@/stores/appStore';
import {
  EquityCurveChart,
  SharpeRatioChart,
  MonthlyReturnsHeatmap,
  WinLossDistribution
} from '@/components/charts';
import {
  ChartBarIcon,
  CursorArrowRaysIcon,
  CurrencyDollarIcon,
  PresentationChartLineIcon,
  CalculatorIcon,
  DocumentChartBarIcon,
  ArrowTrendingUpIcon,
  ArrowTrendingDownIcon
} from '@heroicons/react/24/outline';

interface PerformanceMetrics {
  total_return_pct: number;
  annualized_return: number;
  sharpe_ratio: number;
  sortino_ratio: number;
  max_drawdown_pct: number;
  win_rate: number;
  profit_factor: number;
  expectancy: number;
  recovery_factor: number;
  avg_win: number;
  avg_loss: number;
  risk_of_ruin: number;
  max_consecutive_wins: number;
  max_consecutive_losses: number;
  trades_per_month: number;
}

interface BacktestResult {
  backtest_id: string;
  name: string;
  strategy: string;
  symbol: string;
  timeframe: string;
  start_date: string;
  end_date: string;
  initial_capital: number;
  final_capital: number;
  metrics: PerformanceMetrics;
  equity_curve?: Array<{
    timestamp: string;
    equity: number;
    drawdown_pct: number;
  }>;
  monthly_returns?: Record<string, number>;
  trades?: Array<{
    entry_time: string;
    exit_time: string;
    symbol: string;
    side: 'buy' | 'sell';
    quantity: number;
    entry_price: number;
    exit_price: number;
    pnl: number;
    pnl_pct: number;
    duration_hours: number;
  }>;
  drawdowns?: Array<{
    start_date: string;
    end_date: string;
    recovery_date?: string;
    depth_pct: number;
    duration_days: number;
  }>;
  monte_carlo?: {
    mean_return: number;
    median_return: number;
    worst_case: number;
    best_case: number;
    probability_of_profit: number;
    probability_of_10pct_drawdown: number;
    percentiles: Record<string, number>;
  };
}

export default function PerformanceAnalytics() {
  const [activeTab, setActiveTab] = useState('overview');
  const [selectedBacktest, setSelectedBacktest] = useState<string>('');
  const [backtests, setBacktests] = useState<BacktestResult[]>([]);
  const [currentResult, setCurrentResult] = useState<BacktestResult | null>(null);
  const [loading, setLoading] = useState(true);

  const { addNotification } = useAppStore();

  useEffect(() => {
    loadBacktests();
  }, []);

  useEffect(() => {
    if (selectedBacktest && backtests.length > 0) {
      const result = backtests.find(b => b.backtest_id === selectedBacktest);
      setCurrentResult(result || null);
    }
  }, [selectedBacktest, backtests]);

  const loadBacktests = async () => {
    try {
      setLoading(true);
      // Simulate API call - in production this would fetch from /api/backtests
      const mockResults: BacktestResult[] = [
        {
          backtest_id: 'bt_001',
          name: 'EURUSD MA Crossover Strategy',
          strategy: 'ma_crossover',
          symbol: 'EURUSD',
          timeframe: '1h',
          start_date: '2023-01-01',
          end_date: '2023-12-31',
          initial_capital: 10000,
          final_capital: 12450,
          metrics: {
            total_return_pct: 24.5,
            annualized_return: 24.5,
            sharpe_ratio: 1.45,
            sortino_ratio: 1.89,
            max_drawdown_pct: -8.3,
            win_rate: 0.58,
            profit_factor: 1.85,
            expectancy: 42.5,
            recovery_factor: 2.95,
            avg_win: 125.30,
            avg_loss: -89.20,
            risk_of_ruin: 0.02,
            max_consecutive_wins: 8,
            max_consecutive_losses: 5,
            trades_per_month: 12.5
          },
          equity_curve: generateEquityCurve(10000, 12450, 365),
          monthly_returns: generateMonthlyReturns(),
          trades: generateTradeHistory(150),
          drawdowns: generateDrawdowns(),
          monte_carlo: {
            mean_return: 23.1,
            median_return: 22.8,
            worst_case: -12.5,
            best_case: 45.2,
            probability_of_profit: 0.72,
            probability_of_10pct_drawdown: 0.18,
            percentiles: {
              '5%': -8.5,
              '25%': 12.3,
              '50%': 22.8,
              '75%': 34.1,
              '95%': 41.8
            }
          }
        },
        {
          backtest_id: 'bt_002',
          name: 'GBPUSD ML Ensemble Strategy',
          strategy: 'ml_ensemble',
          symbol: 'GBPUSD',
          timeframe: '4h',
          start_date: '2023-01-01',
          end_date: '2023-12-31',
          initial_capital: 10000,
          final_capital: 11890,
          metrics: {
            total_return_pct: 18.9,
            annualized_return: 18.9,
            sharpe_ratio: 1.28,
            sortino_ratio: 1.65,
            max_drawdown_pct: -12.1,
            win_rate: 0.62,
            profit_factor: 1.72,
            expectancy: 38.2,
            recovery_factor: 1.56,
            avg_win: 145.60,
            avg_loss: -95.40,
            risk_of_ruin: 0.04,
            max_consecutive_wins: 6,
            max_consecutive_losses: 7,
            trades_per_month: 8.3
          },
          equity_curve: generateEquityCurve(10000, 11890, 365),
          monthly_returns: generateMonthlyReturns(),
          trades: generateTradeHistory(100),
          drawdowns: generateDrawdowns(),
          monte_carlo: {
            mean_return: 17.5,
            median_return: 18.1,
            worst_case: -18.2,
            best_case: 38.7,
            probability_of_profit: 0.69,
            probability_of_10pct_drawdown: 0.25,
            percentiles: {
              '5%': -12.1,
              '25%': 8.9,
              '50%': 18.1,
              '75%': 26.8,
              '95%': 35.4
            }
          }
        }
      ];

      setBacktests(mockResults);
      if (mockResults.length > 0) {
        setSelectedBacktest(mockResults[0].backtest_id);
      }
    } catch (error) {
      console.error('Failed to load backtests:', error);
      addNotification({
        type: 'error',
        title: 'Load Error',
        message: 'Failed to load backtest results'
      });
    } finally {
      setLoading(false);
    }
  };

  const formatCurrency = (value: number): string => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD'
    }).format(value);
  };

  const formatPercent = (value: number): string => {
    return `${value.toFixed(2)}%`;
  };

  const formatTime = (timestamp: string): string => {
    return new Date(timestamp).toLocaleDateString();
  };

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center">
          <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-gray-400">Loading performance analytics...</p>
        </div>
      </div>
    );
  }

  if (!currentResult) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center">
          <ChartBarIcon className="w-12 h-12 text-gray-400 mx-auto mb-4" />
          <h3 className="text-lg font-semibold text-white mb-2">No Analysis Selected</h3>
          <p className="text-gray-400">Select a backtest to view performance analytics</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full">
      <Tabs value={activeTab} onValueChange={setActiveTab} className="h-full flex flex-col">
        {/* Header */}
        <div className="p-6 border-b border-gray-700 bg-gray-900/50">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h1 className="text-2xl font-bold text-white">Performance Analytics</h1>
              <p className="text-gray-400">Comprehensive backtest analysis and metrics</p>
            </div>

            <div className="flex items-center gap-3">
              <Select value={selectedBacktest} onValueChange={setSelectedBacktest}>
                <SelectTrigger className="w-80">
                  <SelectValue placeholder="Select backtest..." />
                </SelectTrigger>
                <SelectContent>
                  {backtests.map((backtest) => (
                    <SelectItem key={backtest.backtest_id} value={backtest.backtest_id}>
                      {backtest.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>

              <Button
                onClick={loadBacktests}
                variant="outline"
                size="sm"
              >
                Refresh
              </Button>
            </div>
          </div>

          <TabsList className="grid w-full grid-cols-5 bg-gray-800">
            <TabsTrigger value="overview" className="gap-2">
              <PresentationChartLineIcon className="w-4 h-4" />
              Overview
            </TabsTrigger>
            <TabsTrigger value="returns" className="gap-2">
              <ArrowTrendingUpIcon className="w-4 h-4" />
              Returns
            </TabsTrigger>
            <TabsTrigger value="drawdowns" className="gap-2">
              <ArrowTrendingDownIcon className="w-4 h-4" />
              Drawdowns
            </TabsTrigger>
            <TabsTrigger value="trades" className="gap-2">
              <CurrencyDollarIcon className="w-4 h-4" />
              Trades
            </TabsTrigger>
            <TabsTrigger value="montecarlo" className="gap-2">
              <CalculatorIcon className="w-4 h-4" />
              Monte Carlo
            </TabsTrigger>
          </TabsList>
        </div>

        <div className="flex-1 p-6">
          <TabsContent value="overview" className="h-full mt-0">
            <div className="space-y-6">
              {/* Key Metrics Grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                <div className="bg-gray-900 border border-gray-700 rounded-lg p-6">
                  <div className="flex items-center gap-3 mb-4">
                    <ArrowTrendingUpIcon className="w-6 h-6 text-green-400" />
                    <h4 className="font-semibold text-white">Returns</h4>
                  </div>
                  <div className="space-y-3">
                    <div className="flex justify-between">
                      <span className="text-gray-400">Total Return:</span>
                      <span className="text-green-400 font-medium">{formatPercent(currentResult.metrics.total_return_pct)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-400">Annualized:</span>
                      <span className="text-white font-medium">{formatPercent(currentResult.metrics.annualized_return)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-400">Final Capital:</span>
                      <span className="text-white font-medium">{formatCurrency(currentResult.final_capital)}</span>
                    </div>
                  </div>
                </div>

                <div className="bg-gray-900 border border-gray-700 rounded-lg p-6">
                  <div className="flex items-center gap-3 mb-4">
                    <CursorArrowRaysIcon className="w-6 h-6 text-blue-400" />
                    <h4 className="font-semibold text-white">Risk Metrics</h4>
                  </div>
                  <div className="space-y-3">
                    <div className="flex justify-between">
                      <span className="text-gray-400">Sharpe Ratio:</span>
                      <span className="text-white font-medium">{currentResult.metrics.sharpe_ratio.toFixed(2)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-400">Sortino Ratio:</span>
                      <span className="text-white font-medium">{currentResult.metrics.sortino_ratio.toFixed(2)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-400">Max Drawdown:</span>
                      <span className="text-red-400 font-medium">{formatPercent(Math.abs(currentResult.metrics.max_drawdown_pct))}</span>
                    </div>
                  </div>
                </div>

                <div className="bg-gray-900 border border-gray-700 rounded-lg p-6">
                  <div className="flex items-center gap-3 mb-4">
                    <CurrencyDollarIcon className="w-6 h-6 text-purple-400" />
                    <h4 className="font-semibold text-white">Trade Stats</h4>
                  </div>
                  <div className="space-y-3">
                    <div className="flex justify-between">
                      <span className="text-gray-400">Win Rate:</span>
                      <span className="text-white font-medium">{formatPercent(currentResult.metrics.win_rate * 100)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-400">Profit Factor:</span>
                      <span className="text-white font-medium">{currentResult.metrics.profit_factor.toFixed(2)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-400">Expectancy:</span>
                      <span className="text-white font-medium">{formatCurrency(currentResult.metrics.expectancy)}</span>
                    </div>
                  </div>
                </div>

                <div className="bg-gray-900 border border-gray-700 rounded-lg p-6">
                  <div className="flex items-center gap-3 mb-4">
                    <DocumentChartBarIcon className="w-6 h-6 text-yellow-400" />
                    <h4 className="font-semibold text-white">Advanced</h4>
                  </div>
                  <div className="space-y-3">
                    <div className="flex justify-between">
                      <span className="text-gray-400">Recovery Factor:</span>
                      <span className="text-white font-medium">{currentResult.metrics.recovery_factor.toFixed(2)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-400">Risk of Ruin:</span>
                      <span className="text-white font-medium">{formatPercent(currentResult.metrics.risk_of_ruin * 100)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-400">Trades/Month:</span>
                      <span className="text-white font-medium">{currentResult.metrics.trades_per_month.toFixed(1)}</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Equity Curve */}
              <div className="bg-gray-900 border border-gray-700 rounded-lg p-6">
                <EquityCurveChart
                  data={currentResult.equity_curve || []}
                  initialCapital={currentResult.initial_capital}
                  finalCapital={currentResult.final_capital}
                />
              </div>
            </div>
          </TabsContent>

          <TabsContent value="returns" className="h-full mt-0">
            <div className="space-y-6">
              <div className="bg-gray-900 border border-gray-700 rounded-lg p-6">
                <MonthlyReturnsHeatmap
                  data={currentResult.monthly_returns || {}}
                />
              </div>

              <div className="bg-gray-900 border border-gray-700 rounded-lg p-6">
                <SharpeRatioChart
                  currentSharpe={currentResult.metrics.sharpe_ratio}
                  currentSortino={currentResult.metrics.sortino_ratio}
                />
              </div>
            </div>
          </TabsContent>

          <TabsContent value="drawdowns" className="h-full mt-0">
            <div className="space-y-6">
              <div className="bg-gray-900 border border-gray-700 rounded-lg p-6">
                <h3 className="text-lg font-semibold text-white mb-4">Drawdown Analysis</h3>

                {currentResult.drawdowns && (
                  <div className="space-y-4">
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                      <div>
                        <h4 className="font-medium text-white mb-3">Top Drawdowns</h4>
                        <div className="space-y-2">
                          {currentResult.drawdowns.slice(0, 5).map((dd, index) => (
                            <div key={index} className="bg-gray-800/50 rounded p-3">
                              <div className="flex justify-between items-center">
                                <span className="text-sm text-gray-300">
                                  {formatTime(dd.start_date)} - {formatTime(dd.end_date)}
                                </span>
                                <span className="text-red-400 font-medium">
                                  {formatPercent(Math.abs(dd.depth_pct))}
                                </span>
                              </div>
                              <div className="text-xs text-gray-500 mt-1">
                                Duration: {dd.duration_days} days
                                {dd.recovery_date && ` | Recovery: ${formatTime(dd.recovery_date)}`}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>

                      <div>
                        <h4 className="font-medium text-white mb-3">Drawdown Statistics</h4>
                        <div className="bg-gray-800/50 rounded p-4 space-y-3">
                          <div className="flex justify-between">
                            <span className="text-gray-400">Max Drawdown:</span>
                            <span className="text-red-400 font-medium">
                              {formatPercent(Math.abs(currentResult.metrics.max_drawdown_pct))}
                            </span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-gray-400">Avg Drawdown:</span>
                            <span className="text-white font-medium">
                              {formatPercent(currentResult.drawdowns.reduce((sum, dd) => sum + Math.abs(dd.depth_pct), 0) / currentResult.drawdowns.length)}
                            </span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-gray-400">Recovery Factor:</span>
                            <span className="text-white font-medium">
                              {currentResult.metrics.recovery_factor.toFixed(2)}
                            </span>
                          </div>
                        </div>
                      </div>
                    </div>

                    <div className="bg-gray-800/50 rounded-lg p-6 text-center">
                      <ArrowTrendingDownIcon className="w-16 h-16 text-gray-400 mx-auto mb-4" />
                      <p className="text-gray-400">Underwater curve chart would be displayed here</p>
                      <p className="text-sm text-gray-500 mt-2">
                        Visual representation of drawdown periods and recovery times
                      </p>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </TabsContent>

          <TabsContent value="trades" className="h-full mt-0">
            <div className="space-y-6">
              <div className="bg-gray-900 border border-gray-700 rounded-lg p-6">
                <WinLossDistribution
                  trades={currentResult.trades || []}
                  avgWin={currentResult.metrics.avg_win}
                  avgLoss={currentResult.metrics.avg_loss}
                  winRate={currentResult.metrics.win_rate}
                />
              </div>
            </div>
          </TabsContent>

          <TabsContent value="montecarlo" className="h-full mt-0">
            <div className="space-y-6">
              <div className="bg-gray-900 border border-gray-700 rounded-lg p-6">
                <h3 className="text-lg font-semibold text-white mb-4">Monte Carlo Simulation</h3>

                {currentResult.monte_carlo && (
                  <div className="space-y-6">
                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                      <div className="bg-gray-800/50 rounded p-4 text-center">
                        <div className="text-2xl font-bold text-blue-400 mb-1">
                          {formatPercent(currentResult.monte_carlo.mean_return)}
                        </div>
                        <div className="text-sm text-gray-400">Mean Return</div>
                      </div>

                      <div className="bg-gray-800/50 rounded p-4 text-center">
                        <div className="text-2xl font-bold text-green-400 mb-1">
                          {formatPercent(currentResult.monte_carlo.probability_of_profit * 100)}
                        </div>
                        <div className="text-sm text-gray-400">Probability of Profit</div>
                      </div>

                      <div className="bg-gray-800/50 rounded p-4 text-center">
                        <div className="text-2xl font-bold text-red-400 mb-1">
                          {formatPercent(currentResult.monte_carlo.worst_case)}
                        </div>
                        <div className="text-sm text-gray-400">Worst Case Scenario</div>
                      </div>
                    </div>

                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                      <div>
                        <h4 className="font-medium text-white mb-3">Return Percentiles</h4>
                        <div className="bg-gray-800/50 rounded p-4 space-y-3">
                          {Object.entries(currentResult.monte_carlo.percentiles).map(([percentile, value]) => (
                            <div key={percentile} className="flex justify-between">
                              <span className="text-gray-400">{percentile} Percentile:</span>
                              <span className={`font-medium ${value >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                {formatPercent(value)}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>

                      <div>
                        <h4 className="font-medium text-white mb-3">Risk Metrics</h4>
                        <div className="bg-gray-800/50 rounded p-4 space-y-3">
                          <div className="flex justify-between">
                            <span className="text-gray-400">Best Case:</span>
                            <span className="text-green-400 font-medium">
                              {formatPercent(currentResult.monte_carlo.best_case)}
                            </span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-gray-400">Median Return:</span>
                            <span className="text-white font-medium">
                              {formatPercent(currentResult.monte_carlo.median_return)}
                            </span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-gray-400">Prob of 10% DD:</span>
                            <span className="text-yellow-400 font-medium">
                              {formatPercent(currentResult.monte_carlo.probability_of_10pct_drawdown * 100)}
                            </span>
                          </div>
                        </div>
                      </div>
                    </div>

                    <div className="bg-gray-800/50 rounded-lg p-6 text-center">
                      <CalculatorIcon className="w-16 h-16 text-gray-400 mx-auto mb-4" />
                      <p className="text-gray-400">Monte Carlo distribution chart would be displayed here</p>
                      <p className="text-sm text-gray-500 mt-2">
                        Probability distribution of returns and risk assessment visualization
                      </p>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </TabsContent>
        </div>
      </Tabs>
    </div>
  );
}

// Helper functions for generating mock data
function generateEquityCurve(initial: number, final: number, days: number) {
  const curve = [];
  const totalReturn = (final - initial) / initial;
  const dailyReturn = Math.pow(1 + totalReturn, 1 / days) - 1;

  let currentEquity = initial;
  const startDate = new Date('2023-01-01');

  for (let i = 0; i < days; i++) {
    const date = new Date(startDate);
    date.setDate(date.getDate() + i);

    // Add some volatility
    const volatility = Math.random() * 0.02 - 0.01;
    currentEquity *= (1 + dailyReturn + volatility);

    // Calculate drawdown
    const peak = curve.length > 0 ? Math.max(...curve.map(c => c.equity)) : currentEquity;
    const drawdown = ((currentEquity - peak) / peak) * 100;

    curve.push({
      timestamp: date.toISOString(),
      equity: currentEquity,
      drawdown_pct: Math.min(drawdown, 0)
    });
  }

  return curve;
}

function generateMonthlyReturns() {
  const returns: Record<string, number> = {};
  const months = ['2023-01', '2023-02', '2023-03', '2023-04', '2023-05', '2023-06',
                 '2023-07', '2023-08', '2023-09', '2023-10', '2023-11', '2023-12'];

  months.forEach(month => {
    returns[month] = (Math.random() - 0.3) * 8; // -2.4% to 5.6% monthly returns
  });

  return returns;
}

function generateTradeHistory(count: number) {
  const trades = [];
  const symbols = ['EURUSD', 'GBPUSD', 'USDJPY'];
  const sides = ['buy', 'sell'] as const;

  for (let i = 0; i < count; i++) {
    const entryTime = new Date('2023-01-01');
    entryTime.setHours(entryTime.getHours() + i * 24 + Math.random() * 24);

    const exitTime = new Date(entryTime);
    exitTime.setHours(exitTime.getHours() + Math.random() * 48 + 1);

    const entryPrice = 1.0500 + (Math.random() - 0.5) * 0.1;
    const pnlPct = (Math.random() - 0.4) * 0.05; // Bias toward winning
    const exitPrice = entryPrice * (1 + pnlPct);

    trades.push({
      entry_time: entryTime.toISOString(),
      exit_time: exitTime.toISOString(),
      symbol: symbols[Math.floor(Math.random() * symbols.length)],
      side: sides[Math.floor(Math.random() * sides.length)],
      quantity: 10000,
      entry_price: entryPrice,
      exit_price: exitPrice,
      pnl: (exitPrice - entryPrice) * 10000,
      pnl_pct: pnlPct * 100,
      duration_hours: Math.round((exitTime.getTime() - entryTime.getTime()) / (1000 * 60 * 60))
    });
  }

  return trades;
}

function generateDrawdowns() {
  const drawdowns = [];
  const startDate = new Date('2023-01-01');

  for (let i = 0; i < 5; i++) {
    const start = new Date(startDate);
    start.setDate(start.getDate() + i * 60 + Math.random() * 30);

    const duration = Math.floor(Math.random() * 20) + 5;
    const end = new Date(start);
    end.setDate(end.getDate() + duration);

    const recovery = new Date(end);
    recovery.setDate(recovery.getDate() + Math.floor(Math.random() * 15) + 5);

    drawdowns.push({
      start_date: start.toISOString(),
      end_date: end.toISOString(),
      recovery_date: recovery.toISOString(),
      depth_pct: -(Math.random() * 15 + 2), // -2% to -17%
      duration_days: duration
    });
  }

  return drawdowns.sort((a, b) => Math.abs(b.depth_pct) - Math.abs(a.depth_pct));
}
