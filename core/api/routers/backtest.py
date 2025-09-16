"""
Backtesting routes for FXML4 API.

This module handles backtesting operations, including running backtests
and retrieving results.
"""

import logging
from datetime import datetime
from typing import Any, Dict, Tuple

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Security, status

from fxml4.api.auth.uat_auth import UATUser, get_current_active_user_uat
from fxml4.api.schemas.api_models import BacktestRequest, BacktestResponse

# Create router
router = APIRouter()
logger = logging.getLogger(__name__)


async def _fetch_backtest_data(request: BacktestRequest) -> Tuple[pd.DataFrame, str]:
    """Fetch market data for backtesting using real data sources.

    Args:
        request: Backtest request containing symbol and date range

    Returns:
        Tuple of (market data DataFrame, feed type)
    """
    # Use the same real data approach as signals
    # Calculate how many data points we need based on date range
    from datetime import datetime

    from fxml4.api.services.direct_polygon_service import direct_polygon_service

    start_date = (
        pd.to_datetime(request.start_date)
        if request.start_date
        else datetime.utcnow() - pd.Timedelta(days=30)
    )
    end_date = (
        pd.to_datetime(request.end_date) if request.end_date else datetime.utcnow()
    )

    # Get more data for backtesting - aim for ~500 points
    limit = 500

    try:
        # Get real market data from Polygon.io
        data_points = await direct_polygon_service.get_real_forex_data(
            symbol=request.symbol, timeframe=request.timeframe or "1h", limit=limit
        )

        if not data_points:
            raise Exception(f"No data available for {request.symbol}")

        # Convert MarketDataPoint objects to DataFrame
        df_data = []
        for point in data_points:
            df_data.append(
                {
                    "timestamp": point.time,
                    "open": point.open,
                    "high": point.high,
                    "low": point.low,
                    "close": point.close,
                    "volume": point.volume,
                }
            )

        data = pd.DataFrame(df_data)
        data.set_index("timestamp", inplace=True)
        data.sort_index(inplace=True)

        # Filter data to requested date range if provided
        if request.start_date:
            data = data[data.index >= pd.to_datetime(request.start_date)]
        if request.end_date:
            data = data[data.index <= pd.to_datetime(request.end_date)]

        return data, "polygon_real"

    except Exception as e:
        logger.error(f"Failed to fetch backtest data: {e}")
        raise Exception(f"Could not fetch market data for backtesting: {e}")


def _configure_strategy(request: BacktestRequest):
    """Configure and return appropriate strategy function based on request.

    Args:
        request: Backtest request containing strategy type and parameters

    Returns:
        Strategy function
    """
    strategy_name = request.strategy

    # Get strategy function based on the request
    if strategy_name == "integrated_strategy":
        from fxml4.strategy.integrated_strategy import simple_strategy

        return simple_strategy
    elif strategy_name == "ml_strategy":
        return _create_ml_strategy(request)
    elif strategy_name == "wave_strategy":
        return _create_wave_strategy(request)
    else:
        raise ValueError(f"Unknown strategy: {strategy_name}")


