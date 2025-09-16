/**
 * NotificationCenter Component
 *
 * Main UI component for displaying and managing notifications
 */

'use client';

import React, { useState, useEffect, useCallback } from 'react';
import {
  Notification,
  NotificationType,
  NotificationPriority,
  getNotificationService
} from '@/services/notification';
import { NotificationItem } from './NotificationItem';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import {
  BellIcon,
  CheckIcon,
  TrashIcon,
  FunnelIcon,
} from '@heroicons/react/24/outline';

type FilterType = 'all' | NotificationType;

interface NotificationCenterProps {
  className?: string;
  maxHeight?: string;
  showActions?: boolean;
}

export const NotificationCenter: React.FC<NotificationCenterProps> = ({
  className = '',
  maxHeight = '400px',
  showActions = true,
}) => {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [filter, setFilter] = useState<FilterType>('all');
  const [stats, setStats] = useState({ total: 0, unread: 0 });

  const notificationService = getNotificationService();

  // Load notifications and stats
  const loadNotifications = useCallback(() => {
    const allNotifications = notificationService.getAll();
    const filteredNotifications = filter === 'all'
      ? allNotifications
      : allNotifications.filter(n => n.type === filter);

    setNotifications(filteredNotifications);

    const serviceStats = notificationService.getStats();
    setStats({
      total: serviceStats.total,
      unread: serviceStats.unread,
    });
  }, [notificationService, filter]);

  // Setup event listeners for real-time updates
  useEffect(() => {
    loadNotifications();

    const handleNotificationCreated = () => loadNotifications();
    const handleNotificationRead = () => loadNotifications();
    const handleNotificationDismissed = () => loadNotifications();

    // Listen to notification events
    notificationService['eventBus'].on('notification:created', handleNotificationCreated);
    notificationService['eventBus'].on('notification:read', handleNotificationRead);
    notificationService['eventBus'].on('notification:dismissed', handleNotificationDismissed);

    return () => {
      notificationService['eventBus'].off('notification:created', handleNotificationCreated);
      notificationService['eventBus'].off('notification:read', handleNotificationRead);
      notificationService['eventBus'].off('notification:dismissed', handleNotificationDismissed);
    };
  }, [loadNotifications, notificationService]);

  // Handle notification click (mark as read)
  const handleNotificationClick = (notificationId: string) => {
    notificationService.markAsRead(notificationId);
  };

  // Handle notification dismiss
  const handleNotificationDismiss = (notificationId: string) => {
    notificationService.dismiss(notificationId);
  };

  // Handle notification action execution
  const handleNotificationAction = (notificationId: string, actionId: string) => {
    notificationService.executeAction(notificationId, actionId);
  };

  // Handle mark all as read
  const handleMarkAllRead = () => {
    notificationService.markAllAsRead();
  };

  // Handle clear all
  const handleClearAll = () => {
    notificationService.clearAll();
  };

  // Get filter options
  const filterOptions = [
    { value: 'all', label: 'All' },
    { value: NotificationType.INFO, label: 'Info' },
    { value: NotificationType.SUCCESS, label: 'Success' },
    { value: NotificationType.WARNING, label: 'Warnings' },
    { value: NotificationType.ERROR, label: 'Errors' },
    { value: NotificationType.SYSTEM, label: 'System' },
    { value: NotificationType.TRADING, label: 'Trading' },
  ];

  return (
    <div
      data-testid="notification-center"
      role="region"
      aria-label="Notifications"
      className={`bg-gray-900 border border-gray-700 rounded-lg ${className}`}
    >
      {/* Header */}
      <div className="p-4 border-b border-gray-700">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <BellIcon className="w-5 h-5 text-gray-400" />
            <h3 className="font-semibold text-white">Notifications</h3>
            {stats.unread > 0 && (
              <span className="px-2 py-1 bg-blue-500 text-white text-xs rounded-full">
                {stats.unread} unread
              </span>
            )}
          </div>

          {showActions && (
            <div className="flex items-center gap-2">
              <Select value={filter} onValueChange={(value: FilterType) => setFilter(value)}>
                <SelectTrigger
                  data-testid="notification-filter"
                  className="w-32 h-8"
                >
                  <FunnelIcon className="w-4 h-4 mr-1" />
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {filterOptions.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}
        </div>

        {showActions && stats.total > 0 && (
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={handleMarkAllRead}
              disabled={stats.unread === 0}
              className="gap-1"
            >
              <CheckIcon className="w-4 h-4" />
              Mark all read
            </Button>

            <Button
              variant="ghost"
              size="sm"
              onClick={handleClearAll}
              className="gap-1 text-red-400 hover:text-red-300"
            >
              <TrashIcon className="w-4 h-4" />
              Clear all
            </Button>
          </div>
        )}
      </div>

      {/* Notification List */}
      <div
        data-testid="notification-list"
        role="list"
        className="overflow-y-auto"
        style={{ maxHeight }}
      >
        {notifications.length === 0 ? (
          <div className="p-8 text-center text-gray-400">
            <BellIcon className="w-12 h-12 mx-auto mb-3 opacity-50" />
            <p>No notifications</p>
          </div>
        ) : (
          <div className="p-2 space-y-2">
            {notifications.map((notification) => (
              <NotificationItem
                key={notification.id}
                notification={notification}
                onClick={() => handleNotificationClick(notification.id)}
                onDismiss={() => handleNotificationDismiss(notification.id)}
                onActionClick={(actionId) => handleNotificationAction(notification.id, actionId)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
