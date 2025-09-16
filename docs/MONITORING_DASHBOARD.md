# FXML4 Monitoring Dashboard

## Overview

The FXML4 Monitoring Dashboard provides real-time visibility into the broker abstraction system, including adapter status, risk management metrics, and system health monitoring. The dashboard consists of a FastAPI backend with comprehensive REST endpoints and a modern web-based frontend.

## Features

### 🎯 Core Monitoring Capabilities

- **System Health Overview**: Real-time system status with component health checks
- **Broker Adapter Monitoring**: Status, metrics, and performance data for all adapters
- **Risk Management Dashboard**: Position tracking, limit monitoring, and violation alerts
- **Performance Metrics**: Order statistics, success rates, and throughput analysis
- **Real-time Updates**: Auto-refreshing dashboard with WebSocket support (optional)
- **Activity Logs**: Recent system events and error tracking

### 📊 Key Metrics Tracked

#### Adapter Metrics
- Connection status (Connected/Disconnected/Connecting)
- Order statistics (Total, Filled, Rejected, Cancelled, Failed)
- Uptime and stability scores
- Reconnection attempts and success rates
- Adapter-specific session information

#### Risk Management Metrics
- Total portfolio notional exposure
- Daily P&L tracking
- Position counts and limits
- Open order monitoring
- Risk limit utilization percentages

#### System Performance
- Order success rates
- Average response times
- System component health status
- Resource utilization metrics

## API Endpoints

### System Health

- `GET /api/monitoring/health` - Overall system health status
- `GET /api/monitoring/metrics/summary` - Aggregated metrics summary
- `GET /api/monitoring/metrics/performance` - Performance metrics for all adapters

### Adapter Management

- `GET /api/monitoring/adapters` - Status of all broker adapters
- `GET /api/monitoring/adapters/{adapter_id}` - Detailed adapter information
- `POST /api/monitoring/adapters/{adapter_id}/restart` - Restart specific adapter

### Logs and Events

- `GET /api/monitoring/logs/recent` - Recent log entries with filtering
- `WebSocket /api/monitoring/ws` - Real-time monitoring updates

### Risk Management Integration

- `GET /api/risk/summary` - Current risk metrics and limits
- `GET /api/risk/positions` - Active positions and exposures
- `GET /api/risk/limits` - Configured risk limits
- `POST /api/risk/check` - Manual risk check for orders
- `POST /api/risk/override` - Risk override management

## Dashboard Access

### Primary Access Points

1. **Main Dashboard**: `http://localhost:8000/dashboard`
2. **Static Access**: `http://localhost:8000/static/monitoring_dashboard.html`
3. **API Documentation**: `http://localhost:8000/docs`

### Dashboard Sections

#### 1. System Health Overview
- **Status Indicator**: Green (Healthy), Yellow (Degraded), Red (Critical)
- **Component Summary**: Shows health of all monitored components
- **Key Metrics Grid**: Displays 6 core metrics at a glance
  - Total Orders
  - Success Rate
  - Active Adapters
  - Total Notional
  - Daily P&L
  - Open Orders

#### 2. Broker Adapters Panel
- **Adapter Cards**: Visual representation of each adapter
- **Status Indicators**: Color-coded connection status
- **Metrics Display**: Order counts, uptime, and performance data
- **Error Reporting**: Latest error messages and timestamps

#### 3. Activity & Logs Panel
- **Recent Events**: Last 10 system events with filtering
- **Log Levels**: INFO, WARNING, ERROR with color coding
- **Timestamps**: Precise timing of all events
- **Source Tracking**: Logger names for easy debugging

## Configuration

### Environment Setup

1. **Dependencies**: Ensure all required packages are installed
   ```bash
   pip install fastapi uvicorn websockets pydantic
   ```

2. **Risk Configuration**: Update `config/risk_limits.yaml`
   ```yaml
   position_limits:
     max_portfolio_notional: 10000000
     max_single_position_notional: 1000000

   order_limits:
     max_order_notional: 500000
     min_order_size: 1000

   loss_limits:
     max_daily_loss: 50000
   ```

3. **Adapter Configuration**: Configure adapters in your main config

### Dashboard Settings

The dashboard includes several configurable features:

- **Auto-refresh**: 5-second interval (toggleable)
- **WebSocket Updates**: Real-time updates when available
- **Responsive Design**: Works on desktop and mobile devices
- **Dark Theme**: Professional trading interface styling

