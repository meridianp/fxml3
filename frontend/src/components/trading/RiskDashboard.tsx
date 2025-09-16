/**
 * Risk Management Dashboard Component
 *
 * Comprehensive risk monitoring and management interface
 */

'use client';

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { useAppStore } from '@/stores/appStore';
import {
  ShieldExclamationIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  XCircleIcon,
  ClockIcon,
  CurrencyDollarIcon,
  ChartBarIcon,
  AdjustmentsHorizontalIcon,
  BellAlertIcon,
  PauseIcon,
  PlayIcon,
  StopIcon,
  EyeIcon,
  ArrowPathIcon,
  ScaleIcon,
  TrendingUpIcon,
  TrendingDownIcon
} from '@heroicons/react/24/outline';

interface RiskLimit {
  id: string;
  name: string;
  type: 'daily_loss' | 'position_size' | 'exposure' | 'drawdown' | 'var' | 'correlation';
  current_value: number;
  limit_value: number;
  utilization: number; // 0-1
  status: 'safe' | 'warning' | 'critical' | 'breached';
  enabled: boolean;
  last_updated: string;
}

interface RiskAlert {
  id: string;
  type: 'limit_breach' | 'high_correlation' | 'unusual_activity' | 'margin_warning';
  severity: 'low' | 'medium' | 'high' | 'critical';
  title: string;
  message: string;
  instrument?: string;
  current_value?: number;
  threshold?: number;
  timestamp: string;
  acknowledged: boolean;
}

interface Position {
  id: string;
  symbol: string;
  side: 'long' | 'short';
  size: number;
  entry_price: number;
  current_price: number;
  unrealized_pnl: number;
  unrealized_pnl_pct: number;
  risk_contribution: number;
  margin_used: number;
  time_held: number; // hours
  max_adverse_excursion: number;
  max_favorable_excursion: number;
}

interface RiskMetrics {
  portfolio_value: number;
  total_exposure: number;
  net_exposure: number;
  gross_exposure: number;
  daily_pnl: number;
  daily_pnl_pct: number;
  max_drawdown: number;
  max_drawdown_pct: number;
  var_95: number; // Value at Risk 95%
  var_99: number; // Value at Risk 99%
  sharpe_ratio: number;
  sortino_ratio: number;
  margin_used: number;
  margin_available: number;
  margin_utilization: number;
}

interface RiskDashboardProps {
  positions?: Position[];
}

