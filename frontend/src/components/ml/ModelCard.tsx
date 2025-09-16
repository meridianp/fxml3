/**
 * ML Model Card Component
 *
 * Displays ML model information with status, metrics, and actions
 */

'use client';

import { useState } from 'react';
import { formatRelativeTime, formatPercentage } from '@/lib/utils';
import { MLModel } from '@/stores/useMLStore';
import {
  PlayIcon,
  PauseIcon,
  StopIcon,
  ChartBarIcon,
  Cog6ToothIcon,
  TrashIcon,
  CloudArrowDownIcon,
  EyeIcon
} from '@heroicons/react/24/outline';

interface ModelCardProps {
  model: MLModel;
  onTrain?: (model: MLModel) => void;
  onStop?: (model: MLModel) => void;
  onDeploy?: (model: MLModel) => void;
  onDelete?: (model: MLModel) => void;
  onViewDetails?: (model: MLModel) => void;
  className?: string;
}

const getStatusColor = (status: string) => {
  switch (status) {
    case 'trained': return 'bg-green-500/20 text-green-400 border-green-500/30';
    case 'training': return 'bg-blue-500/20 text-blue-400 border-blue-500/30';
    case 'deployed': return 'bg-purple-500/20 text-purple-400 border-purple-500/30';
    case 'failed': return 'bg-red-500/20 text-red-400 border-red-500/30';
    case 'pending': return 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30';
    default: return 'bg-gray-500/20 text-gray-400 border-gray-500/30';
  }
};

const getModelTypeIcon = (type: string) => {
  switch (type) {
    case 'neural_network':
      return '🧠';
    case 'random_forest':
      return '🌳';
    case 'svm':
      return '📊';
    case 'xgboost':
      return '🚀';
    case 'lstm':
      return '🔄';
    case 'transformer':
      return '⚡';
    default:
      return '🤖';
  }
};

