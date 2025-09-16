#!/usr/bin/env python3
"""
FXML4 Component Configuration Loader
Loads and merges component-specific TDD configurations
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


@dataclass
class ComponentConfig:
    """Represents a component-specific configuration"""

    name: str
    path: str
    language: str
    framework: str
    testing: Dict[str, Any]
    tdd_cycles: Dict[str, Any]
    performance_targets: Dict[str, Any]
    mutation_testing: Dict[str, Any]
    quality_gates: Dict[str, Any]
    specialized_controls: Dict[str, Any] = field(default_factory=dict)


class ComponentConfigLoader:
    """Loads and manages component-specific TDD configurations"""

    def __init__(self, components_dir: str = ".claude-tdd/components/"):
        self.components_dir = Path(components_dir)
        self.loaded_configs = {}

    def load_component_config(self, component_name: str) -> Optional[ComponentConfig]:
        """Load configuration for a specific component"""
        config_file = self.components_dir / f"{component_name}_config.yml"

        if not config_file.exists():
            print(f"Warning: Component config not found: {config_file}")
            return None

        try:
            with open(config_file, "r") as f:
                config_data = yaml.safe_load(f)

            component_config = ComponentConfig(
                name=config_data["component"]["name"],
                path=config_data["component"]["path"],
                language=config_data["component"]["language"],
                framework=config_data["component"]["framework"],
                testing=config_data.get("testing", {}),
                tdd_cycles=config_data.get("tdd_cycles", {}),
                performance_targets=config_data.get("performance_targets", {}),
                mutation_testing=config_data.get("mutation_testing", {}),
                quality_gates=self._extract_quality_gates(config_data),
                specialized_controls=self._extract_specialized_controls(config_data),
            )

            self.loaded_configs[component_name] = component_config
            return component_config

        except Exception as e:
            print(f"Error loading component config {config_file}: {e}")
            return None

    def _extract_quality_gates(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract quality gates from component config"""
        quality_gates = {}

        # Standard quality gates
        if "quality_gates" in config_data:
            quality_gates.update(config_data["quality_gates"])

        # Component-specific quality gates
        for key in ["ml_quality_gates", "frontend_quality_gates"]:
            if key in config_data:
                quality_gates.update(config_data[key])

        return quality_gates

    def _extract_specialized_controls(
        self, config_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract specialized controls based on component type"""
        controls = {}

        # Risk controls for core component
        if "risk_controls" in config_data:
            controls["risk_controls"] = config_data["risk_controls"]

        # Wave analysis controls
        if "wave_analysis_controls" in config_data:
            controls["wave_analysis_controls"] = config_data["wave_analysis_controls"]

        # Frontend controls
        if "frontend_controls" in config_data:
            controls["frontend_controls"] = config_data["frontend_controls"]

        # Property testing
        if "property_testing" in config_data:
            controls["property_testing"] = config_data["property_testing"]

        # Visual testing
        if "visual_testing" in config_data:
            controls["visual_testing"] = config_data["visual_testing"]

        # E2E testing
        if "e2e_testing" in config_data:
            controls["e2e_testing"] = config_data["e2e_testing"]

        return controls

    def load_all_components(self) -> Dict[str, ComponentConfig]:
        """Load all available component configurations"""
        component_configs = {}

        # Standard FXML4 components
        for component_name in ["core", "elliott_wave", "frontend"]:
            config = self.load_component_config(component_name)
            if config:
                component_configs[component_name] = config

        return component_configs

    def get_component_test_paths(self, component_name: str) -> List[str]:
        """Get test paths for a specific component"""
        if component_name not in self.loaded_configs:
            self.load_component_config(component_name)

        if component_name in self.loaded_configs:
            testing_config = self.loaded_configs[component_name].testing
            test_paths = testing_config.get("test_paths", {})

            # Flatten all test paths
            all_paths = []
            for category, paths in test_paths.items():
                if isinstance(paths, list):
                    all_paths.extend(paths)
                else:
                    all_paths.append(paths)

            return all_paths

        return []

    def get_component_markers(self, component_name: str) -> List[str]:
        """Get test markers for a specific component"""
        if component_name not in self.loaded_configs:
            self.load_component_config(component_name)

        if component_name in self.loaded_configs:
            testing_config = self.loaded_configs[component_name].testing
            return testing_config.get("markers", [])

        return []

    def get_tdd_cycle_config(
        self, component_name: str, phase: str
    ) -> Optional[Dict[str, Any]]:
        """Get TDD cycle configuration for a component and phase"""
        if component_name not in self.loaded_configs:
            self.load_component_config(component_name)

        if component_name in self.loaded_configs:
            tdd_cycles = self.loaded_configs[component_name].tdd_cycles
            return tdd_cycles.get(phase)

        return None

    def get_performance_targets(self, component_name: str) -> Dict[str, Any]:
        """Get performance targets for a component"""
        if component_name not in self.loaded_configs:
            self.load_component_config(component_name)

        if component_name in self.loaded_configs:
            return self.loaded_configs[component_name].performance_targets

        return {}

    def validate_component_config(self, component_name: str) -> bool:
        """Validate that a component configuration is complete and valid"""
        if component_name not in self.loaded_configs:
            self.load_component_config(component_name)

        if component_name not in self.loaded_configs:
            return False

        config = self.loaded_configs[component_name]

        # Required fields validation
        required_fields = ["name", "path", "language", "framework"]
        for field in required_fields:
            if not hasattr(config, field) or not getattr(config, field):
                print(f"Missing required field '{field}' in {component_name} config")
                return False

        # Path existence validation
        component_path = Path(config.path)
        if not component_path.exists():
            print(f"Component path does not exist: {component_path}")
            return False

        # Test paths validation
        if config.testing and "test_paths" in config.testing:
            test_paths = config.testing["test_paths"]
            for category, paths in test_paths.items():
                if isinstance(paths, list):
                    for path in paths:
                        full_path = Path(path)
                        if not full_path.exists():
                            print(f"Test path does not exist: {full_path}")
                            # Warning only, don't fail validation

        return True

    def merge_with_base_config(
        self, base_config: Dict[str, Any], component_name: str
    ) -> Dict[str, Any]:
        """Merge component-specific config with base configuration"""
        if component_name not in self.loaded_configs:
            self.load_component_config(component_name)

        if component_name not in self.loaded_configs:
            return base_config

        component_config = self.loaded_configs[component_name]
        merged_config = base_config.copy()

        # Merge testing configuration
        if "testing" in merged_config and component_config.testing:
            merged_config["testing"].update(component_config.testing)

        # Merge TDD cycles
        if "tdd_cycles" in merged_config and component_config.tdd_cycles:
            merged_config["tdd_cycles"].update(component_config.tdd_cycles)

        # Add component-specific sections
        merged_config["performance_targets"] = component_config.performance_targets
        merged_config["component_quality_gates"] = component_config.quality_gates
        merged_config["specialized_controls"] = component_config.specialized_controls

        return merged_config


def main():
    """Demo usage of component configuration loader"""
    loader = ComponentConfigLoader()

    # Load all components
    configs = loader.load_all_components()

    print("Loaded Component Configurations:")
    print("=" * 50)

    for name, config in configs.items():
        print(f"\nComponent: {name}")
        print(f"  Path: {config.path}")
        print(f"  Language: {config.language}")
        print(f"  Framework: {config.framework}")

        # Validation
        is_valid = loader.validate_component_config(name)
        print(f"  Valid: {is_valid}")

        # Test paths
        test_paths = loader.get_component_test_paths(name)
        print(f"  Test Paths: {len(test_paths)} configured")

        # Markers
        markers = loader.get_component_markers(name)
        print(f"  Markers: {len(markers)} configured")


if __name__ == "__main__":
    main()
