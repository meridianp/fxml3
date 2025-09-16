"""
ML Training Component Test Suite
===============================

Example test demonstrating advanced testing patterns for ML training components
including async operations, data visualization, and complex user interactions.
"""

import React from 'react';
import { rest } from 'msw';
import { ComponentTestBuilder, testUtils, generateMockData } from '../foundation/component-test-foundation';
import MLTrainingDashboard from '@/components/MLTrainingDashboard';

describe('MLTrainingDashboard Component', () => {
  let testBuilder: ComponentTestBuilder<any>;

  beforeEach(() => {
    testBuilder = new ComponentTestBuilder(MLTrainingDashboard);
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  describe('Training Process', () => {
    it('should start training with valid parameters', async () => {
      let trainingStarted = false;

      await testBuilder
        .withApiMock(
          rest.post('/api/ml/training/start', (req, res, ctx) => {
            trainingStarted = true;
            return res(ctx.json({
              trainingId: 'train-123',
              status: 'started',
              estimatedDuration: 300, // 5 minutes
            }));
          })
        )
        .render();

      await testBuilder.waitForLoading();

      // Configure training parameters
      await testBuilder.selectOption('Algorithm', 'xgboost');
      await testBuilder.selectOption('Symbol', 'EUR/USD');
      await testBuilder.typeInInput('Training Period (days)', '365');
      await testBuilder.clickButton('Start Training');

      // Verify training started
      expect(trainingStarted).toBe(true);
      await testBuilder.waitForText('Training started...');
    });

    it('should show progress updates during training', async () => {
      const { getByTestId } = await testBuilder
        .withApiMock(
          rest.post('/api/ml/training/start', (req, res, ctx) => {
            return res(ctx.json({ trainingId: 'train-123' }));
          })
        )
        .withApiMock(
          rest.get('/api/ml/training/train-123/status', (req, res, ctx) => {
            return res(ctx.json({
              status: 'training',
              progress: 0.45,
              currentEpoch: 45,
              totalEpochs: 100,
              accuracy: 0.73,
            }));
          })
        )
        .render();

      await testBuilder.clickButton('Start Training');

      // Wait for progress updates
      await testUtils.advanceTimersByTime(5000); // 5 seconds

      expect(getByTestId('progress-bar')).toHaveAttribute('value', '45');
      expect(getByTestId('accuracy-display')).toHaveTextContent('73%');
    });

    it('should handle training completion', async () => {
      const mockModel = {
        modelId: 'model-456',
        accuracy: 0.87,
        precision: 0.84,
        recall: 0.89,
        f1Score: 0.86,
        sharpeRatio: 2.15,
      };

      await testBuilder
        .withApiMock(
          rest.get('/api/ml/training/train-123/status', (req, res, ctx) => {
            return res(ctx.json({
              status: 'completed',
              model: mockModel,
            }));
          })
        )
        .render();

      // Simulate training completion
      testUtils.sendWebSocketMessage({
        type: 'training_completed',
        data: { trainingId: 'train-123', model: mockModel },
      });

      await testBuilder.waitForText('Training Completed');
      await testBuilder.waitForText('Accuracy: 87%');
      await testBuilder.waitForText('Sharpe Ratio: 2.15');
    });

    it('should allow training cancellation', async () => {
      let trainingCancelled = false;

      await testBuilder
        .withApiMock(
          rest.delete('/api/ml/training/train-123', (req, res, ctx) => {
            trainingCancelled = true;
            return res(ctx.json({ success: true }));
          })
        )
        .render();

      // Start training first
      await testBuilder.clickButton('Start Training');
      await testBuilder.waitForText('Training in progress...');

      // Cancel training
      await testBuilder.clickButton('Cancel Training');
      await testBuilder.clickButton('Confirm Cancellation');

      expect(trainingCancelled).toBe(true);
      await testBuilder.waitForText('Training cancelled');
    });
  });

  describe('Data Visualization', () => {
    it('should display training metrics chart', async () => {
      const metricsData = [
        { epoch: 1, accuracy: 0.45, loss: 0.89 },
        { epoch: 2, accuracy: 0.52, loss: 0.78 },
        { epoch: 3, accuracy: 0.61, loss: 0.65 },
      ];

      const { getByTestId } = await testBuilder
        .withApiMock(
          rest.get('/api/ml/training/train-123/metrics', (req, res, ctx) => {
            return res(ctx.json(metricsData));
          })
        )
        .render();

      await testBuilder.waitForLoading();

      const chart = getByTestId('training-metrics-chart');
      expect(chart).toBeInTheDocument();

      // Check if chart contains data points
      expect(chart.querySelectorAll('.recharts-line')).toHaveLength(2); // accuracy + loss
    });

    it('should update chart in real-time', async () => {
      const { getByTestId } = await testBuilder.render();

      // Send real-time metric updates
      for (let i = 1; i <= 5; i++) {
        testUtils.sendWebSocketMessage({
          type: 'training_metrics',
          data: {
            epoch: i,
            accuracy: 0.4 + i * 0.05,
            loss: 1.0 - i * 0.1,
          },
        });

        await testUtils.advanceTimersByTime(1000);
      }

      const chart = getByTestId('training-metrics-chart');
      const dataPoints = chart.querySelectorAll('.recharts-dot');
      expect(dataPoints.length).toBeGreaterThan(0);
    });
  });

  describe('Model Comparison', () => {
    it('should compare multiple models', async () => {
      const models = [
        { id: 'model-1', algorithm: 'xgboost', accuracy: 0.85 },
        { id: 'model-2', algorithm: 'lightgbm', accuracy: 0.83 },
        { id: 'model-3', algorithm: 'neural_network', accuracy: 0.88 },
      ];

      await testBuilder
        .withApiMock(
          rest.get('/api/ml/models', (req, res, ctx) => {
            return res(ctx.json(models));
          })
        )
        .render();

      await testBuilder.waitForLoading();

      // Switch to comparison view
      await testBuilder.clickButton('Compare Models');

      // Verify all models are displayed
      testBuilder.expectText('xgboost - 85%');
      testBuilder.expectText('lightgbm - 83%');
      testBuilder.expectText('neural_network - 88%');
    });

    it('should highlight best performing model', async () => {
      const { getByTestId } = await testBuilder.render();

      await testBuilder.clickButton('Compare Models');

      const bestModel = getByTestId('best-model-highlight');
      expect(bestModel).toHaveClass('best-model');
      expect(bestModel).toHaveTextContent('neural_network');
    });
  });

  describe('Hyperparameter Tuning', () => {
    it('should allow hyperparameter adjustment', async () => {
      await testBuilder.render();

      // Open hyperparameter panel
      await testBuilder.clickButton('Advanced Settings');

      // Adjust parameters
      await testBuilder.typeInInput('Learning Rate', '0.01');
      await testBuilder.typeInInput('Max Depth', '6');
      await testBuilder.typeInInput('N Estimators', '500');

      // Save settings
      await testBuilder.clickButton('Save Parameters');

      await testBuilder.waitForText('Parameters saved');
    });

    it('should validate hyperparameter ranges', async () => {
      await testBuilder.render();

      await testBuilder.clickButton('Advanced Settings');

      // Try invalid values
      await testBuilder.typeInInput('Learning Rate', '2.5'); // Too high
      await testBuilder.typeInInput('Max Depth', '0'); // Too low

      await testBuilder.clickButton('Save Parameters');

      // Check validation errors
      testBuilder.expectText('Learning rate must be between 0.001 and 1.0');
      testBuilder.expectText('Max depth must be at least 1');
    });
  });

  describe('Model Deployment', () => {
    it('should deploy trained model', async () => {
      let modelDeployed = false;

      await testBuilder
        .withApiMock(
          rest.post('/api/ml/models/model-123/deploy', (req, res, ctx) => {
            modelDeployed = true;
            return res(ctx.json({
              deploymentId: 'deploy-789',
              status: 'deployed',
              endpoint: '/api/predictions/model-123',
            }));
          })
        )
        .render();

      // Select model and deploy
      await testBuilder.selectOption('Select Model', 'model-123');
      await testBuilder.clickButton('Deploy Model');

      // Confirm deployment
      await testBuilder.clickButton('Confirm Deployment');

      expect(modelDeployed).toBe(true);
      await testBuilder.waitForText('Model deployed successfully');
      await testBuilder.waitForText('/api/predictions/model-123');
    });

    it('should show deployment status', async () => {
      const { getByTestId } = await testBuilder
        .withApiMock(
          rest.get('/api/ml/deployments', (req, res, ctx) => {
            return res(ctx.json([
              {
                id: 'deploy-1',
                modelId: 'model-123',
                status: 'running',
                requests: 1250,
                avgLatency: 45,
              },
            ]));
          })
        )
        .render();

      await testBuilder.clickButton('Deployment Status');
      await testBuilder.waitForLoading();

      expect(getByTestId('deployment-status')).toHaveTextContent('Running');
      expect(getByTestId('request-count')).toHaveTextContent('1,250');
      expect(getByTestId('avg-latency')).toHaveTextContent('45ms');
    });
  });

  describe('Error Handling', () => {
    it('should handle training failures gracefully', async () => {
      await testBuilder
        .withApiMock(
          rest.post('/api/ml/training/start', (req, res, ctx) => {
            return res(ctx.status(500), ctx.json({
              error: 'Insufficient training data',
            }));
          })
        )
        .render();

      await testBuilder.clickButton('Start Training');

      await testBuilder.waitForText('Training failed: Insufficient training data');
    });

    it('should retry failed operations', async () => {
      let attempts = 0;

      await testBuilder
        .withApiMock(
          rest.post('/api/ml/training/start', (req, res, ctx) => {
            attempts++;
            if (attempts < 3) {
              return res(ctx.status(503), ctx.json({ error: 'Service unavailable' }));
            }
            return res(ctx.json({ trainingId: 'train-retry-123' }));
          })
        )
        .render();

      await testBuilder.clickButton('Start Training');

      // Should show retry message
      await testBuilder.waitForText('Retrying...');

      // Eventually succeeds
      await testBuilder.waitForText('Training started...');

      expect(attempts).toBe(3);
    });
  });

  describe('Performance', () => {
    it('should handle large datasets efficiently', async () => {
      // Generate large dataset
      const largeDataset = Array.from({ length: 10000 }, (_, i) => ({
        timestamp: new Date(Date.now() - i * 86400000).toISOString(),
        price: 1.0850 + Math.random() * 0.02 - 0.01,
        volume: Math.floor(Math.random() * 1000000),
      }));

      await testBuilder
        .withApiMock(
          rest.get('/api/market-data/historical', (req, res, ctx) => {
            return res(ctx.json(largeDataset));
          })
        )
        .render();

      const startTime = performance.now();

      await testBuilder.clickButton('Load Historical Data');
      await testBuilder.waitForText('10,000 records loaded');

      const loadTime = performance.now() - startTime;
      expect(loadTime).toBeLessThan(3000); // Should load within 3 seconds
    });

    it('should virtualize large lists', async () => {
      const { getByTestId } = await testBuilder.render();

      // Load component with many items
      await testBuilder.clickButton('View All Models');

      const list = getByTestId('model-list');

      // Check that only visible items are rendered
      const renderedItems = list.querySelectorAll('[data-testid^="model-item-"]');
      expect(renderedItems.length).toBeLessThan(50); // Should virtualize
    });
  });
});
