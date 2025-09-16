#!/usr/bin/env python3
"""
Script to identify which fxml4 modules are missing from the main directory
but exist in the legacy directory.
"""

import os
from pathlib import Path
import json

def find_python_modules(directory: Path) -> set:
    """Find all Python modules (directories with __init__.py) in a directory."""
    modules = set()
    
    for root, dirs, files in os.walk(directory):
        # Skip __pycache__ directories
        dirs[:] = [d for d in dirs if d != '__pycache__']
        
        # Check if this directory is a Python module
        if '__init__.py' in files:
            # Calculate relative path from base directory
            rel_path = Path(root).relative_to(directory)
            if str(rel_path) != '.':
                modules.add(str(rel_path).replace('/', '.'))
    
    return modules

def find_module_files(directory: Path) -> dict:
    """Find all Python files in each module."""
    module_files = {}
    
    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if d != '__pycache__']
        
        for file in files:
            if file.endswith('.py') and file != '__init__.py':
                rel_path = Path(root).relative_to(directory)
                module_path = str(rel_path).replace('/', '.')
                
                if module_path not in module_files:
                    module_files[module_path] = []
                module_files[module_path].append(file[:-3])  # Remove .py extension
    
    return module_files

def main():
    # Define paths
    main_fxml4 = Path('/home/cnross/code/fxml4/fxml4')
    legacy_fxml4 = Path('/home/cnross/code/fxml4/fxml4-monorepo/legacy/fxml4')
    old_ml = Path('/home/cnross/code/fxml4/ml')
    
    print("🔍 Analyzing FXML4 module structure...")
    print("=" * 60)
    
    # Find modules in each location
    main_modules = find_python_modules(main_fxml4)
    legacy_modules = find_python_modules(legacy_fxml4)
    
    # Find module files
    main_files = find_module_files(main_fxml4)
    legacy_files = find_module_files(legacy_fxml4)
    
    # Find what's missing in main
    missing_modules = legacy_modules - main_modules
    
    print(f"\n📦 Modules in main fxml4: {len(main_modules)}")
    for mod in sorted(main_modules):
        print(f"  ✓ {mod}")
    
    print(f"\n📦 Modules in legacy fxml4: {len(legacy_modules)}")
    
    print(f"\n❌ Missing modules in main fxml4: {len(missing_modules)}")
    for mod in sorted(missing_modules):
        print(f"  - {mod}")
        # Show what files are in this module
        if mod in legacy_files:
            for file in sorted(legacy_files[mod]):
                print(f"    • {file}.py")
    
    # Check for modules that exist but might be incomplete
    print("\n🔄 Modules that exist in both (check for completeness):")
    common_modules = main_modules & legacy_modules
    for mod in sorted(common_modules):
        main_mod_files = set(main_files.get(mod, []))
        legacy_mod_files = set(legacy_files.get(mod, []))
        missing_files = legacy_mod_files - main_mod_files
        
        if missing_files:
            print(f"\n  {mod}:")
            print(f"    Main has: {len(main_mod_files)} files")
            print(f"    Legacy has: {len(legacy_mod_files)} files")
            print(f"    Missing files:")
            for file in sorted(missing_files):
                print(f"      - {file}.py")
    
    # Check old ml directory
    if old_ml.exists():
        print("\n📁 Old /ml directory exists:")
        ml_files = list(old_ml.glob('*.py'))
        print(f"  Contains {len(ml_files)} Python files")
        for file in sorted(ml_files):
            print(f"    • {file.name}")
    
    # Generate migration plan
    migration_plan = {
        'missing_modules': sorted(missing_modules),
        'incomplete_modules': {},
        'old_ml_files': []
    }
    
    for mod in sorted(common_modules):
        main_mod_files = set(main_files.get(mod, []))
        legacy_mod_files = set(legacy_files.get(mod, []))
        missing_files = legacy_mod_files - main_mod_files
        
        if missing_files:
            migration_plan['incomplete_modules'][mod] = sorted(missing_files)
    
    if old_ml.exists():
        migration_plan['old_ml_files'] = [f.name for f in sorted(old_ml.glob('*.py'))]
    
    # Save migration plan
    with open('module_migration_plan.json', 'w') as f:
        json.dump(migration_plan, f, indent=2)
    
    print(f"\n💾 Migration plan saved to module_migration_plan.json")
    
    # Summary
    print("\n📊 Summary:")
    print(f"  - Main fxml4 has {len(main_modules)} modules")
    print(f"  - Legacy fxml4 has {len(legacy_modules)} modules")
    print(f"  - Missing modules: {len(missing_modules)}")
    print(f"  - Modules to check: {len([m for m in migration_plan['incomplete_modules'] if migration_plan['incomplete_modules'][m]])}")

if __name__ == '__main__':
    main()