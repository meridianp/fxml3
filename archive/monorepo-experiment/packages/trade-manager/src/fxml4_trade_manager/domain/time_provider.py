"""Time provider implementations for dependency injection."""

from datetime import datetime, timezone, time
from typing import Optional

from .interfaces import ITimeProvider


class UTCTimeProvider(ITimeProvider):
    """Production time provider using UTC."""
    
    def now(self) -> datetime:
        """Get current UTC time."""
        return datetime.now(timezone.utc)
    
    def today(self) -> datetime:
        """Get current UTC date at midnight."""
        return datetime.combine(
            datetime.now(timezone.utc).date(),
            time.min,
            tzinfo=timezone.utc
        )


class MockTimeProvider(ITimeProvider):
    """Mock time provider for testing."""
    
    def __init__(self, fixed_time: Optional[datetime] = None):
        """Initialize with optional fixed time."""
        self._fixed_time = fixed_time or datetime.now(timezone.utc)
        self._auto_advance = False
        self._advance_seconds = 0
    
    def now(self) -> datetime:
        """Get current time (fixed or auto-advancing)."""
        if self._auto_advance and self._advance_seconds > 0:
            self._fixed_time = self._fixed_time.replace(
                second=self._fixed_time.second + self._advance_seconds
            )
        return self._fixed_time
    
    def today(self) -> datetime:
        """Get current date at midnight."""
        return datetime.combine(self._fixed_time.date(), time.min, tzinfo=self._fixed_time.tzinfo)
    
    def set_time(self, new_time: datetime) -> None:
        """Set a new fixed time."""
        self._fixed_time = new_time
    
    def advance_time(self, seconds: int) -> None:
        """Advance time by specified seconds."""
        from datetime import timedelta
        self._fixed_time += timedelta(seconds=seconds)
    
    def enable_auto_advance(self, seconds_per_call: int = 1) -> None:
        """Enable automatic time advancement on each call."""
        self._auto_advance = True
        self._advance_seconds = seconds_per_call
    
    def disable_auto_advance(self) -> None:
        """Disable automatic time advancement."""
        self._auto_advance = False
    
    def advance(self, seconds: int = 0, minutes: int = 0, hours: int = 0, days: int = 0) -> None:
        """Advance time by specified duration."""
        from datetime import timedelta
        delta = timedelta(seconds=seconds, minutes=minutes, hours=hours, days=days)
        self._fixed_time += delta