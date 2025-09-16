"""News event filter for risk management.

This module provides functionality to filter out trading during major news events
using data from ForexFactory calendar and FRED API.
"""

import datetime
import json
import logging
import os
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple, Union

import pandas as pd
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class NewsEventFilter:
    """Filter for major news events.
    
    This class provides functionality to filter out trading during major news events
    using data from ForexFactory calendar and FRED API.
    """
    
    def __init__(
        self,
        high_impact_only: bool = True,
        event_buffer_before: int = 60,  # minutes before event
        event_buffer_after: int = 60,  # minutes after event
        currency_specific: bool = True,
        cache_duration: int = 24,  # hours
        cache_file: str = "news_events_cache.json",
    ):
        """Initialize the news event filter.
        
        Args:
            high_impact_only: Only filter high impact events if True.
            event_buffer_before: Minutes to avoid trading before event.
            event_buffer_after: Minutes to avoid trading after event.
            currency_specific: Only filter events for specific currency pairs.
            cache_duration: Hours to cache the fetched calendar data.
            cache_file: File to cache the fetched calendar data.
        """
        self.high_impact_only = high_impact_only
        self.event_buffer_before = event_buffer_before
        self.event_buffer_after = event_buffer_after
        self.currency_specific = currency_specific
        self.cache_duration = cache_duration
        self.cache_file = cache_file
        
        # Dictionary to store events by date
        self.events_by_date = {}
        self.last_cache_update = None
        
        # Map of currency pairs to currencies
        self.currency_map = {
            "EURUSD": ["EUR", "USD"],
            "GBPUSD": ["GBP", "USD"],
            "USDJPY": ["USD", "JPY"],
            "USDCHF": ["USD", "CHF"],
            "AUDUSD": ["AUD", "USD"],
            "NZDUSD": ["NZD", "USD"],
            "USDCAD": ["USD", "CAD"],
            "EURGBP": ["EUR", "GBP"],
            "EURJPY": ["EUR", "JPY"],
            "GBPJPY": ["GBP", "JPY"],
        }
        
        # Try to load cache on initialization
        self._load_cache()
    
    def _load_cache(self) -> None:
        """Load cached news events."""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, "r") as f:
                    cache_data = json.load(f)
                
                self.events_by_date = cache_data.get("events", {})
                
                # Convert string dates back to datetime objects
                self.events_by_date = {
                    datetime.fromisoformat(date_str): events
                    for date_str, events in self.events_by_date.items()
                }
                
                cache_time = datetime.fromisoformat(cache_data.get("timestamp", ""))
                self.last_cache_update = cache_time
                
                # Check if cache is still valid
                if (datetime.now() - cache_time).total_seconds() > self.cache_duration * 3600:
                    logger.info("Cache expired, will fetch fresh data")
                    self.events_by_date = {}
                    self.last_cache_update = None
                else:
                    logger.info("Loaded news events from cache")
        except Exception as e:
            logger.warning(f"Error loading cache: {e}")
            self.events_by_date = {}
            self.last_cache_update = None
    
    def _save_cache(self) -> None:
        """Save news events to cache."""
        try:
            # Convert datetime keys to strings for JSON serialization
            events_str_keys = {
                date.isoformat(): events
                for date, events in self.events_by_date.items()
            }
            
            cache_data = {
                "timestamp": datetime.now().isoformat(),
                "events": events_str_keys,
            }
            
            with open(self.cache_file, "w") as f:
                json.dump(cache_data, f, indent=2)
            
            logger.info("Saved news events to cache")
        except Exception as e:
            logger.warning(f"Error saving cache: {e}")
    
    def fetch_forexfactory_calendar(
        self, 
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[Dict]:
        """Fetch economic calendar from ForexFactory using ScraperAPI.
        
        Args:
            start_date: Start date for the calendar (defaults to today).
            end_date: End date for the calendar (defaults to 7 days from start).
            
        Returns:
            List of events from the calendar.
        """
        # Default date range is today to 7 days from now
        if start_date is None:
            start_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        if end_date is None:
            end_date = start_date + timedelta(days=7)
        
        # Format dates for URL
        month_year_strs = []
        current = start_date
        
        while current <= end_date:
            month_year = current.strftime("%b%Y").lower()
            if month_year not in month_year_strs:
                month_year_strs.append(month_year)
            current += timedelta(days=32)
            current = current.replace(day=1)
        
        all_events = []
        
        for month_year in month_year_strs:
            url = f"https://www.forexfactory.com/calendar?month={month_year}"
            events = self._scrape_forexfactory_page(url)
            all_events.extend(events)
        
        # Filter events by date range
        filtered_events = [
            event for event in all_events
            if start_date <= event["datetime"] <= end_date
        ]
        
        return filtered_events
    
    def _scrape_forexfactory_page(self, url: str) -> List[Dict]:
        """Scrape a single ForexFactory calendar page.
        
        Args:
            url: URL to scrape.
            
        Returns:
            List of events from the page.
        """
        logger.info(f"Fetching calendar data from {url}")
        
        # Use ScraperAPI to handle the scraping
        api_key = os.getenv("SCRAPER_API_KEY")
        if not api_key:
            raise ValueError("SCRAPER_API_KEY not found in environment variables")
        
        scraper_url = f"http://api.scraperapi.com?api_key={api_key}&url={url}&render=true"
        
        try:
            response = requests.get(scraper_url)
            response.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"Error fetching calendar: {e}")
            return []
        
        # Parse the HTML
        soup = BeautifulSoup(response.content, "html.parser")
        
        # Extract event rows
        events = []
        current_date = None
        
        # Find the calendar table
        calendar_table = soup.find("table", class_="calendar__table")
        if not calendar_table:
            logger.warning("Calendar table not found")
            return []
        
        # Extract the year from the calendar
        year_elem = soup.find("div", class_="calendar__options__dates")
        year = datetime.now().year
        if year_elem:
            year_match = re.search(r'\b\d{4}\b', year_elem.text)
            if year_match:
                year = int(year_match.group(0))
        
        # Process each row
        rows = calendar_table.find_all("tr", class_="calendar__row")
        for row in rows:
            # Check if this row contains a date
            date_cell = row.find("td", class_="calendar__cell--date")
            if date_cell and date_cell.text.strip():
                date_text = date_cell.text.strip()
                
                # Try to parse the date
                try:
                    # Format is typically like "Mon Sep 11"
                    month_day = date_text.split()[1:]
                    if len(month_day) >= 2:
                        month_str = month_day[0]
                        day_str = month_day[1]
                        month_mapping = {
                            "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4,
                            "May": 5, "Jun": 6, "Jul": 7, "Aug": 8,
                            "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12
                        }
                        month = month_mapping.get(month_str, 1)
                        day = int(day_str)
                        current_date = datetime(year, month, day)
                except Exception as e:
                    logger.warning(f"Error parsing date {date_text}: {e}")
                    continue
            
            # Skip rows without a valid date
            if not current_date:
                continue
            
            # Extract event details
            time_cell = row.find("td", class_="calendar__cell--time")
            currency_cell = row.find("td", class_="calendar__cell--currency")
            impact_cell = row.find("td", class_="calendar__cell--impact")
            event_cell = row.find("td", class_="calendar__cell--event")
            
            # Skip rows without key cells
            if not all([time_cell, currency_cell, impact_cell, event_cell]):
                continue
            
            # Get time
            time_text = time_cell.text.strip()
            event_time = None
            
            if time_text and time_text != "All Day" and time_text != "Tentative":
                try:
                    # Handle various time formats
                    if ":" in time_text:
                        hour, minute = map(int, time_text.split(":"))
                        # Adjust for PM times without explicit AM/PM
                        if hour < 12 and "pm" in time_text.lower():
                            hour += 12
                        event_time = current_date.replace(hour=hour, minute=minute)
                    else:
                        # Just hour, no minutes
                        hour = int(time_text.replace("am", "").replace("pm", "").strip())
                        if hour < 12 and "pm" in time_text.lower():
                            hour += 12
                        event_time = current_date.replace(hour=hour, minute=0)
                except Exception as e:
                    logger.warning(f"Error parsing time {time_text}: {e}")
                    event_time = current_date  # Default to day's start
            else:
                # Default for "All Day" or "Tentative"
                event_time = current_date
            
            # Get currency
            currency = currency_cell.text.strip()
            
            # Get impact level
            impact = "low"
            impact_span = impact_cell.find("span")
            if impact_span:
                impact_class = impact_span.get("class", [""])[0]
                if "high" in impact_class:
                    impact = "high"
                elif "medium" in impact_class:
                    impact = "medium"
            
            # Get event title
            event_title = event_cell.text.strip()
            
            # Create event entry
            event = {
                "datetime": event_time,
                "currency": currency,
                "impact": impact,
                "title": event_title
            }
            
            events.append(event)
        
        return events
    
    def update_calendar(self) -> bool:
        """Update the news event calendar.
        
        Returns:
            True if successful, False otherwise.
        """
        try:
            # Determine if we need to update based on cache
            now = datetime.now()
            if (self.last_cache_update and 
                (now - self.last_cache_update).total_seconds() < self.cache_duration * 3600):
                logger.info("Using cached news events")
                return True
            
            # Fetch new events
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = start_date + timedelta(days=14)  # Get two weeks of data
            
            events = self.fetch_forexfactory_calendar(start_date, end_date)
            
            # Group events by date
            self.events_by_date = {}
            for event in events:
                event_date = event["datetime"].replace(hour=0, minute=0, second=0, microsecond=0)
                if event_date not in self.events_by_date:
                    self.events_by_date[event_date] = []
                self.events_by_date[event_date].append(event)
            
            self.last_cache_update = now
            
            # Save to cache
            self._save_cache()
            
            return True
        except Exception as e:
            logger.error(f"Error updating calendar: {e}")
            return False
    
    def is_news_event_time(
        self,
        timestamp: datetime,
        symbol: Optional[str] = None,
    ) -> Tuple[bool, List[Dict]]:
        """Check if given timestamp is during a major news event.
        
        Args:
            timestamp: Time to check.
            symbol: Symbol to check for currency-specific events.
            
        Returns:
            Tuple of (is_event_time, relevant_events).
        """
        # Make sure calendar is up to date
        if not self.events_by_date or self.last_cache_update is None:
            self.update_calendar()
        
        # Check if we need to refresh the cache
        now = datetime.now()
        if (self.last_cache_update and 
            (now - self.last_cache_update).total_seconds() >= self.cache_duration * 3600):
            self.update_calendar()
        
        # Get date of the timestamp
        date = timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # No events for this date
        if date not in self.events_by_date:
            return False, []
        
        relevant_events = []
        
        # Check each event
        for event in self.events_by_date[date]:
            # Skip low impact events if high_impact_only is True
            if self.high_impact_only and event["impact"] != "high":
                continue
            
            # Check if event is currency-specific and relevant to the symbol
            if self.currency_specific and symbol:
                event_currency = event["currency"]
                
                # Get currencies in the symbol
                symbol_currencies = self.currency_map.get(symbol, [])
                
                # Skip if event currency is not in the symbol currencies
                if event_currency not in symbol_currencies:
                    continue
            
            # Calculate event buffer window
            event_time = event["datetime"]
            buffer_before = event_time - timedelta(minutes=self.event_buffer_before)
            buffer_after = event_time + timedelta(minutes=self.event_buffer_after)
            
            # Check if timestamp is within buffer window
            if buffer_before <= timestamp <= buffer_after:
                relevant_events.append(event)
        
        return len(relevant_events) > 0, relevant_events
    
    def get_upcoming_events(
        self,
        from_time: Optional[datetime] = None,
        days_ahead: int = 3,
        symbol: Optional[str] = None,
    ) -> List[Dict]:
        """Get upcoming news events.
        
        Args:
            from_time: Starting time (defaults to now).
            days_ahead: Number of days to look ahead.
            symbol: Symbol to check for currency-specific events.
            
        Returns:
            List of upcoming events.
        """
        if from_time is None:
            from_time = datetime.now()
        
        # Make sure calendar is up to date
        if not self.events_by_date or self.last_cache_update is None:
            self.update_calendar()
        
        end_time = from_time + timedelta(days=days_ahead)
        
        all_events = []
        
        # Loop through dates in range
        current_date = from_time.replace(hour=0, minute=0, second=0, microsecond=0)
        while current_date <= end_time:
            if current_date in self.events_by_date:
                for event in self.events_by_date[current_date]:
                    # Skip if before from_time
                    if event["datetime"] < from_time:
                        continue
                    
                    # Skip low impact events if high_impact_only is True
                    if self.high_impact_only and event["impact"] != "high":
                        continue
                    
                    # Check if event is currency-specific and relevant to the symbol
                    if self.currency_specific and symbol:
                        event_currency = event["currency"]
                        
                        # Get currencies in the symbol
                        symbol_currencies = self.currency_map.get(symbol, [])
                        
                        # Skip if event currency is not in the symbol currencies
                        if event_currency not in symbol_currencies:
                            continue
                    
                    all_events.append(event)
            
            current_date += timedelta(days=1)
        
        # Sort events by time
        return sorted(all_events, key=lambda x: x["datetime"])


