"""Data quality validation module for FXML4.

This module provides data quality validation functionality required by the
test suite, implementing quality checks for market data integrity.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


class DataQualityChecker:
    """Validates data quality and handles anomalies in market data.

    This class implements the interface expected by the test suite for
    validating tick data, OHLCV candles, and time series data integrity.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the data quality checker.

        Args:
            config: Configuration dictionary with quality check parameters
        """
        if config is None:
            config = {}

        self.max_price_change_pct = config.get("max_price_change_pct", 10.0)
        self.min_volume_threshold = config.get("min_volume_threshold", 0)
        self.max_gap_minutes = config.get("max_gap_minutes", 5)
        self.max_spread_pips = config.get("max_spread_pips", 10)
        self.min_bid_ask_ratio = config.get("min_bid_ask_ratio", 0.5)

        logger.info(f"Initialized DataQualityChecker with config: {config}")

    def validate_tick(
        self, tick: Dict[str, Any], previous_tick: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Validate individual tick data quality.

        Args:
            tick: Tick data dictionary with keys: timestamp, symbol, bid, ask,
                  volume, etc.
            previous_tick: Optional previous tick for comparison

        Returns:
            True if tick passes quality checks, False otherwise
        """
        try:
            # Basic required field validation
            if not self._validate_required_fields(tick):
                return False

            # Price validation
            if not self._validate_prices(tick):
                return False

            # Spread validation
            if not self._validate_spread(tick):
                return False

            # Volume validation
            if not self._validate_volume(tick):
                return False

            # Timestamp validation
            if not self._validate_timestamp(tick, previous_tick):
                return False

            # Price movement validation (if previous tick available)
            if previous_tick and not self._validate_price_movement(tick, previous_tick):
                return False

            return True

        except Exception as e:
            logger.error(f"Error validating tick: {str(e)}")
            return False

    def validate_candle(
        self, candle: Dict[str, Any], previous_candle: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Validate OHLCV candle data quality.

        Args:
            candle: Candle data with keys: timestamp, symbol, open, high, low,
                    close, volume
            previous_candle: Optional previous candle for comparison

        Returns:
            True if candle passes quality checks, False otherwise
        """
        try:
            # Basic required field validation
            if not self._validate_candle_fields(candle):
                return False

            # OHLCV logic validation
            if not self._validate_ohlcv_logic(candle):
                return False

            # Volume validation
            if not self._validate_candle_volume(candle):
                return False

            # Timestamp validation
            if not self._validate_candle_timestamp(candle, previous_candle):
                return False

            # Price gap validation (if previous candle available)
            if previous_candle and not self._validate_candle_price_gap(
                candle, previous_candle
            ):
                return False

            return True

        except Exception as e:
            logger.error(f"Error validating candle: {str(e)}")
            return False

    def validate_time_series(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Validate a complete time series for quality issues.

        Args:
            data: List of data points (ticks or candles) to validate

        Returns:
            Dictionary with validation results and statistics
        """
        if not data:
            return {"valid": True, "issues": [], "stats": {"total": 0}}

        issues = []
        valid_count = 0

        for i, point in enumerate(data):
            previous_point = data[i - 1] if i > 0 else None

            # Determine data type and validate accordingly
            if self._is_tick_data(point):
                is_valid = self.validate_tick(point, previous_point)
            elif self._is_candle_data(point):
                is_valid = self.validate_candle(point, previous_point)
            else:
                issues.append(f"Unknown data type at index {i}")
                continue

            if is_valid:
                valid_count += 1
            else:
                issues.append(f"Quality issue at index {i}")

        # Calculate time series specific metrics
        time_gaps = self._find_time_gaps(data)
        duplicate_timestamps = self._find_duplicate_timestamps(data)

        issues.extend([f"Time gap: {gap}" for gap in time_gaps])
        issues.extend([f"Duplicate timestamp: {dup}" for dup in duplicate_timestamps])

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "stats": {
                "total": len(data),
                "valid": valid_count,
                "invalid": len(data) - valid_count,
                "success_rate": valid_count / len(data) if data else 0,
                "time_gaps": len(time_gaps),
                "duplicates": len(duplicate_timestamps),
            },
        }

    def _validate_required_fields(self, tick: Dict[str, Any]) -> bool:
        """Validate required fields are present."""
        required_fields = ["timestamp", "symbol"]

        for field in required_fields:
            if field not in tick or tick[field] is None:
                logger.warning(f"Missing required field '{field}' in tick")
                return False

        # At least one price field required
        price_fields = ["bid", "ask", "last", "price"]
        has_price_field = any(
            field in tick and tick[field] is not None for field in price_fields
        )
        if not has_price_field:
            logger.warning("No price fields found in tick")
            return False

        return True

    def _validate_prices(self, tick: Dict[str, Any]) -> bool:
        """Validate price values are reasonable."""
        price_fields = ["bid", "ask", "last", "price"]

        for field in price_fields:
            if field in tick and tick[field] is not None:
                price = float(tick[field])
                if price <= 0:
                    logger.warning(f"Invalid {field} price: {price}")
                    return False
                if price > 1000:  # Reasonable upper bound for FX rates
                    logger.warning(f"Suspicious high {field} price: {price}")
                    return False

        return True

    def _validate_spread(self, tick: Dict[str, Any]) -> bool:
        """Validate bid/ask spread is reasonable."""
        if (
            "bid" in tick
            and "ask" in tick
            and tick["bid"] is not None
            and tick["ask"] is not None
        ):
            bid = float(tick["bid"])
            ask = float(tick["ask"])

            if ask <= bid:
                logger.warning(f"Invalid spread: ask ({ask}) <= bid ({bid})")
                return False

            # Assuming 4-decimal currency pairs
            spread_pips = (ask - bid) * 10000
            if spread_pips > self.max_spread_pips:
                logger.warning(f"Wide spread: {spread_pips} pips")
                return False

        return True

    def _validate_volume(self, tick: Dict[str, Any]) -> bool:
        """Validate volume is reasonable."""
        if "volume" in tick and tick["volume"] is not None:
            volume = tick["volume"]
            if volume < 0:
                logger.warning(f"Negative volume: {volume}")
                return False

        return True

    def _validate_timestamp(
        self, tick: Dict[str, Any], previous_tick: Optional[Dict[str, Any]]
    ) -> bool:
        """Validate timestamp is reasonable."""
        timestamp = tick.get("timestamp")

        if timestamp is None:
            return False

        # Convert to datetime if needed
        if isinstance(timestamp, str):
            try:
                timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            except ValueError:
                logger.warning(f"Invalid timestamp format: {timestamp}")
                return False

        # Check for future timestamps
        now = datetime.now(timestamp.tzinfo) if timestamp.tzinfo else datetime.now()
        # Allow small future tolerance
        if timestamp > now + timedelta(minutes=1):
            logger.warning(f"Future timestamp: {timestamp}")
            return False

        # Check for backwards time movement
        if previous_tick:
            prev_timestamp = previous_tick.get("timestamp")
            if prev_timestamp:
                if isinstance(prev_timestamp, str):
                    try:
                        prev_timestamp = datetime.fromisoformat(
                            prev_timestamp.replace("Z", "+00:00")
                        )
                    except ValueError:
                        # Can't compare, but current tick timestamp is valid
                        return True

                if timestamp < prev_timestamp:
                    logger.warning(
                        f"Backwards time movement: {timestamp} < {prev_timestamp}"
                    )
                    return False

                # Check for large time gaps
                time_diff = (timestamp - prev_timestamp).total_seconds()
                if time_diff > self.max_gap_minutes * 60:
                    logger.warning(f"Large time gap: {time_diff} seconds")

        return True

    def _validate_price_movement(
        self, tick: Dict[str, Any], previous_tick: Dict[str, Any]
    ) -> bool:
        """Validate price movement between ticks is reasonable."""
        current_price = self._get_price_for_comparison(tick)
        previous_price = self._get_price_for_comparison(previous_tick)

        if current_price is None or previous_price is None:
            return True  # Can't compare

        price_change_pct = abs((current_price - previous_price) / previous_price) * 100
        if price_change_pct > self.max_price_change_pct:
            logger.warning(f"Large price movement: {price_change_pct}% in single tick")
            return False

        return True

    def _get_price_for_comparison(self, data_point: Dict[str, Any]) -> Optional[float]:
        """Get the best price for comparison from a data point."""
        for field in ["last", "price", "close", "bid", "ask"]:
            if field in data_point and data_point[field] is not None:
                return float(data_point[field])
        return None

    def _validate_candle_fields(self, candle: Dict[str, Any]) -> bool:
        """Validate required candle fields."""
        required_fields = ["timestamp", "symbol", "open", "high", "low", "close"]

        for field in required_fields:
            if field not in candle or candle[field] is None:
                logger.warning(f"Missing required candle field '{field}'")
                return False

        return True

    def _validate_ohlcv_logic(self, candle: Dict[str, Any]) -> bool:
        """Validate OHLCV logical consistency."""
        try:
            o, h, l, c = (
                float(candle["open"]),
                float(candle["high"]),
                float(candle["low"]),
                float(candle["close"]),
            )

            if h < l:
                logger.warning(f"Invalid candle: high ({h}) < low ({l})")
                return False

            if h < max(o, c) or l > min(o, c):
                logger.warning("Invalid candle: high/low inconsistent with open/close")
                return False

            return True

        except (ValueError, TypeError) as e:
            logger.warning(f"Invalid price values in candle: {e}")
            return False

    def _validate_candle_volume(self, candle: Dict[str, Any]) -> bool:
        """Validate candle volume."""
        if "volume" in candle and candle["volume"] is not None:
            volume = candle["volume"]
            if volume < self.min_volume_threshold:
                logger.debug(f"Low volume candle: {volume}")
            if volume < 0:
                logger.warning(f"Negative volume in candle: {volume}")
                return False

        return True

    def _validate_candle_timestamp(
        self, candle: Dict[str, Any], previous_candle: Optional[Dict[str, Any]]
    ) -> bool:
        """Validate candle timestamp."""
        return self._validate_timestamp(candle, previous_candle)

    def _validate_candle_price_gap(
        self, candle: Dict[str, Any], previous_candle: Dict[str, Any]
    ) -> bool:
        """Validate price gap between candles."""
        current_close = candle.get("close")
        previous_close = previous_candle.get("close")

        if current_close is None or previous_close is None:
            return True

        try:
            gap_pct = (
                abs(
                    (float(current_close) - float(previous_close))
                    / float(previous_close)
                )
                * 100
            )
            if gap_pct > self.max_price_change_pct:
                logger.warning(f"Large price gap between candles: {gap_pct}%")
                return False

        except (ValueError, TypeError, ZeroDivisionError):
            logger.warning("Could not calculate price gap")
            return False

        return True

    def _is_tick_data(self, data_point: Dict[str, Any]) -> bool:
        """Determine if data point is tick data."""
        tick_indicators = ["bid", "ask", "tick_type"]
        return any(field in data_point for field in tick_indicators)

    def _is_candle_data(self, data_point: Dict[str, Any]) -> bool:
        """Determine if data point is candle data."""
        candle_indicators = ["open", "high", "low", "close"]
        return all(field in data_point for field in candle_indicators)

    def _find_time_gaps(self, data: List[Dict[str, Any]]) -> List[str]:
        """Find significant time gaps in the data."""
        gaps = []

        for i in range(1, len(data)):
            current_ts = data[i].get("timestamp")
            previous_ts = data[i - 1].get("timestamp")

            if current_ts and previous_ts:
                try:
                    # Convert to datetime if needed
                    if isinstance(current_ts, str):
                        current_ts = datetime.fromisoformat(
                            current_ts.replace("Z", "+00:00")
                        )
                    if isinstance(previous_ts, str):
                        previous_ts = datetime.fromisoformat(
                            previous_ts.replace("Z", "+00:00")
                        )

                    gap_minutes = (current_ts - previous_ts).total_seconds() / 60
                    if gap_minutes > self.max_gap_minutes:
                        gaps.append(f"Gap of {gap_minutes:.1f} minutes at index {i}")

                except (ValueError, TypeError):
                    continue

        return gaps

    def _find_duplicate_timestamps(self, data: List[Dict[str, Any]]) -> List[str]:
        """Find duplicate timestamps in the data."""
        seen_timestamps = set()
        duplicates = []

        for i, point in enumerate(data):
            timestamp = point.get("timestamp")
            if timestamp:
                if timestamp in seen_timestamps:
                    duplicates.append(f"Duplicate timestamp {timestamp} at index {i}")
                else:
                    seen_timestamps.add(timestamp)

        return duplicates
