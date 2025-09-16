import { create } from 'zustand';
import { devtools } from 'zustand/middleware';

export type ModelType = 'neural_network' | 'random_forest' | 'xgboost' | 'lstm' | 'svm';
export type ModelStatus = 'draft' | 'training' | 'trained' | 'deployed' | 'failed' | 'stopped';
export type TrainingStatus = 'idle' | 'preparing' | 'training' | 'validating' | 'completed' | 'failed' | 'stopped';

export interface ModelFeature {
  id: string;
  name: string;
  description: string;
  category: 'price_features' | 'technical_indicators' | 'volume_features' | 'sentiment_features' | 'macro_features';
  enabled: boolean;
}

export interface TrainingMetrics {
  accuracy: number;
  precision: number;
  recall: number;
  f1Score: number;
  loss: number;
  validationLoss: number;
  epoch: number;
  totalEpochs: number;
  trainingTime: number;
}

export interface ModelVersion {
  id: string;
  version: string;
  createdAt: Date;
  metrics: TrainingMetrics | null;
  hyperparameters: Record<string, any>;
  isActive: boolean;
}

export interface MLModel {
  id: string;
  name: string;
  description: string;
  type: ModelType;
  symbol: string;
  timeframe: string;
  status: ModelStatus;
  trainingStatus: TrainingStatus;
  features: string[];
  metrics: TrainingMetrics | null;
  versions: ModelVersion[];
  currentVersion: string;
  createdAt: Date;
  updatedAt: Date;
  trainingProgress: number;
  trainingLogs: string[];
  hyperparameters: Record<string, any>;
  deploymentConfig: Record<string, any>;
  lastTrainingError: string | null;
}

export interface TrainingJob {
  id: string;
  modelId: string;
  status: TrainingStatus;
  progress: number;
  startTime: Date;
  endTime?: Date;
  currentEpoch: number;
  totalEpochs: number;
  currentMetrics: Partial<TrainingMetrics>;
  logs: string[];
  error?: string;
}

export interface MLState {
  // Models
  models: MLModel[];
  selectedModel: MLModel | null;

  // Training
  trainingJobs: TrainingJob[];
  activeTrainingJob: TrainingJob | null;

  // Features
  availableFeatures: ModelFeature[];
  selectedFeatures: string[];

  // UI state
  activeTab: 'models' | 'training' | 'deployment' | 'experiments';
  showCreateModelDialog: boolean;
  showModelDetails: boolean;

  // Deployment
  deployedModels: MLModel[];

  // Loading states
  loadingModels: boolean;
  creatingModel: boolean;
  startingTraining: boolean;
  deployingModel: boolean;
}

interface MLActions {
  // Model management
  loadModels: () => Promise<void>;
  createModel: (modelData: any) => Promise<void>;
  trainModel: (modelId: string) => Promise<void>;
  deleteModel: (modelId: string) => Promise<void>;
  addModel: (model: MLModel) => void;
  updateModel: (modelId: string, updates: Partial<MLModel>) => void;
  removeModel: (modelId: string) => void;
  setSelectedModel: (model: MLModel | null) => void;

  // Training
  startTraining: (modelId: string, hyperparameters?: Record<string, any>) => void;
  stopTraining: (modelId: string) => void;
  updateTrainingProgress: (modelId: string, progress: number, metrics?: Partial<TrainingMetrics>) => void;
  addTrainingLog: (modelId: string, log: string) => void;
  completeTraining: (modelId: string, metrics: TrainingMetrics) => void;
  failTraining: (modelId: string, error: string) => void;

  // Training jobs
  addTrainingJob: (job: TrainingJob) => void;
  updateTrainingJob: (jobId: string, updates: Partial<TrainingJob>) => void;
  setActiveTrainingJob: (job: TrainingJob | null) => void;

  // Features
  setAvailableFeatures: (features: ModelFeature[]) => void;
  setSelectedFeatures: (features: string[]) => void;
  toggleFeature: (featureId: string) => void;

  // Deployment
  deployModel: (modelId: string, config?: Record<string, any>) => void;
  undeployModel: (modelId: string) => void;
  updateDeployedModels: (models: MLModel[]) => void;

  // Version management
  createModelVersion: (modelId: string, metrics: TrainingMetrics, hyperparameters: Record<string, any>) => void;
  setActiveVersion: (modelId: string, versionId: string) => void;

  // UI actions
  setActiveTab: (tab: MLState['activeTab']) => void;
  setShowCreateModelDialog: (show: boolean) => void;
  setShowModelDetails: (show: boolean) => void;

  // Loading actions
  setLoadingModels: (loading: boolean) => void;
  setCreatingModel: (creating: boolean) => void;
  setStartingTraining: (starting: boolean) => void;
  setDeployingModel: (deploying: boolean) => void;

