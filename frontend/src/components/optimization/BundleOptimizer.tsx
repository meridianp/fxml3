/**
 * Bundle Optimizer Component
 *
 * Development tool for monitoring and optimizing bundle performance
 */

import React, { useState, useEffect, useCallback } from 'react';
import { useBundlePerformance } from '../../hooks/useLazyLoad';

interface BundleInfo {
  name: string;
  size: number;
  loadTime: number;
  status: 'loading' | 'loaded' | 'error';
  priority: 'high' | 'medium' | 'low';
}

interface BundleOptimizerProps {
  isVisible?: boolean;
  position?: 'top-right' | 'bottom-right' | 'bottom-left';
}

export const BundleOptimizer: React.FC<BundleOptimizerProps> = ({
  isVisible = process.env.NODE_ENV === 'development',
  position = 'bottom-right'
}) => {
  const [bundles, setBundles] = useState<BundleInfo[]>([]);
  const [isExpanded, setIsExpanded] = useState(false);
  const [totalSize, setTotalSize] = useState(0);
  const [recommendations, setRecommendations] = useState<string[]>([]);

  const { metrics, getAverageLoadTime, getSlowestChunk } = useBundlePerformance();

  // Monitor bundle loading
  useEffect(() => {
    if (typeof window !== 'undefined') {
      // Monitor chunk loading events
      const originalImport = window.__webpack_require__;

      if (originalImport) {
        window.__webpack_require__ = function(...args) {
          const chunkId = args[0];
          const startTime = performance.now();

          try {
            const result = originalImport.apply(this, args);
            const endTime = performance.now();

            // Log chunk load
            setBundles(prev => {
              const existing = prev.find(b => b.name === `chunk-${chunkId}`);
              if (existing) {
                return prev.map(b =>
                  b.name === `chunk-${chunkId}`
                    ? { ...b, loadTime: endTime - startTime, status: 'loaded' as const }
                    : b
                );
              } else {
                return [...prev, {
                  name: `chunk-${chunkId}`,
                  size: 0, // Would need to be calculated
                  loadTime: endTime - startTime,
                  status: 'loaded' as const,
                  priority: 'medium' as const
                }];
              }
            });

            return result;
          } catch (error) {
            setBundles(prev => prev.map(b =>
              b.name === `chunk-${chunkId}`
                ? { ...b, status: 'error' as const }
                : b
            ));
            throw error;
          }
        };
      }
    }
  }, []);

  // Analyze performance and generate recommendations
  useEffect(() => {
    const newRecommendations: string[] = [];

    // Check for slow loading chunks
    const slowChunk = getSlowestChunk();
    if (slowChunk && slowChunk.duration > 1000) {
      newRecommendations.push(`Slow chunk detected: ${slowChunk.chunkName} (${slowChunk.duration.toFixed(2)}ms)`);
    }

    // Check average load time
    const avgLoadTime = getAverageLoadTime();
    if (avgLoadTime > 500) {
      newRecommendations.push(`High average load time: ${avgLoadTime.toFixed(2)}ms`);
    }

    // Check number of chunks
    if (bundles.length > 20) {
      newRecommendations.push(`Many chunks loaded (${bundles.length}). Consider consolidation.`);
    }

    // Check for failed loads
    const failedBundles = bundles.filter(b => b.status === 'error');
    if (failedBundles.length > 0) {
      newRecommendations.push(`${failedBundles.length} chunks failed to load`);
    }

    setRecommendations(newRecommendations);
  }, [bundles, metrics, getAverageLoadTime, getSlowestChunk]);

  const handleOptimize = useCallback(() => {
    // Trigger optimization actions
    console.group('🎯 Bundle Optimization');
    console.log('Current bundles:', bundles);
    console.log('Performance metrics:', metrics);
    console.log('Recommendations:', recommendations);
    console.groupEnd();

    // Could trigger actual optimization actions here
    alert('Optimization analysis logged to console');
  }, [bundles, metrics, recommendations]);

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const formatTime = (ms: number) => {
    return `${ms.toFixed(2)}ms`;
  };

  const getPositionClasses = () => {
    const base = 'fixed z-50';
    switch (position) {
      case 'top-right':
        return `${base} top-4 right-4`;
      case 'bottom-left':
        return `${base} bottom-4 left-4`;
      case 'bottom-right':
      default:
        return `${base} bottom-4 right-4`;
    }
  };

  if (!isVisible) return null;

  return (
    <div className={getPositionClasses()}>
      <div className="bg-gray-900 text-white rounded-lg shadow-lg border border-gray-700 max-w-sm">
        {/* Header */}
        <div
          className="flex items-center justify-between p-3 cursor-pointer hover:bg-gray-800 rounded-t-lg"
          onClick={() => setIsExpanded(!isExpanded)}
        >
          <div className="flex items-center space-x-2">
            <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
            <span className="text-sm font-semibold">Bundle Monitor</span>
          </div>
          <div className="flex items-center space-x-2">
            <span className="text-xs text-gray-400">
              {bundles.length} chunks
            </span>
            <svg
              className={`w-4 h-4 transform transition-transform ${isExpanded ? 'rotate-180' : ''}`}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </div>
        </div>

        {/* Expanded Content */}
        {isExpanded && (
          <div className="border-t border-gray-700">
            {/* Summary */}
            <div className="p-3 border-b border-gray-700">
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div>
                  <span className="text-gray-400">Total Size:</span>
                  <div className="font-mono">{formatBytes(totalSize)}</div>
                </div>
                <div>
                  <span className="text-gray-400">Avg Load:</span>
                  <div className="font-mono">{formatTime(getAverageLoadTime())}</div>
                </div>
              </div>
            </div>

            {/* Bundle List */}
            <div className="max-h-48 overflow-y-auto">
              {bundles.slice(0, 10).map((bundle, index) => (
                <div key={bundle.name} className="px-3 py-2 border-b border-gray-800 last:border-b-0">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      <div className={`w-2 h-2 rounded-full ${
                        bundle.status === 'loaded' ? 'bg-green-400' :
                        bundle.status === 'loading' ? 'bg-yellow-400' : 'bg-red-400'
                      }`}></div>
                      <span className="text-xs font-mono truncate max-w-[120px]">
                        {bundle.name}
                      </span>
                    </div>
                    <div className="text-xs text-gray-400">
                      {formatTime(bundle.loadTime)}
                    </div>
                  </div>
                  {bundle.size > 0 && (
                    <div className="text-xs text-gray-500 mt-1">
                      {formatBytes(bundle.size)}
                    </div>
                  )}
                </div>
              ))}

              {bundles.length > 10 && (
                <div className="px-3 py-2 text-xs text-gray-500 text-center">
                  ... and {bundles.length - 10} more
                </div>
              )}
            </div>

            {/* Recommendations */}
            {recommendations.length > 0 && (
              <div className="p-3 border-t border-gray-700">
                <div className="text-xs text-gray-400 mb-2">Recommendations:</div>
                {recommendations.slice(0, 3).map((rec, index) => (
                  <div key={index} className="text-xs text-yellow-400 mb-1">
                    • {rec}
                  </div>
                ))}
              </div>
            )}

            {/* Actions */}
            <div className="p-3 border-t border-gray-700">
              <div className="flex space-x-2">
                <button
                  onClick={handleOptimize}
                  className="flex-1 bg-blue-600 hover:bg-blue-700 text-white text-xs py-2 px-3 rounded"
                >
                  Analyze
                </button>
                <button
                  onClick={() => setBundles([])}
                  className="flex-1 bg-gray-600 hover:bg-gray-700 text-white text-xs py-2 px-3 rounded"
                >
                  Clear
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

// Hook for bundle monitoring in development
export function useBundleMonitor() {
  const [isEnabled, setIsEnabled] = useState(
    process.env.NODE_ENV === 'development' &&
    typeof window !== 'undefined' &&
    window.localStorage.getItem('bundle-monitor') !== 'false'
  );

  const enable = useCallback(() => {
    setIsEnabled(true);
    if (typeof window !== 'undefined') {
      window.localStorage.setItem('bundle-monitor', 'true');
    }
  }, []);

  const disable = useCallback(() => {
    setIsEnabled(false);
    if (typeof window !== 'undefined') {
      window.localStorage.setItem('bundle-monitor', 'false');
    }
  }, []);

  return {
    isEnabled,
    enable,
    disable
  };
}

// Performance metrics display component
export const PerformanceMetrics: React.FC = () => {
  const [metrics, setMetrics] = useState<any>(null);

  useEffect(() => {
    if (typeof window !== 'undefined' && 'performance' in window) {
      const paintMetrics = performance.getEntriesByType('paint');
      const navigationMetrics = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming;

      setMetrics({
        fcp: paintMetrics.find(metric => metric.name === 'first-contentful-paint')?.startTime || 0,
        lcp: 0, // Would need PerformanceObserver for LCP
        cls: 0, // Would need PerformanceObserver for CLS
        fid: 0, // Would need PerformanceObserver for FID
        ttfb: navigationMetrics?.responseStart - navigationMetrics?.requestStart || 0,
        domLoad: navigationMetrics?.domContentLoadedEventEnd - navigationMetrics?.domContentLoadedEventStart || 0,
        windowLoad: navigationMetrics?.loadEventEnd - navigationMetrics?.loadEventStart || 0
      });
    }
  }, []);

  if (!metrics || process.env.NODE_ENV !== 'development') return null;

  return (
    <div className="fixed top-4 left-4 bg-black bg-opacity-75 text-white text-xs p-2 rounded font-mono z-50">
      <div>FCP: {metrics.fcp.toFixed(0)}ms</div>
      <div>TTFB: {metrics.ttfb.toFixed(0)}ms</div>
      <div>DOM: {metrics.domLoad.toFixed(0)}ms</div>
      <div>Load: {metrics.windowLoad.toFixed(0)}ms</div>
    </div>
  );
};
