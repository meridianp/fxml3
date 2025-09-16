/**
 * Parameter Configuration Component
 *
 * Dynamic parameter configuration interface for different strategy types
 */

'use client';

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import {
  Cog6ToothIcon,
  InformationCircleIcon,
  ChartBarIcon,
  BeakerIcon,
  AdjustmentsHorizontalIcon,
  ArrowPathIcon
} from '@heroicons/react/24/outline';

interface Strategy {
  name: string;
  description: string;
  type: string;
  parameters: Record<string, any>;
}

interface ParameterConfigProps {
  strategyType: string;
  parameters: Record<string, any>;
  onChange: (parameters: Record<string, any>) => void;
  strategy: Strategy;
  onStrategyUpdate: (updates: Partial<Strategy>) => void;
}

interface ParameterDefinition {
  key: string;
  label: string;
  type: 'number' | 'select' | 'boolean' | 'range' | 'text';
  description: string;
  defaultValue: any;
  min?: number;
  max?: number;
  step?: number;
  options?: { value: any; label: string; description?: string }[];
  validation?: {
    required?: boolean;
    min?: number;
    max?: number;
    pattern?: string;
  };
  category: 'Entry' | 'Exit' | 'Risk' | 'Advanced';
  impact: 'High' | 'Medium' | 'Low';
}

