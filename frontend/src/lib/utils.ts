/**
 * Utility Functions
 * 
 * Common utility functions for formatting, validation, and data manipulation
 */

import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Format currency value based on symbol
 */
export function formatCurrency(value: number, symbol?: string): string {
  if (typeof value !== 'number' || isNaN(value)) {
    return '--';
  }

  // Determine decimal places based on symbol
  let decimals = 5; // Default for forex
  
  if (symbol) {
    if (symbol.includes('JPY')) {
      decimals = 3; // Japanese Yen pairs
    } else if (symbol.startsWith('BTC') || symbol.startsWith('ETH')) {
      decimals = 2; // Crypto
    } else if (/^[A-Z]{3,4}$/.test(symbol) && !symbol.includes('USD')) {
      decimals = 4; // Other forex pairs
    }
  }

  return value.toFixed(decimals);
}

/**
 * Format percentage value
 */
export function formatPercentage(value: number): string {
  if (typeof value !== 'number' || isNaN(value)) {
    return '0.00%';
  }

  return `${value.toFixed(2)}%`;
}

/**
 * Format date and time for display
 */
export function formatDateTime(timestamp: string | number | Date): string {
  const date = new Date(timestamp);
  
  if (isNaN(date.getTime())) {
    return 'Invalid Date';
  }

  // Format as MM/DD HH:MM
  return date.toLocaleString('en-US', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false
  });
}

/**
 * Format relative time (e.g., "2 minutes ago")
 */
export function formatRelativeTime(timestamp: string | number | Date): string {
  const date = new Date(timestamp);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  
  const diffSeconds = Math.floor(diffMs / 1000);
  const diffMinutes = Math.floor(diffSeconds / 60);
  const diffHours = Math.floor(diffMinutes / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffSeconds < 60) return 'just now';
  if (diffMinutes < 60) return `${diffMinutes}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  
  return date.toLocaleDateString();
}

/**
 * Format large numbers with K/M/B suffixes
 */
export function formatNumber(value: number): string {
  if (typeof value !== 'number' || isNaN(value)) {
    return '0';
  }

  const absValue = Math.abs(value);
  
  if (absValue >= 1e9) {
    return `${(value / 1e9).toFixed(1)}B`;
  }
  
  if (absValue >= 1e6) {
    return `${(value / 1e6).toFixed(1)}M`;
  }
  
  if (absValue >= 1e3) {
    return `${(value / 1e3).toFixed(1)}K`;
  }
  
  return value.toFixed(0);
}

/**
 * Calculate price change color class
 */
export function getPriceChangeColor(change: number): string {
  if (change > 0) return 'text-green-500';
  if (change < 0) return 'text-red-500';
  return 'text-gray-400';
}

/**
 * Get symbol display name
 */
export function getSymbolDisplayName(symbol: string): string {
  // Common forex pair display names
  const forexPairs: Record<string, string> = {
    'EURUSD': 'EUR/USD',
    'GBPUSD': 'GBP/USD',
    'USDJPY': 'USD/JPY',
    'USDCHF': 'USD/CHF',
    'AUDUSD': 'AUD/USD',
    'USDCAD': 'USD/CAD',
    'NZDUSD': 'NZD/USD',
    'EURGBP': 'EUR/GBP',
    'EURJPY': 'EUR/JPY',
    'GBPJPY': 'GBP/JPY',
    'EURCHF': 'EUR/CHF',
    'GBPCHF': 'GBP/CHF',
    'CADCHF': 'CAD/CHF',
    'AUDJPY': 'AUD/JPY',
    'NZDJPY': 'NZD/JPY'
  };

  return forexPairs[symbol] || symbol;
}

/**
 * Validate email address
 */
export function isValidEmail(email: string): boolean {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return emailRegex.test(email);
}

/**
 * Generate random ID
 */
export function generateId(): string {
  return Math.random().toString(36).substr(2, 9);
}

/**
 * Debounce function
 */
export function debounce<T extends (...args: any[]) => any>(
  func: T,
  delay: number
): (...args: Parameters<T>) => void {
  let timeoutId: NodeJS.Timeout;
  
  return (...args: Parameters<T>) => {
    clearTimeout(timeoutId);
    timeoutId = setTimeout(() => func.apply(null, args), delay);
  };
}

/**
 * Throttle function
 */
export function throttle<T extends (...args: any[]) => any>(
  func: T,
  delay: number
): (...args: Parameters<T>) => void {
  let lastCall = 0;
  
  return (...args: Parameters<T>) => {
    const now = Date.now();
    
    if (now - lastCall >= delay) {
      lastCall = now;
      func.apply(null, args);
    }
  };
}

/**
 * Deep clone object
 */
export function deepClone<T>(obj: T): T {
  if (obj === null || typeof obj !== 'object') {
    return obj;
  }
  
  if (obj instanceof Date) {
    return new Date(obj.getTime()) as unknown as T;
  }
  
  if (obj instanceof Array) {
    return obj.map(item => deepClone(item)) as unknown as T;
  }
  
  if (typeof obj === 'object') {
    const copy = {} as { [key in keyof T]: T[key] };
    
    for (const key in obj) {
      if (obj.hasOwnProperty(key)) {
        copy[key] = deepClone(obj[key]);
      }
    }
    
    return copy;
  }
  
  return obj;
}

/**
 * Calculate lot size for position sizing
 */
export function calculateLotSize(
  accountBalance: number,
  riskPercent: number,
  stopLossPips: number,
  pipValue: number
): number {
  const riskAmount = accountBalance * (riskPercent / 100);
  const lotSize = riskAmount / (stopLossPips * pipValue);
  
  // Round to nearest 0.01 lot
  return Math.round(lotSize * 100) / 100;
}

/**
 * Calculate pip value for a given symbol
 */
export function calculatePipValue(
  symbol: string,
  lotSize: number = 1,
  accountCurrency: string = 'USD'
): number {
  // Simplified pip value calculation
  // In a real application, this would need to account for cross rates
  
  if (symbol.includes('JPY')) {
    return 0.01 * lotSize; // JPY pairs: 1 pip = 0.01
  }
  
  return 0.0001 * lotSize; // Most other pairs: 1 pip = 0.0001
}

/**
 * Safe JSON parse with fallback
 */
export function safeJsonParse<T>(json: string, fallback: T): T {
  try {
    return JSON.parse(json);
  } catch {
    return fallback;
  }
}

/**
 * Format storage size (bytes to human readable)
 */
export function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}