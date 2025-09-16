/**
 * Strategy Builder Component
 *
 * Main interface for creating and editing trading strategies
 */

'use client';

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import StrategyTemplate from './StrategyTemplate';
import ParameterConfig from './ParameterConfig';
import StrategyValidator from './StrategyValidator';
import { useAppStore } from '@/stores/appStore';
import {
  RocketLaunchIcon,
  Cog6ToothIcon,
  CheckCircleIcon,
  DocumentTextIcon,
  ChartBarIcon,
  BeakerIcon,
  SaveIcon,
  PlayIcon
} from '@heroicons/react/24/outline';

export interface Strategy {
  id?: string;
  name: string;
  description: string;
  type: 'ma_crossover' | 'rsi_reversal' | 'bollinger_bands' | 'ml_signals' | 'elliott_wave' | 'custom';
  parameters: Record<string, any>;
  code?: string;
  isActive: boolean;
  performance?: {
    backtestResults?: any;
    sharpeRatio?: number;
    maxDrawdown?: number;
    winRate?: number;
  };
  created: string;
  lastModified: string;
  tags: string[];
}

interface StrategyBuilderProps {
  strategy?: Strategy;
  onSave: (strategy: Strategy) => void;
  onCancel: () => void;
  mode?: 'create' | 'edit';
}

const STRATEGY_TYPES = [
  {
    id: 'ma_crossover',
    name: 'Moving Average Crossover',
    description: 'Buy/sell signals based on moving average crossovers',
    icon: ChartBarIcon,
    complexity: 'Beginner',
    category: 'Trend Following'
  },
  {
    id: 'rsi_reversal',
    name: 'RSI Reversal',
    description: 'Mean reversion strategy using RSI overbought/oversold levels',
    icon: BeakerIcon,
    complexity: 'Intermediate',
    category: 'Mean Reversion'
  },
  {
    id: 'bollinger_bands',
    name: 'Bollinger Bands',
    description: 'Volatility-based strategy using Bollinger Band boundaries',
    icon: ChartBarIcon,
    complexity: 'Intermediate',
    category: 'Volatility'
  },
  {
    id: 'ml_signals',
    name: 'ML Signals',
    description: 'Machine learning model-based trading signals',
    icon: RocketLaunchIcon,
    complexity: 'Advanced',
    category: 'Machine Learning'
  },
  {
    id: 'elliott_wave',
    name: 'Elliott Wave',
    description: 'Elliott Wave pattern recognition and trading',
    icon: ChartBarIcon,
    complexity: 'Expert',
    category: 'Pattern Recognition'
  },
  {
    id: 'custom',
    name: 'Custom Strategy',
    description: 'Build your own custom trading strategy',
    icon: Cog6ToothIcon,
    complexity: 'Advanced',
    category: 'Custom'
  }
];

