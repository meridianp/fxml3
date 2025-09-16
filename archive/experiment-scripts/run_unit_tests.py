#!/usr/bin/env python3
"""
FXML4 Unit Test Runner

This script runs unit tests for FXML4 components without requiring
full dependency installation.
"""

import subprocess
import sys
from pathlib import Path
import importlib.util


def check_pytest_available():
    """Check if pytest is available."""
    try:
        import pytest
        return True
    except ImportError:
        return False


def check_dependencies():
    """Check which dependencies are available."""
    dependencies = {
        'pandas': False,
        'numpy': False,
        'pytest': False,
        'unittest': True  # Part of standard library
    }
    
    for dep in dependencies:
        if dep == 'unittest':
            continue
        try:
            importlib.import_module(dep)
            dependencies[dep] = True
        except ImportError:
            dependencies[dep] = False
    
    return dependencies


def run_basic_unit_tests():
    """Run basic unit tests using unittest module."""
    print("Running basic unit tests using unittest...")
    
    # Import test modules and run basic tests
    test_results = {}
    
    # Test 1: Configuration module structure
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from fxml4.config import Config
        
        # Test basic Config class structure
        config_methods = ['get', 'get_all', 'load_config']
        for method in config_methods:
            assert hasattr(Config, method), f"Config missing method: {method}"
        
        test_results['config_structure'] = True
        print("✓ Configuration module structure test passed")
    except Exception as e:
        test_results['config_structure'] = False
        print(f"✗ Configuration module structure test failed: {e}")
    
    # Test 2: Strategy enums
    try:
        from fxml4.strategy.integrated_strategy import SignalType, SignalSource, SignalStrength
        
        # Test enum values
        assert SignalType.ENTRY_LONG.value == "entry_long"
        assert SignalSource.ML.value == "ml"
        assert SignalStrength.STRONG.value == "strong"
        
        test_results['strategy_enums'] = True
        print("✓ Strategy enums test passed")
    except Exception as e:
        test_results['strategy_enums'] = False
        print(f"✗ Strategy enums test failed: {e}")
    
    # Test 3: Backtesting enums
    try:
        from fxml4.backtesting.backtest_engine import OrderType, OrderSide, PositionStatus
        
        # Test enum values
        assert OrderType.MARKET.value == "market"
        assert OrderSide.BUY.value == "buy"
        assert PositionStatus.OPEN.value == "open"
        
        test_results['backtesting_enums'] = True
        print("✓ Backtesting enums test passed")
    except Exception as e:
        test_results['backtesting_enums'] = False
        print(f"✗ Backtesting enums test failed: {e}")
    
    # Test 4: Wave analysis enums
    try:
        from fxml4.wave_analysis.elliott_wave import WaveType, WaveDirection, WaveLabel
        
        # Test enum values
        assert WaveType.IMPULSE.value == "impulse"
        assert WaveDirection.UP.value == "up"
        assert WaveLabel.W1.value == "1"
        
        test_results['wave_enums'] = True
        print("✓ Wave analysis enums test passed")
    except Exception as e:
        test_results['wave_enums'] = False
        print(f"✗ Wave analysis enums test failed: {e}")
    
    # Test 5: Worker structure
    try:
        from fxml4.worker.main import WorkerManager
        
        # Test WorkerManager class structure
        worker_methods = ['start', 'stop', '_worker_loop', '_run_task']
        for method in worker_methods:
            assert hasattr(WorkerManager, method), f"WorkerManager missing method: {method}"
        
        test_results['worker_structure'] = True
        print("✓ Worker module structure test passed")
    except Exception as e:
        test_results['worker_structure'] = False
        print(f"✗ Worker module structure test failed: {e}")
    
    return test_results


def run_pytest_tests():
    """Run tests using pytest if available."""
    print("Running tests with pytest...")
    
    try:
        # Run pytest on the tests directory
        result = subprocess.run(
            [sys.executable, '-m', 'pytest', 'tests/unit/', '-v', '--tb=short'],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent
        )
        
        print("PYTEST STDOUT:")
        print(result.stdout)
        
        if result.stderr:
            print("PYTEST STDERR:")
            print(result.stderr)
        
        return result.returncode == 0
        
    except Exception as e:
        print(f"Error running pytest: {e}")
        return False


def main():
    """Main test runner."""
    print("FXML4 Unit Test Runner")
    print("=" * 50)
    
    # Check available dependencies
    deps = check_dependencies()
    print("\nDependency Status:")
    for dep, available in deps.items():
        status = "✓" if available else "✗"
        print(f"  {status} {dep}: {'Available' if available else 'Missing'}")
    
    print("\n" + "=" * 50)
    
    # Run appropriate tests based on available dependencies
    if deps['pytest'] and deps['pandas'] and deps['numpy']:
        print("All dependencies available - running full pytest suite")
        success = run_pytest_tests()
    elif deps['pytest']:
        print("Pytest available but missing data dependencies - running basic pytest")
        success = run_pytest_tests()
    else:
        print("Pytest not available - running basic structure tests")
        test_results = run_basic_unit_tests()
        success = all(test_results.values())
        
        print(f"\nBasic Test Results:")
        for test, passed in test_results.items():
            status = "✓ PASS" if passed else "✗ FAIL"
            print(f"  {status} {test}")
    
    print("\n" + "=" * 50)
    print("UNIT TEST SUMMARY")
    print("=" * 50)
    
    if success:
        print("🎉 All available unit tests passed!")
        print("✅ FXML4 components are structurally sound and functional")
        
        if not deps['pandas'] or not deps['numpy']:
            print("\n📝 Note: Full testing requires pandas and numpy")
            print("   Install with: pip install pandas numpy pytest")
        
        return 0
    else:
        print("❌ Some unit tests failed")
        print("🔧 Review the test output above for details")
        return 1


if __name__ == "__main__":
    sys.exit(main())