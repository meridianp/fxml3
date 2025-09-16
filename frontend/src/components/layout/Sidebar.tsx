/**
 * Sidebar Navigation Component
 *
 * Main navigation sidebar with collapsible design
 */

'use client';

import { useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useAppStore } from '@/stores/useAppStore';
import ThemeToggle from '@/components/ui/ThemeToggle';
import {
  HomeIcon,
  ChartBarIcon,
  RocketLaunchIcon,
  BeakerIcon,
  CurrencyDollarIcon,
  WifiIcon,
  CursorArrowRaysIcon,
  PresentationChartLineIcon,
  Cog6ToothIcon,
  UserCircleIcon,
  QuestionMarkCircleIcon,
  Bars3Icon,
  XMarkIcon,
  BellIcon,
  ArrowRightOnRectangleIcon
} from '@heroicons/react/24/outline';
import {
  HomeIcon as HomeIconSolid,
  ChartBarIcon as ChartBarIconSolid,
  RocketLaunchIcon as RocketLaunchIconSolid,
  BeakerIcon as BeakerIconSolid,
  CurrencyDollarIcon as CurrencyDollarIconSolid,
  WifiIcon as WifiIconSolid,
  CursorArrowRaysIcon as CursorArrowRaysIconSolid,
  PresentationChartLineIcon as PresentationChartLineIconSolid,
} from '@heroicons/react/24/solid';

interface NavigationItem {
  name: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  iconSolid: React.ComponentType<{ className?: string }>;
  badge?: string;
  description: string;
}

const navigation: NavigationItem[] = [
  {
    name: 'Dashboard',
    href: '/dashboard',
    icon: HomeIcon,
    iconSolid: HomeIconSolid,
    description: 'Overview and quick access'
  },
  {
    name: 'Data',
    href: '/data',
    icon: WifiIcon,
    iconSolid: WifiIconSolid,
    description: 'Market data and feeds'
  },
  {
    name: 'Training',
    href: '/training',
    icon: RocketLaunchIcon,
    iconSolid: RocketLaunchIconSolid,
    description: 'ML model training'
  },
  {
    name: 'Analytics',
    href: '/analytics',
    icon: PresentationChartLineIcon,
    iconSolid: PresentationChartLineIconSolid,
    description: 'Performance & wave analysis'
  },
  {
    name: 'Elliott Waves',
    href: '/elliott-waves',
    icon: CursorArrowRaysIcon,
    iconSolid: CursorArrowRaysIconSolid,
    description: 'AI-enhanced wave analysis'
  },
  {
    name: 'Backtesting',
    href: '/backtesting',
    icon: BeakerIcon,
    iconSolid: BeakerIconSolid,
    description: 'Strategy backtests'
  },
  {
    name: 'Trading',
    href: '/trading',
    icon: CurrencyDollarIcon,
    iconSolid: CurrencyDollarIconSolid,
    badge: '5',
    description: 'Live trading console'
  },
];

const secondaryNavigation = [
  {
    name: 'Settings',
    href: '/settings',
    icon: Cog6ToothIcon,
    description: 'Platform configuration'
  },
  {
    name: 'Profile',
    href: '/profile',
    icon: UserCircleIcon,
    description: 'User account settings'
  },
  {
    name: 'Help',
    href: '/help',
    icon: QuestionMarkCircleIcon,
    description: 'Documentation and support'
  },
];

