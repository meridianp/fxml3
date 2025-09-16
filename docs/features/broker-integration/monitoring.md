# Monitoring Dashboard

The FXML4 Monitoring Dashboard provides real-time visibility into the broker integration system, allowing traders and administrators to monitor system health, order flow, and performance metrics.

## Overview

The monitoring dashboard is a web-based interface that displays:

- **System Health**: Connection status, uptime, error rates
- **Order Flow**: Real-time order submission and execution metrics
- **Risk Metrics**: Position monitoring, limit utilization, violations
- **Performance**: Response times, throughput, error analysis
- **Compliance**: Real-time compliance checks and violations

## Accessing the Dashboard

The monitoring dashboard is available at:

```
http://localhost:8000/static/monitoring_dashboard.html
```

### Authentication

Access requires valid API credentials. The dashboard will prompt for authentication if not already logged in.

## Dashboard Sections

### 1. System Overview

**Real-time Status Cards:**
- Total system uptime
- Active broker connections
- Orders processed today
- Current error rate

**Connection Status:**
- Interactive Brokers: Connected/Disconnected status
- FIX Brokers: Session status and heartbeat
- Manual Execution: Queue status
- RabbitMQ: Message queue health

### 2. Order Flow Monitoring

**Order Statistics:**
- Orders submitted per minute/hour
- Fill rates by broker
- Average execution time
- Rejection rates and reasons

**Real-time Order Stream:**
- Live order submissions
- Execution reports
- Order status changes
- Risk interventions

### 3. Risk Management

**Position Monitoring:**
- Current positions by symbol
- Exposure limits and utilization
- Concentration risk metrics
- Daily P&L tracking

**Risk Violations:**
- Recent violations by rule type
- Auto-blocked orders
- Manual overrides pending
- Risk limit breaches

### 4. Performance Metrics

**Response Time Analysis:**
- Average response times by broker
- P95/P99 response time percentiles
- Slow query identification
- Performance trend analysis

**Throughput Monitoring:**
- Messages per second
- Order processing capacity
- Queue depths and latency
- Capacity utilization

### 5. Compliance Dashboard

**Regulatory Compliance:**
- Active compliance rules
- Recent violations by jurisdiction
- Audit event summary
- Report generation status

**Suspicious Activity:**
- AML alerts and risk scores
- Transaction monitoring results
- False positive rates
- Investigation status

## Real-time Features

### WebSocket Updates

The dashboard uses WebSocket connections for real-time updates:

```javascript
// Example WebSocket connection
const ws = new WebSocket('ws://localhost:8000/ws/monitoring');

ws.onmessage = function(event) {
    const data = JSON.parse(event.data);
    updateDashboard(data);
};
```

### Auto-refresh Intervals

- **System Status**: Every 5 seconds
- **Order Metrics**: Every 10 seconds
- **Risk Metrics**: Every 30 seconds
- **Performance Data**: Every 60 seconds

## Alerting and Notifications

### Visual Alerts

The dashboard provides visual indicators for:

- 🔴 **Critical**: System failures, compliance violations
- 🟡 **Warning**: Performance degradation, limit breaches
- 🟢 **Normal**: Healthy operation
- 🔵 **Info**: Status updates, configuration changes

### Audio Notifications

Audio alerts are triggered for:
- Critical system failures
- Compliance violations requiring immediate attention
- Risk limit breaches
- Connection failures

### Browser Notifications

Desktop notifications for:
- Order execution failures
- System maintenance events
- Performance threshold breaches

## Configuration

Dashboard settings are configured in the browser and persist locally:

```javascript
// Dashboard configuration
const dashboardConfig = {
    refreshIntervals: {
        systemHealth: 5000,    // 5 seconds
        orderFlow: 10000,      // 10 seconds
        riskMetrics: 30000,    // 30 seconds
        performance: 60000     // 60 seconds
    },
    alerts: {
        enableAudio: true,
        enableDesktop: true,
        alertThresholds: {
            errorRate: 0.05,        // 5%
            responseTime: 1000,     // 1 second
            queueDepth: 100         // messages
        }
    },
    display: {
        theme: 'dark',
        autoHideAlerts: 30000,  // 30 seconds
        maxHistoryItems: 100
    }
};
```

