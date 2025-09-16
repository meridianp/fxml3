/**
 * DataQualityDashboard Component Tests
 *
 * Tests for real-time data quality monitoring and validation dashboard
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { DataQualityDashboard } from './DataQualityDashboard';
import { DataQualityService } from '@/services/dataQuality';
import { NotificationService } from '@/services/notification';
import { DataQualityReport, ValidationRule, QualityLevel, AlertType } from '@/types/dataManagement';

// Mock services
jest.mock('@/services/dataQuality');
jest.mock('@/services/notification');
jest.mock('recharts', () => ({
  LineChart: ({ children }: any) => <div data-testid="line-chart">{children}</div>,
  Line: ({ dataKey }: any) => <div data-testid={`line-${dataKey}`} />,
  XAxis: () => <div data-testid="x-axis" />,
  YAxis: () => <div data-testid="y-axis" />,
  CartesianGrid: () => <div data-testid="cartesian-grid" />,
  Tooltip: () => <div data-testid="tooltip" />,
  Legend: () => <div data-testid="legend" />,
  ResponsiveContainer: ({ children }: any) => <div data-testid="responsive-container">{children}</div>,
  BarChart: ({ children }: any) => <div data-testid="bar-chart">{children}</div>,
  Bar: ({ dataKey }: any) => <div data-testid={`bar-${dataKey}`} />,
  PieChart: ({ children }: any) => <div data-testid="pie-chart">{children}</div>,
  Pie: ({ dataKey }: any) => <div data-testid={`pie-${dataKey}`} />,
  Cell: () => <div data-testid="pie-cell" />,
}));

const mockDataQualityService = DataQualityService as jest.MockedClass<typeof DataQualityService>;
const mockNotificationService = NotificationService as jest.MockedClass<typeof NotificationService>;

// Mock data
const mockDataQualityReport: DataQualityReport = {
  timestamp: new Date('2024-01-15T10:30:00Z'),
  overall: {
    score: 85.5,
    level: QualityLevel.GOOD,
    totalRecords: 1000000,
    validRecords: 855000,
    invalidRecords: 145000,
    completeness: 92.5,
    accuracy: 88.0,
    consistency: 78.5,
    timeliness: 95.0,
  },
  datasetMetrics: {
    market_data: {
      score: 90.2,
      level: QualityLevel.EXCELLENT,
      recordCount: 500000,
      validRecords: 451000,
      invalidRecords: 49000,
      completeness: 95.5,
      accuracy: 92.0,
      consistency: 88.5,
      timeliness: 98.0,
      lastUpdated: new Date('2024-01-15T10:29:00Z'),
    },
    features: {
      score: 78.5,
      level: QualityLevel.FAIR,
      recordCount: 300000,
      validRecords: 235500,
      invalidRecords: 64500,
      completeness: 88.0,
      accuracy: 82.5,
      consistency: 75.0,
      timeliness: 89.5,
      lastUpdated: new Date('2024-01-15T10:28:00Z'),
    },
    signals: {
      score: 92.8,
      level: QualityLevel.EXCELLENT,
      recordCount: 200000,
      validRecords: 185600,
      invalidRecords: 14400,
      completeness: 96.5,
      accuracy: 94.0,
      consistency: 91.5,
      timeliness: 99.0,
      lastUpdated: new Date('2024-01-15T10:30:00Z'),
    },
  },
  failedValidations: [
    {
      id: 'val-001',
      rule: 'price_range_check',
      dataset: 'market_data',
      field: 'close_price',
      message: 'Price outside expected range (0.0001-10000)',
      severity: 'warning',
      count: 156,
      samples: [
        { recordId: 'md-001', value: 0.00005, expected: '>= 0.0001' },
        { recordId: 'md-002', value: 12500.0, expected: '<= 10000' },
      ],
    },
    {
      id: 'val-002',
      rule: 'timestamp_freshness',
      dataset: 'features',
      field: 'created_at',
      message: 'Stale data detected (older than 1 hour)',
      severity: 'error',
      count: 4532,
      samples: [
        { recordId: 'feat-001', value: '2024-01-15T08:15:00Z', expected: '> 2024-01-15T09:30:00Z' },
        { recordId: 'feat-002', value: '2024-01-15T07:45:00Z', expected: '> 2024-01-15T09:30:00Z' },
      ],
    },
  ],
  trends: [
    {
      timestamp: '2024-01-15T09:30:00Z',
      overallScore: 82.1,
      completeness: 90.2,
      accuracy: 85.5,
      consistency: 76.8,
      timeliness: 96.0,
    },
    {
      timestamp: '2024-01-15T10:00:00Z',
      overallScore: 84.2,
      completeness: 91.5,
      accuracy: 87.0,
      consistency: 77.5,
      timeliness: 95.5,
    },
    {
      timestamp: '2024-01-15T10:30:00Z',
      overallScore: 85.5,
      completeness: 92.5,
      accuracy: 88.0,
      consistency: 78.5,
      timeliness: 95.0,
    },
  ],
};

const mockValidationRules: ValidationRule[] = [
  {
    id: 'price_range_check',
    name: 'Price Range Validation',
    description: 'Ensures price values are within expected ranges',
    dataset: 'market_data',
    field: 'close_price',
    type: 'range',
    parameters: { min: 0.0001, max: 10000 },
    severity: 'warning',
    enabled: true,
    createdAt: new Date('2024-01-01T00:00:00Z'),
    updatedAt: new Date('2024-01-15T10:00:00Z'),
  },
  {
    id: 'timestamp_freshness',
    name: 'Data Freshness Check',
    description: 'Validates data is not older than specified threshold',
    dataset: 'features',
    field: 'created_at',
    type: 'freshness',
    parameters: { maxAge: '1h' },
    severity: 'error',
    enabled: true,
    createdAt: new Date('2024-01-01T00:00:00Z'),
    updatedAt: new Date('2024-01-15T09:30:00Z'),
  },
  {
    id: 'symbol_format_check',
    name: 'Symbol Format Validation',
    description: 'Ensures trading symbols follow correct format',
    dataset: 'market_data',
    field: 'symbol',
    type: 'regex',
    parameters: { pattern: '^[A-Z]{6}$' },
    severity: 'error',
    enabled: false,
    createdAt: new Date('2024-01-01T00:00:00Z'),
    updatedAt: new Date('2024-01-10T15:30:00Z'),
  },
];

describe('DataQualityDashboard', () => {
  let mockDataQualityServiceInstance: jest.Mocked<DataQualityService>;
  let mockNotificationServiceInstance: jest.Mocked<NotificationService>;

  beforeEach(() => {
    mockDataQualityServiceInstance = {
      getQualityReport: jest.fn(),
      getQualityHistory: jest.fn(),
      getValidationRules: jest.fn(),
      createValidationRule: jest.fn(),
      updateValidationRule: jest.fn(),
      deleteValidationRule: jest.fn(),
      runValidation: jest.fn(),
      getDatasetQuality: jest.fn(),
      getFieldQuality: jest.fn(),
      generateQualityReport: jest.fn(),
      exportReport: jest.fn(),
      setQualityThresholds: jest.fn(),
      getQualityAlerts: jest.fn(),
      acknowledgeAlert: jest.fn(),
      startRealTimeMonitoring: jest.fn(),
      stopRealTimeMonitoring: jest.fn(),
      subscribeToUpdates: jest.fn(),
      unsubscribeFromUpdates: jest.fn(),
      destroy: jest.fn(),
    } as any;

    mockNotificationServiceInstance = {
      create: jest.fn(),
      getAll: jest.fn(),
      dismiss: jest.fn(),
      markAsRead: jest.fn(),
      destroy: jest.fn(),
    } as any;

    mockDataQualityService.mockImplementation(() => mockDataQualityServiceInstance);
    mockNotificationService.mockImplementation(() => mockNotificationServiceInstance);

    jest.clearAllMocks();
  });

  describe('Component Rendering', () => {
    it('should render data quality dashboard with loading state initially', () => {
      mockDataQualityServiceInstance.getQualityReport.mockResolvedValue(mockDataQualityReport);

      render(<DataQualityDashboard />);

      expect(screen.getByText('Data Quality Dashboard')).toBeInTheDocument();
      expect(screen.getByText('Loading...')).toBeInTheDocument();
    });

    it('should render quality metrics after loading', async () => {
      mockDataQualityServiceInstance.getQualityReport.mockResolvedValue(mockDataQualityReport);
      mockDataQualityServiceInstance.getQualityHistory.mockResolvedValue(mockDataQualityReport.trends);

      render(<DataQualityDashboard />);

      await waitFor(() => {
        expect(screen.getByText('Overall Quality Score')).toBeInTheDocument();
        expect(screen.getByText('Dataset Quality')).toBeInTheDocument();
        expect(screen.getByText('Failed Validations')).toBeInTheDocument();
      });
    });

    it('should display overall quality score correctly', async () => {
      mockDataQualityServiceInstance.getQualityReport.mockResolvedValue(mockDataQualityReport);
      mockDataQualityServiceInstance.getQualityHistory.mockResolvedValue(mockDataQualityReport.trends);

      render(<DataQualityDashboard />);

      await waitFor(() => {
        expect(screen.getByTestId('overall-quality-score')).toHaveTextContent('85.5');
        expect(screen.getByTestId('quality-level')).toHaveTextContent('Good');
        expect(screen.getByTestId('total-records')).toHaveTextContent('1,000,000');
        expect(screen.getByTestId('valid-records')).toHaveTextContent('855,000');
      });
    });

    it('should display quality dimensions correctly', async () => {
      mockDataQualityServiceInstance.getQualityReport.mockResolvedValue(mockDataQualityReport);
      mockDataQualityServiceInstance.getQualityHistory.mockResolvedValue(mockDataQualityReport.trends);

      render(<DataQualityDashboard />);

      await waitFor(() => {
        expect(screen.getByTestId('completeness-score')).toHaveTextContent('92.5%');
        expect(screen.getByTestId('accuracy-score')).toHaveTextContent('88.0%');
        expect(screen.getByTestId('consistency-score')).toHaveTextContent('78.5%');
        expect(screen.getByTestId('timeliness-score')).toHaveTextContent('95.0%');
      });
    });

    it('should display dataset quality metrics', async () => {
      mockDataQualityServiceInstance.getQualityReport.mockResolvedValue(mockDataQualityReport);
      mockDataQualityServiceInstance.getQualityHistory.mockResolvedValue(mockDataQualityReport.trends);

      render(<DataQualityDashboard />);

      await waitFor(() => {
        expect(screen.getByTestId('dataset-market_data')).toBeInTheDocument();
        expect(screen.getByTestId('dataset-features')).toBeInTheDocument();
        expect(screen.getByTestId('dataset-signals')).toBeInTheDocument();
      });
    });

    it('should render quality trend charts', async () => {
      mockDataQualityServiceInstance.getQualityReport.mockResolvedValue(mockDataQualityReport);
      mockDataQualityServiceInstance.getQualityHistory.mockResolvedValue(mockDataQualityReport.trends);

      render(<DataQualityDashboard />);

      await waitFor(() => {
        expect(screen.getByTestId('quality-trends-chart')).toBeInTheDocument();
        expect(screen.getByTestId('line-chart')).toBeInTheDocument();
        expect(screen.getByTestId('line-overallScore')).toBeInTheDocument();
        expect(screen.getByTestId('line-completeness')).toBeInTheDocument();
      });
    });

    it('should render dataset distribution chart', async () => {
      mockDataQualityServiceInstance.getQualityReport.mockResolvedValue(mockDataQualityReport);
      mockDataQualityServiceInstance.getQualityHistory.mockResolvedValue(mockDataQualityReport.trends);

      render(<DataQualityDashboard />);

      await waitFor(() => {
        expect(screen.getByTestId('dataset-distribution-chart')).toBeInTheDocument();
        expect(screen.getByTestId('pie-chart')).toBeInTheDocument();
        expect(screen.getByTestId('pie-score')).toBeInTheDocument();
      });
    });
  });

  describe('Interactive Features', () => {
    it('should allow switching between chart time ranges', async () => {
      mockDataQualityServiceInstance.getQualityReport.mockResolvedValue(mockDataQualityReport);
      mockDataQualityServiceInstance.getQualityHistory.mockResolvedValue(mockDataQualityReport.trends);

      render(<DataQualityDashboard />);

      await waitFor(() => {
        expect(screen.getByText('Data Quality Dashboard')).toBeInTheDocument();
      });

      // Switch to 24h view
      const timeRangeSelect = screen.getByLabelText('Time range');
      await userEvent.selectOptions(timeRangeSelect, '24h');

      expect(mockDataQualityServiceInstance.getQualityHistory).toHaveBeenCalledWith(
        expect.objectContaining({
          interval: '1h',
        })
      );
    });

    it('should allow filtering datasets', async () => {
      mockDataQualityServiceInstance.getQualityReport.mockResolvedValue(mockDataQualityReport);
      mockDataQualityServiceInstance.getQualityHistory.mockResolvedValue(mockDataQualityReport.trends);

      render(<DataQualityDashboard />);

      await waitFor(() => {
        expect(screen.getByTestId('dataset-market_data')).toBeInTheDocument();
        expect(screen.getByTestId('dataset-features')).toBeInTheDocument();
      });

      // Filter to show only market_data
      const datasetFilter = screen.getByLabelText('Filter datasets');
      await userEvent.selectOptions(datasetFilter, 'market_data');

      await waitFor(() => {
        expect(screen.getByTestId('dataset-market_data')).toBeInTheDocument();
        expect(screen.queryByTestId('dataset-features')).not.toBeInTheDocument();
      });
    });

    it('should show validation failures when section is expanded', async () => {
      mockDataQualityServiceInstance.getQualityReport.mockResolvedValue(mockDataQualityReport);
      mockDataQualityServiceInstance.getQualityHistory.mockResolvedValue(mockDataQualityReport.trends);

      render(<DataQualityDashboard />);

      await waitFor(() => {
        expect(screen.getByText('Failed Validations')).toBeInTheDocument();
      });

      // Expand validation failures section
      const expandButton = screen.getByTestId('expand-validation-failures');
      await userEvent.click(expandButton);

      await waitFor(() => {
        expect(screen.getByText('Price Range Validation')).toBeInTheDocument();
        expect(screen.getByText('Price outside expected range')).toBeInTheDocument();
        expect(screen.getByText('156 failures')).toBeInTheDocument();
      });
    });

    it('should allow running manual validation', async () => {
      const mockValidationResult = {
        success: true,
        validatedRecords: 50000,
        failedRecords: 123,
        executionTime: 2500,
      };

      mockDataQualityServiceInstance.getQualityReport.mockResolvedValue(mockDataQualityReport);
      mockDataQualityServiceInstance.runValidation.mockResolvedValue(mockValidationResult);

      render(<DataQualityDashboard />);

      await waitFor(() => {
        expect(screen.getByText('Data Quality Dashboard')).toBeInTheDocument();
      });

      // Click run validation button
      const runValidationButton = screen.getByTestId('run-validation');
      await userEvent.click(runValidationButton);

      expect(mockDataQualityServiceInstance.runValidation).toHaveBeenCalledWith({
        datasets: ['all'],
        rules: ['all'],
      });

      await waitFor(() => {
        expect(mockNotificationServiceInstance.create).toHaveBeenCalledWith({
          type: 'success',
          title: 'Validation Complete',
          message: 'Validated 50,000 records with 123 failures in 2.5s',
        });
      });
    });

    it('should allow exporting quality report', async () => {
      mockDataQualityServiceInstance.getQualityReport.mockResolvedValue(mockDataQualityReport);
      mockDataQualityServiceInstance.exportReport.mockResolvedValue({
        format: 'pdf',
        filename: 'quality-report-2024-01-15.pdf',
        size: 245760,
      });

      render(<DataQualityDashboard />);

      await waitFor(() => {
        expect(screen.getByText('Data Quality Dashboard')).toBeInTheDocument();
      });

      // Click export report button
      const exportButton = screen.getByTestId('export-report');
      await userEvent.click(exportButton);

      expect(mockDataQualityServiceInstance.exportReport).toHaveBeenCalledWith({
        format: 'pdf',
        includeCharts: true,
        includeDetails: true,
      });

      await waitFor(() => {
        expect(mockNotificationServiceInstance.create).toHaveBeenCalledWith({
          type: 'success',
          title: 'Report Exported',
          message: 'Quality report exported as quality-report-2024-01-15.pdf (240 KB)',
        });
      });
    });
  });

  describe('Validation Rules Management', () => {
    it('should display validation rules when management section is opened', async () => {
      mockDataQualityServiceInstance.getQualityReport.mockResolvedValue(mockDataQualityReport);
      mockDataQualityServiceInstance.getValidationRules.mockResolvedValue(mockValidationRules);

      render(<DataQualityDashboard />);

      await waitFor(() => {
        expect(screen.getByText('Data Quality Dashboard')).toBeInTheDocument();
      });

      // Open validation rules management
      const manageRulesButton = screen.getByTestId('manage-validation-rules');
      await userEvent.click(manageRulesButton);

      await waitFor(() => {
        expect(screen.getByText('Validation Rules')).toBeInTheDocument();
        expect(screen.getByText('Price Range Validation')).toBeInTheDocument();
        expect(screen.getByText('Data Freshness Check')).toBeInTheDocument();
        expect(screen.getByText('Symbol Format Validation')).toBeInTheDocument();
      });
    });

    it('should allow enabling/disabling validation rules', async () => {
      mockDataQualityServiceInstance.getQualityReport.mockResolvedValue(mockDataQualityReport);
      mockDataQualityServiceInstance.getValidationRules.mockResolvedValue(mockValidationRules);
      mockDataQualityServiceInstance.updateValidationRule.mockResolvedValue({
        ...mockValidationRules[2],
        enabled: true,
      });

      render(<DataQualityDashboard />);

      await waitFor(() => {
        expect(screen.getByText('Data Quality Dashboard')).toBeInTheDocument();
      });

      // Open validation rules management
      const manageRulesButton = screen.getByTestId('manage-validation-rules');
      await userEvent.click(manageRulesButton);

      await waitFor(() => {
        expect(screen.getByText('Symbol Format Validation')).toBeInTheDocument();
      });

      // Toggle disabled rule to enabled
      const enableButton = screen.getByTestId('toggle-rule-symbol_format_check');
      await userEvent.click(enableButton);

      expect(mockDataQualityServiceInstance.updateValidationRule).toHaveBeenCalledWith(
        'symbol_format_check',
        expect.objectContaining({
          enabled: true,
        })
      );
    });

    it('should allow creating new validation rules', async () => {
      const newRule: ValidationRule = {
        id: 'volume_range_check',
        name: 'Volume Range Validation',
        description: 'Ensures volume values are positive',
        dataset: 'market_data',
        field: 'volume',
        type: 'range',
        parameters: { min: 0 },
        severity: 'warning',
        enabled: true,
        createdAt: new Date(),
        updatedAt: new Date(),
      };

      mockDataQualityServiceInstance.getQualityReport.mockResolvedValue(mockDataQualityReport);
      mockDataQualityServiceInstance.getValidationRules.mockResolvedValue(mockValidationRules);
      mockDataQualityServiceInstance.createValidationRule.mockResolvedValue(newRule);

      render(<DataQualityDashboard />);

      await waitFor(() => {
        expect(screen.getByText('Data Quality Dashboard')).toBeInTheDocument();
      });

      // Open validation rules management
      const manageRulesButton = screen.getByTestId('manage-validation-rules');
      await userEvent.click(manageRulesButton);

      await waitFor(() => {
        expect(screen.getByText('Validation Rules')).toBeInTheDocument();
      });

      // Click create new rule button
      const createRuleButton = screen.getByTestId('create-validation-rule');
      await userEvent.click(createRuleButton);

      // Fill in rule form
      const nameInput = screen.getByLabelText('Rule Name');
      const descriptionInput = screen.getByLabelText('Description');
      const datasetSelect = screen.getByLabelText('Dataset');
      const fieldInput = screen.getByLabelText('Field');

      await userEvent.type(nameInput, 'Volume Range Validation');
      await userEvent.type(descriptionInput, 'Ensures volume values are positive');
      await userEvent.selectOptions(datasetSelect, 'market_data');
      await userEvent.type(fieldInput, 'volume');

      // Submit form
      const saveButton = screen.getByTestId('save-validation-rule');
      await userEvent.click(saveButton);

      expect(mockDataQualityServiceInstance.createValidationRule).toHaveBeenCalledWith(
        expect.objectContaining({
          name: 'Volume Range Validation',
          description: 'Ensures volume values are positive',
          dataset: 'market_data',
          field: 'volume',
        })
      );
    });
  });

  describe('Alert Generation', () => {
    it('should generate alerts for poor data quality', async () => {
      const poorQualityReport = {
        ...mockDataQualityReport,
        overall: {
          ...mockDataQualityReport.overall,
          score: 65.5,
          level: QualityLevel.POOR,
        },
      };

      mockDataQualityServiceInstance.getQualityReport.mockResolvedValue(poorQualityReport);

      const onAlert = jest.fn();
      render(<DataQualityDashboard onAlert={onAlert} />);

      await waitFor(() => {
        expect(onAlert).toHaveBeenCalledWith(
          expect.objectContaining({
            type: 'data_quality',
            severity: 'warning',
            title: 'Poor Data Quality Detected',
            message: expect.stringContaining('65.5'),
          })
        );
      });
    });

    it('should generate alerts for critical data quality', async () => {
      const criticalQualityReport = {
        ...mockDataQualityReport,
        overall: {
          ...mockDataQualityReport.overall,
          score: 45.2,
          level: QualityLevel.CRITICAL,
        },
      };

      mockDataQualityServiceInstance.getQualityReport.mockResolvedValue(criticalQualityReport);

      const onAlert = jest.fn();
      render(<DataQualityDashboard onAlert={onAlert} />);

      await waitFor(() => {
        expect(onAlert).toHaveBeenCalledWith(
          expect.objectContaining({
            type: 'data_quality',
            severity: 'critical',
            title: 'Critical Data Quality Issues',
            message: expect.stringContaining('45.2'),
          })
        );
      });
    });

    it('should generate alerts for high validation failure rates', async () => {
      const highFailureReport = {
        ...mockDataQualityReport,
        failedValidations: [
          ...mockDataQualityReport.failedValidations,
          {
            id: 'val-003',
            rule: 'critical_validation',
            dataset: 'market_data',
            field: 'symbol',
            message: 'Invalid symbol format',
            severity: 'error',
            count: 15000,
            samples: [],
          },
        ],
      };

      mockDataQualityServiceInstance.getQualityReport.mockResolvedValue(highFailureReport);

      const onAlert = jest.fn();
      render(<DataQualityDashboard onAlert={onAlert} />);

      await waitFor(() => {
        expect(onAlert).toHaveBeenCalledWith(
          expect.objectContaining({
            type: 'data_quality',
            severity: 'critical',
            title: 'High Validation Failure Rate',
            message: expect.stringContaining('19,688 failed validations'),
          })
        );
      });
    });
  });

  describe('Real-time Updates', () => {
    it('should auto-refresh quality metrics at specified intervals', async () => {
      jest.useFakeTimers();

      mockDataQualityServiceInstance.getQualityReport.mockResolvedValue(mockDataQualityReport);
      mockDataQualityServiceInstance.getQualityHistory.mockResolvedValue(mockDataQualityReport.trends);

      render(<DataQualityDashboard refreshInterval={5000} />);

      // Initial load
      await waitFor(() => {
        expect(mockDataQualityServiceInstance.getQualityReport).toHaveBeenCalledTimes(1);
      });

      // Fast forward 5 seconds
      jest.advanceTimersByTime(5000);

      await waitFor(() => {
        expect(mockDataQualityServiceInstance.getQualityReport).toHaveBeenCalledTimes(2);
      });

      jest.useRealTimers();
    });

    it('should emit real-time updates when quality metrics change', async () => {
      const onQualityUpdate = jest.fn();
      mockDataQualityServiceInstance.getQualityReport.mockResolvedValue(mockDataQualityReport);

      render(<DataQualityDashboard onQualityUpdate={onQualityUpdate} />);

      await waitFor(() => {
        expect(onQualityUpdate).toHaveBeenCalledWith(mockDataQualityReport);
      });
    });
  });

  describe('Dashboard Integration', () => {
    it('should accept service instances as props', async () => {
      const customService = mockDataQualityServiceInstance;
      customService.getQualityReport.mockResolvedValue(mockDataQualityReport);

      render(<DataQualityDashboard dataQualityService={customService} />);

      await waitFor(() => {
        expect(customService.getQualityReport).toHaveBeenCalled();
      });
    });

    it('should support grid positioning', async () => {
      mockDataQualityServiceInstance.getQualityReport.mockResolvedValue(mockDataQualityReport);

      render(<DataQualityDashboard gridArea="data-quality" className="custom-grid-item" />);

      await waitFor(() => {
        const container = screen.getByTestId('data-quality-dashboard');
        expect(container).toHaveClass('custom-grid-item');
        expect(container).toHaveStyle('grid-area: data-quality');
      });
    });

    it('should emit status change events for dashboard coordination', async () => {
      const onStatusChange = jest.fn();
      mockDataQualityServiceInstance.getQualityReport.mockResolvedValue(mockDataQualityReport);

      render(<DataQualityDashboard onStatusChange={onStatusChange} />);

      await waitFor(() => {
        expect(onStatusChange).toHaveBeenCalledWith(
          expect.objectContaining({
            type: 'data_quality',
            status: 'good',
            qualityScore: 85.5,
            level: QualityLevel.GOOD,
          })
        );
      });
    });
  });

  describe('Error Handling', () => {
    it('should display error message when quality report fails to load', async () => {
      mockDataQualityServiceInstance.getQualityReport.mockRejectedValue(new Error('API error'));

      render(<DataQualityDashboard />);

      await waitFor(() => {
        expect(screen.getByText('Error loading data quality report: API error')).toBeInTheDocument();
      });
    });

    it('should handle validation run errors gracefully', async () => {
      mockDataQualityServiceInstance.getQualityReport.mockResolvedValue(mockDataQualityReport);
      mockDataQualityServiceInstance.runValidation.mockRejectedValue(new Error('Validation failed'));

      render(<DataQualityDashboard />);

      await waitFor(() => {
        expect(screen.getByTestId('run-validation')).toBeInTheDocument();
      });

      const runValidationButton = screen.getByTestId('run-validation');
      await userEvent.click(runValidationButton);

      await waitFor(() => {
        expect(mockNotificationServiceInstance.create).toHaveBeenCalledWith({
          type: 'error',
          title: 'Validation Failed',
          message: 'Failed to run data validation: Validation failed',
        });
      });
    });

    it('should handle export errors gracefully', async () => {
      mockDataQualityServiceInstance.getQualityReport.mockResolvedValue(mockDataQualityReport);
      mockDataQualityServiceInstance.exportReport.mockRejectedValue(new Error('Export failed'));

      render(<DataQualityDashboard />);

      await waitFor(() => {
        expect(screen.getByTestId('export-report')).toBeInTheDocument();
      });

      const exportButton = screen.getByTestId('export-report');
      await userEvent.click(exportButton);

      await waitFor(() => {
        expect(mockNotificationServiceInstance.create).toHaveBeenCalledWith({
          type: 'error',
          title: 'Export Failed',
          message: 'Failed to export quality report: Export failed',
        });
      });
    });
  });

  describe('Accessibility', () => {
    it('should have proper ARIA labels and roles', async () => {
      mockDataQualityServiceInstance.getQualityReport.mockResolvedValue(mockDataQualityReport);

      render(<DataQualityDashboard />);

      await waitFor(() => {
        expect(screen.getByRole('region', { name: 'Data Quality Dashboard' })).toBeInTheDocument();
        expect(screen.getByLabelText('Time range')).toBeInTheDocument();
        expect(screen.getByLabelText('Filter datasets')).toBeInTheDocument();
      });
    });

    it('should support keyboard navigation', async () => {
      mockDataQualityServiceInstance.getQualityReport.mockResolvedValue(mockDataQualityReport);
      mockDataQualityServiceInstance.runValidation.mockResolvedValue({
        success: true,
        validatedRecords: 1000,
        failedRecords: 50,
        executionTime: 1200,
      });

      render(<DataQualityDashboard />);

      await waitFor(() => {
        expect(screen.getByTestId('run-validation')).toBeInTheDocument();
      });

      // Tab to validation button and press Enter
      const validationButton = screen.getByTestId('run-validation');
      validationButton.focus();
      fireEvent.keyDown(validationButton, { key: 'Enter', code: 'Enter' });

      expect(mockDataQualityServiceInstance.runValidation).toHaveBeenCalled();
    });
  });

  describe('Responsive Design', () => {
    it('should adapt layout for mobile screens', async () => {
      // Mock window.innerWidth for mobile
      Object.defineProperty(window, 'innerWidth', {
        writable: true,
        configurable: true,
        value: 375,
      });

      mockDataQualityServiceInstance.getQualityReport.mockResolvedValue(mockDataQualityReport);

      render(<DataQualityDashboard />);

      await waitFor(() => {
        const container = screen.getByTestId('data-quality-dashboard');
        expect(container).toHaveClass('mobile-layout');
      });
    });

    it('should stack charts vertically on small screens', async () => {
      Object.defineProperty(window, 'innerWidth', {
        writable: true,
        configurable: true,
        value: 640,
      });

      mockDataQualityServiceInstance.getQualityReport.mockResolvedValue(mockDataQualityReport);
      mockDataQualityServiceInstance.getQualityHistory.mockResolvedValue(mockDataQualityReport.trends);

      render(<DataQualityDashboard />);

      await waitFor(() => {
        const chartsContainer = screen.getByTestId('charts-container');
        expect(chartsContainer).toHaveClass('flex-col');
      });
    });
  });
});
