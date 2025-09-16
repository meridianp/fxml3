/**
 * ReportsManager Component
 *
 * Comprehensive report management interface with creation, scheduling, and template management
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  ReportsService,
  getReportsService,
} from '@/services/reports';
import {
  ExportService,
  getExportService,
} from '@/services/export';
import {
  Report,
  ReportTemplate,
  ReportType,
  ReportStatus,
  ReportSchedule,
  ScheduleFrequency,
  DeliveryMethod,
  ReportParameters,
  TimeRange,
  TimeInterval,
  ExportFormat,
  ExportJob,
  AnalyticsCategory,
} from '@/types/analytics';

export interface ReportsManagerProps {
  className?: string;
  view?: ReportsManagerView;
  reportsService?: ReportsService;
  exportService?: ExportService;
  onReportCreate?: (report: Report) => void;
  onReportEdit?: (report: Report) => void;
  onReportDelete?: (reportId: string) => void;
  onReportGenerate?: (jobId: string) => void;
  onError?: (error: Error) => void;
}

export enum ReportsManagerView {
  LIST = 'list',
  CREATE = 'create',
  EDIT = 'edit',
  SCHEDULE = 'schedule',
  TEMPLATES = 'templates',
}

interface ReportsManagerState {
  loading: boolean;
  error: string | null;
  reports: Report[];
  templates: ReportTemplate[];
  selectedReport: Report | null;
  selectedTemplate: ReportTemplate | null;
  currentView: ReportsManagerView;
  editingReport: Partial<Report> | null;
  generatingReports: Set<string>;
  exportJobs: ExportJob[];
}

interface ReportFormData {
  name: string;
  description: string;
  type: ReportType;
  templateId: string;
  parameters: ReportParameters;
  schedule?: ReportSchedule;
}

export const ReportsManager: React.FC<ReportsManagerProps> = ({
  className = '',
  view = ReportsManagerView.LIST,
  reportsService,
  exportService,
  onReportCreate,
  onReportEdit,
  onReportDelete,
  onReportGenerate,
  onError,
}) => {
  const [services] = useState(() => ({
    reports: reportsService || getReportsService(),
    export: exportService || getExportService(),
  }));

  const [state, setState] = useState<ReportsManagerState>(() => ({
    loading: true,
    error: null,
    reports: [],
    templates: [],
    selectedReport: null,
    selectedTemplate: null,
    currentView: view,
    editingReport: null,
    generatingReports: new Set(),
    exportJobs: [],
  }));

  // Form state for report creation/editing
  const [formData, setFormData] = useState<ReportFormData>(() => ({
    name: '',
    description: '',
    type: ReportType.OPERATIONAL,
    templateId: '',
    parameters: {
      timeRange: {
        start: new Date(Date.now() - 24 * 60 * 60 * 1000),
        end: new Date(),
        interval: TimeInterval.HOUR,
      },
      filters: [],
      includeCharts: true,
      includeData: true,
      includeSummary: true,
    },
  }));

  // Load reports and templates
  const loadData = useCallback(async () => {
    setState(prev => ({ ...prev, loading: true, error: null }));

    try {
      const [reports, templates, exportJobs] = await Promise.all([
        services.reports.getReports(),
        services.reports.getTemplates(),
        services.export.getExportJobs(),
      ]);

      setState(prev => ({
        ...prev,
        loading: false,
        reports,
        templates,
        exportJobs: exportJobs.filter(job => job.type === 'report'),
      }));
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to load data';
      setState(prev => ({
        ...prev,
        loading: false,
        error: errorMessage,
      }));
      onError?.(error instanceof Error ? error : new Error(errorMessage));
    }
  }, [services, onError]);

  // Initial data load
  useEffect(() => {
    loadData();
  }, [loadData]);

  // Handle view changes
  const handleViewChange = useCallback((newView: ReportsManagerView) => {
    setState(prev => ({ ...prev, currentView: newView }));
  }, []);

  // Report CRUD operations
  const handleCreateReport = useCallback(async () => {
    if (!formData.name || !formData.templateId) {
      onError?.(new Error('Report name and template are required'));
      return;
    }

    try {
      const template = state.templates.find(t => t.id === formData.templateId);
      if (!template) {
        throw new Error('Selected template not found');
      }

      const reportData = {
        name: formData.name,
        description: formData.description,
        type: formData.type,
        template,
        parameters: formData.parameters,
        schedule: formData.schedule,
        createdBy: 'current-user', // This should come from auth context
      };

      const newReport = await services.reports.createReport(reportData);

      setState(prev => ({
        ...prev,
        reports: [newReport, ...prev.reports],
        currentView: ReportsManagerView.LIST,
      }));

      // Reset form
      setFormData({
        name: '',
        description: '',
        type: ReportType.OPERATIONAL,
        templateId: '',
        parameters: {
          timeRange: {
            start: new Date(Date.now() - 24 * 60 * 60 * 1000),
            end: new Date(),
            interval: TimeInterval.HOUR,
          },
          filters: [],
          includeCharts: true,
          includeData: true,
          includeSummary: true,
        },
      });

      onReportCreate?.(newReport);
    } catch (error) {
      onError?.(error instanceof Error ? error : new Error('Failed to create report'));
    }
  }, [formData, state.templates, services.reports, onReportCreate, onError]);

  const handleEditReport = useCallback(async (reportId: string, updates: Partial<Report>) => {
    try {
      const updatedReport = await services.reports.updateReport(reportId, updates);

      setState(prev => ({
        ...prev,
        reports: prev.reports.map(r => r.id === reportId ? updatedReport : r),
        selectedReport: updatedReport,
      }));

      onReportEdit?.(updatedReport);
    } catch (error) {
      onError?.(error instanceof Error ? error : new Error('Failed to update report'));
    }
  }, [services.reports, onReportEdit, onError]);

  const handleDeleteReport = useCallback(async (reportId: string) => {
    if (!window.confirm('Are you sure you want to delete this report?')) {
      return;
    }

    try {
      await services.reports.deleteReport(reportId);

      setState(prev => ({
        ...prev,
        reports: prev.reports.filter(r => r.id !== reportId),
        selectedReport: prev.selectedReport?.id === reportId ? null : prev.selectedReport,
      }));

      onReportDelete?.(reportId);
    } catch (error) {
      onError?.(error instanceof Error ? error : new Error('Failed to delete report'));
    }
  }, [services.reports, onReportDelete, onError]);

  // Report generation
  const handleGenerateReport = useCallback(async (reportId: string, parameters?: Partial<ReportParameters>) => {
    setState(prev => ({
      ...prev,
      generatingReports: new Set([...prev.generatingReports, reportId]),
    }));

    try {
      const exportJob = await services.reports.generateReport(reportId, parameters);

      setState(prev => ({
        ...prev,
        generatingReports: new Set([...prev.generatingReports].filter(id => id !== reportId)),
        exportJobs: [exportJob, ...prev.exportJobs],
      }));

      onReportGenerate?.(exportJob.id);
    } catch (error) {
      setState(prev => ({
        ...prev,
        generatingReports: new Set([...prev.generatingReports].filter(id => id !== reportId)),
      }));
      onError?.(error instanceof Error ? error : new Error('Failed to generate report'));
    }
  }, [services.reports, onReportGenerate, onError]);

  // Schedule management
  const handleScheduleReport = useCallback(async (reportId: string, schedule: ReportSchedule) => {
    try {
      const updatedReport = await services.reports.scheduleReport(reportId, schedule);

      setState(prev => ({
        ...prev,
        reports: prev.reports.map(r => r.id === reportId ? updatedReport : r),
        selectedReport: updatedReport,
      }));
    } catch (error) {
      onError?.(error instanceof Error ? error : new Error('Failed to schedule report'));
    }
  }, [services.reports, onError]);

  const handlePauseSchedule = useCallback(async (reportId: string) => {
    try {
      const updatedReport = await services.reports.pauseSchedule(reportId);

      setState(prev => ({
        ...prev,
        reports: prev.reports.map(r => r.id === reportId ? updatedReport : r),
      }));
    } catch (error) {
      onError?.(error instanceof Error ? error : new Error('Failed to pause schedule'));
    }
  }, [services.reports, onError]);

  const handleResumeSchedule = useCallback(async (reportId: string) => {
    try {
      const updatedReport = await services.reports.resumeSchedule(reportId);

      setState(prev => ({
        ...prev,
        reports: prev.reports.map(r => r.id === reportId ? updatedReport : r),
      }));
    } catch (error) {
      onError?.(error instanceof Error ? error : new Error('Failed to resume schedule'));
    }
  }, [services.reports, onError]);

  // Preview report
  const handlePreviewReport = useCallback(async (reportId: string) => {
    try {
      const preview = await services.reports.previewReport(reportId);
      // In a real implementation, this would open a preview modal or navigate to a preview page
      console.log('Report preview:', preview);
    } catch (error) {
      onError?.(error instanceof Error ? error : new Error('Failed to preview report'));
    }
  }, [services.reports, onError]);

  // Form validation
  const isFormValid = useMemo(() => {
    return formData.name.trim().length > 0 && formData.templateId.length > 0;
  }, [formData]);

  // Get status color for reports
  const getStatusColor = (status: ReportStatus) => {
    switch (status) {
      case ReportStatus.ACTIVE:
        return 'text-green-600 bg-green-100';
      case ReportStatus.PAUSED:
        return 'text-yellow-600 bg-yellow-100';
      case ReportStatus.DRAFT:
        return 'text-gray-600 bg-gray-100';
      case ReportStatus.ARCHIVED:
        return 'text-purple-600 bg-purple-100';
      case ReportStatus.ERROR:
        return 'text-red-600 bg-red-100';
      default:
        return 'text-gray-600 bg-gray-100';
    }
  };

  // Loading state
  if (state.loading) {
    return (
      <div className={`flex items-center justify-center h-64 ${className}`} data-testid="reports-manager-loading">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading reports manager...</p>
        </div>
      </div>
    );
  }

  // Error state
  if (state.error) {
    return (
      <div className={`bg-red-50 border border-red-200 rounded-lg p-6 ${className}`} data-testid="reports-manager-error">
        <div className="flex items-center space-x-3">
          <div className="text-red-600 text-xl">⚠️</div>
          <div>
            <h3 className="text-red-800 font-medium">Reports Manager Error</h3>
            <p className="text-red-600">{state.error}</p>
            <button
              onClick={loadData}
              className="mt-2 px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700"
            >
              Retry
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={`reports-manager space-y-6 ${className}`} data-testid="reports-manager">
      {/* Header and Navigation */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between space-y-4 sm:space-y-0">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Reports Manager</h2>
          <p className="text-gray-600">Create, schedule, and manage analytical reports</p>
        </div>

        <div className="flex items-center space-x-4">
          {/* View Navigation */}
          <div className="flex bg-gray-100 rounded-lg p-1" data-testid="view-navigation">
            <button
              onClick={() => handleViewChange(ReportsManagerView.LIST)}
              className={`px-3 py-2 rounded text-sm font-medium ${
                state.currentView === ReportsManagerView.LIST
                  ? 'bg-white text-blue-600 shadow'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
              data-testid="list-view-button"
            >
              Reports
            </button>
            <button
              onClick={() => handleViewChange(ReportsManagerView.TEMPLATES)}
              className={`px-3 py-2 rounded text-sm font-medium ${
                state.currentView === ReportsManagerView.TEMPLATES
                  ? 'bg-white text-blue-600 shadow'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
              data-testid="templates-view-button"
            >
              Templates
            </button>
          </div>

          <button
            onClick={() => handleViewChange(ReportsManagerView.CREATE)}
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
            data-testid="create-report-button"
          >
            Create Report
          </button>
        </div>
      </div>

      {/* Content Area */}
      <div className="bg-white rounded-lg shadow border">
        {/* Reports List View */}
        {state.currentView === ReportsManagerView.LIST && (
          <div data-testid="reports-list-view">
            <div className="px-6 py-4 border-b border-gray-200">
              <h3 className="text-lg font-medium text-gray-900">Reports ({state.reports.length})</h3>
            </div>

            {state.reports.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Report
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Type
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Status
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Schedule
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Last Run
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Actions
                      </th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {state.reports.map((report) => (
                      <tr
                        key={report.id}
                        className="hover:bg-gray-50"
                        data-testid={`report-row-${report.id}`}
                      >
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div>
                            <div className="text-sm font-medium text-gray-900">{report.name}</div>
                            <div className="text-sm text-gray-500">{report.description}</div>
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <span className="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-blue-100 text-blue-800">
                            {report.type}
                          </span>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <span className={`px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(report.status)}`}>
                            {report.status}
                          </span>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                          {report.schedule?.enabled ? (
                            <div>
                              <div>{report.schedule.frequency} ({report.schedule.interval}x)</div>
                              {report.nextExecution && (
                                <div className="text-xs text-gray-500">
                                  Next: {report.nextExecution.toLocaleString()}
                                </div>
                              )}
                            </div>
                          ) : (
                            <span className="text-gray-500">Manual</span>
                          )}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          {report.lastExecuted?.toLocaleString() || 'Never'}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm font-medium space-x-2">
                          <button
                            onClick={() => handleGenerateReport(report.id)}
                            disabled={state.generatingReports.has(report.id)}
                            className="text-blue-600 hover:text-blue-900 disabled:opacity-50"
                            data-testid={`generate-report-${report.id}`}
                          >
                            {state.generatingReports.has(report.id) ? 'Generating...' : 'Generate'}
                          </button>
                          <button
                            onClick={() => handlePreviewReport(report.id)}
                            className="text-green-600 hover:text-green-900"
                            data-testid={`preview-report-${report.id}`}
                          >
                            Preview
                          </button>
                          <button
                            onClick={() => {
                              setState(prev => ({ ...prev, selectedReport: report, currentView: ReportsManagerView.EDIT }));
                            }}
                            className="text-yellow-600 hover:text-yellow-900"
                            data-testid={`edit-report-${report.id}`}
                          >
                            Edit
                          </button>
                          {report.schedule?.enabled ? (
                            <button
                              onClick={() => handlePauseSchedule(report.id)}
                              className="text-orange-600 hover:text-orange-900"
                              data-testid={`pause-schedule-${report.id}`}
                            >
                              Pause
                            </button>
                          ) : report.schedule ? (
                            <button
                              onClick={() => handleResumeSchedule(report.id)}
                              className="text-green-600 hover:text-green-900"
                              data-testid={`resume-schedule-${report.id}`}
                            >
                              Resume
                            </button>
                          ) : null}
                          <button
                            onClick={() => handleDeleteReport(report.id)}
                            className="text-red-600 hover:text-red-900"
                            data-testid={`delete-report-${report.id}`}
                          >
                            Delete
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="text-center py-12" data-testid="no-reports-message">
                <div className="text-gray-400 text-6xl mb-4">📊</div>
                <h3 className="text-lg font-medium text-gray-900 mb-2">No reports yet</h3>
                <p className="text-gray-600 mb-4">Get started by creating your first report</p>
                <button
                  onClick={() => handleViewChange(ReportsManagerView.CREATE)}
                  className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
                >
                  Create Report
                </button>
              </div>
            )}
          </div>
        )}

        {/* Create Report View */}
        {state.currentView === ReportsManagerView.CREATE && (
          <div className="p-6" data-testid="create-report-view">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-lg font-medium text-gray-900">Create New Report</h3>
              <button
                onClick={() => handleViewChange(ReportsManagerView.LIST)}
                className="text-gray-600 hover:text-gray-900"
                data-testid="cancel-create-button"
              >
                Cancel
              </button>
            </div>

            <form className="space-y-6" data-testid="report-form">
              {/* Basic Information */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <label htmlFor="report-name" className="block text-sm font-medium text-gray-700 mb-2">
                    Report Name *
                  </label>
                  <input
                    id="report-name"
                    type="text"
                    value={formData.name}
                    onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
                    className="w-full rounded border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                    placeholder="Enter report name"
                    data-testid="report-name-input"
                  />
                </div>

                <div>
                  <label htmlFor="report-type" className="block text-sm font-medium text-gray-700 mb-2">
                    Report Type
                  </label>
                  <select
                    id="report-type"
                    value={formData.type}
                    onChange={(e) => setFormData(prev => ({ ...prev, type: e.target.value as ReportType }))}
                    className="w-full rounded border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                    data-testid="report-type-select"
                  >
                    {Object.values(ReportType).map(type => (
                      <option key={type} value={type}>
                        {type.replace('_', ' ').toUpperCase()}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div>
                <label htmlFor="report-description" className="block text-sm font-medium text-gray-700 mb-2">
                  Description
                </label>
                <textarea
                  id="report-description"
                  value={formData.description}
                  onChange={(e) => setFormData(prev => ({ ...prev, description: e.target.value }))}
                  rows={3}
                  className="w-full rounded border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                  placeholder="Enter report description"
                  data-testid="report-description-input"
                />
              </div>

              {/* Template Selection */}
              <div>
                <label htmlFor="report-template" className="block text-sm font-medium text-gray-700 mb-2">
                  Report Template *
                </label>
                <select
                  id="report-template"
                  value={formData.templateId}
                  onChange={(e) => setFormData(prev => ({ ...prev, templateId: e.target.value }))}
                  className="w-full rounded border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                  data-testid="template-select"
                >
                  <option value="">Select a template</option>
                  {state.templates.map(template => (
                    <option key={template.id} value={template.id}>
                      {template.name} - {template.description}
                    </option>
                  ))}
                </select>
              </div>

              {/* Parameters */}
              <div className="space-y-4">
                <h4 className="text-base font-medium text-gray-900">Report Parameters</h4>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div>
                    <label className="flex items-center">
                      <input
                        type="checkbox"
                        checked={formData.parameters.includeCharts}
                        onChange={(e) => setFormData(prev => ({
                          ...prev,
                          parameters: { ...prev.parameters, includeCharts: e.target.checked }
                        }))}
                        className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                        data-testid="include-charts-checkbox"
                      />
                      <span className="ml-2 text-sm text-gray-700">Include Charts</span>
                    </label>
                  </div>

                  <div>
                    <label className="flex items-center">
                      <input
                        type="checkbox"
                        checked={formData.parameters.includeData}
                        onChange={(e) => setFormData(prev => ({
                          ...prev,
                          parameters: { ...prev.parameters, includeData: e.target.checked }
                        }))}
                        className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                        data-testid="include-data-checkbox"
                      />
                      <span className="ml-2 text-sm text-gray-700">Include Data Tables</span>
                    </label>
                  </div>

                  <div>
                    <label className="flex items-center">
                      <input
                        type="checkbox"
                        checked={formData.parameters.includeSummary}
                        onChange={(e) => setFormData(prev => ({
                          ...prev,
                          parameters: { ...prev.parameters, includeSummary: e.target.checked }
                        }))}
                        className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                        data-testid="include-summary-checkbox"
                      />
                      <span className="ml-2 text-sm text-gray-700">Include Summary</span>
                    </label>
                  </div>
                </div>
              </div>

              {/* Actions */}
              <div className="flex justify-end space-x-4 pt-6 border-t border-gray-200">
                <button
                  type="button"
                  onClick={() => handleViewChange(ReportsManagerView.LIST)}
                  className="px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
                  data-testid="form-cancel-button"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleCreateReport}
                  disabled={!isFormValid}
                  className="px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                  data-testid="form-submit-button"
                >
                  Create Report
                </button>
              </div>
            </form>
          </div>
        )}

        {/* Templates View */}
        {state.currentView === ReportsManagerView.TEMPLATES && (
          <div data-testid="templates-view">
            <div className="px-6 py-4 border-b border-gray-200">
              <h3 className="text-lg font-medium text-gray-900">Report Templates ({state.templates.length})</h3>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 p-6">
              {state.templates.map(template => (
                <div key={template.id} className="border rounded-lg p-4" data-testid={`template-card-${template.id}`}>
                  <h4 className="text-lg font-medium text-gray-900 mb-2">{template.name}</h4>
                  <p className="text-sm text-gray-600 mb-4">{template.description}</p>

                  <div className="space-y-2 text-xs text-gray-500">
                    <div>Version: {template.version}</div>
                    <div>Sections: {template.sections.length}</div>
                    <div>Created: {template.createdAt.toLocaleDateString()}</div>
                  </div>

                  <div className="mt-4 flex space-x-2">
                    <button
                      onClick={() => {
                        setFormData(prev => ({ ...prev, templateId: template.id }));
                        handleViewChange(ReportsManagerView.CREATE);
                      }}
                      className="flex-1 px-3 py-2 bg-blue-600 text-white text-sm rounded hover:bg-blue-700"
                      data-testid={`use-template-${template.id}`}
                    >
                      Use Template
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Edit Report View */}
        {state.currentView === ReportsManagerView.EDIT && state.selectedReport && (
          <div className="p-6" data-testid="edit-report-view">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-lg font-medium text-gray-900">Edit Report: {state.selectedReport.name}</h3>
              <button
                onClick={() => handleViewChange(ReportsManagerView.LIST)}
                className="text-gray-600 hover:text-gray-900"
                data-testid="cancel-edit-button"
              >
                Cancel
              </button>
            </div>

            {/* Edit form would go here - simplified for this example */}
            <div className="space-y-4">
              <p className="text-gray-600">Report editing interface would be implemented here.</p>
              <p className="text-sm text-gray-500">This would include forms to edit all report properties, schedule settings, and parameters.</p>
            </div>
          </div>
        )}
      </div>

      {/* Recent Export Jobs */}
      {state.exportJobs.length > 0 && (
        <div className="bg-white rounded-lg shadow border" data-testid="export-jobs-section">
          <div className="px-6 py-4 border-b border-gray-200">
            <h3 className="text-lg font-medium text-gray-900">Recent Export Jobs</h3>
          </div>

          <div className="divide-y divide-gray-200">
            {state.exportJobs.slice(0, 5).map(job => (
              <div key={job.id} className="px-6 py-4 flex items-center justify-between" data-testid={`export-job-${job.id}`}>
                <div>
                  <div className="text-sm font-medium text-gray-900">{job.name}</div>
                  <div className="text-sm text-gray-500">
                    {job.format.toUpperCase()} • {job.createdAt.toLocaleString()}
                  </div>
                </div>
                <div className="flex items-center space-x-2">
                  <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                    job.status === 'completed' ? 'text-green-600 bg-green-100' :
                    job.status === 'failed' ? 'text-red-600 bg-red-100' :
                    job.status === 'processing' ? 'text-blue-600 bg-blue-100' :
                    'text-gray-600 bg-gray-100'
                  }`}>
                    {job.status}
                  </span>
                  {job.status === 'processing' && (
                    <div className="text-sm text-gray-500">{job.progress}%</div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