const PARAMETER_DEFINITIONS: Record<string, ParameterDefinition[]> = {
  ma_crossover: [
    {
      key: 'fast_period',
      label: 'Fast MA Period',
      type: 'number',
      description: 'Period for the fast moving average (typically 5-20)',
      defaultValue: 10,
      min: 2,
      max: 50,
      step: 1,
      validation: { required: true, min: 2, max: 50 },
      category: 'Entry',
      impact: 'High'
    },
    {
      key: 'slow_period',
      label: 'Slow MA Period',
      type: 'number',
      description: 'Period for the slow moving average (typically 20-100)',
      defaultValue: 20,
      min: 5,
      max: 200,
      step: 1,
      validation: { required: true, min: 5, max: 200 },
      category: 'Entry',
      impact: 'High'
    },
    {
      key: 'ma_type',
      label: 'MA Type',
      type: 'select',
      description: 'Type of moving average calculation',
      defaultValue: 'sma',
      options: [
        { value: 'sma', label: 'Simple MA', description: 'Equal weight to all periods' },
        { value: 'ema', label: 'Exponential MA', description: 'More weight to recent prices' },
        { value: 'wma', label: 'Weighted MA', description: 'Linear weight decrease' },
        { value: 'hull', label: 'Hull MA', description: 'Reduced lag moving average' }
      ],
      category: 'Entry',
      impact: 'Medium'
    },
    {
      key: 'signal_threshold',
      label: 'Signal Threshold',
      type: 'range',
      description: 'Minimum price difference required for signal confirmation (%)',
      defaultValue: 0.1,
      min: 0.01,
      max: 1.0,
      step: 0.01,
      category: 'Entry',
      impact: 'Medium'
    },
    {
      key: 'stop_loss_pct',
      label: 'Stop Loss (%)',
      type: 'range',
      description: 'Stop loss as percentage of entry price',
      defaultValue: 2.0,
      min: 0.5,
      max: 10.0,
      step: 0.1,
      category: 'Risk',
      impact: 'High'
    },
    {
      key: 'take_profit_pct',
      label: 'Take Profit (%)',
      type: 'range',
      description: 'Take profit as percentage of entry price',
      defaultValue: 4.0,
      min: 1.0,
      max: 20.0,
      step: 0.1,
      category: 'Risk',
      impact: 'High'
    },
    {
      key: 'use_trailing_stop',
      label: 'Use Trailing Stop',
      type: 'boolean',
      description: 'Enable trailing stop loss functionality',
      defaultValue: false,
      category: 'Risk',
      impact: 'Medium'
    },
    {
      key: 'min_trade_interval',
      label: 'Min Trade Interval (hours)',
      type: 'number',
      description: 'Minimum hours between trades to avoid overtrading',
      defaultValue: 4,
      min: 1,
      max: 168,
      step: 1,
      category: 'Advanced',
      impact: 'Low'
    }
  ],

  rsi_reversal: [
    {
      key: 'rsi_period',
      label: 'RSI Period',
      type: 'number',
      description: 'Number of periods for RSI calculation (typically 14)',
      defaultValue: 14,
      min: 2,
      max: 50,
      step: 1,
      validation: { required: true, min: 2, max: 50 },
      category: 'Entry',
      impact: 'High'
    },
    {
      key: 'oversold_level',
      label: 'Oversold Level',
      type: 'range',
      description: 'RSI level considered oversold (buy signal)',
      defaultValue: 30,
      min: 10,
      max: 40,
      step: 1,
      category: 'Entry',
      impact: 'High'
    },
    {
      key: 'overbought_level',
      label: 'Overbought Level',
      type: 'range',
      description: 'RSI level considered overbought (sell signal)',
      defaultValue: 70,
      min: 60,
      max: 90,
      step: 1,
      category: 'Entry',
      impact: 'High'
    },
    {
      key: 'exit_rsi',
      label: 'Exit RSI Level',
      type: 'range',
      description: 'RSI level to exit positions (typically 50)',
      defaultValue: 50,
      min: 40,
      max: 60,
      step: 1,
      category: 'Exit',
      impact: 'Medium'
    },
    {
      key: 'confirmation_periods',
      label: 'Confirmation Periods',
      type: 'number',
      description: 'Number of periods RSI must stay in signal zone',
      defaultValue: 2,
      min: 1,
      max: 5,
      step: 1,
      category: 'Entry',
      impact: 'Medium'
    },
    {
      key: 'use_divergence',
      label: 'Use Divergence',
      type: 'boolean',
      description: 'Enable RSI divergence detection for stronger signals',
      defaultValue: true,
      category: 'Advanced',
      impact: 'Medium'
    }
  ],

  bollinger_bands: [
    {
      key: 'period',
      label: 'Period',
      type: 'number',
      description: 'Number of periods for moving average (typically 20)',
      defaultValue: 20,
      min: 5,
      max: 100,
      step: 1,
      validation: { required: true, min: 5, max: 100 },
      category: 'Entry',
      impact: 'High'
    },
    {
      key: 'std_dev',
      label: 'Standard Deviations',
      type: 'range',
      description: 'Number of standard deviations for band calculation',
      defaultValue: 2.0,
      min: 1.0,
      max: 3.0,
      step: 0.1,
      category: 'Entry',
      impact: 'High'
    },
    {
      key: 'entry_method',
      label: 'Entry Method',
      type: 'select',
      description: 'How to determine entry signals',
      defaultValue: 'band_touch',
      options: [
        { value: 'band_touch', label: 'Band Touch', description: 'Enter when price touches outer bands' },
        { value: 'band_break', label: 'Band Break', description: 'Enter when price breaks through bands' },
        { value: 'squeeze', label: 'Squeeze', description: 'Enter after volatility squeeze' }
      ],
      category: 'Entry',
      impact: 'High'
    },
    {
      key: 'exit_method',
      label: 'Exit Method',
      type: 'select',
      description: 'How to determine exit signals',
      defaultValue: 'middle_band',
      options: [
        { value: 'middle_band', label: 'Middle Band', description: 'Exit when price returns to middle band' },
        { value: 'opposite_band', label: 'Opposite Band', description: 'Exit when price reaches opposite band' },
        { value: 'percent_b', label: 'Percent B', description: 'Exit based on %B indicator' }
      ],
      category: 'Exit',
      impact: 'High'
    },
    {
      key: 'min_band_width',
      label: 'Min Band Width (%)',
      type: 'range',
      description: 'Minimum band width to avoid trading in low volatility',
      defaultValue: 1.0,
      min: 0.5,
      max: 5.0,
      step: 0.1,
      category: 'Advanced',
      impact: 'Medium'
    }
  ],

  ml_signals: [
    {
      key: 'model_type',
      label: 'Model Type',
      type: 'select',
      description: 'Type of machine learning model to use',
      defaultValue: 'neural_network',
      options: [
        { value: 'neural_network', label: 'Neural Network', description: 'Deep learning model' },
        { value: 'random_forest', label: 'Random Forest', description: 'Ensemble tree model' },
        { value: 'xgboost', label: 'XGBoost', description: 'Gradient boosting' },
        { value: 'lstm', label: 'LSTM', description: 'Recurrent neural network' }
      ],
      category: 'Entry',
      impact: 'High'
    },
    {
      key: 'prediction_horizon',
      label: 'Prediction Horizon (bars)',
      type: 'number',
      description: 'Number of bars ahead to predict',
      defaultValue: 4,
      min: 1,
      max: 24,
      step: 1,
      category: 'Entry',
      impact: 'High'
    },
    {
      key: 'confidence_threshold',
      label: 'Confidence Threshold',
      type: 'range',
      description: 'Minimum model confidence required for trades',
      defaultValue: 0.7,
      min: 0.5,
      max: 0.95,
      step: 0.01,
      category: 'Entry',
      impact: 'High'
    },
    {
      key: 'feature_set',
      label: 'Feature Set',
      type: 'select',
      description: 'Set of features to use for prediction',
      defaultValue: 'comprehensive',
      options: [
        { value: 'basic', label: 'Basic', description: 'Price and volume only' },
        { value: 'technical', label: 'Technical', description: 'Technical indicators' },
        { value: 'comprehensive', label: 'Comprehensive', description: 'All available features' }
      ],
      category: 'Advanced',
      impact: 'Medium'
    },
    {
      key: 'retrain_interval',
      label: 'Retrain Interval (days)',
      type: 'number',
      description: 'How often to retrain the model',
      defaultValue: 30,
      min: 7,
      max: 90,
      step: 1,
      category: 'Advanced',
      impact: 'Medium'
    }
  ],

  elliott_wave: [
    {
      key: 'wave_degree',
      label: 'Wave Degree',
      type: 'select',
      description: 'Elliott Wave degree to analyze',
      defaultValue: 'primary',
      options: [
        { value: 'minute', label: 'Minute', description: 'Very short-term waves' },
        { value: 'minor', label: 'Minor', description: 'Short-term waves' },
        { value: 'intermediate', label: 'Intermediate', description: 'Medium-term waves' },
        { value: 'primary', label: 'Primary', description: 'Long-term waves' },
        { value: 'cycle', label: 'Cycle', description: 'Very long-term waves' }
      ],
      category: 'Entry',
      impact: 'High'
    },
    {
      key: 'pattern_confidence',
      label: 'Pattern Confidence',
      type: 'range',
      description: 'Minimum confidence in wave pattern identification',
      defaultValue: 0.8,
      min: 0.5,
      max: 0.95,
      step: 0.01,
      category: 'Entry',
      impact: 'High'
    },
    {
      key: 'fibonacci_levels',
      label: 'Fibonacci Retracement Levels',
      type: 'text',
      description: 'Comma-separated fibonacci levels (e.g., 0.236,0.382,0.618)',
      defaultValue: '0.236,0.382,0.618,0.786',
      validation: { required: true, pattern: '^[0-9.,]+$' },
      category: 'Entry',
      impact: 'Medium'
    },
    {
      key: 'wave_completion_method',
      label: 'Wave Completion Method',
      type: 'select',
      description: 'How to determine wave completion',
      defaultValue: 'fibonacci',
      options: [
        { value: 'fibonacci', label: 'Fibonacci', description: 'Use fibonacci ratios' },
        { value: 'time', label: 'Time', description: 'Use time-based completion' },
        { value: 'hybrid', label: 'Hybrid', description: 'Combine price and time' }
      ],
      category: 'Exit',
      impact: 'Medium'
    },
    {
      key: 'use_wave_extensions',
      label: 'Use Wave Extensions',
      type: 'boolean',
      description: 'Include extended wave analysis',
      defaultValue: true,
      category: 'Advanced',
      impact: 'Medium'
    }
  ],

  custom: [
    {
      key: 'custom_logic',
      label: 'Custom Logic',
      type: 'text',
      description: 'Custom strategy logic (Python-like syntax)',
      defaultValue: '# Define your strategy logic here\nif close > sma(20):\n    buy()\nelse:\n    sell()',
      category: 'Entry',
      impact: 'High'
    }
  ]
};

