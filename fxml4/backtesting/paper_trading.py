"""Paper Trading Engine for FXML4.

This module implements a paper trading engine that connects to Interactive Brokers,
processes real-time data, generates trading signals, and executes trades.
"""

import logging
import queue
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from fxml4.backtesting.event import FillEvent, MarketEvent, OrderEvent, SignalEvent
from fxml4.backtesting.market_impact import SlippageModel
from fxml4.backtesting.risk_management import RiskManager
from fxml4.data_engineering.data_feeds.ib_feed import IBDataFeed
from fxml4.data_engineering.tick_to_candle import TickAggregator
from fxml4.data_engineering.timeframe_conversion import TimeframeConverter

logger = logging.getLogger(__name__)


class PaperTradingEngine:
    """Paper trading engine that connects to Interactive Brokers.

    This class implements a paper trading engine that:
    1. Connects to Interactive Brokers for real-time data
    2. Processes tick data into candles
    3. Generates features and signals
    4. Executes trades with simulated fills
    5. Tracks performance in real-time
    """

    def __init__(self, config: Dict[str, Any]):
        """Initialize the paper trading engine.

        Args:
            config: Configuration dictionary with the following settings:
                symbols: List of symbols to trade
                timeframes: List of timeframes to process
                base_timeframe: Base timeframe for data processing
                signal_timeframe: Timeframe for signal generation
                risk_config: Risk management configuration
                ib_config: Interactive Brokers connection configuration
                signal_generators: List of signal generators to use
                initial_capital: Initial capital for paper trading
                position_size: Position sizing method
                max_positions: Maximum number of concurrent positions
                working_hours: Trading hours configuration
                enable_storage: Whether to store trades and performance in database
        """
        self.config = config
        self.symbols = config.get("symbols", ["EURUSD", "GBPUSD"])
        self.timeframes = config.get(
            "timeframes", ["1m", "5m", "15m", "1h", "4h", "1d"]
        )
        self.base_timeframe = config.get("base_timeframe", "1m")
        self.signal_timeframe = config.get("signal_timeframe", "1h")
        self.initial_capital = config.get("initial_capital", 10000.0)
        self.max_positions = config.get("max_positions", 5)

        # Set up data feed
        ib_config = config.get(
            "ib_config",
            {
                "host": "127.0.0.1",
                "port": 7497,  # Paper trading port
                "client_id": 1,
                "real_time_updates": True,
                "update_interval": 1.0,
                "tick_storage_limit": 10000,
                "candle_storage_days": 7,
            },
        )

        self.data_feed = IBDataFeed(ib_config)

        # Set up timeframe converter
        self.timeframe_converter = TimeframeConverter(
            base_timeframe=self.base_timeframe,
            derived_timeframes=[
                tf for tf in self.timeframes if tf != self.base_timeframe
            ],
        )

        # Set up risk manager
        risk_config = config.get("risk_config", {})
        self.risk_manager = RiskManager(risk_config)

        # Set up slippage model
        slippage_config = config.get("slippage_config", {})
        self.slippage_model = SlippageModel(slippage_config)

        # Signal generators
        self.signal_generators = config.get("signal_generators", [])

        # Portfolio state
        self.portfolio = {
            "cash": self.initial_capital,
            "equity": self.initial_capital,
            "positions": {},
            "trades": [],
            "orders": {},
        }

        # Event queues
        self.market_event_queue = queue.Queue()
        self.signal_event_queue = queue.Queue()
        self.order_event_queue = queue.Queue()
        self.fill_event_queue = queue.Queue()

        # Trading state
        self.is_running = False
        self.last_signal_time = {}
        self.signal_cooldown = config.get("signal_cooldown", 60)  # minutes
        self.last_processed_time = {}

        # Thread management
        self.data_thread = None
        self.signal_thread = None
        self.order_thread = None
        self.fill_thread = None

        # Working hours
        self.working_hours = config.get(
            "working_hours",
            {
                "enabled": False,
                "start_time": "00:00",  # UTC
                "end_time": "23:59",  # UTC
                "weekend_trading": False,
            },
        )

        # Performance tracking
        self.equity_curve = pd.Series(dtype=float)
        self.drawdowns = pd.Series(dtype=float)
        self.trade_history = []

        # Storage settings
        self.enable_storage = config.get("enable_storage", False)
        self.db_client = None

        logger.info(f"Initialized PaperTradingEngine with {len(self.symbols)} symbols")

    def connect(self) -> bool:
        """Connect to Interactive Brokers.

        Returns:
            True if connection was successful, False otherwise
        """
        try:
            # Connect to IB
            if not self.data_feed.connect():
                logger.error("Failed to connect to Interactive Brokers")
                return False

            # Subscribe to market data for all symbols
            logger.info(f"Subscribing to market data for {len(self.symbols)} symbols")
            for symbol in self.symbols:
                self.data_feed.subscribe_market_data(symbol)

            # Initialize database connection if storage is enabled
            if self.enable_storage:
                self._init_storage()

            # Wait for initial data to arrive
            time.sleep(5.0)
            logger.info(f"Successfully connected to Interactive Brokers")

            # Fetch historical data for initial signal calculation
            self._fetch_initial_data()

            return True

        except Exception as e:
            logger.error(f"Error connecting to Interactive Brokers: {e}")
            return False

    def disconnect(self):
        """Disconnect from Interactive Brokers."""
        try:
            self.data_feed.disconnect()
            logger.info("Disconnected from Interactive Brokers")
        except Exception as e:
            logger.error(f"Error disconnecting from Interactive Brokers: {e}")

    def start(self):
        """Start the paper trading engine."""
        if self.is_running:
            logger.warning("Paper trading engine is already running")
            return

        # Connect to IB if not already connected
        if not hasattr(self.data_feed, "app") or not self.data_feed.app.connected:
            if not self.connect():
                logger.error(
                    "Failed to connect to Interactive Brokers, cannot start paper trading engine"
                )
                return

        # Set running flag
        self.is_running = True

        # Start processing threads
        self.data_thread = threading.Thread(
            target=self._process_market_data, daemon=True
        )
        self.signal_thread = threading.Thread(target=self._process_signals, daemon=True)
        self.order_thread = threading.Thread(target=self._process_orders, daemon=True)
        self.fill_thread = threading.Thread(target=self._process_fills, daemon=True)

        self.data_thread.start()
        self.signal_thread.start()
        self.order_thread.start()
        self.fill_thread.start()

        logger.info("Paper trading engine started")

    def stop(self):
        """Stop the paper trading engine."""
        if not self.is_running:
            logger.warning("Paper trading engine is not running")
            return

        # Clear the running flag - threads will exit on next iteration
        self.is_running = False

        # Wait for threads to terminate
        if self.data_thread:
            self.data_thread.join(timeout=5.0)
        if self.signal_thread:
            self.signal_thread.join(timeout=5.0)
        if self.order_thread:
            self.order_thread.join(timeout=5.0)
        if self.fill_thread:
            self.fill_thread.join(timeout=5.0)

        # Disconnect from IB
        self.disconnect()

        logger.info("Paper trading engine stopped")

    def get_portfolio_status(self) -> Dict[str, Any]:
        """Get the current portfolio status.

        Returns:
            Dictionary containing portfolio status
        """
        current_time = datetime.now(timezone.utc)

        # Update positions with current market prices
        for symbol, position in self.portfolio["positions"].items():
            latest_tick = self.data_feed.get_latest_tick(symbol)

            if latest_tick and "bid" in latest_tick and "ask" in latest_tick:
                # Use mid price for valuation
                mid_price = (latest_tick["bid"] + latest_tick["ask"]) / 2.0

                # Update position value
                if position["direction"] == "LONG":
                    position["current_price"] = mid_price
                    position["current_value"] = position["size"] * mid_price
                    position["unrealized_pnl"] = position["size"] * (
                        mid_price - position["entry_price"]
                    )
                else:
                    position["current_price"] = mid_price
                    position["current_value"] = position["size"] * mid_price
                    position["unrealized_pnl"] = position["size"] * (
                        position["entry_price"] - mid_price
                    )

        # Calculate total equity
        total_position_value = sum(
            [pos["current_value"] for pos in self.portfolio["positions"].values()]
        )
        total_unrealized_pnl = sum(
            [pos["unrealized_pnl"] for pos in self.portfolio["positions"].values()]
        )

        # Update portfolio
        self.portfolio["equity"] = self.portfolio["cash"] + total_position_value
        self.portfolio["timestamp"] = current_time

        # Add to equity curve
        self.equity_curve.loc[current_time] = self.portfolio["equity"]

        # Calculate drawdown
        if not self.equity_curve.empty:
            running_max = self.equity_curve.cummax()
            drawdown = (self.equity_curve / running_max - 1.0) * 100
            self.drawdowns = drawdown

        # Format response
        status = {
            "timestamp": current_time,
            "cash": self.portfolio["cash"],
            "equity": self.portfolio["equity"],
            "unrealized_pnl": total_unrealized_pnl,
            "positions": len(self.portfolio["positions"]),
            "trades_today": sum(
                1
                for trade in self.trade_history
                if (current_time - trade["timestamp"]).total_seconds() < 86400
            ),
            "drawdown": (
                float(self.drawdowns.iloc[-1]) if not self.drawdowns.empty else 0.0
            ),
            "max_drawdown": (
                float(self.drawdowns.min()) if not self.drawdowns.empty else 0.0
            ),
            "positions_detail": self.portfolio["positions"],
        }

        return status

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Calculate and return performance metrics.

        Returns:
            Dictionary containing performance metrics
        """
        if self.equity_curve.empty:
            return {
                "total_return": 0.0,
                "annualized_return": 0.0,
                "sharpe_ratio": 0.0,
                "max_drawdown": 0.0,
                "win_rate": 0.0,
                "profit_factor": 0.0,
                "total_trades": 0,
            }

        # Calculate returns
        returns = self.equity_curve.pct_change().dropna()

        # Filter out flat periods
        returns = returns[returns != 0]

        # Trading days calculation
        if len(returns) > 0:
            first_date = self.equity_curve.index[0]
            last_date = self.equity_curve.index[-1]
            trading_days = (last_date - first_date).days
            if trading_days == 0:
                trading_days = 1

            daily_return = (
                (self.equity_curve.iloc[-1] / self.equity_curve.iloc[0])
                ** (252 / trading_days)
            ) - 1
        else:
            daily_return = 0

        # Calculate metrics
        total_return = (
            ((self.equity_curve.iloc[-1] / self.initial_capital) - 1) * 100
            if len(self.equity_curve) > 0
            else 0
        )

        # Sharpe ratio (annualized, assuming daily returns)
        sharpe_ratio = (
            (returns.mean() / returns.std()) * np.sqrt(252)
            if len(returns) > 0 and returns.std() > 0
            else 0
        )

        # Max drawdown
        max_drawdown = float(self.drawdowns.min()) if not self.drawdowns.empty else 0.0

        # Trade statistics
        closed_trades = [t for t in self.trade_history if t["status"] == "CLOSED"]
        total_trades = len(closed_trades)

        if total_trades > 0:
            winning_trades = sum(1 for t in closed_trades if t["pnl"] > 0)
            win_rate = (winning_trades / total_trades) * 100

            total_profit = sum(t["pnl"] for t in closed_trades if t["pnl"] > 0)
            total_loss = abs(sum(t["pnl"] for t in closed_trades if t["pnl"] <= 0))
            profit_factor = (
                total_profit / total_loss if total_loss > 0 else float("inf")
            )
        else:
            win_rate = 0
            profit_factor = 0

        return {
            "total_return": total_return,
            "annualized_return": daily_return * 100,
            "sharpe_ratio": sharpe_ratio,
            "max_drawdown": max_drawdown,
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "total_trades": total_trades,
            "current_equity": (
                float(self.equity_curve.iloc[-1])
                if not self.equity_curve.empty
                else self.initial_capital
            ),
            "initial_capital": self.initial_capital,
        }

    def _fetch_initial_data(self):
        """Fetch initial historical data for all symbols and timeframes."""
        logger.info("Fetching initial historical data")

        for symbol in self.symbols:
            try:
                # Fetch historical data for signal timeframe
                df = self.data_feed.fetch_data(
                    symbol=symbol,
                    timeframe=self.signal_timeframe,
                    end_date=datetime.now(timezone.utc),
                )

                if not df.empty:
                    logger.info(
                        f"Fetched {len(df)} historical {self.signal_timeframe} bars for {symbol}"
                    )

                    # Initialize timeframe converter with this data
                    if self.timeframe_converter:
                        self.timeframe_converter.update_data(
                            symbol, df, self.signal_timeframe
                        )
                else:
                    logger.warning(f"No historical data available for {symbol}")

            except Exception as e:
                logger.error(f"Error fetching historical data for {symbol}: {e}")

    def _is_trading_active(self) -> bool:
        """Check if trading should be active based on working hours configuration.

        Returns:
            True if trading should be active, False otherwise
        """
        if not self.working_hours.get("enabled", False):
            return True  # Always active if working hours not enabled

        current_time = datetime.now(timezone.utc)

        # Check if it's weekend
        if not self.working_hours.get("weekend_trading", False):
            if current_time.weekday() >= 5:  # 5 = Saturday, 6 = Sunday
                return False

        # Parse working hours
        start_time = datetime.strptime(
            self.working_hours.get("start_time", "00:00"), "%H:%M"
        ).time()
        end_time = datetime.strptime(
            self.working_hours.get("end_time", "23:59"), "%H:%M"
        ).time()

        # Check if current time is within working hours
        current_time_only = current_time.time()

        if start_time <= end_time:
            return start_time <= current_time_only <= end_time
        else:
            # Handle overnight period (e.g., 22:00 - 06:00)
            return start_time <= current_time_only or current_time_only <= end_time

    def _process_market_data(self):
        """Process real-time market data in a background thread."""
        logger.info("Started market data processing thread")

        # Set initial timestamps for all symbols
        for symbol in self.symbols:
            self.last_processed_time[symbol] = {}
            for timeframe in self.timeframes:
                self.last_processed_time[symbol][timeframe] = datetime.now(timezone.utc)

        while self.is_running:
            try:
                # Check if trading is active
                is_active = self._is_trading_active()

                # Process each symbol
                for symbol in self.symbols:
                    # Get latest candles for signal timeframe
                    candles = self.data_feed.get_realtime_candles(
                        symbol=symbol, timeframe=self.signal_timeframe, limit=100
                    )

                    if candles.empty:
                        continue

                    latest_candle_time = candles.index[-1]

                    # Check if we have a new candle
                    if (
                        symbol in self.last_processed_time
                        and self.signal_timeframe in self.last_processed_time[symbol]
                        and latest_candle_time
                        > self.last_processed_time[symbol][self.signal_timeframe]
                    ):

                        # Update last processed time
                        self.last_processed_time[symbol][
                            self.signal_timeframe
                        ] = latest_candle_time

                        # Create market event
                        event = MarketEvent(
                            timestamp=latest_candle_time,
                            symbol=symbol,
                            timeframe=self.signal_timeframe,
                            data=candles,
                        )

                        # Put event in queue
                        self.market_event_queue.put(event)
                        logger.debug(
                            f"Created market event for {symbol} at {latest_candle_time}"
                        )

                # Update portfolio status every minute
                if datetime.now(timezone.utc).second < 5:
                    self.get_portfolio_status()

                    # Save to database if enabled
                    if self.enable_storage and hasattr(self, "db_client"):
                        self._store_portfolio_snapshot()

                # Sleep to avoid high CPU usage
                time.sleep(1.0)

            except Exception as e:
                logger.error(f"Error in market data processing: {e}")
                time.sleep(5.0)

    def _process_signals(self):
        """Process market events and generate signals in a background thread."""
        logger.info("Started signal processing thread")

        while self.is_running:
            try:
                # Check if we have a market event
                try:
                    event = self.market_event_queue.get(timeout=1.0)
                except queue.Empty:
                    continue

                # Skip if trading is not active
                if not self._is_trading_active():
                    logger.debug("Trading not active, skipping signal generation")
                    self.market_event_queue.task_done()
                    continue

                # Process the event
                symbol = event.symbol
                timeframe = event.timeframe
                data = event.data

                # Skip if we don't have enough data
                if len(data) < 30:  # Need enough data for indicators
                    logger.debug(
                        f"Not enough data for {symbol} ({len(data)} bars), skipping signal generation"
                    )
                    self.market_event_queue.task_done()
                    continue

                # Check cooldown period
                current_time = datetime.now(timezone.utc)
                if (
                    symbol in self.last_signal_time
                    and (current_time - self.last_signal_time[symbol]).total_seconds()
                    < self.signal_cooldown * 60
                ):
                    logger.debug(
                        f"Signal cooldown active for {symbol}, skipping signal generation"
                    )
                    self.market_event_queue.task_done()
                    continue

                # Generate signals using all available signal generators
                signals = []
                weights = {}

                for generator in self.signal_generators:
                    try:
                        # Check if generator supports this symbol and timeframe
                        if hasattr(
                            generator, "supports_symbol"
                        ) and not generator.supports_symbol(symbol):
                            continue

                        # Generate signal
                        generator_name = generator.__class__.__name__
                        signal = generator.generate_signal(symbol, data)

                        if signal and signal.signal_type in ["LONG", "SHORT", "EXIT"]:
                            # Store the signal with its weight
                            weight = getattr(generator, "weight", 1.0)
                            signals.append(signal)
                            weights[generator_name] = weight

                            logger.info(
                                f"Generated {signal.signal_type} signal for {symbol} from {generator_name}"
                            )
                    except Exception as e:
                        logger.error(
                            f"Error generating signal with {generator.__class__.__name__}: {e}"
                        )

                # Process combined signals if we have any
                if signals:
                    # Update last signal time
                    self.last_signal_time[symbol] = current_time

                    # Combine signals using weighted approach
                    if len(signals) > 1:
                        combined_signal = self._combine_signals(signals, weights)

                        if combined_signal:
                            self.signal_event_queue.put(combined_signal)
                            logger.info(
                                f"Combined signal {combined_signal.signal_type} for {symbol}"
                            )
                    else:
                        # Just use the single signal
                        self.signal_event_queue.put(signals[0])

                # Mark as done
                self.market_event_queue.task_done()

            except Exception as e:
                logger.error(f"Error in signal processing: {e}")
                time.sleep(1.0)

    def _combine_signals(
        self, signals: List[SignalEvent], weights: Dict[str, float]
    ) -> Optional[SignalEvent]:
        """Combine multiple signals into a single signal using a weighted approach.

        Args:
            signals: List of signal events
            weights: Dictionary of signal generator weights

        Returns:
            Combined signal or None if signals conflict
        """
        if not signals:
            return None

        if len(signals) == 1:
            return signals[0]

        # Extract basic properties from first signal
        symbol = signals[0].symbol
        timestamp = signals[0].timestamp

        # Count signal types with weights
        signal_scores = {"LONG": 0.0, "SHORT": 0.0, "EXIT": 0.0}

        for signal in signals:
            generator_name = signal.generator
            weight = weights.get(generator_name, 1.0)
            signal_scores[signal.signal_type] += weight

        # Normalize to get percentage
        total_weight = sum(signal_scores.values())
        if total_weight > 0:
            for key in signal_scores:
                signal_scores[key] /= total_weight

        # Determine final signal based on threshold
        threshold = 0.6  # 60% agreement needed

        if signal_scores["LONG"] > threshold:
            final_type = "LONG"
        elif signal_scores["SHORT"] > threshold:
            final_type = "SHORT"
        elif signal_scores["EXIT"] > threshold:
            final_type = "EXIT"
        else:
            # No clear consensus
            logger.debug(f"No consensus among signals for {symbol}: {signal_scores}")
            return None

        # Create combined signal
        combined_signal = SignalEvent(
            timestamp=timestamp,
            symbol=symbol,
            signal_type=final_type,
            strength=max(signal_scores.values()),
            generator="CombinedSignal",
        )

        return combined_signal

    def _process_orders(self):
        """Process signal events and generate orders in a background thread."""
        logger.info("Started order processing thread")

        while self.is_running:
            try:
                # Check if we have a signal event
                try:
                    event = self.signal_event_queue.get(timeout=1.0)
                except queue.Empty:
                    continue

                # Process the event
                symbol = event.symbol
                signal_type = event.signal_type

                # Get latest market data
                latest_tick = self.data_feed.get_latest_tick(symbol)
                if (
                    not latest_tick
                    or "bid" not in latest_tick
                    or "ask" not in latest_tick
                ):
                    logger.warning(
                        f"No market data available for {symbol}, skipping order generation"
                    )
                    self.signal_event_queue.task_done()
                    continue

                # Calculate mid price
                mid_price = (latest_tick["bid"] + latest_tick["ask"]) / 2.0

                # Check if we already have a position for this symbol
                has_position = symbol in self.portfolio["positions"]
                position_direction = (
                    self.portfolio["positions"].get(symbol, {}).get("direction", None)
                )

                # Determine order type based on signal and current position
                order_type = None

                if signal_type == "LONG":
                    if not has_position:
                        order_type = "BUY"
                    elif position_direction == "SHORT":
                        order_type = "COVER"  # Close short and go long
                elif signal_type == "SHORT":
                    if not has_position:
                        order_type = "SELL"
                    elif position_direction == "LONG":
                        order_type = "SELL"  # Close long and go short
                elif signal_type == "EXIT":
                    if has_position:
                        if position_direction == "LONG":
                            order_type = "SELL"
                        else:
                            order_type = "COVER"

                if not order_type:
                    logger.debug(
                        f"No order generated for {symbol} signal {signal_type}, position: {position_direction}"
                    )
                    self.signal_event_queue.task_done()
                    continue

                # Check risk constraints
                max_position_size = self._calculate_position_size(
                    symbol, order_type, mid_price
                )

                if max_position_size <= 0:
                    logger.warning(
                        f"Risk constraints prevent order for {symbol} ({order_type})"
                    )
                    self.signal_event_queue.task_done()
                    continue

                # Create order event
                order = OrderEvent(
                    timestamp=datetime.now(timezone.utc),
                    symbol=symbol,
                    order_type=order_type,
                    quantity=max_position_size,
                    price=mid_price,
                )

                # Put order in queue
                self.order_event_queue.put(order)
                logger.info(
                    f"Created {order_type} order for {symbol}: {max_position_size} units at {mid_price:.5f}"
                )

                # Mark as done
                self.signal_event_queue.task_done()

            except Exception as e:
                logger.error(f"Error in order processing: {e}")
                time.sleep(1.0)

    def _calculate_position_size(
        self, symbol: str, order_type: str, price: float
    ) -> float:
        """Calculate position size based on risk management rules.

        Args:
            symbol: Trading symbol
            order_type: Order type (BUY, SELL, COVER)
            price: Current market price

        Returns:
            Position size in units
        """
        # Check if we already have too many positions
        current_positions = len(self.portfolio["positions"])
        if (
            current_positions >= self.max_positions
            and symbol not in self.portfolio["positions"]
        ):
            logger.warning(
                f"Maximum positions limit reached ({self.max_positions}), no new positions allowed"
            )
            return 0.0

        # Get account equity
        equity = self.portfolio["equity"]

        # Get risk per trade (% of equity)
        risk_pct = self.config.get("risk_per_trade", 0.01)  # Default 1%
        risk_amount = equity * risk_pct

        # Get stop loss distance (in pips)
        stop_pips = self.config.get("stop_loss_pips", 50)
        pip_value = 0.0001 if symbol not in ["USDJPY"] else 0.01
        stop_distance = stop_pips * pip_value

        # Calculate position size based on risk and stop distance
        if stop_distance > 0:
            # Convert risk amount to position currency (for Forex)
            position_size = risk_amount / stop_distance

            # Apply leverage constraint if specified
            max_leverage = self.config.get("max_leverage", 20.0)
            max_position_from_leverage = (equity * max_leverage) / price

            # Take the minimum of the two constraints
            position_size = min(position_size, max_position_from_leverage)

            # Round to standard lot sizes (0.01 lots = 1000 units)
            lot_size = 100000  # Standard lot (100k units)
            micro_lot = lot_size / 100  # Micro lot (1k units)
            position_size = round(position_size / micro_lot) * micro_lot

            return position_size
        else:
            return 0.0

    def _process_fills(self):
        """Process order events and generate fills in a background thread."""
        logger.info("Started fill processing thread")

        while self.is_running:
            try:
                # Check if we have an order event
                try:
                    event = self.order_event_queue.get(timeout=1.0)
                except queue.Empty:
                    continue

                # Process the event
                symbol = event.symbol
                order_type = event.order_type
                quantity = event.quantity
                price = event.price

                # Get latest market data for realistic fill price
                latest_tick = self.data_feed.get_latest_tick(symbol)
                if (
                    not latest_tick
                    or "bid" not in latest_tick
                    or "ask" not in latest_tick
                ):
                    logger.warning(
                        f"No market data available for {symbol}, using original price"
                    )
                else:
                    # Use appropriate price based on order type
                    if order_type in ["BUY", "COVER"]:
                        price = latest_tick["ask"]  # Buy at ask
                    else:
                        price = latest_tick["bid"]  # Sell at bid

                # Apply slippage
                fill_price = self.slippage_model.apply_slippage(
                    price, order_type, quantity
                )

                # Create fill event
                fill = FillEvent(
                    timestamp=datetime.now(timezone.utc),
                    symbol=symbol,
                    exchange="FXML_PAPER",
                    quantity=quantity,
                    direction=order_type,
                    fill_price=fill_price,
                    commission=0.0,  # No commission in paper trading
                )

                # Process the fill
                self._process_fill_event(fill)

                # Mark as done
                self.order_event_queue.task_done()

            except Exception as e:
                logger.error(f"Error in fill processing: {e}")
                time.sleep(1.0)

    def _process_fill_event(self, fill: FillEvent):
        """Process a fill event and update the portfolio.

        Args:
            fill: Fill event to process
        """
        symbol = fill.symbol
        direction = fill.direction
        quantity = fill.quantity
        fill_price = fill.fill_price

        # Update portfolio based on fill
        if direction in ["BUY", "COVER"]:
            # Check if we have enough cash
            cost = quantity * fill_price
            if cost > self.portfolio["cash"]:
                logger.warning(
                    f"Insufficient cash for {direction} {symbol}: {cost} > {self.portfolio['cash']}"
                )
                return

            # If this is covering a short position
            if direction == "COVER" and symbol in self.portfolio["positions"]:
                position = self.portfolio["positions"][symbol]
                if position["direction"] == "SHORT":
                    # Calculate P&L
                    entry_price = position["entry_price"]
                    position_size = position["size"]

                    # Only cover what we have
                    cover_size = min(quantity, position_size)

                    # Calculate profit/loss (short profit when entry_price > fill_price)
                    pnl = cover_size * (entry_price - fill_price)

                    # Update position or remove if fully covered
                    if cover_size < position_size:
                        # Partial cover
                        position["size"] -= cover_size
                        logger.info(
                            f"Partially covered {symbol} short: {cover_size} units at {fill_price:.5f}, PnL: {pnl:.2f}"
                        )
                    else:
                        # Full cover
                        del self.portfolio["positions"][symbol]
                        logger.info(
                            f"Fully covered {symbol} short: {cover_size} units at {fill_price:.5f}, PnL: {pnl:.2f}"
                        )

                    # Update cash
                    self.portfolio["cash"] += pnl

                    # Record trade
                    self._record_trade(
                        symbol, "COVER", entry_price, fill_price, cover_size, pnl
                    )

                    # If this is a full position reversal (cover and go long)
                    if cover_size < quantity and direction == "COVER":
                        # Create a new long position with the remainder
                        long_size = quantity - cover_size
                        cost = long_size * fill_price

                        # Create new position
                        self.portfolio["positions"][symbol] = {
                            "direction": "LONG",
                            "size": long_size,
                            "entry_price": fill_price,
                            "entry_time": datetime.now(timezone.utc),
                            "current_price": fill_price,
                            "current_value": long_size * fill_price,
                            "unrealized_pnl": 0.0,
                        }

                        # Update cash
                        self.portfolio["cash"] -= cost

                        logger.info(
                            f"Opened new {symbol} long: {long_size} units at {fill_price:.5f}"
                        )
                else:
                    logger.warning(
                        f"Attempted to cover {symbol} but position is not short"
                    )
            else:
                # New long position
                self.portfolio["positions"][symbol] = {
                    "direction": "LONG",
                    "size": quantity,
                    "entry_price": fill_price,
                    "entry_time": datetime.now(timezone.utc),
                    "current_price": fill_price,
                    "current_value": quantity * fill_price,
                    "unrealized_pnl": 0.0,
                }

                # Update cash
                self.portfolio["cash"] -= cost

                logger.info(
                    f"Opened new {symbol} long: {quantity} units at {fill_price:.5f}"
                )

        elif direction == "SELL":
            # If we're closing a long position
            if symbol in self.portfolio["positions"]:
                position = self.portfolio["positions"][symbol]
                if position["direction"] == "LONG":
                    # Calculate P&L
                    entry_price = position["entry_price"]
                    position_size = position["size"]

                    # Only sell what we have
                    sell_size = min(quantity, position_size)

                    # Calculate profit/loss (long profit when fill_price > entry_price)
                    pnl = sell_size * (fill_price - entry_price)

                    # Update position or remove if fully sold
                    if sell_size < position_size:
                        # Partial sell
                        position["size"] -= sell_size
                        logger.info(
                            f"Partially closed {symbol} long: {sell_size} units at {fill_price:.5f}, PnL: {pnl:.2f}"
                        )
                    else:
                        # Full sell
                        del self.portfolio["positions"][symbol]
                        logger.info(
                            f"Fully closed {symbol} long: {sell_size} units at {fill_price:.5f}, PnL: {pnl:.2f}"
                        )

                    # Update cash (add sale proceeds and profit)
                    self.portfolio["cash"] += sell_size * fill_price

                    # Record trade
                    self._record_trade(
                        symbol, "SELL", entry_price, fill_price, sell_size, pnl
                    )

                    # If this is a full position reversal (sell and go short)
                    if sell_size < quantity:
                        # Create a new short position with the remainder
                        short_size = quantity - sell_size

                        # Create new position
                        self.portfolio["positions"][symbol] = {
                            "direction": "SHORT",
                            "size": short_size,
                            "entry_price": fill_price,
                            "entry_time": datetime.now(timezone.utc),
                            "current_price": fill_price,
                            "current_value": short_size * fill_price,
                            "unrealized_pnl": 0.0,
                        }

                        logger.info(
                            f"Opened new {symbol} short: {short_size} units at {fill_price:.5f}"
                        )
                else:
                    # Position is already short, increase it
                    position["size"] += quantity
                    # For adding to position, use weighted average price
                    position["entry_price"] = (
                        (position["size"] - quantity) * position["entry_price"]
                        + quantity * fill_price
                    ) / position["size"]
                    logger.info(
                        f"Increased {symbol} short position to {position['size']} units, avg price: {position['entry_price']:.5f}"
                    )
            else:
                # New short position
                self.portfolio["positions"][symbol] = {
                    "direction": "SHORT",
                    "size": quantity,
                    "entry_price": fill_price,
                    "entry_time": datetime.now(timezone.utc),
                    "current_price": fill_price,
                    "current_value": quantity * fill_price,
                    "unrealized_pnl": 0.0,
                }

                logger.info(
                    f"Opened new {symbol} short: {quantity} units at {fill_price:.5f}"
                )

        # Update portfolio status
        self.get_portfolio_status()

        # Store fill in database if enabled
        if self.enable_storage and hasattr(self, "db_client"):
            self._store_fill(fill)

    def _record_trade(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        exit_price: float,
        size: float,
        pnl: float,
    ):
        """Record a completed trade.

        Args:
            symbol: Symbol traded
            direction: Trade direction
            entry_price: Entry price
            exit_price: Exit price
            size: Position size
            pnl: Profit/loss
        """
        trade = {
            "timestamp": datetime.now(timezone.utc),
            "symbol": symbol,
            "direction": direction,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "size": size,
            "pnl": pnl,
            "status": "CLOSED",
        }

        self.trade_history.append(trade)

        # Store trade in database if enabled
        if self.enable_storage and hasattr(self, "db_client"):
            self._store_trade(trade)

    def _init_storage(self):
        """Initialize database storage for paper trading results."""
        try:
            from fxml4.config import get_config
            from fxml4.data_engineering.timescaledb import TimescaleDBClient

            # Get TimescaleDB configuration
            config = get_config()
            db_config = config.get("database", {})

            # Initialize TimescaleDB client
            self.db_client = TimescaleDBClient(
                host=db_config.get("host", "localhost"),
                port=db_config.get("port", 5433),
                dbname=db_config.get("name", "fxml4"),
                user=db_config.get("user", "postgres"),
                password=db_config.get("password", "postgres"),
            )

            logger.info("Initialized database storage for paper trading results")
        except Exception as e:
            logger.error(f"Error initializing database storage: {e}")
            self.enable_storage = False

    def _store_portfolio_snapshot(self):
        """Store a snapshot of the current portfolio in the database."""
        if not hasattr(self, "db_client"):
            return

        try:
            status = self.get_portfolio_status()

            # Store in paper_trading_snapshots table
            query = """
                INSERT INTO paper_trading_snapshots
                (timestamp, cash, equity, unrealized_pnl, positions_count, drawdown, max_drawdown)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """

            values = (
                status["timestamp"],
                status["cash"],
                status["equity"],
                status["unrealized_pnl"],
                status["positions"],
                status["drawdown"],
                status["max_drawdown"],
            )

            self.db_client.execute_query(query, values)
            logger.debug("Stored portfolio snapshot in database")
        except Exception as e:
            logger.error(f"Error storing portfolio snapshot: {e}")

    def _store_fill(self, fill: FillEvent):
        """Store a fill event in the database.

        Args:
            fill: Fill event to store
        """
        if not hasattr(self, "db_client"):
            return

        try:
            # Store in paper_trading_fills table
            query = """
                INSERT INTO paper_trading_fills
                (timestamp, symbol, direction, quantity, fill_price, commission)
                VALUES (%s, %s, %s, %s, %s, %s)
            """

            values = (
                fill.timestamp,
                fill.symbol,
                fill.direction,
                fill.quantity,
                fill.fill_price,
                fill.commission,
            )

            self.db_client.execute_query(query, values)
            logger.debug(
                f"Stored fill event in database: {fill.symbol} {fill.direction}"
            )
        except Exception as e:
            logger.error(f"Error storing fill event: {e}")

    def _store_trade(self, trade: Dict[str, Any]):
        """Store a completed trade in the database.

        Args:
            trade: Trade information dictionary
        """
        if not hasattr(self, "db_client"):
            return

        try:
            # Store in paper_trading_trades table
            query = """
                INSERT INTO paper_trading_trades
                (timestamp, symbol, direction, entry_price, exit_price, size, pnl)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """

            values = (
                trade["timestamp"],
                trade["symbol"],
                trade["direction"],
                trade["entry_price"],
                trade["exit_price"],
                trade["size"],
                trade["pnl"],
            )

            self.db_client.execute_query(query, values)
            logger.debug(
                f"Stored trade in database: {trade['symbol']} {trade['pnl']:.2f}"
            )
        except Exception as e:
            logger.error(f"Error storing trade: {e}")
