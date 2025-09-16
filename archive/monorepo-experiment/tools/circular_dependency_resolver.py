#!/usr/bin/env python3
"""
Circular Dependency Resolver for FXML4 Monorepo
Detects and provides solutions for circular dependencies.
"""

import ast
import json
from pathlib import Path
from typing import Dict, Set, List, Tuple, Optional
from collections import defaultdict, deque
import networkx as nx
import matplotlib.pyplot as plt


class ImportAnalyzer(ast.NodeVisitor):
    """Extract imports and their usage from Python files."""
    
    def __init__(self, file_path: Path, package_root: Path):
        self.file_path = file_path
        self.package_root = package_root
        self.imports = set()
        self.internal_imports = set()
        self.external_imports = set()
        
    def visit_Import(self, node):
        for alias in node.names:
            self.imports.add(alias.name)
            self._categorize_import(alias.name)
        self.generic_visit(node)
        
    def visit_ImportFrom(self, node):
        if node.module:
            # Handle relative imports
            if node.level > 0:
                module = self._resolve_relative_import(node.module, node.level)
            else:
                module = node.module
            
            self.imports.add(module)
            self._categorize_import(module)
            
            # Also track specific imports
            for alias in node.names:
                full_name = f"{module}.{alias.name}"
                self.imports.add(full_name)
                
        self.generic_visit(node)
    
    def _resolve_relative_import(self, module: Optional[str], level: int) -> str:
        """Resolve relative imports to absolute imports."""
        current_package = str(self.file_path.relative_to(self.package_root).parent)
        current_package = current_package.replace('/', '.')
        
        # Go up 'level' directories
        parts = current_package.split('.')
        if level <= len(parts):
            base = '.'.join(parts[:-level])
            if module:
                return f"{base}.{module}"
            return base
        
        return module or ""
    
    def _categorize_import(self, module: str):
        """Categorize import as internal or external."""
        if module.startswith('fxml4') or module.startswith('.'):
            self.internal_imports.add(module)
        else:
            self.external_imports.add(module)


