#!/usr/bin/env python3.12
"""
AI Workflow Validator for Pre-commit Hook
Validates GitHub Actions workflows and AI configuration before commit
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml


def validate_workflow_syntax(workflow_path: Path) -> Tuple[bool, List[str]]:
    """Validate GitHub Actions workflow YAML syntax."""
    errors = []

    try:
        with open(workflow_path, "r") as f:
            workflow = yaml.safe_load(f)
    except yaml.YAMLError as e:
        errors.append(f"YAML syntax error in {workflow_path}: {e}")
        return False, errors
    except FileNotFoundError:
        errors.append(f"Workflow file not found: {workflow_path}")
        return False, errors

    # Validate required top-level keys
    # Note: YAML parses 'on:' as boolean True, so we need to check for both
    required_keys = [("name", "name"), ("on", True), ("jobs", "jobs")]
    for key_name, key_value in required_keys:
        if key_value not in workflow:
            errors.append(f"Missing required key '{key_name}' in {workflow_path}")
        else:
            # Additional validation for key presence
            if key_name == "on" and not workflow.get(True):
                errors.append(f"Key '{key_name}' is empty in {workflow_path}")
            elif key_name == "jobs" and not workflow.get("jobs"):
                errors.append(f"Key '{key_name}' is empty in {workflow_path}")
            elif key_name == "name" and not workflow.get("name"):
                errors.append(f"Key '{key_name}' is empty in {workflow_path}")

    # Validate AI-specific requirements
    if "ai-" in workflow_path.name:
        if not validate_ai_workflow_requirements(workflow, workflow_path, errors):
            return False, errors

    return len(errors) == 0, errors


def validate_ai_workflow_requirements(
    workflow: Dict, workflow_path: Path, errors: List[str]
) -> bool:
    """Validate AI-specific workflow requirements."""
    # Check for AI environment variables
    required_ai_env = ["AI_PROVIDER", "AI_MODEL"]

    if "env" in workflow:
        for var in required_ai_env:
            if var not in workflow["env"]:
                errors.append(
                    f"Missing required AI environment variable '{var}' in {workflow_path}"
                )
    else:
        errors.append(f"Missing 'env' section with AI configuration in {workflow_path}")

    # Check for OpenAI API key secret usage
    workflow_str = str(workflow)
    if "OPENAI_API_KEY" not in workflow_str:
        errors.append(f"Missing OPENAI_API_KEY secret reference in {workflow_path}")

    # Validate job structure for AI workflows
    jobs = workflow.get("jobs", {})
    if not jobs:
        errors.append(f"No jobs defined in AI workflow {workflow_path}")
        return False

    # Check for Codex CLI installation step
    codex_found = False
    for job_name, job in jobs.items():
        steps = job.get("steps", [])
        for step in steps:
            step_name = step.get("name", "").lower()
            step_run = step.get("run", "").lower()
            if (
                "codex" in step_name
                or "codex" in step_run
                or "@openai/codex" in step_run
            ):
                codex_found = True
                break
        if codex_found:
            break

    if not codex_found:
        errors.append(f"No Codex CLI installation found in AI workflow {workflow_path}")

    return len(errors) == 0


def validate_ai_config_files() -> Tuple[bool, List[str]]:
    """Validate AI configuration files."""
    errors = []
    config_files = {
        ".ai/tests.yaml": validate_tests_config,
        ".ai/quality-gates.json": validate_quality_gates_config,
    }

    for config_path, validator in config_files.items():
        if Path(config_path).exists():
            valid, file_errors = validator(Path(config_path))
            if not valid:
                errors.extend(file_errors)
        else:
            errors.append(f"Required AI config file missing: {config_path}")

    return len(errors) == 0, errors


def validate_tests_config(config_path: Path) -> Tuple[bool, List[str]]:
    """Validate .ai/tests.yaml configuration."""
    errors = []

    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        errors.append(f"YAML syntax error in {config_path}: {e}")
        return False, errors

    # Validate required sections
    required_sections = ["global", "backend", "quality_gates"]
    for section in required_sections:
        if section not in config:
            errors.append(f"Missing required section '{section}' in {config_path}")

    # Validate coverage thresholds
    if "global" in config and "coverage" in config["global"]:
        coverage = config["global"]["coverage"]
        if "minimum_threshold" not in coverage:
            errors.append(f"Missing minimum_threshold in coverage config")
        elif coverage["minimum_threshold"] < 60:
            errors.append(
                f"Coverage threshold too low: {coverage['minimum_threshold']}% (minimum 60%)"
            )

    return len(errors) == 0, errors


def validate_quality_gates_config(config_path: Path) -> Tuple[bool, List[str]]:
    """Validate .ai/quality-gates.json configuration."""
    errors = []

    try:
        with open(config_path, "r") as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        errors.append(f"JSON syntax error in {config_path}: {e}")
        return False, errors

    # Validate required sections
    if "quality_gates" not in config:
        errors.append(f"Missing 'quality_gates' section in {config_path}")
        return False, errors

    quality_gates = config["quality_gates"]
    required_sections = ["coverage", "testing", "security", "code_quality"]
    for section in required_sections:
        if section not in quality_gates:
            errors.append(f"Missing required section '{section}' in quality_gates")

    # Validate coverage requirements
    if "coverage" in quality_gates:
        coverage = quality_gates["coverage"]
        if coverage.get("minimum_overall", 0) < 80:
            errors.append(
                f"Overall coverage threshold too low: {coverage.get('minimum_overall')}% (minimum 80%)"
            )
        if coverage.get("minimum_api", 0) < 94:
            errors.append(
                f"API coverage threshold too low: {coverage.get('minimum_api')}% (minimum 94%)"
            )

    return len(errors) == 0, errors


def validate_codex_config() -> Tuple[bool, List[str]]:
    """Validate Codex CLI configuration."""
    errors = []
    codex_config_path = Path.home() / ".codex" / "config.toml"

    if not codex_config_path.exists():
        errors.append(f"Codex configuration not found: {codex_config_path}")
        return False, errors

    try:
        with open(codex_config_path, "r") as f:
            config_content = f.read()
    except Exception as e:
        errors.append(f"Error reading Codex config: {e}")
        return False, errors

    # Check for required configuration
    required_configs = ['model = "gpt-5"', 'provider = "openai"', "[profiles.fxml4_ci]"]
    for config in required_configs:
        if config not in config_content:
            errors.append(f"Missing required Codex configuration: {config}")

    return len(errors) == 0, errors


def check_ai_dependencies() -> Tuple[bool, List[str]]:
    """Check if AI dependencies are available."""
    errors = []

    # Check if Codex CLI is installed
    import subprocess

    try:
        result = subprocess.run(
            ["codex", "--version"], capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            errors.append("Codex CLI not working properly")
    except subprocess.TimeoutExpired:
        errors.append("Codex CLI timeout - may not be installed")
    except FileNotFoundError:
        errors.append("Codex CLI not installed (run: npm install -g @openai/codex)")

    # Check Node.js for Codex CLI
    try:
        result = subprocess.run(
            ["node", "--version"], capture_output=True, text=True, timeout=5
        )
        if result.returncode != 0:
            errors.append("Node.js not available (required for Codex CLI)")
    except (subprocess.TimeoutExpired, FileNotFoundError):
        errors.append("Node.js not installed (required for Codex CLI)")

    return len(errors) == 0, errors


def main():
    parser = argparse.ArgumentParser(description="Validate AI workflow configuration")
    parser.add_argument(
        "--check-workflows",
        action="store_true",
        help="Validate GitHub Actions workflows",
    )
    parser.add_argument(
        "--check-config", action="store_true", help="Validate AI configuration files"
    )
    parser.add_argument(
        "--check-dependencies", action="store_true", help="Check AI tool dependencies"
    )
    parser.add_argument("files", nargs="*", help="Specific files to validate")

    args = parser.parse_args()

    # If no specific checks requested, do all
    if not any([args.check_workflows, args.check_config, args.check_dependencies]):
        args.check_workflows = True
        args.check_config = True
        args.check_dependencies = True

    all_errors = []
    exit_code = 0

    # Validate workflows
    if args.check_workflows:
        workflow_dir = Path(".github/workflows")
        if workflow_dir.exists():
            ai_workflows = list(workflow_dir.glob("ai-*.yml"))
            for workflow in ai_workflows:
                valid, errors = validate_workflow_syntax(workflow)
                if not valid:
                    all_errors.extend(errors)
                    exit_code = 1
                else:
                    print(f"✅ {workflow} - Valid")

        # Also validate specific files if provided
        for file_path in args.files:
            if file_path.endswith(".yml") and "workflows" in file_path:
                path = Path(file_path)
                if path.exists():
                    valid, errors = validate_workflow_syntax(path)
                    if not valid:
                        all_errors.extend(errors)
                        exit_code = 1

    # Validate AI config files
    if args.check_config:
        valid, errors = validate_ai_config_files()
        if not valid:
            all_errors.extend(errors)
            exit_code = 1
        else:
            print("✅ AI configuration files - Valid")

        # Validate Codex config
        valid, errors = validate_codex_config()
        if not valid:
            all_errors.extend(errors)
            exit_code = 1
        else:
            print("✅ Codex CLI configuration - Valid")

    # Check dependencies
    if args.check_dependencies:
        valid, errors = check_ai_dependencies()
        if not valid:
            all_errors.extend(errors)
            exit_code = 1
        else:
            print("✅ AI dependencies - Available")

    # Print all errors
    if all_errors:
        print("\n❌ AI Workflow Validation Errors:")
        for error in all_errors:
            print(f"  - {error}")
        print(f"\nFound {len(all_errors)} validation errors.")

        # Provide helpful suggestions
        print("\n💡 Suggestions:")
        print("  - Run: ./scripts/ai-cicd-setup.sh validate")
        print("  - Check: docs/runbooks/ai-ci.md")
        print("  - Install missing dependencies")
    else:
        print("\n✅ All AI workflow validations passed!")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
