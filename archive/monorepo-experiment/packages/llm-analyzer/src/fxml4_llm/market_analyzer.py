"""
Market analysis using LLM.
"""

from typing import Dict, Any, List, Optional
import pandas as pd
import json
from datetime import datetime

from fxml4_core.logging import get_logger
from fxml4_llm.client import LLMClient

logger = get_logger(__name__)


class MarketAnalyzer:
    """Analyze market conditions using LLM."""
    
    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client
        self.analysis_cache = {}
    
    async def analyze_market(
        self,
        symbol: str,
        timeframe: str,
        technical_data: pd.DataFrame,
        news_data: Optional[List[Dict[str, Any]]] = None,
        analysis_depth: str = "standard"
    ) -> Dict[str, Any]:
        """Perform comprehensive market analysis."""
        # Prepare market data
        market_data = self._prepare_market_data(symbol, timeframe, technical_data)
        
        # Add news context if available
        if news_data:
            market_data["news_context"] = self._summarize_news(news_data)
        
        # Generate analysis based on depth
        if analysis_depth == "detailed":
            analysis = await self._detailed_analysis(market_data)
        elif analysis_depth == "elliott_wave":
            analysis = await self._elliott_wave_analysis(market_data)
        else:
            analysis = await self._standard_analysis(market_data)
        
        # Cache result
        cache_key = f"{symbol}_{timeframe}_{datetime.now().strftime('%Y%m%d_%H')}"
        self.analysis_cache[cache_key] = analysis
        
        return analysis
    
    async def analyze_elliott_wave(
        self,
        symbol: str,
        price_data: pd.DataFrame,
        wave_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Analyze Elliott Wave patterns."""
        prompt = f"""Analyze the Elliott Wave pattern for {symbol} based on the following data:

Price Data Summary:
- Current Price: {price_data['close'].iloc[-1]:.5f}
- 24h High: {price_data['high'].tail(24).max():.5f}
- 24h Low: {price_data['low'].tail(24).min():.5f}
- Recent Swing Points: {self._identify_swings(price_data)}

"""
        
        if wave_data:
            prompt += f"""
Detected Wave Pattern:
- Wave Type: {wave_data.get('wave_type', 'Unknown')}
- Current Wave: {wave_data.get('current_wave', 'Unknown')}
- Wave Degree: {wave_data.get('degree', 'Unknown')}
- Completion: {wave_data.get('completion', 0):.1f}%
"""
        
        prompt += """
Please provide:
1. Wave count validation and any corrections needed
2. Expected price targets for the current wave
3. Key Fibonacci levels to watch
4. Probability of the wave count being correct
5. Alternative wave counts if applicable
"""
        
        response = await self.llm.complete(
            prompt,
            system="You are an expert Elliott Wave analyst with 20+ years of experience. "
                   "Provide precise wave analysis following Elliott Wave principles."
        )
        
        return {
            "symbol": symbol,
            "timestamp": datetime.now(),
            "wave_analysis": response,
            "price_data_points": len(price_data),
            "current_price": price_data['close'].iloc[-1]
        }
    
    async def generate_trade_narrative(
        self,
        trade_setup: Dict[str, Any]
    ) -> str:
        """Generate narrative explanation for trade setup."""
        prompt = f"""Generate a clear trading narrative for the following setup:

Symbol: {trade_setup.get('symbol')}
Direction: {trade_setup.get('direction')}
Entry Price: {trade_setup.get('entry_price')}
Stop Loss: {trade_setup.get('stop_loss')}
Take Profit: {trade_setup.get('take_profit')}
Risk/Reward: {trade_setup.get('risk_reward_ratio', 'N/A')}

Technical Factors:
{json.dumps(trade_setup.get('technical_factors', {}), indent=2)}

Market Context:
{trade_setup.get('market_context', 'N/A')}

Create a professional trade explanation that covers:
1. Why this trade makes sense
2. Key technical confluences
3. Risk management approach
4. What could invalidate the trade
"""
        
        response = await self.llm.complete(
            prompt,
            system="You are a professional forex trader explaining trades to clients. "
                   "Be clear, concise, and focus on risk management."
        )
        
        return response
    
    async def assess_market_regime(
        self,
        symbol: str,
        data: pd.DataFrame,
        lookback_days: int = 30
    ) -> Dict[str, Any]:
        """Assess current market regime."""
        # Calculate regime indicators
        regime_data = self._calculate_regime_indicators(data, lookback_days)
        
        prompt = f"""Assess the market regime for {symbol} based on:

Volatility Metrics:
- Current ATR: {regime_data['atr_current']:.5f}
- ATR Percentile (30d): {regime_data['atr_percentile']:.1f}%
- Realized Volatility: {regime_data['realized_vol']:.2f}%

Trend Metrics:
- ADX: {regime_data['adx']:.1f}
- Trend Strength: {regime_data['trend_strength']}
- Price vs MA200: {regime_data['price_vs_ma200']:.2f}%

Market Structure:
- Higher Highs/Lows: {regime_data['market_structure']}
- Volume Profile: {regime_data['volume_profile']}

Classify the market regime and provide:
1. Regime classification (Trending/Ranging/Volatile/Quiet)
2. Strength of the regime (1-10)
3. Recommended trading approach
4. Key levels to watch for regime change
"""
        
        response = await self.llm.complete(prompt)
        
        # Parse response and structure output
        return {
            "symbol": symbol,
            "timestamp": datetime.now(),
            "regime_assessment": response,
            "metrics": regime_data,
            "lookback_days": lookback_days
        }
    
    def _prepare_market_data(
        self,
        symbol: str,
        timeframe: str,
        technical_data: pd.DataFrame
    ) -> Dict[str, Any]:
        """Prepare market data for analysis."""
        latest = technical_data.iloc[-1]
        
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "timestamp": latest.name if hasattr(latest, 'name') else datetime.now(),
            "close": latest.get('close', 0),
            "change_24h": self._calculate_change(technical_data),
            "rsi": latest.get('rsi_14', latest.get('rsi', 'N/A')),
            "macd": latest.get('macd', 'N/A'),
            "sma_50": latest.get('sma_50', 'N/A'),
            "sma_200": latest.get('sma_200', 'N/A'),
            "volume": latest.get('volume', 'N/A'),
            "atr": latest.get('atr_14', latest.get('atr', 'N/A'))
        }
    
    def _calculate_change(self, data: pd.DataFrame) -> float:
        """Calculate 24h price change."""
        if len(data) < 24:
            return 0
        
        current = data['close'].iloc[-1]
        previous = data['close'].iloc[-24]
        
        return ((current - previous) / previous) * 100
    
    def _summarize_news(self, news_data: List[Dict[str, Any]]) -> str:
        """Summarize news for context."""
        if not news_data:
            return "No recent news available."
        
        summary = "Recent news:\n"
        for i, news in enumerate(news_data[:5]):  # Top 5 news items
            summary += f"{i+1}. {news.get('title', 'N/A')} ({news.get('sentiment', 'neutral')})\n"
        
        return summary
    
    def _identify_swings(self, data: pd.DataFrame, window: int = 5) -> str:
        """Identify recent swing points."""
        highs = data['high'].rolling(window=window*2+1, center=True).max()
        lows = data['low'].rolling(window=window*2+1, center=True).min()
        
        swing_highs = data[data['high'] == highs].tail(3)
        swing_lows = data[data['low'] == lows].tail(3)
        
        swings = []
        for idx, high in swing_highs.iterrows():
            swings.append(f"High: {high['high']:.5f}")
        
        for idx, low in swing_lows.iterrows():
            swings.append(f"Low: {low['low']:.5f}")
        
        return ", ".join(swings) if swings else "No clear swings identified"
    
    def _calculate_regime_indicators(
        self,
        data: pd.DataFrame,
        lookback_days: int
    ) -> Dict[str, Any]:
        """Calculate market regime indicators."""
        recent_data = data.tail(lookback_days * 24)  # Assuming hourly data
        
        # ATR analysis
        current_atr = data['atr_14'].iloc[-1] if 'atr_14' in data else 0
        atr_series = recent_data.get('atr_14', recent_data.get('atr', pd.Series()))
        atr_percentile = (atr_series < current_atr).sum() / len(atr_series) * 100
        
        # Volatility
        returns = recent_data['close'].pct_change()
        realized_vol = returns.std() * (252 ** 0.5) * 100  # Annualized
        
        # Trend indicators
        adx = data.get('adx', pd.Series()).iloc[-1] if 'adx' in data else 0
        
        # Price vs MA
        ma200 = data.get('sma_200', data.get('ma_200', pd.Series())).iloc[-1]
        price_vs_ma200 = ((data['close'].iloc[-1] - ma200) / ma200 * 100) if ma200 else 0
        
        # Market structure
        highs = recent_data['high']
        lows = recent_data['low']
        higher_highs = (highs.diff() > 0).sum() > len(highs) / 2
        higher_lows = (lows.diff() > 0).sum() > len(lows) / 2
        
        structure = "Uptrend" if higher_highs and higher_lows else "Downtrend"
        
        return {
            "atr_current": current_atr,
            "atr_percentile": atr_percentile,
            "realized_vol": realized_vol,
            "adx": adx,
            "trend_strength": "Strong" if adx > 25 else "Weak",
            "price_vs_ma200": price_vs_ma200,
            "market_structure": structure,
            "volume_profile": "Normal"  # Placeholder
        }
    
    async def _standard_analysis(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """Perform standard market analysis."""
        analysis = await self.llm.analyze_market(market_data, "comprehensive")
        return {
            "type": "standard",
            "timestamp": datetime.now(),
            **analysis
        }
    
    async def _detailed_analysis(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """Perform detailed market analysis."""
        # Get multiple perspectives
        technical = await self.llm.analyze_market(market_data, "comprehensive")
        risk = await self.llm.analyze_market(market_data, "risk_assessment")
        
        return {
            "type": "detailed",
            "timestamp": datetime.now(),
            "technical_analysis": technical,
            "risk_assessment": risk,
            "market_data": market_data
        }
    
    async def _elliott_wave_analysis(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """Perform Elliott Wave focused analysis."""
        analysis = await self.llm.analyze_market(market_data, "elliott_wave")
        return {
            "type": "elliott_wave",
            "timestamp": datetime.now(),
            **analysis
        }