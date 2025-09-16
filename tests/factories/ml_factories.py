"""
Machine Learning and Signal Factory Definitions
==============================================

Factory Boy factories for creating ML models, signals, predictions, backtests,
and related machine learning artifacts for testing.
"""

import json
import random
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List

import factory
import factory.fuzzy
from faker import Faker

fake = Faker()


class ModelFactory(factory.Factory):
    """
    Factory for creating ML model metadata and configurations.

    Generates realistic model configurations with proper versioning,
    performance metrics, and deployment information.
    """

    class Meta:
        model = dict

    # Model identification
    model_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    model_name = factory.LazyAttribute(
        lambda obj: f"{obj.algorithm}_{obj.symbol}_{obj.timeframe}_v{obj.version}"
    )
    version = factory.Sequence(lambda n: f"1.{n}")

    # Model type and algorithm
    algorithm = factory.fuzzy.FuzzyChoice(
        [
            "XGBoost",
            "LightGBM",
            "RandomForest",
            "LogisticRegression",
            "SVM",
            "NeuralNetwork",
            "LSTM",
            "GRU",
            "Transformer",
        ]
    )
    model_type = factory.fuzzy.FuzzyChoice(["classification", "regression", "ensemble"])
    problem_type = factory.fuzzy.FuzzyChoice(
        ["signal_generation", "price_prediction", "risk_assessment"]
    )

    # Trading configuration
    symbol = factory.fuzzy.FuzzyChoice(["EURUSD", "GBPUSD", "USDJPY", "USDCHF"])
    timeframe = factory.fuzzy.FuzzyChoice(["1m", "5m", "15m", "1h", "4h", "1d"])
    prediction_horizon = factory.LazyAttribute(
        lambda obj: {
            "1m": 5,  # 5 minutes ahead
            "5m": 15,  # 15 minutes ahead
            "15m": 60,  # 1 hour ahead
            "1h": 240,  # 4 hours ahead
            "4h": 1440,  # 1 day ahead
            "1d": 10080,  # 1 week ahead
        }.get(obj.timeframe, 60)
    )

    # Training data
    training_start = factory.LazyFunction(
        lambda: fake.date_between(start_date="-2y", end_date="-6m")
    )
    training_end = factory.LazyAttribute(
        lambda obj: obj.training_start + timedelta(days=365)  # 1 year training
    )
    training_samples = factory.fuzzy.FuzzyInteger(50000, 500000)
    validation_samples = factory.LazyAttribute(
        lambda obj: int(obj.training_samples * 0.2)
    )
    test_samples = factory.LazyAttribute(lambda obj: int(obj.training_samples * 0.2))

    # Feature engineering
    feature_count = factory.fuzzy.FuzzyInteger(20, 200)
    feature_names = factory.LazyAttribute(
        lambda obj: [f"feature_{i}" for i in range(obj.feature_count)]
    )

    # Key features used
    technical_indicators = factory.LazyFunction(
        lambda: fake.random_elements(
            [
                "SMA_20",
                "EMA_12",
                "RSI_14",
                "MACD",
                "Bollinger_Bands",
                "ATR_14",
                "Stochastic",
                "Williams_R",
                "CCI",
                "ADX",
            ],
            length=fake.random_int(5, 8),
        )
    )

    # Performance metrics
    accuracy = factory.fuzzy.FuzzyDecimal(0.45, 0.75, 3)
    precision = factory.fuzzy.FuzzyDecimal(0.40, 0.80, 3)
    recall = factory.fuzzy.FuzzyDecimal(0.40, 0.80, 3)
    f1_score = factory.LazyAttribute(
        lambda obj: (
            2 * (obj.precision * obj.recall) / (obj.precision + obj.recall)
            if (obj.precision + obj.recall) > 0
            else Decimal("0")
        )
    )

    # Financial metrics
    sharpe_ratio = factory.fuzzy.FuzzyDecimal(-0.5, 3.0, 2)
    max_drawdown = factory.fuzzy.FuzzyDecimal(5.0, 30.0, 2)
    total_return = factory.fuzzy.FuzzyDecimal(-20.0, 50.0, 2)
    win_rate = factory.LazyAttribute(lambda obj: obj.accuracy)  # For trading models
    profit_factor = factory.fuzzy.FuzzyDecimal(0.8, 2.5, 2)

    # Model hyperparameters (JSON stored)
    hyperparameters = factory.LazyAttribute(
        lambda obj: {
            "XGBoost": {
                "n_estimators": fake.random_int(100, 1000),
                "max_depth": fake.random_int(3, 10),
                "learning_rate": fake.random.uniform(0.01, 0.3),
                "subsample": fake.random.uniform(0.8, 1.0),
            },
            "RandomForest": {
                "n_estimators": fake.random_int(50, 500),
                "max_depth": fake.random_int(5, 20),
                "min_samples_split": fake.random_int(2, 10),
                "min_samples_leaf": fake.random_int(1, 5),
            },
            "NeuralNetwork": {
                "hidden_layers": fake.random_int(2, 5),
                "neurons_per_layer": fake.random_int(32, 256),
                "dropout_rate": fake.random.uniform(0.1, 0.5),
                "learning_rate": fake.random.uniform(0.001, 0.01),
            },
        }.get(obj.algorithm, {"param1": "value1"})
    )

    # Model lifecycle
    status = factory.fuzzy.FuzzyChoice(
        ["training", "trained", "deployed", "deprecated"]
    )
    created_at = factory.LazyFunction(
        lambda: fake.date_time_between(start_date="-1y", end_date="now")
    )
    trained_at = factory.LazyAttribute(
        lambda obj: obj.created_at + timedelta(hours=fake.random_int(1, 48))
    )
    deployed_at = factory.LazyAttribute(
        lambda obj: (
            obj.trained_at + timedelta(days=fake.random_int(1, 7))
            if obj.status == "deployed"
            else None
        )
    )

    # File paths and storage
    model_path = factory.LazyAttribute(
        lambda obj: f"models/{obj.symbol}/{obj.algorithm}/{obj.version}/model.pkl"
    )
    config_path = factory.LazyAttribute(
        lambda obj: f"models/{obj.symbol}/{obj.algorithm}/{obj.version}/config.json"
    )

    # Training environment
    python_version = factory.fuzzy.FuzzyChoice(
        ["3.8.10", "3.9.18", "3.10.12", "3.11.5"]
    )
    framework_version = factory.LazyAttribute(
        lambda obj: {
            "XGBoost": "1.7.5",
            "LightGBM": "3.3.5",
            "RandomForest": "scikit-learn==1.3.0",
            "NeuralNetwork": "tensorflow==2.13.0",
        }.get(obj.algorithm, "unknown")
    )

    class Params:
        # Traits for different model types
        high_performer = factory.Trait(
            accuracy=factory.fuzzy.FuzzyDecimal(0.65, 0.80, 3),
            sharpe_ratio=factory.fuzzy.FuzzyDecimal(1.5, 3.0, 2),
            max_drawdown=factory.fuzzy.FuzzyDecimal(5.0, 15.0, 2),
            status="deployed",
        )

        underperformer = factory.Trait(
            accuracy=factory.fuzzy.FuzzyDecimal(0.40, 0.55, 3),
            sharpe_ratio=factory.fuzzy.FuzzyDecimal(-0.5, 0.8, 2),
            max_drawdown=factory.fuzzy.FuzzyDecimal(20.0, 35.0, 2),
            status="deprecated",
        )

        ensemble_model = factory.Trait(
            algorithm="Ensemble",
            model_type="ensemble",
            feature_count=factory.fuzzy.FuzzyInteger(100, 300),
        )


