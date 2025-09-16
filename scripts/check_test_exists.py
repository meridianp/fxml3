#!/usr/bin/env python3
"""
TDD enforcement script - Ensures tests exist for source files.

This script checks that every source file has a corresponding test file,
enforcing Test-Driven Development practices.
"""

import os
import sys
from pathlib import Path


def find_test_file(source_file: str) -> bool:
    """
    Check if a test file exists for the given source file.

    Args:
        source_file: Path to the source file

    Returns:
        True if test file exists, False otherwise
    """
    source_path = Path(source_file)

    # Skip certain files that don't need tests
    skip_patterns = [
        "__init__.py",
        "conftest.py",
        "setup.py",
        "__pycache__",
        ".pyc",
    ]

    for pattern in skip_patterns:
        if pattern in str(source_path):
            return True

    # Determine test file path
    # Example: core/api/auth/service.py -> tests/unit/api/auth/test_service.py
    parts = source_path.parts

    if "core" in parts:
        # Remove 'core' and construct test path
        core_idx = parts.index("core")
        relative_parts = parts[core_idx + 1 :]

        # Handle both unit and integration test locations
        test_locations = [
            Path("tests")
            / "unit"
            / Path(*relative_parts[:-1])
            / f"test_{relative_parts[-1]}",
            Path("tests")
            / "integration"
            / Path(*relative_parts[:-1])
            / f"test_{relative_parts[-1]}",
            Path("core")
            / "tests"
            / "unit"
            / Path(*relative_parts[:-1])
            / f"test_{relative_parts[-1]}",
            Path("core")
            / "tests"
            / "integration"
            / Path(*relative_parts[:-1])
            / f"test_{relative_parts[-1]}",
        ]
    elif "src" in parts:
        # TypeScript/React files
        src_idx = parts.index("src")
        relative_parts = parts[src_idx + 1 :]

        # Handle .ts, .tsx files -> .test.ts, .test.tsx
        filename = relative_parts[-1]
        base_name = filename.rsplit(".", 1)[0]
        extension = filename.rsplit(".", 1)[1] if "." in filename else ""

        test_locations = [
            Path("tests")
            / Path(*relative_parts[:-1])
            / f"{base_name}.test.{extension}",
            Path("tests")
            / Path(*relative_parts[:-1])
            / f"{base_name}.spec.{extension}",
            source_path.parent / f"{base_name}.test.{extension}",
            source_path.parent / f"{base_name}.spec.{extension}",
        ]
    else:
        # Default pattern
        filename = source_path.name
        base_name = filename.rsplit(".", 1)[0]

        test_locations = [
            source_path.parent / "tests" / f"test_{filename}",
            source_path.parent / f"test_{filename}",
            Path("tests") / f"test_{filename}",
        ]

    # Check if any test file exists
    for test_path in test_locations:
        if test_path.exists():
            return True

    return False


def main():
    """
    Main entry point for the test checker.

    Exits with code 1 if tests are missing, 0 otherwise.
    """
    # Get files to check from command line or stdin
    files_to_check = sys.argv[1:] if len(sys.argv) > 1 else []

    if not files_to_check:
        # Read from stdin (pre-commit passes files this way)
        files_to_check = [line.strip() for line in sys.stdin if line.strip()]

    missing_tests = []

    for source_file in files_to_check:
        if not find_test_file(source_file):
            missing_tests.append(source_file)

    if missing_tests:
        print("❌ TDD Violation: The following files are missing tests:")
        for file in missing_tests:
            print(f"  - {file}")
        print(
            "\n📝 Remember: Write tests FIRST, then implementation (Red-Green-Refactor)"
        )
        print("📚 See docs/TDD_PLAYBOOK.md for TDD guidelines")
        sys.exit(1)

    print("✅ All source files have corresponding tests")
    sys.exit(0)


if __name__ == "__main__":
    main()
