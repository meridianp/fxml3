#!/usr/bin/env python
"""Test ensemble model signal generation."""

import sys
from datetime import datetime, timedelta
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from fxml4.data.market_data import MarketDataProvider
from fxml4.ml.ensemble_models import StackingEnsemble, VotingEnsemble
from fxml4.strategy.integrated_strategy import IntegratedStrategy
from fxml4.strategy.ml_signal_generator import (
    EnsembleMLSignalGenerator,
    MLSignalGenerator,
)


def create_ensemble_model(symbol: str, models_dir: Path):
    """Create an ensemble model from trained models.

    Args:
        symbol: Trading symbol.
        models_dir: Directory containing trained models.

    Returns:
        Ensemble model and scaler.
    """
    symbol_dir = models_dir / symbol

    # Load individual models
    models = []

    # Try to load each model type
    for model_type, file_suffix in [
        ("RandomForest", "rf"),
        ("XGBoost", "xgb"),
        ("LightGBM", "lgb"),
    ]:
        model_file = symbol_dir / f"model_{file_suffix}.joblib"
        if model_file.exists():
            model = joblib.load(model_file)
            models.append((model_type, model))
            print(f"Loaded {model_type} model")

    if len(models) < 2:
        raise ValueError(f"Need at least 2 models for ensemble, found {len(models)}")

    # Create voting ensemble
    ensemble = VotingEnsemble(models, voting="soft", weights=None)

    # Load scaler
    scaler = joblib.load(symbol_dir / "scaler.joblib")

    # Load selected features
    with open(symbol_dir / "selected_features.json", "r") as f:
        import json

        selected_features = json.load(f)

    return ensemble, scaler, selected_features


def test_single_vs_ensemble_signals():
    """Test signal generation with single model vs ensemble."""
    print("=" * 80)
    print("TESTING SINGLE MODEL VS ENSEMBLE SIGNAL GENERATION")
    print("=" * 80)

    # Parameters
    symbol = "GBPUSD"
    models_dir = Path(__file__).parent.parent / "models"

    # Load data provider
    data_provider = MarketDataProvider()

    # Get recent data
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)

    # Load market data
    data = data_provider.get_data(
        symbol=symbol,
        timeframe="4h",
        start_date=start_date,
        end_date=end_date,
    )

    if data.empty:
        print("No data available")
        return

    print(f"\nLoaded {len(data)} bars of {symbol} data")

    # 1. Single Model Signal Generator
    print("\n1. Single Model (Best Model)")

    # Load best single model
    best_model = joblib.load(models_dir / symbol / "model_lgb.joblib")
    scaler = joblib.load(models_dir / symbol / "scaler.joblib")

    single_generator = MLSignalGenerator(
        model=best_model,
        config={
            "threshold": 0.6,
            "probability_mode": True,
            "use_technical_features": True,
        },
    )

    # Generate signals with single model
    single_signals = single_generator.generate_signals(
        data, symbol=symbol, timeframe="4h"
    )

    print(f"Single model generated {len(single_signals)} signals")
    for signal in single_signals[-5:]:  # Show last 5
        print(
            f"  {signal.timestamp}: {signal.signal_type.value} "
            f"(strength: {signal.strength:.3f})"
        )

    # 2. Ensemble Model Signal Generator
    print("\n2. Ensemble Model")

    try:
        # Create ensemble model
        ensemble_model, ensemble_scaler, selected_features = create_ensemble_model(
            symbol, models_dir
        )

        # Fit ensemble on training data (in practice, this would be done offline)
        # For demo, we'll use the pre-trained models
        ensemble.fitted_models_ = ensemble_model.models
        ensemble.classes_ = np.array([-1, 0, 1])  # For 3-class classification

        ensemble_generator = MLSignalGenerator(
            model=ensemble_model,
            config={
                "threshold": 0.65,  # Slightly higher threshold for ensemble
                "probability_mode": True,
                "use_technical_features": True,
                "feature_columns": selected_features,
            },
        )

        # Generate signals with ensemble
        ensemble_signals = ensemble_generator.generate_signals(
            data, symbol=symbol, timeframe="4h"
        )

        print(f"Ensemble model generated {len(ensemble_signals)} signals")
        for signal in ensemble_signals[-5:]:  # Show last 5
            print(
                f"  {signal.timestamp}: {signal.signal_type.value} "
                f"(strength: {signal.strength:.3f})"
            )

    except Exception as e:
        print(f"Error creating ensemble: {e}")

    # 3. Multi-Model Ensemble Signal Generator
    print("\n3. Multi-Model Ensemble Signal Generator")

    # Load multiple individual models
    individual_models = []

    for model_file, name in [
        ("model_rf.joblib", "RandomForest"),
        ("model_lgb.joblib", "LightGBM"),
    ]:
        model_path = models_dir / symbol / model_file
        if model_path.exists():
            model = joblib.load(model_path)
            individual_models.append(model)
            print(f"  Loaded {name}")

    if len(individual_models) >= 2:
        # Create ensemble signal generator
        ensemble_ml_generator = EnsembleMLSignalGenerator(
            models=individual_models,
            weights=[0.4, 0.6],  # Weight LightGBM higher
            config={
                "threshold": 0.6,
                "probability_mode": True,
                "use_technical_features": True,
            },
        )

        # Generate ensemble signals
        ensemble_ml_signals = ensemble_ml_generator.generate_signals(
            data, symbol=symbol, timeframe="4h"
        )

        print(f"\nEnsemble ML generator produced {len(ensemble_ml_signals)} signals")
        for signal in ensemble_ml_signals[-5:]:  # Show last 5
            print(
                f"  {signal.timestamp}: {signal.signal_type.value} "
                f"(strength: {signal.strength:.3f})"
            )

            # Show model contributions
            if "model_contributions" in signal.metadata:
                print("    Model contributions:")
                for contrib in signal.metadata["model_contributions"]:
                    print(
                        f"      {contrib['model']}: {contrib['strength']:.3f} "
                        f"(weight: {contrib['weight']:.2f})"
                    )

    # 4. Integrated Strategy with Multiple Signal Sources
    print("\n4. Integrated Strategy (Multiple Signal Sources)")

    # Create multiple signal generators
    generators = []

    # Add single model generator
    generators.append(single_generator)

    # Add ensemble generator if available
    if "ensemble_generator" in locals():
        generators.append(ensemble_generator)

    # Create integrated strategy
    integrated_strategy = IntegratedStrategy(
        signal_generators=generators,
        config={
            "signal_aggregation": "weighted",
            "min_combined_strength": 0.6,
            "generator_weights": [0.6, 0.4] if len(generators) > 1 else [1.0],
        },
    )

    # Generate integrated signals
    integrated_signals = integrated_strategy.generate_signals(
        data, symbol=symbol, timeframe="4h"
    )

    print(f"\nIntegrated strategy generated {len(integrated_signals)} signals")
    for signal in integrated_signals[-5:]:  # Show last 5
        print(
            f"  {signal.timestamp}: {signal.signal_type.value} "
            f"(strength: {signal.strength:.3f}, "
            f"sources: {signal.metadata.get('combined_sources', 'N/A')})"
        )


