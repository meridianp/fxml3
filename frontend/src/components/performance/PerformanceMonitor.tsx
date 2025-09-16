/**
 * Performance Monitor Component
 *
 * Real-time performance monitoring with Core Web Vitals tracking
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { getCLS, getFCP, getFID, getLCP, getTTFB } from 'web-vitals';

interface PerformanceMetric {
  name: string;
  value: number;
  rating: 'good' | 'needs-improvement' | 'poor';
  threshold: { good: number; poor: number };
  unit: string;
  timestamp: number;
}

interface PerformanceData {
  coreWebVitals: {
    cls: PerformanceMetric | null;
    fcp: PerformanceMetric | null;
    fid: PerformanceMetric | null;
    lcp: PerformanceMetric | null;
    ttfb: PerformanceMetric | null;
  };
  customMetrics: {
    memoryUsage: number;
    networkLatency: number;
    renderTime: number;
    bundleLoadTime: number;
    apiResponseTime: number;
  };
  performanceEntries: PerformanceEntry[];
  isRecording: boolean;
}

interface PerformanceMonitorProps {
  isVisible?: boolean;
  autoRecord?: boolean;
  sampleRate?: number;
  onMetricChange?: (metric: PerformanceMetric) => void;
}

const defaultThresholds = {
  cls: { good: 0.1, poor: 0.25 },
  fcp: { good: 1800, poor: 3000 },
  fid: { good: 100, poor: 300 },
  lcp: { good: 2500, poor: 4000 },
  ttfb: { good: 800, poor: 1800 }
};

export const PerformanceMonitor: React.FC<PerformanceMonitorProps> = ({
  isVisible = process.env.NODE_ENV === 'development',
  autoRecord = true,
  sampleRate = 0.1,
  onMetricChange
}) => {
  const [performanceData, setPerformanceData] = useState<PerformanceData>({
    coreWebVitals: {
      cls: null,
      fcp: null,
      fid: null,
      lcp: null,
      ttfb: null
    },
    customMetrics: {
      memoryUsage: 0,
      networkLatency: 0,
      renderTime: 0,
      bundleLoadTime: 0,
      apiResponseTime: 0
    },
    performanceEntries: [],
    isRecording: false
  });

  const [isExpanded, setIsExpanded] = useState(false);
  const [recordingHistory, setRecordingHistory] = useState<PerformanceMetric[]>([]);
  const observerRef = useRef<PerformanceObserver>();
  const intervalRef = useRef<NodeJS.Timeout>();

  // Initialize Core Web Vitals monitoring
  useEffect(() => {
    if (!autoRecord || Math.random() > sampleRate) return;

    const createMetric = (
      name: string,
      value: number,
      unit: string = 'ms'
    ): PerformanceMetric => {
      const threshold = defaultThresholds[name as keyof typeof defaultThresholds];
      const rating = !threshold ? 'good' :
        value <= threshold.good ? 'good' :
        value <= threshold.poor ? 'needs-improvement' : 'poor';

      return {
        name,
        value,
        rating,
        threshold: threshold || { good: 0, poor: 0 },
        unit,
        timestamp: Date.now()
      };
    };

    // Cumulative Layout Shift
    getCLS((metric) => {
      const clsMetric = createMetric('cls', metric.value, '');
      setPerformanceData(prev => ({
        ...prev,
        coreWebVitals: { ...prev.coreWebVitals, cls: clsMetric }
      }));
      onMetricChange?.(clsMetric);
    });

    // First Contentful Paint
    getFCP((metric) => {
      const fcpMetric = createMetric('fcp', metric.value);
      setPerformanceData(prev => ({
        ...prev,
        coreWebVitals: { ...prev.coreWebVitals, fcp: fcpMetric }
      }));
      onMetricChange?.(fcpMetric);
    });

    // First Input Delay
    getFID((metric) => {
      const fidMetric = createMetric('fid', metric.value);
      setPerformanceData(prev => ({
        ...prev,
        coreWebVitals: { ...prev.coreWebVitals, fid: fidMetric }
      }));
      onMetricChange?.(fidMetric);
    });

    // Largest Contentful Paint
    getLCP((metric) => {
      const lcpMetric = createMetric('lcp', metric.value);
      setPerformanceData(prev => ({
        ...prev,
        coreWebVitals: { ...prev.coreWebVitals, lcp: lcpMetric }
      }));
      onMetricChange?.(lcpMetric);
    });

    // Time to First Byte
    getTTFB((metric) => {
      const ttfbMetric = createMetric('ttfb', metric.value);
      setPerformanceData(prev => ({
        ...prev,
        coreWebVitals: { ...prev.coreWebVitals, ttfb: ttfbMetric }
      }));
      onMetricChange?.(ttfbMetric);
    });

  }, [autoRecord, sampleRate, onMetricChange]);

  // Monitor custom performance metrics
  useEffect(() => {
    if (!isVisible) return;

    const updateCustomMetrics = () => {
      const customMetrics = {
        memoryUsage: getMemoryUsage(),
        networkLatency: getNetworkLatency(),
        renderTime: getRenderTime(),
        bundleLoadTime: getBundleLoadTime(),
        apiResponseTime: getApiResponseTime()
      };

      setPerformanceData(prev => ({
        ...prev,
        customMetrics
      }));
    };

    // Update custom metrics every 5 seconds
    intervalRef.current = setInterval(updateCustomMetrics, 5000);
    updateCustomMetrics(); // Initial update

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [isVisible]);

  // Performance observer for navigation and resource timing
  useEffect(() => {
    if (typeof window === 'undefined') return;

    try {
      observerRef.current = new PerformanceObserver((list) => {
        const entries = list.getEntries();
        setPerformanceData(prev => ({
          ...prev,
          performanceEntries: [...prev.performanceEntries, ...entries].slice(-50) // Keep last 50 entries
        }));
      });

      observerRef.current.observe({
        entryTypes: ['navigation', 'resource', 'paint', 'layout-shift', 'first-input']
      });

    } catch (error) {
      console.warn('PerformanceObserver not supported:', error);
    }

    return () => {
      if (observerRef.current) {
        observerRef.current.disconnect();
      }
    };
  }, []);

  // Start/stop performance recording
  const toggleRecording = useCallback(() => {
    setPerformanceData(prev => ({
      ...prev,
      isRecording: !prev.isRecording
    }));
  }, []);

  // Clear performance data
  const clearData = useCallback(() => {
    setPerformanceData(prev => ({
      ...prev,
      performanceEntries: [],
      customMetrics: {
        memoryUsage: 0,
        networkLatency: 0,
        renderTime: 0,
        bundleLoadTime: 0,
        apiResponseTime: 0
      }
    }));
    setRecordingHistory([]);
  }, []);

  // Export performance data
  const exportData = useCallback(() => {
    const exportData = {
      timestamp: new Date().toISOString(),
      url: window.location.href,
      userAgent: navigator.userAgent,
      coreWebVitals: performanceData.coreWebVitals,
      customMetrics: performanceData.customMetrics,
      performanceEntries: performanceData.performanceEntries.map(entry => ({
        name: entry.name,
        entryType: entry.entryType,
        startTime: entry.startTime,
        duration: entry.duration
      })),
      recordingHistory
    };

    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `performance-data-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }, [performanceData, recordingHistory]);

  const getMetricColor = (metric: PerformanceMetric | null) => {
    if (!metric) return 'text-gray-400';
    switch (metric.rating) {
      case 'good': return 'text-green-500';
      case 'needs-improvement': return 'text-yellow-500';
      case 'poor': return 'text-red-500';
      default: return 'text-gray-400';
    }
  };

  const formatValue = (metric: PerformanceMetric | null) => {
    if (!metric) return '-';
    const value = metric.unit === '' ? metric.value.toFixed(3) : metric.value.toFixed(0);
    return `${value}${metric.unit}`;
  };

  if (!isVisible) return null;

  return (
    <div className="fixed top-4 right-4 z-50">
      <div className="bg-gray-900 text-white rounded-lg shadow-lg border border-gray-700 max-w-md">
        {/* Header */}
        <div
          className="flex items-center justify-between p-3 cursor-pointer hover:bg-gray-800 rounded-t-lg"
          onClick={() => setIsExpanded(!isExpanded)}
        >
          <div className="flex items-center space-x-2">
            <div className={`w-2 h-2 rounded-full ${
              performanceData.isRecording ? 'bg-red-400 animate-pulse' : 'bg-green-400'
            }`}></div>
            <span className="text-sm font-semibold">Performance Monitor</span>
          </div>
          <svg
            className={`w-4 h-4 transform transition-transform ${isExpanded ? 'rotate-180' : ''}`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </div>

        {/* Expanded Content */}
        {isExpanded && (
          <div className="border-t border-gray-700">
            {/* Core Web Vitals */}
            <div className="p-3 border-b border-gray-700">
              <h4 className="text-xs font-semibold text-gray-300 mb-2">Core Web Vitals</h4>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div>
                  <span className="text-gray-400">CLS:</span>
                  <div className={`font-mono ${getMetricColor(performanceData.coreWebVitals.cls)}`}>
                    {formatValue(performanceData.coreWebVitals.cls)}
                  </div>
                </div>
                <div>
                  <span className="text-gray-400">FCP:</span>
                  <div className={`font-mono ${getMetricColor(performanceData.coreWebVitals.fcp)}`}>
                    {formatValue(performanceData.coreWebVitals.fcp)}
                  </div>
                </div>
                <div>
                  <span className="text-gray-400">FID:</span>
                  <div className={`font-mono ${getMetricColor(performanceData.coreWebVitals.fid)}`}>
                    {formatValue(performanceData.coreWebVitals.fid)}
                  </div>
                </div>
                <div>
                  <span className="text-gray-400">LCP:</span>
                  <div className={`font-mono ${getMetricColor(performanceData.coreWebVitals.lcp)}`}>
                    {formatValue(performanceData.coreWebVitals.lcp)}
                  </div>
                </div>
                <div>
                  <span className="text-gray-400">TTFB:</span>
                  <div className={`font-mono ${getMetricColor(performanceData.coreWebVitals.ttfb)}`}>
                    {formatValue(performanceData.coreWebVitals.ttfb)}
                  </div>
                </div>
              </div>
            </div>

            {/* Custom Metrics */}
            <div className="p-3 border-b border-gray-700">
              <h4 className="text-xs font-semibold text-gray-300 mb-2">Custom Metrics</h4>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div>
                  <span className="text-gray-400">Memory:</span>
                  <div className="font-mono">{formatMemory(performanceData.customMetrics.memoryUsage)}</div>
                </div>
                <div>
                  <span className="text-gray-400">Network:</span>
                  <div className="font-mono">{performanceData.customMetrics.networkLatency.toFixed(0)}ms</div>
                </div>
                <div>
                  <span className="text-gray-400">Render:</span>
                  <div className="font-mono">{performanceData.customMetrics.renderTime.toFixed(0)}ms</div>
                </div>
                <div>
                  <span className="text-gray-400">Bundle:</span>
                  <div className="font-mono">{performanceData.customMetrics.bundleLoadTime.toFixed(0)}ms</div>
                </div>
              </div>
            </div>

            {/* Performance Entries */}
            <div className="p-3 border-b border-gray-700">
              <h4 className="text-xs font-semibold text-gray-300 mb-2">
                Recent Entries ({performanceData.performanceEntries.length})
              </h4>
              <div className="max-h-24 overflow-y-auto space-y-1">
                {performanceData.performanceEntries.slice(-5).map((entry, index) => (
                  <div key={index} className="flex justify-between text-xs">
                    <span className="truncate max-w-[150px]">{entry.name}</span>
                    <span className="text-gray-400">{entry.duration?.toFixed(0)}ms</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Actions */}
            <div className="p-3">
              <div className="flex space-x-2">
                <button
                  onClick={toggleRecording}
                  className={`flex-1 py-2 px-3 rounded text-xs font-medium ${
                    performanceData.isRecording
                      ? 'bg-red-600 hover:bg-red-700'
                      : 'bg-green-600 hover:bg-green-700'
                  }`}
                >
                  {performanceData.isRecording ? 'Stop' : 'Record'}
                </button>
                <button
                  onClick={exportData}
                  className="flex-1 bg-blue-600 hover:bg-blue-700 py-2 px-3 rounded text-xs font-medium"
                >
                  Export
                </button>
                <button
                  onClick={clearData}
                  className="flex-1 bg-gray-600 hover:bg-gray-700 py-2 px-3 rounded text-xs font-medium"
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

// Helper functions for custom metrics
function getMemoryUsage(): number {
  if (typeof window !== 'undefined' && 'performance' in window && 'memory' in performance) {
    return (performance as any).memory.usedJSHeapSize || 0;
  }
  return 0;
}

function getNetworkLatency(): number {
  if (typeof window !== 'undefined' && 'performance' in window) {
    const navigation = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming;
    return navigation ? navigation.responseStart - navigation.connectStart : 0;
  }
  return 0;
}

function getRenderTime(): number {
  if (typeof window !== 'undefined' && 'performance' in window) {
    const navigation = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming;
    return navigation ? navigation.domComplete - navigation.domLoading : 0;
  }
  return 0;
}

function getBundleLoadTime(): number {
  if (typeof window !== 'undefined' && 'performance' in window) {
    const resources = performance.getEntriesByType('resource');
    const jsResources = resources.filter(resource => resource.name.includes('.js'));
    return jsResources.reduce((total, resource) => total + resource.duration, 0);
  }
  return 0;
}

function getApiResponseTime(): number {
  if (typeof window !== 'undefined' && 'performance' in window) {
    const resources = performance.getEntriesByType('resource');
    const apiResources = resources.filter(resource =>
      resource.name.includes('/api/') || resource.name.includes('api.')
    );

    if (apiResources.length === 0) return 0;

    const totalTime = apiResources.reduce((total, resource) => total + resource.duration, 0);
    return totalTime / apiResources.length;
  }
  return 0;
}

function formatMemory(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}
