"""Interactive Brokers data feed implementation.

This module implements a data feed for Interactive Brokers.
"""

import logging
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Union, Tuple

import pandas as pd

from .base_feed import DataFeed, DataFeedFactory

logger = logging.getLogger(__name__)

try:
    from ibapi.client import EClient
    from ibapi.wrapper import EWrapper
    from ibapi.contract import Contract
    from ibapi.ticktype import TickTypeEnum
    IB_API_AVAILABLE = True
    
    # Log the version of the API
    import ibapi
    logger.info(f"Using IB API version: {ibapi.__version__}")
except ImportError:
    logger.warning("IB API not available. Please install ibapi package.")
    IB_API_AVAILABLE = False

# Mapping of FXML4 timeframes to IB bar sizes
TIMEFRAME_MAPPING = {
    '1m': '1 min',
    '5m': '5 mins',
    '15m': '15 mins',
    '30m': '30 mins',
    '1h': '1 hour',
    '2h': '2 hours',
    '4h': '4 hours',
    '1d': '1 day',
    '1w': '1 week',
    '1M': '1 month'
}

# Duration strings for different timeframes
DURATION_MAPPING = {
    '1m': '1 D',     # 1 day of 1-minute data
    '5m': '1 D',     # 1 day of 5-minute data
    '15m': '1 D',    # 1 day of 15-minute data
    '30m': '2 D',    # 2 days of 30-minute data
    '1h': '5 D',     # 5 days of 1-hour data
    '2h': '10 D',    # 10 days of 2-hour data
    '4h': '20 D',    # 20 days of 4-hour data
    '1d': '60 D',    # 60 days of daily data
    '1w': '1 Y',     # 1 year of weekly data
    '1M': '5 Y'      # 5 years of monthly data
}


