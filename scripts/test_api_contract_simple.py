#!/usr/bin/env python3
"""
Simple API Contract Testing Framework Validation

This script runs a simplified validation of the API contract testing framework.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import contract testing components
try:
    from tests.api_contracts.schemas import ALL_SCHEMAS, validate_schema_completeness
    from tests.api_contracts.test_contract_framework import APIContractTester

    IMPORTS_SUCCESSFUL = True
except ImportError as e:
    print(f"Import error: {e}")
    IMPORTS_SUCCESSFUL = False


async def main():
    """Simple validation test."""
    print("FXML4 API Contract Testing Framework - Simple Validation")
    print("=" * 60)

    if not IMPORTS_SUCCESSFUL:
        print("❌ Failed to import contract testing framework")
        return 1

    try:
        # Test 1: Schema validation
        print("1. Testing Schema Validation...")
        results = validate_schema_completeness()
        print(f"   ✓ Total schemas: {results['total_schemas']}")
        print(f"   ✓ Categories: {len(results['categories'])}")

        # Test 2: Basic framework functionality
        print("\n2. Testing Basic Framework...")
        async with APIContractTester() as tester:
            endpoints = tester.generate_test_endpoints()
            print(f"   ✓ Generated {len(endpoints)} endpoints")

            # Count by category
            category_counts = {}
            for endpoint in endpoints:
                category = endpoint.category.value
                category_counts[category] = category_counts.get(category, 0) + 1

            print("   ✓ Endpoint categories:")
            for category, count in sorted(category_counts.items()):
                print(f"      {category}: {count}")

        print("\n✅ API Contract Testing Framework is working!")
        print("\nSummary:")
        print(
            f"  • {results['total_schemas']} schemas across {len(results['categories'])} categories"
        )
        print(
            f"  • {len(endpoints)} endpoints across {len(category_counts)} categories"
        )
        print("  • Framework successfully generates and categorizes endpoints")
        print("  • Schema validation system functional")

        return 0

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
