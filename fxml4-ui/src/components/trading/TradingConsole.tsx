/**
 * Trading Console Component
 *
 * Main live trading interface with order management, positions, and market data
 */

'use client';

import { useState, useEffect } from 'react';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import OrderPanel from './OrderPanel';
import PositionsTable from './PositionsTable';
import OrdersTable from './OrdersTable';
import { MarketDataGrid } from '@/components/data';
import { useTradingStore } from '@/stores/useTradingStore';
import { useMarketDataStore } from '@/stores/useMarketDataStore';
import { useWebSocket } from '@/hooks/useWebSocket';
import { formatCurrency, formatPercentage } from '@/lib/utils';
import {
  CurrencyDollarIcon,
  ChartBarSquareIcon,
  DocumentTextIcon,
  ExclamationTriangleIcon,
  ShieldCheckIcon,
  BoltIcon,
  ArrowPathIcon
} from '@heroicons/react/24/outline';

export default function TradingConsole() {
  const [activeTab, setActiveTab] = useState('overview');
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [showMobileOrderPanel, setShowMobileOrderPanel] = useState(false);

  const {
    accountInfo,
    positions,
    orders,
    getTotalPnL
  } = useTradingStore();

  const { isConnected, lastUpdateTime } = useMarketDataStore();

  // Subscribe to all trading updates
  const { connect, connectionStatus } = useWebSocket({
    autoConnect: true,
    subscribeToMarketData: true,
    subscribeToTradingUpdates: true,
    subscribeToSignals: true,
    subscribeToSystemUpdates: true,
    symbols: ['EURUSD', 'GBPUSD', 'USDJPY', 'USDCHF', 'AUDUSD']
  });

  const handleRefresh = async () => {
    setIsRefreshing(true);
    try {
      if (!isConnected) {
        await connect();
      }
      // Force refresh data
      await new Promise(resolve => setTimeout(resolve, 1000));
    } finally {
      setIsRefreshing(false);
    }
  };

  const totalPnL = getTotalPnL();
  const marginUsed = accountInfo?.marginUsed || 0;
  const marginAvailable = accountInfo?.availableMargin || 0;
  const activeOrdersCount = orders.filter(o => o.status === 'pending' || o.status === 'partially_filled').length;
  const openPositionsCount = positions.length;

  const accountBalance = accountInfo?.balance || 0;
  const equity = accountInfo?.equity || 0;
  const marginLevel = accountInfo?.marginLevel || 0;

  const getConnectionStatus = () => {
    if (!isConnected) return { color: 'text-red-400', bg: 'bg-red-500/20', text: 'Disconnected' };
    if (connectionStatus === 'connecting') return { color: 'text-yellow-400', bg: 'bg-yellow-500/20', text: 'Connecting...' };
    return { color: 'text-green-400', bg: 'bg-green-500/20', text: 'Connected' };
  };

  const connection = getConnectionStatus();

  return (
    <div data-testid="trading-console" className="h-full flex flex-col">
      {/* Header */}
      <div className="p-6 border-b border-gray-700 bg-gray-900/50">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-2xl font-bold text-white">Trading Console</h1>
            <p className="text-gray-400">Live trading operations and portfolio management</p>
          </div>

          <div className="flex items-center gap-3">
            <div className={`flex items-center gap-2 px-3 py-2 rounded-lg ${connection.bg}`}>
              <div className={`w-2 h-2 rounded-full ${connection.color.replace('text-', 'bg-')}`} />
              <span className={`text-sm ${connection.color}`}>{connection.text}</span>
            </div>

            <Button
              onClick={handleRefresh}
              disabled={isRefreshing}
              variant="outline"
              size="sm"
              className="gap-2"
            >
              <ArrowPathIcon className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
          </div>
        </div>

        {/* Account Summary */}
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
          <div className="bg-gray-800/50 rounded-lg p-3">
            <div className="flex items-center gap-2 mb-1">
              <CurrencyDollarIcon className="w-4 h-4 text-blue-400" />
              <span className="text-xs text-gray-400">Balance</span>
            </div>
            <div data-testid="account-balance" className="text-lg font-bold text-white">
              {formatCurrency(accountBalance)}
            </div>
          </div>

          <div className="bg-gray-800/50 rounded-lg p-3">
            <div className="flex items-center gap-2 mb-1">
              <ChartBarSquareIcon className="w-4 h-4 text-purple-400" />
              <span className="text-xs text-gray-400">Equity</span>
            </div>
            <div data-testid="account-equity" className="text-lg font-bold text-white">
              {formatCurrency(equity)}
            </div>
          </div>

          <div className="bg-gray-800/50 rounded-lg p-3">
            <div className="flex items-center gap-2 mb-1">
              <BoltIcon className="w-4 h-4 text-yellow-400" />
              <span className="text-xs text-gray-400">P&L</span>
            </div>
            <div className={`text-lg font-bold ${totalPnL >= 0 ? 'text-green-400' : 'text-red-400'}`}>
              {totalPnL >= 0 ? '+' : ''}{formatCurrency(totalPnL)}
            </div>
          </div>

          <div className="bg-gray-800/50 rounded-lg p-3">
            <div className="flex items-center gap-2 mb-1">
              <ShieldCheckIcon className="w-4 h-4 text-orange-400" />
              <span className="text-xs text-gray-400">Margin Used</span>
            </div>
            <div data-testid="margin-used" className="text-lg font-bold text-white">
              {formatCurrency(marginUsed)}
            </div>
          </div>

          <div className="bg-gray-800/50 rounded-lg p-3">
            <div className="flex items-center gap-2 mb-1">
              <ExclamationTriangleIcon className="w-4 h-4 text-green-400" />
              <span className="text-xs text-gray-400">Margin Free</span>
            </div>
            <div data-testid="available-margin" className="text-lg font-bold text-white">
              {formatCurrency(marginAvailable)}
            </div>
          </div>

          <div className="bg-gray-800/50 rounded-lg p-3">
            <div className="flex items-center gap-2 mb-1">
              <DocumentTextIcon className="w-4 h-4 text-indigo-400" />
              <span className="text-xs text-gray-400">Margin Level</span>
            </div>
            <div className={`text-lg font-bold ${marginLevel > 100 ? 'text-green-400' : marginLevel > 50 ? 'text-yellow-400' : 'text-red-400'}`}>
              {marginLevel.toFixed(0)}%
            </div>
          </div>
        </div>

        {/* Quick Stats */}
        <div className="flex items-center gap-6 mt-4 text-sm text-gray-400">
          <div>Open Positions: <span className="text-white font-medium">{openPositionsCount}</span></div>
          <div>Active Orders: <span className="text-white font-medium">{activeOrdersCount}</span></div>
          <div>Last Update: <span className="text-white font-medium">
            {lastUpdateTime ? new Date(lastUpdateTime).toLocaleTimeString() : '--'}
          </span></div>
        </div>

        {/* Risk Warning */}
        {marginLevel < 100 && marginLevel > 0 && (
          <div className="mt-4 p-3 bg-red-900/20 border border-red-500/30 rounded-lg flex items-center gap-2">
            <ExclamationTriangleIcon className="w-5 h-5 text-red-400 flex-shrink-0" />
            <span className="text-red-400 text-sm">
              {marginLevel < 50
                ? 'Critical: Margin level is very low. Positions may be closed automatically.'
                : 'Warning: Margin level is below recommended threshold.'
              }
            </span>
          </div>
        )}
      </div>

      {/* Main Content */}
      <div className="flex-1 p-3 md:p-6">
        <div className="flex flex-col lg:grid lg:grid-cols-12 gap-6 h-full">
          {/* Mobile-first: Stack panels vertically on mobile, side-by-side on desktop */}

          {/* Order Panel - Hidden on mobile by default, accessible via modal */}
          <div className="hidden lg:block lg:col-span-3 order-1 lg:order-none">
            <OrderPanel />
          </div>

          {/* Main Content Panel */}
          <div className="flex-1 lg:col-span-9 order-2 lg:order-none">
            <Tabs value={activeTab} onValueChange={setActiveTab} className="h-full flex flex-col">
              <div className="overflow-x-auto -mx-3 md:mx-0">
                <TabsList className="grid w-max md:w-full grid-cols-4 bg-gray-800 mx-3 md:mx-0 gap-1 p-1">
                  <TabsTrigger value="overview" className="gap-1 md:gap-2 px-3 md:px-4 py-2 text-sm whitespace-nowrap">
                    <ChartBarSquareIcon className="w-4 h-4 flex-shrink-0" />
                    <span className="hidden sm:inline">Overview</span>
                    <span className="sm:hidden">View</span>
                  </TabsTrigger>
                  <TabsTrigger value="positions" className="gap-1 md:gap-2 px-3 md:px-4 py-2 text-sm whitespace-nowrap">
                    <CurrencyDollarIcon className="w-4 h-4 flex-shrink-0" />
                    <span className="hidden sm:inline">Positions ({openPositionsCount})</span>
                    <span className="sm:hidden">Pos</span>
                  </TabsTrigger>
                  <TabsTrigger value="orders" className="gap-1 md:gap-2 px-3 md:px-4 py-2 text-sm whitespace-nowrap">
                    <DocumentTextIcon className="w-4 h-4 flex-shrink-0" />
                    <span className="hidden sm:inline">Orders ({activeOrdersCount})</span>
                    <span className="sm:hidden">Orders</span>
                  </TabsTrigger>
                  <TabsTrigger value="market" className="gap-1 md:gap-2 px-3 md:px-4 py-2 text-sm whitespace-nowrap">
                    <BoltIcon className="w-4 h-4 flex-shrink-0" />
                    <span className="hidden sm:inline">Market Data</span>
                    <span className="sm:hidden">Market</span>
                  </TabsTrigger>
                </TabsList>
              </div>

              <div className="flex-1 mt-6">
                <TabsContent value="overview" className="h-full">
                  <div className="grid grid-rows-2 gap-6 h-full">
                    <PositionsTable />
                    <OrdersTable />
                  </div>
                </TabsContent>

                <TabsContent value="positions" className="h-full">
                  <PositionsTable className="h-full" />
                </TabsContent>

                <TabsContent value="orders" className="h-full">
                  <OrdersTable showAll={true} className="h-full" />
                </TabsContent>

                <TabsContent value="market" className="h-full">
                  <MarketDataGrid
                    symbols={['EURUSD', 'GBPUSD', 'USDJPY', 'USDCHF', 'AUDUSD', 'USDCAD']}
                    showSpread={true}
                    showVolume={false}
                    className="h-full"
                  />
                </TabsContent>
              </div>
            </Tabs>
          </div>
        </div>
      </div>

      {/* Mobile Order Panel Modal */}
      {showMobileOrderPanel && (
        <>
          <div
            className="fixed inset-0 bg-black/50 z-40 lg:hidden"
            onClick={() => setShowMobileOrderPanel(false)}
          />
          <div className="fixed inset-x-0 bottom-0 z-50 bg-gray-900 border-t border-gray-700 rounded-t-xl lg:hidden transform transition-transform duration-300">
            <div className="p-4 border-b border-gray-700 flex items-center justify-between">
              <h3 className="text-lg font-semibold text-white">Quick Order</h3>
              <button
                onClick={() => setShowMobileOrderPanel(false)}
                className="p-2 text-gray-400 hover:text-white hover:bg-gray-800 rounded-lg transition-colors"
              >
                ×
              </button>
            </div>
            <div className="max-h-96 overflow-y-auto">
              <OrderPanel />
            </div>
          </div>
        </>
      )}

      {/* Mobile Floating Action Button for Order Entry */}
      <button
        onClick={() => setShowMobileOrderPanel(true)}
        className="fixed bottom-6 right-6 z-30 lg:hidden w-14 h-14 bg-blue-600 hover:bg-blue-700 text-white rounded-full shadow-lg hover:shadow-xl transition-all duration-200 flex items-center justify-center"
        aria-label="Open order panel"
      >
        <CurrencyDollarIcon className="w-6 h-6" />
      </button>
    </div>
  );
}