class CircularDependencyResolver:
    """Detect and resolve circular dependencies in the monorepo."""
    
    def __init__(self, monorepo_root: Path):
        self.monorepo_root = monorepo_root
        self.packages_root = monorepo_root / "packages"
        self.dependency_graph = nx.DiGraph()
        self.file_to_package = {}
        self.package_dependencies = defaultdict(set)
        
    def analyze(self) -> Dict:
        """Analyze the entire monorepo for circular dependencies."""
        # Build dependency graph
        self._build_dependency_graph()
        
        # Detect cycles
        cycles = self._detect_cycles()
        
        # Analyze each cycle
        cycle_analysis = []
        for cycle in cycles:
            analysis = self._analyze_cycle(cycle)
            cycle_analysis.append(analysis)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(cycle_analysis)
        
        return {
            'total_packages': len(self.package_dependencies),
            'cycles_found': len(cycles),
            'cycles': cycle_analysis,
            'recommendations': recommendations,
            'dependency_graph': self._export_graph()
        }
    
    def _build_dependency_graph(self):
        """Build a dependency graph of all packages."""
        # Map files to packages
        for package_dir in self.packages_root.iterdir():
            if package_dir.is_dir() and (package_dir / "pyproject.toml").exists():
                package_name = package_dir.name
                
                # Analyze all Python files in the package
                src_dir = package_dir / "src"
                if src_dir.exists():
                    for py_file in src_dir.rglob("*.py"):
                        self.file_to_package[py_file] = package_name
                        
                        # Analyze imports
                        analyzer = self._analyze_file(py_file)
                        if analyzer:
                            # Map imports to packages
                            for imp in analyzer.internal_imports:
                                dep_package = self._import_to_package(imp)
                                if dep_package and dep_package != package_name:
                                    self.package_dependencies[package_name].add(dep_package)
                                    self.dependency_graph.add_edge(package_name, dep_package)
    
    def _analyze_file(self, file_path: Path) -> Optional[ImportAnalyzer]:
        """Analyze imports in a single file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content)
            analyzer = ImportAnalyzer(file_path, self.monorepo_root)
            analyzer.visit(tree)
            
            return analyzer
            
        except Exception as e:
            print(f"Error analyzing {file_path}: {e}")
            return None
    
    def _import_to_package(self, import_name: str) -> Optional[str]:
        """Map an import to its package."""
        # Handle fxml4_* imports
        if import_name.startswith('fxml4_'):
            parts = import_name.split('_', 1)
            if len(parts) > 1:
                # Map fxml4_core -> core, fxml4_ml -> ml-models, etc.
                package_map = {
                    'fxml4_core': 'core',
                    'fxml4_data_collector': 'data-collector',
                    'fxml4_ml': 'ml-models',
                    'fxml4_signals': 'signal-generator',
                    'fxml4_llm': 'llm-analyzer',
                    'fxml4_trade_manager': 'trade-manager',
                    'fxml4_backtesting': 'backtesting',
                    'fxml4_web': 'web-ui',
                }
                return package_map.get(import_name.split('.')[0])
        
        return None
    
    def _detect_cycles(self) -> List[List[str]]:
        """Detect all cycles in the dependency graph."""
        try:
            cycles = list(nx.simple_cycles(self.dependency_graph))
            return cycles
        except:
            return []
    
    def _analyze_cycle(self, cycle: List[str]) -> Dict:
        """Analyze a specific cycle to understand its nature."""
        edges = []
        for i in range(len(cycle)):
            from_pkg = cycle[i]
            to_pkg = cycle[(i + 1) % len(cycle)]
            edges.append({
                'from': from_pkg,
                'to': to_pkg,
                'imports': self._get_specific_imports(from_pkg, to_pkg)
            })
        
        return {
            'packages': cycle,
            'edges': edges,
            'severity': self._calculate_severity(cycle),
            'type': self._classify_cycle(cycle, edges)
        }
    
    def _get_specific_imports(self, from_pkg: str, to_pkg: str) -> List[str]:
        """Get specific imports between two packages."""
        # This would require more detailed tracking in the real implementation
        return [f"fxml4_{to_pkg}"]
    
    def _calculate_severity(self, cycle: List[str]) -> str:
        """Calculate the severity of a circular dependency."""
        if len(cycle) == 2:
            return "HIGH"  # Direct circular dependency
        elif len(cycle) <= 4:
            return "MEDIUM"  # Small cycle
        else:
            return "LOW"  # Large cycle, might be easier to break
    
    def _classify_cycle(self, cycle: List[str], edges: List[Dict]) -> str:
        """Classify the type of circular dependency."""
        # Check for common patterns
        if 'core' in cycle:
            return "CORE_VIOLATION"  # Core should have no dependencies
        elif any('api' in pkg or 'web' in pkg for pkg in cycle):
            return "UI_BACKEND_COUPLING"  # UI and backend are coupled
        elif any('ml' in pkg for pkg in cycle):
            return "ML_PIPELINE_CYCLE"  # ML pipeline has circular deps
        else:
            return "GENERAL_CYCLE"
    
    def _generate_recommendations(self, cycle_analysis: List[Dict]) -> List[Dict]:
        """Generate specific recommendations to resolve cycles."""
        recommendations = []
        
        for analysis in cycle_analysis:
            cycle_type = analysis['type']
            packages = analysis['packages']
            
            if cycle_type == "CORE_VIOLATION":
                recommendations.append({
                    'severity': 'CRITICAL',
                    'packages': packages,
                    'recommendation': 'Move shared interfaces from dependent packages to core',
                    'actions': [
                        'Extract interfaces to fxml4_core.interfaces',
                        'Use Protocol types for loose coupling',
                        'Remove direct imports from core to other packages'
                    ]
                })
            
            elif cycle_type == "UI_BACKEND_COUPLING":
                recommendations.append({
                    'severity': 'HIGH',
                    'packages': packages,
                    'recommendation': 'Decouple UI from backend using API contracts',
                    'actions': [
                        'Define API schemas in a separate package',
                        'Use dependency injection for services',
                        'Implement event-based communication'
                    ]
                })
            
            elif cycle_type == "ML_PIPELINE_CYCLE":
                recommendations.append({
                    'severity': 'MEDIUM',
                    'packages': packages,
                    'recommendation': 'Refactor ML pipeline to use unidirectional flow',
                    'actions': [
                        'Separate model definitions from feature engineering',
                        'Use configuration files instead of imports',
                        'Implement pipeline stages as independent services'
                    ]
                })
            
            else:
                recommendations.append({
                    'severity': 'LOW',
                    'packages': packages,
                    'recommendation': 'Review and refactor package boundaries',
                    'actions': [
                        'Consider merging tightly coupled packages',
                        'Extract common functionality to shared package',
                        'Use interfaces instead of concrete implementations'
                    ]
                })
        
        return recommendations
    
    def _export_graph(self) -> Dict:
        """Export the dependency graph in a serializable format."""
        return {
            'nodes': list(self.dependency_graph.nodes()),
            'edges': [{'from': u, 'to': v} for u, v in self.dependency_graph.edges()]
        }
    
    def visualize(self, output_path: Path):
        """Visualize the dependency graph."""
        plt.figure(figsize=(12, 8))
        
        # Layout
        pos = nx.spring_layout(self.dependency_graph, k=2, iterations=50)
        
        # Draw nodes
        nx.draw_networkx_nodes(self.dependency_graph, pos, 
                              node_color='lightblue', 
                              node_size=3000)
        
        # Draw edges
        nx.draw_networkx_edges(self.dependency_graph, pos, 
                              edge_color='gray', 
                              arrows=True,
                              arrowsize=20)
        
        # Draw labels
        nx.draw_networkx_labels(self.dependency_graph, pos)
        
        # Highlight cycles
        cycles = self._detect_cycles()
        for cycle in cycles:
            cycle_edges = [(cycle[i], cycle[(i+1) % len(cycle)]) 
                          for i in range(len(cycle))]
            nx.draw_networkx_edges(self.dependency_graph, pos,
                                 edgelist=cycle_edges,
                                 edge_color='red',
                                 width=2,
                                 arrows=True,
                                 arrowsize=20)
        
        plt.title("Package Dependencies (Red = Circular)")
        plt.axis('off')
        plt.tight_layout()
        plt.savefig(output_path)
        plt.close()


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Detect and resolve circular dependencies')
    parser.add_argument('--monorepo-root', type=Path, 
                       default=Path('/home/cnross/code/fxml4/fxml4-monorepo'),
                       help='Root of the monorepo')
    parser.add_argument('--output', type=Path,
                       default=Path('circular_deps_report.json'),
                       help='Output file for the report')
    parser.add_argument('--visualize', action='store_true',
                       help='Generate visualization')
    
    args = parser.parse_args()
    
    # Run analysis
    resolver = CircularDependencyResolver(args.monorepo_root)
    results = resolver.analyze()
    
    # Save results
    with open(args.output, 'w') as f:
        json.dump(results, f, indent=2)
    
    # Print summary
    print(f"Circular Dependency Analysis Complete")
    print(f"{'='*50}")
    print(f"Total packages: {results['total_packages']}")
    print(f"Circular dependencies found: {results['cycles_found']}")
    
    if results['cycles']:
        print(f"\nCircular Dependencies:")
        for i, cycle in enumerate(results['cycles'], 1):
            print(f"\n{i}. Cycle: {' -> '.join(cycle['packages'])} -> {cycle['packages'][0]}")
            print(f"   Severity: {cycle['severity']}")
            print(f"   Type: {cycle['type']}")
    
    if results['recommendations']:
        print(f"\nRecommendations:")
        for i, rec in enumerate(results['recommendations'], 1):
            print(f"\n{i}. {rec['recommendation']}")
            print(f"   Severity: {rec['severity']}")
            print(f"   Packages: {', '.join(rec['packages'])}")
            print(f"   Actions:")
            for action in rec['actions']:
                print(f"     - {action}")
    
    # Generate visualization
    if args.visualize:
        viz_path = args.output.with_suffix('.png')
        resolver.visualize(viz_path)
        print(f"\nDependency graph saved to: {viz_path}")
    
    print(f"\nFull report saved to: {args.output}")


if __name__ == "__main__":
    main()