"""
Portfolio management module for Elliott Wave trading strategies.

This module implements portfolio-level strategy logic, including
multi-currency portfolio construction, correlation-based
diversification, and exposure management.
"""

import datetime
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

import numpy as np
import pandas as pd

from fxml3.strategy.entry_signals import EntrySignal, SignalStrength, SignalType
from fxml3.strategy.position_sizing import (
    PositionSize,
    PositionSizer,
    PositionSizingMethod,
)
from fxml3.strategy.risk_management import RiskManager


@dataclass
class Position:
    """Represents an active position in the portfolio."""

    id: str  # Unique identifier for the position
    symbol: str  # Trading symbol (e.g., "EURUSD")
    type: str  # Position type: "long" or "short"
    entry_price: float  # Entry price
    stop_loss: float  # Stop loss price
    take_profit: float  # Take profit price
    entry_time: datetime.datetime  # Entry timestamp
    size: float  # Position size
    pattern: str  # Elliott Wave pattern
    timeframe: str  # Timeframe (e.g., "1H", "4H", "1D")
    risk_amount: float  # Risk amount in account currency
    risk_percentage: float  # Risk as percentage of account
    status: str = "open"  # Position status: "open", "partial_exit", "closed"
    exits: List[Dict[str, Any]] = None  # List of partial exits, if any
    metadata: Dict[str, Any] = None  # Additional metadata


class CorrelationType(Enum):
    """Types of correlation relationships."""

    STRONG_POSITIVE = 3  # Correlation > 0.7
    MODERATE_POSITIVE = 2  # Correlation 0.3 to 0.7
    WEAK_POSITIVE = 1  # Correlation 0 to 0.3
    NEUTRAL = 0  # Correlation near 0
    WEAK_NEGATIVE = -1  # Correlation 0 to -0.3
    MODERATE_NEGATIVE = -2  # Correlation -0.3 to -0.7
    STRONG_NEGATIVE = -3  # Correlation < -0.7


class AssetClass(Enum):
    """Asset class categorization."""

    MAJOR_FX = 1  # Major forex pairs (EUR/USD, GBP/USD, etc.)
    MINOR_FX = 2  # Minor forex pairs (EUR/GBP, AUD/CAD, etc.)
    EXOTIC_FX = 3  # Exotic forex pairs (USD/TRY, EUR/HUF, etc.)
    COMMODITY_FX = 4  # Commodity currencies (AUD/USD, USD/CAD, etc.)
    INDICES = 5  # Stock indices
    COMMODITIES = 6  # Commodities
    CRYPTO = 7  # Cryptocurrencies
    STOCKS = 8  # Individual stocks


