"""Backtesting module for Elliott Wave pattern detection with realistic market simulation."""

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
from scipy.stats import norm

from fxml3.data_engineering.data_loader import ForexDataLoader
from fxml3.wave_analysis.elliott_wave import ElliottWaveAnalyzer
from fxml3.wave_analysis.fractal import FractalDegreeHandler


class WaveBacktester:
    """Backtests Elliott Wave pattern detection algorithms with realistic market simulation.
    
    This class evaluates the accuracy of Elliott Wave pattern detection by comparing
    predicted patterns with actual future price movements. It uses a rolling window
    approach to simulate real-time detection and prediction, including realistic 
    market conditions like slippage, spread, and liquidity constraints.
    """
    
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
        self.data_loader = data_loader or ForexDataLoader()
        self.wave_analyzer = wave_analyzer or ElliottWaveAnalyzer()
        self.fractal_handler = fractal_handler
        
        # Market simulation parameters
        self.slippage_model = slippage_model
        self.spread_model = spread_model
        self.commission_model = commission_model
        
        # Default simulation parameters
        self.slippage_params = {
            "fixed": 1.0,  # 1 pip fixed slippage
            "normal": {
                "mean": 0.5,  # Mean slippage of 0.5 pips
                "std": 0.3,   # Standard deviation of 0.3 pips
            },
            "pareto": {
                "alpha": 1.5,   # Shape parameter
                "scale": 0.3,   # Scale parameter
            }
        }
        
        self.spread_params = {
            "fixed": 1.5,  # 1.5 pips fixed spread
            "variable": {
                "min": 0.9,   # Minimum spread
                "max": 2.5,   # Maximum spread
                "volatility_factor": 0.7,  # How much volatility affects spread
            },
            "volatile": {
                "base": 1.2,  # Base spread
                "spike_probability": 0.05,  # Probability of spread spikes
                "spike_multiplier": 5.0,  # Multiplier during spikes
            }
        }
        
        self.commission_params = {
            "fixed": 5.0,  # $5 per trade
            "percentage": 0.0001,  # 0.01% of trade value
        }
        
        # Store backtest results
        self.results = {}
        
        # Store predictions and actual outcomes
        self.predictions = []
        self.actual_outcomes = []
        
        # Order execution and position tracking
        self.positions = []
        self.orders = []
        self.trades = []
        
    def prepare_data(
        self,
        symbol: str,
        start_date: Union[str, datetime],
        end_date: Optional[Union[str, datetime]] = None,
        timeframe: str = "1D",
        split_ratio: float = 0.7,
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Prepare data for backtesting by loading and splitting it.
        
        Args:
            symbol: Symbol to backtest (e.g., "EURUSD")
            start_date: Start date for historical data
            end_date: End date for historical data
            timeframe: Timeframe to use (e.g., "1D", "4H", "1H")
            split_ratio: Ratio to split training/testing data
            
        Returns:
            Tuple of (training_data, testing_data) DataFrames
        """
        # Load historical data
        df = self.data_loader.load_data(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            timeframe=timeframe,
        )
        
        # Ensure data has required columns
        required_columns = ["open", "high", "low", "close"]
        for col in required_columns:
            if col not in df.columns:
                raise ValueError(f"Required column '{col}' not found in DataFrame")
        
        # Split data into training and testing sets
        split_idx = int(len(df) * split_ratio)
        training_data = df.iloc[:split_idx].copy()
        testing_data = df.iloc[split_idx:].copy()
        
        return training_data, testing_data
    
    def run_rolling_window_backtest(
        self,
        data: pd.DataFrame,
        window_size: int = 100,
        step_size: int = 20,
        prediction_horizon: int = 20,
    ) -> Dict[str, Any]:
        """Run a rolling window backtest on the data.
        
        Simulates real-time detection by analyzing fixed-size windows of data
        and making predictions about future price movements based on detected patterns.
        
        Args:
            data: DataFrame with price data
            window_size: Size of the rolling window (number of bars)
            step_size: Number of bars to advance the window each iteration
            prediction_horizon: Number of bars to predict into the future
            
        Returns:
            Dictionary with backtest results
        """
        if len(data) < window_size + prediction_horizon:
            raise ValueError("Not enough data for rolling window backtest")
        
        # Reset prediction storage
        self.predictions = []
        self.actual_outcomes = []
        
        # Track detection statistics
        stats = {
            "total_windows": 0,
            "impulse_patterns_detected": 0,
            "corrective_patterns_detected": 0,
            "predictions_made": 0,
            "correct_predictions": 0,
            "incorrect_predictions": 0,
            "prediction_accuracy": 0.0,
            "windows": [],
        }
        
        # Run rolling window analysis
        for start_idx in range(0, len(data) - window_size - prediction_horizon, step_size):
            # Extract window data
            end_idx = start_idx + window_size
            window_data = data.iloc[start_idx:end_idx].copy()
            
            # Extract future data for validation
            future_data = data.iloc[end_idx:end_idx + prediction_horizon].copy()
            
            # Detect waves in the window
            wave_points = self.wave_analyzer.detect_waves(window_data)
            
            # Skip if no waves detected
            if not wave_points:
                continue
                
            window_stats = self._analyze_window_and_predict(
                window_data, future_data, wave_points, start_idx, end_idx
            )
            
            # Update overall statistics
            stats["total_windows"] += 1
            stats["impulse_patterns_detected"] += window_stats["impulse_patterns"]
            stats["corrective_patterns_detected"] += window_stats["corrective_patterns"]
            stats["predictions_made"] += window_stats["predictions_made"]
            stats["correct_predictions"] += window_stats["correct_predictions"]
            stats["windows"].append(window_stats)
        
        # Calculate overall accuracy
        if stats["predictions_made"] > 0:
            stats["prediction_accuracy"] = stats["correct_predictions"] / stats["predictions_made"]
            stats["incorrect_predictions"] = stats["predictions_made"] - stats["correct_predictions"]
        
        # Store results
        self.results = stats
        
        return stats
    
    def _analyze_window_and_predict(
        self,
        window_data: pd.DataFrame,
        future_data: pd.DataFrame,
        wave_points: Dict[str, List[Tuple[int, float]]],
        start_idx: int,
        end_idx: int,
    ) -> Dict[str, Any]:
        """Analyze a window, make predictions, and validate against future data.
        
        Args:
            window_data: Current window data
            future_data: Future data for validation
            wave_points: Detected wave points in the window
            start_idx: Start index of the window in the original data
            end_idx: End index of the window in the original data
            
        Returns:
            Dictionary with window analysis statistics
        """
        window_stats = {
            "start_idx": start_idx,
            "end_idx": end_idx,
            "impulse_patterns": 0,
            "corrective_patterns": 0,
            "predictions_made": 0,
            "correct_predictions": 0,
            "incorrect_predictions": 0,
            "prediction_details": [],
        }
        
        # Check for completed impulse or corrective patterns at the end of the window
        impulse_pattern_keys = [k for k in wave_points.keys() if k.startswith("impulse_") and k.endswith("_end")]
        corrective_pattern_keys = [k for k in wave_points.keys() if k.startswith("corrective_") and k.endswith("_end")]
        
        # Count patterns
        window_stats["impulse_patterns"] = len(impulse_pattern_keys) // 5  # 5 waves per impulse pattern
        window_stats["corrective_patterns"] = len(corrective_pattern_keys) // 3  # 3 waves per corrective pattern
        
        # Make predictions based on completed patterns
        # Focus on the patterns that end near the end of the window
        predictions = self._generate_predictions(window_data, wave_points)
        
        # Validate predictions against future data
        for prediction in predictions:
            prediction_result = self._validate_prediction(prediction, future_data)
            
            # Update statistics
            window_stats["predictions_made"] += 1
            if prediction_result["correct"]:
                window_stats["correct_predictions"] += 1
            
            # Store prediction details
            window_stats["prediction_details"].append({
                "pattern_type": prediction["pattern_type"],
                "predicted_direction": prediction["direction"],
                "predicted_target": prediction["target_price"],
                "actual_outcome": prediction_result["actual_price"],
                "correct": prediction_result["correct"],
                "time_to_target": prediction_result["time_to_target"],
            })
            
            # Store for overall analysis
            self.predictions.append(prediction)
            self.actual_outcomes.append(prediction_result)
        
        return window_stats
    
    def _generate_predictions(
        self,
        data: pd.DataFrame,
        wave_points: Dict[str, List[Tuple[int, float]]],
    ) -> List[Dict[str, Any]]:
        """Generate predictions based on detected wave patterns.
        
        Args:
            data: DataFrame with price data
            wave_points: Detected wave points
            
        Returns:
            List of prediction dictionaries
        """
        predictions = []
        
        # Look for completed impulse patterns (wave 5 end)
        impulse_wave5_end_keys = [k for k in wave_points.keys() if k.startswith("impulse_") and k.endswith("5_end")]
        
        for wave_key in impulse_wave5_end_keys:
            # Get the base key (without the "_5_end" suffix)
            base_key = wave_key[:-5]  # Remove "_5_end"
            
            # Check if we have all the required wave points for this pattern
            wave_keys = [f"{base_key}{i}_end" for i in range(1, 6)]
            if not all(k in wave_points for k in wave_keys):
                continue
                
            # Get wave 5 end point (most recent)
            wave5_end_points = wave_points[f"{base_key}5_end"]
            if not wave5_end_points:
                continue
                
            # Get most recent wave 5 end point
            wave5_end_idx, wave5_end_price = wave5_end_points[-1]
            
            # Get wave 1 start point for the same pattern
            wave1_start_key = f"{base_key}1_start"
            if wave1_start_key not in wave_points or not wave_points[wave1_start_key]:
                continue
                
            wave1_start_idx, wave1_start_price = wave_points[wave1_start_key][0]
            
            # Calculate pattern height
            pattern_height = abs(wave5_end_price - wave1_start_price)
            
            # After impulse pattern, predict a corrective pattern (opposite direction)
            # with target at 50% to 61.8% retracement
            if wave5_end_price > wave1_start_price:  # Upward impulse
                direction = "down"
                # Target: 50-61.8% retracement
                target_price = wave5_end_price - (pattern_height * 0.618)
            else:  # Downward impulse
                direction = "up"
                # Target: 50-61.8% retracement
                target_price = wave5_end_price + (pattern_height * 0.618)
            
            prediction = {
                "pattern_type": "impulse",
                "pattern_key": base_key,
                "end_idx": wave5_end_idx,
                "end_price": wave5_end_price,
                "direction": direction,
                "target_price": target_price,
                "confidence": 0.8,  # Higher confidence for impulse pattern projections
            }
            
            predictions.append(prediction)
        
        # Look for completed corrective patterns (wave C end)
        corrective_waveC_end_keys = [k for k in wave_points.keys() if k.startswith("corrective_") and k.endswith("C_end")]
        
        for wave_key in corrective_waveC_end_keys:
            # Get the base key (without the "_C_end" suffix)
            base_key = wave_key[:-5]  # Remove "_C_end"
            
            # Check if we have all the required wave points for this pattern
            wave_keys = [f"{base_key}{w}_end" for w in ["A", "B", "C"]]
            if not all(k in wave_points for k in wave_keys):
                continue
                
            # Get wave C end point (most recent)
            waveC_end_points = wave_points[f"{base_key}C_end"]
            if not waveC_end_points:
                continue
                
            # Get most recent wave C end point
            waveC_end_idx, waveC_end_price = waveC_end_points[-1]
            
            # Get wave A start point for the same pattern
            waveA_start_key = f"{base_key}A_start"
            if waveA_start_key not in wave_points or not wave_points[waveA_start_key]:
                continue
                
            waveA_start_idx, waveA_start_price = wave_points[waveA_start_key][0]
            
            # Calculate pattern height
            pattern_height = abs(waveC_end_price - waveA_start_price)
            
            # After corrective pattern, predict a new move in the original trend direction
            if waveC_end_price < waveA_start_price:  # Downward correction
                direction = "up"
                # Target: 100% of the correction
                target_price = waveA_start_price
            else:  # Upward correction
                direction = "down"
                # Target: 100% of the correction
                target_price = waveA_start_price
            
            prediction = {
                "pattern_type": "corrective",
                "pattern_key": base_key,
                "end_idx": waveC_end_idx,
                "end_price": waveC_end_price,
                "direction": direction,
                "target_price": target_price,
                "confidence": 0.7,  # Slightly lower confidence for corrective patterns
            }
            
            predictions.append(prediction)
        
        return predictions
    
    def _validate_prediction(
        self,
        prediction: Dict[str, Any],
        future_data: pd.DataFrame,
        account_balance: float = 10000.0,
        position_size: float = 10000.0,  # Standard lot: 100,000 units
        risk_percent: float = 2.0,  # Risk 2% per trade
    ) -> Dict[str, Any]:
        """Validate a prediction against future price data with realistic market simulation.
        
        Args:
            prediction: The prediction to validate
            future_data: Future price data
            account_balance: Starting account balance for this trade
            position_size: Position size in currency units
            risk_percent: Percentage of account balance to risk per trade
            
        Returns:
            Dictionary with validation results including simulated execution details
        """
        direction = prediction["direction"]
        target_price = prediction["target_price"]
        
        # Initialize result
        result = {
            "correct": False,
            "time_to_target": None,
            "actual_price": None,
            "max_favorable_move": 0.0,
            "max_adverse_move": 0.0,
            "trade_pnl": 0.0,
            "execution_price": 0.0,
            "exit_price": 0.0,
            "slippage": 0.0,
            "spread_cost": 0.0,
            "commission": 0.0,
            "total_cost": 0.0,
            "risk_amount": 0.0,
            "realized_return": 0.0,
        }
        
        if not future_data.empty:
            start_price = prediction["end_price"]
            
            # Calculate realistic entry price with slippage and spread
            entry_slippage = self._calculate_slippage(start_price, direction)
            entry_spread = self._calculate_spread(future_data.iloc[0], start_price)
            
            # Apply slippage and spread to entry price
            if direction == "up":
                # Buying: pay the ask price (higher)
                execution_price = start_price + entry_spread + entry_slippage
            else:
                # Selling: receive the bid price (lower)
                execution_price = start_price - entry_slippage
            
            result["execution_price"] = execution_price
            result["slippage"] = entry_slippage
            result["spread_cost"] = entry_spread if direction == "up" else 0
            
            # Calculate commission
            commission = self._calculate_commission(position_size, execution_price)
            result["commission"] = commission
            
            # Calculate total trade cost
            spread_cost_in_money = entry_spread * position_size if direction == "up" else 0
            result["total_cost"] = spread_cost_in_money + commission
            
            # Calculate risk amount based on account balance
            risk_amount = account_balance * (risk_percent / 100)
            result["risk_amount"] = risk_amount
            
            # Determine stop loss level (assume fixed 1% risk initially)
            # We'll refine this based on wave structure in a later enhancement
            if direction == "up":
                stop_loss = execution_price * 0.99
            else:
                stop_loss = execution_price * 1.01
                
            # Check if the target was reached in the future data
            target_reached = False
            bars_to_target = None
            stop_hit = False
            
            # Track max favorable and adverse moves
            max_favorable_move = 0.0
            max_adverse_move = 0.0
            exit_price = start_price  # Default if no conditions met
            
            # Simulate market conditions bar by bar
            for i, row in enumerate(future_data.iterrows()):
                _, prices = row
                
                # Calculate volatility-adjusted spread for this bar
                current_spread = self._calculate_spread(prices, start_price)
                
                # Apply spread to current prices
                bid_price = prices["close"] - (current_spread / 2)
                ask_price = prices["close"] + (current_spread / 2)
                
                # Check if stop loss was hit
                if direction == "up" and prices["low"] <= stop_loss:
                    stop_hit = True
                    # Apply slippage on stop loss
                    exit_slippage = self._calculate_slippage(stop_loss, "down")
                    exit_price = stop_loss - exit_slippage
                    bars_to_target = i + 1
                    break
                elif direction == "down" and prices["high"] >= stop_loss:
                    stop_hit = True
                    # Apply slippage on stop loss
                    exit_slippage = self._calculate_slippage(stop_loss, "up")
                    exit_price = stop_loss + exit_slippage
                    bars_to_target = i + 1
                    break
                
                # Check if target is reached based on direction
                if direction == "up":
                    # For long positions, check if high reached target
                    if prices["high"] >= target_price:
                        target_reached = True
                        # Apply slippage on target exit
                        exit_slippage = self._calculate_slippage(target_price, "down")
                        exit_price = target_price - exit_slippage
                        bars_to_target = i + 1
                        break
                        
                    # Calculate max moves
                    favorable_move = prices["high"] - execution_price
                    adverse_move = execution_price - prices["low"]
                    
                else:  # direction == "down"
                    # For short positions, check if low reached target
                    if prices["low"] <= target_price:
                        target_reached = True
                        # Apply slippage on target exit
                        exit_slippage = self._calculate_slippage(target_price, "up")
                        exit_price = target_price + exit_slippage
                        bars_to_target = i + 1
                        break
                        
                    # Calculate max moves
                    favorable_move = execution_price - prices["low"]
                    adverse_move = prices["high"] - execution_price
                
                # Update max moves
                max_favorable_move = max(max_favorable_move, favorable_move)
                max_adverse_move = max(max_adverse_move, adverse_move)
            
            # If no exit occurred (target not reached and stop not hit),
            # use the last price as exit with slippage
            if not target_reached and not stop_hit and not future_data.empty:
                last_price = future_data.iloc[-1]["close"]
                exit_slippage = self._calculate_slippage(last_price, "down" if direction == "up" else "up")
                
                if direction == "up":
                    exit_price = last_price - exit_slippage
                else:
                    exit_price = last_price + exit_slippage
            
            result["exit_price"] = exit_price
            
            # Calculate P&L
            if direction == "up":
                pnl = (exit_price - execution_price) * position_size
            else:
                pnl = (execution_price - exit_price) * position_size
                
            # Subtract costs
            net_pnl = pnl - result["total_cost"]
            result["trade_pnl"] = net_pnl
            
            # Calculate realized return percentage
            if account_balance > 0:
                result["realized_return"] = (net_pnl / account_balance) * 100
            
            # Update result
            result["correct"] = target_reached
            result["time_to_target"] = bars_to_target
            
            # If target wasn't reached, record the closest price
            if not target_reached:
                if direction == "up":
                    result["actual_price"] = future_data["high"].max()
                else:
                    result["actual_price"] = future_data["low"].min()
            else:
                result["actual_price"] = target_price
                
            # Add max moves
            result["max_favorable_move"] = max_favorable_move
            result["max_adverse_move"] = max_adverse_move
            
            # Calculate risk-reward ratio
            if max_adverse_move > 0:
                result["risk_reward_ratio"] = max_favorable_move / max_adverse_move
            else:
                result["risk_reward_ratio"] = float('inf')
        
        return result
    
    def _calculate_slippage(self, price: float, direction: str) -> float:
        """Calculate realistic slippage based on the selected model.
        
        Args:
            price: Current price
            direction: Trade direction ("up" or "down")
            
        Returns:
            Slippage amount in price units
        """
        if self.slippage_model == "none":
            return 0.0
            
        if self.slippage_model == "fixed":
            # Convert pips to price units (assuming 4 decimal places for forex)
            return self.slippage_params["fixed"] * 0.0001
            
        if self.slippage_model == "normal":
            # Random slippage from normal distribution
            params = self.slippage_params["normal"]
            slippage_pips = abs(np.random.normal(params["mean"], params["std"]))
            return slippage_pips * 0.0001
            
        if self.slippage_model == "pareto":
            # Heavy-tailed distribution for more realistic slippage modeling
            params = self.slippage_params["pareto"]
            slippage_pips = np.random.pareto(params["alpha"]) * params["scale"]
            return slippage_pips * 0.0001
            
        # Default case
        return 0.0
        
    def _calculate_spread(self, price_data: pd.Series, reference_price: float) -> float:
        """Calculate bid-ask spread based on the selected model.
        
        Args:
            price_data: Price data for the current bar
            reference_price: Reference price for calculations
            
        Returns:
            Spread amount in price units
        """
        if self.spread_model == "fixed":
            # Convert pips to price units (assuming 4 decimal places for forex)
            return self.spread_params["fixed"] * 0.0001
            
        if self.spread_model == "variable":
            # Spread varies with volatility
            params = self.spread_params["variable"]
            
            # Calculate volatility as high-low range relative to reference
            if "high" in price_data and "low" in price_data:
                volatility = (price_data["high"] - price_data["low"]) / reference_price
                volatility_factor = params["volatility_factor"] * volatility * 10000  # Scale to meaningful range
                
                # Calculate spread between min and max based on volatility
                spread_pips = params["min"] + volatility_factor
                spread_pips = min(spread_pips, params["max"])  # Cap at maximum
                
                return spread_pips * 0.0001
            
            # Fallback if high/low not available
            return params["min"] * 0.0001
            
        if self.spread_model == "volatile":
            # Occasionally has spread spikes
            params = self.spread_params["volatile"]
            
            # Determine if this is a spread spike event
            is_spike = np.random.random() < params["spike_probability"]
            
            if is_spike:
                spread_pips = params["base"] * params["spike_multiplier"]
            else:
                spread_pips = params["base"]
                
            return spread_pips * 0.0001
            
        # Default case
        return 0.0001  # 1 pip default
        
    def _calculate_commission(self, position_size: float, price: float) -> float:
        """Calculate trading commission based on the selected model.
        
        Args:
            position_size: Size of the position in currency units
            price: Execution price
            
        Returns:
            Commission amount in account currency
        """
        if self.commission_model == "none":
            return 0.0
            
        if self.commission_model == "fixed":
            return self.commission_params["fixed"]
            
        if self.commission_model == "percentage":
            trade_value = position_size * price
            return trade_value * self.commission_params["percentage"]
            
        # Default case
        return 0.0
    
    def run_monte_carlo_simulation(
        self,
        backtest_result: Dict[str, Any],
        num_simulations: int = 1000,
        confidence_level: float = 0.95,
        initial_capital: float = 10000.0,
    ) -> Dict[str, Any]:
        """Run Monte Carlo simulations to estimate strategy robustness.
        
        Simulates many possible equity curves by randomly reordering trades,
        which helps determine the statistical significance of backtest results.
        
        Args:
            backtest_result: Results from a previous backtest
            num_simulations: Number of Monte Carlo simulations to run
            confidence_level: Confidence level for statistical analysis
            initial_capital: Initial capital for simulations
            
        Returns:
            Dictionary with Monte Carlo simulation results
        """
        # Extract trade results from backtest
        if "windows" not in backtest_result or not backtest_result["windows"]:
            return {"error": "No trade data available for Monte Carlo simulation"}
            
        # Collect all trades with their P&L values
        trades = []
        for window in backtest_result["windows"]:
            if "prediction_details" in window:
                for pred in window["prediction_details"]:
                    if "trade_pnl" in pred:
                        trades.append(pred["trade_pnl"])
                    elif "realized_return" in pred:
                        # Convert percentage return to dollar value
                        trades.append(initial_capital * (pred["realized_return"] / 100))
            
        if not trades:
            return {"error": "No trade P&L data available for Monte Carlo simulation"}
            
        # Run Monte Carlo simulations
        simulation_results = []
        final_capitals = []
        drawdowns = []
        
        for sim in range(num_simulations):
            # Shuffle trades randomly
            np.random.shuffle(trades)
            
            # Generate equity curve
            equity = [initial_capital]
            current_equity = initial_capital
            peak_equity = initial_capital
            max_drawdown = 0
            
            for trade_pnl in trades:
                current_equity += trade_pnl
                equity.append(current_equity)
                
                # Track peak equity and drawdown
                if current_equity > peak_equity:
                    peak_equity = current_equity
                else:
                    drawdown = (peak_equity - current_equity) / peak_equity
                    max_drawdown = max(max_drawdown, drawdown)
            
            # Store results for this simulation
            simulation_results.append({
                "equity_curve": equity,
                "final_capital": current_equity,
                "max_drawdown": max_drawdown,
                "total_return": (current_equity / initial_capital) - 1,
            })
            
            final_capitals.append(current_equity)
            drawdowns.append(max_drawdown)
            
        # Analyze Monte Carlo results
        final_capitals = np.array(final_capitals)
        drawdowns = np.array(drawdowns)
        
        # Calculate confidence intervals
        confidence_idx = int(num_simulations * (1 - confidence_level))
        sorted_capitals = np.sort(final_capitals)
        sorted_drawdowns = np.sort(drawdowns)
        
        worst_capital = sorted_capitals[confidence_idx]
        worst_drawdown = sorted_drawdowns[-confidence_idx - 1]
        
        # Calculate risk metrics
        expected_return = np.mean(final_capitals / initial_capital) - 1
        return_std = np.std(final_capitals / initial_capital)
        sharpe_ratio = expected_return / return_std if return_std > 0 else 0
        
        # Prepare final results
        mc_results = {
            "num_simulations": num_simulations,
            "confidence_level": confidence_level,
            "initial_capital": initial_capital,
            "expected_final_capital": np.mean(final_capitals),
            "median_final_capital": np.median(final_capitals),
            "worst_case_capital": worst_capital,
            "best_case_capital": sorted_capitals[-1],
            "expected_return": expected_return * 100,  # Convert to percentage
            "expected_drawdown": np.mean(drawdowns) * 100,  # Convert to percentage
            "worst_drawdown": worst_drawdown * 100,  # Convert to percentage
            "probability_of_profit": np.mean(final_capitals > initial_capital) * 100,
            "sharpe_ratio": sharpe_ratio,
            "profit_factor": -np.sum(final_capitals[final_capitals > initial_capital] - initial_capital) / 
                             np.sum(final_capitals[final_capitals < initial_capital] - initial_capital)
                             if np.sum(final_capitals[final_capitals < initial_capital] - initial_capital) != 0 else float('inf'),
            "summary": ""
        }
        
        # Generate summary text
        mc_results["summary"] = (
            f"Monte Carlo analysis ({confidence_level*100:.0f}% confidence):\n"
            f"Expected return: {mc_results['expected_return']:.2f}%\n"
            f"Worst-case capital: ${mc_results['worst_case_capital']:.2f}\n"
            f"Worst-case drawdown: {mc_results['worst_drawdown']:.2f}%\n"
            f"Probability of profit: {mc_results['probability_of_profit']:.2f}%\n"
            f"Sharpe ratio: {mc_results['sharpe_ratio']:.2f}"
        )
        
        return mc_results
        
    def backtest_multiple_timeframes(
        self,
        symbol: str,
        start_date: Union[str, datetime],
        end_date: Optional[Union[str, datetime]] = None,
        timeframes: List[str] = ["1D", "4H", "1H"],
        window_size_multipliers: Dict[str, float] = None,
        prediction_horizon_multipliers: Dict[str, float] = None,
        use_realistic_simulation: bool = True,
    ) -> Dict[str, Dict[str, Any]]:
        """Run backtests on multiple timeframes with realistic market simulation.
        
        Args:
            symbol: Symbol to backtest
            start_date: Start date for historical data
            end_date: End date for historical data
            timeframes: List of timeframes to test
            window_size_multipliers: Dictionary mapping timeframe to window size multiplier
            prediction_horizon_multipliers: Dictionary mapping timeframe to prediction horizon multiplier
            use_realistic_simulation: Whether to apply realistic market simulation
            
        Returns:
            Dictionary mapping timeframe to backtest results
        """
        # Default multipliers based on timeframe
        if window_size_multipliers is None:
            window_size_multipliers = {
                "1m": 200,
                "5m": 100,
                "15m": 80,
                "30m": 60,
                "1H": 50,
                "4H": 30,
                "1D": 20,
                "1W": 15,
            }
            
        if prediction_horizon_multipliers is None:
            prediction_horizon_multipliers = {
                "1m": 50,
                "5m": 40,
                "15m": 30,
                "30m": 25,
                "1H": 20,
                "4H": 15,
                "1D": 10,
                "1W": 5,
            }
        
        results = {}
        
        # Run backtest for each timeframe
        for tf in timeframes:
            # Load data for this timeframe
            training_data, testing_data = self.prepare_data(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                timeframe=tf,
            )
            
            # Determine window size and prediction horizon based on timeframe
            window_size = int(window_size_multipliers.get(tf, 50))
            prediction_horizon = int(prediction_horizon_multipliers.get(tf, 20))
            
            # Run backtest
            tf_results = self.run_rolling_window_backtest(
                data=testing_data,
                window_size=window_size,
                step_size=max(1, window_size // 5),  # 20% of window size
                prediction_horizon=prediction_horizon,
            )
            
            results[tf] = tf_results
        
        return results
    
    def analyze_results(self) -> Dict[str, Any]:
        """Analyze backtest results to extract insights.
        
        Returns:
            Dictionary with analysis results
        """
        if not self.results:
            return {"error": "No backtest results available"}
        
        analysis = {
            "accuracy": self.results.get("prediction_accuracy", 0),
            "total_predictions": self.results.get("predictions_made", 0),
            "correct_predictions": self.results.get("correct_predictions", 0),
            "pattern_detection_rate": 0.0,
            "avg_time_to_target": 0.0,
            "success_by_pattern_type": {},
            "risk_reward_ratio": 0.0,
        }
        
        # Calculate pattern detection rate
        total_windows = self.results.get("total_windows", 0)
        patterns_detected = (
            self.results.get("impulse_patterns_detected", 0) + 
            self.results.get("corrective_patterns_detected", 0)
        )
        
        if total_windows > 0:
            analysis["pattern_detection_rate"] = patterns_detected / total_windows
        
        # Analyze predictions by pattern type
        if self.predictions and self.actual_outcomes:
            # Group by pattern type
            impulse_correct = 0
            impulse_total = 0
            corrective_correct = 0
            corrective_total = 0
            
            # Calculate average time to target
            total_time = 0
            time_count = 0
            
            # Calculate risk-reward ratio
            total_rr = 0.0
            rr_count = 0
            
            for pred, actual in zip(self.predictions, self.actual_outcomes):
                if pred["pattern_type"] == "impulse":
                    impulse_total += 1
                    if actual["correct"]:
                        impulse_correct += 1
                else:  # corrective
                    corrective_total += 1
                    if actual["correct"]:
                        corrective_correct += 1
                
                # Track time to target for successful predictions
                if actual["correct"] and actual["time_to_target"] is not None:
                    total_time += actual["time_to_target"]
                    time_count += 1
                
                # Track risk-reward ratio
                if "risk_reward_ratio" in actual and actual["risk_reward_ratio"] != float('inf'):
                    total_rr += actual["risk_reward_ratio"]
                    rr_count += 1
            
            # Calculate success rates by pattern type
            if impulse_total > 0:
                analysis["success_by_pattern_type"]["impulse"] = impulse_correct / impulse_total
            
            if corrective_total > 0:
                analysis["success_by_pattern_type"]["corrective"] = corrective_correct / corrective_total
            
            # Calculate average time to target
            if time_count > 0:
                analysis["avg_time_to_target"] = total_time / time_count
            
            # Calculate average risk-reward ratio
            if rr_count > 0:
                analysis["risk_reward_ratio"] = total_rr / rr_count
        
        return analysis