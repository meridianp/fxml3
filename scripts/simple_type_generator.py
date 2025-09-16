#!/usr/bin/env python3
"""
Simple TypeScript type generator from FXML4 Pydantic schemas.
"""

import re
from pathlib import Path


def extract_pydantic_models_from_file(file_path: Path) -> str:
    """Extract Pydantic models from a Python file and convert to TypeScript."""

    if not file_path.exists():
        return ""

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        print(f"Warning: Could not read {file_path}: {e}")
        return ""

    typescript_types = []

    # Extract enums
    enum_pattern = r'class\s+(\w+)\s*\([^)]*Enum[^)]*\):\s*"""([^"]*)"""\s*(.*?)(?=\n\n|\nclass|\n#|\Z)'
    enum_matches = re.finditer(enum_pattern, content, re.DOTALL)

    for match in enum_matches:
        enum_name = match.group(1)
        description = match.group(2).strip()
        enum_body = match.group(3)

        # Extract enum values
        value_pattern = r'(\w+)\s*=\s*["\']([^"\']+)["\']'
        values = re.findall(value_pattern, enum_body)

        if values:
            ts_enum = f"/** {description} */\nexport enum {enum_name} {{\n"
            for name, value in values:
                ts_enum += f'  {name} = "{value}",\n'
            ts_enum = ts_enum.rstrip(",\n") + "\n}\n\n"
            typescript_types.append(ts_enum)

    # Extract BaseModel classes
    model_pattern = r'class\s+(\w+)\s*\([^)]*BaseModel[^)]*\):\s*"""([^"]*)"""(.*?)(?=\nclass|\n#|\Z)'
    model_matches = re.finditer(model_pattern, content, re.DOTALL)

    for match in model_matches:
        model_name = match.group(1)
        description = match.group(2).strip()
        model_body = match.group(3)

        # Extract fields
        field_pattern = r"(\w+):\s*([^=\n]+?)(?:\s*=\s*[^\n]*)?(?:\n|$)"
        fields = re.findall(field_pattern, model_body)

        if fields:
            ts_interface = f"/** {description} */\nexport interface {model_name} {{\n"

            for field_name, field_type in fields:
                # Convert Python types to TypeScript
                ts_type = convert_python_to_ts_type(field_type.strip())

                # Check if field is optional (has Optional or default value)
                is_optional = (
                    "Optional" in field_type
                    or "= None" in model_body
                    or "= Field(" in model_body
                )
                optional_marker = "?" if is_optional else ""

                ts_interface += f"  {field_name}{optional_marker}: {ts_type};\n"

            ts_interface += "}\n\n"
            typescript_types.append(ts_interface)

    return "".join(typescript_types)


def convert_python_to_ts_type(python_type: str) -> str:
    """Convert Python type annotation to TypeScript type."""
    python_type = python_type.strip()

    # Handle basic types
    type_mapping = {
        "str": "string",
        "int": "number",
        "float": "number",
        "bool": "boolean",
        "datetime": "string",
        "UUID": "string",
        "Any": "any",
        "Dict": "Record<string, any>",
        "dict": "Record<string, any>",
    }

    for py_type, ts_type in type_mapping.items():
        if python_type == py_type:
            return ts_type

    # Handle Optional types
    if "Optional[" in python_type:
        inner_type = python_type.replace("Optional[", "").rstrip("]")
        return f"{convert_python_to_ts_type(inner_type)} | null"

    # Handle List types
    if "List[" in python_type or "list[" in python_type:
        inner_type = re.search(r"List\[([^\]]+)\]|list\[([^\]]+)\]", python_type)
        if inner_type:
            item_type = inner_type.group(1) or inner_type.group(2)
            return f"{convert_python_to_ts_type(item_type)}[]"
        return "any[]"

    # Handle Union types
    if "Union[" in python_type:
        # Extract union types - simplified
        return "any"  # For now

    # Handle known FXML4 types
    if python_type in [
        "TimeframeEnum",
        "SignalTypeEnum",
        "OrderSideEnum",
        "StrategyEnum",
        "DataSourceEnum",
    ]:
        return python_type

    # Default to the type name as-is (for custom classes)
    return python_type


def main():
    """Generate TypeScript types from key FXML4 files."""
    print("🔄 Generating TypeScript types from FXML4 schemas...")

    # Key files to extract types from
    schema_files = [
        Path("fxml4/api/schemas.py"),
    ]

    # Additional files with models
    additional_files = [
        Path("fxml4/api/services/trading_engine.py"),
        Path("fxml4/api/services/order_management.py"),
        Path("fxml4/api/services/signal_processing.py"),
    ]

    all_types = []

    # Header
    header = """/**
 * Auto-generated TypeScript types from FXML4 Pydantic schemas
 *
 * DO NOT EDIT MANUALLY - This file is generated automatically
 * Run `python scripts/simple_type_generator.py` to regenerate
 */

// Utility types
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

    all_types.append(header)

    # Process each file
    for file_path in schema_files + additional_files:
        if file_path.exists():
            print(f"📂 Processing {file_path}")
            types = extract_pydantic_models_from_file(file_path)
            if types:
                all_types.append(f"// Types from {file_path}\n{types}\n")

    # Combine all types
    typescript_content = "".join(all_types)

    # Write to frontend types directory
    frontend_types_dir = Path("fxml4-ui/src/types")
    frontend_types_dir.mkdir(parents=True, exist_ok=True)

    output_file = frontend_types_dir / "api-generated.ts"

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(typescript_content)

    print(f"✅ Generated TypeScript definitions")
    print(f"📄 Wrote to {output_file}")

    # Update main types index
    index_file = frontend_types_dir / "index.ts"

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

        print(f"📝 Updated {index_file}")

    print("✅ TypeScript type generation complete!")


if __name__ == "__main__":
    main()
