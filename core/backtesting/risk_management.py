"""Risk management module for backtesting.

This module provides risk management capabilities for backtesting, including
position sizing, stop-loss management, drawdown controls, and portfolio-level risk metrics.

DEPRECATED: This module is being refactored. Use the unified risk management system:
- BacktestRiskManager from fxml4.risk_management.backtest
- BaseRiskManager from fxml4.risk_management.base
"""

import logging
import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from fxml4.backtesting.event import OrderEvent, SignalEvent

# Import from new refactored modules
from fxml4.backtesting.risk.position_sizing import (
    FixedPositionSizer,
    KellyPositionSizer,
    PercentagePositionSizer,
    PositionSizer,
    VolatilityPositionSizer,
)
from fxml4.backtesting.risk.stop_loss.types import StopLossType
from fxml4.config import get_config

logger = logging.getLogger(__name__)

# Import position sizing factory for easy access
try:
    from fxml4.backtesting.position_sizing_factory import position_sizing_factory
except ImportError:
    position_sizing_factory = None
    logger.warning("Enhanced position sizing factory not available")


# Position sizing classes moved to fxml4.backtesting.risk.position_sizing
# The classes are imported above for backward compatibility


class OptimalFPositionSizer(PositionSizer):
    """Optimal-F position sizer.

    Uses Ralph Vince's Optimal-F method for position sizing.
    """

    def __init__(
        self,
        default_optimal_f: float = 0.1,
        max_allocation: float = 0.2,
        lookback_trades: int = 20,
    ):
        """Initialize an Optimal-F position sizer.

        Args:
            default_optimal_f: Default Optimal-F value to use if no history available.
            max_allocation: Maximum allocation as a fraction of equity.
            lookback_trades: Number of past trades to consider for statistics.
        """
        self.default_optimal_f = default_optimal_f
        self.max_allocation = max_allocation
        self.lookback_trades = lookback_trades

    def calculate_position_size(
        self,
        signal: SignalEvent,
        portfolio: Any,
        current_price: float,
    ) -> float:
        """Calculate Optimal-F position size.

        Args:
            signal: Signal event.
            portfolio: Portfolio instance.
            current_price: Current price of the asset.

        Returns:
            Position size (quantity).
        """
        # Calculate Optimal-F from portfolio history
        optimal_f = self._calculate_optimal_f(portfolio, signal.symbol)

        # Allow overriding with signal data
        optimal_f = signal.signal_data.get("optimal_f", optimal_f)

        # Apply max allocation
        allocation_pct = min(optimal_f, self.max_allocation)

        # Calculate allocation amount
        amount = portfolio.equity * allocation_pct

        # Calculate quantity
        quantity = amount / current_price if current_price > 0 else 0

        return quantity

    def _calculate_optimal_f(
        self, portfolio: Any, symbol: Optional[str] = None
    ) -> float:
        """Calculate Optimal-F from portfolio history.

        Args:
            portfolio: Portfolio instance.
            symbol: Symbol to filter trades by (optional).

        Returns:
            Optimal-F value.
        """
        closed_positions = portfolio.get_closed_positions()

        # Filter by symbol if provided
        if symbol:
            closed_positions = [
                p for p in closed_positions if p.get("symbol") == symbol
            ]

        # Limit to recent trades
        closed_positions = (
            closed_positions[-self.lookback_trades :] if closed_positions else []
        )

        if not closed_positions:
            return self.default_optimal_f

        # Calculate R multiples (P&L divided by initial risk)
        r_multiples = []
        for position in closed_positions:
            # Use actual P&L
            pnl = position.get("realized_pnl", 0)

            # Estimate initial risk from avg_price * 0.01 if not available
            price = position.get("avg_price", 0)
            risk = position.get("initial_risk", price * 0.01 * position.get("size", 1))

            # Calculate R multiple
            if risk > 0:
                r_multiple = pnl / risk
                r_multiples.append(r_multiple)

        if not r_multiples:
            return self.default_optimal_f

        # Calculate Optimal-F
        worst_loss = min(r_multiples)
        if worst_loss >= 0:
            # All trades are winners, use default
            return self.default_optimal_f

        # Optimal-F formula: 1 / abs(worst_loss)
        optimal_f = 1 / abs(worst_loss)

        # Conservative adjustment: use a fraction of Optimal-F
        return optimal_f * 0.5  # Use half of the calculated Optimal-F


class PositionSizingRegistry:
    """Registry of position sizing algorithms."""

    def __init__(self):
        """Initialize the registry with default algorithms."""
        self.algorithms = {
            "fixed": FixedPositionSizer(),
            "percentage": PercentagePositionSizer(),
            "volatility": VolatilityPositionSizer(),
            "kelly": KellyPositionSizer(),
            "optimal_f": OptimalFPositionSizer(),
        }

    def register(self, name: str, algorithm: PositionSizer) -> None:
        """Register a new position sizing algorithm.

        Args:
            name: Algorithm name.
            algorithm: Position sizer instance.
        """
        self.algorithms[name] = algorithm

    def get(self, name: str) -> PositionSizer:
        """Get a position sizing algorithm by name.

        Args:
            name: Algorithm name.

        Returns:
            Position sizer instance.

        Raises:
            KeyError: If algorithm not found.
        """
        return self.algorithms[name]


class StopLossType(Enum):
    """Types of stop-loss orders."""

    FIXED = "fixed"
    PERCENTAGE = "percentage"
    VOLATILITY = "volatility"
    TRAILING = "trailing"
    CHANDELIER = "chandelier"
    TIME = "time"


