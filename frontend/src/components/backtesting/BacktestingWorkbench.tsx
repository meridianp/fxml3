/**
 * Backtesting Workbench Component
 *
 * Main interface for creating, running, and analyzing strategy backtests
 */

'use client';

import { useState, useEffect } from 'react';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import BacktestCard from './BacktestCard';
import { SymbolSelector } from '@/components/data';
import { api } from '@/services/api';
import { useAppStore } from '@/stores/appStore';
import type { Backtest, Strategy } from '@/types';
import {
  PlusIcon,
  PlayIcon,
  ChartBarIcon,
  Cog6ToothIcon,
  DocumentChartBarIcon,
  RocketLaunchIcon,
  BeakerIcon,
  ClockIcon
} from '@heroicons/react/24/outline';

interface CreateBacktestForm {
  name: string;
  description: string;
  strategy_id: string;
  symbol: string;
  timeframe: string;
  start_date: string;
  end_date: string;
  initial_capital: number;
  commission: number;
  slippage: number;
  parameters: Record<string, any>;
}

const SAMPLE_STRATEGIES = [
  { id: '1', name: 'MA Crossover', description: 'Moving average crossover strategy' },
  { id: '2', name: 'RSI Reversal', description: 'RSI overbought/oversold reversal' },
  { id: '3', name: 'Bollinger Bands', description: 'Bollinger bands breakout/reversal' },
  { id: '4', name: 'ML Signals', description: 'Machine learning based signals' },
  { id: '5', name: 'Elliott Wave', description: 'Elliott wave pattern trading' },
];

