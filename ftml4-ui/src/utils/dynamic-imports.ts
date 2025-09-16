/**
 * Dynamic Import Utilities
 *
 * Centralized dynamic imports for code splitting and lazy loading
 */

import dynamic from 'next/dynamic';
import { ComponentType } from 'react';

// Loading component for dynamic imports
const LoadingSpinner = () => (
  <div className="flex items-center justify-center min-h-[200px]">
    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
  </div>
);

// Error boundary component for dynamic imports
const ErrorFallback = ({ error }: { error: Error }) => (
  <div className="flex items-center justify-center min-h-[200px] text-red-600">
    <div className="text-center">
      <p className="text-lg font-semibold">Failed to load component</p>
      <p className="text-sm mt-2">{error.message}</p>
    </div>
  </div>
);

// Common dynamic import options
const dynamicOptions = {
  loading: LoadingSpinner,
  ssr: false, // Disable SSR for heavy components
};

const dynamicOptionsWithSSR = {
  loading: LoadingSpinner,
  ssr: true,
};

// Dashboard Components (Heavy components with charts)
export const DynamicAnalyticsDashboard = dynamic(
  () => import('../components/analytics/AnalyticsDashboard'),
  {
    ...dynamicOptions,
    loading: () => <LoadingSpinner />,
  }
);

export const DynamicPerformanceScorecard = dynamic(
  () => import('../components/analytics/PerformanceScorecard'),
  dynamicOptions
);

export const DynamicDataQualityDashboard = dynamic(
  () => import('../components/data-management/DataQualityDashboard'),
  dynamicOptions
);

export const DynamicDataManagementDashboard = dynamic(
  () => import('../components/data-management/DataManagementDashboard'),
  dynamicOptions
);

// Trading Components (Chart libraries are heavy)
export const DynamicTradingConsole = dynamic(
  () => import('../components/trading/TradingConsole'),
  {
    ...dynamicOptions,
    loading: () => (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <LoadingSpinner />
          <p className="mt-2 text-sm text-gray-600">Loading Trading Console...</p>
        </div>
      </div>
    ),
  }
);

export const DynamicPriceChart = dynamic(
  () => import('../components/trading/PriceChart'),
  dynamicOptions
);

export const DynamicOrderBook = dynamic(
  () => import('../components/trading/OrderBook'),
  dynamicOptions
);

// ML Training Components (Heavy computation components)
export const DynamicTrainingStudio = dynamic(
  () => import('../components/training/TrainingStudio'),
  {
    ...dynamicOptions,
    loading: () => (
      <div className="flex items-center justify-center min-h-[500px]">
        <div className="text-center">
          <LoadingSpinner />
          <p className="mt-2 text-sm text-gray-600">Loading ML Training Studio...</p>
        </div>
      </div>
    ),
  }
);

export const DynamicParameterOptimization = dynamic(
  () => import('../components/training/ParameterOptimization'),
  dynamicOptions
);

export const DynamicExperimentList = dynamic(
  () => import('../components/training/ExperimentList'),
  dynamicOptions
);

export const DynamicModelConfiguration = dynamic(
  () => import('../components/training/ModelConfiguration'),
  dynamicOptions
);

// Data Visualization Components
export const DynamicChart = dynamic(
  () => import('../components/charts/Chart'),
  dynamicOptions
);

export const DynamicMetricsChart = dynamic(
  () => import('../components/charts/MetricsChart'),
  dynamicOptions
);

export const DynamicTrendChart = dynamic(
  () => import('../components/charts/TrendChart'),
  dynamicOptions
);

// Report and Export Components
export const DynamicReportsManager = dynamic(
  () => import('../components/reports/ReportsManager'),
  dynamicOptions
);

export const DynamicExportManager = dynamic(
  () => import('../components/reports/ExportManager'),
  dynamicOptions
);

// Modal and Dialog Components (Can be lazy loaded)
export const DynamicSettingsModal = dynamic(
  () => import('../components/modals/SettingsModal'),
  dynamicOptions
);

export const DynamicConfirmationDialog = dynamic(
  () => import('../components/modals/ConfirmationDialog'),
  dynamicOptionsWithSSR // Keep SSR for better UX
);

export const DynamicHelpModal = dynamic(
  () => import('../components/modals/HelpModal'),
  dynamicOptions
);

// Form Components (Can be loaded on demand)
export const DynamicAdvancedOrderForm = dynamic(
  () => import('../components/forms/AdvancedOrderForm'),
  dynamicOptions
);

export const DynamicModelTrainingForm = dynamic(
  () => import('../components/forms/ModelTrainingForm'),
  dynamicOptions
);

