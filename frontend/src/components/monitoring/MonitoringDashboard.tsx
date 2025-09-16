/**
 * Monitoring Dashboard Component
 *
 * Migrated from static HTML to React with real-time monitoring capabilities
 */

'use client';

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { useAppStore } from '@/stores/appStore';
import {
  ChartBarIcon,
  ServerIcon,
  CpuChipIcon,
  CircleStackIcon,
  BoltIcon,
  ArrowPathIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  ClockIcon,
  RocketLaunchIcon,
  CurrencyDollarIcon,
  TrendingUpIcon,
  SignalIcon
} from '@heroicons/react/24/outline';

interface SystemMetrics {
  timestamp: string;
  system_health: {
    status: 'healthy' | 'warning' | 'unhealthy';
    uptime_seconds: number;
    active_requests: number;
  };
  api_performance: {
    total_requests: number;
    error_requests: number;
    error_rate_percent: number;
    avg_response_time: number;
    requests_per_minute: number;
  };
  trading_performance: {
    total_orders: number;
    successful_orders: number;
    success_rate_percent: number;
    avg_execution_time: number;
    orders_per_minute: number;
  };
  fix_protocol: {
    total_messages: number;
    avg_processing_time: number;
    messages_per_minute: number;
    performance_improvement: string;
  };
  ml_performance: {
    total_inferences: number;
    successful_inferences: number;
    success_rate_percent: number;
    avg_inference_time: number;
    inferences_per_minute: number;
  };
  broker_adapters: Record<string, {
    total_operations: number;
    errors: number;
    avg_duration: number;
  }>;
  recent_activity: Array<{
    timestamp: string;
    event: string;
    details: string;
  }>;
  performance_trends: {
    timestamps: number[];
    api_response_times: number[];
    order_execution_times: number[];
    fix_processing_times: number[];
  };
}

