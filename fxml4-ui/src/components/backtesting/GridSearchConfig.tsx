/**
 * Grid Search Configuration Component
 *
 * Configure grid search parameter ranges and constraints
 */

'use client';

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import {
  CpuChipIcon,
  PlayIcon,
  InformationCircleIcon,
  AdjustmentsHorizontalIcon,
  ExclamationTriangleIcon,
  CalculatorIcon
} from '@heroicons/react/24/outline';

interface Strategy {
  id: string;
  name: string;
  type: string;
  parameters: Record<string, any>;
}

interface ParameterRange {
  parameter: string;
  enabled: boolean;
  type: 'range' | 'list' | 'boolean';
  min?: number;
  max?: number;
  step?: number;
  values?: any[];
  current_value: any;
}

interface GridSearchConfigProps {
  strategy: Strategy;
  onConfigChange: (config: any) => void;
  onStart: (config: any) => void;
  isRunning: boolean;
}

export default function GridSearchConfig({
  strategy,
  onConfigChange,
  onStart,
  isRunning
}: GridSearchConfigProps) {
  const [parameterRanges, setParameterRanges] = useState<ParameterRange[]>([]);
  const [estimatedCombinations, setEstimatedCombinations] = useState(0);
  const [estimatedTime, setEstimatedTime] = useState(0);
  const [maxCombinations, setMaxCombinations] = useState(1000);

  useEffect(() => {
    initializeParameterRanges();
  }, [strategy]);

  useEffect(() => {
    calculateEstimates();
  }, [parameterRanges]);

  const initializeParameterRanges = () => {
    const ranges: ParameterRange[] = [];

    Object.entries(strategy.parameters).forEach(([key, value]) => {
      const range: ParameterRange = {
        parameter: key,
        enabled: false,
        type: getParameterType(key, value),
        current_value: value
      };

      // Set default ranges based on parameter type and value
      if (typeof value === 'number') {
        range.type = 'range';
        range.min = Math.max(0.1, value * 0.5);
        range.max = value * 2;
        range.step = value * 0.1;
      } else if (typeof value === 'boolean') {
        range.type = 'boolean';
        range.values = [true, false];
      } else if (typeof value === 'string') {
        range.type = 'list';
        range.values = getStringParameterOptions(key, value);
      }

      ranges.push(range);
    });

    setParameterRanges(ranges);
  };

  const getParameterType = (key: string, value: any): 'range' | 'list' | 'boolean' => {
    if (typeof value === 'boolean') return 'boolean';
    if (typeof value === 'number') return 'range';
    return 'list';
  };

  const getStringParameterOptions = (key: string, currentValue: string): string[] => {
    // Define common parameter options based on key name
    const optionMap: Record<string, string[]> = {
      'ma_type': ['sma', 'ema', 'wma', 'hull'],
      'model_type': ['neural_network', 'random_forest', 'xgboost', 'lstm'],
      'entry_method': ['band_touch', 'band_break', 'squeeze'],
      'exit_method': ['middle_band', 'opposite_band', 'percent_b'],
      'wave_degree': ['minute', 'minor', 'intermediate', 'primary', 'cycle'],
      'wave_completion_method': ['fibonacci', 'time', 'hybrid'],
      'feature_set': ['basic', 'technical', 'comprehensive']
    };

    return optionMap[key] || [currentValue];
  };

  const calculateEstimates = () => {
    let combinations = 1;

    parameterRanges.forEach(range => {
      if (range.enabled) {
        if (range.type === 'range' && range.min !== undefined && range.max !== undefined && range.step !== undefined) {
          const steps = Math.floor((range.max - range.min) / range.step) + 1;
          combinations *= Math.max(1, steps);
        } else if (range.type === 'list' && range.values) {
          combinations *= range.values.length;
        } else if (range.type === 'boolean') {
          combinations *= 2;
        }
      }
    });

    setEstimatedCombinations(combinations);

    // Estimate time: ~2-5 seconds per backtest
    const avgBacktestTime = 3.5;
    setEstimatedTime(combinations * avgBacktestTime);
  };

  const updateParameterRange = (index: number, updates: Partial<ParameterRange>) => {
    const newRanges = [...parameterRanges];
    newRanges[index] = { ...newRanges[index], ...updates };
    setParameterRanges(newRanges);

    // Update config
    const config = generateGridSearchConfig(newRanges);
    onConfigChange(config);
  };

  const generateGridSearchConfig = (ranges: ParameterRange[]) => {
    const config: any = {
      method: 'grid_search',
      parameter_ranges: {},
      max_combinations: maxCombinations,
      total_combinations: estimatedCombinations
    };

    ranges.forEach(range => {
      if (range.enabled) {
        if (range.type === 'range') {
          config.parameter_ranges[range.parameter] = {
            type: 'range',
            min: range.min,
            max: range.max,
            step: range.step
          };
        } else if (range.type === 'list') {
          config.parameter_ranges[range.parameter] = {
            type: 'list',
            values: range.values
          };
        } else if (range.type === 'boolean') {
          config.parameter_ranges[range.parameter] = {
            type: 'boolean',
            values: [true, false]
          };
        }
      }
    });

    return config;
  };

  const handleStart = () => {
    const config = generateGridSearchConfig(parameterRanges);
    onStart(config);
  };

  const formatTime = (seconds: number): string => {
    if (seconds < 60) return `${Math.round(seconds)}s`;
    if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
    if (seconds < 86400) return `${Math.round(seconds / 3600)}h`;
    return `${Math.round(seconds / 86400)}d`;
  };

  const enabledCount = parameterRanges.filter(r => r.enabled).length;
  const canStart = enabledCount > 0 && estimatedCombinations > 0 && estimatedCombinations <= maxCombinations;

  return (
    <div className="h-full space-y-6">
      {/* Header */}
      <div className="bg-gray-900 border border-gray-700 rounded-lg p-6">
        <div className="flex items-center gap-3 mb-4">
          <CpuChipIcon className="w-6 h-6 text-blue-400" />
          <div>
            <h3 className="text-lg font-semibold text-white">Grid Search Configuration</h3>
            <p className="text-gray-400 text-sm">
              Define parameter ranges to systematically test all combinations
            </p>
          </div>
        </div>

        {/* Estimates */}
        <div className="grid grid-cols-3 gap-4">
          <div className="bg-gray-800/50 rounded-lg p-3 text-center">
            <div className="text-2xl font-bold text-blue-400">{estimatedCombinations.toLocaleString()}</div>
            <div className="text-sm text-gray-400">Total Combinations</div>
          </div>
          <div className="bg-gray-800/50 rounded-lg p-3 text-center">
            <div className="text-2xl font-bold text-yellow-400">{formatTime(estimatedTime)}</div>
            <div className="text-sm text-gray-400">Estimated Time</div>
          </div>
          <div className="bg-gray-800/50 rounded-lg p-3 text-center">
            <div className="text-2xl font-bold text-green-400">{enabledCount}</div>
            <div className="text-sm text-gray-400">Parameters</div>
          </div>
        </div>

        {estimatedCombinations > maxCombinations && (
          <div className="mt-4 p-3 bg-red-500/10 border border-red-500/30 rounded-lg flex items-start gap-2">
            <ExclamationTriangleIcon className="w-5 h-5 text-red-400 mt-0.5 flex-shrink-0" />
            <div className="text-sm text-red-300">
              <strong>Too many combinations!</strong> Reduce parameter ranges or increase max combinations limit.
              Current: {estimatedCombinations.toLocaleString()}, Max: {maxCombinations.toLocaleString()}
            </div>
          </div>
        )}

        <div className="mt-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <label className="text-sm text-gray-300">
              Max Combinations:
            </label>
            <input
              type="number"
              value={maxCombinations}
              onChange={(e) => setMaxCombinations(Math.max(1, parseInt(e.target.value) || 1))}
              min="1"
              max="10000"
              className="w-24 px-2 py-1 bg-gray-800 border border-gray-600 rounded text-white text-sm"
            />
          </div>

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
            Start Grid Search
          </Button>
        </div>
      </div>

      {/* Parameter Configuration */}
      <div className="bg-gray-900 border border-gray-700 rounded-lg p-6">
        <div className="flex items-center gap-2 mb-4">
          <AdjustmentsHorizontalIcon className="w-5 h-5 text-blue-400" />
          <h4 className="text-lg font-semibold text-white">Parameter Ranges</h4>
        </div>

        <div className="space-y-4">
          {parameterRanges.map((range, index) => (
            <div key={range.parameter} className="border border-gray-700 rounded-lg p-4">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-3">
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={range.enabled}
                      onChange={(e) => updateParameterRange(index, { enabled: e.target.checked })}
                      className="w-4 h-4 text-blue-500 bg-gray-800 border-gray-600 rounded focus:ring-blue-500"
                    />
                    <span className="font-medium text-white">{range.parameter}</span>
                  </label>
                  <span className="text-xs px-2 py-0.5 bg-gray-700 text-gray-300 rounded">
                    {range.type}
                  </span>
                </div>

                <div className="text-sm text-gray-400">
                  Current: <span className="text-white">{String(range.current_value)}</span>
                </div>
              </div>

              {range.enabled && (
                <div className="mt-3 pl-6">
                  {range.type === 'range' && (
                    <div className="grid grid-cols-3 gap-3">
                      <div>
                        <label className="block text-xs text-gray-400 mb-1">Min</label>
                        <input
                          type="number"
                          value={range.min || 0}
                          onChange={(e) => updateParameterRange(index, { min: parseFloat(e.target.value) || 0 })}
                          step="any"
                          className="w-full px-2 py-1 bg-gray-800 border border-gray-600 rounded text-white text-sm"
                        />
                      </div>
                      <div>
                        <label className="block text-xs text-gray-400 mb-1">Max</label>
                        <input
                          type="number"
                          value={range.max || 0}
                          onChange={(e) => updateParameterRange(index, { max: parseFloat(e.target.value) || 0 })}
                          step="any"
                          className="w-full px-2 py-1 bg-gray-800 border border-gray-600 rounded text-white text-sm"
                        />
                      </div>
                      <div>
                        <label className="block text-xs text-gray-400 mb-1">Step</label>
                        <input
                          type="number"
                          value={range.step || 0}
                          onChange={(e) => updateParameterRange(index, { step: parseFloat(e.target.value) || 0 })}
                          step="any"
                          min="0.001"
                          className="w-full px-2 py-1 bg-gray-800 border border-gray-600 rounded text-white text-sm"
                        />
                      </div>
                    </div>
                  )}

                  {range.type === 'list' && (
                    <div>
                      <label className="block text-xs text-gray-400 mb-2">Values to test</label>
                      <div className="flex flex-wrap gap-2">
                        {range.values?.map((value, valueIndex) => (
                          <label key={valueIndex} className="flex items-center gap-1">
                            <input
                              type="checkbox"
                              defaultChecked={true}
                              className="w-3 h-3 text-blue-500 bg-gray-800 border-gray-600 rounded"
                            />
                            <span className="text-sm text-gray-300">{String(value)}</span>
                          </label>
                        ))}
                      </div>
                    </div>
                  )}

                  {range.type === 'boolean' && (
                    <div className="text-sm text-gray-400">
                      Will test both <span className="text-white">true</span> and <span className="text-white">false</span> values
                    </div>
                  )}

                  {range.type === 'range' && range.min !== undefined && range.max !== undefined && range.step !== undefined && (
                    <div className="mt-2 flex items-center gap-2 text-xs text-gray-500">
                      <CalculatorIcon className="w-3 h-3" />
                      <span>
                        {Math.floor((range.max - range.min) / range.step) + 1} values will be tested
                      </span>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>

        {parameterRanges.length === 0 && (
          <div className="text-center py-8 text-gray-400">
            <InformationCircleIcon className="w-12 h-12 mx-auto mb-3 opacity-50" />
            <p>No parameters available for optimization</p>
            <p className="text-sm">Make sure your strategy has configurable parameters</p>
          </div>
        )}
      </div>
    </div>
  );
}
