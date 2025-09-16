/**
 * Manual Execution Interface Component
 *
 * Direct market execution and order management interface for traders
 */

'use client';

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { useAppStore } from '@/stores/appStore';
import {
  CurrencyDollarIcon,
  ArrowUpIcon,
  ArrowDownIcon,
  ClockIcon,
  XMarkIcon,
  PencilIcon,
  EyeIcon,
  PlayIcon,
  PauseIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  ChartBarIcon,
  CalculatorIcon,
  AdjustmentsHorizontalIcon,
  BanknotesIcon,
  ScaleIcon
} from '@heroicons/react/24/outline';

interface MarketData {
  symbol: string;
  bid: number;
  ask: number;
  spread: number;
  change: number;
  change_percent: number;
  volume: number;
  timestamp: string;
}

interface OrderTicket {
  symbol: string;
  side: 'buy' | 'sell';
  order_type: 'market' | 'limit' | 'stop' | 'stop_limit';
  size: number;
  price?: number;
  stop_price?: number;
  time_in_force: 'GTC' | 'IOC' | 'FOK' | 'DAY';
  reduce_only: boolean;
}

interface Order {
  id: string;
  symbol: string;
  side: 'buy' | 'sell';
  order_type: string;
  size: number;
  filled_size: number;
  price?: number;
  avg_fill_price?: number;
  status: 'pending' | 'working' | 'filled' | 'cancelled' | 'rejected' | 'partial';
  time_in_force: string;
  created_at: string;
  updated_at: string;
  reduce_only: boolean;
}

interface Position {
  symbol: string;
  side: 'long' | 'short';
  size: number;
  entry_price: number;
  current_price: number;
  unrealized_pnl: number;
  unrealized_pnl_pct: number;
  margin_used: number;
}

interface RiskCalculation {
  position_value: number;
  margin_required: number;
  max_loss: number;
  risk_reward_ratio: number;
  portfolio_risk_pct: number;
}