  // Utilities
  getModel: (modelId: string) => MLModel | undefined;
  getModelsByStatus: (status: ModelStatus) => MLModel[];
  getActiveTrainingJobs: () => TrainingJob[];
  getModelMetrics: (modelId: string) => TrainingMetrics | null;

  // Reset
  reset: () => void;
}

const defaultFeatures: ModelFeature[] = [
  {
    id: 'price_features',
    name: 'Price Features',
    description: 'OHLC price data and price-based indicators',
    category: 'price_features',
    enabled: true,
  },
  {
    id: 'technical_indicators',
    name: 'Technical Indicators',
    description: 'RSI, MACD, Moving averages, etc.',
    category: 'technical_indicators',
    enabled: true,
  },
  {
    id: 'volume_features',
    name: 'Volume Features',
    description: 'Volume-based indicators and patterns',
    category: 'volume_features',
    enabled: false,
  },
  {
    id: 'sentiment_features',
    name: 'Sentiment Features',
    description: 'Market sentiment and news analysis',
    category: 'sentiment_features',
    enabled: false,
  },
  {
    id: 'macro_features',
    name: 'Macro Features',
    description: 'Economic indicators and macro data',
    category: 'macro_features',
    enabled: false,
  },
];

const initialState: MLState = {
  models: [],
  selectedModel: null,
  trainingJobs: [],
  activeTrainingJob: null,
  availableFeatures: defaultFeatures,
  selectedFeatures: ['price_features', 'technical_indicators'],
  activeTab: 'models',
  showCreateModelDialog: false,
  showModelDetails: false,
  deployedModels: [],
  loadingModels: false,
  creatingModel: false,
  startingTraining: false,
  deployingModel: false,
};

