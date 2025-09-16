#!/usr/bin/env python3

"""
Fix Signal Generator Registry
Connects signal generators to model registry for proper loading
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fxml4.api.services.market_data import get_connection_pool
from fxml4.ml.model_registry import ModelRegistry

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def fix_signal_generator_registry():
    """Register the created signal generators in the model registry."""

    # Database connection
    pool = await get_connection_pool()
    registry = ModelRegistry(pool)

    # Signal generator mappings
    signal_generators = {
        "EURUSD": {
            "model_path": "/home/cnross/code/fxml4/models/EURUSD/xgboost_model_20250618_124701.joblib",
            "model_type": "xgboost",
            "version": "20250618_124701",
        },
        "GBPUSD": {
            "model_path": "/home/cnross/code/fxml4/models/GBPUSD/best_model_lightgbm.joblib",
            "model_type": "lightgbm",
            "version": "best_model",
        },
        "USDJPY": {
            "model_path": "/home/cnross/code/fxml4/models/USDJPY/rf_model_20250618_220826.joblib",
            "model_type": "random_forest",
            "version": "20250618_220826",
        },
        "USDCHF": {
            "model_path": "/home/cnross/code/fxml4/models/USDCHF/xgboost_model_20250618_223620.joblib",
            "model_type": "xgboost",
            "version": "20250618_223620",
        },
    }

    try:
        for symbol, info in signal_generators.items():
            try:
                # Check if model file exists
                if not Path(info["model_path"]).exists():
                    logger.warning(
                        f"Model file not found for {symbol}: {info['model_path']}"
                    )
                    continue

                # Register model in the registry
                await registry.register_model(
                    name=symbol,
                    model_type=info["model_type"],
                    version=info["version"],
                    symbol=symbol,
                    timeframe="1h",  # Default timeframe
                    metadata={
                        "signal_generator": True,
                        "file_path": info["model_path"],
                        "status": "active",
                    },
                    file_path=info["model_path"],
                )

                logger.info(
                    f"✅ Registered {symbol} signal generator in model registry"
                )

            except Exception as e:
                logger.error(f"❌ Failed to register {symbol}: {e}")

        # Verify registrations
        models = await registry.list_models()
        active_models = [
            m for m in models if m.get("symbol") in signal_generators.keys()
        ]

        logger.info(f"📊 Model Registry Status:")
        logger.info(f"   Total models: {len(models)}")
        logger.info(f"   Signal generator models: {len(active_models)}")

        for model in active_models:
            logger.info(
                f"   - {model['symbol']}: {model['model_type']} v{model['version']}"
            )

    except Exception as e:
        logger.error(f"Error fixing signal generator registry: {e}")
        return False

    finally:
        await pool.close()

    return True


if __name__ == "__main__":
    success = asyncio.run(fix_signal_generator_registry())
    if success:
        print("\n🎯 Signal Generator Registry Fixed Successfully!")
        print(
            "Signal generators are now properly registered and should load correctly."
        )
    else:
        print("\n❌ Failed to fix signal generator registry")
        sys.exit(1)
