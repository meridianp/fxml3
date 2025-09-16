/**
 * Enhanced Deployment Manager Component
 *
 * Comprehensive model deployment management with version control
 */

'use client';

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { useAppStore } from '@/stores/appStore';
import {
  CloudArrowUpIcon,
  CloudArrowDownIcon,
  RocketLaunchIcon,
  StopIcon,
  ArrowPathIcon,
  EyeIcon,
  TrashIcon,
  ClockIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  CpuChipIcon,
  ServerIcon,
  ChartBarIcon,
  Cog6ToothIcon,
  TagIcon,
  DocumentTextIcon,
  ShieldCheckIcon,
  BoltIcon,
  GlobeAltIcon
} from '@heroicons/react/24/outline';

interface ModelDeployment {
  id: string;
  model_id: string;
  model_name: string;
  model_version: string;
  environment: 'development' | 'staging' | 'production';
  status: 'deploying' | 'deployed' | 'failed' | 'stopped' | 'rollback';
  endpoint_url: string;
  health_status: 'healthy' | 'degraded' | 'unhealthy';
  deployment_config: {
    instance_type: string;
    min_instances: number;
    max_instances: number;
    auto_scaling: boolean;
    cpu_limit: string;
    memory_limit: string;
    timeout: number;
  };
  performance_metrics: {
    requests_per_second: number;
    avg_latency_ms: number;
    error_rate: number;
    cpu_usage: number;
    memory_usage: number;
    predictions_total: number;
  };
  version_history: Array<{
    version: string;
    deployed_at: string;
    deployed_by: string;
    rollback_available: boolean;
  }>;
  created: string;
  deployed_at: string;
  last_health_check: string;
  tags: string[];
  notes: string;
}

interface DeploymentTarget {
  id: string;
  name: string;
  type: 'kubernetes' | 'docker' | 'lambda' | 'vertex_ai' | 'sagemaker';
  region: string;
  status: 'available' | 'unavailable' | 'maintenance';
  config: Record<string, any>;
}

interface DeploymentManagerProps {
  models?: any[];
}

