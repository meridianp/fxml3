/**
 * Example: DataManagementDashboard with Analytics Integration
 *
 * Demonstrates how to integrate the AnalyticsPanel into the existing DataManagementDashboard
 */

import React, { useState, useEffect } from 'react';
import { DataManagementDashboard, DashboardLayout, DashboardTheme } from '@/components/data-management/DataManagementDashboard';
import { AnalyticsPanel, AnalyticsPanelLayout } from '@/components/analytics/AnalyticsPanel';
import { DataSourceService } from '@/services/dataSource';
import { StorageMetricsService } from '@/services/storageMetrics';
import { DataQualityService } from '@/services/dataQuality';
import { PipelineService } from '@/services/pipeline';
import { NotificationService } from '@/services/notification';
import { KPI, SystemHealth } from '@/types/analytics';
import { DataManagementAlert } from '@/types/dataManagement';

/**
 * Example 1: Dashboard with Side Analytics Panel
 */
export const DashboardWithSideAnalytics: React.FC = () => {
  const [services] = useState(() => ({
    dataSource: new DataSourceService(),
    storage: new StorageMetricsService(),
    dataQuality: new DataQualityService(),
    pipeline: new PipelineService(),
    notification: new NotificationService(),
  }));

  const [showAnalytics, setShowAnalytics] = useState(true);

  const handleKPIClick = (kpi: KPI) => {
    console.log('KPI clicked:', kpi);
    // Navigate to detailed KPI view or show modal
  };

  const handleAlertClick = (alert: DataManagementAlert) => {
    console.log('Alert clicked:', alert);
    // Handle alert action
  };

  const handleHealthClick = (health: SystemHealth) => {
    console.log('Health clicked:', health);
    // Show detailed health breakdown
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header with Analytics Toggle */}
      <div className="bg-white border-b px-6 py-4">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold text-gray-900">
            Enhanced Data Management Dashboard
          </h1>
          <button
            onClick={() => setShowAnalytics(!showAnalytics)}
            className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
              showAnalytics
                ? 'bg-blue-600 text-white hover:bg-blue-700'
                : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
            }`}
          >
            {showAnalytics ? 'Hide Analytics' : 'Show Analytics'}
          </button>
        </div>
      </div>

      {/* Main Content */}
      <div className={`flex ${showAnalytics ? 'space-x-6' : ''} p-6`}>
        {/* Data Management Dashboard */}
        <div className={`${showAnalytics ? 'flex-1' : 'w-full'}`}>
          <DataManagementDashboard
            title="Data Management"
            initialLayout={DashboardLayout.DEFAULT}
            initialTheme={DashboardTheme.LIGHT}
            autoRefresh={true}
            refreshInterval={30000}
            dataSourceService={services.dataSource}
            storageMetricsService={services.storage}
            dataQualityService={services.dataQuality}
            pipelineService={services.pipeline}
            notificationService={services.notification}
            onAlert={(alert) => console.log('Dashboard alert:', alert)}
          />
        </div>

        {/* Analytics Panel */}
        {showAnalytics && (
          <div className="w-80 flex-shrink-0">
            <AnalyticsPanel
              layout={AnalyticsPanelLayout.VERTICAL}
              showQuickStats={true}
              showSystemHealth={true}
              showKPIs={true}
              showInsights={true}
              showAlerts={true}
              compactMode={false}
              dataSourceService={services.dataSource}
              storageMetricsService={services.storage}
              dataQualityService={services.dataQuality}
              pipelineService={services.pipeline}
              onKPIClick={handleKPIClick}
              onAlertClick={handleAlertClick}
              onHealthClick={handleHealthClick}
              onError={(error) => console.error('Analytics error:', error)}
            />
          </div>
        )}
      </div>
    </div>
  );
};

/**
 * Example 2: Dashboard with Floating Analytics Panel
 */
export const DashboardWithFloatingAnalytics: React.FC = () => {
  const [showAnalytics, setShowAnalytics] = useState(false);
  const [analyticsPosition, setAnalyticsPosition] = useState({ x: 20, y: 20 });

  return (
    <div className="min-h-screen bg-gray-50 relative">
      {/* Main Dashboard */}
      <DataManagementDashboard
        title="Data Management Dashboard"
        autoRefresh={true}
        refreshInterval={30000}
        onAlert={(alert) => console.log('Alert:', alert)}
      />

      {/* Floating Analytics Toggle */}
      <button
        onClick={() => setShowAnalytics(!showAnalytics)}
        className="fixed bottom-6 right-6 bg-blue-600 text-white p-3 rounded-full shadow-lg hover:bg-blue-700 transition-colors z-50"
        title="Toggle Analytics"
      >
        📊
      </button>

      {/* Floating Analytics Panel */}
      {showAnalytics && (
        <div
          className="fixed bg-white rounded-lg shadow-xl border z-40"
          style={{
            left: analyticsPosition.x,
            top: analyticsPosition.y,
            width: '320px',
            maxHeight: '500px',
          }}
        >
          {/* Draggable Header */}
          <div
            className="flex items-center justify-between p-3 border-b cursor-move"
            onMouseDown={(e) => {
              const startX = e.clientX - analyticsPosition.x;
              const startY = e.clientY - analyticsPosition.y;

              const handleMouseMove = (e: MouseEvent) => {
                setAnalyticsPosition({
                  x: e.clientX - startX,
                  y: e.clientY - startY,
                });
              };

              const handleMouseUp = () => {
                document.removeEventListener('mousemove', handleMouseMove);
                document.removeEventListener('mouseup', handleMouseUp);
              };

              document.addEventListener('mousemove', handleMouseMove);
              document.addEventListener('mouseup', handleMouseUp);
            }}
          >
            <h3 className="font-medium text-gray-900">Analytics</h3>
            <button
              onClick={() => setShowAnalytics(false)}
              className="text-gray-400 hover:text-gray-600"
            >
              ✕
            </button>
          </div>

          {/* Analytics Content */}
          <div className="overflow-hidden">
            <AnalyticsPanel
              layout={AnalyticsPanelLayout.COMPACT}
              showQuickStats={true}
              showSystemHealth={true}
              showKPIs={true}
              showAlerts={true}
              compactMode={true}
              className="border-0 shadow-none"
              onError={(error) => console.error('Analytics error:', error)}
            />
          </div>
        </div>
      )}
    </div>
  );
};

/**
 * Example 3: Dashboard with Modal Analytics
 */
export const DashboardWithModalAnalytics: React.FC = () => {
  const [showAnalyticsModal, setShowAnalyticsModal] = useState(false);

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Main Dashboard */}
      <DataManagementDashboard
        title="Data Management Dashboard"
        autoRefresh={true}
        refreshInterval={30000}
        onAlert={(alert) => console.log('Alert:', alert)}
      >
        {/* Add analytics button to dashboard */}
        <div className="bg-white rounded-lg p-4 shadow border">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-medium text-gray-900">Analytics</h3>
            <button
              onClick={() => setShowAnalyticsModal(true)}
              className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
            >
              Open Analytics
            </button>
          </div>
          <p className="text-gray-600 mt-2">
            View detailed analytics and performance metrics
          </p>
        </div>
      </DataManagementDashboard>

      {/* Analytics Modal */}
      {showAnalyticsModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center">
          <div className="bg-white rounded-lg shadow-xl max-w-4xl w-full mx-4 max-h-[90vh] overflow-hidden">
            {/* Modal Header */}
            <div className="flex items-center justify-between p-6 border-b">
              <h2 className="text-xl font-bold text-gray-900">Analytics Dashboard</h2>
              <button
                onClick={() => setShowAnalyticsModal(false)}
                className="text-gray-400 hover:text-gray-600"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* Modal Content */}
            <div className="p-6 overflow-y-auto" style={{ maxHeight: 'calc(90vh - 120px)' }}>
              <AnalyticsPanel
                layout={AnalyticsPanelLayout.GRID}
                showQuickStats={true}
                showSystemHealth={true}
                showKPIs={true}
                showInsights={true}
                showAlerts={true}
                compactMode={false}
                className="border-0 shadow-none"
                onError={(error) => console.error('Analytics error:', error)}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

/**
 * Example 4: Responsive Dashboard with Adaptive Analytics
 */
export const ResponsiveDashboardWithAnalytics: React.FC = () => {
  const [isMobile, setIsMobile] = useState(false);
  const [showMobileAnalytics, setShowMobileAnalytics] = useState(false);

  useEffect(() => {
    const checkScreenSize = () => {
      setIsMobile(window.innerWidth < 768);
    };

    checkScreenSize();
    window.addEventListener('resize', checkScreenSize);
    return () => window.removeEventListener('resize', checkScreenSize);
  }, []);

  if (isMobile) {
    return (
      <div className="min-h-screen bg-gray-50">
        {/* Mobile Header */}
        <div className="bg-white border-b px-4 py-3">
          <div className="flex items-center justify-between">
            <h1 className="text-lg font-bold text-gray-900">Dashboard</h1>
            <button
              onClick={() => setShowMobileAnalytics(!showMobileAnalytics)}
              className="p-2 text-gray-600 hover:text-gray-900"
            >
              📊
            </button>
          </div>
        </div>

        {/* Mobile Content */}
        <div className="p-4">
          {showMobileAnalytics ? (
            <AnalyticsPanel
              layout={AnalyticsPanelLayout.VERTICAL}
              showQuickStats={true}
              showSystemHealth={true}
              showKPIs={true}
              showAlerts={true}
              compactMode={true}
              onError={(error) => console.error('Analytics error:', error)}
            />
          ) : (
            <DataManagementDashboard
              title=""
              initialLayout={DashboardLayout.MOBILE}
              autoRefresh={true}
              refreshInterval={30000}
            />
          )}
        </div>
      </div>
    );
  }

  // Desktop layout
  return (
    <div className="min-h-screen bg-gray-50">
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 p-6">
        {/* Main Dashboard */}
        <div className="lg:col-span-3">
          <DataManagementDashboard
            title="Data Management Dashboard"
            autoRefresh={true}
            refreshInterval={30000}
          />
        </div>

        {/* Analytics Sidebar */}
        <div className="lg:col-span-1">
          <AnalyticsPanel
            layout={AnalyticsPanelLayout.VERTICAL}
            showQuickStats={true}
            showSystemHealth={true}
            showKPIs={true}
            showInsights={true}
            showAlerts={true}
            compactMode={false}
            onError={(error) => console.error('Analytics error:', error)}
          />
        </div>
      </div>
    </div>
  );
};

/**
 * Example Usage in a Real Application
 */
export const ExampleUsage: React.FC = () => {
  return (
    <div className="space-y-8 p-8">
      <div>
        <h2 className="text-2xl font-bold mb-4">Analytics Integration Examples</h2>
        <p className="text-gray-600 mb-6">
          Choose from various ways to integrate analytics into your data management dashboard:
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-white p-6 rounded-lg shadow border">
          <h3 className="text-lg font-medium mb-2">Side Panel Integration</h3>
          <p className="text-gray-600 mb-4">
            Add a persistent analytics panel to the side of your dashboard.
          </p>
          <DashboardWithSideAnalytics />
        </div>

        <div className="bg-white p-6 rounded-lg shadow border">
          <h3 className="text-lg font-medium mb-2">Floating Panel</h3>
          <p className="text-gray-600 mb-4">
            Use a draggable floating panel for analytics that can be positioned anywhere.
          </p>
          <DashboardWithFloatingAnalytics />
        </div>

        <div className="bg-white p-6 rounded-lg shadow border">
          <h3 className="text-lg font-medium mb-2">Modal Analytics</h3>
          <p className="text-gray-600 mb-4">
            Open analytics in a full-featured modal dialog for detailed analysis.
          </p>
          <DashboardWithModalAnalytics />
        </div>

        <div className="bg-white p-6 rounded-lg shadow border">
          <h3 className="text-lg font-medium mb-2">Responsive Integration</h3>
          <p className="text-gray-600 mb-4">
            Adaptive layout that works on both desktop and mobile devices.
          </p>
          <ResponsiveDashboardWithAnalytics />
        </div>
      </div>
    </div>
  );
};