class IBAPIApp(EWrapper, EClient):
    """
    Interactive Brokers API wrapper application.
    Combines EWrapper and EClient functionality.
    """
    
    def __init__(self):
        """Initialize the application."""
        EClient.__init__(self, self)
        
        # State management
        self.next_req_id = 1
        self.connected = False
        
        # Data containers
        self.historical_data = []
        self.market_data = {}
        self.account_info = {}
        
        # Event flags
        self.historical_data_end_event = threading.Event()
        self.market_data_received = threading.Event()
        
        # Real-time tick data
        self.tick_queue = []
        self.tick_queue_lock = threading.Lock()
        self.max_tick_queue_size = 10000
        self.symbol_map = {}  # Maps reqId to symbol for market data
        
        # Statistics
        self.tick_count = 0
        self.last_tick_time = {}
    
    def nextValidId(self, orderId: int):
        """Callback for next valid order ID."""
        self.connected = True
        logger.info(f"Connected to TWS")
    
    def connectAck(self):
        """Callback for connection acknowledgement."""
        logger.info("Connection to TWS acknowledged")
    
    def error(self, reqId: int, errorCode: int, errorString: str, advancedOrderRejectJson: str = ""):
        """Callback for error messages."""
        # Ignore certain informational messages
        if errorCode in [2104, 2106, 2158]:  # Market data farm connection messages
            return
        
        logger.error(f"Error {errorCode}: {errorString}")
    
    def historicalData(self, reqId: int, bar):
        """Callback for historical data."""
        self.historical_data.append([
            bar.date, 
            bar.open, 
            bar.high, 
            bar.low, 
            bar.close, 
            bar.volume
        ])
        logger.debug(f"Historical data: {bar.date} - OHLCV: {bar.open}/{bar.high}/{bar.low}/{bar.close}/{bar.volume}")
    
    def historicalDataEnd(self, reqId: int, start: str, end: str):
        """Callback for end of historical data."""
        logger.info(f"Historical data retrieval completed. {len(self.historical_data)} bars received.")
        self.historical_data_end_event.set()
    
    def tickPrice(self, reqId: int, tickType: int, price: float, attrib):
        """Callback for price tick."""
        # Store in market data dict for snapshot requests
        if reqId not in self.market_data:
            self.market_data[reqId] = {}
        
        # Get tick name based on API version
        if hasattr(TickTypeEnum, 'toStr'):
            tick_name = TickTypeEnum.toStr(tickType)
        else:
            tick_name = TickTypeEnum.to_str(tickType)
            
        self.market_data[reqId][tick_name] = price
        self.market_data_received.set()
        
        # For real-time processing, add to tick queue
        if reqId in self.symbol_map:
            symbol = self.symbol_map[reqId]
            
            # Add to tick queue for processing
            with self.tick_queue_lock:
                now = datetime.now(timezone.utc)
                self.tick_queue.append({
                    'reqId': reqId,
                    'symbol': symbol,
                    'type': 'price',
                    'tick_type': tick_name,
                    'price': price,
                    'size': None,
                    'timestamp': now
                })
                
                # Trim queue if it gets too large
                if len(self.tick_queue) > self.max_tick_queue_size:
                    self.tick_queue = self.tick_queue[-self.max_tick_queue_size:]
            
            # Update statistics
            self.tick_count += 1
            self.last_tick_time[symbol] = now
            
            # Log occasional updates
            if self.tick_count % 1000 == 0:
                logger.info(f"Received {self.tick_count} ticks, latest symbol: {symbol}")
        
    def tickSize(self, reqId: int, tickType: int, size: int):
        """Callback for size tick."""
        # Store in market data dict for snapshot requests
        if reqId not in self.market_data:
            self.market_data[reqId] = {}
        
        # Get tick name based on API version
        if hasattr(TickTypeEnum, 'toStr'):
            tick_name = TickTypeEnum.toStr(tickType)
        else:
            tick_name = TickTypeEnum.to_str(tickType)
            
        self.market_data[reqId][tick_name] = size
        
        # For real-time processing, add to tick queue
        if reqId in self.symbol_map:
            symbol = self.symbol_map[reqId]
            
            # Add to tick queue for processing
            with self.tick_queue_lock:
                now = datetime.now(timezone.utc)
                self.tick_queue.append({
                    'reqId': reqId,
                    'symbol': symbol,
                    'type': 'size',
                    'tick_type': tick_name,
                    'price': None,
                    'size': size,
                    'timestamp': now
                })
                
                # Trim queue if it gets too large
                if len(self.tick_queue) > self.max_tick_queue_size:
                    self.tick_queue = self.tick_queue[-self.max_tick_queue_size:]
    
    def get_ticks(self, max_ticks: int = 1000) -> List[Dict[str, Any]]:
        """Get ticks from the tick queue.
        
        Args:
            max_ticks: Maximum number of ticks to return
            
        Returns:
            List of tick dictionaries
        """
        with self.tick_queue_lock:
            ticks = self.tick_queue[:max_ticks]
            self.tick_queue = self.tick_queue[max_ticks:]
            return ticks


def create_forex_contract(symbol: str) -> Contract:
    """Create a forex contract object.
    
    Args:
        symbol: Forex pair symbol (e.g., "EURUSD" or "EUR.USD")
    
    Returns:
        Contract object for the specified forex pair
    """
    # Handle both formats: EURUSD and EUR.USD
    if "." in symbol:
        base_currency = symbol.split(".")[0]
        quote_currency = symbol.split(".")[1]
    else:
        base_currency = symbol[:3]
        quote_currency = symbol[3:]
    
    contract = Contract()
    contract.symbol = base_currency
    contract.secType = "CASH"
    contract.currency = quote_currency
    contract.exchange = "IDEALPRO"
    
    logger.debug(f"Created Forex contract: {base_currency}/{quote_currency}")
    return contract