class FeatureFactory(factory.Factory):
    """
    Factory for creating feature data used in ML models.
    """

    class Meta:
        model = dict

    # Feature identification
    feature_id = factory.Sequence(lambda n: f"FEAT_{n:06d}")
    feature_name = factory.fuzzy.FuzzyChoice(
        [
            "SMA_20",
            "EMA_12",
            "RSI_14",
            "MACD_Line",
            "MACD_Signal",
            "BB_Upper",
            "BB_Lower",
            "ATR_14",
            "Volume_SMA",
            "Price_Change",
            "Volatility_1h",
            "Session_London",
            "Day_of_Week",
            "Hour_of_Day",
        ]
    )

    # Feature metadata
    feature_type = factory.fuzzy.FuzzyChoice(
        ["technical", "fundamental", "sentiment", "temporal"]
    )
    data_type = factory.fuzzy.FuzzyChoice(["numeric", "categorical", "boolean"])
    calculation_method = factory.Faker("sentence", nb_words=5)

    # Feature statistics
    min_value = factory.fuzzy.FuzzyDecimal(-100.0, 0.0, 4)
    max_value = factory.fuzzy.FuzzyDecimal(0.0, 100.0, 4)
    mean_value = factory.LazyAttribute(lambda obj: (obj.min_value + obj.max_value) / 2)
    std_deviation = factory.LazyAttribute(
        lambda obj: (obj.max_value - obj.min_value) / 6  # Rough estimate
    )

    # Feature importance
    importance_score = factory.fuzzy.FuzzyDecimal(0.001, 0.500, 4)
    correlation_with_target = factory.fuzzy.FuzzyDecimal(-0.8, 0.8, 3)

    # Feature engineering metadata
    requires_historical_data = factory.fuzzy.FuzzyChoice([True, False])
    lookback_periods = factory.fuzzy.FuzzyInteger(1, 50)
    is_normalized = factory.fuzzy.FuzzyChoice([True, False])
    normalization_method = factory.LazyAttribute(
        lambda obj: (
            fake.random_element(["min_max", "z_score", "robust", "none"])
            if obj.is_normalized
            else "none"
        )
    )


