"""
ML Trading Pipeline for FXML4

TDD-driven implementation integrating feature extraction, model predictions,
and signal generation into a unified trading pipeline.
Following Green phase - minimal implementation to pass tests.
"""

import asyncio
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Any
from datetime import datetime

from core.ml.feature_extractor import FeatureExtractor
from core.ml.model_predictor import ModelPredictor
from core.ml.signal_generator import SignalGenerator


class MLTradingPipeline:
    """Unified ML trading pipeline for market analysis and signal generation."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize ML trading pipeline with configuration."""
        self.config = config or {}

        self.feature_extractor = FeatureExtractor(config)
        self.model_predictor = ModelPredictor(config)
        self.signal_generator = SignalGenerator(config)

        self.websocket = None
        self.websocket_connected = False
        self.is_running = False

    async def process_market_data(self, market_data: pd.DataFrame) -> Dict[str, Any]:
        """Process market data through complete ML pipeline."""
        if market_data.empty:
            return None

        symbol = (
            market_data["symbol"].iloc[-1] if "symbol" in market_data else "EUR/USD"
        )
        current_price = market_data["close"].iloc[-1]

        features = self.feature_extractor.extract_technical_features(market_data)

        features_array = features.fillna(0).values[-1].reshape(1, -1)

        prediction = self.model_predictor.predict_ensemble(features_array)

        signal = self.signal_generator.generate_signal(
            symbol=symbol, prediction=prediction, current_price=current_price
        )

        signal["features"] = features.columns.tolist()
        signal["models_used"] = list(prediction.get("model_predictions", {}).keys())

        if self.websocket_connected:
            await self.broadcast_signal(signal)

        return signal

    def connect_websocket(self, websocket_server):
        """Connect pipeline to WebSocket server for real-time broadcasting."""
        self.websocket = websocket_server
        self.websocket_connected = True

    async def broadcast_signal(self, signal: Dict[str, Any]):
        """Broadcast trading signal through WebSocket."""
        if self.websocket and self.websocket_connected:
            message = {
                "type": "ml_signal",
                "data": signal,
                "timestamp": datetime.now().isoformat(),
            }

            if hasattr(self.websocket, "broadcast"):
                await self.websocket.broadcast(message)

    async def start_real_time_processing(self, data_feed):
        """Start real-time market data processing."""
        self.is_running = True

        while self.is_running:
            try:
                market_data = await data_feed.get_latest_data()

                if market_data is not None:
                    signal = await self.process_market_data(market_data)

                    if (
                        signal
                        and signal["confidence"]
                        >= self.signal_generator.confidence_threshold
                    ):
                        await self.broadcast_signal(signal)

                await asyncio.sleep(1)

            except Exception as e:
                print(f"Error in real-time processing: {e}")
                await asyncio.sleep(5)

    def stop(self):
        """Stop the ML pipeline."""
        self.is_running = False
        self.websocket_connected = False
