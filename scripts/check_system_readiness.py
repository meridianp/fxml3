#!/usr/bin/env python
"""Check if the integrated system is ready for training."""

import importlib.util
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def check_data():
    """Check if we have sufficient data."""
    print("Checking data availability...")

    data_dir = Path("/polygon/processed")
    symbols = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF"]

    data_status = {}
    for symbol in symbols:
        # Data is stored with C_ prefix
        symbol_dir = data_dir / f"C_{symbol}"
        if symbol_dir.exists():
            parquet_files = list(symbol_dir.glob("**/*.parquet*"))
            data_status[symbol] = len(parquet_files)
            print(f"  ✅ {symbol}: {len(parquet_files)} files")
        else:
            data_status[symbol] = 0
            print(f"  ❌ {symbol}: No data")

    return all(count > 0 for count in data_status.values())


def check_dependencies():
    """Check if all required packages are installed."""
    print("\nChecking dependencies...")

    required_packages = {
        "pandas": "pandas",
        "numpy": "numpy",
        "scikit-learn": "sklearn",
        "xgboost": "xgboost",
        "lightgbm": "lightgbm",
        "tensorflow": "tensorflow",
        "alpha_vantage": "alpha_vantage",
        "fredapi": "fredapi",
        "matplotlib": "matplotlib",
        "seaborn": "seaborn",
        "scipy": "scipy",
        "statsmodels": "statsmodels",
    }

    all_installed = True
    for name, module in required_packages.items():
        spec = importlib.util.find_spec(module)
        if spec is not None:
            print(f"  ✅ {name}")
        else:
            print(f"  ❌ {name} - Run: pip install {name}")
            all_installed = False

    return all_installed


def check_api_keys():
    """Check if API keys are configured."""
    print("\nChecking API keys...")

    api_keys = {
        "POLYGON_API_KEY": "Polygon.io",
        "ALPHA_VANTAGE_API_KEY": "Alpha Vantage",
        "FRED_API_KEY": "FRED (Federal Reserve)",
    }

    all_keys = True
    for key, service in api_keys.items():
        if os.getenv(key):
            print(f"  ✅ {service}: {key} found")
        else:
            print(f"  ⚠️  {service}: {key} not in environment")
            all_keys = False

    return all_keys


def check_directories():
    """Check if necessary directories exist."""
    print("\nChecking directories...")

    dirs = ["models", "output", "logs", "/polygon/processed"]

    for dir_path in dirs:
        path = Path(dir_path)
        if path.exists():
            print(f"  ✅ {dir_path}")
        else:
            print(f"  ❌ {dir_path} - Creating...")
            path.mkdir(parents=True, exist_ok=True)


def estimate_training_time():
    """Estimate training time based on data size."""
    print("\nEstimating training time...")

    # Count total data files
    data_dir = Path("/polygon/processed")
    total_files = sum(
        len(list(data_dir.glob(f"C_{symbol}/**/*.parquet*")))
        for symbol in ["EURUSD", "GBPUSD", "USDJPY", "USDCHF"]
    )

    # Rough estimates
    time_per_symbol = 10  # minutes
    total_time = len(["EURUSD", "GBPUSD", "USDJPY", "USDCHF"]) * time_per_symbol

    print(f"  Data files: {total_files}")
    print(f"  Estimated time: {total_time}-{total_time*2} minutes")
    print(f"  Note: Actual time depends on CPU/GPU and data size")


def main():
    """Run all checks."""
    print("=" * 70)
    print("INTEGRATED FOREX SYSTEM READINESS CHECK")
    print("=" * 70)

    # Run checks
    data_ok = check_data()
    deps_ok = check_dependencies()
    keys_ok = check_api_keys()
    check_directories()
    estimate_training_time()

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    if data_ok and deps_ok:
        print("✅ System is READY for training!")
        print("\nTo start training, run:")
        print("  ./scripts/launch_integrated_training.sh")
        print("\nOr directly:")
        print("  ./venv/bin/python scripts/train_integrated_system.py")
    else:
        print("❌ System is NOT ready. Please fix the issues above.")

        if not data_ok:
            print("\nTo download data:")
            print("  python scripts/download_10year_forex_data.py")

        if not deps_ok:
            print("\nTo install dependencies:")
            print("  pip install -r requirements.txt")
            print("  bash scripts/setup_correlation_analysis.sh")

    if not keys_ok:
        print("\n⚠️  Note: Missing API keys will limit correlation analysis features")


if __name__ == "__main__":
    main()