class PortfolioManager:
    """
    Manages a portfolio of trading positions across multiple currency pairs.

    This class implements portfolio-level strategy logic, handling position
    allocation, correlation management, and risk exposure across multiple
    instruments.
    """

    def __init__(
        self,
        risk_manager: Optional[RiskManager] = None,
        position_sizer: Optional[PositionSizer] = None,
        max_portfolio_risk: float = 0.05,  # 5% maximum portfolio risk
        max_correlation_exposure: float = 0.3,  # 30% max for correlated assets
        default_position_timeframe: str = "1D",  # Default position timeframe
        use_correlation_adjustment: bool = True,  # Whether to adjust for correlations
        correlation_lookback: int = 90,  # Days to look back for correlation calculation
        account_base_currency: str = "USD",  # Base currency for the account
    ):
        """
        Initialize the portfolio manager.

        Args:
            risk_manager: Risk manager for stop loss and risk calculations
            position_sizer: Position sizer for determining position sizes
            max_portfolio_risk: Maximum portfolio risk as percentage of account
            max_correlation_exposure: Maximum exposure to correlated assets
            default_position_timeframe: Default timeframe for position tracking
            use_correlation_adjustment: Whether to adjust for correlations
            correlation_lookback: Lookback period for correlation calculation
            account_base_currency: Base currency for the account
        """
        self.risk_manager = risk_manager or RiskManager()
        self.position_sizer = position_sizer or PositionSizer()
        self.max_portfolio_risk = max_portfolio_risk
        self.max_correlation_exposure = max_correlation_exposure
        self.default_position_timeframe = default_position_timeframe
        self.use_correlation_adjustment = use_correlation_adjustment
        self.correlation_lookback = correlation_lookback
        self.account_base_currency = account_base_currency

        # Active positions by symbol
        self.positions: Dict[str, List[Position]] = {}

        # Correlation matrix between symbols
        self.correlation_matrix: Dict[str, Dict[str, float]] = {}

        # Asset categorization
        self.asset_classes: Dict[str, AssetClass] = {}

        # Exposure tracking
        self.current_exposure: Dict[str, float] = {}
        self.exposure_by_asset_class: Dict[AssetClass, float] = {}
        self.exposure_by_correlation_group: Dict[str, float] = {}
        self.total_portfolio_risk: float = 0.0

        # Position history
        self.closed_positions: List[Position] = []

        # Initialize common forex asset classes
        self._initialize_asset_classes()

    def evaluate_new_position(
        self,
        entry_signal: EntrySignal,
        symbol: str,
        account_size: float,
        current_price_data: Optional[pd.DataFrame] = None,
        historical_data: Optional[Dict[str, pd.DataFrame]] = None,
        custom_stop_loss: Optional[float] = None,
        custom_take_profit: Optional[float] = None,
        sizing_method: PositionSizingMethod = PositionSizingMethod.KELLY,
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Evaluate whether a new position fits within portfolio constraints.

        Args:
            entry_signal: Entry signal for the new position
            symbol: Trading symbol for the position
            account_size: Current account size
            current_price_data: Current price data for the symbol
            historical_data: Historical price data for correlation analysis
            custom_stop_loss: Optional custom stop loss price
            custom_take_profit: Optional custom take profit price
            sizing_method: Position sizing method to use

        Returns:
            Tuple of (accepted_flag, evaluation_metadata)
        """
        evaluation = {
            "symbol": symbol,
            "signal_type": entry_signal.signal_type,
            "pattern": entry_signal.pattern,
            "accepted": False,
            "reasons": [],
        }

        # 1. Check if we already have a position for this symbol in the same direction
        if symbol in self.positions and self.positions[symbol]:
            for position in self.positions[symbol]:
                if (
                    position.type == "long"
                    and entry_signal.signal_type == SignalType.LONG
                ) or (
                    position.type == "short"
                    and entry_signal.signal_type == SignalType.SHORT
                ):
                    evaluation["reasons"].append(
                        f"Already have a {position.type} position for {symbol}"
                    )
                    return False, evaluation

        # 2. Determine position size and risk
        stop_loss = custom_stop_loss or entry_signal.stop_loss
        take_profit = custom_take_profit or entry_signal.take_profit
        position_result = self.position_sizer.calculate_position_size(
            entry_signal=entry_signal,
            account_size=account_size,
            method=sizing_method,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )

        # Store sizing information
        evaluation["position_size"] = position_result.size
        evaluation["risk_amount"] = position_result.risk_amount
        evaluation["risk_percentage"] = position_result.risk_percentage

        # 3. Check if adding this position would exceed maximum portfolio risk
        new_portfolio_risk = self.total_portfolio_risk + position_result.risk_percentage
        if new_portfolio_risk > self.max_portfolio_risk:
            evaluation["reasons"].append(
                f"Portfolio risk would exceed maximum: {new_portfolio_risk:.2%} > {self.max_portfolio_risk:.2%}"
            )
            return False, evaluation

        # 4. Check correlation-based exposure limits if enabled
        if self.use_correlation_adjustment and historical_data:
            # Update correlation matrix if needed
            if not self.correlation_matrix or symbol not in self.correlation_matrix:
                self._update_correlation_matrix(historical_data)

            # Get correlated symbols
            correlated_symbols = self._get_correlated_symbols(symbol, threshold=0.7)
            correlation_exposure = 0.0

            # Calculate exposure to correlated symbols
            for corr_symbol in correlated_symbols:
                if corr_symbol in self.current_exposure:
                    correlation_exposure += self.current_exposure[corr_symbol]

            # Add new position exposure
            correlation_exposure += position_result.risk_percentage

            # Check if correlation exposure would exceed limit
            if correlation_exposure > self.max_correlation_exposure:
                evaluation["reasons"].append(
                    f"Correlation exposure would exceed maximum: {correlation_exposure:.2%} > {self.max_correlation_exposure:.2%}"
                )
                evaluation["correlated_symbols"] = correlated_symbols
                evaluation["correlation_exposure"] = correlation_exposure
                return False, evaluation

            # Store correlation information
            evaluation["correlated_symbols"] = correlated_symbols
            evaluation["correlation_exposure"] = correlation_exposure

        # 5. Check asset class diversification
        asset_class = self._get_asset_class(symbol)
        asset_exposure = self.exposure_by_asset_class.get(asset_class, 0.0)
        new_asset_exposure = asset_exposure + position_result.risk_percentage

        # Apply asset class specific limits (e.g., max 30% in exotic currencies)
        max_asset_exposure = self._get_max_asset_exposure(asset_class)
        if new_asset_exposure > max_asset_exposure:
            evaluation["reasons"].append(
                f"{asset_class.name} exposure would exceed maximum: {new_asset_exposure:.2%} > {max_asset_exposure:.2%}"
            )
            return False, evaluation

        # Position passes all checks
        evaluation["accepted"] = True
        return True, evaluation

    def add_position(
        self,
        entry_signal: EntrySignal,
        symbol: str,
        position_size: float,
        account_size: float,
        entry_time: Optional[datetime.datetime] = None,
        custom_stop_loss: Optional[float] = None,
        custom_take_profit: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Position:
        """
        Add a new position to the portfolio.

        Args:
            entry_signal: Entry signal for the position
            symbol: Trading symbol for the position
            position_size: Size of the position
            account_size: Current account size
            entry_time: Entry timestamp (defaults to current time)
            custom_stop_loss: Optional custom stop loss price
            custom_take_profit: Optional custom take profit price
            metadata: Additional metadata for the position

        Returns:
            The created Position object
        """
        # Ensure entry_time is set
        if entry_time is None:
            entry_time = datetime.datetime.now()

        # Create position ID
        position_id = f"{symbol}_{entry_signal.signal_type.name}_{entry_time.strftime('%Y%m%d%H%M%S')}"

        # Determine position type
        position_type = (
            "long" if entry_signal.signal_type == SignalType.LONG else "short"
        )

        # Use custom stop loss and take profit if provided
        stop_loss = custom_stop_loss or entry_signal.stop_loss
        take_profit = custom_take_profit or entry_signal.take_profit

        # Calculate risk amount and percentage
        entry_price = entry_signal.entry_price
        price_risk = abs(entry_price - stop_loss)
        risk_amount = position_size * price_risk
        risk_percentage = risk_amount / account_size if account_size > 0 else 0.0

        # Create position object
        position = Position(
            id=position_id,
            symbol=symbol,
            type=position_type,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            entry_time=entry_time,
            size=position_size,
            pattern=entry_signal.pattern,
            timeframe=entry_signal.timeframe or self.default_position_timeframe,
            risk_amount=risk_amount,
            risk_percentage=risk_percentage,
            exits=[],
            metadata=metadata or {},
        )

        # Add to positions dictionary
        if symbol not in self.positions:
            self.positions[symbol] = []
        self.positions[symbol].append(position)

        # Update exposure tracking
        self._update_exposure(symbol, position, add=True)

        return position

    def update_position(
        self, position_id: str, updates: Dict[str, Any]
    ) -> Optional[Position]:
        """
        Update an existing position.

        Args:
            position_id: ID of the position to update
            updates: Dictionary with updates to apply

        Returns:
            Updated Position object or None if not found
        """
        # Find the position
        for symbol, positions in self.positions.items():
            for i, position in enumerate(positions):
                if position.id == position_id:
                    # Update exposure before modifying position
                    if "stop_loss" in updates or "size" in updates:
                        self._update_exposure(symbol, position, add=False)

                    # Apply updates
                    for key, value in updates.items():
                        if hasattr(position, key):
                            setattr(position, key, value)

                    # If partial exit, record it
                    if (
                        updates.get("status") == "partial_exit"
                        and "exit_data" in updates
                    ):
                        if position.exits is None:
                            position.exits = []
                        position.exits.append(updates["exit_data"])

                    # Update exposure after changes
                    if "stop_loss" in updates or "size" in updates:
                        self._update_exposure(symbol, position, add=True)

                    return position

        return None

    def close_position(
        self,
        position_id: str,
        exit_price: float,
        exit_time: Optional[datetime.datetime] = None,
        exit_type: str = "market",
        exit_reason: str = "",
        pnl: Optional[float] = None,
    ) -> Optional[Position]:
        """
        Close a position and move it to closed positions history.

        Args:
            position_id: ID of the position to close
            exit_price: Exit price
            exit_time: Exit timestamp (defaults to current time)
            exit_type: Type of exit (market, stop, target, etc.)
            exit_reason: Reason for closing the position
            pnl: Optional profit/loss amount (calculated if not provided)

        Returns:
            Closed Position object or None if not found
        """
        # Ensure exit_time is set
        if exit_time is None:
            exit_time = datetime.datetime.now()

        # Find the position
        for symbol, positions in self.positions.items():
            for i, position in enumerate(positions):
                if position.id == position_id:
                    # Calculate PNL if not provided
                    if pnl is None:
                        if position.type == "long":
                            pnl = (exit_price - position.entry_price) * position.size
                        else:  # short
                            pnl = (position.entry_price - exit_price) * position.size

                    # Update position with exit information
                    position.status = "closed"
                    position.metadata = position.metadata or {}
                    position.metadata.update(
                        {
                            "exit_price": exit_price,
                            "exit_time": exit_time,
                            "exit_type": exit_type,
                            "exit_reason": exit_reason,
                            "pnl": pnl,
                        }
                    )

                    # Remove from active positions
                    self.positions[symbol].pop(i)
                    if not self.positions[symbol]:
                        del self.positions[symbol]

                    # Add to closed positions
                    self.closed_positions.append(position)

                    # Update exposure
                    self._update_exposure(symbol, position, add=False)

                    # Add trade to position sizer history for Kelly calculations
                    self.position_sizer.add_trade_to_history(
                        {
                            "symbol": symbol,
                            "entry_price": position.entry_price,
                            "exit_price": exit_price,
                            "type": position.type,
                            "profit": pnl,
                            "pattern": position.pattern,
                            "timeframe": position.timeframe,
                        }
                    )

                    return position

        return None

    def get_active_positions(self) -> List[Position]:
        """
        Get all active positions across all symbols.

        Returns:
            List of active Position objects
        """
        active_positions = []
        for positions in self.positions.values():
            active_positions.extend(positions)
        return active_positions

    def get_portfolio_stats(self, account_size: float) -> Dict[str, Any]:
        """
        Get statistics about the current portfolio.

        Args:
            account_size: Current account size

        Returns:
            Dictionary with portfolio statistics
        """
        active_positions = self.get_active_positions()

        stats = {
            "total_positions": len(active_positions),
            "portfolio_risk": self.total_portfolio_risk,
            "portfolio_risk_percentage": self.total_portfolio_risk,  # Same as above for convenience
            "max_portfolio_risk": self.max_portfolio_risk,
            "risk_utilization": (
                self.total_portfolio_risk / self.max_portfolio_risk
                if self.max_portfolio_risk > 0
                else 0
            ),
            "position_count_by_type": {
                "long": sum(1 for p in active_positions if p.type == "long"),
                "short": sum(1 for p in active_positions if p.type == "short"),
            },
            "position_count_by_symbol": {
                symbol: len(positions) for symbol, positions in self.positions.items()
            },
            "risk_by_asset_class": {
                asset_class.name: risk_pct
                for asset_class, risk_pct in self.exposure_by_asset_class.items()
            },
            "exposure_by_symbol": self.current_exposure,
            "symbols_with_positions": list(self.positions.keys()),
            "exposure_categories": {
                "low": [],  # < 1% risk
                "medium": [],  # 1-2% risk
                "high": [],  # > 2% risk
            },
        }

        # Categorize symbols by exposure level
        for symbol, exposure in self.current_exposure.items():
            if exposure < 0.01:
                stats["exposure_categories"]["low"].append(symbol)
            elif exposure < 0.02:
                stats["exposure_categories"]["medium"].append(symbol)
            else:
                stats["exposure_categories"]["high"].append(symbol)

        return stats

    def reset_portfolio(self) -> None:
        """Reset the portfolio to an empty state."""
        self.positions = {}
        self.current_exposure = {}
        self.exposure_by_asset_class = {}
        self.exposure_by_correlation_group = {}
        self.total_portfolio_risk = 0.0

    def _update_exposure(
        self, symbol: str, position: Position, add: bool = True
    ) -> None:
        """
        Update exposure tracking for a position.

        Args:
            symbol: Symbol of the position
            position: Position object
            add: Whether to add (True) or remove (False) exposure
        """
        # Get asset class
        asset_class = self._get_asset_class(symbol)

        # Calculate risk percentage
        risk_percentage = position.risk_percentage

        # Adjust sign based on add/remove
        if not add:
            risk_percentage = -risk_percentage

        # Update symbol exposure
        self.current_exposure[symbol] = (
            self.current_exposure.get(symbol, 0.0) + risk_percentage
        )

        # Update asset class exposure
        self.exposure_by_asset_class[asset_class] = (
            self.exposure_by_asset_class.get(asset_class, 0.0) + risk_percentage
        )

        # Update total portfolio risk
        self.total_portfolio_risk += risk_percentage

        # Clean up if exposure is zero or negative
        if self.current_exposure[symbol] <= 0:
            del self.current_exposure[symbol]

        if (
            asset_class in self.exposure_by_asset_class
            and self.exposure_by_asset_class[asset_class] <= 0
        ):
            del self.exposure_by_asset_class[asset_class]

    def _update_correlation_matrix(
        self, historical_data: Dict[str, pd.DataFrame]
    ) -> None:
        """
        Update the correlation matrix based on historical data.

        Args:
            historical_data: Dictionary mapping symbols to historical price DataFrames
        """
        # Ensure all symbols have enough data
        valid_symbols = {}
        for symbol, data in historical_data.items():
            if len(data) >= self.correlation_lookback:
                valid_symbols[symbol] = (
                    data["close"].tail(self.correlation_lookback).values
                )

        # Create correlation matrix
        symbols = list(valid_symbols.keys())
        n_symbols = len(symbols)
        if n_symbols < 2:
            return

        # Initialize correlation matrix
        self.correlation_matrix = {symbol: {} for symbol in symbols}

        # Calculate correlations
        for i in range(n_symbols):
            sym1 = symbols[i]
            prices1 = valid_symbols[sym1]

            for j in range(i, n_symbols):
                sym2 = symbols[j]
                prices2 = valid_symbols[sym2]

                if i == j:
                    correlation = 1.0
                else:
                    # Calculate returns (percentage change)
                    returns1 = np.diff(prices1) / prices1[:-1]
                    returns2 = np.diff(prices2) / prices2[:-1]

                    # Ensure equal length
                    min_len = min(len(returns1), len(returns2))
                    returns1 = returns1[-min_len:]
                    returns2 = returns2[-min_len:]

                    # Calculate correlation
                    if min_len >= 30:  # Need sufficient data points
                        correlation = np.corrcoef(returns1, returns2)[0, 1]
                        if np.isnan(correlation):
                            correlation = 0.0
                    else:
                        correlation = 0.0

                # Store in matrix (both directions)
                self.correlation_matrix[sym1][sym2] = correlation
                if i != j:
                    self.correlation_matrix[sym2][sym1] = correlation

    def _get_correlated_symbols(self, symbol: str, threshold: float = 0.7) -> List[str]:
        """
        Get symbols that are correlated with the given symbol.

        Args:
            symbol: Symbol to get correlations for
            threshold: Correlation threshold to consider symbols correlated

        Returns:
            List of correlated symbols
        """
        if symbol not in self.correlation_matrix:
            return []

        correlated_symbols = []
        for other_symbol, correlation in self.correlation_matrix[symbol].items():
            if symbol != other_symbol and abs(correlation) >= threshold:
                correlated_symbols.append(other_symbol)

        return correlated_symbols

    def _initialize_asset_classes(self) -> None:
        """Initialize common forex asset classes."""
        # Major forex pairs (vs USD)
        major_pairs = [
            "EURUSD",
            "GBPUSD",
            "USDJPY",
            "AUDUSD",
            "USDCHF",
            "USDCAD",
            "NZDUSD",
        ]
        for pair in major_pairs:
            self.asset_classes[pair] = AssetClass.MAJOR_FX

        # Minor forex pairs (cross-rates between majors)
        minor_pairs = [
            "EURGBP",
            "EURJPY",
            "EURCHF",
            "EURAUD",
            "EURCAD",
            "GBPJPY",
            "GBPAUD",
            "GBPCAD",
            "CADJPY",
        ]
        for pair in minor_pairs:
            self.asset_classes[pair] = AssetClass.MINOR_FX

        # Commodity currencies
        commodity_pairs = ["AUDUSD", "USDCAD", "NZDUSD", "AUDJPY", "CADJPY", "NZDJPY"]
        for pair in commodity_pairs:
            self.asset_classes[pair] = AssetClass.COMMODITY_FX

        # Exotic currencies
        exotic_pairs = ["USDZAR", "USDTRY", "USDHKD", "USDRUB", "USDSGD"]
        for pair in exotic_pairs:
            self.asset_classes[pair] = AssetClass.EXOTIC_FX

        # Indices
        indices = ["SPX500", "NAS100", "DJ30", "UK100", "GER40", "JPN225"]
        for index in indices:
            self.asset_classes[index] = AssetClass.INDICES

        # Commodities
        commodities = ["XAUUSD", "XAGUSD", "XTIUSD", "XBRUSD"]
        for commodity in commodities:
            self.asset_classes[commodity] = AssetClass.COMMODITIES

        # Cryptocurrencies
        cryptos = ["BTCUSD", "ETHUSD", "LTCUSD", "XRPUSD"]
        for crypto in cryptos:
            self.asset_classes[crypto] = AssetClass.CRYPTO

    def _get_asset_class(self, symbol: str) -> AssetClass:
        """
        Get the asset class for a symbol.

        Args:
            symbol: Symbol to get asset class for

        Returns:
            AssetClass enum value
        """
        # Return from known mapping if available
        if symbol in self.asset_classes:
            return self.asset_classes[symbol]

        # Try to infer for unknown forex pairs
        if len(symbol) == 6 and symbol.isupper():
            # Assume it's a forex pair
            if "USD" in symbol:
                return AssetClass.MAJOR_FX
            else:
                return AssetClass.MINOR_FX

        # Default to STOCKS for unknown symbols
        return AssetClass.STOCKS

    def _get_max_asset_exposure(self, asset_class: AssetClass) -> float:
        """
        Get maximum allowable exposure for an asset class.

        Args:
            asset_class: Asset class to get max exposure for

        Returns:
            Maximum exposure as a percentage
        """
        # Define maximum exposure limits by asset class
        limits = {
            AssetClass.MAJOR_FX: 0.6,  # 60% max in major forex
            AssetClass.MINOR_FX: 0.4,  # 40% max in minor forex
            AssetClass.EXOTIC_FX: 0.2,  # 20% max in exotic forex
            AssetClass.COMMODITY_FX: 0.3,  # 30% max in commodity currencies
            AssetClass.INDICES: 0.3,  # 30% max in indices
            AssetClass.COMMODITIES: 0.2,  # 20% max in commodities
            AssetClass.CRYPTO: 0.1,  # 10% max in crypto
            AssetClass.STOCKS: 0.2,  # 20% max in stocks
        }

        return limits.get(asset_class, 0.2)  # Default to 20% for unknown asset classes

    def group_positions_by_correlation(self) -> Dict[str, List[Position]]:
        """
        Group positions by correlation to identify exposure clusters.

        Returns:
            Dictionary mapping correlation group to positions
        """
        if not self.correlation_matrix:
            return {"no_correlation_data": self.get_active_positions()}

        # Create correlation groups
        all_positions = self.get_active_positions()
        symbols = set(pos.symbol for pos in all_positions)

        # Create graph where edges represent strong correlations
        correlation_graph: Dict[str, Set[str]] = {sym: set() for sym in symbols}
        for sym1 in symbols:
            if sym1 not in self.correlation_matrix:
                continue

            for sym2 in symbols:
                if sym1 == sym2 or sym2 not in self.correlation_matrix[sym1]:
                    continue

                correlation = self.correlation_matrix[sym1][sym2]
                if abs(correlation) >= 0.7:  # Strong correlation threshold
                    correlation_graph[sym1].add(sym2)

        # Implement connected components algorithm to find correlation clusters
        visited: Set[str] = set()
        correlation_groups: Dict[str, List[Position]] = {}

        for symbol in symbols:
            if symbol in visited:
                continue

            # Start a new cluster
            cluster = []
            self._dfs_correlation(symbol, correlation_graph, visited, cluster)

            if cluster:
                group_name = "_".join(sorted(cluster))

                # Add positions in this cluster
                correlation_groups[group_name] = [
                    pos for pos in all_positions if pos.symbol in cluster
                ]

        # Add any unvisited symbols (with no correlations)
        isolated_symbols = symbols - visited
        for symbol in isolated_symbols:
            correlation_groups[symbol] = [
                pos for pos in all_positions if pos.symbol == symbol
            ]

        return correlation_groups

    def _dfs_correlation(
        self,
        symbol: str,
        graph: Dict[str, Set[str]],
        visited: Set[str],
        cluster: List[str],
    ) -> None:
        """
        Depth-first search for finding connected correlation components.

        Args:
            symbol: Current symbol to process
            graph: Correlation graph representation
            visited: Set of visited symbols
            cluster: Current cluster being built
        """
        visited.add(symbol)
        cluster.append(symbol)

        if symbol not in graph:
            return

        for neighbor in graph[symbol]:
            if neighbor not in visited:
                self._dfs_correlation(neighbor, graph, visited, cluster)

    def analyze_portfolio_correlation_risk(self) -> Dict[str, Any]:
        """
        Analyze portfolio correlation risk to identify concentrated exposures.

        Returns:
            Dictionary with correlation risk analysis
        """
        # Group positions by correlation
        correlation_groups = self.group_positions_by_correlation()

        # Calculate risk for each group
        group_risk: Dict[str, float] = {}
        for group_name, positions in correlation_groups.items():
            group_risk[group_name] = sum(pos.risk_percentage for pos in positions)

        # Identify high-risk correlation groups
        high_risk_groups = {
            group: risk
            for group, risk in group_risk.items()
            if risk > self.max_correlation_exposure
        }

        # Calculate directional exposure within groups
        group_directional: Dict[str, Dict[str, float]] = {}
        for group_name, positions in correlation_groups.items():
            long_risk = sum(
                pos.risk_percentage for pos in positions if pos.type == "long"
            )
            short_risk = sum(
                pos.risk_percentage for pos in positions if pos.type == "short"
            )

            group_directional[group_name] = {
                "long": long_risk,
                "short": short_risk,
                "net": long_risk - short_risk,
            }

        return {
            "correlation_groups": correlation_groups,
            "group_risk": group_risk,
            "high_risk_groups": high_risk_groups,
            "group_directional_exposure": group_directional,
            "total_groups": len(correlation_groups),
            "max_group_risk": max(group_risk.values()) if group_risk else 0.0,
        }
