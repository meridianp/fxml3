/**
 * Optimization Results Component
 *
 * Display and analyze optimization results from grid search and genetic algorithms
 */

'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import {
  ChartBarIcon,
  TrophyIcon,
  ArrowDownTrayIcon,
  TrashIcon,
  EyeIcon,
  CheckIcon,
  ClockIcon,
  CpuChipIcon,
  RocketLaunchIcon,
  ArrowTrendingUpIcon,
  ArrowTrendingDownIcon
} from '@heroicons/react/24/outline';

interface OptimizationJob {
  id: string;
  strategy: any;
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

interface OptimizationResultsProps {
  currentJob: OptimizationJob | null;
  history: OptimizationJob[];
  onApplyParameters: (results: OptimizationResults) => void;
  onDeleteJob: (jobId: string) => void;
}

export default function OptimizationResults({
  currentJob,
  history,
  onApplyParameters,
  onDeleteJob
}: OptimizationResultsProps) {
  const [selectedJob, setSelectedJob] = useState<OptimizationJob | null>(null);
  const [viewMode, setViewMode] = useState<'summary' | 'detailed' | 'comparison'>('summary');
  const [sortBy, setSortBy] = useState<'score' | 'return' | 'sharpe' | 'drawdown'>('score');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');

  const allJobs = currentJob ? [currentJob, ...history] : history;
  const completedJobs = allJobs.filter(job => job.status === 'completed' && job.results);

  const formatDuration = (start: string, end?: string) => {
    const startTime = new Date(start).getTime();
    const endTime = end ? new Date(end).getTime() : Date.now();
    const duration = Math.round((endTime - startTime) / 1000);

    if (duration < 60) return `${duration}s`;
    if (duration < 3600) return `${Math.round(duration / 60)}m`;
    return `${Math.round(duration / 3600)}h`;
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

  const exportResults = (job: OptimizationJob) => {
    if (!job.results) return;

    const data = {
      job_info: {
        id: job.id,
        method: job.method,
        strategy: job.strategy.name,
        start_time: job.startTime,
        end_time: job.endTime,
        duration: formatDuration(job.startTime, job.endTime)
      },
      best_parameters: job.results.best_parameters,
      best_score: job.results.best_score,
      all_results: job.results.all_results,
      stats: job.results.optimization_stats
    };

    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `optimization_results_${job.id}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const sortResults = (results: OptimizationResults['all_results']) => {
    return [...results].sort((a, b) => {
      let aVal, bVal;

      switch (sortBy) {
        case 'score':
          aVal = a.score;
          bVal = b.score;
          break;
        case 'return':
          aVal = a.metrics.total_return;
          bVal = b.metrics.total_return;
          break;
        case 'sharpe':
          aVal = a.metrics.sharpe_ratio;
          bVal = b.metrics.sharpe_ratio;
          break;
        case 'drawdown':
          aVal = a.metrics.max_drawdown;
          bVal = b.metrics.max_drawdown;
          break;
        default:
          aVal = a.score;
          bVal = b.score;
      }

      return sortOrder === 'desc' ? bVal - aVal : aVal - bVal;
    });
  };

  const renderJobSummary = (job: OptimizationJob) => {
    if (!job.results) return null;

    const best = job.results.all_results[0];
    const MethodIcon = getMethodIcon(job.method);

    return (
      <div
        key={job.id}
        className={`border rounded-lg p-4 cursor-pointer transition-all ${
          selectedJob?.id === job.id ? 'border-blue-500 bg-blue-500/10' : 'border-gray-700 bg-gray-800/50 hover:border-gray-600'
        }`}
        onClick={() => setSelectedJob(selectedJob?.id === job.id ? null : job)}
      >
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-gray-700 rounded-lg flex items-center justify-center">
              <MethodIcon className="w-5 h-5 text-gray-300" />
            </div>
            <div>
              <div className="font-medium text-white">
                {job.method === 'grid_search' ? 'Grid Search' : 'Genetic Algorithm'}
              </div>
              <div className="text-sm text-gray-400">
                {new Date(job.startTime).toLocaleString()}
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <span className={`text-xs px-2 py-1 rounded ${getStatusColor(job.status)}`}>
              {job.status.replace('_', ' ').toUpperCase()}
            </span>
            <div className="flex items-center gap-1">
              <Button
                size="sm"
                variant="outline"
                onClick={(e) => {
                  e.stopPropagation();
                  exportResults(job);
                }}
                className="p-1"
              >
                <ArrowDownTrayIcon className="w-3 h-3" />
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={(e) => {
                  e.stopPropagation();
                  onDeleteJob(job.id);
                }}
                className="p-1 text-red-400 hover:text-red-300"
              >
                <TrashIcon className="w-3 h-3" />
              </Button>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-4 gap-3 text-sm">
          <div className="bg-gray-800/50 rounded p-2 text-center">
            <div className="text-green-400 font-bold">{(best.metrics.total_return * 100).toFixed(1)}%</div>
            <div className="text-gray-400 text-xs">Return</div>
          </div>
          <div className="bg-gray-800/50 rounded p-2 text-center">
            <div className="text-blue-400 font-bold">{best.metrics.sharpe_ratio.toFixed(2)}</div>
            <div className="text-gray-400 text-xs">Sharpe</div>
          </div>
          <div className="bg-gray-800/50 rounded p-2 text-center">
            <div className="text-red-400 font-bold">{(best.metrics.max_drawdown * 100).toFixed(1)}%</div>
            <div className="text-gray-400 text-xs">Drawdown</div>
          </div>
          <div className="bg-gray-800/50 rounded p-2 text-center">
            <div className="text-purple-400 font-bold">{best.score.toFixed(3)}</div>
            <div className="text-gray-400 text-xs">Score</div>
          </div>
        </div>

        <div className="mt-3 flex items-center justify-between text-xs text-gray-500">
          <span>Duration: {formatDuration(job.startTime, job.endTime)}</span>
          <span>{job.results.optimization_stats.completed_combinations} evaluations</span>
        </div>
      </div>
    );
  };

  const renderDetailedResults = (job: OptimizationJob) => {
    if (!job.results) return null;

    const sortedResults = sortResults(job.results.all_results.slice(0, 20)); // Top 20 results

    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h4 className="text-lg font-semibold text-white">
            Top Results - {job.method === 'grid_search' ? 'Grid Search' : 'Genetic Algorithm'}
          </h4>

          <div className="flex items-center gap-2">
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as any)}
              className="px-2 py-1 bg-gray-800 border border-gray-600 rounded text-sm text-white"
            >
              <option value="score">Score</option>
              <option value="return">Return</option>
              <option value="sharpe">Sharpe Ratio</option>
              <option value="drawdown">Max Drawdown</option>
            </select>

            <Button
              size="sm"
              variant="outline"
              onClick={() => setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')}
              className="p-1"
            >
              {sortOrder === 'desc' ? <ArrowTrendingDownIcon className="w-4 h-4" /> : <ArrowTrendingUpIcon className="w-4 h-4" />}
            </Button>
          </div>
        </div>

        <div className="bg-gray-800/50 rounded-lg overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-700/50">
                <tr>
                  <th className="px-3 py-2 text-left text-gray-300">Rank</th>
                  <th className="px-3 py-2 text-left text-gray-300">Score</th>
                  <th className="px-3 py-2 text-left text-gray-300">Return</th>
                  <th className="px-3 py-2 text-left text-gray-300">Sharpe</th>
                  <th className="px-3 py-2 text-left text-gray-300">Drawdown</th>
                  <th className="px-3 py-2 text-left text-gray-300">Win Rate</th>
                  <th className="px-3 py-2 text-left text-gray-300">Trades</th>
                  <th className="px-3 py-2 text-left text-gray-300">Action</th>
                </tr>
              </thead>
              <tbody>
                {sortedResults.map((result, index) => (
                  <tr key={index} className={`border-t border-gray-700 ${index === 0 ? 'bg-green-500/10' : 'hover:bg-gray-700/30'}`}>
                    <td className="px-3 py-2">
                      <div className="flex items-center gap-2">
                        {index === 0 && <TrophyIcon className="w-4 h-4 text-yellow-400" />}
                        <span className="text-white">#{index + 1}</span>
                      </div>
                    </td>
                    <td className="px-3 py-2 font-bold text-purple-400">{result.score.toFixed(3)}</td>
                    <td className={`px-3 py-2 font-medium ${result.metrics.total_return >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {(result.metrics.total_return * 100).toFixed(1)}%
                    </td>
                    <td className="px-3 py-2 text-blue-400">{result.metrics.sharpe_ratio.toFixed(2)}</td>
                    <td className="px-3 py-2 text-red-400">{(result.metrics.max_drawdown * 100).toFixed(1)}%</td>
                    <td className="px-3 py-2 text-gray-300">{(result.metrics.win_rate * 100).toFixed(1)}%</td>
                    <td className="px-3 py-2 text-gray-300">{result.metrics.total_trades}</td>
                    <td className="px-3 py-2">
                      <Button
                        size="sm"
                        onClick={() => onApplyParameters({ ...job.results!, best_parameters: result.parameters, best_score: result.score })}
                        className="gap-1"
                      >
                        <CheckIcon className="w-3 h-3" />
                        Apply
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Parameter Details for Best Result */}
        {sortedResults.length > 0 && (
          <div className="bg-gray-900 border border-gray-700 rounded-lg p-4">
            <h5 className="font-medium text-white mb-3">Best Parameters</h5>
            <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
              {Object.entries(sortedResults[0].parameters).map(([key, value]) => (
                <div key={key} className="bg-gray-800/50 rounded p-2">
                  <div className="text-xs text-gray-400">{key}</div>
                  <div className="font-medium text-white">{String(value)}</div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="h-full">
      {completedJobs.length === 0 && !currentJob ? (
        <div className="text-center py-12">
          <ChartBarIcon className="w-16 h-16 text-gray-400 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-300 mb-2">No Optimization Results</h3>
          <p className="text-gray-400">
            Run a grid search or genetic algorithm optimization to see results here
          </p>
        </div>
      ) : (
        <div className="space-y-6">
          {/* Current Job Status */}
          {currentJob && currentJob.status === 'running' && (
            <div className="bg-gray-900 border border-gray-700 rounded-lg p-6">
              <div className="flex items-center gap-3 mb-4">
                <div className="w-3 h-3 bg-blue-500 rounded-full animate-pulse"></div>
                <h3 className="text-lg font-semibold text-white">Optimization in Progress</h3>
              </div>
              <div className="grid grid-cols-3 gap-4">
                <div className="text-center">
                  <div className="text-2xl font-bold text-blue-400">{Math.round(currentJob.progress)}%</div>
                  <div className="text-sm text-gray-400">Progress</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-yellow-400">
                    {formatDuration(currentJob.startTime)}
                  </div>
                  <div className="text-sm text-gray-400">Elapsed</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-green-400">
                    {currentJob.method === 'grid_search' ? 'Grid' : 'Genetic'}
                  </div>
                  <div className="text-sm text-gray-400">Method</div>
                </div>
              </div>
              <div className="mt-4">
                <div className="w-full bg-gray-700 rounded-full h-2">
                  <div
                    className="bg-blue-500 h-2 rounded-full transition-all duration-300"
                    style={{ width: `${currentJob.progress}%` }}
                  />
                </div>
              </div>
            </div>
          )}

          {/* Results Summary */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold text-white">Optimization History</h3>
              <div className="flex items-center gap-2">
                <Button
                  size="sm"
                  variant={viewMode === 'summary' ? 'default' : 'outline'}
                  onClick={() => setViewMode('summary')}
                >
                  Summary
                </Button>
                <Button
                  size="sm"
                  variant={viewMode === 'detailed' ? 'default' : 'outline'}
                  onClick={() => setViewMode('detailed')}
                  disabled={!selectedJob}
                >
                  Detailed
                </Button>
              </div>
            </div>

            {viewMode === 'summary' ? (
              <div className="space-y-4">
                {completedJobs.map(renderJobSummary)}
              </div>
            ) : selectedJob ? (
              renderDetailedResults(selectedJob)
            ) : (
              <div className="text-center py-8 text-gray-400">
                <EyeIcon className="w-12 h-12 mx-auto mb-3 opacity-50" />
                <p>Select a job to view detailed results</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
