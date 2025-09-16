#!/usr/bin/env python3
"""Script to migrate legacy code to the new monorepo structure."""

import os
import shutil
from pathlib import Path
import argparse
import json


def create_mapping():
    """Create mapping of old paths to new locations."""
    return {
        # Core utilities
        "fxml4/utils": "packages/core/src/fxml4_core/utils",
        "fxml4/config.py": "packages/core/src/fxml4_core/config.py",
        
        # Data engineering
        "fxml4/data_engineering": "packages/data-collector/src/fxml4_data_collector",
        "fxml4/data": "libs/database/src/fxml4_database/models",
        
        # ML components
        "fxml4/ml": "packages/ml-models/src/fxml4_ml",
        "fxml4/features": "packages/ml-models/src/fxml4_ml/features",
        
        # Trading strategy
        "fxml4/strategy": "packages/signal-generator/src/fxml4_signals",
        "fxml4/backtesting": "packages/backtesting/src/fxml4_backtesting",
        
        # LLM integration
        "fxml4/llm_integration": "packages/llm-analyzer/src/fxml4_llm",
        "fxml3/llm": "packages/llm-analyzer/src/fxml4_llm/legacy",
        
        # API
        "fxml4/api": "packages/web-ui/src/fxml4_web/api",
        "fxml4/ui": "packages/web-ui/src/fxml4_web/ui",
        
        # Scripts
        "scripts": "scripts/legacy",
        
        # Tests
        "tests": "tests/legacy",
    }


def migrate_file(src_path: Path, dest_path: Path, dry_run: bool = True):
    """Migrate a single file."""
    if dry_run:
        print(f"Would copy: {src_path} -> {dest_path}")
    else:
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_path, dest_path)
        print(f"Copied: {src_path} -> {dest_path}")


def update_imports(file_path: Path, import_mapping: dict):
    """Update import statements in Python files."""
    if file_path.suffix != '.py':
        return
        
    content = file_path.read_text()
    updated = content
    
    for old_import, new_import in import_mapping.items():
        updated = updated.replace(f"from {old_import}", f"from {new_import}")
        updated = updated.replace(f"import {old_import}", f"import {new_import}")
    
    if updated != content:
        file_path.write_text(updated)
        print(f"Updated imports in: {file_path}")


def generate_import_mapping():
    """Generate mapping for import statement updates."""
    return {
        "fxml4.utils": "fxml4_core.utils",
        "fxml4.config": "fxml4_core.config",
        "fxml4.data_engineering": "fxml4_data_collector",
        "fxml4.ml": "fxml4_ml",
        "fxml4.strategy": "fxml4_signals",
        "fxml4.backtesting": "fxml4_backtesting",
        "fxml4.llm_integration": "fxml4_llm",
        "fxml4.api": "fxml4_web.api",
    }


def main():
    parser = argparse.ArgumentParser(description="Migrate legacy code to monorepo")
    parser.add_argument("--source", default="../", help="Source directory")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    parser.add_argument("--update-imports", action="store_true", help="Update import statements")
    
    args = parser.parse_args()
    
    source_root = Path(args.source).resolve()
    dest_root = Path(".").resolve()
    
    mapping = create_mapping()
    import_mapping = generate_import_mapping()
    
    # Track migration
    migration_log = {
        "files_migrated": [],
        "files_skipped": [],
        "errors": []
    }
    
    for old_path, new_path in mapping.items():
        src = source_root / old_path
        dest = dest_root / new_path
        
        if not src.exists():
            migration_log["files_skipped"].append(str(src))
            continue
            
        try:
            if src.is_file():
                migrate_file(src, dest, args.dry_run)
                migration_log["files_migrated"].append(str(src))
                
                if args.update_imports and not args.dry_run:
                    update_imports(dest, import_mapping)
                    
            elif src.is_dir():
                for file_path in src.rglob("*.py"):
                    relative = file_path.relative_to(src)
                    dest_file = dest / relative
                    migrate_file(file_path, dest_file, args.dry_run)
                    migration_log["files_migrated"].append(str(file_path))
                    
                    if args.update_imports and not args.dry_run:
                        update_imports(dest_file, import_mapping)
                        
        except Exception as e:
            migration_log["errors"].append({
                "file": str(src),
                "error": str(e)
            })
    
    # Save migration log
    log_path = dest_root / "migration_log.json"
    with open(log_path, "w") as f:
        json.dump(migration_log, f, indent=2)
    
    print(f"\nMigration complete!")
    print(f"Files migrated: {len(migration_log['files_migrated'])}")
    print(f"Files skipped: {len(migration_log['files_skipped'])}")
    print(f"Errors: {len(migration_log['errors'])}")
    print(f"Log saved to: {log_path}")


if __name__ == "__main__":
    main()