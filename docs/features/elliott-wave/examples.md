# Elliott Wave Examples

This page provides practical examples of using FXML4's Elliott Wave analysis system in various trading scenarios.

## Basic Analysis Example

### Simple Wave Detection

```python
import pandas as pd
from fxml4.wave_analysis.elliott_wave import ElliottWaveAnalyzer

# Load market data
df = pd.read_parquet('data/features/EURUSD_4h_features_advanced.parquet')

# Initialize analyzer
analyzer = ElliottWaveAnalyzer()

# Run analysis on recent data
recent_data = df.last('30D')
result = analyzer.analyze(recent_data)

# Print results
if result.best_pattern:
    print(f"Pattern Type: {result.best_pattern.pattern_type}")
    print(f"Confidence: {result.best_pattern.confidence:.2%}")
    print(f"Wave Position: {result.best_pattern.current_wave}")
    print(f"Direction: {result.best_pattern.direction}")
else:
    print("No clear Elliott Wave pattern detected")
```

## Visual Analysis Example

### Complete Visual Elliott Wave Analysis

```python
from scripts.elliott_wave_visual_enhanced import VisualElliottWaveAnalyzer
import pandas as pd

# Load data
symbol = "GBPUSD"
df = pd.read_parquet(f'data/features/{symbol}_4h_features_advanced.parquet')

# Get last 30 days of data
analysis_period = df['2024-06-01':'2024-06-30']

# Initialize visual analyzer
analyzer = VisualElliottWaveAnalyzer()

# Run complete analysis
print(f"Analyzing {symbol}...")
results = analyzer.analyze_complete(analysis_period, symbol)

# Extract key information
algo_analysis = results['algorithmic_analysis']
llm_analysis = results['llm_analysis']
decision = results['trading_decision']

# Display results
print("\n=== ANALYSIS RESULTS ===")
print(f"Patterns Found: {len(algo_analysis['patterns'])}")

if algo_analysis['best_pattern']:
    pattern = algo_analysis['best_pattern']
    print(f"\nBest Pattern:")
    print(f"  Type: {pattern['pattern_type']}")
    print(f"  Confidence: {pattern['confidence']:.2%}")

print(f"\nLLM Analysis:")
print(f"  Wave Quality: {llm_analysis.get('wave_count', {}).get('quality', 'N/A')}/10")

print(f"\nTrading Decision:")
print(f"  Action: {decision['action']}")
print(f"  Confidence: {decision['confidence']*100:.1f}%")

if decision['action'] != 'HOLD':
    print(f"  Entry: {decision['entry']:.5f}")
    print(f"  Stop Loss: {decision['stop_loss']:.5f}")
    print(f"  Targets: {[f'{t:.5f}' for t in decision['targets']]}")
    print(f"  Risk/Reward: 1:{decision['risk_reward']:.1f}")

# Chart saved automatically
print(f"\nChart saved to: {results['chart_path']}")
```

## Hybrid Approach Example

### Optimal Elliott Wave Implementation

```python
from scripts.elliott_wave_optimal_hybrid import OptimalElliottWaveSystem
import pandas as pd

class ElliottWaveTradingBot:
    """Example trading bot using Elliott Wave analysis."""

    def __init__(self):
        self.ew_system = OptimalElliottWaveSystem()
        self.positions = {}

    def analyze_symbol(self, symbol: str, data: pd.DataFrame):
        """Analyze a symbol and generate trading signals."""

        print(f"\n{'='*60}")
        print(f"Analyzing {symbol}")
        print(f"{'='*60}")

        # Run optimal analysis
        analysis = self.ew_system.analyze_with_optimal_approach(data, symbol)

        # Extract components
        algo_waves = analysis['algorithmic_waves']
        visual_analysis = analysis['chart_analysis']
        decision = analysis['trading_decision']

        # Display wave patterns found
        if analysis['wave_patterns']:
            print(f"\nWave Patterns Detected:")
            for pattern in analysis['wave_patterns'][:3]:
                print(f"  - {pattern['wave_type']}: confidence {pattern['confidence']:.2f}")

        # Show trading decision
        self._display_trading_decision(symbol, decision)

        # Execute trade if confident
        if decision['confidence'] >= 0.7:
            self._execute_trade(symbol, decision)

        return decision

    def _display_trading_decision(self, symbol: str, decision: dict):
        """Display trading decision details."""

        print(f"\nTrading Decision for {symbol}:")
        print(f"  Action: {decision['action']}")
        print(f"  Confidence: {decision['confidence']*100:.1f}%")

        if decision['action'] != 'HOLD':
            print(f"  Entry Price: {decision['entry']:.5f}")
            print(f"  Stop Loss: {decision['stop_loss']:.5f}")
            print(f"  Take Profit Levels:")
            for i, target in enumerate(decision['targets'], 1):
                print(f"    TP{i}: {target:.5f}")
            print(f"  Risk/Reward Ratio: 1:{decision['risk_reward']:.1f}")
            print(f"  Reasoning: {decision['reasoning']}")

    def _execute_trade(self, symbol: str, decision: dict):
        """Simulate trade execution."""

        if symbol in self.positions:
            print(f"\n⚠️  Already have position in {symbol}")
            return

        print(f"\n✅ Executing {decision['action']} trade for {symbol}")

        self.positions[symbol] = {
            'direction': decision['action'],
            'entry': decision['entry'],
            'stop_loss': decision['stop_loss'],
            'targets': decision['targets'],
            'timestamp': pd.Timestamp.now()
        }

# Example usage
bot = ElliottWaveTradingBot()

# Analyze multiple symbols
symbols = ['EURUSD', 'GBPUSD', 'USDJPY']

for symbol in symbols:
    # Load data
    df = pd.read_parquet(f'data/features/{symbol}_4h_features_advanced.parquet')
    recent_data = df.last('2W')  # Last 2 weeks

    # Analyze and potentially trade
    bot.analyze_symbol(symbol, recent_data)
```

