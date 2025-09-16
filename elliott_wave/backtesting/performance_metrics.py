"""Performance metrics for backtesting."""

from typing import Dict, List, Optional, Union

import numpy as np
import pandas as pd


class PerformanceMetrics:
    """Calculate and analyze performance metrics for backtesting results."""

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
        metrics = {
            "overall": {},
            "by_pattern_type": {},
        }

        # Extract overall metrics
        total_windows = backtest_results.get("total_windows", 0)
        predictions_made = backtest_results.get("predictions_made", 0)
        correct_predictions = backtest_results.get("correct_predictions", 0)

        # Calculate accuracy
        if predictions_made > 0:
            accuracy = correct_predictions / predictions_made
        else:
            accuracy = 0.0

        # Calculate pattern detection rate
        patterns_detected = backtest_results.get(
            "impulse_patterns_detected", 0
        ) + backtest_results.get("corrective_patterns_detected", 0)

        if total_windows > 0:
            detection_rate = patterns_detected / total_windows
        else:
            detection_rate = 0.0

        # Store overall metrics
        metrics["overall"] = {
            "total_windows": total_windows,
            "predictions_made": predictions_made,
            "correct_predictions": correct_predictions,
            "incorrect_predictions": predictions_made - correct_predictions,
            "accuracy": accuracy,
            "detection_rate": detection_rate,
        }

        # Calculate pattern-specific metrics if windows data is available
        if include_windows and "windows" in backtest_results:
            # Initialize counters
            impulse_predictions = 0
            impulse_correct = 0
            corrective_predictions = 0
            corrective_correct = 0

            # Analyze each window
            for window in backtest_results["windows"]:
                if "prediction_details" in window:
                    for pred in window["prediction_details"]:
                        if pred["pattern_type"] == "impulse":
                            impulse_predictions += 1
                            if pred["correct"]:
                                impulse_correct += 1
                        elif pred["pattern_type"] == "corrective":
                            corrective_predictions += 1
                            if pred["correct"]:
                                corrective_correct += 1

            # Calculate pattern-specific accuracy
            if impulse_predictions > 0:
                impulse_accuracy = impulse_correct / impulse_predictions
            else:
                impulse_accuracy = 0.0

            if corrective_predictions > 0:
                corrective_accuracy = corrective_correct / corrective_predictions
            else:
                corrective_accuracy = 0.0

            # Store pattern-specific metrics
            metrics["by_pattern_type"] = {
                "impulse": {
                    "predictions": impulse_predictions,
                    "correct": impulse_correct,
                    "accuracy": impulse_accuracy,
                },
                "corrective": {
                    "predictions": corrective_predictions,
                    "correct": corrective_correct,
                    "accuracy": corrective_accuracy,
                },
            }

        return metrics

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
        if not actual_outcomes:
            return {}

        # Initialize metrics
        metrics = {
            "avg_risk_reward_ratio": 0.0,
            "median_risk_reward_ratio": 0.0,
            "avg_favorable_move": 0.0,
            "avg_adverse_move": 0.0,
            "max_favorable_move": 0.0,
            "max_adverse_move": 0.0,
            "avg_time_to_target": 0.0,
            "win_rate": 0.0,
        }

        # Extract values
        rr_ratios = []
        favorable_moves = []
        adverse_moves = []
        times_to_target = []
        win_count = 0

        for outcome in actual_outcomes:
            # Risk/reward ratio
            if "risk_reward_ratio" in outcome and outcome["risk_reward_ratio"] != float(
                "inf"
            ):
                rr_ratios.append(outcome["risk_reward_ratio"])

            # Favorable and adverse moves
            if "max_favorable_move" in outcome:
                favorable_moves.append(outcome["max_favorable_move"])

            if "max_adverse_move" in outcome:
                adverse_moves.append(outcome["max_adverse_move"])

            # Time to target
            if (
                outcome.get("correct", False)
                and outcome.get("time_to_target") is not None
            ):
                times_to_target.append(outcome["time_to_target"])

            # Win count
            if outcome.get("correct", False):
                win_count += 1

        # Calculate metrics
        if rr_ratios:
            metrics["avg_risk_reward_ratio"] = np.mean(rr_ratios)
            metrics["median_risk_reward_ratio"] = np.median(rr_ratios)

        if favorable_moves:
            metrics["avg_favorable_move"] = np.mean(favorable_moves)
            metrics["max_favorable_move"] = max(favorable_moves)

        if adverse_moves:
            metrics["avg_adverse_move"] = np.mean(adverse_moves)
            metrics["max_adverse_move"] = max(adverse_moves)

        if times_to_target:
            metrics["avg_time_to_target"] = np.mean(times_to_target)

        if actual_outcomes:
            metrics["win_rate"] = win_count / len(actual_outcomes)

        return metrics

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
        if not multi_tf_results:
            return {}

        # Initialize metrics
        metrics = {
            "by_timeframe": {},
            "overall": {
                "total_predictions": 0,
                "correct_predictions": 0,
                "accuracy": 0.0,
                "best_timeframe": None,
                "best_accuracy": 0.0,
            },
        }

        # Calculate metrics for each timeframe
        for tf, results in multi_tf_results.items():
            tf_metrics = PerformanceMetrics.calculate_metrics(results)
            metrics["by_timeframe"][tf] = tf_metrics

            # Update overall totals
            metrics["overall"]["total_predictions"] += tf_metrics["overall"][
                "predictions_made"
            ]
            metrics["overall"]["correct_predictions"] += tf_metrics["overall"][
                "correct_predictions"
            ]

            # Track best timeframe
            if tf_metrics["overall"]["accuracy"] > metrics["overall"]["best_accuracy"]:
                metrics["overall"]["best_accuracy"] = tf_metrics["overall"]["accuracy"]
                metrics["overall"]["best_timeframe"] = tf

        # Calculate overall accuracy
        if metrics["overall"]["total_predictions"] > 0:
            metrics["overall"]["accuracy"] = (
                metrics["overall"]["correct_predictions"]
                / metrics["overall"]["total_predictions"]
            )

        return metrics

    @staticmethod
    def calculate_profitability(
        actual_outcomes: List[Dict],
        risk_per_trade: float = 0.02,  # 2% risk per trade
        account_size: float = 10000.0,  # $10,000 starting capital
        stop_multiplier: float = 1.5,  # Stop loss at 1.5x the max adverse move
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
        if not actual_outcomes:
            return {}

        # Initialize metrics
        metrics = {
            "initial_capital": account_size,
            "final_capital": account_size,
            "total_return_pct": 0.0,
            "win_count": 0,
            "loss_count": 0,
            "avg_win_pct": 0.0,
            "avg_loss_pct": 0.0,
            "profit_factor": 0.0,
            "max_drawdown_pct": 0.0,
            "cost_metrics": {
                "total_slippage": 0.0,
                "total_spread_cost": 0.0,
                "total_commission": 0.0,
                "total_cost": 0.0,
                "cost_as_pct_of_profit": 0.0,
            },
        }

        # Track equity curve and trade results
        equity_curve = [account_size]
        win_pcts = []
        loss_pcts = []
        total_profit = 0.0
        total_loss = 0.0

        # Track trading costs
        total_slippage = 0.0
        total_spread_cost = 0.0
        total_commission = 0.0

        # Simulate trades
        current_equity = account_size
        peak_equity = account_size
        max_drawdown = 0.0

        for outcome in actual_outcomes:
            # Check if using realistic simulation data
            if use_realistic_costs and "trade_pnl" in outcome:
                # Use the pre-calculated P&L from realistic simulation
                trade_result = outcome["trade_pnl"]

                # Track costs
                if "slippage" in outcome:
                    position_size = outcome.get("position_size", 10000.0)
                    total_slippage += outcome["slippage"] * position_size

                if "spread_cost" in outcome:
                    total_spread_cost += outcome["spread_cost"]

                if "commission" in outcome:
                    total_commission += outcome["commission"]

                # Update equity
                current_equity += trade_result

                # Update win/loss counts
                if trade_result > 0:
                    metrics["win_count"] += 1
                    win_pcts.append((trade_result / current_equity) * 100)
                    total_profit += trade_result
                else:
                    metrics["loss_count"] += 1
                    loss_pcts.append((abs(trade_result) / current_equity) * 100)
                    total_loss += abs(trade_result)

            else:
                # Use the traditional approach without realistic costs
                # Set risk amount for this trade
                risk_amount = current_equity * risk_per_trade

                # Determine stop loss and take profit levels
                if outcome.get("max_adverse_move", 0) > 0:
                    stop_loss = outcome["max_adverse_move"] * stop_multiplier
                else:
                    # Default to 1% of price if no adverse move info
                    stop_loss = outcome.get("end_price", 100) * 0.01

                # Calculate position size based on risk and stop loss
                price = outcome.get("end_price", 100)  # Default to 100 if not available
                position_size = risk_amount / stop_loss

                # Calculate trade result
                if outcome.get("correct", False):
                    # Winning trade - calculate profit
                    target_move = abs(outcome.get("target_price", price) - price)
                    trade_profit = position_size * target_move
                    current_equity += trade_profit

                    metrics["win_count"] += 1
                    win_pcts.append(trade_profit / current_equity * 100)
                    total_profit += trade_profit
                else:
                    # Losing trade - calculate loss
                    trade_loss = risk_amount  # Assume stop loss was hit
                    current_equity -= trade_loss

                    metrics["loss_count"] += 1
                    loss_pcts.append(trade_loss / current_equity * 100)
                    total_loss += trade_loss

            # Track equity curve
            equity_curve.append(current_equity)

            # Update peak equity and drawdown
            if current_equity > peak_equity:
                peak_equity = current_equity
            else:
                drawdown = (peak_equity - current_equity) / peak_equity
                max_drawdown = max(max_drawdown, drawdown)

        # Calculate final metrics
        metrics["final_capital"] = current_equity
        metrics["total_return_pct"] = (current_equity / account_size - 1) * 100

        if win_pcts:
            metrics["avg_win_pct"] = np.mean(win_pcts)

        if loss_pcts:
            metrics["avg_loss_pct"] = np.mean(loss_pcts)

        if total_loss > 0:
            metrics["profit_factor"] = total_profit / total_loss

        metrics["max_drawdown_pct"] = max_drawdown * 100

        # Add equity curve
        metrics["equity_curve"] = equity_curve

        # Add cost metrics
        total_cost = total_slippage + total_spread_cost + total_commission
        metrics["cost_metrics"]["total_slippage"] = total_slippage
        metrics["cost_metrics"]["total_spread_cost"] = total_spread_cost
        metrics["cost_metrics"]["total_commission"] = total_commission
        metrics["cost_metrics"]["total_cost"] = total_cost

        # Calculate cost as percentage of profit
        if total_profit > 0:
            metrics["cost_metrics"]["cost_as_pct_of_profit"] = (
                total_cost / total_profit
            ) * 100

        # Add advanced metrics
        metrics["expectancy"] = 0.0
        if (metrics["win_count"] + metrics["loss_count"]) > 0:
            win_rate = metrics["win_count"] / (
                metrics["win_count"] + metrics["loss_count"]
            )
            loss_rate = 1 - win_rate
            if metrics["avg_loss_pct"] > 0:
                avg_win_loss_ratio = metrics["avg_win_pct"] / metrics["avg_loss_pct"]
                metrics["expectancy"] = (win_rate * avg_win_loss_ratio) - loss_rate

        metrics["kelly_percentage"] = 0.0
        if metrics["avg_loss_pct"] > 0:
            win_rate = (
                metrics["win_count"] / (metrics["win_count"] + metrics["loss_count"])
                if (metrics["win_count"] + metrics["loss_count"]) > 0
                else 0
            )
            avg_win_loss_ratio = metrics["avg_win_pct"] / metrics["avg_loss_pct"]
            metrics["kelly_percentage"] = win_rate - (
                (1 - win_rate) / avg_win_loss_ratio
            )
            metrics["kelly_percentage"] = (
                max(0, metrics["kelly_percentage"]) * 100
            )  # Keep positive only, convert to percentage

        return metrics

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
        if not actual_outcomes:
            return {}

        # Initialize metrics
        metrics = {
            "avg_slippage_pips": 0.0,
            "avg_spread_pips": 0.0,
            "total_transaction_cost_pct": 0.0,
            "slippage_as_pct_of_atr": 0.0,
            "worst_slippage": 0.0,
            "worst_spread": 0.0,
            "avg_execution_quality": 0.0,
        }

        # Collect slippage and spread data
        slippage_values = []
        spread_values = []
        slippage_to_atr = []
        total_costs = []

        for i, outcome in enumerate(actual_outcomes):
            # Extract slippage and spread if available
            if "slippage" in outcome:
                # Convert to pips (assuming 4 decimal places)
                slippage_pips = outcome["slippage"] * 10000
                slippage_values.append(slippage_pips)

                # Calculate slippage as percentage of ATR if available
                if atr_values and i < len(atr_values) and atr_values[i] > 0:
                    slippage_to_atr.append(outcome["slippage"] / atr_values[i])

            if "spread_cost" in outcome:
                # Try to convert to pips
                if "execution_price" in outcome and outcome["execution_price"] > 0:
                    spread_pips = (
                        outcome["spread_cost"] / outcome["execution_price"]
                    ) * 10000
                else:
                    # Assume it's already in price units like slippage
                    spread_pips = outcome.get("spread_cost", 0) * 10000

                spread_values.append(spread_pips)

            # Calculate total transaction cost as percentage of trade value
            if (
                "total_cost" in outcome
                and "execution_price" in outcome
                and outcome["execution_price"] > 0
            ):
                position_size = outcome.get("position_size", 10000.0)
                trade_value = position_size * outcome["execution_price"]
                if trade_value > 0:
                    cost_pct = (outcome["total_cost"] / trade_value) * 100
                    total_costs.append(cost_pct)

        # Calculate metrics
        if slippage_values:
            metrics["avg_slippage_pips"] = np.mean(slippage_values)
            metrics["worst_slippage"] = np.max(slippage_values)

        if spread_values:
            metrics["avg_spread_pips"] = np.mean(spread_values)
            metrics["worst_spread"] = np.max(spread_values)

        if total_costs:
            metrics["total_transaction_cost_pct"] = np.mean(total_costs)

        if slippage_to_atr:
            metrics["slippage_as_pct_of_atr"] = np.mean(slippage_to_atr) * 100

        # Calculate execution quality (0-100 scale)
        # Lower slippage and spread means better execution
        if slippage_values and spread_values:
            # Normalize worst values to keep within reasonable range
            norm_slippage = np.array(slippage_values) / max(
                5.0, np.max(slippage_values)
            )
            norm_spread = np.array(spread_values) / max(5.0, np.max(spread_values))

            # Calculate execution quality (100 = perfect, 0 = worst)
            execution_quality = 100 - (((norm_slippage + norm_spread) / 2) * 100)
            metrics["avg_execution_quality"] = np.mean(execution_quality)

        return metrics
