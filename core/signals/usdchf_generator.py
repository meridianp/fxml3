"""
Simple ML Signal Generator for USDCHF
Generated automatically by FXML4 Feature Engineering Integration
"""

from typing import Any, Dict, Optional

import joblib
import numpy as np
import pandas as pd


class USDCHFSignalGenerator:
    def __init__(self):
        self.model_path = (
            "/home/cnross/code/fxml4/models/USDCHF/xgboost_model_20250618_223620.joblib"
        )
        self.model = None
        self.symbol = "USDCHF"
        self.model_type = "xgboost"

    def load_model(self):
        """Load the trained model."""
        if self.model is None:
            self.model = joblib.load(self.model_path)
        return self.model is not None

    def generate_signal(self, features: pd.DataFrame) -> Dict[str, Any]:
        """Generate trading signal from features."""
        if not self.load_model():
            return {"signal": "hold", "confidence": 0.0, "error": "Model not loaded"}

        try:
            # Use last row of features for prediction
            latest_features = features.iloc[-1:].values

            # Handle NaN values
            if np.isnan(latest_features).any():
                latest_features = np.nan_to_num(latest_features, nan=0.0)

            # Get prediction
            if hasattr(self.model, "predict_proba"):
                prediction_proba = self.model.predict_proba(latest_features)[0]
                prediction = self.model.predict(latest_features)[0]
                confidence = max(prediction_proba)
            else:
                prediction = self.model.predict(latest_features)[0]
                confidence = 0.7  # Default confidence

            # Convert prediction to signal
            if prediction == 1 or prediction > 0.5:
                signal = "buy"
            elif prediction == 0 or prediction < -0.5:
                signal = "sell"
            else:
                signal = "hold"

            return {
                "signal": signal,
                "confidence": float(confidence),
                "prediction": float(prediction),
                "model_type": self.model_type,
                "symbol": self.symbol,
                "timestamp": pd.Timestamp.now().isoformat(),
            }

        except Exception as e:
            return {"signal": "hold", "confidence": 0.0, "error": str(e)}


# Create global instance
usdchf_signal_generator = USDCHFSignalGenerator()


def generate_usdchf_signal(features: pd.DataFrame) -> Dict[str, Any]:
    """Global function to generate USDCHF signal."""
    return usdchf_signal_generator.generate_signal(features)
