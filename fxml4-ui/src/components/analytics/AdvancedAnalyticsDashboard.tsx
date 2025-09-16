"""
Advanced Analytics Dashboard for Phase 8 - FXML3/LLM Integration & AI-Powered Market Intelligence

This component provides a comprehensive real-time analytics interface integrating:
- AI-powered market regime detection
- Multi-modal pattern recognition (Elliott Wave + LLM)
- Sentiment-driven trade signals with confidence scoring
- Real-time market analyst insights with natural language explanations
"""
import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  TrendingUp,
  TrendingDown,
  Brain,
  Activity,
  AlertTriangle,
  CheckCircle,
  Eye,
  BarChart3,
  Zap,
  Target,
  Clock,
  Lightbulb,
  MessageSquare,
  Layers,
  Waves,
  Search
} from 'lucide-react';
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ScatterChart,
  Scatter,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ComposedChart
} from 'recharts';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card';
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../ui/tabs';
import { Progress } from '../ui/progress';
import { ScrollArea } from '../ui/scroll-area';
import { Separator } from '../ui/separator';
import { Alert, AlertDescription, AlertTitle } from '../ui/alert';

// Types for advanced analytics data
interface MarketRegime {
  id: string;
  name: 'trending' | 'ranging' | 'volatile' | 'breakout';
  confidence: number;
  duration: number;
  characteristics: string[];
  color: string;
  description: string;
}

interface AIInsight {
  id: string;
  type: 'pattern' | 'sentiment' | 'regime' | 'prediction';
  title: string;
  content: string;
  confidence: number;
  source: 'elliott_wave' | 'sentiment_llm' | 'market_regime' | 'multimodal';
  timestamp: string;
  actionable: boolean;
  risk_level: 'low' | 'medium' | 'high';
}

interface SentimentSignal {
  id: string;
  symbol: string;
  signal: 'buy' | 'sell' | 'hold';
  confidence: number;
  sentiment_score: number;
  news_impact: number;
  social_sentiment: number;
  llm_reasoning: string;
  expiry: string;
}

interface PatternRecognition {
  id: string;
  pattern_type: 'elliott_wave' | 'harmonic' | 'chart_pattern' | 'custom';
  name: string;
  confidence: number;
  completion: number;
  target_price: number;
  stop_loss: number;
  timeframe: string;
  validation: {
    fibonacci: boolean;
    volume: boolean;
    sentiment: boolean;
    llm_validated: boolean;
  };
}

interface MarketIntelligence {
  overview: {
    market_state: string;
    primary_trend: 'bullish' | 'bearish' | 'neutral';
    volatility_regime: 'low' | 'normal' | 'high';
    sentiment_bias: number;
  };
  regimes: MarketRegime[];
  ai_insights: AIInsight[];
  sentiment_signals: SentimentSignal[];
  pattern_recognition: PatternRecognition[];
  performance_metrics: {
    accuracy_24h: number;
    signal_count: number;
    profit_factor: number;
    avg_confidence: number;
  };
}

