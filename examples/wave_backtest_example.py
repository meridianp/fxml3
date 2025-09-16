#!/usr/bin/env python
"""Example demonstrating backtesting with the combined strategy using wave analysis.

This example shows how to set up a backtesting environment using the combined strategy
with ML, sentiment, and wave signal generators.
"""

import logging
import os
import sys
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from fxml4.backtesting.combined_strategy import CombinedStrategy
from fxml4.backtesting.event_driven_engine import EventDrivenEngine
from fxml4.config import get_config
from fxml4.strategy.combined_signal_generator import CombinedSignalGenerator


# Mock signal generator classes for testing
class MLSignalGenerator:
    """Mock ML signal generator for testing."""

    def __init__(self, model=None, config=None):
        self.model = model
        self.config = config or {}

    def generate_signals(self, data, **kwargs):
        """Generate mock ML signals."""
        import pandas as pd

        from fxml4.strategy.integrated_strategy import Signal, SignalSource, SignalType

        # Return a simple mock signal
        if len(data) > 0:
            timestamp = (
                data.index[-1]
                if isinstance(data.index, pd.DatetimeIndex)
                else pd.Timestamp.now()
            )
            return [
                Signal(
                    signal_type=SignalType.ENTRY_LONG,
                    strength=0.8,
                    source=SignalSource.ML,
                    timestamp=timestamp,
                    symbol="GBPUSD",
                    timeframe="1h",
                    metadata={"feature_importance": {"close": 0.6, "sma_10": 0.4}},
                )
            ]
        return []


class SentimentSignalGenerator:
    """Mock sentiment signal generator for testing."""

    def __init__(self, sentiment_analyzer=None, config=None):
        self.sentiment_analyzer = sentiment_analyzer
        self.config = config or {}

    def generate_signals(self, data, news_data=None, **kwargs):
        """Generate mock sentiment signals."""
        import pandas as pd

        from fxml4.strategy.integrated_strategy import Signal, SignalSource, SignalType

        # Return a simple mock signal
        if len(data) > 0:
            timestamp = (
                data.index[-1]
                if isinstance(data.index, pd.DatetimeIndex)
                else pd.Timestamp.now()
            )
            return [
                Signal(
                    signal_type=SignalType.ENTRY_LONG,
                    strength=0.7,
                    source=SignalSource.SENTIMENT,
                    timestamp=timestamp,
                    symbol="GBPUSD",
                    timeframe="1h",
                    metadata={"sentiment_score": 0.6, "source": "mock"},
                )
            ]
        return []


class EnhancedWaveSignalGenerator:
    """Mock enhanced wave signal generator for testing."""

    def __init__(self, wave_validator=None, config=None):
        self.wave_validator = wave_validator
        self.config = config or {}

    def generate_signals(self, data, news_data=None, **kwargs):
        """Generate mock wave signals."""
        import pandas as pd

        from fxml4.strategy.integrated_strategy import Signal, SignalSource, SignalType

        # Return a simple mock signal with stop loss and take profit
        if len(data) > 0:
            current_price = data["close"].iloc[-1]
            timestamp = (
                data.index[-1]
                if isinstance(data.index, pd.DatetimeIndex)
                else pd.Timestamp.now()
            )
            return [
                Signal(
                    signal_type=SignalType.ENTRY_LONG,
                    strength=0.9,
                    source=SignalSource.WAVE,
                    timestamp=timestamp,
                    symbol="GBPUSD",
                    timeframe="1h",
                    metadata={
                        "wave_pattern": "IMPULSE",
                        "wave_position": "correction_end_c",
                        "stop_loss": current_price * 0.995,
                        "take_profit": {"target": current_price * 1.015},
                    },
                )
            ]
        return []


from fxml4.ml.models import load_model
from fxml4.wave_analysis.elliott_wave import ElliottWaveAnalyzer


