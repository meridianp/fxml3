#!/usr/bin/env python
"""Train integrated model with anti-overfitting measures and Elliott Wave analysis."""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
from datetime import datetime
import json
import joblib
import logging
import warnings
warnings.filterwarnings('ignore')

from fxml4.ml.robust_model_trainer import RobustModelTrainer
from fxml4.wave_analysis.elliott_wave import ElliottWaveAnalyzer
from fxml4.strategy.integrated_signal_generator import IntegratedSignalGenerator

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def prepare_wave_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add Elliott Wave-based features to the dataset."""
    logger.info("Generating Elliott Wave features...")
    
    wave_analyzer = ElliottWaveAnalyzer()
    wave_features = []
    
    # Analyze in rolling windows
    window_size = 200
    step_size = 1
    
    for i in range(window_size, len(df), step_size):
        window_data = df.iloc[i-window_size:i]
        
        try:
            # Analyze wave patterns
            wave_count = wave_analyzer.analyze(window_data)
            
            if wave_count and wave_count.waves:
                current_wave = wave_count.get_current_wave()
                
                # Extract features
                features = {
                    'wave_position': wave_count.get_position_in_cycle(),
                    'wave_degree': current_wave.degree.value if current_wave else 0,
                    'wave_completion': wave_count.get_completion_percentage() / 100,
                    'is_impulse': 1 if wave_count.is_impulse_wave() else 0,
                    'is_corrective': 1 if wave_count.is_corrective_wave() else 0,
                    'wave_confidence': wave_count.confidence,
                    'next_wave_target': wave_count.get_next_target_price() if wave_count.get_next_target_price() else df.iloc[i-1]['close']
                }
            else:
                # Default features
                features = {
                    'wave_position': 0,
                    'wave_degree': 0,
                    'wave_completion': 0,
                    'is_impulse': 0,
                    'is_corrective': 0,
                    'wave_confidence': 0,
                    'next_wave_target': df.iloc[i-1]['close']
                }
                
        except Exception as e:
            logger.debug(f"Wave analysis error at index {i}: {e}")
            features = {
                'wave_position': 0,
                'wave_degree': 0,
                'wave_completion': 0,
                'is_impulse': 0,
                'is_corrective': 0,
                'wave_confidence': 0,
                'next_wave_target': df.iloc[i-1]['close']
            }
            
        wave_features.append(features)
    
    # Create DataFrame
    wave_df = pd.DataFrame(wave_features, index=df.index[window_size:])
    
    # Add wave-based derived features
    wave_df['wave_target_distance'] = (wave_df['next_wave_target'] - df.loc[wave_df.index, 'close']) / df.loc[wave_df.index, 'close']
    wave_df['wave_momentum'] = wave_df['wave_position'].diff()
    
    # Align with original DataFrame
    for col in wave_df.columns:
        df.loc[wave_df.index, col] = wave_df[col]
        
    # Fill NaN values for initial rows
    df.fillna(method='bfill', inplace=True)
    
    logger.info(f"Added {len(wave_df.columns)} Elliott Wave features")
    
    return df


def create_robust_target(df: pd.DataFrame, lookahead_bars: int = 10) -> pd.Series:
    """
    Create target variable with multiple confirmation bars to reduce noise.
    This helps prevent overfitting to single-bar movements.
    """
    # Calculate future returns over multiple bars
    future_returns = []
    
    for i in range(1, lookahead_bars + 1):
        future_returns.append(df['close'].pct_change(periods=i).shift(-i))
    
    # Average future returns
    avg_future_return = pd.concat(future_returns, axis=1).mean(axis=1)
    
    # More conservative thresholds
    buy_threshold = 0.002   # 0.2% average gain
    sell_threshold = -0.002  # 0.2% average loss
    
    # Create target
    conditions = [
        avg_future_return > buy_threshold,
        avg_future_return < sell_threshold
    ]
    choices = [2, 0]  # 2=buy, 0=sell, 1=hold (default)
    
    target = pd.Series(
        np.select(conditions, choices, default=1),
        index=df.index,
        name='target'
    )
    
    return target


def main():
    """Train robust integrated model."""
    print("="*80)
    print("TRAINING INTEGRATED MODEL WITH ANTI-OVERFITTING MEASURES")
    print("="*80)
    
    # Parameters
    symbol = "GBPUSD"
    
    # Load data
    logger.info(f"Loading data for {symbol}...")
    feature_file = Path(f"data/features/{symbol}_4h_features_advanced.parquet")
    df = pd.read_parquet(feature_file)
    
    # Add Elliott Wave features
    df = prepare_wave_features(df)
    
    # Create robust target
    logger.info("Creating robust target variable...")
    df['target'] = create_robust_target(df, lookahead_bars=10)
    
    # Remove last rows with NaN target
    df = df.dropna(subset=['target'])
    
    logger.info(f"Data shape: {df.shape}")
    
    # Get all feature columns
    exclude_cols = ['open', 'high', 'low', 'close', 'volume', 'target']
    all_features = [col for col in df.columns if col not in exclude_cols]
    
    logger.info(f"Total features available: {len(all_features)}")
    
    # Initialize robust trainer
    trainer = RobustModelTrainer()
    
    # Train robust model
    logger.info("Training robust model with anti-overfitting measures...")
    result = trainer.train_robust_model(
        data=df,
        features=all_features,
        target_col='target',
        test_size=0.3  # 30% test set
    )
    
    # Print results
    print("\n" + "="*80)
    print("TRAINING RESULTS")
    print("="*80)
    
    print(f"\nModel Performance:")
    print(f"Training Accuracy: {result['train_accuracy']:.4f}")
    print(f"Test Accuracy: {result['test_accuracy']:.4f}")
    print(f"Overfit Ratio: {result['overfit_ratio']:.2f}")
    
    print(f"\nFeature Selection:")
    print(f"Original features: {len(all_features)}")
    print(f"Selected stable features: {len(result['features'])}")
    
    # Show top stable features
    print(f"\nTop 10 Most Stable Features:")
    stability_scores = result['stability_scores']
    top_features = sorted(stability_scores.items(), key=lambda x: x[1], reverse=True)[:10]
    
    for feature, score in top_features:
        print(f"  {feature}: {score:.3f}")
    
    # Check if Elliott Wave features are selected
    wave_features_selected = [f for f in result['features'] if 'wave' in f]
    print(f"\nElliott Wave features selected: {len(wave_features_selected)}")
    for feature in wave_features_selected:
        print(f"  {feature}")
    
    # Save model and metadata
    output_dir = Path(f"models/{symbol}_integrated")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Save best model
    model_path = output_dir / "model.joblib"
    scaler_path = output_dir / "scaler.joblib"
    
    joblib.dump(result['model'], model_path)
    joblib.dump(result['scaler'], scaler_path)
    
    # Save metadata
    metadata = {
        'symbol': symbol,
        'training_date': datetime.now().isoformat(),
        'train_accuracy': result['train_accuracy'],
        'test_accuracy': result['test_accuracy'],
        'overfit_ratio': result['overfit_ratio'],
        'n_features': len(result['features']),
        'features': result['features'],
        'elliott_wave_features': wave_features_selected,
        'anti_overfitting_measures': [
            'Feature stability analysis',
            'Time decay weighting',
            'Noise injection',
            'Conservative model complexity',
            'Multi-bar target averaging',
            'Proper time series validation'
        ]
    }
    
    with open(output_dir / 'training_metadata.json', 'w') as f:
        json.dump(metadata, f, indent=2)
    
    # Save feature list
    with open(output_dir / 'selected_features.json', 'w') as f:
        json.dump(result['features'], f, indent=2)
    
    print(f"\nModel saved to: {output_dir}")
    
    # Demonstrate integrated signal generation
    print("\n" + "="*80)
    print("TESTING INTEGRATED SIGNAL GENERATOR")
    print("="*80)
    
    # Create integrated signal generator
    signal_generator = IntegratedSignalGenerator(
        ml_model=result['model'],
        ml_scaler=result['scaler'],
        ml_features=result['features'],
        use_llm_validation=False  # Set to True if LLM keys are configured
    )
    
    # Generate sample signals
    test_start = -100
    sample_signals = []
    
    for i in range(test_start, -50):
        try:
            signal = signal_generator.generate_signal(df, i)
            sample_signals.append(signal)
        except Exception as e:
            logger.debug(f"Signal generation error: {e}")
            
    # Show sample signals
    print(f"\nGenerated {len(sample_signals)} signals")
    
    if sample_signals:
        # Analyze signals
        buy_signals = [s for s in sample_signals if s.direction == 1]
        sell_signals = [s for s in sample_signals if s.direction == -1]
        hold_signals = [s for s in sample_signals if s.direction == 0]
        
        print(f"\nSignal Distribution:")
        print(f"Buy signals: {len(buy_signals)} ({len(buy_signals)/len(sample_signals)*100:.1f}%)")
        print(f"Sell signals: {len(sell_signals)} ({len(sell_signals)/len(sample_signals)*100:.1f}%)")
        print(f"Hold signals: {len(hold_signals)} ({len(hold_signals)/len(sample_signals)*100:.1f}%)")
        
        # Show high confidence signals
        high_conf_signals = [s for s in sample_signals if s.confidence > 0.7]
        
        if high_conf_signals:
            print(f"\nHigh Confidence Signals (>70%):")
            for signal in high_conf_signals[:5]:
                print(f"\n{signal.timestamp}:")
                print(f"  Direction: {'BUY' if signal.direction == 1 else 'SELL' if signal.direction == -1 else 'HOLD'}")
                print(f"  Confidence: {signal.confidence:.1%}")
                print(f"  ML: {signal.ml_confidence:.1%}, Wave: {signal.wave_confidence:.1%}")
                print(f"  Reasoning: {signal.reasoning}")
    
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print("✓ Trained model with anti-overfitting measures")
    print("✓ Integrated Elliott Wave pattern analysis")
    print("✓ Implemented multi-signal validation")
    print("✓ Created robust target with noise reduction")
    print(f"✓ Achieved overfit ratio of {result['overfit_ratio']:.2f} (lower is better)")
    
    if result['overfit_ratio'] < 1.2:
        print("\n🎯 Model shows good generalization! Ready for live testing.")
    else:
        print("\n⚠️ Model may still overfit. Consider more regularization.")


if __name__ == "__main__":
    main()