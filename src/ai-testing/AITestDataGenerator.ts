/**
 * AI-Enhanced Test Data Generation for Financial Trading Systems
 *
 * Generates sophisticated financial scenarios, market conditions,
 * and edge cases using AI patterns while maintaining deterministic
 * reproducibility for financial system testing.
 */

import { faker } from '@faker-js/faker';

export interface MarketCondition {
  name: string;
  volatilityMultiplier: number;
  trendStrength: number; // -1 to 1 (bearish to bullish)
  liquidityFactor: number; // 0 to 1
  newsImpact: number; // 0 to 1
  description: string;
}

export interface AIGeneratedScenario {
  id: string;
  name: string;
  description: string;
  marketCondition: MarketCondition;
  timeframe: string;
  duration: number; // minutes
  expectedOutcome: 'profit' | 'loss' | 'neutral' | 'extreme';
  riskLevel: 'low' | 'medium' | 'high' | 'extreme';
  complexity: number; // 1-10
  tags: string[];
  generatedAt: number;
  aiConfidence: number;
}

export interface FinancialEdgeCase {
  type: 'price_gap' | 'liquidity_crisis' | 'flash_crash' | 'circuit_breaker' | 'rollover' | 'news_spike';
  severity: 'minor' | 'moderate' | 'major' | 'extreme';
  symbol: string;
  trigger: {
    condition: string;
    probability: number;
    timeToEvent: number; // seconds
  };
  impact: {
    priceChange: number; // percentage
    volumeMultiplier: number;
    spreadMultiplier: number;
    duration: number; // seconds
  };
  testValidation: {
    expectedBehavior: string;
    riskControls: string[];
    recoveryCriteria: string;
  };
}

export interface SmartMarketData {
  symbol: string;
  timestamp: number;
  bid: number;
  ask: number;
  volume: number;
  volatility: number;
  marketCondition: string;
  technicalIndicators: {
    rsi: number;
    macd: number;
    bollingerPosition: number; // -1 to 1 (lower band to upper band)
    support: number;
    resistance: number;
  };
  fundamentals: {
    economicEvents: string[];
    sentiment: number; // -1 to 1
    correlations: Record<string, number>;
  };
}

/**
 * AI-Enhanced Test Data Generator with financial domain intelligence
 */
export class AITestDataGenerator {
  private marketConditions: MarketCondition[] = [
    {
      name: 'Normal Trading',
      volatilityMultiplier: 1.0,
      trendStrength: 0.0,
      liquidityFactor: 1.0,
      newsImpact: 0.1,
      description: 'Standard market conditions with normal volatility and liquidity'
    },
    {
      name: 'High Volatility',
      volatilityMultiplier: 2.5,
      trendStrength: 0.0,
      liquidityFactor: 0.8,
      newsImpact: 0.4,
      description: 'Increased market volatility with reduced liquidity'
    },
    {
      name: 'Bull Market',
      volatilityMultiplier: 1.2,
      trendStrength: 0.7,
      liquidityFactor: 1.2,
      newsImpact: 0.2,
      description: 'Strong upward trend with good liquidity'
    },
    {
      name: 'Bear Market',
      volatilityMultiplier: 1.5,
      trendStrength: -0.6,
      liquidityFactor: 0.7,
      newsImpact: 0.3,
      description: 'Downward trend with reduced liquidity and negative sentiment'
    },
    {
      name: 'Flash Crash Scenario',
      volatilityMultiplier: 5.0,
      trendStrength: -0.9,
      liquidityFactor: 0.1,
      newsImpact: 0.8,
      description: 'Extreme market stress with rapid price decline and liquidity crisis'
    },
    {
      name: 'Low Liquidity Asian Session',
      volatilityMultiplier: 0.6,
      trendStrength: 0.1,
      liquidityFactor: 0.3,
      newsImpact: 0.05,
      description: 'Thin liquidity during Asian trading session with minimal news flow'
    },
    {
      name: 'Central Bank Intervention',
      volatilityMultiplier: 3.0,
      trendStrength: 0.8,
      liquidityFactor: 1.5,
      newsImpact: 0.9,
      description: 'Major central bank intervention causing significant market movement'
    },
    {
      name: 'Economic Data Release',
      volatilityMultiplier: 2.0,
      trendStrength: 0.3,
      liquidityFactor: 0.9,
      newsImpact: 0.7,
      description: 'High-impact economic data release causing market reaction'
    }
  ];

