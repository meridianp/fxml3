/**
 * TrainingStudio Component Tests
 *
 * Tests for the ML training studio interface
 */

import React from 'react';
import { screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithStore, mockApiSuccess, mockApiError } from '@/test-utils/render';
import TrainingStudio from '../TrainingStudio';
import { api } from '@/services/api';
import type { MLModel } from '@/types';

jest.mock('@/services/api');
const mockedApi = api as jest.Mocked<typeof api>;

// Mock child components
jest.mock('../ModelCard', () => {
  return function MockModelCard({ model, onTrain, onStop, onDeploy, onDelete }: any) {
    return (
      <div data-testid={`model-card-${model.id}`}>
        <div>{model.name}</div>
        <div>{model.status}</div>
        <button onClick={() => onTrain?.(model)}>Train</button>
        <button onClick={() => onStop?.(model)}>Stop</button>
        <button onClick={() => onDeploy?.(model)}>Deploy</button>
        <button onClick={() => onDelete?.(model)}>Delete</button>
      </div>
    );
  };
});

jest.mock('@/components/data', () => ({
  SymbolSelector: ({ value, onChange }: any) => (
    <select data-testid="symbol-selector" value={value} onChange={(e) => onChange(e.target.value)}>
      <option value="EURUSD">EURUSD</option>
      <option value="GBPUSD">GBPUSD</option>
      <option value="USDJPY">USDJPY</option>
    </select>
  ),
}));

jest.mock('@/stores/appStore');

