"""
FXML4 Signal Generation.

This package provides trading signal generation from multiple sources.
"""

from fxml4_signals.base import Signal, SignalType, SignalGenerator
from fxml4_signals.technical import TechnicalSignals
from fxml4_signals.ml_signals import MLSignals

__version__ = "0.1.0"
__all__ = ["Signal", "SignalType", "SignalGenerator", "TechnicalSignals", "MLSignals"]