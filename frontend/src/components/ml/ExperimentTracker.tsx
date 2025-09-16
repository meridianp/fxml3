/**
 * Experiment Tracker Component
 *
 * Comprehensive ML experiment tracking with model comparison
 */

'use client';

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { useAppStore } from '@/stores/appStore';
import {
  BeakerIcon,
  ChartBarIcon,
  EyeIcon,
  PlayIcon,
  StopIcon,
  TrashIcon,
  ArrowPathIcon,
  TrophyIcon,
  ScaleIcon,
  ClockIcon,
  CpuChipIcon,
  DocumentTextIcon,
  TagIcon,
  ArrowTrendingUpIcon,
  ArrowTrendingDownIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  StarIcon
} from '@heroicons/react/24/outline';

interface Experiment {
  id: string;
  name: string;
  description: string;
  model_type: string;
  dataset_id: string;
  dataset_name: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  progress: number;
  hyperparameters: Record<string, any>;
  metrics: {
    train_accuracy: number;
    val_accuracy: number;
    test_accuracy: number;
    train_loss: number;
    val_loss: number;
    test_loss: number;
    sharpe_ratio?: number;
    max_drawdown?: number;
    total_return?: number;
    win_rate?: number;
  };
  training_history: Array<{
    epoch: number;
    train_loss: number;
    val_loss: number;
    train_accuracy: number;
    val_accuracy: number;
    learning_rate: number;
    duration: number;
  }>;
  artifacts: {
    model_path?: string;
    logs_path?: string;
    plots_path?: string;
    checkpoint_path?: string;
  };
  compute_stats: {
    gpu_hours: number;
    memory_peak: number;
    cpu_hours: number;
    estimated_cost: number;
  };
  created: string;
  started?: string;
  completed?: string;
  duration?: number;
  tags: string[];
  notes: string;
  starred: boolean;
}

interface ExperimentComparison {
  experiments: string[]; // experiment IDs
  metrics: string[];
  created: string;
}

interface ExperimentTrackerProps {
  onExperimentSelect: (experiment: Experiment) => void;
}

