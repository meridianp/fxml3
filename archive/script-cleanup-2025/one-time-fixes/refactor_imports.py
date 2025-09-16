#!/usr/bin/env python3
"""
Script to refactor imports from old fxml4.* structure to new fxml4_* monorepo structure.

This script will:
1. Find all Python files with old imports
2. Update imports to use new package names
3. Create a migration report
"""

import os
import re
import json
from pathlib import Path
from typing import Dict, List, Tuple
import argparse
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import mapping from old to new structure
IMPORT_MAPPING = {
    # Core utilities
    'fxml4.config': 'fxml4_core.config',
    'fxml4.utils': 'fxml4_core',
    'fxml4.core': 'fxml4_core',
    
    # ML modules
    'fxml4.ml.models': 'fxml4_ml.models',
    'fxml4.ml.features': 'fxml4_ml.features',
    'fxml4.ml.training': 'fxml4_ml.training',
    'fxml4.ml.validation': 'fxml4_ml.validation',
    'fxml4.ml': 'fxml4_ml',
    
    # Strategy/Signals
    'fxml4.strategy': 'fxml4_signals',
    'fxml4.strategy.signals': 'fxml4_signals.generators',
    'fxml4.strategy.ml_signal_generator': 'fxml4_signals.ml_signals',
    'fxml4.strategy.wave_signal_generator': 'fxml4_signals.technical',
    
    # Data engineering
    'fxml4.data_engineering': 'fxml4_data_collector',
    'fxml4.data_engineering.data_feeds': 'fxml4_data_collector.collectors',
    'fxml4.data_engineering.timescaledb': 'fxml4_data_collector.storage.timescaledb',
    
    # LLM integration
    'fxml4.llm_integration': 'fxml4_llm',
    'fxml4.llm_integration.sentiment_analysis': 'fxml4_llm.sentiment',
    'fxml4.llm_integration.llm_client': 'fxml4_llm.client',
    'fxml4.llm_integration.rag': 'fxml4_llm.market_analyzer',
    
    # API and UI
    'fxml4.api': 'fxml4_web.api',
    'fxml4.api.main': 'fxml4_web.api.main',
    'fxml4.api.auth': 'fxml4_web.api.routers.auth',
    'fxml4.ui': 'fxml4_web.ui',
    
    # Backtesting
    'fxml4.backtesting': 'fxml4_backtesting',
    'fxml4.backtesting.backtest_engine': 'fxml4_backtesting.engine',
    'fxml4.backtesting.events': 'fxml4_backtesting.events',
    'fxml4.backtesting.portfolio': 'fxml4_backtesting.portfolio',
    'fxml4.backtesting.strategy': 'fxml4_backtesting.strategy',
    
    # Wave analysis (needs special handling - no direct package yet)
    'fxml4.wave_analysis': 'fxml4_signals.technical.elliott_wave',
    
    # Worker (needs special handling)
    'fxml4.worker': 'fxml4_trade_manager',
}


def find_python_files(directory: Path, exclude_dirs: List[str] = None) -> List[Path]:
    """Find all Python files in directory, excluding specified directories."""
    exclude_dirs = exclude_dirs or ['venv', '__pycache__', '.git', 'build', 'dist']
    python_files = []
    
    for root, dirs, files in os.walk(directory):
        # Remove excluded directories from search
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        
        for file in files:
            if file.endswith('.py'):
                python_files.append(Path(root) / file)
    
    return python_files


def extract_imports(file_path: Path) -> List[Tuple[str, str, int]]:
    """Extract all fxml4 imports from a file.
    
    Returns list of (import_statement, module_path, line_number)
    """
    imports = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        for i, line in enumerate(lines, 1):
            # Match "from fxml4.xxx import yyy"
            match1 = re.match(r'^\s*from\s+(fxml4(?:\.[a-zA-Z0-9_]+)*)\s+import\s+(.+)', line)
            if match1:
                imports.append((line.strip(), match1.group(1), i))
                continue
                
            # Match "import fxml4.xxx"
            match2 = re.match(r'^\s*import\s+(fxml4(?:\.[a-zA-Z0-9_]+)*)', line)
            if match2:
                imports.append((line.strip(), match2.group(1), i))
                
    except Exception as e:
        logger.error(f"Error reading {file_path}: {e}")
        
    return imports


