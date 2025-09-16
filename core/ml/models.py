"""
FXML4 Machine Learning Models

This module has been decomposed into smaller, more manageable modules.
This file provides backward compatibility by re-exporting the new structure.

NEW STRUCTURE:
- fxml4.ml.models.base: Base classes and common functionality
- fxml4.ml.models.classic: Classic ML models (RF, XGBoost, Logistic)
- fxml4.ml.models.ensemble: Ensemble methods
- fxml4.ml.models.utils: Utility functions
- fxml4.ml.models.constants: Platform constants

For new code, prefer importing from the specific modules for better clarity.
"""

import warnings

# Re-export everything from the new modular structure
from .models.base import MLModelBase
from .models.classic import ClassicMLModel
from .models.constants import GPU_AVAILABLE, IS_APPLE_SILICON
from .models.ensemble import EnsembleModel
from .models.utils import (
    compare_models,
    create_ensemble,
    create_model,
    cross_validate_models,
    get_model_summary,
    load_models,
    save_models,
    select_best_models,
)

# Warn about deprecated import
warnings.warn(
    "Importing from fxml4.ml.models directly is deprecated. "
    "Please use specific imports from fxml4.ml.models.{module} instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    # Base classes
    "MLModelBase",
    "ClassicMLModel",
    "EnsembleModel",
    # Utility functions
    "create_model",
    "compare_models",
    "create_ensemble",
    "select_best_models",
    "cross_validate_models",
    "save_models",
    "load_models",
    "get_model_summary",
    # Constants
    "GPU_AVAILABLE",
    "IS_APPLE_SILICON",
]
