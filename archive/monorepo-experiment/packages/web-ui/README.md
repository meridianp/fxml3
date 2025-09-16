# FXML4 Web UI

Web interface and REST API for the FXML4 trading system.

## Features

### REST API (FastAPI)
- Authentication and authorization
- Market data endpoints
- Signal generation API
- Backtesting API
- Position management
- Performance analytics
- WebSocket support for real-time data

### Web Dashboard (Streamlit)
- Real-time market monitoring
- Signal visualization
- Backtest results viewer
- Performance analytics dashboard
- Position tracking
- Risk metrics display

## Installation

```bash
poetry install
```

## Running the Services

### Start API Server

```bash
# Development
poetry run uvicorn fxml4_web.api.main:app --reload --port 8000

# Production
poetry run uvicorn fxml4_web.api.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Start Streamlit Dashboard

```bash
poetry run streamlit run src/fxml4_web/ui/app.py --server.port 8501
```

## API Documentation

Once the API is running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## API Endpoints

### Authentication
- `POST /api/v1/auth/login` - User login
- `POST /api/v1/auth/refresh` - Refresh token
- `POST /api/v1/auth/logout` - User logout

### Market Data
- `GET /api/v1/market/symbols` - List available symbols
- `GET /api/v1/market/data/{symbol}` - Get market data
- `WS /api/v1/market/stream` - WebSocket stream

### Trading
- `POST /api/v1/signals/generate` - Generate signals
- `GET /api/v1/positions` - Get current positions
- `POST /api/v1/orders` - Place order
- `GET /api/v1/orders/{order_id}` - Get order status

### Backtesting
- `POST /api/v1/backtest/run` - Run backtest
- `GET /api/v1/backtest/{backtest_id}` - Get results
- `GET /api/v1/backtest/{backtest_id}/report` - Download report

### Analytics
- `GET /api/v1/analytics/performance` - Performance metrics
- `GET /api/v1/analytics/risk` - Risk metrics
- `GET /api/v1/analytics/trades` - Trade history

## Dashboard Features

### Home Page
- System status
- Active positions
- Recent signals
- P&L summary

### Market View
- Real-time price charts
- Technical indicators
- Signal overlays
- Multi-timeframe analysis

### Backtesting
- Strategy configuration
- Parameter optimization
- Results visualization
- Performance comparison

### Analytics
- Equity curve
- Drawdown analysis
- Trade distribution
- Risk metrics

## Development

```bash
# Run tests
poetry run pytest

# Format code
poetry run black src tests
poetry run isort src tests

# Type checking
poetry run mypy src
```

## Configuration

Environment variables:
- `FXML4_API_HOST`: API host (default: 0.0.0.0)
- `FXML4_API_PORT`: API port (default: 8000)
- `FXML4_SECRET_KEY`: JWT secret key
- `FXML4_DATABASE_URL`: Database connection string
- `FXML4_REDIS_URL`: Redis connection for caching