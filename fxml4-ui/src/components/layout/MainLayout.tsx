/**
 * Main layout component for the trading platform
 *
 * Provides the overall structure with sidebar navigation,
 * header, and main content area
 */

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import {
  Bars3Icon,
  XMarkIcon,
  ChartBarIcon,
  CurrencyDollarIcon,
  CpuChipIcon,
  ClockIcon,
  Cog6ToothIcon,
  HomeIcon,
  BellIcon,
  UserCircleIcon,
} from '@heroicons/react/24/outline';
import { clsx } from 'clsx';

import { APP_CONFIG, ROUTES } from '@/config/constants';
import { wsService } from '@/services/websocket';
import type { NavigationItem } from '@/types';

interface MainLayoutProps {
  children: React.ReactNode;
  title?: string;
  showSidebar?: boolean;
}

const navigation: NavigationItem[] = [
  {
    id: 'dashboard',
    label: 'Dashboard',
    icon: 'HomeIcon',
    path: ROUTES.home,
  },
  {
    id: 'data',
    label: 'Data Management',
    icon: 'ChartBarIcon',
    path: ROUTES.data.index,
    children: [
      { id: 'market-data', label: 'Market Data', icon: '', path: ROUTES.data.marketData },
      { id: 'history', label: 'Historical Data', icon: '', path: ROUTES.data.history },
      { id: 'feeds', label: 'Data Feeds', icon: '', path: ROUTES.data.feeds },
      { id: 'quality', label: 'Data Quality', icon: '', path: ROUTES.data.quality },
    ],
  },
  {
    id: 'trading',
    label: 'Live Trading',
    icon: 'CurrencyDollarIcon',
    path: ROUTES.trading.index,
    children: [
      { id: 'trading-dashboard', label: 'Trading Dashboard', icon: '', path: ROUTES.trading.dashboard },
      { id: 'orders', label: 'Orders', icon: '', path: ROUTES.trading.orders },
      { id: 'positions', label: 'Positions', icon: '', path: ROUTES.trading.positions },
      { id: 'signals', label: 'Signals', icon: '', path: ROUTES.trading.signals },
      { id: 'risk', label: 'Risk Management', icon: '', path: ROUTES.trading.risk },
    ],
  },
  {
    id: 'training',
    label: 'ML Training',
    icon: 'CpuChipIcon',
    path: ROUTES.training.index,
    children: [
      { id: 'models', label: 'Models', icon: '', path: ROUTES.training.models },
      { id: 'datasets', label: 'Datasets', icon: '', path: ROUTES.training.datasets },
      { id: 'experiments', label: 'Experiments', icon: '', path: ROUTES.training.experiments },
      { id: 'deployment', label: 'Deployment', icon: '', path: ROUTES.training.deployment },
    ],
  },
  {
    id: 'backtesting',
    label: 'Backtesting',
    icon: 'ClockIcon',
    path: ROUTES.backtesting.index,
    children: [
      { id: 'strategies', label: 'Strategies', icon: '', path: ROUTES.backtesting.strategies },
      { id: 'results', label: 'Results', icon: '', path: ROUTES.backtesting.results },
      { id: 'optimization', label: 'Optimization', icon: '', path: ROUTES.backtesting.optimization },
      { id: 'reports', label: 'Reports', icon: '', path: ROUTES.backtesting.reports },
    ],
  },
];

const iconComponents: Record<string, React.ComponentType<{ className?: string }>> = {
  HomeIcon,
  ChartBarIcon,
  CurrencyDollarIcon,
  CpuChipIcon,
  ClockIcon,
  Cog6ToothIcon,
};

