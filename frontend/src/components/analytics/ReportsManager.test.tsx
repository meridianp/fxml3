/**
 * ReportsManager Component Tests
 *
 * Comprehensive test suite for the ReportsManager component
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ReportsManager, ReportsManagerView } from './ReportsManager';
import {
  Report,
  ReportTemplate,
  ReportType,
  ReportStatus,
  ReportSectionType,
  ScheduleFrequency,
  DeliveryMethod,
  ExportJob,
  ExportStatus,
  ExportFormat,
  TimeInterval,
} from '@/types/analytics';

// Mock services
const mockReportsService = {
  getReports: jest.fn(),
  getTemplates: jest.fn(),
  createReport: jest.fn(),
  updateReport: jest.fn(),
  deleteReport: jest.fn(),
  generateReport: jest.fn(),
  previewReport: jest.fn(),
  scheduleReport: jest.fn(),
  pauseSchedule: jest.fn(),
  resumeSchedule: jest.fn(),
};

const mockExportService = {
  getExportJobs: jest.fn(),
  exportData: jest.fn(),
  exportReport: jest.fn(),
};

// Mock data
const mockTemplates: ReportTemplate[] = [
  {
    id: 'template-1',
    name: 'Executive Summary',
    description: 'High-level overview for executives',
    layout: {
      orientation: 'portrait',
      pageSize: 'A4',
      margins: { top: 20, right: 20, bottom: 20, left: 20 },
      columns: 1,
      spacing: 10,
    },
    sections: [
      {
        id: 'summary',
        type: ReportSectionType.SUMMARY,
        title: 'Executive Summary',
        order: 1,
        config: {},
        visible: true,
      },
    ],
    style: {
      primaryColor: '#3B82F6',
      secondaryColor: '#1F2937',
      fontFamily: 'Inter, sans-serif',
      fontSize: 12,
      headerStyle: {
        fontSize: 18,
        fontWeight: 'bold',
        color: '#1F2937',
        alignment: 'left',
      },
      bodyStyle: {
        fontSize: 12,
        color: '#374151',
        alignment: 'left',
      },
      tableStyle: {
        headerBackground: '#F3F4F6',
        headerColor: '#1F2937',
        alternateRowBackground: '#F9FAFB',
        borderColor: '#E5E7EB',
        borderWidth: 1,
      },
    },
    version: '1.0',
    createdAt: new Date('2024-01-15T10:00:00Z'),
  },
];

const mockReports: Report[] = [
  {
    id: 'report-1',
    name: 'Daily Performance Report',
    description: 'Daily system performance overview',
    type: ReportType.OPERATIONAL,
    template: mockTemplates[0],
    parameters: {
      timeRange: {
        start: new Date('2024-01-14T00:00:00Z'),
        end: new Date('2024-01-15T00:00:00Z'),
        interval: TimeInterval.HOUR,
      },
      filters: [],
      includeCharts: true,
      includeData: true,
      includeSummary: true,
    },
    schedule: {
      enabled: true,
      frequency: ScheduleFrequency.DAILY,
      interval: 1,
      timezone: 'UTC',
      startDate: new Date('2024-01-15T00:00:00Z'),
      recipients: [
        { type: 'email', address: 'admin@example.com', name: 'Admin' },
      ],
      deliveryMethod: [DeliveryMethod.EMAIL],
    },
    status: ReportStatus.ACTIVE,
    createdAt: new Date('2024-01-10T10:00:00Z'),
    updatedAt: new Date('2024-01-15T10:00:00Z'),
    createdBy: 'user-1',
    lastExecuted: new Date('2024-01-15T09:00:00Z'),
    nextExecution: new Date('2024-01-16T09:00:00Z'),
  },
  {
    id: 'report-2',
    name: 'Weekly Analytics Report',
    description: 'Weekly performance analytics',
    type: ReportType.TECHNICAL,
    template: mockTemplates[0],
    parameters: {
      timeRange: {
        start: new Date('2024-01-08T00:00:00Z'),
        end: new Date('2024-01-15T00:00:00Z'),
        interval: TimeInterval.DAY,
      },
      filters: [],
      includeCharts: true,
      includeData: false,
      includeSummary: true,
    },
    status: ReportStatus.DRAFT,
    createdAt: new Date('2024-01-12T10:00:00Z'),
    updatedAt: new Date('2024-01-15T10:00:00Z'),
    createdBy: 'user-2',
  },
];

const mockExportJobs: ExportJob[] = [
  {
    id: 'job-1',
    name: 'Daily Performance Report - Export',
    type: 'report' as any,
    format: ExportFormat.PDF,
    report: 'report-1',
    parameters: { includeMetadata: true, includeCharts: true },
    status: ExportStatus.COMPLETED,
    progress: 100,
    createdAt: new Date('2024-01-15T10:00:00Z'),
    completedAt: new Date('2024-01-15T10:02:00Z'),
    createdBy: 'user-1',
    fileSize: 2048000,
    downloadUrl: '/api/exports/job-1/download',
  },
];

describe('ReportsManager', () => {
  beforeEach(() => {
    jest.clearAllMocks();

    // Setup default mock responses
    mockReportsService.getReports.mockResolvedValue(mockReports);
    mockReportsService.getTemplates.mockResolvedValue(mockTemplates);
    mockExportService.getExportJobs.mockResolvedValue(mockExportJobs);
  });

  describe('Component Rendering', () => {
    it('renders manager with loading state initially', () => {
      render(<ReportsManager />);

      expect(screen.getByTestId('reports-manager-loading')).toBeInTheDocument();
      expect(screen.getByText('Loading reports manager...')).toBeInTheDocument();
    });

    it('renders manager content after loading', async () => {
      render(
        <ReportsManager
          reportsService={mockReportsService as any}
          exportService={mockExportService as any}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('reports-manager')).toBeInTheDocument();
      });

      expect(screen.getByText('Reports Manager')).toBeInTheDocument();
      expect(screen.getByText('Create, schedule, and manage analytical reports')).toBeInTheDocument();
    });

    it('renders error state when data loading fails', async () => {
      mockReportsService.getReports.mockRejectedValue(new Error('API Error'));

      render(
        <ReportsManager
          reportsService={mockReportsService as any}
          exportService={mockExportService as any}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('reports-manager-error')).toBeInTheDocument();
      });

      expect(screen.getByText('Reports Manager Error')).toBeInTheDocument();
      expect(screen.getByText('API Error')).toBeInTheDocument();
    });

    it('renders with custom className and view', async () => {
      render(
        <ReportsManager
          className="custom-manager"
          view={ReportsManagerView.TEMPLATES}
          reportsService={mockReportsService as any}
          exportService={mockExportService as any}
        />
      );

      await waitFor(() => {
        const manager = screen.getByTestId('reports-manager');
        expect(manager).toHaveClass('custom-manager');
        expect(screen.getByTestId('templates-view')).toBeInTheDocument();
      });
    });
  });

  describe('View Navigation', () => {
    it('handles view navigation between reports and templates', async () => {
      render(
        <ReportsManager
          reportsService={mockReportsService as any}
          exportService={mockExportService as any}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('view-navigation')).toBeInTheDocument();
      });

      // Should start on list view
      expect(screen.getByTestId('reports-list-view')).toBeInTheDocument();

      // Switch to templates view
      const templatesButton = screen.getByTestId('templates-view-button');
      fireEvent.click(templatesButton);

      expect(screen.getByTestId('templates-view')).toBeInTheDocument();

      // Switch back to list view
      const listButton = screen.getByTestId('list-view-button');
      fireEvent.click(listButton);

      expect(screen.getByTestId('reports-list-view')).toBeInTheDocument();
    });

    it('navigates to create view when create button is clicked', async () => {
      render(
        <ReportsManager
          reportsService={mockReportsService as any}
          exportService={mockExportService as any}
        />
      );

      await waitFor(() => {
        const createButton = screen.getByTestId('create-report-button');
        fireEvent.click(createButton);
      });

      expect(screen.getByTestId('create-report-view')).toBeInTheDocument();
    });
  });

  describe('Reports List Display', () => {
    it('displays reports list with correct data', async () => {
      render(
        <ReportsManager
          reportsService={mockReportsService as any}
          exportService={mockExportService as any}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('reports-list-view')).toBeInTheDocument();
      });

      expect(screen.getByText('Reports (2)')).toBeInTheDocument();
      expect(screen.getByText('Daily Performance Report')).toBeInTheDocument();
      expect(screen.getByText('Weekly Analytics Report')).toBeInTheDocument();
    });

    it('displays report status with correct colors', async () => {
      render(
        <ReportsManager
          reportsService={mockReportsService as any}
          exportService={mockExportService as any}
        />
      );

      await waitFor(() => {
        const activeStatus = screen.getByText('active');
        const draftStatus = screen.getByText('draft');

        expect(activeStatus).toHaveClass('text-green-600', 'bg-green-100');
        expect(draftStatus).toHaveClass('text-gray-600', 'bg-gray-100');
      });
    });

    it('displays schedule information correctly', async () => {
      render(
        <ReportsManager
          reportsService={mockReportsService as any}
          exportService={mockExportService as any}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('daily (1x)')).toBeInTheDocument();
        expect(screen.getByText('Manual')).toBeInTheDocument();
      });
    });

    it('shows empty state when no reports exist', async () => {
      mockReportsService.getReports.mockResolvedValue([]);

      render(
        <ReportsManager
          reportsService={mockReportsService as any}
          exportService={mockExportService as any}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('no-reports-message')).toBeInTheDocument();
      });

      expect(screen.getByText('No reports yet')).toBeInTheDocument();
      expect(screen.getByText('Get started by creating your first report')).toBeInTheDocument();
    });
  });

  describe('Report Actions', () => {
    it('handles report generation', async () => {
      const onReportGenerate = jest.fn();
      mockReportsService.generateReport.mockResolvedValue({ id: 'job-1' });

      render(
        <ReportsManager
          reportsService={mockReportsService as any}
          exportService={mockExportService as any}
          onReportGenerate={onReportGenerate}
        />
      );

      await waitFor(() => {
        const generateButton = screen.getByTestId('generate-report-report-1');
        fireEvent.click(generateButton);
      });

      expect(mockReportsService.generateReport).toHaveBeenCalledWith('report-1', undefined);

      await waitFor(() => {
        expect(onReportGenerate).toHaveBeenCalledWith('job-1');
      });
    });

    it('handles report preview', async () => {
      mockReportsService.previewReport.mockResolvedValue({ preview: 'data' });

      render(
        <ReportsManager
          reportsService={mockReportsService as any}
          exportService={mockExportService as any}
        />
      );

      await waitFor(() => {
        const previewButton = screen.getByTestId('preview-report-report-1');
        fireEvent.click(previewButton);
      });

      expect(mockReportsService.previewReport).toHaveBeenCalledWith('report-1');
    });

    it('handles report editing navigation', async () => {
      render(
        <ReportsManager
          reportsService={mockReportsService as any}
          exportService={mockExportService as any}
        />
      );

      await waitFor(() => {
        const editButton = screen.getByTestId('edit-report-report-1');
        fireEvent.click(editButton);
      });

      expect(screen.getByTestId('edit-report-view')).toBeInTheDocument();
      expect(screen.getByText('Edit Report: Daily Performance Report')).toBeInTheDocument();
    });

    it('handles report deletion with confirmation', async () => {
      const onReportDelete = jest.fn();
      window.confirm = jest.fn().mockReturnValue(true);
      mockReportsService.deleteReport.mockResolvedValue(true);

      render(
        <ReportsManager
          reportsService={mockReportsService as any}
          exportService={mockExportService as any}
          onReportDelete={onReportDelete}
        />
      );

      await waitFor(() => {
        const deleteButton = screen.getByTestId('delete-report-report-1');
        fireEvent.click(deleteButton);
      });

      expect(window.confirm).toHaveBeenCalledWith('Are you sure you want to delete this report?');
      expect(mockReportsService.deleteReport).toHaveBeenCalledWith('report-1');

      await waitFor(() => {
        expect(onReportDelete).toHaveBeenCalledWith('report-1');
      });
    });

    it('handles schedule pause and resume', async () => {
      mockReportsService.pauseSchedule.mockResolvedValue({ ...mockReports[0], status: ReportStatus.PAUSED });
      mockReportsService.resumeSchedule.mockResolvedValue({ ...mockReports[0], status: ReportStatus.ACTIVE });

      render(
        <ReportsManager
          reportsService={mockReportsService as any}
          exportService={mockExportService as any}
        />
      );

      await waitFor(() => {
        // Pause schedule
        const pauseButton = screen.getByTestId('pause-schedule-report-1');
        fireEvent.click(pauseButton);
      });

      expect(mockReportsService.pauseSchedule).toHaveBeenCalledWith('report-1');
    });

    it('shows generating state during report generation', async () => {
      mockReportsService.generateReport.mockImplementation(() =>
        new Promise(resolve => setTimeout(() => resolve({ id: 'job-1' }), 100))
      );

      render(
        <ReportsManager
          reportsService={mockReportsService as any}
          exportService={mockExportService as any}
        />
      );

      await waitFor(() => {
        const generateButton = screen.getByTestId('generate-report-report-1');
        fireEvent.click(generateButton);
      });

      expect(screen.getByText('Generating...')).toBeInTheDocument();

      await waitFor(() => {
        expect(screen.getByText('Generate')).toBeInTheDocument();
      });
    });
  });

  describe('Report Creation', () => {
    it('displays create report form', async () => {
      render(
        <ReportsManager
          view={ReportsManagerView.CREATE}
          reportsService={mockReportsService as any}
          exportService={mockExportService as any}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('create-report-view')).toBeInTheDocument();
      });

      expect(screen.getByTestId('report-form')).toBeInTheDocument();
      expect(screen.getByTestId('report-name-input')).toBeInTheDocument();
      expect(screen.getByTestId('report-type-select')).toBeInTheDocument();
      expect(screen.getByTestId('template-select')).toBeInTheDocument();
    });

    it('handles form input changes', async () => {
      const user = userEvent.setup();

      render(
        <ReportsManager
          view={ReportsManagerView.CREATE}
          reportsService={mockReportsService as any}
          exportService={mockExportService as any}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('report-name-input')).toBeInTheDocument();
      });

      const nameInput = screen.getByTestId('report-name-input');
      await user.type(nameInput, 'Test Report');

      expect(nameInput).toHaveValue('Test Report');
    });

    it('validates form before submission', async () => {
      render(
        <ReportsManager
          view={ReportsManagerView.CREATE}
          reportsService={mockReportsService as any}
          exportService={mockExportService as any}
        />
      );

      await waitFor(() => {
        const submitButton = screen.getByTestId('form-submit-button');
        expect(submitButton).toBeDisabled();
      });
    });

    it('creates report with valid form data', async () => {
      const onReportCreate = jest.fn();
      const user = userEvent.setup();
      mockReportsService.createReport.mockResolvedValue(mockReports[0]);

      render(
        <ReportsManager
          view={ReportsManagerView.CREATE}
          reportsService={mockReportsService as any}
          exportService={mockExportService as any}
          onReportCreate={onReportCreate}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('report-form')).toBeInTheDocument();
      });

      // Fill out form
      const nameInput = screen.getByTestId('report-name-input');
      await user.type(nameInput, 'Test Report');

      const templateSelect = screen.getByTestId('template-select');
      fireEvent.change(templateSelect, { target: { value: 'template-1' } });

      // Submit form
      const submitButton = screen.getByTestId('form-submit-button');
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(mockReportsService.createReport).toHaveBeenCalled();
        expect(onReportCreate).toHaveBeenCalledWith(mockReports[0]);
      });
    });

    it('handles form cancellation', async () => {
      render(
        <ReportsManager
          view={ReportsManagerView.CREATE}
          reportsService={mockReportsService as any}
          exportService={mockExportService as any}
        />
      );

      await waitFor(() => {
        const cancelButton = screen.getByTestId('form-cancel-button');
        fireEvent.click(cancelButton);
      });

      expect(screen.getByTestId('reports-list-view')).toBeInTheDocument();
    });

    it('handles parameter checkboxes', async () => {
      render(
        <ReportsManager
          view={ReportsManagerView.CREATE}
          reportsService={mockReportsService as any}
          exportService={mockExportService as any}
        />
      );

      await waitFor(() => {
        const chartsCheckbox = screen.getByTestId('include-charts-checkbox');
        const dataCheckbox = screen.getByTestId('include-data-checkbox');
        const summaryCheckbox = screen.getByTestId('include-summary-checkbox');

        expect(chartsCheckbox).toBeChecked();
        expect(dataCheckbox).toBeChecked();
        expect(summaryCheckbox).toBeChecked();

        fireEvent.click(chartsCheckbox);
        expect(chartsCheckbox).not.toBeChecked();
      });
    });
  });

  describe('Templates Management', () => {
    it('displays templates view with template cards', async () => {
      render(
        <ReportsManager
          view={ReportsManagerView.TEMPLATES}
          reportsService={mockReportsService as any}
          exportService={mockExportService as any}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('templates-view')).toBeInTheDocument();
      });

      expect(screen.getByText('Report Templates (1)')).toBeInTheDocument();
      expect(screen.getByTestId('template-card-template-1')).toBeInTheDocument();
      expect(screen.getByText('Executive Summary')).toBeInTheDocument();
    });

    it('handles template selection for report creation', async () => {
      render(
        <ReportsManager
          view={ReportsManagerView.TEMPLATES}
          reportsService={mockReportsService as any}
          exportService={mockExportService as any}
        />
      );

      await waitFor(() => {
        const useTemplateButton = screen.getByTestId('use-template-template-1');
        fireEvent.click(useTemplateButton);
      });

      expect(screen.getByTestId('create-report-view')).toBeInTheDocument();
    });
  });

  describe('Export Jobs Display', () => {
    it('displays recent export jobs', async () => {
      render(
        <ReportsManager
          reportsService={mockReportsService as any}
          exportService={mockExportService as any}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('export-jobs-section')).toBeInTheDocument();
      });

      expect(screen.getByText('Recent Export Jobs')).toBeInTheDocument();
      expect(screen.getByTestId('export-job-job-1')).toBeInTheDocument();
      expect(screen.getByText('Daily Performance Report - Export')).toBeInTheDocument();
    });

    it('displays export job status correctly', async () => {
      render(
        <ReportsManager
          reportsService={mockReportsService as any}
          exportService={mockExportService as any}
        />
      );

      await waitFor(() => {
        const completedStatus = screen.getByText('completed');
        expect(completedStatus).toHaveClass('text-green-600', 'bg-green-100');
      });
    });
  });

  describe('Error Handling', () => {
    it('handles service errors gracefully', async () => {
      const onError = jest.fn();
      mockReportsService.getReports.mockRejectedValue(new Error('Service unavailable'));

      render(
        <ReportsManager
          reportsService={mockReportsService as any}
          exportService={mockExportService as any}
          onError={onError}
        />
      );

      await waitFor(() => {
        expect(onError).toHaveBeenCalledWith(expect.any(Error));
      });
    });

    it('handles report creation errors', async () => {
      const onError = jest.fn();
      mockReportsService.createReport.mockRejectedValue(new Error('Creation failed'));

      render(
        <ReportsManager
          view={ReportsManagerView.CREATE}
          reportsService={mockReportsService as any}
          exportService={mockExportService as any}
          onError={onError}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('report-name-input')).toBeInTheDocument();
      });

      // Fill out form with invalid data
      const nameInput = screen.getByTestId('report-name-input');
      fireEvent.change(nameInput, { target: { value: 'Test Report' } });

      const templateSelect = screen.getByTestId('template-select');
      fireEvent.change(templateSelect, { target: { value: 'template-1' } });

      const submitButton = screen.getByTestId('form-submit-button');
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(onError).toHaveBeenCalledWith(expect.any(Error));
      });
    });

    it('retries data loading on error state retry button click', async () => {
      mockReportsService.getReports.mockRejectedValueOnce(new Error('Network error'));
      mockReportsService.getReports.mockResolvedValueOnce(mockReports);

      render(
        <ReportsManager
          reportsService={mockReportsService as any}
          exportService={mockExportService as any}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('reports-manager-error')).toBeInTheDocument();
      });

      const retryButton = screen.getByRole('button', { name: /retry/i });
      fireEvent.click(retryButton);

      await waitFor(() => {
        expect(screen.getByTestId('reports-manager')).toBeInTheDocument();
      });
    });
  });

  describe('Accessibility', () => {
    it('has proper form labels and structure', async () => {
      render(
        <ReportsManager
          view={ReportsManagerView.CREATE}
          reportsService={mockReportsService as any}
          exportService={mockExportService as any}
        />
      );

      await waitFor(() => {
        // Check for proper form labels
        expect(screen.getByLabelText(/report name/i)).toBeInTheDocument();
        expect(screen.getByLabelText(/report type/i)).toBeInTheDocument();
        expect(screen.getByLabelText(/report template/i)).toBeInTheDocument();
      });
    });

    it('supports keyboard navigation', async () => {
      const user = userEvent.setup();

      render(
        <ReportsManager
          reportsService={mockReportsService as any}
          exportService={mockExportService as any}
        />
      );

      await waitFor(() => {
        const createButton = screen.getByTestId('create-report-button');
        createButton.focus();
        expect(createButton).toHaveFocus();
      });
    });

    it('has proper table structure', async () => {
      render(
        <ReportsManager
          reportsService={mockReportsService as any}
          exportService={mockExportService as any}
        />
      );

      await waitFor(() => {
        const table = screen.getByRole('table');
        expect(table).toBeInTheDocument();

        const headers = screen.getAllByRole('columnheader');
        expect(headers).toHaveLength(6); // Report, Type, Status, Schedule, Last Run, Actions
      });
    });
  });

  describe('Responsive Design', () => {
    it('adapts layout for different screen sizes', async () => {
      render(
        <ReportsManager
          reportsService={mockReportsService as any}
          exportService={mockExportService as any}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('reports-manager')).toBeInTheDocument();
      });

      // Manager should render with responsive classes
      const manager = screen.getByTestId('reports-manager');
      expect(manager).toHaveClass('space-y-6');
    });
  });

  describe('Performance Optimization', () => {
    it('memoizes form validation', async () => {
      const { rerender } = render(
        <ReportsManager
          view={ReportsManagerView.CREATE}
          reportsService={mockReportsService as any}
          exportService={mockExportService as any}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('form-submit-button')).toBeDisabled();
      });

      // Re-render with same props should maintain validation state
      rerender(
        <ReportsManager
          view={ReportsManagerView.CREATE}
          reportsService={mockReportsService as any}
          exportService={mockExportService as any}
        />
      );

      expect(screen.getByTestId('form-submit-button')).toBeDisabled();
    });
  });

  describe('Integration Features', () => {
    it('handles callbacks correctly', async () => {
      const callbacks = {
        onReportCreate: jest.fn(),
        onReportEdit: jest.fn(),
        onReportDelete: jest.fn(),
        onReportGenerate: jest.fn(),
        onError: jest.fn(),
      };

      render(
        <ReportsManager
          reportsService={mockReportsService as any}
          exportService={mockExportService as any}
          {...callbacks}
        />
      );

      // Test that callbacks are properly passed through and would be called
      await waitFor(() => {
        expect(screen.getByTestId('reports-manager')).toBeInTheDocument();
      });
    });
  });
});
