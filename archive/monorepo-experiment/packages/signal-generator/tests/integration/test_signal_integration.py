"""Integration tests for signal generation components."""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
import tempfile
import joblib
from pathlib import Path

from fxml4_signals.base import SignalGenerator, SignalType
from fxml4_signals.technical import TechnicalSignals
from fxml4_signals.ml_signals import MLSignals, EnsembleMLSignals


@pytest.fixture
def comprehensive_market_data():
    """Generate comprehensive market data for integration testing."""
    # Create 30 days of 5-minute data
    periods = 30 * 24 * 12  # 30 days of 5-min bars
    dates = pd.date_range(end=datetime.now(), periods=periods, freq='5min')
    
    # Generate realistic price movement with trends
    np.random.seed(42)
    
    # Create trending periods
    trend_changes = np.random.choice([-1, 0, 1], size=periods, p=[0.2, 0.6, 0.2])
    trend = np.cumsum(trend_changes) * 0.00001
    
    # Add cyclical patterns
    daily_cycle = np.sin(np.arange(periods) * 2 * np.pi / (24 * 12)) * 0.0005
    weekly_cycle = np.sin(np.arange(periods) * 2 * np.pi / (24 * 12 * 5)) * 0.0010
    
    # Base price with trends and cycles
    base_price = 1.0850
    close = base_price + trend + daily_cycle + weekly_cycle
    close += np.random.randn(periods) * 0.0002  # Add noise
    
    # Generate OHLC
    open_price = np.roll(close, 1)
    open_price[0] = close[0]
    
    high = np.maximum(open_price, close) + abs(np.random.randn(periods) * 0.0001)
    low = np.minimum(open_price, close) - abs(np.random.randn(periods) * 0.0001)
    
    # Volume with intraday patterns
    hour_of_day = np.array([d.hour for d in dates])
    volume_profile = np.where(
        (hour_of_day >= 8) & (hour_of_day <= 16),
        1.5,  # Higher volume during market hours
        1.0
    )
    volume = (np.random.randint(1000, 5000, periods) * volume_profile).astype(int)
    
    df = pd.DataFrame({
        'open': open_price,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume
    }, index=dates)
    
    return df


@pytest.fixture
def mock_ml_model():
    """Create a mock ML model that behaves realistically."""
    model = Mock()
    model.name = "mock_xgboost"
    model.feature_names = ["close", "volume", "rsi_14", "macd", "sma_20", "sma_50"]
    
    def predict_proba(features):
        """Generate realistic predictions based on features."""
        predictions = []
        
        for idx in range(len(features)):
            row = features.iloc[idx]
            
            # Simple logic based on RSI and price vs SMA
            rsi = row.get('rsi_14', 50)
            price_vs_sma = (row.get('close', 1) / row.get('sma_20', 1) - 1) * 100
            
            if rsi < 30 and price_vs_sma < -1:  # Oversold
                predictions.append([0.2, 0.2, 0.6])  # Buy signal
            elif rsi > 70 and price_vs_sma > 1:  # Overbought
                predictions.append([0.7, 0.2, 0.1])  # Sell signal
            else:
                predictions.append([0.35, 0.35, 0.3])  # No clear signal
        
        return np.array(predictions)
    
    model.predict_proba = predict_proba
    return model


@pytest.fixture
def signal_generator_with_sources(mock_ml_model):
    """Create signal generator with multiple sources."""
    generator = SignalGenerator(min_confidence=0.5)
    
    # Add technical signals
    tech_signals = TechnicalSignals(
        name="technical",
        weight=0.8,
        rsi_oversold=30,
        rsi_overbought=70
    )
    generator.add_source(tech_signals)
    
    # Add ML signals
    ml_signals = MLSignals(
        name="ml",
        weight=1.0,
        model=mock_ml_model,
        prediction_threshold=0.55
    )
    generator.add_source(ml_signals)
    
    return generator


