#!/usr/bin/env python3
"""Test critical imports after refactoring."""

import sys
import traceback

# Test imports
test_imports = [
    ("Config", "from fxml4.config import get_config"),
    ("Base Strategy", "from fxml4.strategy.base_strategy import BaseStrategy"),
    ("Risk Manager", "from fxml4.risk_management import RiskManager"),
    ("Data Loader", "from fxml4.data.data_loader import DataLoader"),
    ("Model Loader", "from fxml4.ml.model_loader import ModelLoader"),
    (
        "Elliott Wave Analyzer",
        "from fxml4.wave_analysis.elliott_wave_analyzer import ElliottWaveAnalyzer",
    ),
    ("Backtesting Engine", "from fxml4.backtesting.engine import BacktestEngine"),
    (
        "Data Aggregator",
        "from fxml4.data_engineering.data_aggregator import DataAggregator",
    ),
    ("Main", "import fxml4.main"),
]

successful = []
failed = []

print("🧪 Testing FXML4 imports after refactoring...\n")

for name, import_stmt in test_imports:
    try:
        exec(import_stmt)
        successful.append(name)
        print(f"✅ {name}")
    except Exception as e:
        failed.append((name, str(e)))
        print(f"❌ {name}: {type(e).__name__}")

print(f"\n📊 Summary:")
print(f"  ✅ Successful: {len(successful)}/{len(test_imports)}")
print(f"  ❌ Failed: {len(failed)}/{len(test_imports)}")

if failed:
    print(f"\n❌ Failed imports details:")
    for name, error in failed:
        print(f"\n  {name}:")
        print(f"    {error}")

if len(successful) == len(test_imports):
    print("\n🎉 All imports successful! The refactoring is complete.")
    sys.exit(0)
else:
    sys.exit(1)