export default function ModelCard({
  model,
  onTrain,
  onStop,
  onDeploy,
  onDelete,
  onViewDetails,
  className = ''
}: ModelCardProps) {
  const [isActionLoading, setIsActionLoading] = useState<string | null>(null);

  const handleAction = async (action: string, callback?: () => void) => {
    setIsActionLoading(action);
    try {
      if (callback) {
        await callback();
      }
    } finally {
      setIsActionLoading(null);
    }
  };

  const canTrain = ['draft', 'failed', 'trained'].includes(model.status);
  const canStop = model.trainingStatus === 'training';
  const canDeploy = model.status === 'trained' && model.trainingStatus !== 'deployed';
  const isDeployed = model.trainingStatus === 'deployed';

  return (
    <div data-testid="model-card" className={`bg-gray-900 border border-gray-700 rounded-lg hover:border-gray-600 transition-colors ${className}`}>
      {/* Header */}
      <div className="p-4 border-b border-gray-800">
        <div className="flex items-start justify-between">
          <div className="flex items-start gap-3">
            <div className="text-2xl" title={`${model.type} model`}>
              {getModelTypeIcon(model.type)}
            </div>
            <div>
              <h3 data-testid="model-name" className="font-semibold text-white text-lg">{model.name}</h3>
              <p className="text-gray-400 text-sm mt-1">{model.name}</p>
              <div className="flex items-center gap-3 mt-2">
                <span data-testid="model-status" className={`px-2 py-1 text-xs font-medium rounded-full border ${getStatusColor(model.status)}`}>
                  {model.status.toUpperCase()}
                </span>
                <span className="text-xs text-gray-500">
                  {model.type.replace('_', ' ').toUpperCase()}
                </span>
                {isDeployed && (
                  <span className="px-2 py-1 text-xs font-medium rounded-full bg-purple-500/20 text-purple-400 border border-purple-500/30">
                    DEPLOYED
                  </span>
                )}
              </div>
            </div>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-2">
            {canTrain && (
              <button
                data-testid="train-button"
                onClick={() => handleAction('train', () => onTrain?.(model))}
                disabled={isActionLoading === 'train'}
                className="p-2 text-green-400 hover:bg-green-500/20 rounded-lg transition-colors disabled:opacity-50"
                title="Train Model"
              >
                {isActionLoading === 'train' ? (
                  <div className="w-4 h-4 border-2 border-green-400 border-t-transparent rounded-full animate-spin" />
                ) : (
                  <PlayIcon className="w-4 h-4" />
                )}
              </button>
            )}

            {canStop && (
              <button
                onClick={() => handleAction('stop', () => onStop?.(model))}
                disabled={isActionLoading === 'stop'}
                className="p-2 text-red-400 hover:bg-red-500/20 rounded-lg transition-colors disabled:opacity-50"
                title="Stop Training"
              >
                {isActionLoading === 'stop' ? (
                  <div className="w-4 h-4 border-2 border-red-400 border-t-transparent rounded-full animate-spin" />
                ) : (
                  <StopIcon className="w-4 h-4" />
                )}
              </button>
            )}

            {canDeploy && (
              <button
                data-testid="deploy-button"
                onClick={() => handleAction('deploy', () => onDeploy?.(model))}
                disabled={isActionLoading === 'deploy'}
                className="p-2 text-blue-400 hover:bg-blue-500/20 rounded-lg transition-colors disabled:opacity-50"
                title="Deploy Model"
              >
                {isActionLoading === 'deploy' ? (
                  <div className="w-4 h-4 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
                ) : (
                  <CloudArrowDownIcon className="w-4 h-4" />
                )}
              </button>
            )}

            <button
              onClick={() => onViewDetails?.(model)}
              className="p-2 text-gray-400 hover:bg-gray-700 rounded-lg transition-colors"
              title="View Details"
            >
              <EyeIcon className="w-4 h-4" />
            </button>

            <button
              onClick={() => handleAction('delete', () => onDelete?.(model))}
              disabled={isActionLoading === 'delete'}
              className="p-2 text-red-400 hover:bg-red-500/20 rounded-lg transition-colors disabled:opacity-50"
              title="Delete Model"
            >
              {isActionLoading === 'delete' ? (
                <div className="w-4 h-4 border-2 border-red-400 border-t-transparent rounded-full animate-spin" />
              ) : (
                <TrashIcon className="w-4 h-4" />
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Metrics */}
      <div className="p-4">
        <div className="grid grid-cols-2 gap-4 mb-4">
          <div>
            <div className="text-xs text-gray-500 mb-1">Accuracy</div>
            <div className="text-lg font-semibold text-white">
              {model.metrics?.accuracy ? formatPercentage(model.metrics.accuracy * 100) : '--'}
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-500 mb-1">Loss</div>
            <div className="text-lg font-semibold text-white">
              {model.metrics?.loss ? model.metrics.loss.toFixed(4) : '--'}
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-500 mb-1">Precision</div>
            <div className="text-lg font-semibold text-white">
              {model.metrics?.precision ? formatPercentage(model.metrics.precision * 100) : '--'}
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-500 mb-1">Recall</div>
            <div className="text-lg font-semibold text-white">
              {model.metrics?.recall ? formatPercentage(model.metrics.recall * 100) : '--'}
            </div>
          </div>
        </div>

        {/* Training Progress */}
        {model.trainingStatus === 'training' && model.versions?.[0]?.trainingProgress !== undefined && (
          <div className="mb-4">
            <div className="flex justify-between text-xs text-gray-400 mb-1">
              <span>Training Progress</span>
              <span>{Math.round(model.versions[0].trainingProgress * 100)}%</span>
            </div>
            <div className="w-full bg-gray-800 rounded-full h-2">
              <div
                data-testid="training-progress"
                className="bg-blue-500 h-2 rounded-full transition-all duration-300"
                style={{ width: `${model.versions[0].trainingProgress * 100}%` }}
              />
            </div>
          </div>
        )}

        {/* Additional Info */}
        <div className="text-xs text-gray-500 space-y-1">
          <div className="flex justify-between">
            <span>Created:</span>
            <span className="text-gray-300">{formatRelativeTime(model.createdAt)}</span>
          </div>
          <div className="flex justify-between">
            <span>Updated:</span>
            <span className="text-gray-300">{formatRelativeTime(model.updatedAt)}</span>
          </div>
          {model.versions?.length > 0 && (
            <div className="flex justify-between">
              <span>Version:</span>
              <span className="text-gray-300">v{model.versions[0].version}</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
