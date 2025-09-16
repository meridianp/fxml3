"""Tests for machine learning signal generation."""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from fxml4_signals.ml_signals import MLSignals, EnsembleMLSignals
from fxml4_signals.base import Signal, SignalType


@pytest.fixture
def mock_ml_model():
    """Create mock ML model."""
    model = Mock()
    model.name = "test_model"
    model.feature_names = ["close", "volume", "rsi_14", "macd", "sma_20"]
    model.predict_proba = Mock()
    model.load = Mock()
    return model


@pytest.fixture
def ml_signals(mock_ml_model):
    """Create MLSignals instance with mock model."""
    return MLSignals(
        name="ml_test",
        weight=0.9,
        model=mock_ml_model,
        prediction_threshold=0.6
    )


@pytest.fixture
def sample_feature_data():
    """Create sample data with ML features."""
    periods = 100
    dates = pd.date_range(start='2024-01-15', periods=periods, freq='1h')
    
    # Generate base price data
    base_price = 1.0850
    prices = base_price + np.random.randn(periods).cumsum() * 0.0002
    prices_series = pd.Series(prices, index=dates)
    
    # Create DataFrame with all features
    df = pd.DataFrame({
        'open': prices + np.random.randn(periods) * 0.0001,
        'high': prices + abs(np.random.randn(periods) * 0.0002),
        'low': prices - abs(np.random.randn(periods) * 0.0002),
        'close': prices,
        'volume': np.random.randint(1000, 10000, periods),
        'sma_20': prices_series.rolling(20).mean(),
        'sma_50': prices_series.rolling(50).mean(),
        'rsi_14': 50 + np.random.randn(periods) * 15,
        'macd': np.random.randn(periods) * 0.0001,
        'macd_signal': np.random.randn(periods) * 0.00008,
        'bb_upper': prices + 0.002,
        'bb_middle': prices,
        'bb_lower': prices - 0.002,
        'atr_14': abs(np.random.randn(periods) * 0.0002)
    }, index=dates)
    
    # Forward fill NaN values from rolling calculations
    df = df.ffill()
    
    return df


