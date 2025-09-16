"""
Live Data Handler for Interactive Brokers connection.

This module provides a robust service for managing continuous data streams
from Interactive Brokers, with proper connection management, reconnection logic,
and handling of market hours and trading sessions.
"""

import logging
import threading
import time
import queue
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any, Set, Tuple, Callable

import pandas as pd

from fxml4.data_engineering.data_feeds.ib_feed import IBDataFeed
from fxml4.data_engineering.data_feeds.ib_feed import IBAPIApp
from fxml4.data_engineering.tick_to_candle import TickAggregator
from fxml4.data_engineering.timeframe_conversion import TimeframeConverter
from fxml4.config import get_config

# Configure logging
logger = logging.getLogger(__name__)

# Market schedule definitions - times in UTC
MARKET_SCHEDULES = {
    "forex": {
        "sunday_open": "21:00",     # 9 PM UTC Sunday (market opens)
        "friday_close": "21:00",    # 9 PM UTC Friday (market closes)
        "daily_maintenance": {
            "start": "21:55",       # 9:55 PM UTC (5 minutes before daily roll)
            "end": "22:05"          # 10:05 PM UTC (5 minutes after daily roll)
        }
    },
    "us_equities": {
        "regular": {
            "open": "14:30",        # 9:30 AM ET / 14:30 UTC
            "close": "21:00"        # 4:00 PM ET / 21:00 UTC
        },
        "pre_market": {
            "open": "09:00",        # 4:00 AM ET / 09:00 UTC
            "close": "14:30"        # 9:30 AM ET / 14:30 UTC
        },
        "after_market": {
            "open": "21:00",        # 4:00 PM ET / 21:00 UTC
            "close": "01:00"        # 8:00 PM ET / 01:00 UTC next day
        }
    }
}

class ConnectionState:
    """Enum for connection states."""
    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    RECONNECTING = "RECONNECTING"
    ERROR = "ERROR"

class MarketStatus:
    """Enum for market status."""
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    PRE_MARKET = "PRE_MARKET"
    AFTER_MARKET = "AFTER_MARKET"
    MAINTENANCE = "MAINTENANCE"
    WEEKEND = "WEEKEND"
    HOLIDAY = "HOLIDAY"

