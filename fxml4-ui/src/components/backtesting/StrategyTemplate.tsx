/**
 * Strategy Template Component
 *
 * Displays available strategy templates for selection
 */

'use client';

import { Button } from '@/components/ui/button';
import {
  ChartBarIcon,
  BeakerIcon,
  RocketLaunchIcon,
  Cog6ToothIcon,
  StarIcon,
  ClockIcon,
  TrendingUpIcon
} from '@heroicons/react/24/outline';

interface StrategyType {
  id: string;
  name: string;
  description: string;
  icon: any;
  complexity: string;
  category: string;
}

interface StrategyTemplateProps {
  selectedType?: string;
  onSelect: (type: string) => void;
  strategyTypes: StrategyType[];
}

const COMPLEXITY_COLORS = {
  'Beginner': 'text-green-400 bg-green-500/20',
  'Intermediate': 'text-yellow-400 bg-yellow-500/20',
  'Advanced': 'text-orange-400 bg-orange-500/20',
  'Expert': 'text-red-400 bg-red-500/20'
};

const CATEGORY_ICONS = {
  'Trend Following': TrendingUpIcon,
  'Mean Reversion': BeakerIcon,
  'Volatility': ChartBarIcon,
  'Machine Learning': RocketLaunchIcon,
  'Pattern Recognition': StarIcon,
  'Custom': Cog6ToothIcon
};

