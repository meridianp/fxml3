/**
 * Unified Notification Service
 *
 * Real-time notification system with WebSocket integration and event-driven architecture
 */

import { EventEmitter } from 'events';

export enum NotificationType {
  INFO = 'info',
  SUCCESS = 'success',
  WARNING = 'warning',
  ERROR = 'error',
  SYSTEM = 'system',
  TRADING = 'trading',
}

export enum NotificationPriority {
  LOW = 'low',
  NORMAL = 'normal',
  HIGH = 'high',
  CRITICAL = 'critical',
}

export interface NotificationAction {
  id: string;
  label: string;
  primary: boolean;
  handler?: (notificationId: string) => void;
}

export interface NotificationCreateData {
  type: NotificationType;
  title: string;
  message: string;
  priority?: NotificationPriority;
  persistent?: boolean;
  autoDismiss?: boolean;
  autoDismissTimeout?: number;
  actions?: NotificationAction[];
  metadata?: Record<string, any>;
}

export interface Notification {
  id: string;
  type: NotificationType;
  title: string;
  message: string;
  priority: NotificationPriority;
  timestamp: Date;
  read: boolean;
  persistent: boolean;
  autoDismiss?: boolean;
  autoDismissTimeout?: number;
  actions: NotificationAction[];
  metadata?: Record<string, any>;
}

export interface NotificationStats {
  total: number;
  unread: number;
  byType: Record<NotificationType, number>;
  byPriority: Record<NotificationPriority, number>;
}

export interface NotificationServiceConfig {
  eventBus: EventEmitter;
  websocket?: WebSocket;
  defaultAutoDismissTimeout?: number;
  maxNotifications?: number;
}

export class NotificationService {
  private notifications: Map<string, Notification> = new Map();
  private eventBus: EventEmitter;
  private websocket?: WebSocket;
  private config: NotificationServiceConfig;
  private autoDismissTimeouts: Map<string, NodeJS.Timeout> = new Map();

  constructor(config: NotificationServiceConfig) {
    this.config = {
      defaultAutoDismissTimeout: 10000,
      maxNotifications: 1000,
      ...config,
    };

    this.eventBus = config.eventBus;
    this.websocket = config.websocket;
  }

  /**
   * Create a new notification
   */
  create(data: NotificationCreateData): Notification {
    const notification: Notification = {
      id: this.generateId(),
      type: data.type,
      title: data.title,
      message: data.message,
      priority: data.priority || NotificationPriority.NORMAL,
      timestamp: new Date(),
      read: false,
      persistent: data.persistent || false,
      autoDismiss: data.autoDismiss,
      autoDismissTimeout: data.autoDismissTimeout || this.config.defaultAutoDismissTimeout,
      actions: data.actions || [],
      metadata: data.metadata,
    };

    // Enforce max notifications limit
    if (this.notifications.size >= (this.config.maxNotifications || 1000)) {
      this.removeOldestNonPersistent();
    }

    this.notifications.set(notification.id, notification);

    // Set up auto-dismiss if enabled
    if (notification.autoDismiss && !notification.persistent && notification.autoDismissTimeout) {
      const timeout = setTimeout(() => {
        this.dismiss(notification.id);
      }, notification.autoDismissTimeout);

      this.autoDismissTimeouts.set(notification.id, timeout);
    }

    // Emit events
    this.eventBus.emit('notification:created', notification);

    // Send over WebSocket if connected
    this.sendOverWebSocket(notification);

    return notification;
  }

  /**
   * Get all notifications
   */
  getAll(): Notification[] {
    return Array.from(this.notifications.values())
      .sort((a, b) => b.timestamp.getTime() - a.timestamp.getTime());
  }

  /**
   * Get notification by ID
   */
  getById(id: string): Notification | null {
    return this.notifications.get(id) || null;
  }

  /**
   * Get notifications by type
   */
  getByType(type: NotificationType): Notification[] {
    return this.getAll().filter(notification => notification.type === type);
  }

  /**
   * Get notifications by priority
   */
  getByPriority(priority: NotificationPriority): Notification[] {
    return this.getAll().filter(notification => notification.priority === priority);
  }

  /**
   * Get unread notifications
   */
  getUnread(): Notification[] {
    return this.getAll().filter(notification => !notification.read);
  }

  /**
   * Mark notification as read
   */
  markAsRead(id: string): Notification | null {
    const notification = this.notifications.get(id);
    if (!notification) return null;

    notification.read = true;
    this.notifications.set(id, notification);

    this.eventBus.emit('notification:read', id);
    return notification;
  }

  /**
   * Mark all notifications as read
   */
  markAllAsRead(): void {
    this.notifications.forEach((notification) => {
      if (!notification.read) {
        notification.read = true;
        this.notifications.set(notification.id, notification);
        this.eventBus.emit('notification:read', notification.id);
      }
    });
  }

  /**
   * Dismiss notification
   */
  dismiss(id: string, force = false): boolean {
    const notification = this.notifications.get(id);
    if (!notification) return false;

    // Don't dismiss persistent notifications unless forced
    if (notification.persistent && !force) {
      return false;
    }

    // Clear auto-dismiss timeout if exists
    const timeout = this.autoDismissTimeouts.get(id);
    if (timeout) {
      clearTimeout(timeout);
      this.autoDismissTimeouts.delete(id);
    }

    this.notifications.delete(id);
    this.eventBus.emit('notification:dismissed', id);

    return true;
  }

