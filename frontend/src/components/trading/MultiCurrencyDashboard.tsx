/**
 * Multi-Currency Trading Dashboard Component
 *
 * Provides comprehensive multi-currency trading analysis including:
 * - Real-time currency pair monitoring
 * - Session-aware trading optimization
 * - Cross-currency arbitrage opportunities
 * - Economic calendar integration
 * - Elliott Wave pattern analysis across currencies
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  AlertTriangle,
  TrendingUp,
  TrendingDown,
  Activity,
  Globe,
  Clock,
  DollarSign,
  Target,
  Zap,
  BarChart3,
  PieChart,
  LineChart,
  Calendar,
  Alert,
  CheckCircle,
  XCircle,
  RefreshCw
} from 'lucide-react';
import { format } from 'date-fns';

// Types for multi-currency dashboard
interface CurrencyPair {
  symbol: string;
  baseCode: string;
  quoteCode: string;
  bid: number;
  ask: number;
  spread: number;
  change24h: number;
  volume24h: number;
  lastUpdate: string;
  sessionActivity: 'high' | 'medium' | 'low';
  volatility: number;
}

interface TradingSession {
  name: string;
  region: string;
  isActive: boolean;
  intensity: number;
  openTime: string;
  closeTime: string;
  preferredPairs: string[];
}

interface ArbitrageOpportunity {
  id: string;
  type: 'triangular' | 'statistical' | 'carry_trade';
  currencyPath: string[];
  expectedProfit: number;
  riskLevel: 'low' | 'medium' | 'high';
  confidence: number;
  timeToExpiry: number;
  requiredCapital: number;
}

interface EconomicEvent {
  id: string;
  title: string;
  currency: string;
  impact: 'low' | 'medium' | 'high' | 'critical';
  datetime: string;
  actual?: number;
  forecast?: number;
  previous?: number;
  description: string;
}

interface WavePattern {
  id: string;
  pair: string;
  type: string;
  strength: number;
  timeframe: string;
  status: 'active' | 'completed' | 'forming';
  confidence: number;
  targets: number[];
  sessionOptimized: boolean;
}

interface PortfolioPosition {
  pair: string;
  direction: 'long' | 'short';
  size: number;
  entryPrice: number;
  currentPrice: number;
  unrealizedPnL: number;
  riskPercent: number;
  correlationRisk: number;
}

interface MultiCurrencyState {
  currencyPairs: CurrencyPair[];
  tradingSessions: TradingSession[];
  arbitrageOpportunities: ArbitrageOpportunity[];
  economicEvents: EconomicEvent[];
  wavePatterns: WavePattern[];
  portfolioPositions: PortfolioPosition[];
  correlationMatrix: Record<string, Record<string, number>>;
  sessionAnalysis: {
    currentSession: string;
    nextSession: string;
    timeToNext: number;
    optimizedPairs: string[];
  };
}

const CURRENCY_PAIRS = [
  'EURUSD', 'GBPUSD', 'USDJPY', 'USDCHF',
  'AUDUSD', 'USDCAD', 'NZDUSD', 'EURGBP',
  'EURJPY', 'GBPJPY', 'EURCHF', 'GBPCHF'
];

const TRADING_SESSIONS = [
  { name: 'Tokyo', region: 'Asia-Pacific', timezone: 'Asia/Tokyo' },
  { name: 'London', region: 'Europe', timezone: 'Europe/London' },
  { name: 'New York', region: 'Americas', timezone: 'America/New_York' },
  { name: 'Sydney', region: 'Asia-Pacific', timezone: 'Australia/Sydney' }
];

export default function MultiCurrencyDashboard() {
  const [state, setState] = useState<MultiCurrencyState>({
    currencyPairs: [],
    tradingSessions: [],
    arbitrageOpportunities: [],
    economicEvents: [],
    wavePatterns: [],
    portfolioPositions: [],
    correlationMatrix: {},
    sessionAnalysis: {
      currentSession: 'London',
      nextSession: 'New York',
      timeToNext: 45,
      optimizedPairs: ['EURUSD', 'GBPUSD']
    }
  });

  const [selectedPair, setSelectedPair] = useState<string>('EURUSD');
  const [selectedTimeframe, setSelectedTimeframe] = useState<string>('1h');
  const [refreshing, setRefreshing] = useState(false);
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date());

  // Initialize dashboard data
  useEffect(() => {
    loadDashboardData();
    const interval = setInterval(loadDashboardData, 30000); // Update every 30 seconds
    return () => clearInterval(interval);
  }, []);

  const loadDashboardData = useCallback(async () => {
    setRefreshing(true);
    try {
      // Simulate API calls to load multi-currency data
      const [
        currencyData,
        sessionData,
        arbitrageData,
        economicData,
        waveData,
        portfolioData
      ] = await Promise.all([
        fetchCurrencyPairs(),
        fetchTradingSessions(),
        fetchArbitrageOpportunities(),
        fetchEconomicEvents(),
        fetchWavePatterns(),
        fetchPortfolioPositions()
      ]);

      setState(prev => ({
        ...prev,
        currencyPairs: currencyData,
        tradingSessions: sessionData,
        arbitrageOpportunities: arbitrageData,
        economicEvents: economicData,
        wavePatterns: waveData,
        portfolioPositions: portfolioData
      }));

      setLastUpdate(new Date());
    } catch (error) {
      console.error('Error loading dashboard data:', error);
    } finally {
      setRefreshing(false);
    }
  }, []);

  // Mock data fetching functions
  const fetchCurrencyPairs = async (): Promise<CurrencyPair[]> => {
    return CURRENCY_PAIRS.map(pair => ({
      symbol: pair,
      baseCode: pair.slice(0, 3),
      quoteCode: pair.slice(3, 6),
      bid: 1.0800 + Math.random() * 0.1,
      ask: 1.0805 + Math.random() * 0.1,
      spread: 0.5 + Math.random() * 2,
      change24h: (Math.random() - 0.5) * 2,
      volume24h: Math.random() * 1000000,
      lastUpdate: new Date().toISOString(),
      sessionActivity: ['high', 'medium', 'low'][Math.floor(Math.random() * 3)] as 'high' | 'medium' | 'low',
      volatility: Math.random() * 100
    }));
  };

  const fetchTradingSessions = async (): Promise<TradingSession[]> => {
    return TRADING_SESSIONS.map(session => ({
      name: session.name,
      region: session.region,
      isActive: Math.random() > 0.5,
      intensity: Math.random() * 100,
      openTime: '09:00',
      closeTime: '17:00',
      preferredPairs: CURRENCY_PAIRS.slice(0, 3)
    }));
  };

  const fetchArbitrageOpportunities = async (): Promise<ArbitrageOpportunity[]> => {
    return [
      {
        id: '1',
        type: 'triangular',
        currencyPath: ['EUR', 'GBP', 'USD'],
        expectedProfit: 0.0023,
        riskLevel: 'low',
        confidence: 0.85,
        timeToExpiry: 300,
        requiredCapital: 100000
      },
      {
        id: '2',
        type: 'statistical',
        currencyPath: ['USD', 'JPY'],
        expectedProfit: 0.0045,
        riskLevel: 'medium',
        confidence: 0.72,
        timeToExpiry: 180,
        requiredCapital: 50000
      }
    ];
  };

  const fetchEconomicEvents = async (): Promise<EconomicEvent[]> => {
    return [
      {
        id: '1',
        title: 'Non-Farm Payrolls',
        currency: 'USD',
        impact: 'high',
        datetime: new Date().toISOString(),
        forecast: 200000,
        previous: 180000,
        description: 'Monthly employment data'
      },
      {
        id: '2',
        title: 'ECB Interest Rate Decision',
        currency: 'EUR',
        impact: 'critical',
        datetime: new Date(Date.now() + 3600000).toISOString(),
        forecast: 4.5,
        previous: 4.5,
        description: 'European Central Bank monetary policy decision'
      }
    ];
  };

  const fetchWavePatterns = async (): Promise<WavePattern[]> => {
    return [
      {
        id: '1',
        pair: 'EURUSD',
        type: 'impulse',
        strength: 0.85,
        timeframe: '1h',
        status: 'active',
        confidence: 0.78,
        targets: [1.0850, 1.0900],
        sessionOptimized: true
      },
      {
        id: '2',
        pair: 'GBPUSD',
        type: 'corrective',
        strength: 0.72,
        timeframe: '4h',
        status: 'forming',
        confidence: 0.65,
        targets: [1.2650, 1.2700],
        sessionOptimized: false
      }
    ];
  };

  const fetchPortfolioPositions = async (): Promise<PortfolioPosition[]> => {
    return [
      {
        pair: 'EURUSD',
        direction: 'long',
        size: 100000,
        entryPrice: 1.0780,
        currentPrice: 1.0820,
        unrealizedPnL: 400,
        riskPercent: 2.0,
        correlationRisk: 0.15
      },
      {
        pair: 'GBPUSD',
        direction: 'short',
        size: 50000,
        entryPrice: 1.2720,
        currentPrice: 1.2680,
        unrealizedPnL: 200,
        riskPercent: 1.5,
        correlationRisk: 0.25
      }
    ];
  };

  // Computed values
  const totalUnrealizedPnL = useMemo(() => {
    return state.portfolioPositions.reduce((sum, pos) => sum + pos.unrealizedPnL, 0);
  }, [state.portfolioPositions]);

  const totalRiskPercent = useMemo(() => {
    return state.portfolioPositions.reduce((sum, pos) => sum + pos.riskPercent, 0);
  }, [state.portfolioPositions]);

  const activeSessions = useMemo(() => {
    return state.tradingSessions.filter(session => session.isActive);
  }, [state.tradingSessions]);

  const highImpactEvents = useMemo(() => {
    return state.economicEvents.filter(event =>
      ['high', 'critical'].includes(event.impact)
    );
  }, [state.economicEvents]);

  // Component render functions
  const renderCurrencyPairCard = (pair: CurrencyPair) => (
    <Card key={pair.symbol} className="hover:shadow-md transition-shadow">
      <CardContent className="p-4">
        <div className="flex justify-between items-start mb-2">
          <div>
            <h3 className="font-semibold text-lg">{pair.symbol}</h3>
            <p className="text-sm text-gray-600">{pair.baseCode}/{pair.quoteCode}</p>
          </div>
          <Badge
            variant={pair.sessionActivity === 'high' ? 'default' :
                    pair.sessionActivity === 'medium' ? 'secondary' : 'outline'}
          >
            {pair.sessionActivity}
          </Badge>
        </div>

        <div className="grid grid-cols-2 gap-2 text-sm">
          <div>
            <span className="text-gray-600">Bid:</span>
            <span className="font-mono ml-1">{pair.bid.toFixed(5)}</span>
          </div>
          <div>
            <span className="text-gray-600">Ask:</span>
            <span className="font-mono ml-1">{pair.ask.toFixed(5)}</span>
          </div>
          <div>
            <span className="text-gray-600">Spread:</span>
            <span className="font-mono ml-1">{pair.spread.toFixed(1)} pips</span>
          </div>
          <div className="flex items-center">
            <span className="text-gray-600">24h:</span>
            <span className={`font-mono ml-1 flex items-center ${
              pair.change24h >= 0 ? 'text-green-600' : 'text-red-600'
            }`}>
              {pair.change24h >= 0 ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
              {Math.abs(pair.change24h).toFixed(2)}%
            </span>
          </div>
        </div>

        <div className="mt-3 pt-2 border-t">
          <div className="flex justify-between text-xs text-gray-500">
            <span>Vol: {(pair.volume24h / 1000000).toFixed(1)}M</span>
            <span>Volatility: {pair.volatility.toFixed(1)}%</span>
          </div>
        </div>
      </CardContent>
    </Card>
  );

  const renderTradingSessionCard = (session: TradingSession) => (
    <Card key={session.name} className={`transition-all ${
      session.isActive ? 'ring-2 ring-green-500 bg-green-50' : ''
    }`}>
      <CardContent className="p-4">
        <div className="flex justify-between items-start mb-2">
          <div>
            <h3 className="font-semibold">{session.name}</h3>
            <p className="text-sm text-gray-600">{session.region}</p>
          </div>
          <div className="flex items-center">
            <Activity
              size={16}
              className={session.isActive ? 'text-green-500' : 'text-gray-400'}
            />
            <span className="ml-1 text-sm">
              {session.isActive ? 'Active' : 'Closed'}
            </span>
          </div>
        </div>

        <div className="mb-3">
          <div className="flex justify-between text-sm mb-1">
            <span>Intensity</span>
            <span>{session.intensity.toFixed(0)}%</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div
              className="bg-blue-600 h-2 rounded-full"
              style={{ width: `${session.intensity}%` }}
            ></div>
          </div>
        </div>

        <div className="text-xs text-gray-500">
          <div className="flex justify-between">
            <span>Open: {session.openTime}</span>
            <span>Close: {session.closeTime}</span>
          </div>
          <div className="mt-1">
            Preferred: {session.preferredPairs.join(', ')}
          </div>
        </div>
      </CardContent>
    </Card>
  );

  const renderArbitrageOpportunity = (opportunity: ArbitrageOpportunity) => (
    <Card key={opportunity.id} className="hover:shadow-md transition-shadow">
      <CardContent className="p-4">
        <div className="flex justify-between items-start mb-2">
          <div>
            <h3 className="font-semibold capitalize">{opportunity.type}</h3>
            <p className="text-sm text-gray-600">
              {opportunity.currencyPath.join(' → ')}
            </p>
          </div>
          <Badge
            variant={opportunity.riskLevel === 'low' ? 'default' :
                    opportunity.riskLevel === 'medium' ? 'secondary' : 'destructive'}
          >
            {opportunity.riskLevel} risk
          </Badge>
        </div>

        <div className="grid grid-cols-2 gap-2 text-sm mb-3">
          <div>
            <span className="text-gray-600">Profit:</span>
            <span className="font-mono ml-1 text-green-600">
              {(opportunity.expectedProfit * 100).toFixed(3)}%
            </span>
          </div>
          <div>
            <span className="text-gray-600">Confidence:</span>
            <span className="font-mono ml-1">{(opportunity.confidence * 100).toFixed(0)}%</span>
          </div>
          <div>
            <span className="text-gray-600">Capital:</span>
            <span className="font-mono ml-1">${(opportunity.requiredCapital / 1000).toFixed(0)}k</span>
          </div>
          <div>
            <span className="text-gray-600">Expiry:</span>
            <span className="font-mono ml-1">{opportunity.timeToExpiry}s</span>
          </div>
        </div>

        <Button size="sm" className="w-full">
          <Target className="mr-2" size={14} />
          Execute
        </Button>
      </CardContent>
    </Card>
  );

  const renderEconomicEvent = (event: EconomicEvent) => (
    <div key={event.id} className={`p-3 border-l-4 ${
      event.impact === 'critical' ? 'border-red-500 bg-red-50' :
      event.impact === 'high' ? 'border-orange-500 bg-orange-50' :
      event.impact === 'medium' ? 'border-yellow-500 bg-yellow-50' :
      'border-gray-300 bg-gray-50'
    }`}>
      <div className="flex justify-between items-start mb-1">
        <h4 className="font-semibold text-sm">{event.title}</h4>
        <Badge variant="outline" className="text-xs">
          {event.currency}
        </Badge>
      </div>

      <p className="text-xs text-gray-600 mb-2">{event.description}</p>

      <div className="flex justify-between text-xs">
        <span>{format(new Date(event.datetime), 'HH:mm')}</span>
        {event.forecast && (
          <span>
            Forecast: {event.forecast}
            {event.previous && ` (Prev: ${event.previous})`}
          </span>
        )}
      </div>
    </div>
  );

  const renderWavePattern = (pattern: WavePattern) => (
    <div key={pattern.id} className="p-3 border rounded-lg hover:bg-gray-50">
      <div className="flex justify-between items-start mb-2">
        <div>
          <h4 className="font-semibold text-sm">{pattern.pair}</h4>
          <p className="text-xs text-gray-600 capitalize">{pattern.type} wave</p>
        </div>
        <div className="text-right">
          <Badge
            variant={pattern.status === 'active' ? 'default' :
                    pattern.status === 'forming' ? 'secondary' : 'outline'}
            className="text-xs"
          >
            {pattern.status}
          </Badge>
          {pattern.sessionOptimized && (
            <div className="mt-1">
              <Badge variant="outline" className="text-xs">
                <Zap size={10} className="mr-1" />
                Optimized
              </Badge>
            </div>
          )}
        </div>
      </div>

      <div className="grid grid-cols-3 gap-2 text-xs">
        <div>
          <span className="text-gray-600">Strength:</span>
          <span className="font-mono ml-1">{(pattern.strength * 100).toFixed(0)}%</span>
        </div>
        <div>
          <span className="text-gray-600">Confidence:</span>
          <span className="font-mono ml-1">{(pattern.confidence * 100).toFixed(0)}%</span>
        </div>
        <div>
          <span className="text-gray-600">TF:</span>
          <span className="font-mono ml-1">{pattern.timeframe}</span>
        </div>
      </div>

      {pattern.targets.length > 0 && (
        <div className="mt-2 text-xs">
          <span className="text-gray-600">Targets:</span>
          <span className="font-mono ml-1">{pattern.targets.join(', ')}</span>
        </div>
      )}
    </div>
  );

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">Multi-Currency Dashboard</h1>
          <p className="text-gray-600">
            Real-time analysis across {CURRENCY_PAIRS.length} currency pairs
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <div className="text-sm text-gray-500">
            Last update: {format(lastUpdate, 'HH:mm:ss')}
          </div>
          <Button
            onClick={loadDashboardData}
            disabled={refreshing}
            size="sm"
          >
            <RefreshCw className={`mr-2 ${refreshing ? 'animate-spin' : ''}`} size={14} />
            Refresh
          </Button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Total P&L</p>
                <p className={`text-2xl font-bold ${
                  totalUnrealizedPnL >= 0 ? 'text-green-600' : 'text-red-600'
                }`}>
                  ${totalUnrealizedPnL.toFixed(0)}
                </p>
              </div>
              <DollarSign className="text-gray-400" size={24} />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Portfolio Risk</p>
                <p className="text-2xl font-bold">{totalRiskPercent.toFixed(1)}%</p>
              </div>
              <AlertTriangle className="text-gray-400" size={24} />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Active Sessions</p>
                <p className="text-2xl font-bold">{activeSessions.length}</p>
              </div>
              <Globe className="text-gray-400" size={24} />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">High Impact Events</p>
                <p className="text-2xl font-bold">{highImpactEvents.length}</p>
              </div>
              <Calendar className="text-gray-400" size={24} />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Main Dashboard Tabs */}
      <Tabs defaultValue="overview" className="space-y-4">
        <TabsList className="grid w-full grid-cols-6">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="sessions">Sessions</TabsTrigger>
          <TabsTrigger value="arbitrage">Arbitrage</TabsTrigger>
          <TabsTrigger value="calendar">Calendar</TabsTrigger>
          <TabsTrigger value="waves">Wave Analysis</TabsTrigger>
          <TabsTrigger value="portfolio">Portfolio</TabsTrigger>
        </TabsList>

        {/* Overview Tab */}
        <TabsContent value="overview" className="space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Currency Pairs */}
            <div className="lg:col-span-2">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center">
                    <BarChart3 className="mr-2" size={20} />
                    Currency Pairs
                  </CardTitle>
                  <CardDescription>
                    Real-time rates and session activity
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {state.currencyPairs.slice(0, 6).map(renderCurrencyPairCard)}
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Session Analysis */}
            <div>
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center">
                    <Clock className="mr-2" size={20} />
                    Current Session
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="text-center">
                    <h3 className="text-2xl font-bold text-blue-600">
                      {state.sessionAnalysis.currentSession}
                    </h3>
                    <p className="text-sm text-gray-600">Active Session</p>
                  </div>

                  <div className="space-y-2">
                    <div className="flex justify-between text-sm">
                      <span>Next Session:</span>
                      <span className="font-semibold">{state.sessionAnalysis.nextSession}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span>Time to Next:</span>
                      <span className="font-mono">{state.sessionAnalysis.timeToNext}m</span>
                    </div>
                  </div>

                  <div>
                    <p className="text-sm text-gray-600 mb-2">Optimized Pairs:</p>
                    <div className="flex flex-wrap gap-1">
                      {state.sessionAnalysis.optimizedPairs.map(pair => (
                        <Badge key={pair} variant="secondary" className="text-xs">
                          {pair}
                        </Badge>
                      ))}
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
        </TabsContent>

        {/* Sessions Tab */}
        <TabsContent value="sessions" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Global Trading Sessions</CardTitle>
              <CardDescription>
                Monitor activity levels across major trading centers
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                {state.tradingSessions.map(renderTradingSessionCard)}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Arbitrage Tab */}
        <TabsContent value="arbitrage" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center">
                <Target className="mr-2" size={20} />
                Arbitrage Opportunities
              </CardTitle>
              <CardDescription>
                Cross-currency arbitrage detection and analysis
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {state.arbitrageOpportunities.map(renderArbitrageOpportunity)}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Economic Calendar Tab */}
        <TabsContent value="calendar" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center">
                <Calendar className="mr-2" size={20} />
                Economic Calendar
              </CardTitle>
              <CardDescription>
                Upcoming high-impact economic events
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {state.economicEvents.map(renderEconomicEvent)}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Wave Analysis Tab */}
        <TabsContent value="waves" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center">
                <LineChart className="mr-2" size={20} />
                Elliott Wave Patterns
              </CardTitle>
              <CardDescription>
                Multi-currency wave analysis with session optimization
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {state.wavePatterns.map(renderWavePattern)}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Portfolio Tab */}
        <TabsContent value="portfolio" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center">
                <PieChart className="mr-2" size={20} />
                Portfolio Positions
              </CardTitle>
              <CardDescription>
                Multi-currency position management and correlation analysis
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b">
                      <th className="text-left p-2">Pair</th>
                      <th className="text-left p-2">Direction</th>
                      <th className="text-left p-2">Size</th>
                      <th className="text-left p-2">Entry</th>
                      <th className="text-left p-2">Current</th>
                      <th className="text-left p-2">P&L</th>
                      <th className="text-left p-2">Risk %</th>
                      <th className="text-left p-2">Corr Risk</th>
                    </tr>
                  </thead>
                  <tbody>
                    {state.portfolioPositions.map((position, index) => (
                      <tr key={index} className="border-b hover:bg-gray-50">
                        <td className="p-2 font-semibold">{position.pair}</td>
                        <td className="p-2">
                          <Badge
                            variant={position.direction === 'long' ? 'default' : 'secondary'}
                            className="text-xs"
                          >
                            {position.direction}
                          </Badge>
                        </td>
                        <td className="p-2 font-mono">{position.size.toLocaleString()}</td>
                        <td className="p-2 font-mono">{position.entryPrice.toFixed(5)}</td>
                        <td className="p-2 font-mono">{position.currentPrice.toFixed(5)}</td>
                        <td className={`p-2 font-mono ${
                          position.unrealizedPnL >= 0 ? 'text-green-600' : 'text-red-600'
                        }`}>
                          ${position.unrealizedPnL.toFixed(0)}
                        </td>
                        <td className="p-2 font-mono">{position.riskPercent.toFixed(1)}%</td>
                        <td className="p-2 font-mono">{(position.correlationRisk * 100).toFixed(0)}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
