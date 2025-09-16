/**
 * Header Component
 *
 * Top header with mobile menu toggle and status indicators
 */

'use client';

import { useState, useEffect } from 'react';
import { useAppStore } from '@/stores/useAppStore';
import { useMarketDataStore } from '@/stores/useMarketDataStore';
import { useTradingStore } from '@/stores/useTradingStore';
import { formatCurrency } from '@/lib/utils';
import {
  Bars3Icon,
  BellIcon,
  WifiIcon,
  SignalIcon,
  CurrencyDollarIcon
} from '@heroicons/react/24/outline';

export default function Header() {
  const { setSidebarOpen, isConnected: appConnected, notifications } = useAppStore();
  const { isConnected: marketConnected, marketData } = useMarketDataStore();
  const { accountInfo, positions, getTotalPnL } = useTradingStore();

  // Fix hydration issue by only showing time on client
  const [currentTime, setCurrentTime] = useState<string>('');
  const [isClient, setIsClient] = useState(false);

  useEffect(() => {
    setIsClient(true);
    const updateTime = () => setCurrentTime(new Date().toLocaleTimeString());
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  const unreadCount = notifications.filter(n => !n.read).length;
  const totalPnL = getTotalPnL();

  const getConnectionStatus = () => {
    if (!appConnected || !marketConnected) {
      return { color: 'text-red-400', bg: 'bg-red-500/20', text: 'Disconnected' };
    }
    return { color: 'text-green-400', bg: 'bg-green-500/20', text: 'Live' };
  };

  const connection = getConnectionStatus();

  return (
    <header className="sticky top-0 z-30 bg-gray-950/95 backdrop-blur supports-[backdrop-filter]:bg-gray-950/75 border-b border-gray-800">
      <div className="px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Left section - Mobile menu toggle */}
          <div className="flex items-center gap-4">
            <button
              onClick={() => setSidebarOpen(true)}
              className="p-2 text-gray-400 hover:text-white hover:bg-gray-800 rounded-lg transition-colors lg:hidden"
            >
              <Bars3Icon className="w-5 h-5" />
            </button>

            {/* Connection status */}
            <div className={`flex items-center gap-2 px-3 py-1.5 rounded-lg ${connection.bg}`}>
              <div className={`w-2 h-2 rounded-full ${connection.color.replace('text-', 'bg-')}`} />
              <WifiIcon className={`w-4 h-4 ${connection.color}`} />
              <span className={`text-sm font-medium ${connection.color}`}>
                {connection.text}
              </span>
            </div>
          </div>

          {/* Center section - Trading stats */}
          <div className="hidden md:flex items-center gap-6">
            {/* Market data status */}
            <div className="flex items-center gap-2 text-sm">
              <SignalIcon className="w-4 h-4 text-blue-400" />
              <span className="text-gray-300">
                {Object.keys(marketData).length} symbols
              </span>
            </div>

            {/* Account balance */}
            {accountInfo && (
              <div className="flex items-center gap-2 text-sm">
                <CurrencyDollarIcon className="w-4 h-4 text-green-400" />
                <span className="text-gray-300">
                  Balance: <span className="font-mono text-white">{formatCurrency(accountInfo.balance)}</span>
                </span>
              </div>
            )}

            {/* Total P&L */}
            {positions.length > 0 && (
              <div className="flex items-center gap-2 text-sm">
                <span className="text-gray-300">P&L:</span>
                <span className={`font-mono font-medium ${
                  totalPnL >= 0 ? 'text-green-400' : 'text-red-400'
                }`}>
                  {totalPnL >= 0 ? '+' : ''}{formatCurrency(totalPnL)}
                </span>
              </div>
            )}
          </div>

          {/* Right section - Notifications and user menu */}
          <div className="flex items-center gap-4">
            {/* Market status */}
            <div className="hidden sm:flex items-center gap-2 text-sm text-gray-400">
              <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
              <span>Market Open</span>
            </div>

            {/* Notifications */}
            <button className="relative p-2 text-gray-400 hover:text-white hover:bg-gray-800 rounded-lg transition-colors">
              <BellIcon className="w-5 h-5" />
              {unreadCount > 0 && (
                <div className="absolute -top-1 -right-1 w-5 h-5 bg-red-500 text-white text-xs rounded-full flex items-center justify-center">
                  {unreadCount > 9 ? '9+' : unreadCount}
                </div>
              )}
            </button>

            {/* Current time */}
            <div className="hidden sm:block text-sm text-gray-400 font-mono">
              {isClient ? currentTime : '00:00:00'}
            </div>
          </div>
        </div>
      </div>
    </header>
  );
}