// Third-party integrations (Heavy libraries)
export const DynamicCodeEditor = dynamic(
  () => import('@monaco-editor/react').then(mod => ({ default: mod.Editor })),
  {
    ...dynamicOptions,
    loading: () => (
      <div className="flex items-center justify-center h-64 bg-gray-100 rounded-md">
        <div className="text-center">
          <LoadingSpinner />
          <p className="mt-2 text-sm text-gray-600">Loading Code Editor...</p>
        </div>
      </div>
    ),
  }
);

// Date picker (moment.js is heavy)
export const DynamicDateRangePicker = dynamic(
  () => import('react-date-range').then(mod => ({ default: mod.DateRangePicker })),
  dynamicOptions
);

// File upload with drag and drop
export const DynamicFileUpload = dynamic(
  () => import('react-dropzone').then(mod => ({ default: mod.default })),
  dynamicOptions
);

// Data table with virtualization
export const DynamicVirtualizedTable = dynamic(
  () => import('../components/tables/VirtualizedTable'),
  dynamicOptions
);

// Advanced analytics components
export const DynamicHeatmap = dynamic(
  () => import('../components/analytics/Heatmap'),
  dynamicOptions
);

export const DynamicCorrelationMatrix = dynamic(
  () => import('../components/analytics/CorrelationMatrix'),
  dynamicOptions
);

// WebSocket components (for real-time features)
export const DynamicRealtimeMonitor = dynamic(
  () => import('../components/monitoring/RealtimeMonitor'),
  dynamicOptions
);

export const DynamicLiveDataFeed = dynamic(
  () => import('../components/data/LiveDataFeed'),
  dynamicOptions
);

// Utility function to create dynamic imports with custom loading
export function createDynamicImport<T = any>(
  importFn: () => Promise<{ default: ComponentType<T> }>,
  options: {
    loading?: ComponentType;
    ssr?: boolean;
    loadingText?: string;
  } = {}
) {
  const {
    loading = LoadingSpinner,
    ssr = false,
    loadingText
  } = options;

  const LoadingComponent = loadingText
    ? () => (
        <div className="flex items-center justify-center min-h-[200px]">
          <div className="text-center">
            <LoadingSpinner />
            <p className="mt-2 text-sm text-gray-600">{loadingText}</p>
          </div>
        </div>
      )
    : loading;

  return dynamic(importFn, {
    loading: LoadingComponent,
    ssr,
  });
}

// Utility function for lazy loading heavy libraries
export async function loadHeavyLibrary(libraryName: string) {
  const libraries = {
    'chart.js': () => import('chart.js'),
    'd3': () => import('d3'),
    'three': () => import('three'),
    'tensorflow': () => import('@tensorflow/tfjs'),
    'moment': () => import('moment'),
    'lodash': () => import('lodash-es'),
  };

  const library = libraries[libraryName as keyof typeof libraries];

  if (!library) {
    throw new Error(`Unknown library: ${libraryName}`);
  }

  try {
    return await library();
  } catch (error) {
    console.error(`Failed to load library ${libraryName}:`, error);
    throw error;
  }
}

// Route-based code splitting
export const RouteComponents = {
  Dashboard: DynamicAnalyticsDashboard,
  Trading: DynamicTradingConsole,
  DataManagement: DynamicDataManagementDashboard,
  Training: DynamicTrainingStudio,
  Reports: DynamicReportsManager,
};

// Feature flags for progressive loading
export const FeatureFlags = {
  ENABLE_ADVANCED_CHARTS: process.env.NODE_ENV === 'production',
  ENABLE_ML_FEATURES: true,
  ENABLE_REALTIME_FEATURES: true,
  ENABLE_EXPERIMENTAL_FEATURES: process.env.NODE_ENV === 'development',
};

// Preload critical components
export function preloadCriticalComponents() {
  if (typeof window !== 'undefined') {
    // Preload most likely to be used components
    import('../components/analytics/AnalyticsDashboard');
    import('../components/trading/TradingConsole');

    // Preload on interaction
    const preloadOnInteraction = [
      () => import('../components/data-management/DataManagementDashboard'),
      () => import('../components/training/TrainingStudio'),
    ];

    // Preload after a delay
    setTimeout(() => {
      preloadOnInteraction.forEach(importFn => importFn());
    }, 2000);
  }
}

// Bundle size monitoring
export function logBundleSizes() {
  if (process.env.NODE_ENV === 'development') {
    console.group('🎯 Dynamic Import Summary');
    console.log('Analytics Dashboard: Lazy loaded');
    console.log('Trading Console: Lazy loaded');
    console.log('ML Training Studio: Lazy loaded');
    console.log('Chart Libraries: Lazy loaded');
    console.log('Code Editor: Lazy loaded');
    console.groupEnd();
  }
}