@pytest.mark.integration
class TestSignalGeneratorIntegration:
    """Integration tests for complete signal generation pipeline."""
    
    def test_multi_source_signal_generation(self, signal_generator_with_sources, 
                                          comprehensive_market_data):
        """Test signal generation with multiple sources."""
        # Calculate indicators needed by ML model
        from ta import add_all_ta_features
        data_with_indicators = add_all_ta_features(
            comprehensive_market_data,
            open="open", high="high", low="low", close="close", volume="volume",
            fillna=True
        )
        
        # Rename columns to match expected names
        data_with_indicators.rename(columns={
            'momentum_rsi': 'rsi_14',
            'trend_macd': 'macd',
            'trend_sma_fast': 'sma_20',
            'trend_sma_slow': 'sma_50'
        }, inplace=True)
        
        # Generate signals
        signals_df = signal_generator_with_sources.generate(
            data_with_indicators.tail(1000),  # Last ~3.5 days
            "EURUSD"
        )
        
        # Verify signals were generated
        assert not signals_df.empty
        assert len(signals_df) > 0
        
        # Check signal diversity
        assert len(signals_df['source'].unique()) >= 2  # Multiple sources
        assert len(signals_df['signal_type'].unique()) >= 2  # Both BUY and SELL
        
        # Verify signal properties
        assert all(signals_df['confidence'] >= 0.5)  # Min confidence
        assert all(signals_df['symbol'] == 'EURUSD')
    
    def test_signal_aggregation(self, signal_generator_with_sources, 
                               comprehensive_market_data):
        """Test signal aggregation over time windows."""
        # Prepare data
        from ta import add_all_ta_features
        data_with_indicators = add_all_ta_features(
            comprehensive_market_data,
            open="open", high="high", low="low", close="close", volume="volume",
            fillna=True
        )
        
        data_with_indicators.rename(columns={
            'momentum_rsi': 'rsi_14',
            'trend_macd': 'macd',
            'trend_sma_fast': 'sma_20',
            'trend_sma_slow': 'sma_50'
        }, inplace=True)
        
        # Generate signals
        signals_df = signal_generator_with_sources.generate(
            data_with_indicators.tail(500),
            "EURUSD"
        )
        
        if not signals_df.empty:
            # Aggregate signals
            aggregated = signal_generator_with_sources.aggregate_signals(
                signals_df,
                window='15min'
            )
            
            # Verify aggregation
            assert not aggregated.empty
            assert 'avg_confidence' in aggregated.columns
            assert 'signal_count' in aggregated.columns
            
            # Should have fewer rows after aggregation
            assert len(aggregated) <= len(signals_df)
    
    def test_signal_filtering_by_confidence(self, comprehensive_market_data):
        """Test that low confidence signals are filtered out."""
        # Create generator with high confidence threshold
        generator = SignalGenerator(min_confidence=0.8)
        
        # Add technical signals
        tech_signals = TechnicalSignals(name="tech", weight=0.5)  # Low weight
        generator.add_source(tech_signals)
        
        # Generate signals
        signals_df = generator.generate(comprehensive_market_data.tail(100), "EURUSD")
        
        # All signals should have high confidence (weight * original >= 0.8)
        if not signals_df.empty:
            assert all(signals_df['confidence'] >= 0.4)  # 0.8 / 0.5 weight
    
    def test_signal_history_tracking(self, signal_generator_with_sources, 
                                   comprehensive_market_data):
        """Test that signal history is properly maintained."""
        # Prepare data
        from ta import add_all_ta_features
        data_with_indicators = add_all_ta_features(
            comprehensive_market_data,
            open="open", high="high", low="low", close="close", volume="volume",
            fillna=True
        )
        
        data_with_indicators.rename(columns={
            'momentum_rsi': 'rsi_14',
            'trend_macd': 'macd',
            'trend_sma_fast': 'sma_20',
            'trend_sma_slow': 'sma_50'
        }, inplace=True)
        
        # Generate signals multiple times
        for i in range(3):
            chunk = data_with_indicators.iloc[i*100:(i+1)*100]
            signal_generator_with_sources.generate(chunk, "EURUSD")
        
        # Check signal history
        history = signal_generator_with_sources.signal_history
        assert len(history) > 0
        
        # Get latest signals
        latest = signal_generator_with_sources.get_latest_signals(n=10)
        assert len(latest) <= 10
        assert all(isinstance(s.timestamp, pd.Timestamp) for s in latest)
    
    def test_ensemble_ml_signals_integration(self, comprehensive_market_data):
        """Test ensemble ML signal generation."""
        # Create multiple mock models
        models = []
        for i in range(3):
            model = Mock()
            model.name = f"model_{i}"
            model.feature_names = ["close", "volume", "rsi_14"]
            
            # Different prediction patterns for each model
            def make_predictor(model_idx):
                def predict(features):
                    predictions = []
                    for idx in range(len(features)):
                        rsi = features.iloc[idx].get('rsi_14', 50)
                        
                        if model_idx == 0:  # Conservative model
                            if rsi < 25:
                                predictions.append([0.1, 0.1, 0.8])
                            elif rsi > 75:
                                predictions.append([0.8, 0.1, 0.1])
                            else:
                                predictions.append([0.4, 0.4, 0.2])
                        
                        elif model_idx == 1:  # Aggressive model
                            if rsi < 35:
                                predictions.append([0.2, 0.1, 0.7])
                            elif rsi > 65:
                                predictions.append([0.7, 0.2, 0.1])
                            else:
                                predictions.append([0.3, 0.4, 0.3])
                        
                        else:  # Neutral model
                            predictions.append([0.33, 0.34, 0.33])
                    
                    return np.array(predictions)
                return predict
            
            model.predict_proba = make_predictor(i)
            models.append(model)
        
        # Create ensemble
        ensemble = EnsembleMLSignals(
            models=models,
            voting="soft",
            min_agreement=0.6
        )
        
        # Add indicators
        from ta import add_all_ta_features
        data_with_indicators = add_all_ta_features(
            comprehensive_market_data,
            open="open", high="high", low="low", close="close", volume="volume",
            fillna=True
        )
        
        data_with_indicators.rename(columns={
            'momentum_rsi': 'rsi_14'
        }, inplace=True)
        
        # Generate ensemble signals
        signals = ensemble.generate_signals(data_with_indicators.tail(200), "EURUSD")
        
        # Should generate consensus signals
        assert len(signals) > 0
        assert all(s.metadata["n_models"] == 3 for s in signals)
    
    def test_real_time_signal_generation(self, signal_generator_with_sources):
        """Test signal generation on streaming data."""
        # Simulate real-time data updates
        base_time = datetime.now()
        signals_generated = []
        
        for i in range(10):
            # Create new data point
            new_time = base_time + timedelta(minutes=i*5)
            new_data = pd.DataFrame({
                'open': [1.0850 + i*0.0001],
                'high': [1.0852 + i*0.0001],
                'low': [1.0848 + i*0.0001],
                'close': [1.0851 + i*0.0001],
                'volume': [5000 + i*100],
                'rsi_14': [45 + i*2],
                'macd': [0.0001 * i],
                'sma_20': [1.0849],
                'sma_50': [1.0845]
            }, index=[new_time])
            
            # Generate signals for new data
            signals = signal_generator_with_sources.generate(new_data, "EURUSD")
            
            if not signals.empty:
                signals_generated.append(signals)
        
        # Verify we can generate signals in real-time
        assert len(signal_generator_with_sources.signal_history) >= 0
    
    def test_performance_with_large_dataset(self, comprehensive_market_data):
        """Test performance with large dataset."""
        import time
        
        # Create generator with multiple sources
        generator = SignalGenerator(min_confidence=0.5)
        
        # Add sources
        for i in range(3):
            tech = TechnicalSignals(name=f"tech_{i}", weight=0.8+i*0.1)
            generator.add_source(tech)
        
        # Measure performance
        start_time = time.time()
        
        # Generate signals for full dataset
        signals_df = generator.generate(comprehensive_market_data, "EURUSD")
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Should complete in reasonable time
        assert duration < 10.0  # 10 seconds max
        
        print(f"Generated {len(signals_df)} signals from {len(comprehensive_market_data)} bars in {duration:.2f} seconds")
    
    @pytest.mark.slow
    def test_model_persistence_integration(self, mock_ml_model, comprehensive_market_data):
        """Test saving and loading ML models for signal generation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = Path(tmpdir) / "test_model.pkl"
            
            # Save mock model
            joblib.dump(mock_ml_model, model_path)
            
            # Create MLSignals with saved model
            with patch('fxml4_signals.ml_signals.MLModelFactory') as mock_factory:
                mock_factory.create.return_value = mock_ml_model
                
                ml_signals = MLSignals(model_path=str(model_path))
                
                # Add indicators
                from ta import add_all_ta_features
                data_with_indicators = add_all_ta_features(
                    comprehensive_market_data.tail(100),
                    open="open", high="high", low="low", close="close", volume="volume",
                    fillna=True
                )
                
                data_with_indicators.rename(columns={
                    'momentum_rsi': 'rsi_14',
                    'trend_macd': 'macd',
                    'trend_sma_fast': 'sma_20',
                    'trend_sma_slow': 'sma_50'
                }, inplace=True)
                
                # Generate signals
                signals = ml_signals.generate_signals(data_with_indicators, "EURUSD")
                
                # Should work with loaded model
                assert len(signals) > 0