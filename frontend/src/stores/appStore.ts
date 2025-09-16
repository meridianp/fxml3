/**
 * Application Store
 *
 * Manages global application state including UI, theme, and system status
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { Theme, UserPreferences, LoadingState, AppError } from '@/types';
import { STORAGE_KEYS } from '@/config/constants';

interface AppState {
  // Theme and UI
  theme: Theme;
  sidebarCollapsed: boolean;
  sidebarOpen: boolean; // Mobile sidebar

  // Connection status
  isConnected: boolean;
  connectionStatus: 'connected' | 'connecting' | 'disconnected' | 'error';
  lastConnectionTime: number;

  // System status
  systemHealth: 'healthy' | 'warning' | 'error';
  systemMetrics: Record<string, any>;

  // User preferences
  preferences: UserPreferences;

  // Global loading states
  globalLoading: LoadingState;

  // Error handling
  errors: AppError[];
  notifications: Array<{
    id: string;
    type: 'success' | 'error' | 'warning' | 'info';
    title: string;
    message: string;
    timestamp: number;
    read: boolean;
  }>;

  // Actions
  setTheme: (theme: Theme) => void;
  toggleSidebar: () => void;
  setSidebarOpen: (open: boolean) => void;

  setConnectionStatus: (status: 'connected' | 'connecting' | 'disconnected' | 'error') => void;
  setConnected: (connected: boolean) => void;

  setSystemHealth: (health: 'healthy' | 'warning' | 'error') => void;
  setSystemMetrics: (metrics: Record<string, any>) => void;

  setPreferences: (preferences: Partial<UserPreferences>) => void;

  setGlobalLoading: (loading: LoadingState) => void;

  addError: (error: AppError) => void;
  removeError: (errorId: string) => void;
  clearErrors: () => void;

  addNotification: (notification: Omit<AppState['notifications'][0], 'id' | 'timestamp' | 'read'>) => void;
  markNotificationAsRead: (id: string) => void;
  removeNotification: (id: string) => void;
  clearNotifications: () => void;

  // Computed values
  getUnreadNotificationCount: () => number;
  hasErrors: () => boolean;
  isSystemHealthy: () => boolean;
}

const defaultPreferences: UserPreferences = {
  theme: 'dark',
  default_timeframe: '1h',
  favorite_symbols: ['EURUSD', 'GBPUSD', 'USDJPY'],
  dashboard_layout: [],
  notifications: {
    email: true,
    push: true,
    trading_signals: true,
    order_fills: true,
    system_alerts: true,
  },
  risk_settings: {
    max_position_size: 100000,
    max_daily_loss: 1000,
    max_drawdown: 0.05,
    enable_auto_stop_loss: true,
  },
};

export const useAppStore = create<AppState>()(
  persist(
    (set, get) => ({
      // Initial state
      theme: 'dark',
      sidebarCollapsed: false,
      sidebarOpen: false,

      isConnected: false,
      connectionStatus: 'disconnected',
      lastConnectionTime: 0,

      systemHealth: 'healthy',
      systemMetrics: {},

      preferences: defaultPreferences,

      globalLoading: 'idle',

      errors: [],
      notifications: [],

      // Actions
      setTheme: (theme: Theme) => {
        set({ theme });

        // Apply theme to document
        if (typeof window !== 'undefined') {
          const root = window.document.documentElement;
          root.classList.remove('light', 'dark');

          if (theme === 'system') {
            const systemTheme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
            root.classList.add(systemTheme);
          } else {
            root.classList.add(theme);
          }
        }
      },

      toggleSidebar: () => {
        set(state => ({ sidebarCollapsed: !state.sidebarCollapsed }));
      },

      setSidebarOpen: (open: boolean) => {
        set({ sidebarOpen: open });
      },

      setConnectionStatus: (status) => {
        const now = Date.now();
        set({
          connectionStatus: status,
          isConnected: status === 'connected',
          lastConnectionTime: status === 'connected' ? now : get().lastConnectionTime
        });

        // Add system notification for connection changes
        if (status === 'connected') {
          get().addNotification({
            type: 'success',
            title: 'Connected',
            message: 'Successfully connected to trading server'
          });
        } else if (status === 'error') {
          get().addNotification({
            type: 'error',
            title: 'Connection Error',
            message: 'Lost connection to trading server'
          });
        }
      },

      setConnected: (connected: boolean) => {
        set({ isConnected: connected });
      },

      setSystemHealth: (health) => {
        set({ systemHealth: health });

        if (health === 'error') {
          get().addNotification({
            type: 'error',
            title: 'System Alert',
            message: 'Trading system experiencing issues'
          });
        }
      },

      setSystemMetrics: (metrics) => {
        set({ systemMetrics: metrics });
      },

      setPreferences: (newPreferences) => {
        set(state => ({
          preferences: { ...state.preferences, ...newPreferences }
        }));
      },

      setGlobalLoading: (loading) => {
        set({ globalLoading: loading });
      },

      addError: (error) => {
        set(state => ({
          errors: [...state.errors, error].slice(-10) // Keep only last 10 errors
        }));
      },

      removeError: (errorId) => {
        set(state => ({
          errors: state.errors.filter(error => error.code !== errorId)
        }));
      },

      clearErrors: () => {
        set({ errors: [] });
      },

      addNotification: (notification) => {
        const id = Math.random().toString(36).substr(2, 9);
        const newNotification = {
          ...notification,
          id,
          timestamp: Date.now(),
          read: false
        };

        set(state => ({
          notifications: [newNotification, ...state.notifications].slice(0, 50) // Keep only last 50
        }));
      },

      markNotificationAsRead: (id) => {
        set(state => ({
          notifications: state.notifications.map(notif =>
            notif.id === id ? { ...notif, read: true } : notif
          )
        }));
      },

      removeNotification: (id) => {
        set(state => ({
          notifications: state.notifications.filter(notif => notif.id !== id)
        }));
      },

      clearNotifications: () => {
        set({ notifications: [] });
      },

      // Computed values
      getUnreadNotificationCount: () => {
        return get().notifications.filter(notif => !notif.read).length;
      },

      hasErrors: () => {
        return get().errors.length > 0;
      },

      isSystemHealthy: () => {
        return get().systemHealth === 'healthy' && get().isConnected;
      }
    }),
    {
      name: STORAGE_KEYS.userPreferences,
      partialize: (state) => ({
        theme: state.theme,
        sidebarCollapsed: state.sidebarCollapsed,
        preferences: state.preferences,
      }),
    }
  )
);
