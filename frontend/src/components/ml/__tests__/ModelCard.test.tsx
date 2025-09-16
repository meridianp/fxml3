/**
 * ModelCard Component Tests
 *
 * Tests for ML model display and management functionality
 */

import React from 'react';
import { screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { render, mockApiSuccess, mockApiError } from '@/test-utils/render';
import ModelCard from '../ModelCard';
import type { MLModel } from '@/types';

// Mock utils
jest.mock('@/lib/utils', () => ({
  formatRelativeTime: jest.fn((date) => '2 hours ago'),
  formatPercentage: jest.fn((value) => `${value.toFixed(1)}%`),
}));

describe('ModelCard', () => {
  const user = userEvent.setup();

  const mockModel: MLModel = {
    id: 'model-123',
    name: 'EURUSD Trend Predictor',
    description: 'Neural network for trend prediction',
    model_type: 'neural_network',
    symbol: 'EURUSD',
    timeframe: '1h',
    status: 'trained',
    is_deployed: false,
    created_at: '2024-01-15T10:00:00.000Z',
    last_trained: '2024-01-15T12:00:00.000Z',
    version: '1.0.0',
    metrics: {
      accuracy: 0.85,
      loss: 0.0234,
      precision: 0.82,
      recall: 0.89,
    },
    hyperparameters: {
      learning_rate: 0.001,
      batch_size: 32,
      epochs: 100,
    },
    training_progress: undefined,
  };

  const mockCallbacks = {
    onTrain: jest.fn(),
    onStop: jest.fn(),
    onDeploy: jest.fn(),
    onDelete: jest.fn(),
    onViewDetails: jest.fn(),
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Component Rendering', () => {
    it('should render model information correctly', () => {
      render(<ModelCard model={mockModel} {...mockCallbacks} />);

      expect(screen.getByText('EURUSD Trend Predictor')).toBeInTheDocument();
      expect(screen.getByText('Neural network for trend prediction')).toBeInTheDocument();
      expect(screen.getByText('TRAINED')).toBeInTheDocument();
      expect(screen.getByText('NEURAL NETWORK')).toBeInTheDocument();
      expect(screen.getByText('EURUSD')).toBeInTheDocument();
      expect(screen.getByText('1h')).toBeInTheDocument();
    });

    it('should display model type icon correctly', () => {
      render(<ModelCard model={mockModel} {...mockCallbacks} />);

      const icon = screen.getByTitle('neural_network model');
      expect(icon).toHaveTextContent('🧠');
    });

    it('should display different model type icons', () => {
      const models = [
        { ...mockModel, model_type: 'random_forest' as const, name: 'RF Model' },
        { ...mockModel, model_type: 'svm' as const, name: 'SVM Model' },
        { ...mockModel, model_type: 'xgboost' as const, name: 'XGB Model' },
        { ...mockModel, model_type: 'lstm' as const, name: 'LSTM Model' },
        { ...mockModel, model_type: 'transformer' as const, name: 'Trans Model' },
      ];

      models.forEach((model) => {
        const { unmount } = render(<ModelCard model={model} {...mockCallbacks} />);
        const icon = screen.getByTitle(`${model.model_type} model`);
        expect(icon).toBeInTheDocument();
        unmount();
      });
    });

    it('should show deployment status when deployed', () => {
      const deployedModel = { ...mockModel, is_deployed: true };
      render(<ModelCard model={deployedModel} {...mockCallbacks} />);

      expect(screen.getByText('DEPLOYED')).toBeInTheDocument();
    });

    it('should display metrics correctly', () => {
      render(<ModelCard model={mockModel} {...mockCallbacks} />);

      expect(screen.getByText('85.0%')).toBeInTheDocument(); // Accuracy
      expect(screen.getByText('0.0234')).toBeInTheDocument(); // Loss
      expect(screen.getByText('82.0%')).toBeInTheDocument(); // Precision
      expect(screen.getByText('89.0%')).toBeInTheDocument(); // Recall
    });

    it('should handle missing metrics gracefully', () => {
      const modelNoMetrics = { ...mockModel, metrics: undefined };
      render(<ModelCard model={modelNoMetrics} {...mockCallbacks} />);

      expect(screen.getAllByText('--')).toHaveLength(4); // All metrics should show '--'
    });

    it('should display version information', () => {
      render(<ModelCard model={mockModel} {...mockCallbacks} />);

      expect(screen.getByText('Version:')).toBeInTheDocument();
      expect(screen.getByText('v1.0.0')).toBeInTheDocument();
    });
  });

  describe('Status Display', () => {
    it('should use correct colors for different statuses', () => {
      const statuses: Array<MLModel['status']> = [
        'trained',
        'training',
        'deployed',
        'failed',
        'pending',
        'draft',
      ];

      statuses.forEach((status) => {
        const model = { ...mockModel, status };
        const { unmount } = render(<ModelCard model={model} {...mockCallbacks} />);

        const statusElement = screen.getByText(status.toUpperCase());
        expect(statusElement).toBeInTheDocument();

        // Check that it has appropriate CSS classes based on status
        if (status === 'trained') {
          expect(statusElement).toHaveClass('text-green-400');
        } else if (status === 'training') {
          expect(statusElement).toHaveClass('text-blue-400');
        } else if (status === 'failed') {
          expect(statusElement).toHaveClass('text-red-400');
        } else if (status === 'pending') {
          expect(statusElement).toHaveClass('text-yellow-400');
        }

        unmount();
      });
    });

    it('should show training progress for training models', () => {
      const trainingModel = {
        ...mockModel,
        status: 'training' as const,
        training_progress: 0.65,
      };

      render(<ModelCard model={trainingModel} {...mockCallbacks} />);

      expect(screen.getByText('Training Progress')).toBeInTheDocument();
      expect(screen.getByText('65%')).toBeInTheDocument();

      const progressBar = screen.getByRole('progressbar');
      expect(progressBar).toHaveStyle('width: 65%');
    });
  });

  describe('Action Buttons', () => {
    it('should show train button for trainable models', () => {
      const trainableStatuses: Array<MLModel['status']> = ['draft', 'failed', 'trained'];

      trainableStatuses.forEach((status) => {
        const model = { ...mockModel, status };
        const { unmount } = render(<ModelCard model={model} {...mockCallbacks} />);

        expect(screen.getByTitle('Train Model')).toBeInTheDocument();
        unmount();
      });
    });

    it('should not show train button for non-trainable models', () => {
      const nonTrainableModel = { ...mockModel, status: 'training' as const };
      render(<ModelCard model={nonTrainableModel} {...mockCallbacks} />);

      expect(screen.queryByTitle('Train Model')).not.toBeInTheDocument();
    });

    it('should show stop button for training models', () => {
      const trainingModel = { ...mockModel, status: 'training' as const };
      render(<ModelCard model={trainingModel} {...mockCallbacks} />);

      expect(screen.getByTitle('Stop Training')).toBeInTheDocument();
    });

    it('should show deploy button for trained, undeployed models', () => {
      const trainedModel = { ...mockModel, status: 'trained' as const, is_deployed: false };
      render(<ModelCard model={trainedModel} {...mockCallbacks} />);

      expect(screen.getByTitle('Deploy Model')).toBeInTheDocument();
    });

    it('should not show deploy button for already deployed models', () => {
      const deployedModel = { ...mockModel, is_deployed: true };
      render(<ModelCard model={deployedModel} {...mockCallbacks} />);

      expect(screen.queryByTitle('Deploy Model')).not.toBeInTheDocument();
    });

    it('should always show view details and delete buttons', () => {
      render(<ModelCard model={mockModel} {...mockCallbacks} />);

      expect(screen.getByTitle('View Details')).toBeInTheDocument();
      expect(screen.getByTitle('Delete Model')).toBeInTheDocument();
    });
  });

  describe('Action Handlers', () => {
    it('should call onTrain when train button is clicked', async () => {
      render(<ModelCard model={mockModel} {...mockCallbacks} />);

      const trainButton = screen.getByTitle('Train Model');
      await user.click(trainButton);

      expect(mockCallbacks.onTrain).toHaveBeenCalledWith(mockModel);
    });

    it('should call onStop when stop button is clicked', async () => {
      const trainingModel = { ...mockModel, status: 'training' as const };
      render(<ModelCard model={trainingModel} {...mockCallbacks} />);

      const stopButton = screen.getByTitle('Stop Training');
      await user.click(stopButton);

      expect(mockCallbacks.onStop).toHaveBeenCalledWith(trainingModel);
    });

    it('should call onDeploy when deploy button is clicked', async () => {
      const trainedModel = { ...mockModel, status: 'trained' as const, is_deployed: false };
      render(<ModelCard model={trainedModel} {...mockCallbacks} />);

      const deployButton = screen.getByTitle('Deploy Model');
      await user.click(deployButton);

      expect(mockCallbacks.onDeploy).toHaveBeenCalledWith(trainedModel);
    });

    it('should call onDelete when delete button is clicked', async () => {
      render(<ModelCard model={mockModel} {...mockCallbacks} />);

      const deleteButton = screen.getByTitle('Delete Model');
      await user.click(deleteButton);

      expect(mockCallbacks.onDelete).toHaveBeenCalledWith(mockModel);
    });

    it('should call onViewDetails when view details button is clicked', async () => {
      render(<ModelCard model={mockModel} {...mockCallbacks} />);

      const viewButton = screen.getByTitle('View Details');
      await user.click(viewButton);

      expect(mockCallbacks.onViewDetails).toHaveBeenCalledWith(mockModel);
    });
  });

  describe('Loading States', () => {
    it('should show loading spinner when training action is in progress', async () => {
      render(<ModelCard model={mockModel} {...mockCallbacks} />);

      const trainButton = screen.getByTitle('Train Model');
      await user.click(trainButton);

      // Should show loading spinner
      expect(screen.getByRole('button')).toContain(
        document.querySelector('.animate-spin')
      );
    });

    it('should disable button during loading', async () => {
      render(<ModelCard model={mockModel} {...mockCallbacks} />);

      const trainButton = screen.getByTitle('Train Model');
      await user.click(trainButton);

      expect(trainButton).toBeDisabled();
    });

    it('should show different loading states for different actions', async () => {
      const trainedModel = { ...mockModel, status: 'trained' as const, is_deployed: false };
      render(<ModelCard model={trainedModel} {...mockCallbacks} />);

      // Test deploy loading
      const deployButton = screen.getByTitle('Deploy Model');
      await user.click(deployButton);
      expect(deployButton).toBeDisabled();

      // Wait for loading to finish
      await waitFor(() => {
        expect(deployButton).not.toBeDisabled();
      });

      // Test delete loading
      const deleteButton = screen.getByTitle('Delete Model');
      await user.click(deleteButton);
      expect(deleteButton).toBeDisabled();
    });
  });

  describe('Model Information Display', () => {
    it('should display relative time formatting', () => {
      render(<ModelCard model={mockModel} {...mockCallbacks} />);

      expect(screen.getByText('Created:')).toBeInTheDocument();
      expect(screen.getByText('Last Trained:')).toBeInTheDocument();
      expect(screen.getAllByText('2 hours ago')).toHaveLength(2);
    });

    it('should handle model without last_trained date', () => {
      const newModel = { ...mockModel, last_trained: undefined };
      render(<ModelCard model={newModel} {...mockCallbacks} />);

      expect(screen.getByText('Created:')).toBeInTheDocument();
      expect(screen.queryByText('Last Trained:')).not.toBeInTheDocument();
    });

    it('should handle model without version', () => {
      const versionlessModel = { ...mockModel, version: undefined };
      render(<ModelCard model={versionlessModel} {...mockCallbacks} />);

      expect(screen.queryByText('Version:')).not.toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('should have proper ARIA labels', () => {
      render(<ModelCard model={mockModel} {...mockCallbacks} />);

      expect(screen.getByTitle('Train Model')).toBeInTheDocument();
      expect(screen.getByTitle('Deploy Model')).toBeInTheDocument();
      expect(screen.getByTitle('View Details')).toBeInTheDocument();
      expect(screen.getByTitle('Delete Model')).toBeInTheDocument();
      expect(screen.getByTitle('neural_network model')).toBeInTheDocument();
    });

    it('should be keyboard navigable', async () => {
      render(<ModelCard model={mockModel} {...mockCallbacks} />);

      // Should be able to tab through buttons
      const trainButton = screen.getByTitle('Train Model');
      const deployButton = screen.getByTitle('Deploy Model');
      const viewButton = screen.getByTitle('View Details');
      const deleteButton = screen.getByTitle('Delete Model');

      await user.tab();
      expect(trainButton).toHaveFocus();

      await user.tab();
      expect(deployButton).toHaveFocus();

      await user.tab();
      expect(viewButton).toHaveFocus();

      await user.tab();
      expect(deleteButton).toHaveFocus();
    });
  });

  describe('Error Handling', () => {
    it('should handle action errors gracefully', async () => {
      const errorCallback = jest.fn().mockRejectedValue(new Error('Training failed'));
      render(<ModelCard model={mockModel} onTrain={errorCallback} {...mockCallbacks} />);

      const trainButton = screen.getByTitle('Train Model');
      await user.click(trainButton);

      // Loading state should clear even on error
      await waitFor(() => {
        expect(trainButton).not.toBeDisabled();
      });
    });

    it('should handle missing callback functions', async () => {
      render(<ModelCard model={mockModel} />);

      // Buttons should still be present but clicking should not throw errors
      const trainButton = screen.getByTitle('Train Model');
      await user.click(trainButton);

      // Should not throw an error
      expect(trainButton).toBeInTheDocument();
    });
  });

  describe('Visual Styling', () => {
    it('should apply custom className', () => {
      const { container } = render(
        <ModelCard model={mockModel} className="custom-class" {...mockCallbacks} />
      );

      expect(container.firstChild).toHaveClass('custom-class');
    });

    it('should have consistent styling structure', () => {
      const { container } = render(<ModelCard model={mockModel} {...mockCallbacks} />);

      expect(container.firstChild).toHaveClass('bg-gray-900', 'border', 'border-gray-700', 'rounded-lg');
    });
  });
});