class StopLossManager:
    """Manager for stop-loss orders."""

    def __init__(
        self,
        default_type: StopLossType = StopLossType.PERCENTAGE,
        default_percentage: float = 0.02,
        default_atr_multiple: float = 2.0,
        default_trailing_percentage: float = 0.01,
        default_time_limit: Optional[timedelta] = None,
    ):
        """Initialize the stop-loss manager.

        Args:
            default_type: Default stop-loss type.
            default_percentage: Default percentage for percentage stops.
            default_atr_multiple: Default ATR multiple for volatility stops.
            default_trailing_percentage: Default percentage for trailing stops.
            default_time_limit: Default time limit for time stops.
        """
        self.default_type = default_type
        self.default_percentage = default_percentage
        self.default_atr_multiple = default_atr_multiple
        self.default_trailing_percentage = default_trailing_percentage
        self.default_time_limit = default_time_limit
        self.stop_orders: Dict[str, Dict[str, Any]] = {}

    def create_stop_loss(
        self,
        signal: SignalEvent,
        entry_price: float,
        entry_time: datetime,
        position_id: str,
        market_data: Optional[pd.DataFrame] = None,
    ) -> Optional[OrderEvent]:
        """Create a stop-loss order based on a signal.

        Args:
            signal: Signal event.
            entry_price: Entry price of the position.
            entry_time: Entry time of the position.
            position_id: Position ID.
            market_data: Historical market data (for volatility calculation).

        Returns:
            Stop-loss order event if applicable, None otherwise.
        """
        stop_type = signal.signal_data.get("stop_type", self.default_type.value)
        stop_price = None

        # If stop_loss is explicitly provided in signal, use it
        if "stop_loss" in signal.signal_data:
            stop_price = signal.signal_data["stop_loss"]
        else:
            # Calculate stop price based on stop type
            if stop_type == StopLossType.FIXED.value:
                fixed_amount = signal.signal_data.get("stop_amount", entry_price * 0.02)
                stop_price = (
                    entry_price - fixed_amount
                    if signal.signal_data.get("side") == "buy"
                    else entry_price + fixed_amount
                )

            elif stop_type == StopLossType.PERCENTAGE.value:
                percentage = signal.signal_data.get(
                    "stop_percentage", self.default_percentage
                )
                stop_price = (
                    entry_price * (1 - percentage)
                    if signal.signal_data.get("side") == "buy"
                    else entry_price * (1 + percentage)
                )

            elif stop_type == StopLossType.VOLATILITY.value and market_data is not None:
                atr_multiple = signal.signal_data.get(
                    "atr_multiple", self.default_atr_multiple
                )
                atr = self._calculate_atr(market_data)
                stop_price = (
                    entry_price - (atr * atr_multiple)
                    if signal.signal_data.get("side") == "buy"
                    else entry_price + (atr * atr_multiple)
                )

            elif stop_type == StopLossType.TRAILING.value:
                # For trailing stops, set initial stop price
                trailing_percentage = signal.signal_data.get(
                    "trailing_percentage", self.default_trailing_percentage
                )
                stop_price = (
                    entry_price * (1 - trailing_percentage)
                    if signal.signal_data.get("side") == "buy"
                    else entry_price * (1 + trailing_percentage)
                )

            elif stop_type == StopLossType.CHANDELIER.value and market_data is not None:
                # Chandelier exit (ATR from recent high/low)
                atr_multiple = signal.signal_data.get(
                    "atr_multiple", self.default_atr_multiple
                )
                atr = self._calculate_atr(market_data)

                if signal.signal_data.get("side") == "buy":
                    recent_high = (
                        market_data["high"].iloc[-20:].max()
                        if len(market_data) >= 20
                        else entry_price
                    )
                    stop_price = recent_high - (atr * atr_multiple)
                else:
                    recent_low = (
                        market_data["low"].iloc[-20:].min()
                        if len(market_data) >= 20
                        else entry_price
                    )
                    stop_price = recent_low + (atr * atr_multiple)

            elif stop_type == StopLossType.TIME.value:
                # Time-based stops don't have a price component
                time_limit = signal.signal_data.get(
                    "time_limit", self.default_time_limit
                )
                if time_limit:
                    # Store time limit in stop orders
                    self.stop_orders[position_id] = {
                        "type": StopLossType.TIME.value,
                        "entry_time": entry_time,
                        "time_limit": time_limit,
                        "position_id": position_id,
                        "symbol": signal.symbol,
                        "side": (
                            "sell" if signal.signal_data.get("side") == "buy" else "buy"
                        ),
                    }
                return None

        if stop_price is None:
            return None

        # Create stop order
        order_id = f"stop-{uuid.uuid4()}"
        order = OrderEvent(
            timestamp=entry_time,
            order_id=order_id,
            symbol=signal.symbol,
            order_type="stop",
            side="sell" if signal.signal_data.get("side") == "buy" else "buy",
            quantity=signal.signal_data.get("quantity", 0),
            price=None,
            stop_price=stop_price,
            limit_price=None,
            time_in_force="GTC",
            parent_order_id=position_id,
            signal_id=None,
            additional_params={
                "stop_type": stop_type,
                "trailing": stop_type == StopLossType.TRAILING.value,
                "trailing_percentage": (
                    signal.signal_data.get(
                        "trailing_percentage", self.default_trailing_percentage
                    )
                    if stop_type == StopLossType.TRAILING.value
                    else None
                ),
            },
        )

        # Store stop order info
        self.stop_orders[position_id] = {
            "type": stop_type,
            "order_id": order_id,
            "stop_price": stop_price,
            "entry_price": entry_price,
            "position_id": position_id,
            "symbol": signal.symbol,
            "side": signal.signal_data.get("side"),
            "trailing": stop_type == StopLossType.TRAILING.value,
            "trailing_percentage": (
                signal.signal_data.get(
                    "trailing_percentage", self.default_trailing_percentage
                )
                if stop_type == StopLossType.TRAILING.value
                else None
            ),
            "highest_price": (
                entry_price if signal.signal_data.get("side") == "buy" else None
            ),
            "lowest_price": (
                entry_price if signal.signal_data.get("side") == "sell" else None
            ),
        }

        return order

    def update_stops(
        self,
        current_prices: Dict[str, float],
        current_time: datetime,
    ) -> List[OrderEvent]:
        """Update stop-loss orders based on new prices.

        Args:
            current_prices: Current prices by symbol.
            current_time: Current time.

        Returns:
            List of updated stop orders.
        """
        updated_orders = []
        triggered_stops = []

        for position_id, stop_info in self.stop_orders.items():
            symbol = stop_info.get("symbol")

            if symbol not in current_prices:
                continue

            current_price = current_prices[symbol]

            # Check time-based stops
            if stop_info.get("type") == StopLossType.TIME.value:
                entry_time = stop_info.get("entry_time")
                time_limit = stop_info.get("time_limit")

                if (
                    entry_time
                    and time_limit
                    and current_time - entry_time >= time_limit
                ):
                    # Time limit reached, create market order to close position
                    order = OrderEvent(
                        timestamp=current_time,
                        order_id=f"time-stop-{uuid.uuid4()}",
                        symbol=symbol,
                        order_type="market",
                        side=stop_info.get("side", "sell"),
                        quantity=stop_info.get("quantity", 0),
                        price=None,
                        stop_price=None,
                        limit_price=None,
                        time_in_force="IOC",
                        parent_order_id=position_id,
                        signal_id=None,
                        additional_params={"stop_type": StopLossType.TIME.value},
                    )
                    updated_orders.append(order)
                    triggered_stops.append(position_id)
                    continue

            # Update trailing stops
            if stop_info.get("trailing"):
                side = stop_info.get("side")
                trailing_percentage = stop_info.get(
                    "trailing_percentage", self.default_trailing_percentage
                )

                if side == "buy":
                    # For long positions, track highest price and adjust stop
                    highest_price = stop_info.get("highest_price", current_price)
                    if current_price > highest_price:
                        # Update highest price
                        stop_info["highest_price"] = current_price
                        # Update stop price
                        new_stop = current_price * (1 - trailing_percentage)
                        if new_stop > stop_info.get("stop_price", 0):
                            stop_info["stop_price"] = new_stop
                            # Create updated stop order
                            order = OrderEvent(
                                timestamp=current_time,
                                order_id=stop_info.get(
                                    "order_id", f"trailing-{uuid.uuid4()}"
                                ),
                                symbol=symbol,
                                order_type="stop",
                                side="sell",
                                quantity=stop_info.get("quantity", 0),
                                price=None,
                                stop_price=new_stop,
                                limit_price=None,
                                time_in_force="GTC",
                                parent_order_id=position_id,
                                signal_id=None,
                                additional_params={
                                    "stop_type": StopLossType.TRAILING.value
                                },
                            )
                            updated_orders.append(order)

                elif side == "sell":
                    # For short positions, track lowest price and adjust stop
                    lowest_price = stop_info.get("lowest_price", current_price)
                    if current_price < lowest_price:
                        # Update lowest price
                        stop_info["lowest_price"] = current_price
                        # Update stop price
                        new_stop = current_price * (1 + trailing_percentage)
                        if new_stop < stop_info.get("stop_price", float("inf")):
                            stop_info["stop_price"] = new_stop
                            # Create updated stop order
                            order = OrderEvent(
                                timestamp=current_time,
                                order_id=stop_info.get(
                                    "order_id", f"trailing-{uuid.uuid4()}"
                                ),
                                symbol=symbol,
                                order_type="stop",
                                side="buy",
                                quantity=stop_info.get("quantity", 0),
                                price=None,
                                stop_price=new_stop,
                                limit_price=None,
                                time_in_force="GTC",
                                parent_order_id=position_id,
                                signal_id=None,
                                additional_params={
                                    "stop_type": StopLossType.TRAILING.value
                                },
                            )
                            updated_orders.append(order)

        # Remove triggered stops
        for position_id in triggered_stops:
            if position_id in self.stop_orders:
                del self.stop_orders[position_id]

        return updated_orders

    def remove_stop(self, position_id: str) -> None:
        """Remove a stop-loss order.

        Args:
            position_id: Position ID.
        """
        if position_id in self.stop_orders:
            del self.stop_orders[position_id]

    def _calculate_atr(self, market_data: pd.DataFrame, window: int = 14) -> float:
        """Calculate Average True Range (ATR).

        Args:
            market_data: Market data with OHLC prices.
            window: Window size for ATR calculation.

        Returns:
            ATR value.
        """
        # Extract high, low, close prices
        high = market_data["high"].values
        low = market_data["low"].values
        close = market_data["close"].values

        # Calculate true range
        tr1 = np.abs(high[1:] - low[1:])
        tr2 = np.abs(high[1:] - close[:-1])
        tr3 = np.abs(low[1:] - close[:-1])

        # True range is the maximum of the three
        tr = np.vstack([tr1, tr2, tr3]).max(axis=0)

        # Calculate ATR (simple average of true range over window)
        atr = np.mean(tr[-window:]) if len(tr) >= window else np.mean(tr)

        return atr


