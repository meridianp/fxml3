/**
 * Push Notification Service
 *
 * Handles mobile push notifications for trading alerts, position updates,
 * and critical system events with proper permissions and fallbacks
 */

'use client';

export interface NotificationConfig {
  title: string;
  body: string;
  icon?: string;
  badge?: string;
  image?: string;
  tag?: string;
  renotify?: boolean;
  requireInteraction?: boolean;
  silent?: boolean;
  vibrate?: number[];
  actions?: NotificationAction[];
  data?: any;
}

export interface TradingNotification extends NotificationConfig {
  type: 'trade_executed' | 'position_update' | 'risk_alert' | 'market_alert' | 'system_alert';
  priority: 'low' | 'normal' | 'high' | 'critical';
  symbol?: string;
  amount?: number;
  pnl?: number;
}

class PushNotificationService {
  private swRegistration: ServiceWorkerRegistration | null = null;
  private isSupported: boolean = false;
  private permission: NotificationPermission = 'default';

  constructor() {
    this.init();
  }

  private async init() {
    // Check for notification support
    this.isSupported = 'Notification' in window && 'serviceWorker' in navigator;

    if (this.isSupported) {
      this.permission = Notification.permission;

      // Register service worker if not already registered
      if ('serviceWorker' in navigator) {
        try {
          this.swRegistration = await navigator.serviceWorker.ready;
        } catch (error) {
          console.warn('Service Worker not available:', error);
        }
      }
    }
  }

  /**
   * Request notification permissions from the user
   */
  async requestPermission(): Promise<NotificationPermission> {
    if (!this.isSupported) {
      throw new Error('Push notifications not supported');
    }

    if (this.permission === 'granted') {
      return this.permission;
    }

    try {
      const permission = await Notification.requestPermission();
      this.permission = permission;
      return permission;
    } catch (error) {
      console.error('Error requesting notification permission:', error);
      return 'denied';
    }
  }

  /**
   * Check if notifications are supported and permitted
   */
  isAvailable(): boolean {
    return this.isSupported && this.permission === 'granted';
  }

  /**
   * Show a trading-specific notification with enhanced metadata
   */
  async showTradingNotification(notification: TradingNotification): Promise<boolean> {
    if (!this.isAvailable()) {
      console.warn('Notifications not available, falling back to browser alert');
      this.showFallbackNotification(notification);
      return false;
    }

    try {
      // Enhanced notification config for trading
      const config: NotificationConfig = {
        ...notification,
        icon: notification.icon || '/images/icons/icon-192.png',
        badge: notification.badge || '/images/icons/badge.png',
        tag: notification.tag || `trading-${notification.type}`,
        requireInteraction: notification.priority === 'critical',
        vibrate: this.getVibrationPattern(notification.priority),
        actions: notification.actions || this.getDefaultActions(notification.type),
        data: {
          ...notification.data,
          type: notification.type,
          priority: notification.priority,
          timestamp: new Date().toISOString(),
          symbol: notification.symbol,
          amount: notification.amount,
          pnl: notification.pnl
        }
      };

      // Use service worker notification if available
      if (this.swRegistration && this.swRegistration.showNotification) {
        await this.swRegistration.showNotification(config.title, config);
      } else {
        // Fallback to basic notification
        new Notification(config.title, config);
      }

      return true;
    } catch (error) {
      console.error('Error showing notification:', error);
      this.showFallbackNotification(notification);
      return false;
    }
  }

  /**
   * Show a general notification
   */
  async showNotification(config: NotificationConfig): Promise<boolean> {
    if (!this.isAvailable()) {
      console.warn('Notifications not available');
      return false;
    }

    try {
      const enhancedConfig = {
        ...config,
        icon: config.icon || '/images/icons/icon-192.png',
        badge: config.badge || '/images/icons/badge.png'
      };

      if (this.swRegistration && this.swRegistration.showNotification) {
        await this.swRegistration.showNotification(config.title, enhancedConfig);
      } else {
        new Notification(config.title, enhancedConfig);
      }

      return true;
    } catch (error) {
      console.error('Error showing notification:', error);
      return false;
    }
  }

  /**
   * Clear all notifications with a specific tag
   */
  async clearNotifications(tag?: string): Promise<void> {
    if (!this.swRegistration) return;

    try {
      const notifications = await this.swRegistration.getNotifications({ tag });
      notifications.forEach(notification => notification.close());
    } catch (error) {
      console.error('Error clearing notifications:', error);
    }
  }

  /**
   * Get all active notifications
   */
  async getActiveNotifications(tag?: string): Promise<Notification[]> {
    if (!this.swRegistration) return [];

    try {
      return await this.swRegistration.getNotifications({ tag });
    } catch (error) {
      console.error('Error getting notifications:', error);
      return [];
    }
  }

  /**
   * Subscribe to push notifications from server
   */
  async subscribeToPush(serverPublicKey: string): Promise<PushSubscription | null> {
    if (!this.swRegistration) {
      throw new Error('Service Worker not available');
    }

    try {
      const subscription = await this.swRegistration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: this.urlBase64ToUint8Array(serverPublicKey)
      });

