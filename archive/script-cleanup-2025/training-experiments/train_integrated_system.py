#!/usr/bin/env python
"""Train the complete integrated forex system with all enhancements."""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import joblib
import warnings
warnings.filterwarnings('ignore')

from scripts.exogenous_variable_analysis import ExogenousVariableAnalyzer
from scripts.enhanced_model_trainer import EnhancedModelTrainer
from scripts.correlation_analysis_system import CorrelationAnalysisSystem
from scripts.ensemble_ml_elliott_wave import EnsembleMLElliottWave

class IntegratedSystemTrainer:
    """Train the complete integrated forex trading system."""
    
    def __init__(self, symbols: list):
        self.symbols = symbols
        self.models_dir = Path("models/integrated_system")
        self.models_dir.mkdir(exist_ok=True, parents=True)
        
        # Initialize components
        self.exogenous_analyzer = ExogenousVariableAnalyzer()
        self.correlation_analyzer = CorrelationAnalysisSystem()
        self.model_trainers = {}
        self.ensemble_models = {}
        
        # Training results
        self.training_results = {}
        
    def load_all_data(self, start_date: str, end_date: str):
        """Load data for all symbols."""
        print("Loading forex data...")
        
        # Import the polygon data loader
        sys.path.append(str(Path(__file__).parent))
        from load_polygon_data import load_aggregated_data
        
        forex_data = {}
        for symbol in self.symbols:
            try:
                df = load_aggregated_data(f"C_{symbol}", start_date, end_date)
                if df is not None and len(df) > 252:  # At least 1 year of data
                    forex_data[symbol] = df
                    print(f"  ✅ {symbol}: {len(df)} records")
                else:
                    print(f"  ❌ {symbol}: Insufficient data")
            except Exception as e:
                print(f"  ❌ {symbol}: Error loading data - {e}")
        
        return forex_data
    
    def prepare_enhanced_features(self, symbol: str, forex_data: dict, economic_data: dict):
        """Prepare enhanced features including exogenous variables."""
        print(f"\nPreparing enhanced features for {symbol}...")
        
        # Get target data
        target_df = forex_data[symbol]
        target_series = target_df['close']
        
        # Get other forex data
        other_forex = {k: v['close'] for k, v in forex_data.items() if k != symbol}
        
        # Create exogenous features with technical indicators for target
        features = self.exogenous_analyzer.create_lagged_features(
            pd.DataFrame(economic_data), 
            symbol,
            target_df
        )
        
        # Add other forex pairs
        for other_symbol, other_data in other_forex.items():
            features[other_symbol] = other_data
            # Add lagged features
            for lag in [1, 2, 3, 5, 10]:
                features[f'{other_symbol}_lag{lag}'] = other_data.shift(lag)
        
        # Add original technical features from target
        # These are the features we've been using successfully
        original_features = self.create_original_features(target_df)
        
        # Combine all features
        all_features = pd.concat([features, original_features], axis=1)
        
        # Remove duplicates
        all_features = all_features.loc[:, ~all_features.columns.duplicated()]
        
        return all_features
    
    def create_original_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create the original feature set that worked well."""
        features = pd.DataFrame(index=df.index)
        
        # Price features
        features['returns'] = df['close'].pct_change()
        features['log_returns'] = np.log(df['close']).diff()
        
        # Moving averages
        for period in [5, 10, 20, 50, 100, 200]:
            features[f'sma_{period}'] = df['close'].rolling(period).mean()
            features[f'price_to_sma_{period}'] = df['close'] / features[f'sma_{period}']
        
        # RSI
        for period in [7, 14, 21]:
            features[f'rsi_{period}'] = self.calculate_rsi(df['close'], period)
        
        # Bollinger Bands
        for period in [20, 50]:
            sma = df['close'].rolling(period).mean()
            std = df['close'].rolling(period).std()
            features[f'bb_upper_{period}'] = sma + (2 * std)
            features[f'bb_lower_{period}'] = sma - (2 * std)
            features[f'bb_width_{period}'] = features[f'bb_upper_{period}'] - features[f'bb_lower_{period}']
            features[f'bb_position_{period}'] = (df['close'] - features[f'bb_lower_{period}']) / features[f'bb_width_{period}']
        
        # ATR
        tr = pd.DataFrame(index=df.index)
        tr['hl'] = df['high'] - df['low']
        tr['hc'] = abs(df['high'] - df['close'].shift(1))
        tr['lc'] = abs(df['low'] - df['close'].shift(1))
        true_range = tr.max(axis=1)
        
        for period in [7, 14, 21]:
            features[f'atr_{period}'] = true_range.rolling(period).mean()
            features[f'atr_ratio_{period}'] = features[f'atr_{period}'] / df['close']
        
        # Volume features
        if 'volume' in df.columns and df['volume'].sum() > 0:
            features['volume_sma'] = df['volume'].rolling(20).mean()
            features['volume_ratio'] = df['volume'] / features['volume_sma']
        
        # Volatility
        for period in [5, 10, 20]:
            features[f'volatility_{period}'] = df['close'].pct_change().rolling(period).std()
        
        # Price patterns
        features['higher_high'] = ((df['high'] > df['high'].shift(1)) & 
                                  (df['high'].shift(1) > df['high'].shift(2))).astype(int)
        features['lower_low'] = ((df['low'] < df['low'].shift(1)) & 
                                (df['low'].shift(1) < df['low'].shift(2))).astype(int)
        
        # Support/Resistance
        for period in [20, 50]:
            features[f'resistance_{period}'] = df['high'].rolling(period).max()
            features[f'support_{period}'] = df['low'].rolling(period).min()
            features[f'sr_position_{period}'] = (df['close'] - features[f'support_{period}']) / \
                                               (features[f'resistance_{period}'] - features[f'support_{period}'])
        
        return features
    
    def calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Calculate RSI."""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def select_best_features(self, X: pd.DataFrame, y: pd.Series, symbol: str, n_features: int = 100):
        """Select best features using the exogenous analyzer's method."""
        print(f"\nSelecting best features for {symbol}...")
        
        selected_features, X_selected = self.exogenous_analyzer.select_relevant_features(
            X, y, n_features=n_features
        )
        
        # Save feature list
        feature_file = self.models_dir / f"{symbol}_selected_features.json"
        with open(feature_file, 'w') as f:
            json.dump({
                'features': selected_features,
                'n_features': len(selected_features),
                'total_candidates': len(X.columns)
            }, f, indent=2)
        
        print(f"  Selected {len(selected_features)} from {len(X.columns)} features")
        
        return X_selected, selected_features
    
    def train_symbol(self, symbol: str, forex_data: dict, economic_data: dict):
        """Train models for a single symbol."""
        print(f"\n{'='*70}")
        print(f"Training models for {symbol}")
        print(f"{'='*70}")
        
        # Prepare features
        X = self.prepare_enhanced_features(symbol, forex_data, economic_data)
        
        # Target: Next day return
        y = forex_data[symbol]['close'].pct_change().shift(-1)
        
        # Align data
        mask = ~(X.isna().any(axis=1) | y.isna())
        X_clean = X[mask]
        y_clean = y[mask]
        
        print(f"\nData shape after cleaning:")
        print(f"  Original: {len(X)} samples, {X.shape[1]} features")
        print(f"  Clean: {len(X_clean)} samples")
        
        if len(X_clean) < 500:  # Reduced threshold
            print(f"⚠️  Insufficient clean data for {symbol}: {len(X_clean)} samples")
            return None
        
        # Feature selection
        X_selected, selected_features = self.select_best_features(
            X_clean, y_clean, symbol, n_features=100
        )
        
        # Split data (80/20)
        split_idx = int(len(X_selected) * 0.8)
        
        X_train = X_selected.iloc[:split_idx]
        X_test = X_selected.iloc[split_idx:]
        y_train = y_clean.iloc[:split_idx]
        y_test = y_clean.iloc[split_idx:]
        
        print(f"\nTraining set: {len(X_train)} samples")
        print(f"Test set: {len(X_test)} samples")
        
        # Initialize trainer
        trainer = EnhancedModelTrainer(symbol)
        
        # Train models
        results = trainer.train_all_models(
            X_train, y_train, X_test, y_test,
            optimize_threshold=True
        )
        
        # Save models and results
        model_file = self.models_dir / f"{symbol}_models.joblib"
        joblib.dump({
            'models': trainer.models,
            'scalers': trainer.scalers,
            'selected_features': selected_features,
            'training_results': results
        }, model_file)
        
        # Initialize ensemble model
        ensemble = EnsembleMLElliottWave(symbol)
        ensemble.ml_model = trainer.models['ensemble']
        ensemble.scaler = trainer.scalers['ensemble']
        ensemble.feature_columns = selected_features
        self.ensemble_models[symbol] = ensemble
        
        # Store results
        self.training_results[symbol] = results
        
        return results
    
    def train_all_symbols(self, start_date: str, end_date: str):
        """Train models for all symbols."""
        print("\n" + "="*80)
        print("INTEGRATED FOREX SYSTEM TRAINING")
        print("="*80)
        print(f"Symbols: {', '.join(self.symbols)}")
        print(f"Period: {start_date} to {end_date}")
        
        # Load forex data
        forex_data = self.load_all_data(start_date, end_date)
        
        if len(forex_data) < 2:
            print("❌ Insufficient data for training")
            return
        
        # Fetch economic indicators
        print("\nFetching economic indicators...")
        economic_data = self.exogenous_analyzer.fetch_all_exogenous_data(
            self.symbols, start_date, end_date
        )
        
        # Train each symbol
        for symbol in self.symbols:
            if symbol in forex_data:
                self.train_symbol(symbol, forex_data, economic_data)
        
        # Summary
        self.print_training_summary()
        
        # Save overall results
        summary_file = self.models_dir / "training_summary.json"
        with open(summary_file, 'w') as f:
            json.dump({
                'symbols': self.symbols,
                'training_date': datetime.now().isoformat(),
                'start_date': start_date,
                'end_date': end_date,
                'results': self.training_results
            }, f, indent=2)
        
        print(f"\n✅ Training complete! Models saved to: {self.models_dir}")
    
    def print_training_summary(self):
        """Print summary of training results."""
        print("\n" + "="*80)
        print("TRAINING SUMMARY")
        print("="*80)
        
        for symbol, results in self.training_results.items():
            print(f"\n{symbol}:")
            
            if 'ensemble' in results:
                ens = results['ensemble']
                print(f"  Ensemble Model:")
                print(f"    Direction Accuracy: {ens['test_direction_accuracy']:.1%}")
                print(f"    Sharpe Ratio: {ens['sharpe_ratio']:.2f}")
                print(f"    Optimal Threshold: {ens.get('optimal_threshold', 0.001):.4f}")
                print(f"    Signal Rate: {ens.get('signal_rate', 0):.1%}")
            
            # Best individual model
            best_model = None
            best_accuracy = 0
            
            for model_name, metrics in results.items():
                if model_name != 'ensemble' and 'test_direction_accuracy' in metrics:
                    if metrics['test_direction_accuracy'] > best_accuracy:
                        best_accuracy = metrics['test_direction_accuracy']
                        best_model = model_name
            
            if best_model:
                print(f"  Best Individual: {best_model} ({best_accuracy:.1%})")


def main():
    """Run integrated system training."""
    # Configuration
    symbols = ['EURUSD', 'GBPUSD', 'USDJPY', 'USDCHF']
    
    # Use last 3 years for training (keeping most recent for live trading)
    end_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=365*3)).strftime('%Y-%m-%d')
    
    # Initialize trainer
    trainer = IntegratedSystemTrainer(symbols)
    
    # Train all symbols
    trainer.train_all_symbols(start_date, end_date)
    
    print("\n💡 Next steps:")
    print("1. Run backtesting with integrated system: python scripts/backtest_integrated_system.py")
    print("2. Start paper trading: python scripts/start_paper_trading.py")
    print("3. Monitor performance: python scripts/monitor_integrated_system.py")


if __name__ == "__main__":
    main()