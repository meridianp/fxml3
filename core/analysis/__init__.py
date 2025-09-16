"""
Analysis module for FXML4 trading platform.

Contains technical analysis tools including Elliott Wave detection,
pattern recognition, and market analysis algorithms.
"""

from .elliott_wave_detector import (
    ElliottWaveDetector,
    WaveCount,
    WaveDegree,
    WavePattern,
    WaveType,
)

__all__ = ["ElliottWaveDetector", "WavePattern", "WaveDegree", "WaveType", "WaveCount"]
