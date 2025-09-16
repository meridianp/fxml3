#!/usr/bin/env python3
"""
Advanced Mutation Testing Configuration for FXML4
Provides intelligent mutation strategies for financial trading systems
"""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import yaml


@dataclass
class MutationStrategy:
    """Configuration for mutation testing strategy"""

    name: str
    enabled: bool = True
    operators: List[str] = field(default_factory=list)
    exclusions: List[str] = field(default_factory=list)
    risk_level: str = "medium"  # low, medium, high, critical
    description: str = ""


@dataclass
class FinancialMutationRules:
    """Financial trading specific mutation rules"""

    # Critical financial operations that need special handling
    price_calculations: List[str] = field(
        default_factory=lambda: [
            "calculate_price",
            "get_bid",
            "get_ask",
            "compute_spread",
            "calculate_pnl",
            "calculate_unrealized_pnl",
            "mark_to_market",
        ]
    )

    risk_calculations: List[str] = field(
        default_factory=lambda: [
            "calculate_var",
            "calculate_risk",
            "compute_exposure",
            "check_limits",
            "validate_position_size",
            "calculate_margin",
        ]
    )

    # Operations that should NEVER be mutated (safety critical)
    immutable_operations: List[str] = field(
        default_factory=lambda: [
            "emergency_stop",
            "force_close",
            "circuit_breaker",
            "compliance_check",
            "audit_log",
            "security_validate",
        ]
    )

    # High-precision numeric operations
    precision_critical: List[str] = field(
        default_factory=lambda: ["decimal", "Decimal", "round", "quantize", "normalize"]
    )