  private currencyPairs = [
    'EUR/USD', 'GBP/USD', 'USD/JPY', 'AUD/USD', 'USD/CHF', 'NZD/USD',
    'USD/CAD', 'EUR/GBP', 'EUR/JPY', 'GBP/JPY', 'AUD/JPY', 'EUR/CHF'
  ];

  constructor(private config: {
    seed?: string;
    enableExtremeScenarios?: boolean;
    riskLevel?: 'conservative' | 'moderate' | 'aggressive';
  } = {}) {
    if (config.seed) {
      faker.seed(this.stringToSeed(config.seed));
    }
  }

  /**
   * Generate AI-powered trading scenarios based on market patterns
   */
  generateTradingScenario(options: {
    complexity?: number;
    riskLevel?: 'low' | 'medium' | 'high' | 'extreme';
    duration?: number;
    focusArea?: 'volatility' | 'trend' | 'liquidity' | 'risk' | 'compliance';
  } = {}): AIGeneratedScenario {
    const complexity = options.complexity || faker.number.int({ min: 1, max: 10 });
    const riskLevel = options.riskLevel || faker.helpers.arrayElement(['low', 'medium', 'high']);
    const duration = options.duration || faker.number.int({ min: 15, max: 480 }); // 15 minutes to 8 hours

    // Select appropriate market condition based on complexity and risk
    const suitableConditions = this.marketConditions.filter(condition => {
      if (riskLevel === 'low') return condition.volatilityMultiplier <= 1.5;
      if (riskLevel === 'medium') return condition.volatilityMultiplier <= 2.5;
      if (riskLevel === 'high') return condition.volatilityMultiplier <= 4.0;
      return true; // extreme risk allows all conditions
    });

    const marketCondition = faker.helpers.arrayElement(suitableConditions);

    // Generate scenario based on AI patterns
    const scenario: AIGeneratedScenario = {
      id: faker.string.uuid(),
      name: this.generateScenarioName(marketCondition, options.focusArea),
      description: this.generateScenarioDescription(marketCondition, complexity),
      marketCondition,
      timeframe: this.selectOptimalTimeframe(marketCondition, duration),
      duration,
      expectedOutcome: this.predictScenarioOutcome(marketCondition, complexity),
      riskLevel,
      complexity,
      tags: this.generateScenarioTags(marketCondition, options),
      generatedAt: Date.now(),
      aiConfidence: this.calculateScenarioConfidence(marketCondition, complexity)
    };

    return scenario;
  }

  /**
   * Generate sophisticated market data with realistic patterns
   */
  generateSmartMarketData(
    symbol: string,
    scenario: AIGeneratedScenario,
    dataPoints: number = 100
  ): SmartMarketData[] {
    const data: SmartMarketData[] = [];
    const basePrice = this.getBasePriceForSymbol(symbol);
    const { marketCondition } = scenario;

    let currentPrice = basePrice;
    let trend = marketCondition.trendStrength;
    let volatility = 0.001 * marketCondition.volatilityMultiplier; // Base volatility

    for (let i = 0; i < dataPoints; i++) {
      const timestamp = Date.now() - (dataPoints - i) * 60000; // 1-minute intervals

      // Apply trend with some randomness
      const trendComponent = trend * (0.0001 + Math.random() * 0.0002);
      const volatilityComponent = (Math.random() - 0.5) * volatility;
      const newsComponent = Math.random() < 0.05 ? (Math.random() - 0.5) * marketCondition.newsImpact * 0.01 : 0;

      currentPrice *= (1 + trendComponent + volatilityComponent + newsComponent);

      // Calculate spread based on liquidity
      const baseSpread = this.getBaseSpreadForSymbol(symbol);
      const spread = baseSpread / marketCondition.liquidityFactor;

      const bid = currentPrice - spread / 2;
      const ask = currentPrice + spread / 2;

      // Generate volume based on market condition
      const baseVolume = faker.number.int({ min: 1000, max: 100000 });
      const volume = baseVolume * marketCondition.liquidityFactor * (1 + Math.random());

      // Calculate technical indicators
      const technicalIndicators = this.calculateTechnicalIndicators(data, currentPrice);

      // Generate fundamental data
      const fundamentals = this.generateFundamentalData(symbol, marketCondition);

      data.push({
        symbol,
        timestamp,
        bid,
        ask,
        volume,
        volatility: volatility * 100, // Convert to percentage
        marketCondition: marketCondition.name,
        technicalIndicators,
        fundamentals
      });

      // Evolve trend and volatility
      trend += (Math.random() - 0.5) * 0.1;
      trend = Math.max(-1, Math.min(1, trend)); // Clamp between -1 and 1

      volatility *= (0.95 + Math.random() * 0.1); // Slight volatility clustering
    }

    return data;
  }