class DrawdownControl:
    """Drawdown control for risk management."""

    def __init__(
        self,
        max_drawdown_pct: float = 0.20,  # 20% max drawdown
        per_symbol_drawdown_pct: float = 0.10,  # 10% max per symbol
        cooling_off_days: int = 5,
        reduction_factor: float = 0.5,
    ):
        """Initialize the drawdown control.

        Args:
            max_drawdown_pct: Maximum portfolio drawdown percentage.
            per_symbol_drawdown_pct: Maximum drawdown percentage per symbol.
            cooling_off_days: Days to cool off after max drawdown.
            reduction_factor: Position size reduction factor during drawdown.
        """
        self.max_drawdown_pct = max_drawdown_pct
        self.per_symbol_drawdown_pct = per_symbol_drawdown_pct
        self.cooling_off_days = cooling_off_days
        self.reduction_factor = reduction_factor
        self.portfolio_peak = 0.0
        self.symbol_peaks: Dict[str, float] = {}
        self.cooling_off_until: Dict[str, datetime] = {}
        self.portfolio_cooling_off_until: Optional[datetime] = None

    def check_drawdown(
        self,
        portfolio_value: float,
        symbol_values: Dict[str, float],
        current_time: datetime,
    ) -> Dict[str, Any]:
        """Check drawdown levels and return control signals.

        Args:
            portfolio_value: Current portfolio value.
            symbol_values: Current values by symbol.
            current_time: Current time.

        Returns:
            Dict with drawdown status and control signals.
        """
        # Update portfolio peak
        self.portfolio_peak = max(self.portfolio_peak, portfolio_value)

        # Calculate portfolio drawdown
        portfolio_drawdown = 0.0
        if self.portfolio_peak > 0:
            portfolio_drawdown = (
                self.portfolio_peak - portfolio_value
            ) / self.portfolio_peak

        # Check portfolio-level cooling off
        portfolio_cooling_off = False
        if (
            self.portfolio_cooling_off_until
            and current_time < self.portfolio_cooling_off_until
        ):
            portfolio_cooling_off = True

        # Set new cooling off period if max drawdown exceeded
        if portfolio_drawdown > self.max_drawdown_pct and not portfolio_cooling_off:
            self.portfolio_cooling_off_until = current_time + timedelta(
                days=self.cooling_off_days
            )
            portfolio_cooling_off = True

        # Check symbol-level drawdown and cooling off
        symbol_status = {}
        for symbol, value in symbol_values.items():
            # Update symbol peak
            if symbol not in self.symbol_peaks:
                self.symbol_peaks[symbol] = value
            else:
                self.symbol_peaks[symbol] = max(self.symbol_peaks[symbol], value)

            # Calculate symbol drawdown
            symbol_drawdown = 0.0
            if self.symbol_peaks[symbol] > 0:
                symbol_drawdown = (
                    self.symbol_peaks[symbol] - value
                ) / self.symbol_peaks[symbol]

            # Check symbol cooling off
            symbol_cooling_off = False
            if (
                symbol in self.cooling_off_until
                and current_time < self.cooling_off_until[symbol]
            ):
                symbol_cooling_off = True

            # Set new cooling off period if max drawdown exceeded
            if (
                symbol_drawdown > self.per_symbol_drawdown_pct
                and not symbol_cooling_off
            ):
                self.cooling_off_until[symbol] = current_time + timedelta(
                    days=self.cooling_off_days
                )
                symbol_cooling_off = True

            # Store symbol status
            symbol_status[symbol] = {
                "drawdown": symbol_drawdown,
                "cooling_off": symbol_cooling_off,
                "reduction_factor": (
                    self.reduction_factor if symbol_cooling_off else 1.0
                ),
            }

        return {
            "portfolio_drawdown": portfolio_drawdown,
            "portfolio_cooling_off": portfolio_cooling_off,
            "portfolio_reduction_factor": (
                self.reduction_factor if portfolio_cooling_off else 1.0
            ),
            "symbol_status": symbol_status,
        }

    def get_position_adjustment(
        self,
        symbol: str,
        position_size: float,
        current_time: datetime,
    ) -> float:
        """Get position size adjustment based on drawdown control.

        Args:
            symbol: Symbol.
            position_size: Calculated position size.
            current_time: Current time.

        Returns:
            Adjusted position size.
        """
        # Check portfolio-level cooling off
        if (
            self.portfolio_cooling_off_until
            and current_time < self.portfolio_cooling_off_until
        ):
            position_size *= self.reduction_factor

        # Check symbol-level cooling off
        if (
            symbol in self.cooling_off_until
            and current_time < self.cooling_off_until[symbol]
        ):
            position_size *= self.reduction_factor

        return position_size

    def reset(self) -> None:
        """Reset drawdown control."""
        self.portfolio_peak = 0.0
        self.symbol_peaks.clear()
        self.cooling_off_until.clear()
        self.portfolio_cooling_off_until = None


