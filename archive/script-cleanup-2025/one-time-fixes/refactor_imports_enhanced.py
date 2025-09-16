#!/usr/bin/env python3
"""
Enhanced Import Refactoring Script for FXML4

This script finds and updates Python imports throughout the project to ensure
they work with the new structure. It handles various import patterns and
provides safety features like backups and dry-run mode.

Usage:
    python refactor_imports_enhanced.py [options]

Options:
    --dry-run           Show what would be changed without modifying files
    --no-backup         Skip creating backups (not recommended)
    --verbose           Show detailed progress
    --pattern PATTERN   Additional regex pattern to match imports
    --exclude PATH      Exclude paths matching this pattern
"""

import os
import re
import sys
import shutil
import argparse
import logging
from pathlib import Path
from typing import List, Tuple, Dict, Set, Optional
from datetime import datetime
import json
from collections import defaultdict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ImportRefactorer:
    """Handles the refactoring of Python imports."""
    
    # Common import patterns to detect
    IMPORT_PATTERNS = [
        # from fxml4.module import Something
        re.compile(r'^(\s*)from\s+fxml4\.([a-zA-Z0-9_.]+)\s+import\s+(.+)$', re.MULTILINE),
        # from fxml4 import module
        re.compile(r'^(\s*)from\s+fxml4\s+import\s+(.+)$', re.MULTILINE),
        # import fxml4.module
        re.compile(r'^(\s*)import\s+fxml4\.([a-zA-Z0-9_.]+)$', re.MULTILINE),
        # import fxml4
        re.compile(r'^(\s*)import\s+fxml4$', re.MULTILINE),
        # Multi-line imports with parentheses
        re.compile(r'^(\s*)from\s+fxml4\.([a-zA-Z0-9_.]+)\s+import\s+\(\s*\n([^)]+)\)', re.MULTILINE | re.DOTALL),
        re.compile(r'^(\s*)from\s+fxml4\s+import\s+\(\s*\n([^)]+)\)', re.MULTILINE | re.DOTALL),
    ]
    
    # Directories to focus on
    FOCUS_DIRS = ['scripts', 'tests', 'examples', 'docs']
    
    # Default exclude patterns
    DEFAULT_EXCLUDES = [
        '__pycache__',
        '.git',
        '.venv',
        'venv',
        'env',
        '.pytest_cache',
        '.mypy_cache',
        'build',
        'dist',
        '*.egg-info',
        'archive',
        'legacy',
        'fxml4-monorepo',
        '.backup',
    ]
    
    # Common issues to check for
    IMPORT_ISSUES = {
        'duplicate_imports': 'Multiple imports of the same module',
        'unused_imports': 'Imports that are not used in the file',
        'circular_imports': 'Potential circular import dependencies',
        'deprecated_modules': 'Imports from deprecated modules',
        'missing_init': 'Package directories missing __init__.py',
    }
    
    def __init__(self, root_path: Path, dry_run: bool = False, 
                 create_backups: bool = True, verbose: bool = False):
        self.root_path = root_path
        self.dry_run = dry_run
        self.create_backups = create_backups
        self.verbose = verbose
        self.stats = defaultdict(int)
        self.modified_files: List[Path] = []
        self.backup_dir = root_path / f'.backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
        
    def find_python_files(self, exclude_patterns: Optional[List[str]] = None) -> List[Path]:
        """Find all Python files in the project."""
        exclude_patterns = exclude_patterns or []
        exclude_patterns.extend(self.DEFAULT_EXCLUDES)
        
        python_files = []
        
        # Convert exclude patterns to Path objects for easier matching
        exclude_paths = [self.root_path / pattern for pattern in exclude_patterns]
        
        for focus_dir in self.FOCUS_DIRS:
            dir_path = self.root_path / focus_dir
            if not dir_path.exists():
                logger.warning(f"Directory not found: {dir_path}")
                continue
                
            for file_path in dir_path.rglob('*.py'):
                # Check if file should be excluded
                should_exclude = False
                for exclude in exclude_patterns:
                    if exclude in str(file_path):
                        should_exclude = True
                        break
                        
                if not should_exclude:
                    python_files.append(file_path)
                    self.stats['files_found'] += 1
                    
        # Also check root level Python files
        for file_path in self.root_path.glob('*.py'):
            if file_path.name != 'setup.py' and not any(exclude in str(file_path) for exclude in exclude_patterns):
                python_files.append(file_path)
                self.stats['files_found'] += 1
                
        return python_files
    
    def backup_file(self, file_path: Path) -> Optional[Path]:
        """Create a backup of the file."""
        if not self.create_backups or self.dry_run:
            return None
            
        relative_path = file_path.relative_to(self.root_path)
        backup_path = self.backup_dir / relative_path
        
        # Create backup directory
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            shutil.copy2(file_path, backup_path)
            return backup_path
        except Exception as e:
            logger.error(f"Failed to backup {file_path}: {e}")
            return None
    
    def analyze_import(self, line: str, pattern_match) -> Dict[str, str]:
        """Analyze an import statement and determine how to refactor it."""
        analysis = {
            'original': line,
            'type': None,
            'module': None,
            'imports': None,
            'suggested': None,
            'confidence': 'high'
        }
        
        # Determine import type and extract components
        if 'from fxml4.' in line and 'import' in line:
            analysis['type'] = 'from_module'
            # Extract module and imports
            if hasattr(pattern_match, 'groups'):
                groups = pattern_match.groups()
                if len(groups) >= 3:
                    analysis['module'] = groups[1]
                    analysis['imports'] = groups[2]
                    
        elif 'from fxml4 import' in line:
            analysis['type'] = 'from_package'
            if hasattr(pattern_match, 'groups'):
                groups = pattern_match.groups()
                if len(groups) >= 2:
                    analysis['imports'] = groups[1]
                    
        elif 'import fxml4.' in line:
            analysis['type'] = 'import_module'
            if hasattr(pattern_match, 'groups'):
                groups = pattern_match.groups()
                if len(groups) >= 2:
                    analysis['module'] = groups[1]
                    
        elif line.strip() == 'import fxml4':
            analysis['type'] = 'import_package'
        
        # Generate suggested refactoring
        analysis['suggested'] = self.suggest_refactoring(analysis)
        
        return analysis
    
    def suggest_refactoring(self, analysis: Dict[str, str]) -> str:
        """Suggest how to refactor the import."""
        original = analysis['original']
        
        # Define refactoring rules
        # These are example rules - customize based on your specific needs
        REFACTORING_RULES = {
            # Example: Move elliott_wave to wave_analysis
            'elliott_wave': 'wave_analysis.elliott_wave',
            
            # Example: Rename modules
            # 'old_module': 'new_module',
            
            # Example: Consolidate modules
            # 'module1': 'consolidated_module',
            # 'module2': 'consolidated_module',
        }
        
        # Apply refactoring rules
        refactored = original
        
        if analysis['type'] == 'from_module' and analysis['module']:
            # Check if the module needs refactoring
            module_parts = analysis['module'].split('.')
            if module_parts[0] in REFACTORING_RULES:
                new_module = REFACTORING_RULES[module_parts[0]]
                if len(module_parts) > 1:
                    new_module = new_module + '.' + '.'.join(module_parts[1:])
                
                # Reconstruct the import statement
                indent = re.match(r'^(\s*)', original).group(1)
                refactored = f"{indent}from fxml4.{new_module} import {analysis['imports']}"
                
        elif analysis['type'] == 'import_module' and analysis['module']:
            # Check if the module needs refactoring
            module_parts = analysis['module'].split('.')
            if module_parts[0] in REFACTORING_RULES:
                new_module = REFACTORING_RULES[module_parts[0]]
                if len(module_parts) > 1:
                    new_module = new_module + '.' + '.'.join(module_parts[1:])
                
                # Reconstruct the import statement
                indent = re.match(r'^(\s*)', original).group(1)
                refactored = f"{indent}import fxml4.{new_module}"
        
        # Add more sophisticated rules as needed
        # For example:
        # - Handle aliased imports (import X as Y)
        # - Handle multi-line imports
        # - Handle relative imports that need to become absolute
        # - Check for deprecated modules and suggest alternatives
        
        return refactored
    
    def process_file(self, file_path: Path) -> Tuple[bool, List[Dict[str, str]]]:
        """Process a single Python file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                original_content = content
        except Exception as e:
            logger.error(f"Failed to read {file_path}: {e}")
            self.stats['errors'] += 1
            return False, []
        
        changes = []
        lines = content.split('\n')
        modified_lines = []
        line_modified = False
        
        i = 0
        while i < len(lines):
            line = lines[i]
            matched = False
            
            # Check each import pattern
            for pattern in self.IMPORT_PATTERNS:
                match = pattern.match(line)
                if match:
                    matched = True
                    analysis = self.analyze_import(line, match)
                    
                    # Handle multi-line imports
                    if pattern.flags & re.DOTALL:
                        # This is a multi-line import
                        import_block = [line]
                        i += 1
                        while i < len(lines) and ')' not in lines[i]:
                            import_block.append(lines[i])
                            i += 1
                        if i < len(lines):
                            import_block.append(lines[i])
                        
                        analysis['original'] = '\n'.join(import_block)
                        analysis['type'] = 'multi_line'
                    
                    changes.append(analysis)
                    self.stats['imports_found'] += 1
                    
                    # Apply refactoring if not in dry-run mode
                    if analysis['suggested'] != analysis['original']:
                        line_modified = True
                        modified_lines.append(analysis['suggested'])
                        self.stats['imports_modified'] += 1
                    else:
                        modified_lines.append(line)
                    
                    break
            
            if not matched:
                modified_lines.append(line)
            
            i += 1
        
        # Write changes if file was modified and not in dry-run mode
        if line_modified and not self.dry_run:
            # Create backup
            backup_path = self.backup_file(file_path)
            if backup_path:
                logger.debug(f"Backed up {file_path} to {backup_path}")
            
            # Write modified content
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(modified_lines))
                self.modified_files.append(file_path)
                self.stats['files_modified'] += 1
            except Exception as e:
                logger.error(f"Failed to write {file_path}: {e}")
                self.stats['errors'] += 1
                return False, changes
        
        return line_modified, changes
    
    def generate_report(self) -> Dict[str, any]:
        """Generate a detailed report of the refactoring process."""
        report = {
            'timestamp': datetime.now().isoformat(),
            'dry_run': self.dry_run,
            'statistics': dict(self.stats),
            'modified_files': [str(f) for f in self.modified_files],
            'backup_directory': str(self.backup_dir) if self.create_backups else None,
        }
        
        return report
    
    def run(self, exclude_patterns: Optional[List[str]] = None) -> Dict[str, any]:
        """Run the import refactoring process."""
        logger.info(f"Starting import refactoring in {self.root_path}")
        if self.dry_run:
            logger.info("DRY RUN MODE - No files will be modified")
        
        # Find Python files
        python_files = self.find_python_files(exclude_patterns)
        logger.info(f"Found {len(python_files)} Python files to process")
        
        # Process each file
        all_changes = {}
        for i, file_path in enumerate(python_files, 1):
            if self.verbose:
                logger.info(f"Processing [{i}/{len(python_files)}]: {file_path}")
            
            modified, changes = self.process_file(file_path)
            
            if changes:
                all_changes[str(file_path)] = changes
                
            # Show progress every 10 files
            if i % 10 == 0 and not self.verbose:
                logger.info(f"Progress: {i}/{len(python_files)} files processed")
        
        # Generate and save report
        report = self.generate_report()
        report['changes'] = all_changes
        
        # Save report
        report_path = self.root_path / f'import_refactoring_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        try:
            with open(report_path, 'w') as f:
                json.dump(report, f, indent=2)
            logger.info(f"Report saved to: {report_path}")
        except Exception as e:
            logger.error(f"Failed to save report: {e}")
        
        # Print summary
        self.print_summary()
        
        return report
    
    def detect_import_issues(self, file_path: Path, imports: List[Dict[str, str]]) -> List[str]:
        """Detect common import issues in a file."""
        issues = []
        
        # Check for duplicate imports
        import_lines = [imp['original'].strip() for imp in imports]
        if len(import_lines) != len(set(import_lines)):
            issues.append('duplicate_imports')
            
        # Check for potential circular imports (basic check)
        # This would need more sophisticated analysis in practice
        file_module = file_path.stem
        for imp in imports:
            if imp['module'] and file_module in imp['module']:
                issues.append('potential_circular_import')
                break
                
        return issues
    
    def print_summary(self):
        """Print a summary of the refactoring process."""
        print("\n" + "="*60)
        print("IMPORT REFACTORING SUMMARY")
        print("="*60)
        print(f"Files found:        {self.stats['files_found']}")
        print(f"Files modified:     {self.stats['files_modified']}")
        print(f"Imports found:      {self.stats['imports_found']}")
        print(f"Imports modified:   {self.stats['imports_modified']}")
        print(f"Errors:             {self.stats['errors']}")
        
        if self.dry_run:
            print("\nDRY RUN - No files were actually modified")
        
        if self.create_backups and not self.dry_run and self.stats['files_modified'] > 0:
            print(f"\nBackups created in: {self.backup_dir}")
        
        print("="*60 + "\n")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Refactor Python imports in the FXML4 project',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be changed without modifying files'
    )
    
    parser.add_argument(
        '--no-backup',
        action='store_true',
        help='Skip creating backups (not recommended)'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Show detailed progress'
    )
    
    parser.add_argument(
        '--exclude',
        action='append',
        dest='exclude_patterns',
        help='Exclude paths matching this pattern (can be used multiple times)'
    )
    
    parser.add_argument(
        '--root',
        type=str,
        default='.',
        help='Root directory of the project (default: current directory)'
    )
    
    args = parser.parse_args()
    
    # Set up logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Determine root path
    root_path = Path(args.root).resolve()
    if not root_path.exists():
        logger.error(f"Root path does not exist: {root_path}")
        sys.exit(1)
    
    # Create refactorer instance
    refactorer = ImportRefactorer(
        root_path=root_path,
        dry_run=args.dry_run,
        create_backups=not args.no_backup,
        verbose=args.verbose
    )
    
    # Run refactoring
    try:
        report = refactorer.run(exclude_patterns=args.exclude_patterns)
        
        # Exit with appropriate code
        if refactorer.stats['errors'] > 0:
            sys.exit(1)
        else:
            sys.exit(0)
            
    except KeyboardInterrupt:
        logger.info("\nRefactoring interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()