# Mock classes for testing
class SentimentWaveValidator:
    """Mock SentimentWaveValidator for testing."""

    def __init__(self, wave_analyzer, sentiment_analyzer, rag=None, config=None):
        self.wave_analyzer = wave_analyzer
        self.sentiment_analyzer = sentiment_analyzer
        self.rag = rag
        self.config = config or {}

    def analyze_with_sentiment(self, price_data, news_data=None):
        """Mock analysis that returns dummy results."""
        return {
            "sentiment_score": 0.5,
            "patterns": [],
            "validation": [
                {
                    "pattern": {"wave_type": "IMPULSE", "position": "END"},
                    "is_valid": True,
                    "confidence": 0.75,
                    "details": {"sentiment_match": True},
                }
            ],
            "combined_score": 0.75,
        }


class MarketSentimentAnalyzer:
    """Mock MarketSentimentAnalyzer for testing."""

    def __init__(self, config=None):
        self.config = config or {}

    def analyze_sentiment(self, data):
        """Mock sentiment analysis that returns a dummy score."""
        return 0.5


# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def load_test_data(symbol="GBPUSD", start_date="2024-01-01", end_date="2024-03-01"):
    """Load test data for backtesting.

    Args:
        symbol: Trading symbol.
        start_date: Start date.
        end_date: End date.

    Returns:
        DataFrame with data.
    """
    # Load example data
    try:
        # Try to load from input directory with real data
        input_path = f"input/C_{symbol}/year=2024/month=3/C_{symbol}_year=2024_month=3_day=1.parquet"
        if os.path.exists(input_path):
            data = pd.read_parquet(input_path)
            data = data.iloc[-5000:]  # Use last 5000 rows for testing
            logger.info(f"Loaded real data for {symbol}, shape: {data.shape}")
        else:
            # Generate synthetic data
            logger.info("Generating synthetic data")
            np.random.seed(42)
            periods = 5000

            # Create date range
            dates = pd.date_range(start=start_date, end=end_date, periods=periods)

            # Generate random price data with trend and noise
            base_price = 1.2000  # Starting price for GBPUSD
            trend = (
                np.linspace(0, 0.05, periods)
                + np.sin(np.linspace(0, 10, periods)) * 0.02
            )
            noise = np.random.normal(0, 0.0010, periods)

            # Calculate OHLC data
            close = base_price + trend + noise
            high = close + np.abs(np.random.normal(0, 0.0015, periods))
            low = close - np.abs(np.random.normal(0, 0.0015, periods))
            open_price = close - np.random.normal(0, 0.0010, periods)

            # Create volume with some randomness
            volume = np.random.normal(1000, 200, periods)
            volume = np.abs(volume) + 100  # Ensure positive values

            # Create DataFrame
            data = pd.DataFrame(
                {
                    "time": dates,
                    "open": open_price,
                    "high": high,
                    "low": low,
                    "close": close,
                    "volume": volume,
                    "symbol": symbol,
                    "timeframe": "1h",
                }
            )

            # Add some basic indicators
            data["sma_10"] = data["close"].rolling(window=10).mean()
            data["sma_20"] = data["close"].rolling(window=20).mean()
            data["rsi"] = calculate_rsi(data["close"], 14)

            logger.info(f"Generated synthetic data, shape: {data.shape}")

        return data

    except Exception as e:
        logger.exception(f"Error loading data: {e}")
        raise


def calculate_rsi(series, period=14):
    """Calculate RSI for a series.

    Args:
        series: Price series.
        period: RSI period.

    Returns:
        Series with RSI values.
    """
    delta = series.diff()
    gain = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss = -delta.where(delta < 0, 0).rolling(window=period).mean()

    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))

    return rsi


