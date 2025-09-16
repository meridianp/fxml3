#!/usr/bin/env python3
"""
Migration script to move components from traditional structure to monorepo packages.
"""

import os
import shutil
import ast
import re
from pathlib import Path
from typing import Dict, List, Set, Optional, Tuple
import click
import json


class ImportTransformer(ast.NodeTransformer):
    """Transform imports from old structure to new package structure."""
    
    def __init__(self, import_mappings: Dict[str, str]):
        self.import_mappings = import_mappings
        self.modified = False
        
    def visit_Import(self, node):
        for alias in node.names:
            if alias.name in self.import_mappings:
                alias.name = self.import_mappings[alias.name]
                self.modified = True
        return node
        
    def visit_ImportFrom(self, node):
        if node.module and node.module in self.import_mappings:
            node.module = self.import_mappings[node.module]
            self.modified = True
        elif node.module:
            # Check for partial matches
            for old_import, new_import in self.import_mappings.items():
                if node.module.startswith(old_import + '.'):
                    node.module = node.module.replace(old_import, new_import, 1)
                    self.modified = True
                    break
        return node


class PackageMigrator:
    """Migrate components to monorepo package structure."""
    
    # Standard import mappings
    IMPORT_MAPPINGS = {
        'fxml4.utils': 'fxml4_core',
        'fxml4.config': 'fxml4_core.config',
        'fxml4.utils.logging': 'fxml4_core.logging',
        'fxml4.ml': 'fxml4_ml',
        'fxml4.ml.models': 'fxml4_ml.models',
        'fxml4.ml.features': 'fxml4_ml.features',
        'fxml4.strategy': 'fxml4_signals',
        'fxml4.signals': 'fxml4_signals',
        'fxml4.api': 'fxml4_api',
        'fxml4.data': 'fxml4_data_collector',
        'fxml4.backtesting': 'fxml4_backtesting',
        'fxml4.llm_integration': 'fxml4_llm',
        'fxml4.wave_analysis': 'fxml4_wave',
        'fxml4.features': 'fxml4_data_processor.features',
        'fxml4.data_engineering': 'fxml4_data_processor',
        'fxml4.visualization': 'fxml4_web.visualization',
        'fxml4.ui': 'fxml4_web.ui',
    }
    
    # Package configurations
    PACKAGE_CONFIGS = {
        'data-processor': {
            'description': 'Data processing and feature engineering for FXML4',
            'dependencies': ['fxml4-core', 'fxml4-data-collector'],
            'source_dirs': ['fxml4/features', 'fxml4/data_engineering'],
            'namespace': 'fxml4_data_processor'
        },
        'wave-analyzer': {
            'description': 'Elliott Wave analysis for FXML4',
            'dependencies': ['fxml4-core'],
            'source_dirs': ['fxml4/wave_analysis'],
            'namespace': 'fxml4_wave'
        },
        'risk-manager': {
            'description': 'Risk management service for FXML4',
            'dependencies': ['fxml4-core', 'fxml4-trade-manager'],
            'source_dirs': ['fxml4/risk_management'],
            'namespace': 'fxml4_risk'
        },
        'api-gateway': {
            'description': 'API gateway for FXML4',
            'dependencies': ['fxml4-core', 'fxml4-trade-manager', 'fxml4-signal-generator'],
            'source_dirs': ['fxml4/api'],
            'namespace': 'fxml4_api'
        },
        'web-dashboard': {
            'description': 'Web dashboard for FXML4',
            'dependencies': ['fxml4-api-gateway'],
            'source_dirs': ['fxml4/ui', 'fxml4/visualization'],
            'namespace': 'fxml4_web'
        },
        'worker-services': {
            'description': 'Background worker services for FXML4',
            'dependencies': ['fxml4-core', 'fxml4-data-collector', 'fxml4-ml-models'],
            'source_dirs': ['fxml4/worker'],
            'namespace': 'fxml4_worker'
        }
    }
    
    def __init__(self, source_root: Path, monorepo_root: Path):
        self.source_root = source_root
        self.monorepo_root = monorepo_root
        self.packages_root = monorepo_root / "packages"
        
    def migrate_package(self, package_name: str, dry_run: bool = False) -> Dict:
        """Migrate a specific package."""
        if package_name not in self.PACKAGE_CONFIGS:
            raise ValueError(f"Unknown package: {package_name}")
        
        config = self.PACKAGE_CONFIGS[package_name]
        package_dir = self.packages_root / package_name
        
        results = {
            'package': package_name,
            'created_dirs': [],
            'copied_files': [],
            'updated_imports': [],
            'errors': []
        }
        
        try:
            # Create package structure
            if not dry_run:
                self._create_package_structure(package_dir, config)
            results['created_dirs'].append(str(package_dir))
            
            # Copy source files
            namespace = config['namespace']
            src_dir = package_dir / "src" / namespace
            
            for source_dir in config['source_dirs']:
                source_path = self.source_root / source_dir
                if source_path.exists():
                    files = self._copy_source_files(source_path, src_dir, dry_run)
                    results['copied_files'].extend(files)
            
            # Update imports in copied files
            if not dry_run:
                for file_path in results['copied_files']:
                    if file_path.endswith('.py'):
                        full_path = package_dir / "src" / namespace / Path(file_path).name
                        if self._update_imports(full_path):
                            results['updated_imports'].append(file_path)
            
            # Create tests structure
            if not dry_run:
                self._create_test_structure(package_dir)
            
        except Exception as e:
            results['errors'].append(str(e))
        
        return results
    
    def _create_package_structure(self, package_dir: Path, config: Dict):
        """Create the package directory structure."""
        # Create directories
        (package_dir / "src" / config['namespace']).mkdir(parents=True, exist_ok=True)
        (package_dir / "tests" / "unit").mkdir(parents=True, exist_ok=True)
        (package_dir / "tests" / "integration").mkdir(parents=True, exist_ok=True)
        
        # Create __init__.py files
        (package_dir / "src" / config['namespace'] / "__init__.py").touch()
        (package_dir / "tests" / "__init__.py").touch()
        
        # Create pyproject.toml
        self._create_pyproject_toml(package_dir, config)
        
        # Create README.md
        self._create_readme(package_dir, config)
    
    def _create_pyproject_toml(self, package_dir: Path, config: Dict):
        """Create pyproject.toml for the package."""
        namespace = config['namespace']
        package_name = package_dir.name
        
        content = f'''[tool.poetry]
name = "fxml4-{package_name}"
version = "0.1.0"
description = "{config['description']}"
authors = ["FXML4 Team"]
packages = [{{include = "{namespace}", from = "src"}}]

[tool.poetry.dependencies]
python = "^3.8"
'''
        
        # Add dependencies
        for dep in config['dependencies']:
            content += f'{dep} = {{path = "../{dep.replace("fxml4-", "")}", develop = true}}\n'
        
        content += '''
[tool.poetry.dev-dependencies]
pytest = "^7.0"
pytest-cov = "^4.0"
pytest-asyncio = "^0.21"
black = "^23.0"
isort = "^5.10"
mypy = "^1.0"

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_functions = ["test_*"]

[tool.coverage.run]
source = ["src"]
omit = ["*/tests/*", "*/__init__.py"]

[tool.mypy]
python_version = "3.8"
warn_return_any = true
warn_unused_configs = true
ignore_missing_imports = true

[tool.isort]
profile = "black"
line_length = 88

[tool.black]
line-length = 88
target-version = ["py38"]

[build-system]
requires = ["poetry-core>=1.0.0"]
build-backend = "poetry.core.masonry.api"
'''
        
        (package_dir / "pyproject.toml").write_text(content)
    
    def _create_readme(self, package_dir: Path, config: Dict):
        """Create README.md for the package."""
        package_name = package_dir.name
        namespace = config['namespace']
        
        content = f'''# {package_name}

{config['description']}

## Installation

```bash
cd packages/{package_name}
poetry install
```

## Usage

```python
from {namespace} import ...
```

## Development

### Running Tests

```bash
poetry run pytest
```

### Code Quality

```bash
poetry run black src tests
poetry run isort src tests
poetry run mypy src
```

## API Reference

See the [API documentation](docs/api.md) for detailed information.
'''
        
        (package_dir / "README.md").write_text(content)
    
    def _copy_source_files(self, source_path: Path, dest_dir: Path, dry_run: bool) -> List[str]:
        """Copy source files from old structure to new package."""
        copied_files = []
        
        if source_path.is_file() and source_path.suffix == '.py':
            dest_file = dest_dir / source_path.name
            if not dry_run:
                dest_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_path, dest_file)
            copied_files.append(source_path.name)
        
        elif source_path.is_dir():
            for item in source_path.rglob('*.py'):
                if '__pycache__' not in str(item):
                    rel_path = item.relative_to(source_path)
                    dest_file = dest_dir / rel_path
                    if not dry_run:
                        dest_file.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(item, dest_file)
                    copied_files.append(str(rel_path))
        
        return copied_files
    
    def _update_imports(self, file_path: Path) -> bool:
        """Update imports in a Python file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse and transform AST
            tree = ast.parse(content)
            transformer = ImportTransformer(self.IMPORT_MAPPINGS)
            new_tree = transformer.visit(tree)
            
            if transformer.modified:
                # Generate new code
                new_content = ast.unparse(new_tree)
                
                # Write back
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                
                return True
            
        except Exception as e:
            print(f"Error updating imports in {file_path}: {e}")
        
        return False
    
    def _create_test_structure(self, package_dir: Path):
        """Create test structure for the package."""
        # Create conftest.py
        conftest_content = '''"""