class SignalFactory(factory.Factory):
    """
    Factory for creating trading signals generated by ML models.

    Creates realistic trading signals with confidence scores, risk assessments,
    and performance tracking data.
    """

    class Meta:
        model = dict

    # Signal identification
    signal_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    model_id = factory.LazyFunction(lambda: ModelFactory().model_id)
    timestamp = factory.LazyFunction(
        lambda: fake.date_time_between(start_date="-7d", end_date="now")
    )

    # Signal details
    symbol = factory.fuzzy.FuzzyChoice(["EURUSD", "GBPUSD", "USDJPY", "USDCHF"])
    signal_type = factory.fuzzy.FuzzyChoice(["BUY", "SELL", "HOLD"])
    confidence = factory.fuzzy.FuzzyDecimal(0.1, 1.0, 3)

    # Price and execution data
    signal_price = factory.fuzzy.FuzzyDecimal(1.0000, 1.5000, 4)
    current_price = factory.LazyAttribute(
        lambda obj: obj.signal_price
        + Decimal(str(fake.random.uniform(-0.0010, 0.0010)))
    )

    # Risk management
    stop_loss = factory.LazyAttribute(
        lambda obj: (
            obj.signal_price
            - (Decimal("0.0030") if obj.signal_type == "BUY" else -Decimal("0.0030"))
            if obj.signal_type != "HOLD"
            else None
        )
    )
    take_profit = factory.LazyAttribute(
        lambda obj: (
            obj.signal_price
            + (Decimal("0.0060") if obj.signal_type == "BUY" else -Decimal("0.0060"))
            if obj.signal_type != "HOLD"
            else None
        )
    )

    # Risk metrics
    risk_score = factory.fuzzy.FuzzyDecimal(0.1, 1.0, 2)
    expected_return = factory.fuzzy.FuzzyDecimal(-2.0, 5.0, 2)  # Percentage
    risk_reward_ratio = factory.LazyAttribute(
        lambda obj: (
            abs(obj.expected_return / obj.risk_score)
            if obj.risk_score > 0
            else Decimal("0")
        )
    )

    # Signal strength indicators
    volume_confirmation = factory.fuzzy.FuzzyChoice([True, False])
    momentum_alignment = factory.fuzzy.FuzzyChoice([True, False])
    trend_alignment = factory.fuzzy.FuzzyChoice([True, False])

    # Feature contributions (top 5 features)
    feature_contributions = factory.LazyFunction(
        lambda: {f"feature_{i}": fake.random.uniform(-0.5, 0.5) for i in range(5)}
    )

    # Market context
    market_regime = factory.fuzzy.FuzzyChoice(
        ["trending", "ranging", "volatile", "quiet"]
    )
    session = factory.LazyAttribute(
        lambda obj: {0: "Sydney", 6: "Tokyo", 12: "London", 18: "New York"}.get(
            obj.timestamp.hour // 6 * 6, "London"
        )
    )

    # Signal lifecycle
    status = factory.fuzzy.FuzzyChoice(["active", "triggered", "expired", "cancelled"])
    expires_at = factory.LazyAttribute(
        lambda obj: obj.timestamp + timedelta(hours=fake.random_int(1, 24))
    )

    # Actual outcome (if trade was taken)
    was_traded = factory.fuzzy.FuzzyChoice([True, False])
    actual_return = factory.LazyAttribute(
        lambda obj: (
            Decimal(str(fake.random.uniform(-3.0, 7.0))) if obj.was_traded else None
        )
    )
    trade_duration_minutes = factory.LazyAttribute(
        lambda obj: fake.random_int(5, 1440) if obj.was_traded else None
    )

    class Params:
        # Traits for different signal qualities
        high_confidence = factory.Trait(
            confidence=factory.fuzzy.FuzzyDecimal(0.7, 1.0, 3),
            risk_score=factory.fuzzy.FuzzyDecimal(0.1, 0.4, 2),
            volume_confirmation=True,
            momentum_alignment=True,
            trend_alignment=True,
        )

        low_confidence = factory.Trait(
            confidence=factory.fuzzy.FuzzyDecimal(0.1, 0.4, 3),
            risk_score=factory.fuzzy.FuzzyDecimal(0.6, 1.0, 2),
            volume_confirmation=False,
        )

        profitable_signal = factory.Trait(
            was_traded=True,
            actual_return=factory.fuzzy.FuzzyDecimal(1.0, 8.0, 2),
            status="triggered",
        )

        losing_signal = factory.Trait(
            was_traded=True,
            actual_return=factory.fuzzy.FuzzyDecimal(-5.0, -0.5, 2),
            status="triggered",
        )


