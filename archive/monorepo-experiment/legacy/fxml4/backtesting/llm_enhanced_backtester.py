"""Enhanced backtesting framework with multi-timeframe LLM validation."""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
import logging
import asyncio
from dataclasses import dataclass
from collections import defaultdict
import json

from fxml4.backtesting.backtest_engine import BacktestEngine
from fxml4.llm_integration.multimodal_mtf_validator import MultiTimeframeChartValidator
from fxml4.data.polygon_official_fetcher import PolygonDataManager
from fxml4.utils.timeframe_aggregator import TimeframeAggregator

logger = logging.getLogger(__name__)


@dataclass
class LLMValidatedSignal:
    """Enhanced signal with LLM validation results."""
    timestamp: datetime
    symbol: str
    direction: str
    ml_confidence: float
    entry_price: float
    stop_loss: float
    take_profit: float
    timeframe: str
    llm_valid: bool
    llm_confidence: float
    timeframe_alignment: float
    pattern_clarity: float
    visual_patterns: List[str]
    concerns: List[str]
    overall_assessment: str
    chart_image: Optional[str] = None  # Base64 encoded chart


class LLMEnhancedBacktester(BacktestEngine):
    """Backtester with multi-timeframe LLM validation using Polygon.io data."""
    
    def __init__(self,
                 initial_capital: float = 100000,
                 commission: float = 0.0002,
                 slippage_model: Optional[Any] = None,
                 polygon_api_key: Optional[str] = None,
                 timeframes_to_validate: List[str] = None,
                 llm_validation_threshold: float = 0.7):
        """Initialize the enhanced backtester.
        
        Args:
            initial_capital: Starting capital
            commission: Commission per trade
            slippage_model: Slippage model
            polygon_api_key: Polygon.io API key
            timeframes_to_validate: Timeframes for LLM validation
            llm_validation_threshold: Minimum LLM confidence to accept signal
        """
        # Initialize base backtester with config
        config = {
            'initial_capital': initial_capital,
            'commission': commission,
            'slippage': 0.0001 if slippage_model is None else 0.0
        }
        super().__init__(config)
        
        # Store additional parameters
        self.slippage_model = slippage_model
        
        # LLM validation components
        self.polygon_manager = PolygonDataManager(polygon_api_key)
        self.timeframes_to_validate = timeframes_to_validate or ['15m', '1H', '4H', 'D']
        self.llm_validation_threshold = llm_validation_threshold
        
        # Initialize validators
        self.mtf_validator = MultiTimeframeChartValidator(config={
            'timeframes': self.timeframes_to_validate,
            'candles_per_timeframe': {
                '15m': 100,
                '1H': 100,
                '4H': 60,
                'D': 30
            }
        })
        self.aggregator = TimeframeAggregator()
        
        # Storage for validated signals
        self.validated_signals: List[LLMValidatedSignal] = []
        self.validation_stats = defaultdict(int)
        
    async def run_backtest_with_llm(self,
                                  symbol: str,
                                  primary_data: pd.DataFrame,
                                  signal_generator: Any,
                                  start_date: datetime,
                                  end_date: datetime,
                                  polygon_symbol: str = None) -> Dict[str, Any]:
        """Run backtest with LLM validation on historical data.
        
        Args:
            symbol: Trading symbol
            primary_data: Primary timeframe data
            signal_generator: ML signal generator
            start_date: Backtest start date
            end_date: Backtest end date
            polygon_symbol: Symbol format for Polygon (e.g., 'C:GBPUSD')
            
        Returns:
            Backtest results with LLM validation metrics
        """
        # Use polygon symbol format if provided
        if polygon_symbol is None:
            polygon_symbol = f"C:{symbol}" if len(symbol) == 6 else symbol
            
        logger.info(f"Starting LLM-enhanced backtest for {symbol}")
        logger.info(f"Period: {start_date} to {end_date}")
        logger.info(f"Timeframes for validation: {self.timeframes_to_validate}")
        
        # Pre-fetch all historical data for efficiency
        logger.info("Pre-fetching historical data from Polygon.io...")
        all_historical_data = self.polygon_manager.get_backtest_data(
            polygon_symbol,
            self.timeframes_to_validate,
            start_date - timedelta(days=30),  # Extra buffer for indicators
            end_date
        )
        
        if not all_historical_data:
            logger.error("Failed to fetch historical data from Polygon")
            return {}
            
        # Calculate indicators for all timeframes
        logger.info("Calculating indicators for all timeframes...")
        indicators_by_timeframe = {}
        for tf, data in all_historical_data.items():
            indicators_by_timeframe[tf] = self._calculate_all_indicators(data)
            
        # Process signals day by day
        total_signals = 0
        accepted_signals = 0
        rejected_signals = 0
        
        # Generate signals on primary data
        for i in range(100, len(primary_data)):  # Start after warmup
            current_time = primary_data.index[i]
            
            # Skip if outside backtest period
            if current_time < start_date or current_time > end_date:
                continue
                
            # Generate ML signal
            signal = signal_generator.generate_signal(
                primary_data.iloc[:i+1],
                symbol
            )
            
            if signal and signal['confidence'] > 0.5:
                total_signals += 1
                
                # Validate with LLM
                logger.info(f"\nValidating signal at {current_time}...")
                
                try:
                    validated_signal = await self._validate_signal_with_llm(
                        signal,
                        current_time,
                        all_historical_data,
                        indicators_by_timeframe,
                        symbol
                    )
                    
                    self.validated_signals.append(validated_signal)
                    
                    if validated_signal.llm_valid and validated_signal.llm_confidence >= self.llm_validation_threshold:
                        accepted_signals += 1
                        
                        # Execute trade in backtest
                        self._execute_signal(validated_signal, current_time)
                        
                        logger.info(f"✅ Signal ACCEPTED - LLM confidence: {validated_signal.llm_confidence:.1%}")
                    else:
                        rejected_signals += 1
                        logger.info(f"❌ Signal REJECTED - LLM confidence: {validated_signal.llm_confidence:.1%}")
                        
                except Exception as e:
                    logger.error(f"Error validating signal: {e}")
                    rejected_signals += 1
                    
            # Update portfolio with current prices
            current_prices = {symbol: primary_data['close'].iloc[i]}
            self.update_portfolio(current_time, current_prices)
            
        # Calculate final statistics
        results = self.calculate_statistics()
        
        # Add LLM validation statistics
        results['llm_validation'] = {
            'total_signals': total_signals,
            'accepted_signals': accepted_signals,
            'rejected_signals': rejected_signals,
            'acceptance_rate': accepted_signals / total_signals if total_signals > 0 else 0,
            'avg_llm_confidence': np.mean([s.llm_confidence for s in self.validated_signals]) if self.validated_signals else 0,
            'avg_timeframe_alignment': np.mean([s.timeframe_alignment for s in self.validated_signals]) if self.validated_signals else 0,
            'avg_pattern_clarity': np.mean([s.pattern_clarity for s in self.validated_signals]) if self.validated_signals else 0,
        }
        
        # Analyze performance by LLM confidence
        results['performance_by_confidence'] = self._analyze_performance_by_confidence()
        
        logger.info("\nBacktest complete!")
        logger.info(f"Total signals: {total_signals}")
        logger.info(f"Accepted: {accepted_signals} ({accepted_signals/total_signals*100:.1f}%)")
        logger.info(f"Rejected: {rejected_signals} ({rejected_signals/total_signals*100:.1f}%)")
        
        return results
        
    async def _validate_signal_with_llm(self,
                                      signal: Dict[str, Any],
                                      signal_time: datetime,
                                      historical_data: Dict[str, pd.DataFrame],
                                      indicators_by_timeframe: Dict[str, Dict[str, Any]],
                                      symbol: str) -> LLMValidatedSignal:
        """Validate a signal using multi-timeframe LLM analysis.
        
        Args:
            signal: ML-generated signal
            signal_time: Time of the signal
            historical_data: Pre-fetched historical data
            indicators_by_timeframe: Pre-calculated indicators
            symbol: Trading symbol
            
        Returns:
            LLM validated signal
        """
        # Align data to signal time
        aligned_data = {}
        aligned_indicators = {}
        
        for tf in self.timeframes_to_validate:
            if tf in historical_data:
                # Get data up to signal time
                tf_data = historical_data[tf]
                tf_data = tf_data[tf_data.index <= signal_time]
                
                # Limit to reasonable lookback
                lookback_bars = {
                    '15m': 100,
                    '1H': 100,
                    '4H': 60,
                    'D': 30
                }
                
                if len(tf_data) > lookback_bars.get(tf, 100):
                    tf_data = tf_data.tail(lookback_bars[tf])
                    
                aligned_data[tf] = tf_data
                
                # Align indicators
                if tf in indicators_by_timeframe:
                    aligned_indicators[tf] = self._align_indicators(
                        indicators_by_timeframe[tf],
                        signal_time,
                        tf_data.index
                    )
                    
        # Prepare signal for validation
        validation_signal = {
            'symbol': symbol,
            'direction': signal['direction'],
            'confidence': signal['confidence'],
            'entry_price': signal['entry_price'],
            'stop_loss': signal.get('stop_loss', signal['entry_price'] - 0.0050),
            'take_profit': signal.get('take_profit', signal['entry_price'] + 0.0100),
            'timeframe': signal.get('timeframe', '4H'),
            'timestamp': signal_time,
            'reason': signal.get('reason', 'ML model prediction')
        }
        
        # Validate with LLM
        validation_result = await self.mtf_validator.validate_trading_signal_mtf(
            validation_signal,
            aligned_data,
            aligned_indicators
        )
        
        # Create validated signal
        return LLMValidatedSignal(
            timestamp=signal_time,
            symbol=symbol,
            direction=signal['direction'],
            ml_confidence=signal['confidence'],
            entry_price=signal['entry_price'],
            stop_loss=validation_signal['stop_loss'],
            take_profit=validation_signal['take_profit'],
            timeframe=validation_signal['timeframe'],
            llm_valid=validation_result.get('valid', False),
            llm_confidence=validation_result.get('llm_confidence', 0),
            timeframe_alignment=validation_result.get('timeframe_alignment', 0),
            pattern_clarity=validation_result.get('pattern_clarity', 0),
            visual_patterns=validation_result.get('visual_patterns', []),
            concerns=validation_result.get('concerns', []),
            overall_assessment=validation_result.get('overall_assessment', ''),
            chart_image=validation_result.get('chart_image')
        )
        
    def _calculate_all_indicators(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Calculate all indicators for a timeframe."""
        indicators = {}
        
        # Moving averages
        indicators['sma_20'] = data['close'].rolling(20).mean()
        indicators['sma_50'] = data['close'].rolling(50).mean()
        indicators['ema_9'] = data['close'].ewm(span=9).mean()
        
        # RSI
        delta = data['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        indicators['rsi'] = 100 - (100 / (1 + rs))
        
        # Bollinger Bands
        bb_sma = data['close'].rolling(20).mean()
        bb_std = data['close'].rolling(20).std()
        indicators['bb_upper'] = bb_sma + (bb_std * 2)
        indicators['bb_middle'] = bb_sma
        indicators['bb_lower'] = bb_sma - (bb_std * 2)
        
        # Support/Resistance
        indicators['support_levels'] = self._find_levels(data, 'support')
        indicators['resistance_levels'] = self._find_levels(data, 'resistance')
        
        return indicators
        
    def _find_levels(self, data: pd.DataFrame, level_type: str) -> List[float]:
        """Find support/resistance levels."""
        levels = []
        
        if level_type == 'support':
            # Find local minima
            for i in range(10, len(data) - 10):
                if data['low'].iloc[i] == data['low'].iloc[i-10:i+10].min():
                    levels.append(data['low'].iloc[i])
        else:
            # Find local maxima
            for i in range(10, len(data) - 10):
                if data['high'].iloc[i] == data['high'].iloc[i-10:i+10].max():
                    levels.append(data['high'].iloc[i])
                    
        # Remove duplicates and sort
        levels = sorted(list(set(levels)))
        
        # Return most recent levels
        return levels[-5:] if level_type == 'support' else levels[:5]
        
    def _align_indicators(self, indicators: Dict[str, Any], signal_time: datetime, valid_index: pd.Index) -> Dict[str, Any]:
        """Align indicators to signal time."""
        aligned = {}
        
        for name, data in indicators.items():
            if isinstance(data, pd.Series):
                # Align series data
                aligned[name] = data[data.index.isin(valid_index)]
            else:
                # Keep non-series data as is
                aligned[name] = data
                
        return aligned
        
    def _execute_signal(self, signal: LLMValidatedSignal, current_time: datetime):
        """Execute a validated signal in the backtest."""
        # Create order based on signal
        order = {
            'symbol': signal.symbol,
            'direction': signal.direction,
            'quantity': self._calculate_position_size(signal),
            'order_type': 'MARKET',
            'stop_loss': signal.stop_loss,
            'take_profit': signal.take_profit,
            'timestamp': current_time
        }
        
        # Process order through base backtester
        self.process_order(order, current_time, signal.entry_price)
        
    def _calculate_position_size(self, signal: LLMValidatedSignal) -> float:
        """Calculate position size based on LLM confidence."""
        # Base position size
        base_size = self.capital * 0.02  # 2% risk per trade
        
        # Adjust based on LLM confidence
        confidence_multiplier = signal.llm_confidence
        
        # Further adjust based on timeframe alignment
        if signal.timeframe_alignment > 0.8:
            confidence_multiplier *= 1.2
        elif signal.timeframe_alignment < 0.5:
            confidence_multiplier *= 0.8
            
        # Calculate final position size
        position_value = base_size * confidence_multiplier
        position_size = position_value / signal.entry_price
        
        return position_size
        
    def _analyze_performance_by_confidence(self) -> Dict[str, Any]:
        """Analyze performance grouped by LLM confidence levels."""
        if not self.validated_signals:
            return {}
            
        # Group signals by confidence buckets
        buckets = {
            'high': [],
            'medium': [],
            'low': []
        }
        
        for signal in self.validated_signals:
            if signal.llm_confidence >= 0.8:
                buckets['high'].append(signal)
            elif signal.llm_confidence >= 0.6:
                buckets['medium'].append(signal)
            else:
                buckets['low'].append(signal)
                
        # Calculate performance for each bucket
        results = {}
        for bucket_name, signals in buckets.items():
            if signals:
                # Get trades for these signals
                bucket_trades = [t for t in self.trades if any(
                    t.entry_time == s.timestamp for s in signals
                )]
                
                if bucket_trades:
                    wins = len([t for t in bucket_trades if t.pnl > 0])
                    total = len(bucket_trades)
                    avg_pnl = np.mean([t.pnl for t in bucket_trades])
                    
                    results[bucket_name] = {
                        'count': len(signals),
                        'win_rate': wins / total if total > 0 else 0,
                        'avg_pnl': avg_pnl,
                        'total_pnl': sum(t.pnl for t in bucket_trades)
                    }
                    
        return results
        
    def save_validation_report(self, filepath: str):
        """Save detailed validation report."""
        report = {
            'summary': {
                'total_signals': len(self.validated_signals),
                'accepted': len([s for s in self.validated_signals if s.llm_valid]),
                'rejected': len([s for s in self.validated_signals if not s.llm_valid]),
                'avg_llm_confidence': np.mean([s.llm_confidence for s in self.validated_signals]) if self.validated_signals else 0
            },
            'signals': []
        }
        
        for signal in self.validated_signals:
            report['signals'].append({
                'timestamp': signal.timestamp.isoformat(),
                'symbol': signal.symbol,
                'direction': signal.direction,
                'ml_confidence': signal.ml_confidence,
                'llm_valid': signal.llm_valid,
                'llm_confidence': signal.llm_confidence,
                'timeframe_alignment': signal.timeframe_alignment,
                'pattern_clarity': signal.pattern_clarity,
                'visual_patterns': signal.visual_patterns,
                'concerns': signal.concerns,
                'overall_assessment': signal.overall_assessment
            })
            
        with open(filepath, 'w') as f:
            json.dump(report, f, indent=2)
            
        logger.info(f"Validation report saved to: {filepath}")