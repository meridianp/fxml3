# Elliott Wave Implementation Guide

This guide provides detailed instructions for implementing Elliott Wave analysis in your trading system using FXML4.

## Installation

### Prerequisites

```bash
# Required packages
pip install mplfinance matplotlib pandas numpy
pip install anthropic  # For Claude Opus 4

# Optional but recommended
pip install ta  # Technical indicators
pip install scipy  # Advanced calculations
```

### Environment Setup

```bash
# .env file configuration
ANTHROPIC_API_KEY=your_api_key_here
LLM_MODEL=claude-opus-4-20250514

# Optional settings
ELLIOTT_WAVE_CONFIDENCE_THRESHOLD=0.6
ELLIOTT_WAVE_USE_VISUAL=true
ELLIOTT_WAVE_CACHE_TTL=300
```

## Core Components

### 1. Elliott Wave Analyzer

The main algorithmic component:

```python
from fxml4.wave_analysis.elliott_wave import ElliottWaveAnalyzer

class ElliottWaveAnalyzer:
    """Core Elliott Wave pattern detection."""

    def __init__(self, min_wave_size=0.001, fibonacci_tolerance=0.02):
        self.min_wave_size = min_wave_size
        self.fibonacci_tolerance = fibonacci_tolerance
        self.wave_detector = WaveDetector()
        self.pattern_validator = PatternValidator()

    def analyze(self, price_data: pd.DataFrame) -> WaveAnalysisResult:
        """Analyze price data for Elliott Wave patterns."""

        # Step 1: Detect extremes
        extremes = self.detect_peaks_and_troughs(price_data)

        # Step 2: Compute waves
        waves = self.compute_waves(extremes)

        # Step 3: Find patterns
        impulse_patterns = self.find_impulse_waves(waves)
        corrective_patterns = self.find_corrective_waves(waves)

        # Step 4: Validate and score
        validated_patterns = self.validate_patterns(
            impulse_patterns + corrective_patterns
        )

        return WaveAnalysisResult(
            waves=waves,
            patterns=validated_patterns,
            best_pattern=self._select_best_pattern(validated_patterns)
        )
```

### 2. Chart Generator

Creates annotated technical charts:

```python
from fxml4.wave_analysis.chart_generator import ElliottWaveChartGenerator

class ElliottWaveChartGenerator:
    """Generate annotated charts for Elliott Wave analysis."""

    def generate_elliott_wave_chart(
        self,
        price_data: pd.DataFrame,
        wave_patterns: List[Dict],
        fibonacci_levels: Optional[Dict] = None,
        indicators: List[str] = ['volume', 'rsi'],
        title: str = "Elliott Wave Analysis"
    ) -> Tuple[plt.Figure, str]:
        """Generate comprehensive Elliott Wave chart."""

        # Create the base chart
        fig, axes = self._create_base_chart(price_data, indicators)

        # Add wave annotations
        self._add_wave_annotations(axes[0], price_data, wave_patterns)

        # Add Fibonacci levels
        if fibonacci_levels:
            self._add_fibonacci_levels(axes[0], fibonacci_levels)

        # Convert to base64
        base64_img = self._fig_to_base64(fig)

        return fig, base64_img
```

### 3. Visual Analyzer

Integrates with Claude Opus 4:

```python
from fxml4.llm_integration.llm_client import LLMClient

class VisualElliottWaveAnalyzer:
    """Visual analysis using Claude Opus 4."""

    def __init__(self):
        self.llm_client = LLMClient(provider="anthropic")
        self.wave_analyzer = ElliottWaveAnalyzer()
        self.chart_generator = ElliottWaveChartGenerator()

    def analyze_with_visual(
        self,
        price_data: pd.DataFrame,
        symbol: str = "EURUSD"
    ) -> Dict:
        """Complete visual Elliott Wave analysis."""

        # Run algorithmic analysis
        algo_result = self.wave_analyzer.analyze(price_data)

        # Generate chart
        fig, chart_base64 = self.chart_generator.generate_elliott_wave_chart(
            price_data,
            algo_result.patterns
        )

        # Get AI analysis
        visual_analysis = self._get_ai_analysis(
            chart_base64,
            algo_result,
            symbol
        )

        # Synthesize decision
        trading_decision = self._create_trading_decision(
            algo_result,
            visual_analysis,
            price_data
        )

        return {
            'algorithmic': algo_result.to_dict(),
            'visual': visual_analysis,
            'decision': trading_decision
        }
```

