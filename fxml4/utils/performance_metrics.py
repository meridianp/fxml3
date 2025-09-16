"""Performance metrics calculation utilities."""

from typing import Union

import numpy as np
import pandas as pd


def calculate_sharpe_ratio(
    returns: Union[pd.Series, np.ndarray],
    risk_free_rate: float = 0.0,
    periods_per_year: int = 252,
) -> float:
    """Calculate Sharpe ratio.

    Args:
        returns: Series of returns
        risk_free_rate: Annual risk-free rate
        periods_per_year: Number of periods in a year (252 for daily, 52 for weekly)

    Returns:
        Sharpe ratio
    """
    if len(returns) < 2:
        return 0.0

    excess_returns = returns - risk_free_rate / periods_per_year

    if excess_returns.std() == 0:
        return 0.0

    return np.sqrt(periods_per_year) * excess_returns.mean() / excess_returns.std()


def calculate_sortino_ratio(
    returns: Union[pd.Series, np.ndarray],
    risk_free_rate: float = 0.0,
    periods_per_year: int = 252,
) -> float:
    """Calculate Sortino ratio (uses downside deviation).

    Args:
        returns: Series of returns
        risk_free_rate: Annual risk-free rate
        periods_per_year: Number of periods in a year

    Returns:
        Sortino ratio
    """
    if len(returns) < 2:
        return 0.0

    excess_returns = returns - risk_free_rate / periods_per_year
    downside_returns = excess_returns[excess_returns < 0]

    if len(downside_returns) == 0 or downside_returns.std() == 0:
        return 0.0

    return np.sqrt(periods_per_year) * excess_returns.mean() / downside_returns.std()


def calculate_max_drawdown(equity_curve: Union[pd.Series, np.ndarray]) -> float:
    """Calculate maximum drawdown.

    Args:
        equity_curve: Series of portfolio values

    Returns:
        Maximum drawdown as a percentage (negative value)
    """
    if len(equity_curve) < 2:
        return 0.0

    # Convert to pandas Series if needed
    if isinstance(equity_curve, np.ndarray):
        equity_curve = pd.Series(equity_curve)

    # Calculate running maximum
    running_max = equity_curve.expanding().max()

    # Calculate drawdown
    drawdown = (equity_curve - running_max) / running_max

    return drawdown.min()


def calculate_calmar_ratio(
    returns: Union[pd.Series, np.ndarray],
    equity_curve: Union[pd.Series, np.ndarray],
    periods_per_year: int = 252,
) -> float:
    """Calculate Calmar ratio (annual return / max drawdown).

    Args:
        returns: Series of returns
        equity_curve: Series of portfolio values
        periods_per_year: Number of periods in a year

    Returns:
        Calmar ratio
    """
    if len(returns) < 2:
        return 0.0

    annual_return = returns.mean() * periods_per_year
    max_dd = abs(calculate_max_drawdown(equity_curve))

    if max_dd == 0:
        return 0.0

    return annual_return / max_dd


def calculate_win_rate(trades: list) -> float:
    """Calculate win rate from trades.

    Args:
        trades: List of trade dictionaries with 'pnl' field

    Returns:
        Win rate as a percentage
    """
    if not trades:
        return 0.0

    wins = sum(1 for trade in trades if trade.get("pnl", 0) > 0)
    return wins / len(trades)


def calculate_profit_factor(trades: list) -> float:
    """Calculate profit factor (gross profits / gross losses).

    Args:
        trades: List of trade dictionaries with 'pnl' field

    Returns:
        Profit factor
    """
    if not trades:
        return 0.0

    gross_profits = sum(trade["pnl"] for trade in trades if trade.get("pnl", 0) > 0)
    gross_losses = abs(sum(trade["pnl"] for trade in trades if trade.get("pnl", 0) < 0))

    if gross_losses == 0:
        return float("inf") if gross_profits > 0 else 0.0

    return gross_profits / gross_losses


def calculate_expectancy(trades: list) -> float:
    """Calculate trade expectancy (average profit per trade).

    Args:
        trades: List of trade dictionaries with 'pnl' field

    Returns:
        Expectancy value
    """
    if not trades:
        return 0.0

    return sum(trade.get("pnl", 0) for trade in trades) / len(trades)


def calculate_risk_reward_ratio(trades: list) -> float:
    """Calculate average risk/reward ratio.

    Args:
        trades: List of trade dictionaries

    Returns:
        Average risk/reward ratio
    """
    if not trades:
        return 0.0

    ratios = []
    for trade in trades:
        if "risk_reward" in trade:
            ratios.append(trade["risk_reward"])
        elif "entry_price" in trade and "stop_loss" in trade and "targets" in trade:
            risk = abs(trade["entry_price"] - trade["stop_loss"])
            if risk > 0 and trade["targets"]:
                reward = abs(trade["targets"][0] - trade["entry_price"])
                ratios.append(reward / risk)

    return np.mean(ratios) if ratios else 0.0