def generate_news_data(price_data):
    """Generate synthetic news data for backtesting.

    Args:
        price_data: Price data DataFrame.

    Returns:
        DataFrame with synthetic news data.
    """
    # Create a subset of dates from the price data
    dates = price_data["time"].dt.date.unique()[
        5::30
    ]  # Every 30th day, starting from 5th

    # Create news entries
    news = []
    for date in dates:
        # Determine sentiment based on price movement in the next few days
        date_str = pd.to_datetime(date)
        next_week_mask = (price_data["time"] >= date_str) & (
            price_data["time"] < date_str + pd.Timedelta(days=7)
        )

        if next_week_mask.sum() > 0:
            next_week_data = price_data.loc[next_week_mask]
            price_change = (
                next_week_data["close"].iloc[-1] / next_week_data["close"].iloc[0] - 1
            ) * 100

            # Generate sentiment based on price change
            if price_change > 1.5:
                sentiment = "very bullish"
                title = f"Analysts Extremely Positive on {price_data['symbol'].iloc[0]} Outlook"
                content = f"Market analysts are projecting significant gains for {price_data['symbol'].iloc[0]} in the coming weeks due to strong economic indicators."
            elif price_change > 0.5:
                sentiment = "bullish"
                title = f"{price_data['symbol'].iloc[0]} Showing Positive Signs"
                content = f"Technical analysts are noting several positive indicators for {price_data['symbol'].iloc[0]} suggesting upward momentum."
            elif price_change > -0.5:
                sentiment = "neutral"
                title = f"{price_data['symbol'].iloc[0]} Expected to Trade Sideways"
                content = f"The market consensus for {price_data['symbol'].iloc[0]} is mixed with equal bullish and bearish factors at play."
            elif price_change > -1.5:
                sentiment = "bearish"
                title = f"Headwinds Expected for {price_data['symbol'].iloc[0]}"
                content = f"Economic data suggests potential challenges for {price_data['symbol'].iloc[0]} in the near term with possible downward pressure."
            else:
                sentiment = "very bearish"
                title = f"Analysts Warn of Significant Downside Risk for {price_data['symbol'].iloc[0]}"
                content = f"Market conditions are deteriorating for {price_data['symbol'].iloc[0]} with several technical indicators pointing to continued weakness."

            news.append(
                {
                    "date": date,
                    "title": title,
                    "content": content,
                    "sentiment": sentiment,
                    "source": "Synthetic News Generator",
                    "symbol": price_data["symbol"].iloc[0],
                }
            )

    # Convert to DataFrame
    news_df = pd.DataFrame(news)
    if not news_df.empty:
        news_df["date"] = pd.to_datetime(news_df["date"])

    return news_df


def prepare_signal_generator(data):
    """Prepare the combined signal generator with all components.

    Args:
        data: Price data for initialization.

    Returns:
        Combined signal generator instance.
    """
    # Create mock ML model or load if available
    try:
        ml_model = load_model(
            "models/gbpusd_random_forest_20250313_112208_metadata.json"
        )
        logger.info("Loaded ML model from file")
    except Exception as e:
        logger.warning(f"Could not load ML model: {e}. Using mock model.")

        class MockModel:
            def predict(self, X):
                # Random predictions
                return np.random.choice([-1, 0, 1], size=len(X))

            def predict_proba(self, X):
                # Random probabilities
                probs = np.random.random((len(X), 3))
                return probs / probs.sum(axis=1, keepdims=True)

        ml_model = MockModel()

    # Create ML signal generator
    ml_signal_generator = MLSignalGenerator(
        model=ml_model,
        config={
            "prediction_threshold": 0.6,
            "features": ["rsi", "sma_10", "sma_20", "close", "high", "low", "open"],
        },
    )

    # Create sentiment analyzer
    sentiment_analyzer = MarketSentimentAnalyzer(
        config={"default_source": "price_action"}
    )

    # Create sentiment signal generator
    sentiment_signal_generator = SentimentSignalGenerator(
        sentiment_analyzer=sentiment_analyzer, config={"threshold": 0.6}
    )

    # Create Elliott Wave analyzer
    elliott_wave_analyzer = ElliottWaveAnalyzer(
        config={"max_wave_count": 5, "min_confidence": 0.5}
    )

    # Create SentimentWaveValidator
    sentiment_wave_validator = SentimentWaveValidator(
        wave_analyzer=elliott_wave_analyzer,
        sentiment_analyzer=sentiment_analyzer,
        rag=None,  # We don't need RAG for this example
        config={"sentiment_weight": 0.4, "wave_weight": 0.6, "min_confidence": 0.5},
    )

    # Create EnhancedWaveSignalGenerator
    wave_signal_generator = EnhancedWaveSignalGenerator(
        wave_validator=sentiment_wave_validator,
        config={"threshold": 0.6, "max_stop_loss_pct": 1.5, "use_news_sentiment": True},
    )

    # Create CombinedSignalGenerator
    combined_signal_generator = CombinedSignalGenerator(
        ml_signal_generator=ml_signal_generator,
        sentiment_signal_generator=sentiment_signal_generator,
        wave_signal_generator=wave_signal_generator,
        config={
            "method": "weighted",
            "weights": {
                "ml": 0.4,
                "sentiment": 0.2,
                "wave": 0.4,
            },
            "min_confidence": 0.6,
            "min_agreement": 2,
            "require_consensus": True,
            "use_adaptive_weights": True,
        },
    )

    return combined_signal_generator


