#!/usr/bin/env python3
"""
Migration script for ML models decomposition.

This script helps migrate from the old monolithic models.py to the new
modular structure.
"""

import os
import shutil
from pathlib import Path


def migrate_models():
    """Migrate the models module to new structure."""

    # Backup original file
    original_file = Path("fxml4/ml/models.py")
    backup_file = Path("fxml4/ml/models.py.backup")

    if original_file.exists():
        shutil.copy2(original_file, backup_file)
        print(f"✅ Backed up original file to {backup_file}")

    # The new structure is already created, so we just need to update imports
    print("✅ New modular structure created:")
    print("   - fxml4/ml/models/base.py")
    print("   - fxml4/ml/models/classic.py")
    print("   - fxml4/ml/models/ensemble.py")
    print("   - fxml4/ml/models/utils.py")
    print("   - fxml4/ml/models/constants.py")
    print("   - fxml4/ml/models/__init__.py")

    # Test imports
    try:
        from fxml4.ml.models import (
            ClassicMLModel,
            EnsembleModel,
            MLModelBase,
            compare_models,
            create_ensemble,
            create_model,
        )

        print("✅ New imports working correctly")

        # Test basic functionality
        model = create_model("random_forest", name="test_model")
        print(f"✅ Model creation working: {model.name}")

        return True

    except Exception as e:
        print(f"❌ Import test failed: {e}")
        return False


if __name__ == "__main__":
    print("🔄 Starting ML models migration...")
    success = migrate_models()

    if success:
        print("\n🎉 Migration completed successfully!")
        print("\nTo complete the migration:")
        print("1. Update any imports from 'fxml4.ml.models' to use new structure")
        print("2. Test your existing code with the new modular structure")
        print("3. Remove the backup file when confident everything works")
    else:
        print("\n❌ Migration failed. Please check the errors above.")
