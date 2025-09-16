#!/usr/bin/env python3
"""
FXML4 Functionality Test Script

This script tests basic functionality of FXML4 components that can work
without external dependencies.
"""

import sys
import os
from pathlib import Path
import json

# Add current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

def test_imports():
    """Test that we can import core modules with minimal dependencies."""
    print("=== Testing Module Imports ===")
    
    success_count = 0
    
    # Test basic imports that should work without heavy dependencies
    try:
        from fxml4.strategy.integrated_strategy import SignalType, SignalStrength, SignalSource
        print("✓ SignalType, SignalStrength, SignalSource imported successfully")
        success_count += 1
    except Exception as e:
        print(f"✗ Signal enums import failed: {e}")
    
    try:
        from fxml4.backtesting.backtest_engine import OrderType, OrderSide, PositionStatus
        print("✓ OrderType, OrderSide, PositionStatus imported successfully")
        success_count += 1
    except Exception as e:
        print(f"✗ Backtest enums import failed: {e}")
    
    try:
        from fxml4.wave_analysis.elliott_wave import WaveType, WaveDirection, WaveLabel
        print("✓ WaveType, WaveDirection, WaveLabel imported successfully")
        success_count += 1
    except Exception as e:
        print(f"✗ Wave enums import failed: {e}")
    
    return success_count

def test_configuration():
    """Test configuration loading with minimal dependencies."""
    print("\n=== Testing Configuration Loading ===")
    
    try:
        # Try loading config without full dependencies
        import yaml
        
        with open('config/default.yaml', 'r') as f:
            config = yaml.safe_load(f)
        
        # Test essential configuration sections
        required_sections = ['api', 'database', 'backtesting', 'ml', 'worker']
        missing_sections = []
        
        for section in required_sections:
            if section in config:
                print(f"✓ Config section '{section}' present")
            else:
                print(f"✗ Config section '{section}' missing")
                missing_sections.append(section)
        
        # Test specific important config values
        api_config = config.get('api', {})
        if 'host' in api_config and 'port' in api_config:
            print(f"✓ API configuration: {api_config['host']}:{api_config['port']}")
        else:
            print("✗ API host/port not configured")
        
        db_config = config.get('database', {})
        if 'host' in db_config and 'port' in db_config:
            print(f"✓ Database configuration: {db_config['host']}:{db_config['port']}")
        else:
            print("✗ Database host/port not configured")
        
        return len(missing_sections) == 0
        
    except Exception as e:
        print(f"✗ Configuration test failed: {e}")
        return False

def test_data_structures():
    """Test that we can create basic data structures."""
    print("\n=== Testing Data Structures ===")
    
    try:
        # Test creating Signal enum instances
        from fxml4.strategy.integrated_strategy import SignalType, SignalStrength, SignalSource
        
        signal_type = SignalType.ENTRY_LONG
        strength = SignalStrength.STRONG
        source = SignalSource.ML
        
        print(f"✓ Created signal enums: {signal_type.value}, {strength.value}, {source.value}")
        
        # Test creating Order enum instances
        from fxml4.backtesting.backtest_engine import OrderType, OrderSide
        
        order_type = OrderType.MARKET
        order_side = OrderSide.BUY
        
        print(f"✓ Created order enums: {order_type.value}, {order_side.value}")
        
        # Test creating Wave enum instances
        from fxml4.wave_analysis.elliott_wave import WaveType, WaveDirection
        
        wave_type = WaveType.IMPULSE
        wave_direction = WaveDirection.UP
        
        print(f"✓ Created wave enums: {wave_type.value}, {wave_direction.value}")
        
        return True
        
    except Exception as e:
        print(f"✗ Data structure test failed: {e}")
        return False

def test_cli_interface():
    """Test command-line interface parsing."""
    print("\n=== Testing CLI Interface ===")
    
    try:
        from fxml4.main import parse_args
        
        # Test default arguments
        args = parse_args([])
        print(f"✓ Default CLI args: mode={args.mode}")
        
        # Test custom arguments
        args = parse_args(['--mode', 'backtest', '--symbol', 'EURUSD'])
        print(f"✓ Custom CLI args: mode={args.mode}, symbol={args.symbol}")
        
        return True
        
    except Exception as e:
        print(f"✗ CLI interface test failed: {e}")
        return False

def test_file_structure():
    """Test that all expected files and directories exist."""
    print("\n=== Testing File Structure ===")
    
    essential_files = [
        "fxml4/main.py",
        "fxml4/config.py", 
        "fxml4/api/main.py",
        "fxml4/ui/main.py",
        "fxml4/ui/streamlit_app.py",
        "fxml4/worker/main.py",
        "fxml4/backtesting/backtest_engine.py",
        "fxml4/strategy/integrated_strategy.py",
        "fxml4/ml/features.py",
        "fxml4/wave_analysis/elliott_wave.py",
        "config/default.yaml",
        "Dockerfile",
        "docker-compose.yml",
        "monitoring/prometheus.yml"
    ]
    
    missing_files = []
    for file_path in essential_files:
        if os.path.exists(file_path):
            print(f"✓ {file_path}")
        else:
            print(f"✗ {file_path}")
            missing_files.append(file_path)
    
    return len(missing_files) == 0

def test_docker_configuration():
    """Test Docker configuration validity."""
    print("\n=== Testing Docker Configuration ===")
    
    try:
        import yaml
        
        # Test docker-compose.yml
        with open('docker-compose.yml', 'r') as f:
            docker_config = yaml.safe_load(f)
        
        # Check essential services
        required_services = ['api', 'dashboard', 'worker', 'db', 'redis']
        missing_services = []
        
        services = docker_config.get('services', {})
        for service in required_services:
            if service in services:
                print(f"✓ Docker service '{service}' defined")
            else:
                print(f"✗ Docker service '{service}' missing")
                missing_services.append(service)
        
        # Check that services have required configuration
        if 'api' in services:
            api_service = services['api']
            if 'ports' in api_service and 'command' in api_service:
                print("✓ API service properly configured")
            else:
                print("✗ API service missing essential configuration")
        
        return len(missing_services) == 0
        
    except Exception as e:
        print(f"✗ Docker configuration test failed: {e}")
        return False

def main():
    """Run all functionality tests."""
    print("FXML4 Functionality Test")
    print("=" * 50)
    
    test_results = []
    
    # Run all tests
    test_results.append(("Module Imports", test_imports() >= 2))
    test_results.append(("Configuration", test_configuration()))
    test_results.append(("Data Structures", test_data_structures()))
    test_results.append(("CLI Interface", test_cli_interface()))
    test_results.append(("File Structure", test_file_structure()))
    test_results.append(("Docker Configuration", test_docker_configuration()))
    
    # Generate summary report
    print("\n" + "=" * 50)
    print("FUNCTIONALITY TEST SUMMARY")
    print("=" * 50)
    
    passed_tests = sum(1 for _, result in test_results if result)
    total_tests = len(test_results)
    
    for test_name, result in test_results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{test_name:<20} {status}")
    
    print(f"\nOverall: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print("🎉 All functionality tests passed!")
        print("✅ FXML4 appears to be complete and functional!")
        return True
    else:
        print(f"⚠️  {total_tests - passed_tests} test(s) failed")
        print("🔧 Some functionality may need additional work")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)