export default function StrategyBuilder({
  strategy,
  onSave,
  onCancel,
  mode = 'create'
}: StrategyBuilderProps) {
  const [activeTab, setActiveTab] = useState('template');
  const [currentStrategy, setCurrentStrategy] = useState<Strategy>({
    name: '',
    description: '',
    type: 'ma_crossover',
    parameters: {},
    isActive: false,
    created: new Date().toISOString(),
    lastModified: new Date().toISOString(),
    tags: []
  });
  const [validationResults, setValidationResults] = useState<any>(null);
  const [isValidating, setIsValidating] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  const { addNotification, addError } = useAppStore();

  useEffect(() => {
    if (strategy) {
      setCurrentStrategy(strategy);
    }
  }, [strategy]);

  const handleStrategyUpdate = (updates: Partial<Strategy>) => {
    setCurrentStrategy(prev => ({
      ...prev,
      ...updates,
      lastModified: new Date().toISOString()
    }));
  };

  const handleTemplateSelect = (type: Strategy['type']) => {
    const template = STRATEGY_TYPES.find(t => t.id === type);
    if (template) {
      handleStrategyUpdate({
        type,
        name: currentStrategy.name || template.name,
        description: currentStrategy.description || template.description,
        parameters: getDefaultParameters(type)
      });
      setActiveTab('parameters');
    }
  };

  const handleParametersUpdate = (parameters: Record<string, any>) => {
    handleStrategyUpdate({ parameters });
  };

  const handleValidate = async () => {
    try {
      setIsValidating(true);

      // Simulate strategy validation
      const results = await validateStrategy(currentStrategy);
      setValidationResults(results);

      if (results.isValid) {
        addNotification({
          type: 'success',
          title: 'Strategy Validated',
          message: 'Strategy passed all validation checks'
        });
        setActiveTab('summary');
      } else {
        addNotification({
          type: 'warning',
          title: 'Validation Issues',
          message: `Found ${results.issues.length} issues to fix`
        });
      }
    } catch (error) {
      console.error('Strategy validation failed:', error);
      addError({
        code: 'STRATEGY_VALIDATION_ERROR',
        message: 'Failed to validate strategy',
        timestamp: new Date().toISOString()
      });
    } finally {
      setIsValidating(false);
    }
  };

  const handleSave = async () => {
    try {
      setIsSaving(true);

      // Validate before saving
      if (!currentStrategy.name.trim()) {
        throw new Error('Strategy name is required');
      }

      if (!currentStrategy.description.trim()) {
        throw new Error('Strategy description is required');
      }

      // Add ID if creating new strategy
      const strategyToSave = {
        ...currentStrategy,
        id: currentStrategy.id || `strategy_${Date.now()}`,
        lastModified: new Date().toISOString()
      };

      await onSave(strategyToSave);

      addNotification({
        type: 'success',
        title: 'Strategy Saved',
        message: `Strategy "${currentStrategy.name}" saved successfully`
      });
    } catch (error) {
      console.error('Failed to save strategy:', error);
      addError({
        code: 'STRATEGY_SAVE_ERROR',
        message: error instanceof Error ? error.message : 'Failed to save strategy',
        timestamp: new Date().toISOString()
      });
    } finally {
      setIsSaving(false);
    }
  };

  const handleTestStrategy = async () => {
    try {
      addNotification({
        type: 'info',
        title: 'Strategy Test Started',
        message: 'Running quick backtest to validate strategy logic'
      });

      // This would trigger a quick backtest
      // Implementation would depend on backend API
    } catch (error) {
      console.error('Strategy test failed:', error);
    }
  };

  const getStepStatus = (step: string) => {
    switch (step) {
      case 'template':
        return currentStrategy.type ? 'complete' : 'current';
      case 'parameters':
        return Object.keys(currentStrategy.parameters).length > 0 ? 'complete' :
               currentStrategy.type ? 'current' : 'pending';
      case 'validation':
        return validationResults?.isValid ? 'complete' :
               Object.keys(currentStrategy.parameters).length > 0 ? 'current' : 'pending';
      case 'summary':
        return validationResults?.isValid ? 'current' : 'pending';
      default:
        return 'pending';
    }
  };

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="p-6 border-b border-gray-700 bg-gray-900/50">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-semibold text-white">
              {mode === 'edit' ? 'Edit Strategy' : 'Create New Strategy'}
            </h2>
            <p className="text-gray-400 text-sm mt-1">
              Build and configure your trading strategy
            </p>
          </div>

          <div className="flex items-center gap-3">
            <Button
              variant="outline"
              onClick={onCancel}
              disabled={isSaving}
            >
              Cancel
            </Button>

            <Button
              onClick={handleTestStrategy}
              variant="outline"
              className="gap-2"
              disabled={!validationResults?.isValid}
            >
              <PlayIcon className="w-4 h-4" />
              Test Strategy
            </Button>

            <Button
              onClick={handleSave}
              disabled={!currentStrategy.name || !validationResults?.isValid || isSaving}
              className="gap-2"
            >
              {isSaving ? (
                <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
              ) : (
                <SaveIcon className="w-4 h-4" />
              )}
              Save Strategy
            </Button>
          </div>
        </div>

        {/* Progress Steps */}
        <div className="flex items-center gap-4 mt-4">
          {[
            { id: 'template', label: 'Template', icon: RocketLaunchIcon },
            { id: 'parameters', label: 'Parameters', icon: Cog6ToothIcon },
            { id: 'validation', label: 'Validation', icon: CheckCircleIcon },
            { id: 'summary', label: 'Summary', icon: DocumentTextIcon }
          ].map((step, index) => {
            const status = getStepStatus(step.id);
            const StepIcon = step.icon;

            return (
              <div key={step.id} className="flex items-center gap-2">
                <div className={`
                  flex items-center justify-center w-8 h-8 rounded-full border-2 transition-colors
                  ${status === 'complete' ? 'bg-green-500 border-green-500 text-white' :
                    status === 'current' ? 'bg-blue-500 border-blue-500 text-white' :
                    'border-gray-500 text-gray-500'}
                `}>
                  {status === 'complete' ? (
                    <CheckCircleIcon className="w-4 h-4" />
                  ) : (
                    <StepIcon className="w-4 h-4" />
                  )}
                </div>
                <span className={`text-sm ${
                  status === 'complete' ? 'text-green-400' :
                  status === 'current' ? 'text-blue-400' :
                  'text-gray-500'
                }`}>
                  {step.label}
                </span>
                {index < 3 && (
                  <div className={`w-8 h-0.5 ${
                    status === 'complete' ? 'bg-green-500' : 'bg-gray-600'
                  }`} />
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 p-6">
        <Tabs value={activeTab} onValueChange={setActiveTab} className="h-full flex flex-col">
          <TabsList className="grid w-full grid-cols-4 bg-gray-800 mb-6">
            <TabsTrigger value="template" className="gap-2">
              <RocketLaunchIcon className="w-4 h-4" />
              Template
            </TabsTrigger>
            <TabsTrigger value="parameters" className="gap-2">
              <Cog6ToothIcon className="w-4 h-4" />
              Parameters
            </TabsTrigger>
            <TabsTrigger value="validation" className="gap-2">
              <CheckCircleIcon className="w-4 h-4" />
              Validation
            </TabsTrigger>
            <TabsTrigger value="summary" className="gap-2">
              <DocumentTextIcon className="w-4 h-4" />
              Summary
            </TabsTrigger>
          </TabsList>

          <div className="flex-1">
            <TabsContent value="template" className="h-full">
              <StrategyTemplate
                selectedType={currentStrategy.type}
                onSelect={handleTemplateSelect}
                strategyTypes={STRATEGY_TYPES}
              />
            </TabsContent>

            <TabsContent value="parameters" className="h-full">
              <ParameterConfig
                strategyType={currentStrategy.type}
                parameters={currentStrategy.parameters}
                onChange={handleParametersUpdate}
                strategy={currentStrategy}
                onStrategyUpdate={handleStrategyUpdate}
              />
            </TabsContent>

            <TabsContent value="validation" className="h-full">
              <StrategyValidator
                strategy={currentStrategy}
                validationResults={validationResults}
                isValidating={isValidating}
                onValidate={handleValidate}
              />
            </TabsContent>

            <TabsContent value="summary" className="h-full">
              <div className="bg-gray-900 border border-gray-700 rounded-lg p-6">
                <h3 className="text-lg font-semibold text-white mb-4">Strategy Summary</h3>

                <div className="grid grid-cols-2 gap-6">
                  <div className="space-y-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-300 mb-1">Name</label>
                      <div className="text-white">{currentStrategy.name || 'Unnamed Strategy'}</div>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-300 mb-1">Type</label>
                      <div className="text-white">
                        {STRATEGY_TYPES.find(t => t.id === currentStrategy.type)?.name || 'Unknown'}
                      </div>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-300 mb-1">Description</label>
                      <div className="text-white">{currentStrategy.description || 'No description'}</div>
                    </div>
                  </div>

                  <div className="space-y-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-300 mb-1">Parameters</label>
                      <div className="text-sm text-gray-400">
                        {Object.keys(currentStrategy.parameters).length} parameters configured
                      </div>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-300 mb-1">Status</label>
                      <div className={`inline-flex items-center gap-2 px-2 py-1 rounded text-sm ${
                        validationResults?.isValid ? 'bg-green-500/20 text-green-400' :
                        'bg-yellow-500/20 text-yellow-400'
                      }`}>
                        {validationResults?.isValid ? 'Validated' : 'Needs Validation'}
                      </div>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-300 mb-1">Last Modified</label>
                      <div className="text-sm text-gray-400">
                        {new Date(currentStrategy.lastModified).toLocaleString()}
                      </div>
                    </div>
                  </div>
                </div>

                {validationResults?.issues && validationResults.issues.length > 0 && (
                  <div className="mt-6 p-4 bg-yellow-500/10 border border-yellow-500/30 rounded-lg">
                    <h4 className="font-medium text-yellow-400 mb-2">Issues to Address:</h4>
                    <ul className="text-sm text-yellow-300 space-y-1">
                      {validationResults.issues.map((issue: string, index: number) => (
                        <li key={index}>• {issue}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </TabsContent>
          </div>
        </Tabs>
      </div>
    </div>
  );
}

// Helper functions
function getDefaultParameters(type: Strategy['type']): Record<string, any> {
  switch (type) {
    case 'ma_crossover':
      return {
        fast_period: 10,
        slow_period: 20,
        signal_threshold: 0.001
      };
    case 'rsi_reversal':
      return {
        rsi_period: 14,
        oversold_level: 30,
        overbought_level: 70,
        exit_rsi: 50
      };
    case 'bollinger_bands':
      return {
        period: 20,
        std_dev: 2,
        exit_method: 'middle_band'
      };
    case 'ml_signals':
      return {
        model_type: 'neural_network',
        prediction_horizon: 4,
        confidence_threshold: 0.7
      };
    case 'elliott_wave':
      return {
        wave_degree: 'primary',
        pattern_confidence: 0.8,
        fibonacci_levels: [0.236, 0.382, 0.618]
      };
    case 'custom':
      return {};
    default:
      return {};
  }
}

async function validateStrategy(strategy: Strategy) {
  // Simulate strategy validation
  await new Promise(resolve => setTimeout(resolve, 2000));

  const issues = [];

  if (!strategy.name.trim()) {
    issues.push('Strategy name is required');
  }

  if (!strategy.description.trim()) {
    issues.push('Strategy description is required');
  }

  if (Object.keys(strategy.parameters).length === 0) {
    issues.push('Strategy parameters must be configured');
  }

  // Type-specific validations
  switch (strategy.type) {
    case 'ma_crossover':
      if (strategy.parameters.fast_period >= strategy.parameters.slow_period) {
        issues.push('Fast period must be less than slow period');
      }
      break;
    case 'rsi_reversal':
      if (strategy.parameters.oversold_level >= strategy.parameters.overbought_level) {
        issues.push('Oversold level must be less than overbought level');
      }
      break;
  }

  return {
    isValid: issues.length === 0,
    issues,
    performance: issues.length === 0 ? {
      estimatedSharpe: 1.2 + Math.random(),
      estimatedDrawdown: 0.05 + Math.random() * 0.1,
      estimatedWinRate: 0.55 + Math.random() * 0.2
    } : null
  };
}