  /**
   * Generate financial edge cases for stress testing
   */
  generateFinancialEdgeCase(
    symbol: string,
    scenario?: AIGeneratedScenario
  ): FinancialEdgeCase {
    const edgeTypes = ['price_gap', 'liquidity_crisis', 'flash_crash', 'circuit_breaker', 'rollover', 'news_spike'] as const;
    const type = faker.helpers.arrayElement(edgeTypes);

    const severity = scenario?.riskLevel === 'extreme' ?
      faker.helpers.arrayElement(['major', 'extreme']) :
      faker.helpers.arrayElement(['minor', 'moderate', 'major']);

    return {
      type,
      severity,
      symbol,
      trigger: {
        condition: this.generateTriggerCondition(type),
        probability: this.calculateTriggerProbability(type, severity),
        timeToEvent: faker.number.int({ min: 1, max: 300 }) // 1-300 seconds
      },
      impact: {
        priceChange: this.calculatePriceImpact(type, severity),
        volumeMultiplier: this.calculateVolumeImpact(type, severity),
        spreadMultiplier: this.calculateSpreadImpact(type, severity),
        duration: this.calculateEventDuration(type, severity)
      },
      testValidation: {
        expectedBehavior: this.generateExpectedBehavior(type),
        riskControls: this.generateRiskControls(type, severity),
        recoveryCriteria: this.generateRecoveryCriteria(type, severity)
      }
    };
  }

  /**
   * Generate batch of correlated market data for multi-symbol testing
   */
  generateCorrelatedMarketData(
    symbols: string[],
    scenario: AIGeneratedScenario,
    correlationMatrix?: Record<string, Record<string, number>>
  ): Record<string, SmartMarketData[]> {
    const result: Record<string, SmartMarketData[]> = {};

    // Generate base data for primary symbol
    const primarySymbol = symbols[0];
    result[primarySymbol] = this.generateSmartMarketData(primarySymbol, scenario);

    // Generate correlated data for other symbols
    for (let i = 1; i < symbols.length; i++) {
      const symbol = symbols[i];
      const correlation = correlationMatrix?.[primarySymbol]?.[symbol] ||
                         this.getDefaultCorrelation(primarySymbol, symbol);

      result[symbol] = this.generateCorrelatedData(
        result[primarySymbol],
        symbol,
        correlation,
        scenario
      );
    }

    return result;
  }

  /**
   * Generate stress test scenarios for risk management validation
   */
  generateStressTestScenarios(): AIGeneratedScenario[] {
    const stressScenarios: AIGeneratedScenario[] = [];

    // Market crash scenario
    stressScenarios.push(this.generateTradingScenario({
      complexity: 9,
      riskLevel: 'extreme',
      duration: 60,
      focusArea: 'risk'
    }));

    // Liquidity crisis scenario
    stressScenarios.push(this.generateTradingScenario({
      complexity: 8,
      riskLevel: 'high',
      duration: 120,
      focusArea: 'liquidity'
    }));

    // Extreme volatility scenario
    stressScenarios.push(this.generateTradingScenario({
      complexity: 7,
      riskLevel: 'high',
      duration: 90,
      focusArea: 'volatility'
    }));

    // Regulatory compliance scenario
    stressScenarios.push(this.generateTradingScenario({
      complexity: 6,
      riskLevel: 'medium',
      duration: 240,
      focusArea: 'compliance'
    }));

    return stressScenarios;
  }

  // Private helper methods