Test configuration for the package.
"""
import pytest
from pathlib import Path

@pytest.fixture
def test_data_dir():
    """Return the test data directory."""
    return Path(__file__).parent / "data"
'''
        
        (package_dir / "tests" / "conftest.py").write_text(conftest_content)
        
        # Create example test
        namespace = self.PACKAGE_CONFIGS.get(package_dir.name, {}).get('namespace', 'fxml4_package')
        test_content = f'''"""
Example test file.
"""
import pytest
from {namespace} import __version__

def test_version():
    """Test that version is defined."""
    assert __version__ is not None
'''
        
        (package_dir / "tests" / "unit" / "test_example.py").write_text(test_content)


@click.command()
@click.option('--package', '-p', required=True, 
              type=click.Choice(list(PackageMigrator.PACKAGE_CONFIGS.keys())),
              help='Package to migrate')
@click.option('--source-root', '-s', 
              type=click.Path(exists=True, path_type=Path),
              default=Path('/home/cnross/code/fxml4'),
              help='Source root directory')
@click.option('--monorepo-root', '-m',
              type=click.Path(exists=True, path_type=Path),
              default=Path('/home/cnross/code/fxml4/fxml4-monorepo'),
              help='Monorepo root directory')
@click.option('--dry-run', is_flag=True,
              help='Show what would be done without doing it')
@click.option('--output', '-o', type=click.Path(),
              help='Output file for migration report')
def migrate(package: str, source_root: Path, monorepo_root: Path, 
           dry_run: bool, output: Optional[str]):
    """Migrate a package from traditional structure to monorepo."""
    
    click.echo(f"Migrating package: {package}")
    click.echo(f"Source root: {source_root}")
    click.echo(f"Monorepo root: {monorepo_root}")
    click.echo(f"Dry run: {dry_run}")
    
    migrator = PackageMigrator(source_root, monorepo_root)
    results = migrator.migrate_package(package, dry_run)
    
    # Print results
    click.echo("\nMigration Results:")
    click.echo(f"Created directories: {len(results['created_dirs'])}")
    for dir_path in results['created_dirs']:
        click.echo(f"  - {dir_path}")
    
    click.echo(f"\nCopied files: {len(results['copied_files'])}")
    for file_path in results['copied_files'][:10]:  # Show first 10
        click.echo(f"  - {file_path}")
    if len(results['copied_files']) > 10:
        click.echo(f"  ... and {len(results['copied_files']) - 10} more")
    
    click.echo(f"\nUpdated imports: {len(results['updated_imports'])}")
    
    if results['errors']:
        click.echo(f"\nErrors: {len(results['errors'])}")
        for error in results['errors']:
            click.echo(f"  - {error}")
    
    # Save results if requested
    if output:
        with open(output, 'w') as f:
            json.dump(results, f, indent=2)
        click.echo(f"\nResults saved to: {output}")
    
    if dry_run:
        click.echo("\nThis was a dry run. No changes were made.")
    else:
        click.echo("\nMigration complete!")
        click.echo("\nNext steps:")
        click.echo(f"1. cd {monorepo_root}/packages/{package}")
        click.echo("2. poetry install")
        click.echo("3. poetry run pytest")


if __name__ == "__main__":
    migrate()