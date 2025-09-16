"""Integrated signal generator combining ML, Elliott Wave, and LLM sentiment analysis."""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
import logging
from datetime import datetime

from fxml4.wave_analysis.elliott_wave import ElliottWaveAnalyzer
from fxml4.wave_analysis.sentiment_wave_validator import SentimentWaveValidator
from fxml4.strategy.enhanced_wave_signal_generator import EnhancedWaveSignalGenerator
from fxml4.llm_integration.sentiment_analysis import SentimentAnalyzer
from fxml4.strategy.market_regime_detector import MarketRegimeDetector

logger = logging.getLogger(__name__)


@dataclass
class IntegratedSignal:
    """Combined signal from multiple sources."""
    timestamp: datetime
    direction: int  # -1, 0, 1
    confidence: float
    ml_signal: int
    ml_confidence: float
    wave_pattern: Optional[str]
    wave_confidence: float
    sentiment_score: float
    market_regime: str
    risk_score: float
    position_size_multiplier: float
    reasoning: str


class IntegratedSignalGenerator:
    """
    Combines multiple signal sources to prevent overfitting and improve accuracy:
    
    1. ML predictions (with anti-overfitting measures)
    2. Elliott Wave pattern analysis
    3. LLM-based sentiment analysis
    4. Market regime filtering
    
    This multi-model approach reduces reliance on any single model
    and provides better out-of-sample performance.
    """
    
    def __init__(
        self,
        ml_model,
        ml_scaler,
        ml_features: List[str],
        wave_analyzer: Optional[ElliottWaveAnalyzer] = None,
        sentiment_analyzer: Optional[SentimentAnalyzer] = None,
        use_llm_validation: bool = True
    ):
        self.ml_model = ml_model
        self.ml_scaler = ml_scaler
        self.ml_features = ml_features
        
        # Initialize components
        self.wave_analyzer = wave_analyzer or ElliottWaveAnalyzer()
        self.sentiment_analyzer = sentiment_analyzer
        self.wave_signal_generator = EnhancedWaveSignalGenerator()
        
        if use_llm_validation and sentiment_analyzer:
            self.sentiment_validator = SentimentWaveValidator(
                sentiment_analyzer=sentiment_analyzer
            )
        else:
            self.sentiment_validator = None
            
        self.regime_detector = MarketRegimeDetector()
        
        # Signal combination weights
        self.weights = {
            'ml': 0.3,      # Reduced weight due to overfitting risk
            'wave': 0.4,    # Elliott Wave patterns
            'sentiment': 0.2,
            'regime': 0.1
        }
        
    def generate_signal(
        self,
        data: pd.DataFrame,
        current_idx: int,
        market_news: Optional[List[str]] = None
    ) -> IntegratedSignal:
        """
        Generate integrated signal from all sources.
        
        Args:
            data: Market data with indicators
            current_idx: Current bar index
            market_news: Recent news for sentiment analysis
            
        Returns:
            IntegratedSignal with combined analysis
        """
        current_bar = data.iloc[current_idx]
        current_time = data.index[current_idx]
        
        # 1. Get ML signal (with caution due to overfitting)
        ml_signal, ml_confidence = self._get_ml_signal(data, current_idx)
        
        # 2. Get Elliott Wave signal
        wave_signal, wave_pattern, wave_confidence = self._get_wave_signal(
            data, current_idx
        )
        
        # 3. Get sentiment signal
        sentiment_score = self._get_sentiment_signal(market_news, current_time)
        
        # 4. Get market regime
        regime_analysis = self.regime_detector.analyze_market(data, current_idx)
        
        # 5. Combine signals with validation
        combined_signal = self._combine_signals(
            ml_signal, ml_confidence,
            wave_signal, wave_confidence,
            sentiment_score,
            regime_analysis
        )
        
        # 6. Calculate risk and position sizing
        risk_score = self._calculate_risk_score(
            data, current_idx, combined_signal, regime_analysis
        )
        
        position_multiplier = self._calculate_position_multiplier(
            combined_signal['confidence'],
            risk_score,
            regime_analysis
        )
        
        # 7. Generate reasoning
        reasoning = self._generate_reasoning(
            ml_signal, ml_confidence,
            wave_pattern, wave_confidence,
            sentiment_score,
            regime_analysis,
            combined_signal
        )
        
        return IntegratedSignal(
            timestamp=current_time,
            direction=combined_signal['direction'],
            confidence=combined_signal['confidence'],
            ml_signal=ml_signal,
            ml_confidence=ml_confidence,
            wave_pattern=wave_pattern,
            wave_confidence=wave_confidence,
            sentiment_score=sentiment_score,
            market_regime=regime_analysis['market_regime'].value,
            risk_score=risk_score,
            position_size_multiplier=position_multiplier,
            reasoning=reasoning
        )
        
    def _get_ml_signal(
        self,
        data: pd.DataFrame,
        current_idx: int
    ) -> Tuple[int, float]:
        """Get ML model signal with overfitting awareness."""
        try:
            # Prepare features
            X = data[self.ml_features].iloc[current_idx:current_idx+1]
            
            if X.isnull().any().any():
                return 0, 0.3  # Low confidence for missing data
                
            # Scale and predict
            X_scaled = self.ml_scaler.transform(X)
            prediction = self.ml_model.predict(X_scaled)[0]
            
            # Get probability
            if hasattr(self.ml_model, 'predict_proba'):
                proba = self.ml_model.predict_proba(X_scaled)[0]
                confidence = max(proba)
                
                # Reduce confidence if too high (overfitting indicator)
                if confidence > 0.9:
                    confidence = 0.7 + (confidence - 0.9) * 0.5
            else:
                confidence = 0.5
                
            # Convert to signal
            signal = prediction - 1 if hasattr(prediction, '__int__') else int(prediction) - 1
            
            return signal, confidence
            
        except Exception as e:
            logger.warning(f"ML signal error: {e}")
            return 0, 0.3
            
    def _get_wave_signal(
        self,
        data: pd.DataFrame,
        current_idx: int
    ) -> Tuple[int, Optional[str], float]:
        """Get Elliott Wave signal."""
        try:
            # Analyze wave patterns
            wave_count = self.wave_analyzer.analyze(
                data.iloc[max(0, current_idx-500):current_idx+1]
            )
            
            if not wave_count or not wave_count.waves:
                return 0, None, 0.3
                
            # Get current wave position
            current_wave = wave_count.get_current_wave()
            if not current_wave:
                return 0, None, 0.3
                
            # Generate signal based on wave position
            signal_info = self.wave_signal_generator.generate_signal(
                wave_count,
                data.iloc[current_idx]
            )
            
            if signal_info:
                # Validate with sentiment if available
                if self.sentiment_validator:
                    validation = self.sentiment_validator.validate_pattern(
                        wave_count,
                        data.iloc[max(0, current_idx-100):current_idx+1]
                    )
                    confidence = validation.confidence_score
                else:
                    confidence = signal_info.confidence
                    
                return signal_info.signal, current_wave.wave_type.value, confidence
            else:
                return 0, current_wave.wave_type.value, 0.3
                
        except Exception as e:
            logger.warning(f"Wave signal error: {e}")
            return 0, None, 0.3
            
    def _get_sentiment_signal(
        self,
        market_news: Optional[List[str]],
        current_time: datetime
    ) -> float:
        """Get sentiment signal from news analysis."""
        if not self.sentiment_analyzer or not market_news:
            return 0.0  # Neutral
            
        try:
            # Analyze recent news
            sentiment_scores = []
            
            for news_item in market_news[-10:]:  # Last 10 news items
                result = self.sentiment_analyzer.analyze_text(news_item)
                sentiment_scores.append(result['score'])
                
            if sentiment_scores:
                # Weighted average (recent news weighted more)
                weights = np.linspace(0.5, 1.0, len(sentiment_scores))
                weights = weights / weights.sum()
                
                weighted_sentiment = np.average(sentiment_scores, weights=weights)
                
                # Convert to -1 to 1 scale
                return (weighted_sentiment - 0.5) * 2
            else:
                return 0.0
                
        except Exception as e:
            logger.warning(f"Sentiment signal error: {e}")
            return 0.0
            
    def _combine_signals(
        self,
        ml_signal: int,
        ml_confidence: float,
        wave_signal: int,
        wave_confidence: float,
        sentiment_score: float,
        regime_analysis: Dict
    ) -> Dict[str, Any]:
        """Combine signals with weighted voting."""
        
        # Convert sentiment to signal
        sentiment_signal = 1 if sentiment_score > 0.2 else (-1 if sentiment_score < -0.2 else 0)
        
        # Check if regime allows trading
        if not regime_analysis['is_tradeable']:
            return {
                'direction': 0,
                'confidence': 0.0,
                'reason': 'Market regime not suitable for trading'
            }
            
        # Weighted signal combination
        weighted_sum = 0.0
        total_weight = 0.0
        
        # ML signal (reduced weight if low confidence)
        if ml_confidence > 0.6:
            ml_weight = self.weights['ml'] * ml_confidence
            weighted_sum += ml_signal * ml_weight
            total_weight += ml_weight
            
        # Wave signal (higher weight for clear patterns)
        if wave_confidence > 0.5:
            wave_weight = self.weights['wave'] * wave_confidence
            weighted_sum += wave_signal * wave_weight
            total_weight += wave_weight
            
        # Sentiment signal
        if abs(sentiment_score) > 0.2:
            sentiment_weight = self.weights['sentiment'] * abs(sentiment_score)
            weighted_sum += sentiment_signal * sentiment_weight
            total_weight += sentiment_weight
            
        # Regime bonus for trending markets
        if regime_analysis['market_regime'].value in ['trending_up', 'trending_down']:
            regime_weight = self.weights['regime'] * regime_analysis['trend_strength'] / 100
            regime_signal = 1 if regime_analysis['market_regime'].value == 'trending_up' else -1
            weighted_sum += regime_signal * regime_weight
            total_weight += regime_weight
            
        # Calculate final signal
        if total_weight > 0:
            final_score = weighted_sum / total_weight
            
            # Convert to discrete signal
            if final_score > 0.3:
                direction = 1
            elif final_score < -0.3:
                direction = -1
            else:
                direction = 0
                
            # Confidence based on agreement and weights
            confidence = min(abs(final_score), 1.0) * (total_weight / sum(self.weights.values()))
            
            # Require minimum agreement
            signal_agreement = sum([
                ml_signal == direction,
                wave_signal == direction,
                sentiment_signal == direction
            ]) / 3.0
            
            if signal_agreement < 0.5:
                confidence *= 0.7  # Reduce confidence for disagreement
                
        else:
            direction = 0
            confidence = 0.0
            
        return {
            'direction': direction,
            'confidence': confidence,
            'score': weighted_sum / total_weight if total_weight > 0 else 0
        }
        
    def _calculate_risk_score(
        self,
        data: pd.DataFrame,
        current_idx: int,
        combined_signal: Dict,
        regime_analysis: Dict
    ) -> float:
        """Calculate risk score for position sizing."""
        risk_factors = []
        
        # Volatility risk
        current_atr = data.iloc[current_idx].get('atr_14', 0)
        historical_atr = data['atr_14'].rolling(252).mean().iloc[current_idx]
        
        if historical_atr > 0:
            volatility_risk = min(current_atr / historical_atr, 2.0)
            risk_factors.append(volatility_risk)
            
        # Regime risk
        regime_risk_map = {
            'trending_up': 0.3,
            'trending_down': 0.3,
            'ranging': 0.5,
            'volatile': 0.8,
            'choppy': 1.0,
            'breakout': 0.6
        }
        regime_risk = regime_risk_map.get(regime_analysis['market_regime'].value, 0.7)
        risk_factors.append(regime_risk)
        
        # Signal disagreement risk
        disagreement_risk = 1.0 - combined_signal['confidence']
        risk_factors.append(disagreement_risk)
        
        # Average risk score
        return np.mean(risk_factors)
        
    def _calculate_position_multiplier(
        self,
        confidence: float,
        risk_score: float,
        regime_analysis: Dict
    ) -> float:
        """Calculate position size multiplier."""
        
        # Base multiplier from confidence
        base_multiplier = confidence
        
        # Adjust for risk (inverse relationship)
        risk_adjustment = 1.0 - (risk_score * 0.5)
        
        # Regime adjustment
        regime_multiplier = regime_analysis['position_size_multiplier']
        
        # Final multiplier
        final_multiplier = base_multiplier * risk_adjustment * regime_multiplier
        
        # Bounds
        return np.clip(final_multiplier, 0.1, 2.0)
        
    def _generate_reasoning(
        self,
        ml_signal: int,
        ml_confidence: float,
        wave_pattern: Optional[str],
        wave_confidence: float,
        sentiment_score: float,
        regime_analysis: Dict,
        combined_signal: Dict
    ) -> str:
        """Generate human-readable reasoning for the signal."""
        
        reasons = []
        
        # ML reasoning
        if ml_confidence > 0.6:
            ml_dir = "bullish" if ml_signal == 1 else ("bearish" if ml_signal == -1 else "neutral")
            reasons.append(f"ML model: {ml_dir} ({ml_confidence:.1%} confidence)")
            
        # Wave reasoning
        if wave_pattern and wave_confidence > 0.5:
            reasons.append(f"Elliott Wave: {wave_pattern} pattern ({wave_confidence:.1%} confidence)")
            
        # Sentiment reasoning
        if abs(sentiment_score) > 0.2:
            sent_dir = "positive" if sentiment_score > 0 else "negative"
            reasons.append(f"Market sentiment: {sent_dir} ({abs(sentiment_score):.1f})")
            
        # Regime reasoning
        reasons.append(f"Market regime: {regime_analysis['market_regime'].value}")
        
        # Final decision
        if combined_signal['direction'] == 0:
            reasons.append("No trade: insufficient signal strength or agreement")
        else:
            direction = "LONG" if combined_signal['direction'] == 1 else "SHORT"
            reasons.append(f"Signal: {direction} with {combined_signal['confidence']:.1%} confidence")
            
        return " | ".join(reasons)