export default function RiskDashboard({ positions = [] }: RiskDashboardProps) {
  const [activeTab, setActiveTab] = useState('overview');
  const [riskLimits, setRiskLimits] = useState<RiskLimit[]>([]);
  const [alerts, setAlerts] = useState<RiskAlert[]>([]);
  const [metrics, setMetrics] = useState<RiskMetrics | null>(null);
  const [selectedAlert, setSelectedAlert] = useState<RiskAlert | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [riskSystemEnabled, setRiskSystemEnabled] = useState(true);
  const [loading, setLoading] = useState(true);

  const { addNotification } = useAppStore();

  useEffect(() => {
    loadRiskData();
  }, []);

  useEffect(() => {
    let interval: NodeJS.Timeout;

    if (autoRefresh) {
      interval = setInterval(() => {
        loadRiskData();
      }, 5000); // Update every 5 seconds for risk data
    }

    return () => {
      if (interval) clearInterval(interval);
    };
  }, [autoRefresh]);

  const loadRiskData = async () => {
    try {
      // Fetch real risk metrics from API
      const metricsResponse = await fetch('/api/risk/metrics');
      if (!metricsResponse.ok) {
        throw new Error(`Failed to fetch risk metrics: ${metricsResponse.status}`);
      }
      const metricsData = await metricsResponse.json();
      setMetrics(metricsData);

      // TODO: Replace mock data with real API calls for limits and alerts
      const mockLimits: RiskLimit[] = [
        {
          id: 'daily_loss',
          name: 'Daily Loss Limit',
          type: 'daily_loss',
          current_value: -1250,
          limit_value: -5000,
          utilization: 0.25,
          status: 'safe',
          enabled: true,
          last_updated: new Date().toISOString()
        },
        {
          id: 'position_size',
          name: 'Max Position Size',
          type: 'position_size',
          current_value: 850000,
          limit_value: 1000000,
          utilization: 0.85,
          status: 'warning',
          enabled: true,
          last_updated: new Date().toISOString()
        },
        {
          id: 'total_exposure',
          name: 'Total Exposure',
          type: 'exposure',
          current_value: 2450000,
          limit_value: 3000000,
          utilization: 0.82,
          status: 'warning',
          enabled: true,
          last_updated: new Date().toISOString()
        },
        {
          id: 'max_drawdown',
          name: 'Max Drawdown',
          type: 'drawdown',
          current_value: 0.034,
          limit_value: 0.05,
          utilization: 0.68,
          status: 'warning',
          enabled: true,
          last_updated: new Date().toISOString()
        },
        {
          id: 'var_95',
          name: 'VaR 95% (Daily)',
          type: 'var',
          current_value: 15600,
          limit_value: 25000,
          utilization: 0.62,
          status: 'safe',
          enabled: true,
          last_updated: new Date().toISOString()
        },
        {
          id: 'correlation',
          name: 'Max Correlation',
          type: 'correlation',
          current_value: 0.78,
          limit_value: 0.85,
          utilization: 0.92,
          status: 'critical',
          enabled: true,
          last_updated: new Date().toISOString()
        }
      ];

      const mockAlerts: RiskAlert[] = [
        {
          id: 'alert_001',
          type: 'high_correlation',
          severity: 'high',
          title: 'High Correlation Detected',
          message: 'EURUSD and GBPUSD positions showing correlation of 0.89, exceeding threshold of 0.85',
          instrument: 'EURUSD/GBPUSD',
          current_value: 0.89,
          threshold: 0.85,
          timestamp: new Date(Date.now() - 120000).toISOString(),
          acknowledged: false
        },
        {
          id: 'alert_002',
          type: 'limit_breach',
          severity: 'medium',
          title: 'Position Size Warning',
          message: 'USDJPY position size approaching limit (85% utilized)',
          instrument: 'USDJPY',
          current_value: 850000,
          threshold: 1000000,
          timestamp: new Date(Date.now() - 300000).toISOString(),
          acknowledged: false
        },
        {
          id: 'alert_003',
          type: 'unusual_activity',
          severity: 'medium',
          title: 'Unusual Volatility',
          message: 'GBPUSD showing 3x normal volatility in the last 30 minutes',
          instrument: 'GBPUSD',
          timestamp: new Date(Date.now() - 480000).toISOString(),
          acknowledged: true
        },
        {
          id: 'alert_004',
          type: 'margin_warning',
          severity: 'low',
          title: 'Margin Utilization',
          message: 'Margin utilization at 72%, consider reducing exposure',
          current_value: 0.72,
          threshold: 0.8,
          timestamp: new Date(Date.now() - 600000).toISOString(),
          acknowledged: false
        }
      ];


      const mockPositions: Position[] = [
        {
          id: 'pos_001',
          symbol: 'EURUSD',
          side: 'long',
          size: 500000,
          entry_price: 1.0847,
          current_price: 1.0852,
          unrealized_pnl: 250,
          unrealized_pnl_pct: 0.05,
          risk_contribution: 0.34,
          margin_used: 12500,
          time_held: 4.5,
          max_adverse_excursion: -0.0012,
          max_favorable_excursion: 0.0008
        },
        {
          id: 'pos_002',
          symbol: 'GBPUSD',
          side: 'short',
          size: 300000,
          entry_price: 1.2634,
          current_price: 1.2628,
          unrealized_pnl: 180,
          unrealized_pnl_pct: 0.05,
          risk_contribution: 0.28,
          margin_used: 9480,
          time_held: 2.1,
          max_adverse_excursion: -0.0018,
          max_favorable_excursion: 0.0015
        },
        {
          id: 'pos_003',
          symbol: 'USDJPY',
          side: 'long',
          size: 850000,
          entry_price: 149.45,
          current_price: 149.32,
          unrealized_pnl: -910,
          unrealized_pnl_pct: -0.09,
          risk_contribution: 0.38,
          margin_used: 21250,
          time_held: 1.3,
          max_adverse_excursion: -0.0024,
          max_favorable_excursion: 0.0003
        }
      ];

      setRiskLimits(mockLimits);
      setAlerts(mockAlerts);
      setLoading(false);
    } catch (error) {
      console.error('Failed to load risk data:', error);
      // Show user-friendly error notification
      addNotification({
        type: 'error',
        title: 'Risk Data Error',
        message: 'Failed to load risk metrics. Using cached data if available.',
        duration: 5000
      });
      setLoading(false);
    }
  };

  const getStatusColor = (status: string): string => {
    switch (status) {
      case 'safe': return 'text-green-400 bg-green-500/20';
      case 'warning': return 'text-yellow-400 bg-yellow-500/20';
      case 'critical': return 'text-orange-400 bg-orange-500/20';
      case 'breached': return 'text-red-400 bg-red-500/20';
      default: return 'text-gray-400 bg-gray-500/20';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'safe': return <CheckCircleIcon className="w-4 h-4 text-green-400" />;
      case 'warning': return <ExclamationTriangleIcon className="w-4 h-4 text-yellow-400" />;
      case 'critical': return <ExclamationTriangleIcon className="w-4 h-4 text-orange-400" />;
      case 'breached': return <XCircleIcon className="w-4 h-4 text-red-400" />;
      default: return <ClockIcon className="w-4 h-4 text-gray-400" />;
    }
  };

  const getSeverityColor = (severity: string): string => {
    switch (severity) {
      case 'low': return 'text-blue-400 bg-blue-500/20';
      case 'medium': return 'text-yellow-400 bg-yellow-500/20';
      case 'high': return 'text-orange-400 bg-orange-500/20';
      case 'critical': return 'text-red-400 bg-red-500/20';
      default: return 'text-gray-400 bg-gray-500/20';
    }
  };

  const formatCurrency = (value: number): string => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0
    }).format(value);
  };

  const formatPercentage = (value: number): string => {
    return `${(value * 100).toFixed(2)}%`;
  };

  const acknowledgeAlert = (alertId: string) => {
    setAlerts(prev => prev.map(alert =>
      alert.id === alertId ? { ...alert, acknowledged: true } : alert
    ));

    addNotification({
      type: 'success',
      title: 'Alert Acknowledged',
      message: 'Risk alert has been acknowledged'
    });
  };

  const toggleRiskLimit = (limitId: string) => {
    setRiskLimits(prev => prev.map(limit =>
      limit.id === limitId ? { ...limit, enabled: !limit.enabled } : limit
    ));
  };

  const toggleRiskSystem = () => {
    setRiskSystemEnabled(!riskSystemEnabled);

    addNotification({
      type: riskSystemEnabled ? 'warning' : 'success',
      title: 'Risk System',
      message: `Risk monitoring ${riskSystemEnabled ? 'disabled' : 'enabled'}`
    });
  };

  const unacknowledgedAlerts = alerts.filter(alert => !alert.acknowledged);
  const criticalAlerts = alerts.filter(alert => alert.severity === 'critical' || alert.severity === 'high');

  if (loading || !metrics) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center">
          <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-gray-400">Loading risk data...</p>
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
            <div className="flex items-center gap-4">
              <div>
                <h1 className="text-2xl font-bold text-white">Risk Management Dashboard</h1>
                <p className="text-gray-400">Real-time risk monitoring and position analysis</p>
              </div>

              <div className={`flex items-center gap-2 px-3 py-1 rounded ${
                riskSystemEnabled ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
              }`}>
                <div className={`w-2 h-2 rounded-full ${riskSystemEnabled ? 'bg-green-400' : 'bg-red-400'}`} />
                <span className="text-sm font-medium">
                  Risk System {riskSystemEnabled ? 'ACTIVE' : 'DISABLED'}
                </span>
              </div>
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

              <Button
                onClick={toggleRiskSystem}
                variant={riskSystemEnabled ? "destructive" : "default"}
                size="sm"
                className="gap-2"
              >
                {riskSystemEnabled ? (
                  <>
                    <PauseIcon className="w-4 h-4" />
                    Disable Risk System
                  </>
                ) : (
                  <>
                    <PlayIcon className="w-4 h-4" />
                    Enable Risk System
                  </>
                )}
              </Button>

              <Button
                onClick={loadRiskData}
                variant="outline"
                size="sm"
                className="gap-2"
              >
                <ArrowPathIcon className="w-4 h-4" />
                Refresh
              </Button>
            </div>
          </div>

          {/* Alert Banner */}
          {unacknowledgedAlerts.length > 0 && (
            <div className="mb-4 p-3 bg-red-500/10 border border-red-500/30 rounded-lg">
              <div className="flex items-center gap-2">
                <BellAlertIcon className="w-5 h-5 text-red-400" />
                <span className="text-red-400 font-medium">
                  {unacknowledgedAlerts.length} unacknowledged alert{unacknowledgedAlerts.length > 1 ? 's' : ''}
                </span>
                <span className="text-gray-400">
                  ({criticalAlerts.length} critical/high priority)
                </span>
              </div>
            </div>
          )}

          <TabsList className="grid w-full grid-cols-4 bg-gray-800">
            <TabsTrigger value="overview" className="gap-2">
              <ShieldExclamationIcon className="w-4 h-4" />
              Overview
            </TabsTrigger>
            <TabsTrigger value="limits" className="gap-2">
              <ScaleIcon className="w-4 h-4" />
              Risk Limits
            </TabsTrigger>
            <TabsTrigger value="positions" className="gap-2">
              <CurrencyDollarIcon className="w-4 h-4" />
              Positions
            </TabsTrigger>
            <TabsTrigger value="alerts" className="gap-2 relative">
              <BellAlertIcon className="w-4 h-4" />
              Alerts
              {unacknowledgedAlerts.length > 0 && (
                <span className="absolute -top-1 -right-1 w-5 h-5 bg-red-500 text-white text-xs rounded-full flex items-center justify-center">
                  {unacknowledgedAlerts.length}
                </span>
              )}
            </TabsTrigger>
          </TabsList>
        </div>

        <div className="flex-1 p-6">
          <TabsContent value="overview" className="h-full mt-0">
            <div className="space-y-6">
              {/* Portfolio Metrics */}
              <div className="bg-gray-900 border border-gray-700 rounded-lg p-6">
                <h3 className="text-lg font-semibold text-white mb-4">Portfolio Risk Metrics</h3>

                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                  <div className="bg-gray-800/50 rounded p-4 text-center">
                    <div className="text-2xl font-bold text-white mb-1">
                      {formatCurrency(metrics.portfolio_value)}
                    </div>
                    <div className="text-sm text-gray-400">Portfolio Value</div>
                  </div>

                  <div className="bg-gray-800/50 rounded p-4 text-center">
                    <div className={`text-2xl font-bold mb-1 ${
                      metrics.daily_pnl >= 0 ? 'text-green-400' : 'text-red-400'
                    }`}>
                      {metrics.daily_pnl >= 0 ? '+' : ''}{formatCurrency(metrics.daily_pnl)}
                    </div>
                    <div className="text-sm text-gray-400">Daily P&L</div>
                  </div>

                  <div className="bg-gray-800/50 rounded p-4 text-center">
                    <div className="text-2xl font-bold text-red-400 mb-1">
                      {formatPercentage(metrics.max_drawdown_pct)}
                    </div>
                    <div className="text-sm text-gray-400">Max Drawdown</div>
                  </div>

                  <div className="bg-gray-800/50 rounded p-4 text-center">
                    <div className="text-2xl font-bold text-blue-400 mb-1">
                      {formatCurrency(metrics.var_95)}
                    </div>
                    <div className="text-sm text-gray-400">VaR 95%</div>
                  </div>
                </div>
              </div>

              {/* Risk Limit Status Summary */}
              <div className="bg-gray-900 border border-gray-700 rounded-lg p-6">
                <h3 className="text-lg font-semibold text-white mb-4">Risk Limit Status</h3>

                <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
                  {riskLimits.map(limit => (
                    <div key={limit.id} className="bg-gray-800/50 rounded-lg p-4">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm text-gray-300">{limit.name}</span>
                        {getStatusIcon(limit.status)}
                      </div>

                      <div className="mb-2">
                        <div className="text-lg font-bold text-white">
                          {limit.type === 'daily_loss' || limit.type === 'exposure' || limit.type === 'var'
                            ? formatCurrency(Math.abs(limit.current_value))
                            : limit.type === 'drawdown' || limit.type === 'correlation'
                            ? formatPercentage(limit.current_value)
                            : limit.current_value.toLocaleString()}
                        </div>
                        <div className="text-xs text-gray-400">
                          of {limit.type === 'daily_loss' || limit.type === 'exposure' || limit.type === 'var'
                            ? formatCurrency(Math.abs(limit.limit_value))
                            : limit.type === 'drawdown' || limit.type === 'correlation'
                            ? formatPercentage(limit.limit_value)
                            : limit.limit_value.toLocaleString()} limit
                        </div>
                      </div>

                      <div className="w-full bg-gray-700 rounded-full h-2 mb-2">
                        <div
                          className={`h-2 rounded-full transition-all duration-300 ${
                            limit.utilization < 0.7 ? 'bg-green-500' :
                            limit.utilization < 0.85 ? 'bg-yellow-500' :
                            limit.utilization < 0.95 ? 'bg-orange-500' : 'bg-red-500'
                          }`}
                          style={{ width: `${Math.min(limit.utilization * 100, 100)}%` }}
                        />
                      </div>

                      <div className={`text-xs px-2 py-1 rounded ${getStatusColor(limit.status)}`}>
                        {limit.status.toUpperCase()} ({(limit.utilization * 100).toFixed(0)}%)
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Exposure Analysis */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div className="bg-gray-900 border border-gray-700 rounded-lg p-6">
                  <h4 className="text-lg font-semibold text-white mb-4">Exposure Breakdown</h4>

                  <div className="space-y-4">
                    <div className="flex justify-between items-center">
                      <span className="text-gray-400">Gross Exposure:</span>
                      <span className="text-white font-medium">{formatCurrency(metrics.gross_exposure)}</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-gray-400">Net Exposure:</span>
                      <span className={`font-medium ${
                        metrics.net_exposure >= 0 ? 'text-green-400' : 'text-red-400'
                      }`}>
                        {formatCurrency(metrics.net_exposure)}
                      </span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-gray-400">Margin Used:</span>
                      <span className="text-white font-medium">{formatCurrency(metrics.margin_used)}</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-gray-400">Margin Available:</span>
                      <span className="text-green-400 font-medium">{formatCurrency(metrics.margin_available)}</span>
                    </div>
                  </div>

                  <div className="mt-4">
                    <div className="flex justify-between text-sm text-gray-400 mb-2">
                      <span>Margin Utilization</span>
                      <span>{formatPercentage(metrics.margin_utilization)}</span>
                    </div>
                    <div className="w-full bg-gray-700 rounded-full h-3">
                      <div
                        className={`h-3 rounded-full transition-all duration-300 ${
                          metrics.margin_utilization < 0.7 ? 'bg-green-500' :
                          metrics.margin_utilization < 0.85 ? 'bg-yellow-500' : 'bg-red-500'
                        }`}
                        style={{ width: `${Math.min(metrics.margin_utilization * 100, 100)}%` }}
                      />
                    </div>
                  </div>
                </div>

                <div className="bg-gray-900 border border-gray-700 rounded-lg p-6">
                  <h4 className="text-lg font-semibold text-white mb-4">Risk Ratios</h4>

                  <div className="space-y-4">
                    <div className="flex justify-between items-center">
                      <span className="text-gray-400">Sharpe Ratio:</span>
                      <span className={`font-medium ${
                        metrics.sharpe_ratio > 1 ? 'text-green-400' :
                        metrics.sharpe_ratio > 0.5 ? 'text-yellow-400' : 'text-red-400'
                      }`}>
                        {metrics.sharpe_ratio.toFixed(2)}
                      </span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-gray-400">Sortino Ratio:</span>
                      <span className={`font-medium ${
                        metrics.sortino_ratio > 1 ? 'text-green-400' :
                        metrics.sortino_ratio > 0.5 ? 'text-yellow-400' : 'text-red-400'
                      }`}>
                        {metrics.sortino_ratio.toFixed(2)}
                      </span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-gray-400">VaR 99%:</span>
                      <span className="text-red-400 font-medium">{formatCurrency(metrics.var_99)}</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-gray-400">Portfolio Beta:</span>
                      <span className="text-blue-400 font-medium">0.89</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </TabsContent>

          <TabsContent value="limits" className="h-full mt-0">
            <div className="space-y-4">
              {riskLimits.map(limit => (
                <div key={limit.id} className="bg-gray-900 border border-gray-700 rounded-lg p-6">
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-4">
                      <div className="flex items-center gap-2">
                        {getStatusIcon(limit.status)}
                        <h3 className="text-lg font-semibold text-white">{limit.name}</h3>
                      </div>

                      <span className={`text-xs px-2 py-1 rounded ${getStatusColor(limit.status)}`}>
                        {limit.status.toUpperCase()}
                      </span>
                    </div>

                    <div className="flex items-center gap-3">
                      <div className="text-right">
                        <div className="text-sm text-gray-400">Utilization</div>
                        <div className="font-bold text-white">{(limit.utilization * 100).toFixed(1)}%</div>
                      </div>

                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => toggleRiskLimit(limit.id)}
                        className={limit.enabled ? 'text-green-400' : 'text-red-400'}
                      >
                        {limit.enabled ? 'Enabled' : 'Disabled'}
                      </Button>
                    </div>
                  </div>

                  <div className="grid grid-cols-3 gap-6 mb-4">
                    <div>
                      <div className="text-sm text-gray-400 mb-1">Current Value</div>
                      <div className="text-xl font-bold text-white">
                        {limit.type === 'daily_loss' || limit.type === 'exposure' || limit.type === 'var'
                          ? formatCurrency(Math.abs(limit.current_value))
                          : limit.type === 'drawdown' || limit.type === 'correlation'
                          ? formatPercentage(limit.current_value)
                          : limit.current_value.toLocaleString()}
                      </div>
                    </div>

                    <div>
                      <div className="text-sm text-gray-400 mb-1">Limit</div>
                      <div className="text-xl font-bold text-red-400">
                        {limit.type === 'daily_loss' || limit.type === 'exposure' || limit.type === 'var'
                          ? formatCurrency(Math.abs(limit.limit_value))
                          : limit.type === 'drawdown' || limit.type === 'correlation'
                          ? formatPercentage(limit.limit_value)
                          : limit.limit_value.toLocaleString()}
                      </div>
                    </div>

                    <div>
                      <div className="text-sm text-gray-400 mb-1">Remaining</div>
                      <div className="text-xl font-bold text-green-400">
                        {limit.type === 'daily_loss' || limit.type === 'exposure' || limit.type === 'var'
                          ? formatCurrency(Math.abs(limit.limit_value) - Math.abs(limit.current_value))
                          : limit.type === 'drawdown' || limit.type === 'correlation'
                          ? formatPercentage(limit.limit_value - limit.current_value)
                          : (limit.limit_value - limit.current_value).toLocaleString()}
                      </div>
                    </div>
                  </div>

                  <div className="w-full bg-gray-700 rounded-full h-4">
                    <div
                      className={`h-4 rounded-full transition-all duration-300 ${
                        limit.utilization < 0.7 ? 'bg-green-500' :
                        limit.utilization < 0.85 ? 'bg-yellow-500' :
                        limit.utilization < 0.95 ? 'bg-orange-500' : 'bg-red-500'
                      }`}
                      style={{ width: `${Math.min(limit.utilization * 100, 100)}%` }}
                    />
                  </div>

                  <div className="flex justify-between text-xs text-gray-400 mt-2">
                    <span>Safe (0-70%)</span>
                    <span>Warning (70-85%)</span>
                    <span>Critical (85-95%)</span>
                    <span>Breach (95%+)</span>
                  </div>
                </div>
              ))}
            </div>
          </TabsContent>

          <TabsContent value="positions" className="h-full mt-0">
            <div className="bg-gray-900 border border-gray-700 rounded-lg overflow-hidden">
              <div className="p-4 border-b border-gray-700">
                <h3 className="text-lg font-semibold text-white">Position Risk Analysis</h3>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-gray-800/50">
                    <tr>
                      <th className="px-4 py-3 text-left text-gray-300">Symbol</th>
                      <th className="px-4 py-3 text-left text-gray-300">Side</th>
                      <th className="px-4 py-3 text-left text-gray-300">Size</th>
                      <th className="px-4 py-3 text-left text-gray-300">P&L</th>
                      <th className="px-4 py-3 text-left text-gray-300">Risk Contrib.</th>
                      <th className="px-4 py-3 text-left text-gray-300">Margin</th>
                      <th className="px-4 py-3 text-left text-gray-300">Time Held</th>
                      <th className="px-4 py-3 text-left text-gray-300">MAE/MFE</th>
                      <th className="px-4 py-3 text-left text-gray-300">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[
                      {
                        id: 'pos_001',
                        symbol: 'EURUSD',
                        side: 'long' as const,
                        size: 500000,
                        entry_price: 1.0847,
                        current_price: 1.0852,
                        unrealized_pnl: 250,
                        unrealized_pnl_pct: 0.05,
                        risk_contribution: 0.34,
                        margin_used: 12500,
                        time_held: 4.5,
                        max_adverse_excursion: -0.0012,
                        max_favorable_excursion: 0.0008
                      },
                      {
                        id: 'pos_002',
                        symbol: 'GBPUSD',
                        side: 'short' as const,
                        size: 300000,
                        entry_price: 1.2634,
                        current_price: 1.2628,
                        unrealized_pnl: 180,
                        unrealized_pnl_pct: 0.05,
                        risk_contribution: 0.28,
                        margin_used: 9480,
                        time_held: 2.1,
                        max_adverse_excursion: -0.0018,
                        max_favorable_excursion: 0.0015
                      },
                      {
                        id: 'pos_003',
                        symbol: 'USDJPY',
                        side: 'long' as const,
                        size: 850000,
                        entry_price: 149.45,
                        current_price: 149.32,
                        unrealized_pnl: -910,
                        unrealized_pnl_pct: -0.09,
                        risk_contribution: 0.38,
                        margin_used: 21250,
                        time_held: 1.3,
                        max_adverse_excursion: -0.0024,
                        max_favorable_excursion: 0.0003
                      }
                    ].map(position => (
                      <tr key={position.id} className="border-t border-gray-700 hover:bg-gray-800/30">
                        <td className="px-4 py-3 font-medium text-white">{position.symbol}</td>
                        <td className="px-4 py-3">
                          <span className={`px-2 py-1 rounded text-xs font-medium ${
                            position.side === 'long' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
                          }`}>
                            {position.side.toUpperCase()}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-gray-300">{position.size.toLocaleString()}</td>
                        <td className="px-4 py-3">
                          <div className={`font-medium ${
                            position.unrealized_pnl >= 0 ? 'text-green-400' : 'text-red-400'
                          }`}>
                            {position.unrealized_pnl >= 0 ? '+' : ''}{formatCurrency(position.unrealized_pnl)}
                          </div>
                          <div className="text-xs text-gray-400">
                            {formatPercentage(position.unrealized_pnl_pct)}
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          <div className="w-16 bg-gray-700 rounded-full h-2">
                            <div
                              className="bg-blue-500 h-2 rounded-full"
                              style={{ width: `${position.risk_contribution * 100}%` }}
                            />
                          </div>
                          <div className="text-xs text-gray-400 mt-1">
                            {(position.risk_contribution * 100).toFixed(0)}%
                          </div>
                        </td>
                        <td className="px-4 py-3 text-gray-300">{formatCurrency(position.margin_used)}</td>
                        <td className="px-4 py-3 text-gray-300">{position.time_held.toFixed(1)}h</td>
                        <td className="px-4 py-3">
                          <div className="text-red-400 text-xs">
                            MAE: {formatPercentage(Math.abs(position.max_adverse_excursion))}
                          </div>
                          <div className="text-green-400 text-xs">
                            MFE: {formatPercentage(position.max_favorable_excursion)}
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-1">
                            <Button size="sm" variant="outline" className="p-1">
                              <EyeIcon className="w-3 h-3" />
                            </Button>
                            <Button size="sm" variant="outline" className="p-1 text-red-400">
                              <StopIcon className="w-3 h-3" />
                            </Button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </TabsContent>

          <TabsContent value="alerts" className="h-full mt-0">
            <div className="space-y-4">
              {alerts.map(alert => (
                <div key={alert.id} className={`bg-gray-900 border rounded-lg p-6 ${
                  alert.acknowledged ? 'border-gray-700' : 'border-yellow-500/50'
                }`}>
                  <div className="flex items-start justify-between">
                    <div className="flex items-start gap-4">
                      <div className={`w-2 h-2 rounded-full mt-2 ${
                        alert.acknowledged ? 'bg-gray-400' :
                        alert.severity === 'critical' ? 'bg-red-500' :
                        alert.severity === 'high' ? 'bg-orange-500' :
                        alert.severity === 'medium' ? 'bg-yellow-500' : 'bg-blue-500'
                      }`} />

                      <div className="flex-1">
                        <div className="flex items-center gap-3 mb-2">
                          <h4 className="font-semibold text-white">{alert.title}</h4>
                          <span className={`text-xs px-2 py-1 rounded ${getSeverityColor(alert.severity)}`}>
                            {alert.severity.toUpperCase()}
                          </span>
                          {alert.acknowledged && (
                            <span className="text-xs px-2 py-1 bg-gray-500/20 text-gray-400 rounded">
                              ACKNOWLEDGED
                            </span>
                          )}
                        </div>

                        <p className="text-gray-400 mb-2">{alert.message}</p>

                        <div className="flex items-center gap-4 text-sm text-gray-500">
                          <span>{new Date(alert.timestamp).toLocaleString()}</span>
                          {alert.instrument && <span>Instrument: {alert.instrument}</span>}
                          {alert.current_value && alert.threshold && (
                            <span>
                              Current: {alert.current_value} / Threshold: {alert.threshold}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      {!alert.acknowledged && (
                        <Button
                          size="sm"
                          onClick={() => acknowledgeAlert(alert.id)}
                          className="gap-2"
                        >
                          <CheckCircleIcon className="w-4 h-4" />
                          Acknowledge
                        </Button>
                      )}

                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => setSelectedAlert(alert)}
                        className="p-2"
                      >
                        <EyeIcon className="w-4 h-4" />
                      </Button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </TabsContent>
        </div>
      </Tabs>

      {/* Alert Detail Modal */}
      {selectedAlert && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-gray-900 border border-gray-700 rounded-lg max-w-2xl w-full">
            <div className="p-6 border-b border-gray-700">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-xl font-semibold text-white">{selectedAlert.title}</h3>
                  <div className="flex items-center gap-2 mt-2">
                    <span className={`text-xs px-2 py-1 rounded ${getSeverityColor(selectedAlert.severity)}`}>
                      {selectedAlert.severity.toUpperCase()}
                    </span>
                    <span className="text-sm text-gray-400">
                      {new Date(selectedAlert.timestamp).toLocaleString()}
                    </span>
                  </div>
                </div>
                <Button
                  variant="outline"
                  onClick={() => setSelectedAlert(null)}
                >
                  Close
                </Button>
              </div>
            </div>

            <div className="p-6 space-y-4">
              <div>
                <h4 className="font-medium text-white mb-2">Alert Details</h4>
                <p className="text-gray-300">{selectedAlert.message}</p>
              </div>

              {selectedAlert.instrument && (
                <div>
                  <h4 className="font-medium text-white mb-2">Affected Instrument</h4>
                  <p className="text-blue-400">{selectedAlert.instrument}</p>
                </div>
              )}

              {selectedAlert.current_value && selectedAlert.threshold && (
                <div>
                  <h4 className="font-medium text-white mb-2">Values</h4>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="bg-gray-800/50 rounded p-3">
                      <div className="text-sm text-gray-400">Current Value</div>
                      <div className="text-lg font-bold text-white">{selectedAlert.current_value}</div>
                    </div>
                    <div className="bg-gray-800/50 rounded p-3">
                      <div className="text-sm text-gray-400">Threshold</div>
                      <div className="text-lg font-bold text-red-400">{selectedAlert.threshold}</div>
                    </div>
                  </div>
                </div>
              )}

              {!selectedAlert.acknowledged && (
                <div className="flex justify-end">
                  <Button
                    onClick={() => {
                      acknowledgeAlert(selectedAlert.id);
                      setSelectedAlert(null);
                    }}
                    className="gap-2"
                  >
                    <CheckCircleIcon className="w-4 h-4" />
                    Acknowledge Alert
                  </Button>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
