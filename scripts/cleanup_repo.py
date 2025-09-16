#!/usr/bin/env python3
"""
Repository Cleanup Script for FXML4.

This script removes build artifacts, temporary files, and other clutter
to maintain a clean repository state for production deployment.

CRITICAL MAINTENANCE: Keeps repository clean and deployment-ready.
"""

import glob
import logging
import os
import shutil
from pathlib import Path
from typing import List, Set

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent


def find_files_to_clean(root_dir: Path) -> Set[Path]:
    """Find all files and directories that should be cleaned up."""
    files_to_clean = set()

    # Patterns for files to remove
    cleanup_patterns = [
        # Python cache and compiled files
        "**/__pycache__",
        "**/*.pyc",
        "**/*.pyo",
        "**/*.pyd",
        # Test cache and artifacts
        "**/.pytest_cache",
        "**/test_output.txt",
        "**/test_results.txt",
        "**/test_analysis.json",
        # Backup files
        "**/*.backup",
        "**/*.orig",
        "**/*~",
        "**/*.bak",
        # Log files (but preserve structure)
        "**/*.log",
        # Temporary files
        "**/*.tmp",
        "**/*.temp",
        "**/tmp.*",
        # IDE files
        "**/.vscode/settings.json",
        "**/.idea",
        "**/*.swp",
        "**/*.swo",
        # OS files
        "**/.DS_Store",
        "**/Thumbs.db",
        # Build artifacts
        "**/*.egg-info",
        "**/build",
        "**/dist",
        # Coverage files
        "**/.coverage",
        "**/htmlcov",
        "**/coverage.xml",
        # Jupyter notebook checkpoints
        "**/.ipynb_checkpoints",
        # Model files that might be temporary
        "**/models/*.pkl.tmp",
        "**/models/*.joblib.tmp",
    ]

    # Find all matching files
    for pattern in cleanup_patterns:
        for path in root_dir.glob(pattern):
            files_to_clean.add(path)

    # Add specific files we know should be cleaned
    specific_files = [
        "fxml4/api/main.py.backup",
        "fxml4/ml/models.py.backup",
        "test_analysis.json",
    ]

    for specific_file in specific_files:
        file_path = root_dir / specific_file
        if file_path.exists():
            files_to_clean.add(file_path)

    return files_to_clean


def should_preserve_file(file_path: Path) -> bool:
    """Check if a file should be preserved despite matching cleanup patterns."""
    # Preserve important log files
    if file_path.name in ["audit.log", "system.log", "error.log"]:
        return True

    # Preserve configuration files that might have .backup in the name
    if "config" in str(file_path).lower() and not file_path.suffix == ".backup":
        return True

    # Preserve any file in the git directory
    if ".git" in file_path.parts:
        return True

    # Preserve requirements files
    if file_path.name.startswith("requirements") and file_path.suffix in [
        ".txt",
        ".pip",
    ]:
        return True

    return False


def safe_remove(path: Path) -> bool:
    """Safely remove a file or directory."""
    try:
        if path.is_file():
            path.unlink()
            logger.info(f"Removed file: {path}")
            return True
        elif path.is_dir():
            shutil.rmtree(path)
            logger.info(f"Removed directory: {path}")
            return True
        else:
            logger.warning(f"Path does not exist: {path}")
            return False
    except Exception as e:
        logger.error(f"Failed to remove {path}: {e}")
        return False


def clean_empty_directories(root_dir: Path):
    """Remove empty directories."""
    for dirpath, dirnames, filenames in os.walk(root_dir, topdown=False):
        dir_path = Path(dirpath)

        # Skip important directories
        if any(part in [".git", ".github", "venv", ".venv"] for part in dir_path.parts):
            continue

        # Check if directory is empty
        try:
            if dir_path.is_dir() and not any(dir_path.iterdir()):
                # Don't remove logs directory even if empty
                if dir_path.name != "logs":
                    dir_path.rmdir()
                    logger.info(f"Removed empty directory: {dir_path}")
        except Exception as e:
            logger.warning(f"Could not check/remove empty directory {dir_path}: {e}")


