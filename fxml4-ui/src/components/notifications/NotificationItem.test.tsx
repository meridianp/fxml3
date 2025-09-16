/**
 * NotificationItem Component Tests
 *
 * Tests for individual notification display component
 */

import React from 'react';
import { screen, fireEvent } from '@testing-library/react';
import { render } from '@/test-utils/render';
import { NotificationItem } from './NotificationItem';
import { Notification, NotificationType, NotificationPriority } from '@/services/notification';

// Base notification for testing
const baseNotification: Notification = {
  id: 'test-notification-123',
  type: NotificationType.INFO,
  title: 'Test Notification',
  message: 'This is a test notification message',
  priority: NotificationPriority.NORMAL,
  timestamp: new Date('2024-01-15T10:30:00Z'),
  read: false,
  persistent: false,
  autoDismiss: undefined,
  autoDismissTimeout: 10000,
  actions: [],
  metadata: undefined,
};

const mockOnClick = jest.fn();
const mockOnDismiss = jest.fn();
const mockOnActionClick = jest.fn();

describe('NotificationItem', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Basic Rendering', () => {
    it('should render notification with basic information', () => {
      render(
        <NotificationItem
          notification={baseNotification}
          onClick={mockOnClick}
          onDismiss={mockOnDismiss}
          onActionClick={mockOnActionClick}
        />
      );

      expect(screen.getByTestId('notification-test-notification-123')).toBeInTheDocument();
      expect(screen.getByTestId('notification-title')).toHaveTextContent('Test Notification');
      expect(screen.getByText('This is a test notification message')).toBeInTheDocument();
    });

    it('should display timestamp in relative format', () => {
      const recentNotification = {
        ...baseNotification,
        timestamp: new Date(Date.now() - 60000), // 1 minute ago
      };

      render(
        <NotificationItem
          notification={recentNotification}
          onClick={mockOnClick}
          onDismiss={mockOnDismiss}
          onActionClick={mockOnActionClick}
        />
      );

      // Should show relative time like "1m ago"
      expect(screen.getByText(/ago/)).toBeInTheDocument();
    });

    it('should show dismiss button for non-persistent notifications', () => {
      render(
        <NotificationItem
          notification={baseNotification}
          onClick={mockOnClick}
          onDismiss={mockOnDismiss}
          onActionClick={mockOnActionClick}
        />
      );

      expect(screen.getByTestId('dismiss-test-notification-123')).toBeInTheDocument();
    });

    it('should not show dismiss button for persistent notifications', () => {
      const persistentNotification = {
        ...baseNotification,
        persistent: true,
      };

      render(
        <NotificationItem
          notification={persistentNotification}
          onClick={mockOnClick}
          onDismiss={mockOnDismiss}
          onActionClick={mockOnActionClick}
        />
      );

      expect(screen.queryByTestId('dismiss-test-notification-123')).not.toBeInTheDocument();
    });
  });

  describe('Notification Types and Styling', () => {
    const testCases = [
      { type: NotificationType.INFO, expectedIcon: 'info', expectedColor: 'blue' },
      { type: NotificationType.SUCCESS, expectedIcon: 'success', expectedColor: 'green' },
      { type: NotificationType.WARNING, expectedIcon: 'warning', expectedColor: 'yellow' },
      { type: NotificationType.ERROR, expectedIcon: 'error', expectedColor: 'red' },
      { type: NotificationType.SYSTEM, expectedIcon: 'system', expectedColor: 'purple' },
      { type: NotificationType.TRADING, expectedIcon: 'trading', expectedColor: 'indigo' },
    ];

    testCases.forEach(({ type, expectedIcon, expectedColor }) => {
      it(`should render ${type} notification with appropriate styling`, () => {
        const typedNotification = {
          ...baseNotification,
          type,
        };

        render(
          <NotificationItem
            notification={typedNotification}
            onClick={mockOnClick}
            onDismiss={mockOnDismiss}
            onActionClick={mockOnActionClick}
          />
        );

        const notificationElement = screen.getByTestId('notification-test-notification-123');
        expect(notificationElement).toHaveAttribute('data-type', type);
      });
    });
  });

  describe('Priority Handling', () => {
    it('should highlight critical priority notifications', () => {
      const criticalNotification = {
        ...baseNotification,
        priority: NotificationPriority.CRITICAL,
        type: NotificationType.ERROR,
      };

      render(
        <NotificationItem
          notification={criticalNotification}
          onClick={mockOnClick}
          onDismiss={mockOnDismiss}
          onActionClick={mockOnActionClick}
        />
      );

      const notificationElement = screen.getByTestId('notification-test-notification-123');
      expect(notificationElement).toHaveAttribute('data-priority', 'critical');
    });

    it('should show priority indicator for high priority notifications', () => {
      const highPriorityNotification = {
        ...baseNotification,
        priority: NotificationPriority.HIGH,
      };

      render(
        <NotificationItem
          notification={highPriorityNotification}
          onClick={mockOnClick}
          onDismiss={mockOnDismiss}
          onActionClick={mockOnActionClick}
        />
      );

      const notificationElement = screen.getByTestId('notification-test-notification-123');
      expect(notificationElement).toHaveAttribute('data-priority', 'high');
    });
  });

  describe('Read State', () => {
    it('should show unread notification styling', () => {
      render(
        <NotificationItem
          notification={baseNotification}
          onClick={mockOnClick}
          onDismiss={mockOnDismiss}
          onActionClick={mockOnActionClick}
        />
      );

      const notificationElement = screen.getByTestId('notification-test-notification-123');
      expect(notificationElement).toHaveAttribute('data-read', 'false');
    });

    it('should show read notification styling', () => {
      const readNotification = {
        ...baseNotification,
        read: true,
      };

      render(
        <NotificationItem
          notification={readNotification}
          onClick={mockOnClick}
          onDismiss={mockOnDismiss}
          onActionClick={mockOnActionClick}
        />
      );

      const notificationElement = screen.getByTestId('notification-test-notification-123');
      expect(notificationElement).toHaveAttribute('data-read', 'true');
    });
  });

  describe('Actions', () => {
    it('should render notification actions when provided', () => {
      const notificationWithActions = {
        ...baseNotification,
        actions: [
          { id: 'view', label: 'View Details', primary: true },
          { id: 'dismiss', label: 'Dismiss', primary: false },
        ],
      };

      render(
        <NotificationItem
          notification={notificationWithActions}
          onClick={mockOnClick}
          onDismiss={mockOnDismiss}
          onActionClick={mockOnActionClick}
        />
      );

      expect(screen.getByText('View Details')).toBeInTheDocument();
      expect(screen.getByText('Dismiss')).toBeInTheDocument();
    });

    it('should distinguish primary and secondary actions', () => {
      const notificationWithActions = {
        ...baseNotification,
        actions: [
          { id: 'view', label: 'View Details', primary: true },
          { id: 'dismiss', label: 'Dismiss', primary: false },
        ],
      };

      render(
        <NotificationItem
          notification={notificationWithActions}
          onClick={mockOnClick}
          onDismiss={mockOnDismiss}
          onActionClick={mockOnActionClick}
        />
      );

      const primaryAction = screen.getByText('View Details');
      const secondaryAction = screen.getByText('Dismiss');

      expect(primaryAction).toHaveAttribute('data-primary', 'true');
      expect(secondaryAction).toHaveAttribute('data-primary', 'false');
    });

    it('should call onActionClick when action button is clicked', () => {
      const notificationWithActions = {
        ...baseNotification,
        actions: [
          { id: 'test-action', label: 'Test Action', primary: true },
        ],
      };

      render(
        <NotificationItem
          notification={notificationWithActions}
          onClick={mockOnClick}
          onDismiss={mockOnDismiss}
          onActionClick={mockOnActionClick}
        />
      );

      const actionButton = screen.getByText('Test Action');
      fireEvent.click(actionButton);

      expect(mockOnActionClick).toHaveBeenCalledWith('test-action');
      expect(mockOnActionClick).toHaveBeenCalledTimes(1);
    });
  });

  describe('Interactions', () => {
    it('should call onClick when notification is clicked', () => {
      render(
        <NotificationItem
          notification={baseNotification}
          onClick={mockOnClick}
          onDismiss={mockOnDismiss}
          onActionClick={mockOnActionClick}
        />
      );

      const notificationElement = screen.getByTestId('notification-test-notification-123');
      fireEvent.click(notificationElement);

      expect(mockOnClick).toHaveBeenCalledTimes(1);
    });

    it('should call onDismiss when dismiss button is clicked', () => {
      render(
        <NotificationItem
          notification={baseNotification}
          onClick={mockOnClick}
          onDismiss={mockOnDismiss}
          onActionClick={mockOnActionClick}
        />
      );

      const dismissButton = screen.getByTestId('dismiss-test-notification-123');
      fireEvent.click(dismissButton);

      expect(mockOnDismiss).toHaveBeenCalledTimes(1);
    });

    it('should prevent onClick when dismiss button is clicked', () => {
      render(
        <NotificationItem
          notification={baseNotification}
          onClick={mockOnClick}
          onDismiss={mockOnDismiss}
          onActionClick={mockOnActionClick}
        />
      );

      const dismissButton = screen.getByTestId('dismiss-test-notification-123');
      fireEvent.click(dismissButton);

      expect(mockOnDismiss).toHaveBeenCalledTimes(1);
      expect(mockOnClick).not.toHaveBeenCalled();
    });

    it('should prevent onClick when action button is clicked', () => {
      const notificationWithActions = {
        ...baseNotification,
        actions: [
          { id: 'test-action', label: 'Test Action', primary: true },
        ],
      };

      render(
        <NotificationItem
          notification={notificationWithActions}
          onClick={mockOnClick}
          onDismiss={mockOnDismiss}
          onActionClick={mockOnActionClick}
        />
      );

      const actionButton = screen.getByText('Test Action');
      fireEvent.click(actionButton);

      expect(mockOnActionClick).toHaveBeenCalledWith('test-action');
      expect(mockOnClick).not.toHaveBeenCalled();
    });
  });

  describe('Keyboard Navigation', () => {
    it('should be focusable', () => {
      render(
        <NotificationItem
          notification={baseNotification}
          onClick={mockOnClick}
          onDismiss={mockOnDismiss}
          onActionClick={mockOnActionClick}
        />
      );

      const notificationElement = screen.getByTestId('notification-test-notification-123');
      expect(notificationElement).toHaveAttribute('tabIndex', '0');
    });

    it('should respond to Enter key', () => {
      render(
        <NotificationItem
          notification={baseNotification}
          onClick={mockOnClick}
          onDismiss={mockOnDismiss}
          onActionClick={mockOnActionClick}
        />
      );

      const notificationElement = screen.getByTestId('notification-test-notification-123');
      fireEvent.keyDown(notificationElement, { key: 'Enter', code: 'Enter' });

      expect(mockOnClick).toHaveBeenCalledTimes(1);
    });

    it('should respond to Space key', () => {
      render(
        <NotificationItem
          notification={baseNotification}
          onClick={mockOnClick}
          onDismiss={mockOnDismiss}
          onActionClick={mockOnActionClick}
        />
      );

      const notificationElement = screen.getByTestId('notification-test-notification-123');
      fireEvent.keyDown(notificationElement, { key: ' ', code: 'Space' });

      expect(mockOnClick).toHaveBeenCalledTimes(1);
    });
  });

  describe('Accessibility', () => {
    it('should have proper ARIA attributes', () => {
      render(
        <NotificationItem
          notification={baseNotification}
          onClick={mockOnClick}
          onDismiss={mockOnDismiss}
          onActionClick={mockOnActionClick}
        />
      );

      const notificationElement = screen.getByTestId('notification-test-notification-123');
      expect(notificationElement).toHaveAttribute('role', 'listitem');
      expect(notificationElement).toHaveAttribute('aria-label');
      expect(notificationElement).toHaveAttribute('aria-live', 'polite');
    });

    it('should have urgent aria-live for critical notifications', () => {
      const criticalNotification = {
        ...baseNotification,
        priority: NotificationPriority.CRITICAL,
      };

      render(
        <NotificationItem
          notification={criticalNotification}
          onClick={mockOnClick}
          onDismiss={mockOnDismiss}
          onActionClick={mockOnActionClick}
        />
      );

      const notificationElement = screen.getByTestId('notification-test-notification-123');
      expect(notificationElement).toHaveAttribute('aria-live', 'assertive');
    });

    it('should have accessible dismiss button', () => {
      render(
        <NotificationItem
          notification={baseNotification}
          onClick={mockOnClick}
          onDismiss={mockOnDismiss}
          onActionClick={mockOnActionClick}
        />
      );

      const dismissButton = screen.getByTestId('dismiss-test-notification-123');
      expect(dismissButton).toHaveAttribute('aria-label', 'Dismiss notification');
    });
  });

  describe('Metadata Display', () => {
    it('should display metadata when provided', () => {
      const notificationWithMetadata = {
        ...baseNotification,
        metadata: {
          source: 'Trading Engine',
          symbol: 'EURUSD',
          orderId: 'ORD-123456',
        },
      };

      render(
        <NotificationItem
          notification={notificationWithMetadata}
          onClick={mockOnClick}
          onDismiss={mockOnDismiss}
          onActionClick={mockOnActionClick}
        />
      );

      expect(screen.getByText('Trading Engine')).toBeInTheDocument();
      expect(screen.getByText('EURUSD')).toBeInTheDocument();
    });

    it('should not show metadata section when metadata is empty', () => {
      render(
        <NotificationItem
          notification={baseNotification}
          onClick={mockOnClick}
          onDismiss={mockOnDismiss}
          onActionClick={mockOnActionClick}
        />
      );

      // Should not have metadata container
      expect(screen.queryByTestId('notification-metadata')).not.toBeInTheDocument();
    });
  });
});
