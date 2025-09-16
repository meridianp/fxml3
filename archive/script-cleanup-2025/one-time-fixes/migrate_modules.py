#!/usr/bin/env python3
"""
Module Migration Script for FXML4

This script migrates modules from the legacy structure to the main package structure.
"""

import os
import shutil
from pathlib import Path
from typing import List, Tuple
import argparse


class ModuleMigrator:
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.project_root = Path(__file__).parent.parent
        self.legacy_path = self.project_root / "fxml4-monorepo" / "legacy" / "fxml4"
        self.target_path = self.project_root / "fxml4"
        self.migrations = []
        
    def get_modules_to_migrate(self) -> List[Tuple[str, Path, Path]]:
        """Get list of modules that need migration."""
        modules = [
            # (module_name, source_path, target_path)
            ("ml", self.legacy_path / "ml", self.target_path / "ml"),
            ("data_engineering", self.legacy_path / "data_engineering", self.target_path / "data_engineering"),
            ("wave_analysis", self.legacy_path / "wave_analysis", self.target_path / "wave_analysis"),
            ("api", self.legacy_path / "api", self.target_path / "api"),
            ("signal_generation", self.legacy_path / "signal_generation", self.target_path / "signal_generation"),
            ("core", self.legacy_path / "core", self.target_path / "core"),
            ("strategies", self.legacy_path / "strategies", self.target_path / "strategies"),
            ("utils", self.legacy_path / "utils", self.target_path / "utils"),
            ("data", self.legacy_path / "data", self.target_path / "data"),
            ("llm_integration", self.legacy_path / "llm_integration", self.target_path / "llm_integration"),
            ("production", self.legacy_path / "production", self.target_path / "production"),
            ("ui", self.legacy_path / "ui", self.target_path / "ui"),
            ("worker", self.legacy_path / "worker", self.target_path / "worker"),
        ]
        
        # Check which modules exist and need migration
        migrations_needed = []
        for module_name, source, target in modules:
            if source.exists() and not target.exists():
                migrations_needed.append((module_name, source, target))
        
        return migrations_needed
    
    def migrate_module(self, module_name: str, source: Path, target: Path) -> bool:
        """Migrate a single module."""
        try:
            if self.dry_run:
                print(f"[DRY RUN] Would copy: {source} -> {target}")
                return True
            
            # Create parent directory if needed
            target.parent.mkdir(parents=True, exist_ok=True)
            
            # Copy the module
            if source.is_dir():
                shutil.copytree(source, target, dirs_exist_ok=False)
                print(f"✅ Copied directory: {module_name}")
            else:
                shutil.copy2(source, target)
                print(f"✅ Copied file: {module_name}")
            
            self.migrations.append((module_name, source, target))
            return True
            
        except Exception as e:
            print(f"❌ Failed to migrate {module_name}: {e}")
            return False
    
    def ensure_init_files(self):
        """Ensure __init__.py exists in all directories."""
        for root, dirs, files in os.walk(self.target_path):
            if '__init__.py' not in files and not root.endswith('__pycache__'):
                init_path = Path(root) / '__init__.py'
                if not self.dry_run:
                    init_path.write_text('"""Package initialization."""\n')
                    print(f"✅ Created __init__.py in {root}")
                else:
                    print(f"[DRY RUN] Would create __init__.py in {root}")
    
    def create_root_init(self):
        """Create root __init__.py with proper exports."""
        init_content = '''"""
FXML4 - Advanced Forex Trading Platform

This package provides comprehensive forex trading capabilities including:
- Machine Learning models for price prediction
- Elliott Wave analysis
- Backtesting framework
- Real-time data collection
- Signal generation
- Risk management
"""

__version__ = "0.1.0"

# Import main components for easier access
from . import (
    backtesting,
    ml,
    data_engineering,
    wave_analysis,
    signal_generation,
    core,
    strategies,
    utils
)

__all__ = [
    'backtesting',
    'ml',
    'data_engineering',
    'wave_analysis',
    'signal_generation',
    'core',
    'strategies',
    'utils'
]
'''
        
        init_path = self.target_path / "__init__.py"
        if not init_path.exists():
            if not self.dry_run:
                init_path.write_text(init_content)
                print("✅ Created root __init__.py")
            else:
                print("[DRY RUN] Would create root __init__.py")
    
    def run(self):
        """Run the migration process."""
        print("🚀 Starting FXML4 Module Migration")
        print(f"{'='*60}")
        print(f"Legacy path: {self.legacy_path}")
        print(f"Target path: {self.target_path}")
        print(f"Dry run: {self.dry_run}")
        print(f"{'='*60}\n")
        
        # Get modules to migrate
        modules_to_migrate = self.get_modules_to_migrate()
        
        if not modules_to_migrate:
            print("✅ No modules need migration - all modules already exist!")
            return
        
        print(f"Found {len(modules_to_migrate)} modules to migrate:\n")
        for module_name, source, target in modules_to_migrate:
            print(f"  • {module_name}: {source.relative_to(self.project_root)}")
        
        print(f"\n{'='*60}")
        print("Starting migration...\n")
        
        # Migrate each module
        success_count = 0
        for module_name, source, target in modules_to_migrate:
            if self.migrate_module(module_name, source, target):
                success_count += 1
        
        # Create __init__.py files
        print(f"\n{'='*60}")
        print("Creating __init__.py files...\n")
        self.ensure_init_files()
        self.create_root_init()
        
        # Summary
        print(f"\n{'='*60}")
        print("Migration Summary:")
        print(f"  • Total modules: {len(modules_to_migrate)}")
        print(f"  • Successfully migrated: {success_count}")
        print(f"  • Failed: {len(modules_to_migrate) - success_count}")
        
        if not self.dry_run and success_count > 0:
            print(f"\n✅ Migration complete! Created {success_count} modules in {self.target_path}")
            print("\nNext steps:")
            print("1. Run 'python scripts/refactor_imports_enhanced.py' to fix imports")
            print("2. Run tests to verify everything works")
        

def main():
    parser = argparse.ArgumentParser(description="Migrate FXML4 modules from legacy to main structure")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without making changes")
    args = parser.parse_args()
    
    migrator = ModuleMigrator(dry_run=args.dry_run)
    migrator.run()


if __name__ == "__main__":
    main()