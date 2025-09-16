/**
 * Dataset Manager Component
 *
 * Comprehensive dataset management with data pipeline interface
 */

'use client';

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { useAppStore } from '@/stores/appStore';
import {
  DatabaseIcon,
  FolderIcon,
  ArrowPathIcon,
  PlayIcon,
  StopIcon,
  DocumentTextIcon,
  ChartBarIcon,
  CloudArrowUpIcon,
  TrashIcon,
  EyeIcon,
  PencilIcon,
  PlusIcon,
  ArrowDownTrayIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  ClockIcon,
  CpuChipIcon
} from '@heroicons/react/24/outline';

interface DataSource {
  id: string;
  name: string;
  type: 'polygon' | 'interactive_brokers' | 'csv_upload' | 'database' | 'api';
  config: Record<string, any>;
  status: 'connected' | 'disconnected' | 'error';
  lastSync: string;
  totalRecords: number;
}

interface Dataset {
  id: string;
  name: string;
  description: string;
  source: DataSource;
  version: number;
  status: 'creating' | 'ready' | 'processing' | 'error';
  size: number; // bytes
  recordCount: number;
  schema: {
    columns: Array<{
      name: string;
      type: 'datetime' | 'float' | 'integer' | 'string' | 'boolean';
      nullable: boolean;
    }>;
  };
  features: {
    timeframe: string;
    symbols: string[];
    dateRange: {
      start: string;
      end: string;
    };
    preprocessing: PreprocessingStep[];
  };
  created: string;
  lastModified: string;
  tags: string[];
}

interface PreprocessingStep {
  id: string;
  name: string;
  type: 'fill_missing' | 'normalize' | 'technical_indicators' | 'feature_engineering' | 'filter' | 'transform';
  config: Record<string, any>;
  enabled: boolean;
  order: number;
}

interface DataPipeline {
  id: string;
  name: string;
  description: string;
  datasets: string[]; // dataset IDs
  steps: PreprocessingStep[];
  schedule?: {
    enabled: boolean;
    cron: string;
    timezone: string;
  };
  status: 'idle' | 'running' | 'completed' | 'error';
  lastRun?: string;
  nextRun?: string;
}

interface DatasetManagerProps {
  onDatasetSelect: (dataset: Dataset) => void;
}

