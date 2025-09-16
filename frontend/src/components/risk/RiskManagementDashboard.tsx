/**
 * Phase 7 - Risk Management Dashboard
 * 
 * Comprehensive risk monitoring and management interface that integrates
 * with Phase 6 risk limit enforcement and compliance systems.
 */

'use client';

import React, { useState, useEffect, useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { 
  LineChart, 
  Line, 
  AreaChart,
  Area,
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  ReferenceLine
} from 'recharts';
import {
  ShieldExclamationIcon,
  ExclamationTriangleIcon,
  ChartPieIcon,
  ScaleIcon,
  BoltIcon,
  ClockIcon,
  AdjustmentsVerticalIcon,
  SignalIcon,
  TrendingUpIcon,
  TrendingDownIcon,
  EyeIcon,
  Cog6ToothIcon
} from '@heroicons/react/24/outline';
import { format, subHours, subDays } from 'date-fns';
import { motion, AnimatePresence } from 'framer-motion';

// Risk Management Types
interface RiskLimit {
  id: string;
  name: string;
  type: 'position_size' | 'daily_loss' | 'concentration' | 'leverage' | 'drawdown' | 'var';
  currentValue: number;
  limitValue: number;
  utilizationPercent: number;
  status: 'normal' | 'warning' | 'breach';
  lastUpdated: string;
}

interface PortfolioExposure {
  symbol: string;
  exposure: number;
  percentage: number;
  risk: 'low' | 'medium' | 'high';
}

interface RiskMetrics {
  portfolioVar: number; // Value at Risk (daily, 95%)
  expectedShortfall: number; // Conditional VaR
  maxDrawdown: number;
  currentDrawdown: number;
  sharpeRatio: number;
  sortinoRatio: number;
  betaToMarket: number;
  correlationToMarket: number;
  volatility: number; // Annualized
}

interface RiskEvent {
  id: string;
  type: 'limit_breach' | 'concentration_risk' | 'var_exceedance' | 'correlation_spike';
  severity: 'low' | 'medium' | 'high' | 'critical';
  title: string;
  description: string;
  timestamp: string;
  status: 'active' | 'acknowledged' | 'resolved';
  impact: number;
}

interface StressTestScenario {
  name: string;
  description: string;
  marketShock: number; // Percentage change
  portfolioImpact: number; // Expected P&L impact
  probability: number; // Estimated probability
  severity: 'low' | 'medium' | 'high' | 'extreme';
}

export default function RiskManagementDashboard() {
  const [selectedTimeframe, setSelectedTimeframe] = useState<'1d' | '1w' | '1m' | '3m'>('1d');
  const [riskLimits, setRiskLimits] = useState<RiskLimit[]>([]);
  const [portfolioExposure, setPortfolioExposure] = useState<PortfolioExposure[]>([]);
  const [riskMetrics, setRiskMetrics] = useState<RiskMetrics | null>(null);
  const [riskEvents, setRiskEvents] = useState<RiskEvent[]>([]);
  const [stressTests, setStressTests] = useState<StressTestScenario[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  // Mock data generation
  useEffect(() => {
    const mockRiskLimits: RiskLimit[] = [
      {
        id: '1',
        name: 'Daily Position Limit',
        type: 'position_size',
        currentValue: 8500000,
        limitValue: 10000000,
        utilizationPercent: 85,
        status: 'warning',
        lastUpdated: new Date(Date.now() - 300000).toISOString()
      },
      {
        id: '2',
        name: 'Daily Loss Limit',
        type: 'daily_loss',
        currentValue: 1200,
        limitValue: 5000,
        utilizationPercent: 24,
        status: 'normal',
        lastUpdated: new Date(Date.now() - 600000).toISOString()
      },
      {
        id: '3',
        name: 'Single Currency Concentration',
        type: 'concentration',
        currentValue: 0.72,
        limitValue: 0.75,
        utilizationPercent: 96,
        status: 'breach',
        lastUpdated: new Date(Date.now() - 180000).toISOString()
      },
      {
        id: '4',
        name: 'Maximum Leverage',
        type: 'leverage',
        currentValue: 18.5,
        limitValue: 20,
        utilizationPercent: 92.5,
        status: 'warning',
        lastUpdated: new Date(Date.now() - 120000).toISOString()
      },
      {
        id: '5',
        name: 'Maximum Drawdown',
        type: 'drawdown',
        currentValue: 0.085,
        limitValue: 0.15,
        utilizationPercent: 56.7,
        status: 'normal',
        lastUpdated: new Date(Date.now() - 900000).toISOString()
      },
      {
        id: '6',
        name: 'Daily VaR (95%)',
        type: 'var',
        currentValue: 2850,
        limitValue: 4000,
        utilizationPercent: 71.25,
        status: 'normal',
        lastUpdated: new Date(Date.now() - 450000).toISOString()
      }
    ];

    const mockPortfolioExposure: PortfolioExposure[] = [
      { symbol: 'EUR/USD', exposure: 4200000, percentage: 35.2, risk: 'medium' },
      { symbol: 'GBP/USD', exposure: 2800000, percentage: 23.5, risk: 'high' },
      { symbol: 'USD/JPY', exposure: 1950000, percentage: 16.4, risk: 'low' },
      { symbol: 'AUD/USD', exposure: 1500000, percentage: 12.6, risk: 'medium' },
      { symbol: 'USD/CHF', exposure: 980000, percentage: 8.2, risk: 'low' },
      { symbol: 'NZD/USD', exposure: 495000, percentage: 4.1, risk: 'medium' }
    ];

    const mockRiskMetrics: RiskMetrics = {
      portfolioVar: 2847.50,
      expectedShortfall: 4235.80,
      maxDrawdown: 0.124,
      currentDrawdown: 0.085,
      sharpeRatio: 1.84,
      sortinoRatio: 2.67,
      betaToMarket: 0.73,
      correlationToMarket: 0.68,
      volatility: 0.156
    };

    const mockRiskEvents: RiskEvent[] = [
      {
        id: '1',
        type: 'limit_breach',
        severity: 'critical',
        title: 'Concentration Limit Breach',
        description: 'EUR exposure exceeded maximum concentration limit of 75%',
        timestamp: new Date(Date.now() - 900000).toISOString(),
        status: 'active',
        impact: -15000
      },
      {
        id: '2',
        type: 'var_exceedance',
        severity: 'medium',
        title: 'VaR Exceedance',
        description: 'Portfolio VaR exceeded daily limit by 12.5%',
        timestamp: new Date(Date.now() - 1800000).toISOString(),
        status: 'acknowledged',
        impact: -8500
      },
      {
        id: '3',
        type: 'correlation_spike',
        severity: 'high',
        title: 'High Correlation Risk',
        description: 'Correlation between EUR/USD and GBP/USD spiked to 0.95',
        timestamp: new Date(Date.now() - 3600000).toISOString(),
        status: 'resolved',
        impact: -5200
      }
    ];

    const mockStressTests: StressTestScenario[] = [
      {
        name: 'Flash Crash',
        description: 'Sudden 5% market drop across all major pairs',
        marketShock: -5,
        portfolioImpact: -125000,
        probability: 0.05,
        severity: 'extreme'
      },
      {
        name: 'Central Bank Intervention',
        description: 'Coordinated central bank intervention causing 2% volatility spike',
        marketShock: -2,
        portfolioImpact: -45000,
        probability: 0.15,
        severity: 'high'
      },
      {
        name: 'Economic Data Surprise',
        description: 'Major economic announcement causing 1.5% market movement',
        marketShock: 1.5,
        portfolioImpact: 38000,
        probability: 0.25,
        severity: 'medium'
      },
      {
        name: 'Geopolitical Event',
        description: 'Political instability causing flight to safe haven currencies',
        marketShock: -3,
        portfolioImpact: -78000,
        probability: 0.12,
        severity: 'high'
      }
    ];

    setTimeout(() => {
      setRiskLimits(mockRiskLimits);
      setPortfolioExposure(mockPortfolioExposure);
      setRiskMetrics(mockRiskMetrics);
      setRiskEvents(mockRiskEvents);
      setStressTests(mockStressTests);
      setIsLoading(false);
    }, 1000);
  }, [selectedTimeframe]);

  // Helper functions
  const getRiskStatusColor = (status: string) => {
    switch (status) {
      case 'normal': return 'text-green-600 bg-green-50 border-green-200';
      case 'warning': return 'text-yellow-600 bg-yellow-50 border-yellow-200';
      case 'breach': return 'text-red-600 bg-red-50 border-red-200';
      default: return 'text-gray-600 bg-gray-50 border-gray-200';
    }
  };

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'low': return 'text-blue-600 bg-blue-50';
      case 'medium': return 'text-yellow-600 bg-yellow-50';
      case 'high': return 'text-orange-600 bg-orange-50';
      case 'critical': case 'extreme': return 'text-red-600 bg-red-50';
      default: return 'text-gray-600 bg-gray-50';
    }
  };

  const getUtilizationBarColor = (percent: number) => {
    if (percent >= 90) return 'bg-red-500';
    if (percent >= 75) return 'bg-yellow-500';
    return 'bg-green-500';
  };

  // Radar chart data for risk metrics
  const radarData = useMemo(() => {
    if (!riskMetrics) return [];
    return [
      { subject: 'Sharpe Ratio', A: Math.min(riskMetrics.sharpeRatio * 20, 100), fullMark: 100 },
      { subject: 'Sortino Ratio', A: Math.min(riskMetrics.sortinoRatio * 15, 100), fullMark: 100 },
      { subject: 'Beta', A: (1 - Math.abs(riskMetrics.betaToMarket - 1)) * 100, fullMark: 100 },
      { subject: 'Volatility', A: Math.max(100 - riskMetrics.volatility * 300, 0), fullMark: 100 },
      { subject: 'Drawdown', A: Math.max(100 - riskMetrics.currentDrawdown * 500, 0), fullMark: 100 },
      { subject: 'Correlation', A: Math.max(100 - Math.abs(riskMetrics.correlationToMarket) * 100, 0), fullMark: 100 }
    ];
  }, [riskMetrics]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-blue-500"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Risk Management</h1>
          <p className="text-sm text-gray-600">
            Portfolio risk monitoring and limit enforcement
          </p>
        </div>
        <div className="flex items-center space-x-2 mt-4 sm:mt-0">
          <div className="flex rounded-md overflow-hidden border">
            {(['1d', '1w', '1m', '3m'] as const).map((tf) => (
              <button
                key={tf}
                onClick={() => setSelectedTimeframe(tf)}
                className={`px-3 py-1 text-xs font-medium ${
                  selectedTimeframe === tf 
                    ? 'bg-blue-500 text-white' 
                    : 'bg-white text-gray-700 hover:bg-gray-50'
                }`}
              >
                {tf}
              </button>
            ))}
          </div>
          <Button variant="outline" size="sm">
            <Cog6ToothIcon className="w-4 h-4 mr-2" />
            Settings
          </Button>
        </div>
      </div>

      {/* Risk Overview Cards */}
      {riskMetrics && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <Card className="bg-gradient-to-r from-blue-50 to-blue-100 border-blue-200">
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-blue-600">Portfolio VaR (95%)</p>
                  <p className="text-2xl font-bold text-blue-900">
                    ${riskMetrics.portfolioVar.toLocaleString()}
                  </p>
                </div>
                <ChartPieIcon className="w-8 h-8 text-blue-500" />
              </div>
            </CardContent>
          </Card>

          <Card className="bg-gradient-to-r from-green-50 to-green-100 border-green-200">
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-green-600">Sharpe Ratio</p>
                  <p className="text-2xl font-bold text-green-900">
                    {riskMetrics.sharpeRatio.toFixed(2)}
                  </p>
                </div>
                <TrendingUpIcon className="w-8 h-8 text-green-500" />
              </div>
            </CardContent>
          </Card>

          <Card className={`bg-gradient-to-r ${riskMetrics.currentDrawdown < 0.1 ? 'from-green-50 to-green-100 border-green-200' : 'from-red-50 to-red-100 border-red-200'}`}>
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className={`text-sm font-medium ${riskMetrics.currentDrawdown < 0.1 ? 'text-green-600' : 'text-red-600'}`}>
                    Current Drawdown
                  </p>
                  <p className={`text-2xl font-bold ${riskMetrics.currentDrawdown < 0.1 ? 'text-green-900' : 'text-red-900'}`}>
                    {(riskMetrics.currentDrawdown * 100).toFixed(1)}%
                  </p>
                </div>
                <TrendingDownIcon className={`w-8 h-8 ${riskMetrics.currentDrawdown < 0.1 ? 'text-green-500' : 'text-red-500'}`} />
              </div>
            </CardContent>
          </Card>

          <Card className="bg-gradient-to-r from-purple-50 to-purple-100 border-purple-200">
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-purple-600">Volatility (Ann.)</p>
                  <p className="text-2xl font-bold text-purple-900">
                    {(riskMetrics.volatility * 100).toFixed(1)}%
                  </p>
                </div>
                <SignalIcon className="w-8 h-8 text-purple-500" />
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Main Dashboard */}
      <Tabs defaultValue="limits" className="w-full">
        <TabsList className="grid w-full grid-cols-5">
          <TabsTrigger value="limits">Risk Limits</TabsTrigger>
          <TabsTrigger value="exposure">Exposure</TabsTrigger>
          <TabsTrigger value="metrics">Metrics</TabsTrigger>
          <TabsTrigger value="events">Events</TabsTrigger>
          <TabsTrigger value="stress">Stress Tests</TabsTrigger>
        </TabsList>

        <TabsContent value="limits" className="space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {riskLimits.map((limit) => (
              <Card key={limit.id} className={`border-l-4 ${
                limit.status === 'breach' ? 'border-red-500' :
                limit.status === 'warning' ? 'border-yellow-500' : 
                'border-green-500'
              }`}>
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-lg">{limit.name}</CardTitle>
                    <Badge 
                      variant="outline" 
                      className={`${getRiskStatusColor(limit.status)}`}
                    >
                      {limit.status.toUpperCase()}
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    <div className="flex justify-between items-end">
                      <div>
                        <p className="text-sm text-gray-600">Current / Limit</p>
                        <p className="text-lg font-semibold">
                          {limit.type === 'concentration' ? 
                            `${(limit.currentValue * 100).toFixed(1)}% / ${(limit.limitValue * 100).toFixed(1)}%` :
                            `${limit.currentValue.toLocaleString()} / ${limit.limitValue.toLocaleString()}`
                          }
                        </p>
                      </div>
                      <div className="text-right">
                        <p className="text-sm text-gray-600">Utilization</p>
                        <p className="text-xl font-bold">{limit.utilizationPercent.toFixed(1)}%</p>
                      </div>
                    </div>
                    
                    <div className="w-full bg-gray-200 rounded-full h-2">
                      <div 
                        className={`h-2 rounded-full ${getUtilizationBarColor(limit.utilizationPercent)}`}
                        style={{ width: `${Math.min(limit.utilizationPercent, 100)}%` }}
                      />
                    </div>
                    
                    <p className="text-xs text-gray-500">
                      Last updated: {format(new Date(limit.lastUpdated), 'HH:mm:ss')}
                    </p>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        <TabsContent value="exposure" className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Exposure Chart */}
            <Card>
              <CardHeader>
                <CardTitle>Portfolio Exposure Distribution</CardTitle>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={300}>
                  <PieChart>
                    <Pie
                      dataKey="percentage"
                      data={portfolioExposure}
                      cx="50%"
                      cy="50%"
                      outerRadius={100}
                      label={({ symbol, percentage }) => `${symbol} (${percentage}%)`}
                    >
                      {portfolioExposure.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={
                          entry.risk === 'high' ? '#f87171' :
                          entry.risk === 'medium' ? '#fbbf24' : '#34d399'
                        } />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>

            {/* Exposure Table */}
            <Card>
              <CardHeader>
                <CardTitle>Currency Exposure Details</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {portfolioExposure.map((exposure) => (
                    <div key={exposure.symbol} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                      <div className="flex items-center space-x-3">
                        <div className={`w-3 h-3 rounded-full ${
                          exposure.risk === 'high' ? 'bg-red-500' :
                          exposure.risk === 'medium' ? 'bg-yellow-500' : 'bg-green-500'
                        }`} />
                        <div>
                          <p className="font-medium">{exposure.symbol}</p>
                          <p className="text-sm text-gray-500">${exposure.exposure.toLocaleString()}</p>
                        </div>
                      </div>
                      <div className="text-right">
                        <p className="font-semibold">{exposure.percentage}%</p>
                        <Badge 
                          variant="outline" 
                          className={`text-xs ${getSeverityColor(exposure.risk)}`}
                        >
                          {exposure.risk}
                        </Badge>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="metrics" className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Risk Metrics Radar */}
            <Card>
              <CardHeader>
                <CardTitle>Risk Profile Analysis</CardTitle>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={300}>
                  <RadarChart data={radarData}>
                    <PolarGrid />
                    <PolarAngleAxis dataKey="subject" />
                    <PolarRadiusAxis angle={90} domain={[0, 100]} />
                    <Radar name="Risk Score" dataKey="A" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.3} />
                    <Tooltip />
                  </RadarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>

            {/* Detailed Metrics */}
            <Card>
              <CardHeader>
                <CardTitle>Detailed Risk Metrics</CardTitle>
              </CardHeader>
              <CardContent>
                {riskMetrics && (
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-3">
                      <div>
                        <p className="text-sm text-gray-600">Expected Shortfall</p>
                        <p className="text-lg font-semibold">${riskMetrics.expectedShortfall.toFixed(2)}</p>
                      </div>
                      <div>
                        <p className="text-sm text-gray-600">Max Drawdown</p>
                        <p className="text-lg font-semibold">{(riskMetrics.maxDrawdown * 100).toFixed(1)}%</p>
                      </div>
                      <div>
                        <p className="text-sm text-gray-600">Beta to Market</p>
                        <p className="text-lg font-semibold">{riskMetrics.betaToMarket.toFixed(2)}</p>
                      </div>
                    </div>
                    <div className="space-y-3">
                      <div>
                        <p className="text-sm text-gray-600">Sortino Ratio</p>
                        <p className="text-lg font-semibold">{riskMetrics.sortinoRatio.toFixed(2)}</p>
                      </div>
                      <div>
                        <p className="text-sm text-gray-600">Market Correlation</p>
                        <p className="text-lg font-semibold">{riskMetrics.correlationToMarket.toFixed(2)}</p>
                      </div>
                      <div>
                        <p className="text-sm text-gray-600">Ann. Volatility</p>
                        <p className="text-lg font-semibold">{(riskMetrics.volatility * 100).toFixed(1)}%</p>
                      </div>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="events" className="space-y-4">
          <div className="space-y-4">
            {riskEvents.map((event) => (
              <motion.div
                key={event.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className={`p-4 rounded-lg border-l-4 ${
                  event.severity === 'critical' ? 'border-red-500 bg-red-50' :
                  event.severity === 'high' ? 'border-orange-500 bg-orange-50' :
                  event.severity === 'medium' ? 'border-yellow-500 bg-yellow-50' :
                  'border-blue-500 bg-blue-50'
                }`}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center space-x-2 mb-2">
                      <h4 className="text-sm font-medium text-gray-900">{event.title}</h4>
                      <Badge variant="outline" className={getSeverityColor(event.severity)}>
                        {event.severity}
                      </Badge>
                      <Badge variant="secondary" className="text-xs">
                        {event.type.replace('_', ' ')}
                      </Badge>
                    </div>
                    <p className="text-sm text-gray-600 mb-2">{event.description}</p>
                    <div className="flex items-center space-x-4 text-xs text-gray-500">
                      <span>{format(new Date(event.timestamp), 'PPpp')}</span>
                      <span>Impact: {event.impact >= 0 ? '+' : ''}${event.impact.toLocaleString()}</span>
                      <span>Status: {event.status}</span>
                    </div>
                  </div>
                  <div className="flex space-x-2">
                    <Button variant="outline" size="sm">View Details</Button>
                    {event.status === 'active' && (
                      <Button variant="outline" size="sm">Acknowledge</Button>
                    )}
                  </div>
                </div>
              </motion.div>
            ))}
          </div>
        </TabsContent>

        <TabsContent value="stress" className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {stressTests.map((test, index) => (
              <Card key={index} className="border">
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-lg">{test.name}</CardTitle>
                    <Badge variant="outline" className={getSeverityColor(test.severity)}>
                      {test.severity}
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-gray-600 mb-4">{test.description}</p>
                  
                  <div className="grid grid-cols-2 gap-4 mb-4">
                    <div>
                      <p className="text-sm text-gray-600">Market Shock</p>
                      <p className="text-lg font-semibold">{test.marketShock > 0 ? '+' : ''}{test.marketShock}%</p>
                    </div>
                    <div>
                      <p className="text-sm text-gray-600">Portfolio Impact</p>
                      <p className={`text-lg font-semibold ${test.portfolioImpact >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                        {test.portfolioImpact >= 0 ? '+' : ''}${test.portfolioImpact.toLocaleString()}
                      </p>
                    </div>
                  </div>

                  <div className="mb-4">
                    <p className="text-sm text-gray-600 mb-2">Probability: {(test.probability * 100).toFixed(1)}%</p>
                    <div className="w-full bg-gray-200 rounded-full h-2">
                      <div 
                        className="bg-blue-500 h-2 rounded-full"
                        style={{ width: `${test.probability * 100}%` }}
                      />
                    </div>
                  </div>

                  <Button variant="outline" size="sm" className="w-full">
                    Run Scenario Analysis
                  </Button>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}