class RiskManager:
    """Comprehensive risk manager.

    Combines position sizing, stop-loss management, and drawdown control.
    """

    def __init__(
        self,
        position_sizer: Optional[PositionSizer] = None,
        stop_loss_manager: Optional[StopLossManager] = None,
        drawdown_control: Optional[DrawdownControl] = None,
        max_positions: int = 10,
        max_correlated_positions: int = 3,
        correlation_threshold: float = 0.7,
        leverage_limit: float = 2.0,
        risk_per_trade_pct: float = 0.01,
        max_risk_per_day_pct: float = 0.03,
        news_filter=None,
        avoid_high_impact_news: bool = True,
    ):
        """Initialize the risk manager.

        Args:
            position_sizer: Position sizing algorithm.
            stop_loss_manager: Stop-loss manager.
            drawdown_control: Drawdown control.
            max_positions: Maximum number of open positions.
            max_correlated_positions: Maximum correlated positions.
            correlation_threshold: Correlation threshold.
            leverage_limit: Maximum leverage.
            risk_per_trade_pct: Maximum risk per trade.
            max_risk_per_day_pct: Maximum risk per day.
            news_filter: Filter for avoiding trading during major news events.
            avoid_high_impact_news: Whether to avoid trading during high-impact news events.
        """
        self.position_sizer = position_sizer or VolatilityPositionSizer()
        self.stop_loss_manager = stop_loss_manager or StopLossManager()
        self.drawdown_control = drawdown_control or DrawdownControl()
        self.max_positions = max_positions
        self.max_correlated_positions = max_correlated_positions
        self.correlation_threshold = correlation_threshold
        self.leverage_limit = leverage_limit
        self.risk_per_trade_pct = risk_per_trade_pct
        self.max_risk_per_day_pct = max_risk_per_day_pct
        self.daily_risk_used = 0.0
        self.last_risk_reset = datetime.now()
        self.correlation_matrix: Optional[pd.DataFrame] = None

        # News event filtering
        try:
            # Import here to avoid circular imports
            from fxml4.backtesting.news_filter import IntegratedNewsFilter

            # Initialize news filter if not provided
            self.news_filter = news_filter or IntegratedNewsFilter(
                high_impact_only=True,
                event_buffer_before=120,  # 2 hours before event
                event_buffer_after=60,  # 1 hour after event
                currency_specific=True,
            )
            self.avoid_high_impact_news = avoid_high_impact_news
            # Try to update calendars on initialization
            if self.avoid_high_impact_news:
                self.news_filter.update_calendars()
        except (ImportError, Exception) as e:
            logger.warning(f"News filter initialization failed: {e}")
            self.news_filter = None
            self.avoid_high_impact_news = False

    def process_signal(
        self,
        signal: SignalEvent,
        portfolio: Any,
        current_time: datetime,
    ) -> Tuple[Optional[OrderEvent], Optional[OrderEvent]]:
        """Process a signal and apply risk management rules.

        Args:
            signal: Signal event.
            portfolio: Portfolio instance.
            current_time: Current time.

        Returns:
            Tuple of (main_order, stop_order).
        """
        # Skip if we've reached max positions
        if (
            len(portfolio.positions) >= self.max_positions
            and signal.signal_type == "entry"
        ):
            logger.info(
                "Skipping signal: maximum positions reached (%d)", self.max_positions
            )
            return None, None

        # Update daily risk usage
        self._update_daily_risk(current_time)

        # Get current price
        symbol = signal.symbol
        current_price = self._get_current_price(symbol, portfolio)
        if current_price <= 0:
            logger.warning("Invalid current price: %.2f", current_price)
            return None, None

        # Check for news events and abnormal spreads
        if (
            self.avoid_high_impact_news
            and self.news_filter
            and signal.signal_type == "entry"
        ):
            current_bar = portfolio.current_bars.get(symbol)
            market_data = portfolio.market_data.get(symbol)

            is_news_time, events, reason = self.news_filter.is_news_event_time(
                current_time, symbol, current_bar, market_data
            )

            if is_news_time:
                event_names = ", ".join([e["title"] for e in events])
                if reason == "abnormal_spread":
                    logger.info(
                        f"Skipping signal: abnormal spread detected [{event_names}]"
                    )
                else:
                    logger.info(
                        f"Skipping signal: high impact news event(s) [{event_names}]"
                    )
                return None, None

        # Apply drawdown control
        portfolio_value = portfolio.equity
        symbol_values = {
            s: pos["current_value"] for s, pos in portfolio.positions.items()
        }
        drawdown_status = self.drawdown_control.check_drawdown(
            portfolio_value, symbol_values, current_time
        )

        # Entry signal
        if signal.signal_type == "entry":
            # Check if we already have a position in this symbol
            if symbol in portfolio.positions:
                logger.info(
                    "Skipping entry signal: position already exists for %s", symbol
                )
                return None, None

            # Check correlation limits
            if not self._check_correlation_limits(symbol, portfolio):
                logger.info(
                    "Skipping entry signal: correlation limits reached for %s", symbol
                )
                return None, None

            # Check leverage limits
            if not self._check_leverage_limits(portfolio, signal, current_price):
                logger.info("Skipping entry signal: leverage limit reached")
                return None, None

            # Calculate position size
            quantity = self.position_sizer.calculate_position_size(
                signal, portfolio, current_price
            )

            # Apply drawdown control adjustment
            quantity = self.drawdown_control.get_position_adjustment(
                symbol, quantity, current_time
            )

            # Apply daily risk limit
            risk_amount = self._calculate_risk_amount(
                signal, portfolio, current_price, quantity
            )
            if risk_amount / portfolio.equity > self.risk_per_trade_pct:
                logger.info("Reducing position size: risk per trade limit exceeded")
                quantity = quantity * (
                    self.risk_per_trade_pct * portfolio.equity / risk_amount
                )

            if (
                self.daily_risk_used + risk_amount / portfolio.equity
                > self.max_risk_per_day_pct
            ):
                logger.info("Skipping entry signal: daily risk limit reached")
                return None, None

            self.daily_risk_used += risk_amount / portfolio.equity

            # Create main order
            if quantity <= 0:
                logger.warning("Invalid position size: %.2f", quantity)
                return None, None

            main_order = OrderEvent(
                timestamp=current_time,
                order_id=f"order-{uuid.uuid4()}",
                symbol=symbol,
                order_type=signal.signal_data.get("order_type", "market"),
                side=signal.signal_data.get("side", "buy"),
                quantity=quantity,
                price=signal.signal_data.get("price"),
                stop_price=signal.signal_data.get("stop_price"),
                limit_price=signal.signal_data.get("limit_price"),
                time_in_force=signal.signal_data.get("time_in_force", "GTC"),
                signal_id=str(id(signal)),
                additional_params=signal.signal_data.get("additional_params", {}),
            )

            # Create stop-loss order if applicable
            stop_order = self.stop_loss_manager.create_stop_loss(
                signal,
                current_price,
                current_time,
                main_order.order_id,
                portfolio.market_data.get(symbol),
            )

            return main_order, stop_order

        # Exit signal
        elif signal.signal_type == "exit":
            # Check if we have a position to exit
            if symbol not in portfolio.positions:
                logger.info("Skipping exit signal: no position for %s", symbol)
                return None, None

            position = portfolio.positions[symbol]

            # Create exit order
            main_order = OrderEvent(
                timestamp=current_time,
                order_id=f"exit-{uuid.uuid4()}",
                symbol=symbol,
                order_type=signal.signal_data.get("order_type", "market"),
                side="sell" if position["side"] == "buy" else "buy",
                quantity=position["size"],
                price=signal.signal_data.get("price"),
                stop_price=signal.signal_data.get("stop_price"),
                limit_price=signal.signal_data.get("limit_price"),
                time_in_force=signal.signal_data.get("time_in_force", "GTC"),
                signal_id=str(id(signal)),
                additional_params=signal.signal_data.get("additional_params", {}),
            )

            # Remove any existing stop-loss orders
            self.stop_loss_manager.remove_stop(position.get("position_id", symbol))

            return main_order, None

        return None, None

    def update_risk_controls(
        self,
        portfolio: Any,
        current_time: datetime,
    ) -> List[OrderEvent]:
        """Update risk controls based on current portfolio state.

        Args:
            portfolio: Portfolio instance.
            current_time: Current time.

        Returns:
            List of orders generated by risk controls.
        """
        # Get current prices
        current_prices = {
            symbol: portfolio.current_bars[symbol]["close"]
            for symbol in portfolio.positions
            if symbol in portfolio.current_bars
        }

        # Update stop-loss orders
        stop_orders = self.stop_loss_manager.update_stops(current_prices, current_time)

        # Update drawdown controls
        symbol_values = {
            s: pos["current_value"] for s, pos in portfolio.positions.items()
        }
        self.drawdown_control.check_drawdown(
            portfolio.equity, symbol_values, current_time
        )

        # Check for news events and generate exit orders if needed
        if self.avoid_high_impact_news and self.news_filter:
            news_exit_orders = self._check_news_events(portfolio, current_time)
            stop_orders.extend(news_exit_orders)

        # Reset daily risk if needed
        self._update_daily_risk(current_time)

        return stop_orders

    def _check_news_events(
        self, portfolio: Any, current_time: datetime
    ) -> List[OrderEvent]:
        """Check for news events and generate exit orders if needed.

        Args:
            portfolio: Portfolio instance.
            current_time: Current time.

        Returns:
            List of exit orders for positions affected by news events.
        """
        if not self.news_filter:
            return []

        exit_orders = []

        # Check each open position
        for symbol, position in portfolio.positions.items():
            # Get current bar and market data for spread analysis
            current_bar = portfolio.current_bars.get(symbol)
            market_data = portfolio.market_data.get(symbol)

            # Check for news events or abnormal spreads
            is_news_time, events, reason = self.news_filter.is_news_event_time(
                current_time, symbol, current_bar, market_data
            )

            if is_news_time:
                event_names = ", ".join([e["title"] for e in events])

                # Log appropriate reason
                if reason == "abnormal_spread":
                    logger.info(
                        f"Exiting position for {symbol} due to abnormal spread: {event_names}"
                    )
                elif reason == "economic_release":
                    logger.info(
                        f"Exiting position for {symbol} due to economic release: {event_names}"
                    )
                else:
                    logger.info(
                        f"Exiting position for {symbol} due to news event(s): {event_names}"
                    )

                # Create exit order
                exit_order = OrderEvent(
                    timestamp=current_time,
                    order_id=f"news-exit-{uuid.uuid4()}",
                    symbol=symbol,
                    order_type="market",
                    side="sell" if position["side"] == "buy" else "buy",
                    quantity=position["size"],
                    price=None,
                    stop_price=None,
                    limit_price=None,
                    time_in_force="IOC",
                    parent_order_id=position.get("position_id", symbol),
                    signal_id=None,
                    additional_params={"reason": reason or "news_event"},
                )

                exit_orders.append(exit_order)

                # Remove any existing stop-loss orders
                self.stop_loss_manager.remove_stop(position.get("position_id", symbol))

        return exit_orders

    def _update_daily_risk(self, current_time: datetime) -> None:
        """Update daily risk usage.

        Args:
            current_time: Current time.
        """
        # Reset daily risk at the start of a new day
        if current_time.date() > self.last_risk_reset.date():
            self.daily_risk_used = 0.0
            self.last_risk_reset = current_time

    def _get_current_price(self, symbol: str, portfolio: Any) -> float:
        """Get current price for a symbol.

        Args:
            symbol: Symbol.
            portfolio: Portfolio instance.

        Returns:
            Current price.
        """
        if symbol in portfolio.current_bars:
            return portfolio.current_bars[symbol]["close"]

        # Try to find in market data
        market_data = portfolio.market_data.get(symbol)
        if market_data is not None and not market_data.empty:
            return market_data["close"].iloc[-1]

        return 0.0

    def _check_correlation_limits(self, symbol: str, portfolio: Any) -> bool:
        """Check correlation limits for a new position.

        Args:
            symbol: Symbol for new position.
            portfolio: Portfolio instance.

        Returns:
            True if correlation limits allow the position, False otherwise.
        """
        if not portfolio.positions:
            return True

        # Update correlation matrix if needed
        self._update_correlation_matrix(portfolio)

        if (
            self.correlation_matrix is None
            or symbol not in self.correlation_matrix.columns
        ):
            return True

        # Count existing correlated positions
        correlated_count = 0
        for existing_symbol in portfolio.positions:
            if existing_symbol in self.correlation_matrix.columns:
                correlation = self.correlation_matrix.loc[symbol, existing_symbol]
                if abs(correlation) >= self.correlation_threshold:
                    correlated_count += 1

        return correlated_count < self.max_correlated_positions

    def _update_correlation_matrix(self, portfolio: Any) -> None:
        """Update correlation matrix based on market data.

        Args:
            portfolio: Portfolio instance.
        """
        # Collect price data for all symbols
        price_data = {}
        for symbol, data in portfolio.market_data.items():
            if not data.empty and "close" in data.columns:
                price_data[symbol] = data["close"]

        if not price_data:
            return

        # Create price DataFrame
        prices_df = pd.DataFrame(price_data)

        # Calculate correlation matrix
        if len(prices_df.columns) > 1:
            self.correlation_matrix = prices_df.corr()

    def _check_leverage_limits(
        self,
        portfolio: Any,
        signal: SignalEvent,
        current_price: float,
    ) -> bool:
        """Check leverage limits for a new position.

        Args:
            portfolio: Portfolio instance.
            signal: Signal event.
            current_price: Current price.

        Returns:
            True if leverage limits allow the position, False otherwise.
        """
        # Calculate current leverage
        total_position_value = sum(
            pos["current_value"] for pos in portfolio.positions.values()
        )
        current_leverage = (
            total_position_value / portfolio.equity if portfolio.equity > 0 else 0
        )

        # Estimate new position value
        position_size = self.position_sizer.calculate_position_size(
            signal, portfolio, current_price
        )
        new_position_value = position_size * current_price

        # Calculate new leverage
        new_leverage = (
            (total_position_value + new_position_value) / portfolio.equity
            if portfolio.equity > 0
            else 0
        )

        return new_leverage <= self.leverage_limit

    def _calculate_risk_amount(
        self,
        signal: SignalEvent,
        portfolio: Any,
        current_price: float,
        quantity: float,
    ) -> float:
        """Calculate risk amount for a trade.

        Args:
            signal: Signal event.
            portfolio: Portfolio instance.
            current_price: Current price.
            quantity: Position size.

        Returns:
            Risk amount in currency units.
        """
        # If stop loss is provided in signal, use it
        if "stop_loss" in signal.signal_data:
            stop_price = signal.signal_data["stop_loss"]
            risk_per_unit = abs(current_price - stop_price)
            return risk_per_unit * quantity

        # Otherwise use a default risk percentage
        return current_price * quantity * self.risk_per_trade_pct

    def reset(self) -> None:
        """Reset risk manager."""
        self.stop_loss_manager.stop_orders.clear()
        self.drawdown_control.reset()
        self.daily_risk_used = 0.0
        self.last_risk_reset = datetime.now()
        self.correlation_matrix = None


