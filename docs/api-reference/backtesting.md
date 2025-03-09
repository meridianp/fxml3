# Backtesting API Reference

This document provides detailed API reference for the FXML3 backtesting framework classes and methods.

## WaveBacktester

The main class for backtesting Elliott Wave pattern detection algorithms with realistic market simulation.

```python
class WaveBacktester:
    def __init__(
        self,
        data_loader: Optional[ForexDataLoader] = None,
        wave_analyzer: Optional[ElliottWaveAnalyzer] = None,
        fractal_handler: Optional[FractalDegreeHandler] = None,
        slippage_model: str = "normal",
        spread_model: str = "fixed",
        commission_model: str = "fixed",
    ):
        """Initialize the wave backtester with realistic market simulation.
        
        Args:
            data_loader: ForexDataLoader instance for fetching historical data
            wave_analyzer: ElliottWaveAnalyzer instance for detecting waves
            fractal_handler: FractalDegreeHandler for multi-timeframe analysis
            slippage_model: Model for simulating slippage ('none', 'fixed', 'normal', 'pareto')
            spread_model: Model for simulating bid-ask spreads ('fixed', 'variable', 'volatile')
            commission_model: Model for applying trading commissions ('none', 'fixed', 'percentage')
        """
```

### Key Methods

#### Run Rolling Window Backtest

```python
def run_rolling_window_backtest(
    self,
    data: pd.DataFrame,
    window_size: int = 100,
    step_size: int = 20,
    prediction_horizon: int = 20,
    initial_capital: float = 10000.0,
    use_realistic_simulation: bool = True,
) -> Dict[str, Any]:
    """Run a rolling window backtest on the data with realistic simulation.
    
    Args:
        data: DataFrame with price data
        window_size: Size of the rolling window (number of bars)
        step_size: Number of bars to advance the window each iteration
        prediction_horizon: Number of bars to predict into the future
        initial_capital: Initial capital for performance calculation
        use_realistic_simulation: Whether to apply realistic market simulation
        
    Returns:
        Dictionary with backtest results
    """
```

#### Run Walk-Forward Analysis

```python
def run_walk_forward_analysis(
    self,
    symbol: str,
    start_date: Union[str, datetime],
    end_date: Optional[Union[str, datetime]] = None,
    timeframe: str = "1D",
    n_folds: int = 5,
    window_size: int = 100,
    validation_size: int = 50,
    step_size: int = 20,
    prediction_horizon: int = 20,
    use_realistic_simulation: bool = True,
    initial_capital: float = 10000.0,
) -> Dict[str, Any]:
    """Run walk-forward analysis to validate strategy robustness on out-of-sample data.
    
    Args:
        symbol: Symbol to analyze
        start_date: Start date for historical data
        end_date: End date for historical data
        timeframe: Timeframe to use for analysis
        n_folds: Number of walk-forward windows
        window_size: Size of each training window
        validation_size: Size of each validation window
        step_size: Step size for rolling window analysis within each training window
        prediction_horizon: Number of bars to predict into the future
        use_realistic_simulation: Whether to use realistic market simulation
        initial_capital: Initial capital for performance calculation
        
    Returns:
        Dictionary with walk-forward analysis results
    """
```

#### Run Cross-Market Validation

```python
def run_cross_market_validation(
    self,
    symbols: List[str],
    start_date: Union[str, datetime],
    end_date: Optional[Union[str, datetime]] = None,
    timeframe: str = "1D",
    window_size: int = 100,
    step_size: int = 20,
    prediction_horizon: int = 20,
    use_realistic_simulation: bool = True,
    initial_capital: float = 10000.0,
) -> Dict[str, Any]:
    """Run cross-market validation to test strategy robustness across different markets.
    
    Args:
        symbols: List of symbols to validate on
        start_date: Start date for historical data
        end_date: End date for historical data
        timeframe: Timeframe to use for analysis
        window_size: Size of the rolling window
        step_size: Step size for rolling window analysis
        prediction_horizon: Number of bars to predict into the future
        use_realistic_simulation: Whether to use realistic market simulation
        initial_capital: Initial capital for performance calculation
        
    Returns:
        Dictionary with cross-market validation results
    """
```

#### Run Monte Carlo Simulation

```python
def run_monte_carlo_simulation(
    self,
    backtest_result: Dict[str, Any],
    num_simulations: int = 1000,
    confidence_level: float = 0.95,
    initial_capital: float = 10000.0,
) -> Dict[str, Any]:
    """Run Monte Carlo simulations to estimate strategy robustness.
    
    Args:
        backtest_result: Results from a previous backtest
        num_simulations: Number of Monte Carlo simulations to run
        confidence_level: Confidence level for statistical analysis
        initial_capital: Initial capital for simulations
        
    Returns:
        Dictionary with Monte Carlo simulation results
    """
```

### Market Simulation Methods