## Usage Examples

### Basic Usage

```python
import pandas as pd
from fxml4.wave_analysis.elliott_wave import ElliottWaveAnalyzer

# Load price data
df = pd.read_csv('EURUSD_4H.csv', parse_dates=['timestamp'])

# Initialize analyzer
analyzer = ElliottWaveAnalyzer()

# Run analysis
result = analyzer.analyze(df)

# Check results
if result.best_pattern:
    print(f"Pattern: {result.best_pattern.pattern_type}")
    print(f"Confidence: {result.best_pattern.confidence:.2%}")
    print(f"Direction: {result.best_pattern.direction}")
```

### Visual Analysis

```python
from scripts.elliott_wave_visual_enhanced import VisualElliottWaveAnalyzer

# Initialize visual analyzer
visual_analyzer = VisualElliottWaveAnalyzer()

# Run complete analysis
analysis = visual_analyzer.analyze_complete(df, "EURUSD")

# Get trading decision
decision = analysis['trading_decision']
print(f"Action: {decision['action']}")
print(f"Entry: {decision['entry']}")
print(f"Stop Loss: {decision['stop_loss']}")
print(f"Targets: {decision['targets']}")
```

### Hybrid Approach

```python
from scripts.elliott_wave_optimal_hybrid import OptimalElliottWaveSystem

# Initialize hybrid system
hybrid_system = OptimalElliottWaveSystem()

# Analyze with optimal approach
results = hybrid_system.analyze_with_optimal_approach(df, "EURUSD")

# Access different components
algo_waves = results['algorithmic_waves']
visual_analysis = results['chart_analysis']
final_decision = results['trading_decision']
```

## Integration with Trading System

### 1. Signal Generation

```python
class ElliottWaveSignalGenerator:
    """Generate trading signals from Elliott Wave analysis."""

    def __init__(self, confidence_threshold=0.6):
        self.analyzer = OptimalElliottWaveSystem()
        self.confidence_threshold = confidence_threshold

    def generate_signals(self, market_data: Dict[str, pd.DataFrame]) -> List[Signal]:
        """Generate signals for multiple symbols."""

        signals = []

        for symbol, data in market_data.items():
            # Run analysis
            analysis = self.analyzer.analyze_with_optimal_approach(data, symbol)

            # Check confidence
            decision = analysis['trading_decision']
            if decision['confidence'] >= self.confidence_threshold:
                signal = Signal(
                    symbol=symbol,
                    action=decision['action'],
                    entry=decision['entry'],
                    stop_loss=decision['stop_loss'],
                    targets=decision['targets'],
                    confidence=decision['confidence'],
                    strategy='elliott_wave'
                )
                signals.append(signal)

        return signals
```

### 2. Risk Management Integration

```python
def calculate_position_size(decision, account_balance, risk_per_trade=0.02):
    """Calculate position size based on Elliott Wave analysis."""

    # Base calculation
    risk_amount = account_balance * risk_per_trade
    stop_distance = abs(decision['entry'] - decision['stop_loss'])

    # Adjust for confidence
    confidence_multiplier = decision['confidence']

    # Calculate final position size
    position_size = (risk_amount / stop_distance) * confidence_multiplier

    return position_size
```

### 3. Backtesting Integration

```python
from fxml4.backtesting.strategies import BaseStrategy

class ElliottWaveStrategy(BaseStrategy):
    """Backtest strategy using Elliott Wave signals."""

    def __init__(self, visual_threshold=0.7):
        super().__init__()
        self.analyzer = OptimalElliottWaveSystem()
        self.visual_threshold = visual_threshold

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """Generate signals for backtesting."""

        signals = pd.Series(index=data.index, data=0)

        # Analyze in rolling windows
        window_size = 100
        step_size = 20

        for i in range(window_size, len(data), step_size):
            window_data = data.iloc[i-window_size:i]

            # Run analysis
            analysis = self.analyzer.analyze_with_optimal_approach(
                window_data,
                self.symbol
            )

            decision = analysis['trading_decision']

            # Set signal
            if decision['action'] == 'LONG':
                signals.iloc[i] = 1
            elif decision['action'] == 'SHORT':
                signals.iloc[i] = -1

        return signals
```

