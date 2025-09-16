/**
 * Resource Monitor Component
 *
 * Monitors resource usage, network requests, and system performance
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { usePerformanceBudget } from '../../hooks/usePerformanceOptimization';

interface NetworkRequest {
  url: string;
  method: string;
  status: number;
  duration: number;
  size: number;
  type: string;
  timestamp: number;
}

interface ResourceUsage {
  memory: {
    used: number;
    total: number;
    limit: number;
  };
  cpu: {
    usage: number;
    cores: number;
  };
  network: {
    requests: NetworkRequest[];
    totalSize: number;
    avgResponseTime: number;
  };
  storage: {
    localStorage: number;
    sessionStorage: number;
    indexedDB: number;
  };
}

interface ResourceMonitorProps {
  isVisible?: boolean;
  updateInterval?: number;
  maxRequestHistory?: number;
  enableNetworkMonitoring?: boolean;
  enableStorageMonitoring?: boolean;
}

export const ResourceMonitor: React.FC<ResourceMonitorProps> = ({
  isVisible = process.env.NODE_ENV === 'development',
  updateInterval = 2000,
  maxRequestHistory = 50,
  enableNetworkMonitoring = true,
  enableStorageMonitoring = true
}) => {
  const [resourceUsage, setResourceUsage] = useState<ResourceUsage>({
    memory: { used: 0, total: 0, limit: 0 },
    cpu: { usage: 0, cores: 1 },
    network: { requests: [], totalSize: 0, avgResponseTime: 0 },
    storage: { localStorage: 0, sessionStorage: 0, indexedDB: 0 }
  });

  const [isExpanded, setIsExpanded] = useState(false);
  const [alerts, setAlerts] = useState<string[]>([]);
  const performanceObserverRef = useRef<PerformanceObserver>();
  const intervalRef = useRef<NodeJS.Timeout>();
  const networkInterceptRef = useRef<any>();

  // Performance budget monitoring
  const { budgetStatus, overallStatus } = usePerformanceBudget({
    bundleSize: 500 * 1024, // 500KB
    loadTime: 3000, // 3 seconds
    memoryUsage: 50 * 1024 * 1024 // 50MB
  });

  // Initialize resource monitoring
  useEffect(() => {
    if (!isVisible) return;

    const updateResources = () => {
      setResourceUsage(prev => ({
        ...prev,
        memory: getMemoryUsage(),
        cpu: getCPUUsage(),
        storage: enableStorageMonitoring ? getStorageUsage() : prev.storage
      }));
    };

    // Initial update
    updateResources();

    // Set up interval for resource updates
    intervalRef.current = setInterval(updateResources, updateInterval);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [isVisible, updateInterval, enableStorageMonitoring]);

  // Network monitoring
  useEffect(() => {
    if (!isVisible || !enableNetworkMonitoring) return;

    // Monitor resource timing for network requests
    if (typeof window !== 'undefined' && 'PerformanceObserver' in window) {
      performanceObserverRef.current = new PerformanceObserver((list) => {
        const entries = list.getEntries();
        const newRequests: NetworkRequest[] = [];

        entries.forEach(entry => {
          if (entry.entryType === 'resource') {
            const resourceEntry = entry as PerformanceResourceTiming;

            newRequests.push({
              url: resourceEntry.name,
              method: 'GET', // PerformanceResourceTiming doesn't provide method
              status: 200, // Assume success if in performance timeline
              duration: resourceEntry.duration,
              size: resourceEntry.transferSize || 0,
              type: getResourceType(resourceEntry.name),
              timestamp: Date.now()
            });
          }
        });

        if (newRequests.length > 0) {
          setResourceUsage(prev => {
            const allRequests = [...prev.network.requests, ...newRequests]
              .slice(-maxRequestHistory);

            const totalSize = allRequests.reduce((sum, req) => sum + req.size, 0);
            const avgResponseTime = allRequests.length > 0
              ? allRequests.reduce((sum, req) => sum + req.duration, 0) / allRequests.length
              : 0;

            return {
              ...prev,
              network: {
                requests: allRequests,
                totalSize,
                avgResponseTime
              }
            };
          });
        }
      });

      performanceObserverRef.current.observe({ entryTypes: ['resource'] });
    }

    // Intercept fetch requests for more detailed monitoring
    if (typeof window !== 'undefined') {
      const originalFetch = window.fetch;

      window.fetch = async function(...args) {
        const startTime = performance.now();
        const url = typeof args[0] === 'string' ? args[0] : args[0].url;
        const method = args[1]?.method || 'GET';

        try {
          const response = await originalFetch.apply(this, args);
          const endTime = performance.now();

          const newRequest: NetworkRequest = {
            url,
            method,
            status: response.status,
            duration: endTime - startTime,
            size: parseInt(response.headers.get('content-length') || '0'),
            type: 'fetch',
            timestamp: Date.now()
          };

          setResourceUsage(prev => {
            const allRequests = [...prev.network.requests, newRequest]
              .slice(-maxRequestHistory);

            const totalSize = allRequests.reduce((sum, req) => sum + req.size, 0);
            const avgResponseTime = allRequests.length > 0
              ? allRequests.reduce((sum, req) => sum + req.duration, 0) / allRequests.length
              : 0;

            return {
              ...prev,
              network: {
                requests: allRequests,
                totalSize,
                avgResponseTime
              }
            };
          });

          return response;
        } catch (error) {
          const endTime = performance.now();

          const newRequest: NetworkRequest = {
            url,
            method,
            status: 0,
            duration: endTime - startTime,
            size: 0,
            type: 'fetch',
            timestamp: Date.now()
          };

          setResourceUsage(prev => ({
            ...prev,
            network: {
              ...prev.network,
              requests: [...prev.network.requests, newRequest].slice(-maxRequestHistory)
            }
          }));

          throw error;
        }
      };

      networkInterceptRef.current = originalFetch;
    }

    return () => {
      if (performanceObserverRef.current) {
        performanceObserverRef.current.disconnect();
      }

      if (networkInterceptRef.current && typeof window !== 'undefined') {
        window.fetch = networkInterceptRef.current;
      }
    };
  }, [isVisible, enableNetworkMonitoring, maxRequestHistory]);

  // Monitor for resource alerts
  useEffect(() => {
    const newAlerts: string[] = [];

    // Memory alerts
    if (resourceUsage.memory.used > resourceUsage.memory.limit * 0.8) {
      newAlerts.push('High memory usage detected');
    }

    // Network alerts
    if (resourceUsage.network.avgResponseTime > 2000) {
      newAlerts.push('Slow network responses detected');
    }

    // Failed requests
    const recentFailures = resourceUsage.network.requests
      .filter(req => req.status >= 400 && Date.now() - req.timestamp < 60000);

    if (recentFailures.length > 3) {
      newAlerts.push(`${recentFailures.length} failed requests in last minute`);
    }

    // Bundle size alerts
    if (budgetStatus.bundleSize?.status === 'exceeded') {
      newAlerts.push('Bundle size budget exceeded');
    }

    setAlerts(newAlerts);
  }, [resourceUsage, budgetStatus]);

  const clearNetworkHistory = useCallback(() => {
    setResourceUsage(prev => ({
      ...prev,
      network: {
        ...prev.network,
        requests: []
      }
    }));
  }, []);

  const exportResourceData = useCallback(() => {
    const exportData = {
      timestamp: new Date().toISOString(),
      resourceUsage,
      budgetStatus,
      alerts,
      systemInfo: {
        userAgent: navigator.userAgent,
        platform: navigator.platform,
        language: navigator.language,
        cookieEnabled: navigator.cookieEnabled,
        onLine: navigator.onLine
      }
    };

    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `resource-monitor-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }, [resourceUsage, budgetStatus, alerts]);

  if (!isVisible) return null;

  return (
    <div className="fixed top-4 left-1/2 transform -translate-x-1/2 z-50">
      <div className="bg-gray-900 text-white rounded-lg shadow-lg border border-gray-700 max-w-lg">
        {/* Header */}
        <div
          className="flex items-center justify-between p-3 cursor-pointer hover:bg-gray-800 rounded-t-lg"
          onClick={() => setIsExpanded(!isExpanded)}
        >
          <div className="flex items-center space-x-2">
            <div className={`w-2 h-2 rounded-full ${
              overallStatus === 'exceeded' ? 'bg-red-400' :
              overallStatus === 'warning' ? 'bg-yellow-400' : 'bg-green-400'
            }`}></div>
            <span className="text-sm font-semibold">Resource Monitor</span>
            {alerts.length > 0 && (
              <span className="bg-red-600 text-xs px-2 py-1 rounded-full">
                {alerts.length}
              </span>
            )}
          </div>
          <div className="flex items-center space-x-2">
            <span className="text-xs text-gray-400">
              {formatBytes(resourceUsage.memory.used)}
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
            {/* Alerts */}
            {alerts.length > 0 && (
              <div className="p-3 border-b border-gray-700 bg-red-900 bg-opacity-50">
                <div className="text-xs font-semibold text-red-300 mb-1">Alerts</div>
                {alerts.map((alert, index) => (
                  <div key={index} className="text-xs text-red-200">
                    • {alert}
                  </div>
                ))}
              </div>
            )}

            {/* Memory Usage */}
            <div className="p-3 border-b border-gray-700">
              <h4 className="text-xs font-semibold text-gray-300 mb-2">Memory Usage</h4>
              <div className="flex items-center justify-between text-xs mb-1">
                <span>Used: {formatBytes(resourceUsage.memory.used)}</span>
                <span>Limit: {formatBytes(resourceUsage.memory.limit)}</span>
              </div>
              <div className="w-full bg-gray-700 rounded-full h-2">
                <div
                  className={`h-2 rounded-full ${
                    resourceUsage.memory.used / resourceUsage.memory.limit > 0.8 ? 'bg-red-500' :
                    resourceUsage.memory.used / resourceUsage.memory.limit > 0.6 ? 'bg-yellow-500' : 'bg-green-500'
                  }`}
                  style={{
                    width: `${Math.min((resourceUsage.memory.used / resourceUsage.memory.limit) * 100, 100)}%`
                  }}
                ></div>
              </div>
            </div>

            {/* Network Activity */}
            <div className="p-3 border-b border-gray-700">
              <div className="flex items-center justify-between mb-2">
                <h4 className="text-xs font-semibold text-gray-300">Network Activity</h4>
                <button
                  onClick={clearNetworkHistory}
                  className="text-xs text-gray-400 hover:text-white"
                >
                  Clear
                </button>
              </div>
              <div className="grid grid-cols-2 gap-2 text-xs mb-2">
                <div>
                  <span className="text-gray-400">Requests:</span>
                  <div className="font-mono">{resourceUsage.network.requests.length}</div>
                </div>
                <div>
                  <span className="text-gray-400">Avg Time:</span>
                  <div className="font-mono">{resourceUsage.network.avgResponseTime.toFixed(0)}ms</div>
                </div>
                <div>
                  <span className="text-gray-400">Total Size:</span>
                  <div className="font-mono">{formatBytes(resourceUsage.network.totalSize)}</div>
                </div>
                <div>
                  <span className="text-gray-400">Failed:</span>
                  <div className="font-mono text-red-400">
                    {resourceUsage.network.requests.filter(r => r.status >= 400).length}
                  </div>
                </div>
              </div>

              {/* Recent Requests */}
              <div className="max-h-24 overflow-y-auto space-y-1">
                {resourceUsage.network.requests.slice(-5).map((request, index) => (
                  <div key={index} className="flex justify-between text-xs">
                    <span className="truncate max-w-[200px]">
                      {request.url.split('/').pop() || request.url}
                    </span>
                    <div className="flex items-center space-x-2">
                      <span className={`${
                        request.status >= 400 ? 'text-red-400' :
                        request.status >= 300 ? 'text-yellow-400' : 'text-green-400'
                      }`}>
                        {request.status}
                      </span>
                      <span className="text-gray-400">{request.duration.toFixed(0)}ms</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Storage Usage */}
            {enableStorageMonitoring && (
              <div className="p-3 border-b border-gray-700">
                <h4 className="text-xs font-semibold text-gray-300 mb-2">Storage Usage</h4>
                <div className="grid grid-cols-3 gap-2 text-xs">
                  <div>
                    <span className="text-gray-400">Local:</span>
                    <div className="font-mono">{formatBytes(resourceUsage.storage.localStorage)}</div>
                  </div>
                  <div>
                    <span className="text-gray-400">Session:</span>
                    <div className="font-mono">{formatBytes(resourceUsage.storage.sessionStorage)}</div>
                  </div>
                  <div>
                    <span className="text-gray-400">IndexedDB:</span>
                    <div className="font-mono">{formatBytes(resourceUsage.storage.indexedDB)}</div>
                  </div>
                </div>
              </div>
            )}

            {/* Performance Budget */}
            <div className="p-3 border-b border-gray-700">
              <h4 className="text-xs font-semibold text-gray-300 mb-2">Performance Budget</h4>
              {Object.entries(budgetStatus).map(([key, status]) => (
                <div key={key} className="mb-1">
                  <div className="flex justify-between text-xs">
                    <span className="capitalize">{key}:</span>
                    <span className={`${
                      status.status === 'exceeded' ? 'text-red-400' :
                      status.status === 'warning' ? 'text-yellow-400' : 'text-green-400'
                    }`}>
                      {status.percentage.toFixed(0)}%
                    </span>
                  </div>
                  <div className="w-full bg-gray-700 rounded-full h-1">
                    <div
                      className={`h-1 rounded-full ${
                        status.status === 'exceeded' ? 'bg-red-500' :
                        status.status === 'warning' ? 'bg-yellow-500' : 'bg-green-500'
                      }`}
                      style={{ width: `${Math.min(status.percentage, 100)}%` }}
                    ></div>
                  </div>
                </div>
              ))}
            </div>

            {/* Actions */}
            <div className="p-3">
              <button
                onClick={exportResourceData}
                className="w-full bg-blue-600 hover:bg-blue-700 text-white text-xs py-2 px-3 rounded"
              >
                Export Resource Data
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

// Helper functions
function getMemoryUsage() {
  if (typeof window !== 'undefined' && 'performance' in window && 'memory' in performance) {
    const memory = (performance as any).memory;
    return {
      used: memory.usedJSHeapSize || 0,
      total: memory.totalJSHeapSize || 0,
      limit: memory.jsHeapSizeLimit || 0
    };
  }
  return { used: 0, total: 0, limit: 0 };
}

function getCPUUsage() {
  // CPU usage is not directly available in browsers
  // This is a placeholder for future implementation
  return {
    usage: 0,
    cores: navigator.hardwareConcurrency || 1
  };
}

function getStorageUsage() {
  const getStorageSize = (storage: Storage) => {
    let total = 0;
    for (let key in storage) {
      if (storage.hasOwnProperty(key)) {
        total += storage[key].length + key.length;
      }
    }
    return total;
  };

  return {
    localStorage: typeof localStorage !== 'undefined' ? getStorageSize(localStorage) : 0,
    sessionStorage: typeof sessionStorage !== 'undefined' ? getStorageSize(sessionStorage) : 0,
    indexedDB: 0 // Would need more complex logic to calculate IndexedDB size
  };
}

function getResourceType(url: string): string {
  if (url.includes('.js')) return 'script';
  if (url.includes('.css')) return 'stylesheet';
  if (url.match(/\.(png|jpg|jpeg|gif|svg|webp)$/)) return 'image';
  if (url.includes('/api/') || url.includes('api.')) return 'api';
  return 'other';
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}
