"""
FXML4 Business Intelligence Module

This module provides comprehensive business intelligence capabilities including:
- Executive dashboards and operational analytics
- Advanced analytics engine with predictive capabilities
- Custom reporting framework with automated generation
- Data warehouse management and ETL pipelines
- Real-time analytics processing and visualization

Key Components:
- dashboard: Executive and operational dashboard components
- analytics: Core analytics engine and processing
- reporting: Custom report generation and distribution
- warehouse: Data warehouse management and ETL
- predictive: Predictive analytics and forecasting models
"""

from .analytics.engine import AnalyticsEngine
from .dashboard.executive import ExecutiveDashboard
from .predictive.forecaster import PredictiveAnalytics
from .reporting.generator import ReportGenerator
from .warehouse.manager import DataWarehouseManager

__version__ = "1.0.0"
__author__ = "FXML4 Development Team"

__all__ = [
    "ExecutiveDashboard",
    "AnalyticsEngine",
    "ReportGenerator",
    "DataWarehouseManager",
    "PredictiveAnalytics",
]