class PredictionFactory(factory.Factory):
    """
    Factory for creating ML model predictions with uncertainty estimates.
    """

    class Meta:
        model = dict

    # Prediction identification
    prediction_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    model_id = factory.LazyFunction(lambda: ModelFactory().model_id)
    timestamp = factory.LazyFunction(
        lambda: fake.date_time_between(start_date="-1d", end_date="now")
    )

    # Prediction target
    symbol = factory.fuzzy.FuzzyChoice(["EURUSD", "GBPUSD", "USDJPY"])
    prediction_type = factory.fuzzy.FuzzyChoice(
        ["price", "direction", "volatility", "return"]
    )
    prediction_horizon = factory.fuzzy.FuzzyInteger(5, 1440)  # 5 minutes to 1 day

    # Prediction values
    predicted_value = factory.fuzzy.FuzzyDecimal(1.0000, 1.5000, 4)
    confidence_interval_lower = factory.LazyAttribute(
        lambda obj: obj.predicted_value
        - Decimal(str(fake.random.uniform(0.0010, 0.0050)))
    )
    confidence_interval_upper = factory.LazyAttribute(
        lambda obj: obj.predicted_value
        + Decimal(str(fake.random.uniform(0.0010, 0.0050)))
    )

    # Uncertainty measures
    prediction_uncertainty = factory.fuzzy.FuzzyDecimal(0.001, 0.010, 4)
    model_confidence = factory.fuzzy.FuzzyDecimal(0.3, 0.9, 2)

    # Actual outcome (if available)
    actual_value = factory.LazyAttribute(
        lambda obj: (
            obj.predicted_value + Decimal(str(fake.random.uniform(-0.0030, 0.0030)))
            if fake.random.random() > 0.3
            else None
        )  # 70% have actual values
    )
    prediction_error = factory.LazyAttribute(
        lambda obj: (
            abs(obj.actual_value - obj.predicted_value) if obj.actual_value else None
        )
    )
    is_accurate = factory.LazyAttribute(
        lambda obj: (
            obj.prediction_error < Decimal("0.0020") if obj.prediction_error else None
        )
    )


