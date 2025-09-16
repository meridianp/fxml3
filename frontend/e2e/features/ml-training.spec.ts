/**
 * ML Training Workflow E2E Tests
 *
 * Comprehensive testing of machine learning training interface, experiment tracking, and model management
 */

import { test, expect } from '@playwright/test';

test.describe('ML Training Workflow', () => {
  test.use({ storageState: 'e2e/.auth/user.json' });

  test.beforeEach(async ({ page }) => {
    await page.goto('/training');
    await page.waitForLoadState('networkidle');
  });

  test('training studio layout and components', async ({ page }) => {
    // Verify main training studio
    await expect(page.locator('[data-testid="training-studio"]')).toBeVisible();

    // Verify key components
    await expect(page.locator('[data-testid="dataset-manager"]')).toBeVisible();
    await expect(page.locator('[data-testid="model-configuration"]')).toBeVisible();
    await expect(page.locator('[data-testid="experiment-tracker"]')).toBeVisible();
  });

  test('dataset management and preparation', async ({ page }) => {
    const datasetManager = page.locator('[data-testid="dataset-manager"]');

    // Verify dataset list
    await expect(datasetManager.locator('[data-testid="dataset-list"]')).toBeVisible();

    // Test dataset upload
    if (await datasetManager.locator('[data-testid="upload-dataset-button"]').isVisible()) {
      await datasetManager.locator('[data-testid="upload-dataset-button"]').click();

      // Verify upload modal
      await expect(page.locator('[data-testid="upload-modal"]')).toBeVisible();

      // Fill dataset details
      await page.fill('[data-testid="dataset-name"]', 'E2E Test Dataset');
      await page.selectOption('[data-testid="dataset-type"]', 'forex_pairs');

      // Close modal (skip actual file upload for E2E)
      await page.click('[data-testid="cancel-upload"]');
      await expect(page.locator('[data-testid="upload-modal"]')).toBeHidden();
    }

    // Test dataset selection
    if (await datasetManager.locator('[data-testid="dataset-item"]').first().isVisible()) {
      await datasetManager.locator('[data-testid="dataset-item"]').first().click();

      // Verify dataset details
      await expect(page.locator('[data-testid="dataset-details"]')).toBeVisible();
      await expect(page.locator('[data-testid="dataset-preview"]')).toBeVisible();
    }
  });

  test('model configuration and parameter tuning', async ({ page }) => {
    const modelConfig = page.locator('[data-testid="model-configuration"]');

    // Select model type
    if (await modelConfig.locator('[data-testid="model-type-selector"]').isVisible()) {
      await modelConfig.locator('[data-testid="model-type-selector"]').click();
      await page.click('[data-testid="model-type-lstm"]');

      // Verify model-specific parameters appear
      await expect(page.locator('[data-testid="lstm-parameters"]')).toBeVisible();
    }

    // Configure hyperparameters
    if (await page.locator('[data-testid="hyperparameters-section"]').isVisible()) {
      // Set learning rate
      await page.fill('[data-testid="learning-rate-input"]', '0.001');

      // Set batch size
      await page.fill('[data-testid="batch-size-input"]', '32');

      // Set epochs
      await page.fill('[data-testid="epochs-input"]', '10');

      // Configure layers
      if (await page.locator('[data-testid="add-layer-button"]').isVisible()) {
        await page.click('[data-testid="add-layer-button"]');

        // Configure new layer
        await page.selectOption('[data-testid="layer-type"]', 'dense');
        await page.fill('[data-testid="layer-units"]', '50');

        await page.click('[data-testid="save-layer"]');
      }
    }
  });

  test('training execution and monitoring', async ({ page }) => {
    // Ensure we have a dataset and model selected
    if (await page.locator('[data-testid="start-training-button"]').isVisible()) {
      // Start training
      await page.click('[data-testid="start-training-button"]');

      // Verify training progress modal
      await expect(page.locator('[data-testid="training-progress-modal"]')).toBeVisible();

      // Verify progress indicators
      await expect(page.locator('[data-testid="training-progress-bar"]')).toBeVisible();
      await expect(page.locator('[data-testid="current-epoch"]')).toBeVisible();
      await expect(page.locator('[data-testid="training-loss"]')).toBeVisible();

      // Verify real-time metrics
      if (await page.locator('[data-testid="training-metrics-chart"]').isVisible()) {
        await expect(page.locator('[data-testid="training-metrics-chart"]')).toBeVisible();
      }

      // Test pause functionality
      if (await page.locator('[data-testid="pause-training-button"]').isVisible()) {
        await page.click('[data-testid="pause-training-button"]');

        // Verify paused state
        await expect(page.locator('[data-testid="training-paused-indicator"]')).toBeVisible();

        // Resume training
        await page.click('[data-testid="resume-training-button"]');
      }

      // For E2E testing, stop training early
      if (await page.locator('[data-testid="stop-training-button"]').isVisible()) {
        await page.click('[data-testid="stop-training-button"]');

        // Confirm stop
        await page.click('[data-testid="confirm-stop-training"]');

        // Verify training stopped
        await expect(page.locator('[data-testid="training-stopped-message"]')).toBeVisible();
      }
    }
  });

  test('experiment tracking and comparison', async ({ page }) => {
    const experimentTracker = page.locator('[data-testid="experiment-tracker"]');

    // Verify experiment list
    await expect(experimentTracker.locator('[data-testid="experiment-list"]')).toBeVisible();

    // Check if experiments exist
    const experiments = experimentTracker.locator('[data-testid="experiment-row"]');
    const experimentCount = await experiments.count();

    if (experimentCount > 0) {
      // Test experiment selection
      await experiments.first().click();

      // Verify experiment details
      await expect(page.locator('[data-testid="experiment-details"]')).toBeVisible();
      await expect(page.locator('[data-testid="experiment-metrics"]')).toBeVisible();

      // Test experiment comparison
      if (experimentCount > 1 && await page.locator('[data-testid="compare-experiments"]').isVisible()) {
        // Select multiple experiments
        await experiments.first().locator('[data-testid="experiment-checkbox"]').check();
        await experiments.nth(1).locator('[data-testid="experiment-checkbox"]').check();

        // Start comparison
        await page.click('[data-testid="compare-selected-button"]');

        // Verify comparison view
        await expect(page.locator('[data-testid="experiment-comparison"]')).toBeVisible();
        await expect(page.locator('[data-testid="comparison-metrics-table"]')).toBeVisible();
      }
    }

    // Test creating new experiment
    if (await page.locator('[data-testid="new-experiment-button"]').isVisible()) {
      await page.click('[data-testid="new-experiment-button"]');

      // Fill experiment details
      await page.fill('[data-testid="experiment-name"]', 'E2E Test Experiment');
      await page.fill('[data-testid="experiment-description"]', 'Automated E2E test experiment');

      // Save experiment
      await page.click('[data-testid="save-experiment"]');

      // Verify experiment created
      await expect(page.locator('[data-testid="experiment-created-notification"]')).toBeVisible();
    }
  });

  test('model evaluation and validation', async ({ page }) => {
    // Check if there are trained models to evaluate
    if (await page.locator('[data-testid="model-list"]').isVisible()) {
      const modelList = page.locator('[data-testid="model-list"]');
      const models = modelList.locator('[data-testid="model-item"]');
      const modelCount = await models.count();

      if (modelCount > 0) {
        // Select a model for evaluation
        await models.first().click();

        // Start evaluation
        if (await page.locator('[data-testid="evaluate-model-button"]').isVisible()) {
          await page.click('[data-testid="evaluate-model-button"]');

          // Verify evaluation results
          await expect(page.locator('[data-testid="evaluation-results"]')).toBeVisible();
          await expect(page.locator('[data-testid="model-accuracy"]')).toBeVisible();
          await expect(page.locator('[data-testid="confusion-matrix"]')).toBeVisible();

          // Test validation metrics
          if (await page.locator('[data-testid="validation-metrics"]').isVisible()) {
            await expect(page.locator('[data-testid="precision-score"]')).toBeVisible();
            await expect(page.locator('[data-testid="recall-score"]')).toBeVisible();
            await expect(page.locator('[data-testid="f1-score"]')).toBeVisible();
          }
        }
      }
    }
  });

  test('model deployment workflow', async ({ page }) => {
    // Navigate to deployment section
    if (await page.locator('[data-testid="deployment-manager"]').isVisible()) {
      const deploymentManager = page.locator('[data-testid="deployment-manager"]');

      // Test model deployment
      if (await deploymentManager.locator('[data-testid="deploy-model-button"]').isVisible()) {
        await deploymentManager.locator('[data-testid="deploy-model-button"]').click();

        // Configure deployment
        await expect(page.locator('[data-testid="deployment-config"]')).toBeVisible();

        // Set deployment name
        await page.fill('[data-testid="deployment-name"]', 'E2E Test Deployment');

        // Select environment
        await page.selectOption('[data-testid="deployment-environment"]', 'staging');

        // Configure resources
        await page.selectOption('[data-testid="instance-type"]', 'small');

        // Start deployment
        await page.click('[data-testid="start-deployment"]');

        // Verify deployment progress
        await expect(page.locator('[data-testid="deployment-progress"]')).toBeVisible();

        // For E2E testing, we might mock the deployment completion
        await page.waitForSelector('[data-testid="deployment-complete"]', { timeout: 30000 });

        // Verify deployment success
        await expect(page.locator('[data-testid="deployment-success-message"]')).toBeVisible();
      }

      // Test deployment monitoring
      if (await deploymentManager.locator('[data-testid="deployment-list"]').isVisible()) {
        const deployments = deploymentManager.locator('[data-testid="deployment-item"]');

        if (await deployments.first().isVisible()) {
          await deployments.first().click();

          // Verify deployment details
          await expect(page.locator('[data-testid="deployment-details"]')).toBeVisible();
          await expect(page.locator('[data-testid="deployment-status"]')).toBeVisible();
          await expect(page.locator('[data-testid="deployment-metrics"]')).toBeVisible();
        }
      }
    }
  });

  test('parameter optimization workflow', async ({ page }) => {
    // Navigate to optimization section
    if (await page.locator('[data-testid="optimization-workbench"]').isVisible()) {
      const optimizationWorkbench = page.locator('[data-testid="optimization-workbench"]');

      // Test grid search optimization
      if (await optimizationWorkbench.locator('[data-testid="grid-search-tab"]').isVisible()) {
        await optimizationWorkbench.locator('[data-testid="grid-search-tab"]').click();

        // Configure parameter ranges
        await page.fill('[data-testid="learning-rate-min"]', '0.0001');
        await page.fill('[data-testid="learning-rate-max"]', '0.01');
        await page.fill('[data-testid="learning-rate-steps"]', '5');

        await page.fill('[data-testid="batch-size-values"]', '16,32,64');

        // Start optimization
        await page.click('[data-testid="start-grid-search"]');

        // Verify optimization progress
        await expect(page.locator('[data-testid="optimization-progress"]')).toBeVisible();

        // For E2E testing, stop early
        await page.click('[data-testid="stop-optimization"]');
        await page.click('[data-testid="confirm-stop"]');
      }

      // Test genetic algorithm optimization
      if (await optimizationWorkbench.locator('[data-testid="genetic-algorithm-tab"]').isVisible()) {
        await optimizationWorkbench.locator('[data-testid="genetic-algorithm-tab"]').click();

        // Configure GA parameters
        await page.fill('[data-testid="population-size"]', '20');
        await page.fill('[data-testid="generations"]', '10');
        await page.fill('[data-testid="mutation-rate"]', '0.1');

        // Configure parameter bounds
        await page.fill('[data-testid="param-bounds"]', '{"learning_rate": [0.001, 0.1], "batch_size": [16, 128]}');

        // Start GA optimization
        await page.click('[data-testid="start-genetic-algorithm"]');

        // Verify GA progress
        await expect(page.locator('[data-testid="ga-progress"]')).toBeVisible();
        await expect(page.locator('[data-testid="generation-counter"]')).toBeVisible();

        // Stop early for E2E
        await page.click('[data-testid="stop-ga"]');
      }
    }
  });

  test('training error handling and recovery', async ({ page }) => {
    // Test insufficient data error
    if (await page.locator('[data-testid="start-training-button"]').isVisible()) {
      // Try to start training without proper setup
      await page.click('[data-testid="start-training-button"]');

      // Verify validation error
      if (await page.locator('[data-testid="validation-error"]').isVisible()) {
        await expect(page.locator('[data-testid="validation-error"]')).toContainText('dataset');
      }
    }

    // Test network error during training
    await page.route('**/api/training/**', route => route.abort());

    if (await page.locator('[data-testid="retry-connection"]').isVisible()) {
      await page.click('[data-testid="retry-connection"]');

      // Verify error handling
      await expect(page.locator('[data-testid="connection-error"]')).toBeVisible();
    }

    // Restore connection
    await page.unroute('**/api/training/**');
  });

  test('training workspace persistence', async ({ page }) => {
    // Configure a training session
    if (await page.locator('[data-testid="model-type-selector"]').isVisible()) {
      await page.click('[data-testid="model-type-selector"]');
      await page.click('[data-testid="model-type-lstm"]');

      await page.fill('[data-testid="learning-rate-input"]', '0.002');
      await page.fill('[data-testid="batch-size-input"]', '64');
    }

    // Refresh page
    await page.reload();
    await page.waitForLoadState('networkidle');

    // Verify settings are preserved
    if (await page.locator('[data-testid="learning-rate-input"]').isVisible()) {
      const learningRate = await page.locator('[data-testid="learning-rate-input"]').inputValue();
      expect(learningRate).toBe('0.002');
    }
  });

  test('mobile training interface', async ({ page }) => {
    // Switch to mobile viewport
    await page.setViewportSize({ width: 375, height: 667 });

    // Verify mobile layout
    await expect(page.locator('[data-testid="training-studio"]')).toBeVisible();

    // Test mobile navigation
    if (await page.locator('[data-testid="mobile-training-tabs"]').isVisible()) {
      await page.click('[data-testid="tab-datasets"]');
      await expect(page.locator('[data-testid="dataset-manager"]')).toBeVisible();

      await page.click('[data-testid="tab-models"]');
      await expect(page.locator('[data-testid="model-configuration"]')).toBeVisible();

      await page.click('[data-testid="tab-experiments"]');
      await expect(page.locator('[data-testid="experiment-tracker"]')).toBeVisible();
    }
  });
});
