"""
Comprehensive Technical Indicators for FXML4 GBP/USD Strategy

This module implements 68+ technical indicators specifically optimized for forex trading
and the GBP/USD currency pair. Indicators are organized into categories:

1. Trend Indicators (20+): Moving averages, trend lines, ADX, etc.
2. Momentum Indicators (15+): RSI, MACD, Stochastic, Williams %R, etc.
3. Volume Indicators (8+): OBV, Volume Profile, VWAP, etc.
4. Volatility Indicators (10+): Bollinger Bands, ATR, Keltner Channels, etc.
5. Market Structure (8+): Support/Resistance, Pivot Points, etc.
6. Session-based (7+): London/NY session patterns, overnight gaps, etc.

All indicators are designed for real-time calculation and historical backtesting.
"""

from dataclasses import dataclass
from datetime import datetime, time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import talib


@dataclass
class IndicatorResult:
    """Result of technical indicator calculation"""

    name: str
    value: float
    signal: float  # -1 to 1
    confidence: float  # 0 to 1
    timestamp: datetime
    metadata: Dict[str, Any]


class TechnicalIndicators:
    """
    Comprehensive technical indicators implementation for GBP/USD trading.

    This class provides 68+ technical indicators organized by category,
    with forex-specific optimizations and GBP/USD parameter tuning.
    """

    def __init__(self, config: Dict[str, Any] = None):
        """Initialize technical indicators with configuration"""
        self.config = config or {}

        # Trend indicator parameters
        self.ma_periods = [5, 10, 20, 50, 100, 200]
        self.ema_periods = [8, 13, 21, 34, 55, 89]  # Fibonacci sequence
        self.sma_periods = [9, 14, 25, 50, 200]

        # Momentum parameters
        self.rsi_period = 14
        self.macd_fast = 12
        self.macd_slow = 26
        self.macd_signal = 9
        self.stoch_k = 14
        self.stoch_d = 3
        self.williams_period = 14
        self.roc_periods = [10, 20, 30]

        # Volume parameters (adapted for forex tick volume)
        self.obv_period = 20
        self.vwap_period = 14
        self.volume_sma = 20

        # Volatility parameters
        self.bb_period = 20
        self.bb_std = 2.0
        self.atr_period = 14
        self.keltner_period = 20
        self.keltner_multiplier = 2.0

        # Market structure parameters
        self.pivot_period = 20
        self.support_resistance_period = 50
        self.fibonacci_levels = [0.236, 0.382, 0.5, 0.618, 0.786]

        # Session parameters (GBP/USD specific)
        self.london_open = time(8, 0)  # UTC
        self.london_close = time(17, 0)  # UTC
        self.ny_open = time(13, 0)  # UTC
        self.ny_close = time(22, 0)  # UTC

    def calculate_all_indicators(
        self, data: pd.DataFrame
    ) -> Dict[str, IndicatorResult]:
        """
        Calculate all technical indicators for the given data

        Args:
            data: OHLCV DataFrame with columns: open, high, low, close, volume

        Returns:
            Dictionary of indicator results
        """
        results = {}

        # Trend indicators
        results.update(self._calculate_trend_indicators(data))

        # Momentum indicators
        results.update(self._calculate_momentum_indicators(data))

        # Volume indicators
        results.update(self._calculate_volume_indicators(data))

        # Volatility indicators
        results.update(self._calculate_volatility_indicators(data))

        # Market structure indicators
        results.update(self._calculate_market_structure_indicators(data))

        # Session-based indicators
        results.update(self._calculate_session_indicators(data))

        return results

    def _calculate_trend_indicators(
        self, data: pd.DataFrame
    ) -> Dict[str, IndicatorResult]:
        """Calculate trend-based indicators (20+ indicators)"""
        results = {}
        current_price = data["close"].iloc[-1]
        timestamp = datetime.utcnow()

        try:
            # 1-6. Simple Moving Averages
            for period in self.sma_periods:
                if len(data) >= period:
                    sma = talib.SMA(data["close"], timeperiod=period)
                    sma_value = sma.iloc[-1]
                    signal = self._calculate_ma_signal(current_price, sma_value)

                    results[f"sma_{period}"] = IndicatorResult(
                        name=f"SMA_{period}",
                        value=sma_value,
                        signal=signal,
                        confidence=0.7,
                        timestamp=timestamp,
                        metadata={"period": period, "type": "trend"},
                    )

            # 7-12. Exponential Moving Averages
            for period in self.ema_periods:
                if len(data) >= period:
                    ema = talib.EMA(data["close"], timeperiod=period)
                    ema_value = ema.iloc[-1]
                    signal = self._calculate_ma_signal(current_price, ema_value)

                    results[f"ema_{period}"] = IndicatorResult(
                        name=f"EMA_{period}",
                        value=ema_value,
                        signal=signal,
                        confidence=0.75,
                        timestamp=timestamp,
                        metadata={"period": period, "type": "trend"},
                    )

            # 13. Double Exponential Moving Average (DEMA)
            if len(data) >= 21:
                dema = talib.DEMA(data["close"], timeperiod=21)
                dema_value = dema.iloc[-1]
                signal = self._calculate_ma_signal(current_price, dema_value)

                results["dema"] = IndicatorResult(
                    name="DEMA",
                    value=dema_value,
                    signal=signal,
                    confidence=0.8,
                    timestamp=timestamp,
                    metadata={"period": 21, "type": "trend"},
                )

            # 14. Triple Exponential Moving Average (TEMA)
            if len(data) >= 21:
                tema = talib.TEMA(data["close"], timeperiod=21)
                tema_value = tema.iloc[-1]
                signal = self._calculate_ma_signal(current_price, tema_value)

                results["tema"] = IndicatorResult(
                    name="TEMA",
                    value=tema_value,
                    signal=signal,
                    confidence=0.8,
                    timestamp=timestamp,
                    metadata={"period": 21, "type": "trend"},
                )

            # 15. Weighted Moving Average (WMA)
            if len(data) >= 20:
                wma = talib.WMA(data["close"], timeperiod=20)
                wma_value = wma.iloc[-1]
                signal = self._calculate_ma_signal(current_price, wma_value)

                results["wma"] = IndicatorResult(
                    name="WMA",
                    value=wma_value,
                    signal=signal,
                    confidence=0.75,
                    timestamp=timestamp,
                    metadata={"period": 20, "type": "trend"},
                )

            # 16. Parabolic SAR
            if len(data) >= 20:
                sar = talib.SAR(
                    data["high"], data["low"], acceleration=0.02, maximum=0.2
                )
                sar_value = sar.iloc[-1]
                signal = 1.0 if current_price > sar_value else -1.0

                results["sar"] = IndicatorResult(
                    name="SAR",
                    value=sar_value,
                    signal=signal,
                    confidence=0.85,
                    timestamp=timestamp,
                    metadata={"type": "trend", "interpretation": "trailing_stop"},
                )

            # 17. Average Directional Index (ADX)
            if len(data) >= 14:
                adx = talib.ADX(data["high"], data["low"], data["close"], timeperiod=14)
                adx_value = adx.iloc[-1]

                # ADX signal interpretation
                if adx_value > 50:
                    signal = 0.8  # Strong trend
                elif adx_value > 25:
                    signal = 0.4  # Moderate trend
                else:
                    signal = -0.2  # Weak trend

                results["adx"] = IndicatorResult(
                    name="ADX",
                    value=adx_value,
                    signal=signal,
                    confidence=0.9,
                    timestamp=timestamp,
                    metadata={"period": 14, "type": "trend_strength"},
                )

            # 18. Directional Movement Index (DMI)
            if len(data) >= 14:
                plus_di = talib.PLUS_DI(
                    data["high"], data["low"], data["close"], timeperiod=14
                )
                minus_di = talib.MINUS_DI(
                    data["high"], data["low"], data["close"], timeperiod=14
                )

                plus_di_value = plus_di.iloc[-1]
                minus_di_value = minus_di.iloc[-1]

                # DMI crossover signal
                if plus_di_value > minus_di_value:
                    signal = min((plus_di_value - minus_di_value) / 20.0, 1.0)
                else:
                    signal = max((plus_di_value - minus_di_value) / 20.0, -1.0)

                results["dmi"] = IndicatorResult(
                    name="DMI",
                    value=plus_di_value - minus_di_value,
                    signal=signal,
                    confidence=0.85,
                    timestamp=timestamp,
                    metadata={
                        "plus_di": plus_di_value,
                        "minus_di": minus_di_value,
                        "type": "trend_direction",
                    },
                )

            # 19. Aroon Indicator
            if len(data) >= 25:
                aroon_down, aroon_up = talib.AROON(
                    data["high"], data["low"], timeperiod=25
                )
                aroon_up_value = aroon_up.iloc[-1]
                aroon_down_value = aroon_down.iloc[-1]

                # Aroon signal
                aroon_diff = aroon_up_value - aroon_down_value
                signal = aroon_diff / 100.0  # Normalize to -1 to 1

                results["aroon"] = IndicatorResult(
                    name="AROON",
                    value=aroon_diff,
                    signal=signal,
                    confidence=0.8,
                    timestamp=timestamp,
                    metadata={
                        "aroon_up": aroon_up_value,
                        "aroon_down": aroon_down_value,
                        "type": "trend",
                    },
                )

            # 20. Linear Regression Slope
            if len(data) >= 14:
                slope = talib.LINEARREG_SLOPE(data["close"], timeperiod=14)
                slope_value = slope.iloc[-1]

                # Normalize slope signal
                signal = np.tanh(slope_value * 1000)  # Scale and normalize

                results["linear_reg_slope"] = IndicatorResult(
                    name="LINEAR_REG_SLOPE",
                    value=slope_value,
                    signal=signal,
                    confidence=0.75,
                    timestamp=timestamp,
                    metadata={"period": 14, "type": "trend_slope"},
                )

        except Exception as e:
            print(f"Error calculating trend indicators: {e}")

        return results

    def _calculate_momentum_indicators(
        self, data: pd.DataFrame
    ) -> Dict[str, IndicatorResult]:
        """Calculate momentum-based indicators (15+ indicators)"""
        results = {}
        timestamp = datetime.utcnow()

        try:
            # 1. Relative Strength Index (RSI)
            if len(data) >= self.rsi_period:
                rsi = talib.RSI(data["close"], timeperiod=self.rsi_period)
                rsi_value = rsi.iloc[-1]

                # RSI signal interpretation
                if rsi_value > 70:
                    signal = -0.8  # Overbought
                elif rsi_value < 30:
                    signal = 0.8  # Oversold
                elif rsi_value > 60:
                    signal = -0.4
                elif rsi_value < 40:
                    signal = 0.4
                else:
                    signal = 0.0  # Neutral

                results["rsi"] = IndicatorResult(
                    name="RSI",
                    value=rsi_value,
                    signal=signal,
                    confidence=0.9,
                    timestamp=timestamp,
                    metadata={"period": self.rsi_period, "type": "momentum"},
                )

            # 2-4. Multi-timeframe RSI
            for period in [7, 21, 28]:
                if len(data) >= period:
                    rsi = talib.RSI(data["close"], timeperiod=period)
                    rsi_value = rsi.iloc[-1]

                    # Multi-timeframe RSI signal
                    if rsi_value > 70:
                        signal = -0.6
                    elif rsi_value < 30:
                        signal = 0.6
                    else:
                        signal = (50 - rsi_value) / 50.0

                    results[f"rsi_{period}"] = IndicatorResult(
                        name=f"RSI_{period}",
                        value=rsi_value,
                        signal=signal,
                        confidence=0.8,
                        timestamp=timestamp,
                        metadata={"period": period, "type": "momentum"},
                    )

            # 5. MACD
            if len(data) >= self.macd_slow:
                macd, signal_line, histogram = talib.MACD(
                    data["close"],
                    fastperiod=self.macd_fast,
                    slowperiod=self.macd_slow,
                    signalperiod=self.macd_signal,
                )

                macd_value = macd.iloc[-1]
                signal_value = signal_line.iloc[-1]
                hist_value = histogram.iloc[-1]

                # MACD signal
                if macd_value > signal_value and hist_value > 0:
                    signal = min(hist_value * 100, 1.0)
                elif macd_value < signal_value and hist_value < 0:
                    signal = max(hist_value * 100, -1.0)
                else:
                    signal = 0.0

                results["macd"] = IndicatorResult(
                    name="MACD",
                    value=hist_value,
                    signal=signal,
                    confidence=0.85,
                    timestamp=timestamp,
                    metadata={
                        "macd": macd_value,
                        "signal": signal_value,
                        "histogram": hist_value,
                        "type": "momentum",
                    },
                )

            # 6. Stochastic Oscillator
            if len(data) >= self.stoch_k:
                slowk, slowd = talib.STOCH(
                    data["high"],
                    data["low"],
                    data["close"],
                    fastk_period=self.stoch_k,
                    slowk_period=self.stoch_d,
                    slowd_period=self.stoch_d,
                )

                k_value = slowk.iloc[-1]
                d_value = slowd.iloc[-1]

                # Stochastic signal
                if k_value > 80 and d_value > 80:
                    signal = -0.8  # Overbought
                elif k_value < 20 and d_value < 20:
                    signal = 0.8  # Oversold
                elif k_value > d_value:
                    signal = 0.4
                else:
                    signal = -0.4

                results["stochastic"] = IndicatorResult(
                    name="STOCHASTIC",
                    value=k_value,
                    signal=signal,
                    confidence=0.8,
                    timestamp=timestamp,
                    metadata={"k": k_value, "d": d_value, "type": "momentum"},
                )

            # 7. Williams %R
            if len(data) >= self.williams_period:
                williams_r = talib.WILLR(
                    data["high"],
                    data["low"],
                    data["close"],
                    timeperiod=self.williams_period,
                )
                williams_value = williams_r.iloc[-1]

                # Williams %R signal
                if williams_value > -20:
                    signal = -0.8  # Overbought
                elif williams_value < -80:
                    signal = 0.8  # Oversold
                else:
                    signal = (williams_value + 50) / 50.0

                results["williams_r"] = IndicatorResult(
                    name="WILLIAMS_R",
                    value=williams_value,
                    signal=signal,
                    confidence=0.75,
                    timestamp=timestamp,
                    metadata={"period": self.williams_period, "type": "momentum"},
                )

            # 8-10. Rate of Change (Multiple periods)
            for period in self.roc_periods:
                if len(data) >= period:
                    roc = talib.ROC(data["close"], timeperiod=period)
                    roc_value = roc.iloc[-1]

                    # ROC signal (normalize)
                    signal = np.tanh(roc_value / 2.0)  # Normalize to -1 to 1

                    results[f"roc_{period}"] = IndicatorResult(
                        name=f"ROC_{period}",
                        value=roc_value,
                        signal=signal,
                        confidence=0.7,
                        timestamp=timestamp,
                        metadata={"period": period, "type": "momentum"},
                    )

            # 11. Commodity Channel Index (CCI)
            if len(data) >= 20:
                cci = talib.CCI(data["high"], data["low"], data["close"], timeperiod=20)
                cci_value = cci.iloc[-1]

                # CCI signal
                if cci_value > 100:
                    signal = min((cci_value - 100) / 100.0, 1.0)
                elif cci_value < -100:
                    signal = max((cci_value + 100) / 100.0, -1.0)
                else:
                    signal = cci_value / 100.0

                results["cci"] = IndicatorResult(
                    name="CCI",
                    value=cci_value,
                    signal=signal,
                    confidence=0.75,
                    timestamp=timestamp,
                    metadata={"period": 20, "type": "momentum"},
                )

            # 12. Money Flow Index (MFI)
            if len(data) >= 14:
                mfi = talib.MFI(
                    data["high"],
                    data["low"],
                    data["close"],
                    data["volume"],
                    timeperiod=14,
                )
                mfi_value = mfi.iloc[-1]

                # MFI signal (similar to RSI but volume-weighted)
                if mfi_value > 80:
                    signal = -0.8
                elif mfi_value < 20:
                    signal = 0.8
                else:
                    signal = (50 - mfi_value) / 50.0

                results["mfi"] = IndicatorResult(
                    name="MFI",
                    value=mfi_value,
                    signal=signal,
                    confidence=0.8,
                    timestamp=timestamp,
                    metadata={"period": 14, "type": "momentum_volume"},
                )

            # 13. Ultimate Oscillator
            if len(data) >= 28:
                ult_osc = talib.ULTOSC(data["high"], data["low"], data["close"])
                ult_value = ult_osc.iloc[-1]

                # Ultimate Oscillator signal
                if ult_value > 70:
                    signal = -0.6
                elif ult_value < 30:
                    signal = 0.6
                else:
                    signal = (50 - ult_value) / 50.0

                results["ultimate_oscillator"] = IndicatorResult(
                    name="ULTIMATE_OSCILLATOR",
                    value=ult_value,
                    signal=signal,
                    confidence=0.75,
                    timestamp=timestamp,
                    metadata={"type": "momentum"},
                )

            # 14. Momentum
            if len(data) >= 10:
                momentum = talib.MOM(data["close"], timeperiod=10)
                mom_value = momentum.iloc[-1]

                # Momentum signal
                signal = np.tanh(mom_value / (data["close"].iloc[-1] * 0.01))

                results["momentum"] = IndicatorResult(
                    name="MOMENTUM",
                    value=mom_value,
                    signal=signal,
                    confidence=0.7,
                    timestamp=timestamp,
                    metadata={"period": 10, "type": "momentum"},
                )

            # 15. Balance of Power
            if len(data) >= 1:
                bop = talib.BOP(data["open"], data["high"], data["low"], data["close"])
                bop_value = bop.iloc[-1]

                # BOP is already normalized between -1 and 1
                signal = bop_value

                results["balance_of_power"] = IndicatorResult(
                    name="BALANCE_OF_POWER",
                    value=bop_value,
                    signal=signal,
                    confidence=0.8,
                    timestamp=timestamp,
                    metadata={"type": "momentum"},
                )

        except Exception as e:
            print(f"Error calculating momentum indicators: {e}")

        return results

    def _calculate_volume_indicators(
        self, data: pd.DataFrame
    ) -> Dict[str, IndicatorResult]:
        """Calculate volume-based indicators (8+ indicators)"""
        results = {}
        timestamp = datetime.utcnow()

        try:
            # Note: In forex, volume is typically tick volume, not actual volume

            # 1. On Balance Volume (OBV)
            if len(data) >= 2:
                obv = talib.OBV(data["close"], data["volume"])
                obv_value = obv.iloc[-1]
                obv_sma = obv.rolling(20).mean().iloc[-1]

                # OBV signal based on trend
                if obv_value > obv_sma:
                    signal = 0.6
                else:
                    signal = -0.6

                results["obv"] = IndicatorResult(
                    name="OBV",
                    value=obv_value,
                    signal=signal,
                    confidence=0.7,
                    timestamp=timestamp,
                    metadata={"obv_sma": obv_sma, "type": "volume"},
                )

            # 2. Volume SMA
            if len(data) >= self.volume_sma:
                vol_sma = data["volume"].rolling(self.volume_sma).mean()
                current_volume = data["volume"].iloc[-1]
                vol_sma_value = vol_sma.iloc[-1]

                # Volume signal (high volume = higher confidence in price moves)
                volume_ratio = (
                    current_volume / vol_sma_value if vol_sma_value > 0 else 1.0
                )
                signal = min(max((volume_ratio - 1.0), -1.0), 1.0)

                results["volume_sma"] = IndicatorResult(
                    name="VOLUME_SMA",
                    value=vol_sma_value,
                    signal=signal,
                    confidence=0.6,
                    timestamp=timestamp,
                    metadata={"volume_ratio": volume_ratio, "type": "volume"},
                )

            # 3. Accumulation/Distribution (A/D)
            if len(data) >= 2:
                ad = talib.AD(data["high"], data["low"], data["close"], data["volume"])
                ad_value = ad.iloc[-1]
                ad_prev = ad.iloc[-2] if len(ad) > 1 else ad_value

                # A/D signal based on change
                ad_change = ad_value - ad_prev
                signal = np.tanh(ad_change / 1000.0)  # Normalize

                results["ad"] = IndicatorResult(
                    name="AD",
                    value=ad_value,
                    signal=signal,
                    confidence=0.75,
                    timestamp=timestamp,
                    metadata={"ad_change": ad_change, "type": "volume"},
                )

            # 4. Volume Weighted Average Price (VWAP) approximation
            if len(data) >= self.vwap_period:
                typical_price = (data["high"] + data["low"] + data["close"]) / 3
                vwap = (typical_price * data["volume"]).rolling(
                    self.vwap_period
                ).sum() / data["volume"].rolling(self.vwap_period).sum()
                vwap_value = vwap.iloc[-1]
                current_price = data["close"].iloc[-1]

                # VWAP signal
                price_vwap_ratio = (current_price - vwap_value) / vwap_value
                signal = np.tanh(price_vwap_ratio * 100)

                results["vwap"] = IndicatorResult(
                    name="VWAP",
                    value=vwap_value,
                    signal=signal,
                    confidence=0.8,
                    timestamp=timestamp,
                    metadata={"price_vwap_ratio": price_vwap_ratio, "type": "volume"},
                )

            # 5. Volume Rate of Change
            if len(data) >= 12:
                vol_roc = data["volume"].pct_change(periods=12).iloc[-1]

                # Volume ROC signal
                signal = np.tanh(vol_roc * 2)  # Normalize

                results["volume_roc"] = IndicatorResult(
                    name="VOLUME_ROC",
                    value=vol_roc,
                    signal=signal,
                    confidence=0.65,
                    timestamp=timestamp,
                    metadata={"period": 12, "type": "volume"},
                )

            # 6. Chaikin Money Flow (CMF)
            if len(data) >= 20:
                # CMF calculation
                money_flow_multiplier = (
                    (data["close"] - data["low"]) - (data["high"] - data["close"])
                ) / (data["high"] - data["low"])
                money_flow_volume = money_flow_multiplier * data["volume"]
                cmf = (
                    money_flow_volume.rolling(20).sum()
                    / data["volume"].rolling(20).sum()
                )
                cmf_value = cmf.iloc[-1]

                # CMF signal
                signal = cmf_value  # CMF is typically between -1 and 1

                results["cmf"] = IndicatorResult(
                    name="CMF",
                    value=cmf_value,
                    signal=signal,
                    confidence=0.8,
                    timestamp=timestamp,
                    metadata={"period": 20, "type": "volume"},
                )

            # 7. Volume Oscillator
            if len(data) >= 28:
                vol_short = data["volume"].rolling(14).mean()
                vol_long = data["volume"].rolling(28).mean()
                vol_osc = ((vol_short - vol_long) / vol_long * 100).iloc[-1]

                # Volume oscillator signal
                signal = np.tanh(vol_osc / 50)  # Normalize

                results["volume_oscillator"] = IndicatorResult(
                    name="VOLUME_OSCILLATOR",
                    value=vol_osc,
                    signal=signal,
                    confidence=0.7,
                    timestamp=timestamp,
                    metadata={"short_period": 14, "long_period": 28, "type": "volume"},
                )

            # 8. Force Index
            if len(data) >= 2:
                force_index = data["volume"] * (data["close"] - data["close"].shift(1))
                fi_ema = force_index.ewm(span=13).mean().iloc[-1]

                # Force index signal
                signal = np.tanh(fi_ema / 1000)  # Normalize

                results["force_index"] = IndicatorResult(
                    name="FORCE_INDEX",
                    value=fi_ema,
                    signal=signal,
                    confidence=0.75,
                    timestamp=timestamp,
                    metadata={"span": 13, "type": "volume"},
                )

        except Exception as e:
            print(f"Error calculating volume indicators: {e}")

        return results

    def _calculate_volatility_indicators(
        self, data: pd.DataFrame
    ) -> Dict[str, IndicatorResult]:
        """Calculate volatility-based indicators (10+ indicators)"""
        results = {}
        timestamp = datetime.utcnow()
        current_price = data["close"].iloc[-1]

        try:
            # 1. Bollinger Bands
            if len(data) >= self.bb_period:
                upper, middle, lower = talib.BBANDS(
                    data["close"],
                    timeperiod=self.bb_period,
                    nbdevup=self.bb_std,
                    nbdevdn=self.bb_std,
                )

                upper_value = upper.iloc[-1]
                middle_value = middle.iloc[-1]
                lower_value = lower.iloc[-1]

                # Bollinger Band position
                bb_position = (current_price - lower_value) / (
                    upper_value - lower_value
                )

                # BB signal
                if bb_position > 0.8:
                    signal = -0.6  # Near upper band (potential reversal)
                elif bb_position < 0.2:
                    signal = 0.6  # Near lower band (potential reversal)
                else:
                    signal = 0.0

                results["bollinger_bands"] = IndicatorResult(
                    name="BOLLINGER_BANDS",
                    value=bb_position,
                    signal=signal,
                    confidence=0.85,
                    timestamp=timestamp,
                    metadata={
                        "upper": upper_value,
                        "middle": middle_value,
                        "lower": lower_value,
                        "position": bb_position,
                        "type": "volatility",
                    },
                )

            # 2. Average True Range (ATR)
            if len(data) >= self.atr_period:
                atr = talib.ATR(
                    data["high"], data["low"], data["close"], timeperiod=self.atr_period
                )
                atr_value = atr.iloc[-1]
                atr_normalized = atr_value / current_price  # Normalize by price

                # ATR signal (higher ATR = higher volatility)
                atr_percentile = self._calculate_percentile(atr, 0.8)
                if atr_value > atr_percentile:
                    signal = 0.6  # High volatility
                else:
                    signal = -0.3  # Lower volatility

                results["atr"] = IndicatorResult(
                    name="ATR",
                    value=atr_value,
                    signal=signal,
                    confidence=0.9,
                    timestamp=timestamp,
                    metadata={
                        "atr_normalized": atr_normalized,
                        "percentile": atr_percentile,
                        "type": "volatility",
                    },
                )

            # 3. Keltner Channels
            if len(data) >= self.keltner_period:
                kc_middle = talib.EMA(data["close"], timeperiod=self.keltner_period)
                kc_atr = talib.ATR(
                    data["high"],
                    data["low"],
                    data["close"],
                    timeperiod=self.keltner_period,
                )
                kc_upper = kc_middle + (self.keltner_multiplier * kc_atr)
                kc_lower = kc_middle - (self.keltner_multiplier * kc_atr)

                upper_value = kc_upper.iloc[-1]
                middle_value = kc_middle.iloc[-1]
                lower_value = kc_lower.iloc[-1]

                # Keltner Channel position
                kc_position = (current_price - lower_value) / (
                    upper_value - lower_value
                )

                # KC signal
                if kc_position > 0.9:
                    signal = -0.7
                elif kc_position < 0.1:
                    signal = 0.7
                else:
                    signal = 0.0

                results["keltner_channels"] = IndicatorResult(
                    name="KELTNER_CHANNELS",
                    value=kc_position,
                    signal=signal,
                    confidence=0.8,
                    timestamp=timestamp,
                    metadata={
                        "upper": upper_value,
                        "middle": middle_value,
                        "lower": lower_value,
                        "position": kc_position,
                        "type": "volatility",
                    },
                )

            # 4-6. Multiple ATR timeframes
            for period in [7, 21, 50]:
                if len(data) >= period:
                    atr = talib.ATR(
                        data["high"], data["low"], data["close"], timeperiod=period
                    )
                    atr_value = atr.iloc[-1]
                    atr_sma = atr.rolling(10).mean().iloc[-1]

                    # ATR trend signal
                    if atr_value > atr_sma:
                        signal = 0.4  # Increasing volatility
                    else:
                        signal = -0.4  # Decreasing volatility

                    results[f"atr_{period}"] = IndicatorResult(
                        name=f"ATR_{period}",
                        value=atr_value,
                        signal=signal,
                        confidence=0.75,
                        timestamp=timestamp,
                        metadata={
                            "period": period,
                            "atr_sma": atr_sma,
                            "type": "volatility",
                        },
                    )

            # 7. Standard Deviation
            if len(data) >= 20:
                std_dev = data["close"].rolling(20).std().iloc[-1]
                std_normalized = std_dev / current_price

                # Standard deviation signal
                std_percentile = self._calculate_percentile(
                    data["close"].rolling(20).std().dropna(), 0.8
                )
                if std_dev > std_percentile:
                    signal = 0.5
                else:
                    signal = -0.2

                results["std_dev"] = IndicatorResult(
                    name="STD_DEV",
                    value=std_dev,
                    signal=signal,
                    confidence=0.7,
                    timestamp=timestamp,
                    metadata={
                        "normalized": std_normalized,
                        "percentile": std_percentile,
                        "type": "volatility",
                    },
                )

            # 8. Historical Volatility
            if len(data) >= 20:
                returns = data["close"].pct_change().dropna()
                hist_vol = returns.rolling(20).std().iloc[-1] * np.sqrt(
                    252
                )  # Annualized

                # Historical volatility signal
                vol_mean = (
                    returns.rolling(60).std().mean() * np.sqrt(252)
                    if len(returns) >= 60
                    else hist_vol
                )

                if hist_vol > vol_mean * 1.5:
                    signal = 0.7  # High volatility
                elif hist_vol < vol_mean * 0.7:
                    signal = -0.5  # Low volatility
                else:
                    signal = 0.0

                results["hist_volatility"] = IndicatorResult(
                    name="HIST_VOLATILITY",
                    value=hist_vol,
                    signal=signal,
                    confidence=0.8,
                    timestamp=timestamp,
                    metadata={"vol_mean": vol_mean, "type": "volatility"},
                )

            # 9. Donchian Channels
            if len(data) >= 20:
                dc_upper = data["high"].rolling(20).max().iloc[-1]
                dc_lower = data["low"].rolling(20).min().iloc[-1]
                dc_middle = (dc_upper + dc_lower) / 2

                # Donchian position
                dc_position = (current_price - dc_lower) / (dc_upper - dc_lower)

                # DC signal
                if dc_position > 0.9:
                    signal = -0.6  # Near upper channel
                elif dc_position < 0.1:
                    signal = 0.6  # Near lower channel
                else:
                    signal = 0.0

                results["donchian_channels"] = IndicatorResult(
                    name="DONCHIAN_CHANNELS",
                    value=dc_position,
                    signal=signal,
                    confidence=0.75,
                    timestamp=timestamp,
                    metadata={
                        "upper": dc_upper,
                        "lower": dc_lower,
                        "middle": dc_middle,
                        "position": dc_position,
                        "type": "volatility",
                    },
                )

            # 10. Volatility Ratio
            if len(data) >= 30:
                short_vol = data["close"].pct_change().rolling(10).std()
                long_vol = data["close"].pct_change().rolling(30).std()
                vol_ratio = (short_vol / long_vol).iloc[-1]

                # Volatility ratio signal
                if vol_ratio > 1.5:
                    signal = 0.6  # Increasing volatility
                elif vol_ratio < 0.7:
                    signal = -0.4  # Decreasing volatility
                else:
                    signal = 0.0

                results["volatility_ratio"] = IndicatorResult(
                    name="VOLATILITY_RATIO",
                    value=vol_ratio,
                    signal=signal,
                    confidence=0.75,
                    timestamp=timestamp,
                    metadata={
                        "short_period": 10,
                        "long_period": 30,
                        "type": "volatility",
                    },
                )

        except Exception as e:
            print(f"Error calculating volatility indicators: {e}")

        return results

    def _calculate_market_structure_indicators(
        self, data: pd.DataFrame
    ) -> Dict[str, IndicatorResult]:
        """Calculate market structure indicators (8+ indicators)"""
        results = {}
        timestamp = datetime.utcnow()
        current_price = data["close"].iloc[-1]

        try:
            # 1. Pivot Points (Standard)
            if len(data) >= 1:
                prev_high = data["high"].iloc[-1]
                prev_low = data["low"].iloc[-1]
                prev_close = data["close"].iloc[-1]

                pivot = (prev_high + prev_low + prev_close) / 3
                r1 = 2 * pivot - prev_low
                s1 = 2 * pivot - prev_high
                r2 = pivot + (prev_high - prev_low)
                s2 = pivot - (prev_high - prev_low)

                # Pivot signal based on price relative to pivot
                if current_price > r1:
                    signal = 0.6
                elif current_price < s1:
                    signal = -0.6
                elif current_price > pivot:
                    signal = 0.3
                else:
                    signal = -0.3

                results["pivot_points"] = IndicatorResult(
                    name="PIVOT_POINTS",
                    value=pivot,
                    signal=signal,
                    confidence=0.8,
                    timestamp=timestamp,
                    metadata={
                        "r1": r1,
                        "s1": s1,
                        "r2": r2,
                        "s2": s2,
                        "current_vs_pivot": (current_price - pivot) / pivot,
                        "type": "structure",
                    },
                )

            # 2. Support and Resistance Levels
            if len(data) >= self.support_resistance_period:
                # Find local highs and lows
                highs = data["high"].rolling(5, center=True).max()
                lows = data["low"].rolling(5, center=True).min()

                # Identify significant levels
                resistance_levels = []
                support_levels = []

                for i in range(5, len(data) - 5):
                    if data["high"].iloc[i] == highs.iloc[i]:
                        resistance_levels.append(data["high"].iloc[i])
                    if data["low"].iloc[i] == lows.iloc[i]:
                        support_levels.append(data["low"].iloc[i])

                # Find nearest levels
                nearest_resistance = (
                    min(resistance_levels, key=lambda x: abs(x - current_price))
                    if resistance_levels
                    else current_price * 1.01
                )
                nearest_support = (
                    min(support_levels, key=lambda x: abs(x - current_price))
                    if support_levels
                    else current_price * 0.99
                )

                # Support/Resistance signal
                resistance_distance = (
                    nearest_resistance - current_price
                ) / current_price
                support_distance = (current_price - nearest_support) / current_price

                if resistance_distance < 0.002:  # Within 20 pips
                    signal = -0.7  # Near resistance
                elif support_distance < 0.002:  # Within 20 pips
                    signal = 0.7  # Near support
                else:
                    signal = 0.0

                results["support_resistance"] = IndicatorResult(
                    name="SUPPORT_RESISTANCE",
                    value=current_price,
                    signal=signal,
                    confidence=0.85,
                    timestamp=timestamp,
                    metadata={
                        "nearest_resistance": nearest_resistance,
                        "nearest_support": nearest_support,
                        "resistance_distance": resistance_distance,
                        "support_distance": support_distance,
                        "type": "structure",
                    },
                )

            # 3-7. Fibonacci Retracement Levels
            if len(data) >= 50:
                # Find recent swing high and low
                recent_data = data.tail(50)
                swing_high = recent_data["high"].max()
                swing_low = recent_data["low"].min()

                # Calculate Fibonacci levels
                fib_levels = {}
                range_size = swing_high - swing_low

                for level in self.fibonacci_levels:
                    fib_levels[f"fib_{level}"] = swing_high - (level * range_size)

                # Find nearest Fibonacci level
                nearest_fib_level = min(
                    fib_levels.values(), key=lambda x: abs(x - current_price)
                )
                fib_distance = abs(current_price - nearest_fib_level) / current_price

                # Fibonacci signal
                if fib_distance < 0.001:  # Within 10 pips of Fibonacci level
                    signal = 0.8 if current_price > nearest_fib_level else -0.8
                else:
                    signal = 0.0

                results["fibonacci_retracement"] = IndicatorResult(
                    name="FIBONACCI_RETRACEMENT",
                    value=nearest_fib_level,
                    signal=signal,
                    confidence=0.75,
                    timestamp=timestamp,
                    metadata={
                        "swing_high": swing_high,
                        "swing_low": swing_low,
                        "fib_levels": fib_levels,
                        "nearest_level": nearest_fib_level,
                        "distance": fib_distance,
                        "type": "structure",
                    },
                )

            # 8. Market Structure Slope
            if len(data) >= 20:
                # Calculate trend slope using linear regression
                x = np.arange(len(data.tail(20)))
                y = data["close"].tail(20).values

                slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)
                slope_normalized = (
                    slope / current_price * 100
                )  # Normalize to percentage

                # Slope signal
                if abs(r_value) > 0.8:  # Strong correlation
                    signal = np.tanh(slope_normalized * 10)  # Amplify and normalize
                else:
                    signal = 0.0

                results["market_structure_slope"] = IndicatorResult(
                    name="MARKET_STRUCTURE_SLOPE",
                    value=slope_normalized,
                    signal=signal,
                    confidence=abs(r_value),
                    timestamp=timestamp,
                    metadata={
                        "r_squared": r_value**2,
                        "p_value": p_value,
                        "std_err": std_err,
                        "type": "structure",
                    },
                )

        except Exception as e:
            print(f"Error calculating market structure indicators: {e}")

        return results

    def _calculate_session_indicators(
        self, data: pd.DataFrame
    ) -> Dict[str, IndicatorResult]:
        """Calculate session-based indicators (7+ indicators)"""
        results = {}
        timestamp = datetime.utcnow()

        try:
            # Add timestamp index if not present
            if not isinstance(data.index, pd.DatetimeIndex):
                data = data.copy()
                data.index = pd.date_range(
                    start="2023-01-01", periods=len(data), freq="1min"
                )

            current_time = datetime.utcnow().time()
            current_price = data["close"].iloc[-1]

            # 1. London Session Indicator
            london_active = self.london_open <= current_time <= self.london_close

            if london_active:
                # During London session
                london_data = data.between_time(self.london_open, self.london_close)
                if not london_data.empty:
                    london_avg = london_data["close"].mean()
                    signal = (current_price - london_avg) / london_avg * 10  # Amplify
                else:
                    signal = 0.5  # Default bullish during London
            else:
                signal = 0.0

            results["london_session"] = IndicatorResult(
                name="LONDON_SESSION",
                value=1.0 if london_active else 0.0,
                signal=signal,
                confidence=0.7,
                timestamp=timestamp,
                metadata={"active": london_active, "type": "session"},
            )

            # 2. New York Session Indicator
            ny_active = self.ny_open <= current_time <= self.ny_close

            if ny_active:
                # During NY session
                ny_data = data.between_time(self.ny_open, self.ny_close)
                if not ny_data.empty:
                    ny_avg = ny_data["close"].mean()
                    signal = (current_price - ny_avg) / ny_avg * 10  # Amplify
                else:
                    signal = 0.3  # Default moderate bullish during NY
            else:
                signal = 0.0

            results["ny_session"] = IndicatorResult(
                name="NY_SESSION",
                value=1.0 if ny_active else 0.0,
                signal=signal,
                confidence=0.7,
                timestamp=timestamp,
                metadata={"active": ny_active, "type": "session"},
            )

            # 3. Session Overlap Indicator (London + NY)
            overlap_active = london_active and ny_active

            if overlap_active:
                signal = 0.8  # Strong signal during overlap
            else:
                signal = 0.0

            results["session_overlap"] = IndicatorResult(
                name="SESSION_OVERLAP",
                value=1.0 if overlap_active else 0.0,
                signal=signal,
                confidence=0.9,
                timestamp=timestamp,
                metadata={"overlap_active": overlap_active, "type": "session"},
            )

            # 4. Overnight Gap Indicator
            if len(data) >= 2:
                today_open = data["open"].iloc[-1]
                yesterday_close = data["close"].iloc[-2]
                gap_size = (today_open - yesterday_close) / yesterday_close

                # Gap signal
                if abs(gap_size) > 0.001:  # Significant gap (>10 pips)
                    signal = np.sign(gap_size) * min(abs(gap_size) * 100, 1.0)
                else:
                    signal = 0.0

                results["overnight_gap"] = IndicatorResult(
                    name="OVERNIGHT_GAP",
                    value=gap_size,
                    signal=signal,
                    confidence=0.8,
                    timestamp=timestamp,
                    metadata={"gap_pips": gap_size * 10000, "type": "session"},
                )

            # 5. Asian Session Low Activity Indicator
            asian_hours = time(22, 0) <= current_time or current_time <= time(8, 0)

            if asian_hours:
                # Lower volatility expected during Asian session for GBP/USD
                signal = -0.3  # Bearish signal for momentum strategies
            else:
                signal = 0.0

            results["asian_session"] = IndicatorResult(
                name="ASIAN_SESSION",
                value=1.0 if asian_hours else 0.0,
                signal=signal,
                confidence=0.6,
                timestamp=timestamp,
                metadata={"asian_active": asian_hours, "type": "session"},
            )

            # 6. Weekend Gap Preparation
            weekday = datetime.utcnow().weekday()  # 0=Monday, 6=Sunday

            if weekday == 4 and current_time >= time(20, 0):  # Friday evening
                signal = -0.4  # Reduce positions before weekend
            elif weekday == 6:  # Sunday
                signal = 0.6  # Prepare for weekly opening
            else:
                signal = 0.0

            results["weekend_preparation"] = IndicatorResult(
                name="WEEKEND_PREPARATION",
                value=weekday,
                signal=signal,
                confidence=0.5,
                timestamp=timestamp,
                metadata={"weekday": weekday, "type": "session"},
            )

            # 7. Hourly Volume Pattern
            if len(data) >= 24:
                current_hour = current_time.hour
                hourly_volumes = []

                for hour in range(24):
                    hour_data = data[data.index.hour == hour]
                    if not hour_data.empty:
                        hourly_volumes.append(hour_data["volume"].mean())
                    else:
                        hourly_volumes.append(0)

                if len(hourly_volumes) == 24 and current_hour < 24:
                    current_hour_vol = hourly_volumes[current_hour]
                    avg_vol = np.mean(hourly_volumes)

                    # Volume pattern signal
                    if avg_vol > 0:
                        vol_ratio = current_hour_vol / avg_vol
                        signal = min(max((vol_ratio - 1.0), -1.0), 1.0)
                    else:
                        signal = 0.0
                else:
                    signal = 0.0

                results["hourly_volume_pattern"] = IndicatorResult(
                    name="HOURLY_VOLUME_PATTERN",
                    value=current_hour_vol if "current_hour_vol" in locals() else 0,
                    signal=signal,
                    confidence=0.6,
                    timestamp=timestamp,
                    metadata={
                        "current_hour": current_hour,
                        "vol_ratio": vol_ratio if "vol_ratio" in locals() else 1.0,
                        "type": "session",
                    },
                )

        except Exception as e:
            print(f"Error calculating session indicators: {e}")

        return results

    # Helper methods

    def _calculate_ma_signal(self, current_price: float, ma_value: float) -> float:
        """Calculate moving average signal"""
        if current_price > ma_value:
            return min((current_price - ma_value) / ma_value * 20, 1.0)
        else:
            return max((current_price - ma_value) / ma_value * 20, -1.0)

    def _calculate_percentile(self, series: pd.Series, percentile: float) -> float:
        """Calculate percentile for a series"""
        try:
            return series.quantile(percentile)
        except:
            return series.iloc[-1] if len(series) > 0 else 0.0
