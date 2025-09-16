# fxml4-trade-manager

Trade management service for the fxml4 trading system.

## Features

- Position lifecycle management
- Risk monitoring and enforcement
- P&L tracking
- Exit strategy management
- Multi-broker support

## Installation

```bash
pip install fxml4-trade-manager
```

## Usage

```python
from fxml4_trade_manager import TradeManager
from fxml4_trade_manager.position import Position
from fxml4_trade_manager.risk import RiskMonitor

# Initialize trade manager
trade_manager = TradeManager()

# Create a position
position = await trade_manager.create_position(
    symbol="EURUSD",
    side="BUY",
    quantity=10000,
    entry_price=1.0950
)

# Monitor risk
risk_monitor = RiskMonitor()
violations = await risk_monitor.check_position_risk(position)
```

## Architecture

The trade manager consists of several components:

- **PositionManager**: Handles position lifecycle
- **RiskMonitor**: Real-time risk monitoring
- **ExitManager**: Manages stops and targets
- **PnLTracker**: Tracks performance metrics

## Configuration

Configure via environment variables:

- `FXML4_MAX_POSITIONS`: Maximum open positions
- `FXML4_RISK_PER_TRADE`: Risk per trade (%)
- `FXML4_DAILY_LOSS_LIMIT`: Daily loss limit (%)

## Testing

```bash
pytest tests/
```