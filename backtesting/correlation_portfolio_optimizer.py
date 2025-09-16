"""Portfolio optimization using correlation analysis for forex trading."""

import warnings
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy.optimize import minimize

warnings.filterwarnings("ignore")


@dataclass
class PortfolioWeights:
    """Container for optimized portfolio weights."""

    symbols: List[str]
    weights: np.ndarray
    expected_return: float
    expected_risk: float
    sharpe_ratio: float
    correlation_penalty: float


class CorrelationPortfolioOptimizer:
    """Portfolio optimizer that considers cross-asset correlations."""

    def __init__(
        self,
        correlation_matrix: pd.DataFrame,
        expected_returns: pd.Series,
        risk_free_rate: float = 0.02,
    ):
        """
        Initialize portfolio optimizer.

        Args:
            correlation_matrix: Correlation matrix of assets
            expected_returns: Expected returns for each asset
            risk_free_rate: Risk-free rate for Sharpe calculation
        """
        self.correlation_matrix = correlation_matrix
        self.expected_returns = expected_returns
        self.risk_free_rate = risk_free_rate

        # Ensure alignment
        self.symbols = list(set(correlation_matrix.index) & set(expected_returns.index))
        self.corr_matrix = correlation_matrix.loc[self.symbols, self.symbols].values
        self.returns = expected_returns[self.symbols].values

        # Calculate covariance from correlation
        # Assuming unit variance for simplification (can be adjusted)
        self.cov_matrix = self.corr_matrix

    def portfolio_stats(self, weights: np.ndarray) -> Tuple[float, float, float]:
        """Calculate portfolio statistics."""
        # Expected return
        portfolio_return = np.sum(weights * self.returns)

        # Portfolio variance
        portfolio_variance = np.dot(weights.T, np.dot(self.cov_matrix, weights))
        portfolio_risk = np.sqrt(portfolio_variance)

        # Sharpe ratio
        sharpe = (
            (portfolio_return - self.risk_free_rate) / portfolio_risk
            if portfolio_risk > 0
            else 0
        )

        return portfolio_return, portfolio_risk, sharpe

    def correlation_penalty(
        self, weights: np.ndarray, penalty_factor: float = 0.1
    ) -> float:
        """
        Calculate penalty for highly correlated positions.

        High positive weights on highly correlated assets are penalized.
        """
        penalty = 0
        n = len(weights)

        for i in range(n):
            for j in range(i + 1, n):
                # Penalize same-direction positions on highly correlated assets
                if self.corr_matrix[i, j] > 0.7:  # High correlation threshold
                    same_direction_exposure = weights[i] * weights[j]
                    if same_direction_exposure > 0:  # Same direction
                        penalty += (
                            penalty_factor
                            * same_direction_exposure
                            * self.corr_matrix[i, j]
                        )

        return penalty

    def objective_function(
        self,
        weights: np.ndarray,
        optimize_for: str = "sharpe",
        correlation_penalty_weight: float = 0.1,
    ) -> float:
        """Objective function for optimization."""
        ret, risk, sharpe = self.portfolio_stats(weights)
        corr_penalty = self.correlation_penalty(weights)

        if optimize_for == "sharpe":
            # Maximize Sharpe ratio (minimize negative Sharpe)
            return -sharpe + correlation_penalty_weight * corr_penalty
        elif optimize_for == "return":
            # Maximize return with risk penalty
            return -ret + 0.5 * risk + correlation_penalty_weight * corr_penalty
        elif optimize_for == "min_risk":
            # Minimize risk
            return risk + correlation_penalty_weight * corr_penalty
        else:
            raise ValueError(f"Unknown optimization target: {optimize_for}")

    def optimize_portfolio(
        self,
        constraints: Optional[Dict] = None,
        max_position: float = 0.3,
        allow_short: bool = True,
        optimize_for: str = "sharpe",
        correlation_penalty_weight: float = 0.1,
    ) -> PortfolioWeights:
        """
        Optimize portfolio weights considering correlations.

        Args:
            constraints: Additional constraints
            max_position: Maximum position size per asset
            allow_short: Whether to allow short positions
            optimize_for: 'sharpe', 'return', or 'min_risk'
            correlation_penalty_weight: Weight for correlation penalty
        """
        n_assets = len(self.symbols)

        # Initial guess (equal weight)
        x0 = np.ones(n_assets) / n_assets

        # Bounds
        if allow_short:
            bounds = [(-max_position, max_position) for _ in range(n_assets)]
        else:
            bounds = [(0, max_position) for _ in range(n_assets)]

        # Constraints
        cons = [{"type": "eq", "fun": lambda x: np.sum(x) - 1.0}]  # Weights sum to 1

        # Add user constraints
        if constraints:
            cons.extend(constraints)

        # Optimize
        result = minimize(
            fun=lambda w: self.objective_function(
                w, optimize_for, correlation_penalty_weight
            ),
            x0=x0,
            method="SLSQP",
            bounds=bounds,
            constraints=cons,
            options={"maxiter": 1000},
        )

        if not result.success:
            print(f"Optimization warning: {result.message}")

        # Get final stats
        weights = result.x
        ret, risk, sharpe = self.portfolio_stats(weights)
        corr_penalty = self.correlation_penalty(weights)

        return PortfolioWeights(
            symbols=self.symbols,
            weights=weights,
            expected_return=ret,
            expected_risk=risk,
            sharpe_ratio=sharpe,
            correlation_penalty=corr_penalty,
        )

    def efficient_frontier(self, n_portfolios: int = 50) -> pd.DataFrame:
        """Calculate efficient frontier."""
        # Target returns
        min_ret = self.returns.min()
        max_ret = self.returns.max()
        target_returns = np.linspace(min_ret, max_ret, n_portfolios)

        frontier = []

        for target_return in target_returns:
            # Constraint for target return
            cons = [
                {"type": "eq", "fun": lambda x: np.sum(x) - 1.0},
                {
                    "type": "eq",
                    "fun": lambda x, tr=target_return: np.sum(x * self.returns) - tr,
                },
            ]

            # Optimize for minimum risk given return
            result = minimize(
                fun=lambda w: self.portfolio_stats(w)[1],  # Minimize risk
                x0=np.ones(len(self.symbols)) / len(self.symbols),
                method="SLSQP",
                bounds=[(0, 1) for _ in range(len(self.symbols))],
                constraints=cons,
            )

            if result.success:
                weights = result.x
                ret, risk, sharpe = self.portfolio_stats(weights)

                frontier.append(
                    {"return": ret, "risk": risk, "sharpe": sharpe, "weights": weights}
                )

        return pd.DataFrame(frontier)

    def get_risk_parity_weights(self) -> np.ndarray:
        """Calculate risk parity weights (equal risk contribution)."""
        n = len(self.symbols)

        # Initial guess
        x0 = np.ones(n) / n

        def risk_contribution(weights):
            # Portfolio variance
            portfolio_var = np.dot(weights.T, np.dot(self.cov_matrix, weights))

            # Marginal contributions to risk
            marginal_contrib = np.dot(self.cov_matrix, weights)

            # Contribution to risk
            contrib = weights * marginal_contrib / np.sqrt(portfolio_var)

            return contrib

        def objective(weights):
            # Minimize difference in risk contributions
            contrib = risk_contribution(weights)
            target = np.ones(n) / n  # Equal contribution
            return np.sum((contrib - target) ** 2)

        # Constraints
        cons = [
            {"type": "eq", "fun": lambda x: np.sum(x) - 1.0},
            {"type": "ineq", "fun": lambda x: x},  # Non-negative weights
        ]

        # Optimize
        result = minimize(
            fun=objective,
            x0=x0,
            method="SLSQP",
            bounds=[(0, 1) for _ in range(n)],
            constraints=cons,
        )

        return result.x if result.success else x0

    def recommend_portfolio_adjustments(
        self, current_weights: Dict[str, float], market_regime: str = "NEUTRAL"
    ) -> Dict[str, float]:
        """Recommend portfolio adjustments based on correlations and regime."""
        # Get optimal weights for current regime
        if market_regime == "RISK_OFF":
            # Prefer low correlation, defensive assets
            optimize_for = "min_risk"
            correlation_penalty_weight = 0.2  # Higher penalty
        elif market_regime == "RISK_ON":
            # Can take more correlated bets
            optimize_for = "return"
            correlation_penalty_weight = 0.05  # Lower penalty
        else:
            optimize_for = "sharpe"
            correlation_penalty_weight = 0.1

        # Optimize
        optimal = self.optimize_portfolio(
            optimize_for=optimize_for,
            correlation_penalty_weight=correlation_penalty_weight,
        )

        # Calculate adjustments
        adjustments = {}
        current_array = np.zeros(len(self.symbols))

        for i, symbol in enumerate(self.symbols):
            current_array[i] = current_weights.get(symbol, 0)
            adjustments[symbol] = optimal.weights[i] - current_array[i]

        # Add metadata
        adjustments["_metadata"] = {
            "expected_return": optimal.expected_return,
            "expected_risk": optimal.expected_risk,
            "sharpe_ratio": optimal.sharpe_ratio,
            "correlation_penalty": optimal.correlation_penalty,
            "regime": market_regime,
        }

        return adjustments


