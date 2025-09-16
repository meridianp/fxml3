#!/usr/bin/env python3
"""Comprehensive backtest with 400:1 leverage using all system features."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import logging
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from pathlib import Path
import json
from dotenv import load_dotenv
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import pickle

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Import FXML4 modules we know work
from fxml4.data.polygon_official_fetcher import PolygonDataManager
from fxml4.llm_integration.multimodal_mtf_validator import MultiTimeframeChartValidator
from fxml4.features.feature_engineering import UnifiedFeatureEngineer
from fxml4.ml.features import create_basic_technical_features
from fxml4.wave_analysis.elliott_wave import ElliottWaveAnalyzer
from fxml4.wave_analysis.fibonacci import FibonacciCalculator


@dataclass
class ComprehensiveTrade:
    """Comprehensive trade record with all details."""
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
    exit_reason: str


class ComprehensiveBacktester:
    """Complete FXML4 backtesting system with 400:1 leverage."""
    
    def __init__(self, 
                 initial_capital: float = 10000,
                 max_leverage: float = 400.0,
                 min_lot_size: float = 1.0,  # $1 micro lots
                 commission_per_lot: float = 0.02,  # $0.02 per $1000 traded
                 max_risk_per_trade: float = 0.02,  # 2% risk per trade
                 polygon_api_key: Optional[str] = None):
        """Initialize the comprehensive backtesting system."""
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.max_leverage = max_leverage
        self.min_lot_size = min_lot_size
        self.commission_per_lot = commission_per_lot
        self.max_risk_per_trade = max_risk_per_trade
        
        # Initialize components
        self.polygon_manager = PolygonDataManager(polygon_api_key)
        
        # Feature engineer with all enhancements
        self.feature_engineer = UnifiedFeatureEngineer({
            'basic_indicators': ['sma', 'ema', 'rsi', 'macd', 'bollinger', 'stoch', 'atr', 'adx'],
            'ma_periods': [5, 21, 55, 200],
            'advanced_features': True,
            'elliott_wave_features': True,
            'regime_features': True,
            'microstructure_features': True
        })
        
        # Elliott Wave analyzer
        self.elliott_analyzer = ElliottWaveAnalyzer()
        self.fibonacci_calc = FibonacciCalculator()
        
        # Multi-timeframe validator
        self.mtf_validator = MultiTimeframeChartValidator(config={
            'timeframes': ['15m', '1H', '4H', 'D'],
            'candles_per_timeframe': {
                '15m': 100,
                '1H': 100,
                '4H': 60,
                'D': 30
            }
        })
        
        # Trading records
        self.trades: List[ComprehensiveTrade] = []
        self.open_positions: Dict[str, Any] = {}
        self.equity_curve = []
        self.max_drawdown = 0
        self.peak_equity = initial_capital
        
    async def run_backtest(self,
                          symbol: str,
                          start_date: datetime,
                          end_date: datetime) -> Dict[str, Any]:
        """Run comprehensive backtest with all system features."""
        polygon_symbol = f"C:{symbol}"
        
        logger.info(f"\n{'='*60}")
        logger.info("COMPREHENSIVE FXML4 BACKTEST - 400:1 LEVERAGE")
        logger.info(f"{'='*60}")
        logger.info(f"Symbol: {symbol}")
        logger.info(f"Period: {start_date.date()} to {end_date.date()}")
        logger.info(f"Initial Capital: ${self.initial_capital:,.2f}")
        logger.info(f"Max Leverage: {self.max_leverage}:1")
        logger.info(f"Min Position Size: ${self.min_lot_size}")
        
        # Fetch multi-timeframe data
        logger.info("\nFetching historical data from Polygon.io...")
        timeframes = ['15m', '1H', '4H', 'D']
        
        historical_data = self.polygon_manager.get_backtest_data(
            polygon_symbol,
            timeframes,
            start_date - timedelta(days=100),  # Buffer for indicators
            end_date
        )
        
        if '4H' not in historical_data:
            logger.error("Failed to fetch data")
            return {}
            
        primary_data = historical_data['4H']
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
            
        # Process signals
        total_signals = 0
        ml_signals_count = 0
        elliott_validated = 0
        llm_validated = 0
        executed_trades = 0
        
        # Generate signals using enhanced strategy
        for i in range(200, len(primary_data), 4):  # Check every 16 hours
            current_time = primary_data.index[i]
            
            # Skip if outside backtest period
            if current_time < start_date or current_time > end_date:
                continue
                
            # Update equity tracking
            current_equity = self._calculate_current_equity(primary_data.iloc[i])
            self.equity_curve.append({
                'timestamp': current_time,
                'equity': current_equity
            })
            
            # Update drawdown
            if current_equity > self.peak_equity:
                self.peak_equity = current_equity
            drawdown = (self.peak_equity - current_equity) / self.peak_equity
            self.max_drawdown = max(self.max_drawdown, drawdown)
            
            # Risk check
            if len(self.open_positions) >= 3:  # Max 3 concurrent positions
                continue
                
            # Generate signal using ML or technical analysis
            signal = await self._generate_comprehensive_signal(
                features_df.iloc[:i+1] if i < len(features_df) else primary_data.iloc[:i+1],
                current_time,
                ml_model
            )
            
            if signal and signal['confidence'] > 0.6:
                total_signals += 1
                ml_signals_count += 1
                
                # Elliott Wave validation
                wave_score = await self._validate_elliott_wave(
                    primary_data.iloc[:i+1],
                    signal
                )
                
                if wave_score > 0.5:
                    elliott_validated += 1
                    
                    # Enhance signal with Elliott Wave score
                    enhanced_signal = {
                        **signal,
                        'elliott_wave_score': wave_score
                    }
                    
                    # Multi-timeframe LLM validation
                    llm_result = await self._validate_with_llm(
                        enhanced_signal,
                        current_time,
                        historical_data,
                        indicators_by_tf
                    )
                    
                    if llm_result['valid'] and llm_result['llm_confidence'] >= 0.65:
                        llm_validated += 1
                        
                        # Calculate position size with leverage
                        position_details = self._calculate_leveraged_position(
                            enhanced_signal,
                            llm_result,
                            primary_data.iloc[i]
                        )
                        
                        if position_details['position_size'] >= self.min_lot_size:
                            # Execute trade
                            executed_trades += 1
                            self._execute_trade(
                                enhanced_signal,
                                position_details,
                                llm_result,
                                wave_score
                            )
                            
                            logger.info(f"\n✅ Trade #{executed_trades} executed at {current_time}")
                            logger.info(f"   Direction: {enhanced_signal['direction']}")
                            logger.info(f"   Size: ${position_details['position_size']:,.2f} ({position_details['lots']:.0f} micro lots)")
                            logger.info(f"   Leverage: {position_details['effective_leverage']:.1f}:1")
                            logger.info(f"   ML: {enhanced_signal['confidence']:.1%}, Elliott: {wave_score:.1%}, LLM: {llm_result['llm_confidence']:.1%}")
            
            # Check exits for open positions
            self._check_exits(primary_data.iloc[i], current_time)
            
        # Close any remaining positions at end
        if self.open_positions:
            logger.info("\nClosing remaining positions at end of backtest...")
            for _ in list(self.open_positions.keys()):
                self._check_exits(primary_data.iloc[-1], primary_data.index[-1], force_close=True)
            
        # Calculate final results
        results = self._calculate_results()
        
        # Display summary
        logger.info(f"\n{'='*60}")
        logger.info("BACKTEST RESULTS SUMMARY")
        logger.info(f"{'='*60}")
        
        logger.info("\nSignal Funnel:")
        logger.info(f"Total Signals Generated: {total_signals}")
        logger.info(f"ML/Technical Signals (>60% conf): {ml_signals_count}")
        logger.info(f"Elliott Wave Validated (>50%): {elliott_validated}")
        logger.info(f"LLM Validated (>65%): {llm_validated}")
        logger.info(f"Trades Executed: {executed_trades}")
        
        logger.info("\nPerformance Metrics:")
        logger.info(f"Total Trades: {results['total_trades']}")
        logger.info(f"Winning Trades: {results['winning_trades']} ({results['win_rate']:.1%})")
        logger.info(f"Average Win: ${results['avg_win']:,.2f}")
        logger.info(f"Average Loss: ${results['avg_loss']:,.2f}")
        logger.info(f"Profit Factor: {results['profit_factor']:.2f}")
        
        logger.info("\nCapital & Returns:")
        logger.info(f"Starting Capital: ${self.initial_capital:,.2f}")
        logger.info(f"Final Capital: ${results['final_capital']:,.2f}")
        logger.info(f"Total PnL: ${results['total_pnl']:,.2f}")
        logger.info(f"Total Return: {results['total_return']:.2%}")
        logger.info(f"Max Drawdown: {results['max_drawdown']:.2%}")
        logger.info(f"Sharpe Ratio: {results['sharpe_ratio']:.2f}")
        
        logger.info("\nLeverage Usage:")
        logger.info(f"Average Leverage: {results['avg_leverage']:.1f}:1")
        logger.info(f"Max Leverage Used: {results['max_leverage']:.1f}:1")
        logger.info(f"Total Commission: ${results['total_commission']:,.2f}")
        
        # Save detailed results
        self._save_results(results, start_date, end_date)
        
        return results
        
    async def _load_ml_model(self, symbol: str):
        """Load ML model if available."""
        # Check for existing trained models
        model_paths = [
            f'models/{symbol}_100x_leverage/gb_model.pkl',
            f'models/{symbol}_100x_leverage/rf_model.pkl',
            f'models/{symbol}_100x_simple/model.pkl'
        ]
        
        for model_path in model_paths:
            if Path(model_path).exists():
                logger.info(f"Loading ML model from {model_path}")
                try:
                    with open(model_path, 'rb') as f:
                        model = pickle.load(f)
                    
                    # Load scaler if available
                    scaler_path = Path(model_path).parent / 'scaler.pkl'
                    if scaler_path.exists():
                        with open(scaler_path, 'rb') as f:
                            scaler = pickle.load(f)
                    else:
                        scaler = None
                        
                    return {'model': model, 'scaler': scaler, 'path': model_path}
                except Exception as e:
                    logger.warning(f"Failed to load model {model_path}: {e}")
                    
        logger.info("No ML model found, using technical analysis")
        return None
        
    async def _generate_comprehensive_signal(self, data: pd.DataFrame, current_time: datetime, ml_model: Optional[Dict]) -> Optional[Dict[str, Any]]:
        """Generate signal using ML or enhanced technical analysis."""
        if len(data) < 200:
            return None
            
        current_price = data['close'].iloc[-1]
        
        # Try ML model first
        if ml_model and 'model' in ml_model:
            try:
                # Prepare features for ML model
                features = data.iloc[-1:].copy()
                
                # Apply scaler if available
                if ml_model.get('scaler'):
                    feature_cols = [col for col in features.columns if col not in ['open', 'high', 'low', 'close', 'volume']]
                    if feature_cols:
                        features[feature_cols] = ml_model['scaler'].transform(features[feature_cols])
                
                # Make prediction
                if hasattr(ml_model['model'], 'predict_proba'):
                    proba = ml_model['model'].predict_proba(features.iloc[-1:])
                    confidence = float(proba[0][1]) if proba.shape[1] > 1 else 0.5
                else:
                    prediction = ml_model['model'].predict(features.iloc[-1:])
                    confidence = 0.7 if prediction[0] > 0 else 0.3
                    
                if confidence > 0.6:
                    direction = 'BUY' if confidence > 0.5 else 'SELL'
                    return {
                        'symbol': 'GBPUSD',
                        'direction': direction,
                        'confidence': confidence,
                        'timestamp': current_time,
                        'entry_price': current_price,
                        'stop_loss': current_price * (0.995 if direction == 'BUY' else 1.005),
                        'take_profit': current_price * (1.01 if direction == 'BUY' else 0.99),
                        'timeframe': '4H',
                        'source': 'ML Model'
                    }
            except Exception as e:
                logger.warning(f"ML prediction failed: {e}")
        
        # Fallback to enhanced technical analysis
        return self._generate_technical_signal(data, current_time)
        
    def _generate_technical_signal(self, data: pd.DataFrame, current_time: datetime) -> Optional[Dict[str, Any]]:
        """Generate signal using enhanced technical analysis."""
        # Calculate indicators
        sma_20 = data['close'].rolling(20).mean()
        sma_50 = data['close'].rolling(50).mean()
        sma_200 = data['close'].rolling(200).mean()
        
        # RSI
        delta = data['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        # MACD
        exp1 = data['close'].ewm(span=12).mean()
        exp2 = data['close'].ewm(span=26).mean()
        macd = exp1 - exp2
        macd_signal = macd.ewm(span=9).mean()
        
        current_price = data['close'].iloc[-1]
        current_rsi = rsi.iloc[-1]
        
        # Enhanced signal logic
        confidence = 0.5  # Base confidence
        
        # Strong uptrend
        if sma_20.iloc[-1] > sma_50.iloc[-1] > sma_200.iloc[-1]:
            if current_rsi < 70 and macd.iloc[-1] > macd_signal.iloc[-1]:
                confidence += 0.2
                
                # Recent golden cross
                if sma_20.iloc[-2] <= sma_50.iloc[-2]:
                    confidence += 0.1
                    
                # Price above all MAs
                if current_price > sma_200.iloc[-1]:
                    confidence += 0.05
                    
                if confidence > 0.6:
                    return {
                        'symbol': 'GBPUSD',
                        'direction': 'BUY',
                        'confidence': min(confidence, 0.85),
                        'timestamp': current_time,
                        'entry_price': current_price,
                        'stop_loss': current_price - 0.0050,
                        'take_profit': current_price + 0.0100,
                        'timeframe': '4H',
                        'source': 'Technical Analysis',
                        'reason': f'Uptrend alignment, RSI {current_rsi:.0f}'
                    }
                    
        # Strong downtrend
        elif sma_20.iloc[-1] < sma_50.iloc[-1] < sma_200.iloc[-1]:
            if current_rsi > 30 and macd.iloc[-1] < macd_signal.iloc[-1]:
                confidence += 0.2
                
                # Recent death cross
                if sma_20.iloc[-2] >= sma_50.iloc[-2]:
                    confidence += 0.1
                    
                # Price below all MAs
                if current_price < sma_200.iloc[-1]:
                    confidence += 0.05
                    
                if confidence > 0.6:
                    return {
                        'symbol': 'GBPUSD',
                        'direction': 'SELL',
                        'confidence': min(confidence, 0.85),
                        'timestamp': current_time,
                        'entry_price': current_price,
                        'stop_loss': current_price + 0.0050,
                        'take_profit': current_price - 0.0100,
                        'timeframe': '4H',
                        'source': 'Technical Analysis',
                        'reason': f'Downtrend alignment, RSI {current_rsi:.0f}'
                    }
                    
        return None
        
    async def _validate_elliott_wave(self, price_data: pd.DataFrame, signal: Dict[str, Any]) -> float:
        """Validate signal with Elliott Wave analysis."""
        try:
            # Analyze wave patterns
            wave_count = self.elliott_analyzer.analyze(price_data)
            
            if wave_count and wave_count.waves:
                # Calculate Fibonacci levels
                fib_levels = self.fibonacci_calc.calculate_retracement_levels(
                    price_data['high'].max(),
                    price_data['low'].min()
                )
                
                # Score based on wave position
                current_price = price_data['close'].iloc[-1]
                wave_score = 0.5  # Base score
                
                # Adjust score based on wave patterns
                patterns = wave_count.waves[-3:] if len(wave_count.waves) >= 3 else wave_count.waves
                
                # Check wave types and confidence
                for pattern in patterns:
                    if pattern.confidence > 0.7:
                        wave_score += 0.2
                        
                    # Check Fibonacci relationships
                    if signal['direction'] == 'BUY':
                        # Check if near Fibonacci support levels
                        for level in [0.382, 0.5, 0.618]:
                            if abs(current_price - fib_levels[level]) / current_price < 0.002:
                                wave_score += 0.15
                                break
                    else:
                        # Check if near Fibonacci resistance levels
                        for level in [1.618, 1.382, 1.236]:
                            if abs(current_price - fib_levels.get(level, current_price)) / current_price < 0.002:
                                wave_score += 0.15
                                break
                        
                return min(wave_score, 0.9)
            else:
                return 0.5  # Neutral if no clear pattern
                
        except Exception as e:
            logger.error(f"Elliott Wave validation error: {e}")
            return 0.5
            
    async def _validate_with_llm(self, signal: Dict[str, Any], current_time: datetime,
                               historical_data: Dict[str, pd.DataFrame],
                               indicators_by_tf: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
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
            return {'valid': False, 'llm_confidence': 0}
            
    def _calculate_leveraged_position(self, signal: Dict[str, Any], 
                                    llm_result: Dict[str, Any],
                                    current_bar: pd.Series) -> Dict[str, Any]:
        """Calculate position size with 400:1 leverage."""
        # Base position calculation
        stop_distance = abs(signal['entry_price'] - signal['stop_loss'])
        risk_amount = self.capital * self.max_risk_per_trade
        
        # Position size based on risk
        base_position = risk_amount / stop_distance
        
        # Adjust for confidence scores (ML, Elliott Wave, LLM)
        confidence_multiplier = (
            signal['confidence'] * 0.4 +
            signal.get('elliott_wave_score', 0.5) * 0.3 +
            llm_result.get('llm_confidence', 0.5) * 0.3
        )
        
        # Apply leverage
        max_position = self.capital * self.max_leverage * 0.1  # 10% of leveraged capital per trade
        position_size = min(base_position * confidence_multiplier, max_position)
        
        # Round to micro lots ($1 minimum)
        lots = max(1, round(position_size / self.min_lot_size))
        position_size = lots * self.min_lot_size
        
        # Calculate effective leverage
        effective_leverage = position_size / self.capital
        
        return {
            'position_size': position_size,
            'lots': lots,
            'effective_leverage': effective_leverage,
            'risk_amount': stop_distance * position_size / signal['entry_price']
        }
        
    def _execute_trade(self, signal: Dict[str, Any], position: Dict[str, Any],
                      llm_result: Dict[str, Any], wave_score: float):
        """Execute a trade with all details."""
        trade_id = f"{signal['symbol']}_{signal['timestamp'].strftime('%Y%m%d_%H%M%S')}"
        
        # Calculate commission
        commission = (position['position_size'] / 1000) * self.commission_per_lot * 2  # Round trip
        
        # Store open position
        self.open_positions[trade_id] = {
            'signal': signal,
            'position': position,
            'llm_result': llm_result,
            'wave_score': wave_score,
            'entry_time': signal['timestamp'],
            'commission': commission
        }
        
        # Deduct commission from capital
        self.capital -= commission
        
    def _check_exits(self, current_bar: pd.Series, current_time: datetime, force_close: bool = False):
        """Check and process exits for open positions."""
        closed_trades = []
        
        for trade_id, position_data in self.open_positions.items():
            signal = position_data['signal']
            position = position_data['position']
            
            current_price = current_bar['close']
            exit_price = None
            exit_reason = None
            
            if force_close:
                exit_price = current_price
                exit_reason = 'End of Backtest'
            else:
                # Check stop loss and take profit
                if signal['direction'] == 'BUY':
                    if current_price <= signal['stop_loss']:
                        exit_price = signal['stop_loss']
                        exit_reason = 'Stop Loss'
                    elif current_price >= signal['take_profit']:
                        exit_price = signal['take_profit']
                        exit_reason = 'Take Profit'
                else:
                    if current_price >= signal['stop_loss']:
                        exit_price = signal['stop_loss']
                        exit_reason = 'Stop Loss'
                    elif current_price <= signal['take_profit']:
                        exit_price = signal['take_profit']
                        exit_reason = 'Take Profit'
                        
            if exit_price:
                # Calculate PnL
                if signal['direction'] == 'BUY':
                    pnl_pips = (exit_price - signal['entry_price']) * 10000
                    pnl = (exit_price - signal['entry_price']) / signal['entry_price'] * position['position_size']
                else:
                    pnl_pips = (signal['entry_price'] - exit_price) * 10000
                    pnl = (signal['entry_price'] - exit_price) / signal['entry_price'] * position['position_size']
                    
                # Subtract commission
                pnl -= position_data['commission']
                
                # Update capital
                self.capital += pnl
                
                # Record trade
                trade = ComprehensiveTrade(
                    timestamp=current_time,
                    direction=signal['direction'],
                    entry_price=signal['entry_price'],
                    exit_price=exit_price,
                    position_size=position['position_size'],
                    lots=position['lots'],
                    leverage_used=position['effective_leverage'],
                    pnl=pnl,
                    pnl_pips=pnl_pips,
                    ml_confidence=signal['confidence'],
                    llm_confidence=position_data['llm_result'].get('llm_confidence', 0),
                    elliott_wave_score=position_data['wave_score'],
                    exit_reason=exit_reason
                )
                
                self.trades.append(trade)
                closed_trades.append(trade_id)
                
        # Remove closed trades
        for trade_id in closed_trades:
            del self.open_positions[trade_id]
            
    def _calculate_current_equity(self, current_bar: pd.Series) -> float:
        """Calculate current equity including open positions."""
        equity = self.capital
        
        for position_data in self.open_positions.values():
            signal = position_data['signal']
            position = position_data['position']
            current_price = current_bar['close']
            
            # Unrealized PnL
            if signal['direction'] == 'BUY':
                unrealized_pnl = (current_price - signal['entry_price']) / signal['entry_price'] * position['position_size']
            else:
                unrealized_pnl = (signal['entry_price'] - current_price) / signal['entry_price'] * position['position_size']
                
            equity += unrealized_pnl
            
        return equity
        
    def _calculate_comprehensive_indicators(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Calculate comprehensive indicators for analysis."""
        indicators = {}
        
        if len(data) < 50:
            return indicators
            
        # Trend indicators
        indicators['sma_20'] = data['close'].rolling(20).mean()
        indicators['sma_50'] = data['close'].rolling(50).mean()
        indicators['sma_200'] = data['close'].rolling(200).mean() if len(data) >= 200 else None
        indicators['ema_9'] = data['close'].ewm(span=9).mean()
        
        # Momentum
        delta = data['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        indicators['rsi'] = 100 - (100 / (1 + rs))
        
        # MACD
        exp1 = data['close'].ewm(span=12).mean()
        exp2 = data['close'].ewm(span=26).mean()
        indicators['macd'] = exp1 - exp2
        indicators['macd_signal'] = indicators['macd'].ewm(span=9).mean()
        
        # Volatility
        indicators['atr'] = self._calculate_atr(data)
        bb_sma = data['close'].rolling(20).mean()
        bb_std = data['close'].rolling(20).std()
        indicators['bb_upper'] = bb_sma + (bb_std * 2)
        indicators['bb_lower'] = bb_sma - (bb_std * 2)
        
        return indicators
        
    def _calculate_atr(self, data: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate Average True Range."""
        high_low = data['high'] - data['low']
        high_close = np.abs(data['high'] - data['close'].shift())
        low_close = np.abs(data['low'] - data['close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = np.max(ranges, axis=1)
        return true_range.rolling(period).mean()
        
    def _align_indicators(self, indicators: Dict[str, Any], data: pd.DataFrame) -> Dict[str, Any]:
        """Align indicators to data index."""
        aligned = {}
        
        for name, ind in indicators.items():
            if isinstance(ind, pd.Series) and hasattr(ind, 'index'):
                aligned[name] = ind[ind.index.isin(data.index)]
            else:
                aligned[name] = ind
                
        return aligned
        
    def _calculate_results(self) -> Dict[str, Any]:
        """Calculate comprehensive backtest results."""
        if not self.trades:
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0,
                'avg_win': 0,
                'avg_loss': 0,
                'profit_factor': 0,
                'total_pnl': 0,
                'final_capital': self.capital,
                'total_return': 0,
                'max_drawdown': 0,
                'sharpe_ratio': 0,
                'avg_leverage': 0,
                'max_leverage': 0,
                'total_commission': 0
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
        sharpe_ratio = np.mean(returns) / np.std(returns) * np.sqrt(252) if returns and np.std(returns) > 0 else 0
        
        # Leverage metrics
        leverages = [t.leverage_used for t in self.trades]
        avg_leverage = np.mean(leverages) if leverages else 0
        max_leverage = max(leverages) if leverages else 0
        
        # Commission
        total_commission = sum(t.position_size / 1000 * self.commission_per_lot * 2 for t in self.trades)
        
        return {
            'total_trades': len(self.trades),
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'total_pnl': total_pnl,
            'final_capital': self.capital,
            'total_return': total_return,
            'max_drawdown': self.max_drawdown,
            'sharpe_ratio': sharpe_ratio,
            'avg_leverage': avg_leverage,
            'max_leverage': max_leverage,
            'avg_pnl_pips': np.mean([t.pnl_pips for t in self.trades]) if self.trades else 0,
            'total_commission': total_commission
        }
        
    def _save_results(self, results: Dict[str, Any], start_date: datetime, end_date: datetime):
        """Save detailed backtest results."""
        output_dir = Path('output/comprehensive_backtest_400x')
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Prepare data for JSON
        save_data = {
            'config': {
                'initial_capital': self.initial_capital,
                'max_leverage': self.max_leverage,
                'min_lot_size': self.min_lot_size,
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat()
            },
            'results': results,
            'trades': [
                {
                    'timestamp': t.timestamp.isoformat(),
                    'direction': t.direction,
                    'entry_price': t.entry_price,
                    'exit_price': t.exit_price,
                    'position_size': t.position_size,
                    'lots': t.lots,
                    'leverage_used': t.leverage_used,
                    'pnl': t.pnl,
                    'pnl_pips': t.pnl_pips,
                    'ml_confidence': t.ml_confidence,
                    'llm_confidence': t.llm_confidence,
                    'elliott_wave_score': t.elliott_wave_score,
                    'exit_reason': t.exit_reason
                }
                for t in self.trades
            ],
            'equity_curve': [
                {
                    'timestamp': point['timestamp'].isoformat() if hasattr(point['timestamp'], 'isoformat') else str(point['timestamp']),
                    'equity': point['equity']
                }
                for point in (self.equity_curve[-200:] if len(self.equity_curve) > 200 else self.equity_curve)
            ]
        }
        
        filename = output_dir / f'backtest_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        with open(filename, 'w') as f:
            json.dump(save_data, f, indent=2)
            
        logger.info(f"\nDetailed results saved to: {filename}")


async def main():
    """Run the comprehensive backtest."""
    # Check for API key
    polygon_api_key = os.getenv('POLYGON_API_KEY')
    if not polygon_api_key:
        logger.error("POLYGON_API_KEY not found in .env file")
        return
        
    # Initialize backtester with 400:1 leverage
    backtester = ComprehensiveBacktester(
        initial_capital=10000,
        max_leverage=400.0,
        min_lot_size=1.0,  # $1 micro lots
        commission_per_lot=0.02,
        max_risk_per_trade=0.02,
        polygon_api_key=polygon_api_key
    )
    
    # Run backtest for 2024
    await backtester.run_backtest(
        symbol='GBPUSD',
        start_date=datetime(2024, 1, 1),
        end_date=datetime(2024, 12, 31)
    )


if __name__ == "__main__":
    asyncio.run(main())