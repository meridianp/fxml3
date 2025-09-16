"""
Base classes for signal generation.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Any, Optional
from enum import Enum
import pandas as pd

from fxml4_core.logging import get_logger

logger = get_logger(__name__)


class SignalType(Enum):
    """Signal types."""
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    CLOSE_LONG = "CLOSE_LONG"
    CLOSE_SHORT = "CLOSE_SHORT"


@dataclass
class Signal:
    """Trading signal."""
    timestamp: datetime
    symbol: str
    signal_type: SignalType
    source: str
    confidence: float
    price: float
    metadata: Dict[str, Any]
    
    def __post_init__(self):
        """Validate signal."""
        if not 0 <= self.confidence <= 1:
            raise ValueError(f"Confidence must be between 0 and 1, got {self.confidence}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "symbol": self.symbol,
            "signal_type": self.signal_type.value,
            "source": self.source,
            "confidence": self.confidence,
            "price": self.price,
            "metadata": self.metadata
        }


class SignalSource(ABC):
    """Abstract base class for signal sources."""
    
    def __init__(self, name: str, weight: float = 1.0):
        self.name = name
        self.weight = weight
    
    @abstractmethod
    def generate_signals(self, data: pd.DataFrame, symbol: str) -> List[Signal]:
        """Generate signals from data."""
        pass
    
    def validate_data(self, data: pd.DataFrame) -> bool:
        """Validate input data."""
        if data.empty:
            logger.warning(f"{self.name}: Empty dataframe provided")
            return False
        
        required_columns = self.get_required_columns()
        missing_columns = set(required_columns) - set(data.columns)
        
        if missing_columns:
            logger.error(f"{self.name}: Missing columns: {missing_columns}")
            return False
        
        return True
    
    @abstractmethod
    def get_required_columns(self) -> List[str]:
        """Get required column names."""
        pass


class SignalGenerator:
    """Main signal generator combining multiple sources."""
    
    def __init__(self, min_confidence: float = 0.5):
        self.sources: List[SignalSource] = []
        self.min_confidence = min_confidence
        self.signal_history: List[Signal] = []
    
    def add_source(self, source: SignalSource) -> None:
        """Add a signal source."""
        self.sources.append(source)
        logger.info(f"Added signal source: {source.name} (weight: {source.weight})")
    
    def generate(self, data: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """Generate signals from all sources."""
        all_signals = []
        
        for source in self.sources:
            try:
                if source.validate_data(data):
                    signals = source.generate_signals(data, symbol)
                    
                    # Apply source weight to confidence
                    for signal in signals:
                        signal.confidence *= source.weight
                    
                    all_signals.extend(signals)
                    logger.debug(f"Generated {len(signals)} signals from {source.name}")
                
            except Exception as e:
                logger.error(f"Error generating signals from {source.name}: {e}")
        
        # Filter by confidence
        filtered_signals = [s for s in all_signals if s.confidence >= self.min_confidence]
        
        # Store in history
        self.signal_history.extend(filtered_signals)
        
        # Convert to DataFrame
        if filtered_signals:
            df = pd.DataFrame([s.to_dict() for s in filtered_signals])
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.set_index('timestamp').sort_index()
        else:
            df = pd.DataFrame()
        
        logger.info(f"Generated {len(filtered_signals)} signals above confidence threshold")
        
        return df
    
    def aggregate_signals(self, signals: pd.DataFrame, window: str = '5T') -> pd.DataFrame:
        """Aggregate signals over time windows."""
        if signals.empty:
            return signals
        
        # Group by time window and signal type
        aggregated = signals.groupby([
            pd.Grouper(freq=window),
            'symbol',
            'signal_type'
        ]).agg({
            'confidence': ['mean', 'max', 'count'],
            'price': 'mean'
        }).reset_index()
        
        # Flatten column names
        aggregated.columns = [
            'timestamp', 'symbol', 'signal_type',
            'avg_confidence', 'max_confidence', 'signal_count', 'avg_price'
        ]
        
        return aggregated
    
    def get_latest_signals(self, symbol: Optional[str] = None, n: int = 10) -> List[Signal]:
        """Get latest signals from history."""
        signals = self.signal_history
        
        if symbol:
            signals = [s for s in signals if s.symbol == symbol]
        
        # Sort by timestamp descending
        signals.sort(key=lambda x: x.timestamp, reverse=True)
        
        return signals[:n]