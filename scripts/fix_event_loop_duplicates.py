#!/usr/bin/env python3
"""
Fix Event Loop Duplicate Definitions in Test Suite
==================================================

This script removes duplicate event loop fixture definitions from test files
and ensures they all use the centralized version from event_loop_fixtures.py
"""

import os
import re
from pathlib import Path
from typing import List, Tuple


def find_event_loop_definitions(file_path: Path) -> List[Tuple[int, int]]:
    """
    Find event loop fixture definitions in a file.

    Returns list of (start_line, end_line) tuples for each definition.
    """
    with open(file_path, "r") as f:
        lines = f.readlines()

    definitions = []
    in_fixture = False
    start_line = 0
    indent_level = 0

    for i, line in enumerate(lines):
        # Check for event loop fixture definition
        if re.match(r"^@pytest\.fixture.*\)?\s*$", line.strip()):
            # Check if next line defines event_loop
            if i + 1 < len(lines) and "def event_loop" in lines[i + 1]:
                in_fixture = True
                start_line = i
                # Get indentation level of the def line
                indent_level = len(lines[i + 1]) - len(lines[i + 1].lstrip())
        elif in_fixture:
            # Check if we've exited the function (dedented or new function)
            current_indent = len(line) - len(line.lstrip())
            if (
                line.strip()
                and current_indent <= indent_level
                and not line.strip().startswith("#")
            ):
                # Found end of fixture
                definitions.append((start_line, i - 1))
                in_fixture = False

    # Handle case where fixture goes to end of file
    if in_fixture:
        definitions.append((start_line, len(lines) - 1))

    return definitions


def remove_event_loop_fixtures(file_path: Path) -> bool:
    """
    Remove event loop fixture definitions from a file.

    Returns True if file was modified.
    """
    definitions = find_event_loop_definitions(file_path)

    if not definitions:
        return False

    with open(file_path, "r") as f:
        lines = f.readlines()

    # Remove definitions in reverse order to preserve line numbers
    for start, end in reversed(definitions):
        # Remove the lines
        del lines[start : end + 1]

        # Clean up extra blank lines
        while start < len(lines) and start > 0:
            if lines[start - 1].strip() == "" and lines[start].strip() == "":
                del lines[start]
            else:
                break

    # Check if we need to add import
    needs_import = True
    for line in lines:
        if "from tests.fixtures.event_loop_fixtures import" in line:
            needs_import = False
            break

    if needs_import:
        # Find where to add import (after other imports)
        import_line = -1
        for i, line in enumerate(lines):
            if line.startswith("import ") or line.startswith("from "):
                import_line = i

        if import_line >= 0:
            # Add import after last import
            lines.insert(import_line + 1, "\n")
            lines.insert(import_line + 2, "# Use centralized event loop fixture\n")
            lines.insert(
                import_line + 3,
                "from tests.fixtures.event_loop_fixtures import event_loop\n",
            )

    # Write back the modified content
    with open(file_path, "w") as f:
        f.writelines(lines)

    return True


def main():
    """Main function to process all test files."""
    project_root = Path(__file__).parent.parent
    test_dir = project_root / "tests"

    # Files to exclude from processing
    exclude_files = {
        "conftest.py",  # Already handled manually
        "event_loop_fixtures.py",  # The centralized fixture file
    }

    modified_files = []

    # Process all Python test files
    for test_file in test_dir.rglob("*.py"):
        if test_file.name in exclude_files:
            continue

        # Check if file contains event_loop fixture
        if test_file.is_file():
            with open(test_file, "r") as f:
                content = f.read()
                if "def event_loop" in content:
                    print(f"Processing: {test_file.relative_to(project_root)}")
                    if remove_event_loop_fixtures(test_file):
                        modified_files.append(test_file)
                        print(f"  ✓ Removed duplicate event_loop fixture")

    # Summary
    print("\n" + "=" * 60)
    print(f"Event Loop Fixture Cleanup Complete")
    print("=" * 60)
    print(f"Files modified: {len(modified_files)}")

    if modified_files:
        print("\nModified files:")
        for f in modified_files:
            print(f"  - {f.relative_to(project_root)}")

    print("\nAll test files now use the centralized event_loop fixture from:")
    print("  tests/fixtures/event_loop_fixtures.py")

    return 0


if __name__ == "__main__":
    exit(main())