def backtest_strategy_adapter(symbol, current_bar, market_data, portfolio):
    """Adapter function for the event-driven backtest engine.

    Args:
        symbol: Market symbol.
        current_bar: Current price bar.
        market_data: Historical market data.
        portfolio: Portfolio instance.

    Returns:
        Dictionary of signals for the event-driven engine.
    """
    # Access the combined strategy
    strategy = backtest_strategy_adapter.combined_strategy

    # Generate signals from the strategy
    signal_events = strategy.generate_signals(
        symbol, current_bar, market_data, portfolio
    )

    # Format signals for the event-driven engine
    formatted_signals = {}
    for signal_event in signal_events:
        signal_type = signal_event.signal_type
        if "LONG" in signal_type or "SHORT" in signal_type:
            is_entry = "ENTRY" in signal_type
            is_long = "LONG" in signal_type

            if is_entry:
                formatted_signals["entry"] = {
                    "side": "buy" if is_long else "sell",
                    "risk_pct": strategy.config.get("max_risk_pct", 2.0) / 100,
                    "stop_loss": signal_event.metadata.get("stop_loss"),
                    "position_sizing": "risk_pct",
                    "quantity": (
                        signal_event.quantity
                        if hasattr(signal_event, "quantity")
                        else None
                    ),
                }
            else:  # Exit
                formatted_signals["exit"] = {
                    "reason": signal_event.metadata.get("reason", "Signal exit"),
                }

    return formatted_signals


def run_backtest(data, combined_signal_generator, initial_capital=10000.0):
    """Run an event-driven backtest with the combined strategy.

    Args:
        data: Market data.
        combined_signal_generator: Signal generator.
        initial_capital: Initial capital.

    Returns:
        Backtest results.
    """
    # Create combined strategy
    combined_strategy = CombinedStrategy(
        signal_generator=combined_signal_generator,
        config={
            "use_dynamic_stops": True,
            "use_wave_stops": True,
            "position_size_pct": 2.0,
            "max_risk_pct": 2.0,
            "adjustable_stops": True,
            "signal_cooldown": 24,  # 24 hours
            "min_signal_strength": 0.6,
        },
    )

    # Set up adapter function
    backtest_strategy_adapter.combined_strategy = combined_strategy

    # Create event-driven engine
    engine = EventDrivenEngine(
        strategy=backtest_strategy_adapter,
        initial_capital=initial_capital,
        fee_model="percentage_0.1",  # 0.1% fee
    )

    # Prepare data for backtesting
    if "time" in data.columns:
        date_col = "time"
    else:
        date_col = data.index.name if data.index.name else "index"
        data = data.reset_index()

    # Load data into backtesting engine
    engine.load_data(data, date_col=date_col)

    # Run backtest
    logger.info("Starting backtest...")
    results = engine.run()
    logger.info(f"Backtest completed. Final equity: ${results.final_capital:.2f}")

    return results