## Advanced Features

### 1. Multi-Timeframe Analysis

```python
def multi_timeframe_elliott_wave(symbol, timeframes=['1H', '4H', '1D']):
    """Analyze multiple timeframes for confirmation."""

    analyzer = OptimalElliottWaveSystem()
    results = {}

    for tf in timeframes:
        # Load data for timeframe
        data = load_data(symbol, tf)

        # Run analysis
        results[tf] = analyzer.analyze_with_optimal_approach(data, symbol)

    # Combine results
    combined_confidence = np.mean([
        r['trading_decision']['confidence']
        for r in results.values()
    ])

    # Check alignment
    directions = [
        r['trading_decision']['action']
        for r in results.values()
    ]

    if len(set(directions)) == 1:  # All agree
        confidence_boost = 1.2
    else:
        confidence_boost = 0.8

    return {
        'timeframe_results': results,
        'combined_confidence': combined_confidence * confidence_boost,
        'alignment': len(set(directions)) == 1
    }
```

### 2. Pattern Library

```python
class ElliottWavePatternLibrary:
    """Store and retrieve successful patterns."""

    def __init__(self, db_path='patterns.db'):
        self.db_path = db_path
        self.patterns = []

    def add_pattern(self, pattern, outcome):
        """Store pattern with its outcome."""

        self.patterns.append({
            'pattern': pattern,
            'outcome': outcome,
            'timestamp': datetime.now(),
            'symbol': pattern.symbol,
            'timeframe': pattern.timeframe
        })

    def find_similar_patterns(self, current_pattern, similarity_threshold=0.8):
        """Find historically similar patterns."""

        similar = []

        for stored in self.patterns:
            similarity = self._calculate_similarity(
                current_pattern,
                stored['pattern']
            )

            if similarity >= similarity_threshold:
                similar.append({
                    'pattern': stored,
                    'similarity': similarity,
                    'historical_outcome': stored['outcome']
                })

        return sorted(similar, key=lambda x: x['similarity'], reverse=True)
```

### 3. Real-Time Monitoring

```python
class ElliottWaveMonitor:
    """Monitor real-time data for Elliott Wave patterns."""

    def __init__(self, symbols, update_interval=300):
        self.symbols = symbols
        self.update_interval = update_interval
        self.analyzer = OptimalElliottWaveSystem()
        self.last_analysis = {}

    async def monitor(self):
        """Continuously monitor for patterns."""

        while True:
            for symbol in self.symbols:
                # Get latest data
                data = await self.get_live_data(symbol)

                # Check if enough new data
                if self.should_reanalyze(symbol, data):
                    # Run analysis
                    analysis = self.analyzer.analyze_with_optimal_approach(
                        data,
                        symbol
                    )

                    # Check for significant changes
                    if self.is_significant_change(symbol, analysis):
                        await self.send_alert(symbol, analysis)

                    # Store results
                    self.last_analysis[symbol] = analysis

            await asyncio.sleep(self.update_interval)
```

## Performance Optimization

### 1. Caching

```python
from functools import lru_cache
import hashlib

class CachedElliottWaveAnalyzer:
    """Analyzer with intelligent caching."""

    def __init__(self, cache_size=128):
        self.analyzer = OptimalElliottWaveSystem()
        self.cache_size = cache_size

    @lru_cache(maxsize=128)
    def _analyze_cached(self, data_hash, symbol):
        """Cached analysis based on data hash."""
        # This will only run if not in cache
        return self.analyzer.analyze_with_optimal_approach(
            self._reconstruct_data(data_hash),
            symbol
        )

    def analyze(self, data, symbol):
        """Analyze with caching."""
        # Create hash of data
        data_hash = self._hash_dataframe(data)

        # Use cached result if available
        return self._analyze_cached(data_hash, symbol)

    def _hash_dataframe(self, df):
        """Create hash of dataframe for caching."""
        return hashlib.md5(
            pd.util.hash_pandas_object(df, index=True).values
        ).hexdigest()
```

