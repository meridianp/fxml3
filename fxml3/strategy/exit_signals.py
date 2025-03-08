"""
Exit signal generation module for Elliott Wave trading strategies.

This module implements various exit signal generators based on 
Elliott Wave patterns, including profit targets, pattern completion,
and trailing stop strategies.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional, Union, Any, Callable
from dataclasses import dataclass
from enum import Enum

from fxml3.wave_analysis.elliott_wave import ElliottWaveAnalyzer
from fxml3.strategy.entry_signals import SignalType, SignalStrength


@dataclass
class ExitSignal:
    """Represents a trading exit signal."""
    timestamp: pd.Timestamp
    position_type: SignalType  # LONG or SHORT - the position being exited
    exit_type: str  # 'take_profit', 'stop_loss', 'pattern_completion', 'trailing_stop', 'time_based'
    strength: SignalStrength
    pattern: str  # Related Elliott Wave pattern
    exit_price: float
    profit_loss: float  # Estimated P&L if taken
    confidence: float  # 0.0 to 1.0
    timeframe: str
    partial_exit: bool = False  # Whether this is a partial position exit
    partial_percentage: float = 1.0  # Percentage of position to exit (1.0 = full exit)
    additional_info: Dict[str, Any] = None


class ExitSignalGenerator:
    """
    Generates exit signals based on Elliott Wave patterns.
    
    This class analyzes wave patterns to generate trade exit signals
    with detailed information about exit prices and timing.
    """
    
    def __init__(
        self,
        wave_analyzer: Optional[ElliottWaveAnalyzer] = None,
        use_partial_exits: bool = True,
        partial_exit_levels: List[float] = None,
        trailing_stop_factor: float = 0.382,
        confidence_threshold: float = 0.6,
        max_holding_periods: Dict[str, int] = None
    ):
        """
        Initialize the exit signal generator.
        
        Args:
            wave_analyzer: Elliott Wave analyzer for pattern detection
            use_partial_exits: Whether to use partial position exits
            partial_exit_levels: Fibonacci levels for partial exits
            trailing_stop_factor: Factor for trailing stop calculation
            confidence_threshold: Minimum confidence level for signals
            max_holding_periods: Maximum holding period by timeframe
        """
        self.wave_analyzer = wave_analyzer or ElliottWaveAnalyzer()
        self.use_partial_exits = use_partial_exits
        self.partial_exit_levels = partial_exit_levels or [0.382, 0.618, 0.786, 1.0]
        self.trailing_stop_factor = trailing_stop_factor
        self.confidence_threshold = confidence_threshold
        self.max_holding_periods = max_holding_periods or {
            "1m": 60,    # 1 hour
            "5m": 36,    # 3 hours
            "15m": 32,   # 8 hours
            "1H": 24,    # 1 day
            "4H": 15,    # 2.5 days
            "1D": 10     # 2 weeks
        }
        
        # Store active positions for trailing stops
        self.active_positions = {}
        
    def analyze(
        self,
        data: pd.DataFrame,
        active_positions: List[Dict[str, Any]],
        timeframe: str = "1H"
    ) -> Dict[pd.Timestamp, List[ExitSignal]]:
        """
        Analyze price data to generate exit signals for active positions.
        
        Args:
            data: DataFrame with OHLCV data and optional wave annotations
            active_positions: List of active position dictionaries
            timeframe: Timeframe of the data
            
        Returns:
            Dictionary mapping timestamps to lists of exit signals
        """
        # First, ensure wave analysis is done
        wave_data = self._ensure_wave_analysis(data)
        
        # Initialize signals container
        signals = {}
        
        # Update active positions list
        self._update_active_positions(active_positions)
        
        # Process each active position
        for position_id, position in self.active_positions.items():
            # Generate take profit signals
            tp_signals = self._generate_take_profit_signals(wave_data, position, timeframe)
            
            # Generate stop loss signals
            sl_signals = self._generate_stop_loss_signals(wave_data, position, timeframe)
            
            # Generate pattern completion exit signals
            pc_signals = self._generate_pattern_completion_signals(wave_data, position, timeframe)
            
            # Generate trailing stop signals
            ts_signals = self._generate_trailing_stop_signals(wave_data, position, timeframe)
            
            # Generate time-based exit signals
            tb_signals = self._generate_time_based_signals(wave_data, position, timeframe)
            
            # Merge all signals
            all_position_signals = {}
            for signal_dict in [tp_signals, sl_signals, pc_signals, ts_signals, tb_signals]:
                for timestamp, signal_list in signal_dict.items():
                    if timestamp not in all_position_signals:
                        all_position_signals[timestamp] = []
                    all_position_signals[timestamp].extend(signal_list)
            
            # Add to overall signals
            for timestamp, signal_list in all_position_signals.items():
                if timestamp not in signals:
                    signals[timestamp] = []
                signals[timestamp].extend(signal_list)
        
        return signals
    
    def _ensure_wave_analysis(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Ensure that wave analysis has been performed on the data.
        
        Args:
            data: OHLCV price data
            
        Returns:
            DataFrame with wave analysis annotations
        """
        # Check if data already has wave annotations
        wave_columns = [col for col in data.columns if 'wave_' in col or '_wave' in col]
        
        if not wave_columns:
            # Run wave analysis
            wave_data = self.wave_analyzer.analyze(data)
            
            # Merge wave data with price data
            if isinstance(wave_data, pd.DataFrame) and not wave_data.empty:
                return pd.merge(
                    data, wave_data, how='left', left_index=True, right_index=True
                )
            return data
        
        return data
    
    def _update_active_positions(self, positions: List[Dict[str, Any]]):
        """
        Update the internal active positions list.
        
        Args:
            positions: List of active position dictionaries
        """
        # Create a dictionary with position_id as key
        for position in positions:
            position_id = position.get('id')
            if position_id:
                # Add or update position
                self.active_positions[position_id] = position
        
        # Remove closed positions
        active_ids = {p.get('id') for p in positions if p.get('id')}
        for position_id in list(self.active_positions.keys()):
            if position_id not in active_ids:
                del self.active_positions[position_id]
    
    def _generate_take_profit_signals(
        self,
        data: pd.DataFrame,
        position: Dict[str, Any],
        timeframe: str
    ) -> Dict[pd.Timestamp, List[ExitSignal]]:
        """
        Generate take profit exit signals based on price targets.
        
        Args:
            data: DataFrame with wave analysis annotations
            position: Active position dictionary
            timeframe: Timeframe of the data
            
        Returns:
            Dictionary mapping timestamps to take profit signals
        """
        signals = {}
        
        # Extract position details
        position_id = position.get('id')
        entry_price = position.get('entry_price')
        take_profit = position.get('take_profit')
        position_type = position.get('type')  # 'long' or 'short'
        entry_time = position.get('entry_time')
        size = position.get('size', 1.0)
        pattern = position.get('pattern', '')
        
        # Convert position_type to SignalType
        signal_type = SignalType.LONG if position_type == 'long' else SignalType.SHORT
        
        # Check if take_profit is defined
        if not take_profit or not entry_price:
            return signals
        
        # Check if we have partial exit levels
        partial_levels = []
        if self.use_partial_exits and take_profit and entry_price:
            # Calculate partial exit prices based on Fibonacci projections
            target_distance = abs(take_profit - entry_price)
            
            for level in self.partial_exit_levels:
                if position_type == 'long':
                    partial_price = entry_price + (target_distance * level)
                else:
                    partial_price = entry_price - (target_distance * level)
                    
                partial_levels.append({
                    'level': level,
                    'price': partial_price,
                    'percentage': 0.25 if level < 1.0 else 1.0  # Exit 25% at partial levels, full at 100%
                })
        
        # Check each candle for take profit hits
        for i in range(len(data)):
            row = data.iloc[i]
            timestamp = row.name if isinstance(row.name, pd.Timestamp) else pd.Timestamp(row['timestamp'])
            
            # Skip rows before entry time
            if entry_time and timestamp <= entry_time:
                continue
            
            # Check for take profit hit on main target
            if position_type == 'long' and row['high'] >= take_profit:
                # Calculate profit
                profit = (take_profit - entry_price) * size
                
                # Create signal
                exit_signal = ExitSignal(
                    timestamp=timestamp,
                    position_type=signal_type,
                    exit_type='take_profit',
                    strength=SignalStrength.STRONG,
                    pattern=pattern,
                    exit_price=take_profit,
                    profit_loss=profit,
                    confidence=0.9,
                    timeframe=timeframe,
                    partial_exit=False,
                    partial_percentage=1.0,
                    additional_info={
                        'position_id': position_id,
                        'target_type': 'main'
                    }
                )
                
                if timestamp not in signals:
                    signals[timestamp] = []
                signals[timestamp].append(exit_signal)
                
                # Once we hit the main target, no need to check further
                break
                
            elif position_type == 'short' and row['low'] <= take_profit:
                # Calculate profit
                profit = (entry_price - take_profit) * size
                
                # Create signal
                exit_signal = ExitSignal(
                    timestamp=timestamp,
                    position_type=signal_type,
                    exit_type='take_profit',
                    strength=SignalStrength.STRONG,
                    pattern=pattern,
                    exit_price=take_profit,
                    profit_loss=profit,
                    confidence=0.9,
                    timeframe=timeframe,
                    partial_exit=False,
                    partial_percentage=1.0,
                    additional_info={
                        'position_id': position_id,
                        'target_type': 'main'
                    }
                )
                
                if timestamp not in signals:
                    signals[timestamp] = []
                signals[timestamp].append(exit_signal)
                
                # Once we hit the main target, no need to check further
                break
            
            # Check for partial exit levels
            for level_data in partial_levels:
                level_price = level_data['price']
                level_pct = level_data['percentage']
                level_value = level_data['level']
                
                if position_type == 'long' and row['high'] >= level_price:
                    # Calculate profit for this partial exit
                    profit = (level_price - entry_price) * size * level_pct
                    
                    # Create partial exit signal
                    exit_signal = ExitSignal(
                        timestamp=timestamp,
                        position_type=signal_type,
                        exit_type='take_profit',
                        strength=SignalStrength.MODERATE,
                        pattern=pattern,
                        exit_price=level_price,
                        profit_loss=profit,
                        confidence=0.75,
                        timeframe=timeframe,
                        partial_exit=True,
                        partial_percentage=level_pct,
                        additional_info={
                            'position_id': position_id,
                            'target_type': f'partial_{level_value}',
                            'fibonacci_level': level_value
                        }
                    )
                    
                    if timestamp not in signals:
                        signals[timestamp] = []
                    signals[timestamp].append(exit_signal)
                    
                    # Remove this level from consideration
                    partial_levels.remove(level_data)
                    
                elif position_type == 'short' and row['low'] <= level_price:
                    # Calculate profit for this partial exit
                    profit = (entry_price - level_price) * size * level_pct
                    
                    # Create partial exit signal
                    exit_signal = ExitSignal(
                        timestamp=timestamp,
                        position_type=signal_type,
                        exit_type='take_profit',
                        strength=SignalStrength.MODERATE,
                        pattern=pattern,
                        exit_price=level_price,
                        profit_loss=profit,
                        confidence=0.75,
                        timeframe=timeframe,
                        partial_exit=True,
                        partial_percentage=level_pct,
                        additional_info={
                            'position_id': position_id,
                            'target_type': f'partial_{level_value}',
                            'fibonacci_level': level_value
                        }
                    )
                    
                    if timestamp not in signals:
                        signals[timestamp] = []
                    signals[timestamp].append(exit_signal)
                    
                    # Remove this level from consideration
                    partial_levels.remove(level_data)
        
        return signals
    
    def _generate_stop_loss_signals(
        self,
        data: pd.DataFrame,
        position: Dict[str, Any],
        timeframe: str
    ) -> Dict[pd.Timestamp, List[ExitSignal]]:
        """
        Generate stop loss exit signals.
        
        Args:
            data: DataFrame with wave analysis annotations
            position: Active position dictionary
            timeframe: Timeframe of the data
            
        Returns:
            Dictionary mapping timestamps to stop loss signals
        """
        signals = {}
        
        # Extract position details
        position_id = position.get('id')
        entry_price = position.get('entry_price')
        stop_loss = position.get('stop_loss')
        position_type = position.get('type')  # 'long' or 'short'
        entry_time = position.get('entry_time')
        size = position.get('size', 1.0)
        pattern = position.get('pattern', '')
        
        # Convert position_type to SignalType
        signal_type = SignalType.LONG if position_type == 'long' else SignalType.SHORT
        
        # Check if stop_loss is defined
        if not stop_loss or not entry_price:
            return signals
        
        # Check each candle for stop loss hits
        for i in range(len(data)):
            row = data.iloc[i]
            timestamp = row.name if isinstance(row.name, pd.Timestamp) else pd.Timestamp(row['timestamp'])
            
            # Skip rows before entry time
            if entry_time and timestamp <= entry_time:
                continue
            
            # Check for stop loss hit
            if position_type == 'long' and row['low'] <= stop_loss:
                # Calculate loss
                loss = (stop_loss - entry_price) * size
                
                # Create signal
                exit_signal = ExitSignal(
                    timestamp=timestamp,
                    position_type=signal_type,
                    exit_type='stop_loss',
                    strength=SignalStrength.STRONG,
                    pattern=pattern,
                    exit_price=stop_loss,
                    profit_loss=loss,
                    confidence=0.95,  # High confidence for stop loss
                    timeframe=timeframe,
                    partial_exit=False,
                    partial_percentage=1.0,
                    additional_info={
                        'position_id': position_id
                    }
                )
                
                if timestamp not in signals:
                    signals[timestamp] = []
                signals[timestamp].append(exit_signal)
                
                # Once stop loss is hit, no need to check further
                break
                
            elif position_type == 'short' and row['high'] >= stop_loss:
                # Calculate loss
                loss = (entry_price - stop_loss) * size
                
                # Create signal
                exit_signal = ExitSignal(
                    timestamp=timestamp,
                    position_type=signal_type,
                    exit_type='stop_loss',
                    strength=SignalStrength.STRONG,
                    pattern=pattern,
                    exit_price=stop_loss,
                    profit_loss=loss,
                    confidence=0.95,  # High confidence for stop loss
                    timeframe=timeframe,
                    partial_exit=False,
                    partial_percentage=1.0,
                    additional_info={
                        'position_id': position_id
                    }
                )
                
                if timestamp not in signals:
                    signals[timestamp] = []
                signals[timestamp].append(exit_signal)
                
                # Once stop loss is hit, no need to check further
                break
        
        return signals
    
    def _generate_pattern_completion_signals(
        self,
        data: pd.DataFrame,
        position: Dict[str, Any],
        timeframe: str
    ) -> Dict[pd.Timestamp, List[ExitSignal]]:
        """
        Generate exit signals based on Elliott Wave pattern completion.
        
        Args:
            data: DataFrame with wave analysis annotations
            position: Active position dictionary
            timeframe: Timeframe of the data
            
        Returns:
            Dictionary mapping timestamps to pattern completion signals
        """
        signals = {}
        
        # Extract position details
        position_id = position.get('id')
        entry_price = position.get('entry_price')
        position_type = position.get('type')  # 'long' or 'short'
        entry_time = position.get('entry_time')
        size = position.get('size', 1.0)
        pattern = position.get('pattern', '')
        entry_pattern = position.get('entry_pattern', '')
        
        # Convert position_type to SignalType
        signal_type = SignalType.LONG if position_type == 'long' else SignalType.SHORT
        
        # Check each candle for pattern completion signals
        for i in range(len(data)):
            row = data.iloc[i]
            timestamp = row.name if isinstance(row.name, pd.Timestamp) else pd.Timestamp(row['timestamp'])
            
            # Skip rows before entry time
            if entry_time and timestamp <= entry_time:
                continue
            
            # Check for pattern completion based on entry pattern
            exit_pattern = self._get_completion_pattern(entry_pattern)
            if exit_pattern and self._check_pattern_exists(row, exit_pattern):
                # Calculate profit/loss
                current_price = row['close']
                if position_type == 'long':
                    profit_loss = (current_price - entry_price) * size
                else:
                    profit_loss = (entry_price - current_price) * size
                
                # Create signal
                exit_signal = ExitSignal(
                    timestamp=timestamp,
                    position_type=signal_type,
                    exit_type='pattern_completion',
                    strength=SignalStrength.MODERATE,
                    pattern=exit_pattern,
                    exit_price=current_price,
                    profit_loss=profit_loss,
                    confidence=0.8,
                    timeframe=timeframe,
                    partial_exit=False,
                    partial_percentage=1.0,
                    additional_info={
                        'position_id': position_id,
                        'entry_pattern': entry_pattern
                    }
                )
                
                if timestamp not in signals:
                    signals[timestamp] = []
                signals[timestamp].append(exit_signal)
                
                # Once pattern completion is detected, no need to check further
                break
            
            # Check for opposite pattern signals indicating reversal
            if position_type == 'long' and self._check_bearish_pattern(row):
                # Calculate profit/loss
                current_price = row['close']
                profit_loss = (current_price - entry_price) * size
                
                # Create signal
                exit_signal = ExitSignal(
                    timestamp=timestamp,
                    position_type=signal_type,
                    exit_type='pattern_completion',
                    strength=SignalStrength.MODERATE,
                    pattern='bearish_reversal',
                    exit_price=current_price,
                    profit_loss=profit_loss,
                    confidence=0.75,
                    timeframe=timeframe,
                    partial_exit=False,
                    partial_percentage=1.0,
                    additional_info={
                        'position_id': position_id,
                        'reversal_type': 'bearish'
                    }
                )
                
                if timestamp not in signals:
                    signals[timestamp] = []
                signals[timestamp].append(exit_signal)
                
            elif position_type == 'short' and self._check_bullish_pattern(row):
                # Calculate profit/loss
                current_price = row['close']
                profit_loss = (entry_price - current_price) * size
                
                # Create signal
                exit_signal = ExitSignal(
                    timestamp=timestamp,
                    position_type=signal_type,
                    exit_type='pattern_completion',
                    strength=SignalStrength.MODERATE,
                    pattern='bullish_reversal',
                    exit_price=current_price,
                    profit_loss=profit_loss,
                    confidence=0.75,
                    timeframe=timeframe,
                    partial_exit=False,
                    partial_percentage=1.0,
                    additional_info={
                        'position_id': position_id,
                        'reversal_type': 'bullish'
                    }
                )
                
                if timestamp not in signals:
                    signals[timestamp] = []
                signals[timestamp].append(exit_signal)
        
        return signals
    
    def _generate_trailing_stop_signals(
        self,
        data: pd.DataFrame,
        position: Dict[str, Any],
        timeframe: str
    ) -> Dict[pd.Timestamp, List[ExitSignal]]:
        """
        Generate trailing stop exit signals.
        
        Args:
            data: DataFrame with wave analysis annotations
            position: Active position dictionary
            timeframe: Timeframe of the data
            
        Returns:
            Dictionary mapping timestamps to trailing stop signals
        """
        signals = {}
        
        # Extract position details
        position_id = position.get('id')
        entry_price = position.get('entry_price')
        position_type = position.get('type')  # 'long' or 'short'
        entry_time = position.get('entry_time')
        size = position.get('size', 1.0)
        pattern = position.get('pattern', '')
        
        # Convert position_type to SignalType
        signal_type = SignalType.LONG if position_type == 'long' else SignalType.SHORT
        
        # Initialize trailing stop
        trailing_stop = None
        highest_since_entry = None
        lowest_since_entry = None
        
        # Check each candle for trailing stop calculation and hits
        for i in range(len(data)):
            row = data.iloc[i]
            timestamp = row.name if isinstance(row.name, pd.Timestamp) else pd.Timestamp(row['timestamp'])
            
            # Skip rows before entry time
            if entry_time and timestamp <= entry_time:
                continue
            
            # Update highest/lowest since entry
            if position_type == 'long':
                if highest_since_entry is None or row['high'] > highest_since_entry:
                    highest_since_entry = row['high']
                    # Update trailing stop
                    trailing_stop = highest_since_entry * (1 - self.trailing_stop_factor)
            else:  # short position
                if lowest_since_entry is None or row['low'] < lowest_since_entry:
                    lowest_since_entry = row['low']
                    # Update trailing stop
                    trailing_stop = lowest_since_entry * (1 + self.trailing_stop_factor)
            
            # Check if trailing stop has been hit
            if trailing_stop is not None:
                if position_type == 'long' and row['low'] <= trailing_stop:
                    # Calculate profit/loss
                    profit_loss = (trailing_stop - entry_price) * size
                    
                    # Create signal
                    exit_signal = ExitSignal(
                        timestamp=timestamp,
                        position_type=signal_type,
                        exit_type='trailing_stop',
                        strength=SignalStrength.STRONG,
                        pattern=pattern,
                        exit_price=trailing_stop,
                        profit_loss=profit_loss,
                        confidence=0.9,
                        timeframe=timeframe,
                        partial_exit=False,
                        partial_percentage=1.0,
                        additional_info={
                            'position_id': position_id,
                            'highest_price': highest_since_entry
                        }
                    )
                    
                    if timestamp not in signals:
                        signals[timestamp] = []
                    signals[timestamp].append(exit_signal)
                    
                    # Once trailing stop is hit, no need to check further
                    break
                    
                elif position_type == 'short' and row['high'] >= trailing_stop:
                    # Calculate profit/loss
                    profit_loss = (entry_price - trailing_stop) * size
                    
                    # Create signal
                    exit_signal = ExitSignal(
                        timestamp=timestamp,
                        position_type=signal_type,
                        exit_type='trailing_stop',
                        strength=SignalStrength.STRONG,
                        pattern=pattern,
                        exit_price=trailing_stop,
                        profit_loss=profit_loss,
                        confidence=0.9,
                        timeframe=timeframe,
                        partial_exit=False,
                        partial_percentage=1.0,
                        additional_info={
                            'position_id': position_id,
                            'lowest_price': lowest_since_entry
                        }
                    )
                    
                    if timestamp not in signals:
                        signals[timestamp] = []
                    signals[timestamp].append(exit_signal)
                    
                    # Once trailing stop is hit, no need to check further
                    break
        
        return signals
    
    def _generate_time_based_signals(
        self,
        data: pd.DataFrame,
        position: Dict[str, Any],
        timeframe: str
    ) -> Dict[pd.Timestamp, List[ExitSignal]]:
        """
        Generate time-based exit signals.
        
        Args:
            data: DataFrame with wave analysis annotations
            position: Active position dictionary
            timeframe: Timeframe of the data
            
        Returns:
            Dictionary mapping timestamps to time-based exit signals
        """
        signals = {}
        
        # Extract position details
        position_id = position.get('id')
        entry_price = position.get('entry_price')
        position_type = position.get('type')  # 'long' or 'short'
        entry_time = position.get('entry_time')
        size = position.get('size', 1.0)
        pattern = position.get('pattern', '')
        
        # Convert position_type to SignalType
        signal_type = SignalType.LONG if position_type == 'long' else SignalType.SHORT
        
        # Check if entry_time is available
        if not entry_time:
            return signals
        
        # Get maximum holding period for this timeframe
        max_periods = self.max_holding_periods.get(timeframe, 20)
        
        # Count periods since entry
        periods_held = 0
        max_time_index = None
        
        for i in range(len(data)):
            row = data.iloc[i]
            timestamp = row.name if isinstance(row.name, pd.Timestamp) else pd.Timestamp(row['timestamp'])
            
            # Skip rows before entry time
            if timestamp <= entry_time:
                continue
            
            # Count this period
            periods_held += 1
            
            # Check if we've reached maximum holding period
            if periods_held >= max_periods:
                max_time_index = i
                break
        
        # If we've found the maximum time index, generate a signal
        if max_time_index is not None:
            row = data.iloc[max_time_index]
            timestamp = row.name if isinstance(row.name, pd.Timestamp) else pd.Timestamp(row['timestamp'])
            current_price = row['close']
            
            # Calculate profit/loss
            if position_type == 'long':
                profit_loss = (current_price - entry_price) * size
            else:
                profit_loss = (entry_price - current_price) * size
            
            # Create signal
            exit_signal = ExitSignal(
                timestamp=timestamp,
                position_type=signal_type,
                exit_type='time_based',
                strength=SignalStrength.MODERATE,
                pattern=pattern,
                exit_price=current_price,
                profit_loss=profit_loss,
                confidence=0.7,
                timeframe=timeframe,
                partial_exit=False,
                partial_percentage=1.0,
                additional_info={
                    'position_id': position_id,
                    'holding_periods': periods_held,
                    'max_periods': max_periods
                }
            )
            
            if timestamp not in signals:
                signals[timestamp] = []
            signals[timestamp].append(exit_signal)
        
        return signals
    
    def _get_completion_pattern(self, entry_pattern: str) -> Optional[str]:
        """
        Get the corresponding completion pattern for an entry pattern.
        
        Args:
            entry_pattern: Entry pattern string
            
        Returns:
            Corresponding completion pattern or None
        """
        # Map entry patterns to exit patterns
        pattern_map = {
            'wave_3_start': 'wave_3_end',
            'wave_5_start': 'wave_5_end',
            'abc_completion': 'impulse_start',
            'correction_end': 'impulse_start',
            'impulse_end': 'correction_start',
            'triangle_breakout': 'post_triangle_completion'
        }
        
        return pattern_map.get(entry_pattern)
    
    def _check_pattern_exists(self, row: pd.Series, pattern: str) -> bool:
        """
        Check if a specific pattern exists in the row annotations.
        
        Args:
            row: DataFrame row with wave annotations
            pattern: Pattern to check for
            
        Returns:
            True if pattern exists, False otherwise
        """
        # Convert pattern to possible column names
        pattern_variations = [
            pattern,
            f"{pattern}_signal",
            f"wave_{pattern}",
            f"{pattern}_flag",
            f"{pattern}_detected"
        ]
        
        # Check for pattern indicators
        for indicator in pattern_variations:
            if indicator in row and row[indicator]:
                return True
        
        return False
    
    def _check_bearish_pattern(self, row: pd.Series) -> bool:
        """
        Check if the row contains bearish reversal patterns.
        
        Args:
            row: DataFrame row with wave annotations
            
        Returns:
            True if bearish pattern exists, False otherwise
        """
        # Common bearish patterns
        bearish_patterns = [
            'bearish_reversal',
            'impulse_end',
            'wave_5_end',
            'sell_signal',
            'double_top',
            'head_and_shoulders',
            'bearish_divergence'
        ]
        
        for pattern in bearish_patterns:
            if self._check_pattern_exists(row, pattern):
                return True
        
        return False
    
    def _check_bullish_pattern(self, row: pd.Series) -> bool:
        """
        Check if the row contains bullish reversal patterns.
        
        Args:
            row: DataFrame row with wave annotations
            
        Returns:
            True if bullish pattern exists, False otherwise
        """
        # Common bullish patterns
        bullish_patterns = [
            'bullish_reversal',
            'correction_end',
            'wave_c_end',
            'buy_signal',
            'double_bottom',
            'inverse_head_and_shoulders',
            'bullish_divergence'
        ]
        
        for pattern in bullish_patterns:
            if self._check_pattern_exists(row, pattern):
                return True
        
        return False