"""
Performance monitoring dashboard for FXML4.

Provides real-time metrics visualization and system health monitoring
through a web-based dashboard.
"""

import json
import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse

from .metrics import get_metrics_collector

logger = logging.getLogger(__name__)


class MetricsDashboard:
    """Real-time metrics dashboard for FXML4 system monitoring."""

    def __init__(self):
        """Initialize metrics dashboard."""
        self.collector = get_metrics_collector()
        logger.info("MetricsDashboard initialized")

    def get_dashboard_data(self) -> Dict[str, Any]:
        """Get comprehensive dashboard data."""
        metrics_summary = self.collector.get_metrics_summary()

        # Calculate key performance indicators
        counters = metrics_summary.get("counters", {})
        gauges = metrics_summary.get("gauges", {})
        timers = metrics_summary.get("timers", {})

        # API Performance KPIs
        total_requests = counters.get("http_requests_total", 0)
        error_requests = counters.get("http_requests_errors_total", 0)
        error_rate = (
            (error_requests / total_requests * 100) if total_requests > 0 else 0
        )

        # Trading KPIs
        total_orders = counters.get("orders_executed_total", 0)
        order_errors = counters.get("order_execution_errors_total", 0)
        order_success_rate = (
            ((total_orders - order_errors) / total_orders * 100)
            if total_orders > 0
            else 100
        )

        # FIX Message KPIs
        fix_messages = counters.get("fix_messages_total", 0)
        avg_fix_processing = timers.get("fix_message_processing_time_seconds", {}).get(
            "avg_time", 0
        )

        # ML Performance KPIs
        ml_inferences = counters.get("ml_inferences_total", 0)
        ml_errors = counters.get("ml_inference_errors_total", 0)
        ml_success_rate = (
            ((ml_inferences - ml_errors) / ml_inferences * 100)
            if ml_inferences > 0
            else 100
        )

        return {
            "timestamp": datetime.now().isoformat(),
            "system_health": {
                "status": self._calculate_health_status(
                    error_rate, order_success_rate, ml_success_rate
                ),
                "uptime_seconds": metrics_summary.get("system", {}).get(
                    "uptime_seconds", 0
                ),
                "active_requests": gauges.get("api_active_requests", 0),
            },
            "api_performance": {
                "total_requests": total_requests,
                "error_requests": error_requests,
                "error_rate_percent": round(error_rate, 2),
                "avg_response_time": timers.get("api_request_duration_seconds", {}).get(
                    "avg_time", 0
                ),
                "requests_per_minute": self._calculate_rate(
                    counters, "http_requests_total"
                ),
            },
            "trading_performance": {
                "total_orders": total_orders,
                "successful_orders": total_orders - order_errors,
                "success_rate_percent": round(order_success_rate, 2),
                "avg_execution_time": timers.get(
                    "order_execution_time_seconds", {}
                ).get("avg_time", 0),
                "orders_per_minute": self._calculate_rate(
                    counters, "orders_executed_total"
                ),
            },
            "fix_protocol": {
                "total_messages": fix_messages,
                "avg_processing_time": round(
                    avg_fix_processing * 1000, 2
                ),  # Convert to ms
                "messages_per_minute": self._calculate_rate(
                    counters, "fix_messages_total"
                ),
                "performance_improvement": (
                    "Fast FIX enabled" if avg_fix_processing < 0.001 else "Standard FIX"
                ),
            },
            "ml_performance": {
                "total_inferences": ml_inferences,
                "successful_inferences": ml_inferences - ml_errors,
                "success_rate_percent": round(ml_success_rate, 2),
                "avg_inference_time": timers.get("ml_inference_time_seconds", {}).get(
                    "avg_time", 0
                ),
                "inferences_per_minute": self._calculate_rate(
                    counters, "ml_inferences_total"
                ),
            },
            "broker_adapters": self._get_broker_adapter_stats(counters, timers),
            "recent_activity": self._get_recent_activity(),
            "performance_trends": self._get_performance_trends(),
        }

    def _calculate_health_status(
        self, error_rate: float, order_success_rate: float, ml_success_rate: float
    ) -> str:
        """Calculate overall system health status."""
        if error_rate > 10 or order_success_rate < 90 or ml_success_rate < 90:
            return "unhealthy"
        elif error_rate > 5 or order_success_rate < 95 or ml_success_rate < 95:
            return "warning"
        else:
            return "healthy"

    def _calculate_rate(self, counters: Dict[str, float], metric_name: str) -> float:
        """Calculate per-minute rate for a metric."""
        # This is simplified - in production, you'd track time-series data
        total_value = counters.get(metric_name, 0)
        uptime_minutes = max(
            1, self.collector.get_metrics_summary()["system"]["uptime_seconds"] / 60
        )
        return round(total_value / uptime_minutes, 2)

    def _get_broker_adapter_stats(
        self, counters: Dict[str, float], timers: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Get broker adapter performance statistics."""
        # Extract broker-specific metrics
        broker_stats = {}

        for key in counters.keys():
            if key.startswith("broker_operations_total[adapter="):
                # Parse adapter name from key
                adapter_name = (
                    key.split("adapter=")[1].split(",")[0]
                    if "adapter=" in key
                    else "unknown"
                )

                if adapter_name not in broker_stats:
                    broker_stats[adapter_name] = {
                        "total_operations": 0,
                        "errors": 0,
                        "avg_duration": 0,
                    }

                broker_stats[adapter_name]["total_operations"] += counters[key]

        return broker_stats

    def _get_recent_activity(self) -> List[Dict[str, Any]]:
        """Get recent system activity log."""
        # Simplified activity log - in production, you'd maintain a proper event log
        return [
            {
                "timestamp": (datetime.now() - timedelta(minutes=1)).isoformat(),
                "event": "FIX message processed",
                "details": "ExecutionReport processed in 0.5ms",
            },
            {
                "timestamp": (datetime.now() - timedelta(minutes=2)).isoformat(),
                "event": "Order executed",
                "details": "EURUSD buy order filled",
            },
            {
                "timestamp": (datetime.now() - timedelta(minutes=3)).isoformat(),
                "event": "ML inference completed",
                "details": "Signal generated for GBPUSD",
            },
        ]

    def _get_performance_trends(self) -> Dict[str, List[float]]:
        """Get performance trend data for charts."""
        # Simplified trends - in production, you'd store historical data
        import random

        # Generate sample trend data
        now = time.time()
        trend_points = []

        for i in range(20):  # Last 20 data points
            trend_points.append(
                {
                    "timestamp": now - (19 - i) * 30,  # 30-second intervals
                    "api_response_time": random.uniform(0.1, 0.5),
                    "order_execution_time": random.uniform(0.05, 0.2),
                    "fix_processing_time": random.uniform(0.001, 0.005),
                }
            )

        return {
            "timestamps": [p["timestamp"] for p in trend_points],
            "api_response_times": [p["api_response_time"] for p in trend_points],
            "order_execution_times": [p["order_execution_time"] for p in trend_points],
            "fix_processing_times": [p["fix_processing_time"] for p in trend_points],
        }


def create_dashboard_router() -> APIRouter:
    """Create FastAPI router for metrics dashboard."""
    router = APIRouter(prefix="/monitoring", tags=["monitoring"])
    dashboard = MetricsDashboard()

    @router.get("/dashboard", response_class=HTMLResponse)
    async def get_dashboard_html():
        """Serve the metrics dashboard HTML page."""
        html_content = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>FXML4 Performance Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }
        .dashboard { max-width: 1200px; margin: 0 auto; }
        .header { text-align: center; margin-bottom: 30px; }
        .metrics-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }
        .metric-card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .metric-value { font-size: 2em; font-weight: bold; color: #2196F3; }
        .metric-label { color: #666; margin-bottom: 10px; }
        .status-healthy { color: #4CAF50; }
        .status-warning { color: #FF9800; }
        .status-unhealthy { color: #F44336; }
        .chart-container { width: 100%; height: 300px; margin-top: 20px; }
        .activity-log { max-height: 300px; overflow-y: auto; }
        .activity-item { padding: 10px; border-bottom: 1px solid #eee; }
        .refresh-button { background: #2196F3; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; }
        .refresh-button:hover { background: #1976D2; }
    </style>
</head>
<body>
    <div class="dashboard">
        <div class="header">
            <h1>FXML4 Performance Dashboard</h1>
            <button class="refresh-button" onclick="refreshDashboard()">Refresh Data</button>
            <p>Last updated: <span id="lastUpdate">Loading...</span></p>
        </div>

        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-label">System Health</div>
                <div class="metric-value" id="systemHealth">Loading...</div>
                <div>Uptime: <span id="uptime">0</span> seconds</div>
                <div>Active Requests: <span id="activeRequests">0</span></div>
            </div>

            <div class="metric-card">
                <div class="metric-label">API Performance</div>
                <div class="metric-value" id="totalRequests">0</div>
                <div>Error Rate: <span id="errorRate">0</span>%</div>
                <div>Avg Response Time: <span id="avgResponseTime">0</span>ms</div>
                <div>Requests/min: <span id="requestsPerMin">0</span></div>
            </div>

            <div class="metric-card">
                <div class="metric-label">Trading Performance</div>
                <div class="metric-value" id="totalOrders">0</div>
                <div>Success Rate: <span id="orderSuccessRate">100</span>%</div>
                <div>Avg Execution: <span id="avgExecutionTime">0</span>ms</div>
                <div>Orders/min: <span id="ordersPerMin">0</span></div>
            </div>

            <div class="metric-card">
                <div class="metric-label">FIX Protocol</div>
                <div class="metric-value" id="fixMessages">0</div>
                <div>Avg Processing: <span id="fixProcessingTime">0</span>ms</div>
                <div>Messages/min: <span id="fixPerMin">0</span></div>
                <div>Mode: <span id="fixMode">Standard</span></div>
            </div>

            <div class="metric-card">
                <div class="metric-label">ML Performance</div>
                <div class="metric-value" id="mlInferences">0</div>
                <div>Success Rate: <span id="mlSuccessRate">100</span>%</div>
                <div>Avg Inference: <span id="avgInferenceTime">0</span>ms</div>
                <div>Inferences/min: <span id="inferencesPerMin">0</span></div>
            </div>

            <div class="metric-card">
                <div class="metric-label">Performance Trends</div>
                <canvas id="performanceChart"></canvas>
            </div>
        </div>

        <div class="metrics-grid" style="margin-top: 20px;">
            <div class="metric-card">
                <div class="metric-label">Recent Activity</div>
                <div class="activity-log" id="activityLog">
                    Loading activity...
                </div>
            </div>

            <div class="metric-card">
                <div class="metric-label">Broker Adapters</div>
                <div id="brokerStats">Loading broker statistics...</div>
            </div>
        </div>
    </div>

    <script>
        let performanceChart = null;

        async function refreshDashboard() {
            try {
                const response = await fetch('/monitoring/data');
                const data = await response.json();
                updateDashboard(data);
            } catch (error) {
                console.error('Error refreshing dashboard:', error);
            }
        }

        function updateDashboard(data) {
            // Update timestamp
            document.getElementById('lastUpdate').textContent = new Date(data.timestamp).toLocaleString();

            // System health
            const healthElement = document.getElementById('systemHealth');
            healthElement.textContent = data.system_health.status.toUpperCase();
            healthElement.className = 'metric-value status-' + data.system_health.status;
            document.getElementById('uptime').textContent = Math.round(data.system_health.uptime_seconds);
            document.getElementById('activeRequests').textContent = data.system_health.active_requests;

            // API performance
            document.getElementById('totalRequests').textContent = data.api_performance.total_requests;
            document.getElementById('errorRate').textContent = data.api_performance.error_rate_percent;
            document.getElementById('avgResponseTime').textContent = Math.round(data.api_performance.avg_response_time * 1000);
            document.getElementById('requestsPerMin').textContent = data.api_performance.requests_per_minute;

            // Trading performance
            document.getElementById('totalOrders').textContent = data.trading_performance.total_orders;
            document.getElementById('orderSuccessRate').textContent = data.trading_performance.success_rate_percent;
            document.getElementById('avgExecutionTime').textContent = Math.round(data.trading_performance.avg_execution_time * 1000);
            document.getElementById('ordersPerMin').textContent = data.trading_performance.orders_per_minute;

            // FIX protocol
            document.getElementById('fixMessages').textContent = data.fix_protocol.total_messages;
            document.getElementById('fixProcessingTime').textContent = data.fix_protocol.avg_processing_time;
            document.getElementById('fixPerMin').textContent = data.fix_protocol.messages_per_minute;
            document.getElementById('fixMode').textContent = data.fix_protocol.performance_improvement;

            // ML performance
            document.getElementById('mlInferences').textContent = data.ml_performance.total_inferences;
            document.getElementById('mlSuccessRate').textContent = data.ml_performance.success_rate_percent;
            document.getElementById('avgInferenceTime').textContent = Math.round(data.ml_performance.avg_inference_time * 1000);
            document.getElementById('inferencesPerMin').textContent = data.ml_performance.inferences_per_minute;

            // Update activity log
            const activityHtml = data.recent_activity.map(item =>
                `<div class="activity-item">
                    <strong>${new Date(item.timestamp).toLocaleTimeString()}</strong><br>
                    ${item.event}: ${item.details}
                </div>`
            ).join('');
            document.getElementById('activityLog').innerHTML = activityHtml;

            // Update broker stats
            const brokerHtml = Object.entries(data.broker_adapters).map(([name, stats]) =>
                `<div><strong>${name}</strong>: ${stats.total_operations} ops, ${stats.errors} errors</div>`
            ).join('');
            document.getElementById('brokerStats').innerHTML = brokerHtml || 'No broker activity';

            // Update performance chart
            updatePerformanceChart(data.performance_trends);
        }

        function updatePerformanceChart(trends) {
            const ctx = document.getElementById('performanceChart').getContext('2d');

            if (performanceChart) {
                performanceChart.destroy();
            }

            performanceChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: trends.timestamps.map(t => new Date(t * 1000).toLocaleTimeString()),
                    datasets: [
                        {
                            label: 'API Response Time (ms)',
                            data: trends.api_response_times.map(t => t * 1000),
                            borderColor: 'rgb(75, 192, 192)',
                            tension: 0.1
                        },
                        {
                            label: 'Order Execution Time (ms)',
                            data: trends.order_execution_times.map(t => t * 1000),
                            borderColor: 'rgb(255, 99, 132)',
                            tension: 0.1
                        },
                        {
                            label: 'FIX Processing Time (ms)',
                            data: trends.fix_processing_times.map(t => t * 1000),
                            borderColor: 'rgb(54, 162, 235)',
                            tension: 0.1
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: {
                            beginAtZero: true,
                            title: { display: true, text: 'Time (ms)' }
                        }
                    }
                }
            });
        }

        // Auto-refresh every 30 seconds
        setInterval(refreshDashboard, 30000);

        // Initial load
        refreshDashboard();
    </script>
</body>
</html>
        """
        return HTMLResponse(content=html_content)

    @router.get("/data")
    async def get_dashboard_data():
        """Get dashboard data as JSON."""
        try:
            return JSONResponse(content=dashboard.get_dashboard_data())
        except Exception as e:
            logger.error(f"Error getting dashboard data: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to get dashboard data")

    @router.get("/metrics/summary")
    async def get_metrics_summary():
        """Get raw metrics summary."""
        try:
            collector = get_metrics_collector()
            return JSONResponse(content=collector.get_metrics_summary())
        except Exception as e:
            logger.error(f"Error getting metrics summary: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to get metrics summary")

    @router.post("/metrics/reset")
    async def reset_metrics():
        """Reset all metrics (admin endpoint)."""
        try:
            collector = get_metrics_collector()
            collector.reset_metrics()
            return JSONResponse(content={"message": "Metrics reset successfully"})
        except Exception as e:
            logger.error(f"Error resetting metrics: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to reset metrics")

    return router