## Multi-Timeframe Example

### Confirming Patterns Across Timeframes

```python
from scripts.elliott_wave_optimal_hybrid import OptimalElliottWaveSystem
import pandas as pd

def multi_timeframe_analysis(symbol: str):
    """Analyze Elliott Waves across multiple timeframes."""

    system = OptimalElliottWaveSystem()
    timeframes = ['1H', '4H', '1D']
    results = {}

    print(f"\nMulti-Timeframe Elliott Wave Analysis for {symbol}")
    print("="*60)

    for tf in timeframes:
        # Load data for timeframe
        df = pd.read_parquet(f'data/features/{symbol}_{tf}_features_advanced.parquet')
        data = df.last('30D')

        print(f"\n{tf} Timeframe:")

        # Run analysis
        analysis = system.analyze_with_optimal_approach(data, symbol)
        decision = analysis['trading_decision']

        # Store results
        results[tf] = {
            'action': decision['action'],
            'confidence': decision['confidence'],
            'patterns': len(analysis['wave_patterns'])
        }

        print(f"  Action: {decision['action']}")
        print(f"  Confidence: {decision['confidence']*100:.1f}%")
        print(f"  Patterns: {len(analysis['wave_patterns'])}")

    # Analyze alignment
    print("\n" + "="*60)
    print("Multi-Timeframe Summary:")

    # Check if all timeframes agree
    actions = [r['action'] for r in results.values()]
    unique_actions = set(actions)

    if len(unique_actions) == 1 and 'HOLD' not in unique_actions:
        print(f"✅ Strong Signal: All timeframes agree on {actions[0]}")
        avg_confidence = sum(r['confidence'] for r in results.values()) / len(results)
        print(f"   Average Confidence: {avg_confidence*100:.1f}%")
    else:
        print("⚠️  Mixed signals across timeframes")
        for tf, result in results.items():
            print(f"   {tf}: {result['action']} ({result['confidence']*100:.1f}%)")

    return results

# Run multi-timeframe analysis
results = multi_timeframe_analysis('EURUSD')
```

## Real-Time Monitoring Example

### Live Elliott Wave Monitoring