      return subscription;
    } catch (error) {
      console.error('Error subscribing to push:', error);
      return null;
    }
  }

  /**
   * Unsubscribe from push notifications
   */
  async unsubscribeFromPush(): Promise<boolean> {
    if (!this.swRegistration) return false;

    try {
      const subscription = await this.swRegistration.pushManager.getSubscription();
      if (subscription) {
        return await subscription.unsubscribe();
      }
      return true;
    } catch (error) {
      console.error('Error unsubscribing from push:', error);
      return false;
    }
  }

  /**
   * Get vibration pattern based on priority
   */
  private getVibrationPattern(priority: TradingNotification['priority']): number[] {
    switch (priority) {
      case 'critical':
        return [200, 100, 200, 100, 200]; // Long vibration pattern
      case 'high':
        return [100, 50, 100]; // Medium vibration
      case 'normal':
        return [100]; // Single vibration
      case 'low':
        return []; // No vibration
      default:
        return [100];
    }
  }

  /**
   * Get default notification actions based on type
   */
  private getDefaultActions(type: TradingNotification['type']): NotificationAction[] {
    switch (type) {
      case 'trade_executed':
        return [
          { action: 'view', title: 'View Trade', icon: '/images/icons/view.png' },
          { action: 'close', title: 'Dismiss', icon: '/images/icons/close.png' }
        ];
      case 'position_update':
        return [
          { action: 'view', title: 'View Position', icon: '/images/icons/view.png' },
          { action: 'close_position', title: 'Close Position', icon: '/images/icons/close-position.png' }
        ];
      case 'risk_alert':
        return [
          { action: 'view', title: 'View Risk', icon: '/images/icons/warning.png' },
          { action: 'acknowledge', title: 'Acknowledge', icon: '/images/icons/check.png' }
        ];
      case 'market_alert':
        return [
          { action: 'view', title: 'View Market', icon: '/images/icons/chart.png' },
          { action: 'trade', title: 'Trade Now', icon: '/images/icons/trade.png' }
        ];
      case 'system_alert':
        return [
          { action: 'view', title: 'View Details', icon: '/images/icons/info.png' }
        ];
      default:
        return [
          { action: 'view', title: 'View', icon: '/images/icons/view.png' }
        ];
    }
  }

  /**
   * Fallback notification for unsupported browsers
   */
  private showFallbackNotification(notification: TradingNotification): void {
    // Browser alert as last resort
    if (notification.priority === 'critical') {
      alert(`${notification.title}: ${notification.body}`);
    } else {
      console.log(`Notification: ${notification.title} - ${notification.body}`);
    }
  }

  /**
   * Convert URL-safe base64 to Uint8Array for push subscription
   */
  private urlBase64ToUint8Array(base64String: string): Uint8Array {
    const padding = '='.repeat((4 - base64String.length % 4) % 4);
    const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
    const rawData = window.atob(base64);
    const outputArray = new Uint8Array(rawData.length);

    for (let i = 0; i < rawData.length; ++i) {
      outputArray[i] = rawData.charCodeAt(i);
    }

    return outputArray;
  }
}

// Singleton instance
export const pushNotificationService = new PushNotificationService();

// React hook for using push notifications
export function usePushNotifications() {
  const [isSupported, setIsSupported] = useState(false);
  const [permission, setPermission] = useState<NotificationPermission>('default');
  const [isSubscribed, setIsSubscribed] = useState(false);

  useEffect(() => {
    setIsSupported(pushNotificationService.isAvailable());
    setPermission(Notification.permission);
  }, []);

  const requestPermission = useCallback(async () => {
    try {
      const newPermission = await pushNotificationService.requestPermission();
      setPermission(newPermission);
      setIsSupported(newPermission === 'granted');
      return newPermission;
    } catch (error) {
      console.error('Failed to request permission:', error);
      return 'denied';
    }
  }, []);

  const showTradingNotification = useCallback(async (notification: TradingNotification) => {
    return await pushNotificationService.showTradingNotification(notification);
  }, []);

  const subscribeToPush = useCallback(async (serverPublicKey: string) => {
    try {
      const subscription = await pushNotificationService.subscribeToPush(serverPublicKey);
      setIsSubscribed(!!subscription);
      return subscription;
    } catch (error) {
      console.error('Failed to subscribe to push:', error);
      return null;
    }
  }, []);

  const unsubscribeFromPush = useCallback(async () => {
    const success = await pushNotificationService.unsubscribeFromPush();
    if (success) {
      setIsSubscribed(false);
    }
    return success;
  }, []);

  return {
    isSupported,
    permission,
    isSubscribed,
    requestPermission,
    showTradingNotification,
    subscribeToPush,
    unsubscribeFromPush,
    clearNotifications: pushNotificationService.clearNotifications.bind(pushNotificationService),
    getActiveNotifications: pushNotificationService.getActiveNotifications.bind(pushNotificationService)
  };
}