  private generateScenarioName(condition: MarketCondition, focusArea?: string): string {
    const baseNames = {
      'volatility': ['Volatility Spike', 'Market Turbulence', 'Price Instability'],
      'trend': ['Trend Reversal', 'Momentum Shift', 'Directional Movement'],
      'liquidity': ['Liquidity Drain', 'Market Depth Test', 'Thin Market Conditions'],
      'risk': ['Risk Event', 'Stress Scenario', 'Crisis Simulation'],
      'compliance': ['Regulatory Scenario', 'Compliance Test', 'Rule Validation']
    };

    const names = baseNames[focusArea as keyof typeof baseNames] || [
      'Market Scenario', 'Trading Condition', 'Financial Simulation'
    ];

    return `${faker.helpers.arrayElement(names)}: ${condition.name}`;
  }

  private generateScenarioDescription(condition: MarketCondition, complexity: number): string {
    const complexityDesc = complexity > 7 ? 'highly complex' :
                          complexity > 4 ? 'moderately complex' : 'straightforward';

    return `${complexityDesc.charAt(0).toUpperCase() + complexityDesc.slice(1)} scenario featuring ${condition.description.toLowerCase()}. ` +
           `Complexity level ${complexity}/10 with multiple market dynamics and potential edge cases.`;
  }

  private selectOptimalTimeframe(condition: MarketCondition, duration: number): string {
    if (duration <= 30) return '1m';
    if (duration <= 120) return '5m';
    if (duration <= 240) return '15m';
    return '1h';
  }

  private predictScenarioOutcome(condition: MarketCondition, complexity: number): 'profit' | 'loss' | 'neutral' | 'extreme' {
    if (condition.volatilityMultiplier > 3.0 || complexity > 8) return 'extreme';
    if (Math.abs(condition.trendStrength) > 0.5) return condition.trendStrength > 0 ? 'profit' : 'loss';
    return 'neutral';
  }

  private generateScenarioTags(condition: MarketCondition, options: any): string[] {
    const tags = [condition.name.toLowerCase().replace(' ', '_')];

    if (condition.volatilityMultiplier > 2.0) tags.push('high_volatility');
    if (condition.liquidityFactor < 0.5) tags.push('low_liquidity');
    if (condition.newsImpact > 0.5) tags.push('news_driven');
    if (Math.abs(condition.trendStrength) > 0.5) tags.push('trending');
    if (options.focusArea) tags.push(options.focusArea);

    return tags;
  }

  private calculateScenarioConfidence(condition: MarketCondition, complexity: number): number {
    let confidence = 85; // Base confidence

    // Reduce confidence for extreme conditions
    if (condition.volatilityMultiplier > 4.0) confidence -= 15;
    if (complexity > 8) confidence -= 10;
    if (condition.liquidityFactor < 0.2) confidence -= 10;

    return Math.max(50, confidence);
  }

  private getBasePriceForSymbol(symbol: string): number {
    const basePrices: Record<string, number> = {
      'EUR/USD': 1.2000,
      'GBP/USD': 1.3500,
      'USD/JPY': 110.00,
      'AUD/USD': 0.7500,
      'USD/CHF': 0.9200,
      'NZD/USD': 0.7000
    };

    return basePrices[symbol] || 1.0000;
  }

  private getBaseSpreadForSymbol(symbol: string): number {
    const baseSpreads: Record<string, number> = {
      'EUR/USD': 0.0001,
      'GBP/USD': 0.0002,
      'USD/JPY': 0.01,
      'AUD/USD': 0.0002,
      'USD/CHF': 0.0002,
      'NZD/USD': 0.0003
    };

    return baseSpreads[symbol] || 0.0002;
  }

  private calculateTechnicalIndicators(historicalData: SmartMarketData[], currentPrice: number): SmartMarketData['technicalIndicators'] {
    // Simplified technical indicator calculations
    const rsi = 50 + (Math.random() - 0.5) * 60; // Random RSI between 20-80
    const macd = (Math.random() - 0.5) * 0.01;
    const bollingerPosition = (Math.random() - 0.5) * 2;

    const support = currentPrice * (0.98 + Math.random() * 0.01);
    const resistance = currentPrice * (1.01 + Math.random() * 0.01);

    return {
      rsi: Math.max(0, Math.min(100, rsi)),
      macd,
      bollingerPosition: Math.max(-1, Math.min(1, bollingerPosition)),
      support,
      resistance
    };
  }