export default function ExperimentTracker({ onExperimentSelect }: ExperimentTrackerProps) {
  const [activeTab, setActiveTab] = useState('experiments');
  const [experiments, setExperiments] = useState<Experiment[]>([]);
  const [comparisons, setComparisons] = useState<ExperimentComparison[]>([]);
  const [selectedExperiment, setSelectedExperiment] = useState<Experiment | null>(null);
  const [selectedForComparison, setSelectedForComparison] = useState<Set<string>>(new Set());
  const [searchTerm, setSearchTerm] = useState('');
  const [filterStatus, setFilterStatus] = useState<string>('all');
  const [sortBy, setSortBy] = useState<'created' | 'accuracy' | 'loss' | 'duration'>('created');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');

  const { addNotification, addError } = useAppStore();

  useEffect(() => {
    loadExperiments();
    loadComparisons();
  }, []);

  const loadExperiments = () => {
    // Mock experiments data
    const mockExperiments: Experiment[] = [
      {
        id: 'exp_001',
        name: 'LSTM_EURUSD_Baseline',
        description: 'Baseline LSTM model for EURUSD prediction with standard features',
        model_type: 'LSTM',
        dataset_id: 'ds_001',
        dataset_name: 'EURUSD_H1_2023',
        status: 'completed',
        progress: 100,
        hyperparameters: {
          lstm_units: 50,
          dropout: 0.2,
          learning_rate: 0.001,
          batch_size: 32,
          epochs: 100,
          sequence_length: 60
        },
        metrics: {
          train_accuracy: 0.847,
          val_accuracy: 0.723,
          test_accuracy: 0.698,
          train_loss: 0.234,
          val_loss: 0.387,
          test_loss: 0.421,
          sharpe_ratio: 1.34,
          max_drawdown: 0.087,
          total_return: 0.156,
          win_rate: 0.61
        },
        training_history: generateTrainingHistory(100),
        artifacts: {
          model_path: '/models/exp_001/model.pkl',
          logs_path: '/logs/exp_001/training.log',
          plots_path: '/plots/exp_001/',
          checkpoint_path: '/checkpoints/exp_001/best_model.ckpt'
        },
        compute_stats: {
          gpu_hours: 2.3,
          memory_peak: 4.2,
          cpu_hours: 0.8,
          estimated_cost: 1.45
        },
        created: '2024-01-10T09:00:00Z',
        started: '2024-01-10T09:05:00Z',
        completed: '2024-01-10T11:18:00Z',
        duration: 8280, // seconds
        tags: ['lstm', 'baseline', 'eurusd', 'production'],
        notes: 'Baseline model showing good performance on validation set. Consider as production candidate.',
        starred: true
      },
      {
        id: 'exp_002',
        name: 'Transformer_MultiPair',
        description: 'Transformer architecture for multi-pair prediction with attention mechanism',
        model_type: 'Transformer',
        dataset_id: 'ds_002',
        dataset_name: 'Multi_Pair_Daily_ML',
        status: 'running',
        progress: 67,
        hyperparameters: {
          d_model: 256,
          nhead: 8,
          num_layers: 6,
          dropout: 0.1,
          learning_rate: 0.0001,
          batch_size: 64,
          epochs: 200,
          sequence_length: 120
        },
        metrics: {
          train_accuracy: 0.792,
          val_accuracy: 0.651,
          test_accuracy: 0,
          train_loss: 0.312,
          val_loss: 0.456,
          test_loss: 0,
          sharpe_ratio: 0.98,
          max_drawdown: 0.123,
          total_return: 0.089,
          win_rate: 0.58
        },
        training_history: generateTrainingHistory(134), // 67% of 200 epochs
        artifacts: {
          logs_path: '/logs/exp_002/training.log',
          checkpoint_path: '/checkpoints/exp_002/latest.ckpt'
        },
        compute_stats: {
          gpu_hours: 5.2,
          memory_peak: 8.7,
          cpu_hours: 1.3,
          estimated_cost: 3.89
        },
        created: '2024-01-12T14:30:00Z',
        started: '2024-01-12T14:35:00Z',
        duration: 0,
        tags: ['transformer', 'multi-pair', 'attention', 'experimental'],
        notes: 'Testing transformer architecture for improved pattern recognition across multiple currency pairs.',
        starred: false
      },
      {
        id: 'exp_003',
        name: 'XGBoost_Features_v2',
        description: 'XGBoost with extended feature engineering and hyperparameter optimization',
        model_type: 'XGBoost',
        dataset_id: 'ds_001',
        dataset_name: 'EURUSD_H1_2023',
        status: 'completed',
        progress: 100,
        hyperparameters: {
          n_estimators: 500,
          max_depth: 8,
          learning_rate: 0.05,
          subsample: 0.8,
          colsample_bytree: 0.9,
          min_child_weight: 3,
          reg_alpha: 0.1,
          reg_lambda: 0.2
        },
        metrics: {
          train_accuracy: 0.913,
          val_accuracy: 0.756,
          test_accuracy: 0.742,
          train_loss: 0.187,
          val_loss: 0.342,
          test_loss: 0.367,
          sharpe_ratio: 1.52,
          max_drawdown: 0.065,
          total_return: 0.203,
          win_rate: 0.68
        },
        training_history: generateTrainingHistory(500),
        artifacts: {
          model_path: '/models/exp_003/model.pkl',
          logs_path: '/logs/exp_003/training.log',
          plots_path: '/plots/exp_003/',
        },
        compute_stats: {
          gpu_hours: 0,
          memory_peak: 2.1,
          cpu_hours: 3.4,
          estimated_cost: 0.67
        },
        created: '2024-01-14T08:15:00Z',
        started: '2024-01-14T08:20:00Z',
        completed: '2024-01-14T11:44:00Z',
        duration: 12240,
        tags: ['xgboost', 'feature-engineering', 'optimized', 'champion'],
        notes: 'Best performing model so far. Excellent generalization with robust feature importance analysis.',
        starred: true
      },
      {
        id: 'exp_004',
        name: 'CNN_LSTM_Hybrid',
        description: 'Hybrid CNN-LSTM architecture for capturing both local patterns and temporal dependencies',
        model_type: 'CNN-LSTM',
        dataset_id: 'ds_001',
        dataset_name: 'EURUSD_H1_2023',
        status: 'failed',
        progress: 23,
        hyperparameters: {
          conv_filters: [32, 64, 128],
          kernel_size: 3,
          lstm_units: 100,
          dropout: 0.3,
          learning_rate: 0.002,
          batch_size: 16,
          epochs: 150
        },
        metrics: {
          train_accuracy: 0.623,
          val_accuracy: 0.534,
          test_accuracy: 0,
          train_loss: 0.734,
          val_loss: 0.823,
          test_loss: 0
        },
        training_history: generateTrainingHistory(35), // Failed at 23% progress
        artifacts: {
          logs_path: '/logs/exp_004/training.log',
          checkpoint_path: '/checkpoints/exp_004/last.ckpt'
        },
        compute_stats: {
          gpu_hours: 0.8,
          memory_peak: 6.3,
          cpu_hours: 0.2,
          estimated_cost: 0.95
        },
        created: '2024-01-13T16:00:00Z',
        started: '2024-01-13T16:05:00Z',
        duration: 0,
        tags: ['cnn-lstm', 'hybrid', 'failed', 'memory-issue'],
        notes: 'Failed due to memory issues. Need to reduce batch size or model complexity.',
        starred: false
      }
    ];

    setExperiments(mockExperiments);
  };

  const loadComparisons = () => {
    const mockComparisons: ExperimentComparison[] = [
      {
        experiments: ['exp_001', 'exp_003'],
        metrics: ['val_accuracy', 'sharpe_ratio', 'max_drawdown'],
        created: '2024-01-15T10:00:00Z'
      }
    ];

    setComparisons(mockComparisons);
  };

  function generateTrainingHistory(epochs: number) {
    const history = [];
    for (let i = 1; i <= epochs; i++) {
      // Simulate realistic training curves
      const progress = i / epochs;
      const trainLoss = 0.8 * Math.exp(-3 * progress) + 0.15 + Math.random() * 0.05;
      const valLoss = trainLoss + 0.1 + Math.random() * 0.1;
      const trainAcc = 1 - trainLoss + Math.random() * 0.02;
      const valAcc = trainAcc - 0.05 - Math.random() * 0.05;

      history.push({
        epoch: i,
        train_loss: trainLoss,
        val_loss: valLoss,
        train_accuracy: Math.max(0.5, Math.min(1, trainAcc)),
        val_accuracy: Math.max(0.4, Math.min(0.95, valAcc)),
        learning_rate: 0.001 * Math.pow(0.95, Math.floor(i / 20)),
        duration: 45 + Math.random() * 15
      });
    }
    return history;
  }

  const formatDuration = (seconds: number): string => {
    if (seconds === 0) return 'N/A';
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;

    if (hours > 0) return `${hours}h ${minutes}m ${secs}s`;
    if (minutes > 0) return `${minutes}m ${secs}s`;
    return `${secs}s`;
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircleIcon className="w-4 h-4 text-green-400" />;
      case 'running':
        return <ClockIcon className="w-4 h-4 text-yellow-400 animate-pulse" />;
      case 'failed':
      case 'cancelled':
        return <ExclamationTriangleIcon className="w-4 h-4 text-red-400" />;
      default:
        return <BeakerIcon className="w-4 h-4 text-gray-400" />;
    }
  };

  const getStatusColor = (status: string): string => {
    switch (status) {
      case 'completed':
        return 'text-green-400 bg-green-500/20';
      case 'running':
        return 'text-yellow-400 bg-yellow-500/20';
      case 'failed':
      case 'cancelled':
        return 'text-red-400 bg-red-500/20';
      default:
        return 'text-gray-400 bg-gray-500/20';
    }
  };

  const sortExperiments = (experiments: Experiment[]) => {
    return [...experiments].sort((a, b) => {
      let aVal, bVal;

      switch (sortBy) {
        case 'accuracy':
          aVal = a.metrics.val_accuracy;
          bVal = b.metrics.val_accuracy;
          break;
        case 'loss':
          aVal = a.metrics.val_loss;
          bVal = b.metrics.val_loss;
          break;
        case 'duration':
          aVal = a.duration || 0;
          bVal = b.duration || 0;
          break;
        default:
          aVal = new Date(a.created).getTime();
          bVal = new Date(b.created).getTime();
      }

      return sortOrder === 'desc' ? bVal - aVal : aVal - bVal;
    });
  };

  const filteredAndSortedExperiments = sortExperiments(
    experiments.filter(exp => {
      const matchesSearch = exp.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                           exp.description.toLowerCase().includes(searchTerm.toLowerCase()) ||
                           exp.tags.some(tag => tag.toLowerCase().includes(searchTerm.toLowerCase()));

      const matchesFilter = filterStatus === 'all' || exp.status === filterStatus;

      return matchesSearch && matchesFilter;
    })
  );

  const toggleExperimentComparison = (expId: string) => {
    const newSelected = new Set(selectedForComparison);
    if (newSelected.has(expId)) {
      newSelected.delete(expId);
    } else if (newSelected.size < 4) { // Limit to 4 experiments
      newSelected.add(expId);
    } else {
      addNotification({
        type: 'warning',
        title: 'Comparison Limit',
        message: 'Maximum 4 experiments can be compared at once'
      });
      return;
    }
    setSelectedForComparison(newSelected);
  };

  const createComparison = () => {
    if (selectedForComparison.size < 2) {
      addNotification({
        type: 'warning',
        title: 'Select Experiments',
        message: 'Please select at least 2 experiments to compare'
      });
      return;
    }

    const newComparison: ExperimentComparison = {
      experiments: Array.from(selectedForComparison),
      metrics: ['val_accuracy', 'val_loss', 'sharpe_ratio', 'max_drawdown'],
      created: new Date().toISOString()
    };

    setComparisons(prev => [newComparison, ...prev]);
    setSelectedForComparison(new Set());
    setActiveTab('comparison');

    addNotification({
      type: 'success',
      title: 'Comparison Created',
      message: `Created comparison of ${selectedForComparison.size} experiments`
    });
  };

  const toggleStarred = (expId: string) => {
    setExperiments(prev => prev.map(exp =>
      exp.id === expId ? { ...exp, starred: !exp.starred } : exp
    ));
  };

  const deleteExperiment = (expId: string) => {
    setExperiments(prev => prev.filter(exp => exp.id !== expId));
    addNotification({
      type: 'success',
      title: 'Experiment Deleted',
      message: 'Experiment has been successfully deleted'
    });
  };

  const cancelExperiment = (expId: string) => {
    setExperiments(prev => prev.map(exp =>
      exp.id === expId && exp.status === 'running'
        ? { ...exp, status: 'cancelled' as const }
        : exp
    ));

    addNotification({
      type: 'warning',
      title: 'Experiment Cancelled',
      message: 'Training has been cancelled'
    });
  };

  return (
    <div className="h-full">
      <Tabs value={activeTab} onValueChange={setActiveTab} className="h-full flex flex-col">
        <div className="p-6 border-b border-gray-700 bg-gray-900/50">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-xl font-semibold text-white">Experiment Tracking</h2>
              <p className="text-gray-400 text-sm mt-1">
                Track ML experiments, compare models, and analyze performance
              </p>
            </div>

            <div className="flex items-center gap-3">
              {selectedForComparison.size > 0 && (
                <Button
                  onClick={createComparison}
                  disabled={selectedForComparison.size < 2}
                  className="gap-2"
                >
                  <ScaleIcon className="w-4 h-4" />
                  Compare ({selectedForComparison.size})
                </Button>
              )}

              <Button className="gap-2">
                <PlayIcon className="w-4 h-4" />
                New Experiment
              </Button>
            </div>
          </div>

          <TabsList className="grid w-full grid-cols-3 bg-gray-800">
            <TabsTrigger value="experiments" className="gap-2">
              <BeakerIcon className="w-4 h-4" />
              Experiments
            </TabsTrigger>
            <TabsTrigger value="comparison" className="gap-2">
              <ScaleIcon className="w-4 h-4" />
              Comparison
            </TabsTrigger>
            <TabsTrigger value="analytics" className="gap-2">
              <ChartBarIcon className="w-4 h-4" />
              Analytics
            </TabsTrigger>
          </TabsList>
        </div>

        <div className="flex-1 p-6">
          <TabsContent value="experiments" className="h-full mt-0">
            <div className="mb-6 flex items-center gap-4">
              <div className="flex-1">
                <input
                  type="text"
                  placeholder="Search experiments..."
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
                <option value="completed">Completed</option>
                <option value="running">Running</option>
                <option value="failed">Failed</option>
                <option value="cancelled">Cancelled</option>
              </select>

              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value as any)}
                className="px-3 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white"
              >
                <option value="created">Created</option>
                <option value="accuracy">Accuracy</option>
                <option value="loss">Loss</option>
                <option value="duration">Duration</option>
              </select>

              <Button
                size="sm"
                variant="outline"
                onClick={() => setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')}
              >
                {sortOrder === 'desc' ? <ArrowTrendingDownIcon className="w-4 h-4" /> : <ArrowTrendingUpIcon className="w-4 h-4" />}
              </Button>
            </div>

            <div className="space-y-4">
              {filteredAndSortedExperiments.map(experiment => (
                <div
                  key={experiment.id}
                  className={`bg-gray-900 border rounded-lg p-6 transition-all ${
                    selectedForComparison.has(experiment.id)
                      ? 'border-blue-500 bg-blue-500/5'
                      : 'border-gray-700 hover:border-gray-600'
                  }`}
                >
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex items-start gap-4">
                      <input
                        type="checkbox"
                        checked={selectedForComparison.has(experiment.id)}
                        onChange={() => toggleExperimentComparison(experiment.id)}
                        className="mt-1 w-4 h-4 text-blue-500 bg-gray-800 border-gray-600 rounded focus:ring-blue-500"
                      />

                      <div className="flex-1">
                        <div className="flex items-center gap-3 mb-2">
                          <h3 className="font-semibold text-white">{experiment.name}</h3>
                          {experiment.starred && (
                            <StarIcon className="w-4 h-4 text-yellow-400 fill-current" />
                          )}
                          <span className="text-xs px-2 py-1 bg-gray-700 text-gray-300 rounded">
                            {experiment.model_type}
                          </span>
                          <span className={`text-xs px-2 py-1 rounded ${getStatusColor(experiment.status)}`}>
                            {experiment.status.toUpperCase()}
                          </span>
                        </div>

                        <p className="text-gray-400 text-sm mb-3">{experiment.description}</p>

                        <div className="flex flex-wrap gap-1 mb-3">
                          {experiment.tags.map(tag => (
                            <span
                              key={tag}
                              className="text-xs px-2 py-1 bg-gray-800 text-gray-300 rounded-full"
                            >
                              {tag}
                            </span>
                          ))}
                        </div>

                        {experiment.status === 'running' && (
                          <div className="mb-3">
                            <div className="flex justify-between text-sm text-gray-400 mb-1">
                              <span>Progress</span>
                              <span>{experiment.progress}%</span>
                            </div>
                            <div className="w-full bg-gray-700 rounded-full h-2">
                              <div
                                className="bg-yellow-500 h-2 rounded-full transition-all duration-300"
                                style={{ width: `${experiment.progress}%` }}
                              />
                            </div>
                          </div>
                        )}
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => toggleStarred(experiment.id)}
                        className="p-2"
                      >
                        <StarIcon className={`w-4 h-4 ${experiment.starred ? 'text-yellow-400 fill-current' : 'text-gray-400'}`} />
                      </Button>

                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => setSelectedExperiment(experiment)}
                        className="p-2"
                      >
                        <EyeIcon className="w-4 h-4" />
                      </Button>

                      {experiment.status === 'running' && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => cancelExperiment(experiment.id)}
                          className="p-2 text-red-400"
                        >
                          <StopIcon className="w-4 h-4" />
                        </Button>
                      )}

                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => deleteExperiment(experiment.id)}
                        className="p-2 text-red-400"
                      >
                        <TrashIcon className="w-4 h-4" />
                      </Button>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
                    <div className="bg-gray-800/50 rounded p-3 text-center">
                      <div className="text-lg font-bold text-green-400">
                        {(experiment.metrics.val_accuracy * 100).toFixed(1)}%
                      </div>
                      <div className="text-xs text-gray-400">Val Accuracy</div>
                    </div>

                    <div className="bg-gray-800/50 rounded p-3 text-center">
                      <div className="text-lg font-bold text-blue-400">
                        {experiment.metrics.val_loss.toFixed(3)}
                      </div>
                      <div className="text-xs text-gray-400">Val Loss</div>
                    </div>

                    {experiment.metrics.sharpe_ratio && (
                      <div className="bg-gray-800/50 rounded p-3 text-center">
                        <div className="text-lg font-bold text-purple-400">
                          {experiment.metrics.sharpe_ratio.toFixed(2)}
                        </div>
                        <div className="text-xs text-gray-400">Sharpe</div>
                      </div>
                    )}

                    <div className="bg-gray-800/50 rounded p-3 text-center">
                      <div className="text-lg font-bold text-orange-400">
                        {formatDuration(experiment.duration || 0)}
                      </div>
                      <div className="text-xs text-gray-400">Duration</div>
                    </div>

                    <div className="bg-gray-800/50 rounded p-3 text-center">
                      <div className="text-lg font-bold text-yellow-400">
                        ${experiment.compute_stats.estimated_cost.toFixed(2)}
                      </div>
                      <div className="text-xs text-gray-400">Cost</div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </TabsContent>

          <TabsContent value="comparison" className="h-full mt-0">
            {selectedForComparison.size > 1 || comparisons.length > 0 ? (
              <div className="space-y-6">
                {/* Current Comparison */}
                {selectedForComparison.size > 1 && (
                  <div className="bg-gray-900 border border-gray-700 rounded-lg p-6">
                    <h3 className="text-lg font-semibold text-white mb-4">
                      Current Comparison ({selectedForComparison.size} experiments)
                    </h3>

                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead className="bg-gray-800/50">
                          <tr>
                            <th className="px-3 py-2 text-left text-gray-300">Experiment</th>
                            <th className="px-3 py-2 text-left text-gray-300">Val Accuracy</th>
                            <th className="px-3 py-2 text-left text-gray-300">Val Loss</th>
                            <th className="px-3 py-2 text-left text-gray-300">Sharpe Ratio</th>
                            <th className="px-3 py-2 text-left text-gray-300">Max Drawdown</th>
                            <th className="px-3 py-2 text-left text-gray-300">Duration</th>
                            <th className="px-3 py-2 text-left text-gray-300">Cost</th>
                          </tr>
                        </thead>
                        <tbody>
                          {Array.from(selectedForComparison).map(expId => {
                            const exp = experiments.find(e => e.id === expId)!;
                            return (
                              <tr key={expId} className="border-t border-gray-700">
                                <td className="px-3 py-2">
                                  <div className="font-medium text-white">{exp.name}</div>
                                  <div className="text-xs text-gray-400">{exp.model_type}</div>
                                </td>
                                <td className="px-3 py-2 text-green-400 font-medium">
                                  {(exp.metrics.val_accuracy * 100).toFixed(1)}%
                                </td>
                                <td className="px-3 py-2 text-blue-400 font-medium">
                                  {exp.metrics.val_loss.toFixed(3)}
                                </td>
                                <td className="px-3 py-2 text-purple-400 font-medium">
                                  {exp.metrics.sharpe_ratio?.toFixed(2) || 'N/A'}
                                </td>
                                <td className="px-3 py-2 text-red-400 font-medium">
                                  {exp.metrics.max_drawdown ? (exp.metrics.max_drawdown * 100).toFixed(1) + '%' : 'N/A'}
                                </td>
                                <td className="px-3 py-2 text-gray-300">
                                  {formatDuration(exp.duration || 0)}
                                </td>
                                <td className="px-3 py-2 text-yellow-400">
                                  ${exp.compute_stats.estimated_cost.toFixed(2)}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                {/* Previous Comparisons */}
                {comparisons.map((comparison, index) => (
                  <div key={index} className="bg-gray-900 border border-gray-700 rounded-lg p-6">
                    <div className="flex items-center justify-between mb-4">
                      <h3 className="text-lg font-semibold text-white">
                        Comparison #{index + 1}
                      </h3>
                      <span className="text-sm text-gray-400">
                        {new Date(comparison.created).toLocaleDateString()}
                      </span>
                    </div>

                    <div className="text-sm text-gray-400 mb-4">
                      Comparing: {comparison.experiments.map(id =>
                        experiments.find(e => e.id === id)?.name || id
                      ).join(', ')}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-12">
                <ScaleIcon className="w-16 h-16 text-gray-400 mx-auto mb-4" />
                <h3 className="text-lg font-medium text-gray-300 mb-2">No Comparisons</h3>
                <p className="text-gray-400 mb-4">
                  Select experiments from the Experiments tab to compare their performance
                </p>
                <Button onClick={() => setActiveTab('experiments')} variant="outline">
                  Go to Experiments
                </Button>
              </div>
            )}
          </TabsContent>

          <TabsContent value="analytics" className="h-full mt-0">
            <div className="text-center py-12">
              <ChartBarIcon className="w-16 h-16 text-gray-400 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-300 mb-2">Analytics Dashboard</h3>
              <p className="text-gray-400">
                Advanced analytics and visualizations for experiment performance
              </p>
            </div>
          </TabsContent>
        </div>
      </Tabs>

      {/* Experiment Detail Modal */}
      {selectedExperiment && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-gray-900 border border-gray-700 rounded-lg max-w-6xl w-full max-h-[90vh] overflow-y-auto">
            <div className="p-6 border-b border-gray-700">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-xl font-semibold text-white">{selectedExperiment.name}</h3>
                  <p className="text-gray-400 mt-1">{selectedExperiment.description}</p>
                </div>
                <Button
                  variant="outline"
                  onClick={() => setSelectedExperiment(null)}
                >
                  Close
                </Button>
              </div>
            </div>

            <div className="p-6 space-y-6">
              {/* Metrics Overview */}
              <div>
                <h4 className="text-lg font-medium text-white mb-3">Performance Metrics</h4>
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                  {Object.entries(selectedExperiment.metrics).map(([key, value]) => (
                    <div key={key} className="bg-gray-800/50 rounded p-3">
                      <div className="text-sm text-gray-400 mb-1">
                        {key.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())}
                      </div>
                      <div className="font-bold text-white">
                        {typeof value === 'number' ?
                          (key.includes('accuracy') || key.includes('rate') ? (value * 100).toFixed(1) + '%' :
                           key.includes('return') || key.includes('drawdown') ? (value * 100).toFixed(1) + '%' :
                           value.toFixed(3)) :
                          String(value)}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Hyperparameters */}
              <div>
                <h4 className="text-lg font-medium text-white mb-3">Hyperparameters</h4>
                <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
                  {Object.entries(selectedExperiment.hyperparameters).map(([key, value]) => (
                    <div key={key} className="bg-gray-800/50 rounded p-3">
                      <div className="text-sm text-gray-400">{key}</div>
                      <div className="font-medium text-white">{String(value)}</div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Training History Chart Placeholder */}
              <div>
                <h4 className="text-lg font-medium text-white mb-3">Training History</h4>
                <div className="bg-gray-800/50 rounded-lg p-6 text-center">
                  <ChartBarIcon className="w-12 h-12 text-gray-400 mx-auto mb-3" />
                  <p className="text-gray-400">Training loss/accuracy curves would be displayed here</p>
                </div>
              </div>

              {/* Compute Stats */}
              <div>
                <h4 className="text-lg font-medium text-white mb-3">Compute Statistics</h4>
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                  <div className="bg-gray-800/50 rounded p-3">
                    <div className="text-sm text-gray-400">GPU Hours</div>
                    <div className="font-bold text-blue-400">{selectedExperiment.compute_stats.gpu_hours}</div>
                  </div>
                  <div className="bg-gray-800/50 rounded p-3">
                    <div className="text-sm text-gray-400">Peak Memory (GB)</div>
                    <div className="font-bold text-green-400">{selectedExperiment.compute_stats.memory_peak}</div>
                  </div>
                  <div className="bg-gray-800/50 rounded p-3">
                    <div className="text-sm text-gray-400">CPU Hours</div>
                    <div className="font-bold text-purple-400">{selectedExperiment.compute_stats.cpu_hours}</div>
                  </div>
                  <div className="bg-gray-800/50 rounded p-3">
                    <div className="text-sm text-gray-400">Estimated Cost</div>
                    <div className="font-bold text-yellow-400">${selectedExperiment.compute_stats.estimated_cost}</div>
                  </div>
                </div>
              </div>

              {/* Notes */}
              {selectedExperiment.notes && (
                <div>
                  <h4 className="text-lg font-medium text-white mb-3">Notes</h4>
                  <div className="bg-gray-800/50 rounded p-4">
                    <p className="text-gray-300">{selectedExperiment.notes}</p>
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
