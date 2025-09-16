"""Elliott Wave signal generator.

This module provides a signal generator that uses Elliott Wave patterns
to generate trading signals.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from fxml4.config import get_config
from fxml4.strategy.integrated_strategy import Signal, SignalGenerator, SignalSource, SignalType
from fxml4.wave_analysis.elliott_wave import (
    ElliottWavePattern, ElliottWaveCount, WavePosition, WaveDegree, WaveType
)

logger = logging.getLogger(__name__)


class WaveSignalGenerator(SignalGenerator):
    """Signal generator using Elliott Wave patterns."""
    
    def __init__(
        self,
        wave_analyzer: Any,
        config: Optional[Dict[str, Any]] = None
    ):
        """Initialize the Elliott Wave signal generator.
        
        Args:
            wave_analyzer: Elliott Wave analyzer.
            config: Configuration dictionary.
        """
        super().__init__(config)
        self.wave_analyzer = wave_analyzer
        
        # Signal configuration
        self.threshold = self.config.get("threshold", 0.65)
        self.position_weights = self.config.get("position_weights", {
            "impulse_end_5": 0.9,    # End of impulse wave 5
            "correction_end_c": 0.8,  # End of correction wave C
            "impulse_end_3": 0.7,    # End of impulse wave 3
            "correction_end_b": 0.5,  # End of correction wave B
            "diagonal_end": 0.7,     # End of diagonal pattern
            "triangle_end": 0.6,     # End of triangle pattern
            "correction_end_a": 0.4,  # End of correction wave A
            "impulse_end_1": 0.3,    # End of impulse wave 1
        })
        
        # Wave pattern confidence thresholds
        self.pattern_thresholds = self.config.get("pattern_thresholds", {
            "impulse": 0.7,
            "correction": 0.65,
            "diagonal": 0.75,
            "triangle": 0.7,
            "zigzag": 0.65,
            "flat": 0.65,
        })
        
        # Define key positions for trading signals
        self.entry_positions = self.config.get("entry_positions", [
            "correction_end_c",
            "correction_end_a",
            "triangle_end",
        ])
        
        self.exit_positions = self.config.get("exit_positions", [
            "impulse_end_5",
            "diagonal_end",
            "impulse_end_3",
        ])
        
        # LLM integration for pattern confidence
        self.use_llm = self.config.get("use_llm", True)
        self.llm_confidence_weight = self.config.get("llm_confidence_weight", 0.5)
        
        # Reference to RAG system if available
        self.rag = self.config.get("rag", None)
        
        logger.info("Initialized Elliott Wave signal generator")
    
    def get_wave_confidence(
        self, 
        wave_pattern: ElliottWavePattern,
        data: pd.DataFrame,
    ) -> float:
        """Get confidence level for a given wave pattern.
        
        Args:
            wave_pattern: Elliott Wave pattern.
            data: Market data.
            
        Returns:
            Confidence level (0 to 1).
        """
        # Get base confidence from wave pattern
        base_confidence = wave_pattern.confidence
        
        # If LLM integration is enabled and RAG is available
        if self.use_llm and self.rag is not None:
            try:
                # Create market context description
                market_context = self._create_market_context(data)
                
                # Use RAG to validate pattern
                pattern_type = wave_pattern.wave_type.value
                pattern_desc = wave_pattern.to_dict()
                
                query = f"""
                Validate this {pattern_type} Elliott Wave pattern:
                {pattern_desc}
                
                Market context:
                {market_context}
                
                Is this a valid Elliott Wave pattern according to Elliott Wave Principle?
                Rate the confidence from 0 to 1, where 1 is highest confidence.
                """
                
                # Get response from RAG
                response = self.rag.query(query)
                
                # Extract confidence from response (assume response contains a confidence value)
                llm_confidence = self._extract_confidence(response)
                
                # Combine base confidence with LLM confidence
                combined_confidence = (
                    base_confidence * (1 - self.llm_confidence_weight) + 
                    llm_confidence * self.llm_confidence_weight
                )
                
                return combined_confidence
            
            except Exception as e:
                logger.exception("Error using LLM for pattern validation: %s", e)
                return base_confidence
        
        return base_confidence
    
    def _extract_confidence(self, response: str) -> float:
        """Extract confidence value from LLM response.
        
        Args:
            response: LLM response text.
            
        Returns:
            Extracted confidence value (0 to 1).
        """
        try:
            # Look for confidence values in the response text
            import re
            
            # Try to find a direct confidence score
            confidence_pattern = r"confidence[:\s]+(\d+\.\d+)"
            match = re.search(confidence_pattern, response, re.IGNORECASE)
            if match:
                confidence = float(match.group(1))
                return max(0, min(1, confidence))
            
            # Try to find a percentage
            percentage_pattern = r"(\d+)%"
            match = re.search(percentage_pattern, response)
            if match:
                confidence = float(match.group(1)) / 100.0
                return max(0, min(1, confidence))
            
            # Default to a moderate confidence if we can't extract it
            return 0.6
            
        except Exception as e:
            logger.exception("Error extracting confidence from LLM response: %s", e)
            return 0.5
    
    def _create_market_context(self, data: pd.DataFrame) -> str:
        """Create market context description for LLM.
        
        Args:
            data: Market data.
            
        Returns:
            Market context description.
        """
        # Get recent price movement
        recent_data = data.tail(20)
        
        # Calculate key metrics
        try:
            price_change = (recent_data['close'].iloc[-1] - recent_data['close'].iloc[0]) / recent_data['close'].iloc[0] * 100
            avg_volume = recent_data['volume'].mean() if 'volume' in recent_data.columns else "N/A"
            avg_range = ((recent_data['high'] - recent_data['low']) / recent_data['low']).mean() * 100
            
            # Get momentum indicators if available
            rsi = recent_data['rsi'].iloc[-1] if 'rsi' in recent_data.columns else "N/A"
            macd = recent_data['macd'].iloc[-1] if 'macd' in recent_data.columns else "N/A"
            
            # Create context description
            context = f"""
            Recent price change: {price_change:.2f}%
            Average trading range: {avg_range:.2f}%
            Average volume: {avg_volume}
            Latest RSI: {rsi}
            Latest MACD: {macd}
            """
            
            return context
        
        except Exception as e:
            logger.exception("Error creating market context: %s", e)
            return "Error creating market context"
    
    def _get_position_type(self, wave_count: ElliottWaveCount) -> str:
        """Get the current position type in the wave count.
        
        Args:
            wave_count: Current Elliott Wave count.
            
        Returns:
            Position type string.
        """
        if not wave_count or not wave_count.waves:
            return "unknown"
        
        last_wave = wave_count.waves[-1]
        wave_type = last_wave.wave_type
        
        # Identify important positions
        if wave_type == WaveType.IMPULSE:
            if last_wave.subwaves and len(last_wave.subwaves) >= 5:
                return "impulse_end_5"
            elif last_wave.subwaves and len(last_wave.subwaves) >= 3:
                return "impulse_end_3"
            elif last_wave.subwaves and len(last_wave.subwaves) >= 1:
                return "impulse_end_1"
        
        elif wave_type == WaveType.CORRECTION:
            if last_wave.subwaves and len(last_wave.subwaves) >= 3:
                return "correction_end_c"
            elif last_wave.subwaves and len(last_wave.subwaves) >= 2:
                return "correction_end_b"
            elif last_wave.subwaves and len(last_wave.subwaves) >= 1:
                return "correction_end_a"
        
        elif wave_type == WaveType.DIAGONAL:
            return "diagonal_end"
        
        elif wave_type == WaveType.TRIANGLE:
            return "triangle_end"
        
        return "unknown"
    
    def generate_signals(
        self,
        data: pd.DataFrame,
        **kwargs: Any,
    ) -> List[Signal]:
        """Generate trading signals using Elliott Wave patterns.
        
        Args:
            data: Market data.
            **kwargs: Additional arguments.
            
        Returns:
            List of generated signals.
        """
        signals = []
        
        # Extract metadata
        symbol = kwargs.get("symbol", data.get("symbol", ["unknown"])[0] 
                             if "symbol" in data.columns else "unknown")
        timeframe = kwargs.get("timeframe", data.get("timeframe", ["unknown"])[0] 
                               if "timeframe" in data.columns else "unknown")
        
        # Get the latest timestamp
        latest_timestamp = data.index[-1] if isinstance(data.index, pd.DatetimeIndex) else pd.Timestamp.now()
        
        try:
            # Analyze wave patterns
            wave_count = self.wave_analyzer.analyze(data)
            
            if not wave_count or not wave_count.waves:
                logger.debug("No wave patterns detected")
                return signals
            
            # Get the current position in the wave count
            position_type = self._get_position_type(wave_count)
            
            # Get confidence level
            last_wave = wave_count.waves[-1]
            confidence = self.get_wave_confidence(last_wave, data)
            
            # Get pattern-specific threshold
            pattern_type = last_wave.wave_type.value.lower()
            pattern_threshold = self.pattern_thresholds.get(pattern_type, 0.7)
            
            # Skip if confidence is below threshold for this pattern type
            if confidence < pattern_threshold:
                logger.debug("Wave pattern confidence too low: %f < %f", confidence, pattern_threshold)
                return signals
            
            # Get signal strength based on position
            position_strength = self.position_weights.get(position_type, 0.5)
            signal_strength = confidence * position_strength
            
            # Generate entry signals
            if position_type in self.entry_positions and signal_strength >= self.threshold:
                # Determine direction
                if last_wave.wave_type in [WaveType.CORRECTION, WaveType.ZIGZAG]:
                    # After corrections, usually go long for impulse
                    signal_type = SignalType.ENTRY_LONG
                elif last_wave.wave_type == WaveType.IMPULSE and "5" in position_type:
                    # After impulse 5, look for correction
                    signal_type = SignalType.ENTRY_SHORT
                else:
                    # Default to long for other patterns
                    signal_type = SignalType.ENTRY_LONG
                
                # Create signal
                signal = Signal(
                    signal_type=signal_type,
                    strength=signal_strength,
                    source=SignalSource.WAVE,
                    timestamp=latest_timestamp,
                    symbol=symbol,
                    timeframe=timeframe,
                    metadata={
                        "wave_position": position_type,
                        "pattern_type": pattern_type,
                        "wave_confidence": confidence,
                        "pattern_details": last_wave.to_dict(),
                    },
                )
                signals.append(signal)
            
            # Generate exit signals
            if position_type in self.exit_positions and signal_strength >= self.threshold:
                # Determine direction to exit
                if last_wave.wave_type == WaveType.IMPULSE:
                    # After impulse, exit long positions
                    signal_type = SignalType.EXIT_LONG
                elif last_wave.wave_type in [WaveType.CORRECTION, WaveType.ZIGZAG]:
                    # After corrections, exit short positions
                    signal_type = SignalType.EXIT_SHORT
                else:
                    # Default to exit long for other patterns
                    signal_type = SignalType.EXIT_LONG
                
                # Create signal
                signal = Signal(
                    signal_type=signal_type,
                    strength=signal_strength,
                    source=SignalSource.WAVE,
                    timestamp=latest_timestamp,
                    symbol=symbol,
                    timeframe=timeframe,
                    metadata={
                        "wave_position": position_type,
                        "pattern_type": pattern_type,
                        "wave_confidence": confidence,
                        "pattern_details": last_wave.to_dict(),
                    },
                )
                signals.append(signal)
            
        except Exception as e:
            logger.exception("Error generating wave signals: %s", e)
        
        return signals


class LLMWaveSignalGenerator(SignalGenerator):
    """Signal generator using LLM-enhanced Elliott Wave patterns."""
    
    def __init__(
        self,
        wave_analyzer: Any,
        rag: Any,
        config: Optional[Dict[str, Any]] = None
    ):
        """Initialize the LLM-enhanced Elliott Wave signal generator.
        
        Args:
            wave_analyzer: Elliott Wave analyzer.
            rag: RAG system for LLM integration.
            config: Configuration dictionary.
        """
        super().__init__(config)
        self.wave_analyzer = wave_analyzer
        self.rag = rag
        
        # Signal configuration
        self.threshold = self.config.get("threshold", 0.6)
        
        # LLM query templates
        self.entry_template = self.config.get("entry_template", """
        Analyze the following market data and Elliott Wave pattern:
        
        Symbol: {symbol}
        Timeframe: {timeframe}
        
        Elliott Wave Context:
        {wave_context}
        
        Market Data:
        {market_data}
        
        Based on Elliott Wave Principle, should I enter a trade now?
        If yes, should I go long or short?
        What is your confidence level (0-1) in this recommendation?
        """)
        
        self.exit_template = self.config.get("exit_template", """
        Analyze the following market data and Elliott Wave pattern:
        
        Symbol: {symbol}
        Timeframe: {timeframe}
        
        Elliott Wave Context:
        {wave_context}
        
        Market Data:
        {market_data}
        
        Based on Elliott Wave Principle, should I exit my current position now?
        What is your confidence level (0-1) in this recommendation?
        """)
        
        # Logging setup
        self.log_queries = self.config.get("log_queries", False)
        
        logger.info("Initialized LLM-enhanced Elliott Wave signal generator")
    
    def _format_market_data(self, data: pd.DataFrame) -> str:
        """Format market data for LLM query.
        
        Args:
            data: Market data.
            
        Returns:
            Formatted market data string.
        """
        # Use only recent data
        recent_data = data.tail(10).copy()
        
        # Format as a table
        if isinstance(recent_data.index, pd.DatetimeIndex):
            recent_data.index = recent_data.index.strftime('%Y-%m-%d %H:%M')
        
        # Select key columns
        key_columns = ['open', 'high', 'low', 'close', 'volume']
        data_columns = [col for col in key_columns if col in recent_data.columns]
        
        # Add indicators if available
        for indicator in ['rsi', 'macd', 'adx', 'atr']:
            if indicator in recent_data.columns:
                data_columns.append(indicator)
        
        # Format as string
        table = recent_data[data_columns].to_string()
        return table
    
    def _format_wave_context(self, wave_count: ElliottWaveCount) -> str:
        """Format wave context for LLM query.
        
        Args:
            wave_count: Elliott Wave count.
            
        Returns:
            Formatted wave context string.
        """
        if not wave_count or not wave_count.waves:
            return "No wave patterns detected."
        
        # Format the wave count
        context = "Current Elliott Wave Count:\n"
        
        for i, wave in enumerate(wave_count.waves[-3:]):  # Use last 3 waves for context
            context += f"Wave {i+1}: {wave.wave_type.value}"
            
            if wave.degree:
                context += f" ({wave.degree.value})"
            
            context += f" - Confidence: {wave.confidence:.2f}\n"
            
            # Add subwaves
            if wave.subwaves:
                for j, subwave in enumerate(wave.subwaves):
                    context += f"  Subwave {j+1}: {subwave.wave_type.value}"
                    if subwave.degree:
                        context += f" ({subwave.degree.value})"
                    context += "\n"
        
        # Add current position
        last_wave = wave_count.waves[-1]
        if last_wave.position:
            context += f"\nCurrent position: {last_wave.position.value}\n"
        
        return context
    
    def _parse_llm_response(self, response: str) -> Tuple[Optional[SignalType], float]:
        """Parse LLM response to extract signal type and confidence.
        
        Args:
            response: LLM response text.
            
        Returns:
            Tuple of (signal type, confidence).
        """
        signal_type = None
        confidence = 0.0
        
        try:
            # Look for direction keywords
            response_lower = response.lower()
            
            # Entry signals
            if any(word in response_lower for word in ["buy", "long", "bullish"]):
                signal_type = SignalType.ENTRY_LONG
            elif any(word in response_lower for word in ["sell", "short", "bearish"]):
                signal_type = SignalType.ENTRY_SHORT
            
            # Exit signals
            elif "exit long" in response_lower or "close long" in response_lower:
                signal_type = SignalType.EXIT_LONG
            elif "exit short" in response_lower or "close short" in response_lower:
                signal_type = SignalType.EXIT_SHORT
            
            # Look for confidence value
            import re
            
            # Try to find a direct confidence score
            confidence_pattern = r"confidence[:\s]+(\d+\.\d+)"
            match = re.search(confidence_pattern, response_lower)
            if match:
                confidence = float(match.group(1))
            else:
                # Try to find a percentage
                percentage_pattern = r"(\d+)%"
                match = re.search(percentage_pattern, response_lower)
                if match:
                    confidence = float(match.group(1)) / 100.0
            
            # If no explicit confidence found but we have a signal type
            if signal_type and confidence == 0.0:
                # Use a default moderate confidence
                confidence = 0.65
            
            # Ensure confidence is in range [0, 1]
            confidence = max(0, min(1, confidence))
            
            return signal_type, confidence
            
        except Exception as e:
            logger.exception("Error parsing LLM response: %s", e)
            return None, 0.0
    
    def generate_signals(
        self,
        data: pd.DataFrame,
        **kwargs: Any,
    ) -> List[Signal]:
        """Generate trading signals using LLM-enhanced Elliott Wave analysis.
        
        Args:
            data: Market data.
            **kwargs: Additional arguments.
            
        Returns:
            List of generated signals.
        """
        signals = []
        
        # Extract metadata
        symbol = kwargs.get("symbol", data.get("symbol", ["unknown"])[0] 
                             if "symbol" in data.columns else "unknown")
        timeframe = kwargs.get("timeframe", data.get("timeframe", ["unknown"])[0] 
                               if "timeframe" in data.columns else "unknown")
        
        # Get the latest timestamp
        latest_timestamp = data.index[-1] if isinstance(data.index, pd.DatetimeIndex) else pd.Timestamp.now()
        
        try:
            # Check if we have the required components
            if not self.wave_analyzer or not self.rag:
                logger.error("Missing wave analyzer or RAG system")
                return signals
            
            # Analyze wave patterns
            wave_count = self.wave_analyzer.analyze(data)
            
            if not wave_count or not wave_count.waves:
                logger.debug("No wave patterns detected")
                return signals
            
            # Format data for LLM
            market_data = self._format_market_data(data)
            wave_context = self._format_wave_context(wave_count)
            
            # Check for entry signals
            entry_query = self.entry_template.format(
                symbol=symbol,
                timeframe=timeframe,
                wave_context=wave_context,
                market_data=market_data
            )
            
            if self.log_queries:
                logger.debug("Entry query: %s", entry_query)
            
            # Get response from RAG
            entry_response = self.rag.query(entry_query)
            
            # Parse response
            entry_signal_type, entry_confidence = self._parse_llm_response(entry_response)
            
            # Create entry signal if confidence is high enough
            if entry_signal_type and entry_confidence >= self.threshold:
                entry_signal = Signal(
                    signal_type=entry_signal_type,
                    strength=entry_confidence,
                    source=SignalSource.WAVE,
                    timestamp=latest_timestamp,
                    symbol=symbol,
                    timeframe=timeframe,
                    metadata={
                        "llm_response": entry_response,
                        "wave_context": wave_context,
                    },
                )
                signals.append(entry_signal)
            
            # Check for exit signals
            exit_query = self.exit_template.format(
                symbol=symbol,
                timeframe=timeframe,
                wave_context=wave_context,
                market_data=market_data
            )
            
            if self.log_queries:
                logger.debug("Exit query: %s", exit_query)
            
            # Get response from RAG
            exit_response = self.rag.query(exit_query)
            
            # Parse response
            exit_signal_type, exit_confidence = self._parse_llm_response(exit_response)
            
            # Create exit signal if confidence is high enough
            if exit_signal_type and exit_confidence >= self.threshold:
                exit_signal = Signal(
                    signal_type=exit_signal_type,
                    strength=exit_confidence,
                    source=SignalSource.WAVE,
                    timestamp=latest_timestamp,
                    symbol=symbol,
                    timeframe=timeframe,
                    metadata={
                        "llm_response": exit_response,
                        "wave_context": wave_context,
                    },
                )
                signals.append(exit_signal)
            
        except Exception as e:
            logger.exception("Error generating LLM-enhanced wave signals: %s", e)
        
        return signals