  /**
   * Clear all non-persistent notifications
   */
  clearAll(): void {
    const toDelete: string[] = [];

    this.notifications.forEach((notification, id) => {
      if (!notification.persistent) {
        toDelete.push(id);
      }
    });

    toDelete.forEach(id => this.dismiss(id));
  }

  /**
   * Get notification statistics
   */
  getStats(): NotificationStats {
    const notifications = this.getAll();

    const stats: NotificationStats = {
      total: notifications.length,
      unread: notifications.filter(n => !n.read).length,
      byType: {} as Record<NotificationType, number>,
      byPriority: {} as Record<NotificationPriority, number>,
    };

    // Initialize counters
    Object.values(NotificationType).forEach(type => {
      stats.byType[type] = 0;
    });

    Object.values(NotificationPriority).forEach(priority => {
      stats.byPriority[priority] = 0;
    });

    // Count notifications
    notifications.forEach(notification => {
      stats.byType[notification.type]++;
      stats.byPriority[notification.priority]++;
    });

    return stats;
  }

  /**
   * Execute notification action
   */
  executeAction(notificationId: string, actionId: string): boolean {
    const notification = this.notifications.get(notificationId);
    if (!notification) return false;

    const action = notification.actions.find(a => a.id === actionId);
    if (!action || !action.handler) return false;

    try {
      action.handler(notificationId);
      this.eventBus.emit('notification:action', { notificationId, actionId });
      return true;
    } catch (error) {
      console.error('Error executing notification action:', error);
      return false;
    }
  }

  /**
   * Clean up resources
   */
  destroy(): void {
    // Clear all auto-dismiss timeouts
    this.autoDismissTimeouts.forEach(timeout => clearTimeout(timeout));
    this.autoDismissTimeouts.clear();

    // Clear notifications
    this.notifications.clear();

    // Remove event listeners
    this.eventBus.removeAllListeners();
  }

  /**
   * Generate unique notification ID
   */
  private generateId(): string {
    return `notification_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  /**
   * Remove oldest non-persistent notification to make room for new ones
   */
  private removeOldestNonPersistent(): void {
    const nonPersistent = this.getAll()
      .filter(n => !n.persistent)
      .sort((a, b) => a.timestamp.getTime() - b.timestamp.getTime());

    if (nonPersistent.length > 0) {
      this.dismiss(nonPersistent[0].id);
    }
  }

  /**
   * Send notification over WebSocket if connected
   */
  private sendOverWebSocket(notification: Notification): void {
    if (!this.websocket || this.websocket.readyState !== WebSocket.OPEN) {
      return;
    }

    try {
      this.websocket.send(JSON.stringify({
        type: 'notification',
        data: notification,
      }));
    } catch (error) {
      console.warn('Failed to send notification over WebSocket:', error);
    }
  }
}

// Singleton instance for global use
let globalNotificationService: NotificationService | null = null;

/**
 * Get or create global notification service instance
 */
export const getNotificationService = (config?: NotificationServiceConfig): NotificationService => {
  if (!globalNotificationService) {
    if (config) {
      globalNotificationService = new NotificationService(config);
    } else {
      // Create with default config as fallback
      console.warn('NotificationService initialized with default config');
      globalNotificationService = new NotificationService({
        eventBus: new EventEmitter(),
        defaultAutoDismissTimeout: 10000,
        maxNotifications: 1000
      });
    }
  }

  return globalNotificationService;
};

/**
 * Helper functions for creating specific types of notifications
 */
export const createInfoNotification = (title: string, message: string, options?: Partial<NotificationCreateData>) => {
  const service = getNotificationService();
  return service.create({
    type: NotificationType.INFO,
    title,
    message,
    ...options,
  });
};

export const createSuccessNotification = (title: string, message: string, options?: Partial<NotificationCreateData>) => {
  const service = getNotificationService();
  return service.create({
    type: NotificationType.SUCCESS,
    title,
    message,
    ...options,
  });
};

export const createWarningNotification = (title: string, message: string, options?: Partial<NotificationCreateData>) => {
  const service = getNotificationService();
  return service.create({
    type: NotificationType.WARNING,
    title,
    message,
    priority: NotificationPriority.HIGH,
    ...options,
  });
};

export const createErrorNotification = (title: string, message: string, options?: Partial<NotificationCreateData>) => {
  const service = getNotificationService();
  return service.create({
    type: NotificationType.ERROR,
    title,
    message,
    priority: NotificationPriority.CRITICAL,
    persistent: true,
    ...options,
  });
};

export const createTradingNotification = (title: string, message: string, options?: Partial<NotificationCreateData>) => {
  const service = getNotificationService();
  return service.create({
    type: NotificationType.TRADING,
    title,
    message,
    priority: NotificationPriority.HIGH,
    ...options,
  });
};

export const createSystemNotification = (title: string, message: string, options?: Partial<NotificationCreateData>) => {
  const service = getNotificationService();
  return service.create({
    type: NotificationType.SYSTEM,
    title,
    message,
    priority: NotificationPriority.HIGH,
    persistent: true,
    ...options,
  });
};
