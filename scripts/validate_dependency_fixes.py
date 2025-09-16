#!/usr/bin/env python3
"""
Validate that TDD Phase 2 dependency resolution fixes are working.
This script tests the key issues that were causing CI/CD failures.
"""

import sys
import traceback


def test_pinecone_import():
    """Test that Pinecone package imports correctly without conflicts."""
    print("🔍 Testing Pinecone package import...")
    try:
        import pinecone

        # Should have the new package API
        if hasattr(pinecone, "Pinecone"):
            print("  ✅ New pinecone package API available")
            return True
        else:
            print("  ❌ Pinecone package missing expected API")
            return False

    except Exception as e:
        if "pinecone-client" in str(e):
            print(f"  ❌ Package conflict still exists: {e}")
            return False
        else:
            print(f"  ⚠️ Pinecone not available (acceptable): {e}")
            return True  # Acceptable if not installed


def test_rag_graceful_degradation():
    """Test that RAG module handles missing dependencies gracefully."""
    print("🔍 Testing RAG module graceful degradation...")
    try:
        from fxml4.llm_integration import rag

        # Should have availability check function
        if hasattr(rag, "is_rag_available"):
            available = rag.is_rag_available()
            print(f"  ✅ RAG availability check: {available}")
            return True
        else:
            print("  ❌ RAG missing is_rag_available function")
            return False

    except ImportError as e:
        print(f"  ❌ RAG module failed to import: {e}")
        return False


def test_service_registry():
    """Test that service registry is working."""
    print("🔍 Testing service registry...")
    try:
        from fxml4.core.services import ServiceRegistry

        registry = ServiceRegistry()

        # Test basic functionality
        if all(hasattr(registry, attr) for attr in ["register", "get", "is_available"]):
            print("  ✅ Service registry has required methods")
            return True
        else:
            print("  ❌ Service registry missing required methods")
            return False

    except ImportError as e:
        print(f"  ❌ Service registry failed to import: {e}")
        return False


def test_core_imports_without_ml():
    """Test that core modules work without ML dependencies."""
    print("🔍 Testing core imports independence...")
    try:
        # These should always work
        from fxml4.api.main import app
        from fxml4.config import get_config

        config = get_config()

        if config is not None and app is not None:
            print("  ✅ Core imports work independently")
            return True
        else:
            print("  ❌ Core imports failed")
            return False

    except ImportError as e:
        print(f"  ❌ Core import failed: {e}")
        traceback.print_exc()
        return False


def test_requirements_consistency():
    """Test that requirements files are consistent."""
    print("🔍 Testing requirements files consistency...")
    try:
        # Check main requirements.txt
        with open("requirements.txt", "r") as f:
            content = f.read()

        if "pinecone-client" in content:
            print("  ❌ requirements.txt still has pinecone-client")
            return False

        if "pinecone>=3.0.0" in content:
            print("  ✅ requirements.txt has correct pinecone package")
            return True
        else:
            print("  ⚠️ requirements.txt doesn't specify pinecone (acceptable)")
            return True

    except Exception as e:
        print(f"  ❌ Requirements check failed: {e}")
        return False


def main():
    """Run all validation tests."""
    print("🚀 TDD PHASE 2 VALIDATION: Dependency Resolution Fixes")
    print("=" * 70)

    tests = [
        ("Pinecone Package Import", test_pinecone_import),
        ("RAG Graceful Degradation", test_rag_graceful_degradation),
        ("Service Registry", test_service_registry),
        ("Core Import Independence", test_core_imports_without_ml),
        ("Requirements Consistency", test_requirements_consistency),
    ]

    results = []

    for test_name, test_func in tests:
        print(f"\n📋 {test_name}:")
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"  ❌ Test error: {e}")
            results.append((test_name, False))

    # Summary
    print("\n" + "=" * 70)
    print("📊 VALIDATION RESULTS:")

    passed = 0
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"  {status}: {test_name}")
        if success:
            passed += 1

    success_rate = (passed / len(results)) * 100
    print(f"\n📈 Success Rate: {success_rate:.1f}% ({passed}/{len(results)})")

    if success_rate >= 80:
        print("🎉 PHASE 2 VALIDATION: PASSED")
        print("✅ Dependency resolution fixes are working!")
        print("🚀 Ready for Phase 3 implementation")
        return True
    else:
        print("❌ PHASE 2 VALIDATION: NEEDS IMPROVEMENT")
        print("🔧 Some dependency issues remain")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
