"""
Realistic Market Data Service for UAT.

Provides realistic market data that looks like current market conditions
when live data sources are not available.
"""

import asyncio
import logging
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import requests

from .market_data import MarketDataPoint

logger = logging.getLogger(__name__)


class RealisticMarketDataService:
    """Service providing realistic market data for UAT."""

    def __init__(self):
        self.current_prices = {}
        self.last_update = {}
        self._initialize_current_prices()

    def _initialize_current_prices(self):
        """Initialize with realistic current market prices."""
        # Use approximate current market rates (as of late 2025)
        self.current_prices = {
            "EURUSD": 1.0450,
            "GBPUSD": 1.2720,
            "USDJPY": 149.85,
            "USDCHF": 0.8890,
            "AUDUSD": 0.6234,
            "USDCAD": 1.4456,
            "NZDUSD": 0.5678,
            "EURGBP": 0.8234,
        }

        now = datetime.utcnow()
        for symbol in self.current_prices:
            self.last_update[symbol] = now

    async def get_realistic_forex_data(
        self, symbol: str, timeframe: str = "1h", limit: int = 100
    ) -> List[MarketDataPoint]:
        """Get realistic forex data that looks like current market conditions."""
        try:
            # Try to get real current price first
            await self._update_current_price(symbol)

            base_price = self.current_prices.get(symbol, 1.0000)

            # Generate realistic historical data leading up to current price
            data_points = []

            # Calculate time intervals
            interval_minutes = self._get_interval_minutes(timeframe)
            current_time = datetime.utcnow()

            # Start from older time and work forward
            start_time = current_time - timedelta(minutes=interval_minutes * limit)

            # Generate realistic price movement
            current_price = base_price * (
                1 + random.uniform(-0.02, 0.02)
            )  # Start with +/- 2% variation

            for i in range(limit):
                # Calculate timestamp
                timestamp = start_time + timedelta(minutes=interval_minutes * i)

                # Generate realistic OHLC data
                open_price = current_price

                # Price movement based on timeframe (higher volatility for longer timeframes)
                if timeframe in ["1d"]:
                    max_change = 0.015  # 1.5% max change per day
                elif timeframe in ["4h"]:
                    max_change = 0.008  # 0.8% max change per 4h
                elif timeframe in ["1h"]:
                    max_change = 0.003  # 0.3% max change per hour
                else:
                    max_change = 0.001  # 0.1% max change per minute

                # Random walk with slight trend
                change_pct = random.uniform(-max_change, max_change)

                # Add some trend (slight bias towards current actual price)
                if i > limit * 0.7:  # Last 30% of data points trend towards current
                    trend_factor = (base_price - current_price) / base_price * 0.1
                    change_pct += trend_factor

                close_price = open_price * (1 + change_pct)

                # Generate high/low
                spread = abs(close_price - open_price) * random.uniform(1.2, 2.5)
                high_price = max(open_price, close_price) + spread * random.uniform(
                    0.3, 0.8
                )
                low_price = min(open_price, close_price) - spread * random.uniform(
                    0.3, 0.8
                )

                # Generate realistic volume (higher during market hours)
                base_volume = self._get_realistic_volume(symbol, timeframe, timestamp)
                volume = int(base_volume * random.uniform(0.5, 1.8))

                # Create data point
                data_point = MarketDataPoint(
                    time=timestamp,
                    symbol=symbol,
                    open=round(open_price, 5),
                    high=round(high_price, 5),
                    low=round(low_price, 5),
                    close=round(close_price, 5),
                    volume=volume,
                    tick_count=random.randint(50, 300),
                    source="realistic_uat",
                )
                data_points.append(data_point)

                # Update current price for next iteration
                current_price = close_price

            # Ensure the last price is close to our target current price
            if data_points:
                last_point = data_points[-1]
                adjusted_close = base_price * random.uniform(
                    0.999, 1.001
                )  # Very close to actual
                data_points[-1] = MarketDataPoint(
                    time=last_point.time,
                    symbol=last_point.symbol,
                    open=last_point.open,
                    high=max(last_point.high, adjusted_close),
                    low=min(last_point.low, adjusted_close),
                    close=round(adjusted_close, 5),
                    volume=last_point.volume,
                    tick_count=last_point.tick_count,
                    source=last_point.source,
                )

            logger.info(
                f"Generated {len(data_points)} realistic data points for {symbol}"
            )
            return data_points

        except Exception as e:
            logger.error(f"Error generating realistic data for {symbol}: {e}")
            return []

    async def _update_current_price(self, symbol: str):
        """Try to get current price from free API source."""
        try:
            # Use a free API to get current rates (example: exchangerate-api.com free tier)
            # This is for demonstration - in production you'd use your premium data source

            if symbol == "EURUSD":
                # Try to get current EUR/USD rate from a free source
                response = await asyncio.to_thread(
                    requests.get,
                    "https://api.exchangerate-api.com/v4/latest/EUR",
                    timeout=2,
                )
                if response.status_code == 200:
                    data = response.json()
                    if "rates" in data and "USD" in data["rates"]:
                        current_rate = float(data["rates"]["USD"])
                        self.current_prices[symbol] = current_rate
                        self.last_update[symbol] = datetime.utcnow()
                        logger.info(f"Updated {symbol} current price to {current_rate}")

        except Exception as e:
            # Silently fail and use existing price
            logger.debug(f"Could not update current price for {symbol}: {e}")

    def _get_interval_minutes(self, timeframe: str) -> int:
        """Convert timeframe to minutes."""
        mapping = {
            "1m": 1,
            "5m": 5,
            "15m": 15,
            "30m": 30,
            "1h": 60,
            "4h": 240,
            "1d": 1440,
        }
        return mapping.get(timeframe, 60)

    def _get_realistic_volume(
        self, symbol: str, timeframe: str, timestamp: datetime
    ) -> int:
        """Generate realistic volume based on symbol, timeframe and time."""
        # Base volumes (approximate realistic ranges)
        base_volumes = {
            "EURUSD": 50000,
            "GBPUSD": 35000,
            "USDJPY": 40000,
            "USDCHF": 25000,
            "AUDUSD": 20000,
            "USDCAD": 18000,
            "NZDUSD": 12000,
            "EURGBP": 15000,
        }

        base_volume = base_volumes.get(symbol, 20000)

        # Adjust for timeframe
        if timeframe == "1d":
            base_volume *= 24
        elif timeframe == "4h":
            base_volume *= 4
        elif timeframe == "1h":
            base_volume *= 1
        else:
            base_volume //= 60  # For minute timeframes

        # Adjust for market hours (higher during London/NY overlap)
        hour = timestamp.hour
        if 13 <= hour <= 17:  # London/NY overlap (UTC)
            base_volume *= 1.8
        elif 8 <= hour <= 17:  # London hours
            base_volume *= 1.4
        elif 0 <= hour <= 4:  # Low activity
            base_volume *= 0.6

        return max(100, base_volume)


# Create singleton instance
realistic_market_data_service = RealisticMarketDataService()