export default function BacktestingWorkbench() {
  const [activeTab, setActiveTab] = useState('backtests');
  const [backtests, setBacktests] = useState<Backtest[]>([]);
  const [strategies, setStrategies] = useState<Strategy[]>(SAMPLE_STRATEGIES as Strategy[]);
  const [loading, setLoading] = useState(false);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [createForm, setCreateForm] = useState<CreateBacktestForm>({
    name: '',
    description: '',
    strategy_id: '',
    symbol: 'EURUSD',
    timeframe: '1h',
    start_date: new Date(Date.now() - 365 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
    end_date: new Date().toISOString().split('T')[0],
    initial_capital: 100000,
    commission: 0.0001,
    slippage: 0.0001,
    parameters: {}
  });

  const { addNotification, addError } = useAppStore();

  // Load backtests
  useEffect(() => {
    loadBacktests();
  }, []);

  const loadBacktests = async () => {
    try {
      setLoading(true);
      // Note: Backend doesn't have backtest results storage yet
      // Return empty array until implemented
      console.warn('Backtest results storage not implemented - showing empty state');
      setBacktests([]);
    } catch (error) {
      console.error('Failed to load backtests:', error);
      addError({
        code: 'LOAD_BACKTESTS_ERROR',
        message: 'Failed to load backtests',
        timestamp: new Date().toISOString()
      });
    } finally {
      setLoading(false);
    }
  };

  const handleCreateBacktest = async () => {
    try {
      setLoading(true);
      const response = await api.post('/backtesting/backtests', createForm);
      const newBacktest = response.data.backtest;

      setBacktests(prev => [newBacktest, ...prev]);
      setShowCreateForm(false);
      setCreateForm({
        name: '',
        description: '',
        strategy_id: '',
        symbol: 'EURUSD',
        timeframe: '1h',
        start_date: new Date(Date.now() - 365 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
        end_date: new Date().toISOString().split('T')[0],
        initial_capital: 100000,
        commission: 0.0001,
        slippage: 0.0001,
        parameters: {}
      });

      addNotification({
        type: 'success',
        title: 'Backtest Created',
        message: `Backtest "${newBacktest.name}" created successfully`
      });
    } catch (error) {
      console.error('Failed to create backtest:', error);
      addError({
        code: 'CREATE_BACKTEST_ERROR',
        message: 'Failed to create backtest',
        timestamp: new Date().toISOString()
      });
    } finally {
      setLoading(false);
    }
  };

  const handleRunBacktest = async (backtest: Backtest) => {
    try {
      setLoading(true);
      await api.post(`/backtesting/backtests/${backtest.id}/run`);

      // Update backtest status
      setBacktests(prev => prev.map(b =>
        b.id === backtest.id
          ? { ...b, status: 'running', progress: 0 }
          : b
      ));

      addNotification({
        type: 'success',
        title: 'Backtest Started',
        message: `Backtest "${backtest.name}" started running`
      });
    } catch (error) {
      console.error('Failed to run backtest:', error);
      addError({
        code: 'RUN_BACKTEST_ERROR',
        message: 'Failed to run backtest',
        timestamp: new Date().toISOString()
      });
    } finally {
      setLoading(false);
    }
  };

  const handleStopBacktest = async (backtest: Backtest) => {
    try {
      await api.post(`/backtesting/backtests/${backtest.id}/stop`);

      setBacktests(prev => prev.map(b =>
        b.id === backtest.id
          ? { ...b, status: 'cancelled' }
          : b
      ));

      addNotification({
        type: 'info',
        title: 'Backtest Stopped',
        message: `Backtest "${backtest.name}" was cancelled`
      });
    } catch (error) {
      console.error('Failed to stop backtest:', error);
    }
  };

  const handleDuplicateBacktest = async (backtest: Backtest) => {
    const duplicateForm = {
      ...backtest,
      name: `${backtest.name} (Copy)`,
      id: undefined,
      status: 'draft',
      results: undefined
    };

    try {
      const response = await api.post('/backtesting/backtests', duplicateForm);
      const newBacktest = response.data.backtest;
      setBacktests(prev => [newBacktest, ...prev]);

      addNotification({
        type: 'success',
        title: 'Backtest Duplicated',
        message: `Created copy of "${backtest.name}"`
      });
    } catch (error) {
      console.error('Failed to duplicate backtest:', error);
    }
  };

  const handleDeleteBacktest = async (backtest: Backtest) => {
    if (!confirm(`Are you sure you want to delete "${backtest.name}"?`)) {
      return;
    }

    try {
      await api.delete(`/backtesting/backtests/${backtest.id}`);
      setBacktests(prev => prev.filter(b => b.id !== backtest.id));

      addNotification({
        type: 'success',
        title: 'Backtest Deleted',
        message: `Backtest "${backtest.name}" deleted successfully`
      });
    } catch (error) {
      console.error('Failed to delete backtest:', error);
    }
  };

  const handleExportResults = async (backtest: Backtest) => {
    try {
      const response = await api.get(`/backtesting/backtests/${backtest.id}/export`, {
        responseType: 'blob'
      });

      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.download = `${backtest.name.replace(/\s+/g, '_')}_results.csv`;
      link.click();

      addNotification({
        type: 'success',
        title: 'Results Exported',
        message: `Exported results for "${backtest.name}"`
      });
    } catch (error) {
      console.error('Failed to export results:', error);
    }
  };

  const getBacktestStats = () => {
    const total = backtests.length;
    const running = backtests.filter(b => b.status === 'running').length;
    const completed = backtests.filter(b => b.status === 'completed').length;
    const avgReturn = completed > 0
      ? backtests
          .filter(b => b.status === 'completed' && b.results)
          .reduce((sum, b) => sum + (b.results!.total_return || 0), 0) / completed
      : 0;

    return { total, running, completed, avgReturn };
  };

  const stats = getBacktestStats();

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="p-6 border-b border-gray-700 bg-gray-900/50">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-2xl font-bold text-white">Backtesting Workbench</h1>
            <p className="text-gray-400">Create and analyze trading strategy backtests</p>
          </div>

          <div className="flex items-center gap-3">
            <Button
              onClick={() => setShowCreateForm(true)}
              className="gap-2"
            >
              <PlusIcon className="w-4 h-4" />
              New Backtest
            </Button>
          </div>
        </div>

        {/* Quick Stats */}
        <div className="grid grid-cols-4 gap-4">
          <div className="bg-gray-800/50 rounded-lg p-3">
            <div className="text-2xl font-bold text-white">{stats.total}</div>
            <div className="text-sm text-gray-400">Total Backtests</div>
          </div>
          <div className="bg-gray-800/50 rounded-lg p-3">
            <div className="text-2xl font-bold text-blue-400">{stats.running}</div>
            <div className="text-sm text-gray-400">Running</div>
          </div>
          <div className="bg-gray-800/50 rounded-lg p-3">
            <div className="text-2xl font-bold text-green-400">{stats.completed}</div>
            <div className="text-sm text-gray-400">Completed</div>
          </div>
          <div className="bg-gray-800/50 rounded-lg p-3">
            <div className={`text-2xl font-bold ${stats.avgReturn >= 0 ? 'text-green-400' : 'text-red-400'}`}>
              {stats.avgReturn >= 0 ? '+' : ''}{(stats.avgReturn * 100).toFixed(1)}%
            </div>
            <div className="text-sm text-gray-400">Avg Return</div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 p-6">
        <Tabs value={activeTab} onValueChange={setActiveTab} className="h-full flex flex-col">
          <TabsList className="grid w-full grid-cols-4 bg-gray-800">
            <TabsTrigger value="backtests" className="gap-2">
              <PlayIcon className="w-4 h-4" />
              Backtests
            </TabsTrigger>
            <TabsTrigger value="strategies" className="gap-2">
              <RocketLaunchIcon className="w-4 h-4" />
              Strategies
            </TabsTrigger>
            <TabsTrigger value="optimization" className="gap-2">
              <BeakerIcon className="w-4 h-4" />
              Optimization
            </TabsTrigger>
            <TabsTrigger value="reports" className="gap-2">
              <DocumentChartBarIcon className="w-4 h-4" />
              Reports
            </TabsTrigger>
          </TabsList>

          <div className="flex-1 mt-6">
            <TabsContent value="backtests" className="h-full">
              {loading && backtests.length === 0 ? (
                <div className="flex items-center justify-center h-full">
                  <div className="flex items-center gap-2 text-gray-400">
                    <div className="w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
                    Loading backtests...
                  </div>
                </div>
              ) : backtests.length === 0 ? (
                <div className="flex items-center justify-center h-full">
                  <div className="text-center">
                    <ChartBarIcon className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                    <h3 className="text-lg font-semibold text-white mb-2">No Backtests Yet</h3>
                    <p className="text-gray-400 mb-4">Create your first backtest to analyze strategy performance</p>
                    <Button onClick={() => setShowCreateForm(true)} className="gap-2">
                      <PlusIcon className="w-4 h-4" />
                      Create Your First Backtest
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                  {backtests.map((backtest) => (
                    <BacktestCard
                      key={backtest.id}
                      backtest={backtest}
                      onRun={handleRunBacktest}
                      onStop={handleStopBacktest}
                      onView={(backtest) => console.log('View results:', backtest)}
                      onDuplicate={handleDuplicateBacktest}
                      onDelete={handleDeleteBacktest}
                      onExport={handleExportResults}
                    />
                  ))}
                </div>
              )}
            </TabsContent>

            <TabsContent value="strategies" className="h-full">
              <div className="bg-gray-900 border border-gray-700 rounded-lg p-6 text-center">
                <RocketLaunchIcon className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                <h3 className="text-lg font-semibold text-white mb-2">Strategy Library</h3>
                <p className="text-gray-400 mb-4">
                  Manage and create trading strategies for backtesting
                </p>
                <Button className="gap-2">
                  <PlusIcon className="w-4 h-4" />
                  Create Strategy
                </Button>
              </div>
            </TabsContent>

            <TabsContent value="optimization" className="h-full">
              <div className="bg-gray-900 border border-gray-700 rounded-lg p-6 text-center">
                <BeakerIcon className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                <h3 className="text-lg font-semibold text-white mb-2">Parameter Optimization</h3>
                <p className="text-gray-400 mb-4">
                  Optimize strategy parameters using genetic algorithms and grid search
                </p>
                <Button className="gap-2">
                  <BeakerIcon className="w-4 h-4" />
                  Start Optimization
                </Button>
              </div>
            </TabsContent>

            <TabsContent value="reports" className="h-full">
              <div className="bg-gray-900 border border-gray-700 rounded-lg p-6 text-center">
                <DocumentChartBarIcon className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                <h3 className="text-lg font-semibold text-white mb-2">Performance Reports</h3>
                <p className="text-gray-400 mb-4">
                  Generate detailed performance reports and analytics
                </p>
                <Button className="gap-2">
                  <DocumentChartBarIcon className="w-4 h-4" />
                  View Reports
                </Button>
              </div>
            </TabsContent>
          </div>
        </Tabs>
      </div>

      {/* Create Backtest Modal */}
      {showCreateForm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-gray-900 border border-gray-700 rounded-lg w-full max-w-2xl max-h-[90vh] overflow-y-auto">
            <div className="p-6 border-b border-gray-700">
              <h2 className="text-xl font-semibold text-white">Create New Backtest</h2>
              <p className="text-gray-400 text-sm mt-1">Configure your strategy backtest parameters</p>
            </div>

            <div className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">Backtest Name</label>
                <input
                  type="text"
                  value={createForm.name}
                  onChange={(e) => setCreateForm(prev => ({ ...prev, name: e.target.value }))}
                  className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                  placeholder="e.g., MA Crossover EURUSD Q4 2023"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">Description</label>
                <textarea
                  value={createForm.description}
                  onChange={(e) => setCreateForm(prev => ({ ...prev, description: e.target.value }))}
                  className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                  rows={3}
                  placeholder="Describe the strategy and test conditions..."
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">Strategy</label>
                  <select
                    value={createForm.strategy_id}
                    onChange={(e) => setCreateForm(prev => ({ ...prev, strategy_id: e.target.value }))}
                    className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                  >
                    <option value="">Select Strategy</option>
                    {strategies.map((strategy) => (
                      <option key={strategy.id} value={strategy.id}>
                        {strategy.name}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">Symbol</label>
                  <SymbolSelector
                    value={createForm.symbol}
                    onChange={(symbol) => setCreateForm(prev => ({ ...prev, symbol }))}
                    filterBy="forex"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">Timeframe</label>
                  <select
                    value={createForm.timeframe}
                    onChange={(e) => setCreateForm(prev => ({ ...prev, timeframe: e.target.value }))}
                    className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                  >
                    <option value="1m">1 Minute</option>
                    <option value="5m">5 Minutes</option>
                    <option value="15m">15 Minutes</option>
                    <option value="30m">30 Minutes</option>
                    <option value="1h">1 Hour</option>
                    <option value="4h">4 Hours</option>
                    <option value="1d">1 Day</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">Initial Capital</label>
                  <input
                    type="number"
                    value={createForm.initial_capital}
                    onChange={(e) => setCreateForm(prev => ({ ...prev, initial_capital: Number(e.target.value) }))}
                    className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                    min="1000"
                    step="1000"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">Start Date</label>
                  <input
                    type="date"
                    value={createForm.start_date}
                    onChange={(e) => setCreateForm(prev => ({ ...prev, start_date: e.target.value }))}
                    className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">End Date</label>
                  <input
                    type="date"
                    value={createForm.end_date}
                    onChange={(e) => setCreateForm(prev => ({ ...prev, end_date: e.target.value }))}
                    className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">Commission (%)</label>
                  <input
                    type="number"
                    value={createForm.commission}
                    onChange={(e) => setCreateForm(prev => ({ ...prev, commission: Number(e.target.value) }))}
                    className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                    min="0"
                    max="1"
                    step="0.0001"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">Slippage (%)</label>
                  <input
                    type="number"
                    value={createForm.slippage}
                    onChange={(e) => setCreateForm(prev => ({ ...prev, slippage: Number(e.target.value) }))}
                    className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                    min="0"
                    max="1"
                    step="0.0001"
                  />
                </div>
              </div>
            </div>

            <div className="p-6 border-t border-gray-700 flex justify-end gap-3">
              <Button
                variant="ghost"
                onClick={() => setShowCreateForm(false)}
              >
                Cancel
              </Button>
              <Button
                onClick={handleCreateBacktest}
                disabled={!createForm.name || !createForm.strategy_id || loading}
                className="gap-2"
              >
                {loading ? (
                  <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                ) : (
                  <PlusIcon className="w-4 h-4" />
                )}
                Create Backtest
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