def test_dynamic_ensemble():
    """Test dynamic ensemble that adapts based on performance."""
    print("\n" + "=" * 80)
    print("TESTING DYNAMIC ENSEMBLE")
    print("=" * 80)

    from fxml4.ml.ensemble_models import DynamicEnsemble

    # Parameters
    symbol = "EURUSD"
    models_dir = Path(__file__).parent.parent / "models"

    # Load models
    models = []
    for model_type, file_suffix in [("RF", "rf"), ("XGB", "xgb"), ("LGB", "lgb")]:
        model_file = models_dir / symbol / f"model_{file_suffix}.joblib"
        if model_file.exists():
            model = joblib.load(model_file)
            models.append((model_type, model))

    if len(models) < 2:
        print("Not enough models for dynamic ensemble")
        return

    # Create dynamic ensemble
    dynamic_ensemble = DynamicEnsemble(
        models=models,
        window_size=50,
        selection_method="weighted",
        n_select=2,
    )

    # Simulate fitting (in practice, would use training data)
    dynamic_ensemble.fitted_models_ = models
    dynamic_ensemble.classes_ = np.array([-1, 0, 1])

    print(f"Dynamic ensemble initialized with {len(models)} models")

    # Simulate performance updates
    print("\nSimulating performance tracking...")

    # Generate some fake performance data
    np.random.seed(42)
    for i in range(10):
        y_true = np.random.choice([-1, 0, 1], size=100)
        y_pred = {}

        # Simulate different model performances
        for name, _ in models:
            if name == "LGB":
                # Make LightGBM perform best
                accuracy = 0.65 + np.random.uniform(-0.05, 0.05)
            elif name == "XGB":
                # XGBoost second best
                accuracy = 0.60 + np.random.uniform(-0.05, 0.05)
            else:
                # Random Forest varies more
                accuracy = 0.55 + np.random.uniform(-0.1, 0.1)

            # Generate predictions based on accuracy
            y_pred[name] = y_true.copy()
            n_wrong = int((1 - accuracy) * len(y_true))
            wrong_indices = np.random.choice(len(y_true), n_wrong, replace=False)
            y_pred[name][wrong_indices] = np.random.choice([-1, 0, 1], size=n_wrong)

        # Update performance
        dynamic_ensemble.update_performance(y_true, y_pred)

    # Show current weights
    weights = dynamic_ensemble._get_weights()
    print("\nModel weights after performance tracking:")
    for name, weight in weights.items():
        avg_perf = np.mean(dynamic_ensemble.performance_history_[name][-10:])
        print(f"  {name}: weight={weight:.3f}, recent_accuracy={avg_perf:.3f}")

    # Create signal generator with dynamic ensemble
    dynamic_generator = MLSignalGenerator(
        model=dynamic_ensemble,
        config={
            "threshold": 0.6,
            "probability_mode": False,  # Dynamic ensemble may not support probabilities
        },
    )

    print("\nDynamic ensemble signal generator created successfully!")


def main():
    """Run all ensemble tests."""
    test_single_vs_ensemble_signals()
    test_dynamic_ensemble()

    print("\n" + "=" * 80)
    print("ENSEMBLE SIGNAL GENERATION TEST COMPLETE")
    print("=" * 80)

    print("\nKey Takeaways:")
    print("1. Ensemble models can provide more robust signals than single models")
    print("2. Different ensemble methods (voting, stacking) offer various benefits")
    print("3. Dynamic ensembles can adapt to changing market conditions")
    print("4. EnsembleMLSignalGenerator makes it easy to combine multiple models")
    print("5. Integrated strategies can combine ensemble and single model signals")


if __name__ == "__main__":
    main()