```python
def _calculate_slippage(self, price: float, direction: str) -> float:
    """Calculate realistic slippage based on the selected model.
    
    Args:
        price: Current price
        direction: Trade direction ("up" or "down")
        
    Returns:
        Slippage amount in price units
    """

def _calculate_spread(self, price_data: pd.Series, reference_price: float) -> float:
    """Calculate bid-ask spread based on the selected model.
    
    Args:
        price_data: Price data for the current bar
        reference_price: Reference price for calculations
        
    Returns:
        Spread amount in price units
    """

def _calculate_commission(self, position_size: float, price: float) -> float:
    """Calculate trading commission based on the selected model.
    
    Args:
        position_size: Size of the position in currency units
        price: Execution price
        
    Returns:
        Commission amount in account currency
    """
```

## PerformanceMetrics

Static utility class for calculating performance metrics from backtesting results.

```python
class PerformanceMetrics:
    @staticmethod
    def calculate_metrics(
        backtest_results: Dict,
        include_windows: bool = False,
    ) -> Dict:
        """Calculate performance metrics from backtest results.
        
        Args:
            backtest_results: Results from WaveBacktester
            include_windows: Whether to include per-window metrics
            
        Returns:
            Dictionary with calculated metrics
        """
```

### Key Methods

#### Calculate Profitability

```python
@staticmethod
def calculate_profitability(
    actual_outcomes: List[Dict],
    risk_per_trade: float = 0.02,  # 2% risk per trade
    account_size: float = 10000.0,  # $10,000 starting capital
    stop_multiplier: float = 1.5,   # Stop loss at 1.5x the max adverse move
    use_realistic_costs: bool = True,  # Include slippage, spread, commission
) -> Dict:
    """Calculate profitability metrics from prediction outcomes with realistic costs.
    
    Args:
        actual_outcomes: List of prediction outcome dictionaries
        risk_per_trade: Percentage of account to risk per trade
        account_size: Starting account size
        stop_multiplier: Multiplier to determine stop loss distance
        use_realistic_costs: Whether to include realistic trading costs
        
    Returns:
        Dictionary with profitability metrics
    """
```

#### Calculate Market Impact Metrics

```python
@staticmethod
def calculate_market_impact_metrics(
    actual_outcomes: List[Dict],
    atr_values: Optional[List[float]] = None,
) -> Dict:
    """Calculate metrics related to market impact and order execution quality.
    
    Args:
        actual_outcomes: List of prediction outcome dictionaries
        atr_values: Optional list of ATR values aligned with outcomes
        
    Returns:
        Dictionary with market impact metrics
    """
```

#### Calculate Multi-Timeframe Metrics

```python
@staticmethod
def calculate_multi_timeframe_metrics(
    multi_tf_results: Dict[str, Dict],
) -> Dict:
    """Calculate metrics across multiple timeframes.
    
    Args:
        multi_tf_results: Dictionary mapping timeframe to backtest results
        
    Returns:
        Dictionary with multi-timeframe metrics
    """
```

#### Calculate Risk/Reward Metrics

```python
@staticmethod
def calculate_risk_reward_metrics(
    actual_outcomes: List[Dict],
) -> Dict:
    """Calculate risk/reward metrics from actual outcomes.
    
    Args:
        actual_outcomes: List of prediction outcome dictionaries
        
    Returns:
        Dictionary with risk/reward metrics
    """
```

## ResultVisualizer

Static utility class for visualizing backtesting results.

```python
class ResultVisualizer:
    @staticmethod
    def plot_performance_metrics(
        metrics: Dict,
        title: str = "Backtesting Performance Metrics",
        figsize: Tuple[int, int] = (10, 6),
    ) -> plt.Figure:
        """Create a bar chart of performance metrics.
        
        Args:
            metrics: Dictionary with performance metrics
            title: Chart title
            figsize: Figure size
            
        Returns:
            Matplotlib figure
        """
```

### Key Visualization Methods

#### Plot Advanced Equity Curve

```python
@staticmethod
def plot_advanced_equity_curve(
    equity_curve: List[float],
    trade_outcomes: Optional[List[Dict]] = None,
    monte_carlo_results: Optional[Dict] = None,
    title: str = "Advanced Equity Curve with Monte Carlo Simulation",
    figsize: Tuple[int, int] = (14, 10),
) -> plt.Figure:
    """Plot an advanced equity curve with Monte Carlo simulation results.
    
    Args:
        equity_curve: List of equity values
        trade_outcomes: Optional list of trade outcomes with execution details
        monte_carlo_results: Optional Monte Carlo simulation results
        title: Chart title
        figsize: Figure size
        
    Returns:
        Matplotlib figure with multiple subplots showing equity curve and statistics
    """
```

#### Plot Walk-Forward Analysis

```python
@staticmethod
def plot_walk_forward_analysis(
    wfa_results: Dict[str, Any],
    title: str = "Walk-Forward Analysis Results",
    figsize: Tuple[int, int] = (14, 12),
) -> plt.Figure:
    """Plot the results of walk-forward analysis including performance and parameter stability.
    
    Args:
        wfa_results: Results from walk-forward analysis
        title: Chart title
        figsize: Figure size
        
    Returns:
        Matplotlib figure with multiple subplots
    """
```

