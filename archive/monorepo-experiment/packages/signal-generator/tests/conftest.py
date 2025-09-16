"""Shared fixtures and configuration for signal-generator tests."""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock
import ta


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    import asyncio
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def market_data_generator():
    """Factory for generating different types of market data."""
    def _generate(
        pattern="random",
        periods=100,
        freq="5min",
        start_price=1.0850,
        volatility=0.0002
    ):
        """Generate market data with specified pattern."""
        dates = pd.date_range(end=datetime.now(), periods=periods, freq=freq)
        
        if pattern == "trending_up":
            # Upward trend
            trend = np.linspace(0, 0.01, periods)
            noise = np.random.randn(periods) * volatility
            close = start_price + trend + noise
            
        elif pattern == "trending_down":
            # Downward trend
            trend = np.linspace(0, -0.01, periods)
            noise = np.random.randn(periods) * volatility
            close = start_price + trend + noise
            
        elif pattern == "ranging":
            # Sideways movement
            cycle = np.sin(np.linspace(0, 4*np.pi, periods)) * 0.002
            noise = np.random.randn(periods) * volatility * 0.5
            close = start_price + cycle + noise
            
        elif pattern == "volatile":
            # High volatility
            close = start_price + np.random.randn(periods).cumsum() * volatility * 2
            
        else:  # random
            close = start_price + np.random.randn(periods).cumsum() * volatility
        
        # Generate OHLC
        open_price = np.roll(close, 1)
        open_price[0] = close[0]
        
        high = np.maximum(open_price, close) + abs(np.random.randn(periods) * volatility * 0.5)
        low = np.minimum(open_price, close) - abs(np.random.randn(periods) * volatility * 0.5)
        
        # Generate volume with some correlation to price movement
        price_change = abs(close - open_price)
        volume_base = 5000 + price_change * 1000000
        volume = (volume_base + np.random.randint(-1000, 1000, periods)).astype(int)
        volume = np.maximum(volume, 100)  # Ensure positive volume
        
        df = pd.DataFrame({
            'open': open_price,
            'high': high,
            'low': low,
            'close': close,
            'volume': volume
        }, index=dates)
        
        return df
    
    return _generate


@pytest.fixture
def add_technical_indicators():
    """Add technical indicators to price data."""
    def _add_indicators(df, indicators=None):
        """Add specified technical indicators."""
        if indicators is None:
            indicators = ['sma', 'rsi', 'macd', 'bb', 'atr']
        
        result = df.copy()
        
        if 'sma' in indicators:
            result['sma_20'] = ta.trend.sma_indicator(result['close'], window=20)
            result['sma_50'] = ta.trend.sma_indicator(result['close'], window=50)
            result['ema_12'] = ta.trend.ema_indicator(result['close'], window=12)
            result['ema_26'] = ta.trend.ema_indicator(result['close'], window=26)
        
        if 'rsi' in indicators:
            result['rsi_14'] = ta.momentum.RSIIndicator(result['close']).rsi()
        
        if 'macd' in indicators:
            macd = ta.trend.MACD(result['close'])
            result['macd'] = macd.macd()
            result['macd_signal'] = macd.macd_signal()
            result['macd_diff'] = macd.macd_diff()
        
        if 'bb' in indicators:
            bb = ta.volatility.BollingerBands(result['close'])
            result['bb_upper'] = bb.bollinger_hband()
            result['bb_middle'] = bb.bollinger_mavg()
            result['bb_lower'] = bb.bollinger_lband()
        
        if 'atr' in indicators:
            result['atr_14'] = ta.volatility.AverageTrueRange(
                result['high'], result['low'], result['close']
            ).average_true_range()
        
        # Fill NaN values
        result = result.fillna(method='ffill').fillna(method='bfill')
        
        return result
    
    return _add_indicators


@pytest.fixture
def signal_validator():
    """Validate signal properties."""
    def _validate(signal):
        """Validate a single signal."""
        errors = []
        
        # Check required attributes
        required_attrs = ['timestamp', 'symbol', 'signal_type', 'source', 
                         'confidence', 'price', 'metadata']
        for attr in required_attrs:
            if not hasattr(signal, attr):
                errors.append(f"Missing attribute: {attr}")
        
        # Check confidence range
        if hasattr(signal, 'confidence'):
            if not 0 <= signal.confidence <= 1:
                errors.append(f"Invalid confidence: {signal.confidence}")
        
        # Check metadata is dict
        if hasattr(signal, 'metadata'):
            if not isinstance(signal.metadata, dict):
                errors.append("Metadata must be a dictionary")
        
        return errors
    
    return _validate


