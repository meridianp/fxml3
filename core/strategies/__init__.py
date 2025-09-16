"""Trading strategies module."""

# Import main strategy components
try:
    from ..strategy.integrated_strategy import (
        IntegratedStrategy,
        Signal,
        SignalCombiner,
        SignalGenerator,
        SignalSource,
        SignalStrength,
        SignalType,
        simple_strategy,
    )
except ImportError:
    IntegratedStrategy = None
    SignalType = None
    SignalStrength = None
    SignalSource = None
    Signal = None
    SignalGenerator = None
    SignalCombiner = None
    simple_strategy = None

try:
    from ..strategy.market_regime_detector import MarketRegime, VolatilityRegime
except ImportError:
    MarketRegime = None
    VolatilityRegime = None

try:
    from ..strategy.base_strategy import BaseStrategy
except ImportError:
    BaseStrategy = None

try:
    from ..strategy.ml_signal_generator import MLSignalGenerator
except ImportError:
    MLSignalGenerator = None

__all__ = [
    "IntegratedStrategy",
    "SignalType",
    "SignalStrength",
    "SignalSource",
    "Signal",
    "SignalGenerator",
    "SignalCombiner",
    "simple_strategy",
    "MarketRegime",
    "VolatilityRegime",
    "BaseStrategy",
    "MLSignalGenerator",
]