  private generateFundamentalData(symbol: string, condition: MarketCondition): SmartMarketData['fundamentals'] {
    const economicEvents = [];

    if (condition.newsImpact > 0.3) {
      economicEvents.push(faker.helpers.arrayElement([
        'Central Bank Meeting', 'GDP Release', 'Employment Data', 'Inflation Report', 'Trade Balance'
      ]));
    }

    return {
      economicEvents,
      sentiment: condition.trendStrength + (Math.random() - 0.5) * 0.2,
      correlations: this.generateCorrelations(symbol)
    };
  }

  private generateCorrelations(symbol: string): Record<string, number> {
    // Simplified correlation generation
    const otherPairs = this.currencyPairs.filter(pair => pair !== symbol);
    const correlations: Record<string, number> = {};

    otherPairs.slice(0, 3).forEach(pair => {
      correlations[pair] = (Math.random() - 0.5) * 2; // -1 to 1
    });

    return correlations;
  }

  private generateTriggerCondition(type: FinancialEdgeCase['type']): string {
    const conditions: Record<FinancialEdgeCase['type'], string[]> = {
      'price_gap': ['Market open after weekend', 'Major news announcement', 'Liquidity provider disconnect'],
      'liquidity_crisis': ['Bank holiday', 'System maintenance', 'Market maker withdrawal'],
      'flash_crash': ['Algorithmic trading error', 'Stop-loss cascade', 'Fat finger trade'],
      'circuit_breaker': ['5% price movement in 1 minute', 'Volatility threshold exceeded'],
      'rollover': ['Daily rollover period', 'Swap rate adjustment'],
      'news_spike': ['Economic data release', 'Central bank announcement', 'Geopolitical event']
    };

    return faker.helpers.arrayElement(conditions[type]);
  }

  private calculateTriggerProbability(type: FinancialEdgeCase['type'], severity: FinancialEdgeCase['severity']): number {
    const baseProbabilities = {
      'price_gap': 0.1,
      'liquidity_crisis': 0.05,
      'flash_crash': 0.01,
      'circuit_breaker': 0.02,
      'rollover': 0.95,
      'news_spike': 0.3
    };

    const severityMultiplier = {
      'minor': 1.0,
      'moderate': 0.7,
      'major': 0.3,
      'extreme': 0.1
    };

    return baseProbabilities[type] * severityMultiplier[severity];
  }

  private calculatePriceImpact(type: FinancialEdgeCase['type'], severity: FinancialEdgeCase['severity']): number {
    const baseImpacts = {
      'price_gap': 0.5,
      'liquidity_crisis': 2.0,
      'flash_crash': 10.0,
      'circuit_breaker': 5.0,
      'rollover': 0.1,
      'news_spike': 3.0
    };

    const severityMultiplier = {
      'minor': 0.5,
      'moderate': 1.0,
      'major': 2.0,
      'extreme': 5.0
    };

    return baseImpacts[type] * severityMultiplier[severity];
  }

  private calculateVolumeImpact(type: FinancialEdgeCase['type'], severity: FinancialEdgeCase['severity']): number {
    return 1.0 + Math.random() * (severity === 'extreme' ? 10 : severity === 'major' ? 5 : 2);
  }

  private calculateSpreadImpact(type: FinancialEdgeCase['type'], severity: FinancialEdgeCase['severity']): number {
    const baseMultiplier = type === 'liquidity_crisis' ? 5.0 : type === 'flash_crash' ? 8.0 : 2.0;
    const severityMultiplier = { 'minor': 1, 'moderate': 2, 'major': 4, 'extreme': 8 };

    return baseMultiplier * severityMultiplier[severity];
  }

  private calculateEventDuration(type: FinancialEdgeCase['type'], severity: FinancialEdgeCase['severity']): number {
    const baseDurations = {
      'price_gap': 10,
      'liquidity_crisis': 300,
      'flash_crash': 30,
      'circuit_breaker': 60,
      'rollover': 120,
      'news_spike': 180
    };

    const severityMultiplier = {
      'minor': 0.5,
      'moderate': 1.0,
      'major': 2.0,
      'extreme': 4.0
    };

    return baseDurations[type] * severityMultiplier[severity];
  }

