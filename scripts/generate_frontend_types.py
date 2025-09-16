#!/usr/bin/env python3
"""
Generate TypeScript types from Pydantic schemas for frontend-backend type consistency.

This script extracts all Pydantic models from the FXML4 API and generates
corresponding TypeScript interfaces for the frontend.
"""

import ast
import importlib.util
import inspect
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from datetime import datetime
    from enum import Enum
    from typing import get_args, get_origin
    from uuid import UUID

    from pydantic import BaseModel
    from pydantic.fields import FieldInfo
except ImportError as e:
    print(f"Error importing required modules: {e}")
    sys.exit(1)


class TypeScriptGenerator:
    """Generate TypeScript types from Pydantic models."""

    def __init__(self):
        self.generated_types: Set[str] = set()
        self.type_definitions: List[str] = []
        self.imports: Set[str] = set()

    def python_to_typescript_type(self, python_type: Any) -> str:
        """Convert Python type annotations to TypeScript types."""
        if python_type is None or python_type is type(None):
            return "null"

        # Handle basic types
        if python_type == int:
            return "number"
        elif python_type == float:
            return "number"
        elif python_type == str:
            return "string"
        elif python_type == bool:
            return "boolean"
        elif python_type == datetime:
            return "string"  # ISO string format
        elif python_type == UUID:
            return "string"

        # Handle generic types
        origin = get_origin(python_type)
        args = get_args(python_type)

        if origin is Union:
            # Handle Optional[T] -> T | null
            if len(args) == 2 and type(None) in args:
                non_null_type = args[0] if args[1] is type(None) else args[1]
                return f"{self.python_to_typescript_type(non_null_type)} | null"
            # Handle Union types
            union_types = [self.python_to_typescript_type(arg) for arg in args]
            return " | ".join(union_types)

        if origin is list or origin is List:
            if args:
                item_type = self.python_to_typescript_type(args[0])
                return f"{item_type}[]"
            return "any[]"

        if origin is dict or origin is Dict:
            if args and len(args) == 2:
                key_type = self.python_to_typescript_type(args[0])
                value_type = self.python_to_typescript_type(args[1])
                return f"Record<{key_type}, {value_type}>"
            return "Record<string, any>"

        # Handle Pydantic models
        if inspect.isclass(python_type) and issubclass(python_type, BaseModel):
            return python_type.__name__

        # Handle Enums
        if inspect.isclass(python_type) and issubclass(python_type, Enum):
            return python_type.__name__

        # Fallback
        if hasattr(python_type, "__name__"):
            return python_type.__name__

        return "any"

    def generate_enum_type(self, enum_class: type) -> str:
        """Generate TypeScript enum from Python Enum."""
        if not issubclass(enum_class, Enum):
            return ""

        enum_name = enum_class.__name__
        if enum_name in self.generated_types:
            return ""

        self.generated_types.add(enum_name)

        # Get enum values
        enum_values = []
        for member in enum_class:
            if isinstance(member.value, str):
                enum_values.append(f'  {member.name} = "{member.value}"')
            else:
                enum_values.append(f"  {member.name} = {member.value}")

        enum_def = f"""export enum {enum_name} {{
{chr(10).join(enum_values)}
}}"""

        return enum_def

    def generate_interface(self, model_class: type) -> str:
        """Generate TypeScript interface from Pydantic model."""
        if not issubclass(model_class, BaseModel):
            return ""

        interface_name = model_class.__name__
        if interface_name in self.generated_types:
            return ""

        self.generated_types.add(interface_name)

        # Get model fields
        fields = []
        if hasattr(model_class, "__fields__"):
            for field_name, field_info in model_class.__fields__.items():
                field_type = field_info.type_
                ts_type = self.python_to_typescript_type(field_type)

                # Check if field is optional
                is_optional = (
                    field_info.allow_none
                    or field_info.default is not None
                    or field_info.default_factory is not None
                )
                optional_marker = "?" if is_optional else ""

                # Add field description if available
                description = ""
                if (
                    field_info.field_info
                    and hasattr(field_info.field_info, "description")
                    and field_info.field_info.description
                ):
                    description = f"  /** {field_info.field_info.description} */\n"

                fields.append(
                    f"{description}  {field_name}{optional_marker}: {ts_type};"
                )

        # Create interface
        interface_def = f"""export interface {interface_name} {{
{chr(10).join(fields)}
}}"""

        return interface_def

    def scan_module_for_models(self, module_path: Path) -> List[type]:
        """Scan a Python module for Pydantic models and Enums."""
        models = []

        try:
            spec = importlib.util.spec_from_file_location("module", module_path)
            if spec is None or spec.loader is None:
                return models

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Find all classes in the module
            for name, obj in inspect.getmembers(module, inspect.isclass):
                # Skip imported classes
                if obj.__module__ != module.__name__:
                    continue

                # Check if it's a Pydantic model or Enum
                if issubclass(obj, BaseModel) or issubclass(obj, Enum):
                    models.append(obj)

        except Exception as e:
            print(f"Warning: Could not scan {module_path}: {e}")

        return models

    def generate_types_from_directory(self, directory: Path) -> None:
        """Scan directory for Python files and extract Pydantic models."""
        for py_file in directory.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue

            models = self.scan_module_for_models(py_file)

            for model in models:
                if issubclass(model, Enum):
                    enum_def = self.generate_enum_type(model)
                    if enum_def:
                        self.type_definitions.append(enum_def)
                elif issubclass(model, BaseModel):
                    interface_def = self.generate_interface(model)
                    if interface_def:
                        self.type_definitions.append(interface_def)

    def generate_typescript_file(self) -> str:
        """Generate complete TypeScript definitions file."""
        header = """/**
 * Auto-generated TypeScript types from FXML4 Pydantic schemas
 *
 * DO NOT EDIT MANUALLY - This file is generated automatically
 * Run `python scripts/generate_frontend_types.py` to regenerate
 */

"""

        # Add utility types
        utility_types = """// Utility types
export type LoadingState = 'idle' | 'loading' | 'success' | 'error';
export type SortOrder = 'asc' | 'desc';

// API Response wrapper
export interface ApiResponse<T = any> {
  success: boolean;
  data?: T;
  error?: string;
  message?: string;
  timestamp: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

"""

        # Combine all parts
        content = header + utility_types + "\n\n".join(self.type_definitions) + "\n"

        return content


