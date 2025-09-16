/**
 * ML Training Studio Component
 *
 * Main interface for managing ML models, training, and experiments
 */

'use client';

import { useState, useEffect } from 'react';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import ModelCard from './ModelCard';
import { SymbolSelector } from '@/components/data';
import { useMLStore } from '@/stores/useMLStore';
import { useAppStore } from '@/stores/useAppStore';
import { apiClient } from '@/services/api';
import {
  PlusIcon,
  RocketLaunchIcon,
  BeakerIcon,
  ChartBarSquareIcon,
  Cog6ToothIcon,
  CloudArrowDownIcon,
  DocumentChartBarIcon
} from '@heroicons/react/24/outline';

interface CreateModelForm {
  name: string;
  type: string;
  features: string[];
  hyperparameters: Record<string, any>;
}

const MODEL_TYPES = [
  { value: 'neural_network', label: 'Neural Network', description: 'Deep learning model for complex patterns' },
  { value: 'random_forest', label: 'Random Forest', description: 'Ensemble method with high accuracy' },
  { value: 'xgboost', label: 'XGBoost', description: 'Gradient boosting for structured data' },
  { value: 'svm', label: 'SVM', description: 'Support Vector Machine for classification' },
  { value: 'lstm', label: 'LSTM', description: 'Recurrent network for time series' },
  { value: 'transformer', label: 'Transformer', description: 'Attention-based architecture' },
];

const DEFAULT_FEATURES = [
  'price_features',
  'technical_indicators',
  'volume_features',
  'volatility_features',
  'session_features',
  'sentiment_features',
];