export default function StrategyTemplate({
  selectedType,
  onSelect,
  strategyTypes
}: StrategyTemplateProps) {

  const getTemplateDetails = (strategyId: string) => {
    const details = {
      ma_crossover: {
        features: ['Trend Following', 'Simple Logic', 'Low Latency', 'Good for Beginners'],
        pros: ['Easy to understand', 'Works well in trending markets', 'Low computational cost'],
        cons: ['Poor performance in sideways markets', 'Lagging signals', 'Frequent false signals'],
        timeframes: ['5m', '15m', '1h', '4h', '1d'],
        instruments: ['All Forex Pairs', 'Major Indices', 'Commodities'],
        expectedReturn: '8-15% annually',
        maxDrawdown: '5-12%',
        winRate: '45-55%'
      },
      rsi_reversal: {
        features: ['Mean Reversion', 'Momentum Based', 'Contrarian Approach', 'Good for Ranges'],
        pros: ['Works well in ranging markets', 'Clear entry/exit rules', 'Good risk/reward'],
        cons: ['Can struggle in strong trends', 'Requires market context', 'False signals in trends'],
        timeframes: ['15m', '1h', '4h', '1d'],
        instruments: ['Major Forex Pairs', 'Volatile Stocks', 'Crypto'],
        expectedReturn: '12-20% annually',
        maxDrawdown: '8-15%',
        winRate: '55-65%'
      },
      bollinger_bands: {
        features: ['Volatility Based', 'Dynamic Levels', 'Multiple Strategies', 'Adaptive'],
        pros: ['Adapts to market volatility', 'Multiple trading approaches', 'Visual clarity'],
        cons: ['Can be whipsawed', 'Requires parameter tuning', 'Complex interpretation'],
        timeframes: ['15m', '1h', '4h', '1d'],
        instruments: ['All Markets', 'Especially Forex', 'High Volume Assets'],
        expectedReturn: '10-18% annually',
        maxDrawdown: '6-14%',
        winRate: '50-60%'
      },
      ml_signals: {
        features: ['AI Powered', 'Pattern Recognition', 'Multi-Factor', 'Adaptive Learning'],
        pros: ['Learns from data', 'Complex pattern recognition', 'Continuous improvement'],
        cons: ['Black box approach', 'Requires lots of data', 'Can overfit'],
        timeframes: ['1h', '4h', '1d'],
        instruments: ['Major Pairs', 'Liquid Markets', 'High Data Availability'],
        expectedReturn: '15-25% annually',
        maxDrawdown: '10-20%',
        winRate: '55-70%'
      },
      elliott_wave: {
        features: ['Wave Analysis', 'Fibonacci Based', 'Long-term Focus', 'Pattern Based'],
        pros: ['Excellent for major moves', 'Clear wave structure', 'Multiple timeframes'],
        cons: ['Subjective interpretation', 'Complex analysis', 'Requires experience'],
        timeframes: ['4h', '1d', '1w'],
        instruments: ['Major Indices', 'Major Forex', 'Gold/Silver'],
        expectedReturn: '20-35% annually',
        maxDrawdown: '15-25%',
        winRate: '40-55%'
      },
      custom: {
        features: ['Fully Customizable', 'Your Logic', 'Advanced Scripting', 'Unlimited Flexibility'],
        pros: ['Complete control', 'Unique strategies', 'Perfect customization'],
        cons: ['Requires programming', 'Time intensive', 'Debugging needed'],
        timeframes: ['Any'],
        instruments: ['Any'],
        expectedReturn: 'Variable',
        maxDrawdown: 'Variable',
        winRate: 'Variable'
      }
    };

    return details[strategyId as keyof typeof details] || details.custom;
  };

  return (
    <div className="h-full">
      <div className="mb-6">
        <h3 className="text-lg font-semibold text-white mb-2">Choose a Strategy Template</h3>
        <p className="text-gray-400">
          Select a strategy type to get started. You can customize parameters in the next step.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 h-full">
        {/* Strategy Cards */}
        <div className="space-y-4 overflow-y-auto">
          {strategyTypes.map((strategyType) => {
            const IconComponent = strategyType.icon;
            const CategoryIcon = CATEGORY_ICONS[strategyType.category as keyof typeof CATEGORY_ICONS];
            const isSelected = selectedType === strategyType.id;

            return (
              <div
                key={strategyType.id}
                className={`
                  border rounded-lg p-4 cursor-pointer transition-all duration-200 hover:scale-[1.02]
                  ${isSelected
                    ? 'border-blue-500 bg-blue-500/10 shadow-lg shadow-blue-500/20'
                    : 'border-gray-700 bg-gray-800/50 hover:border-gray-600'
                  }
                `}
                onClick={() => onSelect(strategyType.id)}
              >
                <div className="flex items-start gap-3">
                  <div className={`
                    flex items-center justify-center w-10 h-10 rounded-lg
                    ${isSelected ? 'bg-blue-500 text-white' : 'bg-gray-700 text-gray-300'}
                  `}>
                    <IconComponent className="w-5 h-5" />
                  </div>

                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <h4 className="font-semibold text-white">{strategyType.name}</h4>
                      <span className={`
                        text-xs px-2 py-0.5 rounded-full font-medium
                        ${COMPLEXITY_COLORS[strategyType.complexity as keyof typeof COMPLEXITY_COLORS]}
                      `}>
                        {strategyType.complexity}
                      </span>
                    </div>

                    <p className="text-sm text-gray-400 mb-2">
                      {strategyType.description}
                    </p>

                    <div className="flex items-center gap-2 text-xs text-gray-500">
                      <CategoryIcon className="w-3 h-3" />
                      <span>{strategyType.category}</span>
                      <span>•</span>
                      <ClockIcon className="w-3 h-3" />
                      <span>5-10 min setup</span>
                    </div>
                  </div>

                  <div className="flex items-center">
                    <Button
                      variant={isSelected ? "default" : "outline"}
                      size="sm"
                      className="gap-2"
                      onClick={(e) => {
                        e.stopPropagation();
                        onSelect(strategyType.id);
                      }}
                    >
                      {isSelected ? 'Selected' : 'Select'}
                    </Button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* Strategy Details */}
        <div className="bg-gray-900 border border-gray-700 rounded-lg p-6 h-fit sticky top-0">
          {selectedType ? (
            <div>
              <div className="flex items-center gap-2 mb-4">
                <div className="w-8 h-8 bg-blue-500 rounded-lg flex items-center justify-center">
                  {(() => {
                    const strategy = strategyTypes.find(s => s.id === selectedType);
                    const IconComponent = strategy?.icon || Cog6ToothIcon;
                    return <IconComponent className="w-4 h-4 text-white" />;
                  })()}
                </div>
                <h4 className="text-lg font-semibold text-white">
                  {strategyTypes.find(s => s.id === selectedType)?.name}
                </h4>
              </div>

              {(() => {
                const details = getTemplateDetails(selectedType);
                return (
                  <div className="space-y-4">
                    {/* Key Features */}
                    <div>
                      <h5 className="text-sm font-medium text-gray-300 mb-2">Key Features</h5>
                      <div className="flex flex-wrap gap-1">
                        {details.features.map((feature, index) => (
                          <span
                            key={index}
                            className="text-xs px-2 py-1 bg-gray-800 text-gray-300 rounded-full"
                          >
                            {feature}
                          </span>
                        ))}
                      </div>
                    </div>

                    {/* Performance Metrics */}
                    <div>
                      <h5 className="text-sm font-medium text-gray-300 mb-2">Expected Performance</h5>
                      <div className="grid grid-cols-2 gap-3 text-sm">
                        <div className="bg-gray-800/50 rounded p-2">
                          <div className="text-gray-400">Expected Return</div>
                          <div className="text-green-400 font-medium">{details.expectedReturn}</div>
                        </div>
                        <div className="bg-gray-800/50 rounded p-2">
                          <div className="text-gray-400">Max Drawdown</div>
                          <div className="text-red-400 font-medium">{details.maxDrawdown}</div>
                        </div>
                        <div className="bg-gray-800/50 rounded p-2">
                          <div className="text-gray-400">Win Rate</div>
                          <div className="text-blue-400 font-medium">{details.winRate}</div>
                        </div>
                        <div className="bg-gray-800/50 rounded p-2">
                          <div className="text-gray-400">Timeframes</div>
                          <div className="text-gray-300 font-medium">
                            {details.timeframes.slice(0, 2).join(', ')}
                            {details.timeframes.length > 2 && '...'}
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Pros and Cons */}
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <h5 className="text-sm font-medium text-green-400 mb-2">Pros</h5>
                        <ul className="text-xs text-gray-400 space-y-1">
                          {details.pros.map((pro, index) => (
                            <li key={index} className="flex items-start gap-1">
                              <span className="text-green-400 mt-0.5">+</span>
                              <span>{pro}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                      <div>
                        <h5 className="text-sm font-medium text-red-400 mb-2">Cons</h5>
                        <ul className="text-xs text-gray-400 space-y-1">
                          {details.cons.map((con, index) => (
                            <li key={index} className="flex items-start gap-1">
                              <span className="text-red-400 mt-0.5">-</span>
                              <span>{con}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    </div>

                    {/* Suitable Markets */}
                    <div>
                      <h5 className="text-sm font-medium text-gray-300 mb-2">Suitable Markets</h5>
                      <p className="text-xs text-gray-400">
                        {details.instruments.join(', ')}
                      </p>
                    </div>
                  </div>
                );
              })()}
            </div>
          ) : (
            <div className="text-center py-8">
              <ChartBarIcon className="w-12 h-12 text-gray-400 mx-auto mb-3" />
              <h4 className="text-lg font-medium text-gray-300 mb-2">Select a Strategy</h4>
              <p className="text-sm text-gray-400">
                Choose a strategy template to see detailed information and performance metrics.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