export default function MainLayout({
  children,
  title,
  showSidebar = true
}: MainLayoutProps) {
  const router = useRouter();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [expandedItems, setExpandedItems] = useState<Set<string>>(new Set());
  const [connectionStatus, setConnectionStatus] = useState<string>('disconnected');
  const [notifications, setNotifications] = useState(0);

  useEffect(() => {
    // Set up WebSocket connection status monitoring
    const unsubscribeConnected = wsService.on('connected', () => {
      setConnectionStatus('connected');
    });

    const unsubscribeDisconnected = wsService.on('disconnected', () => {
      setConnectionStatus('disconnected');
    });

    const unsubscribeError = wsService.on('error', () => {
      setConnectionStatus('error');
    });

    // Initialize connection status
    setConnectionStatus(wsService.getConnectionState());

    return () => {
      unsubscribeConnected();
      unsubscribeDisconnected();
      unsubscribeError();
    };
  }, []);

  useEffect(() => {
    // Auto-expand current navigation item
    const currentPath = router.pathname;
    for (const item of navigation) {
      if (item.children) {
        const hasActiveChild = item.children.some(child =>
          currentPath.startsWith(child.path)
        );
        if (hasActiveChild) {
          setExpandedItems(prev => new Set([...prev, item.id]));
        }
      }
    }
  }, [router.pathname]);

  const toggleExpanded = (itemId: string) => {
    setExpandedItems(prev => {
      const newSet = new Set(prev);
      if (newSet.has(itemId)) {
        newSet.delete(itemId);
      } else {
        newSet.add(itemId);
      }
      return newSet;
    });
  };

  const isActive = (path: string): boolean => {
    if (path === '/') {
      return router.pathname === '/';
    }
    return router.pathname.startsWith(path);
  };

  const getStatusColor = () => {
    switch (connectionStatus) {
      case 'connected':
        return 'bg-green-500';
      case 'error':
        return 'bg-red-500';
      default:
        return 'bg-yellow-500';
    }
  };

  const sidebarContent = (
    <div className="flex flex-col h-full">
      {/* Logo */}
      <div className="flex items-center justify-between h-16 px-4 border-b border-gray-200 dark:border-gray-700">
        <div className="flex items-center space-x-2">
          <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center">
            <span className="text-white font-bold text-sm">FX</span>
          </div>
          <span className="font-semibold text-gray-900 dark:text-white">
            FXML4
          </span>
        </div>
        {sidebarOpen && (
          <button
            onClick={() => setSidebarOpen(false)}
            className="lg:hidden p-1 rounded-md text-gray-400 hover:text-gray-500"
          >
            <XMarkIcon className="h-6 w-6" />
          </button>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-4 py-4 space-y-2 overflow-y-auto custom-scrollbar">
        {navigation.map((item) => {
          const IconComponent = iconComponents[item.icon];
          const isItemActive = isActive(item.path);
          const isExpanded = expandedItems.has(item.id);

          return (
            <div key={item.id}>
              <button
                onClick={() => {
                  if (item.children) {
                    toggleExpanded(item.id);
                  } else {
                    router.push(item.path);
                    setSidebarOpen(false);
                  }
                }}
                className={clsx(
                  'w-full flex items-center justify-between px-3 py-2 rounded-lg text-left transition-colors',
                  isItemActive
                    ? 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-200'
                    : 'text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700'
                )}
              >
                <div className="flex items-center space-x-3">
                  {IconComponent && (
                    <IconComponent className="h-5 w-5 flex-shrink-0" />
                  )}
                  <span className="font-medium">{item.label}</span>
                  {item.badge && (
                    <span className="bg-red-500 text-white text-xs rounded-full px-2 py-0.5 min-w-[20px] text-center">
                      {item.badge}
                    </span>
                  )}
                </div>
                {item.children && (
                  <div className={clsx(
                    'transition-transform',
                    isExpanded ? 'rotate-90' : 'rotate-0'
                  )}>
                    <svg className="h-4 w-4" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clipRule="evenodd" />
                    </svg>
                  </div>
                )}
              </button>

              {/* Submenu */}
              {item.children && isExpanded && (
                <div className="ml-8 mt-1 space-y-1">
                  {item.children.map((child) => (
                    <button
                      key={child.id}
                      onClick={() => {
                        router.push(child.path);
                        setSidebarOpen(false);
                      }}
                      className={clsx(
                        'w-full flex items-center px-3 py-2 rounded-lg text-left text-sm transition-colors',
                        isActive(child.path)
                          ? 'bg-blue-50 text-blue-700 dark:bg-blue-900/50 dark:text-blue-200'
                          : 'text-gray-600 hover:bg-gray-50 dark:text-gray-400 dark:hover:bg-gray-700/50'
                      )}
                    >
                      {child.label}
                    </button>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </nav>

      {/* Footer with connection status */}
      <div className="border-t border-gray-200 dark:border-gray-700 p-4">
        <div className="flex items-center justify-between text-sm">
          <div className="flex items-center space-x-2">
            <div className={`w-2 h-2 rounded-full ${getStatusColor()}`} />
            <span className="text-gray-600 dark:text-gray-400 capitalize">
              {connectionStatus}
            </span>
          </div>
          <div className="text-gray-500 dark:text-gray-400 text-xs">
            v{APP_CONFIG.version}
          </div>
        </div>
      </div>
    </div>
  );

  if (!showSidebar) {
    return <div className="min-h-screen bg-gray-50 dark:bg-gray-900">{children}</div>;
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 flex">
      {/* Mobile sidebar */}
      <div className={clsx(
        'fixed inset-0 z-50 lg:hidden',
        sidebarOpen ? 'block' : 'hidden'
      )}>
        <div className="fixed inset-0 bg-gray-600 bg-opacity-75" onClick={() => setSidebarOpen(false)} />
        <div className="fixed inset-y-0 left-0 w-64 bg-white dark:bg-gray-800 shadow-xl">
          {sidebarContent}
        </div>
      </div>

      {/* Desktop sidebar */}
      <div className="hidden lg:flex lg:flex-shrink-0">
        <div className="w-64 bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700">
          {sidebarContent}
        </div>
      </div>

      {/* Main content */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <header className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 h-16 flex items-center justify-between px-4 lg:px-6">
          <div className="flex items-center space-x-4">
            <button
              onClick={() => setSidebarOpen(true)}
              className="lg:hidden p-2 rounded-md text-gray-400 hover:text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-700"
            >
              <Bars3Icon className="h-6 w-6" />
            </button>
            {title && (
              <h1 className="text-xl font-semibold text-gray-900 dark:text-white">
                {title}
              </h1>
            )}
          </div>

          <div className="flex items-center space-x-4">
            {/* Notifications */}
            <button className="relative p-2 rounded-md text-gray-400 hover:text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-700">
              <BellIcon className="h-6 w-6" />
              {notifications > 0 && (
                <span className="absolute top-0 right-0 block h-4 w-4 rounded-full bg-red-400 text-xs text-white text-center leading-4">
                  {notifications > 9 ? '9+' : notifications}
                </span>
              )}
            </button>

            {/* User menu */}
            <button className="flex items-center space-x-2 p-2 rounded-md text-gray-400 hover:text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-700">
              <UserCircleIcon className="h-6 w-6" />
              <span className="hidden sm:block text-sm font-medium text-gray-700 dark:text-gray-300">
                Trading User
              </span>
            </button>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-auto">
          {children}
        </main>
      </div>
    </div>
  );
}