# FRED API integration for economic data
class FredEconomicCalendar:
    """FRED API integration for economic data."""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize FRED API client.
        
        Args:
            api_key: FRED API key.
        """
        self.api_key = api_key or os.getenv("FRED_API_KEY")
        if not self.api_key:
            logger.warning("FRED_API_KEY not found in environment variables")
        
        self.base_url = "https://api.stlouisfed.org/fred"
    
    def fetch_release_dates(
        self,
        release_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict]:
        """Fetch release dates for a specific economic release.
        
        Args:
            release_id: FRED release ID.
            start_date: Start date (YYYY-MM-DD).
            end_date: End date (YYYY-MM-DD).
            
        Returns:
            List of release dates.
        """
        if not self.api_key:
            logger.error("FRED API key is required")
            return []
        
        # Default date range is last 30 days to 30 days from now
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        
        if not end_date:
            end_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        
        # Build URL
        url = f"{self.base_url}/release/dates"
        params = {
            "release_id": release_id,
            "realtime_start": start_date,
            "realtime_end": end_date,
            "api_key": self.api_key,
            "file_type": "json",
        }
        
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            # Extract release dates
            return data.get("release_dates", [])
        except requests.RequestException as e:
            logger.error(f"Error fetching FRED release dates: {e}")
            return []
    
    def get_releases(self) -> List[Dict]:
        """Get list of available releases.
        
        Returns:
            List of releases.
        """
        if not self.api_key:
            logger.error("FRED API key is required")
            return []
        
        url = f"{self.base_url}/releases"
        params = {
            "api_key": self.api_key,
            "file_type": "json",
        }
        
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            return data.get("releases", [])
        except requests.RequestException as e:
            logger.error(f"Error fetching FRED releases: {e}")
            return []
    
    # Key U.S. economic releases for forex traders
    US_NONFARM_PAYROLLS = "151"  # Employment Situation
    US_CPI = "10"  # Consumer Price Index
    US_RETAIL_SALES = "5"  # Retail Sales
    US_GDP = "3"  # Gross Domestic Product
    US_FOMC = "180"  # FOMC Meeting


# Integrated news filter for risk management
class SpreadAnalyzer:
    """Analyzer for detecting abnormal spread conditions."""
    
    def __init__(
        self,
        lookback_window: int = 100,
        threshold_stdevs: float = 2.0,
        min_data_points: int = 20,
    ):
        """Initialize the spread analyzer.
        
        Args:
            lookback_window: Number of bars to use for spread statistics.
            threshold_stdevs: How many standard deviations above mean is considered wide.
            min_data_points: Minimum data points required to compute statistics.
        """
        self.lookback_window = lookback_window
        self.threshold_stdevs = threshold_stdevs
        self.min_data_points = min_data_points
        
        # Cached statistics per symbol
        self.spread_stats = {}
    
    def update_stats(self, symbol: str, market_data: pd.DataFrame) -> None:
        """Update spread statistics for a symbol.
        
        Args:
            symbol: Market symbol.
            market_data: Market data with high and low prices.
        """
        if len(market_data) < self.min_data_points:
            return
        
        # Calculate spreads using high-low difference as proxy
        # In real systems with bid-ask data, would use actual spreads
        recent_data = market_data.iloc[-self.lookback_window:]
        
        # Use high-low as proxy, or calculate other spread estimate
        spreads = (recent_data["high"] - recent_data["low"]) / recent_data["close"] * 10000  # In pips
        
        # Calculate statistics
        mean_spread = spreads.mean()
        std_spread = spreads.std()
        
        self.spread_stats[symbol] = {
            "mean": mean_spread,
            "std": std_spread,
            "threshold": mean_spread + (std_spread * self.threshold_stdevs),
            "last_update": datetime.now(),
        }
    
    def is_spread_abnormal(
        self, 
        symbol: str, 
        current_bar: pd.Series,
        market_data: Optional[pd.DataFrame] = None,
    ) -> Tuple[bool, float]:
        """Check if current spread is abnormally high.
        
        Args:
            symbol: Market symbol.
            current_bar: Current price bar.
            market_data: Historical market data (to update stats if needed).
            
        Returns:
            Tuple of (is_abnormal, spread_z_score).
        """
        # Update stats if needed and market data is provided
        if market_data is not None and (
            symbol not in self.spread_stats or 
            (datetime.now() - self.spread_stats[symbol].get("last_update", datetime.min)).total_seconds() > 3600
        ):
            self.update_stats(symbol, market_data)
        
        # If no stats are available, return False (not abnormal)
        if symbol not in self.spread_stats:
            return False, 0.0
        
        # Calculate current spread (high-low as proxy)
        current_spread = (current_bar["high"] - current_bar["low"]) / current_bar["close"] * 10000  # In pips
        
        # Get stored statistics
        stats = self.spread_stats[symbol]
        mean_spread = stats["mean"]
        std_spread = stats["std"]
        threshold = stats["threshold"]
        
        # Calculate z-score
        z_score = (current_spread - mean_spread) / std_spread if std_spread > 0 else 0
        
        # Check if current spread exceeds threshold
        is_abnormal = current_spread > threshold
        
        return is_abnormal, z_score


class IntegratedNewsFilter:
    """Integrated news filter using both ForexFactory and FRED data."""
    
    def __init__(
        self,
        high_impact_only: bool = True,
        event_buffer_before: int = 120,  # minutes before event
        event_buffer_after: int = 60,  # minutes after event
        currency_specific: bool = True,
        scheduled_updates: bool = True,
        update_interval_hours: int = 12,
        spread_analyzer: Optional[SpreadAnalyzer] = None,
    ):
        """Initialize integrated news filter.
        
        Args:
            high_impact_only: Only filter high impact events if True.
            event_buffer_before: Minutes to avoid trading before event.
            event_buffer_after: Minutes to avoid trading after event.
            currency_specific: Only filter events for specific currency pairs.
            scheduled_updates: Whether to automatically schedule updates.
            update_interval_hours: How often to update the calendar data.
            spread_analyzer: Analyzer for detecting abnormal spread conditions.
        """
        self.forex_factory = NewsEventFilter(
            high_impact_only=high_impact_only,
            event_buffer_before=event_buffer_before,
            event_buffer_after=event_buffer_after,
            currency_specific=currency_specific,
        )
        
        self.fred = FredEconomicCalendar()
        
        # Key economic releases to monitor
        self.key_releases = {
            "NFP": self.fred.US_NONFARM_PAYROLLS,
            "CPI": self.fred.US_CPI,
            "Retail Sales": self.fred.US_RETAIL_SALES,
            "GDP": self.fred.US_GDP,
            "FOMC": self.fred.US_FOMC,
        }
        
        # Cache for FRED release dates
        self.fred_release_cache = {}
        
        # Spread analyzer for detecting abnormal spreads
        self.spread_analyzer = spread_analyzer or SpreadAnalyzer()
        
        # Scheduled updates
        self.scheduled_updates = scheduled_updates
        self.update_interval_hours = update_interval_hours
        self.last_scheduled_update = None
        
        # Initialize with first update
        if self.scheduled_updates:
            self.update_calendars()
            self.last_scheduled_update = datetime.now()
    
    def update_calendars(self) -> bool:
        """Update both calendars.
        
        Returns:
            True if successful, False otherwise.
        """
        # Update ForexFactory calendar
        ff_success = self.forex_factory.update_calendar()
        
        # Update FRED release dates for key releases
        fred_success = True
        
        if self.fred.api_key:
            for name, release_id in self.key_releases.items():
                try:
                    dates = self.fred.fetch_release_dates(release_id)
                    self.fred_release_cache[name] = dates
                except Exception as e:
                    logger.error(f"Error fetching {name} release dates: {e}")
                    fred_success = False
        
        return ff_success and fred_success
    
    def is_news_event_time(
        self,
        timestamp: datetime,
        symbol: Optional[str] = None,
        current_bar: Optional[pd.Series] = None,
        market_data: Optional[pd.DataFrame] = None,
    ) -> Tuple[bool, List[Dict], Optional[str]]:
        """Check if given timestamp is during a major news event.
        
        Args:
            timestamp: Time to check.
            symbol: Symbol to check for currency-specific events.
            current_bar: Current price bar for spread analysis.
            market_data: Historical market data for spread analysis.
            
        Returns:
            Tuple of (is_event_time, relevant_events, reason).
        """
        # Check if scheduled update is needed
        if self.scheduled_updates and self.last_scheduled_update:
            hours_since_update = (timestamp - self.last_scheduled_update).total_seconds() / 3600
            if hours_since_update >= self.update_interval_hours:
                logger.info("Performing scheduled news calendar update")
                self.update_calendars()
                self.last_scheduled_update = timestamp
        
        # Check ForexFactory calendar
        is_event, events = self.forex_factory.is_news_event_time(timestamp, symbol)
        
        # If already an event time, no need to check further
        if is_event:
            return True, events, "high_impact_news"
        
        # Check FRED releases
        fred_events = []
        
        for name, release_dates in self.fred_release_cache.items():
            for release in release_dates:
                release_date_str = release.get("date")
                
                if not release_date_str:
                    continue
                
                try:
                    release_date = datetime.strptime(release_date_str, "%Y-%m-%d")
                    
                    # Set a default release time (typically 8:30 AM ET)
                    release_time = release_date.replace(hour=8, minute=30)
                    
                    # Calculate buffer window
                    buffer_before = release_time - timedelta(minutes=self.forex_factory.event_buffer_before)
                    buffer_after = release_time + timedelta(minutes=self.forex_factory.event_buffer_after)
                    
                    # Check if timestamp is within buffer window
                    if buffer_before <= timestamp <= buffer_after:
                        # Check currency relevance for USD pairs
                        if self.forex_factory.currency_specific and symbol:
                            symbol_currencies = self.forex_factory.currency_map.get(symbol, [])
                            
                            # Most FRED releases are USD-related
                            if "USD" not in symbol_currencies:
                                continue
                        
                        fred_events.append({
                            "datetime": release_time,
                            "currency": "USD",
                            "impact": "high",
                            "title": f"FRED: {name}",
                        })
                except Exception as e:
                    logger.warning(f"Error processing FRED release date {release_date_str}: {e}")
        
        if fred_events:
            return True, fred_events, "economic_release"
        
        # If we have current bar and market data, check for abnormal spreads
        if current_bar is not None and symbol is not None:
            is_abnormal, z_score = self.spread_analyzer.is_spread_abnormal(
                symbol, current_bar, market_data
            )
            
            if is_abnormal:
                # Create a pseudo-event to represent the abnormal spread
                spread_events = [{
                    "datetime": timestamp,
                    "currency": symbol,
                    "impact": "high",
                    "title": f"Abnormal Spread (z-score: {z_score:.2f})",
                }]
                
                return True, spread_events, "abnormal_spread"
        
        return False, [], None
    
    def get_upcoming_events(
        self,
        from_time: Optional[datetime] = None,
        days_ahead: int = 7,
        symbol: Optional[str] = None,
    ) -> List[Dict]:
        """Get upcoming news events from both sources.
        
        Args:
            from_time: Starting time (defaults to now).
            days_ahead: Number of days to look ahead.
            symbol: Symbol to check for currency-specific events.
            
        Returns:
            List of upcoming events.
        """
        # Get events from ForexFactory
        ff_events = self.forex_factory.get_upcoming_events(from_time, days_ahead, symbol)
        
        # Get events from FRED
        fred_events = []
        
        if from_time is None:
            from_time = datetime.now()
        
        end_time = from_time + timedelta(days=days_ahead)
        
        for name, release_dates in self.fred_release_cache.items():
            for release in release_dates:
                release_date_str = release.get("date")
                
                if not release_date_str:
                    continue
                
                try:
                    release_date = datetime.strptime(release_date_str, "%Y-%m-%d")
                    
                    # Set a default release time (typically 8:30 AM ET)
                    release_time = release_date.replace(hour=8, minute=30)
                    
                    # Skip if outside time range
                    if release_time < from_time or release_time > end_time:
                        continue
                    
                    # Check currency relevance for USD pairs
                    if self.forex_factory.currency_specific and symbol:
                        symbol_currencies = self.forex_factory.currency_map.get(symbol, [])
                        
                        # Most FRED releases are USD-related
                        if "USD" not in symbol_currencies:
                            continue
                    
                    fred_events.append({
                        "datetime": release_time,
                        "currency": "USD",
                        "impact": "high",
                        "title": f"FRED: {name}",
                    })
                except Exception as e:
                    logger.warning(f"Error processing FRED release date {release_date_str}: {e}")
        
        # Combine and sort all events
        all_events = ff_events + fred_events
        return sorted(all_events, key=lambda x: x["datetime"])