export default function MonitoringDashboard() {
  const [activeTab, setActiveTab] = useState('overview');
  const [metrics, setMetrics] = useState<SystemMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [refreshInterval, setRefreshInterval] = useState(30000); // 30 seconds

  const { addNotification } = useAppStore();

  useEffect(() => {
    loadMetrics();
  }, []);

  useEffect(() => {
    let interval: NodeJS.Timeout;

    if (autoRefresh) {
      interval = setInterval(() => {
        loadMetrics();
      }, refreshInterval);
    }

    return () => {
      if (interval) clearInterval(interval);
    };
  }, [autoRefresh, refreshInterval]);

  const loadMetrics = async () => {
    try {
      // Simulate API call - in production, this would fetch from /monitoring/data
      const mockMetrics: SystemMetrics = {
        timestamp: new Date().toISOString(),
        system_health: {
          status: 'healthy',
          uptime_seconds: Math.floor(Date.now() / 1000) - 86400 * 5, // 5 days
          active_requests: Math.floor(Math.random() * 10) + 2
        },
        api_performance: {
          total_requests: 125847 + Math.floor(Math.random() * 100),
          error_requests: 234 + Math.floor(Math.random() * 5),
          error_rate_percent: 0.18 + Math.random() * 0.1,
          avg_response_time: 0.145 + Math.random() * 0.05,
          requests_per_minute: 45.2 + Math.random() * 10
        },
        trading_performance: {
          total_orders: 8934 + Math.floor(Math.random() * 50),
          successful_orders: 8867 + Math.floor(Math.random() * 45),
          success_rate_percent: 99.2 + Math.random() * 0.5,
          avg_execution_time: 0.089 + Math.random() * 0.02,
          orders_per_minute: 12.3 + Math.random() * 5
        },
        fix_protocol: {
          total_messages: 45623 + Math.floor(Math.random() * 200),
          avg_processing_time: 0.5 + Math.random() * 0.3,
          messages_per_minute: 234.5 + Math.random() * 50,
          performance_improvement: 'Fast FIX enabled'
        },
        ml_performance: {
          total_inferences: 15647 + Math.floor(Math.random() * 100),
          successful_inferences: 15589 + Math.floor(Math.random() * 95),
          success_rate_percent: 99.6 + Math.random() * 0.3,
          avg_inference_time: 0.234 + Math.random() * 0.1,
          inferences_per_minute: 87.2 + Math.random() * 20
        },
        broker_adapters: {
          'Interactive Brokers': {
            total_operations: 5634 + Math.floor(Math.random() * 50),
            errors: 12 + Math.floor(Math.random() * 3),
            avg_duration: 0.156 + Math.random() * 0.05
          },
          'FXCM': {
            total_operations: 2145 + Math.floor(Math.random() * 30),
            errors: 8 + Math.floor(Math.random() * 2),
            avg_duration: 0.203 + Math.random() * 0.08
          },
          'Manual': {
            total_operations: 89 + Math.floor(Math.random() * 10),
            errors: 2 + Math.floor(Math.random() * 1),
            avg_duration: 0.045 + Math.random() * 0.02
          }
        },
        recent_activity: [
          {
            timestamp: new Date(Date.now() - 30000).toISOString(),
            event: 'Order Executed',
            details: 'EURUSD buy order filled at 1.0847'
          },
          {
            timestamp: new Date(Date.now() - 65000).toISOString(),
            event: 'ML Inference',
            details: 'Signal generated for GBPUSD - Probability: 0.73'
          },
          {
            timestamp: new Date(Date.now() - 120000).toISOString(),
            event: 'FIX Message',
            details: 'ExecutionReport processed in 0.8ms'
          },
          {
            timestamp: new Date(Date.now() - 180000).toISOString(),
            event: 'Risk Check',
            details: 'Position size validated for USDJPY trade'
          },
          {
            timestamp: new Date(Date.now() - 240000).toISOString(),
            event: 'Model Update',
            details: 'LSTM model retrained with latest data'
          }
        ],
        performance_trends: {
          timestamps: Array.from({ length: 20 }, (_, i) => Date.now() - (19 - i) * 30000),
          api_response_times: Array.from({ length: 20 }, () => 0.1 + Math.random() * 0.4),
          order_execution_times: Array.from({ length: 20 }, () => 0.05 + Math.random() * 0.15),
          fix_processing_times: Array.from({ length: 20 }, () => 0.001 + Math.random() * 0.004)
        }
      };

      setMetrics(mockMetrics);
      setLoading(false);
    } catch (error) {
      console.error('Failed to load metrics:', error);
      addNotification({
        type: 'error',
        title: 'Metrics Error',
        message: 'Failed to load system metrics'
      });
      setLoading(false);
    }
  };

  const formatUptime = (seconds: number): string => {
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);

    if (days > 0) return `${days}d ${hours}h ${minutes}m`;
    if (hours > 0) return `${hours}h ${minutes}m`;
    return `${minutes}m`;
  };

  const formatTime = (timestamp: string): string => {
    return new Date(timestamp).toLocaleTimeString();
  };

  const getHealthColor = (status: string): string => {
    switch (status) {
      case 'healthy': return 'text-green-400 bg-green-500/20';
      case 'warning': return 'text-yellow-400 bg-yellow-500/20';
      case 'unhealthy': return 'text-red-400 bg-red-500/20';
      default: return 'text-gray-400 bg-gray-500/20';
    }
  };

  const getHealthIcon = (status: string) => {
    switch (status) {
      case 'healthy': return <CheckCircleIcon className="w-5 h-5 text-green-400" />;
      case 'warning': return <ExclamationTriangleIcon className="w-5 h-5 text-yellow-400" />;
      case 'unhealthy': return <ExclamationTriangleIcon className="w-5 h-5 text-red-400" />;
      default: return <ClockIcon className="w-5 h-5 text-gray-400" />;
    }
  };

  if (loading || !metrics) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center">
          <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-gray-400">Loading system metrics...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full">
      <Tabs value={activeTab} onValueChange={setActiveTab} className="h-full flex flex-col">
        {/* Header */}
        <div className="p-6 border-b border-gray-700 bg-gray-900/50">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h1 className="text-2xl font-bold text-white">FXML4 Performance Dashboard</h1>
              <p className="text-gray-400">Real-time system monitoring and performance metrics</p>
            </div>

            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2">
                <label className="text-sm text-gray-300">Auto Refresh:</label>
                <input
                  type="checkbox"
                  checked={autoRefresh}
                  onChange={(e) => setAutoRefresh(e.target.checked)}
                  className="w-4 h-4 text-blue-500 bg-gray-800 border-gray-600 rounded focus:ring-blue-500"
                />
              </div>

              <select
                value={refreshInterval}
                onChange={(e) => setRefreshInterval(parseInt(e.target.value))}
                className="px-2 py-1 bg-gray-800 border border-gray-600 rounded text-white text-sm"
              >
                <option value="10000">10s</option>
                <option value="30000">30s</option>
                <option value="60000">1m</option>
                <option value="300000">5m</option>
              </select>

              <Button
                onClick={loadMetrics}
                variant="outline"
                size="sm"
                className="gap-2"
              >
                <ArrowPathIcon className="w-4 h-4" />
                Refresh
              </Button>
            </div>
          </div>

          <div className="text-sm text-gray-400 mb-4">
            Last updated: {formatTime(metrics.timestamp)}
          </div>

          <TabsList className="grid w-full grid-cols-4 bg-gray-800">
            <TabsTrigger value="overview" className="gap-2">
              <ChartBarIcon className="w-4 h-4" />
              Overview
            </TabsTrigger>
            <TabsTrigger value="performance" className="gap-2">
              <TrendingUpIcon className="w-4 h-4" />
              Performance
            </TabsTrigger>
            <TabsTrigger value="brokers" className="gap-2">
              <CurrencyDollarIcon className="w-4 h-4" />
              Brokers
            </TabsTrigger>
            <TabsTrigger value="activity" className="gap-2">
              <SignalIcon className="w-4 h-4" />
              Activity
            </TabsTrigger>
          </TabsList>
        </div>

        <div className="flex-1 p-6">
          <TabsContent value="overview" className="h-full mt-0">
            <div className="space-y-6">
              {/* System Health */}
              <div className="bg-gray-900 border border-gray-700 rounded-lg p-6">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-semibold text-white">System Health</h3>
                  <div className={`flex items-center gap-2 px-3 py-1 rounded ${getHealthColor(metrics.system_health.status)}`}>
                    {getHealthIcon(metrics.system_health.status)}
                    <span className="text-sm font-medium">{metrics.system_health.status.toUpperCase()}</span>
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-4">
                  <div className="bg-gray-800/50 rounded p-4 text-center">
                    <div className="text-2xl font-bold text-blue-400 mb-1">
                      {formatUptime(metrics.system_health.uptime_seconds)}
                    </div>
                    <div className="text-sm text-gray-400">Uptime</div>
                  </div>

                  <div className="bg-gray-800/50 rounded p-4 text-center">
                    <div className="text-2xl font-bold text-green-400 mb-1">
                      {metrics.system_health.active_requests}
                    </div>
                    <div className="text-sm text-gray-400">Active Requests</div>
                  </div>

                  <div className="bg-gray-800/50 rounded p-4 text-center">
                    <div className="text-2xl font-bold text-purple-400 mb-1">
                      {(metrics.api_performance.error_rate_percent).toFixed(2)}%
                    </div>
                    <div className="text-sm text-gray-400">Error Rate</div>
                  </div>
                </div>
              </div>

              {/* Key Metrics Grid */}
              <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-4 gap-6">
                {/* API Performance */}
                <div className="bg-gray-900 border border-gray-700 rounded-lg p-6">
                  <div className="flex items-center gap-3 mb-4">
                    <ServerIcon className="w-6 h-6 text-blue-400" />
                    <h4 className="font-semibold text-white">API Performance</h4>
                  </div>

                  <div className="space-y-3">
                    <div className="flex justify-between">
                      <span className="text-gray-400">Total Requests:</span>
                      <span className="text-white font-medium">{metrics.api_performance.total_requests.toLocaleString()}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-400">Avg Response:</span>
                      <span className="text-white font-medium">{(metrics.api_performance.avg_response_time * 1000).toFixed(0)}ms</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-400">Requests/min:</span>
                      <span className="text-white font-medium">{metrics.api_performance.requests_per_minute.toFixed(1)}</span>
                    </div>
                  </div>
                </div>

                {/* Trading Performance */}
                <div className="bg-gray-900 border border-gray-700 rounded-lg p-6">
                  <div className="flex items-center gap-3 mb-4">
                    <CurrencyDollarIcon className="w-6 h-6 text-green-400" />
                    <h4 className="font-semibold text-white">Trading</h4>
                  </div>

                  <div className="space-y-3">
                    <div className="flex justify-between">
                      <span className="text-gray-400">Total Orders:</span>
                      <span className="text-white font-medium">{metrics.trading_performance.total_orders.toLocaleString()}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-400">Success Rate:</span>
                      <span className="text-green-400 font-medium">{metrics.trading_performance.success_rate_percent.toFixed(1)}%</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-400">Avg Execution:</span>
                      <span className="text-white font-medium">{(metrics.trading_performance.avg_execution_time * 1000).toFixed(0)}ms</span>
                    </div>
                  </div>
                </div>

                {/* FIX Protocol */}
                <div className="bg-gray-900 border border-gray-700 rounded-lg p-6">
                  <div className="flex items-center gap-3 mb-4">
                    <BoltIcon className="w-6 h-6 text-yellow-400" />
                    <h4 className="font-semibold text-white">FIX Protocol</h4>
                  </div>

                  <div className="space-y-3">
                    <div className="flex justify-between">
                      <span className="text-gray-400">Messages:</span>
                      <span className="text-white font-medium">{metrics.fix_protocol.total_messages.toLocaleString()}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-400">Avg Processing:</span>
                      <span className="text-white font-medium">{metrics.fix_protocol.avg_processing_time.toFixed(1)}ms</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-400">Mode:</span>
                      <span className="text-yellow-400 font-medium">{metrics.fix_protocol.performance_improvement}</span>
                    </div>
                  </div>
                </div>

                {/* ML Performance */}
                <div className="bg-gray-900 border border-gray-700 rounded-lg p-6">
                  <div className="flex items-center gap-3 mb-4">
                    <CpuChipIcon className="w-6 h-6 text-purple-400" />
                    <h4 className="font-semibold text-white">ML Performance</h4>
                  </div>

                  <div className="space-y-3">
                    <div className="flex justify-between">
                      <span className="text-gray-400">Inferences:</span>
                      <span className="text-white font-medium">{metrics.ml_performance.total_inferences.toLocaleString()}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-400">Success Rate:</span>
                      <span className="text-green-400 font-medium">{metrics.ml_performance.success_rate_percent.toFixed(1)}%</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-400">Avg Inference:</span>
                      <span className="text-white font-medium">{(metrics.ml_performance.avg_inference_time * 1000).toFixed(0)}ms</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </TabsContent>

          <TabsContent value="performance" className="h-full mt-0">
            <div className="bg-gray-900 border border-gray-700 rounded-lg p-6">
              <h3 className="text-lg font-semibold text-white mb-4">Performance Trends</h3>
              <div className="bg-gray-800/50 rounded-lg p-6 text-center">
                <ChartBarIcon className="w-16 h-16 text-gray-400 mx-auto mb-4" />
                <p className="text-gray-400">Real-time performance charts would be displayed here</p>
                <p className="text-sm text-gray-500 mt-2">
                  Integration with Chart.js or similar library for trend visualization
                </p>
              </div>
            </div>
          </TabsContent>

          <TabsContent value="brokers" className="h-full mt-0">
            <div className="space-y-4">
              {Object.entries(metrics.broker_adapters).map(([name, stats]) => (
                <div key={name} className="bg-gray-900 border border-gray-700 rounded-lg p-6">
                  <div className="flex items-center gap-3 mb-4">
                    <CircleStackIcon className="w-6 h-6 text-blue-400" />
                    <h4 className="text-lg font-semibold text-white">{name}</h4>
                  </div>

                  <div className="grid grid-cols-3 gap-4">
                    <div className="bg-gray-800/50 rounded p-4 text-center">
                      <div className="text-xl font-bold text-blue-400 mb-1">
                        {stats.total_operations.toLocaleString()}
                      </div>
                      <div className="text-sm text-gray-400">Operations</div>
                    </div>

                    <div className="bg-gray-800/50 rounded p-4 text-center">
                      <div className="text-xl font-bold text-red-400 mb-1">
                        {stats.errors}
                      </div>
                      <div className="text-sm text-gray-400">Errors</div>
                    </div>

                    <div className="bg-gray-800/50 rounded p-4 text-center">
                      <div className="text-xl font-bold text-green-400 mb-1">
                        {(stats.avg_duration * 1000).toFixed(0)}ms
                      </div>
                      <div className="text-sm text-gray-400">Avg Duration</div>
                    </div>
                  </div>

                  <div className="mt-4 flex justify-between items-center">
                    <div className="text-sm text-gray-400">
                      Error Rate: {stats.total_operations > 0 ? ((stats.errors / stats.total_operations) * 100).toFixed(2) : 0}%
                    </div>
                    <div className={`text-xs px-2 py-1 rounded ${
                      (stats.errors / stats.total_operations) < 0.01 ? 'text-green-400 bg-green-500/20' :
                      (stats.errors / stats.total_operations) < 0.05 ? 'text-yellow-400 bg-yellow-500/20' :
                      'text-red-400 bg-red-500/20'
                    }`}>
                      {(stats.errors / stats.total_operations) < 0.01 ? 'HEALTHY' :
                       (stats.errors / stats.total_operations) < 0.05 ? 'WARNING' : 'CRITICAL'}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </TabsContent>

          <TabsContent value="activity" className="h-full mt-0">
            <div className="bg-gray-900 border border-gray-700 rounded-lg p-6">
              <h3 className="text-lg font-semibold text-white mb-4">Recent Activity</h3>

              <div className="space-y-4">
                {metrics.recent_activity.map((activity, index) => (
                  <div key={index} className="flex items-start gap-4 p-4 bg-gray-800/50 rounded-lg">
                    <div className="w-2 h-2 bg-blue-400 rounded-full mt-2 flex-shrink-0" />
                    <div className="flex-1">
                      <div className="flex items-center justify-between mb-1">
                        <span className="font-medium text-white">{activity.event}</span>
                        <span className="text-xs text-gray-500">
                          {formatTime(activity.timestamp)}
                        </span>
                      </div>
                      <p className="text-sm text-gray-400">{activity.details}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </TabsContent>
        </div>
      </Tabs>
    </div>
  );
}
