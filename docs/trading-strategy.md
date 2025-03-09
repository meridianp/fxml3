# Trading Strategy

This document provides information about the trading strategy components of FXML3, including entry/exit signal generation, risk management, and position sizing.

## Overview

The FXML3 strategy module implements a comprehensive trading strategy system based on Elliott Wave patterns. The system is composed of several key components:

1. **Entry Signal Generation**: Identifies potential entry points based on Elliott Wave patterns
2. **Exit Signal Generation**: Determines optimal exit points for active positions
3. **Risk Management**: Calculates dynamic stop loss levels and manages trade risk
4. **Position Sizing**: Optimizes position sizes based on various algorithms
5. **Portfolio Management**: Manages multi-currency exposure and correlation (in progress)

## Entry Signal Generation

The `EntrySignalGenerator` class detects potential trade entry points based on various Elliott Wave patterns:

### Impulse Wave Entries
- Wave 3 start entries (typically the strongest trend wave)
- Wave 5 start entries (final impulse leg)
- Failed fifth wave setups (for potential reversals)
- Extended wave opportunities

### Corrective Wave Entries
- A-B-C pattern completion
- Triangle pattern breakouts
- Flat pattern entries
- Multiple correction patterns

### Advanced Pattern Recognition
- Nested wave pattern detection
- Fibonacci confluence entry points
- Multi-timeframe confirmation

Each entry signal includes detailed information such as:
- Entry price
- Suggested stop loss level
- Take profit target
- Risk/reward ratio
- Confidence level
- Pattern type and wave degree

## Exit Signal Generation

The `ExitSignalGenerator` class provides various exit strategies for active positions:

### Exit Types
- **Take Profit Exits**: Based on Fibonacci extensions and price targets
- **Stop Loss Exits**: Dynamic protection against adverse moves
- **Pattern Completion Exits**: Exiting when a pattern completes
- **Trailing Stop Exits**: Following the trend with adaptive stops
- **Time-Based Exits**: Maximum holding period exits

### Partial Exit Strategy
The system supports partial position exits at key Fibonacci levels, allowing for:
- Locking in partial profits at specific levels
- Reducing exposure while letting winners run
- Scaling out methodically based on market structure

## Risk Management

The `RiskManager` class implements sophisticated risk management techniques:

### Dynamic Stop Loss Calculation
- Wave structure-based stop losses (e.g., below Wave 2 for Wave 3 entries)
- Pattern-specific stop placement based on Elliott Wave rules
- Technical level integration (support/resistance)

### Volatility-Adjusted Risk
- ATR-based volatility measurement
- Historical vs. current volatility comparison
- Risk adjustment based on market conditions

### Pattern Invalidation
- Detecting when wave patterns become invalid
- Automatic adjustment of risk parameters
- Multi-level invalidation severity classification

### Multi-Timeframe Risk Assessment
- Higher timeframe key level identification
- Stop loss validation across multiple timeframes
- Support/resistance integration from various timeframes

## Position Sizing

The `PositionSizer` class offers multiple position sizing algorithms:

### Fixed Risk Position Sizing
- Risk a fixed percentage of account on each trade
- Adjustments based on signal strength and confidence

### Kelly Criterion Optimization
- Optimal position sizing based on win rate and profit/loss ratio
- Half-Kelly implementation for more conservative sizing
- Dynamic win rate calculation from trade history

### Volatility-Adjusted Position Sizing
- Larger positions in low-volatility conditions
- Smaller positions in high-volatility conditions
- ATR-based volatility measurement

### Scaling Methods
- Systematic position scaling into entries
- Geometric distribution of entry levels
- Partial position exits at predetermined levels

## Usage Examples

### Entry Signal Generation
```python
from fxml3.strategy import EntrySignalGenerator, SignalType

# Initialize the generator
generator = EntrySignalGenerator()

# Analyze price data for entry signals
signals = generator.analyze(price_data, timeframe="1H")

# Process generated signals
for timestamp, signal_list in signals.items():
    for signal in signal_list:
        print(f"Entry Signal: {signal.pattern} at {signal.entry_price}")
        print(f"Stop Loss: {signal.stop_loss}, Take Profit: {signal.take_profit}")
```

### Dynamic Stop Loss Calculation
```python
from fxml3.strategy import RiskManager

# Initialize the risk manager
risk_manager = RiskManager()

# Calculate dynamic stop loss for a signal
stop_loss, meta = risk_manager.calculate_dynamic_stop_loss(
    data=price_data,
    entry_signal=signal,
    account_size=10000.0
)

print(f"Dynamic Stop Loss: {stop_loss}")
print(f"Calculation Method: {meta['calculation_method']}")
```

### Position Sizing with Kelly Criterion
```python
from fxml3.strategy import PositionSizer, PositionSizingMethod

# Initialize position sizer
sizer = PositionSizer(kelly_fraction=0.5)  # Half-Kelly for conservatism

# Calculate position size
position = sizer.calculate_position_size(
    entry_signal=signal,
    account_size=10000.0,
    method=PositionSizingMethod.KELLY
)

print(f"Position Size: {position.size}")
print(f"Risk Percentage: {position.risk_percentage:.2%}")
print(f"Win Rate Used: {position.metadata['win_rate']:.2f}")
```

## Future Developments

The following components are currently under development:

1. **Portfolio-Level Strategy Logic**
   - Multi-currency portfolio construction
   - Correlation-based diversification
   - Maximum exposure rules and limits

2. **Advanced Backtesting**
   - Realistic market simulation (slippage, spread)
   - Monte Carlo analysis
   - Strategy validation framework