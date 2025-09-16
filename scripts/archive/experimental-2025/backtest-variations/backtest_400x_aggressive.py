#!/usr/bin/env python3
"""Aggressive backtest with better leverage utilization and drawdown control."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import json
import logging
import pickle
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Import FXML4 modules
from fxml4.data.polygon_official_fetcher import PolygonDataManager
from fxml4.features.feature_engineering import UnifiedFeatureEngineer
from fxml4.llm_integration.multimodal_mtf_validator import MultiTimeframeChartValidator
from fxml4.ml.features import create_basic_technical_features
from fxml4.wave_analysis.elliott_wave import ElliottWaveAnalyzer
from fxml4.wave_analysis.fibonacci import FibonacciCalculator


@dataclass
class AggressiveTrade:
    """Trade record with aggressive leverage."""

    timestamp: datetime
    direction: str
    entry_price: float
    exit_price: float
    position_size: float  # In USD
    lots: float  # Number of micro lots
    leverage_used: float
    pnl: float
    pnl_pips: float
    ml_confidence: float
    llm_confidence: float
    elliott_wave_score: float
    signal_source: str
    exit_reason: str
    drawdown_at_entry: float


class AggressiveBacktester:
    """Aggressive backtesting system with enhanced leverage utilization."""

    def __init__(
        self,
        initial_capital: float = 10000,
        max_leverage: float = 400.0,
        target_leverage: float = 50.0,  # Target average leverage
        min_lot_size: float = 1.0,
        commission_per_lot: float = 0.02,
        max_risk_per_trade: float = 0.05,  # 5% max risk per trade
        max_drawdown_limit: float = 0.25,  # 25% max drawdown
        polygon_api_key: Optional[str] = None,
    ):
        """Initialize aggressive backtesting system."""
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.max_leverage = max_leverage
        self.target_leverage = target_leverage
        self.min_lot_size = min_lot_size
        self.commission_per_lot = commission_per_lot
        self.max_risk_per_trade = max_risk_per_trade
        self.max_drawdown_limit = max_drawdown_limit

        # Initialize components
        self.polygon_manager = PolygonDataManager(polygon_api_key)

        # Feature engineer with all enhancements
        self.feature_engineer = UnifiedFeatureEngineer(
            {
                "basic_indicators": [
                    "sma",
                    "ema",
                    "rsi",
                    "macd",
                    "bollinger",
                    "stoch",
                    "atr",
                    "adx",
                ],
                "ma_periods": [5, 10, 20, 50, 100, 200],  # More MA periods
                "advanced_features": True,
                "elliott_wave_features": True,
                "regime_features": True,
                "microstructure_features": True,
            }
        )

        # Elliott Wave analyzer
        self.elliott_analyzer = ElliottWaveAnalyzer()
        self.fibonacci_calc = FibonacciCalculator()

        # Multi-timeframe validator with lower thresholds
        self.mtf_validator = MultiTimeframeChartValidator(
            config={
                "timeframes": ["15m", "1H", "4H", "D"],
                "candles_per_timeframe": {"15m": 100, "1H": 100, "4H": 60, "D": 30},
            }
        )

        # Trading records
        self.trades: List[AggressiveTrade] = []
        self.open_positions: Dict[str, Any] = {}
        self.equity_curve = []
        self.max_drawdown = 0
        self.current_drawdown = 0
        self.peak_equity = initial_capital
        self.consecutive_losses = 0
        self.max_concurrent_positions = 10  # Allow more concurrent positions

    async def run_backtest(
        self, symbol: str, start_date: datetime, end_date: datetime
    ) -> Dict[str, Any]:
        """Run aggressive backtest with enhanced signal generation."""
        polygon_symbol = f"C:{symbol}"

        logger.info(f"\n{'='*60}")
        logger.info("AGGRESSIVE FXML4 BACKTEST - ENHANCED LEVERAGE")
        logger.info(f"{'='*60}")
        logger.info(f"Symbol: {symbol}")
        logger.info(f"Period: {start_date.date()} to {end_date.date()}")
        logger.info(f"Initial Capital: ${self.initial_capital:,.2f}")
        logger.info(f"Max Leverage: {self.max_leverage}:1")
        logger.info(f"Target Leverage: {self.target_leverage}:1")
        logger.info(f"Max Drawdown Limit: {self.max_drawdown_limit:.1%}")

        # Fetch multi-timeframe data
        logger.info("\nFetching historical data from Polygon.io...")
        timeframes = ["15m", "1H", "4H", "D"]

        historical_data = self.polygon_manager.get_backtest_data(
            polygon_symbol, timeframes, start_date - timedelta(days=100), end_date
        )

        if "4H" not in historical_data:
            logger.error("Failed to fetch data")
            return {}

        primary_data = historical_data["4H"]
        logger.info(f"Loaded {len(primary_data)} bars of 4H data")

        # Calculate comprehensive features
        logger.info("\nCalculating comprehensive technical features...")
        try:
            features_df = self.feature_engineer.generate_features(primary_data)
            logger.info(f"Generated {len(features_df.columns)} features")
        except Exception as e:
            logger.warning(f"Advanced features failed: {e}, using basic features")
            features_df = create_basic_technical_features(primary_data)

        # Load ML model if available
        ml_model = await self._load_ml_model(symbol)

        # Calculate indicators for all timeframes
        indicators_by_tf = {}
        for tf, data in historical_data.items():
            indicators_by_tf[tf] = self._calculate_comprehensive_indicators(data)

        # Process signals with multiple strategies
        total_signals = 0
        ml_signals_count = 0
        elliott_validated = 0
        llm_validated = 0
        executed_trades = 0

        # Check every bar for maximum signal generation
        for i in range(200, len(primary_data)):
            current_time = primary_data.index[i]

            # Skip if outside backtest period
            if current_time < start_date or current_time > end_date:
                continue

            # Update equity tracking
            current_equity = self._calculate_current_equity(primary_data.iloc[i])
            self.equity_curve.append(
                {"timestamp": current_time, "equity": current_equity}
            )

            # Update drawdown
            if current_equity > self.peak_equity:
                self.peak_equity = current_equity
            self.current_drawdown = (
                self.peak_equity - current_equity
            ) / self.peak_equity
            self.max_drawdown = max(self.max_drawdown, self.current_drawdown)

            # Check drawdown limit
            if self.current_drawdown >= self.max_drawdown_limit:
                # Close all positions if drawdown limit hit
                if self.open_positions:
                    logger.warning(
                        f"Drawdown limit hit ({self.current_drawdown:.1%}), closing all positions"
                    )
                    self._close_all_positions(primary_data.iloc[i], current_time)
                continue

            # Dynamic position limit based on drawdown
            max_positions = self._calculate_dynamic_position_limit()
            if len(self.open_positions) >= max_positions:
                continue

            # Generate signals from multiple sources
            signals = await self._generate_multi_source_signals(
                (
                    features_df.iloc[: i + 1]
                    if i < len(features_df)
                    else primary_data.iloc[: i + 1]
                ),
                current_time,
                ml_model,
                primary_data.iloc[i],
            )

            # Process each signal
            for signal in signals:
                if signal and signal["confidence"] > 0.5:  # Lower threshold
                    total_signals += 1

                    # Check if we already have a position in this direction
                    same_direction_positions = [
                        p
                        for p in self.open_positions.values()
                        if p["signal"]["direction"] == signal["direction"]
                    ]
                    if (
                        len(same_direction_positions) >= 3
                    ):  # Max 3 positions per direction
                        continue

                    # Elliott Wave validation with lower threshold
                    wave_score = await self._validate_elliott_wave(
                        primary_data.iloc[: i + 1], signal
                    )

                    if wave_score > 0.4:  # Lower threshold
                        elliott_validated += 1

                        # Enhance signal
                        enhanced_signal = {**signal, "elliott_wave_score": wave_score}

                        # Multi-timeframe LLM validation
                        llm_result = await self._validate_with_llm(
                            enhanced_signal,
                            current_time,
                            historical_data,
                            indicators_by_tf,
                        )

                        if (
                            llm_result["valid"] and llm_result["llm_confidence"] >= 0.6
                        ):  # Lower threshold
                            llm_validated += 1

                            # Calculate aggressive position size
                            position_details = self._calculate_aggressive_position(
                                enhanced_signal, llm_result, primary_data.iloc[i]
                            )

                            if position_details["position_size"] >= self.min_lot_size:
                                # Execute trade
                                executed_trades += 1
                                self._execute_trade(
                                    enhanced_signal,
                                    position_details,
                                    llm_result,
                                    wave_score,
                                )

                                logger.info(
                                    f"\n✅ Trade #{executed_trades} executed at {current_time}"
                                )
                                logger.info(
                                    f"   Direction: {enhanced_signal['direction']}"
                                )
                                logger.info(
                                    f"   Size: ${position_details['position_size']:,.2f} ({position_details['lots']:.0f} micro lots)"
                                )
                                logger.info(
                                    f"   Leverage: {position_details['effective_leverage']:.1f}:1"
                                )
                                logger.info(
                                    f"   Source: {enhanced_signal.get('source', 'Technical')}"
                                )
                                logger.info(
                                    f"   Confidence: ML={enhanced_signal['confidence']:.1%}, Elliott={wave_score:.1%}, LLM={llm_result['llm_confidence']:.1%}"
                                )
                                logger.info(
                                    f"   Current Drawdown: {self.current_drawdown:.1%}"
                                )

            # Check exits for open positions
            self._check_exits(primary_data.iloc[i], current_time)

        # Close any remaining positions at end
        if self.open_positions:
            logger.info("\nClosing remaining positions at end of backtest...")
            self._close_all_positions(primary_data.iloc[-1], primary_data.index[-1])

        # Calculate final results
        results = self._calculate_results()

        # Display summary
        logger.info(f"\n{'='*60}")
        logger.info("BACKTEST RESULTS SUMMARY")
        logger.info(f"{'='*60}")

        logger.info("\nSignal Funnel:")
        logger.info(f"Total Signals Generated: {total_signals}")
        logger.info(f"Signals (>50% conf): {total_signals}")
        logger.info(f"Elliott Wave Validated (>40%): {elliott_validated}")
        logger.info(f"LLM Validated (>60%): {llm_validated}")
        logger.info(f"Trades Executed: {executed_trades}")

        logger.info("\nPerformance Metrics:")
        logger.info(f"Total Trades: {results['total_trades']}")
        logger.info(
            f"Winning Trades: {results['winning_trades']} ({results['win_rate']:.1%})"
        )
        logger.info(f"Average Win: ${results['avg_win']:,.2f}")
        logger.info(f"Average Loss: ${results['avg_loss']:,.2f}")
        logger.info(f"Profit Factor: {results['profit_factor']:.2f}")
        logger.info(f"Max Consecutive Losses: {results['max_consecutive_losses']}")

        logger.info("\nCapital & Returns:")
        logger.info(f"Starting Capital: ${self.initial_capital:,.2f}")
        logger.info(f"Final Capital: ${results['final_capital']:,.2f}")
        logger.info(f"Total PnL: ${results['total_pnl']:,.2f}")
        logger.info(f"Total Return: {results['total_return']:.2%}")
        logger.info(f"Max Drawdown: {results['max_drawdown']:.2%}")
        logger.info(f"Sharpe Ratio: {results['sharpe_ratio']:.2f}")
        logger.info(f"Sortino Ratio: {results['sortino_ratio']:.2f}")

        logger.info("\nLeverage Usage:")
        logger.info(f"Average Leverage: {results['avg_leverage']:.1f}:1")
        logger.info(f"Max Leverage Used: {results['max_leverage']:.1f}:1")
        logger.info(f"Total Commission: ${results['total_commission']:,.2f}")

        # Save detailed results
        self._save_results(results, start_date, end_date)

        return results

    async def _generate_multi_source_signals(
        self,
        data: pd.DataFrame,
        current_time: datetime,
        ml_model: Optional[Dict],
        current_bar: pd.Series,
    ) -> List[Dict[str, Any]]:
        """Generate signals from multiple sources for more opportunities."""
        signals = []

        if len(data) < 200:
            return signals

        current_price = current_bar["close"]

        # 1. ML Model signals
        if ml_model and "model" in ml_model:
            ml_signal = await self._generate_ml_signal(
                data, current_time, ml_model, current_price
            )
            if ml_signal:
                ml_signal["source"] = "ML Model"
                signals.append(ml_signal)

        # 2. Moving Average Crossover signals
        ma_signal = self._generate_ma_crossover_signal(
            data, current_time, current_price
        )
        if ma_signal:
            ma_signal["source"] = "MA Crossover"
            signals.append(ma_signal)

        # 3. RSI Divergence signals
        rsi_signal = self._generate_rsi_divergence_signal(
            data, current_time, current_price
        )
        if rsi_signal:
            rsi_signal["source"] = "RSI Divergence"
            signals.append(rsi_signal)

        # 4. Bollinger Band signals
        bb_signal = self._generate_bollinger_band_signal(
            data, current_time, current_price
        )
        if bb_signal:
            bb_signal["source"] = "Bollinger Bands"
            signals.append(bb_signal)

        # 5. MACD signals
        macd_signal = self._generate_macd_signal(data, current_time, current_price)
        if macd_signal:
            macd_signal["source"] = "MACD"
            signals.append(macd_signal)

        # 6. Support/Resistance breakout signals
        sr_signal = self._generate_support_resistance_signal(
            data, current_time, current_price
        )
        if sr_signal:
            sr_signal["source"] = "S/R Breakout"
            signals.append(sr_signal)

        return signals

    async def _generate_ml_signal(
        self,
        data: pd.DataFrame,
        current_time: datetime,
        ml_model: Dict,
        current_price: float,
    ) -> Optional[Dict[str, Any]]:
        """Generate ML-based signal."""
        try:
            features = data.iloc[-1:].copy()

            # Apply scaler if available
            if ml_model.get("scaler"):
                feature_cols = [
                    col
                    for col in features.columns
                    if col not in ["open", "high", "low", "close", "volume"]
                ]
                if feature_cols:
                    features[feature_cols] = ml_model["scaler"].transform(
                        features[feature_cols]
                    )

            # Make prediction
            if hasattr(ml_model["model"], "predict_proba"):
                proba = ml_model["model"].predict_proba(features.iloc[-1:])
                confidence = float(proba[0][1]) if proba.shape[1] > 1 else 0.5
            else:
                prediction = ml_model["model"].predict(features.iloc[-1:])
                confidence = 0.7 if prediction[0] > 0 else 0.3

            if confidence > 0.55 or confidence < 0.45:  # Signal on both directions
                direction = "BUY" if confidence > 0.5 else "SELL"
                return {
                    "symbol": "GBPUSD",
                    "direction": direction,
                    "confidence": abs(confidence - 0.5) * 2
                    + 0.5,  # Normalize confidence
                    "timestamp": current_time,
                    "entry_price": current_price,
                    "stop_loss": current_price
                    * (0.997 if direction == "BUY" else 1.003),
                    "take_profit": current_price
                    * (1.006 if direction == "BUY" else 0.994),
                    "timeframe": "4H",
                }
        except Exception as e:
            logger.debug(f"ML prediction failed: {e}")

        return None

    def _generate_ma_crossover_signal(
        self, data: pd.DataFrame, current_time: datetime, current_price: float
    ) -> Optional[Dict[str, Any]]:
        """Generate MA crossover signals."""
        # Fast and slow MAs
        ma_fast = data["close"].rolling(10).mean()
        ma_slow = data["close"].rolling(20).mean()
        ma_trend = data["close"].rolling(50).mean()

        if len(ma_fast) < 2 or pd.isna(ma_trend.iloc[-1]):
            return None

        # Golden/Death cross
        if ma_fast.iloc[-1] > ma_slow.iloc[-1] and ma_fast.iloc[-2] <= ma_slow.iloc[-2]:
            # Golden cross - bullish
            if current_price > ma_trend.iloc[-1]:  # Above trend
                return {
                    "symbol": "GBPUSD",
                    "direction": "BUY",
                    "confidence": 0.65,
                    "timestamp": current_time,
                    "entry_price": current_price,
                    "stop_loss": ma_slow.iloc[-1],
                    "take_profit": current_price
                    + 2 * (current_price - ma_slow.iloc[-1]),
                    "timeframe": "4H",
                }
        elif (
            ma_fast.iloc[-1] < ma_slow.iloc[-1] and ma_fast.iloc[-2] >= ma_slow.iloc[-2]
        ):
            # Death cross - bearish
            if current_price < ma_trend.iloc[-1]:  # Below trend
                return {
                    "symbol": "GBPUSD",
                    "direction": "SELL",
                    "confidence": 0.65,
                    "timestamp": current_time,
                    "entry_price": current_price,
                    "stop_loss": ma_slow.iloc[-1],
                    "take_profit": current_price
                    - 2 * (ma_slow.iloc[-1] - current_price),
                    "timeframe": "4H",
                }

        return None

    def _generate_rsi_divergence_signal(
        self, data: pd.DataFrame, current_time: datetime, current_price: float
    ) -> Optional[Dict[str, Any]]:
        """Generate RSI divergence signals."""
        # Calculate RSI
        delta = data["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))

        if len(rsi) < 50:
            return None

        # Look for divergences
        lookback = 20
        current_rsi = rsi.iloc[-1]

        # Bullish divergence: Price makes lower low, RSI makes higher low
        if current_rsi < 40:  # Oversold
            recent_lows_price = data["low"].iloc[-lookback:].nsmallest(2)
            recent_lows_rsi = rsi.iloc[-lookback:].nsmallest(2)

            if len(recent_lows_price) == 2 and len(recent_lows_rsi) == 2:
                if (
                    recent_lows_price.iloc[1] < recent_lows_price.iloc[0]
                    and recent_lows_rsi.iloc[1] > recent_lows_rsi.iloc[0]
                ):
                    return {
                        "symbol": "GBPUSD",
                        "direction": "BUY",
                        "confidence": 0.6,
                        "timestamp": current_time,
                        "entry_price": current_price,
                        "stop_loss": recent_lows_price.iloc[1] * 0.997,
                        "take_profit": current_price * 1.008,
                        "timeframe": "4H",
                    }

        # Bearish divergence: Price makes higher high, RSI makes lower high
        elif current_rsi > 60:  # Overbought
            recent_highs_price = data["high"].iloc[-lookback:].nlargest(2)
            recent_highs_rsi = rsi.iloc[-lookback:].nlargest(2)

            if len(recent_highs_price) == 2 and len(recent_highs_rsi) == 2:
                if (
                    recent_highs_price.iloc[1] > recent_highs_price.iloc[0]
                    and recent_highs_rsi.iloc[1] < recent_highs_rsi.iloc[0]
                ):
                    return {
                        "symbol": "GBPUSD",
                        "direction": "SELL",
                        "confidence": 0.6,
                        "timestamp": current_time,
                        "entry_price": current_price,
                        "stop_loss": recent_highs_price.iloc[1] * 1.003,
                        "take_profit": current_price * 0.992,
                        "timeframe": "4H",
                    }

        return None

    def _generate_bollinger_band_signal(
        self, data: pd.DataFrame, current_time: datetime, current_price: float
    ) -> Optional[Dict[str, Any]]:
        """Generate Bollinger Band signals."""
        # Calculate Bollinger Bands
        sma = data["close"].rolling(20).mean()
        std = data["close"].rolling(20).std()
        upper_band = sma + 2 * std
        lower_band = sma - 2 * std

        if pd.isna(upper_band.iloc[-1]):
            return None

        # Band squeeze detection
        band_width = (upper_band - lower_band) / sma
        avg_width = band_width.rolling(50).mean()

        if pd.isna(avg_width.iloc[-1]):
            return None

        # Squeeze breakout
        if band_width.iloc[-1] < avg_width.iloc[-1] * 0.7:  # Squeeze detected
            # Wait for breakout
            if current_price > upper_band.iloc[-1]:
                return {
                    "symbol": "GBPUSD",
                    "direction": "BUY",
                    "confidence": 0.7,
                    "timestamp": current_time,
                    "entry_price": current_price,
                    "stop_loss": sma.iloc[-1],
                    "take_profit": current_price + 2 * (current_price - sma.iloc[-1]),
                    "timeframe": "4H",
                }
            elif current_price < lower_band.iloc[-1]:
                return {
                    "symbol": "GBPUSD",
                    "direction": "SELL",
                    "confidence": 0.7,
                    "timestamp": current_time,
                    "entry_price": current_price,
                    "stop_loss": sma.iloc[-1],
                    "take_profit": current_price - 2 * (sma.iloc[-1] - current_price),
                    "timeframe": "4H",
                }

        # Mean reversion signals
        elif current_price < lower_band.iloc[-1] * 0.998:  # Below lower band
            return {
                "symbol": "GBPUSD",
                "direction": "BUY",
                "confidence": 0.55,
                "timestamp": current_time,
                "entry_price": current_price,
                "stop_loss": current_price * 0.995,
                "take_profit": sma.iloc[-1],
                "timeframe": "4H",
            }
        elif current_price > upper_band.iloc[-1] * 1.002:  # Above upper band
            return {
                "symbol": "GBPUSD",
                "direction": "SELL",
                "confidence": 0.55,
                "timestamp": current_time,
                "entry_price": current_price,
                "stop_loss": current_price * 1.005,
                "take_profit": sma.iloc[-1],
                "timeframe": "4H",
            }

        return None

    def _generate_macd_signal(
        self, data: pd.DataFrame, current_time: datetime, current_price: float
    ) -> Optional[Dict[str, Any]]:
        """Generate MACD signals."""
        # Calculate MACD
        exp1 = data["close"].ewm(span=12).mean()
        exp2 = data["close"].ewm(span=26).mean()
        macd = exp1 - exp2
        macd_signal = macd.ewm(span=9).mean()
        macd_hist = macd - macd_signal

        if len(macd_hist) < 2 or pd.isna(macd_hist.iloc[-1]):
            return None

        # MACD crossover
        if macd_hist.iloc[-1] > 0 and macd_hist.iloc[-2] <= 0:
            # Bullish crossover
            return {
                "symbol": "GBPUSD",
                "direction": "BUY",
                "confidence": 0.6,
                "timestamp": current_time,
                "entry_price": current_price,
                "stop_loss": current_price * 0.996,
                "take_profit": current_price * 1.008,
                "timeframe": "4H",
            }
        elif macd_hist.iloc[-1] < 0 and macd_hist.iloc[-2] >= 0:
            # Bearish crossover
            return {
                "symbol": "GBPUSD",
                "direction": "SELL",
                "confidence": 0.6,
                "timestamp": current_time,
                "entry_price": current_price,
                "stop_loss": current_price * 1.004,
                "take_profit": current_price * 0.992,
                "timeframe": "4H",
            }

        return None

    def _generate_support_resistance_signal(
        self, data: pd.DataFrame, current_time: datetime, current_price: float
    ) -> Optional[Dict[str, Any]]:
        """Generate support/resistance breakout signals."""
        if len(data) < 100:
            return None

        # Find recent support/resistance levels
        lookback = 50
        recent_data = data.iloc[-lookback:]

        # Find swing highs and lows
        highs = []
        lows = []

        for i in range(2, len(recent_data) - 2):
            # Swing high
            if (
                recent_data["high"].iloc[i] > recent_data["high"].iloc[i - 1]
                and recent_data["high"].iloc[i] > recent_data["high"].iloc[i - 2]
                and recent_data["high"].iloc[i] > recent_data["high"].iloc[i + 1]
                and recent_data["high"].iloc[i] > recent_data["high"].iloc[i + 2]
            ):
                highs.append(recent_data["high"].iloc[i])

            # Swing low
            if (
                recent_data["low"].iloc[i] < recent_data["low"].iloc[i - 1]
                and recent_data["low"].iloc[i] < recent_data["low"].iloc[i - 2]
                and recent_data["low"].iloc[i] < recent_data["low"].iloc[i + 1]
                and recent_data["low"].iloc[i] < recent_data["low"].iloc[i + 2]
            ):
                lows.append(recent_data["low"].iloc[i])

        if not highs or not lows:
            return None

        # Find key levels
        resistance = max(highs)
        support = min(lows)

        # Breakout signals
        if current_price > resistance * 1.001:  # Resistance breakout
            return {
                "symbol": "GBPUSD",
                "direction": "BUY",
                "confidence": 0.65,
                "timestamp": current_time,
                "entry_price": current_price,
                "stop_loss": resistance * 0.998,
                "take_profit": current_price + 1.5 * (current_price - resistance),
                "timeframe": "4H",
            }
        elif current_price < support * 0.999:  # Support breakdown
            return {
                "symbol": "GBPUSD",
                "direction": "SELL",
                "confidence": 0.65,
                "timestamp": current_time,
                "entry_price": current_price,
                "stop_loss": support * 1.002,
                "take_profit": current_price - 1.5 * (support - current_price),
                "timeframe": "4H",
            }

        return None

    def _calculate_dynamic_position_limit(self) -> int:
        """Calculate dynamic position limit based on current drawdown."""
        if self.current_drawdown < 0.05:  # Less than 5% drawdown
            return self.max_concurrent_positions
        elif self.current_drawdown < 0.10:  # 5-10% drawdown
            return max(5, self.max_concurrent_positions // 2)
        elif self.current_drawdown < 0.15:  # 10-15% drawdown
            return 3
        elif self.current_drawdown < 0.20:  # 15-20% drawdown
            return 2
        else:  # Above 20% drawdown
            return 1

    def _calculate_aggressive_position(
        self, signal: Dict[str, Any], llm_result: Dict[str, Any], current_bar: pd.Series
    ) -> Dict[str, Any]:
        """Calculate aggressive position size with dynamic adjustments."""
        # Base calculations
        stop_distance = abs(signal["entry_price"] - signal["stop_loss"])
        stop_percentage = stop_distance / signal["entry_price"]

        # Dynamic risk based on drawdown
        if self.current_drawdown < 0.05:
            risk_percent = self.max_risk_per_trade
        elif self.current_drawdown < 0.10:
            risk_percent = self.max_risk_per_trade * 0.8
        elif self.current_drawdown < 0.15:
            risk_percent = self.max_risk_per_trade * 0.6
        else:
            risk_percent = self.max_risk_per_trade * 0.4

        # Adjust for consecutive losses
        if self.consecutive_losses > 2:
            risk_percent *= 0.7
        elif self.consecutive_losses > 4:
            risk_percent *= 0.5

        risk_amount = self.capital * risk_percent

        # Position size based on risk
        base_position = risk_amount / stop_distance

        # Confidence multiplier with aggressive weighting
        confidence_multiplier = (
            signal["confidence"] * 0.3
            + signal.get("elliott_wave_score", 0.5) * 0.3
            + llm_result.get("llm_confidence", 0.5) * 0.4
        )

        # Boost confidence for strong signals
        if confidence_multiplier > 0.7:
            confidence_multiplier *= 1.5

        # Calculate target leverage based on signal strength
        signal_leverage = self.target_leverage * confidence_multiplier

        # Apply leverage with dynamic adjustments
        leveraged_position = min(
            base_position * confidence_multiplier, self.capital * signal_leverage
        )

        # Max position checks
        max_position = self.capital * min(self.max_leverage, signal_leverage * 2)
        position_size = min(leveraged_position, max_position)

        # Round to micro lots
        lots = max(1, round(position_size / self.min_lot_size))
        position_size = lots * self.min_lot_size

        # Calculate effective leverage
        effective_leverage = position_size / self.capital

        return {
            "position_size": position_size,
            "lots": lots,
            "effective_leverage": effective_leverage,
            "risk_amount": stop_percentage * position_size,
            "signal_strength": confidence_multiplier,
        }

    async def _validate_elliott_wave(
        self, price_data: pd.DataFrame, signal: Dict[str, Any]
    ) -> float:
        """Validate signal with Elliott Wave analysis - more lenient."""
        try:
            # Analyze wave patterns
            wave_count = self.elliott_analyzer.analyze(price_data)

            if wave_count and wave_count.waves:
                # Base score starts higher for aggressive trading
                wave_score = 0.6

                # Any wave pattern adds to score
                patterns = (
                    wave_count.waves[-5:]
                    if len(wave_count.waves) >= 5
                    else wave_count.waves
                )

                for pattern in patterns:
                    if pattern.confidence > 0.5:
                        wave_score += 0.1

                return min(wave_score, 0.95)
            else:
                return 0.5  # Neutral if no clear pattern

        except Exception as e:
            logger.error(f"Elliott Wave validation error: {e}")
            return 0.5

    async def _validate_with_llm(
        self,
        signal: Dict[str, Any],
        current_time: datetime,
        historical_data: Dict[str, pd.DataFrame],
        indicators_by_tf: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Validate signal with multi-timeframe LLM analysis."""
        # Align data to signal time
        aligned_data = {}
        aligned_indicators = {}

        for tf, data in historical_data.items():
            tf_data = data[data.index <= current_time]
            if len(tf_data) > 100:
                tf_data = tf_data.tail(100)
            aligned_data[tf] = tf_data

            if tf in indicators_by_tf:
                aligned_indicators[tf] = self._align_indicators(
                    indicators_by_tf[tf], tf_data
                )

        # Validate with LLM
        try:
            validation = await self.mtf_validator.validate_trading_signal_mtf(
                signal, aligned_data, aligned_indicators
            )
            return validation
        except Exception as e:
            logger.error(f"LLM validation error: {e}")
            # Return positive validation to not block trades on LLM errors
            return {"valid": True, "llm_confidence": 0.6}

    def _execute_trade(
        self,
        signal: Dict[str, Any],
        position: Dict[str, Any],
        llm_result: Dict[str, Any],
        wave_score: float,
    ):
        """Execute a trade with all details."""
        trade_id = f"{signal['symbol']}_{signal['timestamp'].strftime('%Y%m%d_%H%M%S')}_{len(self.trades)}"

        # Calculate commission
        commission = (position["position_size"] / 1000) * self.commission_per_lot * 2

        # Store open position
        self.open_positions[trade_id] = {
            "signal": signal,
            "position": position,
            "llm_result": llm_result,
            "wave_score": wave_score,
            "entry_time": signal["timestamp"],
            "commission": commission,
            "drawdown_at_entry": self.current_drawdown,
        }

        # Deduct commission from capital
        self.capital -= commission

    def _check_exits(self, current_bar: pd.Series, current_time: datetime):
        """Check and process exits with trailing stops."""
        closed_trades = []

        for trade_id, position_data in self.open_positions.items():
            signal = position_data["signal"]
            position = position_data["position"]

            current_price = current_bar["close"]
            exit_price = None
            exit_reason = None

            # Calculate current P&L
            if signal["direction"] == "BUY":
                unrealized_pnl_pct = (current_price - signal["entry_price"]) / signal[
                    "entry_price"
                ]
            else:
                unrealized_pnl_pct = (signal["entry_price"] - current_price) / signal[
                    "entry_price"
                ]

            # Trailing stop logic
            if unrealized_pnl_pct > 0.003:  # 0.3% profit (30 pips)
                # Move stop to breakeven
                if signal["direction"] == "BUY":
                    signal["stop_loss"] = max(
                        signal["stop_loss"], signal["entry_price"] * 1.0005
                    )
                else:
                    signal["stop_loss"] = min(
                        signal["stop_loss"], signal["entry_price"] * 0.9995
                    )

            if unrealized_pnl_pct > 0.005:  # 0.5% profit (50 pips)
                # Trail stop to lock in profit
                if signal["direction"] == "BUY":
                    trail_stop = current_price * 0.997
                    signal["stop_loss"] = max(signal["stop_loss"], trail_stop)
                else:
                    trail_stop = current_price * 1.003
                    signal["stop_loss"] = min(signal["stop_loss"], trail_stop)

            # Check stop loss and take profit
            if signal["direction"] == "BUY":
                if current_price <= signal["stop_loss"]:
                    exit_price = signal["stop_loss"]
                    exit_reason = "Stop Loss"
                elif current_price >= signal["take_profit"]:
                    exit_price = signal["take_profit"]
                    exit_reason = "Take Profit"
            else:
                if current_price >= signal["stop_loss"]:
                    exit_price = signal["stop_loss"]
                    exit_reason = "Stop Loss"
                elif current_price <= signal["take_profit"]:
                    exit_price = signal["take_profit"]
                    exit_reason = "Take Profit"

            if exit_price:
                # Calculate PnL
                if signal["direction"] == "BUY":
                    pnl_pips = (exit_price - signal["entry_price"]) * 10000
                    pnl = (
                        (exit_price - signal["entry_price"])
                        / signal["entry_price"]
                        * position["position_size"]
                    )
                else:
                    pnl_pips = (signal["entry_price"] - exit_price) * 10000
                    pnl = (
                        (signal["entry_price"] - exit_price)
                        / signal["entry_price"]
                        * position["position_size"]
                    )

                # Subtract commission
                pnl -= position_data["commission"]

                # Update capital
                self.capital += pnl

                # Track consecutive losses
                if pnl < 0:
                    self.consecutive_losses += 1
                else:
                    self.consecutive_losses = 0

                # Record trade
                trade = AggressiveTrade(
                    timestamp=current_time,
                    direction=signal["direction"],
                    entry_price=signal["entry_price"],
                    exit_price=exit_price,
                    position_size=position["position_size"],
                    lots=position["lots"],
                    leverage_used=position["effective_leverage"],
                    pnl=pnl,
                    pnl_pips=pnl_pips,
                    ml_confidence=signal["confidence"],
                    llm_confidence=position_data["llm_result"].get("llm_confidence", 0),
                    elliott_wave_score=position_data["wave_score"],
                    signal_source=signal.get("source", "Unknown"),
                    exit_reason=exit_reason,
                    drawdown_at_entry=position_data["drawdown_at_entry"],
                )

                self.trades.append(trade)
                closed_trades.append(trade_id)

        # Remove closed trades
        for trade_id in closed_trades:
            del self.open_positions[trade_id]

    def _close_all_positions(self, current_bar: pd.Series, current_time: datetime):
        """Close all open positions."""
        for trade_id in list(self.open_positions.keys()):
            position_data = self.open_positions[trade_id]
            signal = position_data["signal"]
            position = position_data["position"]

            exit_price = current_bar["close"]

            # Calculate PnL
            if signal["direction"] == "BUY":
                pnl_pips = (exit_price - signal["entry_price"]) * 10000
                pnl = (
                    (exit_price - signal["entry_price"])
                    / signal["entry_price"]
                    * position["position_size"]
                )
            else:
                pnl_pips = (signal["entry_price"] - exit_price) * 10000
                pnl = (
                    (signal["entry_price"] - exit_price)
                    / signal["entry_price"]
                    * position["position_size"]
                )

            # Subtract commission
            pnl -= position_data["commission"]

            # Update capital
            self.capital += pnl

            # Record trade
            trade = AggressiveTrade(
                timestamp=current_time,
                direction=signal["direction"],
                entry_price=signal["entry_price"],
                exit_price=exit_price,
                position_size=position["position_size"],
                lots=position["lots"],
                leverage_used=position["effective_leverage"],
                pnl=pnl,
                pnl_pips=pnl_pips,
                ml_confidence=signal["confidence"],
                llm_confidence=position_data["llm_result"].get("llm_confidence", 0),
                elliott_wave_score=position_data["wave_score"],
                signal_source=signal.get("source", "Unknown"),
                exit_reason="Forced Close",
                drawdown_at_entry=position_data["drawdown_at_entry"],
            )

            self.trades.append(trade)

        self.open_positions.clear()

    def _calculate_current_equity(self, current_bar: pd.Series) -> float:
        """Calculate current equity including open positions."""
        equity = self.capital

        for position_data in self.open_positions.values():
            signal = position_data["signal"]
            position = position_data["position"]
            current_price = current_bar["close"]

            # Unrealized PnL
            if signal["direction"] == "BUY":
                unrealized_pnl = (
                    (current_price - signal["entry_price"])
                    / signal["entry_price"]
                    * position["position_size"]
                )
            else:
                unrealized_pnl = (
                    (signal["entry_price"] - current_price)
                    / signal["entry_price"]
                    * position["position_size"]
                )

            equity += unrealized_pnl

        return equity

    def _calculate_comprehensive_indicators(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Calculate comprehensive indicators for analysis."""
        indicators = {}

        if len(data) < 50:
            return indicators

        # Trend indicators
        for period in [10, 20, 50, 100, 200]:
            if len(data) >= period:
                indicators[f"sma_{period}"] = data["close"].rolling(period).mean()
                indicators[f"ema_{period}"] = data["close"].ewm(span=period).mean()

        # Momentum
        delta = data["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        indicators["rsi"] = 100 - (100 / (1 + rs))

        # MACD
        exp1 = data["close"].ewm(span=12).mean()
        exp2 = data["close"].ewm(span=26).mean()
        indicators["macd"] = exp1 - exp2
        indicators["macd_signal"] = indicators["macd"].ewm(span=9).mean()
        indicators["macd_hist"] = indicators["macd"] - indicators["macd_signal"]

        # Volatility
        indicators["atr"] = self._calculate_atr(data)
        bb_sma = data["close"].rolling(20).mean()
        bb_std = data["close"].rolling(20).std()
        indicators["bb_upper"] = bb_sma + (bb_std * 2)
        indicators["bb_lower"] = bb_sma - (bb_std * 2)
        indicators["bb_width"] = (
            indicators["bb_upper"] - indicators["bb_lower"]
        ) / bb_sma

        return indicators

    def _calculate_atr(self, data: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate Average True Range."""
        high_low = data["high"] - data["low"]
        high_close = np.abs(data["high"] - data["close"].shift())
        low_close = np.abs(data["low"] - data["close"].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = np.max(ranges, axis=1)
        return true_range.rolling(period).mean()

    def _align_indicators(
        self, indicators: Dict[str, Any], data: pd.DataFrame
    ) -> Dict[str, Any]:
        """Align indicators to data index."""
        aligned = {}

        for name, ind in indicators.items():
            if isinstance(ind, pd.Series) and hasattr(ind, "index"):
                aligned[name] = ind[ind.index.isin(data.index)]
            else:
                aligned[name] = ind

        return aligned

    async def _load_ml_model(self, symbol: str):
        """Load ML model if available."""
        # Check for existing trained models
        model_paths = [
            f"models/{symbol}_100x_leverage/gb_model.pkl",
            f"models/{symbol}_100x_leverage/rf_model.pkl",
            f"models/{symbol}_100x_simple/model.pkl",
        ]

        for model_path in model_paths:
            if Path(model_path).exists():
                logger.info(f"Loading ML model from {model_path}")
                try:
                    with open(model_path, "rb") as f:
                        model = pickle.load(f)

                    # Load scaler if available
                    scaler_path = Path(model_path).parent / "scaler.pkl"
                    if scaler_path.exists():
                        with open(scaler_path, "rb") as f:
                            scaler = pickle.load(f)
                    else:
                        scaler = None

                    return {"model": model, "scaler": scaler, "path": model_path}
                except Exception as e:
                    logger.warning(f"Failed to load model {model_path}: {e}")

        logger.info("No ML model found, using technical analysis")
        return None

    def _calculate_results(self) -> Dict[str, Any]:
        """Calculate comprehensive backtest results."""
        if not self.trades:
            return {
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate": 0,
                "avg_win": 0,
                "avg_loss": 0,
                "profit_factor": 0,
                "total_pnl": 0,
                "final_capital": self.capital,
                "total_return": 0,
                "max_drawdown": 0,
                "sharpe_ratio": 0,
                "sortino_ratio": 0,
                "avg_leverage": 0,
                "max_leverage": 0,
                "total_commission": 0,
                "max_consecutive_losses": 0,
            }

        winning_trades = [t for t in self.trades if t.pnl > 0]
        losing_trades = [t for t in self.trades if t.pnl <= 0]

        # Basic metrics
        total_pnl = sum(t.pnl for t in self.trades)
        total_return = (self.capital - self.initial_capital) / self.initial_capital

        # Win/Loss metrics
        win_rate = len(winning_trades) / len(self.trades) if self.trades else 0
        avg_win = np.mean([t.pnl for t in winning_trades]) if winning_trades else 0
        avg_loss = np.mean([abs(t.pnl) for t in losing_trades]) if losing_trades else 0

        # Profit factor
        gross_profit = sum(t.pnl for t in winning_trades) if winning_trades else 0
        gross_loss = sum(abs(t.pnl) for t in losing_trades) if losing_trades else 0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

        # Risk metrics
        returns = [t.pnl / self.initial_capital for t in self.trades]
        sharpe_ratio = (
            np.mean(returns) / np.std(returns) * np.sqrt(252)
            if returns and np.std(returns) > 0
            else 0
        )

        # Sortino ratio (downside deviation)
        negative_returns = [r for r in returns if r < 0]
        downside_dev = np.std(negative_returns) if negative_returns else 0
        sortino_ratio = (
            np.mean(returns) / downside_dev * np.sqrt(252) if downside_dev > 0 else 0
        )

        # Leverage metrics
        leverages = [t.leverage_used for t in self.trades]
        avg_leverage = np.mean(leverages) if leverages else 0
        max_leverage = max(leverages) if leverages else 0

        # Commission
        total_commission = sum(
            t.position_size / 1000 * self.commission_per_lot * 2 for t in self.trades
        )

        # Max consecutive losses
        max_consecutive = 0
        current_consecutive = 0
        for trade in self.trades:
            if trade.pnl < 0:
                current_consecutive += 1
                max_consecutive = max(max_consecutive, current_consecutive)
            else:
                current_consecutive = 0

        # Signal source analysis
        signal_sources = {}
        for trade in self.trades:
            source = trade.signal_source
            if source not in signal_sources:
                signal_sources[source] = {"count": 0, "pnl": 0}
            signal_sources[source]["count"] += 1
            signal_sources[source]["pnl"] += trade.pnl

        return {
            "total_trades": len(self.trades),
            "winning_trades": len(winning_trades),
            "losing_trades": len(losing_trades),
            "win_rate": win_rate,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "profit_factor": profit_factor,
            "total_pnl": total_pnl,
            "final_capital": self.capital,
            "total_return": total_return,
            "max_drawdown": self.max_drawdown,
            "sharpe_ratio": sharpe_ratio,
            "sortino_ratio": sortino_ratio,
            "avg_leverage": avg_leverage,
            "max_leverage": max_leverage,
            "avg_pnl_pips": (
                np.mean([t.pnl_pips for t in self.trades]) if self.trades else 0
            ),
            "total_commission": total_commission,
            "max_consecutive_losses": max_consecutive,
            "signal_sources": signal_sources,
        }

    def _save_results(
        self, results: Dict[str, Any], start_date: datetime, end_date: datetime
    ):
        """Save detailed backtest results."""
        output_dir = Path("output/aggressive_backtest_400x")
        output_dir.mkdir(parents=True, exist_ok=True)

        # Prepare data for JSON
        save_data = {
            "config": {
                "initial_capital": self.initial_capital,
                "max_leverage": self.max_leverage,
                "target_leverage": self.target_leverage,
                "min_lot_size": self.min_lot_size,
                "max_drawdown_limit": self.max_drawdown_limit,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
            "results": results,
            "trades": [
                {
                    "timestamp": t.timestamp.isoformat(),
                    "direction": t.direction,
                    "entry_price": t.entry_price,
                    "exit_price": t.exit_price,
                    "position_size": t.position_size,
                    "lots": t.lots,
                    "leverage_used": t.leverage_used,
                    "pnl": t.pnl,
                    "pnl_pips": t.pnl_pips,
                    "ml_confidence": t.ml_confidence,
                    "llm_confidence": t.llm_confidence,
                    "elliott_wave_score": t.elliott_wave_score,
                    "signal_source": t.signal_source,
                    "exit_reason": t.exit_reason,
                    "drawdown_at_entry": t.drawdown_at_entry,
                }
                for t in self.trades
            ],
            "equity_curve": [
                {
                    "timestamp": (
                        point["timestamp"].isoformat()
                        if hasattr(point["timestamp"], "isoformat")
                        else str(point["timestamp"])
                    ),
                    "equity": point["equity"],
                }
                for point in (
                    self.equity_curve[-500:]
                    if len(self.equity_curve) > 500
                    else self.equity_curve
                )
            ],
        }

        filename = (
            output_dir
            / f'aggressive_backtest_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        )
        with open(filename, "w") as f:
            json.dump(save_data, f, indent=2)

        logger.info(f"\nDetailed results saved to: {filename}")


async def main():
    """Run the aggressive backtest."""
    # Check for API key
    polygon_api_key = os.getenv("POLYGON_API_KEY")
    if not polygon_api_key:
        logger.error("POLYGON_API_KEY not found in .env file")
        return

    # Initialize aggressive backtester
    backtester = AggressiveBacktester(
        initial_capital=10000,
        max_leverage=400.0,
        target_leverage=50.0,  # Target 50x average leverage
        min_lot_size=1.0,
        commission_per_lot=0.02,
        max_risk_per_trade=0.05,  # 5% max risk
        max_drawdown_limit=0.25,  # 25% drawdown limit
        polygon_api_key=polygon_api_key,
    )

    # Run backtest for 2024
    await backtester.run_backtest(
        symbol="GBPUSD",
        start_date=datetime(2024, 1, 1),
        end_date=datetime(2024, 12, 31),
    )


if __name__ == "__main__":
    asyncio.run(main())
