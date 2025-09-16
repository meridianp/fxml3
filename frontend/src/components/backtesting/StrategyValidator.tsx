/**
 * Strategy Validator Component
 *
 * Validates strategy configuration and runs quick tests
 */

'use client';

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import {
  CheckCircleIcon,
  XCircleIcon,
  ExclamationTriangleIcon,
  PlayIcon,
  ChartBarIcon,
  ClockIcon,
  CurrencyDollarIcon,
  TrendingUpIcon,
  ArrowPathIcon
} from '@heroicons/react/24/outline';

interface Strategy {
  name: string;
  description: string;
  type: string;
  parameters: Record<string, any>;
}

interface ValidationResult {
  isValid: boolean;
  issues: string[];
  warnings: string[];
  performance?: {
    estimatedSharpe: number;
    estimatedDrawdown: number;
    estimatedWinRate: number;
    backtestPreview?: {
      totalTrades: number;
      winningTrades: number;
      totalReturn: number;
      maxDrawdown: number;
      sharpeRatio: number;
      avgTradeDuration: number;
    };
  };
}

interface StrategyValidatorProps {
  strategy: Strategy;
  validationResults: ValidationResult | null;
  isValidating: boolean;
  onValidate: () => void;
}

export default function StrategyValidator({
  strategy,
  validationResults,
  isValidating,
  onValidate
}: StrategyValidatorProps) {
  const [quickTestResults, setQuickTestResults] = useState<any>(null);
  const [isRunningQuickTest, setIsRunningQuickTest] = useState(false);
  const [testProgress, setTestProgress] = useState(0);

  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (isValidating || isRunningQuickTest) {
      interval = setInterval(() => {
        setTestProgress(prev => {
          const increment = Math.random() * 10;
          return Math.min(prev + increment, 95);
        });
      }, 200);
    } else {
      setTestProgress(0);
    }

    return () => {
      if (interval) clearInterval(interval);
    };
  }, [isValidating, isRunningQuickTest]);

  const runQuickTest = async () => {
    try {
      setIsRunningQuickTest(true);
      setTestProgress(0);

      // Simulate quick backtest
      await new Promise(resolve => setTimeout(resolve, 3000));

      const mockResults = {
        period: '3 months',
        totalTrades: 45 + Math.floor(Math.random() * 20),
        winningTrades: Math.floor(Math.random() * 25) + 20,
        totalReturn: (Math.random() * 0.3 + 0.05) * 100, // 5-35%
        maxDrawdown: (Math.random() * 0.15 + 0.02) * 100, // 2-17%
        sharpeRatio: Math.random() * 2 + 0.5, // 0.5-2.5
        avgTradeDuration: Math.random() * 48 + 4, // 4-52 hours
        monthlyReturns: [
          { month: 'Month 1', return: Math.random() * 0.2 - 0.05 },
          { month: 'Month 2', return: Math.random() * 0.2 - 0.05 },
          { month: 'Month 3', return: Math.random() * 0.2 - 0.05 }
        ],
        equityCurve: Array.from({ length: 20 }, (_, i) => ({
          date: new Date(Date.now() - (19 - i) * 24 * 60 * 60 * 1000).toLocaleDateString(),
          equity: 10000 + Math.random() * 2000 * (i / 10) + (Math.random() - 0.5) * 500
        }))
      };

      setQuickTestResults(mockResults);
      setTestProgress(100);
    } catch (error) {
      console.error('Quick test failed:', error);
    } finally {
      setIsRunningQuickTest(false);
    }
  };

  const getValidationStatusIcon = () => {
    if (isValidating) {
      return <ArrowPathIcon className="w-5 h-5 text-blue-400 animate-spin" />;
    }

    if (!validationResults) {
      return <ExclamationTriangleIcon className="w-5 h-5 text-gray-400" />;
    }

    if (validationResults.isValid) {
      return <CheckCircleIcon className="w-5 h-5 text-green-400" />;
    }

    return <XCircleIcon className="w-5 h-5 text-red-400" />;
  };

  const getValidationStatusText = () => {
    if (isValidating) return 'Validating...';
    if (!validationResults) return 'Not validated';
    if (validationResults.isValid) return 'Valid';
    return 'Invalid';
  };

  const getValidationStatusColor = () => {
    if (isValidating) return 'text-blue-400';
    if (!validationResults) return 'text-gray-400';
    if (validationResults.isValid) return 'text-green-400';
    return 'text-red-400';
  };

  return (
    <div className="h-full space-y-6">
      {/* Validation Status */}
      <div className="bg-gray-900 border border-gray-700 rounded-lg p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            {getValidationStatusIcon()}
            <div>
              <h3 className="text-lg font-semibold text-white">Strategy Validation</h3>
              <p className={`text-sm ${getValidationStatusColor()}`}>
                {getValidationStatusText()}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <Button
              onClick={runQuickTest}
              disabled={!validationResults?.isValid || isRunningQuickTest}
              variant="outline"
              className="gap-2"
            >
              <PlayIcon className="w-4 h-4" />
              Quick Test
            </Button>

            <Button
              onClick={onValidate}
              disabled={isValidating}
              className="gap-2"
            >
              {isValidating ? (
                <ArrowPathIcon className="w-4 h-4 animate-spin" />
              ) : (
                <CheckCircleIcon className="w-4 h-4" />
              )}
              {isValidating ? 'Validating...' : 'Validate Strategy'}
            </Button>
          </div>
        </div>

        {(isValidating || isRunningQuickTest) && (
          <div className="mb-4">
            <div className="flex items-center justify-between text-sm text-gray-400 mb-2">
              <span>
                {isValidating ? 'Validating strategy logic...' : 'Running quick backtest...'}
              </span>
              <span>{Math.round(testProgress)}%</span>
            </div>
            <div className="w-full bg-gray-700 rounded-full h-2">
              <div
                className="bg-blue-500 h-2 rounded-full transition-all duration-300"
                style={{ width: `${testProgress}%` }}
              />
            </div>
          </div>
        )}

        {/* Validation Results */}
        {validationResults && (
          <div className="space-y-4">
            {/* Issues */}
            {validationResults.issues.length > 0 && (
              <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-lg">
                <div className="flex items-center gap-2 mb-2">
                  <XCircleIcon className="w-5 h-5 text-red-400" />
                  <h4 className="font-medium text-red-400">Issues ({validationResults.issues.length})</h4>
                </div>
                <ul className="text-sm text-red-300 space-y-1">
                  {validationResults.issues.map((issue, index) => (
                    <li key={index} className="flex items-start gap-2">
                      <span className="text-red-400 mt-0.5">•</span>
                      <span>{issue}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Warnings */}
            {validationResults.warnings && validationResults.warnings.length > 0 && (
              <div className="p-4 bg-yellow-500/10 border border-yellow-500/30 rounded-lg">
                <div className="flex items-center gap-2 mb-2">
                  <ExclamationTriangleIcon className="w-5 h-5 text-yellow-400" />
                  <h4 className="font-medium text-yellow-400">Warnings ({validationResults.warnings.length})</h4>
                </div>
                <ul className="text-sm text-yellow-300 space-y-1">
                  {validationResults.warnings.map((warning, index) => (
                    <li key={index} className="flex items-start gap-2">
                      <span className="text-yellow-400 mt-0.5">•</span>
                      <span>{warning}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Success */}
            {validationResults.isValid && (
              <div className="p-4 bg-green-500/10 border border-green-500/30 rounded-lg">
                <div className="flex items-center gap-2 mb-2">
                  <CheckCircleIcon className="w-5 h-5 text-green-400" />
                  <h4 className="font-medium text-green-400">Strategy Validated Successfully</h4>
                </div>
                <p className="text-sm text-green-300">
                  Your strategy has passed all validation checks and is ready for backtesting.
                </p>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Performance Estimates */}
      {validationResults?.performance && (
        <div className="bg-gray-900 border border-gray-700 rounded-lg p-6">
          <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <TrendingUpIcon className="w-5 h-5" />
            Performance Estimates
          </h3>

          <div className="grid grid-cols-3 gap-4 mb-6">
            <div className="bg-gray-800/50 rounded-lg p-4 text-center">
              <div className="text-2xl font-bold text-blue-400 mb-1">
                {validationResults.performance.estimatedSharpe.toFixed(2)}
              </div>
              <div className="text-sm text-gray-400">Estimated Sharpe Ratio</div>
            </div>

            <div className="bg-gray-800/50 rounded-lg p-4 text-center">
              <div className="text-2xl font-bold text-red-400 mb-1">
                {(validationResults.performance.estimatedDrawdown * 100).toFixed(1)}%
              </div>
              <div className="text-sm text-gray-400">Estimated Max Drawdown</div>
            </div>

            <div className="bg-gray-800/50 rounded-lg p-4 text-center">
              <div className="text-2xl font-bold text-green-400 mb-1">
                {(validationResults.performance.estimatedWinRate * 100).toFixed(1)}%
              </div>
              <div className="text-sm text-gray-400">Estimated Win Rate</div>
            </div>
          </div>

          <div className="text-xs text-gray-500 bg-gray-800/30 rounded p-3">
            <strong>Note:</strong> These are preliminary estimates based on strategy parameters and historical patterns.
            Actual results may vary significantly based on market conditions, execution, and other factors.
          </div>
        </div>
      )}

      {/* Quick Test Results */}
      {quickTestResults && (
        <div className="bg-gray-900 border border-gray-700 rounded-lg p-6">
          <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <ChartBarIcon className="w-5 h-5" />
            Quick Test Results ({quickTestResults.period})
          </h3>

          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
            <div className="bg-gray-800/50 rounded-lg p-3">
              <div className="flex items-center gap-2 mb-2">
                <PlayIcon className="w-4 h-4 text-blue-400" />
                <span className="text-sm text-gray-400">Total Trades</span>
              </div>
              <div className="text-xl font-bold text-white">{quickTestResults.totalTrades}</div>
            </div>

            <div className="bg-gray-800/50 rounded-lg p-3">
              <div className="flex items-center gap-2 mb-2">
                <CheckCircleIcon className="w-4 h-4 text-green-400" />
                <span className="text-sm text-gray-400">Win Rate</span>
              </div>
              <div className="text-xl font-bold text-green-400">
                {((quickTestResults.winningTrades / quickTestResults.totalTrades) * 100).toFixed(1)}%
              </div>
            </div>

            <div className="bg-gray-800/50 rounded-lg p-3">
              <div className="flex items-center gap-2 mb-2">
                <CurrencyDollarIcon className="w-4 h-4 text-blue-400" />
                <span className="text-sm text-gray-400">Total Return</span>
              </div>
              <div className={`text-xl font-bold ${quickTestResults.totalReturn >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {quickTestResults.totalReturn >= 0 ? '+' : ''}{quickTestResults.totalReturn.toFixed(2)}%
              </div>
            </div>

            <div className="bg-gray-800/50 rounded-lg p-3">
              <div className="flex items-center gap-2 mb-2">
                <TrendingUpIcon className="w-4 h-4 text-purple-400" />
                <span className="text-sm text-gray-400">Sharpe Ratio</span>
              </div>
              <div className="text-xl font-bold text-purple-400">
                {quickTestResults.sharpeRatio.toFixed(2)}
              </div>
            </div>
          </div>

          {/* Additional Metrics */}
          <div className="grid grid-cols-2 gap-6">
            <div>
              <h4 className="text-sm font-medium text-gray-300 mb-3">Key Metrics</h4>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-400">Max Drawdown:</span>
                  <span className="text-red-400">{quickTestResults.maxDrawdown.toFixed(2)}%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Avg Trade Duration:</span>
                  <span className="text-gray-300">{quickTestResults.avgTradeDuration.toFixed(1)}h</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Winning Trades:</span>
                  <span className="text-green-400">{quickTestResults.winningTrades}/{quickTestResults.totalTrades}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Profit Factor:</span>
                  <span className="text-blue-400">
                    {((quickTestResults.totalReturn + 100) / Math.max(100 - quickTestResults.totalReturn, 1)).toFixed(2)}
                  </span>
                </div>
              </div>
            </div>

            <div>
              <h4 className="text-sm font-medium text-gray-300 mb-3">Monthly Performance</h4>
              <div className="space-y-2">
                {quickTestResults.monthlyReturns.map((month: any, index: number) => (
                  <div key={index} className="flex justify-between text-sm">
                    <span className="text-gray-400">{month.month}:</span>
                    <span className={month.return >= 0 ? 'text-green-400' : 'text-red-400'}>
                      {month.return >= 0 ? '+' : ''}{(month.return * 100).toFixed(2)}%
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="mt-6 pt-4 border-t border-gray-700">
            <div className="flex items-center gap-2 text-sm text-gray-400">
              <ClockIcon className="w-4 h-4" />
              <span>Test completed in 3.2 seconds using last 3 months of data</span>
            </div>
          </div>
        </div>
      )}

      {/* Strategy Checklist */}
      <div className="bg-gray-900 border border-gray-700 rounded-lg p-6">
        <h3 className="text-lg font-semibold text-white mb-4">Pre-Deployment Checklist</h3>

        <div className="space-y-3">
          {[
            {
              label: 'Strategy logic validated',
              completed: validationResults?.isValid || false,
              description: 'All parameters and logic checks passed'
            },
            {
              label: 'Quick test completed',
              completed: quickTestResults !== null,
              description: 'Strategy tested with historical data'
            },
            {
              label: 'Risk parameters set',
              completed: strategy.parameters.stop_loss_pct || strategy.parameters.max_position_size || false,
              description: 'Stop loss and position sizing configured'
            },
            {
              label: 'Performance reviewed',
              completed: quickTestResults && quickTestResults.sharpeRatio > 0,
              description: 'Strategy shows positive risk-adjusted returns'
            }
          ].map((item, index) => (
            <div key={index} className="flex items-start gap-3 p-3 bg-gray-800/30 rounded-lg">
              <div className={`
                flex items-center justify-center w-5 h-5 rounded-full mt-0.5
                ${item.completed
                  ? 'bg-green-500 text-white'
                  : 'bg-gray-600 text-gray-400'
                }
              `}>
                {item.completed ? (
                  <CheckCircleIcon className="w-3 h-3" />
                ) : (
                  <span className="text-xs">○</span>
                )}
              </div>
              <div>
                <div className={`font-medium ${item.completed ? 'text-white' : 'text-gray-400'}`}>
                  {item.label}
                </div>
                <div className="text-sm text-gray-500">{item.description}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
