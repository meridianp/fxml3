#!/usr/bin/env python
"""Retrain EURUSD and GBPUSD models to fix their issues."""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
import os
from scripts.train_4hour_models import FourHourModelTrainer

def main():
    """Retrain problem symbols with better configuration."""
    
    # Symbols to retrain
    problem_symbols = ['EURUSD', 'GBPUSD']
    
    print("="*80)
    print("RETRAINING PROBLEM SYMBOLS")
    print("="*80)
    print("Issues to fix:")
    print("- EURUSD: Low signal generation (5% vs 85%+ for others)")
    print("- GBPUSD: Low win rate (40% vs 52%+ for others)")
    print("="*80)
    
    for symbol in problem_symbols:
        print(f"\n\nRetraining {symbol}...")
        print("-"*60)
        
        try:
            # Create trainer
            trainer = FourHourModelTrainer(symbol)
            
            # Load data
            df = trainer.load_prepared_data()
            
            # Check current target distribution
            print(f"\nTarget distribution for {symbol}:")
            print(f"  Mean: {df['target'].mean():.6f}")
            print(f"  Std: {df['target'].std():.6f}")
            print(f"  Skewness: {df['target'].skew():.3f}")
            
            # For EURUSD, we need to adjust the target scaling
            if symbol == 'EURUSD':
                # EURUSD predictions are too small, let's check if we can rescale
                print("\nAdjusting EURUSD target scaling...")
                
                # Normalize target to have similar scale as other symbols
                target_std = df['target'].std()
                desired_std = 0.002  # Similar to other symbols
                
                if target_std < desired_std * 0.5:
                    scale_factor = desired_std / target_std
                    df['target'] = df['target'] * scale_factor
                    print(f"  Scaled target by {scale_factor:.2f}x")
                    print(f"  New std: {df['target'].std():.6f}")
            
            # Train models
            results = trainer.train_models(df)
            
            # Save models
            trainer.save_models(results)
            
            print(f"\n✅ Successfully retrained {symbol}")
            
        except Exception as e:
            print(f"\n❌ Error retraining {symbol}: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "="*80)
    print("RETRAINING COMPLETE")
    print("="*80)
    print("\nNext steps:")
    print("1. Run the optimized backtest again to see improvements")
    print("2. Monitor signal generation rates")
    print("3. Check win rates for both symbols")


if __name__ == "__main__":
    main()