class BacktestFactory(factory.Factory):
    """
    Factory for creating backtest configurations and setups.
    """

    class Meta:
        model = dict

    # Backtest identification
    backtest_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    backtest_name = factory.Sequence(lambda n: f"Backtest_{n:04d}")
    model_id = factory.LazyFunction(lambda: ModelFactory().model_id)

    # Backtest period
    start_date = factory.LazyFunction(
        lambda: fake.date_between(start_date="-1y", end_date="-3m")
    )
    end_date = factory.LazyAttribute(
        lambda obj: obj.start_date + timedelta(days=fake.random_int(30, 180))
    )

    # Trading parameters
    initial_balance = factory.fuzzy.FuzzyDecimal(10000.0, 100000.0, 2)
    risk_per_trade = factory.fuzzy.FuzzyDecimal(0.01, 0.05, 3)  # 1-5% per trade
    max_positions = factory.fuzzy.FuzzyInteger(1, 10)
    commission_per_lot = factory.fuzzy.FuzzyDecimal(5.0, 30.0, 2)

    # Symbol and timeframe
    symbols = factory.LazyFunction(
        lambda: fake.random_elements(["EURUSD", "GBPUSD", "USDJPY", "USDCHF"], length=2)
    )
    timeframes = factory.LazyFunction(
        lambda: fake.random_elements(["5m", "15m", "1h", "4h"], length=1)
    )

    # Backtest configuration
    data_source = factory.fuzzy.FuzzyChoice(["IB", "Polygon", "Yahoo", "Manual"])
    execution_model = factory.fuzzy.FuzzyChoice(["perfect", "realistic", "pessimistic"])
    slippage_model = factory.fuzzy.FuzzyChoice(["none", "fixed", "variable"])

    # Status and metadata
    status = factory.fuzzy.FuzzyChoice(["pending", "running", "completed", "failed"])
    created_at = factory.LazyFunction(
        lambda: fake.date_time_between(start_date="-30d", end_date="now")
    )
    started_at = factory.LazyAttribute(
        lambda obj: (
            obj.created_at + timedelta(minutes=fake.random_int(1, 60))
            if obj.status != "pending"
            else None
        )
    )
    completed_at = factory.LazyAttribute(
        lambda obj: (
            obj.started_at + timedelta(hours=fake.random_int(1, 12))
            if obj.status == "completed"
            else None
        )
    )