def main():
    """Main function to generate TypeScript types."""
    print("🔄 Generating TypeScript types from Pydantic schemas...")

    # Initialize generator
    generator = TypeScriptGenerator()

    # Scan API directories for Pydantic models
    api_dir = project_root / "fxml4" / "api"
    if api_dir.exists():
        print(f"📂 Scanning {api_dir}")
        generator.generate_types_from_directory(api_dir)

    # Scan other relevant directories
    for dir_name in ["fxml4/ml", "fxml4/brokers", "fxml4/backtesting"]:
        scan_dir = project_root / dir_name
        if scan_dir.exists():
            print(f"📂 Scanning {scan_dir}")
            generator.generate_types_from_directory(scan_dir)

    # Generate TypeScript file
    ts_content = generator.generate_typescript_file()

    # Write to frontend types directory
    frontend_types_dir = project_root / "fxml4-ui" / "src" / "types"
    frontend_types_dir.mkdir(parents=True, exist_ok=True)

    output_file = frontend_types_dir / "api-generated.ts"

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(ts_content)

    print(f"✅ Generated {len(generator.generated_types)} types")
    print(f"📄 Wrote TypeScript definitions to {output_file}")

    # Generate summary
    print(f"\n📊 Summary:")
    print(f"   - Total types generated: {len(generator.generated_types)}")
    print(f"   - Generated types: {', '.join(sorted(generator.generated_types))}")

    # Update main types index
    update_types_index(frontend_types_dir)

    print("✅ Frontend types generation complete!")


def update_types_index(types_dir: Path):
    """Update the main types index file to include generated types."""
    index_file = types_dir / "index.ts"

    # Read existing content
    existing_content = ""
    if index_file.exists():
        with open(index_file, "r", encoding="utf-8") as f:
            existing_content = f.read()

    # Add export for generated types if not already present
    export_line = 'export * from "./api-generated";'
    if export_line not in existing_content:
        # Add at the end
        new_content = (
            existing_content.rstrip()
            + f"\n\n// Auto-generated API types\n{export_line}\n"
        )

        with open(index_file, "w", encoding="utf-8") as f:
            f.write(new_content)

        print(f"📝 Updated {index_file} with generated types export")


if __name__ == "__main__":
    main()