class PortfolioRiskMetrics:
    """Portfolio-level risk metrics calculator."""

    def __init__(
        self,
        lookback_days: int = 90,
        benchmark_symbol: Optional[str] = None,
        risk_free_rate: float = 0.0,
        calculation_frequency: str = "daily",
    ):
        """Initialize portfolio risk metrics calculator.

        Args:
            lookback_days: Lookback period for calculations.
            benchmark_symbol: Symbol to use as benchmark.
            risk_free_rate: Risk-free rate for Sharpe/Sortino calculations.
            calculation_frequency: How often to calculate metrics ('daily', 'weekly', etc.).
        """
        self.lookback_days = lookback_days
        self.benchmark_symbol = benchmark_symbol
        self.risk_free_rate = risk_free_rate
        self.calculation_frequency = calculation_frequency
        self.metrics_history: List[Dict[str, Any]] = []
        self.last_calculation: Optional[datetime] = None

    def calculate_metrics(
        self,
        portfolio: Any,
        current_time: datetime,
    ) -> Dict[str, Any]:
        """Calculate portfolio risk metrics.

        Args:
            portfolio: Portfolio instance.
            current_time: Current time.

        Returns:
            Dict of risk metrics.
        """
        # Check if we need to calculate metrics
        if self.last_calculation and not self._should_calculate(current_time):
            # Return the most recent metrics
            return self.metrics_history[-1] if self.metrics_history else {}

        self.last_calculation = current_time

        # Get equity curve
        equity_curve = portfolio.get_equity_curve()
        if equity_curve.empty:
            return {}

        # Calculate return metrics
        returns = equity_curve["equity"].pct_change().dropna()
        if len(returns) < 2:
            return {}

        # Calculate benchmark returns if available
        benchmark_returns = None
        if self.benchmark_symbol and self.benchmark_symbol in portfolio.market_data:
            benchmark_data = portfolio.market_data[self.benchmark_symbol]
            if not benchmark_data.empty and "close" in benchmark_data.columns:
                benchmark_returns = benchmark_data["close"].pct_change().dropna()

        # Basic metrics
        annualization_factor = 252  # Trading days in a year

        metrics = {
            "timestamp": current_time,
            "equity": equity_curve["equity"].iloc[-1],
            "returns": returns.tolist(),  # Store for historical analysis
            "return_stats": {
                "mean": returns.mean(),
                "std": returns.std(),
                "min": returns.min(),
                "max": returns.max(),
            },
            "sharpe_ratio": self._calculate_sharpe_ratio(returns, annualization_factor),
            "sortino_ratio": self._calculate_sortino_ratio(
                returns, annualization_factor
            ),
            "drawdown": self._calculate_drawdown(equity_curve["equity"]),
            "var_95": self._calculate_var(returns, 0.95),  # 95% Value at Risk
            "var_99": self._calculate_var(returns, 0.99),  # 99% Value at Risk
            "cvar_95": self._calculate_cvar(returns, 0.95),  # 95% Conditional VaR
        }

        # Calculate beta and alpha if benchmark is available
        if benchmark_returns is not None and len(benchmark_returns) > 0:
            metrics.update(
                self._calculate_benchmark_metrics(returns, benchmark_returns)
            )

        # Calculate portfolio-level risk exposure
        metrics.update(self._calculate_risk_exposure(portfolio))

        # Store metrics history
        self.metrics_history.append(metrics)

        # Trim history to lookback period
        lookback_timestamp = current_time - timedelta(days=self.lookback_days)
        self.metrics_history = [
            m for m in self.metrics_history if m["timestamp"] >= lookback_timestamp
        ]

        return metrics

    def _should_calculate(self, current_time: datetime) -> bool:
        """Determine if metrics should be calculated.

        Args:
            current_time: Current time.

        Returns:
            True if metrics should be calculated, False otherwise.
        """
        if not self.last_calculation:
            return True

        if self.calculation_frequency == "daily":
            return current_time.date() > self.last_calculation.date()
        elif self.calculation_frequency == "weekly":
            # Calculate once per week
            days_diff = (current_time.date() - self.last_calculation.date()).days
            return days_diff >= 7
        elif self.calculation_frequency == "monthly":
            # Calculate once per month
            return (current_time.year, current_time.month) > (
                self.last_calculation.year,
                self.last_calculation.month,
            )

        # Default: calculate every time
        return True

    def _calculate_sharpe_ratio(
        self,
        returns: pd.Series,
        annualization_factor: int = 252,
    ) -> float:
        """Calculate Sharpe ratio.

        Args:
            returns: Return series.
            annualization_factor: Annualization factor (e.g., 252 for daily).

        Returns:
            Sharpe ratio.
        """
        if returns.std() == 0:
            return 0.0

        sharpe = (
            returns.mean() - self.risk_free_rate / annualization_factor
        ) / returns.std()
        return sharpe * np.sqrt(annualization_factor)

    def _calculate_sortino_ratio(
        self,
        returns: pd.Series,
        annualization_factor: int = 252,
    ) -> float:
        """Calculate Sortino ratio.

        Args:
            returns: Return series.
            annualization_factor: Annualization factor (e.g., 252 for daily).

        Returns:
            Sortino ratio.
        """
        downside_returns = returns[returns < 0]
        if len(downside_returns) == 0 or downside_returns.std() == 0:
            return 0.0

        sortino = (
            returns.mean() - self.risk_free_rate / annualization_factor
        ) / downside_returns.std()
        return sortino * np.sqrt(annualization_factor)

    def _calculate_drawdown(self, equity: pd.Series) -> Dict[str, float]:
        """Calculate drawdown metrics.

        Args:
            equity: Equity series.

        Returns:
            Dict of drawdown metrics.
        """
        max_equity = equity.cummax()
        drawdown = (equity - max_equity) / max_equity

        return {
            "current": drawdown.iloc[-1],
            "max": drawdown.min(),
            "avg": drawdown.mean(),
        }

    def _calculate_var(self, returns: pd.Series, percentile: float = 0.95) -> float:
        """Calculate Value at Risk (VaR).

        Args:
            returns: Return series.
            percentile: VaR percentile (e.g., 0.95 for 95% VaR).

        Returns:
            VaR value.
        """
        return abs(np.percentile(returns, 100 * (1 - percentile)))

    def _calculate_cvar(self, returns: pd.Series, percentile: float = 0.95) -> float:
        """Calculate Conditional Value at Risk (CVaR).

        Args:
            returns: Return series.
            percentile: CVaR percentile (e.g., 0.95 for 95% CVaR).

        Returns:
            CVaR value.
        """
        var = self._calculate_var(returns, percentile)
        cvar_returns = returns[returns <= -var]

        if len(cvar_returns) == 0:
            return var

        return abs(cvar_returns.mean())

    def _calculate_benchmark_metrics(
        self,
        returns: pd.Series,
        benchmark_returns: pd.Series,
    ) -> Dict[str, Any]:
        """Calculate benchmark-relative metrics.

        Args:
            returns: Portfolio return series.
            benchmark_returns: Benchmark return series.

        Returns:
            Dict of benchmark metrics.
        """
        # Align return series
        common_index = returns.index.intersection(benchmark_returns.index)
        if len(common_index) < 2:
            return {}

        portfolio_returns = returns.loc[common_index]
        benchmark_returns = benchmark_returns.loc[common_index]

        # Calculate beta
        cov = np.cov(portfolio_returns, benchmark_returns)[0, 1]
        var = np.var(benchmark_returns)
        beta = cov / var if var > 0 else 0

        # Calculate alpha (Jensen's Alpha)
        alpha = portfolio_returns.mean() - (
            self.risk_free_rate
            + beta * (benchmark_returns.mean() - self.risk_free_rate)
        )

        # Calculate information ratio
        tracking_error = (portfolio_returns - benchmark_returns).std()
        information_ratio = (
            (portfolio_returns.mean() - benchmark_returns.mean()) / tracking_error
            if tracking_error > 0
            else 0
        )

        # Calculate correlation
        correlation = portfolio_returns.corr(benchmark_returns)

        # Calculate up/down capture
        up_market = benchmark_returns > 0
        down_market = benchmark_returns < 0

        up_capture = (
            (portfolio_returns[up_market].mean() / benchmark_returns[up_market].mean())
            if up_market.any() and benchmark_returns[up_market].mean() != 0
            else 0
        )
        down_capture = (
            (
                portfolio_returns[down_market].mean()
                / benchmark_returns[down_market].mean()
            )
            if down_market.any() and benchmark_returns[down_market].mean() != 0
            else 0
        )

        return {
            "beta": beta,
            "alpha": alpha,
            "information_ratio": information_ratio,
            "correlation": correlation,
            "up_capture": up_capture,
            "down_capture": down_capture,
            "active_return": portfolio_returns.mean() - benchmark_returns.mean(),
        }

    def _calculate_risk_exposure(self, portfolio: Any) -> Dict[str, Any]:
        """Calculate portfolio risk exposure metrics.

        Args:
            portfolio: Portfolio instance.

        Returns:
            Dict of risk exposure metrics.
        """
        # Calculate allocation by symbol
        positions = portfolio.get_current_positions()
        total_value = sum(pos.get("current_value", 0) for pos in positions.values())

        if total_value == 0:
            return {
                "leverage": 0.0,
                "concentration": 0.0,
                "long_exposure": 0.0,
                "short_exposure": 0.0,
                "net_exposure": 0.0,
                "gross_exposure": 0.0,
            }

        # Calculate long and short exposure
        long_value = sum(
            pos.get("current_value", 0)
            for pos in positions.values()
            if pos.get("side") == "buy"
        )
        short_value = sum(
            pos.get("current_value", 0)
            for pos in positions.values()
            if pos.get("side") == "sell"
        )

        # Calculate exposure metrics
        net_exposure = (long_value - short_value) / portfolio.equity
        gross_exposure = (long_value + short_value) / portfolio.equity
        long_exposure = long_value / portfolio.equity
        short_exposure = short_value / portfolio.equity

        # Calculate concentration (Herfindahl-Hirschman Index)
        if not positions:
            concentration = 0.0
        else:
            weights = [
                (pos.get("current_value", 0) / total_value) ** 2
                for pos in positions.values()
            ]
            concentration = sum(weights)

        return {
            "leverage": gross_exposure,
            "concentration": concentration,
            "long_exposure": long_exposure,
            "short_exposure": short_exposure,
            "net_exposure": net_exposure,
            "gross_exposure": gross_exposure,
        }

    def get_historical_metrics(self) -> pd.DataFrame:
        """Get historical metrics as a DataFrame.

        Returns:
            DataFrame of historical metrics.
        """
        if not self.metrics_history:
            return pd.DataFrame()

        # Extract basic fields
        metrics_df = pd.DataFrame(
            [
                {
                    "timestamp": m["timestamp"],
                    "equity": m["equity"],
                    "sharpe_ratio": m["sharpe_ratio"],
                    "sortino_ratio": m["sortino_ratio"],
                    "max_drawdown": m["drawdown"]["max"],
                    "var_95": m["var_95"],
                    "leverage": m.get("leverage", 0),
                    "net_exposure": m.get("net_exposure", 0),
                }
                for m in self.metrics_history
            ]
        )

        return metrics_df