class BacktestResultFactory(factory.Factory):
    """
    Factory for creating backtest results with comprehensive performance metrics.
    """

    class Meta:
        model = dict

    # Result identification
    result_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    backtest_id = factory.LazyFunction(lambda: BacktestFactory().backtest_id)

    # Basic performance metrics
    total_trades = factory.fuzzy.FuzzyInteger(50, 500)
    winning_trades = factory.LazyAttribute(
        lambda obj: int(obj.total_trades * fake.random.uniform(0.3, 0.7))
    )
    losing_trades = factory.LazyAttribute(
        lambda obj: obj.total_trades - obj.winning_trades
    )

    # Financial performance
    initial_balance = factory.fuzzy.FuzzyDecimal(10000.0, 100000.0, 2)
    final_balance = factory.LazyAttribute(
        lambda obj: obj.initial_balance * Decimal(str(fake.random.uniform(0.8, 1.5)))
    )
    total_return = factory.LazyAttribute(
        lambda obj: ((obj.final_balance - obj.initial_balance) / obj.initial_balance)
        * 100
    )

    # Risk metrics
    max_drawdown = factory.fuzzy.FuzzyDecimal(5.0, 30.0, 2)
    max_drawdown_duration_days = factory.fuzzy.FuzzyInteger(1, 60)
    sharpe_ratio = factory.fuzzy.FuzzyDecimal(-0.5, 3.0, 2)
    sortino_ratio = factory.fuzzy.FuzzyDecimal(-0.5, 3.5, 2)
    calmar_ratio = factory.LazyAttribute(
        lambda obj: (
            obj.total_return / obj.max_drawdown
            if obj.max_drawdown > 0
            else Decimal("0")
        )
    )

    # Trade statistics
    win_rate = factory.LazyAttribute(
        lambda obj: (
            (obj.winning_trades / obj.total_trades) * 100
            if obj.total_trades > 0
            else Decimal("0")
        )
    )
    avg_winning_trade = factory.fuzzy.FuzzyDecimal(50.0, 500.0, 2)
    avg_losing_trade = factory.fuzzy.FuzzyDecimal(-300.0, -20.0, 2)
    profit_factor = factory.LazyAttribute(
        lambda obj: (
            abs(
                obj.avg_winning_trade
                * obj.winning_trades
                / (obj.avg_losing_trade * obj.losing_trades)
            )
            if obj.losing_trades > 0
            else Decimal("999")
        )
    )

    # Trading statistics
    avg_trade_duration_hours = factory.fuzzy.FuzzyDecimal(0.5, 72.0, 1)
    trades_per_day = factory.LazyAttribute(
        lambda obj: obj.total_trades / 90  # Assume ~90 day backtest
    )

    # Monthly breakdown
    monthly_returns = factory.LazyFunction(
        lambda: [fake.random.uniform(-10.0, 15.0) for _ in range(3)]  # 3 months
    )
    monthly_drawdowns = factory.LazyFunction(
        lambda: [fake.random.uniform(1.0, 8.0) for _ in range(3)]
    )

    # Additional metrics
    expectancy = factory.LazyAttribute(
        lambda obj: (obj.win_rate / 100 * obj.avg_winning_trade)
        + ((100 - obj.win_rate) / 100 * obj.avg_losing_trade)
    )
    kelly_criterion = factory.LazyAttribute(
        lambda obj: (
            (
                (obj.win_rate / 100) * abs(obj.avg_winning_trade / obj.avg_losing_trade)
                - (1 - obj.win_rate / 100)
            )
            / abs(obj.avg_winning_trade / obj.avg_losing_trade)
            if obj.avg_losing_trade != 0
            else Decimal("0")
        )
    )

    class Params:
        # Traits for different backtest performance
        profitable_strategy = factory.Trait(
            win_rate=factory.fuzzy.FuzzyDecimal(55.0, 75.0, 1),
            total_return=factory.fuzzy.FuzzyDecimal(10.0, 50.0, 2),
            max_drawdown=factory.fuzzy.FuzzyDecimal(5.0, 15.0, 2),
            sharpe_ratio=factory.fuzzy.FuzzyDecimal(1.0, 3.0, 2),
        )

        losing_strategy = factory.Trait(
            win_rate=factory.fuzzy.FuzzyDecimal(25.0, 45.0, 1),
            total_return=factory.fuzzy.FuzzyDecimal(-30.0, -5.0, 2),
            max_drawdown=factory.fuzzy.FuzzyDecimal(20.0, 40.0, 2),
            sharpe_ratio=factory.fuzzy.FuzzyDecimal(-1.5, 0.5, 2),
        )

        high_frequency = factory.Trait(
            total_trades=factory.fuzzy.FuzzyInteger(1000, 5000),
            avg_trade_duration_hours=factory.fuzzy.FuzzyDecimal(0.1, 2.0, 1),
            trades_per_day=factory.LazyAttribute(
                lambda obj: obj.total_trades / 30
            ),  # 30 day backtest
        )