```python
import asyncio
from datetime import datetime
from scripts.elliott_wave_optimal_hybrid import OptimalElliottWaveSystem

class ElliottWaveMonitor:
    """Monitor markets for Elliott Wave patterns in real-time."""

    def __init__(self, symbols: list, interval_minutes: int = 15):
        self.symbols = symbols
        self.interval = interval_minutes * 60  # Convert to seconds
        self.system = OptimalElliottWaveSystem()
        self.last_signals = {}

    async def monitor(self):
        """Continuously monitor for Elliott Wave patterns."""

        print(f"Starting Elliott Wave Monitor")
        print(f"Symbols: {', '.join(self.symbols)}")
        print(f"Update interval: {self.interval/60} minutes")
        print("="*60)

        while True:
            for symbol in self.symbols:
                await self.check_symbol(symbol)

            print(f"\n⏰ Next update in {self.interval/60} minutes...")
            await asyncio.sleep(self.interval)

    async def check_symbol(self, symbol: str):
        """Check a symbol for new patterns."""

        try:
            # Load latest data
            df = pd.read_parquet(f'data/features/{symbol}_4h_features_advanced.parquet')
            recent_data = df.last('2W')

            # Run analysis
            analysis = self.system.analyze_with_optimal_approach(recent_data, symbol)
            decision = analysis['trading_decision']

            # Check for signal change
            last_signal = self.last_signals.get(symbol, {'action': 'NONE'})

            if decision['action'] != last_signal['action']:
                await self.alert_signal_change(symbol, last_signal, decision)
                self.last_signals[symbol] = decision

        except Exception as e:
            print(f"❌ Error analyzing {symbol}: {e}")

    async def alert_signal_change(self, symbol: str, old_signal: dict, new_signal: dict):
        """Alert when signal changes."""

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        print(f"\n🔔 SIGNAL CHANGE DETECTED - {symbol} at {timestamp}")
        print(f"   Previous: {old_signal.get('action', 'NONE')}")
        print(f"   New Signal: {new_signal['action']}")
        print(f"   Confidence: {new_signal['confidence']*100:.1f}%")

        if new_signal['action'] != 'HOLD':
            print(f"   Entry: {new_signal['entry']:.5f}")
            print(f"   Stop: {new_signal['stop_loss']:.5f}")
            print(f"   Target: {new_signal['targets'][0]:.5f}")

        # Here you could add:
        # - Email notifications
        # - Telegram alerts
        # - Database logging
        # - Auto-trading execution

# Run the monitor
async def main():
    monitor = ElliottWaveMonitor(
        symbols=['EURUSD', 'GBPUSD', 'USDJPY'],
        interval_minutes=15
    )
    await monitor.monitor()

# Uncomment to run:
# asyncio.run(main())
```

## Backtesting Example

### Backtest Elliott Wave Strategy

```python
from fxml4.backtesting.strategies import BaseStrategy
from fxml4.backtesting.event_engine import EventDrivenBacktester
from scripts.elliott_wave_optimal_hybrid import OptimalElliottWaveSystem

class ElliottWaveStrategy(BaseStrategy):
    """Backtesting strategy using Elliott Wave analysis."""

    def __init__(self, confidence_threshold=0.7):
        super().__init__()
        self.ew_system = OptimalElliottWaveSystem()
        self.confidence_threshold = confidence_threshold
        self.analysis_frequency = 20  # Analyze every 20 bars
        self.bar_count = 0

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """Generate trading signals based on Elliott Wave analysis."""

        signals = pd.Series(index=data.index, data=0)

        # We need at least 100 bars for analysis
        if len(data) < 100:
            return signals

        self.bar_count += 1

        # Only analyze at specified frequency
        if self.bar_count % self.analysis_frequency != 0:
            return signals

        # Get recent window for analysis
        window = data.iloc[-100:]

        # Run Elliott Wave analysis
        analysis = self.ew_system.analyze_with_optimal_approach(window, self.symbol)
        decision = analysis['trading_decision']

        # Generate signal if confident enough
        if decision['confidence'] >= self.confidence_threshold:
            if decision['action'] == 'LONG':
                signals.iloc[-1] = 1
                self.stop_loss = decision['stop_loss']
                self.take_profit = decision['targets'][0]
            elif decision['action'] == 'SHORT':
                signals.iloc[-1] = -1
                self.stop_loss = decision['stop_loss']
                self.take_profit = decision['targets'][0]

        return signals

# Run backtest
def run_elliott_wave_backtest(symbol='EURUSD', start_date='2024-01-01', end_date='2024-06-30'):
    """Run backtest of Elliott Wave strategy."""

    # Load data
    df = pd.read_parquet(f'data/features/{symbol}_4h_features_advanced.parquet')
    backtest_data = df[start_date:end_date]

    # Create strategy
    strategy = ElliottWaveStrategy(confidence_threshold=0.7)

    # Configure backtester
    backtester = EventDrivenBacktester(
        data=backtest_data,
        strategy=strategy,
        initial_capital=10000,
        commission=0.00005,  # 0.5 pips
        slippage=0.00002    # 0.2 pips
    )

    # Run backtest
    print(f"Running Elliott Wave backtest for {symbol}")
    print(f"Period: {start_date} to {end_date}")
    print("="*60)

    results = backtester.run()

    # Display results
    print(f"\nBacktest Results:")
    print(f"  Total Return: {results['total_return']:.2%}")
    print(f"  Sharpe Ratio: {results['sharpe_ratio']:.2f}")
    print(f"  Max Drawdown: {results['max_drawdown']:.2%}")
    print(f"  Win Rate: {results['win_rate']:.1%}")
    print(f"  Total Trades: {results['total_trades']}")

    return results

# Run the backtest
results = run_elliott_wave_backtest()
```

