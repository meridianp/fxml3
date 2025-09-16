/**
 * Loading Spinner Component
 *
 * Reusable loading indicator for the trading interface
 */

import React from 'react';
import { clsx } from 'clsx';

interface LoadingSpinnerProps {
  size?: 'sm' | 'md' | 'lg' | 'xl';
  color?: 'primary' | 'secondary' | 'white' | 'gray';
  className?: string;
  label?: string;
}

const sizeClasses = {
  sm: 'w-4 h-4',
  md: 'w-6 h-6',
  lg: 'w-8 h-8',
  xl: 'w-12 h-12',
};

const colorClasses = {
  primary: 'text-blue-600',
  secondary: 'text-gray-600',
  white: 'text-white',
  gray: 'text-gray-400',
};

export default function LoadingSpinner({
  size = 'md',
  color = 'primary',
  className,
  label = 'Loading...',
}: LoadingSpinnerProps) {
  return (
    <div className={clsx('flex items-center justify-center', className)}>
      <div className="flex flex-col items-center space-y-2">
        <div
          className={clsx(
            'animate-spin rounded-full border-2 border-transparent',
            sizeClasses[size],
            colorClasses[color]
          )}
          style={{
            borderTopColor: 'currentColor',
            borderRightColor: 'currentColor',
          }}
          role="status"
          aria-label={label}
        />
        {label && (
          <span className={clsx(
            'text-sm font-medium',
            colorClasses[color]
          )}>
            {label}
          </span>
        )}
      </div>
    </div>
  );
}