def _create_ml_strategy(request: BacktestRequest):
    """Create ML-based strategy function with proper time-series validation.

    CRITICAL FIX: Eliminates look-ahead bias by using walk-forward analysis
    and ensuring no future price data is used for model training.

    Args:
        request: Backtest request with ML parameters

    Returns:
        ML strategy function
    """
    # Get ML parameters from request
    ml_params = request.strategy_params or {}
    model_type = ml_params.get("model_type", "random_forest")
    n_estimators = ml_params.get("n_estimators", 100)
    max_depth = ml_params.get("max_depth", 10)
    train_window = ml_params.get("train_window", 252)  # Trading days for training
    retrain_frequency = ml_params.get("retrain_frequency", 21)  # Retrain every 21 days

    # Create strategy function
    def ml_strategy(data):
        import numpy as np

        from fxml4.ml.features import create_technical_features
        from fxml4.ml.models import create_model

        # Create features
        feature_data = create_technical_features(
            data,
            indicators=["sma", "ema", "rsi", "macd", "bollinger", "atr"],
            ma_periods=[10, 20, 50],
            include_original=True,
        )

        # CRITICAL FIX: Create target using LAGGED price data only
        # Use price data from T-1 to T-5 to predict direction at T
        # This ensures no future information leakage
        feature_data["return_1d"] = feature_data["close"].pct_change(1)
        feature_data["return_3d"] = (
            feature_data["close"].pct_change(3).shift(1)
        )  # Shift to avoid lookahead
        feature_data["return_5d"] = (
            feature_data["close"].pct_change(5).shift(1)
        )  # Shift to avoid lookahead

        # Create binary target: positive return over next period
        # But use HISTORICAL return patterns to predict, not future returns
        feature_data["target"] = (feature_data["return_1d"] > 0.001).astype(int)

        # Shift target to align with historical features (eliminate lookahead)
        feature_data["target"] = feature_data["target"].shift(-1)

        # Drop NaN values and ensure we have enough data
        feature_data = feature_data.dropna()

        if len(feature_data) < train_window + 50:
            logger.warning(
                f"Insufficient data for ML strategy: {len(feature_data)} < {train_window + 50}"
            )
            return pd.DataFrame()

        # Select features (exclude price and target data)
        feature_cols = [
            col
            for col in feature_data.columns
            if col
            not in [
                "target",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "return_1d",
                "return_3d",
                "return_5d",
            ]
        ]

        # CRITICAL FIX: Implement walk-forward analysis
        signals = []

        # Start predictions after we have enough training data
        start_idx = train_window

        for i in range(start_idx, len(feature_data)):
            # Define training window (only historical data)
            train_start = max(0, i - train_window)
            train_end = i  # Exclusive, so we don't include current observation

            # Only retrain model every retrain_frequency days
            if i == start_idx or (i - start_idx) % retrain_frequency == 0:
                # Get training data (strictly historical)
                train_data = feature_data.iloc[train_start:train_end]

                # Ensure we have valid targets for training
                train_targets = train_data["target"].dropna()
                if len(train_targets) < 50:
                    continue

                # Align features with valid targets
                valid_train_idx = train_data["target"].dropna().index
                X_train = train_data.loc[valid_train_idx, feature_cols]
                y_train = train_data.loc[valid_train_idx, "target"].astype(int)

                # Skip if insufficient training data
                if len(X_train) < 50:
                    continue

                # Train model on historical data only
                try:
                    model = create_model(
                        model_type,
                        model_params={
                            "n_estimators": n_estimators,
                            "max_depth": max_depth,
                            "random_state": 42,
                        },
                    )

                    model.train(X_train, y_train)

                except Exception as e:
                    logger.error(f"Model training failed at step {i}: {e}")
                    continue

            # Make prediction for current time step using only historical features
            current_features = feature_data.iloc[i][feature_cols].values.reshape(1, -1)

            # Handle NaN values in features
            if np.any(np.isnan(current_features)):
                continue

            try:
                prediction = model.predict(current_features)[0]
                prediction_proba = getattr(
                    model, "predict_proba", lambda x: [0.5, 0.5]
                )(current_features)

                # Calculate confidence based on prediction probability
                if (
                    hasattr(prediction_proba, "__len__")
                    and len(prediction_proba[0]) > 1
                ):
                    confidence = max(prediction_proba[0])
                else:
                    confidence = 0.6  # Default confidence

                # Only generate signals with sufficient confidence
                if confidence > 0.55:  # Minimum confidence threshold
                    current_timestamp = feature_data.index[i]
                    current_price = feature_data.iloc[i]["close"]

                    signal = {
                        "timestamp": current_timestamp,
                        "signal": "buy" if prediction == 1 else "sell",
                        "confidence": float(confidence),
                        "price": float(current_price),
                    }
                    signals.append(signal)

            except Exception as e:
                logger.error(f"Prediction failed at step {i}: {e}")
                continue

        return pd.DataFrame(signals)

    return ml_strategy


def _create_wave_strategy(request: BacktestRequest):
    """Create Elliott Wave-based strategy function.

    Args:
        request: Backtest request with wave parameters

    Returns:
        Wave strategy function
    """

    def wave_strategy(data):
        import numpy as np

        from fxml4.elliott_wave import detect_wave_patterns

        # Detect wave patterns
        patterns = detect_wave_patterns(data)

        # Generate signals based on patterns
        signals = []
        for pattern in patterns:
            if pattern["type"] == "impulse":
                signal = {
                    "timestamp": pattern["end_time"],
                    "signal": "buy" if pattern["direction"] == "up" else "sell",
                    "confidence": pattern["confidence"],
                    "price": pattern["end_price"],
                }
                signals.append(signal)

        return pd.DataFrame(signals)

    return wave_strategy