export default function ParameterConfig({
  strategyType,
  parameters,
  onChange,
  strategy,
  onStrategyUpdate
}: ParameterConfigProps) {
  const [activeCategory, setActiveCategory] = useState<string>('Entry');
  const [showAdvanced, setShowAdvanced] = useState(false);

  const parameterDefs = PARAMETER_DEFINITIONS[strategyType] || [];
  const categories = ['Entry', 'Exit', 'Risk', 'Advanced'];
  const filteredParams = parameterDefs.filter(param =>
    param.category === activeCategory && (showAdvanced || param.category !== 'Advanced')
  );

  useEffect(() => {
    // Initialize parameters with defaults if not set
    const newParams = { ...parameters };
    let hasChanges = false;

    parameterDefs.forEach(param => {
      if (!(param.key in newParams)) {
        newParams[param.key] = param.defaultValue;
        hasChanges = true;
      }
    });

    if (hasChanges) {
      onChange(newParams);
    }
  }, [strategyType, parameterDefs, parameters, onChange]);

  const handleParameterChange = (key: string, value: any) => {
    const newParams = { ...parameters, [key]: value };
    onChange(newParams);
  };

  const handleNameChange = (name: string) => {
    onStrategyUpdate({ name });
  };

  const handleDescriptionChange = (description: string) => {
    onStrategyUpdate({ description });
  };

  const resetToDefaults = () => {
    const defaultParams: Record<string, any> = {};
    parameterDefs.forEach(param => {
      defaultParams[param.key] = param.defaultValue;
    });
    onChange(defaultParams);
  };

  const renderParameterInput = (param: ParameterDefinition) => {
    const value = parameters[param.key] ?? param.defaultValue;

    switch (param.type) {
      case 'number':
        return (
          <input
            type="number"
            value={value}
            min={param.min}
            max={param.max}
            step={param.step}
            onChange={(e) => handleParameterChange(param.key, parseFloat(e.target.value) || 0)}
            className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
          />
        );

      case 'range':
        return (
          <div className="space-y-2">
            <input
              type="range"
              value={value}
              min={param.min}
              max={param.max}
              step={param.step}
              onChange={(e) => handleParameterChange(param.key, parseFloat(e.target.value))}
              className="w-full h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer slider"
            />
            <div className="flex justify-between text-xs text-gray-400">
              <span>{param.min}</span>
              <span className="font-medium text-white">{value}</span>
              <span>{param.max}</span>
            </div>
          </div>
        );

      case 'select':
        return (
          <select
            value={value}
            onChange={(e) => handleParameterChange(param.key, e.target.value)}
            className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
          >
            {param.options?.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        );

      case 'boolean':
        return (
          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={value}
              onChange={(e) => handleParameterChange(param.key, e.target.checked)}
              className="w-4 h-4 text-blue-500 bg-gray-800 border-gray-600 rounded focus:ring-blue-500 focus:ring-2"
            />
            <span className="text-sm text-gray-300">
              {value ? 'Enabled' : 'Disabled'}
            </span>
          </label>
        );

      case 'text':
        return (
          <textarea
            value={value}
            onChange={(e) => handleParameterChange(param.key, e.target.value)}
            rows={param.key === 'custom_logic' ? 10 : 3}
            className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 font-mono text-sm"
            placeholder={param.description}
          />
        );

      default:
        return null;
    }
  };

  const getImpactColor = (impact: string) => {
    switch (impact) {
      case 'High': return 'text-red-400 bg-red-500/20';
      case 'Medium': return 'text-yellow-400 bg-yellow-500/20';
      case 'Low': return 'text-green-400 bg-green-500/20';
      default: return 'text-gray-400 bg-gray-500/20';
    }
  };

  return (
    <div className="h-full">
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-lg font-semibold text-white mb-2">Configure Parameters</h3>
            <p className="text-gray-400">
              Customize your strategy parameters. Changes are automatically saved.
            </p>
          </div>

          <Button
            onClick={resetToDefaults}
            variant="outline"
            size="sm"
            className="gap-2"
          >
            <ArrowPathIcon className="w-4 h-4" />
            Reset to Defaults
          </Button>
        </div>

        {/* Strategy Basic Info */}
        <div className="grid grid-cols-2 gap-4 mb-6">
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">Strategy Name</label>
            <input
              type="text"
              value={strategy.name}
              onChange={(e) => handleNameChange(e.target.value)}
              placeholder="Enter strategy name..."
              className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">Description</label>
            <input
              type="text"
              value={strategy.description}
              onChange={(e) => handleDescriptionChange(e.target.value)}
              placeholder="Describe your strategy..."
              className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
            />
          </div>
        </div>
      </div>

      <div className="grid grid-cols-12 gap-6 h-full">
        {/* Category Navigation */}
        <div className="col-span-3">
          <div className="bg-gray-900 border border-gray-700 rounded-lg p-4 sticky top-0">
            <h4 className="text-sm font-medium text-gray-300 mb-3">Parameter Categories</h4>
            <div className="space-y-1">
              {categories.map((category) => {
                const categoryParams = parameterDefs.filter(p => p.category === category);
                const isActive = activeCategory === category;

                return (
                  <button
                    key={category}
                    onClick={() => setActiveCategory(category)}
                    className={`
                      w-full text-left px-3 py-2 rounded-lg text-sm transition-colors flex items-center justify-between
                      ${isActive
                        ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30'
                        : 'text-gray-400 hover:text-gray-300 hover:bg-gray-800'
                      }
                    `}
                  >
                    <span>{category}</span>
                    <span className="text-xs bg-gray-700 px-1.5 py-0.5 rounded">
                      {categoryParams.length}
                    </span>
                  </button>
                );
              })}
            </div>

            <div className="mt-4 pt-4 border-t border-gray-700">
              <label className="flex items-center gap-2 text-sm text-gray-400">
                <input
                  type="checkbox"
                  checked={showAdvanced}
                  onChange={(e) => setShowAdvanced(e.target.checked)}
                  className="w-3 h-3 text-blue-500 bg-gray-800 border-gray-600 rounded"
                />
                Show Advanced
              </label>
            </div>
          </div>
        </div>

        {/* Parameters */}
        <div className="col-span-9">
          <div className="bg-gray-900 border border-gray-700 rounded-lg p-6 h-full overflow-y-auto">
            <div className="flex items-center gap-2 mb-6">
              <AdjustmentsHorizontalIcon className="w-5 h-5 text-blue-400" />
              <h4 className="text-lg font-semibold text-white">{activeCategory} Parameters</h4>
            </div>

            {filteredParams.length === 0 ? (
              <div className="text-center py-8 text-gray-400">
                <Cog6ToothIcon className="w-12 h-12 mx-auto mb-3 opacity-50" />
                <p>No parameters in this category</p>
              </div>
            ) : (
              <div className="space-y-6">
                {filteredParams.map((param) => (
                  <div key={param.key} className="border border-gray-700 rounded-lg p-4">
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <h5 className="font-medium text-white">{param.label}</h5>
                          <span className={`
                            text-xs px-2 py-0.5 rounded-full font-medium
                            ${getImpactColor(param.impact)}
                          `}>
                            {param.impact} Impact
                          </span>
                        </div>
                        <p className="text-sm text-gray-400 mb-3">{param.description}</p>
                      </div>

                      <InformationCircleIcon className="w-5 h-5 text-gray-400 mt-0.5" />
                    </div>

                    <div className="mt-3">
                      {renderParameterInput(param)}
                    </div>

                    {/* Show current value for select options */}
                    {param.type === 'select' && param.options && (
                      <div className="mt-2 p-2 bg-gray-800/50 rounded text-xs text-gray-400">
                        {param.options.find(opt => opt.value === parameters[param.key])?.description}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
