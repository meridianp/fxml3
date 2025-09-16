/**
 * Phase 7 - Advanced Trading Dashboard
 * 
 * Enhanced trading interface with real-time data visualization, 
 * advanced charting, and comprehensive position monitoring.
 */

'use client';

import React, { useState, useEffect, useRef, useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { 
  LineChart, 
  Line, 
  CandlestickChart,
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer,
  ReferenceLine,
  Brush,
  ComposedChart,
  Bar,
  Area
} from 'recharts';
import {
  ChartBarIcon,
  CurrencyDollarIcon,
  ArrowTrendingUpIcon,
  ArrowTrendingDownIcon,
  ClockIcon,
  BoltIcon,
  AdjustmentsHorizontalIcon,
  PlayIcon,
  PauseIcon,
  ArrowsPointingOutIcon,
  MagnifyingGlassIcon
} from '@heroicons/react/24/outline';
import { format, subHours, subMinutes } from 'date-fns';
import { motion, AnimatePresence } from 'framer-motion';
import { createChart, ColorType } from 'lightweight-charts';

// Types for trading data
interface MarketData {
  symbol: string;
  timestamp: string;
  bid: number;
  ask: number;
  spread: number;
  volume: number;
  high: number;
  low: number;
  open: number;
  close: number;
}

interface Position {
  id: string;
  symbol: string;
  side: 'buy' | 'sell';
  size: number;
  entry_price: number;
  current_price: number;
  unrealized_pnl: number;
  realized_pnl: number;
  timestamp: string;
  duration: string;
}

interface Order {
  id: string;
  symbol: string;
  side: 'buy' | 'sell';
  type: 'market' | 'limit' | 'stop';
  size: number;
  price?: number;
  status: 'pending' | 'filled' | 'cancelled' | 'rejected';
  timestamp: string;
}

interface TradingMetrics {
  totalPnL: number;
  dayPnL: number;
  openPositions: number;
  pendingOrders: number;
  winRate: number;
  averageWin: number;
  averageLoss: number;
  sharpeRatio: number;
}

interface ChartData {
  timestamp: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export default function AdvancedTradingDashboard() {
  const [selectedSymbol, setSelectedSymbol] = useState('EUR/USD');
  const [selectedTimeframe, setSelectedTimeframe] = useState<'1m' | '5m' | '15m' | '1h' | '4h'>('15m');
  const [isLiveData, setIsLiveData] = useState(true);
  const [positions, setPositions] = useState<Position[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [tradingMetrics, setTradingMetrics] = useState<TradingMetrics | null>(null);
  const [marketData, setMarketData] = useState<MarketData[]>([]);
  const [chartData, setChartData] = useState<ChartData[]>([]);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const chartContainerRef = useRef<HTMLDivElement>(null);

  // Symbols available for trading
  const symbols = ['EUR/USD', 'GBP/USD', 'USD/JPY', 'AUD/USD', 'USD/CHF', 'NZD/USD', 'USD/CAD'];

  // Generate mock data
  useEffect(() => {
    const generateMockData = () => {
      const now = new Date();
      const data: ChartData[] = [];
      let basePrice = 1.0950; // EUR/USD base price

      // Generate 200 data points
      for (let i = 199; i >= 0; i--) {
        const timestamp = subMinutes(now, i * (selectedTimeframe === '1m' ? 1 : selectedTimeframe === '5m' ? 5 : 15)).getTime();
        
        // Simulate price movement
        const volatility = 0.001; // 0.1% volatility
        const change = (Math.random() - 0.5) * volatility;
        basePrice += change;
        
        const high = basePrice + Math.random() * 0.0005;
        const low = basePrice - Math.random() * 0.0005;
        const open = i === 199 ? basePrice : data[data.length - 1]?.close || basePrice;
        const close = basePrice;
        const volume = Math.floor(Math.random() * 1000000) + 100000;

        data.push({
          timestamp,
          open,
          high: Math.max(open, close, high),
          low: Math.min(open, close, low),
          close,
          volume
        });
      }

      setChartData(data);
    };

    const mockMetrics: TradingMetrics = {
      totalPnL: 12847.50,
      dayPnL: 892.30,
      openPositions: 3,
      pendingOrders: 2,
      winRate: 68.4,
      averageWin: 145.20,
      averageLoss: -87.40,
      sharpeRatio: 1.84
    };

    const mockPositions: Position[] = [
      {
        id: '1',
        symbol: 'EUR/USD',
        side: 'buy',
        size: 100000,
        entry_price: 1.0945,
        current_price: 1.0952,
        unrealized_pnl: 70.00,
        realized_pnl: 0,
        timestamp: new Date(Date.now() - 3600000).toISOString(),
        duration: '1h 15m'
      },
      {
        id: '2',
        symbol: 'GBP/USD',
        side: 'sell',
        size: 50000,
        entry_price: 1.2720,
        current_price: 1.2715,
        unrealized_pnl: 25.00,
        realized_pnl: 0,
        timestamp: new Date(Date.now() - 1800000).toISOString(),
        duration: '32m'
      }
    ];

    const mockOrders: Order[] = [
      {
        id: '1',
        symbol: 'USD/JPY',
        side: 'buy',
        type: 'limit',
        size: 75000,
        price: 148.50,
        status: 'pending',
        timestamp: new Date(Date.now() - 900000).toISOString()
      },
      {
        id: '2',
        symbol: 'AUD/USD',
        side: 'sell',
        type: 'stop',
        size: 100000,
        price: 0.6650,
        status: 'pending',
        timestamp: new Date(Date.now() - 600000).toISOString()
      }
    ];

    generateMockData();
    setTradingMetrics(mockMetrics);
    setPositions(mockPositions);
    setOrders(mockOrders);

    // Set up real-time data updates
    const interval = setInterval(() => {
      if (isLiveData) {
        generateMockData();
      }
    }, selectedTimeframe === '1m' ? 60000 : 300000); // Update every minute for 1m, every 5 minutes otherwise

    return () => clearInterval(interval);
  }, [selectedSymbol, selectedTimeframe, isLiveData]);

  // Custom Candlestick Chart Component using Lightweight Charts
  const TradingViewChart = ({ data }: { data: ChartData[] }) => {
    const chartRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
      if (!chartRef.current || !data.length) return;

      const chart = createChart(chartRef.current, {
        width: chartRef.current.clientWidth,
        height: 400,
        layout: {
          background: { type: ColorType.Solid, color: '#ffffff' },
          textColor: '#333333',
        },
        grid: {
          vertLines: { color: '#f0f0f0' },
          horzLines: { color: '#f0f0f0' },
        },
        crosshair: {
          mode: 1,
        },
        rightPriceScale: {
          borderColor: '#cccccc',
        },
        timeScale: {
          borderColor: '#cccccc',
          timeVisible: true,
          secondsVisible: false,
        },
      });

      const candlestickSeries = chart.addCandlestickSeries({
        upColor: '#4caf50',
        downColor: '#f44336',
        borderDownColor: '#f44336',
        borderUpColor: '#4caf50',
        wickDownColor: '#f44336',
        wickUpColor: '#4caf50',
      });

      const volumeSeries = chart.addHistogramSeries({
        color: '#26a69a',
        priceFormat: {
          type: 'volume',
        },
        priceScaleId: '',
      });

      chart.priceScale('').applyOptions({
        scaleMargins: {
          top: 0.8,
          bottom: 0,
        },
      });

      const candleData = data.map(d => ({
        time: Math.floor(d.timestamp / 1000) as any,
        open: d.open,
        high: d.high,
        low: d.low,
        close: d.close
      }));

      const volumeData = data.map(d => ({
        time: Math.floor(d.timestamp / 1000) as any,
        value: d.volume,
        color: d.close >= d.open ? '#4caf50' : '#f44336'
      }));

      candlestickSeries.setData(candleData);
      volumeSeries.setData(volumeData as any);

      const handleResize = () => {
        if (chartRef.current) {
          chart.applyOptions({ width: chartRef.current.clientWidth });
        }
      };

      window.addEventListener('resize', handleResize);

      return () => {
        window.removeEventListener('resize', handleResize);
        chart.remove();
      };
    }, [data]);

    return <div ref={chartRef} className="w-full h-96" />;
  };

  // Helper functions
  const formatPrice = (price: number, symbol: string) => {
    const digits = symbol.includes('JPY') ? 3 : 5;
    return price.toFixed(digits);
  };

  const formatPnL = (pnl: number) => {
    const color = pnl >= 0 ? 'text-green-600' : 'text-red-600';
    const sign = pnl >= 0 ? '+' : '';
    return <span className={color}>{sign}${pnl.toFixed(2)}</span>;
  };

  if (!tradingMetrics) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-blue-500"></div>
      </div>
    );
  }

  return (
    <div className={`space-y-6 p-6 ${isFullscreen ? 'fixed inset-0 z-50 bg-white overflow-auto' : ''}`}>
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Advanced Trading Dashboard</h1>
          <p className="text-sm text-gray-600">
            Real-time market analysis and position management
          </p>
        </div>
        <div className="flex items-center space-x-2 mt-4 sm:mt-0">
          <Button 
            variant={isLiveData ? "default" : "outline"} 
            size="sm"
            onClick={() => setIsLiveData(!isLiveData)}
          >
            {isLiveData ? <PauseIcon className="w-4 h-4 mr-2" /> : <PlayIcon className="w-4 h-4 mr-2" />}
            {isLiveData ? 'Pause' : 'Resume'} Live Data
          </Button>
          <Button 
            variant="outline" 
            size="sm"
            onClick={() => setIsFullscreen(!isFullscreen)}
          >
            <ArrowsPointingOutIcon className="w-4 h-4 mr-2" />
            {isFullscreen ? 'Exit' : 'Fullscreen'}
          </Button>
        </div>
      </div>

      {/* Trading Metrics Overview */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card className="bg-gradient-to-r from-green-50 to-green-100 border-green-200">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-green-600">Total P&L</p>
                <p className="text-2xl font-bold text-green-900">
                  ${tradingMetrics.totalPnL.toLocaleString()}
                </p>
              </div>
              <ArrowTrendingUpIcon className="w-8 h-8 text-green-500" />
            </div>
          </CardContent>
        </Card>

        <Card className={`bg-gradient-to-r ${tradingMetrics.dayPnL >= 0 ? 'from-blue-50 to-blue-100 border-blue-200' : 'from-red-50 to-red-100 border-red-200'}`}>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className={`text-sm font-medium ${tradingMetrics.dayPnL >= 0 ? 'text-blue-600' : 'text-red-600'}`}>Today P&L</p>
                <p className={`text-2xl font-bold ${tradingMetrics.dayPnL >= 0 ? 'text-blue-900' : 'text-red-900'}`}>
                  {tradingMetrics.dayPnL >= 0 ? '+' : ''}${tradingMetrics.dayPnL.toFixed(2)}
                </p>
              </div>
              {tradingMetrics.dayPnL >= 0 ? 
                <ArrowTrendingUpIcon className="w-8 h-8 text-blue-500" /> :
                <ArrowTrendingDownIcon className="w-8 h-8 text-red-500" />
              }
            </div>
          </CardContent>
        </Card>

        <Card className="bg-gradient-to-r from-purple-50 to-purple-100 border-purple-200">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-purple-600">Open Positions</p>
                <p className="text-2xl font-bold text-purple-900">
                  {tradingMetrics.openPositions}
                </p>
              </div>
              <ChartBarIcon className="w-8 h-8 text-purple-500" />
            </div>
          </CardContent>
        </Card>

        <Card className="bg-gradient-to-r from-orange-50 to-orange-100 border-orange-200">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-orange-600">Win Rate</p>
                <p className="text-2xl font-bold text-orange-900">
                  {tradingMetrics.winRate}%
                </p>
              </div>
              <BoltIcon className="w-8 h-8 text-orange-500" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Main Trading Interface */}
      <div className="grid grid-cols-1 xl:grid-cols-4 gap-6">
        {/* Chart Section */}
        <div className="xl:col-span-3">
          <Card>
            <CardHeader>
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between">
                <CardTitle className="flex items-center">
                  <ChartBarIcon className="w-5 h-5 mr-2" />
                  {selectedSymbol} Chart
                </CardTitle>
                <div className="flex items-center space-x-2 mt-2 sm:mt-0">
                  <select 
                    value={selectedSymbol} 
                    onChange={(e) => setSelectedSymbol(e.target.value)}
                    className="px-3 py-1 border rounded-md text-sm"
                  >
                    {symbols.map(symbol => (
                      <option key={symbol} value={symbol}>{symbol}</option>
                    ))}
                  </select>
                  <div className="flex rounded-md overflow-hidden border">
                    {(['1m', '5m', '15m', '1h', '4h'] as const).map((tf) => (
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
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <TradingViewChart data={chartData} />
            </CardContent>
          </Card>
        </div>

        {/* Order Panel */}
        <div className="xl:col-span-1">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center">
                <CurrencyDollarIcon className="w-5 h-5 mr-2" />
                Quick Order
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <label className="text-sm font-medium">Symbol</label>
                <select className="w-full mt-1 px-3 py-2 border rounded-md">
                  {symbols.map(symbol => (
                    <option key={symbol} value={symbol}>{symbol}</option>
                  ))}
                </select>
              </div>
              
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="text-sm font-medium">Size</label>
                  <input 
                    type="number" 
                    defaultValue="10000"
                    className="w-full mt-1 px-3 py-2 border rounded-md"
                  />
                </div>
                <div>
                  <label className="text-sm font-medium">Type</label>
                  <select className="w-full mt-1 px-3 py-2 border rounded-md">
                    <option value="market">Market</option>
                    <option value="limit">Limit</option>
                    <option value="stop">Stop</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <Button className="w-full bg-green-500 hover:bg-green-600 text-white">
                  Buy {formatPrice(chartData[chartData.length - 1]?.close || 1.0950, selectedSymbol)}
                </Button>
                <Button className="w-full bg-red-500 hover:bg-red-600 text-white">
                  Sell {formatPrice(chartData[chartData.length - 1]?.close || 1.0950, selectedSymbol)}
                </Button>
              </div>

              <div className="pt-4 border-t">
                <h4 className="font-medium mb-2">Market Info</h4>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span>Spread:</span>
                    <span>1.2 pips</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Margin:</span>
                    <span>3.33%</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Swap:</span>
                    <span>-0.5 / +0.2</span>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Positions and Orders Tables */}
      <Tabs defaultValue="positions" className="w-full">
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="positions">Open Positions ({positions.length})</TabsTrigger>
          <TabsTrigger value="orders">Pending Orders ({orders.length})</TabsTrigger>
          <TabsTrigger value="history">Trade History</TabsTrigger>
        </TabsList>

        <TabsContent value="positions">
          <Card>
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-gray-50 border-b">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Symbol</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Side</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Size</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Entry</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Current</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">P&L</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Duration</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {positions.map((position) => (
                      <motion.tr
                        key={position.id}
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="hover:bg-gray-50"
                      >
                        <td className="px-4 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                          {position.symbol}
                        </td>
                        <td className="px-4 py-4 whitespace-nowrap text-sm">
                          <Badge variant={position.side === 'buy' ? 'default' : 'secondary'} className={
                            position.side === 'buy' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                          }>
                            {position.side.toUpperCase()}
                          </Badge>
                        </td>
                        <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-900">
                          {position.size.toLocaleString()}
                        </td>
                        <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-900">
                          {formatPrice(position.entry_price, position.symbol)}
                        </td>
                        <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-900">
                          {formatPrice(position.current_price, position.symbol)}
                        </td>
                        <td className="px-4 py-4 whitespace-nowrap text-sm">
                          {formatPnL(position.unrealized_pnl)}
                        </td>
                        <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-500">
                          {position.duration}
                        </td>
                        <td className="px-4 py-4 whitespace-nowrap text-sm">
                          <div className="flex space-x-2">
                            <Button variant="outline" size="sm">Close</Button>
                            <Button variant="outline" size="sm">Modify</Button>
                          </div>
                        </td>
                      </motion.tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="orders">
          <Card>
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-gray-50 border-b">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Symbol</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Side</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Type</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Size</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Price</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Time</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {orders.map((order) => (
                      <motion.tr
                        key={order.id}
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="hover:bg-gray-50"
                      >
                        <td className="px-4 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                          {order.symbol}
                        </td>
                        <td className="px-4 py-4 whitespace-nowrap text-sm">
                          <Badge variant={order.side === 'buy' ? 'default' : 'secondary'} className={
                            order.side === 'buy' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                          }>
                            {order.side.toUpperCase()}
                          </Badge>
                        </td>
                        <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-900">
                          {order.type.toUpperCase()}
                        </td>
                        <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-900">
                          {order.size.toLocaleString()}
                        </td>
                        <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-900">
                          {order.price ? formatPrice(order.price, order.symbol) : 'Market'}
                        </td>
                        <td className="px-4 py-4 whitespace-nowrap text-sm">
                          <Badge variant="outline" className="bg-yellow-100 text-yellow-800">
                            {order.status.toUpperCase()}
                          </Badge>
                        </td>
                        <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-500">
                          {format(new Date(order.timestamp), 'HH:mm:ss')}
                        </td>
                        <td className="px-4 py-4 whitespace-nowrap text-sm">
                          <div className="flex space-x-2">
                            <Button variant="outline" size="sm">Cancel</Button>
                            <Button variant="outline" size="sm">Modify</Button>
                          </div>
                        </td>
                      </motion.tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="history">
          <Card>
            <CardContent className="p-8 text-center">
              <p className="text-gray-500">Trade history will be displayed here</p>
              <p className="text-sm text-gray-400 mt-2">Connect to view your trading history</p>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}