def plot_results(results):
    """Plot backtest results.

    Args:
        results: Backtest results object.

    Returns:
        None.
    """
    # Create figure
    fig, axes = plt.subplots(
        3, 1, figsize=(12, 18), gridspec_kw={"height_ratios": [3, 1, 1]}
    )

    # Plot equity curve
    equity_curve = results.equity_curve
    if isinstance(equity_curve, list):
        equity_curve = pd.DataFrame(equity_curve)

    if (
        not equity_curve.empty
        and "timestamp" in equity_curve.columns
        and "equity" in equity_curve.columns
    ):
        axes[0].plot(equity_curve["timestamp"], equity_curve["equity"], label="Equity")
        axes[0].set_title("Equity Curve")
        axes[0].set_xlabel("Date")
        axes[0].set_ylabel("Equity ($)")
        axes[0].grid(True)
        axes[0].legend()

    # Plot drawdowns
    if hasattr(results, "drawdown_analysis") and results.drawdown_analysis is not None:
        drawdown_df = results.drawdown_analysis.get("drawdowns_df")
        if drawdown_df is not None and not drawdown_df.empty:
            axes[1].fill_between(
                drawdown_df.index,
                0,
                drawdown_df["drawdown_pct"] * 100,
                color="red",
                alpha=0.3,
            )
            axes[1].set_title("Drawdowns")
            axes[1].set_xlabel("Date")
            axes[1].set_ylabel("Drawdown (%)")
            axes[1].grid(True)

    # Plot trades
    trades = results.trades
    if trades:
        if isinstance(trades, list):
            # Convert to DataFrame if it's a list of trade objects
            trades_data = []
            for trade in trades:
                if hasattr(trade, "entry_timestamp") and hasattr(trade, "pnl"):
                    trades_data.append(
                        {
                            "entry_timestamp": trade.entry_timestamp,
                            "pnl": trade.pnl,
                            "side": (
                                trade.side.value
                                if hasattr(trade.side, "value")
                                else trade.side
                            ),
                        }
                    )
                elif (
                    isinstance(trade, dict)
                    and "open_time" in trade
                    and "realized_pnl" in trade
                ):
                    trades_data.append(
                        {
                            "entry_timestamp": trade["open_time"],
                            "pnl": trade["realized_pnl"],
                            "side": trade["side"],
                        }
                    )

            if trades_data:
                trades_df = pd.DataFrame(trades_data)

                # Plot PnL per trade
                axes[2].bar(
                    range(len(trades_df)),
                    trades_df["pnl"],
                    color=trades_df["pnl"].apply(lambda x: "green" if x > 0 else "red"),
                )
                axes[2].set_title("Trade PnL")
                axes[2].set_xlabel("Trade #")
                axes[2].set_ylabel("PnL ($)")
                axes[2].grid(True)

    # Adjust layout and save
    plt.tight_layout()
    result_dir = Path("output/wave_backtest_results")
    result_dir.mkdir(exist_ok=True, parents=True)

    plt.savefig(
        result_dir / f"backtest_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    )

    # Show if in interactive mode
    if plt.isinteractive():
        plt.show()


def main():
    """Main function."""
    # Load test data
    data = load_test_data()

    # Generate synthetic news data
    news_data = generate_news_data(data)

    # Prepare combined signal generator
    combined_signal_generator = prepare_signal_generator(data)

    # Run backtest
    results = run_backtest(data, combined_signal_generator)

    # Plot results
    plot_results(results)

    # Print summary
    print("\n=== Backtest Results Summary ===")
    print(f"Initial capital: ${results.initial_capital:.2f}")
    print(f"Final capital: ${results.final_capital:.2f}")
    print(f"Total return: {results.total_return_pct:.2f}%")
    print(f"Max drawdown: {results.max_drawdown_pct:.2f}%")
    if hasattr(results, "sharpe_ratio"):
        print(f"Sharpe ratio: {results.sharpe_ratio:.2f}")
    if hasattr(results, "win_rate"):
        print(f"Win rate: {results.win_rate*100:.2f}%")
    print(f"Total trades: {len(results.trades)}")
    print("===============================\n")


if __name__ == "__main__":
    main()
