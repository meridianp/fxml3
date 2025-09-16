"""Elliott Wave module - redirects to wave_analysis."""

# Re-export from wave_analysis for compatibility
from ..wave_analysis.elliott_wave import (
    ElliottWaveAnalyzer,
    ElliottWaveCount,
    ElliottWavePattern,
    WaveDegree,
    WavePosition,
    WaveType,
)

try:
    from ..wave_analysis.wave_counter import WaveCounter
except ImportError:
    WaveCounter = None

try:
    from ..wave_analysis.pattern_validator import PatternValidator
except ImportError:
    PatternValidator = None

# For backtesting integration
from .backtesting_integration import ElliottWaveBacktestStrategy

# Legacy compatibility - map old names to new ones
WavePattern = ElliottWavePattern

__all__ = [
    "ElliottWaveAnalyzer",
    "ElliottWavePattern",
    "ElliottWaveCount",
    "WaveType",
    "WaveDegree",
    "WavePosition",
    "WaveCounter",
    "PatternValidator",
    "ElliottWaveBacktestStrategy",
    "WavePattern",  # Legacy name
]