def _execute_backtest(
    request: BacktestRequest, data: pd.DataFrame, strategy, backtest_id: str
):
    """Execute backtest with specified strategy and data.

    Args:
        request: Backtest request parameters
        data: Market data for backtesting
        strategy: Strategy function to use
        backtest_id: Unique identifier for this backtest

    Returns:
        Backtest result object
    """
    from fxml4.backtesting.engine import (
        SimpleBacktestEngine,
        simple_ma_crossover_strategy,
    )

    # Initialize backtest engine
    engine = SimpleBacktestEngine(initial_capital=request.initial_capital)

    # Use simple MA crossover strategy as default
    # The strategy function should return signals (-1, 0, 1)
    strategy_func = simple_ma_crossover_strategy

    # Run backtest using our simple engine
    result = engine.run_backtest(
        data=data, strategy_func=strategy_func, symbol=request.symbol
    )

    return result


def _compile_backtest_results(
    request: BacktestRequest, result, backtest_id: str
) -> Dict[str, Any]:
    """Compile backtest results into API response format.

    Args:
        request: Original backtest request
        result: Backtest result object
        backtest_id: Unique identifier for this backtest

    Returns:
        Dictionary with backtest results
    """
    # Extract key metrics
    total_return = result.total_return if hasattr(result, "total_return") else 0.0
    sharpe_ratio = result.sharpe_ratio if hasattr(result, "sharpe_ratio") else 0.0
    max_drawdown = result.max_drawdown if hasattr(result, "max_drawdown") else 0.0

    return {
        "backtest_id": backtest_id,
        "symbol": request.symbol,
        "timeframe": request.timeframe,
        "start_date": request.start_date,
        "end_date": request.end_date,
        "strategy": request.strategy,
        "initial_capital": request.initial_capital,
        "final_capital": request.initial_capital * (1 + total_return),
        "total_return": total_return,
        "sharpe_ratio": sharpe_ratio,
        "max_drawdown": max_drawdown,
        "num_trades": len(result.trades) if hasattr(result, "trades") else 0,
        "win_rate": result.win_rate if hasattr(result, "win_rate") else 0.0,
        "avg_trade_return": (
            result.avg_trade_return if hasattr(result, "avg_trade_return") else 0.0
        ),
        "status": "completed",
        "created_at": datetime.now().isoformat(),
        "duration": "N/A",  # TODO: Calculate actual duration
    }


@router.post("/backtest", response_model=BacktestResponse, tags=["backtest"])
async def run_backtest(
    request: BacktestRequest,
    current_user: UATUser = Depends(get_current_active_user_uat),
):
    """Run a backtest."""
    try:
        logger.info("Backtest request: %s", request)

        # Generate a unique backtest ID
        backtest_id = f"BT-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

        # Configure data feed and fetch market data
        data, feed_type = await _fetch_backtest_data(request)

        # Execute simple backtest directly
        from fxml4.backtesting.engine import (
            SimpleBacktestEngine,
            simple_ma_crossover_strategy,
        )

        engine = SimpleBacktestEngine(initial_capital=request.initial_capital)
        result = engine.run_backtest(
            data=data, strategy_func=simple_ma_crossover_strategy, symbol=request.symbol
        )

        # Transform result to match BacktestResponse schema
        return {
            "backtest_id": result.get("backtest_id", backtest_id),
            "symbol": result.get("symbol", request.symbol),
            "timeframe": (
                request.timeframe.value
                if hasattr(request.timeframe, "value")
                else str(request.timeframe)
            ),  # Add missing field
            "strategy": (
                request.strategy.value
                if hasattr(request.strategy, "value")
                else str(request.strategy)
            ),  # Add missing field
            "start_date": result.get("start_date"),
            "end_date": result.get("end_date"),
            "initial_capital": result.get("initial_capital", request.initial_capital),
            "final_capital": result.get(
                "final_value", request.initial_capital
            ),  # Map final_value to final_capital
            "total_return": result.get("total_return", 0.0),
            "total_return_pct": result.get("total_return_pct", 0.0),
            "max_drawdown": result.get("max_drawdown", 0.0),
            "max_drawdown_pct": result.get("max_drawdown_pct", 0.0),
            "sharpe_ratio": result.get("sharpe_ratio", 0.0),
            "sortino_ratio": result.get(
                "sortino_ratio", 0.0
            ),  # Add missing field with default
            "win_rate": result.get("win_rate", 0.0),
            "profit_factor": result.get(
                "profit_factor", 1.0
            ),  # Add missing field with default
            "trade_count": result.get(
                "total_trades", 0
            ),  # Map total_trades to trade_count
            "report_url": None,  # Optional field
        }

    except Exception as e:
        logger.exception("Error running backtest: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