class LiveDataHandler:
    """
    Live Data Handler for Interactive Brokers connection.
    
    This class manages:
    1. Robust connection to Interactive Brokers
    2. Automatic reconnection logic
    3. Market hours and trading session awareness
    4. Continuous data streaming with error handling
    5. Tick data processing and candle generation
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the Live Data Handler.
        
        Args:
            config: Configuration settings (optional, will load from config file if not provided)
        """
        # Load configuration
        if config is None:
            config = get_config().get("live_data_handler", {})
        
        self.config = config
        
        # IB connection settings
        self.ib_config = config.get("ib_config", {
            "host": "127.0.0.1",
            "port": 7497,  # Paper trading port by default
            "client_id": 1,
            "real_time_updates": True,
            "update_interval": 1.0,
            "tick_storage_limit": 10000,
            "candle_storage_days": 7
        })
        
        # Market settings
        self.market_type = config.get("market_type", "forex")
        self.symbols = config.get("symbols", ["EURUSD", "GBPUSD"])
        self.timeframes = config.get("timeframes", ["1m", "5m", "15m", "1h", "4h", "1d"])
        self.base_timeframe = config.get("base_timeframe", "1m")
        
        # Connection management
        self.max_reconnect_attempts = config.get("max_reconnect_attempts", 5)
        self.reconnect_delay = config.get("reconnect_delay", 30)  # seconds
        self.health_check_interval = config.get("health_check_interval", 60)  # seconds
        self.connection_state = ConnectionState.DISCONNECTED
        self.last_data_time = {}
        self.reconnect_attempts = 0
        self.data_timeout = config.get("data_timeout", 300)  # seconds
        
        # Market hours management
        self.observe_market_hours = config.get("observe_market_hours", True)
        self.current_market_status = MarketStatus.CLOSED
        self.custom_holidays = config.get("holidays", [])
        self.market_schedule = MARKET_SCHEDULES.get(self.market_type, MARKET_SCHEDULES["forex"])
        
        # IB feed and related components
        self.data_feed = None
        self.tick_aggregator = None
        self.timeframe_converter = None
        
        # Threading and event handling
        self.running = False
        self.connection_thread = None
        self.market_hours_thread = None
        self.health_check_thread = None
        self.data_processing_thread = None
        self._lock = threading.Lock()
        
        # Data subscription management
        self.active_subscriptions = set()
        self.pending_subscriptions = queue.Queue()
        self.data_callbacks = {}
        
        # Status notification
        self.status_callbacks = []
        
        # Initialize components
        self._initialize_components()
        
        logger.info(f"LiveDataHandler initialized for market type: {self.market_type}")
    
    def _initialize_components(self):
        """Initialize the core components."""
        # Initialize data feed
        self.data_feed = IBDataFeed(self.ib_config)
        
        # Initialize tick aggregator for candle generation
        from fxml4.data_engineering.tick_to_candle import TickAggregator
        self.tick_aggregator = TickAggregator(
            timeframes=[1, 5, 15, 30, 60, 240, 1440]  # 1m, 5m, 15m, 30m, 1h, 4h, 1d
        )
        
        # Initialize timeframe converter for derived timeframes
        from fxml4.data_engineering.timeframe_conversion import TimeframeConverter
        self.timeframe_converter = TimeframeConverter(
            base_timeframe=self.base_timeframe,
            derived_timeframes=[tf for tf in self.timeframes if tf != self.base_timeframe]
        )
    
    def start(self):
        """Start the Live Data Handler service."""
        if self.running:
            logger.warning("LiveDataHandler is already running")
            return False
        
        self.running = True
        
        # Start connection management thread
        self.connection_thread = threading.Thread(
            target=self._connection_management_loop,
            daemon=True,
            name="IBConnectionManager"
        )
        self.connection_thread.start()
        
        # Start market hours monitoring thread
        self.market_hours_thread = threading.Thread(
            target=self._market_hours_monitoring_loop, 
            daemon=True,
            name="MarketHoursMonitor"
        )
        self.market_hours_thread.start()
        
        # Start health check thread
        self.health_check_thread = threading.Thread(
            target=self._health_check_loop,
            daemon=True,
            name="IBHealthCheck"
        )
        self.health_check_thread.start()
        
        # Start data processing thread
        self.data_processing_thread = threading.Thread(
            target=self._data_processing_loop, 
            daemon=True,
            name="DataProcessor"
        )
        self.data_processing_thread.start()
        
        logger.info("LiveDataHandler service started")
        return True
    
    def stop(self):
        """Stop the Live Data Handler service."""
        if not self.running:
            logger.warning("LiveDataHandler is not running")
            return
        
        self.running = False
        
        # Wait for threads to terminate
        if self.connection_thread:
            self.connection_thread.join(timeout=5.0)
        
        if self.market_hours_thread:
            self.market_hours_thread.join(timeout=5.0)
        
        if self.health_check_thread:
            self.health_check_thread.join(timeout=5.0)
        
        if self.data_processing_thread:
            self.data_processing_thread.join(timeout=5.0)
        
        # Disconnect from IB if connected
        if self.data_feed and hasattr(self.data_feed, 'app') and self.data_feed.app:
            if self.data_feed.app.connected:
                self.data_feed.disconnect()
        
        self.connection_state = ConnectionState.DISCONNECTED
        self._notify_status_change()
        
        logger.info("LiveDataHandler service stopped")
    
    def _connection_management_loop(self):
        """Main loop for connection management."""
        logger.info("Connection management thread started")
        
        while self.running:
            try:
                # If disconnected, try to connect
                if self.connection_state in [ConnectionState.DISCONNECTED, ConnectionState.ERROR]:
                    self._attempt_connection()
                
                # If the market is open and we're connected, check subscriptions
                if (self.connection_state == ConnectionState.CONNECTED and 
                    self._is_market_trading_hours()):
                    self._process_subscription_queue()
                
                # Sleep for a bit
                time.sleep(5.0)
            
            except Exception as e:
                logger.error(f"Error in connection management loop: {e}")
                self.connection_state = ConnectionState.ERROR
                self._notify_status_change()
                time.sleep(self.reconnect_delay)
    
    def _attempt_connection(self):
        """Attempt to connect to Interactive Brokers."""
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            logger.error(f"Maximum reconnection attempts ({self.max_reconnect_attempts}) reached.")
            self.connection_state = ConnectionState.ERROR
            self._notify_status_change()
            return False
        
        logger.info(f"Attempting to connect to IB (attempt {self.reconnect_attempts + 1}/{self.max_reconnect_attempts})")
        self.connection_state = ConnectionState.CONNECTING
        self._notify_status_change()
        
        try:
            # Connect to IB
            if self.data_feed.connect():
                logger.info("Successfully connected to Interactive Brokers")
                self.connection_state = ConnectionState.CONNECTED
                self.reconnect_attempts = 0  # Reset counter on successful connection
                self._notify_status_change()
                
                # Resubscribe to symbols
                self._resubscribe_all()
                
                return True
            else:
                logger.error("Failed to connect to Interactive Brokers")
                self.reconnect_attempts += 1
                self.connection_state = ConnectionState.ERROR
                self._notify_status_change()
                return False
        
        except Exception as e:
            logger.error(f"Error connecting to Interactive Brokers: {e}")
            self.reconnect_attempts += 1
            self.connection_state = ConnectionState.ERROR
            self._notify_status_change()
            return False
    
    def _resubscribe_all(self):
        """Resubscribe to all active symbols."""
        if not self.data_feed or not self.data_feed.app or not self.data_feed.app.connected:
            return
        
        logger.info(f"Resubscribing to {len(self.active_subscriptions)} symbols")
        
        for symbol in self.active_subscriptions:
            try:
                self.data_feed.subscribe_market_data(symbol)
                logger.info(f"Resubscribed to {symbol}")
            except Exception as e:
                logger.error(f"Error resubscribing to {symbol}: {e}")
                # Add to pending queue to retry later
                self.pending_subscriptions.put(symbol)
    
    def _process_subscription_queue(self):
        """Process any pending subscriptions."""
        if not self.data_feed or not self.data_feed.app or not self.data_feed.app.connected:
            return
        
        # Process up to 5 pending subscriptions at once
        for _ in range(5):
            try:
                symbol = self.pending_subscriptions.get_nowait()
                self.data_feed.subscribe_market_data(symbol)
                self.active_subscriptions.add(symbol)
                logger.info(f"Subscribed to {symbol} from pending queue")
            except queue.Empty:
                break
            except Exception as e:
                logger.error(f"Error subscribing to symbol from queue: {e}")
                # Put back in queue to retry
                self.pending_subscriptions.put(symbol)
                break
    
    def _market_hours_monitoring_loop(self):
        """Monitor market hours and update status."""
        logger.info("Market hours monitoring thread started")
        
        last_status = None
        
        while self.running:
            try:
                current_status = self._determine_market_status()
                
                # If status changed, log and notify
                if current_status != last_status:
                    self.current_market_status = current_status
                    logger.info(f"Market status changed to: {current_status}")
                    self._notify_status_change()
                    last_status = current_status
                
                # Sleep for a minute before checking again
                time.sleep(60)
                
            except Exception as e:
                logger.error(f"Error in market hours monitoring: {e}")
                time.sleep(60)
    
    def _determine_market_status(self) -> str:
        """
        Determine the current market status based on time and calendar.
        
        Returns:
            Market status string
        """
        if not self.observe_market_hours:
            # If not observing market hours, always return OPEN
            return MarketStatus.OPEN
        
        now = datetime.now(timezone.utc)
        current_time_str = now.strftime("%H:%M")
        weekday = now.weekday()  # 0=Monday, 6=Sunday
        
        # Check if it's a holiday
        for holiday_date in self.custom_holidays:
            if isinstance(holiday_date, str):
                holiday_date = datetime.strptime(holiday_date, "%Y-%m-%d").date()
            
            if now.date() == holiday_date:
                return MarketStatus.HOLIDAY
        
        if self.market_type == "forex":
            # Forex market is open from Sunday evening to Friday evening
            if weekday == 6:  # Sunday
                sunday_open_time = self.market_schedule["sunday_open"]
                if current_time_str >= sunday_open_time:
                    return MarketStatus.OPEN
                return MarketStatus.WEEKEND
            
            elif weekday == 5:  # Friday
                friday_close_time = self.market_schedule["friday_close"]
                if current_time_str < friday_close_time:
                    return MarketStatus.OPEN
                return MarketStatus.WEEKEND
            
            elif 0 <= weekday <= 4:  # Monday to Thursday
                # Check for daily maintenance window around rollover
                daily_maint = self.market_schedule["daily_maintenance"]
                if daily_maint["start"] <= current_time_str <= daily_maint["end"]:
                    return MarketStatus.MAINTENANCE
                return MarketStatus.OPEN
            
            return MarketStatus.WEEKEND
        
        elif self.market_type == "us_equities":
            if weekday >= 5:  # Weekend
                return MarketStatus.WEEKEND
            
            regular = self.market_schedule["regular"]
            pre = self.market_schedule["pre_market"]
            after = self.market_schedule["after_market"]
            
            if regular["open"] <= current_time_str <= regular["close"]:
                return MarketStatus.OPEN
            elif pre["open"] <= current_time_str < regular["open"]:
                return MarketStatus.PRE_MARKET
            elif regular["close"] < current_time_str <= after["close"]:
                return MarketStatus.AFTER_MARKET
            else:
                return MarketStatus.CLOSED
        
        # Default case, should not reach here
        logger.warning(f"Unhandled market_type: {self.market_type}, returning CLOSED")
        return MarketStatus.CLOSED
    
    def _is_market_trading_hours(self) -> bool:
        """Check if the market is currently in trading hours."""
        status = self.current_market_status
        
        if not self.observe_market_hours:
            return True
        
        if self.market_type == "forex":
            return status in [MarketStatus.OPEN]
        elif self.market_type == "us_equities":
            return status in [MarketStatus.OPEN, MarketStatus.PRE_MARKET, MarketStatus.AFTER_MARKET]
        
        return False
    
    def _health_check_loop(self):
        """Perform regular health checks on the connection."""
        logger.info("Health check thread started")
        
        while self.running:
            try:
                # Skip health check if not connected
                if self.connection_state != ConnectionState.CONNECTED:
                    time.sleep(self.health_check_interval)
                    continue
                
                # Check if we're receiving data for all subscribed symbols
                self._check_data_freshness()
                
                # Check if IB connection is still alive
                if not self._check_ib_connection():
                    logger.warning("IB connection test failed, initiating reconnection")
                    self._initiate_reconnection()
                
                # Sleep until next check
                time.sleep(self.health_check_interval)
                
            except Exception as e:
                logger.error(f"Error in health check loop: {e}")
                time.sleep(self.health_check_interval)
    
    def _check_data_freshness(self):
        """Check if we're receiving fresh data for subscribed symbols."""
        if not self.data_feed or not self.data_feed.app or not self.data_feed.app.connected:
            return
        
        now = datetime.now(timezone.utc)
        stale_symbols = []
        
        # Skip check if market is closed
        if not self._is_market_trading_hours():
            return
        
        for symbol in self.active_subscriptions:
            if symbol in self.last_data_time:
                time_since_last = (now - self.last_data_time[symbol]).total_seconds()
                if time_since_last > self.data_timeout:
                    stale_symbols.append(symbol)
        
        if stale_symbols:
            logger.warning(f"Data timeout for symbols: {', '.join(stale_symbols)}")
            # Resubscribe to stale symbols
            for symbol in stale_symbols:
                self.pending_subscriptions.put(symbol)
    
    def _check_ib_connection(self) -> bool:
        """Check if IB connection is still active."""
        if not self.data_feed or not hasattr(self.data_feed, 'app') or not self.data_feed.app:
            return False
        
        try:
            # Simple connection check - could enhance with a ping method
            return self.data_feed.app.connected
        except Exception as e:
            logger.error(f"Error checking IB connection: {e}")
            return False
    
    def _initiate_reconnection(self):
        """Initiate reconnection process."""
        logger.info("Initiating reconnection to Interactive Brokers")
        
        # Set state to reconnecting
        self.connection_state = ConnectionState.RECONNECTING
        self._notify_status_change()
        
        try:
            # Disconnect if connected
            if self.data_feed:
                self.data_feed.disconnect()
            
            # Wait a moment
            time.sleep(2.0)
            
            # Reset client
            self._initialize_components()
            
            # Attempt reconnection
            if self.data_feed.connect():
                logger.info("Successfully reconnected to Interactive Brokers")
                self.connection_state = ConnectionState.CONNECTED
                self._notify_status_change()
                
                # Resubscribe to symbols
                self._resubscribe_all()
                
                return True
            else:
                logger.error("Failed to reconnect to Interactive Brokers")
                self.connection_state = ConnectionState.ERROR
                self.reconnect_attempts += 1
                self._notify_status_change()
                return False
            
        except Exception as e:
            logger.error(f"Error during reconnection: {e}")
            self.connection_state = ConnectionState.ERROR
            self.reconnect_attempts += 1
            self._notify_status_change()
            return False
    
    def _data_processing_loop(self):
        """Process incoming data and generate candles."""
        logger.info("Data processing thread started")
        
        last_check_time = datetime.now(timezone.utc)
        
        while self.running:
            try:
                # Skip processing if not connected
                if self.connection_state != ConnectionState.CONNECTED:
                    time.sleep(1.0)
                    continue
                
                # Skip processing if market is closed
                if not self._is_market_trading_hours() and self.observe_market_hours:
                    time.sleep(5.0)
                    continue
                
                # Process ticks from all subscribed symbols
                processed_count = 0
                for symbol in self.active_subscriptions:
                    processed = self._process_symbol_data(symbol)
                    processed_count += processed
                
                # Check and trigger callbacks for completed candles
                now = datetime.now(timezone.utc)
                if (now - last_check_time).total_seconds() >= 10:  # Every 10 seconds
                    self._check_and_trigger_callbacks()
                    last_check_time = now
                
                # Sleep to prevent high CPU usage
                # Use shorter sleep if we're actively processing data
                if processed_count > 0:
                    time.sleep(0.1)  # 100ms when active
                else:
                    time.sleep(0.5)  # 500ms when idle
                
            except Exception as e:
                logger.error(f"Error in data processing loop: {e}")
                time.sleep(1.0)
    
    def _process_symbol_data(self, symbol: str) -> int:
        """
        Process incoming data for a specific symbol.
        
        Args:
            symbol: Symbol to process
            
        Returns:
            Number of ticks processed
        """
        if not self.data_feed or not self.data_feed.app:
            return 0
        
        try:
            # Get latest tick
            latest_tick = self.data_feed.get_latest_tick(symbol)
            if not latest_tick:
                return 0
            
            # Update last data time
            self.last_data_time[symbol] = datetime.now(timezone.utc)
            
            # Process the tick
            if self.tick_aggregator and "bid" in latest_tick and "ask" in latest_tick:
                # Calculate mid price
                mid_price = (latest_tick["bid"] + latest_tick["ask"]) / 2.0
                
                # Process in tick aggregator
                completed_candles = self.tick_aggregator.process_tick(
                    symbol=symbol,
                    timestamp=latest_tick["timestamp"],
                    price=mid_price,
                    size=latest_tick.get("last_size", 0),
                    tick_type="trade",
                    source="ib",
                    store_in_db=self.config.get("store_in_db", True)
                )
                
                # Handle completed candles
                if completed_candles:
                    self._handle_completed_candles(symbol, completed_candles)
                
                return 1  # Processed one tick
            
            return 0
            
        except Exception as e:
            logger.error(f"Error processing data for {symbol}: {e}")
            return 0
    
    def _handle_completed_candles(self, symbol: str, completed_candles: Dict[int, Dict[str, Any]]):
        """
        Handle completed candles from the tick aggregator.
        
        Args:
            symbol: Symbol of the completed candles
            completed_candles: Dictionary mapping timeframe to completed candle
        """
        # Log completed candles
        for timeframe, candle in completed_candles.items():
            logger.debug(f"Completed {timeframe}m candle for {symbol}: " +
                       f"O:{candle['open']:.5f} H:{candle['high']:.5f} " +
                       f"L:{candle['low']:.5f} C:{candle['close']:.5f} V:{candle['volume']:.2f}")
            
            # Handle derived timeframes if this is a 1-minute candle and we have a timeframe converter
            if timeframe == 1 and self.timeframe_converter:
                self._update_derived_timeframes(symbol, candle)
    
    def _update_derived_timeframes(self, symbol: str, one_min_candle: Dict[str, Any]):
        """
        Update derived timeframes based on a new 1-minute candle.
        
        Args:
            symbol: Symbol of the candle
            one_min_candle: The 1-minute candle that was just completed
        """
        try:
            # Convert the candle to a DataFrame with a single row
            candle_df = pd.DataFrame([{
                'open': one_min_candle['open'],
                'high': one_min_candle['high'],
                'low': one_min_candle['low'],
                'close': one_min_candle['close'],
                'volume': one_min_candle['volume']
            }], index=[one_min_candle['timestamp']])
            
            # Get existing 1-minute candles for this symbol
            existing_candles = self.tick_aggregator.get_candles(symbol, timeframe=1)
            
            # If we already have candles, append the new one (avoid duplicates)
            if not existing_candles.empty:
                # Check if the timestamp already exists
                if one_min_candle['timestamp'] not in existing_candles.index:
                    # Append the new candle
                    candle_df = pd.concat([existing_candles, candle_df])
            
            # Update all derived timeframes
            if self.timeframe_converter:
                self.timeframe_converter.update_data(symbol, candle_df, timeframe="1m")
                
                # Log update
                logger.debug(f"Updated derived timeframes for {symbol} based on new 1-minute candle")
        except Exception as e:
            logger.error(f"Error updating derived timeframes for {symbol}: {e}")
    
    def _check_and_trigger_callbacks(self):
        """Check for completed candles and trigger registered callbacks."""
        if not self.data_callbacks:
            return
        
        for symbol, callbacks in list(self.data_callbacks.items()):
            for timeframe, callback_list in list(callbacks.items()):
                # Get the latest candles
                try:
                    if timeframe == "1m":
                        candles = self.tick_aggregator.get_candles(symbol, timeframe=1, limit=100)
                    else:
                        # Try to get from timeframe converter if available
                        if self.timeframe_converter:
                            candles = self.timeframe_converter.get_data(symbol, timeframe)
                        else:
                            # Convert numeric minutes
                            minutes = int(timeframe[:-1])
                            if timeframe.endswith('h'):
                                minutes *= 60
                            if timeframe.endswith('d'):
                                minutes *= 1440
                            candles = self.tick_aggregator.get_candles(symbol, timeframe=minutes, limit=100)
                    
                    # If we have candles and callbacks
                    if not candles.empty and callback_list:
                        # Call each registered callback with the data
                        for callback in callback_list:
                            try:
                                callback(symbol, timeframe, candles)
                            except Exception as e:
                                logger.error(f"Error in callback for {symbol} {timeframe}: {e}")
                
                except Exception as e:
                    logger.error(f"Error getting candles for {symbol} {timeframe}: {e}")
    
    def _notify_status_change(self):
        """Notify subscribers of status changes."""
        status = {
            "connection_state": self.connection_state,
            "market_status": self.current_market_status,
            "timestamp": datetime.now(timezone.utc),
            "active_symbols": list(self.active_subscriptions),
            "reconnect_attempts": self.reconnect_attempts
        }
        
        # Call registered callbacks
        for callback in self.status_callbacks:
            try:
                callback(status)
            except Exception as e:
                logger.error(f"Error in status callback: {e}")
    
    def subscribe_symbol(self, symbol: str) -> bool:
        """
        Subscribe to market data for a symbol.
        
        Args:
            symbol: Symbol to subscribe to
            
        Returns:
            True if subscription was initiated, False otherwise
        """
        with self._lock:
            # If already subscribed, return True
            if symbol in self.active_subscriptions:
                return True
            
            # If not connected, queue the subscription for when we connect
            if self.connection_state != ConnectionState.CONNECTED:
                self.pending_subscriptions.put(symbol)
                logger.info(f"Queued subscription for {symbol} (not connected)")
                return True
            
            # If connected but market is closed, queue the subscription
            if not self._is_market_trading_hours() and self.observe_market_hours:
                self.pending_subscriptions.put(symbol)
                logger.info(f"Queued subscription for {symbol} (market closed)")
                return True
            
            # Otherwise, try to subscribe now
            try:
                if self.data_feed.subscribe_market_data(symbol):
                    self.active_subscriptions.add(symbol)
                    logger.info(f"Subscribed to {symbol}")
                    return True
                else:
                    logger.error(f"Failed to subscribe to {symbol}")
                    return False
            except Exception as e:
                logger.error(f"Error subscribing to {symbol}: {e}")
                # Add to pending queue to retry later
                self.pending_subscriptions.put(symbol)
                return False
    
    def unsubscribe_symbol(self, symbol: str) -> bool:
        """
        Unsubscribe from market data for a symbol.
        
        Args:
            symbol: Symbol to unsubscribe from
            
        Returns:
            True if unsubscription was successful, False otherwise
        """
        with self._lock:
            # Remove from active subscriptions
            self.active_subscriptions.discard(symbol)
            
            # Remove from pending queue if present
            new_pending = queue.Queue()
            while not self.pending_subscriptions.empty():
                item = self.pending_subscriptions.get()
                if item != symbol:
                    new_pending.put(item)
            self.pending_subscriptions = new_pending
            
            # If not connected, just return
            if self.connection_state != ConnectionState.CONNECTED:
                return True
            
            # Try to cancel subscription
            try:
                result = self.data_feed.cancel_market_data(symbol)
                logger.info(f"Unsubscribed from {symbol}")
                return result
            except Exception as e:
                logger.error(f"Error unsubscribing from {symbol}: {e}")
                return False
    
    def get_current_market_status(self) -> Dict[str, Any]:
        """
        Get the current market status.
        
        Returns:
            Dictionary with market status information
        """
        return {
            "connection_state": self.connection_state,
            "market_status": self.current_market_status,
            "market_type": self.market_type,
            "is_trading_hours": self._is_market_trading_hours(),
            "timestamp": datetime.now(timezone.utc),
            "active_symbols": list(self.active_subscriptions),
            "pending_symbols": list(self.pending_subscriptions.queue),
            "reconnect_attempts": self.reconnect_attempts
        }
    
    def get_latest_candles(self, symbol: str, timeframe: str, limit: int = 100) -> pd.DataFrame:
        """
        Get the latest candles for a symbol and timeframe.
        
        Args:
            symbol: Symbol to get candles for
            timeframe: Timeframe of the candles
            limit: Maximum number of candles to return
            
        Returns:
            DataFrame with candle data
        """
        # Check if we have data for this symbol
        if symbol not in self.active_subscriptions:
            logger.warning(f"Symbol {symbol} is not subscribed")
            return pd.DataFrame()
        
        try:
            # Get from correct source based on timeframe
            if timeframe == "1m":
                return self.tick_aggregator.get_candles(symbol, timeframe=1, limit=limit)
            
            # Try to get from timeframe converter if available
            if self.timeframe_converter:
                df = self.timeframe_converter.get_data(symbol, timeframe)
                if not df.empty:
                    return df.tail(limit)
            
            # Convert numeric minutes
            minutes = int(timeframe[:-1])
            if timeframe.endswith('h'):
                minutes *= 60
            if timeframe.endswith('d'):
                minutes *= 1440
                
            return self.tick_aggregator.get_candles(symbol, timeframe=minutes, limit=limit)
            
        except Exception as e:
            logger.error(f"Error getting candles for {symbol} {timeframe}: {e}")
            return pd.DataFrame()
    
    def get_latest_tick(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get the latest tick for a symbol.
        
        Args:
            symbol: Symbol to get tick for
            
        Returns:
            Dictionary with tick information or None if not available
        """
        if not self.data_feed:
            return None
        
        try:
            return self.data_feed.get_latest_tick(symbol)
        except Exception as e:
            logger.error(f"Error getting latest tick for {symbol}: {e}")
            return None
    
    def register_candle_callback(self, symbol: str, timeframe: str, 
                                callback: Callable[[str, str, pd.DataFrame], None]) -> bool:
        """
        Register a callback to be called when new candles are available.
        
        Args:
            symbol: Symbol to register for
            timeframe: Timeframe to register for
            callback: Function to call with (symbol, timeframe, candles)
            
        Returns:
            True if registration was successful, False otherwise
        """
        with self._lock:
            # Make sure we're subscribed to this symbol
            if symbol not in self.active_subscriptions:
                self.subscribe_symbol(symbol)
            
            # Initialize callback structure if needed
            if symbol not in self.data_callbacks:
                self.data_callbacks[symbol] = {}
            
            if timeframe not in self.data_callbacks[symbol]:
                self.data_callbacks[symbol][timeframe] = []
            
            # Add callback
            self.data_callbacks[symbol][timeframe].append(callback)
            logger.info(f"Registered callback for {symbol} {timeframe}")
            return True
    
    def unregister_candle_callback(self, symbol: str, timeframe: str,
                                 callback: Callable[[str, str, pd.DataFrame], None]) -> bool:
        """
        Unregister a previously registered callback.
        
        Args:
            symbol: Symbol to unregister for
            timeframe: Timeframe to unregister for
            callback: Function to unregister
            
        Returns:
            True if unregistration was successful, False otherwise
        """
        with self._lock:
            try:
                # Check if we have this callback
                if (symbol in self.data_callbacks and 
                    timeframe in self.data_callbacks[symbol] and
                    callback in self.data_callbacks[symbol][timeframe]):
                    
                    # Remove callback
                    self.data_callbacks[symbol][timeframe].remove(callback)
                    
                    # Clean up empty lists
                    if not self.data_callbacks[symbol][timeframe]:
                        del self.data_callbacks[symbol][timeframe]
                    
                    if not self.data_callbacks[symbol]:
                        del self.data_callbacks[symbol]
                    
                    logger.info(f"Unregistered callback for {symbol} {timeframe}")
                    return True
                else:
                    logger.warning(f"Callback not found for {symbol} {timeframe}")
                    return False
            except Exception as e:
                logger.error(f"Error unregistering callback: {e}")
                return False
    
    def register_status_callback(self, callback: Callable[[Dict[str, Any]], None]) -> bool:
        """
        Register a callback for status changes.
        
        Args:
            callback: Function to call with status dictionary
            
        Returns:
            True if registration was successful, False otherwise
        """
        with self._lock:
            if callback not in self.status_callbacks:
                self.status_callbacks.append(callback)
                logger.info("Registered status callback")
                return True
            return False
    
    def unregister_status_callback(self, callback: Callable[[Dict[str, Any]], None]) -> bool:
        """
        Unregister a previously registered status callback.
        
        Args:
            callback: Function to unregister
            
        Returns:
            True if unregistration was successful, False otherwise
        """
        with self._lock:
            if callback in self.status_callbacks:
                self.status_callbacks.remove(callback)
                logger.info("Unregistered status callback")
                return True
            return False
    
    def get_historical_data(self, symbol: str, timeframe: str, 
                          start_date: Optional[datetime] = None,
                          end_date: Optional[datetime] = None) -> pd.DataFrame:
        """
        Get historical data for a symbol and timeframe.
        
        Args:
            symbol: Symbol to get data for
            timeframe: Timeframe to get data for
            start_date: Start date for the data (None for default duration)
            end_date: End date for the data (None for current time)
            
        Returns:
            DataFrame with historical data
        """
        if not self.data_feed or self.connection_state != ConnectionState.CONNECTED:
            logger.error("Cannot get historical data: not connected to Interactive Brokers")
            return pd.DataFrame()
        
        try:
            return self.data_feed.fetch_data(
                symbol=symbol,
                timeframe=timeframe,
                start_date=start_date,
                end_date=end_date
            )
        except Exception as e:
            logger.error(f"Error getting historical data for {symbol} {timeframe}: {e}")
            return pd.DataFrame()
    
    def __del__(self):
        """Cleanup when object is destroyed."""
        try:
            self.stop()
        except:
            pass