/**
 * Genetic Algorithm Configuration Component
 *
 * Configure genetic algorithm parameters for optimization
 */

'use client';

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import {
  RocketLaunchIcon,
  PlayIcon,
  InformationCircleIcon,
  BeakerIcon,
  ChartLineIcon,
  Cog6ToothIcon,
  AdjustmentsHorizontalIcon
} from '@heroicons/react/24/outline';

interface Strategy {
  id: string;
  name: string;
  type: string;
  parameters: Record<string, any>;
}

interface GeneticConfig {
  population_size: number;
  generations: number;
  mutation_rate: number;
  crossover_rate: number;
  elitism_rate: number;
  convergence_threshold: number;
  early_stopping: boolean;
  selection_method: 'tournament' | 'roulette' | 'rank';
  crossover_method: 'uniform' | 'single_point' | 'two_point';
  mutation_method: 'gaussian' | 'uniform' | 'polynomial';
  fitness_function: 'sharpe_ratio' | 'total_return' | 'profit_factor' | 'custom';
}

interface GeneticAlgorithmProps {
  strategy: Strategy;
  onConfigChange: (config: any) => void;
  onStart: (config: any) => void;
  isRunning: boolean;
}

export default function GeneticAlgorithm({
  strategy,
  onConfigChange,
  onStart,
  isRunning
}: GeneticAlgorithmProps) {
  const [config, setConfig] = useState<GeneticConfig>({
    population_size: 50,
    generations: 100,
    mutation_rate: 0.1,
    crossover_rate: 0.8,
    elitism_rate: 0.1,
    convergence_threshold: 0.001,
    early_stopping: true,
    selection_method: 'tournament',
    crossover_method: 'uniform',
    mutation_method: 'gaussian',
    fitness_function: 'sharpe_ratio'
  });

  const [estimatedEvaluations, setEstimatedEvaluations] = useState(0);
  const [estimatedTime, setEstimatedTime] = useState(0);
  const [parameterBounds, setParameterBounds] = useState<Record<string, { min: number; max: number }>>({});

  useEffect(() => {
    initializeParameterBounds();
  }, [strategy]);

  useEffect(() => {
    calculateEstimates();
    onConfigChange(generateGeneticConfig());
  }, [config, parameterBounds]);

  const initializeParameterBounds = () => {
    const bounds: Record<string, { min: number; max: number }> = {};

    Object.entries(strategy.parameters).forEach(([key, value]) => {
      if (typeof value === 'number') {
        bounds[key] = {
          min: Math.max(0.01, value * 0.1),
          max: value * 10
        };
      }
    });

    setParameterBounds(bounds);
  };

  const calculateEstimates = () => {
    const evaluations = config.population_size * config.generations;
    setEstimatedEvaluations(evaluations);

    // Estimate 3-5 seconds per evaluation
    const avgEvaluationTime = 4;
    setEstimatedTime(evaluations * avgEvaluationTime);
  };

  const generateGeneticConfig = () => {
    return {
      method: 'genetic_algorithm',
      ...config,
      parameter_bounds: parameterBounds,
      estimated_evaluations: estimatedEvaluations
    };
  };

  const updateConfig = (updates: Partial<GeneticConfig>) => {
    const newConfig = { ...config, ...updates };
    setConfig(newConfig);
  };

  const updateParameterBounds = (parameter: string, bounds: { min: number; max: number }) => {
    setParameterBounds(prev => ({
      ...prev,
      [parameter]: bounds
    }));
  };

  const handleStart = () => {
    onStart(generateGeneticConfig());
  };

  const formatTime = (seconds: number): string => {
    if (seconds < 60) return `${Math.round(seconds)}s`;
    if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
    if (seconds < 86400) return `${Math.round(seconds / 3600)}h`;
    return `${Math.round(seconds / 86400)}d`;
  };

  const getMethodDescription = (type: string, method: string): string => {
    const descriptions: Record<string, Record<string, string>> = {
      selection: {
        tournament: 'Select parents by tournament competition among random individuals',
        roulette: 'Select parents based on fitness-proportionate probability',
        rank: 'Select parents based on fitness ranking rather than absolute values'
      },
      crossover: {
        uniform: 'Each gene has equal probability of coming from either parent',
        single_point: 'Single crossover point divides parent genes',
        two_point: 'Two crossover points create three gene segments'
      },
      mutation: {
        gaussian: 'Add random noise from normal distribution',
        uniform: 'Replace with random value within bounds',
        polynomial: 'Bounded polynomial mutation with configurable distribution'
      },
      fitness: {
        sharpe_ratio: 'Risk-adjusted returns (return/volatility)',
        total_return: 'Absolute return percentage',
        profit_factor: 'Ratio of gross profit to gross loss',
        custom: 'Custom weighted combination of metrics'
      }
    };

    return descriptions[type]?.[method] || 'No description available';
  };

  const numericParameters = Object.keys(strategy.parameters).filter(key =>
    typeof strategy.parameters[key] === 'number'
  );

  const canStart = numericParameters.length > 0 && config.population_size > 0 && config.generations > 0;

  return (
    <div className="h-full space-y-6">
      {/* Header */}
      <div className="bg-gray-900 border border-gray-700 rounded-lg p-6">
        <div className="flex items-center gap-3 mb-4">
          <RocketLaunchIcon className="w-6 h-6 text-purple-400" />
          <div>
            <h3 className="text-lg font-semibold text-white">Genetic Algorithm Configuration</h3>
            <p className="text-gray-400 text-sm">
              Evolutionary optimization using genetic algorithms
            </p>
          </div>
        </div>

        {/* Estimates */}
        <div className="grid grid-cols-3 gap-4 mb-4">
          <div className="bg-gray-800/50 rounded-lg p-3 text-center">
            <div className="text-2xl font-bold text-purple-400">{estimatedEvaluations.toLocaleString()}</div>
            <div className="text-sm text-gray-400">Evaluations</div>
          </div>
          <div className="bg-gray-800/50 rounded-lg p-3 text-center">
            <div className="text-2xl font-bold text-yellow-400">{formatTime(estimatedTime)}</div>
            <div className="text-sm text-gray-400">Estimated Time</div>
          </div>
          <div className="bg-gray-800/50 rounded-lg p-3 text-center">
            <div className="text-2xl font-bold text-green-400">{numericParameters.length}</div>
            <div className="text-sm text-gray-400">Parameters</div>
          </div>
        </div>

        <div className="flex justify-end">
          <Button
            onClick={handleStart}
            disabled={!canStart || isRunning}
            className="gap-2"
          >
            {isRunning ? (
              <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
            ) : (
              <PlayIcon className="w-4 h-4" />
            )}
            Start Evolution
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Population & Generation Settings */}
        <div className="bg-gray-900 border border-gray-700 rounded-lg p-6">
          <div className="flex items-center gap-2 mb-4">
            <BeakerIcon className="w-5 h-5 text-blue-400" />
            <h4 className="text-lg font-semibold text-white">Population Settings</h4>
          </div>

          <div className="space-y-4">
            <div>
              <label className="block text-sm text-gray-300 mb-2">Population Size</label>
              <input
                type="number"
                value={config.population_size}
                onChange={(e) => updateConfig({ population_size: Math.max(10, parseInt(e.target.value) || 10) })}
                min="10"
                max="200"
                className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded text-white"
              />
              <p className="text-xs text-gray-500 mt-1">Number of individuals in each generation (10-200)</p>
            </div>

            <div>
              <label className="block text-sm text-gray-300 mb-2">Generations</label>
              <input
                type="number"
                value={config.generations}
                onChange={(e) => updateConfig({ generations: Math.max(10, parseInt(e.target.value) || 10) })}
                min="10"
                max="500"
                className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded text-white"
              />
              <p className="text-xs text-gray-500 mt-1">Maximum number of generations (10-500)</p>
            </div>

            <div>
              <label className="block text-sm text-gray-300 mb-2">Elitism Rate</label>
              <input
                type="range"
                value={config.elitism_rate}
                onChange={(e) => updateConfig({ elitism_rate: parseFloat(e.target.value) })}
                min="0"
                max="0.3"
                step="0.01"
                className="w-full"
              />
              <div className="flex justify-between text-xs text-gray-400 mt-1">
                <span>0%</span>
                <span>{Math.round(config.elitism_rate * 100)}%</span>
                <span>30%</span>
              </div>
              <p className="text-xs text-gray-500 mt-1">Percentage of best individuals preserved</p>
            </div>
          </div>
        </div>

        {/* Genetic Operators */}
        <div className="bg-gray-900 border border-gray-700 rounded-lg p-6">
          <div className="flex items-center gap-2 mb-4">
            <Cog6ToothIcon className="w-5 h-5 text-green-400" />
            <h4 className="text-lg font-semibold text-white">Genetic Operators</h4>
          </div>

          <div className="space-y-4">
            <div>
              <label className="block text-sm text-gray-300 mb-2">Crossover Rate</label>
              <input
                type="range"
                value={config.crossover_rate}
                onChange={(e) => updateConfig({ crossover_rate: parseFloat(e.target.value) })}
                min="0.5"
                max="1.0"
                step="0.01"
                className="w-full"
              />
              <div className="flex justify-between text-xs text-gray-400 mt-1">
                <span>50%</span>
                <span>{Math.round(config.crossover_rate * 100)}%</span>
                <span>100%</span>
              </div>
            </div>

            <div>
              <label className="block text-sm text-gray-300 mb-2">Mutation Rate</label>
              <input
                type="range"
                value={config.mutation_rate}
                onChange={(e) => updateConfig({ mutation_rate: parseFloat(e.target.value) })}
                min="0.01"
                max="0.3"
                step="0.01"
                className="w-full"
              />
              <div className="flex justify-between text-xs text-gray-400 mt-1">
                <span>1%</span>
                <span>{Math.round(config.mutation_rate * 100)}%</span>
                <span>30%</span>
              </div>
            </div>

            <div>
              <label className="block text-sm text-gray-300 mb-2">Selection Method</label>
              <select
                value={config.selection_method}
                onChange={(e) => updateConfig({ selection_method: e.target.value as any })}
                className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded text-white"
              >
                <option value="tournament">Tournament Selection</option>
                <option value="roulette">Roulette Wheel</option>
                <option value="rank">Rank-based Selection</option>
              </select>
              <p className="text-xs text-gray-500 mt-1">
                {getMethodDescription('selection', config.selection_method)}
              </p>
            </div>
          </div>
        </div>

        {/* Advanced Settings */}
        <div className="bg-gray-900 border border-gray-700 rounded-lg p-6">
          <div className="flex items-center gap-2 mb-4">
            <AdjustmentsHorizontalIcon className="w-5 h-5 text-yellow-400" />
            <h4 className="text-lg font-semibold text-white">Advanced Settings</h4>
          </div>

          <div className="space-y-4">
            <div>
              <label className="block text-sm text-gray-300 mb-2">Crossover Method</label>
              <select
                value={config.crossover_method}
                onChange={(e) => updateConfig({ crossover_method: e.target.value as any })}
                className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded text-white"
              >
                <option value="uniform">Uniform Crossover</option>
                <option value="single_point">Single Point</option>
                <option value="two_point">Two Point</option>
              </select>
              <p className="text-xs text-gray-500 mt-1">
                {getMethodDescription('crossover', config.crossover_method)}
              </p>
            </div>

            <div>
              <label className="block text-sm text-gray-300 mb-2">Mutation Method</label>
              <select
                value={config.mutation_method}
                onChange={(e) => updateConfig({ mutation_method: e.target.value as any })}
                className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded text-white"
              >
                <option value="gaussian">Gaussian</option>
                <option value="uniform">Uniform</option>
                <option value="polynomial">Polynomial</option>
              </select>
              <p className="text-xs text-gray-500 mt-1">
                {getMethodDescription('mutation', config.mutation_method)}
              </p>
            </div>

            <div>
              <label className="block text-sm text-gray-300 mb-2">Fitness Function</label>
              <select
                value={config.fitness_function}
                onChange={(e) => updateConfig({ fitness_function: e.target.value as any })}
                className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded text-white"
              >
                <option value="sharpe_ratio">Sharpe Ratio</option>
                <option value="total_return">Total Return</option>
                <option value="profit_factor">Profit Factor</option>
                <option value="custom">Custom Weighted</option>
              </select>
              <p className="text-xs text-gray-500 mt-1">
                {getMethodDescription('fitness', config.fitness_function)}
              </p>
            </div>

            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="early_stopping"
                checked={config.early_stopping}
                onChange={(e) => updateConfig({ early_stopping: e.target.checked })}
                className="w-4 h-4 text-blue-500 bg-gray-800 border-gray-600 rounded focus:ring-blue-500"
              />
              <label htmlFor="early_stopping" className="text-sm text-gray-300">
                Enable Early Stopping
              </label>
            </div>

            {config.early_stopping && (
              <div>
                <label className="block text-sm text-gray-300 mb-2">Convergence Threshold</label>
                <input
                  type="number"
                  value={config.convergence_threshold}
                  onChange={(e) => updateConfig({ convergence_threshold: parseFloat(e.target.value) || 0.001 })}
                  min="0.0001"
                  max="0.01"
                  step="0.0001"
                  className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded text-white"
                />
                <p className="text-xs text-gray-500 mt-1">Stop when fitness improvement falls below threshold</p>
              </div>
            )}
          </div>
        </div>

        {/* Parameter Bounds */}
        <div className="bg-gray-900 border border-gray-700 rounded-lg p-6">
          <div className="flex items-center gap-2 mb-4">
            <ChartLineIcon className="w-5 h-5 text-red-400" />
            <h4 className="text-lg font-semibold text-white">Parameter Bounds</h4>
          </div>

          {numericParameters.length > 0 ? (
            <div className="space-y-4">
              {numericParameters.map(param => {
                const currentValue = strategy.parameters[param];
                const bounds = parameterBounds[param] || { min: 0, max: 100 };

                return (
                  <div key={param} className="border border-gray-700 rounded p-3">
                    <div className="flex items-center justify-between mb-2">
                      <span className="font-medium text-white">{param}</span>
                      <span className="text-sm text-gray-400">
                        Current: {currentValue}
                      </span>
                    </div>

                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="block text-xs text-gray-400 mb-1">Min</label>
                        <input
                          type="number"
                          value={bounds.min}
                          onChange={(e) => updateParameterBounds(param, {
                            ...bounds,
                            min: parseFloat(e.target.value) || 0
                          })}
                          step="any"
                          className="w-full px-2 py-1 bg-gray-800 border border-gray-600 rounded text-white text-sm"
                        />
                      </div>
                      <div>
                        <label className="block text-xs text-gray-400 mb-1">Max</label>
                        <input
                          type="number"
                          value={bounds.max}
                          onChange={(e) => updateParameterBounds(param, {
                            ...bounds,
                            max: parseFloat(e.target.value) || 0
                          })}
                          step="any"
                          className="w-full px-2 py-1 bg-gray-800 border border-gray-600 rounded text-white text-sm"
                        />
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="text-center py-8 text-gray-400">
              <InformationCircleIcon className="w-12 h-12 mx-auto mb-3 opacity-50" />
              <p>No numeric parameters found</p>
              <p className="text-sm">Genetic algorithm requires numeric parameters to optimize</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