### 2. Batch Processing

```python
def batch_analyze_elliott_wave(symbols, timeframe='4H', max_concurrent=5):
    """Efficiently analyze multiple symbols."""

    import asyncio
    from concurrent.futures import ThreadPoolExecutor

    analyzer = OptimalElliottWaveSystem()
    executor = ThreadPoolExecutor(max_workers=max_concurrent)

    async def analyze_symbol(symbol):
        """Analyze single symbol asynchronously."""
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(
            executor,
            load_data,
            symbol,
            timeframe
        )

        result = await loop.run_in_executor(
            executor,
            analyzer.analyze_with_optimal_approach,
            data,
            symbol
        )

        return symbol, result

    async def run_batch():
        """Run all analyses concurrently."""
        tasks = [analyze_symbol(s) for s in symbols]
        results = await asyncio.gather(*tasks)
        return dict(results)

    return asyncio.run(run_batch())
```

## Testing

### Unit Tests

```python
import unittest
from fxml4.wave_analysis.elliott_wave import ElliottWaveAnalyzer

class TestElliottWaveAnalyzer(unittest.TestCase):
    def setUp(self):
        self.analyzer = ElliottWaveAnalyzer()

    def test_impulse_wave_detection(self):
        """Test detection of simple impulse wave."""
        # Create synthetic impulse wave data
        data = create_impulse_wave_data()

        result = self.analyzer.analyze(data)

        self.assertIsNotNone(result.best_pattern)
        self.assertEqual(result.best_pattern.pattern_type, 'impulse')
        self.assertGreater(result.best_pattern.confidence, 0.8)

    def test_corrective_wave_detection(self):
        """Test detection of ABC correction."""
        data = create_corrective_wave_data()

        result = self.analyzer.analyze(data)

        self.assertIsNotNone(result.best_pattern)
        self.assertEqual(result.best_pattern.pattern_type, 'zigzag')
```

### Integration Tests

```python
def test_visual_analysis_integration():
    """Test complete visual analysis workflow."""

    # Load test data
    test_data = pd.read_parquet('test_data/EURUSD_impulse_wave.parquet')

    # Run analysis
    analyzer = VisualElliottWaveAnalyzer()
    result = analyzer.analyze_with_visual(test_data, 'EURUSD')

    # Verify components
    assert 'algorithmic' in result
    assert 'visual' in result
    assert 'decision' in result

    # Check decision
    decision = result['decision']
    assert decision['action'] in ['LONG', 'SHORT', 'HOLD']
    assert 0 <= decision['confidence'] <= 1
    assert decision['stop_loss'] is not None
    assert len(decision['targets']) > 0
```

## Troubleshooting

### Common Issues

1. **Pattern Not Detected**
   ```python
   # Check wave size threshold
   analyzer = ElliottWaveAnalyzer(min_wave_size=0.0005)  # Lower threshold
   ```

2. **Visual Analysis Timeout**
   ```python
   # Increase timeout
   llm_client = LLMClient(
       provider="anthropic",
       timeout=60  # 60 seconds
   )
   ```

3. **Memory Issues with Large Datasets**
   ```python
   # Process in chunks
   chunk_size = 1000
   results = []
   for i in range(0, len(data), chunk_size):
       chunk = data.iloc[i:i+chunk_size]
       results.append(analyzer.analyze(chunk))
   ```

## Best Practices

1. **Data Quality**
   - Ensure clean, continuous data
   - Handle gaps appropriately
   - Use appropriate timeframes

2. **Parameter Tuning**
   - Adjust wave size for different markets
   - Tune Fibonacci tolerance
   - Set appropriate confidence thresholds

3. **Production Deployment**
   - Implement proper error handling
   - Set up monitoring and alerting
   - Use async processing for real-time
   - Cache results where appropriate

## Conclusion

The Elliott Wave implementation in FXML4 provides a robust, scalable solution for pattern recognition in forex markets. By following this guide, you can:

1. Set up the complete system
2. Integrate with your trading infrastructure
3. Optimize for your specific needs
4. Deploy in production environments

For further assistance, refer to the [examples](examples.md) or join our [community forum](https://github.com/meridianp/fxml4/discussions).