export default function DatasetManager({ onDatasetSelect }: DatasetManagerProps) {
  const [activeTab, setActiveTab] = useState('datasets');
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [dataSources, setDataSources] = useState<DataSource[]>([]);
  const [pipelines, setPipelines] = useState<DataPipeline[]>([]);
  const [selectedDataset, setSelectedDataset] = useState<Dataset | null>(null);
  const [isCreatingDataset, setIsCreatingDataset] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterStatus, setFilterStatus] = useState<string>('all');

  const { addNotification, addError } = useAppStore();

  useEffect(() => {
    loadDatasets();
    loadDataSources();
    loadPipelines();
  }, []);

  const loadDatasets = () => {
    // Mock datasets - in production, load from API
    const mockDatasets: Dataset[] = [
      {
        id: 'ds_001',
        name: 'EURUSD_H1_2023',
        description: 'EURUSD hourly data for 2023 with technical indicators',
        source: {
          id: 'src_polygon',
          name: 'Polygon.io',
          type: 'polygon',
          config: { api_key: 'xxx', tier: 'basic' },
          status: 'connected',
          lastSync: '2024-01-15T10:30:00Z',
          totalRecords: 8760
        },
        version: 3,
        status: 'ready',
        size: 1245680,
        recordCount: 8760,
        schema: {
          columns: [
            { name: 'timestamp', type: 'datetime', nullable: false },
            { name: 'open', type: 'float', nullable: false },
            { name: 'high', type: 'float', nullable: false },
            { name: 'low', type: 'float', nullable: false },
            { name: 'close', type: 'float', nullable: false },
            { name: 'volume', type: 'integer', nullable: true },
            { name: 'rsi_14', type: 'float', nullable: true },
            { name: 'sma_20', type: 'float', nullable: true },
            { name: 'ema_50', type: 'float', nullable: true }
          ]
        },
        features: {
          timeframe: '1H',
          symbols: ['EURUSD'],
          dateRange: {
            start: '2023-01-01T00:00:00Z',
            end: '2023-12-31T23:59:59Z'
          },
          preprocessing: [
            {
              id: 'step_1',
              name: 'Fill Missing Values',
              type: 'fill_missing',
              config: { method: 'forward_fill' },
              enabled: true,
              order: 1
            },
            {
              id: 'step_2',
              name: 'Technical Indicators',
              type: 'technical_indicators',
              config: { indicators: ['rsi', 'sma', 'ema'] },
              enabled: true,
              order: 2
            }
          ]
        },
        created: '2024-01-10T09:00:00Z',
        lastModified: '2024-01-15T11:30:00Z',
        tags: ['forex', 'hourly', 'eurusd', 'indicators']
      },
      {
        id: 'ds_002',
        name: 'Multi_Pair_Daily_ML',
        description: 'Multiple currency pairs with ML features for daily predictions',
        source: {
          id: 'src_ib',
          name: 'Interactive Brokers',
          type: 'interactive_brokers',
          config: { account: 'DU123456' },
          status: 'connected',
          lastSync: '2024-01-15T08:00:00Z',
          totalRecords: 12450
        },
        version: 1,
        status: 'processing',
        size: 2456790,
        recordCount: 0, // Still processing
        schema: {
          columns: [
            { name: 'timestamp', type: 'datetime', nullable: false },
            { name: 'symbol', type: 'string', nullable: false },
            { name: 'open', type: 'float', nullable: false },
            { name: 'high', type: 'float', nullable: false },
            { name: 'low', type: 'float', nullable: false },
            { name: 'close', type: 'float', nullable: false },
            { name: 'volume', type: 'integer', nullable: true }
          ]
        },
        features: {
          timeframe: '1D',
          symbols: ['EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD'],
          dateRange: {
            start: '2022-01-01T00:00:00Z',
            end: '2024-01-15T23:59:59Z'
          },
          preprocessing: [
            {
              id: 'step_1',
              name: 'Multi-Symbol Normalization',
              type: 'normalize',
              config: { method: 'z_score', group_by: 'symbol' },
              enabled: true,
              order: 1
            },
            {
              id: 'step_2',
              name: 'Feature Engineering',
              type: 'feature_engineering',
              config: { features: ['price_changes', 'volatility', 'correlation'] },
              enabled: true,
              order: 2
            }
          ]
        },
        created: '2024-01-15T07:00:00Z',
        lastModified: '2024-01-15T10:00:00Z',
        tags: ['forex', 'daily', 'multi-pair', 'ml-ready']
      }
    ];

    setDatasets(mockDatasets);
  };

  const loadDataSources = () => {
    const mockSources: DataSource[] = [
      {
        id: 'src_polygon',
        name: 'Polygon.io',
        type: 'polygon',
        config: { api_key: 'xxx', tier: 'basic' },
        status: 'connected',
        lastSync: '2024-01-15T10:30:00Z',
        totalRecords: 15430
      },
      {
        id: 'src_ib',
        name: 'Interactive Brokers',
        type: 'interactive_brokers',
        config: { account: 'DU123456' },
        status: 'connected',
        lastSync: '2024-01-15T08:00:00Z',
        totalRecords: 8920
      },
      {
        id: 'src_csv',
        name: 'Historical CSV Files',
        type: 'csv_upload',
        config: { upload_path: '/data/uploads' },
        status: 'disconnected',
        lastSync: '2024-01-10T14:00:00Z',
        totalRecords: 5600
      }
    ];

    setDataSources(mockSources);
  };

  const loadPipelines = () => {
    const mockPipelines: DataPipeline[] = [
      {
        id: 'pip_001',
        name: 'Daily Data Refresh',
        description: 'Automated daily refresh of all forex datasets',
        datasets: ['ds_001', 'ds_002'],
        steps: [
          {
            id: 'sync_step',
            name: 'Sync Latest Data',
            type: 'transform',
            config: { source: 'all_connected' },
            enabled: true,
            order: 1
          },
          {
            id: 'process_step',
            name: 'Apply Preprocessing',
            type: 'feature_engineering',
            config: { rebuild_features: true },
            enabled: true,
            order: 2
          }
        ],
        schedule: {
          enabled: true,
          cron: '0 2 * * *', // Daily at 2 AM
          timezone: 'UTC'
        },
        status: 'idle',
        lastRun: '2024-01-15T02:05:00Z',
        nextRun: '2024-01-16T02:00:00Z'
      }
    ];

    setPipelines(mockPipelines);
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'ready':
      case 'connected':
      case 'completed':
        return <CheckCircleIcon className="w-4 h-4 text-green-400" />;
      case 'processing':
      case 'creating':
      case 'running':
        return <ClockIcon className="w-4 h-4 text-yellow-400 animate-pulse" />;
      case 'error':
      case 'disconnected':
        return <ExclamationTriangleIcon className="w-4 h-4 text-red-400" />;
      default:
        return <DatabaseIcon className="w-4 h-4 text-gray-400" />;
    }
  };

  const getStatusColor = (status: string): string => {
    switch (status) {
      case 'ready':
      case 'connected':
      case 'completed':
        return 'text-green-400 bg-green-500/20';
      case 'processing':
      case 'creating':
      case 'running':
        return 'text-yellow-400 bg-yellow-500/20';
      case 'error':
      case 'disconnected':
        return 'text-red-400 bg-red-500/20';
      default:
        return 'text-gray-400 bg-gray-500/20';
    }
  };

  const filteredDatasets = datasets.filter(dataset => {
    const matchesSearch = dataset.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         dataset.description.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         dataset.tags.some(tag => tag.toLowerCase().includes(searchTerm.toLowerCase()));

    const matchesFilter = filterStatus === 'all' || dataset.status === filterStatus;

    return matchesSearch && matchesFilter;
  });

  const createNewDataset = () => {
    setIsCreatingDataset(true);
    // This would open a dataset creation modal or form
    addNotification({
      type: 'info',
      title: 'Dataset Creation',
      message: 'Dataset creation form would open here'
    });
    setIsCreatingDataset(false);
  };

  const deleteDataset = (datasetId: string) => {
    setDatasets(prev => prev.filter(ds => ds.id !== datasetId));
    addNotification({
      type: 'success',
      title: 'Dataset Deleted',
      message: 'Dataset has been successfully deleted'
    });
  };

  const runPipeline = (pipelineId: string) => {
    setPipelines(prev => prev.map(pip =>
      pip.id === pipelineId ? { ...pip, status: 'running' } : pip
    ));

    addNotification({
      type: 'info',
      title: 'Pipeline Started',
      message: 'Data pipeline is now running'
    });

    // Simulate pipeline completion
    setTimeout(() => {
      setPipelines(prev => prev.map(pip =>
        pip.id === pipelineId ? {
          ...pip,
          status: 'completed',
          lastRun: new Date().toISOString()
        } : pip
      ));
    }, 3000);
  };

  return (
    <div className="h-full">
      <Tabs value={activeTab} onValueChange={setActiveTab} className="h-full flex flex-col">
        <div className="p-6 border-b border-gray-700 bg-gray-900/50">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-xl font-semibold text-white">Dataset Management</h2>
              <p className="text-gray-400 text-sm mt-1">
                Manage datasets, data sources, and processing pipelines
              </p>
            </div>

            <div className="flex items-center gap-3">
              <Button
                onClick={createNewDataset}
                disabled={isCreatingDataset}
                className="gap-2"
              >
                <PlusIcon className="w-4 h-4" />
                New Dataset
              </Button>
            </div>
          </div>

          <TabsList className="grid w-full grid-cols-3 bg-gray-800">
            <TabsTrigger value="datasets" className="gap-2">
              <DatabaseIcon className="w-4 h-4" />
              Datasets
            </TabsTrigger>
            <TabsTrigger value="sources" className="gap-2">
              <FolderIcon className="w-4 h-4" />
              Data Sources
            </TabsTrigger>
            <TabsTrigger value="pipelines" className="gap-2">
              <CpuChipIcon className="w-4 h-4" />
              Pipelines
            </TabsTrigger>
          </TabsList>
        </div>

        <div className="flex-1 p-6">
          <TabsContent value="datasets" className="h-full mt-0">
            <div className="mb-6 flex items-center gap-4">
              <div className="flex-1">
                <input
                  type="text"
                  placeholder="Search datasets..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="w-full px-4 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white placeholder-gray-400"
                />
              </div>

              <select
                value={filterStatus}
                onChange={(e) => setFilterStatus(e.target.value)}
                className="px-3 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white"
              >
                <option value="all">All Status</option>
                <option value="ready">Ready</option>
                <option value="processing">Processing</option>
                <option value="creating">Creating</option>
                <option value="error">Error</option>
              </select>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {filteredDatasets.map(dataset => (
                <div key={dataset.id} className="bg-gray-900 border border-gray-700 rounded-lg p-6">
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex items-start gap-3">
                      <div className="w-10 h-10 bg-blue-500 rounded-lg flex items-center justify-center">
                        <DatabaseIcon className="w-5 h-5 text-white" />
                      </div>
                      <div>
                        <h3 className="font-semibold text-white">{dataset.name}</h3>
                        <p className="text-sm text-gray-400 mt-1">{dataset.description}</p>
                        <div className="flex items-center gap-2 mt-2">
                          {getStatusIcon(dataset.status)}
                          <span className={`text-xs px-2 py-1 rounded ${getStatusColor(dataset.status)}`}>
                            {dataset.status.replace('_', ' ').toUpperCase()}
                          </span>
                          <span className="text-xs text-gray-500">v{dataset.version}</span>
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-1">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => setSelectedDataset(dataset)}
                        className="p-1"
                      >
                        <EyeIcon className="w-3 h-3" />
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => onDatasetSelect(dataset)}
                        className="p-1"
                      >
                        <PencilIcon className="w-3 h-3" />
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => deleteDataset(dataset.id)}
                        className="p-1 text-red-400 hover:text-red-300"
                      >
                        <TrashIcon className="w-3 h-3" />
                      </Button>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-4 mb-4">
                    <div className="bg-gray-800/50 rounded p-3">
                      <div className="text-sm text-gray-400">Records</div>
                      <div className="font-bold text-white">
                        {dataset.recordCount.toLocaleString()}
                      </div>
                    </div>
                    <div className="bg-gray-800/50 rounded p-3">
                      <div className="text-sm text-gray-400">Size</div>
                      <div className="font-bold text-white">
                        {formatFileSize(dataset.size)}
                      </div>
                    </div>
                  </div>

                  <div className="space-y-2">
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-gray-400">Source:</span>
                      <span className="text-white">{dataset.source.name}</span>
                    </div>
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-gray-400">Timeframe:</span>
                      <span className="text-white">{dataset.features.timeframe}</span>
                    </div>
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-gray-400">Symbols:</span>
                      <span className="text-white">{dataset.features.symbols.join(', ')}</span>
                    </div>
                  </div>

                  <div className="mt-4 pt-4 border-t border-gray-700">
                    <div className="flex flex-wrap gap-1">
                      {dataset.tags.map(tag => (
                        <span
                          key={tag}
                          className="text-xs px-2 py-1 bg-gray-700 text-gray-300 rounded-full"
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </TabsContent>

          <TabsContent value="sources" className="h-full mt-0">
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {dataSources.map(source => (
                <div key={source.id} className="bg-gray-900 border border-gray-700 rounded-lg p-6">
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 bg-purple-500 rounded-lg flex items-center justify-center">
                        <FolderIcon className="w-5 h-5 text-white" />
                      </div>
                      <div>
                        <h3 className="font-semibold text-white">{source.name}</h3>
                        <p className="text-sm text-gray-400">{source.type.replace('_', ' ')}</p>
                      </div>
                    </div>

                    {getStatusIcon(source.status)}
                  </div>

                  <div className="space-y-3">
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-gray-400">Status:</span>
                      <span className={`px-2 py-1 rounded text-xs ${getStatusColor(source.status)}`}>
                        {source.status.toUpperCase()}
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-gray-400">Records:</span>
                      <span className="text-white">{source.totalRecords.toLocaleString()}</span>
                    </div>
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-gray-400">Last Sync:</span>
                      <span className="text-white">
                        {new Date(source.lastSync).toLocaleDateString()}
                      </span>
                    </div>
                  </div>

                  <div className="mt-4 flex gap-2">
                    <Button size="sm" variant="outline" className="flex-1 gap-2">
                      <ArrowPathIcon className="w-3 h-3" />
                      Sync
                    </Button>
                    <Button size="sm" variant="outline" className="flex-1 gap-2">
                      <PencilIcon className="w-3 h-3" />
                      Config
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </TabsContent>

          <TabsContent value="pipelines" className="h-full mt-0">
            <div className="space-y-6">
              {pipelines.map(pipeline => (
                <div key={pipeline.id} className="bg-gray-900 border border-gray-700 rounded-lg p-6">
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex items-start gap-3">
                      <div className="w-10 h-10 bg-green-500 rounded-lg flex items-center justify-center">
                        <CpuChipIcon className="w-5 h-5 text-white" />
                      </div>
                      <div>
                        <h3 className="font-semibold text-white">{pipeline.name}</h3>
                        <p className="text-sm text-gray-400 mt-1">{pipeline.description}</p>
                        <div className="flex items-center gap-2 mt-2">
                          {getStatusIcon(pipeline.status)}
                          <span className={`text-xs px-2 py-1 rounded ${getStatusColor(pipeline.status)}`}>
                            {pipeline.status.toUpperCase()}
                          </span>
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      <Button
                        size="sm"
                        onClick={() => runPipeline(pipeline.id)}
                        disabled={pipeline.status === 'running'}
                        className="gap-2"
                      >
                        {pipeline.status === 'running' ? (
                          <StopIcon className="w-3 h-3" />
                        ) : (
                          <PlayIcon className="w-3 h-3" />
                        )}
                        {pipeline.status === 'running' ? 'Running...' : 'Run'}
                      </Button>
                    </div>
                  </div>

                  <div className="grid grid-cols-3 gap-4 mb-4">
                    <div className="bg-gray-800/50 rounded p-3">
                      <div className="text-sm text-gray-400">Datasets</div>
                      <div className="font-bold text-white">{pipeline.datasets.length}</div>
                    </div>
                    <div className="bg-gray-800/50 rounded p-3">
                      <div className="text-sm text-gray-400">Steps</div>
                      <div className="font-bold text-white">{pipeline.steps.length}</div>
                    </div>
                    <div className="bg-gray-800/50 rounded p-3">
                      <div className="text-sm text-gray-400">Schedule</div>
                      <div className="font-bold text-white">
                        {pipeline.schedule?.enabled ? 'Enabled' : 'Manual'}
                      </div>
                    </div>
                  </div>

                  {pipeline.schedule && (
                    <div className="space-y-2 text-sm">
                      <div className="flex items-center justify-between">
                        <span className="text-gray-400">Last Run:</span>
                        <span className="text-white">
                          {pipeline.lastRun ? new Date(pipeline.lastRun).toLocaleString() : 'Never'}
                        </span>
                      </div>
                      {pipeline.nextRun && (
                        <div className="flex items-center justify-between">
                          <span className="text-gray-400">Next Run:</span>
                          <span className="text-white">
                            {new Date(pipeline.nextRun).toLocaleString()}
                          </span>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </TabsContent>
        </div>
      </Tabs>

      {/* Dataset Detail Modal */}
      {selectedDataset && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-gray-900 border border-gray-700 rounded-lg p-6 max-w-4xl w-full max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-xl font-semibold text-white">{selectedDataset.name}</h3>
              <Button
                variant="outline"
                onClick={() => setSelectedDataset(null)}
              >
                Close
              </Button>
            </div>

            <div className="space-y-6">
              <div>
                <h4 className="text-lg font-medium text-white mb-3">Schema</h4>
                <div className="bg-gray-800/50 rounded-lg overflow-hidden">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-700/50">
                      <tr>
                        <th className="px-3 py-2 text-left text-gray-300">Column</th>
                        <th className="px-3 py-2 text-left text-gray-300">Type</th>
                        <th className="px-3 py-2 text-left text-gray-300">Nullable</th>
                      </tr>
                    </thead>
                    <tbody>
                      {selectedDataset.schema.columns.map((column, index) => (
                        <tr key={index} className="border-t border-gray-700">
                          <td className="px-3 py-2 text-white">{column.name}</td>
                          <td className="px-3 py-2 text-blue-400">{column.type}</td>
                          <td className="px-3 py-2 text-gray-300">
                            {column.nullable ? 'Yes' : 'No'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              <div>
                <h4 className="text-lg font-medium text-white mb-3">Preprocessing Steps</h4>
                <div className="space-y-3">
                  {selectedDataset.features.preprocessing.map((step, index) => (
                    <div key={step.id} className="bg-gray-800/50 rounded p-3">
                      <div className="flex items-center justify-between">
                        <div>
                          <div className="font-medium text-white">{step.name}</div>
                          <div className="text-sm text-gray-400">{step.type}</div>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="text-xs text-gray-500">Step {step.order}</span>
                          {step.enabled ? (
                            <CheckCircleIcon className="w-4 h-4 text-green-400" />
                          ) : (
                            <ExclamationTriangleIcon className="w-4 h-4 text-gray-400" />
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
