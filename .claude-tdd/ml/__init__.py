"""
FXML4 Claude TDD Automation Framework - Phase 5: ML-Enhanced Testing
AI-powered test generation, prioritization, and quality prediction for financial systems
"""

__version__ = "5.0.0"
__author__ = "FXML4 Claude TDD Framework"

# ML-Enhanced Testing Components
from .test_generator import AITestGenerator
from .test_prioritizer import IntelligentTestPrioritizer
from .quality_predictor import PredictiveQualityAnalytics
from .test_optimizer import TestOptimizer

__all__ = [
    "AITestGenerator",
    "IntelligentTestPrioritizer",
    "PredictiveQualityAnalytics",
    "TestOptimizer"
]