@pytest.fixture
def mock_model_factory():
    """Factory for creating mock ML models."""
    def _create_model(
        name="mock_model",
        accuracy=0.7,
        feature_names=None,
        prediction_pattern="balanced"
    ):
        """Create a mock ML model with specified behavior."""
        model = Mock()
        model.name = name
        model.accuracy = accuracy
        
        if feature_names is None:
            feature_names = ["close", "volume", "rsi_14", "macd"]
        model.feature_names = feature_names
        
        def predict_proba(X):
            """Generate predictions based on pattern."""
            n_samples = len(X)
            predictions = []
            
            for i in range(n_samples):
                if prediction_pattern == "bullish":
                    # Mostly buy signals
                    if np.random.random() < accuracy:
                        predictions.append([0.1, 0.2, 0.7])
                    else:
                        predictions.append([0.4, 0.4, 0.2])
                
                elif prediction_pattern == "bearish":
                    # Mostly sell signals
                    if np.random.random() < accuracy:
                        predictions.append([0.7, 0.2, 0.1])
                    else:
                        predictions.append([0.2, 0.4, 0.4])
                
                else:  # balanced
                    # Mixed signals
                    r = np.random.random()
                    if r < 0.3:
                        predictions.append([0.1, 0.2, 0.7])  # Buy
                    elif r < 0.6:
                        predictions.append([0.7, 0.2, 0.1])  # Sell
                    else:
                        predictions.append([0.3, 0.4, 0.3])  # No signal
            
            return np.array(predictions)
        
        model.predict_proba = predict_proba
        model.predict = lambda X: np.argmax(predict_proba(X), axis=1)
        
        return model
    
    return _create_model


@pytest.fixture
def performance_metrics():
    """Calculate performance metrics for signals."""
    def _calculate(signals_df, actual_prices):
        """Calculate signal performance metrics."""
        if signals_df.empty:
            return {
                "total_signals": 0,
                "buy_signals": 0,
                "sell_signals": 0,
                "avg_confidence": 0,
                "signal_accuracy": 0
            }
        
        metrics = {
            "total_signals": len(signals_df),
            "buy_signals": len(signals_df[signals_df['signal_type'] == 'BUY']),
            "sell_signals": len(signals_df[signals_df['signal_type'] == 'SELL']),
            "avg_confidence": signals_df['confidence'].mean(),
            "confidence_std": signals_df['confidence'].std(),
            "sources": signals_df['source'].unique().tolist()
        }
        
        # Calculate signal accuracy if we have price data
        if actual_prices is not None and len(signals_df) > 0:
            correct_signals = 0
            
            for idx, signal in signals_df.iterrows():
                # Find next price after signal
                future_prices = actual_prices[actual_prices.index > idx]
                
                if len(future_prices) >= 10:  # Need at least 10 future bars
                    future_price = future_prices.iloc[10]['close']
                    current_price = signal['price']
                    
                    if signal['signal_type'] == 'BUY' and future_price > current_price:
                        correct_signals += 1
                    elif signal['signal_type'] == 'SELL' and future_price < current_price:
                        correct_signals += 1
            
            metrics["signal_accuracy"] = correct_signals / len(signals_df) if len(signals_df) > 0 else 0
        
        return metrics
    
    return _calculate


@pytest.fixture
def signal_backtester():
    """Simple backtester for signals."""
    def _backtest(signals_df, price_data, initial_balance=10000, position_size=0.1):
        """Run simple backtest on signals."""
        if signals_df.empty:
            return {
                "final_balance": initial_balance,
                "total_trades": 0,
                "winning_trades": 0,
                "total_pnl": 0,
                "sharpe_ratio": 0
            }
        
        balance = initial_balance
        position = 0
        entry_price = 0
        trades = []
        
        # Merge signals with price data
        combined = price_data.join(signals_df.set_index('timestamp'), how='left')
        
        for idx, row in combined.iterrows():
            if pd.notna(row.get('signal_type')):
                if row['signal_type'] == 'BUY' and position == 0:
                    # Enter long position
                    position = balance * position_size / row['close']
                    entry_price = row['close']
                    
                elif row['signal_type'] == 'SELL' and position > 0:
                    # Close long position
                    exit_price = row['close']
                    pnl = position * (exit_price - entry_price)
                    balance += pnl
                    
                    trades.append({
                        "entry_price": entry_price,
                        "exit_price": exit_price,
                        "pnl": pnl,
                        "return": (exit_price - entry_price) / entry_price
                    })
                    
                    position = 0
        
        # Calculate metrics
        total_trades = len(trades)
        winning_trades = len([t for t in trades if t['pnl'] > 0])
        total_pnl = sum(t['pnl'] for t in trades)
        
        # Calculate Sharpe ratio (simplified)
        if trades:
            returns = [t['return'] for t in trades]
            sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252) if np.std(returns) > 0 else 0
        else:
            sharpe = 0
        
        return {
            "final_balance": balance,
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "win_rate": winning_trades / total_trades if total_trades > 0 else 0,
            "total_pnl": total_pnl,
            "sharpe_ratio": sharpe,
            "trades": trades
        }
    
    return _backtest


# Test markers
pytest.mark.unit = pytest.mark.unit
pytest.mark.integration = pytest.mark.integration
pytest.mark.slow = pytest.mark.slow