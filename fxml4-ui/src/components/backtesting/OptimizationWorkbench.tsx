/**
 * Optimization Workbench Component
 *
 * Main interface for parameter optimization using grid search and genetic algorithms
 */

'use client';

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import GridSearchConfig from './GridSearchConfig';
import GeneticAlgorithm from './GeneticAlgorithm';
import OptimizationResults from './OptimizationResults';
import { useAppStore } from '@/stores/appStore';
import {
  CpuChipIcon,
  BeakerIcon,
  ChartBarIcon,
  PlayIcon,
  StopIcon,
  ArrowPathIcon,
  AdjustmentsHorizontalIcon,
  RocketLaunchIcon
} from '@heroicons/react/24/outline';

interface Strategy {
  id: string;
  name: string;
  type: string;
  parameters: Record<string, any>;
}

interface OptimizationJob {
  id: string;
  strategy: Strategy;
  method: 'grid_search' | 'genetic_algorithm';
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  progress: number;
  startTime: string;
  endTime?: string;
  config: any;
  results?: OptimizationResults;
}

interface OptimizationResults {
  best_parameters: Record<string, any>;
  best_score: number;
  all_results: Array<{
    parameters: Record<string, any>;
    score: number;
    metrics: {
      total_return: number;
      sharpe_ratio: number;
      max_drawdown: number;
      win_rate: number;
      total_trades: number;
    };
  }>;
  optimization_stats: {
    total_combinations: number;
    completed_combinations: number;
    best_generation?: number;
    convergence_metric?: number;
  };
}

interface OptimizationWorkbenchProps {
  strategy: Strategy;
  onStrategyUpdate: (strategy: Strategy) => void;
}