def example_usage():
    """Example of portfolio optimization with correlations."""

    # Sample correlation matrix (would come from correlation analysis)
    symbols = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF"]

    # Realistic forex correlations
    corr_data = np.array(
        [
            [1.00, 0.85, -0.70, -0.90],  # EURUSD
            [0.85, 1.00, -0.60, -0.75],  # GBPUSD
            [-0.70, -0.60, 1.00, 0.80],  # USDJPY
            [-0.90, -0.75, 0.80, 1.00],  # USDCHF
        ]
    )

    corr_matrix = pd.DataFrame(corr_data, index=symbols, columns=symbols)

    # Expected returns (annualized)
    expected_returns = pd.Series(
        {"EURUSD": 0.02, "GBPUSD": 0.03, "USDJPY": -0.01, "USDCHF": -0.02}
    )

    # Initialize optimizer
    optimizer = CorrelationPortfolioOptimizer(corr_matrix, expected_returns)

    print("Forex Portfolio Optimization with Correlation Constraints")
    print("=" * 60)

    # 1. Optimize for Sharpe ratio
    print("\n1. Sharpe Ratio Optimization:")
    sharpe_portfolio = optimizer.optimize_portfolio(optimize_for="sharpe")

    print(f"Expected Return: {sharpe_portfolio.expected_return:.2%}")
    print(f"Expected Risk: {sharpe_portfolio.expected_risk:.2%}")
    print(f"Sharpe Ratio: {sharpe_portfolio.sharpe_ratio:.2f}")
    print(f"Correlation Penalty: {sharpe_portfolio.correlation_penalty:.3f}")
    print("\nWeights:")
    for symbol, weight in zip(sharpe_portfolio.symbols, sharpe_portfolio.weights):
        print(f"  {symbol}: {weight:+.1%}")

    # 2. Risk Parity
    print("\n2. Risk Parity Weights:")
    rp_weights = optimizer.get_risk_parity_weights()
    for symbol, weight in zip(symbols, rp_weights):
        print(f"  {symbol}: {weight:.1%}")

    # 3. Regime-based adjustment
    print("\n3. Regime-Based Recommendations:")

    current_weights = {"EURUSD": 0.25, "GBPUSD": 0.25, "USDJPY": 0.25, "USDCHF": 0.25}

    for regime in ["RISK_OFF", "NEUTRAL", "RISK_ON"]:
        print(f"\n{regime} Regime:")
        adjustments = optimizer.recommend_portfolio_adjustments(current_weights, regime)

        metadata = adjustments.pop("_metadata")
        print(f"  Expected Sharpe: {metadata['sharpe_ratio']:.2f}")
        print(f"  Adjustments:")
        for symbol, adj in adjustments.items():
            if abs(adj) > 0.01:  # Only show significant adjustments
                print(f"    {symbol}: {adj:+.1%}")


if __name__ == "__main__":
    example_usage()