class TestMLSignals:
    """Test MLSignals class."""
    
    def test_initialization_with_model(self, mock_ml_model):
        """Test initialization with provided model."""
        signals = MLSignals(
            name="ml_custom",
            weight=0.8,
            model=mock_ml_model,
            prediction_threshold=0.7,
            feature_columns=["close", "volume"]
        )
        
        assert signals.name == "ml_custom"
        assert signals.weight == 0.8
        assert signals.model == mock_ml_model
        assert signals.prediction_threshold == 0.7
        assert signals.feature_columns == ["close", "volume"]
    
    def test_initialization_default(self):
        """Test initialization with defaults."""
        signals = MLSignals()
        
        assert signals.name == "ml"
        assert signals.weight == 1.0
        assert signals.model is None
        assert signals.prediction_threshold == 0.6
        assert signals.feature_columns is None
    
    @patch('fxml4_signals.ml_signals.MLModelFactory')
    def test_load_model_from_path(self, mock_factory):
        """Test loading model from path."""
        # Setup mock
        mock_model = Mock()
        mock_model.feature_names = ["feature1", "feature2"]
        mock_factory.create.return_value = mock_model
        
        # Create MLSignals with model path
        signals = MLSignals(model_path="/path/to/xgboost_model.pkl")
        
        # Verify model was loaded
        mock_factory.create.assert_called_once_with("xgboost")
        mock_model.load.assert_called_once_with("/path/to/xgboost_model.pkl")
        assert signals.model == mock_model
        assert signals.feature_columns == ["feature1", "feature2"]
    
    def test_infer_model_type(self, ml_signals):
        """Test model type inference from path."""
        # Test various model types
        assert ml_signals._infer_model_type("random_forest_model.pkl") == "random_forest"
        assert ml_signals._infer_model_type("xgboost_classifier.json") == "xgboost"
        assert ml_signals._infer_model_type("lightgbm_v2.txt") == "lightgbm"
        assert ml_signals._infer_model_type("logistic_regression.joblib") == "logistic_regression"
        
        # Test default
        assert ml_signals._infer_model_type("unknown_model.bin") == "xgboost"
    
    def test_get_required_columns_with_features(self):
        """Test getting required columns when features are specified."""
        signals = MLSignals(feature_columns=["col1", "col2", "col3"])
        assert signals.get_required_columns() == ["col1", "col2", "col3"]
    
    def test_get_required_columns_default(self, ml_signals):
        """Test getting default required columns."""
        ml_signals.feature_columns = None
        columns = ml_signals.get_required_columns()
        
        # Check default columns
        assert "open" in columns
        assert "close" in columns
        assert "volume" in columns
        assert "rsi_14" in columns
        assert "macd" in columns
        assert "sma_20" in columns
    
    def test_generate_signals_no_model(self):
        """Test signal generation without model."""
        signals = MLSignals()
        
        with patch('fxml4_signals.ml_signals.logger') as mock_logger:
            result = signals.generate_signals(pd.DataFrame(), "EURUSD")
            assert result == []
            mock_logger.error.assert_called_once()
    
    def test_generate_signals_success(self, ml_signals, mock_ml_model, sample_feature_data):
        """Test successful signal generation."""
        # Setup model predictions (3-class: SELL, HOLD, BUY)
        n_samples = len(sample_feature_data)
        predictions = []
        
        for i in range(n_samples):
            if i % 10 == 0:  # Buy signal
                predictions.append([0.1, 0.2, 0.7])
            elif i % 10 == 5:  # Sell signal
                predictions.append([0.8, 0.1, 0.1])
            else:  # No signal (below threshold)
                predictions.append([0.3, 0.4, 0.3])
        
        mock_ml_model.predict_proba.return_value = np.array(predictions)
        
        # Generate signals
        signals = ml_signals.generate_signals(sample_feature_data, "EURUSD")
        
        # Verify signals were generated
        assert len(signals) > 0
        
        # Check signal properties
        buy_signals = [s for s in signals if s.signal_type == SignalType.BUY]
        sell_signals = [s for s in signals if s.signal_type == SignalType.SELL]
        
        assert len(buy_signals) > 0
        assert len(sell_signals) > 0
        
        # Verify signal details
        for signal in signals:
            assert signal.symbol == "EURUSD"
            assert signal.source == "ml_test_prediction"
            assert signal.confidence >= 0.6  # threshold
            assert "model_name" in signal.metadata
            assert "buy_probability" in signal.metadata
            assert "sell_probability" in signal.metadata
    
    def test_generate_signals_binary_classification(self, ml_signals, mock_ml_model, sample_feature_data):
        """Test signal generation with binary classification."""
        # Setup binary predictions (SELL, BUY)
        n_samples = len(sample_feature_data)
        predictions = []
        
        for i in range(n_samples):
            if i % 8 == 0:  # Buy signal
                predictions.append([0.2, 0.8])
            elif i % 8 == 4:  # Sell signal
                predictions.append([0.9, 0.1])
            else:  # No signal
                predictions.append([0.5, 0.5])
        
        mock_ml_model.predict_proba.return_value = np.array(predictions)
        
        # Generate signals
        signals = ml_signals.generate_signals(sample_feature_data, "GBPUSD")
        
        # Verify signals
        assert len(signals) > 0
        assert all(s.signal_type in [SignalType.BUY, SignalType.SELL] for s in signals)
    
    def test_prepare_features(self, ml_signals, sample_feature_data):
        """Test feature preparation."""
        # Set specific feature columns
        ml_signals.feature_columns = ["close", "volume", "rsi_14"]
        
        features = ml_signals._prepare_features(sample_feature_data)
        
        # Check prepared features
        assert not features.empty
        assert list(features.columns) == ["close", "volume", "rsi_14"]
        assert len(features) == len(sample_feature_data)
        assert not features.isna().any().any()  # No NaN values
    
    def test_prepare_features_missing_columns(self, ml_signals):
        """Test feature preparation with missing columns."""
        # Create data missing required columns
        data = pd.DataFrame({
            'price': [1.08, 1.09, 1.10],
            'time': [1, 2, 3]
        })
        
        with patch('fxml4_signals.ml_signals.logger') as mock_logger:
            features = ml_signals._prepare_features(data)
            assert features.empty
            mock_logger.error.assert_called_once()
    
    def test_prepare_features_with_nan(self, ml_signals):
        """Test feature preparation with NaN values."""
        # Create data with NaN
        dates = pd.date_range('2024-01-15', periods=10, freq='1h')
        data = pd.DataFrame({
            'close': [1.08, np.nan, 1.09, 1.10, np.nan, 1.11, 1.12, np.nan, 1.13, 1.14],
            'volume': [1000, 2000, np.nan, 3000, 4000, 5000, np.nan, 6000, 7000, 8000]
        }, index=dates)
        
        ml_signals.feature_columns = ["close", "volume"]
        features = ml_signals._prepare_features(data)
        
        # Should handle NaN values
        assert not features.empty
        assert not features.isna().any().any()
    
    def test_create_signal_from_prediction(self, ml_signals, sample_feature_data):
        """Test signal creation from prediction."""
        timestamp = sample_feature_data.index[0]
        row_data = sample_feature_data.iloc[0]
        
        # Test buy signal
        buy_proba = np.array([0.1, 0.2, 0.7])
        signal = ml_signals._create_signal_from_prediction(
            timestamp, buy_proba, row_data, "EURUSD"
        )
        
        assert signal is not None
        assert signal.signal_type == SignalType.BUY
        assert signal.confidence == 0.7
        assert signal.metadata["buy_probability"] == 0.7
        
        # Test sell signal
        sell_proba = np.array([0.8, 0.1, 0.1])
        signal = ml_signals._create_signal_from_prediction(
            timestamp, sell_proba, row_data, "EURUSD"
        )
        
        assert signal.signal_type == SignalType.SELL
        assert signal.confidence == 0.8
        
        # Test no signal (below threshold)
        low_proba = np.array([0.4, 0.3, 0.3])
        signal = ml_signals._create_signal_from_prediction(
            timestamp, low_proba, row_data, "EURUSD"
        )
        
        assert signal is None
        
        # Test hold signal (should not generate)
        hold_proba = np.array([0.1, 0.8, 0.1])
        signal = ml_signals._create_signal_from_prediction(
            timestamp, hold_proba, row_data, "EURUSD"
        )
        
        assert signal is None
    
    def test_model_prediction_error(self, ml_signals, mock_ml_model, sample_feature_data):
        """Test handling of model prediction errors."""
        # Make model raise exception
        mock_ml_model.predict_proba.side_effect = Exception("Model error")
        
        with patch('fxml4_signals.ml_signals.logger') as mock_logger:
            signals = ml_signals.generate_signals(sample_feature_data, "EURUSD")
            
            assert signals == []
            mock_logger.error.assert_called()
            assert "Model error" in str(mock_logger.error.call_args)