## Pattern-Specific Examples

### Detecting Specific Patterns

```python
from fxml4.wave_analysis.elliott_wave import ElliottWaveAnalyzer

def find_specific_patterns(data: pd.DataFrame, pattern_types: list):
    """Find specific Elliott Wave patterns."""

    analyzer = ElliottWaveAnalyzer()
    result = analyzer.analyze(data)

    found_patterns = []

    for pattern in result.patterns:
        if pattern.pattern_type in pattern_types:
            found_patterns.append({
                'type': pattern.pattern_type,
                'confidence': pattern.confidence,
                'start': pattern.start_time,
                'end': pattern.end_time,
                'waves': pattern.waves
            })

    return found_patterns

# Example: Find ending diagonals (reversal patterns)
df = pd.read_parquet('data/features/EURUSD_4h_features_advanced.parquet')
recent_data = df.last('30D')

reversal_patterns = find_specific_patterns(
    recent_data,
    ['ending_diagonal', 'truncated_fifth']
)

if reversal_patterns:
    print("Potential Reversal Patterns Found:")
    for pattern in reversal_patterns:
        print(f"\n{pattern['type'].upper()}")
        print(f"  Confidence: {pattern['confidence']:.2%}")
        print(f"  Period: {pattern['start']} to {pattern['end']}")
        print(f"  Wave Count: {len(pattern['waves'])}")
else:
    print("No reversal patterns detected")
```

## API Integration Example

### Elliott Wave API Endpoint

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import pandas as pd
from scripts.elliott_wave_optimal_hybrid import OptimalElliottWaveSystem

app = FastAPI()

class ElliottWaveRequest(BaseModel):
    symbol: str
    timeframe: str = "4H"
    lookback_days: int = 30
    use_visual: bool = True

class ElliottWaveResponse(BaseModel):
    symbol: str
    pattern_type: Optional[str]
    confidence: float
    action: str
    entry: Optional[float]
    stop_loss: Optional[float]
    targets: Optional[list]
    analysis_time: str

@app.post("/elliott-wave/analyze", response_model=ElliottWaveResponse)
async def analyze_elliott_wave(request: ElliottWaveRequest):
    """Analyze Elliott Wave patterns for a symbol."""

    try:
        # Load data
        df = pd.read_parquet(
            f'data/features/{request.symbol}_{request.timeframe}_features_advanced.parquet'
        )

        # Get recent data
        analysis_data = df.last(f'{request.lookback_days}D')

        # Run analysis
        system = OptimalElliottWaveSystem()

        if request.use_visual:
            results = system.analyze_with_optimal_approach(
                analysis_data,
                request.symbol
            )
        else:
            # Algorithmic only
            results = system.analyze_algorithmic_only(
                analysis_data,
                request.symbol
            )

        # Extract decision
        decision = results['trading_decision']
        patterns = results.get('wave_patterns', [])

        # Prepare response
        response = ElliottWaveResponse(
            symbol=request.symbol,
            pattern_type=patterns[0]['wave_type'] if patterns else None,
            confidence=decision['confidence'],
            action=decision['action'],
            entry=decision.get('entry'),
            stop_loss=decision.get('stop_loss'),
            targets=decision.get('targets'),
            analysis_time=pd.Timestamp.now().isoformat()
        )

        return response

    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Data not found for {request.symbol}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Example usage:
# POST /elliott-wave/analyze
# {
#     "symbol": "EURUSD",
#     "timeframe": "4H",
#     "lookback_days": 30,
#     "use_visual": true
# }
```

## Best Practices Summary

1. **Data Quality**
   - Always use clean, continuous data
   - Ensure sufficient history (minimum 100 bars)
   - Handle gaps and anomalies

2. **Analysis Frequency**
   - Don't over-analyze (every 4-24 hours is usually sufficient)
   - Cache results to avoid redundant API calls
   - Use appropriate timeframes for your trading style

3. **Risk Management**
   - Always use stop losses at wave invalidation points
   - Size positions based on confidence
   - Don't trade low-confidence patterns

4. **Multi-Timeframe Confirmation**
   - Check higher timeframes for trend context
   - Ensure pattern alignment across timeframes
   - Use lower timeframes for entry timing

5. **Continuous Improvement**
   - Track pattern performance
   - Adjust confidence thresholds based on results
   - Build a library of successful patterns

These examples demonstrate the flexibility and power of FXML4's Elliott Wave implementation. Start with simple analysis and gradually incorporate more advanced features as you become comfortable with the system.
