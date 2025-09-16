/**
 * NotificationCenter Component Tests
 *
 * Tests for the main notification center UI component
 */

import React from 'react';
import { screen, fireEvent, waitFor } from '@testing-library/react';
import { render } from '@/test-utils/render';
import { NotificationCenter } from './NotificationCenter';
import { NotificationService, NotificationType, NotificationPriority } from '@/services/notification';
import { EventEmitter } from 'events';

// Mock the notification service
const mockEventBus = new EventEmitter();
const mockWebSocket = {
  send: jest.fn(),
  close: jest.fn(),
  readyState: WebSocket.OPEN,
  addEventListener: jest.fn(),
  removeEventListener: jest.fn(),
} as any;

const notificationService = new NotificationService({
  eventBus: mockEventBus,
  websocket: mockWebSocket,
});

// Mock the service module
jest.mock('@/services/notification', () => ({
  ...jest.requireActual('@/services/notification'),
  getNotificationService: () => notificationService,
}));

describe('NotificationCenter', () => {
  beforeEach(() => {
    // Clear all notifications before each test
    notificationService.clearAll();
    jest.clearAllMocks();
  });

  afterEach(() => {
    notificationService.destroy();
  });

  describe('Rendering and Basic Functionality', () => {
    it('should render notification center with empty state', () => {
      render(<NotificationCenter />);

      expect(screen.getByTestId('notification-center')).toBeInTheDocument();
      expect(screen.getByText('No notifications')).toBeInTheDocument();
    });

    it('should render notifications when they exist', () => {
      // Create test notifications
      notificationService.create({
        type: NotificationType.INFO,
        title: 'Test Info',
        message: 'This is an info notification',
      });

      notificationService.create({
        type: NotificationType.WARNING,
        title: 'Test Warning',
        message: 'This is a warning notification',
      });

      render(<NotificationCenter />);

      expect(screen.getByText('Test Info')).toBeInTheDocument();
      expect(screen.getByText('This is an info notification')).toBeInTheDocument();
      expect(screen.getByText('Test Warning')).toBeInTheDocument();
      expect(screen.getByText('This is a warning notification')).toBeInTheDocument();
    });

    it('should show unread notification count', () => {
      // Create unread notifications
      notificationService.create({
        type: NotificationType.INFO,
        title: 'Unread 1',
        message: 'Message 1',
      });

      notificationService.create({
        type: NotificationType.INFO,
        title: 'Unread 2',
        message: 'Message 2',
      });

      render(<NotificationCenter />);

      expect(screen.getByText('2 unread')).toBeInTheDocument();
    });

    it('should update unread count when notifications are read', async () => {
      const notification = notificationService.create({
        type: NotificationType.INFO,
        title: 'Test Notification',
        message: 'Test message',
      });

      render(<NotificationCenter />);

      expect(screen.getByText('1 unread')).toBeInTheDocument();

      // Mark as read
      notificationService.markAsRead(notification.id);

      await waitFor(() => {
        expect(screen.queryByText('1 unread')).not.toBeInTheDocument();
      });
    });
  });

  describe('Notification Interactions', () => {
    it('should mark notification as read when clicked', async () => {
      const notification = notificationService.create({
        type: NotificationType.INFO,
        title: 'Click Test',
        message: 'Click to mark as read',
      });

      render(<NotificationCenter />);

      const notificationElement = screen.getByTestId(`notification-${notification.id}`);
      fireEvent.click(notificationElement);

      await waitFor(() => {
        expect(notificationService.getById(notification.id)?.read).toBe(true);
      });
    });

    it('should dismiss notification when dismiss button is clicked', async () => {
      const notification = notificationService.create({
        type: NotificationType.INFO,
        title: 'Dismiss Test',
        message: 'Click dismiss to remove',
      });

      render(<NotificationCenter />);

      const dismissButton = screen.getByTestId(`dismiss-${notification.id}`);
      fireEvent.click(dismissButton);

      await waitFor(() => {
        expect(notificationService.getById(notification.id)).toBeNull();
        expect(screen.queryByText('Dismiss Test')).not.toBeInTheDocument();
      });
    });

    it('should not show dismiss button for persistent notifications', () => {
      const notification = notificationService.create({
        type: NotificationType.ERROR,
        title: 'Persistent Error',
        message: 'This error is persistent',
        persistent: true,
      });

      render(<NotificationCenter />);

      expect(screen.queryByTestId(`dismiss-${notification.id}`)).not.toBeInTheDocument();
    });

    it('should execute notification actions when clicked', async () => {
      const actionHandler = jest.fn();

      const notification = notificationService.create({
        type: NotificationType.WARNING,
        title: 'Action Test',
        message: 'Click action button',
        actions: [
          {
            id: 'test-action',
            label: 'Test Action',
            primary: true,
            handler: actionHandler,
          },
        ],
      });

      render(<NotificationCenter />);

      const actionButton = screen.getByText('Test Action');
      fireEvent.click(actionButton);

      expect(actionHandler).toHaveBeenCalledWith(notification.id);
    });
  });

  describe('Filtering and Sorting', () => {
    beforeEach(async () => {
      // Create notifications of different types with slight time delays to ensure different timestamps
      const infoNotification = notificationService.create({
        type: NotificationType.INFO,
        title: 'Info Notification',
        message: 'Info message',
      });

      // Manually set timestamps to ensure proper sorting
      const now = Date.now();
      infoNotification.timestamp = new Date(now - 2000); // 2 seconds ago
      notificationService['notifications'].set(infoNotification.id, infoNotification);

      const warningNotification = notificationService.create({
        type: NotificationType.WARNING,
        title: 'Warning Notification',
        message: 'Warning message',
      });

      warningNotification.timestamp = new Date(now - 1000); // 1 second ago
      notificationService['notifications'].set(warningNotification.id, warningNotification);

      const errorNotification = notificationService.create({
        type: NotificationType.ERROR,
        title: 'Error Notification',
        message: 'Error message',
      });

      errorNotification.timestamp = new Date(now); // most recent
      notificationService['notifications'].set(errorNotification.id, errorNotification);
    });

    it('should filter notifications by type', async () => {
      render(<NotificationCenter />);

      // Click filter dropdown
      const filterButton = screen.getByTestId('notification-filter');
      fireEvent.click(filterButton);

      // Select warning filter
      const warningFilter = screen.getByText('Warnings');
      fireEvent.click(warningFilter);

      await waitFor(() => {
        expect(screen.getByText('Warning Notification')).toBeInTheDocument();
        expect(screen.queryByText('Info Notification')).not.toBeInTheDocument();
        expect(screen.queryByText('Error Notification')).not.toBeInTheDocument();
      });
    });

    it('should show all notifications when "All" filter is selected', async () => {
      render(<NotificationCenter />);

      // First filter by warnings
      const filterButton = screen.getByTestId('notification-filter');
      fireEvent.click(filterButton);
      fireEvent.click(screen.getByText('Warnings'));

      // Then select "All"
      fireEvent.click(filterButton);
      fireEvent.click(screen.getByText('All'));

      await waitFor(() => {
        expect(screen.getByText('Info Notification')).toBeInTheDocument();
        expect(screen.getByText('Warning Notification')).toBeInTheDocument();
        expect(screen.getByText('Error Notification')).toBeInTheDocument();
      });
    });

    it('should sort notifications by timestamp (newest first)', () => {
      render(<NotificationCenter />);

      // Get all notification titles directly
      const titleElements = screen.getAllByTestId('notification-title');
      const titles = titleElements.map(element => element.textContent);

      // Since notifications are created in order: Info, Warning, Error
      // They should appear in reverse order (newest first): Error, Warning, Info
      expect(titles).toEqual(['Error Notification', 'Warning Notification', 'Info Notification']);
    });
  });

  describe('Bulk Actions', () => {
    beforeEach(() => {
      // Create multiple notifications
      notificationService.create({
        type: NotificationType.INFO,
        title: 'Info 1',
        message: 'Info message 1',
      });

      notificationService.create({
        type: NotificationType.WARNING,
        title: 'Warning 1',
        message: 'Warning message 1',
      });
    });

    it('should mark all notifications as read', async () => {
      render(<NotificationCenter />);

      const markAllReadButton = screen.getByText('Mark all read');
      fireEvent.click(markAllReadButton);

      await waitFor(() => {
        expect(notificationService.getUnread()).toHaveLength(0);
        expect(screen.queryByText('unread')).not.toBeInTheDocument();
      });
    });

    it('should clear all non-persistent notifications', async () => {
      // Add a persistent notification
      notificationService.create({
        type: NotificationType.ERROR,
        title: 'Persistent Error',
        message: 'This should remain',
        persistent: true,
      });

      render(<NotificationCenter />);

      const clearAllButton = screen.getByText('Clear all');
      fireEvent.click(clearAllButton);

      await waitFor(() => {
        // Should only have the persistent notification
        expect(screen.getByText('Persistent Error')).toBeInTheDocument();
        expect(screen.queryByText('Info 1')).not.toBeInTheDocument();
        expect(screen.queryByText('Warning 1')).not.toBeInTheDocument();
      });
    });
  });

  describe('Real-time Updates', () => {
    it('should update when new notifications are created', async () => {
      render(<NotificationCenter />);

      expect(screen.getByText('No notifications')).toBeInTheDocument();

      // Create notification after component is rendered
      notificationService.create({
        type: NotificationType.SUCCESS,
        title: 'New Notification',
        message: 'This should appear automatically',
      });

      await waitFor(() => {
        expect(screen.getByText('New Notification')).toBeInTheDocument();
        expect(screen.queryByText('No notifications')).not.toBeInTheDocument();
      });
    });

    it('should update when notifications are dismissed', async () => {
      const notification = notificationService.create({
        type: NotificationType.INFO,
        title: 'To Be Dismissed',
        message: 'This will be removed',
      });

      render(<NotificationCenter />);

      expect(screen.getByText('To Be Dismissed')).toBeInTheDocument();

      // Dismiss notification programmatically
      notificationService.dismiss(notification.id);

      await waitFor(() => {
        expect(screen.queryByText('To Be Dismissed')).not.toBeInTheDocument();
      });
    });
  });

  describe('Accessibility', () => {
    it('should have proper ARIA attributes', () => {
      notificationService.create({
        type: NotificationType.INFO,
        title: 'Accessibility Test',
        message: 'Testing ARIA attributes',
      });

      render(<NotificationCenter />);

      const notificationCenter = screen.getByTestId('notification-center');
      expect(notificationCenter).toHaveAttribute('role', 'region');
      expect(notificationCenter).toHaveAttribute('aria-label', 'Notifications');

      const notificationList = screen.getByTestId('notification-list');
      expect(notificationList).toHaveAttribute('role', 'list');
    });

    it('should support keyboard navigation', () => {
      const notification = notificationService.create({
        type: NotificationType.INFO,
        title: 'Keyboard Test',
        message: 'Testing keyboard navigation',
      });

      render(<NotificationCenter />);

      const notificationElement = screen.getByTestId(`notification-${notification.id}`);
      expect(notificationElement).toHaveAttribute('tabIndex', '0');

      // Test Enter key
      fireEvent.keyDown(notificationElement, { key: 'Enter', code: 'Enter' });
      expect(notificationService.getById(notification.id)?.read).toBe(true);
    });
  });
});