@DataFeedFactory.register("ib")
class IBDataFeed(DataFeed):
    """Data feed implementation for Interactive Brokers."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the Interactive Brokers data feed.
        
        Args:
            config: Configuration dictionary with the following keys:
                host: TWS host (default: "127.0.0.1")
                port: TWS port (default: 7497 for paper trading)
                client_id: Client ID (default: 0)
                timeout: Connection timeout in seconds (default: 30)
                real_time_updates: Enable real-time tick processing (default: False)
                update_interval: How often to process ticks in seconds (default: 1.0)
                tick_storage_limit: Maximum number of ticks to store (default: 10000)
                candle_storage_days: Number of days of candle history to keep (default: 7)
        """
        super().__init__(config)
        
        # Check if the IB API is available
        if not IB_API_AVAILABLE:
            raise ImportError("Interactive Brokers API not available. Please install ibapi package.")
        
        # Set default configuration values
        self.host = config.get("host", "127.0.0.1")
        self.port = config.get("port", 7497)  # Default to paper trading port
        self.client_id = config.get("client_id", 0)
        self.timeout = config.get("timeout", 30)
        
        # Real-time data configuration
        self.real_time_updates = config.get("real_time_updates", False)
        self.update_interval = config.get("update_interval", 1.0)  # Process ticks every second
        self.tick_storage_limit = config.get("tick_storage_limit", 10000)
        self.candle_storage_days = config.get("candle_storage_days", 7)
        
        # IB connection
        self.app = None
        self.api_thread = None
        
        # Real-time data processing
        self.tick_aggregator = None
        self.tick_processor_thread = None
        self.tick_processor_running = False
        self.last_tick_time = {}
        
        # Market data subscription tracking
        self.market_data_subscriptions = {}
        
        # List of supported symbols and timeframes
        self.supported_symbols = config.get("symbols", ["EUR.USD", "GBP.USD", "USD.JPY", "USD.CHF"])
        
        # Timeframe converter for derived timeframes
        self.timeframe_converter = None
        
        # Import tick aggregator if real-time updates are enabled
        if self.real_time_updates:
            from fxml4.data_engineering.tick_to_candle import TickAggregator
            from fxml4.data_engineering.timeframe_conversion import TimeframeConverter
            
            # Initialize tick aggregator (builds 1-minute candles from ticks)
            self.tick_aggregator = TickAggregator(timeframes=[1, 5, 15, 60, 240])
            
            # Initialize timeframe converter (derives higher timeframes from 1-minute)
            self.timeframe_converter = TimeframeConverter(
                base_timeframe="1m",
                derived_timeframes=["5m", "15m", "30m", "1h", "4h", "1d"]
            )
        
        # Verify configuration
        logger.info(f"Initialized IB data feed with host={self.host}, port={self.port}, real_time={self.real_time_updates}")
    
    def connect(self) -> bool:
        """Connect to the Interactive Brokers TWS API.
        
        Returns:
            True if connected successfully, False otherwise
        """
        try:
            self.app = IBAPIApp()
            self.app.connect(self.host, self.port, self.client_id)
            
            # Start API event loop in a separate thread
            self.api_thread = threading.Thread(target=self.app.run, daemon=True)
            self.api_thread.start()
            
            # Wait for connection
            wait_time = 0
            wait_interval = 0.5
            
            while not self.app.connected and wait_time < self.timeout:
                time.sleep(wait_interval)
                wait_time += wait_interval
            
            if not self.app.connected:
                logger.error(f"Failed to connect to TWS at {self.host}:{self.port}")
                self.disconnect()
                return False
            
            logger.info(f"Connected to TWS at {self.host}:{self.port}")
            return True
        
        except Exception as e:
            logger.error(f"Error connecting to TWS: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from the Interactive Brokers TWS API."""
        # Stop tick processor if running
        self.stop_tick_processor()
        
        # Cancel any active market data subscriptions
        self.cancel_all_market_data()
        
        # Disconnect from TWS
        if self.app:
            self.app.disconnect()
            logger.info("Disconnected from TWS")
    
    def fetch_data(
        self,
        symbol: str,
        timeframe: str,
        start_date: Optional[Union[str, datetime]] = None,
        end_date: Optional[Union[str, datetime]] = None,
        **kwargs: Any,
    ) -> pd.DataFrame:
        """Fetch historical data from Interactive Brokers.
        
        Args:
            symbol: Trading symbol (e.g., "EURUSD" or "EUR.USD")
            timeframe: Timeframe for the data (e.g., "1m", "1h", "1d")
            start_date: Start date for the data
            end_date: End date for the data
            **kwargs: Additional arguments:
                what_to_show: Type of data to retrieve (default: "MIDPOINT")
                use_rth: Use regular trading hours only (default: True)
        
        Returns:
            DataFrame containing the fetched data
            
        Raises:
            ValueError: If the timeframe is not supported
            ConnectionError: If connection to TWS fails
        """
        if timeframe not in TIMEFRAME_MAPPING:
            raise ValueError(f"Unsupported timeframe: {timeframe}")
        
        ib_bar_size = TIMEFRAME_MAPPING[timeframe]
        
        # Use default duration if dates not provided
        if not end_date:
            end_date = datetime.now()
        elif isinstance(end_date, str):
            end_date = pd.to_datetime(end_date)
        
        # Convert duration based on timeframe
        duration_str = DURATION_MAPPING.get(timeframe, "1 D")
        
        # Handle parameters from kwargs
        what_to_show = kwargs.get("what_to_show", "MIDPOINT")
        use_rth = kwargs.get("use_rth", True)
        
        # Connect to IB if not already connected
        if not self.app or not self.app.connected:
            if not self.connect():
                raise ConnectionError("Failed to connect to Interactive Brokers")
        
        try:
            # Reset historical data
            self.app.historical_data = []
            self.app.historical_data_end_event.clear()
            
            # Create contract
            contract = create_forex_contract(symbol)
            
            # Format end date
            end_date_str = end_date.strftime("%Y%m%d %H:%M:%S")
            end_date_with_tz = f"{end_date_str} US/Eastern"
            
            # Request historical data
            logger.info(f"Requesting {ib_bar_size} data for {symbol} with duration {duration_str}")
            
            self.app.reqHistoricalData(
                reqId=self.app.next_req_id,
                contract=contract,
                endDateTime=end_date_with_tz,
                durationStr=duration_str,
                barSizeSetting=ib_bar_size,
                whatToShow=what_to_show,
                useRTH=1 if use_rth else 0,
                formatDate=1,
                keepUpToDate=False,
                chartOptions=[]
            )
            
            # Increment request ID for next request
            self.app.next_req_id += 1
            
            # Wait for data
            self.app.historical_data_end_event.wait(self.timeout)
            
            # Check if we received data
            if not self.app.historical_data_end_event.is_set():
                logger.warning(f"Timeout waiting for historical data for {symbol}")
            
            # Convert data to DataFrame
            if not self.app.historical_data:
                logger.warning(f"No historical data received for {symbol}")
                return pd.DataFrame()
            
            df = pd.DataFrame(
                self.app.historical_data,
                columns=["timestamp", "open", "high", "low", "close", "volume"]
            )
            
            # Process timestamp based on format
            try:
                # Try to parse as string with timezone
                if isinstance(df["timestamp"].iloc[0], str) and "US/Eastern" in df["timestamp"].iloc[0]:
                    # Remove timezone info for now
                    df["timestamp"] = df["timestamp"].apply(lambda x: x.split(" US/Eastern")[0])
                    df["timestamp"] = pd.to_datetime(df["timestamp"], format="%Y%m%d %H:%M:%S")
                elif isinstance(df["timestamp"].iloc[0], str):
                    df["timestamp"] = pd.to_datetime(df["timestamp"])
                else:
                    # Assume Unix timestamp
                    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")
            except Exception as e:
                logger.warning(f"Error processing timestamps: {e}")
            
            # Set index and sort
            df = df.set_index("timestamp")
            df = df.sort_index()
            
            logger.info(f"Retrieved {len(df)} rows of {timeframe} data for {symbol}")
            return df
        
        except Exception as e:
            logger.error(f"Error fetching data: {e}")
            raise
    
    def get_market_data(self, symbol: str, timeout: int = 10) -> Dict[str, Any]:
        """Get real-time market data for a symbol.
        
        Args:
            symbol: Trading symbol (e.g., "EURUSD" or "EUR.USD")
            timeout: Timeout in seconds
            
        Returns:
            Dictionary containing market data
            
        Raises:
            ConnectionError: If connection to TWS fails
            TimeoutError: If market data is not received within timeout
        """
        # Connect to IB if not already connected
        if not self.app or not self.app.connected:
            if not self.connect():
                raise ConnectionError("Failed to connect to Interactive Brokers")
        
        try:
            # Reset market data event
            self.app.market_data_received.clear()
            
            # Create contract
            contract = create_forex_contract(symbol)
            
            # Request market data
            req_id = self.app.next_req_id
            self.app.reqMktData(req_id, contract, "", False, False, [])
            self.app.next_req_id += 1
            
            logger.info(f"Requested market data for {symbol}")
            
            # Wait for data
            if not self.app.market_data_received.wait(timeout):
                raise TimeoutError(f"Timeout waiting for market data for {symbol}")
            
            # Get the data
            if req_id not in self.app.market_data:
                logger.warning(f"No market data received for {symbol}")
                return {}
            
            market_data = self.app.market_data[req_id].copy()
            
            # Cancel the market data subscription
            self.app.cancelMktData(req_id)
            
            return market_data
        
        except Exception as e:
            logger.error(f"Error getting market data: {e}")
            raise
    
    def get_available_symbols(self) -> List[str]:
        """Get the list of available symbols.
        
        Returns:
            List of available symbols
        """
        return self.supported_symbols
    
    def get_available_timeframes(self) -> List[str]:
        """Get the list of available timeframes.
        
        Returns:
            List of available timeframes
        """
        return list(TIMEFRAME_MAPPING.keys())
    
    def subscribe_market_data(self, symbol: str, snapshot: bool = False) -> int:
        """Subscribe to real-time market data for a symbol.
        
        Args:
            symbol: Symbol to subscribe to (e.g., "EURUSD" or "EUR.USD")
            snapshot: Whether to request a snapshot instead of streaming data
            
        Returns:
            Request ID for the subscription
            
        Raises:
            ConnectionError: If not connected to TWS
            ValueError: If real-time updates are disabled
        """
        if not self.app or not self.app.connected:
            if not self.connect():
                raise ConnectionError("Failed to connect to Interactive Brokers")
        
        # Create contract
        contract = create_forex_contract(symbol)
        
        # Request market data
        req_id = self.app.next_req_id
        
        # Store mapping of reqId to symbol
        self.app.symbol_map[req_id] = symbol
        
        # Track subscription
        self.market_data_subscriptions[symbol] = req_id
        
        # Request market data (generic tick list empty, snapshot flag as specified)
        self.app.reqMktData(req_id, contract, "", snapshot, False, [])
        self.app.next_req_id += 1
        
        logger.info(f"Subscribed to {'snapshot' if snapshot else 'streaming'} market data for {symbol} (reqId: {req_id})")
        
        # Start tick processor if needed and real-time updates are enabled
        if self.real_time_updates and not snapshot and not self.tick_processor_running:
            self.start_tick_processor()
        
        return req_id
    
    def cancel_market_data(self, symbol: str) -> bool:
        """Cancel market data subscription for a symbol.
        
        Args:
            symbol: Symbol to cancel subscription for
            
        Returns:
            True if subscription was canceled, False otherwise
        """
        if symbol in self.market_data_subscriptions:
            req_id = self.market_data_subscriptions[symbol]
            if self.app and self.app.connected:
                self.app.cancelMktData(req_id)
                logger.info(f"Canceled market data subscription for {symbol} (reqId: {req_id})")
            
            # Remove from subscriptions and symbol map
            del self.market_data_subscriptions[symbol]
            if req_id in self.app.symbol_map:
                del self.app.symbol_map[req_id]
            
            return True
        
        return False
    
    def cancel_all_market_data(self):
        """Cancel all market data subscriptions."""
        symbols = list(self.market_data_subscriptions.keys())
        for symbol in symbols:
            self.cancel_market_data(symbol)
    
    def start_tick_processor(self):
        """Start the tick processor thread.
        
        Raises:
            ValueError: If real-time updates are disabled
        """
        if not self.real_time_updates:
            raise ValueError("Real-time updates are disabled")
        
        if self.tick_processor_running:
            logger.warning("Tick processor is already running")
            return
        
        self.tick_processor_running = True
        self.tick_processor_thread = threading.Thread(
            target=self._tick_processor_loop, 
            daemon=True
        )
        self.tick_processor_thread.start()
        logger.info("Started tick processor thread")
    
    def stop_tick_processor(self):
        """Stop the tick processor thread."""
        if self.tick_processor_running:
            self.tick_processor_running = False
            if self.tick_processor_thread:
                self.tick_processor_thread.join(timeout=5.0)
                logger.info("Stopped tick processor thread")
    
    def _tick_processor_loop(self):
        """Background thread that processes ticks and updates candles."""
        last_cleanup_time = datetime.now()
        
        while self.tick_processor_running:
            try:
                # Get ticks from queue
                ticks = self.app.get_ticks(max_ticks=1000)
                
                # Process each tick
                for tick in ticks:
                    # Skip ticks without price information
                    if tick['type'] == 'price' and tick['price'] is not None:
                        symbol = tick['symbol']
                        timestamp = tick['timestamp']
                        price = tick['price']
                        
                        # For size ticks, we may have a corresponding price tick later
                        # in the queue, so we'll process it in the next batch
                        size = 0.0  # Default size
                        
                        # Process tick in the aggregator, now with storage in TimescaleDB
                        if self.tick_aggregator:
                            # Determine if we should store ticks in TimescaleDB
                            store_in_db = self.config.get("store_ticks_in_db", True)
                            
                            # Process the tick
                            completed_candles = self.tick_aggregator.process_tick(
                                symbol=symbol, 
                                timestamp=timestamp, 
                                price=price, 
                                size=size,
                                tick_type=tick.get('tick_type', 'trade'),
                                source='ib',
                                store_in_db=store_in_db
                            )
                            
                            # Handle completed candles
                            if completed_candles:
                                self._handle_completed_candles(symbol, completed_candles)
                
                # Clean up old candles periodically (once a day)
                now = datetime.now()
                if (now - last_cleanup_time).total_seconds() > 86400:  # 24 hours
                    self._cleanup_old_candles()
                    last_cleanup_time = now
                
                # Sleep for the update interval
                time.sleep(self.update_interval)
            
            except Exception as e:
                logger.error(f"Error in tick processor: {e}")
                time.sleep(1.0)  # Sleep a bit longer on error
    
    def _handle_completed_candles(self, symbol: str, completed_candles: Dict[int, Dict[str, Any]]):
        """Handle completed candles from the tick aggregator.
        
        Args:
            symbol: Symbol of the completed candles
            completed_candles: Dictionary mapping timeframe to completed candle
        """
        from fxml4.data_engineering.timescaledb import TimescaleDBClient
        from fxml4.config import get_config
        
        # Get TimescaleDB configuration
        config = get_config()
        db_config = config.get("database", {})
        
        # Initialize TimescaleDB client if not already done
        if not hasattr(self, '_timescaledb_client'):
            self._timescaledb_client = TimescaleDBClient(
                host=db_config.get("host", "localhost"),
                port=db_config.get("port", 5433),
                dbname=db_config.get("name", "fxml4"),
                user=db_config.get("user", "postgres"),
                password=db_config.get("password", "postgres")
            )
        
        # Log completed candles
        for timeframe, candle in completed_candles.items():
            logger.debug(f"Completed {timeframe}m candle for {symbol}: " +
                         f"O:{candle['open']:.5f} H:{candle['high']:.5f} " +
                         f"L:{candle['low']:.5f} C:{candle['close']:.5f} V:{candle['volume']:.2f}")
            
            # Handle derived timeframes if this is a 1-minute candle and we have a timeframe converter
            if timeframe == 1 and self.timeframe_converter:
                self._update_derived_timeframes(symbol, candle)
            
            # Store the candle in TimescaleDB
            try:
                # Only 1-minute candles are stored directly, higher timeframes are derived via continuous aggregates
                if timeframe == 1:
                    result = self._timescaledb_client.store_candle(
                        symbol=symbol,
                        timestamp=candle['timestamp'],
                        open_price=candle['open'],
                        high_price=candle['high'],
                        low_price=candle['low'],
                        close_price=candle['close'],
                        volume=int(candle['volume']),
                        tick_count=candle['tick_count'],
                        source='ib'
                    )
                    if result:
                        logger.debug(f"Stored {timeframe}m candle for {symbol} in TimescaleDB")
                    else:
                        logger.warning(f"Failed to store {timeframe}m candle for {symbol} in TimescaleDB")
            except Exception as e:
                logger.error(f"Error storing candle in TimescaleDB: {e}")
                # Log the full stack trace for debugging
                import traceback
                logger.error(traceback.format_exc())
    
    def _update_derived_timeframes(self, symbol: str, one_min_candle: Dict[str, Any]):
        """Update derived timeframes based on a new 1-minute candle.
        
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
            # Log the full stack trace for debugging
            import traceback
            logger.error(traceback.format_exc())
    
    def _cleanup_old_candles(self):
        """Clean up old candles from the tick aggregator."""
        if not self.tick_aggregator:
            return
        
        # Calculate cutoff date
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=self.candle_storage_days)
        
        # Clean up old candles
        self.tick_aggregator.clear_old_candles(cutoff_date)
        logger.info(f"Cleaned up candles older than {cutoff_date}")
    
    def get_realtime_candles(self, symbol: str, timeframe: Union[int, str] = 1, limit: int = 100) -> pd.DataFrame:
        """Get real-time candles for a symbol and timeframe.
        
        Args:
            symbol: Symbol to get candles for
            timeframe: Timeframe in minutes (int) or as string (e.g., "5m", "1h")
            limit: Maximum number of candles to return
            
        Returns:
            DataFrame of candles with timestamp as index
            
        Raises:
            ValueError: If real-time updates are disabled
        """
        if not self.real_time_updates:
            raise ValueError("Real-time updates are disabled")
        
        if not self.tick_aggregator:
            return pd.DataFrame()
        
        # Subscribe to market data if not already subscribed
        if symbol not in self.market_data_subscriptions:
            self.subscribe_market_data(symbol)
        
        # Convert timeframe to string format if it's an integer
        if isinstance(timeframe, int):
            timeframe_str = f"{timeframe}m"
        else:
            timeframe_str = timeframe
        
        # Check if this is a derived timeframe that should come from the timeframe converter
        derived_timeframes = ["5m", "15m", "30m", "1h", "4h", "1d"] if self.timeframe_converter else []
        
        if timeframe_str in derived_timeframes:
            # Get derived candles from the timeframe converter
            if self.timeframe_converter:
                df = self.timeframe_converter.get_data(symbol, timeframe_str)
                if not df.empty:
                    # Limit the number of candles
                    return df.tail(limit)
        
        # For tick aggregator's native timeframes or if timeframe converter doesn't have the data
        # Convert string timeframe to integer if needed
        if not isinstance(timeframe, int):
            # Extract the numeric part and convert to int
            numeric_part = ''.join(filter(str.isdigit, timeframe_str))
            if numeric_part:
                timeframe_int = int(numeric_part)
                
                # Convert hours to minutes if needed
                if timeframe_str.endswith('h'):
                    timeframe_int *= 60
                # Convert days to minutes if needed    
                elif timeframe_str.endswith('d'):
                    timeframe_int *= 1440
                    
                return self.tick_aggregator.get_candles(symbol, timeframe_int, limit)
        
        # Default to tick aggregator with the original timeframe
        return self.tick_aggregator.get_candles(symbol, timeframe, limit)
    
    def get_latest_tick(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get the latest tick for a symbol.
        
        Args:
            symbol: Symbol to get the latest tick for
            
        Returns:
            Latest tick information or None if no tick available
            
        Raises:
            ValueError: If real-time updates are disabled
        """
        if not self.real_time_updates:
            raise ValueError("Real-time updates are disabled")
        
        if not self.app:
            return None
        
        # Find reqId for this symbol
        req_id = None
        for rid, sym in self.app.symbol_map.items():
            if sym == symbol:
                req_id = rid
                break
        
        if req_id is None or req_id not in self.app.market_data:
            return None
        
        market_data = self.app.market_data[req_id]
        
        # Try to get latest BID/ASK prices
        result = {
            'symbol': symbol,
            'timestamp': self.app.last_tick_time.get(symbol, datetime.now(timezone.utc))
        }
        
        # Add available price data
        if 'BID' in market_data:
            result['bid'] = market_data['BID']
        if 'ASK' in market_data:
            result['ask'] = market_data['ASK']
        if 'LAST' in market_data:
            result['last'] = market_data['LAST']
        
        # Add available size data
        if 'BID_SIZE' in market_data:
            result['bid_size'] = market_data['BID_SIZE']
        if 'ASK_SIZE' in market_data:
            result['ask_size'] = market_data['ASK_SIZE']
        if 'LAST_SIZE' in market_data:
            result['last_size'] = market_data['LAST_SIZE']
        
        return result
    
    def __del__(self):
        """Clean up resources."""
        self.disconnect()