class TestEnsembleMLSignals:
    """Test EnsembleMLSignals class."""
    
    def test_initialization(self):
        """Test ensemble initialization."""
        model1 = Mock()
        model2 = Mock()
        
        ensemble = EnsembleMLSignals(
            name="ensemble_test",
            weight=0.95,
            models=[model1, model2],
            voting="soft",
            min_agreement=0.7
        )
        
        assert ensemble.name == "ensemble_test"
        assert ensemble.weight == 0.95
        assert len(ensemble.models) == 2
        assert ensemble.voting == "soft"
        assert ensemble.min_agreement == 0.7
    
    @patch('fxml4_signals.ml_signals.MLSignals')
    def test_load_models_from_paths(self, mock_ml_signals_class):
        """Test loading models from paths."""
        # Setup mocks
        mock_instances = []
        for i in range(3):
            instance = Mock()
            instance.model = Mock(name=f"model_{i}")
            mock_instances.append(instance)
        
        mock_ml_signals_class.side_effect = mock_instances
        
        # Create ensemble with model paths
        paths = ["/path/model1.pkl", "/path/model2.pkl", "/path/model3.pkl"]
        ensemble = EnsembleMLSignals(model_paths=paths)
        
        # Verify models were loaded
        assert len(ensemble.models) == 3
        assert all(hasattr(m, 'name') for m in ensemble.models)
    
    def test_get_required_columns_from_models(self):
        """Test getting required columns from all models."""
        # Create models with different features
        model1 = Mock()
        model1.feature_names = ["close", "volume", "rsi"]
        
        model2 = Mock()
        model2.feature_names = ["close", "macd", "sma_20"]
        
        ensemble = EnsembleMLSignals(models=[model1, model2])
        columns = ensemble.get_required_columns()
        
        # Should combine all features
        assert "close" in columns
        assert "volume" in columns
        assert "rsi" in columns
        assert "macd" in columns
        assert "sma_20" in columns
    
    def test_generate_signals_soft_voting(self, sample_feature_data):
        """Test ensemble signal generation with soft voting."""
        # Create mock models
        model1 = Mock()
        model1.name = "model1"
        model1.feature_names = ["close", "volume"]
        model1.predict_proba = Mock(return_value=np.array([[0.1, 0.2, 0.7]] * len(sample_feature_data)))
        
        model2 = Mock()
        model2.name = "model2" 
        model2.feature_names = ["close", "volume"]
        model2.predict_proba = Mock(return_value=np.array([[0.2, 0.1, 0.7]] * len(sample_feature_data)))
        
        ensemble = EnsembleMLSignals(
            models=[model1, model2],
            voting="soft",
            min_agreement=0.6
        )
        
        # Generate signals
        signals = ensemble.generate_signals(sample_feature_data, "EURUSD")
        
        # Should generate buy signals (both models agree)
        assert len(signals) > 0
        assert all(s.signal_type == SignalType.BUY for s in signals)
        assert all(s.metadata["n_models"] == 2 for s in signals)
    
    def test_generate_signals_hard_voting(self, sample_feature_data):
        """Test ensemble signal generation with hard voting."""
        # Create mock models with different predictions
        n_samples = len(sample_feature_data)
        
        # Model 1: Mostly BUY
        model1 = Mock()
        model1.name = "model1"
        model1.feature_names = ["close"]
        pred1 = []
        for i in range(n_samples):
            if i % 3 == 0:
                pred1.append([0.1, 0.1, 0.8])  # BUY
            else:
                pred1.append([0.4, 0.4, 0.2])  # Uncertain
        model1.predict_proba = Mock(return_value=np.array(pred1))
        
        # Model 2: Mixed predictions
        model2 = Mock()
        model2.name = "model2"
        model2.feature_names = ["close"]
        pred2 = []
        for i in range(n_samples):
            if i % 3 == 0:
                pred2.append([0.2, 0.1, 0.7])  # BUY
            else:
                pred2.append([0.7, 0.2, 0.1])  # SELL
        model2.predict_proba = Mock(return_value=np.array(pred2))
        
        ensemble = EnsembleMLSignals(
            models=[model1, model2],
            voting="hard",
            min_agreement=0.5
        )
        
        # Generate signals
        signals = ensemble.generate_signals(sample_feature_data, "EURUSD")
        
        # Should have signals where models agree
        assert len(signals) > 0
    
    def test_hard_voting_calculation(self):
        """Test hard voting aggregation method."""
        ensemble = EnsembleMLSignals()
        
        # Test with 3 models, 3 classes
        predictions = [
            np.array([2, 1, 0, 2]),  # Model 1 predictions
            np.array([2, 2, 0, 1]),  # Model 2 predictions  
            np.array([1, 2, 0, 2])   # Model 3 predictions
        ]
        
        result = ensemble._hard_voting(predictions, n_classes=3)
        
        # Check shape
        assert result.shape == (4, 3)
        
        # Check first sample: votes are [2, 2, 1] -> class 2 wins
        assert result[0, 2] == 2/3  # 2 votes for class 2
        assert result[0, 1] == 1/3  # 1 vote for class 1
        assert result[0, 0] == 0    # 0 votes for class 0
    
    def test_generate_signals_no_models(self, sample_feature_data):
        """Test signal generation with no models."""
        ensemble = EnsembleMLSignals()
        
        with patch('fxml4_signals.ml_signals.logger') as mock_logger:
            signals = ensemble.generate_signals(sample_feature_data, "EURUSD")
            
            assert signals == []
            mock_logger.error.assert_called_once()
    
    def test_model_error_handling(self, sample_feature_data):
        """Test handling of individual model errors."""
        # Create models where one fails
        model1 = Mock()
        model1.name = "model1"
        model1.feature_names = ["close"]
        model1.predict_proba = Mock(return_value=np.array([[0.1, 0.2, 0.7]] * len(sample_feature_data)))
        
        model2 = Mock()
        model2.name = "model2_error"
        model2.feature_names = ["close"]
        model2.predict_proba = Mock(side_effect=Exception("Model 2 failed"))
        
        ensemble = EnsembleMLSignals(models=[model1, model2])
        
        with patch('fxml4_signals.ml_signals.logger') as mock_logger:
            # Should still generate signals from working model
            signals = ensemble.generate_signals(sample_feature_data, "EURUSD")
            
            # Error should be logged
            error_calls = [call for call in mock_logger.error.call_args_list 
                          if "Model 2 failed" in str(call)]
            assert len(error_calls) > 0
            
            # Should still have signals from model1
            assert len(signals) > 0