## API Integration

The dashboard connects to monitoring endpoints:

### System Health Endpoint

```http
GET /api/v1/monitoring/health
```

Returns comprehensive system health metrics including broker connections, queue status, and error rates.

### Order Metrics Endpoint

```http
GET /api/v1/monitoring/orders
```

Provides real-time order flow statistics and execution metrics.

### Risk Metrics Endpoint

```http
GET /api/v1/monitoring/risk
```

Returns current risk exposure, limit utilization, and recent violations.

## Troubleshooting

### Common Issues

**Dashboard Not Loading:**
1. Check API server is running on port 8000
2. Verify static file serving is enabled
3. Check browser console for JavaScript errors
4. Ensure WebSocket connection is established

**Missing Data:**
1. Verify monitoring endpoints are responding
2. Check API authentication tokens
3. Review server logs for errors
4. Confirm data collection services are running

**Slow Performance:**
1. Check network latency to API server
2. Reduce refresh frequencies if needed
3. Clear browser cache and local storage
4. Monitor server resource usage

### Debug Mode

Enable debug mode by adding `?debug=1` to the URL:

```
http://localhost:8000/static/monitoring_dashboard.html?debug=1
```

Debug mode provides:
- Console logging of all API calls
- WebSocket message inspection
- Performance timing information
- Error stack traces

## Customization

### Adding Custom Metrics

To add custom metrics to the dashboard:

1. **Create API Endpoint:**
```python
@router.get("/monitoring/custom-metric")
async def get_custom_metric():
    return {"value": calculate_custom_metric()}
```

2. **Update Dashboard JavaScript:**
```javascript
async function updateCustomMetric() {
    const response = await fetch('/api/v1/monitoring/custom-metric');
    const data = await response.json();
    document.getElementById('custom-metric').textContent = data.value;
}
```

3. **Add to Refresh Cycle:**
```javascript
setInterval(updateCustomMetric, 30000); // Update every 30 seconds
```

### Custom Themes

Create custom CSS themes by modifying the dashboard styles:

```css
/* Custom dark theme */
:root {
    --bg-primary: #1a1a1a;
    --bg-secondary: #2d2d2d;
    --text-primary: #ffffff;
    --text-secondary: #cccccc;
    --accent-color: #00ff88;
    --warning-color: #ffcc00;
    --error-color: #ff4444;
}
```

## Mobile Access

The dashboard is responsive and works on mobile devices:

- **Optimized Layout**: Stacked cards for mobile screens
- **Touch Gestures**: Swipe to refresh sections
- **Simplified View**: Essential metrics only on small screens
- **Offline Mode**: Cached data when connection is lost

## Security Considerations

### Access Control

- Dashboard access is protected by API authentication
- Role-based permissions control visible sections
- Sensitive data can be masked for certain user roles

### Data Privacy

- No sensitive trading data is cached in browser
- All communications use HTTPS in production
- Session tokens expire automatically

### Audit Trail

- All dashboard access is logged
- User actions are tracked for compliance
- Configuration changes are audited

## Performance Optimization

### Efficient Updates

- Only changed data is transmitted via WebSocket
- Client-side caching reduces API calls
- Conditional rendering prevents unnecessary DOM updates

### Memory Management

- Automatic cleanup of old data points
- Efficient chart rendering with data sampling
- Memory leak prevention in long-running sessions

## See Also

- [API Reference](../../api-reference/endpoints/monitoring.md)
- [Manual Execution](manual-execution.md)
- [Risk Management](../risk-management/monitoring.md)
- [Compliance Monitoring](../compliance/index.md)