export default function ManualExecution() {
  const [activeTab, setActiveTab] = useState('execution');
  const [marketData, setMarketData] = useState<MarketData[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [positions, setPositions] = useState<Position[]>([]);
  const [orderTicket, setOrderTicket] = useState<OrderTicket>({
    symbol: 'EURUSD',
    side: 'buy',
    order_type: 'market',
    size: 100000,
    time_in_force: 'GTC',
    reduce_only: false
  });
  const [selectedSymbol, setSelectedSymbol] = useState('EURUSD');
  const [riskCalculation, setRiskCalculation] = useState<RiskCalculation | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(true);

  const { addNotification, addError } = useAppStore();

  const SYMBOLS = ['EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'USDCHF', 'USDCAD', 'NZDUSD'];

  useEffect(() => {
    loadMarketData();
    loadOrders();
    loadPositions();
  }, []);

  useEffect(() => {
    let interval: NodeJS.Timeout;

    if (autoRefresh) {
      interval = setInterval(() => {
        loadMarketData();
        loadOrders();
        loadPositions();
      }, 1000); // Update every second for execution interface
    }

    return () => {
      if (interval) clearInterval(interval);
    };
  }, [autoRefresh]);

  useEffect(() => {
    calculateRisk();
  }, [orderTicket, marketData]);

  const loadMarketData = () => {
    // Mock market data with realistic forex prices
    const mockData: MarketData[] = SYMBOLS.map(symbol => ({
      symbol,
      bid: getBasePrice(symbol) + (Math.random() - 0.5) * 0.01,
      ask: getBasePrice(symbol) + (Math.random() - 0.5) * 0.01 + 0.0001,
      spread: 0.0001 + Math.random() * 0.0003,
      change: (Math.random() - 0.5) * 0.02,
      change_percent: (Math.random() - 0.5) * 2,
      volume: Math.floor(Math.random() * 1000000) + 500000,
      timestamp: new Date().toISOString()
    }));

    setMarketData(mockData);
  };

  const getBasePrice = (symbol: string): number => {
    const basePrices: Record<string, number> = {
      'EURUSD': 1.0850,
      'GBPUSD': 1.2650,
      'USDJPY': 149.50,
      'AUDUSD': 0.6580,
      'USDCHF': 0.8950,
      'USDCAD': 1.3750,
      'NZDUSD': 0.6050
    };
    return basePrices[symbol] || 1.0000;
  };

  const loadOrders = () => {
    const mockOrders: Order[] = [
      {
        id: 'ord_001',
        symbol: 'EURUSD',
        side: 'buy',
        order_type: 'limit',
        size: 100000,
        filled_size: 0,
        price: 1.0840,
        status: 'working',
        time_in_force: 'GTC',
        created_at: new Date(Date.now() - 300000).toISOString(),
        updated_at: new Date(Date.now() - 300000).toISOString(),
        reduce_only: false
      },
      {
        id: 'ord_002',
        symbol: 'GBPUSD',
        side: 'sell',
        order_type: 'market',
        size: 50000,
        filled_size: 50000,
        avg_fill_price: 1.2645,
        status: 'filled',
        time_in_force: 'IOC',
        created_at: new Date(Date.now() - 600000).toISOString(),
        updated_at: new Date(Date.now() - 580000).toISOString(),
        reduce_only: false
      },
      {
        id: 'ord_003',
        symbol: 'USDJPY',
        side: 'buy',
        order_type: 'stop',
        size: 75000,
        filled_size: 0,
        price: 150.00,
        status: 'working',
        time_in_force: 'GTC',
        created_at: new Date(Date.now() - 900000).toISOString(),
        updated_at: new Date(Date.now() - 900000).toISOString(),
        reduce_only: false
      }
    ];

    setOrders(mockOrders);
  };

  const loadPositions = () => {
    const mockPositions: Position[] = [
      {
        symbol: 'EURUSD',
        side: 'long',
        size: 200000,
        entry_price: 1.0845,
        current_price: 1.0852,
        unrealized_pnl: 140,
        unrealized_pnl_pct: 0.06,
        margin_used: 5000
      },
      {
        symbol: 'GBPUSD',
        side: 'short',
        size: 150000,
        entry_price: 1.2655,
        current_price: 1.2648,
        unrealized_pnl: 105,
        unrealized_pnl_pct: 0.06,
        margin_used: 3750
      },
      {
        symbol: 'USDJPY',
        side: 'long',
        size: 100000,
        entry_price: 149.30,
        current_price: 149.48,
        unrealized_pnl: 120,
        unrealized_pnl_pct: 0.12,
        margin_used: 2500
      }
    ];

    setPositions(mockPositions);
  };

  const calculateRisk = () => {
    const market = marketData.find(m => m.symbol === orderTicket.symbol);
    if (!market || !orderTicket.size) {
      setRiskCalculation(null);
      return;
    }

    const price = orderTicket.order_type === 'market'
      ? (orderTicket.side === 'buy' ? market.ask : market.bid)
      : orderTicket.price || market.ask;

    const positionValue = orderTicket.size * price;
    const marginRequired = positionValue * 0.025; // 2.5% margin
    const maxLoss = positionValue * 0.02; // Assume 2% stop loss
    const riskRewardRatio = 2.0; // Assume 2:1 RR
    const portfolioRiskPct = (maxLoss / 1000000) * 100; // Assume 1M portfolio

    setRiskCalculation({
      position_value: positionValue,
      margin_required: marginRequired,
      max_loss: maxLoss,
      risk_reward_ratio: riskRewardRatio,
      portfolio_risk_pct: portfolioRiskPct
    });
  };

  const submitOrder = async () => {
    try {
      const market = marketData.find(m => m.symbol === orderTicket.symbol);
      if (!market) {
        throw new Error('Market data not available');
      }

      const newOrder: Order = {
        id: `ord_${Date.now()}`,
        symbol: orderTicket.symbol,
        side: orderTicket.side,
        order_type: orderTicket.order_type,
        size: orderTicket.size,
        filled_size: orderTicket.order_type === 'market' ? orderTicket.size : 0,
        price: orderTicket.price,
        avg_fill_price: orderTicket.order_type === 'market'
          ? (orderTicket.side === 'buy' ? market.ask : market.bid)
          : undefined,
        status: orderTicket.order_type === 'market' ? 'filled' : 'working',
        time_in_force: orderTicket.time_in_force,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        reduce_only: orderTicket.reduce_only
      };

      setOrders(prev => [newOrder, ...prev]);

      // If market order, update positions
      if (orderTicket.order_type === 'market') {
        updatePositionsAfterFill(newOrder);
      }

      addNotification({
        type: 'success',
        title: 'Order Submitted',
        message: `${orderTicket.order_type.toUpperCase()} ${orderTicket.side} order for ${orderTicket.size} ${orderTicket.symbol} submitted`
      });

      // Reset order ticket
      setOrderTicket(prev => ({
        ...prev,
        size: 100000,
        price: undefined,
        stop_price: undefined
      }));

    } catch (error) {
      console.error('Order submission failed:', error);
      addError({
        code: 'ORDER_SUBMIT_ERROR',
        message: error instanceof Error ? error.message : 'Failed to submit order',
        timestamp: new Date().toISOString()
      });
    }
  };

  const updatePositionsAfterFill = (order: Order) => {
    const existingPosition = positions.find(p => p.symbol === order.symbol);

    if (existingPosition) {
      // Update existing position
      setPositions(prev => prev.map(pos => {
        if (pos.symbol === order.symbol) {
          const newSize = order.side === pos.side
            ? pos.size + order.filled_size
            : Math.abs(pos.size - order.filled_size);

          const newSide = order.side === pos.side
            ? pos.side
            : pos.size > order.filled_size ? pos.side : order.side;

          return {
            ...pos,
            size: newSize,
            side: newSide as 'long' | 'short'
          };
        }
        return pos;
      }));
    } else {
      // Create new position
      const market = marketData.find(m => m.symbol === order.symbol);
      if (market && order.avg_fill_price) {
        const newPosition: Position = {
          symbol: order.symbol,
          side: order.side === 'buy' ? 'long' : 'short',
          size: order.filled_size,
          entry_price: order.avg_fill_price,
          current_price: order.side === 'buy' ? market.bid : market.ask,
          unrealized_pnl: 0,
          unrealized_pnl_pct: 0,
          margin_used: order.filled_size * order.avg_fill_price * 0.025
        };
        setPositions(prev => [...prev, newPosition]);
      }
    }
  };

  const cancelOrder = (orderId: string) => {
    setOrders(prev => prev.map(order =>
      order.id === orderId ? { ...order, status: 'cancelled' as const } : order
    ));

    addNotification({
      type: 'info',
      title: 'Order Cancelled',
      message: 'Order has been cancelled'
    });
  };

  const closePosition = (symbol: string) => {
    const position = positions.find(p => p.symbol === symbol);
    if (!position) return;

    const market = marketData.find(m => m.symbol === symbol);
    if (!market) return;

    // Create closing order
    const closeOrder: OrderTicket = {
      symbol: symbol,
      side: position.side === 'long' ? 'sell' : 'buy',
      order_type: 'market',
      size: position.size,
      time_in_force: 'IOC',
      reduce_only: true
    };

    setOrderTicket(closeOrder);
    submitOrder();

    // Remove position
    setPositions(prev => prev.filter(p => p.symbol !== symbol));

    addNotification({
      type: 'success',
      title: 'Position Closed',
      message: `${symbol} position closed at market`
    });
  };

  const formatCurrency = (value: number): string => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: value < 1 ? 4 : 2
    }).format(value);
  };

  const formatPrice = (symbol: string, price: number): string => {
    const decimals = symbol.includes('JPY') ? 3 : 5;
    return price.toFixed(decimals);
  };

  const getOrderStatusColor = (status: string): string => {
    switch (status) {
      case 'filled': return 'text-green-400 bg-green-500/20';
      case 'working': return 'text-blue-400 bg-blue-500/20';
      case 'partial': return 'text-yellow-400 bg-yellow-500/20';
      case 'cancelled': return 'text-gray-400 bg-gray-500/20';
      case 'rejected': return 'text-red-400 bg-red-500/20';
      default: return 'text-gray-400 bg-gray-500/20';
    }
  };

  return (
    <div className="h-full">
      <Tabs value={activeTab} onValueChange={setActiveTab} className="h-full flex flex-col">
        {/* Header */}
        <div className="p-6 border-b border-gray-700 bg-gray-900/50">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h1 className="text-2xl font-bold text-white">Manual Execution</h1>
              <p className="text-gray-400">Direct market access and order management</p>
            </div>

            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2">
                <label className="text-sm text-gray-300">Live Prices:</label>
                <input
                  type="checkbox"
                  checked={autoRefresh}
                  onChange={(e) => setAutoRefresh(e.target.checked)}
                  className="w-4 h-4 text-blue-500 bg-gray-800 border-gray-600 rounded focus:ring-blue-500"
                />
              </div>

              <div className="text-sm text-gray-400">
                Last update: {new Date().toLocaleTimeString()}
              </div>
            </div>
          </div>

          <TabsList className="grid w-full grid-cols-4 bg-gray-800">
            <TabsTrigger value="execution" className="gap-2">
              <CurrencyDollarIcon className="w-4 h-4" />
              Order Entry
            </TabsTrigger>
            <TabsTrigger value="market" className="gap-2">
              <ChartBarIcon className="w-4 h-4" />
              Market Data
            </TabsTrigger>
            <TabsTrigger value="orders" className="gap-2">
              <ClockIcon className="w-4 h-4" />
              Orders
            </TabsTrigger>
            <TabsTrigger value="positions" className="gap-2">
              <BanknotesIcon className="w-4 h-4" />
              Positions
            </TabsTrigger>
          </TabsList>
        </div>

        <div className="flex-1 p-6">
          <TabsContent value="execution" className="h-full mt-0">
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 h-full">
              {/* Order Ticket */}
              <div className="lg:col-span-2 bg-gray-900 border border-gray-700 rounded-lg p-6">
                <h3 className="text-lg font-semibold text-white mb-4">Order Ticket</h3>

                <div className="grid grid-cols-2 gap-4 mb-4">
                  <div>
                    <label className="block text-sm text-gray-300 mb-2">Symbol</label>
                    <select
                      value={orderTicket.symbol}
                      onChange={(e) => setOrderTicket(prev => ({ ...prev, symbol: e.target.value }))}
                      className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded text-white"
                    >
                      {SYMBOLS.map(symbol => (
                        <option key={symbol} value={symbol}>{symbol}</option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="block text-sm text-gray-300 mb-2">Order Type</label>
                    <select
                      value={orderTicket.order_type}
                      onChange={(e) => setOrderTicket(prev => ({ ...prev, order_type: e.target.value as any }))}
                      className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded text-white"
                    >
                      <option value="market">Market</option>
                      <option value="limit">Limit</option>
                      <option value="stop">Stop</option>
                      <option value="stop_limit">Stop Limit</option>
                    </select>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4 mb-4">
                  <div>
                    <label className="block text-sm text-gray-300 mb-2">Side</label>
                    <div className="flex gap-2">
                      <button
                        onClick={() => setOrderTicket(prev => ({ ...prev, side: 'buy' }))}
                        className={`flex-1 py-2 px-4 rounded font-medium transition-colors ${
                          orderTicket.side === 'buy'
                            ? 'bg-green-500 text-white'
                            : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                        }`}
                      >
                        <ArrowUpIcon className="w-4 h-4 inline mr-2" />
                        BUY
                      </button>
                      <button
                        onClick={() => setOrderTicket(prev => ({ ...prev, side: 'sell' }))}
                        className={`flex-1 py-2 px-4 rounded font-medium transition-colors ${
                          orderTicket.side === 'sell'
                            ? 'bg-red-500 text-white'
                            : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                        }`}
                      >
                        <ArrowDownIcon className="w-4 h-4 inline mr-2" />
                        SELL
                      </button>
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm text-gray-300 mb-2">Size</label>
                    <input
                      type="number"
                      value={orderTicket.size}
                      onChange={(e) => setOrderTicket(prev => ({ ...prev, size: parseInt(e.target.value) || 0 }))}
                      min="1000"
                      step="1000"
                      className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded text-white"
                    />
                  </div>
                </div>

                {(orderTicket.order_type === 'limit' || orderTicket.order_type === 'stop_limit') && (
                  <div className="mb-4">
                    <label className="block text-sm text-gray-300 mb-2">Limit Price</label>
                    <input
                      type="number"
                      value={orderTicket.price || ''}
                      onChange={(e) => setOrderTicket(prev => ({ ...prev, price: parseFloat(e.target.value) || undefined }))}
                      step="0.00001"
                      className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded text-white"
                      placeholder="Enter limit price"
                    />
                  </div>
                )}

                {(orderTicket.order_type === 'stop' || orderTicket.order_type === 'stop_limit') && (
                  <div className="mb-4">
                    <label className="block text-sm text-gray-300 mb-2">Stop Price</label>
                    <input
                      type="number"
                      value={orderTicket.stop_price || ''}
                      onChange={(e) => setOrderTicket(prev => ({ ...prev, stop_price: parseFloat(e.target.value) || undefined }))}
                      step="0.00001"
                      className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded text-white"
                      placeholder="Enter stop price"
                    />
                  </div>
                )}

                <div className="grid grid-cols-2 gap-4 mb-6">
                  <div>
                    <label className="block text-sm text-gray-300 mb-2">Time in Force</label>
                    <select
                      value={orderTicket.time_in_force}
                      onChange={(e) => setOrderTicket(prev => ({ ...prev, time_in_force: e.target.value as any }))}
                      className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded text-white"
                    >
                      <option value="GTC">Good Till Cancelled</option>
                      <option value="IOC">Immediate or Cancel</option>
                      <option value="FOK">Fill or Kill</option>
                      <option value="DAY">Day Order</option>
                    </select>
                  </div>

                  <div className="flex items-end">
                    <label className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={orderTicket.reduce_only}
                        onChange={(e) => setOrderTicket(prev => ({ ...prev, reduce_only: e.target.checked }))}
                        className="w-4 h-4 text-blue-500 bg-gray-800 border-gray-600 rounded focus:ring-blue-500"
                      />
                      <span className="text-sm text-gray-300">Reduce Only</span>
                    </label>
                  </div>
                </div>

                {/* Current Market Price */}
                {(() => {
                  const market = marketData.find(m => m.symbol === orderTicket.symbol);
                  return market ? (
                    <div className="mb-6 p-4 bg-gray-800/50 rounded">
                      <div className="flex justify-between items-center">
                        <span className="text-gray-300">Current Market</span>
                        <div className="flex items-center gap-4">
                          <div className="text-right">
                            <div className="text-xs text-gray-400">BID</div>
                            <div className="text-lg font-bold text-red-400">
                              {formatPrice(market.symbol, market.bid)}
                            </div>
                          </div>
                          <div className="text-right">
                            <div className="text-xs text-gray-400">ASK</div>
                            <div className="text-lg font-bold text-green-400">
                              {formatPrice(market.symbol, market.ask)}
                            </div>
                          </div>
                          <div className="text-right">
                            <div className="text-xs text-gray-400">SPREAD</div>
                            <div className="text-sm text-gray-300">
                              {(market.spread * 10000).toFixed(1)} pips
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  ) : null;
                })()}

                <Button
                  onClick={submitOrder}
                  disabled={!orderTicket.size}
                  className={`w-full py-3 text-lg font-bold ${
                    orderTicket.side === 'buy'
                      ? 'bg-green-600 hover:bg-green-700'
                      : 'bg-red-600 hover:bg-red-700'
                  }`}
                >
                  {orderTicket.side === 'buy' ? 'BUY' : 'SELL'} {orderTicket.symbol}
                </Button>
              </div>

              {/* Risk Calculator */}
              <div className="bg-gray-900 border border-gray-700 rounded-lg p-6">
                <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                  <CalculatorIcon className="w-5 h-5" />
                  Risk Calculator
                </h3>

                {riskCalculation ? (
                  <div className="space-y-4">
                    <div className="bg-gray-800/50 rounded p-3">
                      <div className="text-sm text-gray-400">Position Value</div>
                      <div className="text-lg font-bold text-white">
                        {formatCurrency(riskCalculation.position_value)}
                      </div>
                    </div>

                    <div className="bg-gray-800/50 rounded p-3">
                      <div className="text-sm text-gray-400">Margin Required</div>
                      <div className="text-lg font-bold text-blue-400">
                        {formatCurrency(riskCalculation.margin_required)}
                      </div>
                    </div>

                    <div className="bg-gray-800/50 rounded p-3">
                      <div className="text-sm text-gray-400">Max Risk (2% SL)</div>
                      <div className="text-lg font-bold text-red-400">
                        {formatCurrency(riskCalculation.max_loss)}
                      </div>
                    </div>

                    <div className="bg-gray-800/50 rounded p-3">
                      <div className="text-sm text-gray-400">Risk/Reward Ratio</div>
                      <div className="text-lg font-bold text-green-400">
                        1:{riskCalculation.risk_reward_ratio.toFixed(1)}
                      </div>
                    </div>

                    <div className="bg-gray-800/50 rounded p-3">
                      <div className="text-sm text-gray-400">Portfolio Risk</div>
                      <div className="text-lg font-bold text-yellow-400">
                        {riskCalculation.portfolio_risk_pct.toFixed(2)}%
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="text-center py-8 text-gray-400">
                    <CalculatorIcon className="w-12 h-12 mx-auto mb-3 opacity-50" />
                    <p>Configure order to see risk calculation</p>
                  </div>
                )}
              </div>
            </div>
          </TabsContent>

          <TabsContent value="market" className="h-full mt-0">
            <div className="bg-gray-900 border border-gray-700 rounded-lg overflow-hidden">
              <div className="p-4 border-b border-gray-700">
                <h3 className="text-lg font-semibold text-white">Live Market Data</h3>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-gray-800/50">
                    <tr>
                      <th className="px-4 py-3 text-left text-gray-300">Symbol</th>
                      <th className="px-4 py-3 text-left text-gray-300">Bid</th>
                      <th className="px-4 py-3 text-left text-gray-300">Ask</th>
                      <th className="px-4 py-3 text-left text-gray-300">Spread</th>
                      <th className="px-4 py-3 text-left text-gray-300">Change</th>
                      <th className="px-4 py-3 text-left text-gray-300">Volume</th>
                      <th className="px-4 py-3 text-left text-gray-300">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {marketData.map(market => (
                      <tr key={market.symbol} className="border-t border-gray-700 hover:bg-gray-800/30">
                        <td className="px-4 py-3 font-medium text-white">{market.symbol}</td>
                        <td className="px-4 py-3 text-red-400 font-mono">
                          {formatPrice(market.symbol, market.bid)}
                        </td>
                        <td className="px-4 py-3 text-green-400 font-mono">
                          {formatPrice(market.symbol, market.ask)}
                        </td>
                        <td className="px-4 py-3 text-gray-300">
                          {(market.spread * 10000).toFixed(1)} pips
                        </td>
                        <td className={`px-4 py-3 font-medium ${
                          market.change >= 0 ? 'text-green-400' : 'text-red-400'
                        }`}>
                          {market.change >= 0 ? '+' : ''}{(market.change * 100).toFixed(2)}%
                        </td>
                        <td className="px-4 py-3 text-gray-300">
                          {market.volume.toLocaleString()}
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex gap-1">
                            <Button
                              size="sm"
                              onClick={() => setOrderTicket(prev => ({
                                ...prev,
                                symbol: market.symbol,
                                side: 'buy'
                              }))}
                              className="bg-green-600 hover:bg-green-700 text-xs px-2 py-1"
                            >
                              BUY
                            </Button>
                            <Button
                              size="sm"
                              onClick={() => setOrderTicket(prev => ({
                                ...prev,
                                symbol: market.symbol,
                                side: 'sell'
                              }))}
                              className="bg-red-600 hover:bg-red-700 text-xs px-2 py-1"
                            >
                              SELL
                            </Button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </TabsContent>

          <TabsContent value="orders" className="h-full mt-0">
            <div className="bg-gray-900 border border-gray-700 rounded-lg overflow-hidden">
              <div className="p-4 border-b border-gray-700">
                <div className="flex items-center justify-between">
                  <h3 className="text-lg font-semibold text-white">Order History</h3>
                  <div className="text-sm text-gray-400">
                    {orders.filter(o => o.status === 'working').length} working orders
                  </div>
                </div>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-gray-800/50">
                    <tr>
                      <th className="px-4 py-3 text-left text-gray-300">Time</th>
                      <th className="px-4 py-3 text-left text-gray-300">Symbol</th>
                      <th className="px-4 py-3 text-left text-gray-300">Side</th>
                      <th className="px-4 py-3 text-left text-gray-300">Type</th>
                      <th className="px-4 py-3 text-left text-gray-300">Size</th>
                      <th className="px-4 py-3 text-left text-gray-300">Price</th>
                      <th className="px-4 py-3 text-left text-gray-300">Status</th>
                      <th className="px-4 py-3 text-left text-gray-300">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {orders.map(order => (
                      <tr key={order.id} className="border-t border-gray-700 hover:bg-gray-800/30">
                        <td className="px-4 py-3 text-gray-400">
                          {new Date(order.created_at).toLocaleTimeString()}
                        </td>
                        <td className="px-4 py-3 text-white font-medium">{order.symbol}</td>
                        <td className="px-4 py-3">
                          <span className={`px-2 py-1 rounded text-xs font-medium ${
                            order.side === 'buy' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
                          }`}>
                            {order.side.toUpperCase()}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-gray-300 capitalize">{order.order_type}</td>
                        <td className="px-4 py-3 text-gray-300">
                          {order.filled_size > 0 && order.filled_size < order.size
                            ? `${order.filled_size.toLocaleString()}/${order.size.toLocaleString()}`
                            : order.size.toLocaleString()}
                        </td>
                        <td className="px-4 py-3 text-gray-300 font-mono">
                          {order.price ? formatPrice(order.symbol, order.price) : 'Market'}
                        </td>
                        <td className="px-4 py-3">
                          <span className={`px-2 py-1 rounded text-xs ${getOrderStatusColor(order.status)}`}>
                            {order.status.toUpperCase()}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex gap-1">
                            {order.status === 'working' && (
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => cancelOrder(order.id)}
                                className="p-1 text-red-400"
                              >
                                <XMarkIcon className="w-3 h-3" />
                              </Button>
                            )}
                            <Button
                              size="sm"
                              variant="outline"
                              className="p-1"
                            >
                              <EyeIcon className="w-3 h-3" />
                            </Button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </TabsContent>

          <TabsContent value="positions" className="h-full mt-0">
            <div className="bg-gray-900 border border-gray-700 rounded-lg overflow-hidden">
              <div className="p-4 border-b border-gray-700">
                <div className="flex items-center justify-between">
                  <h3 className="text-lg font-semibold text-white">Open Positions</h3>
                  <div className="text-sm text-gray-400">
                    {positions.length} open positions
                  </div>
                </div>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-gray-800/50">
                    <tr>
                      <th className="px-4 py-3 text-left text-gray-300">Symbol</th>
                      <th className="px-4 py-3 text-left text-gray-300">Side</th>
                      <th className="px-4 py-3 text-left text-gray-300">Size</th>
                      <th className="px-4 py-3 text-left text-gray-300">Entry Price</th>
                      <th className="px-4 py-3 text-left text-gray-300">Current Price</th>
                      <th className="px-4 py-3 text-left text-gray-300">P&L</th>
                      <th className="px-4 py-3 text-left text-gray-300">Margin</th>
                      <th className="px-4 py-3 text-left text-gray-300">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {positions.map(position => (
                      <tr key={position.symbol} className="border-t border-gray-700 hover:bg-gray-800/30">
                        <td className="px-4 py-3 text-white font-medium">{position.symbol}</td>
                        <td className="px-4 py-3">
                          <span className={`px-2 py-1 rounded text-xs font-medium ${
                            position.side === 'long' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
                          }`}>
                            {position.side.toUpperCase()}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-gray-300">{position.size.toLocaleString()}</td>
                        <td className="px-4 py-3 text-gray-300 font-mono">
                          {formatPrice(position.symbol, position.entry_price)}
                        </td>
                        <td className="px-4 py-3 text-white font-mono">
                          {formatPrice(position.symbol, position.current_price)}
                        </td>
                        <td className="px-4 py-3">
                          <div className={`font-medium ${
                            position.unrealized_pnl >= 0 ? 'text-green-400' : 'text-red-400'
                          }`}>
                            {position.unrealized_pnl >= 0 ? '+' : ''}{formatCurrency(position.unrealized_pnl)}
                          </div>
                          <div className="text-xs text-gray-400">
                            ({position.unrealized_pnl >= 0 ? '+' : ''}{position.unrealized_pnl_pct.toFixed(2)}%)
                          </div>
                        </td>
                        <td className="px-4 py-3 text-gray-300">{formatCurrency(position.margin_used)}</td>
                        <td className="px-4 py-3">
                          <div className="flex gap-1">
                            <Button
                              size="sm"
                              onClick={() => closePosition(position.symbol)}
                              className="bg-red-600 hover:bg-red-700 text-xs px-2 py-1"
                            >
                              Close
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              className="p-1"
                            >
                              <PencilIcon className="w-3 h-3" />
                            </Button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </TabsContent>
        </div>
      </Tabs>
    </div>
  );
}