export default function DeploymentManager({ models = [] }: DeploymentManagerProps) {
  const [activeTab, setActiveTab] = useState('deployments');
  const [deployments, setDeployments] = useState<ModelDeployment[]>([]);
  const [targets, setTargets] = useState<DeploymentTarget[]>([]);
  const [selectedDeployment, setSelectedDeployment] = useState<ModelDeployment | null>(null);
  const [showDeployForm, setShowDeployForm] = useState(false);
  const [deployForm, setDeployForm] = useState({
    model_id: '',
    environment: 'development' as const,
    target_id: '',
    instance_type: 't3.medium',
    min_instances: 1,
    max_instances: 3,
    auto_scaling: true
  });

  const { addNotification, addError } = useAppStore();

  useEffect(() => {
    loadDeployments();
    loadTargets();
  }, []);

  const loadDeployments = () => {
    // Mock deployments data
    const mockDeployments: ModelDeployment[] = [
      {
        id: 'dep_001',
        model_id: 'model_001',
        model_name: 'LSTM_EURUSD_v1',
        model_version: '1.2.3',
        environment: 'production',
        status: 'deployed',
        endpoint_url: 'https://api.fxml4.com/models/lstm-eurusd-v1/predict',
        health_status: 'healthy',
        deployment_config: {
          instance_type: 't3.large',
          min_instances: 2,
          max_instances: 5,
          auto_scaling: true,
          cpu_limit: '2000m',
          memory_limit: '4Gi',
          timeout: 30000
        },
        performance_metrics: {
          requests_per_second: 45.2,
          avg_latency_ms: 125,
          error_rate: 0.02,
          cpu_usage: 0.68,
          memory_usage: 0.74,
          predictions_total: 15847
        },
        version_history: [
          {
            version: '1.2.3',
            deployed_at: '2024-01-15T10:00:00Z',
            deployed_by: 'admin@fxml4.com',
            rollback_available: false
          },
          {
            version: '1.2.2',
            deployed_at: '2024-01-12T14:30:00Z',
            deployed_by: 'admin@fxml4.com',
            rollback_available: true
          },
          {
            version: '1.2.1',
            deployed_at: '2024-01-10T09:15:00Z',
            deployed_by: 'admin@fxml4.com',
            rollback_available: true
          }
        ],
        created: '2024-01-10T09:15:00Z',
        deployed_at: '2024-01-15T10:05:00Z',
        last_health_check: '2024-01-15T12:30:00Z',
        tags: ['production', 'lstm', 'eurusd', 'primary'],
        notes: 'Primary EURUSD prediction model in production. Excellent performance metrics.'
      },
      {
        id: 'dep_002',
        model_id: 'model_002',
        model_name: 'XGBoost_MultiPair_v2',
        model_version: '2.1.0',
        environment: 'staging',
        status: 'deployed',
        endpoint_url: 'https://staging.fxml4.com/models/xgboost-multipair/predict',
        health_status: 'healthy',
        deployment_config: {
          instance_type: 't3.medium',
          min_instances: 1,
          max_instances: 2,
          auto_scaling: true,
          cpu_limit: '1000m',
          memory_limit: '2Gi',
          timeout: 15000
        },
        performance_metrics: {
          requests_per_second: 12.8,
          avg_latency_ms: 89,
          error_rate: 0.01,
          cpu_usage: 0.45,
          memory_usage: 0.52,
          predictions_total: 3245
        },
        version_history: [
          {
            version: '2.1.0',
            deployed_at: '2024-01-14T16:00:00Z',
            deployed_by: 'dev@fxml4.com',
            rollback_available: false
          },
          {
            version: '2.0.9',
            deployed_at: '2024-01-13T11:20:00Z',
            deployed_by: 'dev@fxml4.com',
            rollback_available: true
          }
        ],
        created: '2024-01-13T11:20:00Z',
        deployed_at: '2024-01-14T16:05:00Z',
        last_health_check: '2024-01-15T12:28:00Z',
        tags: ['staging', 'xgboost', 'multi-pair', 'candidate'],
        notes: 'Multi-pair model in staging for final testing before production deployment.'
      },
      {
        id: 'dep_003',
        model_id: 'model_003',
        model_name: 'Transformer_Experimental',
        model_version: '0.8.1',
        environment: 'development',
        status: 'deploying',
        endpoint_url: '',
        health_status: 'unhealthy',
        deployment_config: {
          instance_type: 't3.small',
          min_instances: 1,
          max_instances: 1,
          auto_scaling: false,
          cpu_limit: '500m',
          memory_limit: '1Gi',
          timeout: 10000
        },
        performance_metrics: {
          requests_per_second: 0,
          avg_latency_ms: 0,
          error_rate: 0,
          cpu_usage: 0,
          memory_usage: 0,
          predictions_total: 0
        },
        version_history: [
          {
            version: '0.8.1',
            deployed_at: '2024-01-15T14:00:00Z',
            deployed_by: 'researcher@fxml4.com',
            rollback_available: false
          }
        ],
        created: '2024-01-15T14:00:00Z',
        deployed_at: '2024-01-15T14:00:00Z',
        last_health_check: '',
        tags: ['development', 'transformer', 'experimental'],
        notes: 'Experimental transformer model for research purposes.'
      }
    ];

    setDeployments(mockDeployments);
  };

  const loadTargets = () => {
    const mockTargets: DeploymentTarget[] = [
      {
        id: 'target_k8s',
        name: 'Kubernetes Cluster',
        type: 'kubernetes',
        region: 'us-east-1',
        status: 'available',
        config: { cluster_name: 'fxml4-prod', namespace: 'ml-models' }
      },
      {
        id: 'target_vertex',
        name: 'Google Vertex AI',
        type: 'vertex_ai',
        region: 'us-central1',
        status: 'available',
        config: { project_id: 'fxml4-project', endpoint_region: 'us-central1' }
      },
      {
        id: 'target_lambda',
        name: 'AWS Lambda',
        type: 'lambda',
        region: 'us-east-1',
        status: 'maintenance',
        config: { runtime: 'python3.9', architecture: 'x86_64' }
      }
    ];

    setTargets(mockTargets);
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'deployed':
        return <CheckCircleIcon className="w-4 h-4 text-green-400" />;
      case 'deploying':
        return <ClockIcon className="w-4 h-4 text-yellow-400 animate-pulse" />;
      case 'failed':
      case 'stopped':
        return <ExclamationTriangleIcon className="w-4 h-4 text-red-400" />;
      case 'rollback':
        return <ArrowPathIcon className="w-4 h-4 text-orange-400" />;
      default:
        return <CloudArrowDownIcon className="w-4 h-4 text-gray-400" />;
    }
  };

  const getHealthIcon = (health: string) => {
    switch (health) {
      case 'healthy':
        return <ShieldCheckIcon className="w-4 h-4 text-green-400" />;
      case 'degraded':
        return <ExclamationTriangleIcon className="w-4 h-4 text-yellow-400" />;
      case 'unhealthy':
        return <ExclamationTriangleIcon className="w-4 h-4 text-red-400" />;
      default:
        return <ShieldCheckIcon className="w-4 h-4 text-gray-400" />;
    }
  };

  const getEnvironmentColor = (env: string) => {
    switch (env) {
      case 'production':
        return 'text-red-400 bg-red-500/20';
      case 'staging':
        return 'text-yellow-400 bg-yellow-500/20';
      case 'development':
        return 'text-blue-400 bg-blue-500/20';
      default:
        return 'text-gray-400 bg-gray-500/20';
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'deployed':
        return 'text-green-400 bg-green-500/20';
      case 'deploying':
        return 'text-yellow-400 bg-yellow-500/20';
      case 'failed':
      case 'stopped':
        return 'text-red-400 bg-red-500/20';
      case 'rollback':
        return 'text-orange-400 bg-orange-500/20';
      default:
        return 'text-gray-400 bg-gray-500/20';
    }
  };

  const deployModel = async () => {
    try {
      const newDeployment: Partial<ModelDeployment> = {
        id: `dep_${Date.now()}`,
        model_id: deployForm.model_id,
        model_name: models.find(m => m.id === deployForm.model_id)?.name || 'Unknown Model',
        model_version: '1.0.0',
        environment: deployForm.environment,
        status: 'deploying',
        deployment_config: {
          instance_type: deployForm.instance_type,
          min_instances: deployForm.min_instances,
          max_instances: deployForm.max_instances,
          auto_scaling: deployForm.auto_scaling,
          cpu_limit: '1000m',
          memory_limit: '2Gi',
          timeout: 30000
        }
      };

      // Simulate deployment process
      setDeployments(prev => [...prev, newDeployment as ModelDeployment]);
      setShowDeployForm(false);

      addNotification({
        type: 'info',
        title: 'Deployment Started',
        message: `Model deployment to ${deployForm.environment} environment initiated`
      });

      // Simulate deployment completion
      setTimeout(() => {
        setDeployments(prev => prev.map(dep =>
          dep.id === newDeployment.id
            ? {
                ...dep,
                status: 'deployed' as const,
                endpoint_url: `https://api.fxml4.com/models/${dep.model_name.toLowerCase()}/predict`,
                health_status: 'healthy' as const,
                deployed_at: new Date().toISOString()
              }
            : dep
        ));

        addNotification({
          type: 'success',
          title: 'Deployment Successful',
          message: 'Model has been successfully deployed and is ready to serve predictions'
        });
      }, 3000);

    } catch (error) {
      console.error('Deployment failed:', error);
      addError({
        code: 'DEPLOYMENT_ERROR',
        message: 'Failed to deploy model',
        timestamp: new Date().toISOString()
      });
    }
  };

  const stopDeployment = (deploymentId: string) => {
    setDeployments(prev => prev.map(dep =>
      dep.id === deploymentId
        ? { ...dep, status: 'stopped' as const, health_status: 'unhealthy' as const }
        : dep
    ));

    addNotification({
      type: 'warning',
      title: 'Deployment Stopped',
      message: 'Model deployment has been stopped'
    });
  };

  const rollbackDeployment = (deploymentId: string, targetVersion: string) => {
    setDeployments(prev => prev.map(dep =>
      dep.id === deploymentId
        ? {
            ...dep,
            status: 'rollback' as const,
            model_version: targetVersion,
            version_history: [
              {
                version: targetVersion,
                deployed_at: new Date().toISOString(),
                deployed_by: 'admin@fxml4.com',
                rollback_available: false
              },
              ...dep.version_history
            ]
          }
        : dep
    ));

    addNotification({
      type: 'info',
      title: 'Rollback Initiated',
      message: `Rolling back to version ${targetVersion}`
    });

    // Simulate rollback completion
    setTimeout(() => {
      setDeployments(prev => prev.map(dep =>
        dep.id === deploymentId
          ? { ...dep, status: 'deployed' as const }
          : dep
      ));

      addNotification({
        type: 'success',
        title: 'Rollback Complete',
        message: `Successfully rolled back to version ${targetVersion}`
      });
    }, 2000);
  };

  return (
    <div className="h-full">
      <Tabs value={activeTab} onValueChange={setActiveTab} className="h-full flex flex-col">
        <div className="p-6 border-b border-gray-700 bg-gray-900/50">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-xl font-semibold text-white">Model Deployment</h2>
              <p className="text-gray-400 text-sm mt-1">
                Deploy and manage ML models with version control and monitoring
              </p>
            </div>

            <div className="flex items-center gap-3">
              <Button
                onClick={() => setShowDeployForm(true)}
                className="gap-2"
              >
                <CloudArrowUpIcon className="w-4 h-4" />
                Deploy Model
              </Button>
            </div>
          </div>

          <TabsList className="grid w-full grid-cols-3 bg-gray-800">
            <TabsTrigger value="deployments" className="gap-2">
              <CloudArrowDownIcon className="w-4 h-4" />
              Deployments
            </TabsTrigger>
            <TabsTrigger value="targets" className="gap-2">
              <ServerIcon className="w-4 h-4" />
              Targets
            </TabsTrigger>
            <TabsTrigger value="monitoring" className="gap-2">
              <ChartBarIcon className="w-4 h-4" />
              Monitoring
            </TabsTrigger>
          </TabsList>
        </div>

        <div className="flex-1 p-6">
          <TabsContent value="deployments" className="h-full mt-0">
            <div className="space-y-6">
              {deployments.map(deployment => (
                <div key={deployment.id} className="bg-gray-900 border border-gray-700 rounded-lg p-6">
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex items-start gap-4">
                      <div className="w-12 h-12 bg-blue-500 rounded-lg flex items-center justify-center">
                        <RocketLaunchIcon className="w-6 h-6 text-white" />
                      </div>

                      <div>
                        <div className="flex items-center gap-3 mb-2">
                          <h3 className="text-lg font-semibold text-white">{deployment.model_name}</h3>
                          <span className="text-sm px-2 py-1 bg-gray-700 text-gray-300 rounded">
                            v{deployment.model_version}
                          </span>
                          <span className={`text-xs px-2 py-1 rounded ${getEnvironmentColor(deployment.environment)}`}>
                            {deployment.environment.toUpperCase()}
                          </span>
                        </div>

                        <div className="flex items-center gap-4 mb-2">
                          <div className="flex items-center gap-2">
                            {getStatusIcon(deployment.status)}
                            <span className={`text-xs px-2 py-1 rounded ${getStatusColor(deployment.status)}`}>
                              {deployment.status.toUpperCase()}
                            </span>
                          </div>

                          <div className="flex items-center gap-2">
                            {getHealthIcon(deployment.health_status)}
                            <span className="text-sm text-gray-400">
                              {deployment.health_status}
                            </span>
                          </div>
                        </div>

                        {deployment.endpoint_url && (
                          <div className="flex items-center gap-2 text-sm text-gray-400">
                            <GlobeAltIcon className="w-4 h-4" />
                            <span className="font-mono">{deployment.endpoint_url}</span>
                          </div>
                        )}
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => setSelectedDeployment(deployment)}
                        className="p-2"
                      >
                        <EyeIcon className="w-4 h-4" />
                      </Button>

                      {deployment.status === 'deployed' && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => stopDeployment(deployment.id)}
                          className="p-2 text-red-400"
                        >
                          <StopIcon className="w-4 h-4" />
                        </Button>
                      )}

                      <Button
                        size="sm"
                        variant="outline"
                        className="p-2 text-red-400"
                      >
                        <TrashIcon className="w-4 h-4" />
                      </Button>
                    </div>
                  </div>

                  {deployment.status === 'deployed' && (
                    <div className="grid grid-cols-2 lg:grid-cols-6 gap-4 mb-4">
                      <div className="bg-gray-800/50 rounded p-3 text-center">
                        <div className="text-lg font-bold text-blue-400">
                          {deployment.performance_metrics.requests_per_second.toFixed(1)}
                        </div>
                        <div className="text-xs text-gray-400">RPS</div>
                      </div>

                      <div className="bg-gray-800/50 rounded p-3 text-center">
                        <div className="text-lg font-bold text-green-400">
                          {deployment.performance_metrics.avg_latency_ms}ms
                        </div>
                        <div className="text-xs text-gray-400">Latency</div>
                      </div>

                      <div className="bg-gray-800/50 rounded p-3 text-center">
                        <div className="text-lg font-bold text-red-400">
                          {(deployment.performance_metrics.error_rate * 100).toFixed(2)}%
                        </div>
                        <div className="text-xs text-gray-400">Error Rate</div>
                      </div>

                      <div className="bg-gray-800/50 rounded p-3 text-center">
                        <div className="text-lg font-bold text-yellow-400">
                          {(deployment.performance_metrics.cpu_usage * 100).toFixed(0)}%
                        </div>
                        <div className="text-xs text-gray-400">CPU</div>
                      </div>

                      <div className="bg-gray-800/50 rounded p-3 text-center">
                        <div className="text-lg font-bold text-purple-400">
                          {(deployment.performance_metrics.memory_usage * 100).toFixed(0)}%
                        </div>
                        <div className="text-xs text-gray-400">Memory</div>
                      </div>

                      <div className="bg-gray-800/50 rounded p-3 text-center">
                        <div className="text-lg font-bold text-orange-400">
                          {deployment.performance_metrics.predictions_total.toLocaleString()}
                        </div>
                        <div className="text-xs text-gray-400">Predictions</div>
                      </div>
                    </div>
                  )}

                  <div className="flex items-center justify-between">
                    <div className="flex flex-wrap gap-1">
                      {deployment.tags.map(tag => (
                        <span
                          key={tag}
                          className="text-xs px-2 py-1 bg-gray-800 text-gray-300 rounded-full"
                        >
                          {tag}
                        </span>
                      ))}
                    </div>

                    <div className="flex items-center gap-2">
                      <span className="text-sm text-gray-400">
                        Deployed {new Date(deployment.deployed_at).toLocaleDateString()}
                      </span>

                      {deployment.version_history.length > 1 && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => rollbackDeployment(
                            deployment.id,
                            deployment.version_history[1].version
                          )}
                          className="gap-1"
                        >
                          <ArrowPathIcon className="w-3 h-3" />
                          Rollback
                        </Button>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </TabsContent>

          <TabsContent value="targets" className="h-full mt-0">
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {targets.map(target => (
                <div key={target.id} className="bg-gray-900 border border-gray-700 rounded-lg p-6">
                  <div className="flex items-center gap-3 mb-4">
                    <div className="w-10 h-10 bg-purple-500 rounded-lg flex items-center justify-center">
                      <ServerIcon className="w-5 h-5 text-white" />
                    </div>
                    <div>
                      <h3 className="font-semibold text-white">{target.name}</h3>
                      <p className="text-sm text-gray-400">{target.type.replace('_', ' ')}</p>
                    </div>
                  </div>

                  <div className="space-y-2 mb-4">
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-400">Region:</span>
                      <span className="text-white">{target.region}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-400">Status:</span>
                      <span className={`px-2 py-1 rounded text-xs ${
                        target.status === 'available' ? 'text-green-400 bg-green-500/20' :
                        target.status === 'maintenance' ? 'text-yellow-400 bg-yellow-500/20' :
                        'text-red-400 bg-red-500/20'
                      }`}>
                        {target.status.toUpperCase()}
                      </span>
                    </div>
                  </div>

                  <Button
                    size="sm"
                    variant="outline"
                    className="w-full gap-2"
                    disabled={target.status !== 'available'}
                  >
                    <Cog6ToothIcon className="w-4 h-4" />
                    Configure
                  </Button>
                </div>
              ))}
            </div>
          </TabsContent>

          <TabsContent value="monitoring" className="h-full mt-0">
            <div className="text-center py-12">
              <ChartBarIcon className="w-16 h-16 text-gray-400 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-300 mb-2">Deployment Monitoring</h3>
              <p className="text-gray-400">
                Real-time monitoring dashboards for deployed models
              </p>
            </div>
          </TabsContent>
        </div>
      </Tabs>

      {/* Deploy Model Modal */}
      {showDeployForm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-gray-900 border border-gray-700 rounded-lg max-w-2xl w-full">
            <div className="p-6 border-b border-gray-700">
              <h3 className="text-xl font-semibold text-white">Deploy Model</h3>
              <p className="text-gray-400 mt-1">Configure model deployment settings</p>
            </div>

            <div className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">Model</label>
                <select
                  value={deployForm.model_id}
                  onChange={(e) => setDeployForm(prev => ({ ...prev, model_id: e.target.value }))}
                  className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white"
                >
                  <option value="">Select a model</option>
                  {models.map(model => (
                    <option key={model.id} value={model.id}>{model.name}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">Environment</label>
                <select
                  value={deployForm.environment}
                  onChange={(e) => setDeployForm(prev => ({ ...prev, environment: e.target.value as any }))}
                  className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white"
                >
                  <option value="development">Development</option>
                  <option value="staging">Staging</option>
                  <option value="production">Production</option>
                </select>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">Instance Type</label>
                  <select
                    value={deployForm.instance_type}
                    onChange={(e) => setDeployForm(prev => ({ ...prev, instance_type: e.target.value }))}
                    className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white"
                  >
                    <option value="t3.small">t3.small (2 vCPUs, 2GB)</option>
                    <option value="t3.medium">t3.medium (2 vCPUs, 4GB)</option>
                    <option value="t3.large">t3.large (2 vCPUs, 8GB)</option>
                    <option value="c5.large">c5.large (2 vCPUs, 4GB)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">Target</label>
                  <select
                    value={deployForm.target_id}
                    onChange={(e) => setDeployForm(prev => ({ ...prev, target_id: e.target.value }))}
                    className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white"
                  >
                    <option value="">Select target</option>
                    {targets.filter(t => t.status === 'available').map(target => (
                      <option key={target.id} value={target.id}>{target.name}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">Min Instances</label>
                  <input
                    type="number"
                    value={deployForm.min_instances}
                    onChange={(e) => setDeployForm(prev => ({ ...prev, min_instances: parseInt(e.target.value) || 1 }))}
                    min="1"
                    max="10"
                    className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">Max Instances</label>
                  <input
                    type="number"
                    value={deployForm.max_instances}
                    onChange={(e) => setDeployForm(prev => ({ ...prev, max_instances: parseInt(e.target.value) || 1 }))}
                    min="1"
                    max="20"
                    className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white"
                  />
                </div>
              </div>

              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="auto_scaling"
                  checked={deployForm.auto_scaling}
                  onChange={(e) => setDeployForm(prev => ({ ...prev, auto_scaling: e.target.checked }))}
                  className="w-4 h-4 text-blue-500 bg-gray-800 border-gray-600 rounded focus:ring-blue-500"
                />
                <label htmlFor="auto_scaling" className="text-sm text-gray-300">
                  Enable Auto Scaling
                </label>
              </div>
            </div>

            <div className="p-6 border-t border-gray-700 flex justify-end gap-3">
              <Button
                variant="outline"
                onClick={() => setShowDeployForm(false)}
              >
                Cancel
              </Button>
              <Button
                onClick={deployModel}
                disabled={!deployForm.model_id || !deployForm.target_id}
                className="gap-2"
              >
                <CloudArrowUpIcon className="w-4 h-4" />
                Deploy
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Deployment Detail Modal */}
      {selectedDeployment && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-gray-900 border border-gray-700 rounded-lg max-w-4xl w-full max-h-[90vh] overflow-y-auto">
            <div className="p-6 border-b border-gray-700">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-xl font-semibold text-white">{selectedDeployment.model_name}</h3>
                  <p className="text-gray-400 mt-1">
                    Deployment Details - v{selectedDeployment.model_version}
                  </p>
                </div>
                <Button
                  variant="outline"
                  onClick={() => setSelectedDeployment(null)}
                >
                  Close
                </Button>
              </div>
            </div>

            <div className="p-6 space-y-6">
              {/* Version History */}
              <div>
                <h4 className="text-lg font-medium text-white mb-3">Version History</h4>
                <div className="space-y-3">
                  {selectedDeployment.version_history.map((version, index) => (
                    <div key={index} className="flex items-center justify-between p-3 bg-gray-800/50 rounded">
                      <div>
                        <div className="font-medium text-white">Version {version.version}</div>
                        <div className="text-sm text-gray-400">
                          Deployed by {version.deployed_by} on{' '}
                          {new Date(version.deployed_at).toLocaleDateString()}
                        </div>
                      </div>

                      <div className="flex items-center gap-2">
                        {index === 0 && (
                          <span className="text-xs px-2 py-1 bg-green-500/20 text-green-400 rounded">
                            CURRENT
                          </span>
                        )}
                        {version.rollback_available && index > 0 && (
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => rollbackDeployment(selectedDeployment.id, version.version)}
                            className="gap-1"
                          >
                            <ArrowPathIcon className="w-3 h-3" />
                            Rollback
                          </Button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Configuration */}
              <div>
                <h4 className="text-lg font-medium text-white mb-3">Deployment Configuration</h4>
                <div className="grid grid-cols-2 gap-4">
                  {Object.entries(selectedDeployment.deployment_config).map(([key, value]) => (
                    <div key={key} className="bg-gray-800/50 rounded p-3">
                      <div className="text-sm text-gray-400">{key.replace('_', ' ')}</div>
                      <div className="font-medium text-white">{String(value)}</div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Notes */}
              {selectedDeployment.notes && (
                <div>
                  <h4 className="text-lg font-medium text-white mb-3">Notes</h4>
                  <div className="bg-gray-800/50 rounded p-4">
                    <p className="text-gray-300">{selectedDeployment.notes}</p>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
