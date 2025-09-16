import { create } from 'zustand';
import { devtools } from 'zustand/middleware';

export interface AppState {
  // Connection status
  isConnected: boolean;
  connectionStatus: 'connecting' | 'connected' | 'disconnected' | 'error';
  lastConnectionError: string | null;

  // UI state
  sidebarCollapsed: boolean;
  sidebarOpen: boolean;
  activeTab: string;
  theme: 'light' | 'dark';

  // Notifications
  notifications: Notification[];

  // Loading states
  isLoading: boolean;
  loadingMessage: string;

  // System metrics
  systemMetrics: Record<string, any>;
}

export interface Notification {
  id: string;
  type: 'info' | 'success' | 'warning' | 'error';
  title: string;
  message: string;
  timestamp: Date;
  autoClose?: boolean;
}

interface AppActions {
  // Connection actions
  setConnectionStatus: (status: AppState['connectionStatus']) => void;
  setConnectionError: (error: string | null) => void;

  // UI actions
  toggleSidebar: () => void;
  setSidebarOpen: (open: boolean) => void;
  setActiveTab: (tab: string) => void;
  setTheme: (theme: AppState['theme']) => void;

  // Notification actions
  addNotification: (notification: Omit<Notification, 'id' | 'timestamp'>) => void;
  removeNotification: (id: string) => void;
  clearNotifications: () => void;
  getUnreadNotificationCount: () => number;

  // Loading actions
  setLoading: (loading: boolean, message?: string) => void;

  // System metrics actions
  setSystemMetrics: (metrics: Record<string, any> | ((prev: Record<string, any>) => Record<string, any>)) => void;

  // Reset actions
  reset: () => void;
}

const initialState: AppState = {
  isConnected: false,
  connectionStatus: 'disconnected',
  lastConnectionError: null,
  sidebarCollapsed: false,
  sidebarOpen: false,
  activeTab: 'trading',
  theme: 'light',
  notifications: [],
  isLoading: false,
  loadingMessage: '',
  systemMetrics: {},
};

export const useAppStore = create<AppState & AppActions>()(
  devtools(
    (set, get) => ({
      ...initialState,

      // Connection actions
      setConnectionStatus: (status) => {
        set(
          (state) => ({
            connectionStatus: status,
            isConnected: status === 'connected',
            lastConnectionError: status === 'connected' ? null : state.lastConnectionError,
          }),
          false,
          'setConnectionStatus'
        );
      },

      setConnectionError: (error) => {
        set(
          {
            lastConnectionError: error,
            connectionStatus: error ? 'error' : 'disconnected',
            isConnected: false,
          },
          false,
          'setConnectionError'
        );
      },

      // UI actions
      toggleSidebar: () => {
        set(
          (state) => ({ sidebarCollapsed: !state.sidebarCollapsed }),
          false,
          'toggleSidebar'
        );
      },

      setSidebarOpen: (open) => {
        set({ sidebarOpen: open }, false, 'setSidebarOpen');
      },

      setActiveTab: (tab) => {
        set({ activeTab: tab }, false, 'setActiveTab');
      },

      setTheme: (theme) => {
        set({ theme }, false, 'setTheme');
        // Update document class for Tailwind
        if (typeof document !== 'undefined') {
          document.documentElement.classList.toggle('dark', theme === 'dark');
        }
      },

      // Notification actions
      addNotification: (notification) => {
        const id = `notification-${Date.now()}-${Math.random()}`;
        const newNotification: Notification = {
          ...notification,
          id,
          timestamp: new Date(),
          autoClose: notification.autoClose ?? true,
        };

        set(
          (state) => ({
            notifications: [...state.notifications, newNotification],
          }),
          false,
          'addNotification'
        );

        // Auto-remove notification after 5 seconds if autoClose is true
        if (newNotification.autoClose) {
          setTimeout(() => {
            get().removeNotification(id);
          }, 5000);
        }
      },

      removeNotification: (id) => {
        set(
          (state) => ({
            notifications: state.notifications.filter((n) => n.id !== id),
          }),
          false,
          'removeNotification'
        );
      },

      clearNotifications: () => {
        set({ notifications: [] }, false, 'clearNotifications');
      },

      getUnreadNotificationCount: () => {
        return get().notifications.length;
      },

      // Loading actions
      setLoading: (loading, message = '') => {
        set(
          { isLoading: loading, loadingMessage: message },
          false,
          'setLoading'
        );
      },

      // System metrics actions
      setSystemMetrics: (metrics) => {
        set(
          (state) => ({
            systemMetrics: typeof metrics === 'function' ? metrics(state.systemMetrics) : metrics
          }),
          false,
          'setSystemMetrics'
        );
      },

      // Reset actions
      reset: () => {
        set(initialState, false, 'reset');
      },
    }),
    {
      name: 'app-store',
    }
  )
);
