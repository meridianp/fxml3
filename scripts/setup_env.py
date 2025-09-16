#!/usr/bin/env python3
"""
Environment setup script for FXML4.

This script sets up the development environment for FXML4, including:
- Creating a virtual environment
- Installing dependencies
- Setting up environment variables
- Creating necessary directories
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path


def run_command(command, cwd=None):
    """Run a shell command and return the exit code."""
    print(f"Running: {command}")
    result = subprocess.run(command, shell=True, cwd=cwd)
    return result.returncode


def create_virtual_environment(venv_path):
    """Create a Python virtual environment."""
    if os.path.exists(venv_path):
        print(f"Virtual environment already exists at {venv_path}")
        return 0

    print(f"Creating virtual environment at {venv_path}")
    return run_command(f"{sys.executable} -m venv {venv_path}")


def install_dependencies(venv_python, requirements_file):
    """Install dependencies from requirements.txt."""
    if not os.path.exists(requirements_file):
        print(f"Requirements file not found: {requirements_file}")
        return 1

    print("Upgrading pip")
    run_command(f"{venv_python} -m pip install --upgrade pip")

    print("Installing dependencies")
    return run_command(f"{venv_python} -m pip install -r {requirements_file}")


def create_env_file(template_file, output_file):
    """Create .env file from template if it doesn't exist."""
    if os.path.exists(output_file):
        print(f".env file already exists at {output_file}")
        return 0

    if not os.path.exists(template_file):
        print(f"Template file not found: {template_file}")
        return 1

    print(f"Creating .env file from template")
    with open(template_file, "r") as template, open(output_file, "w") as output:
        output.write(template.read())
    print(f"Created .env file at {output_file}")
    print("Please edit this file with your configuration values")
    return 0


def create_directories(directories):
    """Create necessary directories if they don't exist."""
    for directory in directories:
        if not os.path.exists(directory):
            print(f"Creating directory: {directory}")
            os.makedirs(directory)
        else:
            print(f"Directory already exists: {directory}")
    return 0


def install_dev_tools(venv_python):
    """Install development tools."""
    print("Installing development tools")
    dev_tools = [
        "black",
        "flake8",
        "mypy",
        "pytest",
        "pytest-cov",
        "isort",
    ]
    return run_command(f"{venv_python} -m pip install {' '.join(dev_tools)}")


def setup_git_hooks(project_root):
    """Set up Git hooks for the project."""
    hooks_dir = os.path.join(project_root, ".git", "hooks")
    if not os.path.exists(hooks_dir):
        print("Git repository not initialized. Skipping Git hooks setup.")
        return 0

    pre_commit_hook = os.path.join(hooks_dir, "pre-commit")
    print(f"Creating pre-commit hook at {pre_commit_hook}")

    with open(pre_commit_hook, "w") as f:
        f.write(
            """#!/bin/bash
# Pre-commit hook for FXML4

# Activate virtual environment
source venv/bin/activate

# Run linting and formatting checks
echo "Running style checks..."
black --check fxml4/ tests/
STYLE_RESULT=$?

echo "Running import sorting checks..."
isort --check-only fxml4/ tests/
IMPORT_RESULT=$?

echo "Running flake8 checks..."
flake8 fxml4/ tests/
FLAKE_RESULT=$?

# Deactivate virtual environment
deactivate

# Return error if any check failed
if [ $STYLE_RESULT -ne 0 ] || [ $IMPORT_RESULT -ne 0 ] || [ $FLAKE_RESULT -ne 0 ]; then
    echo "Pre-commit checks failed. Please fix the issues and try again."
    exit 1
fi

echo "All pre-commit checks passed."
exit 0
"""
        )

    os.chmod(pre_commit_hook, 0o755)
    return 0


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Set up the FXML4 development environment"
    )
    parser.add_argument("--venv", default="venv", help="Virtual environment directory")
    parser.add_argument(
        "--requirements", default="requirements.txt", help="Requirements file"
    )
    parser.add_argument(
        "--no-dev-tools",
        action="store_true",
        help="Skip development tools installation",
    )
    parser.add_argument(
        "--no-git-hooks", action="store_true", help="Skip Git hooks setup"
    )
    args = parser.parse_args()

    # Get project root directory
    project_root = os.path.dirname(os.path.abspath(__file__))
    os.chdir(project_root)

    # Define paths
    venv_path = os.path.join(project_root, args.venv)
    requirements_file = os.path.join(project_root, args.requirements)
    template_file = os.path.join(project_root, ".env.example")
    output_file = os.path.join(project_root, ".env")

    # Determine Python executable in virtual environment
    if os.name == "nt":  # Windows
        venv_python = os.path.join(venv_path, "Scripts", "python.exe")
    else:  # Unix-like
        venv_python = os.path.join(venv_path, "bin", "python")

    # Create directories
    directories = [
        os.path.join(project_root, "data"),
        os.path.join(project_root, "logs"),
        os.path.join(project_root, "output"),
    ]

    # Run setup steps
    steps = [
        (create_virtual_environment, (venv_path,), "Creating virtual environment"),
        (
            install_dependencies,
            (venv_python, requirements_file),
            "Installing dependencies",
        ),
        (create_env_file, (template_file, output_file), "Creating .env file"),
        (create_directories, (directories,), "Creating directories"),
    ]

    if not args.no_dev_tools:
        steps.append(
            (install_dev_tools, (venv_python,), "Installing development tools")
        )

    if not args.no_git_hooks:
        steps.append((setup_git_hooks, (project_root,), "Setting up Git hooks"))

    # Execute setup steps
    for func, func_args, description in steps:
        print(f"\n=== {description} ===")
        result = func(*func_args)
        if result != 0:
            print(f"Error during {description}. Exiting.")
            return result

    print("\n=== Setup completed successfully ===")

    # Print activation instructions
    if os.name == "nt":  # Windows
        activate_cmd = f"{args.venv}\\Scripts\\activate"
    else:  # Unix-like
        activate_cmd = f"source {args.venv}/bin/activate"

    print(f"\nTo activate the virtual environment, run:")
    print(f"  {activate_cmd}")
    print("\nTo start developing, run:")
    print("  python -m fxml4.main")

    return 0


if __name__ == "__main__":
    sys.exit(main())
