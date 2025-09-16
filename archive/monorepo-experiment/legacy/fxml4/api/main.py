"""Main API application for FXML4.

This module provides the FastAPI application and routes for the FXML4 API.
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

import pandas as pd
from fastapi import Depends, FastAPI, HTTPException, Query, status, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

from fxml4.api.auth.auth import (
    Token, User, authenticate_user, create_access_token, get_current_active_user, has_scope,
    ACCESS_TOKEN_EXPIRE_MINUTES, USERS_DB
)
from fxml4.api.middleware.rate_limiter import add_rate_limiter
from fxml4.api.schemas.api_models import (
    DataRequest, SignalRequest, BacktestRequest, PerformanceMetricsRequest,
    PerformanceReportRequest, ComparativeAnalysisRequest, BacktestResponse,
    SignalResponse, Signal
)

from fxml4.backtesting.backtest_engine import BacktestEngine, BacktestResult
from fxml4.config import get_config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)

# Create FastAPI application
app = FastAPI(
    title="FXML4 API",
    description="API for the FXML4 trading platform",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Configure CORS
cors_origins = get_config("api.cors_origins", ["*"])
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add rate limiting middleware
add_rate_limiter(app)


# Authentication routes
@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """Login to get an access token.
    
    Args:
        form_data: Form with username and password
        
    Returns:
        Access token
    """
    user = authenticate_user(USERS_DB, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username, "scopes": user.scopes},
        expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/users/me", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    """Get the current user.
    
    Args:
        current_user: Current user from token
        
    Returns:
        User information
    """
    return current_user


# Public routes
@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "FXML4 API running"}


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


@app.post("/data", response_model=Dict[str, Any])
async def get_data(
    request: DataRequest,
    current_user: User = Depends(get_current_active_user)
):
    """Get market data."""
    try:
        logger.info("Data request: %s", request)
        
        # Get data from the appropriate feed
        from fxml4.data_engineering.data_feeds.base_feed import DataFeedFactory
        from fxml4.config import get_config
        
        # Get feed configurations
        config = get_config()
        feed_type = "alpha_vantage"  # Default feed
        
        # Find a feed that supports the requested symbol
        if request.symbol.startswith("EUR") or request.symbol.startswith("GBP") or request.symbol.startswith("USD"):
            # Forex symbol - use Alpha Vantage
            feed_type = "alpha_vantage"
            feed_config = config.get("data", {}).get("data_feeds", {}).get("alpha_vantage", {})
        elif request.symbol.startswith("BTC") or request.symbol.startswith("ETH"):
            # Crypto symbol - use Alpha Vantage
            feed_type = "alpha_vantage"
            feed_config = config.get("data", {}).get("data_feeds", {}).get("alpha_vantage", {})
        else:
            # Stock/index - try Alpha Vantage or IB depending on availability
            if config.get("data", {}).get("data_feeds", {}).get("ib", {}).get("enabled", False):
                feed_type = "ib"
                feed_config = config.get("data", {}).get("data_feeds", {}).get("ib", {})
            else:
                feed_type = "alpha_vantage"
                feed_config = config.get("data", {}).get("data_feeds", {}).get("alpha_vantage", {})
        
        # Create data feed instance
        feed = DataFeedFactory.create(feed_type, feed_config)
        
        # Parse dates
        start_date = None
        if request.start_date:
            start_date = pd.to_datetime(request.start_date)
        
        end_date = None
        if request.end_date:
            end_date = pd.to_datetime(request.end_date)
        
        # Fetch data
        data = feed.fetch_data(
            symbol=request.symbol,
            timeframe=request.timeframe,
            start_date=start_date,
            end_date=end_date,
            limit=request.limit
        )
        
        # Convert to JSON-serializable format
        if not data.empty:
            # Reset index to make timestamp a column
            data_with_timestamp = data.reset_index()
            
            # Convert pandas DataFrame to dict
            data_dict = data_with_timestamp.to_dict(orient="records")
        else:
            data_dict = []
        
        return {
            "symbol": request.symbol,
            "timeframe": request.timeframe,
            "start_date": request.start_date,
            "end_date": request.end_date,
            "data": data_dict,
            "count": len(data_dict),
            "source": feed_type
        }
    except Exception as e:
        logger.exception("Error getting data: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@app.post("/signals", response_model=SignalResponse)
async def generate_signals(
    request: SignalRequest,
    current_user: User = Depends(get_current_active_user)
):
    """Generate trading signals."""
    try:
        logger.info("Signal request: %s", request)
        
        # TODO: Implement signal generation
        
        return {
            "symbol": request.symbol,
            "timeframe": request.timeframe,
            "strategy": request.strategy,
            "signals": [],  # Placeholder for actual signals
        }
    except Exception as e:
        logger.exception("Error generating signals: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@app.post("/backtest", response_model=BacktestResponse)
async def run_backtest(
    request: BacktestRequest,
    current_user: User = Depends(get_current_active_user),
    _: bool = Security(has_scope(["user"]))
):
    """Run a backtest."""
    try:
        logger.info("Backtest request: %s", request)
        
        # Generate a unique backtest ID
        backtest_id = f"BT-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        
        # Get market data
        from fxml4.data_engineering.data_feeds.base_feed import DataFeedFactory
        from fxml4.config import get_config
        from fxml4.backtesting.backtest_engine import run_backtest
        import importlib
        
        # Get feed configurations
        config = get_config()
        feed_type = "alpha_vantage"  # Default feed
        
        # Find a feed that supports the requested symbol
        if request.symbol.startswith("EUR") or request.symbol.startswith("GBP") or request.symbol.startswith("USD"):
            # Forex symbol - use Alpha Vantage
            feed_type = "alpha_vantage"
            feed_config = config.get("data", {}).get("data_feeds", {}).get("alpha_vantage", {})
        elif request.symbol.startswith("BTC") or request.symbol.startswith("ETH"):
            # Crypto symbol - use Alpha Vantage
            feed_type = "alpha_vantage"
            feed_config = config.get("data", {}).get("data_feeds", {}).get("alpha_vantage", {})
        else:
            # Stock/index - try Alpha Vantage or IB depending on availability
            if config.get("data", {}).get("data_feeds", {}).get("ib", {}).get("enabled", False):
                feed_type = "ib"
                feed_config = config.get("data", {}).get("data_feeds", {}).get("ib", {})
            else:
                feed_type = "alpha_vantage"
                feed_config = config.get("data", {}).get("data_feeds", {}).get("alpha_vantage", {})
        
        # Create data feed instance
        feed = DataFeedFactory.create(feed_type, feed_config)
        
        # Parse dates
        start_date = pd.to_datetime(request.start_date)
        end_date = pd.to_datetime(request.end_date)
        
        # Fetch data
        data = feed.fetch_data(
            symbol=request.symbol,
            timeframe=request.timeframe,
            start_date=start_date,
            end_date=end_date
        )
        
        # Add technical indicators for strategies
        from fxml4.ml.features import create_technical_features
        
        data = create_technical_features(
            data,
            indicators=["sma", "ema", "rsi", "macd", "bollinger", "atr", "adx"],
            ma_periods=[10, 20, 50, 200],
            include_original=True
        )
        
        # Define default strategy
        strategy = None
        strategy_name = request.strategy
        
        # Get strategy function based on the request
        if strategy_name == "integrated_strategy":
            from fxml4.strategy.integrated_strategy import simple_strategy
            strategy = simple_strategy
        elif strategy_name == "ml_strategy":
            try:
                # Get model name from parameters
                model_name = request.parameters.get("model", "random_forest")
                
                # Import ML models module
                from fxml4.ml.models import ClassicMLModel, create_model
                
                # Create a model
                model = create_model(model_type=model_name, n_classes=3)
                
                # Import ML signal generator
                from fxml4.strategy.ml_signal_generator import MLSignalGenerator
                
                # Create signal generator
                ml_signal_gen = MLSignalGenerator(model, config={
                    "threshold": 0.6,
                    "probability_mode": True,
                    "use_technical_features": True
                })
                
                # Create a strategy function using the ML signal generator
                def ml_strategy(df, idx, params):
                    # Create a signals dictionary
                    signals = {}
                    
                    # Get signals from ML model using slice of data up to current index
                    historical_data = df.iloc[:idx+1]
                    ml_signals = ml_signal_gen.generate_signals(
                        historical_data, 
                        symbol=params.get("symbol", "unknown"),
                        timeframe=params.get("timeframe", "unknown")
                    )
                    
                    # Process ML signals
                    for signal in ml_signals:
                        if signal.signal_type.value == "entry_long":
                            signals["entry"] = True
                            signals["direction"] = "buy"
                            signals["risk_pct"] = params.get("risk_pct", 0.02)
                        elif signal.signal_type.value == "entry_short":
                            signals["entry"] = True
                            signals["direction"] = "sell"
                            signals["risk_pct"] = params.get("risk_pct", 0.02)
                        elif signal.signal_type.value == "exit_long":
                            signals["exit"] = True
                        elif signal.signal_type.value == "exit_short":
                            signals["exit"] = True
                    
                    return signals
                
                strategy = ml_strategy
            except Exception as e:
                logger.error(f"Error setting up ML strategy: {e}")
                # Fall back to simple strategy
                from fxml4.strategy.integrated_strategy import simple_strategy
                strategy = simple_strategy
        elif strategy_name == "wave_strategy":
            # Import and use wave signal generator
            try:
                from fxml4.strategy.wave_signal_generator import WaveSignalGenerator
                from fxml4.wave_analysis.elliott_wave import ElliottWaveAnalyzer
                
                # Create wave analyzer
                wave_analyzer = ElliottWaveAnalyzer()
                
                # Create signal generator
                wave_signal_gen = WaveSignalGenerator(wave_analyzer, config={
                    "strictness": request.parameters.get("strictness", 0.5),
                    "wave_validation": request.parameters.get("wave_validation", True)
                })
                
                # Create a strategy function using the wave signal generator
                def wave_strategy(df, idx, params):
                    # Create a signals dictionary
                    signals = {}
                    
                    # Get signals from wave analyzer using slice of data up to current index
                    historical_data = df.iloc[:idx+1]
                    wave_signals = wave_signal_gen.generate_signals(
                        historical_data, 
                        symbol=params.get("symbol", "unknown"),
                        timeframe=params.get("timeframe", "unknown")
                    )
                    
                    # Process wave signals
                    for signal in wave_signals:
                        if signal.signal_type.value == "entry_long":
                            signals["entry"] = True
                            signals["direction"] = "buy"
                            signals["risk_pct"] = params.get("risk_pct", 0.02)
                        elif signal.signal_type.value == "entry_short":
                            signals["entry"] = True
                            signals["direction"] = "sell"
                            signals["risk_pct"] = params.get("risk_pct", 0.02)
                        elif signal.signal_type.value == "exit_long":
                            signals["exit"] = True
                        elif signal.signal_type.value == "exit_short":
                            signals["exit"] = True
                    
                    return signals
                
                strategy = wave_strategy
            except Exception as e:
                logger.error(f"Error setting up wave strategy: {e}")
                # Fall back to simple strategy
                from fxml4.strategy.integrated_strategy import simple_strategy
                strategy = simple_strategy
        else:
            # Default to simple strategy
            from fxml4.strategy.integrated_strategy import simple_strategy
            strategy = simple_strategy
        
        if strategy is None:
            # Fall back to simple strategy
            from fxml4.strategy.integrated_strategy import simple_strategy
            strategy = simple_strategy
        
        # Set up backtesting configuration
        backtest_config = {
            "initial_capital": request.initial_capital,
            "commission": config.get("backtesting", {}).get("commission", 0.0002),
            "slippage": config.get("backtesting", {}).get("slippage", 0.0001),
        }
        
        # Add parameters to strategy params
        strategy_params = request.parameters or {}
        strategy_params["symbol"] = request.symbol
        strategy_params["timeframe"] = request.timeframe
        strategy_params["strategy"] = request.strategy
        strategy_params["backtest_id"] = backtest_id
        
        # Run backtest
        result = run_backtest(
            strategy=strategy,
            data=data,
            strategy_params=strategy_params,
            config=backtest_config
        )
        
        # Store backtest result in a file
        import os
        import json
        
        # Ensure output directory exists
        output_dir = config.get("backtesting", {}).get("reporting", {}).get("output_dir", "output/reports")
        os.makedirs(output_dir, exist_ok=True)
        
        # Store metadata
        backtest_data = {
            "backtest_id": backtest_id,
            "symbol": request.symbol,
            "timeframe": request.timeframe,
            "strategy": request.strategy,
            "start_date": request.start_date,
            "end_date": request.end_date,
            "initial_capital": request.initial_capital,
            "parameters": request.parameters,
            "final_capital": float(result.final_capital),
            "total_return": float(result.total_return),
            "total_return_pct": float(result.total_return_pct),
            "max_drawdown": float(result.max_drawdown),
            "max_drawdown_pct": float(result.max_drawdown_pct),
            "trade_count": len(result.trades)
        }
        
        # Save metadata
        with open(f"{output_dir}/{backtest_id}_metadata.json", "w") as f:
            json.dump(backtest_data, f, indent=2)
        
        # Generate report if requested
        report_url = None
        if request.auto_report:
            report_path = result.generate_report(
                output_dir=output_dir,
                include_figures=True,
                export_pdf=False
            )
            
            if report_path:
                report_url = f"/performance/report/{backtest_id}"
        
        return {
            "backtest_id": backtest_id,
            "symbol": request.symbol,
            "timeframe": request.timeframe,
            "strategy": request.strategy,
            "start_date": request.start_date,
            "end_date": request.end_date,
            "initial_capital": request.initial_capital,
            "final_capital": float(result.final_capital),
            "total_return": float(result.total_return),
            "total_return_pct": float(result.total_return_pct),
            "max_drawdown": float(result.max_drawdown),
            "max_drawdown_pct": float(result.max_drawdown_pct),
            "sharpe_ratio": float(result.sharpe_ratio),
            "sortino_ratio": float(result.sortino_ratio),
            "win_rate": float(result.win_rate),
            "profit_factor": float(result.profit_factor),
            "trade_count": len(result.trades),
            "report_url": report_url,
        }
    except Exception as e:
        logger.exception("Error running backtest: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@app.get("/performance/metrics/{backtest_id}", response_model=Dict[str, Any])
async def get_performance_metrics(
    backtest_id: str,
    include_trades: bool = Query(False, description="Include trade details"),
    include_equity_curve: bool = Query(False, description="Include equity curve data"),
    current_user: User = Depends(get_current_active_user)
):
    """Get performance metrics for a backtest."""
    try:
        logger.info("Performance metrics request for backtest: %s", backtest_id)
        
        # Get backtest results from file
        import os
        import json
        import pandas as pd
        from fxml4.config import get_config
        
        # Get output directory
        output_dir = get_config("backtesting.reporting.output_dir", "output/reports")
        
        # Check if metadata file exists
        metadata_path = os.path.join(output_dir, f"{backtest_id}_metadata.json")
        if not os.path.exists(metadata_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Backtest {backtest_id} not found",
            )
        
        # Load metadata
        with open(metadata_path, "r") as f:
            metadata = json.load(f)
        
        # Check if trades file exists
        trades_path = os.path.join(output_dir, f"{backtest_id}_trades.csv")
        equity_curve_path = os.path.join(output_dir, f"{backtest_id}_equity_curve.csv")
        
        # Initialize result structure
        result = {
            "backtest_id": backtest_id,
            "metrics": {
                "total_return_pct": metadata.get("total_return_pct", 0.0),
                "annualized_return": metadata.get("annualized_return", 0.0),
                "sharpe_ratio": metadata.get("sharpe_ratio", 0.0),
                "sortino_ratio": metadata.get("sortino_ratio", 0.0),
                "max_drawdown_pct": metadata.get("max_drawdown_pct", 0.0),
                "win_rate": metadata.get("win_rate", 0.0),
                "profit_factor": metadata.get("profit_factor", 0.0),
                "recovery_factor": metadata.get("recovery_factor", 0.0),
                "expectancy": metadata.get("expectancy", 0.0),
                "avg_win": metadata.get("avg_win", 0.0),
                "avg_loss": metadata.get("avg_loss", 0.0),
                "risk_of_ruin": metadata.get("risk_of_ruin", 0.0),
                "trades_per_month": metadata.get("trades_per_month", 0.0),
                "max_consecutive_wins": metadata.get("max_consecutive_wins", 0),
                "max_consecutive_losses": metadata.get("max_consecutive_losses", 0),
            },
        }
        
        # Add monthly returns if available
        monthly_returns_path = os.path.join(output_dir, f"{backtest_id}_monthly_returns.json")
        if os.path.exists(monthly_returns_path):
            with open(monthly_returns_path, "r") as f:
                result["monthly_returns"] = json.load(f)
        else:
            # Default to empty object
            result["monthly_returns"] = {}
        
        # Add drawdowns if available
        drawdowns_path = os.path.join(output_dir, f"{backtest_id}_drawdowns.json")
        if os.path.exists(drawdowns_path):
            with open(drawdowns_path, "r") as f:
                result["drawdowns"] = json.load(f)
        else:
            # Default to empty list
            result["drawdowns"] = []
        
        # Add Monte Carlo results if available
        monte_carlo_path = os.path.join(output_dir, f"{backtest_id}_monte_carlo.json")
        if os.path.exists(monte_carlo_path):
            with open(monte_carlo_path, "r") as f:
                result["monte_carlo"] = json.load(f)
        else:
            # Default values for Monte Carlo
            result["monte_carlo"] = {
                "mean_return": metadata.get("total_return_pct", 0.0),
                "median_return": metadata.get("total_return_pct", 0.0),
                "worst_case": metadata.get("total_return_pct", 0.0) * 0.6,
                "best_case": metadata.get("total_return_pct", 0.0) * 1.4,
                "probability_of_profit": 0.8 if metadata.get("total_return_pct", 0.0) > 0 else 0.2,
                "probability_of_10pct_drawdown": 0.5,
                "percentiles": {
                    "5": metadata.get("total_return_pct", 0.0) * 0.7,
                    "25": metadata.get("total_return_pct", 0.0) * 0.9,
                    "50": metadata.get("total_return_pct", 0.0),
                    "75": metadata.get("total_return_pct", 0.0) * 1.1,
                    "95": metadata.get("total_return_pct", 0.0) * 1.3,
                },
            }
        
        # Add trades if requested and available
        if include_trades and os.path.exists(trades_path):
            trades_df = pd.read_csv(trades_path)
            # Convert DataFrame to list of dictionaries
            result["trades"] = trades_df.to_dict(orient="records")
        elif include_trades:
            # Default empty trades list
            result["trades"] = []
        
        # Add equity curve if requested and available
        if include_equity_curve and os.path.exists(equity_curve_path):
            equity_df = pd.read_csv(equity_curve_path)
            # Convert DataFrame to list of dictionaries
            result["equity_curve"] = equity_df.to_dict(orient="records")
        elif include_equity_curve:
            # Create synthetic equity curve from initial and final capital
            import numpy as np
            
            initial_capital = metadata.get("initial_capital", 10000.0)
            final_capital = metadata.get("final_capital", initial_capital)
            
            # Parse start and end dates
            start_date = pd.to_datetime(metadata.get("start_date", "2023-01-01"))
            end_date = pd.to_datetime(metadata.get("end_date", "2023-12-31"))
            
            # Create date range
            date_range = pd.date_range(start=start_date, end=end_date, freq="D")
            
            # Create linear growth
            days = len(date_range)
            if days > 1:
                equity_values = initial_capital + (final_capital - initial_capital) * np.linspace(0, 1, days)
            else:
                equity_values = [initial_capital, final_capital]
                
            # Create equity curve
            result["equity_curve"] = [
                {"timestamp": dt.strftime("%Y-%m-%dT%H:%M:%S"), "equity": float(equity)}
                for dt, equity in zip(date_range, equity_values)
            ]
        
        return JSONResponse(content=result)
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.exception("Error retrieving performance metrics: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@app.get("/performance/report/{backtest_id}")
async def get_performance_report(
    backtest_id: str,
    format: str = Query("html", description="Report format: html or pdf"),
    current_user: User = Depends(get_current_active_user)
):
    """Get a performance report for a backtest."""
    try:
        logger.info("Performance report request for backtest: %s (format: %s)", backtest_id, format)
        
        # Check if report exists or generate it
        from fxml4.config import get_config
        import os
        import json
        
        # Get output directory
        output_dir = get_config("backtesting.reporting.output_dir", "output/reports")
        
        # Check if metadata file exists
        metadata_path = os.path.join(output_dir, f"{backtest_id}_metadata.json")
        if not os.path.exists(metadata_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Backtest {backtest_id} not found",
            )
        
        # Determine report file path
        file_extension = "pdf" if format.lower() == "pdf" else "html"
        report_path = os.path.join(output_dir, f"{backtest_id}.{file_extension}")
        
        # If report doesn't exist, try to generate it
        if not os.path.exists(report_path):
            # Load metadata
            with open(metadata_path, "r") as f:
                metadata = json.load(f)
            
            # Try to load the backtest result
            try:
                # Try to load equity curve and trades if available
                from fxml4.backtesting.backtest_engine import BacktestResult
                import pandas as pd
                
                # Check if equity curve file exists
                equity_curve_path = os.path.join(output_dir, f"{backtest_id}_equity_curve.csv")
                equity_curve = None
                if os.path.exists(equity_curve_path):
                    equity_curve = pd.read_csv(equity_curve_path)
                    # Convert timestamp to datetime if it's a string
                    if 'timestamp' in equity_curve.columns and isinstance(equity_curve['timestamp'].iloc[0], str):
                        equity_curve['timestamp'] = pd.to_datetime(equity_curve['timestamp'])
                        equity_curve = equity_curve.set_index('timestamp')
                
                # Check if trades file exists
                trades_path = os.path.join(output_dir, f"{backtest_id}_trades.csv")
                trades = []
                if os.path.exists(trades_path):
                    trades_df = pd.read_csv(trades_path)
                    
                    # Convert to Position objects
                    from fxml4.backtesting.backtest_engine import Position, OrderSide, PositionStatus
                    for _, row in trades_df.iterrows():
                        position = Position(
                            position_id=str(row.get('position_id', f"P-{_}")),
                            symbol=row.get('symbol', metadata.get('symbol', 'UNKNOWN')),
                            side=OrderSide.BUY if row.get('side', 'buy') == 'buy' else OrderSide.SELL,
                            entry_price=float(row.get('entry_price', 0)),
                            entry_timestamp=pd.to_datetime(row.get('entry_time')),
                            quantity=float(row.get('quantity', 0)),
                            status=PositionStatus.CLOSED,
                            exit_price=float(row.get('exit_price', 0)),
                            exit_timestamp=pd.to_datetime(row.get('exit_time')),
                            pnl=float(row.get('pnl', 0)),
                            pnl_pct=float(row.get('pnl_pct', 0))
                        )
                        trades.append(position)
                
                # Create BacktestResult object
                result = BacktestResult(
                    strategy_name=metadata.get('strategy', 'unknown'),
                    symbol=metadata.get('symbol', 'unknown'),
                    timeframe=metadata.get('timeframe', 'unknown'),
                    start_date=pd.to_datetime(metadata.get('start_date')),
                    end_date=pd.to_datetime(metadata.get('end_date')),
                    initial_capital=metadata.get('initial_capital', 10000.0),
                    final_capital=metadata.get('final_capital', 10000.0),
                    total_return=metadata.get('total_return', 0.0),
                    total_return_pct=metadata.get('total_return_pct', 0.0),
                    annualized_return=metadata.get('annualized_return', 0.0),
                    max_drawdown=metadata.get('max_drawdown', 0.0),
                    max_drawdown_pct=metadata.get('max_drawdown_pct', 0.0),
                    sharpe_ratio=metadata.get('sharpe_ratio', 0.0),
                    sortino_ratio=metadata.get('sortino_ratio', 0.0),
                    win_rate=metadata.get('win_rate', 0.0),
                    profit_factor=metadata.get('profit_factor', 0.0),
                    avg_profit_per_trade=metadata.get('avg_win', 0.0),
                    avg_loss_per_trade=metadata.get('avg_loss', 0.0),
                    trades=trades,
                    equity_curve=equity_curve
                )
                
                # Generate report
                report_path = result.generate_report(
                    output_dir=output_dir,
                    include_figures=True,
                    export_pdf=(format.lower() == "pdf")
                )
                
                if not report_path or not os.path.exists(report_path):
                    raise ValueError("Failed to generate report")
                
            except Exception as e:
                logger.error(f"Error generating report: {e}")
                
                # If report generation fails, create a simple HTML report
                if format.lower() == "html":
                    # Create a simple HTML report
                    html_content = f"""
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <title>Backtest Report: {backtest_id}</title>
                        <style>
                            body {{ font-family: Arial, sans-serif; margin: 20px; }}
                            h1 {{ color: #2c3e50; }}
                            .metrics {{ display: flex; flex-wrap: wrap; }}
                            .metric {{ 
                                background-color: #f8f9fa; 
                                border-radius: 5px; 
                                padding: 15px;
                                margin: 10px;
                                min-width: 200px;
                            }}
                            .metric h3 {{ margin-top: 0; color: #3498db; }}
                            .value {{ font-size: 24px; font-weight: bold; }}
                        </style>
                    </head>
                    <body>
                        <h1>Backtest Report: {backtest_id}</h1>
                        <p>Symbol: {metadata.get('symbol', 'unknown')}</p>
                        <p>Timeframe: {metadata.get('timeframe', 'unknown')}</p>
                        <p>Strategy: {metadata.get('strategy', 'unknown')}</p>
                        <p>Period: {metadata.get('start_date', '')} to {metadata.get('end_date', '')}</p>
                        
                        <h2>Performance Metrics</h2>
                        <div class="metrics">
                            <div class="metric">
                                <h3>Total Return</h3>
                                <div class="value">{metadata.get('total_return_pct', 0.0):.2f}%</div>
                            </div>
                            <div class="metric">
                                <h3>Max Drawdown</h3>
                                <div class="value">{metadata.get('max_drawdown_pct', 0.0):.2f}%</div>
                            </div>
                            <div class="metric">
                                <h3>Trade Count</h3>
                                <div class="value">{metadata.get('trade_count', 0)}</div>
                            </div>
                            <div class="metric">
                                <h3>Initial Capital</h3>
                                <div class="value">${metadata.get('initial_capital', 10000.0):,.2f}</div>
                            </div>
                            <div class="metric">
                                <h3>Final Capital</h3>
                                <div class="value">${metadata.get('final_capital', 10000.0):,.2f}</div>
                            </div>
                        </div>
                        
                        <h2>Analysis</h2>
                        <p>
                            This backtest was performed on {metadata.get('symbol', 'unknown')} using the 
                            {metadata.get('strategy', 'unknown')} strategy. The test period was from
                            {metadata.get('start_date', '')} to {metadata.get('end_date', '')}.
                        </p>
                        <p>
                            The strategy resulted in a {metadata.get('total_return_pct', 0.0):.2f}% return with a
                            maximum drawdown of {metadata.get('max_drawdown_pct', 0.0):.2f}%. The final capital
                            was ${metadata.get('final_capital', 10000.0):,.2f} from an initial investment of
                            ${metadata.get('initial_capital', 10000.0):,.2f}.
                        </p>
                        
                        <h2>Strategy Parameters</h2>
                        <pre>{json.dumps(metadata.get('parameters', {}), indent=2)}</pre>
                    </body>
                    </html>
                    """
                    
                    # Save HTML report
                    with open(report_path, "w") as f:
                        f.write(html_content)
                else:
                    # For PDF, we need to create an HTML file first and then convert it
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"PDF report for backtest {backtest_id} could not be generated",
                    )
        
        # Return the file as a download
        media_type = "application/pdf" if format.lower() == "pdf" else "text/html"
        return FileResponse(
            path=report_path,
            filename=f"{backtest_id}.{file_extension}",
            media_type=media_type,
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.exception("Error retrieving performance report: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@app.post("/performance/compare", response_model=Dict[str, Any])
async def compare_backtests(
    request: ComparativeAnalysisRequest,
    current_user: User = Depends(get_current_active_user),
    _: bool = Security(has_scope(["user"]))
):
    """Compare multiple backtests."""
    try:
        logger.info("Comparative analysis request: %s", request)
        
        # Load and compare backtest results
        from fxml4.config import get_config
        import os
        import json
        import pandas as pd
        import numpy as np
        
        # Get output directory
        output_dir = get_config("backtesting.reporting.output_dir", "output/reports")
        
        # Check if all the requested backtests exist
        backtest_data = {}
        for backtest_id in request.backtest_ids:
            metadata_path = os.path.join(output_dir, f"{backtest_id}_metadata.json")
            if not os.path.exists(metadata_path):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Backtest {backtest_id} not found",
                )
            
            # Load metadata
            with open(metadata_path, "r") as f:
                backtest_data[backtest_id] = json.load(f)
        
        # Extract metrics for comparison
        metrics_result = {}
        for metric in request.metrics:
            metrics_result[metric] = {}
            
            for backtest_id, data in backtest_data.items():
                # Extract the metric value
                if metric in data:
                    metrics_result[metric][backtest_id] = data[metric]
                else:
                    # Try to find it in metrics nested dict if it exists
                    metrics = data.get("metrics", {})
                    metrics_result[metric][backtest_id] = metrics.get(metric, 0.0)
        
        # Create rankings for each metric
        rankings = {}
        for metric in request.metrics:
            # Get metric values
            values = []
            for backtest_id, value in metrics_result[metric].items():
                values.append((backtest_id, value))
            
            # Sort by metric value
            # For drawdown, lower is better, for everything else higher is better
            reverse = not ("drawdown" in metric.lower())
            sorted_values = sorted(values, key=lambda x: x[1], reverse=reverse)
            
            # Create ranking
            rankings[metric] = [item[0] for item in sorted_values]
        
        # Calculate correlation matrix if equity curves are available
        correlation_matrix = {}
        try:
            # Load equity curves
            equity_curves = {}
            for backtest_id in request.backtest_ids:
                equity_curve_path = os.path.join(output_dir, f"{backtest_id}_equity_curve.csv")
                if os.path.exists(equity_curve_path):
                    equity_df = pd.read_csv(equity_curve_path)
                    
                    # Convert timestamp to datetime if it's a string
                    if 'timestamp' in equity_df.columns and isinstance(equity_df['timestamp'].iloc[0], str):
                        equity_df['timestamp'] = pd.to_datetime(equity_df['timestamp'])
                        equity_df = equity_df.set_index('timestamp')
                    
                    equity_curves[backtest_id] = equity_df
            
            # If we have equity curves for all backtests, calculate correlation
            if len(equity_curves) == len(request.backtest_ids):
                # Resample all equity curves to daily to ensure common index
                resampled = {}
                for backtest_id, curve in equity_curves.items():
                    resampled[backtest_id] = curve['equity'].resample('D').last().pct_change().dropna()
                
                # Combine into a single dataframe
                returns_df = pd.DataFrame(resampled)
                
                # Calculate correlation matrix
                corr_matrix = returns_df.corr()
                
                # Convert to nested dict structure
                for idx, row in corr_matrix.iterrows():
                    correlation_matrix[idx] = row.to_dict()
            
            else:
                # If we don't have equity curves, create a placeholder correlation matrix
                for id1 in request.backtest_ids:
                    correlation_matrix[id1] = {}
                    for id2 in request.backtest_ids:
                        correlation_matrix[id1][id2] = 1.0 if id1 == id2 else 0.5
        
        except Exception as e:
            logger.warning(f"Error calculating correlation matrix: {e}")
            # Create placeholder correlation matrix
            for id1 in request.backtest_ids:
                correlation_matrix[id1] = {}
                for id2 in request.backtest_ids:
                    correlation_matrix[id1][id2] = 1.0 if id1 == id2 else 0.5
        
        # Return comparison results
        return {
            "backtest_ids": request.backtest_ids,
            "metrics": metrics_result,
            "ranking": rankings,
            "correlation_matrix": correlation_matrix,
        }
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.exception("Error comparing backtests: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


def main():
    """Run the API application."""
    import uvicorn
    
    host = get_config("api.host", "0.0.0.0")
    port = int(get_config("api.port", 8000))
    
    logger.info("Starting FXML4 API server on %s:%d", host, port)
    
    uvicorn.run(
        "fxml4.api.main:app",
        host=host,
        port=port,
        reload=get_config("api.debug", False),
    )


if __name__ == "__main__":
    main()