## Usage Examples

### Starting the Monitoring System

```bash
# Start the API server
python -m uvicorn fxml4.api.main:app --host 0.0.0.0 --port 8000

# Or use the test script
python scripts/test_monitoring_dashboard.py
```

### API Usage Examples

#### Check System Health
```python
import requests

response = requests.get("http://localhost:8000/api/monitoring/health")
health_data = response.json()
print(f"System Status: {health_data['status']}")
```

#### Get Adapter Status
```python
response = requests.get("http://localhost:8000/api/monitoring/adapters")
adapters = response.json()
for adapter in adapters['data']['adapters']:
    print(f"{adapter['broker_name']}: {adapter['status']}")
```

#### Monitor Risk Metrics
```python
response = requests.get("http://localhost:8000/api/monitoring/metrics/summary")
metrics = response.json()
risk = metrics['data']['risk']
print(f"Portfolio Notional: ${risk['total_notional']:,}")
print(f"Daily P&L: ${risk['daily_pnl']:,}")
```

### WebSocket Real-time Updates

```javascript
const ws = new WebSocket('ws://localhost:8000/api/monitoring/ws');

ws.onmessage = function(event) {
    const update = JSON.parse(event.data);
    if (update.type === 'health_update') {
        updateDashboard(update.data);
    }
};
```

## Troubleshooting

### Common Issues

#### 1. Dashboard Not Loading
- Check API server is running on correct port
- Verify static files are properly mounted
- Check browser console for JavaScript errors

#### 2. No Data Showing
- Ensure adapters are configured and connected
- Check risk manager is initialized
- Verify database connections if applicable

#### 3. WebSocket Connection Failed
- WebSocket is optional; dashboard falls back to polling
- Check firewall settings for WebSocket traffic
- Verify proxy configurations if behind load balancer

#### 4. API Errors
- Check logs for detailed error messages
- Verify all dependencies are installed
- Ensure configuration files are valid

### Debugging Steps

1. **Check API Health**:
   ```bash
   curl http://localhost:8000/health
   ```

2. **Test Monitoring Endpoints**:
   ```bash
   curl http://localhost:8000/api/monitoring/health
   ```

3. **Verify Static Files**:
   ```bash
   curl http://localhost:8000/static/monitoring_dashboard.html
   ```

4. **Check Logs**:
   ```bash
   tail -f logs/fxml4.log
   ```

## Development

### Adding New Metrics

1. **Backend**: Add metrics to appropriate router in `fxml4/api/routers/monitoring.py`
2. **Frontend**: Update dashboard JavaScript to display new metrics
3. **Testing**: Add tests to `scripts/test_monitoring_dashboard.py`

### Customizing the Dashboard

The dashboard is built with vanilla HTML/CSS/JavaScript for maximum compatibility:

- **Styling**: Edit CSS in the `<style>` section
- **Functionality**: Modify JavaScript functions
- **Layout**: Update HTML structure in the dashboard file

### Performance Considerations

- **Caching**: API responses include timestamps for cache validation
- **Polling Rate**: Default 5-second refresh can be adjusted
- **Data Limits**: Log entries are limited to prevent memory issues
- **WebSocket**: Optional for reduced server load

## Security

### Authentication

- Dashboard requires API authentication for production use
- JWT tokens for session management
- Role-based access control for sensitive operations

### CORS Configuration

```python
# Configure CORS for dashboard access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Add your domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Rate Limiting

- Built-in rate limiting for API endpoints
- Configurable limits per endpoint
- Protection against abuse and DDoS

## Production Deployment

### Docker Configuration

```dockerfile
FROM python:3.9-slim

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . /app
WORKDIR /app

EXPOSE 8000
CMD ["uvicorn", "fxml4.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Nginx Reverse Proxy

```nginx
location /api/ {
    proxy_pass http://localhost:8000/api/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}

location /dashboard {
    proxy_pass http://localhost:8000/dashboard;
}

location /ws {
    proxy_pass http://localhost:8000/ws;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
}
```

### Monitoring in Production

- **Health Checks**: Configure load balancer health checks
- **Alerting**: Set up alerts for system failures
- **Logging**: Centralized logging with ELK stack or similar
- **Metrics**: Export metrics to Prometheus/Grafana

## Support

For issues or questions:

1. Check the troubleshooting section above
2. Review API documentation at `/docs`
3. Check system logs for error details
4. Verify configuration files and dependencies