class AdvancedMutationConfig:
    """Advanced mutation testing configuration manager"""

    def __init__(self, config_path: str = ".claude-tdd/config.yml"):
        self.config = self._load_config(config_path)
        self.financial_rules = FinancialMutationRules()
        self.mutation_strategies = self._create_mutation_strategies()

    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load main TDD configuration"""
        with open(config_path, "r") as f:
            return yaml.safe_load(f)

    def _create_mutation_strategies(self) -> Dict[str, MutationStrategy]:
        """Create mutation strategies for different components"""
        strategies = {}

        # Core trading system strategy
        strategies["core_trading"] = MutationStrategy(
            name="core_trading",
            enabled=True,
            operators=[
                "AOR",  # Arithmetic Operator Replacement
                "AOD",  # Arithmetic Operator Deletion
                "COI",  # Conditional Operator Insertion
                "CRP",  # Constant Replacement
                "DDL",  # Decorator Deletion
            ],
            exclusions=[
                "test_*",  # Don't mutate test files
                "*_test.py",
                "conftest.py",
                "setup.py",
                "__init__.py",
            ],
            risk_level="high",
            description="Mutation strategy for core trading system components",
        )

        # Elliott Wave ML strategy
        strategies["elliott_wave_ml"] = MutationStrategy(
            name="elliott_wave_ml",
            enabled=True,
            operators=[
                "AOR",
                "COI",
                "CRP",
                "CCR",  # Comparison operator replacement
                "LCR",  # Logical connector replacement
                "ROR",  # Return statement replacement
            ],
            exclusions=["test_*", "*_test.py", "model_weights/*", "*.pkl", "*.h5"],
            risk_level="medium",
            description="Mutation strategy for Elliott Wave ML components",
        )

        # Risk management strategy (most conservative)
        strategies["risk_management"] = MutationStrategy(
            name="risk_management",
            enabled=True,
            operators=[
                "AOR",  # Only arithmetic - be very careful with risk logic
                "CRP",  # Constants only
            ],
            exclusions=[
                "test_*",
                "*_test.py",
                "emergency_*",
                "circuit_breaker*",
                "compliance_*",
                "audit_*",
            ],
            risk_level="critical",
            description="Conservative mutation strategy for risk management",
        )

        # Frontend/UI strategy
        strategies["frontend"] = MutationStrategy(
            name="frontend",
            enabled=True,
            operators=[
                "ArithmeticOperator",
                "ConditionalExpression",
                "EqualityOperator",
                "LogicalOperator",
                "UpdateExpression",
            ],
            exclusions=[
                "*.test.ts",
                "*.test.tsx",
                "*.spec.ts",
                "*.spec.tsx",
                "node_modules/**",
                "dist/**",
                "build/**",
            ],
            risk_level="low",
            description="Mutation strategy for frontend components",
        )

        return strategies

    def get_mutmut_config(self, component: str) -> Dict[str, Any]:
        """Generate mutmut configuration for component"""
        strategy = self._get_strategy_for_component(component)
        component_config = self.config["components"][component]

        # Base mutmut configuration
        config = {
            "paths_to_mutate": self._get_mutation_paths(component),
            "paths_to_exclude": strategy.exclusions,
            "runner": self._get_test_runner_command(component),
            "tests_dir": "tests",
            "timeout_factor": self._get_timeout_factor(strategy.risk_level),
            "backup": True,
            "simple_output": self.config["mutation"].get("ci_mode", False),
        }

        # Add financial-specific exclusions
        config["paths_to_exclude"].extend(self._get_financial_exclusions())

        return config

    def get_stryker_config(self, component: str) -> Dict[str, Any]:
        """Generate Stryker configuration for component"""
        strategy = self._get_strategy_for_component(component)

        config = {
            "$schema": "./node_modules/@stryker-mutator/core/schema/stryker-schema.json",
            "packageManager": "npm",
            "reporters": ["progress", "clear-text", "html", "json"],
            "testRunner": "jest",
            "jest": {
                "projectType": "custom",
                "configFile": "jest.config.js",
                "enableFindRelatedTests": True,
            },
            "coverageAnalysis": "perTest",
            "mutate": self._get_frontend_mutation_patterns(),
            "ignore": strategy.exclusions,
            "mutator": {
                "plugins": strategy.operators,
                "excludedMutations": self._get_excluded_mutations_for_frontend(),
            },
            "thresholds": {
                "high": 80,
                "low": 70,
                "break": 60,
            },
            "timeoutMS": 300000,  # 5 minutes
            "maxConcurrentTestRunners": 4,
            "logLevel": "info",
        }

        return config

    def _get_strategy_for_component(self, component: str) -> MutationStrategy:
        """Get mutation strategy for component based on its characteristics"""
        component_config = self.config["components"][component]
        component_path = component_config["path"]

        # Determine strategy based on component characteristics
        if "risk" in component.lower() or "compliance" in component.lower():
            return self.mutation_strategies["risk_management"]
        elif "elliott" in component.lower() or "ml" in component.lower():
            return self.mutation_strategies["elliott_wave_ml"]
        elif component_config["language"] == "typescript":
            return self.mutation_strategies["frontend"]
        else:
            return self.mutation_strategies["core_trading"]

    def _get_mutation_paths(self, component: str) -> List[str]:
        """Get paths to mutate for component"""
        component_config = self.config["components"][component]
        base_path = Path(component_config["path"])

        # Core Python source directories
        source_dirs = [
            "api",
            "brokers",
            "ml",
            "strategy",
            "backtesting",
            "data_engineering",
            "risk_management",
            "core",
            "src",
            "elliott_wave",
            "indicators",
            "patterns",
        ]

        paths = []
        for source_dir in source_dirs:
            dir_path = base_path / source_dir
            if dir_path.exists():
                paths.append(str(dir_path))

        # If no specific directories, use component path
        if not paths:
            paths.append(str(base_path))

        return paths

    def _get_financial_exclusions(self) -> List[str]:
        """Get financial trading system specific exclusions"""
        return [
            # Never mutate safety-critical functions
            "*emergency*",
            "*circuit_breaker*",
            "*force_close*",
            "*compliance*",
            "*audit*",
            "*security*",
            # Configuration and constants
            "config/*",
            "settings/*",
            "constants.py",
            "*_config.py",
            "*_settings.py",
            # Data files and models
            "*.pkl",
            "*.h5",
            "*.json",
            "*.csv",
            "*.parquet",
            "models/*",
            "weights/*",
            "checkpoints/*",
            # Logging and monitoring (but allow some mutation for robustness)
            "logs/*",
            "*logger*",
            # Database migrations and schemas
            "migrations/*",
            "*migration*",
            "schema/*",
        ]

    def _get_test_runner_command(self, component: str) -> str:
        """Get test runner command for component"""
        component_config = self.config["components"][component]
        test_framework = component_config.get("test_framework", "pytest")

        if test_framework == "pytest":
            # Build pytest command with component-specific options
            cmd_parts = ["python", "-m", "pytest"]

            # Add performance optimizations for mutation testing
            cmd_parts.extend(
                [
                    "-x",  # Stop on first failure
                    "--tb=short",  # Short traceback format
                    "--disable-warnings",  # Reduce noise
                    "-q",  # Quiet mode
                ]
            )

            # Add markers for component
            markers = component_config.get("pytest_markers", [])
            if markers:
                # Filter for unit tests only during mutation testing
                unit_markers = [m for m in markers if "unit" in m or "fast" in m]
                if unit_markers:
                    cmd_parts.extend(["-m", unit_markers[0]])

            return " ".join(cmd_parts)
        else:
            return "python -m pytest -x"

    def _get_timeout_factor(self, risk_level: str) -> float:
        """Get timeout factor based on risk level"""
        timeout_factors = {
            "low": 2.0,
            "medium": 3.0,
            "high": 5.0,
            "critical": 10.0,  # Extra time for critical components
        }
        return timeout_factors.get(risk_level, 3.0)

    def _get_frontend_mutation_patterns(self) -> List[str]:
        """Get mutation patterns for frontend code"""
        return [
            "src/**/*.ts",
            "src/**/*.tsx",
            "!src/**/*.test.ts",
            "!src/**/*.test.tsx",
            "!src/**/*.spec.ts",
            "!src/**/*.spec.tsx",
            "!src/test-utils/**",
            "!src/mocks/**",
        ]

    def _get_excluded_mutations_for_frontend(self) -> List[str]:
        """Get excluded mutations for frontend to avoid breaking critical UI"""
        return [
            "StringLiteral",  # Don't mutate strings (could break labels/messages)
            "ObjectLiteral",  # Don't mutate object literals (could break configs)
            "ArrayDeclaration",  # Don't mutate array declarations
        ]

    def create_mutmut_config_file(self, component: str) -> str:
        """Create mutmut configuration file for component"""
        config = self.get_mutmut_config(component)

        # Create component-specific config directory
        config_dir = Path(".claude-tdd/mutation/configs")
        config_dir.mkdir(exist_ok=True)

        config_file = config_dir / f"mutmut_{component}.conf"

        # Write mutmut config format
        with open(config_file, "w") as f:
            f.write(f"[mutmut]\n")
            f.write(f"paths_to_mutate = {','.join(config['paths_to_mutate'])}\n")
            f.write(f"backup = {str(config['backup']).lower()}\n")
            f.write(f"runner = {config['runner']}\n")
            f.write(f"tests_dir = {config['tests_dir']}\n")

            if config["paths_to_exclude"]:
                f.write(f"paths_to_exclude = {','.join(config['paths_to_exclude'])}\n")

        print(f"Created mutmut config: {config_file}")
        return str(config_file)

    def create_stryker_config_file(self, component: str) -> str:
        """Create Stryker configuration file for component"""
        config = self.get_stryker_config(component)

        config_dir = Path(".claude-tdd/mutation/configs")
        config_dir.mkdir(exist_ok=True)

        config_file = config_dir / f"stryker_{component}.conf.js"

        # Write Stryker JavaScript config
        with open(config_file, "w") as f:
            f.write("module.exports = ")
            f.write(json.dumps(config, indent=2))
            f.write(";\n")

        print(f"Created Stryker config: {config_file}")
        return str(config_file)

    def validate_mutation_safety(self, component: str, file_path: str) -> bool:
        """Validate if file is safe to mutate based on financial rules"""
        file_path_lower = file_path.lower()

        # Check for immutable operations
        for operation in self.financial_rules.immutable_operations:
            if operation in file_path_lower:
                print(
                    f"SKIPPING {file_path}: Contains immutable operation '{operation}'"
                )
                return False

        # Check for critical financial calculations - extra care needed
        critical_operations = (
            self.financial_rules.price_calculations
            + self.financial_rules.risk_calculations
        )

        for operation in critical_operations:
            if operation in file_path_lower:
                print(
                    f"WARNING: {file_path} contains critical operation '{operation}' - using conservative mutation"
                )

        return True

    def get_mutation_report_config(self) -> Dict[str, Any]:
        """Get configuration for mutation testing reports"""
        return {
            "formats": ["html", "json", "markdown"],
            "output_dir": ".claude-tdd/mutation/reports",
            "include_survived_mutants": True,
            "include_killed_mutants": False,  # Too verbose for large projects
            "quality_gates": {
                "minimum_score": self.config["mutation"]["thresholds"]["minimum_score"],
                "target_score": self.config["mutation"]["thresholds"]["target_score"],
                "fail_fast": True,
            },
            "financial_analysis": {
                "group_by_risk_level": True,
                "highlight_critical_survivors": True,
                "show_financial_function_coverage": True,
            },
        }


def main():
    """Main entry point for advanced mutation configuration"""
    import argparse

    parser = argparse.ArgumentParser(
        description="FXML4 Advanced Mutation Configuration"
    )
    parser.add_argument(
        "--component", "-c", required=True, help="Component to generate config for"
    )
    parser.add_argument(
        "--type",
        "-t",
        choices=["mutmut", "stryker"],
        default="mutmut",
        help="Type of config to generate",
    )
    parser.add_argument(
        "--validate",
        "-v",
        action="store_true",
        help="Validate mutation safety for component files",
    )

    args = parser.parse_args()

    config_manager = AdvancedMutationConfig()

    if args.validate:
        # Validate all files in component for mutation safety
        component_config = config_manager.config["components"][args.component]
        component_path = Path(component_config["path"])

        print(f"Validating mutation safety for component: {args.component}")
        safe_files = []
        unsafe_files = []

        for file_path in component_path.rglob("*.py"):
            if config_manager.validate_mutation_safety(args.component, str(file_path)):
                safe_files.append(file_path)
            else:
                unsafe_files.append(file_path)

        print(f"\nSafe to mutate: {len(safe_files)} files")
        print(f"Unsafe to mutate: {len(unsafe_files)} files")

        if unsafe_files:
            print("\nUnsafe files:")
            for file_path in unsafe_files:
                print(f"  - {file_path}")

    elif args.type == "mutmut":
        config_file = config_manager.create_mutmut_config_file(args.component)
        print(f"Generated mutmut config: {config_file}")

    elif args.type == "stryker":
        config_file = config_manager.create_stryker_config_file(args.component)
        print(f"Generated Stryker config: {config_file}")


if __name__ == "__main__":
    main()
