/**
 * Notification Service Tests
 *
 * Tests for unified notification system with real-time capabilities
 */

import { NotificationService, NotificationType, NotificationPriority } from './notification';
import { EventEmitter } from 'events';

// Mock WebSocket
const mockWebSocket = {
  send: jest.fn(),
  close: jest.fn(),
  readyState: WebSocket.OPEN,
  addEventListener: jest.fn(),
  removeEventListener: jest.fn(),
};

// Mock EventEmitter for testing
class MockEventEmitter extends EventEmitter {}

describe('NotificationService', () => {
  let notificationService: NotificationService;
  let mockEventBus: MockEventEmitter;

  beforeEach(() => {
    mockEventBus = new MockEventEmitter();
    notificationService = new NotificationService({
      eventBus: mockEventBus,
      websocket: mockWebSocket as any,
    });

    // Clear all mocks
    jest.clearAllMocks();
  });

  afterEach(() => {
    notificationService.destroy();
  });

  describe('Notification Creation and Management', () => {
    it('should create a basic notification with required fields', () => {
      const notification = notificationService.create({
        type: NotificationType.INFO,
        title: 'Test Notification',
        message: 'This is a test message',
      });

      expect(notification).toEqual({
        id: expect.any(String),
        type: NotificationType.INFO,
        title: 'Test Notification',
        message: 'This is a test message',
        priority: NotificationPriority.NORMAL,
        timestamp: expect.any(Date),
        read: false,
        persistent: false,
        autoDismiss: undefined,
        autoDismissTimeout: 10000,
        actions: [],
        metadata: undefined,
      });
    });

    it('should create notification with custom priority and actions', () => {
      const actions = [
        { id: 'view', label: 'View Details', primary: true },
        { id: 'dismiss', label: 'Dismiss', primary: false },
      ];

      const notification = notificationService.create({
        type: NotificationType.WARNING,
        title: 'Risk Alert',
        message: 'Position size exceeds risk limit',
        priority: NotificationPriority.HIGH,
        persistent: true,
        actions,
      });

      expect(notification.priority).toBe(NotificationPriority.HIGH);
      expect(notification.persistent).toBe(true);
      expect(notification.actions).toEqual(actions);
    });

    it('should assign unique IDs to notifications', () => {
      const notification1 = notificationService.create({
        type: NotificationType.INFO,
        title: 'Test 1',
        message: 'Message 1',
      });

      const notification2 = notificationService.create({
        type: NotificationType.INFO,
        title: 'Test 2',
        message: 'Message 2',
      });

      expect(notification1.id).not.toBe(notification2.id);
    });

    it('should emit notification events when created', () => {
      const eventSpy = jest.fn();
      mockEventBus.on('notification:created', eventSpy);

      const notification = notificationService.create({
        type: NotificationType.SUCCESS,
        title: 'Order Filled',
        message: 'Buy order for EURUSD executed successfully',
      });

      expect(eventSpy).toHaveBeenCalledWith(notification);
    });
  });

  describe('Notification Retrieval and Filtering', () => {
    beforeEach(() => {
      // Create test notifications
      notificationService.create({
        type: NotificationType.INFO,
        title: 'Info 1',
        message: 'Info message 1',
        priority: NotificationPriority.LOW,
      });

      notificationService.create({
        type: NotificationType.WARNING,
        title: 'Warning 1',
        message: 'Warning message 1',
        priority: NotificationPriority.HIGH,
      });

      notificationService.create({
        type: NotificationType.ERROR,
        title: 'Error 1',
        message: 'Error message 1',
        priority: NotificationPriority.CRITICAL,
      });
    });

    it('should retrieve all notifications', () => {
      const notifications = notificationService.getAll();
      expect(notifications).toHaveLength(3);
    });

    it('should filter notifications by type', () => {
      const warningNotifications = notificationService.getByType(NotificationType.WARNING);
      expect(warningNotifications).toHaveLength(1);
      expect(warningNotifications[0].type).toBe(NotificationType.WARNING);
    });

    it('should filter notifications by priority', () => {
      const highPriorityNotifications = notificationService.getByPriority(NotificationPriority.HIGH);
      expect(highPriorityNotifications).toHaveLength(1);
      expect(highPriorityNotifications[0].priority).toBe(NotificationPriority.HIGH);
    });

    it('should filter unread notifications', () => {
      const unreadNotifications = notificationService.getUnread();
      expect(unreadNotifications).toHaveLength(3);
    });

    it('should get notification by ID', () => {
      const allNotifications = notificationService.getAll();
      const firstNotification = allNotifications[0];

      const foundNotification = notificationService.getById(firstNotification.id);
      expect(foundNotification).toEqual(firstNotification);
    });

    it('should return null for non-existent notification ID', () => {
      const foundNotification = notificationService.getById('non-existent-id');
      expect(foundNotification).toBeNull();
    });
  });

  describe('Notification Actions', () => {
    let testNotification: any;

    beforeEach(() => {
      testNotification = notificationService.create({
        type: NotificationType.INFO,
        title: 'Test Notification',
        message: 'Test message',
      });
    });

    it('should mark notification as read', () => {
      const updated = notificationService.markAsRead(testNotification.id);

      expect(updated?.read).toBe(true);
      expect(notificationService.getUnread()).toHaveLength(0);
    });

    it('should mark all notifications as read', () => {
      // Create additional notifications
      notificationService.create({
        type: NotificationType.WARNING,
        title: 'Warning',
        message: 'Warning message',
      });

      notificationService.markAllAsRead();
      expect(notificationService.getUnread()).toHaveLength(0);
    });

    it('should dismiss notification', () => {
      const dismissed = notificationService.dismiss(testNotification.id);

      expect(dismissed).toBe(true);
      expect(notificationService.getAll()).toHaveLength(0);
    });

    it('should not dismiss persistent notifications', () => {
      const persistentNotification = notificationService.create({
        type: NotificationType.ERROR,
        title: 'Critical Error',
        message: 'System error occurred',
        persistent: true,
      });

      const dismissed = notificationService.dismiss(persistentNotification.id);

      expect(dismissed).toBe(false);
      expect(notificationService.getAll()).toHaveLength(2); // Original + persistent
    });

    it('should force dismiss persistent notifications', () => {
      const persistentNotification = notificationService.create({
        type: NotificationType.ERROR,
        title: 'Critical Error',
        message: 'System error occurred',
        persistent: true,
      });

      const dismissed = notificationService.dismiss(persistentNotification.id, true);

      expect(dismissed).toBe(true);
      expect(notificationService.getAll()).toHaveLength(1); // Only original
    });

    it('should clear all non-persistent notifications', () => {
      notificationService.create({
        type: NotificationType.ERROR,
        title: 'Critical Error',
        message: 'System error occurred',
        persistent: true,
      });

      notificationService.clearAll();

      const remaining = notificationService.getAll();
      expect(remaining).toHaveLength(1);
      expect(remaining[0].persistent).toBe(true);
    });
  });

  describe('Real-time Capabilities', () => {
    it('should send notification over WebSocket when created', () => {
      const notification = notificationService.create({
        type: NotificationType.SUCCESS,
        title: 'Trade Executed',
        message: 'EURUSD buy order filled at 1.08245',
      });

      expect(mockWebSocket.send).toHaveBeenCalledWith(
        JSON.stringify({
          type: 'notification',
          data: notification,
        })
      );
    });

    it('should emit events for notification state changes', () => {
      const readSpy = jest.fn();
      const dismissSpy = jest.fn();

      mockEventBus.on('notification:read', readSpy);
      mockEventBus.on('notification:dismissed', dismissSpy);

      const notification = notificationService.create({
        type: NotificationType.INFO,
        title: 'Test',
        message: 'Test message',
      });

      notificationService.markAsRead(notification.id);
      expect(readSpy).toHaveBeenCalledWith(notification.id);

      notificationService.dismiss(notification.id);
      expect(dismissSpy).toHaveBeenCalledWith(notification.id);
    });

    it('should handle WebSocket connection errors gracefully', () => {
      // Mock WebSocket error
      const errorWebSocket = {
        ...mockWebSocket,
        readyState: WebSocket.CLOSED,
        send: jest.fn(() => {
          throw new Error('WebSocket connection closed');
        }),
      };

      const serviceWithError = new NotificationService({
        eventBus: mockEventBus,
        websocket: errorWebSocket as any,
      });

      // Should not throw error
      expect(() => {
        serviceWithError.create({
          type: NotificationType.INFO,
          title: 'Test',
          message: 'Test message',
        });
      }).not.toThrow();

      serviceWithError.destroy();
    });
  });

  describe('Auto-dismiss and Expiry', () => {
    beforeEach(() => {
      jest.useFakeTimers();
    });

    afterEach(() => {
      jest.useRealTimers();
    });

    it('should auto-dismiss notification after specified timeout', () => {
      const notification = notificationService.create({
        type: NotificationType.INFO,
        title: 'Auto-dismiss Test',
        message: 'This should auto-dismiss',
        autoDismiss: true,
        autoDismissTimeout: 5000,
      });

      expect(notificationService.getAll()).toHaveLength(1);

      // Fast-forward time
      jest.advanceTimersByTime(5000);

      expect(notificationService.getAll()).toHaveLength(0);
    });

    it('should not auto-dismiss persistent notifications', () => {
      const notification = notificationService.create({
        type: NotificationType.ERROR,
        title: 'Persistent Error',
        message: 'This should not auto-dismiss',
        persistent: true,
        autoDismiss: true,
        autoDismissTimeout: 1000,
      });

      jest.advanceTimersByTime(1000);

      expect(notificationService.getAll()).toHaveLength(1);
    });

    it('should cancel auto-dismiss when notification is manually dismissed', () => {
      const notification = notificationService.create({
        type: NotificationType.INFO,
        title: 'Manual Dismiss Test',
        message: 'This will be manually dismissed',
        autoDismiss: true,
        autoDismissTimeout: 5000,
      });

      // Manually dismiss before timeout
      notificationService.dismiss(notification.id);

      expect(notificationService.getAll()).toHaveLength(0);

      // Fast-forward time - should not cause errors
      jest.advanceTimersByTime(5000);

      expect(notificationService.getAll()).toHaveLength(0);
    });
  });

  describe('Notification Statistics', () => {
    beforeEach(() => {
      // Create various notifications
      notificationService.create({ type: NotificationType.INFO, title: 'Info 1', message: 'Message 1' });
      notificationService.create({ type: NotificationType.INFO, title: 'Info 2', message: 'Message 2' });
      notificationService.create({ type: NotificationType.WARNING, title: 'Warning 1', message: 'Message 3' });
      notificationService.create({ type: NotificationType.ERROR, title: 'Error 1', message: 'Message 4' });
      notificationService.create({ type: NotificationType.SUCCESS, title: 'Success 1', message: 'Message 5' });
    });

    it('should return correct notification counts', () => {
      const stats = notificationService.getStats();

      expect(stats.total).toBe(5);
      expect(stats.unread).toBe(5);
      expect(stats.byType[NotificationType.INFO]).toBe(2);
      expect(stats.byType[NotificationType.WARNING]).toBe(1);
      expect(stats.byType[NotificationType.ERROR]).toBe(1);
      expect(stats.byType[NotificationType.SUCCESS]).toBe(1);
    });

    it('should update stats after reading notifications', () => {
      const notifications = notificationService.getAll();
      notificationService.markAsRead(notifications[0].id);
      notificationService.markAsRead(notifications[1].id);

      const stats = notificationService.getStats();
      expect(stats.total).toBe(5);
      expect(stats.unread).toBe(3);
    });

    it('should update stats after dismissing notifications', () => {
      const notifications = notificationService.getAll();
      notificationService.dismiss(notifications[0].id);
      notificationService.dismiss(notifications[1].id);

      const stats = notificationService.getStats();
      expect(stats.total).toBe(3);
      expect(stats.unread).toBe(3);
    });
  });
});
