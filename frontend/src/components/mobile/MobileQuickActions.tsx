/**
 * Mobile Quick Actions Component
 *
 * Floating action menu optimized for mobile trading workflows
 * Provides quick access to common trading functions with gesture support
 */

'use client';

import { useState, useRef, useEffect } from 'react';
import { useTradingStore } from '@/stores/useTradingStore';
import { useMarketDataStore } from '@/stores/useMarketDataStore';
import { usePushNotifications } from '@/services/pushNotificationService';
import { formatCurrency, formatPercentage } from '@/lib/utils';
import {
  CurrencyDollarIcon,
  ChartBarIcon,
  BellIcon,
  PlusIcon,
  XMarkIcon,
  ClockIcon,
  ExclamationTriangleIcon,
  SignalIcon,
  AdjustmentsHorizontalIcon
} from '@heroicons/react/24/outline';

interface QuickAction {
  id: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  color: string;
  action: () => void;
  badge?: string | number;
  disabled?: boolean;
}

interface MobileQuickActionsProps {
  className?: string;
  onOrderAction?: () => void;
  onAnalyticsAction?: () => void;
  onPositionsAction?: () => void;
  onAlertsAction?: () => void;
}

export default function MobileQuickActions({
  className = '',
  onOrderAction,
  onAnalyticsAction,
  onPositionsAction,
  onAlertsAction
}: MobileQuickActionsProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });

  const fabRef = useRef<HTMLDivElement>(null);
  const { positions, orders, getTotalPnL, accountInfo } = useTradingStore();
  const { isConnected, lastUpdateTime } = useMarketDataStore();
  const { isSupported: notificationSupported, permission } = usePushNotifications();

  // Calculate badge counts
  const openPositions = positions.length;
  const activeOrders = orders.filter(o => o.status === 'pending').length;
  const totalPnL = getTotalPnL();
  const needsAttention = !isConnected || (accountInfo?.marginLevel || 100) < 100;

  // Quick actions configuration
  const quickActions: QuickAction[] = [
    {
      id: 'new-order',
      label: 'New Order',
      icon: CurrencyDollarIcon,
      color: 'bg-blue-600',
      action: () => {
        onOrderAction?.();
        setIsExpanded(false);
      }
    },
    {
      id: 'positions',
      label: 'Positions',
      icon: ChartBarIcon,
      color: 'bg-green-600',
      action: () => {
        onPositionsAction?.();
        setIsExpanded(false);
      },
      badge: openPositions > 0 ? openPositions : undefined
    },
    {
      id: 'analytics',
      label: 'Analytics',
      icon: SignalIcon,
      color: 'bg-purple-600',
      action: () => {
        onAnalyticsAction?.();
        setIsExpanded(false);
      }
    },
    {
      id: 'alerts',
      label: 'Alerts',
      icon: BellIcon,
      color: needsAttention ? 'bg-red-600' : 'bg-gray-600',
      action: () => {
        onAlertsAction?.();
        setIsExpanded(false);
      },
      badge: needsAttention ? '!' : undefined
    }
  ];

  // Handle drag functionality for repositioning the FAB
  const handleTouchStart = (e: React.TouchEvent) => {
    if (!fabRef.current) return;

    const touch = e.touches[0];
    const rect = fabRef.current.getBoundingClientRect();

    setIsDragging(true);
    setDragStart({
      x: touch.clientX - rect.left,
      y: touch.clientY - rect.top
    });
  };

  const handleTouchMove = (e: React.TouchEvent) => {
    if (!isDragging || !fabRef.current) return;

    const touch = e.touches[0];
    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;
    const fabSize = 56; // Size of the FAB

    // Calculate new position with bounds checking
    let newX = touch.clientX - dragStart.x;
    let newY = touch.clientY - dragStart.y;

    // Keep within viewport bounds
    newX = Math.max(20, Math.min(viewportWidth - fabSize - 20, newX));
    newY = Math.max(80, Math.min(viewportHeight - fabSize - 80, newY));

    setPosition({ x: newX, y: newY });
  };

  const handleTouchEnd = () => {
    setIsDragging(false);

    // Snap to edges for better UX
    const viewportWidth = window.innerWidth;
    const fabSize = 56;
    const threshold = viewportWidth * 0.6;

    if (position.x < threshold) {
      setPosition(prev => ({ ...prev, x: 20 }));
    } else {
      setPosition(prev => ({ ...prev, x: viewportWidth - fabSize - 20 }));
    }
  };

  // Auto-collapse after inactivity
  useEffect(() => {
    if (!isExpanded) return;

    const timer = setTimeout(() => {
      setIsExpanded(false);
    }, 10000); // Auto-collapse after 10 seconds

    return () => clearTimeout(timer);
  }, [isExpanded]);

  // Quick status component
  const QuickStatus = () => (
    <div className="fixed top-0 left-0 right-0 z-40 lg:hidden bg-gray-900/95 backdrop-blur border-b border-gray-700 px-4 py-2">
      <div className="flex items-center justify-between text-xs">
        <div className="flex items-center gap-4">
          <div className={`flex items-center gap-1 ${isConnected ? 'text-green-400' : 'text-red-400'}`}>
            <div className={`w-1.5 h-1.5 rounded-full ${isConnected ? 'bg-green-400' : 'bg-red-400'}`} />
            <span>{isConnected ? 'Live' : 'Offline'}</span>
          </div>

          {accountInfo && (
            <div className="text-gray-300">
              Balance: <span className="font-mono">{formatCurrency(accountInfo.balance)}</span>
            </div>
          )}
        </div>

        <div className="flex items-center gap-3">
          {totalPnL !== 0 && (
            <div className={`font-mono ${totalPnL >= 0 ? 'text-green-400' : 'text-red-400'}`}>
              {totalPnL >= 0 ? '+' : ''}{formatCurrency(totalPnL)}
            </div>
          )}

          {lastUpdateTime && (
            <div className="text-gray-500">
              {new Date(lastUpdateTime).toLocaleTimeString()}
            </div>
          )}
        </div>
      </div>
    </div>
  );

  return (
    <>
      <QuickStatus />

      {/* Floating Action Button */}
      <div
        className={`${className} lg:hidden`}
        style={{
          position: 'fixed',
          right: position.x > 0 ? 'auto' : '20px',
          bottom: '20px',
          left: position.x > 0 ? `${position.x}px` : 'auto',
          top: position.y > 0 ? `${position.y}px` : 'auto',
          zIndex: 50
        }}
      >
        {/* Action Menu */}
        {isExpanded && (
          <div className="absolute bottom-20 right-0 flex flex-col items-end gap-3 animate-in slide-in-from-bottom-5 duration-200">
            {quickActions.map((action, index) => (
              <div
                key={action.id}
                className="flex items-center gap-3 animate-in slide-in-from-right-3 duration-200"
                style={{ animationDelay: `${index * 50}ms` }}
              >
                <div className="bg-gray-900/95 backdrop-blur rounded-lg px-3 py-2 text-sm text-white whitespace-nowrap">
                  {action.label}
                </div>

                <button
                  onClick={action.action}
                  disabled={action.disabled}
                  className={`
                    relative w-12 h-12 rounded-full shadow-lg
                    ${action.color} text-white
                    ${action.disabled ? 'opacity-50' : 'hover:scale-105'}
                    transition-all duration-200 flex items-center justify-center
                  `}
                >
                  <action.icon className="w-5 h-5" />

                  {action.badge && (
                    <div className="absolute -top-1 -right-1 w-5 h-5 bg-red-500 text-white text-xs rounded-full flex items-center justify-center font-bold">
                      {action.badge}
                    </div>
                  )}
                </button>
              </div>
            ))}
          </div>
        )}

        {/* Main FAB */}
        <div
          ref={fabRef}
          className={`
            w-14 h-14 rounded-full shadow-xl flex items-center justify-center
            transition-all duration-300 cursor-pointer select-none
            ${isExpanded
              ? 'bg-gray-800 rotate-45 scale-110'
              : totalPnL >= 0
                ? 'bg-gradient-to-br from-blue-600 to-purple-600'
                : 'bg-gradient-to-br from-red-600 to-orange-600'
            }
            ${isDragging ? 'scale-110' : 'hover:scale-105'}
            text-white
          `}
          onTouchStart={handleTouchStart}
          onTouchMove={handleTouchMove}
          onTouchEnd={handleTouchEnd}
          onClick={() => !isDragging && setIsExpanded(!isExpanded)}
        >
          {isExpanded ? (
            <XMarkIcon className="w-6 h-6" />
          ) : (
            <div className="relative">
              <PlusIcon className="w-6 h-6" />

              {/* Activity indicator */}
              {(activeOrders > 0 || needsAttention) && (
                <div className="absolute -top-1 -right-1 w-3 h-3 bg-red-500 rounded-full animate-pulse" />
              )}
            </div>
          )}
        </div>

        {/* Connection status indicator */}
        {!isConnected && (
          <div className="absolute -top-2 -left-2 w-4 h-4 bg-red-500 rounded-full animate-pulse flex items-center justify-center">
            <ExclamationTriangleIcon className="w-2.5 h-2.5 text-white" />
          </div>
        )}
      </div>

      {/* Backdrop for expanded state */}
      {isExpanded && (
        <div
          className="fixed inset-0 bg-black/20 z-40 lg:hidden"
          onClick={() => setIsExpanded(false)}
        />
      )}
    </>
  );
}

// Hook for integrating quick actions with navigation
export function useMobileQuickActions() {
  const [showOrderPanel, setShowOrderPanel] = useState(false);
  const [activeQuickAction, setActiveQuickAction] = useState<string | null>(null);

  const handleOrderAction = () => {
    setShowOrderPanel(true);
    setActiveQuickAction('order');
  };

  const handleAnalyticsAction = () => {
    // Navigate to analytics
    window.location.href = '/analytics';
    setActiveQuickAction('analytics');
  };

  const handlePositionsAction = () => {
    // Show positions modal or navigate
    setActiveQuickAction('positions');
  };

  const handleAlertsAction = () => {
    // Show alerts panel
    setActiveQuickAction('alerts');
  };

  const closeActiveAction = () => {
    setShowOrderPanel(false);
    setActiveQuickAction(null);
  };

  return {
    showOrderPanel,
    activeQuickAction,
    handleOrderAction,
    handleAnalyticsAction,
    handlePositionsAction,
    handleAlertsAction,
    closeActiveAction
  };
}
