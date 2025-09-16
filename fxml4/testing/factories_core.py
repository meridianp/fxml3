"""Advanced test data factories for reproducible and realistic test data."""

import hashlib
import logging
import random
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class VersionedDataFactory:
    """Creates versioned, reproducible test data."""

    def __init__(self):
        self.versions = {}
        self.data_cache = {}

    def create_market_data(
        self, version: str = "1.0", seed: int = 42, **kwargs
    ) -> pd.DataFrame:
        """Create versioned market data."""
        cache_key = self._get_cache_key(version, seed, kwargs)

        if cache_key in self.data_cache:
            return self.data_cache[cache_key].copy()

        # Set seed for reproducibility
        np.random.seed(seed)
        random.seed(seed)

        # Version-specific generation logic
        if version == "1.0":
            data = self._generate_market_data_v1(**kwargs)
        elif version == "2.0":
            data = self._generate_market_data_v2(**kwargs)
        else:
            raise ValueError(f"Unknown version: {version}")

        self.versions[version] = True
        self.data_cache[cache_key] = data.copy()

        return data

    def get_available_versions(self) -> List[str]:
        """Get list of available data versions."""
        return list(self.versions.keys())

    def _get_cache_key(self, version: str, seed: int, kwargs: Dict) -> str:
        """Generate cache key for data."""
        key_data = f"{version}_{seed}_{sorted(kwargs.items())}"
        return hashlib.md5(key_data.encode()).hexdigest()

    def _generate_market_data_v1(self, periods: int = 100, **kwargs) -> pd.DataFrame:
        """Generate market data version 1.0."""
        dates = pd.date_range(start="2024-01-01", periods=periods, freq="1H")

        # Simple random walk
        returns = np.random.normal(0, 0.01, periods)
        prices = 1.1000 + np.cumsum(returns)

        return pd.DataFrame(
            {
                "timestamp": dates,
                "open": prices,
                "high": prices * (1 + np.random.uniform(0, 0.01, periods)),
                "low": prices * (1 - np.random.uniform(0, 0.01, periods)),
                "close": prices,
                "volume": np.random.randint(1000, 10000, periods),
            }
        )

    def _generate_market_data_v2(self, periods: int = 100, **kwargs) -> pd.DataFrame:
        """Generate market data version 2.0 (more realistic)."""
        dates = pd.date_range(start="2024-01-01", periods=periods, freq="1H")

        # More sophisticated price model with volatility clustering
        volatility = np.random.gamma(2, 0.5, periods) * 0.01
        returns = np.random.normal(0, volatility)
        prices = 1.1000 * np.exp(np.cumsum(returns))

        return pd.DataFrame(
            {
                "timestamp": dates,
                "open": prices,
                "high": prices * (1 + volatility),
                "low": prices * (1 - volatility),
                "close": prices,
                "volume": np.random.poisson(5000, periods) + 1000,
                "volatility": volatility,
            }
        )