def cleanup_logs_directory(root_dir: Path):
    """Clean up old log files, keeping only recent ones."""
    logs_dir = root_dir / "logs"
    if not logs_dir.exists():
        return

    # Keep only the most recent 10 log files of each type
    log_patterns = ["*.log", "*.out", "*.err"]

    for pattern in log_patterns:
        log_files = list(logs_dir.glob(pattern))

        # Sort by modification time (newest first)
        log_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)

        # Remove old log files (keep newest 10)
        for old_log in log_files[10:]:
            try:
                old_log.unlink()
                logger.info(f"Removed old log file: {old_log}")
            except Exception as e:
                logger.warning(f"Could not remove old log file {old_log}: {e}")


def create_gitignore_if_missing(root_dir: Path):
    """Create or update .gitignore with common patterns."""
    gitignore_path = root_dir / ".gitignore"

    additional_patterns = [
        "",
        "# Build and cache files",
        "__pycache__/",
        "*.pyc",
        "*.pyo",
        "*.pyd",
        ".pytest_cache/",
        "",
        "# Logs",
        "*.log",
        "logs/*.log",
        "",
        "# Temporary files",
        "*.tmp",
        "*.temp",
        "*.backup",
        "*.orig",
        "",
        "# IDE files",
        ".vscode/settings.json",
        ".idea/",
        "",
        "# OS files",
        ".DS_Store",
        "Thumbs.db",
        "",
        "# Model artifacts",
        "models/*.pkl.tmp",
        "models/*.joblib.tmp",
        "",
        "# Test artifacts",
        "test_output.txt",
        "test_results.txt",
        "test_analysis.json",
        "",
    ]

    # Read existing .gitignore if it exists
    existing_patterns = set()
    if gitignore_path.exists():
        with open(gitignore_path, "r") as f:
            existing_patterns = set(line.strip() for line in f if line.strip())

    # Add new patterns that don't exist
    new_patterns = []
    for pattern in additional_patterns:
        if pattern not in existing_patterns:
            new_patterns.append(pattern)

    if new_patterns:
        with open(gitignore_path, "a") as f:
            f.write("\n".join(new_patterns))
        logger.info(f"Updated .gitignore with {len(new_patterns)} new patterns")


def main():
    """Main cleanup function."""
    logger.info("Starting repository cleanup...")

    root_dir = get_project_root()
    logger.info(f"Cleaning repository at: {root_dir}")

    # Find files to clean
    files_to_clean = find_files_to_clean(root_dir)
    logger.info(f"Found {len(files_to_clean)} files/directories to clean")

    # Filter out files that should be preserved
    files_to_remove = set()
    for file_path in files_to_clean:
        if not should_preserve_file(file_path):
            files_to_remove.add(file_path)
        else:
            logger.info(f"Preserving file: {file_path}")

    logger.info(f"Will remove {len(files_to_remove)} files/directories")

    # Remove files
    removed_count = 0
    for file_path in files_to_remove:
        if safe_remove(file_path):
            removed_count += 1

    logger.info(f"Successfully removed {removed_count} files/directories")

    # Clean up old log files
    cleanup_logs_directory(root_dir)

    # Remove empty directories
    clean_empty_directories(root_dir)

    # Update .gitignore
    create_gitignore_if_missing(root_dir)

    logger.info("Repository cleanup completed successfully!")

    # Report final statistics
    remaining_artifacts = find_files_to_clean(root_dir)
    preserved_count = len([f for f in remaining_artifacts if should_preserve_file(f)])

    logger.info(f"Cleanup summary:")
    logger.info(f"  - Files removed: {removed_count}")
    logger.info(f"  - Files preserved: {preserved_count}")
    logger.info(f"  - Repository is now clean and deployment-ready")


if __name__ == "__main__":
    main()