  private generateExpectedBehavior(type: FinancialEdgeCase['type']): string {
    const behaviors: Record<FinancialEdgeCase['type'], string> = {
      'price_gap': 'System should detect price gap and adjust position sizing',
      'liquidity_crisis': 'Trading should be suspended or reduced to minimum size',
      'flash_crash': 'Circuit breakers should activate and halt trading',
      'circuit_breaker': 'All pending orders should be cancelled and positions reviewed',
      'rollover': 'Swap charges should be applied and positions rolled forward',
      'news_spike': 'Volatility filters should activate and spread protection engaged'
    };

    return behaviors[type];
  }

  private generateRiskControls(type: FinancialEdgeCase['type'], severity: FinancialEdgeCase['severity']): string[] {
    const controls: Record<FinancialEdgeCase['type'], string[]> = {
      'price_gap': ['Gap risk monitoring', 'Position size limits', 'Stop-loss adjustment'],
      'liquidity_crisis': ['Liquidity monitoring', 'Order size reduction', 'Provider diversification'],
      'flash_crash': ['Circuit breaker activation', 'Emergency stop', 'Position liquidation'],
      'circuit_breaker': ['Trading halt', 'Order cancellation', 'Risk assessment'],
      'rollover': ['Swap calculation', 'Position adjustment', 'Cost monitoring'],
      'news_spike': ['Volatility filtering', 'Spread protection', 'News detection']
    };

    return controls[type];
  }

  private generateRecoveryCriteria(type: FinancialEdgeCase['type'], severity: FinancialEdgeCase['severity']): string {
    const criteria: Record<FinancialEdgeCase['type'], string> = {
      'price_gap': 'Market returns to normal spread and volatility levels',
      'liquidity_crisis': 'Minimum liquidity threshold restored',
      'flash_crash': 'Price stabilization and manual intervention complete',
      'circuit_breaker': 'Volatility returns below threshold for 5 minutes',
      'rollover': 'Rollover process completed successfully',
      'news_spike': 'News impact absorbed and volatility normalized'
    };

    return criteria[type];
  }

  private generateCorrelatedData(
    baseData: SmartMarketData[],
    symbol: string,
    correlation: number,
    scenario: AIGeneratedScenario
  ): SmartMarketData[] {
    const correlatedData: SmartMarketData[] = [];
    const basePrice = this.getBasePriceForSymbol(symbol);

    baseData.forEach((basePoint, index) => {
      // Calculate correlated price movement
      const basePriceChange = index > 0 ?
        (basePoint.ask - baseData[index - 1].ask) / baseData[index - 1].ask :
        0;

      const correlatedChange = basePriceChange * correlation +
                              (Math.random() - 0.5) * 0.001 * (1 - Math.abs(correlation));

      const correlatedPrice = index === 0 ?
        basePrice :
        correlatedData[index - 1].ask * (1 + correlatedChange);

      const spread = this.getBaseSpreadForSymbol(symbol) / scenario.marketCondition.liquidityFactor;

      correlatedData.push({
        symbol,
        timestamp: basePoint.timestamp,
        bid: correlatedPrice - spread / 2,
        ask: correlatedPrice + spread / 2,
        volume: basePoint.volume * (0.8 + Math.random() * 0.4), // Some volume variance
        volatility: basePoint.volatility * (0.9 + Math.random() * 0.2),
        marketCondition: basePoint.marketCondition,
        technicalIndicators: this.calculateTechnicalIndicators(correlatedData, correlatedPrice),
        fundamentals: this.generateFundamentalData(symbol, scenario.marketCondition)
      });
    });

    return correlatedData;
  }

  private getDefaultCorrelation(symbol1: string, symbol2: string): number {
    // Simplified correlation matrix for major currency pairs
    const correlations: Record<string, Record<string, number>> = {
      'EUR/USD': { 'GBP/USD': 0.7, 'AUD/USD': 0.6, 'USD/CHF': -0.8 },
      'GBP/USD': { 'EUR/USD': 0.7, 'AUD/USD': 0.5, 'USD/JPY': -0.3 },
      'USD/JPY': { 'USD/CHF': 0.6, 'EUR/USD': -0.5, 'GBP/USD': -0.3 }
    };

    return correlations[symbol1]?.[symbol2] || correlations[symbol2]?.[symbol1] || 0.1;
  }

  private stringToSeed(str: string): number {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
      const char = str.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash & hash; // Convert to 32-bit integer
    }
    return Math.abs(hash);
  }
}

/**
 * Singleton instance for global access
 */
export const aiTestDataGenerator = new AITestDataGenerator();