export default function Sidebar() {
  const pathname = usePathname();
  const { sidebarCollapsed, toggleSidebar, sidebarOpen, setSidebarOpen, getUnreadNotificationCount } = useAppStore();
  const unreadCount = getUnreadNotificationCount();

  const isCurrentPage = (href: string) => {
    if (href === '/dashboard') {
      return pathname === '/' || pathname === '/dashboard';
    }
    return pathname.startsWith(href);
  };

  return (
    <>
      {/* Mobile sidebar backdrop */}
      <div
        className={`fixed inset-0 bg-black/50 z-40 lg:hidden transition-opacity duration-300 ${
          sidebarOpen ? 'opacity-100' : 'opacity-0 pointer-events-none'
        }`}
        onClick={() => setSidebarOpen(false)}
      />

      {/* Sidebar */}
      <div
        data-testid="sidebar"
        className={`
          sidebar fixed inset-y-0 left-0 z-50 bg-gray-900 border-r border-gray-700
          transition-all duration-300 ease-in-out
          ${sidebarCollapsed ? 'w-16' : 'w-64'}
          ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
          lg:translate-x-0
        `}>
        <div className="flex flex-col h-full">
          {/* Header */}
          <div className="flex items-center justify-between p-4 border-b border-gray-700">
            {!sidebarCollapsed && (
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-purple-600 rounded-lg flex items-center justify-center">
                  <span className="text-white font-bold text-sm">FX</span>
                </div>
                <div>
                  <h1 className="text-white font-semibold text-lg">FXML4</h1>
                  <p className="text-gray-400 text-xs">Trading Platform</p>
                </div>
              </div>
            )}

            {/* Toggle button */}
            <button
              onClick={toggleSidebar}
              className="p-1.5 text-gray-400 hover:text-white hover:bg-gray-800 rounded-lg transition-colors hidden lg:flex"
            >
              {sidebarCollapsed ? (
                <Bars3Icon className="w-5 h-5" />
              ) : (
                <XMarkIcon className="w-5 h-5" />
              )}
            </button>

            {/* Mobile close button */}
            <button
              onClick={() => setSidebarOpen(false)}
              className="p-1.5 text-gray-400 hover:text-white hover:bg-gray-800 rounded-lg transition-colors lg:hidden"
            >
              <XMarkIcon className="w-5 h-5" />
            </button>
          </div>

          {/* Navigation */}
          <nav role="navigation" className="flex-1 px-4 py-6 space-y-2 overflow-y-auto">
            {/* Primary Navigation */}
            <div className="space-y-1">
              {navigation.map((item) => {
                const isActive = isCurrentPage(item.href);
                const Icon = isActive ? item.iconSolid : item.icon;

                return (
                  <Link
                    key={item.name}
                    href={item.href}
                    className={`
                      group flex items-center gap-3 px-3 py-2.5 rounded-lg
                      transition-all duration-200
                      ${isActive
                        ? 'bg-blue-600 text-white shadow-lg shadow-blue-600/25'
                        : 'text-gray-300 hover:text-white hover:bg-gray-800'
                      }
                      ${sidebarCollapsed ? 'justify-center' : ''}
                    `}
                    title={sidebarCollapsed ? item.description : ''}
                  >
                    <div className="relative">
                      <Icon className="w-5 h-5 flex-shrink-0" />
                      {item.badge && (
                        <div className="absolute -top-2 -right-2 w-4 h-4 bg-red-500 text-white text-xs rounded-full flex items-center justify-center">
                          {item.badge}
                        </div>
                      )}
                    </div>

                    {!sidebarCollapsed && (
                      <div className="flex-1 min-w-0">
                        <span className="font-medium">{item.name}</span>
                        {!isActive && (
                          <p className="text-xs text-gray-500 group-hover:text-gray-400 truncate">
                            {item.description}
                          </p>
                        )}
                      </div>
                    )}
                  </Link>
                );
              })}
            </div>

            {/* Divider */}
            <div className="border-t border-gray-700 my-6" />

            {/* Secondary Navigation */}
            <div className="space-y-1">
              {secondaryNavigation.map((item) => {
                const isActive = isCurrentPage(item.href);

                return (
                  <Link
                    key={item.name}
                    href={item.href}
                    className={`
                      group flex items-center gap-3 px-3 py-2.5 rounded-lg
                      transition-all duration-200
                      ${isActive
                        ? 'bg-gray-800 text-white'
                        : 'text-gray-400 hover:text-white hover:bg-gray-800'
                      }
                      ${sidebarCollapsed ? 'justify-center' : ''}
                    `}
                    title={sidebarCollapsed ? item.description : ''}
                  >
                    <item.icon className="w-5 h-5 flex-shrink-0" />
                    {!sidebarCollapsed && (
                      <span className="font-medium">{item.name}</span>
                    )}
                  </Link>
                );
              })}
            </div>
          </nav>

          {/* Footer */}
          <div className="p-4 border-t border-gray-700">
            {!sidebarCollapsed ? (
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 bg-gradient-to-br from-green-500 to-blue-500 rounded-full flex items-center justify-center">
                  <span className="text-white font-bold text-xs">JD</span>
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-white font-medium text-sm truncate">John Doe</p>
                  <p className="text-gray-400 text-xs">Pro Trader</p>
                </div>
                <div className="flex items-center gap-1">
                  <ThemeToggle variant="ghost" size="sm" />
                  <button className="p-1.5 text-gray-400 hover:text-white hover:bg-gray-800 rounded-lg transition-colors relative">
                    <BellIcon className="w-4 h-4" />
                    {unreadCount > 0 && (
                      <div className="absolute -top-1 -right-1 w-3 h-3 bg-red-500 text-white text-xs rounded-full flex items-center justify-center">
                        {unreadCount > 9 ? '9+' : unreadCount}
                      </div>
                    )}
                  </button>
                  <button className="p-1.5 text-gray-400 hover:text-white hover:bg-gray-800 rounded-lg transition-colors">
                    <ArrowRightOnRectangleIcon className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-2">
                <div className="w-8 h-8 bg-gradient-to-br from-green-500 to-blue-500 rounded-full flex items-center justify-center">
                  <span className="text-white font-bold text-xs">JD</span>
                </div>
                <div className="flex flex-col gap-1">
                  <ThemeToggle variant="ghost" size="sm" />
                  <button className="p-1.5 text-gray-400 hover:text-white hover:bg-gray-800 rounded-lg transition-colors relative">
                    <BellIcon className="w-4 h-4" />
                    {unreadCount > 0 && (
                      <div className="absolute -top-1 -right-1 w-3 h-3 bg-red-500 rounded-full" />
                    )}
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
