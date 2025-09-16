/**
 * Phase 7 - Advanced Compliance Monitoring Dashboard
 * 
 * Real-time compliance monitoring interface that integrates with Phase 6
 * compliance and regulatory systems for comprehensive oversight.
 */

'use client';

import React, { useState, useEffect, useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { 
  LineChart, 
  Line, 
  AreaChart,
  Area,
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar
} from 'recharts';
import {
  ShieldCheckIcon,
  ExclamationTriangleIcon,
  DocumentChartBarIcon,
  EyeIcon,
  ClockIcon,
  BellAlertIcon,
  CheckCircleIcon,
  XCircleIcon,
  InformationCircleIcon,
  ChartBarSquareIcon
} from '@heroicons/react/24/outline';
import { formatDistanceToNow, format } from 'date-fns';
import { motion, AnimatePresence } from 'framer-motion';

// Types for compliance data
interface ComplianceAlert {
  id: string;
  type: 'surveillance' | 'risk_limit' | 'regulatory';
  severity: 'critical' | 'high' | 'medium' | 'low';
  title: string;
  description: string;
  timestamp: string;
  status: 'active' | 'acknowledged' | 'resolved';
  jurisdiction?: string;
  regulatoryFramework?: string;
}

interface SurveillancePattern {
  pattern: string;
  count: number;
  severity: string;
  lastDetected: string;
}

interface ComplianceMetrics {
  surveillanceScore: number;
  riskComplianceScore: number;
  regulatoryComplianceScore: number;
  overallComplianceScore: number;
  activeBreaches: number;
  resolvedToday: number;
  pendingReports: number;
  auditTrailIntegrity: number;
}

interface RiskLimitBreach {
  id: string;
  limitType: string;
  currentValue: number;
  limitValue: number;
  exceedancePercent: number;
  timestamp: string;
  status: 'active' | 'resolved';
}

export default function ComplianceMonitoringDashboard() {
  const [selectedTimeframe, setSelectedTimeframe] = useState<'1h' | '4h' | '1d' | '1w'>('1d');
  const [activeAlerts, setActiveAlerts] = useState<ComplianceAlert[]>([]);
  const [complianceMetrics, setComplianceMetrics] = useState<ComplianceMetrics | null>(null);
  const [surveillancePatterns, setSurveillancePatterns] = useState<SurveillancePattern[]>([]);
  const [riskBreaches, setRiskBreaches] = useState<RiskLimitBreach[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  // Simulated data - in real implementation, this would come from Phase 6 APIs
  useEffect(() => {
    const mockData = {
      metrics: {
        surveillanceScore: 94,
        riskComplianceScore: 88,
        regulatoryComplianceScore: 96,
        overallComplianceScore: 93,
        activeBreaches: 3,
        resolvedToday: 12,
        pendingReports: 2,
        auditTrailIntegrity: 100
      },
      alerts: [
        {
          id: '1',
          type: 'surveillance' as const,
          severity: 'high' as const,
          title: 'Unusual Volume Pattern Detected',
          description: 'EUR/USD showing 300% above average volume with potential layering pattern',
          timestamp: new Date(Date.now() - 1800000).toISOString(),
          status: 'active' as const,
          jurisdiction: 'US-CFTC'
        },
        {
          id: '2',
          type: 'risk_limit' as const,
          severity: 'critical' as const,
          title: 'Position Limit Exceeded',
          description: 'Daily position limit exceeded by 15% for GBP/USD',
          timestamp: new Date(Date.now() - 900000).toISOString(),
          status: 'active' as const
        },
        {
          id: '3',
          type: 'regulatory' as const,
          severity: 'medium' as const,
          title: 'MiFID II Reporting Delay',
          description: 'Trade reporting to ESMA delayed by 45 minutes',
          timestamp: new Date(Date.now() - 2700000).toISOString(),
          status: 'acknowledged' as const,
          regulatoryFramework: 'MiFID II'
        }
      ],
      patterns: [
        { pattern: 'Wash Trading', count: 0, severity: 'none', lastDetected: '' },
        { pattern: 'Layering/Spoofing', count: 2, severity: 'medium', lastDetected: '15 minutes ago' },
        { pattern: 'Momentum Ignition', count: 1, severity: 'low', lastDetected: '2 hours ago' },
        { pattern: 'Cross Product Manipulation', count: 0, severity: 'none', lastDetected: '' },
        { pattern: 'Churning', count: 0, severity: 'none', lastDetected: '' }
      ],
      breaches: [
        {
          id: '1',
          limitType: 'Daily Position Limit',
          currentValue: 11500000,
          limitValue: 10000000,
          exceedancePercent: 15,
          timestamp: new Date(Date.now() - 900000).toISOString(),
          status: 'active' as const
        },
        {
          id: '2', 
          limitType: 'Concentration Risk',
          currentValue: 0.85,
          limitValue: 0.75,
          exceedancePercent: 13.3,
          timestamp: new Date(Date.now() - 1800000).toISOString(),
          status: 'active' as const
        }
      ]
    };

    setTimeout(() => {
      setComplianceMetrics(mockData.metrics);
      setActiveAlerts(mockData.alerts);
      setSurveillancePatterns(mockData.patterns);
      setRiskBreaches(mockData.breaches);
      setIsLoading(false);
    }, 1000);
  }, []);

  // Helper functions
  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'critical': return 'text-red-600 bg-red-50 border-red-200';
      case 'high': return 'text-orange-600 bg-orange-50 border-orange-200';
      case 'medium': return 'text-yellow-600 bg-yellow-50 border-yellow-200';
      case 'low': return 'text-blue-600 bg-blue-50 border-blue-200';
      default: return 'text-gray-600 bg-gray-50 border-gray-200';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'active': return <ExclamationTriangleIcon className="w-4 h-4 text-red-500" />;
      case 'acknowledged': return <InformationCircleIcon className="w-4 h-4 text-yellow-500" />;
      case 'resolved': return <CheckCircleIcon className="w-4 h-4 text-green-500" />;
      default: return <ClockIcon className="w-4 h-4 text-gray-500" />;
    }
  };

  // Compliance score data for chart
  const complianceScoreData = useMemo(() => {
    if (!complianceMetrics) return [];
    return [
      { name: 'Surveillance', value: complianceMetrics.surveillanceScore, color: '#3b82f6' },
      { name: 'Risk Compliance', value: complianceMetrics.riskComplianceScore, color: '#10b981' },
      { name: 'Regulatory', value: complianceMetrics.regulatoryComplianceScore, color: '#8b5cf6' },
    ];
  }, [complianceMetrics]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-blue-500"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Compliance Monitoring</h1>
          <p className="text-sm text-gray-600">
            Real-time compliance oversight and regulatory monitoring
          </p>
        </div>
        <div className="flex items-center space-x-2 mt-4 sm:mt-0">
          <Button variant="outline" size="sm">
            <DocumentChartBarIcon className="w-4 h-4 mr-2" />
            Generate Report
          </Button>
          <Button variant="outline" size="sm">
            <EyeIcon className="w-4 h-4 mr-2" />
            Audit Trail
          </Button>
        </div>
      </div>

      {/* Compliance Score Overview */}
      {complianceMetrics && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <Card className="bg-gradient-to-r from-blue-50 to-blue-100 border-blue-200">
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-blue-600">Overall Score</p>
                  <p className="text-2xl font-bold text-blue-900">
                    {complianceMetrics.overallComplianceScore}%
                  </p>
                </div>
                <ShieldCheckIcon className="w-8 h-8 text-blue-500" />
              </div>
            </CardContent>
          </Card>

          <Card className="bg-gradient-to-r from-red-50 to-red-100 border-red-200">
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-red-600">Active Breaches</p>
                  <p className="text-2xl font-bold text-red-900">
                    {complianceMetrics.activeBreaches}
                  </p>
                </div>
                <ExclamationTriangleIcon className="w-8 h-8 text-red-500" />
              </div>
            </CardContent>
          </Card>

          <Card className="bg-gradient-to-r from-green-50 to-green-100 border-green-200">
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-green-600">Resolved Today</p>
                  <p className="text-2xl font-bold text-green-900">
                    {complianceMetrics.resolvedToday}
                  </p>
                </div>
                <CheckCircleIcon className="w-8 h-8 text-green-500" />
              </div>
            </CardContent>
          </Card>

          <Card className="bg-gradient-to-r from-purple-50 to-purple-100 border-purple-200">
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-purple-600">Audit Integrity</p>
                  <p className="text-2xl font-bold text-purple-900">
                    {complianceMetrics.auditTrailIntegrity}%
                  </p>
                </div>
                <DocumentChartBarIcon className="w-8 h-8 text-purple-500" />
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Main Dashboard Tabs */}
      <Tabs defaultValue="overview" className="w-full">
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="alerts">Active Alerts</TabsTrigger>
          <TabsTrigger value="surveillance">Surveillance</TabsTrigger>
          <TabsTrigger value="risk">Risk Limits</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Compliance Scores Chart */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center">
                  <ChartBarSquareIcon className="w-5 h-5 mr-2" />
                  Compliance Scores
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={complianceScoreData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="name" />
                    <YAxis domain={[0, 100]} />
                    <Tooltip />
                    <Bar dataKey="value" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>

            {/* Recent Activity */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center">
                  <ClockIcon className="w-5 h-5 mr-2" />
                  Recent Activity
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4 max-h-80 overflow-y-auto">
                  {activeAlerts.slice(0, 5).map((alert) => (
                    <div key={alert.id} className="flex items-start space-x-3 p-3 bg-gray-50 rounded-lg">
                      {getStatusIcon(alert.status)}
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-gray-900 truncate">
                          {alert.title}
                        </p>
                        <p className="text-xs text-gray-500">
                          {formatDistanceToNow(new Date(alert.timestamp))} ago
                        </p>
                      </div>
                      <Badge 
                        variant="outline" 
                        className={`text-xs ${getSeverityColor(alert.severity)}`}
                      >
                        {alert.severity}
                      </Badge>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="alerts" className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-medium">Active Compliance Alerts</h3>
            <div className="flex space-x-2">
              <Button variant="outline" size="sm">Filter</Button>
              <Button variant="outline" size="sm">Sort</Button>
            </div>
          </div>

          <div className="space-y-4">
            <AnimatePresence>
              {activeAlerts.map((alert) => (
                <motion.div
                  key={alert.id}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -20 }}
                  className={`p-4 rounded-lg border-l-4 ${
                    alert.severity === 'critical' ? 'border-red-500 bg-red-50' :
                    alert.severity === 'high' ? 'border-orange-500 bg-orange-50' :
                    alert.severity === 'medium' ? 'border-yellow-500 bg-yellow-50' :
                    'border-blue-500 bg-blue-50'
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center space-x-2">
                        <h4 className="text-sm font-medium text-gray-900">{alert.title}</h4>
                        <Badge 
                          variant="outline" 
                          className={`text-xs ${getSeverityColor(alert.severity)}`}
                        >
                          {alert.severity}
                        </Badge>
                        <Badge variant="secondary" className="text-xs">
                          {alert.type}
                        </Badge>
                      </div>
                      <p className="text-sm text-gray-600 mt-1">{alert.description}</p>
                      <div className="flex items-center space-x-4 mt-2 text-xs text-gray-500">
                        <span>{formatDistanceToNow(new Date(alert.timestamp))} ago</span>
                        {alert.jurisdiction && <span>Jurisdiction: {alert.jurisdiction}</span>}
                        {alert.regulatoryFramework && <span>Framework: {alert.regulatoryFramework}</span>}
                      </div>
                    </div>
                    <div className="flex items-center space-x-2">
                      {getStatusIcon(alert.status)}
                      <Button variant="ghost" size="sm">
                        Acknowledge
                      </Button>
                      <Button variant="ghost" size="sm">
                        Details
                      </Button>
                    </div>
                  </div>
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
        </TabsContent>

        <TabsContent value="surveillance" className="space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <CardTitle>Pattern Detection Summary</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {surveillancePatterns.map((pattern) => (
                    <div key={pattern.pattern} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                      <div>
                        <p className="text-sm font-medium">{pattern.pattern}</p>
                        <p className="text-xs text-gray-500">
                          {pattern.count > 0 ? `Last: ${pattern.lastDetected}` : 'No recent activity'}
                        </p>
                      </div>
                      <div className="text-right">
                        <p className="text-lg font-bold">{pattern.count}</p>
                        <Badge 
                          variant="outline" 
                          className={`text-xs ${
                            pattern.severity === 'high' ? 'text-red-600 bg-red-50' :
                            pattern.severity === 'medium' ? 'text-yellow-600 bg-yellow-50' :
                            pattern.severity === 'low' ? 'text-blue-600 bg-blue-50' :
                            'text-gray-600 bg-gray-50'
                          }`}
                        >
                          {pattern.severity}
                        </Badge>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Surveillance Timeline</CardTitle>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={300}>
                  <LineChart data={[
                    { time: '00:00', alerts: 0 },
                    { time: '04:00', alerts: 1 },
                    { time: '08:00', alerts: 3 },
                    { time: '12:00', alerts: 2 },
                    { time: '16:00', alerts: 4 },
                    { time: '20:00', alerts: 1 },
                  ]}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="time" />
                    <YAxis />
                    <Tooltip />
                    <Line type="monotone" dataKey="alerts" stroke="#3b82f6" strokeWidth={2} />
                  </LineChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="risk" className="space-y-4">
          <div className="grid grid-cols-1 gap-4">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center">
                  <ExclamationTriangleIcon className="w-5 h-5 mr-2 text-red-500" />
                  Active Risk Limit Breaches
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {riskBreaches.map((breach) => (
                    <div key={breach.id} className="p-4 border border-red-200 bg-red-50 rounded-lg">
                      <div className="flex items-center justify-between mb-2">
                        <h4 className="text-sm font-medium text-red-900">{breach.limitType}</h4>
                        <Badge variant="destructive">
                          +{breach.exceedancePercent.toFixed(1)}%
                        </Badge>
                      </div>
                      <div className="grid grid-cols-2 gap-4 text-sm">
                        <div>
                          <p className="text-gray-600">Current Value</p>
                          <p className="font-medium">{breach.currentValue.toLocaleString()}</p>
                        </div>
                        <div>
                          <p className="text-gray-600">Limit Value</p>
                          <p className="font-medium">{breach.limitValue.toLocaleString()}</p>
                        </div>
                      </div>
                      <p className="text-xs text-gray-500 mt-2">
                        Detected {formatDistanceToNow(new Date(breach.timestamp))} ago
                      </p>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}