/**
 * App Layout Component
 *
 * Main layout wrapper with sidebar and header
 */

'use client';

import { useEffect, useState } from 'react';
import { EventEmitter } from 'events';
import { useAppStore } from '@/stores/useAppStore';
import { useWebSocket } from '@/hooks/useWebSocket';
import { getNotificationService } from '@/services/notification';
import Sidebar from './Sidebar';
import Header from './Header';
import NotificationCenter from '../notifications';

interface AppLayoutProps {
  children: React.ReactNode;
}

export default function AppLayout({ children }: AppLayoutProps) {
  const { sidebarCollapsed, theme } = useAppStore();
  const [notificationServiceReady, setNotificationServiceReady] = useState(false);

  // Initialize NotificationService on client side
  useEffect(() => {
    if (typeof window !== 'undefined') {
      try {
        // Initialize notification service with default config
        const eventBus = new EventEmitter();

        getNotificationService({
          eventBus,
          defaultAutoDismissTimeout: 10000,
          maxNotifications: 1000
        });

        setNotificationServiceReady(true);
        console.log('NotificationService initialized successfully');
      } catch (error) {
        // Service may already be initialized, which is fine
        console.debug('NotificationService already initialized:', error);
        setNotificationServiceReady(true);
      }
    }
  }, []);

  // Initialize WebSocket connection for global app state (disabled for now)
  useWebSocket({
    autoConnect: false, // Disable until WebSocket server is running
    subscribeToSystemUpdates: false,
    subscribeToSignals: false
  });

  // Apply theme to document
  useEffect(() => {
    const root = document.documentElement;
    root.classList.remove('light', 'dark');

    if (theme === 'system') {
      const systemTheme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
      root.classList.add(systemTheme);
    } else {
      root.classList.add(theme);
    }
  }, [theme]);

  // Handle keyboard shortcuts
  useEffect(() => {
    const handleKeyboard = (e: KeyboardEvent) => {
      // Cmd/Ctrl + K for command palette (future)
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        // Open command palette
      }

      // Cmd/Ctrl + B for sidebar toggle
      if ((e.metaKey || e.ctrlKey) && e.key === 'b') {
        e.preventDefault();
        useAppStore.getState().toggleSidebar();
      }
    };

    window.addEventListener('keydown', handleKeyboard);
    return () => window.removeEventListener('keydown', handleKeyboard);
  }, []);

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      <Sidebar />

      <div className={`transition-all duration-300 ${
        sidebarCollapsed ? 'lg:ml-16' : 'lg:ml-64'
      }`}>
        <Header />

        <main className="relative">
          {children}
        </main>
      </div>

      {notificationServiceReady && <NotificationCenter />}
    </div>
  );
}