describe('TrainingStudio', () => {
  const user = userEvent.setup();

  const mockModels: MLModel[] = [
    {
      id: 'model-1',
      name: 'EURUSD Neural Network',
      description: 'Deep learning model for EURUSD',
      model_type: 'neural_network',
      symbol: 'EURUSD',
      timeframe: '1h',
      status: 'trained',
      is_deployed: false,
      created_at: '2024-01-15T10:00:00.000Z',
      metrics: { accuracy: 0.85, loss: 0.023 },
    },
    {
      id: 'model-2',
      name: 'GBPUSD Random Forest',
      description: 'Random forest for GBPUSD prediction',
      model_type: 'random_forest',
      symbol: 'GBPUSD',
      timeframe: '4h',
      status: 'training',
      is_deployed: false,
      created_at: '2024-01-15T11:00:00.000Z',
      training_progress: 0.45,
    },
    {
      id: 'model-3',
      name: 'USDJPY LSTM',
      description: 'LSTM for USDJPY trend analysis',
      model_type: 'lstm',
      symbol: 'USDJPY',
      timeframe: '1h',
      status: 'trained',
      is_deployed: true,
      created_at: '2024-01-15T09:00:00.000Z',
      metrics: { accuracy: 0.78, loss: 0.034 },
    },
  ];

  const mockStoreState = {
    appState: {
      isConnected: true,
      errors: [],
      notifications: [],
    },
  };

  beforeEach(() => {
    jest.clearAllMocks();
    mockedApi.get.mockImplementation((url) => {
      if (url === '/ml/models') {
        return Promise.resolve(mockApiSuccess({ models: mockModels }));
      }
      if (url === '/ml/datasets') {
        return Promise.resolve(mockApiSuccess({ datasets: [] }));
      }
      return Promise.resolve(mockApiSuccess({}));
    });

    mockedApi.post.mockResolvedValue(mockApiSuccess({}));
    mockedApi.delete.mockResolvedValue(mockApiSuccess({}));
  });

  describe('Component Initialization', () => {
    it('should render training studio header', async () => {
      renderWithStore(<TrainingStudio />, mockStoreState);

      expect(screen.getByText('ML Training Studio')).toBeInTheDocument();
      expect(screen.getByText('Train and manage machine learning models')).toBeInTheDocument();
    });

    it('should load models on mount', async () => {
      renderWithStore(<TrainingStudio />, mockStoreState);

      await waitFor(() => {
        expect(mockedApi.get).toHaveBeenCalledWith('/ml/models');
      });
    });

    it('should load datasets on mount', async () => {
      renderWithStore(<TrainingStudio />, mockStoreState);

      await waitFor(() => {
        expect(mockedApi.get).toHaveBeenCalledWith('/ml/datasets');
      });
    });

    it('should display loading state while fetching models', () => {
      mockedApi.get.mockImplementation(() => new Promise(() => {})); // Never resolves

      renderWithStore(<TrainingStudio />, mockStoreState);

      expect(screen.getByText('Loading models...')).toBeInTheDocument();
    });
  });

  describe('Model Statistics', () => {
    it('should display correct model statistics', async () => {
      renderWithStore(<TrainingStudio />, mockStoreState);

      await waitFor(() => {
        expect(screen.getByText('3')).toBeInTheDocument(); // Total models
      });

      expect(screen.getByText('Total Models')).toBeInTheDocument();
      expect(screen.getByText('Trained')).toBeInTheDocument();
      expect(screen.getByText('Training')).toBeInTheDocument();
      expect(screen.getByText('Deployed')).toBeInTheDocument();

      // Check specific counts based on mock data
      const stats = screen.getAllByText('2'); // 2 trained models
      expect(stats.length).toBeGreaterThan(0);

      expect(screen.getByText('1')).toBeInTheDocument(); // 1 training, 1 deployed
    });

    it('should update statistics when models change', async () => {
      renderWithStore(<TrainingStudio />, mockStoreState);

      await waitFor(() => {
        expect(screen.getByText('3')).toBeInTheDocument();
      });

      // Simulate adding a new model
      const createButton = screen.getByText('Create Model');
      await user.click(createButton);

      // Fill out and submit form (this would update the stats)
      const nameInput = screen.getByPlaceholderText('e.g., EURUSD Trend Predictor');
      await user.type(nameInput, 'New Test Model');

      const submitButton = screen.getByRole('button', { name: /Create Model/i });
      await user.click(submitButton);

      // Stats should update after successful creation
      await waitFor(() => {
        expect(mockedApi.post).toHaveBeenCalledWith('/ml/models', expect.any(Object));
      });
    });
  });

  describe('Tab Navigation', () => {
    it('should render all tab options', async () => {
      renderWithStore(<TrainingStudio />, mockStoreState);

      expect(screen.getByRole('tab', { name: /Models/i })).toBeInTheDocument();
      expect(screen.getByRole('tab', { name: /Datasets/i })).toBeInTheDocument();
      expect(screen.getByRole('tab', { name: /Experiments/i })).toBeInTheDocument();
      expect(screen.getByRole('tab', { name: /Deployment/i })).toBeInTheDocument();
    });

    it('should switch between tabs', async () => {
      renderWithStore(<TrainingStudio />, mockStoreState);

      // Default should be models tab
      await waitFor(() => {
        expect(screen.getByTestId('model-card-model-1')).toBeInTheDocument();
      });

      // Switch to datasets tab
      const datasetsTab = screen.getByRole('tab', { name: /Datasets/i });
      await user.click(datasetsTab);

      expect(screen.getByText('Training Datasets')).toBeInTheDocument();
      expect(screen.getByText('Manage and prepare datasets for model training')).toBeInTheDocument();

      // Switch to experiments tab
      const experimentsTab = screen.getByRole('tab', { name: /Experiments/i });
      await user.click(experimentsTab);

      expect(screen.getByText('Experiments')).toBeInTheDocument();
      expect(screen.getByText('Track and compare model training experiments')).toBeInTheDocument();

      // Switch to deployment tab
      const deploymentTab = screen.getByRole('tab', { name: /Deployment/i });
      await user.click(deploymentTab);

      expect(screen.getByText('Model Deployment')).toBeInTheDocument();
      expect(screen.getByText('Deploy trained models for live trading signals')).toBeInTheDocument();
    });
  });

  describe('Models Display', () => {
    it('should render all models as cards', async () => {
      renderWithStore(<TrainingStudio />, mockStoreState);

      await waitFor(() => {
        expect(screen.getByTestId('model-card-model-1')).toBeInTheDocument();
        expect(screen.getByTestId('model-card-model-2')).toBeInTheDocument();
        expect(screen.getByTestId('model-card-model-3')).toBeInTheDocument();
      });

      expect(screen.getByText('EURUSD Neural Network')).toBeInTheDocument();
      expect(screen.getByText('GBPUSD Random Forest')).toBeInTheDocument();
      expect(screen.getByText('USDJPY LSTM')).toBeInTheDocument();
    });

    it('should show empty state when no models exist', () => {
      mockedApi.get.mockImplementation((url) => {
        if (url === '/ml/models') {
          return Promise.resolve(mockApiSuccess({ models: [] }));
        }
        return Promise.resolve(mockApiSuccess({}));
      });

      renderWithStore(<TrainingStudio />, mockStoreState);

      expect(screen.getByText('No Models Yet')).toBeInTheDocument();
      expect(screen.getByText('Create your first ML model to get started')).toBeInTheDocument();
      expect(screen.getByText('Create Your First Model')).toBeInTheDocument();
    });

    it('should handle loading errors gracefully', async () => {
      mockedApi.get.mockRejectedValueOnce(new Error('Failed to load'));

      renderWithStore(<TrainingStudio />, mockStoreState);

      // Should still render the component without crashing
      expect(screen.getByText('ML Training Studio')).toBeInTheDocument();
    });
  });

  describe('Model Creation Form', () => {
    it('should open create form when create button is clicked', async () => {
      renderWithStore(<TrainingStudio />, mockStoreState);

      const createButton = screen.getByText('Create Model');
      await user.click(createButton);

      expect(screen.getByText('Create New Model')).toBeInTheDocument();
      expect(screen.getByText('Configure your machine learning model')).toBeInTheDocument();
    });

    it('should close form when cancel is clicked', async () => {
      renderWithStore(<TrainingStudio />, mockStoreState);

      const createButton = screen.getByText('Create Model');
      await user.click(createButton);

      const cancelButton = screen.getByText('Cancel');
      await user.click(cancelButton);

      expect(screen.queryByText('Create New Model')).not.toBeInTheDocument();
    });

    it('should fill out and submit create form', async () => {
      const newModel = { id: 'new-model', name: 'Test Model', status: 'draft' };
      mockedApi.post.mockResolvedValueOnce(mockApiSuccess({ model: newModel }));

      renderWithStore(<TrainingStudio />, mockStoreState);

      // Open form
      const createButton = screen.getByText('Create Model');
      await user.click(createButton);

      // Fill out form
      const nameInput = screen.getByPlaceholderText('e.g., EURUSD Trend Predictor');
      await user.type(nameInput, 'Test Neural Network');

      const descriptionInput = screen.getByPlaceholderText('Describe what this model does...');
      await user.type(descriptionInput, 'Test model description');

      const modelTypeSelect = screen.getByDisplayValue('Neural Network');
      await user.selectOptions(modelTypeSelect, 'random_forest');

      const symbolSelector = screen.getByTestId('symbol-selector');
      await user.selectOptions(symbolSelector, 'GBPUSD');

      const timeframeSelect = screen.getByDisplayValue('1 Hour');
      await user.selectOptions(timeframeSelect, '4h');

      // Submit form
      const submitButton = screen.getByRole('button', { name: /Create Model/i });
      await user.click(submitButton);

      await waitFor(() => {
        expect(mockedApi.post).toHaveBeenCalledWith('/ml/models', expect.objectContaining({
          name: 'Test Neural Network',
          description: 'Test model description',
          model_type: 'random_forest',
          symbol: 'GBPUSD',
          timeframe: '4h',
        }));
      });
    });

    it('should handle feature selection', async () => {
      renderWithStore(<TrainingStudio />, mockStoreState);

      const createButton = screen.getByText('Create Model');
      await user.click(createButton);

      // Test feature checkboxes
      const priceFeatures = screen.getByLabelText(/Price Features/i);
      expect(priceFeatures).toBeChecked(); // Should be checked by default

      // Uncheck a feature
      await user.click(priceFeatures);
      expect(priceFeatures).not.toBeChecked();

      // Check a different feature
      const volumeFeatures = screen.getByLabelText(/Volume Features/i);
      await user.click(volumeFeatures); // Should toggle on/off

      const nameInput = screen.getByPlaceholderText('e.g., EURUSD Trend Predictor');
      await user.type(nameInput, 'Feature Test Model');

      const submitButton = screen.getByRole('button', { name: /Create Model/i });
      await user.click(submitButton);

      await waitFor(() => {
        expect(mockedApi.post).toHaveBeenCalledWith('/ml/models', expect.objectContaining({
          features: expect.arrayContaining([
            'technical_indicators', // Should still be included
          ]),
        }));
      });
    });

    it('should disable submit button when required fields are missing', async () => {
      renderWithStore(<TrainingStudio />, mockStoreState);

      const createButton = screen.getByText('Create Model');
      await user.click(createButton);

      const submitButton = screen.getByRole('button', { name: /Create Model/i });
      expect(submitButton).toBeDisabled();

      // Add name to enable button
      const nameInput = screen.getByPlaceholderText('e.g., EURUSD Trend Predictor');
      await user.type(nameInput, 'Test Model');

      expect(submitButton).not.toBeDisabled();
    });
  });

  describe('Model Actions', () => {
    it('should handle model training', async () => {
      renderWithStore(<TrainingStudio />, mockStoreState);

      await waitFor(() => {
        expect(screen.getByTestId('model-card-model-1')).toBeInTheDocument();
      });

      const trainButton = screen.getAllByText('Train')[0];
      await user.click(trainButton);

      await waitFor(() => {
        expect(mockedApi.post).toHaveBeenCalledWith('/ml/models/model-1/train');
      });
    });

    it('should handle stopping training', async () => {
      renderWithStore(<TrainingStudio />, mockStoreState);

      await waitFor(() => {
        expect(screen.getByTestId('model-card-model-2')).toBeInTheDocument();
      });

      const stopButton = screen.getAllByText('Stop')[0];
      await user.click(stopButton);

      await waitFor(() => {
        expect(mockedApi.post).toHaveBeenCalledWith('/ml/models/model-2/stop');
      });
    });

    it('should handle model deployment', async () => {
      renderWithStore(<TrainingStudio />, mockStoreState);

      await waitFor(() => {
        expect(screen.getByTestId('model-card-model-1')).toBeInTheDocument();
      });

      const deployButton = screen.getAllByText('Deploy')[0];
      await user.click(deployButton);

      await waitFor(() => {
        expect(mockedApi.post).toHaveBeenCalledWith('/ml/models/model-1/deploy');
      });
    });

    it('should handle model deletion', async () => {
      renderWithStore(<TrainingStudio />, mockStoreState);

      await waitFor(() => {
        expect(screen.getByTestId('model-card-model-1')).toBeInTheDocument();
      });

      // Mock window.confirm
      window.confirm = jest.fn(() => true);

      const deleteButton = screen.getAllByText('Delete')[0];
      await user.click(deleteButton);

      await waitFor(() => {
        expect(mockedApi.delete).toHaveBeenCalledWith('/ml/models/model-1');
      });

      expect(window.confirm).toHaveBeenCalledWith('Are you sure you want to delete "EURUSD Neural Network"?');
    });

    it('should not delete model if user cancels confirmation', async () => {
      renderWithStore(<TrainingStudio />, mockStoreState);

      await waitFor(() => {
        expect(screen.getByTestId('model-card-model-1')).toBeInTheDocument();
      });

      // Mock window.confirm to return false
      window.confirm = jest.fn(() => false);

      const deleteButton = screen.getAllByText('Delete')[0];
      await user.click(deleteButton);

      expect(window.confirm).toHaveBeenCalled();
      expect(mockedApi.delete).not.toHaveBeenCalled();
    });
  });

  describe('Error Handling', () => {
    it('should handle API errors during model creation', async () => {
      mockedApi.post.mockRejectedValueOnce(new Error('Creation failed'));

      renderWithStore(<TrainingStudio />, mockStoreState);

      const createButton = screen.getByText('Create Model');
      await user.click(createButton);

      const nameInput = screen.getByPlaceholderText('e.g., EURUSD Trend Predictor');
      await user.type(nameInput, 'Test Model');

      const submitButton = screen.getByRole('button', { name: /Create Model/i });
      await user.click(submitButton);

      // Should handle error gracefully without crashing
      await waitFor(() => {
        expect(submitButton).not.toBeDisabled();
      });
    });

    it('should handle training errors', async () => {
      mockedApi.post.mockImplementation((url) => {
        if (url.includes('/train')) {
          return Promise.reject(new Error('Training failed'));
        }
        return Promise.resolve(mockApiSuccess({}));
      });

      renderWithStore(<TrainingStudio />, mockStoreState);

      await waitFor(() => {
        expect(screen.getByTestId('model-card-model-1')).toBeInTheDocument();
      });

      const trainButton = screen.getAllByText('Train')[0];
      await user.click(trainButton);

      // Should handle error gracefully
      await waitFor(() => {
        expect(mockedApi.post).toHaveBeenCalledWith('/ml/models/model-1/train');
      });
    });
  });

  describe('Keyboard Navigation', () => {
    it('should be keyboard accessible', async () => {
      renderWithStore(<TrainingStudio />, mockStoreState);

      // Should be able to navigate to create button
      await user.tab();
      expect(screen.getByText('Create Model')).toHaveFocus();

      // Should be able to navigate through tabs
      const modelsTab = screen.getByRole('tab', { name: /Models/i });
      modelsTab.focus();
      expect(modelsTab).toHaveFocus();

      await user.keyboard('{ArrowRight}');
      expect(screen.getByRole('tab', { name: /Datasets/i })).toHaveFocus();
    });
  });
});