export default function OptimizationWorkbench({
  strategy,
  onStrategyUpdate
}: OptimizationWorkbenchProps) {
  const [activeTab, setActiveTab] = useState('grid_search');
  const [currentJob, setCurrentJob] = useState<OptimizationJob | null>(null);
  const [optimizationHistory, setOptimizationHistory] = useState<OptimizationJob[]>([]);
  const [gridSearchConfig, setGridSearchConfig] = useState<any>(null);
  const [geneticConfig, setGeneticConfig] = useState<any>(null);

  const { addNotification, addError } = useAppStore();

  useEffect(() => {
    // Load optimization history from localStorage or API
    loadOptimizationHistory();
  }, []);

  const loadOptimizationHistory = () => {
    const saved = localStorage.getItem(`optimization_history_${strategy.id}`);
    if (saved) {
      try {
        setOptimizationHistory(JSON.parse(saved));
      } catch (error) {
        console.error('Failed to load optimization history:', error);
      }
    }
  };

  const saveOptimizationHistory = (history: OptimizationJob[]) => {
    localStorage.setItem(`optimization_history_${strategy.id}`, JSON.stringify(history));
  };

  const startOptimization = async (method: 'grid_search' | 'genetic_algorithm', config: any) => {
    try {
      const job: OptimizationJob = {
        id: `opt_${Date.now()}`,
        strategy,
        method,
        status: 'running',
        progress: 0,
        startTime: new Date().toISOString(),
        config
      };

      setCurrentJob(job);

      addNotification({
        type: 'info',
        title: 'Optimization Started',
        message: `${method === 'grid_search' ? 'Grid Search' : 'Genetic Algorithm'} optimization started`
      });

      // Simulate optimization process
      await simulateOptimization(job);

    } catch (error) {
      console.error('Optimization failed:', error);
      addError({
        code: 'OPTIMIZATION_ERROR',
        message: 'Failed to start optimization',
        timestamp: new Date().toISOString()
      });
    }
  };

  const simulateOptimization = async (job: OptimizationJob) => {
    const updateInterval = 500; // Update every 500ms
    const totalDuration = job.method === 'grid_search' ? 10000 : 15000; // 10s for grid, 15s for genetic
    const steps = totalDuration / updateInterval;

    for (let i = 0; i <= steps; i++) {
      if (job.status === 'cancelled') break;

      job.progress = (i / steps) * 100;
      setCurrentJob({ ...job });

      await new Promise(resolve => setTimeout(resolve, updateInterval));
    }

    if (job.status !== 'cancelled') {
      // Generate mock results
      const mockResults = generateMockResults(job.method, job.config);

      job.status = 'completed';
      job.progress = 100;
      job.endTime = new Date().toISOString();
      job.results = mockResults;

      setCurrentJob({ ...job });

      // Add to history
      const newHistory = [...optimizationHistory, job];
      setOptimizationHistory(newHistory);
      saveOptimizationHistory(newHistory);

      addNotification({
        type: 'success',
        title: 'Optimization Completed',
        message: `Best score: ${mockResults.best_score.toFixed(4)}`
      });
    }
  };

  const cancelOptimization = () => {
    if (currentJob) {
      setCurrentJob({
        ...currentJob,
        status: 'cancelled',
        endTime: new Date().toISOString()
      });

      addNotification({
        type: 'warning',
        title: 'Optimization Cancelled',
        message: 'Optimization process was cancelled by user'
      });
    }
  };

  const generateMockResults = (method: string, config: any): OptimizationResults => {
    const numResults = method === 'grid_search' ?
      Math.min(config.total_combinations || 100, 1000) :
      (config.population_size || 50) * (config.generations || 20);

    const results = [];
    let bestScore = -Infinity;
    let bestParams = {};

    for (let i = 0; i < Math.min(numResults, 100); i++) {
      // Generate random parameter variations
      const params: Record<string, any> = {};
      Object.keys(strategy.parameters).forEach(key => {
        const baseValue = strategy.parameters[key];
        if (typeof baseValue === 'number') {
          params[key] = baseValue * (0.8 + Math.random() * 0.4);
        } else {
          params[key] = baseValue;
        }
      });

      // Generate performance metrics
      const totalReturn = -0.2 + Math.random() * 0.6; // -20% to +40%
      const sharpeRatio = -1 + Math.random() * 4; // -1 to 3
      const maxDrawdown = 0.02 + Math.random() * 0.3; // 2% to 32%
      const winRate = 0.3 + Math.random() * 0.4; // 30% to 70%
      const totalTrades = Math.floor(50 + Math.random() * 200);

      // Calculate composite score (simplified)
      const score = sharpeRatio * 0.4 + (totalReturn * 100) * 0.3 + (1 - maxDrawdown) * 0.3;

      if (score > bestScore) {
        bestScore = score;
        bestParams = { ...params };
      }

      results.push({
        parameters: params,
        score,
        metrics: {
          total_return: totalReturn,
          sharpe_ratio: sharpeRatio,
          max_drawdown: maxDrawdown,
          win_rate: winRate,
          total_trades: totalTrades
        }
      });
    }

    // Sort by score descending
    results.sort((a, b) => b.score - a.score);

    return {
      best_parameters: bestParams,
      best_score: bestScore,
      all_results: results,
      optimization_stats: {
        total_combinations: numResults,
        completed_combinations: results.length,
        best_generation: method === 'genetic_algorithm' ? Math.floor(Math.random() * (config.generations || 20)) : undefined,
        convergence_metric: method === 'genetic_algorithm' ? Math.random() * 0.1 : undefined
      }
    };
  };

  const applyBestParameters = (results: OptimizationResults) => {
    const updatedStrategy = {
      ...strategy,
      parameters: { ...strategy.parameters, ...results.best_parameters }
    };

    onStrategyUpdate(updatedStrategy);

    addNotification({
      type: 'success',
      title: 'Parameters Applied',
      message: 'Best parameters have been applied to your strategy'
    });
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'running': return 'text-blue-400 bg-blue-500/20';
      case 'completed': return 'text-green-400 bg-green-500/20';
      case 'failed': return 'text-red-400 bg-red-500/20';
      case 'cancelled': return 'text-yellow-400 bg-yellow-500/20';
      default: return 'text-gray-400 bg-gray-500/20';
    }
  };

  const getMethodIcon = (method: string) => {
    return method === 'grid_search' ? CpuChipIcon : RocketLaunchIcon;
  };

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="p-6 border-b border-gray-700 bg-gray-900/50">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-xl font-semibold text-white">Parameter Optimization</h3>
            <p className="text-gray-400 text-sm mt-1">
              Optimize strategy parameters using grid search or genetic algorithms
            </p>
          </div>

          <div className="flex items-center gap-3">
            {currentJob && currentJob.status === 'running' && (
              <Button
                variant="destructive"
                onClick={cancelOptimization}
                className="gap-2"
              >
                <StopIcon className="w-4 h-4" />
                Cancel
              </Button>
            )}

            <Button
              variant="outline"
              onClick={loadOptimizationHistory}
              className="gap-2"
            >
              <ArrowPathIcon className="w-4 h-4" />
              Refresh History
            </Button>
          </div>
        </div>

        {/* Current Job Status */}
        {currentJob && (
          <div className="mt-4 p-4 bg-gray-800/50 rounded-lg">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-3">
                {(() => {
                  const Icon = getMethodIcon(currentJob.method);
                  return <Icon className="w-5 h-5 text-blue-400" />;
                })()}
                <div>
                  <div className="font-medium text-white">
                    {currentJob.method === 'grid_search' ? 'Grid Search' : 'Genetic Algorithm'}
                  </div>
                  <div className={`text-xs px-2 py-0.5 rounded ${getStatusColor(currentJob.status)}`}>
                    {currentJob.status.replace('_', ' ').toUpperCase()}
                  </div>
                </div>
              </div>

              <div className="text-right text-sm text-gray-400">
                Started: {new Date(currentJob.startTime).toLocaleTimeString()}
                {currentJob.endTime && (
                  <div>
                    Completed: {new Date(currentJob.endTime).toLocaleTimeString()}
                  </div>
                )}
              </div>
            </div>

            {currentJob.status === 'running' && (
              <div className="mt-3">
                <div className="flex justify-between text-sm text-gray-400 mb-1">
                  <span>Progress</span>
                  <span>{Math.round(currentJob.progress)}%</span>
                </div>
                <div className="w-full bg-gray-700 rounded-full h-2">
                  <div
                    className="bg-blue-500 h-2 rounded-full transition-all duration-300"
                    style={{ width: `${currentJob.progress}%` }}
                  />
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Main Content */}
      <div className="flex-1 p-6">
        <Tabs value={activeTab} onValueChange={setActiveTab} className="h-full flex flex-col">
          <TabsList className="grid w-full grid-cols-3 bg-gray-800 mb-6">
            <TabsTrigger value="grid_search" className="gap-2">
              <CpuChipIcon className="w-4 h-4" />
              Grid Search
            </TabsTrigger>
            <TabsTrigger value="genetic_algorithm" className="gap-2">
              <RocketLaunchIcon className="w-4 h-4" />
              Genetic Algorithm
            </TabsTrigger>
            <TabsTrigger value="results" className="gap-2">
              <ChartBarIcon className="w-4 h-4" />
              Results
            </TabsTrigger>
          </TabsList>

          <div className="flex-1">
            <TabsContent value="grid_search" className="h-full">
              <GridSearchConfig
                strategy={strategy}
                onConfigChange={setGridSearchConfig}
                onStart={(config) => startOptimization('grid_search', config)}
                isRunning={currentJob?.status === 'running' && currentJob.method === 'grid_search'}
              />
            </TabsContent>

            <TabsContent value="genetic_algorithm" className="h-full">
              <GeneticAlgorithm
                strategy={strategy}
                onConfigChange={setGeneticConfig}
                onStart={(config) => startOptimization('genetic_algorithm', config)}
                isRunning={currentJob?.status === 'running' && currentJob.method === 'genetic_algorithm'}
              />
            </TabsContent>

            <TabsContent value="results" className="h-full">
              <OptimizationResults
                currentJob={currentJob}
                history={optimizationHistory}
                onApplyParameters={applyBestParameters}
                onDeleteJob={(jobId) => {
                  const newHistory = optimizationHistory.filter(job => job.id !== jobId);
                  setOptimizationHistory(newHistory);
                  saveOptimizationHistory(newHistory);
                }}
              />
            </TabsContent>
          </div>
        </Tabs>
      </div>
    </div>
  );
}
