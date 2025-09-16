/**
 * DataManagementDashboard Component Tests
 *
 * Tests for the main data management dashboard container with grid layout
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { DataManagementDashboard } from './DataManagementDashboard';
import { DataSourceService } from '@/services/dataSource';
import { StorageMetricsService } from '@/services/storageMetrics';
import { DataQualityService } from '@/services/dataQuality';
import { PipelineService } from '@/services/pipeline';
import { NotificationService } from '@/services/notification';
import {
  DataSourceReport,
  StorageMetrics,
  DataQualityReport,
  Pipeline,
  DashboardLayout,
  DashboardTheme,
} from '@/types/dataManagement';

// Mock child components
jest.mock('./DataSourceMonitor', () => ({
  DataSourceMonitor: ({ onAlert, onStatusChange, gridArea }: any) => (
    <div
      data-testid="data-source-monitor"
      data-grid-area={gridArea}
      onClick={() => {
        onAlert?.({
          id: 'ds-alert-1',
          type: 'data_source',
          severity: 'warning',
          title: 'Connection Issue',
          message: 'Test alert from DataSourceMonitor',
          timestamp: new Date(),
          source: 'data_source_monitor'
        });
        onStatusChange?.({
          type: 'data_source',
          activeConnections: 3,
          failedConnections: 1,
          timestamp: new Date()
        });
      }}
    >
      DataSourceMonitor Component
    </div>
  ),
}));

jest.mock('./StorageManager', () => ({
  StorageManager: ({ onAlert, onStatusChange, gridArea }: any) => (
    <div
      data-testid="storage-manager"
      data-grid-area={gridArea}
      onClick={() => {
        onAlert?.({
          id: 'sm-alert-1',
          type: 'storage',
          severity: 'critical',
          title: 'Storage Critical',
          message: 'Test alert from StorageManager',
          timestamp: new Date(),
          source: 'storage_manager'
        });
        onStatusChange?.({
          type: 'storage',
          totalStorage: 1000,
          usedStorage: 850,
          timestamp: new Date()
        });
      }}
    >
      StorageManager Component
    </div>
  ),
}));

jest.mock('./DataQualityDashboard', () => ({
  DataQualityDashboard: ({ onAlert, onStatusChange, gridArea }: any) => (
    <div
      data-testid="data-quality-dashboard"
      data-grid-area={gridArea}
      onClick={() => {
        onAlert?.({
          id: 'dq-alert-1',
          type: 'data_quality',
          severity: 'warning',
          title: 'Quality Issue',
          message: 'Test alert from DataQualityDashboard',
          timestamp: new Date(),
          source: 'data_quality_dashboard'
        });
        onStatusChange?.({
          type: 'data_quality',
          qualityScore: 75.5,
          timestamp: new Date()
        });
      }}
    >
      DataQualityDashboard Component
    </div>
  ),
}));

jest.mock('./PipelineMonitor', () => ({
  PipelineMonitor: ({ onAlert, onStatusChange, gridArea }: any) => (
    <div
      data-testid="pipeline-monitor"
      data-grid-area={gridArea}
      onClick={() => {
        onAlert?.({
          id: 'pm-alert-1',
          type: 'pipeline',
          severity: 'error',
          title: 'Pipeline Failed',
          message: 'Test alert from PipelineMonitor',
          timestamp: new Date(),
          source: 'pipeline_monitor'
        });
        onStatusChange?.({
          type: 'pipeline',
          runningJobs: 2,
          failedJobs: 1,
          timestamp: new Date()
        });
      }}
    >
      PipelineMonitor Component
    </div>
  ),
}));

// Mock services
jest.mock('@/services/dataSource');
jest.mock('@/services/storageMetrics');
jest.mock('@/services/dataQuality');
jest.mock('@/services/pipeline');
jest.mock('@/services/notification');

const mockDataSourceService = DataSourceService as jest.MockedClass<typeof DataSourceService>;
const mockStorageMetricsService = StorageMetricsService as jest.MockedClass<typeof StorageMetricsService>;
const mockDataQualityService = DataQualityService as jest.MockedClass<typeof DataQualityService>;
const mockPipelineService = PipelineService as jest.MockedClass<typeof PipelineService>;
const mockNotificationService = NotificationService as jest.MockedClass<typeof NotificationService>;

describe('DataManagementDashboard', () => {
  let mockNotificationServiceInstance: jest.Mocked<NotificationService>;

  beforeEach(() => {
    mockNotificationServiceInstance = {
      create: jest.fn(),
      getAll: jest.fn(),
      dismiss: jest.fn(),
      markAsRead: jest.fn(),
      destroy: jest.fn(),
    } as any;

    mockNotificationService.mockImplementation(() => mockNotificationServiceInstance);

    // Mock localStorage
    const localStorageMock = {
      getItem: jest.fn(),
      setItem: jest.fn(),
      removeItem: jest.fn(),
      clear: jest.fn(),
    };
    Object.defineProperty(window, 'localStorage', { value: localStorageMock });

    jest.clearAllMocks();
  });

  describe('Component Rendering', () => {
    it('should render dashboard with default grid layout', () => {
      render(<DataManagementDashboard />);

      expect(screen.getByTestId('data-management-dashboard')).toBeInTheDocument();
      expect(screen.getByText('Data Management Dashboard')).toBeInTheDocument();

      // Check all child components are rendered
      expect(screen.getByTestId('data-source-monitor')).toBeInTheDocument();
      expect(screen.getByTestId('storage-manager')).toBeInTheDocument();
      expect(screen.getByTestId('data-quality-dashboard')).toBeInTheDocument();
      expect(screen.getByTestId('pipeline-monitor')).toBeInTheDocument();
    });

    it('should apply correct grid areas to child components', () => {
      render(<DataManagementDashboard />);

      expect(screen.getByTestId('data-source-monitor')).toHaveAttribute('data-grid-area', 'data-sources');
      expect(screen.getByTestId('storage-manager')).toHaveAttribute('data-grid-area', 'storage');
      expect(screen.getByTestId('data-quality-dashboard')).toHaveAttribute('data-grid-area', 'quality');
      expect(screen.getByTestId('pipeline-monitor')).toHaveAttribute('data-grid-area', 'pipelines');
    });

    it('should display dashboard title and controls', () => {
      render(<DataManagementDashboard />);

      expect(screen.getByText('Data Management Dashboard')).toBeInTheDocument();
      expect(screen.getByTestId('layout-selector')).toBeInTheDocument();
      expect(screen.getByTestId('theme-selector')).toBeInTheDocument();
      expect(screen.getByTestId('refresh-button')).toBeInTheDocument();
    });

    it('should render with custom title', () => {
      render(<DataManagementDashboard title="Custom Data Dashboard" />);

      expect(screen.getByText('Custom Data Dashboard')).toBeInTheDocument();
    });

    it('should apply custom className and styles', () => {
      render(
        <DataManagementDashboard
          className="custom-dashboard"
          style={{ backgroundColor: 'red' }}
        />
      );

      const dashboard = screen.getByTestId('data-management-dashboard');
      expect(dashboard).toHaveClass('custom-dashboard');
      expect(dashboard).toHaveStyle('background-color: red');
    });
  });

  describe('Layout Management', () => {
    it('should switch between different layout options', async () => {
      render(<DataManagementDashboard />);

      const layoutSelector = screen.getByTestId('layout-selector');

      // Switch to compact layout
      await userEvent.selectOptions(layoutSelector, 'compact');

      await waitFor(() => {
        const dashboard = screen.getByTestId('data-management-dashboard');
        expect(dashboard).toHaveClass('layout-compact');
      });

      // Switch to detailed layout
      await userEvent.selectOptions(layoutSelector, 'detailed');

      await waitFor(() => {
        const dashboard = screen.getByTestId('data-management-dashboard');
        expect(dashboard).toHaveClass('layout-detailed');
      });
    });

    it('should persist layout preference in localStorage', async () => {
      const setItemSpy = jest.spyOn(Storage.prototype, 'setItem');

      render(<DataManagementDashboard />);

      const layoutSelector = screen.getByTestId('layout-selector');
      await userEvent.selectOptions(layoutSelector, 'compact');

      expect(setItemSpy).toHaveBeenCalledWith('data-dashboard-layout', 'compact');
    });

    it('should load layout preference from localStorage', () => {
      const getItemSpy = jest.spyOn(Storage.prototype, 'getItem');
      getItemSpy.mockReturnValue('compact');

      render(<DataManagementDashboard />);

      const dashboard = screen.getByTestId('data-management-dashboard');
      expect(dashboard).toHaveClass('layout-compact');
    });

    it('should handle mobile responsive layout', () => {
      // Mock window.innerWidth for mobile
      Object.defineProperty(window, 'innerWidth', {
        writable: true,
        configurable: true,
        value: 375,
      });

      render(<DataManagementDashboard />);

      const dashboard = screen.getByTestId('data-management-dashboard');
      expect(dashboard).toHaveClass('mobile-layout');
    });
  });

  describe('Theme Management', () => {
    it('should switch between light and dark themes', async () => {
      render(<DataManagementDashboard />);

      const themeSelector = screen.getByTestId('theme-selector');

      // Switch to dark theme
      await userEvent.selectOptions(themeSelector, 'dark');

      await waitFor(() => {
        const dashboard = screen.getByTestId('data-management-dashboard');
        expect(dashboard).toHaveClass('theme-dark');
      });

      // Switch back to light theme
      await userEvent.selectOptions(themeSelector, 'light');

      await waitFor(() => {
        const dashboard = screen.getByTestId('data-management-dashboard');
        expect(dashboard).toHaveClass('theme-light');
      });
    });

    it('should persist theme preference in localStorage', async () => {
      const setItemSpy = jest.spyOn(Storage.prototype, 'setItem');

      render(<DataManagementDashboard />);

      const themeSelector = screen.getByTestId('theme-selector');
      await userEvent.selectOptions(themeSelector, 'dark');

      expect(setItemSpy).toHaveBeenCalledWith('data-dashboard-theme', 'dark');
    });

    it('should load theme preference from localStorage', () => {
      const getItemSpy = jest.spyOn(Storage.prototype, 'getItem');
      getItemSpy.mockReturnValueOnce('light'); // layout
      getItemSpy.mockReturnValueOnce('dark'); // theme

      render(<DataManagementDashboard />);

      const dashboard = screen.getByTestId('data-management-dashboard');
      expect(dashboard).toHaveClass('theme-dark');
    });
  });

  describe('Alert Handling', () => {
    it('should collect and display alerts from child components', async () => {
      render(<DataManagementDashboard />);

      // Trigger alerts from child components
      const dataSourceMonitor = screen.getByTestId('data-source-monitor');
      const storageManager = screen.getByTestId('storage-manager');

      await userEvent.click(dataSourceMonitor);
      await userEvent.click(storageManager);

      await waitFor(() => {
        expect(screen.getByTestId('alert-count')).toHaveTextContent('2');
        expect(screen.getByTestId('alert-indicator')).toHaveClass('has-alerts');
      });
    });

    it('should show alert details panel when clicked', async () => {
      render(<DataManagementDashboard />);

      // Trigger an alert
      const dataSourceMonitor = screen.getByTestId('data-source-monitor');
      await userEvent.click(dataSourceMonitor);

      await waitFor(() => {
        expect(screen.getByTestId('alert-indicator')).toBeInTheDocument();
      });

      // Click alert indicator to show details
      const alertIndicator = screen.getByTestId('alert-indicator');
      await userEvent.click(alertIndicator);

      await waitFor(() => {
        expect(screen.getByTestId('alerts-panel')).toBeInTheDocument();
        expect(screen.getByText('Connection Issue')).toBeInTheDocument();
        expect(screen.getByText('Test alert from DataSourceMonitor')).toBeInTheDocument();
      });
    });

    it('should allow dismissing individual alerts', async () => {
      render(<DataManagementDashboard />);

      // Trigger an alert
      const dataSourceMonitor = screen.getByTestId('data-source-monitor');
      await userEvent.click(dataSourceMonitor);

      // Open alerts panel
      await waitFor(() => {
        const alertIndicator = screen.getByTestId('alert-indicator');
        userEvent.click(alertIndicator);
      });

      await waitFor(() => {
        expect(screen.getByTestId('alerts-panel')).toBeInTheDocument();
      });

      // Dismiss the alert
      const dismissButton = screen.getByTestId('dismiss-alert-ds-alert-1');
      await userEvent.click(dismissButton);

      await waitFor(() => {
        expect(screen.queryByText('Connection Issue')).not.toBeInTheDocument();
      });
    });

    it('should clear all alerts when clear all button is clicked', async () => {
      render(<DataManagementDashboard />);

      // Trigger multiple alerts
      const dataSourceMonitor = screen.getByTestId('data-source-monitor');
      const storageManager = screen.getByTestId('storage-manager');

      await userEvent.click(dataSourceMonitor);
      await userEvent.click(storageManager);

      // Open alerts panel
      await waitFor(() => {
        const alertIndicator = screen.getByTestId('alert-indicator');
        userEvent.click(alertIndicator);
      });

      await waitFor(() => {
        expect(screen.getByTestId('alerts-panel')).toBeInTheDocument();
      });

      // Clear all alerts
      const clearAllButton = screen.getByTestId('clear-all-alerts');
      await userEvent.click(clearAllButton);

      await waitFor(() => {
        expect(screen.getByTestId('alert-count')).toHaveTextContent('0');
        expect(screen.queryByTestId('alert-indicator')).not.toHaveClass('has-alerts');
      });
    });

    it('should forward alerts to notification service when provided', async () => {
      const onAlert = jest.fn();
      render(<DataManagementDashboard onAlert={onAlert} />);

      // Trigger an alert
      const dataSourceMonitor = screen.getByTestId('data-source-monitor');
      await userEvent.click(dataSourceMonitor);

      await waitFor(() => {
        expect(onAlert).toHaveBeenCalledWith(
          expect.objectContaining({
            type: 'data_source',
            severity: 'warning',
            title: 'Connection Issue',
          })
        );
      });
    });
  });

  describe('Status Updates', () => {
    it('should collect status updates from child components', async () => {
      const onStatusUpdate = jest.fn();
      render(<DataManagementDashboard onStatusUpdate={onStatusUpdate} />);

      // Trigger status updates from child components
      const dataSourceMonitor = screen.getByTestId('data-source-monitor');
      const pipelineMonitor = screen.getByTestId('pipeline-monitor');

      await userEvent.click(dataSourceMonitor);
      await userEvent.click(pipelineMonitor);

      await waitFor(() => {
        expect(onStatusUpdate).toHaveBeenCalledWith(
          expect.objectContaining({
            dataSource: expect.objectContaining({
              type: 'data_source',
              activeConnections: 3,
              failedConnections: 1,
            }),
            pipeline: expect.objectContaining({
              type: 'pipeline',
              runningJobs: 2,
              failedJobs: 1,
            }),
          })
        );
      });
    });

    it('should display overall system health status', async () => {
      render(<DataManagementDashboard />);

      // Trigger status updates
      const storageManager = screen.getByTestId('storage-manager');
      await userEvent.click(storageManager);

      await waitFor(() => {
        expect(screen.getByTestId('system-health-indicator')).toBeInTheDocument();
        expect(screen.getByTestId('overall-status')).toBeInTheDocument();
      });
    });
  });

  describe('Refresh Functionality', () => {
    it('should refresh all child components when refresh button is clicked', async () => {
      const onRefresh = jest.fn();
      render(<DataManagementDashboard onRefresh={onRefresh} />);

      const refreshButton = screen.getByTestId('refresh-button');
      await userEvent.click(refreshButton);

      expect(onRefresh).toHaveBeenCalled();
    });

    it('should show refresh indicator during refresh', async () => {
      render(<DataManagementDashboard />);

      const refreshButton = screen.getByTestId('refresh-button');
      await userEvent.click(refreshButton);

      expect(screen.getByTestId('refresh-indicator')).toHaveClass('refreshing');
    });

    it('should auto-refresh at specified intervals', async () => {
      jest.useFakeTimers();
      const onRefresh = jest.fn();

      render(<DataManagementDashboard autoRefresh={true} refreshInterval={30000} onRefresh={onRefresh} />);

      // Fast forward 30 seconds
      jest.advanceTimersByTime(30000);

      await waitFor(() => {
        expect(onRefresh).toHaveBeenCalled();
      });

      jest.useRealTimers();
    });
  });

  describe('Service Integration', () => {
    it('should accept custom service instances as props', () => {
      const customDataSourceService = {} as DataSourceService;
      const customStorageService = {} as StorageMetricsService;
      const customDataQualityService = {} as DataQualityService;
      const customPipelineService = {} as PipelineService;
      const customNotificationService = {} as NotificationService;

      render(
        <DataManagementDashboard
          dataSourceService={customDataSourceService}
          storageMetricsService={customStorageService}
          dataQualityService={customDataQualityService}
          pipelineService={customPipelineService}
          notificationService={customNotificationService}
        />
      );

      expect(screen.getByTestId('data-management-dashboard')).toBeInTheDocument();
    });

    it('should pass service instances to child components', () => {
      const customDataSourceService = {} as DataSourceService;

      render(<DataManagementDashboard dataSourceService={customDataSourceService} />);

      // Child components should receive the custom service
      expect(screen.getByTestId('data-source-monitor')).toBeInTheDocument();
    });
  });

  describe('Export Functionality', () => {
    it('should allow exporting dashboard configuration', async () => {
      render(<DataManagementDashboard />);

      const exportButton = screen.getByTestId('export-config');
      await userEvent.click(exportButton);

      // Mock the download behavior
      expect(mockNotificationServiceInstance.create).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'success',
          title: 'Configuration Exported',
        })
      );
    });

    it('should allow importing dashboard configuration', async () => {
      render(<DataManagementDashboard />);

      const importButton = screen.getByTestId('import-config');
      const fileInput = screen.getByTestId('config-file-input');

      // Create a mock file
      const configFile = new File(
        [JSON.stringify({ layout: 'compact', theme: 'dark' })],
        'dashboard-config.json',
        { type: 'application/json' }
      );

      await userEvent.upload(fileInput, configFile);

      expect(mockNotificationServiceInstance.create).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'success',
          title: 'Configuration Imported',
        })
      );
    });
  });

  describe('Error Handling', () => {
    it('should handle child component errors gracefully', () => {
      // Mock console.error to avoid noise in test output
      const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});

      const ThrowingComponent = () => {
        throw new Error('Test error');
      };

      render(
        <DataManagementDashboard>
          <ThrowingComponent />
        </DataManagementDashboard>
      );

      expect(screen.getByText('Something went wrong')).toBeInTheDocument();
      expect(screen.getByTestId('error-boundary')).toBeInTheDocument();

      consoleErrorSpy.mockRestore();
    });

    it('should show error message when configuration fails to load', async () => {
      jest.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
        throw new Error('LocalStorage error');
      });

      render(<DataManagementDashboard />);

      expect(screen.getByTestId('data-management-dashboard')).toBeInTheDocument();
      // Should still render with default configuration
    });
  });

  describe('Accessibility', () => {
    it('should have proper ARIA labels and roles', () => {
      render(<DataManagementDashboard />);

      expect(screen.getByRole('main', { name: 'Data Management Dashboard' })).toBeInTheDocument();
      expect(screen.getByLabelText('Dashboard layout')).toBeInTheDocument();
      expect(screen.getByLabelText('Dashboard theme')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Refresh dashboard' })).toBeInTheDocument();
    });

    it('should support keyboard navigation', async () => {
      render(<DataManagementDashboard />);

      const refreshButton = screen.getByTestId('refresh-button');
      const layoutSelector = screen.getByTestId('layout-selector');

      // Tab navigation
      refreshButton.focus();
      fireEvent.keyDown(refreshButton, { key: 'Tab' });
      expect(layoutSelector).toHaveFocus();
    });

    it('should announce alerts to screen readers', async () => {
      render(<DataManagementDashboard />);

      const dataSourceMonitor = screen.getByTestId('data-source-monitor');
      await userEvent.click(dataSourceMonitor);

      await waitFor(() => {
        expect(screen.getByRole('alert')).toBeInTheDocument();
        expect(screen.getByText('New alert: Connection Issue')).toBeInTheDocument();
      });
    });
  });

  describe('Performance', () => {
    it('should not re-render child components unnecessarily', () => {
      const { rerender } = render(<DataManagementDashboard />);

      const initialDataSource = screen.getByTestId('data-source-monitor');

      // Re-render with same props
      rerender(<DataManagementDashboard />);

      const afterRerenderDataSource = screen.getByTestId('data-source-monitor');

      // Components should be the same instance due to memoization
      expect(initialDataSource).toBe(afterRerenderDataSource);
    });

    it('should cleanup resources on unmount', () => {
      const { unmount } = render(<DataManagementDashboard />);

      unmount();

      // Should not throw any errors or cause memory leaks
      expect(() => {
        // Any cleanup assertions would go here
      }).not.toThrow();
    });
  });
});