#### Plot Cross-Market Validation

```python
@staticmethod
def plot_cross_market_validation(
    cross_market_results: Dict[str, Any],
    title: str = "Cross-Market Validation Results",
    figsize: Tuple[int, int] = (14, 12),
) -> plt.Figure:
    """Plot the results of cross-market validation to assess strategy robustness.
    
    Args:
        cross_market_results: Results from cross-market validation
        title: Chart title
        figsize: Figure size
        
    Returns:
        Matplotlib figure with multiple subplots
    """
```

#### Plot Interactive Results

```python
@staticmethod
def plot_interactive_results(
    backtest_results: Dict,
    metrics: Dict,
    title: str = "Interactive Backtesting Results",
) -> go.Figure:
    """Create an interactive dashboard of backtesting results.
    
    Args:
        backtest_results: Dictionary with backtesting results
        metrics: Dictionary with performance metrics
        title: Dashboard title
        
    Returns:
        Plotly figure
    """
```

#### Plot Prediction Examples

```python
@staticmethod
def plot_prediction_examples(
    price_data: pd.DataFrame,
    wave_points: Dict,
    predictions: List[Dict],
    actual_outcomes: List[Dict],
    num_examples: int = 3,
    title: str = "Prediction Examples",
) -> go.Figure:
    """Plot examples of predictions with actual outcomes.
    
    Args:
        price_data: DataFrame with price data
        wave_points: Dictionary with wave points
        predictions: List of prediction dictionaries
        actual_outcomes: List of actual outcome dictionaries
        num_examples: Number of examples to plot
        title: Chart title
        
    Returns:
        Plotly figure
    """
```

## BacktestAgent

A specialized agent for backtesting within the multi-agent system that integrates with other agents to provide comprehensive strategy validation.

```python
class BacktestAgent:
    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        knowledge_base: Optional[KnowledgeBase] = None,
        config: Dict = None,
    ):
        """Initialize the BacktestAgent with LLM integration.
        
        Args:
            llm_client: Optional LLMClient for analysis enhancement
            knowledge_base: Optional KnowledgeBase for retrieving relevant information
            config: Configuration dictionary for agent behavior
        """
```

### Key Methods

#### Process Task

```python
def process_task(
    self,
    task: Dict,
) -> Dict:
    """Process a backtesting task received from the agent coordinator.
    
    Args:
        task: Dictionary containing task information with structure:
            {
                "type": "backtest_request",
                "data": {
                    "symbol": "EURUSD",
                    "timeframe": "H1",
                    "start_date": "2021-01-01",
                    "end_date": "2022-12-31",
                    "strategy": {...},
                    "validation_methods": ["monte_carlo", "walk_forward"]
                }
            }
            
    Returns:
        Dictionary with task results
    """
```

#### Run Backtest

```python
def run_backtest(
    self,
    symbol: str,
    timeframe: str,
    start_date: Union[str, datetime],
    end_date: Optional[Union[str, datetime]] = None,
    strategy: Dict = None,
    wave_patterns: List[Dict] = None,
    validation_methods: List[str] = None,
    capital: float = 10000.0,
) -> Dict:
    """Run a comprehensive backtest with statistical validation.
    
    Args:
        symbol: Trading symbol
        timeframe: Chart timeframe
        start_date: Backtest start date
        end_date: Backtest end date
        strategy: Strategy configuration
        wave_patterns: Elliott Wave patterns from WaveDetectionAgent
        validation_methods: List of validation methods to apply
        capital: Initial capital
        
    Returns:
        Dictionary with comprehensive backtest results
    """
```

#### Analyze Results

```python
def analyze_results(
    self, 
    backtest_results: Dict,
    include_strengths_weaknesses: bool = True,
    include_improvement_suggestions: bool = True,
) -> Dict:
    """Use LLM to analyze backtest results and provide enhanced insights.
    
    Args:
        backtest_results: Backtesting results dictionary
        include_strengths_weaknesses: Whether to include strengths and weaknesses analysis
        include_improvement_suggestions: Whether to include strategy improvement suggestions
        
    Returns:
        Dictionary with LLM-enhanced analysis
    """
```

#### Generate Strategy Report

```python
def generate_strategy_report(
    self,
    backtest_results: Dict,
    metrics: Dict,
    wave_patterns: Optional[List[Dict]] = None,
    format: str = "markdown",
) -> str:
    """Generate a comprehensive strategy performance report.
    
    Args:
        backtest_results: Backtesting results dictionary
        metrics: Performance metrics dictionary
        wave_patterns: Optional list of wave patterns used in the strategy
        format: Output format ('markdown', 'html', 'text')
        
    Returns:
        Formatted strategy report
    """
```

#### Validate Against Market Regimes

```python
def validate_against_market_regimes(
    self,
    strategy: Dict,
    market_regimes: List[Dict],
) -> Dict:
    """Validate strategy performance across different market regimes.
    
    Args:
        strategy: Strategy configuration
        market_regimes: List of market regime periods to test
        
    Returns:
        Dictionary with validation results
    """
```