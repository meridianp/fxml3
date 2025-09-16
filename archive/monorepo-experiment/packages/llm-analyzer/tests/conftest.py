"""Shared fixtures and configuration for llm-analyzer tests."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_llm_response():
    """Factory for creating mock LLM responses."""
    def _create_response(content, provider="openai"):
        if provider == "openai":
            response = Mock()
            response.choices = [Mock(message=Mock(content=content))]
            return response
        elif provider == "anthropic":
            response = Mock()
            response.content = [Mock(text=content)]
            return response
        else:
            return content
    
    return _create_response


@pytest.fixture
def sample_technical_indicators():
    """Generate sample technical indicators."""
    return {
        "rsi_14": 65.5,
        "rsi_30": 62.3,
        "macd": 0.0012,
        "macd_signal": 0.0010,
        "macd_histogram": 0.0002,
        "sma_20": 1.0845,
        "sma_50": 1.0840,
        "sma_200": 1.0820,
        "ema_12": 1.0852,
        "ema_26": 1.0848,
        "atr_14": 0.0015,
        "adx": 28.5,
        "stochastic_k": 75.0,
        "stochastic_d": 72.0,
        "bollinger_upper": 1.0870,
        "bollinger_middle": 1.0850,
        "bollinger_lower": 1.0830
    }


@pytest.fixture
def forex_symbols():
    """Common forex symbols for testing."""
    return ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD", "NZDUSD"]


@pytest.fixture
def timeframes():
    """Common timeframes for testing."""
    return ["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w", "1M"]


@pytest.fixture
def market_conditions():
    """Different market condition scenarios."""
    return {
        "trending_up": {
            "description": "Strong uptrend",
            "rsi": 70,
            "adx": 35,
            "price_vs_sma200": 1.5,  # 1.5% above
            "volume_trend": "increasing"
        },
        "trending_down": {
            "description": "Strong downtrend",
            "rsi": 30,
            "adx": 32,
            "price_vs_sma200": -1.2,  # 1.2% below
            "volume_trend": "increasing"
        },
        "ranging": {
            "description": "Sideways market",
            "rsi": 50,
            "adx": 18,
            "price_vs_sma200": 0.1,
            "volume_trend": "decreasing"
        },
        "volatile": {
            "description": "High volatility",
            "rsi": 45,
            "adx": 22,
            "atr_percentile": 90,
            "volume_trend": "spiking"
        },
        "breakout": {
            "description": "Breakout conditions",
            "rsi": 65,
            "adx": 28,
            "volume_spike": 2.5,  # 2.5x average
            "price_action": "new_high"
        }
    }


@pytest.fixture
def elliott_wave_scenarios():
    """Elliott Wave pattern scenarios."""
    return {
        "impulse_wave3": {
            "pattern": "Impulse",
            "current_wave": "3",
            "sub_wave": "iii of 3",
            "degree": "Minor",
            "completion": 65,
            "fibonacci_target": 1.618,
            "confidence": 0.75
        },
        "corrective_abc": {
            "pattern": "Zigzag",
            "current_wave": "B",
            "degree": "Minute",
            "completion": 80,
            "retracement": 0.618,
            "confidence": 0.60
        },
        "ending_diagonal": {
            "pattern": "Ending Diagonal",
            "current_wave": "5",
            "degree": "Minor",
            "completion": 90,
            "overlapping": True,
            "confidence": 0.55
        },
        "complex_correction": {
            "pattern": "Complex Correction",
            "current_wave": "X",
            "degree": "Intermediate",
            "type": "WXY",
            "completion": 40,
            "confidence": 0.45
        }
    }


@pytest.fixture
def sentiment_scenarios():
    """Market sentiment scenarios."""
    return {
        "bullish_extreme": {
            "score": 0.85,
            "confidence": "high",
            "retail_positioning": "90% long",
            "institutional_positioning": "75% long",
            "news_sentiment": "very_positive",
            "social_sentiment": "euphoric"
        },
        "bearish_moderate": {
            "score": -0.45,
            "confidence": "medium",
            "retail_positioning": "65% short",
            "institutional_positioning": "55% short",
            "news_sentiment": "negative",
            "social_sentiment": "pessimistic"
        },
        "neutral_mixed": {
            "score": 0.05,
            "confidence": "low",
            "retail_positioning": "52% long",
            "institutional_positioning": "48% long",
            "news_sentiment": "mixed",
            "social_sentiment": "uncertain"
        },
        "divergent": {
            "score": 0.25,
            "confidence": "medium",
            "retail_positioning": "80% long",
            "institutional_positioning": "70% short",
            "news_sentiment": "negative",
            "social_sentiment": "positive"
        }
    }


@pytest.fixture
def risk_scenarios():
    """Risk assessment scenarios."""
    return {
        "low_risk": {
            "vix_level": 12,
            "correlation_breakdown": False,
            "liquidity": "high",
            "event_risk": "none",
            "technical_risk": "support_holding"
        },
        "moderate_risk": {
            "vix_level": 20,
            "correlation_breakdown": False,
            "liquidity": "normal",
            "event_risk": "upcoming_data",
            "technical_risk": "approaching_resistance"
        },
        "high_risk": {
            "vix_level": 35,
            "correlation_breakdown": True,
            "liquidity": "low",
            "event_risk": "central_bank_meeting",
            "technical_risk": "breakdown_imminent"
        },
        "extreme_risk": {
            "vix_level": 50,
            "correlation_breakdown": True,
            "liquidity": "very_low",
            "event_risk": "black_swan",
            "technical_risk": "cascading_stops"
        }
    }


@pytest.fixture
def mock_market_data_generator():
    """Generate mock market data with various patterns."""
    def _generate(pattern="random", periods=100, timeframe="1h"):
        dates = pd.date_range(end=datetime.now(), periods=periods, freq=timeframe)
        
        if pattern == "uptrend":
            # Generate uptrending data
            base = 1.0800
            trend = 0.0001
            prices = []
            for i in range(periods):
                base += trend + np.random.randn() * 0.0002
                prices.append(base)
        
        elif pattern == "downtrend":
            # Generate downtrending data
            base = 1.0900
            trend = -0.0001
            prices = []
            for i in range(periods):
                base += trend + np.random.randn() * 0.0002
                prices.append(base)
        
        elif pattern == "ranging":
            # Generate ranging data
            center = 1.0850
            prices = []
            for i in range(periods):
                price = center + np.sin(i * 0.1) * 0.0030 + np.random.randn() * 0.0001
                prices.append(price)
        
        else:  # random
            prices = 1.0850 + np.random.randn(periods).cumsum() * 0.0001
        
        # Create OHLC from prices
        df = pd.DataFrame(index=dates)
        df['close'] = prices
        df['open'] = df['close'].shift(1).fillna(df['close'].iloc[0])
        df['high'] = df[['open', 'close']].max(axis=1) + abs(np.random.randn(periods) * 0.0002)
        df['low'] = df[['open', 'close']].min(axis=1) - abs(np.random.randn(periods) * 0.0002)
        df['volume'] = np.random.randint(1000, 10000, periods)
        
        return df
    
    return _generate


@pytest.fixture
def performance_tracker():
    """Track performance metrics during tests."""
    class PerformanceTracker:
        def __init__(self):
            self.metrics = {
                "api_calls": 0,
                "cache_hits": 0,
                "cache_misses": 0,
                "total_tokens": 0,
                "errors": 0,
                "response_times": []
            }
            self.start_time = None
            self.end_time = None
        
        def start(self):
            self.start_time = datetime.now()
        
        def end(self):
            self.end_time = datetime.now()
        
        def record_api_call(self, tokens=0, response_time=0):
            self.metrics["api_calls"] += 1
            self.metrics["total_tokens"] += tokens
            self.metrics["response_times"].append(response_time)
        
        def record_cache_hit(self):
            self.metrics["cache_hits"] += 1
        
        def record_cache_miss(self):
            self.metrics["cache_misses"] += 1
        
        def record_error(self):
            self.metrics["errors"] += 1
        
        def get_summary(self):
            avg_response_time = (
                sum(self.metrics["response_times"]) / len(self.metrics["response_times"])
                if self.metrics["response_times"] else 0
            )
            
            cache_hit_rate = (
                self.metrics["cache_hits"] / 
                (self.metrics["cache_hits"] + self.metrics["cache_misses"])
                if (self.metrics["cache_hits"] + self.metrics["cache_misses"]) > 0
                else 0
            )
            
            return {
                **self.metrics,
                "avg_response_time": avg_response_time,
                "cache_hit_rate": cache_hit_rate,
                "duration": (
                    (self.end_time - self.start_time).total_seconds()
                    if self.start_time and self.end_time else None
                )
            }
    
    return PerformanceTracker()


# Markers for different test types
pytest.mark.unit = pytest.mark.unit
pytest.mark.integration = pytest.mark.integration
pytest.mark.slow = pytest.mark.slow
pytest.mark.requires_api_key = pytest.mark.requires_api_key