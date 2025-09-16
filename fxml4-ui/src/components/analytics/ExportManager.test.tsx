/**
 * ExportManager Component Tests
 *
 * Comprehensive test suite for the ExportManager component
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ExportManager, ExportManagerView, BulkAction } from './ExportManager';
import {
  ExportJob,
  ExportType,
  ExportFormat,
  ExportStatus,
} from '@/types/analytics';

// Mock services
const mockExportService = {
  getExportJobs: jest.fn(),
  getExportStatistics: jest.fn(),
  cancelExportJob: jest.fn(),
  downloadExport: jest.fn(),
  deleteExport: jest.fn(),
};

// Mock data
const mockExportJobs: ExportJob[] = [
  {
    id: 'job-1',
    name: 'Daily Report Export',
    type: ExportType.REPORT,
    format: ExportFormat.PDF,
    parameters: { includeMetadata: true, includeCharts: true },
    status: ExportStatus.COMPLETED,
    progress: 100,
    createdAt: new Date('2024-01-15T10:00:00Z'),
    startedAt: new Date('2024-01-15T10:00:30Z'),
    completedAt: new Date('2024-01-15T10:02:00Z'),
    createdBy: 'user-1',
    fileSize: 2048000,
    downloadUrl: '/api/exports/job-1/download',
  },
  {
    id: 'job-2',
    name: 'Data Export - Analytics',
    type: ExportType.DATA,
    format: ExportFormat.CSV,
    parameters: { includeMetadata: false, includeCharts: false },
    status: ExportStatus.PROCESSING,
    progress: 65,
    createdAt: new Date('2024-01-15T10:05:00Z'),
    startedAt: new Date('2024-01-15T10:05:15Z'),
    createdBy: 'user-2',
  },
  {
    id: 'job-3',
    name: 'Failed Export Test',
    type: ExportType.CHART,
    format: ExportFormat.PNG,
    parameters: { includeMetadata: true, chartResolution: 300 },
    status: ExportStatus.FAILED,
    progress: 45,
    createdAt: new Date('2024-01-15T09:30:00Z'),
    startedAt: new Date('2024-01-15T09:30:20Z'),
    createdBy: 'user-1',
    error: 'Processing timeout',
  },
  {
    id: 'job-4',
    name: 'Queued Export',
    type: ExportType.DASHBOARD,
    format: ExportFormat.EXCEL,
    parameters: { includeMetadata: true, includeCharts: true },
    status: ExportStatus.QUEUED,
    progress: 0,
    createdAt: new Date('2024-01-15T10:10:00Z'),
    createdBy: 'user-3',
  },
];

const mockStatistics = {
  totalJobs: 4,
  activeJobs: 2,
  completedJobs: 1,
  failedJobs: 1,
  totalSize: 2048000,
  averageSize: 512000,
  averageProcessingTime: 90000, // 1.5 minutes
  successRate: 0.75,
};

// Mock URL.createObjectURL and URL.revokeObjectURL
global.URL.createObjectURL = jest.fn(() => 'mock-url');
global.URL.revokeObjectURL = jest.fn();

describe('ExportManager', () => {
  beforeEach(() => {
    jest.clearAllMocks();

    // Setup default mock responses
    mockExportService.getExportJobs.mockResolvedValue(mockExportJobs);
    mockExportService.getExportStatistics.mockResolvedValue(mockStatistics);
    mockExportService.downloadExport.mockResolvedValue(new Blob(['test content']));
    mockExportService.cancelExportJob.mockResolvedValue(true);
    mockExportService.deleteExport.mockResolvedValue(true);
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  describe('Component Rendering', () => {
    it('renders manager with loading state initially', () => {
      render(<ExportManager />);

      expect(screen.getByTestId('export-manager-loading')).toBeInTheDocument();
      expect(screen.getByText('Loading export manager...')).toBeInTheDocument();
    });

    it('renders manager content after loading', async () => {
      render(
        <ExportManager
          exportService={mockExportService as any}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('export-manager')).toBeInTheDocument();
      });

      expect(screen.getByText('Export Manager')).toBeInTheDocument();
      expect(screen.getByText('Manage export jobs, downloads, and configurations')).toBeInTheDocument();
    });

    it('renders error state when data loading fails', async () => {
      mockExportService.getExportJobs.mockRejectedValue(new Error('API Error'));

      render(
        <ExportManager
          exportService={mockExportService as any}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('export-manager-error')).toBeInTheDocument();
      });

      expect(screen.getByText('Export Manager Error')).toBeInTheDocument();
      expect(screen.getByText('API Error')).toBeInTheDocument();
    });

    it('renders with custom view', async () => {
      render(
        <ExportManager
          view={ExportManagerView.SETTINGS}
          exportService={mockExportService as any}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('export-settings')).toBeInTheDocument();
      });
    });
  });

  describe('Statistics Display', () => {
    it('displays statistics cards with correct data', async () => {
      render(
        <ExportManager
          exportService={mockExportService as any}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('export-statistics')).toBeInTheDocument();
      });

      expect(screen.getByText('4')).toBeInTheDocument(); // Total jobs
      expect(screen.getByText('75.0%')).toBeInTheDocument(); // Success rate
      expect(screen.getByText('2.0 MB')).toBeInTheDocument(); // Total size
    });

    it('formats file sizes correctly', async () => {
      render(
        <ExportManager
          exportService={mockExportService as any}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('2.0 MB')).toBeInTheDocument();
      });
    });

    it('formats duration correctly', async () => {
      render(
        <ExportManager
          exportService={mockExportService as any}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('1m 30s')).toBeInTheDocument(); // Average processing time
      });
    });
  });

  describe('View Navigation', () => {
    it('handles view navigation between active, history, and settings', async () => {
      render(
        <ExportManager
          exportService={mockExportService as any}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('view-navigation')).toBeInTheDocument();
      });

      // Should start on active view by default
      expect(screen.getByTestId('jobs-table')).toBeInTheDocument();

      // Switch to settings view
      const settingsButton = screen.getByTestId('settings-view-button');
      fireEvent.click(settingsButton);

      expect(screen.getByTestId('export-settings')).toBeInTheDocument();

      // Switch back to active view
      const activeButton = screen.getByTestId('active-view-button');
      fireEvent.click(activeButton);

      expect(screen.getByTestId('jobs-table')).toBeInTheDocument();
    });

    it('shows active job count in navigation', async () => {
      render(
        <ExportManager
          exportService={mockExportService as any}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('Active (2)')).toBeInTheDocument();
      });
    });
  });

  describe('Jobs Table Display', () => {
    it('displays all export jobs with correct data', async () => {
      render(
        <ExportManager
          exportService={mockExportService as any}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('jobs-table')).toBeInTheDocument();
      });

      expect(screen.getByTestId('job-row-job-1')).toBeInTheDocument();
      expect(screen.getByTestId('job-row-job-2')).toBeInTheDocument();
      expect(screen.getByTestId('job-row-job-3')).toBeInTheDocument();
      expect(screen.getByTestId('job-row-job-4')).toBeInTheDocument();

      expect(screen.getByText('Daily Report Export')).toBeInTheDocument();
      expect(screen.getByText('Data Export - Analytics')).toBeInTheDocument();
      expect(screen.getByText('Failed Export Test')).toBeInTheDocument();
      expect(screen.getByText('Queued Export')).toBeInTheDocument();
    });

    it('displays job status with correct colors', async () => {
      render(
        <ExportManager
          exportService={mockExportService as any}
        />
      );

      await waitFor(() => {
        const completedStatus = screen.getByText('completed');
        const processingStatus = screen.getByText('processing');
        const failedStatus = screen.getByText('failed');
        const queuedStatus = screen.getByText('queued');

        expect(completedStatus).toHaveClass('text-green-600', 'bg-green-100');
        expect(processingStatus).toHaveClass('text-blue-600', 'bg-blue-100');
        expect(failedStatus).toHaveClass('text-red-600', 'bg-red-100');
        expect(queuedStatus).toHaveClass('text-yellow-600', 'bg-yellow-100');
      });
    });

    it('displays progress bars correctly', async () => {
      render(
        <ExportManager
          exportService={mockExportService as any}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('100%')).toBeInTheDocument(); // Completed job
        expect(screen.getByText('65%')).toBeInTheDocument(); // Processing job
        expect(screen.getByText('45%')).toBeInTheDocument(); // Failed job
        expect(screen.getByText('0%')).toBeInTheDocument(); // Queued job
      });
    });

    it('displays error messages for failed jobs', async () => {
      render(
        <ExportManager
          exportService={mockExportService as any}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('Error: Processing timeout...')).toBeInTheDocument();
      });
    });

    it('shows no jobs message when empty', async () => {
      mockExportService.getExportJobs.mockResolvedValue([]);
      mockExportService.getExportStatistics.mockResolvedValue({
        ...mockStatistics,
        totalJobs: 0,
        activeJobs: 0,
        completedJobs: 0,
        failedJobs: 0,
      });

      render(
        <ExportManager
          exportService={mockExportService as any}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('no-jobs-message')).toBeInTheDocument();
      });

      expect(screen.getByText('No export jobs found')).toBeInTheDocument();
      expect(screen.getByText('No export jobs have been created yet')).toBeInTheDocument();
    });
  });

  describe('Job Actions', () => {
    it('handles job download', async () => {
      render(
        <ExportManager
          exportService={mockExportService as any}
        />
      );

      await waitFor(() => {
        const downloadButton = screen.getByTestId('download-button-job-1');
        fireEvent.click(downloadButton);
      });

      expect(mockExportService.downloadExport).toHaveBeenCalledWith('job-1');
    });

    it('handles job cancellation', async () => {
      render(
        <ExportManager
          exportService={mockExportService as any}
        />
      );

      await waitFor(() => {
        const cancelButton = screen.getByTestId('cancel-button-job-2');
        fireEvent.click(cancelButton);
      });

      expect(mockExportService.cancelExportJob).toHaveBeenCalledWith('job-2');
    });

    it('handles job deletion', async () => {
      render(
        <ExportManager
          exportService={mockExportService as any}
        />
      );

      await waitFor(() => {
        const deleteButton = screen.getByTestId('delete-button-job-1');
        fireEvent.click(deleteButton);
      });

      expect(mockExportService.deleteExport).toHaveBeenCalledWith('job-1');
    });

    it('calls callbacks when jobs are acted upon', async () => {
      const callbacks = {
        onJobCancel: jest.fn(),
        onJobDownload: jest.fn(),
        onJobDelete: jest.fn(),
      };

      render(
        <ExportManager
          exportService={mockExportService as any}
          {...callbacks}
        />
      );

      await waitFor(() => {
        const downloadButton = screen.getByTestId('download-button-job-1');
        fireEvent.click(downloadButton);
      });

      await waitFor(() => {
        expect(callbacks.onJobDownload).toHaveBeenCalledWith('job-1');
      });
    });

    it('only shows appropriate actions based on job status', async () => {
      render(
        <ExportManager
          exportService={mockExportService as any}
        />
      );

      await waitFor(() => {
        // Completed job should have download button
        expect(screen.getByTestId('download-button-job-1')).toBeInTheDocument();

        // Processing job should have cancel button
        expect(screen.getByTestId('cancel-button-job-2')).toBeInTheDocument();

        // All jobs should have delete button
        expect(screen.getByTestId('delete-button-job-1')).toBeInTheDocument();
        expect(screen.getByTestId('delete-button-job-2')).toBeInTheDocument();
      });
    });
  });

  describe('Job Selection and Bulk Actions', () => {
    it('handles individual job selection', async () => {
      render(
        <ExportManager
          exportService={mockExportService as any}
        />
      );

      await waitFor(() => {
        const checkbox = screen.getByTestId('job-checkbox-job-1');
        fireEvent.click(checkbox);
      });

      expect(screen.getByTestId('bulk-actions')).toBeInTheDocument();
      expect(screen.getByText('1 selected')).toBeInTheDocument();
    });

    it('handles select all functionality', async () => {
      render(
        <ExportManager
          exportService={mockExportService as any}
        />
      );

      await waitFor(() => {
        const selectAllCheckbox = screen.getByTestId('select-all-checkbox');
        fireEvent.click(selectAllCheckbox);
      });

      expect(screen.getByText('4 selected')).toBeInTheDocument();
    });

    it('handles bulk cancel action', async () => {
      render(
        <ExportManager
          exportService={mockExportService as any}
        />
      );

      await waitFor(() => {
        // Select multiple jobs
        const checkbox1 = screen.getByTestId('job-checkbox-job-2');
        const checkbox2 = screen.getByTestId('job-checkbox-job-4');
        fireEvent.click(checkbox1);
        fireEvent.click(checkbox2);
      });

      const bulkCancelButton = screen.getByTestId('bulk-cancel-button');
      fireEvent.click(bulkCancelButton);

      await waitFor(() => {
        expect(mockExportService.cancelExportJob).toHaveBeenCalledWith('job-2');
        expect(mockExportService.cancelExportJob).toHaveBeenCalledWith('job-4');
      });
    });

    it('handles bulk delete action', async () => {
      const onBulkAction = jest.fn();

      render(
        <ExportManager
          exportService={mockExportService as any}
          onBulkAction={onBulkAction}
        />
      );

      await waitFor(() => {
        const checkbox = screen.getByTestId('job-checkbox-job-1');
        fireEvent.click(checkbox);
      });

      const bulkDeleteButton = screen.getByTestId('bulk-delete-button');
      fireEvent.click(bulkDeleteButton);

      await waitFor(() => {
        expect(mockExportService.deleteExport).toHaveBeenCalledWith('job-1');
        expect(onBulkAction).toHaveBeenCalledWith(BulkAction.DELETE, ['job-1']);
      });
    });
  });

  describe('Filtering and Searching', () => {
    it('filters jobs by status', async () => {
      render(
        <ExportManager
          exportService={mockExportService as any}
        />
      );

      await waitFor(() => {
        const statusFilter = screen.getByTestId('status-filter');
        fireEvent.change(statusFilter, { target: { value: ExportStatus.COMPLETED } });
      });

      // Should only show completed jobs
      expect(screen.getByTestId('job-row-job-1')).toBeInTheDocument();
      expect(screen.queryByTestId('job-row-job-2')).not.toBeInTheDocument();
      expect(screen.queryByTestId('job-row-job-3')).not.toBeInTheDocument();
      expect(screen.queryByTestId('job-row-job-4')).not.toBeInTheDocument();
    });

    it('filters jobs by format', async () => {
      render(
        <ExportManager
          exportService={mockExportService as any}
        />
      );

      await waitFor(() => {
        const formatFilter = screen.getByTestId('format-filter');
        fireEvent.change(formatFilter, { target: { value: ExportFormat.PDF } });
      });

      // Should only show PDF jobs
      expect(screen.getByTestId('job-row-job-1')).toBeInTheDocument();
      expect(screen.queryByTestId('job-row-job-2')).not.toBeInTheDocument();
    });

    it('searches jobs by name', async () => {
      const user = userEvent.setup();

      render(
        <ExportManager
          exportService={mockExportService as any}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('search-input')).toBeInTheDocument();
      });

      const searchInput = screen.getByTestId('search-input');
      await user.type(searchInput, 'Daily');

      // Should only show jobs matching search
      expect(screen.getByTestId('job-row-job-1')).toBeInTheDocument();
      expect(screen.queryByTestId('job-row-job-2')).not.toBeInTheDocument();
    });

    it('sorts jobs by different criteria', async () => {
      render(
        <ExportManager
          exportService={mockExportService as any}
        />
      );

      await waitFor(() => {
        const sortSelect = screen.getByTestId('sort-select');
        fireEvent.change(sortSelect, { target: { value: 'name' } });
      });

      const sortOrderButton = screen.getByTestId('sort-order-button');
      fireEvent.click(sortOrderButton);

      // Should change sort order indicator
      expect(sortOrderButton).toHaveTextContent('↑');
    });
  });

  describe('Settings View', () => {
    it('displays settings when settings view is selected', async () => {
      render(
        <ExportManager
          view={ExportManagerView.SETTINGS}
          exportService={mockExportService as any}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('export-settings')).toBeInTheDocument();
      });

      expect(screen.getByText('Export Settings')).toBeInTheDocument();
      expect(screen.getByText('Default Export Preferences')).toBeInTheDocument();
      expect(screen.getByText('Notification Settings')).toBeInTheDocument();
    });

    it('has working form controls in settings', async () => {
      render(
        <ExportManager
          view={ExportManagerView.SETTINGS}
          exportService={mockExportService as any}
        />
      );

      await waitFor(() => {
        const defaultFormatSelect = screen.getByTestId('default-format-select');
        const cleanupDaysInput = screen.getByTestId('cleanup-days-input');
        const notifyCompletionCheckbox = screen.getByTestId('notify-completion-checkbox');
        const notifyFailureCheckbox = screen.getByTestId('notify-failure-checkbox');

        expect(defaultFormatSelect).toBeInTheDocument();
        expect(cleanupDaysInput).toBeInTheDocument();
        expect(notifyCompletionCheckbox).toBeChecked();
        expect(notifyFailureCheckbox).toBeChecked();
      });
    });
  });

  describe('Auto-refresh Functionality', () => {
    beforeEach(() => {
      jest.useFakeTimers();
    });

    afterEach(() => {
      jest.useRealTimers();
    });

    it('auto-refreshes data at specified intervals', async () => {
      render(
        <ExportManager
          autoRefresh={true}
          refreshInterval={5000}
          exportService={mockExportService as any}
        />
      );

      // Wait for initial load
      await waitFor(() => {
        expect(mockExportService.getExportJobs).toHaveBeenCalledTimes(1);
      });

      // Fast-forward time to trigger refresh
      jest.advanceTimersByTime(5000);

      await waitFor(() => {
        expect(mockExportService.getExportJobs).toHaveBeenCalledTimes(2);
      });
    });

    it('does not auto-refresh when disabled', async () => {
      render(
        <ExportManager
          autoRefresh={false}
          exportService={mockExportService as any}
        />
      );

      // Wait for initial load
      await waitFor(() => {
        expect(mockExportService.getExportJobs).toHaveBeenCalledTimes(1);
      });

      // Fast-forward time
      jest.advanceTimersByTime(30000);

      // Should not have triggered additional calls
      expect(mockExportService.getExportJobs).toHaveBeenCalledTimes(1);
    });

    it('shows refreshing indicator during refresh', async () => {
      render(
        <ExportManager
          exportService={mockExportService as any}
        />
      );

      await waitFor(() => {
        const refreshButton = screen.getByTestId('refresh-button');
        fireEvent.click(refreshButton);
      });

      expect(screen.getByText('Refreshing...')).toBeInTheDocument();
    });
  });

  describe('Error Handling', () => {
    it('handles service errors gracefully', async () => {
      const onError = jest.fn();
      mockExportService.getExportJobs.mockRejectedValue(new Error('Service unavailable'));

      render(
        <ExportManager
          exportService={mockExportService as any}
          onError={onError}
        />
      );

      await waitFor(() => {
        expect(onError).toHaveBeenCalledWith(expect.any(Error));
      });
    });

    it('handles job action errors', async () => {
      const onError = jest.fn();
      mockExportService.downloadExport.mockRejectedValue(new Error('Download failed'));

      render(
        <ExportManager
          exportService={mockExportService as any}
          onError={onError}
        />
      );

      await waitFor(() => {
        const downloadButton = screen.getByTestId('download-button-job-1');
        fireEvent.click(downloadButton);
      });

      await waitFor(() => {
        expect(onError).toHaveBeenCalledWith(expect.any(Error));
      });
    });

    it('retries data loading on error state retry button click', async () => {
      mockExportService.getExportJobs.mockRejectedValueOnce(new Error('Network error'));
      mockExportService.getExportJobs.mockResolvedValueOnce(mockExportJobs);

      render(
        <ExportManager
          exportService={mockExportService as any}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('export-manager-error')).toBeInTheDocument();
      });

      const retryButton = screen.getByRole('button', { name: /retry/i });
      fireEvent.click(retryButton);

      await waitFor(() => {
        expect(screen.getByTestId('export-manager')).toBeInTheDocument();
      });
    });
  });

  describe('Job Selection Events', () => {
    it('calls onJobSelect when job name is clicked', async () => {
      const onJobSelect = jest.fn();

      render(
        <ExportManager
          exportService={mockExportService as any}
          onJobSelect={onJobSelect}
        />
      );

      await waitFor(() => {
        const jobName = screen.getByTestId('job-name-job-1');
        fireEvent.click(jobName);
      });

      expect(onJobSelect).toHaveBeenCalledWith(mockExportJobs[0]);
    });
  });

  describe('Accessibility', () => {
    it('has proper table structure', async () => {
      render(
        <ExportManager
          exportService={mockExportService as any}
        />
      );

      await waitFor(() => {
        const table = screen.getByRole('table');
        expect(table).toBeInTheDocument();

        const headers = screen.getAllByRole('columnheader');
        expect(headers).toHaveLength(9); // Including checkbox column
      });
    });

    it('supports keyboard navigation', async () => {
      render(
        <ExportManager
          exportService={mockExportService as any}
        />
      );

      await waitFor(() => {
        const refreshButton = screen.getByTestId('refresh-button');
        refreshButton.focus();
        expect(refreshButton).toHaveFocus();
      });
    });

    it('has proper form labels in settings', async () => {
      render(
        <ExportManager
          view={ExportManagerView.SETTINGS}
          exportService={mockExportService as any}
        />
      );

      await waitFor(() => {
        expect(screen.getByLabelText(/default format/i)).toBeInTheDocument();
        expect(screen.getByLabelText(/auto-cleanup after/i)).toBeInTheDocument();
      });
    });
  });

  describe('Performance Optimization', () => {
    it('memoizes filtered jobs calculation', async () => {
      const { rerender } = render(
        <ExportManager
          exportService={mockExportService as any}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('export-manager')).toBeInTheDocument();
      });

      const initialCallCount = mockExportService.getExportJobs.mock.calls.length;

      // Re-render with same props should not cause additional service calls
      rerender(
        <ExportManager
          exportService={mockExportService as any}
        />
      );

      // Should still have the same number of service calls
      expect(mockExportService.getExportJobs).toHaveBeenCalledTimes(initialCallCount);
    });
  });

  describe('Visibility Options', () => {
    it('hides completed jobs when showCompleted is false', async () => {
      render(
        <ExportManager
          showCompleted={false}
          exportService={mockExportService as any}
        />
      );

      await waitFor(() => {
        expect(screen.queryByTestId('job-row-job-1')).not.toBeInTheDocument(); // Completed job
        expect(screen.getByTestId('job-row-job-2')).toBeInTheDocument(); // Processing job
      });
    });

    it('hides failed jobs when showFailed is false', async () => {
      render(
        <ExportManager
          showFailed={false}
          exportService={mockExportService as any}
        />
      );

      await waitFor(() => {
        expect(screen.queryByTestId('job-row-job-3')).not.toBeInTheDocument(); // Failed job
        expect(screen.getByTestId('job-row-job-1')).toBeInTheDocument(); // Completed job
      });
    });
  });
});