export const useMLStore = create<MLState & MLActions>()(
  devtools(
    (set, get) => ({
      ...initialState,

      // API functions
      loadModels: async () => {
        set({ loadingModels: true }, false, 'loadModels:start');
        try {
          // For now, return empty array until API is working
          // TODO: Replace with actual API call when backend is fixed
          set({ models: [], loadingModels: false }, false, 'loadModels:success');
        } catch (error) {
          console.error('Failed to load models:', error);
          set({ loadingModels: false }, false, 'loadModels:error');
        }
      },

      createModel: async (modelData) => {
        set({ creatingModel: true }, false, 'createModel:start');
        try {
          // Create a mock model until API is working
          const mockModel: MLModel = {
            id: `model-${Date.now()}`,
            name: modelData.name || 'Untitled Model',
            description: modelData.description || '',
            type: modelData.type || 'neural_network',
            symbol: modelData.symbol || 'EURUSD',
            timeframe: modelData.timeframe || '1h',
            status: 'draft',
            trainingStatus: 'idle',
            features: modelData.features || [],
            metrics: null,
            versions: [],
            currentVersion: '',
            createdAt: new Date(),
            updatedAt: new Date(),
            trainingProgress: 0,
            trainingLogs: [],
            hyperparameters: modelData.hyperparameters || {},
            deploymentConfig: {},
            lastTrainingError: null,
          };

          get().addModel(mockModel);
          set({ creatingModel: false }, false, 'createModel:success');
        } catch (error) {
          console.error('Failed to create model:', error);
          set({ creatingModel: false }, false, 'createModel:error');
          throw error;
        }
      },

      trainModel: async (modelId: string) => {
        get().startTraining(modelId);
      },

      deleteModel: async (modelId: string) => {
        get().removeModel(modelId);
      },

      // Model management
      addModel: (model) => {
        set(
          (state) => ({ models: [...state.models, model] }),
          false,
          'addModel'
        );
      },

      updateModel: (modelId, updates) => {
        set(
          (state) => ({
            models: state.models.map((model) =>
              model.id === modelId
                ? { ...model, ...updates, updatedAt: new Date() }
                : model
            ),
            selectedModel:
              state.selectedModel?.id === modelId
                ? { ...state.selectedModel, ...updates, updatedAt: new Date() }
                : state.selectedModel,
          }),
          false,
          'updateModel'
        );
      },

      removeModel: (modelId) => {
        set(
          (state) => ({
            models: state.models.filter((model) => model.id !== modelId),
            selectedModel: state.selectedModel?.id === modelId ? null : state.selectedModel,
            deployedModels: state.deployedModels.filter((model) => model.id !== modelId),
          }),
          false,
          'removeModel'
        );
      },

      setSelectedModel: (model) => {
        set({ selectedModel: model }, false, 'setSelectedModel');
      },

      // Training
      startTraining: (modelId, hyperparameters = {}) => {
        const trainingJob: TrainingJob = {
          id: `job-${Date.now()}`,
          modelId,
          status: 'preparing',
          progress: 0,
          startTime: new Date(),
          currentEpoch: 0,
          totalEpochs: hyperparameters.epochs || 100,
          currentMetrics: {},
          logs: ['Training started...'],
        };

        set(
          (state) => ({
            models: state.models.map((model) =>
              model.id === modelId
                ? {
                    ...model,
                    status: 'training' as ModelStatus,
                    trainingStatus: 'preparing' as TrainingStatus,
                    trainingProgress: 0,
                    hyperparameters,
                    lastTrainingError: null,
                  }
                : model
            ),
            trainingJobs: [...state.trainingJobs, trainingJob],
            activeTrainingJob: trainingJob,
          }),
          false,
          'startTraining'
        );
      },

      stopTraining: (modelId) => {
        set(
          (state) => ({
            models: state.models.map((model) =>
              model.id === modelId
                ? {
                    ...model,
                    trainingStatus: 'stopped' as TrainingStatus,
                    status: 'stopped' as ModelStatus,
                  }
                : model
            ),
            trainingJobs: state.trainingJobs.map((job) =>
              job.modelId === modelId
                ? { ...job, status: 'stopped' as TrainingStatus, endTime: new Date() }
                : job
            ),
            activeTrainingJob:
              state.activeTrainingJob?.modelId === modelId ? null : state.activeTrainingJob,
          }),
          false,
          'stopTraining'
        );
      },

      updateTrainingProgress: (modelId, progress, metrics = {}) => {
        set(
          (state) => ({
            models: state.models.map((model) =>
              model.id === modelId
                ? {
                    ...model,
                    trainingProgress: progress,
                    trainingStatus: 'training' as TrainingStatus,
                    metrics: metrics.accuracy !== undefined ? { ...model.metrics, ...metrics } as TrainingMetrics : model.metrics,
                  }
                : model
            ),
            trainingJobs: state.trainingJobs.map((job) =>
              job.modelId === modelId
                ? {
                    ...job,
                    progress,
                    currentMetrics: { ...job.currentMetrics, ...metrics },
                    status: 'training' as TrainingStatus,
                  }
                : job
            ),
          }),
          false,
          'updateTrainingProgress'
        );
      },

      addTrainingLog: (modelId, log) => {
        set(
          (state) => ({
            models: state.models.map((model) =>
              model.id === modelId
                ? { ...model, trainingLogs: [...model.trainingLogs, log] }
                : model
            ),
            trainingJobs: state.trainingJobs.map((job) =>
              job.modelId === modelId
                ? { ...job, logs: [...job.logs, log] }
                : job
            ),
          }),
          false,
          'addTrainingLog'
        );
      },

      completeTraining: (modelId, metrics) => {
        const timestamp = new Date();
        set(
          (state) => ({
            models: state.models.map((model) =>
              model.id === modelId
                ? {
                    ...model,
                    status: 'trained' as ModelStatus,
                    trainingStatus: 'completed' as TrainingStatus,
                    metrics,
                    trainingProgress: 100,
                    updatedAt: timestamp,
                  }
                : model
            ),
            trainingJobs: state.trainingJobs.map((job) =>
              job.modelId === modelId
                ? {
                    ...job,
                    status: 'completed' as TrainingStatus,
                    progress: 100,
                    endTime: timestamp,
                    currentMetrics: metrics,
                  }
                : job
            ),
            activeTrainingJob:
              state.activeTrainingJob?.modelId === modelId ? null : state.activeTrainingJob,
          }),
          false,
          'completeTraining'
        );
      },

      failTraining: (modelId, error) => {
        set(
          (state) => ({
            models: state.models.map((model) =>
              model.id === modelId
                ? {
                    ...model,
                    status: 'failed' as ModelStatus,
                    trainingStatus: 'failed' as TrainingStatus,
                    lastTrainingError: error,
                  }
                : model
            ),
            trainingJobs: state.trainingJobs.map((job) =>
              job.modelId === modelId
                ? {
                    ...job,
                    status: 'failed' as TrainingStatus,
                    endTime: new Date(),
                    error,
                  }
                : job
            ),
            activeTrainingJob:
              state.activeTrainingJob?.modelId === modelId ? null : state.activeTrainingJob,
          }),
          false,
          'failTraining'
        );
      },

      // Training jobs
      addTrainingJob: (job) => {
        set(
          (state) => ({ trainingJobs: [...state.trainingJobs, job] }),
          false,
          'addTrainingJob'
        );
      },

      updateTrainingJob: (jobId, updates) => {
        set(
          (state) => ({
            trainingJobs: state.trainingJobs.map((job) =>
              job.id === jobId ? { ...job, ...updates } : job
            ),
          }),
          false,
          'updateTrainingJob'
        );
      },

      setActiveTrainingJob: (job) => {
        set({ activeTrainingJob: job }, false, 'setActiveTrainingJob');
      },

      // Features
      setAvailableFeatures: (features) => {
        set({ availableFeatures: features }, false, 'setAvailableFeatures');
      },

      setSelectedFeatures: (features) => {
        set({ selectedFeatures: features }, false, 'setSelectedFeatures');
      },

      toggleFeature: (featureId) => {
        set(
          (state) => ({
            selectedFeatures: state.selectedFeatures.includes(featureId)
              ? state.selectedFeatures.filter((f) => f !== featureId)
              : [...state.selectedFeatures, featureId],
          }),
          false,
          'toggleFeature'
        );
      },

      // Deployment
      deployModel: (modelId, config = {}) => {
        set(
          (state) => {
            const model = state.models.find((m) => m.id === modelId);
            if (!model) return state;

            const deployedModel = {
              ...model,
              status: 'deployed' as ModelStatus,
              deploymentConfig: config,
            };

            return {
              models: state.models.map((m) =>
                m.id === modelId ? deployedModel : m
              ),
              deployedModels: state.deployedModels.some((dm) => dm.id === modelId)
                ? state.deployedModels.map((dm) =>
                    dm.id === modelId ? deployedModel : dm
                  )
                : [...state.deployedModels, deployedModel],
            };
          },
          false,
          'deployModel'
        );
      },

      undeployModel: (modelId) => {
        set(
          (state) => ({
            models: state.models.map((model) =>
              model.id === modelId
                ? { ...model, status: 'trained' as ModelStatus }
                : model
            ),
            deployedModels: state.deployedModels.filter((model) => model.id !== modelId),
          }),
          false,
          'undeployModel'
        );
      },

      updateDeployedModels: (models) => {
        set({ deployedModels: models }, false, 'updateDeployedModels');
      },

      // Version management
      createModelVersion: (modelId, metrics, hyperparameters) => {
        set(
          (state) => {
            const model = state.models.find((m) => m.id === modelId);
            if (!model) return state;

            const newVersion: ModelVersion = {
              id: `v${Date.now()}`,
              version: `v${model.versions.length + 1}.0`,
              createdAt: new Date(),
              metrics,
              hyperparameters,
              isActive: true,
            };

            return {
              models: state.models.map((m) =>
                m.id === modelId
                  ? {
                      ...m,
                      versions: m.versions.map((v) => ({ ...v, isActive: false })).concat([newVersion]),
                      currentVersion: newVersion.id,
                    }
                  : m
              ),
            };
          },
          false,
          'createModelVersion'
        );
      },

      setActiveVersion: (modelId, versionId) => {
        set(
          (state) => ({
            models: state.models.map((model) =>
              model.id === modelId
                ? {
                    ...model,
                    currentVersion: versionId,
                    versions: model.versions.map((v) => ({
                      ...v,
                      isActive: v.id === versionId,
                    })),
                  }
                : model
            ),
          }),
          false,
          'setActiveVersion'
        );
      },

      // UI actions
      setActiveTab: (tab) => {
        set({ activeTab: tab }, false, 'setActiveTab');
      },

      setShowCreateModelDialog: (show) => {
        set({ showCreateModelDialog: show }, false, 'setShowCreateModelDialog');
      },

      setShowModelDetails: (show) => {
        set({ showModelDetails: show }, false, 'setShowModelDetails');
      },

      // Loading actions
      setLoadingModels: (loading) => {
        set({ loadingModels: loading }, false, 'setLoadingModels');
      },

      setCreatingModel: (creating) => {
        set({ creatingModel: creating }, false, 'setCreatingModel');
      },

      setStartingTraining: (starting) => {
        set({ startingTraining: starting }, false, 'setStartingTraining');
      },

      setDeployingModel: (deploying) => {
        set({ deployingModel: deploying }, false, 'setDeployingModel');
      },

      // Utilities
      getModel: (modelId) => {
        return get().models.find((model) => model.id === modelId);
      },

      getModelsByStatus: (status) => {
        return get().models.filter((model) => model.status === status);
      },

      getActiveTrainingJobs: () => {
        return get().trainingJobs.filter((job) =>
          ['preparing', 'training', 'validating'].includes(job.status)
        );
      },

      getModelMetrics: (modelId) => {
        const model = get().models.find((m) => m.id === modelId);
        return model?.metrics || null;
      },

      // Reset
      reset: () => {
        set(initialState, false, 'reset');
      },
    }),
    {
      name: 'ml-store',
    }
  )
);
