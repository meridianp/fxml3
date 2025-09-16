/**
 * NotificationItem Component
 *
 * Individual notification display component with actions and interactions
 */

'use client';

import React from 'react';
import { Notification, NotificationType, NotificationPriority } from '@/services/notification';
import { Button } from '@/components/ui/button';
import {
  InformationCircleIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  XCircleIcon,
  CogIcon,
  ChartBarIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline';

interface NotificationItemProps {
  notification: Notification;
  onClick: () => void;
  onDismiss: () => void;
  onActionClick: (actionId: string) => void;
}

// Icon mapping for notification types
const getNotificationIcon = (type: NotificationType) => {
  const iconProps = { className: 'w-5 h-5 flex-shrink-0' };

  switch (type) {
    case NotificationType.INFO:
      return <InformationCircleIcon {...iconProps} />;
    case NotificationType.SUCCESS:
      return <CheckCircleIcon {...iconProps} />;
    case NotificationType.WARNING:
      return <ExclamationTriangleIcon {...iconProps} />;
    case NotificationType.ERROR:
      return <XCircleIcon {...iconProps} />;
    case NotificationType.SYSTEM:
      return <CogIcon {...iconProps} />;
    case NotificationType.TRADING:
      return <ChartBarIcon {...iconProps} />;
    default:
      return <InformationCircleIcon {...iconProps} />;
  }
};

// Color mapping for notification types
const getNotificationColors = (type: NotificationType, read: boolean) => {
  const baseColors = {
    [NotificationType.INFO]: 'border-blue-500 bg-blue-50 text-blue-900',
    [NotificationType.SUCCESS]: 'border-green-500 bg-green-50 text-green-900',
    [NotificationType.WARNING]: 'border-yellow-500 bg-yellow-50 text-yellow-900',
    [NotificationType.ERROR]: 'border-red-500 bg-red-50 text-red-900',
    [NotificationType.SYSTEM]: 'border-purple-500 bg-purple-50 text-purple-900',
    [NotificationType.TRADING]: 'border-indigo-500 bg-indigo-50 text-indigo-900',
  };

  const readColors = {
    [NotificationType.INFO]: 'border-blue-300 bg-blue-25 text-blue-700',
    [NotificationType.SUCCESS]: 'border-green-300 bg-green-25 text-green-700',
    [NotificationType.WARNING]: 'border-yellow-300 bg-yellow-25 text-yellow-700',
    [NotificationType.ERROR]: 'border-red-300 bg-red-25 text-red-700',
    [NotificationType.SYSTEM]: 'border-purple-300 bg-purple-25 text-purple-700',
    [NotificationType.TRADING]: 'border-indigo-300 bg-indigo-25 text-indigo-700',
  };

  return read ? readColors[type] : baseColors[type];
};

// Priority styling
const getPriorityStyles = (priority: NotificationPriority) => {
  switch (priority) {
    case NotificationPriority.CRITICAL:
      return 'ring-2 ring-red-500 ring-opacity-50 shadow-lg';
    case NotificationPriority.HIGH:
      return 'ring-1 ring-orange-400 ring-opacity-30';
    default:
      return '';
  }
};

// Format timestamp to relative time
const formatRelativeTime = (timestamp: Date): string => {
  const now = new Date();
  const diff = now.getTime() - timestamp.getTime();

  const minutes = Math.floor(diff / 60000);
  const hours = Math.floor(diff / 3600000);
  const days = Math.floor(diff / 86400000);

  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes}m ago`;
  if (hours < 24) return `${hours}h ago`;
  if (days < 7) return `${days}d ago`;

  return timestamp.toLocaleDateString();
};

export const NotificationItem: React.FC<NotificationItemProps> = ({
  notification,
  onClick,
  onDismiss,
  onActionClick,
}) => {
  const handleClick = () => {
    onClick();
  };

  const handleDismiss = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    onDismiss();
  };

  const handleActionClick = (actionId: string) => (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    onActionClick(actionId);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      onClick();
    }
  };

  const colorClasses = getNotificationColors(notification.type, notification.read);
  const priorityClasses = getPriorityStyles(notification.priority);
  const icon = getNotificationIcon(notification.type);
  const relativeTime = formatRelativeTime(notification.timestamp);

  const ariaLive = notification.priority === NotificationPriority.CRITICAL ? 'assertive' : 'polite';
  const ariaLabel = `${notification.type} notification: ${notification.title}. ${notification.message}`;

  return (
    <div
      data-testid={`notification-${notification.id}`}
      data-type={notification.type}
      data-priority={notification.priority}
      data-read={notification.read.toString()}
      role="listitem"
      tabIndex={0}
      aria-label={ariaLabel}
      aria-live={ariaLive}
      className={`
        relative p-4 border-l-4 rounded-r-lg cursor-pointer transition-all duration-200
        hover:shadow-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-opacity-50
        ${colorClasses} ${priorityClasses}
        ${notification.read ? 'opacity-75' : ''}
      `}
      onClick={handleClick}
      onKeyDown={handleKeyDown}
    >
      {/* Header with icon, title, and timestamp */}
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-3 flex-1 min-w-0">
          <div className="flex-shrink-0">
            {icon}
          </div>

          <div className="flex-1 min-w-0">
            <h4
              data-testid="notification-title"
              className="font-semibold text-sm truncate"
            >
              {notification.title}
            </h4>

            {notification.priority === NotificationPriority.HIGH && (
              <span className="inline-flex items-center px-1.5 py-0.5 rounded-full text-xs font-medium bg-orange-100 text-orange-800">
                High Priority
              </span>
            )}

            {notification.priority === NotificationPriority.CRITICAL && (
              <span className="inline-flex items-center px-1.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800">
                Critical
              </span>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2 flex-shrink-0">
          <span className="text-xs opacity-75">
            {relativeTime}
          </span>

          {!notification.persistent && (
            <button
              data-testid={`dismiss-${notification.id}`}
              aria-label="Dismiss notification"
              className="p-1 rounded-full hover:bg-black hover:bg-opacity-10 focus:outline-none focus:ring-2 focus:ring-current"
              onClick={handleDismiss}
            >
              <XMarkIcon className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      {/* Message */}
      <div className="mb-3">
        <p className="text-sm leading-relaxed">
          {notification.message}
        </p>
      </div>

      {/* Metadata */}
      {notification.metadata && Object.keys(notification.metadata).length > 0 && (
        <div data-testid="notification-metadata" className="mb-3">
          <div className="flex flex-wrap gap-2">
            {Object.entries(notification.metadata).map(([key, value]) => (
              <span
                key={key}
                className="inline-flex items-center px-2 py-1 rounded-md text-xs bg-black bg-opacity-10"
              >
                <span className="font-medium">{key}:</span>
                <span className="ml-1">{String(value)}</span>
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Actions */}
      {notification.actions && notification.actions.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {notification.actions.map((action) => (
            <Button
              key={action.id}
              data-primary={action.primary.toString()}
              variant={action.primary ? 'default' : 'outline'}
              size="sm"
              className="text-xs"
              onClick={handleActionClick(action.id)}
            >
              {action.label}
            </Button>
          ))}
        </div>
      )}

      {/* Unread indicator */}
      {!notification.read && (
        <div className="absolute top-2 right-2 w-2 h-2 bg-current rounded-full opacity-60" />
      )}
    </div>
  );
};