class RealisticDataFactory:
    """Creates realistic test data matching production patterns."""

    def create_realistic_market_data(
        self,
        symbol: str = "EURUSD",
        start_date: str = "2024-01-01",
        days: int = 30,
        market_conditions: str = "normal",
    ) -> pd.DataFrame:
        """Create realistic market data with specified conditions."""

        periods = days * 24  # Hourly data
        dates = pd.date_range(start=start_date, periods=periods, freq="1H")

        if market_conditions == "trending":
            data = self._create_trending_market(dates, symbol)
        elif market_conditions == "sideways":
            data = self._create_sideways_market(dates, symbol)
        else:
            data = self._create_normal_market(dates, symbol)

        return data

    def _create_trending_market(
        self, dates: pd.DatetimeIndex, symbol: str
    ) -> pd.DataFrame:
        """Create trending market data."""
        periods = len(dates)

        # Strong trend with occasional pullbacks
        trend = np.linspace(0, 0.05, periods)  # 5% trend over period
        noise = np.random.normal(0, 0.002, periods)

        # Add pullbacks every ~50 periods
        pullbacks = np.zeros(periods)
        for i in range(50, periods, 50):
            pullback_size = 0.01
            pullback_length = 10
            start_idx = min(i, periods - pullback_length)
            pullbacks[start_idx : start_idx + pullback_length] = -pullback_size

        returns = trend / periods + noise + pullbacks / periods
        prices = 1.1000 * np.exp(np.cumsum(returns))

        return self._create_ohlc_from_prices(dates, symbol, prices)

    def _create_sideways_market(
        self, dates: pd.DatetimeIndex, symbol: str
    ) -> pd.DataFrame:
        """Create sideways/ranging market data."""
        periods = len(dates)

        # Mean-reverting price action
        mean_price = 1.1000
        noise = np.random.normal(0, 0.001, periods)

        # Add mean reversion
        prices = np.zeros(periods)
        prices[0] = mean_price

        for i in range(1, periods):
            # Mean reversion force
            reversion = -0.1 * (prices[i - 1] - mean_price)
            prices[i] = prices[i - 1] + reversion + noise[i]

        return self._create_ohlc_from_prices(dates, symbol, prices)

    def _create_normal_market(
        self, dates: pd.DatetimeIndex, symbol: str
    ) -> pd.DataFrame:
        """Create normal market conditions."""
        periods = len(dates)

        # Random walk with realistic volatility
        returns = np.random.normal(0, 0.005, periods)
        prices = 1.1000 * np.exp(np.cumsum(returns))

        return self._create_ohlc_from_prices(dates, symbol, prices)

    def _create_ohlc_from_prices(
        self, dates: pd.DatetimeIndex, symbol: str, prices: np.ndarray
    ) -> pd.DataFrame:
        """Create OHLC data from price series."""
        periods = len(prices)

        # Generate realistic OHLC with proper relationships
        spread = np.random.uniform(0.0001, 0.001, periods)

        high = prices + spread * np.random.uniform(0.3, 1.0, periods)
        low = prices - spread * np.random.uniform(0.3, 1.0, periods)

        # Ensure OHLC relationships are valid
        open_prices = np.roll(prices, 1)
        open_prices[0] = prices[0]

        return pd.DataFrame(
            {
                "timestamp": dates,
                "symbol": symbol,
                "open": open_prices,
                "high": np.maximum.reduce([open_prices, high, prices]),
                "low": np.minimum.reduce([open_prices, low, prices]),
                "close": prices,
                "volume": np.random.poisson(5000, periods) + 1000,
                "volatility": np.abs(
                    np.diff(np.log(prices), prepend=np.log(prices[0]))
                ),
            }
        ).set_index("timestamp")


class RelationalDataFactory:
    """Creates test data with proper relationships and constraints."""

    def create_accounts(self, count: int = 5) -> pd.DataFrame:
        """Create account test data."""
        accounts = []

        for i in range(count):
            account_id = f"ACC_{i:06d}"
            accounts.append(
                {
                    "id": account_id,
                    "name": f"Account {i+1}",
                    "balance": round(random.uniform(10000, 100000), 2),
                    "currency": "USD",
                    "created_at": datetime.now()
                    - timedelta(days=random.randint(1, 365)),
                }
            )

        return pd.DataFrame(accounts)

    def create_trades(self, accounts: pd.DataFrame, count: int = 20) -> pd.DataFrame:
        """Create trade data referencing existing accounts."""
        trades = []
        account_ids = accounts["id"].tolist()

        for i in range(count):
            account_id = random.choice(account_ids)

            trades.append(
                {
                    "id": f"TRD_{i:08d}",
                    "account_id": account_id,
                    "symbol": random.choice(["EURUSD", "GBPUSD", "USDJPY"]),
                    "side": random.choice(["buy", "sell"]),
                    "quantity": random.choice([10000, 25000, 50000, 100000]),
                    "price": round(random.uniform(1.0, 1.5), 5),
                    "timestamp": datetime.now()
                    - timedelta(hours=random.randint(1, 168)),
                }
            )

        return pd.DataFrame(trades)

    def create_positions(self, trades: pd.DataFrame) -> pd.DataFrame:
        """Create position data based on trades."""
        positions = []

        # Group trades by account and symbol
        for (account_id, symbol), group in trades.groupby(["account_id", "symbol"]):
            # Calculate net position
            buy_qty = group[group["side"] == "buy"]["quantity"].sum()
            sell_qty = group[group["side"] == "sell"]["quantity"].sum()
            net_quantity = buy_qty - sell_qty

            if net_quantity != 0:
                positions.append(
                    {
                        "id": f"POS_{len(positions):08d}",
                        "account_id": account_id,
                        "symbol": symbol,
                        "quantity": net_quantity,
                        "side": "long" if net_quantity > 0 else "short",
                        "updated_at": group["timestamp"].max(),
                    }
                )

        return pd.DataFrame(positions)