export default function TrainingStudio() {
  const [activeTab, setActiveTab] = useState('models');
  const [loading, setLoading] = useState(false);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [createForm, setCreateForm] = useState<CreateModelForm>({
    name: '',
    type: 'neural_network',
    features: DEFAULT_FEATURES,
    hyperparameters: {}
  });

  const {
    models,
    createModel,
    trainModel,
    stopTraining,
    deployModel,
    deleteModel,
    loadModels
  } = useMLStore();

  const { addNotification, setError } = useAppStore();

  // Load models on mount
  useEffect(() => {
    loadModels();
  }, [loadModels]);

  const handleCreateModel = async () => {
    try {
      setLoading(true);
      await createModel(createForm);

      setShowCreateForm(false);
      setCreateForm({
        name: '',
        type: 'neural_network',
        features: DEFAULT_FEATURES,
        hyperparameters: {}
      });

      addNotification({
        type: 'success',
        title: 'Model Created',
        message: `Model "${createForm.name}" created successfully`
      });
    } catch (error) {
      console.error('Failed to create model:', error);
      setError({
        code: 'CREATE_MODEL_ERROR',
        message: 'Failed to create ML model',
        timestamp: new Date().toISOString()
      });
    } finally {
      setLoading(false);
    }
  };

  const handleTrainModel = async (model: any) => {
    try {
      setLoading(true);
      await trainModel(model.id);

      addNotification({
        type: 'success',
        title: 'Training Started',
        message: `Training started for model "${model.name}"`
      });
    } catch (error) {
      console.error('Failed to start training:', error);
      setError({
        code: 'TRAINING_ERROR',
        message: 'Failed to start model training',
        timestamp: new Date().toISOString()
      });
    } finally {
      setLoading(false);
    }
  };

  const handleStopTraining = async (model: any) => {
    try {
      await stopTraining(model.id);

      addNotification({
        type: 'info',
        title: 'Training Stopped',
        message: `Training stopped for model "${model.name}"`
      });
    } catch (error) {
      console.error('Failed to stop training:', error);
    }
  };

  const handleDeployModel = async (model: any) => {
    try {
      await deployModel(model.id);

      addNotification({
        type: 'success',
        title: 'Model Deployed',
        message: `Model "${model.name}" deployed successfully`
      });
    } catch (error) {
      console.error('Failed to deploy model:', error);
    }
  };

  const handleDeleteModel = async (model: any) => {
    if (!confirm(`Are you sure you want to delete "${model.name}"?`)) {
      return;
    }

    try {
      await deleteModel(model.id);

      addNotification({
        type: 'success',
        title: 'Model Deleted',
        message: `Model "${model.name}" deleted successfully`
      });
    } catch (error) {
      console.error('Failed to delete model:', error);
    }
  };

  const getModelStats = () => {
    const total = models.length;
    const trained = models.filter(m => m.status === 'trained').length;
    const training = models.filter(m => m.trainingStatus === 'training').length;
    const deployed = models.filter(m => m.trainingStatus === 'deployed').length;

    return { total, trained, training, deployed };
  };

  const stats = getModelStats();

  return (
    <div data-testid="training-studio" className="h-full flex flex-col">
      {/* Header */}
      <div className="p-6 border-b border-gray-700 bg-gray-900/50">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-2xl font-bold text-white">ML Training Studio</h1>
            <p className="text-gray-400">Train and manage machine learning models</p>
          </div>

          <div className="flex items-center gap-3">
            <Button
              data-testid="create-model-button"
              onClick={() => setShowCreateForm(true)}
              className="gap-2"
            >
              <PlusIcon className="w-4 h-4" />
              Create Model
            </Button>
          </div>
        </div>

        {/* Quick Stats */}
        <div className="grid grid-cols-4 gap-4">
          <div className="bg-gray-800/50 rounded-lg p-3">
            <div data-testid="total-models-count" className="text-2xl font-bold text-white">{stats.total}</div>
            <div className="text-sm text-gray-400">Total Models</div>
          </div>
          <div className="bg-gray-800/50 rounded-lg p-3">
            <div className="text-2xl font-bold text-green-400">{stats.trained}</div>
            <div className="text-sm text-gray-400">Trained</div>
          </div>
          <div className="bg-gray-800/50 rounded-lg p-3">
            <div className="text-2xl font-bold text-blue-400">{stats.training}</div>
            <div className="text-sm text-gray-400">Training</div>
          </div>
          <div className="bg-gray-800/50 rounded-lg p-3">
            <div className="text-2xl font-bold text-purple-400">{stats.deployed}</div>
            <div className="text-sm text-gray-400">Deployed</div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 p-6">
        <Tabs value={activeTab} onValueChange={setActiveTab} className="h-full flex flex-col">
          <TabsList className="grid w-full grid-cols-4 bg-gray-800">
            <TabsTrigger value="models" className="gap-2">
              <RocketLaunchIcon className="w-4 h-4" />
              Models
            </TabsTrigger>
            <TabsTrigger value="datasets" className="gap-2">
              <DocumentChartBarIcon className="w-4 h-4" />
              Datasets
            </TabsTrigger>
            <TabsTrigger value="experiments" className="gap-2">
              <BeakerIcon className="w-4 h-4" />
              Experiments
            </TabsTrigger>
            <TabsTrigger value="deployment" className="gap-2">
              <CloudArrowDownIcon className="w-4 h-4" />
              Deployment
            </TabsTrigger>
          </TabsList>

          <div className="flex-1 mt-6">
            <TabsContent value="models" className="h-full">
              {loading && models.length === 0 ? (
                <div className="flex items-center justify-center h-full">
                  <div className="flex items-center gap-2 text-gray-400">
                    <div className="w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
                    Loading models...
                  </div>
                </div>
              ) : models.length === 0 ? (
                <div className="flex items-center justify-center h-full">
                  <div className="text-center">
                    <RocketLaunchIcon className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                    <h3 className="text-lg font-semibold text-white mb-2">No Models Yet</h3>
                    <p className="text-gray-400 mb-4">Create your first ML model to get started</p>
                    <Button onClick={() => setShowCreateForm(true)} className="gap-2">
                      <PlusIcon className="w-4 h-4" />
                      Create Your First Model
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                  {models.map((model) => (
                    <ModelCard
                      key={model.id}
                      model={model}
                      onTrain={handleTrainModel}
                      onStop={handleStopTraining}
                      onDeploy={handleDeployModel}
                      onDelete={handleDeleteModel}
                      onViewDetails={(model) => console.log('View details:', model)}
                    />
                  ))}
                </div>
              )}
            </TabsContent>

            <TabsContent value="datasets" className="h-full">
              <div className="bg-gray-900 border border-gray-700 rounded-lg p-6 text-center">
                <DocumentChartBarIcon className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                <h3 className="text-lg font-semibold text-white mb-2">Training Datasets</h3>
                <p className="text-gray-400 mb-4">
                  Manage and prepare datasets for model training
                </p>
                <Button className="gap-2">
                  <PlusIcon className="w-4 h-4" />
                  Create Dataset
                </Button>
              </div>
            </TabsContent>

            <TabsContent value="experiments" className="h-full">
              <div className="bg-gray-900 border border-gray-700 rounded-lg p-6 text-center">
                <BeakerIcon className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                <h3 className="text-lg font-semibold text-white mb-2">Experiments</h3>
                <p className="text-gray-400 mb-4">
                  Track and compare model training experiments
                </p>
                <Button className="gap-2">
                  <PlusIcon className="w-4 h-4" />
                  Start Experiment
                </Button>
              </div>
            </TabsContent>

            <TabsContent value="deployment" className="h-full">
              <div className="bg-gray-900 border border-gray-700 rounded-lg p-6 text-center">
                <CloudArrowDownIcon className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                <h3 className="text-lg font-semibold text-white mb-2">Model Deployment</h3>
                <p className="text-gray-400 mb-4">
                  Deploy trained models for live trading signals
                </p>
                <Button className="gap-2">
                  <CloudArrowDownIcon className="w-4 h-4" />
                  View Deployments
                </Button>
              </div>
            </TabsContent>
          </div>
        </Tabs>
      </div>

      {/* Create Model Modal */}
      {showCreateForm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-gray-900 border border-gray-700 rounded-lg w-full max-w-2xl max-h-[90vh] overflow-y-auto">
            <div className="p-6 border-b border-gray-700">
              <h2 className="text-xl font-semibold text-white">Create New Model</h2>
              <p className="text-gray-400 text-sm mt-1">Configure your machine learning model</p>
            </div>

            <div className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">Model Name</label>
                <input
                  data-testid="model-name-input"
                  type="text"
                  value={createForm.name}
                  onChange={(e) => setCreateForm(prev => ({ ...prev, name: e.target.value }))}
                  className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                  placeholder="e.g., EURUSD Trend Predictor"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">Model Type</label>
                <select
                  data-testid="model-type-select"
                  value={createForm.type}
                  onChange={(e) => setCreateForm(prev => ({ ...prev, type: e.target.value }))}
                  className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                >
                  {MODEL_TYPES.map((type) => (
                    <option key={type.value} value={type.value}>
                      {type.label}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">Features</label>
                <div className="grid grid-cols-2 gap-2">
                  {DEFAULT_FEATURES.map((feature) => (
                    <label key={feature} className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={createForm.features.includes(feature)}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setCreateForm(prev => ({
                              ...prev,
                              features: [...prev.features, feature]
                            }));
                          } else {
                            setCreateForm(prev => ({
                              ...prev,
                              features: prev.features.filter(f => f !== feature)
                            }));
                          }
                        }}
                        className="rounded border-gray-600 bg-gray-800 text-blue-500 focus:ring-blue-500"
                      />
                      <span className="text-sm text-gray-300">
                        {feature.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())}
                      </span>
                    </label>
                  ))}
                </div>
              </div>
            </div>

            <div className="p-6 border-t border-gray-700 flex justify-end gap-3">
              <Button
                variant="ghost"
                onClick={() => setShowCreateForm(false)}
              >
                Cancel
              </Button>
              <Button
                data-testid="submit-create-model"
                onClick={handleCreateModel}
                disabled={!createForm.name || loading}
                className="gap-2"
              >
                {loading ? (
                  <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                ) : (
                  <PlusIcon className="w-4 h-4" />
                )}
                Create Model
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