export default function AdvancedAnalyticsDashboard() {
  const [selectedSymbol, setSelectedSymbol] = useState('EUR/USD');
  const [selectedTimeframe, setSelectedTimeframe] = useState<'1h' | '4h' | '1d'>('4h');
  const [activeInsightType, setActiveInsightType] = useState<string>('all');
  const queryClient = useQueryClient();

  // Fetch real-time market intelligence
  const { data: marketIntelligence, isLoading } = useQuery<MarketIntelligence>({
    queryKey: ['marketIntelligence', selectedSymbol, selectedTimeframe],
    queryFn: async () => {
      // Mock data for development - replace with actual API call
      return {
        overview: {
          market_state: 'AI-Enhanced Trending Market',
          primary_trend: 'bullish',
          volatility_regime: 'normal',
          sentiment_bias: 0.73
        },
        regimes: [
          {
            id: '1',
            name: 'trending',
            confidence: 0.87,
            duration: 156,
            characteristics: ['Strong momentum', 'Clear direction', 'Low noise'],
            color: '#22c55e',
            description: 'AI-detected uptrend with high conviction Elliott Wave patterns'
          },
          {
            id: '2',
            name: 'breakout',
            confidence: 0.65,
            duration: 23,
            characteristics: ['Volume surge', 'Key level break', 'Follow-through'],
            color: '#f59e0b',
            description: 'Recent breakout from consolidation with LLM validation'
          }
        ],
        ai_insights: [
          {
            id: '1',
            type: 'pattern',
            title: 'Elliott Wave 5th Wave Extension Detected',
            content: 'AI analysis confirms EUR/USD is completing an extended 5th wave with 94% fibonacci confluence. Target: 1.0950-1.0980. LLM sentiment validation shows bullish bias from ECB dovishness.',
            confidence: 0.94,
            source: 'elliott_wave',
            timestamp: new Date().toISOString(),
            actionable: true,
            risk_level: 'medium'
          },
          {
            id: '2',
            type: 'sentiment',
            title: 'Multi-Source Sentiment Surge',
            content: 'Real-time sentiment analysis from 847 news sources + social media shows strong EUR bullish sentiment (82%). LLM reasoning: ECB policy divergence + USD weakness narrative gaining traction.',
            confidence: 0.89,
            source: 'sentiment_llm',
            timestamp: new Date(Date.now() - 300000).toISOString(),
            actionable: true,
            risk_level: 'low'
          },
          {
            id: '3',
            type: 'regime',
            title: 'Regime Shift to High Momentum',
            content: 'AI regime detector identifies transition from ranging to trending market. Volatility profile suggests sustained move likely. Pattern recognition confidence: 87%.',
            confidence: 0.87,
            source: 'market_regime',
            timestamp: new Date(Date.now() - 600000).toISOString(),
            actionable: true,
            risk_level: 'low'
          }
        ],
        sentiment_signals: [
          {
            id: '1',
            symbol: 'EUR/USD',
            signal: 'buy',
            confidence: 0.91,
            sentiment_score: 0.82,
            news_impact: 0.76,
            social_sentiment: 0.88,
            llm_reasoning: 'ECB dovish pivot narrative strengthening EUR positioning. Technical confluence with Elliott Wave completion suggests upside momentum.',
            expiry: new Date(Date.now() + 14400000).toISOString()
          }
        ],
        pattern_recognition: [
          {
            id: '1',
            pattern_type: 'elliott_wave',
            name: 'Impulse Wave 5 Extension',
            confidence: 0.94,
            completion: 0.78,
            target_price: 1.0965,
            stop_loss: 1.0820,
            timeframe: '4h',
            validation: {
              fibonacci: true,
              volume: true,
              sentiment: true,
              llm_validated: true
            }
          }
        ],
        performance_metrics: {
          accuracy_24h: 0.847,
          signal_count: 23,
          profit_factor: 1.67,
          avg_confidence: 0.835
        }
      };
    },
    refetchInterval: 30000, // Update every 30 seconds
  });

  // Real-time updates
  useEffect(() => {
    const interval = setInterval(() => {
      queryClient.invalidateQueries({ queryKey: ['marketIntelligence'] });
    }, 30000);

    return () => clearInterval(interval);
  }, [queryClient]);

  // Filter insights by type
  const filteredInsights = useMemo(() => {
    if (!marketIntelligence?.ai_insights) return [];
    if (activeInsightType === 'all') return marketIntelligence.ai_insights;
    return marketIntelligence.ai_insights.filter(insight => insight.type === activeInsightType);
  }, [marketIntelligence?.ai_insights, activeInsightType]);

  // Get regime color
  const getRegimeColor = (regime: MarketRegime) => {
    const colors = {
      trending: '#22c55e',
      ranging: '#6b7280',
      volatile: '#ef4444',
      breakout: '#f59e0b'
    };
    return colors[regime.name];
  };

  // Get confidence color
  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.8) return 'text-green-600';
    if (confidence >= 0.6) return 'text-yellow-600';
    return 'text-red-600';
  };

  // Get signal color
  const getSignalColor = (signal: string) => {
    const colors = {
      buy: 'text-green-600 bg-green-50 border-green-200',
      sell: 'text-red-600 bg-red-50 border-red-200',
      hold: 'text-gray-600 bg-gray-50 border-gray-200'
    };
    return colors[signal as keyof typeof colors] || colors.hold;
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="flex items-center space-x-2">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          <span className="text-lg font-medium">Loading AI Analytics...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Advanced Analytics</h1>
          <p className="text-gray-600 mt-1">AI-Powered Market Intelligence & Pattern Recognition</p>
        </div>
        <div className="flex items-center space-x-4">
          <select
            value={selectedSymbol}
            onChange={(e) => setSelectedSymbol(e.target.value)}
            className="border border-gray-300 rounded-md px-3 py-2 bg-white"
          >
            <option value="EUR/USD">EUR/USD</option>
            <option value="GBP/USD">GBP/USD</option>
            <option value="USD/JPY">USD/JPY</option>
            <option value="USD/CHF">USD/CHF</option>
          </select>
          <select
            value={selectedTimeframe}
            onChange={(e) => setSelectedTimeframe(e.target.value as '1h' | '4h' | '1d')}
            className="border border-gray-300 rounded-md px-3 py-2 bg-white"
          >
            <option value="1h">1 Hour</option>
            <option value="4h">4 Hours</option>
            <option value="1d">1 Day</option>
          </select>
        </div>
      </div>

      {/* Overview Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Market State</CardTitle>
            <Brain className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{marketIntelligence?.overview.market_state}</div>
            <p className="text-xs text-muted-foreground">
              AI-Enhanced Analysis
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Sentiment Bias</CardTitle>
            <Activity className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {((marketIntelligence?.overview.sentiment_bias || 0) * 100).toFixed(1)}%
            </div>
            <div className="flex items-center space-x-2 mt-2">
              {marketIntelligence?.overview.sentiment_bias > 0.5 ? (
                <TrendingUp className="h-4 w-4 text-green-600" />
              ) : (
                <TrendingDown className="h-4 w-4 text-red-600" />
              )}
              <span className="text-xs text-muted-foreground">
                Bullish Bias
              </span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">24h Accuracy</CardTitle>
            <Target className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {((marketIntelligence?.performance_metrics.accuracy_24h || 0) * 100).toFixed(1)}%
            </div>
            <p className="text-xs text-muted-foreground">
              {marketIntelligence?.performance_metrics.signal_count} signals
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Profit Factor</CardTitle>
            <BarChart3 className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {marketIntelligence?.performance_metrics.profit_factor.toFixed(2)}
            </div>
            <p className="text-xs text-muted-foreground">
              {((marketIntelligence?.performance_metrics.avg_confidence || 0) * 100).toFixed(1)}% avg confidence
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Main Analytics Tabs */}
      <Tabs defaultValue="insights" className="space-y-6">
        <TabsList className="grid w-full grid-cols-5">
          <TabsTrigger value="insights">AI Insights</TabsTrigger>
          <TabsTrigger value="regimes">Market Regimes</TabsTrigger>
          <TabsTrigger value="patterns">Pattern Recognition</TabsTrigger>
          <TabsTrigger value="sentiment">Sentiment Signals</TabsTrigger>
          <TabsTrigger value="multimodal">Multi-Modal Analysis</TabsTrigger>
        </TabsList>

        {/* AI Insights Tab */}
        <TabsContent value="insights" className="space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-semibold">Real-time AI Insights</h2>
            <div className="flex items-center space-x-2">
              <Button
                variant={activeInsightType === 'all' ? 'default' : 'outline'}
                size="sm"
                onClick={() => setActiveInsightType('all')}
              >
                All
              </Button>
              <Button
                variant={activeInsightType === 'pattern' ? 'default' : 'outline'}
                size="sm"
                onClick={() => setActiveInsightType('pattern')}
              >
                <Waves className="h-4 w-4 mr-1" />
                Patterns
              </Button>
              <Button
                variant={activeInsightType === 'sentiment' ? 'default' : 'outline'}
                size="sm"
                onClick={() => setActiveInsightType('sentiment')}
              >
                <MessageSquare className="h-4 w-4 mr-1" />
                Sentiment
              </Button>
              <Button
                variant={activeInsightType === 'regime' ? 'default' : 'outline'}
                size="sm"
                onClick={() => setActiveInsightType('regime')}
              >
                <Layers className="h-4 w-4 mr-1" />
                Regime
              </Button>
            </div>
          </div>

          <div className="grid gap-4">
            {filteredInsights.map((insight) => (
              <Card key={insight.id} className="border-l-4 border-l-blue-500">
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-3">
                      <Badge variant="secondary" className="capitalize">
                        {insight.type}
                      </Badge>
                      <Badge
                        variant="outline"
                        className={getConfidenceColor(insight.confidence)}
                      >
                        {(insight.confidence * 100).toFixed(1)}% confidence
                      </Badge>
                      <Badge
                        variant={insight.risk_level === 'low' ? 'default' :
                                insight.risk_level === 'medium' ? 'secondary' : 'destructive'}
                      >
                        {insight.risk_level} risk
                      </Badge>
                    </div>
                    <div className="flex items-center space-x-2">
                      <Clock className="h-4 w-4 text-gray-400" />
                      <span className="text-sm text-gray-500">
                        {new Date(insight.timestamp).toLocaleTimeString()}
                      </span>
                    </div>
                  </div>
                  <CardTitle className="text-lg">{insight.title}</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-gray-700 leading-relaxed">{insight.content}</p>
                  <div className="flex items-center justify-between mt-4">
                    <div className="flex items-center space-x-2">
                      <Lightbulb className="h-4 w-4 text-yellow-500" />
                      <span className="text-sm font-medium">Source: {insight.source.replace('_', ' ')}</span>
                    </div>
                    {insight.actionable && (
                      <Badge variant="default" className="bg-green-100 text-green-800">
                        <CheckCircle className="h-3 w-3 mr-1" />
                        Actionable
                      </Badge>
                    )}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        {/* Market Regimes Tab */}
        <TabsContent value="regimes" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>AI-Detected Market Regimes</CardTitle>
              <CardDescription>
                Real-time market regime classification using machine learning
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {marketIntelligence?.regimes.map((regime) => (
                  <div
                    key={regime.id}
                    className="border rounded-lg p-4"
                    style={{ borderColor: getRegimeColor(regime) }}
                  >
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center space-x-3">
                        <div
                          className="w-4 h-4 rounded-full"
                          style={{ backgroundColor: getRegimeColor(regime) }}
                        />
                        <h3 className="text-lg font-semibold capitalize">{regime.name} Market</h3>
                        <Badge variant="outline">
                          {(regime.confidence * 100).toFixed(1)}% confidence
                        </Badge>
                      </div>
                      <span className="text-sm text-gray-500">
                        Active for {regime.duration} minutes
                      </span>
                    </div>
                    <p className="text-gray-700 mb-3">{regime.description}</p>
                    <div className="flex flex-wrap gap-2">
                      {regime.characteristics.map((char, index) => (
                        <Badge key={index} variant="secondary">
                          {char}
                        </Badge>
                      ))}
                    </div>
                    <div className="mt-3">
                      <div className="flex items-center justify-between text-sm mb-1">
                        <span>Confidence Level</span>
                        <span>{(regime.confidence * 100).toFixed(1)}%</span>
                      </div>
                      <Progress value={regime.confidence * 100} className="h-2" />
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Pattern Recognition Tab */}
        <TabsContent value="patterns" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Multi-Modal Pattern Recognition</CardTitle>
              <CardDescription>
                Elliott Wave + LLM validated pattern detection
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {marketIntelligence?.pattern_recognition.map((pattern) => (
                  <div key={pattern.id} className="border rounded-lg p-4">
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center space-x-3">
                        <h3 className="text-lg font-semibold">{pattern.name}</h3>
                        <Badge variant="outline" className="capitalize">
                          {pattern.pattern_type.replace('_', ' ')}
                        </Badge>
                        <Badge variant="secondary">
                          {pattern.timeframe}
                        </Badge>
                      </div>
                      <Badge
                        variant="default"
                        className={getConfidenceColor(pattern.confidence)}
                      >
                        {(pattern.confidence * 100).toFixed(1)}% confidence
                      </Badge>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
                      <div>
                        <span className="text-sm font-medium">Target Price</span>
                        <div className="text-lg font-bold text-green-600">
                          {pattern.target_price.toFixed(4)}
                        </div>
                      </div>
                      <div>
                        <span className="text-sm font-medium">Stop Loss</span>
                        <div className="text-lg font-bold text-red-600">
                          {pattern.stop_loss.toFixed(4)}
                        </div>
                      </div>
                      <div>
                        <span className="text-sm font-medium">Completion</span>
                        <div className="text-lg font-bold">
                          {(pattern.completion * 100).toFixed(1)}%
                        </div>
                      </div>
                    </div>

                    <div>
                      <div className="flex items-center justify-between text-sm mb-2">
                        <span>Pattern Completion</span>
                        <span>{(pattern.completion * 100).toFixed(1)}%</span>
                      </div>
                      <Progress value={pattern.completion * 100} className="h-2 mb-4" />
                    </div>

                    <div>
                      <span className="text-sm font-medium mb-2 block">Validation Status</span>
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                        {Object.entries(pattern.validation).map(([key, value]) => (
                          <div key={key} className="flex items-center space-x-2">
                            {value ? (
                              <CheckCircle className="h-4 w-4 text-green-600" />
                            ) : (
                              <AlertTriangle className="h-4 w-4 text-red-600" />
                            )}
                            <span className="text-sm capitalize">
                              {key.replace('_', ' ')}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Sentiment Signals Tab */}
        <TabsContent value="sentiment" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Real-time Sentiment-Driven Signals</CardTitle>
              <CardDescription>
                LLM-powered sentiment analysis with actionable trading signals
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {marketIntelligence?.sentiment_signals.map((signal) => (
                  <div key={signal.id} className="border rounded-lg p-4">
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center space-x-3">
                        <h3 className="text-lg font-semibold">{signal.symbol}</h3>
                        <Badge
                          className={`font-semibold uppercase ${getSignalColor(signal.signal)}`}
                        >
                          {signal.signal}
                        </Badge>
                        <Badge variant="outline">
                          {(signal.confidence * 100).toFixed(1)}% confidence
                        </Badge>
                      </div>
                      <span className="text-sm text-gray-500">
                        Expires: {new Date(signal.expiry).toLocaleTimeString()}
                      </span>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
                      <div>
                        <span className="text-sm font-medium">Overall Sentiment</span>
                        <div className="text-lg font-bold">
                          {(signal.sentiment_score * 100).toFixed(1)}%
                        </div>
                        <Progress value={signal.sentiment_score * 100} className="h-2 mt-1" />
                      </div>
                      <div>
                        <span className="text-sm font-medium">News Impact</span>
                        <div className="text-lg font-bold">
                          {(signal.news_impact * 100).toFixed(1)}%
                        </div>
                        <Progress value={signal.news_impact * 100} className="h-2 mt-1" />
                      </div>
                      <div>
                        <span className="text-sm font-medium">Social Sentiment</span>
                        <div className="text-lg font-bold">
                          {(signal.social_sentiment * 100).toFixed(1)}%
                        </div>
                        <Progress value={signal.social_sentiment * 100} className="h-2 mt-1" />
                      </div>
                    </div>

                    <div>
                      <span className="text-sm font-medium mb-2 block">LLM Reasoning</span>
                      <p className="text-gray-700 leading-relaxed bg-gray-50 p-3 rounded">
                        {signal.llm_reasoning}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Multi-Modal Analysis Tab */}
        <TabsContent value="multimodal" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Multi-Modal AI Analysis</CardTitle>
              <CardDescription>
                Combined Elliott Wave, Sentiment, and Pattern Recognition Analysis
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-6">
                {/* Analysis Confidence Radar Chart */}
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <RadarChart data={[
                      {
                        subject: 'Elliott Wave',
                        confidence: 94,
                        fullMark: 100
                      },
                      {
                        subject: 'Sentiment',
                        confidence: 89,
                        fullMark: 100
                      },
                      {
                        subject: 'Pattern Recognition',
                        confidence: 87,
                        fullMark: 100
                      },
                      {
                        subject: 'Market Regime',
                        confidence: 91,
                        fullMark: 100
                      },
                      {
                        subject: 'LLM Validation',
                        confidence: 88,
                        fullMark: 100
                      }
                    ]}>
                      <PolarGrid />
                      <PolarAngleAxis dataKey="subject" />
                      <PolarRadiusAxis angle={90} domain={[0, 100]} />
                      <Radar
                        name="Confidence"
                        dataKey="confidence"
                        stroke="#3b82f6"
                        fill="#3b82f6"
                        fillOpacity={0.2}
                      />
                    </RadarChart>
                  </ResponsiveContainer>
                </div>

                {/* Combined Analysis Summary */}
                <Alert>
                  <Brain className="h-4 w-4" />
                  <AlertTitle>AI Consensus Analysis</AlertTitle>
                  <AlertDescription>
                    Multi-modal analysis shows strong agreement across all AI systems (91% consensus).
                    Elliott Wave patterns align with sentiment trends, and LLM validation confirms
                    bullish bias with high confidence. Recommended action: Monitor for entry opportunity.
                  </AlertDescription>
                </Alert>

                {/* Correlation Matrix */}
                <div>
                  <h3 className="text-lg font-semibold mb-3">Signal Correlation Matrix</h3>
                  <div className="grid grid-cols-3 gap-4">
                    <Card className="text-center">
                      <CardContent className="pt-4">
                        <div className="text-2xl font-bold text-green-600">0.89</div>
                        <p className="text-sm text-gray-600">Wave ↔ Sentiment</p>
                      </CardContent>
                    </Card>
                    <Card className="text-center">
                      <CardContent className="pt-4">
                        <div className="text-2xl font-bold text-green-600">0.92</div>
                        <p className="text-sm text-gray-600">Pattern ↔ LLM</p>
                      </CardContent>
                    </Card>
                    <Card className="text-center">
                      <CardContent className="pt-4">
                        <div className="text-2xl font-bold text-green-600">0.85</div>
                        <p className="text-sm text-gray-600">Regime ↔ Technical</p>
                      </CardContent>
                    </Card>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
