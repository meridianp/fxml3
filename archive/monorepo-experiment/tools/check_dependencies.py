#!/usr/bin/env python3
"""
Simple dependency checker for FXML4 monorepo packages.
"""

import ast
import json
from pathlib import Path
from typing import Dict, Set, List, Optional
from collections import defaultdict


class ImportAnalyzer(ast.NodeVisitor):
    """Extract imports from Python files."""
    
    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.imports = set()
        self.fxml4_imports = set()
        
    def visit_Import(self, node):
        for alias in node.names:
            self.imports.add(alias.name)
            if alias.name.startswith('fxml4'):
                self.fxml4_imports.add(alias.name)
        self.generic_visit(node)
        
    def visit_ImportFrom(self, node):
        if node.module:
            self.imports.add(node.module)
            if node.module.startswith('fxml4'):
                self.fxml4_imports.add(node.module)
        self.generic_visit(node)


def analyze_package(package_dir: Path) -> Dict[str, Set[str]]:
    """Analyze all Python files in a package for imports."""
    imports_by_file = {}
    
    src_dir = package_dir / "src"
    if src_dir.exists():
        for py_file in src_dir.rglob("*.py"):
            if '__pycache__' not in str(py_file):
                try:
                    with open(py_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    tree = ast.parse(content)
                    analyzer = ImportAnalyzer(py_file)
                    analyzer.visit(tree)
                    
                    if analyzer.fxml4_imports:
                        rel_path = py_file.relative_to(package_dir)
                        imports_by_file[str(rel_path)] = analyzer.fxml4_imports
                        
                except Exception as e:
                    print(f"Error analyzing {py_file}: {e}")
    
    return imports_by_file


def map_import_to_package(import_name: str) -> Optional[str]:
    """Map an fxml4_* import to its package name."""
    mapping = {
        'fxml4_core': 'core',
        'fxml4_data_collector': 'data-collector',
        'fxml4_ml': 'ml-models',
        'fxml4_signals': 'signal-generator',
        'fxml4_llm': 'llm-analyzer',
        'fxml4_trade_manager': 'trade-manager',
        'fxml4_backtesting': 'backtesting',
        'fxml4_web': 'web-ui',
    }
    
    for prefix, package in mapping.items():
        if import_name.startswith(prefix):
            return package
    
    return None


def detect_circular_dependencies(dependencies: Dict[str, Set[str]]) -> List[List[str]]:
    """Simple cycle detection using DFS."""
    visited = set()
    rec_stack = set()
    cycles = []
    
    def dfs(node: str, path: List[str]):
        if node in rec_stack:
            # Found a cycle
            cycle_start = path.index(node)
            cycle = path[cycle_start:] + [node]
            if len(cycle) > 2:  # Only report non-trivial cycles
                cycles.append(cycle)
            return
        
        if node in visited:
            return
        
        visited.add(node)
        rec_stack.add(node)
        
        for neighbor in dependencies.get(node, set()):
            dfs(neighbor, path + [node])
        
        rec_stack.remove(node)
    
    for node in dependencies:
        if node not in visited:
            dfs(node, [])
    
    return cycles


def main():
    """Main analysis function."""
    monorepo_root = Path('/home/cnross/code/fxml4/fxml4-monorepo')
    packages_root = monorepo_root / "packages"
    
    # Analyze each package
    package_imports = {}
    package_dependencies = defaultdict(set)
    
    print("Analyzing packages...")
    for package_dir in packages_root.iterdir():
        if package_dir.is_dir() and (package_dir / "pyproject.toml").exists():
            package_name = package_dir.name
            print(f"  - {package_name}")
            
            # Analyze imports
            imports = analyze_package(package_dir)
            package_imports[package_name] = imports
            
            # Extract package dependencies
            for file_imports in imports.values():
                for imp in file_imports:
                    dep_package = map_import_to_package(imp)
                    if dep_package and dep_package != package_name:
                        package_dependencies[package_name].add(dep_package)
    
    # Print dependency summary
    print("\nPackage Dependencies:")
    for package, deps in sorted(package_dependencies.items()):
        if deps:
            print(f"  {package}:")
            for dep in sorted(deps):
                print(f"    → {dep}")
    
    # Check for circular dependencies
    print("\nChecking for circular dependencies...")
    cycles = detect_circular_dependencies(dict(package_dependencies))
    
    if cycles:
        print(f"Found {len(cycles)} circular dependencies:")
        for i, cycle in enumerate(cycles, 1):
            print(f"\n  Cycle {i}: {' → '.join(cycle)}")
    else:
        print("No circular dependencies found!")
    
    # Generate report
    report = {
        'packages_analyzed': len(package_imports),
        'dependencies': {k: list(v) for k, v in package_dependencies.items()},
        'circular_dependencies': cycles,
        'import_details': {}
    }
    
    # Add detailed import information
    for package, imports in package_imports.items():
        if imports:
            report['import_details'][package] = {
                'files_with_imports': len(imports),
                'total_fxml4_imports': sum(len(imps) for imps in imports.values()),
                'sample_imports': {
                    file: list(imps)[:3]  # First 3 imports per file
                    for file, imps in list(imports.items())[:3]  # First 3 files
                }
            }
    
    # Save report
    report_path = monorepo_root / "dependency_report.json"
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"\nDetailed report saved to: {report_path}")
    
    # Print recommendations if cycles found
    if cycles:
        print("\nRecommendations to resolve circular dependencies:")
        for i, cycle in enumerate(cycles, 1):
            print(f"\n{i}. Cycle: {' → '.join(cycle)}")
            print("   Solutions:")
            print("   - Extract shared interfaces to fxml4_core")
            print("   - Use dependency injection instead of direct imports")
            print("   - Consider merging tightly coupled packages")
            print("   - Implement event-based communication")


if __name__ == "__main__":
    main()