def update_import(import_line: str, old_module: str) -> str:
    """Update a single import line to use new module structure."""
    # Find the best match for the old module
    new_module = None
    
    # Try exact match first
    if old_module in IMPORT_MAPPING:
        new_module = IMPORT_MAPPING[old_module]
    else:
        # Try prefix match
        for old_prefix, new_prefix in sorted(IMPORT_MAPPING.items(), key=lambda x: len(x[0]), reverse=True):
            if old_module.startswith(old_prefix):
                # Replace the prefix
                new_module = old_module.replace(old_prefix, new_prefix, 1)
                break
    
    if new_module:
        return import_line.replace(old_module, new_module)
    else:
        # No mapping found, log warning
        logger.warning(f"No mapping found for module: {old_module}")
        return import_line


def process_file(file_path: Path, dry_run: bool = True) -> Dict:
    """Process a single file and update imports.
    
    Returns dict with migration details.
    """
    imports = extract_imports(file_path)
    if not imports:
        return None
        
    changes = []
    
    if not dry_run:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        for import_line, old_module, line_num in imports:
            new_line = update_import(import_line, old_module)
            if new_line != import_line:
                changes.append({
                    'line_number': line_num,
                    'old': import_line,
                    'new': new_line
                })
                lines[line_num - 1] = new_line + '\n'
        
        if changes:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)
    else:
        # Dry run - just collect what would change
        for import_line, old_module, line_num in imports:
            new_line = update_import(import_line, old_module)
            if new_line != import_line:
                changes.append({
                    'line_number': line_num,
                    'old': import_line,
                    'new': new_line
                })
    
    if changes:
        return {
            'file': str(file_path),
            'imports_found': len(imports),
            'changes': changes
        }
    
    return None


def main():
    parser = argparse.ArgumentParser(description='Refactor FXML4 imports to new structure')
    parser.add_argument('--directory', type=str, default='.',
                        help='Directory to process (default: current directory)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be changed without modifying files')
    parser.add_argument('--exclude', nargs='+', default=[],
                        help='Additional directories to exclude')
    parser.add_argument('--output', type=str, default='migration_report.json',
                        help='Output file for migration report')
    
    args = parser.parse_args()
    
    # Set up paths
    base_dir = Path(args.directory).resolve()
    exclude_dirs = ['venv', '__pycache__', '.git', 'build', 'dist', 'fxml4-monorepo', 'legacy', 'archive'] + args.exclude
    
    logger.info(f"Processing directory: {base_dir}")
    logger.info(f"Excluding: {exclude_dirs}")
    logger.info(f"Dry run: {args.dry_run}")
    
    # Find all Python files
    python_files = find_python_files(base_dir, exclude_dirs)
    logger.info(f"Found {len(python_files)} Python files")
    
    # Process each file
    results = []
    total_changes = 0
    
    for file_path in python_files:
        result = process_file(file_path, args.dry_run)
        if result:
            results.append(result)
            total_changes += len(result['changes'])
            logger.info(f"Processed {file_path}: {len(result['changes'])} changes")
    
    # Generate report
    report = {
        'summary': {
            'total_files': len(python_files),
            'files_with_imports': len(results),
            'total_changes': total_changes,
            'dry_run': args.dry_run
        },
        'import_mapping': IMPORT_MAPPING,
        'changes': results
    }
    
    # Save report
    with open(args.output, 'w') as f:
        json.dump(report, f, indent=2)
    
    logger.info(f"\nMigration {'preview' if args.dry_run else 'complete'}!")
    logger.info(f"Files processed: {len(python_files)}")
    logger.info(f"Files with FXML4 imports: {len(results)}")
    logger.info(f"Total import changes: {total_changes}")
    logger.info(f"Report saved to: {args.output}")
    
    if args.dry_run:
        logger.info("\nThis was a dry run. To apply changes, run without --dry-run flag")


if __name__ == '__main__':
    main()